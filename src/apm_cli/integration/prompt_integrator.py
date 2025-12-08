"""Prompt integration functionality for APM packages."""

from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass
import hashlib
import re
from datetime import datetime
import frontmatter

from .utils import normalize_repo_url
from apm_cli.compilation.link_resolver import UnifiedLinkResolver
from apm_cli.primitives.discovery import discover_primitives


@dataclass
class IntegrationResult:
    """Result of prompt integration operation."""
    files_integrated: int
    files_updated: int  # Updated due to version/commit change
    files_skipped: int  # Unchanged (same version/commit)
    target_paths: List[Path]
    gitignore_updated: bool
    links_resolved: int = 0  # Number of context links resolved


class PromptIntegrator:
    """Handles integration of APM package prompts into .github/prompts/."""
    
    def __init__(self):
        """Initialize the prompt integrator."""
        self.link_resolver = None  # Lazy init when needed
    
    def should_integrate(self, project_root: Path) -> bool:
        """Check if prompt integration should be performed.
        
        Args:
            project_root: Root directory of the project
            
        Returns:
            bool: Always True - integration happens automatically
        """
        return True
    
    def find_prompt_files(self, package_path: Path) -> List[Path]:
        """Find all .prompt.md files in a package.
        
        Searches in:
        - Package root directory
        - .apm/prompts/ subdirectory
        
        Args:
            package_path: Path to the package directory
            
        Returns:
            List[Path]: List of absolute paths to .prompt.md files
        """
        prompt_files = []
        
        # Search in package root
        if package_path.exists():
            prompt_files.extend(package_path.glob("*.prompt.md"))
        
        # Search in .apm/prompts/
        apm_prompts = package_path / ".apm" / "prompts"
        if apm_prompts.exists():
            prompt_files.extend(apm_prompts.glob("*.prompt.md"))
        
        return prompt_files
    
    def _parse_header_metadata(self, file_path: Path) -> dict:
        """Parse metadata from frontmatter or legacy header comment in an integrated prompt file.
        
        Args:
            file_path: Path to the integrated prompt file
            
        Returns:
            dict: Metadata extracted from frontmatter/header (version, commit, source, etc.)
                  Empty dict if no valid metadata found or parsing fails
        """
        try:
            # Try parsing frontmatter first (new format)
            post = frontmatter.load(file_path)
            
            # Check for nested apm metadata (new format)
            apm_data = post.metadata.get('apm', {})
            if apm_data:
                metadata = {
                    'Version': apm_data.get('version', ''),
                    'Commit': apm_data.get('commit', ''),
                    'Source': f"{apm_data.get('source', '')} ({apm_data.get('source_repo', '')})",
                    'SourceDependency': apm_data.get('source_dependency', ''),  # Full dependency string
                    'ContentHash': apm_data.get('content_hash', '')
                }
                return metadata
            
            # Fallback: Try legacy HTML comment format
            content = file_path.read_text(encoding='utf-8')
            
            # Check if file starts with comment block
            if not content.startswith('<!--'):
                return {}
            
            # Extract comment block (everything before the closing -->)
            end_marker = content.find('-->')
            if end_marker == -1:
                return {}
            
            header_text = content[4:end_marker].strip()
            
            # Parse key-value pairs from header
            metadata = {}
            for line in header_text.split('\n'):
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    metadata[key.strip()] = value.strip()
            
            return metadata
        except Exception:
            # If any error occurs during parsing, return empty dict
            return {}
    
    def _calculate_content_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file content (excluding frontmatter).
        
        Args:
            file_path: Path to the file
            
        Returns:
            str: Hexadecimal hash of the content
        """
        try:
            post = frontmatter.load(file_path)
            # Hash only the content, not the frontmatter
            return hashlib.sha256(post.content.encode()).hexdigest()
        except Exception:
            return ""
    
    def _should_update_prompt(self, existing_header: dict, package_info, existing_file: Path = None) -> tuple[bool, bool]:
        """Determine if an existing prompt file should be updated.
        
        Args:
            existing_header: Metadata from existing file's header
            package_info: PackageInfo object with new package metadata
            existing_file: Path to existing file for content hash verification
            
        Returns:
            tuple[bool, bool]: (should_update, was_modified)
                - should_update: True if file should be updated
                - was_modified: True if content was modified by user
        """
        # If no valid header exists, update the file
        if not existing_header:
            return (True, False)
        
        # Get new version and commit
        new_version = package_info.package.version
        new_commit = (
            package_info.resolved_reference.resolved_commit
            if package_info.resolved_reference
            else "unknown"
        )
        
        # Get existing version and commit from header
        existing_version = existing_header.get('Version', '')
        existing_commit = existing_header.get('Commit', '')
        
        # Check for content modifications if we have the file path
        was_modified = False
        if existing_file and existing_file.exists():
            stored_hash = existing_header.get('ContentHash', '')
            if stored_hash:
                current_hash = self._calculate_content_hash(existing_file)
                was_modified = (current_hash != stored_hash and current_hash != "")
        
        # Update if version or commit has changed
        should_update = (existing_version != new_version or existing_commit != new_commit)
        return (should_update, was_modified)
    
    def copy_prompt_with_metadata(self, source: Path, target: Path, package_info, original_path: Path) -> int:
        """Copy prompt file with metadata embedded in frontmatter.
        
        If source has frontmatter, adds nested apm: metadata.
        If source has no frontmatter, creates frontmatter with apm: metadata only.
        Resolves context links before writing.
        
        Args:
            source: Source file path
            target: Target file path
            package_info: PackageInfo object with package metadata
            original_path: Original path to the prompt file (for metadata)
        
        Returns:
            int: Number of links resolved
        """
        # Parse source file
        post = frontmatter.load(source)
        
        # Resolve context links in content
        links_resolved = 0
        if self.link_resolver:
            original_content = post.content
            resolved_content = self.link_resolver.resolve_links_for_installation(
                content=post.content,
                source_file=source,
                target_file=target
            )
            post.content = resolved_content
            # Count how many links changed by comparing actual link content
            if resolved_content != original_content:
                import re
                # Extract all links from both versions
                link_pattern = re.compile(r'\]\(([^)]+)\)')
                original_links = set(link_pattern.findall(original_content))
                resolved_links = set(link_pattern.findall(resolved_content))
                # Count links that were changed
                links_resolved = len(original_links - resolved_links)
        
        # Calculate content hash for modification detection (after link resolution)
        content_hash = hashlib.sha256(post.content.encode()).hexdigest()
        
        # Add nested apm metadata
        post.metadata['apm'] = {
            'source': package_info.package.name,
            'source_repo': package_info.package.source or "unknown",
            'source_dependency': package_info.get_canonical_dependency_string(),  # Full dependency string for orphan detection
            'version': package_info.package.version,
            'commit': (
                package_info.resolved_reference.resolved_commit
                if package_info.resolved_reference
                else "unknown"
            ),
            'original_path': (
                str(original_path.relative_to(package_info.install_path))
                if original_path.is_relative_to(package_info.install_path)
                else original_path.name
            ),
            'installed_at': package_info.installed_at or datetime.now().isoformat(),
            'content_hash': content_hash
        }
        
        # Write to target with updated frontmatter
        with open(target, 'w', encoding='utf-8') as f:
            f.write(frontmatter.dumps(post))
        
        return links_resolved
    
    def get_target_filename(self, source_file: Path, package_name: str) -> str:
        """Generate target filename with -apm suffix (intent-first naming).
        
        Args:
            source_file: Source file path
            package_name: Name of the package (not used in simple naming)
            
        Returns:
            str: Target filename with -apm suffix (e.g., accessibility-audit-apm.prompt.md)
        """
        # Intent-first naming: insert -apm suffix before .prompt.md extension
        # Example: design-review.prompt.md -> design-review-apm.prompt.md
        stem = source_file.stem.replace('.prompt', '')  # Remove .prompt from stem
        return f"{stem}-apm.prompt.md"
    

    
    def integrate_package_prompts(self, package_info, project_root: Path) -> IntegrationResult:
        """Integrate all prompts from a package into .github/prompts/.
        
        Implements smart update logic:
        - First install: Copy with header and @ prefix
        - Subsequent installs:
          - Compare version/commit with existing file
          - Update if different (re-copy with new header)
          - Skip if unchanged (preserve file timestamps)
        Resolves context links during integration.
        
        Args:
            package_info: PackageInfo object with package metadata
            project_root: Root directory of the project
            
        Returns:
            IntegrationResult: Results of the integration operation
        """
        # Initialize link resolver and register contexts
        self.link_resolver = UnifiedLinkResolver(project_root)
        try:
            primitives = discover_primitives(package_info.install_path)
            self.link_resolver.register_contexts(primitives)
        except Exception:
            # If context discovery fails, continue without link resolution
            self.link_resolver = None
        
        # Find all prompt files in the package
        prompt_files = self.find_prompt_files(package_info.install_path)
        
        if not prompt_files:
            return IntegrationResult(
                files_integrated=0,
                files_updated=0,
                files_skipped=0,
                target_paths=[],
                gitignore_updated=False
            )
        
        # Create .github/prompts/ if it doesn't exist
        prompts_dir = project_root / ".github" / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        
        # Process each prompt file
        files_integrated = 0
        files_updated = 0
        files_skipped = 0
        target_paths = []
        total_links_resolved = 0
        
        for source_file in prompt_files:
            # Generate target filename
            target_filename = self.get_target_filename(source_file, package_info.package.name)
            target_path = prompts_dir / target_filename
            
            # Check if target already exists
            if target_path.exists():
                # Parse existing file's metadata
                existing_header = self._parse_header_metadata(target_path)
                
                # Check if update is needed and if content was modified
                should_update, was_modified = self._should_update_prompt(
                    existing_header, package_info, target_path
                )
                
                if should_update:
                    # Warn if user modified the content
                    if was_modified:
                        from apm_cli.cli import _rich_warning
                        _rich_warning(
                            f"⚠ Restoring modified file: {target_path.name} "
                            f"(your changes will be overwritten)"
                        )
                    # Version or commit changed - update the file
                    links_resolved = self.copy_prompt_with_metadata(source_file, target_path, package_info, source_file)
                    total_links_resolved += links_resolved
                    files_updated += 1
                    target_paths.append(target_path)
                else:
                    # No change - skip to preserve file timestamp
                    files_skipped += 1
            else:
                # New file - integrate it
                links_resolved = self.copy_prompt_with_metadata(source_file, target_path, package_info, source_file)
                total_links_resolved += links_resolved
                files_integrated += 1
                target_paths.append(target_path)
        
        return IntegrationResult(
            files_integrated=files_integrated,
            files_updated=files_updated,
            files_skipped=files_skipped,
            target_paths=target_paths,
            gitignore_updated=False,
            links_resolved=total_links_resolved
        )
    
    def sync_integration(self, apm_package, project_root: Path) -> Dict[str, int]:
        """Sync .github/prompts/ with currently installed packages.
        
        - Removes prompts from uninstalled packages (orphans)
        - Updates prompts from updated packages
        - Adds prompts from new packages
        
        Idempotent: safe to call anytime. Reuses existing smart update logic.
        
        Args:
            apm_package: APMPackage with current dependencies
            project_root: Root directory of the project
            
        Returns:
            Dict with 'files_removed' and 'errors' counts
        """
        prompts_dir = project_root / ".github" / "prompts"
        if not prompts_dir.exists():
            return {'files_removed': 0, 'errors': 0}
        
        # Build set of canonical dependency strings for comparison
        # For virtual packages: owner/repo/path/to/file or owner/repo/collections/name
        # For regular packages: owner/repo
        installed_deps = set()
        installed_repo_urls = set()  # Fallback for old metadata format
        for dep in apm_package.get_apm_dependencies():
            installed_deps.add(dep.get_canonical_dependency_string())
            installed_repo_urls.add(dep.repo_url)
        
        # Track cleanup statistics
        files_removed = 0
        errors = 0
        
        # Remove orphaned prompts (from uninstalled packages)
        for prompt_file in prompts_dir.glob("*-apm.prompt.md"):
            metadata = self._parse_header_metadata(prompt_file)
            
            # Skip files without valid metadata - they might be user's custom files
            if not metadata:
                continue
            
            # Try new format first: source_dependency contains full dependency string
            source_dependency = metadata.get('SourceDependency', '')
            
            if source_dependency and source_dependency != 'unknown':
                # New format: compare full dependency strings directly
                # Both source_dependency and installed_deps are in canonical form
                package_match = source_dependency in installed_deps
            else:
                # Fallback: old format using repo URL from Source field
                source = metadata.get('Source', '')
                if not source:
                    continue
                
                # Extract package repo URL from source
                # Format: "package-name (owner/repo)" or "package-name (host.com/owner/repo)"
                package_repo_url = None
                if '(' in source and ')' in source:
                    package_repo_url = source.split('(')[1].split(')')[0].strip()
                
                if not package_repo_url:
                    continue
                
                # Normalize the repo URL for comparison
                normalized_package_url = normalize_repo_url(package_repo_url)
                
                # Check if source package is still installed (using repo_url for backwards compat)
                package_match = any(
                    pkg == normalized_package_url or 
                    (pkg + '.git') == normalized_package_url or
                    pkg == package_repo_url
                    for pkg in installed_repo_urls
                )
            
            if not package_match:
                try:
                    prompt_file.unlink()  # Orphaned - remove it
                    files_removed += 1
                except Exception:
                    errors += 1
        
        return {'files_removed': files_removed, 'errors': errors}
    
    def update_gitignore_for_integrated_prompts(self, project_root: Path) -> bool:
        """Update .gitignore with pattern for integrated prompts.
        
        Args:
            project_root: Root directory of the project
            
        Returns:
            bool: True if .gitignore was updated, False if pattern already exists
        """
        gitignore_path = project_root / ".gitignore"
        pattern = ".github/prompts/*-apm.prompt.md"
        
        # Read current content
        current_content = []
        if gitignore_path.exists():
            try:
                with open(gitignore_path, "r", encoding="utf-8") as f:
                    current_content = [line.rstrip("\n\r") for line in f.readlines()]
            except Exception:
                return False
        
        # Check if pattern already exists
        if any(pattern in line for line in current_content):
            return False
        
        # Add pattern to .gitignore
        try:
            with open(gitignore_path, "a", encoding="utf-8") as f:
                # Add a blank line before our entry if file isn't empty
                if current_content and current_content[-1].strip():
                    f.write("\n")
                f.write(f"\n# APM integrated prompts\n{pattern}\n")
            return True
        except Exception:
            return False

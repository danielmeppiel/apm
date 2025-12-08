"""Claude command integration functionality for APM packages.

Integrates .prompt.md files as .claude/commands/ during install,
mirroring how PromptIntegrator handles .github/prompts/.
"""

from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass
import hashlib
from datetime import datetime
import frontmatter

from apm_cli.compilation.link_resolver import UnifiedLinkResolver


@dataclass
class CommandIntegrationResult:
    """Result of command integration operation."""
    files_integrated: int
    files_updated: int  # Updated due to version/commit change
    files_skipped: int  # Unchanged (same version/commit)
    target_paths: List[Path]
    gitignore_updated: bool
    links_resolved: int = 0  # Number of context links resolved


class CommandIntegrator:
    """Handles integration of APM package prompts into .claude/commands/.
    
    Transforms .prompt.md files into Claude Code custom slash commands
    during package installation, following the same pattern as PromptIntegrator.
    """
    
    def __init__(self):
        """Initialize the command integrator."""
        self.link_resolver = None  # Lazy init when needed
    
    def should_integrate(self, project_root: Path) -> bool:
        """Check if command integration should be performed.
        
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
        """Parse metadata from frontmatter in an integrated command file.
        
        Args:
            file_path: Path to the integrated command file
            
        Returns:
            dict: Metadata extracted from frontmatter (version, commit, source, etc.)
                  Empty dict if no valid metadata found
        """
        try:
            post = frontmatter.load(file_path)
            apm_metadata = post.metadata.get('apm', {})
            
            if apm_metadata:
                return {
                    'Version': apm_metadata.get('version', ''),
                    'Commit': apm_metadata.get('commit', ''),
                    'Source': apm_metadata.get('source', ''),
                    'SourceDependency': apm_metadata.get('source_dependency', ''),
                    'ContentHash': apm_metadata.get('content_hash', ''),
                }
            return {}
        except Exception:
            return {}
    
    def _calculate_content_hash(self, file_path: Path) -> str:
        """Calculate hash of command content (excluding metadata).
        
        Args:
            file_path: Path to the command file
            
        Returns:
            str: SHA256 hash of content, or empty string if error
        """
        try:
            post = frontmatter.load(file_path)
            return hashlib.sha256(post.content.encode()).hexdigest()
        except Exception:
            return ""
    
    def _should_update_command(self, existing_header: dict, package_info, existing_file: Path = None) -> tuple:
        """Determine if an existing command file should be updated.
        
        Args:
            existing_header: Metadata from existing file's header
            package_info: PackageInfo object with new package metadata
            existing_file: Path to existing file for content hash verification
            
        Returns:
            tuple[bool, bool]: (should_update, was_modified)
        """
        if not existing_header:
            return (True, False)
        
        new_version = package_info.package.version
        new_commit = (
            package_info.resolved_reference.resolved_commit
            if package_info.resolved_reference
            else "unknown"
        )
        
        existing_version = existing_header.get('Version', '')
        existing_commit = existing_header.get('Commit', '')
        
        was_modified = False
        if existing_file and existing_file.exists():
            stored_hash = existing_header.get('ContentHash', '')
            if stored_hash:
                current_hash = self._calculate_content_hash(existing_file)
                was_modified = (current_hash != stored_hash and current_hash != "")
        
        should_update = (existing_version != new_version or existing_commit != new_commit)
        return (should_update, was_modified)
    
    def _transform_prompt_to_command(self, source: Path) -> tuple:
        """Transform a .prompt.md file into Claude command format.
        
        Args:
            source: Path to the .prompt.md file
            
        Returns:
            Tuple[str, frontmatter.Post, List[str]]: (command_name, post, warnings)
        """
        warnings: List[str] = []
        
        post = frontmatter.load(source)
        
        # Extract command name from filename
        filename = source.name
        if filename.endswith('.prompt.md'):
            command_name = filename[:-len('.prompt.md')]
        else:
            command_name = source.stem
        
        # Build Claude command frontmatter (preserve existing, add Claude-specific)
        claude_metadata = {}
        
        # Map APM frontmatter to Claude frontmatter
        if 'description' in post.metadata:
            claude_metadata['description'] = post.metadata['description']
        
        if 'allowed-tools' in post.metadata:
            claude_metadata['allowed-tools'] = post.metadata['allowed-tools']
        elif 'allowedTools' in post.metadata:
            claude_metadata['allowed-tools'] = post.metadata['allowedTools']
        
        if 'model' in post.metadata:
            claude_metadata['model'] = post.metadata['model']
        
        if 'argument-hint' in post.metadata:
            claude_metadata['argument-hint'] = post.metadata['argument-hint']
        elif 'argumentHint' in post.metadata:
            claude_metadata['argument-hint'] = post.metadata['argumentHint']
        
        # Create new post with Claude metadata
        new_post = frontmatter.Post(post.content)
        new_post.metadata = claude_metadata
        
        return (command_name, new_post, warnings)
    
    def integrate_command(self, source: Path, target: Path, package_info, original_path: Path) -> int:
        """Integrate a prompt file as a Claude command with metadata.
        
        Args:
            source: Source .prompt.md file path
            target: Target command file path in .claude/commands/
            package_info: PackageInfo object with package metadata
            original_path: Original path to the prompt file
            
        Returns:
            int: Number of links resolved
        """
        # Transform to command format
        command_name, post, warnings = self._transform_prompt_to_command(source)
        
        # Resolve context links in content
        links_resolved = 0
        if self.link_resolver:
            import re
            original_content = post.content
            resolved_content = self.link_resolver.resolve_links_for_installation(
                content=post.content,
                source_file=source,
                target_file=target
            )
            post.content = resolved_content
            if resolved_content != original_content:
                link_pattern = re.compile(r'\]\(([^)]+)\)')
                original_links = set(link_pattern.findall(original_content))
                resolved_links = set(link_pattern.findall(resolved_content))
                links_resolved = len(original_links - resolved_links)
        
        # Calculate content hash for modification detection
        content_hash = hashlib.sha256(post.content.encode()).hexdigest()
        
        # Add APM metadata for tracking
        post.metadata['apm'] = {
            'source': package_info.package.name,
            'source_repo': package_info.package.source or "unknown",
            'source_dependency': package_info.get_canonical_dependency_string(),
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
        
        # Ensure target directory exists
        target.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the command file
        with open(target, 'w', encoding='utf-8') as f:
            f.write(frontmatter.dumps(post))
        
        return links_resolved
    
    def integrate_package_commands(self, package_info, project_root: Path) -> CommandIntegrationResult:
        """Integrate all prompt files from a package as Claude commands.
        
        Args:
            package_info: PackageInfo object with package metadata and install path
            project_root: Root directory of the project
            
        Returns:
            CommandIntegrationResult: Result of integration
        """
        commands_dir = project_root / ".claude" / "commands"
        prompt_files = self.find_prompt_files(package_info.install_path)
        
        if not prompt_files:
            return CommandIntegrationResult(
                files_integrated=0,
                files_updated=0,
                files_skipped=0,
                target_paths=[],
                gitignore_updated=False,
                links_resolved=0
            )
        
        # Initialize link resolver if needed
        if self.link_resolver is None:
            self.link_resolver = UnifiedLinkResolver(project_root)
        
        files_integrated = 0
        files_updated = 0
        files_skipped = 0
        target_paths = []
        total_links_resolved = 0
        
        for prompt_file in prompt_files:
            # Generate command name with package suffix for uniqueness
            filename = prompt_file.name
            if filename.endswith('.prompt.md'):
                base_name = filename[:-len('.prompt.md')]
            else:
                base_name = prompt_file.stem
            
            # Add -apm suffix to distinguish from local prompts
            command_name = f"{base_name}-apm"
            target_path = commands_dir / f"{command_name}.md"
            
            # Check if update is needed
            if target_path.exists():
                existing_header = self._parse_header_metadata(target_path)
                should_update, was_modified = self._should_update_command(
                    existing_header, package_info, target_path
                )
                
                if was_modified:
                    # User modified the file - skip to preserve their changes
                    files_skipped += 1
                    target_paths.append(target_path)
                    continue
                
                if not should_update:
                    # Same version/commit - skip
                    files_skipped += 1
                    target_paths.append(target_path)
                    continue
                
                # Update needed
                links_resolved = self.integrate_command(
                    prompt_file, target_path, package_info, prompt_file
                )
                files_updated += 1
                total_links_resolved += links_resolved
            else:
                # New file
                links_resolved = self.integrate_command(
                    prompt_file, target_path, package_info, prompt_file
                )
                files_integrated += 1
                total_links_resolved += links_resolved
            
            target_paths.append(target_path)
        
        # Update .gitignore
        gitignore_updated = self._update_gitignore(project_root)
        
        return CommandIntegrationResult(
            files_integrated=files_integrated,
            files_updated=files_updated,
            files_skipped=files_skipped,
            target_paths=target_paths,
            gitignore_updated=gitignore_updated,
            links_resolved=total_links_resolved
        )
    
    def _update_gitignore(self, project_root: Path) -> bool:
        """Add .claude/commands/ patterns to .gitignore if needed.
        
        Args:
            project_root: Root directory of the project
            
        Returns:
            bool: True if .gitignore was updated
        """
        gitignore_path = project_root / ".gitignore"
        patterns = [
            "# APM-generated Claude commands",
            ".claude/commands/*-apm.md"
        ]
        
        existing_content = ""
        if gitignore_path.exists():
            existing_content = gitignore_path.read_text()
        
        # Check if patterns already exist
        if ".claude/commands/*-apm.md" in existing_content:
            return False
        
        # Add patterns
        new_content = existing_content.rstrip() + "\n\n" + "\n".join(patterns) + "\n"
        gitignore_path.write_text(new_content)
        return True
    
    def sync_integration(self, apm_package, project_root: Path) -> Dict:
        """Synchronize command integration - remove orphaned commands.
        
        Called during uninstall to clean up commands from removed packages.
        
        Args:
            apm_package: APMPackage with current dependencies
            project_root: Root directory of the project
            
        Returns:
            Dict with cleanup stats: {'files_removed': int, 'errors': int}
        """
        commands_dir = project_root / ".claude" / "commands"
        
        if not commands_dir.exists():
            return {'files_removed': 0, 'errors': 0}
        
        # Get current APM dependencies using get_unique_key() for proper matching
        # For regular packages: "owner/repo"
        # For virtual packages: "owner/repo/path/to/file.prompt.md"
        current_deps = set()
        if apm_package and apm_package.dependencies:
            apm_deps = apm_package.dependencies.get('apm', [])
            for dep in apm_deps:
                # DependencyReference has get_unique_key() for proper virtual package handling
                if hasattr(dep, 'get_unique_key'):
                    current_deps.add(dep.get_unique_key())
                elif hasattr(dep, 'repo_url'):
                    current_deps.add(dep.repo_url)
                elif isinstance(dep, str):
                    current_deps.add(dep)
        
        files_removed = 0
        errors = 0
        
        # Scan integrated command files (those with -apm suffix)
        for command_file in commands_dir.glob("*-apm.md"):
            try:
                metadata = self._parse_header_metadata(command_file)
                source_dep = metadata.get('SourceDependency', '')
                
                if source_dep and source_dep not in current_deps:
                    # Package is no longer installed - remove command
                    command_file.unlink()
                    files_removed += 1
            except Exception:
                errors += 1
        
        return {'files_removed': files_removed, 'errors': errors}
    
    def remove_package_commands(self, package_name: str, project_root: Path) -> int:
        """Remove all commands for a specific package.
        
        Args:
            package_name: Name of the package (e.g., "danielmeppiel/compliance-rules")
            project_root: Root directory of the project
            
        Returns:
            int: Number of files removed
        """
        commands_dir = project_root / ".claude" / "commands"
        
        if not commands_dir.exists():
            return 0
        
        files_removed = 0
        
        for command_file in commands_dir.glob("*-apm.md"):
            try:
                metadata = self._parse_header_metadata(command_file)
                source_dep = metadata.get('SourceDependency', '')
                
                if package_name in source_dep:
                    command_file.unlink()
                    files_removed += 1
            except Exception:
                # Skip files that can't be read or removed - continue with remaining files
                pass
        
        return files_removed

"""Prompt integration functionality for APM packages."""

from pathlib import Path
from typing import List
from dataclasses import dataclass
import shutil
from datetime import datetime


@dataclass
class IntegrationResult:
    """Result of prompt integration operation."""
    files_integrated: int
    files_updated: int  # Updated due to version/commit change
    files_skipped: int  # Unchanged (same version/commit)
    target_paths: List[Path]
    gitignore_updated: bool


class PromptIntegrator:
    """Handles integration of APM package prompts into .github/prompts/."""
    
    def __init__(self):
        """Initialize the prompt integrator."""
        pass
    
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
        """Parse metadata from header comment in an integrated prompt file.
        
        Args:
            file_path: Path to the integrated prompt file
            
        Returns:
            dict: Metadata extracted from header (version, commit, source, etc.)
                  Empty dict if no valid header found or parsing fails
        """
        try:
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
    
    def _should_update_prompt(self, existing_header: dict, package_info) -> bool:
        """Determine if an existing prompt file should be updated.
        
        Args:
            existing_header: Metadata from existing file's header
            package_info: PackageInfo object with new package metadata
            
        Returns:
            bool: True if file should be updated (version or commit changed)
        """
        # If no valid header exists, update the file
        if not existing_header:
            return True
        
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
        
        # Update if version or commit has changed
        return (existing_version != new_version or existing_commit != new_commit)
    
    def generate_header_comment(self, package_info, original_path: Path) -> str:
        """Generate metadata header comment for integrated prompt.
        
        Args:
            package_info: PackageInfo object with package metadata
            original_path: Original path to the prompt file
            
        Returns:
            str: Header comment with metadata
        """
        package_name = package_info.package.name
        version = package_info.package.version
        resolved_commit = (
            package_info.resolved_reference.resolved_commit
            if package_info.resolved_reference
            else "unknown"
        )
        
        # Get relative path within the package
        try:
            relative_path = original_path.relative_to(package_info.install_path)
        except ValueError:
            relative_path = original_path.name
        
        # Use installed_at from PackageInfo if available
        installed_at = package_info.installed_at or datetime.now().isoformat()
        
        # Determine source repository
        source_repo = package_info.package.source or "unknown"
        
        header = f"""<!-- 
Source: {package_name} ({source_repo})
Version: {version}
Commit: {resolved_commit}
Original: {relative_path}
Installed: {installed_at}
-->

"""
        return header
    
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
    
    def copy_prompt_with_header(self, source: Path, target: Path, header: str) -> None:
        """Copy prompt file with header comment prepended.
        
        Args:
            source: Source file path
            target: Target file path
            header: Header comment to prepend
        """
        # Read source content
        source_content = source.read_text(encoding='utf-8')
        
        # Write target with header
        target.write_text(header + source_content, encoding='utf-8')
    
    def integrate_package_prompts(self, package_info, project_root: Path) -> IntegrationResult:
        """Integrate all prompts from a package into .github/prompts/.
        
        Implements smart update logic:
        - First install: Copy with header and @ prefix
        - Subsequent installs:
          - Compare version/commit with existing file
          - Update if different (re-copy with new header)
          - Skip if unchanged (preserve file timestamps)
        
        Args:
            package_info: PackageInfo object with package metadata
            project_root: Root directory of the project
            
        Returns:
            IntegrationResult: Results of the integration operation
        """
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
        
        for source_file in prompt_files:
            # Generate target filename
            target_filename = self.get_target_filename(source_file, package_info.package.name)
            target_path = prompts_dir / target_filename
            
            # Generate header comment for new/updated file
            header = self.generate_header_comment(package_info, source_file)
            
            # Check if target already exists
            if target_path.exists():
                # Parse existing file's header
                existing_header = self._parse_header_metadata(target_path)
                
                # Check if update is needed
                if self._should_update_prompt(existing_header, package_info):
                    # Version or commit changed - update the file
                    self.copy_prompt_with_header(source_file, target_path, header)
                    files_updated += 1
                    target_paths.append(target_path)
                else:
                    # No change - skip to preserve file timestamp
                    files_skipped += 1
            else:
                # New file - integrate it
                self.copy_prompt_with_header(source_file, target_path, header)
                files_integrated += 1
                target_paths.append(target_path)
        
        return IntegrationResult(
            files_integrated=files_integrated,
            files_updated=files_updated,
            files_skipped=files_skipped,
            target_paths=target_paths,
            gitignore_updated=False
        )
    
    def sync_integration(self, apm_package, project_root: Path) -> None:
        """Sync .github/prompts/ with currently installed packages.
        
        - Removes prompts from uninstalled packages (orphans)
        - Updates prompts from updated packages
        - Adds prompts from new packages
        
        Idempotent: safe to call anytime. Reuses existing smart update logic.
        
        Args:
            apm_package: APMPackage with current dependencies
            project_root: Root directory of the project
        """
        prompts_dir = project_root / ".github" / "prompts"
        if not prompts_dir.exists():
            return
        
        # Get currently installed package URLs
        installed = {dep.repo_url for dep in apm_package.get_apm_dependencies()}
        
        # Remove orphaned prompts (from uninstalled packages)
        for prompt_file in prompts_dir.glob("*-apm.prompt.md"):
            metadata = self._parse_header_metadata(prompt_file)
            
            # Skip files without valid metadata - they might be user's custom files
            if not metadata:
                continue
            
            source = metadata.get('Source', '')
            
            # Skip if no source metadata
            if not source:
                continue
            
            # Extract package repo URL from source
            # Format: "package-name (owner/repo)" or "package-name (host.com/owner/repo)"
            # We need to match against the full URL including hostname if present
            # Works with any Git host: github.com, gitlab.com, git.company.com, etc.
            package_repo_url = None
            if '(' in source and ')' in source:
                # Extract content within parentheses - this is the full repo identifier
                package_repo_url = source.split('(')[1].split(')')[0].strip()
            
            if not package_repo_url:
                continue
            
            # Check if source package is still installed
            package_match = any(pkg == package_repo_url for pkg in installed)
            
            if not package_match:
                try:
                    prompt_file.unlink()  # Orphaned - remove it
                except Exception:
                    pass  # Silent failure OK for cleanup
    
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

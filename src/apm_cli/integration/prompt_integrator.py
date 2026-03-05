"""Prompt integration functionality for APM packages."""

from pathlib import Path
from typing import List, Dict

from apm_cli.integration.base_integrator import BaseIntegrator, IntegrationResult


class PromptIntegrator(BaseIntegrator):
    """Handles integration of APM package prompts into .github/prompts/."""
    
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
    
    def copy_prompt(self, source: Path, target: Path) -> int:
        """Copy prompt file verbatim with link resolution.
        
        Args:
            source: Source file path
            target: Target file path
        
        Returns:
            int: Number of links resolved
        """
        content = source.read_text(encoding='utf-8')
        content, links_resolved = self.resolve_links(content, source, target)
        target.write_text(content, encoding='utf-8')
        return links_resolved
    
    def get_target_filename(self, source_file: Path, package_name: str) -> str:
        """Generate target filename (clean, no suffix).
        
        Args:
            source_file: Source file path
            package_name: Name of the package (not used in simple naming)
            
        Returns:
            str: Target filename (e.g., accessibility-audit.prompt.md)
        """
        # Use original filename — no -apm suffix
        return source_file.name
    

    
    def integrate_package_prompts(self, package_info, project_root: Path,
                                    force: bool = False,
                                    managed_files: set = None) -> IntegrationResult:
        """Integrate all prompts from a package into .github/prompts/.
        
        Deploys with clean filenames. Skips files that exist locally and
        are not tracked in any package's deployed_files (user-authored),
        unless force=True.
        
        Args:
            package_info: PackageInfo object with package metadata
            project_root: Root directory of the project
            force: If True, overwrite user-authored files on collision
            managed_files: Set of relative paths known to be APM-managed
            
        Returns:
            IntegrationResult: Results of the integration operation
        """
        self.init_link_resolver(package_info, project_root)
        
        # Find all prompt files in the package
        prompt_files = self.find_prompt_files(package_info.install_path)
        
        if not prompt_files:
            return IntegrationResult(
                files_integrated=0,
                files_updated=0,
                files_skipped=0,
                target_paths=[],
                )
        
        # Create .github/prompts/ if it doesn't exist
        prompts_dir = project_root / ".github" / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        
        # Process each prompt file
        files_integrated = 0
        files_skipped = 0
        target_paths = []
        total_links_resolved = 0
        
        for source_file in prompt_files:
            target_filename = self.get_target_filename(source_file, package_info.package.name)
            target_path = prompts_dir / target_filename
            rel_path = str(target_path.relative_to(project_root))
            
            if self.check_collision(target_path, rel_path, managed_files, force):
                files_skipped += 1
                continue
            
            links_resolved = self.copy_prompt(source_file, target_path)
            total_links_resolved += links_resolved
            files_integrated += 1
            target_paths.append(target_path)
        
        return IntegrationResult(
            files_integrated=files_integrated,
            files_updated=0,
            files_skipped=files_skipped,
            target_paths=target_paths,
            links_resolved=total_links_resolved
        )
    
    def sync_integration(self, apm_package, project_root: Path,
                          managed_files: set = None) -> Dict[str, int]:
        """Remove APM-managed prompt files.

        Only removes files listed in *managed_files* (from apm.lock
        deployed_files).  Falls back to legacy ``*-apm.prompt.md`` glob
        when *managed_files* is ``None`` (old lockfile).
        """
        prompts_dir = project_root / ".github" / "prompts"
        return self.sync_remove_files(
            project_root,
            managed_files,
            prefix=".github/prompts/",
            legacy_glob_dir=prompts_dir,
            legacy_glob_pattern="*-apm.prompt.md",
        )


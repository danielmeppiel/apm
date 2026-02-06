"""Prompt integration functionality for APM packages."""

from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass
import re

from apm_cli.compilation.link_resolver import UnifiedLinkResolver
from apm_cli.primitives.discovery import discover_primitives


@dataclass
class IntegrationResult:
    """Result of prompt integration operation."""
    files_integrated: int
    files_updated: int  # Kept for CLI compatibility, always 0
    files_skipped: int  # Kept for CLI compatibility, always 0
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
    
    def copy_prompt(self, source: Path, target: Path) -> int:
        """Copy prompt file verbatim with link resolution.
        
        Copies file content as-is, only resolving context links.
        No metadata injection.
        
        Args:
            source: Source file path
            target: Target file path
        
        Returns:
            int: Number of links resolved
        """
        content = source.read_text(encoding='utf-8')
        links_resolved = 0
        
        if self.link_resolver:
            resolved_content = self.link_resolver.resolve_links_for_installation(
                content=content,
                source_file=source,
                target_file=target
            )
            if resolved_content != content:
                link_pattern = re.compile(r'\]\(([^)]+)\)')
                original_links = set(link_pattern.findall(content))
                resolved_links = set(link_pattern.findall(resolved_content))
                links_resolved = len(original_links - resolved_links)
                content = resolved_content
        
        target.write_text(content, encoding='utf-8')
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
        
        Always overwrites existing files (it's cheap).
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
        
        # Process each prompt file - always overwrite
        files_integrated = 0
        target_paths = []
        total_links_resolved = 0
        
        for source_file in prompt_files:
            target_filename = self.get_target_filename(source_file, package_info.package.name)
            target_path = prompts_dir / target_filename
            
            links_resolved = self.copy_prompt(source_file, target_path)
            total_links_resolved += links_resolved
            files_integrated += 1
            target_paths.append(target_path)
        
        return IntegrationResult(
            files_integrated=files_integrated,
            files_updated=0,
            files_skipped=0,
            target_paths=target_paths,
            gitignore_updated=False,
            links_resolved=total_links_resolved
        )
    
    def sync_integration(self, apm_package, project_root: Path) -> Dict[str, int]:
        """Remove all APM-managed prompt files for clean regeneration.
        
        Uses nuke-and-regenerate approach: removes all *-apm.prompt.md files.
        The caller re-integrates from currently installed packages.
        """
        stats = {'files_removed': 0, 'errors': 0}
        
        prompts_dir = project_root / ".github" / "prompts"
        if not prompts_dir.exists():
            return stats
        
        for prompt_file in prompts_dir.glob("*-apm.prompt.md"):
            try:
                prompt_file.unlink()
                stats['files_removed'] += 1
            except Exception:
                stats['errors'] += 1
        
        return stats
    
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

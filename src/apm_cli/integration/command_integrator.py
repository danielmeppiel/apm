"""Claude command integration functionality for APM packages.

Integrates .prompt.md files as .claude/commands/ during install,
mirroring how PromptIntegrator handles .github/prompts/.
"""

from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass
import frontmatter

from apm_cli.compilation.link_resolver import UnifiedLinkResolver


@dataclass
class CommandIntegrationResult:
    """Result of command integration operation."""
    files_integrated: int
    files_updated: int
    files_skipped: int
    target_paths: List[Path]
    gitignore_updated: bool
    links_resolved: int = 0


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
        """Integrate a prompt file as a Claude command (verbatim copy with format conversion).
        
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
        
        # Ensure target directory exists
        target.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the command file
        with open(target, 'w', encoding='utf-8') as f:
            f.write(frontmatter.dumps(post))
        
        return links_resolved
    
    def integrate_package_commands(self, package_info, project_root: Path,
                                    force: bool = False,
                                    managed_files: set = None) -> CommandIntegrationResult:
        """Integrate all prompt files from a package as Claude commands.
        
        Deploys with clean filenames. Skips user-authored files unless force=True.
        
        Args:
            package_info: PackageInfo object with package metadata and install path
            project_root: Root directory of the project
            force: If True, overwrite user-authored files on collision
            managed_files: Set of relative paths known to be APM-managed
            
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
        files_skipped = 0
        target_paths = []
        total_links_resolved = 0
        
        for prompt_file in prompt_files:
            # Generate clean command name (no suffix)
            filename = prompt_file.name
            if filename.endswith('.prompt.md'):
                base_name = filename[:-len('.prompt.md')]
            else:
                base_name = prompt_file.stem
            
            target_path = commands_dir / f"{base_name}.md"
            rel_path = str(target_path.relative_to(project_root))
            
            # Collision detection: skip user-authored files unless --force
            # managed_files=None means legacy mode (no collision checking)
            if managed_files is not None and target_path.exists() and rel_path not in managed_files and not force:
                import sys
                print(
                    f"\u26a0\ufe0f  Skipping {rel_path} \u2014 local file exists (not managed by APM). "
                    f"Use 'apm install --force' to overwrite.",
                    file=sys.stderr,
                )
                files_skipped += 1
                continue
            
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
            files_updated=0,
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
    
    def sync_integration(self, apm_package, project_root: Path,
                          managed_files: set = None) -> Dict:
        """Remove APM-managed command files from .claude/commands/.

        Only removes files listed in *managed_files*.  Falls back to
        legacy ``*-apm.md`` glob when *managed_files* is ``None``.
        """
        stats = {'files_removed': 0, 'errors': 0}
        
        commands_dir = project_root / ".claude" / "commands"
        if not commands_dir.exists():
            return stats

        if managed_files is not None:
            for rel_path in managed_files:
                if not rel_path.startswith(".claude/commands/") or ".." in rel_path:
                    continue
                target = project_root / rel_path
                if target.exists():
                    try:
                        target.unlink()
                        stats['files_removed'] += 1
                    except Exception:
                        stats['errors'] += 1
        else:
            for cmd_file in commands_dir.glob("*-apm.md"):
                try:
                    cmd_file.unlink()
                    stats['files_removed'] += 1
                except Exception:
                    stats['errors'] += 1
        
        return stats
    
    def remove_package_commands(self, package_name: str, project_root: Path,
                                managed_files: set = None) -> int:
        """Remove APM-managed command files.
        
        Uses *managed_files* when available; falls back to legacy glob.
        
        Args:
            package_name: Name of the package (unused)
            project_root: Root directory of the project
            managed_files: Set of relative paths known to be APM-managed
            
        Returns:
            int: Number of files removed
        """
        commands_dir = project_root / ".claude" / "commands"
        
        if not commands_dir.exists():
            return 0
        
        files_removed = 0

        if managed_files is not None:
            for rel_path in managed_files:
                if not rel_path.startswith(".claude/commands/") or ".." in rel_path:
                    continue
                target = project_root / rel_path
                if target.exists():
                    try:
                        target.unlink()
                        files_removed += 1
                    except Exception:
                        pass
        else:
            for cmd_file in commands_dir.glob("*-apm.md"):
                try:
                    cmd_file.unlink()
                    files_removed += 1
                except Exception:
                    pass
        
        return files_removed

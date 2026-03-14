"""Claude command integration functionality for APM packages.

Integrates .prompt.md files as .claude/commands/ during install,
mirroring how PromptIntegrator handles .github/prompts/.
"""

from pathlib import Path
from typing import List, Dict
import frontmatter

from apm_cli.integration.base_integrator import BaseIntegrator, IntegrationResult

# Re-export for backward compat (tests import CommandIntegrationResult)
CommandIntegrationResult = IntegrationResult


class CommandIntegrator(BaseIntegrator):
    """Handles integration of APM package prompts into .claude/commands/.
    
    Transforms .prompt.md files into Claude Code custom slash commands
    during package installation, following the same pattern as PromptIntegrator.
    """
    
    def find_prompt_files(self, package_path: Path) -> List[Path]:
        """Find all .prompt.md files in a package."""
        return self.find_files_by_glob(
            package_path, "*.prompt.md", subdirs=[".apm/prompts"]
        )
    
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
        post.content, links_resolved = self.resolve_links(post.content, source, target)
        
        # Ensure target directory exists
        target.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the command file
        with open(target, 'w', encoding='utf-8') as f:
            f.write(frontmatter.dumps(post))
        
        return links_resolved
    
    def integrate_package_commands(self, package_info, project_root: Path,
                                    force: bool = False,
                                    managed_files: set = None,
                                    diagnostics=None) -> IntegrationResult:
        """Integrate all prompt files from a package as Claude commands.
        
        Deploys with clean filenames. Skips user-authored files unless force=True.
        """
        commands_dir = project_root / ".claude" / "commands"
        prompt_files = self.find_prompt_files(package_info.install_path)
        
        if not prompt_files:
            return IntegrationResult(
                files_integrated=0,
                files_updated=0,
                files_skipped=0,
                target_paths=[],
                links_resolved=0
            )
        
        self.init_link_resolver(package_info, project_root)
        
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
            
            if self.check_collision(target_path, rel_path, managed_files, force, diagnostics=diagnostics):
                files_skipped += 1
                continue
            
            links_resolved = self.integrate_command(
                prompt_file, target_path, package_info, prompt_file
            )
            files_integrated += 1
            total_links_resolved += links_resolved
            target_paths.append(target_path)
        
        return IntegrationResult(
            files_integrated=files_integrated,
            files_updated=0,
            files_skipped=files_skipped,
            target_paths=target_paths,
            links_resolved=total_links_resolved
        )
    
    def sync_integration(self, apm_package, project_root: Path,
                          managed_files: set = None) -> Dict:
        """Remove APM-managed command files from .claude/commands/."""
        commands_dir = project_root / ".claude" / "commands"
        return self.sync_remove_files(
            project_root,
            managed_files,
            prefix=".claude/commands/",
            legacy_glob_dir=commands_dir,
            legacy_glob_pattern="*-apm.md",
        )
    
    def remove_package_commands(self, package_name: str, project_root: Path,
                                managed_files: set = None) -> int:
        """Remove APM-managed command files.
        
        Uses *managed_files* when available; falls back to legacy glob.
        """
        stats = self.sync_remove_files(
            project_root,
            managed_files,
            prefix=".claude/commands/",
            legacy_glob_dir=project_root / ".claude" / "commands",
            legacy_glob_pattern="*-apm.md",
        )
        return stats["files_removed"]

    def integrate_package_commands_opencode(self, package_info, project_root: Path,
                                            force: bool = False,
                                            managed_files: set = None,
                                            diagnostics=None) -> IntegrationResult:
        """Integrate all prompt files from a package as OpenCode commands.

        Deploys .prompt.md → .opencode/commands/<name>.md.
        Only deploys if .opencode/ directory already exists (opt-in).
        """
        opencode_dir = project_root / ".opencode"
        if not opencode_dir.exists() or not opencode_dir.is_dir():
            return IntegrationResult(
                files_integrated=0, files_updated=0,
                files_skipped=0, target_paths=[], links_resolved=0,
            )

        commands_dir = opencode_dir / "commands"
        prompt_files = self.find_prompt_files(package_info.install_path)

        if not prompt_files:
            return IntegrationResult(
                files_integrated=0, files_updated=0,
                files_skipped=0, target_paths=[], links_resolved=0,
            )

        self.init_link_resolver(package_info, project_root)

        files_integrated = 0
        files_skipped = 0
        target_paths = []
        total_links_resolved = 0

        for prompt_file in prompt_files:
            filename = prompt_file.name
            if filename.endswith('.prompt.md'):
                base_name = filename[:-len('.prompt.md')]
            else:
                base_name = prompt_file.stem

            target_path = commands_dir / f"{base_name}.md"
            rel_path = str(target_path.relative_to(project_root))

            if self.check_collision(target_path, rel_path, managed_files, force, diagnostics=diagnostics):
                files_skipped += 1
                continue

            links_resolved = self.integrate_command(
                prompt_file, target_path, package_info, prompt_file
            )
            files_integrated += 1
            total_links_resolved += links_resolved
            target_paths.append(target_path)

        return IntegrationResult(
            files_integrated=files_integrated,
            files_updated=0,
            files_skipped=files_skipped,
            target_paths=target_paths,
            links_resolved=total_links_resolved,
        )

    def sync_integration_opencode(self, apm_package, project_root: Path,
                                  managed_files: set = None) -> Dict:
        """Remove APM-managed command files from .opencode/commands/."""
        commands_dir = project_root / ".opencode" / "commands"
        return self.sync_remove_files(
            project_root,
            managed_files,
            prefix=".opencode/commands/",
            legacy_glob_dir=commands_dir,
            legacy_glob_pattern="*-apm.md",
        )

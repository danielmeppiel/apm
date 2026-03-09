"""OpenCode command integration functionality for APM packages.

Integrates .prompt.md files as .opencode/commands/ during install,
mirroring how PromptIntegrator handles .github/prompts/.
"""

from pathlib import Path
from typing import Dict, List

import frontmatter

from apm_cli.integration.base_integrator import BaseIntegrator, IntegrationResult

# Re-export for backward compat (tests import CommandIntegrationResult)
CommandIntegrationResult = IntegrationResult


class CommandIntegrator(BaseIntegrator):
    """Handles integration of APM package prompts into .opencode/commands/."""

    def find_prompt_files(self, package_path: Path) -> List[Path]:
        """Find all .prompt.md files in a package."""
        return self.find_files_by_glob(
            package_path,
            "*.prompt.md",
            subdirs=[".apm/prompts"],
        )

    def _transform_prompt_to_command(
        self, source: Path
    ) -> tuple[str, frontmatter.Post, List[str]]:
        """Transform a .prompt.md file into OpenCode command format."""
        warnings: List[str] = []
        post = frontmatter.load(str(source))

        filename = source.name
        if filename.endswith('.prompt.md'):
            command_name = filename[: -len(".prompt.md")]
        else:
            command_name = source.stem

        opencode_metadata = {}
        if "description" in post.metadata:
            opencode_metadata["description"] = post.metadata["description"]
        if "agent" in post.metadata:
            opencode_metadata["agent"] = post.metadata["agent"]
        if "model" in post.metadata:
            opencode_metadata["model"] = post.metadata["model"]
        if "subtask" in post.metadata:
            opencode_metadata["subtask"] = post.metadata["subtask"]

        new_post = frontmatter.Post(post.content)
        new_post.metadata = opencode_metadata
        return command_name, new_post, warnings

    def integrate_command(
        self,
        source: Path,
        target: Path,
        package_info,
        original_path: Path,
    ) -> int:
        """Integrate a prompt file as an OpenCode command."""
        _command_name, post, _warnings = self._transform_prompt_to_command(source)
        post.content, links_resolved = self.resolve_links(post.content, source, target)

        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))

        return links_resolved

    def integrate_package_commands(
        self,
        package_info,
        project_root: Path,
        force: bool = False,
        managed_files: set | None = None,
    ) -> IntegrationResult:
        """Integrate all prompt files from a package as OpenCode commands."""
        commands_dir = project_root / ".opencode" / "commands"
        prompt_files = self.find_prompt_files(package_info.install_path)

        if not prompt_files:
            return IntegrationResult(
                files_integrated=0,
                files_updated=0,
                files_skipped=0,
                target_paths=[],
                links_resolved=0,
            )

        self.init_link_resolver(package_info, project_root)

        files_integrated = 0
        files_skipped = 0
        target_paths = []
        total_links_resolved = 0

        for prompt_file in prompt_files:
            filename = prompt_file.name
            if filename.endswith('.prompt.md'):
                base_name = filename[: -len(".prompt.md")]
            else:
                base_name = prompt_file.stem

            target_path = commands_dir / f"{base_name}.md"
            rel_path = str(target_path.relative_to(project_root))

            if self.check_collision(target_path, rel_path, managed_files, force):
                files_skipped += 1
                continue

            links_resolved = self.integrate_command(
                prompt_file,
                target_path,
                package_info,
                prompt_file,
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

    def sync_integration(
        self,
        apm_package,
        project_root: Path,
        managed_files: set | None = None,
    ) -> Dict[str, int]:
        """Remove APM-managed command files from .opencode/commands/."""
        commands_dir = project_root / ".opencode" / "commands"
        return self.sync_remove_files(
            project_root,
            managed_files,
            prefix=".opencode/commands/",
            legacy_glob_dir=commands_dir,
            legacy_glob_pattern="*-apm.md",
        )

    def remove_package_commands(
        self,
        package_name: str,
        project_root: Path,
        managed_files: set | None = None,
    ) -> int:
        """Remove APM-managed command files."""
        stats = self.sync_remove_files(
            project_root,
            managed_files,
            prefix=".opencode/commands/",
            legacy_glob_dir=project_root / ".opencode" / "commands",
            legacy_glob_pattern="*-apm.md",
        )
        return stats["files_removed"]

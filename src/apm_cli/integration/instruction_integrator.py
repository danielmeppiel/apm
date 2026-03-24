"""Instruction integration functionality for APM packages.

Deploys .instructions.md files from APM packages to .github/instructions/
so VS Code Copilot picks them up natively with applyTo: scoping.

Also converts instructions to Cursor Rules (.mdc) format when a .cursor/
directory exists in the project root.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from apm_cli.integration.base_integrator import BaseIntegrator, IntegrationResult
from apm_cli.utils.paths import portable_relpath


class InstructionIntegrator(BaseIntegrator):
    """Handles integration of APM package instructions into .github/instructions/.

    Deploys .instructions.md files verbatim (preserving applyTo: frontmatter)
    so VS Code Copilot discovers them natively.
    """

    def find_instruction_files(self, package_path: Path) -> List[Path]:
        """Find all .instructions.md files in a package.

        Searches in .apm/instructions/ subdirectory.
        """
        return self.find_files_by_glob(
            package_path,
            "*.instructions.md",
            subdirs=[".apm/instructions"],
        )

    def copy_instruction(self, source: Path, target: Path) -> int:
        """Copy instruction file with link resolution.

        Preserves applyTo: frontmatter and all content as-is.
        """
        content = source.read_text(encoding='utf-8')
        content, links_resolved = self.resolve_links(content, source, target)
        target.write_text(content, encoding='utf-8')
        return links_resolved

    def integrate_package_instructions(
        self,
        package_info,
        project_root: Path,
        force: bool = False,
        managed_files: Optional[Set[str]] = None,
        diagnostics=None,
        logger=None,
    ) -> IntegrationResult:
        """Integrate all instructions from a package into .github/instructions/.

        Skips files that exist locally and are not tracked in any package's
        deployed_files (user-authored), unless force=True.
        """
        self.init_link_resolver(package_info, project_root)

        instruction_files = self.find_instruction_files(package_info.install_path)

        if not instruction_files:
            return IntegrationResult(
                files_integrated=0,
                files_updated=0,
                files_skipped=0,
                target_paths=[],
            )

        instructions_dir = project_root / ".github" / "instructions"
        instructions_dir.mkdir(parents=True, exist_ok=True)

        files_integrated = 0
        files_skipped = 0
        target_paths = []
        total_links_resolved = 0

        for source_file in instruction_files:
            target_path = instructions_dir / source_file.name
            rel_path = portable_relpath(target_path, project_root)

            if self.check_collision(target_path, rel_path, managed_files, force, diagnostics=diagnostics):
                files_skipped += 1
                continue

            links_resolved = self.copy_instruction(source_file, target_path)
            total_links_resolved += links_resolved
            files_integrated += 1
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
        managed_files: Optional[Set[str]] = None,
    ) -> Dict[str, int]:
        """Remove APM-managed instruction files.

        Only removes files listed in *managed_files* (from apm.lock
        deployed_files).  Falls back to a discovery-based scan when
        *managed_files* is ``None`` (old lockfile without deployed_files).
        """
        instructions_dir = project_root / ".github" / "instructions"
        return self.sync_remove_files(
            project_root,
            managed_files,
            prefix=".github/instructions/",
            legacy_glob_dir=instructions_dir,
            legacy_glob_pattern="*.instructions.md",
        )

    # ------------------------------------------------------------------
    # Cursor Rules (.mdc) support
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_to_cursor_rules(content: str) -> str:
        """Convert APM instruction content to Cursor Rules ``.mdc`` format.

        Parses existing YAML frontmatter, maps ``applyTo`` → ``globs``,
        extracts or generates a ``description``, and rewrites the
        frontmatter in Cursor's expected format.
        """
        body = content
        apply_to = ""
        description = ""

        # Parse existing frontmatter
        fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n?', content, re.DOTALL)
        if fm_match:
            fm_block = fm_match.group(1)
            body = content[fm_match.end():]

            for line in fm_block.splitlines():
                line_stripped = line.strip()
                if line_stripped.startswith("applyTo:"):
                    apply_to = line_stripped[len("applyTo:"):].strip().strip("'\"")
                elif line_stripped.startswith("description:"):
                    description = line_stripped[len("description:"):].strip().strip("'\"")

        # Generate description from first content sentence if missing
        if not description:
            for line in body.splitlines():
                stripped = line.strip().lstrip("#").strip()
                if stripped:
                    description = stripped.split(".")[0].strip()
                    break

        # Build Cursor Rules frontmatter
        parts = ["---"]
        if description:
            parts.append(f"description: {description}")
        if apply_to:
            parts.append(f'globs: "{apply_to}"')
        parts.append("---")

        return "\n".join(parts) + "\n\n" + body.lstrip("\n")

    def copy_instruction_cursor(self, source: Path, target: Path) -> int:
        """Copy instruction file converted to Cursor Rules format.

        Converts ``applyTo:`` → ``globs:`` frontmatter and resolves links.
        """
        content = source.read_text(encoding='utf-8')
        content = self._convert_to_cursor_rules(content)
        content, links_resolved = self.resolve_links(content, source, target)
        target.write_text(content, encoding='utf-8')
        return links_resolved

    def integrate_package_instructions_cursor(
        self,
        package_info,
        project_root: Path,
        force: bool = False,
        managed_files: Optional[Set[str]] = None,
        diagnostics=None,
        logger=None,
    ) -> IntegrationResult:
        """Integrate instructions as Cursor Rules into ``.cursor/rules/``.

        Only deploys when ``.cursor/`` already exists (opt-in).
        Creates ``.cursor/rules/`` subdirectory if needed.
        """
        cursor_dir = project_root / ".cursor"
        if not cursor_dir.exists():
            return IntegrationResult(
                files_integrated=0,
                files_updated=0,
                files_skipped=0,
                target_paths=[],
            )

        self.init_link_resolver(package_info, project_root)

        instruction_files = self.find_instruction_files(package_info.install_path)

        if not instruction_files:
            return IntegrationResult(
                files_integrated=0,
                files_updated=0,
                files_skipped=0,
                target_paths=[],
            )

        rules_dir = cursor_dir / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)

        files_integrated = 0
        files_skipped = 0
        target_paths = []
        total_links_resolved = 0

        for source_file in instruction_files:
            # Strip .instructions.md suffix, add .mdc
            stem = source_file.name
            if stem.endswith(".instructions.md"):
                stem = stem[: -len(".instructions.md")]
            mdc_name = f"{stem}.mdc"

            target_path = rules_dir / mdc_name
            rel_path = portable_relpath(target_path, project_root)

            if self.check_collision(target_path, rel_path, managed_files, force, diagnostics=diagnostics):
                files_skipped += 1
                continue

            links_resolved = self.copy_instruction_cursor(source_file, target_path)
            total_links_resolved += links_resolved
            files_integrated += 1
            target_paths.append(target_path)

        return IntegrationResult(
            files_integrated=files_integrated,
            files_updated=0,
            files_skipped=files_skipped,
            target_paths=target_paths,
            links_resolved=total_links_resolved,
        )

    def sync_integration_cursor(
        self,
        apm_package,
        project_root: Path,
        managed_files: Optional[Set[str]] = None,
    ) -> Dict[str, int]:
        """Remove APM-managed Cursor Rules files from ``.cursor/rules/``."""
        rules_dir = project_root / ".cursor" / "rules"
        return self.sync_remove_files(
            project_root,
            managed_files,
            prefix=".cursor/rules/",
            legacy_glob_dir=rules_dir,
            legacy_glob_pattern="*.mdc",
        )

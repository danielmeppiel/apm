"""Instruction integration functionality for APM packages.

Deploys .instructions.md files from APM packages to .github/instructions/
so VS Code Copilot picks them up natively with applyTo: scoping.
"""

from pathlib import Path
from typing import Dict, List, Optional, Set

from apm_cli.integration.base_integrator import BaseIntegrator, IntegrationResult


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
            rel_path = str(target_path.relative_to(project_root))

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

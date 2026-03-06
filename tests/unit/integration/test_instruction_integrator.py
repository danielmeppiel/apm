"""Tests for instruction integration functionality."""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock
from datetime import datetime

from apm_cli.integration.instruction_integrator import InstructionIntegrator
from apm_cli.integration.base_integrator import IntegrationResult
from apm_cli.models.apm_package import PackageInfo, APMPackage, ResolvedReference, GitReferenceType


class TestInstructionIntegrator:
    """Test instruction integration logic."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)
        self.integrator = InstructionIntegrator()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_package_info(self, package_dir, name="test-pkg"):
        package = APMPackage(
            name=name,
            version="1.0.0",
            package_path=package_dir,
            source=f"github.com/test/{name}",
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123",
            ref_name="main",
        )
        return PackageInfo(
            package=package,
            install_path=package_dir,
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat(),
        )

    # ===== Discovery =====

    def test_should_integrate_always_returns_true(self):
        assert self.integrator.should_integrate(self.project_root) is True

    def test_find_instruction_files_in_apm_instructions(self):
        """Finds *.instructions.md files under .apm/instructions/."""
        pkg = self.project_root / "package"
        inst_dir = pkg / ".apm" / "instructions"
        inst_dir.mkdir(parents=True)
        (inst_dir / "python.instructions.md").write_text("---\napplyTo: '**/*.py'\n---\n# Python rules")
        (inst_dir / "readme.md").write_text("# Not an instruction")

        files = self.integrator.find_instruction_files(pkg)
        assert len(files) == 1
        assert files[0].name == "python.instructions.md"

    def test_find_instruction_files_returns_empty_when_no_dir(self):
        pkg = self.project_root / "package"
        pkg.mkdir()
        assert self.integrator.find_instruction_files(pkg) == []

    def test_find_multiple_instruction_files(self):
        pkg = self.project_root / "package"
        inst_dir = pkg / ".apm" / "instructions"
        inst_dir.mkdir(parents=True)
        (inst_dir / "python.instructions.md").write_text("# Python")
        (inst_dir / "testing.instructions.md").write_text("# Testing")
        (inst_dir / "security.instructions.md").write_text("# Security")

        files = self.integrator.find_instruction_files(pkg)
        assert len(files) == 3

    # ===== Copy =====

    def test_copy_instruction_verbatim(self):
        """Copies content without modification when no link resolver."""
        source = self.project_root / "source.instructions.md"
        target = self.project_root / "target.instructions.md"
        content = "---\napplyTo: '**/*.py'\n---\n# Python coding standards\n\nUse type hints."
        source.write_text(content)

        self.integrator.copy_instruction(source, target)
        assert target.read_text() == content

    def test_copy_instruction_preserves_frontmatter(self):
        """Frontmatter with applyTo is preserved exactly."""
        source = self.project_root / "source.instructions.md"
        target = self.project_root / "target.instructions.md"
        content = "---\napplyTo: 'src/**/*.ts'\ndescription: TypeScript guidelines\n---\n\n# TS Rules"
        source.write_text(content)

        self.integrator.copy_instruction(source, target)
        assert target.read_text() == content

    # ===== Integration =====

    def test_integrate_creates_target_directory(self):
        """Creates .github/instructions/ if it doesn't exist."""
        pkg = self.project_root / "package"
        inst_dir = pkg / ".apm" / "instructions"
        inst_dir.mkdir(parents=True)
        (inst_dir / "python.instructions.md").write_text("# Python")

        (self.project_root / ".github").mkdir()
        pkg_info = self._make_package_info(pkg)

        result = self.integrator.integrate_package_instructions(pkg_info, self.project_root)

        assert result.files_integrated == 1
        assert (self.project_root / ".github" / "instructions").exists()

    def test_integrate_returns_integration_result(self):
        """Returns IntegrationResult (shared base type, not custom dataclass)."""
        pkg = self.project_root / "package"
        inst_dir = pkg / ".apm" / "instructions"
        inst_dir.mkdir(parents=True)
        (inst_dir / "python.instructions.md").write_text("# Python")

        pkg_info = self._make_package_info(pkg)
        result = self.integrator.integrate_package_instructions(pkg_info, self.project_root)

        assert isinstance(result, IntegrationResult)

    def test_integrate_keeps_original_filename(self):
        """Deploys with original filename — no suffix, no renaming."""
        pkg = self.project_root / "package"
        inst_dir = pkg / ".apm" / "instructions"
        inst_dir.mkdir(parents=True)
        (inst_dir / "python.instructions.md").write_text("# Python rules")

        pkg_info = self._make_package_info(pkg)
        self.integrator.integrate_package_instructions(pkg_info, self.project_root)

        target = self.project_root / ".github" / "instructions" / "python.instructions.md"
        assert target.exists()
        assert target.read_text() == "# Python rules"

    def test_integrate_overwrites_when_no_manifest(self):
        """Without managed_files (no manifest), overwrites existing files."""
        pkg = self.project_root / "package"
        inst_dir = pkg / ".apm" / "instructions"
        inst_dir.mkdir(parents=True)
        (inst_dir / "python.instructions.md").write_text("# New version")

        target_dir = self.project_root / ".github" / "instructions"
        target_dir.mkdir(parents=True)
        (target_dir / "python.instructions.md").write_text("# Old version")

        pkg_info = self._make_package_info(pkg)
        result = self.integrator.integrate_package_instructions(pkg_info, self.project_root)

        assert result.files_integrated == 1
        assert (target_dir / "python.instructions.md").read_text() == "# New version"

    def test_integrate_skips_user_file_collision(self):
        """Skips user-authored file when managed_files says it's not APM-owned."""
        pkg = self.project_root / "package"
        inst_dir = pkg / ".apm" / "instructions"
        inst_dir.mkdir(parents=True)
        (inst_dir / "python.instructions.md").write_text("# APM version")

        target_dir = self.project_root / ".github" / "instructions"
        target_dir.mkdir(parents=True)
        (target_dir / "python.instructions.md").write_text("# User version")

        pkg_info = self._make_package_info(pkg)
        # managed_files is empty set — python.instructions.md not in it → user-authored
        result = self.integrator.integrate_package_instructions(
            pkg_info, self.project_root, managed_files=set()
        )

        assert result.files_integrated == 0
        assert result.files_skipped == 1
        assert (target_dir / "python.instructions.md").read_text() == "# User version"

    def test_integrate_overwrites_managed_file(self):
        """Overwrites file when managed_files includes it (APM-owned)."""
        pkg = self.project_root / "package"
        inst_dir = pkg / ".apm" / "instructions"
        inst_dir.mkdir(parents=True)
        (inst_dir / "python.instructions.md").write_text("# Updated APM version")

        target_dir = self.project_root / ".github" / "instructions"
        target_dir.mkdir(parents=True)
        (target_dir / "python.instructions.md").write_text("# Old APM version")

        pkg_info = self._make_package_info(pkg)
        managed = {".github/instructions/python.instructions.md"}
        result = self.integrator.integrate_package_instructions(
            pkg_info, self.project_root, managed_files=managed
        )

        assert result.files_integrated == 1
        assert (target_dir / "python.instructions.md").read_text() == "# Updated APM version"

    def test_integrate_force_overwrites_user_file(self):
        """Force flag overrides collision detection."""
        pkg = self.project_root / "package"
        inst_dir = pkg / ".apm" / "instructions"
        inst_dir.mkdir(parents=True)
        (inst_dir / "python.instructions.md").write_text("# APM version")

        target_dir = self.project_root / ".github" / "instructions"
        target_dir.mkdir(parents=True)
        (target_dir / "python.instructions.md").write_text("# User version")

        pkg_info = self._make_package_info(pkg)
        result = self.integrator.integrate_package_instructions(
            pkg_info, self.project_root, force=True, managed_files=set()
        )

        assert result.files_integrated == 1
        assert (target_dir / "python.instructions.md").read_text() == "# APM version"

    def test_integrate_multiple_files_from_one_package(self):
        """Integrates all instruction files from a single package."""
        pkg = self.project_root / "package"
        inst_dir = pkg / ".apm" / "instructions"
        inst_dir.mkdir(parents=True)
        (inst_dir / "python.instructions.md").write_text("# Python")
        (inst_dir / "testing.instructions.md").write_text("# Testing")

        pkg_info = self._make_package_info(pkg)
        result = self.integrator.integrate_package_instructions(pkg_info, self.project_root)

        assert result.files_integrated == 2
        target_dir = self.project_root / ".github" / "instructions"
        assert (target_dir / "python.instructions.md").exists()
        assert (target_dir / "testing.instructions.md").exists()

    def test_integrate_returns_empty_when_no_instructions(self):
        """Returns zero-result when package has no instruction files."""
        pkg = self.project_root / "package"
        pkg.mkdir()

        pkg_info = self._make_package_info(pkg)
        result = self.integrator.integrate_package_instructions(pkg_info, self.project_root)

        assert result.files_integrated == 0
        assert result.target_paths == []

    def test_integrate_preserves_user_files_with_different_names(self):
        """User-authored instruction files with different names are untouched."""
        pkg = self.project_root / "package"
        inst_dir = pkg / ".apm" / "instructions"
        inst_dir.mkdir(parents=True)
        (inst_dir / "python.instructions.md").write_text("# APM Python")

        target_dir = self.project_root / ".github" / "instructions"
        target_dir.mkdir(parents=True)
        (target_dir / "my-custom.instructions.md").write_text("# My custom instructions")

        pkg_info = self._make_package_info(pkg)
        self.integrator.integrate_package_instructions(pkg_info, self.project_root)

        assert (target_dir / "my-custom.instructions.md").read_text() == "# My custom instructions"
        assert (target_dir / "python.instructions.md").read_text() == "# APM Python"

    def test_integrate_target_paths_are_absolute(self):
        """Target paths in result are absolute Path objects for deployed_files tracking."""
        pkg = self.project_root / "package"
        inst_dir = pkg / ".apm" / "instructions"
        inst_dir.mkdir(parents=True)
        (inst_dir / "python.instructions.md").write_text("# Python")

        pkg_info = self._make_package_info(pkg)
        result = self.integrator.integrate_package_instructions(pkg_info, self.project_root)

        assert len(result.target_paths) == 1
        tp = result.target_paths[0]
        assert tp.is_absolute()
        assert tp.relative_to(self.project_root).as_posix() == ".github/instructions/python.instructions.md"


class TestInstructionSyncIntegration:
    """Test sync_integration (manifest-based removal for uninstall)."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)
        self.integrator = InstructionIntegrator()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sync_removes_managed_files(self):
        """Removes files listed in managed_files from deployed_files manifest."""
        target_dir = self.project_root / ".github" / "instructions"
        target_dir.mkdir(parents=True)
        (target_dir / "python.instructions.md").write_text("# Python")
        (target_dir / "testing.instructions.md").write_text("# Testing")

        managed = {
            ".github/instructions/python.instructions.md",
            ".github/instructions/testing.instructions.md",
        }
        apm_package = Mock()
        result = self.integrator.sync_integration(apm_package, self.project_root, managed_files=managed)

        assert result['files_removed'] == 2
        assert not (target_dir / "python.instructions.md").exists()
        assert not (target_dir / "testing.instructions.md").exists()

    def test_sync_preserves_unmanaged_files(self):
        """Files not in managed_files are preserved (user-authored)."""
        target_dir = self.project_root / ".github" / "instructions"
        target_dir.mkdir(parents=True)
        (target_dir / "python.instructions.md").write_text("# APM Python")
        (target_dir / "my-custom.instructions.md").write_text("# User-authored")

        managed = {".github/instructions/python.instructions.md"}
        apm_package = Mock()
        result = self.integrator.sync_integration(apm_package, self.project_root, managed_files=managed)

        assert result['files_removed'] == 1
        assert not (target_dir / "python.instructions.md").exists()
        assert (target_dir / "my-custom.instructions.md").exists()

    def test_sync_legacy_fallback_removes_all_instruction_files(self):
        """Without managed_files, falls back to glob removing all *.instructions.md."""
        target_dir = self.project_root / ".github" / "instructions"
        target_dir.mkdir(parents=True)
        (target_dir / "python.instructions.md").write_text("# Python")
        (target_dir / "testing.instructions.md").write_text("# Testing")

        apm_package = Mock()
        result = self.integrator.sync_integration(apm_package, self.project_root, managed_files=None)

        assert result['files_removed'] == 2

    def test_sync_legacy_preserves_non_instruction_files(self):
        """Legacy glob only matches *.instructions.md — other files preserved."""
        target_dir = self.project_root / ".github" / "instructions"
        target_dir.mkdir(parents=True)
        (target_dir / "python.instructions.md").write_text("# Python")
        (target_dir / "README.md").write_text("# Readme")
        (target_dir / "notes.txt").write_text("notes")

        apm_package = Mock()
        result = self.integrator.sync_integration(apm_package, self.project_root, managed_files=None)

        assert result['files_removed'] == 1
        assert (target_dir / "README.md").exists()
        assert (target_dir / "notes.txt").exists()

    def test_sync_handles_missing_instructions_dir(self):
        """Gracefully handles missing .github/instructions/."""
        apm_package = Mock()
        result = self.integrator.sync_integration(apm_package, self.project_root)

        assert result['files_removed'] == 0
        assert result['errors'] == 0

    def test_sync_empty_managed_files_removes_nothing(self):
        """Empty managed_files set removes nothing."""
        target_dir = self.project_root / ".github" / "instructions"
        target_dir.mkdir(parents=True)
        (target_dir / "python.instructions.md").write_text("# Python")

        apm_package = Mock()
        result = self.integrator.sync_integration(apm_package, self.project_root, managed_files=set())

        assert result['files_removed'] == 0
        assert (target_dir / "python.instructions.md").exists()

    def test_sync_skips_files_not_on_disk(self):
        """Managed files that don't exist on disk are gracefully skipped."""
        target_dir = self.project_root / ".github" / "instructions"
        target_dir.mkdir(parents=True)

        managed = {".github/instructions/nonexistent.instructions.md"}
        apm_package = Mock()
        result = self.integrator.sync_integration(apm_package, self.project_root, managed_files=managed)

        assert result['files_removed'] == 0


class TestInstructionNameCollision:
    """Test behavior when APM instruction filenames collide with user files."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)
        self.integrator = InstructionIntegrator()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_package_info(self, package_dir, name="test-pkg"):
        package = APMPackage(
            name=name,
            version="1.0.0",
            package_path=package_dir,
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123",
            ref_name="main",
        )
        return PackageInfo(
            package=package,
            install_path=package_dir,
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat(),
        )

    def test_install_overwrites_when_managed(self):
        """APM-managed file with same name is overwritten."""
        pkg = self.project_root / "package"
        inst_dir = pkg / ".apm" / "instructions"
        inst_dir.mkdir(parents=True)
        (inst_dir / "python.instructions.md").write_text("# APM Python standards")

        target_dir = self.project_root / ".github" / "instructions"
        target_dir.mkdir(parents=True)
        (target_dir / "python.instructions.md").write_text("# Old version")

        pkg_info = self._make_package_info(pkg)
        managed = {".github/instructions/python.instructions.md"}
        result = self.integrator.integrate_package_instructions(
            pkg_info, self.project_root, managed_files=managed
        )

        assert result.files_integrated == 1
        assert (target_dir / "python.instructions.md").read_text() == "# APM Python standards"

    def test_two_packages_same_instruction_name_last_wins(self):
        """When two packages deploy the same filename, last-installed wins."""
        target_dir = self.project_root / ".github" / "instructions"
        target_dir.mkdir(parents=True)

        # Package A installs first
        pkg_a = self.project_root / "pkg-a"
        inst_a = pkg_a / ".apm" / "instructions"
        inst_a.mkdir(parents=True)
        (inst_a / "python.instructions.md").write_text("# Package A rules")
        info_a = self._make_package_info(pkg_a, "pkg-a")
        self.integrator.integrate_package_instructions(info_a, self.project_root)

        # Package B installs second — same filename
        pkg_b = self.project_root / "pkg-b"
        inst_b = pkg_b / ".apm" / "instructions"
        inst_b.mkdir(parents=True)
        (inst_b / "python.instructions.md").write_text("# Package B rules")
        info_b = self._make_package_info(pkg_b, "pkg-b")
        self.integrator.integrate_package_instructions(info_b, self.project_root)

        # Last write wins
        assert (target_dir / "python.instructions.md").read_text() == "# Package B rules"

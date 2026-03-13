"""Unit tests for apm_cli.bundle.packer."""

import tarfile
from pathlib import Path

import pytest
import yaml

from apm_cli.bundle.packer import pack_bundle, PackResult, _filter_files_by_target
from apm_cli.deps.lockfile import LockFile, LockedDependency


def _setup_project(tmp_path: Path, deployed_files: list[str], *, target: str | None = None) -> Path:
    """Create a minimal project with apm.yml, apm.lock.yaml, and deployed files on disk."""
    project = tmp_path / "project"
    project.mkdir()

    # apm.yml
    apm_yml = {"name": "test-pkg", "version": "1.0.0"}
    if target:
        apm_yml["target"] = target
    (project / "apm.yml").write_text(yaml.dump(apm_yml), encoding="utf-8")

    # Create deployed files on disk
    for fpath in deployed_files:
        full = project / fpath
        if fpath.endswith("/"):
            full.mkdir(parents=True, exist_ok=True)
        else:
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(f"content of {fpath}", encoding="utf-8")

    # apm.lock.yaml with a single dependency containing those files
    lockfile = LockFile()
    dep = LockedDependency(
        repo_url="owner/repo",
        resolved_commit="abc123",
        deployed_files=deployed_files,
    )
    lockfile.add_dependency(dep)
    lockfile.write(project / "apm.lock.yaml")

    return project


class TestFilterFilesByTarget:
    def test_vscode_only(self):
        files = [".github/agents/a.md", ".claude/commands/b.md"]
        assert _filter_files_by_target(files, "vscode") == [".github/agents/a.md"]

    def test_claude_only(self):
        files = [".github/agents/a.md", ".claude/commands/b.md"]
        assert _filter_files_by_target(files, "claude") == [".claude/commands/b.md"]

    def test_all_includes_both(self):
        files = [".github/agents/a.md", ".claude/commands/b.md"]
        assert _filter_files_by_target(files, "all") == files


class TestPackBundle:
    def test_pack_apm_format_vscode(self, tmp_path):
        deployed = [".github/agents/helper.agent.md", ".github/instructions/rules.md"]
        project = _setup_project(tmp_path, deployed, target="vscode")
        out = tmp_path / "build"

        result = pack_bundle(project, out, fmt="apm")

        assert result.bundle_path == out / "test-pkg-1.0.0"
        assert set(result.files) == set(deployed)
        assert result.lockfile_enriched
        # Files exist in bundle
        for f in deployed:
            assert (result.bundle_path / f).exists()
        # Enriched lockfile present
        lock_content = (result.bundle_path / "apm.lock.yaml").read_text()
        assert "pack:" in lock_content

    def test_pack_apm_format_claude(self, tmp_path):
        deployed = [".claude/commands/cmd.md", ".claude/skills/s1/SKILL.md"]
        project = _setup_project(tmp_path, deployed, target="claude")
        out = tmp_path / "build"

        result = pack_bundle(project, out, fmt="apm")

        assert set(result.files) == set(deployed)
        for f in deployed:
            assert (result.bundle_path / f).exists()

    def test_pack_apm_format_all(self, tmp_path):
        deployed = [".github/agents/a.md", ".claude/commands/b.md"]
        project = _setup_project(tmp_path, deployed, target="all")
        out = tmp_path / "build"

        result = pack_bundle(project, out, fmt="apm")

        assert set(result.files) == set(deployed)

    def test_pack_archive(self, tmp_path):
        deployed = [".github/agents/a.md"]
        project = _setup_project(tmp_path, deployed, target="vscode")
        out = tmp_path / "build"

        result = pack_bundle(project, out, archive=True)

        assert result.bundle_path.name == "test-pkg-1.0.0.tar.gz"
        assert result.bundle_path.exists()
        # The directory should be cleaned up
        assert not (out / "test-pkg-1.0.0").exists()
        # Archive is valid
        with tarfile.open(result.bundle_path, "r:gz") as tar:
            names = tar.getnames()
            assert any("a.md" in n for n in names)

    def test_pack_custom_output_dir(self, tmp_path):
        deployed = [".github/agents/a.md"]
        project = _setup_project(tmp_path, deployed, target="vscode")
        custom_out = tmp_path / "custom" / "output"

        result = pack_bundle(project, custom_out)

        assert result.bundle_path.parent == custom_out
        assert result.bundle_path.exists()

    def test_pack_dry_run(self, tmp_path):
        deployed = [".github/agents/a.md", ".github/instructions/b.md"]
        project = _setup_project(tmp_path, deployed, target="vscode")
        out = tmp_path / "build"

        result = pack_bundle(project, out, dry_run=True)

        assert set(result.files) == set(deployed)
        # Nothing written to disk
        assert not out.exists()

    def test_pack_no_lockfile_errors(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        (project / "apm.yml").write_text(
            yaml.dump({"name": "test", "version": "1.0.0"}), encoding="utf-8"
        )
        out = tmp_path / "build"

        with pytest.raises(FileNotFoundError, match="apm.lock.yaml not found"):
            pack_bundle(project, out)

    def test_pack_missing_deployed_file(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        (project / "apm.yml").write_text(
            yaml.dump({"name": "test", "version": "1.0.0"}), encoding="utf-8"
        )
        # Lock with a file that doesn't exist on disk
        lockfile = LockFile()
        dep = LockedDependency(
            repo_url="owner/repo",
            deployed_files=[".github/agents/ghost.md"],
        )
        lockfile.add_dependency(dep)
        lockfile.write(project / "apm.lock.yaml")
        out = tmp_path / "build"

        with pytest.raises(ValueError, match="missing on disk"):
            pack_bundle(project, out)

    def test_pack_empty_deployed_files(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        (project / "apm.yml").write_text(
            yaml.dump({"name": "test", "version": "1.0.0"}), encoding="utf-8"
        )
        lockfile = LockFile()
        dep = LockedDependency(repo_url="owner/repo", deployed_files=[])
        lockfile.add_dependency(dep)
        lockfile.write(project / "apm.lock.yaml")
        out = tmp_path / "build"

        result = pack_bundle(project, out)

        assert result.files == []
        assert result.bundle_path.exists()

    def test_pack_target_filtering(self, tmp_path):
        deployed = [".github/agents/a.md", ".claude/commands/b.md"]
        project = _setup_project(tmp_path, deployed)
        out = tmp_path / "build"

        result = pack_bundle(project, out, target="vscode")

        assert result.files == [".github/agents/a.md"]
        assert not (result.bundle_path / ".claude").exists()

    def test_pack_lockfile_enrichment(self, tmp_path):
        deployed = [".github/agents/a.md"]
        project = _setup_project(tmp_path, deployed, target="vscode")
        out = tmp_path / "build"

        result = pack_bundle(project, out)

        lock_yaml = yaml.safe_load((result.bundle_path / "apm.lock.yaml").read_text())
        assert "pack" in lock_yaml
        assert lock_yaml["pack"]["format"] == "apm"
        assert lock_yaml["pack"]["target"] == "vscode"
        assert "packed_at" in lock_yaml["pack"]

    def test_pack_lockfile_original_unchanged(self, tmp_path):
        deployed = [".github/agents/a.md"]
        project = _setup_project(tmp_path, deployed, target="vscode")
        out = tmp_path / "build"

        original_content = (project / "apm.lock.yaml").read_text()
        pack_bundle(project, out)

        assert (project / "apm.lock.yaml").read_text() == original_content

    def test_pack_rejects_embedded_traversal_in_deployed_path(self, tmp_path):
        """pack_bundle must reject path-traversal entries embedded in deployed_files."""
        project = _setup_project(tmp_path, [])
        # A path that looks like it starts with .github/ but traverses out
        lockfile = LockFile.read(project / "apm.lock.yaml")
        dep = LockedDependency(
            repo_url="owner/repo",
            deployed_files=[".github/../../../etc/passwd"],
        )
        lockfile.add_dependency(dep)
        lockfile.write(project / "apm.lock.yaml")

        with pytest.raises(ValueError, match="unsafe path"):
            pack_bundle(project, tmp_path / "out")

    def test_pack_rejects_traversal_deployed_path(self, tmp_path):
        """pack_bundle must reject path-traversal entries in deployed_files."""
        project = _setup_project(tmp_path, [])
        lockfile = LockFile.read(project / "apm.lock.yaml")
        dep = LockedDependency(
            repo_url="owner/repo",
            deployed_files=[".github/agents/../../../../../../tmp/evil.sh"],
        )
        lockfile.add_dependency(dep)
        lockfile.write(project / "apm.lock.yaml")

        with pytest.raises(ValueError, match="unsafe path"):
            pack_bundle(project, tmp_path / "out")

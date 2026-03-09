"""Unit tests for apm_cli.bundle.unpacker."""

import tarfile
from pathlib import Path

import pytest
import yaml

from apm_cli.bundle.unpacker import unpack_bundle, UnpackResult
from apm_cli.deps.lockfile import LockFile, LockedDependency


def _build_bundle_dir(tmp_path: Path, deployed_files: list[str]) -> Path:
    """Create a bundle directory with an enriched lockfile and the listed files."""
    bundle = tmp_path / "bundle" / "test-pkg-1.0.0"
    bundle.mkdir(parents=True)

    for fpath in deployed_files:
        full = bundle / fpath
        if fpath.endswith("/"):
            full.mkdir(parents=True, exist_ok=True)
        else:
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(f"content of {fpath}", encoding="utf-8")

    lockfile = LockFile()
    dep = LockedDependency(
        repo_url="owner/repo",
        resolved_commit="abc123",
        deployed_files=deployed_files,
    )
    lockfile.add_dependency(dep)
    lockfile.write(bundle / "apm.lock")
    return bundle


def _archive_bundle(bundle_dir: Path, dest: Path) -> Path:
    """Create a .tar.gz from a bundle directory."""
    archive_path = dest / f"{bundle_dir.name}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(bundle_dir, arcname=bundle_dir.name)
    return archive_path


class TestUnpackBundle:
    def test_unpack_directory(self, tmp_path):
        deployed = [".github/agents/a.md", ".github/instructions/b.md"]
        bundle = _build_bundle_dir(tmp_path, deployed)
        output = tmp_path / "target"
        output.mkdir()

        result = unpack_bundle(bundle, output)

        assert set(result.files) == set(deployed)
        assert result.verified
        for f in deployed:
            assert (output / f).exists()

    def test_unpack_archive(self, tmp_path):
        deployed = [".github/agents/a.md"]
        bundle = _build_bundle_dir(tmp_path, deployed)
        archive = _archive_bundle(bundle, tmp_path)
        output = tmp_path / "target"
        output.mkdir()

        result = unpack_bundle(archive, output)

        assert set(result.files) == set(deployed)
        assert result.verified
        assert (output / ".github" / "agents" / "a.md").exists()

    def test_unpack_verify_complete(self, tmp_path):
        deployed = [".github/agents/a.md", ".claude/commands/b.md"]
        bundle = _build_bundle_dir(tmp_path, deployed)
        output = tmp_path / "target"
        output.mkdir()

        result = unpack_bundle(bundle, output)

        assert result.verified

    def test_unpack_verify_missing_file(self, tmp_path):
        deployed = [".github/agents/a.md", ".github/agents/missing.md"]
        bundle_dir = tmp_path / "bundle" / "test-pkg-1.0.0"
        bundle_dir.mkdir(parents=True)

        # Only create one file on disk but claim two in lockfile
        (bundle_dir / ".github" / "agents").mkdir(parents=True)
        (bundle_dir / ".github" / "agents" / "a.md").write_text("ok")

        lockfile = LockFile()
        dep = LockedDependency(
            repo_url="owner/repo",
            deployed_files=deployed,
        )
        lockfile.add_dependency(dep)
        lockfile.write(bundle_dir / "apm.lock")

        output = tmp_path / "target"
        output.mkdir()

        with pytest.raises(ValueError, match="missing from the bundle"):
            unpack_bundle(bundle_dir, output)

    def test_unpack_skip_verify(self, tmp_path):
        deployed = [".github/agents/a.md", ".github/agents/missing.md"]
        bundle_dir = tmp_path / "bundle" / "test-pkg-1.0.0"
        bundle_dir.mkdir(parents=True)

        (bundle_dir / ".github" / "agents").mkdir(parents=True)
        (bundle_dir / ".github" / "agents" / "a.md").write_text("ok")

        lockfile = LockFile()
        dep = LockedDependency(
            repo_url="owner/repo",
            deployed_files=deployed,
        )
        lockfile.add_dependency(dep)
        lockfile.write(bundle_dir / "apm.lock")

        output = tmp_path / "target"
        output.mkdir()

        # skip_verify should bypass the missing-file check
        result = unpack_bundle(bundle_dir, output, skip_verify=True)
        assert not result.verified
        # a.md should still be copied
        assert (output / ".github" / "agents" / "a.md").exists()

    def test_unpack_dry_run(self, tmp_path):
        deployed = [".github/agents/a.md"]
        bundle = _build_bundle_dir(tmp_path, deployed)
        output = tmp_path / "target"
        output.mkdir()

        result = unpack_bundle(bundle, output, dry_run=True)

        assert result.files == deployed
        # Nothing written
        assert not (output / ".github").exists()

    def test_unpack_preserves_local_files(self, tmp_path):
        deployed = [".github/agents/a.md"]
        bundle = _build_bundle_dir(tmp_path, deployed)
        output = tmp_path / "target"
        output.mkdir()

        # Pre-existing local file
        local_file = output / ".github" / "instructions" / "my-local.md"
        local_file.parent.mkdir(parents=True)
        local_file.write_text("local content")

        unpack_bundle(bundle, output)

        # Local file untouched
        assert local_file.read_text() == "local content"
        # Bundle file present
        assert (output / ".github" / "agents" / "a.md").exists()

    def test_unpack_overwrites_bundle_files(self, tmp_path):
        deployed = [".github/agents/a.md"]
        bundle = _build_bundle_dir(tmp_path, deployed)
        output = tmp_path / "target"
        output.mkdir()

        # Pre-existing file with same path
        existing = output / ".github" / "agents" / "a.md"
        existing.parent.mkdir(parents=True)
        existing.write_text("old content")

        unpack_bundle(bundle, output)

        assert (output / ".github" / "agents" / "a.md").read_text() == "content of .github/agents/a.md"

    def test_unpack_lockfile_not_scattered(self, tmp_path):
        deployed = [".github/agents/a.md"]
        bundle = _build_bundle_dir(tmp_path, deployed)
        output = tmp_path / "target"
        output.mkdir()

        unpack_bundle(bundle, output)

        # apm.lock should NOT be copied to the output root
        assert not (output / "apm.lock").exists()

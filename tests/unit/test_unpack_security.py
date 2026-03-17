"""Unit tests for content scanning during bundle unpack."""

import os
from pathlib import Path
from typing import Union

import pytest

from apm_cli.bundle.unpacker import unpack_bundle, UnpackResult
from apm_cli.deps.lockfile import LockFile, LockedDependency


def _build_bundle_dir(tmp_path: Path, deployed_files: dict[str, Union[str, bytes]]) -> Path:
    """Create a bundle directory with a lockfile and file contents.

    Args:
        tmp_path: pytest tmp_path fixture.
        deployed_files: Mapping of relative path → file content.
    """
    bundle = tmp_path / "bundle" / "test-pkg-1.0.0"
    bundle.mkdir(parents=True)

    file_paths: list[str] = []
    for fpath, content in deployed_files.items():
        full = bundle / fpath
        full.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            full.write_bytes(content)
        else:
            full.write_text(content, encoding="utf-8")
        file_paths.append(fpath)

    lockfile = LockFile()
    dep = LockedDependency(
        repo_url="owner/repo",
        resolved_commit="abc123",
        deployed_files=file_paths,
    )
    lockfile.add_dependency(dep)
    lockfile.write(bundle / "apm.lock.yaml")
    return bundle


class TestUnpackSecurity:
    """Content scanning gate for apm unpack."""

    def test_unpack_clean_bundle(self, tmp_path):
        """Bundle with no findings unpacks normally."""
        bundle = _build_bundle_dir(tmp_path, {
            ".github/prompts/hello.md": "# Hello\nClean ASCII content.\n",
            ".github/instructions/guide.md": "Follow these steps.\n",
        })
        output = tmp_path / "target"
        output.mkdir()

        result = unpack_bundle(bundle, output_dir=output)

        assert len(result.files) == 2
        assert result.security_warnings == 0
        assert result.security_critical == 0
        assert (output / ".github/prompts/hello.md").exists()

    def test_unpack_critical_blocks(self, tmp_path):
        """Bundle with critical hidden characters raises ValueError."""
        # U+E0001 is a Unicode tag character (critical)
        malicious = "Innocent text \U000E0001 hidden tag"
        bundle = _build_bundle_dir(tmp_path, {
            ".github/prompts/bad.md": malicious,
        })
        output = tmp_path / "target"
        output.mkdir()

        with pytest.raises(ValueError, match="Blocked.*critical hidden characters"):
            unpack_bundle(bundle, output_dir=output)

        # File must NOT have been deployed
        assert not (output / ".github/prompts/bad.md").exists()

    def test_unpack_critical_force_allows(self, tmp_path):
        """Bundle with critical findings + force=True still deploys."""
        malicious = "Text with \U000E0001 tag character"
        bundle = _build_bundle_dir(tmp_path, {
            ".github/prompts/bad.md": malicious,
        })
        output = tmp_path / "target"
        output.mkdir()

        result = unpack_bundle(bundle, output_dir=output, force=True)

        assert len(result.files) == 1
        assert result.security_critical > 0
        assert (output / ".github/prompts/bad.md").exists()

    def test_unpack_warning_allows(self, tmp_path):
        """Bundle with warning-level findings deploys with count in result."""
        # U+200B is a zero-width space (warning)
        content = "Text with \u200b zero-width space"
        bundle = _build_bundle_dir(tmp_path, {
            ".github/prompts/warn.md": content,
        })
        output = tmp_path / "target"
        output.mkdir()

        result = unpack_bundle(bundle, output_dir=output)

        assert len(result.files) == 1
        assert result.security_warnings > 0
        assert result.security_critical == 0
        assert (output / ".github/prompts/warn.md").exists()

    def test_unpack_skips_symlinks(self, tmp_path):
        """Symlinked files in the bundle are not scanned."""
        bundle = _build_bundle_dir(tmp_path, {
            ".github/prompts/real.md": "Clean content\n",
        })
        # Create a symlink inside the bundle pointing to a file with critical content
        malicious_target = tmp_path / "outside.md"
        malicious_target.write_text("Text with \U000E0001 tag", encoding="utf-8")
        link = bundle / ".github/prompts/linked.md"
        try:
            link.symlink_to(malicious_target)
        except OSError:
            pytest.skip("Platform does not support symlinks")

        # Add the symlink to the lockfile so unpacker tries to process it
        lockfile = LockFile.read(bundle / "apm.lock.yaml")
        dep = lockfile.get_all_dependencies()[0]
        dep.deployed_files.append(".github/prompts/linked.md")
        lockfile.write(bundle / "apm.lock.yaml")

        output = tmp_path / "target"
        output.mkdir()

        # Should not raise — symlinks are skipped during scanning
        result = unpack_bundle(bundle, output_dir=output)
        assert result.security_critical == 0
        # Symlinked file must NOT be deployed
        assert not (output / ".github/prompts/linked.md").exists()

    def test_unpack_binary_files_skip(self, tmp_path):
        """Binary files don't cause scan errors."""
        # Random bytes that will fail UTF-8 decode
        binary_data = bytes(range(256))
        bundle = _build_bundle_dir(tmp_path, {
            ".github/prompts/clean.md": "Normal text\n",
            ".github/data/image.bin": binary_data,
        })
        output = tmp_path / "target"
        output.mkdir()

        result = unpack_bundle(bundle, output_dir=output)

        assert len(result.files) == 2
        assert result.security_warnings == 0
        assert result.security_critical == 0

    def test_unpack_scans_directory_contents(self, tmp_path):
        """Directory entries have their nested files scanned for hidden chars."""
        bundle = tmp_path / "bundle" / "test-pkg-1.0.0"
        bundle.mkdir(parents=True)

        # Create a directory with a poisoned nested file
        skills_dir = bundle / ".github" / "agents"
        skills_dir.mkdir(parents=True)
        (skills_dir / "safe.md").write_text("Safe content\n", encoding="utf-8")
        (skills_dir / "poisoned.md").write_text(
            "Hidden \U000E0001 tag", encoding="utf-8"
        )

        # Lockfile references the directory
        lockfile = LockFile()
        dep = LockedDependency(
            repo_url="owner/repo",
            resolved_commit="abc123",
            deployed_files=[".github/agents"],
        )
        lockfile.add_dependency(dep)
        lockfile.write(bundle / "apm.lock.yaml")

        output = tmp_path / "target"
        output.mkdir()

        with pytest.raises(ValueError, match="Blocked.*critical hidden characters"):
            unpack_bundle(bundle, output_dir=output)

    def test_unpack_directory_skips_nested_symlinks(self, tmp_path):
        """Nested symlinks inside deployed directories must not be deployed."""
        bundle = tmp_path / "bundle" / "test-pkg-1.0.0"
        bundle.mkdir(parents=True)

        # Create a directory with a regular file and a nested symlink
        skills_dir = bundle / ".github" / "agents"
        skills_dir.mkdir(parents=True)
        (skills_dir / "real.md").write_text("Real content\n", encoding="utf-8")

        # Create a symlink pointing outside the bundle
        outside = tmp_path / "secret.md"
        outside.write_text("Secret content\n", encoding="utf-8")
        try:
            (skills_dir / "linked.md").symlink_to(outside)
        except OSError:
            pytest.skip("Platform does not support symlinks")

        # Lockfile references the directory
        lockfile = LockFile()
        dep = LockedDependency(
            repo_url="owner/repo",
            resolved_commit="abc123",
            deployed_files=[".github/agents"],
        )
        lockfile.add_dependency(dep)
        lockfile.write(bundle / "apm.lock.yaml")

        output = tmp_path / "target"
        output.mkdir()

        result = unpack_bundle(bundle, output_dir=output)

        # Real file deployed, symlink filtered out
        assert (output / ".github/agents/real.md").exists()
        assert not (output / ".github/agents/linked.md").exists()

"""Regression test for GitHub issue #3186: nested hook descriptors silently ignored.

Hook descriptors placed in subdirectories of hooks/ (e.g. hooks/sub/hooks.json)
are copied into the deployed tree but never parsed or registered, because
find_hook_files uses a non-recursive glob while the bundle copy is recursive.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from apm_cli.integration.hook_integrator import HookIntegrator


class TestNestedHookDiscovery:
    """Tests that hook descriptors in subdirectories are discovered."""

    @pytest.fixture
    def temp_project(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_find_nested_hook_descriptor_in_hooks_subdir(self, temp_project):
        """Nested hooks.json inside hooks/ subdirectory should be discovered."""
        pkg_dir = temp_project / "pkg"
        hooks_dir = pkg_dir / "hooks"
        sub_dir = hooks_dir / "sub"
        sub_dir.mkdir(parents=True, exist_ok=True)

        # Root-level hook descriptor
        (hooks_dir / "hooks.json").write_text(
            json.dumps({"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "root.py"}]}]}})
        )
        # Nested hook descriptor
        (sub_dir / "hooks.json").write_text(
            json.dumps({"hooks": {"PostToolUse": [{"hooks": [{"type": "command", "command": "sub.py"}]}]}})
        )
        # Scripts
        (hooks_dir / "root.py").write_text("# root hook")
        (sub_dir / "sub.py").write_text("# sub hook")

        integrator = HookIntegrator()
        files = integrator.find_hook_files(pkg_dir)

        # Both root and nested descriptors should be found
        assert len(files) == 2, f"Expected 2 hook files, found {len(files)}: {files}"
        file_names = {f.name for f in files}
        assert "hooks.json" in file_names

    def test_find_nested_hook_descriptor_in_apm_hooks_subdir(self, temp_project):
        """Nested hooks.json inside .apm/hooks/ subdirectory should be discovered."""
        pkg_dir = temp_project / "pkg"
        hooks_dir = pkg_dir / ".apm" / "hooks"
        sub_dir = hooks_dir / "sub"
        sub_dir.mkdir(parents=True, exist_ok=True)

        # Root-level hook descriptor
        (hooks_dir / "hooks.json").write_text(
            json.dumps({"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "root.py"}]}]}})
        )
        # Nested hook descriptor
        (sub_dir / "hooks.json").write_text(
            json.dumps({"hooks": {"PostToolUse": [{"hooks": [{"type": "command", "command": "sub.py"}]}]}})
        )

        integrator = HookIntegrator()
        files = integrator.find_hook_files(pkg_dir)

        # Both root and nested descriptors should be found
        assert len(files) == 2, f"Expected 2 hook files, found {len(files)}: {files}"

    def test_find_only_nested_hook_descriptor(self, temp_project):
        """When only a nested descriptor exists (no root), it should still be discovered."""
        pkg_dir = temp_project / "pkg"
        hooks_dir = pkg_dir / "hooks"
        sub_dir = hooks_dir / "sub"
        sub_dir.mkdir(parents=True, exist_ok=True)

        # Only nested hook descriptor - no root descriptor
        (sub_dir / "hooks.json").write_text(
            json.dumps({"hooks": {"PostToolUse": [{"hooks": [{"type": "command", "command": "sub.py"}]}]}})
        )
        (sub_dir / "sub.py").write_text("# sub hook")

        integrator = HookIntegrator()
        files = integrator.find_hook_files(pkg_dir)

        # The nested descriptor should be found
        assert len(files) == 1, f"Expected 1 hook file, found {len(files)}: {files}"
        assert "sub" in str(files[0].parent)

    def test_find_multiple_nested_hook_descriptors(self, temp_project):
        """Multiple nested hook descriptors in different subdirectories should all be discovered."""
        pkg_dir = temp_project / "pkg"
        hooks_dir = pkg_dir / "hooks"

        # First subdirectory
        sub1_dir = hooks_dir / "check"
        sub1_dir.mkdir(parents=True, exist_ok=True)
        (sub1_dir / "hooks.json").write_text(
            json.dumps({"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "check.py"}]}]}})
        )
        (sub1_dir / "check.py").write_text("# check hook")

        # Second subdirectory
        sub2_dir = hooks_dir / "format"
        sub2_dir.mkdir(parents=True, exist_ok=True)
        (sub2_dir / "hooks.json").write_text(
            json.dumps({"hooks": {"PostToolUse": [{"hooks": [{"type": "command", "command": "format.py"}]}]}})
        )
        (sub2_dir / "format.py").write_text("# format hook")

        integrator = HookIntegrator()
        files = integrator.find_hook_files(pkg_dir)

        # Both nested descriptors should be found
        assert len(files) == 2, f"Expected 2 hook files, found {len(files)}: {files}"

    def test_find_nested_hook_descriptor_deep_nesting(self, temp_project):
        """Deeply nested hook descriptors should be discovered."""
        pkg_dir = temp_project / "pkg"
        hooks_dir = pkg_dir / "hooks"
        deep_dir = hooks_dir / "level1" / "level2" / "level3"
        deep_dir.mkdir(parents=True, exist_ok=True)

        (deep_dir / "hooks.json").write_text(
            json.dumps({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "deep.py"}]}]}})
        )
        (deep_dir / "deep.py").write_text("# deep hook")

        integrator = HookIntegrator()
        files = integrator.find_hook_files(pkg_dir)

        # The deeply nested descriptor should be found
        assert len(files) == 1, f"Expected 1 hook file, found {len(files)}: {files}"
        assert "level3" in str(files[0])

    def test_find_hook_files_still_finds_root_level(self, temp_project):
        """Root-level hook discovery should still work after adding recursive search."""
        pkg_dir = temp_project / "pkg"
        hooks_dir = pkg_dir / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)

        (hooks_dir / "hooks.json").write_text(
            json.dumps({"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "root.py"}]}]}})
        )
        (hooks_dir / "hooks.json").write_text(
            json.dumps({"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "root.py"}]}]}})
        )
        (hooks_dir / "root.py").write_text("# root hook")

        integrator = HookIntegrator()
        files = integrator.find_hook_files(pkg_dir)

        # Root-level hook should still be found
        assert len(files) == 1, f"Expected 1 hook file, found {len(files)}: {files}"

    def test_find_hook_files_excludes_non_json(self, temp_project):
        """Non-JSON files in hooks/ should not be discovered as hook descriptors."""
        pkg_dir = temp_project / "pkg"
        hooks_dir = pkg_dir / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)

        (hooks_dir / "hooks.json").write_text(json.dumps({"hooks": {}}))
        (hooks_dir / "readme.md").write_text("# not a hook")
        (hooks_dir / "data.txt").write_text("not a hook")

        integrator = HookIntegrator()
        files = integrator.find_hook_files(pkg_dir)

        # Only JSON files should be found
        assert len(files) == 1
        assert files[0].suffix == ".json"

    def test_find_hook_files_excludes_symlinks(self, temp_project):
        """Symlinks to hook JSON files should not be discovered."""
        pkg_dir = temp_project / "pkg"
        hooks_dir = pkg_dir / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)

        # Create a real file and a symlink
        real_file = hooks_dir / "real.json"
        real_file.write_text(json.dumps({"hooks": {}}))
        symlink = hooks_dir / "linked.json"
        symlink.symlink_to(real_file)

        integrator = HookIntegrator()
        files = integrator.find_hook_files(pkg_dir)

        # Only the real file should be found, not the symlink
        assert len(files) == 1
        assert files[0] == real_file

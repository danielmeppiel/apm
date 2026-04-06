"""Tests for symlink containment enforcement across APM subsystems.

Validates that symlinked primitive files are rejected at discovery and
resolution time, preventing arbitrary local file reads.
"""

import json
import os
import tempfile
import shutil
import unittest
from pathlib import Path


def _try_symlink(link: Path, target: Path):
    """Create a symlink or skip the test on platforms that don't support it."""
    try:
        link.symlink_to(target)
    except OSError:
        raise unittest.SkipTest("Symlinks not supported on this platform")


class TestPromptCompilerSymlinkContainment(unittest.TestCase):
    """PromptCompiler._resolve_prompt_file rejects external symlinks."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.project = Path(self.tmpdir) / "project"
        self.project.mkdir()
        self.outside = Path(self.tmpdir) / "outside"
        self.outside.mkdir()
        # Create a file outside the project
        self.secret = self.outside / "secret.txt"
        self.secret.write_text("sensitive-data", encoding="utf-8")
        # Create apm.yml so the project is valid
        (self.project / "apm.yml").write_text(
            "name: test\nversion: 1.0.0\n", encoding="utf-8"
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_symlinked_prompt_outside_project_rejected(self):
        """Symlinked .prompt.md is rejected with clear error message."""
        from apm_cli.core.script_runner import PromptCompiler

        prompts_dir = self.project / ".apm" / "prompts"
        prompts_dir.mkdir(parents=True)
        symlink = prompts_dir / "evil.prompt.md"
        _try_symlink(symlink, self.secret)

        compiler = PromptCompiler()
        old_cwd = os.getcwd()
        try:
            os.chdir(self.project)
            with self.assertRaises(FileNotFoundError) as ctx:
                compiler._resolve_prompt_file(".apm/prompts/evil.prompt.md")
            self.assertIn("symlink", str(ctx.exception).lower())
        finally:
            os.chdir(old_cwd)

    def test_normal_prompt_within_project_allowed(self):
        """Non-symlinked prompt files within the project are allowed."""
        from apm_cli.core.script_runner import PromptCompiler

        prompts_dir = self.project / ".apm" / "prompts"
        prompts_dir.mkdir(parents=True)
        prompt = prompts_dir / "safe.prompt.md"
        prompt.write_text("# Safe prompt", encoding="utf-8")

        compiler = PromptCompiler()
        old_cwd = os.getcwd()
        try:
            os.chdir(self.project)
            result = compiler._resolve_prompt_file(".apm/prompts/safe.prompt.md")
            self.assertTrue(result.exists())
        finally:
            os.chdir(old_cwd)


class TestPrimitiveDiscoverySymlinkContainment(unittest.TestCase):
    """find_primitive_files rejects symlinks outside base directory."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.project = Path(self.tmpdir) / "project"
        self.project.mkdir()
        self.outside = Path(self.tmpdir) / "outside"
        self.outside.mkdir()
        self.secret = self.outside / "leak.instructions.md"
        self.secret.write_text("---\napplyTo: '**'\n---\nLeaked!", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_symlinked_instruction_outside_base_rejected(self):
        """Symlinked .instructions.md outside base_dir is filtered out."""
        from apm_cli.primitives.discovery import find_primitive_files

        instructions_dir = self.project / ".github" / "instructions"
        instructions_dir.mkdir(parents=True)
        symlink = instructions_dir / "evil.instructions.md"
        _try_symlink(symlink, self.secret)

        # Also add a normal file
        normal = instructions_dir / "safe.instructions.md"
        normal.write_text("---\napplyTo: '**'\n---\nSafe", encoding="utf-8")

        results = find_primitive_files(
            str(self.project),
            [".github/instructions/*.instructions.md"],
        )
        names = [f.name for f in results]
        self.assertIn("safe.instructions.md", names)
        self.assertNotIn("evil.instructions.md", names)


class TestBaseIntegratorSymlinkContainment(unittest.TestCase):
    """BaseIntegrator.find_files_by_glob rejects external symlinks."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.pkg = Path(self.tmpdir) / "pkg"
        self.pkg.mkdir()
        self.outside = Path(self.tmpdir) / "outside"
        self.outside.mkdir()
        self.secret = self.outside / "leak.agent.md"
        self.secret.write_text("# Leaked agent", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_symlinked_agent_outside_package_rejected(self):
        """Symlinked .agent.md outside package dir is filtered out."""
        from apm_cli.integration.base_integrator import BaseIntegrator

        agents_dir = self.pkg / ".apm" / "agents"
        agents_dir.mkdir(parents=True)
        symlink = agents_dir / "evil.agent.md"
        _try_symlink(symlink, self.secret)

        normal = agents_dir / "safe.agent.md"
        normal.write_text("# Safe agent", encoding="utf-8")

        results = BaseIntegrator.find_files_by_glob(
            self.pkg, "*.agent.md", subdirs=[".apm/agents"],
        )
        names = [f.name for f in results]
        self.assertIn("safe.agent.md", names)
        self.assertNotIn("evil.agent.md", names)


class TestHookIntegratorSymlinkContainment(unittest.TestCase):
    """HookIntegrator.find_hook_files rejects external symlinks."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.pkg = Path(self.tmpdir) / "pkg"
        self.pkg.mkdir()
        self.outside = Path(self.tmpdir) / "outside"
        self.outside.mkdir()
        self.secret = self.outside / "evil.json"
        self.secret.write_text(json.dumps({"hooks": {}}), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_symlinked_hook_json_outside_package_rejected(self):
        """Symlinked hook JSON outside package dir is filtered out."""
        from apm_cli.integration.hook_integrator import HookIntegrator

        hooks_dir = self.pkg / ".apm" / "hooks"
        hooks_dir.mkdir(parents=True)
        symlink = hooks_dir / "evil.json"
        _try_symlink(symlink, self.secret)

        normal = hooks_dir / "safe.json"
        normal.write_text(json.dumps({"hooks": {}}), encoding="utf-8")

        integrator = HookIntegrator()
        results = integrator.find_hook_files(self.pkg)
        names = [f.name for f in results]
        self.assertIn("safe.json", names)
        self.assertNotIn("evil.json", names)


if __name__ == "__main__":
    unittest.main()

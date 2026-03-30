"""Tests for active_targets() resolution in targets.py."""

import tempfile
import shutil
from pathlib import Path

from apm_cli.integration.targets import active_targets, KNOWN_TARGETS


class TestActiveTargets:
    """Verify active_targets() presence-based detection and fallback."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.root = Path(self.temp_dir)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -- auto-detect (no explicit target) --

    def test_nothing_exists_falls_back_to_copilot(self):
        targets = active_targets(self.root)
        assert len(targets) == 1
        assert targets[0].name == "copilot"

    def test_only_github_returns_copilot(self):
        (self.root / ".github").mkdir()
        targets = active_targets(self.root)
        assert [t.name for t in targets] == ["copilot"]

    def test_only_claude_returns_claude(self):
        (self.root / ".claude").mkdir()
        targets = active_targets(self.root)
        assert [t.name for t in targets] == ["claude"]

    def test_only_cursor_returns_cursor(self):
        (self.root / ".cursor").mkdir()
        targets = active_targets(self.root)
        assert [t.name for t in targets] == ["cursor"]

    def test_only_opencode_returns_opencode(self):
        (self.root / ".opencode").mkdir()
        targets = active_targets(self.root)
        assert [t.name for t in targets] == ["opencode"]

    def test_github_and_claude_returns_both(self):
        (self.root / ".github").mkdir()
        (self.root / ".claude").mkdir()
        targets = active_targets(self.root)
        names = {t.name for t in targets}
        assert names == {"copilot", "claude"}

    def test_all_four_dirs_returns_all_four(self):
        for d in (".github", ".claude", ".cursor", ".opencode"):
            (self.root / d).mkdir()
        targets = active_targets(self.root)
        assert len(targets) == 4

    def test_claude_and_cursor_without_github(self):
        (self.root / ".claude").mkdir()
        (self.root / ".cursor").mkdir()
        targets = active_targets(self.root)
        names = {t.name for t in targets}
        assert "copilot" not in names
        assert names == {"claude", "cursor"}

    # -- explicit target --

    def test_explicit_copilot(self):
        targets = active_targets(self.root, explicit_target="copilot")
        assert [t.name for t in targets] == ["copilot"]

    def test_explicit_claude(self):
        targets = active_targets(self.root, explicit_target="claude")
        assert [t.name for t in targets] == ["claude"]

    def test_explicit_all_returns_every_known_target(self):
        targets = active_targets(self.root, explicit_target="all")
        assert len(targets) == len(KNOWN_TARGETS)

    def test_explicit_vscode_alias(self):
        targets = active_targets(self.root, explicit_target="vscode")
        assert [t.name for t in targets] == ["copilot"]

    def test_explicit_agents_alias(self):
        targets = active_targets(self.root, explicit_target="agents")
        assert [t.name for t in targets] == ["copilot"]

    def test_explicit_overrides_detection(self):
        """Explicit target wins even if dirs for other targets exist."""
        (self.root / ".github").mkdir()
        (self.root / ".claude").mkdir()
        targets = active_targets(self.root, explicit_target="claude")
        assert [t.name for t in targets] == ["claude"]

    def test_explicit_unknown_returns_empty(self):
        targets = active_targets(self.root, explicit_target="nonexistent")
        assert targets == []


class TestIntegrationDispatchRegistry:
    """Verify INTEGRATION_DISPATCH covers every non-skill primitive."""

    def test_every_target_primitive_has_dispatch_entry(self):
        """Each (target, primitive) pair in KNOWN_TARGETS that is not 'skills'
        must have a matching entry in INTEGRATION_DISPATCH."""
        from apm_cli.integration.targets import INTEGRATION_DISPATCH

        missing = []
        for name, profile in KNOWN_TARGETS.items():
            for primitive in profile.primitives:
                if primitive == "skills":
                    continue
                key = (name, primitive)
                if key not in INTEGRATION_DISPATCH:
                    missing.append(key)

        assert missing == [], f"Missing dispatch entries: {missing}"

    def test_dispatch_entries_reference_valid_methods(self):
        """All integrator_key/method_name pairs in INTEGRATION_DISPATCH
        must exist on the actual integrator classes."""
        from apm_cli.integration.targets import INTEGRATION_DISPATCH
        from apm_cli.integration.prompt_integrator import PromptIntegrator
        from apm_cli.integration.agent_integrator import AgentIntegrator
        from apm_cli.integration.instruction_integrator import InstructionIntegrator
        from apm_cli.integration.command_integrator import CommandIntegrator
        from apm_cli.integration.hook_integrator import HookIntegrator

        class_map = {
            "prompt_integrator": PromptIntegrator,
            "agent_integrator": AgentIntegrator,
            "instruction_integrator": InstructionIntegrator,
            "command_integrator": CommandIntegrator,
            "hook_integrator": HookIntegrator,
        }

        for (target, primitive), (ikey, method, _) in INTEGRATION_DISPATCH.items():
            cls = class_map.get(ikey)
            assert cls is not None, f"Unknown integrator key: {ikey}"
            assert hasattr(cls, method), (
                f"({target}, {primitive}): {cls.__name__} has no method {method}"
            )


class TestIntegratePackageForTargets:
    """Tests for integrate_package_for_targets() dispatcher."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.root = Path(self.temp_dir)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_mock_integrators(self):
        from unittest.mock import MagicMock

        def _empty_result(*args, **kwargs):
            r = MagicMock()
            r.files_integrated = 0
            r.files_updated = 0
            r.links_resolved = 0
            r.target_paths = []
            r.skill_created = False
            r.sub_skills_promoted = 0
            r.hooks_integrated = 0
            return r

        integrators = {}
        for name in (
            "prompt_integrator",
            "agent_integrator",
            "skill_integrator",
            "instruction_integrator",
            "command_integrator",
            "hook_integrator",
        ):
            m = MagicMock()
            for method in (
                "integrate_package_prompts",
                "integrate_package_agents",
                "integrate_package_agents_claude",
                "integrate_package_agents_cursor",
                "integrate_package_agents_opencode",
                "integrate_package_skill",
                "integrate_package_instructions",
                "integrate_package_instructions_cursor",
                "integrate_package_commands",
                "integrate_package_commands_opencode",
                "integrate_package_hooks",
                "integrate_package_hooks_claude",
                "integrate_package_hooks_cursor",
            ):
                getattr(m, method).side_effect = _empty_result
            integrators[name] = m
        return integrators

    def test_opencode_target_skips_github(self):
        """Only opencode primitives should fire for opencode target."""
        from unittest.mock import MagicMock
        from apm_cli.integration.targets import integrate_package_for_targets

        pkg = MagicMock()
        integrators = self._make_mock_integrators()

        result = integrate_package_for_targets(
            [KNOWN_TARGETS["opencode"]],
            pkg, self.root, integrators,
        )

        integrators["prompt_integrator"].integrate_package_prompts.assert_not_called()
        integrators["agent_integrator"].integrate_package_agents.assert_not_called()
        integrators["agent_integrator"].integrate_package_agents_opencode.assert_called_once()
        integrators["command_integrator"].integrate_package_commands_opencode.assert_called_once()
        assert result["deployed_files"] == []

    def test_all_targets_calls_every_dispatch_entry(self):
        """With all 4 targets, every dispatch entry should fire once."""
        from unittest.mock import MagicMock
        from apm_cli.integration.targets import (
            integrate_package_for_targets,
            INTEGRATION_DISPATCH,
        )

        for d in (".github", ".claude", ".cursor", ".opencode"):
            (self.root / d).mkdir()

        pkg = MagicMock()
        integrators = self._make_mock_integrators()

        integrate_package_for_targets(
            list(KNOWN_TARGETS.values()),
            pkg, self.root, integrators,
        )

        for (target, primitive), (ikey, method, _) in INTEGRATION_DISPATCH.items():
            m = integrators[ikey]
            fn = getattr(m, method)
            assert fn.call_count == 1, (
                f"({target}, {primitive}) -> {ikey}.{method} "
                f"expected 1 call, got {fn.call_count}"
            )

"""Tests for the data-driven target x primitive dispatch architecture.

Validates that:
- Target gating correctly restricts which directories are written.
- Every (target, primitive) pair has a dispatch path.
- Synthetic TargetProfiles work without code changes.
- partition_managed_files produces correct bucket keys.
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from apm_cli.integration.base_integrator import BaseIntegrator, IntegrationResult
from apm_cli.integration.targets import KNOWN_TARGETS, PrimitiveMapping, TargetProfile
from apm_cli.commands.install import _integrate_package_primitives


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_integration_result(n=0):
    """Return an IntegrationResult with *n* files integrated."""
    return IntegrationResult(
        files_integrated=n,
        files_updated=0,
        files_skipped=0,
        target_paths=[],
        links_resolved=0,
    )


def _make_hook_result(n=0):
    """Return a MagicMock mimicking HookIntegrationResult."""
    hr = MagicMock()
    hr.hooks_integrated = n
    hr.target_paths = []
    return hr


def _make_skill_result():
    """Return a MagicMock mimicking SkillIntegrationResult."""
    sr = MagicMock()
    sr.skill_created = False
    sr.sub_skills_promoted = 0
    sr.target_paths = []
    return sr


def _make_mock_integrators():
    """Build a dict of mock integrators matching _integrate_package_primitives kwargs."""
    prompt = MagicMock()
    prompt.integrate_prompts_for_target = MagicMock(return_value=_make_integration_result())

    agent = MagicMock()
    agent.integrate_agents_for_target = MagicMock(return_value=_make_integration_result())

    command = MagicMock()
    command.integrate_commands_for_target = MagicMock(return_value=_make_integration_result())

    instruction = MagicMock()
    instruction.integrate_instructions_for_target = MagicMock(return_value=_make_integration_result())

    hook = MagicMock()
    hook.integrate_hooks_for_target = MagicMock(return_value=_make_hook_result())

    skill = MagicMock()
    skill.integrate_package_skill = MagicMock(return_value=_make_skill_result())

    return {
        "prompt_integrator": prompt,
        "agent_integrator": agent,
        "command_integrator": command,
        "instruction_integrator": instruction,
        "hook_integrator": hook,
        "skill_integrator": skill,
    }


def _dispatch(targets, integrators=None, package_info=None, project_root=None):
    """Call _integrate_package_primitives with defaults for convenience."""
    if integrators is None:
        integrators = _make_mock_integrators()
    if package_info is None:
        package_info = MagicMock()
    if project_root is None:
        project_root = Path("/fake/root")
    return _integrate_package_primitives(
        package_info,
        project_root,
        targets=targets,
        force=False,
        managed_files=set(),
        diagnostics=None,
        **integrators,
    ), integrators


# ===================================================================
# 1. TestTargetGatingRegression
# ===================================================================

class TestTargetGatingRegression:
    """Verify that the dispatch loop only invokes integrators for the
    primitives declared by each target, preventing cross-target writes."""

    def test_opencode_only_does_not_write_github_dirs(self):
        """With targets=[opencode], no .github/ primitive is dispatched."""
        targets = [KNOWN_TARGETS["opencode"]]
        _result, mocks = _dispatch(targets)

        # opencode does not declare prompts or instructions (those are copilot/cursor)
        for call_args in mocks["prompt_integrator"].integrate_prompts_for_target.call_args_list:
            target = call_args[0][0]
            assert target.root_dir != ".github"

        for call_args in mocks["instruction_integrator"].integrate_instructions_for_target.call_args_list:
            target = call_args[0][0]
            assert target.root_dir != ".github"

        # opencode has no hooks -- hook integrator should NOT be called for .github
        for call_args in mocks["hook_integrator"].integrate_hooks_for_target.call_args_list:
            target = call_args[0][0]
            assert target.root_dir != ".github"

    def test_cursor_only_does_not_write_claude_or_github(self):
        """With targets=[cursor], no .claude/ or .github/ primitives fire."""
        targets = [KNOWN_TARGETS["cursor"]]
        _result, mocks = _dispatch(targets)

        all_calls = []
        for name in ("prompt_integrator", "agent_integrator",
                      "command_integrator", "instruction_integrator",
                      "hook_integrator"):
            for method_name, method in vars(mocks[name]).items():
                if hasattr(method, "call_args_list"):
                    for call_args in method.call_args_list:
                        if call_args[0]:
                            target = call_args[0][0]
                            if hasattr(target, "root_dir"):
                                all_calls.append(target.root_dir)

        assert ".claude" not in all_calls
        assert ".github" not in all_calls

    def test_copilot_only_does_not_write_cursor_or_opencode(self):
        """With targets=[copilot], no .cursor/ or .opencode/ primitives fire."""
        targets = [KNOWN_TARGETS["copilot"]]
        _result, mocks = _dispatch(targets)

        dispatched_roots = set()
        for name in ("prompt_integrator", "agent_integrator",
                      "command_integrator", "instruction_integrator",
                      "hook_integrator"):
            for attr_name in dir(mocks[name]):
                method = getattr(mocks[name], attr_name)
                if hasattr(method, "call_args_list"):
                    for call_args in method.call_args_list:
                        if call_args[0] and hasattr(call_args[0][0], "root_dir"):
                            dispatched_roots.add(call_args[0][0].root_dir)

        assert ".cursor" not in dispatched_roots
        assert ".opencode" not in dispatched_roots

    def test_empty_targets_returns_zeros(self):
        """With targets=[], all counters are 0 and no integrators are called."""
        result, mocks = _dispatch(targets=[])

        assert result["prompts"] == 0
        assert result["agents"] == 0
        assert result["instructions"] == 0
        assert result["commands"] == 0
        assert result["hooks"] == 0
        assert result["skills"] == 0
        assert result["deployed_files"] == []

        # No target-driven methods should have been called
        mocks["prompt_integrator"].integrate_prompts_for_target.assert_not_called()
        mocks["agent_integrator"].integrate_agents_for_target.assert_not_called()
        mocks["command_integrator"].integrate_commands_for_target.assert_not_called()
        mocks["instruction_integrator"].integrate_instructions_for_target.assert_not_called()
        mocks["hook_integrator"].integrate_hooks_for_target.assert_not_called()
        # Skills are also gated by early return
        mocks["skill_integrator"].integrate_package_skill.assert_not_called()

    def test_all_targets_dispatches_all_primitives(self):
        """With all 4 targets, every primitive in every target is dispatched."""
        all_targets = list(KNOWN_TARGETS.values())
        _result, mocks = _dispatch(targets=all_targets)

        # Collect (target_name, method_name) pairs that were called
        dispatched = set()
        method_map = {
            "prompt_integrator": "integrate_prompts_for_target",
            "agent_integrator": "integrate_agents_for_target",
            "command_integrator": "integrate_commands_for_target",
            "instruction_integrator": "integrate_instructions_for_target",
            "hook_integrator": "integrate_hooks_for_target",
        }
        prim_from_method = {
            "integrate_prompts_for_target": "prompts",
            "integrate_agents_for_target": "agents",
            "integrate_commands_for_target": "commands",
            "integrate_instructions_for_target": "instructions",
            "integrate_hooks_for_target": "hooks",
        }

        for int_name, method_name in method_map.items():
            method = getattr(mocks[int_name], method_name)
            for call_args in method.call_args_list:
                target = call_args[0][0]
                prim = prim_from_method[method_name]
                dispatched.add((target.name, prim))

        # Verify every non-skills primitive in each target was dispatched
        for target in all_targets:
            for prim_name in target.primitives:
                if prim_name == "skills":
                    continue  # skills handled separately
                assert (target.name, prim_name) in dispatched, (
                    f"Expected ({target.name}, {prim_name}) to be dispatched"
                )


# ===================================================================
# 2. TestExhaustivenessChecks
# ===================================================================

class TestExhaustivenessChecks:
    """Structural checks ensuring no target x primitive pair is orphaned."""

    def test_every_target_primitive_has_dispatch_path(self):
        """For each (target, primitive) in KNOWN_TARGETS, verify the dispatch
        loop routes to a real integrator method or a known special case."""
        # The dispatch loop recognizes these primitives via _PRIMITIVE_INTEGRATORS
        dispatched_primitives = {"prompts", "agents", "commands", "instructions"}
        # Plus these special cases handled inline
        special_cases = {"hooks", "skills"}
        all_handled = dispatched_primitives | special_cases

        for target_name, profile in KNOWN_TARGETS.items():
            for prim_name in profile.primitives:
                assert prim_name in all_handled, (
                    f"Primitive '{prim_name}' in target '{target_name}' has no "
                    f"dispatch path. Add it to _PRIMITIVE_INTEGRATORS or handle "
                    f"as a special case."
                )

    def test_partition_parity_with_old_buckets(self):
        """Verify partition_managed_files produces the expected bucket keys
        that callers rely on (backward-compat aliases applied)."""
        # Use an empty set -- we only care about the keys produced
        buckets = BaseIntegrator.partition_managed_files(set())

        # Expected keys from the old hardcoded version:
        expected_keys = {
            "prompts",             # was prompts_copilot, aliased
            "agents_github",       # was agents_copilot, aliased
            "agents_claude",
            "agents_cursor",
            "agents_opencode",
            "commands",            # was commands_claude, aliased
            "commands_opencode",
            "instructions",        # was instructions_copilot, aliased
            "rules_cursor",        # was instructions_cursor, aliased
            "skills",              # cross-target bucket
            "hooks",               # cross-target bucket
        }

        assert expected_keys == set(buckets.keys()), (
            f"Bucket keys mismatch.\n"
            f"  Missing: {expected_keys - set(buckets.keys())}\n"
            f"  Extra:   {set(buckets.keys()) - expected_keys}"
        )


# ===================================================================
# 3. TestSyntheticTargetProfile
# ===================================================================

class TestSyntheticTargetProfile:
    """Verify that a hand-built TargetProfile works end-to-end without
    any code changes -- proving the architecture is truly data-driven."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.root = Path(self.temp_dir)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_synthetic_target_integrates_successfully(self):
        """A synthetic TargetProfile with a custom root_dir (.newcode)
        passes through integrate_commands_for_target without errors."""
        from apm_cli.integration.command_integrator import CommandIntegrator

        synthetic = TargetProfile(
            name="newcode",
            root_dir=".newcode",
            primitives={
                "commands": PrimitiveMapping("cmds", ".md", "newcode_cmd"),
            },
            auto_create=True,
            detect_by_dir=False,
        )

        # CommandIntegrator.find_prompt_files() discovers .prompt.md files
        # in .apm/prompts/ and transforms them to command format.
        pkg_dir = self.root / "packages" / "test-pkg"
        prompts_dir = pkg_dir / ".apm" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "hello.prompt.md").write_text(
            "---\nname: hello\n---\nHello world"
        )

        # Create the target root so integration proceeds
        (self.root / ".newcode").mkdir(parents=True)

        package_info = MagicMock()
        package_info.install_path = pkg_dir
        package_info.resolved_reference = None
        package_info.package = MagicMock()
        package_info.package.name = "test-pkg"

        integrator = CommandIntegrator()
        result = integrator.integrate_commands_for_target(
            synthetic, package_info, self.root,
            force=False, managed_files=set(),
        )

        assert result.files_integrated == 1
        assert len(result.target_paths) == 1
        # Verify the file landed under the synthetic root_dir
        deployed = result.target_paths[0]
        assert ".newcode" in deployed.parts
        assert "cmds" in deployed.parts
        assert deployed.name == "hello.md"

    def test_synthetic_target_sync_computes_correct_prefix(self):
        """sync_for_target uses the synthetic target's root_dir/subdir
        to compute the correct prefix for file removal."""
        from apm_cli.integration.command_integrator import CommandIntegrator

        synthetic = TargetProfile(
            name="newcode",
            root_dir=".newcode",
            primitives={
                "commands": PrimitiveMapping("cmds", ".md", "newcode_cmd"),
            },
            auto_create=True,
            detect_by_dir=False,
        )

        apm_package = MagicMock()
        apm_package.name = "test-pkg"

        integrator = CommandIntegrator()

        # Provide managed files under the synthetic prefix
        managed = {
            ".newcode/cmds/hello.md",
            ".newcode/cmds/goodbye.md",
            ".claude/commands/other.md",  # should NOT be removed
        }

        # Create the files so sync can actually remove them
        cmds_dir = self.root / ".newcode" / "cmds"
        cmds_dir.mkdir(parents=True)
        (cmds_dir / "hello.md").write_text("test")
        (cmds_dir / "goodbye.md").write_text("test")

        claude_dir = self.root / ".claude" / "commands"
        claude_dir.mkdir(parents=True)
        (claude_dir / "other.md").write_text("test")

        # Patch validate_deploy_path to accept .newcode/ prefix (which
        # is not in KNOWN_TARGETS) while keeping all other security checks
        _orig = BaseIntegrator.validate_deploy_path

        def _patched(rel_path, project_root, allowed_prefixes=None):
            extended = (".newcode/",) + (allowed_prefixes or BaseIntegrator._get_integration_prefixes())
            return _orig(rel_path, project_root, allowed_prefixes=extended)

        with patch.object(BaseIntegrator, "validate_deploy_path", staticmethod(_patched)):
            result = integrator.sync_for_target(
                synthetic, apm_package, self.root,
                managed_files=managed,
            )

        # The .newcode files should be removed
        assert result["files_removed"] == 2
        assert not (cmds_dir / "hello.md").exists()
        assert not (cmds_dir / "goodbye.md").exists()
        # The .claude file should still exist (different prefix)
        assert (claude_dir / "other.md").exists()


# ===================================================================
# 4. TestSkillTargetGating  (Issue #482 regression)
# ===================================================================

class TestSkillTargetGating:
    """Verify that the skill integrator respects the targets parameter
    passed from the dispatch loop, preventing cross-target skill writes."""

    def test_skill_integrator_receives_targets_from_dispatch(self):
        """_integrate_package_primitives passes its targets list to
        skill_integrator.integrate_package_skill (Issue #482)."""
        cursor_only = [KNOWN_TARGETS["cursor"]]
        _result, mocks = _dispatch(targets=cursor_only)

        # Verify skill integrator was called with targets= kwarg
        call_kwargs = mocks["skill_integrator"].integrate_package_skill.call_args
        assert call_kwargs is not None, "skill integrator was not called"
        assert "targets" in call_kwargs.kwargs, (
            "targets= not passed to skill integrator"
        )
        passed_targets = call_kwargs.kwargs["targets"]
        assert len(passed_targets) == 1
        assert passed_targets[0].name == "cursor"

    def test_opencode_target_does_not_pass_copilot_to_skills(self):
        """With targets=[opencode], skill integrator only gets opencode."""
        opencode_only = [KNOWN_TARGETS["opencode"]]
        _result, mocks = _dispatch(targets=opencode_only)

        call_kwargs = mocks["skill_integrator"].integrate_package_skill.call_args
        passed_targets = call_kwargs.kwargs["targets"]
        assert all(t.name == "opencode" for t in passed_targets)

    def test_empty_targets_skips_skill_integrator(self):
        """With targets=[], skill integrator is not called at all."""
        _result, mocks = _dispatch(targets=[])
        mocks["skill_integrator"].integrate_package_skill.assert_not_called()


# ===================================================================
# 5. TestPartitionBucketKey
# ===================================================================

class TestPartitionBucketKey:
    """Verify that partition_bucket_key produces the correct aliased keys."""

    def test_copilot_prompts_alias(self):
        assert BaseIntegrator.partition_bucket_key("prompts", "copilot") == "prompts"

    def test_copilot_agents_alias(self):
        assert BaseIntegrator.partition_bucket_key("agents", "copilot") == "agents_github"

    def test_claude_commands_alias(self):
        assert BaseIntegrator.partition_bucket_key("commands", "claude") == "commands"

    def test_cursor_instructions_alias(self):
        assert BaseIntegrator.partition_bucket_key("instructions", "cursor") == "rules_cursor"

    def test_unaliased_key_passthrough(self):
        assert BaseIntegrator.partition_bucket_key("agents", "cursor") == "agents_cursor"

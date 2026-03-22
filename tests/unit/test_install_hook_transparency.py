import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from apm_cli.commands.install import _integrate_package_primitives
from apm_cli.integration.hook_integrator import HookIntegrator
from apm_cli.models.apm_package import APMPackage, PackageInfo


def _empty_result(**overrides):
    payload = {
        "files_integrated": 0,
        "files_updated": 0,
        "links_resolved": 0,
        "target_paths": [],
        "skill_created": False,
        "sub_skills_promoted": 0,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


class _NoopPromptIntegrator:
    def integrate_package_prompts(self, *args, **kwargs):
        return _empty_result()


class _NoopAgentIntegrator:
    def integrate_package_agents(self, *args, **kwargs):
        return _empty_result()

    def integrate_package_agents_claude(self, *args, **kwargs):
        return _empty_result()

    def integrate_package_agents_cursor(self, *args, **kwargs):
        return _empty_result()

    def integrate_package_agents_opencode(self, *args, **kwargs):
        return _empty_result()


class _NoopSkillIntegrator:
    def integrate_package_skill(self, *args, **kwargs):
        return _empty_result()


class _NoopInstructionIntegrator:
    def integrate_package_instructions(self, *args, **kwargs):
        return _empty_result()

    def integrate_package_instructions_cursor(self, *args, **kwargs):
        return _empty_result()


class _NoopCommandIntegrator:
    def integrate_package_commands(self, *args, **kwargs):
        return _empty_result()

    def integrate_package_commands_opencode(self, *args, **kwargs):
        return _empty_result()


def _make_package_info(install_path: Path, name: str = "hookify") -> PackageInfo:
    package = APMPackage(name=name, version="1.0.0")
    return PackageInfo(package=package, install_path=install_path)


def _setup_hook_package(project_root: Path) -> PackageInfo:
    pkg_dir = project_root / "apm_modules" / "anthropics" / "hookify"
    hooks_dir = pkg_dir / "hooks"
    hooks_dir.mkdir(parents=True)

    (hooks_dir / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/pretooluse.py",
                                    "timeout": 10,
                                }
                            ]
                        }
                    ]
                }
            }
        )
    )
    (hooks_dir / "pretooluse.py").write_text("#!/usr/bin/env python3\nprint('ok')\n")
    return _make_package_info(pkg_dir)


def test_install_logs_hook_action_summary(tmp_path):
    package_info = _setup_hook_package(tmp_path)
    logger = MagicMock()
    logger.verbose = False

    _integrate_package_primitives(
        package_info,
        tmp_path,
        integrate_vscode=True,
        integrate_claude=False,
        integrate_opencode=False,
        prompt_integrator=_NoopPromptIntegrator(),
        agent_integrator=_NoopAgentIntegrator(),
        skill_integrator=_NoopSkillIntegrator(),
        instruction_integrator=_NoopInstructionIntegrator(),
        command_integrator=_NoopCommandIntegrator(),
        hook_integrator=HookIntegrator(),
        force=False,
        managed_files=set(),
        diagnostics=None,
        package_name="anthropics/hookify",
        logger=logger,
    )

    tree_lines = [call.args[0] for call in logger.tree_item.call_args_list]
    assert any("1 hook(s) integrated -> .github/hooks/" in line for line in tree_lines)
    assert any(
        "PreToolUse: runs .github/hooks/scripts/hookify/hooks/pretooluse.py (hooks.json)"
        in line
        for line in tree_lines
    )
    logger.verbose_detail.assert_not_called()


def test_install_logs_full_hook_json_in_verbose_mode(tmp_path):
    package_info = _setup_hook_package(tmp_path)
    (tmp_path / ".claude").mkdir()
    logger = MagicMock()
    logger.verbose = True

    _integrate_package_primitives(
        package_info,
        tmp_path,
        integrate_vscode=False,
        integrate_claude=True,
        integrate_opencode=False,
        prompt_integrator=_NoopPromptIntegrator(),
        agent_integrator=_NoopAgentIntegrator(),
        skill_integrator=_NoopSkillIntegrator(),
        instruction_integrator=_NoopInstructionIntegrator(),
        command_integrator=_NoopCommandIntegrator(),
        hook_integrator=HookIntegrator(),
        force=False,
        managed_files=set(),
        diagnostics=None,
        package_name="anthropics/hookify",
        logger=logger,
    )

    verbose_lines = [call.args[0] for call in logger.verbose_detail.call_args_list]
    assert any(
        "Hook JSON (hooks.json -> .claude/settings.json):" in line
        for line in verbose_lines
    )
    assert any(
        '"command": "python3 .claude/hooks/hookify/hooks/pretooluse.py"' in line
        for line in verbose_lines
    )

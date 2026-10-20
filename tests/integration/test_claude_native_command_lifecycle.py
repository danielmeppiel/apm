"""Installed Python CLI contracts with only the external Claude CLI substituted.

These tests prove APM acquisition, selection, deployment and reconciliation.
The substitute models native registration, not command loading or invocation.
Authenticated Claude runtime qualification is a separate acceptance gate.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from apm_cli.utils.yaml_io import load_yaml
from tests.utils.apm_lifecycle_runner import ApmLifecycleRunner, CommandResult
from tests.utils.isolated_apm_environment import IsolatedApmEnvironment
from tests.utils.local_git_repository import LocalGitRepository, LocalGitRepositoryFactory

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

_FIXTURE = Path(__file__).parents[1] / "fixtures" / "native_claude_commands"
_DEPENDENCY = "fixture/native-commands"

# Only this external-host boundary is replaced; all APM decisions run unchanged.
_NATIVE_CLIENT_STUB = r"""
import json
import os
from pathlib import Path
from apm_cli.claude_plugins.client import ClaudePluginCLI


def _native_run(self, *args):
    state_path = Path(os.environ["APM_NATIVE_TEST_STATE"])
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {
        "marketplaces": [], "plugins": [], "calls": []
    }
    args = list(args)
    state["calls"].append(args)
    output = ""
    if args == ["--version"]:
        output = "2.1.291 (Claude Code)"
    elif args == ["plugin", "marketplace", "list", "--json"]:
        output = json.dumps(state["marketplaces"])
    elif args == ["plugin", "list", "--json"]:
        output = json.dumps(state["plugins"])
    elif args[:3] == ["plugin", "marketplace", "add"]:
        assert args[4:] == ["--scope", "user"], "Marketplace must stay user-scoped"
        root = Path(args[3])
        catalog = json.loads((root / ".claude-plugin" / "marketplace.json").read_text())
        state["marketplaces"] = [{
            "name": catalog["name"], "source": "directory",
            "path": str(root), "installLocation": str(root)
        }]
    elif args[:2] in (["plugin", "install"], ["plugin", "update"]):
        assert args[3:] == ["--scope", "user"], "Plugin registration must stay user-scoped"
        name, marketplace = args[2].split("@")
        selected = next(m for m in state["marketplaces"] if m["name"] == marketplace)
        root = Path(selected["path"])
        catalog = json.loads((root / ".claude-plugin" / "marketplace.json").read_text())
        entry = next(p for p in catalog["plugins"] if p["name"] == name)
        source = (root / entry["source"]).resolve()
        manifest = json.loads((source / ".claude-plugin" / "plugin.json").read_text())
        existing = next((p for p in state["plugins"] if p["id"] == args[2]), None)
        enabled = existing["enabled"] if existing else entry.get("defaultEnabled", True)
        state["plugins"] = [p for p in state["plugins"] if p["id"] != args[2]]
        state["plugins"].append({
            "id": args[2], "scope": "user", "enabled": enabled,
            "readFromFolder": str(source), "installPath": str(root / "not-the-live-root"),
            "version": manifest["version"]
        })
    elif args[:2] == ["plugin", "uninstall"]:
        assert args[3:] == ["--scope", "user", "--keep-data"], (
            "Native removal must stay user-scoped and retain user plugin data"
        )
        state["plugins"] = [p for p in state["plugins"] if p["id"] != args[2]]
    else:
        raise AssertionError(f"Unexpected native CLI call: {args!r}")
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return output


ClaudePluginCLI.run = _native_run
"""


@dataclass
class _Scenario:
    """Own isolated Git, APM and external-host protocol state for one lifecycle."""

    isolated: IsolatedApmEnvironment
    runner: ApmLifecycleRunner
    factory: LocalGitRepositoryFactory
    repository: LocalGitRepository
    environment: dict[str, str]
    source: Path
    revision: str

    def run(self, *args: str, expected: int = 0) -> CommandResult:
        """Run the installed Python CLI and keep complete failure evidence."""
        result = self.runner.run(
            args,
            scenario_id="claude-native-command-context",
            cwd=self.isolated.work_root,
            env=self.environment,
        )
        assert result.returncode == expected, (
            f"{result.command!r}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        return result

    def native_state(self) -> dict:
        """Read only the substituted host's externally visible registration state."""
        path = Path(self.environment["APM_NATIVE_TEST_STATE"])
        assert path.is_file(), "APM never reached the external native registration boundary"
        return json.loads(path.read_text(encoding="utf-8"))

    @property
    def modules(self) -> Path:
        """Return the real global APM acquisition root."""
        return self.isolated.config_root / "apm_modules"

    @property
    def claude(self) -> Path:
        """Return the isolated native user config root."""
        return self.isolated.home / ".claude"

    def write_manifest(self, *, revision: str | None = None) -> None:
        """Pin the selected Git-path source without a moving remote reference."""
        document = {
            "name": "native-command-consumer",
            "version": "1.0.0",
            "dependencies": {
                "apm": [
                    {
                        "git": _DEPENDENCY,
                        "ref": revision or self.revision,
                        "path": "plugins/context",
                    }
                ]
            },
        }
        (self.isolated.config_root / "apm.yml").write_text(json.dumps(document), encoding="utf-8")

    def install(self) -> CommandResult:
        """Exercise the ordinary global dependency installation surface."""
        return self.run("install", "-g", "--target", "claude", "--only", "apm")


def _scenario(tmp_path: Path, command: tuple[str, ...], *, empty: bool = False) -> _Scenario:
    """Create a Git-path plugin and stub only the external native CLI transport."""
    isolated = IsolatedApmEnvironment.create(tmp_path / "scenario", base_env=dict(os.environ))
    environment = isolated.subprocess_env()
    environment["CLAUDE_CONFIG_DIR"] = str(isolated.home / ".claude")
    environment["APM_NATIVE_TEST_STATE"] = str(isolated.root / "native-state.json")
    executable_dir = isolated.root / "executables"
    executable_dir.mkdir()
    for name in ("claude", "claude.cmd"):
        executable = executable_dir / name
        executable.write_text("exit 91\n", encoding="ascii")
        executable.chmod(0o755)
    environment["PATH"] = str(executable_dir) + os.pathsep + environment["PATH"]
    guard = isolated.root / "network_guard" / "sitecustomize.py"
    guard.write_text(guard.read_text(encoding="utf-8") + _NATIVE_CLIENT_STUB, encoding="utf-8")
    factory = LocalGitRepositoryFactory(isolated.repository_root, env=environment)
    repository = factory.create("commands")
    source = repository.worktree / "plugins" / "context"
    shutil.copytree(_FIXTURE, source)
    if empty:
        manifest = source / ".claude-plugin" / "plugin.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["commands"] = []
        manifest.write_text(json.dumps(data), encoding="utf-8")
    revision = factory.commit(repository, message="Own native command fixture").sha
    environment = factory.url_rewrite_subprocess_env(
        repository, f"https://github.com/{_DEPENDENCY}.git"
    )
    scenario = _Scenario(
        isolated,
        ApmLifecycleRunner(command),
        factory,
        repository,
        environment,
        source,
        revision,
    )
    scenario.write_manifest()
    return scenario


def _assert_intact_native_source(
    scenario: _Scenario, revision: str, *, empty: bool, enabled: bool = False
) -> Path:
    """Bind the native registration to acquired source bytes and immutable identity."""
    state = scenario.native_state()
    assert len(state["plugins"]) == 1
    plugin = state["plugins"][0]
    assert plugin["id"] == "apm-command-context@apm-claude"
    assert plugin["scope"] == "user"
    assert plugin["enabled"] is enabled
    source = Path(plugin["readFromFolder"])
    assert source.is_relative_to(scenario.modules)
    assert source != Path(plugin["installPath"])
    for path in scenario.source.rglob("*"):
        if path.is_file():
            assert (source / path.relative_to(scenario.source)).read_bytes() == path.read_bytes()
    manifest = json.loads((source / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["commands"] == ([] if empty else ["./selected/status.md"])
    assert not (scenario.claude / "commands" / "status.md").exists()
    assert not (scenario.claude / "commands" / "unselected.md").exists()
    assert not (scenario.claude / "hooks").exists()
    lock = load_yaml(scenario.isolated.config_root / "apm.lock.yaml")
    assert len(lock["dependencies"]) == 1
    dependency = lock["dependencies"][0]
    assert dependency["repo_url"] == _DEPENDENCY
    assert dependency["virtual_path"] == "plugins/context"
    assert dependency["resolved_commit"] == revision
    return source


@pytest.mark.parametrize("empty", [False, True], ids=["selected-command", "explicit-empty"])
@pytest.mark.parametrize("enabled", [False, True], ids=["user-disabled", "user-enabled"])
def test_global_git_path_command_install_reinstall_and_empty_selection(
    tmp_path: Path, apm_engine_command: tuple[str, ...], empty: bool, enabled: bool
) -> None:
    """Normal and frozen reinstall retain user activation and an intact native unit."""
    scenario = _scenario(tmp_path, apm_engine_command, empty=empty)
    user_command = scenario.claude / "commands" / "personal.md"
    user_command.parent.mkdir(parents=True)
    user_command.write_bytes(b"# User-owned command\n")

    scenario.install()
    source = _assert_intact_native_source(scenario, scenario.revision, empty=empty)
    first_lock = (scenario.isolated.config_root / "apm.lock.yaml").read_bytes()
    first_manifest = (source / ".claude-plugin" / "plugin.json").read_bytes()
    state = scenario.native_state()
    state["plugins"][0]["enabled"] = enabled
    Path(scenario.environment["APM_NATIVE_TEST_STATE"]).write_text(
        json.dumps(state), encoding="utf-8"
    )
    scenario.install()
    assert (
        _assert_intact_native_source(scenario, scenario.revision, empty=empty, enabled=enabled)
        == source
    )
    scenario.run("install", "-g", "--target", "claude", "--only", "apm", "--frozen")

    assert (
        _assert_intact_native_source(scenario, scenario.revision, empty=empty, enabled=enabled)
        == source
    )
    assert (scenario.isolated.config_root / "apm.lock.yaml").read_bytes() == first_lock
    assert (source / ".claude-plugin" / "plugin.json").read_bytes() == first_manifest
    assert user_command.read_bytes() == b"# User-owned command\n"
    assert sorted(path.name for path in user_command.parent.iterdir()) == ["personal.md"]
    registration_calls = [
        call
        for call in scenario.native_state()["calls"]
        if call[:2] in (["plugin", "install"], ["plugin", "update"])
    ]
    assert registration_calls == [
        ["plugin", operation, "apm-command-context@apm-claude", "--scope", "user"]
        for operation in ("install", "update", "update")
    ]
    assert not any(
        call[:2] in (["plugin", "enable"], ["plugin", "disable"])
        for call in scenario.native_state()["calls"]
    )


@pytest.mark.parametrize("enabled", [False, True], ids=["user-disabled", "user-enabled"])
def test_global_git_path_command_update_and_owned_removal(
    tmp_path: Path, apm_engine_command: tuple[str, ...], enabled: bool
) -> None:
    """Ref replacement updates live resources and uninstall retains user command/data."""
    scenario = _scenario(tmp_path, apm_engine_command)
    scenario.install()
    _assert_intact_native_source(scenario, scenario.revision, empty=False)
    state = scenario.native_state()
    state["plugins"][0]["enabled"] = enabled
    Path(scenario.environment["APM_NATIVE_TEST_STATE"]).write_text(
        json.dumps(state), encoding="utf-8"
    )
    user_command = scenario.claude / "commands" / "personal.md"
    user_command.parent.mkdir(parents=True, exist_ok=True)
    user_command.write_bytes(b"# User-owned command\n")
    user_data = scenario.claude / "plugins" / "data" / "apm-command-context"
    user_data.mkdir(parents=True)
    (user_data / "notes.txt").write_bytes(b"USER_DATA\n")
    resource = scenario.source / "resources" / "identity.txt"
    resource.write_bytes(b"APM_NATIVE_COMMAND_UPDATED_RESOURCE\n")
    revision = scenario.factory.commit(
        scenario.repository, message="Advance owned command resource"
    ).sha
    scenario.write_manifest(revision=revision)

    scenario.install()

    source = _assert_intact_native_source(scenario, revision, empty=False, enabled=enabled)
    assert (source / "resources" / "identity.txt").read_bytes() == resource.read_bytes()
    scenario.run("uninstall", "-g", f"{_DEPENDENCY}/plugins/context")
    assert scenario.native_state()["plugins"] == []
    assert not source.exists()
    assert not (scenario.isolated.config_root / "apm.lock.yaml").exists()
    assert user_command.read_bytes() == b"# User-owned command\n"
    assert (user_data / "notes.txt").read_bytes() == b"USER_DATA\n"
    assert not (scenario.claude / "commands" / "status.md").exists()

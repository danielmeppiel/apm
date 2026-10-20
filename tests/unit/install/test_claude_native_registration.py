"""Native metadata lifecycle crosses only the external Claude command seam."""

import json
import os
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from apm_cli.claude_plugins.admission import ClaudeNativePlugin, ClaudeNativePluginError
from apm_cli.claude_plugins.client import ClaudePluginCLI
from apm_cli.claude_plugins.registrar import (
    CATALOG_RELATIVE,
    LEDGER_RELATIVE,
    MARKETPLACE_NAME,
    resync_claude_plugins,
    synchronize_claude_plugins,
)
from apm_cli.core.scope import InstallScope

pytestmark = pytest.mark.component


def test_native_child_environment_restores_libraries_and_omits_platform_tokens(
    monkeypatch,
) -> None:
    """Reuse canonical subprocess and token owners without changing parent/native auth."""
    monkeypatch.setattr("shutil.which", lambda name: "/native/claude")
    monkeypatch.setattr("sys.frozen", True, raising=False)
    supplied = {
        "GH_TOKEN": "sentinel-gh",
        "GITHUB_APM_PAT_ORG": "sentinel-scoped",
        "APM_REGISTRY_TOKEN_PRIVATE": "sentinel-registry",
        "LD_LIBRARY_PATH": "/bundle",
        "LD_LIBRARY_PATH_ORIG": "/user",
        "CLAUDE_CONFIG_DIR": "/owned-claude",
        "ANTHROPIC_API_KEY": "sentinel-native",
    }
    for key, value in supplied.items():
        monkeypatch.setenv(key, value)
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout="2.1.291 (Claude Code)"))
    monkeypatch.setattr(subprocess, "run", run)
    assert ClaudePluginCLI().run("--version") == "2.1.291 (Claude Code)"
    env = run.call_args.kwargs["env"]
    assert not {"GH_TOKEN", "GITHUB_APM_PAT_ORG", "APM_REGISTRY_TOKEN_PRIVATE"} & env.keys()
    assert env["LD_LIBRARY_PATH"] == "/user"
    assert "LD_LIBRARY_PATH_ORIG" not in env
    assert env["CLAUDE_CONFIG_DIR"] == "/owned-claude"
    assert env["ANTHROPIC_API_KEY"] == "sentinel-native"
    assert all(os.environ[key] == value for key, value in supplied.items())


def test_native_transport_failure_keeps_targets_without_echoing_native_stderr(monkeypatch) -> None:
    """Do not leak captured output or prescribe a target-dropping install retry."""
    monkeypatch.setattr("shutil.which", lambda name: "/native/claude")
    monkeypatch.setattr(
        subprocess,
        "run",
        Mock(
            return_value=SimpleNamespace(returncode=1, stdout="private-out", stderr="private-err")
        ),
    )
    with pytest.raises(ClaudeNativePluginError, match="original target selection") as error:
        ClaudePluginCLI().run("--version")
    assert "private" not in str(error.value)


@pytest.fixture
def native(monkeypatch, tmp_path):
    state = {"plugins": {}, "marketplaces": [], "calls": [], "fail": False}
    monkeypatch.setattr(ClaudePluginCLI, "__init__", lambda self: None)

    def run(self, *args):
        state["calls"].append(args)
        if args == ("--version",):
            return "2.1.291 (Claude Code)"
        if args == ("plugin", "marketplace", "list", "--json"):
            return json.dumps(state["marketplaces"])
        if args == ("plugin", "list", "--json"):
            return json.dumps(list(state["plugins"].values()))
        if args[:3] == ("plugin", "marketplace", "add"):
            state["marketplaces"] = [
                {
                    "name": MARKETPLACE_NAME,
                    "source": "directory",
                    "path": args[3],
                    "installLocation": args[3],
                }
            ]
            return ""
        plugin_id = args[2]
        if args[1] == "uninstall":
            assert args[-1] == "--keep-data"
            state["plugins"].pop(plugin_id)
            return ""
        assert args[1] in {"install", "update"}
        catalog = json.loads((tmp_path / CATALOG_RELATIVE).read_text())
        entry = next(item for item in catalog["plugins"] if item["name"] == plugin_id.split("@")[0])
        assert entry["defaultEnabled"] is False
        previous = state["plugins"].get(plugin_id)
        state["plugins"][plugin_id] = {
            "id": plugin_id,
            "scope": "user",
            "enabled": previous["enabled"] if previous else False,
            "readFromFolder": str((tmp_path / entry["source"]).resolve()),
            "installPath": "/not/the/effective/root",
        }
        if state["fail"]:
            raise ClaudeNativePluginError("interrupted after native install")
        return ""

    monkeypatch.setattr(ClaudePluginCLI, "run", run)
    return state


def _sync(root, names, **kwargs):
    plans = []
    for name in names:
        source = root / name
        source.mkdir(exist_ok=True)
        plans.append(ClaudeNativePlugin("owner/" + name, name, source))
    synchronize_claude_plugins(
        modules_dir=root,
        scope=InstallScope.USER,
        plugins=plans,
        **kwargs,
    )


def test_install_update_remove_preserves_native_activation(tmp_path, native):
    _sync(tmp_path, ["alpha", "beta"])
    assert all(not row["enabled"] for row in native["plugins"].values())
    alpha_id = "alpha@" + MARKETPLACE_NAME
    beta_id = "beta@" + MARKETPLACE_NAME
    native["plugins"][alpha_id]["enabled"] = True
    _sync(tmp_path, ["alpha", "beta"])
    assert native["plugins"][alpha_id]["enabled"] is True
    assert native["plugins"][beta_id]["enabled"] is False
    _sync(tmp_path, ["beta"])
    assert set(native["plugins"]) == {beta_id}
    _sync(tmp_path, [])
    assert native["plugins"] == {}
    assert json.loads((tmp_path / LEDGER_RELATIVE).read_text())["plugins"] == {}
    assert all("enable" not in call and "disable" not in call for call in native["calls"])


def test_interrupted_native_install_recovers_from_intent(tmp_path, native):
    native["fail"] = True
    with pytest.raises(ClaudeNativePluginError, match="interrupted"):
        _sync(tmp_path, ["alpha"])
    assert (
        "alpha@" + MARKETPLACE_NAME
        in json.loads((tmp_path / LEDGER_RELATIVE).read_text())["plugins"]
    )
    native["fail"] = False
    _sync(tmp_path, ["alpha"])
    assert native["plugins"]["alpha@" + MARKETPLACE_NAME]["enabled"] is False


def test_foreign_marketplace_cannot_be_adopted(tmp_path, native):
    native["marketplaces"] = [
        {
            "name": MARKETPLACE_NAME,
            "source": "directory",
            "path": str(tmp_path),
        }
    ]
    with pytest.raises(ClaudeNativePluginError, match="another source"):
        _sync(tmp_path, ["alpha"])
    assert not (tmp_path / LEDGER_RELATIVE).exists()
    assert all(call[1:3] != ("marketplace", "add") for call in native["calls"])


def test_changed_native_root_refused_before_any_write(tmp_path, native):
    _sync(tmp_path, ["alpha"])
    ledger = (tmp_path / LEDGER_RELATIVE).read_bytes()
    native["plugins"]["alpha@" + MARKETPLACE_NAME]["readFromFolder"] = "/foreign"
    native["calls"].clear()
    with pytest.raises(ClaudeNativePluginError, match="ownership changed"):
        _sync(tmp_path, ["alpha"])
    assert (tmp_path / LEDGER_RELATIVE).read_bytes() == ledger
    assert len(native["calls"]) == 3


def test_name_collision_refused(tmp_path, native):
    _sync(tmp_path, ["alpha"])
    with pytest.raises(ClaudeNativePluginError, match="name collision"):
        synchronize_claude_plugins(
            modules_dir=tmp_path,
            scope=InstallScope.USER,
            plugins=[ClaudeNativePlugin("another/identity", "alpha", tmp_path / "alpha")],
        )


def test_dry_run_has_no_cli_or_file_effects(tmp_path, native):
    _sync(tmp_path, ["alpha"], dry_run=True)
    assert native["calls"] == []
    assert not (tmp_path / LEDGER_RELATIVE).exists()


def test_unsupported_client_has_no_writes(tmp_path, native, monkeypatch):
    monkeypatch.setattr(ClaudePluginCLI, "run", lambda *args: "2.1.126 (Claude Code)")
    with pytest.raises(ClaudeNativePluginError, match="qualified only"):
        _sync(tmp_path, ["alpha"])
    assert not (tmp_path / LEDGER_RELATIVE).exists()


@pytest.mark.parametrize(
    "args",
    [
        ("-p", "hello"),
        ("plugin", "enable", "alpha"),
        ("auth", "login"),
    ],
)
def test_client_cannot_activate_or_run_plugins(args, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/native/claude")
    with pytest.raises(ClaudeNativePluginError, match="non-metadata"):
        ClaudePluginCLI().run(*args)


def test_missing_lock_cannot_remove_owned_native_plugins(tmp_path, native):
    _sync(tmp_path, ["alpha"])
    native["calls"].clear()
    with pytest.raises(ClaudeNativePluginError, match="canonical lockfile"):
        resync_claude_plugins(modules_dir=tmp_path, scope=InstallScope.USER, lockfile=None)
    assert native["calls"] == []
    assert set(native["plugins"]) == {"alpha@" + MARKETPLACE_NAME}


def test_prepared_plugin_missing_from_lock_cannot_report_success(tmp_path, native):
    from apm_cli.deps.lockfile import LockFile

    plan = ClaudeNativePlugin("owner/alpha", "alpha", tmp_path / "alpha")
    with pytest.raises(ClaudeNativePluginError, match="authorized locked set"):
        resync_claude_plugins(
            modules_dir=tmp_path,
            scope=InstallScope.USER,
            lockfile=LockFile(),
            prepared={plan.dependency_key: plan},
        )
    assert native["calls"] == []

"""Hermetic ownership contracts; simulated responses are not native qualification."""

import json
import shutil
from pathlib import Path
from unittest.mock import Mock

import pytest

from apm_cli.codex_plugins.admission import CodexNativeDeployment, CodexNativePlugin
from apm_cli.codex_plugins.client import CodexNativeClient, CodexNativeError, NativeUserConfig
from apm_cli.codex_plugins.registrar import (
    _preflight,
    marketplace_name,
    synchronize_codex_plugins,
)
from apm_cli.core.scope import InstallScope
from apm_cli.install.deployable_source_plan import DeployableSourcePlan
from apm_cli.utils.content_hash import compute_package_hash

pytestmark = pytest.mark.component


def _deployment(root: Path) -> CodexNativeDeployment:
    source = root / "source"
    (source / ".codex-plugin").mkdir(parents=True)
    (source / ".codex-plugin/plugin.json").write_text(json.dumps({"name": "example"}))
    skill = source / "skills/example/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: example\ndescription: fixture\n---\ninert\n")
    plan = DeployableSourcePlan(
        source.resolve(),
        frozenset({".codex-plugin/plugin.json", "skills/example/SKILL.md"}),
    )
    return CodexNativeDeployment(
        CodexNativePlugin(
            "owner/example", "example", source.resolve(), compute_package_hash(source)
        ),
        plan,
        compute_package_hash(source),
    )


def test_foreign_marketplace_collision_fails_before_native_or_snapshot_write(tmp_path, monkeypatch):
    deployment = _deployment(tmp_path)
    modules = tmp_path / "apm_modules"
    marketplace = marketplace_name(modules, deployment.plugin.dependency_key)
    client = Mock(spec=CodexNativeClient)
    rpc = Mock()
    client.connect.return_value.__enter__ = Mock(return_value=rpc)
    client.connect.return_value.__exit__ = Mock(return_value=False)
    client.read_config.return_value = NativeUserConfig(
        tmp_path / "native/config.toml",
        "version",
        {"marketplaces": {marketplace: {"source_type": "local", "source": "/foreign"}}},
    )
    monkeypatch.setattr(CodexNativeClient, "for_scope", Mock(return_value=client))
    with pytest.raises(CodexNativeError, match="ownership"):
        synchronize_codex_plugins(
            [deployment],
            modules_dir=modules,
            cwd=tmp_path,
            scope=InstallScope.USER,
            retained_keys={"owner/example"},
        )
    client.write_config.assert_not_called()
    client.upgrade.assert_not_called()
    assert not list(tmp_path.glob(".codex-native/snapshots/*"))


def test_no_native_work_does_not_probe_user_configuration(tmp_path, monkeypatch):
    factory = Mock(side_effect=AssertionError("must not probe"))
    monkeypatch.setattr(CodexNativeClient, "for_scope", factory)
    assert (
        synchronize_codex_plugins(
            [],
            modules_dir=tmp_path / "apm_modules",
            cwd=tmp_path,
            scope=InstallScope.PROJECT,
            retained_keys=set(),
        )
        == ()
    )
    factory.assert_not_called()


def test_foreign_plugin_in_owned_namespace_blocks_removal(tmp_path):
    """Removing an owned marketplace must not discard another native entry."""
    config = NativeUserConfig(
        tmp_path / "config.toml",
        "version",
        {"plugins": {"other@apm-owned": {"enabled": False}}},
    )
    with pytest.raises(CodexNativeError, match="ownership"):
        _preflight(config, "apm-owned", "example", None, removing=True)


def test_pending_refresh_retries_without_replacing_native_disable(tmp_path, monkeypatch):
    """A native failure after CAS leaves retryable ownership, not a fresh/adopted entry."""
    deployment = _deployment(tmp_path)
    modules = tmp_path / "apm_modules"
    marketplace = marketplace_name(modules, deployment.plugin.dependency_key)
    ledger = tmp_path / ".codex-native/ownership.json"
    values = {"plugins": {"foreign@external": {"enabled": False}}}
    client = Mock(spec=CodexNativeClient)
    client.connect.return_value.__enter__ = Mock(return_value=Mock())
    client.connect.return_value.__exit__ = Mock(return_value=False)
    client.read_config.side_effect = lambda rpc: NativeUserConfig(
        tmp_path / "config.toml",
        "version",
        values,
    )

    def write_config(rpc, edits, version):
        for edit in edits:
            table, key = edit["keyPath"].split(".", 1)
            values.setdefault(table, {})[json.loads(key)] = edit["value"]

    client.write_config.side_effect = write_config
    client.upgrade.side_effect = CodexNativeError("injected native refresh failure")
    monkeypatch.setattr(CodexNativeClient, "for_scope", Mock(return_value=client))
    options = {
        "modules_dir": modules,
        "cwd": tmp_path,
        "scope": InstallScope.USER,
        "retained_keys": {deployment.plugin.dependency_key},
    }
    with pytest.raises(CodexNativeError, match="injected"):
        synchronize_codex_plugins([deployment], **options)
    pending = json.loads(ledger.read_text())["plugins"][deployment.plugin.dependency_key]
    assert pending["pending"] is True
    assert values["plugins"][f"example@{marketplace}"] == {"enabled": False}
    snapshot = pending["snapshot"]
    installed = tmp_path / "native-installed"
    shutil.copytree(Path(snapshot["path"]) / "plugins/example", installed)
    native_market = tmp_path / "native-marketplace"
    manifest = native_market / ".agents/plugins/marketplace.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}")
    client.upgrade.side_effect = None
    client.upgrade.return_value = [native_market]
    client.read_plugin.return_value = {
        "summary": {
            "id": f"example@{marketplace}",
            "installed": True,
            "source": {
                "type": "git",
                "url": Path(snapshot["path"]).as_uri(),
                "sha": snapshot["content_commit"],
            },
        },
        "mcpServers": [],
        "skills": [{"path": str(installed / "skills/example/SKILL.md")}],
    }
    assert synchronize_codex_plugins([deployment], **options) == (deployment.plugin.dependency_key,)
    settled = json.loads(ledger.read_text())["plugins"][deployment.plugin.dependency_key]
    assert settled["pending"] is False
    assert settled["snapshot"] == snapshot
    assert values["plugins"]["foreign@external"] == {"enabled": False}
    assert values["plugins"][f"example@{marketplace}"] == {"enabled": False}
    client.write_config.assert_called_once()
    stable = ledger.read_bytes()
    assert synchronize_codex_plugins([deployment], **options) == ()
    assert ledger.read_bytes() == stable

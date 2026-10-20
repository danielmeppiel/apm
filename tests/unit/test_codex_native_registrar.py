"""Hermetic ownership contracts; simulated responses are not native qualification."""

import json
import shutil
from pathlib import Path
from unittest.mock import Mock

import pytest

from apm_cli.codex_plugins.admission import CodexNativeDeployment, CodexNativePlugin
from apm_cli.codex_plugins.client import CodexNativeClient, CodexNativeError, NativeUserConfig
from apm_cli.codex_plugins.registrar import (
    _observed_root,
    _preflight,
    _Record,
    marketplace_name,
    synchronize_codex_plugins,
)
from apm_cli.codex_plugins.snapshot import NativeSnapshot
from apm_cli.core.scope import InstallScope
from apm_cli.install.deployable_source_plan import DeployableSourcePlan
from apm_cli.utils.content_hash import compute_native_bundle_hash

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
            "owner/example", "example", source.resolve(), compute_native_bundle_hash(source)
        ),
        plan,
        compute_native_bundle_hash(source),
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


@pytest.mark.parametrize(
    "fault, diagnostic",
    [
        ("source-pin", "owned source pin"),
        ("mcp-names", "every declared MCP server"),
        ("missing-skills", "installed skill paths"),
        ("symlink", "symlink"),
        ("ambiguous-roots", "unambiguous"),
        ("source-root", "source content"),
        ("content-hash", "incomplete or changed"),
    ],
)
def test_observed_root_refuses_invalid_native_evidence(
    tmp_path: Path, fault: str, diagnostic: str
) -> None:
    """Native readback cannot certify a foreign or incomplete installed bundle."""
    deployment = _deployment(tmp_path)
    installed = tmp_path / "installed"
    shutil.copytree(deployment.plugin.source_root, installed)
    snapshot = NativeSnapshot(tmp_path / "transport", "a" * 40, "b" * 40)
    record = _Record("example", deployment.source_hash, snapshot, tmp_path / "config.toml")
    detail = {
        "summary": {
            "id": "example@apm-owned",
            "installed": True,
            "source": {
                "type": "git",
                "url": snapshot.path.as_uri(),
                "sha": snapshot.content_commit,
            },
        },
        "mcpServers": [],
        "skills": [{"path": str(installed / "skills/example/SKILL.md")}],
    }
    assert _observed_root(detail, deployment, record, "apm-owned") == installed
    if fault == "source-pin":
        detail["summary"]["source"]["sha"] = "c" * 40
    elif fault == "mcp-names":
        detail["mcpServers"] = ["undeclared"]
    elif fault == "missing-skills":
        del detail["skills"]
    elif fault == "symlink":
        link = tmp_path / "linked-install"
        link.symlink_to(installed, target_is_directory=True)
        detail["skills"] = [{"path": str(link / "skills/example/SKILL.md")}]
    elif fault == "ambiguous-roots":
        other = tmp_path / "other-install"
        shutil.copytree(installed, other)
        detail["skills"].append({"path": str(other / "skills/example/SKILL.md")})
    elif fault == "source-root":
        detail["skills"] = [
            {"path": str(deployment.plugin.source_root / "skills/example/SKILL.md")}
        ]
    else:
        (installed / "skills/example/SKILL.md").write_text("changed native content")
    with pytest.raises(CodexNativeError, match=diagnostic):
        _observed_root(detail, deployment, record, "apm-owned")


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

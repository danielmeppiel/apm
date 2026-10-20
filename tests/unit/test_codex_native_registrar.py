"""Hermetic ownership contracts; simulated responses are not native qualification."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from apm_cli.codex_plugins.admission import CodexNativeDeployment, CodexNativePlugin
from apm_cli.codex_plugins.client import CodexNativeClient, CodexNativeError, NativeUserConfig
from apm_cli.codex_plugins.registrar import marketplace_name, synchronize_codex_plugins
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
        CodexNativePlugin("owner/example", "example", source.resolve()),
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

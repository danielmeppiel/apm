"""Codex admission consumes canonical format, target, and executable decisions."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from apm_cli.codex_plugins.admission import plan_native_codex_plugin
from apm_cli.codex_plugins.client import CodexNativeError
from apm_cli.codex_plugins.manifest import CodexCompatibilityPlugin
from apm_cli.core.scope import InstallScope

pytestmark = pytest.mark.component


def _admit(root: Path, **overrides):
    package = SimpleNamespace(codex_plugin=CodexCompatibilityPlugin("example", "1", True, False))
    info = SimpleNamespace(package=package, install_path=root)
    options = {
        "scope": InstallScope.USER,
        "skill_subset": None,
        "approvals": {"mcp": True, "hooks": False, "bin": False, "canvas": False, "lsp": False},
        "ctx": None,
    }
    options.update(overrides)
    return plan_native_codex_plugin(
        info, "owner/example", [SimpleNamespace(name="codex")], **options
    )


def test_native_admission_never_silently_reduces_unapproved_mcp(tmp_path):
    with pytest.raises(CodexNativeError, match="allowExecutables"):
        _admit(tmp_path, approvals={})


def test_native_admission_requires_whole_bundle_and_user_scope(tmp_path):
    with pytest.raises(CodexNativeError, match="complete"):
        _admit(tmp_path, skill_subset=("example",))
    with pytest.raises(CodexNativeError, match="user scope"):
        _admit(tmp_path, scope=InstallScope.PROJECT)


def test_native_admission_gates_hidden_native_root_executables(tmp_path):
    (tmp_path / "hooks").mkdir()
    with pytest.raises(CodexNativeError, match="allowExecutables"):
        _admit(tmp_path)


def test_native_admission_keeps_canonical_identity(tmp_path):
    plan = _admit(tmp_path)
    assert plan.dependency_key == "owner/example"
    assert plan.source_root == tmp_path.resolve()
    assert plan.name == "example"
    assert plan.target_name == "codex"
    assert _admit(tmp_path, skill_subset=()) == plan


def test_read_only_projection_does_not_qualify_or_start_native_client(tmp_path, monkeypatch):
    from apm_cli.codex_plugins.client import CodexNativeClient

    def forbidden(*args):
        raise AssertionError("read-only replay must not qualify or launch a native runtime")

    monkeypatch.setattr(CodexNativeClient, "require_scope", forbidden)
    monkeypatch.setattr(CodexNativeClient, "connect", forbidden)
    assert _admit(tmp_path, read_only=True, scope=None).name == "example"


def test_non_codex_package_has_no_native_admission(tmp_path):
    info = SimpleNamespace(package=SimpleNamespace(), install_path=tmp_path)
    assert (
        plan_native_codex_plugin(
            info,
            "owner/example",
            [],
            scope=InstallScope.PROJECT,
            skill_subset=None,
            approvals={},
            ctx=None,
        )
        is None
    )

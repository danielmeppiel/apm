"""Cross-platform lifetime and recorded-only native-service eligibility."""

from pathlib import Path

import pytest

from apm_cli.deps.lockfile import LockFile
from apm_cli.install.errors import FrozenInstallError
from apm_cli.install.service import InstallService
from apm_cli.integration.mcp_config_view import CurrentMcpConfigView, McpSourceProblem

pytestmark = pytest.mark.component


@pytest.mark.windows_compat
@pytest.mark.parametrize("fail", [False, True], ids=["success", "failure"])
def test_command_suppression_preserves_exact_bytes_and_restores_writer(
    tmp_path: Path, fail: bool
) -> None:
    lock = tmp_path / "space root" / "apm.lock.yaml"
    lock.parent.mkdir()
    original = b"# retained\r\nlockfile_version: '1'\r\ngenerated_at: '2020-01-01'\r\n"
    lock.write_bytes(original)

    def execute() -> None:
        with InstallService.frozen_writes(True) as writes:
            LockFile(mcp_servers=["late-service"]).write(lock)
            assert writes and "late-service" in writes[0]
            if fail:
                raise ValueError("native integration failed")

    if fail:
        with pytest.raises(ValueError, match="native integration failed"):
            execute()
    else:
        execute()
    assert lock.read_bytes() == original
    with InstallService.frozen_writes(False):
        LockFile(mcp_servers=["ordinary-install"]).write(lock)
    restored = LockFile.read(lock)
    assert restored is not None and restored.mcp_servers == ["ordinary-install"]


@pytest.mark.parametrize("legacy", [False, True], ids=["explicit-empty", "legacy-absent"])
def test_native_guard_does_not_adopt_unrecorded_native_ownership(legacy: bool) -> None:
    lock = LockFile(mcp_servers=["managed"], mcp_target_servers={})
    lock._mcp_target_servers_present = not legacy
    with pytest.raises(FrozenInstallError, match="cannot replay") as failure:
        InstallService.enforce_frozen_services(
            lock,
            mcp_servers={"managed"},
            mcp_targets=["intellij"],
            lsp_servers=set(),
            lsp_targets=[],
            current_mcp=None,
            user_scope=False,
        )
    assert failure.value.reasons == [
        "  - MCP server 'managed' target 'intellij' ownership is not recorded in apm.lock.yaml"
    ]
    assert lock.mcp_target_servers == {}


def test_native_guard_requires_actual_source_evidence_even_without_claims() -> None:
    with pytest.raises(FrozenInstallError, match="cannot replay") as failure:
        InstallService.enforce_frozen_services(
            LockFile(),
            mcp_servers=set(),
            mcp_targets=[],
            lsp_servers=set(),
            lsp_targets=[],
            current_mcp=CurrentMcpConfigView(
                dependencies=(),
                configs={},
                provenance={},
                problems=(McpSourceProblem("package", Path("apm.yml"), "source unavailable"),),
            ),
            user_scope=False,
        )
    assert failure.value.reasons == ["  - package: source unavailable"]


@pytest.mark.windows_compat
def test_native_ownership_diagnostic_escapes_non_ascii_server_names() -> None:
    with pytest.raises(FrozenInstallError, match="cannot replay") as failure:
        InstallService.enforce_frozen_services(
            LockFile(),
            mcp_servers={"snowman-\u2603"},
            mcp_targets=["intellij"],
            lsp_servers=set(),
            lsp_targets=[],
            current_mcp=None,
            user_scope=False,
        )
    assert failure.value.reasons == [
        "  - MCP server 'snowman-\\u2603' target 'intellij' "
        "ownership is not recorded in apm.lock.yaml"
    ]

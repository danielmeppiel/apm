"""Regression traps for interrupted resolution and denied recovery operations."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from filelock import FileLock, Timeout

from apm_cli.install.resolution_staging import ResolutionStagingSession
from apm_cli.install.transaction import InstallTransaction

pytestmark = [pytest.mark.component, pytest.mark.windows_compat]


def test_cleanup_denial_preserves_original_failure_and_restores_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second filesystem failure must not replace the failed install's cause."""
    manifest = tmp_path / "apm.yml"
    original = b"name: original\r\nversion: 1.0.0\r\n"
    manifest.write_bytes(original)
    logger = MagicMock()
    transaction = InstallTransaction(
        manifest_path=manifest,
        apm_modules_dir=tmp_path / "apm_modules",
        validation=None,
        logger=logger,
        acquire_lock=False,
    )
    candidate = transaction.resolution.prepare_replacement(
        tmp_path / "apm_modules" / "owner" / "package"
    )
    candidate.mkdir()
    (candidate / "partial").write_bytes(b"downloaded candidate")
    manifest.write_bytes(b"name: modified\n")

    def denied_cleanup() -> None:
        raise PermissionError("cleanup obstruction")

    monkeypatch.setattr(transaction.resolution, "_remove_staging_root", denied_cleanup)
    with pytest.raises(RuntimeError, match="original activation obstruction"):
        with transaction:
            raise RuntimeError("original activation obstruction")

    assert manifest.read_bytes() == original
    assert (candidate / "partial").read_bytes() == b"downloaded candidate"
    diagnostics = " ".join(str(call) for call in logger.method_calls)
    assert "cleanup obstruction" in diagnostics
    assert str(candidate.parent.parent) in diagnostics


def test_failed_immediate_restore_keeps_both_errors_and_prior_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Native denials are supplemented here by exact operation fault injection."""
    staging = ResolutionStagingSession(tmp_path / "apm_modules")
    live = tmp_path / "apm_modules" / "owner" / "package"
    live.mkdir(parents=True)
    (live / "marker").write_bytes(b"prior install")
    candidate = staging.prepare_replacement(live)
    candidate.mkdir()
    (candidate / "marker").write_bytes(b"candidate")
    replace = Path.replace

    def deny_activation_and_restore(path: Path, target: Path) -> Path:
        if path == candidate:
            raise PermissionError("activation obstruction")
        if path.parent.name == "backups":
            raise PermissionError("restoration obstruction")
        return replace(path, target)

    monkeypatch.setattr(Path, "replace", deny_activation_and_restore)
    with pytest.raises(OSError) as caught:
        staging.publish_replacement(candidate)

    message = str(caught.value)
    assert "activation obstruction" in message
    assert "restoration obstruction" in message
    backups = list(staging._staging_root.glob("backups/*/marker"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == b"prior install"
    monkeypatch.setattr(Path, "replace", replace)
    staging.rollback()
    assert (live / "marker").read_bytes() == b"prior install"


def test_prepared_replacement_holds_activity_lock_until_rollback(tmp_path: Path) -> None:
    """A candidate in use is not a lockless legacy root or abandoned backup."""
    staging = ResolutionStagingSession(tmp_path / "apm_modules")
    candidate = staging.prepare_replacement(tmp_path / "apm_modules" / "owner" / "package")
    candidate.mkdir()
    (candidate / "marker").write_bytes(b"active candidate")
    try:
        with pytest.raises(Timeout):
            with FileLock(str(staging._staging_lock_path)).acquire(timeout=0):
                pass
        other = ResolutionStagingSession(tmp_path / "apm_modules")
        assert other.remove_abandoned_roots() == []
        assert (candidate / "marker").read_bytes() == b"active candidate"
    finally:
        staging.rollback()
    assert not candidate.exists()

"""Local receipts prove rendered writes, never ownership or source selection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apm_cli.core.deployment_ledger import DeploymentLedgerCodec, DeploymentMaterializationSession
from apm_cli.core.deployment_state import DeploymentLedger, DeploymentRecord
from apm_cli.core.scope import InstallScope
from apm_cli.deps.lockfile import LockedDependency, LockFile
from apm_cli.integration.targets import KNOWN_TARGETS
from apm_cli.utils.content_hash import compute_file_hash

pytestmark = pytest.mark.component

TARGET = KNOWN_TARGETS["claude"]


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, LockFile]:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    root = tmp_path / "consumer"
    path = root / ".claude/skills/demo/SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text("rendered old\n", encoding="utf-8")
    locator = DeploymentLedgerCodec.locator_for_path(
        path, project_root=root, target=TARGET, scope=InstallScope.PROJECT
    )
    record = DeploymentRecord(locator, ("pkg",), "pkg", compute_file_hash(path))
    lock = LockFile()
    lock.dependencies["pkg"] = LockedDependency(repo_url="pkg")
    DeploymentLedgerCodec.apply_to_lockfile(
        DeploymentLedger({locator.key: record}), lock, write_legacy_views=False
    )
    return root, path, lock


def _session(root: Path, lock: LockFile) -> DeploymentMaterializationSession:
    return DeploymentMaterializationSession(root, InstallScope.PROJECT, lock)


def test_receipt_outlives_checked_out_hash_without_adopting_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, path, lock = _fixture(tmp_path, monkeypatch)
    old_hash = compute_file_hash(path)
    session = _session(root, lock)
    assert session.baseline(path, [TARGET]) is None
    session.record({path: old_hash}, [TARGET], "pkg")
    session.flush()
    row = next(iter(lock.deployment_ledger.records.values()))
    DeploymentLedgerCodec.apply_to_lockfile(
        DeploymentLedger(
            {
                row.locator.key: DeploymentRecord(
                    row.locator, row.owners, "pkg", "sha256:" + "b" * 64
                )
            }
        ),
        lock,
        write_legacy_views=False,
    )
    assert _session(root, lock).baseline(path, [TARGET]) == old_hash
    path.write_text("user edit\n", encoding="utf-8")
    assert _session(root, lock).baseline(path, [TARGET]) == old_hash
    assert compute_file_hash(path) != old_hash


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "corrupt",
        "owner",
        "scope",
        "identity",
        "destination",
        "member",
        "target",
        "duplicate",
        "binding",
    ],
)
def test_missing_or_mismatched_evidence_never_falls_back_to_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    root, path, lock = _fixture(tmp_path, monkeypatch)
    session = _session(root, lock)
    session.record({path: compute_file_hash(path)}, [TARGET], "pkg")
    session.flush()
    if damage == "missing":
        session.state_path.unlink()
    elif damage == "corrupt":
        session.state_path.write_text("{", encoding="utf-8")
    else:
        data = json.loads(session.state_path.read_text(encoding="utf-8"))
        if damage == "owner":
            data["records"][0]["owners"] = ["foreign"]
            data["records"][0]["active_owner"] = "foreign"
        elif damage == "scope":
            data["scope"] = "user"
        elif damage == "identity":
            data["installation"] = "0" * 32
        elif damage == "destination":
            key = next(iter(data["destinations"]))
            data["destinations"][key] = (root / "foreign/SKILL.md").as_posix()
        elif damage == "duplicate":
            data["records"].append(data["records"][0])
        elif damage == "binding":
            key = next(iter(data["bindings"]))
            data["bindings"][key] = [".", "[]"]
        else:
            data["records"][0]["value" if damage == "member" else "target"] = "foreign"
        session.state_path.write_text(json.dumps(data), encoding="utf-8")
    if damage in {"corrupt", "scope", "identity", "member", "target", "duplicate"}:
        with pytest.raises(ValueError, match="materialization evidence"):
            _session(root, lock)
    else:
        assert _session(root, lock).baseline(path, [TARGET]) is None


@pytest.mark.parametrize("copy_identity", [False, True])
def test_recreated_checkout_cannot_reuse_old_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, copy_identity: bool
) -> None:
    root, path, lock = _fixture(tmp_path, monkeypatch)
    session = _session(root, lock)
    session.record({path: compute_file_hash(path)}, [TARGET], "pkg")
    session.flush()
    root.rename(tmp_path / "old-consumer")
    path.parent.mkdir(parents=True)
    path.write_text("rendered old\n", encoding="utf-8")
    if copy_identity:
        identity = root / ".apm-local/installation"
        identity.parent.mkdir()
        identity.write_bytes((tmp_path / "old-consumer/.apm-local/installation").read_bytes())
        with pytest.raises(ValueError, match="installation binding does not match"):
            _session(root, lock)
    else:
        assert _session(root, lock).baseline(path, [TARGET]) is None


def test_atomic_failure_cannot_publish_new_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apm_cli.utils import atomic_io

    root, path, lock = _fixture(tmp_path, monkeypatch)
    session = _session(root, lock)
    session.record({path: compute_file_hash(path)}, [TARGET], "pkg")
    session.flush()
    before = session.state_path.read_bytes()
    write = atomic_io.atomic_write_text

    def refuse(destination: Path, text: str, **kwargs) -> None:
        if destination == session.state_path:
            raise OSError("injected receipt refusal")
        write(destination, text, **kwargs)

    monkeypatch.setattr(atomic_io, "atomic_write_text", refuse)
    path.write_text("new rendered\n", encoding="utf-8")
    with pytest.raises(OSError, match="receipt refusal"):
        session.record({path: compute_file_hash(path)}, [TARGET], "pkg")
        session.flush()
    assert session.state_path.read_bytes() == before


def test_unclaimed_or_other_target_receipt_cannot_authorize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, path, lock = _fixture(tmp_path, monkeypatch)
    session = _session(root, lock)
    session.record({path: compute_file_hash(path)}, [TARGET], "pkg")
    session.flush()
    assert _session(root, LockFile()).baseline(path, [TARGET]) is None
    assert _session(root, lock).baseline(path, [KNOWN_TARGETS["codex"]]) is None


def test_cleanup_retires_only_successfully_removed_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apm_cli.integration.cleanup import remove_stale_deployed_files
    from apm_cli.utils.diagnostics import DiagnosticCollector

    root, path, lock = _fixture(tmp_path, monkeypatch)
    session = _session(root, lock)
    session.record({path: compute_file_hash(path)}, [TARGET], "pkg")
    session.flush()
    entry = path.relative_to(root).as_posix()
    original_hash = compute_file_hash(path)
    path.write_text("edited\n", encoding="utf-8")
    result = remove_stale_deployed_files(
        [entry],
        root,
        dep_key="pkg",
        targets=[TARGET],
        diagnostics=DiagnosticCollector(),
        recorded_hashes={entry: original_hash},
    )
    assert result.skipped_user_edit == [entry]
    assert _session(root, lock).baseline(path, [TARGET]) == original_hash
    path.write_text("rendered old\n", encoding="utf-8")
    result = remove_stale_deployed_files(
        [entry],
        root,
        dep_key="pkg",
        targets=[TARGET],
        diagnostics=DiagnosticCollector(),
        recorded_hashes={entry: original_hash},
    )
    assert result.deleted == [entry]
    path.write_text("rendered old\n", encoding="utf-8")
    session.bind_committed_claims(lock)
    assert _session(root, lock).baseline(path, [TARGET]) is None


@pytest.mark.windows_compat
def test_scope_isolation_and_atomic_lf_serialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, path, lock = _fixture(tmp_path, monkeypatch)
    session = _session(root, lock)
    session.record({path: compute_file_hash(path)}, [TARGET], "pkg")
    session.flush()
    raw = session.state_path.read_bytes()
    assert b"\r" not in raw
    assert raw.endswith(b"\n")
    user = DeploymentMaterializationSession(root, InstallScope.USER, lock)
    assert user.state_path != session.state_path
    assert user.baseline(path, [TARGET]) is None


def test_changed_canonical_claims_cannot_rebind_without_actual_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, path, lock = _fixture(tmp_path, monkeypatch)
    session = _session(root, lock)
    session.record({path: compute_file_hash(path)}, [TARGET], "pkg")
    session.flush()
    before = session.state_path.read_bytes()
    row = next(iter(lock.deployment_ledger.records.values()))
    lock.dependencies["other"] = LockedDependency(repo_url="other")
    DeploymentLedgerCodec.apply_to_lockfile(
        DeploymentLedger(
            {row.locator.key: DeploymentRecord(row.locator, ("other",), "other", row.content_hash)}
        ),
        lock,
        write_legacy_views=False,
    )
    new_session = _session(root, lock)
    assert new_session.baseline(path, [TARGET]) is None
    new_session.bind_committed_claims(lock)
    assert session.state_path.read_bytes() == before
    assert _session(root, lock).baseline(path, [TARGET]) is None


@pytest.mark.parametrize("binding", ["identity", "state"])
@pytest.mark.parametrize("outside", [False, True], ids=["contained", "escaping"])
def test_symlinked_evidence_is_rejected_without_touching_referent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, binding: str, outside: bool
) -> None:
    from apm_cli.utils.path_security import PathTraversalError

    root, path, lock = _fixture(tmp_path, monkeypatch)
    session = _session(root, lock)
    session.record({path: compute_file_hash(path)}, [TARGET], "pkg")
    session.flush()
    selected = session.identity_path if binding == "identity" else session.state_path
    referent = (tmp_path if outside else selected.parent) / f"saved-{binding}"
    selected.rename(referent)
    original = referent.read_bytes()
    selected.symlink_to(referent)
    expected = "outside the allowed base" if outside else "symlinked materialization evidence"
    with pytest.raises(PathTraversalError, match=expected):
        _session(root, lock)
    assert referent.read_bytes() == original


@pytest.mark.parametrize("stage", ["copy", "rewrite", "hash", "persist"])
def test_failed_rendering_never_promotes_a_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    import shutil

    from apm_cli.integration.skill_integrator import SkillIntegrator
    from apm_cli.utils import atomic_io, content_hash
    from tests.unit.integration.test_skill_materialization_completion import (
        _fixture as skill_fixture,
    )

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    package, root, plan = skill_fixture(tmp_path)
    session = _session(root, LockFile())
    integrator = SkillIntegrator()

    def fail(*args, **kwargs):
        raise OSError(f"injected {stage} failure")

    if stage == "copy":
        monkeypatch.setattr(shutil, "copy2", fail)
    elif stage == "rewrite":
        monkeypatch.setattr(integrator, "_resolve_markdown_links_in_skill_bundle", fail)
    elif stage == "hash":
        monkeypatch.setattr(content_hash, "compute_file_hash", fail)
    else:
        monkeypatch.setattr(atomic_io, "atomic_write_text", fail)
    with (
        pytest.raises(OSError, match=f"injected {stage} failure"),
        integrator.ownership_snapshot(materialization_session=session),
    ):
        integrator.integrate_package_skill(
            package, root, targets=[TARGET], source_plan=plan, managed_files=set(), skip_bin=True
        )
    assert not session.state_path.exists()


def test_identical_unowned_members_do_not_create_local_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    from apm_cli.integration.skill_integrator import SkillIntegrator
    from tests.unit.integration.test_skill_materialization_completion import (
        _fixture as skill_fixture,
    )

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    package, root, plan = skill_fixture(tmp_path)
    shutil.copytree(package.install_path / "skills/s", root / ".claude/skills/s")
    session = _session(root, LockFile())
    integrator = SkillIntegrator()
    with integrator.ownership_snapshot(materialization_session=session):
        result = integrator.integrate_package_skill(
            package, root, targets=[TARGET], source_plan=plan, managed_files=set(), skip_bin=True
        )
    assert result.deployed_files
    assert not session.state_path.exists()

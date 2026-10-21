"""Installed-CLI recovery of obsolete, already-absent dependency claims (#3281)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from apm_cli.utils.yaml_io import dump_yaml, load_yaml
from tests.integration.test_required_lifecycle_state_machine import (
    _INSTALL_ARGS,
    _new_scenario,
    _skill,
)
from tests.integration.test_shared_skill_preservation_lifecycle import (
    _scenario as _shared_scenario,
)
from tests.utils.apm_lifecycle_runner import CommandResult
from tests.utils.artifact_snapshot import ArtifactSnapshot, assert_unchanged

pytestmark = [
    pytest.mark.integration,
    pytest.mark.e2e,
    pytest.mark.requires_apm_binary,
]


@pytest.mark.parametrize("user_scope", [False, True], ids=["project", "user"])
@pytest.mark.parametrize("historical", ["legacy", "compatibility", "concrete"])
@pytest.mark.parametrize(
    "already_absent", [False, True], ids=["present-then-absent", "already-absent"]
)
def test_ordinary_install_retires_obsolete_absent_dependency_claims(
    tmp_path: Path,
    apm_binary_path: Path,
    user_scope: bool,
    historical: str,
    already_absent: bool,
) -> None:
    """Migrate a real baseline explicitly, repair normally, audit, replay, and remove."""
    scenario = _new_scenario(tmp_path / "scenario", apm_binary_path)
    source = scenario.sources.create("obsolete-source")
    skill = scenario.sources.add_skill(source, "demo", _skill("demo"))
    extra = skill.parent / "extra.md"
    extra.write_text("Old dependency asset.\n", encoding="ascii")
    consumer = scenario.consumers.create(
        "consumer",
        targets=("claude", "codex"),
        dependencies=({"path": str(source.root)},),
    )
    scope_args = ("--global",) if user_scope else ()
    state_root = scenario.isolated.config_root if user_scope else consumer.root
    deploy_root = scenario.isolated.home if user_scope else consumer.root
    if user_scope:
        dump_yaml(load_yaml(consumer.manifest_path), state_root / "apm.yml")
    lock_path = state_root / "apm.lock.yaml"
    roots = (".claude/skills/demo", ".agents/skills/demo")
    obsolete = {f"{root}/extra.md" for root in roots}
    surviving = {f"{root}/SKILL.md" for root in roots}
    expected_bytes = skill.read_bytes()
    expected_hash = "sha256:" + hashlib.sha256(expected_bytes).hexdigest()

    def run(*args: str, expected: int = 0, cwd: Path | None = None) -> CommandResult:
        result = scenario.runner.run(
            args,
            scenario_id=f"obsolete-claims-{historical}-{user_scope}-{args[0]}",
            cwd=cwd if cwd is not None else consumer.root,
            env=scenario.environment,
        )
        assert result.returncode == expected, (result.command, result.stdout, result.stderr)
        return result

    def audit(*, ci: bool, expected: int = 0) -> dict:
        before = ArtifactSnapshot.capture(tmp_path)
        args = ("audit", "--format", "json")
        if ci:
            args += ("--ci", "--no-policy", "--no-fail-fast")
        result = run(*args, expected=expected, cwd=state_root)
        assert_unchanged(before, ArtifactSnapshot.capture(tmp_path))
        return json.loads(result.stdout)

    install = (*_INSTALL_ARGS, *scope_args)
    run(*install)
    baseline = load_yaml(lock_path)
    assert obsolete <= set(baseline["dependencies"][0]["deployed_files"])
    assert obsolete <= {row["value"] for row in baseline["deployments"]}
    for path in obsolete:
        assert (deploy_root / path).read_bytes() == extra.read_bytes()

    # This is an explicit historical-format migration, not current producer output.
    if historical == "legacy":
        for row in baseline["deployments"]:
            if row["value"].startswith(".agents/"):
                row["target"] = "legacy"
        dump_yaml(baseline, lock_path)
    elif historical == "compatibility":
        baseline.pop("deployments")
        dump_yaml(baseline, lock_path)

    extra.unlink()
    if not already_absent and historical != "concrete":
        # Source removal alone cannot authorize deletion of an unattributed file.
        run(*install)
        retained = load_yaml(lock_path)
        shared = ".agents/skills/demo/extra.md"
        assert (deploy_root / shared).read_bytes() == b"Old dependency asset.\n"
        assert shared in retained["dependencies"][0]["deployed_files"]
        assert shared in retained["dependencies"][0]["deployed_file_hashes"]
        assert any(row["value"] == shared for row in retained["deployments"])
        (deploy_root / shared).unlink()
    if already_absent:
        for path in obsolete:
            (deploy_root / path).unlink()
        before = audit(ci=True, expected=1)
        presence = next(c for c in before["checks"] if c["name"] == "deployed-files-present")
        assert presence["passed"] is False
        assert obsolete <= set(presence["details"])

    before_dry_run = ArtifactSnapshot.capture(tmp_path)
    run(*install, "--dry-run")
    assert_unchanged(before_dry_run, ArtifactSnapshot.capture(tmp_path))
    run(*install)
    repaired = load_yaml(lock_path)
    dependency = repaired["dependencies"][0]
    assert obsolete.isdisjoint(dependency["deployed_files"])
    assert obsolete.isdisjoint(dependency["deployed_file_hashes"])
    assert obsolete.isdisjoint(row["value"] for row in repaired["deployments"])
    assert surviving <= set(dependency["deployed_files"])
    for path in surviving:
        assert (deploy_root / path).read_bytes() == expected_bytes
        assert dependency["deployed_file_hashes"][path] == expected_hash
        records = [row for row in repaired["deployments"] if row["value"] == path]
        assert len(records) == 1
        assert records[0]["owners"] == [str(source.root)]
        assert records[0]["active_owner"] == str(source.root)
        assert records[0]["content_hash"] == expected_hash
    assert all(not (deploy_root / path).exists() for path in obsolete)

    assert audit(ci=True)["passed"] is True
    audit(ci=False)
    settled_bytes = lock_path.read_bytes()
    for flags in ((), ("--frozen",)):
        run(*install, *flags)
        assert lock_path.read_bytes() == settled_bytes
        assert all((deploy_root / path).read_bytes() == expected_bytes for path in surviving)
        assert audit(ci=True)["passed"] is True

    run("uninstall", *scope_args, str(source.root))
    assert all(not (deploy_root / path).exists() for path in surviving | obsolete)
    if lock_path.exists():
        final = load_yaml(lock_path)
        assert not final.get("dependencies")
        assert not final.get("deployments")


@pytest.mark.parametrize("user_scope", [False, True], ids=["project", "user"])
@pytest.mark.parametrize(
    "protection", ["edited-marker", "unprocessed-target", "required-selection", "untracked-content"]
)
def test_historical_absence_respects_live_preservation_boundaries(
    tmp_path: Path, apm_binary_path: Path, user_scope: bool, protection: str
) -> None:
    """Real CLI receipt production cannot turn missing bytes into blanket authority."""
    scenario = _shared_scenario(tmp_path, apm_binary_path, user_scope)
    scenario.install("a")
    lock_path = scenario.lock_root / "apm.lock.yaml"
    lock = load_yaml(lock_path)
    shared = ".agents/skills/s/a.md"
    expected_hash = lock["dependencies"][0]["deployed_file_hashes"][shared]
    for row in lock["deployments"]:
        if row["value"].startswith(".agents/"):
            row["target"] = "legacy"
    dump_yaml(lock, lock_path)
    (scenario.packages["a"] / "skills/s/a.md").unlink()
    for root in (".agents", ".claude"):
        (scenario.deploy_root / root / "skills/s/a.md").unlink()

    marker = scenario.deploy_root / ".agents/skills/s/SKILL.md"
    untracked = scenario.deploy_root / ".agents/skills/s/personal.txt"
    if protection == "edited-marker":
        marker.write_bytes(b"User-edited skill marker.\n")
    elif protection == "required-selection":
        scenario.manifest(
            dependencies={
                "apm": [{"path": str(scenario.packages["a"]), "skills": ["no-such-skill"]}]
            }
        )
    elif protection == "untracked-content":
        untracked.write_bytes(b"Untracked personal content.\n")
    arguments = ("--target", "claude") if protection == "unprocessed-target" else ()
    expected_exit = 1 if protection == "required-selection" else 0
    prior_bytes = lock_path.read_bytes()
    for _ in range(2):
        scenario.run("install", *arguments, expected=expected_exit)
        repaired = load_yaml(lock_path)
        dependency = repaired["dependencies"][0]
        rows = [row for row in repaired["deployments"] if row["value"] == shared]
        if protection == "untracked-content":
            assert shared not in dependency["deployed_files"]
            assert shared not in dependency["deployed_file_hashes"]
            assert rows == []
            assert untracked.read_bytes() == b"Untracked personal content.\n"
            personal = ".agents/skills/s/personal.txt"
            assert personal not in dependency["deployed_files"]
            assert personal not in dependency["deployed_file_hashes"]
            assert all(row["value"] != personal for row in repaired["deployments"])
        else:
            assert shared in dependency["deployed_files"]
            assert dependency["deployed_file_hashes"][shared] == expected_hash
            assert len(rows) == 1
            assert rows[0]["target"] == "legacy"
            assert rows[0]["owners"] == [str(scenario.packages["a"])]
            assert rows[0]["content_hash"] == expected_hash
            scenario.run("audit", "--ci", "--format", "json", expected=1)
        assert not (scenario.deploy_root / shared).exists()
        if protection == "edited-marker":
            assert marker.read_bytes() == b"User-edited skill marker.\n"
        elif protection == "required-selection":
            assert lock_path.read_bytes() == prior_bytes

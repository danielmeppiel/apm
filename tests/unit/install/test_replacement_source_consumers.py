"""Filesystem-backed consumers distinguish ownership from the selected source."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import urlparse

import pytest

from apm_cli.agent_plugins.errors import AgentPluginDeploymentBoundaryError
from apm_cli.commands.deps.why import _render_human, _render_json
from apm_cli.commands.outdated import _check_one_dep
from apm_cli.deps.lockfile import LockedDependency, LockFile
from apm_cli.deps.path_anchoring import LocalResolutionError
from apm_cli.deps.why_walker import compute_why
from apm_cli.install.drift import _materialize_install_path
from apm_cli.install.exec_gate import check_executable_approval, resolve_package_key
from apm_cli.install.helpers.ref_reuse import maybe_resolve_git_semver
from apm_cli.install.native_plugin_admission import verify_native_plugin_cache
from apm_cli.install.resolution_staging import ResolutionStagingSession
from apm_cli.models.dependency.materialization import prepare_materialization_path
from apm_cli.models.dependency.reference import DependencyReference
from apm_cli.models.dependency.replacement import (
    build_replacement_index,
    parse_replace_block,
    replacement_rule_to_dict,
)
from apm_cli.models.dependency.types import GitReferenceType, RemoteRef
from apm_cli.policy.policy_checks import _check_dependency_allowlist, _check_dependency_denylist
from apm_cli.policy.schema import DependencyPolicy
from apm_cli.utils.content_hash import compute_package_hash

pytestmark = pytest.mark.component


def _locked(tmp_path: Path, source: dict, *, parent: str | None = None):
    original = DependencyReference.parse("https://github.com/MixedOrg/MixedRepo#upstream")
    rule = parse_replace_block(
        [{"for": {"git": "https://github.com/MixedOrg/MixedRepo"}, "with": source}]
    )[0]
    selected = build_replacement_index([rule]).bind(
        original,
        consumer_root=tmp_path,
        modules_dir=tmp_path / "apm_modules",
        parent=parent,
        is_dev=False,
    )
    locked = LockedDependency.from_dependency_ref(
        selected, None if selected.is_local else "a" * 40, 1, parent
    )
    lock = LockFile(replacements=[replacement_rule_to_dict(rule)])
    lock.add_dependency(locked)
    return selected, locked, lock


def test_local_replacement_outdated_is_not_remotely_comparable(tmp_path: Path) -> None:
    _, locked, _ = _locked(tmp_path, {"path": "../local"})
    downloader = Mock()
    row = _check_one_dep(locked, downloader, False)
    assert row.package == "mixedorg/mixedrepo"
    assert row.status == "not-comparable"
    assert "../local" in row.source
    assert downloader.mock_calls == []


def test_fork_outdated_queries_clean_selected_reference(tmp_path: Path) -> None:
    _, locked, _ = _locked(tmp_path, {"git": "https://gitlab.com/team/fork", "ref": "patched"})
    downloader = Mock()
    downloader.list_remote_refs.return_value = [
        RemoteRef(name="patched", ref_type=GitReferenceType.BRANCH, commit_sha="b" * 40)
    ]
    row = _check_one_dep(locked, downloader, False)
    queried = downloader.list_remote_refs.call_args.args[0]
    assert queried.repo_url == "team/fork"
    assert queried.host == "gitlab.com"
    assert queried.replacement is None
    assert row.package == "mixedorg/mixedrepo"
    assert row.status == "outdated"
    source = row.source.partition(": ")[2].split()[0]
    parsed = urlparse(source if "://" in source else "//" + source)
    assert (parsed.hostname, parsed.path, parsed.fragment) == (
        "gitlab.com",
        "/team/fork",
        "patched",
    )


def test_replacement_why_keeps_exact_diamond_parents_and_original_refs(tmp_path: Path) -> None:
    left = LockedDependency(repo_url="owner/parents", virtual_path="packages/left", is_virtual=True)
    right = LockedDependency(
        repo_url="owner/parents", virtual_path="packages/right", is_virtual=True
    )
    _, locked, lock = _locked(tmp_path, {"path": "../local"}, parent=left.get_unique_key())
    second = DependencyReference.parse("https://github.com/MixedOrg/MixedRepo#other-request")
    locked.replacement.record(second, right.get_unique_key(), False)
    lock.add_dependency(left)
    lock.add_dependency(right)
    result = compute_why(lock, locked)
    assert not result.is_direct
    assert len(result.paths) == 2
    assert {
        (path.chain[0].child_key, path.chain[-1].child_key, path.chain[-1].constraint)
        for path in result.paths
    } == {
        (left.get_unique_key(), "mixedorg/mixedrepo", "upstream"),
        (right.get_unique_key(), "mixedorg/mixedrepo", "other-request"),
    }


def test_replacement_why_exposes_direct_and_transitive_requests(tmp_path: Path) -> None:
    _, locked, lock = _locked(tmp_path, {"path": "../local"})
    parent = LockedDependency(repo_url="owner/parent")
    indirect = DependencyReference.parse("https://github.com/MixedOrg/MixedRepo#indirect")
    locked.replacement.record(indirect, parent.get_unique_key(), False)
    lock.add_dependency(parent)
    result = compute_why(lock, locked)
    assert result.is_direct
    assert len(result.paths) == 2
    human = _render_human(result)
    assert "-> ../local" in human
    assert "owner/parent" in human
    assert "constraint: indirect" in human
    structured = json.loads(_render_json(result))
    assert structured["package"]["replacement"] == locked.replacement.to_dict()
    assert len(structured["paths"]) == 2


def test_local_replacement_audit_reads_source_not_upstream_cache(tmp_path: Path) -> None:
    source = tmp_path.parent / f"{tmp_path.name}-local"
    source.mkdir()
    _, locked, lock = _locked(tmp_path, {"path": str(source)})
    assert (
        _materialize_install_path(locked, tmp_path, tmp_path / "scratch", True, lockfile=lock)
        == source
    )


def test_native_local_replacement_audit_uses_current_selected_source_bytes(tmp_path: Path) -> None:
    selected, locked, _ = _locked(tmp_path, {"path": "./selected"})
    source = tmp_path / "selected"
    source.mkdir()
    (source / "SKILL.md").write_text("new selected content\n", encoding="ascii")
    modules = tmp_path / "apm_modules"
    candidate = selected.get_install_path(modules)
    candidate.mkdir(parents=True)
    (candidate / "SKILL.md").write_text("old selected content\n", encoding="ascii")
    locked.content_hash = compute_package_hash(candidate)
    scratch = tmp_path / "scratch"
    replay = selected.get_install_path(scratch / "apm_modules")
    with pytest.raises(AgentPluginDeploymentBoundaryError, match="cache differs"):
        verify_native_plugin_cache(locked, source, replay, modules, scratch)
    (candidate / "SKILL.md").write_bytes((source / "SKILL.md").read_bytes())
    verify_native_plugin_cache(locked, source, replay, modules, scratch)
    assert (replay / "SKILL.md").read_bytes() == (source / "SKILL.md").read_bytes()


def test_missing_replacement_audit_source_is_not_a_soft_cache_miss(tmp_path: Path) -> None:
    _, locked, lock = _locked(tmp_path, {"path": "../missing"})
    with pytest.raises(LocalResolutionError, match=r"replacement.*missing"):
        _materialize_install_path(locked, tmp_path, tmp_path / "scratch", True, lockfile=lock)


def test_replacement_casing_migration_uses_original_owner(tmp_path: Path) -> None:
    selected, _, _ = _locked(tmp_path, {"path": "../local"})
    modules = tmp_path / "apm_modules"
    stale = modules / "mixedorg" / "mixedrepo"
    stale.mkdir(parents=True)
    (stale / "marker").write_text("owned", encoding="utf-8")
    staging = ResolutionStagingSession(modules)
    migrations = []
    try:
        destination = prepare_materialization_path(
            selected,
            modules,
            staging,
            on_migrate=lambda old, new: migrations.append((old, new)),
        )
        assert migrations == [(stale, modules / "MixedOrg" / "MixedRepo")]
        assert (destination / "marker").read_text(encoding="utf-8") == "owned"
    finally:
        staging.rollback()
    assert (stale / "marker").is_file()


@pytest.mark.parametrize(
    "source", [{"path": "../local"}, {"git": "https://github.com/team/fork", "ref": "patched"}]
)
def test_replacement_does_not_inherit_upstream_executable_approval(
    tmp_path: Path, source: dict
) -> None:
    selected, _, _ = _locked(tmp_path, source)
    package = SimpleNamespace(dependency_ref=selected)
    upstream = SimpleNamespace(dependency_ref=selected.ownership_reference)
    approval = {
        resolve_package_key(upstream, "upstream"): {"hooks": True, "bin": True, "mcp": True}
    }
    assert check_executable_approval("upstream", upstream, approval)[:3] == (True,) * 3
    assert check_executable_approval("mixedorg/mixedrepo", package, approval) == (False,) * 5


@pytest.mark.parametrize(
    "source", [{"path": "../local"}, {"git": "https://github.com/team/fork", "ref": "patched"}]
)
def test_dependency_policy_evaluates_the_selected_source(tmp_path: Path, source: dict) -> None:
    selected, _, _ = _locked(tmp_path, source)
    original_name = selected.ownership_reference.get_canonical_dependency_string()
    selected_name = selected.get_canonical_dependency_string()
    assert not _check_dependency_allowlist(
        [selected], DependencyPolicy(allow=[original_name])
    ).passed
    assert not _check_dependency_denylist([selected], DependencyPolicy(deny=[selected_name])).passed


def test_semver_source_change_discards_old_resolution_and_routes_effective_auth(
    tmp_path: Path,
) -> None:
    _, old, lock = _locked(tmp_path, {"git": "https://github.com/old/fork", "ref": "^1.0.0"})
    old.constraint = "^1.0.0"
    old.version = "1.0.0"
    old.resolved_ref = old.resolved_tag = "v1.0.0"
    selected, _, _ = _locked(tmp_path, {"git": "https://gitlab.com/new/fork", "ref": "^1.0.0"})
    auth = Mock()
    auth.uses_public_github_anonymous_first.return_value = False
    auth.resolve_for_dep.return_value = SimpleNamespace(
        token=None, auth_scheme="basic", host_info=SimpleNamespace(kind="gitlab")
    )
    auth.git_env_for_remote.return_value = {}
    fresh_resolution = object()
    with (
        patch("apm_cli.marketplace.ref_resolver.RefResolver"),
        patch("apm_cli.deps.git_semver_resolver.GitSemverResolver") as resolver,
    ):
        resolver.return_value.resolve.return_value = fresh_resolution
        assert (
            maybe_resolve_git_semver(
                dep_ref=selected, existing_lockfile=lock, update_refs=False, auth_resolver=auth
            )
            is fresh_resolution
        )
    assert auth.resolve_for_dep.call_args_list
    for call in auth.resolve_for_dep.call_args_list:
        reference = call.args[0]
        assert (reference.host, reference.repo_url) == ("gitlab.com", "new/fork")
        assert reference.replacement is None

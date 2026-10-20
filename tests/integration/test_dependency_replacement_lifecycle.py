"""Root source replacement contracts through an installed APM executable."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from apm_cli.models.dependency.replacement import parse_replace_block
from apm_cli.utils.yaml_io import dump_yaml, load_yaml
from tests.utils.apm_lifecycle_runner import ApmLifecycleRunner, CommandResult
from tests.utils.isolated_apm_environment import IsolatedApmEnvironment
from tests.utils.local_git_repository import LocalGitRepository, LocalGitRepositoryFactory
from tests.utils.local_package import LocalPackage, LocalPackageFactory

pytestmark = [
    pytest.mark.integration,
    pytest.mark.e2e,
    pytest.mark.requires_apm_binary,
    pytest.mark.lifecycle_smoke,
]

_SCHEMA = (
    "https://microsoft.github.io/apm/specs/schemas/manifest-source-replacements-v1.schema.json"
)
_UPSTREAM = "https://github.com/apm-replacement-fixture/base"
_FORK = "https://github.com/apm-replacement-fixture/fork"
_INSTRUCTION = ".github/instructions/base.instructions.md"
_INSTALL = ("install", "--no-policy", "--target", "copilot", "--parallel-downloads", "0")


def _content(marker: str) -> str:
    return f"---\napplyTo: '**'\n---\n# {marker}\n"


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for prefix in ("apm.lock.yaml", ".github", "apm_modules")
        for path in ([root / prefix] if (root / prefix).is_file() else (root / prefix).rglob("*"))
        if path.is_file()
    }


@dataclass(frozen=True)
class ReplacementFixture:
    consumer: LocalPackage
    local: LocalPackage
    upstream_sha: str
    fork_sha: str
    upstream: LocalGitRepository
    fork: LocalGitRepository
    repositories: LocalGitRepositoryFactory
    environment: dict[str, str]
    runner: ApmLifecycleRunner

    def run(self, *args: str, root: Path | None = None) -> CommandResult:
        return self.runner.run(
            args or _INSTALL,
            cwd=root or self.consumer.root,
            env=self.environment,
            scenario_id="root-source-replacement",
        )

    def install(self) -> None:
        result = self.run()
        assert result.returncode == 0, result.stdout + result.stderr

    def replace(self, source: dict[str, str] | None) -> None:
        manifest = load_yaml(self.consumer.manifest_path)
        if source is None:
            manifest.pop("replace", None)
            manifest.pop("$schema", None)
        else:
            manifest["$schema"] = _SCHEMA
            manifest["replace"] = [{"for": {"git": _UPSTREAM}, "with": source}]
        dump_yaml(manifest, self.consumer.manifest_path)

    def assert_bytes(self, marker: str, *, root: Path | None = None) -> None:
        project = root or self.consumer.root
        assert (project / _INSTRUCTION).read_bytes() == _content(marker).encode("utf-8")

    def locked_entry(self) -> dict:
        locked = load_yaml(self.consumer.root / "apm.lock.yaml")
        assert len(locked["dependencies"]) == 1
        entry = locked["dependencies"][0]
        assert entry["repo_url"] == "apm-replacement-fixture/base"
        assert not entry.get("local_path")
        modules = self.consumer.root / "apm_modules"
        manifests = sorted(
            path.relative_to(modules).as_posix() for path in modules.rglob("apm.yml")
        )
        assert manifests == ["apm-replacement-fixture/base/apm.yml"]
        return entry


@pytest.fixture
def replacement_fixture(tmp_path: Path, apm_binary_path: Path) -> ReplacementFixture:
    isolated = IsolatedApmEnvironment.create(tmp_path / "replacement", base_env=dict(os.environ))
    environment = isolated.subprocess_env()
    source_factory = LocalPackageFactory(isolated.package_root)
    upstream = source_factory.create("base", targets=("copilot",))
    source_factory.add_instruction(upstream, "base", _content("UPSTREAM"))
    fork_source = source_factory.create("fork", targets=("copilot",))
    source_factory.add_instruction(fork_source, "base", _content("FORK"))
    work_factory = LocalPackageFactory(isolated.work_root)
    local = work_factory.create("local-base", targets=("copilot",))
    work_factory.add_instruction(local, "base", _content("LOCAL"))
    repositories = LocalGitRepositoryFactory(isolated.repository_root, env=environment)
    origin = repositories.create("base", source_tree=upstream.root)
    upstream_sha = repositories.commit(origin, message="Original source").sha
    fork = repositories.create("fork", source_tree=fork_source.root)
    fork_sha = repositories.commit(fork, message="Replacement source").sha
    environment = repositories.url_rewrite_subprocess_env_many(((origin, _UPSTREAM), (fork, _FORK)))
    environment["APM_POLICY_DISABLE"] = "1"
    consumer = work_factory.create(
        "consumer",
        dependencies=({"git": _UPSTREAM, "ref": upstream_sha},),
        targets=("copilot",),
    )
    return ReplacementFixture(
        consumer,
        local,
        upstream_sha,
        fork_sha,
        origin,
        fork,
        repositories,
        environment,
        ApmLifecycleRunner((str(apm_binary_path),)),
    )


def test_replacement_upstream_local_fork_upstream_owns_one_slot(
    replacement_fixture: ReplacementFixture,
) -> None:
    fixture = replacement_fixture
    fixture.install()
    fixture.assert_bytes("UPSTREAM")
    assert fixture.locked_entry()["resolved_commit"] == fixture.upstream_sha
    unmanaged = fixture.consumer.root / ".github/instructions/user.instructions.md"
    unmanaged.write_bytes(b"unmanaged user content\n")

    fixture.replace({"path": "../local-base"})
    fixture.install()
    fixture.assert_bytes("LOCAL")
    local_entry = fixture.locked_entry()
    assert local_entry["replacement"]["source"] == {"path": "../local-base"}
    assert not local_entry.get("resolved_commit")
    locked = load_yaml(fixture.consumer.root / "apm.lock.yaml")
    assert locked["lockfile_version"] == "3"
    assert parse_replace_block(locked["replacements"]) == parse_replace_block(
        load_yaml(fixture.consumer.manifest_path)["replace"]
    )

    fixture.replace({"git": _FORK, "ref": fixture.fork_sha})
    fixture.install()
    fixture.assert_bytes("FORK")
    fork_entry = fixture.locked_entry()
    assert fork_entry["resolved_commit"] == fixture.fork_sha
    assert fork_entry["replacement"]["requests"][0]["ref"] == fixture.upstream_sha

    fixture.replace(None)
    fixture.install()
    fixture.assert_bytes("UPSTREAM")
    restored = fixture.locked_entry()
    assert restored["resolved_commit"] == fixture.upstream_sha
    assert not restored.get("replacement")
    assert unmanaged.read_bytes() == b"unmanaged user content\n"


def test_replacement_same_named_ref_invalidates_upstream_cache_and_pin(
    replacement_fixture: ReplacementFixture,
) -> None:
    fixture = replacement_fixture
    manifest = load_yaml(fixture.consumer.manifest_path)
    manifest["dependencies"]["apm"][0]["ref"] = "main"
    dump_yaml(manifest, fixture.consumer.manifest_path)
    fixture.install()
    fixture.assert_bytes("UPSTREAM")
    fixture.replace({"git": _FORK, "ref": "main"})
    fixture.install()
    fixture.assert_bytes("FORK")
    assert fixture.locked_entry()["resolved_commit"] == fixture.fork_sha
    fixture.replace(None)
    fixture.install()
    fixture.assert_bytes("UPSTREAM")
    assert fixture.locked_entry()["resolved_commit"] == fixture.upstream_sha


@pytest.mark.parametrize("dry_run", [False, True], ids=["install", "preview"])
def test_replacement_ignores_unused_original_http_transport(
    replacement_fixture: ReplacementFixture, dry_run: bool
) -> None:
    fixture = replacement_fixture
    fixture.replace({"path": "../local-base"})
    manifest = load_yaml(fixture.consumer.manifest_path)
    original = "http://github.com/apm-replacement-fixture/base"
    manifest["dependencies"]["apm"][0]["git"] = original
    manifest["replace"][0]["for"]["git"] = original
    dump_yaml(manifest, fixture.consumer.manifest_path)
    result = fixture.run(*_INSTALL, *(("--dry-run",) if dry_run else ()))
    assert result.returncode == 0, result.stdout + result.stderr
    if dry_run:
        assert not (fixture.consumer.root / "apm.lock.yaml").exists()
        assert not (fixture.consumer.root / _INSTRUCTION).exists()
    else:
        fixture.assert_bytes("LOCAL")
        assert fixture.locked_entry()["replacement"]["source"] == {"path": "../local-base"}
    fixture.replace(None)
    result = fixture.run(*_INSTALL, *(("--dry-run",) if dry_run else ()))
    assert result.returncode != 0, result.stdout + result.stderr
    assert "insecure" in (result.stdout + result.stderr).lower()


@pytest.mark.parametrize("cli_consent", [False, True])
def test_replacement_http_source_cannot_borrow_original_or_global_consent(
    replacement_fixture: ReplacementFixture, cli_consent: bool
) -> None:
    fixture = replacement_fixture
    fixture.replace({"path": "../local-base"})
    fixture.install()
    before = _snapshot(fixture.consumer.root)
    fixture.replace({"git": "http://github.com/apm-replacement-fixture/fork", "ref": "main"})
    manifest = load_yaml(fixture.consumer.manifest_path)
    original = "http://github.com/apm-replacement-fixture/base"
    manifest["dependencies"]["apm"][0]["git"] = original
    manifest["dependencies"]["apm"][0]["allow_insecure"] = True
    manifest["replace"][0]["for"]["git"] = original
    dump_yaml(manifest, fixture.consumer.manifest_path)
    result = fixture.run(*_INSTALL, *(("--allow-insecure",) if cli_consent else ()))
    assert result.returncode != 0, result.stdout + result.stderr
    assert "HTTP replacement sources are not supported" in " ".join(
        (result.stdout + result.stderr).split()
    )
    assert _snapshot(fixture.consumer.root) == before


@pytest.mark.parametrize("failure", ["missing", "invalid", "bad-fork-ref"])
def test_replacement_failure_preserves_previous_owned_bytes_without_fallback(
    replacement_fixture: ReplacementFixture, failure: str
) -> None:
    fixture = replacement_fixture
    fixture.replace({"path": "../local-base"})
    fixture.install()
    before = _snapshot(fixture.consumer.root)
    source = {"path": "../missing"}
    if failure == "invalid":
        fixture.local.manifest_path.write_text("name: [invalid\n", encoding="utf-8")
        source = {"path": "../local-base"}
    elif failure == "bad-fork-ref":
        source = {"git": _FORK, "ref": "missing-replacement-ref"}
    fixture.replace(source)
    result = fixture.run()
    assert result.returncode != 0, result.stdout + result.stderr
    assert "replacement" in (result.stdout + result.stderr).lower()
    assert _snapshot(fixture.consumer.root) == before
    fixture.assert_bytes("LOCAL")


@pytest.mark.parametrize("cold", [False, True], ids=["existing", "cold"])
def test_replacement_frozen_local_content_uses_locked_source_evidence(
    replacement_fixture: ReplacementFixture, cold: bool
) -> None:
    fixture = replacement_fixture
    fixture.replace({"path": "../local-base"})
    fixture.install()
    fixture.assert_bytes("LOCAL")
    target = fixture.consumer.root
    if cold:
        target = target.parent / "cold-consumer"
        target.mkdir()
        shutil.copy2(fixture.consumer.manifest_path, target / "apm.yml")
        shutil.copy2(fixture.consumer.root / "apm.lock.yaml", target / "apm.lock.yaml")
    accepted = fixture.run(*_INSTALL, "--frozen", root=target)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    fixture.assert_bytes("LOCAL", root=target)
    original = fixture.local.root / ".apm/instructions/base.instructions.md"
    original.write_text(_content("LOCAL-CHANGED"), encoding="utf-8")
    if cold:
        target = fixture.consumer.root.parent / "changed-cold-consumer"
        target.mkdir()
        shutil.copy2(fixture.consumer.manifest_path, target / "apm.yml")
        shutil.copy2(fixture.consumer.root / "apm.lock.yaml", target / "apm.lock.yaml")
    before = _snapshot(target)
    refused = fixture.run(*_INSTALL, "--frozen", root=target)
    assert refused.returncode != 0, refused.stdout + refused.stderr
    assert "content" in (refused.stdout + refused.stderr).lower()
    assert _snapshot(target) == before


@pytest.mark.parametrize("change", ["edit", "remove", "add"])
def test_replacement_frozen_compares_dormant_rules_without_reading_sources(
    replacement_fixture: ReplacementFixture, change: str
) -> None:
    fixture = replacement_fixture
    fixture.replace({"path": "../local-base"})
    manifest = load_yaml(fixture.consumer.manifest_path)
    manifest["replace"].append(
        {
            "for": {"git": "https://github.com/apm-replacement-fixture/unused"},
            "with": {"path": "../never-present"},
        }
    )
    dump_yaml(manifest, fixture.consumer.manifest_path)
    result = fixture.run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "unused" in (result.stdout + result.stderr).lower()
    before = _snapshot(fixture.consumer.root)
    if change == "edit":
        manifest["replace"][1]["with"]["path"] = "../also-not-present"
    elif change == "remove":
        manifest["replace"].pop()
    else:
        manifest["replace"].append(
            {
                "for": {"git": "https://github.com/apm-replacement-fixture/another-unused"},
                "with": {"path": "../also-not-present"},
            }
        )
    dump_yaml(manifest, fixture.consumer.manifest_path)
    result = fixture.run(*_INSTALL, "--frozen")
    assert result.returncode != 0, result.stdout + result.stderr
    assert "replacement" in (result.stdout + result.stderr).lower()
    assert _snapshot(fixture.consumer.root) == before


def test_replacement_explicit_fork_sha_survives_update(
    replacement_fixture: ReplacementFixture,
) -> None:
    fixture = replacement_fixture
    fixture.replace({"git": _FORK, "ref": fixture.fork_sha})
    fixture.install()
    fixture.assert_bytes("FORK")
    original = fixture.fork.worktree / ".apm/instructions/base.instructions.md"
    original.write_text(_content("FORK-NEW"), encoding="utf-8")
    fixture.repositories.commit(fixture.fork, message="Advance unselected replacement tip")
    upstream = fixture.upstream.worktree / ".apm/instructions/base.instructions.md"
    upstream.write_text(_content("UPSTREAM-NEW"), encoding="utf-8")
    upstream_tip = fixture.repositories.commit(fixture.upstream, message="New upstream release")
    fixture.repositories.tag(fixture.upstream, "v9.0.0", upstream_tip, annotated=True)
    before_manifest = fixture.consumer.manifest_path.read_bytes()
    result = fixture.run("update", "--yes", "--parallel-downloads", "0")
    assert result.returncode == 0, result.stdout + result.stderr
    fixture.assert_bytes("FORK")
    assert fixture.locked_entry()["resolved_commit"] == fixture.fork_sha
    assert fixture.consumer.manifest_path.read_bytes() == before_manifest


def test_replacement_remote_diamond_preserves_original_requests_and_root_anchor(
    replacement_fixture: ReplacementFixture,
) -> None:
    fixture = replacement_fixture
    factory = LocalPackageFactory(fixture.consumer.root.parent)
    remotes = [(fixture.upstream, _UPSTREAM), (fixture.fork, _FORK)]
    direct = []
    originals = {}
    requests = {}
    for name, ref in (("left", fixture.upstream_sha), ("right", "f" * 40)):
        parent = factory.create(name, dependencies=({"git": _UPSTREAM, "ref": ref},))
        originals[parent.manifest_path] = parent.manifest_path.read_bytes()
        repository = fixture.repositories.create(name, source_tree=parent.root)
        sha = fixture.repositories.commit(repository, message=f"Diamond parent {name}").sha
        remote = f"https://github.com/apm-replacement-fixture/{name}"
        remotes.append((repository, remote))
        direct.append({"git": remote, "ref": sha})
        requests[f"apm-replacement-fixture/{name}"] = ref
    fixture.environment.update(fixture.repositories.url_rewrite_subprocess_env_many(remotes))
    manifest = load_yaml(fixture.consumer.manifest_path)
    manifest["dependencies"]["apm"] = direct
    dump_yaml(manifest, fixture.consumer.manifest_path)
    fixture.replace({"path": "../local-base"})
    fixture.install()
    fixture.assert_bytes("LOCAL")
    entries = load_yaml(fixture.consumer.root / "apm.lock.yaml")["dependencies"]
    assert len(entries) == 3
    replacement = next(d for d in entries if d["repo_url"] == "apm-replacement-fixture/base")
    assert {r["parent"]: r["ref"] for r in replacement["replacement"]["requests"]} == requests
    assert {path: path.read_bytes() for path in originals} == originals
    modules = fixture.consumer.root / "apm_modules"
    assert sorted(path.relative_to(modules).as_posix() for path in modules.rglob("apm.yml")) == [
        "apm-replacement-fixture/base/apm.yml",
        "apm-replacement-fixture/left/apm.yml",
        "apm-replacement-fixture/right/apm.yml",
    ]
    before = _snapshot(fixture.consumer.root)
    fixture.replace(None)
    refused = fixture.run()
    assert refused.returncode != 0, refused.stdout + refused.stderr
    assert "incompatible immutable" in (refused.stdout + refused.stderr).lower()
    assert _snapshot(fixture.consumer.root) == before


def test_replacement_logical_cycle_fails_before_publishing_candidate(
    replacement_fixture: ReplacementFixture,
) -> None:
    fixture = replacement_fixture
    fixture.install()
    before = _snapshot(fixture.consumer.root)
    local = load_yaml(fixture.local.manifest_path)
    local["dependencies"] = {"apm": [{"git": _UPSTREAM, "ref": fixture.upstream_sha}]}
    dump_yaml(local, fixture.local.manifest_path)
    fixture.replace({"path": "../local-base"})
    refused = fixture.run()
    assert refused.returncode != 0, refused.stdout + refused.stderr
    assert "circular" in (refused.stdout + refused.stderr).lower()
    assert _snapshot(fixture.consumer.root) == before


def test_replacement_rules_in_dependency_manifest_do_not_redirect_consumer(
    replacement_fixture: ReplacementFixture,
) -> None:
    fixture = replacement_fixture
    factory = LocalPackageFactory(fixture.consumer.root.parent)
    parent = factory.create(
        "parent", dependencies=({"git": _UPSTREAM, "ref": fixture.upstream_sha},)
    )
    authored = load_yaml(parent.manifest_path)
    authored["$schema"] = _SCHEMA
    authored["replace"] = [
        {"for": {"git": _UPSTREAM}, "with": {"path": "../forbidden-consumer-local"}}
    ]
    dump_yaml(authored, parent.manifest_path)
    original = parent.manifest_path.read_bytes()
    repository = fixture.repositories.create("parent", source_tree=parent.root)
    parent_sha = fixture.repositories.commit(repository, message="Dependency-owned rule").sha
    remote = "https://github.com/apm-replacement-fixture/parent"
    fixture.environment.update(
        fixture.repositories.url_rewrite_subprocess_env_many(
            ((fixture.upstream, _UPSTREAM), (repository, remote))
        )
    )
    manifest = load_yaml(fixture.consumer.manifest_path)
    manifest["dependencies"]["apm"] = [{"git": remote, "ref": parent_sha}]
    dump_yaml(manifest, fixture.consumer.manifest_path)
    fixture.install()
    fixture.assert_bytes("UPSTREAM")
    entries = load_yaml(fixture.consumer.root / "apm.lock.yaml")["dependencies"]
    assert len(entries) == 2
    assert all(not entry.get("replacement") for entry in entries)
    assert parent.manifest_path.read_bytes() == original


@pytest.mark.parametrize("cold", [False, True], ids=["existing", "cold"])
def test_remote_parent_replacement_local_sibling_frozen_preflight(
    replacement_fixture: ReplacementFixture, cold: bool
) -> None:
    fixture = replacement_fixture
    factory = LocalPackageFactory(fixture.consumer.root.parent)
    sibling = factory.create("sibling", targets=("copilot",))
    factory.add_instruction(sibling, "sibling", _content("SIBLING"))
    local_manifest = load_yaml(fixture.local.manifest_path)
    local_manifest["dependencies"] = {"apm": [{"path": "../sibling"}]}
    dump_yaml(local_manifest, fixture.local.manifest_path)
    parent = factory.create("parent", dependencies=({"git": _UPSTREAM, "ref": "upstream"},))
    repository = fixture.repositories.create("parent", source_tree=parent.root)
    parent_sha = fixture.repositories.commit(repository, message="Remote parent").sha
    remote = "https://github.com/apm-replacement-fixture/parent"
    fixture.environment.update(
        fixture.repositories.url_rewrite_subprocess_env_many(
            ((fixture.upstream, _UPSTREAM), (repository, remote))
        )
    )
    manifest = load_yaml(fixture.consumer.manifest_path)
    manifest["dependencies"]["apm"] = [{"git": remote, "ref": parent_sha}]
    dump_yaml(manifest, fixture.consumer.manifest_path)
    fixture.replace({"path": "../local-base"})
    fixture.install()
    target = fixture.consumer.root
    if cold:
        target = target.parent / "cold"
        target.mkdir()
        shutil.copy2(fixture.consumer.manifest_path, target / "apm.yml")
        shutil.copy2(fixture.consumer.root / "apm.lock.yaml", target / "apm.lock.yaml")
    accepted = fixture.run(*_INSTALL, "--frozen", root=target)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    fixture.assert_bytes("LOCAL", root=target)
    assert (target / ".github/instructions/sibling.instructions.md").read_text() == _content(
        "SIBLING"
    )
    (sibling.root / ".apm/instructions/sibling.instructions.md").write_text(
        _content("CHANGED"), encoding="utf-8"
    )
    before = _snapshot(target)
    refused = fixture.run(*_INSTALL, "--frozen", root=target)
    assert refused.returncode != 0, refused.stdout + refused.stderr
    assert "content" in (refused.stdout + refused.stderr).lower()
    assert _snapshot(target) == before


def test_replacement_local_audit_and_outdated_are_read_only(
    replacement_fixture: ReplacementFixture,
) -> None:
    fixture = replacement_fixture
    fixture.replace({"path": "../local-base"})
    fixture.install()
    before = _snapshot(fixture.consumer.root)
    outdated = fixture.run("outdated", "--parallel-checks", "0")
    assert outdated.returncode == 0, outdated.stdout + outdated.stderr
    assert "not remotely comparable" in outdated.stdout
    assert "local-base" in outdated.stdout
    audit = fixture.run("audit", "--ci", "--no-policy")
    assert audit.returncode == 0, audit.stdout + audit.stderr
    assert _snapshot(fixture.consumer.root) == before
    fixture.local.root.rename(fixture.local.root.with_name("missing-local"))
    refused = fixture.run("audit", "--ci", "--no-policy")
    assert refused.returncode != 0, refused.stdout + refused.stderr
    assert "replacement source missing" in (refused.stdout + refused.stderr).lower()
    assert _snapshot(fixture.consumer.root) == before


def test_local_replacement_update_plans_changed_content_without_dry_run_writes(
    replacement_fixture: ReplacementFixture,
) -> None:
    fixture = replacement_fixture
    fixture.replace({"path": "../local-base"})
    fixture.install()
    before = _snapshot(fixture.consumer.root)
    previous_hash = fixture.locked_entry()["content_hash"]
    (fixture.local.root / ".apm/instructions/base.instructions.md").write_text(
        _content("UPDATED-LOCAL"), encoding="utf-8"
    )
    preview = fixture.run("update", "--dry-run", "--parallel-downloads", "0")
    assert preview.returncode == 0, preview.stdout + preview.stderr
    assert "local content" in preview.stdout.lower()
    assert _snapshot(fixture.consumer.root) == before
    updated = fixture.run("update", "--yes", "--parallel-downloads", "0")
    assert updated.returncode == 0, updated.stdout + updated.stderr
    fixture.assert_bytes("UPDATED-LOCAL")
    assert fixture.locked_entry()["content_hash"] != previous_hash


def test_partial_update_refuses_changed_replacement_table_before_mutation(
    replacement_fixture: ReplacementFixture,
) -> None:
    fixture = replacement_fixture
    fixture.install()
    before = _snapshot(fixture.consumer.root)
    fixture.replace({"path": "../local-base"})
    refused = fixture.run(
        "update", "apm-replacement-fixture/base", "--yes", "--parallel-downloads", "0"
    )
    assert refused.returncode != 0, refused.stdout + refused.stderr
    assert "complete replacement table" in " ".join(
        (refused.stdout + refused.stderr).lower().split()
    )
    assert _snapshot(fixture.consumer.root) == before


def test_existing_local_replacement_reloads_changed_child_manifest(
    replacement_fixture: ReplacementFixture,
) -> None:
    fixture = replacement_fixture
    fixture.replace({"path": "../local-base"})
    fixture.install()
    factory = LocalPackageFactory(fixture.consumer.root.parent)
    child = factory.create("child", targets=("copilot",))
    factory.add_instruction(child, "child", _content("CHILD"))
    local = load_yaml(fixture.local.manifest_path)
    local["dependencies"] = {"apm": [{"path": "../child"}]}
    dump_yaml(local, fixture.local.manifest_path)
    fixture.install()
    deployed = fixture.consumer.root / ".github/instructions/child.instructions.md"
    assert deployed.read_text() == _content("CHILD")
    entries = load_yaml(fixture.consumer.root / "apm.lock.yaml")["dependencies"]
    assert len(entries) == 2
    local.pop("dependencies")
    dump_yaml(local, fixture.local.manifest_path)
    fixture.install()
    assert not deployed.exists()
    fixture.assert_bytes("LOCAL")
    entries = load_yaml(fixture.consumer.root / "apm.lock.yaml")["dependencies"]
    assert len(entries) == 1
    assert entries[0]["repo_url"] == "apm-replacement-fixture/base"

"""Snapshot metadata and frozen version-authority contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from apm_cli.deps.git_semver_resolver import GitSemverResolution
from apm_cli.deps.installed_package import InstalledPackage
from apm_cli.deps.lockfile import LockedDependency, LockFile
from apm_cli.deps.registry.resolver import RegistryResolution
from apm_cli.install.context import InstallContext
from apm_cli.install.errors import DirectDependencyError, FrozenInstallError
from apm_cli.install.service import InstallService
from apm_cli.install.source_helpers import materialized_manifest_snapshot
from apm_cli.models.apm_package import APMPackage, PackageType
from apm_cli.models.dependency.reference import DependencyReference
from apm_cli.utils.yaml_io import dump_yaml

pytestmark = pytest.mark.component


@pytest.mark.parametrize("version", ["0.0.0", "1.1.0"])
def test_snapshot_reads_acquired_bytes_without_mutating_path_cache(
    tmp_path: Path, version: str
) -> None:
    """A fresh materialization uses current metadata and retains its source anchor."""
    manifest = tmp_path / "apm.yml"
    original_source = tmp_path / "source"
    dump_yaml({"name": "demo", "version": "1.0.0"}, manifest)
    stale = APMPackage.from_apm_yml(manifest, source_path=original_source)
    stale.source = "owner/demo"
    stale.resolved_commit = "a" * 40
    dump_yaml(
        {
            "name": "demo",
            "version": version,
            "dependencies": {"apm": ["../sibling"]},
            "x-snapshot": "current",
        },
        manifest,
    )

    snapshot = materialized_manifest_snapshot(stale, tmp_path, PackageType.APM_PACKAGE)

    assert snapshot.version == version
    assert snapshot.source_path == original_source.resolve()
    assert snapshot.package_path == tmp_path
    assert snapshot.source == "owner/demo"
    assert snapshot.resolved_commit == "a" * 40
    assert snapshot.extensions == {"x-snapshot": "current"}
    assert snapshot.get_apm_dependencies()[0].local_path == "../sibling"
    assert APMPackage.from_apm_yml(manifest, source_path=original_source) is stale
    assert stale.version == "1.0.0"


@pytest.mark.parametrize(
    "invalid",
    [
        "name: demo\n",
        "name: demo\nversion: ''\n",
        "name: demo\nversion: 2\n",
        "- not-a-mapping\n",
        "name: [\n",
    ],
)
def test_snapshot_does_not_hide_invalid_required_metadata(
    tmp_path: Path, invalid: str
) -> None:
    """A cached valid descriptor cannot conceal invalid replacement metadata."""
    manifest = tmp_path / "apm.yml"
    manifest.write_text("name: demo\nversion: 1.0.0\n", encoding="utf-8")
    stale = APMPackage.from_apm_yml(manifest)
    manifest.write_text(invalid, encoding="utf-8")

    with pytest.raises(DirectDependencyError, match="Invalid materialized manifest for demo"):
        materialized_manifest_snapshot(stale, tmp_path)


def test_snapshot_preserves_manifestless_optional_version(tmp_path: Path) -> None:
    """Formats without apm.yml retain their existing projection and absent version."""
    package = APMPackage(name="native", version="", package_path=tmp_path)

    assert materialized_manifest_snapshot(package, tmp_path) is package
    assert package.version == ""
    assert not (tmp_path / "apm.yml").exists()


def test_snapshot_preserves_legacy_synthesized_projection(tmp_path: Path) -> None:
    """Synthetic manifest rewriting and SHA stamping stay with their existing owner."""
    from apm_cli.deps.package_validator import stamp_plugin_version
    from apm_cli.deps.plugin_parser import synthesize_apm_yml_from_plugin
    from apm_cli.models.validation import validate_legacy_marketplace_plugin

    plugin_manifest = tmp_path / "plugin.json"
    plugin_manifest.write_text('{"name": "demo"}', encoding="utf-8")
    validation = validate_legacy_marketplace_plugin(tmp_path, plugin_manifest)
    assert validation.is_valid, validation.errors
    assert validation.package_type == PackageType.MARKETPLACE_PLUGIN
    package = validation.package
    assert package is not None
    stamp_plugin_version(package, validation.package_type, "abcdef0" + "a" * 33, tmp_path)
    manifest = synthesize_apm_yml_from_plugin(tmp_path, {"name": "demo"})
    baseline = manifest.read_bytes()

    snapshot = materialized_manifest_snapshot(package, tmp_path, validation.package_type)

    assert snapshot is package
    assert snapshot.version == "abcdef0"
    assert manifest.read_bytes() == baseline


def _version_context(
    tmp_path: Path,
    *,
    expected: str | None,
    actual: str | None,
    frozen: bool = True,
    repository: str = "owner/demo",
) -> InstallContext:
    """Build actual lock and materialization records without mocking the verifier."""
    reference = DependencyReference.parse(f"{repository}#release-not-a-version")
    locked = LockedDependency.from_dependency_ref(
        reference,
        resolved_commit="a" * 40,
        depth=1,
        resolved_by=None,
        package_version=expected,
    )
    lock = LockFile()
    lock.add_dependency(locked)
    return InstallContext(
        project_root=tmp_path,
        apm_dir=tmp_path / ".apm",
        frozen=frozen,
        existing_lockfile=lock,
        package_types={reference.get_unique_key(): PackageType.APM_PACKAGE.value},
        installed_packages=[
            InstalledPackage(
                reference,
                resolved_commit="a" * 40,
                depth=1,
                resolved_by=None,
                package_name="demo",
                package_version=actual,
            )
        ],
    )


@pytest.mark.parametrize("actual", ["0.0.0", "1.1.0"])
@pytest.mark.parametrize("repository", ["owner/demo", "git.example.com/owner/demo"])
def test_frozen_version_mismatch_names_dependency_and_both_versions(
    tmp_path: Path, actual: str, repository: str
) -> None:
    """Manifest-authoritative contradictions cannot pass frozen preparation."""
    ctx = _version_context(tmp_path, expected="1.0.0", actual=actual, repository=repository)
    reference = ctx.installed_packages[0].dep_ref
    key = reference.get_unique_key()
    if key != reference.get_canonical_dependency_string():
        ctx.package_types[reference.get_canonical_dependency_string()] = (
            PackageType.MARKETPLACE_PLUGIN.value
        )
    baseline = ctx.existing_lockfile.to_yaml()

    with pytest.raises(FrozenInstallError) as caught:
        InstallService.enforce_materialized_versions(ctx)

    assert caught.value.reasons == [
        f"  - {key}: locked version '1.0.0', manifest version {actual!r}"
    ]
    assert caught.value.tip is not None
    assert "without --frozen" in caught.value.tip
    assert ctx.existing_lockfile.to_yaml() == baseline


@pytest.mark.parametrize(
    ("expected", "actual", "frozen"),
    [
        ("1.1.0", "1.1.0", True),
        (None, "1.1.0", True),
        ("1.1.0", None, True),
        ("1.1.0", "", True),
        ("1.0.0", "1.1.0", False),
    ],
)
def test_optional_version_and_ordinary_recovery_remain_valid(
    tmp_path: Path, expected: str | None, actual: str | None, frozen: bool
) -> None:
    """Missing optional evidence is not a contradiction or a new version requirement."""
    ctx = _version_context(tmp_path, expected=expected, actual=actual, frozen=frozen)
    baseline = ctx.existing_lockfile.to_yaml()

    InstallService.enforce_materialized_versions(ctx)

    assert ctx.existing_lockfile.to_yaml() == baseline


def test_frozen_preserves_git_semver_resolver_authority(tmp_path: Path) -> None:
    """A semver-selected version need not equal the package manifest's version."""
    ctx = _version_context(tmp_path, expected="2.0.0", actual="1.0.0")
    locked = ctx.existing_lockfile.get_dependency("owner/demo")
    assert locked is not None
    locked.constraint = "^2.0.0"
    locked.resolved_tag = "demo-release-2.0.0"
    ctx.installed_packages[0].git_semver_resolution = GitSemverResolution(
        constraint="^2.0.0",
        resolved_version="2.0.0",
        resolved_tag="demo-release-2.0.0",
        resolved_sha="a" * 40,
        matched_pattern="demo-release-{version}",
        resolved_at="2026-10-20T00:00:00Z",
    )
    candidate = LockFile.from_installed_packages(ctx.installed_packages, None)

    InstallService.enforce_materialized_versions(ctx)

    selected = candidate.get_dependency("owner/demo")
    assert selected is not None
    assert selected.version == "2.0.0"
    assert selected.manifest_version is None
    assert locked.manifest_version is None


def test_frozen_preserves_registry_resolver_authority(tmp_path: Path) -> None:
    """Registry selection remains authoritative even when the manifest differs."""
    ctx = _version_context(tmp_path, expected="2.0.0", actual="1.0.0")
    entry = ctx.installed_packages[0]
    entry.dep_ref.source = "registry"
    entry.registry_resolution = RegistryResolution(
        resolved_url="https://registry.example.com/demo.tgz",
        resolved_hash="sha256:" + "a" * 64,
        version="2.0.0",
    )
    ctx.existing_lockfile = LockFile.from_installed_packages(ctx.installed_packages, None)
    locked = ctx.existing_lockfile.get_all_dependencies()[0]
    baseline = ctx.existing_lockfile.to_yaml()

    InstallService.enforce_materialized_versions(ctx)

    assert locked.version == "2.0.0"
    assert locked.manifest_version is None
    assert entry.package_version == "1.0.0"
    assert ctx.existing_lockfile.to_yaml() == baseline


@pytest.mark.parametrize("repository", ["owner/demo", "git.example.com/owner/demo"])
def test_frozen_does_not_reinterpret_legacy_synthesized_versions(
    tmp_path: Path, repository: str
) -> None:
    """Legacy SHA stamping is not newly treated as authored APM manifest evidence."""
    ctx = _version_context(tmp_path, expected="abcdef0", actual="0.0.0", repository=repository)
    reference = ctx.installed_packages[0].dep_ref
    key = reference.get_unique_key()
    ctx.package_types[key] = PackageType.MARKETPLACE_PLUGIN.value
    if key != reference.get_canonical_dependency_string():
        ctx.package_types[reference.get_canonical_dependency_string()] = PackageType.APM_PACKAGE.value
    baseline = ctx.existing_lockfile.to_yaml()

    InstallService.enforce_materialized_versions(ctx)

    assert ctx.existing_lockfile.to_yaml() == baseline
    assert ctx.installed_packages[0].package_version == "0.0.0"


@pytest.mark.parametrize("source", ["registry", None])
def test_locked_version_authority_does_not_infer_from_tag_spelling(source: str | None) -> None:
    """Only resolver provenance changes version authority, never the ref's spelling."""
    locked = LockedDependency(
        repo_url="owner/demo",
        source=source,
        version="1.1.0",
        resolved_ref="release-not-a-version",
    )

    assert locked.manifest_version == (None if source == "registry" else "1.1.0")

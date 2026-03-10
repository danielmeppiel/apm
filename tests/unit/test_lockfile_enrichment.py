"""Unit tests for apm_cli.bundle.lockfile_enrichment."""

import yaml

from apm_cli.bundle.lockfile_enrichment import enrich_lockfile_for_pack
from apm_cli.deps.lockfile import LockFile, LockedDependency


def _make_lockfile() -> LockFile:
    """Create a simple lockfile with one dependency."""
    lf = LockFile()
    dep = LockedDependency(
        repo_url="owner/repo",
        resolved_commit="abc123",
        version="1.0.0",
        deployed_files=[".github/agents/a.md"],
    )
    lf.add_dependency(dep)
    return lf


class TestLockfileEnrichment:
    def test_adds_pack_section(self):
        lf = _make_lockfile()
        result = enrich_lockfile_for_pack(lf, fmt="apm", target="vscode")
        parsed = yaml.safe_load(result)

        assert "pack" in parsed
        assert parsed["pack"]["format"] == "apm"
        assert parsed["pack"]["target"] == "vscode"
        assert "packed_at" in parsed["pack"]

    def test_preserves_dependencies(self):
        lf = _make_lockfile()
        result = enrich_lockfile_for_pack(lf, fmt="apm", target="all")
        parsed = yaml.safe_load(result)

        assert "dependencies" in parsed
        assert len(parsed["dependencies"]) == 1
        assert parsed["dependencies"][0]["repo_url"] == "owner/repo"
        assert parsed["dependencies"][0]["resolved_commit"] == "abc123"

    def test_preserves_lockfile_version(self):
        lf = _make_lockfile()
        result = enrich_lockfile_for_pack(lf, fmt="plugin", target="claude")
        parsed = yaml.safe_load(result)

        assert parsed["lockfile_version"] == "1"

    def test_does_not_mutate_original(self):
        lf = _make_lockfile()
        original_yaml = lf.to_yaml()

        enrich_lockfile_for_pack(lf, fmt="apm", target="all")

        assert lf.to_yaml() == original_yaml

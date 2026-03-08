"""End-to-end integration tests for the MCP lifecycle across install/update/uninstall.

Exercises the full chain: transitive MCP collection, deduplication,
stale-server removal, and lockfile MCP bookkeeping — using synthetic
package names only (no private/project-specific identifiers).
"""

import json
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from apm_cli.cli import (
    _collect_transitive_mcp_deps,
    _deduplicate_mcp_deps,
    _get_mcp_dep_names,
    _remove_stale_mcp_servers,
    _update_lockfile_mcp_servers,
)
from apm_cli.deps.lockfile import LockedDependency, LockFile


# ---------------------------------------------------------------------------
# Helpers — mirror the per-file convention used across the test suite.
# ---------------------------------------------------------------------------

def _write_apm_yml(path: Path, deps: list = None, mcp: list = None, name: str = "test-project"):
    """Write a minimal apm.yml at *path* with optional APM and MCP deps."""
    data = {"name": name, "version": "1.0.0", "dependencies": {}}
    if deps:
        data["dependencies"]["apm"] = deps
    if mcp:
        data["dependencies"]["mcp"] = mcp
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")


def _make_pkg_dir(apm_modules: Path, repo_url: str, mcp: list = None,
                  apm_deps: list = None, name: str = None, virtual_path: str = None):
    """Create a package directory under apm_modules with an apm.yml."""
    base = apm_modules / repo_url
    if virtual_path:
        base = base / virtual_path
    base.mkdir(parents=True, exist_ok=True)
    pkg_name = name or repo_url.split("/")[-1]
    data = {"name": pkg_name, "version": "1.0.0", "dependencies": {}}
    if mcp:
        data["dependencies"]["mcp"] = mcp
    if apm_deps:
        data["dependencies"]["apm"] = apm_deps
    (base / "apm.yml").write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")


def _write_lockfile(path: Path, locked_deps: list, mcp_servers: list = None):
    """Write a lockfile from LockedDependency list and optional MCP server names."""
    lf = LockFile()
    for dep in locked_deps:
        lf.add_dependency(dep)
    if mcp_servers:
        lf.mcp_servers = mcp_servers
    lf.write(path)


def _write_mcp_json(path: Path, servers: dict):
    """Write a .vscode/mcp.json file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"servers": servers}, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Scenario 1 — Selective install with transitive MCP deps
# ---------------------------------------------------------------------------
class TestSelectiveInstallTransitiveMCP:
    """When `apm install acme/squad-alpha` is requested, the lockfile-scoped
    MCP collector should find MCP servers declared by transitive deps
    of squad-alpha even though squad-alpha itself has no MCP section."""

    def setup_method(self):
        self._orig_cwd = os.getcwd()

    def teardown_method(self):
        os.chdir(self._orig_cwd)

    def test_transitive_mcp_collected_through_lockfile(self, tmp_path):
        os.chdir(tmp_path)
        apm_modules = tmp_path / "apm_modules"

        # squad-alpha has no MCP, depends on infra-cloud
        _make_pkg_dir(apm_modules, "acme/squad-alpha", apm_deps=["acme/infra-cloud"])

        # infra-cloud declares two MCP servers
        _make_pkg_dir(apm_modules, "acme/infra-cloud", mcp=[
            "ghcr.io/acme/mcp-server-alpha",
            "ghcr.io/acme/mcp-server-beta",
        ])

        # Lockfile records both packages
        lock_path = tmp_path / "apm.lock"
        _write_lockfile(lock_path, [
            LockedDependency(repo_url="acme/squad-alpha", depth=1, resolved_by="root"),
            LockedDependency(repo_url="acme/infra-cloud", depth=2, resolved_by="acme/squad-alpha"),
        ])

        result = _collect_transitive_mcp_deps(apm_modules, lock_path)
        names = [d.name for d in result]
        assert "ghcr.io/acme/mcp-server-alpha" in names
        assert "ghcr.io/acme/mcp-server-beta" in names

    def test_orphan_pkg_mcp_not_collected(self, tmp_path):
        """A package in apm_modules but NOT in the lockfile should be ignored."""
        os.chdir(tmp_path)
        apm_modules = tmp_path / "apm_modules"

        _make_pkg_dir(apm_modules, "acme/squad-alpha")
        _make_pkg_dir(apm_modules, "acme/orphan-pkg", mcp=["ghcr.io/acme/orphan-server"])

        # Only squad-alpha is locked
        lock_path = tmp_path / "apm.lock"
        _write_lockfile(lock_path, [
            LockedDependency(repo_url="acme/squad-alpha", depth=1, resolved_by="root"),
        ])

        result = _collect_transitive_mcp_deps(apm_modules, lock_path)
        names = [d.name for d in result]
        assert "ghcr.io/acme/orphan-server" not in names


# ---------------------------------------------------------------------------
# Scenario 2 — Uninstall removes transitive MCP servers
# ---------------------------------------------------------------------------
class TestUninstallRemovesTransitiveMCP:
    """After uninstalling a package, _remove_stale_mcp_servers should remove
    MCP entries that are no longer referenced by any remaining package."""

    def setup_method(self):
        self._orig_cwd = os.getcwd()

    def teardown_method(self):
        os.chdir(self._orig_cwd)

    def test_stale_servers_removed_from_mcp_json(self, tmp_path):
        os.chdir(tmp_path)

        # Pre-existing .vscode/mcp.json with servers from two packages
        mcp_json = tmp_path / ".vscode" / "mcp.json"
        _write_mcp_json(mcp_json, {
            "ghcr.io/acme/mcp-server-alpha": {"command": "npx", "args": ["alpha"]},
            "ghcr.io/acme/mcp-server-beta": {"command": "npx", "args": ["beta"]},
            "ghcr.io/acme/mcp-server-gamma": {"command": "npx", "args": ["gamma"]},
        })

        # Suppose infra-cloud (alpha + beta) was uninstalled, gamma remains.
        old_servers = {"ghcr.io/acme/mcp-server-alpha", "ghcr.io/acme/mcp-server-beta", "ghcr.io/acme/mcp-server-gamma"}
        new_servers = {"ghcr.io/acme/mcp-server-gamma"}
        stale = old_servers - new_servers

        _remove_stale_mcp_servers(stale, runtime="vscode")

        updated = json.loads(mcp_json.read_text(encoding="utf-8"))
        assert "ghcr.io/acme/mcp-server-alpha" not in updated["servers"]
        assert "ghcr.io/acme/mcp-server-beta" not in updated["servers"]
        assert "ghcr.io/acme/mcp-server-gamma" in updated["servers"]

    def test_lockfile_mcp_list_updated_after_uninstall(self, tmp_path):
        os.chdir(tmp_path)

        lock_path = tmp_path / "apm.lock"
        _write_lockfile(lock_path, [
            LockedDependency(repo_url="acme/base-lib", depth=1, resolved_by="root"),
        ], mcp_servers=["ghcr.io/acme/mcp-server-alpha", "ghcr.io/acme/mcp-server-beta"])

        # After uninstall, only beta remains
        _update_lockfile_mcp_servers({"ghcr.io/acme/mcp-server-beta"})

        reloaded = LockFile.read(lock_path)
        assert reloaded.mcp_servers == ["ghcr.io/acme/mcp-server-beta"]

    def test_lockfile_mcp_cleared_when_all_removed(self, tmp_path):
        os.chdir(tmp_path)

        lock_path = tmp_path / "apm.lock"
        _write_lockfile(lock_path, [
            LockedDependency(repo_url="acme/base-lib", depth=1, resolved_by="root"),
        ], mcp_servers=["ghcr.io/acme/mcp-server-alpha"])

        _update_lockfile_mcp_servers(set())

        reloaded = LockFile.read(lock_path)
        assert reloaded.mcp_servers == []


# ---------------------------------------------------------------------------
# Scenario 3 — Update with MCP rename (stale removed, new present)
# ---------------------------------------------------------------------------
class TestUpdateMCPRename:
    """When a dependency renames an MCP server between versions, the stale
    name must be removed and the new name must be present."""

    def setup_method(self):
        self._orig_cwd = os.getcwd()

    def teardown_method(self):
        os.chdir(self._orig_cwd)

    def test_rename_produces_correct_stale_set(self, tmp_path):
        os.chdir(tmp_path)

        # Before update: lockfile knows about the old server name
        old_mcp = {"ghcr.io/acme/mcp-server-old", "ghcr.io/acme/mcp-server-gamma"}

        # After update: the package now declares a renamed server
        apm_modules = tmp_path / "apm_modules"
        _make_pkg_dir(apm_modules, "acme/infra-cloud", mcp=[
            "ghcr.io/acme/mcp-server-new",  # renamed from mcp-server-old
            "ghcr.io/acme/mcp-server-gamma",
        ])

        lock_path = tmp_path / "apm.lock"
        _write_lockfile(lock_path, [
            LockedDependency(repo_url="acme/infra-cloud", depth=1, resolved_by="root"),
        ], mcp_servers=sorted(old_mcp))

        transitive = _collect_transitive_mcp_deps(apm_modules, lock_path)
        new_mcp = _get_mcp_dep_names(transitive)
        stale = old_mcp - new_mcp

        assert "ghcr.io/acme/mcp-server-old" in stale
        assert "ghcr.io/acme/mcp-server-new" not in stale
        assert "ghcr.io/acme/mcp-server-new" in new_mcp
        assert "ghcr.io/acme/mcp-server-gamma" in new_mcp

    def test_rename_removes_stale_from_mcp_json(self, tmp_path):
        os.chdir(tmp_path)

        mcp_json = tmp_path / ".vscode" / "mcp.json"
        _write_mcp_json(mcp_json, {
            "ghcr.io/acme/mcp-server-old": {"command": "npx", "args": ["old"]},
            "ghcr.io/acme/mcp-server-gamma": {"command": "npx", "args": ["gamma"]},
        })

        _remove_stale_mcp_servers({"ghcr.io/acme/mcp-server-old"}, runtime="vscode")

        updated = json.loads(mcp_json.read_text(encoding="utf-8"))
        assert "ghcr.io/acme/mcp-server-old" not in updated["servers"]
        assert "ghcr.io/acme/mcp-server-gamma" in updated["servers"]


# ---------------------------------------------------------------------------
# Scenario 4 — Update with MCP removal
# ---------------------------------------------------------------------------
class TestUpdateMCPRemoval:
    """When a dependency drops an MCP server entirely, the server must be
    removed from both .vscode/mcp.json and the lockfile."""

    def setup_method(self):
        self._orig_cwd = os.getcwd()

    def teardown_method(self):
        os.chdir(self._orig_cwd)

    def test_removed_mcp_detected_as_stale(self, tmp_path):
        os.chdir(tmp_path)

        old_mcp = {"ghcr.io/acme/mcp-server-alpha", "ghcr.io/acme/mcp-server-beta"}

        # After update, the package no longer declares any MCP servers
        apm_modules = tmp_path / "apm_modules"
        _make_pkg_dir(apm_modules, "acme/infra-cloud")  # no mcp arg

        lock_path = tmp_path / "apm.lock"
        _write_lockfile(lock_path, [
            LockedDependency(repo_url="acme/infra-cloud", depth=1, resolved_by="root"),
        ], mcp_servers=sorted(old_mcp))

        transitive = _collect_transitive_mcp_deps(apm_modules, lock_path)
        new_mcp = _get_mcp_dep_names(transitive)
        stale = old_mcp - new_mcp

        assert stale == old_mcp  # all old servers are stale

    def test_removal_cleans_mcp_json_and_lockfile(self, tmp_path):
        os.chdir(tmp_path)

        mcp_json = tmp_path / ".vscode" / "mcp.json"
        _write_mcp_json(mcp_json, {
            "ghcr.io/acme/mcp-server-alpha": {"command": "npx", "args": ["alpha"]},
        })

        lock_path = tmp_path / "apm.lock"
        _write_lockfile(lock_path, [
            LockedDependency(repo_url="acme/infra-cloud", depth=1, resolved_by="root"),
        ], mcp_servers=["ghcr.io/acme/mcp-server-alpha"])

        _remove_stale_mcp_servers({"ghcr.io/acme/mcp-server-alpha"}, runtime="vscode")
        _update_lockfile_mcp_servers(set())

        updated = json.loads(mcp_json.read_text(encoding="utf-8"))
        assert updated["servers"] == {}

        reloaded = LockFile.read(lock_path)
        assert reloaded.mcp_servers == []


# ---------------------------------------------------------------------------
# Scenario 5 — Deduplication across root and transitive MCP
# ---------------------------------------------------------------------------
class TestDeduplicationRootAndTransitive:
    """Root-declared MCP deps take precedence over transitive ones.
    Dedup must collapse duplicates while keeping root declarations first."""

    def test_root_overrides_transitive_duplicate(self, tmp_path):
        apm_modules = tmp_path / "apm_modules"
        _make_pkg_dir(apm_modules, "acme/infra-cloud", mcp=[
            "ghcr.io/acme/mcp-server-alpha",
        ])

        lock_path = tmp_path / "apm.lock"
        _write_lockfile(lock_path, [
            LockedDependency(repo_url="acme/infra-cloud", depth=1, resolved_by="root"),
        ])

        # Root declares alpha with extra config (dict form)
        root_mcp = [{"name": "ghcr.io/acme/mcp-server-alpha", "type": "http", "url": "https://custom.example.com"}]
        transitive_mcp = _collect_transitive_mcp_deps(apm_modules, lock_path)

        merged = _deduplicate_mcp_deps(root_mcp + transitive_mcp)
        assert len(merged) == 1
        # Root's dict form should win (first occurrence)
        assert isinstance(merged[0], dict)
        assert merged[0]["url"] == "https://custom.example.com"

    def test_dedup_preserves_distinct_servers(self, tmp_path):
        apm_modules = tmp_path / "apm_modules"
        _make_pkg_dir(apm_modules, "acme/infra-cloud", mcp=["ghcr.io/acme/mcp-server-alpha"])
        _make_pkg_dir(apm_modules, "acme/base-lib", mcp=["ghcr.io/acme/mcp-server-beta"])

        lock_path = tmp_path / "apm.lock"
        _write_lockfile(lock_path, [
            LockedDependency(repo_url="acme/infra-cloud", depth=1, resolved_by="root"),
            LockedDependency(repo_url="acme/base-lib", depth=2, resolved_by="acme/infra-cloud"),
        ])

        transitive_mcp = _collect_transitive_mcp_deps(apm_modules, lock_path)
        merged = _deduplicate_mcp_deps(transitive_mcp)
        names = [d.name for d in merged]
        assert len(names) == 2
        assert "ghcr.io/acme/mcp-server-alpha" in names
        assert "ghcr.io/acme/mcp-server-beta" in names


# ---------------------------------------------------------------------------
# Scenario 6 — Virtual-path packages in lockfile
# ---------------------------------------------------------------------------
class TestVirtualPathMCPCollection:
    """Packages with virtual_path in the lockfile must be correctly resolved
    to their subdirectory inside apm_modules."""

    def test_virtual_path_mcp_collected(self, tmp_path):
        apm_modules = tmp_path / "apm_modules"

        # Virtual package: acme/monorepo with virtual_path=packages/web-api
        _make_pkg_dir(
            apm_modules, "acme/monorepo",
            virtual_path="packages/web-api",
            name="web-api",
            mcp=["ghcr.io/acme/mcp-server-web"],
        )

        lock_path = tmp_path / "apm.lock"
        _write_lockfile(lock_path, [
            LockedDependency(
                repo_url="acme/monorepo",
                virtual_path="packages/web-api",
                is_virtual=True,
                depth=1,
                resolved_by="root",
            ),
        ])

        result = _collect_transitive_mcp_deps(apm_modules, lock_path)
        names = [d.name for d in result]
        assert "ghcr.io/acme/mcp-server-web" in names

    def test_virtual_and_non_virtual_together(self, tmp_path):
        apm_modules = tmp_path / "apm_modules"

        _make_pkg_dir(apm_modules, "acme/base-lib", mcp=["ghcr.io/acme/mcp-base"])
        _make_pkg_dir(
            apm_modules, "acme/monorepo",
            virtual_path="packages/api",
            name="api",
            mcp=["ghcr.io/acme/mcp-api"],
        )

        lock_path = tmp_path / "apm.lock"
        _write_lockfile(lock_path, [
            LockedDependency(repo_url="acme/base-lib", depth=1, resolved_by="root"),
            LockedDependency(
                repo_url="acme/monorepo",
                virtual_path="packages/api",
                is_virtual=True,
                depth=1,
                resolved_by="root",
            ),
        ])

        result = _collect_transitive_mcp_deps(apm_modules, lock_path)
        names = [d.name for d in result]
        assert len(names) == 2
        assert "ghcr.io/acme/mcp-base" in names
        assert "ghcr.io/acme/mcp-api" in names


# ---------------------------------------------------------------------------
# Scenario 7 — Self-defined MCP trust_private gating
# ---------------------------------------------------------------------------
class TestSelfDefinedMCPTrustGating:
    """Self-defined (non-registry) MCP servers from transitive packages are
    gated behind trust_private."""

    def test_self_defined_skipped_by_default(self, tmp_path):
        apm_modules = tmp_path / "apm_modules"
        _make_pkg_dir(apm_modules, "acme/infra-cloud", mcp=[
            "ghcr.io/acme/mcp-registry-server",
            {"name": "private-srv", "registry": False, "transport": "http", "url": "https://private.example.com"},
        ])

        lock_path = tmp_path / "apm.lock"
        _write_lockfile(lock_path, [
            LockedDependency(repo_url="acme/infra-cloud", depth=1, resolved_by="root"),
        ])

        result = _collect_transitive_mcp_deps(apm_modules, lock_path, trust_private=False)
        names = [d.name for d in result]
        assert "ghcr.io/acme/mcp-registry-server" in names
        assert "private-srv" not in names

    def test_self_defined_included_when_trusted(self, tmp_path):
        apm_modules = tmp_path / "apm_modules"
        _make_pkg_dir(apm_modules, "acme/infra-cloud", mcp=[
            "ghcr.io/acme/mcp-registry-server",
            {"name": "private-srv", "registry": False, "transport": "http", "url": "https://private.example.com"},
        ])

        lock_path = tmp_path / "apm.lock"
        _write_lockfile(lock_path, [
            LockedDependency(repo_url="acme/infra-cloud", depth=1, resolved_by="root"),
        ])

        result = _collect_transitive_mcp_deps(apm_modules, lock_path, trust_private=True)
        names = [d.name for d in result]
        assert "ghcr.io/acme/mcp-registry-server" in names
        assert "private-srv" in names

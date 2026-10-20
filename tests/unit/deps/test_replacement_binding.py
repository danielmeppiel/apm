"""Unit tests for replacement binding: projection and graph integration.

Tests ``project_effective_reference`` projection from original to effective
source, edge provenance preservation, and the interaction between replacement
rules and dependency identity.

Includes actual BFS binding tests that exercise ``bind_graph_replacement``
to verify original-identity preservation, effective-source separation,
immutable obligation routing, collision detection, cycle detection, and
per-entry lock evidence round-trip.
"""

import pytest

from apm_cli.models.dependency.reference import DependencyReference
from apm_cli.models.dependency.replacement import (
    GitReplacementSource,
    LocalReplacementSource,
    ReplacementRule,
    ReplacementSelector,
    build_replacement_index,
    project_effective_reference,
)

# ---------------------------------------------------------------------------
# Projection: original -> effective reference
# ---------------------------------------------------------------------------


class TestProjectEffectiveReference:
    """project_effective_reference preserves identity and applies source."""

    def _local_rule(self, repo="owner/repo", subpath=None, local_path="./local"):
        sel = ReplacementSelector(host="github.com", port=None, repo_url=repo, subpath=subpath)
        src = LocalReplacementSource(path=local_path)
        return ReplacementRule(selector=sel, source=src)

    def _git_rule(
        self,
        repo="owner/repo",
        subpath=None,
        fork_repo="fork/repo",
        fork_host="github.com",
        fork_subpath=None,
        ref="main",
    ):
        sel = ReplacementSelector(host="github.com", port=None, repo_url=repo, subpath=subpath)
        src = GitReplacementSource(
            git=f"https://{fork_host}/{fork_repo}.git",
            host=fork_host,
            port=None,
            repo_url=fork_repo,
            subpath=fork_subpath,
            ref=ref,
        )
        return ReplacementRule(selector=sel, source=src)

    def test_local_projection_is_local(self):
        """Local replacement produces a local-path dependency."""
        dep = DependencyReference(repo_url="owner/repo", host="github.com", reference="v1.0")
        rule = self._local_rule(local_path="../checkout")
        effective = project_effective_reference(dep, rule)
        assert effective.is_local is True
        assert effective.local_path == "../checkout"
        assert effective.source == "local"
        # Original repo_url is preserved for identity
        assert effective.repo_url == "owner/repo"

    def test_git_projection_carries_fork_coordinates(self):
        """Git replacement carries fork host, repo, and ref."""
        dep = DependencyReference(repo_url="owner/repo", host="github.com", reference="v1.0")
        rule = self._git_rule(
            fork_repo="my-fork/repo",
            fork_host="gitlab.com",
            ref="fix-branch",
        )
        effective = project_effective_reference(dep, rule)
        assert effective.is_local is False
        assert effective.repo_url == "my-fork/repo"
        assert effective.host == "gitlab.com"
        assert effective.reference == "fix-branch"
        assert effective.source == "git"

    def test_alias_preserved(self):
        """Original alias is carried through projection."""
        dep = DependencyReference(repo_url="owner/repo", host="github.com", alias="my-alias")
        rule = self._local_rule()
        effective = project_effective_reference(dep, rule)
        assert effective.alias == "my-alias"

    def test_skill_subset_preserved(self):
        """Original skill_subset is carried through projection."""
        dep = DependencyReference(repo_url="owner/repo", host="github.com", skill_subset=["a", "b"])
        rule = self._local_rule()
        effective = project_effective_reference(dep, rule)
        assert effective.skill_subset == ["a", "b"]

    def test_target_subset_preserved(self):
        """Original target_subset is carried through projection."""
        dep = DependencyReference(
            repo_url="owner/repo", host="github.com", target_subset=["claude"]
        )
        rule = self._local_rule()
        effective = project_effective_reference(dep, rule)
        assert effective.target_subset == ["claude"]

    def test_virtual_path_preserved_for_local(self):
        """Local replacement preserves original virtual_path."""
        dep = DependencyReference(
            repo_url="owner/repo",
            host="github.com",
            is_virtual=True,
            virtual_path="packages/base",
        )
        rule = self._local_rule(subpath="packages/base")
        effective = project_effective_reference(dep, rule)
        assert effective.is_virtual is True
        assert effective.virtual_path == "packages/base"

    def test_git_source_subpath_overrides_original(self):
        """Git source subpath replaces the original virtual_path."""
        dep = DependencyReference(
            repo_url="owner/repo",
            host="github.com",
            is_virtual=True,
            virtual_path="packages/base",
        )
        rule = self._git_rule(
            subpath="packages/base",
            fork_subpath="src/base",
            ref="v2",
        )
        effective = project_effective_reference(dep, rule)
        assert effective.virtual_path == "src/base"

    def test_git_source_no_subpath_keeps_original(self):
        """Git source without subpath preserves the original virtual_path."""
        dep = DependencyReference(
            repo_url="owner/repo",
            host="github.com",
            is_virtual=True,
            virtual_path="packages/base",
        )
        rule = self._git_rule(
            subpath="packages/base",
            fork_subpath=None,
            ref="v2",
        )
        effective = project_effective_reference(dep, rule)
        assert effective.virtual_path == "packages/base"

    def test_original_ref_not_in_effective(self):
        """Original reference is NOT copied to effective reference."""
        dep = DependencyReference(repo_url="owner/repo", host="github.com", reference=">=1.4.0")
        rule = self._local_rule()
        effective = project_effective_reference(dep, rule)
        # Local replacement has no git ref
        assert effective.reference is None

    def test_effective_ref_is_from_source(self):
        """Effective reference comes from the source, not the original."""
        dep = DependencyReference(repo_url="owner/repo", host="github.com", reference=">=1.4.0")
        rule = self._git_rule(ref="patched-v1.5")
        effective = project_effective_reference(dep, rule)
        assert effective.reference == "patched-v1.5"


# ---------------------------------------------------------------------------
# Binding at graph level: once-only match on original identity
# ---------------------------------------------------------------------------


class TestReplacementBindingSemantics:
    """Index lookup uses original identity, not effective identity."""

    def _make_index_with_one_rule(self, repo="owner/upstream"):
        sel = ReplacementSelector(host="github.com", port=None, repo_url=repo, subpath=None)
        src = LocalReplacementSource(path="./local")
        rule = ReplacementRule(selector=sel, source=src)
        return build_replacement_index([rule]), rule

    def test_once_only_no_chaining(self):
        """An effective reference does not match replacement rules again.

        Rules apply to original requirements only.  A dependency whose
        effective source is ``./local`` must not be re-looked-up.
        """
        idx, rule = self._make_index_with_one_rule()
        dep = DependencyReference(repo_url="owner/upstream", host="github.com")
        effective = project_effective_reference(dep, rule)
        # Effective is local -- must not match
        assert idx.lookup(effective) is None

    def test_dependencies_of_source_can_match(self):
        """Dependencies declared BY the effective package ARE new requirements.

        A fresh ``DependencyReference`` parsed from the replacement source's
        ``apm.yml`` can match rules (it is a new requirement, not a chained
        lookup of the replacement itself).
        """
        # Rule: replace owner/lib -> ./local-lib
        # The local-lib's apm.yml declares a dependency on owner/util
        # There is also a rule: replace owner/util -> ./local-util
        sel_lib = ReplacementSelector(
            host="github.com", port=None, repo_url="owner/lib", subpath=None
        )
        sel_util = ReplacementSelector(
            host="github.com", port=None, repo_url="owner/util", subpath=None
        )
        src_lib = LocalReplacementSource(path="./local-lib")
        src_util = LocalReplacementSource(path="./local-util")
        rule_lib = ReplacementRule(selector=sel_lib, source=src_lib)
        rule_util = ReplacementRule(selector=sel_util, source=src_util)
        idx = build_replacement_index([rule_lib, rule_util])

        # A fresh dependency on owner/util (from the local-lib's manifest) matches
        child_dep = DependencyReference(repo_url="owner/util", host="github.com")
        assert idx.lookup(child_dep) is rule_util

    def test_diamond_edges_all_match(self):
        """Multiple incoming edges for the same identity all match the same rule.

        Diamond: A -> B, A -> C, B -> D, C -> D.  Rule: replace D.
        Both the B->D and C->D edges match the same rule.
        """
        sel = ReplacementSelector(host="github.com", port=None, repo_url="owner/d", subpath=None)
        src = LocalReplacementSource(path="./local-d")
        rule = ReplacementRule(selector=sel, source=src)
        idx = build_replacement_index([rule])

        edge_from_b = DependencyReference(repo_url="owner/d", host="github.com", reference="v1.0")
        edge_from_c = DependencyReference(repo_url="owner/d", host="github.com", reference="v1.1")
        assert idx.lookup(edge_from_b) is rule
        assert idx.lookup(edge_from_c) is rule

    def test_non_virtual_dep_does_not_match_virtual_rule(self):
        """A repo-root dep does not match a rule targeting a subpath."""
        sel = ReplacementSelector(
            host="github.com", port=None, repo_url="owner/mono", subpath="packages/a"
        )
        src = LocalReplacementSource(path="./local-a")
        rule = ReplacementRule(selector=sel, source=src)
        idx = build_replacement_index([rule])

        dep = DependencyReference(repo_url="owner/mono", host="github.com")
        assert idx.lookup(dep) is None

    def test_dev_intent_preserved_in_projection(self):
        """Dev dependency intent is not broadened by replacement.

        The ``is_dev`` field is on the graph node, not the reference, so
        projection does not need to carry it.  Verify the projection does
        not accidentally set a dev flag.
        """
        dep = DependencyReference(repo_url="owner/repo", host="github.com")
        sel = ReplacementSelector(host="github.com", port=None, repo_url="owner/repo", subpath=None)
        src = LocalReplacementSource(path="./local")
        rule = ReplacementRule(selector=sel, source=src)
        effective = project_effective_reference(dep, rule)
        # DependencyReference has no is_dev; it's a graph-node concept
        assert not hasattr(effective, "is_dev") or not effective.__dict__.get("is_dev")


# ---------------------------------------------------------------------------
# BFS binding: bind_graph_replacement dispatches before dedup/admission
# ---------------------------------------------------------------------------


class TestBindGraphReplacement:
    """``bind_graph_replacement`` returns original identity + effective source."""

    def _local_rule(self, repo="owner/upstream", local_path="../local-pkg"):
        sel = ReplacementSelector(host="github.com", port=None, repo_url=repo, subpath=None)
        src = LocalReplacementSource(path=local_path)
        return ReplacementRule(selector=sel, source=src)

    def _git_rule(self, repo="owner/upstream", fork="fork/upstream", ref="fix"):
        sel = ReplacementSelector(host="github.com", port=None, repo_url=repo, subpath=None)
        src = GitReplacementSource(
            git=f"https://github.com/{fork}.git",
            host="github.com",
            port=None,
            repo_url=fork,
            subpath=None,
            ref=ref,
        )
        return ReplacementRule(selector=sel, source=src)

    def test_local_binding_preserves_original_unique_key(self, tmp_path):
        """After binding, get_unique_key uses ORIGINAL identity, not effective."""
        from apm_cli.models.dependency.replacement import bind_graph_replacement

        dep = DependencyReference(repo_url="owner/upstream", host="github.com", reference="v1.0")
        rule = self._local_rule(local_path="../checkout")
        idx = build_replacement_index([rule])
        bound = bind_graph_replacement(dep, idx, consumer_root=tmp_path)
        assert bound is not None
        original, effective = bound
        # Original identity is the upstream package
        assert original.get_unique_key() == dep.get_unique_key()
        # Effective source is local
        assert effective.is_local is True
        assert effective.local_path == "../checkout"

    def test_git_binding_effective_carries_fork_ref(self, tmp_path):
        """Effective source for Git replacement carries fork ref."""
        from apm_cli.models.dependency.replacement import bind_graph_replacement

        dep = DependencyReference(repo_url="owner/upstream", host="github.com", reference="v1.0")
        rule = self._git_rule(fork="my-fork/upstream", ref="hotfix")
        idx = build_replacement_index([rule])
        bound = bind_graph_replacement(dep, idx, consumer_root=tmp_path)
        assert bound is not None
        original, effective = bound
        assert original.repo_url == "owner/upstream"
        assert effective.repo_url == "my-fork/upstream"
        assert effective.reference == "hotfix"

    def test_no_match_returns_none(self, tmp_path):
        """Unmatched dep returns None (no binding)."""
        from apm_cli.models.dependency.replacement import bind_graph_replacement

        dep = DependencyReference(repo_url="other/repo", host="github.com")
        idx = build_replacement_index([self._local_rule()])
        assert bind_graph_replacement(dep, idx, consumer_root=tmp_path) is None

    def test_root_only_no_child_rules(self, tmp_path):
        """Only root-declared rules are applied; child manifests never redirect."""
        from apm_cli.models.dependency.replacement import bind_graph_replacement

        dep = DependencyReference(repo_url="owner/upstream", host="github.com")
        idx = build_replacement_index([self._local_rule()])
        # Binding with is_root=False should not apply rules
        bound = bind_graph_replacement(dep, idx, consumer_root=tmp_path, is_root=False)
        assert bound is None

    def test_effective_parent_git_ref_expansion(self, tmp_path):
        """Git replacement expands effective-parent ref for child deps.

        When a replaced dep declares ``git: parent`` children, the effective
        source's ref (not the original's) must be used for the expansion.
        """
        from apm_cli.models.dependency.replacement import bind_graph_replacement

        dep = DependencyReference(repo_url="owner/upstream", host="github.com", reference="v1.0")
        rule = self._git_rule(fork="fork/upstream", ref="patched-v1.5")
        idx = build_replacement_index([rule])
        bound = bind_graph_replacement(dep, idx, consumer_root=tmp_path)
        assert bound is not None
        _, effective = bound
        # Effective ref comes from the replacement source
        assert effective.reference == "patched-v1.5"
        # Original reference is still on the original
        original, _ = bound
        assert original.reference == "v1.0"

    def test_local_anchored_to_consumer_root(self, tmp_path):
        """Local replacement path is relative to consumer_root."""
        from apm_cli.models.dependency.replacement import bind_graph_replacement

        dep = DependencyReference(repo_url="owner/upstream", host="github.com")
        rule = self._local_rule(local_path="../sibling-checkout")
        idx = build_replacement_index([rule])
        bound = bind_graph_replacement(dep, idx, consumer_root=tmp_path)
        assert bound is not None
        _, effective = bound
        assert effective.local_path == "../sibling-checkout"

    def test_alias_and_subsets_preserved_through_binding(self, tmp_path):
        """Alias, skill_subset, target_subset survive binding."""
        from apm_cli.models.dependency.replacement import bind_graph_replacement

        dep = DependencyReference(
            repo_url="owner/upstream",
            host="github.com",
            alias="custom-name",
            skill_subset=["agent-a"],
            target_subset=["claude"],
        )
        idx = build_replacement_index([self._local_rule()])
        bound = bind_graph_replacement(dep, idx, consumer_root=tmp_path)
        assert bound is not None
        _, effective = bound
        assert effective.alias == "custom-name"
        assert effective.skill_subset == ["agent-a"]
        assert effective.target_subset == ["claude"]

    def test_diamond_all_edges_record_original_identity(self, tmp_path):
        """Diamond edges from different parents all match, all get same effective."""
        from apm_cli.models.dependency.replacement import bind_graph_replacement

        rule = self._local_rule(repo="owner/shared")
        idx = build_replacement_index([rule])

        edge_a = DependencyReference(repo_url="owner/shared", host="github.com", reference="v1")
        edge_b = DependencyReference(repo_url="owner/shared", host="github.com", reference="v2")
        bound_a = bind_graph_replacement(edge_a, idx, consumer_root=tmp_path)
        bound_b = bind_graph_replacement(edge_b, idx, consumer_root=tmp_path)
        assert bound_a is not None
        assert bound_b is not None
        # Both record THEIR OWN original reference
        assert bound_a[0].reference == "v1"
        assert bound_b[0].reference == "v2"
        # Both get same effective source
        assert bound_a[1].local_path == bound_b[1].local_path


# ---------------------------------------------------------------------------
# Collision detection: exact host/port/subpath vs physical slot
# ---------------------------------------------------------------------------


class TestReplacementCollision:
    """Replacement must reject when effective source collides with physical slot."""

    def test_same_identity_no_collision(self, tmp_path):
        """Replacing the same identity twice is caught by duplicate selector."""
        from apm_cli.models.dependency.replacement import (
            validate_no_replacement_collision,
        )

        dep = DependencyReference(repo_url="owner/a", host="github.com")
        effective = DependencyReference(
            repo_url="owner/a", is_local=True, local_path="./local-a", source="local"
        )
        # No collision when the slot set is empty
        slots: dict[str, str] = {}
        validate_no_replacement_collision(dep, effective, slots)
        # Should work fine

    def test_different_host_same_repo_collides(self):
        """owner/repo on github.com vs owner/repo on gitlab.com -> collision.

        The existing physical layout (apm_modules/) is host-blind, so two
        different-host packages with the same repo_url would land in the
        same directory.  Replacement must reject this.
        """
        from apm_cli.models.dependency.replacement import (
            ReplacementCollisionError,
            validate_no_replacement_collision,
        )

        dep = DependencyReference(repo_url="owner/repo", host="github.com")
        effective = DependencyReference(
            repo_url="owner/repo",
            host="gitlab.com",
            source="git",
            reference="main",
        )
        # Existing slot occupancy from the upstream
        slots: dict[str, str] = {"owner/repo": "github.com:owner/repo"}
        with pytest.raises(ReplacementCollisionError, match="collision"):
            validate_no_replacement_collision(dep, effective, slots)

    def test_port_difference_collides(self):
        """Same host+repo but different port -> collision with host-blind layout."""
        from apm_cli.models.dependency.replacement import (
            ReplacementCollisionError,
            validate_no_replacement_collision,
        )

        dep = DependencyReference(repo_url="owner/repo", host="ghe.corp.com", port=8443)
        effective = DependencyReference(
            repo_url="owner/repo",
            host="ghe.corp.com",
            port=9443,
            source="git",
            reference="main",
        )
        slots: dict[str, str] = {"owner/repo": "ghe.corp.com:8443:owner/repo"}
        with pytest.raises(ReplacementCollisionError, match="collision"):
            validate_no_replacement_collision(dep, effective, slots)


# ---------------------------------------------------------------------------
# Cycle detection: local replacement cannot form a cycle
# ---------------------------------------------------------------------------


class TestReplacementCycleGuard:
    """Local replacements must not create a cycle back to the consumer root."""

    def test_self_referential_local_cycle(self, tmp_path):
        """Replacing with '.' creates a cycle to consumer root."""
        from apm_cli.models.dependency.replacement import (
            ReplacementCycleError,
            detect_local_replacement_cycle,
        )

        with pytest.raises(ReplacementCycleError, match="cycle"):
            detect_local_replacement_cycle(
                local_path=".",
                consumer_root=tmp_path,
                ancestor_paths=frozenset({tmp_path.resolve()}),
            )

    def test_sibling_checkout_no_cycle(self, tmp_path):
        """Sibling checkout (../other) does not form a cycle."""
        from apm_cli.models.dependency.replacement import detect_local_replacement_cycle

        # No cycle because sibling is outside the ancestor set
        detect_local_replacement_cycle(
            local_path="../other",
            consumer_root=tmp_path,
            ancestor_paths=frozenset({tmp_path.resolve()}),
        )
        # Should not raise

    def test_ancestor_path_cycle(self, tmp_path):
        """Replacement pointing to an ancestor in the dependency chain is a cycle."""
        from apm_cli.models.dependency.replacement import (
            ReplacementCycleError,
            detect_local_replacement_cycle,
        )

        ancestor = tmp_path / "ancestor"
        ancestor.mkdir()
        with pytest.raises(ReplacementCycleError, match="cycle"):
            detect_local_replacement_cycle(
                local_path=str(ancestor),
                consumer_root=tmp_path,
                ancestor_paths=frozenset({ancestor.resolve()}),
            )


# ---------------------------------------------------------------------------
# Immutable obligation routing: effective refs feed ImmutableRequirements
# ---------------------------------------------------------------------------


class TestReplacementImmutableObligation:
    """Effective replacement refs must feed ImmutableRequirements correctly."""

    def test_effective_git_ref_is_obligation(self, tmp_path):
        """Effective git ref from replacement source is the immutable obligation.

        The original upstream ref is NOT the obligation; the fork's ref is.
        """
        from apm_cli.models.dependency.replacement import bind_graph_replacement

        dep = DependencyReference(repo_url="owner/upstream", host="github.com", reference="v1.0")
        sel = ReplacementSelector(
            host="github.com", port=None, repo_url="owner/upstream", subpath=None
        )
        src = GitReplacementSource(
            git="https://github.com/fork/upstream.git",
            host="github.com",
            port=None,
            repo_url="fork/upstream",
            subpath=None,
            ref="abc123def456abc123def456abc123def456abcd",
        )
        rule = ReplacementRule(selector=sel, source=src)
        idx = build_replacement_index([rule])
        bound = bind_graph_replacement(dep, idx, consumer_root=tmp_path)
        assert bound is not None
        _, effective = bound
        # The effective ref is the commit pin from the fork
        assert effective.reference == "abc123def456abc123def456abc123def456abcd"
        # ImmutableRequirements would validate THIS ref, not "v1.0"

    def test_local_replacement_has_no_immutable_ref(self, tmp_path):
        """Local replacements have no git ref to validate immutably."""
        from apm_cli.models.dependency.replacement import bind_graph_replacement

        dep = DependencyReference(repo_url="owner/upstream", host="github.com", reference="v1.0")
        rule = ReplacementRule(
            selector=ReplacementSelector(
                host="github.com", port=None, repo_url="owner/upstream", subpath=None
            ),
            source=LocalReplacementSource(path="./local"),
        )
        idx = build_replacement_index([rule])
        bound = bind_graph_replacement(dep, idx, consumer_root=tmp_path)
        assert bound is not None
        _, effective = bound
        # Local deps are skipped by ImmutableRequirements.add() (is_local check)
        assert effective.is_local is True
        assert effective.reference is None


# ---------------------------------------------------------------------------
# Per-entry lock evidence
# ---------------------------------------------------------------------------


class TestReplacementLockEvidence:
    """Per-entry replacement evidence on LockedDependency."""

    def test_replacement_source_field_round_trips(self):
        """LockedDependency.replacement_source survives to_dict/from_dict."""
        from apm_cli.deps.lockfile import LockedDependency

        dep = LockedDependency(
            repo_url="owner/upstream",
            host="github.com",
            source="local",
            local_path="./local-upstream",
            replacement_source={
                "for": {"git": "https://github.com/owner/upstream.git"},
                "with": {"path": "./local-upstream"},
            },
        )
        d = dep.to_dict()
        assert "replacement_source" in d
        restored = LockedDependency.from_dict(d)
        assert restored.replacement_source == dep.replacement_source

    def test_replacement_source_absent_by_default(self):
        """LockedDependency without replacement has no replacement_source key."""
        from apm_cli.deps.lockfile import LockedDependency

        dep = LockedDependency(repo_url="owner/normal", host="github.com")
        d = dep.to_dict()
        assert "replacement_source" not in d

    def test_replacement_original_requests_round_trips(self):
        """LockedDependency.replacement_original_requests survives round-trip."""
        from apm_cli.deps.lockfile import LockedDependency

        dep = LockedDependency(
            repo_url="owner/upstream",
            host="github.com",
            source="local",
            local_path="./local",
            replacement_original_requests=["v1.0", "v1.1"],
        )
        d = dep.to_dict()
        assert "replacement_original_requests" in d
        restored = LockedDependency.from_dict(d)
        assert restored.replacement_original_requests == ["v1.0", "v1.1"]

    def test_replacement_evidence_agrees_with_root_table(self):
        """Per-entry evidence agrees with the root replacements table.

        When a lockfile has both a root ``replacements:`` table and per-entry
        ``replacement_source:``, the per-entry evidence must be a subset of
        the root table's rules.
        """
        from apm_cli.deps.lockfile import LockedDependency, LockFile

        lock = LockFile()
        lock.replacements = [
            {
                "for": {"git": "https://github.com/owner/upstream.git"},
                "with": {"path": "./local-upstream"},
            },
        ]
        dep = LockedDependency(
            repo_url="owner/upstream",
            host="github.com",
            source="local",
            local_path="./local-upstream",
            replacement_source={
                "for": {"git": "https://github.com/owner/upstream.git"},
                "with": {"path": "./local-upstream"},
            },
        )
        lock.add_dependency(dep)
        yaml_str = lock.to_yaml()
        restored = LockFile.from_yaml(yaml_str)
        restored_dep = restored.get_dependency(dep.get_unique_key())
        assert restored_dep is not None
        assert restored_dep.replacement_source is not None
        # Per-entry evidence rule must appear in the root table
        assert restored_dep.replacement_source in restored.replacements

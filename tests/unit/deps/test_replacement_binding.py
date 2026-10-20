"""Unit tests for replacement binding: projection and graph integration.

Tests ``project_effective_reference`` projection from original to effective
source, edge provenance preservation, and the interaction between replacement
rules and dependency identity.
"""

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

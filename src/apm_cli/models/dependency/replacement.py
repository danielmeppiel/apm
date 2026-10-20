"""Root dependency replacement rules: typed model, parser, index, and projection.

A consumer root ``apm.yml`` may declare a ``replace:`` list that redirects an
upstream package identity to a local checkout or a fork throughout the transitive
graph.  The model keeps original identity distinct from the effective source so
every existing consumer (graph, lock, auth, policy, materialization) receives a
clean projection without partial host-patching or split authority.

Canonical owner of:
- ``ReplacementSelector`` coordinate tuple (host, port, repo, subpath)
- ``ReplacementSource`` effective source descriptor
- ``ReplacementRule`` validated binding of selector to source
- ``ReplacementIndex`` O(R+E) lookup by normalized coordinate
- ``parse_replace_block`` root manifest parser
- ``project_effective_reference`` projection from original to effective source

No ref, alias, wildcard, name, registry, or marketplace in the selector.
No rule chaining: rules apply once to original requirements.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...utils.github_host import is_supported_git_host
from ...utils.path_security import validate_path_segments
from .identity import (
    _DEFAULT_SCHEME_PORTS,
    normalize_package_repo_url,
)

if TYPE_CHECKING:
    from .reference import DependencyReference


class ReplacementConfigError(ValueError):
    """A replacement rule in ``apm.yml`` is malformed or ambiguous."""


# ---------------------------------------------------------------------------
# Selector: identifies the upstream package to replace
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReplacementSelector:
    """Exact normalized coordinate tuple that identifies an upstream package.

    Fields mirror the identity components of ``DependencyReference`` but are
    restricted to explicit supported Git hosts -- no registry, marketplace,
    name-only, or local selectors.

    ``host`` is always lowercase.  ``repo_url`` is normalized through the
    existing ``normalize_package_repo_url`` casing authority.  ``subpath`` is
    normalized to no leading/trailing slashes and forward slashes only.
    ``port`` is ``None`` when the URL uses the default HTTPS port (443).
    """

    host: str
    port: int | None
    repo_url: str
    subpath: str | None

    @property
    def key(self) -> tuple[str, int | None, str, str | None]:
        """Hashable lookup key for the index."""
        return (self.host, self.port, self.repo_url, self.subpath)


# ---------------------------------------------------------------------------
# Source descriptors: what the upstream identity is redirected to
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LocalReplacementSource:
    """A local filesystem checkout as the effective source.

    ``path`` is the raw string from ``apm.yml`` (e.g. ``../catalog/packages/base``).
    Anchoring to the consumer root happens at bind time, not parse time.
    """

    path: str


@dataclass(frozen=True)
class GitReplacementSource:
    """A Git fork/mirror as the effective source.

    ``ref`` is required -- replacement sources must be explicit about which
    revision they supply.  ``subpath`` is optional (fork may host the package
    at a different location).
    """

    git: str
    host: str
    port: int | None
    repo_url: str
    subpath: str | None
    ref: str


# Union of effective sources
ReplacementSource = LocalReplacementSource | GitReplacementSource


# ---------------------------------------------------------------------------
# A validated rule
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReplacementRule:
    """One validated replacement binding: ``for`` selector -> ``with`` source."""

    selector: ReplacementSelector
    source: ReplacementSource


# ---------------------------------------------------------------------------
# Index: O(R+E) lookup
# ---------------------------------------------------------------------------


class ReplacementIndex:
    """O(1) lookup of replacement rules by normalized coordinate tuple.

    Built once from the parsed ``replace:`` list.  The index rejects duplicate
    selectors at construction time so graph binding is unambiguous.
    """

    def __init__(self, rules: list[ReplacementRule]) -> None:
        self._rules = list(rules)
        self._by_key: dict[tuple[str, int | None, str, str | None], ReplacementRule] = {}
        for rule in self._rules:
            key = rule.selector.key
            if key in self._by_key:
                raise ReplacementConfigError(
                    f"Duplicate replacement selector: "
                    f"host={rule.selector.host!r} "
                    f"repo={rule.selector.repo_url!r} "
                    f"path={rule.selector.subpath!r} "
                    f"collides with an earlier rule for the same coordinates"
                )
            self._by_key[key] = rule

    def lookup(self, dep: DependencyReference) -> ReplacementRule | None:
        """Return the matching rule for *dep*, or ``None``.

        Matches on the original identity coordinates of the dependency:
        host (lowercase), port, normalized repo_url, and virtual_path (subpath).
        Local, registry, marketplace, and parent-inheritance deps never match.
        """
        if dep.is_local or dep.source == "registry" or dep.is_marketplace:
            return None
        if dep.is_parent_repo_inheritance:
            return None
        host = (dep.host or "github.com").lower()
        port = dep.port
        repo_url = normalize_package_repo_url(
            dep.repo_url,
            host=dep.host,
            source=dep.source,
            registry_prefix=dep.artifactory_prefix,
            is_local=dep.is_local,
            is_marketplace=dep.is_marketplace,
        )
        subpath = dep.virtual_path if dep.is_virtual else None
        key = (host, port, repo_url, subpath)
        return self._by_key.get(key)

    @property
    def rules(self) -> list[ReplacementRule]:
        """All rules in declaration order."""
        return list(self._rules)

    def __len__(self) -> int:
        return len(self._rules)

    def __bool__(self) -> bool:
        return bool(self._rules)

    @staticmethod
    def empty() -> ReplacementIndex:
        """Return an empty index (no replacements configured)."""
        return ReplacementIndex([])


# ---------------------------------------------------------------------------
# Parser: ``replace:`` block in root apm.yml
# ---------------------------------------------------------------------------

_SELECTOR_ALLOWED_KEYS = frozenset({"git", "path"})
_LOCAL_SOURCE_ALLOWED_KEYS = frozenset({"path"})
_GIT_SOURCE_ALLOWED_KEYS = frozenset({"git", "path", "ref"})
_RULE_ALLOWED_KEYS = frozenset({"for", "with"})


def _parse_git_url_to_coordinates(
    raw_url: str,
    *,
    context: str,
) -> tuple[str, int | None, str, str | None]:
    """Parse a Git URL into (host, port, repo_url, subpath_from_path_key).

    Reuses existing ``is_supported_git_host`` and ``normalize_package_repo_url``
    boundaries.  Only explicit ``https://`` URLs are accepted in selectors and
    Git sources -- no shorthand, no SCP, no SSH.

    Returns (host_lower, port_or_none, normalized_repo_url, None).
    The ``path`` key is handled separately by the caller.
    """
    stripped = raw_url.strip()
    lower = stripped.lower()
    if not lower.startswith("https://") and not lower.startswith("http://"):
        raise ReplacementConfigError(
            f"{context}: 'git' must be an explicit HTTPS URL "
            f"(e.g. https://github.com/owner/repo.git), got {raw_url!r}"
        )

    parsed = urllib.parse.urlparse(stripped)
    host = (parsed.hostname or "").lower()
    if not host:
        raise ReplacementConfigError(f"{context}: could not extract host from {raw_url!r}")
    if not is_supported_git_host(host):
        raise ReplacementConfigError(
            f"{context}: unsupported Git host {host!r}. "
            "Only supported Git hosting platforms are accepted."
        )
    port = parsed.port
    scheme = (parsed.scheme or "").lower()
    if port == _DEFAULT_SCHEME_PORTS.get(scheme):
        port = None

    # Extract repo path, strip .git suffix
    path_str = parsed.path.strip("/")
    if path_str.endswith(".git"):
        path_str = path_str[:-4]
    if not path_str or "/" not in path_str:
        raise ReplacementConfigError(
            f"{context}: invalid repository path in {raw_url!r}. Expected at least 'owner/repo'."
        )
    # Validate path segments
    validate_path_segments(path_str, context=f"{context} repository path")

    repo_url = normalize_package_repo_url(path_str, host=host)
    return host, port, repo_url, None


def _normalize_subpath(raw: str, *, context: str) -> str:
    """Normalize a package subpath from the ``path`` field."""
    stripped = raw.strip().replace("\\", "/").strip("/")
    if not stripped:
        raise ReplacementConfigError(f"{context}: 'path' must be a non-empty string")
    # Collapse redundant separators
    normalized = "/".join(seg for seg in stripped.split("/") if seg)
    validate_path_segments(normalized, context=f"{context} subpath")
    return normalized


def _parse_selector(raw: object, *, rule_index: int) -> ReplacementSelector:
    """Parse the ``for`` block of one replacement rule."""
    context = f"replace[{rule_index}].for"
    if not isinstance(raw, dict):
        raise ReplacementConfigError(f"{context}: expected a mapping, got {type(raw).__name__}")
    unknown = set(raw.keys()) - _SELECTOR_ALLOWED_KEYS
    if unknown:
        raise ReplacementConfigError(
            f"{context}: unknown field(s) {sorted(unknown)}. "
            f"Allowed fields: {sorted(_SELECTOR_ALLOWED_KEYS)}"
        )
    git_url = raw.get("git")
    if git_url is None:
        raise ReplacementConfigError(f"{context}: 'git' field is required")
    if not isinstance(git_url, str) or not git_url.strip():
        raise ReplacementConfigError(f"{context}: 'git' must be a non-empty string")

    host, port, repo_url, _ = _parse_git_url_to_coordinates(git_url, context=context)

    subpath: str | None = None
    raw_path = raw.get("path")
    if raw_path is not None:
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ReplacementConfigError(f"{context}: 'path' must be a non-empty string")
        subpath = _normalize_subpath(raw_path, context=context)

    return ReplacementSelector(host=host, port=port, repo_url=repo_url, subpath=subpath)


def _parse_local_source(raw: dict, *, rule_index: int) -> LocalReplacementSource:
    """Parse a local-path ``with`` block."""
    context = f"replace[{rule_index}].with"
    path_val = raw["path"]
    if not isinstance(path_val, str) or not path_val.strip():
        raise ReplacementConfigError(f"{context}: 'path' must be a non-empty string")
    path_str = path_val.strip()

    # Validate that it looks like a local path (reuse DependencyReference check)
    from .reference import DependencyReference

    if not DependencyReference.is_local_path(path_str):
        raise ReplacementConfigError(
            f"{context}: local 'path' must start with './', '../', '/', or '~/' (got {path_str!r})"
        )
    return LocalReplacementSource(path=path_str)


def _parse_git_source(raw: dict, *, rule_index: int) -> GitReplacementSource:
    """Parse a Git fork ``with`` block."""
    context = f"replace[{rule_index}].with"
    git_url = raw["git"]
    if not isinstance(git_url, str) or not git_url.strip():
        raise ReplacementConfigError(f"{context}: 'git' must be a non-empty string")

    host, port, repo_url, _ = _parse_git_url_to_coordinates(git_url, context=context)

    ref_val = raw.get("ref")
    if ref_val is None:
        raise ReplacementConfigError(
            f"{context}: Git replacement source requires an explicit 'ref' field"
        )
    if not isinstance(ref_val, str) or not ref_val.strip():
        raise ReplacementConfigError(f"{context}: 'ref' must be a non-empty string")

    subpath: str | None = None
    raw_path = raw.get("path")
    if raw_path is not None:
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ReplacementConfigError(f"{context}: 'path' must be a non-empty string")
        subpath = _normalize_subpath(raw_path, context=context)

    return GitReplacementSource(
        git=git_url.strip(),
        host=host,
        port=port,
        repo_url=repo_url,
        subpath=subpath,
        ref=ref_val.strip(),
    )


def _parse_source(raw: object, *, rule_index: int) -> ReplacementSource:
    """Parse the ``with`` block of one replacement rule."""
    context = f"replace[{rule_index}].with"
    if not isinstance(raw, dict):
        raise ReplacementConfigError(f"{context}: expected a mapping, got {type(raw).__name__}")

    has_git = "git" in raw
    has_path = "path" in raw

    if has_git and has_path and "ref" not in raw:
        # git + path without ref: ambiguous (could be local or git with subpath)
        raise ReplacementConfigError(
            f"{context}: Git replacement source requires an explicit 'ref' field"
        )

    if has_git:
        allowed = _GIT_SOURCE_ALLOWED_KEYS
        unknown = set(raw.keys()) - allowed
        if unknown:
            raise ReplacementConfigError(
                f"{context}: unknown field(s) {sorted(unknown)}. "
                f"Allowed fields for Git source: {sorted(allowed)}"
            )
        return _parse_git_source(raw, rule_index=rule_index)

    if has_path:
        unknown = set(raw.keys()) - _LOCAL_SOURCE_ALLOWED_KEYS
        if unknown:
            raise ReplacementConfigError(
                f"{context}: unknown field(s) {sorted(unknown)}. "
                f"Allowed fields for local source: {sorted(_LOCAL_SOURCE_ALLOWED_KEYS)}"
            )
        return _parse_local_source(raw, rule_index=rule_index)

    raise ReplacementConfigError(
        f"{context}: must contain either 'path' (local) or 'git' + 'ref' (Git fork)"
    )


def parse_replace_block(raw: object) -> list[ReplacementRule]:
    """Parse the top-level ``replace:`` list from a root ``apm.yml``.

    Returns a list of validated rules.  Raises ``ReplacementConfigError``
    for any structural, type, or semantic violation.

    This parser is called only for the consumer root manifest.  Dependency
    manifests may not declare ``replace:`` (enforced by the resolver, not here).
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ReplacementConfigError(f"'replace' must be a list, got {type(raw).__name__}")
    rules: list[ReplacementRule] = []
    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ReplacementConfigError(
                f"replace[{idx}]: each entry must be a mapping with 'for' and 'with' keys, "
                f"got {type(entry).__name__}"
            )
        unknown = set(entry.keys()) - _RULE_ALLOWED_KEYS
        if unknown:
            raise ReplacementConfigError(
                f"replace[{idx}]: unknown field(s) {sorted(unknown)}. "
                f"Allowed fields: {sorted(_RULE_ALLOWED_KEYS)}"
            )
        if "for" not in entry:
            raise ReplacementConfigError(f"replace[{idx}]: missing required 'for' field")
        if "with" not in entry:
            raise ReplacementConfigError(f"replace[{idx}]: missing required 'with' field")

        selector = _parse_selector(entry["for"], rule_index=idx)
        source = _parse_source(entry["with"], rule_index=idx)
        rules.append(ReplacementRule(selector=selector, source=source))
    return rules


def build_replacement_index(rules: list[ReplacementRule]) -> ReplacementIndex:
    """Build a lookup index from parsed rules; rejects duplicate selectors."""
    return ReplacementIndex(rules)


# ---------------------------------------------------------------------------
# Projection: original DependencyReference -> effective source
# ---------------------------------------------------------------------------


def project_effective_reference(
    dep: DependencyReference,
    rule: ReplacementRule,
) -> DependencyReference:
    """Return a new ``DependencyReference`` reflecting the effective source.

    The returned reference carries the replacement source coordinates while the
    caller retains the original ``dep`` for identity/provenance.  The projection
    preserves the original's alias, subset selections, and dev intent.

    For a local source, the effective reference is a local-path dependency.
    For a Git source, the effective reference carries the fork's coordinates
    and the required ref, with the original virtual_path replaced by the
    source's subpath when specified.
    """
    from .reference import DependencyReference as DepRef

    source = rule.source
    if isinstance(source, LocalReplacementSource):
        return DepRef(
            repo_url=dep.repo_url,
            is_local=True,
            local_path=source.path,
            source="local",
            # Preserve selection intent
            alias=dep.alias,
            skill_subset=dep.skill_subset,
            target_subset=dep.target_subset,
            # Keep virtual identity if the original was virtual
            is_virtual=dep.is_virtual,
            virtual_path=dep.virtual_path,
        )
    elif isinstance(source, GitReplacementSource):
        effective_subpath = source.subpath if source.subpath is not None else dep.virtual_path
        return DepRef(
            repo_url=source.repo_url,
            host=source.host,
            port=source.port,
            reference=source.ref,
            source="git",
            # Preserve selection intent
            alias=dep.alias,
            skill_subset=dep.skill_subset,
            target_subset=dep.target_subset,
            # Virtual path from source or original
            is_virtual=bool(effective_subpath),
            virtual_path=effective_subpath,
        )
    else:
        raise TypeError(f"Unknown replacement source type: {type(source)}")


# ---------------------------------------------------------------------------
# Lock-file serialization helpers
# ---------------------------------------------------------------------------


def replacement_rule_to_dict(rule: ReplacementRule) -> dict:
    """Serialize a rule for lockfile ``replacements:`` list."""
    selector_dict: dict[str, object] = {}
    sel = rule.selector
    # Reconstruct a canonical HTTPS URL from coordinates
    netloc = f"{sel.host}:{sel.port}" if sel.port else sel.host
    selector_dict["git"] = f"https://{netloc}/{sel.repo_url}.git"
    if sel.subpath:
        selector_dict["path"] = sel.subpath

    source_dict: dict[str, object] = {}
    src = rule.source
    if isinstance(src, LocalReplacementSource):
        source_dict["path"] = src.path
    elif isinstance(src, GitReplacementSource):
        source_dict["git"] = src.git
        if src.subpath:
            source_dict["path"] = src.subpath
        source_dict["ref"] = src.ref

    return {"for": selector_dict, "with": source_dict}


def replacement_rules_from_dicts(raw_list: list[dict]) -> list[ReplacementRule]:
    """Deserialize rules from a lockfile ``replacements:`` list.

    Reuses ``parse_replace_block`` for validation so lock-file rules are
    subject to the same structural checks as manifest rules.
    """
    return parse_replace_block(raw_list)

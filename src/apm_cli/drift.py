"""Pure drift-detection helpers for diff-aware ``apm install``.

These functions are stateless and side-effect-free, making them easy to test
in isolation and to reuse from multiple call sites in ``install.py`` without
duplicating logic.

Three kinds of drift are detected:

* **Ref drift** — the ``ref`` pinned in ``apm.yml`` differs from what the
  lockfile recorded as ``resolved_ref``.  This includes transitions such as
  ``None → "v1.0.0"`` (user adds a pin), ``"main" → None`` (user removes a
  pin), ``"v1.0.0" → "v2.0.0"`` (user bumps the pin), and hash-based pins
  (``None → "abc1234"`` or ``"abc1234" → "def5678"``).

* **Orphan drift** — packages present in the lockfile but absent from the
  current manifest.  Their deployed files should be removed.

* **Config drift** — an already-installed dependency's serialised configuration
  differs from the baseline stored in the lockfile.  (Currently only MCP
  servers; extendable to other integrator types.)

Scope / non-goals
-----------------
* **Hash-based refs** — handled identically to branch/tag refs: both
  ``dep_ref.reference`` and ``locked_dep.resolved_ref`` store the raw ref
  string from ``apm.yml``/lockfile respectively, so a change from
  ``"abc1234"`` to ``"def5678"`` is detected just like ``"v1.0" → "v2.0"``.

* **URL format changes** — transparent.  ``DependencyReference.parse()``
  normalises all input formats (HTTPS, SSH, shorthand, FQDN) into the same
  canonical ``repo_url`` before the lockfile stores them.  Changing
  ``owner/repo`` to ``https://github.com/owner/repo.git`` in ``apm.yml`` is a
  formatting-only change that produces the same unique key and is correctly
  treated as no drift.

* **Source/host changes** — *not* detected.  If a user changes the host of
  an otherwise identical package (e.g. adding an enterprise FQDN prefix), the
  unique key (``repo_url``, host-blind for the default host) may not change
  and ``detect_ref_change()`` will not signal a re-download.  Host-level
  changes require the user to ``apm remove`` + ``apm install`` the package, or
  use ``--update``.
"""

from __future__ import annotations

import builtins
from dataclasses import replace as _dataclass_replace
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Set

if TYPE_CHECKING:
    from apm_cli.deps.lockfile import LockFile, LockedDependency
    from apm_cli.models.apm_package import DependencyReference


# ---------------------------------------------------------------------------
# Ref drift
# ---------------------------------------------------------------------------

def detect_ref_change(
    dep_ref: "DependencyReference",
    locked_dep: "Optional[LockedDependency]",
    *,
    update_refs: bool = False,
) -> bool:
    """Return ``True`` when the manifest ref differs from the locked resolved_ref.

    Handles all transitions:

    * ref *added*  (``None`` → ``"v1.0.0"``)
    * ref *removed* (``"main"`` → ``None``)
    * ref *changed* (``"v1.0.0"`` → ``"v2.0.0"``)

    Args:
        dep_ref: The dependency as declared in the current manifest.
        locked_dep: The matching entry from the existing lockfile, or ``None``
                    when the package is brand-new (not yet in the lockfile).
        update_refs: Pass ``True`` when running in ``--update`` mode.  In that
                     mode the lockfile is intentionally ignored, so this
                     function always returns ``False`` to avoid double-action.

    Returns:
        ``True`` when a re-download is needed due to a ref change; ``False``
        when the ref is unchanged, when the package is new, or when
        ``update_refs=True``.
    """
    if update_refs:
        return False
    if locked_dep is None:
        return False  # new package — not drift, just a first install
    # Direct comparison: handles None→value, value→None, and value→value.
    # No truthiness guard on locked_dep.resolved_ref — None != "v1.0.0" is True.
    return dep_ref.reference != locked_dep.resolved_ref


# ---------------------------------------------------------------------------
# Orphan drift
# ---------------------------------------------------------------------------

def detect_orphans(
    existing_lockfile: "Optional[LockFile]",
    intended_dep_keys: builtins.set,
    *,
    only_packages: builtins.list,
) -> builtins.set:
    """Return the set of deployed file paths whose owning package left the manifest.

    Only relevant for *full* installs (``only_packages`` is empty/None).
    Partial installs (``apm install <pkg>``) preserve all existing lockfile
    entries unchanged.

    Args:
        existing_lockfile: The lockfile from the previous install, or ``None``
                           on first install.
        intended_dep_keys: Set of unique dependency keys for packages declared
                           in the updated manifest.
        only_packages: When non-empty this is a partial install — return an
                       empty set so no cleanup is performed.

    Returns:
        A set of workspace-relative path strings that belong to packages which
        are no longer in the manifest.  The caller is responsible for actually
        removing the files.
    """
    orphaned: builtins.set = builtins.set()
    if only_packages or not existing_lockfile:
        return orphaned
    for dep_key, dep in existing_lockfile.dependencies.items():
        if dep_key not in intended_dep_keys:
            orphaned.update(dep.deployed_files)
    return orphaned


# ---------------------------------------------------------------------------
# Config drift (integrator-agnostic)
# ---------------------------------------------------------------------------

def detect_config_drift(
    current_configs: Dict[str, dict],
    stored_configs: Dict[str, dict],
) -> builtins.set:
    """Return names of entries whose current config differs from the stored baseline.

    Only entries that *have* a stored baseline and whose config has *changed*
    are returned.  Brand-new entries (not in ``stored_configs``) are excluded
    because they have never been installed — they are installs, not updates.

    Args:
        current_configs: Mapping of name → current serialised config (from the
                         manifest / dependency objects).
        stored_configs: Mapping of name → previously stored config (from the
                        lockfile).

    Returns:
        A set of names (strings) whose configuration has drifted.
    """
    drifted: builtins.set = builtins.set()
    for name, current in current_configs.items():
        stored = stored_configs.get(name)
        if stored is not None and stored != current:
            drifted.add(name)
    return drifted


# ---------------------------------------------------------------------------
# Download ref construction
# ---------------------------------------------------------------------------

def build_download_ref(
    dep_ref: "DependencyReference",
    existing_lockfile: "Optional[LockFile]",
    *,
    update_refs: bool,
    ref_changed: bool,
) -> "DependencyReference":
    """Build the dependency reference passed to the package downloader.

    Returns a :class:`DependencyReference` (not a flat string) so that
    structured fields like ``virtual_path`` survive the trip to
    ``download_package()`` without a lossy ``str()`` → ``parse()``
    round-trip.  See :issue:`382`.

    Uses the locked commit SHA for reproducibility, unless:
    * ``update_refs=True`` — intentional update run; use the manifest ref.
    * ``ref_changed=True`` — the user changed the pin; use the manifest ref.

    Args:
        dep_ref: The dependency as declared in the current manifest.
        existing_lockfile: Existing lockfile, or ``None`` on first install.
        update_refs: Whether ``--update`` mode is active.
        ref_changed: Whether :func:`detect_ref_change` returned ``True`` for
                     this dependency.

    Returns:
        A :class:`DependencyReference` suitable for
        ``GitHubPackageDownloader.download_package``.
    """
    if existing_lockfile and not update_refs and not ref_changed:
        locked_dep = existing_lockfile.get_dependency(dep_ref.get_unique_key())
        if locked_dep:
            # Prefer the lockfile host over the manifest host so that
            # re-installs fetch from the exact same source (e.g. an
            # Artifactory proxy or GHE custom domain).  Without this,
            # the downloader would fall back to github.com.
            locked_host = getattr(locked_dep, "host", None)
            overrides = {}
            if isinstance(locked_host, str) and locked_host != dep_ref.host:
                overrides["host"] = locked_host
            if locked_dep.resolved_commit and locked_dep.resolved_commit != "cached":
                overrides["reference"] = locked_dep.resolved_commit
            elif not overrides.get("reference"):
                # When no commit SHA is available (e.g., Artifactory downloads),
                # preserve a pinned ref from the lockfile or manifest instead of
                # dropping the #ref portion and floating to the default branch.
                locked_ref = getattr(locked_dep, "resolved_ref", None)
                ref = locked_ref if isinstance(locked_ref, str) else dep_ref.reference
                if ref and ref != dep_ref.reference:
                    overrides["reference"] = ref
            if overrides:
                return _dataclass_replace(dep_ref, **overrides)
    return dep_ref

"""Lockfile enrichment for pack-time metadata."""

from datetime import datetime, timezone
from typing import List

from ..deps.lockfile import LockFile


# Must stay in sync with packer._TARGET_PREFIXES
_TARGET_PREFIXES = {
    "copilot": [".github/"],
    "vscode": [".github/"],
    "claude": [".claude/"],
    "cursor": [".cursor/"],
    "opencode": [".opencode/"],
    "all": [".github/", ".claude/", ".cursor/", ".opencode/"],
}


def _filter_files_by_target(deployed_files: List[str], target: str) -> List[str]:
    """Filter deployed file paths by target prefix."""
    prefixes = _TARGET_PREFIXES.get(target, _TARGET_PREFIXES["all"])
    return [f for f in deployed_files if any(f.startswith(p) for p in prefixes)]


def enrich_lockfile_for_pack(
    lockfile: LockFile,
    fmt: str,
    target: str,
) -> str:
    """Create an enriched copy of the lockfile YAML with a ``pack:`` section.

    Filters each dependency's ``deployed_files`` to only include paths
    matching the pack *target*, so the bundle lockfile is consistent with
    the files actually shipped in the bundle.

    Does NOT mutate the original *lockfile* object  -- serialises a copy and
    prepends the pack metadata.

    Args:
        lockfile: The resolved lockfile to enrich.
        fmt: Bundle format (``"apm"`` or ``"plugin"``).
        target: Effective target used for packing (``"vscode"``, ``"claude"``, ``"all"``).

    Returns:
        A YAML string with the ``pack:`` block followed by the original
        lockfile content.
    """
    import yaml

    pack_section = yaml.dump(
        {
            "pack": {
                "format": fmt,
                "target": target,
                "packed_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        default_flow_style=False,
        sort_keys=False,
    )

    # Build a filtered lockfile YAML: each dep's deployed_files is narrowed
    # to only the paths matching the pack target.
    data = yaml.safe_load(lockfile.to_yaml())
    if data and "dependencies" in data:
        for dep in data["dependencies"]:
            if "deployed_files" in dep:
                dep["deployed_files"] = _filter_files_by_target(
                    dep["deployed_files"], target
                )

    lockfile_yaml = yaml.dump(
        data, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    return pack_section + lockfile_yaml

"""Lockfile enrichment for pack-time metadata."""

from datetime import datetime, timezone
from typing import Dict, List, Tuple

from ..deps.lockfile import LockFile


# Authoritative mapping of target names to deployed-file path prefixes.
_TARGET_PREFIXES = {
    "copilot": [".github/"],
    "vscode": [".github/"],
    "claude": [".claude/"],
    "cursor": [".cursor/"],
    "opencode": [".opencode/"],
    "all": [".github/", ".claude/", ".cursor/", ".opencode/"],
}

# Cross-target path equivalences for skills/ and agents/ directories.
# Only these two directory types are semantically identical across targets;
# commands, instructions, hooks are target-specific and are NOT mapped.
#
# .github/ is the canonical interop prefix -- install always creates it, so
# all non-github targets map FROM .github/.  The vscode target additionally
# maps FROM .claude/ for the common case of Claude-first projects packing
# for Copilot.  Cursor/opencode sources are niche; if someone publishes
# skills exclusively under .cursor/, they must pack with --target cursor.
_CROSS_TARGET_MAPS: Dict[str, Dict[str, str]] = {
    "claude": {
        ".github/skills/": ".claude/skills/",
        ".github/agents/": ".claude/agents/",
    },
    "vscode": {
        ".claude/skills/": ".github/skills/",
        ".claude/agents/": ".github/agents/",
    },
    "copilot": {
        ".claude/skills/": ".github/skills/",
        ".claude/agents/": ".github/agents/",
    },
    "cursor": {
        ".github/skills/": ".cursor/skills/",
        ".github/agents/": ".cursor/agents/",
    },
    "opencode": {
        ".github/skills/": ".opencode/skills/",
        ".github/agents/": ".opencode/agents/",
    },
}


def _filter_files_by_target(
    deployed_files: List[str], target: str
) -> Tuple[List[str], Dict[str, str]]:
    """Filter deployed file paths by target prefix, with cross-target mapping.

    When files are deployed under one target prefix (e.g. ``.github/skills/``)
    but the pack target is different (e.g. ``claude``), skills and agents are
    remapped to the equivalent target path.  Commands, instructions, and hooks
    are NOT remapped -- they are target-specific.

    Returns:
        A tuple of ``(filtered_files, path_mappings)`` where *path_mappings*
        maps ``bundle_path -> disk_path`` for any file that was cross-target
        remapped.  Direct matches have no entry in the dict.
    """
    prefixes = _TARGET_PREFIXES.get(target, _TARGET_PREFIXES["all"])
    direct = [f for f in deployed_files if any(f.startswith(p) for p in prefixes)]

    path_mappings: Dict[str, str] = {}
    cross_map = _CROSS_TARGET_MAPS.get(target, {})
    if cross_map:
        direct_set = set(direct)
        for f in deployed_files:
            if f in direct_set:
                continue
            for src_prefix, dst_prefix in cross_map.items():
                if f.startswith(src_prefix):
                    mapped = dst_prefix + f[len(src_prefix):]
                    if mapped not in direct_set:
                        direct.append(mapped)
                        direct_set.add(mapped)
                        path_mappings[mapped] = f
                    break

    return direct, path_mappings


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

    # Build a filtered lockfile YAML: each dep's deployed_files is narrowed
    # to only the paths matching the pack target (with cross-target mapping).
    all_mappings: Dict[str, str] = {}
    data = yaml.safe_load(lockfile.to_yaml())
    if data and "dependencies" in data:
        for dep in data["dependencies"]:
            if "deployed_files" in dep:
                filtered, mappings = _filter_files_by_target(
                    dep["deployed_files"], target
                )
                dep["deployed_files"] = filtered
                all_mappings.update(mappings)

    # Build the pack: metadata section (after filtering so we know if mapping
    # occurred).
    pack_meta: Dict = {
        "format": fmt,
        "target": target,
        "packed_at": datetime.now(timezone.utc).isoformat(),
    }
    if all_mappings:
        # Record the source prefixes that were remapped so consumers know the
        # bundle paths differ from the original lockfile.  Use the canonical
        # prefix keys from _CROSS_TARGET_MAPS rather than reverse-engineering
        # them from file paths.
        cross_map = _CROSS_TARGET_MAPS.get(target, {})
        used_src_prefixes = set()
        for original in all_mappings.values():
            for src_prefix in cross_map:
                if original.startswith(src_prefix):
                    used_src_prefixes.add(src_prefix)
                    break
        pack_meta["mapped_from"] = sorted(used_src_prefixes)

    pack_section = yaml.dump(
        {"pack": pack_meta},
        default_flow_style=False,
        sort_keys=False,
    )

    lockfile_yaml = yaml.dump(
        data, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    return pack_section + lockfile_yaml

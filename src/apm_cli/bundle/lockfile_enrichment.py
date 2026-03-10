"""Lockfile enrichment for pack-time metadata."""

from datetime import datetime, timezone

from ..deps.lockfile import LockFile


def enrich_lockfile_for_pack(
    lockfile: LockFile,
    fmt: str,
    target: str,
) -> str:
    """Create an enriched copy of the lockfile YAML with a ``pack:`` section.

    Does NOT mutate the original *lockfile* object — serialises a copy and
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

    return pack_section + lockfile.to_yaml()

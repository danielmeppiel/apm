"""Opaque compatibility-manifest identity, selected by the canonical format registry."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from apm_cli.codex_plugins.client import CodexNativeError
from apm_cli.deps.plugin_parser import _bounded_read_json
from apm_cli.utils.path_security import ensure_path_within

CODEX_COMPAT_MANIFEST = Path(".codex-plugin/plugin.json")


@dataclass(frozen=True)
class CodexCompatibilityPlugin:
    """Native identity and declared execution surfaces, never translated MCP data."""

    name: str
    version: str
    has_mcp: bool
    has_hooks: bool


def is_codex_compatibility_manifest(root: Path, selected: Path | None) -> bool:
    """Recognize only the manifest already selected by package-format precedence."""
    return selected == root / CODEX_COMPAT_MANIFEST


def load_codex_compatibility_manifest(root: Path) -> CodexCompatibilityPlugin:
    """Read native identity without modifying package bytes or resolving native resources."""
    path = root / CODEX_COMPAT_MANIFEST
    ensure_path_within(path, root)
    if path.is_symlink() or path.parent.is_symlink():
        raise CodexNativeError("Codex compatibility manifest must not be a symbolic link.")
    data = _bounded_read_json(path)
    if not isinstance(data, dict):
        raise CodexNativeError("Codex compatibility manifest must contain a JSON object.")
    name = data.get("name")
    if not isinstance(name, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) is None:
        raise CodexNativeError("Codex compatibility plugin requires a safe native plugin name.")
    version = data.get("version", "0.0.0")
    if not isinstance(version, str) or not version.strip():
        raise CodexNativeError("Codex compatibility plugin version must be a non-empty string.")
    return CodexCompatibilityPlugin(
        name=name,
        version=version,
        has_mcp=bool(data.get("mcpServers")) or (root / ".mcp.json").is_file(),
        has_hooks=bool(data.get("hooks")) or (root / "hooks").is_dir(),
    )

"""
Parser and loader for .apmrc configuration files.

File format: flat INI-style key=value pairs with ${ENV_VAR} substitution.
Supports scoped registries (@scope:registry=url) and per-host auth tokens
(//hostname/:_authToken=value), following .npmrc conventions.

Env var substitution forms:
  ${VAR}          - substitute; leave ${VAR} as-is if unset
  ${VAR?}         - substitute; empty string if unset
  ${VAR:-default} - substitute; use 'default' if unset or empty
  ${VAR:+word}    - use 'word' if VAR is set and non-empty; else empty string
"""

from __future__ import annotations

import configparser
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APMRC_FILENAME = ".apmrc"

_SYNTHETIC_SECTION = "__apmrc__"

DEFAULT_REGISTRY = "https://api.mcp.github.com"

# Canonical key name for each recognised alias (hyphen-normalised form).
_KEY_ALIASES: dict[str, str] = {
    "registry": "registry",
    "github-token": "github-token",
    "github_token": "github-token",
    "default-client": "default-client",
    "default_client": "default-client",
    "auto-integrate": "auto-integrate",
    "auto_integrate": "auto-integrate",
    "ci-mode": "ci-mode",
    "ci_mode": "ci-mode",
}

# ---------------------------------------------------------------------------
# Env-var substitution (compiled once at import time)
# ---------------------------------------------------------------------------

# Order matters: :-/  :+ must be matched before plain ${VAR} to avoid
# partial matches on the colon.
_RE_COND = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*):([+\-])([^}]*)\}")
_RE_OPT = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\?\}")
_RE_PLAIN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

# Sentinel used to protect backslash-escaped \${ sequences during expansion.
_ESC_SENTINEL = "\x00APMRC_LITERAL_DOLLAR_BRACE\x00"

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ApmrcConfig:
    """Parsed, env-expanded contents of a single .apmrc file."""

    registry: Optional[str] = None
    github_token: Optional[str] = None
    default_client: Optional[str] = None
    auto_integrate: Optional[bool] = None
    ci_mode: Optional[bool] = None
    scoped_registries: dict[str, str] = field(default_factory=dict)
    auth_tokens: dict[str, str] = field(default_factory=dict)
    # Unrecognised keys are stored here for forward compatibility.
    raw: dict[str, str] = field(default_factory=dict)
    source_file: Optional[Path] = None


@dataclass
class MergedApmrcConfig:
    """Result of merging the full .apmrc file hierarchy."""

    registry: str = DEFAULT_REGISTRY
    github_token: Optional[str] = None
    default_client: Optional[str] = None
    auto_integrate: Optional[bool] = None
    ci_mode: bool = False
    scoped_registries: dict[str, str] = field(default_factory=dict)
    auth_tokens: dict[str, str] = field(default_factory=dict)
    # Paths of all .apmrc files that contributed to this config, in load order.
    sources: list[Path] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class ApmrcParseError(ValueError):
    """Raised when a .apmrc file cannot be parsed."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"Failed to parse {path}: {reason}")
        self.path = path
        self.reason = reason


# ---------------------------------------------------------------------------
# Env-var expansion
# ---------------------------------------------------------------------------


def expand_env_vars(value: str, env: Optional[dict[str, str]] = None) -> str:
    """
    Expand environment variable references in *value*.

    Supported forms::

        ${VAR}          substitute value of VAR; leave '${VAR}' as-is if unset
        ${VAR?}         substitute value of VAR; empty string if unset
        ${VAR:-default} substitute value of VAR; use 'default' if unset or empty
        ${VAR:+word}    use 'word' if VAR is set and non-empty; else empty string

    Args:
        value: Raw string that may contain substitution tokens.
        env:   Environment mapping to use; defaults to :data:`os.environ`.

    Returns:
        String with all recognised substitution tokens replaced.
    """
    if env is None:
        env = os.environ  # type: ignore[assignment]

    def _replace_cond(m: re.Match[str]) -> str:
        name, operator, word = m.group(1), m.group(2), m.group(3)
        var_value = env.get(name)  # type: ignore[arg-type]
        if operator == "-":
            # ${VAR:-default} — use default if unset or empty
            return var_value if var_value else word
        else:
            # ${VAR:+word} — use word only if set and non-empty
            return word if var_value else ""

    def _replace_opt(m: re.Match[str]) -> str:
        # ${VAR?} — empty string if unset
        return env.get(m.group(1), "")  # type: ignore[arg-type]

    def _replace_plain(m: re.Match[str]) -> str:
        # ${VAR} — leave as-is if unset
        name = m.group(1)
        return env.get(name, m.group(0))  # type: ignore[arg-type]

    # Protect backslash-escaped \${ sequences (npm convention).
    value = value.replace("\\${", _ESC_SENTINEL)
    # Apply substitutions in precedence order.
    value = _RE_COND.sub(_replace_cond, value)
    value = _RE_OPT.sub(_replace_opt, value)
    value = _RE_PLAIN.sub(_replace_plain, value)
    # Restore escaped sequences to literal ${.
    value = value.replace(_ESC_SENTINEL, "${")
    return value


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_raw_pairs(text: str, path: Path) -> dict[str, str]:
    """Parse flat INI text into a raw key→value dict.

    A synthetic section header is prepended so that configparser accepts the
    sectionless format.  The ``=`` character is the only delimiter, which
    preserves colons inside keys (needed for ``@scope:registry`` and
    ``//host/:_authToken``).
    """
    wrapped = f"[{_SYNTHETIC_SECTION}]\n" + text
    parser = configparser.RawConfigParser(
        delimiters=("=",),
        comment_prefixes=("#", ";"),
        strict=False,  # last duplicate key wins, matching .npmrc
        allow_no_value=True,
    )
    parser.optionxform = str  # type: ignore[method-assign]  # preserve case
    try:
        parser.read_string(wrapped)
    except configparser.Error as exc:
        raise ApmrcParseError(path, str(exc)) from exc

    return dict(parser.items(_SYNTHETIC_SECTION))


def _to_bool(value: str) -> bool:
    """Convert a string to bool using the same mapping as configparser."""
    _BOOL_STATES = {
        "true": True,
        "1": True,
        "yes": True,
        "on": True,
        "false": False,
        "0": False,
        "no": False,
        "off": False,
    }
    lowered = value.strip().lower()
    if lowered not in _BOOL_STATES:
        raise ValueError(f"Not a boolean value: {value!r}")
    return _BOOL_STATES[lowered]


_RE_SCOPED_REGISTRY = re.compile(r"^@[^:]+:registry$")
_RE_AUTH_TOKEN = re.compile(r"^//[^/].*/:_authToken$")


def _classify_raw_pairs(
    raw: dict[str, str],
    path: Path,
) -> ApmrcConfig:
    """Route each raw key→value pair into the right ApmrcConfig field."""
    cfg = ApmrcConfig(source_file=path)

    for key, value in raw.items():
        if value is None:
            # allow_no_value keys — skip silently
            continue

        canonical = _KEY_ALIASES.get(key)
        if canonical is not None:
            if canonical == "registry":
                cfg.registry = value
            elif canonical == "github-token":
                cfg.github_token = value
            elif canonical == "default-client":
                cfg.default_client = value
            elif canonical == "auto-integrate":
                try:
                    cfg.auto_integrate = _to_bool(value)
                except ValueError:
                    logger.warning(
                        "Ignoring invalid boolean for %r in %s: %r",
                        canonical,
                        path,
                        value,
                    )
            elif canonical == "ci-mode":
                try:
                    cfg.ci_mode = _to_bool(value)
                except ValueError:
                    logger.warning(
                        "Ignoring invalid boolean for %r in %s: %r",
                        canonical,
                        path,
                        value,
                    )
        elif _RE_SCOPED_REGISTRY.match(key):
            # Strip trailing ':registry' to get the bare scope.
            scope = key[: key.rfind(":registry")]
            cfg.scoped_registries[scope] = value
        elif _RE_AUTH_TOKEN.match(key):
            cfg.auth_tokens[key] = value
        else:
            logger.warning("Unknown key %r in %s (stored but unused)", key, path)
            cfg.raw[key] = value

    return cfg


# ---------------------------------------------------------------------------
# Public API: file-level
# ---------------------------------------------------------------------------


def parse_file(
    path: Path,
    env: Optional[dict[str, str]] = None,
) -> ApmrcConfig:
    """Read and parse a single .apmrc file.

    Args:
        path: Path to the .apmrc file to read.
        env:  Environment mapping for variable expansion; defaults to
              :data:`os.environ`.

    Returns:
        :class:`ApmrcConfig` populated from the file.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ApmrcParseError:   If the file is malformed.
    """
    if not path.exists():
        raise FileNotFoundError(f"No such file: {path}")

    # Warn about overly permissive file modes (tokens may be exposed).
    if sys.platform != "win32":
        try:
            mode = path.stat().st_mode
            if mode & 0o077:
                logger.warning(
                    "%s has overly permissive mode %04o. "
                    "Consider running: chmod 600 %s",
                    path,
                    mode & 0o777,
                    path,
                )
        except OSError:
            pass

    text = path.read_text(encoding="utf-8-sig")  # utf-8-sig strips BOM
    raw = _parse_raw_pairs(text, path)

    # Expand env vars in all values before classification.
    expanded = {k: expand_env_vars(v, env) for k, v in raw.items() if v is not None}
    # Restore None values for allow_no_value keys.
    for k, v in raw.items():
        if v is None:
            expanded[k] = None  # type: ignore[assignment]

    return _classify_raw_pairs(expanded, path)


# ---------------------------------------------------------------------------
# Public API: discovery
# ---------------------------------------------------------------------------


def find_global_apmrc_paths() -> list[Path]:
    """Return candidate global .apmrc paths in ascending precedence order.

    Checks the following locations, returning only those that exist:

    1. ``~/.apmrc``
    2. ``~/.apm/.apmrc``
    3. ``$XDG_CONFIG_HOME/apm/.apmrc``  (skipped on Windows)

    Returns:
        List of existing :class:`~pathlib.Path` objects, lowest precedence first.
    """
    home = Path.home()
    candidates: list[Path] = [
        home / APMRC_FILENAME,
        home / ".apm" / APMRC_FILENAME,
    ]

    if sys.platform != "win32":
        xdg = os.environ.get("XDG_CONFIG_HOME", "")
        if xdg:
            candidates.append(Path(xdg) / "apm" / APMRC_FILENAME)
        else:
            candidates.append(home / ".config" / "apm" / APMRC_FILENAME)

    return [p for p in candidates if p.exists()]


def find_project_apmrc(start: Optional[Path] = None) -> Optional[Path]:
    """Walk upward from *start* to find a project-level .apmrc.

    The walk stops at the first directory that contains ``apm.yml``,
    ``apm.yaml``, or ``.git``.  If an ``.apmrc`` is found at or before that
    boundary it is returned; otherwise ``None`` is returned.

    This prevents a global ``~/.apmrc`` from leaking into unrelated
    directories when ``apm`` is run outside a project.

    Args:
        start: Starting directory; defaults to :func:`pathlib.Path.cwd`.

    Returns:
        Path to the ``.apmrc`` file, or ``None`` if not found.
    """
    current = (start or Path.cwd()).resolve()
    _ROOT_MARKERS = {"apm.yml", "apm.yaml", ".git"}

    while True:
        apmrc = current / APMRC_FILENAME
        if apmrc.exists():
            return apmrc

        # Stop if this directory is a project root (contains a root marker).
        if any((current / marker).exists() for marker in _ROOT_MARKERS):
            return None

        parent = current.parent
        if parent == current:
            # Reached the filesystem root.
            return None
        current = parent


# ---------------------------------------------------------------------------
# Public API: hierarchy merge
# ---------------------------------------------------------------------------


def _merge_into(base: MergedApmrcConfig, layer: ApmrcConfig) -> None:
    """Apply non-None fields from *layer* onto *base* in-place."""
    if layer.registry is not None:
        base.registry = layer.registry
    if layer.github_token is not None:
        base.github_token = layer.github_token
    if layer.default_client is not None:
        base.default_client = layer.default_client
    if layer.auto_integrate is not None:
        base.auto_integrate = layer.auto_integrate
    if layer.ci_mode is not None:
        base.ci_mode = layer.ci_mode
    # Dicts are merged; later layers override earlier ones for the same key.
    base.scoped_registries.update(layer.scoped_registries)
    base.auth_tokens.update(layer.auth_tokens)
    if layer.source_file is not None:
        base.sources.append(layer.source_file)


def _load_env_overrides(
    env: Optional[dict[str, str]] = None,
) -> ApmrcConfig:
    """Build an ApmrcConfig from ``APM_CONFIG_*`` environment variables.

    Maps ``APM_CONFIG_REGISTRY=url`` to ``registry=url``, mirroring npm's
    ``npm_config_*`` convention.  Underscores in the suffix become hyphens.
    """
    if env is None:
        env = os.environ  # type: ignore[assignment]
    prefix = "APM_CONFIG_"
    raw: dict[str, str] = {}
    for key, value in env.items():  # type: ignore[union-attr]
        if key.startswith(prefix) and len(key) > len(prefix):
            config_key = key[len(prefix) :].lower().replace("_", "-")
            raw[config_key] = value
    return _classify_raw_pairs(raw, Path("<env>"))


def load_merged_config(
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
) -> MergedApmrcConfig:
    """Load and merge the full .apmrc hierarchy into one config object.

    Merge order (later sources override earlier ones):

    1. Global paths from :func:`find_global_apmrc_paths` (lowest precedence)
    2. Project .apmrc from :func:`find_project_apmrc`
    3. ``APM_CONFIG_*`` environment variables (highest precedence)

    Args:
        cwd: Working directory for project .apmrc discovery; defaults to
             :func:`pathlib.Path.cwd`.
        env: Environment mapping for variable expansion; defaults to
             :data:`os.environ`.

    Returns:
        :class:`MergedApmrcConfig` with all layers merged.
    """
    merged = MergedApmrcConfig()

    all_paths: list[Path] = list(find_global_apmrc_paths())
    project = find_project_apmrc(cwd)
    if project is not None and project not in all_paths:
        all_paths.append(project)

    for path in all_paths:
        try:
            layer = parse_file(path, env=env)
        except (ApmrcParseError, OSError):
            # Skip unreadable/malformed files gracefully.
            continue
        _merge_into(merged, layer)

    # APM_CONFIG_* env vars override all file-based config.
    env_layer = _load_env_overrides(env)
    if (
        env_layer.registry is not None
        or env_layer.github_token is not None
        or env_layer.default_client is not None
        or env_layer.auto_integrate is not None
        or env_layer.ci_mode is not None
        or env_layer.scoped_registries
        or env_layer.auth_tokens
    ):
        _merge_into(merged, env_layer)

    return merged


# ---------------------------------------------------------------------------
# Public API: convenience accessors
# ---------------------------------------------------------------------------


def get_registry_for_scope(scope: str, config: MergedApmrcConfig) -> str:
    """Return the registry URL for *scope*, falling back to the default.

    Args:
        scope:  Scope string, e.g. ``'@myorg'`` or ``'myorg'``.
        config: Merged config.

    Returns:
        Registry URL string.
    """
    key = scope if scope.startswith("@") else f"@{scope}"
    return config.scoped_registries.get(key, config.registry)


def get_auth_token_for_host(host: str, config: MergedApmrcConfig) -> Optional[str]:
    """Return the ``_authToken`` for a registry host, or ``None``.

    Looks up the ``//host/:_authToken`` key in :attr:`MergedApmrcConfig.auth_tokens`.

    Args:
        host:   Hostname, e.g. ``'myorg.pkg.github.com'``.
        config: Merged config.

    Returns:
        Auth token string, or ``None`` if not configured.
    """
    key = f"//{host}/:_authToken"
    return config.auth_tokens.get(key)


# ---------------------------------------------------------------------------
# Public API: file mutation helpers
# ---------------------------------------------------------------------------


def _safe_write(path: Path, content: str) -> None:
    """Write *content* to *path* with restrictive permissions from the start.

    On Unix the file is opened with mode ``0o600`` so there is no window
    where its contents are world-readable.  Symlinks are rejected to
    prevent write-redirection attacks.
    """
    resolved = path.resolve()
    if path.exists() and not path.is_file():
        raise OSError(f"Refusing to write to non-regular file: {path}")
    if path.is_symlink():
        raise OSError(f"Refusing to write through symlink: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        fd = os.open(str(resolved), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, content.encode("utf-8"))
        finally:
            os.close(fd)
    else:
        path.write_text(content, encoding="utf-8")


def set_value_in_file(path: Path, key: str, value: str) -> None:
    """Set or update a *key=value* pair in an .apmrc file.

    If *key* already exists, its line is replaced in-place.  Otherwise the
    pair is appended.  The file is created with mode ``0o600`` to prevent
    token exposure.  Symlinks are rejected.

    Args:
        path:  Path to the .apmrc file (created if it does not exist).
        key:   Configuration key (e.g. ``'registry'``, ``'@scope:registry'``).
        value: Value to set.

    Raises:
        OSError: If *path* is a symlink or non-regular file.
    """
    lines: list[str] = []
    found = False
    if path.exists() and path.is_file() and not path.is_symlink():
        lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if (
                stripped.startswith("#")
                or stripped.startswith(";")
                or "=" not in stripped
            ):
                continue
            line_key = stripped.split("=", 1)[0].strip()
            if line_key == key:
                lines[i] = f"{key}={value}\n"
                found = True
                break
    if not found:
        lines.append(f"{key}={value}\n")
    _safe_write(path, "".join(lines))


def delete_value_from_file(path: Path, key: str) -> bool:
    """Remove *key* from an .apmrc file.

    Args:
        path: Path to the .apmrc file.
        key:  Configuration key to remove.

    Returns:
        ``True`` if the key was found and removed, ``False`` otherwise.

    Raises:
        OSError: If *path* is a symlink.
    """
    if not path.exists():
        return False
    if path.is_symlink():
        raise OSError(f"Refusing to modify symlink: {path}")
    lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    new_lines: list[str] = []
    found = False
    for line in lines:
        stripped = line.lstrip()
        if (
            not stripped.startswith("#")
            and not stripped.startswith(";")
            and "=" in stripped
        ):
            line_key = stripped.split("=", 1)[0].strip()
            if line_key == key:
                found = True
                continue
        new_lines.append(line)
    if found:
        _safe_write(path, "".join(new_lines))
    return found


def get_value_from_merged(key: str, config: MergedApmrcConfig) -> Optional[str]:
    """Look up any key from a :class:`MergedApmrcConfig`.

    Handles plain keys, scoped registries (``@scope:registry``), and
    auth token keys (``//host/:_authToken``).

    Args:
        key:    Configuration key to look up.
        config: Merged configuration object.

    Returns:
        String representation of the value, or ``None`` if not set.
    """
    # Scoped registry
    if _RE_SCOPED_REGISTRY.match(key):
        scope = key[: key.rfind(":registry")]
        return config.scoped_registries.get(scope)
    # Auth token
    if _RE_AUTH_TOKEN.match(key):
        return config.auth_tokens.get(key)
    # Plain key — map through aliases
    canonical = _KEY_ALIASES.get(key, key)
    _FIELD_MAP: dict[str, str] = {
        "registry": "registry",
        "github-token": "github_token",
        "default-client": "default_client",
        "auto-integrate": "auto_integrate",
        "ci-mode": "ci_mode",
    }
    attr = _FIELD_MAP.get(canonical)
    if attr:
        val = getattr(config, attr, None)
        return str(val) if val is not None else None
    return None

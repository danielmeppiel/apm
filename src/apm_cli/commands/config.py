"""APM config command group."""

import builtins
import sys
from pathlib import Path

import click

from ..constants import APM_YML_FILENAME
from ..core.command_logger import CommandLogger
from ..version import get_version
from ._helpers import HIGHLIGHT, RESET, _get_console, _load_apm_config

# Restore builtin since a subcommand is named ``set``
set = builtins.set


@click.group(help="Configure APM CLI", invoke_without_command=True)
@click.pass_context
def config(ctx):
    """Configure APM CLI settings."""
    # If no subcommand, show current configuration
    if ctx.invoked_subcommand is None:
        logger = CommandLogger("config")
        try:
            # Lazy import rich table
            from rich.table import Table  # type: ignore

            console = _get_console()
            # Create configuration display
            config_table = Table(
                title="Current APM Configuration",
                show_header=True,
                header_style="bold cyan",
            )
            config_table.add_column("Category", style="bold yellow", min_width=12)
            config_table.add_column("Setting", style="white", min_width=15)
            config_table.add_column("Value", style="cyan")

            # Show apm.yml if in project
            if Path(APM_YML_FILENAME).exists():
                apm_config = _load_apm_config()
                config_table.add_row(
                    "Project", "Name", apm_config.get("name", "Unknown")
                )
                config_table.add_row(
                    "", "Version", apm_config.get("version", "Unknown")
                )
                config_table.add_row(
                    "", "Entrypoint", apm_config.get("entrypoint", "None")
                )
                config_table.add_row(
                    "",
                    "MCP Dependencies",
                    str(len(apm_config.get("dependencies", {}).get("mcp", []))),
                )

                # Show compilation configuration
                compilation_config = apm_config.get("compilation", {})
                if compilation_config:
                    config_table.add_row(
                        "Compilation",
                        "Output",
                        compilation_config.get("output", "AGENTS.md"),
                    )
                    config_table.add_row(
                        "",
                        "Chatmode",
                        compilation_config.get("chatmode", "auto-detect"),
                    )
                    config_table.add_row(
                        "",
                        "Resolve Links",
                        str(compilation_config.get("resolve_links", True)),
                    )
                else:
                    config_table.add_row(
                        "Compilation", "Status", "Using defaults (no config)"
                    )
            else:
                config_table.add_row(
                    "Project", "Status", "Not in an APM project directory"
                )

            config_table.add_row("Global", "APM CLI Version", get_version())

            console.print(config_table)

        except (ImportError, NameError):
            # Fallback display
            logger.progress("Current APM Configuration:")

            if Path(APM_YML_FILENAME).exists():
                apm_config = _load_apm_config()
                click.echo(f"\n{HIGHLIGHT}Project (apm.yml):{RESET}")
                click.echo(f"  Name: {apm_config.get('name', 'Unknown')}")
                click.echo(f"  Version: {apm_config.get('version', 'Unknown')}")
                click.echo(f"  Entrypoint: {apm_config.get('entrypoint', 'None')}")
                click.echo(
                    f"  MCP Dependencies: {len(apm_config.get('dependencies', {}).get('mcp', []))}"
                )
            else:
                logger.progress("Not in an APM project directory")

            click.echo(f"\n{HIGHLIGHT}Global:{RESET}")
            click.echo(f"  APM CLI Version: {get_version()}")


_SENSITIVE_KEY_PATTERNS = {"github-token", "github_token"}
_SENSITIVE_KEY_SUFFIXES = (":_authToken", ":_password", ":_auth")


def _is_sensitive_key(key: str) -> bool:
    """Return True if *key* contains auth credentials."""
    if key in _SENSITIVE_KEY_PATTERNS:
        return True
    return any(key.endswith(s) for s in _SENSITIVE_KEY_SUFFIXES)


def _resolve_apmrc_path(is_global: bool) -> Path:
    """Return the target .apmrc path for set/delete operations."""
    if is_global:
        target = Path.home() / ".apm" / ".apmrc"
        target.parent.mkdir(parents=True, exist_ok=True)
        return target
    from ..apmrc import find_project_apmrc

    return find_project_apmrc() or Path.cwd() / ".apmrc"


@config.command(help="Set a configuration value")
@click.argument("key")
@click.argument("value")
@click.option(
    "--global",
    "is_global",
    is_flag=True,
    help="Write to global ~/.apm/.apmrc instead of the project file.",
)
def set(key, value, is_global):
    """Set a configuration value in .apmrc.

    Examples:
        apm config set registry https://custom.registry.io
        apm config set auto-integrate false
        apm config set github-token ghp_xxxx --global
    """
    import re

    from ..apmrc import set_value_in_file
    from ..config import _invalidate_config_cache, set_auto_integrate

    logger = CommandLogger("config set")

    # Validate key format to prevent injection via crafted key names.
    if not re.match(r"^[@a-zA-Z0-9/_][a-zA-Z0-9_./:_-]*$", key):
        logger.error(f"Invalid key format: '{key}'")
        sys.exit(1)

    target = _resolve_apmrc_path(is_global)
    set_value_in_file(target, key, value)
    _invalidate_config_cache()

    # Backward compat: also write auto-integrate to config.json.
    if key == "auto-integrate":
        if value.lower() in ("true", "1", "yes"):
            set_auto_integrate(True)
        elif value.lower() in ("false", "0", "no"):
            set_auto_integrate(False)

    logger.success(f"Set {key} in {target}")


@config.command(help="Get a configuration value")
@click.argument("key", required=False)
def get(key):
    """Get a configuration value from the merged .apmrc hierarchy.

    Examples:
        apm config get registry
        apm config get auto-integrate
        apm config get               # show all
    """
    from ..apmrc import get_value_from_merged, load_merged_config
    from ..config import get_config

    logger = CommandLogger("config get")
    merged = load_merged_config()
    if key:
        if _is_sensitive_key(key):
            logger.error(
                f"Key '{key}' is protected. "
                "Use 'apm config show-rc' to see masked values."
            )
            sys.exit(1)
        value = get_value_from_merged(key, merged)
        if value is not None:
            click.echo(f"{key}={value}")
        else:
            # Fall back to config.json for backward compat.
            config_data = get_config()
            json_key = key.replace("-", "_")
            if json_key in config_data:
                click.echo(f"{key}={config_data[json_key]}")
            else:
                logger.error(f"Key '{key}' is not set")
                sys.exit(1)
    else:
        # Show all config from both sources.
        config_data = get_config()
        logger.progress("APM Configuration:")
        for k, v in config_data.items():
            display_key = k.replace("_", "-")
            click.echo(f"  {display_key}={v}")


@config.command(help="Delete a configuration key from .apmrc")
@click.argument("key")
@click.option(
    "--global",
    "is_global",
    is_flag=True,
    help="Delete from global ~/.apm/.apmrc instead of the project file.",
)
def delete(key, is_global):
    """Remove a key from an .apmrc file.

    Examples:
        apm config delete registry
        apm config delete github-token --global
    """
    from ..apmrc import delete_value_from_file
    from ..config import _invalidate_config_cache

    logger = CommandLogger("config delete")
    target = _resolve_apmrc_path(is_global)
    if delete_value_from_file(target, key):
        _invalidate_config_cache()
        logger.success(f"Deleted {key} from {target}")
    else:
        logger.error(f"Key '{key}' not found in {target}")
        sys.exit(1)


@config.command("show-rc", help="Print all .apmrc configuration values")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def show_rc(as_json):
    """Print all .apmrc configuration values across all loaded files."""
    import json as _json

    from ..apmrc import load_merged_config

    merged = load_merged_config()

    def _mask(value):
        return "***" if value else None

    if as_json:
        data = {
            "registry": merged.registry,
            "github_token": _mask(merged.github_token),
            "default_client": merged.default_client,
            "auto_integrate": merged.auto_integrate,
            "ci_mode": merged.ci_mode,
            "scoped_registries": merged.scoped_registries,
            "auth_tokens": {k: "***" for k in merged.auth_tokens},
            "sources": [str(s) for s in merged.sources],
        }
        click.echo(_json.dumps(data, indent=2))
        return

    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(
            title=".apmrc configuration", show_header=True, header_style="bold cyan"
        )
        table.add_column("Key", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        rows = [
            ("registry", merged.registry),
            ("github-token", _mask(merged.github_token)),
            ("default-client", merged.default_client),
            (
                "auto-integrate",
                (
                    str(merged.auto_integrate)
                    if merged.auto_integrate is not None
                    else None
                ),
            ),
            ("ci-mode", str(merged.ci_mode) if merged.ci_mode else None),
        ]
        for k, v in rows:
            if v is not None:
                table.add_row(k, v)
        for scope, url in merged.scoped_registries.items():
            table.add_row(f"{scope}:registry", url)
        for host_key in merged.auth_tokens:
            table.add_row(host_key, "***")

        console.print(table)
        if merged.sources:
            console.print()
            console.print("[dim]Loaded from (lowest → highest precedence):[/dim]")
            for src in merged.sources:
                console.print(f"  [dim]{src}[/dim]")
    except ImportError:
        for key, value in [
            ("registry", merged.registry),
            ("github-token", _mask(merged.github_token)),
            ("default-client", merged.default_client),
        ]:
            if value is not None:
                click.echo(f"{key}={value}")
        for scope, url in merged.scoped_registries.items():
            click.echo(f"{scope}:registry={url}")
        for host_key in merged.auth_tokens:
            click.echo(f"{host_key}=***")


@config.command(
    "which-rc", help="Show which .apmrc files are loaded and their precedence"
)
def which_rc():
    """Show which .apmrc files are loaded and their precedence order."""
    from ..apmrc import find_global_apmrc_paths, find_project_apmrc

    global_paths = find_global_apmrc_paths()
    project_path = find_project_apmrc()
    all_paths = list(global_paths)
    if project_path is not None and project_path not in all_paths:
        all_paths.append(project_path)

    if not all_paths:
        click.echo("No .apmrc files found.")
        return

    for i, p in enumerate(all_paths, 1):
        label = "project" if p == project_path else "global"
        click.echo(f"  {i}. [{label}] {p}")


_INIT_RC_TEMPLATE = """\
# .apmrc — Agent Package Manager configuration
# https://github.com/microsoft/apm/docs/apmrc.md
#
# Environment variable substitution:
#   ${VAR}          — use env var; leave '${VAR}' as-is if unset
#   ${VAR?}         — use env var; empty string if unset
#   ${VAR:-default} — use env var; fall back to 'default' if unset/empty
#   ${VAR:+word}    — use 'word' only if VAR is set and non-empty
#
# See docs/examples/.apmrc for a fully-annotated example.

# registry=https://api.mcp.github.com
# github-token=${GITHUB_APM_PAT}
# @myorg:registry=https://myorg.pkg.github.com
# //myorg.pkg.github.com/:_authToken=${MYORG_REGISTRY_TOKEN}
# default-client=claude
# auto-integrate=true
# ci-mode=${CI:+true}
"""


@config.command("init-rc", help="Scaffold a .apmrc file with commented-out defaults")
@click.option(
    "--global",
    "is_global",
    is_flag=True,
    help="Write to ~/.apm/.apmrc instead of the current directory.",
)
@click.option("--force", is_flag=True, help="Overwrite an existing file.")
def init_rc(is_global, force):
    """Scaffold a .apmrc file with commented-out defaults."""
    if is_global:
        target = Path.home() / ".apm" / ".apmrc"
        target.parent.mkdir(parents=True, exist_ok=True)
    else:
        target = Path.cwd() / ".apmrc"

    if target.exists() and not force:
        click.echo(f"{target} already exists. Use --force to overwrite.", err=True)
        sys.exit(1)

    from ..apmrc import _safe_write

    _safe_write(target, _INIT_RC_TEMPLATE)
    click.echo(f"Created {target}")


@config.command("edit", help="Open .apmrc in your editor")
@click.option(
    "--global",
    "is_global",
    is_flag=True,
    help="Edit global ~/.apm/.apmrc instead of the project file.",
)
def edit(is_global):
    """Open .apmrc in $EDITOR or $VISUAL."""
    import os as _os
    import subprocess

    from ..apmrc import find_project_apmrc

    editor = _os.environ.get("EDITOR", _os.environ.get("VISUAL", "vi"))
    if is_global:
        target = Path.home() / ".apm" / ".apmrc"
        target.parent.mkdir(parents=True, exist_ok=True)
    else:
        target = find_project_apmrc() or Path.cwd() / ".apmrc"
    subprocess.run([editor, str(target)])

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

_BOOLEAN_TRUE_VALUES = {"true", "1", "yes"}
_BOOLEAN_FALSE_VALUES = {"false", "0", "no"}
_CONFIG_KEY_DISPLAY_NAMES = {
    "auto_integrate": "auto-integrate",
    "allow_insecure": "allow-insecure",
}


def _parse_bool_value(value: str) -> bool:
    """Parse a CLI boolean value."""
    normalized = value.strip().lower()
    if normalized in _BOOLEAN_TRUE_VALUES:
        return True
    if normalized in _BOOLEAN_FALSE_VALUES:
        return False
    raise ValueError(f"Invalid value '{value}'. Use 'true' or 'false'.")


def _get_config_setters():
    """Return config setters keyed by CLI option name."""
    from ..config import set_auto_integrate, set_allow_insecure

    return {
        "auto-integrate": (set_auto_integrate, "Auto-integration"),
        "allow-insecure": (set_allow_insecure, "Allow-insecure"),
    }


def _get_config_getters():
    """Return config getters keyed by CLI option name."""
    from ..config import get_auto_integrate, get_allow_insecure

    return {
        "auto-integrate": get_auto_integrate,
        "allow-insecure": get_allow_insecure,
    }


def _valid_config_keys() -> str:
    """Return valid config keys for messages."""
    return ", ".join(_get_config_getters().keys())


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


@config.command(help="Set a configuration value")
@click.argument("key")
@click.argument("value")
def set(key, value):
    """Set a configuration value.

    Examples:
        apm config set auto-integrate false
        apm config set auto-integrate true
        apm config set allow-insecure true
    """
    logger = CommandLogger("config set")
    setters = _get_config_setters()
    config_entry = setters.get(key)
    if config_entry is None:
        logger.error(f"Unknown configuration key: '{key}'")
        logger.progress(f"Valid keys: {_valid_config_keys()}")
        logger.progress(
            "This error may indicate a bug in command routing. Please report this issue."
        )
        sys.exit(1)

    try:
        enabled = _parse_bool_value(value)
    except ValueError as exc:
        logger.error(str(exc))
        sys.exit(1)

    setter, label = config_entry
    setter(enabled)
    if enabled:
        logger.success(f"{label} enabled")
    else:
        logger.success(f"{label} disabled")


@config.command(help="Get a configuration value")
@click.argument("key", required=False)
def get(key):
    """Get a configuration value or show all configuration.

    Examples:
        apm config get auto-integrate
        apm config get allow-insecure
        apm config get
    """
    from ..config import get_config

    logger = CommandLogger("config get")
    getters = _get_config_getters()
    if key:
        getter = getters.get(key)
        if getter is None:
            logger.error(f"Unknown configuration key: '{key}'")
            logger.progress(f"Valid keys: {_valid_config_keys()}")
            logger.progress(
                "This error may indicate a bug in command routing. Please report this issue."
            )
            sys.exit(1)
        value = getter()
        click.echo(f"{key}: {value}")
    else:
        # Show all config
        config_data = get_config()
        logger.progress("APM Configuration:")
        for k, v in config_data.items():
            display_key = _CONFIG_KEY_DISPLAY_NAMES.get(k, k)
            click.echo(f"  {display_key}: {v}")

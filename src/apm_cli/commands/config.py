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


@config.command(help="Set a configuration value")
@click.argument("key")
@click.argument("value")
def set(key, value):
    """Set a configuration value.

    Examples:
        apm config set auto-integrate false
        apm config set auto-integrate true
    """
    from ..config import set_auto_integrate

    logger = CommandLogger("config set")
    if key == "auto-integrate":
        if value.lower() in ["true", "1", "yes"]:
            set_auto_integrate(True)
            logger.success("Auto-integration enabled")
        elif value.lower() in ["false", "0", "no"]:
            set_auto_integrate(False)
            logger.success("Auto-integration disabled")
        else:
            logger.error(f"Invalid value '{value}'. Use 'true' or 'false'.")
            sys.exit(1)
    else:
        logger.error(f"Unknown configuration key: '{key}'")
        logger.progress("Valid keys: auto-integrate")
        logger.progress(
            "This error may indicate a bug in command routing. Please report this issue."
        )
        sys.exit(1)


@config.command(help="Get a configuration value")
@click.argument("key", required=False)
def get(key):
    """Get a configuration value or show all configuration.

    Examples:
        apm config get auto-integrate
        apm config get
    """
    from ..config import get_auto_integrate, get_config

    logger = CommandLogger("config get")
    if key:
        if key == "auto-integrate":
            value = get_auto_integrate()
            click.echo(f"auto-integrate: {value}")
        else:
            logger.error(f"Unknown configuration key: '{key}'")
            logger.progress("Valid keys: auto-integrate")
            logger.progress(
                "This error may indicate a bug in command routing. Please report this issue."
            )
            sys.exit(1)
    else:
        # Show all config
        config_data = get_config()
        logger.progress("APM Configuration:")
        for k, v in config_data.items():
            # Map internal keys to user-friendly names
            if k == "auto_integrate":
                click.echo(f"  auto-integrate: {v}")
            else:
                click.echo(f"  {k}: {v}")

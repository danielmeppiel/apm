"""APM runtime command group."""

import builtins
import sys

import click

from ..utils.console import (
    STATUS_SYMBOLS,
    _rich_error,
    _rich_info,
    _rich_panel,
    _rich_success,
)
from ._helpers import HIGHLIGHT, RESET, _get_console

# Restore builtin since a subcommand is named ``list``
list = builtins.list


@click.group(help="Manage AI runtimes")
def runtime():
    """Manage Coding Agent CLI runtime installations and configurations."""
    pass


@runtime.command(help="Set up a runtime")
@click.argument("runtime_name", type=click.Choice(["copilot", "codex", "llm"]))
@click.option("--version", help="Specific version to install")
@click.option(
    "--vanilla",
    is_flag=True,
    help="Install runtime without APM configuration (uses runtime's native defaults)",
)
def setup(runtime_name, version, vanilla):
    """Set up an AI runtime with APM-managed installation."""
    try:
        _rich_info(f"Setting up {runtime_name} runtime...")

        from ..runtime.manager import RuntimeManager

        manager = RuntimeManager()
        success = manager.setup_runtime(runtime_name, version, vanilla)

        if not success:
            sys.exit(1)
        else:
            _rich_success(f"{runtime_name} runtime setup complete!", symbol="sparkles")

    except (ImportError, OSError, RuntimeError) as e:
        _rich_error(f"Error setting up runtime: {e}")
        sys.exit(1)


@runtime.command(help="List available and installed runtimes")
def list():
    """List all available runtimes and their installation status."""
    try:
        from ..runtime.manager import RuntimeManager

        manager = RuntimeManager()
        runtimes = manager.list_runtimes()

        try:
            from rich.table import Table  # type: ignore

            console = _get_console()
            # Create a nice table for runtimes
            table = Table(
                title="🤖 Available Runtimes",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("Status", style="green", width=8)
            table.add_column("Runtime", style="bold white", min_width=10)
            table.add_column("Description", style="white")
            table.add_column("Details", style="muted")

            for name, info in runtimes.items():
                status_icon = (
                    STATUS_SYMBOLS["check"]
                    if info["installed"]
                    else STATUS_SYMBOLS["cross"]
                )
                status_text = "Installed" if info["installed"] else "Not installed"

                details = ""
                if info["installed"]:
                    details_list = [f"Path: {info['path']}"]
                    if "version" in info:
                        details_list.append(f"Version: {info['version']}")
                    details = "\n".join(details_list)

                table.add_row(
                    f"{status_icon} {status_text}", name, info["description"], details
                )

            console.print(table)

        except (ImportError, NameError):
            # Fallback to simple output
            _rich_info("Available Runtimes:")
            click.echo()

            for name, info in runtimes.items():
                status_icon = "✅" if info["installed"] else "❌"
                status_text = "Installed" if info["installed"] else "Not installed"

                click.echo(f"{status_icon} {HIGHLIGHT}{name}{RESET}")
                click.echo(f"   Description: {info['description']}")
                click.echo(f"   Status: {status_text}")

                if info["installed"]:
                    click.echo(f"   Path: {info['path']}")
                    if "version" in info:
                        click.echo(f"   Version: {info['version']}")

                click.echo()

    except (ImportError, OSError, RuntimeError) as e:
        _rich_error(f"Error listing runtimes: {e}")
        sys.exit(1)


@runtime.command(help="Remove an installed runtime")
@click.argument("runtime_name", type=click.Choice(["copilot", "codex", "llm"]))
@click.confirmation_option(prompt="Are you sure you want to remove this runtime?", help="Confirm the action without prompting")
def remove(runtime_name):
    """Remove an installed runtime from APM management."""
    try:
        _rich_info(f"Removing {runtime_name} runtime...")

        from ..runtime.manager import RuntimeManager

        manager = RuntimeManager()
        success = manager.remove_runtime(runtime_name)

        if not success:
            sys.exit(1)
        else:
            _rich_success(
                f"{runtime_name} runtime removed successfully!", symbol="sparkles"
            )

    except (ImportError, OSError, RuntimeError) as e:
        _rich_error(f"Error removing runtime: {e}")
        sys.exit(1)


@runtime.command(help="Check which runtime will be used")
def status():
    """Show which runtime APM will use for execution."""
    try:
        from ..runtime.manager import RuntimeManager

        manager = RuntimeManager()
        available_runtime = manager.get_available_runtime()
        preference = manager.get_runtime_preference()

        try:
            # Create a nice status display
            status_content = f"""Preference order: {' → '.join(preference)}

Active runtime: {available_runtime if available_runtime else 'None available'}"""

            if not available_runtime:
                status_content += f"\n\n{STATUS_SYMBOLS['info']} Run 'apm runtime setup copilot' to install the primary runtime"

            _rich_panel(status_content, title="📊 Runtime Status", style="cyan")

        except (ImportError, NameError):
            # Fallback display
            _rich_info("Runtime Status:")
            click.echo()

            click.echo(f"Preference order: {' → '.join(preference)}")

            if available_runtime:
                _rich_success(f"Active runtime: {available_runtime}")
            else:
                _rich_error("No runtimes available")
                _rich_info(
                    "Run 'apm runtime setup copilot' to install the primary runtime"
                )

    except (ImportError, OSError, RuntimeError) as e:
        _rich_error(f"Error checking runtime status: {e}")
        sys.exit(1)

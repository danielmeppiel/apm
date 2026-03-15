"""Command-line interface for Agent Package Manager (APM).

Thin wiring layer  -- all command logic lives in ``apm_cli.commands.*`` modules.
"""

import ctypes
import os
import sys

import click

from apm_cli.commands._helpers import (
    ERROR,
    RESET,
    _check_and_notify_updates,
    print_version,
)
from apm_cli.commands.audit import audit
from apm_cli.commands.compile import compile as compile_cmd
from apm_cli.commands.config import config
from apm_cli.commands.deps import deps
from apm_cli.commands.init import init
from apm_cli.commands.install import install
from apm_cli.commands.list_cmd import list as list_cmd
from apm_cli.commands.mcp import mcp
from apm_cli.commands.pack import pack_cmd, unpack_cmd
from apm_cli.commands.prune import prune
from apm_cli.commands.run import preview, run
from apm_cli.commands.runtime import runtime
from apm_cli.commands.uninstall import uninstall
from apm_cli.commands.update import update


@click.group(
    help="Agent Package Manager (APM): The package manager for AI-Native Development"
)
@click.option(
    "--version",
    is_flag=True,
    callback=print_version,
    expose_value=False,
    is_eager=True,
    help="Show version and exit.",
)
@click.pass_context
def cli(ctx):
    """Main entry point for the APM CLI."""
    ctx.ensure_object(dict)

    # Check for updates non-blockingly (only if not already showing version)
    if not ctx.resilient_parsing:
        _check_and_notify_updates()


# Register command groups
cli.add_command(audit)
cli.add_command(deps)
cli.add_command(pack_cmd, name="pack")
cli.add_command(unpack_cmd, name="unpack")
cli.add_command(init)
cli.add_command(install)
cli.add_command(uninstall)
cli.add_command(prune)
cli.add_command(update)
cli.add_command(compile_cmd, name="compile")
cli.add_command(run)
cli.add_command(preview)
cli.add_command(list_cmd, name="list")
cli.add_command(config)
cli.add_command(runtime)
cli.add_command(mcp)


def _configure_encoding() -> None:
    """Configure stdout/stderr for full Unicode on Windows.

    The default Windows console encoding (cp1252) cannot represent many Unicode
    characters used in APM output (box-drawing, check marks, arrows, etc.).

    This function:
    1. Sets ``PYTHONIOENCODING`` so child processes and redirected pipes
       default to UTF-8.
    2. Switches the console codepage to 65001 (UTF-8) via the Win32 API so
       the terminal itself renders UTF-8 byte sequences correctly.
    3. Reconfigures the Python text-mode streams to UTF-8.

    On non-Windows platforms this is a no-op.
    """
    if sys.platform != "win32":
        return

    # 1. Help child processes / pipes default to UTF-8
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    # 2. Switch the console codepage to UTF-8
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except (OSError, AttributeError):
        pass  # not a real console or ctypes unavailable

    # 3. Reconfigure Python streams to UTF-8
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                try:
                    stream.reconfigure(encoding="utf-8", errors="backslashreplace")
                except Exception:
                    pass


def main():
    """Main entry point for the CLI."""
    _configure_encoding()
    try:
        cli(obj={})
    except Exception as e:
        click.echo(f"{ERROR}Error: {e}{RESET}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

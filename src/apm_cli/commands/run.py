"""APM run and preview commands."""

import sys
from pathlib import Path

import click

from ..utils.console import _rich_echo, _rich_error, _rich_info, _rich_panel, _rich_success, _rich_warning
from ._helpers import (
    HIGHLIGHT,
    RESET,
    _get_console,
    _get_default_script,
    _list_available_scripts,
    _rich_blank_line,
)


@click.command(help="Run a script with parameters")
@click.argument("script_name", required=False)
@click.option("--param", "-p", multiple=True, help="Parameter in format name=value")
@click.pass_context
def run(ctx, script_name, param):
    """Run a script from apm.yml (uses 'start' script if no name specified)."""
    try:
        # If no script name specified, use 'start' script
        if not script_name:
            script_name = _get_default_script()
            if not script_name:
                _rich_error(
                    "No script specified and no 'start' script defined in apm.yml"
                )
                _rich_info("Available scripts:")
                scripts = _list_available_scripts()

                console = _get_console()
                if console:
                    try:
                        from rich.table import Table

                        # Show available scripts in a table
                        table = Table(show_header=False, box=None, padding=(0, 1))
                        table.add_column("Icon", style="cyan")
                        table.add_column("Script", style="highlight")
                        table.add_column("Command", style="white")

                        for name, command in scripts.items():
                            table.add_row("  ", name, command)

                        console.print(table)
                    except (ImportError, NameError):
                        for name, command in scripts.items():
                            click.echo(f"  - {HIGHLIGHT}{name}{RESET}: {command}")
                else:
                    for name, command in scripts.items():
                        click.echo(f"  - {HIGHLIGHT}{name}{RESET}: {command}")
                sys.exit(1)

        # Parse parameters
        params = {}
        for p in param:
            if "=" in p:
                param_name, value = p.split("=", 1)
                params[param_name] = value
                _rich_echo(f"  - {param_name}: {value}", style="muted")

        # Import and use script runner
        try:
            from ..core.script_runner import ScriptRunner

            script_runner = ScriptRunner()
            success = script_runner.run_script(script_name, params)

            if not success:
                _rich_error("Script execution failed")
                sys.exit(1)

            _rich_blank_line()
            _rich_success("Script executed successfully!", symbol="sparkles")

        except ImportError as ie:
            _rich_warning("Script runner not available yet")
            _rich_info(f"Import error: {ie}")
            _rich_info(f"Would run script: {script_name} with params {params}")
        except (RuntimeError, OSError) as ee:
            _rich_error(f"Script execution error: {ee}")
            sys.exit(1)

    except Exception as e:
        _rich_error(f"Error running script: {e}")
        sys.exit(1)


@click.command(help="Preview a script's compiled prompt files")
@click.argument("script_name", required=False)
@click.option("--param", "-p", multiple=True, help="Parameter in format name=value")
@click.pass_context
def preview(ctx, script_name, param):
    """Preview compiled prompt files for a script."""
    try:
        # If no script name specified, use 'start' script
        if not script_name:
            script_name = _get_default_script()
            if not script_name:
                _rich_error(
                    "No script specified and no 'start' script defined in apm.yml"
                )
                sys.exit(1)

        _rich_info(f"Previewing script: {script_name}", symbol="info")

        # Parse parameters
        params = {}
        for p in param:
            if "=" in p:
                param_name, value = p.split("=", 1)
                params[param_name] = value
                _rich_echo(f"  - {param_name}: {value}", style="muted")

        # Import and use script runner for preview
        try:
            from ..core.script_runner import ScriptRunner

            script_runner = ScriptRunner()

            # Get the script command
            scripts = script_runner.list_scripts()
            if script_name not in scripts:
                _rich_error(f"Script '{script_name}' not found")
                sys.exit(1)

            command = scripts[script_name]

            try:
                # Show original and compiled commands in panels
                _rich_panel(command, title="📄 Original command", style="blue")

                # Auto-compile prompts to show what would be executed
                compiled_command, compiled_prompt_files = (
                    script_runner._auto_compile_prompts(command, params)
                )

                if compiled_prompt_files:
                    _rich_panel(
                        compiled_command, title="⚡ Compiled command", style="green"
                    )
                else:
                    _rich_panel(
                        compiled_command,
                        title="⚡ Command (no prompt compilation)",
                        style="yellow",
                    )
                    _rich_warning(
                        f"No .prompt.md files found in command. APM only compiles files ending with '.prompt.md'"
                    )

                # Show compiled files if any .prompt.md files were processed
                if compiled_prompt_files:
                    file_list = []
                    for prompt_file in compiled_prompt_files:
                        output_name = (
                            Path(prompt_file).stem.replace(".prompt", "") + ".txt"
                        )
                        compiled_path = Path(".apm/compiled") / output_name
                        file_list.append(str(compiled_path))

                    files_content = "\n".join([f"📄 {file}" for file in file_list])
                    _rich_panel(
                        files_content, title="📁 Compiled prompt files", style="cyan"
                    )
                else:
                    _rich_panel(
                        "No .prompt.md files were compiled.\n\n"
                        + "APM only compiles files ending with '.prompt.md' extension.\n"
                        + "Other files are executed as-is by the runtime.",
                        title="ℹ️  Compilation Info",
                        style="cyan",
                    )

            except (ImportError, NameError):
                # Fallback display
                _rich_info("Original command:")
                click.echo(f"  {command}")

                compiled_command, compiled_prompt_files = (
                    script_runner._auto_compile_prompts(command, params)
                )

                if compiled_prompt_files:
                    _rich_info("Compiled command:")
                    click.echo(f"  {compiled_command}")

                    _rich_info("Compiled prompt files:")
                    for prompt_file in compiled_prompt_files:
                        output_name = (
                            Path(prompt_file).stem.replace(".prompt", "") + ".txt"
                        )
                        compiled_path = Path(".apm/compiled") / output_name
                        click.echo(f"  - {compiled_path}")
                else:
                    _rich_warning("Command (no prompt compilation):")
                    click.echo(f"  {compiled_command}")
                    _rich_info(
                        "APM only compiles files ending with '.prompt.md' extension."
                    )

            _rich_blank_line()
            _rich_success(
                f"Preview complete! Use 'apm run {script_name}' to execute.",
                symbol="sparkles",
            )

        except ImportError:
            _rich_warning("Script runner not available yet")

    except Exception as e:
        _rich_error(f"Error previewing script: {e}")
        sys.exit(1)

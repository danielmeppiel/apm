"""APM init command."""

import os
import sys
from pathlib import Path

import click

from ..constants import APM_YML_FILENAME
from ..utils.console import (
    _create_files_table,
    _rich_echo,
    _rich_error,
    _rich_info,
    _rich_panel,
    _rich_success,
    _rich_warning,
)
from ._helpers import (
    INFO,
    RESET,
    _create_minimal_apm_yml,
    _get_console,
    _get_default_config,
    _lazy_confirm,
    _rich_blank_line,
)


@click.command(help="Initialize a new APM project")
@click.argument("project_name", required=False)
@click.option(
    "--yes", "-y", is_flag=True, help="Skip interactive prompts and use auto-detected defaults"
)
@click.pass_context
def init(ctx, project_name, yes):
    """Initialize a new APM project (like npm init).

    Creates a minimal apm.yml with auto-detected metadata.
    """
    try:
        # Handle explicit current directory
        if project_name == ".":
            project_name = None

        # Determine project directory and name
        if project_name:
            project_dir = Path(project_name)
            project_dir.mkdir(exist_ok=True)
            os.chdir(project_dir)
            _rich_info(f"Created project directory: {project_name}", symbol="folder")
            final_project_name = project_name
        else:
            project_dir = Path.cwd()
            final_project_name = project_dir.name

        # Check for existing apm.yml
        apm_yml_exists = Path(APM_YML_FILENAME).exists()

        # Handle existing apm.yml in brownfield projects
        if apm_yml_exists:
            _rich_warning("apm.yml already exists")

            if not yes:
                Confirm = _lazy_confirm()
                if Confirm:
                    try:
                        confirm = Confirm.ask("Continue and overwrite?")
                    except (EOFError, KeyboardInterrupt):
                        confirm = click.confirm("Continue and overwrite?")
                else:
                    confirm = click.confirm("Continue and overwrite?")

                if not confirm:
                    _rich_info("Initialization cancelled.")
                    return
            else:
                _rich_info("--yes specified, overwriting apm.yml...")

        # Get project configuration (interactive mode or defaults)
        if not yes:
            config = _interactive_project_setup(final_project_name)
        else:
            # Use auto-detected defaults
            config = _get_default_config(final_project_name)

        _rich_success(f"Initializing APM project: {config['name']}", symbol="rocket")

        # Create minimal apm.yml
        _create_minimal_apm_yml(config)

        _rich_success("APM project initialized successfully!", symbol="sparkles")

        # Display created file info
        try:
            console = _get_console()
            if console:
                files_data = [
                    ("✨", APM_YML_FILENAME, "Project configuration"),
                ]
                table = _create_files_table(files_data, title="Created Files")
                console.print(table)
        except (ImportError, NameError):
            _rich_info("Created:")
            _rich_echo("  ✨ apm.yml - Project configuration", style="muted")

        _rich_blank_line()

        # Next steps - actionable commands matching README workflow
        next_steps = [
            "Install a runtime:       apm runtime setup copilot",
            "Add APM dependencies:    apm install <owner>/<repo>",
            "Compile agent context:   apm compile",
            "Run your first workflow: apm run start",
        ]

        try:
            _rich_panel(
                "\n".join(f"• {step}" for step in next_steps),
                title="💡 Next Steps",
                style="cyan",
            )
        except (ImportError, NameError):
            _rich_info("Next steps:")
            for step in next_steps:
                click.echo(f"  • {step}")

    except Exception as e:
        _rich_error(f"Error initializing project: {e}")
        sys.exit(1)


def _interactive_project_setup(default_name):
    """Interactive setup for new APM projects with auto-detection."""
    from ._helpers import _auto_detect_author, _auto_detect_description

    # Get auto-detected defaults
    auto_author = _auto_detect_author()
    auto_description = _auto_detect_description(default_name)

    try:
        # Lazy import rich pieces
        from rich.console import Console  # type: ignore
        from rich.panel import Panel  # type: ignore
        from rich.prompt import Confirm, Prompt  # type: ignore

        console = _get_console() or Console()
        console.print("\n[info]Setting up your APM project...[/info]")
        console.print("[muted]Press ^C at any time to quit.[/muted]\n")

        name = Prompt.ask("Project name", default=default_name).strip()
        version = Prompt.ask("Version", default="1.0.0").strip()
        description = Prompt.ask("Description", default=auto_description).strip()
        author = Prompt.ask("Author", default=auto_author).strip()

        summary_content = f"""name: {name}
version: {version}
description: {description}
author: {author}"""
        console.print(
            Panel(summary_content, title="About to create", border_style="cyan")
        )

        if not Confirm.ask("\nIs this OK?", default=True):
            console.print("[info]Aborted.[/info]")
            sys.exit(0)

    except (ImportError, NameError):
        # Fallback to click prompts
        _rich_info("Setting up your APM project...")
        _rich_info("Press ^C at any time to quit.")

        name = click.prompt("Project name", default=default_name).strip()
        version = click.prompt("Version", default="1.0.0").strip()
        description = click.prompt("Description", default=auto_description).strip()
        author = click.prompt("Author", default=auto_author).strip()

        click.echo(f"\n{INFO}About to create:{RESET}")
        click.echo(f"  name: {name}")
        click.echo(f"  version: {version}")
        click.echo(f"  description: {description}")
        click.echo(f"  author: {author}")

        if not click.confirm("\nIs this OK?", default=True):
            _rich_info("Aborted.")
            sys.exit(0)

    return {
        "name": name,
        "version": version,
        "description": description,
        "author": author,
    }

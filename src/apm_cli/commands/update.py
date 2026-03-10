"""APM update command."""

import os
import sys

import click

from ..utils.console import _rich_echo, _rich_error, _rich_info, _rich_success, _rich_warning
from ..version import get_version


@click.command(help="Update APM to the latest version")
@click.option("--check", is_flag=True, help="Only check for updates without installing")
def update(check):
    """Update APM CLI to the latest version (like npm update -g npm).

    This command fetches and installs the latest version of APM using the
    official install script. It will detect your platform and architecture
    automatically.

    Examples:
        apm update         # Update to latest version
        apm update --check # Only check if update is available
    """
    try:
        import subprocess
        import tempfile

        current_version = get_version()

        # Skip check for development versions
        if current_version == "unknown":
            _rich_warning(
                "Cannot determine current version. Running in development mode?"
            )
            if not check:
                _rich_info("To update, reinstall from the repository.")
            return

        _rich_info(f"Current version: {current_version}", symbol="info")
        _rich_info("Checking for updates...", symbol="running")

        # Check for latest version
        from ..utils.version_checker import get_latest_version_from_github

        latest_version = get_latest_version_from_github()

        if not latest_version:
            _rich_error("Unable to fetch latest version from GitHub")
            _rich_info("Please check your internet connection or try again later")
            sys.exit(1)

        from ..utils.version_checker import is_newer_version

        if not is_newer_version(current_version, latest_version):
            _rich_success(
                f"You're already on the latest version: {current_version}",
                symbol="check",
            )
            return

        _rich_info(f"Latest version available: {latest_version}", symbol="sparkles")

        if check:
            _rich_warning(f"Update available: {current_version} → {latest_version}")
            _rich_info("Run 'apm update' (without --check) to install", symbol="info")
            return

        # Proceed with update
        _rich_info("Downloading and installing update...", symbol="running")

        # Download install script to temp file
        try:
            import requests

            install_script_url = (
                "https://raw.githubusercontent.com/microsoft/apm/main/install.sh"
            )
            response = requests.get(install_script_url, timeout=10)
            response.raise_for_status()

            # Create temporary file for install script
            with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
                temp_script = f.name
                f.write(response.text)

            # Make script executable
            os.chmod(temp_script, 0o755)

            # Run install script
            _rich_info("Running installer...", symbol="gear")

            # Use /bin/sh for better cross-platform compatibility
            # Note: We don't capture output so the installer can prompt for sudo
            shell_path = "/bin/sh" if os.path.exists("/bin/sh") else "sh"
            result = subprocess.run(
                [shell_path, temp_script], check=False
            )

            # Clean up temp file
            try:
                os.unlink(temp_script)
            except OSError:
                # Non-fatal: failed to delete temp install script
                pass

            if result.returncode == 0:
                _rich_success(
                    f"Successfully updated to version {latest_version}!",
                    symbol="sparkles",
                )
                _rich_info(
                    "Please restart your terminal or run 'apm --version' to verify"
                )
            else:
                _rich_error("Installation failed - see output above for details")
                sys.exit(1)

        except ImportError:
            _rich_error("'requests' library not available")
            _rich_info("Please update manually using:")
            click.echo(
                "  curl -sSL https://raw.githubusercontent.com/microsoft/apm/main/install.sh | sh"
            )
            sys.exit(1)
        except (requests.RequestException, subprocess.SubprocessError, OSError) as e:
            _rich_error(f"Update failed: {e}")
            _rich_info("Please update manually using:")
            click.echo(
                "  curl -sSL https://raw.githubusercontent.com/microsoft/apm/main/install.sh | sh"
            )
            sys.exit(1)

    except Exception as e:
        _rich_error(f"Error during update: {e}")
        sys.exit(1)

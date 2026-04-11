"""Build-time policy for APM self-update behavior.

Package maintainers can patch this module during build to disable self-update
and show users a package-manager-specific update command.
"""

# Default guidance when self-update is disabled.
DEFAULT_SELF_UPDATE_DISABLED_MESSAGE = (
    "Self-update is disabled for this APM distribution. "
    "Update APM using your package manager."
)

# Build-time policy values.
#
# Packagers can patch these constants during build, for example:
# - SELF_UPDATE_ENABLED = False
# - SELF_UPDATE_DISABLED_MESSAGE = "Update with: conda update apm"
SELF_UPDATE_ENABLED = True
SELF_UPDATE_DISABLED_MESSAGE = DEFAULT_SELF_UPDATE_DISABLED_MESSAGE


def is_self_update_enabled() -> bool:
    """Return True when this build allows self-update."""
    return bool(SELF_UPDATE_ENABLED)


def get_self_update_disabled_message() -> str:
    """Return the guidance message shown when self-update is disabled."""
    message = str(SELF_UPDATE_DISABLED_MESSAGE).strip()
    if message:
        return message
    return DEFAULT_SELF_UPDATE_DISABLED_MESSAGE


def get_update_hint_message() -> str:
    """Return the update hint used in startup notifications."""
    if is_self_update_enabled():
        return "Run apm update to upgrade"
    return get_self_update_disabled_message()

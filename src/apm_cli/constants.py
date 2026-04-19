"""Shared constants for the APM CLI."""

from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class InstallMode(Enum):
    """Controls which dependency types are installed."""
    ALL = "all"
    APM = "apm"
    MCP = "mcp"


# ---------------------------------------------------------------------------
# File and directory names
# ---------------------------------------------------------------------------
APM_YML_FILENAME = "apm.yaml"
APM_LOCK_FILENAME = "apm.lock"
APM_MODULES_DIR = "apm_modules"
APM_DIR = ".apm"
SKILL_MD_FILENAME = "SKILL.md"
AGENTS_MD_FILENAME = "AGENTS.md"
CLAUDE_MD_FILENAME = "CLAUDE.md"
GITHUB_DIR = ".github"
CLAUDE_DIR = ".claude"
GITIGNORE_FILENAME = ".gitignore"
APM_MODULES_GITIGNORE_PATTERN = "apm_modules/"

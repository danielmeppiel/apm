"""Target profiles for multi-tool integration.

Each target tool (Copilot, Claude, Cursor, …) describes where APM
primitives should land.  Adding a new target means adding an entry to
``KNOWN_TARGETS`` — no new classes required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(frozen=True)
class PrimitiveMapping:
    """Where a single primitive type is deployed in a target tool."""

    subdir: str
    """Subdirectory under the target root (e.g. ``"rules"``, ``"agents"``)."""

    extension: str
    """File extension or suffix for deployed files
    (e.g. ``".mdc"``, ``".agent.md"``)."""

    format_id: str
    """Opaque tag used by integrators to select the right
    content transformer (e.g. ``"cursor_rules"``)."""


@dataclass(frozen=True)
class TargetProfile:
    """Capabilities and layout of a single target tool."""

    name: str
    """Short unique identifier (``"copilot"``, ``"claude"``, ``"cursor"``)."""

    root_dir: str
    """Top-level directory in the workspace (e.g. ``".github"``)."""

    primitives: Dict[str, PrimitiveMapping]
    """Mapping from APM primitive name → deployment spec.

    Only primitives listed here are deployed to this target.
    """

    auto_create: bool = True
    """Create *root_dir* if it does not exist."""

    detect_by_dir: bool = True
    """If ``True``, only deploy when *root_dir* already exists.

    Copilot sets this to ``False`` (always deploy).
    """

    @property
    def prefix(self) -> str:
        """Return the path prefix for this target (e.g. ``".github/"``).

        Used by ``validate_deploy_path`` and ``partition_managed_files``.
        """
        return f"{self.root_dir}/"

    def supports(self, primitive: str) -> bool:
        """Return ``True`` if this target accepts *primitive*."""
        return primitive in self.primitives


# ------------------------------------------------------------------
# Known targets
# ------------------------------------------------------------------

KNOWN_TARGETS: Dict[str, TargetProfile] = {
    "copilot": TargetProfile(
        name="copilot",
        root_dir=".github",
        primitives={
            "instructions": PrimitiveMapping(
                "instructions", ".instructions.md", "github_instructions"
            ),
            "prompts": PrimitiveMapping(
                "prompts", ".prompt.md", "github_prompt"
            ),
            "agents": PrimitiveMapping(
                "agents", ".agent.md", "github_agent"
            ),
            "skills": PrimitiveMapping(
                "skills", "/SKILL.md", "skill_standard"
            ),
            "hooks": PrimitiveMapping(
                "hooks", ".json", "github_hooks"
            ),
        },
        auto_create=True,
        detect_by_dir=False,
    ),
    "claude": TargetProfile(
        name="claude",
        root_dir=".claude",
        primitives={
            "agents": PrimitiveMapping(
                "agents", ".md", "claude_agent"
            ),
            "commands": PrimitiveMapping(
                "commands", ".md", "claude_command"
            ),
            "skills": PrimitiveMapping(
                "skills", "/SKILL.md", "skill_standard"
            ),
            "hooks": PrimitiveMapping(
                "hooks", ".json", "claude_hooks"
            ),
        },
        auto_create=False,
        detect_by_dir=True,
    ),
    "cursor": TargetProfile(
        name="cursor",
        root_dir=".cursor",
        primitives={
            "instructions": PrimitiveMapping(
                "rules", ".mdc", "cursor_rules"
            ),
            "agents": PrimitiveMapping(
                "agents", ".md", "cursor_agent"
            ),
            "skills": PrimitiveMapping(
                "skills", "/SKILL.md", "skill_standard"
            ),
            "hooks": PrimitiveMapping(
                "hooks", ".json", "cursor_hooks"
            ),
        },
        auto_create=False,
        detect_by_dir=True,
    ),
    # OpenCode does not support hooks — instructions are via AGENTS.md (apm compile).
    "opencode": TargetProfile(
        name="opencode",
        root_dir=".opencode",
        primitives={
            "agents": PrimitiveMapping(
                "agents", ".md", "opencode_agent"
            ),
            "commands": PrimitiveMapping(
                "commands", ".md", "opencode_command"
            ),
            "skills": PrimitiveMapping(
                "skills", "/SKILL.md", "skill_standard"
            ),
        },
        auto_create=False,
        detect_by_dir=True,
    ),
}


def get_integration_prefixes() -> tuple:
    """Return all known target root prefixes as a tuple.

    Used by ``BaseIntegrator.validate_deploy_path`` so the allow-list
    stays in sync with registered targets.
    """
    return tuple(t.prefix for t in KNOWN_TARGETS.values())


def active_targets(project_root) -> list:
    """Return the list of ``TargetProfile`` instances that should be
    deployed into *project_root* (based on ``detect_by_dir``).

    Args:
        project_root: The workspace root ``Path``.
    """
    from pathlib import Path

    root = Path(project_root)
    result = []
    for profile in KNOWN_TARGETS.values():
        if not profile.detect_by_dir or (root / profile.root_dir).exists():
            result.append(profile)
    return result

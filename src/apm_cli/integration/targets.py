"""Target profiles for multi-tool integration.

Each target tool (Copilot, Claude, Cursor, ...) describes where APM
primitives should land.  Adding a new target means adding an entry to
``KNOWN_TARGETS`` -- no new classes required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Union


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

    deploy_root: Optional[str] = None
    """Override *root_dir* for this primitive only.

    When set, integrators use ``deploy_root`` instead of
    ``target.root_dir`` to compute the deploy directory.
    For example, Codex skills deploy to ``.agents/`` (cross-tool
    directory) rather than ``.codex/``.  Default ``None`` preserves
    existing behavior for all other targets.
    """


@dataclass(frozen=True)
class TargetProfile:
    """Capabilities and layout of a single target tool."""

    name: str
    """Short unique identifier (``"copilot"``, ``"claude"``, ``"cursor"``)."""

    root_dir: str
    """Top-level directory in the workspace (e.g. ``".github"``)."""

    primitives: Dict[str, PrimitiveMapping]
    """Mapping from APM primitive name -> deployment spec.

    Only primitives listed here are deployed to this target.
    """

    auto_create: bool = True
    """Create *root_dir* if it does not exist (used during fallback or
    explicit ``--target`` selection)."""

    detect_by_dir: bool = True
    """If ``True``, only deploy when *root_dir* already exists."""

    # -- user-scope metadata --------------------------------------------------

    user_supported: Union[bool, str] = False
    """Whether this target supports user-scope (``~/``) deployment.

    * ``True``  -- fully supported (all primitives work at user scope).
    * ``"partial"`` -- some primitives work, others do not.
    * ``False`` -- not supported at user scope.
    """

    user_root_dir: Optional[str] = None
    """Override for *root_dir* at user scope.

    When ``None`` the normal *root_dir* is used at both project and user
    scope.  Set this when the tool reads from a different directory at
    user level (e.g. Copilot CLI uses ``~/.copilot/`` instead of
    ``~/.github/``).
    """

    unsupported_user_primitives: Tuple[str, ...] = ()
    """Primitives that are **not** available at user scope even when the
    target itself is partially supported (e.g. Copilot CLI cannot deploy
    prompts at user scope)."""

    @property
    def prefix(self) -> str:
        """Return the path prefix for this target (e.g. ``".github/"``).

        Used by ``validate_deploy_path`` and ``partition_managed_files``.
        """
        return f"{self.root_dir}/"

    def supports(self, primitive: str) -> bool:
        """Return ``True`` if this target accepts *primitive*."""
        return primitive in self.primitives

    def effective_root(self, user_scope: bool = False) -> str:
        """Return the root directory for the given scope.

        At user scope, returns *user_root_dir* when set, otherwise
        falls back to the standard *root_dir*.
        """
        if user_scope and self.user_root_dir:
            return self.user_root_dir
        return self.root_dir

    def supports_at_user_scope(self, primitive: str) -> bool:
        """Return ``True`` if *primitive* can be deployed at user scope."""
        if not self.user_supported:
            return False
        if primitive in self.unsupported_user_primitives:
            return False
        return primitive in self.primitives


# ------------------------------------------------------------------
# Known targets
# ------------------------------------------------------------------

KNOWN_TARGETS: Dict[str, TargetProfile] = {
    # Copilot (GitHub) -- at user scope, Copilot CLI reads ~/.copilot/
    # instead of ~/.github/.  Prompts and instructions are not supported at user scope.
    # Ref: https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-config-dir-reference
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
        detect_by_dir=True,
        user_supported="partial",
        user_root_dir=".copilot",
        unsupported_user_primitives=("prompts", "instructions"),
    ),
    # Claude Code -- ~/.claude/ is the documented user-level config directory.
    # All primitives are supported at user scope.
    # Ref: https://docs.anthropic.com/en/docs/claude-code/settings
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
        user_supported=True,
    ),
    # Cursor -- at user scope, ~/.cursor/ supports skills, agents, hooks,
    # and MCP.  Rules/instructions are managed via Cursor Settings UI only
    # (not file-based), so "instructions" is excluded from user scope.
    # Ref: https://cursor.com/docs/rules
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
        user_supported="partial",
        user_root_dir=".cursor",
        unsupported_user_primitives=("instructions",),
    ),
    # OpenCode -- at user scope, ~/.config/opencode/ supports skills, agents,
    # and commands.  OpenCode has no hooks concept, so "hooks" is excluded.
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
        user_supported="partial",
        user_root_dir=".config/opencode",
        unsupported_user_primitives=("hooks",),
    ),
    # Codex CLI: skills use the cross-tool .agents/ dir (agent skills standard),
    # agents are TOML under .codex/agents/, hooks merge into .codex/hooks.json.
    # Instructions are compile-only (AGENTS.md) -- not installed.
    "codex": TargetProfile(
        name="codex",
        root_dir=".codex",
        primitives={
            "agents": PrimitiveMapping(
                "agents", ".toml", "codex_agent"
            ),
            "skills": PrimitiveMapping(
                "skills", "/SKILL.md", "skill_standard",
                deploy_root=".agents",
            ),
            "hooks": PrimitiveMapping(
                "", "hooks.json", "codex_hooks"
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

    Includes prefixes from ``deploy_root`` overrides (e.g. ``.agents/``
    for Codex skills) so cross-root paths pass security validation.
    """
    prefixes: list[str] = []
    seen: set[str] = set()
    for t in KNOWN_TARGETS.values():
        if t.prefix not in seen:
            seen.add(t.prefix)
            prefixes.append(t.prefix)
        for m in t.primitives.values():
            if m.deploy_root is not None:
                dp = f"{m.deploy_root}/"
                if dp not in seen:
                    seen.add(dp)
                    prefixes.append(dp)
    return tuple(prefixes)


def active_targets_user_scope(
    explicit_target: "Optional[str]" = None,
) -> list:
    """Return ``TargetProfile`` instances for user-scope deployment.

    Mirrors ``active_targets()`` but operates against ``~/`` and filters
    out targets that do not support user scope.

    Resolution order:

    1. **Explicit target** (``--target``): returns the matching profile
       if it supports user scope.  ``"all"`` returns every user-capable
       target.
    2. **Directory detection**: profiles whose ``effective_root(user_scope=True)``
       directory exists under ``~/``.
    3. **Fallback**: ``[copilot]`` -- same default as project scope.
    """
    from pathlib import Path

    home = Path.home()

    # --- explicit target ---
    if explicit_target:
        canonical = explicit_target
        if canonical in ("copilot", "vscode", "agents"):
            canonical = "copilot"
        if canonical == "all":
            return [
                p for p in KNOWN_TARGETS.values()
                if p.user_supported
            ]
        profile = KNOWN_TARGETS.get(canonical)
        if profile and profile.user_supported:
            return [profile]
        return []

    # --- auto-detect by directory presence at ~/ ---
    detected = [
        p for p in KNOWN_TARGETS.values()
        if p.user_supported and (home / p.effective_root(user_scope=True)).is_dir()
    ]
    if detected:
        return detected

    # --- fallback: copilot is the universal default ---
    return [KNOWN_TARGETS["copilot"]]


def active_targets(project_root, explicit_target: "Optional[str]" = None) -> list:
    """Return the list of ``TargetProfile`` instances that should be
    deployed into *project_root*.

    Resolution order:

    1. **Explicit target** (``--target`` flag or ``apm.yml target:``):
       returns only the matching profile(s).  ``"all"`` returns every
       known target.
    2. **Directory detection**: profiles whose ``root_dir`` already
       exists under *project_root*.
    3. **Fallback**: when nothing is detected, returns ``[copilot]``
       so greenfield projects get a default skills root.

    Args:
        project_root: The workspace root ``Path``.
        explicit_target: Canonical target name (``"copilot"``, ``"claude"``,
            ``"cursor"``, ``"opencode"``, ``"all"``).  ``None`` means
            auto-detect.
    """
    from pathlib import Path

    root = Path(project_root)

    # --- explicit target ---
    if explicit_target:
        canonical = explicit_target
        if canonical in ("copilot", "vscode", "agents"):
            canonical = "copilot"
        if canonical == "all":
            return list(KNOWN_TARGETS.values())
        profile = KNOWN_TARGETS.get(canonical)
        return [profile] if profile else []

    # --- auto-detect by directory presence ---
    detected = [
        p for p in KNOWN_TARGETS.values()
        if (root / p.root_dir).is_dir()
    ]
    if detected:
        return detected

    # --- fallback: copilot is the universal default ---
    return [KNOWN_TARGETS["copilot"]]

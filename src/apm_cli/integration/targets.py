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
    """Create *root_dir* if it does not exist (used during fallback or
    explicit ``--target`` selection)."""

    detect_by_dir: bool = True
    """If ``True``, only deploy when *root_dir* already exists."""

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
        detect_by_dir=True,
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


# ------------------------------------------------------------------
# Integration dispatch registry
# ------------------------------------------------------------------
#
# Maps (target_name, primitive_name) -> (integrator_key, method_name, log_dir).
#
# ``integrator_key`` selects from the integrator dict passed to
# ``integrate_package_for_targets``.
#
# ``method_name`` is the method to call on that integrator.
#
# ``log_dir`` is the human-readable deploy directory for log output.
#
# Skills are excluded from per-target dispatch because
# ``SkillIntegrator.integrate_package_skill`` already handles
# multi-target routing internally via ``active_targets()``.
#
# Adding a new target or primitive only requires:
# 1. An entry in KNOWN_TARGETS above
# 2. An entry in INTEGRATION_DISPATCH below
# 3. The integrator method it references

INTEGRATION_DISPATCH: Dict[tuple, tuple] = {
    # --- copilot (.github) ---
    ("copilot", "prompts"): (
        "prompt_integrator", "integrate_package_prompts",
        ".github/prompts/",
    ),
    ("copilot", "agents"): (
        "agent_integrator", "integrate_package_agents",
        ".github/agents/",
    ),
    ("copilot", "instructions"): (
        "instruction_integrator", "integrate_package_instructions",
        ".github/instructions/",
    ),
    ("copilot", "hooks"): (
        "hook_integrator", "integrate_package_hooks",
        ".github/hooks/",
    ),

    # --- claude (.claude) ---
    ("claude", "agents"): (
        "agent_integrator", "integrate_package_agents_claude",
        ".claude/agents/",
    ),
    ("claude", "commands"): (
        "command_integrator", "integrate_package_commands",
        ".claude/commands/",
    ),
    ("claude", "hooks"): (
        "hook_integrator", "integrate_package_hooks_claude",
        ".claude/settings.json",
    ),

    # --- cursor (.cursor) ---
    ("cursor", "instructions"): (
        "instruction_integrator", "integrate_package_instructions_cursor",
        ".cursor/rules/",
    ),
    ("cursor", "agents"): (
        "agent_integrator", "integrate_package_agents_cursor",
        ".cursor/agents/",
    ),
    ("cursor", "hooks"): (
        "hook_integrator", "integrate_package_hooks_cursor",
        ".cursor/hooks.json",
    ),

    # --- opencode (.opencode) ---
    ("opencode", "agents"): (
        "agent_integrator", "integrate_package_agents_opencode",
        ".opencode/agents/",
    ),
    ("opencode", "commands"): (
        "command_integrator", "integrate_package_commands_opencode",
        ".opencode/commands/",
    ),
}


def integrate_package_for_targets(
    targets,
    package_info,
    project_root,
    integrators,
    *,
    force=False,
    managed_files=None,
    diagnostics=None,
    logger=None,
):
    """Run the full integration pipeline for a single package.

    Iterates *targets* (a list of ``TargetProfile``), and for each
    primitive that target supports, dispatches to the correct integrator
    method via ``INTEGRATION_DISPATCH``.

    Skills are handled separately because ``SkillIntegrator`` already
    routes to all active targets internally.

    Args:
        targets: List of ``TargetProfile`` to deploy into.
        package_info: ``PackageInfo`` for the package being installed.
        project_root: Workspace root ``Path``.
        integrators: Dict mapping integrator key (e.g. ``"agent_integrator"``)
            to integrator instance.
        force: Overwrite user-authored files on collision.
        managed_files: Set of workspace-relative paths from apm.lock.
        diagnostics: ``DiagnosticCollector`` instance.
        logger: Optional ``CommandLogger`` for tree output.

    Returns:
        Dict with integration counters and deployed file paths::

            {
                "prompts": int,
                "agents": int,
                "skills": int,
                "sub_skills": int,
                "instructions": int,
                "commands": int,
                "hooks": int,
                "links_resolved": int,
                "deployed_files": list[str],
            }
    """
    result = {
        "prompts": 0,
        "agents": 0,
        "skills": 0,
        "sub_skills": 0,
        "instructions": 0,
        "commands": 0,
        "hooks": 0,
        "links_resolved": 0,
        "deployed_files": [],
    }

    if not targets:
        return result

    deployed = result["deployed_files"]

    def _log(msg):
        if logger:
            logger.tree_item(msg)

    # Collect target names for the skill integrator check
    target_names = {t.name for t in targets}

    # --- per-target primitive dispatch ---
    for target in targets:
        for primitive in target.primitives:
            # Skills are handled separately below
            if primitive == "skills":
                continue

            key = (target.name, primitive)
            entry = INTEGRATION_DISPATCH.get(key)
            if entry is None:
                continue

            integrator_key, method_name, log_dir = entry
            integrator = integrators.get(integrator_key)
            if integrator is None:
                continue

            method = getattr(integrator, method_name, None)
            if method is None:
                continue

            call_result = method(
                package_info, project_root,
                force=force, managed_files=managed_files,
                diagnostics=diagnostics,
            )

            # Accumulate counts -- handle both IntegrationResult and
            # HookIntegrationResult (which uses hooks_integrated).
            files = getattr(call_result, "files_integrated", 0)
            hooks = getattr(call_result, "hooks_integrated", 0)
            updated = getattr(call_result, "files_updated", 0)
            links = getattr(call_result, "links_resolved", 0)

            if primitive == "hooks":
                if hooks > 0:
                    result["hooks"] += hooks
                    _log(f"  |-- {hooks} hook(s) integrated -> {log_dir}")
            elif primitive in ("prompts", "agents", "instructions", "commands"):
                if files > 0:
                    result[primitive] += files
                    _log(f"  |-- {files} {primitive} integrated -> {log_dir}")
                if updated > 0:
                    _log(f"  |-- {updated} {primitive} updated")

            result["links_resolved"] += links
            for tp in getattr(call_result, "target_paths", []):
                deployed.append(tp.relative_to(project_root).as_posix())

    # --- skills (multi-target, handled by SkillIntegrator) ---
    has_skill_target = any(t.supports("skills") for t in targets)
    if has_skill_target:
        skill_integrator = integrators.get("skill_integrator")
        if skill_integrator is not None:
            skill_result = skill_integrator.integrate_package_skill(
                package_info, project_root,
                diagnostics=diagnostics, managed_files=managed_files,
                force=force,
            )
            _skill_target_dirs: set[str] = set()
            for tp in skill_result.target_paths:
                rel = tp.relative_to(project_root)
                if rel.parts:
                    _skill_target_dirs.add(rel.parts[0])
            _skill_targets = sorted(_skill_target_dirs)
            _skill_target_str = (
                ", ".join(f"{d}/skills/" for d in _skill_targets) or "skills/"
            )
            if skill_result.skill_created:
                result["skills"] += 1
                _log(f"  |-- Skill integrated -> {_skill_target_str}")
            if skill_result.sub_skills_promoted > 0:
                result["sub_skills"] += skill_result.sub_skills_promoted
                _log(
                    f"  |-- {skill_result.sub_skills_promoted} skill(s) "
                    f"integrated -> {_skill_target_str}"
                )
            for tp in skill_result.target_paths:
                deployed.append(tp.relative_to(project_root).as_posix())

    return result

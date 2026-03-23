"""Target detection for auto-selecting compilation and integration targets.

This module implements the auto-detection pattern for determining which agent
targets (Copilot, Claude, Cursor, OpenCode) should be used based on existing
project structure and configuration.

Detection priority (highest to lowest):
1. Explicit --target flag (always wins)
2. apm.yml target setting (top-level field)
3. Auto-detect from existing folders:
   - .github/ only -> copilot (internal: "vscode")
   - .claude/ only -> claude
   - .cursor/ only -> cursor
   - .opencode/ only -> opencode
   - Multiple target folders -> all
   - None exist -> minimal (AGENTS.md only, no folder integration)

"copilot" is the recommended user-facing target name. "vscode" and "agents"
are accepted as aliases and map to the same internal value.
"""

from pathlib import Path
from typing import Literal, Optional, Tuple

# Valid target values (internal canonical form)
TargetType = Literal["vscode", "claude", "cursor", "opencode", "all", "minimal"]

# User-facing target values (includes aliases accepted by CLI)
UserTargetType = Literal["copilot", "vscode", "agents", "claude", "cursor", "opencode", "all", "minimal"]


def detect_target(
    project_root: Path,
    explicit_target: Optional[str] = None,
    config_target: Optional[str] = None,
) -> Tuple[TargetType, str]:
    """Detect the appropriate target for compilation and integration.
    
    Args:
        project_root: Root directory of the project
        explicit_target: Explicitly provided --target flag value
        config_target: Target from apm.yml top-level 'target' field
        
    Returns:
        Tuple of (target, reason) where:
        - target: The detected target type
        - reason: Human-readable explanation for the choice
    """
    # Priority 1: Explicit --target flag
    if explicit_target:
        if explicit_target in ("copilot", "vscode", "agents"):
            return "vscode", "explicit --target flag"
        elif explicit_target == "claude":
            return "claude", "explicit --target flag"
        elif explicit_target == "cursor":
            return "cursor", "explicit --target flag"
        elif explicit_target == "opencode":
            return "opencode", "explicit --target flag"
        elif explicit_target == "all":
            return "all", "explicit --target flag"
    
    # Priority 2: apm.yml target setting
    if config_target:
        if config_target in ("copilot", "vscode", "agents"):
            return "vscode", "apm.yml target"
        elif config_target == "claude":
            return "claude", "apm.yml target"
        elif config_target == "cursor":
            return "cursor", "apm.yml target"
        elif config_target == "opencode":
            return "opencode", "apm.yml target"
        elif config_target == "all":
            return "all", "apm.yml target"
    
    # Priority 3: Auto-detect from existing folders
    github_exists = (project_root / ".github").exists()
    claude_exists = (project_root / ".claude").exists()
    cursor_exists = (project_root / ".cursor").is_dir()
    opencode_exists = (project_root / ".opencode").is_dir()
    detected = []
    if github_exists:
        detected.append(".github/")
    if claude_exists:
        detected.append(".claude/")
    if cursor_exists:
        detected.append(".cursor/")
    if opencode_exists:
        detected.append(".opencode/")

    if len(detected) >= 2:
        return "all", f"detected {' and '.join(detected)} folders"
    elif github_exists:
        return "vscode", "detected .github/ folder"
    elif claude_exists:
        return "claude", "detected .claude/ folder"
    elif cursor_exists:
        return "cursor", "detected .cursor/ folder"
    elif opencode_exists:
        return "opencode", "detected .opencode/ folder"
    else:
        # No known target folders exist - minimal output
        return "minimal", "no .github/, .claude/, .cursor/, or .opencode/ folder found"


def should_integrate_vscode(target: TargetType) -> bool:
    """Check if VSCode integration should be performed.
    
    Args:
        target: The detected or configured target
        
    Returns:
        bool: True if VSCode integration (prompts, agents) should run
    """
    return target in ("vscode", "all")


def should_integrate_claude(target: TargetType) -> bool:
    """Check if Claude integration should be performed.
    
    Args:
        target: The detected or configured target
        
    Returns:
        bool: True if Claude integration (commands, skills) should run
    """
    return target in ("claude", "all")


def should_integrate_opencode(target: TargetType) -> bool:
    """Check if OpenCode integration should be performed.

    Args:
        target: The detected or configured target

    Returns:
        bool: True if OpenCode integration (agents, commands, skills) should run
    """
    return target in ("opencode", "all")


def should_integrate_cursor(target: TargetType) -> bool:
    """Check if Cursor integration should be performed.

    Args:
        target: The detected or configured target

    Returns:
        bool: True if Cursor integration (agents, skills, rules) should run
    """
    return target in ("cursor", "all")


def should_compile_agents_md(target: TargetType) -> bool:
    """Check if AGENTS.md should be compiled.
    
    AGENTS.md is generated for vscode, all, and minimal targets.
    It's the universal format that works everywhere.
    
    Args:
        target: The detected or configured target
        
    Returns:
        bool: True if AGENTS.md should be generated
    """
    return target in ("vscode", "opencode", "all", "minimal")


def should_compile_claude_md(target: TargetType) -> bool:
    """Check if CLAUDE.md should be compiled.
    
    Args:
        target: The detected or configured target
        
    Returns:
        bool: True if CLAUDE.md should be generated
    """
    return target in ("claude", "all")


def get_target_description(target: UserTargetType) -> str:
    """Get a human-readable description of what will be generated for a target.
    
    Accepts both internal target types and user-facing aliases.
    
    Args:
        target: The target type (internal or user-facing alias)
        
    Returns:
        str: Description of output files
    """
    # Normalize aliases to internal value for lookup
    normalized = "vscode" if target in ("copilot", "agents") else target
    descriptions = {
        "vscode": "AGENTS.md + .github/prompts/ + .github/agents/",
        "claude": "CLAUDE.md + .claude/commands/ + .claude/agents/ + .claude/skills/",
        "cursor": ".cursor/agents/ + .cursor/skills/ + .cursor/rules/",
        "opencode": "AGENTS.md + .opencode/agents/ + .opencode/commands/ + .opencode/skills/",
        "all": "AGENTS.md + CLAUDE.md + .github/ + .claude/ + .cursor/ + .opencode/",
        "minimal": "AGENTS.md only (create .github/ or .claude/ for full integration)",
    }
    return descriptions.get(normalized, "unknown target")

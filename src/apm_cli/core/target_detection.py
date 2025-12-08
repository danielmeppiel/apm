"""Target detection for auto-selecting compilation and integration targets.

This module implements the auto-detection pattern for determining which agent
targets (VSCode/Copilot vs Claude) should be used based on existing project
structure and configuration.

Detection priority (highest to lowest):
1. Explicit --target flag (always wins)
2. apm.yml target setting (top-level field)
3. Auto-detect from existing folders:
   - .github/ exists AND .claude/ doesn't → vscode
   - .claude/ exists AND .github/ doesn't → claude
   - Both exist → all
   - Neither exists → minimal (AGENTS.md only, no folder integration)
"""

from pathlib import Path
from typing import Literal, Optional, Tuple

# Valid target values
TargetType = Literal["vscode", "claude", "all", "minimal"]


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
        if explicit_target in ("vscode", "agents"):
            return "vscode", "explicit --target flag"
        elif explicit_target == "claude":
            return "claude", "explicit --target flag"
        elif explicit_target == "all":
            return "all", "explicit --target flag"
    
    # Priority 2: apm.yml target setting
    if config_target:
        if config_target in ("vscode", "agents"):
            return "vscode", "apm.yml target"
        elif config_target == "claude":
            return "claude", "apm.yml target"
        elif config_target == "all":
            return "all", "apm.yml target"
    
    # Priority 3: Auto-detect from existing folders
    github_exists = (project_root / ".github").exists()
    claude_exists = (project_root / ".claude").exists()
    
    if github_exists and not claude_exists:
        return "vscode", "detected .github/ folder"
    elif claude_exists and not github_exists:
        return "claude", "detected .claude/ folder"
    elif github_exists and claude_exists:
        return "all", "detected both .github/ and .claude/ folders"
    else:
        # Neither folder exists - minimal output
        return "minimal", "no .github/ or .claude/ folder found"


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


def should_compile_agents_md(target: TargetType) -> bool:
    """Check if AGENTS.md should be compiled.
    
    AGENTS.md is generated for vscode, all, and minimal targets.
    It's the universal format that works everywhere.
    
    Args:
        target: The detected or configured target
        
    Returns:
        bool: True if AGENTS.md should be generated
    """
    return target in ("vscode", "all", "minimal")


def should_compile_claude_md(target: TargetType) -> bool:
    """Check if CLAUDE.md should be compiled.
    
    Args:
        target: The detected or configured target
        
    Returns:
        bool: True if CLAUDE.md should be generated
    """
    return target in ("claude", "all")


def get_target_description(target: TargetType) -> str:
    """Get a human-readable description of what will be generated for a target.
    
    Args:
        target: The target type
        
    Returns:
        str: Description of output files
    """
    descriptions = {
        "vscode": "AGENTS.md + .github/prompts/ + .github/agents/",
        "claude": "CLAUDE.md + .claude/commands/ + SKILL.md",
        "all": "AGENTS.md + CLAUDE.md + .github/ + .claude/",
        "minimal": "AGENTS.md only (create .github/ or .claude/ for full integration)",
    }
    return descriptions.get(target, "unknown target")

namespace Apm.Cli.Core;

/// <summary>
/// Target detection for auto-selecting compilation and integration targets.
///
/// Detection priority (highest to lowest):
/// 1. Explicit --target flag (always wins)
/// 2. apm.yml target setting (top-level field)
/// 3. Auto-detect from existing folders:
///    - .github/ exists AND .claude/ doesn't → vscode
///    - .claude/ exists AND .github/ doesn't → claude
///    - Both exist → all
///    - Neither exists → minimal (AGENTS.md only, no folder integration)
/// </summary>
public static class TargetDetection
{
    /// <summary>
    /// Detect the appropriate target for compilation and integration.
    /// </summary>
    /// <param name="projectRoot">Root directory of the project.</param>
    /// <param name="explicitTarget">Explicitly provided --target flag value.</param>
    /// <param name="configTarget">Target from apm.yml top-level 'target' field.</param>
    /// <returns>Tuple of (target, reason).</returns>
    public static (string Target, string Reason) DetectTarget(
        string projectRoot,
        string? explicitTarget = null,
        string? configTarget = null)
    {
        // Priority 1: Explicit --target flag
        if (!string.IsNullOrEmpty(explicitTarget))
        {
            if (explicitTarget is "vscode" or "agents")
                return ("vscode", "explicit --target flag");
            if (explicitTarget is "claude")
                return ("claude", "explicit --target flag");
            if (explicitTarget is "all")
                return ("all", "explicit --target flag");
        }

        // Priority 2: apm.yml target setting
        if (!string.IsNullOrEmpty(configTarget))
        {
            if (configTarget is "vscode" or "agents")
                return ("vscode", "apm.yml target");
            if (configTarget is "claude")
                return ("claude", "apm.yml target");
            if (configTarget is "all")
                return ("all", "apm.yml target");
        }

        // Priority 3: Auto-detect from existing folders
        var githubExists = Directory.Exists(Path.Combine(projectRoot, ".github"));
        var claudeExists = Directory.Exists(Path.Combine(projectRoot, ".claude"));

        if (githubExists && !claudeExists)
            return ("vscode", "detected .github/ folder");
        if (claudeExists && !githubExists)
            return ("claude", "detected .claude/ folder");
        if (githubExists && claudeExists)
            return ("all", "detected both .github/ and .claude/ folders");

        return ("minimal", "no .github/ or .claude/ folder found");
    }

    /// <summary>Check if VSCode integration should be performed.</summary>
    public static bool ShouldIntegrateVscode(string target)
        => target is "vscode" or "all";

    /// <summary>Check if Claude integration should be performed.</summary>
    public static bool ShouldIntegrateClaude(string target)
        => target is "claude" or "all";

    /// <summary>
    /// Check if AGENTS.md should be compiled.
    /// AGENTS.md is generated for vscode, all, and minimal targets.
    /// </summary>
    public static bool ShouldCompileAgentsMd(string target)
        => target is "vscode" or "all" or "minimal";

    /// <summary>Check if CLAUDE.md should be compiled.</summary>
    public static bool ShouldCompileClaudeMd(string target)
        => target is "claude" or "all";

    /// <summary>Get a human-readable description of what will be generated for a target.</summary>
    public static string GetTargetDescription(string target) => target switch
    {
        "vscode" => "AGENTS.md + .github/prompts/ + .github/agents/",
        "claude" => "CLAUDE.md + .claude/commands/ + SKILL.md",
        "all" => "AGENTS.md + CLAUDE.md + .github/ + .claude/",
        "minimal" => "AGENTS.md only (create .github/ or .claude/ for full integration)",
        _ => "unknown target",
    };
}

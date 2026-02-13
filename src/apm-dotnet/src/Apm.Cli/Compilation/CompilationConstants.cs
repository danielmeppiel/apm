namespace Apm.Cli.Compilation;

/// <summary>
/// Shared constants for compilation extensions (constitution injection, etc.).
/// Also contains shared markers for build metadata stabilization.
/// </summary>
public static class CompilationConstants
{
    // Constitution injection markers
    public const string ConstitutionMarkerBegin = "<!-- SPEC-KIT CONSTITUTION: BEGIN -->";
    public const string ConstitutionMarkerEnd = "<!-- SPEC-KIT CONSTITUTION: END -->";
    public const string ConstitutionRelativePath = ".specify/memory/constitution.md";

    // Build ID placeholder & regex pattern
    public const string BuildIdPlaceholder = "<!-- Build ID: __BUILD_ID__ -->";
}

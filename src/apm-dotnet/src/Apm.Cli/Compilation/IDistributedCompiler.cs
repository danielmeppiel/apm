using Apm.Cli.Primitives;

namespace Apm.Cli.Compilation;

/// <summary>
/// Distributed AGENTS.md compilation following the Minimal Context Principle.
/// Stub interface — full implementation in a future wave.
/// </summary>
public interface IDistributedCompiler
{
    /// <summary>Compile primitives into distributed AGENTS.md files.</summary>
    DistributedCompilationResult CompileDistributed(
        PrimitiveCollection primitives,
        Dictionary<string, object> config);

    /// <summary>Analyze directory structure for instruction placement.</summary>
    List<DirectoryMapping> AnalyzeDirectoryStructure(List<Instruction> instructions);

    /// <summary>Determine AGENTS.md placement for instructions.</summary>
    List<PlacementResult> DetermineAgentsPlacement(
        List<Instruction> instructions,
        List<DirectoryMapping> directoryMap,
        int minInstructions = 1,
        bool debug = false);

    /// <summary>Get compilation results formatted for display.</summary>
    string? FormatCompilationOutput(bool isDryRun, bool verbose, bool debug);
}

/// <summary>Mapping of directory structure analysis.</summary>
public class DirectoryMapping
{
    public string Directory { get; init; } = "";
    public HashSet<string> ApplicablePatterns { get; init; } = [];
    public int Depth { get; init; }
    public string? ParentDirectory { get; init; }
}

/// <summary>Result of AGENTS.md placement analysis.</summary>
public class PlacementResult
{
    public string AgentsPath { get; init; } = "";
    public List<Instruction> Instructions { get; init; } = [];
    public List<Instruction> InheritedInstructions { get; init; } = [];
    public HashSet<string> CoveragePatterns { get; init; } = [];
    public Dictionary<string, string> SourceAttribution { get; init; } = [];
}

/// <summary>Result of distributed AGENTS.md compilation.</summary>
public class DistributedCompilationResult
{
    public bool Success { get; init; }
    public List<PlacementResult> Placements { get; init; } = [];
    public Dictionary<string, string> ContentMap { get; init; } = [];
    public List<string> Warnings { get; init; } = [];
    public List<string> Errors { get; init; } = [];
    public Dictionary<string, object> Stats { get; init; } = [];
}

using Apm.Cli.Primitives;

namespace Apm.Cli.Compilation;

/// <summary>
/// Formats CLAUDE.md files following the Claude Memory documentation format.
/// Stub interface — full implementation in a future wave.
/// </summary>
public interface IClaudeFormatter
{
    /// <summary>Format distributed CLAUDE.md files from primitives and placement map.</summary>
    ClaudeCompilationResult FormatDistributed(
        PrimitiveCollection primitives,
        List<PlacementResult> placements,
        Dictionary<string, object> config);
}

/// <summary>Result of CLAUDE.md compilation.</summary>
public class ClaudeCompilationResult
{
    public List<PlacementResult> Placements { get; init; } = [];
    public Dictionary<string, string> ContentMap { get; init; } = [];
    public List<string> Warnings { get; init; } = [];
    public List<string> Errors { get; init; } = [];
    public Dictionary<string, object> Stats { get; init; } = [];
}

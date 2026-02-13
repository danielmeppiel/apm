namespace Apm.Cli.Compilation;

/// <summary>Result of AGENTS.md compilation.</summary>
public class CompilationResult
{
    public bool Success { get; init; }
    public string OutputPath { get; init; } = "";
    public string Content { get; init; } = "";
    public List<string> Warnings { get; init; } = [];
    public List<string> Errors { get; init; } = [];
    public Dictionary<string, object> Stats { get; init; } = [];
}

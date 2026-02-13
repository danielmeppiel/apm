namespace Apm.Cli.Compilation;

/// <summary>Data structure for AGENTS.md template generation.</summary>
public class TemplateData
{
    public string InstructionsContent { get; init; } = "";
    public string Version { get; init; } = "";
    public string? ChatmodeContent { get; init; }
}

using Apm.Cli.Primitives;

namespace Apm.Cli.Workflow;

/// <summary>Simple container for workflow data.</summary>
public class WorkflowDefinition
{
    public string Name { get; set; } = "";
    public string FilePath { get; set; } = "";
    public string Description { get; set; } = "";
    public string Author { get; set; } = "";
    public List<string> McpDependencies { get; set; } = [];
    public List<string> InputParameters { get; set; } = [];
    /// <summary>LLM model specified in frontmatter.</summary>
    public string? LlmModel { get; set; }
    public string Content { get; set; } = "";

    /// <summary>Basic validation of required fields.</summary>
    public List<string> Validate()
    {
        var errors = new List<string>();
        if (string.IsNullOrEmpty(Description))
            errors.Add("Missing 'description' in frontmatter");
        return errors;
    }
}

/// <summary>Parser for workflow definition files.</summary>
public static class WorkflowParser
{
    /// <summary>Parse a workflow file.</summary>
    public static WorkflowDefinition ParseWorkflowFile(string filePath)
    {
        try
        {
            var text = File.ReadAllText(filePath);
            var (metadata, content) = PrimitiveParser.ParseFrontmatter(text);

            var name = ExtractWorkflowName(filePath);

            var mcpDeps = new List<string>();
            if (metadata.TryGetValue("mcp", out var mcpObj) && mcpObj is List<object> mcpList)
            {
                mcpDeps = mcpList.Select(m => m?.ToString() ?? "").Where(s => !string.IsNullOrEmpty(s)).ToList();
            }

            var inputParams = new List<string>();
            if (metadata.TryGetValue("input", out var inputObj) && inputObj is List<object> inputList)
            {
                inputParams = inputList.Select(i => i?.ToString() ?? "").Where(s => !string.IsNullOrEmpty(s)).ToList();
            }

            return new WorkflowDefinition
            {
                Name = name,
                FilePath = filePath,
                Description = metadata.TryGetValue("description", out var desc) ? desc?.ToString() ?? "" : "",
                Author = metadata.TryGetValue("author", out var author) ? author?.ToString() ?? "" : "",
                McpDependencies = mcpDeps,
                InputParameters = inputParams,
                LlmModel = metadata.TryGetValue("llm", out var llm) ? llm?.ToString() : null,
                Content = content
            };
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException($"Failed to parse workflow file: {ex.Message}", ex);
        }
    }

    /// <summary>Extract workflow name from file path based on naming conventions.</summary>
    internal static string ExtractWorkflowName(string filePath)
    {
        var normalized = Path.GetFullPath(filePath);
        var parts = normalized.Split(Path.DirectorySeparatorChar);

        // Check if it's a VSCode .github/prompts convention
        var githubIdx = Array.IndexOf(parts, ".github");
        if (githubIdx >= 0 && githubIdx + 1 < parts.Length && parts[githubIdx + 1] == "prompts")
        {
            var basename = Path.GetFileName(filePath);
            if (basename.EndsWith(".prompt.md", StringComparison.OrdinalIgnoreCase))
                return basename[..^".prompt.md".Length];
        }

        // For .prompt.md files
        var fileName = Path.GetFileName(filePath);
        if (fileName.EndsWith(".prompt.md", StringComparison.OrdinalIgnoreCase))
            return fileName[..^".prompt.md".Length];

        // Fallback: use filename without extension
        return Path.GetFileNameWithoutExtension(fileName);
    }
}

namespace Apm.Cli.Workflow;

/// <summary>Discovery functionality for workflow files.</summary>
public static class WorkflowDiscovery
{
    /// <summary>Find all .prompt.md files following VSCode's .github/prompts convention.</summary>
    public static List<WorkflowDefinition> DiscoverWorkflows(string? baseDir = null)
    {
        baseDir ??= Directory.GetCurrentDirectory();

        var promptPatterns = new[]
        {
            Path.Combine("**", ".github", "prompts", "*.prompt.md"),
            Path.Combine("**", "*.prompt.md")
        };

        var workflowFiles = new List<string>();
        foreach (var pattern in promptPatterns)
        {
            workflowFiles.AddRange(FindFiles(baseDir, pattern));
        }

        // Remove duplicates while preserving order
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var uniqueFiles = new List<string>();
        foreach (var file in workflowFiles)
        {
            var fullPath = Path.GetFullPath(file);
            if (seen.Add(fullPath))
                uniqueFiles.Add(fullPath);
        }

        var workflows = new List<WorkflowDefinition>();
        foreach (var filePath in uniqueFiles)
        {
            try
            {
                var workflow = WorkflowParser.ParseWorkflowFile(filePath);
                workflows.Add(workflow);
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"Warning: Failed to parse {filePath}: {ex.Message}");
            }
        }

        return workflows;
    }

    /// <summary>Create a basic workflow template file.</summary>
    public static string CreateWorkflowTemplate(
        string name, string? outputDir = null, string? description = null, bool useVsCodeConvention = true)
    {
        outputDir ??= Directory.GetCurrentDirectory();

        var title = System.Globalization.CultureInfo.CurrentCulture.TextInfo
            .ToTitleCase(name.Replace('-', ' '));
        var workflowDescription = description ?? $"Workflow for {title.ToLowerInvariant()}";

        var template =
            "---\n" +
            $"description: {workflowDescription}\n" +
            "author: Your Name\n" +
            "mcp:\n" +
            "  - package1\n" +
            "  - package2\n" +
            "input:\n" +
            "  - param1\n" +
            "  - param2\n" +
            "---\n" +
            "\n" +
            $"# {title}\n" +
            "\n" +
            "1. Step One:\n" +
            "   - Details for step one\n" +
            "   - Use parameters like this: ${input:param1}\n" +
            "\n" +
            "2. Step Two:\n" +
            "   - Details for step two\n";

        string filePath;
        if (useVsCodeConvention)
        {
            var promptsDir = Path.Combine(outputDir, ".github", "prompts");
            Directory.CreateDirectory(promptsDir);
            filePath = Path.Combine(promptsDir, $"{name}.prompt.md");
        }
        else
        {
            filePath = Path.Combine(outputDir, $"{name}.prompt.md");
        }

        File.WriteAllText(filePath, template);
        return filePath;
    }

    /// <summary>Find files matching a glob-like pattern with ** support.</summary>
    private static IEnumerable<string> FindFiles(string baseDir, string pattern)
    {
        if (!Directory.Exists(baseDir))
            return [];

        // Split pattern into parts to find the file name pattern
        var parts = pattern.Replace('/', Path.DirectorySeparatorChar).Split(Path.DirectorySeparatorChar);
        var filePattern = parts[^1];
        var hasRecursive = parts.Any(p => p == "**");

        try
        {
            return Directory.EnumerateFiles(
                baseDir,
                filePattern,
                hasRecursive ? SearchOption.AllDirectories : SearchOption.TopDirectoryOnly);
        }
        catch
        {
            return [];
        }
    }
}

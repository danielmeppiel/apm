using System.Text.RegularExpressions;
using Apm.Cli.Primitives;
using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;

namespace Apm.Cli.Dependencies;

/// <summary>
/// Workflow dependency aggregator for APM-CLI.
/// Scans prompt files for MCP dependencies following VSCode's .github/prompts convention.
/// </summary>
public static class Aggregator
{
    private static readonly Regex FrontmatterRegex = new(
        @"^---\s*\r?\n(.*?)\r?\n---",
        RegexOptions.Singleline | RegexOptions.Compiled);

    private static readonly IDeserializer YamlDeserializer = new DeserializerBuilder()
        .WithNamingConvention(CamelCaseNamingConvention.Instance)
        .Build();

    /// <summary>
    /// Scan all .prompt.md workflow files for MCP dependencies.
    /// </summary>
    /// <returns>A set of unique MCP server names from all workflows.</returns>
    public static HashSet<string> ScanWorkflowsForDependencies()
    {
        string[] promptPatterns =
        [
            "**/.github/prompts/*.prompt.md",
            "**/*.prompt.md"
        ];

        var workflows = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var pattern in promptPatterns)
        {
            foreach (var file in GlobFiles(".", pattern))
                workflows.Add(Path.GetFullPath(file));
        }

        var allServers = new HashSet<string>();
        foreach (var workflowFile in workflows)
        {
            try
            {
                var content = File.ReadAllText(workflowFile);
                var match = FrontmatterRegex.Match(content);
                if (!match.Success) continue;

                var metadata = YamlDeserializer.Deserialize<Dictionary<string, object?>>(match.Groups[1].Value);
                if (metadata == null) continue;

                if (metadata.TryGetValue("mcp", out var mcpVal) && mcpVal is List<object> mcpList)
                {
                    foreach (var server in mcpList)
                    {
                        var name = server?.ToString();
                        if (!string.IsNullOrEmpty(name))
                            allServers.Add(name);
                    }
                }
            }
            catch (Exception e)
            {
                Console.Error.WriteLine($"Error processing {workflowFile}: {e.Message}");
            }
        }

        return allServers;
    }

    /// <summary>
    /// Extract all MCP servers from workflows into apm.yml.
    /// </summary>
    /// <returns>Tuple of (success, list of servers added).</returns>
    public static (bool Success, List<string> Servers) SyncWorkflowDependencies(string outputFile = "apm.yml")
    {
        var allServers = ScanWorkflowsForDependencies();
        var sortedServers = allServers.OrderBy(s => s).ToList();

        var apmConfig = new Dictionary<string, object>
        {
            ["version"] = "1.0",
            ["servers"] = sortedServers
        };

        try
        {
            var serializer = new SerializerBuilder()
                .WithNamingConvention(UnderscoredNamingConvention.Instance)
                .Build();
            File.WriteAllText(outputFile, serializer.Serialize(apmConfig));
            return (true, sortedServers);
        }
        catch (Exception e)
        {
            Console.Error.WriteLine($"Error writing to {outputFile}: {e.Message}");
            return (false, []);
        }
    }

    private static IEnumerable<string> GlobFiles(string baseDir, string pattern)
    {
        var searchPattern = Path.GetFileName(pattern);
        try
        {
            return Directory.EnumerateFiles(baseDir, searchPattern, SearchOption.AllDirectories);
        }
        catch
        {
            return [];
        }
    }
}

using System.Text.RegularExpressions;
using Apm.Cli.Primitives;

namespace Apm.Cli.Integration;

/// <summary>Transforms SKILL.md to platform-native formats.</summary>
public class SkillTransformer
{
    /// <summary>
    /// Convert a name to hyphen-case for file naming.
    /// E.g., "Brand Guidelines" or "brand_guidelines" → "brand-guidelines".
    /// </summary>
    public static string ToHyphenCase(string name)
    {
        // Replace underscores and spaces with hyphens
        var result = name.Replace('_', '-').Replace(' ', '-');

        // Insert hyphens before uppercase letters (camelCase to hyphen-case)
        result = Regex.Replace(result, @"([a-z])([A-Z])", "$1-$2");

        // Convert to lowercase and remove any invalid characters
        result = Regex.Replace(result.ToLowerInvariant(), @"[^a-z0-9-]", "");

        // Remove consecutive hyphens
        result = Regex.Replace(result, @"-+", "-");

        // Remove leading/trailing hyphens
        return result.Trim('-');
    }

    /// <summary>Transform SKILL.md → .github/agents/{name}.agent.md for VSCode.</summary>
    public string? TransformToAgent(Skill skill, string outputDir, bool dryRun = false)
    {
        var agentContent = GenerateAgentContent(skill);
        var agentName = ToHyphenCase(skill.Name);
        var agentPath = Path.Combine(outputDir, ".github", "agents", $"{agentName}.agent.md");

        if (dryRun)
            return agentPath;

        Directory.CreateDirectory(Path.GetDirectoryName(agentPath)!);
        File.WriteAllText(agentPath, agentContent);
        return agentPath;
    }

    /// <summary>Get the hyphen-case agent name for a skill.</summary>
    public string GetAgentName(Skill skill) => ToHyphenCase(skill.Name);

    private static string GenerateAgentContent(Skill skill)
    {
        var lines = new List<string>
        {
            "---",
            $"name: {skill.Name}",
            $"description: {skill.Description}",
            "---",
            ""
        };

        if (!string.IsNullOrEmpty(skill.Source) && skill.Source != "local")
        {
            lines.Add($"<!-- Source: {skill.Source} -->");
            lines.Add("");
        }

        lines.Add(skill.Content);

        return string.Join("\n", lines);
    }
}

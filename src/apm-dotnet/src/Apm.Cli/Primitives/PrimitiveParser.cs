using System.Text.RegularExpressions;
using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;

namespace Apm.Cli.Primitives;

/// <summary>
/// Parser for primitive definition files (.instructions.md, .chatmode.md, .agent.md, .context.md, .memory.md, SKILL.md).
/// Handles YAML frontmatter extraction and primitive object construction.
/// </summary>
public static class PrimitiveParser
{
    private static readonly Regex FrontmatterRegex = new(
        @"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n?(.*)",
        RegexOptions.Singleline | RegexOptions.Compiled);

    private static readonly IDeserializer YamlDeserializer = new DeserializerBuilder()
        .WithNamingConvention(CamelCaseNamingConvention.Instance)
        .Build();

    /// <summary>Parse a SKILL.md file into a Skill primitive.</summary>
    public static Skill ParseSkillFile(string filePath, string? source = null)
    {
        try
        {
            var (metadata, content) = ParseFrontmatter(File.ReadAllText(filePath));

            var name = GetString(metadata, "name");
            var description = GetString(metadata, "description");

            // If name is missing, derive from parent directory name
            if (string.IsNullOrEmpty(name))
                name = Path.GetFileName(Path.GetDirectoryName(filePath)) ?? "";

            return new Skill
            {
                Name = name,
                FilePath = filePath,
                Description = description,
                Content = content,
                Source = source
            };
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException($"Failed to parse SKILL.md file {filePath}: {ex.Message}", ex);
        }
    }

    /// <summary>
    /// Parse a primitive file. Determines type based on file extension.
    /// </summary>
    public static object ParsePrimitiveFile(string filePath, string? source = null)
    {
        try
        {
            var (metadata, content) = ParseFrontmatter(File.ReadAllText(filePath));
            var name = ExtractPrimitiveName(filePath);
            var fileName = Path.GetFileName(filePath);

            if (fileName.EndsWith(".chatmode.md", StringComparison.OrdinalIgnoreCase) ||
                fileName.EndsWith(".agent.md", StringComparison.OrdinalIgnoreCase))
            {
                return ParseChatmode(name, filePath, metadata, content, source);
            }

            if (fileName.EndsWith(".instructions.md", StringComparison.OrdinalIgnoreCase))
            {
                return ParseInstruction(name, filePath, metadata, content, source);
            }

            if (fileName.EndsWith(".context.md", StringComparison.OrdinalIgnoreCase) ||
                fileName.EndsWith(".memory.md", StringComparison.OrdinalIgnoreCase) ||
                IsContextFile(filePath))
            {
                return ParseContext(name, filePath, metadata, content, source);
            }

            throw new InvalidOperationException($"Unknown primitive file type: {filePath}");
        }
        catch (Exception ex) when (ex is not InvalidOperationException)
        {
            throw new InvalidOperationException($"Failed to parse primitive file {filePath}: {ex.Message}", ex);
        }
    }

    /// <summary>Validate a primitive and return any errors.</summary>
    public static List<string> ValidatePrimitive(object primitive)
    {
        return primitive switch
        {
            Chatmode c => c.Validate(),
            Instruction i => i.Validate(),
            Context ctx => ctx.Validate(),
            Skill s => s.Validate(),
            _ => [$"Unknown primitive type: {primitive.GetType().Name}"]
        };
    }

    /// <summary>
    /// Parse YAML frontmatter from markdown content.
    /// Returns metadata dictionary and body content.
    /// </summary>
    internal static (Dictionary<string, object?> Metadata, string Content) ParseFrontmatter(string text)
    {
        var match = FrontmatterRegex.Match(text);
        if (!match.Success)
            return (new Dictionary<string, object?>(), text);

        var yamlBlock = match.Groups[1].Value;
        var body = match.Groups[2].Value;

        Dictionary<string, object?> metadata;
        try
        {
            metadata = YamlDeserializer.Deserialize<Dictionary<string, object?>>(yamlBlock)
                       ?? new Dictionary<string, object?>();
        }
        catch
        {
            metadata = new Dictionary<string, object?>();
        }

        return (metadata, body);
    }

    /// <summary>
    /// Extract a primitive name from the file path based on naming conventions.
    /// </summary>
    internal static string ExtractPrimitiveName(string filePath)
    {
        var parts = filePath.Replace('\\', '/').Split('/');

        // Check if it's in a structured directory (.apm/ or .github/)
        var apmIdx = Array.IndexOf(parts, ".apm");
        var ghIdx = Array.IndexOf(parts, ".github");
        var baseIdx = apmIdx >= 0 ? apmIdx : ghIdx;

        if (baseIdx >= 0 && baseIdx + 2 < parts.Length)
        {
            var subDir = parts[baseIdx + 1];
            if (subDir is "chatmodes" or "instructions" or "context" or "memory")
            {
                return StripPrimitiveExtension(Path.GetFileName(filePath));
            }
        }

        // Fallback: extract from filename
        return StripPrimitiveExtension(Path.GetFileName(filePath));
    }

    private static Chatmode ParseChatmode(string name, string filePath, Dictionary<string, object?> metadata, string content, string? source)
    {
        return new Chatmode
        {
            Name = name,
            FilePath = filePath,
            Description = GetString(metadata, "description"),
            ApplyTo = GetStringOrNull(metadata, "applyTo"),
            Content = content,
            Author = GetStringOrNull(metadata, "author"),
            Version = GetStringOrNull(metadata, "version"),
            Source = source
        };
    }

    private static Instruction ParseInstruction(string name, string filePath, Dictionary<string, object?> metadata, string content, string? source)
    {
        return new Instruction
        {
            Name = name,
            FilePath = filePath,
            Description = GetString(metadata, "description"),
            ApplyTo = GetString(metadata, "applyTo"),
            Content = content,
            Author = GetStringOrNull(metadata, "author"),
            Version = GetStringOrNull(metadata, "version"),
            Source = source
        };
    }

    private static Context ParseContext(string name, string filePath, Dictionary<string, object?> metadata, string content, string? source)
    {
        return new Context
        {
            Name = name,
            FilePath = filePath,
            Content = content,
            Description = GetStringOrNull(metadata, "description"),
            Author = GetStringOrNull(metadata, "author"),
            Version = GetStringOrNull(metadata, "version"),
            Source = source
        };
    }

    private static bool IsContextFile(string filePath)
    {
        var normalized = filePath.Replace('\\', '/');
        return normalized.Contains("/.apm/memory/") || normalized.Contains("/.github/memory/") ||
               normalized.Contains("\\.apm\\memory\\") || normalized.Contains("\\.github\\memory\\");
    }

    private static string StripPrimitiveExtension(string fileName)
    {
        string[] extensions = [".chatmode.md", ".agent.md", ".instructions.md", ".context.md", ".memory.md"];
        foreach (var ext in extensions)
        {
            if (fileName.EndsWith(ext, StringComparison.OrdinalIgnoreCase))
                return fileName[..^ext.Length];
        }

        return fileName.EndsWith(".md", StringComparison.OrdinalIgnoreCase)
            ? fileName[..^3]
            : Path.GetFileNameWithoutExtension(fileName);
    }

    private static string GetString(Dictionary<string, object?> metadata, string key)
    {
        return metadata.TryGetValue(key, out var value) && value is not null
            ? value.ToString() ?? ""
            : "";
    }

    private static string? GetStringOrNull(Dictionary<string, object?> metadata, string key)
    {
        return metadata.TryGetValue(key, out var value) && value is not null
            ? value.ToString()
            : null;
    }
}

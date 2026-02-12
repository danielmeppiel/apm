using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;

namespace Apm.Cli.Dependencies;

/// <summary>Represents a single item in a collection manifest.</summary>
public class CollectionItem
{
    /// <summary>Relative path to the file (e.g., "prompts/code-review.prompt.md").</summary>
    public string Path { get; set; } = "";

    /// <summary>Type of primitive (e.g., "prompt", "instruction", "chat-mode").</summary>
    public string Kind { get; set; } = "";

    private static readonly Dictionary<string, string> KindToSubdir = new(StringComparer.OrdinalIgnoreCase)
    {
        ["prompt"] = "prompts",
        ["instruction"] = "instructions",
        ["chat-mode"] = "chatmodes",
        ["chatmode"] = "chatmodes",
        ["agent"] = "agents",
        ["context"] = "contexts"
    };

    /// <summary>Get the .apm subdirectory for this item based on its kind.</summary>
    public string Subdirectory =>
        KindToSubdir.GetValueOrDefault(Kind.ToLowerInvariant(), "prompts");
}

/// <summary>Represents a parsed collection manifest (.collection.yml).</summary>
public class CollectionManifest
{
    public string Id { get; set; } = "";
    public string Name { get; set; } = "";
    public string Description { get; set; } = "";
    public List<CollectionItem> Items { get; set; } = [];
    public List<string>? Tags { get; set; }
    public Dictionary<string, object>? Display { get; set; }

    /// <summary>Get the number of items in this collection.</summary>
    public int ItemCount => Items.Count;

    /// <summary>Get all items of a specific kind.</summary>
    public List<CollectionItem> GetItemsByKind(string kind)
        => Items.Where(i => i.Kind.Equals(kind, StringComparison.OrdinalIgnoreCase)).ToList();
}

/// <summary>Parser for APM collection manifest files (.collection.yml).</summary>
public static class CollectionParser
{
    private static readonly IDeserializer YamlDeserializer = new DeserializerBuilder()
        .WithNamingConvention(UnderscoredNamingConvention.Instance)
        .Build();

    /// <summary>
    /// Parse a collection YAML manifest.
    /// </summary>
    /// <param name="content">Raw YAML content as bytes.</param>
    /// <returns>Parsed and validated collection manifest.</returns>
    /// <exception cref="ArgumentException">If the YAML is invalid or missing required fields.</exception>
    public static CollectionManifest ParseCollectionYml(byte[] content)
    {
        Dictionary<string, object?> data;
        try
        {
            var yamlStr = System.Text.Encoding.UTF8.GetString(content);
            data = YamlDeserializer.Deserialize<Dictionary<string, object?>>(yamlStr)
                   ?? throw new ArgumentException("Collection YAML must be a dictionary");
        }
        catch (YamlDotNet.Core.YamlException e)
        {
            throw new ArgumentException($"Invalid YAML format: {e.Message}", e);
        }

        // Validate required fields
        string[] requiredFields = ["id", "name", "description", "items"];
        var missingFields = requiredFields.Where(f => !data.ContainsKey(f) || data[f] == null).ToList();
        if (missingFields.Count > 0)
            throw new ArgumentException($"Collection manifest missing required fields: {string.Join(", ", missingFields)}");

        // Validate and parse items
        if (data["items"] is not List<object> itemsData)
            throw new ArgumentException("Collection 'items' must be a list");

        if (itemsData.Count == 0)
            throw new ArgumentException("Collection must contain at least one item");

        var items = new List<CollectionItem>();
        for (var idx = 0; idx < itemsData.Count; idx++)
        {
            if (itemsData[idx] is not Dictionary<object, object> itemDict)
                throw new ArgumentException($"Collection item {idx} must be a dictionary");

            if (!itemDict.ContainsKey("path"))
                throw new ArgumentException($"Collection item {idx} missing required field 'path'");
            if (!itemDict.ContainsKey("kind"))
                throw new ArgumentException($"Collection item {idx} missing required field 'kind'");

            items.Add(new CollectionItem
            {
                Path = itemDict["path"]?.ToString() ?? "",
                Kind = itemDict["kind"]?.ToString() ?? ""
            });
        }

        // Parse optional tags
        List<string>? tags = null;
        if (data.TryGetValue("tags", out var tagsVal) && tagsVal is List<object> tagsList)
            tags = tagsList.Select(t => t?.ToString() ?? "").ToList();

        // Parse optional display
        Dictionary<string, object>? display = null;
        if (data.TryGetValue("display", out var displayVal) && displayVal is Dictionary<object, object> displayDict)
        {
            display = new Dictionary<string, object>();
            foreach (var kvp in displayDict)
            {
                if (kvp.Key?.ToString() is { } key)
                    display[key] = kvp.Value!;
            }
        }

        return new CollectionManifest
        {
            Id = data["id"]!.ToString()!,
            Name = data["name"]!.ToString()!,
            Description = data["description"]!.ToString()!,
            Items = items,
            Tags = tags,
            Display = display
        };
    }
}

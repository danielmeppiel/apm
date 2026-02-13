using System.Text.Json;
using System.Text.Json.Nodes;

namespace Apm.Cli.Utils;

/// <summary>
/// AOT-safe JSON serialization helpers that avoid reflection-based JsonSerializer calls.
/// </summary>
internal static class JsonSerializationHelper
{
    /// <summary>
    /// Convert a Dictionary&lt;string, object?&gt; to a JsonObject (AOT-safe).
    /// </summary>
    internal static JsonObject DictToJsonObject(Dictionary<string, object?> dict)
    {
        var obj = new JsonObject();
        foreach (var kvp in dict)
            obj[kvp.Key] = ToJsonNode(kvp.Value);
        return obj;
    }

    /// <summary>
    /// Convert an arbitrary object to a JsonNode (AOT-safe).
    /// </summary>
    internal static JsonNode? ToJsonNode(object? value) => value switch
    {
        null => null,
        JsonNode node => node.DeepClone(),
        JsonElement element => JsonNode.Parse(element.GetRawText()),
        string s => JsonValue.Create(s),
        bool b => JsonValue.Create(b),
        int i => JsonValue.Create(i),
        long l => JsonValue.Create(l),
        double d => JsonValue.Create(d),
        Dictionary<string, object?> dict => DictToJsonObject(dict),
        System.Collections.IList list => ListToJsonArray(list),
        _ => JsonValue.Create(value.ToString()!)
    };

    /// <summary>
    /// Convert an IList to a JsonArray (AOT-safe).
    /// </summary>
    internal static JsonArray ListToJsonArray(System.Collections.IList list)
    {
        var arr = new JsonArray();
        foreach (var item in list)
            arr.Add(ToJsonNode(item));
        return arr;
    }

    /// <summary>
    /// Convert a JsonNode to a JsonElement (AOT-safe replacement for JsonSerializer.SerializeToElement).
    /// </summary>
    internal static JsonElement ToJsonElement(JsonNode? node)
    {
        using var doc = JsonDocument.Parse(node?.ToJsonString() ?? "null");
        return doc.RootElement.Clone();
    }
}

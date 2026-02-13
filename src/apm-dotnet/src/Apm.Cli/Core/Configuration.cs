using System.Text.Json;
using System.Text.Json.Nodes;

namespace Apm.Cli.Core;

/// <summary>
/// Configuration management for APM-CLI.
/// Reads and writes JSON config at ~/.apm-cli/config.json.
/// </summary>
public static class Configuration
{
    private static string ConfigDir = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".apm-cli");

    private static string ConfigFile = Path.Combine(ConfigDir, "config.json");

    private static readonly JsonSerializerOptions WriteOptions = new()
    {
        WriteIndented = true
    };

    /// <summary>
    /// Ensure the configuration directory and file exist.
    /// Creates the directory and a default config file if they don't exist.
    /// </summary>
    public static void EnsureConfigExists()
    {
        if (!Directory.Exists(ConfigDir))
            Directory.CreateDirectory(ConfigDir);

        if (!File.Exists(ConfigFile))
        {
            var defaults = new JsonObject { ["default_client"] = "vscode" };
            File.WriteAllText(ConfigFile, defaults.ToJsonString(WriteOptions));
        }
    }

    /// <summary>
    /// Get the current configuration as a mutable dictionary.
    /// </summary>
    public static Dictionary<string, JsonNode?> GetConfig()
    {
        EnsureConfigExists();
        var text = File.ReadAllText(ConfigFile);
        var obj = JsonNode.Parse(text)?.AsObject()
                  ?? throw new InvalidOperationException("Config file is not a valid JSON object.");

        var dict = new Dictionary<string, JsonNode?>();
        foreach (var kvp in obj)
            dict[kvp.Key] = kvp.Value?.DeepClone();
        return dict;
    }

    /// <summary>
    /// Update the configuration with new values (merge and save).
    /// </summary>
    public static void UpdateConfig(Dictionary<string, JsonNode?> updates)
    {
        var config = GetConfig();
        foreach (var kvp in updates)
            config[kvp.Key] = kvp.Value?.DeepClone();

        var obj = new JsonObject();
        foreach (var kvp in config)
            obj[kvp.Key] = kvp.Value?.DeepClone();

        File.WriteAllText(ConfigFile, obj.ToJsonString(WriteOptions));
    }

    /// <summary>
    /// Get the default MCP client.
    /// </summary>
    public static string GetDefaultClient()
    {
        var config = GetConfig();
        if (config.TryGetValue("default_client", out var node) && node is not null)
            return node.GetValue<string>();
        return "vscode";
    }

    /// <summary>
    /// Set the default MCP client.
    /// </summary>
    public static void SetDefaultClient(string clientType)
    {
        UpdateConfig(new Dictionary<string, JsonNode?> { ["default_client"] = clientType });
    }
}

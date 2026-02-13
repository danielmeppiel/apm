using System.Text.Json;
using Apm.Cli.Adapters.Client;
using Apm.Cli.Registry;

namespace Apm.Cli.Core;

/// <summary>
/// Detailed information about a server conflict.
/// </summary>
public sealed class ConflictSummary
{
    public bool Exists { get; set; }
    public string CanonicalName { get; set; } = "";
    public List<ConflictingServer> ConflictingServers { get; set; } = [];
}

/// <summary>
/// Information about a single conflicting server entry.
/// </summary>
public sealed class ConflictingServer
{
    public required string Name { get; init; }
    public required string Type { get; init; }
    public string? ResolvesTo { get; init; }
}

/// <summary>
/// Handles detection and resolution of MCP server configuration conflicts.
/// </summary>
public sealed class ConflictDetector
{
    private readonly IClientAdapter? _adapter;
    private readonly RegistryClient? _registryClient;

    public ConflictDetector()
    {
    }

    public ConflictDetector(IClientAdapter adapter, RegistryClient? registryClient = null)
    {
        _adapter = adapter;
        _registryClient = registryClient;
    }

    /// <summary>
    /// Check if a server already exists in the configuration.
    /// </summary>
    public bool CheckServerExists(string serverReference)
    {
        var existingServers = GetExistingServerConfigs();

        // Try registry-based UUID comparison
        try
        {
            if (_registryClient is not null)
            {
                var serverInfo = _registryClient.FindServerByReference(serverReference);
                if (serverInfo is not null && serverInfo.TryGetValue("id", out var idEl) &&
                    idEl.ValueKind == JsonValueKind.String)
                {
                    var serverUuid = idEl.GetString();
                    foreach (var (_, config) in existingServers)
                    {
                        if (config is Dictionary<string, object?> dict &&
                            dict.TryGetValue("id", out var existingId) &&
                            existingId?.ToString() == serverUuid)
                            return true;
                    }
                }
            }
            else
            {
                // No registry — go straight to canonical name fallback
                throw new InvalidOperationException();
            }
        }
        catch
        {
            // Fall back to canonical name comparison
            var canonicalName = GetCanonicalServerName(serverReference);

            if (existingServers.ContainsKey(canonicalName))
                return true;

            foreach (var existingName in existingServers.Keys)
            {
                if (existingName == canonicalName)
                    continue;
                try
                {
                    if (GetCanonicalServerName(existingName) == canonicalName)
                        return true;
                }
                catch
                {
                    // Skip unresolvable entries
                }
            }
        }

        return false;
    }

    /// <summary>
    /// Get canonical server name from MCP Registry.
    /// Falls back to the original reference if registry lookup fails.
    /// </summary>
    public string GetCanonicalServerName(string serverRef)
    {
        try
        {
            if (_registryClient is not null)
            {
                var serverInfo = _registryClient.FindServerByReference(serverRef);
                if (serverInfo is not null)
                {
                    // Prefer x-github.name, then fall back to name
                    if (serverInfo.TryGetValue("x-github", out var xGitHub) &&
                        xGitHub.ValueKind == JsonValueKind.Object &&
                        xGitHub.TryGetProperty("name", out var ghName) &&
                        ghName.ValueKind == JsonValueKind.String)
                    {
                        return ghName.GetString()!;
                    }

                    if (serverInfo.TryGetValue("name", out var nameEl) &&
                        nameEl.ValueKind == JsonValueKind.String)
                    {
                        return nameEl.GetString()!;
                    }
                }
            }
        }
        catch
        {
            // Graceful fallback
        }

        return serverRef;
    }

    /// <summary>
    /// Extract all existing server configurations.
    /// Detects config format by adapter type name, falling back to config key probing.
    /// </summary>
    public Dictionary<string, object> GetExistingServerConfigs()
    {
        if (_adapter is null)
            return new Dictionary<string, object>();

        var config = _adapter.GetCurrentConfig();
        var adapterTypeName = _adapter.GetType().Name.ToLowerInvariant();

        // Detect by adapter class name first, then fall back to config key probing
        if (adapterTypeName.Contains("copilot") || config.ContainsKey("mcpServers"))
        {
            return ExtractSection(config, "mcpServers");
        }

        if (adapterTypeName.Contains("codex") ||
            config.ContainsKey("mcp_servers") ||
            config.Keys.Any(k => k.StartsWith("mcp_servers.")))
        {
            return ExtractCodexServers(config);
        }

        if (adapterTypeName.Contains("vscode") || config.ContainsKey("servers"))
        {
            return ExtractSection(config, "servers");
        }

        return new Dictionary<string, object>();
    }

    private static Dictionary<string, object> ExtractCodexServers(Dictionary<string, object?> config)
    {
        var servers = new Dictionary<string, object>();

        // Direct mcp_servers section
        if (config.TryGetValue("mcp_servers", out var mcpSection) && mcpSection is not null)
            MergeSection(servers, mcpSection);

        // Handle TOML-style nested keys like "mcp_servers.github"
        foreach (var (key, value) in config)
        {
            if (key.StartsWith("mcp_servers.") && value is not null)
            {
                var serverName = key["mcp_servers.".Length..];
                if (serverName.StartsWith('"') && serverName.EndsWith('"'))
                    serverName = serverName[1..^1];

                if (value is Dictionary<string, object?> dict &&
                    (dict.ContainsKey("command") || dict.ContainsKey("args")))
                {
                    servers[serverName] = value;
                }
            }
        }

        return servers;
    }

    /// <summary>
    /// Get detailed information about a conflict.
    /// </summary>
    public ConflictSummary GetConflictSummary(string serverReference)
    {
        var canonicalName = GetCanonicalServerName(serverReference);
        var existingServers = GetExistingServerConfigs();

        var summary = new ConflictSummary
        {
            Exists = false,
            CanonicalName = canonicalName,
        };

        // Check exact canonical name match
        if (existingServers.ContainsKey(canonicalName))
        {
            summary.Exists = true;
            summary.ConflictingServers.Add(new ConflictingServer
            {
                Name = canonicalName,
                Type = "exact_match",
            });
        }

        // Check if any existing server resolves to the same canonical name
        foreach (var existingName in existingServers.Keys)
        {
            if (existingName == canonicalName)
                continue;

            var existingCanonical = GetCanonicalServerName(existingName);
            if (existingCanonical == canonicalName)
            {
                summary.Exists = true;
                summary.ConflictingServers.Add(new ConflictingServer
                {
                    Name = existingName,
                    Type = "canonical_match",
                    ResolvesTo = existingCanonical,
                });
            }
        }

        return summary;
    }

    private static Dictionary<string, object> ExtractSection(Dictionary<string, object?> config, string key)
    {
        if (config.TryGetValue(key, out var section) && section is Dictionary<string, object?> dict)
        {
            var result = new Dictionary<string, object>();
            foreach (var (k, v) in dict)
            {
                if (v is not null)
                    result[k] = v;
            }
            return result;
        }

        return new Dictionary<string, object>();
    }

    private static void MergeSection(Dictionary<string, object> target, object source)
    {
        if (source is Dictionary<string, object?> dict)
        {
            foreach (var (k, v) in dict)
            {
                if (v is not null)
                    target[k] = v;
            }
        }
    }
}

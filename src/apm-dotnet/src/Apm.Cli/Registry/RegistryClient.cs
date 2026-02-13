using System.Net.Http.Json;
using System.Text.Json;

namespace Apm.Cli.Registry;

/// <summary>Simple client for querying MCP registries for server discovery.</summary>
public class RegistryClient : IDisposable
{
    private readonly string _registryUrl;
    private readonly HttpClient _httpClient;

    /// <param name="registryUrl">
    /// URL of the MCP registry. Falls back to MCP_REGISTRY_URL env var, then to the default registry.
    /// </param>
    public RegistryClient(string? registryUrl = null)
    {
        _registryUrl = registryUrl
            ?? Environment.GetEnvironmentVariable("MCP_REGISTRY_URL")
            ?? "https://api.mcp.github.com";
        _httpClient = new HttpClient();
        _httpClient.DefaultRequestHeaders.UserAgent.ParseAdd("apm-cli/1.0");
    }

    /// <summary>List all available servers in the registry.</summary>
    public (List<Dictionary<string, JsonElement>> Servers, string? NextCursor) ListServers(int limit = 100, string? cursor = null)
    {
        var url = $"{_registryUrl}/v0/servers?limit={limit}";
        if (cursor != null)
            url += $"&cursor={Uri.EscapeDataString(cursor)}";

        var response = _httpClient.GetAsync(url).GetAwaiter().GetResult();
        response.EnsureSuccessStatusCode();

        using var doc = JsonDocument.Parse(response.Content.ReadAsStringAsync().GetAwaiter().GetResult());
        var root = doc.RootElement;

        var servers = ExtractServers(root);

        string? nextCursor = null;
        if (root.TryGetProperty("metadata", out var metadata) &&
            metadata.TryGetProperty("next_cursor", out var nc) &&
            nc.ValueKind == JsonValueKind.String)
        {
            nextCursor = nc.GetString();
        }

        return (servers, nextCursor);
    }

    /// <summary>Search for servers in the registry.</summary>
    public List<Dictionary<string, JsonElement>> SearchServers(string query)
    {
        var searchQuery = ExtractRepositoryName(query);
        var url = $"{_registryUrl}/v0/servers/search?q={Uri.EscapeDataString(searchQuery)}";

        var response = _httpClient.GetAsync(url).GetAwaiter().GetResult();
        response.EnsureSuccessStatusCode();

        using var doc = JsonDocument.Parse(response.Content.ReadAsStringAsync().GetAwaiter().GetResult());
        return ExtractServers(doc.RootElement);
    }

    /// <summary>Get detailed information about a specific server.</summary>
    /// <exception cref="ArgumentException">If the server is not found.</exception>
    public Dictionary<string, JsonElement> GetServerInfo(string serverId)
    {
        var url = $"{_registryUrl}/v0/servers/{Uri.EscapeDataString(serverId)}";

        var response = _httpClient.GetAsync(url).GetAwaiter().GetResult();
        response.EnsureSuccessStatusCode();

        using var doc = JsonDocument.Parse(response.Content.ReadAsStringAsync().GetAwaiter().GetResult());
        var root = doc.RootElement;

        if (root.TryGetProperty("server", out var serverProp))
        {
            var result = new Dictionary<string, JsonElement>();
            // Merge server info to top level
            foreach (var prop in serverProp.EnumerateObject())
                result[prop.Name] = prop.Value.Clone();
            // Add non-server top-level fields
            foreach (var prop in root.EnumerateObject())
            {
                if (prop.Name != "server")
                    result[prop.Name] = prop.Value.Clone();
            }

            if (result.Count == 0)
                throw new ArgumentException($"Server '{serverId}' not found in registry");
            return result;
        }

        var dict = JsonElementToDict(root);
        if (dict.Count == 0)
            throw new ArgumentException($"Server '{serverId}' not found in registry");
        return dict;
    }

    /// <summary>Find a server by its name using the search API.</summary>
    public Dictionary<string, JsonElement>? GetServerByName(string name)
    {
        try
        {
            var searchResults = SearchServers(name);
            foreach (var server in searchResults)
            {
                if (server.TryGetValue("name", out var nameEl) &&
                    nameEl.ValueKind == JsonValueKind.String &&
                    nameEl.GetString() == name)
                {
                    var id = server.TryGetValue("id", out var idEl) ? idEl.GetString() : null;
                    if (id != null)
                        return GetServerInfo(id);
                }
            }
        }
        catch { }
        return null;
    }

    /// <summary>Find a server by exact name match or server ID.</summary>
    public Dictionary<string, JsonElement>? FindServerByReference(string reference)
    {
        // Strategy 1: Try as UUID
        if (reference.Length == 36 && reference.Count(c => c == '-') == 4)
        {
            try { return GetServerInfo(reference); }
            catch { }
        }

        // Strategy 2: Search API
        try
        {
            var searchResults = SearchServers(reference);
            foreach (var server in searchResults)
            {
                var serverName = server.TryGetValue("name", out var nameEl) && nameEl.ValueKind == JsonValueKind.String
                    ? nameEl.GetString() ?? ""
                    : "";

                if (serverName == reference || IsServerMatch(reference, serverName))
                {
                    var id = server.TryGetValue("id", out var idEl) ? idEl.GetString() : null;
                    if (id != null)
                        return GetServerInfo(id);
                }
            }
        }
        catch { }

        return null;
    }

    private string ExtractRepositoryName(string reference)
        => reference.Contains('/') ? reference.Split('/').Last() : reference;

    private bool IsServerMatch(string reference, string serverName)
    {
        if (reference == serverName) return true;
        return ExtractRepositoryName(reference) == ExtractRepositoryName(serverName);
    }

    private static List<Dictionary<string, JsonElement>> ExtractServers(JsonElement root)
    {
        var servers = new List<Dictionary<string, JsonElement>>();
        if (!root.TryGetProperty("servers", out var rawServers) || rawServers.ValueKind != JsonValueKind.Array)
            return servers;

        foreach (var item in rawServers.EnumerateArray())
        {
            if (item.TryGetProperty("server", out var serverProp))
                servers.Add(JsonElementToDict(serverProp));
            else
                servers.Add(JsonElementToDict(item));
        }
        return servers;
    }

    private static Dictionary<string, JsonElement> JsonElementToDict(JsonElement element)
    {
        var dict = new Dictionary<string, JsonElement>();
        if (element.ValueKind == JsonValueKind.Object)
        {
            foreach (var prop in element.EnumerateObject())
                dict[prop.Name] = prop.Value.Clone();
        }
        return dict;
    }

    public void Dispose()
    {
        _httpClient.Dispose();
        GC.SuppressFinalize(this);
    }
}

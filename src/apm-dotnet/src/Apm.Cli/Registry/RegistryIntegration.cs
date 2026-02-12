using System.Text.Json;
using System.Text.Json.Nodes;
using Apm.Cli.Utils;

namespace Apm.Cli.Registry;

/// <summary>Integration class for connecting registry discovery to package manager.</summary>
public class RegistryIntegration : IDisposable
{
    private readonly RegistryClient _client;

    /// <param name="registryUrl">Optional registry URL override.</param>
    public RegistryIntegration(string? registryUrl = null)
    {
        _client = new RegistryClient(registryUrl);
    }

    /// <summary>List all available packages in the registry.</summary>
    public List<Dictionary<string, JsonElement>> ListAvailablePackages()
    {
        var (servers, _) = _client.ListServers();
        return servers.Select(ServerToPackage).ToList();
    }

    /// <summary>Search for packages in the registry.</summary>
    public List<Dictionary<string, JsonElement>> SearchPackages(string query)
    {
        var servers = _client.SearchServers(query);
        return servers.Select(ServerToPackage).ToList();
    }

    /// <summary>Get detailed information about a specific package.</summary>
    /// <exception cref="ArgumentException">If the package is not found.</exception>
    public Dictionary<string, JsonElement> GetPackageInfo(string name)
    {
        var serverInfo = _client.FindServerByReference(name)
            ?? throw new ArgumentException($"Package '{name}' not found in registry");
        return ServerToPackageDetail(serverInfo);
    }

    /// <summary>Get the latest version of a package.</summary>
    /// <exception cref="ArgumentException">If the package has no versions.</exception>
    public string GetLatestVersion(string name)
    {
        var packageInfo = GetPackageInfo(name);

        if (packageInfo.TryGetValue("version_detail", out var vd) && vd.ValueKind == JsonValueKind.Object)
        {
            if (vd.TryGetProperty("version", out var v) && v.ValueKind == JsonValueKind.String)
                return v.GetString()!;
        }

        if (packageInfo.TryGetValue("packages", out var pkgs) && pkgs.ValueKind == JsonValueKind.Array)
        {
            foreach (var pkg in pkgs.EnumerateArray())
            {
                if (pkg.TryGetProperty("version", out var pv) && pv.ValueKind == JsonValueKind.String)
                    return pv.GetString()!;
            }
        }

        if (packageInfo.TryGetValue("versions", out var versions) && versions.ValueKind == JsonValueKind.Array)
        {
            var last = versions.EnumerateArray().LastOrDefault();
            if (last.ValueKind == JsonValueKind.Object &&
                last.TryGetProperty("version", out var lv) && lv.ValueKind == JsonValueKind.String)
                return lv.GetString()!;
        }

        throw new ArgumentException($"Package '{name}' has no versions");
    }

    private static Dictionary<string, JsonElement> ServerToPackage(Dictionary<string, JsonElement> server)
    {
        var package = new Dictionary<string, object?>
        {
            ["id"] = GetStringValue(server, "id", ""),
            ["name"] = GetStringValue(server, "name", "Unknown"),
            ["description"] = GetStringValue(server, "description", "No description available")
        };

        if (server.ContainsKey("repository"))
            package["repository"] = server["repository"];
        if (server.ContainsKey("version_detail"))
            package["version_detail"] = server["version_detail"];

        return SerializeToJsonElements(package);
    }

    private static Dictionary<string, JsonElement> ServerToPackageDetail(Dictionary<string, JsonElement> server)
    {
        var package = ServerToPackage(server);

        foreach (var key in new[] { "packages", "remotes", "package_canonical" })
        {
            if (server.TryGetValue(key, out var val))
                package[key] = val;
        }

        if (server.TryGetValue("version_detail", out var vd) && vd.ValueKind == JsonValueKind.Object)
        {
            var versionNode = new JsonObject
            {
                ["version"] = vd.TryGetProperty("version", out var v) ? v.GetString() ?? "latest" : "latest",
                ["release_date"] = vd.TryGetProperty("release_date", out var rd) ? rd.GetString() ?? "" : "",
                ["is_latest"] = vd.TryGetProperty("is_latest", out var il) && il.GetBoolean()
            };

            package["versions"] = JsonSerializationHelper.ToJsonElement(new JsonArray(versionNode));
        }

        return package;
    }

    private static string GetStringValue(Dictionary<string, JsonElement> dict, string key, string defaultValue)
    {
        if (dict.TryGetValue(key, out var el) && el.ValueKind == JsonValueKind.String)
            return el.GetString() ?? defaultValue;
        return defaultValue;
    }

    private static Dictionary<string, JsonElement> SerializeToJsonElements(Dictionary<string, object?> data)
    {
        var result = new Dictionary<string, JsonElement>();
        foreach (var (key, value) in data)
        {
            if (value is JsonElement je)
                result[key] = je;
            else
                result[key] = JsonSerializationHelper.ToJsonElement(JsonSerializationHelper.ToJsonNode(value));
        }
        return result;
    }

    public void Dispose()
    {
        _client.Dispose();
        GC.SuppressFinalize(this);
    }
}

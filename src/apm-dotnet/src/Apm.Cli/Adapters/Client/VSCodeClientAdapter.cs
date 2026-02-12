using System.Text.Json;
using System.Text.Json.Nodes;
using Apm.Cli.Registry;
using Apm.Cli.Utils;

namespace Apm.Cli.Adapters.Client;

/// <summary>
/// VSCode implementation of MCP client adapter.
/// Manages MCP server configuration via .vscode/mcp.json in the repository.
/// </summary>
public class VSCodeClientAdapter : IClientAdapter
{
    private static readonly JsonSerializerOptions WriteOptions = new() { WriteIndented = true };
    private readonly RegistryClient _registryClient;

    public VSCodeClientAdapter(string? registryUrl = null)
    {
        _registryClient = new RegistryClient(registryUrl);
    }

    public string GetConfigPath()
    {
        var repoRoot = Directory.GetCurrentDirectory();
        var vscodeDir = Path.Combine(repoRoot, ".vscode");

        try
        {
            if (!Directory.Exists(vscodeDir))
                Directory.CreateDirectory(vscodeDir);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Warning: Could not create .vscode directory: {ex.Message}");
        }

        return Path.Combine(vscodeDir, "mcp.json");
    }

    public bool UpdateConfig(Dictionary<string, object?> newConfig)
    {
        var configPath = GetConfigPath();
        try
        {
            var json = JsonSerializationHelper.DictToJsonObject(newConfig).ToJsonString(WriteOptions);
            File.WriteAllText(configPath, json);
            return true;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error updating VSCode MCP configuration: {ex.Message}");
            return false;
        }
    }

    public Dictionary<string, object?> GetCurrentConfig()
    {
        var configPath = GetConfigPath();
        try
        {
            if (!File.Exists(configPath))
                return new Dictionary<string, object?>();

            var text = File.ReadAllText(configPath);
            var node = JsonNode.Parse(text)?.AsObject();
            if (node is null) return new Dictionary<string, object?>();

            var result = new Dictionary<string, object?>();
            foreach (var kvp in node)
                result[kvp.Key] = kvp.Value?.DeepClone();
            return result;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error reading VSCode MCP configuration: {ex.Message}");
            return new Dictionary<string, object?>();
        }
    }

    public bool ConfigureMcpServer(
        string serverUrl,
        string? serverName = null,
        bool enabled = true,
        Dictionary<string, string>? envOverrides = null,
        Dictionary<string, Dictionary<string, object?>>? serverInfoCache = null,
        Dictionary<string, string>? runtimeVars = null)
    {
        if (string.IsNullOrWhiteSpace(serverUrl))
        {
            Console.WriteLine("Error: serverUrl cannot be empty");
            return false;
        }

        try
        {
            Dictionary<string, JsonElement>? serverInfo = null;
            if (serverInfoCache != null && serverInfoCache.TryGetValue(serverUrl, out var cached))
                serverInfo = ConvertCacheEntry(cached);
            else
                serverInfo = _registryClient.FindServerByReference(serverUrl);

            if (serverInfo == null || serverInfo.Count == 0)
                throw new ArgumentException($"Failed to retrieve server details for '{serverUrl}'. Server not found in registry.");

            var (serverConfig, inputVars) = FormatServerConfig(serverInfo);

            if (serverConfig.Count == 0)
            {
                Console.WriteLine($"Unable to configure server: {serverUrl}");
                return false;
            }

            var configKey = serverName ?? serverUrl;

            // Work directly with JsonNode for reliable nested manipulation
            var configPath = GetConfigPath();
            JsonObject root;
            try
            {
                if (File.Exists(configPath))
                {
                    var text = File.ReadAllText(configPath);
                    root = JsonNode.Parse(text)?.AsObject() ?? new JsonObject();
                }
                else
                    root = new JsonObject();
            }
            catch { root = new JsonObject(); }

            if (root["servers"] is not JsonObject servers)
            {
                servers = new JsonObject();
                root["servers"] = servers;
            }
            if (root["inputs"] is not JsonArray inputs)
            {
                inputs = new JsonArray();
                root["inputs"] = inputs;
            }

            servers[configKey] = JsonSerializationHelper.DictToJsonObject(serverConfig);

            var existingIds = new HashSet<string>();
            foreach (var item in inputs)
            {
                if (item is JsonObject obj && obj["id"]?.GetValue<string>() is string id)
                    existingIds.Add(id);
            }
            foreach (var iv in inputVars)
            {
                if (iv.TryGetValue("id", out var idVal) && idVal is string idStr && !existingIds.Contains(idStr))
                {
                    inputs.Add(JsonSerializationHelper.DictToJsonObject(iv));
                    existingIds.Add(idStr);
                }
            }

            File.WriteAllText(configPath, root.ToJsonString(WriteOptions));
            Console.WriteLine($"Successfully configured MCP server '{configKey}' for VS Code");
            return true;
        }
        catch (ArgumentException)
        {
            throw;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error configuring MCP server: {ex.Message}");
            return false;
        }
    }

    private static (Dictionary<string, object?> ServerConfig, List<Dictionary<string, object?>> InputVars) FormatServerConfig(
        Dictionary<string, JsonElement> serverInfo)
    {
        var serverConfig = new Dictionary<string, object?>();
        var inputVars = new List<Dictionary<string, object?>>();

        if (serverInfo.TryGetValue("packages", out var pkgsEl) && pkgsEl.ValueKind == JsonValueKind.Array)
        {
            var packages = pkgsEl.EnumerateArray().ToList();
            if (packages.Count > 0)
            {
                var package = packages[0];
                var runtimeHint = GetStr(package, "runtime_hint");
                var registryName = GetStr(package, "registry_name").ToLowerInvariant();

                if (runtimeHint == "npx" || registryName.Contains("npm"))
                {
                    var args = ExtractRequiredRuntimeArgs(package);
                    if (args.Count == 0)
                    {
                        var name = GetStr(package, "name");
                        if (!string.IsNullOrEmpty(name)) args.Add(name);
                    }
                    serverConfig["type"] = "stdio";
                    serverConfig["command"] = "npx";
                    serverConfig["args"] = args;
                }
                else if (runtimeHint == "docker")
                {
                    var args = ExtractRequiredRuntimeArgs(package);
                    if (args.Count == 0)
                        args = new List<object?> { "run", "-i", "--rm", GetStr(package, "name") };
                    serverConfig["type"] = "stdio";
                    serverConfig["command"] = "docker";
                    serverConfig["args"] = args;
                }
                else if (runtimeHint is "uvx" or "pip" or "python"
                         || runtimeHint.Contains("python")
                         || registryName == "pypi")
                {
                    var command = runtimeHint switch
                    {
                        "uvx" => "uvx",
                        "python" or "pip" => "python3",
                        _ when runtimeHint.Contains("python") => runtimeHint,
                        _ => "python3"
                    };
                    var args = ExtractRequiredRuntimeArgs(package);
                    if (args.Count == 0)
                    {
                        var pkgName = GetStr(package, "name");
                        if (runtimeHint == "uvx")
                        {
                            var mod = pkgName.Replace("mcp-server-", "");
                            args.Add($"mcp-server-{mod}");
                        }
                        else
                        {
                            var mod = pkgName.Replace("mcp-server-", "").Replace("-", "_");
                            args.Add("-m");
                            args.Add($"mcp_server_{mod}");
                        }
                    }
                    serverConfig["type"] = "stdio";
                    serverConfig["command"] = command;
                    serverConfig["args"] = args;
                }

                // Environment variables → input variable references
                if (package.TryGetProperty("environment_variables", out var envEl) && envEl.ValueKind == JsonValueKind.Array)
                {
                    var env = new Dictionary<string, object?>();
                    foreach (var envVar in envEl.EnumerateArray())
                    {
                        var name = GetStr(envVar, "name");
                        if (string.IsNullOrEmpty(name)) continue;

                        var inputVarName = name.ToLowerInvariant().Replace("_", "-");
                        env[name] = $"${{input:{inputVarName}}}";

                        inputVars.Add(new Dictionary<string, object?>
                        {
                            ["type"] = "promptString",
                            ["id"] = inputVarName,
                            ["description"] = GetStr(envVar, "description", $"{name} for MCP server"),
                            ["password"] = true
                        });
                    }
                    if (env.Count > 0) serverConfig["env"] = env;
                }
            }
        }

        // Fallback: SSE / remotes
        if (serverConfig.Count == 0)
        {
            if (serverInfo.TryGetValue("sse_endpoint", out var sseEl) && sseEl.ValueKind == JsonValueKind.String)
            {
                serverConfig["type"] = "sse";
                serverConfig["url"] = sseEl.GetString() ?? "";
                if (serverInfo.TryGetValue("sse_headers", out var hdr) && hdr.ValueKind == JsonValueKind.Object)
                {
                    var headers = new Dictionary<string, object?>();
                    foreach (var p in hdr.EnumerateObject())
                        headers[p.Name] = p.Value.ToString();
                    serverConfig["headers"] = headers;
                }
            }
            else if (serverInfo.TryGetValue("remotes", out var remotesEl) && remotesEl.ValueKind == JsonValueKind.Array)
            {
                foreach (var remote in remotesEl.EnumerateArray())
                {
                    if (GetStr(remote, "transport_type") == "sse")
                    {
                        serverConfig["type"] = "sse";
                        serverConfig["url"] = GetStr(remote, "url");
                        if (remote.TryGetProperty("headers", out var rh) && rh.ValueKind == JsonValueKind.Object)
                        {
                            var headers = new Dictionary<string, object?>();
                            foreach (var p in rh.EnumerateObject())
                                headers[p.Name] = p.Value.ToString();
                            serverConfig["headers"] = headers;
                        }
                        break;
                    }
                }
            }
            else
            {
                var srvName = serverInfo.TryGetValue("name", out var n) && n.ValueKind == JsonValueKind.String
                    ? n.GetString() ?? "unknown" : "unknown";
                throw new ArgumentException(
                    $"MCP server has incomplete configuration in registry - no package information or remote endpoints available. Server: {srvName}");
            }
        }

        return (serverConfig, inputVars);
    }

    private static List<object?> ExtractRequiredRuntimeArgs(JsonElement package)
    {
        var args = new List<object?>();
        if (package.TryGetProperty("runtime_arguments", out var argsEl) && argsEl.ValueKind == JsonValueKind.Array)
        {
            foreach (var arg in argsEl.EnumerateArray())
            {
                if (arg.TryGetProperty("is_required", out var req) && req.ValueKind == JsonValueKind.True
                    && arg.TryGetProperty("value_hint", out var hint) && hint.ValueKind == JsonValueKind.String)
                {
                    args.Add(hint.GetString());
                }
            }
        }
        return args;
    }

    private static string GetStr(JsonElement el, string prop, string def = "")
    {
        if (el.TryGetProperty(prop, out var v) && v.ValueKind == JsonValueKind.String)
            return v.GetString() ?? def;
        return def;
    }

    private static Dictionary<string, JsonElement> ConvertCacheEntry(Dictionary<string, object?> entry)
    {
        var result = new Dictionary<string, JsonElement>();
        foreach (var (key, value) in entry)
        {
            if (value is JsonElement je)
                result[key] = je;
            else
                result[key] = JsonSerializationHelper.ToJsonElement(JsonSerializationHelper.ToJsonNode(value));
        }
        return result;
    }
}

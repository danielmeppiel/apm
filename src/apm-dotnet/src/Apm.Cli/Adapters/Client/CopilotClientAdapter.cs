using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Apm.Cli.Registry;
using Apm.Cli.Utils;

namespace Apm.Cli.Adapters.Client;

/// <summary>
/// GitHub Copilot CLI implementation of MCP client adapter.
/// Manages MCP server configuration via ~/.copilot/mcp-config.json.
/// </summary>
public class CopilotClientAdapter : IClientAdapter
{
    private static readonly JsonSerializerOptions WriteOptions = new() { WriteIndented = true };
    private readonly RegistryClient _registryClient;

    public CopilotClientAdapter(string? registryUrl = null)
    {
        _registryClient = new RegistryClient(registryUrl);
    }

    public string GetConfigPath()
    {
        var copilotDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".copilot");
        return Path.Combine(copilotDir, "mcp-config.json");
    }

    public bool UpdateConfig(Dictionary<string, object?> configUpdates)
    {
        var current = GetCurrentConfig();

        if (!current.ContainsKey("mcpServers"))
            current["mcpServers"] = new Dictionary<string, object?>();

        if (current["mcpServers"] is Dictionary<string, object?> servers)
        {
            foreach (var kvp in configUpdates)
                servers[kvp.Key] = kvp.Value;
        }

        var configPath = GetConfigPath();
        var dir = Path.GetDirectoryName(configPath);
        if (dir is not null && !Directory.Exists(dir))
            Directory.CreateDirectory(dir);

        try
        {
            var json = JsonSerializationHelper.DictToJsonObject(current).ToJsonString(WriteOptions);
            File.WriteAllText(configPath, json);
            return true;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error updating Copilot configuration: {ex.Message}");
            return false;
        }
    }

    public Dictionary<string, object?> GetCurrentConfig()
    {
        var configPath = GetConfigPath();
        if (!File.Exists(configPath))
            return new Dictionary<string, object?>();

        try
        {
            var text = File.ReadAllText(configPath);
            var node = JsonNode.Parse(text)?.AsObject();
            if (node is null) return new Dictionary<string, object?>();

            var result = new Dictionary<string, object?>();
            foreach (var kvp in node)
                result[kvp.Key] = kvp.Value?.DeepClone();
            return result;
        }
        catch
        {
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
            {
                Console.WriteLine($"Error: MCP server '{serverUrl}' not found in registry");
                return false;
            }

            // Determine config key
            string configKey;
            if (serverName != null)
                configKey = serverName;
            else if (serverUrl.Contains('/'))
                configKey = serverUrl.Split('/').Last();
            else
                configKey = serverUrl;

            var serverConfig = FormatServerConfig(serverInfo, envOverrides, runtimeVars);

            // Write directly with JsonNode for reliable nested manipulation
            var configPath = GetConfigPath();
            var dir = Path.GetDirectoryName(configPath);
            if (dir is not null && !Directory.Exists(dir))
                Directory.CreateDirectory(dir);

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

            if (root["mcpServers"] is not JsonObject mcpServers)
            {
                mcpServers = new JsonObject();
                root["mcpServers"] = mcpServers;
            }

            mcpServers[configKey] = JsonSerializationHelper.DictToJsonObject(serverConfig);
            File.WriteAllText(configPath, root.ToJsonString(WriteOptions));

            Console.WriteLine($"Successfully configured MCP server '{configKey}' for Copilot CLI");
            return true;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error configuring MCP server: {ex.Message}");
            return false;
        }
    }

    private Dictionary<string, object?> FormatServerConfig(
        Dictionary<string, JsonElement> serverInfo,
        Dictionary<string, string>? envOverrides,
        Dictionary<string, string>? runtimeVars)
    {
        runtimeVars ??= new Dictionary<string, string>();

        var config = new Dictionary<string, object?>
        {
            ["type"] = "local",
            ["tools"] = new List<object?> { "*" },
            ["id"] = serverInfo.TryGetValue("id", out var idEl) && idEl.ValueKind == JsonValueKind.String
                ? idEl.GetString() ?? "" : ""
        };

        // Check for remote endpoints first
        if (serverInfo.TryGetValue("remotes", out var remotesEl)
            && remotesEl.ValueKind == JsonValueKind.Array
            && remotesEl.GetArrayLength() > 0)
        {
            var remote = remotesEl.EnumerateArray().First();
            config = new Dictionary<string, object?>
            {
                ["type"] = "http",
                ["url"] = GetStr(remote, "url"),
                ["tools"] = new List<object?> { "*" },
                ["id"] = serverInfo.TryGetValue("id", out var rid) && rid.ValueKind == JsonValueKind.String
                    ? rid.GetString() ?? "" : ""
            };

            // GitHub server auth
            var srvName = serverInfo.TryGetValue("name", out var nEl) && nEl.ValueKind == JsonValueKind.String
                ? nEl.GetString() ?? "" : "";
            if (IsGitHubServer(srvName, GetStr(remote, "url")))
            {
                var token = Environment.GetEnvironmentVariable("GITHUB_PERSONAL_ACCESS_TOKEN");
                if (!string.IsNullOrEmpty(token))
                {
                    config["headers"] = new Dictionary<string, object?>
                    {
                        ["Authorization"] = $"Bearer {token}"
                    };
                }
            }

            // Additional headers from registry
            if (remote.TryGetProperty("headers", out var headersEl) && headersEl.ValueKind == JsonValueKind.Array)
            {
                if (config["headers"] is not Dictionary<string, object?> headers)
                {
                    headers = new Dictionary<string, object?>();
                    config["headers"] = headers;
                }
                foreach (var header in headersEl.EnumerateArray())
                {
                    var hName = GetStr(header, "name");
                    var hValue = GetStr(header, "value");
                    if (!string.IsNullOrEmpty(hName) && !string.IsNullOrEmpty(hValue))
                        headers[hName] = ResolveEnvVariable(hName, hValue, envOverrides);
                }
            }

            return config;
        }

        // Check packages
        if (!serverInfo.TryGetValue("packages", out var pkgsEl) || pkgsEl.ValueKind != JsonValueKind.Array)
        {
            var srvName = serverInfo.TryGetValue("name", out var n) && n.ValueKind == JsonValueKind.String
                ? n.GetString() ?? "unknown" : "unknown";
            throw new InvalidOperationException(
                $"MCP server has incomplete configuration in registry - no package information or remote endpoints available. Server: {srvName}");
        }

        var packages = pkgsEl.EnumerateArray().ToList();
        if (packages.Count == 0) return config;

        var package = SelectBestPackage(packages);
        if (package.ValueKind != JsonValueKind.Object) return config;

        var registryName = GetStr(package, "registry_name");
        var packageName = GetStr(package, "name");
        var runtimeHint = GetStr(package, "runtime_hint");

        // Resolve environment variables
        var envVars = package.TryGetProperty("environment_variables", out var evEl) && evEl.ValueKind == JsonValueKind.Array
            ? evEl : (JsonElement?)null;
        var resolvedEnv = envVars.HasValue
            ? ProcessEnvironmentVariables(envVars.Value, envOverrides)
            : new Dictionary<string, string>();

        // Process arguments
        var runtimeArgs = package.TryGetProperty("runtime_arguments", out var raEl) && raEl.ValueKind == JsonValueKind.Array
            ? ProcessArguments(raEl, resolvedEnv, runtimeVars) : new List<string>();
        var packageArgs = package.TryGetProperty("package_arguments", out var paEl) && paEl.ValueKind == JsonValueKind.Array
            ? ProcessArguments(paEl, resolvedEnv, runtimeVars) : new List<string>();

        var allArgs = runtimeArgs.Concat(packageArgs).ToList();

        switch (registryName)
        {
            case "npm":
                config["command"] = string.IsNullOrEmpty(runtimeHint) ? "npx" : runtimeHint;
                config["args"] = new List<object?> { "-y", packageName }.Concat(allArgs.Cast<object?>()).ToList();
                break;
            case "docker":
                config["command"] = "docker";
                config["args"] = (runtimeArgs.Count > 0
                    ? InjectEnvVarsIntoDockerArgs(runtimeArgs, resolvedEnv)
                    : InjectEnvVarsIntoDockerArgs(new List<string> { "run", "-i", "--rm", packageName }, resolvedEnv))
                    .Cast<object?>().ToList();
                break;
            case "pypi":
                config["command"] = string.IsNullOrEmpty(runtimeHint) ? "uvx" : runtimeHint;
                config["args"] = new List<object?> { packageName }.Concat(allArgs.Cast<object?>()).ToList();
                break;
            case "homebrew":
                config["command"] = packageName.Contains('/') ? packageName.Split('/').Last() : packageName;
                config["args"] = allArgs.Cast<object?>().ToList();
                break;
            default:
                config["command"] = string.IsNullOrEmpty(runtimeHint) ? packageName : runtimeHint;
                config["args"] = allArgs.Cast<object?>().ToList();
                break;
        }

        if (resolvedEnv.Count > 0)
        {
            var envDict = new Dictionary<string, object?>();
            foreach (var kvp in resolvedEnv) envDict[kvp.Key] = kvp.Value;
            config["env"] = envDict;
        }

        return config;
    }

    private static Dictionary<string, string> ProcessEnvironmentVariables(
        JsonElement envVarsArray, Dictionary<string, string>? envOverrides)
    {
        var resolved = new Dictionary<string, string>();
        envOverrides ??= new Dictionary<string, string>();
        var skipPrompting = envOverrides.Count > 0
            || Environment.GetEnvironmentVariable("APM_E2E_TESTS") == "1";

        var defaultGitHubEnv = new Dictionary<string, string>
        {
            ["GITHUB_TOOLSETS"] = "context",
            ["GITHUB_DYNAMIC_TOOLSETS"] = "1"
        };

        var emptyValueVars = new HashSet<string>();
        foreach (var kvp in envOverrides)
        {
            if (string.IsNullOrWhiteSpace(kvp.Value))
                emptyValueVars.Add(kvp.Key);
        }

        foreach (var envVar in envVarsArray.EnumerateArray())
        {
            if (envVar.ValueKind != JsonValueKind.Object) continue;
            var name = GetStr(envVar, "name");
            if (string.IsNullOrEmpty(name)) continue;

            var required = !envVar.TryGetProperty("required", out var reqEl)
                           || reqEl.ValueKind != JsonValueKind.False;

            string? value = envOverrides.TryGetValue(name, out var ov) && !string.IsNullOrWhiteSpace(ov) ? ov : null;
            value ??= Environment.GetEnvironmentVariable(name);

            if (!string.IsNullOrWhiteSpace(value))
                resolved[name] = value;
            else if (emptyValueVars.Contains(name) && defaultGitHubEnv.ContainsKey(name))
                resolved[name] = defaultGitHubEnv[name];
            else if (!required && defaultGitHubEnv.ContainsKey(name))
                resolved[name] = defaultGitHubEnv[name];
            else if (skipPrompting && defaultGitHubEnv.ContainsKey(name))
                resolved[name] = defaultGitHubEnv[name];
        }

        return resolved;
    }

    private static List<string> ProcessArguments(
        JsonElement argsArray,
        Dictionary<string, string> resolvedEnv,
        Dictionary<string, string> runtimeVars)
    {
        var processed = new List<string>();
        foreach (var arg in argsArray.EnumerateArray())
        {
            if (arg.ValueKind == JsonValueKind.Object)
            {
                var argType = GetStr(arg, "type");
                if (argType == "positional")
                {
                    var value = GetStr(arg, "value");
                    if (string.IsNullOrEmpty(value)) value = GetStr(arg, "default");
                    if (!string.IsNullOrEmpty(value))
                        processed.Add(ResolveVariablePlaceholders(value, resolvedEnv, runtimeVars));
                }
                else if (argType == "named")
                {
                    var name = GetStr(arg, "name");
                    var value = GetStr(arg, "value");
                    if (string.IsNullOrEmpty(value)) value = GetStr(arg, "default");
                    if (!string.IsNullOrEmpty(name))
                    {
                        processed.Add(name);
                        if (!string.IsNullOrEmpty(value) && value != name && !value.StartsWith("-"))
                            processed.Add(ResolveVariablePlaceholders(value, resolvedEnv, runtimeVars));
                    }
                }
            }
            else if (arg.ValueKind == JsonValueKind.String)
            {
                var val = arg.GetString() ?? "";
                processed.Add(ResolveVariablePlaceholders(val, resolvedEnv, runtimeVars));
            }
        }
        return processed;
    }

    private static string ResolveVariablePlaceholders(
        string value, Dictionary<string, string> resolvedEnv, Dictionary<string, string> runtimeVars)
    {
        if (string.IsNullOrEmpty(value)) return value;

        var processed = Regex.Replace(value, @"<([A-Z_][A-Z0-9_]*)>", m =>
            resolvedEnv.TryGetValue(m.Groups[1].Value, out var v) ? v : m.Value);

        processed = Regex.Replace(processed, @"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", m =>
            runtimeVars.TryGetValue(m.Groups[1].Value, out var v) ? v : m.Value);

        return processed;
    }

    private static string ResolveEnvVariable(string name, string value, Dictionary<string, string>? envOverrides)
    {
        envOverrides ??= new Dictionary<string, string>();
        var processed = value;
        foreach (Match m in Regex.Matches(value, @"<([A-Z_][A-Z0-9_]*)>"))
        {
            var envName = m.Groups[1].Value;
            var envValue = envOverrides.TryGetValue(envName, out var ov) ? ov : null;
            envValue ??= Environment.GetEnvironmentVariable(envName);
            if (!string.IsNullOrEmpty(envValue))
                processed = processed.Replace(m.Value, envValue);
        }
        return processed;
    }

    private static List<string> InjectEnvVarsIntoDockerArgs(List<string> dockerArgs, Dictionary<string, string> envVars)
    {
        if (envVars.Count == 0) return dockerArgs;

        var result = new List<string>();
        var hasInteractive = dockerArgs.Contains("-i") || dockerArgs.Contains("--interactive");
        var hasRm = dockerArgs.Contains("--rm");

        int i = 0;
        while (i < dockerArgs.Count)
        {
            var arg = dockerArgs[i];
            result.Add(arg);

            if (arg == "run")
            {
                if (!hasInteractive) result.Add("-i");
                if (!hasRm) result.Add("--rm");
            }

            if (envVars.ContainsKey(arg))
            {
                result.RemoveAt(result.Count - 1);
                result.AddRange(new[] { "-e", $"{arg}={envVars[arg]}" });
            }
            else if (arg == "-e" && i + 1 < dockerArgs.Count)
            {
                var next = dockerArgs[i + 1];
                if (envVars.TryGetValue(next, out var ev))
                {
                    result.Add($"{next}={ev}");
                    i++;
                }
                else
                {
                    result.Add(next);
                    i++;
                }
            }
            i++;
        }

        // Add remaining env vars not in template
        var templateVars = new HashSet<string>(dockerArgs.Where(a => envVars.ContainsKey(a)));
        foreach (var (envName, envValue) in envVars)
        {
            if (!templateVars.Contains(envName))
            {
                var insertPos = result.Count;
                for (var idx = 0; idx < result.Count; idx++)
                {
                    if (result[idx] == "run")
                    {
                        insertPos = Math.Min(result.Count - 1, idx + 1);
                        break;
                    }
                }
                result.Insert(insertPos, "-e");
                result.Insert(insertPos + 1, $"{envName}={envValue}");
            }
        }

        return result;
    }

    private static JsonElement SelectBestPackage(List<JsonElement> packages)
    {
        var priority = new[] { "npm", "docker", "pypi", "homebrew" };
        foreach (var reg in priority)
        {
            foreach (var pkg in packages)
            {
                if (GetStr(pkg, "registry_name") == reg)
                    return pkg;
            }
        }
        return packages[0];
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

    /// <summary>
    /// Determine if a server is a GitHub MCP server using allowlist and hostname validation.
    /// </summary>
    internal static bool IsGitHubServer(string? serverName, string? url)
    {
        var allowedNames = new[] { "github-mcp-server", "github", "github-mcp", "github-copilot-mcp-server" };

        if (!string.IsNullOrEmpty(serverName) &&
            allowedNames.Any(n => string.Equals(n, serverName, StringComparison.OrdinalIgnoreCase)))
        {
            return true;
        }

        if (!string.IsNullOrEmpty(url))
        {
            try
            {
                var parsed = new Uri(url);
                if (parsed.Host is { Length: > 0 } host && GitHubHost.IsGitHubHostname(host))
                    return true;
            }
            catch
            {
                // URL parsing failed — not a GitHub server
            }
        }

        return false;
    }
}

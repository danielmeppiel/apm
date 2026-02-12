using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Apm.Cli.Registry;
using Apm.Cli.Utils;
using Tomlyn;
using Tomlyn.Model;

namespace Apm.Cli.Adapters.Client;

/// <summary>
/// OpenAI Codex CLI implementation of MCP client adapter.
/// Manages MCP server configuration via ~/.codex/config.toml.
/// </summary>
public class CodexClientAdapter : IClientAdapter
{
    private readonly RegistryClient _registryClient;

    public CodexClientAdapter(string? registryUrl = null)
    {
        _registryClient = new RegistryClient(registryUrl);
    }

    public string GetConfigPath()
    {
        var codexDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".codex");
        return Path.Combine(codexDir, "config.toml");
    }

    public bool UpdateConfig(Dictionary<string, object?> configUpdates)
    {
        var current = GetCurrentConfig();

        if (!current.ContainsKey("mcp_servers"))
            current["mcp_servers"] = new Dictionary<string, object?>();

        if (current["mcp_servers"] is Dictionary<string, object?> servers)
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
            var tomlModel = DictionaryToTomlTable(current);
            var tomlText = Toml.FromModel(tomlModel);
            File.WriteAllText(configPath, tomlText);
            return true;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error updating Codex configuration: {ex.Message}");
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
            var model = Toml.ToModel(text);
            return TomlTableToDictionary(model);
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

            // Reject remote-only servers
            var hasRemotes = serverInfo.TryGetValue("remotes", out var remotesEl)
                             && remotesEl.ValueKind == JsonValueKind.Array
                             && remotesEl.GetArrayLength() > 0;
            var hasPackages = serverInfo.TryGetValue("packages", out var pkgsEl)
                              && pkgsEl.ValueKind == JsonValueKind.Array
                              && pkgsEl.GetArrayLength() > 0;

            if (hasRemotes && !hasPackages)
            {
                Console.WriteLine($"⚠️  Warning: MCP server '{serverUrl}' is a remote server (SSE type)");
                Console.WriteLine("   Codex CLI only supports local servers with command/args configuration");
                Console.WriteLine("   Remote servers are not supported by Codex CLI");
                Console.WriteLine("   Skipping installation for Codex CLI");
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
            UpdateConfig(new Dictionary<string, object?> { [configKey] = serverConfig });

            Console.WriteLine($"Successfully configured MCP server '{configKey}' for Codex CLI");
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
            ["command"] = "unknown",
            ["args"] = new List<object?>(),
            ["env"] = new Dictionary<string, object?>(),
            ["id"] = serverInfo.TryGetValue("id", out var idEl) && idEl.ValueKind == JsonValueKind.String
                ? idEl.GetString() ?? "" : ""
        };

        if (!serverInfo.TryGetValue("packages", out var pkgsEl) || pkgsEl.ValueKind != JsonValueKind.Array)
        {
            var srvName = serverInfo.TryGetValue("name", out var n) && n.ValueKind == JsonValueKind.String
                ? n.GetString() ?? "unknown" : "unknown";
            throw new InvalidOperationException(
                $"MCP server has no package information available in registry. Server: {srvName}");
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
                config["args"] = allArgs.Cast<object?>().ToList();
                break;
            case "docker":
                config["command"] = "docker";
                config["args"] = EnsureDockerEnvFlags(allArgs, resolvedEnv).Cast<object?>().ToList();
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
                    var flagName = GetStr(arg, "value");
                    if (!string.IsNullOrEmpty(flagName))
                    {
                        processed.Add(flagName);
                        var additional = GetStr(arg, "name");
                        if (!string.IsNullOrEmpty(additional) && additional != flagName && !additional.StartsWith("-"))
                            processed.Add(ResolveVariablePlaceholders(additional, resolvedEnv, runtimeVars));
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

        // Replace <TOKEN_NAME> with actual env values
        var processed = Regex.Replace(value, @"<([A-Z_][A-Z0-9_]*)>", m =>
            resolvedEnv.TryGetValue(m.Groups[1].Value, out var v) ? v : m.Value);

        // Replace {runtime_var} with actual runtime values
        processed = Regex.Replace(processed, @"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", m =>
            runtimeVars.TryGetValue(m.Groups[1].Value, out var v) ? v : m.Value);

        return processed;
    }

    private static List<string> EnsureDockerEnvFlags(List<string> baseArgs, Dictionary<string, string> envVars)
    {
        if (envVars.Count == 0) return baseArgs;

        var result = new List<string>();
        var existingEnvVars = new HashSet<string>();

        int i = 0;
        while (i < baseArgs.Count)
        {
            result.Add(baseArgs[i]);
            if (baseArgs[i] == "-e" && i + 1 < baseArgs.Count)
            {
                existingEnvVars.Add(baseArgs[i + 1]);
                result.Add(baseArgs[i + 1]);
                i += 2;
            }
            else
            {
                i++;
            }
        }

        // Insert missing -e flags before the image name (last non-flag arg)
        var imageName = result.Count > 0 && !result[^1].StartsWith("-") ? result[^1] : null;
        if (imageName != null)
        {
            result.RemoveAt(result.Count - 1);
            foreach (var envName in envVars.Keys.OrderBy(k => k))
            {
                if (!existingEnvVars.Contains(envName))
                    result.AddRange(new[] { "-e", envName });
            }
            result.Add(imageName);
        }
        else
        {
            foreach (var envName in envVars.Keys.OrderBy(k => k))
            {
                if (!existingEnvVars.Contains(envName))
                    result.AddRange(new[] { "-e", envName });
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

    private static Dictionary<string, object?> TomlTableToDictionary(TomlTable table)
    {
        var dict = new Dictionary<string, object?>();
        foreach (var kvp in table)
        {
            if (kvp.Value is TomlTable nested)
                dict[kvp.Key] = TomlTableToDictionary(nested);
            else
                dict[kvp.Key] = kvp.Value;
        }
        return dict;
    }

    private static TomlTable DictionaryToTomlTable(Dictionary<string, object?> dict)
    {
        var table = new TomlTable();
        foreach (var kvp in dict)
        {
            if (kvp.Value is Dictionary<string, object?> nested)
                table[kvp.Key] = DictionaryToTomlTable(nested);
            else if (kvp.Value is List<object?> list)
                table[kvp.Key] = ListToTomlArray(list);
            else if (kvp.Value is not null)
                table[kvp.Key] = kvp.Value;
        }
        return table;
    }

    private static TomlArray ListToTomlArray(List<object?> list)
    {
        var arr = new TomlArray();
        foreach (var item in list)
        {
            if (item is not null)
                arr.Add(item);
        }
        return arr;
    }
}

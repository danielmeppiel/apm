using System.Text.Json;
using Apm.Cli.Adapters.Client;
using Apm.Cli.Core;

namespace Apm.Cli.Registry;

/// <summary>Handles MCP server operations like conflict detection and installation status.</summary>
public class McpServerOperations : IDisposable
{
    private readonly RegistryClient _registryClient;

    /// <param name="registryUrl">Optional registry URL override.</param>
    public McpServerOperations(string? registryUrl = null)
    {
        _registryClient = new RegistryClient(registryUrl);
    }

    /// <summary>Check which MCP servers need installation across target runtimes.</summary>
    public List<string> CheckServersNeedingInstallation(List<string> targetRuntimes, List<string> serverReferences)
    {
        var serversNeedingInstallation = new HashSet<string>();

        foreach (var serverRef in serverReferences)
        {
            try
            {
                var serverInfo = _registryClient.FindServerByReference(serverRef);
                if (serverInfo == null)
                {
                    serversNeedingInstallation.Add(serverRef);
                    continue;
                }

                var serverId = serverInfo.TryGetValue("id", out var idEl) && idEl.ValueKind == JsonValueKind.String
                    ? idEl.GetString()
                    : null;
                if (serverId == null)
                {
                    serversNeedingInstallation.Add(serverRef);
                    continue;
                }

                var needsInstallation = false;
                foreach (var runtime in targetRuntimes)
                {
                    var installedIds = GetInstalledServerIds([runtime]);
                    if (!installedIds.Contains(serverId))
                    {
                        needsInstallation = true;
                        break;
                    }
                }

                if (needsInstallation)
                    serversNeedingInstallation.Add(serverRef);
            }
            catch
            {
                serversNeedingInstallation.Add(serverRef);
            }
        }

        return [.. serversNeedingInstallation];
    }

    private HashSet<string> GetInstalledServerIds(List<string> targetRuntimes)
    {
        var installedIds = new HashSet<string>();

        foreach (var runtime in targetRuntimes)
        {
            try
            {
                var client = ClientFactory.CreateClient(runtime);
                var config = client.GetCurrentConfig();

                var mcpServersKey = runtime == "codex" ? "mcp_servers" : "mcpServers";
                if (config.TryGetValue(mcpServersKey, out var serversObj) && serversObj is Dictionary<string, object?> mcpServers)
                {
                    foreach (var (_, serverConfig) in mcpServers)
                    {
                        if (serverConfig is Dictionary<string, object?> cfg)
                        {
                            string? serverId = null;
                            if (cfg.TryGetValue("id", out var id))
                                serverId = id?.ToString();
                            else if (runtime == "vscode")
                            {
                                if (cfg.TryGetValue("serverId", out var sid)) serverId = sid?.ToString();
                                else if (cfg.TryGetValue("server_id", out var sid2)) serverId = sid2?.ToString();
                            }

                            if (serverId != null)
                                installedIds.Add(serverId);
                        }
                    }
                }
            }
            catch
            {
                // Can't read runtime config — skip
            }
        }

        return installedIds;
    }

    /// <summary>Validate that all servers exist in the registry (fail-fast).</summary>
    public (List<string> Valid, List<string> Invalid) ValidateServersExist(List<string> serverReferences)
    {
        var valid = new List<string>();
        var invalid = new List<string>();

        foreach (var serverRef in serverReferences)
        {
            try
            {
                var serverInfo = _registryClient.FindServerByReference(serverRef);
                if (serverInfo != null)
                    valid.Add(serverRef);
                else
                    invalid.Add(serverRef);
            }
            catch
            {
                invalid.Add(serverRef);
            }
        }

        return (valid, invalid);
    }

    /// <summary>Batch fetch server info for all servers.</summary>
    public Dictionary<string, Dictionary<string, JsonElement>?> BatchFetchServerInfo(List<string> serverReferences)
    {
        var cache = new Dictionary<string, Dictionary<string, JsonElement>?>();
        foreach (var serverRef in serverReferences)
        {
            try
            {
                cache[serverRef] = _registryClient.FindServerByReference(serverRef);
            }
            catch
            {
                cache[serverRef] = null;
            }
        }
        return cache;
    }

    /// <summary>Collect runtime variables from runtime_arguments.variables fields.</summary>
    public Dictionary<string, string> CollectRuntimeVariables(
        List<string> serverReferences,
        Dictionary<string, Dictionary<string, JsonElement>?>? serverInfoCache = null)
    {
        serverInfoCache ??= BatchFetchServerInfo(serverReferences);
        var allRequiredVars = CollectVariablesFromPackages(serverReferences, serverInfoCache, "runtime_arguments");

        return allRequiredVars.Count > 0 ? PromptForVariables(allRequiredVars) : [];
    }

    /// <summary>Collect environment variables needed by the specified servers.</summary>
    public Dictionary<string, string> CollectEnvironmentVariables(
        List<string> serverReferences,
        Dictionary<string, Dictionary<string, JsonElement>?>? serverInfoCache = null)
    {
        serverInfoCache ??= BatchFetchServerInfo(serverReferences);
        var allRequiredVars = new Dictionary<string, Dictionary<string, object>>();

        foreach (var serverRef in serverReferences)
        {
            if (!serverInfoCache.TryGetValue(serverRef, out var serverInfo) || serverInfo == null)
                continue;

            try
            {
                // Check packages for environment variables
                if (serverInfo.TryGetValue("packages", out var pkgsEl) && pkgsEl.ValueKind == JsonValueKind.Array)
                {
                    foreach (var pkg in pkgsEl.EnumerateArray())
                    {
                        JsonElement envVars = default;
                        if (!pkg.TryGetProperty("environmentVariables", out envVars))
                            pkg.TryGetProperty("environment_variables", out envVars);

                        if (envVars.ValueKind == JsonValueKind.Array)
                        {
                            foreach (var envVar in envVars.EnumerateArray())
                            {
                                if (envVar.TryGetProperty("name", out var nameEl) && nameEl.ValueKind == JsonValueKind.String)
                                {
                                    var varName = nameEl.GetString()!;
                                    allRequiredVars[varName] = new Dictionary<string, object>
                                    {
                                        ["description"] = envVar.TryGetProperty("description", out var d) ? d.GetString() ?? "" : "",
                                        ["required"] = envVar.TryGetProperty("required", out var r) && r.ValueKind == JsonValueKind.True
                                    };
                                }
                            }
                        }
                    }
                }
            }
            catch { }
        }

        return allRequiredVars.Count > 0 ? PromptForVariables(allRequiredVars) : [];
    }

    private Dictionary<string, Dictionary<string, object>> CollectVariablesFromPackages(
        List<string> serverReferences,
        Dictionary<string, Dictionary<string, JsonElement>?> serverInfoCache,
        string sourceField)
    {
        var allVars = new Dictionary<string, Dictionary<string, object>>();

        foreach (var serverRef in serverReferences)
        {
            if (!serverInfoCache.TryGetValue(serverRef, out var serverInfo) || serverInfo == null)
                continue;

            try
            {
                if (!serverInfo.TryGetValue("packages", out var pkgsEl) || pkgsEl.ValueKind != JsonValueKind.Array)
                    continue;

                foreach (var pkg in pkgsEl.EnumerateArray())
                {
                    if (!pkg.TryGetProperty(sourceField, out var argsEl) || argsEl.ValueKind != JsonValueKind.Array)
                        continue;

                    foreach (var arg in argsEl.EnumerateArray())
                    {
                        if (!arg.TryGetProperty("variables", out var varsEl) || varsEl.ValueKind != JsonValueKind.Object)
                            continue;

                        foreach (var varProp in varsEl.EnumerateObject())
                        {
                            if (varProp.Value.ValueKind != JsonValueKind.Object) continue;
                            allVars[varProp.Name] = new Dictionary<string, object>
                            {
                                ["description"] = varProp.Value.TryGetProperty("description", out var d) ? d.GetString() ?? "" : "",
                                ["required"] = varProp.Value.TryGetProperty("is_required", out var r) && r.ValueKind == JsonValueKind.True
                            };
                        }
                    }
                }
            }
            catch { }
        }

        return allVars;
    }

    private static Dictionary<string, string> PromptForVariables(Dictionary<string, Dictionary<string, object>> requiredVars)
    {
        var envVars = new Dictionary<string, string>();

        var isE2e = (Environment.GetEnvironmentVariable("APM_E2E_TESTS") ?? "").ToLowerInvariant() is "1" or "true" or "yes";
        var isCi = new[] { "CI", "GITHUB_ACTIONS", "TRAVIS", "JENKINS_URL", "BUILDKITE" }
            .Any(v => !string.IsNullOrEmpty(Environment.GetEnvironmentVariable(v)));

        if (isE2e || isCi)
        {
            foreach (var varName in requiredVars.Keys.Order())
            {
                var existing = Environment.GetEnvironmentVariable(varName);
                if (!string.IsNullOrEmpty(existing))
                {
                    envVars[varName] = existing;
                }
                else if (varName == "GITHUB_DYNAMIC_TOOLSETS")
                {
                    envVars[varName] = "1";
                }
                else if (varName.Contains("token", StringComparison.OrdinalIgnoreCase) ||
                         varName.Contains("key", StringComparison.OrdinalIgnoreCase))
                {
                    envVars[varName] = Environment.GetEnvironmentVariable("GITHUB_APM_PAT")
                        ?? Environment.GetEnvironmentVariable("GITHUB_TOKEN")
                        ?? "";
                }
                else
                {
                    envVars[varName] = "";
                }
            }

            Console.WriteLine(isE2e ? "E2E test mode detected" : "CI environment detected");
            return envVars;
        }

        // Interactive prompt
        Console.WriteLine("Environment variables needed:");
        foreach (var varName in requiredVars.Keys.Order())
        {
            var varInfo = requiredVars[varName];
            var description = varInfo.TryGetValue("description", out var desc) ? desc.ToString() : "";

            var existing = Environment.GetEnvironmentVariable(varName);
            if (!string.IsNullOrEmpty(existing))
            {
                Console.WriteLine($"  ✅ {varName}: using existing value");
                envVars[varName] = existing;
            }
            else
            {
                var prompt = $"  {varName}";
                if (!string.IsNullOrEmpty(description))
                    prompt += $" ({description})";

                Console.Write($"{prompt}: ");
                envVars[varName] = Console.ReadLine() ?? "";
            }
        }
        Console.WriteLine();

        return envVars;
    }

    public void Dispose()
    {
        _registryClient.Dispose();
        GC.SuppressFinalize(this);
    }
}

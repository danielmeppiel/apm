using System.Text.Json;

namespace Apm.Cli.Runtime;

/// <summary>APM adapter for the GitHub Copilot CLI.</summary>
public sealed class CopilotRuntime : RuntimeBase
{
    public CopilotRuntime(string? modelName = null) : base(modelName ?? "default")
    {
        if (!IsAvailable())
            throw new InvalidOperationException("GitHub Copilot CLI not available. Install with: npm install -g @github/copilot");
    }

    public override string ExecutePrompt(string promptContent, Dictionary<string, object>? kwargs = null)
    {
        kwargs ??= [];

        var args = new List<string> { "-p", promptContent };

        if (kwargs.TryGetValue("full_auto", out var fullAuto) && fullAuto is true)
            args.Add("--allow-all-tools");

        if (kwargs.TryGetValue("log_level", out var logLevel) && logLevel is string level && level != "default")
            args.AddRange(["--log-level", level]);

        if (kwargs.TryGetValue("add_dirs", out var addDirsObj) && addDirsObj is IEnumerable<string> addDirs)
        {
            foreach (var dir in addDirs)
                args.AddRange(["--add-dir", dir]);
        }

        try
        {
            var (output, exitCode) = RunProcessStreaming("copilot", args, TimeSpan.FromMinutes(10));

            if (exitCode != 0)
            {
                var msg = output.Contains("not logged in", StringComparison.OrdinalIgnoreCase)
                    ? "Copilot CLI execution failed: Not logged in. Run 'copilot' and use '/login' command."
                    : $"Copilot CLI execution failed with exit code {exitCode}";
                throw new InvalidOperationException(msg);
            }

            return output;
        }
        catch (Exception ex) when (ex is not InvalidOperationException and not TimeoutException)
        {
            throw new InvalidOperationException($"Failed to execute prompt with Copilot CLI: {ex.Message}", ex);
        }
    }

    public override Dictionary<string, object> ListAvailableModels()
    {
        return new Dictionary<string, object>
        {
            ["copilot-default"] = new Dictionary<string, string>
            {
                ["id"] = "copilot-default",
                ["provider"] = "github-copilot",
                ["description"] = "Default GitHub Copilot model (managed by Copilot CLI)"
            }
        };
    }

    public override Dictionary<string, object> GetRuntimeInfo()
    {
        var version = GetToolVersion("copilot");
        var mcpConfigPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".copilot", "mcp-config.json");
        var mcpConfigured = File.Exists(mcpConfigPath);

        return new Dictionary<string, object>
        {
            ["name"] = "copilot",
            ["type"] = "copilot_cli",
            ["version"] = version,
            ["capabilities"] = new Dictionary<string, object>
            {
                ["model_execution"] = true,
                ["mcp_servers"] = mcpConfigured ? "native_support" : "manual_setup_required",
                ["configuration"] = "~/.copilot/mcp-config.json",
                ["interactive_mode"] = true,
                ["background_processes"] = true,
                ["file_operations"] = true,
                ["directory_access"] = "configurable"
            },
            ["description"] = "GitHub Copilot CLI runtime adapter",
            ["mcp_config_path"] = mcpConfigPath,
            ["mcp_configured"] = mcpConfigured
        };
    }

    /// <summary>Get configured MCP servers from the Copilot config.</summary>
    public Dictionary<string, object>? GetMcpServers()
    {
        var mcpConfigPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".copilot", "mcp-config.json");

        if (!File.Exists(mcpConfigPath))
            return null;

        try
        {
            var json = File.ReadAllText(mcpConfigPath);
            var doc = JsonDocument.Parse(json);
            if (doc.RootElement.TryGetProperty("servers", out var servers) &&
                servers.ValueKind == JsonValueKind.Object)
            {
                var result = new Dictionary<string, object>();
                foreach (var prop in servers.EnumerateObject())
                    result[prop.Name] = prop.Value.Clone();
                return result;
            }
        }
        catch
        {
            // Ignore parse errors
        }

        return null;
    }

    public static bool IsAvailable() => IsToolAvailable("copilot");
    public static string GetRuntimeName() => "copilot";
}

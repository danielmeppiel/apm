namespace Apm.Cli.Runtime;

/// <summary>APM adapter for the OpenAI Codex CLI.</summary>
public sealed class CodexRuntime : RuntimeBase
{
    public CodexRuntime(string? modelName = null) : base(modelName ?? "default")
    {
        if (!IsAvailable())
            throw new InvalidOperationException("Codex CLI not available. Install with: npm i -g @openai/codex@native");
    }

    public override string ExecutePrompt(string promptContent, Dictionary<string, object>? kwargs = null)
    {
        var args = new List<string> { "exec", "--skip-git-repo-check", promptContent };

        try
        {
            var (output, exitCode) = RunProcessStreaming("codex", args, TimeSpan.FromMinutes(5));

            if (exitCode != 0)
            {
                var msg = output.Contains("OPENAI_API_KEY", StringComparison.Ordinal)
                    ? "Codex execution failed: Missing or invalid OPENAI_API_KEY. Please set your OpenAI API key."
                    : $"Codex execution failed with exit code {exitCode}";
                throw new InvalidOperationException(msg);
            }

            return output;
        }
        catch (Exception ex) when (ex is not InvalidOperationException and not TimeoutException)
        {
            throw new InvalidOperationException($"Failed to execute prompt with Codex: {ex.Message}", ex);
        }
    }

    public override Dictionary<string, object> ListAvailableModels()
    {
        return new Dictionary<string, object>
        {
            ["codex-default"] = new Dictionary<string, string>
            {
                ["id"] = "codex-default",
                ["provider"] = "codex",
                ["description"] = "Default Codex model (managed by Codex CLI)"
            }
        };
    }

    public override Dictionary<string, object> GetRuntimeInfo()
    {
        var version = GetToolVersion("codex");

        return new Dictionary<string, object>
        {
            ["name"] = "codex",
            ["type"] = "codex_cli",
            ["version"] = version,
            ["capabilities"] = new Dictionary<string, object>
            {
                ["model_execution"] = true,
                ["mcp_servers"] = "native_support",
                ["configuration"] = "config.toml",
                ["sandboxing"] = "built_in"
            },
            ["description"] = "OpenAI Codex CLI runtime adapter"
        };
    }

    public static bool IsAvailable() => IsToolAvailable("codex");
    public static string GetRuntimeName() => "codex";
}

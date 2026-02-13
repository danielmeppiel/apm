using System.Diagnostics;

namespace Apm.Cli.Runtime;

/// <summary>APM adapter for the llm CLI (Simon Willison's LLM library).</summary>
public sealed class LlmRuntime : RuntimeBase
{
    public LlmRuntime(string? modelName = null) : base(modelName)
    {
        if (!IsAvailable())
            throw new InvalidOperationException("llm CLI not found. Please install: pip install llm");
    }

    public override string ExecutePrompt(string promptContent, Dictionary<string, object>? kwargs = null)
    {
        var args = new List<string>();

        if (!string.IsNullOrEmpty(ModelName))
            args.AddRange(["-m", ModelName]);

        args.Add(promptContent);

        try
        {
            var (output, exitCode) = RunProcessStreaming("llm", args, TimeSpan.FromMinutes(5));

            if (exitCode != 0)
                throw new InvalidOperationException($"LLM execution failed: {output}");

            return output;
        }
        catch (Exception ex) when (ex is not InvalidOperationException and not TimeoutException)
        {
            throw new InvalidOperationException($"Failed to execute prompt: {ex.Message}", ex);
        }
    }

    public override Dictionary<string, object> ListAvailableModels()
    {
        try
        {
            var psi = new ProcessStartInfo("llm", "models list")
            {
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            using var process = Process.Start(psi);
            if (process is null)
                return new Dictionary<string, object> { ["error"] = "Failed to start llm" };

            var output = process.StandardOutput.ReadToEnd();
            process.WaitForExit(30_000);

            var models = new Dictionary<string, object>();
            foreach (var line in output.Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
            {
                models[line] = new Dictionary<string, string>
                {
                    ["id"] = line,
                    ["provider"] = "llm"
                };
            }

            return models;
        }
        catch (Exception ex)
        {
            return new Dictionary<string, object> { ["error"] = $"Failed to list models: {ex.Message}" };
        }
    }

    public override Dictionary<string, object> GetRuntimeInfo()
    {
        return new Dictionary<string, object>
        {
            ["name"] = "llm",
            ["type"] = "llm_library",
            ["current_model"] = ModelName ?? "default",
            ["capabilities"] = new Dictionary<string, object>
            {
                ["model_execution"] = true,
                ["mcp_servers"] = "runtime_dependent",
                ["configuration"] = "llm_commands",
                ["sandboxing"] = "runtime_dependent"
            },
            ["description"] = "LLM CLI runtime adapter"
        };
    }

    public static bool IsAvailable() => IsToolAvailable("llm");
    public static string GetRuntimeName() => "llm";
}

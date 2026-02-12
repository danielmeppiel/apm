namespace Apm.Cli.Runtime;

/// <summary>
/// Factory for creating runtime adapters with auto-detection.
/// Preference order: Copilot → Codex → LLM.
/// </summary>
public static class RuntimeFactory
{
    /// <summary>Registry entry pairing a name with availability and creation functions.</summary>
    private record RuntimeEntry(string Name, Func<bool> IsAvailable, Func<string?, RuntimeBase> Create);

    private static readonly RuntimeEntry[] Runtimes =
    [
        new("copilot", CopilotRuntime.IsAvailable, m => new CopilotRuntime(m)),
        new("codex",   CodexRuntime.IsAvailable,   m => new CodexRuntime(m)),
        new("llm",     LlmRuntime.IsAvailable,     m => new LlmRuntime(m)),
    ];

    /// <summary>Get information about all available runtimes on the system.</summary>
    public static List<Dictionary<string, object>> GetAvailableRuntimes()
    {
        var available = new List<Dictionary<string, object>>();

        foreach (var entry in Runtimes)
        {
            if (!entry.IsAvailable()) continue;

            try
            {
                var instance = entry.Create(null);
                var info = instance.GetRuntimeInfo();
                info["available"] = true;
                available.Add(info);
            }
            catch (Exception ex)
            {
                available.Add(new Dictionary<string, object>
                {
                    ["name"] = entry.Name,
                    ["available"] = true,
                    ["error"] = $"Available but failed to initialize: {ex.Message}"
                });
            }
        }

        return available;
    }

    /// <summary>Get a runtime adapter by name.</summary>
    public static RuntimeBase GetRuntimeByName(string runtimeName, string? modelName = null)
    {
        var entry = Array.Find(Runtimes, r => r.Name == runtimeName)
            ?? throw new ArgumentException($"Unknown runtime: {runtimeName}");

        if (!entry.IsAvailable())
            throw new ArgumentException($"Runtime '{runtimeName}' is not available on this system");

        return entry.Create(modelName);
    }

    /// <summary>Get the best available runtime based on preference order.</summary>
    public static RuntimeBase GetBestAvailableRuntime(string? modelName = null)
    {
        foreach (var entry in Runtimes)
        {
            if (!entry.IsAvailable()) continue;

            try
            {
                return entry.Create(modelName);
            }
            catch
            {
                // Continue to next runtime if this one fails to initialize
            }
        }

        throw new InvalidOperationException(
            "No runtimes available. Install at least one of: " +
            "Copilot CLI (npm i -g @github/copilot), " +
            "Codex CLI (npm i -g @openai/codex@native), " +
            "or LLM library (pip install llm)");
    }

    /// <summary>
    /// Create a runtime adapter with optional runtime and model specification.
    /// If no runtime specified, uses the best available.
    /// </summary>
    public static RuntimeBase CreateRuntime(string? runtimeName = null, string? modelName = null)
    {
        return runtimeName is not null
            ? GetRuntimeByName(runtimeName, modelName)
            : GetBestAvailableRuntime(modelName);
    }

    /// <summary>Check if a runtime exists and is available.</summary>
    public static bool RuntimeExists(string runtimeName)
    {
        var entry = Array.Find(Runtimes, r => r.Name == runtimeName);
        return entry is not null && entry.IsAvailable();
    }
}

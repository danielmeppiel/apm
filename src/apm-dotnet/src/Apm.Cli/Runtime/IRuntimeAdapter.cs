namespace Apm.Cli.Runtime;

/// <summary>
/// Base adapter interface for LLM runtimes.
/// </summary>
public interface IRuntimeAdapter
{
    /// <summary>Execute a single prompt and return the response.</summary>
    string ExecutePrompt(string promptContent, Dictionary<string, object>? kwargs = null);

    /// <summary>List all available models in the runtime.</summary>
    Dictionary<string, object> ListAvailableModels();

    /// <summary>Get information about this runtime.</summary>
    Dictionary<string, object> GetRuntimeInfo();
}


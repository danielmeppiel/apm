namespace Apm.Cli.Adapters.Client;

/// <summary>
/// Base interface for MCP client adapters.
/// Each adapter handles client-specific configuration for MCP servers.
/// </summary>
public interface IClientAdapter
{
    /// <summary>Get the path to the MCP configuration file.</summary>
    string GetConfigPath();

    /// <summary>Update the MCP configuration.</summary>
    bool UpdateConfig(Dictionary<string, object?> configUpdates);

    /// <summary>Get the current MCP configuration.</summary>
    Dictionary<string, object?> GetCurrentConfig();

    /// <summary>
    /// Configure an MCP server in the client configuration.
    /// </summary>
    /// <param name="serverUrl">URL or identifier of the MCP server.</param>
    /// <param name="serverName">Optional name for the server.</param>
    /// <param name="enabled">Whether to enable the server.</param>
    /// <param name="envOverrides">Environment variable overrides.</param>
    /// <param name="serverInfoCache">Pre-fetched server info to avoid duplicate registry calls.</param>
    /// <param name="runtimeVars">Runtime variable values.</param>
    /// <returns>True if successful, false otherwise.</returns>
    bool ConfigureMcpServer(
        string serverUrl,
        string? serverName = null,
        bool enabled = true,
        Dictionary<string, string>? envOverrides = null,
        Dictionary<string, Dictionary<string, object?>>? serverInfoCache = null,
        Dictionary<string, string>? runtimeVars = null);
}

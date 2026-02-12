using Apm.Cli.Adapters.Client;

namespace Apm.Cli.Core;

/// <summary>Factory for creating MCP client adapters.</summary>
public static class ClientFactory
{
    private static readonly Dictionary<string, Func<IClientAdapter>> Clients = new(StringComparer.OrdinalIgnoreCase)
    {
        ["copilot"] = () => new CopilotClientAdapter(),
        ["vscode"] = () => new VSCodeClientAdapter(),
        ["codex"] = () => new CodexClientAdapter(),
    };

    /// <summary>
    /// Create a client adapter based on the specified type.
    /// </summary>
    /// <exception cref="ArgumentException">If the client type is not supported.</exception>
    public static IClientAdapter CreateClient(string clientType)
    {
        if (Clients.TryGetValue(clientType, out var factory))
            return factory();
        throw new ArgumentException($"Unsupported client type: {clientType}");
    }
}

using Apm.Cli.Adapters.Client;
using Apm.Cli.Core;

namespace Apm.Cli.Adapters.PackageManager;

/// <summary>
/// Default MCP package manager implementation.
/// Delegates installation to the configured client adapter.
/// </summary>
public class DefaultMcpPackageManager : IPackageManagerAdapter
{
    public bool Install(string packageName, string? version = null)
    {
        try
        {
            var adapter = CreateClientAdapter();
            var result = adapter.ConfigureMcpServer(packageName, packageName, true);
            if (result)
                Console.WriteLine($"Successfully installed {packageName}");
            return result;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error installing package {packageName}: {ex.Message}");
            return false;
        }
    }

    public bool Uninstall(string packageName)
    {
        try
        {
            var adapter = CreateClientAdapter();
            var config = adapter.GetCurrentConfig();

            if (config.TryGetValue("servers", out var serversObj) &&
                serversObj is Dictionary<string, object?> servers &&
                servers.ContainsKey(packageName))
            {
                servers.Remove(packageName);
                var result = adapter.UpdateConfig(config);
                if (result)
                    Console.WriteLine($"Successfully uninstalled {packageName}");
                return result;
            }

            Console.WriteLine($"Package {packageName} not found in configuration");
            return false;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error uninstalling package {packageName}: {ex.Message}");
            return false;
        }
    }

    public List<string> ListInstalled()
    {
        try
        {
            var adapter = CreateClientAdapter();
            var config = adapter.GetCurrentConfig();

            if (config.TryGetValue("servers", out var serversObj) &&
                serversObj is Dictionary<string, object?> servers)
            {
                return servers.Keys.ToList();
            }

            return [];
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error retrieving installed MCP servers: {ex.Message}");
            return [];
        }
    }

    public List<string> Search(string query)
    {
        // Placeholder: registry search integration would go here
        Console.WriteLine("Warning: Package search not yet implemented in .NET port");
        return [];
    }

    private static IClientAdapter CreateClientAdapter()
    {
        var clientType = Configuration.GetDefaultClient();
        return clientType.ToLowerInvariant() switch
        {
            "vscode" => new VSCodeClientAdapter(),
            "codex" => new CodexClientAdapter(),
            "copilot" => new CopilotClientAdapter(),
            _ => new VSCodeClientAdapter(),
        };
    }
}

namespace Apm.Cli.Adapters.PackageManager;

/// <summary>
/// Base interface for MCP package managers.
/// </summary>
public interface IPackageManagerAdapter
{
    /// <summary>Install an MCP package.</summary>
    bool Install(string packageName, string? version = null);

    /// <summary>Uninstall an MCP package.</summary>
    bool Uninstall(string packageName);

    /// <summary>List all installed MCP packages.</summary>
    List<string> ListInstalled();

    /// <summary>Search for MCP packages.</summary>
    List<string> Search(string query);
}

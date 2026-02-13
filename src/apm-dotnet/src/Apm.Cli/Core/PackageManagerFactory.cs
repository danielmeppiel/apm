using Apm.Cli.Adapters.PackageManager;

namespace Apm.Cli.Core;

/// <summary>Factory for creating MCP package manager adapters.</summary>
public static class PackageManagerFactory
{
    private static readonly Dictionary<string, Func<IPackageManagerAdapter>> Managers = new(StringComparer.OrdinalIgnoreCase)
    {
        ["default"] = () => new DefaultMcpPackageManager(),
    };

    /// <summary>
    /// Create a package manager adapter based on the specified type.
    /// </summary>
    /// <exception cref="ArgumentException">If the manager type is not supported.</exception>
    public static IPackageManagerAdapter CreatePackageManager(string managerType = "default")
    {
        if (Managers.TryGetValue(managerType, out var factory))
            return factory();
        throw new ArgumentException($"Unsupported package manager type: {managerType}");
    }
}

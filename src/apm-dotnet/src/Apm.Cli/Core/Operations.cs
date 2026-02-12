namespace Apm.Cli.Core;

/// <summary>
/// Core operations for APM-CLI: install, uninstall, and configure MCP packages.
/// </summary>
public static class Operations
{
    /// <summary>
    /// Install an MCP package for a specific client type using safe installation with conflict detection.
    /// </summary>
    /// <param name="clientType">Type of client to configure (e.g. copilot, codex, vscode).</param>
    /// <param name="packageName">Name of the package to install.</param>
    /// <param name="version">Optional version constraint.</param>
    /// <param name="sharedEnvVars">Pre-collected environment variables to use.</param>
    /// <param name="serverInfoCache">Pre-fetched server info to avoid duplicate registry calls.</param>
    /// <param name="sharedRuntimeVars">Pre-collected runtime variables to use.</param>
    /// <returns>Result dictionary with success/installed/skipped/failed flags.</returns>
    public static InstallResult InstallPackage(
        string clientType,
        string packageName,
        string? version = null,
        Dictionary<string, string>? sharedEnvVars = null,
        Dictionary<string, object>? serverInfoCache = null,
        Dictionary<string, string>? sharedRuntimeVars = null)
    {
        return InstallPackage(
            new SafeInstaller(clientType),
            packageName,
            sharedEnvVars,
            serverInfoCache,
            sharedRuntimeVars);
    }

    /// <summary>Internal overload for testing with a pre-built SafeInstaller.</summary>
    internal static InstallResult InstallPackage(
        SafeInstaller safeInstaller,
        string packageName,
        Dictionary<string, string>? sharedEnvVars = null,
        Dictionary<string, object>? serverInfoCache = null,
        Dictionary<string, string>? sharedRuntimeVars = null)
    {
        try
        {
            var summary = safeInstaller.InstallServers(
                [packageName],
                envOverrides: sharedEnvVars,
                serverInfoCache: serverInfoCache,
                runtimeVars: sharedRuntimeVars);

            return new InstallResult
            {
                Success = true,
                Installed = summary.Installed.Count > 0,
                Skipped = summary.Skipped.Count > 0,
                Failed = summary.Failed.Count > 0,
            };
        }
        catch (Exception e)
        {
            Console.Error.WriteLine($"Error installing package {packageName}: {e.Message}");
            return new InstallResult
            {
                Success = false,
                Installed = false,
                Skipped = false,
                Failed = true,
            };
        }
    }

    /// <summary>
    /// Uninstall an MCP package.
    /// </summary>
    public static bool UninstallPackage(string clientType, string packageName)
    {
        try
        {
            // TODO: Wire up ClientFactory and PackageManagerFactory when ported
            // var client = ClientFactory.CreateClient(clientType);
            // var packageManager = PackageManagerFactory.CreatePackageManager();
            // var result = packageManager.Uninstall(packageName);
            // Remove legacy config entries if they exist
            // return result;
            throw new NotImplementedException(
                "UninstallPackage requires ClientFactory and PackageManagerFactory (not yet ported).");
        }
        catch (Exception e)
        {
            Console.Error.WriteLine($"Error uninstalling package: {e.Message}");
            return false;
        }
    }

    /// <summary>
    /// Configure an MCP client.
    /// </summary>
    public static bool ConfigureClient(string clientType, Dictionary<string, object> configUpdates)
    {
        try
        {
            // TODO: Wire up ClientFactory when ported
            // var client = ClientFactory.CreateClient(clientType);
            // client.UpdateConfig(configUpdates);
            // return true;
            throw new NotImplementedException(
                "ConfigureClient requires ClientFactory (not yet ported).");
        }
        catch (Exception e)
        {
            Console.Error.WriteLine($"Error configuring client: {e.Message}");
            return false;
        }
    }
}

/// <summary>
/// Result of a package install operation.
/// </summary>
public sealed class InstallResult
{
    public bool Success { get; init; }
    public bool Installed { get; init; }
    public bool Skipped { get; init; }
    public bool Failed { get; init; }
}

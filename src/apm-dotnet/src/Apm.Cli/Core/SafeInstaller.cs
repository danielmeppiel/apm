using Apm.Cli.Adapters.Client;
using Apm.Cli.Registry;
using Apm.Cli.Utils;

namespace Apm.Cli.Core;

/// <summary>
/// Summary of MCP server installation results.
/// </summary>
public sealed class InstallationSummary
{
    public List<string> Installed { get; } = [];
    public List<SkippedItem> Skipped { get; } = [];
    public List<FailedItem> Failed { get; } = [];

    public void AddInstalled(string serverRef) => Installed.Add(serverRef);

    public void AddSkipped(string serverRef, string reason)
        => Skipped.Add(new SkippedItem(serverRef, reason));

    public void AddFailed(string serverRef, string reason)
        => Failed.Add(new FailedItem(serverRef, reason));

    public bool HasAnyChanges => Installed.Count > 0 || Failed.Count > 0;

    /// <summary>Log a summary of installation results.</summary>
    public void LogSummary()
    {
        if (Installed.Count > 0)
            ConsoleHelpers.Success($"✅ Installed: {string.Join(", ", Installed)}");

        foreach (var item in Skipped)
            ConsoleHelpers.Warning($"⚠️  Skipped {item.Server}: {item.Reason}");

        foreach (var item in Failed)
            ConsoleHelpers.Error($"❌ Failed {item.Server}: {item.Reason}");
    }

    public sealed record SkippedItem(string Server, string Reason);
    public sealed record FailedItem(string Server, string Reason);
}

/// <summary>
/// Safe MCP server installation with conflict detection.
/// </summary>
public sealed class SafeInstaller
{
    private readonly string _runtime;
    private readonly IClientAdapter _adapter;
    private readonly ConflictDetector _conflictDetector;

    /// <param name="runtime">Target runtime (copilot, codex, vscode).</param>
    public SafeInstaller(string runtime)
    {
        _runtime = runtime;
        _adapter = ClientFactory.CreateClient(runtime);
        _conflictDetector = new ConflictDetector(_adapter, new RegistryClient());
    }

    /// <summary>Internal constructor for testing with a pre-built adapter.</summary>
    internal SafeInstaller(IClientAdapter adapter, RegistryClient? registryClient = null)
    {
        _runtime = adapter.GetType().Name;
        _adapter = adapter;
        _conflictDetector = new ConflictDetector(adapter, registryClient);
    }

    /// <summary>
    /// Install MCP servers with conflict detection.
    /// </summary>
    public InstallationSummary InstallServers(
        IReadOnlyList<string> serverReferences,
        Dictionary<string, string>? envOverrides = null,
        Dictionary<string, object>? serverInfoCache = null,
        Dictionary<string, string>? runtimeVars = null)
    {
        var summary = new InstallationSummary();

        foreach (var serverRef in serverReferences)
        {
            if (_conflictDetector.CheckServerExists(serverRef))
            {
                summary.AddSkipped(serverRef, "already configured");
                ConsoleHelpers.Warning($"  {serverRef} already configured, skipping");
                continue;
            }

            try
            {
                var result = _adapter.ConfigureMcpServer(
                    serverRef,
                    envOverrides: envOverrides,
                    serverInfoCache: ConvertServerInfoCache(serverInfoCache),
                    runtimeVars: runtimeVars);

                if (result)
                {
                    summary.AddInstalled(serverRef);
                    ConsoleHelpers.Success($"  ✓ {serverRef}");
                }
                else
                {
                    summary.AddFailed(serverRef, "configuration failed");
                    ConsoleHelpers.Warning($"  ✗ {serverRef} installation failed");
                }
            }
            catch (Exception e)
            {
                summary.AddFailed(serverRef, e.Message);
                ConsoleHelpers.Error($"  ✗ {serverRef}: {e.Message}");
            }
        }

        return summary;
    }

    /// <summary>
    /// Check for conflicts without installing.
    /// </summary>
    public Dictionary<string, ConflictSummary> CheckConflictsOnly(IReadOnlyList<string> serverReferences)
    {
        var conflicts = new Dictionary<string, ConflictSummary>();
        foreach (var serverRef in serverReferences)
            conflicts[serverRef] = _conflictDetector.GetConflictSummary(serverRef);
        return conflicts;
    }

    private static Dictionary<string, Dictionary<string, object?>>? ConvertServerInfoCache(
        Dictionary<string, object>? cache)
    {
        if (cache is null) return null;
        var result = new Dictionary<string, Dictionary<string, object?>>();
        foreach (var (key, value) in cache)
        {
            if (value is Dictionary<string, object?> dict)
                result[key] = dict;
        }
        return result.Count > 0 ? result : null;
    }
}

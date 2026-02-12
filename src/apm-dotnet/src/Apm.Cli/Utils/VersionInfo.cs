using System.Reflection;

namespace Apm.Cli.Utils;

/// <summary>
/// Version management for APM CLI.
/// </summary>
public static class VersionInfo
{
    /// <summary>
    /// Get the current version string.
    /// Reads from assembly informational version, then assembly version, then falls back to "unknown".
    /// </summary>
    public static string GetVersion()
    {
        // Try informational version (set from <Version> in .csproj, includes prerelease tags)
        var infoAttr = Assembly.GetExecutingAssembly()
            .GetCustomAttribute<AssemblyInformationalVersionAttribute>();
        if (infoAttr?.InformationalVersion is { Length: > 0 } infoVersion)
        {
            // Strip source-link commit hash suffix (e.g. "0.7.2+abc123" → "0.7.2")
            var plusIdx = infoVersion.IndexOf('+');
            return plusIdx >= 0 ? infoVersion[..plusIdx] : infoVersion;
        }

        // Fallback to assembly version
        var asmVersion = Assembly.GetExecutingAssembly().GetName().Version;
        if (asmVersion is not null)
            return $"{asmVersion.Major}.{asmVersion.Minor}.{asmVersion.Build}";

        return "unknown";
    }
}

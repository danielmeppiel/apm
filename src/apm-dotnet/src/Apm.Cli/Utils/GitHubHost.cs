using System.Text.RegularExpressions;
using System.Web;

namespace Apm.Cli.Utils;

/// <summary>
/// Utilities for handling GitHub, GitHub Enterprise, and Azure DevOps hostnames and URLs.
/// </summary>
public static class GitHubHost
{
    /// <summary>
    /// Return the default Git host (can be overridden via GITHUB_HOST env var).
    /// </summary>
    public static string DefaultHost()
        => Environment.GetEnvironmentVariable("GITHUB_HOST") ?? "github.com";

    /// <summary>
    /// Return true if hostname is Azure DevOps (cloud or legacy).
    /// </summary>
    public static bool IsAzureDevOpsHostname(string? hostname)
    {
        if (string.IsNullOrEmpty(hostname))
            return false;
        var h = hostname.ToLowerInvariant();
        return h == "dev.azure.com" || h.EndsWith(".visualstudio.com");
    }

    /// <summary>
    /// Return true if hostname should be treated as GitHub (cloud or enterprise).
    /// </summary>
    public static bool IsGitHubHostname(string? hostname)
    {
        if (string.IsNullOrEmpty(hostname))
            return false;
        var h = hostname.ToLowerInvariant();
        return h == "github.com" || h.EndsWith(".ghe.com");
    }

    /// <summary>
    /// Return true if hostname is a supported Git hosting platform.
    /// </summary>
    public static bool IsSupportedGitHost(string? hostname)
    {
        if (string.IsNullOrEmpty(hostname))
            return false;

        if (IsGitHubHostname(hostname))
            return true;
        if (IsAzureDevOpsHostname(hostname))
            return true;

        var configuredHost = (Environment.GetEnvironmentVariable("GITHUB_HOST") ?? "").ToLowerInvariant();
        if (!string.IsNullOrEmpty(configuredHost) && hostname.ToLowerInvariant() == configuredHost)
            return true;

        return false;
    }

    /// <summary>
    /// Generate an actionable error message for unsupported Git hosts.
    /// </summary>
    public static string UnsupportedHostError(string hostname, string? context = null)
    {
        var currentHost = Environment.GetEnvironmentVariable("GITHUB_HOST") ?? "";

        var msg = "";
        if (context is not null)
            msg += $"{context}\n\n";

        msg += $"Unsupported Git host: '{hostname}'.\n";
        msg += "\n";
        msg += "APM only allows these Git hosts by default:\n";
        msg += "  • github.com\n";
        msg += "  • *.ghe.com (GitHub Enterprise Cloud)\n";
        msg += "  • dev.azure.com, *.visualstudio.com (Azure DevOps)\n";
        msg += "\n";

        if (!string.IsNullOrEmpty(currentHost))
        {
            msg += $"Your GITHUB_HOST is set to: '{currentHost}'\n";
            msg += $"But you're trying to use: '{hostname}'\n";
            msg += "\n";
        }

        msg += $"To use '{hostname}', set the GITHUB_HOST environment variable:\n";
        msg += "\n";
        msg += "  # Linux/macOS:\n";
        msg += $"  export GITHUB_HOST={hostname}\n";
        msg += "\n";
        msg += "  # Windows (PowerShell):\n";
        msg += $"  $env:GITHUB_HOST = \"{hostname}\"\n";
        msg += "\n";
        msg += "  # Windows (Command Prompt):\n";
        msg += $"  set GITHUB_HOST={hostname}\n";

        return msg;
    }

    /// <summary>
    /// Build an SSH clone URL for the given host and repo ref (owner/repo).
    /// </summary>
    public static string BuildSshUrl(string host, string repoRef)
        => $"git@{host}:{repoRef}.git";

    /// <summary>
    /// Build an HTTPS clone URL. If token provided, use x-access-token format.
    /// </summary>
    public static string BuildHttpsCloneUrl(string host, string repoRef, string? token = null)
    {
        if (token is not null)
            return $"https://x-access-token:{token}@{host}/{repoRef}.git";
        return $"https://{host}/{repoRef}";
    }

    /// <summary>
    /// Build Azure DevOps HTTPS clone URL.
    /// </summary>
    public static string BuildAdoHttpsCloneUrl(string org, string project, string repo,
        string? token = null, string host = "dev.azure.com")
    {
        if (token is not null)
            return $"https://{token}@{host}/{org}/{project}/_git/{repo}";
        return $"https://{host}/{org}/{project}/_git/{repo}";
    }

    /// <summary>
    /// Build Azure DevOps SSH clone URL for cloud or server.
    /// </summary>
    public static string BuildAdoSshUrl(string org, string project, string repo,
        string host = "ssh.dev.azure.com")
    {
        if (host == "ssh.dev.azure.com")
            return $"git@ssh.dev.azure.com:v3/{org}/{project}/{repo}";
        return $"ssh://git@{host}/{org}/{project}/_git/{repo}";
    }

    /// <summary>
    /// Build Azure DevOps REST API URL for file contents.
    /// </summary>
    public static string BuildAdoApiUrl(string org, string project, string repo,
        string path, string gitRef = "main", string host = "dev.azure.com")
    {
        var encodedPath = Uri.EscapeDataString(path);
        return $"https://{host}/{org}/{project}/_apis/git/repositories/{repo}/items"
             + $"?path={encodedPath}&versionDescriptor.version={gitRef}&api-version=7.0";
    }

    /// <summary>
    /// Validate if a string is a valid Fully Qualified Domain Name (FQDN).
    /// </summary>
    public static bool IsValidFqdn(string? hostname)
    {
        if (string.IsNullOrEmpty(hostname))
            return false;

        // Remove any path components
        var h = hostname.Split('/')[0];

        const string pattern = @"^[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)+$";
        return Regex.IsMatch(h, pattern);
    }

    /// <summary>
    /// Sanitize occurrences of token-bearing HTTPS URLs in a message.
    /// </summary>
    public static string SanitizeTokenUrlInMessage(string message, string? host = null)
    {
        host ??= DefaultHost();
        var hostRe = Regex.Escape(host);
        var pattern = $@"https://[^@\s]+@{hostRe}";
        return Regex.Replace(message, pattern, $"https://***@{host}");
    }
}

namespace Apm.Cli.Integration;

/// <summary>Shared utility functions for integration modules.</summary>
public static class IntegrationUtils
{
    /// <summary>
    /// Normalize a repo URL to owner/repo format.
    /// Handles full URLs (https://github.com/owner/repo), .git suffix, and short form.
    /// </summary>
    public static string NormalizeRepoUrl(string packageRepoUrl)
    {
        if (!packageRepoUrl.Contains("://"))
        {
            // Already in short form, just remove .git suffix and trailing slashes
            var normalized = packageRepoUrl;
            if (normalized.EndsWith(".git"))
                normalized = normalized[..^4];
            return normalized.TrimEnd('/');
        }

        // Extract owner/repo from full URL: https://github.com/owner/repo -> owner/repo
        var parts = packageRepoUrl.Split("://", 2)[1]; // Remove protocol
        var slashIndex = parts.IndexOf('/');
        if (slashIndex >= 0)
        {
            var pathPart = parts[(slashIndex + 1)..];
            // Remove trailing slashes first
            pathPart = pathPart.TrimEnd('/');
            // Then remove .git suffix if present
            if (pathPart.EndsWith(".git"))
                pathPart = pathPart[..^4];
            return pathPart;
        }

        return packageRepoUrl;
    }
}

using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;
using Spectre.Console;

namespace Apm.Cli.Utils;

/// <summary>
/// Version checking and update notification utilities.
/// Checks GitHub releases for newer versions and displays update notifications.
/// </summary>
public static class VersionChecker
{
    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(2) };

    private static readonly Regex VersionPattern =
        new(@"^(\d+)\.(\d+)\.(\d+)(a\d+|b\d+|rc\d+)?$", RegexOptions.Compiled);

    /// <summary>
    /// Fetch the latest release version from GitHub API.
    /// </summary>
    public static async Task<string?> GetLatestVersionFromGitHubAsync(
        string repo = "danielmeppiel/apm", int timeoutSeconds = 2)
    {
        try
        {
            Http.Timeout = TimeSpan.FromSeconds(timeoutSeconds);
            var url = $"https://api.github.com/repos/{repo}/releases/latest";

            using var request = new HttpRequestMessage(HttpMethod.Get, url);
            request.Headers.Add("User-Agent", "apm-cli");

            using var response = await Http.SendAsync(request);
            if (!response.IsSuccessStatusCode)
                return null;

            var data = await response.Content.ReadFromJsonAsync(ApmJsonContext.Default.GitHubRelease);
            var tagName = data?.TagName ?? "";

            if (tagName.StartsWith('v'))
                tagName = tagName[1..];

            return VersionPattern.IsMatch(tagName) ? tagName : null;
        }
        catch
        {
            return null;
        }
    }

    /// <summary>
    /// Parse a semantic version string into components.
    /// </summary>
    public static (int Major, int Minor, int Patch, string Prerelease)? ParseVersion(string versionStr)
    {
        var match = VersionPattern.Match(versionStr);
        if (!match.Success)
            return null;

        return (
            int.Parse(match.Groups[1].Value),
            int.Parse(match.Groups[2].Value),
            int.Parse(match.Groups[3].Value),
            match.Groups[4].Value
        );
    }

    /// <summary>
    /// Compare two semantic versions. Returns true if latest is newer than current.
    /// </summary>
    public static bool IsNewerVersion(string current, string latest)
    {
        var currentParts = ParseVersion(current);
        var latestParts = ParseVersion(latest);

        if (currentParts is null || latestParts is null)
            return false;

        var (currMaj, currMin, currPatch, currPre) = currentParts.Value;
        var (latMaj, latMin, latPatch, latPre) = latestParts.Value;

        var currTuple = (currMaj, currMin, currPatch);
        var latTuple = (latMaj, latMin, latPatch);

        if (latTuple.CompareTo(currTuple) > 0)
            return true;
        if (latTuple.CompareTo(currTuple) < 0)
            return false;

        // Same major.minor.patch — stable releases are newer than prereleases
        if (string.IsNullOrEmpty(latPre) && !string.IsNullOrEmpty(currPre))
            return true;
        if (!string.IsNullOrEmpty(latPre) && string.IsNullOrEmpty(currPre))
            return false;

        // Both have prereleases — compare lexicographically
        return string.Compare(latPre, currPre, StringComparison.Ordinal) > 0;
    }

    /// <summary>
    /// Get path to version update cache file.
    /// </summary>
    public static string GetUpdateCachePath()
    {
        string cacheDir;
        if (OperatingSystem.IsWindows())
            cacheDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "apm-cli", "cache");
        else
            cacheDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
                ".cache", "apm-cli");

        Directory.CreateDirectory(cacheDir);
        return Path.Combine(cacheDir, "last_version_check");
    }

    /// <summary>
    /// Determine if we should check for updates based on cache. Checks at most once per day.
    /// </summary>
    public static bool ShouldCheckForUpdates()
    {
        try
        {
            var cachePath = GetUpdateCachePath();
            if (!File.Exists(cachePath))
                return true;

            var fileAge = DateTime.UtcNow - File.GetLastWriteTimeUtc(cachePath);
            return fileAge.TotalSeconds > 86400;
        }
        catch
        {
            return true;
        }
    }

    /// <summary>
    /// Save timestamp of last version check to cache.
    /// </summary>
    public static void SaveVersionCheckTimestamp()
    {
        try
        {
            var cachePath = GetUpdateCachePath();
            File.WriteAllText(cachePath, "");
        }
        catch
        {
            // Silently fail
        }
    }

    /// <summary>
    /// Check if a newer version is available. Non-blocking and cache-aware.
    /// </summary>
    public static async Task<string?> CheckForUpdatesAsync(string currentVersion)
    {
        if (!ShouldCheckForUpdates())
            return null;

        var latestVersion = await GetLatestVersionFromGitHubAsync();

        SaveVersionCheckTimestamp();

        if (latestVersion is null)
            return null;

        return IsNewerVersion(currentVersion, latestVersion) ? latestVersion : null;
    }

    /// <summary>
    /// Display update notification using Spectre.Console markup.
    /// </summary>
    public static void DisplayUpdateNotification(string currentVersion, string latestVersion)
    {
        AnsiConsole.WriteLine();
        AnsiConsole.Write(new Panel(
                $"[yellow]Update available:[/] [dim]{Markup.Escape(currentVersion)}[/] → [green bold]{Markup.Escape(latestVersion)}[/]\n" +
                "[dim]Run[/] [cyan]dotnet tool update -g apm-cli[/] [dim]to update[/]")
            .Border(BoxBorder.Rounded)
            .BorderStyle(Style.Parse("yellow")));
    }

    internal sealed class GitHubRelease
    {
        [JsonPropertyName("tag_name")]
        public string? TagName { get; set; }
    }
}

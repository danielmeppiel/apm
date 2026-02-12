using System.Text.RegularExpressions;
using Apm.Cli.Primitives;

namespace Apm.Cli.Compilation;

/// <summary>
/// Context link resolution for APM primitives.
/// Resolves markdown links to context files across installation, compilation, and runtime.
/// </summary>
public partial class UnifiedLinkResolver : ILinkResolver
{
    private static readonly HashSet<string> ContextExtensions = [".context.md", ".memory.md"];

    private readonly string _baseDir;
    private readonly Dictionary<string, string> _contextRegistry = new();

    public UnifiedLinkResolver(string baseDir)
    {
        _baseDir = Path.GetFullPath(baseDir);
    }

    /// <summary>Build registry of all available context files.</summary>
    public void RegisterContexts(PrimitiveCollection primitives)
    {
        foreach (var context in primitives.Contexts)
        {
            var filename = Path.GetFileName(context.FilePath);
            _contextRegistry[filename] = context.FilePath;

            if (context.Source is not null && context.Source.StartsWith("dependency:"))
            {
                var package = context.Source.Replace("dependency:", "");
                var qualifiedName = $"{package}:{filename}";
                _contextRegistry[qualifiedName] = context.FilePath;
            }
        }
    }

    /// <summary>Resolve markdown links when generating AGENTS.md.</summary>
    public string ResolveMarkdownLinks(string content, string baseDir)
    {
        return LinkPattern().Replace(content, match =>
        {
            var linkText = match.Groups[1].Value;
            var linkPath = match.Groups[2].Value;

            // Skip external URLs
            if (IsExternalUrl(linkPath))
                return match.Value;

            // Skip anchors
            if (linkPath.StartsWith('#'))
                return match.Value;

            var fullPath = ResolvePath(linkPath, baseDir);
            if (fullPath is null || !File.Exists(fullPath))
                return match.Value;

            // For .md/.txt files, inline the content
            var ext = Path.GetExtension(fullPath).ToLowerInvariant();
            if (ext is ".md" or ".txt")
            {
                try
                {
                    var fileContent = File.ReadAllText(fullPath);
                    fileContent = RemoveFrontmatter(fileContent);
                    return $"**{linkText}**:\n\n{fileContent}";
                }
                catch
                {
                    return match.Value;
                }
            }

            return match.Value;
        });
    }

    /// <summary>Validate that all referenced files exist.</summary>
    public List<string> ValidateLinkTargets(string content, string baseDir)
    {
        var errors = new List<string>();

        foreach (Match match in LinkPattern().Matches(content))
        {
            var text = match.Groups[1].Value;
            var path = match.Groups[2].Value;

            if (IsExternalUrl(path) || path.StartsWith('#'))
                continue;

            var fullPath = ResolvePath(path, baseDir);
            if (fullPath is null || (!File.Exists(fullPath) && !Directory.Exists(fullPath)))
                errors.Add($"Referenced file not found: {path} (in link '{text}')");
        }

        return errors;
    }

    /// <summary>Resolve links for compilation, rewriting context references to point to source files.</summary>
    public string ResolveLinksForCompilation(string content, string sourceFile, string? compiledOutput = null)
    {
        var targetLocation = compiledOutput ?? sourceFile;
        if (File.Exists(targetLocation) || targetLocation.EndsWith(".md"))
            targetLocation = Path.GetDirectoryName(targetLocation) ?? targetLocation;

        var sourceLocation = Directory.Exists(sourceFile)
            ? sourceFile
            : Path.GetDirectoryName(sourceFile) ?? sourceFile;

        return LinkPattern().Replace(content, match =>
        {
            var linkText = match.Groups[1].Value;
            var linkPath = match.Groups[2].Value;

            if (IsExternalUrl(linkPath) || !IsContextFile(linkPath))
                return match.Value;

            var resolved = ResolveContextLink(linkPath, sourceLocation, targetLocation);
            return resolved is not null ? $"[{linkText}]({resolved})" : match.Value;
        });
    }

    /// <summary>Resolve links when copying files during installation (e.g., from apm_modules/ to .github/).</summary>
    public string ResolveLinksForInstallation(string content, string sourceFile, string targetFile)
    {
        var targetLocation = Path.GetDirectoryName(targetFile) ?? targetFile;
        var sourceLocation = Path.GetDirectoryName(sourceFile) ?? sourceFile;

        return LinkPattern().Replace(content, match =>
        {
            var linkText = match.Groups[1].Value;
            var linkPath = match.Groups[2].Value;

            if (IsExternalUrl(linkPath) || !IsContextFile(linkPath))
                return match.Value;

            var resolved = ResolveContextLink(linkPath, sourceLocation, targetLocation);
            return resolved is not null ? $"[{linkText}]({resolved})" : match.Value;
        });
    }

    /// <summary>Scan files for context references (for reporting/validation).</summary>
    public HashSet<string> GetReferencedContexts(List<string> filesToScan)
    {
        var references = new HashSet<string>();

        foreach (var filePath in filesToScan)
        {
            if (!File.Exists(filePath))
                continue;

            try
            {
                var content = File.ReadAllText(filePath);
                foreach (Match match in LinkPattern().Matches(content))
                {
                    var path = match.Groups[2].Value;
                    if (IsExternalUrl(path) || !IsContextFile(path))
                        continue;

                    var resolved = ResolveToActualFile(path, filePath);
                    if (resolved is not null && File.Exists(resolved))
                        references.Add(resolved);
                }
            }
            catch
            {
                // skip unreadable files
            }
        }

        return references;
    }

    private string? ResolveContextLink(string linkPath, string sourceLocation, string targetLocation)
    {
        var actualFile = ResolveToActualFile(linkPath, sourceLocation);
        if (actualFile is null || !File.Exists(actualFile))
            return null;

        try
        {
            return Path.GetRelativePath(targetLocation, actualFile);
        }
        catch
        {
            return null;
        }
    }

    private string? ResolveToActualFile(string linkPath, string sourceFile)
    {
        var filename = Path.GetFileName(linkPath);

        // Try context registry first
        if (_contextRegistry.TryGetValue(filename, out var registryPath))
            return registryPath;

        // Try relative to source file
        var sourceDir = Directory.Exists(sourceFile) ? sourceFile : Path.GetDirectoryName(sourceFile) ?? sourceFile;
        var potential = Path.GetFullPath(Path.Combine(sourceDir, linkPath));
        if (File.Exists(potential))
            return potential;

        // Try relative to base dir
        potential = Path.GetFullPath(Path.Combine(_baseDir, linkPath));
        if (File.Exists(potential))
            return potential;

        return null;
    }

    internal static bool IsExternalUrl(string path)
    {
        try
        {
            path = path.Trim();
            if (!Uri.TryCreate(path, UriKind.Absolute, out var uri))
                return false;
            return uri.Scheme is "http" or "https" && !string.IsNullOrEmpty(uri.Host);
        }
        catch
        {
            return false;
        }
    }

    private static bool IsContextFile(string path)
    {
        var lower = path.ToLowerInvariant();
        return ContextExtensions.Any(ext => lower.EndsWith(ext));
    }

    private static string? ResolvePath(string path, string baseDir)
    {
        try
        {
            return Path.IsPathRooted(path) ? path : Path.GetFullPath(Path.Combine(baseDir, path));
        }
        catch
        {
            return null;
        }
    }

    private static string RemoveFrontmatter(string content)
    {
        if (!content.StartsWith("---\n"))
            return content.Trim();

        var lines = content.Split('\n');
        var inFrontmatter = true;
        var contentLines = new List<string>();

        foreach (var line in lines.Skip(1))
        {
            if (line.Trim() == "---" && inFrontmatter)
            {
                inFrontmatter = false;
                continue;
            }
            if (!inFrontmatter)
                contentLines.Add(line);
        }

        return string.Join('\n', contentLines).Trim();
    }

    [GeneratedRegex(@"\[([^\]]+)\]\(([^)]+)\)")]
    private static partial Regex LinkPattern();
}

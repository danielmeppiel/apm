using System.Text.RegularExpressions;
using Apm.Cli.Utils;

namespace Apm.Cli.Models;

/// <summary>Raised when a virtual package file has an invalid extension.</summary>
public class InvalidVirtualPackageExtensionException : ArgumentException
{
    public InvalidVirtualPackageExtensionException(string message) : base(message) { }
}

/// <summary>Represents a reference to an APM dependency.</summary>
public class DependencyReference
{
    /// <summary>e.g., "user/repo" for GitHub or "org/project/repo" for Azure DevOps</summary>
    public string RepoUrl { get; set; }

    /// <summary>Optional host (github.com, dev.azure.com, or enterprise host)</summary>
    public string? Host { get; set; }

    /// <summary>e.g., "main", "v1.0.0", "abc123"</summary>
    public string? Reference { get; set; }

    /// <summary>Optional alias for the dependency</summary>
    public string? Alias { get; set; }

    /// <summary>Path for virtual packages (e.g., "prompts/file.prompt.md")</summary>
    public string? VirtualPath { get; set; }

    /// <summary>True if this is a virtual package (individual file or collection)</summary>
    public bool IsVirtual { get; set; }

    /// <summary>Azure DevOps organization</summary>
    public string? AdoOrganization { get; set; }

    /// <summary>Azure DevOps project</summary>
    public string? AdoProject { get; set; }

    /// <summary>Azure DevOps repository</summary>
    public string? AdoRepo { get; set; }

    /// <summary>Supported file extensions for virtual packages.</summary>
    public static readonly string[] VirtualFileExtensions =
        [".prompt.md", ".instructions.md", ".chatmode.md", ".agent.md"];

    private static readonly Regex PathComponentRegex = new(@"^[a-zA-Z0-9._-]+$", RegexOptions.Compiled);
    private static readonly Regex SshUrlRegex = new(@"^git@([^:]+):(.+)$", RegexOptions.Compiled);
    private static readonly Regex CommitShaRegex = new(@"^[a-f0-9]{7,40}$", RegexOptions.Compiled | RegexOptions.IgnoreCase);
    private static readonly Regex SemverTagRegex = new(@"^v?\d+\.\d+\.\d+", RegexOptions.Compiled);
    private static readonly Regex GitHubRepoRegex = new(@"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$", RegexOptions.Compiled);
    private static readonly Regex AdoRepoRegex = new(@"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$", RegexOptions.Compiled);

    public DependencyReference(string repoUrl)
    {
        RepoUrl = repoUrl;
    }

    /// <summary>Check if this reference points to Azure DevOps.</summary>
    public bool IsAzureDevOps() => Host != null && GitHubHost.IsAzureDevOpsHostname(Host);

    /// <summary>Check if this is a virtual file package (individual file).</summary>
    public bool IsVirtualFile()
    {
        if (!IsVirtual || string.IsNullOrEmpty(VirtualPath)) return false;
        return VirtualFileExtensions.Any(ext => VirtualPath.EndsWith(ext, StringComparison.Ordinal));
    }

    /// <summary>Check if this is a virtual collection package.</summary>
    public bool IsVirtualCollection()
    {
        if (!IsVirtual || string.IsNullOrEmpty(VirtualPath)) return false;
        return VirtualPath.Contains("/collections/") || VirtualPath.StartsWith("collections/");
    }

    /// <summary>Check if this is a virtual subdirectory package (e.g., Claude Skill).</summary>
    public bool IsVirtualSubdirectory()
    {
        if (!IsVirtual || string.IsNullOrEmpty(VirtualPath)) return false;
        return !IsVirtualFile() && !IsVirtualCollection();
    }

    /// <summary>Generate a package name for this virtual package.</summary>
    public string GetVirtualPackageName()
    {
        if (!IsVirtual || string.IsNullOrEmpty(VirtualPath))
            return RepoUrl.Split('/').Last();

        var repoParts = RepoUrl.Split('/');
        var repoName = repoParts.Length > 0 ? repoParts.Last() : "package";
        var pathParts = VirtualPath.Split('/');

        if (IsVirtualCollection())
        {
            var collectionName = pathParts.Last();
            foreach (var ext in new[] { ".collection.yml", ".collection.yaml" })
            {
                if (collectionName.EndsWith(ext, StringComparison.Ordinal))
                {
                    collectionName = collectionName[..^ext.Length];
                    break;
                }
            }
            return $"{repoName}-{collectionName}";
        }

        var filename = pathParts.Last();
        foreach (var ext in VirtualFileExtensions)
        {
            if (filename.EndsWith(ext, StringComparison.Ordinal))
            {
                filename = filename[..^ext.Length];
                break;
            }
        }
        return $"{repoName}-{filename}";
    }

    /// <summary>Get a unique key for this dependency for deduplication.</summary>
    public string GetUniqueKey()
        => IsVirtual && !string.IsNullOrEmpty(VirtualPath) ? $"{RepoUrl}/{VirtualPath}" : RepoUrl;

    /// <summary>Get the canonical dependency string as stored in apm.yml.</summary>
    public string GetCanonicalDependencyString() => GetUniqueKey();

    /// <summary>
    /// Get the canonical filesystem path where this package should be installed.
    /// </summary>
    public string GetInstallPath(string apmModulesDir)
    {
        var repoParts = RepoUrl.Split('/');

        if (IsVirtual)
        {
            if (IsVirtualSubdirectory())
            {
                if (IsAzureDevOps() && repoParts.Length >= 3)
                    return Path.Combine(apmModulesDir, repoParts[0], repoParts[1], repoParts[2], VirtualPath!);
                if (repoParts.Length >= 2)
                    return Path.Combine(apmModulesDir, repoParts[0], repoParts[1], VirtualPath!);
            }
            else
            {
                var packageName = GetVirtualPackageName();
                if (IsAzureDevOps() && repoParts.Length >= 3)
                    return Path.Combine(apmModulesDir, repoParts[0], repoParts[1], packageName);
                if (repoParts.Length >= 2)
                    return Path.Combine(apmModulesDir, repoParts[0], packageName);
            }
        }
        else
        {
            if (IsAzureDevOps() && repoParts.Length >= 3)
                return Path.Combine(apmModulesDir, repoParts[0], repoParts[1], repoParts[2]);
            if (repoParts.Length >= 2)
                return Path.Combine(apmModulesDir, repoParts[0], repoParts[1]);
        }

        // Fallback: join all parts
        return Path.Combine([apmModulesDir, .. repoParts]);
    }

    /// <summary>Convert to full repository URL.</summary>
    public string ToGitHubUrl()
    {
        var host = Host ?? GitHubHost.DefaultHost();
        if (IsAzureDevOps())
            return $"https://{host}/{AdoOrganization}/{AdoProject}/_git/{AdoRepo}";
        return $"https://{host}/{RepoUrl}";
    }

    /// <summary>Convert to a clone-friendly URL.</summary>
    public string ToCloneUrl() => ToGitHubUrl();

    /// <summary>Get display name for this dependency (alias or repo name).</summary>
    public string GetDisplayName()
    {
        if (!string.IsNullOrEmpty(Alias)) return Alias;
        if (IsVirtual) return GetVirtualPackageName();
        return RepoUrl;
    }

    /// <summary>Build the dependency string representation (for apm.yml serialization).</summary>
    public string ToDependencyString()
    {
        var result = !string.IsNullOrEmpty(Host) ? $"{Host}/{RepoUrl}" : RepoUrl;
        if (!string.IsNullOrEmpty(VirtualPath))
            result += $"/{VirtualPath}";
        if (!string.IsNullOrEmpty(Reference))
            result += $"#{Reference}";
        if (!string.IsNullOrEmpty(Alias))
            result += $"@{Alias}";
        return result;
    }

    public override string ToString() => ToDependencyString();

    /// <summary>
    /// Parse a dependency string into a DependencyReference.
    /// Supports: user/repo, user/repo#branch, host.com/user/repo, dev.azure.com/org/project/repo,
    /// user/repo/path/to/file.md (virtual packages), user/repo@alias, etc.
    /// </summary>
    public static DependencyReference Parse(string dependencyStr)
    {
        if (string.IsNullOrWhiteSpace(dependencyStr))
            throw new ArgumentException("Empty dependency string");

        // Check for control characters
        if (dependencyStr.Any(c => c < 32))
            throw new ArgumentException("Dependency string contains invalid control characters");

        // SECURITY: Reject protocol-relative URLs
        if (dependencyStr.StartsWith("//"))
            throw new ArgumentException(GitHubHost.UnsupportedHostError("//...",
                context: "Protocol-relative URLs are not supported"));

        var workStr = dependencyStr;

        // Temporarily remove reference and alias for path segment counting
        var tempStr = workStr;
        if (tempStr.Contains('@') && !tempStr.StartsWith("git@"))
            tempStr = tempStr[..tempStr.LastIndexOf('@')];
        if (tempStr.Contains('#'))
            tempStr = tempStr[..tempStr.LastIndexOf('#')];

        var isVirtualPackage = false;
        string? virtualPath = null;
        string? validatedHost = null;

        if (!tempStr.StartsWith("git@") && !tempStr.StartsWith("https://") && !tempStr.StartsWith("http://"))
        {
            var checkStr = tempStr;

            if (checkStr.Contains('/'))
            {
                var firstSegment = checkStr.Split('/')[0];

                if (firstSegment.Contains('.'))
                {
                    // Might be a hostname — validate it
                    var testUrl = $"https://{checkStr}";
                    if (Uri.TryCreate(testUrl, UriKind.Absolute, out var parsed))
                    {
                        var hostname = parsed.Host;
                        if (GitHubHost.IsSupportedGitHost(hostname))
                        {
                            validatedHost = hostname;
                            var pathParts = parsed.AbsolutePath.TrimStart('/').Split('/');
                            if (pathParts.Length >= 2)
                                checkStr = string.Join("/", checkStr.Split('/').Skip(1));
                        }
                        else
                        {
                            throw new ArgumentException(
                                GitHubHost.UnsupportedHostError(hostname));
                        }
                    }
                    else
                    {
                        throw new ArgumentException(
                            GitHubHost.UnsupportedHostError(firstSegment));
                    }
                }
                else if (checkStr.StartsWith("gh/"))
                {
                    checkStr = string.Join("/", checkStr.Split('/').Skip(1));
                }
            }

            var pathSegments = checkStr.Split('/', StringSplitOptions.RemoveEmptyEntries);
            var isAdo = validatedHost != null && GitHubHost.IsAzureDevOpsHostname(validatedHost);

            // Handle _git in ADO URLs
            var segList = pathSegments.ToList();
            var gitIdx = segList.IndexOf("_git");
            if (isAdo && gitIdx >= 0)
            {
                segList.RemoveAt(gitIdx);
                pathSegments = segList.ToArray();
            }

            var minBaseSegments = isAdo ? 3 : 2;
            var minVirtualSegments = minBaseSegments + 1;

            if (pathSegments.Length >= minVirtualSegments)
            {
                isVirtualPackage = true;
                virtualPath = string.Join("/", pathSegments.Skip(minBaseSegments));

                if (!checkStr.Contains("/collections/") && !virtualPath.StartsWith("collections/"))
                {
                    if (!VirtualFileExtensions.Any(ext => virtualPath.EndsWith(ext, StringComparison.Ordinal)))
                    {
                        var lastSegment = virtualPath.Split('/').Last();
                        if (lastSegment.Contains('.'))
                        {
                            throw new InvalidVirtualPackageExtensionException(
                                $"Invalid virtual package path '{virtualPath}'. " +
                                $"Individual files must end with one of: {string.Join(", ", VirtualFileExtensions)}. " +
                                "For subdirectory packages, the path should not have a file extension.");
                        }
                    }
                }
            }
        }

        // Handle SSH URLs first
        string? host = null;
        string repoUrl;
        string? reference = null;
        string? alias = null;

        var sshMatch = SshUrlRegex.Match(dependencyStr);
        if (sshMatch.Success)
        {
            host = sshMatch.Groups[1].Value;
            var sshRepoPart = sshMatch.Groups[2].Value;
            if (sshRepoPart.EndsWith(".git"))
                sshRepoPart = sshRepoPart[..^4];

            if (sshRepoPart.Contains('@'))
            {
                var idx = sshRepoPart.LastIndexOf('@');
                alias = sshRepoPart[(idx + 1)..].Trim();
                sshRepoPart = sshRepoPart[..idx];
            }

            if (sshRepoPart.Contains('#'))
            {
                var idx = sshRepoPart.LastIndexOf('#');
                reference = sshRepoPart[(idx + 1)..].Trim();
                sshRepoPart = sshRepoPart[..idx];
            }

            repoUrl = sshRepoPart.Trim();
        }
        else
        {
            var depStr = dependencyStr;

            // Handle alias (@alias) for non-SSH URLs
            if (depStr.Contains('@'))
            {
                var idx = depStr.LastIndexOf('@');
                alias = depStr[(idx + 1)..].Trim();
                depStr = depStr[..idx];
            }

            // Handle reference (#ref)
            if (depStr.Contains('#'))
            {
                var idx = depStr.LastIndexOf('#');
                reference = depStr[(idx + 1)..].Trim();
                depStr = depStr[..idx];
            }

            repoUrl = depStr.Trim();

            // For virtual packages, extract just the owner/repo part
            if (isVirtualPackage && !repoUrl.StartsWith("https://") && !repoUrl.StartsWith("http://"))
            {
                var parts = repoUrl.Split('/').ToList();

                // Handle _git in path
                var gIdx = parts.IndexOf("_git");
                if (gIdx >= 0) parts.RemoveAt(gIdx);

                if (parts.Count >= 3 && GitHubHost.IsSupportedGitHost(parts[0]))
                {
                    host = parts[0];
                    if (GitHubHost.IsAzureDevOpsHostname(parts[0]))
                    {
                        if (parts.Count < 5)
                            throw new ArgumentException(
                                "Invalid Azure DevOps virtual package format: must be dev.azure.com/org/project/repo/path");
                        repoUrl = string.Join("/", parts.Skip(1).Take(3));
                    }
                    else
                    {
                        repoUrl = string.Join("/", parts.Skip(1).Take(2));
                    }
                }
                else if (parts.Count >= 2)
                {
                    host ??= GitHubHost.DefaultHost();
                    if (validatedHost != null && GitHubHost.IsAzureDevOpsHostname(validatedHost))
                    {
                        if (parts.Count < 4)
                            throw new ArgumentException(
                                "Invalid Azure DevOps virtual package format: expected at least org/project/repo/path");
                        repoUrl = string.Join("/", parts.Take(3));
                    }
                    else
                    {
                        repoUrl = string.Join("/", parts.Take(2));
                    }
                }
            }

            // Normalize URL format
            if (repoUrl.StartsWith("https://") || repoUrl.StartsWith("http://"))
            {
                if (!Uri.TryCreate(repoUrl, UriKind.Absolute, out var parsedUrl))
                    throw new ArgumentException($"Invalid repository URL: {repoUrl}");

                var parsedHostname = parsedUrl.Host;
                if (!GitHubHost.IsSupportedGitHost(parsedHostname))
                    throw new ArgumentException(GitHubHost.UnsupportedHostError(parsedHostname));

                host = parsedHostname;

                var path = parsedUrl.AbsolutePath.Trim('/');
                if (string.IsNullOrEmpty(path))
                    throw new ArgumentException("Repository path cannot be empty");

                if (path.EndsWith(".git"))
                    path = path[..^4];

                var pathParts = path.Split('/').ToList();
                var pgIdx = pathParts.IndexOf("_git");
                if (pgIdx >= 0) pathParts.RemoveAt(pgIdx);

                var isAdoParsed = GitHubHost.IsAzureDevOpsHostname(parsedHostname);
                var expParts = isAdoParsed ? 3 : 2;

                if (pathParts.Count != expParts)
                {
                    if (isAdoParsed)
                        throw new ArgumentException(
                            $"Invalid Azure DevOps repository path: expected 'org/project/repo', got '{path}'");
                    throw new ArgumentException(
                        $"Invalid repository path: expected 'user/repo', got '{path}'");
                }

                for (int i = 0; i < pathParts.Count; i++)
                {
                    if (string.IsNullOrEmpty(pathParts[i]))
                        throw new ArgumentException($"Invalid repository format: path component {i + 1} cannot be empty");
                    if (!PathComponentRegex.IsMatch(pathParts[i]))
                        throw new ArgumentException($"Invalid repository path component: {pathParts[i]}");
                }

                repoUrl = string.Join("/", pathParts);
            }
            else
            {
                var parts = repoUrl.Split('/').ToList();

                // Handle _git in path
                var gIdx = parts.IndexOf("_git");
                if (gIdx >= 0) parts.RemoveAt(gIdx);

                string userRepo;
                if (parts.Count >= 3 && GitHubHost.IsSupportedGitHost(parts[0]))
                {
                    host = parts[0];
                    if (GitHubHost.IsAzureDevOpsHostname(host) && parts.Count >= 4)
                        userRepo = string.Join("/", parts.Skip(1).Take(3));
                    else
                        userRepo = string.Join("/", parts.Skip(1).Take(2));
                }
                else if (parts.Count >= 2 && !parts[0].Contains('.'))
                {
                    host ??= GitHubHost.DefaultHost();
                    if (GitHubHost.IsAzureDevOpsHostname(host) && parts.Count >= 3)
                        userRepo = string.Join("/", parts.Take(3));
                    else
                        userRepo = string.Join("/", parts.Take(2));
                }
                else
                {
                    throw new ArgumentException(
                        "Use 'user/repo' or 'github.com/user/repo' or 'dev.azure.com/org/project/repo' format");
                }

                if (string.IsNullOrEmpty(userRepo) || !userRepo.Contains('/'))
                    throw new ArgumentException(
                        $"Invalid repository format: {repoUrl}. Expected 'user/repo' or 'org/project/repo'");

                var uParts = userRepo.Split('/');
                var isAdoHost = !string.IsNullOrEmpty(host) && GitHubHost.IsAzureDevOpsHostname(host);
                var expectedParts = isAdoHost ? 3 : 2;

                if (uParts.Length < expectedParts)
                {
                    if (isAdoHost)
                        throw new ArgumentException(
                            $"Invalid Azure DevOps repository format: {repoUrl}. Expected 'org/project/repo'");
                    throw new ArgumentException(
                        $"Invalid repository format: {repoUrl}. Expected 'user/repo'");
                }

                foreach (var part in uParts)
                {
                    if (!PathComponentRegex.IsMatch(part.TrimEnd('.').Replace(".git", "")))
                        throw new ArgumentException($"Invalid repository path component: {part}");
                }

                // Construct full URL for validation
                var githubUrl = $"https://{host}/{userRepo}";
                if (!Uri.TryCreate(githubUrl, UriKind.Absolute, out var fullParsed))
                    throw new ArgumentException($"Invalid repository URL: {repoUrl}");

                var parsedHostname = fullParsed.Host;
                if (!GitHubHost.IsSupportedGitHost(parsedHostname))
                    throw new ArgumentException(GitHubHost.UnsupportedHostError(parsedHostname));

                var path = fullParsed.AbsolutePath.Trim('/');
                if (string.IsNullOrEmpty(path))
                    throw new ArgumentException("Repository path cannot be empty");

                if (path.EndsWith(".git"))
                    path = path[..^4];

                var pathParts = path.Split('/').ToList();
                var pgIdx = pathParts.IndexOf("_git");
                if (pgIdx >= 0) pathParts.RemoveAt(pgIdx);

                var isAdoParsed = GitHubHost.IsAzureDevOpsHostname(parsedHostname);
                var expParts = isAdoParsed ? 3 : 2;

                if (pathParts.Count != expParts)
                {
                    if (isAdoParsed)
                        throw new ArgumentException(
                            $"Invalid Azure DevOps repository path: expected 'org/project/repo', got '{path}'");
                    throw new ArgumentException(
                        $"Invalid repository path: expected 'user/repo', got '{path}'");
                }

                for (int i = 0; i < pathParts.Count; i++)
                {
                    if (string.IsNullOrEmpty(pathParts[i]))
                        throw new ArgumentException($"Invalid repository format: path component {i + 1} cannot be empty");
                    if (!PathComponentRegex.IsMatch(pathParts[i]))
                        throw new ArgumentException($"Invalid repository path component: {pathParts[i]}");
                }

                repoUrl = string.Join("/", pathParts);
                host ??= GitHubHost.DefaultHost();
            }
        }

        // Validate repo format based on host type
        string? adoOrg = null, adoProject = null, adoRepo = null;
        var isAdoFinal = !string.IsNullOrEmpty(host) && GitHubHost.IsAzureDevOpsHostname(host);

        if (isAdoFinal)
        {
            if (!AdoRepoRegex.IsMatch(repoUrl))
                throw new ArgumentException(
                    $"Invalid Azure DevOps repository format: {repoUrl}. Expected 'org/project/repo'");
            var adoParts = repoUrl.Split('/');
            adoOrg = adoParts[0];
            adoProject = adoParts[1];
            adoRepo = adoParts[2];
        }
        else
        {
            if (!GitHubRepoRegex.IsMatch(repoUrl))
                throw new ArgumentException(
                    $"Invalid repository format: {repoUrl}. Expected 'user/repo'");
        }

        if (!string.IsNullOrEmpty(alias) && !PathComponentRegex.IsMatch(alias))
            throw new ArgumentException(
                $"Invalid alias: {alias}. Aliases can only contain letters, numbers, dots, underscores, and hyphens");

        return new DependencyReference(repoUrl)
        {
            Host = host,
            Reference = reference,
            Alias = alias,
            VirtualPath = virtualPath,
            IsVirtual = isVirtualPackage,
            AdoOrganization = adoOrg,
            AdoProject = adoProject,
            AdoRepo = adoRepo
        };
    }

    /// <summary>Parse a git reference string to determine its type.</summary>
    public static (GitReferenceType Type, string Reference) ParseGitReference(string? refString)
    {
        if (string.IsNullOrWhiteSpace(refString))
            return (GitReferenceType.Branch, "main");

        var r = refString.Trim();
        if (CommitShaRegex.IsMatch(r))
            return (GitReferenceType.Commit, r);
        if (SemverTagRegex.IsMatch(r))
            return (GitReferenceType.Tag, r);
        return (GitReferenceType.Branch, r);
    }
}

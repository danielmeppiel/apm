using System.Text.RegularExpressions;
using Apm.Cli.Core;
using Apm.Cli.Models;
using Apm.Cli.Utils;
using LibGit2Sharp;

namespace Apm.Cli.Dependencies;

/// <summary>
/// Normalize a collection virtual path by stripping any existing extension.
/// </summary>
public static class CollectionPathHelper
{
    public static string NormalizeCollectionPath(string virtualPath)
    {
        foreach (var ext in new[] { ".collection.yml", ".collection.yaml" })
        {
            if (virtualPath.EndsWith(ext, StringComparison.Ordinal))
                return virtualPath[..^ext.Length];
        }
        return virtualPath;
    }
}

/// <summary>Downloads and validates APM packages from GitHub repositories.</summary>
public class GitHubPackageDownloader : IPackageDownloader
{
    private readonly TokenManager _tokenManager = new();
    private readonly Dictionary<string, string> _gitEnv;
    private readonly string? _githubToken;
    private readonly string? _adoToken;
    private string? _githubHost;

    /// <summary>Whether a GitHub token is available.</summary>
    public bool HasGitHubToken => _githubToken != null;

    /// <summary>Whether an Azure DevOps token is available.</summary>
    public bool HasAdoToken => _adoToken != null;

    public GitHubPackageDownloader()
    {
        _gitEnv = SetupGitEnvironment();
        _githubToken = _tokenManager.GetTokenForPurpose("modules", _gitEnv);
        _adoToken = _tokenManager.GetTokenForPurpose("ado_modules", _gitEnv);
    }

    private Dictionary<string, string> SetupGitEnvironment()
    {
        var env = _tokenManager.SetupEnvironment();
        env["GIT_TERMINAL_PROMPT"] = "0";
        env["GIT_ASKPASS"] = "echo";
        env["GIT_CONFIG_NOSYSTEM"] = "1";
        return env;
    }

    private static void Debug(string message)
    {
        if (Environment.GetEnvironmentVariable("APM_DEBUG") != null)
            Console.Error.WriteLine($"[DEBUG] {message}");
    }

    /// <summary>Sanitize Git error messages to remove sensitive auth information.</summary>
    public string SanitizeGitError(string errorMessage)
    {
        var sanitized = GitHubHost.SanitizeTokenUrlInMessage(errorMessage);

        // Sanitize Azure DevOps URLs
        sanitized = Regex.Replace(sanitized, @"https://[^@\s]+@([^\s/]+)", @"https://***@$1");

        // Remove standalone GitHub tokens
        sanitized = Regex.Replace(sanitized, @"(ghp_|gho_|ghu_|ghs_|ghr_)[a-zA-Z0-9_]+", "***");

        // Remove env var values that might contain tokens
        sanitized = Regex.Replace(sanitized,
            @"(GITHUB_TOKEN|GITHUB_APM_PAT|ADO_APM_PAT|GH_TOKEN|GITHUB_COPILOT_PAT)=[^\s]+",
            @"$1=***");

        return sanitized;
    }

    /// <summary>Build the appropriate repository URL for cloning.</summary>
    internal string BuildRepoUrl(string repoRef, bool useSsh = false, DependencyReference? depRef = null)
    {
        var host = depRef?.Host ?? _githubHost ?? GitHubHost.DefaultHost();
        var isAdo = (depRef != null && depRef.IsAzureDevOps()) || GitHubHost.IsAzureDevOpsHostname(host);

        if (isAdo && depRef?.AdoOrganization != null)
        {
            if (useSsh)
                return GitHubHost.BuildAdoSshUrl(depRef.AdoOrganization!, depRef.AdoProject!, depRef.AdoRepo!);
            if (_adoToken != null)
                return GitHubHost.BuildAdoHttpsCloneUrl(depRef.AdoOrganization!, depRef.AdoProject!, depRef.AdoRepo!, _adoToken, host);
            return GitHubHost.BuildAdoHttpsCloneUrl(depRef.AdoOrganization!, depRef.AdoProject!, depRef.AdoRepo!, host: host);
        }

        if (useSsh)
            return GitHubHost.BuildSshUrl(host, repoRef);
        if (_githubToken != null)
            return GitHubHost.BuildHttpsCloneUrl(host, repoRef, _githubToken);
        return GitHubHost.BuildHttpsCloneUrl(host, repoRef);
    }

    /// <summary>
    /// Attempt to clone a repository with fallback authentication methods.
    /// Uses LibGit2Sharp for cloning.
    /// </summary>
    internal string CloneWithFallback(
        string repoUrlBase,
        string targetPath,
        DependencyReference? depRef = null,
        int? depth = null,
        string? branch = null)
    {
        Exception? lastError = null;
        var isAdo = depRef?.IsAzureDevOps() ?? false;
        var hasToken = isAdo ? _adoToken : _githubToken;

        // Method 1: Authenticated HTTPS
        if (hasToken != null)
        {
            try
            {
                var authUrl = BuildRepoUrl(repoUrlBase, useSsh: false, depRef: depRef);
                return CloneRepository(authUrl, targetPath, branch);
            }
            catch (LibGit2SharpException ex)
            {
                lastError = ex;
            }
        }

        // Method 2: SSH
        try
        {
            var sshUrl = BuildRepoUrl(repoUrlBase, useSsh: true, depRef: depRef);
            return CloneRepository(sshUrl, targetPath, branch);
        }
        catch (LibGit2SharpException ex)
        {
            lastError = ex;
        }

        // Method 3: Standard HTTPS (public repos)
        try
        {
            var httpsUrl = BuildRepoUrl(repoUrlBase, useSsh: false, depRef: depRef);
            return CloneRepository(httpsUrl, targetPath, branch);
        }
        catch (LibGit2SharpException ex)
        {
            lastError = ex;
        }

        var errorMsg = $"Failed to clone repository {repoUrlBase} using all available methods. ";
        if (isAdo && !HasAdoToken)
            errorMsg += "For private Azure DevOps repositories, set ADO_APM_PAT environment variable.";
        else if (!HasGitHubToken)
            errorMsg += "For private repositories, set GITHUB_APM_PAT or GITHUB_TOKEN environment variable, or ensure SSH keys are configured.";
        else
            errorMsg += "Please check repository access permissions and authentication setup.";

        if (lastError != null)
        {
            var sanitizedError = SanitizeGitError(lastError.Message);
            errorMsg += $" Last error: {sanitizedError}";
        }

        throw new InvalidOperationException(errorMsg);
    }

    internal virtual string CloneRepository(string url, string targetPath, string? branch = null)
    {
        var options = new CloneOptions();
        if (branch != null)
            options.BranchName = branch;

        return LibGit2Sharp.Repository.Clone(url, targetPath, options);
    }

    /// <summary>Download a single file from a repository (GitHub or Azure DevOps).</summary>
    public byte[] DownloadRawFile(DependencyReference depRef, string filePath, string gitRef = "main")
    {
        if (depRef.IsAzureDevOps())
            return DownloadAdoFile(depRef, filePath, gitRef);
        return DownloadGitHubFile(depRef, filePath, gitRef);
    }

    private byte[] DownloadAdoFile(DependencyReference depRef, string filePath, string gitRef = "main")
    {
        if (string.IsNullOrEmpty(depRef.AdoOrganization) ||
            string.IsNullOrEmpty(depRef.AdoProject) ||
            string.IsNullOrEmpty(depRef.AdoRepo))
        {
            throw new ArgumentException(
                $"Invalid Azure DevOps dependency reference: missing organization, project, or repo. " +
                $"Got: org={depRef.AdoOrganization}, project={depRef.AdoProject}, repo={depRef.AdoRepo}");
        }

        var host = depRef.Host ?? "dev.azure.com";
        var apiUrl = GitHubHost.BuildAdoApiUrl(depRef.AdoOrganization!, depRef.AdoProject!, depRef.AdoRepo!, filePath, gitRef, host);

        using var client = CreateHttpClient();
        if (_adoToken != null)
        {
            var auth = Convert.ToBase64String(System.Text.Encoding.UTF8.GetBytes($":{_adoToken}"));
            client.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Basic", auth);
        }

        return DownloadFileWithFallback(client, apiUrl, depRef, filePath, gitRef,
            (ref2) => GitHubHost.BuildAdoApiUrl(depRef.AdoOrganization!, depRef.AdoProject!, depRef.AdoRepo!, filePath, ref2, host),
            isAdo: true);
    }

    private byte[] DownloadGitHubFile(DependencyReference depRef, string filePath, string gitRef = "main")
    {
        var host = depRef.Host ?? GitHubHost.DefaultHost();
        var parts = depRef.RepoUrl.Split('/', 2);
        var (owner, repo) = (parts[0], parts[1]);

        var apiUrl = BuildGitHubApiUrl(host, owner, repo, filePath, gitRef);

        using var client = CreateHttpClient();
        client.DefaultRequestHeaders.Accept.Add(new System.Net.Http.Headers.MediaTypeWithQualityHeaderValue("application/vnd.github.v3.raw"));
        if (_githubToken != null)
            client.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("token", _githubToken);

        return DownloadFileWithFallback(client, apiUrl, depRef, filePath, gitRef,
            (ref2) => BuildGitHubApiUrl(host, owner, repo, filePath, ref2),
            isAdo: false);
    }

    private static string BuildGitHubApiUrl(string host, string owner, string repo, string filePath, string gitRef)
    {
        if (host == "github.com")
            return $"https://api.github.com/repos/{owner}/{repo}/contents/{filePath}?ref={gitRef}";
        if (host.EndsWith(".ghe.com"))
            return $"https://api.{host}/repos/{owner}/{repo}/contents/{filePath}?ref={gitRef}";
        return $"https://{host}/api/v3/repos/{owner}/{repo}/contents/{filePath}?ref={gitRef}";
    }

    private byte[] DownloadFileWithFallback(
        HttpClient client,
        string apiUrl,
        DependencyReference depRef,
        string filePath,
        string gitRef,
        Func<string, string> buildFallbackUrl,
        bool isAdo)
    {
        try
        {
            var response = client.GetAsync(apiUrl).GetAwaiter().GetResult();
            response.EnsureSuccessStatusCode();
            return response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult();
        }
        catch (HttpRequestException ex) when (ex.StatusCode == System.Net.HttpStatusCode.NotFound)
        {
            if (gitRef is not ("main" or "master"))
                throw new InvalidOperationException($"File not found: {filePath} at ref '{gitRef}' in {depRef.RepoUrl}");

            var fallbackRef = gitRef == "main" ? "master" : "main";
            var fallbackUrl = buildFallbackUrl(fallbackRef);
            try
            {
                var response = client.GetAsync(fallbackUrl).GetAwaiter().GetResult();
                response.EnsureSuccessStatusCode();
                return response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult();
            }
            catch (HttpRequestException)
            {
                throw new InvalidOperationException(
                    $"File not found: {filePath} in {depRef.RepoUrl} (tried refs: {gitRef}, {fallbackRef})");
            }
        }
        catch (HttpRequestException ex) when (ex.StatusCode is System.Net.HttpStatusCode.Unauthorized or System.Net.HttpStatusCode.Forbidden)
        {
            var errorMsg = $"Authentication failed for {depRef.RepoUrl}. ";
            if (isAdo)
                errorMsg += _adoToken == null
                    ? "Please set ADO_APM_PAT with an Azure DevOps PAT with Code (Read) scope."
                    : "Please check your Azure DevOps PAT permissions.";
            else
                errorMsg += _githubToken == null
                    ? "This might be a private repository. Please set GITHUB_APM_PAT or GITHUB_TOKEN."
                    : "Please check your GitHub token permissions.";
            throw new InvalidOperationException(errorMsg);
        }
        catch (HttpRequestException ex)
        {
            throw new InvalidOperationException($"Network error downloading {filePath}: {ex.Message}");
        }
    }

    private static HttpClient CreateHttpClient()
    {
        var client = new HttpClient { Timeout = TimeSpan.FromSeconds(30) };
        client.DefaultRequestHeaders.UserAgent.ParseAdd("apm-cli/1.0");
        return client;
    }

    /// <summary>Validate that a virtual package (file, collection, or subdirectory) exists.</summary>
    public bool ValidateVirtualPackageExists(DependencyReference depRef)
    {
        if (!depRef.IsVirtual)
            throw new ArgumentException("Can only validate virtual packages with this method");

        var gitRef = depRef.Reference ?? "main";

        if (depRef.IsVirtualCollection())
        {
            try { DownloadRawFile(depRef, $"{depRef.VirtualPath}.collection.yml", gitRef); return true; }
            catch (InvalidOperationException) { return false; }
        }

        if (depRef.IsVirtualFile())
        {
            try { DownloadRawFile(depRef, depRef.VirtualPath!, gitRef); return true; }
            catch (InvalidOperationException) { return false; }
        }

        if (depRef.IsVirtualSubdirectory())
        {
            try { DownloadRawFile(depRef, $"{depRef.VirtualPath}/apm.yml", gitRef); return true; }
            catch (InvalidOperationException) { }

            try { DownloadRawFile(depRef, $"{depRef.VirtualPath}/SKILL.md", gitRef); return true; }
            catch (InvalidOperationException) { }

            return false;
        }

        try { DownloadRawFile(depRef, depRef.VirtualPath!, gitRef); return true; }
        catch (InvalidOperationException) { return false; }
    }

    /// <summary>Download a single file as a virtual APM package.</summary>
    public PackageInfo DownloadVirtualFilePackage(DependencyReference depRef, string targetPath)
    {
        if (!depRef.IsVirtual || string.IsNullOrEmpty(depRef.VirtualPath))
            throw new ArgumentException("Dependency must be a virtual file package");
        if (!depRef.IsVirtualFile())
            throw new ArgumentException(
                $"Path '{depRef.VirtualPath}' is not a valid individual file. " +
                $"Must end with one of: {string.Join(", ", DependencyReference.VirtualFileExtensions)}");

        var gitRef = depRef.Reference ?? "main";
        var fileContent = DownloadRawFile(depRef, depRef.VirtualPath!, gitRef);

        Directory.CreateDirectory(targetPath);

        var subdirs = new Dictionary<string, string>
        {
            [".prompt.md"] = "prompts",
            [".instructions.md"] = "instructions",
            [".chatmode.md"] = "chatmodes",
            [".agent.md"] = "agents"
        };

        var filename = depRef.VirtualPath!.Split('/').Last();
        string? subdir = null;
        foreach (var (ext, dirName) in subdirs)
        {
            if (depRef.VirtualPath.EndsWith(ext, StringComparison.Ordinal))
            {
                subdir = dirName;
                break;
            }
        }
        if (subdir == null)
            throw new ArgumentException($"Unknown file extension for {depRef.VirtualPath}");

        var apmDir = Path.Combine(targetPath, ".apm", subdir);
        Directory.CreateDirectory(apmDir);
        File.WriteAllBytes(Path.Combine(apmDir, filename), fileContent);

        var packageName = depRef.GetVirtualPackageName();
        var description = $"Virtual package containing {filename}";
        try
        {
            var contentStr = System.Text.Encoding.UTF8.GetString(fileContent);
            if (contentStr.StartsWith("---\n"))
            {
                var endIdx = contentStr.IndexOf("\n---\n", 4, StringComparison.Ordinal);
                if (endIdx > 0)
                {
                    var frontmatter = contentStr[4..endIdx];
                    foreach (var line in frontmatter.Split('\n'))
                    {
                        if (line.StartsWith("description:"))
                        {
                            description = line.Split(':', 2)[1].Trim().Trim('"', '\'');
                            break;
                        }
                    }
                }
            }
        }
        catch { /* use default description */ }

        var apmYmlContent = $"""
            name: {packageName}
            version: 1.0.0
            description: {description}
            author: {depRef.RepoUrl.Split('/')[0]}
            """.Replace("            ", "");
        File.WriteAllText(Path.Combine(targetPath, "apm.yml"), apmYmlContent);

        var package = new ApmPackage
        {
            Name = packageName,
            Version = "1.0.0",
            Description = description,
            Author = depRef.RepoUrl.Split('/')[0],
            Source = depRef.ToGitHubUrl(),
            PackagePath = targetPath
        };

        return new PackageInfo(package, targetPath)
        {
            InstalledAt = DateTime.UtcNow.ToString("o"),
            DependencyRef = depRef
        };
    }

    /// <summary>Download a subdirectory from a repo as an APM package.</summary>
    public PackageInfo DownloadSubdirectoryPackage(DependencyReference depRef, string targetPath)
    {
        if (!depRef.IsVirtual || string.IsNullOrEmpty(depRef.VirtualPath))
            throw new ArgumentException("Dependency must be a virtual subdirectory package");
        if (!depRef.IsVirtualSubdirectory())
            throw new ArgumentException($"Path '{depRef.VirtualPath}' is not a valid subdirectory package");

        var gitRef = depRef.Reference;
        var subdirPath = depRef.VirtualPath!;

        var tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
        try
        {
            var tempClonePath = Path.Combine(tempDir, "repo");
            CloneWithFallback(depRef.RepoUrl, tempClonePath, depRef: depRef, branch: gitRef);

            var sourceSubdir = Path.Combine(tempClonePath, subdirPath.Replace('/', Path.DirectorySeparatorChar));
            if (!Directory.Exists(sourceSubdir))
                throw new InvalidOperationException($"Subdirectory '{subdirPath}' not found in repository");

            if (Directory.Exists(targetPath) && Directory.EnumerateFileSystemEntries(targetPath).Any())
            {
                Directory.Delete(targetPath, true);
            }
            Directory.CreateDirectory(targetPath);

            CopyDirectory(sourceSubdir, targetPath);
        }
        finally
        {
            try { if (Directory.Exists(tempDir)) Directory.Delete(tempDir, true); } catch { }
        }

        var apmYmlPath = Path.Combine(targetPath, "apm.yml");
        var hasApmYml = File.Exists(apmYmlPath);
        var hasSkillMd = File.Exists(Path.Combine(targetPath, "SKILL.md"));

        if (!hasApmYml && !hasSkillMd)
            throw new InvalidOperationException("Subdirectory is not a valid APM package or Claude Skill");

        ApmPackage package;
        if (hasApmYml)
        {
            package = ApmPackage.FromApmYml(apmYmlPath);
            package.Source = depRef.ToGitHubUrl();
        }
        else
        {
            package = new ApmPackage
            {
                Name = depRef.GetVirtualPackageName(),
                Version = "1.0.0",
                Source = depRef.ToGitHubUrl(),
                PackagePath = targetPath
            };
        }

        var resolvedRef = new ResolvedReference(
            gitRef ?? "default",
            GitReferenceType.Branch,
            "unknown",
            gitRef ?? "default");

        return new PackageInfo(package, targetPath)
        {
            ResolvedReference = resolvedRef,
            InstalledAt = DateTime.UtcNow.ToString("o"),
            DependencyRef = depRef
        };
    }

    /// <summary>Download a GitHub repository and validate it as an APM package.</summary>
    public PackageInfo DownloadPackage(string repoRef, string targetPath)
    {
        DependencyReference depRef;
        try
        {
            depRef = DependencyReference.Parse(repoRef);
        }
        catch (ArgumentException ex)
        {
            throw new ArgumentException($"Invalid repository reference '{repoRef}': {ex.Message}", ex);
        }

        if (depRef.Host != null)
            _githubHost = depRef.Host;

        // Handle virtual packages
        if (depRef.IsVirtual)
        {
            if (depRef.IsVirtualFile())
                return DownloadVirtualFilePackage(depRef, targetPath);
            if (depRef.IsVirtualSubdirectory())
                return DownloadSubdirectoryPackage(depRef, targetPath);
            throw new ArgumentException($"Unknown virtual package type for {depRef.VirtualPath}");
        }

        // Regular package: clone repository
        Directory.CreateDirectory(targetPath);
        if (Directory.Exists(targetPath) && Directory.EnumerateFileSystemEntries(targetPath).Any())
        {
            Directory.Delete(targetPath, true);
            Directory.CreateDirectory(targetPath);
        }

        var refName = depRef.Reference ?? "main";
        try
        {
            CloneWithFallback(depRef.RepoUrl, targetPath, depRef: depRef, branch: refName);

            // Remove .git directory
            var gitDir = Path.Combine(targetPath, ".git");
            if (Directory.Exists(gitDir))
                try { Directory.Delete(gitDir, true); } catch { }
        }
        catch (LibGit2SharpException ex)
        {
            var msg = ex.Message;
            if (msg.Contains("Authentication failed") || msg.Contains("Repository not found"))
            {
                var errorMsg = $"Failed to clone repository {depRef.RepoUrl}. ";
                errorMsg += !HasGitHubToken
                    ? "This might be a private repository that requires authentication. Please set GITHUB_APM_PAT or GITHUB_TOKEN environment variable."
                    : "Authentication failed. Please check your GitHub token permissions.";
                throw new InvalidOperationException(errorMsg);
            }
            throw new InvalidOperationException($"Failed to clone repository {depRef.RepoUrl}: {SanitizeGitError(msg)}");
        }

        // Validate package
        var apmYmlPath = Path.Combine(targetPath, "apm.yml");
        var hasApmYml = File.Exists(apmYmlPath);
        var hasSkillMd = File.Exists(Path.Combine(targetPath, "SKILL.md"));

        if (!hasApmYml && !hasSkillMd)
        {
            if (Directory.Exists(targetPath))
                try { Directory.Delete(targetPath, true); } catch { }
            throw new InvalidOperationException($"Invalid APM package {depRef.RepoUrl}: missing apm.yml or SKILL.md");
        }

        ApmPackage package;
        if (hasApmYml)
        {
            package = ApmPackage.FromApmYml(apmYmlPath);
        }
        else
        {
            package = new ApmPackage
            {
                Name = depRef.RepoUrl.Split('/').Last(),
                Version = "1.0.0",
                PackagePath = targetPath
            };
        }

        package.Source = depRef.ToGitHubUrl();

        var resolved = new ResolvedReference(repoRef, GitReferenceType.Branch, "unknown", refName);
        return new PackageInfo(package, targetPath)
        {
            ResolvedReference = resolved,
            InstalledAt = DateTime.UtcNow.ToString("o"),
            DependencyRef = depRef
        };
    }

    private static void CopyDirectory(string source, string destination)
    {
        Directory.CreateDirectory(destination);
        foreach (var file in Directory.GetFiles(source))
            File.Copy(file, Path.Combine(destination, Path.GetFileName(file)), true);
        foreach (var dir in Directory.GetDirectories(source))
            CopyDirectory(dir, Path.Combine(destination, Path.GetFileName(dir)));
    }
}

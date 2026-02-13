using Apm.Cli.Core;
using Apm.Cli.Dependencies;
using Apm.Cli.Models;
using Apm.Cli.Utils;
using AwesomeAssertions;
using FakeItEasy;
using LibGit2Sharp;

namespace Apm.Cli.Tests.Dependencies;

public class CollectionPathHelperTests
{
    [Theory]
    [InlineData("my-collection.collection.yml", "my-collection")]
    [InlineData("my-collection.collection.yaml", "my-collection")]
    [InlineData("my-collection", "my-collection")]
    [InlineData("path/to/file.collection.yml", "path/to/file")]
    [InlineData("no-extension", "no-extension")]
    public void NormalizeCollectionPath_StripsCollectionExtension(string input, string expected)
    {
        CollectionPathHelper.NormalizeCollectionPath(input).Should().Be(expected);
    }
}

public class GitHubDownloaderUrlTests
{
    [Fact]
    public void BuildSshUrl_FormatsCorrectly()
    {
        var url = GitHubHost.BuildSshUrl("github.com", "user/repo");
        url.Should().Be("git@github.com:user/repo.git");
    }

    [Fact]
    public void BuildHttpsCloneUrl_WithoutToken()
    {
        var url = GitHubHost.BuildHttpsCloneUrl("github.com", "user/repo");
        url.Should().Be("https://github.com/user/repo");
    }

    [Fact]
    public void BuildHttpsCloneUrl_WithToken()
    {
        var url = GitHubHost.BuildHttpsCloneUrl("github.com", "user/repo", "my-token");
        url.Should().Be("https://x-access-token:my-token@github.com/user/repo.git");
    }

    [Fact]
    public void BuildAdoHttpsCloneUrl_WithoutToken()
    {
        var url = GitHubHost.BuildAdoHttpsCloneUrl("myorg", "myproject", "myrepo");
        url.Should().Be("https://dev.azure.com/myorg/myproject/_git/myrepo");
    }

    [Fact]
    public void BuildAdoHttpsCloneUrl_WithToken()
    {
        var url = GitHubHost.BuildAdoHttpsCloneUrl("myorg", "myproject", "myrepo", "my-token");
        url.Should().Be("https://my-token@dev.azure.com/myorg/myproject/_git/myrepo");
    }

    [Fact]
    public void BuildAdoSshUrl_DefaultHost()
    {
        var url = GitHubHost.BuildAdoSshUrl("myorg", "myproject", "myrepo");
        url.Should().Be("git@ssh.dev.azure.com:v3/myorg/myproject/myrepo");
    }

    [Fact]
    public void BuildAdoSshUrl_CustomHost()
    {
        var url = GitHubHost.BuildAdoSshUrl("myorg", "myproject", "myrepo", "custom.host.com");
        url.Should().Be("ssh://git@custom.host.com/myorg/myproject/_git/myrepo");
    }

    [Fact]
    public void BuildAdoApiUrl_FormatsCorrectly()
    {
        var url = GitHubHost.BuildAdoApiUrl("myorg", "myproject", "myrepo", "path/to/file.md", "main");
        url.Should().Contain("dev.azure.com/myorg/myproject");
        url.Should().Contain("myrepo");
        url.Should().Contain("versionDescriptor.version=main");
    }

    [Theory]
    [InlineData("github.com", true)]
    [InlineData("mycompany.ghe.com", true)]
    [InlineData("dev.azure.com", false)]
    [InlineData("random.com", false)]
    public void IsGitHubHostname_IdentifiesGitHubHosts(string hostname, bool expected)
    {
        GitHubHost.IsGitHubHostname(hostname).Should().Be(expected);
    }

    [Theory]
    [InlineData("dev.azure.com", true)]
    [InlineData("myorg.visualstudio.com", true)]
    [InlineData("github.com", false)]
    [InlineData("random.com", false)]
    public void IsAzureDevOpsHostname_IdentifiesAdoHosts(string hostname, bool expected)
    {
        GitHubHost.IsAzureDevOpsHostname(hostname).Should().Be(expected);
    }

    [Theory]
    [InlineData("github.com", true)]
    [InlineData("mycompany.ghe.com", true)]
    [InlineData("dev.azure.com", true)]
    [InlineData("myorg.visualstudio.com", true)]
    [InlineData("random.com", false)]
    public void IsSupportedGitHost_IdentifiesSupportedHosts(string hostname, bool expected)
    {
        GitHubHost.IsSupportedGitHost(hostname).Should().Be(expected);
    }
}

public class GitHubDownloaderSanitizationTests
{
    [Fact]
    public void SanitizeGitError_RemovesGitHubTokens()
    {
        var downloader = new GitHubPackageDownloader();
        var msg = "Error: ghp_abc123def456 is invalid";
        var sanitized = downloader.SanitizeGitError(msg);

        sanitized.Should().NotContain("ghp_abc123def456");
        sanitized.Should().Contain("***");
    }

    [Fact]
    public void SanitizeGitError_RemovesEnvVarValues()
    {
        var downloader = new GitHubPackageDownloader();
        var msg = "GITHUB_TOKEN=secret123 was used";
        var sanitized = downloader.SanitizeGitError(msg);

        sanitized.Should().NotContain("secret123");
        sanitized.Should().Contain("GITHUB_TOKEN=***");
    }

    [Fact]
    public void SanitizeGitError_RemovesAdoTokenUrls()
    {
        var downloader = new GitHubPackageDownloader();
        var msg = "Failed to clone https://mytoken@dev.azure.com/org/project";
        var sanitized = downloader.SanitizeGitError(msg);

        sanitized.Should().NotContain("mytoken");
        sanitized.Should().Contain("***@");
    }
}

public class GitHubHostValidationTests
{
    [Theory]
    [InlineData("github.com", true)]
    [InlineData("my.company.com", true)]
    [InlineData("a.b", true)]
    [InlineData("", false)]
    [InlineData(null, false)]
    public void IsValidFqdn_ValidatesHostnames(string? hostname, bool expected)
    {
        GitHubHost.IsValidFqdn(hostname).Should().Be(expected);
    }

    [Fact]
    public void SanitizeTokenUrlInMessage_RemovesTokens()
    {
        var msg = "https://x-access-token:ghp_secret@github.com/user/repo";
        var sanitized = GitHubHost.SanitizeTokenUrlInMessage(msg);

        sanitized.Should().NotContain("ghp_secret");
        sanitized.Should().Contain("https://***@github.com");
    }

    [Fact]
    public void UnsupportedHostError_ContainsActionableInstructions()
    {
        var error = GitHubHost.UnsupportedHostError("custom.host.com");

        error.Should().Contain("Unsupported Git host");
        error.Should().Contain("custom.host.com");
        error.Should().Contain("GITHUB_HOST");
    }
}

/// <summary>
/// Tests for token precedence via TokenManager (mirrors Python TestGitHubDownloaderTokenPrecedence).
/// Uses explicit env dictionaries to avoid mutating process-level environment variables.
/// </summary>
public class GitHubDownloaderTokenPrecedenceTests
{
    [Fact]
    public void Modules_ApmPatTakesPrecedenceOverGitHubToken()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_APM_PAT"] = "apm-specific-token",
            ["GITHUB_TOKEN"] = "generic-token"
        };
        var token = new TokenManager().GetTokenForPurpose("modules", env);
        token.Should().Be("apm-specific-token");
    }

    [Fact]
    public void Modules_FallsBackToGitHubTokenWhenNoApmPat()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_TOKEN"] = "fallback-token"
        };
        var token = new TokenManager().GetTokenForPurpose("modules", env);
        token.Should().Be("fallback-token");
    }

    [Fact]
    public void Modules_ReturnsNullWhenNoTokensAvailable()
    {
        var env = new Dictionary<string, string>();
        var token = new TokenManager().GetTokenForPurpose("modules", env);
        token.Should().Be(null);
    }

    [Fact]
    public void AdoModules_DetectsAdoToken()
    {
        var env = new Dictionary<string, string>
        {
            ["ADO_APM_PAT"] = "ado-test-token"
        };
        var token = new TokenManager().GetTokenForPurpose("ado_modules", env);
        token.Should().Be("ado-test-token");
    }

    [Fact]
    public void AdoModules_ReturnsNullWhenOnlyGitHubTokenSet()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_APM_PAT"] = "github-token"
        };
        var token = new TokenManager().GetTokenForPurpose("ado_modules", env);
        token.Should().Be(null);
    }

    [Fact]
    public void MixedTokens_BothPurposesResolveCorrectly()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_APM_PAT"] = "github-token",
            ["ADO_APM_PAT"] = "ado-token"
        };
        var mgr = new TokenManager();
        mgr.GetTokenForPurpose("modules", env).Should().Be("github-token");
        mgr.GetTokenForPurpose("ado_modules", env).Should().Be("ado-token");
    }

    [Fact]
    public void Modules_GhTokenNotInPrecedence()
    {
        // GH_TOKEN alone should NOT resolve for modules purpose
        var env = new Dictionary<string, string>
        {
            ["GH_TOKEN"] = "gh-token-only"
        };
        var token = new TokenManager().GetTokenForPurpose("modules", env);
        token.Should().Be(null);
    }

    [Fact]
    public void Modules_EmptyStringTokenIgnored()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_APM_PAT"] = "",
            ["GITHUB_TOKEN"] = "fallback-token"
        };
        var token = new TokenManager().GetTokenForPurpose("modules", env);
        token.Should().Be("fallback-token");
    }
}

/// <summary>
/// Extended sanitization tests (mirrors Python TestGitHubDownloaderErrorMessages).
/// </summary>
public class GitHubDownloaderSanitizationExtendedTests
{
    [Fact]
    public void SanitizeGitError_RemovesGitHubApmPatEnvVar()
    {
        var downloader = new GitHubPackageDownloader();
        var msg = "Error: GITHUB_APM_PAT=ghp_secrettoken123 failed";
        var sanitized = downloader.SanitizeGitError(msg);

        sanitized.Should().NotContain("ghp_secrettoken123");
        sanitized.Should().Contain("GITHUB_APM_PAT=***");
    }

    [Fact]
    public void SanitizeGitError_RemovesTokenFromHttpsUrl()
    {
        var downloader = new GitHubPackageDownloader();
        var msg = "fatal: Authentication failed for 'https://x-access-token:ghp_secrettoken123@github.com/user/repo.git'";
        var sanitized = downloader.SanitizeGitError(msg);

        sanitized.Should().NotContain("ghp_secrettoken123");
        sanitized.Should().Contain("https://***@github.com");
    }

    [Fact]
    public void SanitizeGitError_RemovesAdoCloudToken()
    {
        var downloader = new GitHubPackageDownloader();
        var msg = "fatal: Authentication failed for 'https://ado_secret_pat@dev.azure.com/myorg/myproject/_git/myrepo'";
        var sanitized = downloader.SanitizeGitError(msg);

        sanitized.Should().NotContain("ado_secret_pat");
        sanitized.Should().Contain("https://***@dev.azure.com");
    }

    [Fact]
    public void SanitizeGitError_RemovesAdoCustomServerToken()
    {
        var downloader = new GitHubPackageDownloader();
        var msg = "fatal: Authentication failed for 'https://my_ado_token@ado.company.internal/DefaultCollection/Project/_git/repo'";
        var sanitized = downloader.SanitizeGitError(msg);

        sanitized.Should().NotContain("my_ado_token");
        sanitized.Should().Contain("https://***@ado.company.internal");
    }

    [Fact]
    public void SanitizeGitError_RemovesTfsServerToken()
    {
        var downloader = new GitHubPackageDownloader();
        var msg = "fatal: could not read from 'https://secret123@tfs.corp.net:8080/tfs/DefaultCollection/_git/myrepo'";
        var sanitized = downloader.SanitizeGitError(msg);

        sanitized.Should().NotContain("secret123");
        sanitized.Should().Contain("https://***@tfs.corp.net:8080");
    }

    [Fact]
    public void SanitizeGitError_RemovesAdoPatEnvVar()
    {
        var downloader = new GitHubPackageDownloader();
        var msg = "Error: ADO_APM_PAT=my_secret_ado_token failed to authenticate";
        var sanitized = downloader.SanitizeGitError(msg);

        sanitized.Should().NotContain("my_secret_ado_token");
        sanitized.Should().Contain("ADO_APM_PAT=***");
    }

    [Fact]
    public void SanitizeGitError_AuthErrorReferencesCorrectTokenNames()
    {
        var downloader = new GitHubPackageDownloader();
        var msg = "Authentication failed. For private repositories, set GITHUB_APM_PAT or GITHUB_TOKEN environment variable";
        var sanitized = downloader.SanitizeGitError(msg);

        sanitized.Should().Contain("GITHUB_APM_PAT");
        sanitized.Should().Contain("GITHUB_TOKEN");
    }

    [Fact]
    public void SanitizeGitError_RemovesGhTokenEnvVar()
    {
        var downloader = new GitHubPackageDownloader();
        var msg = "GH_TOKEN=ghp_mysecretvalue was used";
        var sanitized = downloader.SanitizeGitError(msg);

        sanitized.Should().NotContain("ghp_mysecretvalue");
        sanitized.Should().Contain("GH_TOKEN=***");
    }

    [Fact]
    public void SanitizeGitError_RemovesCopilotPatEnvVar()
    {
        var downloader = new GitHubPackageDownloader();
        var msg = "GITHUB_COPILOT_PAT=some_secret_value detected";
        var sanitized = downloader.SanitizeGitError(msg);

        sanitized.Should().NotContain("some_secret_value");
        sanitized.Should().Contain("GITHUB_COPILOT_PAT=***");
    }

    [Fact]
    public void SanitizeGitError_AuthError_DoesNotMentionOldTokenName()
    {
        var downloader = new GitHubPackageDownloader();
        var msg = "Authentication failed. For private repositories, set GITHUB_APM_PAT or GITHUB_TOKEN environment variable";
        var sanitized = downloader.SanitizeGitError(msg);

        sanitized.Should().Contain("GITHUB_APM_PAT");
        sanitized.Should().Contain("GITHUB_TOKEN");
        sanitized.Should().NotContain("GITHUB_CLI_PAT");
    }

    [Fact]
    public void SanitizeGitError_NoSensitiveData_ReturnsOriginal()
    {
        var downloader = new GitHubPackageDownloader();
        var msg = "fatal: Could not resolve host: github.com";
        var sanitized = downloader.SanitizeGitError(msg);

        sanitized.Should().Be(msg);
    }

    [Fact]
    public void SanitizeGitError_MultipleSensitiveItems_SanitizesAll()
    {
        var downloader = new GitHubPackageDownloader();
        var msg = "GITHUB_TOKEN=secret1 tried https://ghp_abc123@github.com/user/repo";
        var sanitized = downloader.SanitizeGitError(msg);

        sanitized.Should().NotContain("secret1");
        sanitized.Should().NotContain("ghp_abc123");
        sanitized.Should().Contain("GITHUB_TOKEN=***");
        sanitized.Should().Contain("https://***@github.com");
    }
}

/// <summary>
/// Enterprise host URL construction tests (mirrors Python TestEnterpriseHostHandling).
/// </summary>
public class GitHubDownloaderEnterpriseHostUrlTests
{
    [Fact]
    public void EnterpriseHost_SshAndHttpsBothUseCustomHost()
    {
        var sshUrl = GitHubHost.BuildSshUrl("custom.ghe.com", "owner/repo");
        var httpsUrl = GitHubHost.BuildHttpsCloneUrl("custom.ghe.com", "owner/repo");

        sshUrl.Should().Contain("custom.ghe.com");
        httpsUrl.Should().Contain("custom.ghe.com");
        sshUrl.Should().Be("git@custom.ghe.com:owner/repo.git");
        httpsUrl.Should().Be("https://custom.ghe.com/owner/repo");
    }

    [Fact]
    public void EnterpriseHost_HttpsWithTokenUsesCustomHost()
    {
        var url = GitHubHost.BuildHttpsCloneUrl("custom.ghe.com", "owner/repo", "private-repo-token");
        url.Should().Contain("custom.ghe.com");
        url.Should().Contain("private-repo-token");
        url.Should().Be("https://x-access-token:private-repo-token@custom.ghe.com/owner/repo.git");
    }

    [Fact]
    public void GheWithoutToken_ProducesCleanUrl()
    {
        var url = GitHubHost.BuildHttpsCloneUrl("company.ghe.com", "owner/repo");
        url.Should().Be("https://company.ghe.com/owner/repo");
        url.Should().NotContain("@");
    }

    [Fact]
    public void AdoWithoutToken_ProducesCleanUrl()
    {
        var url = GitHubHost.BuildAdoHttpsCloneUrl("myorg", "myproject", "myrepo");
        url.Should().Be("https://dev.azure.com/myorg/myproject/_git/myrepo");
        url.Should().NotContain("@");
    }
}

/// <summary>
/// Mixed source host detection and token isolation tests
/// (mirrors Python TestMixedSourceTokenSelection and TestMultipleHostsResolution).
/// </summary>
public class GitHubDownloaderMixedSourceDetectionTests
{
    [Fact]
    public void Parse_GitHubCom_IdentifiedCorrectly()
    {
        var dep = DependencyReference.Parse("github.com/owner/repo");
        dep.Host.Should().Be("github.com");
        dep.RepoUrl.Should().Be("owner/repo");
        dep.IsAzureDevOps().Should().Be(false);
    }

    [Fact]
    public void Parse_GheHost_IdentifiedCorrectly()
    {
        var dep = DependencyReference.Parse("partner.ghe.com/external/tool");
        dep.Host.Should().Be("partner.ghe.com");
        dep.RepoUrl.Should().Be("external/tool");
        dep.IsAzureDevOps().Should().Be(false);
    }

    [Fact]
    public void Parse_AdoHost_IdentifiedCorrectly()
    {
        var dep = DependencyReference.Parse("dev.azure.com/myorg/myproject/_git/myrepo");
        dep.Host.Should().Be("dev.azure.com");
        dep.IsAzureDevOps().Should().Be(true);
        dep.AdoOrganization.Should().Be("myorg");
        dep.AdoProject.Should().Be("myproject");
        dep.AdoRepo.Should().Be("myrepo");
    }

    [Fact]
    public void Parse_BareOwnerRepo_NotAzureDevOps()
    {
        var dep = DependencyReference.Parse("owner/repo");
        dep.RepoUrl.Should().Be("owner/repo");
        dep.IsAzureDevOps().Should().Be(false);
    }

    [Fact]
    public void Parse_TokenIsolation_HostsCorrectlyDifferentiated()
    {
        var githubDep = DependencyReference.Parse("github.com/owner/repo");
        var gheDep = DependencyReference.Parse("company.ghe.com/owner/repo");
        var adoDep = DependencyReference.Parse("dev.azure.com/org/proj/_git/repo");

        githubDep.Host.Should().Be("github.com");
        gheDep.Host.Should().Be("company.ghe.com");
        adoDep.Host.Should().Be("dev.azure.com");

        githubDep.IsAzureDevOps().Should().Be(false);
        gheDep.IsAzureDevOps().Should().Be(false);
        adoDep.IsAzureDevOps().Should().Be(true);
    }

    [Fact]
    public void GitHubUrl_NeverContainsAdoToken()
    {
        // Verifies URL construction isolates tokens: GitHub URLs use x-access-token format
        var url = GitHubHost.BuildHttpsCloneUrl("github.com", "owner/repo", "github-token");
        url.Should().Contain("github-token");
        url.Should().NotContain("ado-token");
        url.Should().Contain("x-access-token");
    }

    [Fact]
    public void AdoUrl_NeverContainsGitHubToken()
    {
        // Verifies URL construction isolates tokens: ADO URLs use token@host format
        var url = GitHubHost.BuildAdoHttpsCloneUrl("myorg", "myproject", "myrepo", "ado-token");
        url.Should().Contain("ado-token");
        url.Should().NotContain("github-token");
        url.Should().NotContain("x-access-token");
    }

    [Fact]
    public void GheUrl_WithGitHubToken_UsesAccessTokenFormat()
    {
        // Mirrors Python test_mixed_tokens_ghe: GHE URLs use x-access-token, never ADO format
        var url = GitHubHost.BuildHttpsCloneUrl("company.ghe.com", "owner/repo", "github-token");
        url.Should().Contain("company.ghe.com");
        url.Should().Contain("github-token");
        url.Should().Contain("x-access-token");
    }

    [Fact]
    public void GheUrl_WithoutToken_ProducesCleanUrl()
    {
        // Mirrors Python test_ghe_without_github_token_falls_back
        var url = GitHubHost.BuildHttpsCloneUrl("company.ghe.com", "owner/repo");
        url.Should().Be("https://company.ghe.com/owner/repo");
        url.Should().NotContain("@");
    }

    [Fact]
    public void AdoUrl_WithoutToken_ProducesCleanUrl()
    {
        // Mirrors Python test_github_ado_without_ado_token_falls_back
        var url = GitHubHost.BuildAdoHttpsCloneUrl("myorg", "myproject", "myrepo");
        url.Should().Be("https://dev.azure.com/myorg/myproject/_git/myrepo");
        url.Should().NotContain("@");
    }

    [Fact]
    public void Parse_BareOwnerRepo_DefaultsToGitHubHost()
    {
        // Mirrors Python test_mixed_tokens_bare_owner_repo_with_github_host
        var dep = DependencyReference.Parse("owner/repo");
        dep.RepoUrl.Should().Be("owner/repo");
        dep.IsAzureDevOps().Should().BeFalse();
        dep.Host.Should().Be(GitHubHost.DefaultHost());
    }
}

/// <summary>
/// Constructor integration tests for GitHubPackageDownloader.
/// Tests HasGitHubToken/HasAdoToken properties based on environment variables.
/// (Mirrors Python test_setup_git_environment_* and test_public_repo_access_without_token)
/// </summary>
[Collection("EnvironmentVariableTests")]
public class GitHubDownloaderConstructorTests : IDisposable
{
    private readonly string? _origGithubApmPat;
    private readonly string? _origGithubToken;
    private readonly string? _origAdoApmPat;
    private readonly string? _origGhToken;
    private readonly string? _origGithubCopilotPat;

    public GitHubDownloaderConstructorTests()
    {
        _origGithubApmPat = Environment.GetEnvironmentVariable("GITHUB_APM_PAT");
        _origGithubToken = Environment.GetEnvironmentVariable("GITHUB_TOKEN");
        _origAdoApmPat = Environment.GetEnvironmentVariable("ADO_APM_PAT");
        _origGhToken = Environment.GetEnvironmentVariable("GH_TOKEN");
        _origGithubCopilotPat = Environment.GetEnvironmentVariable("GITHUB_COPILOT_PAT");

        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", null);
        Environment.SetEnvironmentVariable("GITHUB_TOKEN", null);
        Environment.SetEnvironmentVariable("ADO_APM_PAT", null);
        Environment.SetEnvironmentVariable("GH_TOKEN", null);
        Environment.SetEnvironmentVariable("GITHUB_COPILOT_PAT", null);
    }

    public void Dispose()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", _origGithubApmPat);
        Environment.SetEnvironmentVariable("GITHUB_TOKEN", _origGithubToken);
        Environment.SetEnvironmentVariable("ADO_APM_PAT", _origAdoApmPat);
        Environment.SetEnvironmentVariable("GH_TOKEN", _origGhToken);
        Environment.SetEnvironmentVariable("GITHUB_COPILOT_PAT", _origGithubCopilotPat);
    }

    [Fact]
    public void WithGitHubApmPat_HasGitHubTokenTrue()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", "test-apm-token");
        var downloader = new GitHubPackageDownloader();
        downloader.HasGitHubToken.Should().BeTrue();
    }

    [Fact]
    public void WithGitHubTokenFallback_HasGitHubTokenTrue()
    {
        Environment.SetEnvironmentVariable("GITHUB_TOKEN", "test-fallback-token");
        var downloader = new GitHubPackageDownloader();
        downloader.HasGitHubToken.Should().BeTrue();
    }

    [Fact]
    public void NoTokens_HasGitHubTokenFalse()
    {
        var downloader = new GitHubPackageDownloader();
        downloader.HasGitHubToken.Should().BeFalse();
    }

    [Fact]
    public void WithAdoApmPat_HasAdoTokenTrue()
    {
        Environment.SetEnvironmentVariable("ADO_APM_PAT", "test-ado-token");
        var downloader = new GitHubPackageDownloader();
        downloader.HasAdoToken.Should().BeTrue();
    }

    [Fact]
    public void OnlyGitHubPat_HasAdoTokenFalse()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", "github-only-token");
        var downloader = new GitHubPackageDownloader();
        downloader.HasAdoToken.Should().BeFalse();
    }

    [Fact]
    public void NoTokens_HasAdoTokenFalse()
    {
        var downloader = new GitHubPackageDownloader();
        downloader.HasAdoToken.Should().BeFalse();
    }

    [Fact]
    public void BothTokenTypes_BothAvailable()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", "github-token");
        Environment.SetEnvironmentVariable("ADO_APM_PAT", "ado-token");
        var downloader = new GitHubPackageDownloader();
        downloader.HasGitHubToken.Should().BeTrue();
        downloader.HasAdoToken.Should().BeTrue();
    }
}

/// <summary>
/// Error handling tests (mirrors Python TestErrorHandling and invalid reference tests).
/// </summary>
public class GitHubDownloaderErrorHandlingTests
{
    [Fact]
    public void Parse_InvalidSingleSegment_ThrowsArgumentException()
    {
        Assert.Throws<ArgumentException>(() => DependencyReference.Parse("invalid-repo-format"));
    }

    [Fact]
    public void Parse_EmptyString_ThrowsArgumentException()
    {
        Assert.Throws<ArgumentException>(() => DependencyReference.Parse(""));
    }

    [Fact]
    public void Parse_WhitespaceOnly_ThrowsArgumentException()
    {
        Assert.Throws<ArgumentException>(() => DependencyReference.Parse("   "));
    }

    [Fact]
    public void Parse_UnsupportedHost_ThrowsArgumentException()
    {
        Assert.Throws<ArgumentException>(() => DependencyReference.Parse("random.unsupported.com/owner/repo"));
    }

    [Fact]
    public void DownloadPackage_InvalidRepoRef_ThrowsArgumentException()
    {
        var downloader = new GitHubPackageDownloader();
        var tempPath = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());

        try
        {
            Assert.Throws<ArgumentException>(() => downloader.DownloadPackage("invalid-repo-format", tempPath));
        }
        finally
        {
            if (Directory.Exists(tempPath))
                Directory.Delete(tempPath, true);
        }
    }

    [Fact]
    public void Parse_ProtocolRelativeUrl_ThrowsArgumentException()
    {
        Assert.Throws<ArgumentException>(() => DependencyReference.Parse("//evil.com/owner/repo"));
    }

    [Fact]
    public void Parse_ControlCharacters_ThrowsArgumentException()
    {
        Assert.Throws<ArgumentException>(() => DependencyReference.Parse("owner/repo\0malicious"));
    }
}

/// <summary>
/// Git reference type detection tests (mirrors Python test_resolve_git_reference_* tests).
/// </summary>
public class GitHubDownloaderGitReferenceTests
{
    [Theory]
    [InlineData("main", GitReferenceType.Branch)]
    [InlineData("develop", GitReferenceType.Branch)]
    [InlineData("feature-branch", GitReferenceType.Branch)]
    public void ParseGitReference_DetectsBranches(string refStr, GitReferenceType expected)
    {
        var (type, _) = DependencyReference.ParseGitReference(refStr);
        type.Should().Be(expected);
    }

    [Theory]
    [InlineData("abcdef1")]
    [InlineData("abc123def456789012345678901234567890abcd")]
    public void ParseGitReference_DetectsCommits(string refStr)
    {
        var (type, _) = DependencyReference.ParseGitReference(refStr);
        type.Should().Be(GitReferenceType.Commit);
    }

    [Theory]
    [InlineData("v1.0.0")]
    [InlineData("1.2.3")]
    [InlineData("v0.1.0-beta")]
    public void ParseGitReference_DetectsTags(string refStr)
    {
        var (type, _) = DependencyReference.ParseGitReference(refStr);
        type.Should().Be(GitReferenceType.Tag);
    }

    [Fact]
    public void ParseGitReference_NullDefaultsToMainBranch()
    {
        var (type, refName) = DependencyReference.ParseGitReference(null);
        type.Should().Be(GitReferenceType.Branch);
        refName.Should().Be("main");
    }

    [Fact]
    public void ParseGitReference_EmptyStringDefaultsToMainBranch()
    {
        var (type, refName) = DependencyReference.ParseGitReference("");
        type.Should().Be(GitReferenceType.Branch);
        refName.Should().Be("main");
    }

    [Fact]
    public void Parse_WithHashReference_ExtractsRef()
    {
        var dep = DependencyReference.Parse("owner/repo#main");
        dep.RepoUrl.Should().Be("owner/repo");
        dep.Reference.Should().Be("main");
    }

    [Fact]
    public void Parse_WithCommitReference_ExtractsRef()
    {
        var dep = DependencyReference.Parse("owner/repo#abcdef1");
        dep.RepoUrl.Should().Be("owner/repo");
        dep.Reference.Should().Be("abcdef1");
    }

    [Fact]
    public void Parse_WithTagReference_ExtractsRef()
    {
        var dep = DependencyReference.Parse("owner/repo#v1.0.0");
        dep.RepoUrl.Should().Be("owner/repo");
        dep.Reference.Should().Be("v1.0.0");
    }

    [Fact]
    public void Parse_WithHostAndRef_ExtractsAll()
    {
        var dep = DependencyReference.Parse("github.com/owner/repo#develop");
        dep.Host.Should().Be("github.com");
        dep.RepoUrl.Should().Be("owner/repo");
        dep.Reference.Should().Be("develop");
    }
}

/// <summary>
/// Tests for BuildRepoUrl integration with token state
/// (mirrors Python test_public_repo_access_without_token, test_private_repo_url_building_with_token, test_ssh_url_building).
/// </summary>
[Collection("EnvironmentVariableTests")]
public class GitHubDownloaderBuildRepoUrlTests : IDisposable
{
    private readonly string? _origGithubApmPat;
    private readonly string? _origGithubToken;
    private readonly string? _origAdoApmPat;
    private readonly string? _origGhToken;
    private readonly string? _origGithubHost;

    public GitHubDownloaderBuildRepoUrlTests()
    {
        _origGithubApmPat = Environment.GetEnvironmentVariable("GITHUB_APM_PAT");
        _origGithubToken = Environment.GetEnvironmentVariable("GITHUB_TOKEN");
        _origAdoApmPat = Environment.GetEnvironmentVariable("ADO_APM_PAT");
        _origGhToken = Environment.GetEnvironmentVariable("GH_TOKEN");
        _origGithubHost = Environment.GetEnvironmentVariable("GITHUB_HOST");

        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", null);
        Environment.SetEnvironmentVariable("GITHUB_TOKEN", null);
        Environment.SetEnvironmentVariable("ADO_APM_PAT", null);
        Environment.SetEnvironmentVariable("GH_TOKEN", null);
        Environment.SetEnvironmentVariable("GITHUB_HOST", null);
    }

    public void Dispose()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", _origGithubApmPat);
        Environment.SetEnvironmentVariable("GITHUB_TOKEN", _origGithubToken);
        Environment.SetEnvironmentVariable("ADO_APM_PAT", _origAdoApmPat);
        Environment.SetEnvironmentVariable("GH_TOKEN", _origGhToken);
        Environment.SetEnvironmentVariable("GITHUB_HOST", _origGithubHost);
    }

    [Fact]
    public void PublicRepo_NoToken_ReturnsCleanUrl()
    {
        var downloader = new GitHubPackageDownloader();
        downloader.HasGitHubToken.Should().BeFalse();

        var url = downloader.BuildRepoUrl("octocat/Hello-World", useSsh: false);
        url.Should().Be("https://github.com/octocat/Hello-World");
        url.Should().NotContain("@");
    }

    [Fact]
    public void PrivateRepo_WithToken_ReturnsAuthenticatedUrl()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", "private-repo-token");
        var downloader = new GitHubPackageDownloader();
        downloader.HasGitHubToken.Should().BeTrue();

        var url = downloader.BuildRepoUrl("private-org/private-repo", useSsh: false);
        url.Should().Contain("private-repo-token");
        url.Should().Contain("x-access-token");
        url.Should().Contain("github.com");
    }

    [Fact]
    public void SshUrl_IgnoresToken()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", "some-token");
        var downloader = new GitHubPackageDownloader();

        var url = downloader.BuildRepoUrl("user/repo", useSsh: true);
        url.Should().Be("git@github.com:user/repo.git");
        url.Should().NotContain("some-token");
    }

    [Fact]
    public void AdoRepo_WithAdoToken_UsesAdoTokenFormat()
    {
        Environment.SetEnvironmentVariable("ADO_APM_PAT", "ado-token");
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", "github-token");
        var downloader = new GitHubPackageDownloader();

        var depRef = DependencyReference.Parse("dev.azure.com/myorg/myproject/_git/myrepo");
        var url = downloader.BuildRepoUrl(depRef.RepoUrl, useSsh: false, depRef: depRef);

        url.Should().Contain("ado-token");
        url.Should().NotContain("github-token");
        url.Should().Contain("dev.azure.com");
    }

    [Fact]
    public void GitHubRepo_NotAffectedByAdoToken()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", "github-token");
        Environment.SetEnvironmentVariable("ADO_APM_PAT", "ado-token");
        var downloader = new GitHubPackageDownloader();

        var depRef = DependencyReference.Parse("owner/repo");
        var url = downloader.BuildRepoUrl(depRef.RepoUrl, useSsh: false, depRef: depRef);

        url.Should().Contain("github-token");
        url.Should().NotContain("ado-token");
    }

    [Fact]
    public void EnterpriseHost_SshAndHttps_BothUseCustomHost()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", "ghe-token");
        var downloader = new GitHubPackageDownloader();

        var depRef = DependencyReference.Parse("company.ghe.com/owner/repo");
        var sshUrl = downloader.BuildRepoUrl(depRef.RepoUrl, useSsh: true, depRef: depRef);
        var httpsUrl = downloader.BuildRepoUrl(depRef.RepoUrl, useSsh: false, depRef: depRef);

        sshUrl.Should().Contain("company.ghe.com");
        httpsUrl.Should().Contain("company.ghe.com");
        sshUrl.Should().NotContain("github.com");
        httpsUrl.Should().NotContain("github.com");
    }
}

/// <summary>
/// Helper subclass that overrides CloneRepository to avoid real git operations.
/// Mirrors Python's @patch('apm_cli.deps.github_downloader.Repo') pattern.
/// </summary>
internal class TestableGitHubPackageDownloader : GitHubPackageDownloader
{
    public List<(string Url, string TargetPath, string? Branch)> CloneCalls { get; } = [];
    public Queue<Func<string, string, string?, string>> CloneBehaviors { get; } = new();

    internal override string CloneRepository(string url, string targetPath, string? branch = null)
    {
        CloneCalls.Add((url, targetPath, branch));

        if (CloneBehaviors.Count > 0)
            return CloneBehaviors.Dequeue()(url, targetPath, branch);

        return targetPath;
    }
}

/// <summary>
/// Clone fallback tests (mirrors Python test_clone_fallback_respects_enterprise_host,
/// test_clone_with_fallback_selects_ado_token, test_clone_with_fallback_selects_github_token).
/// </summary>
[Collection("EnvironmentVariableTests")]
public class GitHubDownloaderCloneFallbackTests : IDisposable
{
    private readonly string? _origGithubApmPat;
    private readonly string? _origGithubToken;
    private readonly string? _origAdoApmPat;
    private readonly string? _origGhToken;
    private readonly string? _origGithubHost;
    private readonly string _tempDir;

    public GitHubDownloaderCloneFallbackTests()
    {
        _origGithubApmPat = Environment.GetEnvironmentVariable("GITHUB_APM_PAT");
        _origGithubToken = Environment.GetEnvironmentVariable("GITHUB_TOKEN");
        _origAdoApmPat = Environment.GetEnvironmentVariable("ADO_APM_PAT");
        _origGhToken = Environment.GetEnvironmentVariable("GH_TOKEN");
        _origGithubHost = Environment.GetEnvironmentVariable("GITHUB_HOST");

        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", null);
        Environment.SetEnvironmentVariable("GITHUB_TOKEN", null);
        Environment.SetEnvironmentVariable("ADO_APM_PAT", null);
        Environment.SetEnvironmentVariable("GH_TOKEN", null);
        Environment.SetEnvironmentVariable("GITHUB_HOST", null);

        _tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", _origGithubApmPat);
        Environment.SetEnvironmentVariable("GITHUB_TOKEN", _origGithubToken);
        Environment.SetEnvironmentVariable("ADO_APM_PAT", _origAdoApmPat);
        Environment.SetEnvironmentVariable("GH_TOKEN", _origGhToken);
        Environment.SetEnvironmentVariable("GITHUB_HOST", _origGithubHost);
        try { if (Directory.Exists(_tempDir)) Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void CloneFallback_WithGitHubToken_FirstAttemptUsesAuthHttps()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", "github-token");
        var downloader = new TestableGitHubPackageDownloader();

        downloader.CloneWithFallback("owner/repo", _tempDir, branch: "main");

        downloader.CloneCalls.Should().HaveCountGreaterThanOrEqualTo(1);
        var firstCallUrl = downloader.CloneCalls[0].Url;
        firstCallUrl.Should().Contain("github-token");
        firstCallUrl.Should().Contain("x-access-token");
    }

    [Fact]
    public void CloneFallback_WithAdoToken_UsesAdoTokenForAdoDep()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", "github-token");
        Environment.SetEnvironmentVariable("ADO_APM_PAT", "ado-token");
        var downloader = new TestableGitHubPackageDownloader();

        var depRef = DependencyReference.Parse("dev.azure.com/myorg/myproject/_git/myrepo");
        downloader.CloneWithFallback(depRef.RepoUrl, _tempDir, depRef: depRef, branch: "main");

        downloader.CloneCalls.Should().HaveCountGreaterThanOrEqualTo(1);
        var firstCallUrl = downloader.CloneCalls[0].Url;
        firstCallUrl.Should().Contain("ado-token");
        firstCallUrl.Should().Contain("dev.azure.com");
        firstCallUrl.Should().NotContain("github-token");
    }

    [Fact]
    public void CloneFallback_EnterpriseHost_AllAttemptsUseCustomHost()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", "ghe-token");
        var downloader = new TestableGitHubPackageDownloader();

        // Make first two attempts fail, third succeeds
        var callCount = 0;
        downloader.CloneBehaviors.Enqueue((_, _, _) =>
        {
            callCount++;
            throw new LibGit2SharpException("auth failed");
        });
        downloader.CloneBehaviors.Enqueue((_, _, _) =>
        {
            callCount++;
            throw new LibGit2SharpException("ssh failed");
        });
        downloader.CloneBehaviors.Enqueue((_, tp, _) =>
        {
            callCount++;
            return tp;
        });

        var depRef = DependencyReference.Parse("company.ghe.com/team/internal-repo");
        downloader.CloneWithFallback(depRef.RepoUrl, _tempDir, depRef: depRef, branch: "main");

        downloader.CloneCalls.Should().HaveCount(3);
        // All three attempts should use company.ghe.com, NOT github.com
        foreach (var call in downloader.CloneCalls)
        {
            call.Url.Should().Contain("company.ghe.com");
            call.Url.Should().Contain("team/internal-repo");
        }
    }

    [Fact]
    public void CloneFallback_NoToken_SkipsAuthAttempt_TriesSshThenHttps()
    {
        var downloader = new TestableGitHubPackageDownloader();
        downloader.HasGitHubToken.Should().BeFalse();

        downloader.CloneWithFallback("owner/repo", _tempDir, branch: "main");

        // Without token: skip Method 1, try Method 2 (SSH), Method 3 (HTTPS)
        downloader.CloneCalls.Should().HaveCountGreaterThanOrEqualTo(1);
        // First call should be SSH (no auth HTTPS is skipped when no token)
        var firstUrl = downloader.CloneCalls[0].Url;
        firstUrl.Should().Contain("git@");
    }

    [Fact]
    public void CloneFallback_AllMethodsFail_NoToken_MentionsEnvVars()
    {
        var downloader = new TestableGitHubPackageDownloader();
        // Make all clone attempts fail
        for (int i = 0; i < 3; i++)
            downloader.CloneBehaviors.Enqueue((_, _, _) => throw new LibGit2SharpException("clone failed"));

        var ex = Assert.Throws<InvalidOperationException>(() =>
            downloader.CloneWithFallback("owner/repo", _tempDir, branch: "main"));

        ex.Message.Should().Contain("GITHUB_APM_PAT");
        ex.Message.Should().Contain("GITHUB_TOKEN");
    }

    [Fact]
    public void CloneFallback_AllMethodsFail_Ado_NoToken_MentionsAdoPat()
    {
        var downloader = new TestableGitHubPackageDownloader();
        for (int i = 0; i < 3; i++)
            downloader.CloneBehaviors.Enqueue((_, _, _) => throw new LibGit2SharpException("clone failed"));

        var depRef = DependencyReference.Parse("dev.azure.com/myorg/myproject/_git/myrepo");
        var ex = Assert.Throws<InvalidOperationException>(() =>
            downloader.CloneWithFallback(depRef.RepoUrl, _tempDir, depRef: depRef, branch: "main"));

        ex.Message.Should().Contain("ADO_APM_PAT");
    }

    [Fact]
    public void CloneFallback_AllMethodsFail_WithToken_MentionsPermissions()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", "test-token");
        var downloader = new TestableGitHubPackageDownloader();
        for (int i = 0; i < 4; i++)
            downloader.CloneBehaviors.Enqueue((_, _, _) => throw new LibGit2SharpException("auth failed"));

        var ex = Assert.Throws<InvalidOperationException>(() =>
            downloader.CloneWithFallback("owner/repo", _tempDir, branch: "main"));

        ex.Message.Should().Contain("repository access permissions");
    }
}

/// <summary>
/// DownloadPackage integration tests with mocked clone
/// (mirrors Python test_download_package_success, test_download_package_validation_failure,
/// test_download_package_git_failure).
/// </summary>
[Collection("EnvironmentVariableTests")]
public class GitHubDownloaderDownloadPackageTests : IDisposable
{
    private readonly string? _origGithubApmPat;
    private readonly string? _origGithubToken;
    private readonly string? _origAdoApmPat;
    private readonly string? _origGhToken;
    private readonly string _tempDir;

    public GitHubDownloaderDownloadPackageTests()
    {
        _origGithubApmPat = Environment.GetEnvironmentVariable("GITHUB_APM_PAT");
        _origGithubToken = Environment.GetEnvironmentVariable("GITHUB_TOKEN");
        _origAdoApmPat = Environment.GetEnvironmentVariable("ADO_APM_PAT");
        _origGhToken = Environment.GetEnvironmentVariable("GH_TOKEN");

        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", null);
        Environment.SetEnvironmentVariable("GITHUB_TOKEN", null);
        Environment.SetEnvironmentVariable("ADO_APM_PAT", null);
        Environment.SetEnvironmentVariable("GH_TOKEN", null);

        _tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", _origGithubApmPat);
        Environment.SetEnvironmentVariable("GITHUB_TOKEN", _origGithubToken);
        Environment.SetEnvironmentVariable("ADO_APM_PAT", _origAdoApmPat);
        Environment.SetEnvironmentVariable("GH_TOKEN", _origGhToken);
        try { if (Directory.Exists(_tempDir)) Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void DownloadPackage_Success_ReturnsPackageInfo()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", "test-token");
        var downloader = new TestableGitHubPackageDownloader();
        var targetPath = Path.Combine(_tempDir, "test_package");

        // Simulate successful clone by creating apm.yml in the target directory
        downloader.CloneBehaviors.Enqueue((_, tp, _) =>
        {
            Directory.CreateDirectory(tp);
            File.WriteAllText(Path.Combine(tp, "apm.yml"),
                "name: test-package\nversion: 1.0.0\ndescription: A test package\n");
            return tp;
        });

        var result = downloader.DownloadPackage("user/repo#main", targetPath);

        result.Should().NotBeNull();
        result.Package.Name.Should().Be("test-package");
        result.Package.Version.Should().Be("1.0.0");
        result.InstallPath.Should().Be(targetPath);
        result.InstalledAt.Should().NotBeNullOrEmpty();
    }

    [Fact]
    public void DownloadPackage_ValidationFailure_MissingApmYmlAndSkillMd_Throws()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", "test-token");
        var downloader = new TestableGitHubPackageDownloader();
        var targetPath = Path.Combine(_tempDir, "invalid_package");

        // Clone succeeds but directory has no apm.yml or SKILL.md
        downloader.CloneBehaviors.Enqueue((_, tp, _) =>
        {
            Directory.CreateDirectory(tp);
            File.WriteAllText(Path.Combine(tp, "README.md"), "# Not an APM package");
            return tp;
        });

        var ex = Assert.Throws<InvalidOperationException>(() =>
            downloader.DownloadPackage("user/repo#main", targetPath));

        ex.Message.Should().Contain("Invalid APM package");
    }

    [Fact]
    public void DownloadPackage_GitCloneFailure_Throws()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", "test-token");
        var downloader = new TestableGitHubPackageDownloader();
        var targetPath = Path.Combine(_tempDir, "fail_package");

        // All clone attempts fail
        for (int i = 0; i < 4; i++)
            downloader.CloneBehaviors.Enqueue((_, _, _) => throw new LibGit2SharpException("Clone failed"));

        var ex = Assert.Throws<InvalidOperationException>(() =>
            downloader.DownloadPackage("user/repo#main", targetPath));

        ex.Message.Should().Contain("Failed to clone repository");
    }

    [Fact]
    public void DownloadPackage_WithSkillMd_ReturnsPackageInfo()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", "test-token");
        var downloader = new TestableGitHubPackageDownloader();
        var targetPath = Path.Combine(_tempDir, "skill_package");

        // Clone succeeds with SKILL.md (no apm.yml)
        downloader.CloneBehaviors.Enqueue((_, tp, _) =>
        {
            Directory.CreateDirectory(tp);
            File.WriteAllText(Path.Combine(tp, "SKILL.md"), "# My Skill\nA test skill.");
            return tp;
        });

        var result = downloader.DownloadPackage("user/repo#main", targetPath);

        result.Should().NotBeNull();
        result.Package.Name.Should().Be("repo");
        result.Package.Version.Should().Be("1.0.0");
    }

    /// <summary>
    /// Mirrors Python test_download_package_commit_checkout: verifies commit SHA
    /// reference is passed through to the clone operation.
    /// </summary>
    [Fact]
    public void DownloadPackage_WithCommitReference_PassesRefToClone()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", "test-token");
        var downloader = new TestableGitHubPackageDownloader();
        var targetPath = Path.Combine(_tempDir, "commit_package");

        downloader.CloneBehaviors.Enqueue((_, tp, _) =>
        {
            Directory.CreateDirectory(tp);
            File.WriteAllText(Path.Combine(tp, "apm.yml"),
                "name: test-package\nversion: 1.0.0\ndescription: Commit test\n");
            return tp;
        });

        var result = downloader.DownloadPackage("user/repo#abcdef1", targetPath);

        result.Should().NotBeNull();
        result.Package.Name.Should().Be("test-package");
        // Verify the commit ref was passed as branch to CloneWithFallback
        downloader.CloneCalls.Should().HaveCountGreaterThanOrEqualTo(1);
        downloader.CloneCalls[0].Branch.Should().Be("abcdef1");
    }
}

/// <summary>
/// Comprehensive mixed-platform token isolation test
/// (mirrors Python test_mixed_installation_token_isolation).
/// Verifies all three platforms from a single downloader with no cross-contamination.
/// </summary>
[Collection("EnvironmentVariableTests")]
public class GitHubDownloaderMixedInstallationIsolationTests : IDisposable
{
    private readonly string? _origGithubApmPat;
    private readonly string? _origGithubToken;
    private readonly string? _origAdoApmPat;
    private readonly string? _origGhToken;

    public GitHubDownloaderMixedInstallationIsolationTests()
    {
        _origGithubApmPat = Environment.GetEnvironmentVariable("GITHUB_APM_PAT");
        _origGithubToken = Environment.GetEnvironmentVariable("GITHUB_TOKEN");
        _origAdoApmPat = Environment.GetEnvironmentVariable("ADO_APM_PAT");
        _origGhToken = Environment.GetEnvironmentVariable("GH_TOKEN");

        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", null);
        Environment.SetEnvironmentVariable("GITHUB_TOKEN", null);
        Environment.SetEnvironmentVariable("ADO_APM_PAT", null);
        Environment.SetEnvironmentVariable("GH_TOKEN", null);
    }

    public void Dispose()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", _origGithubApmPat);
        Environment.SetEnvironmentVariable("GITHUB_TOKEN", _origGithubToken);
        Environment.SetEnvironmentVariable("ADO_APM_PAT", _origAdoApmPat);
        Environment.SetEnvironmentVariable("GH_TOKEN", _origGhToken);
    }

    [Fact]
    public void MixedInstallation_AllPlatforms_TokensIsolated()
    {
        Environment.SetEnvironmentVariable("GITHUB_APM_PAT", "github-token");
        Environment.SetEnvironmentVariable("ADO_APM_PAT", "ado-token");
        var downloader = new GitHubPackageDownloader();

        var githubDep = DependencyReference.Parse("github.com/owner/repo");
        var gheDep = DependencyReference.Parse("company.ghe.com/owner/repo");
        var adoDep = DependencyReference.Parse("dev.azure.com/org/proj/_git/repo");

        var githubUrl = downloader.BuildRepoUrl(githubDep.RepoUrl, useSsh: false, depRef: githubDep);
        var gheUrl = downloader.BuildRepoUrl(gheDep.RepoUrl, useSsh: false, depRef: gheDep);
        var adoUrl = downloader.BuildRepoUrl(adoDep.RepoUrl, useSsh: false, depRef: adoDep);

        // Verify correct hosts
        githubUrl.Should().Contain("github.com");
        gheUrl.Should().Contain("company.ghe.com");
        adoUrl.Should().Contain("dev.azure.com");

        // ADO token only in ADO URL
        githubUrl.Should().NotContain("ado-token");
        gheUrl.Should().NotContain("ado-token");
        adoUrl.Should().Contain("ado-token");

        // GitHub token not in ADO URL
        adoUrl.Should().NotContain("github-token");
    }
}

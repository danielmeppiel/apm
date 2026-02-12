using Apm.Cli.Utils;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Utils;

public class GitHubHostTests
{
    [Fact]
    public void DefaultHost_ReturnsGitHubCom()
    {
        // When GITHUB_HOST is not set, should return github.com
        var original = Environment.GetEnvironmentVariable("GITHUB_HOST");
        try
        {
            Environment.SetEnvironmentVariable("GITHUB_HOST", null);
            GitHubHost.DefaultHost().Should().Be("github.com");
        }
        finally
        {
            Environment.SetEnvironmentVariable("GITHUB_HOST", original);
        }
    }

    [Fact]
    public void DefaultHost_RespectsEnvVar()
    {
        var original = Environment.GetEnvironmentVariable("GITHUB_HOST");
        try
        {
            Environment.SetEnvironmentVariable("GITHUB_HOST", "custom.ghe.com");
            GitHubHost.DefaultHost().Should().Be("custom.ghe.com");
        }
        finally
        {
            Environment.SetEnvironmentVariable("GITHUB_HOST", original);
        }
    }
}

public class IsAzureDevOpsHostnameTests
{
    [Theory]
    [InlineData("dev.azure.com", true)]
    [InlineData("mycompany.visualstudio.com", true)]
    [InlineData("DEV.AZURE.COM", true)]
    [InlineData("MYCOMPANY.VISUALSTUDIO.COM", true)]
    [InlineData("github.com", false)]
    [InlineData("company.ghe.com", false)]
    [InlineData(null, false)]
    [InlineData("", false)]
    public void IsAzureDevOpsHostname_ReturnsExpected(string? hostname, bool expected)
    {
        GitHubHost.IsAzureDevOpsHostname(hostname).Should().Be(expected);
    }
}

public class IsGitHubHostnameTests
{
    [Theory]
    [InlineData("github.com", true)]
    [InlineData("company.ghe.com", true)]
    [InlineData("dev.azure.com", false)]
    [InlineData(null, false)]
    [InlineData("", false)]
    [InlineData("fakegithub.com", false)]
    public void IsGitHubHostname_ReturnsExpected(string? hostname, bool expected)
    {
        GitHubHost.IsGitHubHostname(hostname).Should().Be(expected);
    }
}

public class IsSupportedGitHostTests
{
    [Theory]
    [InlineData("github.com", true)]
    [InlineData("company.ghe.com", true)]
    [InlineData("dev.azure.com", true)]
    [InlineData("mycompany.visualstudio.com", true)]
    [InlineData(null, false)]
    [InlineData("", false)]
    [InlineData("evil.com", false)]
    public void IsSupportedGitHost_ReturnsExpected(string? hostname, bool expected)
    {
        var original = Environment.GetEnvironmentVariable("GITHUB_HOST");
        try
        {
            Environment.SetEnvironmentVariable("GITHUB_HOST", null);
            GitHubHost.IsSupportedGitHost(hostname).Should().Be(expected);
        }
        finally
        {
            Environment.SetEnvironmentVariable("GITHUB_HOST", original);
        }
    }

    [Fact]
    public void IsSupportedGitHost_CustomHost_IsSupported()
    {
        var original = Environment.GetEnvironmentVariable("GITHUB_HOST");
        try
        {
            Environment.SetEnvironmentVariable("GITHUB_HOST", "custom.enterprise.com");
            GitHubHost.IsSupportedGitHost("custom.enterprise.com").Should().BeTrue();
        }
        finally
        {
            Environment.SetEnvironmentVariable("GITHUB_HOST", original);
        }
    }
}

public class IsValidFqdnTests
{
    [Theory]
    [InlineData("github.com", true)]
    [InlineData("dev.azure.com", true)]
    [InlineData("my.enterprise.server.com", true)]
    [InlineData("a.b", true)]
    [InlineData(null, false)]
    [InlineData("", false)]
    [InlineData("localhost", false)]
    [InlineData("just-a-hostname", false)]
    public void IsValidFqdn_ReturnsExpected(string? hostname, bool expected)
    {
        GitHubHost.IsValidFqdn(hostname).Should().Be(expected);
    }

    [Fact]
    public void IsValidFqdn_WithPathComponent_StripsPath()
    {
        GitHubHost.IsValidFqdn("github.com/user/repo").Should().BeTrue();
    }
}

public class UrlBuildingTests
{
    [Fact]
    public void BuildSshUrl_ReturnsCorrectFormat()
    {
        var url = GitHubHost.BuildSshUrl("github.com", "user/repo");
        url.Should().Be("git@github.com:user/repo.git");
    }

    [Fact]
    public void BuildHttpsCloneUrl_NoToken_ReturnsPublicUrl()
    {
        var url = GitHubHost.BuildHttpsCloneUrl("github.com", "user/repo");
        url.Should().Be("https://github.com/user/repo");
    }

    [Fact]
    public void BuildHttpsCloneUrl_WithToken_ReturnsAuthenticatedUrl()
    {
        var url = GitHubHost.BuildHttpsCloneUrl("github.com", "user/repo", "mytoken");
        url.Should().Be("https://x-access-token:mytoken@github.com/user/repo.git");
    }

    [Fact]
    public void BuildAdoHttpsCloneUrl_NoToken_ReturnsPublicUrl()
    {
        var url = GitHubHost.BuildAdoHttpsCloneUrl("org", "project", "repo");
        url.Should().Be("https://dev.azure.com/org/project/_git/repo");
    }

    [Fact]
    public void BuildAdoHttpsCloneUrl_WithToken_ReturnsAuthenticatedUrl()
    {
        var url = GitHubHost.BuildAdoHttpsCloneUrl("org", "project", "repo", "mytoken");
        url.Should().Be("https://mytoken@dev.azure.com/org/project/_git/repo");
    }

    [Fact]
    public void BuildAdoSshUrl_DefaultHost_ReturnsV3Format()
    {
        var url = GitHubHost.BuildAdoSshUrl("org", "project", "repo");
        url.Should().Be("git@ssh.dev.azure.com:v3/org/project/repo");
    }

    [Fact]
    public void BuildAdoSshUrl_CustomHost_ReturnsSshFormat()
    {
        var url = GitHubHost.BuildAdoSshUrl("org", "project", "repo", "custom.server.com");
        url.Should().Be("ssh://git@custom.server.com/org/project/_git/repo");
    }

    [Fact]
    public void BuildAdoApiUrl_ReturnsCorrectFormat()
    {
        var url = GitHubHost.BuildAdoApiUrl("org", "project", "repo", "src/file.md");
        url.Should().Contain("dev.azure.com/org/project/_apis/git/repositories/repo/items");
        url.Should().Contain("api-version=7.0");
    }
}

public class SanitizeTokenUrlInMessageTests
{
    [Fact]
    public void SanitizeTokenUrlInMessage_SanitizesToken()
    {
        var msg = "fatal: Authentication failed for 'https://ghp_secret@github.com/user/repo.git'";
        var sanitized = GitHubHost.SanitizeTokenUrlInMessage(msg);
        sanitized.Should().NotContain("ghp_secret");
        sanitized.Should().Contain("https://***@github.com");
    }

    [Fact]
    public void SanitizeTokenUrlInMessage_NoToken_ReturnsOriginal()
    {
        var msg = "fatal: Could not resolve host: github.com";
        var sanitized = GitHubHost.SanitizeTokenUrlInMessage(msg);
        sanitized.Should().Be(msg);
    }

    [Fact]
    public void SanitizeTokenUrlInMessage_CustomHost_SanitizesCorrectly()
    {
        var msg = "https://token123@custom.ghe.com/user/repo";
        var sanitized = GitHubHost.SanitizeTokenUrlInMessage(msg, "custom.ghe.com");
        sanitized.Should().NotContain("token123");
        sanitized.Should().Contain("https://***@custom.ghe.com");
    }
}

public class UnsupportedHostErrorTests
{
    [Fact]
    public void UnsupportedHostError_ContainsHostname()
    {
        var msg = GitHubHost.UnsupportedHostError("evil.com");
        msg.Should().Contain("evil.com");
        msg.Should().Contain("Unsupported Git host");
    }

    [Fact]
    public void UnsupportedHostError_WithContext_IncludesContext()
    {
        var msg = GitHubHost.UnsupportedHostError("evil.com", "Test context");
        msg.Should().Contain("Test context");
        msg.Should().Contain("evil.com");
    }

    [Fact]
    public void UnsupportedHostError_IncludesGuidance()
    {
        var msg = GitHubHost.UnsupportedHostError("evil.com");
        msg.Should().Contain("GITHUB_HOST");
        msg.Should().Contain("github.com");
    }
}

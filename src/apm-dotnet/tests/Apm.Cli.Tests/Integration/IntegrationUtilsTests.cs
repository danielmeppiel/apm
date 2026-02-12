using Apm.Cli.Integration;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Integration;

public class IntegrationUtilsTests
{
    #region NormalizeRepoUrl

    [Theory]
    [InlineData("owner/repo", "owner/repo")]
    [InlineData("owner/repo.git", "owner/repo")]
    [InlineData("owner/repo/", "owner/repo")]
    [InlineData("owner/repo.git/", "owner/repo.git")]
    public void NormalizeRepoUrl_ShortForm_NormalizesCorrectly(string input, string expected)
    {
        IntegrationUtils.NormalizeRepoUrl(input).Should().Be(expected);
    }

    [Theory]
    [InlineData("https://github.com/owner/repo", "owner/repo")]
    [InlineData("https://github.com/owner/repo.git", "owner/repo")]
    [InlineData("https://github.com/owner/repo/", "owner/repo")]
    [InlineData("https://github.com/owner/repo.git/", "owner/repo")]
    public void NormalizeRepoUrl_FullUrl_ExtractsOwnerRepo(string input, string expected)
    {
        IntegrationUtils.NormalizeRepoUrl(input).Should().Be(expected);
    }

    [Fact]
    public void NormalizeRepoUrl_HttpUrl_ExtractsPath()
    {
        IntegrationUtils.NormalizeRepoUrl("http://gitlab.com/org/project")
            .Should().Be("org/project");
    }

    [Fact]
    public void NormalizeRepoUrl_DeepPath_PreservesFullPath()
    {
        IntegrationUtils.NormalizeRepoUrl("https://github.com/owner/repo/tree/main")
            .Should().Be("owner/repo/tree/main");
    }

    [Fact]
    public void NormalizeRepoUrl_SimpleShortForm_ReturnsAsIs()
    {
        IntegrationUtils.NormalizeRepoUrl("owner/repo").Should().Be("owner/repo");
    }

    [Fact]
    public void NormalizeRepoUrl_AlreadyClean_NoChange()
    {
        IntegrationUtils.NormalizeRepoUrl("my-org/my-repo").Should().Be("my-org/my-repo");
    }

    [Theory]
    [InlineData("https://github.enterprise.com/owner/repo", "owner/repo")]
    [InlineData("https://github.enterprise.com/owner/repo.git", "owner/repo")]
    public void NormalizeRepoUrl_EnterpriseUrl_ExtractsOwnerRepo(string input, string expected)
    {
        IntegrationUtils.NormalizeRepoUrl(input).Should().Be(expected);
    }

    [Fact]
    public void NormalizeRepoUrl_ComplexEnterpriseUrl_ExtractsFullPath()
    {
        IntegrationUtils.NormalizeRepoUrl("https://git.enterprise.internal/organization/team/project")
            .Should().Be("organization/team/project");
    }

    [Fact]
    public void NormalizeRepoUrl_UrlWithoutPath_ReturnsAsIs()
    {
        IntegrationUtils.NormalizeRepoUrl("https://github.com")
            .Should().Be("https://github.com");
    }

    [Fact]
    public void NormalizeRepoUrl_EmptyString_ReturnsEmpty()
    {
        IntegrationUtils.NormalizeRepoUrl("").Should().Be("");
    }

    [Fact]
    public void NormalizeRepoUrl_RepoNameContainsGit_OnlyRemovesTrailingGitSuffix()
    {
        IntegrationUtils.NormalizeRepoUrl("owner/mygit-repo.git").Should().Be("owner/mygit-repo");
    }

    [Fact]
    public void NormalizeRepoUrl_PreservesCase()
    {
        IntegrationUtils.NormalizeRepoUrl("https://github.com/Owner/Repo").Should().Be("Owner/Repo");
    }

    [Fact]
    public void NormalizeRepoUrl_SshUrl_RemovesGitSuffix()
    {
        // SSH URLs without :// are treated as short form
        IntegrationUtils.NormalizeRepoUrl("git@github.com:owner/repo.git")
            .Should().Be("git@github.com:owner/repo");
    }

    [Fact]
    public void NormalizeRepoUrl_GitLabNestedPath_PreservesFullPath()
    {
        IntegrationUtils.NormalizeRepoUrl("https://gitlab.com/group/subgroup/repo")
            .Should().Be("group/subgroup/repo");
    }

    #endregion
}

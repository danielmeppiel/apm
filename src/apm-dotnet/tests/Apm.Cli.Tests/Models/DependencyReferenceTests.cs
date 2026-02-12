using Apm.Cli.Models;
using Apm.Cli.Utils;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Models;

public class DependencyReferenceParseTests
{
    [Fact]
    public void Parse_SimpleRepo_ParsesCorrectly()
    {
        var dep = DependencyReference.Parse("user/repo");
        dep.RepoUrl.Should().Be("user/repo");
        dep.Reference.Should().BeNull();
        dep.Alias.Should().BeNull();
        dep.IsVirtual.Should().BeFalse();
    }

    [Fact]
    public void Parse_WithBranch_ParsesReference()
    {
        var dep = DependencyReference.Parse("user/repo#main");
        dep.RepoUrl.Should().Be("user/repo");
        dep.Reference.Should().Be("main");
        dep.Alias.Should().BeNull();
    }

    [Fact]
    public void Parse_WithTag_ParsesReference()
    {
        var dep = DependencyReference.Parse("user/repo#v1.0.0");
        dep.RepoUrl.Should().Be("user/repo");
        dep.Reference.Should().Be("v1.0.0");
    }

    [Fact]
    public void Parse_WithCommitSha_ParsesReference()
    {
        var dep = DependencyReference.Parse("user/repo#abc123def");
        dep.RepoUrl.Should().Be("user/repo");
        dep.Reference.Should().Be("abc123def");
    }

    [Fact]
    public void Parse_WithAlias_ParsesAlias()
    {
        var dep = DependencyReference.Parse("user/repo@myalias");
        dep.RepoUrl.Should().Be("user/repo");
        dep.Alias.Should().Be("myalias");
        dep.Reference.Should().BeNull();
    }

    [Fact]
    public void Parse_WithReferenceAndAlias_ParsesBoth()
    {
        var dep = DependencyReference.Parse("user/repo#main@myalias");
        dep.RepoUrl.Should().Be("user/repo");
        dep.Reference.Should().Be("main");
        dep.Alias.Should().Be("myalias");
    }

    [Fact]
    public void Parse_GitHubComHost_ParsesCorrectly()
    {
        var dep = DependencyReference.Parse("github.com/user/repo");
        dep.RepoUrl.Should().Be("user/repo");
        dep.Host.Should().Be("github.com");
    }

    [Fact]
    public void Parse_GheHost_ParsesCorrectly()
    {
        var dep = DependencyReference.Parse("company.ghe.com/user/repo");
        dep.RepoUrl.Should().Be("user/repo");
        dep.Host.Should().Be("company.ghe.com");
    }

    [Fact]
    public void Parse_SshUrl_ParsesCorrectly()
    {
        var dep = DependencyReference.Parse("git@github.com:user/repo.git");
        dep.RepoUrl.Should().Be("user/repo");
        dep.Host.Should().Be("github.com");
    }

    [Fact]
    public void Parse_SshUrlWithRef_ParsesCorrectly()
    {
        var dep = DependencyReference.Parse("git@github.com:user/repo#main");
        dep.RepoUrl.Should().Be("user/repo");
        dep.Host.Should().Be("github.com");
        dep.Reference.Should().Be("main");
    }

    [Fact]
    public void Parse_AzureDevOpsWithGit_ParsesCorrectly()
    {
        var dep = DependencyReference.Parse("dev.azure.com/dmeppiel-org/market-js-app/_git/compliance-rules");
        dep.Host.Should().Be("dev.azure.com");
        dep.AdoOrganization.Should().Be("dmeppiel-org");
        dep.AdoProject.Should().Be("market-js-app");
        dep.AdoRepo.Should().Be("compliance-rules");
        dep.IsAzureDevOps().Should().BeTrue();
        dep.RepoUrl.Should().Be("dmeppiel-org/market-js-app/compliance-rules");
    }

    [Fact]
    public void Parse_AzureDevOpsSimplified_ParsesCorrectly()
    {
        var dep = DependencyReference.Parse("dev.azure.com/myorg/myproject/myrepo");
        dep.Host.Should().Be("dev.azure.com");
        dep.AdoOrganization.Should().Be("myorg");
        dep.AdoProject.Should().Be("myproject");
        dep.AdoRepo.Should().Be("myrepo");
        dep.IsAzureDevOps().Should().BeTrue();
    }

    [Fact]
    public void Parse_LegacyVisualStudio_ParsesCorrectly()
    {
        var dep = DependencyReference.Parse("mycompany.visualstudio.com/myorg/myproject/myrepo");
        dep.Host.Should().Be("mycompany.visualstudio.com");
        dep.IsAzureDevOps().Should().BeTrue();
        dep.AdoOrganization.Should().Be("myorg");
        dep.AdoProject.Should().Be("myproject");
        dep.AdoRepo.Should().Be("myrepo");
    }

    [Fact]
    public void Parse_VirtualFilePackage_ParsesCorrectly()
    {
        var dep = DependencyReference.Parse("github/awesome-copilot/prompts/code-review.prompt.md");
        dep.RepoUrl.Should().Be("github/awesome-copilot");
        dep.IsVirtual.Should().BeTrue();
        dep.VirtualPath.Should().Be("prompts/code-review.prompt.md");
        dep.IsVirtualFile().Should().BeTrue();
        dep.IsVirtualCollection().Should().BeFalse();
        dep.GetVirtualPackageName().Should().Be("awesome-copilot-code-review");
    }

    [Fact]
    public void Parse_VirtualFileWithReference_ParsesCorrectly()
    {
        var dep = DependencyReference.Parse("github/awesome-copilot/prompts/code-review.prompt.md#v1.0.0");
        dep.RepoUrl.Should().Be("github/awesome-copilot");
        dep.IsVirtual.Should().BeTrue();
        dep.VirtualPath.Should().Be("prompts/code-review.prompt.md");
        dep.Reference.Should().Be("v1.0.0");
        dep.IsVirtualFile().Should().BeTrue();
    }

    [Theory]
    [InlineData("user/repo/path/to/file.prompt.md")]
    [InlineData("user/repo/path/to/file.instructions.md")]
    [InlineData("user/repo/path/to/file.chatmode.md")]
    [InlineData("user/repo/path/to/file.agent.md")]
    public void Parse_AllVirtualFileExtensions_AreAccepted(string input)
    {
        var dep = DependencyReference.Parse(input);
        dep.IsVirtual.Should().BeTrue();
        dep.IsVirtualFile().Should().BeTrue();
    }

    [Fact]
    public void Parse_VirtualCollection_ParsesCorrectly()
    {
        var dep = DependencyReference.Parse("github/awesome-copilot/collections/project-planning");
        dep.RepoUrl.Should().Be("github/awesome-copilot");
        dep.IsVirtual.Should().BeTrue();
        dep.VirtualPath.Should().Be("collections/project-planning");
        dep.IsVirtualFile().Should().BeFalse();
        dep.IsVirtualCollection().Should().BeTrue();
        dep.GetVirtualPackageName().Should().Be("awesome-copilot-project-planning");
    }

    [Fact]
    public void Parse_VirtualCollectionWithReference_ParsesCorrectly()
    {
        var dep = DependencyReference.Parse("github/awesome-copilot/collections/testing#main");
        dep.IsVirtual.Should().BeTrue();
        dep.VirtualPath.Should().Be("collections/testing");
        dep.Reference.Should().Be("main");
        dep.IsVirtualCollection().Should().BeTrue();
    }

    [Theory]
    [InlineData("user/repo/path/to/file.txt")]
    [InlineData("user/repo/path/to/file.md")]
    [InlineData("user/repo/path/to/README.md")]
    [InlineData("user/repo/path/to/script.py")]
    public void Parse_InvalidVirtualFileExtension_Throws(string input)
    {
        var act = () => DependencyReference.Parse(input);
        act.Should().Throw<InvalidVirtualPackageExtensionException>()
           .WithMessage("*Individual files must end with one of*");
    }

    [Fact]
    public void Parse_AdoVirtualPackage_ParsesCorrectly()
    {
        var dep = DependencyReference.Parse("dev.azure.com/myorg/myproject/myrepo/prompts/code-review.prompt.md");
        dep.IsAzureDevOps().Should().BeTrue();
        dep.IsVirtual.Should().BeTrue();
        dep.RepoUrl.Should().Be("myorg/myproject/myrepo");
        dep.VirtualPath.Should().Be("prompts/code-review.prompt.md");
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    public void Parse_EmptyOrWhitespace_ThrowsArgumentException(string input)
    {
        var act = () => DependencyReference.Parse(input);
        act.Should().Throw<ArgumentException>().WithMessage("*Empty dependency string*");
    }

    [Fact]
    public void Parse_SingleSegment_ThrowsArgumentException()
    {
        var act = () => DependencyReference.Parse("just-repo-name");
        act.Should().Throw<ArgumentException>();
    }

    [Theory]
    [InlineData("evil-github.com/user/repo")]
    [InlineData("github.com.evil.com/user/repo")]
    [InlineData("fakegithub.com/user/repo")]
    [InlineData("notgithub.com/user/repo")]
    public void Parse_MaliciousHosts_ThrowsArgumentException(string input)
    {
        var act = () => DependencyReference.Parse(input);
        act.Should().Throw<ArgumentException>().WithMessage("*Unsupported Git host*");
    }

    [Fact]
    public void Parse_ProtocolRelativeUrl_ThrowsArgumentException()
    {
        var act = () => DependencyReference.Parse("//evil.com/github.com/user/repo");
        act.Should().Throw<ArgumentException>().WithMessage("*Protocol-relative URLs*");
    }

    [Fact]
    public void Parse_ControlCharacters_ThrowsArgumentException()
    {
        var act = () => DependencyReference.Parse("user/repo\0");
        act.Should().Throw<ArgumentException>().WithMessage("*control characters*");
    }

    [Fact]
    public void Parse_RegularPackage_NotVirtual()
    {
        var dep = DependencyReference.Parse("user/repo");
        dep.IsVirtual.Should().BeFalse();
        dep.VirtualPath.Should().BeNull();
        dep.IsVirtualFile().Should().BeFalse();
        dep.IsVirtualCollection().Should().BeFalse();
    }

    [Fact]
    public void Parse_HttpsGitHubUrl_ExtractsOwnerAndRepo()
    {
        var dep = DependencyReference.Parse("https://github.com/user/repo");
        dep.RepoUrl.Should().Be("user/repo");
        dep.Host.Should().Be("github.com");
    }

    [Fact]
    public void Parse_HttpsGitHubUrlWithDotGit_StripsGitSuffix()
    {
        var dep = DependencyReference.Parse("https://github.com/user/repo.git");
        dep.RepoUrl.Should().Be("user/repo");
        dep.Host.Should().Be("github.com");
    }

    [Fact]
    public void Parse_HttpsEnterpriseUrl_ExtractsHostAndRepo()
    {
        var original = Environment.GetEnvironmentVariable("GITHUB_HOST");
        try
        {
            Environment.SetEnvironmentVariable("GITHUB_HOST", "github.enterprise.com");
            var dep = DependencyReference.Parse("https://github.enterprise.com/org/project");
            dep.RepoUrl.Should().Be("org/project");
            dep.Host.Should().Be("github.enterprise.com");
        }
        finally
        {
            Environment.SetEnvironmentVariable("GITHUB_HOST", original);
        }
    }

    [Fact]
    public void Parse_SshUrlWithDotGit_ParsesCorrectly()
    {
        var dep = DependencyReference.Parse("git@github.com:user/repo.git");
        dep.RepoUrl.Should().Be("user/repo");
        dep.Host.Should().Be("github.com");
    }

    [Theory]
    [InlineData("orgname.ghe.com/user/repo")]
    public void Parse_GheUrlFormats_ParsesCorrectly(string input)
    {
        var dep = DependencyReference.Parse(input);
        dep.RepoUrl.Should().Be("user/repo");
    }

    [Fact]
    public void Parse_TrailingSlash_ThrowsArgumentException()
    {
        var act = () => DependencyReference.Parse("user/");
        act.Should().Throw<ArgumentException>();
    }

    [Theory]
    [InlineData("evil.com/github.com/user/repo")]
    [InlineData("attacker.net/github.com/malicious/repo")]
    [InlineData("GitHub.COM.evil.com/user/repo")]
    [InlineData("GITHUB.com.attacker.net/user/repo")]
    public void Parse_PathInjectionAndMixedCaseAttacks_ThrowsArgumentException(string input)
    {
        var act = () => DependencyReference.Parse(input);
        act.Should().Throw<ArgumentException>();
    }

    [Theory]
    [InlineData("evil.com/github.com/user/repo/prompts/file.prompt.md")]
    [InlineData("github.com.evil.com/user/repo/prompts/file.prompt.md")]
    [InlineData("attacker.net/user/repo/prompts/file.prompt.md")]
    public void Parse_VirtualPackageWithMaliciousHost_ThrowsArgumentException(string input)
    {
        var act = () => DependencyReference.Parse(input);
        act.Should().Throw<ArgumentException>();
    }

    [Fact]
    public void Parse_AdoVirtualPackageWithGitSegment_ParsesCorrectly()
    {
        var dep = DependencyReference.Parse("dev.azure.com/myorg/myproject/_git/myrepo/prompts/test.prompt.md");
        dep.IsAzureDevOps().Should().BeTrue();
        dep.IsVirtual.Should().BeTrue();
        dep.VirtualPath.Should().Be("prompts/test.prompt.md");
    }

    [Fact]
    public void Parse_AdoThreeSegments_NotVirtual()
    {
        var dep = DependencyReference.Parse("dev.azure.com/myorg/myproject/myrepo");
        dep.IsVirtual.Should().BeFalse();
        dep.RepoUrl.Should().Be("myorg/myproject/myrepo");
    }

    [Fact]
    public void Parse_AdoFourSegmentVirtual_ParsesCorrectly()
    {
        var dep = DependencyReference.Parse("dev.azure.com/org/proj/repo/file.prompt.md");
        dep.IsVirtual.Should().BeTrue();
        dep.RepoUrl.Should().Be("org/proj/repo");
    }

    [Fact]
    public void Parse_VirtualPackageStr_ContainsAllParts()
    {
        var dep = DependencyReference.Parse("github/awesome-copilot/prompts/code-review.prompt.md#v1.0.0");
        var str = dep.ToString();
        str.Should().Contain("github/awesome-copilot");
        str.Should().Contain("prompts/code-review.prompt.md");
        str.Should().Contain("#v1.0.0");
    }

    [Fact]
    public void Parse_VirtualPackageStrWithAlias_ContainsAllParts()
    {
        var dep = DependencyReference.Parse("github/awesome-copilot/prompts/test.prompt.md@myalias");
        var str = dep.ToString();
        str.Should().Contain("github/awesome-copilot");
        str.Should().Contain("prompts/test.prompt.md");
        str.Should().Contain("@myalias");
    }

    [Theory]
    [InlineData("/repo")]
    [InlineData("user//repo")]
    public void Parse_MalformedPaths_ThrowsArgumentException(string input)
    {
        var act = () => DependencyReference.Parse(input);
        act.Should().Throw<ArgumentException>();
    }
}

public class DependencyReferenceMethodTests
{
    [Fact]
    public void ToGitHubUrl_SimpleRepo_ReturnsFullUrl()
    {
        var dep = DependencyReference.Parse("user/repo");
        var url = dep.ToGitHubUrl();
        url.Should().Be($"https://{GitHubHost.DefaultHost()}/user/repo");
    }

    [Fact]
    public void ToGitHubUrl_AdoRepo_ReturnsAdoUrl()
    {
        var dep = DependencyReference.Parse("dev.azure.com/org/project/repo");
        var url = dep.ToGitHubUrl();
        url.Should().Contain("dev.azure.com");
        url.Should().Contain("/_git/");
    }

    [Fact]
    public void GetDisplayName_NoAlias_ReturnsRepoUrl()
    {
        var dep = DependencyReference.Parse("user/repo");
        dep.GetDisplayName().Should().Be("user/repo");
    }

    [Fact]
    public void GetDisplayName_WithAlias_ReturnsAlias()
    {
        var dep = DependencyReference.Parse("user/repo@myalias");
        dep.GetDisplayName().Should().Be("myalias");
    }

    [Fact]
    public void GetDisplayName_VirtualPackage_ReturnsVirtualName()
    {
        var dep = DependencyReference.Parse("user/repo/prompts/test.prompt.md");
        dep.GetDisplayName().Should().Be("repo-test");
    }

    [Fact]
    public void GetUniqueKey_SimpleRepo_ReturnsRepoUrl()
    {
        var dep = DependencyReference.Parse("user/repo");
        dep.GetUniqueKey().Should().Be("user/repo");
    }

    [Fact]
    public void GetUniqueKey_VirtualPackage_IncludesVirtualPath()
    {
        var dep = DependencyReference.Parse("user/repo/prompts/test.prompt.md");
        dep.GetUniqueKey().Should().Be("user/repo/prompts/test.prompt.md");
    }

    [Fact]
    public void ToDependencyString_SimpleRepo_IncludesHost()
    {
        var dep = DependencyReference.Parse("user/repo");
        var str = dep.ToDependencyString();
        str.Should().Contain("user/repo");
    }

    [Fact]
    public void ToDependencyString_WithRefAndAlias_IncludesAll()
    {
        var dep = DependencyReference.Parse("user/repo#main@myalias");
        var str = dep.ToDependencyString();
        str.Should().Contain("user/repo");
        str.Should().Contain("#main");
        str.Should().Contain("@myalias");
    }

    [Fact]
    public void ToDependencyString_EnterpriseHost_IncludesHost()
    {
        var dep = DependencyReference.Parse("company.ghe.com/user/repo");
        dep.ToDependencyString().Should().Be("company.ghe.com/user/repo");
    }

    [Fact]
    public void ToDependencyString_EnterpriseHostWithRef_IncludesHostAndRef()
    {
        var dep = DependencyReference.Parse("company.ghe.com/user/repo#v1.0.0");
        dep.ToDependencyString().Should().Be("company.ghe.com/user/repo#v1.0.0");
    }

    [Fact]
    public void ToString_MatchesToDependencyString()
    {
        var dep = DependencyReference.Parse("user/repo#main@myalias");
        dep.ToString().Should().Be(dep.ToDependencyString());
    }

    [Fact]
    public void GetInstallPath_SimpleRepo_ReturnsTwoLevelPath()
    {
        var dep = DependencyReference.Parse("user/repo");
        var path = dep.GetInstallPath("modules");
        path.Should().Be(Path.Combine("modules", "user", "repo"));
    }

    [Fact]
    public void GetInstallPath_AdoRepo_ReturnsThreeLevelPath()
    {
        var dep = DependencyReference.Parse("dev.azure.com/org/project/repo");
        var path = dep.GetInstallPath("modules");
        path.Should().Be(Path.Combine("modules", "org", "project", "repo"));
    }

    [Fact]
    public void ToCloneUrl_SameAsToGitHubUrl()
    {
        var dep = DependencyReference.Parse("user/repo");
        dep.ToCloneUrl().Should().Be(dep.ToGitHubUrl());
    }

    [Fact]
    public void IsVirtualSubdirectory_ForDirectoryPath_ReturnsTrue()
    {
        var dep = DependencyReference.Parse("user/repo/skills/my-skill");
        dep.IsVirtual.Should().BeTrue();
        dep.IsVirtualSubdirectory().Should().BeTrue();
        dep.IsVirtualFile().Should().BeFalse();
        dep.IsVirtualCollection().Should().BeFalse();
    }
}

public class ParseGitReferenceTests
{
    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("  ")]
    public void ParseGitReference_NullOrEmpty_ReturnsBranchMain(string? input)
    {
        var (type, refStr) = DependencyReference.ParseGitReference(input);
        type.Should().Be(GitReferenceType.Branch);
        refStr.Should().Be("main");
    }

    [Theory]
    [InlineData("abc1234", GitReferenceType.Commit)]
    [InlineData("abc123def456abc123def456abc123def456abcd", GitReferenceType.Commit)]
    public void ParseGitReference_CommitSha_ReturnsCommitType(string input, GitReferenceType expected)
    {
        var (type, _) = DependencyReference.ParseGitReference(input);
        type.Should().Be(expected);
    }

    [Theory]
    [InlineData("v1.0.0", GitReferenceType.Tag)]
    [InlineData("1.2.3", GitReferenceType.Tag)]
    [InlineData("v0.1.0-beta", GitReferenceType.Tag)]
    public void ParseGitReference_SemverTag_ReturnsTagType(string input, GitReferenceType expected)
    {
        var (type, _) = DependencyReference.ParseGitReference(input);
        type.Should().Be(expected);
    }

    [Theory]
    [InlineData("main")]
    [InlineData("develop")]
    [InlineData("feature/my-feature")]
    public void ParseGitReference_BranchName_ReturnsBranchType(string input)
    {
        var (type, refStr) = DependencyReference.ParseGitReference(input);
        type.Should().Be(GitReferenceType.Branch);
        refStr.Should().Be(input);
    }
}

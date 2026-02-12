using Apm.Cli.Models;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Commands;

/// <summary>
/// Tests for the selective install filter matching logic used in InstallCommand.
/// Mirrors Python test_selective_install.py::TestFilterMatchingLogic.
/// </summary>
public class SelectiveInstallFilterTests
{
    /// <summary>
    /// Normalize package string for comparison (mirrors InstallCommand.NormalizePackageRef).
    /// </summary>
    private static string NormalizePackageRef(string pkg) =>
        pkg.Replace("/_git/", "/");

    /// <summary>
    /// Replicate the filter logic from InstallCommand for isolated testing.
    /// </summary>
    private static bool MatchesFilter(string depStr, string[] onlyPackages)
    {
        var onlySet = new HashSet<string>(onlyPackages.Select(NormalizePackageRef));
        if (onlySet.Contains(depStr)) return true;
        return onlySet.Any(pkg => depStr.EndsWith($"/{pkg}"));
    }

    [Fact]
    public void ExactMatch_ReturnsTrue()
    {
        MatchesFilter("owner/repo", ["owner/repo"]).Should().BeTrue();
    }

    [Fact]
    public void HostPrefixMatch_ReturnsTrue()
    {
        MatchesFilter("github.com/owner/repo", ["owner/repo"]).Should().BeTrue();
    }

    [Fact]
    public void VirtualPackageMatch_ReturnsTrue()
    {
        MatchesFilter(
            "github.com/ComposioHQ/awesome-claude-skills/mcp-builder",
            ["ComposioHQ/awesome-claude-skills/mcp-builder"]).Should().BeTrue();
    }

    [Fact]
    public void NonMatch_ReturnsFalse()
    {
        MatchesFilter("github.com/owner2/repo2", ["owner1/repo1"]).Should().BeFalse();
    }

    [Fact]
    public void PartialRepoName_DoesNotMatch()
    {
        MatchesFilter("github.com/owner1/repo1", ["owner2/repo2"]).Should().BeFalse();
    }

    [Fact]
    public void MultiplePackagesInFilter_MatchesCorrectOnes()
    {
        var filter = new[] { "owner1/repo1", "owner2/repo2" };

        MatchesFilter("github.com/owner1/repo1", filter).Should().BeTrue();
        MatchesFilter("github.com/owner2/repo2", filter).Should().BeTrue();
        MatchesFilter("github.com/owner3/repo3", filter).Should().BeFalse();
    }

    [Fact]
    public void RealBugCase_McpBuilderVsDesignGuidelines()
    {
        var filter = new[] { "ComposioHQ/awesome-claude-skills/mcp-builder" };

        MatchesFilter(
            "github.com/ComposioHQ/awesome-claude-skills/mcp-builder",
            filter).Should().BeTrue();

        MatchesFilter(
            "github.com/danielmeppiel/design-guidelines",
            filter).Should().BeFalse();
    }

    [Fact]
    public void GitHubEnterpriseHost_Matches()
    {
        MatchesFilter("ghe.company.com/owner/repo", ["owner/repo"]).Should().BeTrue();
    }

    [Fact]
    public void AzureDevOpsHost_Matches()
    {
        MatchesFilter("dev.azure.com/org/project/repo", ["org/project/repo"]).Should().BeTrue();
    }

    [Fact]
    public void AzureDevOpsGitNormalization_Matches()
    {
        var depStr = "dev.azure.com/dmeppiel-org/market-js-app/compliance-rules";

        MatchesFilter(depStr, ["dev.azure.com/dmeppiel-org/market-js-app/_git/compliance-rules"])
            .Should().BeTrue();

        MatchesFilter(depStr, ["dmeppiel-org/market-js-app/_git/compliance-rules"])
            .Should().BeTrue();
    }

    [Fact]
    public void EmptyFilter_MatchesNothing()
    {
        MatchesFilter("github.com/owner/repo", []).Should().BeFalse();
    }

    [Fact]
    public void SubstringOwnerName_DoesNotMatch()
    {
        // "owner/repo" should NOT match "prefix-owner/repo" (path boundary check)
        MatchesFilter("github.com/prefix-owner/repo", ["owner/repo"]).Should().BeFalse();

        MatchesFilter("github.com/owner/repo", ["prefix-owner/repo"]).Should().BeFalse();
    }
}

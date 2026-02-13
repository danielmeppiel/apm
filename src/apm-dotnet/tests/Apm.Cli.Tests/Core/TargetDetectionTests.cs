using Apm.Cli.Core;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Core;

public class TargetDetectionExplicitTargetTests
{
    [Theory]
    [InlineData("vscode", "vscode")]
    [InlineData("agents", "vscode")]
    [InlineData("claude", "claude")]
    [InlineData("all", "all")]
    public void DetectTarget_ExplicitTarget_ReturnsExplicitValue(string explicitTarget, string expectedTarget)
    {
        var (target, reason) = TargetDetection.DetectTarget("/fake/path", explicitTarget: explicitTarget);

        target.Should().Be(expectedTarget);
        reason.Should().Be("explicit --target flag");
    }

    [Fact]
    public void DetectTarget_ExplicitTarget_TakesPriorityOverConfig()
    {
        var (target, reason) = TargetDetection.DetectTarget("/fake/path",
            explicitTarget: "claude", configTarget: "vscode");

        target.Should().Be("claude");
        reason.Should().Be("explicit --target flag");
    }
}

public class TargetDetectionConfigTargetTests
{
    [Theory]
    [InlineData("vscode", "vscode")]
    [InlineData("agents", "vscode")]
    [InlineData("claude", "claude")]
    [InlineData("all", "all")]
    public void DetectTarget_ConfigTarget_ReturnsConfigValue(string configTarget, string expectedTarget)
    {
        var (target, reason) = TargetDetection.DetectTarget("/fake/path", configTarget: configTarget);

        target.Should().Be(expectedTarget);
        reason.Should().Be("apm.yml target");
    }
}

public class TargetDetectionAutoDetectTests : IDisposable
{
    private readonly string _tempDir;

    public TargetDetectionAutoDetectTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm_target_test_{Guid.NewGuid()}");
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        try { Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void DetectTarget_OnlyGitHub_ReturnsVscode()
    {
        Directory.CreateDirectory(Path.Combine(_tempDir, ".github"));

        var (target, reason) = TargetDetection.DetectTarget(_tempDir);

        target.Should().Be("vscode");
        reason.Should().Be("detected .github/ folder");
    }

    [Fact]
    public void DetectTarget_OnlyClaude_ReturnsClaude()
    {
        Directory.CreateDirectory(Path.Combine(_tempDir, ".claude"));

        var (target, reason) = TargetDetection.DetectTarget(_tempDir);

        target.Should().Be("claude");
        reason.Should().Be("detected .claude/ folder");
    }

    [Fact]
    public void DetectTarget_BothGitHubAndClaude_ReturnsAll()
    {
        Directory.CreateDirectory(Path.Combine(_tempDir, ".github"));
        Directory.CreateDirectory(Path.Combine(_tempDir, ".claude"));

        var (target, reason) = TargetDetection.DetectTarget(_tempDir);

        target.Should().Be("all");
        reason.Should().Be("detected both .github/ and .claude/ folders");
    }

    [Fact]
    public void DetectTarget_NeitherFolder_ReturnsMinimal()
    {
        var (target, reason) = TargetDetection.DetectTarget(_tempDir);

        target.Should().Be("minimal");
        reason.Should().Be("no .github/ or .claude/ folder found");
    }

    [Fact]
    public void DetectTarget_ExplicitOverridesAutoDetect()
    {
        // Both folders exist (auto-detect would return "all")
        Directory.CreateDirectory(Path.Combine(_tempDir, ".github"));
        Directory.CreateDirectory(Path.Combine(_tempDir, ".claude"));

        var (target, _) = TargetDetection.DetectTarget(_tempDir, explicitTarget: "claude");

        target.Should().Be("claude");
    }

    [Fact]
    public void DetectTarget_ConfigOverridesAutoDetect()
    {
        // Only .github exists (auto-detect would return "vscode")
        Directory.CreateDirectory(Path.Combine(_tempDir, ".github"));

        var (target, reason) = TargetDetection.DetectTarget(_tempDir, configTarget: "all");

        target.Should().Be("all");
        reason.Should().Be("apm.yml target");
    }
}

public class TargetDetectionShouldIntegrateTests
{
    [Theory]
    [InlineData("vscode", true)]
    [InlineData("all", true)]
    [InlineData("claude", false)]
    [InlineData("minimal", false)]
    public void ShouldIntegrateVscode_ReturnsCorrectValue(string target, bool expected)
    {
        TargetDetection.ShouldIntegrateVscode(target).Should().Be(expected);
    }

    [Theory]
    [InlineData("claude", true)]
    [InlineData("all", true)]
    [InlineData("vscode", false)]
    [InlineData("minimal", false)]
    public void ShouldIntegrateClaude_ReturnsCorrectValue(string target, bool expected)
    {
        TargetDetection.ShouldIntegrateClaude(target).Should().Be(expected);
    }

    [Theory]
    [InlineData("vscode", true)]
    [InlineData("all", true)]
    [InlineData("minimal", true)]
    [InlineData("claude", false)]
    public void ShouldCompileAgentsMd_ReturnsCorrectValue(string target, bool expected)
    {
        TargetDetection.ShouldCompileAgentsMd(target).Should().Be(expected);
    }

    [Theory]
    [InlineData("claude", true)]
    [InlineData("all", true)]
    [InlineData("vscode", false)]
    [InlineData("minimal", false)]
    public void ShouldCompileClaudeMd_ReturnsCorrectValue(string target, bool expected)
    {
        TargetDetection.ShouldCompileClaudeMd(target).Should().Be(expected);
    }
}

public class TargetDetectionGetTargetDescriptionTests
{
    [Theory]
    [InlineData("vscode", "AGENTS.md + .github/prompts/ + .github/agents/")]
    [InlineData("claude", "CLAUDE.md + .claude/commands/ + SKILL.md")]
    [InlineData("all", "AGENTS.md + CLAUDE.md + .github/ + .claude/")]
    [InlineData("minimal", "AGENTS.md only (create .github/ or .claude/ for full integration)")]
    public void GetTargetDescription_ReturnsExpectedDescription(string target, string expectedDesc)
    {
        TargetDetection.GetTargetDescription(target).Should().Be(expectedDesc);
    }

    [Fact]
    public void GetTargetDescription_UnknownTarget_ReturnsUnknown()
    {
        TargetDetection.GetTargetDescription("nonexistent").Should().Be("unknown target");
    }
}

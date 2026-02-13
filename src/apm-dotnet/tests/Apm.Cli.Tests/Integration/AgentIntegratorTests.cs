using Apm.Cli.Integration;
using Apm.Cli.Models;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Integration;

public class AgentIntegratorTests : IDisposable
{
    private readonly AgentIntegrator _sut = new();
    private readonly string _tempDir;

    public AgentIntegratorTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm_agent_test_{Guid.NewGuid()}");
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    private static ApmPackage CreatePackage(string name = "test-pkg") =>
        new() { Name = name, Version = "1.0.0" };

    private string CreatePackageDir(string name = "test-pkg")
    {
        var dir = Path.Combine(_tempDir, "packages", name);
        Directory.CreateDirectory(dir);
        return dir;
    }

    #region FindAgentFiles

    [Fact]
    public void FindAgentFiles_EmptyDirectory_ReturnsEmpty()
    {
        var pkgDir = CreatePackageDir();
        _sut.FindAgentFiles(pkgDir).Should().BeEmpty();
    }

    [Fact]
    public void FindAgentFiles_TopLevel_FindsAgentMdFiles()
    {
        var pkgDir = CreatePackageDir();
        File.WriteAllText(Path.Combine(pkgDir, "reviewer.agent.md"), "# Agent");
        File.WriteAllText(Path.Combine(pkgDir, "readme.md"), "# Not an agent");

        var results = _sut.FindAgentFiles(pkgDir);

        results.Should().HaveCount(1);
        Path.GetFileName(results[0]).Should().Be("reviewer.agent.md");
    }

    [Fact]
    public void FindAgentFiles_TopLevel_FindsChatmodeMdFiles()
    {
        var pkgDir = CreatePackageDir();
        File.WriteAllText(Path.Combine(pkgDir, "helper.chatmode.md"), "# Chatmode");

        var results = _sut.FindAgentFiles(pkgDir);

        results.Should().HaveCount(1);
        Path.GetFileName(results[0]).Should().Be("helper.chatmode.md");
    }

    [Fact]
    public void FindAgentFiles_ApmAgentsDir_FindsFiles()
    {
        var pkgDir = CreatePackageDir();
        var agentsDir = Path.Combine(pkgDir, ".apm", "agents");
        Directory.CreateDirectory(agentsDir);
        File.WriteAllText(Path.Combine(agentsDir, "coder.agent.md"), "# Coder");

        var results = _sut.FindAgentFiles(pkgDir);

        results.Should().HaveCount(1);
    }

    [Fact]
    public void FindAgentFiles_ApmChatmodesDir_FindsFiles()
    {
        var pkgDir = CreatePackageDir();
        var chatmodesDir = Path.Combine(pkgDir, ".apm", "chatmodes");
        Directory.CreateDirectory(chatmodesDir);
        File.WriteAllText(Path.Combine(chatmodesDir, "debug.chatmode.md"), "# Debug");

        var results = _sut.FindAgentFiles(pkgDir);

        results.Should().HaveCount(1);
    }

    [Fact]
    public void FindAgentFiles_AllLocations_CombinesResults()
    {
        var pkgDir = CreatePackageDir();
        File.WriteAllText(Path.Combine(pkgDir, "top.agent.md"), "# Top");
        File.WriteAllText(Path.Combine(pkgDir, "mode.chatmode.md"), "# Mode");

        var agentsDir = Path.Combine(pkgDir, ".apm", "agents");
        Directory.CreateDirectory(agentsDir);
        File.WriteAllText(Path.Combine(agentsDir, "nested.agent.md"), "# Nested");

        var chatmodesDir = Path.Combine(pkgDir, ".apm", "chatmodes");
        Directory.CreateDirectory(chatmodesDir);
        File.WriteAllText(Path.Combine(chatmodesDir, "deep.chatmode.md"), "# Deep");

        var results = _sut.FindAgentFiles(pkgDir);

        results.Should().HaveCount(4);
    }

    [Fact]
    public void FindAgentFiles_NonExistentPath_ReturnsEmpty()
    {
        _sut.FindAgentFiles(Path.Combine(_tempDir, "nonexistent")).Should().BeEmpty();
    }

    #endregion

    #region GetTargetFilename

    [Fact]
    public void GetTargetFilename_AgentMd_AddsApmSuffix()
    {
        var result = _sut.GetTargetFilename("reviewer.agent.md", "my-pkg");
        result.Should().Be("reviewer-apm.agent.md");
    }

    [Fact]
    public void GetTargetFilename_ChatmodeMd_AddsApmSuffix()
    {
        var result = _sut.GetTargetFilename("helper.chatmode.md", "my-pkg");
        result.Should().Be("helper-apm.chatmode.md");
    }

    [Fact]
    public void GetTargetFilename_UnknownExtension_FallsBack()
    {
        var result = _sut.GetTargetFilename("unknown.txt", "pkg");
        result.Should().Be("unknown-apm.txt");
    }

    [Fact]
    public void GetTargetFilename_WithPath_UsesFileNameOnly()
    {
        var result = _sut.GetTargetFilename(Path.Combine("some", "dir", "coder.agent.md"), "pkg");
        result.Should().Be("coder-apm.agent.md");
    }

    #endregion

    #region CopyAgent

    [Fact]
    public void CopyAgent_CopiesFileVerbatim()
    {
        var sourceDir = CreatePackageDir("source");
        var source = Path.Combine(sourceDir, "test.agent.md");
        var content = "---\nname: test\n---\n# Agent instructions";
        File.WriteAllText(source, content);

        var targetDir = Path.Combine(_tempDir, "target");
        Directory.CreateDirectory(targetDir);
        var target = Path.Combine(targetDir, "test-apm.agent.md");

        var linksResolved = _sut.CopyAgent(source, target);

        linksResolved.Should().Be(0);
        File.ReadAllText(target).Should().Be(content);
    }

    [Fact]
    public void CopyAgent_CreatesTargetDirectory()
    {
        var sourceDir = CreatePackageDir("source");
        var source = Path.Combine(sourceDir, "test.agent.md");
        File.WriteAllText(source, "content");

        var target = Path.Combine(_tempDir, "deep", "nested", "test-apm.agent.md");

        _sut.CopyAgent(source, target);

        File.Exists(target).Should().BeTrue();
    }

    #endregion

    #region IntegratePackageAgents

    [Fact]
    public void IntegratePackageAgents_NoAgents_ReturnsZeroCounts()
    {
        var pkgDir = CreatePackageDir();
        var pkg = CreatePackage();
        var info = new PackageInfo(pkg, pkgDir);
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var result = _sut.IntegratePackageAgents(info, projectRoot);

        result.FilesIntegrated.Should().Be(0);
        result.TargetPaths.Should().BeEmpty();
    }

    [Fact]
    public void IntegratePackageAgents_WithAgents_CopiesToGithubAgents()
    {
        var pkgDir = CreatePackageDir();
        File.WriteAllText(Path.Combine(pkgDir, "reviewer.agent.md"), "# Review agent");

        var pkg = CreatePackage();
        var info = new PackageInfo(pkg, pkgDir);
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var result = _sut.IntegratePackageAgents(info, projectRoot);

        result.FilesIntegrated.Should().Be(1);
        result.TargetPaths.Should().HaveCount(1);

        var expectedTarget = Path.Combine(projectRoot, ".github", "agents", "reviewer-apm.agent.md");
        File.Exists(expectedTarget).Should().BeTrue();
        File.ReadAllText(expectedTarget).Should().Be("# Review agent");
    }

    [Fact]
    public void IntegratePackageAgents_DuplicateAgent_OverwritesExisting()
    {
        var pkgDir = CreatePackageDir();
        File.WriteAllText(Path.Combine(pkgDir, "reviewer.agent.md"), "# Updated agent");

        var projectRoot = Path.Combine(_tempDir, "project");
        var agentsDir = Path.Combine(projectRoot, ".github", "agents");
        Directory.CreateDirectory(agentsDir);
        File.WriteAllText(Path.Combine(agentsDir, "reviewer-apm.agent.md"), "# Old agent");

        var pkg = CreatePackage();
        var info = new PackageInfo(pkg, pkgDir);

        var result = _sut.IntegratePackageAgents(info, projectRoot);

        result.FilesIntegrated.Should().Be(1);
        File.ReadAllText(Path.Combine(agentsDir, "reviewer-apm.agent.md")).Should().Be("# Updated agent");
    }

    [Fact]
    public void IntegratePackageAgents_MixedTypes_IntegratesAll()
    {
        var pkgDir = CreatePackageDir();
        File.WriteAllText(Path.Combine(pkgDir, "reviewer.agent.md"), "# Agent");
        File.WriteAllText(Path.Combine(pkgDir, "helper.chatmode.md"), "# Chatmode");

        var pkg = CreatePackage();
        var info = new PackageInfo(pkg, pkgDir);
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var result = _sut.IntegratePackageAgents(info, projectRoot);

        result.FilesIntegrated.Should().Be(2);
        result.TargetPaths.Should().HaveCount(2);
    }

    #endregion

    #region SyncIntegration

    [Fact]
    public void SyncIntegration_RemovesApmManagedAgentFiles()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        var agentsDir = Path.Combine(projectRoot, ".github", "agents");
        Directory.CreateDirectory(agentsDir);
        File.WriteAllText(Path.Combine(agentsDir, "reviewer-apm.agent.md"), "managed");
        File.WriteAllText(Path.Combine(agentsDir, "custom.agent.md"), "user file");

        var apmPkg = new ApmPackage { Name = "test" };
        var stats = _sut.SyncIntegration(apmPkg, projectRoot);

        stats["files_removed"].Should().Be(1);
        File.Exists(Path.Combine(agentsDir, "custom.agent.md")).Should().BeTrue();
    }

    [Fact]
    public void SyncIntegration_RemovesChatmodeFiles()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        var agentsDir = Path.Combine(projectRoot, ".github", "agents");
        Directory.CreateDirectory(agentsDir);
        File.WriteAllText(Path.Combine(agentsDir, "helper-apm.chatmode.md"), "managed");

        var apmPkg = new ApmPackage { Name = "test" };
        var stats = _sut.SyncIntegration(apmPkg, projectRoot);

        stats["files_removed"].Should().Be(1);
    }

    [Fact]
    public void SyncIntegration_NoAgentsDir_ReturnsZero()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var apmPkg = new ApmPackage { Name = "test" };
        var stats = _sut.SyncIntegration(apmPkg, projectRoot);

        stats["files_removed"].Should().Be(0);
    }

    #endregion

    #region UpdateGitignoreForIntegratedAgents

    [Fact]
    public void UpdateGitignore_AddsPatternsToNewFile()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var result = _sut.UpdateGitignoreForIntegratedAgents(projectRoot);

        result.Should().BeTrue();
        var content = File.ReadAllText(Path.Combine(projectRoot, ".gitignore"));
        content.Should().Contain(".github/agents/*-apm.agent.md");
        content.Should().Contain(".github/agents/*-apm.chatmode.md");
    }

    [Fact]
    public void UpdateGitignore_SkipsIfAllPatternsPresent()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);
        File.WriteAllText(Path.Combine(projectRoot, ".gitignore"),
            ".github/agents/*-apm.agent.md\n.github/agents/*-apm.chatmode.md\n");

        var result = _sut.UpdateGitignoreForIntegratedAgents(projectRoot);

        result.Should().BeFalse();
    }

    #endregion

    #region ShouldIntegrate

    [Fact]
    public void ShouldIntegrate_AlwaysReturnsTrue()
    {
        _sut.ShouldIntegrate(_tempDir).Should().BeTrue();
    }

    #endregion

    #region VerbatimCopy_NoMetadataInjection

    [Fact]
    public void CopyAgent_PreservesExistingFrontmatter()
    {
        var sourceDir = CreatePackageDir("source");
        var source = Path.Combine(sourceDir, "test.agent.md");
        var content = "---\ndescription: My agent\ntools: []\n---\n\n# Agent content here";
        File.WriteAllText(source, content);

        var targetDir = Path.Combine(_tempDir, "target");
        Directory.CreateDirectory(targetDir);
        var target = Path.Combine(targetDir, "test-apm.agent.md");

        _sut.CopyAgent(source, target);

        File.ReadAllText(target).Should().Be(content);
    }

    [Fact]
    public void IntegratePackageAgents_FirstTimeCopy_NoApmMetadata()
    {
        var pkgDir = CreatePackageDir();
        File.WriteAllText(Path.Combine(pkgDir, "security.agent.md"), "# Security Agent Content");

        var pkg = CreatePackage();
        var info = new PackageInfo(pkg, pkgDir);
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var result = _sut.IntegratePackageAgents(info, projectRoot);

        result.FilesIntegrated.Should().Be(1);

        var targetFile = Path.Combine(projectRoot, ".github", "agents", "security-apm.agent.md");
        var content = File.ReadAllText(targetFile);
        content.Should().Be("# Security Agent Content");
        content.Should().NotContain("apm:");
    }

    [Fact]
    public void IntegratePackageAgents_AllFilesAlwaysCopied_EvenWithPreExisting()
    {
        var pkgDir = CreatePackageDir();
        File.WriteAllText(Path.Combine(pkgDir, "new.agent.md"), "# New Agent");
        File.WriteAllText(Path.Combine(pkgDir, "existing.agent.md"), "# Updated Agent");
        File.WriteAllText(Path.Combine(pkgDir, "another.agent.md"), "# Another Agent");

        var projectRoot = Path.Combine(_tempDir, "project");
        var agentsDir = Path.Combine(projectRoot, ".github", "agents");
        Directory.CreateDirectory(agentsDir);
        File.WriteAllText(Path.Combine(agentsDir, "existing-apm.agent.md"), "# Old Content");
        File.WriteAllText(Path.Combine(agentsDir, "another-apm.agent.md"), "# Old Another");

        var pkg = CreatePackage();
        var info = new PackageInfo(pkg, pkgDir);

        var result = _sut.IntegratePackageAgents(info, projectRoot);

        result.FilesIntegrated.Should().Be(3);

        File.ReadAllText(Path.Combine(agentsDir, "new-apm.agent.md")).Should().Be("# New Agent");
        File.ReadAllText(Path.Combine(agentsDir, "existing-apm.agent.md")).Should().Be("# Updated Agent");
        File.ReadAllText(Path.Combine(agentsDir, "another-apm.agent.md")).Should().Be("# Another Agent");
    }

    #endregion

    #region SyncIntegration_EdgeCases

    [Fact]
    public void SyncIntegration_RemovesApmFiles_RegardlessOfContent()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        var agentsDir = Path.Combine(projectRoot, ".github", "agents");
        Directory.CreateDirectory(agentsDir);
        // APM-managed file with no frontmatter — still removed by pattern
        File.WriteAllText(Path.Combine(agentsDir, "custom-apm.agent.md"), "# Agent without header");

        var apmPkg = new ApmPackage { Name = "test" };
        var stats = _sut.SyncIntegration(apmPkg, projectRoot);

        stats["files_removed"].Should().Be(1);
        File.Exists(Path.Combine(agentsDir, "custom-apm.agent.md")).Should().BeFalse();
    }

    #endregion

    #region SkillSeparation_Regression

    [Fact]
    public void FindAgentFiles_IgnoresSkillMdFiles()
    {
        var pkgDir = CreatePackageDir();
        File.WriteAllText(Path.Combine(pkgDir, "security.agent.md"), "# Real Agent");
        File.WriteAllText(Path.Combine(pkgDir, "SKILL.md"), "# This is a skill");
        File.WriteAllText(Path.Combine(pkgDir, "skill.md"), "# Also a skill");

        var results = _sut.FindAgentFiles(pkgDir);

        results.Should().HaveCount(1);
        Path.GetFileName(results[0]).Should().Be("security.agent.md");
    }

    [Fact]
    public void IntegratePackageAgents_SkillMd_NotConvertedToAgent()
    {
        var pkgDir = CreatePackageDir();
        File.WriteAllText(Path.Combine(pkgDir, "SKILL.md"),
            "---\nname: test-skill\ndescription: A test skill\n---\n# Test Skill\n\nThis is a skill, not an agent.");

        var pkg = CreatePackage("skill-pkg");
        var info = new PackageInfo(pkg, pkgDir);
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var result = _sut.IntegratePackageAgents(info, projectRoot);

        result.FilesIntegrated.Should().Be(0);

        var agentsDir = Path.Combine(projectRoot, ".github", "agents");
        if (Directory.Exists(agentsDir))
        {
            Directory.EnumerateFiles(agentsDir, "*.agent.md")
                .Select(Path.GetFileName)
                .Should().NotContain(f => f!.Contains("skill", StringComparison.OrdinalIgnoreCase));
        }
    }

    #endregion

    #region GetTargetFilename_EdgeCases

    [Theory]
    [InlineData("backend-engineer.agent.md", "backend-engineer-apm.agent.md")]
    [InlineData("security-audit-tool.agent.md", "security-audit-tool-apm.agent.md")]
    [InlineData("my_custom-agent.agent.md", "my_custom-agent-apm.agent.md")]
    public void GetTargetFilename_VariousAgentNames_AddsApmSuffix(string input, string expected)
    {
        _sut.GetTargetFilename(input, "pkg").Should().Be(expected);
    }

    #endregion
}

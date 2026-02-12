using Apm.Cli.Integration;
using Apm.Cli.Models;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Integration;

public class CommandIntegratorTests : IDisposable
{
    private readonly CommandIntegrator _sut = new();
    private readonly string _tempDir;

    public CommandIntegratorTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm_cmd_test_{Guid.NewGuid()}");
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

    #region FindPromptFiles

    [Fact]
    public void FindPromptFiles_EmptyDirectory_ReturnsEmpty()
    {
        var pkgDir = CreatePackageDir();
        _sut.FindPromptFiles(pkgDir).Should().BeEmpty();
    }

    [Fact]
    public void FindPromptFiles_TopLevel_FindsPromptMdFiles()
    {
        var pkgDir = CreatePackageDir();
        File.WriteAllText(Path.Combine(pkgDir, "review.prompt.md"), "# Review");
        File.WriteAllText(Path.Combine(pkgDir, "readme.md"), "# Not a prompt");

        var results = _sut.FindPromptFiles(pkgDir);

        results.Should().HaveCount(1);
    }

    [Fact]
    public void FindPromptFiles_ApmPromptsDir_FindsFiles()
    {
        var pkgDir = CreatePackageDir();
        var promptsDir = Path.Combine(pkgDir, ".apm", "prompts");
        Directory.CreateDirectory(promptsDir);
        File.WriteAllText(Path.Combine(promptsDir, "deploy.prompt.md"), "# Deploy");

        var results = _sut.FindPromptFiles(pkgDir);

        results.Should().HaveCount(1);
    }

    #endregion

    #region TransformPromptToCommand

    [Fact]
    public void TransformPromptToCommand_ExtractsCommandName()
    {
        var pkgDir = CreatePackageDir();
        var source = Path.Combine(pkgDir, "code-review.prompt.md");
        File.WriteAllText(source, "# Review code");

        var (commandName, _, _, _) = _sut.TransformPromptToCommand(source);

        commandName.Should().Be("code-review");
    }

    [Fact]
    public void TransformPromptToCommand_MapsFrontmatter()
    {
        var pkgDir = CreatePackageDir();
        var source = Path.Combine(pkgDir, "review.prompt.md");
        File.WriteAllText(source, "---\ndescription: Review code\nmodel: gpt-4\n---\n# Content");

        var (_, metadata, _, _) = _sut.TransformPromptToCommand(source);

        metadata.Should().ContainKey("description");
        metadata["description"].Should().Be("Review code");
        metadata.Should().ContainKey("model");
        metadata["model"].Should().Be("gpt-4");
    }

    [Fact]
    public void TransformPromptToCommand_MapsAllowedTools()
    {
        var pkgDir = CreatePackageDir();
        var source = Path.Combine(pkgDir, "deploy.prompt.md");
        File.WriteAllText(source, "---\nallowed-tools: bash, git\n---\n# Deploy");

        var (_, metadata, _, _) = _sut.TransformPromptToCommand(source);

        metadata.Should().ContainKey("allowed-tools");
    }

    [Fact]
    public void TransformPromptToCommand_MapsArgumentHint()
    {
        var pkgDir = CreatePackageDir();
        var source = Path.Combine(pkgDir, "search.prompt.md");
        File.WriteAllText(source, "---\nargument-hint: search query\n---\n# Search");

        var (_, metadata, _, _) = _sut.TransformPromptToCommand(source);

        metadata.Should().ContainKey("argument-hint");
        metadata["argument-hint"].Should().Be("search query");
    }

    [Fact]
    public void TransformPromptToCommand_NoFrontmatter_ReturnsBody()
    {
        var pkgDir = CreatePackageDir();
        var source = Path.Combine(pkgDir, "simple.prompt.md");
        File.WriteAllText(source, "# Simple prompt content");

        var (_, metadata, body, _) = _sut.TransformPromptToCommand(source);

        metadata.Should().BeEmpty();
        body.Should().Contain("Simple prompt content");
    }

    #endregion

    #region IntegrateCommand

    [Fact]
    public void IntegrateCommand_WritesTransformedFile()
    {
        var pkgDir = CreatePackageDir();
        var source = Path.Combine(pkgDir, "review.prompt.md");
        File.WriteAllText(source, "---\ndescription: Code review\n---\nReview the code.");

        var target = Path.Combine(_tempDir, "commands", "review-apm.md");
        var pkg = CreatePackage();
        var info = new PackageInfo(pkg, pkgDir);

        _sut.IntegrateCommand(source, target, info, source);

        File.Exists(target).Should().BeTrue();
        var content = File.ReadAllText(target);
        content.Should().Contain("description: Code review");
        content.Should().Contain("Review the code.");
    }

    [Fact]
    public void IntegrateCommand_NoFrontmatter_WritesBodyOnly()
    {
        var pkgDir = CreatePackageDir();
        var source = Path.Combine(pkgDir, "simple.prompt.md");
        File.WriteAllText(source, "Just do it.");

        var target = Path.Combine(_tempDir, "commands", "simple-apm.md");
        var pkg = CreatePackage();
        var info = new PackageInfo(pkg, pkgDir);

        _sut.IntegrateCommand(source, target, info, source);

        var content = File.ReadAllText(target);
        content.Should().NotContain("---");
        content.Should().Contain("Just do it.");
    }

    #endregion

    #region IntegratePackageCommands

    [Fact]
    public void IntegratePackageCommands_NoPrompts_ReturnsZeroCounts()
    {
        var pkgDir = CreatePackageDir();
        var pkg = CreatePackage();
        var info = new PackageInfo(pkg, pkgDir);
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);
        File.WriteAllText(Path.Combine(projectRoot, ".gitignore"), "");

        var result = _sut.IntegratePackageCommands(info, projectRoot);

        result.FilesIntegrated.Should().Be(0);
        result.TargetPaths.Should().BeEmpty();
    }

    [Fact]
    public void IntegratePackageCommands_WithPrompts_CreatesCommandFiles()
    {
        var pkgDir = CreatePackageDir();
        File.WriteAllText(Path.Combine(pkgDir, "review.prompt.md"), "# Review");

        var pkg = CreatePackage();
        var info = new PackageInfo(pkg, pkgDir);
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);
        File.WriteAllText(Path.Combine(projectRoot, ".gitignore"), "");

        var result = _sut.IntegratePackageCommands(info, projectRoot);

        result.FilesIntegrated.Should().Be(1);
        result.TargetPaths.Should().HaveCount(1);

        var expectedTarget = Path.Combine(projectRoot, ".claude", "commands", "review-apm.md");
        File.Exists(expectedTarget).Should().BeTrue();
    }

    [Fact]
    public void IntegratePackageCommands_UpdatesGitignore()
    {
        var pkgDir = CreatePackageDir();
        File.WriteAllText(Path.Combine(pkgDir, "review.prompt.md"), "# Review");

        var pkg = CreatePackage();
        var info = new PackageInfo(pkg, pkgDir);
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);
        File.WriteAllText(Path.Combine(projectRoot, ".gitignore"), "");

        var result = _sut.IntegratePackageCommands(info, projectRoot);

        result.GitignoreUpdated.Should().BeTrue();
        var gitignore = File.ReadAllText(Path.Combine(projectRoot, ".gitignore"));
        gitignore.Should().Contain(".claude/commands/*-apm.md");
    }

    #endregion

    #region SyncIntegration

    [Fact]
    public void SyncIntegration_RemovesApmManagedCommandFiles()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        var commandsDir = Path.Combine(projectRoot, ".claude", "commands");
        Directory.CreateDirectory(commandsDir);
        File.WriteAllText(Path.Combine(commandsDir, "review-apm.md"), "managed");
        File.WriteAllText(Path.Combine(commandsDir, "custom.md"), "user file");

        var apmPkg = new ApmPackage { Name = "test" };
        var stats = _sut.SyncIntegration(apmPkg, projectRoot);

        stats["files_removed"].Should().Be(1);
        File.Exists(Path.Combine(commandsDir, "custom.md")).Should().BeTrue();
    }

    [Fact]
    public void SyncIntegration_NoCommandsDir_ReturnsZero()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var apmPkg = new ApmPackage { Name = "test" };
        var stats = _sut.SyncIntegration(apmPkg, projectRoot);

        stats["files_removed"].Should().Be(0);
    }

    #endregion

    #region RemovePackageCommands

    [Fact]
    public void RemovePackageCommands_RemovesApmFiles()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        var commandsDir = Path.Combine(projectRoot, ".claude", "commands");
        Directory.CreateDirectory(commandsDir);
        File.WriteAllText(Path.Combine(commandsDir, "review-apm.md"), "managed");
        File.WriteAllText(Path.Combine(commandsDir, "custom.md"), "user file");

        var removed = _sut.RemovePackageCommands("test-pkg", projectRoot);

        removed.Should().Be(1);
        File.Exists(Path.Combine(commandsDir, "custom.md")).Should().BeTrue();
    }

    [Fact]
    public void RemovePackageCommands_NoDir_ReturnsZero()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        _sut.RemovePackageCommands("test-pkg", projectRoot).Should().Be(0);
    }

    #endregion

    #region ShouldIntegrate

    [Fact]
    public void ShouldIntegrate_AlwaysReturnsTrue()
    {
        _sut.ShouldIntegrate(_tempDir).Should().BeTrue();
    }

    #endregion

    #region IntegrateCommand_MetadataHandling

    [Fact]
    public void IntegrateCommand_NoApmMetadataInOutput()
    {
        var pkgDir = CreatePackageDir();
        var source = Path.Combine(pkgDir, "audit.prompt.md");
        File.WriteAllText(source, "---\ndescription: Run audit checks\n---\n# Audit Command\nRun compliance audit.");

        var target = Path.Combine(_tempDir, "commands", "audit-apm.md");
        var pkg = CreatePackage();
        var info = new PackageInfo(pkg, pkgDir);

        _sut.IntegrateCommand(source, target, info, source);

        var content = File.ReadAllText(target);
        content.Should().NotContain("apm:");
        content.Should().Contain("description: Run audit checks");
    }

    [Fact]
    public void IntegrateCommand_ContentPreservedVerbatim()
    {
        var pkgDir = CreatePackageDir();
        var body = "# My Command\nDo something useful.\n\n## Steps\n1. First\n2. Second";
        var source = Path.Combine(pkgDir, "test.prompt.md");
        File.WriteAllText(source, $"---\ndescription: Test\n---\n{body}");

        var target = Path.Combine(_tempDir, "commands", "test-apm.md");
        var pkg = CreatePackage();
        var info = new PackageInfo(pkg, pkgDir);

        _sut.IntegrateCommand(source, target, info, source);

        var content = File.ReadAllText(target);
        content.Should().Contain("My Command");
        content.Should().Contain("Do something useful.");
    }

    [Fact]
    public void IntegrateCommand_ClaudeMetadataFieldsMapped()
    {
        var pkgDir = CreatePackageDir();
        var source = Path.Combine(pkgDir, "cmd.prompt.md");
        File.WriteAllText(source, "---\ndescription: A command\nallowed-tools: bash, edit\nmodel: claude-sonnet\nargument-hint: file path\n---\n# Command");

        var target = Path.Combine(_tempDir, "commands", "cmd-apm.md");
        var pkg = CreatePackage();
        var info = new PackageInfo(pkg, pkgDir);

        _sut.IntegrateCommand(source, target, info, source);

        var content = File.ReadAllText(target);
        content.Should().Contain("description:");
        content.Should().Contain("allowed-tools:");
        content.Should().Contain("model:");
        content.Should().Contain("argument-hint:");
        content.Should().NotContain("apm:");
    }

    #endregion

    #region SyncIntegration_EdgeCases

    [Fact]
    public void SyncIntegration_WithEmptyDependencies_StillRemovesApmFiles()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        var commandsDir = Path.Combine(projectRoot, ".claude", "commands");
        Directory.CreateDirectory(commandsDir);
        File.WriteAllText(Path.Combine(commandsDir, "cmd1-apm.md"), "# Command 1");
        File.WriteAllText(Path.Combine(commandsDir, "cmd2-apm.md"), "# Command 2");

        var apmPkg = new ApmPackage { Name = "test" };
        var stats = _sut.SyncIntegration(apmPkg, projectRoot);

        stats["files_removed"].Should().Be(2);
    }

    #endregion
}

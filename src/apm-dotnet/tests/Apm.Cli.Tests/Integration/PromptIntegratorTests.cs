using Apm.Cli.Integration;
using Apm.Cli.Models;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Integration;

public class PromptIntegratorTests : IDisposable
{
    private readonly PromptIntegrator _sut = new();
    private readonly string _tempDir;

    public PromptIntegratorTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm_prompt_test_{Guid.NewGuid()}");
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
        File.WriteAllText(Path.Combine(pkgDir, "code-review.prompt.md"), "# Review");
        File.WriteAllText(Path.Combine(pkgDir, "readme.md"), "# Not a prompt");

        var results = _sut.FindPromptFiles(pkgDir);

        results.Should().HaveCount(1);
        Path.GetFileName(results[0]).Should().Be("code-review.prompt.md");
    }

    [Fact]
    public void FindPromptFiles_ApmPromptsDir_FindsFiles()
    {
        var pkgDir = CreatePackageDir();
        var promptsDir = Path.Combine(pkgDir, ".apm", "prompts");
        Directory.CreateDirectory(promptsDir);
        File.WriteAllText(Path.Combine(promptsDir, "lint.prompt.md"), "# Lint");

        var results = _sut.FindPromptFiles(pkgDir);

        results.Should().HaveCount(1);
        Path.GetFileName(results[0]).Should().Be("lint.prompt.md");
    }

    [Fact]
    public void FindPromptFiles_BothLocations_CombinesResults()
    {
        var pkgDir = CreatePackageDir();
        File.WriteAllText(Path.Combine(pkgDir, "top.prompt.md"), "# Top");
        var promptsDir = Path.Combine(pkgDir, ".apm", "prompts");
        Directory.CreateDirectory(promptsDir);
        File.WriteAllText(Path.Combine(promptsDir, "nested.prompt.md"), "# Nested");

        var results = _sut.FindPromptFiles(pkgDir);

        results.Should().HaveCount(2);
    }

    [Fact]
    public void FindPromptFiles_NonExistentPath_ReturnsEmpty()
    {
        var fakePath = Path.Combine(_tempDir, "nonexistent");
        _sut.FindPromptFiles(fakePath).Should().BeEmpty();
    }

    #endregion

    #region GetTargetFilename

    [Fact]
    public void GetTargetFilename_PromptMd_AddsApmSuffix()
    {
        var result = _sut.GetTargetFilename("code-review.prompt.md", "my-pkg");
        result.Should().Be("code-review-apm.prompt.md");
    }

    [Fact]
    public void GetTargetFilename_WithPath_UsesFileNameOnly()
    {
        var result = _sut.GetTargetFilename(Path.Combine("some", "dir", "lint.prompt.md"), "pkg");
        result.Should().Be("lint-apm.prompt.md");
    }

    #endregion

    #region CopyPrompt

    [Fact]
    public void CopyPrompt_CopiesFileVerbatim()
    {
        var sourceDir = CreatePackageDir("source");
        var source = Path.Combine(sourceDir, "test.prompt.md");
        var content = "---\ndescription: Test\n---\n# Hello";
        File.WriteAllText(source, content);

        var targetDir = Path.Combine(_tempDir, "target");
        Directory.CreateDirectory(targetDir);
        var target = Path.Combine(targetDir, "test-apm.prompt.md");

        var linksResolved = _sut.CopyPrompt(source, target);

        linksResolved.Should().Be(0);
        File.ReadAllText(target).Should().Be(content);
    }

    [Fact]
    public void CopyPrompt_CreatesTargetDirectory()
    {
        var sourceDir = CreatePackageDir("source");
        var source = Path.Combine(sourceDir, "test.prompt.md");
        File.WriteAllText(source, "content");

        var target = Path.Combine(_tempDir, "deep", "nested", "test-apm.prompt.md");

        _sut.CopyPrompt(source, target);

        File.Exists(target).Should().BeTrue();
    }

    #endregion

    #region IntegratePackagePrompts

    [Fact]
    public void IntegratePackagePrompts_NoPrompts_ReturnsZeroCounts()
    {
        var pkgDir = CreatePackageDir();
        var pkg = CreatePackage();
        var info = new PackageInfo(pkg, pkgDir);
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var result = _sut.IntegratePackagePrompts(info, projectRoot);

        result.FilesIntegrated.Should().Be(0);
        result.FilesSkipped.Should().Be(0);
        result.TargetPaths.Should().BeEmpty();
    }

    [Fact]
    public void IntegratePackagePrompts_WithPrompts_CopiesToGithubPrompts()
    {
        var pkgDir = CreatePackageDir();
        File.WriteAllText(Path.Combine(pkgDir, "review.prompt.md"), "# Review prompt");

        var pkg = CreatePackage();
        var info = new PackageInfo(pkg, pkgDir);
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var result = _sut.IntegratePackagePrompts(info, projectRoot);

        result.FilesIntegrated.Should().Be(1);
        result.TargetPaths.Should().HaveCount(1);

        var expectedTarget = Path.Combine(projectRoot, ".github", "prompts", "review-apm.prompt.md");
        File.Exists(expectedTarget).Should().BeTrue();
        File.ReadAllText(expectedTarget).Should().Be("# Review prompt");
    }

    [Fact]
    public void IntegratePackagePrompts_DuplicatePrompt_OverwritesExisting()
    {
        var pkgDir = CreatePackageDir();
        File.WriteAllText(Path.Combine(pkgDir, "review.prompt.md"), "# Updated content");

        var projectRoot = Path.Combine(_tempDir, "project");
        var promptsDir = Path.Combine(projectRoot, ".github", "prompts");
        Directory.CreateDirectory(promptsDir);
        File.WriteAllText(Path.Combine(promptsDir, "review-apm.prompt.md"), "# Old content");

        var pkg = CreatePackage();
        var info = new PackageInfo(pkg, pkgDir);

        var result = _sut.IntegratePackagePrompts(info, projectRoot);

        result.FilesIntegrated.Should().Be(1);
        var target = Path.Combine(promptsDir, "review-apm.prompt.md");
        File.ReadAllText(target).Should().Be("# Updated content");
    }

    [Fact]
    public void IntegratePackagePrompts_MultipleFiles_IntegratesAll()
    {
        var pkgDir = CreatePackageDir();
        File.WriteAllText(Path.Combine(pkgDir, "review.prompt.md"), "# Review");
        var promptsDir = Path.Combine(pkgDir, ".apm", "prompts");
        Directory.CreateDirectory(promptsDir);
        File.WriteAllText(Path.Combine(promptsDir, "lint.prompt.md"), "# Lint");

        var pkg = CreatePackage();
        var info = new PackageInfo(pkg, pkgDir);
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var result = _sut.IntegratePackagePrompts(info, projectRoot);

        result.FilesIntegrated.Should().Be(2);
        result.TargetPaths.Should().HaveCount(2);
    }

    #endregion

    #region SyncIntegration

    [Fact]
    public void SyncIntegration_RemovesApmManagedFiles()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        var promptsDir = Path.Combine(projectRoot, ".github", "prompts");
        Directory.CreateDirectory(promptsDir);
        File.WriteAllText(Path.Combine(promptsDir, "review-apm.prompt.md"), "managed");
        File.WriteAllText(Path.Combine(promptsDir, "custom.prompt.md"), "user file");

        var apmPkg = new ApmPackage { Name = "test" };
        var stats = _sut.SyncIntegration(apmPkg, projectRoot);

        stats["files_removed"].Should().Be(1);
        File.Exists(Path.Combine(promptsDir, "custom.prompt.md")).Should().BeTrue();
    }

    [Fact]
    public void SyncIntegration_NoPromptsDir_ReturnsZero()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var apmPkg = new ApmPackage { Name = "test" };
        var stats = _sut.SyncIntegration(apmPkg, projectRoot);

        stats["files_removed"].Should().Be(0);
    }

    #endregion

    #region UpdateGitignoreForIntegratedPrompts

    [Fact]
    public void UpdateGitignore_AddsPatternToNewFile()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var result = _sut.UpdateGitignoreForIntegratedPrompts(projectRoot);

        result.Should().BeTrue();
        var content = File.ReadAllText(Path.Combine(projectRoot, ".gitignore"));
        content.Should().Contain(".github/prompts/*-apm.prompt.md");
    }

    [Fact]
    public void UpdateGitignore_SkipsIfAlreadyPresent()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);
        File.WriteAllText(Path.Combine(projectRoot, ".gitignore"),
            "# APM\n.github/prompts/*-apm.prompt.md\n");

        var result = _sut.UpdateGitignoreForIntegratedPrompts(projectRoot);

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
    public void CopyPrompt_PreservesExistingFrontmatter()
    {
        var sourceDir = CreatePackageDir("source");
        var source = Path.Combine(sourceDir, "test.prompt.md");
        var content = "---\ntitle: My Prompt\ndescription: A test prompt\n---\n\n# Test Prompt\n\nSome prompt content.";
        File.WriteAllText(source, content);

        var targetDir = Path.Combine(_tempDir, "target");
        Directory.CreateDirectory(targetDir);
        var target = Path.Combine(targetDir, "test-apm.prompt.md");

        _sut.CopyPrompt(source, target);

        var result = File.ReadAllText(target);
        result.Should().Be(content);
        result.Should().NotContain("apm:");
    }

    [Fact]
    public void IntegratePackagePrompts_CopiesVerbatim_NoApmMetadata()
    {
        var pkgDir = CreatePackageDir();
        var sourceContent = "# Test Content\n\nSome content here.";
        File.WriteAllText(Path.Combine(pkgDir, "test.prompt.md"), sourceContent);

        var pkg = CreatePackage();
        var info = new PackageInfo(pkg, pkgDir);
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var result = _sut.IntegratePackagePrompts(info, projectRoot);

        result.FilesIntegrated.Should().Be(1);

        var targetFile = Path.Combine(projectRoot, ".github", "prompts", "test-apm.prompt.md");
        var content = File.ReadAllText(targetFile);
        content.Should().Be(sourceContent);
        content.Should().NotContain("apm:");
        content.Should().NotContain("version:");
    }

    #endregion

    #region SuffixPatternEdgeCases

    [Theory]
    [InlineData("design-review.prompt.md", "design-review-apm.prompt.md")]
    [InlineData("accessibility-audit-wcag.prompt.md", "accessibility-audit-wcag-apm.prompt.md")]
    [InlineData("my_custom-workflow.prompt.md", "my_custom-workflow-apm.prompt.md")]
    public void GetTargetFilename_VariousNames_AddsApmSuffix(string input, string expected)
    {
        _sut.GetTargetFilename(input, "pkg").Should().Be(expected);
    }

    #endregion
}

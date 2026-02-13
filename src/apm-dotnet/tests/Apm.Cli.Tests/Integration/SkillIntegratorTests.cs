using Apm.Cli.Integration;
using Apm.Cli.Models;
using Apm.Cli.Primitives;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Integration;

public class SkillNameUtilsTests
{
    #region ToHyphenCase

    [Theory]
    [InlineData("myPackage", "my-package")]
    [InlineData("my_package", "my-package")]
    [InlineData("my package", "my-package")]
    [InlineData("owner/repo-name", "repo-name")]
    [InlineData("UPPERCASE", "uppercase")]
    [InlineData("camelCaseWord", "camel-case-word")]
    public void ToHyphenCase_ConvertsCorrectly(string input, string expected)
    {
        SkillNameUtils.ToHyphenCase(input).Should().Be(expected);
    }

    [Fact]
    public void ToHyphenCase_TruncatesAt64Characters()
    {
        var longName = new string('a', 100);
        SkillNameUtils.ToHyphenCase(longName).Length.Should().BeLessThanOrEqualTo(64);
    }

    [Fact]
    public void ToHyphenCase_RemovesInvalidCharacters()
    {
        SkillNameUtils.ToHyphenCase("pkg@1.0!").Should().Be("pkg10");
    }

    [Fact]
    public void ToHyphenCase_RemovesConsecutiveHyphens()
    {
        SkillNameUtils.ToHyphenCase("a--b").Should().Be("a-b");
    }

    #endregion

    #region ValidateSkillName

    [Fact]
    public void ValidateSkillName_ValidName_ReturnsTrue()
    {
        var (isValid, _) = SkillNameUtils.ValidateSkillName("my-skill-1");
        isValid.Should().BeTrue();
    }

    [Fact]
    public void ValidateSkillName_EmptyName_ReturnsFalse()
    {
        var (isValid, error) = SkillNameUtils.ValidateSkillName("");
        isValid.Should().BeFalse();
        error.Should().Contain("empty");
    }

    [Fact]
    public void ValidateSkillName_TooLong_ReturnsFalse()
    {
        var (isValid, error) = SkillNameUtils.ValidateSkillName(new string('a', 65));
        isValid.Should().BeFalse();
        error.Should().Contain("64");
    }

    [Fact]
    public void ValidateSkillName_ConsecutiveHyphens_ReturnsFalse()
    {
        var (isValid, error) = SkillNameUtils.ValidateSkillName("my--skill");
        isValid.Should().BeFalse();
        error.Should().Contain("consecutive");
    }

    [Fact]
    public void ValidateSkillName_StartsWithHyphen_ReturnsFalse()
    {
        var (isValid, _) = SkillNameUtils.ValidateSkillName("-skill");
        isValid.Should().BeFalse();
    }

    [Fact]
    public void ValidateSkillName_EndsWithHyphen_ReturnsFalse()
    {
        var (isValid, _) = SkillNameUtils.ValidateSkillName("skill-");
        isValid.Should().BeFalse();
    }

    [Fact]
    public void ValidateSkillName_Uppercase_ReturnsFalse()
    {
        var (isValid, error) = SkillNameUtils.ValidateSkillName("MySkill");
        isValid.Should().BeFalse();
        error.Should().Contain("lowercase");
    }

    [Fact]
    public void ValidateSkillName_Underscore_ReturnsFalse()
    {
        var (isValid, error) = SkillNameUtils.ValidateSkillName("my_skill");
        isValid.Should().BeFalse();
        error.Should().Contain("underscore");
    }

    [Fact]
    public void ValidateSkillName_Spaces_ReturnsFalse()
    {
        var (isValid, error) = SkillNameUtils.ValidateSkillName("my skill");
        isValid.Should().BeFalse();
        error.Should().Contain("space");
    }

    #endregion

    #region NormalizeSkillName

    [Fact]
    public void NormalizeSkillName_DelegatesToToHyphenCase()
    {
        SkillNameUtils.NormalizeSkillName("MyPackage").Should().Be("my-package");
    }

    #endregion

    #region GetEffectiveType

    [Fact]
    public void GetEffectiveType_ExplicitType_ReturnsExplicitType()
    {
        var pkg = new ApmPackage { Name = "test", Version = "1.0.0", Type = PackageContentType.Skill };
        var info = new PackageInfo(pkg, "/path");

        SkillNameUtils.GetEffectiveType(info).Should().Be(PackageContentType.Skill);
    }

    [Fact]
    public void GetEffectiveType_ClaudeSkillPackageType_ReturnsSkill()
    {
        var pkg = new ApmPackage { Name = "test", Version = "1.0.0" };
        var info = new PackageInfo(pkg, "/path") { PackageTypeResult = PackageType.ClaudeSkill };

        SkillNameUtils.GetEffectiveType(info).Should().Be(PackageContentType.Skill);
    }

    [Fact]
    public void GetEffectiveType_NoTypeInfo_DefaultsToInstructions()
    {
        var pkg = new ApmPackage { Name = "test", Version = "1.0.0" };
        var info = new PackageInfo(pkg, "/path");

        SkillNameUtils.GetEffectiveType(info).Should().Be(PackageContentType.Instructions);
    }

    #endregion

    #region ShouldInstallSkill / ShouldCompileInstructions

    [Fact]
    public void ShouldInstallSkill_SkillType_ReturnsTrue()
    {
        var pkg = new ApmPackage { Name = "test", Version = "1.0.0", Type = PackageContentType.Skill };
        var info = new PackageInfo(pkg, "/path");

        SkillNameUtils.ShouldInstallSkill(info).Should().BeTrue();
    }

    [Fact]
    public void ShouldInstallSkill_InstructionsType_ReturnsFalse()
    {
        var pkg = new ApmPackage { Name = "test", Version = "1.0.0", Type = PackageContentType.Instructions };
        var info = new PackageInfo(pkg, "/path");

        SkillNameUtils.ShouldInstallSkill(info).Should().BeFalse();
    }

    [Fact]
    public void ShouldCompileInstructions_InstructionsType_ReturnsTrue()
    {
        var pkg = new ApmPackage { Name = "test", Version = "1.0.0", Type = PackageContentType.Instructions };
        var info = new PackageInfo(pkg, "/path");

        SkillNameUtils.ShouldCompileInstructions(info).Should().BeTrue();
    }

    [Fact]
    public void ShouldCompileInstructions_HybridType_ReturnsTrue()
    {
        var pkg = new ApmPackage { Name = "test", Version = "1.0.0", Type = PackageContentType.Hybrid };
        var info = new PackageInfo(pkg, "/path");

        SkillNameUtils.ShouldCompileInstructions(info).Should().BeTrue();
    }

    #endregion
}

public class SkillIntegratorTests : IDisposable
{
    private readonly SkillIntegrator _sut = new();
    private readonly string _tempDir;

    public SkillIntegratorTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm_skill_test_{Guid.NewGuid()}");
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    private static ApmPackage CreatePackage(string name = "test-pkg", PackageContentType? type = null) =>
        new() { Name = name, Version = "1.0.0", Type = type };

    private string CreatePackageDir(string name = "test-pkg")
    {
        var dir = Path.Combine(_tempDir, "packages", name);
        Directory.CreateDirectory(dir);
        return dir;
    }

    #region FindInstructionFiles

    [Fact]
    public void FindInstructionFiles_WithFiles_FindsThem()
    {
        var pkgDir = CreatePackageDir();
        var instDir = Path.Combine(pkgDir, ".apm", "instructions");
        Directory.CreateDirectory(instDir);
        File.WriteAllText(Path.Combine(instDir, "coding.instructions.md"), "# Coding");

        var results = _sut.FindInstructionFiles(pkgDir);

        results.Should().HaveCount(1);
    }

    [Fact]
    public void FindInstructionFiles_NoDirectory_ReturnsEmpty()
    {
        var pkgDir = CreatePackageDir();
        _sut.FindInstructionFiles(pkgDir).Should().BeEmpty();
    }

    #endregion

    #region FindContextFiles

    [Fact]
    public void FindContextFiles_ContextDir_FindsFiles()
    {
        var pkgDir = CreatePackageDir();
        var contextDir = Path.Combine(pkgDir, ".apm", "context");
        Directory.CreateDirectory(contextDir);
        File.WriteAllText(Path.Combine(contextDir, "api.context.md"), "# API");

        var results = _sut.FindContextFiles(pkgDir);

        results.Should().HaveCount(1);
    }

    [Fact]
    public void FindContextFiles_MemoryDir_FindsFiles()
    {
        var pkgDir = CreatePackageDir();
        var memoryDir = Path.Combine(pkgDir, ".apm", "memory");
        Directory.CreateDirectory(memoryDir);
        File.WriteAllText(Path.Combine(memoryDir, "arch.memory.md"), "# Arch");

        var results = _sut.FindContextFiles(pkgDir);

        results.Should().HaveCount(1);
    }

    #endregion

    #region ExtractKeywords

    [Fact]
    public void ExtractKeywords_ExtractsFromFilenames()
    {
        var files = new List<string> { "code-review.instructions.md", "testing_utils.md" };

        var keywords = _sut.ExtractKeywords(files);

        keywords.Should().Contain("code");
        keywords.Should().Contain("review");
        keywords.Should().Contain("testing");
        keywords.Should().Contain("utils");
    }

    [Fact]
    public void ExtractKeywords_IgnoresShortWords()
    {
        var files = new List<string> { "a-do.instructions.md" };

        var keywords = _sut.ExtractKeywords(files);

        keywords.Should().NotContain("a");
        keywords.Should().NotContain("do");
    }

    #endregion

    #region CopyPrimitivesToSkill

    [Fact]
    public void CopyPrimitivesToSkill_CopiesFilesToSubdirs()
    {
        var pkgDir = CreatePackageDir();
        var instDir = Path.Combine(pkgDir, ".apm", "instructions");
        Directory.CreateDirectory(instDir);
        var instrFile = Path.Combine(instDir, "coding.instructions.md");
        File.WriteAllText(instrFile, "# Coding standards");

        var skillDir = Path.Combine(_tempDir, "skill-output");
        Directory.CreateDirectory(skillDir);

        var primitives = new Dictionary<string, List<string>>
        {
            ["instructions"] = [instrFile]
        };

        var copied = _sut.CopyPrimitivesToSkill(primitives, skillDir);

        copied.Should().Be(1);
        File.Exists(Path.Combine(skillDir, "instructions", "coding.instructions.md")).Should().BeTrue();
    }

    [Fact]
    public void CopyPrimitivesToSkill_SkipsEmptyLists()
    {
        var skillDir = Path.Combine(_tempDir, "skill-output");
        Directory.CreateDirectory(skillDir);

        var primitives = new Dictionary<string, List<string>>
        {
            ["instructions"] = []
        };

        var copied = _sut.CopyPrimitivesToSkill(primitives, skillDir);

        copied.Should().Be(0);
    }

    #endregion

    #region IntegratePackageSkill

    [Fact]
    public void IntegratePackageSkill_InstructionsType_SkipsSkill()
    {
        var pkgDir = CreatePackageDir();
        var pkg = CreatePackage(type: PackageContentType.Instructions);
        var info = new PackageInfo(pkg, pkgDir);
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var result = _sut.IntegratePackageSkill(info, projectRoot);

        result.SkillSkipped.Should().BeTrue();
        result.SkillCreated.Should().BeFalse();
    }

    [Fact]
    public void IntegratePackageSkill_SkillType_WithInstructions_CreatesSkill()
    {
        var pkgDir = CreatePackageDir();
        var instDir = Path.Combine(pkgDir, ".apm", "instructions");
        Directory.CreateDirectory(instDir);
        File.WriteAllText(Path.Combine(instDir, "coding.instructions.md"), "# Coding standards");

        var pkg = CreatePackage(type: PackageContentType.Skill);
        var info = new PackageInfo(pkg, pkgDir);
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var result = _sut.IntegratePackageSkill(info, projectRoot);

        result.SkillCreated.Should().BeTrue();
        result.SkillPath.Should().NotBeNull();
        File.Exists(result.SkillPath!).Should().BeTrue();
    }

    [Fact]
    public void IntegratePackageSkill_NoPrimitives_SkipsSkill()
    {
        var pkgDir = CreatePackageDir();
        var pkg = CreatePackage(type: PackageContentType.Skill);
        var info = new PackageInfo(pkg, pkgDir);
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var result = _sut.IntegratePackageSkill(info, projectRoot);

        result.SkillSkipped.Should().BeTrue();
    }

    [Fact]
    public void IntegratePackageSkill_NativeSkillMd_CopiesDirectly()
    {
        var pkgDir = CreatePackageDir("native-skill");
        File.WriteAllText(Path.Combine(pkgDir, "SKILL.md"), "---\nname: native\n---\n# Native Skill");
        var instDir = Path.Combine(pkgDir, "instructions");
        Directory.CreateDirectory(instDir);
        File.WriteAllText(Path.Combine(instDir, "guide.md"), "# Guide");

        var pkg = CreatePackage("native-skill", type: PackageContentType.Skill);
        var info = new PackageInfo(pkg, pkgDir);
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var result = _sut.IntegratePackageSkill(info, projectRoot);

        result.SkillCreated.Should().BeTrue();
        result.SkillPath.Should().Contain("native-skill");
    }

    [Fact]
    public void IntegratePackageSkill_ClaudeDir_SyncsToClaudeSkills()
    {
        var pkgDir = CreatePackageDir();
        var instDir = Path.Combine(pkgDir, ".apm", "instructions");
        Directory.CreateDirectory(instDir);
        File.WriteAllText(Path.Combine(instDir, "coding.instructions.md"), "# Standards");

        var pkg = CreatePackage(type: PackageContentType.Skill);
        var info = new PackageInfo(pkg, pkgDir);
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(Path.Combine(projectRoot, ".claude"));

        var result = _sut.IntegratePackageSkill(info, projectRoot);

        result.SkillCreated.Should().BeTrue();
        var claudeSkillDir = Path.Combine(projectRoot, ".claude", "skills", "test-pkg");
        Directory.Exists(claudeSkillDir).Should().BeTrue();
    }

    #endregion

    #region GenerateDiscoveryDescription

    [Fact]
    public void GenerateDiscoveryDescription_IncludesKeywords()
    {
        var pkg = CreatePackage();
        pkg.Description = "Code quality tools";
        var info = new PackageInfo(pkg, "/path");

        var primitives = new Dictionary<string, List<string>>
        {
            ["instructions"] = ["testing-utils.instructions.md"]
        };

        var desc = _sut.GenerateDiscoveryDescription(info, primitives);

        desc.Should().Contain("Code quality tools");
        desc.Should().Contain("testing");
    }

    [Fact]
    public void GenerateDiscoveryDescription_NoDescription_UsesFallback()
    {
        var pkg = CreatePackage("my-pkg");
        var info = new PackageInfo(pkg, "/path");

        var primitives = new Dictionary<string, List<string>>
        {
            ["instructions"] = ["short.instructions.md"]
        };

        var desc = _sut.GenerateDiscoveryDescription(info, primitives);

        desc.Should().Contain("my-pkg");
    }

    [Fact]
    public void GenerateDiscoveryDescription_TruncatesAt1024()
    {
        var pkg = CreatePackage();
        pkg.Description = new string('x', 1100);
        var info = new PackageInfo(pkg, "/path");

        var primitives = new Dictionary<string, List<string>>();

        var desc = _sut.GenerateDiscoveryDescription(info, primitives);

        desc.Length.Should().BeLessThanOrEqualTo(1024);
    }

    #endregion

    #region SyncIntegration

    [Fact]
    public void SyncIntegration_NoSkillsDir_ReturnsZero()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var apmPkg = new ApmPackage { Name = "test" };
        var stats = _sut.SyncIntegration(apmPkg, projectRoot);

        stats["files_removed"].Should().Be(0);
    }

    [Fact]
    public void SyncIntegration_RemovesOrphanedSkillDirectories()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        var skillDir = Path.Combine(projectRoot, ".github", "skills", "mcp-builder");
        Directory.CreateDirectory(skillDir);
        File.WriteAllText(Path.Combine(skillDir, "SKILL.md"), "---\nname: mcp-builder\n---\n# MCP Builder");

        // No dependencies installed — skill is orphaned
        var apmPkg = new ApmPackage { Name = "test" };
        var stats = _sut.SyncIntegration(apmPkg, projectRoot);

        stats["files_removed"].Should().Be(1);
        Directory.Exists(skillDir).Should().BeFalse();
    }

    #endregion

    #region IntegratePackageSkill_AdvancedScenarios

    [Fact]
    public void IntegratePackageSkill_GeneratedSkillMd_HasRequiredFrontmatterFields()
    {
        var pkgDir = CreatePackageDir();
        var instDir = Path.Combine(pkgDir, ".apm", "instructions");
        Directory.CreateDirectory(instDir);
        File.WriteAllText(Path.Combine(instDir, "coding.instructions.md"), "# Coding");

        var pkg = CreatePackage("my-package", type: PackageContentType.Hybrid);
        pkg.Description = "A test package";
        var info = new PackageInfo(pkg, pkgDir)
        {
            ResolvedReference = new ResolvedReference("main", GitReferenceType.Branch, "def456", "main"),
            InstalledAt = "2024-11-13T10:00:00"
        };
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var result = _sut.IntegratePackageSkill(info, projectRoot);

        result.SkillCreated.Should().BeTrue();

        var content = File.ReadAllText(result.SkillPath!);
        content.Should().Contain("name:");
        content.Should().Contain("description:");
        content.Should().Contain("metadata:");
        content.Should().Contain("apm_package:");
        content.Should().Contain("apm_version:");
        content.Should().Contain("apm_commit:");
        content.Should().Contain("apm_installed_at:");
        content.Should().Contain("apm_content_hash:");
    }

    [Fact]
    public void IntegratePackageSkill_UpdatesWhenVersionChanges()
    {
        var pkgDir = CreatePackageDir();
        var instDir = Path.Combine(pkgDir, ".apm", "instructions");
        Directory.CreateDirectory(instDir);
        File.WriteAllText(Path.Combine(instDir, "coding.instructions.md"), "# Coding");

        var projectRoot = Path.Combine(_tempDir, "project");
        var skillDir = Path.Combine(projectRoot, ".github", "skills", Path.GetFileName(pkgDir));
        Directory.CreateDirectory(skillDir);

        // Create existing SKILL.md with old version
        File.WriteAllText(Path.Combine(skillDir, "SKILL.md"),
            "---\nname: test-pkg\ndescription: Old\nmetadata:\n  apm_package: test-pkg@1.0.0\n  apm_version: '1.0.0'\n  apm_commit: abc123\n  apm_installed_at: '2024-01-01'\n  apm_content_hash: oldhash\n---\n# Old content");

        var pkg = CreatePackage(type: PackageContentType.Hybrid);
        pkg.Version = "2.0.0";
        var info = new PackageInfo(pkg, pkgDir)
        {
            ResolvedReference = new ResolvedReference("main", GitReferenceType.Branch, "abc123", "main"),
            InstalledAt = "2024-11-13T10:00:00"
        };

        var result = _sut.IntegratePackageSkill(info, projectRoot);

        result.SkillUpdated.Should().BeTrue();
        result.SkillCreated.Should().BeFalse();
        result.SkillSkipped.Should().BeFalse();
    }

    [Fact]
    public void IntegratePackageSkill_SkipsWhenUnchanged()
    {
        var pkgDir = CreatePackageDir();
        var instDir = Path.Combine(pkgDir, ".apm", "instructions");
        Directory.CreateDirectory(instDir);
        File.WriteAllText(Path.Combine(instDir, "coding.instructions.md"), "# Coding");

        var projectRoot = Path.Combine(_tempDir, "project");
        var skillDir = Path.Combine(projectRoot, ".github", "skills", Path.GetFileName(pkgDir));
        Directory.CreateDirectory(skillDir);

        // Create existing SKILL.md with same version and commit
        File.WriteAllText(Path.Combine(skillDir, "SKILL.md"),
            "---\nname: test-pkg\ndescription: Old\nmetadata:\n  apm_package: test-pkg@1.0.0\n  apm_version: '1.0.0'\n  apm_commit: abc123\n  apm_installed_at: '2024-01-01'\n  apm_content_hash: somehash\n---\n# Old content");

        var pkg = CreatePackage(type: PackageContentType.Hybrid);
        var info = new PackageInfo(pkg, pkgDir)
        {
            ResolvedReference = new ResolvedReference("main", GitReferenceType.Branch, "abc123", "main"),
            InstalledAt = "2024-11-13T10:00:00"
        };

        var result = _sut.IntegratePackageSkill(info, projectRoot);

        result.SkillSkipped.Should().BeTrue();
        result.SkillCreated.Should().BeFalse();
        result.SkillUpdated.Should().BeFalse();
    }

    [Fact]
    public void IntegratePackageSkill_IncludesInstructionsSection()
    {
        var pkgDir = CreatePackageDir();
        var instDir = Path.Combine(pkgDir, ".apm", "instructions");
        Directory.CreateDirectory(instDir);
        File.WriteAllText(Path.Combine(instDir, "coding.instructions.md"), "Follow coding standards");

        var pkg = CreatePackage(type: PackageContentType.Hybrid);
        var info = new PackageInfo(pkg, pkgDir);
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var result = _sut.IntegratePackageSkill(info, projectRoot);

        result.SkillCreated.Should().BeTrue();
        var content = File.ReadAllText(result.SkillPath!);
        content.Should().Contain("What's Included");
        content.Should().Contain("instructions/");
    }

    [Fact]
    public void IntegratePackageSkill_CopiesPrimitivesToSubdirectories()
    {
        var pkgDir = CreatePackageDir();
        var instDir = Path.Combine(pkgDir, ".apm", "instructions");
        Directory.CreateDirectory(instDir);
        File.WriteAllText(Path.Combine(instDir, "coding.instructions.md"), "# Coding Standards Content");

        var pkg = CreatePackage(type: PackageContentType.Hybrid);
        var info = new PackageInfo(pkg, pkgDir);
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        _sut.IntegratePackageSkill(info, projectRoot);

        var skillDir = Path.Combine(projectRoot, ".github", "skills", Path.GetFileName(pkgDir));
        var copiedFile = Path.Combine(skillDir, "instructions", "coding.instructions.md");
        File.Exists(copiedFile).Should().BeTrue();
        File.ReadAllText(copiedFile).Should().Contain("Coding Standards Content");
    }

    #endregion

    #region UpdateGitignoreForSkills

    [Fact]
    public void UpdateGitignoreForSkills_AddsPattern()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);
        File.WriteAllText(Path.Combine(projectRoot, ".gitignore"), "# Existing content\napm_modules/\n");

        var result = _sut.UpdateGitignoreForSkills(projectRoot);

        result.Should().BeTrue();
        var content = File.ReadAllText(Path.Combine(projectRoot, ".gitignore"));
        content.Should().Contain(".github/skills/*-apm/");
    }

    [Fact]
    public void UpdateGitignoreForSkills_SkipsIfPatternExists()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);
        File.WriteAllText(Path.Combine(projectRoot, ".gitignore"), ".github/skills/*-apm/\n# APM-generated skills\n");

        var result = _sut.UpdateGitignoreForSkills(projectRoot);

        result.Should().BeFalse();
    }

    [Fact]
    public void UpdateGitignoreForSkills_CreatesFileIfMissing()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(projectRoot);

        var result = _sut.UpdateGitignoreForSkills(projectRoot);

        result.Should().BeTrue();
        File.Exists(Path.Combine(projectRoot, ".gitignore")).Should().BeTrue();
        File.ReadAllText(Path.Combine(projectRoot, ".gitignore")).Should().Contain(".github/skills/*-apm/");
    }

    #endregion

    #region ShouldIntegrate

    [Fact]
    public void ShouldIntegrate_AlwaysReturnsTrue()
    {
        _sut.ShouldIntegrate(_tempDir).Should().BeTrue();
    }

    #endregion
}

public class SkillTransformerTests : IDisposable
{
    private readonly string _tempDir;

    public SkillTransformerTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm_transformer_test_{Guid.NewGuid()}");
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Theory]
    [InlineData("Brand Guidelines", "brand-guidelines")]
    [InlineData("brand_guidelines", "brand-guidelines")]
    [InlineData("camelCase", "camel-case")]
    public void ToHyphenCase_ConvertsCorrectly(string input, string expected)
    {
        SkillTransformer.ToHyphenCase(input).Should().Be(expected);
    }

    [Fact]
    public void TransformToAgent_CreatesAgentFile()
    {
        var transformer = new SkillTransformer();
        var skill = new Skill
        {
            Name = "Code Reviewer",
            Description = "Reviews code changes",
            Content = "Review all code carefully."
        };

        var agentPath = transformer.TransformToAgent(skill, _tempDir);

        agentPath.Should().NotBeNull();
        File.Exists(agentPath!).Should().BeTrue();
        var content = File.ReadAllText(agentPath!);
        content.Should().Contain("name: Code Reviewer");
        content.Should().Contain("description: Reviews code changes");
        content.Should().Contain("Review all code carefully.");
    }

    [Fact]
    public void TransformToAgent_DryRun_DoesNotCreateFile()
    {
        var transformer = new SkillTransformer();
        var skill = new Skill
        {
            Name = "Test Skill",
            Description = "Testing",
            Content = "Content"
        };

        var agentPath = transformer.TransformToAgent(skill, _tempDir, dryRun: true);

        agentPath.Should().NotBeNull();
        File.Exists(agentPath!).Should().BeFalse();
    }

    [Fact]
    public void TransformToAgent_WithSource_IncludesSourceComment()
    {
        var transformer = new SkillTransformer();
        var skill = new Skill
        {
            Name = "Remote Skill",
            Description = "From GitHub",
            Content = "Do stuff.",
            Source = "owner/repo"
        };

        var agentPath = transformer.TransformToAgent(skill, _tempDir);
        var content = File.ReadAllText(agentPath!);

        content.Should().Contain("<!-- Source: owner/repo -->");
    }

    [Fact]
    public void TransformToAgent_LocalSource_NoSourceComment()
    {
        var transformer = new SkillTransformer();
        var skill = new Skill
        {
            Name = "Local Skill",
            Description = "Local",
            Content = "Do stuff.",
            Source = "local"
        };

        var agentPath = transformer.TransformToAgent(skill, _tempDir);
        var content = File.ReadAllText(agentPath!);

        content.Should().NotContain("<!-- Source:");
    }

    [Fact]
    public void GetAgentName_ReturnsHyphenCase()
    {
        var transformer = new SkillTransformer();
        var skill = new Skill { Name = "Code Reviewer" };

        transformer.GetAgentName(skill).Should().Be("code-reviewer");
    }

    [Fact]
    public void TransformToAgent_CreatesDirectory()
    {
        var transformer = new SkillTransformer();
        var skill = new Skill
        {
            Name = "Test Skill",
            Description = "A test skill",
            Content = "# Test Skill\n\nThis is a test skill."
        };

        var agentPath = transformer.TransformToAgent(skill, _tempDir);

        agentPath.Should().NotBeNull();
        Directory.Exists(Path.Combine(_tempDir, ".github", "agents")).Should().BeTrue();
    }

    [Fact]
    public void TransformToAgent_ComplexSkillName_NormalizesCorrectly()
    {
        var transformer = new SkillTransformer();
        var skill = new Skill
        {
            Name = "My Awesome SKILL v2",
            Description = "An awesome skill",
            Content = "# Content"
        };

        var agentPath = transformer.TransformToAgent(skill, _tempDir);

        agentPath.Should().NotBeNull();
        Path.GetFileName(agentPath!).Should().Be("my-awesome-skill-v2.agent.md");
    }

    [Fact]
    public void ToHyphenCase_BasicLowercase_Unchanged()
    {
        SkillTransformer.ToHyphenCase("mypackage").Should().Be("mypackage");
    }

    [Fact]
    public void ToHyphenCase_StripLeadingTrailingHyphens()
    {
        SkillTransformer.ToHyphenCase("-mypackage-").Should().Be("mypackage");
    }
}

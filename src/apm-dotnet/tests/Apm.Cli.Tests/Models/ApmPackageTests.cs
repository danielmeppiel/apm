using Apm.Cli.Models;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Models;

public class ApmPackageFromYmlTests : IDisposable
{
    private readonly List<string> _tempFiles = [];

    public void Dispose()
    {
        foreach (var f in _tempFiles)
        {
            try { File.Delete(f); } catch { }
        }
    }

    private string CreateTempYaml(string content)
    {
        var path = Path.Combine(Path.GetTempPath(), $"apm_test_{Guid.NewGuid()}.yml");
        File.WriteAllText(path, content);
        _tempFiles.Add(path);
        return path;
    }

    [Fact]
    public void FromApmYml_Minimal_ParsesCorrectly()
    {
        var path = CreateTempYaml("""
            name: test-package
            version: 1.0.0
            """);

        var pkg = ApmPackage.FromApmYml(path);
        pkg.Name.Should().Be("test-package");
        pkg.Version.Should().Be("1.0.0");
        pkg.Description.Should().BeNull();
        pkg.Author.Should().BeNull();
        pkg.Dependencies.Should().BeNull();
    }

    [Fact]
    public void FromApmYml_Complete_ParsesAllFields()
    {
        var path = CreateTempYaml("""
            name: test-package
            version: 1.0.0
            description: A test package
            author: Test Author
            license: MIT
            target: vscode
            type: instructions
            scripts:
              start: echo hello
            dependencies:
              apm:
                - user/repo#main
                - another/repo
              mcp:
                - some-mcp-server
            """);

        var pkg = ApmPackage.FromApmYml(path);
        pkg.Name.Should().Be("test-package");
        pkg.Version.Should().Be("1.0.0");
        pkg.Description.Should().Be("A test package");
        pkg.Author.Should().Be("Test Author");
        pkg.License.Should().Be("MIT");
        pkg.Target.Should().Be("vscode");
        pkg.Type.Should().Be(PackageContentType.Instructions);
        pkg.Scripts.Should().NotBeNull();
        pkg.Scripts!["start"].Should().Be("echo hello");
    }

    [Fact]
    public void FromApmYml_WithApmDependencies_ParsesDependencyReferences()
    {
        var path = CreateTempYaml("""
            name: test-package
            version: 1.0.0
            dependencies:
              apm:
                - user/repo#main
                - another/repo
            """);

        var pkg = ApmPackage.FromApmYml(path);
        var deps = pkg.GetApmDependencies();
        deps.Should().HaveCount(2);
        deps[0].RepoUrl.Should().Be("user/repo");
        deps[0].Reference.Should().Be("main");
        deps[1].RepoUrl.Should().Be("another/repo");
    }

    [Fact]
    public void FromApmYml_WithMcpDependencies_ParsesStrings()
    {
        var path = CreateTempYaml("""
            name: test-package
            version: 1.0.0
            dependencies:
              mcp:
                - mcp-server-one
                - mcp-server-two
            """);

        var pkg = ApmPackage.FromApmYml(path);
        var mcpDeps = pkg.GetMcpDependencies();
        mcpDeps.Should().HaveCount(2);
        mcpDeps.Should().Contain("mcp-server-one");
    }

    [Fact]
    public void FromApmYml_NoDependencies_ReturnsEmptyLists()
    {
        var path = CreateTempYaml("""
            name: test-package
            version: 1.0.0
            """);

        var pkg = ApmPackage.FromApmYml(path);
        pkg.GetApmDependencies().Should().BeEmpty();
        pkg.GetMcpDependencies().Should().BeEmpty();
        pkg.HasApmDependencies().Should().BeFalse();
    }

    [Fact]
    public void FromApmYml_MissingFile_ThrowsFileNotFoundException()
    {
        var act = () => ApmPackage.FromApmYml("/nonexistent/path/apm.yml");
        act.Should().Throw<FileNotFoundException>();
    }

    [Fact]
    public void FromApmYml_MissingName_ThrowsArgumentException()
    {
        var path = CreateTempYaml("""
            version: 1.0.0
            """);

        var act = () => ApmPackage.FromApmYml(path);
        act.Should().Throw<ArgumentException>().WithMessage("*Missing required field 'name'*");
    }

    [Fact]
    public void FromApmYml_MissingVersion_ThrowsArgumentException()
    {
        var path = CreateTempYaml("""
            name: test-package
            """);

        var act = () => ApmPackage.FromApmYml(path);
        act.Should().Throw<ArgumentException>().WithMessage("*Missing required field 'version'*");
    }

    [Fact]
    public void FromApmYml_InvalidYaml_ThrowsArgumentException()
    {
        var path = CreateTempYaml("{{{{invalid yaml content");

        var act = () => ApmPackage.FromApmYml(path);
        act.Should().Throw<ArgumentException>().WithMessage("*Invalid YAML*");
    }

    [Fact]
    public void FromApmYml_InvalidPackageType_ThrowsArgumentException()
    {
        var path = CreateTempYaml("""
            name: test-package
            version: 1.0.0
            type: invalid_type
            """);

        var act = () => ApmPackage.FromApmYml(path);
        act.Should().Throw<ArgumentException>().WithMessage("*Invalid 'type' field*");
    }

    [Fact]
    public void FromApmYml_SetsPackagePath()
    {
        var path = CreateTempYaml("""
            name: test-package
            version: 1.0.0
            """);

        var pkg = ApmPackage.FromApmYml(path);
        pkg.PackagePath.Should().NotBeNull();
        pkg.PackagePath.Should().Be(Path.GetDirectoryName(Path.GetFullPath(path)));
    }

    [Theory]
    [InlineData("instructions", PackageContentType.Instructions)]
    [InlineData("skill", PackageContentType.Skill)]
    [InlineData("hybrid", PackageContentType.Hybrid)]
    [InlineData("prompts", PackageContentType.Prompts)]
    public void FromApmYml_AllPackageTypes_ParsedCorrectly(string typeStr, PackageContentType expected)
    {
        var path = CreateTempYaml($"""
            name: test-package
            version: 1.0.0
            type: {typeStr}
            """);

        var pkg = ApmPackage.FromApmYml(path);
        pkg.Type.Should().Be(expected);
    }

    [Fact]
    public void HasApmDependencies_WithDeps_ReturnsTrue()
    {
        var path = CreateTempYaml("""
            name: test-package
            version: 1.0.0
            dependencies:
              apm:
                - user/repo
            """);

        var pkg = ApmPackage.FromApmYml(path);
        pkg.HasApmDependencies().Should().BeTrue();
    }

    [Fact]
    public void FromApmYml_InvalidDependencyFormat_ThrowsArgumentException()
    {
        var path = CreateTempYaml("""
            name: test-package
            version: 1.0.0
            dependencies:
              apm:
                - invalid-repo-format
            """);

        var act = () => ApmPackage.FromApmYml(path);
        act.Should().Throw<ArgumentException>().WithMessage("*Invalid APM dependency*");
    }

    [Fact]
    public void FromApmYml_McpOnlyDeps_HasApmDependenciesFalse()
    {
        var path = CreateTempYaml("""
            name: test-package
            version: 1.0.0
            dependencies:
              mcp:
                - some-mcp-server
            """);

        var pkg = ApmPackage.FromApmYml(path);
        pkg.HasApmDependencies().Should().BeFalse();
        pkg.GetMcpDependencies().Should().HaveCount(1);
    }

    [Fact]
    public void FromApmYml_MissingType_DefaultsToNull()
    {
        var path = CreateTempYaml("""
            name: test-package
            version: 1.0.0
            """);

        var pkg = ApmPackage.FromApmYml(path);
        pkg.Type.Should().BeNull();
    }

    [Fact]
    public void FromApmYml_TypeCaseInsensitive_ParsesCorrectly()
    {
        var path = CreateTempYaml("""
            name: test-package
            version: 1.0.0
            type: SKILL
            """);

        var pkg = ApmPackage.FromApmYml(path);
        pkg.Type.Should().Be(PackageContentType.Skill);
    }

    [Fact]
    public void FromApmYml_NullType_TreatedAsMissing()
    {
        var path = CreateTempYaml("""
            name: test-package
            version: "1.0.0"
            type: null
            """);

        var pkg = ApmPackage.FromApmYml(path);
        pkg.Type.Should().BeNull();
    }

    [Fact]
    public void ApmPackage_WithType_StoresType()
    {
        var pkg = new ApmPackage { Name = "test", Version = "1.0.0", Type = PackageContentType.Skill };
        pkg.Type.Should().Be(PackageContentType.Skill);
    }

    [Fact]
    public void ApmPackage_DefaultType_IsNull()
    {
        var pkg = new ApmPackage { Name = "test", Version = "1.0.0" };
        pkg.Type.Should().BeNull();
    }
}

public class ValidationResultTests
{
    [Fact]
    public void New_IsValidByDefault()
    {
        var result = new ValidationResult();
        result.IsValid.Should().BeTrue();
        result.Errors.Should().BeEmpty();
        result.Warnings.Should().BeEmpty();
    }

    [Fact]
    public void AddError_SetsInvalidAndAddsError()
    {
        var result = new ValidationResult();
        result.AddError("test error");
        result.IsValid.Should().BeFalse();
        result.Errors.Should().Contain("test error");
    }

    [Fact]
    public void AddWarning_StaysValidAndAddsWarning()
    {
        var result = new ValidationResult();
        result.AddWarning("test warning");
        result.IsValid.Should().BeTrue();
        result.Warnings.Should().Contain("test warning");
    }

    [Fact]
    public void HasIssues_WithErrors_ReturnsTrue()
    {
        var result = new ValidationResult();
        result.AddError("error");
        result.HasIssues().Should().BeTrue();
    }

    [Fact]
    public void HasIssues_WithWarningsOnly_ReturnsTrue()
    {
        var result = new ValidationResult();
        result.AddWarning("warning");
        result.HasIssues().Should().BeTrue();
    }

    [Fact]
    public void HasIssues_NoIssues_ReturnsFalse()
    {
        var result = new ValidationResult();
        result.HasIssues().Should().BeFalse();
    }

    [Fact]
    public void Summary_Valid_ContainsCheckMark()
    {
        var result = new ValidationResult();
        result.Summary().Should().Contain("✅");
    }

    [Fact]
    public void Summary_ValidWithWarnings_ContainsWarningEmoji()
    {
        var result = new ValidationResult();
        result.AddWarning("warn");
        result.Summary().Should().Contain("⚠️");
    }

    [Fact]
    public void Summary_Invalid_ContainsCrossEmoji()
    {
        var result = new ValidationResult();
        result.AddError("err");
        result.Summary().Should().Contain("❌");
    }
}

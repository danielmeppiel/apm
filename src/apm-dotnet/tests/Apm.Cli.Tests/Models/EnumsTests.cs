using Apm.Cli.Models;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Models;

public class PackageContentTypeExtensionsTests
{
    [Theory]
    [InlineData("instructions", PackageContentType.Instructions)]
    [InlineData("skill", PackageContentType.Skill)]
    [InlineData("hybrid", PackageContentType.Hybrid)]
    [InlineData("prompts", PackageContentType.Prompts)]
    public void FromString_ValidValues_ReturnsCorrectEnum(string input, PackageContentType expected)
    {
        PackageContentTypeExtensions.FromString(input).Should().Be(expected);
    }

    [Theory]
    [InlineData("INSTRUCTIONS")]
    [InlineData("Skill")]
    [InlineData("HYBRID")]
    [InlineData("Prompts")]
    [InlineData("  instructions  ")]
    public void FromString_CaseInsensitiveAndTrimmed(string input)
    {
        var act = () => PackageContentTypeExtensions.FromString(input);
        act.Should().NotThrow();
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    [InlineData(null)]
    public void FromString_EmptyOrNull_ThrowsArgumentException(string? input)
    {
        var act = () => PackageContentTypeExtensions.FromString(input!);
        act.Should().Throw<ArgumentException>().WithMessage("*cannot be empty*");
    }

    [Theory]
    [InlineData("invalid")]
    [InlineData("module")]
    [InlineData("command")]
    public void FromString_InvalidValue_ThrowsArgumentException(string input)
    {
        var act = () => PackageContentTypeExtensions.FromString(input);
        act.Should().Throw<ArgumentException>().WithMessage("*Invalid package type*");
    }

    [Fact]
    public void FromString_Typo_ErrorListsValidTypes()
    {
        var ex = Assert.Throws<ArgumentException>(() => PackageContentTypeExtensions.FromString("instruction"));
        ex.Message.Should().Contain("instructions");
        ex.Message.Should().Contain("skill");
        ex.Message.Should().Contain("hybrid");
        ex.Message.Should().Contain("prompts");
    }

    [Theory]
    [InlineData(PackageContentType.Instructions, "instructions")]
    [InlineData(PackageContentType.Skill, "skill")]
    [InlineData(PackageContentType.Hybrid, "hybrid")]
    [InlineData(PackageContentType.Prompts, "prompts")]
    public void ToYamlString_AllValues_ReturnsCorrectString(PackageContentType type, string expected)
    {
        type.ToYamlString().Should().Be(expected);
    }

    [Fact]
    public void ToYamlString_InvalidEnum_ThrowsArgumentOutOfRange()
    {
        var invalid = (PackageContentType)999;
        var act = () => invalid.ToYamlString();
        act.Should().Throw<ArgumentOutOfRangeException>();
    }

    [Fact]
    public void RoundTrip_AllValues_PreserveIdentity()
    {
        foreach (var type in Enum.GetValues<PackageContentType>())
        {
            var yaml = type.ToYamlString();
            var parsed = PackageContentTypeExtensions.FromString(yaml);
            parsed.Should().Be(type);
        }
    }
}

public class GitReferenceTypeTests
{
    [Fact]
    public void GitReferenceType_HasExpectedValues()
    {
        Enum.GetValues<GitReferenceType>().Should().HaveCount(3);
        Enum.IsDefined(GitReferenceType.Branch).Should().BeTrue();
        Enum.IsDefined(GitReferenceType.Tag).Should().BeTrue();
        Enum.IsDefined(GitReferenceType.Commit).Should().BeTrue();
    }
}

public class PackageTypeTests
{
    [Fact]
    public void PackageType_HasExpectedValues()
    {
        Enum.GetValues<PackageType>().Should().HaveCount(4);
        Enum.IsDefined(PackageType.ApmPackage).Should().BeTrue();
        Enum.IsDefined(PackageType.ClaudeSkill).Should().BeTrue();
        Enum.IsDefined(PackageType.Hybrid).Should().BeTrue();
        Enum.IsDefined(PackageType.Invalid).Should().BeTrue();
    }
}

public class ValidationErrorTests
{
    [Fact]
    public void ValidationError_HasExpectedValues()
    {
        Enum.GetValues<ValidationError>().Should().HaveCount(8);
    }
}

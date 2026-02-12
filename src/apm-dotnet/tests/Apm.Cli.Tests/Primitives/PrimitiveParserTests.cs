using Apm.Cli.Primitives;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Primitives;

public class PrimitiveParserFrontmatterTests
{
    [Fact]
    public void ParseFrontmatter_ExtractsMetadataAndContent()
    {
        var text = """
            ---
            description: Test description
            applyTo: "**/*.cs"
            ---
            This is the body content.
            """;

        var (metadata, content) = PrimitiveParser.ParseFrontmatter(text);

        metadata.Should().ContainKey("description");
        metadata["description"]!.ToString().Should().Be("Test description");
        metadata.Should().ContainKey("applyTo");
        content.Should().Contain("This is the body content.");
    }

    [Fact]
    public void ParseFrontmatter_ReturnsEmptyMetadata_WhenNoFrontmatter()
    {
        var text = "Just plain content without frontmatter.";

        var (metadata, content) = PrimitiveParser.ParseFrontmatter(text);

        metadata.Should().BeEmpty();
        content.Should().Be(text);
    }

    [Fact]
    public void ParseFrontmatter_HandlesInvalidYaml_GracefullyReturnsEmpty()
    {
        var text = """
            ---
            invalid: yaml: [content
            ---
            Body content here.
            """;

        var (metadata, content) = PrimitiveParser.ParseFrontmatter(text);

        metadata.Should().BeEmpty();
        content.Should().Contain("Body content here.");
    }

    [Fact]
    public void ParseFrontmatter_HandlesEmptyFrontmatter()
    {
        var text = """
            ---
            
            ---
            Content after empty frontmatter.
            """;

        var (metadata, content) = PrimitiveParser.ParseFrontmatter(text);

        metadata.Should().BeEmpty();
        content.Should().Contain("Content after empty frontmatter.");
    }
}

public class PrimitiveParserInstructionTests : IDisposable
{
    private readonly string _tempDir;

    public PrimitiveParserInstructionTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void ParsePrimitiveFile_ParsesInstructionFile()
    {
        var filePath = Path.Combine(_tempDir, "coding.instructions.md");
        File.WriteAllText(filePath, """
            ---
            description: Coding guidelines
            applyTo: "**/*.cs"
            ---
            Follow these coding guidelines.
            """);

        var result = PrimitiveParser.ParsePrimitiveFile(filePath);

        result.Should().BeOfType<Instruction>();
        var instruction = (Instruction)result;
        instruction.Name.Should().Be("coding");
        instruction.Description.Should().Be("Coding guidelines");
        instruction.ApplyTo.Should().Be("**/*.cs");
        instruction.Content.Should().Contain("Follow these coding guidelines.");
    }

    [Fact]
    public void ParsePrimitiveFile_SetsSource_WhenProvided()
    {
        var filePath = Path.Combine(_tempDir, "test.instructions.md");
        File.WriteAllText(filePath, """
            ---
            description: Test
            applyTo: "**"
            ---
            Content.
            """);

        var result = (Instruction)PrimitiveParser.ParsePrimitiveFile(filePath, "dependency:my-package");
        result.Source.Should().Be("dependency:my-package");
    }
}

public class PrimitiveParserChatmodeTests : IDisposable
{
    private readonly string _tempDir;

    public PrimitiveParserChatmodeTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void ParsePrimitiveFile_ParsesChatmodeFile()
    {
        var filePath = Path.Combine(_tempDir, "reviewer.chatmode.md");
        File.WriteAllText(filePath, """
            ---
            description: Code reviewer mode
            ---
            You are a code reviewer.
            """);

        var result = PrimitiveParser.ParsePrimitiveFile(filePath);

        result.Should().BeOfType<Chatmode>();
        var chatmode = (Chatmode)result;
        chatmode.Name.Should().Be("reviewer");
        chatmode.Description.Should().Be("Code reviewer mode");
        chatmode.Content.Should().Contain("You are a code reviewer.");
    }

    [Fact]
    public void ParsePrimitiveFile_ParsesChatmodeWithFullMetadata()
    {
        var filePath = Path.Combine(_tempDir, "code-review.chatmode.md");
        File.WriteAllText(filePath, "---\ndescription: Test chatmode for code review\nauthor: Test Author\napplyTo: \"**/*.{py,js}\"\nversion: \"1.0.0\"\n---\n\n# Code Review Assistant\n\nYou are an expert code reviewer.");

        var result = PrimitiveParser.ParsePrimitiveFile(filePath);

        result.Should().BeOfType<Chatmode>();
        var chatmode = (Chatmode)result;
        chatmode.Name.Should().Be("code-review");
        chatmode.Description.Should().Be("Test chatmode for code review");
        chatmode.Author.Should().Be("Test Author");
        chatmode.ApplyTo.Should().Be("**/*.{py,js}");
        chatmode.Version.Should().Be("1.0.0");
        chatmode.Content.Should().Contain("Code Review Assistant");
        chatmode.Validate().Should().BeEmpty();
    }

    [Fact]
    public void ParsePrimitiveFile_ParsesAgentFile_AsChatmode()
    {
        var filePath = Path.Combine(_tempDir, "helper.agent.md");
        File.WriteAllText(filePath, """
            ---
            description: Helper agent
            ---
            You are a helpful agent.
            """);

        var result = PrimitiveParser.ParsePrimitiveFile(filePath);

        result.Should().BeOfType<Chatmode>();
        var chatmode = (Chatmode)result;
        chatmode.Name.Should().Be("helper");
        chatmode.Description.Should().Be("Helper agent");
    }
}

public class PrimitiveParserContextTests : IDisposable
{
    private readonly string _tempDir;

    public PrimitiveParserContextTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void ParsePrimitiveFile_ParsesContextFile()
    {
        var filePath = Path.Combine(_tempDir, "project.context.md");
        File.WriteAllText(filePath, """
            ---
            description: Project context
            ---
            This project uses TypeScript.
            """);

        var result = PrimitiveParser.ParsePrimitiveFile(filePath);

        result.Should().BeOfType<Context>();
        var context = (Context)result;
        context.Name.Should().Be("project");
        context.Description.Should().Be("Project context");
        context.Content.Should().Contain("This project uses TypeScript.");
    }

    [Fact]
    public void ParsePrimitiveFile_ParsesMemoryFile_AsContext()
    {
        var filePath = Path.Combine(_tempDir, "notes.memory.md");
        File.WriteAllText(filePath, """
            ---
            description: Memory notes
            ---
            Remember these notes.
            """);

        var result = PrimitiveParser.ParsePrimitiveFile(filePath);

        result.Should().BeOfType<Context>();
        var context = (Context)result;
        context.Name.Should().Be("notes");
    }
}

public class PrimitiveParserSkillTests : IDisposable
{
    private readonly string _tempDir;

    public PrimitiveParserSkillTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void ParseSkillFile_ParsesSkillMd()
    {
        var filePath = Path.Combine(_tempDir, "SKILL.md");
        File.WriteAllText(filePath, """
            ---
            name: my-skill
            description: A useful skill
            ---
            Skill content here.
            """);

        var result = PrimitiveParser.ParseSkillFile(filePath);

        result.Name.Should().Be("my-skill");
        result.Description.Should().Be("A useful skill");
        result.Content.Should().Contain("Skill content here.");
    }

    [Fact]
    public void ParseSkillFile_DerivesNameFromDirectory_WhenMissing()
    {
        var subDir = Path.Combine(_tempDir, "my-package");
        Directory.CreateDirectory(subDir);
        var filePath = Path.Combine(subDir, "SKILL.md");
        File.WriteAllText(filePath, """
            ---
            description: A skill without a name
            ---
            Skill content.
            """);

        var result = PrimitiveParser.ParseSkillFile(filePath);

        result.Name.Should().Be("my-package");
    }

    [Fact]
    public void ParseSkillFile_SetsSource_WhenProvided()
    {
        var filePath = Path.Combine(_tempDir, "SKILL.md");
        File.WriteAllText(filePath, """
            ---
            name: test-skill
            description: Test
            ---
            Content.
            """);

        var result = PrimitiveParser.ParseSkillFile(filePath, "dependency:pkg");
        result.Source.Should().Be("dependency:pkg");
    }
}

public class ExtractPrimitiveNameTests
{
    [Theory]
    [InlineData("coding.instructions.md", "coding")]
    [InlineData("reviewer.chatmode.md", "reviewer")]
    [InlineData("helper.agent.md", "helper")]
    [InlineData("project.context.md", "project")]
    [InlineData("notes.memory.md", "notes")]
    [InlineData("readme.md", "readme")]
    public void ExtractPrimitiveName_StripsExtension(string fileName, string expected)
    {
        PrimitiveParser.ExtractPrimitiveName(fileName).Should().Be(expected);
    }

    [Fact]
    public void ExtractPrimitiveName_HandlesStructuredPaths()
    {
        var path = ".apm/instructions/coding.instructions.md";
        PrimitiveParser.ExtractPrimitiveName(path).Should().Be("coding");
    }

    [Fact]
    public void ExtractPrimitiveName_HandlesGitHubPaths()
    {
        var path = ".github/instructions/coding.instructions.md";
        PrimitiveParser.ExtractPrimitiveName(path).Should().Be("coding");
    }
}

public class PrimitiveParserValidationTests : IDisposable
{
    private readonly string _tempDir;

    public PrimitiveParserValidationTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void ValidatePrimitive_ReturnsErrors_ForInvalidInstruction()
    {
        var instruction = new Instruction
        {
            Name = "test",
            Description = "",
            ApplyTo = "",
            Content = ""
        };

        var errors = PrimitiveParser.ValidatePrimitive(instruction);

        errors.Should().NotBeEmpty();
        errors.Should().Contain(e => e.Contains("description"));
        errors.Should().Contain(e => e.Contains("applyTo"));
        errors.Should().Contain(e => e.Contains("Empty content"));
    }

    [Fact]
    public void ValidatePrimitive_ReturnsNoErrors_ForValidChatmode()
    {
        var chatmode = new Chatmode
        {
            Name = "test",
            Description = "Valid description",
            Content = "Valid content"
        };

        var errors = PrimitiveParser.ValidatePrimitive(chatmode);
        errors.Should().BeEmpty();
    }

    [Fact]
    public void ValidatePrimitive_ReturnsErrors_ForInvalidSkill()
    {
        var skill = new Skill
        {
            Name = "",
            Description = "",
            Content = ""
        };

        var errors = PrimitiveParser.ValidatePrimitive(skill);
        errors.Should().HaveCountGreaterThan(0);
    }

    [Fact]
    public void ValidatePrimitive_ReturnsNoErrors_ForValidInstruction()
    {
        var instruction = new Instruction
        {
            Name = "test-instruction",
            Description = "Test instruction",
            ApplyTo = "**/*.{ts,tsx}",
            Content = "# Test instruction content"
        };

        PrimitiveParser.ValidatePrimitive(instruction).Should().BeEmpty();
    }

    [Fact]
    public void ValidatePrimitive_ReturnsNoErrors_ForValidContext()
    {
        var context = new Context
        {
            Name = "test-context",
            Content = "# Test context content"
        };

        PrimitiveParser.ValidatePrimitive(context).Should().BeEmpty();
    }

    [Fact]
    public void ParsePrimitiveFile_Throws_ForUnknownFileType()
    {
        var filePath = Path.Combine(_tempDir, "unknown.txt");
        File.WriteAllText(filePath, "some content");

        var act = () => PrimitiveParser.ParsePrimitiveFile(filePath);
        act.Should().Throw<InvalidOperationException>();
    }

    [Fact]
    public void ParsePrimitiveFile_HandlesMissingFrontmatter()
    {
        var filePath = Path.Combine(_tempDir, "no-frontmatter.instructions.md");
        File.WriteAllText(filePath, "Just content, no frontmatter.");

        var result = PrimitiveParser.ParsePrimitiveFile(filePath);

        result.Should().BeOfType<Instruction>();
        var instruction = (Instruction)result;
        instruction.Description.Should().BeEmpty();
        instruction.ApplyTo.Should().BeEmpty();
        instruction.Content.Should().Contain("Just content, no frontmatter.");
    }
}

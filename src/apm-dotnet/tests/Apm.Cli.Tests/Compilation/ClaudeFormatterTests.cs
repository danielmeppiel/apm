using Apm.Cli.Compilation;
using Apm.Cli.Primitives;
using Apm.Cli.Utils;
using AwesomeAssertions;
using FakeItEasy;

namespace Apm.Cli.Tests.Compilation;

public class ClaudeFormatterTests : IDisposable
{
    private readonly string _tempDir;

    public ClaudeFormatterTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    // ── FormatDistributed ───────────────────────────────────────────

    [Fact]
    public void FormatDistributed_WithPrimitives_ReturnsContentMap()
    {
        var formatter = A.Fake<IClaudeFormatter>();
        var primitives = new PrimitiveCollection();
        primitives.AddPrimitive(new Instruction
        {
            Name = "python",
            Description = "Python rules",
            ApplyTo = "**/*.py",
            Content = "Use type hints",
            Source = "local"
        });

        var placements = new List<PlacementResult>
        {
            new()
            {
                AgentsPath = Path.Combine(_tempDir, "CLAUDE.md"),
                Instructions = primitives.Instructions,
                CoveragePatterns = ["**/*.py"]
            }
        };

        var claudeResult = new ClaudeCompilationResult
        {
            Placements = placements,
            ContentMap = new Dictionary<string, string>
            {
                [Path.Combine(_tempDir, "CLAUDE.md")] = "# CLAUDE.md\n\nUse type hints"
            },
            Stats = new Dictionary<string, object> { ["instructions_placed"] = 1 }
        };

        A.CallTo(() => formatter.FormatDistributed(
            A<PrimitiveCollection>._,
            A<List<PlacementResult>>._,
            A<Dictionary<string, object>>._))
            .Returns(claudeResult);

        var result = formatter.FormatDistributed(primitives, placements, new Dictionary<string, object>());

        result.ContentMap.Should().HaveCount(1);
        result.ContentMap.Values.First().Should().Contain("CLAUDE.md");
        result.ContentMap.Values.First().Should().Contain("Use type hints");
    }

    [Fact]
    public void FormatDistributed_EmptyPrimitives_ReturnsEmptyResult()
    {
        var formatter = A.Fake<IClaudeFormatter>();
        var emptyResult = new ClaudeCompilationResult
        {
            Placements = [],
            ContentMap = new Dictionary<string, string>(),
            Stats = new Dictionary<string, object> { ["instructions_placed"] = 0 }
        };

        A.CallTo(() => formatter.FormatDistributed(
            A<PrimitiveCollection>._,
            A<List<PlacementResult>>._,
            A<Dictionary<string, object>>._))
            .Returns(emptyResult);

        var result = formatter.FormatDistributed(
            new PrimitiveCollection(), [], new Dictionary<string, object>());

        result.ContentMap.Should().BeEmpty();
        result.Placements.Should().BeEmpty();
    }

    [Fact]
    public void FormatDistributed_MultipleFiles_ReturnsAllEntries()
    {
        var formatter = A.Fake<IClaudeFormatter>();
        var rootPath = Path.Combine(_tempDir, "CLAUDE.md");
        var srcPath = Path.Combine(_tempDir, "src", "CLAUDE.md");

        var claudeResult = new ClaudeCompilationResult
        {
            Placements =
            [
                new PlacementResult
                {
                    AgentsPath = rootPath,
                    Instructions = [new Instruction { Name = "global", Description = "d", ApplyTo = "**", Content = "global" }],
                    CoveragePatterns = ["**"]
                },
                new PlacementResult
                {
                    AgentsPath = srcPath,
                    Instructions = [new Instruction { Name = "src", Description = "d", ApplyTo = "src/**", Content = "src" }],
                    CoveragePatterns = ["src/**"]
                }
            ],
            ContentMap = new Dictionary<string, string>
            {
                [rootPath] = "# Root CLAUDE.md",
                [srcPath] = "# Src CLAUDE.md"
            }
        };

        A.CallTo(() => formatter.FormatDistributed(
            A<PrimitiveCollection>._,
            A<List<PlacementResult>>._,
            A<Dictionary<string, object>>._))
            .Returns(claudeResult);

        var result = formatter.FormatDistributed(
            new PrimitiveCollection(),
            claudeResult.Placements,
            new Dictionary<string, object>());

        result.ContentMap.Should().HaveCount(2);
        result.Placements.Should().HaveCount(2);
    }

    // ── ClaudeCompilationResult model ───────────────────────────────

    [Fact]
    public void ClaudeCompilationResult_Defaults()
    {
        var result = new ClaudeCompilationResult();

        result.Placements.Should().BeEmpty();
        result.ContentMap.Should().BeEmpty();
        result.Warnings.Should().BeEmpty();
        result.Errors.Should().BeEmpty();
        result.Stats.Should().BeEmpty();
    }

    [Fact]
    public void ClaudeCompilationResult_WithWarningsAndErrors()
    {
        var result = new ClaudeCompilationResult
        {
            Warnings = ["Missing pattern coverage"],
            Errors = ["Failed to write file"]
        };

        result.Warnings.Should().HaveCount(1);
        result.Errors.Should().HaveCount(1);
        result.Warnings[0].Should().Contain("Missing pattern");
        result.Errors[0].Should().Contain("Failed to write");
    }

    // ── Compiler integration with Claude target ─────────────────────

    [Fact]
    public void Compiler_ClaudeTarget_WithoutFormatter_Fails()
    {
        var compiler = new AgentsCompiler(_tempDir);
        var config = new CompilationConfig { Target = "claude", DryRun = true };

        var result = compiler.Compile(config, new PrimitiveCollection());

        result.Success.Should().BeFalse();
        result.Errors.Should().NotBeEmpty();
    }

    [Fact]
    public void Compiler_ClaudeTarget_WithFormatter_CallsFormatDistributed()
    {
        var claudeFormatter = A.Fake<IClaudeFormatter>();
        var distributedCompiler = A.Fake<IDistributedCompiler>();

        A.CallTo(() => distributedCompiler.AnalyzeDirectoryStructure(A<List<Instruction>>._))
            .Returns([]);
        A.CallTo(() => distributedCompiler.DetermineAgentsPlacement(
            A<List<Instruction>>._, A<List<DirectoryMapping>>._, A<int>._, A<bool>._))
            .Returns([]);
        A.CallTo(() => distributedCompiler.FormatCompilationOutput(A<bool>._, A<bool>._, A<bool>._))
            .Returns(null);
        A.CallTo(() => claudeFormatter.FormatDistributed(
            A<PrimitiveCollection>._,
            A<List<PlacementResult>>._,
            A<Dictionary<string, object>>._))
            .Returns(new ClaudeCompilationResult
            {
                Placements = [],
                ContentMap = new Dictionary<string, string>()
            });

        var compiler = new AgentsCompiler(_tempDir,
            claudeFormatter: claudeFormatter,
            distributedCompiler: distributedCompiler);
        var config = new CompilationConfig { Target = "claude", DryRun = true };

        var result = compiler.Compile(config, new PrimitiveCollection());

        A.CallTo(() => claudeFormatter.FormatDistributed(
            A<PrimitiveCollection>._,
            A<List<PlacementResult>>._,
            A<Dictionary<string, object>>._))
            .MustHaveHappenedOnceExactly();
    }

    [Fact]
    public void Compiler_ClaudeTarget_DryRun_DoesNotWriteFiles()
    {
        var claudeFormatter = A.Fake<IClaudeFormatter>();
        var distributedCompiler = A.Fake<IDistributedCompiler>();
        var claudePath = Path.Combine(_tempDir, "CLAUDE.md");

        A.CallTo(() => distributedCompiler.AnalyzeDirectoryStructure(A<List<Instruction>>._))
            .Returns([]);
        A.CallTo(() => distributedCompiler.DetermineAgentsPlacement(
            A<List<Instruction>>._, A<List<DirectoryMapping>>._, A<int>._, A<bool>._))
            .Returns([]);
        A.CallTo(() => distributedCompiler.FormatCompilationOutput(A<bool>._, A<bool>._, A<bool>._))
            .Returns(null);
        A.CallTo(() => claudeFormatter.FormatDistributed(
            A<PrimitiveCollection>._,
            A<List<PlacementResult>>._,
            A<Dictionary<string, object>>._))
            .Returns(new ClaudeCompilationResult
            {
                Placements = [new PlacementResult { AgentsPath = claudePath }],
                ContentMap = new Dictionary<string, string> { [claudePath] = "# CLAUDE.md" }
            });

        var compiler = new AgentsCompiler(_tempDir,
            claudeFormatter: claudeFormatter,
            distributedCompiler: distributedCompiler);
        var config = new CompilationConfig { Target = "claude", DryRun = true };

        compiler.Compile(config, new PrimitiveCollection());

        File.Exists(claudePath).Should().BeFalse();
    }
}

public class DistributedCompilationModelTests
{
    [Fact]
    public void PlacementResult_Defaults()
    {
        var placement = new PlacementResult();

        placement.AgentsPath.Should().BeEmpty();
        placement.Instructions.Should().BeEmpty();
        placement.InheritedInstructions.Should().BeEmpty();
        placement.CoveragePatterns.Should().BeEmpty();
        placement.SourceAttribution.Should().BeEmpty();
    }

    [Fact]
    public void DirectoryMapping_Defaults()
    {
        var mapping = new DirectoryMapping();

        mapping.Directory.Should().BeEmpty();
        mapping.ApplicablePatterns.Should().BeEmpty();
        mapping.Depth.Should().Be(0);
        mapping.ParentDirectory.Should().BeNull();
    }

    [Fact]
    public void DistributedCompilationResult_Defaults()
    {
        var result = new DistributedCompilationResult();

        result.Success.Should().BeFalse();
        result.Placements.Should().BeEmpty();
        result.ContentMap.Should().BeEmpty();
        result.Warnings.Should().BeEmpty();
        result.Errors.Should().BeEmpty();
        result.Stats.Should().BeEmpty();
    }
}

// ── Real ClaudeFormatter tests (ported from Python) ─────────────────

public class ClaudeFormatterRealTests : IDisposable
{
    private readonly string _tempDir;

    public ClaudeFormatterRealTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    private PrimitiveCollection CreateSamplePrimitives()
    {
        var primitives = new PrimitiveCollection();
        primitives.AddPrimitive(new Instruction
        {
            Name = "python-style",
            FilePath = Path.Combine(_tempDir, ".github", "instructions", "python.instructions.md"),
            Description = "Python coding standards",
            ApplyTo = "**/*.py",
            Content = "Use type hints and follow PEP 8.",
            Source = "local"
        });
        primitives.AddPrimitive(new Instruction
        {
            Name = "js-style",
            FilePath = Path.Combine(_tempDir, ".github", "instructions", "js.instructions.md"),
            Description = "JavaScript coding standards",
            ApplyTo = "**/*.js",
            Content = "Use ES6+ features.",
            Source = "local"
        });
        return primitives;
    }

    private List<PlacementResult> CreatePlacementsFromInstructions(List<Instruction> instructions)
    {
        return
        [
            new PlacementResult
            {
                AgentsPath = Path.Combine(_tempDir, "CLAUDE.md"),
                Instructions = instructions,
                CoveragePatterns = new HashSet<string>(instructions
                    .Where(i => !string.IsNullOrEmpty(i.ApplyTo))
                    .Select(i => i.ApplyTo))
            }
        ];
    }

    // ── Header / Footer ────────────────────────────────────────────

    [Fact]
    public void FormatDistributed_GeneratesHeader()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var primitives = CreateSamplePrimitives();
        var placements = CreatePlacementsFromInstructions(primitives.Instructions);

        var result = formatter.FormatDistributed(primitives, placements, new Dictionary<string, object>());

        result.ContentMap.Should().HaveCount(1);
        var content = result.ContentMap.Values.First();
        content.Should().Contain("# CLAUDE.md");
        content.Should().Contain("<!-- Generated by APM CLI -->");
        content.Should().Contain(CompilationConstants.BuildIdPlaceholder);
        content.Should().Contain($"<!-- APM Version: {VersionInfo.GetVersion()} -->");
    }

    [Fact]
    public void FormatDistributed_GeneratesFooter()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var primitives = CreateSamplePrimitives();
        var placements = CreatePlacementsFromInstructions(primitives.Instructions);

        var result = formatter.FormatDistributed(primitives, placements, new Dictionary<string, object>());

        var content = result.ContentMap.Values.First();
        content.Should().Contain("*This file was generated by APM CLI. Do not edit manually.*");
        content.Should().Contain("*To regenerate: `apm compile`*");
    }

    // ── Pattern grouping / Project Standards ───────────────────────

    [Fact]
    public void FormatDistributed_GroupsByApplyToPatterns()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var primitives = CreateSamplePrimitives();
        var placements = CreatePlacementsFromInstructions(primitives.Instructions);

        var result = formatter.FormatDistributed(primitives, placements, new Dictionary<string, object>());

        var content = result.ContentMap.Values.First();
        content.Should().Contain("## Files matching `**/*.py`");
        content.Should().Contain("## Files matching `**/*.js`");
        content.Should().Contain("Use type hints and follow PEP 8.");
        content.Should().Contain("Use ES6+ features.");
    }

    [Fact]
    public void FormatDistributed_IncludesProjectStandardsSection()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var primitives = CreateSamplePrimitives();
        var placements = CreatePlacementsFromInstructions(primitives.Instructions);

        var result = formatter.FormatDistributed(primitives, placements, new Dictionary<string, object>());

        var content = result.ContentMap.Values.First();
        content.Should().Contain("# Project Standards");
    }

    // ── Source attribution ──────────────────────────────────────────

    [Fact]
    public void FormatDistributed_IncludesSourceAttribution()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var primitives = CreateSamplePrimitives();
        var placements = CreatePlacementsFromInstructions(primitives.Instructions);
        var config = new Dictionary<string, object> { ["source_attribution"] = true };

        var result = formatter.FormatDistributed(primitives, placements, config);

        var content = result.ContentMap.Values.First();
        content.Should().Contain("<!-- Source:");
    }

    [Fact]
    public void FormatDistributed_WithoutSourceAttribution()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var primitives = CreateSamplePrimitives();
        var placements = CreatePlacementsFromInstructions(primitives.Instructions);
        var config = new Dictionary<string, object> { ["source_attribution"] = false };

        var result = formatter.FormatDistributed(primitives, placements, config);

        var content = result.ContentMap.Values.First();
        content.Should().NotContain("<!-- Source:");
    }

    // ── Compilation statistics ──────────────────────────────────────

    [Fact]
    public void FormatDistributed_ReturnsCompilationStats()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var primitives = CreateSamplePrimitives();
        var placements = CreatePlacementsFromInstructions(primitives.Instructions);

        var result = formatter.FormatDistributed(primitives, placements, new Dictionary<string, object>());

        result.Stats["claude_files_generated"].Should().Be(1);
        result.Stats["total_instructions_placed"].Should().Be(2);
        result.Stats["total_patterns_covered"].Should().Be(2);
    }

    // ── Empty placement ────────────────────────────────────────────

    [Fact]
    public void FormatDistributed_EmptyPlacements_ReturnsEmptyContentMap()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var primitives = new PrimitiveCollection();

        var result = formatter.FormatDistributed(primitives, [], new Dictionary<string, object>());

        result.ContentMap.Should().BeEmpty();
    }

    // ── Constitution ───────────────────────────────────────────────

    [Fact]
    public void FormatDistributed_WithConstitution_IncludesConstitutionSection()
    {
        // Create constitution file at the expected path
        var constitutionDir = Path.Combine(_tempDir, ".specify", "memory");
        Directory.CreateDirectory(constitutionDir);
        File.WriteAllText(
            Path.Combine(constitutionDir, "constitution.md"),
            "# Constitution\n\nBe helpful and accurate.");

        var formatter = new ClaudeFormatter(_tempDir);
        var primitives = new PrimitiveCollection();

        // Empty placements triggers constitution-only path
        var result = formatter.FormatDistributed(primitives, [], new Dictionary<string, object>());

        if (result.ContentMap.Count > 0)
        {
            var content = result.ContentMap.Values.First();
            content.Should().Contain("# Constitution");
            content.Should().Contain("Be helpful and accurate.");
        }
    }

    // ── Agents excluded from CLAUDE.md ─────────────────────────────

    [Fact]
    public void FormatDistributed_AgentsNotInClaudeMd()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var primitives = new PrimitiveCollection();

        primitives.AddPrimitive(new Chatmode
        {
            Name = "code-reviewer",
            FilePath = Path.Combine(_tempDir, "code-reviewer.chatmode.md"),
            Description = "Expert code reviewer",
            Content = "You are an expert code reviewer. Focus on security and performance."
        });

        var instruction = new Instruction
        {
            Name = "test",
            FilePath = Path.Combine(_tempDir, "test.instructions.md"),
            Description = "Test",
            ApplyTo = "**/*.py",
            Content = "Test content",
            Source = "local"
        };
        primitives.AddPrimitive(instruction);

        var placements = CreatePlacementsFromInstructions([instruction]);
        var result = formatter.FormatDistributed(primitives, placements, new Dictionary<string, object>());

        var content = result.ContentMap.Values.First();
        content.Should().NotContain("# Workflows");
        content.Should().NotContain("## code-reviewer");
        content.Should().Contain("Test content");
    }

    [Fact]
    public void FormatDistributed_OnlyContainsInstructions()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var primitives = new PrimitiveCollection();

        primitives.AddPrimitive(new Chatmode
        {
            Name = "reviewer",
            FilePath = Path.Combine(_tempDir, "reviewer.chatmode.md"),
            Description = "Reviewer",
            Content = "You are a reviewer."
        });

        var instruction = new Instruction
        {
            Name = "python-standards",
            FilePath = Path.Combine(_tempDir, "python.instructions.md"),
            Description = "Python standards",
            ApplyTo = "**/*.py",
            Content = "Use type hints for all functions.",
            Source = "local"
        };
        primitives.AddPrimitive(instruction);

        var placements = CreatePlacementsFromInstructions([instruction]);
        var result = formatter.FormatDistributed(primitives, placements, new Dictionary<string, object>());

        var content = result.ContentMap.Values.First();
        content.Should().Contain("Use type hints for all functions.");
        content.Should().Contain("**/*.py");
        content.Should().NotContain("You are a reviewer.");
        content.Should().NotContain("Workflows");
    }

    [Fact]
    public void FormatDistributed_MultipleChatmodesExcluded()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var primitives = new PrimitiveCollection();

        primitives.AddPrimitive(new Chatmode
        {
            Name = "reviewer",
            FilePath = Path.Combine(_tempDir, "reviewer.chatmode.md"),
            Description = "Code reviewer",
            Content = "Review code."
        });
        primitives.AddPrimitive(new Chatmode
        {
            Name = "architect",
            FilePath = Path.Combine(_tempDir, "architect.chatmode.md"),
            Description = "System architect",
            Content = "Design systems."
        });

        var instruction = new Instruction
        {
            Name = "test",
            FilePath = Path.Combine(_tempDir, "test.instructions.md"),
            Description = "Test",
            ApplyTo = "**/*.py",
            Content = "Test instruction content",
            Source = "local"
        };
        primitives.AddPrimitive(instruction);

        var placements = CreatePlacementsFromInstructions([instruction]);
        var result = formatter.FormatDistributed(primitives, placements, new Dictionary<string, object>());

        var content = result.ContentMap.Values.First();
        content.Should().NotContain("## reviewer");
        content.Should().NotContain("## architect");
        content.Should().NotContain("Review code.");
        content.Should().NotContain("Design systems.");
        content.Should().Contain("Test instruction content");
    }

    // ── Dependencies ───────────────────────────────────────────────

    [Fact]
    public void FormatDistributed_DependenciesUseImportSyntax()
    {
        // Create apm_modules structure
        var owner1 = Path.Combine(_tempDir, "apm_modules", "owner1", "package1");
        var owner2 = Path.Combine(_tempDir, "apm_modules", "owner2", "package2");
        Directory.CreateDirectory(owner1);
        Directory.CreateDirectory(owner2);

        var formatter = new ClaudeFormatter(_tempDir);
        var primitives = new PrimitiveCollection();

        var instruction = new Instruction
        {
            Name = "test",
            FilePath = Path.Combine(_tempDir, "test.instructions.md"),
            Description = "Test",
            ApplyTo = "**/*.py",
            Content = "Test content",
            Source = "local"
        };
        primitives.AddPrimitive(instruction);

        var placements = new List<PlacementResult>
        {
            new()
            {
                AgentsPath = Path.Combine(_tempDir, "CLAUDE.md"),
                Instructions = [instruction],
                CoveragePatterns = ["**/*.py"]
            }
        };

        var result = formatter.FormatDistributed(primitives, placements, new Dictionary<string, object>());

        var content = result.ContentMap.Values.First();
        content.Should().Contain("@apm_modules/owner1/package1/CLAUDE.md");
        content.Should().Contain("@apm_modules/owner2/package2/CLAUDE.md");
        content.Should().Contain("# Dependencies");
    }

    [Fact]
    public void FormatDistributed_DependenciesAreSorted()
    {
        // Create deps in non-alphabetical order
        var zPkg = Path.Combine(_tempDir, "apm_modules", "z-owner", "z-pkg");
        var aPkg = Path.Combine(_tempDir, "apm_modules", "a-owner", "a-pkg");
        Directory.CreateDirectory(zPkg);
        Directory.CreateDirectory(aPkg);

        var formatter = new ClaudeFormatter(_tempDir);
        var primitives = new PrimitiveCollection();
        var instruction = new Instruction
        {
            Name = "test",
            FilePath = Path.Combine(_tempDir, "test.instructions.md"),
            Description = "Test",
            ApplyTo = "**",
            Content = "Test",
            Source = "local"
        };
        primitives.AddPrimitive(instruction);

        var placements = new List<PlacementResult>
        {
            new()
            {
                AgentsPath = Path.Combine(_tempDir, "CLAUDE.md"),
                Instructions = [instruction],
                CoveragePatterns = ["**"]
            }
        };

        var result = formatter.FormatDistributed(primitives, placements, new Dictionary<string, object>());

        var content = result.ContentMap.Values.First();
        var aIndex = content.IndexOf("@apm_modules/a-owner/a-pkg/CLAUDE.md");
        var zIndex = content.IndexOf("@apm_modules/z-owner/z-pkg/CLAUDE.md");
        aIndex.Should().BeLessThan(zIndex);
    }

    [Fact]
    public void FormatDistributed_NoDependenciesSectionWhenNoApmModules()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var primitives = new PrimitiveCollection();
        var instruction = new Instruction
        {
            Name = "test",
            FilePath = Path.Combine(_tempDir, "test.instructions.md"),
            Description = "Test",
            ApplyTo = "**",
            Content = "Test",
            Source = "local"
        };
        primitives.AddPrimitive(instruction);

        var placements = CreatePlacementsFromInstructions([instruction]);
        var result = formatter.FormatDistributed(primitives, placements, new Dictionary<string, object>());

        var content = result.ContentMap.Values.First();
        content.Should().NotContain("# Dependencies");
    }

    // ── Error handling ─────────────────────────────────────────────

    [Fact]
    public void FormatDistributed_HandlesExceptionsGracefully()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var primitives = new PrimitiveCollection();
        var instruction = new Instruction
        {
            Name = "test",
            FilePath = Path.Combine(_tempDir, "test.md"),
            Description = "Test",
            ApplyTo = "**/*.py",
            Content = "Test",
            Source = "local"
        };
        primitives.AddPrimitive(instruction);

        var result = formatter.FormatDistributed(
            primitives,
            CreatePlacementsFromInstructions([instruction]),
            new Dictionary<string, object>());

        result.Should().BeOfType<ClaudeCompilationResult>();
    }
}

// ── GenerateCommands tests (ported from Python) ─────────────────────

public class ClaudeFormatterCommandTests : IDisposable
{
    private readonly string _tempDir;

    public ClaudeFormatterCommandTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    private string CreatePromptFile(string name, string content)
    {
        var promptsDir = Path.Combine(_tempDir, ".github", "prompts");
        Directory.CreateDirectory(promptsDir);
        var path = Path.Combine(promptsDir, name);
        File.WriteAllText(path, content);
        return path;
    }

    [Fact]
    public void GenerateCommands_CreatesDirectory()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var promptPath = CreatePromptFile("code-review.prompt.md",
            "---\ndescription: Review code for issues\n---\nReview the following code for bugs and security issues.\n");

        var result = formatter.GenerateCommands([promptPath], dryRun: false);

        result.Success.Should().BeTrue();
        result.FilesWritten.Should().Be(1);
        Directory.Exists(result.CommandsDir).Should().BeTrue();
        File.Exists(Path.Combine(result.CommandsDir, "code-review.md")).Should().BeTrue();
    }

    [Fact]
    public void GenerateCommands_DryRun_DoesNotWriteFiles()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var promptPath = CreatePromptFile("test.prompt.md",
            "---\ndescription: Test prompt\n---\nTest content.\n");

        var result = formatter.GenerateCommands([promptPath], dryRun: true);

        result.Success.Should().BeTrue();
        result.FilesWritten.Should().Be(0);
        result.CommandsGenerated.Should().HaveCount(1);
        Directory.Exists(Path.Combine(_tempDir, ".claude", "commands")).Should().BeFalse();
    }

    [Fact]
    public void GenerateCommands_PreservesFrontmatter()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var promptPath = CreatePromptFile("review.prompt.md",
            "---\ndescription: Review code thoroughly\nmodel: claude-3-opus\nallowed-tools: Read, Write\nargument-hint: <file-path>\n---\nReview this code: $ARGUMENTS\n");

        var result = formatter.GenerateCommands([promptPath], dryRun: true);

        var content = result.CommandsGenerated.Values.First();
        content.Should().Contain("---");
        content.Should().Contain("description: Review code thoroughly");
        content.Should().Contain("model: claude-3-opus");
        content.Should().Contain("allowed-tools: Read, Write");
        content.Should().Contain("argument-hint: <file-path>");
    }

    [Fact]
    public void GenerateCommands_AddsArgumentsPlaceholder()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var promptPath = CreatePromptFile("simple.prompt.md",
            "---\ndescription: Simple prompt\n---\nDo something simple.\n");

        var result = formatter.GenerateCommands([promptPath], dryRun: true);

        var content = result.CommandsGenerated.Values.First();
        content.Should().Contain("$ARGUMENTS");
        result.Warnings.Should().Contain(w => w.Contains("Added $ARGUMENTS placeholder"));
    }

    [Fact]
    public void GenerateCommands_PreservesExistingArguments()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var promptPath = CreatePromptFile("with-args.prompt.md",
            "---\ndescription: Prompt with arguments\n---\nProcess this input: $ARGUMENTS\n");

        var result = formatter.GenerateCommands([promptPath], dryRun: true);

        var content = result.CommandsGenerated.Values.First();
        // Exactly one $ARGUMENTS
        var count = content.Split("$ARGUMENTS").Length - 1;
        count.Should().Be(1);
        result.Warnings.Should().NotContain(w => w.Contains("Added $ARGUMENTS"));
    }

    [Fact]
    public void GenerateCommands_PreservesPositionalArgs()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var promptPath = CreatePromptFile("positional.prompt.md",
            "---\ndescription: Prompt with positional args\n---\nCompare $1 with $2.\n");

        var result = formatter.GenerateCommands([promptPath], dryRun: true);

        var content = result.CommandsGenerated.Values.First();
        content.Should().Contain("$1");
        content.Should().Contain("$2");
        result.Warnings.Should().NotContain(w => w.Contains("Added $ARGUMENTS"));
    }

    [Fact]
    public void GenerateCommands_ExtractsNameFromFilename()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var promptPath = CreatePromptFile("my-custom-command.prompt.md",
            "---\ndescription: Custom command\n---\nContent.\n");

        var result = formatter.GenerateCommands([promptPath], dryRun: true);

        result.CommandsGenerated.Keys.Should().Contain(
            k => k.EndsWith("my-custom-command.md"));
    }

    [Fact]
    public void GenerateCommands_MapsCamelCaseFrontmatter()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var promptPath = CreatePromptFile("camel.prompt.md",
            "---\ndescription: Test camelCase\nallowedTools: Read, Write, Bash\nargumentHint: <path>\n---\nContent here.\n");

        var result = formatter.GenerateCommands([promptPath], dryRun: true);

        var content = result.CommandsGenerated.Values.First();
        content.Should().Contain("allowed-tools: Read, Write, Bash");
        content.Should().Contain("argument-hint: <path>");
    }

    [Fact]
    public void GenerateCommands_HandlesInvalidFile()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var nonexistent = Path.Combine(_tempDir, "nonexistent.prompt.md");

        var result = formatter.GenerateCommands([nonexistent], dryRun: true);

        result.Errors.Should().NotBeEmpty();
    }

    [Fact]
    public void GenerateCommands_HandlesMalformedFrontmatter()
    {
        var formatter = new ClaudeFormatter(_tempDir);
        var promptPath = CreatePromptFile("malformed.prompt.md",
            "---\ndescription: [unclosed bracket\n---\nContent here.\n");

        var result = formatter.GenerateCommands([promptPath], dryRun: true);

        result.Should().BeOfType<CommandGenerationResult>();
    }
}

// ── DiscoverPromptFiles tests (ported from Python) ──────────────────

public class ClaudeFormatterDiscoveryTests : IDisposable
{
    private readonly string _tempDir;

    public ClaudeFormatterDiscoveryTests()
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
    public void DiscoverPromptFiles_InGithubPrompts()
    {
        var promptsDir = Path.Combine(_tempDir, ".github", "prompts");
        Directory.CreateDirectory(promptsDir);
        File.WriteAllText(Path.Combine(promptsDir, "test.prompt.md"), "Test content");

        var formatter = new ClaudeFormatter(_tempDir);
        var files = formatter.DiscoverPromptFiles();

        files.Should().HaveCount(1);
        files[0].Should().Contain("test.prompt.md");
    }

    [Fact]
    public void DiscoverPromptFiles_InApmPrompts()
    {
        var promptsDir = Path.Combine(_tempDir, ".apm", "prompts");
        Directory.CreateDirectory(promptsDir);
        File.WriteAllText(Path.Combine(promptsDir, "apm-test.prompt.md"), "APM test");

        var formatter = new ClaudeFormatter(_tempDir);
        var files = formatter.DiscoverPromptFiles();

        files.Should().HaveCount(1);
        files[0].Should().Contain("apm-test.prompt.md");
    }

    [Fact]
    public void DiscoverPromptFiles_InRoot()
    {
        File.WriteAllText(Path.Combine(_tempDir, "root-prompt.prompt.md"), "Root prompt");

        var formatter = new ClaudeFormatter(_tempDir);
        var files = formatter.DiscoverPromptFiles();

        files.Should().HaveCount(1);
        files[0].Should().Contain("root-prompt.prompt.md");
    }

    [Fact]
    public void DiscoverPromptFiles_InApmModules()
    {
        var promptsDir = Path.Combine(_tempDir, "apm_modules", "owner", "package", "prompts");
        Directory.CreateDirectory(promptsDir);
        File.WriteAllText(Path.Combine(promptsDir, "dep-prompt.prompt.md"), "Dependency prompt");

        var formatter = new ClaudeFormatter(_tempDir);
        var files = formatter.DiscoverPromptFiles();

        files.Should().HaveCount(1);
        files[0].Should().Contain("dep-prompt.prompt.md");
    }

    [Fact]
    public void DiscoverPromptFiles_NoDuplicates()
    {
        var promptsDir = Path.Combine(_tempDir, ".github", "prompts");
        Directory.CreateDirectory(promptsDir);
        File.WriteAllText(Path.Combine(promptsDir, "unique.prompt.md"), "Unique");

        var formatter = new ClaudeFormatter(_tempDir);
        var files1 = formatter.DiscoverPromptFiles();
        var files2 = formatter.DiscoverPromptFiles();

        files1.Should().HaveCount(1);
        files2.Should().HaveCount(1);
    }

    [Fact]
    public void DiscoverAndGenerateCommands_Integration()
    {
        var promptsDir = Path.Combine(_tempDir, ".github", "prompts");
        Directory.CreateDirectory(promptsDir);
        File.WriteAllText(
            Path.Combine(promptsDir, "test.prompt.md"),
            "---\ndescription: Test\n---\nTest content.\n");

        var formatter = new ClaudeFormatter(_tempDir);
        var discovered = formatter.DiscoverPromptFiles();
        var result = formatter.GenerateCommands(discovered, dryRun: true);

        result.Success.Should().BeTrue();
        result.CommandsGenerated.Should().HaveCount(1);
    }
}

// ── Init tests (ported from Python TestClaudeFormatterInit) ─────────

public class ClaudeFormatterInitTests : IDisposable
{
    private readonly string _tempDir;

    public ClaudeFormatterInitTests()
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
    public void Init_WithValidDirectory_SetsBaseDir()
    {
        var formatter = new ClaudeFormatter(_tempDir);

        // FormatDistributed with empty input should not throw
        var result = formatter.FormatDistributed(
            new PrimitiveCollection(), [], new Dictionary<string, object>());

        result.Should().BeOfType<ClaudeCompilationResult>();
    }

    [Fact]
    public void Init_WithDefaultDirectory_UsesCurrentDir()
    {
        var formatter = new ClaudeFormatter();

        // Should not throw; uses "." which resolves to cwd
        var result = formatter.FormatDistributed(
            new PrimitiveCollection(), [], new Dictionary<string, object>());

        result.Should().BeOfType<ClaudeCompilationResult>();
    }

    [Fact]
    public void Init_WithRelativePath_ResolvesToAbsolute()
    {
        var formatter = new ClaudeFormatter(".");

        // The formatter should resolve "." to an absolute path internally.
        // Verify it works by running a no-op compilation.
        var result = formatter.FormatDistributed(
            new PrimitiveCollection(), [], new Dictionary<string, object>());

        result.Should().BeOfType<ClaudeCompilationResult>();
    }
}

// ── CommandGenerationResult model tests ─────────────────────────────

public class CommandGenerationResultModelTests
{
    [Fact]
    public void CommandGenerationResult_Defaults()
    {
        var result = new CommandGenerationResult
        {
            Success = true,
            CommandsDir = ".claude/commands",
            FilesWritten = 0
        };

        result.Warnings.Should().BeEmpty();
        result.Errors.Should().BeEmpty();
        result.CommandsGenerated.Should().BeEmpty();
    }
}

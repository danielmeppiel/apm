using Apm.Cli.Compilation;
using Apm.Cli.Primitives;
using AwesomeAssertions;
using FakeItEasy;

namespace Apm.Cli.Tests.Compilation;

public class AgentsCompilerTests : IDisposable
{
    private readonly string _tempDir;

    public AgentsCompilerTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    // ── Compile with empty project ──────────────────────────────────

    [Fact]
    public void Compile_WithEmptyPrimitives_Succeeds()
    {
        var compiler = new AgentsCompiler(_tempDir);
        var config = new CompilationConfig { Strategy = "single-file", Target = "vscode" };
        var primitives = new PrimitiveCollection();

        var result = compiler.Compile(config, primitives);

        result.Success.Should().BeTrue();
        result.Errors.Should().BeEmpty();
    }

    [Fact]
    public void Compile_WithEmptyPrimitives_ProducesEmptyContent()
    {
        var templateBuilder = A.Fake<ITemplateBuilder>();
        A.CallTo(() => templateBuilder.BuildConditionalSections(A<List<Instruction>>._)).Returns("");
        A.CallTo(() => templateBuilder.GenerateAgentsMdTemplate(A<TemplateData>._)).Returns("");

        var compiler = new AgentsCompiler(_tempDir, templateBuilder: templateBuilder);
        var config = new CompilationConfig { Strategy = "single-file", Target = "vscode" };

        var result = compiler.Compile(config, new PrimitiveCollection());

        result.Content.Should().BeEmpty();
    }

    [Fact]
    public void Compile_WithEmptyPrimitives_StatsShowZeroPrimitives()
    {
        var compiler = new AgentsCompiler(_tempDir);
        var config = new CompilationConfig { Strategy = "single-file", Target = "vscode" };

        var result = compiler.Compile(config, new PrimitiveCollection());

        result.Stats.Should().ContainKey("primitives_found");
        ((int)result.Stats["primitives_found"]).Should().Be(0);
    }

    // ── Compile with instructions only ──────────────────────────────

    [Fact]
    public void Compile_WithInstructionsOnly_CallsTemplateBuilder()
    {
        var templateBuilder = A.Fake<ITemplateBuilder>();
        A.CallTo(() => templateBuilder.BuildConditionalSections(A<List<Instruction>>._))
            .Returns("# Instructions\n- Use type hints");
        A.CallTo(() => templateBuilder.GenerateAgentsMdTemplate(A<TemplateData>._))
            .Returns("# AGENTS.md\n# Instructions\n- Use type hints");

        var compiler = new AgentsCompiler(_tempDir, templateBuilder: templateBuilder);
        var config = new CompilationConfig { Strategy = "single-file", Target = "vscode" };
        var primitives = new PrimitiveCollection();
        primitives.AddPrimitive(new Instruction
        {
            Name = "python-style",
            Description = "Python style guide",
            ApplyTo = "**/*.py",
            Content = "Use type hints",
            Source = "local"
        });

        var result = compiler.Compile(config, primitives);

        result.Success.Should().BeTrue();
        result.Content.Should().Contain("Instructions");
        A.CallTo(() => templateBuilder.BuildConditionalSections(A<List<Instruction>>._))
            .MustHaveHappenedOnceExactly();
    }

    [Fact]
    public void Compile_WithInstructions_StatsReflectCount()
    {
        var compiler = new AgentsCompiler(_tempDir);
        var config = new CompilationConfig { Strategy = "single-file", Target = "vscode" };
        var primitives = new PrimitiveCollection();
        primitives.AddPrimitive(new Instruction
        {
            Name = "style1",
            Description = "Style",
            ApplyTo = "**/*.cs",
            Content = "Content",
            Source = "local"
        });
        primitives.AddPrimitive(new Instruction
        {
            Name = "style2",
            Description = "Style 2",
            ApplyTo = "**/*.ts",
            Content = "Content",
            Source = "local"
        });

        var result = compiler.Compile(config, primitives);

        ((int)result.Stats["instructions"]).Should().Be(2);
        ((int)result.Stats["primitives_found"]).Should().Be(2);
    }

    // ── Dry-run mode ────────────────────────────────────────────────

    [Fact]
    public void Compile_DryRun_DoesNotWriteFile()
    {
        var compiler = new AgentsCompiler(_tempDir);
        var config = new CompilationConfig
        {
            Strategy = "single-file",
            Target = "vscode",
            DryRun = true,
            OutputPath = "AGENTS.md"
        };

        compiler.Compile(config, new PrimitiveCollection());

        var outputPath = Path.Combine(_tempDir, "AGENTS.md");
        File.Exists(outputPath).Should().BeFalse();
    }

    [Fact]
    public void Compile_NotDryRun_WritesFile()
    {
        var templateBuilder = A.Fake<ITemplateBuilder>();
        A.CallTo(() => templateBuilder.BuildConditionalSections(A<List<Instruction>>._)).Returns("");
        A.CallTo(() => templateBuilder.GenerateAgentsMdTemplate(A<TemplateData>._)).Returns("# AGENTS.md");

        var compiler = new AgentsCompiler(_tempDir, templateBuilder: templateBuilder);
        var config = new CompilationConfig
        {
            Strategy = "single-file",
            Target = "vscode",
            DryRun = false,
            OutputPath = "AGENTS.md"
        };

        compiler.Compile(config, new PrimitiveCollection());

        var outputPath = Path.Combine(_tempDir, "AGENTS.md");
        File.Exists(outputPath).Should().BeTrue();
        File.ReadAllText(outputPath).Should().Be("# AGENTS.md");
    }

    // ── Target selection ────────────────────────────────────────────

    [Fact]
    public void Compile_TargetVscode_CompilesSingleFile()
    {
        var templateBuilder = A.Fake<ITemplateBuilder>();
        A.CallTo(() => templateBuilder.BuildConditionalSections(A<List<Instruction>>._)).Returns("");
        A.CallTo(() => templateBuilder.GenerateAgentsMdTemplate(A<TemplateData>._)).Returns("vscode content");

        var compiler = new AgentsCompiler(_tempDir, templateBuilder: templateBuilder);
        var config = new CompilationConfig { Target = "vscode", Strategy = "single-file", DryRun = true };

        var result = compiler.Compile(config, new PrimitiveCollection());

        result.Success.Should().BeTrue();
        result.Content.Should().Be("vscode content");
    }

    [Fact]
    public void Compile_TargetClaude_WithoutFormatter_ReturnsError()
    {
        var compiler = new AgentsCompiler(_tempDir);
        var config = new CompilationConfig { Target = "claude", DryRun = true };

        var result = compiler.Compile(config, new PrimitiveCollection());

        result.Success.Should().BeFalse();
        result.Errors.Should().Contain(e => e.Contains("Claude formatter") || e.Contains("not available"));
    }

    [Fact]
    public void Compile_TargetAll_WithoutClaudeFormatter_StillCompilesAgents()
    {
        var templateBuilder = A.Fake<ITemplateBuilder>();
        A.CallTo(() => templateBuilder.BuildConditionalSections(A<List<Instruction>>._)).Returns("");
        A.CallTo(() => templateBuilder.GenerateAgentsMdTemplate(A<TemplateData>._)).Returns("agents output");

        var compiler = new AgentsCompiler(_tempDir, templateBuilder: templateBuilder);
        var config = new CompilationConfig { Target = "all", Strategy = "single-file", DryRun = true };

        var result = compiler.Compile(config, new PrimitiveCollection());

        // "all" target compiles both agents and claude; claude fails but agents portion runs
        result.Content.Should().Contain("agents output");
    }

    // ── Link resolution ─────────────────────────────────────────────

    [Fact]
    public void Compile_WithResolveLinks_CallsLinkResolver()
    {
        var templateBuilder = A.Fake<ITemplateBuilder>();
        var linkResolver = A.Fake<ILinkResolver>();
        A.CallTo(() => templateBuilder.BuildConditionalSections(A<List<Instruction>>._)).Returns("");
        A.CallTo(() => templateBuilder.GenerateAgentsMdTemplate(A<TemplateData>._)).Returns("content with [link](file.md)");
        A.CallTo(() => linkResolver.ResolveMarkdownLinks(A<string>._, A<string>._)).Returns("resolved content");
        A.CallTo(() => linkResolver.ValidateLinkTargets(A<string>._, A<string>._)).Returns([]);

        var compiler = new AgentsCompiler(_tempDir, templateBuilder: templateBuilder, linkResolver: linkResolver);
        var config = new CompilationConfig { Strategy = "single-file", Target = "vscode", ResolveLinks = true, DryRun = true };

        var result = compiler.Compile(config, new PrimitiveCollection());

        result.Content.Should().Be("resolved content");
        A.CallTo(() => linkResolver.ResolveMarkdownLinks(A<string>._, A<string>._))
            .MustHaveHappenedOnceExactly();
    }

    [Fact]
    public void Compile_WithResolveLinksDisabled_DoesNotCallLinkResolver()
    {
        var templateBuilder = A.Fake<ITemplateBuilder>();
        var linkResolver = A.Fake<ILinkResolver>();
        A.CallTo(() => templateBuilder.BuildConditionalSections(A<List<Instruction>>._)).Returns("");
        A.CallTo(() => templateBuilder.GenerateAgentsMdTemplate(A<TemplateData>._)).Returns("raw content");
        A.CallTo(() => linkResolver.ValidateLinkTargets(A<string>._, A<string>._)).Returns([]);

        var compiler = new AgentsCompiler(_tempDir, templateBuilder: templateBuilder, linkResolver: linkResolver);
        var config = new CompilationConfig { Strategy = "single-file", Target = "vscode", ResolveLinks = false, DryRun = true };

        var result = compiler.Compile(config, new PrimitiveCollection());

        result.Content.Should().Be("raw content");
        A.CallTo(() => linkResolver.ResolveMarkdownLinks(A<string>._, A<string>._))
            .MustNotHaveHappened();
    }

    // ── Distributed compilation ─────────────────────────────────────

    [Fact]
    public void Compile_DistributedWithoutCompiler_ReturnsError()
    {
        var compiler = new AgentsCompiler(_tempDir);
        var config = new CompilationConfig { Strategy = "distributed", Target = "vscode", DryRun = true };

        var result = compiler.Compile(config, new PrimitiveCollection());

        result.Success.Should().BeFalse();
        result.Errors.Should().Contain(e => e.Contains("Distributed compiler not available"));
    }

    [Fact]
    public void Compile_SingleAgentsFlag_ForcesSingleFile()
    {
        var templateBuilder = A.Fake<ITemplateBuilder>();
        A.CallTo(() => templateBuilder.BuildConditionalSections(A<List<Instruction>>._)).Returns("");
        A.CallTo(() => templateBuilder.GenerateAgentsMdTemplate(A<TemplateData>._)).Returns("single file output");

        var compiler = new AgentsCompiler(_tempDir, templateBuilder: templateBuilder);
        var config = new CompilationConfig
        {
            Strategy = "distributed",
            SingleAgents = true,
            Target = "vscode",
            DryRun = true
        };

        var result = compiler.Compile(config, new PrimitiveCollection());

        result.Success.Should().BeTrue();
        result.Content.Should().Be("single file output");
    }

    [Fact]
    public void Compile_Distributed_WithCompiler_CallsCompileDistributed()
    {
        var distributedCompiler = A.Fake<IDistributedCompiler>();
        A.CallTo(() => distributedCompiler.CompileDistributed(A<PrimitiveCollection>._, A<Dictionary<string, object>>._))
            .Returns(new DistributedCompilationResult
            {
                Success = true,
                Placements = [],
                ContentMap = [],
                Stats = new Dictionary<string, object> { ["agents_files_generated"] = 0 },
            });
        A.CallTo(() => distributedCompiler.FormatCompilationOutput(A<bool>._, A<bool>._, A<bool>._))
            .Returns(null);

        var compiler = new AgentsCompiler(_tempDir, distributedCompiler: distributedCompiler);
        var config = new CompilationConfig { Strategy = "distributed", Target = "vscode", DryRun = true };

        compiler.Compile(config, new PrimitiveCollection());

        A.CallTo(() => distributedCompiler.CompileDistributed(A<PrimitiveCollection>._, A<Dictionary<string, object>>._))
            .MustHaveHappenedOnceExactly();
    }

    [Fact]
    public void Compile_Distributed_SuccessPath_WritesFiles()
    {
        var agentsPath = Path.Combine(_tempDir, "src", "AGENTS.md");
        Directory.CreateDirectory(Path.Combine(_tempDir, "src"));

        var distributedCompiler = A.Fake<IDistributedCompiler>();
        A.CallTo(() => distributedCompiler.CompileDistributed(A<PrimitiveCollection>._, A<Dictionary<string, object>>._))
            .Returns(new DistributedCompilationResult
            {
                Success = true,
                Placements =
                [
                    new PlacementResult
                    {
                        AgentsPath = agentsPath,
                        Instructions = [new Instruction { Name = "test", ApplyTo = "**/*.py", Content = "Test", Source = "local" }],
                        CoveragePatterns = ["**/*.py"],
                    }
                ],
                ContentMap = new Dictionary<string, string> { [agentsPath] = "# AGENTS.md\nGenerated by APM CLI\nFiles matching **/*.py" },
                Stats = new Dictionary<string, object> { ["agents_files_generated"] = 0 },
            });
        A.CallTo(() => distributedCompiler.FormatCompilationOutput(A<bool>._, A<bool>._, A<bool>._))
            .Returns(null);

        var compiler = new AgentsCompiler(_tempDir, distributedCompiler: distributedCompiler);
        var config = new CompilationConfig { Strategy = "distributed", Target = "vscode", DryRun = false };

        var result = compiler.Compile(config, new PrimitiveCollection());

        result.Success.Should().BeTrue();
        File.Exists(agentsPath).Should().BeTrue();
        var content = File.ReadAllText(agentsPath);
        content.Should().Contain("# AGENTS.md");
        content.Should().Contain("Generated by APM CLI");
        content.Should().Contain("Files matching");
    }

    [Fact]
    public void Compile_Distributed_DryRun_DoesNotWriteFiles()
    {
        var agentsPath = Path.Combine(_tempDir, "src", "AGENTS.md");

        var distributedCompiler = A.Fake<IDistributedCompiler>();
        A.CallTo(() => distributedCompiler.CompileDistributed(A<PrimitiveCollection>._, A<Dictionary<string, object>>._))
            .Returns(new DistributedCompilationResult
            {
                Success = true,
                Placements =
                [
                    new PlacementResult
                    {
                        AgentsPath = agentsPath,
                        Instructions = [new Instruction { Name = "test", ApplyTo = "**/*.py", Content = "Test", Source = "local" }],
                        CoveragePatterns = ["**/*.py"],
                    }
                ],
                ContentMap = new Dictionary<string, string> { [agentsPath] = "# AGENTS.md content" },
                Stats = new Dictionary<string, object> { ["agents_files_generated"] = 0 },
            });
        A.CallTo(() => distributedCompiler.FormatCompilationOutput(A<bool>._, A<bool>._, A<bool>._))
            .Returns(null);

        var compiler = new AgentsCompiler(_tempDir, distributedCompiler: distributedCompiler);
        var config = new CompilationConfig { Strategy = "distributed", Target = "vscode", DryRun = true };

        var result = compiler.Compile(config, new PrimitiveCollection());

        result.Success.Should().BeTrue();
        File.Exists(agentsPath).Should().BeFalse();
        result.Content.Should().Contain("Placement Summary");
    }

    [Fact]
    public void Compile_Distributed_FailedResult_PropagatesErrors()
    {
        var distributedCompiler = A.Fake<IDistributedCompiler>();
        A.CallTo(() => distributedCompiler.CompileDistributed(A<PrimitiveCollection>._, A<Dictionary<string, object>>._))
            .Returns(new DistributedCompilationResult
            {
                Success = false,
                Errors = ["Pattern conflict detected"],
                Warnings = ["Overlapping patterns"],
                Stats = new Dictionary<string, object> { ["agents_files_generated"] = 0 },
            });
        A.CallTo(() => distributedCompiler.FormatCompilationOutput(A<bool>._, A<bool>._, A<bool>._))
            .Returns(null);

        var compiler = new AgentsCompiler(_tempDir, distributedCompiler: distributedCompiler);
        var config = new CompilationConfig { Strategy = "distributed", Target = "vscode", DryRun = true };

        var result = compiler.Compile(config, new PrimitiveCollection());

        result.Success.Should().BeFalse();
        result.Errors.Should().Contain("Pattern conflict detected");
        result.Warnings.Should().Contain("Overlapping patterns");
    }

    [Fact]
    public void Compile_Distributed_PassesConfigToCompiler()
    {
        var distributedCompiler = A.Fake<IDistributedCompiler>();
        Dictionary<string, object>? capturedConfig = null;
        A.CallTo(() => distributedCompiler.CompileDistributed(A<PrimitiveCollection>._, A<Dictionary<string, object>>._))
            .Invokes((PrimitiveCollection _, Dictionary<string, object> cfg) => capturedConfig = cfg)
            .Returns(new DistributedCompilationResult
            {
                Success = true,
                ContentMap = [],
                Placements = [],
                Stats = new Dictionary<string, object> { ["agents_files_generated"] = 0 },
            });
        A.CallTo(() => distributedCompiler.FormatCompilationOutput(A<bool>._, A<bool>._, A<bool>._))
            .Returns(null);

        var compiler = new AgentsCompiler(_tempDir, distributedCompiler: distributedCompiler);
        var config = new CompilationConfig
        {
            Strategy = "distributed",
            Target = "vscode",
            DryRun = true,
            MinInstructionsPerFile = 3,
            SourceAttribution = true,
            Debug = true,
        };

        compiler.Compile(config, new PrimitiveCollection());

        capturedConfig.Should().NotBeNull();
        capturedConfig!["min_instructions_per_file"].Should().Be(3);
        capturedConfig["source_attribution"].Should().Be(true);
        capturedConfig["debug"].Should().Be(true);
    }

    [Fact]
    public void Compile_Distributed_StatsIncludeFilesGenerated()
    {
        var path1 = Path.Combine(_tempDir, "AGENTS.md");
        var path2 = Path.Combine(_tempDir, "src", "AGENTS.md");
        Directory.CreateDirectory(Path.Combine(_tempDir, "src"));

        var distributedCompiler = A.Fake<IDistributedCompiler>();
        A.CallTo(() => distributedCompiler.CompileDistributed(A<PrimitiveCollection>._, A<Dictionary<string, object>>._))
            .Returns(new DistributedCompilationResult
            {
                Success = true,
                Placements =
                [
                    new PlacementResult { AgentsPath = path1, Instructions = [new Instruction { Name = "a", ApplyTo = "**/*.py", Content = "A", Source = "local" }], CoveragePatterns = ["**/*.py"] },
                    new PlacementResult { AgentsPath = path2, Instructions = [new Instruction { Name = "b", ApplyTo = "src/**/*.py", Content = "B", Source = "local" }], CoveragePatterns = ["src/**/*.py"] },
                ],
                ContentMap = new Dictionary<string, string>
                {
                    [path1] = "# Root AGENTS.md",
                    [path2] = "# Src AGENTS.md",
                },
                Stats = new Dictionary<string, object> { ["total_instructions_placed"] = 2, ["total_patterns_covered"] = 2 },
            });
        A.CallTo(() => distributedCompiler.FormatCompilationOutput(A<bool>._, A<bool>._, A<bool>._))
            .Returns(null);

        var compiler = new AgentsCompiler(_tempDir, distributedCompiler: distributedCompiler);
        var config = new CompilationConfig { Strategy = "distributed", Target = "vscode", DryRun = false };

        var result = compiler.Compile(config, new PrimitiveCollection());

        result.Success.Should().BeTrue();
        ((int)result.Stats["agents_files_generated"]).Should().Be(2);
    }

    // ── Primitive validation ────────────────────────────────────────

    [Fact]
    public void ValidatePrimitives_ValidInstruction_ReturnsNoErrors()
    {
        var linkResolver = A.Fake<ILinkResolver>();
        A.CallTo(() => linkResolver.ValidateLinkTargets(A<string>._, A<string>._)).Returns([]);

        var compiler = new AgentsCompiler(_tempDir, linkResolver: linkResolver);
        var primitives = new PrimitiveCollection();
        primitives.AddPrimitive(new Instruction
        {
            Name = "test",
            Description = "Test instruction",
            ApplyTo = "**/*.py",
            Content = "Test content",
            FilePath = Path.Combine(_tempDir, "test.instructions.md"),
            Source = "local"
        });

        var errors = compiler.ValidatePrimitives(primitives);

        errors.Should().BeEmpty();
    }

    // ── Chatmode handling ───────────────────────────────────────────

    [Fact]
    public void Compile_WithChatmode_WarnsIfNotFound()
    {
        var templateBuilder = A.Fake<ITemplateBuilder>();
        A.CallTo(() => templateBuilder.BuildConditionalSections(A<List<Instruction>>._)).Returns("");
        A.CallTo(() => templateBuilder.GenerateAgentsMdTemplate(A<TemplateData>._)).Returns("");
        A.CallTo(() => templateBuilder.FindChatmodeByName(A<List<Chatmode>>._, "nonexistent"))
            .Returns(null);

        var compiler = new AgentsCompiler(_tempDir, templateBuilder: templateBuilder);
        var config = new CompilationConfig
        {
            Strategy = "single-file",
            Target = "vscode",
            Chatmode = "nonexistent",
            DryRun = true
        };

        var result = compiler.Compile(config, new PrimitiveCollection());

        result.Warnings.Should().Contain(w => w.Contains("nonexistent") && w.Contains("not found"));
    }

    [Fact]
    public void Compile_WithValidChatmode_PassesToTemplate()
    {
        var chatmode = new Chatmode
        {
            Name = "architect",
            Description = "Architect mode",
            Content = "You are an architect."
        };

        var templateBuilder = A.Fake<ITemplateBuilder>();
        A.CallTo(() => templateBuilder.BuildConditionalSections(A<List<Instruction>>._)).Returns("");
        A.CallTo(() => templateBuilder.FindChatmodeByName(A<List<Chatmode>>._, "architect"))
            .Returns(chatmode);
        A.CallTo(() => templateBuilder.GenerateAgentsMdTemplate(A<TemplateData>.That.Matches(
            d => d.ChatmodeContent == "You are an architect.")))
            .Returns("compiled with chatmode");

        var compiler = new AgentsCompiler(_tempDir, templateBuilder: templateBuilder);
        var primitives = new PrimitiveCollection();
        primitives.AddPrimitive(chatmode);
        var config = new CompilationConfig
        {
            Strategy = "single-file",
            Target = "vscode",
            Chatmode = "architect",
            DryRun = true
        };

        var result = compiler.Compile(config, primitives);

        result.Content.Should().Be("compiled with chatmode");
    }
}

public class CompilationConfigDefaultTests
{
    [Fact]
    public void Defaults_AreCorrect()
    {
        var config = new CompilationConfig();

        config.OutputPath.Should().Be("AGENTS.md");
        config.Chatmode.Should().BeNull();
        config.ResolveLinks.Should().BeTrue();
        config.DryRun.Should().BeFalse();
        config.WithConstitution.Should().BeTrue();
        config.Target.Should().Be("all");
        config.Strategy.Should().Be("distributed");
        config.SingleAgents.Should().BeFalse();
        config.Trace.Should().BeFalse();
        config.LocalOnly.Should().BeFalse();
        config.Debug.Should().BeFalse();
        config.MinInstructionsPerFile.Should().Be(1);
        config.SourceAttribution.Should().BeTrue();
        config.CleanOrphaned.Should().BeFalse();
        config.Exclude.Should().BeEmpty();
    }

    [Fact]
    public void ApplyFlagPrecedence_SingleAgentsForceSingleFile()
    {
        var config = new CompilationConfig
        {
            Strategy = "distributed",
            SingleAgents = true
        };

        config.ApplyFlagPrecedence();

        config.Strategy.Should().Be("single-file");
    }

    [Fact]
    public void ApplyFlagPrecedence_NoChangeWhenSingleAgentsFalse()
    {
        var config = new CompilationConfig
        {
            Strategy = "distributed",
            SingleAgents = false
        };

        config.ApplyFlagPrecedence();

        config.Strategy.Should().Be("distributed");
    }
}

public class CompilationConfigFromApmYmlTests : IDisposable
{
    private readonly string _tempDir;
    private readonly string _originalDir;

    public CompilationConfigFromApmYmlTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
        Directory.CreateDirectory(_tempDir);
        _originalDir = Directory.GetCurrentDirectory();
        Directory.SetCurrentDirectory(_tempDir);
    }

    public void Dispose()
    {
        Directory.SetCurrentDirectory(_originalDir);
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void FromApmYml_NoFile_ReturnsDefaults()
    {
        var config = CompilationConfig.FromApmYml();

        config.OutputPath.Should().Be("AGENTS.md");
        config.Target.Should().Be("all");
        config.Strategy.Should().Be("distributed");
    }

    [Fact]
    public void FromApmYml_ParsesCompilationSection()
    {
        var yaml = """
            compilation:
              output: custom-agents.md
              target: vscode
              strategy: single-file
              source_attribution: false
            """;
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), yaml);

        var config = CompilationConfig.FromApmYml();

        config.OutputPath.Should().Be("custom-agents.md");
        config.Target.Should().Be("vscode");
        config.Strategy.Should().Be("single-file");
        config.SourceAttribution.Should().BeFalse();
    }

    [Fact]
    public void FromApmYml_OverridesFromCli()
    {
        var yaml = """
            compilation:
              output: from-yml.md
              target: vscode
            """;
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), yaml);

        var overrides = new Dictionary<string, object?>
        {
            ["output_path"] = "from-cli.md",
            ["target"] = "claude",
            ["dry_run"] = true
        };

        var config = CompilationConfig.FromApmYml(overrides);

        config.OutputPath.Should().Be("from-cli.md");
        config.Target.Should().Be("claude");
        config.DryRun.Should().BeTrue();
    }

    [Fact]
    public void FromApmYml_LegacySingleFileSupport()
    {
        var yaml = """
            compilation:
              single_file: true
            """;
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), yaml);

        var config = CompilationConfig.FromApmYml();

        config.Strategy.Should().Be("single-file");
        config.SingleAgents.Should().BeTrue();
    }

    [Fact]
    public void FromApmYml_PlacementSettings()
    {
        var yaml = """
            compilation:
              placement:
                min_instructions_per_file: 3
            """;
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), yaml);

        var config = CompilationConfig.FromApmYml();

        config.MinInstructionsPerFile.Should().Be(3);
    }

    [Fact]
    public void FromApmYml_ExcludePatterns()
    {
        var yaml = """
            compilation:
              exclude:
                - "node_modules/**"
                - "dist/**"
            """;
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), yaml);

        var config = CompilationConfig.FromApmYml();

        config.Exclude.Should().HaveCount(2);
        config.Exclude.Should().Contain("node_modules/**");
        config.Exclude.Should().Contain("dist/**");
    }

    [Fact]
    public void FromApmYml_InvalidYaml_ReturnsDefaults()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), "{{invalid yaml");

        var config = CompilationConfig.FromApmYml();

        config.OutputPath.Should().Be("AGENTS.md");
    }

    [Fact]
    public void FromApmYml_ParsesChatmodeAndResolveLinks()
    {
        var yaml = """
            compilation:
              output: CUSTOM.md
              chatmode: test-mode
              resolve_links: false
            """;
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), yaml);

        var config = CompilationConfig.FromApmYml();

        config.OutputPath.Should().Be("CUSTOM.md");
        config.Chatmode.Should().Be("test-mode");
        config.ResolveLinks.Should().BeFalse();
    }

    [Fact]
    public void FromApmYml_OverridesKeepNonOverriddenYmlValues()
    {
        var yaml = """
            compilation:
              output: from-yml.md
              chatmode: yml-mode
              resolve_links: false
            """;
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), yaml);

        var overrides = new Dictionary<string, object?>
        {
            ["output_path"] = "OVERRIDE.md",
            ["chatmode"] = "override-mode"
        };

        var config = CompilationConfig.FromApmYml(overrides);

        config.OutputPath.Should().Be("OVERRIDE.md");
        config.Chatmode.Should().Be("override-mode");
        config.ResolveLinks.Should().BeFalse(); // kept from yml
    }

    [Fact]
    public void FromApmYml_ExcludeSingleString_ConvertedToList()
    {
        var yaml = """
            compilation:
              exclude: "tmp/**"
            """;
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), yaml);

        var config = CompilationConfig.FromApmYml();

        config.Exclude.Should().HaveCount(1);
        config.Exclude.Should().Contain("tmp/**");
    }

    [Fact]
    public void FromApmYml_NoExcludeSection_DefaultsToEmpty()
    {
        var yaml = """
            compilation:
              output: AGENTS.md
            """;
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), yaml);

        var config = CompilationConfig.FromApmYml();

        config.Exclude.Should().NotBeNull();
        config.Exclude.Should().BeEmpty();
    }

    [Fact]
    public void FromApmYml_ExcludeOverride_ReplacesYmlValues()
    {
        var yaml = """
            compilation:
              exclude:
                - "apm_modules/**"
            """;
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), yaml);

        var overrides = new Dictionary<string, object?>
        {
            ["exclude"] = new List<string> { "tmp/**", "coverage/**" }
        };

        var config = CompilationConfig.FromApmYml(overrides);

        config.Exclude.Should().HaveCount(2);
        config.Exclude.Should().Contain("tmp/**");
        config.Exclude.Should().Contain("coverage/**");
        config.Exclude.Should().NotContain("apm_modules/**");
    }
}

public class CompilationConfigOverrideTests
{
    [Fact]
    public void FromApmYml_NullOverridesIgnored()
    {
        var tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
        Directory.CreateDirectory(tempDir);
        var originalDir = Directory.GetCurrentDirectory();
        try
        {
            Directory.SetCurrentDirectory(tempDir);

            var overrides = new Dictionary<string, object?>
            {
                ["chatmode"] = null,
                ["target"] = "vscode"
            };

            var config = CompilationConfig.FromApmYml(overrides);

            config.Chatmode.Should().BeNull();
            config.Target.Should().Be("vscode");
        }
        finally
        {
            Directory.SetCurrentDirectory(originalDir);
            Directory.Delete(tempDir, true);
        }
    }

    [Fact]
    public void FromApmYml_AllOverrideKeysApplied()
    {
        var overrides = new Dictionary<string, object?>
        {
            ["output_path"] = "out.md",
            ["chatmode"] = "architect",
            ["resolve_links"] = false,
            ["dry_run"] = true,
            ["with_constitution"] = false,
            ["target"] = "claude",
            ["strategy"] = "single-file",
            ["single_agents"] = true,
            ["trace"] = true,
            ["local_only"] = true,
            ["debug"] = true,
            ["min_instructions_per_file"] = 5,
            ["source_attribution"] = false,
            ["clean_orphaned"] = true,
            ["exclude"] = new List<string> { "vendor/**" }
        };

        var config = CompilationConfig.FromApmYml(overrides);

        config.OutputPath.Should().Be("out.md");
        config.Chatmode.Should().Be("architect");
        config.ResolveLinks.Should().BeFalse();
        config.DryRun.Should().BeTrue();
        config.WithConstitution.Should().BeFalse();
        config.Target.Should().Be("claude");
        config.Strategy.Should().Be("single-file");
        config.SingleAgents.Should().BeTrue();
        config.Trace.Should().BeTrue();
        config.LocalOnly.Should().BeTrue();
        config.Debug.Should().BeTrue();
        config.MinInstructionsPerFile.Should().Be(5);
        config.SourceAttribution.Should().BeFalse();
        config.CleanOrphaned.Should().BeTrue();
        config.Exclude.Should().Contain("vendor/**");
    }
}

public class CompilationResultTests
{
    [Fact]
    public void DefaultValues_AreCorrect()
    {
        var result = new CompilationResult();

        result.Success.Should().BeFalse();
        result.OutputPath.Should().BeEmpty();
        result.Content.Should().BeEmpty();
        result.Warnings.Should().BeEmpty();
        result.Errors.Should().BeEmpty();
        result.Stats.Should().BeEmpty();
    }
}

public class DirectoryMappingTests
{
    [Fact]
    public void DefaultValues_AreCorrect()
    {
        var mapping = new DirectoryMapping();

        mapping.Directory.Should().BeEmpty();
        mapping.ApplicablePatterns.Should().BeEmpty();
        mapping.Depth.Should().Be(0);
        mapping.ParentDirectory.Should().BeNull();
    }

    [Fact]
    public void CanRepresentDirectoryHierarchy()
    {
        var root = new DirectoryMapping
        {
            Directory = ".",
            ApplicablePatterns = ["**/*.py"],
            Depth = 0,
            ParentDirectory = null,
        };
        var src = new DirectoryMapping
        {
            Directory = "src",
            ApplicablePatterns = ["src/**/*.py"],
            Depth = 1,
            ParentDirectory = ".",
        };

        root.Depth.Should().BeLessThan(src.Depth);
        src.ParentDirectory.Should().Be(root.Directory);
        root.ApplicablePatterns.Should().Contain("**/*.py");
        src.ApplicablePatterns.Should().Contain("src/**/*.py");
    }
}

public class PlacementResultTests
{
    [Fact]
    public void DefaultValues_AreCorrect()
    {
        var placement = new PlacementResult();

        placement.AgentsPath.Should().BeEmpty();
        placement.Instructions.Should().BeEmpty();
        placement.InheritedInstructions.Should().BeEmpty();
        placement.CoveragePatterns.Should().BeEmpty();
        placement.SourceAttribution.Should().BeEmpty();
    }

    [Fact]
    public void CanHoldMultipleInstructionsAndPatterns()
    {
        var placement = new PlacementResult
        {
            AgentsPath = "/project/src/AGENTS.md",
            Instructions =
            [
                new Instruction { Name = "source-code", ApplyTo = "src/**/*.py", Content = "Source standards", Source = "local" },
                new Instruction { Name = "components", ApplyTo = "src/components/**/*.py", Content = "Component standards", Source = "local" },
            ],
            CoveragePatterns = ["src/**/*.py", "src/components/**/*.py"],
            SourceAttribution = new Dictionary<string, string>
            {
                ["source-code"] = "local",
                ["components"] = "local",
            },
        };

        placement.Instructions.Should().HaveCount(2);
        placement.CoveragePatterns.Should().HaveCount(2);
        placement.SourceAttribution.Should().ContainKey("source-code");
    }
}

public class DistributedCompilationResultTests
{
    [Fact]
    public void DefaultValues_AreCorrect()
    {
        var result = new DistributedCompilationResult();

        result.Success.Should().BeFalse();
        result.Placements.Should().BeEmpty();
        result.ContentMap.Should().BeEmpty();
        result.Warnings.Should().BeEmpty();
        result.Errors.Should().BeEmpty();
        result.Stats.Should().BeEmpty();
    }

    [Fact]
    public void CanRepresentSuccessfulDistributedCompilation()
    {
        var result = new DistributedCompilationResult
        {
            Success = true,
            Placements =
            [
                new PlacementResult { AgentsPath = "/root/AGENTS.md", Instructions = [new Instruction { Name = "global", ApplyTo = "**/*.py", Content = "Global", Source = "local" }], CoveragePatterns = ["**/*.py"] },
                new PlacementResult { AgentsPath = "/root/src/AGENTS.md", Instructions = [new Instruction { Name = "src", ApplyTo = "src/**/*.py", Content = "Src", Source = "local" }], CoveragePatterns = ["src/**/*.py"] },
                new PlacementResult { AgentsPath = "/root/docs/AGENTS.md", Instructions = [new Instruction { Name = "docs", ApplyTo = "docs/**/*.md", Content = "Docs", Source = "local" }], CoveragePatterns = ["docs/**/*.md"] },
            ],
            ContentMap = new Dictionary<string, string>
            {
                ["/root/AGENTS.md"] = "# AGENTS.md\nGlobal content",
                ["/root/src/AGENTS.md"] = "# AGENTS.md\nSrc content",
                ["/root/docs/AGENTS.md"] = "# AGENTS.md\nDocs content",
            },
            Stats = new Dictionary<string, object>
            {
                ["agents_files_generated"] = 3,
                ["total_instructions_placed"] = 3,
                ["total_patterns_covered"] = 3,
            },
        };

        result.Success.Should().BeTrue();
        result.Placements.Should().HaveCount(3);
        result.ContentMap.Should().HaveCount(3);
        ((int)result.Stats["agents_files_generated"]).Should().Be(3);
    }
}

public class StaticCompileAgentsMdTests : IDisposable
{
    private readonly string _tempDir;

    public StaticCompileAgentsMdTests()
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
    public void CompileAgentsMd_StaticConvenience_ThrowsWhenClaudeFormatterMissing()
    {
        // Static method defaults Target to "all", which tries Claude compilation
        // and fails because no Claude formatter is available
        var act = () => AgentsCompiler.CompileAgentsMd(
            primitives: new PrimitiveCollection(),
            dryRun: true,
            baseDir: _tempDir);

        act.Should().Throw<InvalidOperationException>()
            .WithMessage("*Compilation failed*");
    }

    [Fact]
    public void CompileAgentsMd_StaticConvenience_UsesSingleFileStrategy()
    {
        // Static method sets strategy to single-file so distributed compiler is not needed
        // But default Target "all" still tries Claude, which throws
        var act = () => AgentsCompiler.CompileAgentsMd(
            primitives: new PrimitiveCollection(),
            dryRun: false,
            baseDir: _tempDir);

        act.Should().Throw<InvalidOperationException>();
    }
}

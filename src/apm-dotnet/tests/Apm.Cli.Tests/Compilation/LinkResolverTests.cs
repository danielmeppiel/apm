using Apm.Cli.Compilation;
using Apm.Cli.Primitives;
using AwesomeAssertions;
using FakeItEasy;

namespace Apm.Cli.Tests.Compilation;

public class LinkResolverTests : IDisposable
{
    private readonly string _tempDir;

    public LinkResolverTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    // ── ResolveMarkdownLinks ────────────────────────────────────────

    [Fact]
    public void ResolveMarkdownLinks_FakeResolver_ReplacesRelativeLinks()
    {
        var resolver = A.Fake<ILinkResolver>();
        var content = "See [guide](docs/guide.md) for details.";
        A.CallTo(() => resolver.ResolveMarkdownLinks(content, _tempDir))
            .Returns($"See [guide]({Path.Combine(_tempDir, "docs", "guide.md")}) for details.");

        var result = resolver.ResolveMarkdownLinks(content, _tempDir);

        result.Should().Contain(_tempDir);
        result.Should().Contain("guide.md");
    }

    [Fact]
    public void ResolveMarkdownLinks_FakeResolver_PreservesAbsoluteLinks()
    {
        var resolver = A.Fake<ILinkResolver>();
        var content = "See [example](https://example.com) for details.";
        A.CallTo(() => resolver.ResolveMarkdownLinks(content, _tempDir))
            .Returns(content);

        var result = resolver.ResolveMarkdownLinks(content, _tempDir);

        result.Should().Contain("https://example.com");
    }

    [Fact]
    public void ResolveMarkdownLinks_FakeResolver_HandlesNoLinks()
    {
        var resolver = A.Fake<ILinkResolver>();
        var content = "No links here.";
        A.CallTo(() => resolver.ResolveMarkdownLinks(content, _tempDir))
            .Returns(content);

        var result = resolver.ResolveMarkdownLinks(content, _tempDir);

        result.Should().Be("No links here.");
    }

    [Fact]
    public void ResolveMarkdownLinks_FakeResolver_HandlesMultipleLinks()
    {
        var resolver = A.Fake<ILinkResolver>();
        var content = "See [a](a.md) and [b](b.md).";
        A.CallTo(() => resolver.ResolveMarkdownLinks(content, _tempDir))
            .Returns("See [a](resolved/a.md) and [b](resolved/b.md).");

        var result = resolver.ResolveMarkdownLinks(content, _tempDir);

        result.Should().Contain("resolved/a.md");
        result.Should().Contain("resolved/b.md");
    }

    // ── ValidateLinkTargets ─────────────────────────────────────────

    [Fact]
    public void ValidateLinkTargets_FakeResolver_NoErrors_WhenTargetsExist()
    {
        var resolver = A.Fake<ILinkResolver>();
        File.WriteAllText(Path.Combine(_tempDir, "readme.md"), "# README");
        var content = "See [readme](readme.md).";
        A.CallTo(() => resolver.ValidateLinkTargets(content, _tempDir))
            .Returns([]);

        var errors = resolver.ValidateLinkTargets(content, _tempDir);

        errors.Should().BeEmpty();
    }

    [Fact]
    public void ValidateLinkTargets_FakeResolver_ReturnsErrors_WhenTargetMissing()
    {
        var resolver = A.Fake<ILinkResolver>();
        var content = "See [missing](nonexistent.md).";
        A.CallTo(() => resolver.ValidateLinkTargets(content, _tempDir))
            .Returns(["Broken link: nonexistent.md does not exist"]);

        var errors = resolver.ValidateLinkTargets(content, _tempDir);

        errors.Should().HaveCount(1);
        errors[0].Should().Contain("nonexistent.md");
    }

    [Fact]
    public void ValidateLinkTargets_FakeResolver_MultipleBrokenLinks()
    {
        var resolver = A.Fake<ILinkResolver>();
        var content = "[a](a.md) and [b](b.md)";
        A.CallTo(() => resolver.ValidateLinkTargets(content, _tempDir))
            .Returns(["Broken link: a.md", "Broken link: b.md"]);

        var errors = resolver.ValidateLinkTargets(content, _tempDir);

        errors.Should().HaveCount(2);
    }

    [Fact]
    public void ValidateLinkTargets_FakeResolver_EmptyContent()
    {
        var resolver = A.Fake<ILinkResolver>();
        A.CallTo(() => resolver.ValidateLinkTargets("", _tempDir)).Returns([]);

        var errors = resolver.ValidateLinkTargets("", _tempDir);

        errors.Should().BeEmpty();
    }

    // ── StubLinkResolver ────────────────────────────────────────────
}

/// <summary>
/// Tests for the real UnifiedLinkResolver implementation.
/// Mirrors Python test coverage from test_link_resolver.py.
/// </summary>
public class UnifiedLinkResolverTests : IDisposable
{
    private readonly string _tempDir;

    public UnifiedLinkResolverTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    private string CreateFile(string relativePath, string content)
    {
        var fullPath = Path.Combine(_tempDir, relativePath);
        Directory.CreateDirectory(Path.GetDirectoryName(fullPath)!);
        File.WriteAllText(fullPath, content);
        return fullPath;
    }

    // ── IsExternalUrl (Python: test_preserve_external_urls, test_reject_non_http_schemes) ──

    [Theory]
    [InlineData("https://example.com/docs", true)]
    [InlineData("http://example.org", true)]
    [InlineData("javascript:alert('xss')", false)]
    [InlineData("data:text/html,test", false)]
    [InlineData("file:///etc/passwd", false)]
    [InlineData("ftp://example.com/file", false)]
    [InlineData("mailto:user@example.com", false)]
    public void IsExternalUrl_CategorizesSchemes(string url, bool expected)
    {
        UnifiedLinkResolver.IsExternalUrl(url).Should().Be(expected);
    }

    // Python: test_reject_malformed_http_urls
    [Theory]
    [InlineData("http:relative/path")]
    [InlineData("https:/no-double-slash")]
    [InlineData("http://")]
    [InlineData("https://")]
    public void IsExternalUrl_MalformedHttpNoHost_ReturnsFalse(string url)
    {
        UnifiedLinkResolver.IsExternalUrl(url).Should().BeFalse();
    }

    // Python: test_handle_urls_with_whitespace
    [Fact]
    public void IsExternalUrl_UrlWithWhitespace_TrimsAndRecognizes()
    {
        UnifiedLinkResolver.IsExternalUrl(" https://example.com ").Should().BeTrue();
        UnifiedLinkResolver.IsExternalUrl("\thttps://example.com\t").Should().BeTrue();
        UnifiedLinkResolver.IsExternalUrl(" javascript:alert('xss') ").Should().BeFalse();
    }

    // ── RegisterContexts (Python: TestContextRegistry) ──────────────

    // Python: test_register_local_contexts + test_context_paths_are_correct
    [Fact]
    public void RegisterContexts_LocalContexts_EnablesCompilationResolution()
    {
        var contextFile = CreateFile(
            Path.Combine(".apm", "context", "api-standards.context.md"),
            "# API Standards\n\nOur API guidelines...");

        var resolver = new UnifiedLinkResolver(_tempDir);
        var primitives = new PrimitiveCollection();
        primitives.AddPrimitive(new Context
        {
            Name = "api-standards",
            FilePath = contextFile,
            Content = "# API Standards\n\nOur API guidelines...",
            Source = "local"
        });
        resolver.RegisterContexts(primitives);

        var sourceFile = Path.Combine(_tempDir, ".apm", "instructions", "backend.instructions.md");
        Directory.CreateDirectory(Path.GetDirectoryName(sourceFile)!);

        var content = "Follow [API standards](../context/api-standards.context.md)";
        var result = resolver.ResolveLinksForCompilation(
            content, sourceFile, Path.Combine(_tempDir, "AGENTS.md"));

        result.Should().Contain("api-standards.context.md");
        // Link should be rewritten away from ../context/ form
        result.Should().NotContain("../context/");
    }

    // Python: test_register_dependency_contexts
    [Fact]
    public void RegisterContexts_DependencyContexts_RegistersQualifiedAndSimpleNames()
    {
        var contextFile = CreateFile(
            Path.Combine("apm_modules", "company", "standards", ".apm", "context", "api.context.md"),
            "# Company API Standards");

        var resolver = new UnifiedLinkResolver(_tempDir);
        var primitives = new PrimitiveCollection();
        primitives.AddPrimitive(new Context
        {
            Name = "api",
            FilePath = contextFile,
            Content = "# Company API Standards",
            Source = "dependency:company/standards"
        });
        resolver.RegisterContexts(primitives);

        // Simple filename lookup should resolve via registry
        var sourceFile = Path.Combine(_tempDir, ".apm", "instructions", "test.instructions.md");
        Directory.CreateDirectory(Path.GetDirectoryName(sourceFile)!);

        var content = "Follow [API](api.context.md)";
        var result = resolver.ResolveLinksForCompilation(
            content, sourceFile, Path.Combine(_tempDir, "AGENTS.md"));

        result.Should().Contain("api.context.md");
    }

    // ── ResolveLinksForCompilation (Python: TestLinkRewriting + TestCompilationLinkResolution) ──

    // Python: test_rewrite_relative_context_link_same_directory
    [Fact]
    public void ResolveLinksForCompilation_SameDirContextLink_RewritesPath()
    {
        var contextFile = CreateFile(
            Path.Combine(".apm", "context", "api.context.md"), "# API");

        var resolver = new UnifiedLinkResolver(_tempDir);
        var primitives = new PrimitiveCollection();
        primitives.AddPrimitive(new Context
        {
            Name = "api", FilePath = contextFile, Content = "# API", Source = "local"
        });
        resolver.RegisterContexts(primitives);

        var sourceFile = Path.Combine(_tempDir, ".apm", "instructions", "backend.instructions.md");
        Directory.CreateDirectory(Path.GetDirectoryName(sourceFile)!);

        var content = "Follow [API standards](./api.context.md)";
        var compiledOutput = Path.Combine(_tempDir, "backend", "AGENTS.md");

        var result = resolver.ResolveLinksForCompilation(content, sourceFile, compiledOutput);

        result.Should().Contain(".apm");
        result.Should().Contain("api.context.md");
    }

    // Python: test_rewrite_relative_context_link_parent_directory
    [Fact]
    public void ResolveLinksForCompilation_ParentDirContextLink_RewritesPath()
    {
        var contextFile = CreateFile(
            Path.Combine(".apm", "context", "api.context.md"), "# API");

        var resolver = new UnifiedLinkResolver(_tempDir);
        var primitives = new PrimitiveCollection();
        primitives.AddPrimitive(new Context
        {
            Name = "api", FilePath = contextFile, Content = "# API", Source = "local"
        });
        resolver.RegisterContexts(primitives);

        var sourceFile = Path.Combine(_tempDir, ".apm", "instructions", "backend.instructions.md");
        Directory.CreateDirectory(Path.GetDirectoryName(sourceFile)!);

        var content = "Follow [API standards](../context/api.context.md)";
        var result = resolver.ResolveLinksForCompilation(
            content, sourceFile, Path.Combine(_tempDir, "AGENTS.md"));

        result.Should().Contain(".apm");
        result.Should().Contain("api.context.md");
    }

    // Python: test_resolve_links_in_generated_agents_md
    [Fact]
    public void ResolveLinksForCompilation_CompiledAgentsMd_PointsToApmContext()
    {
        var contextFile = CreateFile(
            Path.Combine(".apm", "context", "api.context.md"), "# API");

        var resolver = new UnifiedLinkResolver(_tempDir);
        var primitives = new PrimitiveCollection();
        primitives.AddPrimitive(new Context
        {
            Name = "api", FilePath = contextFile, Content = "# API", Source = "local"
        });
        resolver.RegisterContexts(primitives);

        var sourceFile = Path.Combine(_tempDir, ".apm", "instructions", "backend.instructions.md");
        var compiledOutput = Path.Combine(_tempDir, "backend", "AGENTS.md");

        var content = "# Instructions\n\nFollow [API standards](../context/api.context.md)";
        var result = resolver.ResolveLinksForCompilation(content, sourceFile, compiledOutput);

        result.Should().Contain("api.context.md");
        result.Should().NotContain("../context/api.context.md");
    }

    // Python: test_preserve_external_urls (real resolver)
    [Fact]
    public void ResolveLinksForCompilation_ExternalUrl_Preserved()
    {
        var resolver = new UnifiedLinkResolver(_tempDir);
        var sourceFile = Path.Combine(_tempDir, ".apm", "instructions", "test.instructions.md");

        var content = "See [docs](https://example.com/docs) and [site](http://example.org)";
        var result = resolver.ResolveLinksForCompilation(
            content, sourceFile, Path.Combine(_tempDir, "AGENTS.md"));

        result.Should().Contain("https://example.com/docs");
        result.Should().Contain("http://example.org");
    }

    // Python: test_preserve_non_context_links
    [Fact]
    public void ResolveLinksForCompilation_NonContextLink_Preserved()
    {
        var resolver = new UnifiedLinkResolver(_tempDir);
        var sourceFile = Path.Combine(_tempDir, ".apm", "instructions", "test.instructions.md");

        var content = "See [README](./README.md) for more info.";
        var result = resolver.ResolveLinksForCompilation(
            content, sourceFile, Path.Combine(_tempDir, "AGENTS.md"));

        result.Should().Contain("./README.md");
    }

    // Python: test_missing_context_file
    [Fact]
    public void ResolveLinksForCompilation_MissingContext_PreservesOriginal()
    {
        var resolver = new UnifiedLinkResolver(_tempDir);
        var sourceFile = Path.Combine(_tempDir, ".apm", "instructions", "test.instructions.md");

        var content = "Follow [missing context](../context/missing.context.md)";
        var result = resolver.ResolveLinksForCompilation(
            content, sourceFile, Path.Combine(_tempDir, "AGENTS.md"));

        result.Should().Contain("../context/missing.context.md");
    }

    // Python: test_memory_context_files
    [Fact]
    public void ResolveLinksForCompilation_MemoryFile_RewritesLikeContext()
    {
        var memoryFile = CreateFile(
            Path.Combine(".apm", "context", "project.memory.md"), "# Project Memory");

        var resolver = new UnifiedLinkResolver(_tempDir);
        var primitives = new PrimitiveCollection();
        primitives.AddPrimitive(new Context
        {
            Name = "project", FilePath = memoryFile,
            Content = "# Project Memory", Source = "local"
        });
        resolver.RegisterContexts(primitives);

        var sourceFile = Path.Combine(_tempDir, ".apm", "instructions", "test.instructions.md");
        Directory.CreateDirectory(Path.GetDirectoryName(sourceFile)!);

        var content = "See [project memory](../context/project.memory.md)";
        var result = resolver.ResolveLinksForCompilation(
            content, sourceFile, Path.Combine(_tempDir, "AGENTS.md"));

        result.Should().Contain(".apm");
        result.Should().Contain("project.memory.md");
    }

    // Python: test_empty_context_registry
    [Fact]
    public void ResolveLinksForCompilation_EmptyRegistry_PreservesLinks()
    {
        var resolver = new UnifiedLinkResolver(_tempDir);
        var sourceFile = Path.Combine(_tempDir, ".apm", "instructions", "test.instructions.md");

        var content = "Follow [some context](../context/api.context.md)";
        var result = resolver.ResolveLinksForCompilation(
            content, sourceFile, Path.Combine(_tempDir, "AGENTS.md"));

        result.Should().Contain("../context/api.context.md");
    }

    // ── GetReferencedContexts (Python: TestContextValidation) ────────

    // Python: test_get_referenced_contexts
    [Fact]
    public void GetReferencedContexts_FindsReferencedContextFile()
    {
        var contextFile = CreateFile(
            Path.Combine(".apm", "context", "api-standards.context.md"), "# API Standards");
        var instructionFile = CreateFile(
            Path.Combine(".apm", "instructions", "backend.instructions.md"),
            "Follow [API standards](../context/api-standards.context.md)");

        var resolver = new UnifiedLinkResolver(_tempDir);
        var primitives = new PrimitiveCollection();
        primitives.AddPrimitive(new Context
        {
            Name = "api-standards", FilePath = contextFile,
            Content = "# API Standards", Source = "local"
        });
        resolver.RegisterContexts(primitives);

        var referenced = resolver.GetReferencedContexts([instructionFile]);

        referenced.Should().HaveCount(1);
        referenced.Should().Contain(p => p.Contains("api-standards.context.md"));
    }

    // Python: test_multiple_references
    [Fact]
    public void GetReferencedContexts_MultipleFiles_FindsAll()
    {
        var context1 = CreateFile(
            Path.Combine(".apm", "context", "api-standards.context.md"), "# API Standards");
        var context2 = CreateFile(
            Path.Combine(".apm", "context", "security.context.md"), "# Security");

        var inst1 = CreateFile(
            Path.Combine(".apm", "instructions", "backend.instructions.md"),
            "Follow [API](../context/api-standards.context.md)");
        var inst2 = CreateFile(
            Path.Combine(".apm", "instructions", "security.instructions.md"),
            "Follow [Security](../context/security.context.md)");

        var resolver = new UnifiedLinkResolver(_tempDir);
        var primitives = new PrimitiveCollection();
        primitives.AddPrimitive(new Context
        {
            Name = "api-standards", FilePath = context1,
            Content = "# API", Source = "local"
        });
        primitives.AddPrimitive(new Context
        {
            Name = "security", FilePath = context2,
            Content = "# Security", Source = "local"
        });
        resolver.RegisterContexts(primitives);

        var referenced = resolver.GetReferencedContexts([inst1, inst2]);

        referenced.Should().HaveCount(2);
        referenced.Should().Contain(p => p.Contains("api-standards.context.md"));
        referenced.Should().Contain(p => p.Contains("security.context.md"));
    }

    // ── ResolveLinksForInstallation (Python: TestInstallationLinkResolution) ──

    // Python: test_resolve_links_when_copying_from_dependency
    [Fact]
    public void ResolveLinksForInstallation_DependencyLink_PointsToApmModules()
    {
        var depContextFile = CreateFile(
            Path.Combine("apm_modules", "company", "standards", ".apm", "context", "api.context.md"),
            "# Company API Standards");

        var resolver = new UnifiedLinkResolver(_tempDir);
        var primitives = new PrimitiveCollection();
        primitives.AddPrimitive(new Context
        {
            Name = "api",
            FilePath = depContextFile,
            Content = "# Company API Standards",
            Source = "dependency:company/standards"
        });
        resolver.RegisterContexts(primitives);

        var sourceFile = Path.Combine(
            _tempDir, "apm_modules", "company", "standards", ".apm", "agents", "backend-expert.agent.md");
        Directory.CreateDirectory(Path.GetDirectoryName(sourceFile)!);

        var content = "Follow [API standards](../context/api.context.md)";
        var targetFile = Path.Combine(_tempDir, ".github", "agents", "backend-expert.agent.md");

        var result = resolver.ResolveLinksForInstallation(content, sourceFile, targetFile);

        // Should point to apm_modules (direct link to dependency)
        result.Should().Contain("apm_modules");
        result.Should().Contain("api.context.md");
    }

    // ── ResolveMarkdownLinks real implementation ────────────────────

    [Fact]
    public void ResolveMarkdownLinks_ExternalUrl_PreservesLink()
    {
        var resolver = new UnifiedLinkResolver(_tempDir);
        var content = "See [docs](https://example.com/docs) and [site](http://example.org)";

        var result = resolver.ResolveMarkdownLinks(content, _tempDir);

        result.Should().Contain("https://example.com/docs");
        result.Should().Contain("http://example.org");
    }

    [Fact]
    public void ResolveMarkdownLinks_NoLinks_ReturnsUnchanged()
    {
        var resolver = new UnifiedLinkResolver(_tempDir);
        var result = resolver.ResolveMarkdownLinks("No links here.", _tempDir);

        result.Should().Be("No links here.");
    }

    // ── ValidateLinkTargets real implementation ─────────────────────

    [Fact]
    public void ValidateLinkTargets_ExistingFile_NoErrors()
    {
        CreateFile("readme.md", "# README");
        var resolver = new UnifiedLinkResolver(_tempDir);

        var errors = resolver.ValidateLinkTargets("See [readme](readme.md).", _tempDir);

        errors.Should().BeEmpty();
    }

    [Fact]
    public void ValidateLinkTargets_MissingFile_ReturnsError()
    {
        var resolver = new UnifiedLinkResolver(_tempDir);

        var errors = resolver.ValidateLinkTargets("See [missing](nonexistent.md).", _tempDir);

        errors.Should().HaveCount(1);
        errors[0].Should().Contain("nonexistent.md");
    }

    [Fact]
    public void ValidateLinkTargets_EmptyContent_NoErrors()
    {
        var resolver = new UnifiedLinkResolver(_tempDir);

        resolver.ValidateLinkTargets("", _tempDir).Should().BeEmpty();
    }

    [Fact]
    public void ValidateLinkTargets_ExternalUrl_Skipped()
    {
        var resolver = new UnifiedLinkResolver(_tempDir);

        resolver.ValidateLinkTargets("See [docs](https://example.com).", _tempDir)
            .Should().BeEmpty();
    }

    [Fact]
    public void ValidateLinkTargets_MultipleBrokenLinks_ReturnsAll()
    {
        var resolver = new UnifiedLinkResolver(_tempDir);

        var errors = resolver.ValidateLinkTargets("[a](a.md) and [b](b.md)", _tempDir);

        errors.Should().HaveCount(2);
    }
}

/// <summary>Stub implementation for testing — passes through content unchanged.</summary>
internal class StubLinkResolver : ILinkResolver
{
    public string ResolveMarkdownLinks(string content, string baseDir) => content;
    public List<string> ValidateLinkTargets(string content, string baseDir) => [];
}

public class StubLinkResolverTests : IDisposable
{
    private readonly string _tempDir;

    public StubLinkResolverTests()
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
    public void StubResolver_ResolveMarkdownLinks_ReturnsContentUnchanged()
    {
        ILinkResolver resolver = new StubLinkResolver();
        var content = "See [link](file.md) here.";

        var result = resolver.ResolveMarkdownLinks(content, _tempDir);

        result.Should().Be(content);
    }

    [Fact]
    public void StubResolver_ValidateLinkTargets_ReturnsEmptyList()
    {
        ILinkResolver resolver = new StubLinkResolver();

        var errors = resolver.ValidateLinkTargets("See [link](missing.md)", _tempDir);

        errors.Should().BeEmpty();
    }

    // ── Integration with AgentsCompiler ─────────────────────────────

    [Fact]
    public void Compiler_ValidationWarns_OnBrokenLinks()
    {
        var linkResolver = A.Fake<ILinkResolver>();
        var templateBuilder = A.Fake<ITemplateBuilder>();

        A.CallTo(() => linkResolver.ValidateLinkTargets(A<string>._, A<string>._))
            .Returns(["Broken link: missing.md"]);
        A.CallTo(() => templateBuilder.BuildConditionalSections(A<List<Instruction>>._)).Returns("");
        A.CallTo(() => templateBuilder.GenerateAgentsMdTemplate(A<TemplateData>._)).Returns("");

        var compiler = new AgentsCompiler(_tempDir,
            templateBuilder: templateBuilder,
            linkResolver: linkResolver);

        var primitives = new PrimitiveCollection();
        primitives.AddPrimitive(new Instruction
        {
            Name = "test",
            Description = "Test",
            ApplyTo = "**",
            Content = "See [missing](missing.md)",
            FilePath = Path.Combine(_tempDir, "test.instructions.md"),
            Source = "local"
        });

        var config = new CompilationConfig { Strategy = "single-file", Target = "vscode", DryRun = true };
        var result = compiler.Compile(config, primitives);

        result.Warnings.Should().Contain(w => w.Contains("Broken link"));
    }

    [Fact]
    public void Compiler_NoWarnings_WhenLinksValid()
    {
        var linkResolver = A.Fake<ILinkResolver>();
        var templateBuilder = A.Fake<ITemplateBuilder>();

        A.CallTo(() => linkResolver.ValidateLinkTargets(A<string>._, A<string>._)).Returns([]);
        A.CallTo(() => templateBuilder.BuildConditionalSections(A<List<Instruction>>._)).Returns("");
        A.CallTo(() => templateBuilder.GenerateAgentsMdTemplate(A<TemplateData>._)).Returns("");

        var compiler = new AgentsCompiler(_tempDir,
            templateBuilder: templateBuilder,
            linkResolver: linkResolver);

        var primitives = new PrimitiveCollection();
        primitives.AddPrimitive(new Instruction
        {
            Name = "test",
            Description = "Test",
            ApplyTo = "**",
            Content = "See [readme](README.md)",
            FilePath = Path.Combine(_tempDir, "test.instructions.md"),
            Source = "local"
        });

        var config = new CompilationConfig { Strategy = "single-file", Target = "vscode", DryRun = true };
        var result = compiler.Compile(config, primitives);

        result.Warnings.Should().NotContain(w => w.Contains("Broken link"));
    }
}

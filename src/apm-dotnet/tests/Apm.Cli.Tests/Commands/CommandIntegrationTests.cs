using Apm.Cli.Commands;
using Apm.Cli.Commands.Config;
using Apm.Cli.Commands.Deps;
using AwesomeAssertions;
using Spectre.Console.Cli;

namespace Apm.Cli.Tests.Commands;

[CollectionDefinition("Sequential", DisableParallelization = true)]
public class SequentialCollection;

// ── InitCommand Tests ───────────────────────────────────────────────

[Collection("Sequential")]
public class InitCommandTests : IDisposable
{
    private readonly string _tempDir;
    private readonly string _originalDir;

    public InitCommandTests()
    {
        _originalDir = Directory.GetCurrentDirectory();
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm-test-{Guid.NewGuid()}");
        Directory.CreateDirectory(_tempDir);
        Directory.SetCurrentDirectory(_tempDir);
    }

    public void Dispose()
    {
        try { Directory.SetCurrentDirectory(_originalDir); } catch { }
        try { if (Directory.Exists(_tempDir)) Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void Init_CreatesApmYml()
    {
        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddCommand<InitCommand>("init");
            config.PropagateExceptions();
        });

        app.Run(["init", "-y"]);

        // InitCommand writes apm.yml in cwd
        var cwd = Directory.GetCurrentDirectory();
        File.Exists(Path.Combine(cwd, "apm.yml")).Should().BeTrue();
    }

    [Fact]
    public void Init_ApmYmlContainsProjectName()
    {
        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddCommand<InitCommand>("init");
            config.PropagateExceptions();
        });

        app.Run(["init", "-y"]);

        var cwd = Directory.GetCurrentDirectory();
        var content = File.ReadAllText(Path.Combine(cwd, "apm.yml"));
        content.Should().Contain("name:");
        content.Should().Contain("version:");
    }

    [Fact]
    public void Init_WithProjectName_CreatesSubdirectory()
    {
        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddCommand<InitCommand>("init");
            config.PropagateExceptions();
        });

        app.Run(["init", "my-project", "-y"]);

        var projectDir = Path.Combine(_tempDir, "my-project");
        Directory.Exists(projectDir).Should().BeTrue();
        File.Exists(Path.Combine(projectDir, "apm.yml")).Should().BeTrue();
    }

    [Fact]
    public void Init_ExplicitDot_SameAsCurrentDirectory()
    {
        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddCommand<InitCommand>("init");
            config.PropagateExceptions();
        });

        app.Run(["init", ".", "-y"]);

        var cwd = Directory.GetCurrentDirectory();
        File.Exists(Path.Combine(cwd, "apm.yml")).Should().BeTrue();
    }

    [Fact]
    public void Init_ExistingApmYml_WithYes_Overwrites()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), "name: existing-project\nversion: 0.1.0\n");

        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddCommand<InitCommand>("init");
            config.PropagateExceptions();
        });

        var exitCode = app.Run(["init", "-y"]);

        exitCode.Should().Be(0);
        var content = File.ReadAllText(Path.Combine(_tempDir, "apm.yml"));
        content.Should().Contain("dependencies:");
    }

    [Fact]
    public void Init_ApmYmlHasDependenciesAndScripts()
    {
        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddCommand<InitCommand>("init");
            config.PropagateExceptions();
        });

        app.Run(["init", "test-project", "-y"]);

        var projectDir = Path.Combine(_tempDir, "test-project");
        var content = File.ReadAllText(Path.Combine(projectDir, "apm.yml"));
        content.Should().Contain("name:");
        content.Should().Contain("version:");
        content.Should().Contain("dependencies:");
        content.Should().Contain("scripts:");
    }

    [Fact]
    public void Init_DoesNotCreateSkillMd()
    {
        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddCommand<InitCommand>("init");
            config.PropagateExceptions();
        });

        app.Run(["init", "-y"]);

        var cwd = Directory.GetCurrentDirectory();
        File.Exists(Path.Combine(cwd, "SKILL.md")).Should().BeFalse();
    }
}

// ── InstallCommand Tests ────────────────────────────────────────────

[Collection("Sequential")]
public class InstallCommandTests : IDisposable
{
    private readonly string _tempDir;
    private readonly string _originalDir;

    public InstallCommandTests()
    {
        _originalDir = Directory.GetCurrentDirectory();
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm-test-{Guid.NewGuid()}");
        Directory.CreateDirectory(_tempDir);
        Directory.SetCurrentDirectory(_tempDir);
    }

    public void Dispose()
    {
        try { Directory.SetCurrentDirectory(_originalDir); } catch { }
        try { if (Directory.Exists(_tempDir)) Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void Install_NoApmYml_NoPackages_ReturnsError()
    {
        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddCommand<InstallCommand>("install");
            config.PropagateExceptions();
        });

        var exitCode = app.Run(["install"]);

        exitCode.Should().Be(1);
    }

    [Fact]
    public void Install_NoApmYml_WithPackage_CreatesApmYml()
    {
        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddCommand<InstallCommand>("install");
            // Don't propagate exceptions - install will fail on download but apm.yml should be created
        });

        app.Run(["install", "test/package"]);

        // Auto-bootstrap should create apm.yml even if download fails
        File.Exists(Path.Combine(_tempDir, "apm.yml")).Should().BeTrue();
        var content = File.ReadAllText(Path.Combine(_tempDir, "apm.yml"));
        content.Should().Contain("test/package");
    }

    [Fact]
    public void Install_InvalidPackageFormat_ShowsError()
    {
        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddCommand<InstallCommand>("install");
        });

        // invalid-package has no slash, so it should fail validation
        app.Run(["install", "invalid-package"]);

        // apm.yml still created by auto-bootstrap, but invalid pkg not added
        File.Exists(Path.Combine(_tempDir, "apm.yml")).Should().BeTrue();
        var content = File.ReadAllText(Path.Combine(_tempDir, "apm.yml"));
        content.Should().NotContain("invalid-package");
    }
}

// ── CompileCommand Tests ────────────────────────────────────────────

[Collection("Sequential")]
public class CompileCommandTests : IDisposable
{
    private readonly string _tempDir;
    private readonly string _originalDir;

    public CompileCommandTests()
    {
        _originalDir = Directory.GetCurrentDirectory();
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm-test-{Guid.NewGuid()}");
        Directory.CreateDirectory(_tempDir);
        Directory.SetCurrentDirectory(_tempDir);
    }

    public void Dispose()
    {
        try { Directory.SetCurrentDirectory(_originalDir); } catch { }
        try { if (Directory.Exists(_tempDir)) Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void Compile_WithoutApmYml_ReturnsError()
    {
        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddCommand<CompileCommand>("compile");
            config.PropagateExceptions();
        });

        var exitCode = app.Run(["compile"]);

        exitCode.Should().Be(1);
    }

    [Fact]
    public void Compile_WithApmYmlButNoContent_ReturnsError()
    {
        CreateMinimalApmYml();

        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddCommand<CompileCommand>("compile");
            config.PropagateExceptions();
        });

        var exitCode = app.Run(["compile"]);

        exitCode.Should().Be(1);
    }

    [Fact]
    public void Compile_WithInstructions_DryRun_SingleFile_Succeeds()
    {
        CreateMinimalApmYml();
        CreateSampleInstruction();

        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddCommand<CompileCommand>("compile");
            config.PropagateExceptions();
        });

        var exitCode = app.Run(["compile", "--dry-run", "--single-agents", "--target", "vscode"]);

        exitCode.Should().Be(0);
    }

    [Fact]
    public void Compile_SingleFile_WritesAgentsMd()
    {
        CreateMinimalApmYml();
        CreateSampleInstruction();

        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddCommand<CompileCommand>("compile");
            config.PropagateExceptions();
        });

        app.Run(["compile", "--single-agents", "--target", "vscode"]);

        File.Exists(Path.Combine(_tempDir, "AGENTS.md")).Should().BeTrue();
    }

    [Fact]
    public void Compile_NoConstitution_SkipsConstitution()
    {
        CreateMinimalApmYml();
        CreateSampleInstruction();

        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddCommand<CompileCommand>("compile");
            config.PropagateExceptions();
        });

        var exitCode = app.Run(["compile", "--single-agents", "--target", "vscode", "--no-constitution"]);

        exitCode.Should().Be(0);
    }

    [Fact]
    public void Compile_VerboseFlag_Succeeds()
    {
        CreateMinimalApmYml();
        CreateSampleInstruction();

        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddCommand<CompileCommand>("compile");
            config.PropagateExceptions();
        });

        var exitCode = app.Run(["compile", "--verbose", "--single-agents", "--target", "vscode"]);

        exitCode.Should().Be(0);
    }

    private void CreateMinimalApmYml()
    {
        var yaml = """
            name: test-project
            version: 1.0.0
            description: Test project
            author: Test
            dependencies:
              apm: []
              mcp: []
            scripts: {}
            """;
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), yaml);
    }

    private void CreateSampleInstruction()
    {
        var instrDir = Path.Combine(_tempDir, ".apm", "instructions");
        Directory.CreateDirectory(instrDir);
        var content = """
            ---
            description: Python style guide
            applyTo: "**/*.py"
            ---
            Use type hints for all function parameters.
            """;
        File.WriteAllText(Path.Combine(instrDir, "python-style.instructions.md"), content);
    }
}

// ── ConfigCommand Tests ─────────────────────────────────────────────

[Collection("Sequential")]
public class ConfigCommandTests : IDisposable
{
    private readonly string _tempDir;
    private readonly string _originalDir;

    public ConfigCommandTests()
    {
        _originalDir = Directory.GetCurrentDirectory();
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm-test-{Guid.NewGuid()}");
        Directory.CreateDirectory(_tempDir);
        Directory.SetCurrentDirectory(_tempDir);
    }

    public void Dispose()
    {
        try { Directory.SetCurrentDirectory(_originalDir); } catch { }
        try { if (Directory.Exists(_tempDir)) Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void ConfigGet_WithValidKey_ReturnsZero()
    {
        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddBranch("config", cfg =>
            {
                cfg.AddCommand<ConfigGetCommand>("get");
            });
            config.PropagateExceptions();
        });

        var exitCode = app.Run(["config", "get", "auto-integrate"]);

        exitCode.Should().Be(0);
    }

    [Fact]
    public void ConfigGet_WithInvalidKey_ReturnsError()
    {
        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddBranch("config", cfg =>
            {
                cfg.AddCommand<ConfigGetCommand>("get");
            });
            config.PropagateExceptions();
        });

        var exitCode = app.Run(["config", "get", "nonexistent-key"]);

        exitCode.Should().Be(1);
    }

    [Fact]
    public void ConfigSet_AutoIntegrate_Succeeds()
    {
        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddBranch("config", cfg =>
            {
                cfg.AddCommand<ConfigSetCommand>("set");
            });
            config.PropagateExceptions();
        });

        var exitCode = app.Run(["config", "set", "auto-integrate", "true"]);

        exitCode.Should().Be(0);
    }

    [Fact]
    public void ConfigSet_InvalidKey_ReturnsError()
    {
        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddBranch("config", cfg =>
            {
                cfg.AddCommand<ConfigSetCommand>("set");
            });
            config.PropagateExceptions();
        });

        var exitCode = app.Run(["config", "set", "bad-key", "value"]);

        exitCode.Should().Be(1);
    }

    [Fact]
    public void ConfigShow_ReturnsZero()
    {
        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddBranch("config", cfg =>
            {
                cfg.AddCommand<ConfigShowCommand>("show");
            });
            config.PropagateExceptions();
        });

        var exitCode = app.Run(["config", "show"]);

        exitCode.Should().Be(0);
    }
}

// ── ListCommand Tests ───────────────────────────────────────────────

[Collection("Sequential")]
public class ListCommandTests : IDisposable
{
    private readonly string _tempDir;
    private readonly string _originalDir;

    public ListCommandTests()
    {
        _originalDir = Directory.GetCurrentDirectory();
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm-test-{Guid.NewGuid()}");
        Directory.CreateDirectory(_tempDir);
        Directory.SetCurrentDirectory(_tempDir);
    }

    public void Dispose()
    {
        try { Directory.SetCurrentDirectory(_originalDir); } catch { }
        try { if (Directory.Exists(_tempDir)) Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void List_WithNoApmYml_ReturnsZero()
    {
        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddCommand<ListCommand>("list");
            config.PropagateExceptions();
        });

        var exitCode = app.Run(["list"]);

        exitCode.Should().Be(0);
    }

    [Fact]
    public void List_WithScripts_ReturnsZero()
    {
        var yaml = """
            name: test-project
            version: 1.0.0
            description: Test
            author: Test
            scripts:
              start: "codex run main.prompt.md"
              test: "echo hello"
            """;
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), yaml);

        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddCommand<ListCommand>("list");
            config.PropagateExceptions();
        });

        var exitCode = app.Run(["list"]);

        exitCode.Should().Be(0);
    }

    [Fact]
    public void List_WithEmptyScripts_ReturnsZero()
    {
        var yaml = """
            name: test-project
            version: 1.0.0
            description: Test
            author: Test
            scripts: {}
            """;
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), yaml);

        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddCommand<ListCommand>("list");
            config.PropagateExceptions();
        });

        var exitCode = app.Run(["list"]);

        exitCode.Should().Be(0);
    }
}

// ── DepsListCommand Tests ───────────────────────────────────────────

[Collection("Sequential")]
public class DepsListCommandTests : IDisposable
{
    private readonly string _tempDir;
    private readonly string _originalDir;

    public DepsListCommandTests()
    {
        _originalDir = Directory.GetCurrentDirectory();
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm-test-{Guid.NewGuid()}");
        Directory.CreateDirectory(_tempDir);
        Directory.SetCurrentDirectory(_tempDir);
    }

    public void Dispose()
    {
        try { Directory.SetCurrentDirectory(_originalDir); } catch { }
        try { if (Directory.Exists(_tempDir)) Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void DepsList_NoApmModules_ReturnsZero()
    {
        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddBranch("deps", deps =>
            {
                deps.AddCommand<DepsListCommand>("list");
            });
            config.PropagateExceptions();
        });

        var exitCode = app.Run(["deps", "list"]);

        exitCode.Should().Be(0);
    }

    [Fact]
    public void DepsList_WithEmptyApmModules_ReturnsZero()
    {
        Directory.CreateDirectory(Path.Combine(_tempDir, "apm_modules"));

        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddBranch("deps", deps =>
            {
                deps.AddCommand<DepsListCommand>("list");
            });
            config.PropagateExceptions();
        });

        var exitCode = app.Run(["deps", "list"]);

        exitCode.Should().Be(0);
    }

    [Fact]
    public void DepsList_WithInstalledPackage_ReturnsZero()
    {
        var yaml = """
            name: test-project
            version: 1.0.0
            description: Test
            author: Test
            dependencies:
              apm:
                - testowner/testrepo
            """;
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), yaml);

        var pkgDir = Path.Combine(_tempDir, "apm_modules", "testowner", "testrepo");
        Directory.CreateDirectory(pkgDir);
        var pkgYaml = """
            name: testrepo
            version: 1.0.0
            description: A test package
            author: TestOwner
            """;
        File.WriteAllText(Path.Combine(pkgDir, "apm.yml"), pkgYaml);

        var app = new CommandApp();
        app.Configure(config =>
        {
            config.AddBranch("deps", deps =>
            {
                deps.AddCommand<DepsListCommand>("list");
            });
            config.PropagateExceptions();
        });

        var exitCode = app.Run(["deps", "list"]);

        exitCode.Should().Be(0);
    }
}

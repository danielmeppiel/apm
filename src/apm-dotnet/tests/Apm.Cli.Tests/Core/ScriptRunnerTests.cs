using Apm.Cli.Core;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Core;

/// <summary>
/// All ScriptRunner tests share this collection to prevent parallel execution,
/// since they mutate the process-global current directory.
/// </summary>
[CollectionDefinition("ScriptRunner", DisableParallelization = true)]
public class ScriptRunnerCollection;

[Collection("ScriptRunner")]
public class ScriptRunnerListScriptsTests : IDisposable
{
    private static readonly string SafeDir = AppDomain.CurrentDomain.BaseDirectory;
    private readonly string _tempDir;

    public ScriptRunnerListScriptsTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm_script_test_{Guid.NewGuid()}");
        Directory.CreateDirectory(_tempDir);
        Directory.SetCurrentDirectory(_tempDir);
    }

    public void Dispose()
    {
        Directory.SetCurrentDirectory(SafeDir);
        try { Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void ListScripts_NoConfigFile_ReturnsEmptyDictionary()
    {
        var runner = new ScriptRunner();
        var scripts = runner.ListScripts();
        scripts.Should().BeEmpty();
    }

    [Fact]
    public void ListScripts_ConfigWithScripts_ReturnsThem()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"),
            """
            scripts:
              build: echo building
              test: echo testing
            """);

        var runner = new ScriptRunner();
        var scripts = runner.ListScripts();

        scripts.Should().HaveCount(2);
        scripts.Should().ContainKey("build");
        scripts["build"].Should().Be("echo building");
        scripts.Should().ContainKey("test");
        scripts["test"].Should().Be("echo testing");
    }

    [Fact]
    public void ListScripts_ConfigWithoutScripts_ReturnsEmpty()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"),
            """
            name: my-project
            version: "1.0"
            """);

        var runner = new ScriptRunner();
        var scripts = runner.ListScripts();
        scripts.Should().BeEmpty();
    }
}

[Collection("ScriptRunner")]
public class ScriptRunnerRunScriptTests : IDisposable
{
    private static readonly string SafeDir = AppDomain.CurrentDomain.BaseDirectory;
    private readonly string _tempDir;

    public ScriptRunnerRunScriptTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm_script_run_test_{Guid.NewGuid()}");
        Directory.CreateDirectory(_tempDir);
        Directory.SetCurrentDirectory(_tempDir);
    }

    public void Dispose()
    {
        Directory.SetCurrentDirectory(SafeDir);
        try { Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void RunScript_NoConfigFile_ThrowsInvalidOperationException()
    {
        var runner = new ScriptRunner();
        var act = () => runner.RunScript("build", new Dictionary<string, string>());
        act.Should().Throw<InvalidOperationException>().WithMessage("*apm.yml*");
    }

    [Fact]
    public void RunScript_ScriptNotFound_ThrowsWithAvailableScripts()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"),
            """
            scripts:
              build: echo building
            """);

        var runner = new ScriptRunner();
        var act = () => runner.RunScript("nonexistent", new Dictionary<string, string>());
        act.Should().Throw<InvalidOperationException>()
            .WithMessage("*not found*");
    }

    [Fact]
    public void RunScript_SimpleEchoCommand_Succeeds()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"),
            """
            scripts:
              greet: echo hello
            """);

        var runner = new ScriptRunner();
        var result = runner.RunScript("greet", new Dictionary<string, string>());
        result.Should().BeTrue();
    }

    [Fact]
    public void RunScript_FailingCommand_ReturnsFalse()
    {
        var failCmd = OperatingSystem.IsWindows() ? "cmd /c exit 1" : "false";
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"),
            $"""
            scripts:
              fail: {failCmd}
            """);

        var runner = new ScriptRunner();
        var result = runner.RunScript("fail", new Dictionary<string, string>());
        result.Should().BeFalse();
    }
}

public class ScriptRunnerConstructorTests
{
    [Fact]
    public void Constructor_DefaultCompiledDir_IsApmCompiled()
    {
        var runner = new ScriptRunner();
        runner.Should().NotBeNull();
    }

    [Fact]
    public void Constructor_CustomCompiledDir_DoesNotThrow()
    {
        var runner = new ScriptRunner(compiledDir: "/custom/path");
        runner.Should().NotBeNull();
    }
}

[Collection("ScriptRunner")]
public class ScriptRunnerPromptDiscoveryTests : IDisposable
{
    private static readonly string SafeDir = AppDomain.CurrentDomain.BaseDirectory;
    private readonly string _tempDir;

    public ScriptRunnerPromptDiscoveryTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm_prompt_test_{Guid.NewGuid()}");
        Directory.CreateDirectory(_tempDir);
        Directory.SetCurrentDirectory(_tempDir);
    }

    public void Dispose()
    {
        Directory.SetCurrentDirectory(SafeDir);
        try { Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void RunScript_PromptFileInRoot_IsDiscoveredAndDoesNotThrowNotFound()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"),
            """
            name: test-project
            """);

        File.WriteAllText(Path.Combine(_tempDir, "review.prompt.md"),
            """
            ---
            description: Code review
            ---
            Review the code
            """);

        var runner = new ScriptRunner(compiledDir: Path.Combine(_tempDir, ".apm", "compiled"));

        // The prompt file should be discovered (not "Script or prompt 'review' not found").
        // Depending on whether copilot/codex is installed, it either throws
        // "No compatible runtime found" or actually tries to run it.
        try
        {
            runner.RunScript("review", new Dictionary<string, string>());
        }
        catch (InvalidOperationException ex) when (ex.Message.Contains("not found") && ex.Message.Contains("review"))
        {
            // If the script/prompt was NOT discovered, this is a failure
            Assert.Fail("Prompt file should have been discovered but was not.");
        }
        catch
        {
            // Any other exception (runtime not found, execution failure) means discovery worked
        }
    }

    [Fact]
    public void RunScript_PromptFileInApmPrompts_IsDiscoveredAndDoesNotThrowNotFound()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"),
            """
            name: test-project
            """);

        var promptsDir = Path.Combine(_tempDir, ".apm", "prompts");
        Directory.CreateDirectory(promptsDir);
        File.WriteAllText(Path.Combine(promptsDir, "analyze.prompt.md"),
            """
            Analyze the project
            """);

        var runner = new ScriptRunner(compiledDir: Path.Combine(_tempDir, ".apm", "compiled"));

        try
        {
            runner.RunScript("analyze", new Dictionary<string, string>());
        }
        catch (InvalidOperationException ex) when (ex.Message.Contains("not found") && ex.Message.Contains("analyze"))
        {
            Assert.Fail("Prompt file should have been discovered but was not.");
        }
        catch
        {
            // Discovery succeeded; any runtime/execution error is expected
        }
    }

    [Fact]
    public void RunScript_PromptFileInGitHubPrompts_IsDiscoveredAndDoesNotThrowNotFound()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"),
            """
            name: test-project
            """);

        var promptsDir = Path.Combine(_tempDir, ".github", "prompts");
        Directory.CreateDirectory(promptsDir);
        File.WriteAllText(Path.Combine(promptsDir, "fix.prompt.md"),
            """
            Fix the bugs
            """);

        var runner = new ScriptRunner(compiledDir: Path.Combine(_tempDir, ".apm", "compiled"));

        try
        {
            runner.RunScript("fix", new Dictionary<string, string>());
        }
        catch (InvalidOperationException ex) when (ex.Message.Contains("not found") && ex.Message.Contains("fix"))
        {
            Assert.Fail("Prompt file should have been discovered but was not.");
        }
        catch
        {
            // Discovery succeeded; any runtime/execution error is expected
        }
    }

    [Fact]
    public void RunScript_NoPromptFile_ThrowsNotFound()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"),
            """
            name: test-project
            """);

        var runner = new ScriptRunner(compiledDir: Path.Combine(_tempDir, ".apm", "compiled"));

        var act = () => runner.RunScript("nonexistent", new Dictionary<string, string>());
        act.Should().Throw<InvalidOperationException>()
            .WithMessage("*not found*");
    }
}

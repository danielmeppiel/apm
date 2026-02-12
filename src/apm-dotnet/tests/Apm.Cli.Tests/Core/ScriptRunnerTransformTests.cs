using Apm.Cli.Core;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Core;

/// <summary>
/// Tests ported from Python test_script_runner.py – TransformRuntimeCommand tests.
/// </summary>
public class ScriptRunnerTransformRuntimeCommandTests
{
    private readonly ScriptRunner _runner = new();
    private const string CompiledContent = "You are a helpful assistant. Say hello to TestUser!";
    private const string CompiledPath = ".apm/compiled/hello-world.txt";
    private const string PromptFile = "hello-world.prompt.md";

    [Fact]
    public void TransformRuntimeCommand_SimpleCodex_ReturnsCodexExec()
    {
        var result = _runner.TransformRuntimeCommand(
            "codex hello-world.prompt.md", PromptFile, CompiledContent, CompiledPath);

        result.Should().Be("codex exec");
    }

    [Fact]
    public void TransformRuntimeCommand_CodexWithFlags_PreservesFlags()
    {
        var result = _runner.TransformRuntimeCommand(
            "codex --skip-git-repo-check hello-world.prompt.md", PromptFile, CompiledContent, CompiledPath);

        result.Should().Be("codex exec --skip-git-repo-check");
    }

    [Fact]
    public void TransformRuntimeCommand_CodexMultipleFlags_PreservesAllFlags()
    {
        var result = _runner.TransformRuntimeCommand(
            "codex --verbose --skip-git-repo-check hello-world.prompt.md", PromptFile, CompiledContent, CompiledPath);

        result.Should().Be("codex exec --verbose --skip-git-repo-check");
    }

    [Fact]
    public void TransformRuntimeCommand_EnvVarSimpleCodex_PreservesEnvAndAddsExec()
    {
        var result = _runner.TransformRuntimeCommand(
            "DEBUG=true codex hello-world.prompt.md", PromptFile, CompiledContent, CompiledPath);

        result.Should().Be("DEBUG=true codex exec");
    }

    [Fact]
    public void TransformRuntimeCommand_EnvVarCodexWithFlags_PreservesAll()
    {
        var result = _runner.TransformRuntimeCommand(
            "DEBUG=true codex --skip-git-repo-check hello-world.prompt.md", PromptFile, CompiledContent, CompiledPath);

        result.Should().Be("DEBUG=true codex exec --skip-git-repo-check");
    }

    [Fact]
    public void TransformRuntimeCommand_SimpleLlm_ReturnsLlm()
    {
        var result = _runner.TransformRuntimeCommand(
            "llm hello-world.prompt.md", PromptFile, CompiledContent, CompiledPath);

        result.Should().Be("llm");
    }

    [Fact]
    public void TransformRuntimeCommand_LlmWithOptions_PreservesOptions()
    {
        var result = _runner.TransformRuntimeCommand(
            "llm hello-world.prompt.md --model gpt-4", PromptFile, CompiledContent, CompiledPath);

        result.Should().Be("llm --model gpt-4");
    }

    [Fact]
    public void TransformRuntimeCommand_BareFile_DefaultsToCodexExec()
    {
        var result = _runner.TransformRuntimeCommand(
            "hello-world.prompt.md", PromptFile, CompiledContent, CompiledPath);

        result.Should().Be("codex exec");
    }

    [Fact]
    public void TransformRuntimeCommand_UnrecognizedCommand_FallbackReplacesPath()
    {
        var result = _runner.TransformRuntimeCommand(
            "unknown-command hello-world.prompt.md", PromptFile, CompiledContent, CompiledPath);

        result.Should().Be($"unknown-command {CompiledPath}");
    }

    [Fact]
    public void TransformRuntimeCommand_SimpleCopilot_ReturnsCopilot()
    {
        var result = _runner.TransformRuntimeCommand(
            "copilot hello-world.prompt.md", PromptFile, CompiledContent, CompiledPath);

        result.Should().Be("copilot");
    }

    [Fact]
    public void TransformRuntimeCommand_CopilotWithFlags_PreservesFlags()
    {
        var result = _runner.TransformRuntimeCommand(
            "copilot --log-level all --log-dir copilot-logs hello-world.prompt.md",
            PromptFile, CompiledContent, CompiledPath);

        result.Should().Be("copilot --log-level all --log-dir copilot-logs");
    }

    [Fact]
    public void TransformRuntimeCommand_CopilotRemovesPFlag()
    {
        var result = _runner.TransformRuntimeCommand(
            "copilot -p hello-world.prompt.md --log-level all",
            PromptFile, CompiledContent, CompiledPath);

        result.Should().Be("copilot --log-level all");
    }
}

/// <summary>
/// Tests ported from Python test_script_runner.py – DetectRuntime tests.
/// </summary>
public class ScriptRunnerDetectRuntimeTests
{
    [Theory]
    [InlineData("copilot --log-level all", "copilot")]
    [InlineData("codex exec --skip-git-repo-check", "codex")]
    [InlineData("llm --model gpt-4", "llm")]
    [InlineData("unknown-command", "unknown")]
    public void DetectRuntime_ReturnsExpectedRuntime(string command, string expectedRuntime)
    {
        ScriptRunner.DetectRuntime(command).Should().Be(expectedRuntime);
    }
}

/// <summary>
/// Tests ported from Python test_script_runner.py – PromptCompiler / SubstituteParameters tests.
/// </summary>
public class ScriptRunnerSubstituteParametersTests
{
    [Fact]
    public void SubstituteParameters_Simple_ReplacesPlaceholder()
    {
        var result = ScriptRunner.SubstituteParameters(
            "Hello ${input:name}!", new Dictionary<string, string> { ["name"] = "World" });

        result.Should().Be("Hello World!");
    }

    [Fact]
    public void SubstituteParameters_Multiple_ReplacesAll()
    {
        var result = ScriptRunner.SubstituteParameters(
            "Service: ${input:service}, Environment: ${input:env}",
            new Dictionary<string, string> { ["service"] = "api", ["env"] = "production" });

        result.Should().Be("Service: api, Environment: production");
    }

    [Fact]
    public void SubstituteParameters_NoParams_ReturnsOriginal()
    {
        const string content = "This is a simple prompt with no parameters.";
        var result = ScriptRunner.SubstituteParameters(content, new Dictionary<string, string>());

        result.Should().Be(content);
    }

    [Fact]
    public void SubstituteParameters_MissingParam_LeavesPlaceholder()
    {
        var result = ScriptRunner.SubstituteParameters(
            "Hello ${input:name}!", new Dictionary<string, string>());

        result.Should().Be("Hello ${input:name}!");
    }
}

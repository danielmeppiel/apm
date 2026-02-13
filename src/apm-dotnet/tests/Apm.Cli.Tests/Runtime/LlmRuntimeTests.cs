using Apm.Cli.Runtime;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Runtime;

/// <summary>
/// Port of Python test_llm_runtime.py tests for LlmRuntime.
/// </summary>
public class LlmRuntimeTests
{
    [Fact]
    public void GetRuntimeName_ReturnsLlm()
    {
        LlmRuntime.GetRuntimeName().Should().Be("llm");
    }

    [Fact]
    public void IsAvailable_DoesNotThrow()
    {
        var act = () => LlmRuntime.IsAvailable();
        act.Should().NotThrow();
    }

    [Fact]
    public void Constructor_ThrowsWhenNotAvailable()
    {
        if (LlmRuntime.IsAvailable())
            return;

        var act = () => new LlmRuntime();
        act.Should().Throw<InvalidOperationException>()
            .WithMessage("*llm CLI not found*");
    }

    [Fact]
    public void Constructor_WhenAvailable_SetsModelName()
    {
        if (!LlmRuntime.IsAvailable())
            return;

        var runtime = new LlmRuntime("gpt-4o-mini");
        runtime.ModelName.Should().Be("gpt-4o-mini");
    }

    [Fact]
    public void Constructor_WhenAvailable_NullModelNameByDefault()
    {
        if (!LlmRuntime.IsAvailable())
            return;

        var runtime = new LlmRuntime();
        runtime.ModelName.Should().BeNull();
    }

    [Fact]
    public void GetRuntimeInfo_WhenAvailable_ReturnsExpectedFields()
    {
        if (!LlmRuntime.IsAvailable())
            return;

        var runtime = new LlmRuntime();
        var info = runtime.GetRuntimeInfo();

        info["name"].Should().Be("llm");
        info["type"].Should().Be("llm_library");
        info.Should().ContainKey("capabilities");
    }

    [Fact]
    public void ToString_WhenAvailable_MatchesExpectedFormat()
    {
        if (!LlmRuntime.IsAvailable())
            return;

        var runtime = new LlmRuntime("claude-3-sonnet");
        runtime.ToString().Should().Be("LlmRuntime(model=claude-3-sonnet)");
    }
}

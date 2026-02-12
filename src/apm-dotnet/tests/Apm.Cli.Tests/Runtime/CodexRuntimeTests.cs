using Apm.Cli.Runtime;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Runtime;

/// <summary>
/// Port of Python test_codex_runtime.py tests for CodexRuntime.
/// </summary>
public class CodexRuntimeTests
{
    [Fact]
    public void GetRuntimeName_ReturnsCodex()
    {
        CodexRuntime.GetRuntimeName().Should().Be("codex");
    }

    [Fact]
    public void IsAvailable_DoesNotThrow()
    {
        var act = () => CodexRuntime.IsAvailable();
        act.Should().NotThrow();
    }

    [Fact]
    public void Constructor_ThrowsWhenNotAvailable()
    {
        if (CodexRuntime.IsAvailable())
            return;

        var act = () => new CodexRuntime();
        act.Should().Throw<InvalidOperationException>()
            .WithMessage("*Codex CLI not available*");
    }

    [Fact]
    public void Constructor_WhenAvailable_SetsModelName()
    {
        if (!CodexRuntime.IsAvailable())
            return;

        var runtime = new CodexRuntime("test-model");
        runtime.ModelName.Should().Be("test-model");
    }

    [Fact]
    public void Constructor_WhenAvailable_DefaultModel()
    {
        if (!CodexRuntime.IsAvailable())
            return;

        var runtime = new CodexRuntime();
        runtime.ModelName.Should().Be("default");
    }

    [Fact]
    public void ListAvailableModels_WhenAvailable_ContainsCodexDefault()
    {
        if (!CodexRuntime.IsAvailable())
            return;

        var runtime = new CodexRuntime();
        var models = runtime.ListAvailableModels();

        models.Should().ContainKey("codex-default");
        var modelInfo = models["codex-default"] as Dictionary<string, string>;
        modelInfo.Should().NotBeNull();
        modelInfo!["provider"].Should().Be("codex");
    }

    [Fact]
    public void GetRuntimeInfo_WhenAvailable_ReturnsExpectedFields()
    {
        if (!CodexRuntime.IsAvailable())
            return;

        var runtime = new CodexRuntime();
        var info = runtime.GetRuntimeInfo();

        info["name"].Should().Be("codex");
        info["type"].Should().Be("codex_cli");
        info.Should().ContainKey("version");
        info.Should().ContainKey("capabilities");

        var capabilities = info["capabilities"] as Dictionary<string, object>;
        capabilities.Should().NotBeNull();
        capabilities!["mcp_servers"].Should().Be("native_support");
    }

    [Fact]
    public void ToString_WhenAvailable_MatchesExpectedFormat()
    {
        if (!CodexRuntime.IsAvailable())
            return;

        var runtime = new CodexRuntime("test-model");
        runtime.ToString().Should().Be("CodexRuntime(model=test-model)");
    }
}

using Apm.Cli.Runtime;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Runtime;

/// <summary>
/// Port of Python test_copilot_runtime.py tests for CopilotRuntime.
/// </summary>
public class CopilotRuntimeTests
{
    [Fact]
    public void GetRuntimeName_ReturnsCopilot()
    {
        CopilotRuntime.GetRuntimeName().Should().Be("copilot");
    }

    [Fact]
    public void IsAvailable_DoesNotThrow()
    {
        var act = () => CopilotRuntime.IsAvailable();
        act.Should().NotThrow();
    }

    [Fact]
    public void Constructor_ThrowsWhenNotAvailable()
    {
        if (CopilotRuntime.IsAvailable())
            return; // Skip if actually available

        var act = () => new CopilotRuntime();
        act.Should().Throw<InvalidOperationException>()
            .WithMessage("*Copilot CLI not available*");
    }

    [Fact]
    public void Constructor_WhenAvailable_SetsModelName()
    {
        if (!CopilotRuntime.IsAvailable())
            return;

        var runtime = new CopilotRuntime("test-model");
        runtime.ModelName.Should().Be("test-model");
    }

    [Fact]
    public void Constructor_WhenAvailable_DefaultModel()
    {
        if (!CopilotRuntime.IsAvailable())
            return;

        var runtime = new CopilotRuntime();
        runtime.ModelName.Should().Be("default");
    }

    [Fact]
    public void ListAvailableModels_WhenAvailable_ContainsCopilotDefault()
    {
        if (!CopilotRuntime.IsAvailable())
            return;

        var runtime = new CopilotRuntime();
        var models = runtime.ListAvailableModels();

        models.Should().ContainKey("copilot-default");
        var modelInfo = models["copilot-default"] as Dictionary<string, string>;
        modelInfo.Should().NotBeNull();
        modelInfo!["provider"].Should().Be("github-copilot");
    }

    [Fact]
    public void GetRuntimeInfo_WhenAvailable_ReturnsExpectedFields()
    {
        if (!CopilotRuntime.IsAvailable())
            return;

        var runtime = new CopilotRuntime();
        var info = runtime.GetRuntimeInfo();

        info["name"].Should().Be("copilot");
        info["type"].Should().Be("copilot_cli");
        info.Should().ContainKey("capabilities");

        var capabilities = info["capabilities"] as Dictionary<string, object>;
        capabilities.Should().NotBeNull();
        capabilities!["model_execution"].Should().Be(true);
        capabilities["file_operations"].Should().Be(true);
    }

    [Fact]
    public void ToString_WhenAvailable_ContainsRuntimeNameAndModel()
    {
        if (!CopilotRuntime.IsAvailable())
            return;

        var runtime = new CopilotRuntime("test-model");
        var str = runtime.ToString();

        str.Should().Contain("CopilotRuntime");
        str.Should().Contain("test-model");
    }
}

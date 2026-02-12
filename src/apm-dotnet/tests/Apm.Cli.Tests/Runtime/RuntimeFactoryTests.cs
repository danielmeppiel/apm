using Apm.Cli.Runtime;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Runtime;

/// <summary>
/// Port of Python test_runtime_factory.py tests for RuntimeFactory.
/// </summary>
public class RuntimeFactoryTests
{
    [Fact]
    public void GetRuntimeByName_UnknownRuntime_ThrowsArgumentException()
    {
        var act = () => RuntimeFactory.GetRuntimeByName("unknown");
        act.Should().Throw<ArgumentException>()
            .WithMessage("*Unknown runtime: unknown*");
    }

    [Fact]
    public void RuntimeExists_UnknownRuntime_ReturnsFalse()
    {
        RuntimeFactory.RuntimeExists("unknown").Should().BeFalse();
    }

    [Theory]
    [InlineData("copilot")]
    [InlineData("codex")]
    [InlineData("llm")]
    public void RuntimeExists_KnownRuntime_DoesNotThrow(string runtime)
    {
        var act = () => RuntimeFactory.RuntimeExists(runtime);
        act.Should().NotThrow();
    }

    [Fact]
    public void GetAvailableRuntimes_ReturnsListOfDictionaries()
    {
        var available = RuntimeFactory.GetAvailableRuntimes();

        available.Should().NotBeNull();
        foreach (var runtime in available)
        {
            runtime.Should().ContainKey("name");
            runtime.Should().ContainKey("available");
            runtime["available"].Should().Be(true);
        }
    }

    [Fact]
    public void CreateRuntime_UnknownName_ThrowsArgumentException()
    {
        var act = () => RuntimeFactory.CreateRuntime("unknown");
        act.Should().Throw<ArgumentException>()
            .WithMessage("*Unknown runtime: unknown*");
    }

    [Fact]
    public void CreateRuntime_KnownButUnavailable_ThrowsArgumentException()
    {
        foreach (var name in new[] { "copilot", "codex", "llm" })
        {
            if (RuntimeFactory.RuntimeExists(name))
                continue;

            var runtimeName = name;
            var act = () => RuntimeFactory.CreateRuntime(runtimeName);
            act.Should().Throw<ArgumentException>()
                .WithMessage($"*Runtime '{runtimeName}' is not available*");
            return;
        }
    }

    [Fact]
    public void CreateRuntime_AutoDetect_ReturnsAvailableRuntime()
    {
        var available = RuntimeFactory.GetAvailableRuntimes();
        if (available.Count == 0)
            return;

        var runtime = RuntimeFactory.CreateRuntime();
        runtime.Should().NotBeNull();
    }

    [Fact]
    public void GetBestAvailableRuntime_WhenAvailable_ReturnsRuntime()
    {
        var available = RuntimeFactory.GetAvailableRuntimes();
        if (available.Count == 0)
            return;

        var runtime = RuntimeFactory.GetBestAvailableRuntime();
        runtime.Should().NotBeNull();
    }
}

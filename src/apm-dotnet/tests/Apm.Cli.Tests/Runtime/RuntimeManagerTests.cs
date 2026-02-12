using Apm.Cli.Runtime;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Runtime;

/// <summary>
/// Port of Python test_runtime_detection.py RuntimeManager tests.
/// </summary>
public class RuntimeManagerTests
{
    [Fact]
    public void ListRuntimes_ReturnsAllSupportedRuntimes()
    {
        var manager = new RuntimeManager();
        var runtimes = manager.ListRuntimes();

        runtimes.Should().ContainKey("copilot");
        runtimes.Should().ContainKey("codex");
        runtimes.Should().ContainKey("llm");

        foreach (var (_, status) in runtimes)
        {
            status.Should().ContainKey("description");
            status.Should().ContainKey("installed");
        }
    }

    [Fact]
    public void IsRuntimeAvailable_UnknownRuntime_ReturnsFalse()
    {
        var manager = new RuntimeManager();
        manager.IsRuntimeAvailable("unknown").Should().BeFalse();
    }

    [Theory]
    [InlineData("copilot")]
    [InlineData("codex")]
    [InlineData("llm")]
    public void IsRuntimeAvailable_KnownRuntime_DoesNotThrow(string runtime)
    {
        var manager = new RuntimeManager();
        var act = () => manager.IsRuntimeAvailable(runtime);
        act.Should().NotThrow();
    }

    [Fact]
    public void GetRuntimePreference_ReturnsCopilotCodexLlm()
    {
        var preference = RuntimeManager.GetRuntimePreference();

        preference.Should().HaveCount(3);
        preference[0].Should().Be("copilot");
        preference[1].Should().Be("codex");
        preference[2].Should().Be("llm");
    }

    [Fact]
    public void GetAvailableRuntime_ReturnsNullOrKnownRuntime()
    {
        var manager = new RuntimeManager();
        var runtime = manager.GetAvailableRuntime();

        if (runtime is not null)
            runtime.Should().BeOneOf("copilot", "codex", "llm");
    }
}

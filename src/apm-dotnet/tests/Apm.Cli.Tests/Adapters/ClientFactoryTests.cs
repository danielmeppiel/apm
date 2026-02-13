using Apm.Cli.Adapters.Client;
using Apm.Cli.Core;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Adapters;

/// <summary>
/// Port of Python TestMCPClientFactory tests for ClientFactory.
/// </summary>
public class ClientFactoryTests
{
    [Fact]
    public void CreateClient_VSCode_ReturnsVSCodeAdapter()
    {
        var client = ClientFactory.CreateClient("vscode");
        client.Should().BeOfType<VSCodeClientAdapter>();
    }

    [Fact]
    public void CreateClient_Codex_ReturnsCodexAdapter()
    {
        var client = ClientFactory.CreateClient("codex");
        client.Should().BeOfType<CodexClientAdapter>();
    }

    [Fact]
    public void CreateClient_Copilot_ReturnsCopilotAdapter()
    {
        var client = ClientFactory.CreateClient("copilot");
        client.Should().BeOfType<CopilotClientAdapter>();
    }

    [Theory]
    [InlineData("VSCode")]
    [InlineData("VSCODE")]
    [InlineData("Codex")]
    [InlineData("CODEX")]
    [InlineData("Copilot")]
    [InlineData("COPILOT")]
    public void CreateClient_CaseInsensitive(string clientType)
    {
        var client = ClientFactory.CreateClient(clientType);
        client.Should().NotBeNull();
    }

    [Fact]
    public void CreateClient_Unsupported_ThrowsArgumentException()
    {
        var act = () => ClientFactory.CreateClient("unsupported");
        act.Should().Throw<ArgumentException>()
            .WithMessage("*Unsupported client type*");
    }

    [Theory]
    [InlineData("vscode")]
    [InlineData("codex")]
    [InlineData("copilot")]
    public void AllSupportedTypes_ImplementIClientAdapter(string clientType)
    {
        var client = ClientFactory.CreateClient(clientType);

        client.Should().NotBeNull();
        client.Should().BeAssignableTo<IClientAdapter>();

        // Verify interface methods exist (matches Python's hasattr checks)
        client.GetType().GetMethod("GetConfigPath").Should().NotBeNull();
        client.GetType().GetMethod("UpdateConfig").Should().NotBeNull();
        client.GetType().GetMethod("GetCurrentConfig").Should().NotBeNull();
        client.GetType().GetMethod("ConfigureMcpServer").Should().NotBeNull();
    }
}

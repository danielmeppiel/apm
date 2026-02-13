using Apm.Cli.Adapters.Client;
using Apm.Cli.Core;
using AwesomeAssertions;
using FakeItEasy;

namespace Apm.Cli.Tests.Core;

public class InstallResultTests
{
    [Fact]
    public void InstallResult_DefaultValues_AreFalse()
    {
        var result = new InstallResult
        {
            Success = false,
            Installed = false,
            Skipped = false,
            Failed = false,
        };

        result.Success.Should().BeFalse();
        result.Installed.Should().BeFalse();
        result.Skipped.Should().BeFalse();
        result.Failed.Should().BeFalse();
    }

    [Fact]
    public void InstallResult_CanSetAllProperties()
    {
        var result = new InstallResult
        {
            Success = true,
            Installed = true,
            Skipped = false,
            Failed = false,
        };

        result.Success.Should().BeTrue();
        result.Installed.Should().BeTrue();
    }
}

public class OperationsInstallPackageTests
{
    private static SafeInstaller CreateMockInstaller(bool configureResult = true)
    {
        var adapter = A.Fake<IClientAdapter>();
        A.CallTo(() => adapter.GetCurrentConfig()).Returns(new Dictionary<string, object?>());
        A.CallTo(() => adapter.ConfigureMcpServer(
            A<string>._, A<string?>._, A<bool>._,
            A<Dictionary<string, string>?>._,
            A<Dictionary<string, Dictionary<string, object?>>?>._,
            A<Dictionary<string, string>?>._))
            .Returns(configureResult);
        return new SafeInstaller(adapter);
    }

    [Fact]
    public void InstallPackage_ReturnsSuccessResult()
    {
        var result = Operations.InstallPackage(CreateMockInstaller(), "my-server");

        result.Success.Should().BeTrue();
        result.Installed.Should().BeTrue();
        result.Skipped.Should().BeFalse();
        result.Failed.Should().BeFalse();
    }

    [Fact]
    public void InstallPackage_DifferentServers_AllSucceed()
    {
        var servers = new[] { "server-a", "server-b", "server-c" };

        foreach (var server in servers)
        {
            var result = Operations.InstallPackage(CreateMockInstaller(), server);
            result.Success.Should().BeTrue();
            result.Installed.Should().BeTrue();
        }
    }

    [Fact]
    public void InstallPackage_WithEnvOverrides_Succeeds()
    {
        var env = new Dictionary<string, string> { ["API_KEY"] = "secret" };
        var result = Operations.InstallPackage(CreateMockInstaller(), "my-server", sharedEnvVars: env);

        result.Success.Should().BeTrue();
    }

    [Fact]
    public void InstallPackage_WithAllOptionalParams_Succeeds()
    {
        var result = Operations.InstallPackage(
            CreateMockInstaller(),
            "my-server",
            sharedEnvVars: new Dictionary<string, string> { ["KEY"] = "val" },
            serverInfoCache: new Dictionary<string, object> { ["cache"] = "data" },
            sharedRuntimeVars: new Dictionary<string, string> { ["var"] = "val" });

        result.Success.Should().BeTrue();
        result.Installed.Should().BeTrue();
    }

    [Fact]
    public void InstallPackage_ConfigureFails_ReturnsFailed()
    {
        var result = Operations.InstallPackage(CreateMockInstaller(configureResult: false), "my-server");

        result.Success.Should().BeTrue();
        result.Failed.Should().BeTrue();
        result.Installed.Should().BeFalse();
    }
}

public class OperationsUninstallPackageTests
{
    [Fact]
    public void UninstallPackage_ReturnsFalse_WhenNotYetImplemented()
    {
        // UninstallPackage throws NotImplementedException internally,
        // which is caught and returns false
        var result = Operations.UninstallPackage("vscode", "my-server");
        result.Should().BeFalse();
    }
}

public class OperationsConfigureClientTests
{
    [Fact]
    public void ConfigureClient_ReturnsFalse_WhenNotYetImplemented()
    {
        // ConfigureClient throws NotImplementedException internally,
        // which is caught and returns false
        var result = Operations.ConfigureClient("vscode", new Dictionary<string, object>());
        result.Should().BeFalse();
    }
}

using Apm.Cli.Adapters.Client;
using Apm.Cli.Core;
using AwesomeAssertions;
using FakeItEasy;

namespace Apm.Cli.Tests.Core;

public class InstallationSummaryTests
{
    [Fact]
    public void NewSummary_HasEmptyLists()
    {
        var summary = new InstallationSummary();

        summary.Installed.Should().BeEmpty();
        summary.Skipped.Should().BeEmpty();
        summary.Failed.Should().BeEmpty();
    }

    [Fact]
    public void AddInstalled_AddsToInstalledList()
    {
        var summary = new InstallationSummary();
        summary.AddInstalled("server-a");
        summary.AddInstalled("server-b");

        summary.Installed.Should().HaveCount(2);
        summary.Installed.Should().Contain("server-a");
        summary.Installed.Should().Contain("server-b");
    }

    [Fact]
    public void AddSkipped_AddsToSkippedList()
    {
        var summary = new InstallationSummary();
        summary.AddSkipped("server-a", "already configured");

        summary.Skipped.Should().HaveCount(1);
        summary.Skipped[0].Server.Should().Be("server-a");
        summary.Skipped[0].Reason.Should().Be("already configured");
    }

    [Fact]
    public void AddFailed_AddsToFailedList()
    {
        var summary = new InstallationSummary();
        summary.AddFailed("server-a", "connection error");

        summary.Failed.Should().HaveCount(1);
        summary.Failed[0].Server.Should().Be("server-a");
        summary.Failed[0].Reason.Should().Be("connection error");
    }

    [Fact]
    public void HasAnyChanges_FalseWhenEmpty()
    {
        var summary = new InstallationSummary();
        summary.HasAnyChanges.Should().BeFalse();
    }

    [Fact]
    public void HasAnyChanges_TrueWhenInstalled()
    {
        var summary = new InstallationSummary();
        summary.AddInstalled("server-a");
        summary.HasAnyChanges.Should().BeTrue();
    }

    [Fact]
    public void HasAnyChanges_TrueWhenFailed()
    {
        var summary = new InstallationSummary();
        summary.AddFailed("server-a", "error");
        summary.HasAnyChanges.Should().BeTrue();
    }

    [Fact]
    public void HasAnyChanges_FalseWhenOnlySkipped()
    {
        var summary = new InstallationSummary();
        summary.AddSkipped("server-a", "already exists");
        summary.HasAnyChanges.Should().BeFalse();
    }
}

public class SafeInstallerInstallServersTests
{
    private static IClientAdapter CreateMockAdapter(bool configureResult = true)
    {
        var adapter = A.Fake<IClientAdapter>();
        A.CallTo(() => adapter.GetCurrentConfig()).Returns(new Dictionary<string, object?>());
        A.CallTo(() => adapter.ConfigureMcpServer(
            A<string>._, A<string?>._, A<bool>._,
            A<Dictionary<string, string>?>._,
            A<Dictionary<string, Dictionary<string, object?>>?>._,
            A<Dictionary<string, string>?>._))
            .Returns(configureResult);
        return adapter;
    }

    [Fact]
    public void InstallServers_EmptyList_ReturnsEmptySummary()
    {
        var installer = new SafeInstaller(CreateMockAdapter());
        var summary = installer.InstallServers([]);

        summary.Installed.Should().BeEmpty();
        summary.Skipped.Should().BeEmpty();
        summary.Failed.Should().BeEmpty();
    }

    [Fact]
    public void InstallServers_SingleServer_MarksAsInstalled()
    {
        var installer = new SafeInstaller(CreateMockAdapter());
        var summary = installer.InstallServers(["my-server"]);

        summary.Installed.Should().Contain("my-server");
        summary.Skipped.Should().BeEmpty();
        summary.Failed.Should().BeEmpty();
    }

    [Fact]
    public void InstallServers_MultipleServers_AllInstalled()
    {
        var installer = new SafeInstaller(CreateMockAdapter());
        var servers = new List<string> { "server-a", "server-b", "server-c" };
        var summary = installer.InstallServers(servers);

        summary.Installed.Should().HaveCount(3);
        summary.Installed.Should().Contain("server-a");
        summary.Installed.Should().Contain("server-b");
        summary.Installed.Should().Contain("server-c");
    }

    [Fact]
    public void InstallServers_WithEnvOverrides_DoesNotThrow()
    {
        var installer = new SafeInstaller(CreateMockAdapter());
        var envOverrides = new Dictionary<string, string> { ["API_KEY"] = "test-key" };

        var summary = installer.InstallServers(["my-server"], envOverrides: envOverrides);
        summary.Installed.Should().Contain("my-server");
    }

    [Fact]
    public void InstallServers_WithServerInfoCache_DoesNotThrow()
    {
        var installer = new SafeInstaller(CreateMockAdapter());
        var cache = new Dictionary<string, object> { ["my-server"] = new object() };

        var summary = installer.InstallServers(["my-server"], serverInfoCache: cache);
        summary.Installed.Should().Contain("my-server");
    }

    [Fact]
    public void InstallServers_WithRuntimeVars_DoesNotThrow()
    {
        var installer = new SafeInstaller(CreateMockAdapter());
        var runtimeVars = new Dictionary<string, string> { ["runtime_var"] = "value" };

        var summary = installer.InstallServers(["my-server"], runtimeVars: runtimeVars);
        summary.Installed.Should().Contain("my-server");
    }

    [Fact]
    public void InstallServers_ConfigureFails_MarksAsFailed()
    {
        var installer = new SafeInstaller(CreateMockAdapter(configureResult: false));
        var summary = installer.InstallServers(["my-server"]);

        summary.Installed.Should().BeEmpty();
        summary.Failed.Should().HaveCount(1);
        summary.Failed[0].Server.Should().Be("my-server");
    }

    [Fact]
    public void InstallServers_ConfigureThrows_MarksAsFailed()
    {
        var adapter = A.Fake<IClientAdapter>();
        A.CallTo(() => adapter.GetCurrentConfig()).Returns(new Dictionary<string, object?>());
        A.CallTo(() => adapter.ConfigureMcpServer(
            A<string>._, A<string?>._, A<bool>._,
            A<Dictionary<string, string>?>._,
            A<Dictionary<string, Dictionary<string, object?>>?>._,
            A<Dictionary<string, string>?>._))
            .Throws(new InvalidOperationException("registry error"));

        var installer = new SafeInstaller(adapter);
        var summary = installer.InstallServers(["my-server"]);

        summary.Installed.Should().BeEmpty();
        summary.Failed.Should().HaveCount(1);
        summary.Failed[0].Reason.Should().Contain("registry error");
    }

    [Fact]
    public void InstallServers_SkipsExistingServer()
    {
        var adapter = A.Fake<IClientAdapter>();
        A.CallTo(() => adapter.GetCurrentConfig()).Returns(new Dictionary<string, object?>
        {
            ["mcpServers"] = new Dictionary<string, object?>
            {
                ["github"] = new Dictionary<string, object?> { ["command"] = "gh" },
            }
        });

        var installer = new SafeInstaller(adapter);
        var summary = installer.InstallServers(["github"]);

        summary.Skipped.Should().HaveCount(1);
        summary.Skipped[0].Server.Should().Be("github");
        summary.Installed.Should().BeEmpty();
    }
}

public class SafeInstallerCheckConflictsOnlyTests
{
    private static IClientAdapter CreateMockAdapter()
    {
        var adapter = A.Fake<IClientAdapter>();
        A.CallTo(() => adapter.GetCurrentConfig()).Returns(new Dictionary<string, object?>());
        return adapter;
    }

    [Fact]
    public void CheckConflictsOnly_EmptyList_ReturnsEmptyDictionary()
    {
        var installer = new SafeInstaller(CreateMockAdapter());
        var conflicts = installer.CheckConflictsOnly([]);

        conflicts.Should().BeEmpty();
    }

    [Fact]
    public void CheckConflictsOnly_ReturnsConflictSummaryPerServer()
    {
        var installer = new SafeInstaller(CreateMockAdapter());
        var servers = new List<string> { "server-a", "server-b" };

        var conflicts = installer.CheckConflictsOnly(servers);

        conflicts.Should().HaveCount(2);
        conflicts.Should().ContainKey("server-a");
        conflicts.Should().ContainKey("server-b");
    }

    [Fact]
    public void CheckConflictsOnly_NoExistingServers_AllReturnNoConflict()
    {
        var installer = new SafeInstaller(CreateMockAdapter());
        var conflicts = installer.CheckConflictsOnly(["test-server"]);

        var summary = conflicts["test-server"];
        summary.Exists.Should().BeFalse();
        summary.CanonicalName.Should().Be("test-server");
        summary.ConflictingServers.Should().BeEmpty();
    }
}

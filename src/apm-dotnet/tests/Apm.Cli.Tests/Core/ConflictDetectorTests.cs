using Apm.Cli.Adapters.Client;
using Apm.Cli.Core;
using AwesomeAssertions;
using FakeItEasy;

namespace Apm.Cli.Tests.Core;

public class ConflictDetectorGetCanonicalServerNameTests
{
    [Fact]
    public void GetCanonicalServerName_ReturnsOriginalReference_WhenRegistryNotWired()
    {
        var detector = new ConflictDetector();
        detector.GetCanonicalServerName("my-server").Should().Be("my-server");
    }

    [Theory]
    [InlineData("")]
    [InlineData("some/path/to/server")]
    [InlineData("@org/server-name")]
    public void GetCanonicalServerName_ReturnsInput_ForAnyFormat(string serverRef)
    {
        var detector = new ConflictDetector();
        detector.GetCanonicalServerName(serverRef).Should().Be(serverRef);
    }
}

public class ConflictDetectorGetExistingServerConfigsTests
{
    [Fact]
    public void GetExistingServerConfigs_ReturnsEmptyDictionary_WhenAdapterNotWired()
    {
        var detector = new ConflictDetector();
        var configs = detector.GetExistingServerConfigs();

        configs.Should().NotBeNull();
        configs.Should().BeEmpty();
    }
}

public class ConflictDetectorCheckServerExistsTests
{
    [Fact]
    public void CheckServerExists_ReturnsFalse_WhenNoExistingServers()
    {
        var detector = new ConflictDetector();
        detector.CheckServerExists("any-server").Should().BeFalse();
    }

    [Fact]
    public void CheckServerExists_ReturnsFalse_ForEmptyReference()
    {
        var detector = new ConflictDetector();
        detector.CheckServerExists("").Should().BeFalse();
    }

    [Theory]
    [InlineData("server-a")]
    [InlineData("@org/mcp-server")]
    [InlineData("github.com/user/repo")]
    public void CheckServerExists_ReturnsFalse_ForVariousReferences(string serverRef)
    {
        var detector = new ConflictDetector();
        detector.CheckServerExists(serverRef).Should().BeFalse();
    }
}

public class ConflictDetectorGetConflictSummaryTests
{
    [Fact]
    public void GetConflictSummary_ReturnsNoConflict_WhenNoExistingServers()
    {
        var detector = new ConflictDetector();
        var summary = detector.GetConflictSummary("my-server");

        summary.Should().NotBeNull();
        summary.Exists.Should().BeFalse();
        summary.CanonicalName.Should().Be("my-server");
        summary.ConflictingServers.Should().BeEmpty();
    }

    [Fact]
    public void GetConflictSummary_SetsCanonicalName_ToServerReference()
    {
        var detector = new ConflictDetector();
        var summary = detector.GetConflictSummary("@org/special-server");

        summary.CanonicalName.Should().Be("@org/special-server");
    }

    [Fact]
    public void GetConflictSummary_ReturnsNoConflict_ForEmptyReference()
    {
        var detector = new ConflictDetector();
        var summary = detector.GetConflictSummary("");

        summary.Exists.Should().BeFalse();
        summary.ConflictingServers.Should().BeEmpty();
    }
}

public class ConflictSummaryModelTests
{
    [Fact]
    public void ConflictSummary_DefaultValues_AreCorrect()
    {
        var summary = new ConflictSummary();

        summary.Exists.Should().BeFalse();
        summary.CanonicalName.Should().Be("");
        summary.ConflictingServers.Should().NotBeNull();
        summary.ConflictingServers.Should().BeEmpty();
    }

    [Fact]
    public void ConflictSummary_CanAddConflictingServers()
    {
        var summary = new ConflictSummary
        {
            Exists = true,
            CanonicalName = "test-server",
        };

        summary.ConflictingServers.Add(new ConflictingServer
        {
            Name = "existing-server",
            Type = "exact_match",
        });

        summary.ConflictingServers.Should().HaveCount(1);
        summary.ConflictingServers[0].Name.Should().Be("existing-server");
        summary.ConflictingServers[0].Type.Should().Be("exact_match");
        summary.ConflictingServers[0].ResolvesTo.Should().BeNull();
    }

    [Fact]
    public void ConflictingServer_CanHaveResolvesTo()
    {
        var server = new ConflictingServer
        {
            Name = "alias-server",
            Type = "canonical_match",
            ResolvesTo = "real-server",
        };

        server.ResolvesTo.Should().Be("real-server");
    }
}

public class ConflictDetectorWithAdapterTests
{
    private static IClientAdapter CreateAdapterWithConfig(Dictionary<string, object?> config)
    {
        var adapter = A.Fake<IClientAdapter>();
        A.CallTo(() => adapter.GetCurrentConfig()).Returns(config);
        return adapter;
    }

    [Fact]
    public void GetExistingServerConfigs_ExtractsCopilotMcpServers()
    {
        var adapter = CreateAdapterWithConfig(new Dictionary<string, object?>
        {
            ["mcpServers"] = new Dictionary<string, object?>
            {
                ["github"] = new Dictionary<string, object?> { ["command"] = "gh" },
                ["slack"] = new Dictionary<string, object?> { ["command"] = "slack-mcp" },
            }
        });

        var detector = new ConflictDetector(adapter);
        var configs = detector.GetExistingServerConfigs();

        configs.Should().HaveCount(2);
        configs.Should().ContainKey("github");
        configs.Should().ContainKey("slack");
    }

    [Fact]
    public void GetExistingServerConfigs_ExtractsVSCodeServers()
    {
        var adapter = CreateAdapterWithConfig(new Dictionary<string, object?>
        {
            ["servers"] = new Dictionary<string, object?>
            {
                ["my-server"] = new Dictionary<string, object?> { ["command"] = "my-cmd" },
            }
        });

        var detector = new ConflictDetector(adapter);
        var configs = detector.GetExistingServerConfigs();

        configs.Should().HaveCount(1);
        configs.Should().ContainKey("my-server");
    }

    [Fact]
    public void GetExistingServerConfigs_ExtractsCodexMcpServers()
    {
        var adapter = CreateAdapterWithConfig(new Dictionary<string, object?>
        {
            ["mcp_servers"] = new Dictionary<string, object?>
            {
                ["github"] = new Dictionary<string, object?> { ["command"] = "gh" },
            }
        });

        var detector = new ConflictDetector(adapter);
        var configs = detector.GetExistingServerConfigs();

        configs.Should().HaveCount(1);
        configs.Should().ContainKey("github");
    }

    [Fact]
    public void GetExistingServerConfigs_ExtractsCodexNestedTomlKeys()
    {
        var adapter = CreateAdapterWithConfig(new Dictionary<string, object?>
        {
            ["mcp_servers.github"] = new Dictionary<string, object?> { ["command"] = "gh" },
            ["mcp_servers.\"quoted-name\""] = new Dictionary<string, object?> { ["command"] = "qn", ["args"] = "--flag" },
        });

        var detector = new ConflictDetector(adapter);
        var configs = detector.GetExistingServerConfigs();

        configs.Should().HaveCount(2);
        configs.Should().ContainKey("github");
        configs.Should().ContainKey("quoted-name");
    }

    [Fact]
    public void GetExistingServerConfigs_ReturnsEmpty_WhenSectionMissing()
    {
        var adapter = CreateAdapterWithConfig(new Dictionary<string, object?>
        {
            ["someOtherKey"] = "value"
        });

        var detector = new ConflictDetector(adapter);
        detector.GetExistingServerConfigs().Should().BeEmpty();
    }

    [Fact]
    public void CheckServerExists_ReturnsTrue_WhenExactCanonicalMatch()
    {
        var adapter = CreateAdapterWithConfig(new Dictionary<string, object?>
        {
            ["mcpServers"] = new Dictionary<string, object?>
            {
                ["github"] = new Dictionary<string, object?> { ["command"] = "gh" },
            }
        });

        var detector = new ConflictDetector(adapter);
        detector.CheckServerExists("github").Should().BeTrue();
    }

    [Fact]
    public void CheckServerExists_ReturnsFalse_WhenNotPresent()
    {
        var adapter = CreateAdapterWithConfig(new Dictionary<string, object?>
        {
            ["mcpServers"] = new Dictionary<string, object?>
            {
                ["github"] = new Dictionary<string, object?> { ["command"] = "gh" },
            }
        });

        var detector = new ConflictDetector(adapter);
        detector.CheckServerExists("slack").Should().BeFalse();
    }

    [Fact]
    public void GetConflictSummary_DetectsExactMatch_WithAdapter()
    {
        var adapter = CreateAdapterWithConfig(new Dictionary<string, object?>
        {
            ["mcpServers"] = new Dictionary<string, object?>
            {
                ["github"] = new Dictionary<string, object?> { ["command"] = "gh" },
            }
        });

        var detector = new ConflictDetector(adapter);
        var summary = detector.GetConflictSummary("github");

        summary.Exists.Should().BeTrue();
        summary.CanonicalName.Should().Be("github");
        summary.ConflictingServers.Should().HaveCount(1);
        summary.ConflictingServers[0].Type.Should().Be("exact_match");
    }

    [Fact]
    public void GetConflictSummary_ReturnsNoConflict_WhenNotPresent()
    {
        var adapter = CreateAdapterWithConfig(new Dictionary<string, object?>
        {
            ["mcpServers"] = new Dictionary<string, object?>
            {
                ["github"] = new Dictionary<string, object?> { ["command"] = "gh" },
            }
        });

        var detector = new ConflictDetector(adapter);
        var summary = detector.GetConflictSummary("slack");

        summary.Exists.Should().BeFalse();
        summary.ConflictingServers.Should().BeEmpty();
    }
}

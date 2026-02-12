using Apm.Cli.Core;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Core;

/// <summary>
/// Port of Python test_docker_args.py and docker portion of test_docker_args_and_installer.py
/// for DockerArgs processor.
/// </summary>
public class DockerArgsProcessTests
{
    [Fact]
    public void ProcessDockerArgs_InjectsEnvVarsAfterRun()
    {
        var baseArgs = new List<string> { "run", "-i", "--rm", "image:latest" };
        var envVars = new Dictionary<string, string>
        {
            ["GITHUB_TOKEN"] = "token123",
            ["API_KEY"] = "key456"
        };

        var result = DockerArgs.ProcessDockerArgs(baseArgs, envVars);

        // Env vars injected after "run", existing flags preserved
        result[0].Should().Be("run");
        result.Should().Contain("-e");
        result.Should().Contain("GITHUB_TOKEN=token123");
        result.Should().Contain("API_KEY=key456");
        result.Should().Contain("-i");
        result.Should().Contain("--rm");
        result.Should().Contain("image:latest");
    }

    [Fact]
    public void ProcessDockerArgs_NoRunCommand_ReturnsUnchanged()
    {
        var baseArgs = new List<string> { "build", "-t", "myimage", "." };
        var envVars = new Dictionary<string, string> { ["BUILD_ARG"] = "value" };

        var result = DockerArgs.ProcessDockerArgs(baseArgs, envVars);

        result.Should().BeEquivalentTo(baseArgs);
    }

    [Fact]
    public void ProcessDockerArgs_EmptyEnvVars_PreservesArgs()
    {
        var baseArgs = new List<string> { "run", "-i", "--rm", "image-name" };
        var result = DockerArgs.ProcessDockerArgs(baseArgs, []);

        result.Should().BeEquivalentTo(baseArgs);
    }

    [Fact]
    public void ProcessDockerArgs_WithoutInteractiveFlag_AddsIt()
    {
        var baseArgs = new List<string> { "run", "image:latest" };
        var envVars = new Dictionary<string, string> { ["TOKEN"] = "value" };

        var result = DockerArgs.ProcessDockerArgs(baseArgs, envVars);

        result.Should().Contain("-i");
        result.Should().Contain("--rm");
    }

    [Fact]
    public void ProcessDockerArgs_WithExistingFlags_DoesNotDuplicate()
    {
        var baseArgs = new List<string> { "run", "-i", "--rm", "image:latest" };
        var envVars = new Dictionary<string, string> { ["TOKEN"] = "value" };

        var result = DockerArgs.ProcessDockerArgs(baseArgs, envVars);

        // -i should appear exactly once (from baseArgs, not re-added)
        result.Count(a => a == "-i").Should().Be(1);
        result.Count(a => a == "--rm").Should().Be(1);
    }

    [Fact]
    public void ProcessDockerArgs_NoDuplicateEnvVars()
    {
        var baseArgs = new List<string> { "run", "-i", "--rm" };
        var envVars = new Dictionary<string, string>
        {
            ["GITHUB_TOKEN"] = "test-token",
            ["ANOTHER_VAR"] = "test-value"
        };

        var result = DockerArgs.ProcessDockerArgs(baseArgs, envVars);

        result[0].Should().Be("run");
        // Env vars appear exactly once each
        result.Count(a => a.Contains("GITHUB_TOKEN")).Should().Be(1);
        result.Count(a => a.Contains("ANOTHER_VAR")).Should().Be(1);
    }

    [Fact]
    public void ProcessDockerArgs_PullCommand_NoEnvInjection()
    {
        var baseArgs = new List<string> { "pull", "image-name" };
        var envVars = new Dictionary<string, string> { ["TEST_VAR"] = "test-value" };

        var result = DockerArgs.ProcessDockerArgs(baseArgs, envVars);

        // Should return args unchanged since no 'run' command found
        result.Should().BeEquivalentTo(baseArgs);
    }
}

public class DockerArgsExtractTests
{
    [Fact]
    public void ExtractEnvVarsFromArgs_KeyValuePairs_ExtractsCorrectly()
    {
        var args = new List<string> { "run", "-i", "-e", "TOKEN=value1", "--rm", "-e", "API_KEY=value2", "image" };

        var (cleanArgs, envVars) = DockerArgs.ExtractEnvVarsFromArgs(args);

        cleanArgs.Should().BeEquivalentTo(new List<string> { "run", "-i", "--rm", "image" });
        envVars["TOKEN"].Should().Be("value1");
        envVars["API_KEY"].Should().Be("value2");
    }

    [Fact]
    public void ExtractEnvVarsFromArgs_JustNames_UsesTemplateValue()
    {
        var args = new List<string> { "run", "-e", "TOKEN", "-e", "API_KEY", "image" };

        var (cleanArgs, envVars) = DockerArgs.ExtractEnvVarsFromArgs(args);

        cleanArgs.Should().BeEquivalentTo(new List<string> { "run", "image" });
        envVars["TOKEN"].Should().Be("${TOKEN}");
        envVars["API_KEY"].Should().Be("${API_KEY}");
    }

    [Fact]
    public void ExtractEnvVarsFromArgs_MixedFormats_HandlesAll()
    {
        var args = new List<string>
        {
            "run", "-i", "--rm",
            "-e", "GITHUB_TOKEN=test-token",
            "-e", "ANOTHER_VAR=test-value",
            "-e", "FLAG_ONLY_VAR",
            "ghcr.io/github/github-mcp-server"
        };

        var (cleanArgs, envVars) = DockerArgs.ExtractEnvVarsFromArgs(args);

        cleanArgs.Should().BeEquivalentTo(
            new List<string> { "run", "-i", "--rm", "ghcr.io/github/github-mcp-server" });
        envVars["GITHUB_TOKEN"].Should().Be("test-token");
        envVars["ANOTHER_VAR"].Should().Be("test-value");
        envVars["FLAG_ONLY_VAR"].Should().Be("${FLAG_ONLY_VAR}");
    }

    [Fact]
    public void ExtractEnvVarsFromArgs_NoEnvVars_ReturnsOriginalArgs()
    {
        var args = new List<string> { "run", "-i", "--rm", "image" };

        var (cleanArgs, envVars) = DockerArgs.ExtractEnvVarsFromArgs(args);

        cleanArgs.Should().BeEquivalentTo(args);
        envVars.Should().BeEmpty();
    }
}

public class DockerArgsMergeTests
{
    [Fact]
    public void MergeEnvVars_NewOverridesExisting()
    {
        var existing = new Dictionary<string, string>
        {
            ["GITHUB_TOKEN"] = "existing_token",
            ["OLD_VAR"] = "old_value"
        };
        var newEnv = new Dictionary<string, string>
        {
            ["GITHUB_TOKEN"] = "new_token",
            ["NEW_VAR"] = "new_value"
        };

        var result = DockerArgs.MergeEnvVars(existing, newEnv);

        result["GITHUB_TOKEN"].Should().Be("new_token");
        result["OLD_VAR"].Should().Be("old_value");
        result["NEW_VAR"].Should().Be("new_value");
    }

    [Fact]
    public void MergeEnvVars_EmptyExisting_ReturnsNew()
    {
        var newEnv = new Dictionary<string, string>
        {
            ["TOKEN"] = "value",
            ["KEY"] = "secret"
        };

        var result = DockerArgs.MergeEnvVars([], newEnv);

        result.Should().BeEquivalentTo(newEnv);
    }

    [Fact]
    public void MergeEnvVars_EmptyNew_ReturnsExisting()
    {
        var existing = new Dictionary<string, string>
        {
            ["TOKEN"] = "value"
        };

        var result = DockerArgs.MergeEnvVars(existing, []);

        result.Should().BeEquivalentTo(existing);
    }

    [Fact]
    public void MergeEnvVars_BothEmpty_ReturnsEmpty()
    {
        var result = DockerArgs.MergeEnvVars([], []);
        result.Should().BeEmpty();
    }
}

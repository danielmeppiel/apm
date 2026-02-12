using System.Text.Json.Nodes;
using Apm.Cli.Adapters.Client;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Adapters;

/// <summary>
/// Port of Python test_vscode_adapter.py tests for VSCodeClientAdapter.
/// </summary>
[Collection("CwdTests")]
public class VSCodeClientAdapterTests : IDisposable
{
    private readonly string _tempDir;
    private readonly string _vscodeDir;
    private readonly string _configPath;
    private readonly string _originalCwd;

    public VSCodeClientAdapterTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm_vscode_test_{Guid.NewGuid()}");
        _vscodeDir = Path.Combine(_tempDir, ".vscode");
        _configPath = Path.Combine(_vscodeDir, "mcp.json");

        Directory.CreateDirectory(_vscodeDir);
        File.WriteAllText(_configPath, """{"servers":{}}""");

        _originalCwd = Directory.GetCurrentDirectory();
        Directory.SetCurrentDirectory(_tempDir);
    }

    public void Dispose()
    {
        Directory.SetCurrentDirectory(_originalCwd);
        try { Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void GetCurrentConfig_ReturnsServersFromFile()
    {
        var adapter = new VSCodeClientAdapter();
        var config = adapter.GetCurrentConfig();

        config.Should().ContainKey("servers");
    }

    [Fact]
    public void UpdateConfig_WritesJsonToFile()
    {
        var adapter = new VSCodeClientAdapter();

        var newConfig = new Dictionary<string, object?>
        {
            ["servers"] = new Dictionary<string, object?>
            {
                ["test-server"] = new Dictionary<string, object?>
                {
                    ["type"] = "stdio",
                    ["command"] = "uvx",
                }
            }
        };

        var result = adapter.UpdateConfig(newConfig);
        result.Should().BeTrue();

        var text = File.ReadAllText(_configPath);
        var json = JsonNode.Parse(text);
        json!["servers"]!["test-server"]!["type"]!.GetValue<string>().Should().Be("stdio");
        json!["servers"]!["test-server"]!["command"]!.GetValue<string>().Should().Be("uvx");
    }

    [Fact]
    public void UpdateConfig_CreatesFileWhenMissing()
    {
        // Use a subdirectory with no existing config
        var subDir = Path.Combine(_tempDir, "sub");
        var subVscode = Path.Combine(subDir, ".vscode");
        Directory.CreateDirectory(subDir);
        Directory.SetCurrentDirectory(subDir);

        var adapter = new VSCodeClientAdapter();

        var newConfig = new Dictionary<string, object?>
        {
            ["servers"] = new Dictionary<string, object?>
            {
                ["test-server"] = new Dictionary<string, object?>
                {
                    ["type"] = "stdio",
                    ["command"] = "uvx",
                }
            }
        };

        var result = adapter.UpdateConfig(newConfig);
        result.Should().BeTrue();

        var createdPath = Path.Combine(subVscode, "mcp.json");
        File.Exists(createdPath).Should().BeTrue();
        var text = File.ReadAllText(createdPath);
        var json = JsonNode.Parse(text);
        json!["servers"]!["test-server"]!["type"]!.GetValue<string>().Should().Be("stdio");

        // Restore CWD for cleanup
        Directory.SetCurrentDirectory(_tempDir);
    }

    [Fact]
    public void ConfigureMcpServer_EmptyUrl_ReturnsFalse()
    {
        var adapter = new VSCodeClientAdapter();
        var result = adapter.ConfigureMcpServer(serverUrl: "");
        result.Should().BeFalse();
    }

    [Fact]
    public void ConfigureMcpServer_WhitespaceUrl_ReturnsFalse()
    {
        var adapter = new VSCodeClientAdapter();
        var result = adapter.ConfigureMcpServer(serverUrl: "   ");
        result.Should().BeFalse();
    }

    [Fact]
    public void GetConfigPath_ReturnsMcpJsonInVscodeDir()
    {
        var adapter = new VSCodeClientAdapter();
        var path = adapter.GetConfigPath();

        Path.GetFileName(path).Should().Be("mcp.json");
        Path.GetFileName(Path.GetDirectoryName(path)!).Should().Be(".vscode");
    }

    [Fact]
    public void GetCurrentConfig_MissingFile_ReturnsEmptyDict()
    {
        File.Delete(_configPath);

        var adapter = new VSCodeClientAdapter();
        var config = adapter.GetCurrentConfig();

        config.Should().BeEmpty();
    }
}

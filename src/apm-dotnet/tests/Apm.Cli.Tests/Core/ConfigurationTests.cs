using System.Reflection;
using System.Text.Json.Nodes;
using Apm.Cli.Core;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Core;

/// <summary>
/// Tests for Configuration class using reflection to override static paths.
/// </summary>
public class ConfigurationTests : IDisposable
{
    private readonly string _originalConfigDir;
    private readonly string _originalConfigFile;
    private readonly string _tempDir;

    public ConfigurationTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm_config_test_{Guid.NewGuid()}");
        Directory.CreateDirectory(_tempDir);

        // Save original values
        var configDirField = typeof(Configuration).GetField("ConfigDir", BindingFlags.NonPublic | BindingFlags.Static)!;
        var configFileField = typeof(Configuration).GetField("ConfigFile", BindingFlags.NonPublic | BindingFlags.Static)!;

        _originalConfigDir = (string)configDirField.GetValue(null)!;
        _originalConfigFile = (string)configFileField.GetValue(null)!;

        // Override with temp paths
        configDirField.SetValue(null, _tempDir);
        configFileField.SetValue(null, Path.Combine(_tempDir, "config.json"));
    }

    public void Dispose()
    {
        // Restore original values
        var configDirField = typeof(Configuration).GetField("ConfigDir", BindingFlags.NonPublic | BindingFlags.Static)!;
        var configFileField = typeof(Configuration).GetField("ConfigFile", BindingFlags.NonPublic | BindingFlags.Static)!;

        configDirField.SetValue(null, _originalConfigDir);
        configFileField.SetValue(null, _originalConfigFile);

        try { Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void EnsureConfigExists_CreatesDirectoryAndFile()
    {
        // Delete temp dir to verify it's created
        Directory.Delete(_tempDir, true);

        Configuration.EnsureConfigExists();

        Directory.Exists(_tempDir).Should().BeTrue();
        File.Exists(Path.Combine(_tempDir, "config.json")).Should().BeTrue();
    }

    [Fact]
    public void EnsureConfigExists_DefaultConfig_HasDefaultClient()
    {
        Configuration.EnsureConfigExists();

        var content = File.ReadAllText(Path.Combine(_tempDir, "config.json"));
        var json = JsonNode.Parse(content);
        json!["default_client"]!.GetValue<string>().Should().Be("vscode");
    }

    [Fact]
    public void GetConfig_ReturnsDefaultConfig()
    {
        var config = Configuration.GetConfig();
        config.Should().ContainKey("default_client");
        config["default_client"]!.GetValue<string>().Should().Be("vscode");
    }

    [Fact]
    public void UpdateConfig_MergesValues()
    {
        Configuration.EnsureConfigExists();

        Configuration.UpdateConfig(new Dictionary<string, JsonNode?>
        {
            ["custom_key"] = JsonValue.Create("custom_value")
        });

        var config = Configuration.GetConfig();
        config.Should().ContainKey("default_client");
        config.Should().ContainKey("custom_key");
        config["custom_key"]!.GetValue<string>().Should().Be("custom_value");
    }

    [Fact]
    public void UpdateConfig_OverwritesExistingKey()
    {
        Configuration.EnsureConfigExists();

        Configuration.UpdateConfig(new Dictionary<string, JsonNode?>
        {
            ["default_client"] = JsonValue.Create("claude")
        });

        var config = Configuration.GetConfig();
        config["default_client"]!.GetValue<string>().Should().Be("claude");
    }

    [Fact]
    public void GetDefaultClient_ReturnsVscodeByDefault()
    {
        Configuration.GetDefaultClient().Should().Be("vscode");
    }

    [Fact]
    public void SetDefaultClient_UpdatesValue()
    {
        Configuration.SetDefaultClient("claude");
        Configuration.GetDefaultClient().Should().Be("claude");
    }

    [Fact]
    public void SetDefaultClient_ThenGet_RoundTrips()
    {
        Configuration.SetDefaultClient("windsurf");
        Configuration.GetDefaultClient().Should().Be("windsurf");

        Configuration.SetDefaultClient("vscode");
        Configuration.GetDefaultClient().Should().Be("vscode");
    }
}

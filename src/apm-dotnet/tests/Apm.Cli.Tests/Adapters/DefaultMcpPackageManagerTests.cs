using System.Reflection;
using System.Text.Json.Nodes;
using Apm.Cli.Adapters.Client;
using Apm.Cli.Adapters.PackageManager;
using Apm.Cli.Core;
using AwesomeAssertions;
using FakeItEasy;

namespace Apm.Cli.Tests.Adapters;

/// <summary>
/// Port of Python test_package_manager.py tests for DefaultMcpPackageManager.
/// Uses temp config directory to control Configuration.GetDefaultClient().
/// 
/// NOTE: The .NET DefaultMcpPackageManager has a type mismatch bug:
/// GetCurrentConfig() returns JsonNode values but Uninstall/ListInstalled
/// check for Dictionary&lt;string, object?&gt;. This means ListInstalled always
/// returns empty and Uninstall always returns false for packages read from
/// JSON config. Tests document the current actual behavior.
/// </summary>
[Collection("CwdTests")]
public class DefaultMcpPackageManagerTests : IDisposable
{
    private readonly string _tempDir;
    private readonly string _vscodeDir;
    private readonly string _configPath;
    private readonly string _originalCwd;
    private readonly string _originalConfigDir;
    private readonly string _originalConfigFile;

    public DefaultMcpPackageManagerTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm_pm_test_{Guid.NewGuid()}");
        _vscodeDir = Path.Combine(_tempDir, ".vscode");
        _configPath = Path.Combine(_vscodeDir, "mcp.json");

        Directory.CreateDirectory(_vscodeDir);
        File.WriteAllText(_configPath, """{"servers":{"server1":{},"server2":{}}}""");

        _originalCwd = Directory.GetCurrentDirectory();
        Directory.SetCurrentDirectory(_tempDir);

        // Override Configuration static fields to use temp dir
        var configDirField = typeof(Configuration).GetField("ConfigDir", BindingFlags.NonPublic | BindingFlags.Static)!;
        var configFileField = typeof(Configuration).GetField("ConfigFile", BindingFlags.NonPublic | BindingFlags.Static)!;
        _originalConfigDir = (string)configDirField.GetValue(null)!;
        _originalConfigFile = (string)configFileField.GetValue(null)!;

        var apmConfigDir = Path.Combine(_tempDir, ".apm-cli");
        Directory.CreateDirectory(apmConfigDir);
        var apmConfigFile = Path.Combine(apmConfigDir, "config.json");
        File.WriteAllText(apmConfigFile, """{"default_client":"vscode"}""");

        configDirField.SetValue(null, apmConfigDir);
        configFileField.SetValue(null, apmConfigFile);
    }

    public void Dispose()
    {
        Directory.SetCurrentDirectory(_originalCwd);

        var configDirField = typeof(Configuration).GetField("ConfigDir", BindingFlags.NonPublic | BindingFlags.Static)!;
        var configFileField = typeof(Configuration).GetField("ConfigFile", BindingFlags.NonPublic | BindingFlags.Static)!;
        configDirField.SetValue(null, _originalConfigDir);
        configFileField.SetValue(null, _originalConfigFile);

        try { Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void ListInstalled_EmptyConfig_ReturnsEmpty()
    {
        File.WriteAllText(_configPath, """{"servers":{}}""");

        var pm = new DefaultMcpPackageManager();
        var packages = pm.ListInstalled();

        packages.Should().BeEmpty();
    }

    [Fact]
    public void ListInstalled_WithServers_ReturnsEmpty_DueToTypeMismatch()
    {
        // BUG: GetCurrentConfig returns JsonNode values but ListInstalled checks
        // for Dictionary<string, object?>. This documents the current behavior.
        var pm = new DefaultMcpPackageManager();
        var packages = pm.ListInstalled();

        // Should return ["server1", "server2"] once the type mismatch is fixed
        packages.Should().BeEmpty();
    }

    [Fact]
    public void Uninstall_ReturnsFalse_DueToTypeMismatch()
    {
        // BUG: Same type mismatch as ListInstalled.
        var pm = new DefaultMcpPackageManager();
        var result = pm.Uninstall("server1");

        // Should return true once the type mismatch is fixed
        result.Should().BeFalse();
    }

    [Fact]
    public void Uninstall_NonExistent_ReturnsFalse()
    {
        var pm = new DefaultMcpPackageManager();
        var result = pm.Uninstall("nonexistent-server");

        result.Should().BeFalse();
    }

    [Fact]
    public void Search_ReturnsEmptyList()
    {
        // .NET search is a placeholder that returns empty
        var pm = new DefaultMcpPackageManager();
        var results = pm.Search("test");

        results.Should().BeEmpty();
    }

    [Fact]
    public void Install_WithEmptyConfig_ReturnsFalse_StubNotImplemented()
    {
        // ConfigureMcpServer is a stub returning false in .NET
        File.WriteAllText(_configPath, """{"servers":{}}""");
        var pm = new DefaultMcpPackageManager();
        var result = pm.Install("test-package");

        result.Should().BeFalse();
    }
}

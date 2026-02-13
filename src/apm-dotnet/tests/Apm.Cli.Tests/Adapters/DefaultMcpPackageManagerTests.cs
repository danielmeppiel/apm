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
    public void ListInstalled_WithServers_ReturnsServerNames()
    {
        var pm = new DefaultMcpPackageManager();
        var packages = pm.ListInstalled();

        packages.Should().HaveCount(2);
        packages.Should().Contain("server1");
        packages.Should().Contain("server2");
    }

    [Fact]
    public void Uninstall_ExistingServer_ReturnsTrue()
    {
        var pm = new DefaultMcpPackageManager();
        var result = pm.Uninstall("server1");

        result.Should().BeTrue();

        // Verify it was removed from config
        var remaining = pm.ListInstalled();
        remaining.Should().NotContain("server1");
        remaining.Should().Contain("server2");
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
        var pm = new DefaultMcpPackageManager();
        var results = pm.Search("test");

        results.Should().BeEmpty();
    }

    [Fact]
    public void Install_WithEmptyConfig_ReturnsFalse_StubNotImplemented()
    {
        File.WriteAllText(_configPath, """{"servers":{}}""");
        var pm = new DefaultMcpPackageManager();
        var result = pm.Install("test-package");

        result.Should().BeFalse();
    }
}

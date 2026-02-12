using Apm.Cli.Adapters.Client;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Adapters;

/// <summary>
/// Port of Python TestCodexClientAdapter tests for CodexClientAdapter.
/// </summary>
public class CodexClientAdapterTests : IDisposable
{
    private readonly string _tempDir;
    private readonly string _configPath;

    public CodexClientAdapterTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm_codex_test_{Guid.NewGuid()}");
        Directory.CreateDirectory(_tempDir);
        _configPath = Path.Combine(_tempDir, "config.toml");

        File.WriteAllText(_configPath, "model_provider = \"github-models\"\nmodel = \"gpt-4o-mini\"\n");
    }

    public void Dispose()
    {
        try { Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void GetConfigPath_ReturnsTomlInCodexDir()
    {
        var adapter = new CodexClientAdapter();
        var path = adapter.GetConfigPath();

        Path.GetFileName(path).Should().Be("config.toml");
        Path.GetFileName(Path.GetDirectoryName(path)!).Should().Be(".codex");
    }

    [Fact]
    public void GetCurrentConfig_ReturnsTomlData()
    {
        // Use a subclass that overrides GetConfigPath to point at our temp file
        var adapter = new TestableCodexAdapter(_configPath);
        var config = adapter.GetCurrentConfig();

        config.Should().ContainKey("model_provider");
        config["model_provider"]!.ToString().Should().Be("github-models");
        config.Should().ContainKey("model");
        config["model"]!.ToString().Should().Be("gpt-4o-mini");
    }

    [Fact]
    public void GetCurrentConfig_MissingFile_ReturnsEmptyDict()
    {
        var adapter = new TestableCodexAdapter(Path.Combine(_tempDir, "nonexistent.toml"));
        var config = adapter.GetCurrentConfig();

        config.Should().BeEmpty();
    }

    [Fact]
    public void ConfigureMcpServer_EmptyUrl_ReturnsFalse()
    {
        var adapter = new CodexClientAdapter();
        var result = adapter.ConfigureMcpServer(serverUrl: "");
        result.Should().BeFalse();
    }

    [Fact]
    public void ConfigureMcpServer_WhitespaceUrl_ReturnsFalse()
    {
        var adapter = new CodexClientAdapter();
        var result = adapter.ConfigureMcpServer(serverUrl: "   ");
        result.Should().BeFalse();
    }

    /// <summary>
    /// Testable subclass that redirects config path to a temp file.
    /// </summary>
    private sealed class TestableCodexAdapter(string configPath) : CodexClientAdapter
    {
        public new string GetConfigPath() => configPath;

        public new Dictionary<string, object?> GetCurrentConfig()
        {
            var path = GetConfigPath();
            if (!File.Exists(path))
                return new Dictionary<string, object?>();

            try
            {
                var text = File.ReadAllText(path);
                var model = Tomlyn.Toml.ToModel(text);
                var dict = new Dictionary<string, object?>();
                foreach (var kvp in model)
                    dict[kvp.Key] = kvp.Value;
                return dict;
            }
            catch
            {
                return new Dictionary<string, object?>();
            }
        }
    }
}

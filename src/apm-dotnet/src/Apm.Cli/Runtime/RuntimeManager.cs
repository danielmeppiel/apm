using System.Diagnostics;

namespace Apm.Cli.Runtime;

/// <summary>
/// Manages AI runtime installation, configuration, and status checking.
/// </summary>
public sealed class RuntimeManager
{
    private static readonly string RuntimeDir = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".apm", "runtimes");

    private static readonly Dictionary<string, RuntimeInfo> SupportedRuntimes = new()
    {
        ["copilot"] = new("GitHub Copilot CLI with native MCP integration", "copilot"),
        ["codex"] = new("OpenAI Codex CLI with GitHub Models support", "codex"),
        ["llm"] = new("Simon Willison's LLM library with multiple providers", "llm"),
    };

    /// <summary>List available and installed runtimes with their status.</summary>
    public Dictionary<string, Dictionary<string, object>> ListRuntimes()
    {
        var result = new Dictionary<string, Dictionary<string, object>>();

        foreach (var (name, info) in SupportedRuntimes)
        {
            var binaryPath = Path.Combine(RuntimeDir, info.Binary);
            bool installed;
            string? path;

            if (File.Exists(binaryPath))
            {
                installed = true;
                path = binaryPath;
            }
            else
            {
                path = FindInPath(info.Binary);
                installed = path is not null;
            }

            var status = new Dictionary<string, object>
            {
                ["description"] = info.Description,
                ["installed"] = installed,
                ["path"] = path ?? ""
            };

            if (installed)
                status["version"] = GetToolVersion(info.Binary);

            result[name] = status;
        }

        return result;
    }

    /// <summary>Check if a specific runtime is installed and available.</summary>
    public bool IsRuntimeAvailable(string runtimeName)
    {
        if (!SupportedRuntimes.TryGetValue(runtimeName, out var info))
            return false;

        var apmBinary = Path.Combine(RuntimeDir, info.Binary);
        if (File.Exists(apmBinary))
            return true;

        return FindInPath(info.Binary) is not null;
    }

    /// <summary>Get the runtime preference order.</summary>
    public static IReadOnlyList<string> GetRuntimePreference() => ["copilot", "codex", "llm"];

    /// <summary>Get the first available runtime based on preference.</summary>
    public string? GetAvailableRuntime()
    {
        foreach (var runtime in GetRuntimePreference())
        {
            if (IsRuntimeAvailable(runtime))
                return runtime;
        }

        return null;
    }

    private static string? FindInPath(string executable)
    {
        var pathVar = Environment.GetEnvironmentVariable("PATH") ?? "";
        var separator = OperatingSystem.IsWindows() ? ';' : ':';
        var extensions = OperatingSystem.IsWindows()
            ? new[] { ".exe", ".cmd", ".bat", "" }
            : new[] { "" };

        foreach (var dir in pathVar.Split(separator, StringSplitOptions.RemoveEmptyEntries))
        {
            foreach (var ext in extensions)
            {
                var fullPath = Path.Combine(dir, executable + ext);
                if (File.Exists(fullPath))
                    return fullPath;
            }
        }

        return null;
    }

    private static string GetToolVersion(string tool)
    {
        try
        {
            var psi = new ProcessStartInfo(tool, "--version")
            {
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            using var process = Process.Start(psi);
            if (process is null) return "unknown";

            var output = process.StandardOutput.ReadToEnd().Trim();
            process.WaitForExit(5_000);
            return process.ExitCode == 0 ? output : "unknown";
        }
        catch
        {
            return "unknown";
        }
    }

    private record RuntimeInfo(string Description, string Binary);
}

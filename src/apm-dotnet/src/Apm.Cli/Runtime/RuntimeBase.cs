using System.Diagnostics;

namespace Apm.Cli.Runtime;

/// <summary>
/// Abstract base class for runtime adapters with shared process-execution helpers.
/// </summary>
public abstract class RuntimeBase : IRuntimeAdapter
{
    public string? ModelName { get; }

    protected RuntimeBase(string? modelName = null)
    {
        ModelName = modelName;
    }

    public abstract string ExecutePrompt(string promptContent, Dictionary<string, object>? kwargs = null);
    public abstract Dictionary<string, object> ListAvailableModels();
    public abstract Dictionary<string, object> GetRuntimeInfo();

    /// <summary>
    /// Run a process and stream its stdout to the console in real-time.
    /// Returns the combined output and exit code.
    /// </summary>
    protected static (string Output, int ExitCode) RunProcessStreaming(
        string fileName, IEnumerable<string> arguments, TimeSpan timeout)
    {
        var psi = new ProcessStartInfo(fileName)
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };

        foreach (var arg in arguments)
            psi.ArgumentList.Add(arg);

        using var process = Process.Start(psi)
            ?? throw new InvalidOperationException($"Failed to start {fileName}");

        var outputLines = new List<string>();

        // Stream output in real-time
        while (!process.StandardOutput.EndOfStream)
        {
            var line = process.StandardOutput.ReadLine();
            if (line is not null)
            {
                Console.WriteLine(line);
                outputLines.Add(line);
            }
        }

        if (!process.WaitForExit((int)timeout.TotalMilliseconds))
        {
            process.Kill(entireProcessTree: true);
            throw new TimeoutException($"{fileName} execution timed out after {timeout.TotalMinutes:F0} minutes");
        }

        return (string.Join(Environment.NewLine, outputLines).Trim(), process.ExitCode);
    }

    /// <summary>Try to get the version of a CLI tool.</summary>
    protected static string GetToolVersion(string tool)
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
            process.WaitForExit(10_000);
            return process.ExitCode == 0 ? output : "unknown";
        }
        catch
        {
            return "unknown";
        }
    }

    /// <summary>Check if an executable is available on the system PATH.</summary>
    protected static bool IsToolAvailable(string tool)
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
                if (File.Exists(Path.Combine(dir, tool + ext)))
                    return true;
            }
        }

        return false;
    }

    public override string ToString() => $"{GetType().Name}(model={ModelName})";
}

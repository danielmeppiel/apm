namespace Apm.Cli.Output;

/// <summary>Professional formatter for script execution output following CLI UX design plan.</summary>
public class ScriptExecutionFormatter
{
    private readonly bool _useColor;

    public ScriptExecutionFormatter(bool useColor = true)
    {
        _useColor = useColor;
    }

    /// <summary>Format the script execution header with parameters.</summary>
    public List<string> FormatScriptHeader(string scriptName, Dictionary<string, string> parameters)
    {
        var lines = new List<string> { $"🚀 Running script: {scriptName}" };

        foreach (var (name, value) in parameters)
            lines.Add($"  - {name}: {value}");

        return lines;
    }

    /// <summary>Format prompt compilation progress.</summary>
    public List<string> FormatCompilationProgress(List<string> promptFiles)
    {
        if (promptFiles.Count == 0) return [];

        var lines = new List<string>
        {
            promptFiles.Count == 1
                ? "Compiling prompt..."
                : $"Compiling {promptFiles.Count} prompts..."
        };

        for (var i = 0; i < promptFiles.Count; i++)
        {
            var prefix = i < promptFiles.Count - 1 ? "├─" : "└─";
            lines.Add($"{prefix} {promptFiles[i]}");
        }

        return lines;
    }

    /// <summary>Format runtime command execution with content preview.</summary>
    public List<string> FormatRuntimeExecution(string runtime, string command, int contentLength)
    {
        return
        [
            $"Executing {runtime} runtime...",
            $"├─ Command: {command}",
            $"└─ Prompt content: {contentLength:N0} characters"
        ];
    }

    /// <summary>Format content preview with professional styling.</summary>
    public List<string> FormatContentPreview(string content, int maxPreview = 200)
    {
        var preview = content.Length > maxPreview ? content[..maxPreview] + "..." : content;
        return
        [
            "Prompt preview:",
            new string('─', 50),
            preview,
            new string('─', 50)
        ];
    }

    /// <summary>Format environment setup information.</summary>
    public List<string> FormatEnvironmentSetup(string runtime, List<string> envVarsSet)
    {
        if (envVarsSet.Count == 0) return [];

        var lines = new List<string> { "Environment setup:" };

        for (var i = 0; i < envVarsSet.Count; i++)
        {
            var prefix = i < envVarsSet.Count - 1 ? "├─" : "└─";
            lines.Add($"{prefix} {envVarsSet[i]}: configured");
        }

        return lines;
    }

    /// <summary>Format successful execution result.</summary>
    public List<string> FormatExecutionSuccess(string runtime, double? executionTime = null)
    {
        var msg = $"✅ {Capitalize(runtime)} execution completed successfully";
        if (executionTime.HasValue)
            msg += $" ({executionTime.Value:F2}s)";
        return [msg];
    }

    /// <summary>Format execution error result.</summary>
    public List<string> FormatExecutionError(string runtime, int errorCode, string? errorMsg = null)
    {
        var lines = new List<string> { $"✗ {Capitalize(runtime)} execution failed (exit code: {errorCode})" };

        if (!string.IsNullOrEmpty(errorMsg))
        {
            foreach (var line in errorMsg.Split('\n'))
            {
                if (!string.IsNullOrWhiteSpace(line))
                    lines.Add($"  {line}");
            }
        }

        return lines;
    }

    /// <summary>Format subprocess execution details for debugging.</summary>
    public List<string> FormatSubprocessDetails(List<string> args, int contentLength)
    {
        var argsDisplay = string.Join(" ", args.Select(a => a.Contains(' ') ? $"\"{a}\"" : a));
        return
        [
            "Subprocess execution:",
            $"├─ Args: {argsDisplay}",
            $"└─ Content: +{contentLength:N0} chars appended"
        ];
    }

    /// <summary>Format message for auto-discovered prompts.</summary>
    public string FormatAutoDiscoveryMessage(string scriptName, string promptFile, string runtime)
        => $"ℹ Auto-discovered: {promptFile} (runtime: {runtime})";

    private static string Capitalize(string s)
        => string.IsNullOrEmpty(s) ? s : char.ToUpper(s[0]) + s[1..];
}

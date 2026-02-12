using System.ComponentModel;
using Spectre.Console;
using Spectre.Console.Cli;
using Apm.Cli.Core;
using Apm.Cli.Utils;

namespace Apm.Cli.Commands;

public sealed class PreviewSettings : CommandSettings
{
    [CommandArgument(0, "[script]")]
    [Description("Script name to preview")]
    public string? ScriptName { get; set; }

    [CommandOption("-p|--param")]
    [Description("Parameter in format name=value")]
    public string[]? Params { get; set; }
}

public sealed class PreviewCommand : Command<PreviewSettings>
{
    public override int Execute(CommandContext context, PreviewSettings settings, CancellationToken cancellation)
    {
        try
        {
            var scriptRunner = new ScriptRunner();
            var scriptName = settings.ScriptName;

            // Default to 'start' script if none specified
            if (string.IsNullOrEmpty(scriptName))
            {
                var allScripts = scriptRunner.ListScripts();
                if (allScripts.TryGetValue("start", out _))
                {
                    scriptName = "start";
                }
                else
                {
                    ConsoleHelpers.Error("No script specified and no 'start' script defined in apm.yml");
                    return 1;
                }
            }

            ConsoleHelpers.Info($"Previewing script: {scriptName}", symbol: "info");

            // Parse parameters
            var parameters = new Dictionary<string, string>();
            if (settings.Params is not null)
            {
                foreach (var p in settings.Params)
                {
                    if (p.Contains('='))
                    {
                        var eqIdx = p.IndexOf('=');
                        var paramName = p[..eqIdx];
                        var value = p[(eqIdx + 1)..];
                        parameters[paramName] = value;
                        ConsoleHelpers.Echo($"  - {paramName}: {value}", color: "dim");
                    }
                }
            }

            // Get the script command
            var scripts = scriptRunner.ListScripts();
            if (!scripts.TryGetValue(scriptName, out var command))
            {
                ConsoleHelpers.Error($"Script '{scriptName}' not found");
                return 1;
            }

            // Show original command
            ConsoleHelpers.Panel(command, title: "📄 Original command", borderStyle: "blue");

            // Auto-compile prompts to show what would be executed
            var (compiledCommand, compiledFiles) = PreviewAutoCompilePrompts(
                command, parameters, scriptRunner);

            if (compiledFiles.Count > 0)
            {
                ConsoleHelpers.Panel(compiledCommand, title: "⚡ Compiled command", borderStyle: "green");

                // Show compiled files
                var fileLines = compiledFiles
                    .Select(f =>
                    {
                        var stem = Path.GetFileNameWithoutExtension(
                            Path.GetFileNameWithoutExtension(f));
                        var compiledPath = Path.Combine(".apm", "compiled", $"{stem}.txt");
                        return $"📄 {compiledPath}";
                    });
                ConsoleHelpers.Panel(
                    string.Join("\n", fileLines),
                    title: "📁 Compiled prompt files",
                    borderStyle: "cyan");
            }
            else
            {
                ConsoleHelpers.Panel(compiledCommand,
                    title: "⚡ Command (no prompt compilation)",
                    borderStyle: "yellow");

                ConsoleHelpers.Panel(
                    "No .prompt.md files were compiled.\n\n" +
                    "APM only compiles files ending with '.prompt.md' extension.\n" +
                    "Other files are executed as-is by the runtime.",
                    title: "ℹ️  Compilation Info",
                    borderStyle: "cyan");
            }

            AnsiConsole.WriteLine();
            ConsoleHelpers.Success(
                $"Preview complete! Use 'apm run {scriptName}' to execute.",
                symbol: "sparkles");
            return 0;
        }
        catch (Exception e)
        {
            ConsoleHelpers.Error($"Error previewing script: {e.Message}");
            return 1;
        }
    }

    /// <summary>
    /// Preview-only prompt compilation: detects .prompt.md files in the command
    /// and simulates compilation without executing.
    /// </summary>
    private static (string CompiledCommand, List<string> CompiledFiles) PreviewAutoCompilePrompts(
        string command, Dictionary<string, string> parameters, ScriptRunner scriptRunner)
    {
        // Find .prompt.md file references in the command
        var promptFilePattern = new System.Text.RegularExpressions.Regex(@"\S+\.prompt\.md");
        var matches = promptFilePattern.Matches(command);
        var compiledFiles = new List<string>();
        var compiledCommand = command;

        foreach (System.Text.RegularExpressions.Match match in matches)
        {
            var promptFile = match.Value;
            compiledFiles.Add(promptFile);

            // Build compiled path for display
            var stem = Path.GetFileNameWithoutExtension(
                Path.GetFileNameWithoutExtension(promptFile));
            var compiledPath = Path.Combine(".apm", "compiled", $"{stem}.txt");
            compiledCommand = compiledCommand.Replace(promptFile, compiledPath);
        }

        return (compiledCommand, compiledFiles);
    }
}

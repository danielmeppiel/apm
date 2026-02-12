using System.ComponentModel;
using Spectre.Console;
using Spectre.Console.Cli;
using Apm.Cli.Core;
using Apm.Cli.Utils;

namespace Apm.Cli.Commands;

public sealed class RunSettings : CommandSettings
{
    [CommandArgument(0, "[script]")]
    [Description("Script name to run")]
    public string? ScriptName { get; set; }

    [CommandOption("-p|--param")]
    [Description("Parameter in format name=value")]
    public string[]? Params { get; set; }
}

public sealed class RunCommand : Command<RunSettings>
{
    public override int Execute(CommandContext context, RunSettings settings, CancellationToken cancellation)
    {
        try
        {
            var scriptRunner = new ScriptRunner();
            var scriptName = settings.ScriptName;

            // Default to 'start' script if none specified
            if (string.IsNullOrEmpty(scriptName))
            {
                var scripts = scriptRunner.ListScripts();
                if (scripts.TryGetValue("start", out _))
                {
                    scriptName = "start";
                }
                else
                {
                    ConsoleHelpers.Error("No script specified and no 'start' script defined in apm.yml");
                    ConsoleHelpers.Info("Available scripts:");

                    if (scripts.Count > 0)
                    {
                        var table = new Table { Border = TableBorder.None };
                        table.AddColumn(new TableColumn("Icon").NoWrap());
                        table.AddColumn(new TableColumn("Script").NoWrap());
                        table.AddColumn(new TableColumn("Command"));

                        foreach (var (name, command) in scripts)
                            table.AddRow("  ", $"[cyan]{Markup.Escape(name)}[/]", Markup.Escape(command));

                        AnsiConsole.Write(table);
                    }
                    else
                    {
                        ConsoleHelpers.Warning("No scripts defined in apm.yml");
                    }

                    return 1;
                }
            }

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

            // Execute the script
            var success = scriptRunner.RunScript(scriptName, parameters);

            if (!success)
            {
                ConsoleHelpers.Error("Script execution failed");
                return 1;
            }

            AnsiConsole.WriteLine();
            ConsoleHelpers.Success("Script executed successfully!", symbol: "sparkles");
            return 0;
        }
        catch (Exception e)
        {
            ConsoleHelpers.Error($"Error running script: {e.Message}");
            return 1;
        }
    }
}

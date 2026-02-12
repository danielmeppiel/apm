using Spectre.Console;
using Spectre.Console.Cli;
using Apm.Cli.Core;
using Apm.Cli.Utils;

namespace Apm.Cli.Commands;

public sealed class ListSettings : CommandSettings
{
}

public sealed class ListCommand : Command<ListSettings>
{
    public override int Execute(CommandContext context, ListSettings settings, CancellationToken cancellation)
    {
        try
        {
            var scriptRunner = new ScriptRunner();
            var scripts = scriptRunner.ListScripts();

            if (scripts.Count == 0)
            {
                ConsoleHelpers.Warning("No scripts found.");

                var example = """
                    scripts:
                      start: "codex run main.prompt.md"
                      fast: "llm prompt main.prompt.md -m github/gpt-4o-mini"
                    """;

                ConsoleHelpers.Panel(example,
                    title: $"{ConsoleHelpers.GetSymbol("info")} Add scripts to your apm.yml file",
                    borderStyle: "blue");
                return 0;
            }

            string? defaultScript = scripts.ContainsKey("start") ? "start" : null;

            var table = new Table()
                .Title("📋 Available Scripts")
                .Border(TableBorder.Rounded);

            table.AddColumn(new TableColumn("").Width(3));
            table.AddColumn(new TableColumn("[bold cyan]Script[/]").NoWrap());
            table.AddColumn(new TableColumn("[bold cyan]Command[/]"));

            foreach (var (name, command) in scripts)
            {
                var icon = name == defaultScript
                    ? ConsoleHelpers.GetSymbol("default")
                    : "  ";
                table.AddRow(
                    Markup.Escape(icon),
                    $"[bold white]{Markup.Escape(name)}[/]",
                    Markup.Escape(command));
            }

            AnsiConsole.Write(table);

            if (defaultScript is not null)
            {
                AnsiConsole.MarkupLine(
                    $"\n[dim]{ConsoleHelpers.GetSymbol("info")} {ConsoleHelpers.GetSymbol("default")} = default script (runs when no script name specified)[/]");
            }

            return 0;
        }
        catch (Exception ex)
        {
            ConsoleHelpers.Error($"Error listing scripts: {ex.Message}");
            return 1;
        }
    }
}

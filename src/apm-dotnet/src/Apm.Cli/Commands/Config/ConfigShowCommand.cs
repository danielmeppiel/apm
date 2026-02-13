using Spectre.Console;
using Spectre.Console.Cli;
using Apm.Cli.Core;
using Apm.Cli.Models;
using Apm.Cli.Utils;

namespace Apm.Cli.Commands.Config;

public sealed class ConfigShowSettings : CommandSettings
{
}

public sealed class ConfigShowCommand : Command<ConfigShowSettings>
{
    public override int Execute(CommandContext context, ConfigShowSettings settings, CancellationToken cancellation)
    {
        var table = new Table()
        {
            Border = TableBorder.Rounded,
        };
        table.Title = new TableTitle("⚙️  Current APM Configuration");
        table.AddColumn(new TableColumn("[bold yellow]Category[/]") { NoWrap = true });
        table.AddColumn(new TableColumn("[bold white]Setting[/]") { NoWrap = true });
        table.AddColumn(new TableColumn("[bold cyan]Value[/]"));

        if (File.Exists("apm.yml"))
        {
            try
            {
                var pkg = ApmPackage.FromApmYml(Path.GetFullPath("apm.yml"));
                table.AddRow("Project", "Name", Markup.Escape(pkg.Name));
                table.AddRow("", "Version", Markup.Escape(pkg.Version));
                table.AddRow("", "MCP Dependencies", pkg.GetMcpDependencies().Count.ToString());

                // Compilation settings would go here when available
            }
            catch
            {
                table.AddRow("Project", "Status", "Error reading apm.yml");
            }
        }
        else
        {
            table.AddRow("Project", "Status", "Not in an APM project directory");
        }

        table.AddRow("Global", "APM CLI Version", Markup.Escape(VersionInfo.GetVersion()));
        table.AddRow("", "Default Client", Markup.Escape(Configuration.GetDefaultClient()));

        AnsiConsole.Write(table);
        return 0;
    }
}

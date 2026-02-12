using System.ComponentModel;
using System.Text.Json.Nodes;
using Spectre.Console;
using Spectre.Console.Cli;
using Apm.Cli.Core;
using Apm.Cli.Utils;

namespace Apm.Cli.Commands.Config;

public sealed class ConfigGetSettings : CommandSettings
{
    [CommandArgument(0, "[key]")]
    [Description("Configuration key to retrieve")]
    public string? Key { get; set; }
}

public sealed class ConfigGetCommand : Command<ConfigGetSettings>
{
    private static readonly HashSet<string> ValidKeys = ["auto-integrate"];

    public override int Execute(CommandContext context, ConfigGetSettings settings, CancellationToken cancellation)
    {
        if (!string.IsNullOrEmpty(settings.Key))
        {
            if (settings.Key == "auto-integrate")
            {
                var config = Configuration.GetConfig();
                var value = config.TryGetValue("auto_integrate", out var node) && node is not null
                    ? node.ToString()
                    : "true";
                AnsiConsole.MarkupLine($"auto-integrate: {Markup.Escape(value)}");
            }
            else
            {
                ConsoleHelpers.Error($"Unknown configuration key: '{settings.Key}'");
                ConsoleHelpers.Info($"Valid keys: {string.Join(", ", ValidKeys)}");
                return 1;
            }
        }
        else
        {
            // Show all config
            var config = Configuration.GetConfig();
            ConsoleHelpers.Info("APM Configuration:");
            foreach (var (key, value) in config)
            {
                var displayKey = key == "auto_integrate" ? "auto-integrate" : key;
                AnsiConsole.MarkupLine($"  {Markup.Escape(displayKey)}: {Markup.Escape(value?.ToString() ?? "")}");
            }
        }

        return 0;
    }
}

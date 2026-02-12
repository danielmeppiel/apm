using System.ComponentModel;
using System.Text.Json.Nodes;
using Spectre.Console.Cli;
using Apm.Cli.Core;
using Apm.Cli.Utils;

namespace Apm.Cli.Commands.Config;

public sealed class ConfigSetSettings : CommandSettings
{
    [CommandArgument(0, "<key>")]
    [Description("Configuration key to set")]
    public required string Key { get; set; }

    [CommandArgument(1, "<value>")]
    [Description("Value to set")]
    public required string Value { get; set; }
}

public sealed class ConfigSetCommand : Command<ConfigSetSettings>
{
    private static readonly string[] TrueValues = ["true", "1", "yes"];
    private static readonly string[] FalseValues = ["false", "0", "no"];

    public override int Execute(CommandContext context, ConfigSetSettings settings, CancellationToken cancellation)
    {
        if (settings.Key == "auto-integrate")
        {
            if (TrueValues.Contains(settings.Value, StringComparer.OrdinalIgnoreCase))
            {
                Configuration.UpdateConfig(new Dictionary<string, JsonNode?>
                {
                    ["auto_integrate"] = true
                });
                ConsoleHelpers.Success("Auto-integration enabled");
            }
            else if (FalseValues.Contains(settings.Value, StringComparer.OrdinalIgnoreCase))
            {
                Configuration.UpdateConfig(new Dictionary<string, JsonNode?>
                {
                    ["auto_integrate"] = false
                });
                ConsoleHelpers.Success("Auto-integration disabled");
            }
            else
            {
                ConsoleHelpers.Error($"Invalid value '{settings.Value}'. Use 'true' or 'false'.");
                return 1;
            }
        }
        else
        {
            ConsoleHelpers.Error($"Unknown configuration key: '{settings.Key}'");
            ConsoleHelpers.Info("Valid keys: auto-integrate");
            return 1;
        }

        return 0;
    }
}

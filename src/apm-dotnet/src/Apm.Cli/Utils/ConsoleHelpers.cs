using Spectre.Console;

namespace Apm.Cli.Utils;

/// <summary>
/// Console helper methods ported from Python Rich/Colorama utilities.
/// All output uses Spectre.Console for rich terminal formatting.
/// </summary>
public static class ConsoleHelpers
{
    /// <summary>
    /// Status symbols for consistent iconography across the CLI.
    /// </summary>
    public static readonly IReadOnlyDictionary<string, string> StatusSymbols = new Dictionary<string, string>
    {
        ["success"] = "✨",
        ["sparkles"] = "✨",
        ["running"] = "🚀",
        ["rocket"] = "🚀",
        ["gear"] = "⚙️",
        ["info"] = "💡",
        ["bulb"] = "💡",
        ["warning"] = "⚠️",
        ["error"] = "❌",
        ["check"] = "✅",
        ["cross"] = "❌",
        ["list"] = "📋",
        ["clipboard"] = "📋",
        ["preview"] = "👀",
        ["eyes"] = "👀",
        ["robot"] = "🤖",
        ["metrics"] = "📊",
        ["chart"] = "📊",
        ["default"] = "📍",
        ["folder"] = "📁",
        ["cogs"] = "⚙️",
    };

    /// <summary>
    /// Display a message with optional symbol and color.
    /// </summary>
    public static void Echo(string message, string color = "white", bool bold = false, string? symbol = null)
    {
        if (symbol is not null && StatusSymbols.TryGetValue(symbol, out var emoji))
        {
            message = $"{emoji} {message}";
        }

        var escaped = Markup.Escape(message);
        var style = bold ? $"bold {color}" : color;
        AnsiConsole.MarkupLine($"[{style}]{escaped}[/]");
    }

    /// <summary>
    /// Display a success message in bold green.
    /// </summary>
    public static void Success(string message, string? symbol = null)
    {
        Echo(message, color: "green", bold: true, symbol: symbol);
    }

    /// <summary>
    /// Display an error message in red.
    /// </summary>
    public static void Error(string message, string? symbol = null)
    {
        Echo(message, color: "red", symbol: symbol);
    }

    /// <summary>
    /// Display an info message in blue.
    /// </summary>
    public static void Info(string message, string? symbol = null)
    {
        Echo(message, color: "blue", symbol: symbol);
    }

    /// <summary>
    /// Display a warning message in yellow.
    /// </summary>
    public static void Warning(string message, string? symbol = null)
    {
        Echo(message, color: "yellow", symbol: symbol);
    }

    /// <summary>
    /// Display content in a Spectre.Console panel.
    /// </summary>
    public static void Panel(string content, string? title = null, string borderStyle = "cyan")
    {
        var panel = new Spectre.Console.Panel(Markup.Escape(content));

        if (title is not null)
        {
            panel.Header = new PanelHeader(title);
        }

        panel.Border = BoxBorder.Rounded;
        panel.BorderStyle = Style.Parse(borderStyle);

        AnsiConsole.Write(panel);
    }

    /// <summary>
    /// Create a Spectre.Console table for file display.
    /// </summary>
    public static Table CreateFilesTable(IEnumerable<(string Name, string Description)> files, string title = "Files")
    {
        var table = new Table()
            .Title($"📋 {title}")
            .Border(TableBorder.Rounded);

        table.AddColumn(new TableColumn("[bold]File[/]").NoWrap());
        table.AddColumn(new TableColumn("[bold]Description[/]"));

        foreach (var (name, description) in files)
        {
            table.AddRow(
                Markup.Escape(name),
                Markup.Escape(description));
        }

        return table;
    }

    /// <summary>
    /// Run an action with a spinner status display.
    /// </summary>
    public static void WithSpinner(string statusMessage, Action action)
    {
        AnsiConsole.Status()
            .Spinner(Spinner.Known.Dots)
            .SpinnerStyle(Style.Parse("cyan"))
            .Start(statusMessage, _ => action());
    }

    /// <summary>
    /// Run an async action with a spinner status display.
    /// </summary>
    public static async Task WithSpinnerAsync(string statusMessage, Func<Task> action)
    {
        await AnsiConsole.Status()
            .Spinner(Spinner.Known.Dots)
            .SpinnerStyle(Style.Parse("cyan"))
            .StartAsync(statusMessage, async _ => await action());
    }

    /// <summary>
    /// Get the emoji for a given symbol key, or empty string if not found.
    /// </summary>
    public static string GetSymbol(string key)
    {
        return StatusSymbols.TryGetValue(key, out var symbol) ? symbol : string.Empty;
    }

    /// <summary>
    /// Resolve a color name, providing a safe fallback for Spectre.Console.
    /// </summary>
    private static Color ColorFromName(string name)
    {
        try
        {
            return Style.Parse(name).Foreground;
        }
        catch
        {
            return Color.White;
        }
    }
}

using System.ComponentModel;
using System.Security.Cryptography;
using System.Text;
using Spectre.Console;
using Spectre.Console.Cli;
using Apm.Cli.Compilation;
using Apm.Cli.Core;
using Apm.Cli.Models;
using Apm.Cli.Primitives;
using Apm.Cli.Utils;

namespace Apm.Cli.Commands;

public sealed class CompileSettings : CommandSettings
{
    [CommandOption("-t|--target")]
    [Description("🎯 Target platform: vscode, agents, claude, or all (auto-detects if omitted)")]
    public string? Target { get; set; }

    [CommandOption("--strategy")]
    [Description("Compilation strategy: distributed or single-file")]
    public string? Strategy { get; set; }

    [CommandOption("--single-agents")]
    [Description("📄 Force single-file compilation (legacy mode)")]
    public bool SingleAgents { get; set; }

    [CommandOption("--dry-run")]
    [Description("🔍 Preview compilation without writing files")]
    public bool DryRun { get; set; }

    [CommandOption("-v|--verbose")]
    [Description("🔍 Show detailed source attribution and optimizer analysis")]
    public bool Verbose { get; set; }

    [CommandOption("--trace")]
    [Description("Show source attribution")]
    public bool Trace { get; set; }

    [CommandOption("--local-only")]
    [Description("🏠 Ignore dependencies, compile only local primitives")]
    public bool LocalOnly { get; set; }

    [CommandOption("--debug")]
    [Description("Show optimizer metrics")]
    public bool Debug { get; set; }

    [CommandOption("--no-constitution")]
    [Description("Skip constitution block")]
    public bool NoConstitution { get; set; }

    [CommandOption("--chatmode")]
    [Description("Target specific chatmode")]
    public string? Chatmode { get; set; }

    [CommandOption("--clean")]
    [Description("🧹 Remove orphaned AGENTS.md files that are no longer generated")]
    public bool Clean { get; set; }

    [CommandOption("--exclude")]
    [Description("Glob patterns to exclude from compilation")]
    public string[]? Exclude { get; set; }

    [CommandOption("--watch")]
    [Description("Watch for changes and recompile")]
    public bool Watch { get; set; }

    [CommandOption("--no-links")]
    [Description("Skip markdown link resolution")]
    public bool NoLinks { get; set; }

    [CommandOption("--validate")]
    [Description("Validate primitives without compiling")]
    public bool ValidateOnly { get; set; }
}

public sealed class CompileCommand : Command<CompileSettings>
{
    public override int Execute(CommandContext context, CompileSettings settings, CancellationToken cancellation)
    {
        try
        {
            if (!File.Exists("apm.yml"))
            {
                ConsoleHelpers.Error("❌ Not an APM project - no apm.yml found");
                ConsoleHelpers.Info("💡 To initialize an APM project, run:");
                ConsoleHelpers.Info("   apm init");
                return 1;
            }

            // Check for content to compile
            var apmDir = Path.GetFullPath(".apm");
            var apmModulesExists = Directory.Exists("apm_modules");
            var constitutionPath = Constitution.FindConstitution(".");
            var constitutionExists = File.Exists(constitutionPath);
            var localApmHasContent = Directory.Exists(apmDir)
                && (GlobFiles(apmDir, "*.instructions.md").Any()
                    || GlobFiles(apmDir, "*.chatmode.md").Any());

            if (!apmModulesExists && !localApmHasContent && !constitutionExists)
            {
                var hasEmptyApm = Directory.Exists(apmDir)
                    && !GlobFiles(apmDir, "*.instructions.md").Any()
                    && !GlobFiles(apmDir, "*.chatmode.md").Any();

                if (hasEmptyApm)
                {
                    ConsoleHelpers.Error("❌ No instruction files found in .apm/ directory");
                    ConsoleHelpers.Info("💡 To add instructions, create files like:");
                    ConsoleHelpers.Info("   .apm/instructions/coding-standards.instructions.md");
                    ConsoleHelpers.Info("   .apm/chatmodes/backend-engineer.chatmode.md");
                }
                else
                {
                    ConsoleHelpers.Error("❌ No APM content found to compile");
                    ConsoleHelpers.Info("💡 To get started:");
                    ConsoleHelpers.Info("   1. Install APM dependencies: apm install <owner>/<repo>");
                    ConsoleHelpers.Info("   2. Or create local instructions: mkdir -p .apm/instructions");
                    ConsoleHelpers.Info("   3. Then create .instructions.md or .chatmode.md files");
                }

                if (!settings.DryRun)
                    return 1;
            }

            // Validation-only mode
            if (settings.ValidateOnly)
                return RunValidation();

            // Watch mode
            if (settings.Watch)
                return RunWatchMode(settings, cancellation);

            ConsoleHelpers.Info("Starting context compilation...", symbol: "cogs");

            // Auto-detect target
            string? configTarget = null;
            try
            {
                var apmPkg = ApmPackage.FromApmYml(Path.GetFullPath("apm.yml"));
                configTarget = apmPkg.Target;
            }
            catch { /* proceed with auto-detection */ }

            var (detectedTarget, detectionReason) = TargetDetection.DetectTarget(
                Directory.GetCurrentDirectory(),
                settings.Target,
                configTarget);

            var effectiveTarget = detectedTarget == "minimal" ? "vscode" : detectedTarget;

            // Build compilation config
            var overrides = new Dictionary<string, object?>
            {
                ["chatmode"] = settings.Chatmode,
                ["dry_run"] = settings.DryRun,
                ["single_agents"] = settings.SingleAgents,
                ["trace"] = settings.Trace || settings.Verbose,
                ["local_only"] = settings.LocalOnly,
                ["debug"] = settings.Debug || settings.Verbose,
                ["clean_orphaned"] = settings.Clean,
                ["target"] = effectiveTarget,
            };

            if (settings.NoLinks)
                overrides["resolve_links"] = false;
            if (settings.Strategy is not null)
                overrides["strategy"] = settings.Strategy;
            if (settings.Exclude is { Length: > 0 })
                overrides["exclude"] = settings.Exclude.ToList();

            var config = CompilationConfig.FromApmYml(overrides);
            config.WithConstitution = !settings.NoConstitution;

            // Display target info for distributed mode
            if (config.Strategy == "distributed" && !settings.SingleAgents)
            {
                if (detectedTarget == "minimal")
                {
                    ConsoleHelpers.Info($"Compiling for AGENTS.md only ({detectionReason})");
                    ConsoleHelpers.Info("💡 Create .github/ or .claude/ folder for full integration", symbol: "bulb");
                }
                else if (detectedTarget is "vscode" or "agents")
                    ConsoleHelpers.Info($"Compiling for AGENTS.md (VSCode/Copilot) - {detectionReason}");
                else if (detectedTarget == "claude")
                    ConsoleHelpers.Info($"Compiling for CLAUDE.md (Claude Code) - {detectionReason}");
                else
                    ConsoleHelpers.Info($"Compiling for AGENTS.md + CLAUDE.md - {detectionReason}");

                if (settings.DryRun)
                    ConsoleHelpers.Info("Dry run mode: showing placement without writing files", symbol: "preview");
                if (settings.Verbose)
                    ConsoleHelpers.Info("Verbose mode: showing source attribution and optimizer analysis");
            }
            else
            {
                ConsoleHelpers.Info("Using single-file compilation (legacy mode)");
            }

            // Compile
            var compiler = new AgentsCompiler(".");
            var result = compiler.Compile(config);

            if (result.Success)
            {
                if (config.Strategy == "distributed" && !settings.SingleAgents)
                {
                    if (!settings.DryRun)
                        ConsoleHelpers.Success("Compilation completed successfully!", symbol: "check");
                }
                else
                {
                    HandleSingleFileResult(compiler, config, result, settings);
                }
            }

            // Warnings for single-file mode
            if (config.Strategy != "distributed" || settings.SingleAgents)
            {
                if (result.Warnings.Count > 0)
                {
                    ConsoleHelpers.Warning($"Compilation completed with {result.Warnings.Count} warnings:");
                    foreach (var warning in result.Warnings)
                        AnsiConsole.MarkupLine($"  [yellow]⚠️  {Markup.Escape(warning)}[/]");
                }
            }

            if (result.Errors.Count > 0)
            {
                ConsoleHelpers.Error($"Compilation failed with {result.Errors.Count} errors:");
                foreach (var error in result.Errors)
                    AnsiConsole.MarkupLine($"  [red]❌ {Markup.Escape(error)}[/]");
                return 1;
            }

            return 0;
        }
        catch (Exception ex)
        {
            ConsoleHelpers.Error($"Error during compilation: {ex.Message}");
            return 1;
        }
    }

    private static int RunValidation()
    {
        ConsoleHelpers.Info("Validating APM context...", symbol: "gear");
        var compiler = new AgentsCompiler(".");
        PrimitiveCollection primitives;
        try
        {
            primitives = PrimitiveDiscovery.DiscoverPrimitives(".");
        }
        catch (Exception e)
        {
            ConsoleHelpers.Error($"Failed to discover primitives: {e.Message}");
            return 1;
        }

        var validationErrors = compiler.ValidatePrimitives(primitives);
        if (validationErrors.Count > 0)
        {
            ConsoleHelpers.Error($"Validation failed with {validationErrors.Count} errors");
            return 1;
        }

        ConsoleHelpers.Success("All primitives validated successfully!", symbol: "sparkles");
        ConsoleHelpers.Info($"Validated {primitives.Count()} primitives:");
        ConsoleHelpers.Info($"  • {primitives.Chatmodes.Count} chatmodes");
        ConsoleHelpers.Info($"  • {primitives.Instructions.Count} instructions");
        ConsoleHelpers.Info($"  • {primitives.Contexts.Count} contexts");
        return 0;
    }

    private static void HandleSingleFileResult(
        AgentsCompiler compiler,
        CompilationConfig config,
        CompilationResult result,
        CompileSettings settings)
    {
        // Perform intermediate compilation for constitution injection
        var intermediateConfig = new CompilationConfig
        {
            OutputPath = config.OutputPath,
            Chatmode = config.Chatmode,
            ResolveLinks = config.ResolveLinks,
            DryRun = true,
            WithConstitution = config.WithConstitution,
            Strategy = "single-file",
        };
        var intermediateResult = compiler.Compile(intermediateConfig);

        if (!intermediateResult.Success)
            return;

        var injector = new ConstitutionInjector(".");
        var outputPath = Path.GetFullPath(config.OutputPath);
        var (finalContent, cStatus, cHash) = injector.Inject(
            intermediateResult.Content,
            withConstitution: config.WithConstitution,
            outputPath: outputPath);

        // Compute deterministic Build ID
        var lines = finalContent.Split('\n').ToList();
        var idx = lines.IndexOf(CompilationConstants.BuildIdPlaceholder);
        var hashInputLines = lines.Where((_, i) => i != idx);
        var hashBytes = Encoding.UTF8.GetBytes(string.Join("\n", hashInputLines));
        var buildId = Convert.ToHexString(SHA256.HashData(hashBytes))[..12].ToLowerInvariant();
        if (idx >= 0)
        {
            lines[idx] = $"<!-- Build ID: {buildId} -->";
            finalContent = string.Join("\n", lines);
            if (!finalContent.EndsWith('\n'))
                finalContent += "\n";
        }

        if (!settings.DryRun)
        {
            if (cStatus is "CREATED" or "UPDATED" or "MISSING")
                File.WriteAllText(outputPath, finalContent);
            else
                ConsoleHelpers.Info("No changes detected; preserving existing AGENTS.md for idempotency");
        }

        if (settings.DryRun)
            ConsoleHelpers.Success("Context compilation completed successfully (dry run)", symbol: "check");
        else
            ConsoleHelpers.Success($"Context compiled successfully to {outputPath}", symbol: "sparkles");

        // Summary table
        var stats = intermediateResult.Stats;
        var table = new Table { Border = TableBorder.Rounded };
        table.Title = new TableTitle("Compilation Summary");
        table.AddColumn(new TableColumn("[bold white]Component[/]"));
        table.AddColumn(new TableColumn("[cyan]Count[/]"));
        table.AddColumn(new TableColumn("[white]Details[/]"));

        table.AddRow("Spec-kit Constitution", Markup.Escape(cStatus), Markup.Escape($"Hash: {cHash ?? "-"}"));
        table.AddRow("Instructions", stats.GetValueOrDefault("instructions", 0).ToString()!, "✅ All validated");
        table.AddRow("Contexts", stats.GetValueOrDefault("contexts", 0).ToString()!, "✅ All validated");
        table.AddRow("Chatmodes", stats.GetValueOrDefault("chatmodes", 0).ToString()!, "✅ All validated");

        string outputDetails;
        try
        {
            var fileSize = !settings.DryRun && File.Exists(outputPath) ? new FileInfo(outputPath).Length : 0;
            var sizeStr = fileSize > 0 ? $"{fileSize / 1024.0:F1}KB" : "Preview";
            outputDetails = $"{Path.GetFileName(outputPath)} ({sizeStr})";
        }
        catch
        {
            outputDetails = Path.GetFileName(outputPath);
        }
        table.AddRow("Output", "✨ SUCCESS", Markup.Escape(outputDetails));
        AnsiConsole.Write(table);

        if (settings.DryRun)
        {
            var preview = finalContent.Length > 500
                ? finalContent[..500] + "..."
                : finalContent;
            ConsoleHelpers.Panel(preview, title: "📋 Generated Content Preview", borderStyle: "cyan");
        }
        else
        {
            var nextSteps = new[]
            {
                $"Review the generated {config.OutputPath} file",
                "Install MCP dependencies: apm install",
                "Execute agentic workflows: apm run <script> --param key=value",
            };
            ConsoleHelpers.Panel(
                string.Join("\n", nextSteps.Select(s => $"• {s}")),
                title: "💡 Next Steps",
                borderStyle: "blue");
        }
    }

    private static int RunWatchMode(CompileSettings settings, CancellationToken cancellation)
    {
        ConsoleHelpers.Info("Watch mode: monitoring for changes...", symbol: "preview");

        var watchPaths = new List<string>();
        var watchers = new List<FileSystemWatcher>();

        void ScheduleWatch(string path)
        {
            if (!Directory.Exists(path)) return;
            var watcher = new FileSystemWatcher(path)
            {
                IncludeSubdirectories = true,
                NotifyFilter = NotifyFilters.LastWrite | NotifyFilters.FileName,
                EnableRaisingEvents = true,
            };
            watchers.Add(watcher);
            watchPaths.Add(path);
        }

        ScheduleWatch(".apm");
        ScheduleWatch(Path.Combine(".github", "instructions"));
        ScheduleWatch(Path.Combine(".github", "agents"));
        ScheduleWatch(Path.Combine(".github", "chatmodes"));

        // Watch apm.yml in current directory
        if (File.Exists("apm.yml"))
        {
            var rootWatcher = new FileSystemWatcher(".")
            {
                Filter = "apm.yml",
                IncludeSubdirectories = false,
                NotifyFilter = NotifyFilters.LastWrite,
                EnableRaisingEvents = true,
            };
            watchers.Add(rootWatcher);
            watchPaths.Add("apm.yml");
        }

        if (watchers.Count == 0)
        {
            ConsoleHelpers.Warning("No watch paths found. Create .apm/ directory first.");
            return 1;
        }

        ConsoleHelpers.Info($"Watching: {string.Join(", ", watchPaths)}");
        ConsoleHelpers.Info("Press Ctrl+C to stop watching");

        var lastCompile = DateTime.MinValue;
        var debounceDelay = TimeSpan.FromSeconds(1);

        void OnChanged(object sender, FileSystemEventArgs e)
        {
            if (!e.Name?.EndsWith(".md") == true && e.Name != "apm.yml") return;
            if (DateTime.Now - lastCompile < debounceDelay) return;
            lastCompile = DateTime.Now;

            ConsoleHelpers.Info($"File changed: {e.FullPath}", symbol: "preview");
            ConsoleHelpers.Info("Recompiling...", symbol: "gear");

            try
            {
                var overrides = new Dictionary<string, object?>
                {
                    ["chatmode"] = settings.Chatmode,
                    ["dry_run"] = settings.DryRun,
                };
                if (settings.NoLinks)
                    overrides["resolve_links"] = false;

                var config = CompilationConfig.FromApmYml(overrides);
                var compiler = new AgentsCompiler(".");
                var result = compiler.Compile(config);

                if (result.Success)
                {
                    if (settings.DryRun)
                        ConsoleHelpers.Success("Recompilation successful (dry run)", symbol: "sparkles");
                    else
                        ConsoleHelpers.Success($"Recompiled to {result.OutputPath}", symbol: "sparkles");
                }
                else
                {
                    ConsoleHelpers.Error("Recompilation failed");
                    foreach (var error in result.Errors)
                        AnsiConsole.MarkupLine($"  [red]❌ {Markup.Escape(error)}[/]");
                }
            }
            catch (Exception ex)
            {
                ConsoleHelpers.Error($"Error during recompilation: {ex.Message}");
            }
        }

        foreach (var watcher in watchers)
        {
            watcher.Changed += OnChanged;
            watcher.Created += OnChanged;
        }

        try
        {
            // Block until cancelled
            while (!cancellation.IsCancellationRequested)
                Thread.Sleep(500);
        }
        catch (OperationCanceledException) { }
        finally
        {
            foreach (var watcher in watchers)
                watcher.Dispose();
            ConsoleHelpers.Info("Stopped watching for changes", symbol: "bulb");
        }

        return 0;
    }

    private static IEnumerable<string> GlobFiles(string directory, string pattern)
    {
        if (!Directory.Exists(directory)) return [];
        return Directory.EnumerateFiles(directory, pattern, SearchOption.AllDirectories);
    }
}

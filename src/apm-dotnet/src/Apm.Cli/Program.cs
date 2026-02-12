using System.Reflection;
using Spectre.Console;
using Spectre.Console.Cli;
using Apm.Cli.Commands;
using Apm.Cli.Commands.Config;
using Apm.Cli.Commands.Deps;

var app = new CommandApp();

app.Configure(config =>
{
    config.SetApplicationName("apm");
    config.SetApplicationVersion(
        Assembly.GetExecutingAssembly()
            .GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion
        ?? "0.0.0");

    config.AddCommand<InitCommand>("init")
        .WithDescription("🚀 Initialize a new APM project");

    config.AddCommand<InstallCommand>("install")
        .WithDescription("📦 Install APM packages");

    config.AddCommand<CompileCommand>("compile")
        .WithDescription("🚀 Compile APM context into distributed AGENTS.md files");

    config.AddCommand<RunCommand>("run")
        .WithDescription("▶️  Run a script with parameters");

    config.AddBranch("deps", deps =>
    {
        deps.SetDescription("📋 Manage APM package dependencies");

        deps.AddCommand<DepsListCommand>("list")
            .WithDescription("📋 List installed APM dependencies");

        deps.AddCommand<DepsTreeCommand>("tree")
            .WithDescription("🌳 Show dependency tree");

        deps.AddCommand<DepsVerifyCommand>("verify")
            .WithDescription("✅ Verify installed dependencies");

        deps.AddCommand<DepsUninstallCommand>("uninstall")
            .WithDescription("🗑️  Uninstall APM packages");
    });

    config.AddBranch("config", cfg =>
    {
        cfg.SetDescription("⚙️  Configure APM CLI");

        cfg.AddCommand<ConfigGetCommand>("get")
            .WithDescription("📖 Get configuration value");

        cfg.AddCommand<ConfigSetCommand>("set")
            .WithDescription("✏️  Set configuration value");

        cfg.AddCommand<ConfigShowCommand>("show")
            .WithDescription("📋 Show current configuration");
    });

    config.AddCommand<PreviewCommand>("preview")
        .WithDescription("👀 Preview a script's compiled prompt files");

    config.AddCommand<ListCommand>("list")
        .WithDescription("📋 List available scripts in the current project");
});

return app.Run(args);

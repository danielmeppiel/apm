using Spectre.Console;
using Spectre.Console.Cli;
using Apm.Cli.Models;
using Apm.Cli.Utils;

namespace Apm.Cli.Commands.Deps;

public sealed class DepsListSettings : CommandSettings
{
}

public sealed class DepsListCommand : Command<DepsListSettings>
{
    public override int Execute(CommandContext context, DepsListSettings settings, CancellationToken cancellation)
    {
        try
        {
            var projectRoot = Directory.GetCurrentDirectory();
            var apmModulesPath = Path.Combine(projectRoot, "apm_modules");

            if (!Directory.Exists(apmModulesPath))
            {
                ConsoleHelpers.Info("No APM dependencies installed yet", symbol: "bulb");
                AnsiConsole.MarkupLine("[dim]Run 'apm install' to install dependencies from apm.yml[/]");
                return 0;
            }

            // Load declared deps for orphan detection
            var declaredDeps = new HashSet<string>();
            try
            {
                var apmYmlPath = Path.Combine(projectRoot, "apm.yml");
                if (File.Exists(apmYmlPath))
                {
                    var projectPackage = ApmPackage.FromApmYml(apmYmlPath);
                    foreach (var dep in projectPackage.GetApmDependencies())
                    {
                        var repoParts = dep.RepoUrl.Split('/');
                        if (dep.IsVirtual)
                        {
                            var packageName = dep.GetVirtualPackageName();
                            if (dep.IsAzureDevOps() && repoParts.Length >= 3)
                                declaredDeps.Add($"{repoParts[0]}/{repoParts[1]}/{packageName}");
                            else if (repoParts.Length >= 2)
                                declaredDeps.Add($"{repoParts[0]}/{packageName}");
                        }
                        else
                        {
                            if (dep.IsAzureDevOps() && repoParts.Length >= 3)
                                declaredDeps.Add($"{repoParts[0]}/{repoParts[1]}/{repoParts[2]}");
                            else if (repoParts.Length >= 2)
                                declaredDeps.Add($"{repoParts[0]}/{repoParts[1]}");
                        }
                    }
                }
            }
            catch { /* Continue without orphan detection */ }

            var installedPackages = new List<InstalledPackageInfo>();
            var orphanedPackages = new List<string>();

            // Scan org-namespaced structure: apm_modules/owner/repo or apm_modules/org/project/repo
            ScanApmModules(apmModulesPath, declaredDeps, installedPackages, orphanedPackages);

            if (installedPackages.Count == 0)
            {
                ConsoleHelpers.Info("apm_modules/ directory exists but contains no valid packages", symbol: "bulb");
                return 0;
            }

            // Display packages in table format
            var table = new Table()
                .Title("📋 APM Dependencies")
                .Border(TableBorder.Rounded);
            table.AddColumn(new TableColumn("[bold cyan]Package[/]").NoWrap());
            table.AddColumn(new TableColumn("[bold cyan]Version[/]"));
            table.AddColumn(new TableColumn("[bold cyan]Source[/]"));
            table.AddColumn(new TableColumn("[bold cyan]Context[/]"));
            table.AddColumn(new TableColumn("[bold cyan]Workflows[/]"));

            foreach (var pkg in installedPackages)
            {
                table.AddRow(
                    Markup.Escape(pkg.Name),
                    $"[yellow]{Markup.Escape(pkg.Version)}[/]",
                    $"[blue]{Markup.Escape(pkg.Source)}[/]",
                    $"[green]{pkg.ContextCount} files[/]",
                    $"[magenta]{pkg.WorkflowCount} workflows[/]");
            }

            AnsiConsole.Write(table);

            if (orphanedPackages.Count > 0)
            {
                AnsiConsole.WriteLine();
                ConsoleHelpers.Warning($"{orphanedPackages.Count} orphaned package(s) found (not in apm.yml)");
                foreach (var pkg in orphanedPackages)
                    AnsiConsole.MarkupLine($"[dim yellow]  • {Markup.Escape(pkg)}[/]");
                AnsiConsole.WriteLine();
                ConsoleHelpers.Info("Run 'apm prune' to remove orphaned packages", symbol: "bulb");
            }

            return 0;
        }
        catch (Exception e)
        {
            ConsoleHelpers.Error($"Error listing dependencies: {e.Message}");
            return 1;
        }
    }

    private static void ScanApmModules(
        string apmModulesPath,
        HashSet<string> declaredDeps,
        List<InstalledPackageInfo> installedPackages,
        List<string> orphanedPackages)
    {
        foreach (var level1Dir in Directory.GetDirectories(apmModulesPath))
        {
            var level1Name = Path.GetFileName(level1Dir);
            if (level1Name.StartsWith('.')) continue;

            foreach (var level2Dir in Directory.GetDirectories(level1Dir))
            {
                var level2Name = Path.GetFileName(level2Dir);
                if (level2Name.StartsWith('.')) continue;

                // Check GitHub 2-level structure
                var apmYmlPath = Path.Combine(level2Dir, "apm.yml");
                if (File.Exists(apmYmlPath))
                {
                    TryAddPackage($"{level1Name}/{level2Name}", apmYmlPath, level2Dir,
                        "github", declaredDeps, installedPackages, orphanedPackages);
                }
                else
                {
                    // Check ADO 3-level structure
                    foreach (var level3Dir in Directory.GetDirectories(level2Dir))
                    {
                        var level3Name = Path.GetFileName(level3Dir);
                        if (level3Name.StartsWith('.')) continue;

                        var adoApmYml = Path.Combine(level3Dir, "apm.yml");
                        if (File.Exists(adoApmYml))
                        {
                            TryAddPackage($"{level1Name}/{level2Name}/{level3Name}",
                                adoApmYml, level3Dir, "azure-devops",
                                declaredDeps, installedPackages, orphanedPackages);
                        }
                    }
                }
            }
        }
    }

    private static void TryAddPackage(
        string orgRepoName,
        string apmYmlPath,
        string packageDir,
        string defaultSource,
        HashSet<string> declaredDeps,
        List<InstalledPackageInfo> installedPackages,
        List<string> orphanedPackages)
    {
        try
        {
            var package = ApmPackage.FromApmYml(apmYmlPath);
            var (contextCount, workflowCount) = CountPackageFiles(packageDir);
            var isOrphaned = !declaredDeps.Contains(orgRepoName);

            if (isOrphaned)
                orphanedPackages.Add(orgRepoName);

            installedPackages.Add(new InstalledPackageInfo
            {
                Name = orgRepoName,
                Version = package.Version ?? "unknown",
                Source = isOrphaned ? "orphaned" : defaultSource,
                ContextCount = contextCount,
                WorkflowCount = workflowCount
            });
        }
        catch (Exception e)
        {
            AnsiConsole.MarkupLine($"[yellow]⚠️ Warning: Failed to read package {Markup.Escape(orgRepoName)}: {Markup.Escape(e.Message)}[/]");
        }
    }

    internal static (int ContextCount, int WorkflowCount) CountPackageFiles(string packagePath)
    {
        var apmDir = Path.Combine(packagePath, ".apm");
        if (!Directory.Exists(apmDir))
        {
            var rootWorkflows = Directory.GetFiles(packagePath, "*.prompt.md").Length;
            return (0, rootWorkflows);
        }

        var contextCount = 0;
        foreach (var dir in new[] { "instructions", "chatmodes", "contexts" })
        {
            var contextPath = Path.Combine(apmDir, dir);
            if (Directory.Exists(contextPath))
                contextCount += Directory.GetFiles(contextPath, "*.md").Length;
        }

        var workflowCount = 0;
        var promptsPath = Path.Combine(apmDir, "prompts");
        if (Directory.Exists(promptsPath))
            workflowCount += Directory.GetFiles(promptsPath, "*.prompt.md").Length;
        workflowCount += Directory.GetFiles(packagePath, "*.prompt.md").Length;

        return (contextCount, workflowCount);
    }

    private sealed class InstalledPackageInfo
    {
        public string Name { get; init; } = "";
        public string Version { get; init; } = "";
        public string Source { get; init; } = "";
        public int ContextCount { get; init; }
        public int WorkflowCount { get; init; }
    }
}

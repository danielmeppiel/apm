using Spectre.Console;
using Spectre.Console.Cli;
using Apm.Cli.Models;
using Apm.Cli.Utils;

namespace Apm.Cli.Commands.Deps;

public sealed class DepsTreeSettings : CommandSettings
{
}

public sealed class DepsTreeCommand : Command<DepsTreeSettings>
{
    public override int Execute(CommandContext context, DepsTreeSettings settings, CancellationToken cancellation)
    {
        try
        {
            var projectRoot = Directory.GetCurrentDirectory();
            var apmModulesPath = Path.Combine(projectRoot, "apm_modules");

            // Load project info
            var projectName = "my-project";
            try
            {
                var apmYmlPath = Path.Combine(projectRoot, "apm.yml");
                if (File.Exists(apmYmlPath))
                {
                    var rootPackage = ApmPackage.FromApmYml(apmYmlPath);
                    projectName = rootPackage.Name;
                }
            }
            catch { /* use default */ }

            var rootTree = new Tree($"[bold cyan]{Markup.Escape(projectName)}[/] (local)");

            if (!Directory.Exists(apmModulesPath))
            {
                rootTree.AddNode("[dim]No dependencies installed[/]");
                AnsiConsole.Write(rootTree);
                return 0;
            }

            // Add each dependency as a branch — handle org/repo structure
            foreach (var orgDir in Directory.GetDirectories(apmModulesPath))
            {
                var orgName = Path.GetFileName(orgDir);
                if (orgName.StartsWith('.')) continue;

                foreach (var packageDir in Directory.GetDirectories(orgDir))
                {
                    var packageName = Path.GetFileName(packageDir);
                    if (packageName.StartsWith('.')) continue;

                    try
                    {
                        var displayInfo = GetPackageDisplayInfo(packageDir);
                        var branch = rootTree.AddNode($"[green]{Markup.Escape(displayInfo.DisplayName)}[/]");

                        var contextFiles = GetDetailedContextCounts(packageDir);
                        var workflowCount = CountWorkflows(packageDir);

                        foreach (var (contextType, count) in contextFiles)
                        {
                            if (count > 0)
                                branch.AddNode($"[dim]{count} {Markup.Escape(contextType)}[/]");
                        }

                        if (workflowCount > 0)
                            branch.AddNode($"[bold magenta]{workflowCount} agent workflows[/]");

                        if (!contextFiles.Values.Any(c => c > 0) && workflowCount == 0)
                            branch.AddNode("[dim]no context or workflows[/]");
                    }
                    catch
                    {
                        rootTree.AddNode($"[red]{Markup.Escape(orgName)}/{Markup.Escape(packageName)}[/] [dim](error loading)[/]");
                    }
                }
            }

            AnsiConsole.Write(rootTree);
            return 0;
        }
        catch (Exception e)
        {
            ConsoleHelpers.Error($"Error showing dependency tree: {e.Message}");
            return 1;
        }
    }

    private static PackageDisplayInfo GetPackageDisplayInfo(string packagePath)
    {
        try
        {
            var apmYmlPath = Path.Combine(packagePath, "apm.yml");
            if (File.Exists(apmYmlPath))
            {
                var package = ApmPackage.FromApmYml(apmYmlPath);
                var versionInfo = !string.IsNullOrEmpty(package.Version) ? $"@{package.Version}" : "@unknown";
                return new PackageDisplayInfo(
                    $"{package.Name}{versionInfo}",
                    package.Name,
                    package.Version ?? "unknown");
            }
        }
        catch { /* fall through */ }

        var dirName = Path.GetFileName(packagePath);
        return new PackageDisplayInfo($"{dirName}@unknown", dirName, "unknown");
    }

    private static Dictionary<string, int> GetDetailedContextCounts(string packagePath)
    {
        var apmDir = Path.Combine(packagePath, ".apm");
        if (!Directory.Exists(apmDir))
            return new Dictionary<string, int>
            {
                ["instructions"] = 0, ["chatmodes"] = 0, ["contexts"] = 0
            };

        var contextDirs = new Dictionary<string, string>
        {
            ["instructions"] = "instructions",
            ["chatmodes"] = "chatmodes",
            ["contexts"] = "context"
        };

        var counts = new Dictionary<string, int>();
        foreach (var (contextType, dirName) in contextDirs)
        {
            var contextPath = Path.Combine(apmDir, dirName);
            counts[contextType] = Directory.Exists(contextPath)
                ? Directory.GetFiles(contextPath, "*.md").Length
                : 0;
        }

        return counts;
    }

    private static int CountWorkflows(string packagePath)
    {
        var (_, workflowCount) = DepsListCommand.CountPackageFiles(packagePath);
        return workflowCount;
    }

    private sealed record PackageDisplayInfo(string DisplayName, string Name, string Version);
}

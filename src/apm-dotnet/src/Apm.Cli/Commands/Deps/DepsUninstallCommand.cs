using System.ComponentModel;
using Spectre.Console;
using Spectre.Console.Cli;
using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;
using Apm.Cli.Models;
using Apm.Cli.Utils;

namespace Apm.Cli.Commands.Deps;

public sealed class DepsUninstallSettings : CommandSettings
{
    [CommandArgument(0, "<packages>")]
    [Description("Packages to uninstall")]
    public required string[] Packages { get; set; }

    [CommandOption("--dry-run")]
    [Description("Show what would be removed without removing")]
    public bool DryRun { get; set; }
}

public sealed class DepsUninstallCommand : Command<DepsUninstallSettings>
{
    public override int Execute(CommandContext context, DepsUninstallSettings settings, CancellationToken cancellation)
    {
        try
        {
            var apmYmlPath = Path.Combine(Directory.GetCurrentDirectory(), "apm.yml");
            if (!File.Exists(apmYmlPath))
            {
                ConsoleHelpers.Error("No apm.yml found. Run 'apm init' first.");
                return 1;
            }

            if (settings.Packages.Length == 0)
            {
                ConsoleHelpers.Error("No packages specified. Specify packages to uninstall.");
                return 1;
            }

            ConsoleHelpers.Info($"Uninstalling {settings.Packages.Length} package(s)...", symbol: "bulb");

            // Read current apm.yml
            var deserializer = new DeserializerBuilder()
                .WithNamingConvention(UnderscoredNamingConvention.Instance)
                .Build();

            Dictionary<string, object?> data;
            try
            {
                var yamlContent = File.ReadAllText(apmYmlPath);
                data = deserializer.Deserialize<Dictionary<string, object?>>(yamlContent) ?? new();
            }
            catch (Exception e)
            {
                ConsoleHelpers.Error($"Failed to read apm.yml: {e.Message}");
                return 1;
            }

            // Ensure dependencies structure exists
            if (!data.ContainsKey("dependencies"))
                data["dependencies"] = new Dictionary<object, object>();
            var depsObj = data["dependencies"];
            List<object> currentDeps;

            if (depsObj is Dictionary<object, object> depsDict)
            {
                if (depsDict.TryGetValue("apm", out var apmVal) && apmVal is List<object> list)
                    currentDeps = list;
                else
                {
                    currentDeps = [];
                    depsDict["apm"] = currentDeps;
                }
            }
            else
            {
                var newDict = new Dictionary<object, object>();
                currentDeps = [];
                newDict["apm"] = currentDeps;
                data["dependencies"] = newDict;
            }

            var currentDepStrings = currentDeps.Select(d => d?.ToString() ?? "").ToList();
            var packagesToRemove = new List<string>();
            var packagesNotFound = new List<string>();

            foreach (var package in settings.Packages)
            {
                if (!package.Contains('/'))
                {
                    ConsoleHelpers.Error($"Invalid package format: {package}. Use 'owner/repo' format.");
                    continue;
                }

                if (currentDepStrings.Contains(package))
                {
                    packagesToRemove.Add(package);
                    ConsoleHelpers.Info($"✓ {package} - found in apm.yml");
                }
                else
                {
                    packagesNotFound.Add(package);
                    ConsoleHelpers.Warning($"✗ {package} - not found in apm.yml");
                }
            }

            if (packagesToRemove.Count == 0)
            {
                ConsoleHelpers.Warning("No packages found in apm.yml to remove");
                return 0;
            }

            if (settings.DryRun)
            {
                ConsoleHelpers.Info($"Dry run: Would remove {packagesToRemove.Count} package(s):");
                foreach (var pkg in packagesToRemove)
                {
                    ConsoleHelpers.Info($"  - {pkg} from apm.yml");
                    var apmModulesDir = Path.Combine(Directory.GetCurrentDirectory(), "apm_modules");
                    try
                    {
                        var depRef = DependencyReference.Parse(pkg);
                        var pkgPath = depRef.GetInstallPath(apmModulesDir);
                        if (Directory.Exists(pkgPath))
                            ConsoleHelpers.Info($"  - {pkg} from apm_modules/");
                    }
                    catch
                    {
                        var parts = pkg.Split('/');
                        var pkgPath = Path.Combine([apmModulesDir, .. parts]);
                        if (Directory.Exists(pkgPath))
                            ConsoleHelpers.Info($"  - {pkg} from apm_modules/");
                    }
                }
                ConsoleHelpers.Success("Dry run complete - no changes made", symbol: "sparkles");
                return 0;
            }

            // Remove packages from apm.yml
            foreach (var package in packagesToRemove)
            {
                currentDeps.RemoveAll(d => d?.ToString() == package);
                ConsoleHelpers.Info($"Removed {package} from apm.yml");
            }

            // Write back to apm.yml
            try
            {
                var serializer = new SerializerBuilder()
                    .WithNamingConvention(UnderscoredNamingConvention.Instance)
                    .ConfigureDefaultValuesHandling(DefaultValuesHandling.OmitNull)
                    .Build();
                File.WriteAllText(apmYmlPath, serializer.Serialize(data));
                ConsoleHelpers.Success($"Updated apm.yml (removed {packagesToRemove.Count} package(s))", symbol: "sparkles");
            }
            catch (Exception e)
            {
                ConsoleHelpers.Error($"Failed to write apm.yml: {e.Message}");
                return 1;
            }

            // Remove packages from apm_modules/
            var apmModules = Path.Combine(Directory.GetCurrentDirectory(), "apm_modules");
            var removedFromModules = 0;

            if (Directory.Exists(apmModules))
            {
                foreach (var package in packagesToRemove)
                {
                    string packagePath;
                    try
                    {
                        var depRef = DependencyReference.Parse(package);
                        packagePath = depRef.GetInstallPath(apmModules);
                    }
                    catch
                    {
                        var parts = package.Split('/');
                        packagePath = Path.Combine([apmModules, .. parts]);
                    }

                    if (Directory.Exists(packagePath))
                    {
                        try
                        {
                            Directory.Delete(packagePath, recursive: true);
                            ConsoleHelpers.Info($"✓ Removed {package} from apm_modules/");
                            removedFromModules++;

                            // Cleanup empty parent directories up to apm_modules/
                            var parent = Directory.GetParent(packagePath);
                            while (parent != null && parent.FullName != apmModules && parent.Exists)
                            {
                                try
                                {
                                    if (!parent.EnumerateFileSystemInfos().Any())
                                    {
                                        parent.Delete();
                                        parent = parent.Parent;
                                    }
                                    else break;
                                }
                                catch { break; }
                            }
                        }
                        catch (Exception e)
                        {
                            ConsoleHelpers.Error($"✗ Failed to remove {package} from apm_modules/: {e.Message}");
                        }
                    }
                    else
                    {
                        ConsoleHelpers.Warning($"Package {package} not found in apm_modules/");
                    }
                }
            }

            // Final summary
            var summaryLines = new List<string> { $"Removed {packagesToRemove.Count} package(s) from apm.yml" };
            if (removedFromModules > 0)
                summaryLines.Add($"Removed {removedFromModules} package(s) from apm_modules/");

            ConsoleHelpers.Success("Uninstall complete: " + string.Join(", ", summaryLines), symbol: "sparkles");

            if (packagesNotFound.Count > 0)
                ConsoleHelpers.Warning($"Note: {packagesNotFound.Count} package(s) were not found in apm.yml");

            return 0;
        }
        catch (Exception e)
        {
            ConsoleHelpers.Error($"Error uninstalling packages: {e.Message}");
            return 1;
        }
    }
}

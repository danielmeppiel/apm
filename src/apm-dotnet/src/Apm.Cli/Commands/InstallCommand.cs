using System.ComponentModel;
using Spectre.Console;
using Spectre.Console.Cli;
using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;
using Apm.Cli.Core;
using Apm.Cli.Dependencies;
using Apm.Cli.Integration;
using Apm.Cli.Models;
using Apm.Cli.Utils;

namespace Apm.Cli.Commands;

public sealed class InstallSettings : CommandSettings
{
    [CommandArgument(0, "[packages]")]
    [Description("Packages to install")]
    public string[]? Packages { get; set; }

    [CommandOption("--runtime")]
    [Description("Target specific runtime only (copilot, codex, vscode)")]
    public string? Runtime { get; set; }

    [CommandOption("--exclude")]
    [Description("Exclude specific runtime from installation")]
    public string? Exclude { get; set; }

    [CommandOption("--only")]
    [Description("Install only specific dependency types")]
    public string? Only { get; set; }

    [CommandOption("-u|--update")]
    [Description("Update existing packages")]
    public bool Update { get; set; }

    [CommandOption("--dry-run")]
    [Description("Show what would be installed without installing")]
    public bool DryRun { get; set; }

    [CommandOption("--verbose")]
    [Description("Show detailed installation information")]
    public bool Verbose { get; set; }
}

public sealed class InstallCommand : Command<InstallSettings>
{
    public override int Execute(CommandContext context, InstallSettings settings, CancellationToken cancellation)
    {
        try
        {
            var packages = settings.Packages ?? [];
            var apmYmlExists = File.Exists("apm.yml");

            // Auto-bootstrap: create minimal apm.yml when packages specified but no apm.yml
            if (!apmYmlExists && packages.Length > 0)
            {
                var projectName = Path.GetFileName(Directory.GetCurrentDirectory());
                CreateMinimalApmYml(projectName);
                ConsoleHelpers.Success("Created apm.yml", symbol: "sparkles");
                apmYmlExists = true;
            }

            // Error when NO apm.yml AND NO packages
            if (!apmYmlExists)
            {
                ConsoleHelpers.Error("No apm.yml found");
                ConsoleHelpers.Info("💡 Run 'apm init' to create one, or:");
                ConsoleHelpers.Info("   apm install <org/repo> to auto-create + install");
                return 1;
            }

            // If packages are specified, validate and add them to apm.yml
            if (packages.Length > 0)
                ValidateAndAddPackages(packages, settings.DryRun);

            ConsoleHelpers.Info("Installing dependencies from apm.yml...");

            ApmPackage apmPackage;
            try
            {
                apmPackage = ApmPackage.FromApmYml(Path.GetFullPath("apm.yml"));
            }
            catch (Exception e)
            {
                ConsoleHelpers.Error($"Failed to parse apm.yml: {e.Message}");
                return 1;
            }

            var apmDeps = apmPackage.GetApmDependencies();
            var mcpDeps = apmPackage.GetMcpDependencies();

            var shouldInstallApm = settings.Only != "mcp";
            var shouldInstallMcp = settings.Only != "apm";

            // Dry run mode
            if (settings.DryRun)
            {
                ConsoleHelpers.Info("Dry run mode - showing what would be installed:");

                if (shouldInstallApm && apmDeps.Count > 0)
                {
                    ConsoleHelpers.Info($"APM dependencies ({apmDeps.Count}):");
                    foreach (var dep in apmDeps)
                    {
                        var action = settings.Update ? "update" : "install";
                        ConsoleHelpers.Info($"  - {dep.RepoUrl}#{dep.Reference ?? "main"} → {action}");
                    }
                }

                if (shouldInstallMcp && mcpDeps.Count > 0)
                {
                    ConsoleHelpers.Info($"MCP dependencies ({mcpDeps.Count}):");
                    foreach (var dep in mcpDeps)
                        ConsoleHelpers.Info($"  - {dep}");
                }

                if (apmDeps.Count == 0 && mcpDeps.Count == 0)
                    ConsoleHelpers.Warning("No dependencies found in apm.yml");

                ConsoleHelpers.Success("Dry run complete - no changes made");
                return 0;
            }

            // Install APM dependencies
            int apmCount = 0, promptCount = 0, agentCount = 0;
            if (shouldInstallApm && apmDeps.Count > 0)
            {
                (apmCount, promptCount, agentCount) = InstallApmDependencies(
                    apmPackage, settings.Update, settings.Verbose,
                    packages.Length > 0 ? packages : null);
            }
            else if (shouldInstallApm && apmDeps.Count == 0)
            {
                ConsoleHelpers.Info("No APM dependencies found in apm.yml");
            }

            // Install MCP dependencies
            int mcpCount = 0;
            if (shouldInstallMcp && mcpDeps.Count > 0)
            {
                mcpCount = InstallMcpDependencies(mcpDeps, settings.Runtime, settings.Exclude, settings.Verbose);
            }
            else if (shouldInstallMcp && mcpDeps.Count == 0)
            {
                ConsoleHelpers.Warning("No MCP dependencies found in apm.yml");
            }

            // Post-install summary
            AnsiConsole.WriteLine();
            if (string.IsNullOrEmpty(settings.Only))
                ShowInstallSummary(apmCount, promptCount, agentCount, mcpCount);
            else if (settings.Only == "apm")
                ConsoleHelpers.Success($"Installed {apmCount} APM dependencies");
            else if (settings.Only == "mcp")
                ConsoleHelpers.Success($"Configured {mcpCount} MCP servers");

            return 0;
        }
        catch (Exception e)
        {
            ConsoleHelpers.Error($"Error installing dependencies: {e.Message}");
            return 1;
        }
    }

    private static (int ApmCount, int PromptCount, int AgentCount) InstallApmDependencies(
        ApmPackage apmPackage, bool updateRefs, bool verbose, string[]? onlyPackages)
    {
        var apmDeps = apmPackage.GetApmDependencies();
        if (apmDeps.Count == 0) return (0, 0, 0);

        ConsoleHelpers.Info($"Installing APM dependencies ({apmDeps.Count})...");

        var projectRoot = Directory.GetCurrentDirectory();
        var apmModulesDir = Path.Combine(projectRoot, "apm_modules");
        Directory.CreateDirectory(apmModulesDir);

        // Load existing lockfile for reproducible installs
        var lockfilePath = LockFile.GetLockfilePath(projectRoot);
        LockFile? existingLockfile = null;
        if (File.Exists(lockfilePath) && !updateRefs)
        {
            existingLockfile = LockFile.Read(lockfilePath);
            if (existingLockfile?.Dependencies.Count > 0)
                ConsoleHelpers.Info($"Using apm.lock ({existingLockfile.Dependencies.Count} locked dependencies)");
        }

        var downloader = new GitHubPackageDownloader();

        // Download callback for transitive dependency resolution
        string? DownloadCallback(DependencyReference depRef, string modulesDir)
        {
            var installPath = depRef.GetInstallPath(modulesDir);
            if (Directory.Exists(installPath)) return installPath;
            try
            {
                var repoRef = depRef.RepoUrl;
                if (depRef.Host is not null and not "github.com")
                    repoRef = $"{depRef.Host}/{depRef.RepoUrl}";
                if (depRef.VirtualPath is not null)
                    repoRef = $"{repoRef}/{depRef.VirtualPath}";

                // Use locked commit if available
                string? lockedRef = null;
                if (existingLockfile is not null)
                {
                    var lockedDep = existingLockfile.GetDependency(depRef.GetUniqueKey());
                    if (lockedDep?.ResolvedCommit is not null and not "cached")
                        lockedRef = lockedDep.ResolvedCommit;
                }

                if (lockedRef is not null)
                    repoRef = $"{repoRef}#{lockedRef}";
                else if (depRef.Reference is not null)
                    repoRef = $"{repoRef}#{depRef.Reference}";

                downloader.DownloadPackage(repoRef, installPath);
                ConsoleHelpers.Info($"  └─ Resolved transitive: {depRef.GetDisplayName()}");
                return installPath;
            }
            catch (Exception e)
            {
                if (verbose)
                    ConsoleHelpers.Error($"  └─ Failed to resolve transitive dep {depRef.RepoUrl}: {e.Message}");
                return null;
            }
        }

        // Resolve dependencies
        var resolver = new ApmDependencyResolver(
            apmModulesDir: apmModulesDir,
            downloadCallback: DownloadCallback);

        var dependencyGraph = resolver.ResolveDependencies(projectRoot);

        // Check for circular dependencies
        if (dependencyGraph.HasCircularDependencies())
        {
            ConsoleHelpers.Error("Circular dependencies detected:");
            foreach (var circular in dependencyGraph.CircularDependencies)
            {
                var cyclePath = string.Join(" → ", circular.CyclePath);
                ConsoleHelpers.Error($"  {cyclePath}");
            }
            throw new InvalidOperationException("Cannot install packages with circular dependencies");
        }

        // Get flattened dependencies for installation
        var depsToInstall = dependencyGraph.FlattenedDependencies.GetInstallationList();

        // Filter to specific packages if requested
        if (onlyPackages is { Length: > 0 })
        {
            var onlySet = new HashSet<string>(onlyPackages.Select(NormalizePackageRef));
            depsToInstall = depsToInstall.Where(dep =>
            {
                var depStr = dep.ToString();
                if (onlySet.Contains(depStr)) return true;
                return onlySet.Any(pkg => depStr.EndsWith($"/{pkg}"));
            }).ToList();
        }

        if (depsToInstall.Count == 0)
        {
            ConsoleHelpers.Info("No APM dependencies to install", symbol: "check");
            return (0, 0, 0);
        }

        // Auto-create .github/ if neither .github/ nor .claude/ exists
        var githubDir = Path.Combine(projectRoot, ".github");
        var claudeDir = Path.Combine(projectRoot, ".claude");
        if (!Directory.Exists(githubDir) && !Directory.Exists(claudeDir))
        {
            Directory.CreateDirectory(githubDir);
            ConsoleHelpers.Info("Created .github/ as standard skills root");
        }

        // Detect target for integration
        var (detectedTarget, _) = TargetDetection.DetectTarget(
            projectRoot, configTarget: apmPackage.Target);
        var integrateVscode = TargetDetection.ShouldIntegrateVscode(detectedTarget);
        var integrateClaude = TargetDetection.ShouldIntegrateClaude(detectedTarget);

        // Initialize integrators
        var promptIntegrator = new PromptIntegrator();
        var agentIntegrator = new AgentIntegrator();
        var skillIntegrator = new SkillIntegrator();
        var commandIntegrator = new CommandIntegrator();

        int totalPromptsIntegrated = 0, totalAgentsIntegrated = 0;
        var installedPackages = new List<(DependencyReference, string?, int, string?)>();
        var installedCount = 0;

        // Install each dependency
        AnsiConsole.Status()
            .Spinner(Spinner.Known.Dots)
            .SpinnerStyle(Style.Parse("cyan"))
            .Start("Installing packages...", ctx =>
            {
                foreach (var depRef in depsToInstall)
                {
                    var installPath = depRef.GetInstallPath(apmModulesDir);
                    var displayName = depRef.IsVirtual ? depRef.ToString() : depRef.RepoUrl;

                    // Cache check: only tags/commits are cacheable
                    var (refType, _) = DependencyReference.ParseGitReference(depRef.Reference);
                    var isCacheable = refType is GitReferenceType.Tag or GitReferenceType.Commit;
                    var skipDownload = Directory.Exists(installPath) && isCacheable && !updateRefs;

                    if (skipDownload)
                    {
                        ConsoleHelpers.Info($"✓ {displayName} @{depRef.Reference} (cached)");
                    }
                    else
                    {
                        ctx.Status($"Fetching {displayName}...");

                        // Build download ref - use locked commit if available
                        var downloadRef = depRef.ToString();
                        if (existingLockfile is not null)
                        {
                            var lockedDep = existingLockfile.GetDependency(depRef.GetUniqueKey());
                            if (lockedDep?.ResolvedCommit is not null and not "cached")
                            {
                                var baseRef = depRef.RepoUrl;
                                if (depRef.VirtualPath is not null)
                                    baseRef = $"{baseRef}/{depRef.VirtualPath}";
                                downloadRef = $"{baseRef}#{lockedDep.ResolvedCommit}";
                            }
                        }

                        try
                        {
                            downloader.DownloadPackage(downloadRef, installPath);
                            installedCount++;
                            ConsoleHelpers.Success($"✓ {displayName}");
                        }
                        catch (Exception e)
                        {
                            ConsoleHelpers.Error($"✗ Failed to install {displayName}: {e.Message}");
                            continue;
                        }
                    }

                    // Collect for lockfile
                    var node = dependencyGraph.DependencyTree.GetNode(depRef.GetUniqueKey());
                    var depth = node?.Depth ?? 1;
                    var resolvedBy = node?.Parent?.DependencyRef.RepoUrl;
                    installedPackages.Add((depRef, depRef.Reference, depth, resolvedBy));

                    // Create PackageInfo for integration
                    PackageInfo packageInfo;
                    try
                    {
                        var apmYmlPath = Path.Combine(installPath, "apm.yml");
                        ApmPackage pkg;
                        if (File.Exists(apmYmlPath))
                        {
                            pkg = ApmPackage.FromApmYml(apmYmlPath);
                            if (string.IsNullOrEmpty(pkg.Source))
                                pkg.Source = depRef.RepoUrl;
                        }
                        else
                        {
                            pkg = new ApmPackage
                            {
                                Name = depRef.GetDisplayName(),
                                Version = "1.0.0",
                                Source = depRef.RepoUrl,
                                PackagePath = installPath
                            };
                        }

                        packageInfo = new PackageInfo(pkg, installPath)
                        {
                            DependencyRef = depRef,
                            InstalledAt = DateTime.UtcNow.ToString("o")
                        };
                    }
                    catch
                    {
                        continue;
                    }

                    // Run integrators
                    try
                    {
                        if (integrateVscode)
                        {
                            var promptResult = promptIntegrator.IntegratePackagePrompts(packageInfo, projectRoot);
                            if (promptResult.FilesIntegrated > 0)
                            {
                                totalPromptsIntegrated += promptResult.FilesIntegrated;
                                ConsoleHelpers.Info($"  └─ {promptResult.FilesIntegrated} prompts integrated → .github/prompts/");
                            }

                            var agentResult = agentIntegrator.IntegratePackageAgents(packageInfo, projectRoot);
                            if (agentResult.FilesIntegrated > 0)
                            {
                                totalAgentsIntegrated += agentResult.FilesIntegrated;
                                ConsoleHelpers.Info($"  └─ {agentResult.FilesIntegrated} agents integrated → .github/agents/");
                            }
                        }

                        if (integrateVscode || integrateClaude)
                        {
                            var skillResult = skillIntegrator.IntegratePackageSkill(packageInfo, projectRoot);
                            if (skillResult.SkillCreated)
                                ConsoleHelpers.Info("  └─ Skill integrated → .github/skills/");
                        }

                        if (integrateClaude)
                        {
                            var cmdResult = commandIntegrator.IntegratePackageCommands(packageInfo, projectRoot);
                            if (cmdResult.FilesIntegrated > 0)
                                ConsoleHelpers.Info($"  └─ {cmdResult.FilesIntegrated} commands integrated → .claude/commands/");
                        }
                    }
                    catch (Exception e)
                    {
                        ConsoleHelpers.Warning($"  ⚠ Failed to integrate primitives: {e.Message}");
                    }
                }
            });

        // Write lockfile
        if (installedPackages.Count > 0)
        {
            try
            {
                var lockFile = LockFile.FromInstalledPackages(
                    installedPackages, dependencyGraph);
                lockFile.Save(lockfilePath);
            }
            catch
            {
                // Non-fatal: lockfile write failure
            }
        }

        return (installedCount, totalPromptsIntegrated, totalAgentsIntegrated);
    }

    private static int InstallMcpDependencies(
        List<string> mcpDeps, string? runtime, string? exclude, bool verbose)
    {
        var mcpCount = 0;
        foreach (var dep in mcpDeps)
        {
            try
            {
                if (runtime is not null)
                {
                    var result = Operations.InstallPackage(runtime, dep);
                    if (result.Installed) mcpCount++;
                }
                else
                {
                    // Install for all detected runtimes
                    string[] runtimes = ["copilot", "codex"];
                    foreach (var rt in runtimes)
                    {
                        if (exclude is not null && rt.Equals(exclude, StringComparison.OrdinalIgnoreCase))
                            continue;
                        var result = Operations.InstallPackage(rt, dep);
                        if (result.Installed) mcpCount++;
                    }
                }
            }
            catch (Exception e)
            {
                ConsoleHelpers.Warning($"Failed to install MCP dependency {dep}: {e.Message}");
            }
        }
        return mcpCount;
    }

    private static void ValidateAndAddPackages(string[] packages, bool dryRun)
    {
        var apmYmlPath = Path.GetFullPath("apm.yml");
        var yamlContent = File.ReadAllText(apmYmlPath);
        var deserializer = new DeserializerBuilder()
            .WithNamingConvention(UnderscoredNamingConvention.Instance)
            .Build();
        var data = deserializer.Deserialize<Dictionary<string, object?>>(yamlContent)
                   ?? new Dictionary<string, object?>();

        // Ensure dependencies.apm exists
        if (!data.ContainsKey("dependencies"))
            data["dependencies"] = new Dictionary<object, object>();
        var deps = data["dependencies"] as Dictionary<object, object> ?? new();
        if (!deps.ContainsKey("apm"))
            deps["apm"] = new List<object>();
        var currentDeps = (deps["apm"] as List<object>)?.Select(d => d.ToString()!).ToList()
                          ?? [];

        var validated = new List<string>();
        ConsoleHelpers.Info($"Validating {packages.Length} package(s)...");

        foreach (var package in packages)
        {
            if (!package.Contains('/'))
            {
                ConsoleHelpers.Error($"Invalid package format: {package}. Use 'owner/repo' format.");
                continue;
            }

            if (currentDeps.Contains(package))
            {
                ConsoleHelpers.Info($"✓ {package} - already in apm.yml, ensuring installation...");
            }
            else
            {
                validated.Add(package);
                ConsoleHelpers.Info($"✓ {package} - will be added");
            }
        }

        if (validated.Count == 0 || dryRun) return;

        // Add validated packages to the list and rewrite apm.yml
        foreach (var pkg in validated)
        {
            currentDeps.Add(pkg);
            ConsoleHelpers.Info($"Added {pkg} to apm.yml");
        }

        deps["apm"] = currentDeps.Select(d => (object)d).ToList();
        data["dependencies"] = deps;

        var serializer = new SerializerBuilder()
            .WithNamingConvention(UnderscoredNamingConvention.Instance)
            .ConfigureDefaultValuesHandling(DefaultValuesHandling.Preserve)
            .Build();
        File.WriteAllText(apmYmlPath, serializer.Serialize(data));
        ConsoleHelpers.Success($"Updated apm.yml with {validated.Count} new package(s)");
    }

    private static void CreateMinimalApmYml(string projectName)
    {
        var data = new Dictionary<string, object>
        {
            ["name"] = projectName,
            ["version"] = "1.0.0",
            ["description"] = $"APM project for {projectName}",
            ["dependencies"] = new Dictionary<string, object>
            {
                ["apm"] = new List<string>(),
                ["mcp"] = new List<string>(),
            },
            ["scripts"] = new Dictionary<string, string>(),
        };

        var serializer = new SerializerBuilder()
            .WithNamingConvention(UnderscoredNamingConvention.Instance)
            .ConfigureDefaultValuesHandling(DefaultValuesHandling.Preserve)
            .Build();
        File.WriteAllText("apm.yml", serializer.Serialize(data));
    }

    private static void ShowInstallSummary(int apmCount, int promptCount, int agentCount, int mcpCount)
    {
        var lines = new List<string>();
        if (apmCount > 0) lines.Add($"📦 {apmCount} APM package(s) installed");
        if (promptCount > 0) lines.Add($"📝 {promptCount} prompt(s) integrated");
        if (agentCount > 0) lines.Add($"🤖 {agentCount} agent(s) integrated");
        if (mcpCount > 0) lines.Add($"🔌 {mcpCount} MCP server(s) configured");

        if (lines.Count > 0)
        {
            ConsoleHelpers.Panel(
                string.Join("\n", lines),
                title: "✨ Install Summary",
                borderStyle: "green");
        }
        else
        {
            ConsoleHelpers.Success("Nothing to install - all dependencies are up to date");
        }
    }

    private static string NormalizePackageRef(string pkg) =>
        pkg.Replace("/_git/", "/");
}

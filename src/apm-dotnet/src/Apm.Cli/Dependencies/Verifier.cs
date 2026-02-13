using Apm.Cli.Models;
using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;

namespace Apm.Cli.Dependencies;

/// <summary>Dependency verification for APM-CLI.</summary>
public static class Verifier
{
    private static readonly IDeserializer YamlDeserializer = new DeserializerBuilder()
        .WithNamingConvention(UnderscoredNamingConvention.Instance)
        .Build();

    /// <summary>Load the APM configuration file.</summary>
    /// <returns>Parsed config dictionary, or null if loading failed.</returns>
    public static Dictionary<string, object?>? LoadApmConfig(string configFile = "apm.yml")
    {
        try
        {
            if (!File.Exists(configFile))
            {
                Console.Error.WriteLine($"Configuration file {configFile} not found.");
                return null;
            }

            var content = File.ReadAllText(configFile);
            return YamlDeserializer.Deserialize<Dictionary<string, object?>>(content);
        }
        catch (Exception e)
        {
            Console.Error.WriteLine($"Error loading {configFile}: {e.Message}");
            return null;
        }
    }

    /// <summary>
    /// Verify that declared APM dependencies are installed in apm_modules/.
    /// Checks both apm.yml declarations and installed package directories.
    /// </summary>
    /// <returns>
    /// Tuple of (allInstalled, installedList, missingList).
    /// </returns>
    public static (bool AllInstalled, List<string> Installed, List<string> Missing) VerifyDependencies(
        string configFile = "apm.yml",
        string? projectRoot = null)
    {
        projectRoot ??= Directory.GetCurrentDirectory();
        var apmYmlPath = Path.Combine(projectRoot, configFile);

        if (!File.Exists(apmYmlPath))
            return (false, [], []);

        ApmPackage package;
        try
        {
            package = ApmPackage.FromApmYml(apmYmlPath);
        }
        catch (Exception e)
        {
            Console.Error.WriteLine($"Error reading {configFile}: {e.Message}");
            return (false, [], []);
        }

        var apmDeps = package.GetApmDependencies();
        if (apmDeps.Count == 0)
            return (true, [], []);

        var apmModulesDir = Path.Combine(projectRoot, "apm_modules");
        var installed = new List<string>();
        var missing = new List<string>();

        foreach (var dep in apmDeps)
        {
            var installPath = dep.GetInstallPath(apmModulesDir);
            var depKey = dep.GetCanonicalDependencyString();

            if (Directory.Exists(installPath))
            {
                // Check for apm.yml or SKILL.md inside
                var hasApmYml = File.Exists(Path.Combine(installPath, "apm.yml"));
                var hasSkillMd = File.Exists(Path.Combine(installPath, "SKILL.md"));
                if (hasApmYml || hasSkillMd)
                    installed.Add(depKey);
                else
                    missing.Add(depKey);
            }
            else
            {
                missing.Add(depKey);
            }
        }

        return (missing.Count == 0, installed, missing);
    }

    /// <summary>
    /// Verify installed packages match the lockfile entries.
    /// </summary>
    /// <returns>Tuple of (allMatch, matched, mismatched).</returns>
    public static (bool AllMatch, List<string> Matched, List<string> Mismatched) VerifyLockfile(
        string? projectRoot = null)
    {
        projectRoot ??= Directory.GetCurrentDirectory();
        var lockfilePath = LockFile.GetLockfilePath(projectRoot);
        var lockFile = LockFile.Read(lockfilePath);

        if (lockFile == null)
            return (false, [], ["No lockfile found"]);

        var matched = new List<string>();
        var mismatched = new List<string>();

        foreach (var dep in lockFile.GetAllDependencies())
        {
            var apmModulesDir = Path.Combine(projectRoot, "apm_modules");
            // Build install path from the locked dependency info
            var depRef = new DependencyReference(dep.RepoUrl)
            {
                Host = dep.Host,
                VirtualPath = dep.VirtualPath,
                IsVirtual = dep.IsVirtual
            };
            var installPath = depRef.GetInstallPath(apmModulesDir);

            if (Directory.Exists(installPath))
                matched.Add(dep.GetUniqueKey());
            else
                mismatched.Add(dep.GetUniqueKey());
        }

        return (mismatched.Count == 0, matched, mismatched);
    }
}

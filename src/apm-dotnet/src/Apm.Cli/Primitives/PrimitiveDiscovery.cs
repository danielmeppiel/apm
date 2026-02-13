using Apm.Cli.Models;

namespace Apm.Cli.Primitives;

/// <summary>
/// Discovery functionality for primitive files (.instructions.md, .chatmode.md, .agent.md, .context.md, .memory.md, SKILL.md).
/// Searches local .apm/ and .github/ directories plus apm_modules/ for installed packages.
/// </summary>
public static class PrimitiveDiscovery
{
    /// <summary>Local primitive glob patterns (recursive search).</summary>
    public static readonly Dictionary<string, string[]> LocalPrimitivePatterns = new()
    {
        ["chatmode"] =
        [
            "**/.apm/agents/*.agent.md",
            "**/.github/agents/*.agent.md",
            "**/*.agent.md",
            "**/.apm/chatmodes/*.chatmode.md",
            "**/.github/chatmodes/*.chatmode.md",
            "**/*.chatmode.md"
        ],
        ["instruction"] =
        [
            "**/.apm/instructions/*.instructions.md",
            "**/.github/instructions/*.instructions.md",
            "**/*.instructions.md"
        ],
        ["context"] =
        [
            "**/.apm/context/*.context.md",
            "**/.apm/memory/*.memory.md",
            "**/.github/context/*.context.md",
            "**/.github/memory/*.memory.md",
            "**/*.context.md",
            "**/*.memory.md"
        ]
    };

    /// <summary>Dependency primitive patterns (within a package's .apm directory).</summary>
    public static readonly Dictionary<string, string[]> DependencyPrimitivePatterns = new()
    {
        ["chatmode"] = ["agents/*.agent.md", "chatmodes/*.chatmode.md"],
        ["instruction"] = ["instructions/*.instructions.md"],
        ["context"] = ["context/*.context.md", "memory/*.memory.md"]
    };

    private static readonly HashSet<string> SkipDirectories =
    [
        ".git", "node_modules", "__pycache__", ".pytest_cache",
        ".venv", "venv", ".tox", "build", "dist", ".mypy_cache"
    ];

    /// <summary>Find all APM primitive files in the project (local only).</summary>
    public static PrimitiveCollection DiscoverPrimitives(string baseDir = ".")
    {
        var collection = new PrimitiveCollection();

        foreach (var (_, patterns) in LocalPrimitivePatterns)
        {
            var files = FindPrimitiveFiles(baseDir, patterns);
            foreach (var filePath in files)
            {
                try
                {
                    var primitive = PrimitiveParser.ParsePrimitiveFile(filePath, source: "local");
                    collection.AddPrimitive(primitive);
                }
                catch (Exception e)
                {
                    Console.Error.WriteLine($"Warning: Failed to parse {filePath}: {e.Message}");
                }
            }
        }

        DiscoverLocalSkill(baseDir, collection);
        return collection;
    }

    /// <summary>
    /// Enhanced primitive discovery including dependency sources.
    /// Priority: 1. Local .apm/ (highest) 2. Dependencies in declaration order (first wins).
    /// </summary>
    public static PrimitiveCollection DiscoverPrimitivesWithDependencies(string baseDir = ".")
    {
        var collection = new PrimitiveCollection();

        // Phase 1: Local primitives (highest priority)
        ScanLocalPrimitives(baseDir, collection);

        // Phase 1b: Local SKILL.md
        DiscoverLocalSkill(baseDir, collection);

        // Phase 2: Dependency primitives
        ScanDependencyPrimitives(baseDir, collection);

        return collection;
    }

    /// <summary>Scan local directories for primitives, excluding apm_modules/.</summary>
    public static void ScanLocalPrimitives(string baseDir, PrimitiveCollection collection)
    {
        var apmModulesPath = Path.GetFullPath(Path.Combine(baseDir, "apm_modules"));

        foreach (var (_, patterns) in LocalPrimitivePatterns)
        {
            var files = FindPrimitiveFiles(baseDir, patterns);
            var localFiles = files.Where(f => !IsUnderDirectory(f, apmModulesPath)).ToList();

            foreach (var filePath in localFiles)
            {
                try
                {
                    var primitive = PrimitiveParser.ParsePrimitiveFile(filePath, source: "local");
                    collection.AddPrimitive(primitive);
                }
                catch (Exception e)
                {
                    Console.Error.WriteLine($"Warning: Failed to parse local primitive {filePath}: {e.Message}");
                }
            }
        }
    }

    /// <summary>Scan all dependencies in apm_modules/ with priority handling.</summary>
    public static void ScanDependencyPrimitives(string baseDir, PrimitiveCollection collection)
    {
        var apmModulesPath = Path.Combine(baseDir, "apm_modules");
        if (!Directory.Exists(apmModulesPath))
            return;

        var dependencyOrder = GetDependencyDeclarationOrder(baseDir);

        foreach (var depName in dependencyOrder)
        {
            var parts = depName.Split('/');
            var depPath = parts.Length >= 3
                ? Path.Combine(apmModulesPath, parts[0], parts[1], parts[2])
                : parts.Length == 2
                    ? Path.Combine(apmModulesPath, parts[0], parts[1])
                    : Path.Combine(apmModulesPath, depName);

            if (Directory.Exists(depPath))
                ScanDirectoryWithSource(depPath, collection, source: $"dependency:{depName}");
        }
    }

    /// <summary>
    /// Get APM dependency installed paths in their declaration order from apm.yml.
    /// </summary>
    public static List<string> GetDependencyDeclarationOrder(string baseDir)
    {
        try
        {
            var apmYmlPath = Path.Combine(baseDir, "apm.yml");
            if (!File.Exists(apmYmlPath))
                return [];

            var package = ApmPackage.FromApmYml(apmYmlPath);
            var apmDependencies = package.GetApmDependencies();
            var dependencyNames = new List<string>();

            foreach (var dep in apmDependencies)
            {
                if (!string.IsNullOrEmpty(dep.Alias))
                {
                    dependencyNames.Add(dep.Alias);
                }
                else if (dep.IsVirtual)
                {
                    var repoParts = dep.RepoUrl.Split('/');
                    var virtualName = dep.GetVirtualPackageName();
                    if (dep.IsAzureDevOps() && repoParts.Length >= 3)
                        dependencyNames.Add($"{repoParts[0]}/{repoParts[1]}/{virtualName}");
                    else if (repoParts.Length >= 2)
                        dependencyNames.Add($"{repoParts[0]}/{virtualName}");
                    else
                        dependencyNames.Add(virtualName);
                }
                else
                {
                    dependencyNames.Add(dep.RepoUrl);
                }
            }

            return dependencyNames;
        }
        catch (Exception e)
        {
            Console.Error.WriteLine($"Warning: Failed to parse dependency order from apm.yml: {e.Message}");
            return [];
        }
    }

    /// <summary>Scan a directory for primitives with a specific source tag.</summary>
    public static void ScanDirectoryWithSource(string directory, PrimitiveCollection collection, string source)
    {
        var apmDir = Path.Combine(directory, ".apm");
        if (!Directory.Exists(apmDir))
        {
            DiscoverSkillInDirectory(directory, collection, source);
            return;
        }

        foreach (var (_, patterns) in DependencyPrimitivePatterns)
        {
            foreach (var pattern in patterns)
            {
                var fullPattern = Path.Combine(apmDir, pattern);
                var matchingFiles = GlobFiles(fullPattern);

                foreach (var filePath in matchingFiles)
                {
                    if (File.Exists(filePath) && IsReadable(filePath))
                    {
                        try
                        {
                            var primitive = PrimitiveParser.ParsePrimitiveFile(filePath, source: source);
                            collection.AddPrimitive(primitive);
                        }
                        catch (Exception e)
                        {
                            Console.Error.WriteLine($"Warning: Failed to parse dependency primitive {filePath}: {e.Message}");
                        }
                    }
                }
            }
        }

        DiscoverSkillInDirectory(directory, collection, source);
    }

    /// <summary>Find primitive files matching given glob patterns.</summary>
    public static List<string> FindPrimitiveFiles(string baseDir, string[] patterns)
    {
        if (!Directory.Exists(baseDir))
            return [];

        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var validFiles = new List<string>();

        foreach (var pattern in patterns)
        {
            var fullPattern = Path.Combine(baseDir, pattern);
            foreach (var filePath in GlobFiles(fullPattern))
            {
                var absPath = Path.GetFullPath(filePath);
                if (seen.Add(absPath) && File.Exists(absPath) && IsReadable(absPath))
                    validFiles.Add(absPath);
            }
        }

        return validFiles;
    }

    private static void DiscoverLocalSkill(string baseDir, PrimitiveCollection collection)
    {
        var skillPath = Path.Combine(baseDir, "SKILL.md");
        if (File.Exists(skillPath) && IsReadable(skillPath))
        {
            try
            {
                var skill = PrimitiveParser.ParseSkillFile(skillPath, source: "local");
                collection.AddPrimitive(skill);
            }
            catch (Exception e)
            {
                Console.Error.WriteLine($"Warning: Failed to parse SKILL.md: {e.Message}");
            }
        }
    }

    private static void DiscoverSkillInDirectory(string directory, PrimitiveCollection collection, string source)
    {
        var skillPath = Path.Combine(directory, "SKILL.md");
        if (File.Exists(skillPath) && IsReadable(skillPath))
        {
            try
            {
                var skill = PrimitiveParser.ParseSkillFile(skillPath, source: source);
                collection.AddPrimitive(skill);
            }
            catch (Exception e)
            {
                Console.Error.WriteLine($"Warning: Failed to parse SKILL.md in {directory}: {e.Message}");
            }
        }
    }

    private static bool IsUnderDirectory(string filePath, string directory)
    {
        var fullFile = Path.GetFullPath(filePath);
        var fullDir = Path.GetFullPath(directory);
        return fullFile.StartsWith(fullDir, StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsReadable(string filePath)
    {
        try
        {
            using var fs = new FileStream(filePath, FileMode.Open, FileAccess.Read, FileShare.Read);
            fs.ReadByte();
            return true;
        }
        catch (Exception)
        {
            return false;
        }
    }

    /// <summary>
    /// Simple glob expansion that supports ** and * patterns.
    /// </summary>
    private static IEnumerable<string> GlobFiles(string pattern)
    {
        var normalized = pattern.Replace('/', Path.DirectorySeparatorChar);
        var parts = normalized.Split(Path.DirectorySeparatorChar);

        // Find the base directory (everything before the first wildcard)
        var baseParts = new List<string>();
        var patternParts = new List<string>();
        var foundWildcard = false;

        foreach (var part in parts)
        {
            if (!foundWildcard && !part.Contains('*') && !part.Contains('?'))
                baseParts.Add(part);
            else
            {
                foundWildcard = true;
                patternParts.Add(part);
            }
        }

        var baseDir = baseParts.Count > 0 ? string.Join(Path.DirectorySeparatorChar.ToString(), baseParts) : ".";
        if (!Directory.Exists(baseDir))
            return [];

        var searchPattern = patternParts.Count > 0
            ? patternParts[^1]
            : "*";

        var hasRecursive = patternParts.Any(p => p == "**");
        var searchOption = hasRecursive ? SearchOption.AllDirectories : SearchOption.TopDirectoryOnly;

        try
        {
            return Directory.EnumerateFiles(baseDir, searchPattern, searchOption);
        }
        catch (Exception)
        {
            return [];
        }
    }
}

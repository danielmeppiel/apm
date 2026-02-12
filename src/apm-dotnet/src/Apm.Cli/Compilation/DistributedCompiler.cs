using Apm.Cli.Output;
using Apm.Cli.Primitives;
using Apm.Cli.Utils;

namespace Apm.Cli.Compilation;

/// <summary>
/// Distributed AGENTS.md compilation system following the Minimal Context Principle.
/// Generates multiple AGENTS.md files across a project's directory structure.
/// </summary>
public class DistributedCompiler : IDistributedCompiler
{
    private readonly string _baseDir;
    private readonly List<string> _warnings = [];
    private readonly List<string> _errors = [];
    private readonly ContextOptimizer _contextOptimizer;
    private readonly UnifiedLinkResolver _linkResolver;
    private readonly CompilationFormatter _outputFormatter;
    private Dictionary<string, List<Instruction>>? _placementMap;

    public DistributedCompiler(string baseDir = ".", List<string>? excludePatterns = null)
    {
        _baseDir = Path.GetFullPath(baseDir);
        _contextOptimizer = new ContextOptimizer(baseDir, excludePatterns);
        _linkResolver = new UnifiedLinkResolver(baseDir);
        _outputFormatter = new CompilationFormatter();
    }

    /// <summary>Compile primitives into distributed AGENTS.md files.</summary>
    public DistributedCompilationResult CompileDistributed(
        PrimitiveCollection primitives,
        Dictionary<string, object> config)
    {
        _warnings.Clear();
        _errors.Clear();

        try
        {
            var minInstructions = GetConfigInt(config, "min_instructions_per_file", 1);
            var sourceAttribution = GetConfigBool(config, "source_attribution", true);
            var debug = GetConfigBool(config, "debug", false);
            var cleanOrphaned = GetConfigBool(config, "clean_orphaned", false);
            var dryRun = GetConfigBool(config, "dry_run", false);

            // Phase 0: Context Link Resolution
            _linkResolver.RegisterContexts(primitives);

            // Phase 1: Directory structure analysis
            var directoryMap = AnalyzeDirectoryStructure(primitives.Instructions);

            // Phase 2: Determine optimal placement
            var placementMap = DetermineAgentsPlacementInternal(
                primitives.Instructions, directoryMap, minInstructions, debug);

            // Phase 3: Generate distributed AGENTS.md files
            var placements = GenerateDistributedAgentsFiles(
                placementMap, primitives, sourceAttribution);

            // Phase 4: Handle orphaned file cleanup
            var generatedPaths = placements.Select(p => p.AgentsPath).ToList();
            var orphanedFiles = FindOrphanedAgentsFiles(generatedPaths);

            if (orphanedFiles.Count > 0)
            {
                _warnings.AddRange(GenerateOrphanWarnings(orphanedFiles));
                if (!dryRun && cleanOrphaned)
                    _warnings.AddRange(CleanupOrphanedFiles(orphanedFiles));
            }

            // Phase 5: Validate coverage
            var coverageWarnings = ValidateCoverage(placements, primitives.Instructions);
            _warnings.AddRange(coverageWarnings);

            // Compile statistics
            var stats = CompileDistributedStats(placements, primitives);

            // Context reference stats
            try
            {
                var filesToScan = placements
                    .SelectMany(p => p.Instructions.Select(i => i.FilePath))
                    .ToList();
                var refs = _linkResolver.GetReferencedContexts(filesToScan);
                stats["contexts_referenced"] = refs.Count;
            }
            catch
            {
                stats["contexts_referenced"] = 0;
            }

            return new DistributedCompilationResult
            {
                Success = _errors.Count == 0,
                Placements = placements,
                ContentMap = placements.ToDictionary(
                    p => p.AgentsPath,
                    p => GenerateAgentsContent(p, primitives)),
                Warnings = [.. _warnings],
                Errors = [.. _errors],
                Stats = stats
            };
        }
        catch (Exception e)
        {
            _errors.Add($"Distributed compilation failed: {e.Message}");
            return new DistributedCompilationResult
            {
                Success = false,
                Warnings = [.. _warnings],
                Errors = [.. _errors]
            };
        }
    }

    /// <summary>Analyze directory structure for instruction placement.</summary>
    public List<DirectoryMapping> AnalyzeDirectoryStructure(List<Instruction> instructions)
    {
        var directories = new Dictionary<string, HashSet<string>>();
        var depthMap = new Dictionary<string, int>();
        var parentMap = new Dictionary<string, string?>();

        foreach (var instruction in instructions)
        {
            if (string.IsNullOrEmpty(instruction.ApplyTo))
                continue;

            var pattern = instruction.ApplyTo;
            var dirs = ExtractDirectoriesFromPattern(pattern);

            foreach (var dirPath in dirs)
            {
                var absDir = Path.GetFullPath(Path.Combine(_baseDir, dirPath));
                if (!directories.TryGetValue(absDir, out var patterns))
                {
                    patterns = [];
                    directories[absDir] = patterns;
                }
                patterns.Add(pattern);

                var relParts = Path.GetRelativePath(_baseDir, absDir).Split(
                    Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                var depth = relParts.Length;
                depthMap[absDir] = depth;

                if (depth > 0)
                {
                    var parent = Path.GetDirectoryName(absDir);
                    parentMap[absDir] = parent;
                    if (parent is not null && !directories.ContainsKey(parent))
                        directories[parent] = [];
                }
                else
                {
                    parentMap[absDir] = null;
                }
            }
        }

        // Add base directory
        if (!directories.ContainsKey(_baseDir))
            directories[_baseDir] = [];

        foreach (var inst in instructions.Where(i => !string.IsNullOrEmpty(i.ApplyTo)))
            directories[_baseDir].Add(inst.ApplyTo);

        depthMap[_baseDir] = 0;
        parentMap[_baseDir] = null;

        return directories.Select(kvp => new DirectoryMapping
        {
            Directory = kvp.Key,
            ApplicablePatterns = kvp.Value,
            Depth = depthMap.GetValueOrDefault(kvp.Key, 0),
            ParentDirectory = parentMap.GetValueOrDefault(kvp.Key)
        }).ToList();
    }

    /// <summary>Determine AGENTS.md placement for instructions.</summary>
    public List<PlacementResult> DetermineAgentsPlacement(
        List<Instruction> instructions,
        List<DirectoryMapping> directoryMap,
        int minInstructions = 1,
        bool debug = false)
    {
        var placement = DetermineAgentsPlacementInternal(
            instructions, directoryMap, minInstructions, debug);

        return placement.Select(kvp => new PlacementResult
        {
            AgentsPath = Path.Combine(kvp.Key, "AGENTS.md"),
            Instructions = kvp.Value,
            CoveragePatterns = new HashSet<string>(kvp.Value
                .Where(i => !string.IsNullOrEmpty(i.ApplyTo))
                .Select(i => i.ApplyTo))
        }).ToList();
    }

    /// <summary>Get compilation results formatted for display.</summary>
    public string? FormatCompilationOutput(bool isDryRun, bool verbose, bool debug)
    {
        if (_placementMap is null) return null;

        var compilationResults = _contextOptimizer.GetCompilationResults(_placementMap, isDryRun);

        // Merge warnings
        var allWarnings = new List<string>(compilationResults.Warnings);
        allWarnings.AddRange(_warnings);
        compilationResults.Warnings = allWarnings;

        var allErrors = new List<string>(compilationResults.Errors);
        allErrors.AddRange(_errors);
        compilationResults.Errors = allErrors;

        return verbose || debug
            ? _outputFormatter.FormatVerbose(compilationResults)
            : _outputFormatter.FormatDefault(compilationResults);
    }

    // ── Internal helpers ─────────────────────────────────────────────

    private Dictionary<string, List<Instruction>> DetermineAgentsPlacementInternal(
        List<Instruction> instructions,
        List<DirectoryMapping> directoryMap,
        int minInstructions,
        bool debug)
    {
        var optimizedPlacement = _contextOptimizer.OptimizeInstructionPlacement(
            instructions, verbose: debug, enableTiming: debug);

        // Constitution-only fallback
        if (optimizedPlacement.Count == 0)
        {
            var constitutionPath = Constitution.FindConstitution(_baseDir);
            if (File.Exists(constitutionPath))
                optimizedPlacement[_baseDir] = [];
        }

        _placementMap = optimizedPlacement;

        // Filter for minimum instructions
        if (minInstructions > 1)
        {
            var filtered = new Dictionary<string, List<Instruction>>();
            foreach (var (dir, dirInstructions) in optimizedPlacement)
            {
                if (dirInstructions.Count >= minInstructions ||
                    string.Equals(dir, _baseDir, StringComparison.OrdinalIgnoreCase))
                {
                    filtered[dir] = dirInstructions;
                }
                else
                {
                    var parent = Path.GetDirectoryName(dir) ?? _baseDir;
                    if (!filtered.TryGetValue(parent, out var parentList))
                    {
                        parentList = [];
                        filtered[parent] = parentList;
                    }
                    parentList.AddRange(dirInstructions);
                }
            }
            return filtered;
        }

        return optimizedPlacement;
    }

    private List<PlacementResult> GenerateDistributedAgentsFiles(
        Dictionary<string, List<Instruction>> placementMap,
        PrimitiveCollection primitives,
        bool sourceAttribution)
    {
        var placements = new List<PlacementResult>();

        if (placementMap.Count == 0)
        {
            var constitutionPath = Constitution.FindConstitution(_baseDir);
            if (File.Exists(constitutionPath))
            {
                placements.Add(new PlacementResult
                {
                    AgentsPath = Path.Combine(_baseDir, "AGENTS.md"),
                    Instructions = [],
                    CoveragePatterns = [],
                    SourceAttribution = sourceAttribution
                        ? new Dictionary<string, string> { ["constitution"] = "constitution.md" }
                        : []
                });
            }
        }
        else
        {
            foreach (var (dir, instructions) in placementMap)
            {
                var sourceMap = new Dictionary<string, string>();
                if (sourceAttribution)
                {
                    foreach (var inst in instructions)
                    {
                        sourceMap[inst.FilePath] = inst.Source ?? "local";
                    }
                }

                var patterns = new HashSet<string>(
                    instructions.Where(i => !string.IsNullOrEmpty(i.ApplyTo)).Select(i => i.ApplyTo));

                placements.Add(new PlacementResult
                {
                    AgentsPath = Path.Combine(dir, "AGENTS.md"),
                    Instructions = instructions,
                    CoveragePatterns = patterns,
                    SourceAttribution = sourceMap
                });
            }
        }

        return placements;
    }

    private string GenerateAgentsContent(PlacementResult placement, PrimitiveCollection primitives)
    {
        var sections = new List<string>
        {
            "# AGENTS.md",
            "<!-- Generated by APM CLI from distributed .apm/ primitives -->",
            CompilationConstants.BuildIdPlaceholder,
            $"<!-- APM Version: {VersionInfo.GetVersion()} -->"
        };

        // Source attribution summary
        if (placement.SourceAttribution.Count > 0)
        {
            var sources = placement.SourceAttribution.Values.Distinct().OrderBy(s => s).ToList();
            sections.Add(sources.Count > 1
                ? $"<!-- Sources: {string.Join(", ", sources)} -->"
                : $"<!-- Source: {(sources.Count > 0 ? sources[0] : "local")} -->");
        }

        sections.Add("");

        // Group instructions by pattern
        var patternGroups = new Dictionary<string, List<Instruction>>();
        foreach (var inst in placement.Instructions)
        {
            if (string.IsNullOrEmpty(inst.ApplyTo)) continue;
            if (!patternGroups.TryGetValue(inst.ApplyTo, out var list))
            {
                list = [];
                patternGroups[inst.ApplyTo] = list;
            }
            list.Add(inst);
        }

        foreach (var (pattern, patternInstructions) in patternGroups.OrderBy(kvp => kvp.Key))
        {
            sections.Add($"## Files matching `{pattern}`");
            sections.Add("");

            foreach (var inst in patternInstructions)
            {
                var content = inst.Content.Trim();
                if (string.IsNullOrEmpty(content)) continue;

                if (placement.SourceAttribution.Count > 0)
                {
                    var source = placement.SourceAttribution.GetValueOrDefault(inst.FilePath, "local");
                    string relPath;
                    try { relPath = Path.GetRelativePath(_baseDir, inst.FilePath); }
                    catch { relPath = inst.FilePath; }
                    sections.Add($"<!-- Source: {source} {relPath} -->");
                }

                sections.Add(content);
                sections.Add("");
            }
        }

        sections.Add("---");
        sections.Add("*This file was generated by APM CLI. Do not edit manually.*");
        sections.Add("*To regenerate: `specify apm compile`*");
        sections.Add("");

        var result = string.Join("\n", sections);

        // Resolve context links
        var agentsDir = Path.GetDirectoryName(placement.AgentsPath) ?? _baseDir;
        result = _linkResolver.ResolveLinksForCompilation(result, agentsDir, placement.AgentsPath);

        return result;
    }

    private List<string> FindOrphanedAgentsFiles(List<string> generatedPaths)
    {
        var generatedSet = new HashSet<string>(generatedPaths, StringComparer.OrdinalIgnoreCase);
        var orphaned = new List<string>();

        var skipDirs = new HashSet<string> { ".git", ".apm", "node_modules", "__pycache__", ".pytest_cache", "apm_modules" };

        foreach (var agentsFile in Directory.EnumerateFiles(_baseDir, "AGENTS.md", SearchOption.AllDirectories))
        {
            try
            {
                var relPath = Path.GetRelativePath(_baseDir, agentsFile);
                var parts = relPath.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                if (parts.Any(p => skipDirs.Contains(p)))
                    continue;

                if (!generatedSet.Contains(agentsFile))
                    orphaned.Add(agentsFile);
            }
            catch
            {
                // skip
            }
        }

        return orphaned;
    }

    private List<string> GenerateOrphanWarnings(List<string> orphanedFiles)
    {
        if (orphanedFiles.Count == 0) return [];

        if (orphanedFiles.Count == 1)
        {
            var relPath = Path.GetRelativePath(_baseDir, orphanedFiles[0]);
            return [$"Orphaned AGENTS.md found: {relPath} - run 'apm compile --clean' to remove"];
        }

        var fileList = orphanedFiles
            .Take(5)
            .Select(f => $"  • {Path.GetRelativePath(_baseDir, f)}")
            .ToList();

        if (orphanedFiles.Count > 5)
            fileList.Add($"  • ...and {orphanedFiles.Count - 5} more");

        var text = string.Join("\n", fileList);
        return [$"Found {orphanedFiles.Count} orphaned AGENTS.md files:\n{text}\n  Run 'apm compile --clean' to remove orphaned files"];
    }

    private static List<string> CleanupOrphanedFiles(List<string> orphanedFiles)
    {
        var messages = new List<string> { $"🧹 Cleaning up {orphanedFiles.Count} orphaned AGENTS.md files" };

        foreach (var filePath in orphanedFiles)
        {
            try
            {
                File.Delete(filePath);
                messages.Add($"  ✓ Removed {Path.GetFileName(filePath)}");
            }
            catch (Exception e)
            {
                messages.Add($"  ✗ Failed to remove {Path.GetFileName(filePath)}: {e.Message}");
            }
        }

        return messages;
    }

    private static List<string> ValidateCoverage(
        List<PlacementResult> placements,
        List<Instruction> allInstructions)
    {
        var placed = new HashSet<string>(
            placements.SelectMany(p => p.Instructions.Select(i => i.FilePath)));

        var all = new HashSet<string>(allInstructions.Select(i => i.FilePath));
        var missing = all.Except(placed).ToList();

        return missing.Count > 0
            ? [$"Instructions not placed in any AGENTS.md: {string.Join(", ", missing)}"]
            : [];
    }

    private Dictionary<string, object> CompileDistributedStats(
        List<PlacementResult> placements,
        PrimitiveCollection primitives)
    {
        var totalInstructions = placements.Sum(p => p.Instructions.Count);
        var totalPatterns = placements.Sum(p => p.CoveragePatterns.Count);

        var placementMap = placements.ToDictionary(
            p => Path.GetDirectoryName(p.AgentsPath) ?? _baseDir,
            p => p.Instructions);

        var optimizationStats = _contextOptimizer.GetOptimizationStats(placementMap);

        var stats = new Dictionary<string, object>
        {
            ["agents_files_generated"] = placements.Count,
            ["total_instructions_placed"] = totalInstructions,
            ["total_patterns_covered"] = totalPatterns,
            ["primitives_found"] = primitives.Count(),
            ["chatmodes"] = primitives.Chatmodes.Count,
            ["instructions"] = primitives.Instructions.Count,
            ["contexts"] = primitives.Contexts.Count,
            ["average_context_efficiency"] = optimizationStats.AverageContextEfficiency,
            ["total_agents_files"] = optimizationStats.TotalAgentsFiles,
            ["directories_analyzed"] = optimizationStats.DirectoriesAnalyzed
        };

        return stats;
    }

    private static List<string> ExtractDirectoriesFromPattern(string pattern)
    {
        if (pattern.StartsWith("**/"))
            return ["."];

        if (pattern.Contains('/'))
        {
            var dirPart = pattern.Split('/')[0];
            return !dirPart.StartsWith('*') ? [dirPart] : ["."];
        }

        return ["."];
    }

    private static bool GetConfigBool(Dictionary<string, object> config, string key, bool defaultValue)
        => config.TryGetValue(key, out var val) ? Convert.ToBoolean(val) : defaultValue;

    private static int GetConfigInt(Dictionary<string, object> config, string key, int defaultValue)
        => config.TryGetValue(key, out var val) ? Convert.ToInt32(val) : defaultValue;
}

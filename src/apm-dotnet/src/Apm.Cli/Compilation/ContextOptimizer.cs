using Apm.Cli.Output;
using Apm.Cli.Primitives;

namespace Apm.Cli.Compilation;

/// <summary>Analysis of a directory's file distribution and patterns.</summary>
public class DirectoryAnalysis
{
    public string Directory { get; set; } = "";
    public int Depth { get; set; }
    public int TotalFiles { get; set; }
    public Dictionary<string, int> PatternMatches { get; set; } = [];
    public HashSet<string> FileTypes { get; set; } = [];

    public double GetRelevanceScore(string pattern)
    {
        if (TotalFiles == 0) return 0.0;
        PatternMatches.TryGetValue(pattern, out var matches);
        return (double)matches / TotalFiles;
    }
}

/// <summary>Analysis of context inheritance chain for a working directory.</summary>
public class InheritanceAnalysis
{
    public string WorkingDirectory { get; set; } = "";
    public List<string> InheritanceChain { get; set; } = [];
    public int TotalContextLoad { get; set; }
    public int RelevantContextLoad { get; set; }
    public double PollutionScore { get; set; }

    public double GetEfficiencyRatio()
        => TotalContextLoad == 0 ? 1.0 : (double)RelevantContextLoad / TotalContextLoad;
}

/// <summary>Candidate placement for an instruction with optimization scores.</summary>
public class PlacementCandidate
{
    public Instruction Instruction { get; set; } = new();
    public string Directory { get; set; } = "";
    public double DirectRelevance { get; set; }
    public double InheritancePollution { get; set; }
    public double DepthSpecificity { get; set; }
    public double TotalScore { get; set; }
    public double CoverageEfficiency { get; set; }
    public double PollutionScoreValue { get; set; }
    public double MaintenanceLocality { get; set; }
}

/// <summary>
/// Context Optimization Engine for distributed AGENTS.md placement.
/// Implements the Minimal Context Principle.
/// </summary>
public class ContextOptimizer
{
    // Optimization parameters
    private const double CoverageEfficiencyWeight = 1.0;
    private const double PollutionMinimizationWeight = 0.8;
    private const double MaintenanceLocalityWeight = 0.3;
    private const double DepthPenaltyFactor = 0.1;
    private const double DiversityFactorBase = 0.5;
    private const double LowDistributionThreshold = 0.3;
    private const double HighDistributionThreshold = 0.7;

    private readonly string _baseDir;
    private readonly Dictionary<string, DirectoryAnalysis> _directoryCache = [];
    private readonly Dictionary<string, HashSet<string>> _patternCache = [];
    private readonly List<string> _excludePatterns;

    private readonly List<OptimizationDecision> _optimizationDecisions = [];
    private readonly List<string> _warnings = [];
    private readonly List<string> _errors = [];
    private DateTime? _startTime;

    public ContextOptimizer(string baseDir, List<string>? excludePatterns = null)
    {
        _baseDir = Path.GetFullPath(baseDir);
        _excludePatterns = excludePatterns ?? [];
    }

    /// <summary>Optimize placement of instructions across directories.</summary>
    public Dictionary<string, List<Instruction>> OptimizeInstructionPlacement(
        List<Instruction> instructions,
        bool verbose = false,
        bool enableTiming = false)
    {
        _startTime = DateTime.UtcNow;
        _optimizationDecisions.Clear();
        _warnings.Clear();
        _errors.Clear();

        // Phase 1: Analyze project structure
        AnalyzeProjectStructure();

        // Phase 2: Process each instruction
        var placementMap = new Dictionary<string, List<Instruction>>();

        foreach (var instruction in instructions)
        {
            if (string.IsNullOrEmpty(instruction.ApplyTo))
            {
                // Global instructions go to root
                if (!placementMap.TryGetValue(_baseDir, out var rootList))
                {
                    rootList = [];
                    placementMap[_baseDir] = rootList;
                }
                rootList.Add(instruction);

                _optimizationDecisions.Add(new OptimizationDecision
                {
                    Instruction = instruction,
                    Pattern = "(global)",
                    MatchingDirectories = 1,
                    TotalDirectories = _directoryCache.Count,
                    DistributionScore = 1.0,
                    Strategy = PlacementStrategy.Distributed,
                    PlacementDirectories = [_baseDir],
                    Reasoning = "Global instruction placed at project root",
                    RelevanceScore = 1.0
                });
                continue;
            }

            var optimalPlacements = FindOptimalPlacements(instruction);
            foreach (var directory in optimalPlacements)
            {
                if (!placementMap.TryGetValue(directory, out var list))
                {
                    list = [];
                    placementMap[directory] = list;
                }
                list.Add(instruction);
            }
        }

        return placementMap;
    }

    /// <summary>Analyze context inheritance chain for a working directory.</summary>
    public InheritanceAnalysis AnalyzeContextInheritance(
        string workingDirectory,
        Dictionary<string, List<Instruction>> placementMap)
    {
        var chain = GetInheritanceChain(workingDirectory);
        var totalContext = 0;
        var relevantContext = 0;

        foreach (var dir in chain)
        {
            if (placementMap.TryGetValue(dir, out var instructions))
            {
                totalContext += instructions.Count;
                foreach (var inst in instructions)
                {
                    if (IsInstructionRelevant(inst, workingDirectory))
                        relevantContext++;
                }
            }
        }

        var pollution = totalContext > 0 ? 1.0 - ((double)relevantContext / totalContext) : 0.0;

        return new InheritanceAnalysis
        {
            WorkingDirectory = workingDirectory,
            InheritanceChain = chain,
            TotalContextLoad = totalContext,
            RelevantContextLoad = relevantContext,
            PollutionScore = pollution
        };
    }

    /// <summary>Calculate optimization statistics for the placement map.</summary>
    public OptimizationStats GetOptimizationStats(Dictionary<string, List<Instruction>> placementMap)
    {
        if (placementMap.Count == 0)
        {
            return new OptimizationStats
            {
                AverageContextEfficiency = 0.0,
                TotalAgentsFiles = 0,
                DirectoriesAnalyzed = _directoryCache.Count
            };
        }

        var efficiencyScores = new List<double>();
        foreach (var (dir, analysis) in _directoryCache)
        {
            if (analysis.TotalFiles > 0)
            {
                var inheritance = AnalyzeContextInheritance(dir, placementMap);
                efficiencyScores.Add(inheritance.GetEfficiencyRatio());
            }
        }

        var avg = efficiencyScores.Count > 0 ? efficiencyScores.Average() : 0.0;

        return new OptimizationStats
        {
            AverageContextEfficiency = avg,
            TotalAgentsFiles = placementMap.Count,
            DirectoriesAnalyzed = _directoryCache.Count
        };
    }

    /// <summary>Generate comprehensive compilation results for output formatting.</summary>
    public CompilationResults GetCompilationResults(
        Dictionary<string, List<Instruction>> placementMap,
        bool isDryRun = false)
    {
        var generationTimeMs = _startTime.HasValue
            ? (int)(DateTime.UtcNow - _startTime.Value).TotalMilliseconds
            : (int?)null;

        var fileTypes = new HashSet<string>();
        var totalFiles = 0;
        foreach (var analysis in _directoryCache.Values)
        {
            fileTypes.UnionWith(analysis.FileTypes);
            totalFiles += analysis.TotalFiles;
        }

        var constitutionPath = Constitution.FindConstitution(_baseDir);
        var constitutionDetected = File.Exists(constitutionPath);

        var projectAnalysis = new ProjectAnalysis
        {
            DirectoriesScanned = _directoryCache.Count,
            FilesAnalyzed = totalFiles,
            FileTypesDetected = fileTypes,
            InstructionPatternsDetected = _optimizationDecisions.Count,
            MaxDepth = _directoryCache.Values.Select(a => a.Depth).DefaultIfEmpty(0).Max(),
            ConstitutionDetected = constitutionDetected,
            ConstitutionPath = constitutionDetected
                ? Path.GetRelativePath(_baseDir, constitutionPath)
                : null
        };

        var placementSummaries = new List<PlacementSummary>();

        if (placementMap.Count == 0 && constitutionDetected)
        {
            placementSummaries.Add(new PlacementSummary
            {
                Path = _baseDir,
                InstructionCount = 0,
                SourceCount = 1,
                Sources = ["constitution.md"]
            });
        }
        else
        {
            foreach (var (dir, instructions) in placementMap)
            {
                var sources = new HashSet<string>();
                foreach (var inst in instructions)
                {
                    if (!string.IsNullOrEmpty(inst.Source))
                        sources.Add(inst.Source);
                }
                if (constitutionDetected)
                    sources.Add("constitution.md");

                placementSummaries.Add(new PlacementSummary
                {
                    Path = dir,
                    InstructionCount = instructions.Count,
                    SourceCount = sources.Count,
                    Sources = [.. sources]
                });
            }
        }

        var optimizationStats = GetOptimizationStats(placementMap);
        optimizationStats.GenerationTimeMs = generationTimeMs;

        return new CompilationResults
        {
            ProjectAnalysis = projectAnalysis,
            OptimizationDecisions = [.. _optimizationDecisions],
            PlacementSummaries = placementSummaries,
            OptimizationStats = optimizationStats,
            Warnings = [.. _warnings],
            Errors = [.. _errors],
            IsDryRun = isDryRun
        };
    }

    // ── Internal helpers ─────────────────────────────────────────────

    private void AnalyzeProjectStructure()
    {
        _directoryCache.Clear();
        _patternCache.Clear();

        var visited = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var dir in Directory.EnumerateDirectories(_baseDir, "*", new EnumerationOptions
        {
            RecurseSubdirectories = true,
            IgnoreInaccessible = true,
            AttributesToSkip = FileAttributes.Hidden
        }))
        {
            if (!visited.Add(dir)) continue;

            var relPath = Path.GetRelativePath(_baseDir, dir);
            var parts = relPath.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

            if (parts.Any(p => p.StartsWith('.'))) continue;
            if (parts.Any(p => p is "node_modules" or "__pycache__" or ".git" or "dist" or "build")) continue;
            if (ShouldExcludePath(dir)) continue;

            var depth = parts.Length;
            var files = Directory.GetFiles(dir)
                .Where(f => !Path.GetFileName(f).StartsWith('.'))
                .ToArray();

            if (files.Length == 0) continue;

            var analysis = new DirectoryAnalysis
            {
                Directory = dir,
                Depth = depth,
                TotalFiles = files.Length,
                FileTypes = new HashSet<string>(files.Select(f => Path.GetExtension(f)))
            };

            _directoryCache[dir] = analysis;
        }

        // Also analyze base directory itself
        var baseFiles = Directory.GetFiles(_baseDir)
            .Where(f => !Path.GetFileName(f).StartsWith('.'))
            .ToArray();

        if (baseFiles.Length > 0 || !_directoryCache.ContainsKey(_baseDir))
        {
            _directoryCache[_baseDir] = new DirectoryAnalysis
            {
                Directory = _baseDir,
                Depth = 0,
                TotalFiles = baseFiles.Length,
                FileTypes = new HashSet<string>(baseFiles.Select(f => Path.GetExtension(f)))
            };
        }
    }

    private bool ShouldExcludePath(string path)
    {
        if (_excludePatterns.Count == 0) return false;

        string relPath;
        try { relPath = Path.GetRelativePath(_baseDir, path); }
        catch { return false; }

        var normalized = relPath.Replace('\\', '/');

        foreach (var pattern in _excludePatterns)
        {
            var normalizedPattern = pattern.Replace('\\', '/');

            if (normalizedPattern.EndsWith('/'))
            {
                if (normalized.StartsWith(normalizedPattern) || normalized == normalizedPattern.TrimEnd('/'))
                    return true;
            }
            else
            {
                if (normalized.StartsWith(normalizedPattern + "/") || normalized == normalizedPattern)
                    return true;
            }
        }

        return false;
    }

    private List<string> FindOptimalPlacements(Instruction instruction)
    {
        var pattern = instruction.ApplyTo;
        var matchingDirectories = FindMatchingDirectories(pattern);

        if (matchingDirectories.Count == 0)
        {
            var intended = ExtractIntendedDirectory(pattern);
            var placement = intended ?? _baseDir;
            var reasoning = intended is not null
                ? $"No matching files found, placed in intended directory"
                : "No matching files found, fallback to root placement";

            _optimizationDecisions.Add(new OptimizationDecision
            {
                Instruction = instruction,
                Pattern = pattern,
                MatchingDirectories = 0,
                TotalDirectories = _directoryCache.Count,
                DistributionScore = 0.0,
                Strategy = PlacementStrategy.Distributed,
                PlacementDirectories = [placement],
                Reasoning = reasoning,
                RelevanceScore = 0.0
            });

            return [placement];
        }

        var distributionScore = CalculateDistributionScore(matchingDirectories);
        List<string> placements;
        PlacementStrategy strategy;
        string reason;

        if (distributionScore < LowDistributionThreshold)
        {
            strategy = PlacementStrategy.SinglePoint;
            placements = OptimizeSinglePointPlacement(matchingDirectories, instruction);
            reason = "Low distribution pattern optimized for minimal pollution";
        }
        else if (distributionScore > HighDistributionThreshold)
        {
            strategy = PlacementStrategy.Distributed;
            placements = [_baseDir];
            reason = "High distribution pattern placed at root to minimize duplication";
        }
        else
        {
            strategy = PlacementStrategy.SelectiveMulti;
            placements = OptimizeSelectivePlacement(matchingDirectories, instruction);
            reason = "Medium distribution pattern with selective high-relevance placement";
        }

        var relevance = 0.0;
        if (placements.Count > 0 && _directoryCache.TryGetValue(placements[0], out var a))
            relevance = a.GetRelevanceScore(pattern);

        _optimizationDecisions.Add(new OptimizationDecision
        {
            Instruction = instruction,
            Pattern = pattern,
            MatchingDirectories = matchingDirectories.Count,
            TotalDirectories = _directoryCache.Count,
            DistributionScore = distributionScore,
            Strategy = strategy,
            PlacementDirectories = placements,
            Reasoning = reason,
            RelevanceScore = relevance
        });

        return placements;
    }

    private HashSet<string> FindMatchingDirectories(string pattern)
    {
        if (_patternCache.TryGetValue(pattern, out var cached))
            return cached;

        var matchingDirs = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var (dir, analysis) in _directoryCache)
        {
            try
            {
                var files = Directory.GetFiles(dir)
                    .Where(f => !Path.GetFileName(f).StartsWith('.'))
                    .ToArray();

                var matchCount = files.Count(f => FileMatchesPattern(f, pattern));
                if (matchCount > 0)
                {
                    analysis.PatternMatches[pattern] = matchCount;
                    matchingDirs.Add(dir);
                }
            }
            catch
            {
                // skip inaccessible directories
            }
        }

        _patternCache[pattern] = matchingDirs;
        return matchingDirs;
    }

    private bool FileMatchesPattern(string filePath, string pattern)
    {
        try
        {
            var relPath = Path.GetRelativePath(_baseDir, filePath).Replace('\\', '/');
            var normalizedPattern = pattern.Replace('\\', '/');

            // Simple filename-only patterns (e.g., "*.py")
            if (!normalizedPattern.Contains('/'))
            {
                var fileName = Path.GetFileName(filePath);
                return FileNameMatchesGlob(fileName, normalizedPattern);
            }

            // Patterns with directory structure
            return GlobMatch(relPath, normalizedPattern);
        }
        catch
        {
            return false;
        }
    }

    private static bool FileNameMatchesGlob(string fileName, string pattern)
    {
        // Simple *.ext matching
        if (pattern.StartsWith("*."))
        {
            var ext = pattern[1..]; // e.g., ".py"
            return fileName.EndsWith(ext, StringComparison.OrdinalIgnoreCase);
        }
        return string.Equals(fileName, pattern, StringComparison.OrdinalIgnoreCase);
    }

    private static bool GlobMatch(string path, string pattern)
    {
        var pathParts = path.Split('/');
        var patternParts = pattern.Split('/');
        return GlobMatchRecursive(pathParts, 0, patternParts, 0);
    }

    private static bool GlobMatchRecursive(string[] pathParts, int pi, string[] patternParts, int pati)
    {
        if (pati >= patternParts.Length)
            return pi >= pathParts.Length;
        if (pi >= pathParts.Length)
            return patternParts.Skip(pati).All(p => p is "**" or "");

        var pat = patternParts[pati];
        if (pat == "**")
        {
            // Match zero or more directories
            if (GlobMatchRecursive(pathParts, pi, patternParts, pati + 1))
                return true;
            return GlobMatchRecursive(pathParts, pi + 1, patternParts, pati);
        }

        if (FileNameMatchesGlob(pathParts[pi], pat))
            return GlobMatchRecursive(pathParts, pi + 1, patternParts, pati + 1);

        return false;
    }

    private double CalculateDistributionScore(HashSet<string> matchingDirectories)
    {
        var totalWithFiles = _directoryCache.Values.Count(d => d.TotalFiles > 0);
        if (totalWithFiles == 0) return 0.0;

        var baseRatio = (double)matchingDirectories.Count / totalWithFiles;
        var depths = matchingDirectories
            .Where(d => _directoryCache.ContainsKey(d))
            .Select(d => (double)_directoryCache[d].Depth)
            .ToList();

        if (depths.Count == 0) return baseRatio;

        var mean = depths.Average();
        var variance = depths.Sum(d => (d - mean) * (d - mean)) / depths.Count;
        var diversity = 1.0 + (variance * DiversityFactorBase);

        return baseRatio * diversity;
    }

    private List<string> OptimizeSinglePointPlacement(HashSet<string> matchingDirectories, Instruction instruction)
    {
        var minimal = FindMinimalCoveragePlacement(matchingDirectories);
        return minimal is not null ? [minimal] : [_baseDir];
    }

    private List<string> OptimizeSelectivePlacement(HashSet<string> matchingDirectories, Instruction instruction)
    {
        var coverage = FindMinimalCoveragePlacement(matchingDirectories);
        return coverage is not null ? [coverage] : [_baseDir];
    }

    private string? FindMinimalCoveragePlacement(HashSet<string> matchingDirectories)
    {
        if (matchingDirectories.Count == 0) return null;
        if (matchingDirectories.Count == 1) return matchingDirectories.First();

        // Find common ancestor
        var relativeDirs = matchingDirectories
            .Select(d => Path.GetRelativePath(_baseDir, d).Replace('\\', '/'))
            .ToList();

        var parts = relativeDirs.Select(d => d.Split('/')).ToList();
        var minDepth = parts.Min(p => p.Length);
        var commonParts = new List<string>();

        for (var i = 0; i < minDepth; i++)
        {
            var level = parts.Select(p => p[i]).Distinct().ToList();
            if (level.Count == 1)
                commonParts.Add(level[0]);
            else
                break;
        }

        return commonParts.Count > 0
            ? Path.GetFullPath(Path.Combine(_baseDir, string.Join(Path.DirectorySeparatorChar, commonParts)))
            : _baseDir;
    }

    private string? ExtractIntendedDirectory(string pattern)
    {
        if (string.IsNullOrEmpty(pattern) || pattern.StartsWith("**/"))
            return null;

        if (!pattern.Contains('/'))
            return null;

        var firstPart = pattern.Split('/')[0];
        if (firstPart.Contains('*') || string.IsNullOrEmpty(firstPart))
            return null;

        var intended = Path.Combine(_baseDir, firstPart);
        return Directory.Exists(intended) ? intended : null;
    }

    private List<string> GetInheritanceChain(string workingDirectory)
    {
        var chain = new List<string>();
        var visited = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var current = Path.GetFullPath(workingDirectory);

        while (visited.Add(current))
        {
            chain.Add(current);
            if (string.Equals(current, _baseDir, StringComparison.OrdinalIgnoreCase))
                break;

            var parent = Path.GetDirectoryName(current);
            if (parent is null || parent == current) break;
            current = parent;
        }

        return chain;
    }

    private bool IsInstructionRelevant(Instruction instruction, string workingDirectory)
    {
        if (string.IsNullOrEmpty(instruction.ApplyTo))
            return true;

        if (!_directoryCache.TryGetValue(workingDirectory, out var analysis))
            return false;

        if (analysis.PatternMatches.TryGetValue(instruction.ApplyTo, out var matches))
            return matches > 0;

        // Analyze on-demand
        try
        {
            var files = Directory.GetFiles(workingDirectory)
                .Where(f => !Path.GetFileName(f).StartsWith('.'))
                .ToArray();

            var matchCount = files.Count(f => FileMatchesPattern(f, instruction.ApplyTo));
            analysis.PatternMatches[instruction.ApplyTo] = matchCount;
            return matchCount > 0;
        }
        catch
        {
            return false;
        }
    }
}

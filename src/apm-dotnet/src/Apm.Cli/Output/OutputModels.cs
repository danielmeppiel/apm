using Apm.Cli.Primitives;

namespace Apm.Cli.Output;

/// <summary>Placement strategy types for optimization decisions.</summary>
public enum PlacementStrategy
{
    SinglePoint,
    SelectiveMulti,
    Distributed
}

/// <summary>Analysis of the project structure and file distribution.</summary>
public class ProjectAnalysis
{
    public int DirectoriesScanned { get; set; }
    public int FilesAnalyzed { get; set; }
    public HashSet<string> FileTypesDetected { get; set; } = [];
    public int InstructionPatternsDetected { get; set; }
    public int MaxDepth { get; set; }
    public bool ConstitutionDetected { get; set; }
    public string? ConstitutionPath { get; set; }

    /// <summary>Get a concise summary of detected file types.</summary>
    public string GetFileTypesSummary()
    {
        if (FileTypesDetected.Count == 0) return "none";
        var types = FileTypesDetected
            .Where(t => !string.IsNullOrEmpty(t))
            .Select(t => t.TrimStart('.'))
            .OrderBy(t => t)
            .ToList();
        return types.Count <= 3
            ? string.Join(", ", types)
            : $"{string.Join(", ", types.Take(3))} and {types.Count - 3} more";
    }
}

/// <summary>Details about a specific optimization decision for an instruction.</summary>
public class OptimizationDecision
{
    public Instruction Instruction { get; set; } = new();
    public string Pattern { get; set; } = "";
    public int MatchingDirectories { get; set; }
    public int TotalDirectories { get; set; }
    public double DistributionScore { get; set; }
    public PlacementStrategy Strategy { get; set; }
    public List<string> PlacementDirectories { get; set; } = [];
    public string Reasoning { get; set; } = "";
    /// <summary>Coverage efficiency for primary placement directory.</summary>
    public double RelevanceScore { get; set; }

    /// <summary>Get the distribution ratio (matching/total).</summary>
    public double DistributionRatio
        => TotalDirectories > 0 ? (double)MatchingDirectories / TotalDirectories : 0.0;
}

/// <summary>Summary of a single AGENTS.md file placement.</summary>
public class PlacementSummary
{
    public string Path { get; set; } = "";
    public int InstructionCount { get; set; }
    public int SourceCount { get; set; }
    public List<string> Sources { get; set; } = [];

    /// <summary>Get path relative to base directory.</summary>
    public string GetRelativePath(string baseDir)
    {
        try
        {
            var fullPath = System.IO.Path.GetFullPath(Path);
            var fullBase = System.IO.Path.GetFullPath(baseDir);
            if (fullPath.StartsWith(fullBase, StringComparison.OrdinalIgnoreCase))
            {
                var rel = fullPath[fullBase.Length..].TrimStart(System.IO.Path.DirectorySeparatorChar);
                return string.IsNullOrEmpty(rel) ? "." : rel;
            }
            return Path;
        }
        catch
        {
            return Path;
        }
    }
}

/// <summary>Performance and efficiency statistics from optimization.</summary>
public class OptimizationStats
{
    public double AverageContextEfficiency { get; set; }
    public double? PollutionImprovement { get; set; }
    public double? BaselineEfficiency { get; set; }
    public double? PlacementAccuracy { get; set; }
    public int? GenerationTimeMs { get; set; }
    public int TotalAgentsFiles { get; set; }
    public int DirectoriesAnalyzed { get; set; }

    /// <summary>Calculate efficiency improvement percentage.</summary>
    public double? EfficiencyImprovement
        => BaselineEfficiency.HasValue
            ? (AverageContextEfficiency - BaselineEfficiency.Value) / BaselineEfficiency.Value * 100
            : null;

    /// <summary>Get efficiency as percentage.</summary>
    public double EfficiencyPercentage => AverageContextEfficiency * 100;
}

/// <summary>Complete results from compilation process.</summary>
public class CompilationResults
{
    public ProjectAnalysis ProjectAnalysis { get; set; } = new();
    public List<OptimizationDecision> OptimizationDecisions { get; set; } = [];
    public List<PlacementSummary> PlacementSummaries { get; set; } = [];
    public OptimizationStats OptimizationStats { get; set; } = new();
    public List<string> Warnings { get; set; } = [];
    public List<string> Errors { get; set; } = [];
    public bool IsDryRun { get; set; }
    /// <summary>Target file name for output messages.</summary>
    public string TargetName { get; set; } = "AGENTS.md";

    /// <summary>Get total number of instructions processed.</summary>
    public int TotalInstructions
        => PlacementSummaries.Sum(s => s.InstructionCount);

    /// <summary>Check if there are any warnings or errors.</summary>
    public bool HasIssues => Warnings.Count > 0 || Errors.Count > 0;
}

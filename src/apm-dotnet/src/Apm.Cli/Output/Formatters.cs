using Spectre.Console;

namespace Apm.Cli.Output;

/// <summary>Professional formatter for compilation output using Spectre.Console.</summary>
public class CompilationFormatter
{
    private readonly bool _useColor;
    private string _targetName = "AGENTS.md";

    public CompilationFormatter(bool useColor = true)
    {
        _useColor = useColor;
    }

    /// <summary>Format default compilation output.</summary>
    public string FormatDefault(CompilationResults results)
    {
        _targetName = results.TargetName;
        var lines = new List<string>();

        lines.AddRange(FormatProjectDiscovery(results.ProjectAnalysis));
        lines.Add("");
        lines.AddRange(FormatOptimizationProgress(results.OptimizationDecisions, results.ProjectAnalysis));
        lines.Add("");
        lines.AddRange(FormatResultsSummary(results));

        if (results.HasIssues)
        {
            lines.Add("");
            lines.AddRange(FormatIssues(results.Warnings, results.Errors));
        }

        return string.Join(Environment.NewLine, lines);
    }

    /// <summary>Format verbose compilation output with mathematical details.</summary>
    public string FormatVerbose(CompilationResults results)
    {
        _targetName = results.TargetName;
        var lines = new List<string>();

        lines.AddRange(FormatProjectDiscovery(results.ProjectAnalysis));
        lines.Add("");
        lines.AddRange(FormatOptimizationProgress(results.OptimizationDecisions, results.ProjectAnalysis));
        lines.Add("");
        lines.AddRange(FormatMathematicalAnalysis(results.OptimizationDecisions));
        lines.Add("");
        lines.AddRange(FormatCoverageExplanation(results.OptimizationStats));
        lines.Add("");
        lines.AddRange(FormatDetailedMetrics(results.OptimizationStats));
        lines.Add("");
        lines.AddRange(FormatFinalSummary(results));

        if (results.HasIssues)
        {
            lines.Add("");
            lines.AddRange(FormatIssues(results.Warnings, results.Errors));
        }

        return string.Join(Environment.NewLine, lines);
    }

    /// <summary>Format dry run output.</summary>
    public string FormatDryRun(CompilationResults results)
    {
        _targetName = results.TargetName;
        var lines = new List<string>();

        lines.AddRange(FormatProjectDiscovery(results.ProjectAnalysis));
        lines.Add("");
        lines.AddRange(FormatOptimizationProgress(results.OptimizationDecisions, results.ProjectAnalysis));
        lines.Add("");
        lines.AddRange(FormatDryRunSummary(results));

        if (results.HasIssues)
        {
            lines.Add("");
            lines.AddRange(FormatIssues(results.Warnings, results.Errors));
        }

        return string.Join(Environment.NewLine, lines);
    }

    private List<string> FormatProjectDiscovery(ProjectAnalysis analysis)
    {
        var lines = new List<string> { Styled("Analyzing project structure...", "cyan bold") };

        if (analysis.ConstitutionDetected)
            lines.Add(Styled($"├─ Constitution detected: {analysis.ConstitutionPath}", "dim"));

        var fileTypesSummary = analysis.GetFileTypesSummary();
        lines.Add(Styled($"├─ {analysis.DirectoriesScanned} directories scanned (max depth: {analysis.MaxDepth})", "dim"));
        lines.Add(Styled($"├─ {analysis.FilesAnalyzed} files analyzed across {analysis.FileTypesDetected.Count} file types ({fileTypesSummary})", "dim"));
        lines.Add(Styled($"└─ {analysis.InstructionPatternsDetected} instruction patterns detected", "dim"));

        return lines;
    }

    private List<string> FormatOptimizationProgress(List<OptimizationDecision> decisions, ProjectAnalysis? analysis)
    {
        var lines = new List<string> { Styled("Optimizing placements...", "cyan bold") };

        if (analysis?.ConstitutionDetected == true)
            lines.Add($"{"**",-25} {"constitution.md",-15} {"ALL",-10} → {"./AGENTS.md",-25} (rel: 100%)");

        foreach (var decision in decisions)
        {
            var patternDisplay = string.IsNullOrEmpty(decision.Pattern) ? "(global)" : decision.Pattern;
            var sourceDisplay = "unknown";
            if (!string.IsNullOrEmpty(decision.Instruction?.FilePath))
            {
                try { sourceDisplay = Path.GetFileName(decision.Instruction.FilePath); }
                catch { /* keep unknown */ }
            }

            var ratioDisplay = $"{decision.MatchingDirectories}/{decision.TotalDirectories} dirs";

            if (decision.PlacementDirectories.Count == 1)
            {
                var placement = GetRelativeDisplayPath(decision.PlacementDirectories[0]);
                var relevance = decision.RelevanceScore;
                lines.Add($"{patternDisplay,-25} {sourceDisplay,-15} {ratioDisplay,-10} → {placement,-25} (rel: {relevance * 100:F0}%)");
            }
            else
            {
                var placementCount = decision.PlacementDirectories.Count;
                lines.Add($"{patternDisplay,-25} {sourceDisplay,-15} {ratioDisplay,-10} → {placementCount} locations");
            }
        }

        return lines;
    }

    private List<string> FormatResultsSummary(CompilationResults results)
    {
        var lines = new List<string>();
        var fileCount = results.PlacementSummaries.Count;
        var target = results.TargetName;
        var plural = fileCount != 1 ? "s" : "";
        var summaryLine = results.IsDryRun
            ? $"[DRY RUN] Would generate {fileCount} {target} file{plural}"
            : $"Generated {fileCount} {target} file{plural}";
        var color = results.IsDryRun ? "yellow" : "green";
        lines.Add(Styled(summaryLine, $"{color} bold"));

        lines.AddRange(FormatMetricsLines(results.OptimizationStats));
        lines.Add("");
        lines.AddRange(FormatPlacementDistribution(results));

        return lines;
    }

    private List<string> FormatFinalSummary(CompilationResults results)
    {
        var lines = new List<string>();
        var fileCount = results.PlacementSummaries.Count;
        var target = results.TargetName;
        var plural = fileCount != 1 ? "s" : "";
        var summaryLine = results.IsDryRun
            ? $"[DRY RUN] Would generate {fileCount} {target} file{plural}"
            : $"Generated {fileCount} {target} file{plural}";
        var color = results.IsDryRun ? "yellow" : "green";
        lines.Add(Styled(summaryLine, $"{color} bold"));

        lines.AddRange(FormatMetricsLines(results.OptimizationStats));
        lines.Add("");
        lines.AddRange(FormatPlacementDistribution(results));

        return lines;
    }

    private List<string> FormatMetricsLines(OptimizationStats stats)
    {
        var lines = new List<string>();
        var efficiencyPct = $"{stats.EfficiencyPercentage:F1}%";
        var firstLine = $"┌─ Context efficiency:    {efficiencyPct}";

        if (stats.EfficiencyImprovement.HasValue)
        {
            var improvement = stats.EfficiencyImprovement.Value;
            var baseline = stats.BaselineEfficiency!.Value * 100;
            firstLine += improvement > 0
                ? $" (baseline: {baseline:F1}%, improvement: +{improvement:F0}%)"
                : $" (baseline: {baseline:F1}%, change: {improvement:F0}%)";
        }

        lines.Add(Styled(firstLine, "dim"));

        if (stats.PollutionImprovement.HasValue)
        {
            var pollutionPct = $"{(1.0 - stats.PollutionImprovement.Value) * 100:F1}%";
            var improvementPct = stats.PollutionImprovement.Value > 0
                ? $"-{stats.PollutionImprovement.Value * 100:F0}%"
                : $"+{Math.Abs(stats.PollutionImprovement.Value) * 100:F0}%";
            lines.Add(Styled($"├─ Average pollution:     {pollutionPct} (improvement: {improvementPct})", "dim"));
        }

        if (stats.PlacementAccuracy.HasValue)
            lines.Add(Styled($"├─ Placement accuracy:    {stats.PlacementAccuracy.Value * 100:F1}% (mathematical optimum)", "dim"));

        if (stats.GenerationTimeMs.HasValue)
        {
            lines.Add(Styled($"└─ Generation time:       {stats.GenerationTimeMs.Value}ms", "dim"));
        }
        else if (lines.Count > 1)
        {
            lines[^1] = lines[^1].Replace("├─", "└─");
        }

        return lines;
    }

    private List<string> FormatPlacementDistribution(CompilationResults results)
    {
        var lines = new List<string> { Styled("Placement Distribution", "cyan bold") };
        var cwd = Directory.GetCurrentDirectory();

        for (var i = 0; i < results.PlacementSummaries.Count; i++)
        {
            var summary = results.PlacementSummaries[i];
            var relPath = summary.GetRelativePath(cwd);
            var contentText = GetPlacementDescription(summary);
            var sourceText = $"{summary.SourceCount} source{(summary.SourceCount != 1 ? "s" : "")}";
            var prefix = i < results.PlacementSummaries.Count - 1 ? "├─" : "└─";
            lines.Add(Styled($"{prefix} {relPath,-30} {contentText} from {sourceText}", "dim"));
        }

        return lines;
    }

    private List<string> FormatDryRunSummary(CompilationResults results)
    {
        var lines = new List<string> { Styled("[DRY RUN] File generation preview:", "yellow bold") };
        var cwd = Directory.GetCurrentDirectory();

        for (var i = 0; i < results.PlacementSummaries.Count; i++)
        {
            var summary = results.PlacementSummaries[i];
            var relPath = summary.GetRelativePath(cwd);
            var instructionText = $"{summary.InstructionCount} instruction{(summary.InstructionCount != 1 ? "s" : "")}";
            var sourceText = $"{summary.SourceCount} source{(summary.SourceCount != 1 ? "s" : "")}";
            var prefix = i < results.PlacementSummaries.Count - 1 ? "├─" : "└─";
            lines.Add(Styled($"{prefix} {relPath,-30} {instructionText}, {sourceText}", "dim"));
        }

        lines.Add("");
        lines.Add(Styled("[DRY RUN] No files written. Run 'apm compile' to apply changes.", "yellow"));

        return lines;
    }

    private List<string> FormatMathematicalAnalysis(List<OptimizationDecision> decisions)
    {
        var lines = new List<string>
        {
            Styled("Mathematical Optimization Analysis", "cyan bold"),
            "",
            "Coverage-First Strategy Analysis:"
        };

        foreach (var decision in decisions)
        {
            var pattern = string.IsNullOrEmpty(decision.Pattern) ? "(global)" : decision.Pattern;
            var score = $"{decision.DistributionScore:F3}";
            var strategy = decision.Strategy switch
            {
                PlacementStrategy.SinglePoint => "Single Point",
                PlacementStrategy.SelectiveMulti => "Selective Multi",
                PlacementStrategy.Distributed => "Distributed",
                _ => "Unknown"
            };
            var coverage = decision.DistributionScore < 0.7 ? "✅ Verified" : "⚠️ Root Fallback";
            lines.Add($"  {pattern,-30} {score,-8} {strategy,-15} {coverage}");
        }

        lines.Add("");
        lines.Add("Mathematical Foundation:");
        lines.Add("  Objective: minimize Σ(context_pollution × directory_weight)");
        lines.Add("  Constraints: ∀file_matching_pattern → can_inherit_instruction");
        lines.Add("  Algorithm: Three-tier strategy with coverage verification");
        lines.Add("  Principle: Coverage guarantee takes priority over efficiency");

        return lines;
    }

    private List<string> FormatCoverageExplanation(OptimizationStats stats)
    {
        var lines = new List<string> { Styled("Coverage vs. Efficiency Analysis", "cyan bold"), "" };
        var efficiency = stats.EfficiencyPercentage;

        if (efficiency < 30)
        {
            lines.Add("⚠️  Low Efficiency Detected:");
            lines.Add("   • Coverage guarantee requires some instructions at root level");
            lines.Add("   • This creates pollution for specialized directories");
            lines.Add("   • Trade-off: Guaranteed coverage vs. optimal efficiency");
            lines.Add("   • Alternative: Higher efficiency with coverage violations (data loss)");
            lines.Add("");
            lines.Add("💡 This may be mathematically optimal given coverage constraints");
        }
        else if (efficiency < 60)
        {
            lines.Add("✅ Moderate Efficiency:");
            lines.Add("   • Good balance between coverage and efficiency");
            lines.Add("   • Some coverage-driven pollution is acceptable");
            lines.Add("   • Most patterns are well-localized");
        }
        else
        {
            lines.Add("🎯 High Efficiency:");
            lines.Add("   • Excellent pattern locality achieved");
            lines.Add("   • Minimal coverage conflicts");
            lines.Add("   • Instructions are optimally placed");
        }

        lines.Add("");
        lines.Add("📚 Why Coverage Takes Priority:");
        lines.Add("   • Every file must access applicable instructions");
        lines.Add("   • Hierarchical inheritance prevents data loss");
        lines.Add("   • Better low efficiency than missing instructions");

        return lines;
    }

    private List<string> FormatDetailedMetrics(OptimizationStats stats)
    {
        var lines = new List<string> { Styled("Performance Metrics", "cyan bold") };
        var efficiency = stats.EfficiencyPercentage;
        var pollution = 100 - efficiency;

        string effAssessment = efficiency switch
        {
            >= 80 => "Excellent",
            >= 60 => "Good",
            >= 40 => "Fair",
            >= 20 => "Poor",
            _ => "Very Poor"
        };

        string pollAssessment = pollution switch
        {
            <= 10 => "Excellent",
            <= 25 => "Good",
            <= 50 => "Fair",
            _ => "Poor"
        };

        lines.Add($"Context Efficiency: {efficiency:F1}% ({effAssessment})");
        lines.Add($"Pollution Level: {pollution:F1}% ({pollAssessment})");
        lines.Add("Guide: 80-100% Excellent | 60-80% Good | 40-60% Fair | 20-40% Poor | <20% Very Poor");

        return lines;
    }

    private List<string> FormatIssues(List<string> warnings, List<string> errors)
    {
        var lines = new List<string>();

        foreach (var error in errors)
            lines.Add(Styled($"✗ Error: {error}", "red"));

        foreach (var warning in warnings)
        {
            if (warning.Contains('\n'))
            {
                var warningLines = warning.Split('\n');
                lines.Add(Styled($"⚠ Warning: {warningLines[0]}", "yellow"));
                foreach (var line in warningLines.Skip(1))
                {
                    if (!string.IsNullOrWhiteSpace(line))
                        lines.Add(Styled($"           {line}", "yellow"));
                }
            }
            else
            {
                lines.Add(Styled($"⚠ Warning: {warning}", "yellow"));
            }
        }

        return lines;
    }

    private string GetRelativeDisplayPath(string path)
    {
        try
        {
            var cwd = Directory.GetCurrentDirectory();
            var fullPath = Path.GetFullPath(path);
            var fullCwd = Path.GetFullPath(cwd);
            if (fullPath.StartsWith(fullCwd, StringComparison.OrdinalIgnoreCase))
            {
                var rel = fullPath[fullCwd.Length..].TrimStart(Path.DirectorySeparatorChar);
                return string.IsNullOrEmpty(rel)
                    ? $"./{_targetName}"
                    : $"{rel}/{_targetName}";
            }
            return $"{path}/{_targetName}";
        }
        catch
        {
            return $"{path}/{_targetName}";
        }
    }

    private static string GetPlacementDescription(PlacementSummary summary)
    {
        var hasConstitution = summary.Sources.Any(s => s.Contains("constitution.md"));
        var parts = new List<string>();
        if (hasConstitution) parts.Add("Constitution");
        if (summary.InstructionCount > 0)
            parts.Add($"{summary.InstructionCount} instruction{(summary.InstructionCount != 1 ? "s" : "")}");
        return parts.Count > 0 ? string.Join(" and ", parts) : "content";
    }

    private string Styled(string text, string style)
    {
        // In non-color mode, return plain text.
        // Spectre.Console markup is applied at the AnsiConsole level, not embedded in strings.
        // This formatter returns plain text suitable for both modes.
        _ = style; // style used when rendering via Spectre.Console directly
        return _useColor ? text : text;
    }
}

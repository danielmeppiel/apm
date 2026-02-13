using Apm.Cli.Compilation;
using Apm.Cli.Output;
using Apm.Cli.Primitives;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Compilation;

// ── DirectoryAnalysis model tests ───────────────────────────────────

public class DirectoryAnalysisTests
{
    [Fact]
    public void GetRelevanceScore_ZeroTotalFiles_ReturnsZero()
    {
        var analysis = new DirectoryAnalysis { TotalFiles = 0 };

        analysis.GetRelevanceScore("*.py").Should().Be(0.0);
    }

    [Fact]
    public void GetRelevanceScore_NoMatchesForPattern_ReturnsZero()
    {
        var analysis = new DirectoryAnalysis
        {
            TotalFiles = 10,
            PatternMatches = new Dictionary<string, int> { ["*.cs"] = 5 }
        };

        analysis.GetRelevanceScore("*.py").Should().Be(0.0);
    }

    [Fact]
    public void GetRelevanceScore_WithMatches_ReturnsRatio()
    {
        var analysis = new DirectoryAnalysis
        {
            TotalFiles = 10,
            PatternMatches = new Dictionary<string, int> { ["*.py"] = 3 }
        };

        analysis.GetRelevanceScore("*.py").Should().Be(0.3);
    }

    [Fact]
    public void GetRelevanceScore_AllFilesMatch_ReturnsOne()
    {
        var analysis = new DirectoryAnalysis
        {
            TotalFiles = 5,
            PatternMatches = new Dictionary<string, int> { ["*.cs"] = 5 }
        };

        analysis.GetRelevanceScore("*.cs").Should().Be(1.0);
    }

    [Fact]
    public void DefaultValues_AreEmpty()
    {
        var analysis = new DirectoryAnalysis();

        analysis.Directory.Should().BeEmpty();
        analysis.Depth.Should().Be(0);
        analysis.TotalFiles.Should().Be(0);
        analysis.PatternMatches.Should().BeEmpty();
        analysis.FileTypes.Should().BeEmpty();
    }
}

// ── InheritanceAnalysis model tests ─────────────────────────────────

public class InheritanceAnalysisTests
{
    [Fact]
    public void GetEfficiencyRatio_ZeroTotalContext_ReturnsOne()
    {
        var analysis = new InheritanceAnalysis
        {
            TotalContextLoad = 0,
            RelevantContextLoad = 0
        };

        analysis.GetEfficiencyRatio().Should().Be(1.0);
    }

    [Fact]
    public void GetEfficiencyRatio_AllRelevant_ReturnsOne()
    {
        var analysis = new InheritanceAnalysis
        {
            TotalContextLoad = 5,
            RelevantContextLoad = 5
        };

        analysis.GetEfficiencyRatio().Should().Be(1.0);
    }

    [Fact]
    public void GetEfficiencyRatio_PartiallyRelevant_ReturnsRatio()
    {
        var analysis = new InheritanceAnalysis
        {
            TotalContextLoad = 10,
            RelevantContextLoad = 3
        };

        analysis.GetEfficiencyRatio().Should().Be(0.3);
    }

    [Fact]
    public void GetEfficiencyRatio_NoneRelevant_ReturnsZero()
    {
        var analysis = new InheritanceAnalysis
        {
            TotalContextLoad = 5,
            RelevantContextLoad = 0
        };

        analysis.GetEfficiencyRatio().Should().Be(0.0);
    }

    [Fact]
    public void DefaultValues_AreEmpty()
    {
        var analysis = new InheritanceAnalysis();

        analysis.WorkingDirectory.Should().BeEmpty();
        analysis.InheritanceChain.Should().BeEmpty();
        analysis.TotalContextLoad.Should().Be(0);
        analysis.RelevantContextLoad.Should().Be(0);
        analysis.PollutionScore.Should().Be(0.0);
    }
}

// ── PlacementCandidate model tests ──────────────────────────────────

public class PlacementCandidateTests
{
    [Fact]
    public void DefaultValues_AreZero()
    {
        var candidate = new PlacementCandidate();

        candidate.Directory.Should().BeEmpty();
        candidate.DirectRelevance.Should().Be(0.0);
        candidate.InheritancePollution.Should().Be(0.0);
        candidate.DepthSpecificity.Should().Be(0.0);
        candidate.TotalScore.Should().Be(0.0);
        candidate.CoverageEfficiency.Should().Be(0.0);
        candidate.PollutionScoreValue.Should().Be(0.0);
        candidate.MaintenanceLocality.Should().Be(0.0);
    }
}

// ── ContextOptimizer integration tests ──────────────────────────────

public class ContextOptimizerTests : IDisposable
{
    private readonly string _tempDir;

    public ContextOptimizerTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), "apm_ctx_opt_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    // ── Empty project ───────────────────────────────────────────

    [Fact]
    public void OptimizeInstructionPlacement_EmptyInstructions_ReturnsEmptyMap()
    {
        var optimizer = new ContextOptimizer(_tempDir);

        var result = optimizer.OptimizeInstructionPlacement([]);

        result.Should().BeEmpty();
    }

    // ── Global instructions ─────────────────────────────────────

    [Fact]
    public void OptimizeInstructionPlacement_GlobalInstruction_PlacedAtRoot()
    {
        var optimizer = new ContextOptimizer(_tempDir);
        var instruction = new Instruction
        {
            Name = "global-rule",
            Description = "Global rule",
            ApplyTo = "",
            Content = "Do this everywhere",
            Source = "local"
        };

        var result = optimizer.OptimizeInstructionPlacement([instruction]);

        result.Should().ContainKey(Path.GetFullPath(_tempDir));
        result[Path.GetFullPath(_tempDir)].Should().HaveCount(1);
        result[Path.GetFullPath(_tempDir)][0].Name.Should().Be("global-rule");
    }

    [Fact]
    public void OptimizeInstructionPlacement_MultipleGlobalInstructions_AllPlacedAtRoot()
    {
        var optimizer = new ContextOptimizer(_tempDir);
        var instructions = new List<Instruction>
        {
            new() { Name = "rule-1", Description = "d1", Content = "c1", Source = "local" },
            new() { Name = "rule-2", Description = "d2", Content = "c2", Source = "local" }
        };

        var result = optimizer.OptimizeInstructionPlacement(instructions);

        result[Path.GetFullPath(_tempDir)].Should().HaveCount(2);
    }

    // ── Pattern-based placement with real files ─────────────────

    [Fact]
    public void OptimizeInstructionPlacement_WithMatchingFiles_PlacesInCorrectDirectory()
    {
        var srcDir = Path.Combine(_tempDir, "src");
        Directory.CreateDirectory(srcDir);
        File.WriteAllText(Path.Combine(srcDir, "app.py"), "# python");
        File.WriteAllText(Path.Combine(srcDir, "utils.py"), "# utils");

        var optimizer = new ContextOptimizer(_tempDir);
        var instruction = new Instruction
        {
            Name = "python-style",
            Description = "Python style",
            ApplyTo = "*.py",
            Content = "Use type hints",
            Source = "local"
        };

        var result = optimizer.OptimizeInstructionPlacement([instruction]);

        result.Should().NotBeEmpty();
        var allInstructions = result.Values.SelectMany(v => v).ToList();
        allInstructions.Should().Contain(i => i.Name == "python-style");
    }

    [Fact]
    public void OptimizeInstructionPlacement_NoMatchingFiles_FallsBackToRoot()
    {
        var srcDir = Path.Combine(_tempDir, "src");
        Directory.CreateDirectory(srcDir);
        File.WriteAllText(Path.Combine(srcDir, "app.cs"), "// csharp");

        var optimizer = new ContextOptimizer(_tempDir);
        var instruction = new Instruction
        {
            Name = "ruby-style",
            Description = "Ruby style",
            ApplyTo = "*.rb",
            Content = "Use frozen string literal",
            Source = "local"
        };

        var result = optimizer.OptimizeInstructionPlacement([instruction]);

        result.Should().NotBeEmpty();
        var allInstructions = result.Values.SelectMany(v => v).ToList();
        allInstructions.Should().Contain(i => i.Name == "ruby-style");
    }

    [Fact]
    public void OptimizeInstructionPlacement_MixedGlobalAndPattern_BothPlaced()
    {
        var srcDir = Path.Combine(_tempDir, "src");
        Directory.CreateDirectory(srcDir);
        File.WriteAllText(Path.Combine(srcDir, "main.ts"), "// ts");

        var optimizer = new ContextOptimizer(_tempDir);
        var instructions = new List<Instruction>
        {
            new() { Name = "global", Description = "d", ApplyTo = "", Content = "c", Source = "local" },
            new() { Name = "ts-rule", Description = "d", ApplyTo = "*.ts", Content = "c", Source = "local" }
        };

        var result = optimizer.OptimizeInstructionPlacement(instructions);

        var allInstructions = result.Values.SelectMany(v => v).ToList();
        allInstructions.Should().HaveCount(2);
        allInstructions.Should().Contain(i => i.Name == "global");
        allInstructions.Should().Contain(i => i.Name == "ts-rule");
    }

    // ── Distribution score strategies ───────────────────────────

    [Fact]
    public void OptimizeInstructionPlacement_HighlyDistributedPattern_PlacedAtRoot()
    {
        // Create many directories all with .py files to trigger high distribution
        for (var i = 0; i < 5; i++)
        {
            var dir = Path.Combine(_tempDir, $"pkg{i}");
            Directory.CreateDirectory(dir);
            File.WriteAllText(Path.Combine(dir, $"mod{i}.py"), "# python");
        }

        var optimizer = new ContextOptimizer(_tempDir);
        var instruction = new Instruction
        {
            Name = "py-everywhere",
            Description = "d",
            ApplyTo = "*.py",
            Content = "c",
            Source = "local"
        };

        var result = optimizer.OptimizeInstructionPlacement([instruction]);

        // High distribution should place at root
        result.Should().ContainKey(Path.GetFullPath(_tempDir));
    }

    [Fact]
    public void OptimizeInstructionPlacement_ConcentratedPattern_PlacedNearFiles()
    {
        // Create one directory with target files and many others without
        var targetDir = Path.Combine(_tempDir, "special");
        Directory.CreateDirectory(targetDir);
        File.WriteAllText(Path.Combine(targetDir, "main.rs"), "fn main() {}");
        File.WriteAllText(Path.Combine(targetDir, "lib.rs"), "pub mod lib;");

        for (var i = 0; i < 10; i++)
        {
            var dir = Path.Combine(_tempDir, $"other{i}");
            Directory.CreateDirectory(dir);
            File.WriteAllText(Path.Combine(dir, $"file{i}.txt"), "text");
        }

        var optimizer = new ContextOptimizer(_tempDir);
        var instruction = new Instruction
        {
            Name = "rust-rule",
            Description = "d",
            ApplyTo = "*.rs",
            Content = "c",
            Source = "local"
        };

        var result = optimizer.OptimizeInstructionPlacement([instruction]);

        var allInstructions = result.Values.SelectMany(v => v).ToList();
        allInstructions.Should().Contain(i => i.Name == "rust-rule");
    }

    // ── Exclude patterns ────────────────────────────────────────

    [Fact]
    public void OptimizeInstructionPlacement_WithExcludePatterns_SkipsExcludedDirs()
    {
        var vendorDir = Path.Combine(_tempDir, "vendor");
        Directory.CreateDirectory(vendorDir);
        File.WriteAllText(Path.Combine(vendorDir, "dep.py"), "# vendor");

        var srcDir = Path.Combine(_tempDir, "src");
        Directory.CreateDirectory(srcDir);
        File.WriteAllText(Path.Combine(srcDir, "app.py"), "# app");

        var optimizer = new ContextOptimizer(_tempDir, ["vendor/"]);
        var instruction = new Instruction
        {
            Name = "py-rule",
            Description = "d",
            ApplyTo = "*.py",
            Content = "c",
            Source = "local"
        };

        var result = optimizer.OptimizeInstructionPlacement([instruction]);

        // Vendor directory should not appear as a placement target
        result.Keys.Should().NotContain(k => k.Contains("vendor", StringComparison.OrdinalIgnoreCase));
    }

    // ── AnalyzeContextInheritance ───────────────────────────────

    [Fact]
    public void AnalyzeContextInheritance_EmptyPlacementMap_ZeroPollution()
    {
        var srcDir = Path.Combine(_tempDir, "src");
        Directory.CreateDirectory(srcDir);
        File.WriteAllText(Path.Combine(srcDir, "app.py"), "# app");

        var optimizer = new ContextOptimizer(_tempDir);
        optimizer.OptimizeInstructionPlacement([]);

        var analysis = optimizer.AnalyzeContextInheritance(srcDir, new Dictionary<string, List<Instruction>>());

        analysis.TotalContextLoad.Should().Be(0);
        analysis.RelevantContextLoad.Should().Be(0);
        analysis.PollutionScore.Should().Be(0.0);
    }

    [Fact]
    public void AnalyzeContextInheritance_InheritanceChainIncludesAncestors()
    {
        var srcDir = Path.Combine(_tempDir, "src");
        var subDir = Path.Combine(srcDir, "sub");
        Directory.CreateDirectory(subDir);
        File.WriteAllText(Path.Combine(subDir, "file.py"), "# file");

        var optimizer = new ContextOptimizer(_tempDir);
        optimizer.OptimizeInstructionPlacement([]);

        var placementMap = new Dictionary<string, List<Instruction>>();
        var analysis = optimizer.AnalyzeContextInheritance(subDir, placementMap);

        // Chain should include subDir and ancestors up to baseDir
        analysis.InheritanceChain.Should().Contain(Path.GetFullPath(subDir));
    }

    [Fact]
    public void AnalyzeContextInheritance_WorkingDirectory_IsRecorded()
    {
        var srcDir = Path.Combine(_tempDir, "src");
        Directory.CreateDirectory(srcDir);
        File.WriteAllText(Path.Combine(srcDir, "app.py"), "# app");

        var optimizer = new ContextOptimizer(_tempDir);
        optimizer.OptimizeInstructionPlacement([]);

        var analysis = optimizer.AnalyzeContextInheritance(srcDir, new Dictionary<string, List<Instruction>>());

        analysis.WorkingDirectory.Should().Be(srcDir);
    }

    [Fact]
    public void AnalyzeContextInheritance_WithRelevantInstructions_LowPollution()
    {
        var srcDir = Path.Combine(_tempDir, "src");
        Directory.CreateDirectory(srcDir);
        File.WriteAllText(Path.Combine(srcDir, "app.py"), "# app");

        var optimizer = new ContextOptimizer(_tempDir);
        var instruction = new Instruction
        {
            Name = "py-rule",
            Description = "d",
            ApplyTo = "*.py",
            Content = "c",
            Source = "local"
        };

        var placementMap = optimizer.OptimizeInstructionPlacement([instruction]);
        var analysis = optimizer.AnalyzeContextInheritance(srcDir, placementMap);

        // Instructions relevant to the working dir should not be pollution
        analysis.PollutionScore.Should().BeLessThanOrEqualTo(1.0);
        analysis.PollutionScore.Should().BeGreaterThanOrEqualTo(0.0);
    }

    // ── GetOptimizationStats ────────────────────────────────────

    [Fact]
    public void GetOptimizationStats_EmptyMap_ReturnsZeroEfficiency()
    {
        var optimizer = new ContextOptimizer(_tempDir);
        optimizer.OptimizeInstructionPlacement([]);

        var stats = optimizer.GetOptimizationStats(new Dictionary<string, List<Instruction>>());

        stats.AverageContextEfficiency.Should().Be(0.0);
        stats.TotalAgentsFiles.Should().Be(0);
    }

    [Fact]
    public void GetOptimizationStats_WithPlacements_ReturnsNonZeroStats()
    {
        var srcDir = Path.Combine(_tempDir, "src");
        Directory.CreateDirectory(srcDir);
        File.WriteAllText(Path.Combine(srcDir, "app.py"), "# app");

        var optimizer = new ContextOptimizer(_tempDir);
        var instruction = new Instruction
        {
            Name = "py-rule",
            Description = "d",
            ApplyTo = "*.py",
            Content = "c",
            Source = "local"
        };

        var placementMap = optimizer.OptimizeInstructionPlacement([instruction]);
        var stats = optimizer.GetOptimizationStats(placementMap);

        stats.TotalAgentsFiles.Should().BeGreaterThan(0);
        stats.DirectoriesAnalyzed.Should().BeGreaterThan(0);
    }

    // ── GetCompilationResults ───────────────────────────────────

    [Fact]
    public void GetCompilationResults_EmptyProject_ReturnsValidResults()
    {
        var optimizer = new ContextOptimizer(_tempDir);
        var placementMap = optimizer.OptimizeInstructionPlacement([]);

        var results = optimizer.GetCompilationResults(placementMap);

        results.ProjectAnalysis.Should().NotBeNull();
        results.OptimizationDecisions.Should().BeEmpty();
        results.Warnings.Should().BeEmpty();
        results.Errors.Should().BeEmpty();
    }

    [Fact]
    public void GetCompilationResults_DryRunFlag_IsRecorded()
    {
        var optimizer = new ContextOptimizer(_tempDir);
        var placementMap = optimizer.OptimizeInstructionPlacement([]);

        var results = optimizer.GetCompilationResults(placementMap, isDryRun: true);

        results.IsDryRun.Should().BeTrue();
    }

    [Fact]
    public void GetCompilationResults_WithInstructions_RecordsDecisions()
    {
        var srcDir = Path.Combine(_tempDir, "src");
        Directory.CreateDirectory(srcDir);
        File.WriteAllText(Path.Combine(srcDir, "main.cs"), "// cs");

        var optimizer = new ContextOptimizer(_tempDir);
        var instructions = new List<Instruction>
        {
            new() { Name = "cs-rule", Description = "d", ApplyTo = "*.cs", Content = "c", Source = "local" }
        };

        var placementMap = optimizer.OptimizeInstructionPlacement(instructions);
        var results = optimizer.GetCompilationResults(placementMap);

        results.OptimizationDecisions.Should().HaveCount(1);
        results.OptimizationDecisions[0].Pattern.Should().Be("*.cs");
    }

    [Fact]
    public void GetCompilationResults_GlobalInstruction_RecordsGlobalDecision()
    {
        var optimizer = new ContextOptimizer(_tempDir);
        var instructions = new List<Instruction>
        {
            new() { Name = "global", Description = "d", ApplyTo = "", Content = "c", Source = "local" }
        };

        var placementMap = optimizer.OptimizeInstructionPlacement(instructions);
        var results = optimizer.GetCompilationResults(placementMap);

        results.OptimizationDecisions.Should().HaveCount(1);
        results.OptimizationDecisions[0].Pattern.Should().Be("(global)");
        results.OptimizationDecisions[0].Reasoning.Should().Contain("Global");
    }

    [Fact]
    public void GetCompilationResults_PlacementSummaries_IncludeSourceAttribution()
    {
        var srcDir = Path.Combine(_tempDir, "src");
        Directory.CreateDirectory(srcDir);
        File.WriteAllText(Path.Combine(srcDir, "app.ts"), "// ts");

        var optimizer = new ContextOptimizer(_tempDir);
        var instructions = new List<Instruction>
        {
            new() { Name = "ts-rule", Description = "d", ApplyTo = "*.ts", Content = "c", Source = "my-package" }
        };

        var placementMap = optimizer.OptimizeInstructionPlacement(instructions);
        var results = optimizer.GetCompilationResults(placementMap);

        results.PlacementSummaries.Should().NotBeEmpty();
        results.PlacementSummaries.Should().Contain(s => s.Sources.Contains("my-package"));
    }

    [Fact]
    public void GetCompilationResults_ProjectAnalysis_DetectsFileTypes()
    {
        var srcDir = Path.Combine(_tempDir, "src");
        Directory.CreateDirectory(srcDir);
        File.WriteAllText(Path.Combine(srcDir, "app.py"), "# py");
        File.WriteAllText(Path.Combine(srcDir, "lib.cs"), "// cs");

        var optimizer = new ContextOptimizer(_tempDir);
        var placementMap = optimizer.OptimizeInstructionPlacement([]);
        var results = optimizer.GetCompilationResults(placementMap);

        results.ProjectAnalysis.FileTypesDetected.Should().Contain(".py");
        results.ProjectAnalysis.FileTypesDetected.Should().Contain(".cs");
    }

    [Fact]
    public void GetCompilationResults_ProjectAnalysis_CountsDirectories()
    {
        var srcDir = Path.Combine(_tempDir, "src");
        var libDir = Path.Combine(_tempDir, "lib");
        Directory.CreateDirectory(srcDir);
        Directory.CreateDirectory(libDir);
        File.WriteAllText(Path.Combine(srcDir, "a.py"), "#");
        File.WriteAllText(Path.Combine(libDir, "b.py"), "#");

        var optimizer = new ContextOptimizer(_tempDir);
        var placementMap = optimizer.OptimizeInstructionPlacement([]);
        var results = optimizer.GetCompilationResults(placementMap);

        results.ProjectAnalysis.DirectoriesScanned.Should().BeGreaterThanOrEqualTo(2);
    }

    // ── Glob pattern matching (directory structure) ─────────────

    [Fact]
    public void OptimizeInstructionPlacement_DirectoryGlobPattern_MatchesCorrectly()
    {
        var srcDir = Path.Combine(_tempDir, "src");
        var subDir = Path.Combine(srcDir, "components");
        Directory.CreateDirectory(subDir);
        File.WriteAllText(Path.Combine(subDir, "button.tsx"), "// tsx");

        var optimizer = new ContextOptimizer(_tempDir);
        var instruction = new Instruction
        {
            Name = "tsx-rule",
            Description = "d",
            ApplyTo = "src/**/*.tsx",
            Content = "c",
            Source = "local"
        };

        var result = optimizer.OptimizeInstructionPlacement([instruction]);

        var allInstructions = result.Values.SelectMany(v => v).ToList();
        allInstructions.Should().Contain(i => i.Name == "tsx-rule");
    }

    // ── Intended directory extraction ───────────────────────────

    [Fact]
    public void OptimizeInstructionPlacement_PatternWithExistingDir_PlacesInIntendedDir()
    {
        var srcDir = Path.Combine(_tempDir, "src");
        Directory.CreateDirectory(srcDir);
        // No matching files, but directory exists
        File.WriteAllText(Path.Combine(srcDir, "readme.txt"), "text");

        var optimizer = new ContextOptimizer(_tempDir);
        var instruction = new Instruction
        {
            Name = "go-rule",
            Description = "d",
            ApplyTo = "src/*.go",
            Content = "c",
            Source = "local"
        };

        var result = optimizer.OptimizeInstructionPlacement([instruction]);

        // Should fall back to intended directory "src" even with no .go files
        result.Should().NotBeEmpty();
        result.Should().ContainKey(Path.GetFullPath(srcDir));
    }

    // ── Multiple instructions compete for same directory ────────

    [Fact]
    public void OptimizeInstructionPlacement_MultipleInstructions_SameDir_AllPlaced()
    {
        var srcDir = Path.Combine(_tempDir, "src");
        Directory.CreateDirectory(srcDir);
        File.WriteAllText(Path.Combine(srcDir, "app.py"), "#");
        File.WriteAllText(Path.Combine(srcDir, "test.py"), "#");

        var optimizer = new ContextOptimizer(_tempDir);
        var instructions = new List<Instruction>
        {
            new() { Name = "rule-a", Description = "d", ApplyTo = "*.py", Content = "c", Source = "local" },
            new() { Name = "rule-b", Description = "d", ApplyTo = "*.py", Content = "c2", Source = "local" }
        };

        var result = optimizer.OptimizeInstructionPlacement(instructions);

        var allInstructions = result.Values.SelectMany(v => v).ToList();
        allInstructions.Should().Contain(i => i.Name == "rule-a");
        allInstructions.Should().Contain(i => i.Name == "rule-b");
    }

    // ── Hidden directories and special dirs are skipped ─────────

    [Fact]
    public void OptimizeInstructionPlacement_SkipsNodeModules()
    {
        var nmDir = Path.Combine(_tempDir, "node_modules", "pkg");
        Directory.CreateDirectory(nmDir);
        File.WriteAllText(Path.Combine(nmDir, "index.js"), "//");

        var srcDir = Path.Combine(_tempDir, "src");
        Directory.CreateDirectory(srcDir);
        File.WriteAllText(Path.Combine(srcDir, "app.js"), "//");

        var optimizer = new ContextOptimizer(_tempDir);
        var instruction = new Instruction
        {
            Name = "js-rule",
            Description = "d",
            ApplyTo = "*.js",
            Content = "c",
            Source = "local"
        };

        var result = optimizer.OptimizeInstructionPlacement([instruction]);

        result.Keys.Should().NotContain(k => k.Contains("node_modules", StringComparison.OrdinalIgnoreCase));
    }

    // ── Verbose and timing flags don't affect result ────────────

    [Fact]
    public void OptimizeInstructionPlacement_VerboseMode_SameResult()
    {
        var srcDir = Path.Combine(_tempDir, "src");
        Directory.CreateDirectory(srcDir);
        File.WriteAllText(Path.Combine(srcDir, "app.py"), "#");

        var instruction = new Instruction
        {
            Name = "rule", Description = "d", ApplyTo = "*.py", Content = "c", Source = "local"
        };

        var optimizer1 = new ContextOptimizer(_tempDir);
        var result1 = optimizer1.OptimizeInstructionPlacement([instruction], verbose: false);

        var optimizer2 = new ContextOptimizer(_tempDir);
        var result2 = optimizer2.OptimizeInstructionPlacement([instruction], verbose: true);

        result1.Keys.Should().BeEquivalentTo(result2.Keys);
    }

    [Fact]
    public void OptimizeInstructionPlacement_TimingEnabled_SameResult()
    {
        var optimizer = new ContextOptimizer(_tempDir);
        var instruction = new Instruction
        {
            Name = "rule", Description = "d", ApplyTo = "", Content = "c", Source = "local"
        };

        var result = optimizer.OptimizeInstructionPlacement([instruction], enableTiming: true);

        result.Should().NotBeEmpty();
    }

    // ── GetCompilationResults timing ────────────────────────────

    [Fact]
    public void GetCompilationResults_WithTiming_RecordsGenerationTime()
    {
        var optimizer = new ContextOptimizer(_tempDir);
        var placementMap = optimizer.OptimizeInstructionPlacement([], enableTiming: true);

        var results = optimizer.GetCompilationResults(placementMap);

        results.OptimizationStats.GenerationTimeMs.Should().NotBeNull();
        results.OptimizationStats.GenerationTimeMs.Should().BeGreaterThanOrEqualTo(0);
    }
}

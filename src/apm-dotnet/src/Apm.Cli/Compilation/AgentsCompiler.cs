using Apm.Cli.Primitives;
using Apm.Cli.Utils;

namespace Apm.Cli.Compilation;

/// <summary>
/// Main compiler for generating AGENTS.md files.
/// Orchestrates primitive discovery, template building, link resolution,
/// and distributed/single-file output strategies.
/// </summary>
public class AgentsCompiler
{
    private readonly string _baseDir;
    private readonly ITemplateBuilder _templateBuilder;
    private readonly ILinkResolver _linkResolver;
    private readonly IClaudeFormatter? _claudeFormatter;
    private readonly IDistributedCompiler? _distributedCompiler;
    private readonly IConstitutionInjector? _constitutionInjector;

    private readonly List<string> _warnings = [];
    private readonly List<string> _errors = [];

    /// <summary>Initialize the compiler.</summary>
    /// <param name="baseDir">Base directory for compilation. Defaults to current directory.</param>
    /// <param name="templateBuilder">Template builder implementation.</param>
    /// <param name="linkResolver">Link resolver implementation.</param>
    /// <param name="claudeFormatter">Optional Claude formatter override.</param>
    /// <param name="distributedCompiler">Optional distributed compiler override.</param>
    /// <param name="constitutionInjector">Optional constitution injector override.</param>
    public AgentsCompiler(
        string baseDir = ".",
        ITemplateBuilder? templateBuilder = null,
        ILinkResolver? linkResolver = null,
        IClaudeFormatter? claudeFormatter = null,
        IDistributedCompiler? distributedCompiler = null,
        IConstitutionInjector? constitutionInjector = null)
    {
        _baseDir = Path.GetFullPath(baseDir);
        _templateBuilder = templateBuilder ?? new TemplateBuilder();
        _linkResolver = linkResolver ?? new UnifiedLinkResolver(baseDir);
        _claudeFormatter = claudeFormatter;
        _distributedCompiler = distributedCompiler;
        _constitutionInjector = constitutionInjector ?? new ConstitutionInjector(baseDir);
    }

    /// <summary>
    /// Compile AGENTS.md and/or CLAUDE.md based on target configuration.
    /// Routes compilation to appropriate targets based on config.Target.
    /// </summary>
    public CompilationResult Compile(CompilationConfig config, PrimitiveCollection? primitives = null)
    {
        _warnings.Clear();
        _errors.Clear();

        try
        {
            // Use provided primitives or discover them
            primitives ??= config.LocalOnly
                ? PrimitiveDiscovery.DiscoverPrimitives(_baseDir)
                : PrimitiveDiscovery.DiscoverPrimitivesWithDependencies(_baseDir);

            var results = new List<CompilationResult>();

            // AGENTS.md target (vscode/agents)
            if (config.Target is "vscode" or "agents" or "all")
                results.Add(CompileAgentsMd(config, primitives));

            // CLAUDE.md target
            if (config.Target is "claude" or "all")
                results.Add(CompileClaudeMd(config, primitives));

            return MergeResults(results);
        }
        catch (Exception e)
        {
            _errors.Add($"Compilation failed: {e.Message}");
            return new CompilationResult
            {
                Success = false,
                Warnings = [.. _warnings],
                Errors = [.. _errors],
            };
        }
    }

    // ── Target routing ───────────────────────────────────────────────

    private CompilationResult CompileAgentsMd(CompilationConfig config, PrimitiveCollection primitives)
    {
        if (config.Strategy == "distributed" && !config.SingleAgents)
            return CompileDistributed(config, primitives);

        return CompileSingleFile(config, primitives);
    }

    // ── Distributed compilation ──────────────────────────────────────

    private CompilationResult CompileDistributed(CompilationConfig config, PrimitiveCollection primitives)
    {
        if (_distributedCompiler is null)
        {
            _errors.Add("Distributed compiler not available (not yet ported).");
            return new CompilationResult
            {
                Success = false,
                Warnings = [.. _warnings],
                Errors = [.. _errors],
            };
        }

        var distributedConfig = new Dictionary<string, object>
        {
            ["min_instructions_per_file"] = config.MinInstructionsPerFile,
            ["source_attribution"] = config.SourceAttribution,
            ["debug"] = config.Debug,
            ["clean_orphaned"] = config.CleanOrphaned,
            ["dry_run"] = config.DryRun,
        };

        var distributedResult = _distributedCompiler.CompileDistributed(primitives, distributedConfig);

        // Display compilation output
        var displayOutput = _distributedCompiler.FormatCompilationOutput(
            config.DryRun,
            verbose: config.Debug || config.Trace,
            debug: config.Debug);
        if (displayOutput is not null)
            Console.Write(displayOutput);

        if (!distributedResult.Success)
        {
            _warnings.AddRange(distributedResult.Warnings);
            _errors.AddRange(distributedResult.Errors);
            return new CompilationResult
            {
                Success = false,
                Warnings = [.. _warnings],
                Errors = [.. _errors],
                Stats = distributedResult.Stats,
            };
        }

        // Dry-run: preview only
        if (config.DryRun)
        {
            var successfulWrites = distributedResult.ContentMap.Keys
                .Count(path => Directory.Exists(Path.GetDirectoryName(path)));

            var stats = new Dictionary<string, object>(distributedResult.Stats)
            {
                ["agents_files_generated"] = successfulWrites
            };

            return new CompilationResult
            {
                Success = true,
                OutputPath = "Preview mode - no files written",
                Content = GeneratePlacementSummary(distributedResult),
                Warnings = [.. distributedResult.Warnings],
                Errors = [.. distributedResult.Errors],
                Stats = stats,
            };
        }

        // Write distributed AGENTS.md files
        var filesWritten = 0;
        foreach (var (agentsPath, content) in distributedResult.ContentMap)
        {
            try
            {
                WriteDistributedFile(agentsPath, content, config);
                filesWritten++;
            }
            catch (IOException e)
            {
                _errors.Add($"Failed to write {agentsPath}: {e.Message}");
            }
        }

        var updatedStats = new Dictionary<string, object>(distributedResult.Stats)
        {
            ["agents_files_generated"] = filesWritten
        };

        _warnings.AddRange(distributedResult.Warnings);
        _errors.AddRange(distributedResult.Errors);

        return new CompilationResult
        {
            Success = _errors.Count == 0,
            OutputPath = $"Distributed: {distributedResult.Placements.Count} AGENTS.md files",
            Content = GenerateDistributedSummary(distributedResult, config),
            Warnings = [.. _warnings],
            Errors = [.. _errors],
            Stats = updatedStats,
        };
    }

    // ── Single-file compilation ──────────────────────────────────────

    private CompilationResult CompileSingleFile(CompilationConfig config, PrimitiveCollection primitives)
    {
        var validationErrors = ValidatePrimitives(primitives);
        if (validationErrors.Count > 0)
            _errors.AddRange(validationErrors);

        var templateData = GenerateTemplateData(primitives, config);
        var content = GenerateOutput(templateData, config);

        var outputPath = Path.Combine(_baseDir, config.OutputPath);
        if (!config.DryRun)
            WriteOutputFile(outputPath, content);

        var stats = CompileStats(primitives, templateData);

        return new CompilationResult
        {
            Success = _errors.Count == 0,
            OutputPath = outputPath,
            Content = content,
            Warnings = [.. _warnings],
            Errors = [.. _errors],
            Stats = stats,
        };
    }

    // ── CLAUDE.md compilation ────────────────────────────────────────

    private CompilationResult CompileClaudeMd(CompilationConfig config, PrimitiveCollection primitives)
    {
        if (_claudeFormatter is null || _distributedCompiler is null)
        {
            _errors.Add("Claude formatter or distributed compiler not available (not yet ported).");
            return new CompilationResult
            {
                Success = false,
                Warnings = [.. _warnings],
                Errors = [.. _errors],
            };
        }

        var directoryMap = _distributedCompiler.AnalyzeDirectoryStructure(primitives.Instructions);
        var placements = _distributedCompiler.DetermineAgentsPlacement(
            primitives.Instructions,
            directoryMap,
            config.MinInstructionsPerFile,
            config.Debug);

        var claudeConfig = new Dictionary<string, object>
        {
            ["source_attribution"] = config.SourceAttribution,
            ["debug"] = config.Debug,
        };

        var claudeResult = _claudeFormatter.FormatDistributed(primitives, placements, claudeConfig);

        var allWarnings = new List<string>(claudeResult.Warnings);
        var allErrors = new List<string>(claudeResult.Errors);

        // Dry-run preview
        if (config.DryRun)
        {
            var previewLines = new List<string>
            {
                $"CLAUDE.md Preview: Would generate {claudeResult.Placements.Count} files"
            };
            foreach (var claudePath in claudeResult.ContentMap.Keys)
            {
                var relPath = Path.GetRelativePath(_baseDir, claudePath);
                previewLines.Add($"  📄 {relPath}");
            }

            return new CompilationResult
            {
                Success = allErrors.Count == 0,
                OutputPath = "Preview mode - CLAUDE.md",
                Content = string.Join(Environment.NewLine, previewLines),
                Warnings = allWarnings,
                Errors = allErrors,
                Stats = claudeResult.Stats,
            };
        }

        // Write CLAUDE.md files
        var filesWritten = 0;
        foreach (var (claudePath, content) in claudeResult.ContentMap)
        {
            try
            {
                var dir = Path.GetDirectoryName(claudePath);
                if (dir is not null)
                    Directory.CreateDirectory(dir);

                var finalContent = content;
                if (config.WithConstitution && _constitutionInjector is not null)
                {
                    try
                    {
                        (finalContent, _, _) = _constitutionInjector.Inject(
                            content, withConstitution: true, outputPath: claudePath);
                    }
                    catch (Exception)
                    {
                        // Use original content if injection fails
                    }
                }

                File.WriteAllText(claudePath, finalContent);
                filesWritten++;
            }
            catch (IOException e)
            {
                allErrors.Add($"Failed to write {claudePath}: {e.Message}");
            }
        }

        var stats = new Dictionary<string, object>(claudeResult.Stats)
        {
            ["claude_files_written"] = filesWritten
        };

        // Display output
        var displayOutput = _distributedCompiler.FormatCompilationOutput(
            config.DryRun, verbose: config.Debug || config.Trace, debug: config.Debug);
        if (displayOutput is not null)
            Console.Write(displayOutput);

        var summaryLines = new List<string>
        {
            "# CLAUDE.md Compilation Summary",
            "",
            $"Generated {filesWritten} CLAUDE.md files:"
        };
        foreach (var placement in claudeResult.Placements)
        {
            var relPath = Path.GetRelativePath(_baseDir, placement.AgentsPath);
            summaryLines.Add($"- {relPath} ({placement.Instructions.Count} instructions)");
        }

        return new CompilationResult
        {
            Success = allErrors.Count == 0,
            OutputPath = $"CLAUDE.md: {filesWritten} files",
            Content = string.Join(Environment.NewLine, summaryLines),
            Warnings = allWarnings,
            Errors = allErrors,
            Stats = stats,
        };
    }

    // ── Helpers ──────────────────────────────────────────────────────

    internal List<string> ValidatePrimitives(PrimitiveCollection primitives)
    {
        var errors = new List<string>();

        foreach (var primitive in primitives.AllPrimitives())
        {
            var primitiveErrors = GetValidationErrors(primitive);
            if (primitiveErrors.Count > 0)
            {
                var filePath = GetRelativeFilePath(primitive);
                foreach (var error in primitiveErrors)
                    _warnings.Add($"{filePath}: {error}");
            }

            // Validate markdown links in content
            var content = GetContent(primitive);
            var primDir = Path.GetDirectoryName(GetFilePath(primitive)) ?? _baseDir;
            if (!string.IsNullOrEmpty(content))
            {
                var linkErrors = _linkResolver.ValidateLinkTargets(content, primDir);
                if (linkErrors.Count > 0)
                {
                    var filePath = GetRelativeFilePath(primitive);
                    foreach (var linkError in linkErrors)
                        _warnings.Add($"{filePath}: {linkError}");
                }
            }
        }

        return errors;
    }

    private TemplateData GenerateTemplateData(PrimitiveCollection primitives, CompilationConfig config)
    {
        var instructionsContent = _templateBuilder.BuildConditionalSections(primitives.Instructions);
        var version = VersionInfo.GetVersion();

        string? chatmodeContent = null;
        if (config.Chatmode is not null)
        {
            var chatmode = _templateBuilder.FindChatmodeByName(primitives.Chatmodes, config.Chatmode);
            if (chatmode is not null)
                chatmodeContent = chatmode.Content;
            else
                _warnings.Add($"Chatmode '{config.Chatmode}' not found");
        }

        return new TemplateData
        {
            InstructionsContent = instructionsContent,
            Version = version,
            ChatmodeContent = chatmodeContent,
        };
    }

    internal string GenerateOutput(TemplateData templateData, CompilationConfig config)
    {
        var content = _templateBuilder.GenerateAgentsMdTemplate(templateData);

        if (config.ResolveLinks)
            content = _linkResolver.ResolveMarkdownLinks(content, _baseDir);

        return content;
    }

    private void WriteOutputFile(string outputPath, string content)
    {
        try
        {
            File.WriteAllText(outputPath, content);
        }
        catch (IOException e)
        {
            _errors.Add($"Failed to write output file {outputPath}: {e.Message}");
        }
    }

    private void WriteDistributedFile(string agentsPath, string content, CompilationConfig config)
    {
        var finalContent = content;

        if (config.WithConstitution && _constitutionInjector is not null)
        {
            try
            {
                (finalContent, _, _) = _constitutionInjector.Inject(
                    content, withConstitution: true, outputPath: agentsPath);
            }
            catch (Exception)
            {
                // Use original content if injection fails
            }
        }

        var dir = Path.GetDirectoryName(agentsPath);
        if (dir is not null)
            Directory.CreateDirectory(dir);

        File.WriteAllText(agentsPath, finalContent);
    }

    private Dictionary<string, object> CompileStats(PrimitiveCollection primitives, TemplateData templateData)
    {
        return new Dictionary<string, object>
        {
            ["primitives_found"] = primitives.Count(),
            ["chatmodes"] = primitives.Chatmodes.Count,
            ["instructions"] = primitives.Instructions.Count,
            ["contexts"] = primitives.Contexts.Count,
            ["content_length"] = templateData.InstructionsContent.Length,
            ["version"] = templateData.Version,
        };
    }

    private static CompilationResult MergeResults(List<CompilationResult> results)
    {
        if (results.Count == 0)
            return new CompilationResult { Success = true };

        if (results.Count == 1)
            return results[0];

        var mergedWarnings = new List<string>();
        var mergedErrors = new List<string>();
        var mergedStats = new Dictionary<string, object>();
        var outputPaths = new List<string>();
        var contentParts = new List<string>();

        foreach (var result in results)
        {
            mergedWarnings.AddRange(result.Warnings);
            mergedErrors.AddRange(result.Errors);

            foreach (var (key, value) in result.Stats)
            {
                if (mergedStats.TryGetValue(key, out var existing)
                    && existing is IConvertible existingNum
                    && value is IConvertible valueNum)
                {
                    mergedStats[key] = Convert.ToDouble(existingNum) + Convert.ToDouble(valueNum);
                }
                else
                {
                    mergedStats[key] = value;
                }
            }

            if (!string.IsNullOrEmpty(result.OutputPath))
                outputPaths.Add(result.OutputPath);
            if (!string.IsNullOrEmpty(result.Content))
                contentParts.Add(result.Content);
        }

        return new CompilationResult
        {
            Success = results.TrueForAll(r => r.Success),
            OutputPath = string.Join(" | ", outputPaths),
            Content = string.Join($"{Environment.NewLine}{Environment.NewLine}---{Environment.NewLine}{Environment.NewLine}", contentParts),
            Warnings = mergedWarnings,
            Errors = mergedErrors,
            Stats = mergedStats,
        };
    }

    private string GeneratePlacementSummary(DistributedCompilationResult result)
    {
        var lines = new List<string> { "Distributed AGENTS.md Placement Summary:", "" };

        foreach (var placement in result.Placements)
        {
            var relPath = Path.GetRelativePath(_baseDir, placement.AgentsPath);
            lines.Add($"📄 {relPath}");
            lines.Add($"   Instructions: {placement.Instructions.Count}");
            lines.Add($"   Patterns: {string.Join(", ", placement.CoveragePatterns.Order())}");
            lines.Add("");
        }

        lines.Add($"Total AGENTS.md files: {result.Placements.Count}");
        return string.Join(Environment.NewLine, lines);
    }

    private string GenerateDistributedSummary(DistributedCompilationResult result, CompilationConfig config)
    {
        var lines = new List<string>
        {
            "# Distributed AGENTS.md Compilation Summary",
            "",
            $"Generated {result.Placements.Count} AGENTS.md files:",
            ""
        };

        foreach (var placement in result.Placements)
        {
            var relPath = Path.GetRelativePath(_baseDir, placement.AgentsPath);
            lines.Add($"- {relPath} ({placement.Instructions.Count} instructions)");
        }

        result.Stats.TryGetValue("total_instructions_placed", out var totalInst);
        result.Stats.TryGetValue("total_patterns_covered", out var totalPat);

        lines.AddRange([
            "",
            $"Total instructions: {totalInst ?? 0}",
            $"Total patterns: {totalPat ?? 0}",
            "",
            "Use 'apm compile --single-agents' for traditional single-file compilation."
        ]);

        return string.Join(Environment.NewLine, lines);
    }

    // ── Primitive accessors ─────────────────────────────────────────

    private string GetRelativeFilePath(object primitive)
    {
        var fp = GetFilePath(primitive);
        try { return Path.GetRelativePath(_baseDir, fp); }
        catch { return fp; }
    }

    private static string GetFilePath(object primitive) => primitive switch
    {
        Chatmode c => c.FilePath,
        Instruction i => i.FilePath,
        Context ctx => ctx.FilePath,
        Skill s => s.FilePath,
        _ => ""
    };

    private static string GetContent(object primitive) => primitive switch
    {
        Chatmode c => c.Content,
        Instruction i => i.Content,
        Context ctx => ctx.Content,
        Skill s => s.Content,
        _ => ""
    };

    private static List<string> GetValidationErrors(object primitive) => primitive switch
    {
        Chatmode c => c.Validate(),
        Instruction i => i.Validate(),
        Context ctx => ctx.Validate(),
        Skill s => s.Validate(),
        _ => []
    };

    // ── Convenience function ────────────────────────────────────────

    /// <summary>
    /// Generate AGENTS.md with conditional sections (backward-compatible convenience method).
    /// </summary>
    public static string CompileAgentsMd(
        PrimitiveCollection? primitives = null,
        string outputPath = "AGENTS.md",
        string? chatmode = null,
        bool dryRun = false,
        string baseDir = ".")
    {
        var config = new CompilationConfig
        {
            OutputPath = outputPath,
            Chatmode = chatmode,
            DryRun = dryRun,
            Strategy = "single-file",
        };

        var compiler = new AgentsCompiler(baseDir);
        var result = compiler.Compile(config, primitives);

        if (!result.Success)
            throw new InvalidOperationException($"Compilation failed: {string.Join("; ", result.Errors)}");

        return result.Content;
    }
}


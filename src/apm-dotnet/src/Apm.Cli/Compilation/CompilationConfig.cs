using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;

namespace Apm.Cli.Compilation;

/// <summary>Configuration for AGENTS.md compilation.</summary>
public class CompilationConfig
{
    public string OutputPath { get; set; } = "AGENTS.md";
    public string? Chatmode { get; set; }
    public bool ResolveLinks { get; set; } = true;
    public bool DryRun { get; set; }
    public bool WithConstitution { get; set; } = true;

    /// <summary>
    /// Compilation target: "vscode", "agents", "claude", or "all".
    /// </summary>
    public string Target { get; set; } = "all";

    /// <summary>Compilation strategy: "distributed" or "single-file".</summary>
    public string Strategy { get; set; } = "distributed";

    /// <summary>Force single-file mode.</summary>
    public bool SingleAgents { get; set; }

    /// <summary>Show source attribution and conflicts.</summary>
    public bool Trace { get; set; }

    /// <summary>Ignore dependencies, compile only local primitives.</summary>
    public bool LocalOnly { get; set; }

    /// <summary>Show context optimizer analysis and metrics.</summary>
    public bool Debug { get; set; }

    /// <summary>Minimum instructions per AGENTS.md file (Minimal Context Principle).</summary>
    public int MinInstructionsPerFile { get; set; } = 1;

    /// <summary>Include source file comments.</summary>
    public bool SourceAttribution { get; set; } = true;

    /// <summary>Remove orphaned AGENTS.md files.</summary>
    public bool CleanOrphaned { get; set; }

    /// <summary>Glob patterns for directories to exclude during compilation.</summary>
    public List<string> Exclude { get; set; } = [];

    /// <summary>Apply CLI flag precedence after initialization.</summary>
    public void ApplyFlagPrecedence()
    {
        if (SingleAgents)
            Strategy = "single-file";
    }

    /// <summary>
    /// Create configuration from apm.yml with command-line overrides.
    /// </summary>
    public static CompilationConfig FromApmYml(Dictionary<string, object?>? overrides = null)
    {
        var config = new CompilationConfig();

        try
        {
            var apmYmlPath = Path.Combine(Directory.GetCurrentDirectory(), "apm.yml");
            if (File.Exists(apmYmlPath))
            {
                var yamlContent = File.ReadAllText(apmYmlPath);
                var deserializer = new DeserializerBuilder()
                    .WithNamingConvention(UnderscoredNamingConvention.Instance)
                    .Build();
                var apmConfig = deserializer.Deserialize<Dictionary<string, object?>>(yamlContent);

                if (apmConfig?.TryGetValue("compilation", out var compilationObj) == true
                    && compilationObj is Dictionary<object, object> compilationDict)
                {
                    var compilation = compilationDict
                        .ToDictionary(k => k.Key.ToString()!, v => v.Value);

                    if (compilation.TryGetValue("output", out var output))
                        config.OutputPath = output?.ToString() ?? config.OutputPath;
                    if (compilation.TryGetValue("chatmode", out var chatmode))
                        config.Chatmode = chatmode?.ToString();
                    if (compilation.TryGetValue("resolve_links", out var resolveLinks))
                        config.ResolveLinks = Convert.ToBoolean(resolveLinks);
                    if (compilation.TryGetValue("target", out var target))
                        config.Target = target?.ToString() ?? config.Target;
                    if (compilation.TryGetValue("strategy", out var strategy))
                        config.Strategy = strategy?.ToString() ?? config.Strategy;
                    if (compilation.TryGetValue("source_attribution", out var sourceAttr))
                        config.SourceAttribution = Convert.ToBoolean(sourceAttr);

                    // Legacy single_file support
                    if (compilation.TryGetValue("single_file", out var singleFile)
                        && Convert.ToBoolean(singleFile))
                    {
                        config.Strategy = "single-file";
                        config.SingleAgents = true;
                    }

                    // Placement settings
                    if (compilation.TryGetValue("placement", out var placementObj)
                        && placementObj is Dictionary<object, object> placementDict)
                    {
                        if (placementDict.TryGetValue("min_instructions_per_file", out var minInst))
                            config.MinInstructionsPerFile = Convert.ToInt32(minInst);
                    }

                    // Exclude patterns
                    if (compilation.TryGetValue("exclude", out var excludeObj))
                    {
                        if (excludeObj is List<object> excludeList)
                            config.Exclude = excludeList.Select(e => e.ToString()!).ToList();
                        else if (excludeObj is string excludeStr)
                            config.Exclude = [excludeStr];
                    }
                }
            }
        }
        catch (Exception)
        {
            // If config loading fails, use defaults
        }

        // Apply command-line overrides (highest priority)
        if (overrides is not null)
        {
            foreach (var (key, value) in overrides)
            {
                if (value is null) continue;
                ApplyOverride(config, key, value);
            }
        }

        config.ApplyFlagPrecedence();
        return config;
    }

    private static void ApplyOverride(CompilationConfig config, string key, object value)
    {
        switch (key)
        {
            case "output_path": config.OutputPath = value.ToString()!; break;
            case "chatmode": config.Chatmode = value.ToString(); break;
            case "resolve_links": config.ResolveLinks = Convert.ToBoolean(value); break;
            case "dry_run": config.DryRun = Convert.ToBoolean(value); break;
            case "with_constitution": config.WithConstitution = Convert.ToBoolean(value); break;
            case "target": config.Target = value.ToString()!; break;
            case "strategy": config.Strategy = value.ToString()!; break;
            case "single_agents": config.SingleAgents = Convert.ToBoolean(value); break;
            case "trace": config.Trace = Convert.ToBoolean(value); break;
            case "local_only": config.LocalOnly = Convert.ToBoolean(value); break;
            case "debug": config.Debug = Convert.ToBoolean(value); break;
            case "min_instructions_per_file": config.MinInstructionsPerFile = Convert.ToInt32(value); break;
            case "source_attribution": config.SourceAttribution = Convert.ToBoolean(value); break;
            case "clean_orphaned": config.CleanOrphaned = Convert.ToBoolean(value); break;
            case "exclude":
                if (value is List<string> list) config.Exclude = list;
                break;
        }
    }
}

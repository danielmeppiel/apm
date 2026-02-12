using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;

namespace Apm.Cli.Models;

/// <summary>Represents an APM package with metadata.</summary>
public class ApmPackage
{
    [YamlMember(Alias = "name")]
    public string Name { get; set; } = "";

    [YamlMember(Alias = "version")]
    public string Version { get; set; } = "";

    [YamlMember(Alias = "description")]
    public string? Description { get; set; }

    [YamlMember(Alias = "author")]
    public string? Author { get; set; }

    [YamlMember(Alias = "license")]
    public string? License { get; set; }

    /// <summary>Source location (for dependencies).</summary>
    [YamlIgnore]
    public string? Source { get; set; }

    /// <summary>Resolved commit SHA (for dependencies).</summary>
    [YamlIgnore]
    public string? ResolvedCommit { get; set; }

    /// <summary>
    /// Dependencies by type. APM deps are stored as DependencyReference; other types as strings.
    /// </summary>
    [YamlIgnore]
    public Dictionary<string, List<object>>? Dependencies { get; set; }

    [YamlMember(Alias = "scripts")]
    public Dictionary<string, string>? Scripts { get; set; }

    /// <summary>Local path to the package directory.</summary>
    [YamlIgnore]
    public string? PackagePath { get; set; }

    /// <summary>Target agent: vscode, claude, or all.</summary>
    [YamlMember(Alias = "target")]
    public string? Target { get; set; }

    /// <summary>Package content type: instructions, skill, hybrid, or prompts.</summary>
    [YamlIgnore]
    public PackageContentType? Type { get; set; }

    /// <summary>Load APM package from apm.yml file.</summary>
    /// <exception cref="FileNotFoundException">If the file doesn't exist.</exception>
    /// <exception cref="ArgumentException">If the file is invalid or missing required fields.</exception>
    public static ApmPackage FromApmYml(string apmYmlPath)
    {
        if (!File.Exists(apmYmlPath))
            throw new FileNotFoundException($"apm.yml not found: {apmYmlPath}", apmYmlPath);

        string yamlContent;
        try
        {
            yamlContent = File.ReadAllText(apmYmlPath);
        }
        catch (Exception ex) when (ex is not FileNotFoundException)
        {
            throw new ArgumentException($"Failed to read {apmYmlPath}: {ex.Message}", ex);
        }

        Dictionary<string, object?> data;
        try
        {
            var deserializer = new DeserializerBuilder()
                .WithNamingConvention(UnderscoredNamingConvention.Instance)
                .Build();
            var raw = deserializer.Deserialize<Dictionary<string, object?>>(yamlContent);
            data = raw ?? throw new ArgumentException($"apm.yml must contain a YAML object");
        }
        catch (YamlDotNet.Core.YamlException ex)
        {
            throw new ArgumentException($"Invalid YAML format in {apmYmlPath}: {ex.Message}", ex);
        }

        if (!data.ContainsKey("name") || data["name"] == null)
            throw new ArgumentException("Missing required field 'name' in apm.yml");
        if (!data.ContainsKey("version") || data["version"] == null)
            throw new ArgumentException("Missing required field 'version' in apm.yml");

        // Parse dependencies
        Dictionary<string, List<object>>? dependencies = null;
        if (data.TryGetValue("dependencies", out var depsObj) && depsObj is Dictionary<object, object> depsDict)
        {
            dependencies = new Dictionary<string, List<object>>();
            foreach (var kvp in depsDict)
            {
                var depType = kvp.Key.ToString()!;
                if (kvp.Value is not List<object> depList) continue;

                if (depType == "apm")
                {
                    var parsed = new List<object>();
                    foreach (var item in depList)
                    {
                        var depStr = item.ToString();
                        if (string.IsNullOrEmpty(depStr)) continue;
                        try
                        {
                            parsed.Add(DependencyReference.Parse(depStr));
                        }
                        catch (Exception ex)
                        {
                            throw new ArgumentException($"Invalid APM dependency '{depStr}': {ex.Message}", ex);
                        }
                    }
                    dependencies[depType] = parsed;
                }
                else
                {
                    dependencies[depType] = depList
                        .Where(d => d is string)
                        .Select(d => (object)d.ToString()!)
                        .ToList();
                }
            }
        }

        // Parse package content type
        PackageContentType? pkgType = null;
        if (data.TryGetValue("type", out var typeVal) && typeVal != null)
        {
            var typeStr = typeVal.ToString();
            if (typeStr != null)
            {
                try
                {
                    pkgType = PackageContentTypeExtensions.FromString(typeStr);
                }
                catch (ArgumentException ex)
                {
                    throw new ArgumentException($"Invalid 'type' field in apm.yml: {ex.Message}", ex);
                }
            }
        }

        return new ApmPackage
        {
            Name = data["name"]!.ToString()!,
            Version = data["version"]!.ToString()!,
            Description = data.GetValueOrDefault("description")?.ToString(),
            Author = data.GetValueOrDefault("author")?.ToString(),
            License = data.GetValueOrDefault("license")?.ToString(),
            Dependencies = dependencies,
            Scripts = ExtractStringDict(data, "scripts"),
            PackagePath = Path.GetDirectoryName(Path.GetFullPath(apmYmlPath)),
            Target = data.GetValueOrDefault("target")?.ToString(),
            Type = pkgType,
        };
    }

    /// <summary>Get list of APM dependencies.</summary>
    public List<DependencyReference> GetApmDependencies()
    {
        if (Dependencies == null || !Dependencies.TryGetValue("apm", out var apmDeps))
            return [];
        return apmDeps.OfType<DependencyReference>().ToList();
    }

    /// <summary>Get list of MCP dependencies (as strings).</summary>
    public List<string> GetMcpDependencies()
    {
        if (Dependencies == null || !Dependencies.TryGetValue("mcp", out var mcpDeps))
            return [];
        return mcpDeps.Select(d => d.ToString()!).ToList();
    }

    /// <summary>Check if this package has APM dependencies.</summary>
    public bool HasApmDependencies() => GetApmDependencies().Count > 0;

    private static Dictionary<string, string>? ExtractStringDict(Dictionary<string, object?> data, string key)
    {
        if (!data.TryGetValue(key, out var val) || val is not Dictionary<object, object> dict)
            return null;
        var result = new Dictionary<string, string>();
        foreach (var kvp in dict)
        {
            var k = kvp.Key.ToString();
            var v = kvp.Value?.ToString();
            if (k != null && v != null)
                result[k] = v;
        }
        return result;
    }
}

/// <summary>Result of APM package validation.</summary>
public class ValidationResult
{
    public bool IsValid { get; set; } = true;
    public List<string> Errors { get; } = [];
    public List<string> Warnings { get; } = [];
    public ApmPackage? Package { get; set; }
    public PackageType? PackageTypeResult { get; set; }

    public void AddError(string error)
    {
        Errors.Add(error);
        IsValid = false;
    }

    public void AddWarning(string warning) => Warnings.Add(warning);

    public bool HasIssues() => Errors.Count > 0 || Warnings.Count > 0;

    public string Summary()
    {
        if (IsValid && Warnings.Count == 0)
            return "✅ Package is valid";
        if (IsValid)
            return $"⚠️ Package is valid with {Warnings.Count} warning(s)";
        return $"❌ Package is invalid with {Errors.Count} error(s)";
    }
}

using Apm.Cli.Models;
using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;

namespace Apm.Cli.Dependencies;

/// <summary>A resolved dependency with exact commit/version information.</summary>
public class LockedDependency
{
    public string RepoUrl { get; set; } = "";
    public string? Host { get; set; }
    public string? ResolvedCommit { get; set; }
    public string? ResolvedRef { get; set; }
    public string? Version { get; set; }
    public string? VirtualPath { get; set; }
    public bool IsVirtual { get; set; }
    public int Depth { get; set; } = 1;
    public string? ResolvedBy { get; set; }

    /// <summary>Returns unique key for this dependency.</summary>
    public string GetUniqueKey()
        => IsVirtual && !string.IsNullOrEmpty(VirtualPath)
            ? $"{RepoUrl}/{VirtualPath}"
            : RepoUrl;

    /// <summary>Serialize to dictionary for YAML output.</summary>
    public Dictionary<string, object> ToDict()
    {
        var result = new Dictionary<string, object> { ["repo_url"] = RepoUrl };
        if (Host != null) result["host"] = Host;
        if (ResolvedCommit != null) result["resolved_commit"] = ResolvedCommit;
        if (ResolvedRef != null) result["resolved_ref"] = ResolvedRef;
        if (Version != null) result["version"] = Version;
        if (VirtualPath != null) result["virtual_path"] = VirtualPath;
        if (IsVirtual) result["is_virtual"] = IsVirtual;
        if (Depth != 1) result["depth"] = Depth;
        if (ResolvedBy != null) result["resolved_by"] = ResolvedBy;
        return result;
    }

    /// <summary>Deserialize from dictionary.</summary>
    public static LockedDependency FromDict(Dictionary<object, object> data) => new()
    {
        RepoUrl = data.GetValueOrDefault("repo_url")?.ToString() ?? "",
        Host = data.GetValueOrDefault("host")?.ToString(),
        ResolvedCommit = data.GetValueOrDefault("resolved_commit")?.ToString(),
        ResolvedRef = data.GetValueOrDefault("resolved_ref")?.ToString(),
        Version = data.GetValueOrDefault("version")?.ToString(),
        VirtualPath = data.GetValueOrDefault("virtual_path")?.ToString(),
        IsVirtual = data.TryGetValue("is_virtual", out var iv) && iv is bool b ? b : false,
        Depth = data.TryGetValue("depth", out var d) ? Convert.ToInt32(d) : 1,
        ResolvedBy = data.GetValueOrDefault("resolved_by")?.ToString()
    };

    /// <summary>Create from a DependencyReference with resolution info.</summary>
    public static LockedDependency FromDependencyRef(
        DependencyReference depRef,
        string? resolvedCommit,
        int depth,
        string? resolvedBy) => new()
        {
            RepoUrl = depRef.RepoUrl,
            Host = depRef.Host,
            ResolvedCommit = resolvedCommit,
            ResolvedRef = depRef.Reference,
            VirtualPath = depRef.VirtualPath,
            IsVirtual = depRef.IsVirtual,
            Depth = depth,
            ResolvedBy = resolvedBy
        };
}

/// <summary>APM lock file for reproducible dependency resolution.</summary>
public class LockFile
{
    public string LockfileVersion { get; set; } = "1";
    public string GeneratedAt { get; set; } = DateTimeOffset.UtcNow.ToString("o");
    public string? ApmVersion { get; set; }
    public Dictionary<string, LockedDependency> Dependencies { get; set; } = new();

    public void AddDependency(LockedDependency dep)
        => Dependencies[dep.GetUniqueKey()] = dep;

    public LockedDependency? GetDependency(string key)
        => Dependencies.GetValueOrDefault(key);

    public bool HasDependency(string key) => Dependencies.ContainsKey(key);

    /// <summary>Get all dependencies sorted by depth then repo_url.</summary>
    public List<LockedDependency> GetAllDependencies()
        => Dependencies.Values
            .OrderBy(d => d.Depth)
            .ThenBy(d => d.RepoUrl)
            .ToList();

    /// <summary>Serialize to YAML string.</summary>
    public string ToYaml()
    {
        var data = new Dictionary<string, object>
        {
            ["lockfile_version"] = LockfileVersion,
            ["generated_at"] = GeneratedAt
        };
        if (ApmVersion != null)
            data["apm_version"] = ApmVersion;
        data["dependencies"] = GetAllDependencies().Select(d => d.ToDict()).ToList();

        var serializer = new SerializerBuilder()
            .WithNamingConvention(UnderscoredNamingConvention.Instance)
            .ConfigureDefaultValuesHandling(DefaultValuesHandling.OmitNull)
            .Build();
        return serializer.Serialize(data);
    }

    /// <summary>Deserialize from YAML string.</summary>
    public static LockFile FromYaml(string yamlStr)
    {
        var deserializer = new DeserializerBuilder()
            .WithNamingConvention(UnderscoredNamingConvention.Instance)
            .Build();
        var data = deserializer.Deserialize<Dictionary<string, object?>>(yamlStr);
        if (data == null)
            return new LockFile();

        var lockFile = new LockFile
        {
            LockfileVersion = data.GetValueOrDefault("lockfile_version")?.ToString() ?? "1",
            GeneratedAt = data.GetValueOrDefault("generated_at")?.ToString() ?? "",
            ApmVersion = data.GetValueOrDefault("apm_version")?.ToString()
        };

        if (data.GetValueOrDefault("dependencies") is List<object> depsList)
        {
            foreach (var item in depsList)
            {
                if (item is Dictionary<object, object> depData)
                    lockFile.AddDependency(LockedDependency.FromDict(depData));
            }
        }

        return lockFile;
    }

    /// <summary>Write lock file to disk.</summary>
    public void Write(string path) => File.WriteAllText(path, ToYaml());

    /// <summary>Read lock file from disk. Returns null if not exists or corrupt.</summary>
    public static LockFile? Read(string path)
    {
        if (!File.Exists(path)) return null;
        try
        {
            return FromYaml(File.ReadAllText(path));
        }
        catch
        {
            return null;
        }
    }

    /// <summary>Load existing lock file or create a new one.</summary>
    public static LockFile LoadOrCreate(string path) => Read(path) ?? new LockFile();

    /// <summary>Create a lock file from installed packages.</summary>
    /// <param name="installedPackages">Tuples of (depRef, resolvedCommit, depth, resolvedBy).</param>
    /// <param name="dependencyGraph">The resolved DependencyGraph for additional metadata.</param>
    public static LockFile FromInstalledPackages(
        List<(DependencyReference DepRef, string? ResolvedCommit, int Depth, string? ResolvedBy)> installedPackages,
        DependencyGraph dependencyGraph)
    {
        var lockFile = new LockFile
        {
            ApmVersion = typeof(LockFile).Assembly.GetName().Version?.ToString() ?? "unknown"
        };

        foreach (var (depRef, resolvedCommit, depth, resolvedBy) in installedPackages)
        {
            lockFile.AddDependency(LockedDependency.FromDependencyRef(
                depRef, resolvedCommit, depth, resolvedBy));
        }

        return lockFile;
    }

    /// <summary>Save lock file to disk (alias for Write).</summary>
    public void Save(string path) => Write(path);

    /// <summary>Get the path to the lock file for a project.</summary>
    public static string GetLockfilePath(string projectRoot) => Path.Combine(projectRoot, "apm.lock");
}

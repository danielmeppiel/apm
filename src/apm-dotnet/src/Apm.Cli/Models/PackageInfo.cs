namespace Apm.Cli.Models;

/// <summary>Represents a resolved Git reference.</summary>
public record ResolvedReference(
    string OriginalRef,
    GitReferenceType RefType,
    string ResolvedCommit,
    string RefName)
{
    public override string ToString() =>
        RefType == GitReferenceType.Commit
            ? ResolvedCommit[..Math.Min(8, ResolvedCommit.Length)]
            : $"{RefName} ({ResolvedCommit[..Math.Min(8, ResolvedCommit.Length)]})";
}

/// <summary>Information about a downloaded/installed package.</summary>
public record PackageInfo(
    ApmPackage Package,
    string InstallPath)
{
    public ResolvedReference? ResolvedReference { get; init; }
    public string? InstalledAt { get; init; }
    public DependencyReference? DependencyRef { get; init; }
    public PackageType? PackageTypeResult { get; init; }

    /// <summary>Get the canonical dependency string for this package.</summary>
    public string GetCanonicalDependencyString()
    {
        if (DependencyRef != null)
            return DependencyRef.GetCanonicalDependencyString();
        return Package.Source ?? Package.Name ?? "unknown";
    }

    /// <summary>Get path to the .apm directory for this package.</summary>
    public string GetPrimitivesPath() => Path.Combine(InstallPath, ".apm");

    /// <summary>Check if the package has any primitives.</summary>
    public bool HasPrimitives()
    {
        var apmDir = GetPrimitivesPath();
        if (!Directory.Exists(apmDir)) return false;

        foreach (var primitiveType in new[] { "instructions", "chatmodes", "contexts", "prompts" })
        {
            var dir = Path.Combine(apmDir, primitiveType);
            if (Directory.Exists(dir) && Directory.EnumerateFileSystemEntries(dir).Any())
                return true;
        }
        return false;
    }
}

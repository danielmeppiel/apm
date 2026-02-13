using Apm.Cli.Models;

namespace Apm.Cli.Dependencies;

/// <summary>Represents a single dependency node in the dependency graph.</summary>
public class DependencyNode
{
    public ApmPackage Package { get; set; } = new();
    public DependencyReference DependencyRef { get; set; } = null!;
    public int Depth { get; set; }
    public List<DependencyNode> Children { get; set; } = [];
    public DependencyNode? Parent { get; set; }

    /// <summary>Get unique identifier for this node.</summary>
    public string GetId()
    {
        var uniqueKey = DependencyRef.GetUniqueKey();
        return !string.IsNullOrEmpty(DependencyRef.Reference)
            ? $"{uniqueKey}#{DependencyRef.Reference}"
            : uniqueKey;
    }

    /// <summary>Get display name for this dependency.</summary>
    public string GetDisplayName() => DependencyRef.GetDisplayName();
}

/// <summary>Represents a circular dependency reference.</summary>
public class CircularRef
{
    /// <summary>List of repo URLs forming the cycle.</summary>
    public List<string> CyclePath { get; set; } = [];
    public int DetectedAtDepth { get; set; }

    private string FormatCompleteCycle()
    {
        if (CyclePath.Count == 0) return "(empty path)";
        var display = string.Join(" -> ", CyclePath);
        if (CyclePath.Count > 1 && CyclePath[0] != CyclePath[^1])
            display += $" -> {CyclePath[0]}";
        return display;
    }

    public override string ToString()
        => $"Circular dependency detected: {FormatCompleteCycle()}";
}

/// <summary>Hierarchical representation of dependencies before flattening.</summary>
public class DependencyTree
{
    public ApmPackage RootPackage { get; set; } = new();
    public Dictionary<string, DependencyNode> Nodes { get; set; } = new();
    public int MaxDepth { get; set; }

    public void AddNode(DependencyNode node)
    {
        Nodes[node.GetId()] = node;
        MaxDepth = Math.Max(MaxDepth, node.Depth);
    }

    public DependencyNode? GetNode(string uniqueKey)
        => Nodes.GetValueOrDefault(uniqueKey);

    public List<DependencyNode> GetNodesAtDepth(int depth)
        => Nodes.Values.Where(n => n.Depth == depth).ToList();

    /// <summary>Check if a dependency exists in the tree by repo URL.</summary>
    public bool HasDependency(string repoUrl)
        => Nodes.Values.Any(n => n.DependencyRef.RepoUrl == repoUrl);
}

/// <summary>Information about a dependency conflict.</summary>
public class ConflictInfo
{
    public string RepoUrl { get; set; } = "";
    /// <summary>The dependency that "wins".</summary>
    public DependencyReference Winner { get; set; } = null!;
    /// <summary>All conflicting dependencies.</summary>
    public List<DependencyReference> Conflicts { get; set; } = [];
    /// <summary>Explanation of why winner was chosen.</summary>
    public string Reason { get; set; } = "";

    public override string ToString()
    {
        var conflictRefs = string.Join(", ", Conflicts.Select(r => r.ToString()));
        return $"Conflict for {RepoUrl}: {Winner} wins over {conflictRefs} ({Reason})";
    }
}

/// <summary>Final flattened dependency mapping ready for installation.</summary>
public class FlatDependencyMap
{
    public Dictionary<string, DependencyReference> Dependencies { get; set; } = new();
    public List<ConflictInfo> Conflicts { get; set; } = [];
    /// <summary>Order for installation.</summary>
    public List<string> InstallOrder { get; set; } = [];

    /// <summary>Add a dependency to the flat map.</summary>
    public void AddDependency(DependencyReference depRef, bool isConflict = false)
    {
        var uniqueKey = depRef.GetUniqueKey();

        if (!Dependencies.ContainsKey(uniqueKey))
        {
            Dependencies[uniqueKey] = depRef;
            InstallOrder.Add(uniqueKey);
        }
        else if (isConflict)
        {
            var existingRef = Dependencies[uniqueKey];
            var existingConflict = Conflicts.FirstOrDefault(c => c.RepoUrl == depRef.RepoUrl);
            if (existingConflict != null)
            {
                existingConflict.Conflicts.Add(depRef);
            }
            else
            {
                Conflicts.Add(new ConflictInfo
                {
                    RepoUrl = depRef.RepoUrl,
                    Winner = existingRef,
                    Conflicts = [depRef],
                    Reason = "first declared dependency wins"
                });
            }
        }
    }

    public DependencyReference? GetDependency(string uniqueKey)
        => Dependencies.GetValueOrDefault(uniqueKey);

    public bool HasConflicts() => Conflicts.Count > 0;

    public int TotalDependencies() => Dependencies.Count;

    /// <summary>Get dependencies in installation order.</summary>
    public List<DependencyReference> GetInstallationList()
        => InstallOrder
            .Where(Dependencies.ContainsKey)
            .Select(key => Dependencies[key])
            .ToList();
}

/// <summary>Complete resolved dependency information.</summary>
public class DependencyGraph
{
    public ApmPackage RootPackage { get; set; } = new();
    public DependencyTree DependencyTree { get; set; } = new();
    public FlatDependencyMap FlattenedDependencies { get; set; } = new();
    public List<CircularRef> CircularDependencies { get; set; } = [];
    public List<string> ResolutionErrors { get; set; } = [];

    public bool HasCircularDependencies() => CircularDependencies.Count > 0;

    public bool HasConflicts() => FlattenedDependencies.HasConflicts();

    public bool HasErrors() => ResolutionErrors.Count > 0;

    /// <summary>Check if the dependency graph is valid (no circular deps or errors).</summary>
    public bool IsValid() => !HasCircularDependencies() && !HasErrors();

    /// <summary>Get a summary of the dependency resolution.</summary>
    public Dictionary<string, object> GetSummary() => new()
    {
        ["root_package"] = RootPackage.Name,
        ["total_dependencies"] = FlattenedDependencies.TotalDependencies(),
        ["max_depth"] = DependencyTree.MaxDepth,
        ["has_circular_dependencies"] = HasCircularDependencies(),
        ["circular_count"] = CircularDependencies.Count,
        ["has_conflicts"] = HasConflicts(),
        ["conflict_count"] = FlattenedDependencies.Conflicts.Count,
        ["has_errors"] = HasErrors(),
        ["error_count"] = ResolutionErrors.Count,
        ["is_valid"] = IsValid()
    };

    public void AddError(string error) => ResolutionErrors.Add(error);

    public void AddCircularDependency(CircularRef circularRef)
        => CircularDependencies.Add(circularRef);
}

using Apm.Cli.Models;

namespace Apm.Cli.Dependencies;

/// <summary>
/// Type alias for the download callback.
/// Takes a DependencyReference and apm_modules directory, returns the install path if successful.
/// </summary>
public delegate string? DownloadCallback(DependencyReference depRef, string apmModulesDir);

/// <summary>Handles recursive APM dependency resolution similar to NPM.</summary>
public class ApmDependencyResolver
{
    private readonly int _maxDepth;
    private string? _apmModulesDir;
    private string? _projectRoot;
    private readonly DownloadCallback? _downloadCallback;
    private readonly HashSet<string> _downloadedPackages = [];

    /// <summary>Resolution path tracking (for test compatibility).</summary>
    public List<string> ResolutionPath { get; } = [];

    /// <param name="maxDepth">Maximum depth for dependency resolution (default: 50).</param>
    /// <param name="apmModulesDir">Optional explicit apm_modules directory.</param>
    /// <param name="downloadCallback">Optional callback to download missing packages.</param>
    public ApmDependencyResolver(
        int maxDepth = 50,
        string? apmModulesDir = null,
        DownloadCallback? downloadCallback = null)
    {
        _maxDepth = maxDepth;
        _apmModulesDir = apmModulesDir;
        _downloadCallback = downloadCallback;
    }

    /// <summary>Resolve all APM dependencies recursively.</summary>
    public DependencyGraph ResolveDependencies(string projectRoot)
    {
        _projectRoot = projectRoot;
        _apmModulesDir ??= Path.Combine(projectRoot, "apm_modules");

        var apmYmlPath = Path.Combine(projectRoot, "apm.yml");
        if (!File.Exists(apmYmlPath))
        {
            var emptyPackage = new ApmPackage { Name = "unknown", Version = "0.0.0", PackagePath = projectRoot };
            return new DependencyGraph
            {
                RootPackage = emptyPackage,
                DependencyTree = new DependencyTree { RootPackage = emptyPackage },
                FlattenedDependencies = new FlatDependencyMap()
            };
        }

        ApmPackage rootPackage;
        try
        {
            rootPackage = ApmPackage.FromApmYml(apmYmlPath);
        }
        catch (Exception e) when (e is ArgumentException or FileNotFoundException)
        {
            var errorPackage = new ApmPackage { Name = "error", Version = "0.0.0", PackagePath = projectRoot };
            var graph = new DependencyGraph
            {
                RootPackage = errorPackage,
                DependencyTree = new DependencyTree { RootPackage = errorPackage },
                FlattenedDependencies = new FlatDependencyMap()
            };
            graph.AddError($"Failed to load root apm.yml: {e.Message}");
            return graph;
        }

        var dependencyTree = BuildDependencyTree(apmYmlPath);
        var circularDeps = DetectCircularDependencies(dependencyTree);
        var flattenedDeps = FlattenDependencies(dependencyTree);

        return new DependencyGraph
        {
            RootPackage = rootPackage,
            DependencyTree = dependencyTree,
            FlattenedDependencies = flattenedDeps,
            CircularDependencies = circularDeps
        };
    }

    /// <summary>
    /// Build complete tree of all dependencies and sub-dependencies using BFS.
    /// </summary>
    public DependencyTree BuildDependencyTree(string rootApmYml)
    {
        ApmPackage rootPackage;
        try
        {
            rootPackage = ApmPackage.FromApmYml(rootApmYml);
        }
        catch (Exception)
        {
            var emptyPackage = new ApmPackage { Name = "error", Version = "0.0.0" };
            return new DependencyTree { RootPackage = emptyPackage };
        }

        var tree = new DependencyTree { RootPackage = rootPackage };

        // Queue: (dependency_ref, depth, parent_node)
        var processingQueue = new Queue<(DependencyReference DepRef, int Depth, DependencyNode? Parent)>();
        var queuedKeys = new HashSet<string>();

        foreach (var depRef in rootPackage.GetApmDependencies())
        {
            processingQueue.Enqueue((depRef, 1, null));
            queuedKeys.Add(depRef.GetUniqueKey());
        }

        while (processingQueue.Count > 0)
        {
            var (depRef, depth, parentNode) = processingQueue.Dequeue();
            queuedKeys.Remove(depRef.GetUniqueKey());

            if (depth > _maxDepth)
                continue;

            var existingNode = tree.GetNode(depRef.GetUniqueKey());
            if (existingNode != null && existingNode.Depth <= depth)
            {
                if (parentNode != null && !parentNode.Children.Contains(existingNode))
                    parentNode.Children.Add(existingNode);
                continue;
            }

            var placeholderPackage = new ApmPackage
            {
                Name = depRef.GetDisplayName(),
                Version = "unknown",
                Source = depRef.RepoUrl
            };

            var node = new DependencyNode
            {
                Package = placeholderPackage,
                DependencyRef = depRef,
                Depth = depth,
                Parent = parentNode
            };

            tree.AddNode(node);

            if (parentNode != null)
                parentNode.Children.Add(node);

            try
            {
                var loadedPackage = TryLoadDependencyPackage(depRef);
                if (loadedPackage != null)
                {
                    node.Package = loadedPackage;

                    foreach (var subDep in loadedPackage.GetApmDependencies())
                    {
                        if (!queuedKeys.Contains(subDep.GetUniqueKey()))
                        {
                            processingQueue.Enqueue((subDep, depth + 1, node));
                            queuedKeys.Add(subDep.GetUniqueKey());
                        }
                    }
                }
            }
            catch (Exception)
            {
                // Could not load dependency package — expected for remote deps
            }
        }

        return tree;
    }

    /// <summary>Detect and report circular dependency chains using DFS.</summary>
    public List<CircularRef> DetectCircularDependencies(DependencyTree tree)
    {
        var circularDeps = new List<CircularRef>();
        var visited = new HashSet<string>();
        var currentPath = new List<string>();

        void DfsDetectCycles(DependencyNode node)
        {
            var nodeId = node.GetId();
            var uniqueKey = node.DependencyRef.GetUniqueKey();

            if (currentPath.Contains(uniqueKey))
            {
                var cycleStartIndex = currentPath.IndexOf(uniqueKey);
                var cyclePath = currentPath.Skip(cycleStartIndex).Append(uniqueKey).ToList();
                circularDeps.Add(new CircularRef
                {
                    CyclePath = cyclePath,
                    DetectedAtDepth = node.Depth
                });
                return;
            }

            visited.Add(nodeId);
            currentPath.Add(uniqueKey);

            foreach (var child in node.Children)
            {
                var childId = child.GetId();
                if (!visited.Contains(childId) || currentPath.Contains(child.DependencyRef.GetUniqueKey()))
                    DfsDetectCycles(child);
            }

            currentPath.RemoveAt(currentPath.Count - 1);
        }

        foreach (var rootDep in tree.GetNodesAtDepth(1))
        {
            if (!visited.Contains(rootDep.GetId()))
            {
                currentPath.Clear();
                DfsDetectCycles(rootDep);
            }
        }

        return circularDeps;
    }

    /// <summary>Flatten tree to avoid duplicate installations (NPM hoisting).</summary>
    public FlatDependencyMap FlattenDependencies(DependencyTree tree)
    {
        var flatMap = new FlatDependencyMap();
        var seenKeys = new HashSet<string>();

        for (var depth = 1; depth <= tree.MaxDepth; depth++)
        {
            var nodesAtDepth = tree.GetNodesAtDepth(depth);
            nodesAtDepth.Sort((a, b) => string.Compare(a.GetId(), b.GetId(), StringComparison.Ordinal));

            foreach (var node in nodesAtDepth)
            {
                var uniqueKey = node.DependencyRef.GetUniqueKey();
                if (!seenKeys.Contains(uniqueKey))
                {
                    flatMap.AddDependency(node.DependencyRef, isConflict: false);
                    seenKeys.Add(uniqueKey);
                }
                else
                {
                    flatMap.AddDependency(node.DependencyRef, isConflict: true);
                }
            }
        }

        return flatMap;
    }

    /// <summary>Try to load a dependency package from apm_modules/.</summary>
    private ApmPackage? TryLoadDependencyPackage(DependencyReference depRef)
    {
        if (_apmModulesDir == null)
            return null;

        var installPath = depRef.GetInstallPath(_apmModulesDir);

        if (!Directory.Exists(installPath))
        {
            if (_downloadCallback != null)
            {
                var uniqueKey = depRef.GetUniqueKey();
                if (!_downloadedPackages.Contains(uniqueKey))
                {
                    try
                    {
                        var downloadedPath = _downloadCallback(depRef, _apmModulesDir);
                        if (downloadedPath != null && Directory.Exists(downloadedPath))
                        {
                            _downloadedPackages.Add(uniqueKey);
                            installPath = downloadedPath;
                        }
                    }
                    catch
                    {
                        // Download failed — continue without sub-deps
                    }
                }
            }

            if (!Directory.Exists(installPath))
                return null;
        }

        var apmYmlPath = Path.Combine(installPath, "apm.yml");
        if (!File.Exists(apmYmlPath))
        {
            var skillMdPath = Path.Combine(installPath, "SKILL.md");
            if (File.Exists(skillMdPath))
            {
                return new ApmPackage
                {
                    Name = depRef.GetDisplayName(),
                    Version = "1.0.0",
                    Source = depRef.RepoUrl,
                    PackagePath = installPath
                };
            }
            return null;
        }

        try
        {
            var package = ApmPackage.FromApmYml(apmYmlPath);
            if (string.IsNullOrEmpty(package.Source))
                package.Source = depRef.RepoUrl;
            return package;
        }
        catch
        {
            return null;
        }
    }

    /// <summary>Create a human-readable summary of the resolution results.</summary>
    public string CreateResolutionSummary(DependencyGraph graph)
    {
        var summary = graph.GetSummary();
        var lines = new List<string>
        {
            "Dependency Resolution Summary:",
            $"  Root package: {summary["root_package"]}",
            $"  Total dependencies: {summary["total_dependencies"]}",
            $"  Maximum depth: {summary["max_depth"]}"
        };

        if ((bool)summary["has_conflicts"])
            lines.Add($"  Conflicts detected: {summary["conflict_count"]}");
        if ((bool)summary["has_circular_dependencies"])
            lines.Add($"  Circular dependencies: {summary["circular_count"]}");
        if ((bool)summary["has_errors"])
            lines.Add($"  Resolution errors: {summary["error_count"]}");

        lines.Add($"  Status: {((bool)summary["is_valid"] ? "✅ Valid" : "❌ Invalid")}");

        return string.Join("\n", lines);
    }
}

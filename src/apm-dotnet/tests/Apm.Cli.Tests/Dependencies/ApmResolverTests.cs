using Apm.Cli.Dependencies;
using Apm.Cli.Models;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Dependencies;

public class ApmResolverTests : IDisposable
{
    private readonly string _tempDir;

    public ApmResolverTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void ResolveDependencies_ReturnsEmptyGraph_WhenNoApmYml()
    {
        var resolver = new ApmDependencyResolver();

        var result = resolver.ResolveDependencies(_tempDir);

        result.Should().NotBeNull();
        result.RootPackage.Name.Should().Be("unknown");
        result.RootPackage.Version.Should().Be("0.0.0");
        result.FlattenedDependencies.TotalDependencies().Should().Be(0);
        result.HasCircularDependencies().Should().BeFalse();
        result.HasConflicts().Should().BeFalse();
    }

    [Fact]
    public void ResolveDependencies_ReturnsError_WhenInvalidApmYml()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), "invalid: yaml: content: [");

        var resolver = new ApmDependencyResolver();
        var result = resolver.ResolveDependencies(_tempDir);

        result.RootPackage.Name.Should().Be("error");
        result.HasErrors().Should().BeTrue();
        result.ResolutionErrors[0].Should().Contain("Failed to load root apm.yml");
    }

    [Fact]
    public void ResolveDependencies_ResolvesValidPackage_WithNoDeps()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), """
            name: test-package
            version: 1.0.0
            description: A test package
            """);

        var resolver = new ApmDependencyResolver();
        var result = resolver.ResolveDependencies(_tempDir);

        result.RootPackage.Name.Should().Be("test-package");
        result.RootPackage.Version.Should().Be("1.0.0");
        result.FlattenedDependencies.TotalDependencies().Should().Be(0);
        result.IsValid().Should().BeTrue();
    }

    [Fact]
    public void ResolveDependencies_ResolvesPackage_WithApmDeps()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), """
            name: test-package
            version: 1.0.0
            dependencies:
              apm:
                - user/repo1
                - user/repo2#v1.0.0
            """);

        var resolver = new ApmDependencyResolver();
        var result = resolver.ResolveDependencies(_tempDir);

        result.RootPackage.Name.Should().Be("test-package");
        result.FlattenedDependencies.TotalDependencies().Should().Be(2);
        result.FlattenedDependencies.Dependencies.Should().ContainKey("user/repo1");
        result.FlattenedDependencies.Dependencies.Should().ContainKey("user/repo2");
    }

    [Fact]
    public void BuildDependencyTree_ReturnsEmptyTree_ForPackageWithNoDeps()
    {
        var apmYml = Path.Combine(_tempDir, "apm.yml");
        File.WriteAllText(apmYml, """
            name: empty-package
            version: 1.0.0
            """);

        var resolver = new ApmDependencyResolver();
        var tree = resolver.BuildDependencyTree(apmYml);

        tree.RootPackage.Name.Should().Be("empty-package");
        tree.Nodes.Should().BeEmpty();
        tree.MaxDepth.Should().Be(0);
    }

    [Fact]
    public void BuildDependencyTree_BuildsTree_WithDependencies()
    {
        var apmYml = Path.Combine(_tempDir, "apm.yml");
        File.WriteAllText(apmYml, """
            name: parent-package
            version: 1.0.0
            dependencies:
              apm:
                - user/dependency1
                - user/dependency2#v1.2.0
            """);

        var resolver = new ApmDependencyResolver();
        var tree = resolver.BuildDependencyTree(apmYml);

        tree.RootPackage.Name.Should().Be("parent-package");
        tree.Nodes.Should().HaveCount(2);
        tree.MaxDepth.Should().Be(1);
        tree.HasDependency("user/dependency1").Should().BeTrue();
        tree.HasDependency("user/dependency2").Should().BeTrue();
        tree.GetNodesAtDepth(1).Should().HaveCount(2);
    }

    [Fact]
    public void BuildDependencyTree_ReturnsErrorTree_ForInvalidYml()
    {
        var apmYml = Path.Combine(_tempDir, "apm.yml");
        File.WriteAllText(apmYml, "invalid yaml content [");

        var resolver = new ApmDependencyResolver();
        var tree = resolver.BuildDependencyTree(apmYml);

        tree.RootPackage.Name.Should().Be("error");
        tree.Nodes.Should().BeEmpty();
    }

    [Fact]
    public void BuildDependencyTree_ResolvesSubDeps_WhenPackagesExistLocally()
    {
        // Set up apm_modules directory with a dependency that has its own deps
        var apmModules = Path.Combine(_tempDir, "apm_modules");
        var dep1Dir = Path.Combine(apmModules, "user", "dep1");
        Directory.CreateDirectory(dep1Dir);
        File.WriteAllText(Path.Combine(dep1Dir, "apm.yml"), """
            name: dep1
            version: 1.0.0
            dependencies:
              apm:
                - user/sub-dep1
            """);

        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), """
            name: root-package
            version: 1.0.0
            dependencies:
              apm:
                - user/dep1
            """);

        var resolver = new ApmDependencyResolver(apmModulesDir: apmModules);
        var tree = resolver.BuildDependencyTree(Path.Combine(_tempDir, "apm.yml"));

        tree.RootPackage.Name.Should().Be("root-package");
        tree.HasDependency("user/dep1").Should().BeTrue();
        tree.HasDependency("user/sub-dep1").Should().BeTrue();
        tree.MaxDepth.Should().Be(2);
    }

    [Fact]
    public void MaxDepth_LimitsTreeDepth()
    {
        var apmYml = Path.Combine(_tempDir, "apm.yml");
        File.WriteAllText(apmYml, """
            name: deep-package
            version: 1.0.0
            dependencies:
              apm:
                - user/level1
            """);

        var resolver = new ApmDependencyResolver(maxDepth: 2);
        var tree = resolver.BuildDependencyTree(apmYml);

        tree.MaxDepth.Should().BeLessThanOrEqualTo(2);
    }

    [Fact]
    public void DetectCircularDependencies_ReturnsEmpty_WhenNoCycles()
    {
        var tree = new DependencyTree
        {
            RootPackage = new ApmPackage { Name = "root", Version = "1.0.0" }
        };
        var node1 = new DependencyNode
        {
            Package = new ApmPackage { Name = "dep1", Version = "1.0.0" },
            DependencyRef = DependencyReference.Parse("user/dep1"),
            Depth = 1
        };
        var node2 = new DependencyNode
        {
            Package = new ApmPackage { Name = "dep2", Version = "1.0.0" },
            DependencyRef = DependencyReference.Parse("user/dep2"),
            Depth = 1
        };
        tree.AddNode(node1);
        tree.AddNode(node2);

        var resolver = new ApmDependencyResolver();
        var circular = resolver.DetectCircularDependencies(tree);

        circular.Should().BeEmpty();
    }

    [Fact]
    public void DetectCircularDependencies_DetectsCycle()
    {
        var tree = new DependencyTree
        {
            RootPackage = new ApmPackage { Name = "root", Version = "1.0.0" }
        };

        var depA = DependencyReference.Parse("user/package-a");
        var depB = DependencyReference.Parse("user/package-b");

        var nodeA = new DependencyNode
        {
            Package = new ApmPackage { Name = "package-a", Version = "1.0.0" },
            DependencyRef = depA,
            Depth = 1
        };
        var nodeB = new DependencyNode
        {
            Package = new ApmPackage { Name = "package-b", Version = "1.0.0" },
            DependencyRef = depB,
            Depth = 2,
            Parent = nodeA
        };

        // Create cycle: A -> B -> A
        nodeA.Children.Add(nodeB);
        nodeB.Children.Add(nodeA);

        tree.AddNode(nodeA);
        tree.AddNode(nodeB);

        var resolver = new ApmDependencyResolver();
        var circular = resolver.DetectCircularDependencies(tree);

        circular.Should().HaveCount(1);
        circular[0].Should().BeOfType<CircularRef>();
    }

    [Fact]
    public void FlattenDependencies_FlattensWithoutConflicts()
    {
        var tree = new DependencyTree
        {
            RootPackage = new ApmPackage { Name = "root", Version = "1.0.0" }
        };
        var deps = new (string Repo, int Depth)[]
        {
            ("user/dep1", 1),
            ("user/dep2", 1),
            ("user/dep3", 2)
        };

        foreach (var (repo, depth) in deps)
        {
            tree.AddNode(new DependencyNode
            {
                Package = new ApmPackage { Name = repo.Split('/')[1], Version = "1.0.0" },
                DependencyRef = DependencyReference.Parse(repo),
                Depth = depth
            });
        }

        var resolver = new ApmDependencyResolver();
        var flat = resolver.FlattenDependencies(tree);

        flat.TotalDependencies().Should().Be(3);
        flat.HasConflicts().Should().BeFalse();
        flat.InstallOrder.Should().HaveCount(3);
    }

    [Fact]
    public void FlattenDependencies_DetectsConflicts()
    {
        var tree = new DependencyTree
        {
            RootPackage = new ApmPackage { Name = "root", Version = "1.0.0" }
        };
        tree.AddNode(new DependencyNode
        {
            Package = new ApmPackage { Name = "shared-lib", Version = "1.0.0" },
            DependencyRef = DependencyReference.Parse("user/shared-lib#v1.0.0"),
            Depth = 1
        });
        tree.AddNode(new DependencyNode
        {
            Package = new ApmPackage { Name = "shared-lib", Version = "2.0.0" },
            DependencyRef = DependencyReference.Parse("user/shared-lib#v2.0.0"),
            Depth = 2
        });

        var resolver = new ApmDependencyResolver();
        var flat = resolver.FlattenDependencies(tree);

        flat.TotalDependencies().Should().Be(1);
        flat.HasConflicts().Should().BeTrue();
        flat.Conflicts.Should().HaveCount(1);
        flat.Conflicts[0].RepoUrl.Should().Be("user/shared-lib");
    }

    [Fact]
    public void CreateResolutionSummary_FormatsCorrectly()
    {
        var graph = new DependencyGraph
        {
            RootPackage = new ApmPackage { Name = "test-package", Version = "1.0.0" }
        };
        graph.FlattenedDependencies.AddDependency(DependencyReference.Parse("user/dep1"));

        var resolver = new ApmDependencyResolver();
        var summary = resolver.CreateResolutionSummary(graph);

        summary.Should().Contain("test-package");
        summary.Should().Contain("Total dependencies: 1");
        summary.Should().Contain("✅ Valid");
    }

    [Fact]
    public void ResolveDependencies_WithDownloadCallback_InvokesCallback()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), """
            name: test-package
            version: 1.0.0
            dependencies:
              apm:
                - user/remote-dep
            """);

        var apmModules = Path.Combine(_tempDir, "apm_modules");
        Directory.CreateDirectory(apmModules);

        // Create the callback that simulates downloading a package
        var callbackInvoked = false;
        string? DownloadCallback(DependencyReference depRef, string modulesDir)
        {
            callbackInvoked = true;
            var installPath = depRef.GetInstallPath(modulesDir);
            Directory.CreateDirectory(installPath);
            File.WriteAllText(Path.Combine(installPath, "apm.yml"), """
                name: remote-dep
                version: 1.0.0
                """);
            return installPath;
        }

        var resolver = new ApmDependencyResolver(
            apmModulesDir: apmModules,
            downloadCallback: DownloadCallback);

        var result = resolver.ResolveDependencies(_tempDir);

        callbackInvoked.Should().BeTrue();
        result.FlattenedDependencies.Dependencies.Should().ContainKey("user/remote-dep");
    }

    [Fact]
    public void Constructor_InitializesResolutionPathEmpty()
    {
        var resolver = new ApmDependencyResolver();

        resolver.ResolutionPath.Should().BeEmpty();
    }

    [Fact]
    public void DiamondDependencies_DeduplicatesSharedTransitiveDep()
    {
        // Diamond: root → depB, root → depC, depB → depD, depC → depD
        var apmModules = Path.Combine(_tempDir, "apm_modules");

        var depBDir = Path.Combine(apmModules, "user", "depB");
        var depCDir = Path.Combine(apmModules, "user", "depC");
        Directory.CreateDirectory(depBDir);
        Directory.CreateDirectory(depCDir);

        File.WriteAllText(Path.Combine(depBDir, "apm.yml"), """
            name: depB
            version: 1.0.0
            dependencies:
              apm:
                - user/depD
            """);
        File.WriteAllText(Path.Combine(depCDir, "apm.yml"), """
            name: depC
            version: 1.0.0
            dependencies:
              apm:
                - user/depD
            """);

        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), """
            name: root-package
            version: 1.0.0
            dependencies:
              apm:
                - user/depB
                - user/depC
            """);

        var resolver = new ApmDependencyResolver(apmModulesDir: apmModules);
        var result = resolver.ResolveDependencies(_tempDir);

        result.FlattenedDependencies.Dependencies.Should().ContainKey("user/depB");
        result.FlattenedDependencies.Dependencies.Should().ContainKey("user/depC");
        result.FlattenedDependencies.Dependencies.Should().ContainKey("user/depD");
        // depD should appear exactly once in the flattened map despite two parents
        result.FlattenedDependencies.TotalDependencies().Should().Be(3);
        result.FlattenedDependencies.HasConflicts().Should().BeFalse();
    }

    [Fact]
    public void MissingPackages_StillTrackedAsPlaceholders_WhenNoCallback()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), """
            name: test-package
            version: 1.0.0
            dependencies:
              apm:
                - user/missing-dep
            """);

        var apmModules = Path.Combine(_tempDir, "apm_modules");
        Directory.CreateDirectory(apmModules);

        // No download callback and dep directory doesn't exist
        var resolver = new ApmDependencyResolver(apmModulesDir: apmModules);
        var result = resolver.ResolveDependencies(_tempDir);

        // The dependency should still appear in the graph as a placeholder
        result.FlattenedDependencies.Dependencies.Should().ContainKey("user/missing-dep");
        result.FlattenedDependencies.TotalDependencies().Should().Be(1);
        // Placeholder should have version "unknown"
        var tree = result.DependencyTree;
        tree.HasDependency("user/missing-dep").Should().BeTrue();
        var node = tree.GetNode("user/missing-dep");
        node!.Package.Version.Should().Be("unknown");
    }
}

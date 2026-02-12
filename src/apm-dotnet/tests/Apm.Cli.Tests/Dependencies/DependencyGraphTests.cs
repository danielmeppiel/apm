using Apm.Cli.Dependencies;
using Apm.Cli.Models;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Dependencies;

public class DependencyNodeTests
{
    [Fact]
    public void GetId_ReturnsUniqueKey_WhenNoReference()
    {
        var depRef = DependencyReference.Parse("user/repo");
        var node = new DependencyNode { DependencyRef = depRef, Depth = 1 };

        node.GetId().Should().Be("user/repo");
    }

    [Fact]
    public void GetId_IncludesReference_WhenReferenceIsSet()
    {
        var depRef = DependencyReference.Parse("user/repo#v1.0.0");
        var node = new DependencyNode { DependencyRef = depRef, Depth = 1 };

        node.GetId().Should().Be("user/repo#v1.0.0");
    }

    [Fact]
    public void GetDisplayName_ReturnsRepoUrl()
    {
        var depRef = DependencyReference.Parse("user/repo");
        var node = new DependencyNode { DependencyRef = depRef, Depth = 1 };

        node.GetDisplayName().Should().Be("user/repo");
    }

    [Fact]
    public void Children_DefaultsToEmptyList()
    {
        var node = new DependencyNode { DependencyRef = DependencyReference.Parse("user/repo") };
        node.Children.Should().BeEmpty();
    }

    [Fact]
    public void Parent_DefaultsToNull()
    {
        var node = new DependencyNode { DependencyRef = DependencyReference.Parse("user/repo") };
        node.Parent.Should().BeNull();
    }
}

public class CircularRefTests
{
    [Fact]
    public void ToString_FormatsCompleteCycle()
    {
        var circularRef = new CircularRef
        {
            CyclePath = ["user/a", "user/b", "user/a"],
            DetectedAtDepth = 3
        };

        var str = circularRef.ToString();
        str.Should().Contain("Circular dependency detected");
        str.Should().Contain("user/a -> user/b -> user/a");
    }

    [Fact]
    public void ToString_AppendsFirstElement_WhenCycleNotClosed()
    {
        var circularRef = new CircularRef
        {
            CyclePath = ["user/a", "user/b"],
            DetectedAtDepth = 2
        };

        var str = circularRef.ToString();
        str.Should().Contain("user/a -> user/b -> user/a");
    }

    [Fact]
    public void ToString_HandlesEmptyPath()
    {
        var circularRef = new CircularRef { CyclePath = [], DetectedAtDepth = 0 };

        circularRef.ToString().Should().Contain("(empty path)");
    }
}

public class DependencyTreeTests
{
    [Fact]
    public void AddNode_StoresNodeAndUpdatesMaxDepth()
    {
        var tree = new DependencyTree();
        var depRef = DependencyReference.Parse("user/test");
        var node = new DependencyNode
        {
            Package = new ApmPackage { Name = "test", Version = "1.0.0" },
            DependencyRef = depRef,
            Depth = 1
        };

        tree.AddNode(node);

        tree.MaxDepth.Should().Be(1);
        tree.GetNode("user/test").Should().Be(node);
    }

    [Fact]
    public void AddNode_TracksMaxDepth_AcrossMultipleNodes()
    {
        var tree = new DependencyTree();
        var node1 = new DependencyNode
        {
            DependencyRef = DependencyReference.Parse("user/dep1"),
            Depth = 1
        };
        var node2 = new DependencyNode
        {
            DependencyRef = DependencyReference.Parse("user/dep2"),
            Depth = 3
        };

        tree.AddNode(node1);
        tree.AddNode(node2);

        tree.MaxDepth.Should().Be(3);
    }

    [Fact]
    public void GetNode_ReturnsNull_WhenNotFound()
    {
        var tree = new DependencyTree();
        tree.GetNode("nonexistent").Should().BeNull();
    }

    [Fact]
    public void GetNodesAtDepth_ReturnsCorrectNodes()
    {
        var tree = new DependencyTree();
        var node1 = new DependencyNode
        {
            DependencyRef = DependencyReference.Parse("user/dep1"),
            Depth = 1
        };
        var node2 = new DependencyNode
        {
            DependencyRef = DependencyReference.Parse("user/dep2"),
            Depth = 1
        };
        var node3 = new DependencyNode
        {
            DependencyRef = DependencyReference.Parse("user/dep3"),
            Depth = 2
        };

        tree.AddNode(node1);
        tree.AddNode(node2);
        tree.AddNode(node3);

        tree.GetNodesAtDepth(1).Should().HaveCount(2);
        tree.GetNodesAtDepth(2).Should().HaveCount(1);
        tree.GetNodesAtDepth(3).Should().BeEmpty();
    }

    [Fact]
    public void HasDependency_ReturnsTrueForExistingDep()
    {
        var tree = new DependencyTree();
        var node = new DependencyNode
        {
            DependencyRef = DependencyReference.Parse("user/test"),
            Depth = 1
        };
        tree.AddNode(node);

        tree.HasDependency("user/test").Should().BeTrue();
        tree.HasDependency("user/other").Should().BeFalse();
    }
}

public class FlatDependencyMapTests
{
    [Fact]
    public void AddDependency_AddsNewDependency()
    {
        var flatMap = new FlatDependencyMap();
        var dep = DependencyReference.Parse("user/dep1");

        flatMap.AddDependency(dep);

        flatMap.TotalDependencies().Should().Be(1);
        flatMap.GetDependency("user/dep1").Should().NotBeNull();
        flatMap.InstallOrder.Should().Contain("user/dep1");
    }

    [Fact]
    public void AddDependency_IgnoresDuplicate_WhenNotConflict()
    {
        var flatMap = new FlatDependencyMap();
        var dep1 = DependencyReference.Parse("user/dep1");
        var dep2 = DependencyReference.Parse("user/dep1");

        flatMap.AddDependency(dep1);
        flatMap.AddDependency(dep2);

        flatMap.TotalDependencies().Should().Be(1);
        flatMap.HasConflicts().Should().BeFalse();
    }

    [Fact]
    public void AddDependency_RecordsConflict_WhenFlagged()
    {
        var flatMap = new FlatDependencyMap();
        var dep1 = DependencyReference.Parse("user/shared#v1.0.0");
        var dep2 = DependencyReference.Parse("user/shared#v2.0.0");

        flatMap.AddDependency(dep1);
        flatMap.AddDependency(dep2, isConflict: true);

        flatMap.TotalDependencies().Should().Be(1);
        flatMap.HasConflicts().Should().BeTrue();
        flatMap.Conflicts.Should().HaveCount(1);

        var conflict = flatMap.Conflicts[0];
        conflict.RepoUrl.Should().Be("user/shared");
        conflict.Winner.Should().Be(dep1);
        conflict.Conflicts.Should().Contain(dep2);
        conflict.Reason.Should().Be("first declared dependency wins");
    }

    [Fact]
    public void AddDependency_AccumulatesConflicts_ForSameRepo()
    {
        var flatMap = new FlatDependencyMap();
        var dep1 = DependencyReference.Parse("user/shared#v1.0.0");
        var dep2 = DependencyReference.Parse("user/shared#v2.0.0");
        var dep3 = DependencyReference.Parse("user/shared#v3.0.0");

        flatMap.AddDependency(dep1);
        flatMap.AddDependency(dep2, isConflict: true);
        flatMap.AddDependency(dep3, isConflict: true);

        flatMap.Conflicts.Should().HaveCount(1);
        flatMap.Conflicts[0].Conflicts.Should().HaveCount(2);
    }

    [Fact]
    public void GetInstallationList_ReturnsInOrder()
    {
        var flatMap = new FlatDependencyMap();
        var dep1 = DependencyReference.Parse("user/dep1");
        var dep2 = DependencyReference.Parse("user/dep2");

        flatMap.AddDependency(dep1);
        flatMap.AddDependency(dep2);

        var list = flatMap.GetInstallationList();
        list.Should().HaveCount(2);
        list[0].RepoUrl.Should().Be("user/dep1");
        list[1].RepoUrl.Should().Be("user/dep2");
    }

    [Fact]
    public void GetDependency_ReturnsNull_WhenNotFound()
    {
        var flatMap = new FlatDependencyMap();
        flatMap.GetDependency("nonexistent").Should().BeNull();
    }
}

public class ConflictInfoTests
{
    [Fact]
    public void ToString_FormatsConflictDescription()
    {
        var winner = DependencyReference.Parse("user/shared#v1.0.0");
        var loser = DependencyReference.Parse("user/shared#v2.0.0");
        var conflict = new ConflictInfo
        {
            RepoUrl = "user/shared",
            Winner = winner,
            Conflicts = [loser],
            Reason = "first declared dependency wins"
        };

        var str = conflict.ToString();
        str.Should().Contain("user/shared");
        str.Should().Contain("first declared dependency wins");
    }
}

public class DependencyGraphObjectTests
{
    [Fact]
    public void IsValid_ReturnsTrue_WhenNoErrorsOrCircularDeps()
    {
        var graph = new DependencyGraph
        {
            RootPackage = new ApmPackage { Name = "test", Version = "1.0.0" }
        };

        graph.IsValid().Should().BeTrue();
        graph.HasCircularDependencies().Should().BeFalse();
        graph.HasErrors().Should().BeFalse();
    }

    [Fact]
    public void IsValid_ReturnsFalse_WhenHasErrors()
    {
        var graph = new DependencyGraph();
        graph.AddError("something went wrong");

        graph.IsValid().Should().BeFalse();
        graph.HasErrors().Should().BeTrue();
    }

    [Fact]
    public void IsValid_ReturnsFalse_WhenHasCircularDeps()
    {
        var graph = new DependencyGraph();
        graph.AddCircularDependency(new CircularRef
        {
            CyclePath = ["a", "b", "a"],
            DetectedAtDepth = 2
        });

        graph.IsValid().Should().BeFalse();
        graph.HasCircularDependencies().Should().BeTrue();
    }

    [Fact]
    public void HasConflicts_DelegatesToFlattenedDependencies()
    {
        var graph = new DependencyGraph();
        var dep1 = DependencyReference.Parse("user/shared#v1.0.0");
        var dep2 = DependencyReference.Parse("user/shared#v2.0.0");

        graph.FlattenedDependencies.AddDependency(dep1);
        graph.FlattenedDependencies.AddDependency(dep2, isConflict: true);

        graph.HasConflicts().Should().BeTrue();
    }

    [Fact]
    public void GetSummary_ReturnsCorrectValues()
    {
        var graph = new DependencyGraph
        {
            RootPackage = new ApmPackage { Name = "test-package", Version = "1.0.0" }
        };
        graph.DependencyTree.MaxDepth = 2;
        graph.FlattenedDependencies.AddDependency(DependencyReference.Parse("user/dep1"));

        var summary = graph.GetSummary();

        summary["root_package"].Should().Be("test-package");
        summary["total_dependencies"].Should().Be(1);
        summary["max_depth"].Should().Be(2);
        summary["has_circular_dependencies"].Should().Be(false);
        summary["has_conflicts"].Should().Be(false);
        summary["has_errors"].Should().Be(false);
        summary["is_valid"].Should().Be(true);
    }

    [Fact]
    public void GetSummary_IncludesErrorAndCircularCounts()
    {
        var graph = new DependencyGraph
        {
            RootPackage = new ApmPackage { Name = "test", Version = "1.0.0" }
        };
        graph.AddError("Test error");
        graph.AddCircularDependency(new CircularRef { CyclePath = ["a", "b", "a"], DetectedAtDepth = 2 });

        var summary = graph.GetSummary();

        summary["error_count"].Should().Be(1);
        summary["circular_count"].Should().Be(1);
        summary["is_valid"].Should().Be(false);
    }
}

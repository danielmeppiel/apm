using Apm.Cli.Dependencies;
using Apm.Cli.Models;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Dependencies;

public class LockedDependencyTests
{
    [Fact]
    public void GetUniqueKey_ReturnsRepoUrl_ForRegularDep()
    {
        var dep = new LockedDependency { RepoUrl = "owner/repo" };
        dep.GetUniqueKey().Should().Be("owner/repo");
    }

    [Fact]
    public void GetUniqueKey_IncludesVirtualPath_ForVirtualDep()
    {
        var dep = new LockedDependency
        {
            RepoUrl = "owner/repo",
            VirtualPath = "prompts/file.md",
            IsVirtual = true
        };
        dep.GetUniqueKey().Should().Be("owner/repo/prompts/file.md");
    }

    [Fact]
    public void ToDict_ReturnsMinimalDict_WhenOnlyRepoUrlSet()
    {
        var dep = new LockedDependency { RepoUrl = "owner/repo" };
        var dict = dep.ToDict();

        dict.Should().ContainKey("repo_url");
        dict["repo_url"].Should().Be("owner/repo");
        dict.Should().NotContainKey("host");
        dict.Should().NotContainKey("resolved_commit");
    }

    [Fact]
    public void ToDict_IncludesOptionalFields_WhenSet()
    {
        var dep = new LockedDependency
        {
            RepoUrl = "owner/repo",
            Host = "github.com",
            ResolvedCommit = "abc123",
            ResolvedRef = "main",
            Version = "1.0.0",
            Depth = 2,
            ResolvedBy = "apm"
        };
        var dict = dep.ToDict();

        dict["host"].Should().Be("github.com");
        dict["resolved_commit"].Should().Be("abc123");
        dict["resolved_ref"].Should().Be("main");
        dict["version"].Should().Be("1.0.0");
        dict["depth"].Should().Be(2);
        dict["resolved_by"].Should().Be("apm");
    }

    [Fact]
    public void ToDict_OmitsDefaultDepth()
    {
        var dep = new LockedDependency { RepoUrl = "owner/repo", Depth = 1 };
        var dict = dep.ToDict();
        dict.Should().NotContainKey("depth");
    }

    [Fact]
    public void FromDict_ParsesCorrectly()
    {
        var data = new Dictionary<object, object>
        {
            ["repo_url"] = "owner/repo",
            ["host"] = "github.com",
            ["resolved_commit"] = "abc123",
            ["depth"] = 2
        };

        var dep = LockedDependency.FromDict(data);

        dep.RepoUrl.Should().Be("owner/repo");
        dep.Host.Should().Be("github.com");
        dep.ResolvedCommit.Should().Be("abc123");
        dep.Depth.Should().Be(2);
    }

    [Fact]
    public void FromDict_DefaultsDepthToOne()
    {
        var data = new Dictionary<object, object>
        {
            ["repo_url"] = "owner/repo"
        };

        var dep = LockedDependency.FromDict(data);
        dep.Depth.Should().Be(1);
    }

    [Fact]
    public void FromDependencyRef_CreatesLockedDependency()
    {
        var depRef = DependencyReference.Parse("owner/repo#main");
        var locked = LockedDependency.FromDependencyRef(depRef, "abc123", 1, "apm");

        locked.RepoUrl.Should().Be("owner/repo");
        locked.ResolvedCommit.Should().Be("abc123");
        locked.ResolvedRef.Should().Be("main");
        locked.Depth.Should().Be(1);
        locked.ResolvedBy.Should().Be("apm");
    }
}

public class LockFileTests : IDisposable
{
    private readonly string _tempDir;

    public LockFileTests()
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
    public void AddAndGetDependency_WorksCorrectly()
    {
        var lockFile = new LockFile();
        var dep = new LockedDependency { RepoUrl = "owner/repo", ResolvedCommit = "abc123" };

        lockFile.AddDependency(dep);

        lockFile.HasDependency("owner/repo").Should().BeTrue();
        lockFile.HasDependency("other/repo").Should().BeFalse();
        lockFile.GetDependency("owner/repo").Should().NotBeNull();
        lockFile.GetDependency("owner/repo")!.ResolvedCommit.Should().Be("abc123");
    }

    [Fact]
    public void ToYaml_ProducesValidYaml()
    {
        var lockFile = new LockFile { ApmVersion = "1.0.0" };
        lockFile.AddDependency(new LockedDependency { RepoUrl = "owner/repo" });

        var yaml = lockFile.ToYaml();

        yaml.Should().Contain("lockfile_version");
        yaml.Should().Contain("owner/repo");
        yaml.Should().Contain("apm_version");
    }

    [Fact]
    public void FromYaml_ParsesCorrectly()
    {
        var yamlStr = """
            lockfile_version: "1"
            apm_version: "1.0.0"
            dependencies:
              - repo_url: owner/repo
            """;

        var lockFile = LockFile.FromYaml(yamlStr);

        lockFile.LockfileVersion.Should().Be("1");
        lockFile.ApmVersion.Should().Be("1.0.0");
        lockFile.HasDependency("owner/repo").Should().BeTrue();
    }

    [Fact]
    public void FromYaml_ReturnsEmptyLockFile_WhenNullData()
    {
        var lockFile = LockFile.FromYaml("---\n");
        lockFile.Should().NotBeNull();
        lockFile.Dependencies.Should().BeEmpty();
    }

    [Fact]
    public void WriteAndRead_RoundTrips()
    {
        var lockFile = new LockFile { ApmVersion = "1.0.0" };
        lockFile.AddDependency(new LockedDependency
        {
            RepoUrl = "owner/repo",
            Host = "github.com",
            ResolvedCommit = "abc123"
        });

        var lockPath = Path.Combine(_tempDir, "apm.lock");
        lockFile.Write(lockPath);

        File.Exists(lockPath).Should().BeTrue();

        var loaded = LockFile.Read(lockPath);
        loaded.Should().NotBeNull();
        loaded!.HasDependency("owner/repo").Should().BeTrue();
        loaded.GetDependency("owner/repo")!.ResolvedCommit.Should().Be("abc123");
        loaded.GetDependency("owner/repo")!.Host.Should().Be("github.com");
    }

    [Fact]
    public void Read_ReturnsNull_WhenFileDoesNotExist()
    {
        var result = LockFile.Read(Path.Combine(_tempDir, "nonexistent.lock"));
        result.Should().BeNull();
    }

    [Fact]
    public void LoadOrCreate_CreatesNewLockFile_WhenFileDoesNotExist()
    {
        var lockFile = LockFile.LoadOrCreate(Path.Combine(_tempDir, "nonexistent.lock"));
        lockFile.Should().NotBeNull();
        lockFile.Dependencies.Should().BeEmpty();
    }

    [Fact]
    public void LoadOrCreate_LoadsExistingLockFile()
    {
        var lockPath = Path.Combine(_tempDir, "apm.lock");
        var original = new LockFile();
        original.AddDependency(new LockedDependency { RepoUrl = "owner/repo" });
        original.Write(lockPath);

        var loaded = LockFile.LoadOrCreate(lockPath);
        loaded.HasDependency("owner/repo").Should().BeTrue();
    }

    [Fact]
    public void GetAllDependencies_SortsByDepthThenRepoUrl()
    {
        var lockFile = new LockFile();
        lockFile.AddDependency(new LockedDependency { RepoUrl = "z/repo", Depth = 1 });
        lockFile.AddDependency(new LockedDependency { RepoUrl = "a/repo", Depth = 2 });
        lockFile.AddDependency(new LockedDependency { RepoUrl = "b/repo", Depth = 1 });

        var all = lockFile.GetAllDependencies();

        all.Should().HaveCount(3);
        all[0].RepoUrl.Should().Be("b/repo");
        all[1].RepoUrl.Should().Be("z/repo");
        all[2].RepoUrl.Should().Be("a/repo");
    }

    [Fact]
    public void GetLockfilePath_ReturnsCorrectPath()
    {
        var path = LockFile.GetLockfilePath(_tempDir);
        path.Should().Be(Path.Combine(_tempDir, "apm.lock"));
    }

    [Fact]
    public void FromInstalledPackages_CreatesLockFileFromPackages()
    {
        var depRef = DependencyReference.Parse("owner/repo#main");
        var graph = new DependencyGraph
        {
            RootPackage = new ApmPackage { Name = "root", Version = "1.0.0" }
        };

        var installed = new List<(DependencyReference DepRef, string? ResolvedCommit, int Depth, string? ResolvedBy)>
        {
            (depRef, "commit123", 1, null)
        };

        var lockFile = LockFile.FromInstalledPackages(installed, graph);

        lockFile.HasDependency("owner/repo").Should().BeTrue();
        lockFile.GetDependency("owner/repo")!.ResolvedCommit.Should().Be("commit123");
    }

    [Fact]
    public void Save_IsAliasForWrite()
    {
        var lockFile = new LockFile();
        lockFile.AddDependency(new LockedDependency { RepoUrl = "owner/repo" });

        var lockPath = Path.Combine(_tempDir, "apm.lock");
        lockFile.Save(lockPath);

        File.Exists(lockPath).Should().BeTrue();
        var loaded = LockFile.Read(lockPath);
        loaded.Should().NotBeNull();
        loaded!.HasDependency("owner/repo").Should().BeTrue();
    }

    [Fact]
    public void EmptyLockFile_SerializesAndDeserializes()
    {
        var lockFile = new LockFile();
        var yaml = lockFile.ToYaml();

        var loaded = LockFile.FromYaml(yaml);

        loaded.Should().NotBeNull();
        loaded.Dependencies.Should().BeEmpty();
        loaded.LockfileVersion.Should().Be("1");
    }
}

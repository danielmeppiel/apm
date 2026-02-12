using Apm.Cli.Models;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Models;

public class ResolvedReferenceTests
{
    [Fact]
    public void ToString_CommitType_ReturnsShortSha()
    {
        var resolved = new ResolvedReference("abc123", GitReferenceType.Commit, "abc123def456789012345678901234567890", "abc123");
        resolved.ToString().Should().Be("abc123de");
    }

    [Fact]
    public void ToString_BranchType_ReturnsNameWithShortSha()
    {
        var resolved = new ResolvedReference("main", GitReferenceType.Branch, "abc123def456789012345678901234567890", "main");
        resolved.ToString().Should().Be("main (abc123de)");
    }

    [Fact]
    public void ToString_TagType_ReturnsNameWithShortSha()
    {
        var resolved = new ResolvedReference("v1.0.0", GitReferenceType.Tag, "abc123def456789012345678901234567890", "v1.0.0");
        resolved.ToString().Should().Be("v1.0.0 (abc123de)");
    }

    [Fact]
    public void ToString_ShortCommit_DoesNotOverflow()
    {
        var resolved = new ResolvedReference("abc", GitReferenceType.Commit, "abc", "abc");
        resolved.ToString().Should().Be("abc");
    }
}

public class PackageInfoTests
{
    private static ApmPackage CreateTestPackage(string name = "test-pkg") =>
        new() { Name = name, Version = "1.0.0" };

    [Fact]
    public void GetCanonicalDependencyString_WithDependencyRef_UsesRef()
    {
        var depRef = DependencyReference.Parse("user/repo");
        var info = new PackageInfo(CreateTestPackage(), "/install/path")
        {
            DependencyRef = depRef
        };
        info.GetCanonicalDependencyString().Should().Contain("user/repo");
    }

    [Fact]
    public void GetCanonicalDependencyString_NoDependencyRef_UsesSource()
    {
        var pkg = CreateTestPackage();
        pkg.Source = "custom-source";
        var info = new PackageInfo(pkg, "/install/path");
        info.GetCanonicalDependencyString().Should().Be("custom-source");
    }

    [Fact]
    public void GetCanonicalDependencyString_NoSourceOrRef_UsesName()
    {
        var info = new PackageInfo(CreateTestPackage("my-pkg"), "/install/path");
        info.GetCanonicalDependencyString().Should().Be("my-pkg");
    }

    [Fact]
    public void GetPrimitivesPath_ReturnsDotApmSubdir()
    {
        var info = new PackageInfo(CreateTestPackage(), "/install/path");
        info.GetPrimitivesPath().Should().Be(Path.Combine("/install/path", ".apm"));
    }

    [Fact]
    public void HasPrimitives_NoPrimitivesDir_ReturnsFalse()
    {
        var tmpDir = Path.Combine(Path.GetTempPath(), $"apm_test_{Guid.NewGuid()}");
        Directory.CreateDirectory(tmpDir);
        try
        {
            var info = new PackageInfo(CreateTestPackage(), tmpDir);
            info.HasPrimitives().Should().BeFalse();
        }
        finally
        {
            Directory.Delete(tmpDir, true);
        }
    }

    [Fact]
    public void HasPrimitives_EmptyApmDir_ReturnsFalse()
    {
        var tmpDir = Path.Combine(Path.GetTempPath(), $"apm_test_{Guid.NewGuid()}");
        var apmDir = Path.Combine(tmpDir, ".apm");
        Directory.CreateDirectory(apmDir);
        try
        {
            var info = new PackageInfo(CreateTestPackage(), tmpDir);
            info.HasPrimitives().Should().BeFalse();
        }
        finally
        {
            Directory.Delete(tmpDir, true);
        }
    }

    [Fact]
    public void HasPrimitives_WithInstructionsFile_ReturnsTrue()
    {
        var tmpDir = Path.Combine(Path.GetTempPath(), $"apm_test_{Guid.NewGuid()}");
        var instructionsDir = Path.Combine(tmpDir, ".apm", "instructions");
        Directory.CreateDirectory(instructionsDir);
        File.WriteAllText(Path.Combine(instructionsDir, "test.md"), "content");
        try
        {
            var info = new PackageInfo(CreateTestPackage(), tmpDir);
            info.HasPrimitives().Should().BeTrue();
        }
        finally
        {
            Directory.Delete(tmpDir, true);
        }
    }

    [Fact]
    public void PackageInfo_RecordEquality_Works()
    {
        var pkg = CreateTestPackage();
        var info1 = new PackageInfo(pkg, "/path");
        var info2 = new PackageInfo(pkg, "/path");
        info1.Should().Be(info2);
    }
}

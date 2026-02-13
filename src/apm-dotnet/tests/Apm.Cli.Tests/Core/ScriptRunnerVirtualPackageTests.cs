using Apm.Cli.Core;
using Apm.Cli.Dependencies;
using Apm.Cli.Models;
using AwesomeAssertions;
using FakeItEasy;

namespace Apm.Cli.Tests.Core;

public class ScriptRunnerVirtualPackageTests
{
    [Theory]
    [InlineData("owner/repo/prompts/review.prompt.md", true)]
    [InlineData("owner/repo/file.prompt.md", true)]
    [InlineData("owner/repo/collections/my-collection", true)]
    [InlineData("owner/repo/path/to/deep.prompt.md", true)]
    public void IsVirtualPackageReference_VirtualRefs_ReturnsTrue(string name, bool expected)
    {
        ScriptRunner.IsVirtualPackageReference(name).Should().Be(expected);
    }

    [Theory]
    [InlineData("review")]
    [InlineData("build")]
    [InlineData("my-script")]
    public void IsVirtualPackageReference_SimpleNames_ReturnsFalse(string name)
    {
        ScriptRunner.IsVirtualPackageReference(name).Should().BeFalse();
    }

    [Theory]
    [InlineData("owner/repo")]
    public void IsVirtualPackageReference_TwoSegmentRepo_ReturnsFalse(string name)
    {
        ScriptRunner.IsVirtualPackageReference(name).Should().BeFalse();
    }

    [Fact]
    public void IsVirtualPackageReference_NoExtensionThreeSegments_RetriesToPromptMd()
    {
        // owner/repo/review has no extension, retry with .prompt.md makes it virtual
        ScriptRunner.IsVirtualPackageReference("owner/repo/review").Should().BeTrue();
    }

    [Fact]
    public void IsVirtualPackageReference_WrongExtension_ReturnsFalse()
    {
        ScriptRunner.IsVirtualPackageReference("owner/repo/file.txt").Should().BeFalse();
    }
}

public class ScriptRunnerExtractPromptFileNameTests
{
    [Theory]
    [InlineData("owner/repo/prompts/review.prompt.md", "review.prompt.md")]
    [InlineData("owner/repo/review.prompt.md", "review.prompt.md")]
    [InlineData("owner/repo/review", "review.prompt.md")]
    public void ExtractPromptFileName_ReturnsCorrectFilename(string packageRef, string expected)
    {
        ScriptRunner.ExtractPromptFileName(packageRef).Should().Be(expected);
    }
}

[Collection("ScriptRunner")]
public class ScriptRunnerAutoInstallTests : IDisposable
{
    private static readonly string SafeDir = AppDomain.CurrentDomain.BaseDirectory;
    private readonly string _tempDir;

    public ScriptRunnerAutoInstallTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm_auto_install_test_{Guid.NewGuid()}");
        Directory.CreateDirectory(_tempDir);
        Directory.SetCurrentDirectory(_tempDir);
    }

    public void Dispose()
    {
        Directory.SetCurrentDirectory(SafeDir);
        try { Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void AutoInstallVirtualPackage_NonVirtualRef_ReturnsFalse()
    {
        var fakeDownloader = A.Fake<IPackageDownloader>();
        var runner = new ScriptRunner(packageDownloader: fakeDownloader);

        // "owner/repo" is not virtual (only 2 segments)
        runner.AutoInstallVirtualPackage("owner/repo").Should().BeFalse();
    }

    [Fact]
    public void AutoInstallVirtualPackage_AlreadyInstalled_ReturnsTrue()
    {
        var fakeDownloader = A.Fake<IPackageDownloader>();
        var runner = new ScriptRunner(packageDownloader: fakeDownloader);

        // Parse the ref to find the install path and pre-create it
        var depRef = DependencyReference.Parse("owner/repo/review.prompt.md");
        var targetPath = depRef.GetInstallPath("apm_modules");
        Directory.CreateDirectory(targetPath);

        runner.AutoInstallVirtualPackage("owner/repo/review.prompt.md").Should().BeTrue();
        A.CallTo(fakeDownloader).MustNotHaveHappened();
    }

    [Fact]
    public void AutoInstallVirtualPackage_DownloadSucceeds_ReturnsTrueAndUpdatesConfig()
    {
        // Create apm.yml
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), "name: test-project\nversion: '1.0'\n");

        var fakeDownloader = A.Fake<IPackageDownloader>();
        var fakePackage = new ApmPackage { Name = "repo-review", Version = "1.0.0" };
        A.CallTo(() => fakeDownloader.DownloadPackage(A<string>._, A<string>._))
            .Returns(new PackageInfo(fakePackage, "apm_modules/owner/repo-review"));

        var runner = new ScriptRunner(packageDownloader: fakeDownloader);
        runner.AutoInstallVirtualPackage("owner/repo/review.prompt.md").Should().BeTrue();

        A.CallTo(() => fakeDownloader.DownloadPackage("owner/repo/review.prompt.md", A<string>._))
            .MustHaveHappenedOnceExactly();

        // Verify apm.yml was updated
        var configContent = File.ReadAllText(Path.Combine(_tempDir, "apm.yml"));
        configContent.Should().Contain("owner/repo/review.prompt.md");
    }

    [Fact]
    public void AutoInstallVirtualPackage_DownloadFails_ReturnsFalse()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), "name: test-project\nversion: '1.0'\n");

        var fakeDownloader = A.Fake<IPackageDownloader>();
        A.CallTo(() => fakeDownloader.DownloadPackage(A<string>._, A<string>._))
            .Throws(new InvalidOperationException("Network error"));

        var runner = new ScriptRunner(packageDownloader: fakeDownloader);
        runner.AutoInstallVirtualPackage("owner/repo/review.prompt.md").Should().BeFalse();
    }

    [Fact]
    public void AutoInstallVirtualPackage_NormalizesRefWithoutExtension()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), "name: test-project\nversion: '1.0'\n");

        var fakeDownloader = A.Fake<IPackageDownloader>();
        var fakePackage = new ApmPackage { Name = "repo-review", Version = "1.0.0" };
        A.CallTo(() => fakeDownloader.DownloadPackage(A<string>._, A<string>._))
            .Returns(new PackageInfo(fakePackage, "apm_modules/owner/repo-review"));

        var runner = new ScriptRunner(packageDownloader: fakeDownloader);
        runner.AutoInstallVirtualPackage("owner/repo/review").Should().BeTrue();

        // Should have been normalized to include .prompt.md
        A.CallTo(() => fakeDownloader.DownloadPackage("owner/repo/review.prompt.md", A<string>._))
            .MustHaveHappenedOnceExactly();
    }
}

[Collection("ScriptRunner")]
public class ScriptRunnerAddDependencyToConfigTests : IDisposable
{
    private static readonly string SafeDir = AppDomain.CurrentDomain.BaseDirectory;
    private readonly string _tempDir;

    public ScriptRunnerAddDependencyToConfigTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm_dep_config_test_{Guid.NewGuid()}");
        Directory.CreateDirectory(_tempDir);
        Directory.SetCurrentDirectory(_tempDir);
    }

    public void Dispose()
    {
        Directory.SetCurrentDirectory(SafeDir);
        try { Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void AddDependencyToConfig_NoConfigFile_DoesNothing()
    {
        // Should not throw when apm.yml doesn't exist
        ScriptRunner.AddDependencyToConfig("owner/repo/file.prompt.md");
    }

    [Fact]
    public void AddDependencyToConfig_AddsDependencyToExistingConfig()
    {
        File.WriteAllText("apm.yml", "name: test-project\nversion: '1.0'\n");

        ScriptRunner.AddDependencyToConfig("owner/repo/review.prompt.md");

        var content = File.ReadAllText("apm.yml");
        content.Should().Contain("owner/repo/review.prompt.md");
        content.Should().Contain("dependencies");
    }

    [Fact]
    public void AddDependencyToConfig_DoesNotDuplicate()
    {
        File.WriteAllText("apm.yml",
            "name: test-project\ndependencies:\n  apm:\n  - owner/repo/review.prompt.md\n");

        ScriptRunner.AddDependencyToConfig("owner/repo/review.prompt.md");

        var content = File.ReadAllText("apm.yml");
        // Count occurrences - should be exactly 1
        var count = content.Split("owner/repo/review.prompt.md").Length - 1;
        count.Should().Be(1);
    }

    [Fact]
    public void AddDependencyToConfig_AppendsToExistingDependencies()
    {
        File.WriteAllText("apm.yml",
            "name: test-project\ndependencies:\n  apm:\n  - other/repo/file.prompt.md\n");

        ScriptRunner.AddDependencyToConfig("owner/repo/review.prompt.md");

        var content = File.ReadAllText("apm.yml");
        content.Should().Contain("other/repo/file.prompt.md");
        content.Should().Contain("owner/repo/review.prompt.md");
    }
}

[Collection("ScriptRunner")]
public class ScriptRunnerRunScriptVirtualPackageTests : IDisposable
{
    private static readonly string SafeDir = AppDomain.CurrentDomain.BaseDirectory;
    private readonly string _tempDir;

    public ScriptRunnerRunScriptVirtualPackageTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm_run_virt_test_{Guid.NewGuid()}");
        Directory.CreateDirectory(_tempDir);
        Directory.SetCurrentDirectory(_tempDir);
    }

    public void Dispose()
    {
        Directory.SetCurrentDirectory(SafeDir);
        try { Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void RunScript_VirtualPackageRef_NoConfig_CreatesMinimalConfigAndAttempsAutoInstall()
    {
        var fakeDownloader = A.Fake<IPackageDownloader>();
        A.CallTo(() => fakeDownloader.DownloadPackage(A<string>._, A<string>._))
            .Throws(new InvalidOperationException("Network error"));

        var runner = new ScriptRunner(packageDownloader: fakeDownloader);

        // Should not throw "No apm.yml found" - should attempt auto-install instead
        var act = () => runner.RunScript("owner/repo/review.prompt.md", new Dictionary<string, string>());
        act.Should().Throw<InvalidOperationException>()
            .WithMessage("*not found*");

        // apm.yml should have been created
        File.Exists("apm.yml").Should().BeTrue();
    }

    [Fact]
    public void RunScript_VirtualPackageRef_AutoInstallsAndDiscoversPrompt()
    {
        File.WriteAllText("apm.yml", "name: test-project\nversion: '1.0'\n");

        // Set up the fake downloader to create the prompt file at the expected location
        var fakeDownloader = A.Fake<IPackageDownloader>();
        A.CallTo(() => fakeDownloader.DownloadPackage(A<string>._, A<string>._))
            .Invokes((string _, string targetPath) =>
            {
                // Simulate what the real downloader does - create the prompt file
                var promptsDir = Path.Combine(targetPath, ".apm", "prompts");
                Directory.CreateDirectory(promptsDir);
                File.WriteAllText(Path.Combine(promptsDir, "review.prompt.md"), "Review the code");
                File.WriteAllText(Path.Combine(targetPath, "apm.yml"), "name: repo-review\nversion: 1.0.0\n");
            })
            .Returns(new PackageInfo(
                new ApmPackage { Name = "repo-review", Version = "1.0.0" },
                "apm_modules/owner/repo-review"));

        var runner = new ScriptRunner(
            compiledDir: Path.Combine(_tempDir, ".apm", "compiled"),
            packageDownloader: fakeDownloader);

        // RunScript should auto-install, then discover the prompt.
        // It will fail at runtime detection (no copilot/codex installed), but that's OK -
        // it means auto-install and discovery worked.
        try
        {
            runner.RunScript("owner/repo/review.prompt.md", new Dictionary<string, string>());
        }
        catch (InvalidOperationException ex) when (ex.Message.Contains("not found") && ex.Message.Contains("review"))
        {
            Assert.Fail("Prompt file should have been auto-installed and discovered but was not.");
        }
        catch
        {
            // Runtime detection failure or execution failure means auto-install + discovery worked
        }

        A.CallTo(() => fakeDownloader.DownloadPackage(A<string>._, A<string>._))
            .MustHaveHappenedOnceExactly();
    }
}

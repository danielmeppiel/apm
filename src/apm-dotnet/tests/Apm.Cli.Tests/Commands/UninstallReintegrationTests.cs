using Apm.Cli.Integration;
using Apm.Cli.Models;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Commands;

/// <summary>
/// Tests for the uninstall nuke-and-regenerate flow.
/// Mirrors Python test_uninstall_reintegration.py.
/// When a package is uninstalled, all -apm suffixed integrated files are nuked,
/// then remaining packages are re-integrated from apm_modules/.
/// </summary>
public class UninstallReintegrationTests : IDisposable
{
    private readonly string _tempDir;

    public UninstallReintegrationTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm-uninstall-test-{Guid.NewGuid()}");
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    private PackageInfo CreatePackageWithPrompts(string name, params (string FileName, string Content)[] prompts)
    {
        var pkgDir = Path.Combine(_tempDir, "apm_modules", "owner", name);
        Directory.CreateDirectory(pkgDir);

        foreach (var (fileName, content) in prompts)
        {
            var promptsDir = Path.Combine(pkgDir, ".apm", "prompts");
            Directory.CreateDirectory(promptsDir);
            File.WriteAllText(Path.Combine(promptsDir, fileName), content);
        }

        var pkg = new ApmPackage { Name = name, Version = "1.0.0" };
        return new PackageInfo(pkg, pkgDir);
    }

    private PackageInfo CreatePackageWithAgents(string name, params (string FileName, string Content)[] agents)
    {
        var pkgDir = Path.Combine(_tempDir, "apm_modules", "owner", name);
        Directory.CreateDirectory(pkgDir);

        foreach (var (fileName, content) in agents)
        {
            var agentsDir = Path.Combine(pkgDir, ".apm", "agents");
            Directory.CreateDirectory(agentsDir);
            File.WriteAllText(Path.Combine(agentsDir, fileName), content);
        }

        var pkg = new ApmPackage { Name = name, Version = "1.0.0" };
        return new PackageInfo(pkg, pkgDir);
    }

    // ── Prompt nuke-and-regenerate ──────────────────────────────────

    [Fact]
    public void UninstallPreservesOtherPackagePrompts()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(Path.Combine(projectRoot, ".github"));

        var pkgA = CreatePackageWithPrompts("pkg-a",
            ("review.prompt.md", "---\nname: review\n---\n# Review A"));
        var pkgB = CreatePackageWithPrompts("pkg-b",
            ("lint.prompt.md", "---\nname: lint\n---\n# Lint B"));

        var promptInt = new PromptIntegrator();

        // Integrate both
        promptInt.IntegratePackagePrompts(pkgA, projectRoot);
        promptInt.IntegratePackagePrompts(pkgB, projectRoot);

        var promptsDir = Path.Combine(projectRoot, ".github", "prompts");
        File.Exists(Path.Combine(promptsDir, "review-apm.prompt.md")).Should().BeTrue();
        File.Exists(Path.Combine(promptsDir, "lint-apm.prompt.md")).Should().BeTrue();

        // Phase 1: nuke all -apm prompt files
        var dummyPkg = new ApmPackage { Name = "root", Version = "0.0.0" };
        promptInt.SyncIntegration(dummyPkg, projectRoot);

        File.Exists(Path.Combine(promptsDir, "review-apm.prompt.md")).Should().BeFalse();
        File.Exists(Path.Combine(promptsDir, "lint-apm.prompt.md")).Should().BeFalse();

        // Phase 2: re-integrate only pkg-b
        promptInt.IntegratePackagePrompts(pkgB, projectRoot);

        File.Exists(Path.Combine(promptsDir, "review-apm.prompt.md")).Should().BeFalse();
        File.Exists(Path.Combine(promptsDir, "lint-apm.prompt.md")).Should().BeTrue();
    }

    // ── Agent nuke-and-regenerate ───────────────────────────────────

    [Fact]
    public void UninstallPreservesOtherPackageAgents()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(Path.Combine(projectRoot, ".github"));

        var pkgA = CreatePackageWithAgents("pkg-a",
            ("security.agent.md", "---\nname: security\n---\n# Security A"));
        var pkgB = CreatePackageWithAgents("pkg-b",
            ("planner.agent.md", "---\nname: planner\n---\n# Planner B"));

        var agentInt = new AgentIntegrator();

        agentInt.IntegratePackageAgents(pkgA, projectRoot);
        agentInt.IntegratePackageAgents(pkgB, projectRoot);

        var agentsDir = Path.Combine(projectRoot, ".github", "agents");
        File.Exists(Path.Combine(agentsDir, "security-apm.agent.md")).Should().BeTrue();
        File.Exists(Path.Combine(agentsDir, "planner-apm.agent.md")).Should().BeTrue();

        // Phase 1: nuke
        var dummyPkg = new ApmPackage { Name = "root", Version = "0.0.0" };
        agentInt.SyncIntegration(dummyPkg, projectRoot);

        File.Exists(Path.Combine(agentsDir, "security-apm.agent.md")).Should().BeFalse();
        File.Exists(Path.Combine(agentsDir, "planner-apm.agent.md")).Should().BeFalse();

        // Phase 2: re-integrate only pkg-b
        agentInt.IntegratePackageAgents(pkgB, projectRoot);

        File.Exists(Path.Combine(agentsDir, "security-apm.agent.md")).Should().BeFalse();
        File.Exists(Path.Combine(agentsDir, "planner-apm.agent.md")).Should().BeTrue();
    }

    // ── User files not touched ──────────────────────────────────────

    [Fact]
    public void UninstallPreservesUserFiles()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(Path.Combine(projectRoot, ".github"));

        // User-created files (no -apm suffix)
        var promptsDir = Path.Combine(projectRoot, ".github", "prompts");
        Directory.CreateDirectory(promptsDir);
        var userPrompt = Path.Combine(promptsDir, "my-review.prompt.md");
        File.WriteAllText(userPrompt, "# My custom review prompt");

        var agentsDir = Path.Combine(projectRoot, ".github", "agents");
        Directory.CreateDirectory(agentsDir);
        var userAgent = Path.Combine(agentsDir, "my-agent.agent.md");
        File.WriteAllText(userAgent, "# My custom agent");

        var commandsDir = Path.Combine(projectRoot, ".claude", "commands");
        Directory.CreateDirectory(commandsDir);
        var userCmd = Path.Combine(commandsDir, "my-command.md");
        File.WriteAllText(userCmd, "# My custom command");

        // APM-managed files
        File.WriteAllText(Path.Combine(promptsDir, "pkg-review-apm.prompt.md"), "# APM managed");
        File.WriteAllText(Path.Combine(agentsDir, "pkg-agent-apm.agent.md"), "# APM managed");
        File.WriteAllText(Path.Combine(commandsDir, "pkg-cmd-apm.md"), "# APM managed");

        var dummyPkg = new ApmPackage { Name = "root", Version = "0.0.0" };

        new PromptIntegrator().SyncIntegration(dummyPkg, projectRoot);
        new AgentIntegrator().SyncIntegration(dummyPkg, projectRoot);
        new CommandIntegrator().SyncIntegration(dummyPkg, projectRoot);

        // APM files gone
        File.Exists(Path.Combine(promptsDir, "pkg-review-apm.prompt.md")).Should().BeFalse();
        File.Exists(Path.Combine(agentsDir, "pkg-agent-apm.agent.md")).Should().BeFalse();
        File.Exists(Path.Combine(commandsDir, "pkg-cmd-apm.md")).Should().BeFalse();

        // User files untouched
        File.Exists(userPrompt).Should().BeTrue();
        File.ReadAllText(userPrompt).Should().Be("# My custom review prompt");
        File.Exists(userAgent).Should().BeTrue();
        File.ReadAllText(userAgent).Should().Be("# My custom agent");
        File.Exists(userCmd).Should().BeTrue();
        File.ReadAllText(userCmd).Should().Be("# My custom command");
    }

    // ── Last package uninstall → clean state ────────────────────────

    [Fact]
    public void UninstallLastPackageLeavesCleanDirs()
    {
        var projectRoot = Path.Combine(_tempDir, "project");
        Directory.CreateDirectory(Path.Combine(projectRoot, ".github"));

        var pkg = CreatePackageWithPrompts("only-pkg",
            ("guide.prompt.md", "---\nname: guide\n---\n# Guide"));

        // Also add an agent to the same package dir
        var agentsDir = Path.Combine(pkg.InstallPath, ".apm", "agents");
        Directory.CreateDirectory(agentsDir);
        File.WriteAllText(Path.Combine(agentsDir, "helper.agent.md"),
            "---\nname: helper\n---\n# Helper");

        var promptInt = new PromptIntegrator();
        var agentInt = new AgentIntegrator();
        var cmdInt = new CommandIntegrator();

        promptInt.IntegratePackagePrompts(pkg, projectRoot);
        agentInt.IntegratePackageAgents(pkg, projectRoot);
        cmdInt.IntegratePackageCommands(pkg, projectRoot);

        var promptsDirPath = Path.Combine(projectRoot, ".github", "prompts");
        var agentsDirPath = Path.Combine(projectRoot, ".github", "agents");
        var commandsDirPath = Path.Combine(projectRoot, ".claude", "commands");

        // Verify files were created
        Directory.GetFiles(promptsDirPath, "*-apm.prompt.md").Should().NotBeEmpty();
        Directory.GetFiles(agentsDirPath, "*-apm.agent.md").Should().NotBeEmpty();

        // Nuke everything (no re-integration — last package removed)
        var dummyPkg = new ApmPackage { Name = "root", Version = "0.0.0" };
        promptInt.SyncIntegration(dummyPkg, projectRoot);
        agentInt.SyncIntegration(dummyPkg, projectRoot);
        cmdInt.SyncIntegration(dummyPkg, projectRoot);

        Directory.GetFiles(promptsDirPath, "*-apm.prompt.md").Should().BeEmpty();
        Directory.GetFiles(agentsDirPath, "*-apm.agent.md").Should().BeEmpty();
        if (Directory.Exists(commandsDirPath))
            Directory.GetFiles(commandsDirPath, "*-apm.md").Should().BeEmpty();
    }
}

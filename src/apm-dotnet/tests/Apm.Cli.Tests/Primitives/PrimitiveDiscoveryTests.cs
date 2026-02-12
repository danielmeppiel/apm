using Apm.Cli.Primitives;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Primitives;

public class PrimitiveDiscoveryInstructionTests : IDisposable
{
    private readonly string _tempDir;

    public PrimitiveDiscoveryInstructionTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), "apm-test-" + Guid.NewGuid());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void DiscoverPrimitives_FindsInstructionsInApmDirectory()
    {
        var instrDir = Path.Combine(_tempDir, ".apm", "instructions");
        Directory.CreateDirectory(instrDir);
        File.WriteAllText(Path.Combine(instrDir, "coding.instructions.md"), """
            ---
            description: Coding guidelines
            applyTo: "**/*.cs"
            ---
            Follow coding guidelines.
            """);

        var collection = PrimitiveDiscovery.DiscoverPrimitives(_tempDir);

        collection.Instructions.Should().HaveCount(1);
        collection.Instructions[0].Name.Should().Be("coding");
        collection.Instructions[0].Source.Should().Be("local");
    }

    [Fact]
    public void DiscoverPrimitives_FindsMultipleInstructions()
    {
        var instrDir = Path.Combine(_tempDir, ".apm", "instructions");
        Directory.CreateDirectory(instrDir);
        File.WriteAllText(Path.Combine(instrDir, "style.instructions.md"), """
            ---
            description: Style guide
            applyTo: "**/*.cs"
            ---
            Style content.
            """);
        File.WriteAllText(Path.Combine(instrDir, "testing.instructions.md"), """
            ---
            description: Testing guide
            applyTo: "**/*.test.cs"
            ---
            Testing content.
            """);

        var collection = PrimitiveDiscovery.DiscoverPrimitives(_tempDir);

        collection.Instructions.Should().HaveCount(2);
    }
}

public class PrimitiveDiscoveryPromptTests : IDisposable
{
    private readonly string _tempDir;

    public PrimitiveDiscoveryPromptTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), "apm-test-" + Guid.NewGuid());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void DiscoverPrimitives_FindsChatmodesInApmDirectory()
    {
        var chatDir = Path.Combine(_tempDir, ".apm", "chatmodes");
        Directory.CreateDirectory(chatDir);
        File.WriteAllText(Path.Combine(chatDir, "reviewer.chatmode.md"), """
            ---
            description: Code reviewer
            ---
            You are a code reviewer.
            """);

        var collection = PrimitiveDiscovery.DiscoverPrimitives(_tempDir);

        collection.Chatmodes.Should().HaveCount(1);
        collection.Chatmodes[0].Name.Should().Be("reviewer");
        collection.Chatmodes[0].Source.Should().Be("local");
    }
}

public class PrimitiveDiscoveryAgentTests : IDisposable
{
    private readonly string _tempDir;

    public PrimitiveDiscoveryAgentTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), "apm-test-" + Guid.NewGuid());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void DiscoverPrimitives_FindsAgentsInApmDirectory()
    {
        var agentDir = Path.Combine(_tempDir, ".apm", "agents");
        Directory.CreateDirectory(agentDir);
        File.WriteAllText(Path.Combine(agentDir, "helper.agent.md"), """
            ---
            description: Helper agent
            ---
            You are a helpful agent.
            """);

        var collection = PrimitiveDiscovery.DiscoverPrimitives(_tempDir);

        collection.Chatmodes.Should().HaveCount(1);
        collection.Chatmodes[0].Name.Should().Be("helper");
        collection.Chatmodes[0].Description.Should().Be("Helper agent");
    }
}

public class PrimitiveDiscoveryDependencyTests : IDisposable
{
    private readonly string _tempDir;

    public PrimitiveDiscoveryDependencyTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), "apm-test-" + Guid.NewGuid());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void ScanDependencyPrimitives_FindsPrimitivesInApmModules()
    {
        // Create apm.yml referencing the dependency in user/repo format
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), """
            name: test-project
            version: 1.0.0
            description: Test project
            dependencies:
              apm:
                - org/dep1
            """);

        // Create dependency with .apm structure at apm_modules/org/dep1/
        var depApmDir = Path.Combine(_tempDir, "apm_modules", "org", "dep1", ".apm", "instructions");
        Directory.CreateDirectory(depApmDir);
        File.WriteAllText(Path.Combine(depApmDir, "dep-style.instructions.md"), """
            ---
            description: Dependency style
            applyTo: "**/*.cs"
            ---
            Dependency style content.
            """);

        var collection = new PrimitiveCollection();
        PrimitiveDiscovery.ScanDependencyPrimitives(_tempDir, collection);

        collection.Instructions.Should().HaveCount(1);
        collection.Instructions[0].Name.Should().Be("dep-style");
        collection.Instructions[0].Source.Should().Contain("dep1");
    }

    [Fact]
    public void ScanDependencyPrimitives_NoModulesDir_DoesNothing()
    {
        var collection = new PrimitiveCollection();
        PrimitiveDiscovery.ScanDependencyPrimitives(_tempDir, collection);

        collection.Count().Should().Be(0);
    }

    [Fact]
    public void ScanDirectoryWithSource_FindsPrimitivesAndSetsSource()
    {
        var depDir = Path.Combine(_tempDir, "dep-pkg");
        var apmDir = Path.Combine(depDir, ".apm", "chatmodes");
        Directory.CreateDirectory(apmDir);
        File.WriteAllText(Path.Combine(apmDir, "dep-chat.chatmode.md"), """
            ---
            description: Dep chatmode
            ---
            Chatmode from dep.
            """);

        var collection = new PrimitiveCollection();
        PrimitiveDiscovery.ScanDirectoryWithSource(depDir, collection, "dependency:dep-pkg");

        collection.Chatmodes.Should().HaveCount(1);
        collection.Chatmodes[0].Source.Should().Be("dependency:dep-pkg");
    }

    [Fact]
    public void ScanDirectoryWithSource_FindsSkillWhenNoApmDir()
    {
        var depDir = Path.Combine(_tempDir, "skill-pkg");
        Directory.CreateDirectory(depDir);
        File.WriteAllText(Path.Combine(depDir, "SKILL.md"), """
            ---
            name: skill-pkg
            description: A useful skill
            ---
            Skill content here.
            """);

        var collection = new PrimitiveCollection();
        PrimitiveDiscovery.ScanDirectoryWithSource(depDir, collection, "dependency:skill-pkg");

        collection.Skills.Should().HaveCount(1);
        collection.Skills[0].Source.Should().Be("dependency:skill-pkg");
    }
}

public class PrimitiveDiscoveryEmptyDirectoryTests : IDisposable
{
    private readonly string _tempDir;

    public PrimitiveDiscoveryEmptyDirectoryTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), "apm-test-" + Guid.NewGuid());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void DiscoverPrimitives_EmptyDirectory_ReturnsEmptyCollection()
    {
        var collection = PrimitiveDiscovery.DiscoverPrimitives(_tempDir);

        collection.Count().Should().Be(0);
        collection.Chatmodes.Should().BeEmpty();
        collection.Instructions.Should().BeEmpty();
        collection.Contexts.Should().BeEmpty();
        collection.Skills.Should().BeEmpty();
    }

    [Fact]
    public void DiscoverPrimitives_EmptyApmSubdirs_ReturnsEmptyCollection()
    {
        Directory.CreateDirectory(Path.Combine(_tempDir, ".apm", "instructions"));
        Directory.CreateDirectory(Path.Combine(_tempDir, ".apm", "chatmodes"));
        Directory.CreateDirectory(Path.Combine(_tempDir, ".apm", "context"));
        Directory.CreateDirectory(Path.Combine(_tempDir, ".apm", "agents"));

        var collection = PrimitiveDiscovery.DiscoverPrimitives(_tempDir);

        collection.Count().Should().Be(0);
    }

    [Fact]
    public void FindPrimitiveFiles_NonExistentDirectory_ReturnsEmpty()
    {
        var result = PrimitiveDiscovery.FindPrimitiveFiles(
            Path.Combine(_tempDir, "nonexistent"),
            ["**/*.instructions.md"]);

        result.Should().BeEmpty();
    }
}

public class PrimitiveDiscoveryMixedTests : IDisposable
{
    private readonly string _tempDir;

    public PrimitiveDiscoveryMixedTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), "apm-test-" + Guid.NewGuid());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void DiscoverPrimitives_MixedPrimitivesAcrossDirectories()
    {
        // Instructions
        var instrDir = Path.Combine(_tempDir, ".apm", "instructions");
        Directory.CreateDirectory(instrDir);
        File.WriteAllText(Path.Combine(instrDir, "style.instructions.md"), """
            ---
            description: Style guide
            applyTo: "**/*.cs"
            ---
            Style content.
            """);

        // Chatmodes
        var chatDir = Path.Combine(_tempDir, ".apm", "chatmodes");
        Directory.CreateDirectory(chatDir);
        File.WriteAllText(Path.Combine(chatDir, "reviewer.chatmode.md"), """
            ---
            description: Code reviewer
            ---
            Reviewer content.
            """);

        // Agents
        var agentDir = Path.Combine(_tempDir, ".apm", "agents");
        Directory.CreateDirectory(agentDir);
        File.WriteAllText(Path.Combine(agentDir, "helper.agent.md"), """
            ---
            description: Helper agent
            ---
            Helper content.
            """);

        // Context
        var ctxDir = Path.Combine(_tempDir, ".apm", "context");
        Directory.CreateDirectory(ctxDir);
        File.WriteAllText(Path.Combine(ctxDir, "project.context.md"), """
            ---
            description: Project context
            ---
            Context content.
            """);

        // SKILL.md at root
        File.WriteAllText(Path.Combine(_tempDir, "SKILL.md"), """
            ---
            name: test-skill
            description: Test skill
            ---
            Skill content.
            """);

        var collection = PrimitiveDiscovery.DiscoverPrimitives(_tempDir);

        collection.Instructions.Should().HaveCount(1);
        collection.Chatmodes.Should().HaveCountGreaterThanOrEqualTo(2); // reviewer + helper (agent)
        collection.Contexts.Should().HaveCount(1);
        collection.Skills.Should().HaveCount(1);
        collection.Count().Should().BeGreaterThanOrEqualTo(5);
    }

    [Fact]
    public void DiscoverPrimitivesWithDependencies_LocalAndDependencyPrimitives()
    {
        // Local instruction
        var instrDir = Path.Combine(_tempDir, ".apm", "instructions");
        Directory.CreateDirectory(instrDir);
        File.WriteAllText(Path.Combine(instrDir, "local-style.instructions.md"), """
            ---
            description: Local style
            applyTo: "**/*.cs"
            ---
            Local style content.
            """);

        // apm.yml with dependency
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), """
            name: test-project
            version: 1.0.0
            description: Test
            dependencies:
              apm:
                - org/dep-pkg
            """);

        // Dependency instruction (different name, no conflict)
        var depDir = Path.Combine(_tempDir, "apm_modules", "org", "dep-pkg", ".apm", "instructions");
        Directory.CreateDirectory(depDir);
        File.WriteAllText(Path.Combine(depDir, "dep-style.instructions.md"), """
            ---
            description: Dep style
            applyTo: "**/*.py"
            ---
            Dep style content.
            """);

        var collection = PrimitiveDiscovery.DiscoverPrimitivesWithDependencies(_tempDir);

        collection.Instructions.Should().HaveCount(2);
        collection.HasConflicts().Should().BeFalse();
    }

    [Fact]
    public void DiscoverPrimitivesWithDependencies_LocalOverridesDependency()
    {
        // Local chatmode
        var chatDir = Path.Combine(_tempDir, ".apm", "chatmodes");
        Directory.CreateDirectory(chatDir);
        File.WriteAllText(Path.Combine(chatDir, "assistant.chatmode.md"), """
            ---
            description: Local assistant
            ---
            Local assistant content.
            """);

        // apm.yml
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), """
            name: test-project
            version: 1.0.0
            description: Test
            dependencies:
              apm:
                - org/dep-pkg
            """);

        // Dependency chatmode with same name
        var depDir = Path.Combine(_tempDir, "apm_modules", "org", "dep-pkg", ".apm", "chatmodes");
        Directory.CreateDirectory(depDir);
        File.WriteAllText(Path.Combine(depDir, "assistant.chatmode.md"), """
            ---
            description: Dep assistant
            ---
            Dep assistant content.
            """);

        var collection = PrimitiveDiscovery.DiscoverPrimitivesWithDependencies(_tempDir);

        collection.Chatmodes.Should().HaveCount(1);
        collection.Chatmodes[0].Source.Should().Be("local");
        collection.HasConflicts().Should().BeTrue();
    }

    [Fact]
    public void ScanLocalPrimitives_ExcludesApmModules()
    {
        // Local instruction
        var instrDir = Path.Combine(_tempDir, ".apm", "instructions");
        Directory.CreateDirectory(instrDir);
        File.WriteAllText(Path.Combine(instrDir, "local.instructions.md"), """
            ---
            description: Local
            applyTo: "**"
            ---
            Local content.
            """);

        // Instruction inside apm_modules (should be excluded)
        var modInstrDir = Path.Combine(_tempDir, "apm_modules", "pkg", ".apm", "instructions");
        Directory.CreateDirectory(modInstrDir);
        File.WriteAllText(Path.Combine(modInstrDir, "dep.instructions.md"), """
            ---
            description: Dep
            applyTo: "**"
            ---
            Dep content.
            """);

        var collection = new PrimitiveCollection();
        PrimitiveDiscovery.ScanLocalPrimitives(_tempDir, collection);

        collection.Instructions.Should().HaveCount(1);
        collection.Instructions[0].Name.Should().Be("local");
    }
}

public class PrimitiveDiscoveryContextTests : IDisposable
{
    private readonly string _tempDir;

    public PrimitiveDiscoveryContextTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), "apm-test-" + Guid.NewGuid());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void DiscoverPrimitives_FindsContextInApmDirectory()
    {
        var ctxDir = Path.Combine(_tempDir, ".apm", "context");
        Directory.CreateDirectory(ctxDir);
        File.WriteAllText(Path.Combine(ctxDir, "project.context.md"), """
            ---
            description: Project info
            ---
            Project context content.
            """);

        var collection = PrimitiveDiscovery.DiscoverPrimitives(_tempDir);

        collection.Contexts.Should().HaveCount(1);
        collection.Contexts[0].Name.Should().Be("project");
    }

    [Fact]
    public void DiscoverPrimitives_FindsMemoryAsContext()
    {
        var memDir = Path.Combine(_tempDir, ".apm", "memory");
        Directory.CreateDirectory(memDir);
        File.WriteAllText(Path.Combine(memDir, "notes.memory.md"), """
            ---
            description: Memory notes
            ---
            Memory content.
            """);

        var collection = PrimitiveDiscovery.DiscoverPrimitives(_tempDir);

        collection.Contexts.Should().HaveCount(1);
        collection.Contexts[0].Name.Should().Be("notes");
    }
}

public class PrimitiveDiscoverySkillTests : IDisposable
{
    private readonly string _tempDir;

    public PrimitiveDiscoverySkillTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), "apm-test-" + Guid.NewGuid());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void DiscoverPrimitives_FindsSkillMdAtRoot()
    {
        File.WriteAllText(Path.Combine(_tempDir, "SKILL.md"), """
            ---
            name: my-skill
            description: My skill
            ---
            Skill content.
            """);

        var collection = PrimitiveDiscovery.DiscoverPrimitives(_tempDir);

        collection.Skills.Should().HaveCount(1);
        collection.Skills[0].Name.Should().Be("my-skill");
        collection.Skills[0].Source.Should().Be("local");
    }
}

public class FindPrimitiveFilesTests : IDisposable
{
    private readonly string _tempDir;

    public FindPrimitiveFilesTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), "apm-test-" + Guid.NewGuid());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void FindPrimitiveFiles_ReturnsMatchingFiles()
    {
        var instrDir = Path.Combine(_tempDir, ".apm", "instructions");
        Directory.CreateDirectory(instrDir);
        File.WriteAllText(Path.Combine(instrDir, "a.instructions.md"), "content");
        File.WriteAllText(Path.Combine(instrDir, "b.instructions.md"), "content");

        var files = PrimitiveDiscovery.FindPrimitiveFiles(_tempDir,
            ["**/*.instructions.md"]);

        files.Should().HaveCount(2);
    }

    [Fact]
    public void FindPrimitiveFiles_DeduplicatesFiles()
    {
        var instrDir = Path.Combine(_tempDir, ".apm", "instructions");
        Directory.CreateDirectory(instrDir);
        File.WriteAllText(Path.Combine(instrDir, "test.instructions.md"), "content");

        // Use overlapping patterns that match the same file
        var files = PrimitiveDiscovery.FindPrimitiveFiles(_tempDir,
            ["**/*.instructions.md", "**/.apm/instructions/*.instructions.md"]);

        files.Should().HaveCount(1);
    }
}

public class GetDependencyDeclarationOrderTests : IDisposable
{
    private readonly string _tempDir;

    public GetDependencyDeclarationOrderTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), "apm-test-" + Guid.NewGuid());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void GetDependencyDeclarationOrder_NoApmYml_ReturnsEmpty()
    {
        var result = PrimitiveDiscovery.GetDependencyDeclarationOrder(_tempDir);

        result.Should().BeEmpty();
    }

    [Fact]
    public void GetDependencyDeclarationOrder_WithDependencies_ReturnsOrdered()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), """
            name: test
            version: 1.0.0
            description: Test
            dependencies:
              apm:
                - org/first-dep
                - org/second-dep
            """);

        var result = PrimitiveDiscovery.GetDependencyDeclarationOrder(_tempDir);

        result.Should().HaveCount(2);
        result[0].Should().Be("org/first-dep");
        result[1].Should().Be("org/second-dep");
    }

    [Fact]
    public void GetDependencyDeclarationOrder_WithVersionAndAlias()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), "name: test\nversion: 1.0.0\ndescription: Test\ndependencies:\n  apm:\n    - company/standards\n    - team/workflows#v1.0.0\n    - user/utilities@util-alias\n");

        var result = PrimitiveDiscovery.GetDependencyDeclarationOrder(_tempDir);

        result.Should().HaveCount(3);
        result[0].Should().Be("company/standards");
        result[1].Should().Be("team/workflows");
        result[2].Should().Be("util-alias");
    }
}

public class PrimitiveDiscoveryGitHubDirectoryTests : IDisposable
{
    private readonly string _tempDir;

    public PrimitiveDiscoveryGitHubDirectoryTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), "apm-test-" + Guid.NewGuid());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void DiscoverPrimitives_FindsChatmodesInGitHubDirectory()
    {
        var ghChatDir = Path.Combine(_tempDir, ".github", "chatmodes");
        Directory.CreateDirectory(ghChatDir);
        File.WriteAllText(Path.Combine(ghChatDir, "vscode.chatmode.md"), "---\ndescription: VSCode chatmode\n---\n\nVSCode chatmode content.");

        var collection = PrimitiveDiscovery.DiscoverPrimitives(_tempDir);

        collection.Chatmodes.Should().HaveCount(1);
        collection.Chatmodes[0].Name.Should().Be("vscode");
        collection.Chatmodes[0].Source.Should().Be("local");
    }
}

public class PrimitiveDiscoveryEmptyDepDirTests : IDisposable
{
    private readonly string _tempDir;

    public PrimitiveDiscoveryEmptyDepDirTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), "apm-test-" + Guid.NewGuid());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void DiscoverPrimitivesWithDependencies_EmptyDepDir_ReturnsNoPrimitives()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), "name: test-project\nversion: 1.0.0\ndescription: Test\ndependencies:\n  apm:\n    - company/empty-dep\n");

        // Create dependency directory but no .apm subdirectory
        Directory.CreateDirectory(Path.Combine(_tempDir, "apm_modules", "company", "empty-dep"));

        var collection = PrimitiveDiscovery.DiscoverPrimitivesWithDependencies(_tempDir);

        collection.Count().Should().Be(0);
        collection.HasConflicts().Should().BeFalse();
    }
}

public class PrimitiveDiscoveryFullNoModulesTests : IDisposable
{
    private readonly string _tempDir;

    public PrimitiveDiscoveryFullNoModulesTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), "apm-test-" + Guid.NewGuid());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void DiscoverPrimitivesWithDependencies_NoApmModules_FindsOnlyLocal()
    {
        var chatDir = Path.Combine(_tempDir, ".apm", "chatmodes");
        Directory.CreateDirectory(chatDir);
        File.WriteAllText(Path.Combine(chatDir, "local.chatmode.md"), "---\ndescription: Local chatmode\n---\n\nLocal content.");

        var collection = PrimitiveDiscovery.DiscoverPrimitivesWithDependencies(_tempDir);

        collection.Count().Should().Be(1);
        collection.Chatmodes.Should().HaveCount(1);
        collection.Chatmodes[0].Source.Should().Be("local");
        collection.HasConflicts().Should().BeFalse();
    }
}

public class PrimitiveDiscoveryDepPriorityFilesystemTests : IDisposable
{
    private readonly string _tempDir;

    public PrimitiveDiscoveryDepPriorityFilesystemTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), "apm-test-" + Guid.NewGuid());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void ScanDependencyPrimitives_FirstDependencyWins_ByDeclarationOrder()
    {
        File.WriteAllText(Path.Combine(_tempDir, "apm.yml"), "name: test\nversion: 1.0.0\ndescription: Test\ndependencies:\n  apm:\n    - first/dep\n    - second/dep\n");

        // Create first dependency
        var firstDepDir = Path.Combine(_tempDir, "apm_modules", "first", "dep", ".apm", "instructions");
        Directory.CreateDirectory(firstDepDir);
        File.WriteAllText(Path.Combine(firstDepDir, "style.instructions.md"), "---\ndescription: First dep style\napplyTo: \"**\"\n---\n\nFirst dependency content.");

        // Create second dependency with same primitive name
        var secondDepDir = Path.Combine(_tempDir, "apm_modules", "second", "dep", ".apm", "instructions");
        Directory.CreateDirectory(secondDepDir);
        File.WriteAllText(Path.Combine(secondDepDir, "style.instructions.md"), "---\ndescription: Second dep style\napplyTo: \"**\"\n---\n\nSecond dependency content.");

        var collection = new PrimitiveCollection();
        PrimitiveDiscovery.ScanDependencyPrimitives(_tempDir, collection);

        collection.Instructions.Should().HaveCount(1);
        collection.Instructions[0].Source.Should().Contain("first");
    }
}

public class ScanLocalPrimitivesSourceTests : IDisposable
{
    private readonly string _tempDir;

    public ScanLocalPrimitivesSourceTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), "apm-test-" + Guid.NewGuid());
        Directory.CreateDirectory(_tempDir);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, true);
    }

    [Fact]
    public void ScanLocalPrimitives_AllPrimitivesHaveLocalSource()
    {
        var chatDir = Path.Combine(_tempDir, ".apm", "chatmodes");
        Directory.CreateDirectory(chatDir);
        File.WriteAllText(Path.Combine(chatDir, "assistant.chatmode.md"), "---\ndescription: Local assistant\n---\n\nAssistant content.");

        var instrDir = Path.Combine(_tempDir, ".apm", "instructions");
        Directory.CreateDirectory(instrDir);
        File.WriteAllText(Path.Combine(instrDir, "style.instructions.md"), "---\ndescription: Local style\napplyTo: \"**/*.cs\"\n---\n\nStyle content.");

        var collection = new PrimitiveCollection();
        PrimitiveDiscovery.ScanLocalPrimitives(_tempDir, collection);

        collection.Count().Should().Be(2);
        collection.Chatmodes.Should().HaveCount(1);
        collection.Instructions.Should().HaveCount(1);

        foreach (var primitive in collection.AllPrimitives())
        {
            var source = primitive switch
            {
                Chatmode c => c.Source,
                Instruction i => i.Source,
                Context ctx => ctx.Source,
                Skill s => s.Source,
                _ => null
            };
            source.Should().Be("local");
        }
    }
}

using Apm.Cli.Primitives;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Primitives;

public class PrimitiveCollectionAddTests
{
    [Fact]
    public void AddPrimitive_AddsChatmode()
    {
        var collection = new PrimitiveCollection();
        var chatmode = new Chatmode { Name = "assistant", Description = "Help", Content = "Content", Source = "local" };

        collection.AddPrimitive(chatmode);

        collection.Chatmodes.Should().HaveCount(1);
        collection.Chatmodes[0].Name.Should().Be("assistant");
    }

    [Fact]
    public void AddPrimitive_AddsInstruction()
    {
        var collection = new PrimitiveCollection();
        var instruction = new Instruction { Name = "style", Description = "Style guide", ApplyTo = "**/*.cs", Content = "Content", Source = "local" };

        collection.AddPrimitive(instruction);

        collection.Instructions.Should().HaveCount(1);
        collection.Instructions[0].Name.Should().Be("style");
    }

    [Fact]
    public void AddPrimitive_AddsContext()
    {
        var collection = new PrimitiveCollection();
        var context = new Context { Name = "project", Content = "Context content", Source = "local" };

        collection.AddPrimitive(context);

        collection.Contexts.Should().HaveCount(1);
        collection.Contexts[0].Name.Should().Be("project");
    }

    [Fact]
    public void AddPrimitive_AddsSkill()
    {
        var collection = new PrimitiveCollection();
        var skill = new Skill { Name = "my-skill", Description = "A skill", Content = "Skill content", Source = "local" };

        collection.AddPrimitive(skill);

        collection.Skills.Should().HaveCount(1);
        collection.Skills[0].Name.Should().Be("my-skill");
    }

    [Fact]
    public void AddPrimitive_ThrowsForUnknownType()
    {
        var collection = new PrimitiveCollection();

        var act = () => collection.AddPrimitive("not a primitive");

        act.Should().Throw<ArgumentException>();
    }
}

public class PrimitiveCollectionCountTests
{
    [Fact]
    public void Count_ReturnsZero_WhenEmpty()
    {
        var collection = new PrimitiveCollection();

        collection.Count().Should().Be(0);
    }

    [Fact]
    public void Count_ReturnsTotalAcrossAllTypes()
    {
        var collection = new PrimitiveCollection();
        collection.AddPrimitive(new Chatmode { Name = "c1", Description = "d", Content = "x" });
        collection.AddPrimitive(new Instruction { Name = "i1", Description = "d", ApplyTo = "**", Content = "x" });
        collection.AddPrimitive(new Context { Name = "ctx1", Content = "x" });
        collection.AddPrimitive(new Skill { Name = "s1", Description = "d", Content = "x" });

        collection.Count().Should().Be(4);
    }

    [Fact]
    public void AllPrimitives_ReturnsAllItems()
    {
        var collection = new PrimitiveCollection();
        collection.AddPrimitive(new Chatmode { Name = "c1", Description = "d", Content = "x" });
        collection.AddPrimitive(new Instruction { Name = "i1", Description = "d", ApplyTo = "**", Content = "x" });

        var all = collection.AllPrimitives();

        all.Should().HaveCount(2);
    }
}

public class PrimitiveCollectionConflictTests
{
    [Fact]
    public void HasConflicts_ReturnsFalse_WhenNoConflicts()
    {
        var collection = new PrimitiveCollection();
        collection.AddPrimitive(new Chatmode { Name = "a", Description = "d", Content = "x", Source = "local" });

        collection.HasConflicts().Should().BeFalse();
    }

    [Fact]
    public void LocalOverridesDependency_AndTracksConflict()
    {
        var collection = new PrimitiveCollection();
        collection.AddPrimitive(new Chatmode { Name = "assistant", Description = "Local", Content = "Local", Source = "local" });
        collection.AddPrimitive(new Chatmode { Name = "assistant", Description = "Dep", Content = "Dep", Source = "dependency:dep1" });

        collection.Chatmodes.Should().HaveCount(1);
        collection.Chatmodes[0].Source.Should().Be("local");
        collection.HasConflicts().Should().BeTrue();
        collection.Conflicts.Should().HaveCount(1);
        collection.Conflicts[0].WinningSource.Should().Be("local");
        collection.Conflicts[0].LosingSources.Should().Contain("dependency:dep1");
    }

    [Fact]
    public void DependencyDoesNotOverrideLocal()
    {
        var collection = new PrimitiveCollection();
        collection.AddPrimitive(new Chatmode { Name = "assistant", Description = "Local", Content = "Local content", Source = "local" });
        collection.AddPrimitive(new Chatmode { Name = "assistant", Description = "Dep", Content = "Dep content", Source = "dependency:pkg" });

        collection.Chatmodes[0].Content.Should().Be("Local content");
    }

    [Fact]
    public void FirstDependencyWins_WhenBothAreDependencies()
    {
        var collection = new PrimitiveCollection();
        collection.AddPrimitive(new Instruction { Name = "style", Description = "First", ApplyTo = "**", Content = "First", Source = "dependency:first" });
        collection.AddPrimitive(new Instruction { Name = "style", Description = "Second", ApplyTo = "**", Content = "Second", Source = "dependency:second" });

        collection.Instructions.Should().HaveCount(1);
        collection.Instructions[0].Source.Should().Be("dependency:first");
        collection.Conflicts[0].WinningSource.Should().Be("dependency:first");
        collection.Conflicts[0].LosingSources.Should().Contain("dependency:second");
    }

    [Fact]
    public void LocalReplacesExistingDependency()
    {
        var collection = new PrimitiveCollection();
        collection.AddPrimitive(new Chatmode { Name = "assistant", Description = "Dep", Content = "Dep", Source = "dependency:dep1" });
        collection.AddPrimitive(new Chatmode { Name = "assistant", Description = "Local", Content = "Local", Source = "local" });

        collection.Chatmodes.Should().HaveCount(1);
        collection.Chatmodes[0].Source.Should().Be("local");
        collection.Conflicts[0].WinningSource.Should().Be("local");
    }

    [Fact]
    public void GetConflictsByType_FiltersCorrectly()
    {
        var collection = new PrimitiveCollection();
        collection.AddPrimitive(new Chatmode { Name = "a", Description = "d", Content = "x", Source = "local" });
        collection.AddPrimitive(new Chatmode { Name = "a", Description = "d", Content = "x", Source = "dependency:d1" });
        collection.AddPrimitive(new Instruction { Name = "b", Description = "d", ApplyTo = "**", Content = "x", Source = "local" });
        collection.AddPrimitive(new Instruction { Name = "b", Description = "d", ApplyTo = "**", Content = "x", Source = "dependency:d2" });

        collection.GetConflictsByType("chatmode").Should().HaveCount(1);
        collection.GetConflictsByType("instruction").Should().HaveCount(1);
        collection.GetConflictsByType("context").Should().BeEmpty();
    }
}

public class PrimitiveCollectionFilteringTests
{
    [Fact]
    public void GetPrimitivesBySource_FiltersLocal()
    {
        var collection = new PrimitiveCollection();
        collection.AddPrimitive(new Chatmode { Name = "local-chat", Description = "d", Content = "x", Source = "local" });
        collection.AddPrimitive(new Instruction { Name = "dep-inst", Description = "d", ApplyTo = "**", Content = "x", Source = "dependency:pkg" });

        var local = collection.GetPrimitivesBySource("local");

        local.Should().HaveCount(1);
    }

    [Fact]
    public void GetPrimitivesBySource_ReturnsDependencies()
    {
        var collection = new PrimitiveCollection();
        collection.AddPrimitive(new Chatmode { Name = "c", Description = "d", Content = "x", Source = "local" });
        collection.AddPrimitive(new Context { Name = "ctx", Content = "x", Source = "dependency:pkg1" });
        collection.AddPrimitive(new Skill { Name = "s", Description = "d", Content = "x", Source = "dependency:pkg1" });

        var deps = collection.GetPrimitivesBySource("dependency:pkg1");

        deps.Should().HaveCount(2);
    }

    [Fact]
    public void GetPrimitivesBySource_ReturnsEmpty_WhenNoMatch()
    {
        var collection = new PrimitiveCollection();
        collection.AddPrimitive(new Chatmode { Name = "c", Description = "d", Content = "x", Source = "local" });

        collection.GetPrimitivesBySource("nonexistent").Should().BeEmpty();
    }
}

public class PrimitiveModelPropertyTests
{
    [Fact]
    public void Chatmode_DefaultProperties()
    {
        var chatmode = new Chatmode();

        chatmode.Name.Should().BeEmpty();
        chatmode.FilePath.Should().BeEmpty();
        chatmode.Description.Should().BeEmpty();
        chatmode.ApplyTo.Should().BeNull();
        chatmode.Content.Should().BeEmpty();
        chatmode.Author.Should().BeNull();
        chatmode.Version.Should().BeNull();
        chatmode.Source.Should().BeNull();
    }

    [Fact]
    public void Instruction_DefaultProperties()
    {
        var instruction = new Instruction();

        instruction.Name.Should().BeEmpty();
        instruction.ApplyTo.Should().BeEmpty();
        instruction.Source.Should().BeNull();
    }

    [Fact]
    public void Context_DefaultProperties()
    {
        var context = new Context();

        context.Name.Should().BeEmpty();
        context.Description.Should().BeNull();
        context.Source.Should().BeNull();
    }

    [Fact]
    public void Skill_DefaultProperties()
    {
        var skill = new Skill();

        skill.Name.Should().BeEmpty();
        skill.Description.Should().BeEmpty();
        skill.Source.Should().BeNull();
    }

    [Fact]
    public void Chatmode_Validate_ReturnsErrors_WhenInvalid()
    {
        var chatmode = new Chatmode { Description = "", Content = "" };

        var errors = chatmode.Validate();

        errors.Should().NotBeEmpty();
        errors.Should().Contain(e => e.Contains("description"));
        errors.Should().Contain(e => e.Contains("Empty content"));
    }

    [Fact]
    public void Chatmode_Validate_NoErrors_WhenValid()
    {
        var chatmode = new Chatmode { Description = "Valid", Content = "Valid content" };

        chatmode.Validate().Should().BeEmpty();
    }

    [Fact]
    public void Instruction_Validate_RequiresApplyTo()
    {
        var instruction = new Instruction { Description = "Valid", ApplyTo = "", Content = "Content" };

        var errors = instruction.Validate();

        errors.Should().Contain(e => e.Contains("applyTo"));
    }

    [Fact]
    public void Context_Validate_RequiresContent()
    {
        var context = new Context { Content = "  " };

        context.Validate().Should().NotBeEmpty();
    }

    [Fact]
    public void Skill_Validate_RequiresNameAndDescription()
    {
        var skill = new Skill { Name = "", Description = "", Content = "x" };

        var errors = skill.Validate();

        errors.Should().Contain(e => e.Contains("name"));
        errors.Should().Contain(e => e.Contains("description"));
    }
}

public class PrimitiveConflictTests
{
    [Fact]
    public void ToString_FormatsCorrectly()
    {
        var conflict = new PrimitiveConflict
        {
            PrimitiveName = "assistant",
            PrimitiveType = "chatmode",
            WinningSource = "local",
            LosingSources = ["dependency:dep1", "dependency:dep2"],
            FilePath = "local.chatmode.md"
        };

        var result = conflict.ToString();

        result.Should().Contain("chatmode");
        result.Should().Contain("assistant");
        result.Should().Contain("local");
        result.Should().Contain("dependency:dep1");
        result.Should().Contain("dependency:dep2");
    }

    [Fact]
    public void PrimitiveConflict_DefaultProperties()
    {
        var conflict = new PrimitiveConflict();

        conflict.PrimitiveName.Should().BeEmpty();
        conflict.PrimitiveType.Should().BeEmpty();
        conflict.WinningSource.Should().BeEmpty();
        conflict.LosingSources.Should().BeEmpty();
        conflict.FilePath.Should().BeEmpty();
    }
}

public class SourceTrackingTests
{
    [Fact]
    public void Chatmode_SourceTracking_Local()
    {
        var chatmode = new Chatmode
        {
            Name = "test-chatmode",
            Description = "Test chatmode",
            Content = "# Test content",
            Source = "local"
        };

        chatmode.Source.Should().Be("local");
    }

    [Fact]
    public void Instruction_SourceTracking_Dependency()
    {
        var instruction = new Instruction
        {
            Name = "test-instruction",
            Description = "Test instruction",
            ApplyTo = "**/*.py",
            Content = "# Test content",
            Source = "dependency:package1"
        };

        instruction.Source.Should().Be("dependency:package1");
    }

    [Fact]
    public void Context_SourceTracking_DefaultIsNull()
    {
        var context = new Context
        {
            Name = "test-context",
            Content = "# Test content"
        };

        context.Source.Should().BeNull();
    }
}

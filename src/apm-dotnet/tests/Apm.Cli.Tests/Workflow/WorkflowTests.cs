using Apm.Cli.Workflow;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Workflow;

/// <summary>
/// Port of Python test_workflow.py tests for WorkflowParser, WorkflowRunner, WorkflowDiscovery.
/// </summary>
public class WorkflowParserTests : IDisposable
{
    private readonly string _tempDir;
    private readonly string _promptsDir;
    private readonly string _workflowPath;

    public WorkflowParserTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm_workflow_test_{Guid.NewGuid()}");
        _promptsDir = Path.Combine(_tempDir, ".github", "prompts");
        Directory.CreateDirectory(_promptsDir);

        _workflowPath = Path.Combine(_promptsDir, "test-workflow.prompt.md");
        File.WriteAllText(_workflowPath, """
            ---
            description: Test workflow
            author: Test Author
            mcp:
              - test-package
            input:
              - param1
              - param2
            ---

            # Test Workflow

            1. Step One: ${input:param1}
            2. Step Two: ${input:param2}
            """);
    }

    public void Dispose()
    {
        try { Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void ParseWorkflowFile_ValidFile_ReturnsCorrectDefinition()
    {
        var workflow = WorkflowParser.ParseWorkflowFile(_workflowPath);

        workflow.Name.Should().Be("test-workflow");
        workflow.Description.Should().Be("Test workflow");
        workflow.Author.Should().Be("Test Author");
        workflow.McpDependencies.Should().Contain("test-package");
        workflow.InputParameters.Should().HaveCount(2);
        workflow.InputParameters.Should().Contain("param1");
        workflow.InputParameters.Should().Contain("param2");
        workflow.Content.Should().Contain("# Test Workflow");
    }

    [Fact]
    public void Validate_ValidWorkflow_ReturnsNoErrors()
    {
        var workflow = new WorkflowDefinition
        {
            Name = "test",
            FilePath = ".github/prompts/test.prompt.md",
            Description = "Test",
            InputParameters = ["param1"],
            Content = "content"
        };

        workflow.Validate().Should().BeEmpty();
    }

    [Fact]
    public void Validate_MissingDescription_ReturnsError()
    {
        var workflow = new WorkflowDefinition
        {
            Name = "test",
            FilePath = ".github/prompts/test.prompt.md",
            Description = "",
            InputParameters = ["param1"],
            Content = "content"
        };

        var errors = workflow.Validate();
        errors.Should().HaveCount(1);
        errors[0].Should().Contain("description");
    }

    [Fact]
    public void Validate_MissingInput_IsOptional()
    {
        var workflow = new WorkflowDefinition
        {
            Name = "test",
            FilePath = ".github/prompts/test.prompt.md",
            Description = "Test",
            Content = "content"
        };

        workflow.Validate().Should().BeEmpty();
    }

    [Fact]
    public void ExtractWorkflowName_PromptMdFile_ExtractsName()
    {
        var name = WorkflowParser.ExtractWorkflowName(
            Path.Combine(".github", "prompts", "my-workflow.prompt.md"));

        name.Should().Be("my-workflow");
    }
}

public class WorkflowRunnerTests
{
    [Fact]
    public void SubstituteParameters_ReplacesPlaceholders()
    {
        var content = "This is a test with ${input:param1} and ${input:param2}.";
        var parameters = new Dictionary<string, string>
        {
            ["param1"] = "value1",
            ["param2"] = "value2"
        };

        var result = WorkflowRunner.SubstituteParameters(content, parameters);
        result.Should().Be("This is a test with value1 and value2.");
    }

    [Fact]
    public void SubstituteParameters_MissingParams_LeavesPlaceholder()
    {
        var content = "This is a test with ${input:param1} and ${input:param2}.";
        var parameters = new Dictionary<string, string>
        {
            ["param1"] = "value1"
        };

        var result = WorkflowRunner.SubstituteParameters(content, parameters);
        result.Should().Be("This is a test with value1 and ${input:param2}.");
    }

    [Fact]
    public void SubstituteParameters_EmptyParams_LeavesAllPlaceholders()
    {
        var content = "Hello ${input:name}!";
        var result = WorkflowRunner.SubstituteParameters(content, []);
        result.Should().Be("Hello ${input:name}!");
    }

    [Fact]
    public void SubstituteParameters_NoPlaceholders_ReturnsUnchanged()
    {
        var content = "Plain text without placeholders.";
        var result = WorkflowRunner.SubstituteParameters(content, new Dictionary<string, string> { ["key"] = "value" });
        result.Should().Be("Plain text without placeholders.");
    }
}

public class WorkflowDiscoveryTests : IDisposable
{
    private readonly string _tempDir;
    private readonly string _promptsDir;

    public WorkflowDiscoveryTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"apm_discovery_test_{Guid.NewGuid()}");
        _promptsDir = Path.Combine(_tempDir, ".github", "prompts");
        Directory.CreateDirectory(_promptsDir);

        File.WriteAllText(Path.Combine(_promptsDir, "workflow1.prompt.md"), """
            ---
            description: Workflow 1
            input:
              - param1
            ---
            # Workflow 1
            """);

        File.WriteAllText(Path.Combine(_promptsDir, "workflow2.prompt.md"), """
            ---
            description: Workflow 2
            input:
              - param1
            ---
            # Workflow 2
            """);
    }

    public void Dispose()
    {
        try { Directory.Delete(_tempDir, true); } catch { }
    }

    [Fact]
    public void DiscoverWorkflows_FindsPromptMdFiles()
    {
        var workflows = WorkflowDiscovery.DiscoverWorkflows(_tempDir);

        workflows.Should().HaveCount(2);
        var names = workflows.Select(w => w.Name).ToList();
        names.Should().Contain("workflow1");
        names.Should().Contain("workflow2");
    }

    [Fact]
    public void DiscoverWorkflows_EmptyDirectory_ReturnsEmpty()
    {
        var emptyDir = Path.Combine(Path.GetTempPath(), $"apm_empty_test_{Guid.NewGuid()}");
        Directory.CreateDirectory(emptyDir);

        try
        {
            var workflows = WorkflowDiscovery.DiscoverWorkflows(emptyDir);
            workflows.Should().BeEmpty();
        }
        finally
        {
            try { Directory.Delete(emptyDir, true); } catch { }
        }
    }

    [Fact]
    public void CreateWorkflowTemplate_CreatesFileWithExpectedContent()
    {
        var templatePath = WorkflowDiscovery.CreateWorkflowTemplate("test-template", _tempDir);

        File.Exists(templatePath).Should().BeTrue();
        var content = File.ReadAllText(templatePath);
        content.Should().Contain("description:");
        content.Should().Contain("author:");
        content.Should().Contain("mcp:");
        content.Should().Contain("input:");
        content.Should().Contain("# Test Template");
    }

    [Fact]
    public void CreateWorkflowTemplate_UsesGitHubPromptsConventionByDefault()
    {
        var templatePath = WorkflowDiscovery.CreateWorkflowTemplate("convention-test", _tempDir);

        templatePath.Should().Contain(Path.Combine(".github", "prompts"));
        templatePath.Should().EndWith("convention-test.prompt.md");
    }
}

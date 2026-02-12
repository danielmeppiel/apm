using Apm.Cli.Runtime;

namespace Apm.Cli.Workflow;

/// <summary>Runner for workflow execution.</summary>
public static class WorkflowRunner
{
    /// <summary>Simple string-based parameter substitution.</summary>
    public static string SubstituteParameters(string content, Dictionary<string, string> parameters)
    {
        var result = content;
        foreach (var (key, value) in parameters)
        {
            var placeholder = $"${{input:{key}}}";
            result = result.Replace(placeholder, value);
        }
        return result;
    }

    /// <summary>Collect parameters from provided params or prompt for missing ones.</summary>
    public static Dictionary<string, string> CollectParameters(
        WorkflowDefinition workflowDef, Dictionary<string, string>? providedParams = null)
    {
        providedParams ??= [];

        if (workflowDef.InputParameters.Count == 0)
            return new Dictionary<string, string>(providedParams);

        var result = new Dictionary<string, string>(providedParams);
        var missingParams = workflowDef.InputParameters
            .Where(p => !result.ContainsKey(p))
            .ToList();

        if (missingParams.Count > 0)
        {
            Console.WriteLine($"Workflow '{workflowDef.Name}' requires the following parameters:");
            foreach (var param in missingParams)
            {
                Console.Write($"  {param}: ");
                var value = Console.ReadLine() ?? "";
                result[param] = value;
            }
        }

        return result;
    }

    /// <summary>Find a workflow by name or file path.</summary>
    public static WorkflowDefinition? FindWorkflowByName(string name, string? baseDir = null)
    {
        baseDir ??= Directory.GetCurrentDirectory();

        // If name looks like a file path, try to parse it directly
        if (name.EndsWith(".prompt.md", StringComparison.OrdinalIgnoreCase) ||
            name.EndsWith(".workflow.md", StringComparison.OrdinalIgnoreCase))
        {
            var filePath = Path.IsPathRooted(name) ? name : Path.Combine(baseDir, name);

            if (File.Exists(filePath))
            {
                try
                {
                    return WorkflowParser.ParseWorkflowFile(filePath);
                }
                catch (Exception ex)
                {
                    Console.Error.WriteLine($"Error parsing workflow file {name}: {ex.Message}");
                    return null;
                }
            }
        }

        // Otherwise, search by name
        var workflows = WorkflowDiscovery.DiscoverWorkflows(baseDir);
        return workflows.FirstOrDefault(w => w.Name == name);
    }

    /// <summary>Run a workflow with parameters.</summary>
    public static (bool Success, string Result) RunWorkflow(
        string workflowName,
        Dictionary<string, string>? parameters = null,
        string? baseDir = null)
    {
        parameters ??= [];

        // Extract runtime and model information
        parameters.TryGetValue("_runtime", out var runtimeName);
        parameters.TryGetValue("_llm", out var fallbackLlm);

        // Find the workflow
        var workflow = FindWorkflowByName(workflowName, baseDir);
        if (workflow is null)
            return (false, $"Workflow '{workflowName}' not found.");

        // Validate the workflow
        var errors = workflow.Validate();
        if (errors.Count > 0)
            return (false, $"Invalid workflow: {string.Join(", ", errors)}");

        // Collect missing parameters
        var allParams = CollectParameters(workflow, parameters);

        // Substitute parameters
        var resultContent = SubstituteParameters(workflow.Content, allParams);

        // Determine the LLM model to use (frontmatter > --llm flag > runtime default)
        var llmModel = workflow.LlmModel ?? fallbackLlm;

        if (!string.IsNullOrEmpty(workflow.LlmModel) && !string.IsNullOrEmpty(fallbackLlm))
        {
            Console.Error.WriteLine(
                $"WARNING: Both frontmatter 'llm: {workflow.LlmModel}' and --llm '{fallbackLlm}' specified. " +
                $"Using frontmatter value: {workflow.LlmModel}");
        }

        // Execute with runtime
        try
        {
            RuntimeBase runtime;
            if (!string.IsNullOrEmpty(runtimeName))
            {
                if (RuntimeFactory.RuntimeExists(runtimeName))
                {
                    runtime = RuntimeFactory.CreateRuntime(runtimeName, llmModel);
                }
                else
                {
                    var available = RuntimeFactory.GetAvailableRuntimes();
                    var names = string.Join(", ", available.Select(r => r["name"]));
                    return (false, $"Invalid runtime '{runtimeName}'. Available runtimes: {names}");
                }
            }
            else
            {
                runtime = RuntimeFactory.CreateRuntime(modelName: llmModel);
            }

            var response = runtime.ExecutePrompt(resultContent);
            return (true, response);
        }
        catch (Exception ex)
        {
            return (false, $"Runtime execution failed: {ex.Message}");
        }
    }

    /// <summary>Preview a workflow with parameters substituted (without execution).</summary>
    public static (bool Success, string Result) PreviewWorkflow(
        string workflowName,
        Dictionary<string, string>? parameters = null,
        string? baseDir = null)
    {
        parameters ??= [];

        var workflow = FindWorkflowByName(workflowName, baseDir);
        if (workflow is null)
            return (false, $"Workflow '{workflowName}' not found.");

        var errors = workflow.Validate();
        if (errors.Count > 0)
            return (false, $"Invalid workflow: {string.Join(", ", errors)}");

        var allParams = CollectParameters(workflow, parameters);
        var resultContent = SubstituteParameters(workflow.Content, allParams);
        return (true, resultContent);
    }
}

namespace Apm.Cli.Core;

/// <summary>
/// Handles Docker argument processing with deduplication for MCP configuration.
/// </summary>
public static class DockerArgs
{
    /// <summary>
    /// Process Docker arguments with environment variable deduplication and required flags.
    /// </summary>
    /// <param name="baseArgs">Base Docker arguments list.</param>
    /// <param name="envVars">Environment variables to inject.</param>
    /// <returns>Updated arguments with env vars injected without duplicates and required flags.</returns>
    public static List<string> ProcessDockerArgs(IReadOnlyList<string> baseArgs, Dictionary<string, string> envVars)
    {
        var result = new List<string>();
        var envVarsAdded = new HashSet<string>();
        var hasInteractive = false;
        var hasRm = false;

        // Check for existing -i and --rm flags
        foreach (var arg in baseArgs)
        {
            if (arg is "-i" or "--interactive")
                hasInteractive = true;
            else if (arg == "--rm")
                hasRm = true;
        }

        foreach (var arg in baseArgs)
        {
            result.Add(arg);

            // When we encounter "run", inject required flags and env vars
            if (arg == "run")
            {
                if (!hasInteractive)
                    result.Add("-i");

                if (!hasRm)
                    result.Add("--rm");

                foreach (var (envName, envValue) in envVars)
                {
                    if (envVarsAdded.Add(envName))
                    {
                        result.Add("-e");
                        result.Add($"{envName}={envValue}");
                    }
                }
            }
        }

        return result;
    }

    /// <summary>
    /// Extract environment variables from Docker args.
    /// </summary>
    /// <param name="args">Docker arguments that may contain -e flags.</param>
    /// <returns>Tuple of (cleanArgs, envVars) with -e flags removed.</returns>
    public static (List<string> CleanArgs, Dictionary<string, string> EnvVars) ExtractEnvVarsFromArgs(
        IReadOnlyList<string> args)
    {
        var cleanArgs = new List<string>();
        var envVars = new Dictionary<string, string>();
        var i = 0;

        while (i < args.Count)
        {
            if (args[i] == "-e" && i + 1 < args.Count)
            {
                var envSpec = args[i + 1];
                var eqIdx = envSpec.IndexOf('=');
                if (eqIdx >= 0)
                    envVars[envSpec[..eqIdx]] = envSpec[(eqIdx + 1)..];
                else
                    envVars[envSpec] = "${" + envSpec + "}";
                i += 2;
            }
            else
            {
                cleanArgs.Add(args[i]);
                i++;
            }
        }

        return (cleanArgs, envVars);
    }

    /// <summary>
    /// Merge environment variables, prioritizing resolved values over templates.
    /// </summary>
    /// <param name="existingEnv">Existing environment variables (often templates from registry).</param>
    /// <param name="newEnv">New environment variables to merge (resolved actual values).</param>
    /// <returns>Merged environment variables with resolved values taking precedence.</returns>
    public static Dictionary<string, string> MergeEnvVars(
        Dictionary<string, string> existingEnv,
        Dictionary<string, string> newEnv)
    {
        var merged = new Dictionary<string, string>(existingEnv);
        foreach (var (key, value) in newEnv)
            merged[key] = value;
        return merged;
    }
}

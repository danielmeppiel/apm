namespace Apm.Cli.Core;

/// <summary>
/// Centralized token management for different AI runtimes and git platforms.
///
/// Token Architecture:
///   GITHUB_COPILOT_PAT — User-scoped PAT specifically for Copilot
///   GITHUB_APM_PAT     — Fine-grained PAT for APM module access (GitHub)
///   ADO_APM_PAT        — PAT for APM module access (Azure DevOps)
///   GITHUB_TOKEN       — User-scoped PAT for GitHub Models API access
///
/// Platform Token Selection:
///   GitHub:       GITHUB_APM_PAT → GITHUB_TOKEN → GH_TOKEN
///   Azure DevOps: ADO_APM_PAT
/// </summary>
public class TokenManager
{
    /// <summary>Token precedence for different use cases.</summary>
    public static readonly Dictionary<string, string[]> TokenPrecedence = new()
    {
        ["copilot"]     = ["GITHUB_COPILOT_PAT", "GITHUB_TOKEN", "GITHUB_APM_PAT"],
        ["models"]      = ["GITHUB_TOKEN", "GITHUB_APM_PAT"],
        ["modules"]     = ["GITHUB_APM_PAT", "GITHUB_TOKEN"],
        ["ado_modules"] = ["ADO_APM_PAT"],
    };

    /// <summary>Runtime-specific environment variable mappings.</summary>
    public static readonly Dictionary<string, string[]> RuntimeEnvVars = new()
    {
        ["copilot"] = ["GH_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN"],
        ["codex"]   = ["GITHUB_TOKEN"],
        ["llm"]     = ["GITHUB_MODELS_KEY"],
    };

    private readonly bool _preserveExisting;

    /// <param name="preserveExisting">If true, never overwrite existing environment variables.</param>
    public TokenManager(bool preserveExisting = true)
    {
        _preserveExisting = preserveExisting;
    }

    /// <summary>
    /// Set up complete token environment for all runtimes.
    /// </summary>
    public Dictionary<string, string> SetupEnvironment(Dictionary<string, string>? env = null)
    {
        env ??= GetCurrentEnvironment();

        var availableTokens = GetAvailableTokens(env);

        SetupCopilotTokens(env, availableTokens);
        SetupCodexTokens(env, availableTokens);
        SetupLlmTokens(env, availableTokens);

        return env;
    }

    /// <summary>
    /// Get the best available token for a specific purpose.
    /// </summary>
    public string? GetTokenForPurpose(string purpose, Dictionary<string, string>? env = null)
    {
        env ??= GetCurrentEnvironment();

        if (!TokenPrecedence.TryGetValue(purpose, out var tokenVars))
            throw new ArgumentException($"Unknown purpose: {purpose}", nameof(purpose));

        foreach (var tokenVar in tokenVars)
        {
            if (env.TryGetValue(tokenVar, out var token) && !string.IsNullOrEmpty(token))
                return token;
        }

        return null;
    }

    /// <summary>
    /// Validate that required tokens are available.
    /// </summary>
    public (bool IsValid, string Message) ValidateTokens(Dictionary<string, string>? env = null)
    {
        env ??= GetCurrentEnvironment();

        var hasAnyToken = GetTokenForPurpose("copilot", env) is not null
                       || GetTokenForPurpose("models", env) is not null
                       || GetTokenForPurpose("modules", env) is not null;

        if (!hasAnyToken)
        {
            return (false,
                "No tokens found. Set one of:\n"
              + "- GITHUB_TOKEN (user-scoped PAT for GitHub Models)\n"
              + "- GITHUB_APM_PAT (fine-grained PAT for APM modules on GitHub)\n"
              + "- ADO_APM_PAT (PAT for APM modules on Azure DevOps)");
        }

        var modelsToken = GetTokenForPurpose("models", env);
        if (modelsToken is null && env.ContainsKey("GITHUB_APM_PAT"))
        {
            return (true,
                "Warning: Only fine-grained PAT available. "
              + "GitHub Models requires GITHUB_TOKEN (user-scoped PAT)");
        }

        return (true, "Token validation passed");
    }

    // --- Convenience static helpers (match Python module-level functions) ---

    /// <summary>Resolve the best GitHub token from environment variables.</summary>
    public static string? GetGitHubToken(Dictionary<string, string>? env = null)
    {
        var mgr = new TokenManager();
        return mgr.GetTokenForPurpose("modules", env);
    }

    /// <summary>Resolve the Azure DevOps token from environment variables.</summary>
    public static string? GetAdoToken(Dictionary<string, string>? env = null)
    {
        var mgr = new TokenManager();
        return mgr.GetTokenForPurpose("ado_modules", env);
    }

    /// <summary>Resolve the Copilot token from environment variables.</summary>
    public static string? GetCopilotToken(Dictionary<string, string>? env = null)
    {
        var mgr = new TokenManager();
        return mgr.GetTokenForPurpose("copilot", env);
    }

    /// <summary>Set up complete runtime environment for all AI CLIs.</summary>
    public static Dictionary<string, string> SetupRuntimeEnvironment(Dictionary<string, string>? env = null)
    {
        var mgr = new TokenManager();
        return mgr.SetupEnvironment(env);
    }

    /// <summary>Validate GitHub token setup.</summary>
    public static (bool IsValid, string Message) ValidateGitHubTokens(Dictionary<string, string>? env = null)
    {
        var mgr = new TokenManager();
        return mgr.ValidateTokens(env);
    }

    /// <summary>Get the appropriate GitHub token for a specific runtime.</summary>
    public static string? GetGitHubTokenForRuntime(string runtime, Dictionary<string, string>? env = null)
    {
        var runtimeToPurpose = new Dictionary<string, string>
        {
            ["copilot"] = "copilot",
            ["codex"] = "models",
            ["llm"] = "models",
        };

        if (!runtimeToPurpose.TryGetValue(runtime, out var purpose))
            throw new ArgumentException($"Unknown runtime: {runtime}", nameof(runtime));

        var mgr = new TokenManager();
        return mgr.GetTokenForPurpose(purpose, env);
    }

    // --- Private helpers ---

    private Dictionary<string, string> GetAvailableTokens(Dictionary<string, string> env)
    {
        var tokens = new Dictionary<string, string>();
        foreach (var (_, tokenVars) in TokenPrecedence)
        {
            foreach (var tokenVar in tokenVars)
            {
                if (env.TryGetValue(tokenVar, out var val) && !string.IsNullOrEmpty(val))
                    tokens[tokenVar] = val;
            }
        }
        return tokens;
    }

    private void SetupCopilotTokens(Dictionary<string, string> env, Dictionary<string, string> availableTokens)
    {
        var copilotToken = GetTokenForPurpose("copilot", availableTokens);
        if (copilotToken is null)
            return;

        foreach (var envVar in RuntimeEnvVars["copilot"])
        {
            if (_preserveExisting && env.ContainsKey(envVar))
                continue;
            env[envVar] = copilotToken;
        }
    }

    private void SetupCodexTokens(Dictionary<string, string> env, Dictionary<string, string> availableTokens)
    {
        if (!(_preserveExisting && env.ContainsKey("GITHUB_TOKEN")))
        {
            var modelsToken = GetTokenForPurpose("models", availableTokens);
            if (modelsToken is not null && !env.ContainsKey("GITHUB_TOKEN"))
                env["GITHUB_TOKEN"] = modelsToken;
        }

        if (!(_preserveExisting && env.ContainsKey("GITHUB_APM_PAT")))
        {
            if (availableTokens.TryGetValue("GITHUB_APM_PAT", out var apmToken)
                && !env.ContainsKey("GITHUB_APM_PAT"))
            {
                env["GITHUB_APM_PAT"] = apmToken;
            }
        }
    }

    private void SetupLlmTokens(Dictionary<string, string> env, Dictionary<string, string> availableTokens)
    {
        if (_preserveExisting && env.ContainsKey("GITHUB_MODELS_KEY"))
            return;

        var modelsToken = GetTokenForPurpose("models", availableTokens);
        if (modelsToken is not null)
            env["GITHUB_MODELS_KEY"] = modelsToken;
    }

    private static Dictionary<string, string> GetCurrentEnvironment()
    {
        var dict = new Dictionary<string, string>();
        foreach (var entry in Environment.GetEnvironmentVariables())
        {
            if (entry is System.Collections.DictionaryEntry de
                && de.Key is string key && de.Value is string val)
            {
                dict[key] = val;
            }
        }
        return dict;
    }
}

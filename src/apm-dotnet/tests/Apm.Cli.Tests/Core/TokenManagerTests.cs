using Apm.Cli.Core;
using AwesomeAssertions;

namespace Apm.Cli.Tests.Core;

public class TokenManagerGetTokenForPurposeTests
{
    [Fact]
    public void GetTokenForPurpose_Modules_PrefersApmPat()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_APM_PAT"] = "apm-token",
            ["GITHUB_TOKEN"] = "generic-token"
        };

        var mgr = new TokenManager();
        var token = mgr.GetTokenForPurpose("modules", env);
        token.Should().Be("apm-token");
    }

    [Fact]
    public void GetTokenForPurpose_Modules_FallsBackToGitHubToken()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_TOKEN"] = "fallback-token"
        };

        var mgr = new TokenManager();
        var token = mgr.GetTokenForPurpose("modules", env);
        token.Should().Be("fallback-token");
    }

    [Fact]
    public void GetTokenForPurpose_Models_PrefersGitHubToken()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_TOKEN"] = "models-token",
            ["GITHUB_APM_PAT"] = "apm-token"
        };

        var mgr = new TokenManager();
        var token = mgr.GetTokenForPurpose("models", env);
        token.Should().Be("models-token");
    }

    [Fact]
    public void GetTokenForPurpose_Copilot_PrefersGitHubCopilotPat()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_COPILOT_PAT"] = "copilot-token",
            ["GITHUB_TOKEN"] = "generic-token",
            ["GITHUB_APM_PAT"] = "apm-token"
        };

        var mgr = new TokenManager();
        var token = mgr.GetTokenForPurpose("copilot", env);
        token.Should().Be("copilot-token");
    }

    [Fact]
    public void GetTokenForPurpose_AdoModules_UsesAdoPat()
    {
        var env = new Dictionary<string, string>
        {
            ["ADO_APM_PAT"] = "ado-token"
        };

        var mgr = new TokenManager();
        var token = mgr.GetTokenForPurpose("ado_modules", env);
        token.Should().Be("ado-token");
    }

    [Fact]
    public void GetTokenForPurpose_NoTokens_ReturnsNull()
    {
        var env = new Dictionary<string, string>();
        var mgr = new TokenManager();
        mgr.GetTokenForPurpose("modules", env).Should().BeNull();
    }

    [Fact]
    public void GetTokenForPurpose_EmptyTokenSkipped()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_APM_PAT"] = "",
            ["GITHUB_TOKEN"] = "actual-token"
        };

        var mgr = new TokenManager();
        mgr.GetTokenForPurpose("modules", env).Should().Be("actual-token");
    }

    [Fact]
    public void GetTokenForPurpose_UnknownPurpose_ThrowsArgumentException()
    {
        var mgr = new TokenManager();
        var act = () => mgr.GetTokenForPurpose("nonexistent", new Dictionary<string, string>());
        act.Should().Throw<ArgumentException>().WithMessage("*Unknown purpose*");
    }
}

public class TokenManagerStaticHelperTests
{
    [Fact]
    public void GetGitHubToken_FollowsModulesPrecedence()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_APM_PAT"] = "apm-token",
            ["GITHUB_TOKEN"] = "generic-token"
        };
        TokenManager.GetGitHubToken(env).Should().Be("apm-token");
    }

    [Fact]
    public void GetAdoToken_ReturnsAdoPat()
    {
        var env = new Dictionary<string, string>
        {
            ["ADO_APM_PAT"] = "ado-token"
        };
        TokenManager.GetAdoToken(env).Should().Be("ado-token");
    }

    [Fact]
    public void GetAdoToken_NoToken_ReturnsNull()
    {
        TokenManager.GetAdoToken(new Dictionary<string, string>()).Should().BeNull();
    }

    [Fact]
    public void GetCopilotToken_FollowsCopilotPrecedence()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_COPILOT_PAT"] = "copilot-token",
            ["GITHUB_TOKEN"] = "generic-token"
        };
        TokenManager.GetCopilotToken(env).Should().Be("copilot-token");
    }

    [Fact]
    public void GetGitHubTokenForRuntime_Copilot_UsesCopilotPrecedence()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_COPILOT_PAT"] = "copilot-token",
            ["GITHUB_TOKEN"] = "generic-token"
        };
        TokenManager.GetGitHubTokenForRuntime("copilot", env).Should().Be("copilot-token");
    }

    [Fact]
    public void GetGitHubTokenForRuntime_Codex_UsesModelsPrecedence()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_TOKEN"] = "models-token",
            ["GITHUB_APM_PAT"] = "apm-token"
        };
        TokenManager.GetGitHubTokenForRuntime("codex", env).Should().Be("models-token");
    }

    [Fact]
    public void GetGitHubTokenForRuntime_UnknownRuntime_Throws()
    {
        var act = () => TokenManager.GetGitHubTokenForRuntime("unknown", new Dictionary<string, string>());
        act.Should().Throw<ArgumentException>().WithMessage("*Unknown runtime*");
    }
}

public class TokenManagerValidateTests
{
    [Fact]
    public void ValidateTokens_NoTokens_ReturnsInvalid()
    {
        var env = new Dictionary<string, string>();
        var (isValid, message) = TokenManager.ValidateGitHubTokens(env);
        isValid.Should().BeFalse();
        message.Should().Contain("No tokens found");
    }

    [Fact]
    public void ValidateTokens_WithGitHubToken_ReturnsValid()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_TOKEN"] = "my-token"
        };
        var (isValid, _) = TokenManager.ValidateGitHubTokens(env);
        isValid.Should().BeTrue();
    }

    [Fact]
    public void ValidateTokens_OnlyApmPat_ReturnsValid()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_APM_PAT"] = "apm-token"
        };
        var (isValid, _) = TokenManager.ValidateGitHubTokens(env);
        isValid.Should().BeTrue();
    }
}

public class TokenManagerSetupEnvironmentTests
{
    [Fact]
    public void SetupEnvironment_WithCopilotPat_SetsGhToken()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_COPILOT_PAT"] = "copilot-token"
        };

        var mgr = new TokenManager();
        var result = mgr.SetupEnvironment(env);

        result.Should().ContainKey("GH_TOKEN");
        result["GH_TOKEN"].Should().Be("copilot-token");
    }

    [Fact]
    public void SetupEnvironment_PreservesExisting_DoesNotOverwrite()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_COPILOT_PAT"] = "copilot-token",
            ["GH_TOKEN"] = "existing-token"
        };

        var mgr = new TokenManager(preserveExisting: true);
        var result = mgr.SetupEnvironment(env);
        result["GH_TOKEN"].Should().Be("existing-token");
    }

    [Fact]
    public void SetupEnvironment_WithModelsToken_SetsGitHubModelsKey()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_TOKEN"] = "models-token"
        };

        var mgr = new TokenManager();
        var result = mgr.SetupEnvironment(env);
        result.Should().ContainKey("GITHUB_MODELS_KEY");
        result["GITHUB_MODELS_KEY"].Should().Be("models-token");
    }

    [Fact]
    public void SetupEnvironment_EmptyEnv_ReturnsEmptyishDict()
    {
        var env = new Dictionary<string, string>();
        var mgr = new TokenManager();
        var result = mgr.SetupEnvironment(env);
        // No tokens to set up, shouldn't add new keys
        result.Should().NotContainKey("GH_TOKEN");
        result.Should().NotContainKey("GITHUB_MODELS_KEY");
    }

    [Fact]
    public void SetupEnvironment_NoTokens_NoRuntimeEnvVarsAdded()
    {
        // Matches Python: test_no_tokens_available
        // Verifies ALL runtime env vars are absent when no tokens provided
        var env = new Dictionary<string, string>();
        var mgr = new TokenManager();
        var result = mgr.SetupEnvironment(env);

        result.Should().NotContainKey("GITHUB_TOKEN");
        result.Should().NotContainKey("GH_TOKEN");
        result.Should().NotContainKey("GITHUB_PERSONAL_ACCESS_TOKEN");
        result.Should().NotContainKey("GITHUB_MODELS_KEY");
    }
}

public class TokenManagerFallbackChainTests
{
    [Fact]
    public void GetTokenForPurpose_Copilot_FallsBackToGitHubToken()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_TOKEN"] = "generic-token"
        };

        var mgr = new TokenManager();
        mgr.GetTokenForPurpose("copilot", env).Should().Be("generic-token");
    }

    [Fact]
    public void GetTokenForPurpose_Copilot_FallsBackToApmPat()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_APM_PAT"] = "apm-token"
        };

        var mgr = new TokenManager();
        mgr.GetTokenForPurpose("copilot", env).Should().Be("apm-token");
    }

    [Fact]
    public void GetTokenForPurpose_Models_FallsBackToApmPat()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_APM_PAT"] = "apm-token"
        };

        var mgr = new TokenManager();
        mgr.GetTokenForPurpose("models", env).Should().Be("apm-token");
    }

    [Fact]
    public void GetTokenForPurpose_AllTokensSet_EachPurposeResolvesCorrectly()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_COPILOT_PAT"] = "copilot-token",
            ["GITHUB_APM_PAT"] = "apm-token",
            ["GITHUB_TOKEN"] = "generic-token",
            ["ADO_APM_PAT"] = "ado-token"
        };

        var mgr = new TokenManager();
        mgr.GetTokenForPurpose("copilot", env).Should().Be("copilot-token");
        mgr.GetTokenForPurpose("models", env).Should().Be("generic-token");
        mgr.GetTokenForPurpose("modules", env).Should().Be("apm-token");
        mgr.GetTokenForPurpose("ado_modules", env).Should().Be("ado-token");
    }

    [Fact]
    public void GetGitHubTokenForRuntime_Llm_UsesModelsPrecedence()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_TOKEN"] = "models-token",
            ["GITHUB_APM_PAT"] = "apm-token"
        };
        TokenManager.GetGitHubTokenForRuntime("llm", env).Should().Be("models-token");
    }
}

public class TokenManagerSetupEnvironmentIntegrationTests
{
    [Fact]
    public void SetupEnvironment_BothApmPatAndGitHubToken_SetsAllDerivedVars()
    {
        // Matches Python: test_token_precedence_with_apm_pat
        // When both APM_PAT and GITHUB_TOKEN present, all runtime env vars should be set
        var env = new Dictionary<string, string>
        {
            ["GITHUB_APM_PAT"] = "apm-token",
            ["GITHUB_TOKEN"] = "generic-token"
        };

        var mgr = new TokenManager();
        var result = mgr.SetupEnvironment(env);

        // Copilot runtime: copilot precedence falls back to GITHUB_TOKEN
        result["GH_TOKEN"].Should().Be("generic-token");
        result["GITHUB_PERSONAL_ACCESS_TOKEN"].Should().Be("generic-token");
        // LLM runtime: models precedence prefers GITHUB_TOKEN
        result["GITHUB_MODELS_KEY"].Should().Be("generic-token");
        // Input tokens preserved
        result["GITHUB_APM_PAT"].Should().Be("apm-token");
        result["GITHUB_TOKEN"].Should().Be("generic-token");
    }

    [Fact]
    public void SetupEnvironment_OnlyGitHubToken_SetsAllDerivedVars()
    {
        // Matches Python: test_token_precedence_fallback_to_github_token
        // When only GITHUB_TOKEN is available, it should be used for all runtimes
        var env = new Dictionary<string, string>
        {
            ["GITHUB_TOKEN"] = "generic-token"
        };

        var mgr = new TokenManager();
        var result = mgr.SetupEnvironment(env);

        // Copilot runtime: copilot precedence falls back to GITHUB_TOKEN
        result["GH_TOKEN"].Should().Be("generic-token");
        result["GITHUB_PERSONAL_ACCESS_TOKEN"].Should().Be("generic-token");
        // LLM runtime: models precedence prefers GITHUB_TOKEN
        result["GITHUB_MODELS_KEY"].Should().Be("generic-token");
        // Input token preserved, GITHUB_APM_PAT not added
        result["GITHUB_TOKEN"].Should().Be("generic-token");
        result.Should().NotContainKey("GITHUB_APM_PAT");
    }
}

public class TokenManagerPassthroughTests
{
    [Fact]
    public void SetupEnvironment_MultipleTokens_PreservesAllInputTokens()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_APM_PAT"] = "apm-token",
            ["GITHUB_TOKEN"] = "generic-token"
        };

        var mgr = new TokenManager();
        var result = mgr.SetupEnvironment(env);

        result["GITHUB_APM_PAT"].Should().Be("apm-token");
        result["GITHUB_TOKEN"].Should().Be("generic-token");
    }

    [Fact]
    public void SetupEnvironment_OnlyGitHubToken_PreservesIt()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_TOKEN"] = "generic-token"
        };

        var mgr = new TokenManager();
        var result = mgr.SetupEnvironment(env);

        result["GITHUB_TOKEN"].Should().Be("generic-token");
    }

    [Fact]
    public void SetupEnvironment_NoPreserveExisting_OverwritesGhToken()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_COPILOT_PAT"] = "copilot-token",
            ["GH_TOKEN"] = "old-token"
        };

        var mgr = new TokenManager(preserveExisting: false);
        var result = mgr.SetupEnvironment(env);

        result["GH_TOKEN"].Should().Be("copilot-token");
    }

    [Fact]
    public void SetupEnvironment_OnlyGitHubToken_ApmPatNotAdded()
    {
        // Matches Python: test_token_passthrough_to_scripts Case 2
        // Only expected tokens present — GITHUB_APM_PAT must NOT appear
        var env = new Dictionary<string, string>
        {
            ["GITHUB_TOKEN"] = "generic-token"
        };

        var mgr = new TokenManager();
        var result = mgr.SetupEnvironment(env);

        result["GITHUB_TOKEN"].Should().Be("generic-token");
        result.Should().NotContainKey("GITHUB_APM_PAT");
    }
}

public class TokenManagerValidateWarningTests
{
    [Fact]
    public void ValidateTokens_OnlyCopilotPat_ReturnsValid()
    {
        var env = new Dictionary<string, string>
        {
            ["GITHUB_COPILOT_PAT"] = "copilot-token"
        };
        var (isValid, message) = TokenManager.ValidateGitHubTokens(env);
        isValid.Should().BeTrue();
        message.Should().Contain("validation passed");
    }

    [Fact]
    public void ValidateTokens_OnlyAdoPat_ReturnsInvalid()
    {
        // ADO PAT alone is not sufficient for GitHub token validation
        var env = new Dictionary<string, string>
        {
            ["ADO_APM_PAT"] = "ado-token"
        };
        var (isValid, _) = TokenManager.ValidateGitHubTokens(env);
        // ADO token is not checked in copilot/models/modules purposes
        isValid.Should().BeFalse();
    }
}

public class TokenPrecedenceConstantsTests
{
    [Fact]
    public void TokenPrecedence_ContainsExpectedPurposes()
    {
        TokenManager.TokenPrecedence.Should().ContainKey("copilot");
        TokenManager.TokenPrecedence.Should().ContainKey("models");
        TokenManager.TokenPrecedence.Should().ContainKey("modules");
        TokenManager.TokenPrecedence.Should().ContainKey("ado_modules");
    }

    [Fact]
    public void TokenPrecedence_Modules_CorrectOrder()
    {
        var modules = TokenManager.TokenPrecedence["modules"];
        modules[0].Should().Be("GITHUB_APM_PAT");
        modules[1].Should().Be("GITHUB_TOKEN");
    }

    [Fact]
    public void TokenPrecedence_Copilot_CorrectOrder()
    {
        var copilot = TokenManager.TokenPrecedence["copilot"];
        copilot[0].Should().Be("GITHUB_COPILOT_PAT");
        copilot[1].Should().Be("GITHUB_TOKEN");
        copilot[2].Should().Be("GITHUB_APM_PAT");
    }

    [Fact]
    public void RuntimeEnvVars_ContainsExpectedRuntimes()
    {
        TokenManager.RuntimeEnvVars.Should().ContainKey("copilot");
        TokenManager.RuntimeEnvVars.Should().ContainKey("codex");
        TokenManager.RuntimeEnvVars.Should().ContainKey("llm");
    }
}

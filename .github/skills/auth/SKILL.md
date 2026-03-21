---
name: auth
description: >
  Activate when code touches token management, credential resolution, git auth
  flows, GITHUB_APM_PAT, ADO_APM_PAT, AuthResolver, HostInfo, AuthContext, or
  any remote host authentication — even if 'auth' isn't mentioned explicitly.
---

# Auth Skill

[Auth expert persona](../../agents/auth-expert.agent.md)

## When to activate

- Any change to `src/apm_cli/core/auth.py` or `src/apm_cli/core/token_manager.py`
- Code that reads `GITHUB_APM_PAT`, `GITHUB_TOKEN`, `GH_TOKEN`, `ADO_APM_PAT`
- Code using `git ls-remote`, `git clone`, or GitHub/ADO API calls
- Error messages mentioning tokens, authentication, or credentials
- Changes to `github_downloader.py` auth paths
- Per-host or per-org token resolution logic

## Key rule

All auth flows MUST go through `AuthResolver`. No direct `os.getenv()` for token variables in application code.

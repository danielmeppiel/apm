# Core Workflow

## 5-step workflow

```bash
# 1. Install APM (one-time)
curl -sSL https://aka.ms/apm-unix | sh        # or irm on Windows

# 2. Initialize project
apm init my-project && cd my-project           # new project
cd existing-repo && apm init                   # existing repo

# 3. Install packages
apm install microsoft/apm-sample-package#v1.0.0

# 4. Compile (needed for Codex, Gemini, single-file targets)
apm compile

# 5. Commit and share
git add apm.yml apm.lock.yaml .apm/ .github/ .claude/ .cursor/
git commit -m "Add APM dependencies"
```

## apm.yml schema overview

```yaml
name:          <string>                    # REQUIRED -- package identifier
version:       <string>                    # REQUIRED -- semver (e.g. 1.0.0)
description:   <string>                    # optional
author:        <string>                    # optional
license:       <string>                    # optional -- SPDX (e.g. MIT)
target:        <enum>                      # optional -- vscode|claude|codex|opencode|all
type:          <enum>                      # optional -- instructions|skill|hybrid|prompts
scripts:       <map<string, string>>       # optional -- named commands
dependencies:
  apm:         <list<ApmDependency>>       # optional
  mcp:         <list<McpDependency>>       # optional
devDependencies:                           # optional -- excluded from bundles
  apm:         <list<ApmDependency>>
  mcp:         <list<McpDependency>>
compilation:                               # optional
  target:      <enum>                      # vscode|claude|codex|opencode|all
  strategy:    <enum>                      # distributed|single-file
  output:      <string>                    # custom output path
  chatmode:    <string>                    # chatmode to prepend
  resolve_links: <bool>                    # resolve markdown links (default true)
  source_attribution: <bool>              # include source comments
```

### Type behavior

| Value | Behavior |
|-------|----------|
| `instructions` | Compiled into AGENTS.md only; no skill directory |
| `skill` | Installed as skill only; no AGENTS.md |
| `hybrid` | Both AGENTS.md + skill installation |
| `prompts` | Commands/prompts only; no instructions/skills |

### Target auto-detection

| Condition | Detected target |
|-----------|-----------------|
| `.github/` exists only | `vscode` |
| `.claude/` exists only | `claude` |
| `.codex/` exists | `codex` |
| Both `.github/` and `.claude/` | `all` |
| Neither exists | `minimal` (AGENTS.md only) |

## What to commit

| Path | Commit? | Why |
|------|---------|-----|
| `apm.yml` | Yes | Manifest -- declares dependencies |
| `apm.lock.yaml` | Yes | Lockfile -- pins exact commits for reproducibility |
| `.apm/` | Yes | Local primitives (instructions, agents, etc.) |
| `.github/`, `.claude/`, `.cursor/` | Yes | Deployed files for agent runtimes |
| `apm_modules/` | **No** | Downloaded sources -- add to `.gitignore` |

## Team member setup

```bash
git clone <repo-url>
cd <repo>
apm install            # restores all deps from lockfile
```

The lockfile ensures every team member gets the exact same dependency versions.
Subsequent `apm install` reads locked commit SHAs for reproducible installs.
Use `apm install --update` to refresh to latest refs.

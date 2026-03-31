---
title: Scoped Installation
sidebar:
  order: 11
---

APM supports two installation scopes: **project** (default) and **user** (global).

## Project scope (default)

Packages install into the current directory:

```bash
apm install microsoft/apm-sample-package
```

- Manifest: `./apm.yml`
- Modules: `./apm_modules/`
- Lockfile: `./apm.lock.yaml`
- Deployed primitives: `./.github/`, `./.claude/`, `./.cursor/`, `./.opencode/`

This is the standard behavior. Every collaborator who clones the repo gets the same setup.

## User scope (`--global`)

Packages install to your home directory, making them available across all projects:

```bash
apm install -g microsoft/apm-sample-package
```

- Manifest: `~/.apm/apm.yml`
- Modules: `~/.apm/apm_modules/`
- Lockfile: `~/.apm/apm.lock.yaml`

### Per-target support

Not all AI tools support user-level configuration. APM warns during `--global` installs about targets that lack native user-level support.

| Target | User-level directory | Status | Notes | Reference |
|---|---|---|---|---|
| Claude Code | `~/.claude/` | Supported | All primitives (agents, commands, skills, hooks) | [Settings](https://docs.anthropic.com/en/docs/claude-code/settings) |
| Copilot CLI | `~/.copilot/` | Partial | Agents, skills, instructions; prompts not supported | [Agents](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli), [Skills](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-skills), [Instructions](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions) |
| Cursor | N/A | Not supported | User rules managed via Cursor Settings UI only | [Rules](https://cursor.com/docs/rules) |
| OpenCode | N/A | Not supported | No official docs for user-level config | -- |

### Uninstalling user-scope packages

```bash
apm uninstall -g microsoft/apm-sample-package
```

## When to use each scope

| Use case | Scope |
|---|---|
| Team-shared instructions and prompts | Project (`apm install`) |
| Personal Claude Code commands and agents | User (`apm install -g`) |
| CI/CD reproducible setup | Project |
| Cross-project coding standards (Claude Code) | User |

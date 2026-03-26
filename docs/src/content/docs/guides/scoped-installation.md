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

Currently, only **Claude Code** fully supports user-scope primitives. **Copilot CLI** and **VS Code** are partially supported -- the tools read from user-level directories, but APM's current integrators have limitations. APM deploys primitives relative to the home directory, but some AI tools either read from a different user-level path than what APM produces, or only support workspace-level configuration.

APM warns during `--global` installs about targets that lack native user-level support.

| Target | User-level directory | Status | Why | Reference |
|--------|---------------------|--------|-----|-----------|
| Claude Code | `~/.claude/` | Supported | APM deploys to `~/.claude/` which Claude reads for user-level commands, agents, skills, hooks | [Claude Code settings](https://docs.anthropic.com/en/docs/claude-code/settings) |
| Copilot (CLI) | `~/.copilot/` | Partially supported | Copilot CLI reads agents, skills, instructions from `~/.copilot/`; Copilot CLI does not support prompts | [Agents](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli), [Skills](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-skills), [Instructions](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions) |
| VS Code | User `mcp.json` | Partially supported | VS Code reads user-level MCP servers from user `mcp.json`; APM currently only writes to workspace `.vscode/mcp.json` | [VS Code MCP servers](https://code.visualstudio.com/docs/copilot/customization/mcp-servers) |
| Cursor | `~/.cursor/` | Not supported | User rules are managed via Cursor Settings UI, not the filesystem | [Cursor rules docs](https://cursor.com/docs/rules) |
| OpenCode | `~/.opencode/` | Not supported | No official documentation for user-level config | No official docs available |

### Uninstalling user-scope packages

```bash
apm uninstall -g microsoft/apm-sample-package
```

## When to use each scope

| Use case | Scope |
|----------|-------|
| Team-shared instructions and prompts | Project (`apm install`) |
| Personal Claude Code commands and agents | User (`apm install -g`) |
| CI/CD reproducible setup | Project |
| Cross-project coding standards (Claude Code) | User |

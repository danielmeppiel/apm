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

Not all AI tools read primitives from user-level directories. APM warns during `--global` installs about targets that lack native support.

| Target | User-level directory | Status | Primitives at user scope | Reference |
|--------|---------------------|--------|--------------------------|-----------|
| Claude Code | `~/.claude/` | Supported | commands, agents, skills, hooks | [Claude Code settings](https://docs.anthropic.com/en/docs/claude-code/settings) |
| Copilot (CLI) | `~/.copilot/` | Supported | agents | [Custom agents for CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli) |
| VS Code | User settings.json | Partial | MCP servers only (via VS Code user settings) | [VS Code settings](https://code.visualstudio.com/docs/configure/settings) |
| Cursor | `~/.cursor/` | Not supported | None (user rules are managed via Cursor Settings UI) | [Cursor rules docs](https://cursor.com/docs/rules) |
| OpenCode | `~/.opencode/` | Unverified | None confirmed | No official docs available |

When you run `apm install -g`, APM deploys primitives to all detected targets but shows a warning for those that do not natively read from user-level directories.

### Uninstalling user-scope packages

```bash
apm uninstall -g microsoft/apm-sample-package
```

## When to use each scope

| Use case | Scope |
|----------|-------|
| Team-shared instructions and prompts | Project (`apm install`) |
| Personal Claude Code commands and agents | User (`apm install -g`) |
| Personal Copilot CLI agents | User (`apm install -g`) |
| CI/CD reproducible setup | Project |
| Cross-project coding standards (Claude Code, Copilot CLI) | User |

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
- Deployed primitives: `~/.github/`, `~/.claude/`, `~/.cursor/`, `~/.opencode/`

### Where user-scope primitives land

| Target | User-level directory | What tools read from it |
|--------|---------------------|------------------------|
| Copilot | `~/.github/` | VS Code user-level instructions |
| Claude | `~/.claude/` | Claude Code global commands and instructions |
| Cursor | `~/.cursor/` | Cursor user-level rules and agents |
| OpenCode | `~/.opencode/` | OpenCode user-level agents and commands |

### Uninstalling user-scope packages

```bash
apm uninstall -g microsoft/apm-sample-package
```

## When to use each scope

| Use case | Scope |
|----------|-------|
| Team-shared instructions and prompts | Project (`apm install`) |
| Personal productivity packages | User (`apm install -g`) |
| CI/CD reproducible setup | Project |
| Cross-project coding standards | User |

---
title: Configuration (.apmrc)
description: Configure APM behavior, registries, and authentication with .apmrc files.
---

APM reads configuration from `.apmrc` files using a flat `key=value` format inspired by npm's `.npmrc`. This lets you configure registries, authentication tokens, and behavior flags per-project or globally.

## Quick Start

Scaffold a new `.apmrc` in your project:

```bash
apm config init-rc
```

Or set a value directly:

```bash
apm config set registry https://your-registry.example.com
apm config set auto-integrate false
```

## File Format

`.apmrc` is a flat INI-style file. Each line is a `key=value` pair, a comment (`#` or `;`), or blank.

```ini
# Default registry
registry=https://api.mcp.github.com

# Auth token (use env var reference — never commit real tokens)
github-token=${GITHUB_APM_PAT}

# Scoped registry for an organization
@myorg:registry=https://myorg.pkg.github.com
//myorg.pkg.github.com/:_authToken=${MYORG_TOKEN}

# Behavior
default-client=claude
auto-integrate=true
ci-mode=${CI:+true}
```

## Configuration Hierarchy

APM loads `.apmrc` from multiple locations. Later sources override earlier ones:

| Priority | Source | Location |
|----------|--------|----------|
| 1 (lowest) | Global home | `~/.apmrc` |
| 2 | Global APM dir | `~/.apm/.apmrc` |
| 3 | XDG config | `$XDG_CONFIG_HOME/apm/.apmrc` (Linux/macOS) |
| 4 | Project | `.apmrc` in project root (walked up from cwd) |
| 5 | Env vars | `APM_CONFIG_*` environment variables |
| 6 (highest) | CLI flags | Command-line arguments |

Use `apm config which-rc` to see which files are loaded:

```bash
$ apm config which-rc
  1. [global] /home/user/.apm/.apmrc
  2. [project] /home/user/myproject/.apmrc
```

## Environment Variable Substitution

Values can reference environment variables. This lets you commit `.apmrc` to version control without exposing secrets:

| Syntax | Behavior |
|--------|----------|
| `${VAR}` | Substitute value; leave `${VAR}` as-is if unset |
| `${VAR?}` | Substitute value; empty string if unset |
| `${VAR:-default}` | Substitute value; use `default` if unset or empty |
| `${VAR:+word}` | Use `word` if VAR is set and non-empty; else empty |
| `\${VAR}` | Literal `${VAR}` (backslash escaping) |

Example:

```ini
# Token from env var — safe to commit
github-token=${GITHUB_APM_PAT}

# Conditional CI mode — only active when CI env var is set
ci-mode=${CI:+true}

# Registry with fallback
registry=${APM_REGISTRY:-https://api.mcp.github.com}
```

## `APM_CONFIG_*` Environment Variables

Any environment variable starting with `APM_CONFIG_` is mapped to a config key, mirroring npm's `npm_config_*` convention. Underscores become hyphens:

```bash
# These are equivalent:
export APM_CONFIG_REGISTRY=https://custom.io    # → registry=https://custom.io
export APM_CONFIG_DEFAULT_CLIENT=claude          # → default-client=claude
export APM_CONFIG_AUTO_INTEGRATE=false           # → auto-integrate=false
```

`APM_CONFIG_*` variables take precedence over all `.apmrc` files, making them ideal for CI/CD overrides.

## Supported Keys

### Registry

| Key | Description | Default |
|-----|-------------|---------|
| `registry` | Default registry URL for package lookups | `https://api.mcp.github.com` |
| `@scope:registry` | Override registry for packages under `@scope` | Falls back to `registry` |

### Authentication

| Key | Description |
|-----|-------------|
| `github-token` | GitHub personal access token for private packages |
| `//host/:_authToken` | Per-host bearer token (follows `.npmrc` convention) |

Token resolution priority: `GITHUB_APM_PAT` env → `GITHUB_TOKEN` env → `GH_TOKEN` env → `.apmrc github-token` → git credential helper.

### Behavior

| Key | Description | Default |
|-----|-------------|---------|
| `default-client` | AI client target (`vscode`, `claude`, `cursor`, `copilot`, `codex`) | `vscode` |
| `auto-integrate` | Auto-integrate packages into client config | `true` |
| `ci-mode` | Suppress interactive prompts in CI | `false` |

## Scoped Registries

Route packages under a scope to a different registry, with separate auth:

```ini
# Packages under @myorg use a private registry
@myorg:registry=https://myorg.pkg.github.com

# Auth token for that registry
//myorg.pkg.github.com/:_authToken=${MYORG_TOKEN}
```

When APM resolves `@myorg/some-package`, it uses `https://myorg.pkg.github.com` instead of the default registry, and sends the configured bearer token.

## CLI Commands

| Command | Description |
|---------|-------------|
| `apm config show-rc` | Show all merged `.apmrc` values (tokens masked) |
| `apm config show-rc --json` | Same, as JSON |
| `apm config which-rc` | List loaded `.apmrc` files with precedence |
| `apm config get <key>` | Get a specific config value |
| `apm config set <key> <value>` | Set a value in `.apmrc` |
| `apm config set <key> <value> --global` | Set in `~/.apm/.apmrc` |
| `apm config delete <key>` | Remove a key from `.apmrc` |
| `apm config init-rc` | Scaffold a new `.apmrc` with commented defaults |
| `apm config init-rc --global` | Scaffold global `~/.apm/.apmrc` |
| `apm config edit` | Open `.apmrc` in `$EDITOR` |

## Security

- **Never commit real tokens.** Use `${VAR}` references and set the actual values via environment variables or `~/.apm/.apmrc`.
- **File permissions:** `.apmrc` files are created with mode `0600` (owner-only). APM warns if it finds a world-readable `.apmrc`.
- **Sensitive keys are protected.** `apm config get github-token` is blocked — use `apm config show-rc` to see masked values.
- **Symlinks rejected.** File write operations refuse to follow symlinks to prevent write-redirection attacks.

## Best Practices

1. **Project `.apmrc`** — Commit to version control with `${VAR}` references only. This documents what configuration your project needs without exposing secrets.

2. **Global `~/.apm/.apmrc`** — Store actual tokens here. This file is never committed and is protected with `0600` permissions.

3. **CI/CD** — Use `APM_CONFIG_*` environment variables to override settings in automated pipelines:
   ```yaml
   env:
     APM_CONFIG_REGISTRY: https://internal-registry.example.com
     APM_CONFIG_GITHUB_TOKEN: ${{ secrets.APM_TOKEN }}
   ```

## For npm Users

If you're familiar with `.npmrc`, `.apmrc` works similarly:

| `.npmrc` | `.apmrc` | Notes |
|----------|----------|-------|
| `registry=url` | `registry=url` | Same |
| `@scope:registry=url` | `@scope:registry=url` | Same |
| `//host/:_authToken=tok` | `//host/:_authToken=tok` | Same |
| `${VAR}` | `${VAR}` | Same |
| `\${VAR}` | `\${VAR}` | Same (backslash escaping) |
| `npm_config_*` env vars | `APM_CONFIG_*` env vars | Same convention |
| `~/.npmrc` | `~/.apm/.apmrc` | Different path |

APM additionally supports `${VAR:-default}`, `${VAR?}`, and `${VAR:+word}` substitution forms that `.npmrc` does not.

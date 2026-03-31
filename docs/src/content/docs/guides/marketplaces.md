---
title: "Marketplaces"
sidebar:
  order: 5
---

Marketplaces are curated indexes of plugins hosted as GitHub repositories. Each marketplace contains a `marketplace.json` file that maps plugin names to source locations. APM resolves these entries to Git URLs, so plugins installed from marketplaces get the same version locking, security scanning, and governance as any other APM dependency.

## How marketplaces work

A marketplace is a GitHub repository with a `marketplace.json` at its root. The file lists plugins with their source type and location:

```json
{
  "plugins": {
    "code-review": {
      "type": "github",
      "source": "acme/code-review-plugin"
    },
    "style-guide": {
      "type": "url",
      "source": "https://github.com/acme/style-guide.git"
    },
    "eslint-rules": {
      "type": "git-subdir",
      "source": "acme/monorepo/plugins/eslint-rules"
    },
    "local-tools": {
      "type": "relative",
      "source": "./tools/local-plugin"
    }
  }
}
```

Both Copilot CLI and Claude Code `marketplace.json` formats are supported. APM normalizes entries from either format into its canonical dependency representation.

### Supported source types

| Type | Description | Example |
|------|-------------|---------|
| `github` | GitHub `owner/repo` shorthand | `acme/code-review-plugin` |
| `url` | Full HTTPS or SSH Git URL | `https://github.com/acme/style-guide.git` |
| `git-subdir` | Subdirectory within a Git repository | `acme/monorepo/plugins/eslint-rules` |
| `relative` | Local filesystem path | `./tools/local-plugin` |

npm sources are not supported.

## Register a marketplace

```bash
apm marketplace add acme/plugin-marketplace
```

This registers the marketplace and fetches its `marketplace.json`. By default APM tracks the `main` branch.

**Options:**
- `--name/-n` -- Custom display name for the marketplace
- `--branch/-b` -- Branch to track (default: `main`)

```bash
# Register with a custom name on a specific branch
apm marketplace add acme/plugin-marketplace --name "Acme Plugins" --branch release
```

## List registered marketplaces

```bash
apm marketplace list
```

Shows all registered marketplaces with their source repository and branch.

## Browse plugins

View all plugins available in a specific marketplace:

```bash
apm marketplace browse acme-plugins
```

## Search across marketplaces

Search plugins by name or description across all registered marketplaces:

```bash
apm search "code review"
```

**Options:**
- `--limit` -- Maximum results to return (default: 20)

```bash
apm search "linting" --limit 5
```

## Install from a marketplace

Use the `NAME@MARKETPLACE` syntax to install a plugin from a specific marketplace:

```bash
apm install code-review@acme-plugins
```

APM resolves the plugin name against the marketplace index, fetches the underlying Git repository, and installs it as a standard APM dependency. The resolved source appears in `apm.yml` and `apm.lock.yaml` just like any direct dependency.

For full `apm install` options, see [CLI Commands](../../reference/cli-commands/).

## Provenance tracking

Marketplace-resolved plugins are tracked in `apm.lock.yaml` with full provenance:

```yaml
apm_modules:
  acme/code-review-plugin:
    resolved: https://github.com/acme/code-review-plugin#main
    commit: abc123def456789
    marketplace: acme-plugins
```

The `marketplace` field records which marketplace was used for discovery. The `resolved` URL and `commit` pin the exact version, so builds remain reproducible regardless of marketplace availability.

## Cache behavior

APM caches marketplace indexes locally with a 1-hour TTL. Within that window, commands like `search` and `browse` use the cached index. After expiry, APM fetches a fresh copy in the background (stale-while-revalidate) so commands remain fast.

Force a cache refresh:

```bash
# Refresh a specific marketplace
apm marketplace update acme-plugins

# Refresh all registered marketplaces
apm marketplace update
```

## Manage marketplaces

Remove a registered marketplace:

```bash
apm marketplace remove acme-plugins

# Skip confirmation prompt
apm marketplace remove acme-plugins --yes
```

Removing a marketplace does not uninstall plugins previously installed from it. Those plugins remain pinned in `apm.lock.yaml` to their resolved Git sources.

---
title: "Authentication"
sidebar:
  order: 4
---

APM works without tokens for public packages on github.com. Authentication is needed for private repositories, enterprise hosts (`*.ghe.com`, GHES), and Azure DevOps.

## How APM resolves authentication

APM resolves tokens per `(host, org)` pair. For each dependency, it walks a resolution chain until it finds a token:

1. **Per-org env var** — `GITHUB_APM_PAT_{ORG}` (checked for any host)
2. **Global env vars** — `GITHUB_APM_PAT` → `GITHUB_TOKEN` → `GH_TOKEN` (default host only)
3. **Git credential helper** — `git credential fill` (any host except ADO)

If nothing matches, APM attempts unauthenticated access (works for public repos on github.com).

Results are cached per-process — the same `(host, org)` pair is resolved once.

### Security constraint

Global env vars (`GITHUB_APM_PAT`, `GITHUB_TOKEN`, `GH_TOKEN`) only apply to the default host (github.com unless `GITHUB_HOST` is set). Non-default hosts resolve via per-org env vars or git credentials. APM never sends a github.com token to an enterprise host.

## Token lookup

| Priority | Variable | Scope | Notes |
|----------|----------|-------|-------|
| 1 | `GITHUB_APM_PAT_{ORG}` | Per-org, any host | Org name uppercased, hyphens → underscores |
| 2 | `GITHUB_APM_PAT` | Default host only | github.com unless `GITHUB_HOST` overrides |
| 3 | `GITHUB_TOKEN` | Default host only | Shared with GitHub Actions |
| 4 | `GH_TOKEN` | Default host only | Set by `gh auth login` |
| 5 | `git credential fill` | Per-host | System credential manager, `gh auth`, OS keychain |

For Azure DevOps, the only token source is `ADO_APM_PAT`.

For JFrog Artifactory, use `ARTIFACTORY_APM_TOKEN`.

For runtime features (`GITHUB_COPILOT_PAT`), see [Agent Workflows](../../guides/agent-workflows/).

## Multi-org setup

When your manifest pulls from multiple GitHub organizations, use per-org env vars:

```bash
export GITHUB_APM_PAT_CONTOSO=ghp_token_for_contoso
export GITHUB_APM_PAT_FABRIKAM=ghp_token_for_fabrikam
```

The org name comes from the dependency reference — `contoso/my-package` checks `GITHUB_APM_PAT_CONTOSO`. Naming rules:

- Uppercase the org name
- Replace hyphens with underscores
- `contoso-microsoft` → `GITHUB_APM_PAT_CONTOSO_MICROSOFT`

Per-org tokens take priority over global tokens. Use this when different orgs require different PATs (e.g., separate SSO authorizations).

## Enterprise Managed Users (EMU)

EMU orgs can live on **github.com** (e.g., `contoso-microsoft`) or on **GHE Cloud Data Residency** (`*.ghe.com`). EMU tokens (`ghu_` prefix) are enterprise-scoped and cannot access public repos on github.com.

If your manifest mixes enterprise and public packages, use separate tokens:

```bash
export GITHUB_APM_PAT_CONTOSO_MICROSOFT=ghu_emu_token  # EMU org (any host)
export GITHUB_APM_PAT=ghp_public_token                  # public github.com repos
```

### GHE Cloud Data Residency (`*.ghe.com`)

`*.ghe.com` hosts are always auth-required — there are no public repos. APM skips the unauthenticated attempt entirely for these hosts:

```bash
export GITHUB_APM_PAT_MYENTERPRISE=ghp_enterprise_token
apm install myenterprise.ghe.com/platform/standards
```

## GitHub Enterprise Server (GHES)

Set `GITHUB_HOST` to your GHES instance. Bare package names resolve against this host:

```bash
export GITHUB_HOST=github.company.com
export GITHUB_APM_PAT_MYORG=ghp_ghes_token
apm install myorg/internal-package  # → github.company.com/myorg/internal-package
```

Use full hostnames for packages on other hosts:

```yaml
dependencies:
  apm:
    - team/internal-package                   # → GITHUB_HOST
    - github.com/public/open-source-package   # → github.com
```

Global env vars apply to whichever host `GITHUB_HOST` points to. Alternatively, skip env vars and configure `git credential fill` for your GHES host.

## Azure DevOps

```bash
export ADO_APM_PAT=your_ado_pat
apm install dev.azure.com/myorg/myproject/myrepo
```

ADO is always auth-required. Uses 3-segment paths (`org/project/repo`). No `ADO_HOST` equivalent — always use FQDN syntax:

```bash
apm install dev.azure.com/myorg/myproject/myrepo#main
apm install mycompany.visualstudio.com/org/project/repo  # legacy URL
```

Create the PAT at `https://dev.azure.com/{org}/_usersSettings/tokens` with **Code (Read)** permission.

## Troubleshooting

### Rate limits on github.com

APM tries unauthenticated access first for public repos to conserve rate limits. If you hit limits, set any token:

```bash
export GITHUB_TOKEN=ghp_any_valid_token
```

### SSO-protected organizations

Authorize your PAT for SSO at [github.com/settings/tokens](https://github.com/settings/tokens) — click **Configure SSO** next to the token.

### EMU token can't access public repos

EMU tokens (`ghu_` prefix) are enterprise-scoped and cannot access public github.com repos. Use a standard PAT for public repos alongside your EMU token — see [Enterprise Managed Users (EMU)](#enterprise-managed-users-emu) above.

### Diagnosing auth failures

Run with `--verbose` to see the full resolution chain:

```bash
apm install --verbose your-org/package
```

The output shows which env var matched (or `none`), the detected token type (`fine-grained`, `classic`, `emu`), and the host classification (`github`, `ghe_cloud`, `ghes`, `ado`, `generic`).

### Git credential helper not found

APM calls `git credential fill` as a fallback (60s timeout). If your credential helper needs more time (e.g., Windows account picker), set `APM_GIT_CREDENTIAL_TIMEOUT` (seconds, max 180):

```bash
export APM_GIT_CREDENTIAL_TIMEOUT=120
```

Ensure a credential helper is configured:

```bash
git config credential.helper              # check current helper
git config --global credential.helper osxkeychain  # macOS
gh auth login                              # GitHub CLI
```

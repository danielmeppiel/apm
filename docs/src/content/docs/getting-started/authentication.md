---
title: "Authentication"
sidebar:
  order: 3
---

APM works without any tokens for public packages. Authentication is only needed for private repositories and enterprise hosts.

## Token Configuration

| Variable | Purpose | When Needed |
|----------|---------|-------------|
| `GITHUB_APM_PAT` | Private GitHub/GHE repos | Private GitHub packages |
| `ADO_APM_PAT` | Private Azure DevOps repos | Private ADO packages |
| `GITHUB_COPILOT_PAT` | Copilot runtime | `apm run` with Copilot |
| `GITHUB_HOST` | Default host for bare package names | GitHub Enterprise setups |

### GITHUB_APM_PAT

```bash
export GITHUB_APM_PAT=ghp_finegrained_token_here
```

- **Purpose**: Access to private APM modules on GitHub/GitHub Enterprise
- **Type**: Fine-grained Personal Access Token (org or user-scoped)
- **Permissions**: Repository read access to repositories you want to install from

### ADO_APM_PAT

```bash
export ADO_APM_PAT=your_ado_pat
```

- **Purpose**: Access to private APM modules on Azure DevOps
- **Type**: Azure DevOps Personal Access Token
- **Permissions**: Code (Read) scope

### GITHUB_COPILOT_PAT

```bash
export GITHUB_COPILOT_PAT=ghp_copilot_token
```

- **Purpose**: Authentication for `apm run` with Copilot runtime
- **Type**: Personal Access Token with Copilot access
- **Fallback**: Falls back to `GITHUB_TOKEN` if not set

### GITHUB_HOST

```bash
export GITHUB_HOST=github.company.com
```

- **Purpose**: Set default host for bare package names (e.g., `owner/repo`)
- **Default**: `github.com`
- **Note**: Azure DevOps has no equivalent — always use FQDN syntax (e.g., `dev.azure.com/org/project/repo`)

## Common Setup Scenarios

#### Public Modules Only (Most Users)

```bash
# No tokens needed — just works!
apm install microsoft/apm-sample-package
```

#### Private GitHub Modules

```bash
export GITHUB_APM_PAT=ghp_org_token
```

#### Private Azure DevOps Modules

```bash
export ADO_APM_PAT=your_ado_pat
# Always use FQDN syntax for ADO
apm install dev.azure.com/org/project/repo
```

#### GitHub Enterprise as Default

```bash
export GITHUB_HOST=github.company.com
export GITHUB_APM_PAT=ghp_enterprise_token
# Now bare packages resolve to your enterprise
apm install team/package  # → github.company.com/team/package
```

#### Running Prompts

```bash
export GITHUB_COPILOT_PAT=ghp_copilot_token
```

## GitHub Enterprise Support

APM supports all GitHub Enterprise deployment models via `GITHUB_HOST`.

```bash
# GitHub Enterprise Server
export GITHUB_HOST=github.company.com
apm install team/package  # → github.company.com/team/package

# GitHub Enterprise Cloud with Data Residency
export GITHUB_HOST=myorg.ghe.com
apm install platform/standards  # → myorg.ghe.com/platform/standards

# Multiple instances: Use FQDN for explicit hosts
apm install partner.ghe.com/external/integration  # FQDN always works
apm install github.com/public/open-source-package
```

> **Important:** When `GITHUB_HOST` is set, **all** bare package names (e.g., `owner/repo`) resolve against that host. To reference packages on a different server, use the full hostname (FQDN) in your `apm.yml`:
> ```yaml
> dependencies:
>   apm:
>   - team/internal-package                          # → goes to GITHUB_HOST
>   - github.com/public/open-source-package           # → goes to github.com
> ```

## Azure DevOps Support

APM supports Azure DevOps Services (cloud) and Azure DevOps Server (self-hosted). There is no `ADO_HOST` equivalent — Azure DevOps always requires FQDN syntax.

### URL Format

Azure DevOps uses 3 segments vs GitHub's 2:
- **GitHub**: `owner/repo`
- **Azure DevOps**: `org/project/repo`

```bash
# Both formats work (the _git segment is optional):
apm install dev.azure.com/myorg/myproject/myrepo
apm install dev.azure.com/myorg/myproject/_git/myrepo

# With git reference
apm install dev.azure.com/myorg/myproject/myrepo#main

# Legacy visualstudio.com URLs
apm install mycompany.visualstudio.com/myorg/myproject/myrepo

# Self-hosted Azure DevOps Server
apm install ado.company.internal/myorg/myproject/myrepo

# Virtual packages (individual files)
apm install dev.azure.com/myorg/myproject/myrepo/prompts/code-review.prompt.md
```

## Token Creation Guide

1. **GITHUB_APM_PAT** (Private GitHub modules):
   - Go to [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new)
   - Select "Fine-grained Personal Access Token"
   - Scope: Organization or Personal account (as needed)
   - Permissions: Repository read access

2. **ADO_APM_PAT** (Private ADO modules):
   - Go to `https://dev.azure.com/{org}/_usersSettings/tokens`
   - Create PAT with **Code (Read)** scope

3. **GITHUB_COPILOT_PAT** (Running prompts):
   - Go to [github.com/settings/tokens](https://github.com/settings/tokens)
   - Create token with Copilot access

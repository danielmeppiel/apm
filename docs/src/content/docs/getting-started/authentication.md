---
title: "Authentication"
sidebar:
  order: 4
---

APM works without any tokens for public packages. Authentication is only needed for private repositories and enterprise hosts.

## How APM Authenticates

APM resolves dependencies either via `git clone` (for full packages) or the GitHub API (for individual files). Authentication depends on the host:

| Host | Token variable | How it's used |
|------|---------------|---------------|
| GitHub.com / GitHub Enterprise (`*.ghe.com`) | `GITHUB_APM_PAT` → `GITHUB_TOKEN` → `GH_TOKEN` | Injected into the HTTPS URL as `x-access-token` |
| Azure DevOps | `ADO_APM_PAT` | Injected into the HTTPS URL as the password |
| JFrog Artifactory | `ARTIFACTORY_APM_TOKEN` | Bearer token in HTTP `Authorization` header |
| Any other git host (including GitHub Enterprise on custom domains) | — | Delegated to **git credential helpers** or SSH keys |

When APM has a token for a recognized host (GitHub.com, GitHub Enterprise under `*.ghe.com`, or Azure DevOps), it injects it directly and disables interactive prompts. When no token is available, or the host is treated as generic (including GitHub Enterprise on custom domains), APM relaxes the git environment so your existing credential helpers — `gh auth`, macOS Keychain, Windows Credential Manager, `git-credential-store`, etc. — can provide credentials transparently.

For single-file downloads from GitHub (which use the GitHub API rather than `git clone`), APM also queries `git credential fill` as a last-resort fallback when no token environment variable is set. This means credentials stored by `gh auth login` or your OS keychain work for both folder-level and file-level dependencies.

`git credential fill` can trigger interactive account selection on some systems. APM waits up to 60 seconds by default for this step. If your credential helper is slower, set `APM_GIT_CREDENTIAL_TIMEOUT` (seconds, max 180).

### Object-style `git:` references

The `git:` object form in `apm.yml` lets you reference any git URL explicitly — HTTPS, SSH, or any host:

```yaml
dependencies:
  apm:
    - git: https://gitlab.com/acme/coding-standards.git
      path: instructions/security
      ref: v2.0
    - git: git@bitbucket.org:team/rules.git
      path: prompts/review.prompt.md
```

Authentication for these URLs follows the same rules: APM uses `GITHUB_APM_PAT` / `ADO_APM_PAT` for recognized hosts (GitHub.com and GitHub Enterprise under `*.ghe.com`, Azure DevOps), and falls back to your git credential helpers or SSH keys for everything else (including GitHub Enterprise on custom domains). If your GitLab, Bitbucket, GitHub Enterprise, or self-hosted git server is already configured in `~/.gitconfig` or your SSH agent, APM will work without any additional setup.

## Token Reference

### GITHUB_APM_PAT

```bash
export GITHUB_APM_PAT=github_pat_finegrained_token_here
```

- **Scope**: Private repositories on GitHub.com and GitHub Enterprise instances under `*.ghe.com`
- **Type**: [Fine-grained PAT](https://github.com/settings/personal-access-tokens/new) (org or user-scoped)
- **Permissions**: Repository read access
- **Fallback**: `GITHUB_TOKEN` (e.g., in GitHub Actions), then `GH_TOKEN` (used by the GitHub CLI)

### ADO_APM_PAT

```bash
export ADO_APM_PAT=your_ado_pat
```

- **Scope**: Private repositories on Azure DevOps
- **Type**: PAT created at `https://dev.azure.com/{org}/_usersSettings/tokens`
- **Permissions**: Code (Read)

### GITHUB_COPILOT_PAT

```bash
export GITHUB_COPILOT_PAT=ghp_copilot_token
```

- **Scope**: Runtime features (see [Agent Workflows](../../guides/agent-workflows/))
- **Fallback**: `GITHUB_APM_PAT`, then `GITHUB_TOKEN` (e.g., in GitHub Actions)

### GITHUB_HOST

```bash
export GITHUB_HOST=github.company.com
```

- **Purpose**: Set default host for bare package names (e.g., `owner/repo`)
- **Default**: `github.com`
- **Note**: Azure DevOps has no equivalent — always use FQDN syntax

## Common Setup Scenarios

#### Public Packages (No Setup)

```bash
apm install microsoft/apm-sample-package
```

#### Private GitHub Packages

```bash
export GITHUB_APM_PAT=ghp_org_token
apm install your-org/private-package
```

#### Private Azure DevOps Packages

```bash
export ADO_APM_PAT=your_ado_pat
apm install dev.azure.com/org/project/repo
```

#### GitHub Enterprise

```bash
export GITHUB_HOST=github.company.com
export GITHUB_APM_PAT=ghp_enterprise_token
apm install team/package  # → github.company.com/team/package
```

> When `GITHUB_HOST` is set, **all** bare package names resolve against that host. Use full hostnames for packages on other servers:
> ```yaml
> dependencies:
>   apm:
>     - team/internal-package                   # → GITHUB_HOST
>     - github.com/public/open-source-package   # → github.com
> ```

#### GitLab, Bitbucket, or Self-Hosted Git

No APM-specific token is needed. Configure access using your standard git setup:

```yaml
# SSH — if your key is in the SSH agent, it just works
- git: git@gitlab.com:acme/standards.git

# HTTPS — relies on git credential helpers
- git: https://gitlab.com/acme/standards.git
```

To configure HTTPS credentials for a generic host, use any standard git credential helper:

```bash
# gh CLI (GitHub-compatible forges)
gh auth login

# Git credential store (any host)
git credential approve <<EOF
protocol=https
host=gitlab.com
username=your-username
password=glpat-your-token
EOF
```

#### Runtime Features

See the [Agent Workflows guide](../../guides/agent-workflows/) for `GITHUB_COPILOT_PAT` setup.

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
apm install partner.ghe.com/external/integration
apm install github.com/public/open-source-package
```

## Azure DevOps Support

APM supports Azure DevOps Services (cloud) and Azure DevOps Server (self-hosted). There is no `ADO_HOST` equivalent — always use FQDN syntax.

Azure DevOps uses 3 path segments vs GitHub's 2:

```bash
apm install dev.azure.com/myorg/myproject/myrepo
apm install dev.azure.com/myorg/myproject/_git/myrepo   # _git is optional
apm install dev.azure.com/myorg/myproject/myrepo#main   # with ref
apm install mycompany.visualstudio.com/org/project/repo # legacy URL
apm install ado.internal/myorg/myproject/myrepo          # self-hosted
```

## JFrog Artifactory Support

APM supports [JFrog Artifactory VCS Remote Repositories](https://jfrog.com/help/r/jfrog-artifactory-documentation/vcs-repositories) as a package source. Artifactory downloads use zip archives instead of git clone.

#### Mode 1: Explicit FQDN

```bash
apm install artifactory.example.com/artifactory/github/owner/repo
apm install artifactory.example.com/artifactory/github/owner/repo#v1.0.0
```

#### Mode 2: Transparent Proxy

Set `ARTIFACTORY_BASE_URL` to route all GitHub package downloads through Artifactory:

```bash
export ARTIFACTORY_BASE_URL=https://artifactory.example.com/artifactory/github
apm install owner/repo  # fetched via Artifactory
```

#### Air-Gapped Mode

Block all direct git operations and route everything through Artifactory:

```bash
export ARTIFACTORY_BASE_URL=https://artifactory.example.com/artifactory/github
export ARTIFACTORY_ONLY=1
```

#### Authentication

```bash
export ARTIFACTORY_APM_TOKEN=your-api-key-or-token
```

> **Note:** Artifactory downloads use zip archives, so `apm.lock` will not contain commit SHAs for Artifactory-sourced packages.

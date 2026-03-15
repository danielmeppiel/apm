---
title: "Private Packages"
description: "Create, host, and install APM packages from private repositories on GitHub, Azure DevOps, or any git host."
sidebar:
  order: 8
---

APM installs packages directly from git repositories. Private packages work the same way as public ones — you make the repository private on your git host, configure an access token, and run `apm install` as usual.

## How it works

APM resolves package references to git URLs. When the repository is private, APM authenticates using a Personal Access Token (PAT) stored in an environment variable. No registry, no publish step — a private repo is all you need.

## 1. Create the package

A private APM package is a regular git repository with an `apm.yml` manifest.

```bash
apm init my-private-package
cd my-private-package
```

Add your content to `.apm/instructions/`, `.apm/prompts/`, `.apm/agents/`, etc. Then push to a **private** repository on your git host.

```bash
git init
git add .
git commit -m "Initial APM package"
git remote add origin https://github.com/your-org/my-private-package.git
git push -u origin main
```

Set the repository to **private** in your git host's settings.

## 2. Configure authentication

### GitHub / GitHub Enterprise

Create a [fine-grained Personal Access Token](https://github.com/settings/personal-access-tokens/new) with **Repository read** access, then export it:

```bash
export GITHUB_APM_PAT=ghp_your_token_here
```

For GitHub Enterprise, also set the host:

```bash
export GITHUB_HOST=github.your-company.com
export GITHUB_APM_PAT=ghp_enterprise_token
```

### Azure DevOps

Create a PAT with **Code (Read)** scope at `https://dev.azure.com/{org}/_usersSettings/tokens`:

```bash
export ADO_APM_PAT=your_ado_pat
```

See the [Authentication guide](../../getting-started/authentication/) for the full token creation walkthrough.

## 3. Install the package

Once the token is set, install like any other package:

```bash
# GitHub
apm install your-org/my-private-package

# GitHub Enterprise
apm install your-org/my-private-package   # resolves via GITHUB_HOST

# Azure DevOps
apm install dev.azure.com/org/project/my-private-package

# Explicit HTTPS URL (always works for any host)
apm install git: https://github.com/your-org/my-private-package.git
```

Or declare it in `apm.yml`:

```yaml
name: my-project
version: 1.0.0
dependencies:
  apm:
    - your-org/my-private-package@v1.0.0
```

```bash
apm install
```

## 4. Share with your team

Every developer who needs the package must have the token set in their shell environment (or their `.bashrc` / `.zshrc`):

```bash
export GITHUB_APM_PAT=ghp_token_with_read_access
```

For teams, a fine-grained token scoped to the organization or a service account PAT works well. Grant repository read access to the private repository — no write access is required.

## 5. Use in CI/CD

Store the token as a secret in your CI environment and inject it at install time.

### GitHub Actions

```yaml
- name: Install APM dependencies
  run: apm install
  env:
    GITHUB_APM_PAT: ${{ secrets.GITHUB_APM_PAT }}
```

### Azure Pipelines

```yaml
- script: apm install
  env:
    GITHUB_APM_PAT: $(GITHUB_APM_PAT)
```

### Generic CI

```bash
export GITHUB_APM_PAT="${CI_SECRET_APM_PAT}"
apm install
```

See the [CI/CD guide](../../integrations/ci-cd/) for more pipeline patterns.

## Org-wide private packages

For teams that want a shared, centrally-maintained private package, the pattern is the same as the [Org-Wide Packages guide](../../guides/org-packages/) — just keep the repository private and distribute access via a PAT scoped to the organization.

```yaml
# Each repo in the org depends on the private standards package
dependencies:
  apm:
    - acme-corp/private-standards@v1.0.0
```

Developers and CI jobs with a token that has read access to `acme-corp/private-standards` can install it without any other configuration.

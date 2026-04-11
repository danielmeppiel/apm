# Dependency Reference

## String forms (in apm.yml `dependencies.apm`)

```yaml
dependencies:
  apm:
    # GitHub shorthand
    - microsoft/apm-sample-package
    - microsoft/apm-sample-package#v1.0.0       # pinned tag
    - microsoft/apm-sample-package#main          # branch
    - microsoft/apm-sample-package#abc123d       # commit SHA (7-40 hex)

    # HTTPS URLs (any git host)
    - https://github.com/microsoft/apm-sample-package.git
    - https://gitlab.com/acme/coding-standards.git

    # SSH URLs
    - git@github.com:microsoft/apm-sample-package.git
    - git@gitlab.com:group/subgroup/repo.git

    # FQDN shorthand (non-GitHub hosts keep the domain)
    - gitlab.com/acme/coding-standards
    - gitlab.com/group/subgroup/repo

    # Azure DevOps
    - dev.azure.com/org/project/_git/repo

    # Local paths (development only)
    - ./packages/my-shared-skills
    - ../sibling-repo/my-package
```

## Object form (complex cases)

```yaml
- git: https://gitlab.com/acme/repo.git
  path: instructions/security                   # virtual sub-path
  ref: v2.0                                     # tag, branch, or SHA
  alias: acme-sec                               # local alias

- git: git@gitlab.com:group/subgroup/repo.git
  path: prompts/review.prompt.md

- path: ./packages/my-skills                    # local only
```

## Virtual package types

Virtual packages reference a subset of a repository.

| Type | Detection rule | Example |
|------|---------------|---------|
| File | Ends in `.prompt.md`, `.instructions.md`, `.agent.md`, `.chatmode.md` | `owner/repo/prompts/review.prompt.md` |
| Collection (dir) | Contains `/collections/` (no extension) | `owner/repo/collections/security` |
| Collection (manifest) | Contains `/collections/` + `.collection.yml` | `owner/repo/collections/security.collection.yml` |
| Subdirectory | Does not match file or collection rules | `owner/repo/skills/security` |

## Canonical storage rules

APM normalizes dependency strings when saving to apm.yml:

| Input | Stored as |
|-------|-----------|
| `microsoft/apm-sample-package` | `microsoft/apm-sample-package` |
| `https://github.com/microsoft/apm-sample-package.git` | `microsoft/apm-sample-package` |
| `git@github.com:microsoft/apm-sample-package.git` | `microsoft/apm-sample-package` |
| `https://gitlab.com/acme/rules.git` | `gitlab.com/acme/rules` |
| Object with `git` + `path: docs` + `ref: main` | `org/repo/docs#main` |
| `./packages/my-skills` | `./packages/my-skills` |

GitHub URLs are stripped to shorthand; non-GitHub hosts keep the FQDN.

## MCP dependency formats

```yaml
dependencies:
  mcp:
    # Registry reference (string)
    - io.github.github/github-mcp-server

    # Registry with overlays (object)
    - name: io.github.github/github-mcp-server
      transport: stdio                          # stdio|sse|http|streamable-http
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      args: ["--port", "3000"]
      version: "1.5.0"
      package: npm                              # npm|pypi|oci
      headers:
        X-Custom: "value"
      tools: ["repos", "issues"]

    # Self-defined server (not in registry)
    - name: my-private-server
      registry: false
      transport: stdio
      command: ./bin/my-server
      args: ["--port", "3000"]
      env:
        API_KEY: ${{ secrets.KEY }}

    # Self-defined HTTP server
    - name: internal-kb
      registry: false
      transport: http
      url: "https://mcp.internal.example.com"
```

## Version pinning

| Strategy | Syntax | When to use |
|----------|--------|-------------|
| Tag | `owner/repo#v1.0.0` | Production -- immutable reference |
| Branch | `owner/repo#main` | Development -- tracks latest |
| Commit SHA | `owner/repo#abc123d` | Maximum reproducibility |
| No ref | `owner/repo` | Resolves default branch at install time |
| Marketplace semver | `plugin@marketplace#^2.0.0` | Marketplace plugins with `versions[]` |

## Marketplace version specifiers

When a marketplace plugin declares `versions[]`, the `#` suffix is a semver range:

| Specifier | Meaning | Example |
|-----------|---------|---------|
| `2.0.0` | Exact version | `plugin@mkt#2.0.0` |
| `^2.0.0` | Compatible (`>=2.0.0, <3.0.0`) | `plugin@mkt#^2.0.0` |
| `~2.1.0` | Patch-level (`>=2.1.0, <2.2.0`) | `plugin@mkt#~2.1.0` |
| `>=1.5.0` | Minimum version | `plugin@mkt#>=1.5.0` |
| `>=1.0.0,<3.0.0` | Compound range | `plugin@mkt#>=1.0.0,<3.0.0` |
| *(omitted)* | Latest version | `plugin@mkt` |

Plugins without `versions[]` continue using the source-level ref (backward compatible).

## What the lockfile pins

`apm.lock.yaml` records the exact commit SHA for every dependency, regardless
of the ref format in apm.yml. Running `apm install` without `--update` always
uses the locked SHA, ensuring reproducible installs across machines.

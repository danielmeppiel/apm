# `apm.yml` Manifest Specification

> **Version:** 0.1 &nbsp;|&nbsp; **Status:** Draft &nbsp;|&nbsp; **Format:** YAML 1.2

The `apm.yml` manifest declares the full closure of agent primitive dependencies, MCP servers, scripts, and compilation settings for a project. It is the contract between package authors, runtimes, and integrators — any conforming resolver can consume this format to install, compile, and run agentic workflows.

---

## Document Structure

```yaml
# apm.yml
name:          <string>                  # REQUIRED
version:       <string>                  # REQUIRED
description:   <string>
author:        <string>
license:       <string>
target:        <enum>
type:          <enum>
scripts:       <map<string, string>>
dependencies:
  apm:         <list<ApmDependency>>
  mcp:         <list<McpDependency>>
compilation:   <CompilationConfig>
```

---

## Top-Level Fields

### `name`

| | |
|---|---|
| **Type** | `string` |
| **Required** | Yes |
| **Description** | Package identifier. Free-form string (no pattern enforced at parse time). Convention: alphanumeric, dots, hyphens, underscores. |

### `version`

| | |
|---|---|
| **Type** | `string` |
| **Required** | Yes |
| **Pattern** | `^\d+\.\d+\.\d+` (semver; pre-release/build suffixes allowed) |
| **Description** | Semantic version. A value that does not match the pattern produces a validation warning (non-blocking). |

### `description`

| | |
|---|---|
| **Type** | `string` |
| **Required** | No |
| **Description** | Brief human-readable description. |

### `author`

| | |
|---|---|
| **Type** | `string` |
| **Required** | No |
| **Description** | Package author or organization. |

### `license`

| | |
|---|---|
| **Type** | `string` |
| **Required** | No |
| **Description** | SPDX license identifier (e.g. `MIT`, `Apache-2.0`). |

### `target`

| | |
|---|---|
| **Type** | `enum<string>` |
| **Required** | No |
| **Default** | Auto-detect: `vscode` if `.github/` exists, `claude` if `.claude/` exists, `all` if both, `minimal` if neither |
| **Allowed values** | `vscode` · `agents` · `claude` · `all` |

Controls which output targets are generated during compilation. When unset, the CLI auto-detects based on `.github/` and `.claude/` folder presence. Unknown values are silently ignored (auto-detection takes over).

| Value | Effect |
|---|---|
| `vscode` | Emits `AGENTS.md` at the project root (and per-directory files in distributed mode) |
| `agents` | Alias for `vscode` |
| `claude` | Emits `CLAUDE.md` at the project root |
| `all` | Both `vscode` and `claude` targets |
| `minimal` | AGENTS.md only at project root (fallback when no `.github/` or `.claude/` detected) |

### `type`

| | |
|---|---|
| **Type** | `enum<string>` |
| **Required** | No |
| **Default** | None (unset — behaviour depends on package content) |
| **Allowed values** | `instructions` · `skill` · `hybrid` · `prompts` |

Declares how the package's content is processed during install and compile:

| Value | Behaviour |
|---|---|
| `instructions` | Compiled into AGENTS.md only. No skill directory created. |
| `skill` | Installed as a native skill only. No AGENTS.md output. |
| `hybrid` | Both AGENTS.md compilation and skill installation. |
| `prompts` | Commands/prompts only. No instructions or skills. |

### `scripts`

| | |
|---|---|
| **Type** | `map<string, string>` |
| **Required** | No |
| **Key pattern** | Script name (free-form string) |
| **Value** | Shell command string |
| **Description** | Named commands executed via `apm run <name>`. Supports `--param key=value` substitution. |

---

## `dependencies`

| | |
|---|---|
| **Type** | `object` |
| **Required** | No |
| **Allowed keys** | `apm`, `mcp` |

Contains two optional lists: `apm` for agent primitive packages and `mcp` for MCP servers. Each list entry is either a string shorthand or a typed object.

---

### `dependencies.apm` — `list<ApmDependency>`

Each element is one of two forms: **string** or **object**.

#### String Form

Grammar:

```
dependency = url_form | shorthand_form
url_form   = ("https://" | "http://" | "ssh://git@" | "git@") <clone-url>
shorthand_form = [host "/"] owner "/" repo ["/" virtual_path] ["#" ref] ["@" alias]
```

| Segment | Required | Pattern | Description |
|---|---|---|---|
| `host` | No | FQDN (e.g. `gitlab.com`) | Git host. Defaults to `github.com`. |
| `owner/repo` | **Yes** | `^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$` | Repository path. Nested groups supported for non-GitHub hosts (e.g. `gitlab.com/group/sub/repo`). |
| `virtual_path` | No | Path segments after repo | Subdirectory or file within the repo. See *Virtual Packages* below. |
| `ref` | No | Branch, tag, or commit SHA | Git reference. Commit SHAs matched by `^[a-f0-9]{7,40}$`. Semver tags matched by `^v?\d+\.\d+\.\d+`. |
| `alias` | No | `^[a-zA-Z0-9._-]+$` | Local alias for the dependency. Appears after `#ref` in the string. |

**Examples:**

```yaml
dependencies:
  apm:
    # GitHub shorthand (default host)
    - microsoft/apm-sample-package
    - microsoft/apm-sample-package#v1.0.0
    - microsoft/apm-sample-package@standards

    # Non-GitHub hosts (FQDN preserved)
    - gitlab.com/acme/coding-standards
    - bitbucket.org/team/repo#main

    # Full URLs
    - https://github.com/microsoft/apm-sample-package.git
    - http://github.com/microsoft/apm-sample-package.git
    - git@github.com:microsoft/apm-sample-package.git
    - ssh://git@github.com/microsoft/apm-sample-package.git

    # Virtual packages
    - ComposioHQ/awesome-claude-skills/brand-guidelines   # subdirectory
    - contoso/prompts/review.prompt.md                    # single file

    # Azure DevOps
    - dev.azure.com/org/project/_git/repo
```

#### Object Form

Required when the shorthand is ambiguous (e.g. nested-group repos with virtual paths).

| Field | Type | Required | Pattern / Constraint | Description |
|---|---|---|---|---|
| `git` | `string` | **Yes** | HTTPS URL, SSH URL, or FQDN shorthand | Clone URL of the repository. |
| `path` | `string` | No | Relative path within the repo | Subdirectory or file (virtual package). |
| `ref` | `string` | No | Branch, tag, or commit SHA | Git reference to checkout. |
| `alias` | `string` | No | `^[a-zA-Z0-9._-]+$` | Local alias. |

```yaml
- git: https://gitlab.com/acme/repo.git
  path: instructions/security
  ref: v2.0
  alias: acme-sec
```

#### Virtual Packages

A dependency that targets a subdirectory, file, or collection within a repository rather than the whole repo.

| Kind | Detection rule | Example |
|---|---|---|
| **File** | `virtual_path` ends in `.prompt.md`, `.instructions.md`, `.agent.md`, or `.chatmode.md` | `owner/repo/prompts/review.prompt.md` |
| **Collection (dir)** | `virtual_path` contains `/collections/` (no collection extension) | `owner/repo/collections/security` |
| **Collection (manifest)** | `virtual_path` contains `/collections/` and ends with `.collection.yml` or `.collection.yaml` | `owner/repo/collections/security.collection.yml` |
| **Subdirectory** | `virtual_path` does not match any file, collection, or extension rule above | `owner/repo/skills/security` |

#### Canonical Normalisation

Conforming writers MUST normalise entries to canonical form on write. `github.com` is the default host and is stripped; all other hosts are preserved as FQDN.

| Input | Canonical form |
|---|---|
| `https://github.com/microsoft/apm-sample-package.git` | `microsoft/apm-sample-package` |
| `git@github.com:microsoft/apm-sample-package.git` | `microsoft/apm-sample-package` |
| `gitlab.com/acme/repo` | `gitlab.com/acme/repo` |

---

### `dependencies.mcp` — `list<McpDependency>`

Each element is one of two forms: **string** or **object**.

#### String Form

A plain registry reference: `io.github.github/github-mcp-server`

#### Object Form

| Field | Type | Required | Constraint | Description |
|---|---|---|---|---|
| `name` | `string` | **Yes** | Non-empty | Server identifier (registry name or custom name). |
| `transport` | `enum<string>` | Conditional | `stdio` · `sse` · `http` · `streamable-http` | Transport protocol. **Required** when `registry: false`. |
| `env` | `map<string, string>` | No | | Environment variable overrides. |
| `args` | `dict` or `list` | No | | Dict for overlay variable overrides (registry), list for positional args (self-defined). |
| `version` | `string` | No | | Pin to a specific server version. |
| `registry` | `bool` or `string` | No | Default: `true` (public registry) | `false` = self-defined (private) server. String = custom registry URL. |
| `package` | `enum<string>` | No | `npm` · `pypi` · `oci` | Package manager type hint. |
| `headers` | `map<string, string>` | No | | Custom HTTP headers for remote endpoints. |
| `tools` | `list<string>` | No | Default: `["*"]` | Restrict which tools are exposed. |
| `url` | `string` | Conditional | | Endpoint URL. **Required** when `registry: false` and `transport` is `http`, `sse`, or `streamable-http`. |
| `command` | `string` | Conditional | | Binary path. **Required** when `registry: false` and `transport` is `stdio`. |

**Validation rules for self-defined servers (`registry: false`):**
- `transport` MUST be present.
- If `transport` is `stdio`, `command` MUST be present.
- If `transport` is `http`, `sse`, or `streamable-http`, `url` MUST be present.

```yaml
dependencies:
  mcp:
    # Registry reference (string)
    - io.github.github/github-mcp-server

    # Registry with overlays (object)
    - name: io.github.github/github-mcp-server
      tools: ["repos", "issues"]
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

    # Self-defined server (object, registry: false)
    - name: my-private-server
      registry: false
      transport: stdio
      command: ./bin/my-server
      args: ["--port", "3000"]
      env:
        API_KEY: ${{ secrets.KEY }}
```

---

## `compilation` — `CompilationConfig`

Optional section controlling `apm compile` behaviour. All fields have sensible defaults; omitting the entire section is valid.

| Field | Type | Default | Constraint | Description |
|---|---|---|---|---|
| `target` | `enum<string>` | `all` | `vscode` · `agents` · `claude` · `all` | Output target (same values as top-level `target`). Defaults to `all` when set explicitly in compilation config. |
| `strategy` | `enum<string>` | `distributed` | `distributed` · `single-file` | `distributed` generates per-directory AGENTS.md files. `single-file` generates one monolithic file. |
| `single_file` | `bool` | `false` | | Legacy alias. When `true`, overrides `strategy` to `single-file`. |
| `output` | `string` | `AGENTS.md` | File path | Custom output path for the compiled file. |
| `chatmode` | `string` | — | | Chatmode filter for compilation. |
| `resolve_links` | `bool` | `true` | | Resolve relative Markdown links in primitives. |
| `source_attribution` | `bool` | `true` | | Include source-file origin comments in compiled output. |
| `exclude` | `list<string>` or `string` | `[]` | Glob patterns | Directories to skip during compilation (e.g. `apm_modules/**`). |
| `placement` | `object` | — | | Placement tuning. See sub-fields below. |

#### `compilation.placement`

| Field | Type | Default | Description |
|---|---|---|---|
| `min_instructions_per_file` | `int` | `1` | Minimum instruction count to warrant a separate AGENTS.md file. |

```yaml
compilation:
  target: all
  strategy: distributed
  source_attribution: true
  exclude:
    - "apm_modules/**"
    - "tmp/**"
  placement:
    min_instructions_per_file: 1
```

---

## Complete Example

```yaml
name: my-project
version: 1.0.0
description: AI-native web application
author: Contoso
license: MIT
target: all
type: hybrid              # instructions | skill | hybrid | prompts

scripts:
  review: "copilot -p 'code-review.prompt.md'"
  impl:   "copilot -p 'implement-feature.prompt.md'"

dependencies:
  apm:
    - microsoft/apm-sample-package
    - gitlab.com/acme/coding-standards
    - git: https://gitlab.com/acme/repo.git
      path: instructions/security
      ref: v2.0
      alias: acme-sec
  mcp:
    - io.github.github/github-mcp-server
    - name: my-private-server
      registry: false
      transport: stdio
      command: ./bin/my-server
      env:
        API_KEY: ${{ secrets.KEY }}

compilation:
  target: all
  strategy: distributed
  exclude:
    - "apm_modules/**"
  placement:
    min_instructions_per_file: 1
```

---

## Lockfile Specification (`apm.lock`)

After successful dependency resolution, a conforming resolver MUST write a lockfile capturing the exact resolved state. The lockfile is a separate YAML file committed to version control.

### Structure

```yaml
lockfile_version: "1"
generated_at:     <ISO 8601 timestamp>
apm_version:      <string>
dependencies:                              # YAML list (not a map)
  - repo_url:        <string>              # Resolved clone URL
    host:            <string>              # Git host (optional, e.g. "gitlab.com")
    resolved_commit: <string>              # Full commit SHA
    resolved_ref:    <string>              # Branch/tag that was resolved
    version:         <string>              # Package version from its apm.yml
    virtual_path:    <string>              # Virtual package path (if applicable)
    is_virtual:      <bool>                # True for virtual (file/subdirectory) packages
    depth:           <int>                 # 1 = direct, 2+ = transitive
    resolved_by:     <string>              # Parent dependency (transitive only)
    deployed_files:  <list<string>>        # Workspace-relative paths of installed files
```

### Resolver Behaviour

1. **First install** — resolve all dependencies, write `apm.lock`.
2. **Subsequent installs** — read `apm.lock`, use locked commit SHAs. Skip download if local checkout already matches.
3. **`--update` flag** — re-resolve from `apm.yml`, overwrite lockfile.

---

## Integrator Contract

Any runtime adopting this format (e.g. GitHub Agentic Workflows, CI systems, IDEs) should implement these steps:

1. **Parse** — Read `apm.yml` as YAML. Validate the two required fields (`name`, `version`) and the `dependencies` object shape.
2. **Resolve `dependencies.apm`** — For each entry, clone/fetch the git repo (respecting `ref`), locate the `.apm/` directory (or virtual path), and extract primitives.
3. **Resolve `dependencies.mcp`** — For each entry, resolve from the MCP registry or validate self-defined transport config.
4. **Transitive resolution** — Resolved packages may contain their own `apm.yml` with further dependencies, forming a dependency tree. Resolve transitively. Conflicts are merged at instruction level (by `applyTo` pattern), not file level.
5. **Write lockfile** — Record exact commit SHAs and deployed file paths in `apm.lock` for reproducibility.

The schema (this document) is the contract. Implementations — resolver, downloader, installer, compiler — are decoupled. Each runtime builds its own against this spec.

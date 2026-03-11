---
title: "Migrating Existing Projects"
description: "Adopt APM in projects that already have AI agent configuration — without disruption."
sidebar:
  order: 5
---

Most teams adopting APM already have some form of AI agent configuration in place. This guide covers how to introduce APM into a project that already uses `.github/copilot-instructions.md`, `AGENTS.md`, `CLAUDE.md`, `.cursor-rules`, manually managed `.github/instructions/`, or plugin configurations — without breaking what already works.

## Before You Start

Take stock of what you currently have. Common configurations include:

| File / Directory | Purpose |
|---|---|
| `.github/copilot-instructions.md` | Repository-level Copilot instructions |
| `.github/instructions/*.md` | File-pattern or task-specific Copilot instructions |
| `AGENTS.md` | Agent instructions (Codex, multi-agent workflows) |
| `CLAUDE.md` | Claude Code project instructions |
| `.cursor-rules` or `.cursorrules` | Cursor IDE rules |
| `.aider*` files | Aider conventions |
| Plugin configs (MCP servers, tools) | Manually installed tool integrations |

If you have any of these, you are in the right place.

## What APM Will (and Will Not) Do

APM is additive. Running `apm init` and `apm compile` will never delete, overwrite, or modify your existing configuration files unless you explicitly ask it to. The compiled output targets (like `AGENTS.md` or `.github/copilot-instructions.md`) are clearly marked as generated, so there is no ambiguity about which files APM manages and which are yours.

If you later decide APM is not for you, delete `apm.yml` and `apm.lock` and your original files remain untouched.

## Step-by-Step Migration

### Step 1: Inventory Your Existing Config

List everything you currently have. A quick way to check:

```bash
ls -la .github/copilot-instructions.md .github/instructions/ \
      AGENTS.md CLAUDE.md .cursor-rules .cursorrules 2>/dev/null
```

Write down which files are hand-maintained and which are copy-pasted from other projects or team templates. The copy-pasted ones are your best candidates for replacing with shared APM packages.

### Step 2: Initialize APM

Run `apm init` in your project root:

```bash
apm init
```

This creates an `apm.yml` manifest alongside your existing files. Nothing is deleted or moved. If you already have an `apm.yml`, this step is a no-op.

Review the generated `apm.yml` — it will contain a basic structure with empty dependency and primitive sections ready for you to populate.

### Step 3: Wrap Existing Primitives (Optional)

If you have local instructions, prompts, or agent definitions that you want APM to manage, move them into the `.apm/` directory structure:

```
.apm/
├── instructions/
│   └── coding-standards.instructions.md
├── prompts/
│   └── review.prompt.md
└── agents/
    └── reviewer.agent.md
```

Then reference them in your `apm.yml`:

```yaml
prompts:
  - prompts/review.prompt.md

instructions:
  - instructions/coding-standards.instructions.md
```

This step is optional. APM also discovers files placed directly in `.github/instructions/` and other standard locations. Wrapping them in `.apm/` gives you explicit control over what gets compiled and where.

### Step 4: Add External Dependencies

Replace copy-pasted configuration with shared packages:

```bash
apm install microsoft/copilot-best-practices
apm install your-org/team-standards
```

Each package brings in versioned, maintained primitives instead of stale copies. Your `apm.yml` now tracks these as dependencies with pinned versions in `apm.lock`.

### Step 5: Compile and Verify

Run compilation to see what APM would generate:

```bash
apm compile --verbose --dry-run
```

The `--dry-run` flag shows you the output without writing any files. Compare it against your current `AGENTS.md` or other target files. The compiled output should match or improve on what you had before.

When satisfied, run without `--dry-run`:

```bash
apm compile
```

Review the generated files. If a compiled file conflicts with a hand-maintained one, APM will warn you. You decide whether to let APM manage that file or keep your manual version.

### Step 6: Commit the Manifest

Add the APM manifest and lock file to version control:

```bash
git add apm.yml apm.lock
git commit -m "Add APM manifest for agent configuration management"
```

Your teammates can now run `apm install` followed by `apm compile` to get an identical setup. No more copy-pasting configuration between repositories or Slack threads.

### Step 7: Gradually Convert

You do not need to migrate everything at once. A practical approach:

1. Start with `apm install` for external packages only — keep all local config manual.
2. Move one or two local files into `.apm/` and verify the compiled output.
3. Over time, convert remaining hand-maintained files as you gain confidence.
4. Eventually, your `apm.yml` becomes the single source of truth for all agent configuration.

There is no deadline. APM and manual configuration coexist indefinitely.

## Common Migration Patterns

### From Manual copilot-instructions.md

**Before:** A hand-maintained `.github/copilot-instructions.md` that drifts across repositories.

**After:** An instruction primitive in `.apm/instructions/` compiled into `.github/copilot-instructions.md` by `apm compile`. Changes propagate to every repo that depends on the package.

### From Copy-Pasted AGENTS.md

**Before:** An `AGENTS.md` copied from a template repo, manually edited per project, gradually falling out of date.

**After:** `apm compile` generates `AGENTS.md` from your dependency tree. Updates arrive via `apm update` instead of manual diffing.

### From Individual Plugin Installs

**Before:** Each developer manually installs MCP servers and tool integrations, with inconsistent versions across the team.

**After:** Plugin dependencies declared in `apm.yml`. Running `apm install` gives every developer the same plugin set.

### From Scattered Team Standards

**Before:** Coding standards, review guidelines, and prompt templates live in a wiki, a shared drive, or a pinned Slack message.

**After:** A shared APM package (`your-org/team-standards`) that every repository depends on. Update the package once, run `apm update` everywhere.

## Rollback

APM does not take ownership of your project. If you want to stop using it:

1. Delete `apm.yml` and `apm.lock`.
2. Optionally remove the `.apm/` directory if you created one.
3. Your native configuration files (`.github/`, `.claude/`, `AGENTS.md`) continue to work exactly as they did before APM.

No uninstall script, no cleanup command — just remove the manifest files.

## Troubleshooting

### Compiled output overwrites my manual file

APM-generated files include a header comment marking them as managed. If you have a hand-maintained file at the same path, rename it or move your content into an APM primitive so compilation produces the combined result.

### Existing AGENTS.md has custom sections

Use `apm compile --verbose` to inspect how the output is assembled. You can add local primitives that contribute content to specific sections, preserving your custom additions in a structured way.

### Team members do not have APM installed

APM-generated files are standard Markdown. Team members without APM installed can still read and use the generated `AGENTS.md`, `.github/copilot-instructions.md`, and other output files directly. APM is only needed to update or recompile them.

## Next Steps

- [Compilation guide](../../guides/compilation/) — understand how `apm compile` assembles output
- [Dependencies](../../guides/dependencies/) — managing external packages
- [Manifest schema](../../reference/manifest-schema/) — full `apm.yml` reference
- [CLI commands](../../reference/cli-commands/) — complete command reference

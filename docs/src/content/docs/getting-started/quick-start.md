---
title: "Quick Start"
description: "Get from zero to a fully configured AI agent setup in 5 minutes."
sidebar:
  order: 2
---

This walkthrough takes you from an empty directory to a fully configured AI agent setup. Every step is a command you can run right now.

## 1. Install APM

One command, no prerequisites beyond Python 3.10+:

```bash
curl -sSL https://raw.githubusercontent.com/microsoft/apm/main/install.sh | sh
```

Verify the installation:

```bash
apm --version
```

```
apm, version x.x.x
```

For alternative methods (Homebrew, pip), see the [Installation guide](../installation/).

## 2. Initialize a project

Create a new project and move into it:

```bash
apm init my-project && cd my-project
```

```
Created project directory: my-project
Initializing APM project: my-project
APM project initialized successfully!

 Created Files
 ✨  apm.yml  Project configuration
```

The generated `apm.yml` is your project manifest — equivalent to `package.json` or `requirements.txt`, but for AI agent configuration:

```yaml
name: my-project
version: 1.0.0
dependencies:
  apm: []
```

If you already have a repository, run `apm init` (without a project name) inside it. APM detects your existing project metadata automatically.

## 3. Add your first dependency

Install a sample package to see how APM works:

```bash
apm install microsoft/apm-sample-package
```

```
Installing APM dependencies...
Resolving: microsoft/apm-sample-package
Downloaded: microsoft/apm-sample-package@latest
Deployed 3 files to .github/instructions/
```

APM did three things:

1. **Downloaded** the package from GitHub into `apm_modules/microsoft/apm-sample-package/`.
2. **Resolved** any transitive dependencies the package declares.
3. **Deployed** instruction files into `.github/instructions/` where your AI tools can find them.

Your `apm.yml` now includes the dependency:

```yaml
dependencies:
  apm:
    - microsoft/apm-sample-package
```

And a lockfile (`apm.lock`) pins the exact commit so every developer on your team gets the same version.

## 4. See the result

After install, your project tree looks like this:

```
my-project/
  apm.yml                          # Project manifest
  apm.lock                         # Pinned dependency versions
  apm_modules/                     # Downloaded packages (like node_modules/)
    microsoft/
      apm-sample-package/
        apm.yml
        .apm/
          instructions/
          skills/
          prompts/
  .github/
    instructions/                  # Deployed instructions for Copilot/Cursor
      apm-sample-package/
        ...
```

The `.github/instructions/` directory is where VS Code, GitHub Copilot, and Cursor look for agent context. Open your editor — your AI agent is now configured with the skills, instructions, and prompts from the package you installed.

## 5. Compile instructions

For tools that read a single root file (like Claude Code or Codex), compile everything into one output:

```bash
apm compile
```

```
Compiling APM context...
Target: all (auto-detected)
Generated: AGENTS.md
Generated: CLAUDE.md
```

By default, `apm compile` targets all platforms. You can narrow it:

```bash
# Copilot/Cursor/Codex only — produces AGENTS.md
apm compile --target copilot

# Claude Code only — produces CLAUDE.md
apm compile --target claude
```

Use `--dry-run` to preview what would be generated without writing any files:

```bash
apm compile --dry-run
```

## 6. Check what is installed

List all installed packages:

```bash
apm deps list
```

```
Installed APM Dependencies

 Package                         Source   Version
 microsoft/apm-sample-package    github   abc1234
```

View the full dependency tree, including transitive dependencies:

```bash
apm deps tree
```

```
my-project
  microsoft/apm-sample-package@abc1234
```

## 7. Day-to-day workflow

Once set up, the workflow for your team is straightforward:

```bash
# A new developer clones and installs — same as npm install
git clone <your-repo>
cd <your-repo>
apm install

# Add another package later
apm install github/awesome-copilot/skills/review-and-refactor

# Recompile after adding dependencies
apm compile
```

Commit `apm.yml` and `apm.lock` to version control. The `apm_modules/` directory should be in `.gitignore` — APM recreates it from the lockfile on `apm install`.

## What's next

- [Your First Package](../first-package/) — create and publish your own APM package.
- [Compilation guide](../../guides/compilation/) — learn about distributed compilation, targets, and options.
- [Dependency management](../../guides/dependencies/) — version pinning, updates, and transitive resolution.
- [CLI reference](../../reference/cli-commands/) — full list of commands, flags, and examples.

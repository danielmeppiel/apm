---
title: "Your First Package"
description: "Create an APM package, install it in another project, and compile — in under 5 minutes."
---

This tutorial walks you through the complete APM workflow: creating a reusable instruction package, installing it in a project, and compiling everything into optimized agent context.

## Prerequisites

- APM installed ([Installation](/apm/getting-started/installation/))
- A GitHub account (packages are hosted as Git repos)

## Step 1: Create a Package

Create a new directory and initialize it as an APM package:

```bash
mkdir code-review-kit && cd code-review-kit
apm init
```

APM creates an `apm.yml` manifest:

```yaml
name: code-review-kit
version: 1.0.0
description: Reusable code review instructions for AI agents
```

## Step 2: Add Instructions

Create an instruction file that your AI agent will follow:

```bash
mkdir -p .apm/instructions
```

Create `.apm/instructions/code-review.instructions.md`:

```markdown
---
applyTo: "**/*.py,**/*.js,**/*.ts"
---

# Code Review Standards

When reviewing code changes, follow these guidelines:

## Checklist

- Verify error handling covers edge cases
- Check that new functions have type annotations
- Ensure test coverage for new code paths
- Flag any hardcoded secrets or credentials
- Confirm naming follows project conventions

## Tone

Provide constructive, specific feedback. Reference the exact line and suggest an improvement — don't just say "this is wrong."
```

## Step 3: Push to Git

```bash
git init && git add -A && git commit -m "Initial package"
```

Push this repository to GitHub (or any supported Git host).

## Step 4: Install in Another Project

In a different project, initialize APM and install your package:

```bash
cd ~/my-project
apm init
apm install github/<your-user>/code-review-kit
```

APM clones the package, resolves dependencies, and deploys the instruction files into your project's `.github/instructions/` directory (or `.claude/instructions/` depending on your target).

## Step 5: Compile

```bash
apm compile
```

APM reads all installed instructions, deduplicates overlapping rules, and generates scoped `AGENTS.md` files optimized for your AI agent's context window.

Check the output:

```bash
cat AGENTS.md
```

You should see your code review instructions compiled into a clean, portable format that any AI coding agent can consume.

## What Just Happened?

1. **Created** a reusable package with an `apm.yml` manifest and instruction files.
2. **Installed** it into a consuming project with `apm install`.
3. **Compiled** all instructions into optimized `AGENTS.md` output.

This is the core APM loop: **declare → install → compile**. From here, you can add more packages, create skills and prompts, configure compilation options, and share your packages with others.

## Next Steps

- [Compilation & Optimization](/apm/guides/compilation/) — learn how the compiler works.
- [Skills & Prompts](/apm/guides/skills-and-prompts/) — add executable AI workflows to your packages.
- [Dependencies & Lockfile](/apm/guides/dependencies/) — manage transitive dependencies and version pinning.

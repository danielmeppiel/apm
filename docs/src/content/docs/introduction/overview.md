---
title: Why APM?
description: The 30-second pitch for the Agent Package Manager — what it is, why it exists, and how it helps.
---

AI agents are only as good as their instructions. But today, there is no standard way to **version**, **share**, or **compose** the context that drives them.

Teams copy-paste prompts across repos. Instructions drift out of sync. Onboarding a new project means re-discovering which markdown files matter. CI agents hallucinate because they inherit developer-facing instructions they were never meant to see.

**APM brings dependency management to AI agent context** — the same patterns you already know from npm, pip, and Cargo, applied to instructions, skills, prompts, and tools.

## Before & After

| | Before APM | With APM |
|---|---|---|
| **Sharing** | Copy-paste markdown between repos | `apm install github/org/code-review-kit` |
| **Versioning** | "Which version of AGENTS.md is this?" | Lockfile pins every dependency |
| **Composition** | Manual merge of overlapping instructions | `apm compile` deduplicates and scopes |
| **CI isolation** | Agent reads dev instructions in prod | `apm compile --isolated` strips dev context |
| **Discoverability** | Grep through folders | `apm list` shows what's installed |

## The One-Liner

> APM is `package.json` for AI agent instructions — declare dependencies in `apm.yml`, install them with `apm install`, and compile them into optimized context with `apm compile`.

## How It Works in 30 Seconds

```yaml
# apm.yml — your project's agent dependency manifest
name: my-project
version: 1.0.0
dependencies:
  code-review: github/acme/code-review-instructions
  testing: github/acme/testing-best-practices
  security: github/acme/security-guidelines
```

```bash
# Fetch and deploy all instruction packages
apm install

# Compile into optimized, scoped AGENTS.md files
apm compile
```

That's it. Your agent now has versioned, deduplicated, team-shared context — instead of whatever was last pasted into a markdown file.

## Who Is APM For?

- **Individual developers** who want to reuse their best agent instructions across projects.
- **Teams** who need consistent agent behaviour across repositories.
- **Platform engineers** who need to isolate agent context in CI/CD pipelines.
- **Open-source maintainers** who want to ship agent-ready packages.

## Next Steps

- [Installation](/apm/getting-started/installation/) — get APM running in under a minute.
- [Your First Package](/apm/getting-started/first-package/) — create, install, and compile a package end-to-end.
- [How It Works](/apm/introduction/how-it-works/) — understand the architecture and compilation model.

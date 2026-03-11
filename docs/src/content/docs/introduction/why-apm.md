---
title: "Why APM?"
description: "The problem APM solves — why AI agents need a dependency manager."
sidebar:
  order: 1
---

AI coding agents are powerful — but only when they have the right context. Today, setting up that context is entirely manual.

## The Problem

Every AI-assisted project faces the same setup friction:

1. **Manual configuration** — developers copy instruction files, write prompts from scratch, configure MCP servers by hand.
2. **No portability** — when a new developer clones the repo, none of the AI setup comes with it.
3. **No dependency management** — if your coding standards depend on another team's standards, there's no way to declare or resolve that relationship.
4. **Drift** — without a single source of truth, agent configurations diverge across developers and environments.

This is exactly the problem that package managers solved for application code decades ago. `npm`, `pip`, `cargo` — they all provide a manifest, a resolver, and a reproducible install. AI agent configuration deserves the same.

## How APM Solves It

APM introduces `apm.yml` — a declarative manifest for everything your AI agents need:

```yaml
name: my-project
version: 1.0.0
dependencies:
  apm:
    - anthropics/skills/skills/frontend-design
    - microsoft/apm-sample-package
    - github/awesome-copilot/agents/api-architect.agent.md
```

Run `apm install` and APM:

- **Resolves transitive dependencies** — if package A depends on package B, both are installed automatically.
- **Integrates primitives** — instructions go to `.github/instructions/`, prompts to `.github/prompts/`, skills to `.github/skills/`.
- **Compiles context** — `apm compile` produces optimized `AGENTS.md` and `CLAUDE.md` files for every major AI coding agent.

## What APM Manages

APM handles seven types of agent primitives:

| Primitive | Purpose |
|-----------|---------|
| **Instructions** | Coding standards and guardrails |
| **Skills** | Reusable AI capabilities |
| **Prompts** | Slash commands and workflows |
| **Agents** | Specialized personas |
| **Hooks** | Lifecycle event handlers |
| **Plugins** | Pre-packaged agent bundles |
| **MCP Servers** | Tool integrations |

All declared in one manifest. All installed with one command.

## Design Principles

- **Familiar** — APM works like the package managers you already know.
- **Fast** — install, compile, and run in seconds.
- **Open** — built on [AGENTS.md](https://agents.md), [Agent Skills](https://agentskills.io), and [MCP](https://modelcontextprotocol.io).
- **Portable** — install from GitHub, GitLab, Bitbucket, Azure DevOps, or any git host.

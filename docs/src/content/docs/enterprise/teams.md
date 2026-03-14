---
title: "APM for Teams"
description: "How APM provides reproducibility, governance, and consistency for AI agent configuration at scale."
sidebar:
  order: 1
---

APM is an open-source dependency manager for AI agent configuration.
One manifest (`apm.yml`), one command (`apm install`), locked versions (`apm.lock.yaml`).
Every developer gets the same agent setup.
Every CI run is reproducible.
Every configuration change is auditable.

## The problem at scale

Consider a mid-to-large engineering organization: 50 repositories, 200 developers, four AI coding tools (Copilot, Claude, Cursor, OpenCode).

Without centralized configuration management, a predictable set of problems emerges:

- **Manual configuration per repo.** Each team sets up agent configuration independently. Conventions diverge. Knowledge silos form. The "right" way to configure an agent depends on who you ask.
- **No audit trail.** When security or compliance asks "what agent configuration was active at release 4.2.1?" — there is no answer. Configuration files were hand-edited, and no one tracked which version of which plugin was in use.
- **Version drift.** Developer A has v1.2 of a rules plugin. Developer B has v1.4. CI has whatever was last committed. Bugs that only reproduce under specific configurations become difficult to trace.
- **Onboarding friction.** A new developer reads the README, runs N install commands, copies configuration from a colleague's machine, and hopes nothing was missed. The gap between "environment works" and "environment matches the team standard" is invisible.

These are not hypothetical problems. They are the direct consequence of treating AI agent configuration as a manual, per-developer responsibility rather than as a managed dependency.

## How APM solves this

APM applies the same model that package managers brought to application dependencies — declare, lock, install, audit — to AI agent configuration.

### Declare

A single `apm.yml` file in the repository root declares all agent configuration dependencies:

```yaml
packages:
  - name: org-security-rules
    source: github:your-org/apm-packages
    version: "^2.0"
  - name: team-coding-standards
    source: github:your-org/team-packages
    version: "~1.3"
  - name: project-context
    source: ./local-packages/context
```

This file is version-controlled, reviewed in pull requests, and readable by anyone on the team.

### Lock

Running `apm install` resolves versions and writes `apm.lock.yaml`, which pins the exact version of every dependency. The lock file is committed to the repository.

```
# apm.lock.yaml (auto-generated)
org-security-rules==2.1.0
team-coding-standards==1.3.4
project-context==local
```

Two developers running `apm install` from the same lock file get identical configuration. A CI pipeline running `apm install` gets the same result as a developer workstation.

### Install

`apm install` reads the lock file and deploys configuration into the native formats expected by each tool — `.github/` for Copilot, `.claude/` for Claude, `.cursor/` for Cursor, `.opencode/` for OpenCode. APM generates static files and then gets out of the way. There is no runtime, no daemon, no background process.

### Audit

Because `apm.lock.yaml` is a committed file, standard Git tooling answers governance questions directly:

- **What changed?** `git diff apm.lock.yaml`
- **When did it change?** `git log apm.lock.yaml`
- **What was active at a specific release?** `git show v4.2.1:apm.lock.yaml`
- **Is this environment current?** `apm audit`

## Developer stories

### Solo or small team (2–5 developers)

A small team uses 5 configuration packages across 2 AI tools.

Without APM, each developer runs 5 separate install commands, in the right order, from the right sources. When a package updates, someone notices (or doesn't), and the team re-runs the process.

With APM, the workflow is:

```bash
git clone the-repo
apm install
```

Configuration is ready. Updates are a pull request to `apm.yml`.

### Mid-size team (10–50 developers)

A mid-size organization maintains three layers of configuration: organization-wide security rules, team-specific coding standards, and project-level context. Different teams need different combinations.

APM composes these layers through its dependency model. The organization publishes shared packages. Each team's `apm.yml` references the org packages it needs alongside team and project packages. `apm install` deploys them for Copilot and Claude natively; `apm compile` can merge them into instruction files for other tools.

```yaml
packages:
  # Organization layer
  - name: org-security-rules
    source: github:acme-corp/apm-packages
    version: "^2.0"
  # Team layer
  - name: backend-standards
    source: github:acme-corp/backend-team
    version: "~1.0"
  # Project layer
  - name: service-context
    source: ./packages/context
```

A new developer joining the team runs `apm install` and gets the full, correct configuration stack. There is nothing to forget.

### Enterprise (100+ developers)

At enterprise scale, the primary concerns shift from convenience to governance: reproducibility, audit, and policy enforcement.

APM addresses these through mechanisms that engineering leadership and platform teams can build on:

- **Reproducibility.** `apm.lock.yaml` guarantees that every environment — developer workstation, CI runner, staging — uses identical configuration. "Works on my machine" stops applying to agent setup.
- **Audit trail.** `git log apm.lock.yaml` provides a complete, timestamped history of every configuration change, who made it, and which pull request approved it.
- **CI enforcement.** `apm audit` in a CI pipeline fails the build if local configuration has drifted from the declared and locked state, catching unauthorized or accidental changes before they reach production.
- **Centralized standards.** Organization-wide packages are published once and consumed by every repository. Updates propagate through version bumps in `apm.yml`, reviewed and approved through the normal pull request process.

## What APM adds on top of native plugin systems

Each AI tool has its own plugin or extension system. APM does not replace these — it orchestrates across them.

| Capability | Native plugin systems | With APM |
|---|---|---|
| Install plugins for one tool | Yes | Yes |
| Install across all tools, one command | No | Yes |
| Consumer-side version lock | No | Yes (`apm.lock.yaml`) |
| CI gate for configuration drift | No | Yes (`apm audit`) |
| Audit trail | No | Yes (`git log apm.lock.yaml`) |
| Multi-source composition | No | Yes |

The distinction matters: native plugin systems solve distribution for a single tool. APM solves consistency across tools, teams, and time.

## What APM is not

**APM is not a runtime.** It generates static configuration files in the formats each tool expects, then exits. There is no daemon, no background process, no performance overhead.

**APM is not lock-in.** The output of `apm install` is native configuration: `.github/copilot-instructions.md`, `.claude/settings.json`, `.cursor/rules/`. If you stop using APM, the generated configuration remains and continues to work. There is nothing proprietary in the output.

**APM is not competing with plugins.** Plugin ecosystems handle discovery and distribution for individual tools. APM handles the cross-cutting concerns — version locking, multi-tool deployment, composition, and audit — that no single plugin system addresses.

## Getting started

For hands-on setup and deeper topics, start here:

- [Quick Start](../../getting-started/installation/) — install APM and configure your first project in five minutes.
- [Organization-Wide Packages](../../guides/org-packages/) — publish and maintain shared configuration packages across your organization.
- [Compilation Guide](../../guides/compilation/) — optional: generate instruction files for tools without native APM integration (Codex, Gemini).
- [Dependencies Guide](../../guides/dependencies/) — version constraints, lock file mechanics, and update workflows.

# APM – Agent Package Manager

[![PyPI version](https://badge.fury.io/py/apm-cli.svg)](https://badge.fury.io/py/apm-cli)
[![CI/CD Pipeline](https://github.com/danielmeppiel/apm/actions/workflows/build-release.yml/badge.svg)](https://github.com/danielmeppiel/apm/actions/workflows/build-release.yml)
[![Downloads](https://img.shields.io/pypi/dm/apm-cli.svg)](https://pypi.org/project/apm-cli/)
[![GitHub stars](https://img.shields.io/github/stars/danielmeppiel/apm.svg?style=social&label=Star)](https://github.com/danielmeppiel/apm/stargazers)

**npm for AI coding agents.** The package manager for [AGENTS.md](https://agents.md), [Agent Skills](https://agentskills.io), and MCP servers.

GitHub Copilot · Cursor · Claude · Codex · Gemini

> 📐 **Built on open standards:** APM generates [AGENTS.md](https://agents.md) instructions, installs [Agent Skills](https://agentskills.io) natively, and manages [MCP](https://modelcontextprotocol.io) servers.

## Install

```bash
curl -sSL https://raw.githubusercontent.com/danielmeppiel/apm/main/install.sh | sh
```

## Quick Start

**One package. Every AI agent. Native format for each.**

```bash
# Install a skill — give your agent new capabilities
apm install ComposioHQ/awesome-claude-skills/brand-guidelines

# Install guardrails — keep your agent compliant
apm install danielmeppiel/compliance-rules

# Compile for your AI tools
apm compile
```

**Done.** Type `/gdpr-assessment` or `/code-review` in Copilot or Claude. It just works.

## What APM Does

```
┌─────────────────────────────────────────────────────────────────┐
│  APM Packages (from GitHub, Azure DevOps)                       │
│  ├── Instructions → Coding standards, guardrails (AGENTS.md)    │
│  ├── Skills       → AI capabilities, workflows (agentskills.io) │
│  ├── Prompts      → Reusable commands and templates             │
│  └── MCP Servers  → Tool integrations                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                    apm install && apm compile
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Universal Output (auto-detected from .github/ and .claude/)    │
│  ├── AGENTS.md      → Instructions for Copilot, Cursor, Codex   │
│  ├── CLAUDE.md      → Instructions for Claude Code              │
│  ├── .github/       → VSCode native prompts & agents            │
│  └── .claude/       → Claude commands & skills                  │
└─────────────────────────────────────────────────────────────────┘
```

**One package. Every AI agent. Native format for each.**

## Real Example: corporate-website

A production project using APM with skills and layered guardrails:

```yaml
# apm.yml
name: corporate-website
dependencies:
  apm:
    - ComposioHQ/awesome-claude-skills/mcp-builder  # Build MCP servers
    - danielmeppiel/compliance-rules                 # GDPR, security
    - danielmeppiel/design-guidelines                # UI standards
```

```bash
apm install && apm compile
```

→ [View the full example](https://github.com/danielmeppiel/corporate-website)

## Commands

| Command | What it does |
|---------|--------------|
| `apm install <pkg>` | Add package to project |
| `apm compile` | Generate agent context files |
| `apm init` | Create new APM project |
| `apm run <prompt>` | Execute a workflow |
| `apm deps list` | Show installed packages |

## Install From Anywhere

```bash
# For packages hosted on GitHub 
apm install owner/repo

# Paths or Single file are also OK (Virtual Package)
apm install github/awesome-copilot/prompts/code-review.prompt.md

# For packages in GitHub Enterprise with Data Residency 
apm install ghe.company.com/owner/repo

# For packages Azure DevOps
apm install dev.azure.com/org/project/repo
```

## Create Your Own Package

```bash
apm init my-standards && cd my-standards
```

This creates:

```
my-standards/
├── apm.yml              # Package manifest
├── SKILL.md             # Package meta-guide for AI discovery
└── .apm/
    ├── instructions/    # Guardrails (.instructions.md)
    ├── prompts/         # Workflows (.prompt.md)  
    └── agents/          # Personas (.agent.md)
```

Example guardrail:

```bash
cat > .apm/instructions/python.instructions.md << 'EOF'
---
applyTo: "**/*.py"
---
# Python Standards
- Use type hints for all functions
- Follow PEP 8 style guidelines
EOF

# Push and share
git add . && git commit -m "Initial standards" && git push
```

Anyone can now run: `apm install you/my-standards`

## Installation Options

```bash
# Quick install (recommended)
curl -sSL https://raw.githubusercontent.com/danielmeppiel/apm/main/install.sh | sh

# Homebrew
brew tap danielmeppiel/apm-cli && brew install apm-cli

# pip
pip install apm-cli
```

## Target Specific Agents

```bash
apm compile                    # Auto-detects from .github/ and .claude/ folders
apm compile --target vscode    # AGENTS.md + .github/ only
apm compile --target claude    # CLAUDE.md + .claude/ only
apm compile --target all       # Force all formats
```

> **Note:** `apm compile` generates instruction files (AGENTS.md, CLAUDE.md). Prompts, agents, and skills are integrated by `apm install` into `.github/` and `.claude/` folders.

## Advanced Configuration

For private packages, Azure DevOps, or running prompts via AI runtimes:

| Token | Purpose |
|-------|---------|
| `GITHUB_APM_PAT` | Private GitHub packages |
| `ADO_APM_PAT` | Azure DevOps packages |
| `GITHUB_COPILOT_PAT` | Running prompts via `apm run` |

→ [Complete setup guide](docs/getting-started.md)

---

## Community Packages

[![Install with APM](https://img.shields.io/badge/📦_Install_with-APM-blue?style=flat-square)](https://github.com/danielmeppiel/apm#community-packages)

| Package | What you get |
|---------|-------------|
| [danielmeppiel/compliance-rules](https://github.com/danielmeppiel/compliance-rules) | `/gdpr-assessment`, `/security-audit` + compliance rules |
| [danielmeppiel/design-guidelines](https://github.com/danielmeppiel/design-guidelines) | `/accessibility-audit`, `/design-review` + UI standards |
| [DevExpGbb/platform-mode](https://github.com/DevExpGbb/platform-mode) | Platform engineering prompts & agents |
| [Add yours →](https://github.com/danielmeppiel/apm/discussions/new) | |

---

## Documentation

### Getting Started
| Guide | Description |
|-------|-------------|
| [Quick Start](docs/getting-started.md) | Complete setup, tokens, first project |
| [Core Concepts](docs/concepts.md) | How APM works, the primitives model |
| [Examples](docs/examples.md) | Real-world patterns and use cases |

### Reference
| Guide | Description |
|-------|-------------|
| [CLI Reference](docs/cli-reference.md) | All commands and options |
| [Compilation Engine](docs/compilation.md) | Context optimization algorithm |
| [Skills](docs/skills.md) | Native [agentskills.io](https://agentskills.io) support |
| [Integrations](docs/integrations.md) | VSCode, Spec-kit, MCP servers |

### Advanced
| Guide | Description |
|-------|-------------|
| [Dependencies](docs/dependencies.md) | Package management deep-dive |
| [Primitives](docs/primitives.md) | Building advanced workflows |
| [Contributing](CONTRIBUTING.md) | Join the ecosystem |

---

**Open Standards:** [AGENTS.md](https://agents.md) · [Agent Skills](https://agentskills.io) · [MCP](https://modelcontextprotocol.io)

**Learn AI-Native Development** → [Awesome AI Native](https://danielmeppiel.github.io/awesome-ai-native)  
A practical learning path for AI-Native Development, leveraging APM along the way.

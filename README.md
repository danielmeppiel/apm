# APM – Agent Package Manager

[![PyPI version](https://badge.fury.io/py/apm-cli.svg)](https://badge.fury.io/py/apm-cli)
[![CI/CD Pipeline](https://github.com/danielmeppiel/apm/actions/workflows/build-release.yml/badge.svg)](https://github.com/danielmeppiel/apm/actions/workflows/build-release.yml)
[![Downloads](https://img.shields.io/pypi/dm/apm-cli.svg)](https://pypi.org/project/apm-cli/)
[![GitHub stars](https://img.shields.io/github/stars/danielmeppiel/apm.svg?style=social&label=Star)](https://github.com/danielmeppiel/apm/stargazers)

**npm for AI coding agents.** Package guardrails, workflows, and personas. Deploy to every agent.

GitHub Copilot · Cursor · Claude · Codex · Gemini

## Install

```bash
curl -sSL https://raw.githubusercontent.com/danielmeppiel/apm/main/install.sh | sh
```

## Quick Start

```bash
# Install a compliance package from GitHub (github.com/danielmeppiel/compliance-rules)
apm install danielmeppiel/compliance-rules

# Generate context for all AI agents  
apm compile
```

**Done.** Your AI agents now respect GDPR, security standards, and audit requirements.

## What APM Does

```
┌─────────────────────────────────────────────────────────────────┐
│  APM Packages (hosted on GitHub, Azure DevOps)                  │
│  ├── Guardrails   → Rules, compliance, standards                │
│  ├── Workflows    → Executable prompts, abilities               │
│  └── Personas     → Specialized AI agents                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                    apm install && apm compile
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Universal Output                                               │
│  ├── AGENTS.md      → GitHub Copilot, Cursor, Codex, Gemini     │
│  ├── CLAUDE.md      → Claude Code, Claude Desktop               │
│  ├── .github/       → VSCode native prompts & agents            │
│  └── .claude/       → Claude native commands & skills           │
└─────────────────────────────────────────────────────────────────┘
```

**One package. Every AI agent. Native format for each.**

> 💡 **Install any `.prompt.md` or `.agent.md` directly from GitHub!**  
> Explore ready-to-use prompts and agents at [github/awesome-copilot](https://github.com/github/awesome-copilot) and install them with a simple command:  
> `apm install github/awesome-copilot/prompts/code-review.prompt.md`

## Real Example: corporate-website

A production project using APM with layered guardrails:

```yaml
# apm.yml
name: corporate-website
dependencies:
  apm:
    - danielmeppiel/compliance-rules    # GDPR, security, audit
    - danielmeppiel/design-guidelines   # Accessibility, UI standards
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
# GitHub
apm install owner/repo

# GitHub Enterprise  
apm install ghe.company.com/owner/repo

# Azure DevOps
apm install dev.azure.com/org/project/repo

# Single file (Virtual Package)
apm install github/awesome-copilot/prompts/code-review.prompt.md
```

## Create Your Own Package

```bash
apm init my-standards && cd my-standards
```

Add primitives to the `.apm/` folder (similar to VSCode's `.github/` convention):

```
.apm/
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

| Package | Description |
|---------|-------------|
| [danielmeppiel/compliance-rules](https://github.com/danielmeppiel/compliance-rules) | GDPR, security, audit workflows |
| [danielmeppiel/design-guidelines](https://github.com/danielmeppiel/design-guidelines) | Accessibility, UI standards |
| [DevExpGbb/platform-mode](https://github.com/DevExpGbb/platform-mode) | Platform engineering patterns |
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
| [Integrations](docs/integrations.md) | VSCode, Spec-kit, MCP servers |

### Advanced
| Guide | Description |
|-------|-------------|
| [Dependencies](docs/dependencies.md) | Package management deep-dive |
| [Primitives](docs/primitives.md) | Building advanced workflows |
| [Contributing](CONTRIBUTING.md) | Join the ecosystem |

---

**Learn AI-Native Development** → [Awesome AI Native](https://danielmeppiel.github.io/awesome-ai-native)  
A practical learning path for AI-Native Development, leveraging APM along the way.

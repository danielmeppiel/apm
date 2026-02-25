# APM – Agent Package Manager

[![PyPI version](https://badge.fury.io/py/apm-cli.svg)](https://badge.fury.io/py/apm-cli)
[![CI/CD Pipeline](https://github.com/microsoft/apm/actions/workflows/build-release.yml/badge.svg)](https://github.com/microsoft/apm/actions/workflows/build-release.yml)
[![Downloads](https://img.shields.io/pypi/dm/apm-cli.svg)](https://pypi.org/project/apm-cli/)
[![GitHub stars](https://img.shields.io/github/stars/microsoft/apm.svg?style=social&label=Star)](https://github.com/microsoft/apm/stargazers)

**An open-source, community-driven dependency manager for AI agents.** `apm.yml` declares the skills, prompts, instructions, and tools your project needs — so every developer gets the same agent setup. Packages can depend on packages, and APM resolves the full tree.

Think `package.json`, `requirements.txt`, or `Cargo.toml` — but for AI agent configuration.

GitHub Copilot · Cursor · Claude · Codex · Gemini

## Why APM

AI coding agents need context to be useful: what standards to follow, what prompts to use, what skills to leverage. Today this is manual — each developer installs things one by one, writes instructions from scratch, copies files around. None of it is portable. There's no manifest for it.

**APM fixes this.** You declare your project's agentic dependencies once, and every developer who clones your repo gets a fully configured agent setup in seconds. Packages can depend on other packages — APM resolves transitive dependencies automatically, just like npm or pip.

## See It in Action

```yaml
# apm.yml — ships with your project, like package.json
name: your project
version: 1.0.0
dependencies:
  apm:
    # Skills from any repository
    - anthropics/skills/skills/frontend-design
    - microsoft/GitHub-Copilot-for-Azure/plugin/skills/azure-compliance
    # A full APM package with rules, skills, prompts...
    - microsoft/apm-sample-package
    # Specific agent primitives from any repository
    - github/awesome-copilot/skills/review-and-refactor
    - github/awesome-copilot/agents/api-architect.agent.md
```

New developer joins the team:

```bash
git clone <org/repo>
cd <repo>
apm install
```

**That's it.** Copilot, Claude, Cursor — every agent is configured with the right skills, prompts, and coding standards.

→ [View the full example project](https://github.com/microsoft/apm-project-sample)

## Not Just Skills

Skill registries install skills. APM manages **every primitive** your AI agents need:

| Primitive | What it does | Example |
|-----------|-------------|---------|
| **Instructions** | Coding standards, guardrails | "Use type hints in all Python files" |
| **Skills** | AI capabilities, workflows | Form builder, code reviewer |
| **Prompts** | Reusable slash commands | `/security-audit`, `/design-review` |
| **Agents** | Specialized personas | Accessibility auditor, API designer |
| **MCP Servers** | Tool integrations | Database access, API connectors |

All declared in one manifest. All installed with one command — including transitive dependencies:

**`apm install`** → integrates prompts, agents, and skills into `.github/` and `.claude/`
**`apm compile`** → compiles instructions into `AGENTS.md` (Copilot, Cursor, Codex) and `CLAUDE.md` (Claude)

## Get Started

**1. Install APM**

```bash
curl -sSL https://raw.githubusercontent.com/microsoft/apm/main/install.sh | sh
```

<details>
<summary>Homebrew or pip</summary>

```bash
brew install microsoft/apm/apm
# or
pip install apm-cli
```
</details>

**2. Add APM packages to your project**

```bash
apm install microsoft/apm-sample-package
apm install anthropics/skills/skills/frontend-design
apm install github/awesome-copilot/agents/api-architect.agent.md
```

**Done.** Open your project in VS Code or Claude and your AI tools are ready.

## Install From Anywhere

```bash
# GitHub Repo or Path
apm install owner/repo   
apm install owner/repo/path                                              
# Single file
apm install github/awesome-copilot/skills/review-and-refactor   
# GitHub Enterprise Server
apm install ghe.company.com/owner/repo    
# Azure DevOps                      
apm install dev.azure.com/org/project/repo
```

## Create & Share Packages

```bash
apm init my-standards && cd my-standards
```

```
my-standards/
├── apm.yml              # Package manifest
└── .apm/
    ├── instructions/    # Guardrails (.instructions.md)
    ├── prompts/         # Slash commands (.prompt.md)
    ├── skills/          # Agent Skills (SKILL.md)
    └── agents/          # Personas (.agent.md)
```

Add a guardrail and publish:

```bash
cat > .apm/instructions/python.instructions.md << 'EOF'
---
applyTo: "**/*.py"
---
# Python Standards
- Use type hints for all functions
- Follow PEP 8 style guidelines
EOF

git add . && git commit -m "Initial standards" && git push
```

Anyone can now `apm install you/my-standards`.

## All Commands

| Command | What it does |
|---------|--------------|
| `apm install <pkg>` | Add a package and integrate its primitives |
| `apm compile` | Compile instructions into AGENTS.md / CLAUDE.md |
| `apm init [name]` | Scaffold a new APM project or package |
| `apm run <prompt>` | Execute a prompt workflow via AI runtime |
| `apm deps list` | Show installed packages and versions |
| `apm compile --target` | Target a specific agent (`vscode`, `claude`, `all`) |

## Configuration

For private repos or Azure DevOps, set a token:

| Token | When you need it |
|-------|-----------------|
| `GITHUB_APM_PAT` | Private GitHub packages |
| `ADO_APM_PAT` | Azure DevOps packages |
| `GITHUB_COPILOT_PAT` | Running prompts via `apm run` |

→ [Complete setup guide](docs/getting-started.md)

---

## APM Packages

APM installs from any GitHub or Azure DevOps repo — no special packaging required. Point at a prompt file, a skill, or a full package. These are some curated packages to get you started:

| Package | What you get |
|---------|-------------|
| [github/awesome-copilot](https://github.com/github/awesome-copilot) | Community prompts, agents & instructions for GitHub Copilot |
| [anthropics/courses](https://github.com/anthropics/courses) | Anthropic's official prompt engineering courses |
| [microsoft/GitHub-Copilot-for-Azure](https://github.com/microsoft/GitHub-Copilot-for-Azure/tree/main/plugin/skills) | Azure Skills |
| [Add yours →](https://github.com/microsoft/apm/discussions/new) | |

---

## Documentation

| | |
|---|---|
| **Get Started** | [Quick Start](docs/getting-started.md) · [Core Concepts](docs/concepts.md) · [Examples](docs/examples.md) |
| **Reference** | [CLI Reference](docs/cli-reference.md) · [Compilation Engine](docs/compilation.md) · [Skills](docs/skills.md) · [Integrations](docs/integrations.md) |
| **Advanced** | [Dependencies](docs/dependencies.md) · [Primitives](docs/primitives.md) · [Contributing](CONTRIBUTING.md) |

---

**Built on open standards:** [AGENTS.md](https://agents.md) · [Agent Skills](https://agentskills.io) · [MCP](https://modelcontextprotocol.io)

**Learn AI-Native Development** → [Awesome AI Native](https://danielmeppiel.github.io/awesome-ai-native)
A practical learning path for AI-Native Development, leveraging APM along the way.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general). Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those third-party's policies.

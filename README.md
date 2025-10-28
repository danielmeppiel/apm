# Agent Package Manager - npm for Agents

[![PyPI version](https://badge.fury.io/py/apm-cli.svg)](https://badge.fury.io/py/apm-cli)
[![CI/CD Pipeline](https://github.com/danielmeppiel/apm/actions/workflows/build-release.yml/badge.svg)](https://github.com/danielmeppiel/apm/actions/workflows/build-release.yml)
[![Downloads](https://img.shields.io/pypi/dm/apm-cli.svg)](https://pypi.org/project/apm-cli/)
[![GitHub stars](https://img.shields.io/github/stars/danielmeppiel/apm.svg?style=social&label=Star)](https://github.com/danielmeppiel/apm/stargazers)

**Stop copy-pasting prompts and instructions. Start packaging them.**

✅ Works with **GitHub Copilot, Cursor, Claude, Codex, Gemini and all [AGENTS.md](https://agents.md) adherents**  
✅ **2-minute setup** - zero config  
✅ **Team collaboration** - composable context, without wheel reinvention

**Compound innovation** - reuse [packages built with APM by the community](#built-with-apm)

## What Goes in Packages

📦 **Mix and match what your team needs**:

- **Agents** - Agentic workflows (.prompt.md files)
- **Context** - Company rules, standards, knowledge (.instructions.md files) and domain boundaries (.chatmode.md)

![APM Demo](docs/apm-demo.gif)

## Quick Start (2 minutes)

> [!NOTE] 
> **📋 Prerequisites**: Get tokens at [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new)  
> - **`GITHUB_COPILOT_PAT`** - User-scoped Fine-grained PAT with Copilot CLI subscription access 
> - **`GITHUB_APM_PAT`** - (optional) - Fine-grained PAT for access to private APM modules 
>
> 📖 **Complete Setup Guide**: [Getting Started](docs/getting-started.md)

```bash
# 1. Set your GitHub token (minimal setup)
export GITHUB_COPILOT_PAT=your_fine_grained_token_here

# 2. Install APM CLI
curl -sSL "https://raw.githubusercontent.com/danielmeppiel/apm/main/install.sh" | sh

# 3. Set up runtime (GitHub Copilot CLI with native MCP support)
apm runtime setup copilot

# 3. Create your first AI package
apm init my-project && cd my-project

# 4. Install APM and MCP dependencies
apm install

# 5. Run your first workflow
apm compile && apm run start --param name="<YourGitHubHandle>"
```

**That's it!** Your project now has reliable AI workflows that work with any coding agent.

**GitHub Enterprise Support:** Works with Enterprise Server and Data Residency Cloud. [Configuration →](docs/getting-started.md#github-enterprise-support)

### Example `apm.yml` - Like package.json for AI Native projects

Here's what your `apm.yml` configuration file looks like (similar to `package.json` in npm):

```yaml
name: my-project
version: 1.0.0
description: My AI-native project
author: Developer

dependencies:
  apm:
    - danielmeppiel/compliance-rules
    - danielmeppiel/design-guidelines
  mcp:
    - github/github-mcp-server
    - microsoft/azure-devops-mcp

scripts:
  start: "copilot --full-auto -p hello-world.prompt.md"
```

## What You Just Built

- **Agent Workflows** - Agent executable processes (.prompt.md files)
- **Context System** - Project knowledge that grounds AI responses
- **Dependency Management** - `apm_modules/` with shared context from other projects  
- **Universal Compatibility** - Works with any coding agent supporting the `Agents.md` standard (e.g. GitHub Copilot, Cursor, Claude, Codex, Gemini...)

## Mathematical Context Optimization

APM solves the AI agent context scalability problem through constraint satisfaction optimization.

**[Learn more about the Context Optimization Engine →](docs/compilation.md)**

## Key Commands

```bash
apm init <project>    # Initialize AI-native project
apm runtime setup     # Install coding agents (copilot recommended)
apm compile           # Generate AGENTS.md for compatibility  
apm install           # Install APM and MCP dependencies from apm.yml
apm deps list         # List installed APM dependencies
apm run <workflow>    # Execute Agent workflows
```

## Installation Options

### Homebrew
```bash
brew tap danielmeppiel/apm-cli
brew install apm-cli
```

### Python Package
```bash
pip install apm-cli
```

[See complete installation guide](docs/getting-started.md) for all options and troubleshooting.

## Demo Example

**APM Packages** (reusable modules):
- 🏢 [`compliance-rules`](https://github.com/danielmeppiel/compliance-rules) - GDPR contexts + audit workflows  
- 👤 [`design-guidelines`](https://github.com/danielmeppiel/design-guidelines) - Accessibility rules + UI review workflows

**Application using APM**:
- 🚀 **[Corporate Website](https://github.com/danielmeppiel/corporate-website)** - Complete showcase demonstrating Context Optimization Engine + both packages above as dependencies

## 🌟 APM Packages
*Copy this badge for your APM packages* 

[![Install with APM](https://img.shields.io/badge/📦_Install_with-APM-blue?style=flat-square)](https://github.com/danielmeppiel/apm#-apm-packages) 

Install any of the below APM packages with: `apm install <owner>/<repo>`

- [DevExpGbb/platform-mode](https://github.com/DevExpGbb/platform-mode) - The Future of AI-Enhanced Platform Engineering
- [Add yours here!](https://github.com/danielmeppiel/apm/discussions/new)

## Next Steps

- 📖 [Complete Documentation](docs/README.md) - Deep dive into APM
- 🚀 [Getting Started Guide](docs/getting-started.md) - Extended setup and first project
- 🧠 [Core Concepts](docs/concepts.md) - AI-Native Development framework  
- 📦 [Examples & Use Cases](docs/examples.md) - Real-world workflow patterns
- 🔧 [Agent Primitives Guide](docs/primitives.md) - Build advanced workflows
- 🤝 [Contributing](CONTRIBUTING.md) - Join the AI-native ecosystem

---

**Learning Guide — Awesome AI Native**  
A practical companion guide that inspired APM CLI: <https://danielmeppiel.github.io/awesome-ai-native>

A friendly, step by step example-driven learning path for AI-Native Development — leveraging APM CLI along the way.

---

**APM transforms any project into reliable AI-Native Development**

# APM – Agent Package Manager

**An open-source, community-driven dependency manager for AI agents.**

Think `package.json`, `requirements.txt`, or `Cargo.toml` — but for AI agent configuration.

GitHub Copilot · Claude Code · Cursor

**[Documentation](https://microsoft.github.io/apm/)** · **[Quick Start](https://microsoft.github.io/apm/getting-started/quick-start/)** · **[CLI Reference](https://microsoft.github.io/apm/reference/cli-commands/)**

## Why APM

AI coding agents need context to be useful — standards, prompts, skills, plugins — but today every developer sets this up manually. Nothing is portable nor reproducible. There's no manifest for it.

**APM fixes this.** Declare your project's agentic dependencies once in `apm.yml`, and every developer who clones your repo gets a fully configured agent setup in seconds — with transitive dependency resolution, just like npm or pip.

```yaml
# apm.yml — ships with your project
name: your-project
version: 1.0.0
dependencies:
  apm:
    # Skills from any repository
    - anthropics/skills/skills/frontend-design
    # Plugins
    - github/awesome-copilot/plugins/context-engineering
    # Specific agent primitives from any repository
    - github/awesome-copilot/agents/api-architect.agent.md
    # A full APM package with instructions, skills, prompts, hooks...
    - microsoft/apm-sample-package
```

```bash
git clone <org/repo> && cd <repo>
apm install    # every agent is configured
```

## Highlights

- **One manifest for everything** — instructions, skills, prompts, agents, hooks, plugins, MCP servers
- **Install from anywhere** — GitHub, GitLab, Bitbucket, Azure DevOps, GitHub Enterprise, any git host
- **Transitive dependencies** — packages can depend on packages; APM resolves the full tree
- **Compile to standards** — `apm compile` produces `AGENTS.md` (GitHub Copilot), `CLAUDE.md` (Claude Code), and `.cursor/rules/` (Cursor)
- **Create & share** — `apm pack` bundles your current configuration as a zipped package
- **CI/CD ready** — [GitHub Action](https://github.com/microsoft/apm-action) for automated workflows

## Get Started

#### Linux / macOS

```bash
curl -sSL https://raw.githubusercontent.com/microsoft/apm/main/install.sh | sh
```

#### Windows

```powershell
irm https://raw.githubusercontent.com/microsoft/apm/main/install.ps1 | iex
```

Native release binaries are published for macOS, Linux, and Windows x86_64. `apm update` reuses the matching platform installer.

<details>
<summary>Other install methods</summary>

#### Linux / macOS

```bash
# Homebrew
brew install microsoft/apm/apm
# pip
pip install apm-cli
```

#### Windows

```powershell
# Scoop
scoop bucket add apm https://github.com/microsoft/scoop-apm
scoop install apm
# pip
pip install apm-cli
```

</details>

Then start adding packages:

```bash
apm install microsoft/apm-sample-package
```

See the **[Getting Started guide](https://microsoft.github.io/apm/getting-started/quick-start/)** for the full walkthrough.

## Community

Created and maintained by [@danielmeppiel](https://github.com/danielmeppiel).

- [Roadmap & Discussions](https://github.com/microsoft/apm/discussions/116)
- [Contributing](CONTRIBUTING.md)
- [AI Native Development guide](https://danielmeppiel.github.io/awesome-ai-native) — a practical learning path for AI-native development

---

**Built on open standards:** [AGENTS.md](https://agents.md) · [Agent Skills](https://agentskills.io) · [MCP](https://modelcontextprotocol.io)

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general). Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those third-party's policies.

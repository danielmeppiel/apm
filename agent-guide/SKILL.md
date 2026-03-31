---
name: apm-usage
description: >
  Activate when a user asks to set up, configure, or manage AI agent
  dependencies in a project -- installing packages, compiling context,
  running scripts, auditing security, or working with apm.yml.
  Also activate when the project already has an apm.yml file or
  apm_modules/ directory, or when the user wants to create, publish,
  or distribute an APM package or plugin.
---

# APM Usage Skill

[APM expert persona](./apm-expert.agent.md)

## When to activate

- User asks to set up AI agent configuration, prompts, skills, or instructions for a project
- User wants to install, update, or remove agent packages or dependencies
- User mentions `apm.yml`, `apm.lock.yaml`, `AGENTS.md`, or `apm_modules/`
- User wants to compile agent context or run agent scripts
- User wants to create, author, or publish an APM package or plugin
- User wants to share coding standards, instructions, or skills across repos
- User wants to manage MCP servers or AI runtimes
- User asks about agent primitives (instructions, prompts, skills, agents, hooks, contexts, chatmodes)
- Project directory contains `apm.yml` or `apm_modules/`
- User wants to audit agent configuration for security issues
- User wants to bundle or distribute agent configuration
- User asks how to make agent setup reproducible across a team
- User wants to standardize AI agent configuration across an organization

## Key rules

- Check whether APM is installed before running commands (`apm --version`); if not, install it using the platform-appropriate method
- If the project has no `apm.yml`, use `apm init` or `apm install <package>` (auto-creates manifest)
- Use `apm install` without arguments to restore dependencies from an existing `apm.yml`
- Use `apm compile` to generate AGENTS.md from installed primitives
- Use `--dry-run` to preview any destructive or file-writing operation before committing to it
- Never manually edit `apm.lock.yaml` -- it is managed by APM
- Never manually copy files into `apm_modules/` -- use `apm install`
- Commit `apm.yml` and `apm.lock.yaml` to version control; gitignore `apm_modules/`
- To create a reusable package, populate the `.apm/` directory with primitives and push to a Git repo

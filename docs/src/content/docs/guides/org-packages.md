---
title: "Org-Wide Packages"
description: "Build shared standards packages that standardize AI agent configuration across your organization."
sidebar:
  order: 7
---

## The pattern

A central team publishes a standards package — say `acme-corp/apm-standards`. Every repository in the organization adds it as a dependency. When the standards team pushes an update, every consumer gets it on their next `apm deps update`.

```
acme-corp/apm-standards (central package)
    ├── .apm/instructions/coding-standards.md
    ├── .apm/instructions/security-baseline.md
    ├── .apm/agents/review-agent.md
    └── apm.yml

repo-A/  ──depends on──▶  acme-corp/apm-standards
repo-B/  ──depends on──▶  acme-corp/apm-standards
repo-C/  ──depends on──▶  acme-corp/apm-standards
```

One update to the standards package propagates to all consumers. No copy-pasting, no drift.

## Why shared packages?

**Consistency.** Every repository gets the same coding standards, security baselines, and review agents. New repos start with the org's best practices from day one.

**Single update point.** Change a security policy once in the standards package. Every consumer picks it up with `apm deps update` — no need to open PRs across dozens of repos.

**Versioned.** Consumers pin to a specific version and upgrade on their own schedule. No forced rollouts, no surprise breakage.

**Composable.** Layer packages from broad to narrow: org-wide base, then team-specific, then project-specific. Each layer can override or extend the one below it.

## Creating an org package

Start by initializing a new APM package:

```bash
apm init acme-standards && cd acme-standards
```

Then populate it with the shared configuration your org needs.

### Instructions — coding standards and policies

Place organization-wide instructions in `.apm/instructions/`:

```markdown
<!-- .apm/instructions/coding-standards.md -->
# Coding Standards

- Write clear, self-documenting code. Prefer readability over cleverness.
- All public functions must have docstrings.
- Use type hints in Python, TypeScript types in JS/TS projects.
- Keep functions under 50 lines. Extract when they grow.
```

```markdown
<!-- .apm/instructions/security-baseline.md -->
# Security Baseline

- Never commit secrets, tokens, or credentials to source control.
- Validate all user input at API boundaries.
- Use parameterized queries for database access.
- Dependencies must be pinned to exact versions in lock files.
```

### Agents — standard review and advisory agents

Define reusable agent configurations in `.apm/agents/`:

```markdown
<!-- .apm/agents/security-reviewer.md -->
---
name: security-reviewer
description: Reviews code changes for security vulnerabilities
---

You are a security-focused code reviewer. When reviewing changes:

1. Check for injection vulnerabilities (SQL, command, template).
2. Verify authentication and authorization on all endpoints.
3. Flag hardcoded secrets or credentials.
4. Ensure error messages don't leak internal details.
5. Verify input validation at trust boundaries.

Be specific. Reference the exact file and line. Suggest a fix.
```

### Prompts — common workflows

Add shared prompt templates in `.apm/prompts/`:

```markdown
<!-- .apm/prompts/design-review.md -->
# Design Review

Review the proposed design for:

1. **Scalability** — Will this handle 10x the current load?
2. **Failure modes** — What happens when dependencies are unavailable?
3. **Data consistency** — Are there race conditions or stale reads?
4. **API surface** — Is the interface minimal and hard to misuse?

Provide concrete recommendations, not abstract concerns.
```

### Skills — shared capabilities

Place reusable skill definitions in `.apm/skills/`:

```markdown
<!-- .apm/skills/api-design.md -->
# API Design Skill

When designing or reviewing APIs:

- Use consistent naming: plural nouns for collections, singular for items.
- Return appropriate HTTP status codes (201 for creation, 204 for deletion).
- Version APIs in the URL path (/v1/resources).
- Paginate list endpoints by default.
- Include request IDs in all responses for traceability.
```

### Package manifest

The `apm.yml` defines what the package contains:

```yaml
# apm.yml
name: acme-standards
version: "1.0.0"
description: "Acme Corp organization-wide AI agent standards"
```

## Layered composition

Shared packages become powerful when you layer them. Build from broad to narrow — org-wide, then team-specific, then project-specific.

### Team package — extends the org base

```yaml
# acme-corp/acme-team-frontend/apm.yml
name: acme-team-frontend
version: "1.0.0"
description: "Frontend team standards, extends org base"

dependencies:
  apm:
    - acme-corp/apm-standards        # org-wide base
    - acme-corp/frontend-skills      # frontend-specific capabilities
```

The team package adds frontend-specific instructions and agents while inheriting the org-wide security baseline and coding standards.

### Project — pulls in everything transitively

```yaml
# my-project/apm.yml
name: my-project

dependencies:
  apm:
    - acme-corp/acme-team-frontend   # pulls in org + team transitively
    - some-other/project-specific-pkg
```

After installing:

```bash
apm install
```

The project gets the full stack: org-wide standards from `apm-standards`, frontend-specific skills from `frontend-skills`, team configuration from `acme-team-frontend`, and anything from `project-specific-pkg` — all resolved and deployed automatically.

### Override order

When files from different packages target the same path, the most specific package wins:

1. Project-local files (highest priority)
2. Direct dependencies
3. Transitive dependencies (lowest priority)

This means a project can always override an org default when it has a legitimate reason to diverge.

## Versioning strategy

### Tagging releases

Use git tags to mark versions of your standards package:

```bash
# In the standards package repo
git add -A && git commit -m "Add API design standards"
git tag v1.0.0
git push origin main --tags
```

### Consumer pinning

Consumers reference specific versions to control when they adopt changes:

```yaml
# Pin to exact version
dependencies:
  apm:
    - acme-corp/apm-standards@v1.0.0

# Pin to major version (gets v1.x.x updates)
dependencies:
  apm:
    - acme-corp/apm-standards@v1
```

Regardless of the version specifier, `apm.lock` always pins the exact commit SHA. This guarantees reproducible installs even if the tag is moved.

### When to bump versions

- **Patch** (v1.0.1): Fix typos, clarify wording, add non-breaking examples.
- **Minor** (v1.1.0): Add new instructions or agents. Existing behavior unchanged.
- **Major** (v2.0.0): Remove or rename files, change agent behavior, restructure directories.

## Update workflow

### Package author

When updating the standards package:

```bash
# Make changes to instructions, agents, prompts, or skills
# ...

# Test before publishing
apm compile --dry-run

# Commit, tag, push
git add -A && git commit -m "Tighten input validation policy"
git tag v1.1.0
git push origin main --tags
```

### Consumer

To pick up the latest version within your pinned range:

```bash
apm deps update
```

This updates `apm.lock` to the latest commit matching your version pin and deploys the updated files.

### CI integration

In continuous integration, always use the lock file for reproducible builds:

```bash
# CI pipeline — installs exact versions from lock file
apm install
```

This ensures every CI run uses the same dependency versions, regardless of what has been published since.

## Best practices

**Keep packages focused.** Separate concerns into distinct packages rather than bundling everything into a monolith:

- `acme-corp/security-baseline` — security policies and review agents
- `acme-corp/coding-standards` — language-specific coding guidelines
- `acme-corp/review-agents` — standard code review agent configurations

This lets teams adopt what they need without pulling in irrelevant configuration.

**Use semantic versioning for breaking changes.** Consumers rely on version pins to control their upgrade cadence. A surprise rename or deletion in a patch release breaks trust and workflows.

**Document what each package provides.** Include a clear README in every standards package listing the files it deploys and what each one does. Consumers should know what they're getting without reading every file.

**Test before tagging.** Run `apm compile --dry-run` to verify the package compiles cleanly before publishing a new version. Catch issues before they propagate to consumers.

**Start small.** Begin with one focused package — security baseline is a good first choice. Expand to additional packages as patterns emerge. It is easier to split a package later than to merge two that diverged.

**Review changes like code.** Standards packages affect every repo in the org. Treat updates with the same rigor as production code changes — pull requests, reviews, and testing.

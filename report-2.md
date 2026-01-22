# Report II: Skills Composability & The True npm Analogy

*Follow-up analysis on transitive dependencies, composability, and enterprise scope*

## The Insight: Skills as a Craft

Building Skills will become a craft, just as building npm packages became a craft in the JavaScript ecosystem.

---

## Part 1: The Pure npm Analogy

### What npm Actually Does (That Matters)

| npm Capability | What It Solves | APM Equivalent |
|----------------|----------------|----------------|
| npm install lodash | Fetch package from registry | apm install owner/skill |
| package.json dependencies | Declare what you need | apm.yml dependencies |
| node_modules/ | Local storage of dependencies | apm_modules/ |
| Transitive resolution | lodash needs isequal, npm fetches both | APM resolves skill dependencies |
| Lockfile | Deterministic builds | apm.lock |
| Semantic versioning | ^1.2.0 means compatible upgrades | Version constraints in apm.yml |
| npm publish | Push to registry | apm publish (future) |

### What npm Does Not Do (Built Later by Others)

| Feature | Who Added It | Why It Exists |
|---------|--------------|---------------|
| Monorepo workspaces | npm v7+ / yarn / pnpm | Enterprise scale |
| Private registries | npm Enterprise / Artifactory | IP protection |
| Security audits | npm audit | Supply chain attacks |
| Governance policies | Enterprise tooling | Compliance |

**Key insight:** npm core value was installability + transitivity. Everything else came years later.

---

## Part 2: What APM Phase 2 Actually Needs

### The Core: Transitive Skill Dependencies

This is the single most important feature for APM to nail.

**Scenario: form-builder depends on validation-patterns**

form-builder/apm.yml:
- name: form-builder
- version: 1.0.0
- dependencies: danielmeppiel/validation-patterns@^1.0.0

validation-patterns/apm.yml:
- name: validation-patterns
- version: 1.2.0
- dependencies: danielmeppiel/error-handling@^2.0.0

When someone runs: apm install danielmeppiel/form-builder

APM should:
1. Fetch form-builder
2. Parse its apm.yml, find dependency on validation-patterns
3. Fetch validation-patterns
4. Parse its apm.yml, find dependency on error-handling
5. Fetch error-handling
6. Store all three in apm_modules/
7. Write apm.lock with exact versions

**This is the craft enabler.** Skill authors can now:
- Build on each others work
- Create layered, composable capabilities
- Share common patterns without duplication

### Conflict Detection & Resolution

When two skills have conflicting instructions:

1. Detect the conflict at install time
2. Warn the user with specific conflict details
3. Allow explicit resolution in apm.yml via resolutions field

---

## Part 3: What We Do Not Need Yet (Enterprise Bloat Analysis)

### Governance Policies in apm.yml - NOT NEEDED

Reality Check: This is enterprise tooling built on top of npm (Artifactory, Nexus). APM does not need this built-in. The file system is the governance layer.

Verdict: Skip. Let enterprises build their own layer.

### Org-wide Baseline Config - NOT NEEDED

Reality Check: Anthropic already handles this via Admin Settings. APM role is development workflow, not runtime provisioning.

Verdict: Skip. Vendor territory.

### Audit Logging - NOT NEEDED

Reality Check: APM is a build-time tool. Git history provides the audit trail.

Verdict: Skip. Git is the audit log.

### Private Registries - MAYBE LATER

Reality Check: npm initially only had public registry. APM already supports private GitHub repos and Azure DevOps via PATs.

Verdict: Defer. Current auth model suffices.

### apm validate - YES, BUT MINIMAL

Reality Check: Value for skill authors, not consumers. A malformed SKILL.md will not be discovered.

Simple checks only:
- Does SKILL.md exist?
- Required sections present (name, description, when-to-use)?
- Dependencies resolvable?

Verdict: Keep, but keep it simple. It is a linter for skill authors.

---

## Part 4: Revised Phase 2 Scope

### Phase 2: Skills Composition (Essential)

| Feature | Why It Matters | Complexity |
|---------|----------------|------------|
| Transitive dependency resolution | Core npm value prop | Medium |
| apm.lock file | Deterministic installs | Low |
| Semver constraint parsing | ^1.0.0, ~1.0.0, >=1.0.0 | Low |
| Conflict detection | Warn when skills clash | Medium |
| Skills-in-skills imports | SKILL.md skill:// references | Low |
| apm compile merges skill instructions | Unified AGENTS.md from skill graph | Medium |

### Phase 2.5: Author Experience (Nice to Have)

| Feature | Why It Matters | Complexity |
|---------|----------------|------------|
| apm init skill | Scaffold a new skill | Low |
| apm validate | Lint skill structure | Low |
| Local skill dev mode | Test skill before publishing | Low |

### Deferred (Phase 4+): Enterprise

- Private registries (beyond PAT auth)
- Governance policies
- Audit logging
- Org-wide configuration

---

## Part 5: The Mental Model for Skill Authors

### Level 1: Simple Skill (Single Capability)

validation-patterns/
  SKILL.md
  instructions/
    validation.instructions.md

### Level 2: Composed Skill (Depends on Others)

form-builder/
  SKILL.md (references skill://validation-patterns)
  instructions/
    forms.instructions.md
  prompts/
    create-form.prompt.md
  apm.yml (declares validation-patterns dependency)

### Level 3: Meta-Skill (Orchestrates Multiple Skills)

full-stack-starter/
  SKILL.md (meta-guide for the whole stack)
  apm.yml (depends on form-builder, auth-patterns, api-client)
  agents/
    full-stack-dev.agent.md

This is the npm trajectory: Simple packages -> composed packages -> meta-frameworks.

---

## Conclusion: Keep It Simple, Nail Transitivity

APM Phase 2 should focus on one thing:

> Make Skills composable through transitive dependency resolution, just like npm made JavaScript modules composable.

Everything else is either:
- Already handled (private repos via PATs)
- Vendor territory (runtime provisioning)
- Future optimization (registries, governance)

The craft of building Skills will emerge naturally once authors can:
1. Depend on other Skills
2. Have those dependencies resolved automatically
3. Trust that apm install gives them a working, deterministic setup

That is the npm magic. That is what APM Phase 2 needs to deliver.

---

## Updated Roadmap

### Phase 1: Skills-First (Current)
- Install Skills from GitHub/Azure DevOps
- Recognize SKILL.md as discovery trigger
- Copy to .github/skills/ and .claude/skills/

### Phase 2: Composable Skills (Next Priority)
- Parse apm.yml for transitive dependencies
- Semver constraint resolution
- apm.lock for determinism
- Conflict detection with warnings
- apm compile merges skill graph

### Phase 2.5: Author Experience
- apm init skill scaffolding
- apm validate linting
- Local skill testing

### Phase 3+: Scale (Later)
- apm publish to registry (if ecosystem demands)
- Performance optimizations
- Cross-organization sharing patterns
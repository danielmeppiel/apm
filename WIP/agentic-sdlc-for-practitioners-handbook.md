# Agentic SDLC for Practitioners

**A handbook for AI Engineers who ship large chunks of software by orchestrating agent fleets — without writing a single line of classic code.**

---

## Who This Is For

You are an AI Native Developer. Your job is to think about overall plan and orchestration, and capture it in markdown files that compose together — agents, skills, instructions, plugin bundles. You do not write production code. You may not even type — you might speak to terminals running Copilot CLI using voice input. You review specs, not diffs.

This handbook codifies battle-tested patterns for using GitHub Copilot CLI as your **harness** — the orchestration engine that translates your strategic intent into parallel agent work, tracks progress internally, validates results, and ships.

The patterns were forged on a real PR: **70 files changed, +5,886 / -1,030 lines, 30 commits, 2,874 tests green** — an auth + logging architecture overhaul touching five cross-cutting concerns. One human. Two AI teams. Four waves. Zero regressions. Roughly 90 minutes of wall-clock time for what would be 2-3 days of manual work.

This is not theory. Every section is immediately actionable.

---

## Table of Contents

1. [The Three Actors](#1-the-three-actors)
2. [The Thesis](#2-the-thesis)
3. [Repository Instrumentation: Markdown Is Your Codebase](#3-repository-instrumentation-markdown-is-your-codebase)
4. [The Meta-Process](#4-the-meta-process)
5. [The Planning Discipline](#5-the-planning-discipline)
6. [Team Topology](#6-team-topology)
7. [Wave Execution](#7-wave-execution)
8. [Checkpoint Discipline](#8-checkpoint-discipline)
9. [The Test Ring Pipeline](#9-the-test-ring-pipeline)
10. [Escalation Protocol](#10-escalation-protocol)
11. [The Feedback Loop](#11-the-feedback-loop)
12. [Autonomous CI/CD](#12-autonomous-cicd)
13. [Anti-Patterns](#13-anti-patterns)
14. [Scaling Characteristics](#14-scaling-characteristics)
15. [Example Scenarios](#15-example-scenarios)

---

## 1. The Three Actors

Every interaction in the agentic SDLC involves three distinct actors. Keeping them separate is critical to understanding the system.

### You (the AI Native Developer)

You are the strategist. You think in plans, not in code. You:

- **Iterate on specs** — your primary creative output is the plan (scope, teams, waves, principles)
- **Commission audits** — you tell the harness what to investigate
- **Validate results** — you skim specs, spot-check outputs, approve or reject
- **Make strategic calls** — scope decisions, trade-offs, escalation handling
- **Extract lessons** — when something fails, you improve the agent primitives

You parallelize *planning tasks*, not coding tasks. You might have multiple Copilot CLI sessions running — one exploring architecture, one drafting a logging plan, one reviewing a security audit — all converging into a single spec.

You might work from a laptop, a phone (GitHub App on iPhone), or by speaking to terminals using voice input (e.g., Handy for macOS). The interface is natural language. The output is markdown.

### The Harness (GitHub Copilot CLI)

The harness is your orchestration engine. When you describe what you want, the harness:

- **Translates your intent into agent dispatches** — it decides which tools to call, how to parallelize, when to checkpoint
- **Tracks state internally** — the harness maintains task lists, dependency graphs, and progress tracking in its own session database (SQL tables, session state). You see the plan; the harness manages the machinery.
- **Runs the test pipeline** — after each wave, the harness executes test suites and reports results
- **Manages agent lifecycle** — dispatching, monitoring, reading results, handling failures
- **Activates skills automatically** — when code patterns match, the harness loads the relevant skill rules

You interact with the harness in natural language. You say "dispatch the architecture team for Wave 0" and the harness translates that into parallel agent launches, SQL state updates, file edits, and test runs. The harness's internal mechanics (tool calls, SQL queries, session state management) are implementation details — visible if you want to inspect them, but not something you need to manage.

### The Agents (the Fleet)

Agents are specialized AI engineers dispatched by the harness. Each agent:

- Has a **persona** defined by an agent file (`.github/agents/*.agent.md`)
- Follows **skill rules** activated by the code it touches (`.github/skills/*/SKILL.md`)
- Operates in a **stateless context** — every dispatch starts fresh, with only the prompt as context
- **Writes code, runs tests, reports back** — then terminates

Agents don't know about each other. They don't know about the wave graph. They don't manage state. They receive surgical instructions and execute them. The harness coordinates everything.

```
You (strategist)
  │
  │  natural language prompts
  ▼
Harness (Copilot CLI)
  │
  │  parallel dispatches with precise instructions
  ▼
Agents (the fleet)
  │
  │  code changes, test results, findings
  ▼
Harness (validates, checkpoints, reports back to you)
```

---

## 2. The Thesis

Traditional software development scales linearly with humans. Agentic development scales with orchestration quality.

**You do not parallelize coding tasks. You parallelize planning tasks.** Your creative energy goes into the spec — the plan, the team composition, the wave structure, the principles. Once the spec is right, execution is mechanical: the harness dispatches agents, agents write code, tests validate, you merge.

**Your spec always carries the definition of the Agent Team who will implement it.** The plan isn't just "what to build" — it's "who builds it, in what order, with what constraints." The team composition (architect, logging expert, auth specialist) is part of the spec, not an afterthought.

**If you are not confident in your pipeline, you haven't engineered it correctly.** Confidence comes from:

- Agent primitives (personas, skills, instructions) that encode your project's patterns
- Test rings that catch regressions at every checkpoint
- Escalation protocols that surface genuine decisions to you and handle everything else autonomously
- Feedback loops that harden the system after every failure

**Green CI/CD means click merge and don't look back.** If your test rings, code review agents, and security scans pass — that's the signal. You don't re-read the code. You trust the pipeline you engineered.

**An AI Engineer extracts lessons from failure and improves the Agent Primitives.** When an agent makes a mistake, you don't fix the code — you fix the agent's persona, the skill rules, or the instructions that led to the mistake. The system gets better with every iteration. You code in markdown.

---

## 3. Repository Instrumentation: Markdown Is Your Codebase

Before the agentic SDLC works at scale, your repository needs three instrumentation layers. These are one-time investments that pay dividends on every future change. They are all markdown files.

### Layer 1: Agent Personas (`.github/agents/*.agent.md`)

Agent files define *who* your AI engineers are. Each file creates a specialist with domain knowledge, calibrated judgment, and a consistent voice.

```yaml
# .github/agents/python-architect.agent.md
---
name: python-architect
description: >-
  Expert on Python design patterns, modularization, and scalable architecture.
  Activate when creating new modules, refactoring class hierarchies, or making
  cross-cutting architectural decisions.
model: claude-opus-4.6
---

# Python Architect

You are an expert Python architect specializing in CLI tool design.

## Design Philosophy
- Speed and simplicity over complexity
- Solid foundation, iterate
- Pay only for what you touch

## Patterns You Enforce
- BaseIntegrator for all file-level integrators
- CommandLogger for all CLI output
- AuthResolver for all credential access
```

**Design principles for agent personas:**

| Principle | Why | Example |
|-----------|-----|---------|
| Domain-specific knowledge | Generic agents make generic mistakes | Auth expert knows EMU tokens use standard prefixes |
| Opinionated defaults | Reduces decisions per task | "Always use `logger.progress()`, never `_rich_info()`" |
| Named patterns | Agents can reference by name | "Follow the BaseIntegrator pattern" |
| Anti-patterns section | Prevent known mistakes | "Never instantiate AuthResolver per-request" |

**Recommended personas for a typical project:**

```
.github/agents/
├── python-architect.agent.md     # Structure, patterns, SoC
├── cli-logging-expert.agent.md   # Output UX, CommandLogger
├── auth-expert.agent.md          # Token management, credential flows
├── doc-writer.agent.md           # Documentation consistency
└── security-reviewer.agent.md    # Injection, traversal, leaks
```

### Layer 2: Skills (`.github/skills/*/SKILL.md`)

Skills are *when-to-activate* rules paired with *how-to-do-it* guidelines. The harness fires them automatically when it detects matching code patterns.

```yaml
# .github/skills/cli-logging-ux/SKILL.md
---
name: cli-logging-ux
description: >
  Activate whenever code touches console helpers, DiagnosticCollector,
  STATUS_SYMBOLS, CommandLogger, or any user-facing terminal output.
---

## Decision Framework

### 1. The "So What?" Test
Every warning must answer: what should the user do about this?

### 2. The Traffic Light Rule
| Color  | Helper           | Meaning            |
|--------|------------------|--------------------|
| Green  | _rich_success()  | Completed          |
| Yellow | _rich_warning()  | User action needed |
| Red    | _rich_error()    | Cannot continue    |
| Blue   | _rich_info()     | Status update      |

### 3. The Newspaper Test
Can the user scan output like headlines?
```

**Skills vs. Agents**: Agents are *who* (persona + model). Skills are *what* (rules + patterns). A skill references an agent persona for its voice but provides the domain-specific rules the agent follows.

### Layer 3: Instructions (`.github/instructions/*.instructions.md`)

Instructions are file-pattern-scoped rules that the harness applies automatically when code in matching paths is edited.

```yaml
# .github/instructions/integrators.instructions.md
---
applyTo: "src/app/integration/**"
description: "Architecture rules for file-level integrators"
---

# Integrator Architecture

## Required structure
Every integrator MUST extend BaseIntegrator and return IntegrationResult.

## Base-class methods — use, don't reimplement
| Operation          | Use                          | Never                    |
|--------------------|------------------------------|--------------------------|
| Collision detection| self.check_collision()       | Custom existence checks  |
| File discovery     | self.find_files_by_glob()    | Ad-hoc os.walk           |
```

**The three layers form a cascade:**

```
Instructions (auto-scoped by file path)
    └─ Skills (auto-activated by code patterns)
        └─ Agents (dispatched by harness for specific tasks)
```

These markdown files *are* your codebase as an AI Engineer. When an agent makes a mistake, you don't fix the generated code — you fix the agent persona, the skill rules, or the instruction file that led to the mistake.

---

## 4. The Meta-Process

Every large change goes through these phases, in order:

```
AUDIT ──→ PLAN ──→ WAVE[0..N] ──→ VALIDATE ──→ SHIP
            ↑          │
            └── ADAPT (on escalation only)
```

### Phase: AUDIT

**Your action**: Tell the harness to dispatch expert agents to analyze the codebase from different angles.

**What you say**: "Dispatch the architect and the logging expert to audit the auth and logging code. I want severity-ranked findings with file:line citations."

**What happens**: The harness launches 2-4 parallel explore agents, each with a distinct audit lens (architecture, logging/UX, security, performance). They produce ranked findings with `CRITICAL / HIGH / MODERATE / LOW` severity, exact file:line references, and remediation guidance.

**Key rule**: Audits are *read-only*. The agents explore, they don't modify.

### Phase: PLAN

**Your action**: Review audit findings. Decide scope. Define teams. Approve the wave structure.

**What you say**: "Include all findings in scope. Use two teams: architecture led by the python-architect, logging led by the cli-logging-expert. Organize into waves."

**What happens**: The harness synthesizes audit reports into a plan (`plan.md`) with scope, findings, wave breakdown, and team assignments. Internally, it tracks tasks and dependencies in its session database. You see the plan; the harness manages the execution graph.

**Key rule**: No implementation starts until you approve the plan. This is the single most important gate. Take your time here — this is where your leverage is highest.

### Phase: WAVE EXECUTION

**Your action**: Approve each wave. Monitor progress. Intervene only on escalation.

**What you say**: "Execute Wave 0" or "Deploy the fleet" (if you trust the plan enough to run all waves).

**What happens**: The harness dispatches parallel agents for each wave, grouped by file to avoid conflicts. It tracks which tasks are in progress, waits for agent completions, runs the test suite, and reports results. Between waves, it checkpoints: commit, update task status, verify no regressions.

### Phase: VALIDATE

**Your action**: Review the final state. Spot-check critical changes.

**What happens**: The harness runs the full test suite, acceptance tests, and optionally integration/E2E tests. It produces a summary of what changed, what passed, and any diagnostics.

### Phase: SHIP

**Your action**: Approve the push. Update changelog if the harness hasn't already.

**What happens**: Commit, changelog, push. If CI is green, merge. Don't look back.

---

## 5. The Planning Discipline

Planning is where you have the most leverage. A mediocre plan with perfect execution produces mediocre software. A great plan with imperfect execution produces great software — because the test rings catch the imperfections.

### The Spec Carries the Team

Your plan isn't just "what to build." It includes:

1. **Scope**: What's in, what's out, what's follow-up
2. **Agent Team**: Which personas implement which concerns
3. **Wave Graph**: Dependency-ordered execution batches
4. **Principles**: Priority-ordered values that anchor every decision
5. **Constraints**: What NOT to change (critical for surgical edits)

Example plan structure:

```markdown
## Scope
Auth resolver dedup, verbose coverage gaps, CommandLogger migration, unicode cleanup.
Out of scope: New auth providers, CLI help text changes.

## Teams
- Architecture: python-architect leads. Owns: type safety, SoC, dead code.
- Logging/UX: cli-logging-expert leads. Owns: verbose coverage, CommandLogger, symbols.

## Waves
Wave 0 (foundation): Protocol types, method moves, dedup — fully parallel
Wave 1 (core): Verbose coverage — depends on Wave 0 APIs
Wave 2 (migration): CommandLogger migration — depends on Wave 1 patterns
Wave 3 (polish): Unicode cleanup — depends on Wave 2 completeness

## Principles (priority order)
1. SECURITY — no token leaks, no path traversal
2. CORRECTNESS — tests pass, behavior preserved
3. UX — world-class developer experience in every message
4. KISS — simplest correct solution
5. SHIP SPEED — favor shipping over perfection
```

### Red Teaming and Panel Discussions

For critical plans, have the agent team iterate through adversarial review before execution:

1. **Architect reviews the logging plan** — "Does this create coupling between modules?"
2. **Logging expert reviews the architecture plan** — "Does this break verbose output contracts?"
3. **Security reviewer scans both** — "Does any change expose tokens in logs?"

The agents iterate until reaching consensus. The release manager agent (or a business-owner persona) has the last word on trade-offs. You review the consensus, not the individual arguments.

### Code Review + Security as Parallel Gates

After the agent team produces code, two more agents run in parallel:

- **Code Reviewer**: Surfaces only bugs, logic errors, and security vulnerabilities. Never comments on style.
- **Security Scanner**: Checks for token leaks, path traversal, injection, unsafe operations.

If either finds issues, the work returns to the agent team in a loop. You're only pulled in if the loop doesn't converge (escalation — see §10).

---

## 6. Team Topology

Structure your AI teams by concern, not by file. Each team has a lead persona (the agent file) and members (agents dispatched by the harness following the relevant skill).

### Reference: Two-Team Structure

For most cross-cutting changes, two teams cover the space:

```
┌─────────────────────────────┐  ┌─────────────────────────────┐
│   ARCHITECTURE TEAM         │  │   DOMAIN EXPERT TEAM        │
│                             │  │                             │
│   Lead: python-architect    │  │   Lead: cli-logging-expert  │
│   Skill: python-architecture│  │   Skill: cli-logging-ux     │
│                             │  │                             │
│   Owns:                     │  │   Owns:                     │
│   - Type safety             │  │   - Verbose coverage        │
│   - Pattern compliance      │  │   - CommandLogger migration │
│   - SoC violations          │  │   - Traffic-light fixes     │
│   - Dead code removal       │  │   - Unicode cleanup         │
│   - DiagnosticCollector     │  │   - Actionability audit     │
│     routing                 │  │                             │
└─────────────────────────────┘  └─────────────────────────────┘
```

### Scaling Up

For larger changes, split further:

| Team | Lead Agent | Skill | Owns |
|------|-----------|-------|------|
| Architecture | python-architect | python-architecture | Patterns, types, SoC |
| Logging/UX | cli-logging-expert | cli-logging-ux | Output, verbose, symbols |
| Auth | auth-expert | auth | Tokens, credentials, hosts |
| Security | security-reviewer | (inline) | Scanning, traversal, leaks |
| Docs | doc-writer | (inline) | Guides, reference, changelog |

### Scaling Down

For focused changes (single concern, < 20 files):

| Approach | When |
|----------|------|
| Solo expert | One agent with the relevant skill, single wave |
| Audit + fix | One explore agent to audit, one general-purpose to fix |

---

## 7. Wave Execution

Waves are the core execution unit. Each wave is a batch of tasks with no unmet dependencies, dispatched as parallel agents grouped by file, followed by a checkpoint.

### Wave Structure

```
Wave 0: FOUNDATION    ← No dependencies, fully parallel
Wave 1: CORE CHANGES  ← Depends on Wave 0 outputs
Wave 2: MIGRATION     ← Depends on Wave 1 patterns being stable
Wave 3: POLISH        ← Depends on Wave 2 being complete
Wave 4: VALIDATE      ← Final gate
```

### Rules for Wave Design

**Rule 1: One file, one agent per wave.**

The harness edits files using string matching. If two parallel agents edit the same file, the second agent's edits will fail because the first agent changed the file content.

```
# GOOD: Each agent owns distinct files
Agent A: apm_resolver.py, dependency_graph.py
Agent B: install.py (all sections)

# BAD: Two agents on the same file
Agent B: install.py (lines 240-440)
Agent C: install.py (lines 580-2100)  ← CONFLICT
```

**Rule 2: Foundation before migration.**

Type changes, protocol definitions, and method moves go in Wave 0. Code that *uses* those new APIs goes in Wave 1+.

**Rule 3: Small waves ship faster than large waves.**

A wave with 2-3 agents completes in 3-5 minutes. A wave with 8 agents takes 8-10 minutes (longest agent dominates). Prefer more smaller waves.

**Rule 4: Every wave ends with green tests.**

Non-negotiable. The harness runs the full test suite after each wave and commits only if all tests pass.

### How the Harness Executes a Wave

When you say "execute Wave 0", the harness:

1. Identifies which tasks in the plan are ready (no unfinished dependencies)
2. Groups tasks by file ownership to avoid conflicts
3. Dispatches parallel agents with precise instructions (files, line numbers, code patterns, constraints)
4. Waits for all agents to complete
5. Runs the full test suite
6. If green: commits with a wave-specific message, marks tasks as done
7. If red: reports failures to you for triage

You see the results. The harness manages the dispatching, state tracking, and checkpointing internally.

---

## 8. Checkpoint Discipline

A checkpoint is the pause point between waves. It serves four purposes:

### 1. Validation Gate

The harness runs the full test suite after every wave. This is non-negotiable — no wave is considered complete until tests are green.

### 2. Spot-Check

You review a sample of agent changes. Focus on:

- **Boundary conditions**: Did the agent handle the edge case you specified?
- **Pattern compliance**: Did the agent follow established patterns, or invent new ones?
- **Scope discipline**: Did the agent change only what was asked?

Quick checks you can ask for:

```
"Show me the diff for install.py"
"How many _rich_info calls remain in the codebase?"
"Did the agent add tests for the new code path?"
```

### 3. Commit Boundary

Every wave gets its own commit. This enables:
- Bisection if a later wave introduces a regression
- Reverting a single wave without affecting others
- Clean PR history for reviewers

### 4. Process Adaptation (Rare)

At a checkpoint, you may adapt the remaining plan if:
- An agent discovered a blocker not in the original audit
- A task turned out to be larger than expected
- Two tasks created an unexpected conflict

**Rule**: Adaptation is conservative. Add tasks, split tasks, reorder waves. Never skip validation.

---

## 9. The Test Ring Pipeline

Tests are the safety net that makes the entire system trustworthy. Without them, you cannot confidently merge. With them, green CI/CD means click merge and don't look back.

### Ring 1: Unit Tests (Every Wave)

Fast, deterministic, run after every wave. These catch regressions in logic, type errors, and broken interfaces.

**Coverage principle**: When modifying existing code, add tests for the code paths you touch, on top of tests for new functionality.

### Ring 2: Acceptance Tests (After Final Wave)

Scenario-based tests that verify end-to-end behavior from the user's perspective. Mocked external dependencies, but real command invocations and output verification.

### Ring 3: Integration / E2E Tests (Pre-Ship)

Real-world tests against actual infrastructure. These require credentials, network access, and real repositories. They validate the exact binary/package that ships.

### Test Ring Policy

| Ring | When | Blocks | Flake Policy |
|------|------|--------|--------------|
| Unit | Every wave | Next wave | Zero tolerance |
| Acceptance | Final wave | Ship | Zero tolerance |
| Integration | Pre-ship | Ship | Re-run once, then investigate |

### The Confidence Argument

If your test rings are comprehensive and passing, you don't need to read every line of agent-generated code. The tests *are* the specification. If the tests pass, the code meets the spec. If you're not confident in this, it means your test coverage isn't good enough — fix the tests, not the process.

---

## 10. Escalation Protocol

The agentic process runs autonomously within the plan. Escalation happens when the harness or an agent encounters something outside the plan's scope.

### Escalation Levels

| Level | Trigger | Who Handles | Action |
|-------|---------|-------------|--------|
| **L0: Self-heal** | Agent hits a test failure it can debug | Agent (via harness retry) | Fix and continue |
| **L1: Harness** | Agent reports a blocker or unexpected finding | Harness adapts plan | Re-dispatch with refined prompt |
| **L2: You decide** | Trade-off between competing principles | You | Decide, document rationale |
| **L3: Scope change** | Finding requires work outside the current PR | You + stakeholders | Create follow-up issue |

### When the Harness Escalates to You

The harness brings you in (L2) only when:

1. **Principle conflict**: "KISS says skip this, but security says we must fix it."
2. **Scope explosion**: "Fixing this properly requires changing 15 more files."
3. **Breaking change**: "This fix changes CLI output that users depend on."
4. **Ambiguity**: "The audit found two valid approaches; both have trade-offs."

Everything else the harness handles autonomously. If an agent fails, the harness retries with a refined prompt. If a test fails, the harness debugs it. If a task is larger than expected, the harness splits it.

### The Anchoring Principle

Every decision — yours or the harness's — is anchored on project principles, in priority order:

```
1. SECURITY     — No token leaks, no path traversal, no injection
2. CORRECTNESS  — Tests pass, behavior preserved, edge cases handled
3. UX           — World-class developer experience in every message
4. KISS         — Simplest solution that's correct and secure
5. SHIP SPEED   — Favor shipping over perfection
```

When principles conflict, higher-priority wins. Document the trade-off in the commit message.

---

## 11. The Feedback Loop

When something goes wrong — an agent makes a mistake, a test ring misses a bug, a pattern drifts — you don't fix the symptom. You fix the system.

### The Primitive Improvement Cycle

```
Failure observed
    │
    ▼
Root cause: which primitive failed?
    │
    ├─ Agent persona too generic?    → Add domain knowledge to .agent.md
    ├─ Skill rules incomplete?       → Add anti-pattern to SKILL.md
    ├─ Instructions missing?         → Add file-pattern rule to .instructions.md
    ├─ Test coverage gap?            → Add acceptance test for the scenario
    └─ Harness prompt too vague?     → Refine your prompt template
```

**Examples from the reference case:**

| Failure | Root Cause | Primitive Fix |
|---------|-----------|---------------|
| Agent used `_rich_info()` directly instead of `logger.progress()` | Skill didn't explicitly ban direct calls | Added "Rule: No direct `_rich_*` in commands" to cli-logging-ux SKILL.md |
| Agent invented a new collision detection pattern | Instructions didn't list all base-class methods | Added full "use, don't reimplement" table to integrators.instructions.md |
| Agent claimed success but file wasn't persisted | Harness trusted agent self-report | Added spot-check step to checkpoint protocol |
| Unicode symbols weren't consistent | No single source of truth for symbols | Created STATUS_SYMBOLS dict, added to skill rules |

This is how you "code" as an AI Engineer. Every failure makes the markdown primitives better. Every improvement makes future agents more reliable. The system compounds.

---

## 12. Autonomous CI/CD

The agentic SDLC doesn't stop when you merge. Autonomous GitHub Agentic Workflows run on a schedule to catch drift, gaps, and issues that accumulate over time.

### Scheduled Agentic Workflows

| Workflow | Schedule | What It Does |
|----------|----------|-------------|
| Drift detection | Daily | Compares code patterns against instruction rules, flags violations |
| Dependency audit | Weekly | Scans for outdated deps, security advisories, license issues |
| Test coverage check | On PR | Verifies new code has adequate test coverage |
| Documentation sync | On PR | Checks if code changes require doc updates |

### The Autonomous Fix Loop

For low-risk issues (formatting, dependency bumps, doc sync), the workflow can:

1. Create a branch
2. Dispatch an agent to fix the issue
3. Run the test ring pipeline
4. Open a PR with the fix
5. If CI is green, auto-merge (or notify you for approval)

For higher-risk issues (pattern violations, security findings), the workflow opens an issue with findings and waits for you to plan the fix using the standard AUDIT → PLAN → WAVE flow.

### Why This Matters

Without autonomous workflows, entropy wins. Patterns drift. Dependencies rot. Documentation goes stale. The scheduled workflows are your immune system — they detect problems before they compound.

---

## 13. Anti-Patterns

### The Solo Hero

Dispatching one massive agent to do everything. It will lose context, make inconsistent decisions, and produce unreviewed code.

**Fix**: Split into focused agents with clear scope boundaries. One file, one agent per wave.

### The Context Bomb

Giving an agent the entire codebase as context. Agents work best with *precise* instructions: exact files, line numbers, before/after patterns.

**Fix**: Have the harness read the relevant files first, then give agents surgical instructions.

### The Trust Fall

Accepting agent output without validation. Agents can miss edge cases, introduce subtle bugs, claim success when tests actually fail, or report edits that weren't persisted.

**Fix**: The test ring pipeline catches most issues. Spot-check critical changes at checkpoints. Always verify file state matches what the agent reported.

### The Scope Creep Agent

An agent told to "fix logging in install.py" decides to also refactor imports, add type hints to unrelated functions, and reorganize the file.

**Fix**: Include explicit "Do NOT modify" rules in the plan. Be specific about scope boundaries.

### Same-File Parallel Edits

Two agents editing the same file simultaneously. The second agent's changes won't apply because the first agent changed the file.

**Fix**: One file, one agent per wave. Group related changes to the same file into a single agent's task.

### Skipping Checkpoints

"Wave 1 worked, Wave 2 probably works too, let me just commit both." Then Wave 3 fails and you can't bisect.

**Fix**: Test after every wave. Commit after every wave. The 2-minute cost saves hours of debugging.

### Not Fixing the Primitives

An agent keeps making the same mistake across sessions. You keep correcting it manually.

**Fix**: Find the root primitive (agent persona, skill, instruction) and add the missing rule. The system should learn, not repeat.

---

## 14. Scaling Characteristics

### What Scales Linearly

| Dimension | How It Scales |
|-----------|---------------|
| Files per wave | +1 agent per non-overlapping file group |
| Concerns per change | +1 team per concern |
| Test count | Run time increases, but the test ring pipeline structure is fixed |

### What Doesn't Scale

| Dimension | Bottleneck | Mitigation |
|-----------|-----------|------------|
| Same-file changes | Sequential within file | Group into fewer, larger agents |
| Cross-file dependencies | Wave serialization | Minimize cross-file APIs in Wave 0 |
| Your attention | Review bandwidth | Trust the test ring; spot-check, don't audit every line |

### Observed Performance (Reference Case)

```
Concern scope:       5 cross-cutting concerns
Files changed:       70
Lines changed:       +5,886 / -1,030
Commits:             30
Tests:               2,874 passing
Agents dispatched:   15 (across 4 waves + 2 audits)
Agent failures:      2 (1 connection error, 1 incomplete — both recovered)
Your interventions:  3 (scope decision, agent recovery, test fix)
Wall-clock time:     ~90 minutes (including audit, plan, all waves)
Regressions:         0
```

### The Safety Argument

Agentic development is *safer* than manual development for large changes because:

1. **Forced decomposition**: You must plan before coding. Most bugs come from insufficient planning.
2. **Parallel review**: Multiple specialized agents catch different classes of bugs.
3. **Mandatory test gates**: Every wave runs the full suite. No "I'll test later."
4. **Scope discipline**: Agents do exactly what they're told. No "while I'm here" changes.
5. **Audit trail**: Wave commits + plan.md = full provenance.

The pattern doesn't eliminate bugs. It eliminates the *categories* of bugs that come from cognitive overload, inconsistency across files, and deferred testing.

---

## 15. Example Scenarios

### Scenario A: Auth + Logging Overhaul (the reference case)

**Scope**: 70 files, 5 concerns (auth, logging, migration, unicode, testing)

| Phase | What You Did | What the Harness Did | Duration |
|-------|-------------|---------------------|----------|
| Audit | "Dispatch architect + logging expert" | 2 parallel explore agents | 3 min |
| Plan | Reviewed findings, set scope, approved waves | Created plan.md, tracked 19 tasks internally | 5 min |
| Wave 0 | "Execute Wave 0" | 2 parallel agents (resolver + install) | 5 min |
| Wave 1+2 | "Deploy the fleet" | 5 parallel agents (verbose + migration) | 8 min |
| Wave 2b | Recovered a stuck agent manually | 2 parallel agents + harness retry | 7 min |
| Wave 3 | "Polish wave" | 1 agent (unicode cleanup) | 4 min |
| Validate | Spot-checked install.py, reviewed CHANGELOG | Full suite, commit, push | 2 min |

**Total wall-clock**: ~35 minutes for what would be 2-3 days of manual work.

### Scenario B: New Module Addition

**Scope**: Add a new `apm bundle` command with export functionality.

```
Audit:  1 explore agent to assess existing patterns
Plan:   You define module structure + team
Wave 0: Architecture team designs module skeleton (1 agent)
Wave 1: Implement core module (1 agent)
Wave 2: Wire into CLI + add tests (2 agents: CLI wiring + test writing)
Wave 3: Documentation (1 doc-writer agent)
```

### Scenario C: Cross-Cutting Refactor

**Scope**: Replace all direct `os.getenv()` calls with a centralized config system.

```
Audit:  1 explore agent to find all os.getenv() call sites
Plan:   Group by module, design config class
Wave 0: Create config module + tests (1 agent)
Wave 1: Migrate each module in parallel (5 agents, one per module)
Wave 2: Remove old imports, verify no direct calls remain (1 agent)
```

### Scenario D: Security Hardening

**Scope**: Add path traversal protection across all file operations.

```
Audit:  Security expert + architecture expert (parallel)
Wave 0: Create path_security.py utility (1 agent)
Wave 1: Replace shutil.rmtree with safe_rmtree everywhere (3 agents by module)
Wave 2: Add ensure_path_within() to all user-derived paths (3 agents)
Wave 3: Security-focused test suite (1 agent)
```

---

## Appendix A: Repository Setup Checklist

```
□ .github/agents/          — At least: architect, domain-expert, doc-writer
□ .github/skills/          — One skill per cross-cutting concern
□ .github/instructions/    — File-pattern rules for key directories
□ .github/copilot-instructions.md — Project-wide conventions
□ Test suite               — Fast unit tests (< 3 min), acceptance tests
□ CHANGELOG.md             — Keep a Changelog format
□ CI pipeline              — PR tests, post-merge validation
```

## Appendix B: What You Say to the Harness (Prompt Examples)

These are examples of what *you* type (or speak) to Copilot CLI at each phase. The harness translates these into agent dispatches, tool calls, and state management internally.

### Audit Prompt

```
Dispatch the python-architect and cli-logging-expert to audit the auth and
logging code. For each finding, I want severity (CRITICAL/HIGH/MODERATE/LOW),
file:line, current behavior, expected behavior, and remediation.

Focus on: pattern violations, type safety, verbose coverage gaps,
traffic-light compliance. Do NOT suggest changes to the test infrastructure.
```

### Planning Prompt

```
Synthesize both audit reports into a plan. Include ALL findings in scope —
nothing deferred. Use two teams: architecture led by python-architect,
logging led by cli-logging-expert. Organize into waves by dependency.
Every wave must end with green tests.
```

### Wave Execution Prompt

```
Execute Wave 0. The foundation tasks have no dependencies — dispatch them
in parallel. Group by file to avoid conflicts.
```

Or, if you trust the plan fully:

```
Deploy the fleet in autopilot. Execute all waves sequentially. Stop and
escalate only if tests fail or an agent reports a blocker.
```

### Spot-Check Prompt

```
Show me the diff for install.py since the last commit. How many
_rich_info calls remain? Did any agent touch files outside their scope?
```

### Recovery Prompt (when an agent gets stuck)

```
The wave2-install-logger agent seems stuck. Take over its remaining tasks
manually. The agent was supposed to migrate 58 _rich_* calls in install.py
to use CommandLogger. Check what it completed and finish the rest.
```

## Appendix C: Harness Internals

This section documents how the harness (Copilot CLI) manages state internally. You don't need to manage these details, but understanding them helps you debug issues and make better prompts.

### Task Tracking

The harness maintains a SQL database in its session state with:

- **`todos` table**: Task ID, title, description, status (pending/in_progress/done/blocked)
- **`todo_deps` table**: Dependency edges between tasks

When you say "execute Wave 0", the harness queries for tasks with no unfinished dependencies, marks them as in_progress, dispatches agents, and marks them done when tests pass.

### Session State

The harness maintains:
- `plan.md` — human-readable plan (this is what you review and approve)
- Checkpoints — snapshots after each wave with history, decisions, and file lists
- Session database — SQL tables for task tracking (internal to the harness)

### Agent Dispatch

When the harness dispatches a `general-purpose` agent, it includes:

1. **Role statement**: "You are a [role] on the [team] team."
2. **Context**: What was done in previous waves that this depends on.
3. **Precise instructions**: Exact files, line numbers, old-to-new patterns.
4. **Rules**: What NOT to change.
5. **Verification commands**: Test commands to run before reporting done.

### Skill Activation

Skills activate automatically when the harness detects matching code patterns. They can also be activated explicitly when you mention a relevant concern.

### Why This Matters

Understanding the harness internals helps you:
- **Debug stuck waves**: "Check the task status — is something blocked?"
- **Refine prompts**: "The agent needs more precise file:line instructions"
- **Recover from failures**: "The agent said it finished but the file wasn't updated — check the harness state"


## Appendix D: Live Dashboard POC via Copilot CLI Hooks

### The Vision

The agentic SDLC described in this handbook is powerful but invisible — everything happens inside terminal scrollback. What if you could *see* it? A live browser dashboard showing:

- The wave dependency graph with real-time status (pending → running → done)
- Agent cards spawning and completing with duration timers
- File edits streaming in as they happen
- Test rings lighting up green/red after each checkpoint
- The todo board updating as SQL queries fire

This appendix describes a **proof-of-concept** using [Copilot CLI Hooks](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/use-hooks) to intercept every tool call and stream it to a live web UI — turning the agentic process into something you can watch, share on a screen, or use as an observability layer.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     Copilot CLI Session                          │
│                                                                  │
│  preToolUse ──→ ┌──────────────┐                                │
│  postToolUse ──→│  Hook Scripts │──→ JSONL event log             │
│  sessionStart ─→│  (.github/    │──→ HTTP push to dashboard      │
│  sessionEnd ───→│   hooks/)     │                                │
│                 └──────────────┘                                │
└──────────────────────────────────────────────────────────────────┘
         │                                    │
         ▼                                    ▼
   .hooks/events.jsonl              http://localhost:3391
                                          │
                                          ▼
                              ┌────────────────────┐
                              │   Browser Dashboard │
                              │                    │
                              │  ┌──────────────┐  │
                              │  │ Wave Graph    │  │
                              │  │ o-o-o-*-o    │  │
                              │  └──────────────┘  │
                              │  ┌──────────────┐  │
                              │  │ Agent Fleet   │  │
                              │  │ G  Y  G  W   │  │
                              │  └──────────────┘  │
                              │  ┌──────────────┐  │
                              │  │ Test Ring     │  │
                              │  │ Unit + Acc +  │  │
                              │  └──────────────┘  │
                              │  ┌──────────────┐  │
                              │  │ Todo Board    │  │
                              │  │ 12/19 done    │  │
                              │  └──────────────┘  │
                              └────────────────────┘
```

### Hook Event Model

Every Copilot CLI tool call passes through `preToolUse` and `postToolUse` hooks. The tool name and arguments tell us *exactly* what the orchestrator is doing:

| Tool Name | Args Pattern | Dashboard Event |
|-----------|-------------|----------------|
| `task` | `agent_type`, `name`, `mode` | Agent spawned — show card with spinner |
| `read_agent` | `agent_id` | Agent result read — update card with result |
| `sql` | `INSERT INTO todos` | New todo — add to board |
| `sql` | `UPDATE todos SET status` | Todo status change — move card |
| `bash` | command contains `pytest` | Test run — show ring with spinner |
| `bash` | command contains `git commit` | Checkpoint — mark wave complete |
| `edit` / `create` | `path` | File change — flash in activity feed |
| `report_intent` | `intent` | Phase change — update header |
| `skill` | `skill` name | Skill activated — show badge |

### hooks.json

```json
{
  "version": 1,
  "hooks": {
    "sessionStart": [
      {
        "type": "command",
        "bash": ".github/hooks/dashboard-start.sh",
        "timeoutSec": 5
      }
    ],
    "preToolUse": [
      {
        "type": "command",
        "bash": ".github/hooks/dashboard-event.sh",
        "timeoutSec": 3
      }
    ],
    "postToolUse": [
      {
        "type": "command",
        "bash": ".github/hooks/dashboard-event.sh",
        "timeoutSec": 3
      }
    ],
    "sessionEnd": [
      {
        "type": "command",
        "bash": ".github/hooks/dashboard-stop.sh",
        "timeoutSec": 5
      }
    ]
  }
}
```

### Event Collector Script

`.github/hooks/dashboard-event.sh` — runs on every tool call, must be fast (< 100ms):

```bash
#!/bin/bash
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.toolName // empty')
TIMESTAMP=$(echo "$INPUT" | jq -r '.timestamp')
RESULT_TYPE=$(echo "$INPUT" | jq -r '.toolResult.resultType // empty')

EVENT_LOG="${CWD:-.}/.hooks/events.jsonl"
WS_PORT="${DASHBOARD_PORT:-3391}"

# Phase: "pre" if no result, "post" if result present
if [ -n "$RESULT_TYPE" ]; then PHASE="post"; else PHASE="pre"; fi

EVENT_TYPE="tool"
DETAIL=""

case "$TOOL_NAME" in
  task)
    TOOL_ARGS=$(echo "$INPUT" | jq -r '.toolArgs // empty')
    AGENT_NAME=$(echo "$TOOL_ARGS" | jq -r '.name // empty')
    AGENT_TYPE=$(echo "$TOOL_ARGS" | jq -r '.agent_type // empty')
    AGENT_MODE=$(echo "$TOOL_ARGS" | jq -r '.mode // "sync"')
    AGENT_DESC=$(echo "$TOOL_ARGS" | jq -r '.description // empty')
    if [ "$PHASE" = "pre" ]; then
      EVENT_TYPE="agent_dispatch"
      DETAIL=$(jq -nc --arg n "$AGENT_NAME" --arg t "$AGENT_TYPE" \
        --arg m "$AGENT_MODE" --arg d "$AGENT_DESC" \
        '{name:$n, type:$t, mode:$m, description:$d}')
    fi ;;

  read_agent)
    if [ "$PHASE" = "post" ]; then
      AGENT_ID=$(echo "$INPUT" | jq -r '.toolArgs // empty' | jq -r '.agent_id // empty')
      SUMMARY=$(echo "$INPUT" | jq -r '.toolResult.textResultForLlm // ""' | head -c 200)
      EVENT_TYPE="agent_complete"
      DETAIL=$(jq -nc --arg id "$AGENT_ID" --arg s "$SUMMARY" '{agent_id:$id, summary:$s}')
    fi ;;

  sql)
    QUERY=$(echo "$INPUT" | jq -r '.toolArgs // empty' | jq -r '.query // empty')
    if echo "$QUERY" | grep -qi "UPDATE todos SET status"; then
      EVENT_TYPE="todo_update"
      STATUS=$(echo "$QUERY" | grep -oP "status\s*=\s*'\K[^']+")
      DETAIL=$(jq -nc --arg s "$STATUS" '{status:$s}')
    elif echo "$QUERY" | grep -qi "INSERT INTO todos"; then
      EVENT_TYPE="todo_create"
    fi ;;

  bash)
    COMMAND=$(echo "$INPUT" | jq -r '.toolArgs // empty' | jq -r '.command // empty')
    if echo "$COMMAND" | grep -q "pytest"; then
      [ "$PHASE" = "pre" ] && EVENT_TYPE="test_run_start"
      if [ "$PHASE" = "post" ]; then
        EVENT_TYPE="test_run_complete"
        RESULT_TEXT=$(echo "$INPUT" | jq -r '.toolResult.textResultForLlm // ""')
        PASSED=$(echo "$RESULT_TEXT" | grep -oP '\d+ passed' | head -1)
        FAILED=$(echo "$RESULT_TEXT" | grep -oP '\d+ failed' | head -1)
        DETAIL=$(jq -nc --arg p "$PASSED" --arg f "$FAILED" '{passed:$p, failed:$f}')
      fi
    elif echo "$COMMAND" | grep -q "git commit"; then
      EVENT_TYPE="checkpoint_commit"
    fi ;;

  edit|create)
    [ "$PHASE" = "pre" ] && {
      FILE_PATH=$(echo "$INPUT" | jq -r '.toolArgs // empty' | jq -r '.path // empty')
      EVENT_TYPE="file_change"
      DETAIL=$(jq -nc --arg p "$FILE_PATH" --arg op "$TOOL_NAME" '{path:$p, operation:$op}')
    } ;;

  report_intent)
    INTENT=$(echo "$INPUT" | jq -r '.toolArgs // empty' | jq -r '.intent // empty')
    EVENT_TYPE="intent_change"
    DETAIL=$(jq -nc --arg i "$INTENT" '{intent:$i}') ;;

  skill)
    SKILL=$(echo "$INPUT" | jq -r '.toolArgs // empty' | jq -r '.skill // empty')
    EVENT_TYPE="skill_activated"
    DETAIL=$(jq -nc --arg s "$SKILL" '{skill:$s}') ;;
esac

# Emit JSONL event
EVENT=$(jq -nc --arg type "$EVENT_TYPE" --arg phase "$PHASE" \
  --arg tool "$TOOL_NAME" --arg ts "$TIMESTAMP" --arg result "$RESULT_TYPE" \
  --argjson detail "${DETAIL:-null}" \
  '{type:$type, phase:$phase, tool:$tool, timestamp:$ts, result:$result, detail:$detail}')

echo "$EVENT" >> "$EVENT_LOG"

# Push to dashboard (non-blocking, fire-and-forget)
curl -s -X POST "http://localhost:$WS_PORT/event" \
  -H "Content-Type: application/json" -d "$EVENT" 2>/dev/null &
```

### Dashboard Server

`.github/hooks/dashboard-start.sh`:

```bash
#!/bin/bash
INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd')
PORT="${DASHBOARD_PORT:-3391}"

mkdir -p "$CWD/.hooks"
: > "$CWD/.hooks/events.jsonl"

if command -v node &>/dev/null; then
  node "$CWD/.github/hooks/dashboard-server.mjs" "$PORT" "$CWD/.hooks/events.jsonl" &
  echo $! > "$CWD/.hooks/dashboard.pid"
  echo "Dashboard: http://localhost:$PORT" >&2
fi
```

`.github/hooks/dashboard-server.mjs` — minimal SSE server:

```javascript
import { createServer } from 'http';
import { readFileSync, watchFile } from 'fs';

const PORT = parseInt(process.argv[2] || '3391');
const EVENTS_FILE = process.argv[3] || '.hooks/events.jsonl';
const clients = new Set();
let lastLineCount = 0;

watchFile(EVENTS_FILE, { interval: 200 }, () => {
  try {
    const lines = readFileSync(EVENTS_FILE, 'utf8').trim().split('\n');
    const newLines = lines.slice(lastLineCount);
    lastLineCount = lines.length;
    for (const line of newLines) {
      if (!line) continue;
      for (const client of clients) client.write(`data: ${line}\n\n`);
    }
  } catch {}
});

createServer((req, res) => {
  if (req.url === '/events') {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Access-Control-Allow-Origin': '*',
    });
    clients.add(res);
    req.on('close', () => clients.delete(res));
    return;
  }
  if (req.method === 'POST' && req.url === '/event') {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', () => {
      for (const client of clients) client.write(`data: ${body}\n\n`);
      res.writeHead(200).end('ok');
    });
    return;
  }
  // Serve inline dashboard HTML
  res.writeHead(200, { 'Content-Type': 'text/html' });
  res.end(DASHBOARD_HTML);
}).listen(PORT, () => console.log(`Dashboard: http://localhost:${PORT}`));

const DASHBOARD_HTML = `<!-- See dashboard UI section below -->`;
```

### Dashboard UI Layout

The dashboard renders four panels connected by SSE:

```
+-----------------------------------------------------------+
|  Agentic SDLC Dashboard           Phase: Executing Wave 2 |
+------------------------+----------------------------------+
|  WAVE GRAPH            |  AGENT FLEET                     |
|                        |                                   |
|  Wave 0 [========] +   |  +-----------------------------+ |
|  Wave 1 [========] +   |  | wave2-compile-logger        | |
|  Wave 2 [====    ] *   |  | general-purpose  3m 22s     | |
|  Wave 3 [        ]     |  | Status: running             | |
|  Wave 4 [        ]     |  +-----------------------------+ |
|                        |  +-----------------------------+ |
|                        |  | wave2-uninstall-logger      | |
|                        |  | general-purpose  4m 10s     | |
|                        |  | Status: + complete          | |
|                        |  +-----------------------------+ |
+------------------------+----------------------------------+
|  TODO BOARD            |  TEST RING & FILE ACTIVITY       |
|                        |                                   |
|  Done (14):            |  Ring 1: Unit    2874 +  103s    |
|  + a0-1 Protocol       |  Ring 2: Accept  39 +   2.1s    |
|  + a0-2 Ancestor       |  Ring 3: E2E     pending         |
|  + l0-1 TrafficLight   |  ---                             |
|  ...                   |  Recent files:                    |
|                        |  * install.py (edit)              |
|  In Progress (3):      |  * watcher.py (edit)             |
|  * l2-2 compile/       |  * engine.py (edit)              |
|  * l2-3 uninstall/     |                                   |
|                        |  Last commit:                     |
|  Pending (2):          |  930c4b9 Wave 0 -- Protocol...   |
|  o l3-1 unicode        |                                   |
|  o l3-2 arrows         |                                   |
+------------------------+----------------------------------+
```

**UI behaviors by event type:**

| Event | UI Response |
|-------|------------|
| `intent_change` | Update phase header |
| `agent_dispatch` | Add agent card with spinning timer |
| `agent_complete` | Stop timer, flash green/red |
| `todo_create` | Add cards to Pending column |
| `todo_update` | Animate card between columns |
| `test_run_start` | Show spinner on test ring |
| `test_run_complete` | Flash green/red with counts |
| `file_change` | Flash path in activity feed |
| `checkpoint_commit` | Mark wave complete, advance indicator |
| `skill_activated` | Show badge on current phase |

### SSE Client (dashboard core)

```javascript
const events = new EventSource('/events');

events.onmessage = (e) => {
  const ev = JSON.parse(e.data);
  switch (ev.type) {
    case 'intent_change':   updatePhase(ev.detail.intent); break;
    case 'agent_dispatch':  addAgentCard(ev.detail); break;
    case 'agent_complete':  completeAgent(ev.detail); break;
    case 'todo_create':     refreshTodoBoard(); break;
    case 'todo_update':     moveTodos(ev.detail.status); break;
    case 'test_run_start':  startTestSpinner(); break;
    case 'test_run_complete': completeTestRing(ev.detail); break;
    case 'file_change':     flashFile(ev.detail); break;
    case 'checkpoint_commit': advanceWave(ev.detail); break;
    case 'skill_activated': showSkillBadge(ev.detail.skill); break;
  }
};
```

### Running the POC

```bash
# 1. Ensure hooks and server scripts are in place
ls .github/hooks/hooks.json dashboard-event.sh dashboard-start.sh dashboard-server.mjs

# 2. Make scripts executable
chmod +x .github/hooks/*.sh

# 3. Start a Copilot CLI session (dashboard launches via sessionStart hook)
copilot  # opens http://localhost:3391 automatically

# 4. Open the dashboard
open http://localhost:3391

# 5. Work normally — every tool call streams to the dashboard live
```

### What This Enables

**For practitioners:** Watch your agent fleet work live. See the dependency graph resolve. Catch stuck agents (timer keeps counting) before wasting minutes.

**For team demos:** Share the dashboard URL on screen. Make the agentic process tangible — not a black box of terminal output.

**For CI/CD observability:** Stream events to Datadog/Grafana. Track agent dispatch counts, test pass rates, wall-clock time per wave. Detect regressions in the process itself.

**For research:** The JSONL log is a complete trace of every AI decision. Analyze retries, tool frequency, wave parallelism. Compare sessions to find convergence patterns.

### Extension: Interactive Control Plane

The `preToolUse` hook can return `{"permissionDecision": "deny"}` — enabling **human-in-the-loop via the dashboard**:

1. Agent dispatches `git push` via `bash`
2. `preToolUse` fires, sends event to dashboard
3. Dashboard shows a modal: "Agent wants to push to remote. Allow?"
4. User clicks Allow/Deny in the browser
5. Hook returns the decision to Copilot CLI

```bash
# Interactive hook with HTTP callback
#!/bin/bash
INPUT=$(cat)
if echo "$INPUT" | jq -r '.toolArgs' | grep -q "git push"; then
  DECISION=$(curl -s "http://localhost:3391/approve?tool=bash" --max-time 30)
  echo "$DECISION"  # {"permissionDecision":"allow"} or "deny"
fi
```

This turns the dashboard from a read-only observer into a **control plane for agentic development** — the human watches the process and intervenes at decision points without leaving the browser.

### Limitations and Future Work

| Limitation | Reason | Future Path |
|-----------|--------|-------------|
| 3s hook timeout | Must stay fast | Async queue with batch flush |
| No prompt injection | `userPromptSubmitted` output is ignored | Future: prompt modification support |
| File-based event log | Simple but not durable | SQLite or Redis for production |
| Single-session view | One dashboard per session | Multi-session picker with history |
| No auth on dashboard | localhost-only for dev | Basic auth for shared/remote use |

---

*This handbook is a living document. The patterns evolve as Copilot CLI evolves. The principles don't.*

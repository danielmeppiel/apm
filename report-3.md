# Report III: awesome-ai-native Guide Evolution for Skills Era

## Executive Summary

The awesome-ai-native guide needs substantial updates to integrate Agent Skills as the new apex primitive. Skills fundamentally change the mental model: primitives are now components WITHIN Skills, and Skills provide progressive context disclosure that the current guide's context engineering section doesn't address.

---

## Current Guide Structure Analysis

### 1. Core Concepts (`docs/concepts/index.md`)

**Current State:**
- Layer 1: Markdown Prompt Engineering ✅ (remains valid)
- Layer 2: Agent Primitives (instructions, prompts, agents, memory, context, specs) 
- Layer 3: Context Engineering (session splitting, modular rules, hierarchical discovery)

**Required Updates:**

1. **Add Skills as Distribution Layer**
   - Skills are packages; primitives are internal components
   - SKILL.md enables progressive context disclosure (agents auto-summon)
   - Add diagram showing Skills containing primitives

2. **Update Agent Primitives Section**
   - Add `SKILL.md` as the apex distribution primitive
   - Note: `.instructions.md`, `.prompt.md`, `.agent.md` etc. live INSIDE Skills
   - Clarify: Project-local primitives still exist for non-distributed use

3. **Update Context Engineering Section**
   - Add "Progressive Context Disclosure" as key technique
   - Skills auto-discovery reduces manual context loading
   - Context still matters for skills composition and optimization

**Priority: HIGH** - This is the conceptual foundation

---

### 2. Getting Started (`docs/getting-started/index.md`)

**Current State:**
- Instructions Architecture (`.instructions.md` with `applyTo`)
- Chat Modes Configuration (`.chatmode.md`)
- Agentic Workflows (`.prompt.md`)
- Specification Templates (`.spec.md`)

**Required Updates:**

1. **Add Skills Installation Section (early)**
   ```bash
   apm install danielmeppiel/form-builder
   ```
   - Show how Skills give you capabilities instantly
   - Link to concepts page for Skills explanation

2. **Reframe Primitives as "Internal or Local"**
   - Instructions, prompts, agents → can be local OR inside Skills
   - When you create them locally, they're project-specific
   - When you package them in a Skill, they become shareable

3. **Add "Creating Your First Skill" Section**
   - `apm init skill my-standards`
   - Show SKILL.md structure
   - Explain progressive disclosure metadata

4. **Update Quick Start Checklist**
   - [ ] Install useful Skills for your stack
   - [ ] Create project-local primitives
   - [ ] Package reusable patterns as Skills

**Priority: HIGH** - This is the entry point

---

### 3. Tooling (`docs/tooling/index.md`)

**Current State:**
- Agent CLI Runtimes
- Runtime Management (APM)
- Context Compilation (`.instructions.md` → `AGENTS.md`)
- Distribution and Packaging (APM packages)
- Production Deployment

**Required Updates:**

1. **Shift Primary Focus to Skills**
   - APM is now primarily "the package manager for Skills"
   - Runtime management becomes secondary capability
   - Update examples to show Skill installation first

2. **Add "Skills Composition" Section**
   - Transitive dependencies: Skills can depend on Skills
   - Conflict detection when Skills have overlapping instructions
   - `apm install` resolves entire dependency graph

3. **Update Context Compilation**
   - Now handles Skills + local primitives together
   - Skills contribute to AGENTS.md compilation
   - Show how multiple Skills merge into optimized output

4. **Add "Skill Authoring" Section**
   - `apm init skill` scaffolding
   - SKILL.md specification (title, description, when-to-use)
   - Publishing to GitHub as a Skill package

5. **Simplify Enterprise Features**
   - Remove governance/audit discussion (not APM's job)
   - Focus on: install, compose, compile, share

**Priority: HIGH** - This is the tooling foundation

---

### 4. Agent Delegation (`docs/agent-delegation/index.md`)

**Current State:**
- Local IDE Execution
- Async Agent Delegation (GitHub Coding Agent)
- Hybrid Orchestration
- Progress Monitoring

**Required Updates:**

1. **Add Skills as Context Suppliers**
   - When delegating to agents, Skills provide automatic context
   - Agents summon relevant Skills based on task
   - Link to Skills for understanding auto-discovery

2. **Update Workflow Examples**
   - Show Skills being used in delegated workflows
   - Example: OAuth workflow uses installed `auth-patterns` Skill
   - Skills reduce context specification in delegation prompts

3. **Minor Update Only**
   - Core delegation patterns remain valid
   - Skills enhance delegation, don't replace it

**Priority: MEDIUM** - Skills enhance existing patterns

---

### 5. Team & Enterprise Scale (`docs/team-adoption/index.md`)

**Current State:**
- Spec-Driven Team Workflows
- Agent Onboarding & Enterprise Governance
- Team Roles & Primitive Ownership
- Knowledge Sharing & Team Intelligence

**Required Updates:**

1. **Skills as Governance Mechanism (PATTERN, not tool-specific)**
   - Enterprise standards become Skills packages
   - Instant, deterministic policy enforcement through context injection
   - Can be distributed via APM, Git, or any package mechanism

2. **Update Agent Onboarding Section**
   - Agent onboarding = installing right Skills
   - Skills replace training documentation
   - Progressive disclosure = agents get what they need automatically

3. **Team Knowledge Sharing via Skills**
   - Teams package proven patterns as Skills
   - Cross-team Skills sharing (tool-agnostic pattern)
   - Compound intelligence through Skill composition

4. **KEEP ALL Governance Patterns**
   - Validation gates at phase boundaries
   - Risk-based automation levels
   - Audit trails through explicit specifications
   - These are AI Native Development concepts, not tool features

**Priority: MEDIUM** - Skills enhance existing governance patterns

**Note:** Enterprise governance is a core AI Native Development concept. The guide teaches patterns; APM is one implementation option.

---

### 6. Reference (`docs/reference/index.md`)

**Current State:**
- Quick Start Checklist
- Mastery Progression
- Documentation References

**Required Updates:**

1. **Add Skills to Quick Start Checklist**
   - [ ] Install relevant Skills for your stack
   - [ ] Understand SKILL.md structure

2. **Add Skills Reference Section**
   - Link to agentskills.io specification
   - SKILL.md required sections
   - Skills directory (if one exists)

3. **Update Documentation References**
   - Add: Agent Skills specification (agentskills.io)
   - Add: Anthropic Skills blog post
   - Add: APM Skills documentation

**Priority: LOW** - Reference updates follow content

---

## apm.yml vs SKILL.md: The Dual-File Model

Skills packages have TWO manifest files serving different audiences:

| File | Audience | Purpose |
|------|----------|---------|
| **SKILL.md** | Agents (AI) | Discovery & auto-summoning. "What am I and when should you use me?" |
| **apm.yml** | APM (tooling) | Package management. "What do I depend on and how do I install?" |

### Example Skill Package Structure
```
form-builder/
├── SKILL.md                 # For agents: discovery, description, when-to-use
├── apm.yml                  # For APM: dependencies, versioning, scripts
├── instructions/
│   └── forms.instructions.md
├── prompts/
│   └── create-form.prompt.md
└── examples/
    └── contact-form.tsx
```

### SKILL.md (Agent-Facing)
- Title, description, capabilities
- When-to-use triggers for auto-summoning
- Skill dependencies (skill:// protocol)
- Progressive context disclosure metadata

### apm.yml (Tooling-Facing)
- Package name, version, description
- Dependencies with semver constraints
- Scripts for workflow execution
- Build/compile configuration

**The relationship:**
- `apm.yml` declares dependencies → APM resolves and installs them
- `SKILL.md` describes the Skill → Agents discover and auto-summon it
- Both are needed for a complete Skill package

---

## Key Conceptual Shifts

### Before (Pre-Skills)
```
Primitives (.instructions.md, .prompt.md, etc.)
    ↓
Context Engineering (manual loading, session management)
    ↓
AGENTS.md (compiled output)
```

### After (Skills Era)
```
Skills (SKILL.md + internal primitives)
    ↓
Skill Composition (transitive dependencies, conflict resolution)
    ↓
Progressive Context Disclosure (agents auto-summon Skills)
    ↓
Primitives (instructions, prompts, etc. inside Skills OR local)
    ↓
AGENTS.md (compiled from Skills + local primitives)
```

---

## New Diagram Needed (Concepts Page)

```
┌─────────────────────────────────────────────────────────────────┐
│                    SKILLS ERA ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   SKILL.md                    = Discovery + Auto-Summoning       │
│   (progressive disclosure)      Agents load Skills as needed     │
│                                                                  │
│   PRIMITIVES                  = Implementation Components        │
│   (inside Skills)               .instructions.md, .prompt.md,    │
│                                 .agent.md, .context.md           │
│                                                                  │
│   LOCAL PRIMITIVES            = Project-Specific Guidance        │
│   (not in Skills)               .instructions.md, .memory.md     │
│                                                                  │
│   AGENTS.md                   = Compiled Universal Context       │
│   (output)                      From Skills + Local combined     │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   APM ROLE:                                                      │
│   1. Install Skills (transitive dependency resolution)           │
│   2. Compose Skills + local primitives                          │
│   3. Compile to optimized AGENTS.md / CLAUDE.md                 │
│   4. Multi-platform target support                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Priority Order for Updates

1. **Concepts** (HIGH) - Foundation must be correct first
2. **Getting Started** (HIGH) - Entry point needs Skills-first flow
3. **Tooling** (HIGH) - APM's role needs repositioning
4. **Team Adoption** (MEDIUM) - Skills enhance existing patterns
5. **Agent Delegation** (MEDIUM) - Skills provide context for delegation
6. **Reference** (LOW) - Updates follow content changes

---

## Specific Work Items

### Phase 1: Conceptual Foundation
- [ ] Update Concepts page Layer 2 to include Skills
- [ ] Add Skills hierarchy diagram
- [ ] Update Context Engineering for progressive disclosure
- [ ] Add "Agentic Workflows" → "Skills + Workflows" connection

### Phase 2: Getting Started Refresh
- [ ] Add Skills installation as first step
- [ ] Reframe primitives as "local or internal to Skills"
- [ ] Add "Create Your First Skill" section
- [ ] Update checklist with Skills items

### Phase 3: Tooling Repositioning
- [ ] Shift focus to Skills-first
- [ ] Add Skills composition section
- [ ] Update compilation for Skills + local
- [ ] Add Skill authoring section
- [ ] Simplify/remove enterprise features

### Phase 4: Team/Delegation Enhancement
- [ ] Show Skills as governance mechanism
- [ ] Update examples to include Skills
- [ ] Skills in delegation context

### Phase 5: Reference Polish
- [ ] Add Skills references
- [ ] Update checklist
- [ ] Add Skills specification links

---

## Implementation Complete

All guide pages have been updated for the Skills era:

| Page | Status | Key Updates |
|------|--------|-------------|
| **Concepts** | ✅ DONE | Layer 2 restructured with Skills + Primitives model; Layer 3 updated with progressive context disclosure |
| **Getting Started** | ✅ DONE | Skills installation section added; Create Your First Skill section; Updated checklist |
| **Tooling** | ✅ DONE | Skills-first positioning; Skills Composition section; Key Takeaways updated |
| **Team Adoption** | ✅ DONE | Skills as governance mechanism; Updated APM → Skills + APM pattern; Key Takeaways updated |
| **Reference** | ✅ DONE | Skills added to Quick Start Checklist; Agent Skills documentation links added |

---

## Conclusion

The awesome-ai-native guide has solid foundations, but Agent Skills represent a paradigm shift that requires more than cosmetic updates. The key conceptual change:

> **Skills are the distribution layer that packages your primitives for sharing and enables progressive context disclosure for automatic agent summoning.**

This doesn't invalidate the existing content—it elevates it. Primitives remain the building blocks. Context engineering remains important. But Skills add a new layer that makes everything shareable, discoverable, and automatically summoned.

The guide needs to:
1. Introduce Skills early as the apex primitive
2. Reframe existing primitives as internal/local vs. packaged in Skills
3. Show APM as the Skills package manager (not just "context compiler")
4. Update examples throughout to show Skills-first workflows

This positions awesome-ai-native as authoritative for the Skills era while preserving the valuable frameworks already built.

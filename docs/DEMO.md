# APM 0.7.0 Demo Script: "Skills + Guardrails in 90 Seconds"

---

## Opening Hook (5 seconds)

> "What if you could give any AI coding agent new superpowers — AND keep it compliant — with one command?"

---

## Act 1: The Problem (15 seconds)

**Scene:** Empty project folder, terminal open.

> "You've got a corporate website to build. You want your AI agent to know how to build forms — BUT also follow GDPR rules. Today that means copy-pasting examples, configuring each tool separately, hoping the agent doesn't cut corners on compliance..."

**Visual:** Show scattered files, manual copy-paste, inconsistent outputs.

---

## Act 2: One Command, Native Skills (30 seconds)

**Scene:** Terminal in fresh project.

```bash
# Start fresh
mkdir corporate-website && cd corporate-website
apm init demo

# Install a skill — give your agent form-building powers
apm install danielmeppiel/form-builder
```

**Narration:**
> "APM 0.7.0 brings native Agent Skills support. One command. The skill installs to `.github/skills/` — the standard location that works with Copilot, Claude, Cursor, and more."

**Key Visual:** Show terminal output:
```
✓ danielmeppiel/form-builder
  └─ Skill integrated → .github/skills/
```

**Then show the folder structure:**
```bash
tree .github/skills/
```
```
.github/skills/
└── form-builder/
    ├── SKILL.md
    ├── .apm/instructions/
    └── examples/
```

> "No transformation. No config. Native agentskills.io format with React Hook Form and Zod validation patterns."

---

## Act 3: Layer Guardrails on Top (25 seconds)

**Scene:** Same project.

```bash
# Now add corporate guardrails
apm install danielmeppiel/compliance-rules

# Compile everything
apm compile
```

**Narration:**
> "But skills alone aren't enough. Your agent also needs guardrails — GDPR compliance, data minimization, audit trails. APM compiles these into AGENTS.md, the open standard for agent instructions."

**Key Visual:** Show the compile output:
```
Generated 1 AGENTS.md file
├─ Context efficiency: 85%
└─ Sources: form-builder, compliance-rules
```

**Then show AGENTS.md:**
```bash
head -30 AGENTS.md
```

> "Skills give agents capabilities. Guardrails give agents boundaries. APM gives you both."

---

## Act 4: The Magic Moment (15 seconds)

**Scene:** VSCode/Copilot Chat open.

**Prompt:** "Build a contact form"

**Narration:**
> "Watch this. I ask for a contact form. The agent uses form-builder patterns — React Hook Form, Zod validation, accessible markup. But it ALSO adds the GDPR consent checkbox. Because compliance-rules require it."

**Visual:** Show generated code with both form patterns AND consent checkbox.

> "The skill gave it the power. The guardrail kept it compliant. One package manager. Native formats."

---

## Closing: The Standards Stack (10 seconds)

**Scene:** Terminal with the full apm.yml visible.

```yaml
# apm.yml
dependencies:
  apm:
    - danielmeppiel/form-builder      # Skill: what agents CAN DO
    - danielmeppiel/compliance-rules  # Guardrail: what agents MUST FOLLOW
```

> "APM 0.7.0 — built on open standards: AGENTS.md for instructions, agentskills.io for skills. Install once, use everywhere."

---

## Commands to Reproduce

```bash
# 1. Fresh start
cd /tmp && rm -rf demo-project
mkdir demo-project && cd demo-project

# 2. Initialize APM project
apm init demo

# 3. Install a skill (capability)
apm install danielmeppiel/form-builder

# 4. Show skill structure
tree .github/skills/
cat .github/skills/form-builder/SKILL.md | head -40

# 5. Install guardrails
apm install danielmeppiel/compliance-rules

# 6. Compile to AGENTS.md
apm compile

# 7. Show the tension in action
cat AGENTS.md | grep -A5 "GDPR\|consent\|form"
```

---

## Key Narrative Beats

| Moment | Message | Emotion |
|--------|---------|---------|
| Hook | "Superpowers AND compliance" | Curiosity |
| Problem | "Forms that cut corners on GDPR" | Pain recognition |
| Skill Install | "React Hook Form + Zod, native format" | Relief |
| Guardrails | "Capabilities + Boundaries" | Aha moment |
| Magic | "Consent checkbox appeared automatically" | Delight |
| Close | "Skills + Guardrails = Real AI governance" | Trust |

---

## The "Tension" Visual

```
User: "Build a contact form"

┌─ form-builder (Skill) ───────────────────────┐
│ ✓ React Hook Form for controlled inputs      │
│ ✓ Zod schema for validation                  │
│ ✓ Loading states, error handling             │
└──────────────────────────────────────────────┘
            ↓ constrained by ↓
┌─ compliance-rules (Guardrail) ───────────────┐
│ ✓ GDPR consent checkbox required             │
│ ✓ Data minimization (only needed fields)     │
│ ✓ Audit logging for submissions              │
└──────────────────────────────────────────────┘

Result: Production-ready, GDPR-compliant form
```

---

## Alternate Packages to Demo

| Audience | Skill | Guardrail |
|----------|-------|-----------|
| Web developers | `danielmeppiel/form-builder` | `danielmeppiel/compliance-rules` |
| Enterprise buyers | `danielmeppiel/form-builder` | `danielmeppiel/design-guidelines` |
| Full stack | Both compliance + design | Multiple guardrails stacking |

---

## Live Demo Repository

Point viewers to: **[github.com/danielmeppiel/corporate-website](https://github.com/danielmeppiel/corporate-website)**

> "This is a real project using APM with form-builder skill and compliance guardrails. Clone it, run `apm install && apm compile`, see it work."

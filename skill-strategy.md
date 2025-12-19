# APM Skills Strategy

> Strategic architecture for native Agent Skills support in APM

## Executive Summary

APM will become a first-class citizen in the emerging Agent Skills ecosystem by embracing the [agentskills.io](https://agentskills.io/) standard natively. This document outlines the architectural changes required to properly support Skills as a distinct primitive, separate from instructions, agents, and prompts.

---

## Current State Problems

### 1. Wrong Target Directory for VSCode Skills

The Agent Skills standard specifies:
- `.github/skills/` — **Recommended for all new skills** (VSCode, Copilot CLI, coding agent)
- `.claude/skills/` — Legacy location, backward compatibility only

**APM currently installs skills to `.claude/skills/` and then transforms them to `.github/agents/` files.** This is architecturally backwards.

### 2. Skill-as-Agent Transformation is Wrong

APM converts SKILL.md → `.agent.md` files for VSCode. But Skills ≠ Agents:

| Skills | Agents |
|--------|--------|
| Folders with SKILL.md + resources | Single `.agent.md` files |
| Loaded on-demand by task relevance | Explicitly invoked modes |
| Can contain scripts, examples, references | Instructions only |
| Progressive disclosure (3 levels) | Full content loaded |
| Portable across agents | VSCode-specific |

### 3. Conflating Primitives with Skills

APM auto-generates SKILL.md for packages that have `.apm/` primitives. This conflates:
- **Primitives** (instructions, prompts, agents) = building blocks for context engineering
- **Skills** = portable capability packages for AI agents

A package with only `.instructions.md` files should **not necessarily become a skill**.

### 4. Name Validation Missing

The Agent Skills spec has strict naming requirements:
- Lowercase only, hyphens allowed, no consecutive hyphens
- **Must match parent directory name**

APM generates skills without validating these constraints.

### 5. Missing Progressive Disclosure

Skills are designed for efficient context use with 3-level loading:
1. Metadata (~100 tokens) - always loaded
2. Instructions (<5000 tokens) - loaded on activation
3. Resources - loaded on demand

APM's generated SKILL.md bundles everything into a single file.

---

## Strategic Decisions

### Decision 1: Install Skills to `.github/skills/` by Default

```
BEFORE (current):
  apm install → .claude/skills/{name}/SKILL.md
              → Transform → .github/agents/{name}.agent.md

AFTER (proposed):
  apm install → .github/skills/{name}/SKILL.md  (primary)
              → .claude/skills/{name}/SKILL.md   (if .claude/ exists, for compat)
```

**Rationale**: `.github/skills/` is the standard location. Skills work natively with Copilot CLI, VSCode, and coding agent without transformation.

### Decision 2: Don't Auto-Generate SKILL.md for Every Package

**Current philosophy** (WRONG): "Every APM package should become a skill"

**New philosophy**: "Skills are explicit, not implicit"

| Package Content | Should Become Skill? |
|-----------------|---------------------|
| Only `.instructions.md` files | **NO** — compile to AGENTS.md |
| Only `.prompt.md` files | **NO** — integrate as commands |
| Has `SKILL.md` at root | **YES** — native skill |
| Package declares `type: skill` in apm.yml | **YES** — explicit skill |
| Has scripts + instructions for complex workflow | **CANDIDATE** — author should add SKILL.md |

### Decision 3: Introduce Explicit `type` Field in apm.yml

```yaml
# Package that should NOT be a skill
name: python-standards
type: instructions  # Only compiles to AGENTS.md, no skill created

# Package that SHOULD be a skill  
name: mcp-builder
type: skill  # Installs as native skill

# Hybrid package (default for backward compatibility)
name: compliance-rules
type: hybrid  # Both AGENTS.md instructions AND skill installation
```

**Supported types:**
- `instructions` — Compile to AGENTS.md only
- `skill` — Install as native skill only
- `hybrid` — Both (default for backward compatibility)
- `prompts` — Commands/prompts only

### Decision 4: Keep Agents and Skills Separate

Remove the skill → agent transformation entirely:

| Asset Type | Target Location | Integration |
|------------|-----------------|-------------|
| **Skills** | `.github/skills/{name}/SKILL.md` | Native copy |
| **Agents** | `.github/agents/{name}.agent.md` | Direct integration |
| **Instructions** | Compiled into `AGENTS.md` | Compilation |
| **Prompts** | `.github/prompts/`, `.claude/commands/` | Direct integration |

### Decision 5: Proper Skill Directory Structure

When a package IS a skill, APM generates the correct structure:

```
.github/skills/{skill-name}/
├── SKILL.md              # Core instructions (required)
├── scripts/              # Executable scripts (optional)
├── references/           # Additional documentation (optional)
└── assets/               # Templates, examples (optional)
```

**Mapping from APM primitives to Skills structure:**

| APM Source | Skills Destination |
|------------|-------------------|
| `.apm/instructions/` | Inline in SKILL.md body OR `references/` |
| `.apm/prompts/` | `references/` OR `scripts/` (if executable) |
| `.apm/agents/` | NOT included (agents ≠ skills) |
| `.apm/context/` | `references/` |
| Package scripts | `scripts/` |

### Decision 6: Do NOT Mandate SKILL.md in Packages

**Reasoning:**

1. **Not every package is a skill**: A package with just `.instructions.md` files is for coding standards, not AI capabilities.

2. **Skills have specific semantics**: Per the spec, skills are "folders of instructions, scripts, and resources that agents can load to perform specialized tasks."

3. **Let package authors decide**: If a package author wants their package to be a skill, they should add a `SKILL.md` or declare `type: skill`.

4. **APM's value is different**: APM's core value is **aggregating and compiling** primitives. Skills are a **distribution mechanism**.

### Decision 7: Validate Skill Names

Implement validation per the Agent Skills spec:

```python
def validate_skill_name(name: str) -> bool:
    """
    Validate skill name per agentskills.io spec:
    - 1-64 characters
    - Lowercase alphanumeric + hyphens only
    - No consecutive hyphens
    - Cannot start/end with hyphen
    - Must match parent directory name
    """
    import re
    pattern = r'^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$'
    if not re.match(pattern, name):
        return False
    if '--' in name:
        return False
    return True
```

---

## What Makes an APM Package a Skill?

**A package IS a skill if:**

1. ✅ It has a `SKILL.md` file at root (native skill)
2. ✅ It declares `type: skill` or `type: hybrid` in apm.yml
3. ✅ It contains workflows/capabilities, not just coding standards

**A package is NOT a skill if:**

1. ❌ It only contains `.instructions.md` files (coding standards)
2. ❌ It declares `type: instructions` in apm.yml
3. ❌ It's meant to always apply, not loaded on-demand

**Legacy packages with `.agent.md` and `.prompt.md`:**
- `.agent.md` → `.github/agents/` (not skills)
- `.prompt.md` → `.github/prompts/` + `.claude/commands/`
- These are separate integration paths, not skills

---

## Implementation Phases

### Phase 1: Native Skills Support
- Add `.github/skills/` as primary skill target directory
- Remove the skill → agent transformation
- Copy skill folders directly (preserving structure)
- Add skill name validation
- Keep `.claude/skills/` as secondary target for compatibility

### Phase 2: Explicit Package Types
- Add `type` field to apm.yml schema
- Implement routing based on type
- Default to `hybrid` for backward compatibility
- Deprecate auto-generation for instruction-only packages

### Phase 3: Proper Skill Structure Generation
- Map APM primitives to proper Skills directories
- Generate SKILL.md that references subdirectories
- Split large instructions into `references/`

### Phase 4: Deprecation Path
- Warn when auto-generating SKILL.md for instruction-only packages
- Encourage explicit `type` declarations
- Document migration path for package authors

---

## Success Criteria

1. Skills installed via APM work natively with Copilot CLI, VSCode, and Claude
2. No transformation step required — skills are copied as-is
3. Clear separation between skills, agents, instructions, and prompts
4. Package authors have control via explicit `type` field
5. Backward compatibility maintained via `hybrid` default

---

## References

- [Agent Skills Specification](https://agentskills.io/specification)
- [VSCode Agent Skills Documentation](https://code.visualstudio.com/docs/copilot/customization/agent-skills)
- [APM Primitives Documentation](docs/primitives.md)
- [APM Skills Documentation](docs/skills.md)

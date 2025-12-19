# APM Skills Strategy - Implementation Plan

> Engineering implementation plan for native Agent Skills support

## Task Breakdown (16 Tasks)

| ID | Task | Complexity | Dependencies | Files |
|----|------|------------|--------------|-------|
| **T1** | Add `type` field to apm.yml schema | S | None | `models.py`, templates |
| **T2** | Implement skill name validation | S | None | `skill_integrator.py` |
| **T3** | Create `.github/skills/` as primary target | S | None | `skill_integrator.py` |
| **T4** | Implement package type routing logic | M | T1, T2, T3 | `install.py`, `skill_integrator.py` |
| **T5** | Remove skill → agent transformation | M | T4 | `agent_integrator.py`, `skill_integrator.py` |
| **T6** | Implement direct skill copy to `.github/skills/` | M | T4 | `skill_integrator.py` |
| **T7** | Add `.claude/skills/` compat copy | S | T6 | `skill_integrator.py` |
| **T8** | Phase 2 integration testing | M | T5, T6, T7 | `tests/integration/` |
| **T9** | Map APM primitives to Skills structure | M | T8 | `skill_integrator.py` |
| **T10** | Generate proper SKILL.md with references | M | T9 | `skill_integrator.py` |
| **T11** | Implement progressive disclosure token limits | S | T9 | `skill_integrator.py` |
| **T12** | Update skill orphan cleanup | S | T6, T7 | `skill_integrator.py` |
| **T13** | Add deprecation warnings | S | Phase 3 | `skill_integrator.py`, `install.py` |
| **T14** | Update documentation | M | Phase 3 | `docs/skills.md`, `docs/concepts.md` |
| **T15** | Add E2E test suite | M | Phase 3 | `tests/e2e/` |
| **T16** | Create migration guide | S | T14 | `docs/migration/` |

---

## Parallelization Diagram

```
PHASE 1: Foundation (Week 1, Days 1-2)
═══════════════════════════════════════════════════════════════════════════════

  Engineer 1         Engineer 2         Engineer 3         Engineer 4
      │                  │                  │                  │
      ▼                  ▼                  ▼                  │
  ┌───────┐          ┌───────┐          ┌───────┐             │
  │  T1   │          │  T2   │          │  T3   │             │
  │ type  │          │ name  │          │.github│             │
  │ field │          │ valid │          │skills │             │
  │  [S]  │          │  [S]  │          │  [S]  │             │
  └───┬───┘          └───┬───┘          └───┬───┘             │
      │                  │                  │                  │
      └──────────────────┴──────────────────┘                  │
                         │                                     │
                         ▼                                     │
                    ┌─────────┐                                │
                    │   T4    │◄───────────────────────────────┘
                    │ Routing │        (joins if free)
                    │   [M]   │
                    └────┬────┘
                         │
═════════════════════════╪═════════════════════════════════════════════════════

PHASE 2: Native Skills Support (Week 1, Days 3-5)
═════════════════════════╪═════════════════════════════════════════════════════
                         │
      ┌──────────────────┼──────────────────┐
      │                  │                  │
      ▼                  ▼                  ▼
  ┌───────┐          ┌───────┐          ┌───────┐
  │  T5   │          │  T6   │          │  T12  │
  │Remove │          │Direct │          │Orphan │
  │Transform          │ Copy  │          │Cleanup│
  │  [M]  │          │  [M]  │          │  [S]  │
  └───┬───┘          └───┬───┘          └───┬───┘
      │                  │                  │
      │                  ▼                  │
      │              ┌───────┐              │
      │              │  T7   │              │
      │              │Claude │              │
      │              │Compat │              │
      │              │  [S]  │              │
      │              └───┬───┘              │
      │                  │                  │
      └──────────────────┼──────────────────┘
                         │
                         ▼
                    ┌─────────┐
                    │   T8    │
                    │ Integr. │
                    │  Tests  │
                    │   [M]   │
                    └────┬────┘
                         │
═════════════════════════╪═════════════════════════════════════════════════════

PHASE 3: Skill Structure Generation (Week 2, Days 1-3)
═════════════════════════╪═════════════════════════════════════════════════════
                         │
      ┌──────────────────┼──────────────────┐
      │                  │                  │
      ▼                  ▼                  ▼
  ┌───────┐          ┌───────┐          ┌───────┐
  │  T9   │          │  T10  │          │  T11  │
  │Primtv │          │SKILL  │          │Progrs │
  │Mapping│          │Genrtr │          │Disclos│
  │  [M]  │          │  [M]  │          │  [S]  │
  └───┬───┘          └───┬───┘          └───┬───┘
      │                  │                  │
      └──────────────────┴──────────────────┘
                         │
═════════════════════════╪═════════════════════════════════════════════════════

PHASE 4: Deprecation & Polish (Week 2, Days 4-5)
═════════════════════════╪═════════════════════════════════════════════════════
                         │
      ┌──────────────────┼──────────────────┐
      │                  │                  │
      ▼                  ▼                  ▼
  ┌───────┐          ┌───────┐          ┌───────┐
  │  T13  │          │  T14  │          │  T15  │
  │Deprec │          │ Docs  │          │  E2E  │
  │Warns  │          │Update │          │ Tests │
  │  [S]  │          │  [M]  │          │  [M]  │
  └───────┘          └───┬───┘          └───────┘
                         │
                         ▼
                    ┌─────────┐
                    │   T16   │
                    │Migration│
                    │  Guide  │
                    │   [S]   │
                    └─────────┘
```

---

## Critical Path

```
T1 ─┐
T2 ─┼─► T4 ─► T6 ─► T7 ─► T8 ─► T9 ─► T10 ─► T14 ─► T16
T3 ─┘         │           │
              └─► T5      └─► T12
```

---

## Phase 1: Foundation

### T1: Add `type` Field to apm.yml Schema

| Attribute | Value |
|-----------|-------|
| **Complexity** | S |
| **Dependencies** | None |
| **Parallelizable** | Yes (with T2, T3) |

**Files to Modify:**
- `src/apm_cli/models.py` - Add `type` field to `APMPackage` dataclass
- `templates/apm.yml` - Update init template (if exists)
- `docs/concepts.md` - Document the type field

**Implementation:**
```python
# In models.py
class PackageTypeEnum(Enum):
    INSTRUCTIONS = "instructions"  # Compile to AGENTS.md only
    SKILL = "skill"               # Install as native skill only
    HYBRID = "hybrid"             # Both (default)
    PROMPTS = "prompts"           # Commands/prompts only

@dataclass
class APMPackage:
    ...
    type: Optional[str] = None  # Default to None → hybrid behavior
```

**Acceptance Criteria:**
- [ ] `APMPackage` parses `type` field correctly
- [ ] Unknown type values raise `ValidationError` with helpful message
- [ ] Default is `None` which maps to `hybrid` behavior
- [ ] `apm init` template includes commented `type` example
- [ ] Unit tests for all type values and edge cases

---

### T2: Implement Skill Name Validation

| Attribute | Value |
|-----------|-------|
| **Complexity** | S |
| **Dependencies** | None |
| **Parallelizable** | Yes (with T1, T3) |

**Files to Modify:**
- `src/apm_cli/integrators/skill_integrator.py` - Add validation function
- `src/apm_cli/utils/naming.py` - Optional: centralize naming utils

**Implementation:**
```python
import re

def validate_skill_name(name: str) -> tuple[bool, str]:
    """
    Validate skill name per agentskills.io spec:
    - 1-64 characters
    - Lowercase alphanumeric + hyphens only
    - No consecutive hyphens
    - Cannot start/end with hyphen
    
    Returns:
        tuple[bool, str]: (is_valid, error_message or "")
    """
    if len(name) < 1 or len(name) > 64:
        return (False, "Skill name must be 1-64 characters")
    
    pattern = r'^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$'
    if not re.match(pattern, name):
        return (False, "Must be lowercase alphanumeric with hyphens, cannot start/end with hyphen")
    
    if '--' in name:
        return (False, "Cannot contain consecutive hyphens")
    
    return (True, "")

def normalize_skill_name(name: str) -> str:
    """Convert a package name to a valid skill name."""
    # Use existing to_hyphen_case and ensure lowercase
    normalized = to_hyphen_case(name).lower()
    # Remove consecutive hyphens
    while '--' in normalized:
        normalized = normalized.replace('--', '-')
    # Strip leading/trailing hyphens
    normalized = normalized.strip('-')
    # Truncate to 64 chars
    return normalized[:64]
```

**Acceptance Criteria:**
- [ ] Validation rejects names > 64 chars
- [ ] Validation rejects uppercase, underscores, special chars
- [ ] Validation rejects `--` consecutive hyphens
- [ ] Validation rejects leading/trailing hyphens
- [ ] `normalize_skill_name()` produces valid skill names
- [ ] Clear error messages for each failure case
- [ ] Unit tests for all validation rules

---

### T3: Create `.github/skills/` as Primary Target Directory

| Attribute | Value |
|-----------|-------|
| **Complexity** | S |
| **Dependencies** | None |
| **Parallelizable** | Yes (with T1, T2) |

**Files to Modify:**
- `src/apm_cli/integrators/skill_integrator.py` - Change target from `.claude/skills/` to `.github/skills/`

**Implementation:**
```python
# In SkillIntegrator.integrate_package_skill()
# Change:
# skill_dir = project_root / ".claude" / "skills" / skill_name

# To:
skill_dir = project_root / ".github" / "skills" / skill_name
```

**Acceptance Criteria:**
- [ ] Skills install to `.github/skills/{name}/SKILL.md`
- [ ] Directory structure created if not exists
- [ ] Existing `.github/` directory handling works
- [ ] Unit tests updated for new path
- [ ] Integration test confirms directory placement

---

### T4: Implement Package Type Routing Logic

| Attribute | Value |
|-----------|-------|
| **Complexity** | M |
| **Dependencies** | T1, T2, T3 |
| **Parallelizable** | No (gating task) |

**Files to Modify:**
- `src/apm_cli/commands/install.py` - Route based on package type
- `src/apm_cli/integrators/skill_integrator.py` - Update `integrate_package_skill` to respect type

**Implementation:**
```python
def should_generate_skill(package_info: PackageInfo) -> bool:
    """Determine if package should generate a skill based on type field."""
    pkg_type = package_info.package.type
    
    # Explicit type takes precedence
    if pkg_type == "instructions":
        return False  # Only compile to AGENTS.md
    if pkg_type == "skill":
        return True   # Always generate skill
    if pkg_type == "prompts":
        return False  # Only integrate prompts
    
    # For hybrid/None: check for native SKILL.md
    has_skill_md = (package_info.install_path / "SKILL.md").exists()
    return has_skill_md

def should_compile_instructions(package_info: PackageInfo) -> bool:
    """Determine if package should compile to AGENTS.md."""
    pkg_type = package_info.package.type
    
    if pkg_type == "skill":
        return False  # Skills don't compile to AGENTS.md
    if pkg_type == "prompts":
        return False  # Prompts don't compile to AGENTS.md
    
    # instructions, hybrid, None → compile
    return True
```

**Acceptance Criteria:**
- [ ] `instructions` packages → `AGENTS.md` only, no skill
- [ ] `skill` packages → `.github/skills/` only, no `AGENTS.md`
- [ ] `hybrid` packages → both
- [ ] `prompts` packages → prompts integration only
- [ ] No `type` field → behaves as `hybrid` (backward compat)
- [ ] Routing tested for each package type

---

## Phase 2: Native Skills Support

### T5: Remove Skill → Agent Transformation

| Attribute | Value |
|-----------|-------|
| **Complexity** | M |
| **Dependencies** | T4 |
| **Parallelizable** | Yes (with T6, T12) |

**Files to Modify:**
- `src/apm_cli/integrators/agent_integrator.py` - Remove `integrate_skill` method
- `src/apm_cli/integrators/skill_integrator.py` - Remove calls to agent transformation
- `src/apm_cli/integrators/__init__.py` - Update exports

**Implementation:**
- Remove `integrate_skill()` method from `AgentIntegrator` entirely
- Remove any code that transforms SKILL.md → `.agent.md`
- Remove calls to skill→agent transformation in `install.py`
- Clean up any dead code paths

**Acceptance Criteria:**
- [ ] SKILL.md files are NOT converted to `.agent.md` files
- [ ] `.github/agents/` directory only contains actual `.agent.md` source files
- [ ] No regressions in agent file integration
- [ ] Integration tests pass without skill→agent transformation

---

### T6: Implement Direct Skill Copy to `.github/skills/`

| Attribute | Value |
|-----------|-------|
| **Complexity** | M |
| **Dependencies** | T4 |
| **Parallelizable** | Yes (with T5, T12) |

**Files to Modify:**
- `src/apm_cli/integrators/skill_integrator.py` - Rewrite `_integrate_native_claude_skill` to copy to `.github/skills/`

**Implementation:**
```python
def _integrate_native_skill(
    self, package_info: PackageInfo, project_root: Path, source_skill_md: Path
) -> SkillIntegrationResult:
    """Copy a native Skill (with existing SKILL.md) to .github/skills/."""
    package_path = package_info.install_path
    skill_name = package_path.name
    
    # Validate and normalize skill name
    is_valid, error = validate_skill_name(skill_name)
    if not is_valid:
        skill_name = normalize_skill_name(skill_name)
    
    # Primary target: .github/skills/
    skill_dir = project_root / ".github" / "skills" / skill_name
    
    # Copy entire skill folder structure
    if skill_dir.exists():
        shutil.rmtree(skill_dir)
    shutil.copytree(package_path, skill_dir)
    
    # Add APM tracking metadata to SKILL.md
    self._add_apm_metadata_to_skill(skill_dir / "SKILL.md", package_info)
    
    return SkillIntegrationResult(
        skill_name=skill_name,
        skill_path=skill_dir,
        files_copied=count_files(skill_dir),
    )
```

**Acceptance Criteria:**
- [ ] Native SKILL.md packages copy entire folder to `.github/skills/`
- [ ] Folder structure preserved (scripts/, references/, assets/, etc.)
- [ ] APM metadata added for orphan detection
- [ ] Skill name validated/normalized
- [ ] Existing skills updated correctly (removed and re-copied)

---

### T7: Add `.claude/skills/` Compatibility Copy

| Attribute | Value |
|-----------|-------|
| **Complexity** | S |
| **Dependencies** | T6 |
| **Parallelizable** | No |

**Files to Modify:**
- `src/apm_cli/integrators/skill_integrator.py` - Add secondary copy to `.claude/skills/` if folder exists

**Implementation:**
```python
def _integrate_native_skill(...) -> SkillIntegrationResult:
    # ... existing code for .github/skills/ ...
    
    # Secondary target: .claude/skills/ (for backward compatibility)
    claude_dir = project_root / ".claude"
    if claude_dir.exists():
        claude_skill_dir = claude_dir / "skills" / skill_name
        if claude_skill_dir.exists():
            shutil.rmtree(claude_skill_dir)
        shutil.copytree(package_path, claude_skill_dir)
        self._add_apm_metadata_to_skill(claude_skill_dir / "SKILL.md", package_info)
```

**Acceptance Criteria:**
- [ ] Skills copied to `.claude/skills/` IF `.claude/` folder exists
- [ ] Skills NOT copied to `.claude/skills/` if `.claude/` folder doesn't exist
- [ ] Both locations have identical content
- [ ] APM metadata added to both copies

---

### T8: Phase 2 Integration Testing

| Attribute | Value |
|-----------|-------|
| **Complexity** | M |
| **Dependencies** | T5, T6, T7 |
| **Parallelizable** | No |

**Files to Create/Modify:**
- `tests/integration/test_skill_integration.py` - E2E tests

**Test Cases:**
1. `apm install` with `type: skill` package → `.github/skills/` only
2. `apm install` with `type: instructions` → `AGENTS.md` only
3. `apm install` with native SKILL.md → direct copy preserving structure
4. Both `.github/skills/` and `.claude/skills/` targets when both exist
5. Skill name validation warnings displayed
6. No skill→agent transformation occurs

**Acceptance Criteria:**
- [ ] All test cases pass
- [ ] Tests verify file contents, not just existence
- [ ] Tests cover edge cases (invalid names, missing directories)

---

### T12: Update Skill Orphan Cleanup

| Attribute | Value |
|-----------|-------|
| **Complexity** | S |
| **Dependencies** | T6, T7 |
| **Parallelizable** | Yes (with T5) |

**Files to Modify:**
- `src/apm_cli/integrators/skill_integrator.py` - Update `sync_integration` for both directories

**Implementation:**
```python
def sync_integration(self, apm_package: APMPackage, project_root: Path) -> Dict[str, int]:
    """Sync both .github/skills/ and .claude/skills/ with installed packages."""
    stats = {'files_removed': 0, 'errors': 0}
    installed = {dep.get_canonical_string() for dep in apm_package.get_apm_dependencies()}
    
    # Clean .github/skills/
    github_skills = project_root / ".github" / "skills"
    if github_skills.exists():
        stats = self._clean_orphaned_skills(github_skills, installed, stats)
    
    # Clean .claude/skills/ (if exists)
    claude_skills = project_root / ".claude" / "skills"
    if claude_skills.exists():
        stats = self._clean_orphaned_skills(claude_skills, installed, stats)
    
    return stats
```

**Acceptance Criteria:**
- [ ] Orphaned skills removed from `.github/skills/`
- [ ] Orphaned skills removed from `.claude/skills/`
- [ ] APM metadata used for orphan detection
- [ ] User files (without APM metadata) are NOT removed
- [ ] Correct stats returned

---

## Phase 3: Skill Structure Generation

### T9: Map APM Primitives to Skills Structure

| Attribute | Value |
|-----------|-------|
| **Complexity** | M |
| **Dependencies** | T8 |
| **Parallelizable** | Yes (with T10, T11) |

**Files to Modify:**
- `src/apm_cli/integrators/skill_integrator.py` - Update `_copy_primitives_to_skill`

**Mapping per Strategy:**
| APM Source | Skills Destination |
|------------|-------------------|
| `.apm/instructions/` | Inline in SKILL.md body OR `references/` |
| `.apm/prompts/` | `references/` |
| `.apm/agents/` | **NOT included** (agents ≠ skills) |
| `.apm/context/` | `references/` |
| Package scripts | `scripts/` |

**Acceptance Criteria:**
- [ ] Instructions go to `references/` (or inline if small)
- [ ] Prompts go to `references/`
- [ ] Contexts go to `references/`
- [ ] Agents are NOT copied to skill directories
- [ ] Scripts copied to `scripts/` subdirectory

---

### T10: Generate Proper SKILL.md with References

| Attribute | Value |
|-----------|-------|
| **Complexity** | M |
| **Dependencies** | T9 |
| **Parallelizable** | Yes (with T11) |

**Files to Modify:**
- `src/apm_cli/integrators/skill_integrator.py` - Update `_generate_skill_file`

**Acceptance Criteria:**
- [ ] SKILL.md references subdirectories with relative links
- [ ] Concise body content (~100-150 words)
- [ ] Valid frontmatter with name, description, metadata
- [ ] Links work for Claude/Copilot skill discovery

---

### T11: Implement Progressive Disclosure Token Limits

| Attribute | Value |
|-----------|-------|
| **Complexity** | S |
| **Dependencies** | T9 |
| **Parallelizable** | Yes (with T10) |

**Files to Modify:**
- `src/apm_cli/integrators/skill_integrator.py` - Add token counting

**Acceptance Criteria:**
- [ ] Small instruction files (<5000 tokens) inlined in SKILL.md
- [ ] Large files split to `references/` subdirectory
- [ ] Total SKILL.md body stays under 5000 tokens

---

## Phase 4: Deprecation & Polish

### T13: Add Deprecation Warnings

| Attribute | Value |
|-----------|-------|
| **Complexity** | S |
| **Dependencies** | Phase 3 complete |
| **Parallelizable** | Yes (with T14, T15) |

**Acceptance Criteria:**
- [ ] Warning shown for instruction-only packages generating skills
- [ ] Warning suggests explicit `type` field
- [ ] Warning only shown once per package

---

### T14: Update Documentation

| Attribute | Value |
|-----------|-------|
| **Complexity** | M |
| **Dependencies** | Phase 3 complete |
| **Parallelizable** | Yes (with T13, T15) |

**Files to Modify:**
- `docs/skills.md` - Update for new behavior
- `docs/concepts.md` - Clarify Skills vs Primitives
- `docs/cli-reference.md` - Add package types section

**Note:** Per `doc-sync.instructions.md`, README.md changes require user approval.

---

### T15: Add E2E Test Suite

| Attribute | Value |
|-----------|-------|
| **Complexity** | M |
| **Dependencies** | Phase 3 complete |
| **Parallelizable** | Yes (with T13, T14) |

---

### T16: Create Migration Guide

| Attribute | Value |
|-----------|-------|
| **Complexity** | S |
| **Dependencies** | T14 |
| **Parallelizable** | No |

---

## Risk Areas & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing `.claude/skills/` workflows | High | T7 ensures backward compat copy when `.claude/` exists |
| Skill name validation too strict | Medium | `normalize_skill_name()` auto-converts instead of failing |
| Package type confusion | Medium | Clear documentation in T14, warnings in T13 |
| Orphan cleanup removes user files | High | Only clean files with APM metadata in frontmatter |
| Performance regression from double copy | Low | Only copy to `.claude/skills/` if directory exists |

---

## Suggested Team Assignment

| Engineer | Tasks | Focus Area |
|----------|-------|------------|
| **Engineer 1** | T1, T4, T9 | Package routing & models |
| **Engineer 2** | T2, T3, T6, T12 | Skill integration & validation |
| **Engineer 3** | T5, T7, T10, T11 | Transformation removal & generation |
| **Engineer 4** | T8, T13, T14, T15, T16 | Testing & documentation |

---

## Definition of Done

- [ ] All acceptance criteria met for each task
- [ ] Unit tests added for new functionality
- [ ] Integration tests pass
- [ ] Documentation updated (per doc-sync.instructions.md)
- [ ] No regressions in existing functionality
- [ ] Code reviewed and merged

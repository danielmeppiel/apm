# APM Phase 2: Transitive Dependencies Implementation Plan

## Current State Assessment

### What APM Has Today (Solid Foundation)

**Dependency Infrastructure (70% complete for transitivity)**
- `APMDependencyResolver` with `build_dependency_tree()` - BFS traversal, depth tracking ✓
- `DependencyGraph`, `DependencyTree`, `FlatDependencyMap` data structures ✓
- Circular dependency detection ✓
- Conflict detection with "first wins" strategy ✓
- `_try_load_dependency_package()` - **placeholder that returns `None`** ← THE GAP
- GitHub/ADO package downloading via `GitHubPackageDownloader` ✓

**Package Model**
- `APMPackage.from_apm_yml()` parses dependencies as `DependencyReference` objects ✓
- `get_apm_dependencies()` returns typed `List[DependencyReference]` ✓
- Semver constraints parsed but **not enforced** during resolution

**Compilation**
- `apm compile` merges local + `apm_modules/` instructions → AGENTS.md ✓
- Distributed compilation with source attribution ✓
- Multi-target (VSCode + Claude) ✓

---

## The Missing Link: Recursive Package Loading

The dependency resolver **has the algorithm** but **lacks the integration**:

```python
# apm_resolver.py line 154-168
def _try_load_dependency_package(self, dep_ref: DependencyReference) -> Optional[APMPackage]:
    """Try to load a dependency package from local paths.
    
    This is a placeholder implementation for Task 3...
    """
    # For now, return None to indicate package not found locally
    return None  # ← THIS IS THE ENTIRE BLOCKER
```

This means today:
1. `apm install danielmeppiel/form-builder` downloads to `apm_modules/`
2. But `form-builder/apm.yml` listing `danielmeppiel/validation-patterns` as a dependency **is never read**
3. Tree building stops at depth=1

---

## Strategic Roadmap: The npm Trajectory

### Phase 2.1: Close the Transitive Loop (Critical Path)

**Goal:** When installing A, if A depends on B, automatically install B

| Task | Description | Complexity | Dependencies |
|------|-------------|------------|--------------|
| **T1: Package Loading Integration** | Implement `_try_load_dependency_package()` to scan `apm_modules/` and load `apm.yml` | Low | None |
| **T2: Install-time Recursive Resolution** | Modify `_install_apm_dependencies()` to respect `DependencyGraph` resolution order | Medium | T1 |
| **T3: Download Transitive Deps** | For uninstalled deps in the tree, trigger `GitHubPackageDownloader` | Medium | T1, T2 |
| **T4: apm.lock Generation** | After resolution, write `apm.lock` with exact versions/commits | Low | T2 |
| **T5: apm.lock Consumption** | On subsequent `apm install`, prefer lock file over re-resolution | Low | T4 |

**Architecture Decision:**
```
apm install owner/skill
    ↓
APMDependencyResolver.resolve_dependencies()
    ↓
For each unresolved dep in tree:
    GitHubPackageDownloader.download_package()
    ↓
    Update tree with loaded package's sub-deps
    ↓
    Recurse until all resolved
    ↓
Write apm.lock
```

### Phase 2.2: Semver Constraint Resolution

| Task | Description | Complexity |
|------|-------------|------------|
| **T6: Semver Parser** | Parse `^1.0.0`, `~1.2.0`, `>=2.0.0 <3.0.0` in dependency strings | Low |
| **T7: Tag-based Version Matching** | Map semver constraints to Git tags (`v1.2.3`) | Medium |
| **T8: Conflict Resolution Upgrade** | When conflicts arise, pick highest compatible version (not just "first wins") | Medium |

### Phase 2.3: Skill Compilation Integration

| Task | Description | Complexity |
|------|-------------|------------|
| **T9: Skill Graph Traversal** | During `apm compile`, walk the full dependency tree | Low |
| **T10: Skill Instruction Merging** | Merge transitive skill instructions into AGENTS.md with dedup | Medium |
| **T11: Skill Conflict Reporting** | When two skills have overlapping `applyTo` patterns, warn or resolve | Medium |

---

## Data Flow: Before vs After

### Current State (Flat)
```
apm.yml declares: [A, B]
install → downloads A, B to apm_modules/
compile → scans apm_modules/{A,B}/.apm/instructions/
Result: A + B instructions in AGENTS.md
```

### Target State (Transitive)
```
apm.yml declares: [A]
A's apm.yml declares: [B, C]
B's apm.yml declares: [D]

install → 
  1. Resolve full tree: A → B → D, A → C
  2. Download A, B, C, D in topological order
  3. Write apm.lock

compile →
  1. Walk tree: A (depth 1), B (depth 2), C (depth 2), D (depth 3)
  2. Merge instructions with depth-based priority
  3. Detect pattern conflicts
  
Result: D + B + C + A instructions (leaves first) in AGENTS.md
```

---

## Task Breakdown for Engineering

### Sprint 1: Foundation (T1-T3)
**Goal:** Transitive install works end-to-end

1. **T1: Implement `_try_load_dependency_package()`**
   - Input: `DependencyReference`
   - Output: `APMPackage` or `None`
   - Logic: Check `apm_modules/{owner}/{repo}/apm.yml`, parse if exists

2. **T2: Wire resolver into install flow**
   - Before: Install iterates `apm_package.get_apm_dependencies()` directly
   - After: Install calls `resolver.resolve_dependencies()`, iterates `flat_deps.get_installation_list()`
   - Handle: Already-installed packages (cache check)

3. **T3: Download missing transitive deps**
   - During tree building, when `_try_load_dependency_package()` returns `None`:
   - Trigger download
   - Re-scan and load the newly installed package
   - Continue tree traversal

**Exit Criteria:** 
```bash
# form-builder depends on validation-patterns
apm install danielmeppiel/form-builder
ls apm_modules/danielmeppiel/
# → form-builder/ validation-patterns/  ← BOTH present
```

### Sprint 2: Determinism (T4-T5)
**Goal:** `apm install` is reproducible

4. **T4: Generate `apm.lock`**
   - Format: YAML with resolved commit SHAs
   - Content: Full dependency tree snapshot

5. **T5: Consume `apm.lock`**
   - When `apm.lock` exists, skip resolution
   - Download exact versions from lock
   - Add `--update` flag to re-resolve

**Exit Criteria:**
```bash
apm install  # generates apm.lock
rm -rf apm_modules/
apm install  # restores identical tree from lock
```

### Sprint 3: Semver (T6-T8)
**Goal:** Version constraints work like npm

6. **T6: Semver Parsing**
   - Parse constraints from dependency strings: `owner/repo@^1.0.0`
   - Store in `DependencyReference.version_constraint`

7. **T7: Git Tag Resolution**
   - Fetch tags via GitHub API
   - Match constraint to highest compatible tag
   - Fall back to latest if no tags match

8. **T8: Smart Conflict Resolution**
   - When A wants `B@^1.0.0` and C wants `B@^1.2.0`:
   - Pick `B@1.2.x` (highest compatible with both)
   - If incompatible, error with clear message

### Sprint 4: Compilation (T9-T11)
**Goal:** `apm compile` leverages full graph

9. **T9: Walk dependency tree during compile**
   - Use resolver's tree, not just `apm_modules/` directory scan
   - Respect depth ordering

10. **T10: Merge with deduplication**
    - Same instruction from multiple paths → include once
    - Track source for attribution

11. **T11: Conflict detection**
    - Two instructions with same `applyTo`: warn
    - Option to specify resolution in `apm.yml`

---

## Non-Functional Requirements

| Concern | Approach |
|---------|----------|
| **Performance** | BFS tree building is O(n); cache API calls |
| **Error Messages** | npm-quality: show full chain on conflict ("A → B → C requires D@1, but E requires D@2") |
| **Offline Mode** | If `apm.lock` exists + all in `apm_modules/`, no network needed |
| **Partial Failure** | Download what you can, report failures, don't corrupt `apm_modules/` |

---

## Success Metrics

1. **Craft Enablement:** Skill authors can publish skills that depend on other skills
2. **Install Confidence:** `apm install` always produces complete, working `apm_modules/`
3. **Reproducibility:** Same `apm.lock` → same bytes in `apm_modules/`
4. **Compile Correctness:** All transitive instructions appear in AGENTS.md with proper attribution

---

## What We Explicitly Defer

Per report-2.md guidance:
- Private registries (PAT auth is enough)
- Governance policies (enterprise layer)
- `apm publish` (GitHub is the registry for now)
- Complex conflict resolution UI (start with "first wins" + warning)

---

## Critical Path Summary

**T1 → T2 → T3 → T4 → T5** is the MVP path to transitive dependencies.

Everything else (semver, smart conflicts, compile integration) layers on top.

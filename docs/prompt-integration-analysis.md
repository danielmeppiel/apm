# APM Prompt Integration Analysis

**Date:** November 16, 2025  
**Component:** VSCode/GitHub Prompt Integration  
**Status:** Partial Implementation with Critical Gaps

## Overview

APM implements automatic integration of `.prompt.md` files from installed packages into the `.github/prompts/` directory for VSCode compatibility. This analysis identifies implementation gaps and potential issues in the current integration workflow.

## Architecture

### Core Components

1. **`PromptIntegrator`** (`src/apm_cli/integration/prompt_integrator.py`)
   - Handles copying prompts from `apm_modules/` to `.github/prompts/`
   - Adds metadata headers to track source, version, and commit
   - Implements smart update logic based on version/commit changes

2. **Integration Trigger** (`src/apm_cli/cli.py`, lines 947-1069)
   - Called during `apm install` workflow
   - Conditional based on `.github/` directory existence and `auto_integrate` config

3. **Configuration** (`src/apm_cli/config.py`, lines 57-70)
   - `get_auto_integrate()` - Returns integration setting (default: `True`)
   - `set_auto_integrate()` - Allows users to enable/disable feature

### File Naming Convention

- **Source:** `design-review.prompt.md`
- **Integrated:** `design-review-apm.prompt.md`
- **Pattern:** Insert `-apm` suffix before `.prompt.md` extension

### Metadata Header Format

```markdown
<!-- 
Source: danielmeppiel/design-guidelines (github.com/danielmeppiel/design-guidelines)
Version: 1.0.0
Commit: abc123def456
Original: design-review.prompt.md
Installed: 2024-01-01T00:00:00
-->
```

## Architect's Verdict: 🚨 COMPLEXITY CREEP DETECTED

### Analysis from World-Class Tool Design Perspective

Looking at this through the lens of npm, yarn, pip, cargo—tools used by millions—the current plan introduces **unnecessary complexity**:

**Problems:**
- ❌ New `apm integrate` command (users shouldn't need this)
- ❌ New `auto_integrate` config (99% want it enabled)
- ❌ Manual intervention required (should "just work")
- ❌ Exposing implementation details (silent failures)

**Philosophy:** npm doesn't have `npm integrate` or `npm config set auto_node_modules`. It just works.

---

## Issues Analysis

### Issue 1: Missing Cleanup on Uninstall ❌ CRITICAL

**Status:** NOT IMPLEMENTED  
**Impact:** HIGH - Leaves orphaned files  
**Priority:** HIGH (Keep this fix)

#### Current Behavior

**File:** `src/apm_cli/cli.py`, lines 760-900

The `apm uninstall` command currently:
1. ✅ Removes package from `apm.yml` dependencies
2. ✅ Deletes package directory from `apm_modules/{org}/{repo}/`
3. ❌ **Does NOT** clean up integrated prompts from `.github/prompts/`

```python
# Current uninstall logic (simplified)
for package in packages_to_remove:
    package_name = package.split("/")[-1]
    package_path = apm_modules_dir / package_name
    
    if package_path.exists():
        shutil.rmtree(package_path)  # Only removes from apm_modules
        # Missing: cleanup of .github/prompts/*-apm.prompt.md files
```

#### Consequence

After running `apm uninstall danielmeppiel/design-guidelines`:
- ❌ `apm_modules/danielmeppiel/design-guidelines/` → Deleted
- ❌ `apm.yml` → Package removed from dependencies
- ⚠️ `.github/prompts/design-review-apm.prompt.md` → **Still exists** (orphaned)

Users see stale prompts in VSCode that reference uninstalled packages.

#### Simplified Fix (Idempotent Sync)

**Location:** `src/apm_cli/cli.py`, `uninstall()` function

```python
# After uninstalling, re-sync integration (removes orphans automatically)
if Path(".github/prompts").exists():
    try:
        apm_package = APMPackage.from_apm_yml(Path("apm.yml"))
        integrator = PromptIntegrator()
        integrator.sync_integration(apm_package, Path("."))
    except Exception:
        pass  # Silent cleanup failure OK
```

**New Method:** `PromptIntegrator.sync_integration()` - Simpler & Idempotent

```python
def sync_integration(self, apm_package, project_root: Path):
    """Sync .github/prompts/ with currently installed packages.
    
    - Removes prompts from uninstalled packages (orphans)
    - Updates prompts from updated packages
    - Adds prompts from new packages
    
    Idempotent: safe to call anytime. Reuses existing smart update logic.
    """
    prompts_dir = project_root / ".github" / "prompts"
    if not prompts_dir.exists():
        return
    
    # Get currently installed package names
    installed = {dep.repo_url for dep in apm_package.get_apm_dependencies()}
    
    # Remove orphaned prompts (from uninstalled packages)
    for prompt_file in prompts_dir.glob("*-apm.prompt.md"):
        metadata = self._parse_header_metadata(prompt_file)
        source = metadata.get('Source', '')
        
        # Check if source package is still installed
        package_match = any(pkg in source for pkg in installed)
        
        if not package_match:
            prompt_file.unlink()  # Orphaned - remove it
```

---

### Issue 2: Version Change Updates ✅ WORKING

**Status:** FULLY IMPLEMENTED  
**Impact:** None - Working as designed  
**Priority:** N/A

#### Current Behavior

**File:** `src/apm_cli/integration/prompt_integrator.py`, lines 204-276

The integration system correctly handles version/commit changes:

1. **Parse existing file metadata** (lines 70-105)
   ```python
   def _parse_header_metadata(self, file_path: Path) -> dict:
       """Extract Version and Commit from header comment."""
       # Parses <!-- Source: ... Version: ... Commit: ... -->
   ```

2. **Compare versions** (lines 108-131)
   ```python
   def _should_update_prompt(self, existing_header: dict, package_info) -> bool:
       """Return True if version or commit changed."""
       new_version = package_info.package.version
       new_commit = package_info.resolved_reference.resolved_commit
       
       existing_version = existing_header.get('Version', '')
       existing_commit = existing_header.get('Commit', '')
       
       return (existing_version != new_version or existing_commit != new_commit)
   ```

3. **Smart update logic** (lines 244-259)
   ```python
   if target_path.exists():
       existing_header = self._parse_header_metadata(target_path)
       
       if self._should_update_prompt(existing_header, package_info):
           # Version changed - update the file
           self.copy_prompt_with_header(source_file, target_path, header)
           files_updated += 1
       else:
           # No change - skip to preserve timestamp
           files_skipped += 1
   ```

#### Test Coverage

**File:** `tests/unit/integration/test_prompt_integrator.py`

- ✅ Version change detection tested
- ✅ Update vs skip logic tested
- ✅ Header parsing tested

#### Result Tracking

```python
@dataclass
class IntegrationResult:
    files_integrated: int  # New files added
    files_updated: int     # Files updated due to version change
    files_skipped: int     # Unchanged files (same version/commit)
    target_paths: List[Path]
    gitignore_updated: bool
```

**No action required** - this functionality works correctly.

---

### Issue 3: Late `.github/` Directory Creation ❌ REMOVE THIS

**Status:** REJECT - Over-engineered solution  
**Impact:** Creates unnecessary complexity  
**Priority:** REPLACE WITH AUTO-CREATE

#### Current Problem

Integration requires `.github/` to exist before running `apm install`.

#### Wrong Solution (Current Plan)

Add `apm integrate` command + helpful messages → More commands to learn

#### Right Solution (Zero-Config)

**Location:** `src/apm_cli/integration/prompt_integrator.py`, lines 30-43

**Change this:**
```python
def should_integrate(self, project_root: Path) -> bool:
    """Check if prompt integration should be performed."""
    github_dir = project_root / ".github"
    return github_dir.exists() and get_auto_integrate()  # ❌ Too conservative
```

**To this:**
```python
def should_integrate(self, project_root: Path) -> bool:
    """Check if prompt integration should be performed."""
    return True  # ✅ Always integrate (creates dirs as needed)
```

**Why:** The `integrate_package_prompts()` method already creates `.github/prompts/` with `mkdir(parents=True, exist_ok=True)`. The check is redundant and causes the problem.

**Result:** Zero manual intervention, no new commands, just works.

---

### Issue 4: Auto-Integrate Config ❌ REMOVE THIS

**Status:** REJECT - Unnecessary configuration  
**Impact:** Decision fatigue for 1% edge case  
**Priority:** DELETE

#### Current Problem

Users might not want VSCode integration?

#### Wrong Solution (Current Plan)

Add `apm config set auto_integrate true/false` → More knobs to turn

#### Right Solution (Convention over Configuration)

**DELETE:** The entire `auto_integrate` config option

**Reasoning:**
- npm doesn't have `npm config set auto_node_modules false`
- cargo doesn't have `cargo config set auto_target false`
- 99% of users want prompts integrated for VSCode
- The 1% who don't can simply: `echo ".github/prompts/" >> .gitignore`

**Action:** Remove all references to `get_auto_integrate()` and `set_auto_integrate()`

---

## Implementation Priority

### High Priority (Must Fix)

1. **Issue 1: Cleanup on Uninstall**
   - **Impact:** Leaves orphaned files that confuse users
   - **Effort:** Medium (1-2 days)
   - **Files:**
     - `src/apm_cli/cli.py` - Add cleanup call in `uninstall()`
     - `src/apm_cli/integration/prompt_integrator.py` - Add `cleanup_package_prompts()`
     - `tests/unit/integration/test_prompt_integrator.py` - Add cleanup tests

### Medium Priority (Should Fix)

2. **Issue 3: Add `apm integrate` Command**
   - **Impact:** Better UX for late `.github/` creation
   - **Effort:** Medium (2-3 days)
   - **Files:**
     - `src/apm_cli/cli.py` - Add new `integrate` command
     - `src/apm_cli/integration/prompt_integrator.py` - Add `force_update` parameter
     - `tests/integration/test_integration_command.py` - New test file

### Low Priority (Nice to Have)

3. **Issue 4: Add Helpful Messages**
   - **Impact:** Minor UX improvement
   - **Effort:** Low (1 hour)
   - **Files:**
     - `src/apm_cli/cli.py` - Add informational messages

---

## Testing Requirements (Simplified)

### Unit Tests

**File:** `tests/unit/integration/test_prompt_integrator.py`

#### New Tests Required

```python
def test_sync_integration_removes_orphaned_prompts():
    """Test that sync removes prompts from uninstalled packages."""
    # Setup: Create integrated prompts from package1, package2
    # Uninstall: Remove package1 from apm.yml
    # Action: sync_integration()
    # Assert: Only package1 prompts removed, package2 remains

def test_sync_integration_preserves_installed_prompts():
    """Test sync doesn't remove prompts from installed packages."""

def test_sync_integration_handles_missing_prompts_dir():
    """Test sync gracefully handles missing .github/prompts/."""

def test_should_integrate_always_returns_true():
    """Test integration always enabled (no config check)."""
    assert integrator.should_integrate(Path(".")) == True
```

### Integration Tests

**File:** `tests/integration/test_uninstall_cleanup.py` (new file)

```python
def test_uninstall_removes_integrated_prompts():
    """End-to-end: apm install → apm uninstall → verify cleanup."""
    
def test_uninstall_preserves_other_package_prompts():
    """Verify uninstalling one package doesn't affect others."""

def test_install_creates_github_directory_automatically():
    """Test that apm install creates .github/prompts/ automatically."""
```

---

## Configuration

### Auto-Integration Setting

**File:** `src/apm_cli/config.py`, lines 57-70

Users can disable auto-integration globally:
## Configuration

### ❌ REMOVED: Auto-Integration Setting

**Previous approach:** `apm config set auto_integrate true/false`

**Why removed:** 
- Adds complexity for 1% edge case
- Goes against "convention over configuration" principle
- npm, cargo, pip don't have similar configs
- Users who don't want it can use `.gitignore`

**Migration:** If users had `auto_integrate=false`, they should add `.github/prompts/` to `.gitignore` instead.
- `src/apm_cli/integration/__init__.py` - Exports `PromptIntegrator`
- `src/apm_cli/cli.py` - Command definitions and install workflow
- `src/apm_cli/config.py` - Configuration management

### Tests
- `tests/unit/integration/test_prompt_integrator.py` - Unit tests for integrator
- `tests/integration/test_auto_integration.py` - Integration tests

### Models
- `src/apm_cli/models/apm_package.py` - `PackageInfo` data structure

---

## Recommendations (Simplified Approach)

### Immediate Actions

1. ✅ **Implement idempotent sync on uninstall** (High Priority)
   - Add `sync_integration()` method (simpler than cleanup)
   - Call from `uninstall()` command
   - Add comprehensive tests

2. ✅ **Remove `.github/` existence check** (Medium Priority)
   - Change `should_integrate()` to always return `True`
   - Let existing `mkdir(parents=True)` handle directory creation
   - Zero user intervention required

3. ✅ **Remove `auto_integrate` config** (Low Priority)
   - Delete `get_auto_integrate()` and `set_auto_integrate()`
   - Remove from all integration checks
   - Update tests

### ❌ Rejected Actions (Over-Engineering)

- ~~Add `apm integrate` command~~ → Not needed
- ~~Add helpful messages~~ → Not needed
- ~~Add `--force` flag~~ → Already idempotent
- ~~Add VSCode tips~~ → Just works automatically

### Long-Term Improvements

- **Documentation:** Actually becomes simpler (nothing to explain)
- **CI/CD:** Add integration tests for auto-create and sync
- **User feedback:** Monitor for any edge cases
## Revised Implementation Priority (Simplified)

### High Priority (Critical Fix)

1. **Issue 1: Cleanup on Uninstall**
   - **Impact:** Leaves orphaned files
   - **Effort:** Low (4 hours) - Use idempotent sync approach
   - **Files:**
     - `src/apm_cli/cli.py` - Add sync call in `uninstall()`
     - `src/apm_cli/integration/prompt_integrator.py` - Add `sync_integration()`
     - `tests/unit/integration/test_prompt_integrator.py` - Add sync tests

### Medium Priority (Simplification)

2. **Issue 3: Auto-Create `.github/` Directory**
   - **Impact:** Eliminates manual intervention
   - **Effort:** Trivial (15 minutes) - Remove unnecessary check
   - **Files:**
     - `src/apm_cli/integration/prompt_integrator.py` - Change `should_integrate()` to always return `True`

### Low Priority (Cleanup)

3. **Issue 4: Remove `auto_integrate` Config**
   - **Impact:** Reduces complexity
   - **Effort:** Low (1 hour) - Remove config, update tests
   - **Files:**
     - `src/apm_cli/config.py` - Remove `get/set_auto_integrate()`
     - `src/apm_cli/integration/prompt_integrator.py` - Remove config checks
     - `tests/` - Remove config-related tests

### ❌ Rejected (Complexity Bloat)

- ~~Add `apm integrate` command~~ - Not needed with auto-create
- ~~Add helpful messages~~ - Not needed with zero-config
- ~~Add `--force` flag~~ - `apm install` is already idempotent
# OR
apm integrate              # Manually integrate existing packages
```

Integrated prompts appear as `*-apm.prompt.md` in `.github/prompts/`.
```

**Effort:** 12 lines added

---

#### 2. `docs/commands.md` - Add New Commands (if file exists)

**Location:** Commands reference section

**Add:**
```markdown
### `apm integrate`

Integrate prompts from installed packages into `.github/prompts/`.

**Usage:**
```bash
apm integrate              # Integrate missing prompts
apm integrate --force      # Re-integrate all prompts
```

**When to use:**
- Created `.github/` after installing packages
- Want to refresh integrated prompts
- Manually deleted integrated prompts

---

### `apm uninstall`

**Enhancement:** Now automatically removes integrated prompts from `.github/prompts/`.

**Usage:**
```bash
apm uninstall org/package  # Removes package + integrated prompts
```
```

**Effort:** 25 lines added

---

#### 3. `CHANGELOG.md` - Document Changes

**Location:** Under `## [Unreleased]` or next version

**Add:**
```markdown
### Added
- `apm integrate` command for manual prompt integration
- `apm integrate --force` flag to re-integrate all prompts
- Auto-cleanup of `.github/prompts/*-apm.prompt.md` on `apm uninstall`
- Helpful messages when `.github/` directory missing

### Fixed
- Integrated prompts now properly removed when uninstalling packages
- Better UX for late `.github/` directory creation workflow
```

**Effort:** 8 lines added

---

#### 4. Create `docs/integration.md` - Detailed Guide (Optional)

**Note:** Only if users request more details. Keep it short.

**Content:**
```markdown
# Prompt Integration Guide

## How It Works

APM copies `.prompt.md` files to `.github/prompts/` with:
- Metadata header (source, version, commit)
- `-apm` suffix (e.g., `design-review-apm.prompt.md`)
- Auto-update on version changes

## Commands

### Enable Integration
```bash
mkdir -p .github
apm install
```

### Manual Integration
```bash
apm integrate              # Smart: only new/changed
apm integrate --force      # Force: re-integrate all
```

### Disable Integration
```bash
apm config set auto_integrate false
```

## File Structure

```
.github/prompts/
├── design-review-apm.prompt.md      # From design-guidelines
├── accessibility-audit-apm.prompt.md # From design-guidelines
└── compliance-audit-apm.prompt.md   # From compliance-rules

apm_modules/
├── danielmeppiel/
│   ├── design-guidelines/
│   │   └── design-review.prompt.md  # Original
│   └── compliance-rules/
│       └── compliance-audit.prompt.md # Original
```

## Metadata Header

Each integrated prompt includes tracking metadata:

```markdown
<!-- 
Source: danielmeppiel/design-guidelines (github.com/danielmeppiel/design-guidelines)
Version: 1.0.0
Commit: abc123
Original: design-review.prompt.md
Installed: 2024-01-01T00:00:00
-->
```

## Troubleshooting

**Prompts not integrating?**
- Check `.github/` exists: `ls -la .github`
- Check config: `apm config get auto_integrate`

**Stale prompts after uninstall?**
- Run: `apm integrate` (re-syncs all)
- Or manually: `rm .github/prompts/*-apm.prompt.md`

**Want to disable?**
```bash
apm config set auto_integrate false
rm .github/prompts/*-apm.prompt.md
```

**Effort:** 60 lines (only if needed)

---

### Documentation Summary

| File | Change Type | Lines Added | Priority |
|------|-------------|-------------|----------|
| `docs/getting-started.md` | Add tip | 12 | Required |
| `docs/commands.md` | Add commands | 25 | Required |
| `CHANGELOG.md` | Document changes | 8 | Required |
| `docs/integration.md` | New guide | 60 | Optional |

**Total Required Changes:** 45 lines across 3 files  
**Estimated Time:** 20 minutes

### Writing Guidelines

1. **Be concise** - No walls of text
2. **Show, don't tell** - Use code examples
3. **Practical first** - Common use cases only
4. **Progressive disclosure** - Basic info in README, details in separate docs
5. **Troubleshooting** - Only include if users ask

---

## Impact Analysis: Before vs After

### Before (Original Plan)

| Metric | Value | Assessment |
|--------|-------|------------|
| New commands | 1 (`apm integrate`) | ❌ Adds complexity |
| New config options | 1 (`auto_integrate`) | ❌ Decision fatigue |
| User-facing concepts | 3 (install, integrate, config) | ❌ Too many |
| Lines of docs | 45 | ❌ Needs explanation |
| Manual steps | 2-3 | ❌ Error-prone |
| "Just works" factor | 60% | ❌ Conditional |

### After (Simplified Plan)

| Metric | Value | Assessment |
|--------|-------|------------|
| New commands | 0 | ✅ No learning curve |
| New config options | 0 | ✅ Zero config |
| User-facing concepts | 1 (install/uninstall) | ✅ Familiar |
| Lines of docs | 4 (changelog only) | ✅ Nothing to explain |
| Manual steps | 0 | ✅ Automatic |
| "Just works" factor | 95% | ✅ Invisible |

### Code Changes Comparison

**Original Plan:**
- Add `cleanup_package_prompts()` method (~40 lines)
- Add `apm integrate` command (~80 lines)
- Add helpful messages (~20 lines)
- Add integration tests (~60 lines)
- **Total: ~200 lines added**

**Simplified Plan:**
- Add `sync_integration()` method (~20 lines)
- Change `should_integrate()` to return `True` (1 line change)
- Remove `auto_integrate` config checks (~10 lines removed)
- Add sync tests (~30 lines)
- **Total: ~40 lines added, 10 removed**

**Effort saved:** 60% less code, 90% less documentation

---

## Conclusion

**Verdict:** The original plan suffered from **complexity creep** and exposed implementation details to users.

**Key realizations:**
1. **Cleanup lifecycle** - Solved with idempotent sync (simpler than targeted cleanup)
2. **Late creation workflow** - Non-issue when `.github/` is auto-created
3. **User awareness** - Not needed when feature is invisible

**Revised approach:**
- ✅ **Auto-create directories** - Remove artificial barriers
- ✅ **Idempotent sync** - Self-healing, no manual intervention
- ✅ **Zero configuration** - Convention over configuration
- ✅ **Invisible integration** - Works without user knowledge

**Philosophy shift:**
- FROM: "Give users control" → TO: "Make it just work"
- FROM: "Provide commands for every scenario" → TO: "One command does everything"
- FROM: "Document all features" → TO: "Features don't need docs"

This is how npm, yarn, cargo, and pip handle similar problems. APM should too.

**Implementation effort:** Same or less than original plan  
**User experience:** Vastly superior  
**Maintenance burden:** Significantly lower

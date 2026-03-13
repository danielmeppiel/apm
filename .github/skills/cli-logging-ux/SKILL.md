---
name: cli-logging-ux
description: >
  Use this skill when editing or creating CLI output, logging, warnings,
  error messages, progress indicators, or diagnostic summaries in the APM
  codebase. Activate whenever code touches console helpers (_rich_success,
  _rich_warning, _rich_error, _rich_info, _rich_echo), DiagnosticCollector,
  STATUS_SYMBOLS, or any user-facing terminal output — even if the user
  doesn't mention "logging" or "UX" explicitly.
---

# CLI Logging & Developer Experience

## Decision framework

Apply these three tests to every piece of user-facing output. If a message fails any test, redesign it.

### 1. The "So What?" Test

Every warning must answer: *what should the user do about this?*

```
# Fails — not actionable, user can't do anything
Sub-skill 'my-skill' from 'my-package' overwrites existing skill

# Passes — tells the user exactly what to do
Skipping my-skill — local file exists (not managed by APM). Use 'apm install --force' to overwrite.
```

If the user can't act on it, it's not a warning — it's noise. Demote to `--verbose` or remove.

### 2. The Traffic Light Rule

Use color semantics consistently. Never use a warning color for an informational state.

| Color | Helper | Meaning | When to use |
|-------|--------|---------|-------------|
| Green | `_rich_success()` | Success / completed | Operation finished as expected |
| Yellow | `_rich_warning()` | User action needed | Something requires user decision |
| Red | `_rich_error()` | Error / failure | Operation failed, cannot continue |
| Blue | `_rich_info()` | Informational | Status updates, progress, summaries |
| Dim | `_rich_echo(color="dim")` | Secondary detail | Verbose-mode details, grouping headers |

### 3. The Newspaper Test

Can the user scan output like headlines? Top-level = what happened. Details = drill down.

```
# Bad — warnings break the visual flow between status and summary
[checkmark] package-name
[warning] something happened
[warning] something else happened
  [tree] 3 skill(s) integrated

# Good — clean tree, diagnostics at the end
[checkmark] package-name
  [tree] 3 skill(s) integrated

── Diagnostics ──
  [warning] 2 skills replaced by a different package (last installed wins)
    Run with --verbose to see details
```

## Inline output vs deferred diagnostics

### Use inline output for:
- Success confirmations (`_rich_success`)
- Progress updates (`_rich_info` with indented `└─` prefix)
- Errors that halt the current operation (`_rich_error`)

### Use DiagnosticCollector for:
- Warnings that apply across multiple packages (collisions, overwrites)
- Issues the user should know about but that don't stop the operation
- Anything that would repeat N times in a loop

```python
# Bad — inline warning repeated per file, clutters output
for file in files:
    if collision:
        _rich_warning(f"Skipping {file}...")

# Good — collect during loop, render grouped summary at the end
for file in files:
    if collision:
        diagnostics.skip(file, package=pkg_name)

# Later, after the loop:
if diagnostics.has_diagnostics:
    diagnostics.render_summary()
```

DiagnosticCollector categories: `skip()` for collisions, `overwrite()` for cross-package replacements, `warn()` for general warnings, `error()` for failures.

## Console helper conventions

Always use the helpers from `apm_cli.utils.console` — never raw `print()` or bare `click.echo()`.

**Emojis are banned.** Never use emoji characters anywhere in CLI output — not in messages, symbols, help text, or status indicators. Use ASCII text symbols exclusively via `STATUS_SYMBOLS`.

```python
from apm_cli.utils.console import (
    _rich_success, _rich_error, _rich_warning, _rich_info, _rich_echo
)

_rich_success("Installed 3 APM dependencies")        # green, bold
_rich_info("  └─ 2 prompts integrated → .github/prompts/")  # blue
_rich_warning("Config drift detected — re-run apm install")  # yellow
_rich_error("Failed to download package")              # red
_rich_echo("    [pkg-name]", color="dim")              # dim, for verbose details
```

Use `STATUS_SYMBOLS` dict with `symbol=` parameter for consistent ASCII prefixes:
```python
_rich_info("Starting operation...", symbol="gear")     # renders as "[*] Starting operation..."
```

## Output structure pattern

Follow this visual hierarchy for multi-package operations:

```
[checkmark] package-name-1                      # _rich_success — download/copy ok
  [tree] 2 prompts integrated → .github/prompts/     # _rich_info — indented summary
  [tree] 1 skill(s) integrated → .github/skills/
[checkmark] package-name-2
  [tree] 1 instruction(s) integrated → .github/instructions/

── Diagnostics ──                         # Only if diagnostics.has_diagnostics
  [warning] N files skipped — ...                   # Grouped by category
    Run with --verbose to see details

Installed 2 APM dependencies              # _rich_success — final summary
```

## Content-awareness principle

Before reporting changes, check if anything actually changed. Don't report no-ops.

```python
# Bad — always copies and reports, even when content is identical
shutil.rmtree(target)
shutil.copytree(source, target)
_rich_info(f"  └─ Skill updated")

# Good — skip when content matches
if SkillIntegrator._dirs_equal(source, target):
    continue  # Nothing changed, nothing to report
```

## Anti-patterns

1. **Warning for non-actionable state** — If the user can't do anything about it, use `_rich_info` or defer to `--verbose`, not `_rich_warning`.

2. **Inline warnings in loops** — Use `DiagnosticCollector` to collect, then render a grouped summary after the loop.

3. **Missing `diagnostics` parameter** — When calling integrators, always pass `diagnostics=diagnostics` so warnings route to the deferred summary.

4. **No emojis, ever** — Emojis are completely banned from all CLI output. Use ASCII text symbols from `STATUS_SYMBOLS` exclusively. This applies to messages, help text, status indicators, and table titles.

5. **Inconsistent symbols** — Always use `STATUS_SYMBOLS` dict with `symbol=` param, not inline characters.

6. **Walls of text** — Use Rich tables for structured data, panels for grouped content. Break up long output with visual hierarchy (indentation, `└─` tree connectors).

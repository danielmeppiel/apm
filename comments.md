## Chief Architect Decision — PR #83

@SebastienDegodez — thank you for this. The plugin marketplace ecosystem is an industry standard now and APM needs to support it. This review is about routing it through APM's existing architecture, not building alongside it.

### Decision: Request changes

---

### APM's detection pattern (how it works today)

APM already handles five foreign formats, all the same way:

```
apm install owner/repo
        ↓
   clone to apm_modules/
        ↓
   look at what's inside:
     ├─ apm.yml only           → APM_PACKAGE
     ├─ SKILL.md only          → CLAUDE_SKILL (synthesize apm.yml)
     ├─ apm.yml + SKILL.md     → HYBRID
     ├─ .collection.yml        → COLLECTION (download items, generate .apm/)
     └─ single .prompt.md file → VIRTUAL_FILE (wrap in package)
```

No flags. No separate commands. `apm install` figures it out. The user never needs to know or care what format the source uses.

### What plugin support should look like

The same pattern, extended:

```
apm install anthropics/claude-code-plugins/commit-commands
        ↓
   clone to apm_modules/
        ↓
   look at what's inside:
     ├─ apm.yml       → APM_PACKAGE (existing)
     ├─ SKILL.md      → CLAUDE_SKILL (existing)
     ├─ plugin.json   → MARKETPLACE_PLUGIN ← new detection
     └─ ...
```

When the downloader finds `plugin.json` (and no `apm.yml`), it does what it already does for `SKILL.md`:
1. Parse `plugin.json` for metadata (name, description, version)
2. Map the plugin's `agents/`, `skills/`, `commands/` into `.apm/` subdirectories
3. Synthesize `apm.yml`
4. Set `PackageType.MARKETPLACE_PLUGIN`
5. From here on it's a normal dependency — lock file, version pinning, transitive resolution, conflict detection, everything works

The user experience is just:

```bash
apm install anthropics/claude-code-plugins/commit-commands
```

Or in `apm.yml`:

```yaml
dependencies:
  apm:
    - company/coding-standards#v2.0
    - anthropics/claude-code-plugins/commit-commands#v1.2.0
```

That's it. No `apm plugin` subcommand. No `plugins:` section. No `@claude` syntax. Just `apm install`, same as everything else.

### The marketplace discovery question

The useful part of your PR — `MarketplaceManager` resolving `marketplace.json` manifests — answers a real question: *"How do I find the repo URL for a plugin I saw in the Claude marketplace?"*

But that's a **browsing concern**, not an **install concern**. Once a user knows the repo, it's just `apm install owner/repo/plugin-name`. The mapping from marketplace name to repo URL is what the marketplace UI already does (ClaudePluginHub, `/plugin` in Claude Code, etc.).

If we want APM to help with discovery later, it can be a lightweight convenience:

```bash
apm browse claude    # opens marketplace URL in browser
```

But that's a separate, smaller feature — not a prerequisite for plugin support.

### What to keep from your PR

| Keep & relocate | Cut |
|---|---|
| `Plugin` dataclass + `from_claude_format()` / `from_github_format()` → becomes `plugin_parser.py` (like `collection_parser.py`) | `apm plugin` CLI subcommand group (all 5 commands) |
| `plugin.json` → `.apm/` structure mapping logic | Separate `plugins:` section in `apm.yml` |
| Test fixtures (mock-plugin structure) | `PluginInstaller` (duplicate of existing install pipeline) |
| Docs explaining plugin format support | `MarketplaceManager` / `PluginResolver` (defer to Phase 2) |
| | Separate plugin primitive discovery phase |

### Implementation plan

**Phase 1 — `plugin.json` as detected format** *(core value, small surface area)*

1. Add `MARKETPLACE_PLUGIN` to `PackageType` enum
2. Write `plugin_parser.py` in `src/apm_cli/deps/` — parses `plugin.json`, maps agents/skills/commands to `.apm/` structure, synthesizes `apm.yml`
3. Extend `GitHubPackageDownloader` detection: after checking for `apm.yml` and `SKILL.md`, check for `plugin.json`
4. Extend `validate_virtual_package_exists()` to check for `plugin.json` in subdirectory packages
5. `scan_dependency_primitives()` already handles the rest — no changes needed

Result: `apm install owner/repo` works for plugin repos. Lock file, version pinning, transitive deps, conflict detection — all free.

**Phase 2 — Marketplace source resolution** *(optional, later)*

Your `MarketplaceManager` code becomes a convenience layer that maps short names to repo URLs. Could be a standalone `apm browse` or a resolver that feeds into `apm install`. This is additive and doesn't block Phase 1.

### Why this matters architecturally

APM currently has one install pipeline, one manifest format, one discovery system, one lock file. Every foreign format normalizes into that single model. This is the project's most important architectural invariant — it's what makes APM "the npm for agent primitives" rather than "a wrapper around five different tools."

PR #83 as written breaks that invariant by creating a parallel pipeline. The plugin ecosystem deserves full support — but through the existing architecture, not alongside it.

Your `plugin.json` parsing code and test fixtures are genuinely useful. I'd welcome a V2 that integrates them as a format adapter in the existing pipeline. Happy to pair on scoping that.
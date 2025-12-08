# Skills Guide

Skills (`SKILL.md`) are package meta-guides that help AI agents quickly understand what an APM package does and how to leverage its content. They provide a concise summary optimized for AI consumption.

## What are Skills?

Skills describe an APM package in a format AI agents can quickly parse:
- **What** the package provides (name, description)
- **How** to use it (body content with guidelines)
- **Resources** available (bundled scripts, references, examples)

When you install a package with a SKILL.md, AI agents can quickly understand how to use it.

## Installing Skills

### From Claude Skill Repositories

Many Claude Skills are hosted in monorepos. Install any skill directly:

```bash
# Install a skill from a monorepo subdirectory
apm install ComposioHQ/awesome-claude-skills/brand-guidelines

# Install skill with resources (scripts, references, etc.)
apm install ComposioHQ/awesome-claude-skills/skill-creator
```

**What happens:**
1. APM downloads the subdirectory to `apm_modules/owner/repo/skill-name/`
2. Adds dependency to your `apm.yml`
3. AI agents can read SKILL.md to understand the package

### Installation Path Structure

Skills maintain their natural path hierarchy:

```
apm_modules/
└── ComposioHQ/
    └── awesome-claude-skills/
        └── brand-guidelines/      # Skill subdirectory
            ├── SKILL.md           # Original skill file
            ├── apm.yml            # Auto-generated
            └── LICENSE.txt        # Any bundled files
```

## SKILL.md Format

### Basic Structure

```markdown
---
name: Skill Name
description: One-line description of what this skill does
---

# Skill Body

Detailed instructions for the AI agent on how to use this skill.

## Guidelines
- Guideline 1
- Guideline 2

## Examples
...
```

### Required Frontmatter

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Display name for the skill |
| `description` | string | One-line description |

### Body Content

The body contains:
- **Instructions** for the AI agent
- **Guidelines** and best practices
- **Examples** of usage
- **References** to bundled resources

## Bundled Resources

Skills can include additional resources:

```
my-skill/
├── SKILL.md           # Main skill file
├── scripts/           # Executable code
│   └── validate.py
├── references/        # Documentation
│   └── style-guide.md
├── examples/          # Sample files
│   └── sample.json
└── assets/            # Templates, images
    └── logo.png
```

**Note:** All resources stay in `apm_modules/` where AI agents can reference them.

## Creating Your Own Skills

### Quick Start with apm init

`apm init` automatically creates a SKILL.md at root:

```bash
apm init my-skill && cd my-skill
```

This creates:
```
my-skill/
├── apm.yml       # Package manifest
├── SKILL.md      # Package meta-guide (edit this!)
└── .apm/         # Primitives folder
```

### Option 1: Standalone Skill

Create a repo with just `SKILL.md`:

```bash
mkdir my-skill && cd my-skill

cat > SKILL.md << 'EOF'
---
name: My Custom Skill
description: Does something useful
---

# My Custom Skill

## Overview
Describe what this skill does...

## Guidelines
- Follow these rules...

## Examples
...
EOF

git init && git add . && git commit -m "Initial skill"
git push origin main
```

Anyone can now install it:
```bash
apm install your-org/my-skill
```

### Option 2: Skill in APM Package

Add `SKILL.md` to any existing APM package:

```
my-package/
├── apm.yml
├── SKILL.md          # Add this for Claude compatibility
└── .apm/
    ├── instructions/
    └── prompts/
```

This creates a **hybrid package** that works with both APM primitives and Claude Skills.

### Option 3: Skills Collection (Monorepo)

Organize multiple skills in a monorepo:

```
awesome-skills/
├── skill-1/
│   ├── SKILL.md
│   └── references/
├── skill-2/
│   └── SKILL.md
└── skill-3/
    ├── SKILL.md
    └── scripts/
```

Users install individual skills:
```bash
apm install your-org/awesome-skills/skill-1
apm install your-org/awesome-skills/skill-2
```

## Package Detection

APM automatically detects package types:

| Has | Type | Detection |
|-----|------|-----------|
| `apm.yml` only | APM Package | Standard APM primitives |
| `SKILL.md` only | Claude Skill | Auto-generates `apm.yml` |
| Both files | Hybrid Package | Best of both worlds |

## Target Detection

APM decides where to output based on project structure:

| Condition | Target | Skill Output |
|-----------|--------|--------------|
| `.github/` exists | VSCode | `.github/agents/*.agent.md` |
| `.claude/` exists | Claude | Native SKILL.md |
| Both exist | All | Both outputs |
| Neither | Minimal | AGENTS.md only |

Override with:
```bash
apm install skill-name --target vscode
apm compile --target claude
```

Or set in `apm.yml`:
```yaml
name: my-project
target: vscode  # or claude, or all
```

## Best Practices

### 1. Clear Naming
Use descriptive, lowercase-hyphenated names:
- ✅ `brand-guidelines`
- ✅ `code-review-expert`
- ❌ `mySkill`
- ❌ `Skill_1`

### 2. Focused Description
Keep the description to one line:
- ✅ `Applies corporate brand colors and typography`
- ❌ `This skill helps you with branding and it can also do typography and it uses the company colors...`

### 3. Structured Body
Organize with clear sections:
```markdown
## Overview
What this skill does

## Guidelines
Rules to follow

## Examples
How to use it

## References
Links to resources
```

### 4. Resource Organization
Keep bundled files organized:
```
my-skill/
├── SKILL.md
├── scripts/      # Executable code only
├── references/   # Documentation
├── examples/     # Sample files
└── assets/       # Static resources
```

### 5. Version Control
Keep skills in version control. Use semantic versioning in the generated `apm.yml` for tracking.

## Integration with Other Primitives

Skills complement other APM primitives:

| Primitive | Purpose | Works With Skills |
|-----------|---------|-------------------|
| Instructions | Coding standards | Skills can reference instruction context |
| Prompts | Executable workflows | Skills describe how to use prompts |
| Agents | AI personalities | Skills explain what agents are available |
| Context | Project knowledge | Skills can link to context files |

## Troubleshooting

### Skill Not Installing

```
Error: Could not find SKILL.md or apm.yml
```

**Solution:** Verify the path is correct. For subdirectories, use full path:
```bash
apm install owner/repo/subdirectory
```

### Agent Not Generated

If `.github/agents/*.agent.md` isn't created:

1. **Check target:** Create `.github/` folder or use `--target vscode`
2. **Reinstall:** Run `apm install package-name` again

### Metadata Missing

If agent lacks APM metadata:

1. Check the skill was installed via APM (not manually copied)
2. Reinstall the package

## Related Documentation

- [Core Concepts](concepts.md) - Understanding APM architecture
- [Primitives Guide](primitives.md) - All primitive types
- [CLI Reference](cli-reference.md) - Full command documentation
- [Dependencies](dependencies.md) - Package management

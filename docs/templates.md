# APM Template Ecosystem

This document describes the community-driven template ecosystem for APM, following npm's initializer pattern (`npm init <initializer>`).

## Overview

APM templates are distributed as npm packages named `create-apm-<template-name>`. This allows:

- **Community ownership** - Anyone can publish templates
- **Standard tooling** - Uses npm/npx (no new tools)
- **Versioning** - Templates evolve independently via semver
- **Discoverability** - Standard npm search works

## Using Templates

### Basic Usage

```bash
# Run a template
apm init <template-name> [project-name]

# Examples:
apm init hello-world my-app      # → npx create-apm-hello-world my-app
apm init express-api my-api      # → npx create-apm-express-api my-api
apm init compliance              # → npx create-apm-compliance (current dir)
```

### How It Works

When you run `apm init <template>`, APM delegates to npx:

```
apm init hello-world my-app
        ↓
npx create-apm-hello-world my-app
```

This follows npm's established pattern where `npm init <name>` runs `npx create-<name>`.

### Without Template (Default)

Running `apm init` without a template name creates a minimal `apm.yml`:

```bash
apm init                    # Interactive mode
apm init --yes              # Use defaults
apm init my-project --yes   # Create directory with defaults
```

## Creating Templates

### Package Naming Convention

Templates must be named `create-apm-<template-name>`:

| Template Name | npm Package Name |
|---------------|------------------|
| `hello-world` | `create-apm-hello-world` |
| `express-api` | `create-apm-express-api` |
| `compliance`  | `create-apm-compliance` |

### Package Structure

```
create-apm-hello-world/
├── package.json          # npm package manifest
├── bin/
│   └── index.js          # CLI entry point (executable)
├── templates/
│   ├── apm.yml           # APM configuration template
│   ├── hello-world.prompt.md
│   ├── README.md
│   └── .apm/
│       ├── instructions/
│       │   └── coding-standards.instructions.md
│       └── chatmodes/
│           └── developer.chatmode.md
└── README.md             # Template documentation
```

### Required Files

#### `package.json`

```json
{
  "name": "create-apm-hello-world",
  "version": "1.0.0",
  "description": "APM template for getting started",
  "bin": {
    "create-apm-hello-world": "./bin/index.js"
  },
  "files": ["bin", "templates"],
  "keywords": ["create-apm", "apm", "template"],
  "license": "MIT"
}
```

#### `bin/index.js`

```javascript
#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const args = process.argv.slice(2);
const projectName = args[0] || 'my-apm-project';
const targetDir = path.resolve(process.cwd(), projectName);

// Create project directory
if (!fs.existsSync(targetDir)) {
  fs.mkdirSync(targetDir, { recursive: true });
}

// Copy template files
const templatesDir = path.join(__dirname, '..', 'templates');
copyDir(templatesDir, targetDir);

// Substitute variables in apm.yml
const apmYmlPath = path.join(targetDir, 'apm.yml');
let apmYml = fs.readFileSync(apmYmlPath, 'utf8');
apmYml = apmYml.replace(/{{project_name}}/g, projectName);
fs.writeFileSync(apmYmlPath, apmYml);

console.log(`\n✨ Created APM project: ${projectName}\n`);
console.log('Next steps:');
console.log(`  cd ${projectName}`);
console.log('  apm runtime setup copilot');
console.log('  apm compile');
console.log('  apm run start');

function copyDir(src, dest) {
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      fs.mkdirSync(destPath, { recursive: true });
      copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}
```

### Template Variables

Templates can use variable placeholders that are substituted during project creation:

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `{{project_name}}` | Project directory name | `my-app` |
| `{{author}}` | Auto-detected from git config | `John Doe` |
| `{{year}}` | Current year | Current year (e.g., 2025) |

### Template `apm.yml` Example

```yaml
name: {{project_name}}
version: 1.0.0
description: APM project created from hello-world template
author: {{author}}

dependencies:
  apm: []
  mcp: []

scripts:
  start: "codex hello-world.prompt.md"
```

## Publishing Templates

### To npm

```bash
cd create-apm-hello-world
npm publish
```

### Testing Locally

```bash
# Link for local testing
cd create-apm-hello-world
npm link

# Use the template
apm init hello-world test-project
```

## Template Best Practices

### DO

- ✅ Include a helpful README.md
- ✅ Provide working example prompts
- ✅ Use semantic versioning
- ✅ Include clear next steps after creation
- ✅ Test the template before publishing

### DON'T

- ❌ Include node_modules in the package
- ❌ Hardcode absolute paths
- ❌ Include sensitive information
- ❌ Depend on APM CLI internals

## Available Templates

### Official Templates

| Template | Description | Install |
|----------|-------------|---------|
| `hello-world` | Basic getting started template | `apm init hello-world` |

### Community Templates

Community templates are discovered via npm search:

```bash
npm search create-apm
```

## CLI Integration

The `apm init` command handles template delegation:

```python
# Simplified CLI logic
def init(initializer, project_name, yes):
    if initializer:
        # Delegate to npx for community templates
        cmd = ['npx', f'create-apm-{initializer}']
        if project_name:
            cmd.append(project_name)
        subprocess.run(cmd)
    else:
        # Minimal init (default behavior)
        _create_minimal_apm_yml()
```

This design ensures:
- Templates are decoupled from APM CLI releases
- Community can innovate independently
- APM CLI stays minimal and focused

## Future Considerations

### Template Discovery Command

A future `apm templates` command could search npm for `create-apm-*` packages:

```bash
apm templates              # List popular templates
apm templates search api   # Search for API templates
```

### Template Metadata

Templates could include metadata for better discoverability:

```json
{
  "apm-template": {
    "category": "backend",
    "tags": ["express", "api", "rest"],
    "minApmVersion": "0.5.0"
  }
}
```

## Related Documentation

- [Getting Started](getting-started.md) - Basic APM setup
- [CLI Reference](cli-reference.md) - Full command documentation
- [Examples](examples.md) - Real-world usage patterns

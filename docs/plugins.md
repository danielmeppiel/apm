# Plugin System Guide

APM's plugin system allows you to install reusable components from Claude Code and GitHub marketplaces. Plugins are packages that contain skills, agents, commands (prompts), and hooks that integrate directly into your project.

## Overview

Plugins extend APM projects with pre-built capabilities. Instead of building from scratch, you can install existing plugins that contain:

- **Skills** - Reusable agent personas and expertise packages
- **Agents** - AI agent definitions with tool integration
- **Commands** - Executable workflow prompts (slash commands)
- **Hooks** - Lifecycle and automation scripts
- **Instructions** - Context and coding guidelines

## Installation Workflow

APM uses a two-step process for plugin installation:

```bash
# Step 1: Track plugin in apm.yml
apm plugin install <plugin-id>@<marketplace>

# Step 2: Download and integrate primitives
apm install
```

This workflow:
- Tracks plugins in `apm.yml` for dependency management
- Downloads plugins to `apm_modules/` directory
- Automatically integrates primitives during compilation
- Supports GitHub and Azure DevOps repositories

## Quick Start

### Search for Plugins

```bash
# Search all plugins
apm plugin search

# Search by keyword
apm plugin search copilot

# Filter by tag
apm plugin search --tag best-practices
```

### View Plugin Details

```bash
# Show detailed information
apm plugin info awesome-copilot
```

### Install a Plugin

```bash
# Track plugin from marketplace
apm plugin install awesome-copilot@claude

# Download and integrate primitives
apm install
```

### List Installed Plugins

```bash
# Show installed plugins
apm plugin installed
```

## Installation

### Basic Plugin Installation

Track a plugin from a marketplace in your `apm.yml`:

```bash
apm plugin install plugin-id@marketplace-name
```

Then download and integrate the plugin:

```bash
apm install
```

### Supported Sources

#### Claude Code Marketplace
The official Claude Code marketplace:

```bash
apm plugin search
apm plugin install awesome-copilot@claude
```

#### GitHub Repositories
Plugins hosted on GitHub:
- Automatic detection
- Uses `GITHUB_APM_PAT` or `GITHUB_TOKEN` for authentication

```bash
# Repository: owner/repo
apm plugin install my-plugin@owner/repo
```

#### Azure DevOps Repositories
Plugins hosted on Azure DevOps:
- Automatic detection from full URL
- Uses `ADO_APM_PAT` for authentication
- Must use full URL format in marketplace

```bash
# Repository: https://dev.azure.com/org/project/_git/repo
apm plugin install my-plugin@https://dev.azure.com/org/project/_git/repo
```

#### Claude Official Marketplace
The official Claude Code plugin marketplace contains verified plugins:

```bash
apm plugin install commit-commands@claude
```

#### Awesome Copilot Marketplace
GitHub's Awesome Copilot repository provides curated Copilot extensions:

```bash
apm plugin install my-extension@awesome-copilot
```

#### Custom Marketplaces
You can host your own plugin marketplace:

```bash
apm plugin install my-plugin@https://custom-marketplace.com
```

## How Plugins Work

When you run `apm plugin install plugin-name@marketplace`:

1. Resolves the marketplace source
2. Fetches the marketplace manifest
3. Finds the plugin in the manifest
4. Tracks the plugin in `apm.yml` under the `plugins:` section

Then when you run `apm install`:

1. Loads plugins from the `plugins:` section in `apm.yml`
2. Downloads plugins to `apm_modules/` directory
3. Validates plugin structure and metadata
4. Integrates plugin primitives into your project

Plugin components are automatically discovered during compilation:
- **Agents** → Discovered from `apm_modules/<owner>/<repo>/agents/*.agent.md`
- **Skills** → Discovered from `apm_modules/<owner>/<repo>/skills/*.skill.md`
- **Instructions** → Discovered from `apm_modules/<owner>/<repo>/instructions/*.instructions.md`

### Primitive Discovery Priority

APM discovers primitives in the following priority order:

1. **Local** - Your project's `.apm/` directory (highest priority)
2. **Dependencies** - From `apm_modules/` in declaration order

This ensures your local customizations always take precedence over plugin defaults.

## Plugin Structure

Plugins follow the standard APM package structure:

```plaintext
repository-root/
├── plugin.json              # Plugin metadata (required)
├── README.md               # Plugin documentation
├── agents/                 # Agent definitions
│   └── *.agent.md         # Agent files
├── skills/                 # Skill definitions
│   └── *.skill.md         # Skill files
├── instructions/           # Instruction files
│   └── *.instructions.md
├── commands/              # Command/prompt files
│   └── *.prompt.md       # Prompt files
└── hooks/                 # Lifecycle hooks
    └── *.py              # Hook scripts
```

### plugin.json Format

```json
{
  "id": "my-plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "description": "A helpful plugin for X",
  "author": "Your Name",
  "repository": "owner/repo",
  "homepage": "https://github.com/owner/repo",
  "license": "MIT",
  "tags": ["productivity", "tools"],
  "dependencies": []
}
```

## Managing Plugins

### View Installed Plugins

List all installed plugins with details:

```bash
apm plugin installed
```

Or check your `apm.yml`:

```yaml
name: my-project
version: 1.0.0

plugins:
  - name: commit-commands
    source: https://github.com/anthropics/claude-code
    version: latest
```

### Browse Available Plugins

Search the marketplace:

```bash
# Search all plugins
apm plugin search

# Search by keyword
apm plugin search testing

# Filter by tags
apm plugin search --tag best-practices
```

List plugins from a specific marketplace:

```bash
apm plugin list claude
apm plugin list owner/repo
```

### Update Your Project

After tracking plugins in `apm.yml`, download and integrate them:

```bash
apm install
```

This will download and integrate all plugins tracked in `apm.yml`.

## Creating Plugins

To create a plugin for APM:

1. **Create Plugin Repository**

   Set up your repository with the required structure:
   
   ```bash
   mkdir my-plugin && cd my-plugin
   git init
   ```

2. **Create plugin.json**

   ```json
   {
     "id": "my-plugin",
     "name": "My Awesome Plugin",
     "version": "1.0.0",
     "description": "Provides awesome functionality",
     "author": "Your Name",
     "repository": "owner/my-plugin",
     "tags": ["productivity", "tools"],
     "dependencies": []
   }
   ```

3. **Add Plugin Components**

   Create directories and add your components:
   
   ```bash
   mkdir -p agents skills instructions
   echo "---\nname: My Agent\n---\n\n# Agent" > agents/my-agent.agent.md
   echo "# My Skill" > skills/my-skill.skill.md
   ```

4. **Test Locally**

   ```bash
   # Create test project
   mkdir test-project && cd test-project
   apm init .
   
   # Install your plugin from local path (simulate apm_modules structure)
   mkdir -p apm_modules/owner
   cp -r ../my-plugin apm_modules/owner/my-plugin
   
   # Compile and test
   apm compile
   ```

5. **Publish to GitHub/Azure DevOps**

   ```bash
   git add .
   git commit -m "Initial plugin release"
   git push origin main
   ```

6. **Submit to Marketplace**

   Create a pull request to add your plugin to a marketplace manifest.
   
   For Claude Code marketplace, add to the `marketplace.json` file:
   
   ```json
   {
     "id": "my-plugin",
     "name": "My Awesome Plugin",
     "description": "Provides awesome functionality",
     "repository": "owner/my-plugin",
     "version": "1.0.0",
     "author": "Your Name",
     "tags": ["productivity", "tools"]
   }
   ```

   **Note:** For Azure DevOps or GitHub Enterprise, use full URL:
   ```json
   "repository": "https://dev.azure.com/org/project/_git/repo"
   ```

### Best Practices

1. **Namespace your plugins** - Use clear, lowercase names with hyphens
2. **Include complete metadata** - Version, description, and author information
3. **Document features** - Include a detailed README.md
4. **Test integration** - Ensure primitives work with APM discovery
5. **Version consistently** - Follow semantic versioning

## Troubleshooting

### Plugin Not Found

If you get "Plugin not found in marketplace":

1. Verify the plugin ID and marketplace name are correct
2. Check that the marketplace has a valid manifest file
3. Ensure the plugin ID exists in the marketplace manifest

### Integration Issues

If plugin primitives don't appear after `apm install`:

1. Run `apm install --verbose` to see detailed output
2. Check that plugin files use correct naming conventions:
   - Commands: `*.prompt.md`
   - Agents: `*.agent.md`
   - Skills: `SKILL.md` files in skill directories
3. Verify the plugin repository structure matches the standard

### Custom Marketplace Issues

For custom marketplaces:

1. Ensure the manifest is at `.claude-plugin/marketplace.json` or `.github/plugin/marketplace.json`
2. Use valid JSON syntax
3. Set `Content-Type: application/json` headers if serving via HTTP
4. Test the manifest URL directly to verify it's accessible

## Examples

### Full Plugin Installation Workflow

```bash
# List available plugins from Claude marketplace
apm plugin list claude

# Install a specific plugin
apm plugin install commit-commands@claude

# Verify it was added to apm.yml
cat apm.yml

# Install all dependencies (including plugins)
apm install

# Compile context files with plugin contributions
apm compile
```

### Hosting Your Own Plugin Marketplace

```bash
# Create a GitHub repository for your plugins
mkdir my-plugins-marketplace
cd my-plugins-marketplace

# Create plugin structure
mkdir -p .github/plugin
mkdir plugins/my-first-plugin/{agents,commands,skills}

# Create marketplace manifest
cat > .github/plugin/marketplace.json << 'EOF'
{
  "plugins": [
    {
      "id": "my-first-plugin",
      "name": "My First Plugin",
      "description": "A demonstration plugin",
      "version": "1.0.0",
      "repository": "owner/my-plugins-marketplace"
    }
  ]
}
EOF

# Push to GitHub
git add .
git commit -m "Initial plugin marketplace"
git push origin main

# Install from your marketplace
apm plugin install my-first-plugin@owner/my-plugins-marketplace
```

## See Also

- [Skills Guide](skills.md) - Understanding skill packages
- [Agents Guide](primitives.md) - Creating AI agents
- [CLI Reference](cli-reference.md) - Complete command documentation
- [Dependencies Management](dependencies.md) - How APM manages packages

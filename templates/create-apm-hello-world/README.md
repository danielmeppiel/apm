# create-apm-hello-world

APM template for getting started with AI-Native Development.

## Usage

### Via APM CLI (recommended)

```bash
apm init hello-world my-project
```

### Via npx

```bash
npx create-apm-hello-world my-project
```

## What's Included

This template creates a minimal APM project with:

- **`apm.yml`** - Project configuration (like package.json for AI-Native projects)
- **`hello-world.prompt.md`** - Example executable prompt
- **`.apm/instructions/`** - AI instructions directory
- **`.apm/chatmodes/`** - AI personas directory
- **`README.md`** - Project documentation

## After Creation

```bash
cd my-project
apm runtime setup copilot   # Install coding agent
apm compile                  # Generate AGENTS.md
apm run start               # Run hello world prompt
```

## Creating Your Own Templates

See the [APM Template Ecosystem documentation](https://github.com/danielmeppiel/apm/blob/main/docs/templates.md) for how to create and publish your own templates.

## License

MIT

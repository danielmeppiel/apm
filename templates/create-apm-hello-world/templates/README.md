# {{project_name}}

An AI-Native project powered by [APM](https://github.com/danielmeppiel/apm).

## Quick Start

```bash
# Install a coding agent runtime
apm runtime setup copilot

# Compile AI context into AGENTS.md
apm compile

# Run the hello world prompt
apm run start --param name="YourName"
```

## Project Structure

```
{{project_name}}/
├── apm.yml                 # Project configuration
├── hello-world.prompt.md   # Example prompt
├── AGENTS.md               # Generated AI context (after compile)
└── .apm/
    ├── instructions/       # AI instructions
    └── chatmodes/          # AI personas
```

## Adding Dependencies

Install APM packages from the community:

```bash
apm install danielmeppiel/design-guidelines
apm install danielmeppiel/compliance-rules
```

## Learn More

- [APM Documentation](https://github.com/danielmeppiel/apm)
- [Getting Started Guide](https://github.com/danielmeppiel/apm/blob/main/docs/getting-started.md)
- [Creating Prompts](https://github.com/danielmeppiel/apm/blob/main/docs/prompts.md)

## License

MIT © {{author}} {{year}}

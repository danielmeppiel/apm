# Pack & Unpack

Create self-contained bundles from installed dependencies and apply them to other projects.

## `apm pack`

Collects all deployed files from the resolved dependency tree into a portable bundle.

```bash
apm pack                        # bundle into ./build/<name>-<version>/
apm pack --archive              # produce a .tar.gz
apm pack --target vscode        # only .github/ files
apm pack --dry-run              # list files without writing
apm pack -o dist/               # custom output directory
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--format` | `apm` | Bundle format (`apm` or `plugin`) |
| `--target` | auto-detect | Filter: `vscode`, `claude`, or `all` |
| `--archive` | off | Produce `.tar.gz` and remove the directory |
| `-o, --output` | `./build` | Output directory |
| `--dry-run` | off | Show what would be packed without writing |

### What goes into the bundle

- Every file listed in `deployed_files` across all locked dependencies, filtered by the effective target.
- An enriched copy of `apm.lock` with a `pack:` metadata section (format, target, timestamp). The original lockfile is never modified.

### Target filtering

| Target | Includes paths starting with |
|--------|------------------------------|
| `vscode` | `.github/` |
| `claude` | `.claude/` |
| `all` | both |

If no target is specified, it's auto-detected from `apm.yml` or project structure (same logic as `apm compile`).

## `apm unpack`

Extracts a bundle into the current project directory.

```bash
apm unpack ./build/my-pkg-1.0.0.tar.gz     # from archive
apm unpack ./build/my-pkg-1.0.0/            # from directory
apm unpack bundle.tar.gz -o ./target/       # custom output
apm unpack bundle.tar.gz --skip-verify      # skip completeness check
apm unpack bundle.tar.gz --dry-run          # list files without writing
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `-o, --output` | `.` | Target directory |
| `--skip-verify` | off | Skip bundle completeness check |
| `--dry-run` | off | Show what would be unpacked without writing |

### Verification

By default, `unpack` verifies that every file listed in the lockfile's `deployed_files` exists in the bundle before extracting. Use `--skip-verify` to bypass this.

### Merge semantics (v1)

- **Additive-only**: files from the bundle are copied into the target directory. Existing local files not in the bundle are untouched.
- **Overwrites**: if a local file has the same path as a bundle file, the bundle file wins.
- `apm.lock` from the bundle is metadata only — it is **not** copied to the output directory.

## Enriched lockfile

The `apm.lock` inside a bundle contains an additional `pack:` section:

```yaml
pack:
  format: apm
  target: vscode
  packed_at: '2026-03-09T12:00:00+00:00'
lockfile_version: '1'
generated_at: ...
dependencies:
  - repo_url: owner/repo
    ...
```

This section is only present in the bundle copy — the project's lockfile is never modified.

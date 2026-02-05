# Contributing to apm-cli

Thank you for considering contributing to apm-cli! This document outlines the process for contributing to the project.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before contributing.

## How to Contribute

### Reporting Bugs

Before submitting a bug report:

1. Check the [GitHub Issues](https://github.com/username/apm-cli/issues) to see if the bug has already been reported.
2. Update your copy of the code to the latest version to ensure the issue hasn't been fixed.

When submitting a bug report:

1. Use our bug report template.
2. Include detailed steps to reproduce the bug.
3. Describe the expected behavior and what actually happened.
4. Include any relevant logs or error messages.

### Suggesting Enhancements

Enhancement suggestions are welcome! Please:

1. Use our feature request template.
2. Clearly describe the enhancement and its benefits.
3. Provide examples of how the enhancement would work.

### Development Process

1. Fork the repository.
2. Create a new branch for your feature/fix: `git checkout -b feature/your-feature-name` or `git checkout -b fix/issue-description`.
3. Make your changes.
4. Run tests: `uv run pytest`
5. Ensure your code follows our coding style (we use Black and isort).
6. Commit your changes with a descriptive message.
7. Push to your fork.
8. Submit a pull request.

### Pull Request Process

1. **Choose the appropriate PR template** for your change:
   - **🚀 New Feature**: Use the `feature.md` template
   - **🐛 Bug Fix**: Use the `bugfix.md` template
   - **📖 Documentation**: Use the `documentation.md` template
   - **🔧 Maintenance**: Use the `maintenance.md` template
   - **Other**: Use the standard PR template

2. **Apply the correct label** after creating your PR:
   - `enhancement` or `feature` - New functionality
   - `bug` or `fix` - Bug fixes
   - `documentation` or `docs` - Documentation updates
   - `ignore-for-release` - Exclude from release notes

3. Follow the template provided.
4. Ensure your PR addresses only one concern (one feature, one bug fix).
5. Include tests for new functionality.
6. Update documentation if needed.
7. PRs must pass all checks before they can be merged.

**Note**: Labels are used to automatically categorize changes in release notes. The correct label helps maintainers and users understand what changed in each release.

## Development Environment

This project uses uv to manage Python environments and dependencies:

```bash
# Clone the repository
git clone <this-repo-url>
cd apm

# Create a virtual environment and install dependencies
uv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
uv pip install -e ".[dev]"
```

## Testing

We use pytest for testing. The project uses `uv` to manage virtual environments and dependencies — the recommended way to run tests is:

```bash
uv run pytest
# install dev dependencies (creates .venv managed by uv)
uv sync --extra dev

# run the test suite
uv run pytest -q
```

If you don't have `uv` available, you can use a standard Python venv and pip:

```bash
# create and activate a venv (POSIX / WSL)
python -m venv .venv
source .venv/bin/activate

# install this package in editable mode and test deps
pip install -U pip
pip install -e .[dev]

# run tests
pytest -q
```

## Coding Style

This project follows:
- [PEP 8](https://pep8.org/) for Python style guidelines
- We use Black for code formatting and isort for import sorting

You can run these tools with:

```bash
uv run black .
uv run isort .
```

## Documentation

If your changes affect how users interact with the project, update the documentation accordingly.

## License

By contributing to this project, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).

## Questions?

If you have any questions, feel free to open an issue or reach out to the maintainers.

Thank you for your contributions!
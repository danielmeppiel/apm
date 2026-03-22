# Root conftest.py — shared pytest configuration
#
# Test directory structure:
#   tests/unit/          — Fast isolated unit tests (default CI scope)
#   tests/integration/   — E2E tests requiring network / external services
#   tests/acceptance/    — Acceptance criteria tests
#   tests/benchmarks/    — Performance benchmarks (excluded by default)
#   tests/test_*.py      — Root-level tests (mixed unit/integration)
#
# Quick reference:
#   uv run pytest tests/unit tests/test_console.py -x   # CI-equivalent fast run
#   uv run pytest                                         # Full suite
#   uv run pytest -m benchmark                            # Benchmarks only

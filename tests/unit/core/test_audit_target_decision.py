"""Audit intent uses current declarations without reinterpreting install defaults."""

import pytest

from apm_cli.core.target_detection import resolve_audit_target_decision

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("manifest", "recorded", "expected", "source"),
    [
        (["copilot"], ("grok-cloud",), ("copilot",), "apm.yml"),
        (None, ("grok-cloud",), ("grok-cloud",), "deployment ledger"),
        (None, ("claude", "copilot"), ("claude", "copilot"), "deployment ledger"),
        (None, (), None, "auto-detect"),
    ],
)
def test_audit_target_intent(
    manifest: list[str] | None,
    recorded: tuple[str, ...],
    expected: tuple[str, ...] | None,
    source: str,
) -> None:
    decision = resolve_audit_target_decision(manifest_target=manifest, recorded_targets=recorded)
    assert decision.canonical_targets == expected
    assert decision.source == source

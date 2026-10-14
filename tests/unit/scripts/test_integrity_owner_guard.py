"""The integrity owner guard covers ``deny_hashes`` as well as ``require_hashes`` (#3231)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.architecture_linter.runner import run_selected_rules

ROOT = Path(__file__).resolve().parents[3]
RULE_ID = "install-deployment-require-hashes-enforcement"


@pytest.mark.parametrize(
    ("path", "old", "new"),
    [
        (
            "src/apm_cli/install/pipeline.py",
            "        _enforce_deny_hashes(ctx)\n",
            "        if ctx.policy.security.integrity.deny_hashes:\n"
            "            _enforce_deny_hashes(ctx)\n",
        ),
        (
            "src/apm_cli/policy/policy_checks.py",
            "deny_hash_check = _check_content_hash_denylist(lock, policy.security.integrity)",
            "deny_hash_check = _check_content_hash_denylist(lock, policy.security.integrity)\n"
            "    _revoked = policy.security.integrity.deny_hashes",
        ),
    ],
)
def test_deny_hashes_reread_outside_owner_is_flagged(path: str, old: str, new: str) -> None:
    original = (ROOT / path).read_text(encoding="utf-8")
    assert original.count(old) == 1, f"fragment drifted in {path}: {old!r}"

    report = run_selected_rules(
        ROOT, (RULE_ID,), source_overrides={path: original.replace(old, new, 1)}
    )

    assert {v.rule_id for v in report.violations} == {RULE_ID}
    assert any("deny_hashes" in v.message for v in report.violations)

"""Mutation traps for the local rendered-write authority extension."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from scripts.architecture_linter.runner import run_selected_rules

pytestmark = pytest.mark.component
ROOT = Path(__file__).resolve().parents[2]
RULE = "install-deployment-provenance-state"


@pytest.mark.parametrize(
    ("path", "before", "after"),
    [
        (
            "core/deployment_ledger.py",
            "create_only=not self._state_present",
            "create_only=False",
        ),
        (
            "core/deployment_ledger.py",
            "self._bindings.get(key) != [record.active_owner, self._claim_signature(value)]",
            "False",
        ),
        (
            "install/pipeline.py",
            "materialization_session.bind_committed_claims(",
            "parallel_claim_binding(",
        ),
        (
            "core/deployment_ledger.py",
            'data["root_identity"] != self._root_identity()',
            "False",
        ),
        (
            "core/deployment_ledger.py",
            "record.active_owner not in self._valid_owners",
            "False",
        ),
        (
            "integration/skill_integrator.py",
            "on_member_written=written.append",
            "on_member_written=None",
        ),
        (
            "integration/skill_integrator.py",
            "session.baseline(path, targets)",
            "self._skill_recorded_hashes.get(entry(path))",
        ),
        (
            "integration/skill_integrator.py",
            "materialization_session.flush()",
            "pass",
        ),
        (
            "integration/cleanup.py",
            "DeploymentMaterializationSession.retire_removed(",
            "parallel_retirement(",
        ),
        (
            "install/drift.py",
            "from __future__ import annotations",
            "from __future__ import annotations\n"
            "from apm_cli.core.deployment_ledger import DeploymentMaterializationSession",
        ),
        (
            "install/drift.py",
            "from __future__ import annotations",
            'from __future__ import annotations\nLOCAL_BASELINE = ".apm-local"',
        ),
    ],
)
def test_receipt_guard_rejects_bypass_and_parallel_authority(
    path: str, before: str, after: str
) -> None:
    path = f"src/apm_cli/{path}"
    source = (ROOT / path).read_text(encoding="utf-8")
    assert before in source
    mutated = source.replace(before, after, 1)
    ast.parse(mutated)
    report = run_selected_rules(ROOT, {RULE}, source_overrides={path: mutated})
    assert report.failures == ()
    assert any(item.rule_id == RULE for item in report.violations)

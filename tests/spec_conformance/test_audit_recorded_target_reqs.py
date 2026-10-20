"""Recorded target replay preserves the existing governed drift contract."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from apm_cli.cli import cli
from tests.integration.test_audit_primitive_contract import project as audit_project
from tests.utils.artifact_snapshot import ArtifactSnapshot, assert_unchanged

pytestmark = pytest.mark.component
__all__ = ["audit_project"]


@pytest.mark.req("req-pl-014")
@pytest.mark.parametrize("fail_on_drift", (False, True))
def test_recorded_grok_target_preserves_governed_drift(
    audit_project: Path, monkeypatch: pytest.MonkeyPatch, fail_on_drift: bool
) -> None:
    """Unrelated discovery must not create drift or suppress actual drift."""
    (audit_project / "apm.yml").write_text(
        "name: audit-contract\nversion: 1.0.0\n", encoding="ascii"
    )
    source = audit_project / ".apm/skills/example/SKILL.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "---\nname: example\ndescription: Example.\n---\nOriginal.\n", encoding="ascii"
    )
    workflow = audit_project / ".github/workflows/unrelated.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: unrelated\n", encoding="ascii")
    runner = CliRunner()
    for args in (
        ["experimental", "enable", "grok-cloud"],
        ["install", "--target", "grok-cloud", "--no-policy", "--parallel-downloads", "0"],
    ):
        result = runner.invoke(cli, args)
        assert result.exit_code == 0, result.output
    deployed = audit_project / ".grok/skills/example/SKILL.md"
    assert deployed.read_bytes() == source.read_bytes()
    monkeypatch.setattr("apm_cli.commands.audit._resolve_fail_on_drift", lambda _: fail_on_drift)
    for damaged in (False, True):
        if damaged:
            deployed.write_text("Modified managed content.\n", encoding="ascii")
        before = ArtifactSnapshot.capture(audit_project)
        result = runner.invoke(cli, ["audit"])
        assert result.exit_code == int(damaged and fail_on_drift), result.output
        if damaged:
            assert "Drift detected: 1 file(s)" in result.output
            assert ".grok/skills/example/SKILL.md" in result.output
        else:
            assert "No drift detected" in result.output
        assert not (audit_project / ".agents/skills/example/SKILL.md").exists()
        assert_unchanged(before, ArtifactSnapshot.capture(audit_project))

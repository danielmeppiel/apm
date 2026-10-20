"""Historical audit claims retain canonical path containment."""

from pathlib import Path

import pytest

from apm_cli.integration.targets import KNOWN_TARGETS
from apm_cli.policy.ci_checks import _resolve_deployed_file_path

pytestmark = pytest.mark.component


@pytest.mark.parametrize(
    "value",
    (
        "../outside.md",
        ".grok/../../outside.md",
        ".grok/skills/../../../outside.md",
        "unmanaged/secret.md",
    ),
)
def test_historical_claim_cannot_escape_registered_roots(tmp_path: Path, value: str) -> None:
    assert _resolve_deployed_file_path(value, tmp_path, [KNOWN_TARGETS["copilot"]]) is None


def test_historical_claim_is_not_limited_to_current_replay_target(tmp_path: Path) -> None:
    path = ".grok/skills/example/SKILL.md"
    assert (
        _resolve_deployed_file_path(path, tmp_path, [KNOWN_TARGETS["copilot"]]) == tmp_path / path
    )


@pytest.mark.parametrize("directory_link", (False, True))
def test_historical_claim_cannot_follow_symlink_escape(
    tmp_path: Path, directory_link: bool
) -> None:
    project = tmp_path / "project"
    skill_root = project / ".grok/skills"
    skill_root.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    external_file = outside / "SKILL.md"
    external_file.write_text("not managed\n", encoding="ascii")
    if directory_link:
        (skill_root / "example").symlink_to(outside, target_is_directory=True)
    else:
        (skill_root / "example").mkdir()
        (skill_root / "example/SKILL.md").symlink_to(external_file)
    assert (
        _resolve_deployed_file_path(
            ".grok/skills/example/SKILL.md", project, [KNOWN_TARGETS["copilot"]]
        )
        is None
    )
    assert external_file.read_text(encoding="ascii") == "not managed\n"

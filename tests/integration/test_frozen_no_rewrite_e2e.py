"""Real-CLI contract for the --frozen under-recording failure (req-lk-006).

``apm install --frozen`` never writes the lockfile it freezes. When the
install deploys a path that ``apm.lock.yaml`` does not record, it exits 1,
names the path, and leaves the lockfile bytes untouched. Deployment has
already happened by then: only the lockfile write is withheld.

The project has no remote dependencies, so the scenario needs no network
access to resolve them (CI also sets APM_E2E_TESTS=1, which skips the
update check).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.requires_apm_binary,
]


def _add_skill(project: Path, name: str) -> None:
    skill_dir = project / ".apm" / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Frozen fixture\n---\n# {name}\n",
        encoding="utf-8",
    )


def _install(apm_binary_path: Path, project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(apm_binary_path), "install", *args],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_frozen_install_fails_on_unrecorded_skill_without_rewriting_lockfile(
    tmp_path: Path, apm_binary_path: Path
) -> None:
    project = tmp_path / "frozen-project"
    project.mkdir()
    (project / "apm.yml").write_text(
        "name: frozen-project\nversion: 1.0.0\ntarget: claude\n", encoding="utf-8"
    )
    _add_skill(project, "alpha")
    lockfile = project / "apm.lock.yaml"

    first = _install(apm_binary_path, project)
    assert first.returncode == 0, first.stdout + first.stderr
    locked = lockfile.read_bytes()

    healthy = _install(apm_binary_path, project, "--frozen")
    assert healthy.returncode == 0, healthy.stdout + healthy.stderr
    assert lockfile.read_bytes() == locked

    _add_skill(project, "beta")
    frozen = _install(apm_binary_path, project, "--frozen")
    output = frozen.stdout + frozen.stderr

    assert frozen.returncode == 1, output
    # Rich wraps long lines at the terminal width; compare with whitespace collapsed.
    flat = " ".join(output.split())
    assert (
        ".claude/skills/beta is deployed by this install but not recorded in apm.lock.yaml" in flat
    )
    assert lockfile.read_bytes() == locked
    assert (project / ".claude" / "skills" / "beta" / "SKILL.md").is_file()

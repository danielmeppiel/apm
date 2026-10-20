"""Installed-CLI regression traps for opaque native plugin cache integrity."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sysconfig
from pathlib import Path

import pytest

from apm_cli.copilot_plugins.registrar import catalog_path_for
from tests.unit.copilot_plugins._builders import write_agent_plugin

pytestmark = [pytest.mark.e2e, pytest.mark.integration]


def _snapshot(root: Path) -> dict[str, object]:
    """Include file bytes, permissions and timestamps in the read-only witness."""
    result: dict[str, object] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[relative] = ("symlink", os.readlink(path))
        elif path.is_file():
            stat = path.stat()
            result[relative] = (
                hashlib.sha256(path.read_bytes()).hexdigest(),
                stat.st_mode,
                stat.st_mtime_ns,
            )
    return result


@pytest.mark.parametrize("with_manifest", [False, True])
@pytest.mark.parametrize("tamper", ["modified", "missing"])
def test_native_cache_tamper_fails_installed_audit(
    tmp_path: Path, with_manifest: bool, tamper: str
) -> None:
    """Clean/reinstall pass; native cache drift fails without changing any input."""
    project, source, home, scratch = (
        tmp_path / name for name in ("project", "source", "home", "scratch")
    )
    for root in (project, home, scratch):
        root.mkdir()
    name = "cache-witness"
    write_agent_plugin(source, name=name, with_mcp=False)
    if with_manifest:
        (source / "apm.yml").write_text(
            json.dumps({"name": name, "version": "1.0.0"}), encoding="ascii"
        )
    (project / "apm.yml").write_text(
        json.dumps(
            {
                "name": "consumer",
                "version": "1.0.0",
                "targets": ["copilot"],
                "dependencies": {"apm": [str(source)]},
            }
        ),
        encoding="ascii",
    )
    executable = Path(sysconfig.get_path("scripts")) / ("apm.exe" if os.name == "nt" else "apm")
    assert executable.is_file(), "The test requires the installed project CLI"
    env = {
        **os.environ,
        "HOME": str(home),
        "USERPROFILE": str(home),
        "COPILOT_HOME": str(home / ".copilot"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "TMPDIR": str(scratch),
        "TMP": str(scratch),
        "TEMP": str(scratch),
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(executable), *args],
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    def audit() -> subprocess.CompletedProcess[str]:
        before = [_snapshot(root) for root in (project, source, home)]
        result = run("audit", "--no-policy", "--ci")
        assert [_snapshot(root) for root in (project, source, home)] == before
        return result

    for _ in range(2):
        installed = run("install", "--no-policy", "--target", "copilot")
        assert installed.returncode == 0, installed.stdout + installed.stderr
        clean = audit()
        assert clean.returncode == 0, clean.stdout + clean.stderr
        assert "no drift detected against lockfile" in clean.stdout

    modules = project / "apm_modules"
    (entry,) = json.loads(catalog_path_for(modules).read_text(encoding="utf-8"))["plugins"]
    materialized = modules / entry["source"]
    materialized.resolve().relative_to(modules.resolve())
    relative = Path("skills") / f"{name}-skill" / "SKILL.md"
    skill = materialized / relative
    original = (source / relative).read_bytes()
    assert skill.read_bytes() == original
    assert not (project / ".agents/skills" / f"{name}-skill").exists()
    if tamper == "modified":
        skill.write_bytes(original + b"\nModified only in native cache.\n")
    else:
        skill.unlink()

    changed = audit()
    assert changed.returncode != 0, changed.stdout + changed.stderr
    message = " ".join(changed.stdout.split())
    assert "Native Agent Plugin cache differs from its replay baseline" in message
    assert "run 'apm install' to restore the package" in message
    assert "Traceback" not in changed.stderr
    assert (source / relative).read_bytes() == original
    restored = run("install", "--no-policy", "--target", "copilot")
    assert restored.returncode == 0, restored.stdout + restored.stderr
    assert skill.read_bytes() == original
    clean = audit()
    assert clean.returncode == 0, clean.stdout + clean.stderr

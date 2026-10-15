"""Unsatisfied persisted skill selections preserve the last working deployment (#3204)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from apm_cli.utils.yaml_io import dump_yaml, load_yaml
from tests.utils.apm_lifecycle_runner import ApmLifecycleRunner
from tests.utils.isolated_apm_environment import IsolatedApmEnvironment
from tests.utils.local_package import LocalPackageFactory

pytestmark = [
    pytest.mark.integration,
    pytest.mark.e2e,
    pytest.mark.lifecycle_smoke,
    pytest.mark.requires_e2e_mode,
]


def _managed_snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for base in (root / ".claude" / "skills", root / ".agents" / "skills")
        for path in base.rglob("*")
        if path.is_file()
    }


def test_unmatched_persisted_selection_refuses_without_losing_skills(
    tmp_path: Path,
    apm_engine_command: tuple[str, ...],
) -> None:
    isolated = IsolatedApmEnvironment.create(tmp_path / "isolated", base_env=dict(os.environ))
    packages = LocalPackageFactory(isolated.work_root)
    source = packages.create("selection-source")
    for name in ("review", "lint"):
        packages.add_skill(source, name, f"---\nname: {name}\ndescription: {name}\n---\n# {name}\n")
    consumer = packages.create(
        "selection-consumer",
        targets=("claude", "copilot"),
        dependencies=({"path": "../selection-source", "skills": ["review", "lint"]},),
    )
    runner = ApmLifecycleRunner(apm_engine_command, timeout_seconds=180)
    env = isolated.subprocess_env()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")

    installed = runner.run(
        ("install", "--no-policy"),
        scenario_id="selection-initial-install",
        cwd=consumer.root,
        env=env,
    )
    assert installed.returncode == 0, (installed.stdout, installed.stderr)
    original_managed = _managed_snapshot(consumer.root)
    original_lock = (consumer.root / "apm.lock.yaml").read_bytes()
    assert len(original_managed) == 4

    manifest = load_yaml(consumer.manifest_path)
    manifest["dependencies"]["apm"][0]["skills"] = ["reveiw"]
    dump_yaml(manifest, consumer.manifest_path)
    refused = runner.run(
        ("install", "--no-policy"),
        scenario_id="selection-unmatched-refusal",
        cwd=consumer.root,
        env=env,
    )
    assert refused.returncode != 0, (refused.stdout, refused.stderr)
    output = refused.stdout + refused.stderr
    assert "selection-source" in output
    assert "reveiw" in output and "review" in output and "lint" in output
    assert _managed_snapshot(consumer.root) == original_managed
    assert (consumer.root / "apm.lock.yaml").read_bytes() == original_lock

    manifest = load_yaml(consumer.manifest_path)
    manifest["dependencies"]["apm"][0]["skills"] = ["review"]
    dump_yaml(manifest, consumer.manifest_path)
    narrowed = runner.run(
        ("install", "--no-policy"),
        scenario_id="selection-corrected-narrowing",
        cwd=consumer.root,
        env=env,
    )
    assert narrowed.returncode == 0, (narrowed.stdout, narrowed.stderr)
    assert len(_managed_snapshot(consumer.root)) == 2

    manifest = load_yaml(consumer.manifest_path)
    manifest["dependencies"]["apm"] = []
    dump_yaml(manifest, consumer.manifest_path)
    removed = runner.run(
        ("install", "--no-policy"),
        scenario_id="selection-dependency-removal",
        cwd=consumer.root,
        env=env,
    )
    assert removed.returncode == 0, (removed.stdout, removed.stderr)
    assert _managed_snapshot(consumer.root) == {}

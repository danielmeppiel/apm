"""Frozen local-path content is checked across real install lifecycles."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

from tests.utils.apm_lifecycle_runner import ApmLifecycleRunner
from tests.utils.isolated_apm_environment import IsolatedApmEnvironment
from tests.utils.local_package import LocalPackageFactory

pytestmark = [pytest.mark.integration, pytest.mark.e2e, pytest.mark.lifecycle_smoke]


def _runner() -> ApmLifecycleRunner:
    source = Path(__file__).resolve().parents[2] / "src"
    return ApmLifecycleRunner(
        (
            sys.executable,
            "-c",
            f"import sys; sys.path.insert(0, {str(source)!r}); "
            "from apm_cli.cli import cli; cli()",
        )
    )


def test_frozen_local_path_refuses_changed_snapshot_without_mutation(tmp_path: Path) -> None:
    isolated = IsolatedApmEnvironment.create(tmp_path / "local-frozen", base_env=dict(os.environ))
    factory = LocalPackageFactory(isolated.work_root)
    provider = factory.create("provider", targets=("agent-skills",))
    original = factory.add_skill(provider, "review", "---\nname: review\ndescription: fixture\n---\noriginal\n")
    consumer = factory.create(
        "consumer", dependencies=("../provider",), targets=("agent-skills",)
    )
    cold_consumer = isolated.work_root / "cold-consumer"
    cold_consumer.mkdir()
    shutil.copy2(consumer.manifest_path, cold_consumer / "apm.yml")
    runner = _runner()
    env = isolated.subprocess_env()

    def run(root: Path, *args: str):
        return runner.run(args, scenario_id=f"frozen-local-{root.name}", cwd=root, env=env)

    initial = run(consumer.root, "install", "--no-policy")
    assert initial.returncode == 0, initial.stdout + initial.stderr
    lockfile = consumer.root / "apm.lock.yaml"
    locked_bytes = lockfile.read_bytes()
    deployed = consumer.root / ".agents" / "skills" / "review" / "SKILL.md"
    deployed_bytes = deployed.read_bytes()

    # A fresh consumer uses the CLI-generated baseline and unchanged local source.
    shutil.copy2(lockfile, cold_consumer / "apm.lock.yaml")
    cold = run(cold_consumer, "install", "--frozen", "--no-policy")
    assert cold.returncode == 0, cold.stdout + cold.stderr
    assert (cold_consumer / ".agents" / "skills" / "review" / "SKILL.md").read_bytes() == deployed_bytes

    before_deployment = deployed.read_bytes()

    def assert_rejected_without_mutation() -> None:
        rejected = run(consumer.root, "install", "--frozen", "--no-policy")
        assert rejected.returncode != 0, rejected.stdout + rejected.stderr
        assert "local dependency" in rejected.stdout.lower() + rejected.stderr.lower()
        assert lockfile.read_bytes() == locked_bytes
        assert deployed.read_bytes() == before_deployment == deployed_bytes

    original.write_text("---\nname: review\ndescription: fixture\n---\nchanged\n", encoding="utf-8")
    assert_rejected_without_mutation()

    changed_cold = isolated.work_root / "changed-cold-consumer"
    changed_cold.mkdir()
    shutil.copy2(consumer.manifest_path, changed_cold / "apm.yml")
    shutil.copy2(lockfile, changed_cold / "apm.lock.yaml")
    cold_rejected = run(changed_cold, "install", "--frozen", "--no-policy")
    assert cold_rejected.returncode != 0, cold_rejected.stdout + cold_rejected.stderr
    assert "local dependency" in cold_rejected.stdout.lower() + cold_rejected.stderr.lower()
    assert not (changed_cold / ".agents").exists()
    assert (changed_cold / "apm.lock.yaml").read_bytes() == locked_bytes

    added = provider.root / "references" / "new.md"
    added.parent.mkdir()
    added.write_text("new local content\n", encoding="utf-8")
    assert_rejected_without_mutation()
    added.unlink()

    original.unlink()
    assert_rejected_without_mutation()

    # Restoring the accepted source makes the same locked frozen replay succeed.
    original.write_bytes(b"---\nname: review\ndescription: fixture\n---\noriginal\n")
    recovered = run(consumer.root, "install", "--frozen", "--no-policy")
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert lockfile.read_bytes() == locked_bytes
    assert deployed.read_bytes() == deployed_bytes

"""Real CLI lifecycle coverage for independent Claude user profiles."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from apm_cli.utils.yaml_io import dump_yaml, load_yaml
from tests.utils.apm_lifecycle_runner import ApmLifecycleRunner
from tests.utils.isolated_apm_environment import IsolatedApmEnvironment
from tests.utils.local_package import LocalPackageFactory

pytestmark = [pytest.mark.integration, pytest.mark.e2e, pytest.mark.lifecycle_smoke]


def _server(name: str, revision: int = 1) -> dict[str, Any]:
    return {
        "name": name,
        "registry": False,
        "transport": "stdio",
        "command": "python",
        "args": ["-m", "fixture_server", str(revision)],
    }


def _read_servers(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")).get("mcpServers", {})


def test_claude_user_profile_installation_is_independent_and_idempotent(
    tmp_path: Path,
) -> None:
    isolated = IsolatedApmEnvironment.create(tmp_path / "profiles", base_env=dict(os.environ))
    package = LocalPackageFactory(isolated.work_root).create(
        "claude-profile-consumer",
        mcp_dependencies=(_server("profile-server"),),
        targets=("claude",),
    )
    dump_yaml(load_yaml(package.manifest_path), isolated.config_root / "apm.yml")
    source = Path(__file__).resolve().parents[2] / "src"
    runner = ApmLifecycleRunner(
        (
            sys.executable,
            "-c",
            f"import sys; sys.path.insert(0, {str(source)!r}); from apm_cli.cli import cli; cli()",
        )
    )
    profiles = {name: isolated.root / "claude" / name for name in ("a", "b")}
    environment = isolated.subprocess_env()

    def install(profile: str):
        return runner.run(
            ("install", "--global", "--target", "claude", "--no-policy"),
            scenario_id=f"claude-profile-{profile}",
            cwd=package.root,
            env={**environment, "CLAUDE_CONFIG_DIR": str(profiles[profile])},
        )

    first_a = install("a")
    assert first_a.returncode == 0, first_a.stdout + first_a.stderr
    assert "profile-server" in _read_servers(profiles["a"] / ".claude.json")

    first_b = install("b")
    assert first_b.returncode == 0, first_b.stdout + first_b.stderr
    assert "profile-server" in _read_servers(profiles["b"] / ".claude.json")

    before_a = (profiles["a"] / ".claude.json").read_bytes()
    before_b = (profiles["b"] / ".claude.json").read_bytes()
    second_a = install("a")
    assert second_a.returncode == 0, second_a.stdout + second_a.stderr
    assert (profiles["a"] / ".claude.json").read_bytes() == before_a
    assert (profiles["b"] / ".claude.json").read_bytes() == before_b

    manifest = load_yaml(isolated.config_root / "apm.yml")
    manifest["dependencies"]["mcp"][0]["args"] = ["-m", "fixture_server", "2"]
    dump_yaml(manifest, isolated.config_root / "apm.yml")
    update_a = install("a")
    assert update_a.returncode == 0, update_a.stdout + update_a.stderr
    assert _read_servers(profiles["a"] / ".claude.json")["profile-server"]["args"][-1] == "2"
    assert (profiles["b"] / ".claude.json").read_bytes() == before_b

    profile_a_path = profiles["a"] / ".claude.json"
    profile_a_config = json.loads(profile_a_path.read_text(encoding="utf-8"))
    profile_a_config["mcpServers"]["external-server"] = {"command": "external"}
    profile_a_config["theme"] = "preserve"
    profile_a_path.write_text(json.dumps(profile_a_config), encoding="utf-8")

    manifest["dependencies"]["mcp"] = []
    dump_yaml(manifest, isolated.config_root / "apm.yml")
    remove_a = install("a")
    assert remove_a.returncode == 0, remove_a.stdout + remove_a.stderr
    assert _read_servers(profile_a_path) == {"external-server": {"command": "external"}}
    assert json.loads(profile_a_path.read_text(encoding="utf-8"))["theme"] == "preserve"
    assert (profiles["b"] / ".claude.json").read_bytes() == before_b

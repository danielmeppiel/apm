"""Installed CLI renders native OpenCode references without persisting values."""

import json
import os
from pathlib import Path

import pytest

from apm_cli.deps.lockfile import LockFile
from apm_cli.utils.yaml_io import dump_yaml
from tests.utils.apm_lifecycle_runner import ApmLifecycleRunner
from tests.utils.isolated_apm_environment import IsolatedApmEnvironment

pytestmark = [
    pytest.mark.integration,
    pytest.mark.e2e,
    pytest.mark.lifecycle_smoke,
    pytest.mark.requires_apm_binary,
    pytest.mark.requires_e2e_mode,
]


def test_installed_cli_opencode_runtime_references(tmp_path: Path, apm_binary_path: Path):
    isolated = IsolatedApmEnvironment.create(tmp_path / "scenario", base_env=dict(os.environ))
    project = isolated.work_root / "project"
    project.mkdir()
    (project / ".opencode").mkdir()
    dump_yaml(
        {
            "name": "runtime-references",
            "version": "1.0.0",
            "targets": ["opencode"],
            "dependencies": {
                "apm": [],
                "mcp": [
                    {
                        "name": "local",
                        "registry": False,
                        "transport": "stdio",
                        "command": "echo",
                        "args": ["${EXAMPLE_KEY}"],
                        "env": {"TOKEN": "${env:EXAMPLE_KEY}", "STATIC": "literal"},
                    },
                    {
                        "name": "remote",
                        "registry": False,
                        "transport": "http",
                        "url": "https://example.com/mcp",
                        "headers": {"Authorization": "Bearer ${EXAMPLE_KEY}"},
                    },
                ],
            },
        },
        project / "apm.yml",
    )
    LockFile().write(project / "apm.lock.yaml")
    environment = isolated.subprocess_env(overrides={"EXAMPLE_KEY": "synthetic-cli-secret"})
    result = ApmLifecycleRunner((str(apm_binary_path),)).run(
        ("install", "--no-policy", "--target", "opencode"),
        cwd=project,
        env=environment,
        scenario_id="opencode-runtime-references",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    written = (project / "opencode.json").read_text(encoding="utf-8")
    assert "synthetic-cli-secret" not in written
    config = json.loads(written)["mcp"]
    assert config["local"]["command"] == ["echo", "{env:EXAMPLE_KEY}"]
    assert config["local"]["environment"] == {"TOKEN": "{env:EXAMPLE_KEY}", "STATIC": "literal"}
    assert config["remote"]["headers"]["Authorization"] == "Bearer {env:EXAMPLE_KEY}"

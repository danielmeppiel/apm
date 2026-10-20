"""Preserve observed profile recovery; not a reproduction or fix of issue #3128."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from apm_cli.utils.yaml_io import dump_yaml, load_yaml
from tests.utils.apm_lifecycle_runner import ApmLifecycleRunner
from tests.utils.artifact_snapshot import ArtifactSnapshot, assert_unchanged
from tests.utils.isolated_apm_environment import IsolatedApmEnvironment
from tests.utils.local_package import LocalPackageFactory

pytestmark = [
    pytest.mark.integration,
    pytest.mark.e2e,
    pytest.mark.lifecycle_smoke,
    pytest.mark.requires_apm_binary,
]


def _read_config(path: Path) -> dict[str, Any]:
    """Read the actual destination independently of the production adapter."""
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("missing", ["entry", "file"])
@pytest.mark.parametrize(
    "flags", [(), ("--force",), ("--refresh",)], ids=["ordinary", "force", "refresh"]
)
def test_mcp_only_restores_selected_profile_without_resetting_shared_state(
    tmp_path: Path, apm_binary_path: Path, missing: str, flags: tuple[str, ...]
) -> None:
    """A retained shared lock must not hide missing selected-profile configuration."""
    isolated = IsolatedApmEnvironment.create(tmp_path / "profiles", base_env=dict(os.environ))
    sentinel = isolated.root / "unexpected-mcp-execution.txt"
    script = isolated.root / "owned_mcp_sentinel.py"
    script.write_text(
        "import sys\nfrom pathlib import Path\n"
        "Path(sys.argv[1]).write_text('unexpected MCP execution', encoding='utf-8')\n",
        encoding="utf-8",
    )
    expected_server = {
        "type": "stdio",
        "command": sys.executable,
        "args": [str(script), str(sentinel)],
    }
    package = LocalPackageFactory(isolated.work_root).create(
        "profile-recovery",
        mcp_dependencies=(
            {
                "name": "profile-server",
                "registry": False,
                "transport": "stdio",
                "command": expected_server["command"],
                "args": expected_server["args"],
            },
        ),
        targets=("claude",),
    )
    manifest = isolated.config_root / "apm.yml"
    dump_yaml(load_yaml(package.manifest_path), manifest)
    manifest_before = manifest.read_bytes()
    lock = isolated.config_root / "apm.lock.yaml"
    profiles = {name: isolated.root / "claude" / name / ".claude.json" for name in ("a", "b")}
    unrelated = {
        "mcpServers": {"user-owned": {"command": "never-execute", "args": ["preserve"]}},
        "preferences": {"nested": ["retain", 7, False]},
        "theme": "preserve",
    }
    default = isolated.home / ".claude.json"
    default.write_text(json.dumps(unrelated), encoding="utf-8")
    default_before = default.read_bytes()
    project_before = ArtifactSnapshot.capture(package.root)
    environment = isolated.subprocess_env()
    environment.pop("APM_HOME", None)
    runner = ApmLifecycleRunner((str(apm_binary_path),), timeout_seconds=60)

    def install(profile: str, extra_flags: tuple[str, ...] = ()) -> None:
        """Run the MCP-only route without touching real user or project state."""
        result = runner.run(
            ("install", "-g", "--only", "mcp", "--target", "claude", *extra_flags),
            scenario_id=f"claude-profile-{profile}-{missing}",
            cwd=package.root,
            env={**environment, "CLAUDE_CONFIG_DIR": str(profiles[profile].parent)},
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert not sentinel.exists()
        assert default.read_bytes() == default_before
        assert manifest.read_bytes() == manifest_before
        assert_unchanged(project_before, ArtifactSnapshot.capture(package.root))

    install("a")
    assert _read_config(profiles["a"]) == {"mcpServers": {"profile-server": expected_server}}
    a_before = profiles["a"].read_bytes()
    install("b")
    assert _read_config(profiles["b"]) == {"mcpServers": {"profile-server": expected_server}}
    assert profiles["a"].read_bytes() == a_before
    b_before = profiles["b"].read_bytes()
    install("a")
    assert profiles["a"].read_bytes() == a_before
    assert profiles["b"].read_bytes() == b_before
    assert load_yaml(lock)["mcp_servers"] == ["profile-server"]
    lock_before = lock.read_bytes()

    if missing == "entry":
        profiles["b"].write_text(json.dumps(unrelated), encoding="utf-8")
        expected_b = {
            **unrelated,
            "mcpServers": {**unrelated["mcpServers"], "profile-server": expected_server},
        }
    else:
        profiles["b"].unlink()
        expected_b = {"mcpServers": {"profile-server": expected_server}}
    assert lock.read_bytes() == lock_before
    assert manifest.read_bytes() == manifest_before

    install("b", flags)
    assert _read_config(profiles["b"]) == expected_b
    assert profiles["a"].read_bytes() == a_before
    recovered = profiles["b"].read_bytes()
    install("b")
    assert profiles["b"].read_bytes() == recovered
    assert profiles["a"].read_bytes() == a_before

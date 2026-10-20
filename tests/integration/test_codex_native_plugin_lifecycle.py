"""Real installed APM and qualified Codex lifecycle; no agent or MCP process runs."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest
import tomlkit

from apm_cli.models.apm_package import DependencyReference
from apm_cli.utils.content_hash import compute_package_hash
from apm_cli.utils.yaml_io import dump_yaml
from tests.utils.apm_lifecycle_runner import ApmLifecycleRunner, CommandResult

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.integration,
    pytest.mark.requires_apm_binary,
    pytest.mark.requires_runtime_codex,
]

_NATIVE_SCRIPT = """
import json, sys
from pathlib import Path
from apm_cli.codex_plugins.client import CodexNativeClient
client = CodexNativeClient(Path(sys.argv[1]), Path.cwd())
with client.connect() as rpc:
    result = rpc.call(sys.argv[2], json.loads(sys.argv[3]))
    print(json.dumps(result))
"""


def _native(codex: str, env: dict[str, str], root: Path, method: str, params: dict) -> dict:
    """Drive real public API operations with the same credential-free fixture environment."""
    result = ApmLifecycleRunner((sys.executable, "-c", _NATIVE_SCRIPT, codex)).run(
        (method, json.dumps(params)),
        cwd=root,
        env=env,
        scenario_id=method,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _native_write(codex: str, env: dict[str, str], root: Path, values: dict) -> None:
    config = _native(codex, env, root, "config/read", {"includeLayers": True})
    layer = next(layer for layer in config["layers"] if layer["name"]["type"] == "user")
    result = _native(
        codex,
        env,
        root,
        "config/batchWrite",
        {
            "expectedVersion": layer["version"],
            "edits": [
                {"keyPath": key, "value": value, "mergeStrategy": "replace"}
                for key, value in values.items()
            ],
        },
    )
    assert result["status"] == "ok"


def _apm(
    runner: ApmLifecycleRunner,
    args: tuple[str, ...],
    root: Path,
    env: dict[str, str],
    label: str,
) -> CommandResult:
    result = runner.run(args, cwd=root, env=env, scenario_id=label)
    (root / f"{label}-evidence.json").write_text(
        json.dumps(asdict(result), default=str, indent=2),
        encoding="utf-8",
    )
    return result


def _environment(root: Path) -> dict[str, str]:
    """Do not inherit credentials, native trust, or unrelated user configuration."""
    home = root / "home"
    home.mkdir()
    (home / ".codex").mkdir()
    return {
        "HOME": str(home),
        "USERPROFILE": str(home),
        "CODEX_HOME": str(home / ".codex"),
        "APM_HOME": str(home / ".apm"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "PATH": os.environ["PATH"],
        "LANG": "en_US.UTF-8",
        "NO_COLOR": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        **{key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR") if key in os.environ},
    }


def _source(root: Path, marker: str) -> None:
    """Write only inert source data, including a sentinel that must never execute."""
    (root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".codex-plugin/plugin.json").write_text(
        json.dumps(
            {
                "name": "example",
                "version": "1.0.0",
                "skills": "./skills",
                "mcpServers": "./.mcp.codex.json",
            }
        ),
        encoding="utf-8",
    )
    (root / ".mcp.codex.json").write_text(
        json.dumps({"mcpServers": {"example": {"command": "DO_NOT_EXECUTE", "args": [marker]}}}),
        encoding="utf-8",
    )
    skill = root / "skills/example/SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(
        f"---\nname: example\ndescription: Inert native fixture\n---\n{marker}\n",
        encoding="utf-8",
    )
    (root / "sibling.txt").write_text(marker, encoding="utf-8")


def test_installed_cli_registers_complete_codex_bundle_disabled(
    tmp_path: Path,
    apm_binary_path: Path,
) -> None:
    """The real install cannot claim native delivery after a skills-only projection."""
    codex = shutil.which("codex")
    if codex is None:
        pytest.skip("Codex CLI 0.163.0 is required")
    env = _environment(tmp_path)
    version = subprocess.run(
        [codex, "--version"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if version.returncode or version.stdout.strip() != "codex-cli 0.163.0":
        pytest.skip("Native evidence is qualified only for Codex CLI 0.163.0")
    source = tmp_path / "source"
    _source(source, "FIRST")
    apm_home = Path(env["APM_HOME"])
    apm_home.mkdir()
    reference = DependencyReference.parse(str(source))
    dump_yaml(
        {
            "name": "consumer",
            "version": "1.0.0",
            "targets": ["codex"],
            "dependencies": {"apm": [str(source)]},
            "allowExecutables": {str(reference): {"mcp": True}},
        },
        apm_home / "apm.yml",
    )
    runner = ApmLifecycleRunner((str(apm_binary_path),))
    result = _apm(
        runner,
        ("install", "-g", "--target", "codex", "--no-policy"),
        tmp_path,
        env,
        "codex-native-first",
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    config_path = Path(env["CODEX_HOME"]) / "config.toml"
    assert config_path.is_file(), result.stdout
    config = tomlkit.parse(config_path.read_text()).unwrap()
    owned = [key for key in config.get("plugins", {}) if key.startswith("example@apm-")]
    assert len(owned) == 1
    assert config["plugins"][owned[0]] == {"enabled": False}
    assert not list((Path(env["HOME"]) / ".agents/skills").glob("*"))
    assert all(path.name == ".system" for path in (Path(env["HOME"]) / ".codex/skills").glob("*"))
    ledger = apm_home / ".codex-native/ownership.json"
    original_ledger = ledger.read_bytes()
    record = next(iter(json.loads(original_ledger)["plugins"].values()))
    installed = Path(record["installed_root"])
    assert compute_package_hash(installed) == compute_package_hash(source)
    detail = _native(
        codex,
        env,
        tmp_path,
        "plugin/read",
        {
            "marketplacePath": record["marketplace_path"],
            "pluginName": "example",
        },
    )["plugin"]
    assert detail["mcpServers"] == ["example"]
    assert detail["summary"]["enabled"] is False
    _native_write(
        codex,
        env,
        tmp_path,
        {
            f'plugins."{owned[0]}".mcp_servers.example.enabled': False,
            'plugins."foreign@external"': {"enabled": False},
            "model": "gpt-5.3-codex",
        },
    )
    managed_config = config_path.read_bytes()
    result = _apm(
        runner,
        ("install", "-g", "--frozen", "--target", "codex", "--no-policy"),
        tmp_path,
        env,
        "codex-native-frozen-noop",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert ledger.read_bytes() == original_ledger
    assert config_path.read_bytes() == managed_config

    for label, method, params in (
        (
            "corrupt",
            "fs/writeFile",
            {
                "path": str(installed / "sibling.txt"),
                "dataBase64": base64.b64encode(b"CORRUPTED").decode(),
            },
        ),
        ("missing", "fs/remove", {"path": str(installed), "recursive": True, "force": False}),
    ):
        _native(codex, env, tmp_path, method, params)
        assert compute_package_hash(installed) != compute_package_hash(source)
        before = next(iter(json.loads(ledger.read_bytes())["plugins"].values()))
        result = _apm(
            runner,
            ("install", "-g", "--frozen", "--target", "codex", "--no-policy"),
            tmp_path,
            env,
            f"codex-native-{label}-restore",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        after = next(iter(json.loads(ledger.read_bytes())["plugins"].values()))
        assert after["snapshot"]["content_commit"] == before["snapshot"]["content_commit"]
        assert after["snapshot"]["catalog_commit"] != before["snapshot"]["catalog_commit"]
        assert compute_package_hash(Path(after["installed_root"])) == compute_package_hash(source)
        state = tomlkit.parse(config_path.read_text()).unwrap()
        assert state["plugins"][owned[0]] == {
            "enabled": False,
            "mcp_servers": {"example": {"enabled": False}},
        }
        assert state["plugins"]["foreign@external"] == {"enabled": False}
        assert state["model"] == "gpt-5.3-codex"

    publisher_manifest = (source / ".codex-plugin/plugin.json").read_bytes()
    _source(source, "SAME_VERSION_CHANGED_BYTES")
    result = _apm(
        runner,
        ("install", "-g", "--update", "--target", "codex", "--no-policy"),
        tmp_path,
        env,
        "codex-native-same-version-update",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    record = next(iter(json.loads(ledger.read_bytes())["plugins"].values()))
    assert compute_package_hash(Path(record["installed_root"])) == compute_package_hash(source)
    assert (source / ".codex-plugin/plugin.json").read_bytes() == publisher_manifest
    assert tomlkit.parse(config_path.read_text()).unwrap()["plugins"][owned[0]]["enabled"] is False
    manifest_before = (apm_home / "apm.yml").read_bytes()
    native_before = config_path.read_bytes()
    result = _apm(
        runner,
        ("uninstall", "-g", str(source)),
        tmp_path,
        env,
        "codex-native-customized-retained",
    )
    assert result.returncode != 0, result.stdout
    assert "user-managed settings" in result.stdout + result.stderr
    assert (apm_home / "apm.yml").read_bytes() == manifest_before
    assert config_path.read_bytes() == native_before
    assert Path(record["installed_root"]).is_dir()

    # The fixture operator explicitly retires its custom policy before asking APM to remove.
    _native_write(codex, env, tmp_path, {f'plugins."{owned[0]}"': {"enabled": False}})
    result = _apm(
        runner,
        ("uninstall", "-g", str(source)),
        tmp_path,
        env,
        "codex-native-owned-removal",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    state = tomlkit.parse(config_path.read_text()).unwrap()
    assert owned[0] not in state.get("plugins", {})
    assert state["plugins"]["foreign@external"] == {"enabled": False}
    assert state["model"] == "gpt-5.3-codex"
    assert not Path(record["installed_root"]).exists()
    assert json.loads(ledger.read_bytes())["plugins"] == {}

"""Contained hook aliases retain the source Node module and resource semantics."""

import json
import os
import shlex
import shutil
from pathlib import Path

import pytest

from apm_cli.deps.lockfile import LockFile
from tests.integration.test_hook_nested_module_lifecycle_contract import (
    _AUDIT,
    _BUNDLE,
    _INSTALL,
    _NAME,
    _UPDATE,
    _audit,
    _node_source,
    _record,
    _run,
    _Scenario,
    _scenario,
    _write_json,
)
from tests.utils.apm_lifecycle_runner import ApmLifecycleRunner

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.integration,
    pytest.mark.requires_apm_binary,
    pytest.mark.skipif(os.name == "nt", reason="POSIX source alias fixture"),
    pytest.mark.skipif(shutil.which("node") is None, reason="Node runtime required"),
]


def _execute_alias(
    scenario: _Scenario, relative: str, mode: str, revision: int, *, source: bool = False
) -> None:
    """Run only the owned source alias or the CLI-generated deployed command."""
    environment = scenario.environment.copy()
    if source:
        script = scenario.repository.worktree / "hooks/entry.js"
        environment["APM_2950_TRACE"] = str(scenario.log.parent / "source-node.jsonl")
    else:
        config = json.loads((scenario.project / ".claude/settings.json").read_text())
        [entry] = config["hooks"]["SessionStart"]
        [hook] = entry["hooks"]
        argv = shlex.split(hook["command"].replace("${CLAUDE_PROJECT_DIR}", str(scenario.project)))
        assert len(argv) == 2 and argv[0] == "node"
        script = scenario.project / argv[1]
        assert script.absolute().is_relative_to(scenario.project / _BUNDLE.parent)
    result = ApmLifecycleRunner((scenario.node,), timeout_seconds=15).run(
        (str(script),), cwd=scenario.project, env=environment
    )
    _record(scenario, result)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {
        "label": relative,
        "revision": revision,
        "mode": mode,
        "resource": f"resource-v{revision}\n",
    }


@pytest.mark.parametrize("relative,mode", [("root.js", "commonjs"), ("esm/entry.js", "module")])
@pytest.mark.parametrize("reference", ["plugin", "relative"])
def test_internal_script_alias_and_resource_survive_lifecycle(
    tmp_path: Path, apm_binary_path: Path, relative: str, mode: str, reference: str
) -> None:
    scenario = _scenario(tmp_path / "internal-alias", apm_binary_path)
    hooks = scenario.repository.worktree / "hooks"
    (hooks / "entry.js").symlink_to(relative)
    resource = (hooks / relative).parent / "resource.txt"
    resource.rename(resource.with_name("real-resource.txt"))
    resource.symlink_to("real-resource.txt")
    _write_json(
        hooks / "hooks.json",
        {
            "hooks": {
                "SessionStart": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": (
                                    'node "${CLAUDE_PLUGIN_ROOT}/hooks/entry.js"'
                                    if reference == "plugin"
                                    else 'node "./entry.js"'
                                ),
                            }
                        ]
                    }
                ]
            }
        },
    )
    scenario.repositories.commit(scenario.repository, message="add owned internal aliases")
    _execute_alias(scenario, relative, mode, 1, source=True)
    _run(scenario, _INSTALL)
    assert not (scenario.project / _BUNDLE).exists()
    _run(scenario, ("approve", _NAME))
    _run(scenario, _INSTALL)
    installed = scenario.project / "apm_modules/nested-module-fixture/hooks"
    assert (installed / "entry.js").is_symlink()
    assert ((installed / relative).parent / "resource.txt").is_symlink()
    _execute_alias(scenario, relative, mode, 1)
    lock = LockFile.read(scenario.project / "apm.lock.yaml")
    assert lock is not None
    [dependency] = lock.get_package_dependencies()
    bundle = _BUNDLE if reference == "plugin" else _BUNDLE.parent
    deployed_resource = (bundle / Path(relative).parent / "resource.txt").as_posix()
    assert deployed_resource in dependency.deployed_files
    assert deployed_resource in dependency.deployed_file_hashes
    _run(scenario, _INSTALL)
    _execute_alias(scenario, relative, mode, 1)
    result, _report = _audit(scenario)
    assert result.returncode == 0, result.stdout + result.stderr

    (hooks / relative).write_text(_node_source(mode, relative, 2), encoding="utf-8")
    resource.with_name("real-resource.txt").write_text("resource-v2\n", encoding="utf-8")
    scenario.repositories.commit(scenario.repository, message="update owned alias target")
    _run(scenario, _UPDATE)
    _execute_alias(scenario, relative, mode, 2)
    _run(scenario, _INSTALL)
    _execute_alias(scenario, relative, mode, 2)
    _run(scenario, _AUDIT)

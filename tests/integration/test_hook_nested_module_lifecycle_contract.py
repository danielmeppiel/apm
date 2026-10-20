"""Installed-CLI and owned Node fixtures for issue #2950's two contracts."""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import pytest

from apm_cli.deps.lockfile import LockFile
from apm_cli.utils.yaml_io import dump_yaml, load_yaml
from tests.utils.apm_lifecycle_runner import ApmLifecycleRunner, CommandResult
from tests.utils.artifact_snapshot import ArtifactSnapshot
from tests.utils.isolated_apm_environment import IsolatedApmEnvironment
from tests.utils.lifecycle_state import LifecycleStateSnapshot
from tests.utils.local_git_repository import LocalGitRepository, LocalGitRepositoryFactory
from tests.utils.local_package import LocalPackageFactory

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.integration,
    pytest.mark.requires_apm_binary,
    pytest.mark.skipif(shutil.which("node") is None, reason="Node runtime required"),
]

_NAME = "nested-module-fixture"
_REMOTE = f"https://gitlab.example.invalid/apm-fixtures/{_NAME}.git"
_BUNDLE = PurePosixPath(f".claude/hooks/{_NAME}/hooks")
_INSTALL = ("install", "--parallel-downloads", "0")
_UPDATE = ("update", "--yes", "--parallel-downloads", "0")
_AUDIT = ("audit", "--ci", "--no-fail-fast", "--format", "json")


@dataclass
class _Scenario:
    """One bounded source repository and consumer, without external credentials."""

    project: Path
    repository: LocalGitRepository
    repositories: LocalGitRepositoryFactory
    environment: dict[str, str]
    runner: ApmLifecycleRunner
    node: str
    trace: Path
    npm_trace: Path
    log: Path
    source_type: str | None


def _write_json(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8", newline="\n")


def _manifest(module_type: str) -> dict[str, object]:
    """Extra fields distinguish generated minimal metadata from manifest copying."""
    lifecycle = (
        "node -e \"require('node:fs').appendFileSync("
        "process.env.APM_2950_NPM_TRACE, 'unexpected')\""
    )
    return {
        "type": module_type,
        "name": "source-manifest-not-deployable",
        "private": True,
        "dependencies": {"must-not-install-fixture": "0.0.0"},
        "scripts": dict.fromkeys(("preinstall", "install", "postinstall", "prepare"), lifecycle),
    }


def _modes(source_type: str | None, revision: int) -> dict[str, str]:
    root_type = source_type or "commonjs"
    return {
        "root.js": root_type,
        "esm/entry.js": "module" if revision == 1 else "commonjs",
        "cjs/entry.js": "commonjs" if revision == 1 else "module",
        "deep/lib/entry.js": (
            ("commonjs" if root_type == "module" else "module") if revision == 1 else root_type
        ),
        "control.mjs": "module",
    }


def _node_source(mode: str, label: str, revision: int) -> str:
    imports = (
        'import { appendFileSync, readFileSync } from "node:fs";\n'
        'const resource = new URL("./resource.txt", import.meta.url);\n'
        'const actualMode = typeof require === "undefined" ? "module" : "wrong";\n'
        if mode == "module"
        else 'const { appendFileSync, readFileSync } = require("node:fs");\n'
        'const resource = require("node:path").join(__dirname, "resource.txt");\n'
        'const actualMode = typeof module.exports === "object" ? "commonjs" : "wrong";\n'
    )
    return (
        imports + f"const result = {{ label: {json.dumps(label)}, revision: {revision}, "
        'mode: actualMode, resource: readFileSync(resource, "utf8") };\n'
        'appendFileSync(process.env.APM_2950_TRACE, JSON.stringify(result) + "\\n");\n'
        "console.log(JSON.stringify(result));\n"
    )


def _write_source(root: Path, source_type: str | None, revision: int) -> None:
    if source_type is not None:
        _write_json(root / "package.json", _manifest(source_type))
    hooks = root / "hooks"
    modes = _modes(source_type, revision)
    for relative, mode in modes.items():
        script = hooks / relative
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(_node_source(mode, relative, revision), encoding="utf-8", newline="\n")
        (script.parent / "resource.txt").write_text(
            f"resource-v{revision}\n", encoding="utf-8", newline="\n"
        )
    for boundary in ("esm", "cjs"):
        _write_json(hooks / boundary / "package.json", _manifest(modes[f"{boundary}/entry.js"]))
    deep_metadata = hooks / "deep" / "package.json"
    if revision == 1:
        _write_json(deep_metadata, _manifest(modes["deep/lib/entry.js"]))
    else:
        deep_metadata.unlink()
    _write_json(
        hooks / "hooks.json",
        {
            "hooks": {
                "SessionStart": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": f'node "${{CLAUDE_PLUGIN_ROOT}}/hooks/{relative}"',
                            }
                            for relative in modes
                        ]
                    }
                ]
            }
        },
    )


def _scenario(
    root: Path,
    binary: Path,
    *,
    consumer_type: str = "module",
    source_type: str | None = "commonjs",
    minimal_nested_metadata: bool = False,
) -> _Scenario:
    node = shutil.which("node")
    assert node is not None, "Node is required: file-only checks do not qualify issue #2950"
    isolated = IsolatedApmEnvironment.create(root, base_env=dict(os.environ))
    repositories = LocalGitRepositoryFactory(
        isolated.repository_root, env=isolated.subprocess_env()
    )
    source = LocalPackageFactory(isolated.package_root).create(_NAME)
    (source.root / ".apm").mkdir()
    (source.root / ".apm/.gitkeep").write_text("", encoding="utf-8")
    _write_source(source.root, source_type, 1)
    if minimal_nested_metadata:
        for boundary in ("esm", "cjs", "deep"):
            metadata = source.root / "hooks" / boundary / "package.json"
            _write_json(metadata, {"type": json.loads(metadata.read_text())["type"]})
    repository = repositories.create(_NAME, source_tree=source.root)
    repositories.commit(repository, message="seed owned nested module fixtures")
    environment = repositories.url_rewrite_subprocess_env(repository, _REMOTE)
    # Node's syntax-detection/loader settings must not come from the operator.
    environment.pop("NODE_OPTIONS", None)
    environment.pop("NODE_PATH", None)
    trace, npm_trace = root / "node-executions.jsonl", root / "npm-executions.txt"
    environment.update(APM_2950_TRACE=str(trace), APM_2950_NPM_TRACE=str(npm_trace))
    consumer = LocalPackageFactory(isolated.work_root).create(
        "consumer",
        dependencies=({"git": _REMOTE, "type": "gitlab", "ref": "main", "alias": _NAME},),
        targets=("claude",),
    )
    manifest = load_yaml(consumer.manifest_path)
    manifest["executables"] = {"allow": {}}
    dump_yaml(manifest, consumer.manifest_path)
    _write_json(consumer.root / "package.json", {"type": consumer_type})
    user_file = consumer.root / ".claude" / "user-owned.txt"
    user_file.parent.mkdir()
    user_file.write_text("keep user content\n", encoding="utf-8")
    return _Scenario(
        consumer.root,
        repository,
        repositories,
        environment,
        ApmLifecycleRunner((str(binary),), timeout_seconds=90),
        node,
        trace,
        npm_trace,
        root / "commands.jsonl",
        source_type,
    )


def _trace_bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def _record(scenario: _Scenario, result: CommandResult) -> None:
    with scenario.log.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "command": result.command,
                    "cwd": str(result.cwd),
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            )
            + "\n"
        )


def _run(scenario: _Scenario, args: tuple[str, ...], *, success: bool = True) -> CommandResult:
    before = (_trace_bytes(scenario.trace), _trace_bytes(scenario.npm_trace))
    result = scenario.runner.run(args, cwd=scenario.project, env=scenario.environment)
    _record(scenario, result)
    assert (_trace_bytes(scenario.trace), _trace_bytes(scenario.npm_trace)) == before, (
        "An APM command executed a hook or npm lifecycle script"
    )
    if success:
        assert result.returncode == 0, f"{result.command}\n{result.stdout}\n{result.stderr}"
    return result


def _install(scenario: _Scenario) -> None:
    _run(scenario, _INSTALL)
    assert not (scenario.project / _BUNDLE).exists(), "Unapproved hooks were deployed"
    _run(scenario, ("approve", _NAME))
    _run(scenario, _INSTALL)
    assert (scenario.project / _BUNDLE / "root.js").is_file()
    assert not scenario.trace.exists()
    assert not scenario.npm_trace.exists()
    assert not list(scenario.project.rglob("node_modules"))


def _execute(scenario: _Scenario, revision: int) -> None:
    document = json.loads((scenario.project / ".claude/settings.json").read_text(encoding="utf-8"))
    commands = [
        hook["command"] for entry in document["hooks"]["SessionStart"] for hook in entry["hooks"]
    ]
    modes = _modes(scenario.source_type, revision)
    assert len(commands) == len(modes), commands
    seen = set()
    for command in commands:
        argv = shlex.split(command.replace("${CLAUDE_PROJECT_DIR}", str(scenario.project)))
        assert len(argv) == 2 and argv[0] == "node", argv
        script = (scenario.project / argv[1]).resolve()
        bundle = (scenario.project / _BUNDLE).resolve()
        assert script.is_relative_to(bundle), argv
        relative = script.relative_to(bundle).as_posix()
        assert relative in modes, relative
        seen.add(relative)
        result = ApmLifecycleRunner((scenario.node,), timeout_seconds=15).run(
            (str(script),), cwd=scenario.project, env=scenario.environment
        )
        _record(scenario, result)
        assert result.returncode == 0, f"{result.command}\n{result.stdout}\n{result.stderr}"
        expected = {
            "label": relative,
            "revision": revision,
            "mode": modes[relative],
            "resource": f"resource-v{revision}\n",
        }
        assert json.loads(result.stdout) == expected
        assert json.loads(scenario.trace.read_text(encoding="utf-8").splitlines()[-1]) == expected
        assert not scenario.npm_trace.exists()
    assert seen == set(modes)


def _state(scenario: _Scenario) -> LifecycleStateSnapshot:
    return LifecycleStateSnapshot.capture(
        scenario.project,
        targets=("claude",),
        config_paths=(PurePosixPath("package.json"), PurePosixPath(".claude/user-owned.txt")),
    )


def _audit(scenario: _Scenario, *, no_drift: bool = False) -> tuple[CommandResult, dict]:
    before = ArtifactSnapshot.capture(scenario.project)
    permissions = {
        path.relative_to(scenario.project).as_posix(): path.stat().st_mode
        for path in scenario.project.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    result = _run(scenario, (*_AUDIT, *(("--no-drift",) if no_drift else ())), success=False)
    after = ArtifactSnapshot.capture(scenario.project)
    assert after == before, before.diff(after)
    assert {
        path.relative_to(scenario.project).as_posix(): path.stat().st_mode
        for path in scenario.project.rglob("*")
        if path.is_file() and not path.is_symlink()
    } == permissions
    return result, json.loads(result.stdout)


@pytest.mark.parametrize("consumer_type", ["module", "commonjs"])
@pytest.mark.parametrize("source_type", ["module", "commonjs", None], ids=["esm", "cjs", "default"])
def test_node_nested_modes_survive_install_reinstall_update(
    tmp_path: Path, apm_binary_path: Path, consumer_type: str, source_type: str | None
) -> None:
    """Execute the deployed commands, not source scripts or an in-process integrator."""
    scenario = _scenario(
        tmp_path / "runtime", apm_binary_path, consumer_type=consumer_type, source_type=source_type
    )
    _install(scenario)
    original_source = ArtifactSnapshot.capture(scenario.repository.worktree)
    _execute(scenario, 1)
    before = _state(scenario)
    _run(scenario, _INSTALL)
    assert _state(scenario) == before
    _execute(scenario, 1)
    assert ArtifactSnapshot.capture(scenario.repository.worktree) == original_source
    old_lock = LockFile.read(scenario.project / "apm.lock.yaml")
    assert old_lock is not None

    _write_source(scenario.repository.worktree, source_type, 2)
    commit = scenario.repositories.commit(scenario.repository, message="change nested module modes")
    updated_source = ArtifactSnapshot.capture(scenario.repository.worktree)
    _run(scenario, _UPDATE)
    lock = LockFile.read(scenario.project / "apm.lock.yaml")
    assert lock is not None
    [dependency] = lock.get_package_dependencies()
    assert dependency.resolved_commit == commit.sha
    [old_dependency] = old_lock.get_package_dependencies()
    assert dependency.resolved_commit != old_dependency.resolved_commit
    _execute(scenario, 2)
    removed = (_BUNDLE / "deep/package.json").as_posix()
    assert not (scenario.project / removed).exists()
    assert removed not in dependency.deployed_files
    assert removed not in dependency.deployed_file_hashes
    before = _state(scenario)
    _run(scenario, _INSTALL)
    assert _state(scenario) == before
    _execute(scenario, 2)
    assert ArtifactSnapshot.capture(scenario.repository.worktree) == updated_source
    assert (scenario.project / ".claude/user-owned.txt").read_text() == "keep user content\n"


@pytest.mark.parametrize("phase", ["install", "reinstall", "update"])
def test_generated_metadata_is_minimal_and_owned(
    tmp_path: Path, apm_binary_path: Path, phase: str
) -> None:
    """Metadata fidelity must not be achieved by copying the source npm manifest."""
    scenario = _scenario(tmp_path / "metadata", apm_binary_path)
    _install(scenario)
    revision = 1
    if phase == "update":
        revision = 2
        _write_source(scenario.repository.worktree, scenario.source_type, revision)
        scenario.repositories.commit(scenario.repository, message="update metadata fixture")
        _run(scenario, _UPDATE)
    elif phase == "reinstall":
        _run(scenario, _INSTALL)
    lock = LockFile.read(scenario.project / "apm.lock.yaml")
    assert lock is not None
    [dependency] = lock.get_package_dependencies()
    modes = _modes(scenario.source_type, revision)
    boundaries = {"": modes["root.js"], "esm": modes["esm/entry.js"], "cjs": modes["cjs/entry.js"]}
    if revision == 1:
        boundaries["deep"] = modes["deep/lib/entry.js"]
    problems = {}
    for boundary, expected in boundaries.items():
        relative = (_BUNDLE / boundary / "package.json").as_posix()
        path = scenario.project / relative
        assert path.is_file(), relative
        actual = json.loads(path.read_text(encoding="utf-8"))
        if actual != {"type": expected}:
            problems[relative] = {"type": actual.get("type"), "fields": sorted(actual)}
        assert relative in dependency.deployed_files
        assert dependency.deployed_file_hashes[relative] == (
            "sha256:" + hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        )
        assert any(
            record.locator.value == relative for record in lock.deployment_ledger.records.values()
        )
    assert not problems, f"Full source manifests escaped minimal metadata generation: {problems}"


@pytest.mark.parametrize("no_drift", [False, True], ids=["replay", "classification"])
def test_valid_module_metadata_audits_clean_without_execution(
    tmp_path: Path, apm_binary_path: Path, no_drift: bool
) -> None:
    """Supporting metadata must not require a native hook container."""
    scenario = _scenario(tmp_path / "clean-audit", apm_binary_path, minimal_nested_metadata=True)
    _install(scenario)
    _execute(scenario, 1)
    result, report = _audit(scenario, no_drift=no_drift)
    assert result.returncode == 0, report
    assert report["passed"] is True
    content = next(check for check in report["checks"] if check["name"] == "content-integrity")
    assert content["passed"] is True, content
    assert content["details"] == []


def test_install_replay_agrees_on_unchanged_module_metadata(
    tmp_path: Path, apm_binary_path: Path
) -> None:
    """Expose replay divergence separately from content classification."""
    scenario = _scenario(tmp_path / "replay-parity", apm_binary_path)
    _install(scenario)
    _result, report = _audit(scenario)
    drift = next(check for check in report["checks"] if check["name"] == "drift")
    assert drift["passed"] is True, drift
    assert report["drift"]["drift"] == []


@pytest.mark.parametrize("asset", ["package.json", "esm/package.json", "esm/entry.js"])
@pytest.mark.parametrize("change", ["modify", "delete"])
def test_real_managed_changes_fail_nonmutating_audit(
    tmp_path: Path, apm_binary_path: Path, asset: str, change: str
) -> None:
    """Assert the specific drift failure, not an unrelated metadata false positive."""
    scenario = _scenario(tmp_path / "drift", apm_binary_path)
    _install(scenario)
    relative = (_BUNDLE / asset).as_posix()
    path = scenario.project / relative
    if change == "delete":
        path.unlink()
    elif asset.endswith("package.json"):
        mode = json.loads(path.read_text())["type"]
        _write_json(path, {"type": "commonjs" if mode == "module" else "module"})
    else:
        path.write_text("// meaningful managed script change\n", encoding="utf-8")
    result, report = _audit(scenario)
    assert result.returncode != 0, report
    checks = {check["name"]: check for check in report["checks"]}
    check_name = "deployed-files-present" if change == "delete" else "content-integrity"
    check = checks[check_name]
    assert check["passed"] is False, check
    if change == "delete":
        assert relative in check["details"], check
    else:
        assert any(detail.startswith(f"hash-drift: {relative} ") for detail in check["details"]), (
            check
        )
    assert checks["drift"]["passed"] is False, checks["drift"]
    assert any(relative in detail for detail in checks["drift"]["details"]), checks["drift"]


@pytest.mark.parametrize("relative", [".claude/settings.json", ".claude/hooks/package.json"])
def test_malformed_hook_definitions_are_not_metadata_exemptions(
    tmp_path: Path, apm_binary_path: Path, relative: str
) -> None:
    """Even a JSON file named package.json cannot hide an invalid actual hook."""
    scenario = _scenario(tmp_path / "malformed", apm_binary_path)
    _install(scenario)
    _write_json(scenario.project / relative, {"hooks": {"SessionStart": "invalid"}})
    result, report = _audit(scenario, no_drift=True)
    assert result.returncode != 0, report
    content = next(check for check in report["checks"] if check["name"] == "content-integrity")
    assert any(
        detail.startswith(f"incomplete-coverage: {relative}") for detail in content["details"]
    ), content


def test_unmanaged_metadata_collision_is_preserved(tmp_path: Path, apm_binary_path: Path) -> None:
    scenario = _scenario(tmp_path / "collision", apm_binary_path)
    _run(scenario, _INSTALL)
    _run(scenario, ("approve", _NAME))
    relative = (_BUNDLE / "esm/package.json").as_posix()
    path = scenario.project / relative
    _write_json(path, {"type": "commonjs", "user_owned": True})
    before = path.read_bytes()
    result = _run(scenario, _INSTALL, success=False)
    assert path.read_bytes() == before, result.stdout + result.stderr
    lock = LockFile.read(scenario.project / "apm.lock.yaml")
    assert lock is not None
    [dependency] = lock.get_package_dependencies()
    assert relative not in dependency.deployed_files
    assert "not managed by APM" in " ".join(result.stdout.split())


def test_explicit_denial_never_deploys_or_executes_hooks(
    tmp_path: Path, apm_binary_path: Path
) -> None:
    scenario = _scenario(tmp_path / "denied", apm_binary_path)
    _run(scenario, _INSTALL)
    _run(scenario, ("deny", _NAME))
    _run(scenario, _INSTALL)
    assert not (scenario.project / _BUNDLE).exists()
    assert not scenario.trace.exists()
    assert not scenario.npm_trace.exists()


@pytest.mark.skipif(
    os.name == "nt", reason="POSIX symlink fixture; no Windows privilege assumption"
)
def test_symlinked_metadata_cannot_be_read_outside_selected_package(
    tmp_path: Path, apm_binary_path: Path
) -> None:
    """A skipped source symlink must not reenter through a second metadata scan."""
    scenario = _scenario(tmp_path / "containment", apm_binary_path)
    outside = tmp_path / "owned-outside-package.json"
    _write_json(outside, {"type": "module", "private": "outside-owned-fixture"})
    hooks = scenario.repository.worktree / "hooks"
    boundary = hooks / "escape"
    boundary.mkdir()
    (boundary / "entry.js").write_text("// owned containment fixture\n", encoding="utf-8")
    (boundary / "package.json").symlink_to(outside)
    scenario.repositories.commit(scenario.repository, message="add bounded symlink fixture")
    before = outside.read_bytes()
    _install(scenario)
    assert outside.read_bytes() == before
    assert not (scenario.project / _BUNDLE / "escape/package.json").exists()

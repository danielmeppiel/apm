"""Producer regressions for relocatable, discoverable Claude plugin hooks."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from apm_cli.bundle.plugin_exporter import export_plugin_bundle
from apm_cli.deps.lockfile import LockedDependency, LockFile
from apm_cli.models.apm_package import clear_apm_yml_cache
from apm_cli.utils.yaml_io import dump_yaml, load_yaml
from tests.utils.local_package import LocalPackageFactory

pytestmark = pytest.mark.component


@pytest.fixture
def hook_project(tmp_path: Path) -> Path:
    """Author the two independent hook-resource failures from issue #3074."""
    factory = LocalPackageFactory(tmp_path)
    package = factory.create("demo", version="1.0.0")
    for name, event, relative in (
        ("skill", "Stop", ".apm/skills/demo/scripts/check.py"),
        ("script", "PostToolUse", "scripts/other.py"),
    ):
        factory.add_hook(
            package,
            name,
            {
                "hooks": {
                    event: [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": f'python3 "${{CLAUDE_PLUGIN_ROOT}}/{relative}"',
                                    "timeout": 30,
                                }
                            ]
                        }
                    ]
                }
            },
        )
    for relative, content in {
        ".apm/skills/demo/SKILL.md": "---\nname: demo\ndescription: Demo\n---\n# Demo\n",
        ".apm/skills/demo/scripts/check.py": 'raise RuntimeError("must not execute")\n',
        ".apm/hooks/scripts/other.py": 'raise RuntimeError("must not execute")\n',
        ".apm/hooks/scripts/support.txt": "support data\n",
    }.items():
        path = package.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return package.root


def test_pack_relocates_skill_command_and_preserves_hook_assets(hook_project: Path) -> None:
    result = export_plugin_bundle(hook_project, hook_project / "dist")
    hooks = json.loads((result.bundle_path / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    assert hooks["Stop"][0]["hooks"][0] == {
        "type": "command",
        "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/skills/demo/scripts/check.py"',
        "timeout": 30,
    }
    assert hooks["PostToolUse"][0]["hooks"][0]["command"] == (
        'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/other.py"'
    )
    assert (result.bundle_path / "hooks/scripts/other.py").read_bytes() == (
        hook_project / ".apm/hooks/scripts/other.py"
    ).read_bytes()
    assert (result.bundle_path / "hooks/scripts/support.txt").read_text() == "support data\n"
    assert "hooks/scripts/support.txt" in result.files
    assert not (result.bundle_path / "hooks/script.json").exists()
    assert not (result.bundle_path / ".apm").exists()


def test_pack_declares_hooks_in_native_claude_manifest(hook_project: Path) -> None:
    result = export_plugin_bundle(hook_project, hook_project / "dist")
    manifest = json.loads(
        (result.bundle_path / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
    )
    assert manifest["hooks"] == "./hooks.json"
    assert json.loads((result.bundle_path / manifest["hooks"]).read_text())["hooks"].keys() == {
        "Stop",
        "PostToolUse",
    }
    assert json.loads((result.bundle_path / "plugin.json").read_text()) == manifest
    assert not (result.bundle_path / "hooks/hooks.json").exists()


def test_pack_dry_run_lists_hook_resources_without_writing(hook_project: Path) -> None:
    result = export_plugin_bundle(hook_project, hook_project / "dist", dry_run=True)
    assert {
        "hooks/scripts/other.py",
        "hooks/scripts/support.txt",
        "hooks.json",
        ".claude-plugin/plugin.json",
    } <= set(result.files)
    assert not result.bundle_path.exists()


@pytest.mark.parametrize("reference", ["missing.py", "../outside.py", "scripts/linked.py"])
def test_pack_rejects_unavailable_hook_resource_before_replacing_output(
    hook_project: Path, reference: str
) -> None:
    outside = hook_project.parent / "outside.py"
    outside.write_text("not publishable", encoding="utf-8")
    (hook_project / ".apm/hooks/scripts/linked.py").symlink_to(outside)
    descriptor = hook_project / ".apm/hooks/script.json"
    descriptor.write_text(
        json.dumps(
            {"hooks": {"Stop": [{"command": f'python "${{CLAUDE_PLUGIN_ROOT}}/{reference}"'}]}}
        ),
        encoding="utf-8",
    )
    output = hook_project / "dist/demo-1.0.0"
    output.mkdir(parents=True)
    (output / "keep.txt").write_text("previous bundle", encoding="utf-8")
    with pytest.raises(ValueError, match=r"(?i)hook.*(resource|path|script)"):
        export_plugin_bundle(hook_project, output.parent)
    assert (output / "keep.txt").read_text() == "previous bundle"


def test_explicit_includes_require_referenced_assets(hook_project: Path) -> None:
    manifest = load_yaml(hook_project / "apm.yml")
    manifest["includes"] = [".apm/hooks/script.json"]
    dump_yaml(manifest, hook_project / "apm.yml")
    with pytest.raises(ValueError, match="includes"):
        export_plugin_bundle(hook_project, hook_project / "dist")

    manifest["includes"].append(".apm/hooks/scripts")
    dump_yaml(manifest, hook_project / "apm.yml")
    clear_apm_yml_cache()
    result = export_plugin_bundle(hook_project, hook_project / "dist")
    assert (result.bundle_path / "hooks/scripts/other.py").is_file()
    assert not (result.bundle_path / "skills").exists()


@pytest.mark.parametrize("exclude_metadata", [False, True])
def test_hook_bundle_preserves_node_module_type(hook_project: Path, exclude_metadata: bool) -> None:
    (hook_project / ".apm/hooks/package.json").write_text(
        '{"type":"module","scripts":{"postinstall":"must-not-run"}}', encoding="utf-8"
    )
    descriptor = hook_project / ".apm/hooks/script.json"
    descriptor.write_text(
        '{"hooks":{"Stop":[{"command":"node ${CLAUDE_PLUGIN_ROOT}/scripts/other.js"}]}}',
        encoding="utf-8",
    )
    (hook_project / ".apm/hooks/scripts/other.js").write_text(
        'import "./helper.js";\n', encoding="utf-8"
    )
    (hook_project / ".apm/hooks/scripts/helper.js").write_text(
        'throw new Error("must not run");\n', encoding="utf-8"
    )
    if exclude_metadata:
        manifest = load_yaml(hook_project / "apm.yml")
        manifest["includes"] = [".apm/hooks/script.json", ".apm/hooks/scripts"]
        dump_yaml(manifest, hook_project / "apm.yml")
        with pytest.raises(ValueError, match="includes"):
            export_plugin_bundle(hook_project, hook_project / "dist")
        assert not (hook_project / "dist/demo-1.0.0").exists()
        return
    result = export_plugin_bundle(hook_project, hook_project / "dist")
    assert (result.bundle_path / "hooks/package.json").read_bytes() == (
        hook_project / ".apm/hooks/package.json"
    ).read_bytes()
    assert (result.bundle_path / "hooks/scripts/helper.js").is_file()
    assert set(json.loads((result.bundle_path / "hooks.json").read_text())) == {"hooks"}


def test_root_native_hooks_keep_paths_and_use_descriptor_relative_fallback(
    hook_project: Path,
) -> None:
    shutil.move(hook_project / ".apm/hooks", hook_project / "hooks")
    shutil.move(hook_project / ".apm/skills", hook_project / "skills")
    (hook_project / ".apm").rmdir()
    descriptor = hook_project / "hooks/skill.json"
    descriptor.write_text(
        descriptor.read_text().replace("/.apm/skills/", "/skills/"), encoding="utf-8"
    )
    result = export_plugin_bundle(hook_project, hook_project / "dist")
    hooks = json.loads((result.bundle_path / "hooks.json").read_text())["hooks"]
    assert hooks["Stop"][0]["hooks"][0]["command"] == (
        'python3 "${CLAUDE_PLUGIN_ROOT}/skills/demo/scripts/check.py"'
    )
    assert hooks["PostToolUse"][0]["hooks"][0]["command"] == (
        'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/other.py"'
    )
    assert (result.bundle_path / "hooks/scripts/support.txt").is_file()


def test_hook_resource_reference_does_not_override_apm_source_authority(hook_project: Path) -> None:
    root_skill = hook_project / "skills/private/run.py"
    root_skill.parent.mkdir(parents=True)
    root_skill.write_text("not for publication", encoding="utf-8")
    descriptor = hook_project / ".apm/hooks/script.json"
    descriptor.write_text(
        '{"hooks":{"Stop":[{"command":"python ${CLAUDE_PLUGIN_ROOT}/skills/private/run.py"}]}}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="selected layout"):
        export_plugin_bundle(hook_project, hook_project / "dist")


def test_split_quoted_root_and_multiple_flat_command_fields(hook_project: Path) -> None:
    descriptor = hook_project / ".apm/hooks/script.json"
    command = 'python "${CLAUDE_PLUGIN_ROOT}"/scripts/other.py'
    descriptor.write_text(
        json.dumps({"hooks": {"custom/event~name": [{"bash": command, "powershell": command}]}}),
        encoding="utf-8",
    )
    result = export_plugin_bundle(hook_project, hook_project / "dist")
    entry = json.loads((result.bundle_path / "hooks.json").read_text())["hooks"][
        "custom/event~name"
    ]
    assert entry == [
        {
            "bash": 'python "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/other.py"',
            "powershell": 'python "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/other.py"',
        }
    ]


@pytest.mark.parametrize("name", ["check file.py", "check;file.py"])
def test_hook_relocation_preserves_authored_shell_escapes(hook_project: Path, name: str) -> None:
    source = hook_project / ".apm/hooks/scripts" / name
    source.write_text("raise RuntimeError('must not run')", encoding="utf-8")
    escaped = name.replace(" ", "\\ ").replace(";", "\\;")
    (hook_project / ".apm/hooks/script.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "PostToolUse": [
                        {"command": f"python ${{CLAUDE_PLUGIN_ROOT}}/scripts/{escaped}"}
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    result = export_plugin_bundle(hook_project, hook_project / "dist")
    command = json.loads((result.bundle_path / "hooks.json").read_text())["hooks"]["PostToolUse"][
        0
    ]["command"]
    assert command == f"python ${{CLAUDE_PLUGIN_ROOT}}/hooks/scripts/{escaped}"
    assert (result.bundle_path / "hooks/scripts" / name).read_bytes() == source.read_bytes()


def test_dependency_collision_cannot_substitute_a_first_party_hook_resource(
    hook_project: Path,
) -> None:
    deployed = hook_project / ".claude/hooks/scripts/other.py"
    deployed.parent.mkdir(parents=True)
    deployed.write_text("different dependency script", encoding="utf-8")
    lockfile = LockFile()
    lockfile.add_dependency(
        LockedDependency(
            repo_url="acme/hook-dependency",
            deployed_files=[".claude/hooks/scripts/other.py"],
        )
    )
    lockfile.write(hook_project / "apm.lock.yaml")
    with pytest.raises(ValueError, match="Hook resource collision"):
        export_plugin_bundle(hook_project, hook_project / "dist")
    result = export_plugin_bundle(hook_project, hook_project / "dist", force=True)
    assert (result.bundle_path / "hooks/scripts/other.py").read_bytes() == (
        hook_project / ".apm/hooks/scripts/other.py"
    ).read_bytes()
    packed_lock = load_yaml(result.bundle_path / "apm.lock.yaml")
    assert {
        ".claude-plugin/plugin.json",
        "hooks.json",
        "hooks/scripts/other.py",
        "hooks/scripts/support.txt",
    } <= packed_lock["pack"]["bundle_files"].keys()

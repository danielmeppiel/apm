"""Selected module inputs and narrow audit applicability share bundle semantics."""

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from apm_cli.install.deployable_source_plan import DeployableSourcePlan
from apm_cli.integration.hook_integrator import HookIntegrator
from apm_cli.integration.targets import KNOWN_TARGETS
from apm_cli.models.apm_package import APMPackage, PackageInfo
from apm_cli.security.file_scanner import scan_project_result

pytestmark = pytest.mark.component


def _package(root: Path) -> PackageInfo:
    """Create root and deep declarations without executable external content."""
    hooks = root / "hooks"
    (hooks / "nested/lib").mkdir(parents=True)
    (root / "package.json").write_text('{"type":"module","private":true}\n')
    (hooks / "nested/package.json").write_text('{"type":"commonjs","private":true}\n')
    (hooks / "nested/lib/entry.js").write_text("module.exports = {};\n")
    (hooks / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "node ${CLAUDE_PLUGIN_ROOT}/hooks/nested/lib/entry.js",
                                }
                            ]
                        }
                    ]
                }
            }
        )
    )
    return PackageInfo(
        package=APMPackage(name="fixture", version="1.0.0", source="owner/fixture"),
        install_path=root,
    )


def _plan(package: PackageInfo, target: str = "claude") -> DeployableSourcePlan:
    return DeployableSourcePlan.create(
        package,
        [KNOWN_TARGETS[target]],
        skill_subset=None,
        hooks_approved=True,
        canvas_approved=False,
        skip_bin=True,
    )


def test_root_and_deep_metadata_are_selected_before_materialization(tmp_path: Path) -> None:
    package = _package(tmp_path / "source")
    plan = _plan(package)
    assert {"package.json", "hooks/nested/package.json"} <= plan.paths
    project = tmp_path / "project"
    project.mkdir()
    result = HookIntegrator().integrate_hooks_for_target(
        KNOWN_TARGETS["claude"], package, project, source_plan=plan
    )
    root = project / ".claude/hooks/source/hooks"
    assert json.loads((root / "package.json").read_text()) == {"type": "module"}
    assert json.loads((root / "nested/package.json").read_text()) == {"type": "commonjs"}
    assert root / "nested/package.json" in result.target_paths


def test_metadata_excluded_by_source_plan_cannot_influence_generation(tmp_path: Path) -> None:
    package = _package(tmp_path / "source")
    selected = _plan(package)
    plan = replace(
        selected,
        paths=selected.paths - {"package.json", "hooks/nested/package.json"},
        authorized_parent_prefixes=frozenset(),
    )
    project = tmp_path / "project"
    project.mkdir()
    HookIntegrator().integrate_hooks_for_target(
        KNOWN_TARGETS["claude"], package, project, source_plan=plan
    )
    root = project / ".claude/hooks/source/hooks"
    assert json.loads((root / "package.json").read_text()) == {"type": "commonjs"}
    assert not (root / "nested/package.json").exists()


def test_recursive_json_target_does_not_select_module_inputs(tmp_path: Path) -> None:
    package = _package(tmp_path / "source")
    plan = _plan(package, "copilot")
    assert "package.json" not in plan.paths
    assert "hooks/nested/package.json" not in plan.paths
    assert "hooks/nested/lib/entry.js" in plan.paths


@pytest.mark.parametrize("relative", ["package.json", "hooks/nested/package.json"])
@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink fixture")
def test_symlinked_module_inputs_are_not_selected(tmp_path: Path, relative: str) -> None:
    package = _package(tmp_path / "source")
    outside = tmp_path / "outside.json"
    outside.write_text('{"type":"module"}\n')
    source = package.install_path / relative
    source.unlink()
    source.symlink_to(outside)
    assert relative not in _plan(package).paths
    project = tmp_path / "project"
    project.mkdir()
    HookIntegrator().integrate_package_hooks_claude(package, project)
    root = project / ".claude/hooks/source/hooks"
    if relative == "package.json":
        assert json.loads((root / "package.json").read_text()) == {"type": "commonjs"}
    else:
        assert not (root / "nested/package.json").exists()


@pytest.mark.parametrize(
    "target,relative,document,accepted",
    [
        ("claude", "hooks/fixture/hooks/package.json", '{"type":"module"}', True),
        ("claude", "hooks/fixture/hooks/package.json", '{"type":"commonjs"}', True),
        ("claude", "hooks/fixture/hooks/package.json", '{"type":"module","private":true}', False),
        ("claude", "hooks/fixture/hooks/package.json", '{"type":[]}', False),
        ("claude", "hooks/fixture/hooks/package.json", '{"type":"invalid"}', False),
        (
            "claude",
            "hooks/fixture/hooks/package.json",
            '{"type":"module","hooks":{"SessionStart":"invalid"}}',
            False,
        ),
        (
            "claude",
            "hooks/fixture/hooks/package.json",
            '{"type":"module","type":"commonjs"}',
            False,
        ),
        ("claude", "hooks/fixture/hooks/other.json", '{"type":"module"}', False),
        ("claude", "settings.json", '{"type":"module","hooks":{"SessionStart":"invalid"}}', False),
        ("copilot", "hooks/fixture/package.json", '{"type":"module"}', False),
    ],
)
def test_only_exact_supporting_metadata_is_not_a_hook_container(
    tmp_path: Path, target: str, relative: str, document: str, accepted: bool
) -> None:
    profile = KNOWN_TARGETS[target]
    path = profile.deploy_path(tmp_path) / relative
    path.parent.mkdir(parents=True)
    path.write_text(document)
    before = path.read_bytes()
    result = scan_project_result(tmp_path, targets=[profile])
    entries = [
        entry for entry in result.inventory if entry.file == path.relative_to(tmp_path).as_posix()
    ]
    assert entries
    assert {entry.status for entry in entries} == (
        {"not-applicable"} if accepted else {"incomplete"}
    )
    assert path.read_bytes() == before

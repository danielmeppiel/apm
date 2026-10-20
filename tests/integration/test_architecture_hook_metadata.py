"""Hook metadata cannot bypass selection, containment, or content applicability."""

from pathlib import Path

import pytest

from scripts.architecture_linter.runner import run_selected_rules

pytestmark = pytest.mark.component

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "rule,path,old,new",
    [
        (
            "install-deployment-source-plan",
            "src/apm_cli/deps/github_downloader.py",
            "symlinks=True,",
            "symlinks=False,",
        ),
        (
            "install-deployment-source-plan",
            "src/apm_cli/integration/hook_source_selection.py",
            "iter_hook_root_metadata(package_path, source_root)",
            "bypass_metadata_selection(package_path, source_root)",
        ),
        (
            "install-deployment-source-plan",
            "src/apm_cli/integration/hook_bundle.py",
            "_is_safe_source_path(package_json, package_path)",
            "bypass_metadata_containment(package_json, package_path)",
        ),
        (
            "install-deployment-source-plan",
            "src/apm_cli/integration/hook_bundle.py",
            "source_plan.includes(portable_relpath(path, source_plan.source_root))",
            "source_plan.bypass_includes(portable_relpath(path, source_plan.source_root))",
        ),
        (
            "install-deployment-source-plan",
            "src/apm_cli/integration/hook_bundle.py",
            "    metadata_plan: dict[str, str] = {}",
            '    list(package_path.rglob("package.json"))\n    metadata_plan: dict[str, str] = {}',
        ),
        (
            "audit-primitive-discovery",
            "src/apm_cli/security/file_scanner.py",
            "is_minimal_hook_module_metadata(document)",
            "bypass_metadata_classification(document)",
        ),
    ],
)
def test_metadata_owner_routes_are_guarded(rule: str, path: str, old: str, new: str) -> None:
    baseline = run_selected_rules(ROOT, {rule})
    assert baseline.failures == ()
    assert baseline.violations == ()
    source = (ROOT / path).read_text(encoding="utf-8")
    assert old in source
    report = run_selected_rules(ROOT, {rule}, source_overrides={path: source.replace(old, new, 1)})
    assert report.failures == ()
    assert any(item.rule_id == rule and item.path == path for item in report.violations)

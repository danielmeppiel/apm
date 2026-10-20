"""Static mutation witnesses for root source-binding and frozen delegation."""

import ast
from pathlib import Path

import pytest

from scripts.architecture_linter.runner import run_selected_rules

pytestmark = pytest.mark.component
ROOT = Path(__file__).resolve().parents[2]
RULE = "contracts-tooling-source-replacements"
FROZEN_RULE = "install-deployment-frozen-mutation-eligibility"


@pytest.mark.parametrize(
    ("path", "old", "new"),
    [
        (
            "src/apm_cli/models/dependency/replacement.py",
            "return (self.host, self.port, self.repo_url, self.subpath)",
            "return ('github.com', None, self.repo_url, self.subpath)",
        ),
        (
            "src/apm_cli/models/dependency/replacement.py",
            "if not self._rules or dep.replacement is not None:",
            "if not self._rules:",
        ),
        (
            "src/apm_cli/models/dependency/replacement.py",
            "binding.record(dep, parent, is_dev)",
            "binding.record(dep, None, is_dev)",
        ),
        (
            "src/apm_cli/deps/apm_resolver.py",
            "build_replacement_index(root_package.replace_rules or [])",
            "build_replacement_index([])",
        ),
        (
            "src/apm_cli/deps/apm_resolver.py",
            "            dep_ref = self.replacement_index.bind(\n",
            "            unused = self.replacement_index.bind(\n",
        ),
        (
            "src/apm_cli/deps/apm_resolver.py",
            "                        sub_dep = self.replacement_index.bind(\n",
            "                        queued_keys.add(sub_dep.get_resolution_key())\n"
            "                        sub_dep = self.replacement_index.bind(\n",
        ),
        (
            "src/apm_cli/models/dependency/reference.py",
            "return self.replacement.original.get_unique_key()",
            "return self.source_reference.get_unique_key()",
        ),
        (
            "src/apm_cli/models/dependency/materialization.py",
            "    dependency = dependency.ownership_reference\n",
            "",
        ),
        (
            "src/apm_cli/models/dependency/reference.py",
            "        return build_canonical_dependency_string(\n",
            "        if self.replacement is not None:\n"
            "            return self.ownership_reference.get_canonical_dependency_string()\n"
            "        return build_canonical_dependency_string(\n",
        ),
        (
            "src/apm_cli/deps/immutable_requirements.py",
            "self._resolver.resolve_git_reference(dep.source_reference)",
            "self._resolver.resolve_git_reference(dep.ownership_reference)",
        ),
        (
            "src/apm_cli/install/pipeline.py",
            "dep = dep.source_reference",
            "dep = dep.ownership_reference",
        ),
        (
            "src/apm_cli/install/helpers/ref_reuse.py",
            "locked.matches_replacement(dep_ref)",
            "True",
        ),
        (
            "src/apm_cli/install/helpers/ref_seed.py",
            "seed(selected.source_reference, ref, sha)",
            "seed(selected.ownership_reference, ref, sha)",
        ),
        (
            "src/apm_cli/install/native_plugin_admission.py",
            "if lock_dep.is_local_source:",
            'if lock_dep.source == "local":',
        ),
    ],
)
def test_source_replacement_guard_rejects_owner_bypasses(path: str, old: str, new: str) -> None:
    source = (ROOT / path).read_text(encoding="utf-8")
    assert old in source
    mutated = source.replace(old, new, 1)
    ast.parse(mutated, filename=path)
    report = run_selected_rules(ROOT, (RULE,), source_overrides={path: mutated})
    assert report.failures == ()
    assert any(violation.rule_id == RULE for violation in report.violations)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("if not replacements_satisfied:", "if False:"),
        (
            "InstallService._verify_frozen_local_content(request, lockfile, manifest_deps)",
            "None",
        ),
    ],
)
def test_frozen_replacement_guard_rejects_preflight_bypasses(old: str, new: str) -> None:
    path = "src/apm_cli/install/service.py"
    source = (ROOT / path).read_text(encoding="utf-8")
    assert source.count(old) == 1
    mutated = source.replace(old, new, 1)
    ast.parse(mutated, filename=path)
    report = run_selected_rules(ROOT, (FROZEN_RULE,), source_overrides={path: mutated})
    assert report.failures == ()
    assert any(violation.rule_id == FROZEN_RULE for violation in report.violations)

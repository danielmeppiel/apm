"""Guard original dependency ownership and root-owned source substitution."""

from __future__ import annotations

import ast

from scripts.architecture_linter.checks.contracts_dependency_policy import _unique_definitions
from scripts.architecture_linter.checks.contracts_test_shared import _summary
from scripts.architecture_linter.facts import FactsProvider
from scripts.architecture_linter.groups.common import checked_facts
from scripts.architecture_linter.models import Rule, Violation

RULE = "contracts-tooling-source-replacements"
OWNER = "src/apm_cli/models/dependency/replacement.py"
RESOLVER = "src/apm_cli/deps/apm_resolver.py"


def _binding_order(provider: FactsProvider) -> list[Violation]:
    """Require root, dev and transitive assignments before queue deduplication."""
    facts, failures = checked_facts(provider, RESOLVER, RULE, require_python=True)
    findings = list(failures)
    if facts is None or facts.tree_index is None:
        return list(findings)
    function = facts.tree_index.function("APMDependencyResolver.build_dependency_tree")
    if function is None:
        return [*findings, _summary(RULE, RESOLVER, "Missing canonical dependency-tree builder")]
    loops = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.For)
        and isinstance(node.target, ast.Name)
        and node.target.id in {"dep_ref", "sub_dep"}
    ]
    invalid = len(loops) != 3
    for loop in loops:
        bindings = [
            node
            for node in ast.walk(loop)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == loop.target.id
                for target in node.targets
            )
            and isinstance(node.value, ast.Call)
            and ast.unparse(node.value.func) == "self.replacement_index.bind"
        ]
        lookups = [
            node.lineno
            for node in ast.walk(loop)
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == f"{loop.target.id}.get_resolution_key"
        ]
        invalid |= len(bindings) != 1 or (
            bool(lookups) and bool(bindings) and bindings[0].lineno >= min(lookups)
        )
    if invalid:
        findings.append(
            _summary(RULE, RESOLVER, "Bind every original requirement before queue deduplication")
        )
    return list(findings)


def check_source_replacements(provider: FactsProvider) -> tuple[Violation, ...]:
    """Keep source selection in its typed owner and consumers on clean projections."""
    findings = _unique_definitions(
        provider,
        RULE,
        OWNER,
        ("ReplacementIndex", "parse_replace_block", "project_effective_reference"),
    )
    required = {
        OWNER: (
            "return (self.host, self.port, self.repo_url, self.subpath)",
            "self._by_key.get(ReplacementSelector.from_reference(dep).key)",
            "if not self._rules or dep.replacement is not None:",
            "binding.record(dep, parent, is_dev)",
        ),
        RESOLVER: (
            "build_replacement_index(root_package.replace_rules or [])",
            "if sub_dep.replacement is not None or queue_key not in queued_keys:",
        ),
        "src/apm_cli/models/dependency/reference.py": (
            "return self.replacement.original.get_unique_key()",
        ),
        "src/apm_cli/deps/immutable_requirements.py": (
            "self._resolver.resolve_git_reference(dep.source_reference)",
        ),
        "src/apm_cli/install/pipeline.py": ("dep = dep.source_reference",),
        "src/apm_cli/install/helpers/ref_reuse.py": (
            "locked.matches_replacement(dep_ref)",
            "dep_ref = dep_ref.source_reference",
        ),
        "src/apm_cli/install/helpers/ref_seed.py": ("seed(selected.source_reference, ref, sha)",),
        "src/apm_cli/install/native_plugin_admission.py": ("if lock_dep.is_local_source:",),
    }
    for path, needles in required.items():
        facts, failures = checked_facts(provider, path, RULE, require_python=True)
        findings.extend(failures)
        text = "\n".join(facts.lines) if facts is not None else ""
        if facts is not None and any(needle not in text for needle in needles):
            findings.append(
                _summary(
                    RULE,
                    path,
                    "Preserve original ownership and canonical selected-source projection",
                )
            )
    path = "src/apm_cli/models/dependency/materialization.py"
    facts, failures = checked_facts(provider, path, RULE, require_python=True)
    findings.extend(failures)
    if facts is not None and facts.tree_index is not None:
        function = facts.tree_index.function("build_materialization_path")
        if function is None or "dependency = dependency.ownership_reference" not in ast.unparse(
            function
        ):
            findings.append(_summary(RULE, path, "Materialization must use original ownership"))
    findings.extend(_binding_order(provider))
    path = "src/apm_cli/models/dependency/reference.py"
    facts, failures = checked_facts(provider, path, RULE, require_python=True)
    findings.extend(failures)
    if facts is not None and facts.tree_index is not None:
        function = facts.tree_index.function("DependencyReference.get_canonical_dependency_string")
        if function is None or any(
            isinstance(node, ast.Attribute) and node.attr in {"ownership_reference", "replacement"}
            for node in ast.walk(function)
        ):
            findings.append(_summary(RULE, path, "Policy matching must use selected source fields"))
    return tuple(findings)


RULES = (
    Rule(
        id=RULE,
        group="contracts_tests",
        guard_ids=(RULE,),
        description="Root source bindings preserve exact identity and selected-source boundaries.",
        check=check_source_replacements,
    ),
)

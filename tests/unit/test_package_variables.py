"""Tests for package variable substitution (${var:...})."""

import pytest
from pathlib import Path

from apm_cli.utils.variables import (
    PackageVariable,
    parse_package_variables,
    parse_consumer_overrides,
    resolve_package_variables,
    substitute_variables,
    find_unresolved_variables,
    is_substitutable_file,
    substitute_variables_in_directory,
    VAR_PATTERN,
)


# ---------------------------------------------------------------------------
# VAR_PATTERN regex
# ---------------------------------------------------------------------------

class TestVarPattern:
    def test_matches_simple_name(self):
        assert VAR_PATTERN.search("${var:stack-profile}")

    def test_matches_underscore(self):
        assert VAR_PATTERN.search("${var:my_var}")

    def test_matches_digits(self):
        assert VAR_PATTERN.search("${var:var123}")

    def test_no_match_input_namespace(self):
        assert not VAR_PATTERN.search("${input:prompt}")

    def test_no_match_empty_name(self):
        assert not VAR_PATTERN.search("${var:}")

    def test_no_match_spaces(self):
        assert not VAR_PATTERN.search("${var:has space}")


# ---------------------------------------------------------------------------
# parse_package_variables
# ---------------------------------------------------------------------------

class TestParsePackageVariables:
    def test_none_input(self):
        assert parse_package_variables(None) == {}

    def test_empty_dict(self):
        assert parse_package_variables({}) == {}

    def test_shorthand_string(self):
        result = parse_package_variables({"stack": "react"})
        assert result["stack"].default == "react"
        assert result["stack"].required is False

    def test_full_object(self):
        result = parse_package_variables({
            "stack": {
                "description": "Stack profile",
                "default": "react",
                "required": False,
            }
        })
        assert result["stack"].description == "Stack profile"
        assert result["stack"].default == "react"
        assert result["stack"].required is False

    def test_required_no_default(self):
        result = parse_package_variables({
            "stack": {
                "description": "Stack profile",
                "required": True,
            }
        })
        assert result["stack"].required is True
        assert result["stack"].default is None

    def test_mixed_formats(self):
        result = parse_package_variables({
            "simple": "value",
            "complex": {"default": "other", "description": "desc"},
        })
        assert len(result) == 2
        assert result["simple"].default == "value"
        assert result["complex"].default == "other"

    def test_ignores_invalid_types(self):
        result = parse_package_variables({"bad": 42})
        assert result == {}


# ---------------------------------------------------------------------------
# parse_consumer_overrides
# ---------------------------------------------------------------------------

class TestParseConsumerOverrides:
    def test_none_input(self):
        assert parse_consumer_overrides(None) == {}

    def test_empty_dict(self):
        assert parse_consumer_overrides({}) == {}

    def test_single_package_override(self):
        result = parse_consumer_overrides({
            "tdd-development": {"stack-profile": "stack-ios-swift"}
        })
        assert result["tdd-development"]["stack-profile"] == "stack-ios-swift"

    def test_multiple_packages(self):
        result = parse_consumer_overrides({
            "pkg-a": {"var1": "val1"},
            "pkg-b": {"var2": "val2"},
        })
        assert len(result) == 2
        assert result["pkg-a"]["var1"] == "val1"
        assert result["pkg-b"]["var2"] == "val2"

    def test_coerces_non_string_values(self):
        result = parse_consumer_overrides({
            "pkg": {"num": 42, "flag": True}
        })
        assert result["pkg"]["num"] == "42"
        assert result["pkg"]["flag"] == "True"

    def test_ignores_non_dict_package_overrides(self):
        result = parse_consumer_overrides({"pkg": "not-a-dict"})
        assert result == {}


# ---------------------------------------------------------------------------
# resolve_package_variables
# ---------------------------------------------------------------------------

class TestResolvePackageVariables:
    def test_consumer_override_wins(self):
        pkg_vars = {"stack": PackageVariable(default="react")}
        consumer = {"my-pkg": {"stack": "ios-swift"}}
        resolved, warnings, errors = resolve_package_variables("my-pkg", pkg_vars, consumer)
        assert resolved["stack"] == "ios-swift"
        assert not warnings
        assert not errors

    def test_default_used_when_no_override(self):
        pkg_vars = {"stack": PackageVariable(default="react")}
        resolved, warnings, errors = resolve_package_variables("my-pkg", pkg_vars, {})
        assert resolved["stack"] == "react"
        assert not warnings
        assert not errors

    def test_required_no_default_no_override_errors(self):
        pkg_vars = {"stack": PackageVariable(required=True)}
        resolved, warnings, errors = resolve_package_variables("my-pkg", pkg_vars, {})
        assert "stack" not in resolved
        assert len(errors) == 1
        assert "Required variable" in errors[0]

    def test_no_default_not_required_warns(self):
        pkg_vars = {"stack": PackageVariable()}
        resolved, warnings, errors = resolve_package_variables("my-pkg", pkg_vars, {})
        assert "stack" not in resolved
        assert len(warnings) == 1
        assert "unresolved" in warnings[0]
        assert not errors

    def test_consumer_override_for_undeclared_variable(self):
        pkg_vars = {}
        consumer = {"my-pkg": {"extra-var": "value"}}
        resolved, _, _ = resolve_package_variables("my-pkg", pkg_vars, consumer)
        assert resolved["extra-var"] == "value"

    def test_scoped_by_package_name(self):
        pkg_vars = {"stack": PackageVariable(default="react")}
        consumer = {"other-pkg": {"stack": "ios"}}
        resolved, _, _ = resolve_package_variables("my-pkg", pkg_vars, consumer)
        assert resolved["stack"] == "react"  # other-pkg override does not apply

    def test_multiple_variables(self):
        pkg_vars = {
            "stack": PackageVariable(default="react"),
            "lang": PackageVariable(default="typescript"),
        }
        consumer = {"pkg": {"stack": "ios-swift"}}
        resolved, _, _ = resolve_package_variables("pkg", pkg_vars, consumer)
        assert resolved["stack"] == "ios-swift"
        assert resolved["lang"] == "typescript"


# ---------------------------------------------------------------------------
# substitute_variables
# ---------------------------------------------------------------------------

class TestSubstituteVariables:
    def test_single_substitution(self):
        content = "Invoke skill: `${var:stack-profile}`"
        result = substitute_variables(content, {"stack-profile": "ios-swift"})
        assert result == "Invoke skill: `ios-swift`"

    def test_multiple_substitutions(self):
        content = "${var:a} and ${var:b}"
        result = substitute_variables(content, {"a": "X", "b": "Y"})
        assert result == "X and Y"

    def test_unresolved_left_as_is(self):
        content = "${var:missing}"
        result = substitute_variables(content, {"other": "value"})
        assert result == "${var:missing}"

    def test_empty_variables_dict(self):
        content = "${var:name}"
        result = substitute_variables(content, {})
        assert result == "${var:name}"

    def test_no_variables_in_content(self):
        content = "Plain text with no variables"
        result = substitute_variables(content, {"key": "value"})
        assert result == content

    def test_variable_in_yaml_frontmatter(self):
        content = "---\nskills:\n  - ${var:stack-profile}\n---\nBody text"
        result = substitute_variables(content, {"stack-profile": "react-app"})
        assert "react-app" in result
        assert "${var:stack-profile}" not in result

    def test_same_variable_multiple_times(self):
        content = "${var:name} is ${var:name}"
        result = substitute_variables(content, {"name": "foo"})
        assert result == "foo is foo"

    def test_does_not_substitute_input_vars(self):
        content = "${input:prompt} ${var:name}"
        result = substitute_variables(content, {"name": "X", "prompt": "Y"})
        assert result == "${input:prompt} X"

    def test_hyphen_in_variable_name(self):
        content = "${var:my-var}"
        result = substitute_variables(content, {"my-var": "value"})
        assert result == "value"

    def test_underscore_in_variable_name(self):
        content = "${var:my_var}"
        result = substitute_variables(content, {"my_var": "value"})
        assert result == "value"


# ---------------------------------------------------------------------------
# find_unresolved_variables
# ---------------------------------------------------------------------------

class TestFindUnresolvedVariables:
    def test_no_variables(self):
        assert find_unresolved_variables("plain text") == []

    def test_finds_variables(self):
        content = "${var:a} text ${var:b}"
        result = find_unresolved_variables(content)
        assert set(result) == {"a", "b"}

    def test_finds_single(self):
        assert find_unresolved_variables("${var:name}") == ["name"]


# ---------------------------------------------------------------------------
# is_substitutable_file
# ---------------------------------------------------------------------------

class TestIsSubstitutableFile:
    @pytest.mark.parametrize("suffix", [".md", ".yml", ".yaml", ".json", ".toml", ".txt"])
    def test_text_files(self, suffix):
        assert is_substitutable_file(Path(f"file{suffix}"))

    @pytest.mark.parametrize("suffix", [".py", ".png", ".exe", ".bin", ".zip"])
    def test_non_text_files(self, suffix):
        assert not is_substitutable_file(Path(f"file{suffix}"))

    def test_case_insensitive(self):
        assert is_substitutable_file(Path("FILE.MD"))


# ---------------------------------------------------------------------------
# substitute_variables_in_directory
# ---------------------------------------------------------------------------

class TestSubstituteVariablesInDirectory:
    def test_substitutes_in_md_files(self, tmp_path):
        (tmp_path / "SKILL.md").write_text("Skill: ${var:name}", encoding="utf-8")
        modified = substitute_variables_in_directory(tmp_path, {"name": "react"})
        assert modified == 1
        assert (tmp_path / "SKILL.md").read_text(encoding="utf-8") == "Skill: react"

    def test_skips_non_text_files(self, tmp_path):
        (tmp_path / "script.py").write_text("${var:name}", encoding="utf-8")
        modified = substitute_variables_in_directory(tmp_path, {"name": "react"})
        assert modified == 0
        assert "${var:name}" in (tmp_path / "script.py").read_text(encoding="utf-8")

    def test_no_variables_returns_zero(self, tmp_path):
        (tmp_path / "SKILL.md").write_text("No variables here", encoding="utf-8")
        modified = substitute_variables_in_directory(tmp_path, {"name": "react"})
        assert modified == 0

    def test_empty_variables_returns_zero(self, tmp_path):
        (tmp_path / "SKILL.md").write_text("${var:name}", encoding="utf-8")
        modified = substitute_variables_in_directory(tmp_path, {})
        assert modified == 0

    def test_recursive_subdirectories(self, tmp_path):
        sub = tmp_path / "refs"
        sub.mkdir()
        (sub / "ref.md").write_text("Use ${var:tool}", encoding="utf-8")
        modified = substitute_variables_in_directory(tmp_path, {"tool": "pytest"})
        assert modified == 1
        assert "pytest" in (sub / "ref.md").read_text(encoding="utf-8")

    def test_multiple_files(self, tmp_path):
        (tmp_path / "a.md").write_text("${var:x}", encoding="utf-8")
        (tmp_path / "b.yml").write_text("key: ${var:x}", encoding="utf-8")
        (tmp_path / "c.py").write_text("${var:x}", encoding="utf-8")
        modified = substitute_variables_in_directory(tmp_path, {"x": "val"})
        assert modified == 2  # .md and .yml, not .py


# ---------------------------------------------------------------------------
# APMPackage.variables field
# ---------------------------------------------------------------------------

class TestAPMPackageVariables:
    def test_variables_parsed_from_yml(self, tmp_path):
        apm_yml = tmp_path / "apm.yml"
        apm_yml.write_text(
            "name: test-pkg\n"
            "version: 1.0.0\n"
            "variables:\n"
            "  stack-profile:\n"
            "    description: Stack profile\n"
            "    default: react\n",
            encoding="utf-8",
        )
        from apm_cli.models.apm_package import APMPackage, clear_apm_yml_cache
        clear_apm_yml_cache()
        pkg = APMPackage.from_apm_yml(apm_yml)
        assert pkg.variables is not None
        assert "stack-profile" in pkg.variables
        assert pkg.variables["stack-profile"]["default"] == "react"

    def test_variables_none_when_absent(self, tmp_path):
        apm_yml = tmp_path / "apm.yml"
        apm_yml.write_text("name: test-pkg\nversion: 1.0.0\n", encoding="utf-8")
        from apm_cli.models.apm_package import APMPackage, clear_apm_yml_cache
        clear_apm_yml_cache()
        pkg = APMPackage.from_apm_yml(apm_yml)
        assert pkg.variables is None

    def test_consumer_variables_parsed(self, tmp_path):
        apm_yml = tmp_path / "apm.yml"
        apm_yml.write_text(
            "name: my-app\n"
            "version: 1.0.0\n"
            "variables:\n"
            "  tdd-development:\n"
            "    stack-profile: ios-swift\n",
            encoding="utf-8",
        )
        from apm_cli.models.apm_package import APMPackage, clear_apm_yml_cache
        clear_apm_yml_cache()
        pkg = APMPackage.from_apm_yml(apm_yml)
        assert pkg.variables["tdd-development"]["stack-profile"] == "ios-swift"


# ---------------------------------------------------------------------------
# LockedDependency.resolved_variables
# ---------------------------------------------------------------------------

class TestLockedDependencyVariables:
    def test_serialization_round_trip(self):
        from apm_cli.deps.lockfile import LockedDependency
        dep = LockedDependency(
            repo_url="owner/repo",
            resolved_variables={"stack": "ios-swift", "lang": "swift"},
        )
        d = dep.to_dict()
        assert d["resolved_variables"] == {"lang": "swift", "stack": "ios-swift"}

        restored = LockedDependency.from_dict(d)
        assert restored.resolved_variables == {"lang": "swift", "stack": "ios-swift"}

    def test_no_variables_omitted_from_dict(self):
        from apm_cli.deps.lockfile import LockedDependency
        dep = LockedDependency(repo_url="owner/repo")
        d = dep.to_dict()
        assert "resolved_variables" not in d

    def test_empty_variables_omitted_from_dict(self):
        from apm_cli.deps.lockfile import LockedDependency
        dep = LockedDependency(repo_url="owner/repo", resolved_variables={})
        d = dep.to_dict()
        assert "resolved_variables" not in d


# ---------------------------------------------------------------------------
# BaseIntegrator variable substitution
# ---------------------------------------------------------------------------

class TestBaseIntegratorVariables:
    def test_set_and_apply_variables(self):
        from apm_cli.integration.base_integrator import BaseIntegrator
        integrator = BaseIntegrator()
        integrator.set_variables({"name": "react"})
        result = integrator.apply_variable_substitution("Use ${var:name}")
        assert result == "Use react"

    def test_no_variables_set(self):
        from apm_cli.integration.base_integrator import BaseIntegrator
        integrator = BaseIntegrator()
        result = integrator.apply_variable_substitution("Use ${var:name}")
        assert result == "Use ${var:name}"

    def test_set_empty_variables(self):
        from apm_cli.integration.base_integrator import BaseIntegrator
        integrator = BaseIntegrator()
        integrator.set_variables({})
        result = integrator.apply_variable_substitution("Use ${var:name}")
        assert result == "Use ${var:name}"

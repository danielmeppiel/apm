"""Tests for src/apm_cli/apmrc.py"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow running from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from apm_cli.apmrc import (
    APMRC_FILENAME,
    ApmrcConfig,
    ApmrcParseError,
    MergedApmrcConfig,
    expand_env_vars,
    find_project_apmrc,
    get_auth_token_for_host,
    get_registry_for_scope,
    load_merged_config,
    parse_file,
)

# ===========================================================================
# TestExpandEnvVars
# ===========================================================================


class TestExpandEnvVars:
    ENV: dict[str, str] = {"FOO": "bar", "EMPTY": "", "CI": "1"}

    def test_plain_var_defined(self) -> None:
        assert expand_env_vars("${FOO}", self.ENV) == "bar"

    def test_plain_var_undefined_left_as_is(self) -> None:
        assert expand_env_vars("${UNDEF}", self.ENV) == "${UNDEF}"

    def test_optional_var_undefined_gives_empty(self) -> None:
        assert expand_env_vars("${UNDEF?}", self.ENV) == ""

    def test_optional_var_defined_gives_value(self) -> None:
        assert expand_env_vars("${FOO?}", self.ENV) == "bar"

    def test_default_form_undefined(self) -> None:
        assert expand_env_vars("${UNDEF:-fallback}", self.ENV) == "fallback"

    def test_default_form_defined(self) -> None:
        assert expand_env_vars("${FOO:-fallback}", self.ENV) == "bar"

    def test_default_form_empty_uses_default(self) -> None:
        assert expand_env_vars("${EMPTY:-fallback}", self.ENV) == "fallback"

    def test_conditional_form_set(self) -> None:
        assert expand_env_vars("${CI:+running}", self.ENV) == "running"

    def test_conditional_form_unset(self) -> None:
        assert expand_env_vars("${UNDEF:+running}", self.ENV) == ""

    def test_conditional_form_empty_gives_empty(self) -> None:
        # EMPTY is defined but empty — :+ should return empty string.
        assert expand_env_vars("${EMPTY:+word}", self.ENV) == ""

    def test_no_substitution_tokens(self) -> None:
        assert expand_env_vars("plain_value", self.ENV) == "plain_value"

    def test_multiple_tokens_in_one_value(self) -> None:
        result = expand_env_vars("${FOO}:${CI}", self.ENV)
        assert result == "bar:1"

    def test_token_embedded_in_longer_string(self) -> None:
        result = expand_env_vars("prefix-${FOO}-suffix", self.ENV)
        assert result == "prefix-bar-suffix"

    def test_defaults_to_os_environ(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("_APM_TEST_VAR", "hello")
        assert expand_env_vars("${_APM_TEST_VAR}") == "hello"


# ===========================================================================
# TestParseFile
# ===========================================================================


class TestParseFile:
    def test_parse_plain_registry(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("registry=https://example.com\n")
        cfg = parse_file(f, env={})
        assert cfg.registry == "https://example.com"

    def test_parse_scoped_registry(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("@myorg:registry=https://custom.example.io\n")
        cfg = parse_file(f, env={})
        assert cfg.scoped_registries["@myorg"] == "https://custom.example.io"

    def test_parse_auth_token_key(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("//custom.example.io/:_authToken=tok123\n")
        cfg = parse_file(f, env={})
        assert cfg.auth_tokens["//custom.example.io/:_authToken"] == "tok123"

    def test_env_var_expanded_in_token(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("github-token=${TEST_TOKEN}\n")
        cfg = parse_file(f, env={"TEST_TOKEN": "ghp_abc"})
        assert cfg.github_token == "ghp_abc"

    def test_env_var_undefined_left_as_is(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("github-token=${UNSET_TOKEN}\n")
        cfg = parse_file(f, env={})
        assert cfg.github_token == "${UNSET_TOKEN}"

    def test_comment_hash_ignored(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("# comment\nregistry=https://x.io\n")
        cfg = parse_file(f, env={})
        assert cfg.registry == "https://x.io"

    def test_comment_semicolon_ignored(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("; comment\nregistry=https://x.io\n")
        cfg = parse_file(f, env={})
        assert cfg.registry == "https://x.io"

    def test_blank_lines_ignored(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("\n\nregistry=https://x.io\n\n")
        cfg = parse_file(f, env={})
        assert cfg.registry == "https://x.io"

    def test_unknown_keys_stored_in_raw(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("future-key=some-value\n")
        cfg = parse_file(f, env={})
        assert cfg.raw.get("future-key") == "some-value"
        assert cfg.registry is None

    def test_boolean_auto_integrate_true(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("auto-integrate=true\n")
        cfg = parse_file(f, env={})
        assert cfg.auto_integrate is True

    def test_boolean_auto_integrate_false(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("auto-integrate=false\n")
        cfg = parse_file(f, env={})
        assert cfg.auto_integrate is False

    def test_boolean_yes_no(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("auto-integrate=yes\n")
        cfg = parse_file(f, env={})
        assert cfg.auto_integrate is True

    def test_boolean_numeric(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("auto-integrate=1\n")
        cfg = parse_file(f, env={})
        assert cfg.auto_integrate is True

    def test_boolean_case_insensitive(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("auto-integrate=True\n")
        cfg = parse_file(f, env={})
        assert cfg.auto_integrate is True

    def test_hyphen_and_underscore_aliases(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("default_client=claude\n")
        cfg = parse_file(f, env={})
        assert cfg.default_client == "claude"

    def test_source_file_set(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("registry=https://x.io\n")
        cfg = parse_file(f, env={})
        assert cfg.source_file == f

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            parse_file(tmp_path / "nonexistent.apmrc", env={})

    def test_utf8_bom_handled(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        # Write with BOM
        f.write_bytes(b"\xef\xbb\xbfregistry=https://bom.io\n")
        cfg = parse_file(f, env={})
        assert cfg.registry == "https://bom.io"

    def test_crlf_line_endings(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_bytes(b"registry=https://crlf.io\r\n")
        cfg = parse_file(f, env={})
        assert cfg.registry == "https://crlf.io"

    def test_ci_mode_conditional(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("ci-mode=${CI:+true}\n")
        cfg_ci = parse_file(f, env={"CI": "1"})
        assert cfg_ci.ci_mode is True
        cfg_no_ci = parse_file(f, env={})
        # Empty string after substitution — not a valid bool, stored as None.
        assert cfg_no_ci.ci_mode is None

    def test_multiple_keys_parsed(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text(
            "registry=https://r.io\n" "default-client=claude\n" "auto-integrate=false\n"
        )
        cfg = parse_file(f, env={})
        assert cfg.registry == "https://r.io"
        assert cfg.default_client == "claude"
        assert cfg.auto_integrate is False


# ===========================================================================
# TestFindProjectApmrc
# ===========================================================================


class TestFindProjectApmrc:
    def test_finds_apmrc_in_cwd(self, tmp_path: Path) -> None:
        (tmp_path / ".apmrc").write_text("registry=https://x.io\n")
        assert find_project_apmrc(tmp_path) == tmp_path / ".apmrc"

    def test_finds_apmrc_in_parent(self, tmp_path: Path) -> None:
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / ".apmrc").write_text("registry=https://x.io\n")
        assert find_project_apmrc(subdir) == tmp_path / ".apmrc"

    def test_finds_apmrc_in_grandparent(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        (tmp_path / ".apmrc").write_text("registry=https://x.io\n")
        assert find_project_apmrc(nested) == tmp_path / ".apmrc"

    def test_stops_at_apm_yml_without_apmrc(self, tmp_path: Path) -> None:
        (tmp_path / "apm.yml").write_text("name: test\n")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        assert find_project_apmrc(subdir) is None

    def test_finds_apmrc_at_apm_yml_root(self, tmp_path: Path) -> None:
        (tmp_path / "apm.yml").write_text("name: test\n")
        (tmp_path / ".apmrc").write_text("registry=https://x.io\n")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        assert find_project_apmrc(subdir) == tmp_path / ".apmrc"

    def test_stops_at_dot_git(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        assert find_project_apmrc(subdir) is None

    def test_finds_apmrc_at_dot_git_root(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        (tmp_path / ".apmrc").write_text("registry=https://x.io\n")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        assert find_project_apmrc(subdir) == tmp_path / ".apmrc"

    def test_returns_none_when_no_markers_and_no_apmrc(self, tmp_path: Path) -> None:
        # tmp_path is isolated; no .apmrc or root markers above it in tmp.
        assert find_project_apmrc(tmp_path) is None

    def test_apm_yaml_also_stops_walk(self, tmp_path: Path) -> None:
        (tmp_path / "apm.yaml").write_text("name: test\n")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        assert find_project_apmrc(subdir) is None


# ===========================================================================
# TestLoadMergedConfig
# ===========================================================================


class TestLoadMergedConfig:
    def _write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def test_project_overrides_global(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home_dir = tmp_path / "home"
        self._write(
            home_dir / ".apm" / ".apmrc",
            "registry=https://global.example.io\n",
        )
        project_dir = tmp_path / "project"
        self._write(project_dir / "apm.yml", "name: test\n")
        self._write(
            project_dir / ".apmrc",
            "registry=https://project.example.io\n",
        )
        monkeypatch.setenv("HOME", str(home_dir))
        merged = load_merged_config(cwd=project_dir, env={})
        assert merged.registry == "https://project.example.io"

    def test_global_used_when_no_project_apmrc(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home_dir = tmp_path / "home"
        self._write(
            home_dir / ".apm" / ".apmrc",
            "registry=https://global.example.io\n",
        )
        project_dir = tmp_path / "project"
        self._write(project_dir / "apm.yml", "name: test\n")
        monkeypatch.setenv("HOME", str(home_dir))
        merged = load_merged_config(cwd=project_dir, env={})
        assert merged.registry == "https://global.example.io"

    def test_scoped_registries_merged_from_all_layers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home_dir = tmp_path / "home"
        self._write(
            home_dir / ".apm" / ".apmrc",
            "@globalorg:registry=https://global.io\n",
        )
        project_dir = tmp_path / "project"
        self._write(project_dir / "apm.yml", "name: test\n")
        self._write(
            project_dir / ".apmrc",
            "@projectorg:registry=https://project.io\n",
        )
        monkeypatch.setenv("HOME", str(home_dir))
        merged = load_merged_config(cwd=project_dir, env={})
        assert merged.scoped_registries.get("@globalorg") == "https://global.io"
        assert merged.scoped_registries.get("@projectorg") == "https://project.io"

    def test_sources_list_populated(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home_dir = tmp_path / "empty_home"
        home_dir.mkdir(parents=True)
        project_dir = tmp_path / "project"
        self._write(project_dir / ".apmrc", "registry=https://x.io\n")
        monkeypatch.setenv("HOME", str(home_dir))
        merged = load_merged_config(cwd=project_dir, env={})
        assert project_dir / ".apmrc" in merged.sources

    def test_defaults_when_no_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home_dir = tmp_path / "empty_home"
        home_dir.mkdir(parents=True)
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.setenv("HOME", str(home_dir))
        merged = load_merged_config(cwd=project_dir, env={})
        assert merged.registry == "https://api.mcp.github.com"
        assert merged.github_token is None
        assert merged.sources == []

    def test_auth_tokens_merged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home_dir = tmp_path / "home"
        self._write(
            home_dir / ".apm" / ".apmrc",
            "//global.io/:_authToken=global_tok\n",
        )
        project_dir = tmp_path / "project"
        self._write(project_dir / "apm.yml", "name: test\n")
        self._write(
            project_dir / ".apmrc",
            "//project.io/:_authToken=project_tok\n",
        )
        monkeypatch.setenv("HOME", str(home_dir))
        merged = load_merged_config(cwd=project_dir, env={})
        assert merged.auth_tokens.get("//global.io/:_authToken") == "global_tok"
        assert merged.auth_tokens.get("//project.io/:_authToken") == "project_tok"

    def test_project_auth_token_overrides_global(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home_dir = tmp_path / "home"
        self._write(
            home_dir / ".apm" / ".apmrc",
            "//shared.io/:_authToken=global_tok\n",
        )
        project_dir = tmp_path / "project"
        self._write(project_dir / "apm.yml", "name: test\n")
        self._write(
            project_dir / ".apmrc",
            "//shared.io/:_authToken=project_tok\n",
        )
        monkeypatch.setenv("HOME", str(home_dir))
        merged = load_merged_config(cwd=project_dir, env={})
        assert merged.auth_tokens["//shared.io/:_authToken"] == "project_tok"

    def test_env_var_expanded_during_load(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home_dir = tmp_path / "empty_home"
        home_dir.mkdir(parents=True)
        project_dir = tmp_path / "project"
        self._write(
            project_dir / ".apmrc",
            "github-token=${MY_TOKEN}\n",
        )
        monkeypatch.setenv("HOME", str(home_dir))
        merged = load_merged_config(cwd=project_dir, env={"MY_TOKEN": "ghp_xyz"})
        assert merged.github_token == "ghp_xyz"


# ===========================================================================
# TestScopeAndAuthHelpers
# ===========================================================================


class TestScopeAndAuthHelpers:
    def _cfg(self, **kwargs: object) -> MergedApmrcConfig:
        return MergedApmrcConfig(**kwargs)  # type: ignore[arg-type]

    def test_scoped_registry_lookup(self) -> None:
        cfg = self._cfg(scoped_registries={"@myorg": "https://myorg.io"})
        assert get_registry_for_scope("@myorg", cfg) == "https://myorg.io"

    def test_scope_without_at_prefix_normalised(self) -> None:
        cfg = self._cfg(scoped_registries={"@myorg": "https://myorg.io"})
        assert get_registry_for_scope("myorg", cfg) == "https://myorg.io"

    def test_scoped_registry_falls_back_to_default(self) -> None:
        cfg = self._cfg(registry="https://default.io")
        assert get_registry_for_scope("@unknown", cfg) == "https://default.io"

    def test_auth_token_for_host(self) -> None:
        cfg = self._cfg(auth_tokens={"//myorg.pkg.github.com/:_authToken": "tok123"})
        assert get_auth_token_for_host("myorg.pkg.github.com", cfg) == "tok123"

    def test_auth_token_missing_returns_none(self) -> None:
        cfg = self._cfg()
        assert get_auth_token_for_host("unknown.host", cfg) is None

    def test_auth_token_exact_host_match(self) -> None:
        cfg = self._cfg(
            auth_tokens={
                "//a.example.com/:_authToken": "tok_a",
                "//b.example.com/:_authToken": "tok_b",
            }
        )
        assert get_auth_token_for_host("a.example.com", cfg) == "tok_a"
        assert get_auth_token_for_host("b.example.com", cfg) == "tok_b"


# ===========================================================================
# TestFindGlobalApmrcPaths — XDG_CONFIG_HOME and global discovery
# ===========================================================================


class TestFindGlobalApmrcPaths:
    from apm_cli.apmrc import find_global_apmrc_paths

    def test_xdg_config_home_used_on_non_windows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sys

        if sys.platform == "win32":
            pytest.skip("XDG not applicable on Windows")

        xdg = tmp_path / "xdg"
        apmrc = xdg / "apm" / APMRC_FILENAME
        apmrc.parent.mkdir(parents=True)
        apmrc.write_text("registry=https://xdg.io\n")

        home_dir = tmp_path / "home"
        home_dir.mkdir()
        monkeypatch.setenv("HOME", str(home_dir))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))

        from apm_cli.apmrc import find_global_apmrc_paths

        paths = find_global_apmrc_paths()
        assert apmrc in paths

    def test_fallback_to_dot_config_without_xdg_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sys

        if sys.platform == "win32":
            pytest.skip("XDG not applicable on Windows")

        home_dir = tmp_path / "home"
        dot_config_apmrc = home_dir / ".config" / "apm" / APMRC_FILENAME
        dot_config_apmrc.parent.mkdir(parents=True)
        dot_config_apmrc.write_text("registry=https://dotconfig.io\n")

        monkeypatch.setenv("HOME", str(home_dir))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        from apm_cli.apmrc import find_global_apmrc_paths

        paths = find_global_apmrc_paths()
        assert dot_config_apmrc in paths

    def test_nonexistent_paths_not_returned(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home_dir = tmp_path / "empty_home"
        home_dir.mkdir()
        monkeypatch.setenv("HOME", str(home_dir))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        from apm_cli.apmrc import find_global_apmrc_paths

        paths = find_global_apmrc_paths()
        assert paths == []


# ===========================================================================
# TestConfigIntegration — config.py additions
# ===========================================================================


class TestConfigIntegration:
    def test_get_effective_registry_respects_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MCP_REGISTRY_URL", "https://env-registry.io")
        # Force cache refresh after monkeypatching
        from apm_cli import config as cfg_module

        cfg_module._apmrc_cache = None
        from apm_cli.config import get_effective_registry

        assert get_effective_registry() == "https://env-registry.io"
        monkeypatch.delenv("MCP_REGISTRY_URL")
        cfg_module._apmrc_cache = None

    def test_get_effective_registry_falls_back_to_apmrc(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MCP_REGISTRY_URL", raising=False)
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "apm.yml").write_text("name: test\n")
        (project_dir / ".apmrc").write_text("registry=https://apmrc-registry.io\n")

        home_dir = tmp_path / "home"
        home_dir.mkdir()
        monkeypatch.setenv("HOME", str(home_dir))
        monkeypatch.chdir(project_dir)

        from apm_cli import config as cfg_module

        cfg_module._apmrc_cache = None
        from apm_cli.config import get_effective_registry

        assert get_effective_registry() == "https://apmrc-registry.io"
        cfg_module._apmrc_cache = None

    def test_get_effective_token_env_var_takes_priority(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GITHUB_APM_PAT", "env_token_123")

        from apm_cli import config as cfg_module

        cfg_module._apmrc_cache = None
        from apm_cli.config import get_effective_token

        assert get_effective_token() == "env_token_123"
        monkeypatch.delenv("GITHUB_APM_PAT")
        cfg_module._apmrc_cache = None

    def test_get_effective_token_skips_empty_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GITHUB_APM_PAT", "")
        monkeypatch.setenv("GITHUB_TOKEN", "fallback_token")

        from apm_cli import config as cfg_module

        cfg_module._apmrc_cache = None
        from apm_cli.config import get_effective_token

        assert get_effective_token() == "fallback_token"
        monkeypatch.delenv("GITHUB_APM_PAT")
        monkeypatch.delenv("GITHUB_TOKEN")
        cfg_module._apmrc_cache = None

    def test_get_apmrc_config_cache_refresh(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        monkeypatch.setenv("HOME", str(home_dir))

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        from apm_cli import config as cfg_module

        cfg_module._apmrc_cache = None
        from apm_cli.config import get_apmrc_config

        first = get_apmrc_config()
        second = get_apmrc_config()
        assert first is second  # cached

        third = get_apmrc_config(refresh=True)
        assert third is not first  # fresh load

        cfg_module._apmrc_cache = None


# ===========================================================================
# TestInitRcTemplate — verifies the scaffolded .apmrc template content
# ===========================================================================


class TestInitRcTemplate:
    def test_template_uses_single_braces(self) -> None:
        from apm_cli.commands.config import _INIT_RC_TEMPLATE

        # Must not contain double-brace artifacts from non-f-string formatting.
        assert "{{" not in _INIT_RC_TEMPLATE
        assert "}}" not in _INIT_RC_TEMPLATE

    def test_template_contains_expected_keys(self) -> None:
        from apm_cli.commands.config import _INIT_RC_TEMPLATE

        for expected in (
            "registry=",
            "github-token=",
            "default-client=",
            "auto-integrate=",
            "ci-mode=",
        ):
            assert expected in _INIT_RC_TEMPLATE, f"Missing key: {expected}"

    def test_template_env_vars_use_correct_syntax(self) -> None:
        # Each env var reference should look like ${VAR_NAME}
        import re

        from apm_cli.commands.config import _INIT_RC_TEMPLATE

        refs = re.findall(r"\$\{[^}]+\}", _INIT_RC_TEMPLATE)
        assert len(refs) >= 2  # at least github-token and ci-mode
        for ref in refs:
            assert ref.startswith("${") and ref.endswith("}")


# ===========================================================================
# TestExpandEnvVarsEdgeCases — additional edge cases
# ===========================================================================


class TestExpandEnvVarsEdgeCases:
    def test_invalid_var_name_left_as_is(self) -> None:
        # Variable names starting with digits are invalid per the regex.
        assert expand_env_vars("${123}", {}) == "${123}"

    def test_nested_dollar_brace_not_expanded(self) -> None:
        # No recursive expansion: inner ${FOO} is literal.
        assert expand_env_vars("${${FOO}}", {"FOO": "bar"}) == "${bar}"

    def test_empty_string_value(self) -> None:
        assert expand_env_vars("", {"FOO": "bar"}) == ""

    def test_dollar_sign_without_brace_untouched(self) -> None:
        assert expand_env_vars("$FOO", {"FOO": "bar"}) == "$FOO"

    def test_default_with_empty_default_value(self) -> None:
        # ${VAR:-} means empty string as default.
        assert expand_env_vars("${UNDEF:-}", {}) == ""

    def test_conditional_with_empty_word(self) -> None:
        # ${VAR:+} means replace with empty string when set.
        assert expand_env_vars("${FOO:+}", {"FOO": "bar"}) == ""

    def test_mixed_forms_in_one_string(self) -> None:
        env = {"A": "1", "C": "3"}
        result = expand_env_vars("${A}-${B?}-${C:-default}-${D:+word}", env)
        assert result == "1--3-"


# ===========================================================================
# TestParseFileEdgeCases — additional parse_file edge cases
# ===========================================================================


class TestParseFileEdgeCases:
    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("")
        cfg = parse_file(f, env={})
        assert cfg.registry is None
        assert cfg.scoped_registries == {}
        assert cfg.auth_tokens == {}
        assert cfg.raw == {}

    def test_only_comments_file(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("# comment\n; another\n")
        cfg = parse_file(f, env={})
        assert cfg.registry is None

    def test_duplicate_keys_last_wins(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("registry=https://first.io\nregistry=https://second.io\n")
        cfg = parse_file(f, env={})
        assert cfg.registry == "https://second.io"

    def test_value_containing_equals(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("github-token=abc=def=ghi\n")
        cfg = parse_file(f, env={})
        assert cfg.github_token == "abc=def=ghi"

    def test_spaces_around_equals(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("registry = https://spaced.io\n")
        cfg = parse_file(f, env={})
        assert cfg.registry == "https://spaced.io"

    def test_malformed_boolean_stays_none(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("auto-integrate=garbage\n")
        cfg = parse_file(f, env={})
        assert cfg.auto_integrate is None

    def test_invalid_auth_token_format_goes_to_raw(self, tmp_path: Path) -> None:
        # Missing trailing /:_authToken pattern — should be stored in raw.
        f = tmp_path / ".apmrc"
        f.write_text("//hostname:_authToken=tok\n")
        cfg = parse_file(f, env={})
        assert cfg.auth_tokens == {}
        assert "//hostname:_authToken" in cfg.raw

    def test_multiple_scoped_registries(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text(
            "@org1:registry=https://org1.io\n"
            "@org2:registry=https://org2.io\n"
            "@org3:registry=https://org3.io\n"
        )
        cfg = parse_file(f, env={})
        assert len(cfg.scoped_registries) == 3
        assert cfg.scoped_registries["@org1"] == "https://org1.io"
        assert cfg.scoped_registries["@org3"] == "https://org3.io"

    def test_env_var_in_scoped_registry(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("@myorg:registry=${ORG_REGISTRY}\n")
        cfg = parse_file(f, env={"ORG_REGISTRY": "https://env.io"})
        assert cfg.scoped_registries["@myorg"] == "https://env.io"

    def test_env_var_with_default_in_auth_token(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("//example.io/:_authToken=${TOK:-default_tok}\n")
        cfg = parse_file(f, env={})
        assert cfg.auth_tokens["//example.io/:_authToken"] == "default_tok"

    def test_all_key_aliases(self, tmp_path: Path) -> None:
        # Verify every alias in _KEY_ALIASES resolves correctly.
        f = tmp_path / ".apmrc"
        f.write_text(
            "github_token=tok1\n"
            "default_client=cursor\n"
            "auto_integrate=no\n"
            "ci_mode=true\n"
        )
        cfg = parse_file(f, env={})
        assert cfg.github_token == "tok1"
        assert cfg.default_client == "cursor"
        assert cfg.auto_integrate is False
        assert cfg.ci_mode is True


# ===========================================================================
# TestApmrcParseError
# ===========================================================================


class TestApmrcParseError:
    def test_error_attributes(self) -> None:
        err = ApmrcParseError(Path("/foo/.apmrc"), "bad syntax")
        assert err.path == Path("/foo/.apmrc")
        assert err.reason == "bad syntax"
        assert "/foo/.apmrc" in str(err)
        assert "bad syntax" in str(err)


# ===========================================================================
# TestMergeInto — verify _merge_into semantics
# ===========================================================================


class TestMergeInto:
    from apm_cli.apmrc import _merge_into

    def test_none_fields_do_not_override(self) -> None:
        from apm_cli.apmrc import _merge_into

        base = MergedApmrcConfig(registry="https://base.io", github_token="base_tok")
        layer = ApmrcConfig()  # all None
        _merge_into(base, layer)
        assert base.registry == "https://base.io"
        assert base.github_token == "base_tok"

    def test_non_none_fields_override(self) -> None:
        from apm_cli.apmrc import _merge_into

        base = MergedApmrcConfig(registry="https://base.io")
        layer = ApmrcConfig(registry="https://layer.io", default_client="claude")
        _merge_into(base, layer)
        assert base.registry == "https://layer.io"
        assert base.default_client == "claude"

    def test_scoped_registries_merge_not_replace(self) -> None:
        from apm_cli.apmrc import _merge_into

        base = MergedApmrcConfig(scoped_registries={"@org1": "https://org1.io"})
        layer = ApmrcConfig(scoped_registries={"@org2": "https://org2.io"})
        _merge_into(base, layer)
        assert base.scoped_registries == {
            "@org1": "https://org1.io",
            "@org2": "https://org2.io",
        }

    def test_same_scope_overridden(self) -> None:
        from apm_cli.apmrc import _merge_into

        base = MergedApmrcConfig(scoped_registries={"@org1": "https://old.io"})
        layer = ApmrcConfig(scoped_registries={"@org1": "https://new.io"})
        _merge_into(base, layer)
        assert base.scoped_registries["@org1"] == "https://new.io"


# ===========================================================================
# TestLoadMergedConfigEdgeCases
# ===========================================================================


class TestLoadMergedConfigEdgeCases:
    def _write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def test_malformed_file_skipped_gracefully(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home_dir = tmp_path / "home"
        # Write a binary/unreadable file that will cause a parse error.
        bad_file = home_dir / ".apm" / ".apmrc"
        bad_file.parent.mkdir(parents=True)
        bad_file.write_bytes(b"\x00\x01\x02\x03")

        project_dir = tmp_path / "project"
        self._write(project_dir / ".apmrc", "registry=https://good.io\n")

        monkeypatch.setenv("HOME", str(home_dir))
        merged = load_merged_config(cwd=project_dir, env={})
        # The malformed global file should be skipped; project one works.
        assert merged.registry == "https://good.io"

    def test_home_apmrc_and_apm_dir_both_loaded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home_dir = tmp_path / "home"
        self._write(home_dir / ".apmrc", "default-client=vscode\n")
        self._write(
            home_dir / ".apm" / ".apmrc",
            "registry=https://apm-dir.io\n",
        )
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        monkeypatch.setenv("HOME", str(home_dir))
        merged = load_merged_config(cwd=project_dir, env={})
        # Both global files should be loaded.
        assert merged.default_client == "vscode"
        assert merged.registry == "https://apm-dir.io"
        assert len(merged.sources) == 2


# ===========================================================================
# TestClickCommands — test show-rc, which-rc, init-rc via CliRunner
# ===========================================================================


class TestClickCommands:
    def test_show_rc_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json as _json

        from click.testing import CliRunner

        from apm_cli.commands.config import config

        home_dir = tmp_path / "home"
        home_dir.mkdir()
        monkeypatch.setenv("HOME", str(home_dir))
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".apmrc").write_text("registry=https://test.io\n")

        # Clear the cache.
        from apm_cli import config as cfg_module

        cfg_module._apmrc_cache = None

        runner = CliRunner()
        result = runner.invoke(config, ["show-rc", "--json"])
        assert result.exit_code == 0
        data = _json.loads(result.output)
        assert data["registry"] == "https://test.io"

        cfg_module._apmrc_cache = None

    def test_show_rc_masks_token(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json as _json

        from click.testing import CliRunner

        from apm_cli.commands.config import config

        home_dir = tmp_path / "home"
        home_dir.mkdir()
        monkeypatch.setenv("HOME", str(home_dir))
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".apmrc").write_text("github-token=super_secret\n")

        from apm_cli import config as cfg_module

        cfg_module._apmrc_cache = None

        runner = CliRunner()
        result = runner.invoke(config, ["show-rc", "--json"])
        assert result.exit_code == 0
        data = _json.loads(result.output)
        assert data["github_token"] == "***"
        assert "super_secret" not in result.output

        cfg_module._apmrc_cache = None

    def test_which_rc_no_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from click.testing import CliRunner

        from apm_cli.commands.config import config

        home_dir = tmp_path / "empty_home"
        home_dir.mkdir()
        monkeypatch.setenv("HOME", str(home_dir))
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(config, ["which-rc"])
        assert result.exit_code == 0
        assert "No .apmrc files found" in result.output

    def test_which_rc_lists_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from click.testing import CliRunner

        from apm_cli.commands.config import config

        home_dir = tmp_path / "home"
        home_dir.mkdir()
        monkeypatch.setenv("HOME", str(home_dir))
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".apmrc").write_text("registry=https://x.io\n")

        runner = CliRunner()
        result = runner.invoke(config, ["which-rc"])
        assert result.exit_code == 0
        assert "[project]" in result.output

    def test_init_rc_creates_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from click.testing import CliRunner

        from apm_cli.commands.config import config

        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(config, ["init-rc"])
        assert result.exit_code == 0
        assert "Created" in result.output

        created = tmp_path / ".apmrc"
        assert created.exists()
        content = created.read_text()
        assert "${GITHUB_APM_PAT}" in content
        assert "{{" not in content

    def test_init_rc_refuses_overwrite(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from click.testing import CliRunner

        from apm_cli.commands.config import config

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".apmrc").write_text("existing\n")

        runner = CliRunner()
        result = runner.invoke(config, ["init-rc"])
        assert result.exit_code != 0
        assert "already exists" in result.output

    def test_init_rc_force_overwrites(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from click.testing import CliRunner

        from apm_cli.commands.config import config

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".apmrc").write_text("old content\n")

        runner = CliRunner()
        result = runner.invoke(config, ["init-rc", "--force"])
        assert result.exit_code == 0
        content = (tmp_path / ".apmrc").read_text()
        assert "old content" not in content
        assert "github-token" in content

    def test_init_rc_global(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from click.testing import CliRunner

        from apm_cli.commands.config import config

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(config, ["init-rc", "--global"])
        assert result.exit_code == 0
        assert (tmp_path / ".apm" / ".apmrc").exists()


# ===========================================================================
# TestRegistryClientIntegration
# ===========================================================================


class TestRegistryClientIntegration:
    def test_client_uses_effective_registry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        monkeypatch.setenv("HOME", str(home_dir))
        monkeypatch.delenv("MCP_REGISTRY_URL", raising=False)
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".apmrc").write_text("registry=https://custom.registry.io\n")

        from apm_cli import config as cfg_module

        cfg_module._apmrc_cache = None

        from apm_cli.registry.client import SimpleRegistryClient

        client = SimpleRegistryClient()
        assert client.registry_url == "https://custom.registry.io"

        cfg_module._apmrc_cache = None

    def test_client_explicit_url_takes_priority(self) -> None:
        from apm_cli.registry.client import SimpleRegistryClient

        client = SimpleRegistryClient(registry_url="https://explicit.io")
        assert client.registry_url == "https://explicit.io"


# ===========================================================================
# TestTokenManagerIntegration
# ===========================================================================


class TestTokenManagerIntegration:
    def test_credential_fallback_uses_apmrc_for_modules(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        monkeypatch.setenv("HOME", str(home_dir))
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".apmrc").write_text("github-token=apmrc_tok_123\n")

        # Clear env vars so they don't interfere.
        for k in ("GITHUB_APM_PAT", "GITHUB_TOKEN", "GH_TOKEN"):
            monkeypatch.delenv(k, raising=False)

        from apm_cli import config as cfg_module

        cfg_module._apmrc_cache = None

        from apm_cli.core.token_manager import GitHubTokenManager

        mgr = GitHubTokenManager()
        token = mgr.get_token_with_credential_fallback("modules", "github.com")
        assert token == "apmrc_tok_123"

        cfg_module._apmrc_cache = None

    def test_credential_fallback_env_beats_apmrc(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        monkeypatch.setenv("HOME", str(home_dir))
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".apmrc").write_text("github-token=apmrc_tok\n")
        monkeypatch.setenv("GITHUB_APM_PAT", "env_tok")

        from apm_cli import config as cfg_module

        cfg_module._apmrc_cache = None

        from apm_cli.core.token_manager import GitHubTokenManager

        mgr = GitHubTokenManager()
        token = mgr.get_token_with_credential_fallback("modules", "github.com")
        assert token == "env_tok"

        monkeypatch.delenv("GITHUB_APM_PAT")
        cfg_module._apmrc_cache = None

    def test_credential_fallback_skips_apmrc_for_non_modules(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        monkeypatch.setenv("HOME", str(home_dir))
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".apmrc").write_text("github-token=apmrc_tok\n")

        for k in ("GITHUB_COPILOT_PAT", "GITHUB_TOKEN", "GITHUB_APM_PAT", "GH_TOKEN"):
            monkeypatch.delenv(k, raising=False)

        from apm_cli import config as cfg_module

        cfg_module._apmrc_cache = None

        from apm_cli.core.token_manager import GitHubTokenManager

        mgr = GitHubTokenManager()
        # For 'copilot' purpose, .apmrc is NOT checked.
        token = mgr.get_token_for_purpose("copilot")
        assert token is None

        cfg_module._apmrc_cache = None


# ===========================================================================
# TestBackslashEscaping — Step 1a
# ===========================================================================


class TestBackslashEscaping:
    def test_escaped_var_produces_literal(self) -> None:
        assert expand_env_vars("\\${FOO}", {"FOO": "bar"}) == "${FOO}"

    def test_escaped_mixed_with_real_var(self) -> None:
        result = expand_env_vars("\\${FOO}-${FOO}", {"FOO": "bar"})
        assert result == "${FOO}-bar"

    def test_escaped_in_default_form(self) -> None:
        result = expand_env_vars("\\${FOO:-fallback}", {"FOO": "bar"})
        assert result == "${FOO:-fallback}"

    def test_escaped_in_optional_form(self) -> None:
        result = expand_env_vars("\\${FOO?}", {"FOO": "bar"})
        assert result == "${FOO?}"

    def test_no_double_unescape(self) -> None:
        # A single backslash escape should not be consumed twice.
        result = expand_env_vars("\\${A}\\${B}", {"A": "1", "B": "2"})
        assert result == "${A}${B}"

    def test_backslash_in_file(self, tmp_path: Path) -> None:
        f = tmp_path / ".apmrc"
        f.write_text("registry=\\${NOT_EXPANDED}\n")
        cfg = parse_file(f, env={"NOT_EXPANDED": "should_not_appear"})
        assert cfg.registry == "${NOT_EXPANDED}"


# ===========================================================================
# TestBooleanWarning — Step 1b
# ===========================================================================


class TestBooleanWarning:
    def test_malformed_boolean_warns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        f = tmp_path / ".apmrc"
        f.write_text("auto-integrate=truee\n")
        with caplog.at_level(logging.WARNING, logger="apm_cli.apmrc"):
            cfg = parse_file(f, env={})
        assert cfg.auto_integrate is None
        assert "invalid boolean" in caplog.text.lower()

    def test_valid_boolean_no_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        f = tmp_path / ".apmrc"
        f.write_text("auto-integrate=true\n")
        with caplog.at_level(logging.WARNING, logger="apm_cli.apmrc"):
            cfg = parse_file(f, env={})
        assert cfg.auto_integrate is True
        assert "invalid boolean" not in caplog.text.lower()


# ===========================================================================
# TestCacheInvalidation — Step 1c
# ===========================================================================


class TestCacheInvalidation:
    def test_invalidate_clears_both_caches(self) -> None:
        from apm_cli import config as cfg_module
        from apm_cli.config import _invalidate_config_cache

        cfg_module._config_cache = {"dummy": True}
        cfg_module._apmrc_cache = MergedApmrcConfig()
        _invalidate_config_cache()
        assert cfg_module._config_cache is None
        assert cfg_module._apmrc_cache is None


# ===========================================================================
# TestRegistryAuthHeaders — Step 2
# ===========================================================================


class TestRegistryAuthHeaders:
    def test_auth_token_applied_from_apmrc(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        monkeypatch.setenv("HOME", str(home_dir))
        monkeypatch.delenv("MCP_REGISTRY_URL", raising=False)
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".apmrc").write_text(
            "registry=https://registry.example.com\n"
            "//registry.example.com/:_authToken=test_bearer_tok\n"
        )

        from apm_cli import config as cfg_module

        cfg_module._apmrc_cache = None

        from apm_cli.registry.client import SimpleRegistryClient

        client = SimpleRegistryClient()
        assert client.session.headers.get("Authorization") == "Bearer test_bearer_tok"

        cfg_module._apmrc_cache = None

    def test_no_auth_when_no_token(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        monkeypatch.setenv("HOME", str(home_dir))
        monkeypatch.delenv("MCP_REGISTRY_URL", raising=False)
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".apmrc").write_text("registry=https://no-token.io\n")

        from apm_cli import config as cfg_module

        cfg_module._apmrc_cache = None

        from apm_cli.registry.client import SimpleRegistryClient

        client = SimpleRegistryClient()
        assert "Authorization" not in client.session.headers

        cfg_module._apmrc_cache = None


# ===========================================================================
# TestEnvOverrides — Step 3
# ===========================================================================


class TestEnvOverrides:
    def test_apm_config_registry(self) -> None:
        merged = load_merged_config(
            cwd=Path("/nonexistent"),
            env={"APM_CONFIG_REGISTRY": "https://env.io"},
        )
        assert merged.registry == "https://env.io"

    def test_apm_config_underscore_to_hyphen(self) -> None:
        merged = load_merged_config(
            cwd=Path("/nonexistent"),
            env={"APM_CONFIG_DEFAULT_CLIENT": "claude"},
        )
        assert merged.default_client == "claude"

    def test_apm_config_github_token(self) -> None:
        merged = load_merged_config(
            cwd=Path("/nonexistent"),
            env={"APM_CONFIG_GITHUB_TOKEN": "ghp_test"},
        )
        assert merged.github_token == "ghp_test"

    def test_apm_config_auto_integrate(self) -> None:
        merged = load_merged_config(
            cwd=Path("/nonexistent"),
            env={"APM_CONFIG_AUTO_INTEGRATE": "false"},
        )
        assert merged.auto_integrate is False

    def test_env_overrides_project_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        monkeypatch.setenv("HOME", str(home_dir))
        project = tmp_path / "project"
        project.mkdir()
        (project / ".apmrc").write_text("registry=https://file.io\n")

        merged = load_merged_config(
            cwd=project,
            env={"APM_CONFIG_REGISTRY": "https://env-wins.io"},
        )
        assert merged.registry == "https://env-wins.io"

    def test_no_apm_config_vars_no_sources_added(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        monkeypatch.setenv("HOME", str(home_dir))
        merged = load_merged_config(cwd=tmp_path, env={})
        # No Path("<env>") in sources when no APM_CONFIG_* vars are set.
        assert Path("<env>") not in merged.sources

    def test_apm_config_prefix_only_ignored(self) -> None:
        # "APM_CONFIG_" alone (no key) should not be parsed.
        merged = load_merged_config(
            cwd=Path("/nonexistent"),
            env={"APM_CONFIG_": "bad"},
        )
        assert merged.registry == "https://api.mcp.github.com"


# ===========================================================================
# TestConfigSetGetDelete — Step 4
# ===========================================================================


class TestConfigSetGetDelete:
    def _setup(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        monkeypatch.setenv("HOME", str(home_dir))
        monkeypatch.chdir(tmp_path)

        from apm_cli import config as cfg_module

        cfg_module._apmrc_cache = None
        cfg_module._config_cache = None

    def test_config_set_creates_apmrc(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._setup(tmp_path, monkeypatch)
        from click.testing import CliRunner

        from apm_cli.commands.config import config

        runner = CliRunner()
        result = runner.invoke(config, ["set", "registry", "https://new.io"])
        assert result.exit_code == 0

        content = (tmp_path / ".apmrc").read_text()
        assert "registry=https://new.io" in content

    def test_config_get_reads_value(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._setup(tmp_path, monkeypatch)
        (tmp_path / ".apmrc").write_text("registry=https://test.io\n")

        from click.testing import CliRunner

        from apm_cli.commands.config import config

        runner = CliRunner()
        result = runner.invoke(config, ["get", "registry"])
        assert result.exit_code == 0
        assert "https://test.io" in result.output

    def test_config_delete_removes_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._setup(tmp_path, monkeypatch)
        (tmp_path / ".apmrc").write_text(
            "registry=https://test.io\ndefault-client=claude\n"
        )

        from click.testing import CliRunner

        from apm_cli.commands.config import config

        runner = CliRunner()
        result = runner.invoke(config, ["delete", "registry"])
        assert result.exit_code == 0
        content = (tmp_path / ".apmrc").read_text()
        assert "registry" not in content
        assert "default-client=claude" in content

    def test_config_delete_nonexistent_key_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._setup(tmp_path, monkeypatch)
        (tmp_path / ".apmrc").write_text("registry=https://test.io\n")

        from click.testing import CliRunner

        from apm_cli.commands.config import config

        runner = CliRunner()
        result = runner.invoke(config, ["delete", "nonexistent"])
        assert result.exit_code != 0

    def test_config_set_updates_existing_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._setup(tmp_path, monkeypatch)
        (tmp_path / ".apmrc").write_text("registry=https://old.io\n")

        from click.testing import CliRunner

        from apm_cli.commands.config import config

        runner = CliRunner()
        result = runner.invoke(config, ["set", "registry", "https://new.io"])
        assert result.exit_code == 0
        content = (tmp_path / ".apmrc").read_text()
        assert "https://new.io" in content
        assert "https://old.io" not in content


# ===========================================================================
# TestFilePermissionWarning — Step 5a
# ===========================================================================


class TestFilePermissionWarning:
    def test_world_readable_warns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging
        import sys

        if sys.platform == "win32":
            pytest.skip("Permission checks not applicable on Windows")

        f = tmp_path / ".apmrc"
        f.write_text("registry=https://x.io\n")
        f.chmod(0o644)
        with caplog.at_level(logging.WARNING, logger="apm_cli.apmrc"):
            parse_file(f, env={})
        assert "permissive" in caplog.text.lower()

    def test_restricted_no_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging
        import sys

        if sys.platform == "win32":
            pytest.skip("Permission checks not applicable on Windows")

        f = tmp_path / ".apmrc"
        f.write_text("registry=https://x.io\n")
        f.chmod(0o600)
        with caplog.at_level(logging.WARNING, logger="apm_cli.apmrc"):
            parse_file(f, env={})
        assert "permissive" not in caplog.text.lower()

    def test_init_rc_creates_restricted_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sys

        if sys.platform == "win32":
            pytest.skip("Permission checks not applicable on Windows")

        from click.testing import CliRunner

        from apm_cli.commands.config import config

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        runner.invoke(config, ["init-rc"])
        mode = (tmp_path / ".apmrc").stat().st_mode & 0o777
        assert mode == 0o600


# ===========================================================================
# TestUnknownKeyWarning — Step 5c
# ===========================================================================


class TestUnknownKeyWarning:
    def test_unknown_key_warns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        f = tmp_path / ".apmrc"
        f.write_text("registy=https://typo.io\n")
        with caplog.at_level(logging.WARNING, logger="apm_cli.apmrc"):
            cfg = parse_file(f, env={})
        assert cfg.raw.get("registy") == "https://typo.io"
        assert "unknown key" in caplog.text.lower()

    def test_known_key_no_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        f = tmp_path / ".apmrc"
        f.write_text("registry=https://x.io\n")
        with caplog.at_level(logging.WARNING, logger="apm_cli.apmrc"):
            parse_file(f, env={})
        assert "unknown key" not in caplog.text.lower()

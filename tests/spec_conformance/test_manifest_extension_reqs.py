"""req-ext-003: preserve top-level x-* keys and warn on other unknown keys.

Behavioral coverage also lives in tests/unit/test_manifest_extension_keys.py.
This module is the spec-conformance bind (column-0 req marker).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from apm_cli.deps.lockfile import LockedDependency, LockFile
from apm_cli.models.apm_package import APMPackage, clear_apm_yml_cache
from tests.spec_conformance._helpers import assert_spec_contains, load_schema

_WARN = "apm_cli.models.apm_package._rich_warning"


@pytest.mark.req("req-ext-003")
def test_parser_keeps_x_extensions_and_warns_without_failing(tmp_path: Path) -> None:
    """req-ext-003: x-* values are kept as declared; other unknown keys warn."""
    manifest = tmp_path / "apm.yml"
    manifest.write_text(
        "name: sample\nversion: 1.0.0\nx-zeta: 7\nx-alpha:\n  nested: keep\nmystery: 1\n",
        encoding="utf-8",
    )
    clear_apm_yml_cache()

    with patch(_WARN) as warned:
        package = APMPackage.from_apm_yml(manifest, create_config=False)

    assert package.name == "sample"
    assert list(package.extensions) == ["x-zeta", "x-alpha"]
    assert package.extensions["x-zeta"] == 7
    assert package.extensions["x-alpha"] == {"nested": "keep"}
    warned.assert_called_once()
    message = warned.call_args[0][0]
    assert "mystery" in message
    assert "x-zeta" not in message
    assert "x-alpha" not in message


@pytest.mark.req("req-ext-003")
def test_lock_entry_records_extensions_and_omits_when_empty() -> None:
    """req-ext-003: extensions is recorded, ordered, and omitted when empty."""
    recorded = LockedDependency(
        repo_url="owner/sample",
        extensions={"x-zeta": 7, "x-alpha": {"nested": "keep"}},
    )
    rendered = LockFile(dependencies={"owner/sample": recorded}).to_yaml()
    assert rendered.index("extensions:") < rendered.index("x-zeta:")
    assert rendered.index("x-zeta:") < rendered.index("x-alpha:")
    restored = LockFile.from_yaml(rendered).get_package_dependencies()[0]
    assert list(restored.extensions) == ["x-zeta", "x-alpha"]
    assert restored.extensions["x-alpha"] == {"nested": "keep"}

    empty = LockedDependency(repo_url="owner/sample")
    assert "extensions" not in empty.to_dict()
    empty_yaml = LockFile(dependencies={"owner/sample": empty}).to_yaml()
    assert "extensions:" not in empty_yaml

    entry_props = load_schema("lockfile-v0.1.41.schema.json")["$defs"]["entry"]["properties"]
    assert entry_props["extensions"]["type"] == "object"


@pytest.mark.req("req-ext-003")
def test_req_ext_003_keeps_rewrite_preservation() -> None:
    """req-ext-003 must not contradict the writer preserve-unknown-keys rule."""
    assert_spec_contains(
        "prefix `x-`",
        "optional `extensions`",
        "non-failing warning",
        "does not relax",
        "[req-mf-006](#req-mf-006)",
    )

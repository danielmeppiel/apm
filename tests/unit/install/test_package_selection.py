"""Pure selected-package identity normalization and raw-selector fallback."""

import pytest

from apm_cli.install.package_selection import selected_dependency_keys
from apm_cli.models.dependency.reference import DependencyReference

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("error", [ValueError, TypeError])
def test_selected_keys_preserve_failed_selector_without_losing_valid_keys(
    monkeypatch: pytest.MonkeyPatch, error: type[Exception]
) -> None:
    original_parse = DependencyReference.parse

    def parse(spec: str) -> DependencyReference:
        if spec == "INVALID_REF_NO_SLASH":
            raise error("invalid selector")
        return original_parse(spec)

    monkeypatch.setattr(DependencyReference, "parse", parse)
    assert selected_dependency_keys(["org/pkg#main", "INVALID_REF_NO_SLASH"]) == {
        "org/pkg",
        "INVALID_REF_NO_SLASH",
    }

"""Marketplace manifest validation.

Provides validation functions for marketplace.json integrity checking.
Used by ``apm marketplace validate`` and potentially by ``apm marketplace publish``.

All validators operate on parsed ``MarketplaceManifest`` / ``MarketplacePlugin``
objects. The JSON parser (``models.py``) already drops entries that are
structurally unrecognizable; these validators enforce additional business
rules on the successfully parsed entries.
"""

import re
from dataclasses import dataclass, field
from typing import List, Sequence

from .models import MarketplaceManifest, MarketplacePlugin

# Strict semver: X.Y.Z with integer components only (matches version_resolver).
_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    check_name: str
    passed: bool
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def validate_marketplace(
    manifest: MarketplaceManifest,
) -> List[ValidationResult]:
    """Run all validation checks on a marketplace manifest.

    Returns a list of ``ValidationResult`` objects, one per check.
    """
    plugins = manifest.plugins
    return [
        validate_plugin_schema(plugins),
        validate_version_format(plugins),
        validate_no_duplicate_versions(plugins),
        validate_no_duplicate_names(plugins),
    ]


def validate_plugin_schema(
    plugins: Sequence[MarketplacePlugin],
) -> ValidationResult:
    """Check all plugins have required fields (name, source)."""
    errors: List[str] = []
    for plugin in plugins:
        if not plugin.name or not plugin.name.strip():
            errors.append("Plugin entry has empty name")
        if plugin.source is None:
            errors.append(
                f"Plugin '{plugin.name}' is missing required field 'source'"
            )
    return ValidationResult(
        check_name="Schema",
        passed=len(errors) == 0,
        errors=errors,
    )


def validate_version_format(
    plugins: Sequence[MarketplacePlugin],
) -> ValidationResult:
    """Check all version entries have valid semver and non-empty ref."""
    warnings: List[str] = []
    errors: List[str] = []
    for plugin in plugins:
        for entry in plugin.versions:
            ver = entry.version.strip() if entry.version else ""
            ref = entry.ref.strip() if entry.ref else ""
            if ver and not _SEMVER_RE.match(ver):
                warnings.append(
                    f"Plugin '{plugin.name}' version '{entry.version}' "
                    f"is not valid semver (expected X.Y.Z)"
                )
            if not ref:
                errors.append(
                    f"Plugin '{plugin.name}' version '{entry.version}' "
                    f"has empty ref"
                )
    return ValidationResult(
        check_name="Versions",
        passed=len(errors) == 0 and len(warnings) == 0,
        warnings=warnings,
        errors=errors,
    )


def validate_no_duplicate_versions(
    plugins: Sequence[MarketplacePlugin],
) -> ValidationResult:
    """Check no plugin has duplicate version strings."""
    warnings: List[str] = []
    for plugin in plugins:
        seen: dict = {}
        for entry in plugin.versions:
            normalized = entry.version.strip()
            if normalized in seen:
                warnings.append(
                    f"Plugin '{plugin.name}' has duplicate version "
                    f"'{normalized}'"
                )
            else:
                seen[normalized] = True
    return ValidationResult(
        check_name="Duplicate versions",
        passed=len(warnings) == 0,
        warnings=warnings,
    )


def validate_no_duplicate_names(
    plugins: Sequence[MarketplacePlugin],
) -> ValidationResult:
    """Check no two plugins share the same name (case-insensitive)."""
    errors: List[str] = []
    seen: dict = {}
    for plugin in plugins:
        lower = plugin.name.strip().lower()
        if lower in seen:
            errors.append(
                f"Duplicate plugin name: '{plugin.name}' "
                f"(conflicts with '{seen[lower]}')"
            )
        else:
            seen[lower] = plugin.name
    return ValidationResult(
        check_name="Names",
        passed=len(errors) == 0,
        errors=errors,
    )

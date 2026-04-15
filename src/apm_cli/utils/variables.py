"""Package variable substitution for deployed primitives.

Resolves ``${var:name}`` placeholders in primitive files at install time.
Variables are declared in a package's ``apm.yml`` and can be overridden
by the consuming project's ``apm.yml``.

Resolution order (highest priority first):
1. Consumer's ``apm.yml`` ``variables.<package-name>.<var-name>``
2. Package's ``apm.yml`` ``variables.<var-name>.default``
3. Leave ``${var:...}`` as-is (with a warning)
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Pattern matches ${var:name} where name is alphanumeric with hyphens/underscores
VAR_PATTERN = re.compile(r'\$\{var:([a-zA-Z0-9_-]+)\}')

# File extensions eligible for variable substitution
_TEXT_EXTENSIONS = frozenset({
    ".md", ".yml", ".yaml", ".json", ".toml", ".txt",
})


@dataclass
class PackageVariable:
    """Definition of a package variable declared in apm.yml."""

    description: Optional[str] = None
    default: Optional[str] = None
    required: bool = False


def parse_package_variables(
    raw: Optional[Dict[str, Any]],
) -> Dict[str, PackageVariable]:
    """Parse the ``variables`` section from a package's own ``apm.yml``.

    Accepts both shorthand (string value = default) and full object form.

    Returns:
        Mapping of variable name to PackageVariable.
    """
    if not raw:
        return {}
    result: Dict[str, PackageVariable] = {}
    for name, value in raw.items():
        if isinstance(value, str):
            result[name] = PackageVariable(default=value)
        elif isinstance(value, dict):
            result[name] = PackageVariable(
                description=value.get("description"),
                default=value.get("default"),
                required=bool(value.get("required", False)),
            )
        else:
            logger.warning("Ignoring variable '%s': unsupported type %s", name, type(value).__name__)
    return result


def parse_consumer_overrides(
    raw: Optional[Dict[str, Any]],
) -> Dict[str, Dict[str, str]]:
    """Parse the ``variables`` section from a consumer's ``apm.yml``.

    The consumer format is keyed by package name::

        variables:
          tdd-development:
            stack-profile: stack-ios-swift

    Returns:
        Mapping of package-name to variable-name -> override-value.
    """
    if not raw:
        return {}
    result: Dict[str, Dict[str, str]] = {}
    for pkg_name, overrides in raw.items():
        if isinstance(overrides, dict):
            result[pkg_name] = {
                k: str(v) for k, v in overrides.items() if isinstance(v, (str, int, float, bool))
            }
    return result


def resolve_package_variables(
    package_name: str,
    package_variables: Dict[str, PackageVariable],
    consumer_overrides: Dict[str, Dict[str, str]],
) -> tuple:
    """Resolve variables for a single package.

    Args:
        package_name: Name of the package being installed.
        package_variables: Variable definitions from the package's apm.yml.
        consumer_overrides: All consumer overrides (keyed by package name).

    Returns:
        Tuple of (resolved_dict, warnings, errors) where:
        - resolved_dict maps variable name to resolved value
        - warnings is a list of warning messages
        - errors is a list of error messages (required variables missing)
    """
    resolved: Dict[str, str] = {}
    warnings: List[str] = []
    errors: List[str] = []

    pkg_overrides = consumer_overrides.get(package_name, {})

    for var_name, var_def in package_variables.items():
        if var_name in pkg_overrides:
            resolved[var_name] = pkg_overrides[var_name]
        elif var_def.default is not None:
            resolved[var_name] = var_def.default
        elif var_def.required:
            errors.append(
                f"Required variable '{var_name}' for package '{package_name}' "
                f"has no default and no consumer override. "
                f"Add to your apm.yml: variables.{package_name}.{var_name}"
            )
        else:
            warnings.append(
                f"Variable '{var_name}' for package '{package_name}' is unresolved "
                f"-- ${{{var_name}}} placeholders will be left as-is"
            )

    # Consumer may also provide overrides for variables NOT declared by the
    # package.  Accept them silently -- they'll simply have no effect unless
    # the file content uses a matching placeholder.
    for var_name, value in pkg_overrides.items():
        if var_name not in resolved:
            resolved[var_name] = value

    return resolved, warnings, errors


def substitute_variables(content: str, variables: Dict[str, str]) -> str:
    """Replace ``${var:name}`` placeholders with resolved values.

    Unresolved placeholders are left as-is.
    """
    if not variables:
        return content

    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name in variables:
            return variables[var_name]
        return match.group(0)

    return VAR_PATTERN.sub(_replace, content)


def find_unresolved_variables(content: str) -> List[str]:
    """Return a list of ``${var:...}`` placeholders still present in *content*."""
    return VAR_PATTERN.findall(content)


def is_substitutable_file(path: Path) -> bool:
    """Return True if *path* is a text file eligible for variable substitution."""
    return path.suffix.lower() in _TEXT_EXTENSIONS


def substitute_variables_in_directory(
    directory: Path,
    variables: Dict[str, str],
) -> int:
    """Apply variable substitution to all eligible text files in *directory*.

    Used for skill directories that are bulk-copied via ``shutil.copytree``.

    Returns:
        Number of files modified.
    """
    if not variables:
        return 0
    modified = 0
    for file_path in directory.rglob("*"):
        if not file_path.is_file():
            continue
        if not is_substitutable_file(file_path):
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        new_content = substitute_variables(content, variables)
        if new_content != content:
            file_path.write_text(new_content, encoding="utf-8")
            modified += 1
    return modified

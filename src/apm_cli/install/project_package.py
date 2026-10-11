"""Synthetic package that stands for the project's own content."""

from __future__ import annotations

from pathlib import Path

from ..models.apm_package import APMPackage, PackageInfo, PackageType


def build_project_local_package_info(source_root: Path) -> PackageInfo:
    """Build the package install and audit replay integrate the project itself through.

    It is always an ``APM_PACKAGE``, so only the project's ``.apm/`` content is deployed and a
    sibling ``skills/`` folder or a root ``SKILL.md`` is not promoted as a skill.
    """
    local_pkg = APMPackage(
        name="_local",
        version="0.0.0",
        package_path=source_root,
        source="local",
    )
    return PackageInfo(
        package=local_pkg,
        install_path=source_root,
        package_type=PackageType.APM_PACKAGE,
    )

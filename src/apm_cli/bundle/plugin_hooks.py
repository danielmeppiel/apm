"""Relocate first-party hook resources without evaluating hook commands."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from apm_cli.hook_contract import walk_hook_commands
from apm_cli.integration.hook_bundle import (
    _HOOK_SCRIPT_EXTENSIONS,
    _hook_module_type,
    _hook_source_root,
    iter_deployable_hook_bundle_files,
)
from apm_cli.integration.hook_command_paths import (
    iter_plugin_root_paths,
    normalize_quoted_plugin_root,
    plugin_root_relative_path,
    relocated_plugin_root_reference,
)
from apm_cli.integration.hook_source_selection import resolve_plugin_root_hook_script
from apm_cli.utils.path_security import (
    PathTraversalError,
    ensure_path_within,
    validate_path_segments,
)
from apm_cli.utils.paths import portable_relpath

from .plugin_layout import PLUGIN_ROOT_DIRS


class PluginHookResources:
    """Project source hook paths through the exporter's selected component map."""

    def __init__(
        self,
        project_root: Path,
        components: list[tuple[Path, str]],
        *,
        includes: list[str] | None,
        descriptors: set[Path],
        output_path: Callable[[str], str | None],
    ) -> None:
        self.root = project_root
        self.components = components
        self.outputs = {source: relative for source, relative in components}
        self.includes = (
            tuple(project_root / relative for relative in includes)
            if includes is not None
            else None
        )
        self.descriptors = descriptors
        self.output_path = output_path
        self.generated: dict[str, str] = {}
        self.required: dict[str, Path] = {}
        self.visited_roots: set[Path] = set()

    def _selected(self, source: Path) -> bool:
        if self.includes is None:
            return not (
                (self.root / ".apm").is_dir()
                and source not in self.outputs
                and source.relative_to(self.root).parts[0] in PLUGIN_ROOT_DIRS
            )
        return any(
            source == selected or (selected.is_dir() and source.is_relative_to(selected))
            for selected in self.includes
        )

    def _validate_source(self, source: Path) -> None:
        """Require real source files under the package, including all ancestors."""
        try:
            ensure_path_within(source, self.root)
        except PathTraversalError as exc:
            raise ValueError(
                f"Hook resource escapes the package: {source}. "
                "Keep hook resources inside the package and pack again."
            ) from exc
        current = source
        while current != self.root:
            if current.is_symlink():
                raise ValueError(
                    f"Hook resource uses a symlink: {source}. "
                    "Replace it with a regular package file and pack again."
                )
            current = current.parent
        if not source.is_file():
            raise ValueError(
                f"Hook resource is missing: {source}. "
                "Restore the referenced file or correct the hook command and pack again."
            )

    def _add_resource(self, source: Path) -> str:
        self._validate_source(source)
        if not self._selected(source):
            raise ValueError(
                f"Hook resource is excluded by the selected layout or includes: "
                f"{portable_relpath(source, self.root)}. "
                "Add the resource to includes, move it into .apm/, or remove the hook reference."
            )
        relative = self.outputs.get(source)
        if relative is None:
            source_relative = portable_relpath(source, self.root)
            relative = self.output_path(source_relative) or source_relative
            if relative.startswith(".apm/"):
                raise ValueError(
                    f"Hook resource has no packed layout: {source_relative}. "
                    "Move it under the selected hooks or primitive directory."
                )
            self.components.append((source, relative))
            self.outputs[source] = relative
        if relative in self.required and self.required[relative] != source:
            raise ValueError(
                f"Hook resource collision at {relative}. "
                "Give the referenced resources distinct packed paths and pack again."
            )
        self.required[relative] = source
        return relative

    def _collect_bundle(self, source: Path, descriptor: Path) -> None:
        source_root = _hook_source_root(
            self.root, descriptor.parent if descriptor.parent != self.root else None, source
        )
        if source_root in self.visited_roots:
            return
        self.visited_roots.add(source_root)
        # A root-level script does not grant publication of the whole repository.
        if source_root == self.root:
            return
        assets = list(
            iter_deployable_hook_bundle_files(
                source_root,
                descriptor_files=self.descriptors,
                include_package_metadata=True,
            )
        )
        selected_assets = [asset for asset in assets if self._selected(asset)]
        for asset in selected_assets:
            self._add_resource(asset)
        if any(asset.suffix.lower() in _HOOK_SCRIPT_EXTENSIONS for asset in selected_assets):
            module_source = source_root / "package.json"
            relative = self.output_path(portable_relpath(module_source, self.root))
            if relative is not None and module_source not in self.outputs:
                if module_source.exists() or module_source.is_symlink():
                    self._add_resource(module_source)
                else:
                    self.generated[relative] = (
                        json.dumps({"type": _hook_module_type(self.root, source_root)}, indent=2)
                        + "\n"
                    )

    def rewrite(self, data: dict, descriptor: Path) -> dict:
        """Rewrite only canonical command fields, preserving all hook semantics."""
        self._validate_source(descriptor)
        for declaration in walk_hook_commands(data):
            command = normalize_quoted_plugin_root(declaration.command)
            rewritten = command
            for match in reversed(list(iter_plugin_root_paths(command))):
                relative = plugin_root_relative_path(match.group(1))
                try:
                    validate_path_segments(relative, context="Hook resource")
                    source = resolve_plugin_root_hook_script(
                        self.root, relative, hook_file_dir=descriptor.parent
                    )
                except PathTraversalError as exc:
                    raise ValueError(
                        f"Hook resource path is unsafe: {relative}. "
                        "Use a contained package-relative path and pack again."
                    ) from exc
                output = self._add_resource(source)
                self._collect_bundle(source, descriptor)
                replacement = relocated_plugin_root_reference(match, output)
                rewritten = rewritten[: match.start()] + replacement + rewritten[match.end() :]
            cursor = data
            pointer = declaration.json_pointer.split("/")[1:]
            for token in pointer[:-1]:
                decoded = token.replace("~1", "/").replace("~0", "~")
                cursor = cursor[int(decoded)] if isinstance(cursor, list) else cursor[decoded]
            cursor[declaration.key] = rewritten
        return data

    def validate_outputs(
        self, file_map: dict[str, tuple[Path, str]], *, reserved: set[str]
    ) -> None:
        """Refuse a hook whose resource lost the exporter's collision decision."""
        for relative, source in self.required.items():
            if relative in reserved:
                raise ValueError(
                    f"Hook resource conflicts with generated output: {relative}. "
                    "Move the resource to a non-reserved path and pack again."
                )
            if relative not in file_map or file_map[relative][0] != source:
                raise ValueError(
                    f"Hook resource collision at {relative}. "
                    "Rename the conflicting resource or use --force to select this package."
                )
        for relative in self.generated:
            if relative in file_map:
                raise ValueError(
                    f"Hook resource metadata collides at {relative}. "
                    "Remove the conflicting package metadata and pack again."
                )

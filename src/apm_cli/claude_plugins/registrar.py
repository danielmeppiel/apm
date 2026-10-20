"""Single reconciliation owner for APM's native Claude user marketplace.

Claude owns its settings, cache and installed-plugin registry. APM writes
only a directory catalog and a recoverable intent ledger in apm_modules.
Native operations are not a byte-rollback transaction: a retry checks live
state against intent before continuing a partially completed reconciliation.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from apm_cli.core.scope import is_user_scope
from apm_cli.utils.atomic_io import atomic_write_text
from apm_cli.utils.path_security import ensure_path_within, has_symlink_component
from apm_cli.utils.paths import portable_relpath

from .admission import ClaudeNativePlugin, ClaudeNativePluginError
from .client import ClaudePluginCLI

MARKETPLACE_NAME = "apm-claude"
CATALOG_RELATIVE = ".claude-plugin/marketplace.json"
LEDGER_RELATIVE = ".claude-plugin/apm-registration.json"


def _read_ledger(path: Path, modules_dir: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        entries = document["plugins"]
        if document["version"] != 1 or document["marketplace"] != MARKETPLACE_NAME:
            raise ValueError("unsupported ledger")
        if not isinstance(entries, dict):
            raise ValueError("invalid plugin map")
        for plugin_id, entry in entries.items():
            if (
                not isinstance(plugin_id, str)
                or not plugin_id.endswith("@" + MARKETPLACE_NAME)
                or not isinstance(entry, dict)
                or set(entry) != {"dependency_key", "source"}
                or not all(isinstance(value, str) and value for value in entry.values())
            ):
                raise ValueError("invalid plugin ownership")
            ensure_path_within(modules_dir / entry["source"], modules_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ClaudeNativePluginError(
            "Cannot safely read APM's Claude ownership ledger; refusing native state changes."
        ) from exc
    return entries


def _write_ledger(path: Path, entries: dict[str, dict[str, str]]) -> None:
    atomic_write_text(
        path,
        json.dumps(
            {
                "version": 1,
                "marketplace": MARKETPLACE_NAME,
                "plugins": entries,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )


def _plugin_rows(client: ClaudePluginCLI) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in client.records("plugin", "list", "--json"):
        plugin_id = row.get("id")
        if not isinstance(plugin_id, str):
            raise ClaudeNativePluginError("Claude plugin metadata has no plugin identity.")
        if not plugin_id.endswith("@" + MARKETPLACE_NAME):
            continue
        if row.get("scope") != "user" or plugin_id in result:
            raise ClaudeNativePluginError("APM Claude plugin identity collides with another scope.")
        if not isinstance(row.get("enabled"), bool):
            raise ClaudeNativePluginError("Claude plugin metadata has no explicit enabled state.")
        result[plugin_id] = row
    return result


def _check_live_root(
    row: dict[str, Any],
    entry: dict[str, str],
    modules_dir: Path,
) -> None:
    root = row.get("readFromFolder")
    if (
        not isinstance(root, str)
        or Path(root).resolve() != (modules_dir / entry["source"]).resolve()
    ):
        raise ClaudeNativePluginError(
            "Claude native plugin source ownership changed; refusing to adopt or overwrite it."
        )


def synchronize_claude_plugins(
    *,
    modules_dir: Path,
    scope: Any,
    plugins: Sequence[ClaudeNativePlugin],
    logger: Any = None,
    dry_run: bool = False,
) -> None:
    """Reconcile only owned metadata, preserving native consent and user state."""
    if not is_user_scope(scope) or dry_run:
        return
    modules_dir = Path(modules_dir).absolute()
    catalog = modules_dir / CATALOG_RELATIVE
    ledger = modules_dir / LEDGER_RELATIVE
    if not plugins and not ledger.exists():
        return
    for path in (catalog, ledger):
        ensure_path_within(path, modules_dir)
        if has_symlink_component(modules_dir, path):
            raise ClaudeNativePluginError("Refusing symlinked native Claude registration files.")
    previous = _read_ledger(ledger, modules_dir)
    if catalog.exists() and not ledger.exists():
        raise ClaudeNativePluginError("Claude marketplace catalog is not owned by APM.")

    desired: dict[str, dict[str, str]] = {}
    for plugin in plugins:
        ensure_path_within(plugin.source_root, modules_dir)
        plugin_id = f"{plugin.name}@{MARKETPLACE_NAME}"
        entry = {
            "dependency_key": plugin.dependency_key,
            "source": portable_relpath(plugin.source_root, modules_dir),
        }
        if plugin_id in desired or (plugin_id in previous and previous[plugin_id] != entry):
            raise ClaudeNativePluginError(
                f"Native Claude plugin name collision: {plugin.name}. Use distinct plugin names."
            )
        desired[plugin_id] = entry

    client = ClaudePluginCLI()
    client.check_version()
    marketplaces = client.records("plugin", "marketplace", "list", "--json")
    registered = [row for row in marketplaces if row.get("name") == MARKETPLACE_NAME]
    if len(registered) > 1 or (
        registered
        and (
            not ledger.exists()
            or registered[0].get("source") != "directory"
            or not isinstance(registered[0].get("path"), str)
            or Path(registered[0]["path"]).resolve() != modules_dir.resolve()
        )
    ):
        raise ClaudeNativePluginError(
            "The apm-claude marketplace is already owned by another source. "
            "Resolve the collision in Claude before installing."
        )
    live = _plugin_rows(client)
    for plugin_id, row in live.items():
        if plugin_id not in previous:
            raise ClaudeNativePluginError(
                "The apm-claude marketplace contains an unowned plugin; refusing to mutate it."
            )
        _check_live_root(row, previous[plugin_id], modules_dir)

    catalog.parent.mkdir(parents=True, exist_ok=True)
    # Intent precedes foreign writes. Preserve retiring identities until the
    # native CLI confirms removal, including when a previous attempt crashed.
    _write_ledger(ledger, previous | desired)
    for plugin_id in sorted(set(previous) - set(desired)):
        if plugin_id in live:
            client.run("plugin", "uninstall", plugin_id, "--scope", "user", "--keep-data")
    atomic_write_text(
        catalog,
        json.dumps(
            {
                "name": MARKETPLACE_NAME,
                "owner": {"name": "APM"},
                "plugins": [
                    {
                        "name": plugin_id.split("@", 1)[0],
                        "source": "./" + entry["source"],
                        "defaultEnabled": False,
                    }
                    for plugin_id, entry in sorted(desired.items())
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    if desired and not registered:
        client.run("plugin", "marketplace", "add", str(modules_dir), "--scope", "user")
    for plugin_id in sorted(desired):
        operation = "update" if plugin_id in live else "install"
        client.run("plugin", operation, plugin_id, "--scope", "user")
    after = _plugin_rows(client)
    if set(after) != set(desired):
        raise ClaudeNativePluginError(
            "Claude did not converge to the requested plugin registration. "
            "APM retained its intent ledger; rerun apm install --global."
        )
    for plugin_id, entry in desired.items():
        _check_live_root(after[plugin_id], entry, modules_dir)
        expected_enabled = live[plugin_id]["enabled"] if plugin_id in live else False
        if after[plugin_id]["enabled"] != expected_enabled:
            raise ClaudeNativePluginError(
                "Claude changed a plugin's native activation state unexpectedly. "
                "Review it in Claude; APM will not override native user consent."
            )
    _write_ledger(ledger, desired)
    if logger and desired:
        logger.tree_item(
            f"{len(desired)} native Claude plugin(s) registered; existing activation preserved. "
            "New plugins are disabled. Review and enable them in Claude; restart or "
            "reload plugins there. Hook execution has not been verified by this install."
        )


def resync_claude_plugins(
    *,
    modules_dir: Path,
    scope: Any,
    lockfile: Any,
    targets: list[Any] | None = None,
    prepared: dict[str, ClaudeNativePlugin] | None = None,
    allow_executables: dict[str, dict[str, bool]] | None = None,
    logger: Any = None,
    dry_run: bool = False,
) -> None:
    """Reconcile canonical locked survivors; never admit an unscanned new plugin.

    Install supplies freshly admitted plans. Uninstall retains only identities
    already owned, intersected with the surviving lockfile and its trust state.
    """
    from apm_cli.copilot_plugins.registrar import candidates_from_lockfile
    from apm_cli.install.deployable_source_plan import DeployableSourcePlan
    from apm_cli.install.exec_gate import check_executable_approval
    from apm_cli.install.target_filter import resolve_effective_package_targets
    from apm_cli.integration.targets import KNOWN_TARGETS
    from apm_cli.models.apm_package import APMPackage, PackageInfo, PackageType
    from apm_cli.utils.content_hash import compute_package_hash

    from .admission import plan_native_claude_plugin

    if not is_user_scope(scope) or dry_run:
        return
    modules_dir = Path(modules_dir).absolute()
    ledger = modules_dir / LEDGER_RELATIVE
    if not prepared and not ledger.exists():
        return
    if has_symlink_component(modules_dir, ledger):
        raise ClaudeNativePluginError("Refusing symlinked native Claude ownership ledger.")
    previous = _read_ledger(ledger, modules_dir)
    known_keys = {entry["dependency_key"] for entry in previous.values()} | set(prepared or {})
    plans: list[ClaudeNativePlugin] = []
    for candidate in candidates_from_lockfile(lockfile, modules_dir):
        key = candidate.dependency_key
        if key not in known_keys:
            continue
        locked = lockfile.dependencies[key]
        root = candidate.install_path
        manifest = root / "apm.yml"
        package = APMPackage.from_apm_yml(manifest, source_path=root)
        info = PackageInfo(
            package=package,
            install_path=root,
            dependency_ref=locked.to_dependency_ref(),
            package_type=PackageType(locked.package_type),
        )
        resolved_targets = targets if targets is not None else [KNOWN_TARGETS["claude"]]
        selection = resolve_effective_package_targets(
            resolved_targets,
            candidate.target_subset,
            info,
            None,
            key,
        )
        hooks_approved, *_ = check_executable_approval(key, info, allow_executables)
        plan = plan_native_claude_plugin(
            info,
            package_name=key,
            targets=list(selection.targets),
            scope=scope,
            skill_subset=tuple(info.dependency_ref.skill_subset or ()) or None,
            hooks_approved=hooks_approved,
            skip_bin=True,
        )
        if plan is None:
            continue
        DeployableSourcePlan.create(
            info,
            list(selection.targets),
            skill_subset=None,
            hooks_approved=hooks_approved,
            canvas_approved=False,
            skip_bin=True,
            native_plugin_root=plan.source_root,
        )
        if locked.content_hash and compute_package_hash(root) != locked.content_hash:
            raise ClaudeNativePluginError(
                f"Native Claude source integrity changed for {key}; refusing registration."
            )
        if prepared and key in prepared and prepared[key] != plan:
            raise ClaudeNativePluginError(
                "Native Claude source changed after deployment admission."
            )
        plans.append(plan)
    synchronize_claude_plugins(
        modules_dir=modules_dir,
        scope=scope,
        plugins=plans,
        logger=logger,
        dry_run=dry_run,
    )

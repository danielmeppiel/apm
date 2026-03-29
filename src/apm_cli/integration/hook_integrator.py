"""Hook integration functionality for APM packages.

Integrates hook JSON files and their referenced scripts during package
installation. Supports VSCode Copilot (.github/hooks/), Claude Code
(.claude/settings.json), and Cursor (.cursor/hooks.json) targets.

Hook JSON format (Claude Code  -- nested matcher groups):
    {
        "hooks": {
            "PreToolUse": [
                {
                    "hooks": [
                        {"type": "command", "command": "./scripts/validate.sh", "timeout": 10}
                    ]
                }
            ]
        }
    }

Hook JSON format (GitHub Copilot  -- flat arrays with bash/powershell keys):
    {
        "version": 1,
        "hooks": {
            "preToolUse": [
                {"type": "command", "bash": "./scripts/validate.sh", "timeoutSec": 10}
            ]
        }
    }

Hook JSON format (Cursor  -- flat arrays with command key):
    {
        "hooks": {
            "afterFileEdit": [
                {"command": "./hooks/format.sh"}
            ]
        }
    }

Script path handling:
    - ${CLAUDE_PLUGIN_ROOT}/path -> resolved relative to package root, rewritten for target
    - ./path -> relative path, resolved from hook file's parent directory, rewritten for target
    - System commands (no path separators) -> passed through unchanged
"""

import json
import re
import shutil
from pathlib import Path
from typing import Any, List, Dict, Tuple, Optional
from dataclasses import dataclass, field

from apm_cli.integration.base_integrator import BaseIntegrator
from apm_cli.utils.paths import portable_relpath


@dataclass
class HookIntegrationResult:
    """Result of hook integration operation."""
    hooks_integrated: int
    scripts_copied: int
    target_paths: List[Path] = field(default_factory=list)
    display_payloads: List[Dict[str, Any]] = field(default_factory=list)


class HookIntegrator(BaseIntegrator):
    """Handles integration of APM package hooks into target locations.

    Discovers hook JSON files and their referenced scripts from packages,
    then installs them to the appropriate target location:
    - VSCode: .github/hooks/<pkg>-<name>.json + .github/hooks/scripts/<pkg>/
    - Claude: Merged into .claude/settings.json hooks key + .claude/hooks/<pkg>/
    - Cursor: Merged into .cursor/hooks.json hooks key + .cursor/hooks/<pkg>/
    """

    @staticmethod
    def _iter_hook_entries(payload: Dict) -> List[Tuple[str, Dict]]:
        """Flatten hook payloads into ``(event_name, entry_dict)`` pairs."""
        entries: List[Tuple[str, Dict]] = []
        hooks = payload.get("hooks", {})
        if not isinstance(hooks, dict):
            return entries

        for event_name, matchers in hooks.items():
            if not isinstance(matchers, list):
                continue
            for matcher in matchers:
                if not isinstance(matcher, dict):
                    continue

                for key in ("command", "bash", "powershell"):
                    value = matcher.get(key)
                    if isinstance(value, str):
                        entries.append((event_name, {key: value}))

                nested_hooks = matcher.get("hooks", [])
                if not isinstance(nested_hooks, list):
                    continue
                for hook in nested_hooks:
                    if not isinstance(hook, dict):
                        continue
                    for key in ("command", "bash", "powershell"):
                        value = hook.get(key)
                        if isinstance(value, str):
                            entries.append((event_name, {key: value}))
        return entries

    @staticmethod
    def _summarize_command(entry: Dict) -> str:
        """Return a human-readable summary for a single hook command entry."""
        command = ""
        for key in ("command", "bash", "powershell"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                command = value.strip()
                break

        if not command:
            return "runs hook command"

        for token in command.split():
            cleaned = token.strip("\"'")
            if "/" in cleaned or cleaned.startswith("."):
                return f"runs {cleaned}"

        return f"runs {command}"

    def _build_display_payload(self, target_label: str, output_path: str, source_hook_file: Path, rewritten: Dict) -> Dict[str, Any]:
        """Build CLI display metadata for an integrated hook file."""
        actions = []
        for event_name, entry in self._iter_hook_entries(rewritten):
            actions.append({
                "event": event_name,
                "summary": self._summarize_command(entry),
            })

        return {
            "target_label": target_label,
            "output_path": output_path,
            "source_hook_file": source_hook_file.name,
            "actions": actions,
            "rendered_json": json.dumps(rewritten, indent=2, sort_keys=True),
        }

    def find_hook_files(self, package_path: Path) -> List[Path]:
        """Find all hook JSON files in a package.

        Searches in:
        - .apm/hooks/ subdirectory (APM convention)
        - hooks/ subdirectory (Claude-native convention)

        Args:
            package_path: Path to the package directory

        Returns:
            List[Path]: List of absolute paths to hook JSON files
        """
        hook_files = []
        seen = set()

        # Search in .apm/hooks/ (APM convention)
        apm_hooks = package_path / ".apm" / "hooks"
        if apm_hooks.exists():
            for f in sorted(apm_hooks.glob("*.json")):
                resolved = f.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    hook_files.append(f)

        # Search in hooks/ (Claude-native convention)
        hooks_dir = package_path / "hooks"
        if hooks_dir.exists():
            for f in sorted(hooks_dir.glob("*.json")):
                resolved = f.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    hook_files.append(f)

        return hook_files

    def _parse_hook_json(self, hook_file: Path) -> Optional[Dict]:
        """Parse a hook JSON file and return the data dict.

        Args:
            hook_file: Path to the hook JSON file

        Returns:
            Optional[Dict]: Parsed JSON dict, or None if invalid
        """
        try:
            with open(hook_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return None
            return data
        except (json.JSONDecodeError, OSError):
            return None

    def _rewrite_command_for_target(
        self,
        command: str,
        package_path: Path,
        package_name: str,
        target: str,
        hook_file_dir: Optional[Path] = None,
    ) -> Tuple[str, List[Tuple[Path, str]]]:
        """Rewrite a hook command to use installed script paths.

        Handles:
        - ${CLAUDE_PLUGIN_ROOT}/path references (resolved from package root)
        - ./path relative references (resolved from hook file's parent directory)

        Args:
            command: Original command string
            package_path: Root path of the source package
            package_name: Name used for the scripts subdirectory
            target: "vscode" or "claude"
            hook_file_dir: Directory containing the hook JSON file (for ./path resolution)

        Returns:
            Tuple of (rewritten_command, list of (source_file, relative_target_path))
        """
        scripts_to_copy = []
        new_command = command

        if target == "vscode":
            scripts_base = f".github/hooks/scripts/{package_name}"
        elif target == "cursor":
            scripts_base = f".cursor/hooks/{package_name}"
        else:
            scripts_base = f".claude/hooks/{package_name}"

        # Handle ${CLAUDE_PLUGIN_ROOT} references (always relative to package root)
        plugin_root_pattern = r'\$\{CLAUDE_PLUGIN_ROOT\}(/[^\s]+)'
        for match in re.finditer(plugin_root_pattern, command):
            full_var = match.group(0)
            rel_path = match.group(1).lstrip('/')

            source_file = (package_path / rel_path).resolve()
            # Reject path traversal outside the package directory
            if not source_file.is_relative_to(package_path.resolve()):
                continue
            if source_file.exists() and source_file.is_file():
                target_rel = f"{scripts_base}/{rel_path}"
                scripts_to_copy.append((source_file, target_rel))
                new_command = new_command.replace(full_var, target_rel)

        # Handle relative ./path references (safe to run after ${CLAUDE_PLUGIN_ROOT}
        # substitution since replacements produce paths like ".github/..." not "./...")
        # Resolve from hook file's directory if available, else fall back to package root
        resolve_base = hook_file_dir if hook_file_dir else package_path
        rel_pattern = r'(\./[^\s]+)'
        for match in re.finditer(rel_pattern, new_command):
            rel_ref = match.group(1)
            rel_path = rel_ref[2:]  # Strip ./

            source_file = (resolve_base / rel_path).resolve()
            # Reject path traversal outside the package directory
            if not source_file.is_relative_to(package_path.resolve()):
                continue
            if source_file.exists() and source_file.is_file():
                target_rel = f"{scripts_base}/{rel_path}"
                scripts_to_copy.append((source_file, target_rel))
                new_command = new_command.replace(rel_ref, target_rel)

        return new_command, scripts_to_copy

    def _rewrite_hooks_data(
        self,
        data: Dict,
        package_path: Path,
        package_name: str,
        target: str,
        hook_file_dir: Optional[Path] = None,
    ) -> Tuple[Dict, List[Tuple[Path, str]]]:
        """Rewrite all command paths in a hooks JSON structure.

        Creates a deep copy and rewrites command paths for the target platform.

        Args:
            data: Parsed hook JSON data
            package_path: Root path of the source package
            package_name: Name for scripts subdirectory
            target: "vscode" or "claude"
            hook_file_dir: Directory containing the hook JSON file (for ./path resolution)

        Returns:
            Tuple of (rewritten_data_copy, list of (source_file, target_rel_path))
        """
        import copy
        rewritten = copy.deepcopy(data)
        all_scripts: List[Tuple[Path, str]] = []

        hooks = rewritten.get("hooks", {})
        for event_name, matchers in hooks.items():
            if not isinstance(matchers, list):
                continue
            for matcher in matchers:
                if not isinstance(matcher, dict):
                    continue
                # Rewrite script paths in the matcher dict itself
                # (GitHub Copilot flat format: bash/powershell keys at this level)
                for key in ("command", "bash", "powershell"):
                    if key in matcher:
                        new_cmd, scripts = self._rewrite_command_for_target(
                            matcher[key], package_path, package_name, target,
                            hook_file_dir=hook_file_dir,
                        )
                        matcher[key] = new_cmd
                        all_scripts.extend(scripts)

                # Rewrite script paths in nested hooks array
                # (Claude format: matcher groups with inner hooks array)
                for hook in matcher.get("hooks", []):
                    if not isinstance(hook, dict):
                        continue
                    for key in ("command", "bash", "powershell"):
                        if key in hook:
                            new_cmd, scripts = self._rewrite_command_for_target(
                                hook[key], package_path, package_name, target,
                                hook_file_dir=hook_file_dir,
                            )
                            hook[key] = new_cmd
                            all_scripts.extend(scripts)

        return rewritten, all_scripts

    def _get_package_name(self, package_info) -> str:
        """Get a short package name for use in file/directory naming.

        Args:
            package_info: PackageInfo object

        Returns:
            str: Package name derived from install path
        """
        return package_info.install_path.name

    def integrate_package_hooks(self, package_info, project_root: Path,
                                 force: bool = False,
                                 managed_files: set = None,
                                 diagnostics=None) -> HookIntegrationResult:
        """Integrate hooks from a package into .github/hooks/ (VSCode target).

        Deploys hook JSON files with clean filenames and copies referenced
        script files. Skips user-authored files unless force=True.

        Args:
            package_info: PackageInfo with package metadata and install path
            project_root: Root directory of the project
            force: If True, overwrite user-authored files on collision
            managed_files: Set of relative paths known to be APM-managed

        Returns:
            HookIntegrationResult: Results of the integration operation
        """
        hook_files = self.find_hook_files(package_info.install_path)

        if not hook_files:
            return HookIntegrationResult(
                hooks_integrated=0,
                scripts_copied=0,
            )

        hooks_dir = project_root / ".github" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)

        package_name = self._get_package_name(package_info)
        hooks_integrated = 0
        scripts_copied = 0
        target_paths: List[Path] = []
        display_payloads: List[Dict[str, Any]] = []

        for hook_file in hook_files:
            data = self._parse_hook_json(hook_file)
            if data is None:
                continue

            # Rewrite script paths for VSCode target
            rewritten, scripts = self._rewrite_hooks_data(
                data, package_info.install_path, package_name, "vscode",
                hook_file_dir=hook_file.parent,
            )

            # Generate target filename (clean, no -apm suffix)
            stem = hook_file.stem
            target_filename = f"{package_name}-{stem}.json"
            target_path = hooks_dir / target_filename
            rel_path = portable_relpath(target_path, project_root)

            if self.check_collision(target_path, rel_path, managed_files, force, diagnostics=diagnostics):
                continue

            # Write rewritten JSON
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(rewritten, f, indent=2)
                f.write('\n')

            hooks_integrated += 1
            target_paths.append(target_path)
            display_payloads.append(
                self._build_display_payload(
                    ".github/hooks/",
                    target_filename,
                    hook_file,
                    rewritten,
                )
            )

            # Copy referenced scripts (individual file tracking)
            for source_file, target_rel in scripts:
                target_script = project_root / target_rel
                if self.check_collision(target_script, target_rel, managed_files, force, diagnostics=diagnostics):
                    continue
                target_script.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, target_script)
                scripts_copied += 1
                target_paths.append(target_script)

        return HookIntegrationResult(
            hooks_integrated=hooks_integrated,
            scripts_copied=scripts_copied,
            target_paths=target_paths,
            display_payloads=display_payloads,
        )

    def integrate_package_hooks_claude(self, package_info, project_root: Path,
                                        force: bool = False,
                                        managed_files: set = None,
                                        diagnostics=None) -> HookIntegrationResult:
        """Integrate hooks from a package into .claude/settings.json (Claude target).

        Merges hook definitions into the Claude settings file and copies
        referenced script files. Tracks individual script files for
        manifest-based cleanup.

        Args:
            package_info: PackageInfo with package metadata and install path
            project_root: Root directory of the project
            force: If True, overwrite user-authored files on collision
            managed_files: Set of relative paths known to be APM-managed

        Returns:
            HookIntegrationResult: Results of the integration operation
        """
        hook_files = self.find_hook_files(package_info.install_path)

        if not hook_files:
            return HookIntegrationResult(
                hooks_integrated=0,
                scripts_copied=0,
            )

        package_name = self._get_package_name(package_info)
        hooks_integrated = 0
        scripts_copied = 0
        target_paths: List[Path] = []
        display_payloads: List[Dict[str, Any]] = []

        # Read existing settings
        settings_path = project_root / ".claude" / "settings.json"
        settings: Dict = {}
        if settings_path.exists():
            try:
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            except (json.JSONDecodeError, OSError):
                settings = {}

        if "hooks" not in settings:
            settings["hooks"] = {}

        for hook_file in hook_files:
            data = self._parse_hook_json(hook_file)
            if data is None:
                continue

            # Rewrite script paths for Claude target
            rewritten, scripts = self._rewrite_hooks_data(
                data, package_info.install_path, package_name, "claude",
                hook_file_dir=hook_file.parent,
            )

            # Merge hooks into settings (additive)
            hooks = rewritten.get("hooks", {})
            for event_name, matchers in hooks.items():
                if not isinstance(matchers, list):
                    continue
                if event_name not in settings["hooks"]:
                    settings["hooks"][event_name] = []

                # Mark each matcher with APM source for sync/cleanup
                for matcher in matchers:
                    if isinstance(matcher, dict):
                        matcher["_apm_source"] = package_name

                settings["hooks"][event_name].extend(matchers)

            hooks_integrated += 1
            display_payloads.append(
                self._build_display_payload(
                    ".claude/settings.json",
                    ".claude/settings.json",
                    hook_file,
                    rewritten,
                )
            )

            # Copy referenced scripts
            for source_file, target_rel in scripts:
                target_script = project_root / target_rel
                if self.check_collision(target_script, target_rel, managed_files, force, diagnostics=diagnostics):
                    continue
                target_script.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, target_script)
                scripts_copied += 1
                target_paths.append(target_script)

        # Write settings back
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
            f.write('\n')
        # Don't track settings.json in target_paths  -- it's a shared file
        # cleaned via _apm_source markers, not file-level deletion

        return HookIntegrationResult(
            hooks_integrated=hooks_integrated,
            scripts_copied=scripts_copied,
            target_paths=target_paths,
            display_payloads=display_payloads,
        )

    def integrate_package_hooks_cursor(self, package_info, project_root: Path,
                                        force: bool = False,
                                        managed_files: set = None,
                                        diagnostics=None) -> HookIntegrationResult:
        """Integrate hooks from a package into .cursor/hooks.json (Cursor target).

        Merges hook definitions into the Cursor hooks file and copies
        referenced script files. Tracks individual script files for
        manifest-based cleanup.

        Args:
            package_info: PackageInfo with package metadata and install path
            project_root: Root directory of the project
            force: If True, overwrite user-authored files on collision
            managed_files: Set of relative paths known to be APM-managed

        Returns:
            HookIntegrationResult: Results of the integration operation
        """
        # Only deploy when .cursor/ already exists (opt-in)
        cursor_dir = project_root / ".cursor"
        if not cursor_dir.exists():
            return HookIntegrationResult(
                hooks_integrated=0,
                scripts_copied=0,
            )

        hook_files = self.find_hook_files(package_info.install_path)

        if not hook_files:
            return HookIntegrationResult(
                hooks_integrated=0,
                scripts_copied=0,
            )

        package_name = self._get_package_name(package_info)
        hooks_integrated = 0
        scripts_copied = 0
        target_paths: List[Path] = []
        display_payloads: List[Dict[str, Any]] = []

        # Read existing hooks.json
        hooks_json_path = project_root / ".cursor" / "hooks.json"
        hooks_config: Dict = {}
        if hooks_json_path.exists():
            try:
                with open(hooks_json_path, 'r', encoding='utf-8') as f:
                    hooks_config = json.load(f)
            except (json.JSONDecodeError, OSError):
                hooks_config = {}

        if "hooks" not in hooks_config:
            hooks_config["hooks"] = {}

        for hook_file in hook_files:
            data = self._parse_hook_json(hook_file)
            if data is None:
                continue

            # Rewrite script paths for Cursor target
            rewritten, scripts = self._rewrite_hooks_data(
                data, package_info.install_path, package_name, "cursor",
                hook_file_dir=hook_file.parent,
            )

            # Merge hooks into hooks.json (additive)
            hooks = rewritten.get("hooks", {})
            for event_name, entries in hooks.items():
                if not isinstance(entries, list):
                    continue
                if event_name not in hooks_config["hooks"]:
                    hooks_config["hooks"][event_name] = []

                # Mark each entry with APM source for sync/cleanup
                for entry in entries:
                    if isinstance(entry, dict):
                        entry["_apm_source"] = package_name

                hooks_config["hooks"][event_name].extend(entries)

            hooks_integrated += 1
            display_payloads.append(
                self._build_display_payload(
                    ".cursor/hooks.json",
                    ".cursor/hooks.json",
                    hook_file,
                    rewritten,
                )
            )

            # Copy referenced scripts
            for source_file, target_rel in scripts:
                target_script = project_root / target_rel
                if self.check_collision(target_script, target_rel, managed_files, force, diagnostics=diagnostics):
                    continue
                target_script.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, target_script)
                scripts_copied += 1
                target_paths.append(target_script)

        # Write hooks.json back
        hooks_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(hooks_json_path, 'w', encoding='utf-8') as f:
            json.dump(hooks_config, f, indent=2)
            f.write('\n')
        # Don't track hooks.json in target_paths  -- it's a shared file
        # cleaned via _apm_source markers, not file-level deletion

        return HookIntegrationResult(
            hooks_integrated=hooks_integrated,
            scripts_copied=scripts_copied,
            target_paths=target_paths,
            display_payloads=display_payloads,
        )

    def sync_integration(self, apm_package, project_root: Path,
                          managed_files: set = None) -> Dict:
        """Remove APM-managed hook files.

        Uses *managed_files* (relative paths) to surgically remove only
        APM-tracked files.  Falls back to legacy ``*-apm.json`` glob when
        *managed_files* is ``None``.

        **Never** calls ``shutil.rmtree``.

        Also cleans APM entries from ``.claude/settings.json`` and
        ``.cursor/hooks.json`` via the ``_apm_source`` marker.
        """
        stats: Dict[str, int] = {'files_removed': 0, 'errors': 0}

        if managed_files is not None:
            # Manifest-based removal  -- only remove tracked files
            deleted: list = []
            for rel_path in managed_files:
                # Normalize path separators for cross-platform compatibility
                normalized = rel_path.replace("\\", "/")
                # Only handle hook-related paths
                is_hook = (
                    normalized.startswith(".github/hooks/")
                    or normalized.startswith(".claude/hooks/")
                    or normalized.startswith(".cursor/hooks/")
                )
                if not is_hook or ".." in rel_path:
                    continue
                target = project_root / rel_path
                if target.exists() and target.is_file():
                    try:
                        target.unlink()
                        stats['files_removed'] += 1
                        deleted.append(target)
                    except Exception:
                        stats['errors'] += 1
            # Batch parent cleanup  -- single bottom-up pass
            self.cleanup_empty_parents(deleted, stop_at=project_root)
        else:
            # Legacy fallback  -- glob for old -apm suffix files
            hooks_dir = project_root / ".github" / "hooks"
            if hooks_dir.exists():
                for hook_file in hooks_dir.glob("*-apm.json"):
                    try:
                        hook_file.unlink()
                        stats['files_removed'] += 1
                    except Exception:
                        stats['errors'] += 1

        # Clean APM entries from .claude/settings.json (safe  -- uses _apm_source marker)
        settings_path = project_root / ".claude" / "settings.json"
        if settings_path.exists():
            try:
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)

                if "hooks" in settings:
                    modified = False
                    for event_name in list(settings["hooks"].keys()):
                        matchers = settings["hooks"][event_name]
                        if isinstance(matchers, list):
                            filtered = [
                                m for m in matchers
                                if not (isinstance(m, dict) and "_apm_source" in m)
                            ]
                            if len(filtered) != len(matchers):
                                modified = True
                            settings["hooks"][event_name] = filtered
                            if not filtered:
                                del settings["hooks"][event_name]

                    if not settings["hooks"]:
                        del settings["hooks"]

                    if modified:
                        with open(settings_path, 'w', encoding='utf-8') as f:
                            json.dump(settings, f, indent=2)
                            f.write('\n')
                        stats['files_removed'] += 1
            except (json.JSONDecodeError, OSError):
                stats['errors'] += 1

        # Clean APM entries from .cursor/hooks.json (safe  -- uses _apm_source marker)
        self._clean_apm_entries_from_json(
            project_root / ".cursor" / "hooks.json", stats,
        )

        return stats

    @staticmethod
    def _clean_apm_entries_from_json(json_path: Path, stats: Dict[str, int]) -> None:
        """Remove APM-tagged entries from a hooks JSON file.

        Filters out entries with ``_apm_source`` markers and cleans up
        empty event arrays and the ``hooks`` key itself.
        """
        if not json_path.exists():
            return
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if "hooks" not in data:
                return

            modified = False
            for event_name in list(data["hooks"].keys()):
                entries = data["hooks"][event_name]
                if isinstance(entries, list):
                    filtered = [
                        e for e in entries
                        if not (isinstance(e, dict) and "_apm_source" in e)
                    ]
                    if len(filtered) != len(entries):
                        modified = True
                    data["hooks"][event_name] = filtered
                    if not filtered:
                        del data["hooks"][event_name]

            if not data["hooks"]:
                del data["hooks"]

            if modified:
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                    f.write('\n')
                stats['files_removed'] += 1
        except (json.JSONDecodeError, OSError):
            stats['errors'] += 1

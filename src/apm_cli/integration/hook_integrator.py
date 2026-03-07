"""Hook integration functionality for APM packages.

Integrates hook JSON files and their referenced scripts during package
installation. Supports both VSCode Copilot (.github/hooks/) and Claude Code
(.claude/settings.json) targets.

Hook JSON format (Claude Code — nested matcher groups):
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

Hook JSON format (GitHub Copilot — flat arrays with bash/powershell keys):
    {
        "version": 1,
        "hooks": {
            "preToolUse": [
                {"type": "command", "bash": "./scripts/validate.sh", "timeoutSec": 10}
            ]
        }
    }

Script path handling:
    - ${CLAUDE_PLUGIN_ROOT}/path → resolved relative to package root, rewritten for target
    - ./path → relative path, resolved from hook file's parent directory, rewritten for target
    - System commands (no path separators) → passed through unchanged
"""

import json
import re
import shutil
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

from apm_cli.integration.base_integrator import BaseIntegrator


@dataclass
class HookIntegrationResult:
    """Result of hook integration operation."""
    hooks_integrated: int
    scripts_copied: int
    target_paths: List[Path] = field(default_factory=list)


class HookIntegrator(BaseIntegrator):
    """Handles integration of APM package hooks into target locations.

    Discovers hook JSON files and their referenced scripts from packages,
    then installs them to the appropriate target location:
    - VSCode: .github/hooks/<pkg>-<name>.json + .github/hooks/scripts/<pkg>/
    - Claude: Merged into .claude/settings.json hooks key + .claude/hooks/<pkg>/
    """

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
                                 managed_files: set = None) -> HookIntegrationResult:
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
            rel_path = str(target_path.relative_to(project_root))

            if self.check_collision(target_path, rel_path, managed_files, force):
                continue

            # Write rewritten JSON
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(rewritten, f, indent=2)
                f.write('\n')

            hooks_integrated += 1
            target_paths.append(target_path)

            # Copy referenced scripts (individual file tracking)
            for source_file, target_rel in scripts:
                target_script = project_root / target_rel
                if self.check_collision(target_script, target_rel, managed_files, force):
                    continue
                target_script.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, target_script)
                scripts_copied += 1
                target_paths.append(target_script)

        return HookIntegrationResult(
            hooks_integrated=hooks_integrated,
            scripts_copied=scripts_copied,
            target_paths=target_paths,
        )

    def integrate_package_hooks_claude(self, package_info, project_root: Path,
                                        force: bool = False,
                                        managed_files: set = None) -> HookIntegrationResult:
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

            # Copy referenced scripts
            for source_file, target_rel in scripts:
                target_script = project_root / target_rel
                if self.check_collision(target_script, target_rel, managed_files, force):
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
        # Don't track settings.json in target_paths — it's a shared file
        # cleaned via _apm_source markers, not file-level deletion

        return HookIntegrationResult(
            hooks_integrated=hooks_integrated,
            scripts_copied=scripts_copied,
            target_paths=target_paths,
        )

    def sync_integration(self, apm_package, project_root: Path,
                          managed_files: set = None) -> Dict:
        """Remove APM-managed hook files.

        Uses *managed_files* (relative paths) to surgically remove only
        APM-tracked files.  Falls back to legacy ``*-apm.json`` glob when
        *managed_files* is ``None``.

        **Never** calls ``shutil.rmtree``.

        Also cleans APM entries from ``.claude/settings.json`` via the
        ``_apm_source`` marker.
        """
        stats: Dict[str, int] = {'files_removed': 0, 'errors': 0}

        if managed_files is not None:
            # Manifest-based removal — only remove tracked files
            deleted: list = []
            for rel_path in managed_files:
                # Only handle hook-related paths
                is_hook = (
                    rel_path.startswith(".github/hooks/")
                    or rel_path.startswith(".claude/hooks/")
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
            # Batch parent cleanup — single bottom-up pass
            self.cleanup_empty_parents(deleted, stop_at=project_root)
        else:
            # Legacy fallback — glob for old -apm suffix files
            hooks_dir = project_root / ".github" / "hooks"
            if hooks_dir.exists():
                for hook_file in hooks_dir.glob("*-apm.json"):
                    try:
                        hook_file.unlink()
                        stats['files_removed'] += 1
                    except Exception:
                        stats['errors'] += 1

        # Clean APM entries from .claude/settings.json (safe — uses _apm_source marker)
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

        return stats


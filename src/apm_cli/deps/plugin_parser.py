"""Parser for Claude plugins (plugin.json format).

Aligns with the Claude Code plugin spec:
  https://docs.anthropic.com/en/docs/claude-code/plugins

Key spec rules:
- The manifest (.claude-plugin/plugin.json) is **optional**.
- When present, only `name` is required; everything else is optional metadata.
- When absent, the plugin name is derived from the directory name.
- Standard component directories: agents/, commands/, skills/, hooks/
- Pass-through files: .mcp.json, .lsp.json, settings.json
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
import yaml


def parse_plugin_manifest(plugin_json_path: Path) -> Dict[str, Any]:
    """Parse a plugin.json manifest file.

    Args:
        plugin_json_path: Path to the plugin.json file

    Returns:
        dict: Parsed plugin manifest

    Raises:
        FileNotFoundError: If plugin.json does not exist
        ValueError: If plugin.json is invalid JSON
    """
    if not plugin_json_path.exists():
        raise FileNotFoundError(f"plugin.json not found: {plugin_json_path}")

    try:
        with open(plugin_json_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in plugin.json: {e}")

    if not manifest.get('name'):
        logging.getLogger("apm").warning(
            "plugin.json at %s is missing 'name' field; falling back to directory name",
            plugin_json_path,
        )

    return manifest


def normalize_plugin_directory(plugin_path: Path, plugin_json_path: Optional[Path] = None) -> Path:
    """Normalize a Claude plugin directory into an APM package.

    Works with or without plugin.json.  When plugin.json is present it is
    treated as optional metadata; when absent the plugin name is derived from
    the directory name.

    Auto-discovers the standard component directories defined by the spec:
    agents/, commands/, skills/, hooks/, and pass-through files
    (.mcp.json, .lsp.json, settings.json).

    Args:
        plugin_path: Root of the plugin directory.
        plugin_json_path: Optional path to plugin.json (may be None).

    Returns:
        Path: Path to the generated apm.yml.
    """
    manifest: Dict[str, Any] = {}

    if plugin_json_path is not None and plugin_json_path.exists():
        try:
            manifest = parse_plugin_manifest(plugin_json_path)
        except (ValueError, FileNotFoundError):
            pass  # Treat as empty manifest; fall back to dir-name defaults

    # Derive name from directory if not in manifest
    if 'name' not in manifest or not manifest['name']:
        manifest['name'] = plugin_path.name

    return synthesize_apm_yml_from_plugin(plugin_path, manifest)


def synthesize_apm_yml_from_plugin(plugin_path: Path, manifest: Dict[str, Any]) -> Path:
    """Synthesize apm.yml from plugin metadata.

    Maps the plugin's agents/, skills/, commands/, hooks/ directories and
    pass-through files (.mcp.json, .lsp.json, settings.json) into .apm/,
    then generates apm.yml.

    Args:
        plugin_path: Path to the plugin directory.
        manifest: Plugin metadata dict (only `name` is required; all other
                  fields are optional and default gracefully).

    Returns:
        Path: Path to the generated apm.yml.
    """
    if not manifest.get('name'):
        manifest['name'] = plugin_path.name

    # Create .apm directory structure
    apm_dir = plugin_path / ".apm"
    apm_dir.mkdir(exist_ok=True)

    # Map plugin structure into .apm/ subdirectories
    _map_plugin_artifacts(plugin_path, apm_dir, manifest)

    # Generate apm.yml from plugin metadata
    apm_yml_content = _generate_apm_yml(manifest)
    apm_yml_path = plugin_path / "apm.yml"

    with open(apm_yml_path, 'w', encoding='utf-8') as f:
        f.write(apm_yml_content)

    return apm_yml_path


def _ignore_symlinks(directory, contents):
    """Ignore function for shutil.copytree that skips symlinks."""
    return [name for name in contents if (Path(directory) / name).is_symlink()]


def _map_plugin_artifacts(plugin_path: Path, apm_dir: Path, manifest: Optional[Dict[str, Any]] = None) -> None:
    """Map plugin artifacts to .apm/ subdirectories and copy pass-through files.

    Copies:
    - agents/     → .apm/agents/
    - skills/     → .apm/skills/
    - commands/   → .apm/prompts/  (*.md normalized to *.prompt.md)
    - hooks/      → .apm/hooks/    (directory, config file, or inline object)
    - .mcp.json   → .apm/.mcp.json  (MCP-based plugins need this to function)
    - .lsp.json   → .apm/.lsp.json
    - settings.json → .apm/settings.json

    When the manifest specifies custom component paths (e.g. ``"agents": ["custom/"]``),
    those paths are used instead of the defaults.

    Symlinks are skipped entirely to prevent content exfiltration attacks.

    Args:
        plugin_path: Root of the plugin directory.
        apm_dir: Path to the .apm/ directory.
        manifest: Optional plugin.json metadata; used for custom component paths.
    """
    if manifest is None:
        manifest = {}

    # Resolve source paths — use manifest arrays if present, else defaults.
    # Custom paths may be directories OR individual files.
    def _resolve_sources(component: str, default_dir: str):
        """Return list of existing source paths (dirs or files) for a component."""
        custom = manifest.get(component)
        if isinstance(custom, list):
            paths = []
            for p in custom:
                src = plugin_path / str(p)
                if src.exists() and not src.is_symlink():
                    paths.append(src)
            return paths
        elif isinstance(custom, str):
            src = plugin_path / custom
            return [src] if src.exists() and not src.is_symlink() else []
        default = plugin_path / default_dir
        return [default] if default.exists() and default.is_dir() else []

    # Map agents/
    agent_sources = _resolve_sources("agents", "agents")
    if agent_sources:
        target_agents = apm_dir / "agents"
        if target_agents.exists():
            shutil.rmtree(target_agents)
        agent_dirs = [s for s in agent_sources if s.is_dir()]
        agent_files = [s for s in agent_sources if s.is_file()]
        # Array of directories → each is a named component; preserve dir name.
        # Single/default directories → copy contents as root.
        is_custom_list = isinstance(manifest.get("agents"), list)
        if is_custom_list and agent_dirs:
            target_agents.mkdir(parents=True, exist_ok=True)
            for d in agent_dirs:
                shutil.copytree(
                    d, target_agents / d.name,
                    ignore=_ignore_symlinks, dirs_exist_ok=True,
                )
        elif agent_dirs:
            shutil.copytree(agent_dirs[0], target_agents, ignore=_ignore_symlinks)
            for extra in agent_dirs[1:]:
                shutil.copytree(extra, target_agents, dirs_exist_ok=True, ignore=_ignore_symlinks)
        if agent_files:
            target_agents.mkdir(parents=True, exist_ok=True)
            for f in agent_files:
                shutil.copy2(f, target_agents / f.name)

    # Map skills/
    skill_sources = _resolve_sources("skills", "skills")
    if skill_sources:
        target_skills = apm_dir / "skills"
        if target_skills.exists():
            shutil.rmtree(target_skills)
        skill_dirs = [s for s in skill_sources if s.is_dir()]
        skill_files = [s for s in skill_sources if s.is_file()]
        is_custom_list = isinstance(manifest.get("skills"), list)
        if is_custom_list and skill_dirs:
            target_skills.mkdir(parents=True, exist_ok=True)
            for d in skill_dirs:
                shutil.copytree(
                    d, target_skills / d.name,
                    ignore=_ignore_symlinks, dirs_exist_ok=True,
                )
        elif skill_dirs:
            shutil.copytree(skill_dirs[0], target_skills, ignore=_ignore_symlinks)
            for extra in skill_dirs[1:]:
                shutil.copytree(extra, target_skills, dirs_exist_ok=True, ignore=_ignore_symlinks)
        if skill_files:
            target_skills.mkdir(parents=True, exist_ok=True)
            for f in skill_files:
                shutil.copy2(f, target_skills / f.name)

    # Map commands/ → .apm/prompts/ (normalize .md → .prompt.md)
    command_sources = _resolve_sources("commands", "commands")
    if command_sources:
        target_prompts = apm_dir / "prompts"
        if target_prompts.exists():
            shutil.rmtree(target_prompts)
        target_prompts.mkdir(parents=True, exist_ok=True)

        def _copy_command_file(source_file: Path, dest_dir: Path, rel_to: Path = None):
            """Copy a command file, normalizing .md → .prompt.md."""
            if rel_to:
                relative_path = source_file.relative_to(rel_to)
                target_path = dest_dir / relative_path
            else:
                target_path = dest_dir / source_file.name
            if not source_file.name.endswith(".prompt.md") and source_file.suffix == ".md":
                target_path = target_path.with_name(f"{source_file.stem}.prompt.md")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target_path)

        for source in command_sources:
            if source.is_file() and not source.is_symlink():
                _copy_command_file(source, target_prompts)
            elif source.is_dir():
                for source_file in source.rglob("*"):
                    if not source_file.is_file() or source_file.is_symlink():
                        continue
                    _copy_command_file(source_file, target_prompts, rel_to=source)

    # Map hooks/ — the spec allows a directory path, a config file path,
    # or an inline object.  Handle all three forms.
    hooks_value = manifest.get("hooks")
    if isinstance(hooks_value, dict):
        # Inline hooks object → write as .apm/hooks/hooks.json
        target_hooks = apm_dir / "hooks"
        target_hooks.mkdir(parents=True, exist_ok=True)
        (target_hooks / "hooks.json").write_text(
            json.dumps(hooks_value, indent=2)
        )
    elif isinstance(hooks_value, str) and (plugin_path / hooks_value).is_file():
        # Config file path (e.g. "hooks": "hooks.json")
        target_hooks = apm_dir / "hooks"
        target_hooks.mkdir(parents=True, exist_ok=True)
        src_file = plugin_path / hooks_value
        if not src_file.is_symlink():
            shutil.copy2(src_file, target_hooks / "hooks.json")
    else:
        # Directory path(s) — standard flow
        hook_sources = _resolve_sources("hooks", "hooks")
        if hook_sources:
            target_hooks = apm_dir / "hooks"
            if target_hooks.exists():
                shutil.rmtree(target_hooks)
            shutil.copytree(hook_sources[0], target_hooks, ignore=_ignore_symlinks)
            for extra in hook_sources[1:]:
                shutil.copytree(extra, target_hooks, dirs_exist_ok=True, ignore=_ignore_symlinks)

    # Pass-through files required for MCP/LSP plugins to function
    for passthrough in (".mcp.json", ".lsp.json", "settings.json"):
        source_file = plugin_path / passthrough
        if source_file.exists() and not source_file.is_symlink():
            shutil.copy2(source_file, apm_dir / passthrough)


def _generate_apm_yml(manifest: Dict[str, Any]) -> str:
    """Generate apm.yml content from plugin metadata.

    Args:
        manifest: Plugin metadata dict.

    Returns:
        str: YAML content for apm.yml.
    """
    apm_package: Dict[str, Any] = {
        'name': manifest.get('name'),
        'version': manifest.get('version', '0.0.0'),
        'description': manifest.get('description', ''),
    }

    # author: spec defines it as {name, email, url} object; accept string too
    if 'author' in manifest:
        author = manifest['author']
        if isinstance(author, dict):
            apm_package['author'] = author.get('name', '')
        else:
            apm_package['author'] = str(author)

    for field in ('license', 'repository', 'homepage', 'tags'):
        if field in manifest:
            apm_package[field] = manifest[field]

    if manifest.get('dependencies'):
        apm_package['dependencies'] = {'apm': manifest['dependencies']}

    # Install behavior is driven by file presence (SKILL.md, etc.), not this
    # field.  Default to hybrid so the standard pipeline handles all components.
    apm_package['type'] = 'hybrid'

    return yaml.dump(apm_package, default_flow_style=False, sort_keys=False)


def validate_plugin_package(plugin_path: Path) -> bool:
    """Check whether a directory looks like a Claude plugin.

    A directory is a valid plugin if it has plugin.json (with at least a name),
    or if it contains at least one standard component directory.

    Args:
        plugin_path: Path to the plugin directory.

    Returns:
        bool: True if the directory appears to be a Claude plugin.
    """
    # Check for plugin.json (optional; only name is required when present)
    from ..utils.helpers import find_plugin_json
    plugin_json = find_plugin_json(plugin_path)
    if plugin_json is not None:
        try:
            with open(plugin_json, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            return bool(manifest.get('name'))
        except (json.JSONDecodeError, IOError):
            pass

    # Fallback: presence of any standard component directory
    for component_dir in ("agents", "commands", "skills", "hooks"):
        if (plugin_path / component_dir).is_dir():
            return True

    return False

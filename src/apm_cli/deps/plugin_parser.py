"""Parser for marketplace plugins (plugin.json format).

This module handles parsing plugin.json files and synthesizing apm.yml
from marketplace plugin metadata.
"""

import json
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
    
    return manifest


def synthesize_apm_yml_from_plugin(plugin_path: Path, manifest: Dict[str, Any]) -> Path:
    """Synthesize apm.yml from plugin.json metadata.
    
    Maps the plugin's agents/, skills/, commands/ directories into .apm/
    structure and generates apm.yml with the plugin metadata.
    
    Args:
        plugin_path: Path to the plugin directory
        manifest: Parsed plugin.json manifest
        
    Returns:
        Path: Path to the generated apm.yml
        
    Raises:
        ValueError: If manifest is missing required fields
    """
    # Validate required fields
    required_fields = ['name', 'version', 'description']
    missing = [f for f in required_fields if f not in manifest]
    if missing:
        raise ValueError(f"plugin.json missing required fields: {', '.join(missing)}")
    
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


def _map_plugin_artifacts(plugin_path: Path, apm_dir: Path, manifest: Dict[str, Any]) -> None:
    """Map plugin artifacts (agents, skills, commands) to .apm/ subdirectories.
    
    Args:
        plugin_path: Path to the plugin directory
        apm_dir: Path to the .apm/ directory
        manifest: Plugin manifest (used to understand plugin structure)
    """
    # Map agents/
    source_agents = plugin_path / "agents"
    if source_agents.exists() and source_agents.is_dir():
        target_agents = apm_dir / "agents"
        if target_agents.exists():
            shutil.rmtree(target_agents)
        shutil.copytree(source_agents, target_agents)
    
    # Map skills/ and convert to .apm/skills/ structure
    # Each skill subdirectory with SKILL.md goes to .apm/skills/skillname/
    source_skills = plugin_path / "skills"
    if source_skills.exists() and source_skills.is_dir():
        target_skills = apm_dir / "skills"
        if target_skills.exists():
            shutil.rmtree(target_skills)
        shutil.copytree(source_skills, target_skills)
    
    # Map commands/ to .apm/prompts/
    # Plugin commands typically become prompts in APM
    source_commands = plugin_path / "commands"
    if source_commands.exists() and source_commands.is_dir():
        target_prompts = apm_dir / "prompts"
        if target_prompts.exists():
            shutil.rmtree(target_prompts)
        shutil.copytree(source_commands, target_prompts)


def _generate_apm_yml(manifest: Dict[str, Any]) -> str:
    """Generate apm.yml content from plugin.json metadata.
    
    Args:
        manifest: Plugin manifest from plugin.json
        
    Returns:
        str: YAML content for apm.yml
    """
    apm_package = {
        'name': manifest.get('name'),
        'version': manifest.get('version'),
        'description': manifest.get('description'),
    }
    
    # Add optional fields if present
    if 'author' in manifest:
        apm_package['author'] = manifest['author']
    
    if 'license' in manifest:
        apm_package['license'] = manifest['license']
    
    if 'repository' in manifest:
        apm_package['repository'] = manifest['repository']
    
    if 'homepage' in manifest:
        apm_package['homepage'] = manifest['homepage']
    
    if 'tags' in manifest:
        apm_package['tags'] = manifest['tags']
    
    # Add dependencies if present
    if 'dependencies' in manifest and manifest['dependencies']:
        apm_package['dependencies'] = {
            'apm': manifest['dependencies']
        }
    
    # Add type as 'hybrid' to indicate it came from a marketplace plugin
    apm_package['type'] = 'hybrid'
    
    # Generate YAML directly (no apm: wrapper needed)
    return yaml.dump(apm_package, default_flow_style=False, sort_keys=False)


def validate_plugin_package(plugin_path: Path) -> bool:
    """Validate that a plugin package has required structure.
    
    Args:
        plugin_path: Path to the plugin directory
        
    Returns:
        bool: True if plugin.json exists and is valid
    """
    plugin_json = plugin_path / "plugin.json"
    if not plugin_json.exists():
        return False
    
    try:
        with open(plugin_json, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        # Check for required fields
        required = ['name', 'version', 'description']
        return all(field in manifest for field in required)
    except (json.JSONDecodeError, IOError):
        return False

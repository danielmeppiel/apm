"""Agent integration functionality for APM packages."""

from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib
import re

from .utils import normalize_repo_url
from .skill_transformer import SkillTransformer, to_hyphen_case
from apm_cli.compilation.link_resolver import UnifiedLinkResolver
from apm_cli.primitives.discovery import discover_primitives
from apm_cli.primitives.parser import parse_skill_file


@dataclass
class IntegrationResult:
    """Result of agent integration operation."""
    files_integrated: int
    files_updated: int  # Updated due to version/commit change
    files_skipped: int  # Unchanged (same version/commit)
    target_paths: List[Path]
    gitignore_updated: bool
    links_resolved: int = 0  # Number of context links resolved
    skills_integrated: int = 0  # Number of skills transformed to agents


class AgentIntegrator:
    """Handles integration of APM package agents into .github/agents/."""
    
    def __init__(self):
        """Initialize the agent integrator."""
        self.link_resolver = None  # Lazy init when needed
    
    def should_integrate(self, project_root: Path) -> bool:
        """Check if agent integration should be performed.
        
        Args:
            project_root: Root directory of the project
            
        Returns:
            bool: Always True - integration happens automatically
        """
        return True
    
    def find_agent_files(self, package_path: Path) -> List[Path]:
        """Find all .agent.md and .chatmode.md files in a package.
        
        Searches in:
        - Package root directory (.agent.md and .chatmode.md)
        - .apm/agents/ subdirectory (new standard)
        - .apm/chatmodes/ subdirectory (legacy)
        
        Args:
            package_path: Path to the package directory
            
        Returns:
            List[Path]: List of absolute paths to agent files
        """
        agent_files = []
        
        # Search in package root
        if package_path.exists():
            agent_files.extend(package_path.glob("*.agent.md"))
            agent_files.extend(package_path.glob("*.chatmode.md"))  # Legacy
        
        # Search in .apm/agents/ (new standard)
        apm_agents = package_path / ".apm" / "agents"
        if apm_agents.exists():
            agent_files.extend(apm_agents.glob("*.agent.md"))
        
        # Search in .apm/chatmodes/ (legacy)
        apm_chatmodes = package_path / ".apm" / "chatmodes"
        if apm_chatmodes.exists():
            agent_files.extend(apm_chatmodes.glob("*.chatmode.md"))
        
        return agent_files
    
    def find_skill_file(self, package_path: Path) -> Optional[Path]:
        """Find SKILL.md file in a package (Claude Skill format).
        
        SKILL.md must be at the package root (Claude convention).
        
        Args:
            package_path: Path to the package directory
            
        Returns:
            Optional[Path]: Path to SKILL.md if found, None otherwise
        """
        skill_file = package_path / "SKILL.md"
        return skill_file if skill_file.exists() else None
    
    def integrate_skill(self, package_info, project_root: Path) -> Tuple[int, List[Path]]:
        """Integrate a SKILL.md from a package into .github/agents/.
        
        Transforms SKILL.md → .github/agents/{name}.agent.md
        
        Args:
            package_info: PackageInfo object with package metadata
            project_root: Root directory of the project
            
        Returns:
            Tuple[int, List[Path]]: (number of skills integrated, list of target paths)
        """
        skill_file = self.find_skill_file(package_info.install_path)
        if not skill_file:
            return (0, [])
        
        # Parse the skill file
        skill = parse_skill_file(skill_file)
        if not skill:
            return (0, [])
        
        # Add source attribution
        skill.source = f"dependency:{package_info.get_canonical_dependency_string()}"
        
        # Determine target path
        agent_name = to_hyphen_case(skill.name)
        agents_dir = project_root / ".github" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        target_path = agents_dir / f"{agent_name}.agent.md"
        
        # Generate content with APM metadata
        agent_content = self._generate_skill_agent_content(skill, package_info)
        
        # Write file
        target_path.write_text(agent_content, encoding='utf-8')
        
        return (1, [target_path])
    
    def _generate_skill_agent_content(self, skill, package_info) -> str:
        """Generate agent.md content from a skill with APM metadata.
        
        Args:
            skill: Skill primitive to convert
            package_info: PackageInfo for source attribution
            
        Returns:
            str: Agent.md file content with frontmatter
        """
        import hashlib
        from datetime import datetime
        
        # Calculate content hash
        content_hash = hashlib.sha256(skill.content.encode()).hexdigest()
        
        lines = [
            "---",
            f"name: {skill.name}",
        ]
        
        if skill.description:
            lines.append(f"description: {skill.description}")
        
        # Add APM metadata
        lines.append("apm:")
        lines.append(f"  source: {package_info.package.name}")
        lines.append(f"  source_repo: {package_info.package.source or 'unknown'}")
        lines.append(f"  source_dependency: {package_info.get_canonical_dependency_string()}")
        lines.append(f"  version: {package_info.package.version}")
        commit = (
            package_info.resolved_reference.resolved_commit
            if package_info.resolved_reference
            else "unknown"
        )
        lines.append(f"  commit: {commit}")
        lines.append(f"  original_path: SKILL.md")
        lines.append(f"  installed_at: {datetime.now().isoformat()}")
        lines.append(f"  content_hash: {content_hash}")
        lines.append(f"  source_type: claude-skill")
        
        lines.append("---")
        lines.append("")
        lines.append(skill.content)
        
        return "\n".join(lines)

    def _parse_header_metadata(self, file_path: Path) -> dict:
        """Parse APM metadata from YAML frontmatter in an integrated agent file.
        
        Args:
            file_path: Path to the integrated agent file
            
        Returns:
            dict: Metadata extracted from frontmatter (version, commit, source, etc.)
                  Empty dict if no valid frontmatter found or parsing fails
        """
        try:
            import frontmatter
            
            post = frontmatter.load(file_path)
            
            # Extract APM metadata from nested 'apm' key (new format)
            apm_data = post.metadata.get('apm', {})
            if apm_data:
                metadata = {
                    'Version': apm_data.get('version', ''),
                    'Commit': apm_data.get('commit', ''),
                    'Source': f"{apm_data.get('source', '')} ({apm_data.get('source_repo', '')})",
                    'SourceDependency': apm_data.get('source_dependency', ''),  # Full dependency string
                    'Original': apm_data.get('original_path', ''),
                    'Installed': apm_data.get('installed_at', ''),
                    'ContentHash': apm_data.get('content_hash', ''),
                    'SourceType': apm_data.get('source_type', '')  # Track if from skill
                }
                return metadata
            
            # Fallback: Check for old flat format (backwards compatibility)
            if 'apm_version' in post.metadata:
                metadata = {
                    'Version': post.metadata.get('apm_version', ''),
                    'Commit': post.metadata.get('apm_commit', ''),
                    'Source': f"{post.metadata.get('apm_source', '')} ({post.metadata.get('apm_source_repo', '')})",
                    'Original': post.metadata.get('apm_original_path', ''),
                    'Installed': post.metadata.get('apm_installed_at', ''),
                    'ContentHash': post.metadata.get('apm_content_hash', '')
                }
                return metadata
            
            return {}  # Not an APM-integrated file
        except Exception:
            # If any error occurs during parsing, return empty dict
            return {}
    
    def _calculate_content_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file content (excluding frontmatter).
        
        Args:
            file_path: Path to the file
            
        Returns:
            str: Hexadecimal hash of the content
        """
        try:
            import frontmatter
            post = frontmatter.load(file_path)
            # Hash only the content, not the frontmatter
            return hashlib.sha256(post.content.encode()).hexdigest()
        except Exception:
            return ""
    
    def _should_update_agent(self, existing_header: dict, package_info, existing_file: Path = None) -> tuple[bool, bool]:
        """Determine if an existing agent file should be updated.
        
        Args:
            existing_header: Metadata from existing file's header
            package_info: PackageInfo object with new package metadata
            existing_file: Path to existing file for content hash verification
            
        Returns:
            tuple[bool, bool]: (should_update, was_modified)
                - should_update: True if file should be updated
                - was_modified: True if content was modified by user
        """
        # If no valid header exists, update the file
        if not existing_header:
            return (True, False)
        
        # Get new version and commit
        new_version = package_info.package.version
        new_commit = (
            package_info.resolved_reference.resolved_commit
            if package_info.resolved_reference
            else "unknown"
        )
        
        # Get existing version and commit from header
        existing_version = existing_header.get('Version', '')
        existing_commit = existing_header.get('Commit', '')
        
        # Check for content modifications if we have the file path
        was_modified = False
        if existing_file and existing_file.exists():
            stored_hash = existing_header.get('ContentHash', '')
            if stored_hash:
                current_hash = self._calculate_content_hash(existing_file)
                was_modified = (current_hash != stored_hash and current_hash != "")
        
        # Update if version or commit has changed
        should_update = (existing_version != new_version or existing_commit != new_commit)
        return (should_update, was_modified)
    

    
    def get_target_filename(self, source_file: Path, package_name: str) -> str:
        """Generate target filename with -apm suffix (intent-first naming).
        
        Args:
            source_file: Source file path
            package_name: Name of the package (not used in simple naming)
            
        Returns:
            str: Target filename with -apm suffix (e.g., security-apm.agent.md or security-apm.chatmode.md)
        """
        # Intent-first naming: insert -apm suffix before extension
        # Preserve original extension (.agent.md or .chatmode.md)
        # Examples:
        #   security.agent.md -> security-apm.agent.md
        #   default.chatmode.md -> default-apm.chatmode.md
        
        # Determine extension
        if source_file.name.endswith('.agent.md'):
            stem = source_file.name[:-9]  # Remove .agent.md
            extension = '.agent.md'
        elif source_file.name.endswith('.chatmode.md'):
            stem = source_file.name[:-12]  # Remove .chatmode.md
            extension = '.chatmode.md'
        else:
            # Fallback for unexpected naming
            stem = source_file.stem
            extension = ''.join(source_file.suffixes)
        
        return f"{stem}-apm{extension}"
    
    def copy_agent_with_metadata(self, source: Path, target: Path, package_info, original_path: Path) -> int:
        """Copy agent file with APM metadata embedded in frontmatter.
        Resolves context links before writing.
        
        Args:
            source: Source file path
            target: Target file path
            package_info: PackageInfo object with package metadata
            original_path: Original path to the agent file
        
        Returns:
            int: Number of links resolved
        """
        import frontmatter
        
        # Read and parse source file with frontmatter
        post = frontmatter.load(source)
        
        # Resolve context links in content
        links_resolved = 0
        if self.link_resolver:
            original_content = post.content
            resolved_content = self.link_resolver.resolve_links_for_installation(
                content=post.content,
                source_file=source,
                target_file=target
            )
            post.content = resolved_content
            # Count how many links changed by comparing actual link content
            if resolved_content != original_content:
                import re
                # Extract all links from both versions
                link_pattern = re.compile(r'\]\(([^)]+)\)')
                original_links = set(link_pattern.findall(original_content))
                resolved_links = set(link_pattern.findall(resolved_content))
                # Count links that were changed
                links_resolved = len(original_links - resolved_links)
        
        # Calculate content hash for modification detection (after link resolution)
        content_hash = hashlib.sha256(post.content.encode()).hexdigest()
        
        # Add APM metadata to frontmatter (nested under 'apm' key for clarity)
        post.metadata['apm'] = {
            'source': package_info.package.name,
            'source_repo': package_info.package.source or "unknown",
            'source_dependency': package_info.get_canonical_dependency_string(),  # Full dependency string for orphan detection
            'version': package_info.package.version,
            'commit': (
                package_info.resolved_reference.resolved_commit
                if package_info.resolved_reference
                else "unknown"
            ),
            'original_path': (
                str(original_path.relative_to(package_info.install_path))
                if original_path.is_relative_to(package_info.install_path)
                else original_path.name
            ),
            'installed_at': package_info.installed_at or datetime.now().isoformat(),
            'content_hash': content_hash
        }
        
        # Write to target with modified frontmatter
        with open(target, 'w', encoding='utf-8') as f:
            f.write(frontmatter.dumps(post))
        
        return links_resolved
    
    def integrate_package_agents(self, package_info, project_root: Path) -> IntegrationResult:
        """Integrate all agents from a package into .github/agents/.
        
        Implements smart update logic:
        - First install: Copy with header and -apm suffix
        - Subsequent installs:
          - Compare version/commit with existing file
          - Update if different (re-copy with new header)
          - Skip if unchanged (preserve file timestamps)
        Resolves context links during integration.
        
        Args:
            package_info: PackageInfo object with package metadata
            project_root: Root directory of the project
            
        Returns:
            IntegrationResult: Results of the integration operation
        """
        # Initialize link resolver and register contexts
        self.link_resolver = UnifiedLinkResolver(project_root)
        try:
            primitives = discover_primitives(package_info.install_path)
            self.link_resolver.register_contexts(primitives)
        except Exception:
            # If context discovery fails, continue without link resolution
            self.link_resolver = None
        
        # Find all agent files in the package
        agent_files = self.find_agent_files(package_info.install_path)
        
        # Also check for SKILL.md (Claude Skill format)
        skill_file = self.find_skill_file(package_info.install_path)
        
        # If no agent files AND no skill file, return empty result
        if not agent_files and not skill_file:
            return IntegrationResult(
                files_integrated=0,
                files_updated=0,
                files_skipped=0,
                target_paths=[],
                gitignore_updated=False
            )
        
        # Create .github/agents/ if it doesn't exist
        agents_dir = project_root / ".github" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        
        # Process each agent file
        files_integrated = 0
        files_updated = 0
        files_skipped = 0
        target_paths = []
        total_links_resolved = 0
        
        for source_file in agent_files:
            # Generate target filename
            target_filename = self.get_target_filename(source_file, package_info.package.name)
            target_path = agents_dir / target_filename
            
            # Check if target already exists
            if target_path.exists():
                # Parse existing file's frontmatter metadata
                existing_header = self._parse_header_metadata(target_path)
                
                # Check if update is needed and if content was modified
                should_update, was_modified = self._should_update_agent(
                    existing_header, package_info, target_path
                )
                
                if should_update:
                    # Warn if user modified the content
                    if was_modified:
                        from apm_cli.cli import _rich_warning
                        _rich_warning(
                            f"⚠ Restoring modified file: {target_path.name} "
                            f"(your changes will be overwritten)"
                        )
                    # Version or commit changed - update the file
                    links_resolved = self.copy_agent_with_metadata(source_file, target_path, package_info, source_file)
                    total_links_resolved += links_resolved
                    files_updated += 1
                    target_paths.append(target_path)
                else:
                    # Unchanged version/commit - skip to preserve file timestamp
                    files_skipped += 1
            else:
                # New file - integrate it
                links_resolved = self.copy_agent_with_metadata(source_file, target_path, package_info, source_file)
                total_links_resolved += links_resolved
                files_integrated += 1
                target_paths.append(target_path)
        
        # Also integrate SKILL.md if present (Claude Skill → VSCode agent)
        skills_integrated, skill_paths = self.integrate_skill(package_info, project_root)
        if skills_integrated > 0:
            files_integrated += skills_integrated
            target_paths.extend(skill_paths)
        
        return IntegrationResult(
            files_integrated=files_integrated,
            files_updated=files_updated,
            files_skipped=files_skipped,
            target_paths=target_paths,
            gitignore_updated=False,
            links_resolved=total_links_resolved,
            skills_integrated=skills_integrated
        )
    
    def sync_integration(self, apm_package, project_root: Path) -> Dict[str, int]:
        """Sync .github/agents/ with currently installed packages.
        
        - Removes agents from uninstalled packages (orphans)
        - Updates agents from updated packages
        - Adds agents from new packages
        
        Idempotent: safe to call anytime. Reuses existing smart update logic.
        
        Args:
            apm_package: APMPackage with current dependencies
            project_root: Root directory of the project
            
        Returns:
            Dict with 'files_removed' and 'errors' counts
        """
        agents_dir = project_root / ".github" / "agents"
        if not agents_dir.exists():
            return {'files_removed': 0, 'errors': 0}
        
        # Build set of canonical dependency strings for comparison
        # For virtual packages: owner/repo/path/to/file or owner/repo/collections/name
        # For regular packages: owner/repo
        installed_deps = set()
        installed_repo_urls = set()  # Fallback for old metadata format
        for dep in apm_package.get_apm_dependencies():
            installed_deps.add(dep.get_canonical_dependency_string())
            installed_repo_urls.add(dep.repo_url)
        
        # Track cleanup statistics
        files_removed = 0
        errors = 0
        
        # Remove orphaned agents (from uninstalled packages)
        for agent_file in agents_dir.glob("*-apm.agent.md"):
            metadata = self._parse_header_metadata(agent_file)
            
            # Skip files without valid metadata - they might be user's custom files
            if not metadata:
                continue
            
            # Try new format first: source_dependency contains full dependency string
            source_dependency = metadata.get('SourceDependency', '')
            
            if source_dependency and source_dependency != 'unknown':
                # New format: compare full dependency strings
                normalized_dep = normalize_repo_url(source_dependency)
                package_match = any(
                    dep == normalized_dep or dep == source_dependency
                    for dep in installed_deps
                )
            else:
                # Fallback: old format using repo URL from Source field
                source = metadata.get('Source', '')
                if not source:
                    continue
                
                # Extract package repo URL from source
                # Format: "package-name (owner/repo)" or "package-name (host.com/owner/repo)"
                package_repo_url = None
                if '(' in source and ')' in source:
                    package_repo_url = source.split('(')[1].split(')')[0].strip()
                
                if not package_repo_url:
                    continue
                
                # Normalize the repo URL for comparison
                normalized_package_url = normalize_repo_url(package_repo_url)
                
                # Check if source package is still installed (using repo_url for backwards compat)
                package_match = any(
                    pkg == normalized_package_url or 
                    (pkg + '.git') == normalized_package_url or
                    pkg == package_repo_url
                    for pkg in installed_repo_urls
                )
            
            if not package_match:
                try:
                    agent_file.unlink()  # Orphaned - remove it
                    files_removed += 1
                except Exception:
                    errors += 1
        
        # Also remove orphaned legacy chatmode files
        for chatmode_file in agents_dir.glob("*-apm.chatmode.md"):
            metadata = self._parse_header_metadata(chatmode_file)
            
            # Skip files without valid metadata
            if not metadata:
                continue
            
            # Try new format first: source_dependency contains full dependency string
            source_dependency = metadata.get('SourceDependency', '')
            
            if source_dependency and source_dependency != 'unknown':
                # New format: compare full dependency strings directly
                # Both source_dependency and installed_deps are in canonical form
                package_match = source_dependency in installed_deps
            else:
                # Fallback: old format using repo URL from Source field
                source = metadata.get('Source', '')
                if not source:
                    continue
                
                # Extract package repo URL from source
                package_repo_url = None
                if '(' in source and ')' in source:
                    package_repo_url = source.split('(')[1].split(')')[0].strip()
                
                if not package_repo_url:
                    continue
                
                # Normalize the repo URL for comparison
                normalized_package_url = normalize_repo_url(package_repo_url)
                
                # Check if source package is still installed
                package_match = any(
                    pkg == normalized_package_url or 
                    (pkg + '.git') == normalized_package_url or
                    pkg == package_repo_url
                    for pkg in installed_repo_urls
                )
            
            if not package_match:
                try:
                    chatmode_file.unlink()  # Orphaned - remove it
                    files_removed += 1
                except Exception:
                    errors += 1
        
        return {'files_removed': files_removed, 'errors': errors}
    
    def update_gitignore_for_integrated_agents(self, project_root: Path) -> bool:
        """Update .gitignore with pattern for integrated agents.
        
        Args:
            project_root: Root directory of the project
            
        Returns:
            bool: True if .gitignore was updated, False if pattern already exists
        """
        gitignore_path = project_root / ".gitignore"
        
        # Define patterns for both new and legacy formats
        patterns = [
            ".github/agents/*-apm.agent.md",
            ".github/agents/*-apm.chatmode.md"
        ]
        
        # Read current content
        current_content = []
        if gitignore_path.exists():
            try:
                with open(gitignore_path, "r", encoding="utf-8") as f:
                    current_content = [line.rstrip("\n\r") for line in f.readlines()]
            except Exception:
                return False
        
        # Check which patterns need to be added
        patterns_to_add = []
        for pattern in patterns:
            if not any(pattern in line for line in current_content):
                patterns_to_add.append(pattern)
        
        if not patterns_to_add:
            return False
        
        # Add patterns to .gitignore
        try:
            with open(gitignore_path, "a", encoding="utf-8") as f:
                # Add a blank line before our entry if file isn't empty
                if current_content and current_content[-1].strip():
                    f.write("\n")
                f.write("\n# APM integrated agents\n")
                for pattern in patterns_to_add:
                    f.write(f"{pattern}\n")
            return True
        except Exception:
            return False

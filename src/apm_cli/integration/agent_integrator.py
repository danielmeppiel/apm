"""Agent integration functionality for APM packages.

Note: SKILL.md files are NOT transformed to .agent.md files. Skills are handled
separately by SkillIntegrator and installed to .github/skills/ as native skills.
See skill-strategy.md for the full architectural rationale (T5).
"""

from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass
import re

from apm_cli.compilation.link_resolver import UnifiedLinkResolver
from apm_cli.primitives.discovery import discover_primitives


@dataclass
class IntegrationResult:
    """Result of agent integration operation.
    
    Note: Skills are NOT transformed to agents. They are handled separately
    by SkillIntegrator and installed to .github/skills/ as native skills.
    See skill-strategy.md for architectural rationale.
    """
    files_integrated: int
    files_updated: int  # Updated due to version/commit change
    files_skipped: int  # Unchanged (same version/commit)
    target_paths: List[Path]
    gitignore_updated: bool
    links_resolved: int = 0  # Number of context links resolved


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
    
    # NOTE: find_skill_file(), integrate_skill(), and _generate_skill_agent_content()
    # have been REMOVED as part of T5 (skill-strategy.md).
    #
    # Skills are NOT transformed to .agent.md files. Instead:
    # - Skills go directly to .github/skills/ via SkillIntegrator
    # - This preserves the native skill format and avoids semantic confusion
    # - See skill-strategy.md for the full architectural rationale

    
    def get_target_filename(self, source_file: Path, package_name: str) -> str:
        """Generate target filename with -apm suffix (intent-first naming).
        
        Args:
            source_file: Source file path
            package_name: Name of the package (not used in simple naming)
            
        Returns:
            str: Target filename with -apm suffix (e.g., security-apm.agent.md)
        """
        # Intent-first naming: insert -apm suffix before extension
        # Always deploy as .agent.md (.chatmode.md is legacy)
        # Examples:
        #   security.agent.md -> security-apm.agent.md
        #   default.chatmode.md -> default-apm.agent.md
        
        # Determine extension — always deploy as .agent.md
        # (.chatmode.md is legacy; VS Code now uses .agent.md)
        if source_file.name.endswith('.agent.md'):
            stem = source_file.name[:-9]  # Remove .agent.md
        elif source_file.name.endswith('.chatmode.md'):
            stem = source_file.name[:-12]  # Remove .chatmode.md
        else:
            # Fallback for unexpected naming
            stem = source_file.stem
        
        return f"{stem}-apm.agent.md"
    
    def copy_agent(self, source: Path, target: Path) -> int:
        """Copy agent file verbatim, resolving context links.
        
        Args:
            source: Source file path
            target: Target file path
        
        Returns:
            int: Number of links resolved
        """
        content = source.read_text(encoding='utf-8')
        
        # Resolve context links in content
        links_resolved = 0
        if self.link_resolver:
            original_content = content
            content = self.link_resolver.resolve_links_for_installation(
                content=content,
                source_file=source,
                target_file=target
            )
            if content != original_content:
                link_pattern = re.compile(r'\]\(([^)]+)\)')
                original_links = set(link_pattern.findall(original_content))
                resolved_links = set(link_pattern.findall(content))
                links_resolved = len(original_links - resolved_links)
        
        target.write_text(content, encoding='utf-8')
        return links_resolved
    
    def integrate_package_agents(self, package_info, project_root: Path) -> IntegrationResult:
        """Integrate all agents from a package into .github/agents/.
        
        Always overwrites existing files (no version comparison).
        Resolves context links during integration.
        
        Note: SKILL.md files are NOT transformed to .agent.md files.
        Skills are handled separately by SkillIntegrator and go to .github/skills/.
        See skill-strategy.md for architectural rationale.
        
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
        
        # Find all agent files in the package (.agent.md and .chatmode.md)
        # NOTE: SKILL.md is NOT included - skills go to .github/skills/ via SkillIntegrator
        agent_files = self.find_agent_files(package_info.install_path)
        
        # If no agent files, return empty result
        if not agent_files:
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
        
        # Also target .claude/agents/ when .claude/ folder exists (dual-target)
        claude_agents_dir = None
        claude_dir = project_root / ".claude"
        if claude_dir.exists() and claude_dir.is_dir():
            claude_agents_dir = claude_dir / "agents"
            claude_agents_dir.mkdir(parents=True, exist_ok=True)
        
        # Process each agent file — always overwrite
        files_integrated = 0
        target_paths = []
        total_links_resolved = 0
        
        for source_file in agent_files:
            target_filename = self.get_target_filename(source_file, package_info.package.name)
            target_path = agents_dir / target_filename
            
            links_resolved = self.copy_agent(source_file, target_path)
            total_links_resolved += links_resolved
            files_integrated += 1
            target_paths.append(target_path)
            
            # Copy to .claude/agents/ as well
            if claude_agents_dir:
                claude_target = claude_agents_dir / target_filename
                self.copy_agent(source_file, claude_target)
        
        return IntegrationResult(
            files_integrated=files_integrated,
            files_updated=0,
            files_skipped=0,
            target_paths=target_paths,
            gitignore_updated=False,
            links_resolved=total_links_resolved
        )
    
    def get_target_filename_claude(self, source_file: Path, package_name: str) -> str:
        """Generate target filename for Claude agents with -apm suffix.
        
        Claude sub-agents use plain .md files in .claude/agents/.
        Both .agent.md and .chatmode.md sources are converted to .md.
        
        Args:
            source_file: Source file path
            package_name: Name of the package (not used in simple naming)
            
        Returns:
            str: Target filename with -apm.md suffix (e.g., security-apm.md)
        """
        if source_file.name.endswith('.agent.md'):
            stem = source_file.name[:-9]  # Remove .agent.md
        elif source_file.name.endswith('.chatmode.md'):
            stem = source_file.name[:-12]  # Remove .chatmode.md
        else:
            stem = source_file.stem
        
        return f"{stem}-apm.md"
    
    def integrate_package_agents_claude(self, package_info, project_root: Path) -> IntegrationResult:
        """Integrate all agents from a package into .claude/agents/.
        
        Deploys agent files to Claude Code's native sub-agent directory.
        Always overwrites existing files. Resolves context links during integration.
        
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
            self.link_resolver = None
        
        # Find all agent files in the package
        agent_files = self.find_agent_files(package_info.install_path)
        
        if not agent_files:
            return IntegrationResult(
                files_integrated=0,
                files_updated=0,
                files_skipped=0,
                target_paths=[],
                gitignore_updated=False
            )
        
        # Create .claude/agents/ if it doesn't exist
        agents_dir = project_root / ".claude" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        
        # Process each agent file — always overwrite
        files_integrated = 0
        target_paths = []
        total_links_resolved = 0
        
        for source_file in agent_files:
            target_filename = self.get_target_filename_claude(source_file, package_info.package.name)
            target_path = agents_dir / target_filename
            
            links_resolved = self.copy_agent(source_file, target_path)
            total_links_resolved += links_resolved
            files_integrated += 1
            target_paths.append(target_path)
        
        return IntegrationResult(
            files_integrated=files_integrated,
            files_updated=0,
            files_skipped=0,
            target_paths=target_paths,
            gitignore_updated=False,
            links_resolved=total_links_resolved
        )
    
    def sync_integration(self, apm_package, project_root: Path) -> Dict[str, int]:
        """Remove all APM-managed agent files for clean regeneration.
        
        Args:
            apm_package: APMPackage with current dependencies (unused, kept for API compat)
            project_root: Root directory of the project
            
        Returns:
            Dict with 'files_removed' and 'errors' counts
        """
        stats = {'files_removed': 0, 'errors': 0}
        
        agents_dir = project_root / ".github" / "agents"
        if not agents_dir.exists():
            return stats
        
        for agent_file in agents_dir.glob("*-apm.agent.md"):
            try:
                agent_file.unlink()
                stats['files_removed'] += 1
            except Exception:
                stats['errors'] += 1
        
        return stats
    
    def sync_integration_claude(self, apm_package, project_root: Path) -> Dict[str, int]:
        """Remove all APM-managed agent files from .claude/agents/ for clean regeneration.
        
        Args:
            apm_package: APMPackage with current dependencies (unused, kept for API compat)
            project_root: Root directory of the project
            
        Returns:
            Dict with 'files_removed' and 'errors' counts
        """
        stats = {'files_removed': 0, 'errors': 0}
        
        agents_dir = project_root / ".claude" / "agents"
        if not agents_dir.exists():
            return stats
        
        for agent_file in agents_dir.glob("*-apm.md"):
            try:
                agent_file.unlink()
                stats['files_removed'] += 1
            except Exception:
                stats['errors'] += 1
        
        return stats
    
    def update_gitignore_for_integrated_agents(self, project_root: Path) -> bool:
        """Update .gitignore with pattern for integrated agents.
        
        Args:
            project_root: Root directory of the project
            
        Returns:
            bool: True if .gitignore was updated, False if pattern already exists
        """
        gitignore_path = project_root / ".gitignore"
        
        # Pattern for integrated agent files (chatmode.md renamed to agent.md on deploy)
        patterns = [
            ".github/agents/*-apm.agent.md"
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
    
    def update_gitignore_for_integrated_agents_claude(self, project_root: Path) -> bool:
        """Update .gitignore with pattern for Claude integrated agents.
        
        Args:
            project_root: Root directory of the project
            
        Returns:
            bool: True if .gitignore was updated, False if pattern already exists
        """
        gitignore_path = project_root / ".gitignore"
        
        patterns = [
            ".claude/agents/*-apm.md"
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
                if current_content and current_content[-1].strip():
                    f.write("\n")
                f.write("\n# APM integrated Claude agents\n")
                for pattern in patterns_to_add:
                    f.write(f"{pattern}\n")
            return True
        except Exception:
            return False

"""Agent integration functionality for APM packages.

Note: SKILL.md files are NOT transformed to .agent.md files. Skills are handled
separately by SkillIntegrator and installed to .github/skills/ as native skills.
See skill-strategy.md for the full architectural rationale (T5).
"""

from pathlib import Path
from typing import List, Dict

from apm_cli.integration.base_integrator import BaseIntegrator, IntegrationResult


class AgentIntegrator(BaseIntegrator):
    """Handles integration of APM package agents into .github/agents/."""
    
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
        # Use rglob so agents in subdirectories (e.g. from plugin mapping) are
        # still discovered.
        apm_agents = package_path / ".apm" / "agents"
        if apm_agents.exists():
            agent_files.extend(apm_agents.rglob("*.agent.md"))
            # Also pick up plain .md files in agents/; plugins may not use
            # the .agent.md convention  -- the directory name already implies type
            for md_file in apm_agents.rglob("*.md"):
                if (
                    not md_file.name.endswith(".agent.md")
                    and md_file not in agent_files
                ):
                    agent_files.append(md_file)
        
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
        """Generate target filename (always .agent.md, no suffix).
        
        Args:
            source_file: Source file path
            package_name: Name of the package (not used in simple naming)
            
        Returns:
            str: Target filename (e.g., security.agent.md)
        """
        if source_file.name.endswith('.agent.md'):
            stem = source_file.name[:-9]  # Remove .agent.md
        elif source_file.name.endswith('.chatmode.md'):
            stem = source_file.name[:-12]  # Remove .chatmode.md
        else:
            stem = source_file.stem
        
        return f"{stem}.agent.md"
    
    def copy_agent(self, source: Path, target: Path) -> int:
        """Copy agent file verbatim, resolving context links.
        
        Args:
            source: Source file path
            target: Target file path
        
        Returns:
            int: Number of links resolved
        """
        content = source.read_text(encoding='utf-8')
        content, links_resolved = self.resolve_links(content, source, target)
        target.write_text(content, encoding='utf-8')
        return links_resolved
    
    def integrate_package_agents(self, package_info, project_root: Path,
                                   force: bool = False,
                                   managed_files: set = None,
                                   diagnostics=None) -> IntegrationResult:
        """Integrate all agents from a package into .github/agents/.
        
        Deploys with clean filenames. Skips user-authored files unless force=True.
        Also copies to .claude/agents/ when .claude/ exists (dual-target).
        
        Args:
            package_info: PackageInfo object with package metadata
            project_root: Root directory of the project
            force: If True, overwrite user-authored files on collision
            managed_files: Set of relative paths known to be APM-managed
            
        Returns:
            IntegrationResult: Results of the integration operation
        """
        self.init_link_resolver(package_info, project_root)
        
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
        
        # Process each agent file
        files_integrated = 0
        files_skipped = 0
        target_paths = []
        total_links_resolved = 0
        
        for source_file in agent_files:
            target_filename = self.get_target_filename(source_file, package_info.package.name)
            target_path = agents_dir / target_filename
            rel_path = str(target_path.relative_to(project_root))
            
            if self.check_collision(target_path, rel_path, managed_files, force, diagnostics=diagnostics):
                files_skipped += 1
                continue
            
            links_resolved = self.copy_agent(source_file, target_path)
            total_links_resolved += links_resolved
            files_integrated += 1
            target_paths.append(target_path)
            
            # Copy to .claude/agents/ as well with same collision check
            if claude_agents_dir:
                claude_filename = self.get_target_filename_claude(source_file, package_info.package.name)
                claude_target = claude_agents_dir / claude_filename
                claude_rel = str(claude_target.relative_to(project_root))
                if not self.check_collision(claude_target, claude_rel, managed_files, force, diagnostics=diagnostics):
                    self.copy_agent(source_file, claude_target)
                    target_paths.append(claude_target)
        
        return IntegrationResult(
            files_integrated=files_integrated,
            files_updated=0,
            files_skipped=files_skipped,
            target_paths=target_paths,
            links_resolved=total_links_resolved
        )
    
    def get_target_filename_claude(self, source_file: Path, package_name: str) -> str:
        """Generate target filename for Claude agents (clean, no suffix).
        
        Claude sub-agents use plain .md files in .claude/agents/.
        Both .agent.md and .chatmode.md sources are converted to .md.
        
        Args:
            source_file: Source file path
            package_name: Name of the package (not used in simple naming)
            
        Returns:
            str: Target filename (e.g., security.md)
        """
        if source_file.name.endswith('.agent.md'):
            stem = source_file.name[:-9]  # Remove .agent.md
        elif source_file.name.endswith('.chatmode.md'):
            stem = source_file.name[:-12]  # Remove .chatmode.md
        else:
            stem = source_file.stem
        
        return f"{stem}.md"
    
    def integrate_package_agents_claude(self, package_info, project_root: Path,
                                          force: bool = False,
                                          managed_files: set = None,
                                          diagnostics=None) -> IntegrationResult:
        """Integrate all agents from a package into .claude/agents/.
        
        Deploys with clean filenames. Skips user-authored files unless force=True.
        
        Args:
            package_info: PackageInfo object with package metadata
            project_root: Root directory of the project
            force: If True, overwrite user-authored files on collision
            managed_files: Set of relative paths known to be APM-managed
            
        Returns:
            IntegrationResult: Results of the integration operation
        """
        self.init_link_resolver(package_info, project_root)
        
        # Find all agent files in the package
        agent_files = self.find_agent_files(package_info.install_path)
        
        if not agent_files:
            return IntegrationResult(
                files_integrated=0,
                files_updated=0,
                files_skipped=0,
                target_paths=[],
            )
        
        # Create .claude/agents/ if it doesn't exist
        agents_dir = project_root / ".claude" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        
        # Process each agent file
        files_integrated = 0
        files_skipped = 0
        target_paths = []
        total_links_resolved = 0
        
        for source_file in agent_files:
            target_filename = self.get_target_filename_claude(source_file, package_info.package.name)
            target_path = agents_dir / target_filename
            rel_path = str(target_path.relative_to(project_root))
            
            if self.check_collision(target_path, rel_path, managed_files, force, diagnostics=diagnostics):
                files_skipped += 1
                continue
            
            links_resolved = self.copy_agent(source_file, target_path)
            total_links_resolved += links_resolved
            files_integrated += 1
            target_paths.append(target_path)
        
        return IntegrationResult(
            files_integrated=files_integrated,
            files_updated=0,
            files_skipped=files_skipped,
            target_paths=target_paths,
            links_resolved=total_links_resolved
        )
    
    def sync_integration(self, apm_package, project_root: Path,
                          managed_files: set = None) -> Dict[str, int]:
        """Remove APM-managed agent files from .github/agents/."""
        agents_dir = project_root / ".github" / "agents"
        return self.sync_remove_files(
            project_root,
            managed_files,
            prefix=".github/agents/",
            legacy_glob_dir=agents_dir,
            legacy_glob_pattern="*-apm.agent.md",
        )
    
    def sync_integration_claude(self, apm_package, project_root: Path,
                                managed_files: set = None) -> Dict[str, int]:
        """Remove APM-managed agent files from .claude/agents/."""
        agents_dir = project_root / ".claude" / "agents"
        return self.sync_remove_files(
            project_root,
            managed_files,
            prefix=".claude/agents/",
            legacy_glob_dir=agents_dir,
            legacy_glob_pattern="*-apm.md",
        )



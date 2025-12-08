"""Skill integration functionality for APM packages (Claude Code support)."""

from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass
from datetime import datetime
import hashlib
import shutil
import re

import frontmatter

from .utils import normalize_repo_url
from apm_cli.compilation.link_resolver import UnifiedLinkResolver
from apm_cli.primitives.discovery import discover_primitives, DEPENDENCY_PRIMITIVE_PATTERNS


@dataclass
class SkillIntegrationResult:
    """Result of skill integration operation."""
    skill_created: bool
    skill_updated: bool
    skill_skipped: bool
    skill_path: Path | None
    references_copied: int
    links_resolved: int = 0


def to_hyphen_case(name: str) -> str:
    """Convert a package name to hyphen-case for Claude Skills spec.
    
    Args:
        name: Package name (e.g., "owner/repo" or "MyPackage")
        
    Returns:
        str: Hyphen-case name, max 64 chars (e.g., "owner-repo" or "my-package")
    """
    # Extract just the repo name if it's owner/repo format
    if "/" in name:
        name = name.split("/")[-1]
    
    # Replace underscores and spaces with hyphens
    result = name.replace("_", "-").replace(" ", "-")
    
    # Insert hyphens before uppercase letters (camelCase to hyphen-case)
    result = re.sub(r'([a-z])([A-Z])', r'\1-\2', result)
    
    # Convert to lowercase and remove any invalid characters
    result = re.sub(r'[^a-z0-9-]', '', result.lower())
    
    # Remove consecutive hyphens
    result = re.sub(r'-+', '-', result)
    
    # Remove leading/trailing hyphens
    result = result.strip('-')
    
    # Truncate to 64 chars (Claude Skills spec limit)
    return result[:64]


class SkillIntegrator:
    """Handles generation of SKILL.md files for Claude Code integration.
    
    Claude Skills Spec:
    - SKILL.md files provide structured context for Claude Code
    - YAML frontmatter with name, description, and metadata
    - Markdown body with instructions and agent definitions
    - references/ subdirectory for prompt files
    """
    
    def __init__(self):
        """Initialize the skill integrator."""
        self.link_resolver = None  # Lazy init when needed
    
    def should_integrate(self, project_root: Path) -> bool:
        """Check if skill integration should be performed.
        
        Args:
            project_root: Root directory of the project
            
        Returns:
            bool: Always True - integration happens automatically
        """
        return True
    
    def find_instruction_files(self, package_path: Path) -> List[Path]:
        """Find all instruction files in a package.
        
        Searches in:
        - .apm/instructions/ subdirectory
        
        Args:
            package_path: Path to the package directory
            
        Returns:
            List[Path]: List of absolute paths to instruction files
        """
        instruction_files = []
        
        # Search in .apm/instructions/
        apm_instructions = package_path / ".apm" / "instructions"
        if apm_instructions.exists():
            instruction_files.extend(apm_instructions.glob("*.instructions.md"))
        
        return instruction_files
    
    def find_agent_files(self, package_path: Path) -> List[Path]:
        """Find all agent files in a package.
        
        Searches in:
        - .apm/agents/ subdirectory
        
        Args:
            package_path: Path to the package directory
            
        Returns:
            List[Path]: List of absolute paths to agent files
        """
        agent_files = []
        
        # Search in .apm/agents/
        apm_agents = package_path / ".apm" / "agents"
        if apm_agents.exists():
            agent_files.extend(apm_agents.glob("*.agent.md"))
        
        return agent_files
    
    def find_prompt_files(self, package_path: Path) -> List[Path]:
        """Find all prompt files in a package.
        
        Searches in:
        - Package root directory
        - .apm/prompts/ subdirectory
        
        Args:
            package_path: Path to the package directory
            
        Returns:
            List[Path]: List of absolute paths to prompt files
        """
        prompt_files = []
        
        # Search in package root
        if package_path.exists():
            prompt_files.extend(package_path.glob("*.prompt.md"))
        
        # Search in .apm/prompts/
        apm_prompts = package_path / ".apm" / "prompts"
        if apm_prompts.exists():
            prompt_files.extend(apm_prompts.glob("*.prompt.md"))
        
        return prompt_files
    
    def find_context_files(self, package_path: Path) -> List[Path]:
        """Find all context/memory files in a package.
        
        Searches in:
        - .apm/context/ subdirectory
        - .apm/memory/ subdirectory
        
        Args:
            package_path: Path to the package directory
            
        Returns:
            List[Path]: List of absolute paths to context files
        """
        context_files = []
        
        # Search in .apm/context/
        apm_context = package_path / ".apm" / "context"
        if apm_context.exists():
            context_files.extend(apm_context.glob("*.context.md"))
        
        # Search in .apm/memory/
        apm_memory = package_path / ".apm" / "memory"
        if apm_memory.exists():
            context_files.extend(apm_memory.glob("*.memory.md"))
        
        return context_files
    
    def _parse_skill_metadata(self, file_path: Path) -> dict:
        """Parse APM metadata from YAML frontmatter in a SKILL.md file.
        
        Args:
            file_path: Path to the SKILL.md file
            
        Returns:
            dict: Metadata extracted from frontmatter
                  Empty dict if no valid metadata found
        """
        try:
            post = frontmatter.load(file_path)
            
            # Extract APM metadata from nested 'metadata.apm_*' keys
            metadata = post.metadata.get('metadata', {})
            if metadata:
                return {
                    'Version': metadata.get('apm_version', ''),
                    'Commit': metadata.get('apm_commit', ''),
                    'Package': metadata.get('apm_package', ''),
                    'ContentHash': metadata.get('apm_content_hash', '')
                }
            
            return {}
        except Exception:
            return {}
    
    def _calculate_source_hash(self, package_path: Path) -> str:
        """Calculate a hash of all source files that go into SKILL.md.
        
        Args:
            package_path: Path to the package directory
            
        Returns:
            str: Hexadecimal hash of combined source content
        """
        hasher = hashlib.sha256()
        
        # Collect all source files
        all_files = []
        all_files.extend(self.find_instruction_files(package_path))
        all_files.extend(self.find_agent_files(package_path))
        all_files.extend(self.find_context_files(package_path))
        
        # Sort for deterministic hashing
        all_files.sort(key=lambda p: str(p))
        
        for file_path in all_files:
            try:
                content = file_path.read_text(encoding='utf-8')
                hasher.update(content.encode())
            except Exception:
                pass
        
        return hasher.hexdigest()
    
    def _should_update_skill(self, existing_metadata: dict, package_info, package_path: Path) -> tuple[bool, bool]:
        """Determine if an existing SKILL.md file should be updated.
        
        Args:
            existing_metadata: Metadata from existing SKILL.md
            package_info: PackageInfo object with new package metadata
            package_path: Path to package for source hash calculation
            
        Returns:
            tuple[bool, bool]: (should_update, was_modified)
        """
        if not existing_metadata:
            return (True, False)
        
        # Get new version and commit
        new_version = package_info.package.version
        new_commit = (
            package_info.resolved_reference.resolved_commit
            if package_info.resolved_reference
            else "unknown"
        )
        
        # Get existing version and commit
        existing_version = existing_metadata.get('Version', '')
        existing_commit = existing_metadata.get('Commit', '')
        
        # Check content hash for modification detection
        was_modified = False
        stored_hash = existing_metadata.get('ContentHash', '')
        if stored_hash:
            current_hash = self._calculate_source_hash(package_path)
            was_modified = (current_hash != stored_hash and current_hash != "")
        
        # Update if version or commit changed
        should_update = (existing_version != new_version or existing_commit != new_commit)
        return (should_update, was_modified)
    
    def _extract_content(self, file_path: Path) -> str:
        """Extract markdown content from a file, stripping frontmatter.
        
        Args:
            file_path: Path to the file
            
        Returns:
            str: Markdown content without frontmatter
        """
        try:
            post = frontmatter.load(file_path)
            return post.content.strip()
        except Exception:
            # Fallback to raw content if frontmatter parsing fails
            return file_path.read_text(encoding='utf-8').strip()
    
    def _generate_skill_content(self, package_info, package_path: Path) -> str:
        """Generate the markdown body content for SKILL.md.
        
        Compiles instructions and agents into a single structured document.
        
        Args:
            package_info: PackageInfo object with package metadata
            package_path: Path to the package directory
            
        Returns:
            str: Generated markdown content
        """
        sections = []
        
        # Add package description header
        package_name = package_info.package.name
        package_desc = package_info.package.description or f"Skills from {package_name}"
        sections.append(f"# {package_name}\n\n{package_desc}")
        
        # Collect and compile instructions
        instruction_files = self.find_instruction_files(package_path)
        if instruction_files:
            sections.append("\n## Instructions\n")
            for instr_file in sorted(instruction_files, key=lambda p: p.name):
                content = self._extract_content(instr_file)
                if content:
                    # Add instruction name as subsection
                    instr_name = instr_file.stem.replace('.instructions', '').replace('-', ' ').title()
                    sections.append(f"### {instr_name}\n\n{content}")
        
        # Collect and compile agents
        agent_files = self.find_agent_files(package_path)
        if agent_files:
            sections.append("\n## Agents\n")
            for agent_file in sorted(agent_files, key=lambda p: p.name):
                content = self._extract_content(agent_file)
                if content:
                    # Add agent name as subsection
                    agent_name = agent_file.stem.replace('.agent', '').replace('-', ' ').title()
                    sections.append(f"### {agent_name}\n\n{content}")
        
        # Collect and compile context files
        context_files = self.find_context_files(package_path)
        if context_files:
            sections.append("\n## Context\n")
            for ctx_file in sorted(context_files, key=lambda p: p.name):
                content = self._extract_content(ctx_file)
                if content:
                    # Add context name as subsection
                    ctx_name = ctx_file.stem.replace('.context', '').replace('.memory', '').replace('-', ' ').title()
                    sections.append(f"### {ctx_name}\n\n{content}")
        
        # Add reference to prompts if they exist
        prompt_files = self.find_prompt_files(package_path)
        if prompt_files:
            sections.append("\n## Available Prompts\n")
            sections.append("The following prompts are available in the `references/` directory:\n")
            for prompt_file in sorted(prompt_files, key=lambda p: p.name):
                prompt_name = prompt_file.stem.replace('.prompt', '')
                sections.append(f"- `{prompt_name}`: See [references/{prompt_file.name}](references/{prompt_file.name})")
        
        return "\n".join(sections)
    
    def _generate_skill_file(self, package_info, package_path: Path, skill_path: Path) -> int:
        """Generate the SKILL.md file with proper frontmatter.
        
        Args:
            package_info: PackageInfo object with package metadata
            package_path: Path to the package directory
            skill_path: Target path for SKILL.md
            
        Returns:
            int: Number of links resolved
        """
        # Generate skill name from package
        repo_url = package_info.package.source or package_info.package.name
        skill_name = to_hyphen_case(repo_url)
        
        # Generate description (max 1024 chars per Claude spec)
        package_desc = package_info.package.description or f"Skills and context from {package_info.package.name}"
        skill_description = package_desc[:1024]
        
        # Calculate content hash
        content_hash = self._calculate_source_hash(package_path)
        
        # Generate the body content
        body_content = self._generate_skill_content(package_info, package_path)
        
        # Resolve links if link resolver is available
        links_resolved = 0
        if self.link_resolver:
            original_content = body_content
            # Create a temporary source path for link resolution
            temp_source = package_path / "SKILL.md"
            body_content = self.link_resolver.resolve_links_for_installation(
                content=body_content,
                source_file=temp_source,
                target_file=skill_path
            )
            if body_content != original_content:
                link_pattern = re.compile(r'\]\(([^)]+)\)')
                original_links = set(link_pattern.findall(original_content))
                resolved_links = set(link_pattern.findall(body_content))
                links_resolved = len(original_links - resolved_links)
        
        # Build frontmatter per Claude Skills Spec
        skill_metadata = {
            'name': skill_name,
            'description': skill_description,
            'metadata': {
                'apm_package': package_info.get_canonical_dependency_string(),
                'apm_version': package_info.package.version,
                'apm_commit': (
                    package_info.resolved_reference.resolved_commit
                    if package_info.resolved_reference
                    else "unknown"
                ),
                'apm_installed_at': package_info.installed_at or datetime.now().isoformat(),
                'apm_content_hash': content_hash
            }
        }
        
        # Create the frontmatter post
        post = frontmatter.Post(body_content, **skill_metadata)
        
        # Write the SKILL.md file
        with open(skill_path, 'w', encoding='utf-8') as f:
            f.write(frontmatter.dumps(post))
        
        return links_resolved
    
    def _copy_prompts_to_references(self, package_path: Path, references_dir: Path) -> int:
        """Copy prompt files to the references/ subdirectory.
        
        Args:
            package_path: Path to the package directory
            references_dir: Target references directory
            
        Returns:
            int: Number of files copied
        """
        prompt_files = self.find_prompt_files(package_path)
        
        if not prompt_files:
            return 0
        
        # Create references directory
        references_dir.mkdir(parents=True, exist_ok=True)
        
        copied = 0
        for prompt_file in prompt_files:
            target_path = references_dir / prompt_file.name
            try:
                shutil.copy2(prompt_file, target_path)
                copied += 1
            except Exception:
                pass
        
        return copied
    
    def integrate_package_skill(self, package_info, project_root: Path) -> SkillIntegrationResult:
        """Generate SKILL.md for a package in its apm_modules directory.
        
        Creates:
        - SKILL.md in the package directory (apm_modules/owner/repo/SKILL.md)
        - references/ subdirectory with prompt files
        
        Args:
            package_info: PackageInfo object with package metadata
            project_root: Root directory of the project
            
        Returns:
            SkillIntegrationResult: Results of the integration operation
        """
        package_path = package_info.install_path
        
        # Initialize link resolver and register contexts
        self.link_resolver = UnifiedLinkResolver(project_root)
        try:
            primitives = discover_primitives(package_path)
            self.link_resolver.register_contexts(primitives)
        except Exception:
            self.link_resolver = None
        
        # Check if there's anything to integrate
        instruction_files = self.find_instruction_files(package_path)
        agent_files = self.find_agent_files(package_path)
        context_files = self.find_context_files(package_path)
        prompt_files = self.find_prompt_files(package_path)
        
        has_content = bool(instruction_files or agent_files or context_files or prompt_files)
        
        if not has_content:
            return SkillIntegrationResult(
                skill_created=False,
                skill_updated=False,
                skill_skipped=True,
                skill_path=None,
                references_copied=0,
                links_resolved=0
            )
        
        # Determine target paths
        skill_path = package_path / "SKILL.md"
        references_dir = package_path / "references"
        
        # Check if SKILL.md already exists
        skill_created = False
        skill_updated = False
        skill_skipped = False
        links_resolved = 0
        
        if skill_path.exists():
            existing_metadata = self._parse_skill_metadata(skill_path)
            should_update, was_modified = self._should_update_skill(
                existing_metadata, package_info, package_path
            )
            
            if should_update:
                if was_modified:
                    from apm_cli.cli import _rich_warning
                    _rich_warning(
                        f"⚠ Regenerating SKILL.md: {skill_path.relative_to(project_root)} "
                        f"(source files have changed)"
                    )
                links_resolved = self._generate_skill_file(package_info, package_path, skill_path)
                skill_updated = True
            else:
                skill_skipped = True
        else:
            links_resolved = self._generate_skill_file(package_info, package_path, skill_path)
            skill_created = True
        
        # Copy prompts to references directory
        references_copied = 0
        if skill_created or skill_updated:
            references_copied = self._copy_prompts_to_references(package_path, references_dir)
        
        return SkillIntegrationResult(
            skill_created=skill_created,
            skill_updated=skill_updated,
            skill_skipped=skill_skipped,
            skill_path=skill_path if (skill_created or skill_updated) else None,
            references_copied=references_copied,
            links_resolved=links_resolved
        )
    
    def sync_integration(self, apm_package, project_root: Path) -> Dict[str, int]:
        """Sync SKILL.md files with currently installed packages.
        
        - Removes SKILL.md from uninstalled packages (handled by package removal)
        - Updates SKILL.md for updated packages
        
        Note: Unlike prompts/agents which are copied to .github/,
        SKILL.md files live in the package directory itself, so orphan
        removal happens automatically when packages are uninstalled.
        
        Args:
            apm_package: APMPackage with current dependencies
            project_root: Root directory of the project
            
        Returns:
            Dict with cleanup statistics
        """
        # SKILL.md files are in package directories, not a central location
        # Orphan removal is handled by package uninstallation
        return {'files_removed': 0, 'errors': 0}
    
    def update_gitignore_for_skills(self, project_root: Path) -> bool:
        """Update .gitignore with pattern for generated SKILL.md files.
        
        Args:
            project_root: Root directory of the project
            
        Returns:
            bool: True if .gitignore was updated, False if pattern already exists
        """
        gitignore_path = project_root / ".gitignore"
        
        patterns = [
            "apm_modules/**/SKILL.md",
            "apm_modules/**/references/"
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
                f.write("\n# APM generated Claude Skills\n")
                for pattern in patterns_to_add:
                    f.write(f"{pattern}\n")
            return True
        except Exception:
            return False

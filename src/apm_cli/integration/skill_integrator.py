"""Skill integration functionality for APM packages (Claude Code support)."""

from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass
from datetime import datetime
import hashlib
import shutil
import re

import frontmatter


@dataclass
class SkillIntegrationResult:
    """Result of skill integration operation."""
    skill_created: bool
    skill_updated: bool
    skill_skipped: bool
    skill_path: Path | None
    references_copied: int  # Now tracks total files copied to subdirectories
    links_resolved: int = 0  # Kept for backwards compatibility


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


def _normalize_name_part(part: str) -> str:
    """Normalize a single name part to hyphen-case."""
    result = part.replace("_", "-").replace(" ", "-")
    result = re.sub(r'([a-z])([A-Z])', r'\1-\2', result)
    result = re.sub(r'[^a-z0-9-]', '', result.lower())
    result = re.sub(r'-+', '-', result)
    return result.strip('-')


def skill_name_from_dependency(canonical: str) -> str:
    """Generate unique skill name from canonical dependency string.
    
    Uses owner-repo for standard packages, owner-repo-skill for subdirectory packages.
    This ensures uniqueness while keeping names readable.
    
    Examples:
        owner/repo           → owner-repo
        owner/repo/skill     → owner-repo-skill
        owner/repo/a/b/skill → owner-repo-skill
    
    Args:
        canonical: Canonical dependency string (e.g., "ComposioHQ/awesome-claude-skills/mcp-builder")
        
    Returns:
        str: Unique skill name, max 64 chars
    """
    parts = canonical.split("/")
    
    if len(parts) < 2:
        # Single name, just normalize it
        return _normalize_name_part(parts[0])[:64]
    elif len(parts) == 2:
        # Standard package: owner/repo → owner-repo
        owner = _normalize_name_part(parts[0])
        repo = _normalize_name_part(parts[1])
        result = f"{owner}-{repo}"
    else:
        # Subdirectory package: owner/repo/.../skill → owner-repo-skill
        owner = _normalize_name_part(parts[0])
        repo = _normalize_name_part(parts[1])
        skill = _normalize_name_part(parts[-1])
        result = f"{owner}-{repo}-{skill}"
    
    # Remove consecutive hyphens that might result from empty parts
    result = re.sub(r'-+', '-', result).strip('-')
    
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
        all_files.sort(key=str)
        
        for file_path in all_files:
            try:
                content = file_path.read_text(encoding='utf-8')
                hasher.update(content.encode())
            except Exception:
                # Skip unreadable files - hash will reflect only readable content
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
    
    def _extract_keywords(self, files: List[Path]) -> set:
        """Extract keywords from file names for discovery hints.
        
        Args:
            files: List of file paths
            
        Returns:
            set: Keywords extracted from file names
        """
        keywords = set()
        for f in files:
            # "design-standards.instructions.md" → ["design", "standards"]
            stem = f.stem.split('.')[0]  # Remove extension parts
            words = stem.replace('-', ' ').replace('_', ' ').split()
            keywords.update(w.lower() for w in words if len(w) > 3)
        return keywords
    
    def _generate_discovery_description(self, package_info, primitives: dict) -> str:
        """Generate description optimized for Claude skill discovery.
        
        Claude uses this to decide WHEN to activate the skill.
        Must be specific about triggers and use cases.
        
        Args:
            package_info: Package metadata
            primitives: Dict of primitive type -> list of files
            
        Returns:
            str: Description (max 1024 chars per Claude spec)
        """
        base = package_info.package.description or f"Expertise from {package_info.package.name}"
        
        # Extract keywords from all files for trigger hints
        all_files = []
        for files in primitives.values():
            all_files.extend(files)
        
        keywords = self._extract_keywords(all_files)
        
        if keywords:
            triggers = ", ".join(sorted(keywords)[:5])
            hint = f" Use when working with {triggers}."
        else:
            hint = ""
        
        return (base + hint)[:1024]
    
    def _generate_skill_content(self, package_info, primitives: dict, skill_dir: Path) -> str:
        """Generate concise SKILL.md body content.
        
        Creates a lightweight manifest that points to subdirectories.
        Claude uses progressive disclosure to read files when needed.
        
        Args:
            package_info: Package metadata
            primitives: Dict of primitive type -> list of files
            skill_dir: Target skill directory (for relative paths)
            
        Returns:
            str: Concise markdown content (~100-150 words)
        """
        pkg = package_info.package
        sections = []
        
        # Header
        sections.append(f"# {pkg.name}")
        sections.append("")
        sections.append(pkg.description or f"Expertise from {pkg.source or pkg.name}.")
        sections.append("")
        
        # Resources table
        sections.append("## What's Included")
        sections.append("")
        sections.append("| Directory | Contents |")
        sections.append("|-----------|----------|")
        
        type_labels = {
            'instructions': 'Guidelines & standards',
            'agents': 'Specialist personas',
            'prompts': 'Executable workflows',
            'context': 'Reference documents'
        }
        
        for ptype, label in type_labels.items():
            files = primitives.get(ptype, [])
            if files:
                count = len(files)
                sections.append(f"| [{ptype}/]({ptype}/) | {count} {label.lower()} |")
        
        sections.append("")
        sections.append("Read files in each directory for detailed guidance.")
        
        return "\n".join(sections)
    
    def _copy_primitives_to_skill(self, primitives: dict, skill_dir: Path) -> int:
        """Copy all primitives to typed subdirectories in skill directory.
        
        Args:
            primitives: Dict of primitive type -> list of files
            skill_dir: Target skill directory
            
        Returns:
            int: Total number of files copied
        """
        total_copied = 0
        
        for ptype, files in primitives.items():
            if not files:
                continue
            
            subdir = skill_dir / ptype
            subdir.mkdir(parents=True, exist_ok=True)
            
            for src_file in files:
                target_path = subdir / src_file.name
                try:
                    shutil.copy2(src_file, target_path)
                    total_copied += 1
                except Exception:
                    # Skip files that can't be copied - continue with remaining files
                    pass
        
        return total_copied
    
    def _generate_skill_file(self, package_info, primitives: dict, skill_dir: Path) -> int:
        """Generate the SKILL.md file with proper frontmatter.
        
        Args:
            package_info: PackageInfo object with package metadata
            primitives: Dict of primitive type -> list of files
            skill_dir: Target skill directory
            
        Returns:
            int: Number of files copied to subdirectories
        """
        skill_path = skill_dir / "SKILL.md"
        package_path = package_info.install_path
        
        # Generate skill name from package
        repo_url = package_info.package.source or package_info.package.name
        skill_name = to_hyphen_case(repo_url)
        
        # Generate discovery description
        skill_description = self._generate_discovery_description(package_info, primitives)
        
        # Calculate content hash
        content_hash = self._calculate_source_hash(package_path)
        
        # Copy primitives to typed subdirectories
        files_copied = self._copy_primitives_to_skill(primitives, skill_dir)
        
        # Generate the concise body content
        body_content = self._generate_skill_content(package_info, primitives, skill_dir)
        
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
        
        return files_copied
    
    def _integrate_native_claude_skill(
        self, package_info, project_root: Path, source_skill_md: Path
    ) -> SkillIntegrationResult:
        """Copy a native Claude Skill (with existing SKILL.md) to .claude/skills/.
        
        For packages that already have a SKILL.md at their root (like those from
        awesome-claude-skills), we copy the entire skill folder rather than 
        regenerating from .apm/ primitives.
        
        The skill folder name is the source folder name (e.g., `mcp-builder`).
        
        We add APM tracking metadata to the copied SKILL.md so sync_integration
        can properly identify and clean up orphaned skills.
        
        Args:
            package_info: PackageInfo object with package metadata
            project_root: Root directory of the project
            source_skill_md: Path to the source SKILL.md file
            
        Returns:
            SkillIntegrationResult: Results of the integration operation
        """
        package_path = package_info.install_path
        
        # Use the source folder name as the skill name
        # e.g., apm_modules/ComposioHQ/awesome-claude-skills/mcp-builder → mcp-builder
        skill_name = package_path.name
        
        skill_dir = project_root / ".claude" / "skills" / skill_name
        target_skill_md = skill_dir / "SKILL.md"
        
        # Check if we need to update
        skill_created = False
        skill_updated = False
        skill_skipped = False
        
        if target_skill_md.exists():
            # Check existing metadata for version/commit changes
            existing_metadata = self._parse_skill_metadata(target_skill_md)
            current_version = package_info.package.version
            current_commit = (
                package_info.resolved_reference.resolved_commit
                if package_info.resolved_reference
                else "unknown"
            )
            
            if (existing_metadata.get('Version') == current_version and
                existing_metadata.get('Commit') == current_commit):
                skill_skipped = True
            else:
                skill_updated = True
        else:
            skill_created = True
        
        files_copied = 0
        
        if skill_created or skill_updated:
            # Remove existing skill directory if updating
            if skill_dir.exists():
                shutil.rmtree(skill_dir)
            
            # Copy the entire package directory to the skill location
            shutil.copytree(package_path, skill_dir)
            
            # Add APM tracking metadata to the SKILL.md for orphan detection
            self._add_apm_metadata_to_skill(target_skill_md, package_info)
            
            # Count files copied
            files_copied = sum(1 for _ in skill_dir.rglob('*') if _.is_file())
        
        return SkillIntegrationResult(
            skill_created=skill_created,
            skill_updated=skill_updated,
            skill_skipped=skill_skipped,
            skill_path=target_skill_md if (skill_created or skill_updated) else None,
            references_copied=files_copied,
            links_resolved=0
        )
    
    def _add_apm_metadata_to_skill(self, skill_path: Path, package_info) -> None:
        """Add APM tracking metadata to a SKILL.md file.
        
        This ensures sync_integration can identify APM-managed skills for cleanup.
        """
        post = frontmatter.load(skill_path)
        
        # Add nested metadata for APM tracking
        if 'metadata' not in post.metadata:
            post.metadata['metadata'] = {}
        
        post.metadata['metadata']['apm_package'] = package_info.get_canonical_dependency_string()
        post.metadata['metadata']['apm_version'] = package_info.package.version
        post.metadata['metadata']['apm_commit'] = (
            package_info.resolved_reference.resolved_commit
            if package_info.resolved_reference
            else "unknown"
        )
        post.metadata['metadata']['apm_installed_at'] = (
            package_info.installed_at or datetime.now().isoformat()
        )
        
        with open(skill_path, 'w', encoding='utf-8') as f:
            f.write(frontmatter.dumps(post))

    def integrate_package_skill(self, package_info, project_root: Path) -> SkillIntegrationResult:
        """Generate SKILL.md for a package in .claude/skills/ directory.
        
        Creates:
        - .claude/skills/{skill-name}/SKILL.md 
        - .claude/skills/{skill-name}/references/ with prompt files
        
        This follows Claude Code's skill discovery path (.claude/skills/).
        
        Note: Virtual FILE packages (individual files like owner/repo/path/to/file.agent.md) 
        and COLLECTION packages do NOT generate Skills. Only full APM packages and 
        subdirectory packages (like Claude Skills) generate Skills.
        
        Subdirectory packages (e.g., ComposioHQ/awesome-claude-skills/mcp-builder) ARE 
        processed because they represent complete skill packages with their own SKILL.md.
        
        Args:
            package_info: PackageInfo object with package metadata
            project_root: Root directory of the project
            
        Returns:
            SkillIntegrationResult: Results of the integration operation
        """
        # Skip virtual FILE and COLLECTION packages - they're individual files, not full packages
        # Multiple virtual files from the same repo would collide on skill name
        # BUT: subdirectory packages (like Claude Skills) SHOULD generate skills
        if package_info.dependency_ref and package_info.dependency_ref.is_virtual:
            # Allow subdirectory packages through - they are complete skill packages
            if not package_info.dependency_ref.is_virtual_subdirectory():
                return SkillIntegrationResult(
                    skill_created=False,
                    skill_updated=False,
                    skill_skipped=True,
                    skill_path=None,
                    references_copied=0,
                    links_resolved=0
                )
        
        package_path = package_info.install_path
        
        # Check if this is a native Claude Skill (already has SKILL.md at root)
        source_skill_md = package_path / "SKILL.md"
        if source_skill_md.exists():
            return self._integrate_native_claude_skill(package_info, project_root, source_skill_md)
        
        # Discover all primitives for APM packages without SKILL.md
        instruction_files = self.find_instruction_files(package_path)
        agent_files = self.find_agent_files(package_path)
        context_files = self.find_context_files(package_path)
        prompt_files = self.find_prompt_files(package_path)
        
        # Build primitives dict for new methods
        primitives = {
            'instructions': instruction_files,
            'agents': agent_files,
            'prompts': prompt_files,
            'context': context_files
        }
        
        # Filter out empty lists
        primitives = {k: v for k, v in primitives.items() if v}
        
        if not primitives:
            return SkillIntegrationResult(
                skill_created=False,
                skill_updated=False,
                skill_skipped=True,
                skill_path=None,
                references_copied=0,
                links_resolved=0
            )
        
        # Determine target paths - write to .claude/skills/{skill-name}/
        # Use the install folder name for simplicity and consistency
        # e.g., apm_modules/danielmeppiel/design-guidelines → design-guidelines
        skill_name = package_path.name
        skill_dir = project_root / ".claude" / "skills" / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        
        skill_path = skill_dir / "SKILL.md"
        
        # Check if SKILL.md already exists
        skill_created = False
        skill_updated = False
        skill_skipped = False
        files_copied = 0
        
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
                files_copied = self._generate_skill_file(package_info, primitives, skill_dir)
                skill_updated = True
            else:
                skill_skipped = True
        else:
            files_copied = self._generate_skill_file(package_info, primitives, skill_dir)
            skill_created = True
        
        return SkillIntegrationResult(
            skill_created=skill_created,
            skill_updated=skill_updated,
            skill_skipped=skill_skipped,
            skill_path=skill_path if (skill_created or skill_updated) else None,
            references_copied=files_copied,
            links_resolved=0  # No longer tracking link resolution
        )
    
    def sync_integration(self, apm_package, project_root: Path) -> Dict[str, int]:
        """Sync .claude/skills/ with currently installed packages.
        
        Removes skill directories for packages that are no longer installed.
        Uses apm_package metadata in SKILL.md to identify APM-managed skills.
        
        Args:
            apm_package: APMPackage with current dependencies
            project_root: Root directory of the project
            
        Returns:
            Dict with cleanup statistics
        """
        skills_dir = project_root / ".claude" / "skills"
        if not skills_dir.exists():
            return {'files_removed': 0, 'errors': 0}
        
        # Get canonical dependency strings for all installed packages
        installed_packages = set()
        for dep in apm_package.get_apm_dependencies():
            installed_packages.add(dep.get_canonical_dependency_string())
        
        # Find orphaned skill directories by checking apm_package metadata
        files_removed = 0
        errors = 0
        
        for skill_subdir in skills_dir.iterdir():
            if skill_subdir.is_dir():
                skill_md = skill_subdir / "SKILL.md"
                if skill_md.exists():
                    try:
                        metadata = self._parse_skill_metadata(skill_md)
                        apm_package_ref = metadata.get('Package')
                        if apm_package_ref:  # This is an APM-managed skill
                            if apm_package_ref not in installed_packages:
                                # Remove orphaned skill directory
                                shutil.rmtree(skill_subdir)
                                files_removed += 1
                    except Exception:
                        errors += 1
        
        return {'files_removed': files_removed, 'errors': errors}
    
    def update_gitignore_for_skills(self, project_root: Path) -> bool:
        """Update .gitignore with pattern for generated Claude skills.
        
        Args:
            project_root: Root directory of the project
            
        Returns:
            bool: True if .gitignore was updated, False if pattern already exists
        """
        gitignore_path = project_root / ".gitignore"
        
        patterns = [
            ".claude/skills/*-apm/",  # APM-generated skills use -apm suffix
            "# APM-generated Claude skills"
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

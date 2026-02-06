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


def validate_skill_name(name: str) -> tuple[bool, str]:
    """Validate skill name per agentskills.io spec.
    
    Skill names must:
    - Be 1-64 characters long
    - Contain only lowercase alphanumeric characters and hyphens (a-z, 0-9, -)
    - Not contain consecutive hyphens (--)
    - Not start or end with a hyphen
    
    Args:
        name: Skill name to validate
        
    Returns:
        tuple[bool, str]: (is_valid, error_message)
            - is_valid: True if name is valid, False otherwise
            - error_message: Empty string if valid, descriptive error otherwise
    """
    # Check length
    if len(name) < 1:
        return (False, "Skill name cannot be empty")
    
    if len(name) > 64:
        return (False, f"Skill name must be 1-64 characters (got {len(name)})")
    
    # Check for consecutive hyphens
    if '--' in name:
        return (False, "Skill name cannot contain consecutive hyphens (--)")
    
    # Check for leading/trailing hyphens
    if name.startswith('-'):
        return (False, "Skill name cannot start with a hyphen")
    
    if name.endswith('-'):
        return (False, "Skill name cannot end with a hyphen")
    
    # Check for valid characters (lowercase alphanumeric + hyphens only)
    # Pattern: must start and end with alphanumeric, with alphanumeric or hyphens in between
    pattern = r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$'
    if not re.match(pattern, name):
        # Determine specific error
        if any(c.isupper() for c in name):
            return (False, "Skill name must be lowercase (no uppercase letters)")
        
        if '_' in name:
            return (False, "Skill name cannot contain underscores (use hyphens instead)")
        
        if ' ' in name:
            return (False, "Skill name cannot contain spaces (use hyphens instead)")
        
        # Check for other invalid characters
        invalid_chars = set(re.findall(r'[^a-z0-9-]', name))
        if invalid_chars:
            return (False, f"Skill name contains invalid characters: {', '.join(sorted(invalid_chars))}")
        
        return (False, "Skill name must be lowercase alphanumeric with hyphens only")
    
    return (True, "")


def normalize_skill_name(name: str) -> str:
    """Convert any package name to a valid skill name per agentskills.io spec.
    
    Normalization steps:
    1. Extract repo name if owner/repo format
    2. Convert to lowercase
    3. Replace underscores and spaces with hyphens
    4. Convert camelCase to hyphen-case
    5. Remove invalid characters
    6. Remove consecutive hyphens
    7. Strip leading/trailing hyphens
    8. Truncate to 64 characters
    
    Args:
        name: Package name to normalize (e.g., "owner/MyRepo_Name")
        
    Returns:
        str: Valid skill name (e.g., "my-repo-name")
    """
    # Use to_hyphen_case which already handles most normalization
    return to_hyphen_case(name)


# =============================================================================
# Package Type Routing Functions (T4)
# =============================================================================
# These functions determine behavior based on:
# 1. Explicit `type` field in apm.yml (highest priority)
# 2. Presence of SKILL.md at package root (makes it a skill)
# 3. Default to INSTRUCTIONS for instruction-only packages
#
# Per skill-strategy.md Decision 2: "Skills are explicit, not implicit"
# - Packages with SKILL.md OR explicit type: skill/hybrid → become skills
# - Packages with only instructions → compile to AGENTS.md, NOT skills

def get_effective_type(package_info) -> "PackageContentType":
    """Get effective package content type based on explicit type or package structure.
    
    Priority order:
    1. Explicit `type` field in apm.yml → use it directly
    2. Package has SKILL.md (PackageType.CLAUDE_SKILL or HYBRID) → treat as SKILL
    3. Otherwise → INSTRUCTIONS (compile to AGENTS.md only)
    
    Args:
        package_info: PackageInfo object containing package metadata
        
    Returns:
        PackageContentType: The effective type
    """
    from apm_cli.models.apm_package import PackageContentType, PackageType
    
    # Priority 1: Explicit type field in apm.yml
    pkg_type = package_info.package.type if package_info.package else None
    if pkg_type is not None:
        return pkg_type
    
    # Priority 2: Check if package has SKILL.md (via package_type field)
    # PackageType.CLAUDE_SKILL = has SKILL.md only
    # PackageType.HYBRID = has both apm.yml AND SKILL.md
    if package_info.package_type in (PackageType.CLAUDE_SKILL, PackageType.HYBRID):
        return PackageContentType.SKILL
    
    # Priority 3: Default to INSTRUCTIONS for packages without SKILL.md
    # Per skill-strategy.md: "Only .instructions.md files → NO skill, compile to AGENTS.md"
    return PackageContentType.INSTRUCTIONS


def should_install_skill(package_info) -> bool:
    """Determine if package should be installed as a native skill.
    
    This controls whether a package gets installed to .github/skills/ (or .claude/skills/).
    
    Per skill-strategy.md Decision 2 - "Skills are explicit, not implicit":
    
    Returns True for:
        - SKILL: Package has SKILL.md or declares type: skill
        - HYBRID: Package declares type: hybrid in apm.yml
        
    Returns False for:
        - INSTRUCTIONS: Compile to AGENTS.md only, no skill created
        - PROMPTS: Commands/prompts only, no skill created
        - Packages without SKILL.md and no explicit type field
    
    Args:
        package_info: PackageInfo object containing package metadata
        
    Returns:
        bool: True if package should be installed as a native skill
    """
    from apm_cli.models.apm_package import PackageContentType
    
    effective_type = get_effective_type(package_info)
    
    # SKILL and HYBRID should install as skills
    # INSTRUCTIONS and PROMPTS should NOT install as skills
    return effective_type in (PackageContentType.SKILL, PackageContentType.HYBRID)


def should_compile_instructions(package_info) -> bool:
    """Determine if package should compile to AGENTS.md/CLAUDE.md.
    
    This controls whether a package's instructions are included in compiled output.
    
    Per skill-strategy.md Decision 2:
    
    Returns True for:
        - INSTRUCTIONS: Compile to AGENTS.md only (default for packages without SKILL.md)
        - HYBRID: Package declares type: hybrid in apm.yml
        
    Returns False for:
        - SKILL: Install as native skill only, no AGENTS.md compilation
        - PROMPTS: Commands/prompts only, no instructions compiled
    
    Args:
        package_info: PackageInfo object containing package metadata
        
    Returns:
        bool: True if package's instructions should be compiled to AGENTS.md/CLAUDE.md
    """
    from apm_cli.models.apm_package import PackageContentType
    
    effective_type = get_effective_type(package_info)
    
    # INSTRUCTIONS and HYBRID should compile to AGENTS.md
    # SKILL and PROMPTS should NOT compile to AGENTS.md
    return effective_type in (PackageContentType.INSTRUCTIONS, PackageContentType.HYBRID)


def copy_skill_to_target(
    package_info,
    source_path: Path,
    target_base: Path,
) -> tuple[Path | None, Path | None]:
    """Copy skill directory to .github/skills/ and optionally .claude/skills/.
    
    This is a standalone function for direct skill copy operations.
    It handles:
    - Package type routing via should_install_skill()
    - Skill name validation/normalization
    - Directory structure preservation
    - Compatibility copy to .claude/skills/ when .claude/ exists (T7)
    
    Source SKILL.md is copied verbatim — no metadata injection.
    
    Copies:
    - SKILL.md (required)
    - scripts/ (optional)
    - references/ (optional)
    - assets/ (optional)
    - Any other subdirectories the package contains
    
    Args:
        package_info: PackageInfo object with package metadata
        source_path: Path to skill in apm_modules/
        target_base: Usually project root
        
    Returns:
        Tuple of (github_path, claude_path):
        - github_path: Path to .github/skills/{name}/ or None if skipped
        - claude_path: Path to .claude/skills/{name}/ or None if .claude/ doesn't exist
    """
    # Check if package type allows skill installation (T4 routing)
    if not should_install_skill(package_info):
        return (None, None)
    
    # Check for SKILL.md existence
    source_skill_md = source_path / "SKILL.md"
    if not source_skill_md.exists():
        # No SKILL.md means this package is handled by compilation, not skill copy
        return (None, None)
    
    # Get and validate skill name from folder
    raw_skill_name = source_path.name
    
    is_valid, error_msg = validate_skill_name(raw_skill_name)
    if is_valid:
        skill_name = raw_skill_name
    else:
        skill_name = normalize_skill_name(raw_skill_name)
    
    # === Primary target: .github/skills/ ===
    github_skill_dir = target_base / ".github" / "skills" / skill_name
    
    # Create .github/skills/ if it doesn't exist
    github_skill_dir.parent.mkdir(parents=True, exist_ok=True)
    
    # If skill already exists, remove it for update
    if github_skill_dir.exists():
        shutil.rmtree(github_skill_dir)
    
    # Copy the entire skill folder preserving structure
    # This copies SKILL.md, scripts/, references/, assets/, etc.
    shutil.copytree(source_path, github_skill_dir)
    
    # === Secondary target: .claude/skills/ (T7 - compatibility copy) ===
    claude_skill_dir: Path | None = None
    claude_dir = target_base / ".claude"
    
    # Only copy to .claude/skills/ if .claude/ directory already exists
    # Do NOT create .claude/ folder if it doesn't exist
    if claude_dir.exists() and claude_dir.is_dir():
        claude_skill_dir = claude_dir / "skills" / skill_name
        
        # Create .claude/skills/ if needed (but .claude/ must already exist)
        claude_skill_dir.parent.mkdir(parents=True, exist_ok=True)
        
        # If skill already exists, remove it for update
        if claude_skill_dir.exists():
            shutil.rmtree(claude_skill_dir)
        
        # Copy the entire skill folder (identical to github copy)
        shutil.copytree(source_path, claude_skill_dir)
    
    return (github_skill_dir, claude_skill_dir)


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
    
    def _integrate_native_skill(
        self, package_info, project_root: Path, source_skill_md: Path
    ) -> SkillIntegrationResult:
        """Copy a native Skill (with existing SKILL.md) to .github/skills/ and optionally .claude/skills/.
        
        For packages that already have a SKILL.md at their root (like those from
        awesome-claude-skills), we copy the entire skill folder rather than 
        regenerating from .apm/ primitives.
        
        The skill folder name is the source folder name (e.g., `mcp-builder`),
        validated and normalized per the agentskills.io spec.
        
        Source SKILL.md is copied verbatim — no metadata injection. Orphan
        detection uses apm.lock via directory name matching instead.
        
        T7 Enhancement: Also copies to .claude/skills/ when .claude/ folder exists.
        This ensures Claude Code users get skills while not polluting projects
        that don't use Claude.
        
        Copies:
        - SKILL.md (required)
        - scripts/ (optional)
        - references/ (optional)
        - assets/ (optional)
        - Any other subdirectories the package contains
        
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
        raw_skill_name = package_path.name
        
        # Validate skill name per agentskills.io spec
        is_valid, error_msg = validate_skill_name(raw_skill_name)
        if is_valid:
            skill_name = raw_skill_name
        else:
            # Normalize the name if validation fails
            skill_name = normalize_skill_name(raw_skill_name)
            # Log warning about name normalization (import here to avoid circular import)
            try:
                from apm_cli.cli import _rich_warning
                _rich_warning(
                    f"Skill name '{raw_skill_name}' normalized to '{skill_name}' ({error_msg})"
                )
            except ImportError:
                pass  # CLI not available in tests
        
        # Primary target: .github/skills/
        github_skill_dir = project_root / ".github" / "skills" / skill_name
        github_skill_md = github_skill_dir / "SKILL.md"
        
        # Always copy — source integrity is preserved, orphan detection uses apm.lock
        skill_created = not github_skill_dir.exists()
        skill_updated = not skill_created
        
        files_copied = 0
        claude_skill_dir: Path | None = None
        
        # === Copy to .github/skills/ (primary) ===
        if github_skill_dir.exists():
            shutil.rmtree(github_skill_dir)
        
        github_skill_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(package_path, github_skill_dir)
        
        files_copied = sum(1 for _ in github_skill_dir.rglob('*') if _.is_file())
        
        # === T7: Copy to .claude/skills/ (secondary - compatibility) ===
        claude_dir = project_root / ".claude"
        if claude_dir.exists() and claude_dir.is_dir():
            claude_skill_dir = claude_dir / "skills" / skill_name
            
            if claude_skill_dir.exists():
                shutil.rmtree(claude_skill_dir)
            
            claude_skill_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(package_path, claude_skill_dir)
        
        return SkillIntegrationResult(
            skill_created=skill_created,
            skill_updated=skill_updated,
            skill_skipped=False,
            skill_path=github_skill_md,
            references_copied=files_copied,
            links_resolved=0
        )

    def integrate_package_skill(self, package_info, project_root: Path) -> SkillIntegrationResult:
        """Generate SKILL.md for a package in .github/skills/ directory.
        
        Creates:
        - .github/skills/{skill-name}/SKILL.md 
        - .github/skills/{skill-name}/references/ with prompt files
        
        This follows the Agent Skills standard (.github/skills/).
        
        Routing based on package type (from apm.yml):
        - SKILL/HYBRID: Install as native skill
        - INSTRUCTIONS/PROMPTS: Skip skill installation
        
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
        # Check if package type allows skill installation (T4 routing)
        # SKILL and HYBRID → install as skill
        # INSTRUCTIONS and PROMPTS → skip skill installation
        if not should_install_skill(package_info):
            return SkillIntegrationResult(
                skill_created=False,
                skill_updated=False,
                skill_skipped=True,
                skill_path=None,
                references_copied=0,
                links_resolved=0
            )
        
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
        
        # Check if this is a native Skill (already has SKILL.md at root)
        source_skill_md = package_path / "SKILL.md"
        if source_skill_md.exists():
            return self._integrate_native_skill(package_info, project_root, source_skill_md)
        
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
        
        # Determine target paths - write to .github/skills/{skill-name}/
        # Use the install folder name for simplicity and consistency
        # e.g., apm_modules/danielmeppiel/design-guidelines → design-guidelines
        skill_name = package_path.name
        skill_dir = project_root / ".github" / "skills" / skill_name
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
                # T7: Also update .claude/skills/ if .claude/ exists
                self._sync_to_claude_skills(package_info, primitives, skill_name, project_root)
            else:
                skill_skipped = True
        else:
            files_copied = self._generate_skill_file(package_info, primitives, skill_dir)
            skill_created = True
            # T7: Also copy to .claude/skills/ if .claude/ exists
            self._sync_to_claude_skills(package_info, primitives, skill_name, project_root)
        
        return SkillIntegrationResult(
            skill_created=skill_created,
            skill_updated=skill_updated,
            skill_skipped=skill_skipped,
            skill_path=skill_path if (skill_created or skill_updated) else None,
            references_copied=files_copied,
            links_resolved=0  # No longer tracking link resolution
        )
    
    def _sync_to_claude_skills(
        self, package_info, primitives: dict, skill_name: str, project_root: Path
    ) -> Path | None:
        """Copy generated skill to .claude/skills/ if .claude/ directory exists.
        
        T7: Compatibility copy for Claude Code users.
        Only copies if .claude/ folder already exists - does NOT create it.
        
        Args:
            package_info: PackageInfo object with package metadata
            primitives: Dict of primitive type -> list of files
            skill_name: Normalized skill name
            project_root: Root directory of the project
            
        Returns:
            Path to .claude/skills/{name}/ or None if .claude/ doesn't exist
        """
        claude_dir = project_root / ".claude"
        if not claude_dir.exists() or not claude_dir.is_dir():
            return None
        
        # Create .claude/skills/{skill_name}/
        claude_skill_dir = claude_dir / "skills" / skill_name
        claude_skill_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate the skill file (identical to .github/skills/)
        self._generate_skill_file(package_info, primitives, claude_skill_dir)
        
        return claude_skill_dir
    
    def sync_integration(self, apm_package, project_root: Path) -> Dict[str, int]:
        """Sync .github/skills/ and .claude/skills/ with currently installed packages.
        
        Removes skill directories for packages that are no longer installed.
        Uses npm-style approach: derives expected skill directory names from
        installed dependencies and removes any directory not in that set.
        
        T7 Enhancement: Cleans both .github/skills/ and .claude/skills/ locations.
        
        Args:
            apm_package: APMPackage with current dependencies
            project_root: Root directory of the project
            
        Returns:
            Dict with cleanup statistics
        """
        stats = {'files_removed': 0, 'errors': 0}
        
        # Build set of expected skill directory names from installed packages
        installed_skill_names = set()
        for dep in apm_package.get_apm_dependencies():
            # Derive skill name the same way copy_native_skill / copy_skill_to_target does
            raw_name = dep.repo_url.split('/')[-1]
            if dep.is_virtual and dep.virtual_path:
                raw_name = dep.virtual_path.split('/')[-1]
            is_valid, _ = validate_skill_name(raw_name)
            skill_name = raw_name if is_valid else normalize_skill_name(raw_name)
            installed_skill_names.add(skill_name)
        
        # Clean .github/skills/ (primary)
        github_skills_dir = project_root / ".github" / "skills"
        if github_skills_dir.exists():
            result = self._clean_orphaned_skills(github_skills_dir, installed_skill_names)
            stats['files_removed'] += result['files_removed']
            stats['errors'] += result['errors']
        
        # Clean .claude/skills/ (secondary - T7 compatibility)
        claude_skills_dir = project_root / ".claude" / "skills"
        if claude_skills_dir.exists():
            result = self._clean_orphaned_skills(claude_skills_dir, installed_skill_names)
            stats['files_removed'] += result['files_removed']
            stats['errors'] += result['errors']
        
        return stats
    
    def _clean_orphaned_skills(self, skills_dir: Path, installed_skill_names: set) -> Dict[str, int]:
        """Clean orphaned skills from a skills directory.
        
        Uses npm-style approach: any skill directory not matching an installed
        package name is considered orphaned and removed.
        
        Args:
            skills_dir: Path to skills directory (.github/skills/ or .claude/skills/)
            installed_skill_names: Set of expected skill directory names
            
        Returns:
            Dict with cleanup statistics
        """
        files_removed = 0
        errors = 0
        
        for skill_subdir in skills_dir.iterdir():
            if skill_subdir.is_dir():
                if skill_subdir.name not in installed_skill_names:
                    try:
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
            ".github/skills/*-apm/",  # APM-generated skills use -apm suffix
            "# APM-generated skills"
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

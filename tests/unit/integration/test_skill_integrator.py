"""Tests for skill integration functionality (Claude Code SKILL.md support)."""

import pytest
import tempfile
import shutil
import hashlib
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from apm_cli.integration.skill_integrator import SkillIntegrator, SkillIntegrationResult, to_hyphen_case
from apm_cli.models.apm_package import PackageInfo, APMPackage, ResolvedReference, GitReferenceType


class TestToHyphenCase:
    """Test the to_hyphen_case helper function."""
    
    def test_basic_lowercase(self):
        """Test simple lowercase string."""
        assert to_hyphen_case("mypackage") == "mypackage"
    
    def test_camel_case(self):
        """Test camelCase conversion."""
        assert to_hyphen_case("myPackage") == "my-package"
    
    def test_pascal_case(self):
        """Test PascalCase conversion."""
        assert to_hyphen_case("MyPackage") == "my-package"
    
    def test_multi_camel_case(self):
        """Test multiple camelCase words."""
        assert to_hyphen_case("myAwesomePackageName") == "my-awesome-package-name"
    
    def test_with_underscores(self):
        """Test underscore replacement."""
        assert to_hyphen_case("my_package") == "my-package"
    
    def test_with_spaces(self):
        """Test space replacement."""
        assert to_hyphen_case("my package") == "my-package"
    
    def test_owner_repo_format(self):
        """Test owner/repo format extracts repo name."""
        assert to_hyphen_case("danielmeppiel/design-guidelines") == "design-guidelines"
        assert to_hyphen_case("owner/MyRepo") == "my-repo"
    
    def test_mixed_separators(self):
        """Test mixed underscores and camelCase."""
        assert to_hyphen_case("my_AwesomePackage") == "my-awesome-package"
    
    def test_removes_invalid_characters(self):
        """Test removal of invalid characters."""
        assert to_hyphen_case("my@package!name") == "mypackagename"
    
    def test_removes_consecutive_hyphens(self):
        """Test consecutive hyphens are collapsed."""
        assert to_hyphen_case("my--package") == "my-package"
        assert to_hyphen_case("my___package") == "my-package"
    
    def test_strips_leading_trailing_hyphens(self):
        """Test leading/trailing hyphens are stripped."""
        assert to_hyphen_case("-mypackage-") == "mypackage"
        assert to_hyphen_case("_mypackage_") == "mypackage"
    
    def test_truncates_to_64_chars(self):
        """Test truncation to Claude Skills spec limit of 64 chars."""
        long_name = "a" * 100
        result = to_hyphen_case(long_name)
        assert len(result) == 64
        assert result == "a" * 64
    
    def test_empty_string(self):
        """Test empty string handling."""
        assert to_hyphen_case("") == ""
    
    def test_numbers_preserved(self):
        """Test numbers are preserved."""
        assert to_hyphen_case("package123") == "package123"
        assert to_hyphen_case("my2ndPackage") == "my2nd-package"


class TestSkillIntegrator:
    """Test SkillIntegrator class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)
        self.integrator = SkillIntegrator()
    
    def teardown_method(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    # ========== should_integrate tests ==========
    
    def test_should_integrate_always_returns_true(self):
        """Test that integration is always enabled."""
        assert self.integrator.should_integrate(self.project_root) is True
        
        # Even with various directories present
        (self.project_root / ".github").mkdir()
        assert self.integrator.should_integrate(self.project_root) is True
    
    # ========== find_instruction_files tests ==========
    
    def test_find_instruction_files_in_apm_instructions(self):
        """Test finding instruction files in .apm/instructions/."""
        package_dir = self.project_root / "package"
        apm_instructions = package_dir / ".apm" / "instructions"
        apm_instructions.mkdir(parents=True)
        
        (apm_instructions / "coding.instructions.md").write_text("# Coding Instructions")
        (apm_instructions / "testing.instructions.md").write_text("# Testing Instructions")
        (apm_instructions / "readme.md").write_text("# Not an instruction")  # Should not match
        
        instructions = self.integrator.find_instruction_files(package_dir)
        
        assert len(instructions) == 2
        assert all(p.name.endswith('.instructions.md') for p in instructions)
    
    def test_find_instruction_files_empty_when_no_directory(self):
        """Test returns empty list when .apm/instructions/ doesn't exist."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        
        instructions = self.integrator.find_instruction_files(package_dir)
        
        assert instructions == []
    
    def test_find_instruction_files_empty_when_no_files(self):
        """Test returns empty list when directory exists but has no instruction files."""
        package_dir = self.project_root / "package"
        apm_instructions = package_dir / ".apm" / "instructions"
        apm_instructions.mkdir(parents=True)
        
        instructions = self.integrator.find_instruction_files(package_dir)
        
        assert instructions == []
    
    # ========== find_agent_files tests ==========
    
    def test_find_agent_files_in_apm_agents(self):
        """Test finding agent files in .apm/agents/."""
        package_dir = self.project_root / "package"
        apm_agents = package_dir / ".apm" / "agents"
        apm_agents.mkdir(parents=True)
        
        (apm_agents / "reviewer.agent.md").write_text("# Reviewer Agent")
        (apm_agents / "debugger.agent.md").write_text("# Debugger Agent")
        (apm_agents / "other.md").write_text("# Not an agent")  # Should not match
        
        agents = self.integrator.find_agent_files(package_dir)
        
        assert len(agents) == 2
        assert all(p.name.endswith('.agent.md') for p in agents)
    
    def test_find_agent_files_empty_when_no_directory(self):
        """Test returns empty list when .apm/agents/ doesn't exist."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        
        agents = self.integrator.find_agent_files(package_dir)
        
        assert agents == []
    
    def test_find_agent_files_empty_when_no_files(self):
        """Test returns empty list when directory exists but has no agent files."""
        package_dir = self.project_root / "package"
        apm_agents = package_dir / ".apm" / "agents"
        apm_agents.mkdir(parents=True)
        
        agents = self.integrator.find_agent_files(package_dir)
        
        assert agents == []
    
    # ========== find_prompt_files tests ==========
    
    def test_find_prompt_files_in_root(self):
        """Test finding prompt files in package root."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        
        (package_dir / "design-review.prompt.md").write_text("# Design Review")
        (package_dir / "code-audit.prompt.md").write_text("# Code Audit")
        (package_dir / "readme.md").write_text("# Readme")  # Should not match
        
        prompts = self.integrator.find_prompt_files(package_dir)
        
        assert len(prompts) == 2
        assert all(p.name.endswith('.prompt.md') for p in prompts)
    
    def test_find_prompt_files_in_apm_prompts(self):
        """Test finding prompt files in .apm/prompts/."""
        package_dir = self.project_root / "package"
        apm_prompts = package_dir / ".apm" / "prompts"
        apm_prompts.mkdir(parents=True)
        
        (apm_prompts / "workflow.prompt.md").write_text("# Workflow")
        
        prompts = self.integrator.find_prompt_files(package_dir)
        
        assert len(prompts) == 1
        assert prompts[0].name == "workflow.prompt.md"
    
    def test_find_prompt_files_combines_root_and_apm(self):
        """Test finding prompt files from both root and .apm/prompts/."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        apm_prompts = package_dir / ".apm" / "prompts"
        apm_prompts.mkdir(parents=True)
        
        (package_dir / "root.prompt.md").write_text("# Root Prompt")
        (apm_prompts / "nested.prompt.md").write_text("# Nested Prompt")
        
        prompts = self.integrator.find_prompt_files(package_dir)
        
        assert len(prompts) == 2
        prompt_names = [p.name for p in prompts]
        assert "root.prompt.md" in prompt_names
        assert "nested.prompt.md" in prompt_names
    
    def test_find_prompt_files_empty_when_no_prompts(self):
        """Test returns empty list when no prompt files exist."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        
        prompts = self.integrator.find_prompt_files(package_dir)
        
        assert prompts == []
    
    # ========== find_context_files tests ==========
    
    def test_find_context_files_in_apm_context(self):
        """Test finding context files in .apm/context/."""
        package_dir = self.project_root / "package"
        apm_context = package_dir / ".apm" / "context"
        apm_context.mkdir(parents=True)
        
        (apm_context / "project.context.md").write_text("# Project Context")
        
        context_files = self.integrator.find_context_files(package_dir)
        
        assert len(context_files) == 1
        assert context_files[0].name == "project.context.md"
    
    def test_find_context_files_in_apm_memory(self):
        """Test finding memory files in .apm/memory/."""
        package_dir = self.project_root / "package"
        apm_memory = package_dir / ".apm" / "memory"
        apm_memory.mkdir(parents=True)
        
        (apm_memory / "history.memory.md").write_text("# History Memory")
        
        context_files = self.integrator.find_context_files(package_dir)
        
        assert len(context_files) == 1
        assert context_files[0].name == "history.memory.md"
    
    def test_find_context_files_combines_context_and_memory(self):
        """Test finding files from both context and memory directories."""
        package_dir = self.project_root / "package"
        apm_context = package_dir / ".apm" / "context"
        apm_memory = package_dir / ".apm" / "memory"
        apm_context.mkdir(parents=True)
        apm_memory.mkdir(parents=True)
        
        (apm_context / "project.context.md").write_text("# Context")
        (apm_memory / "history.memory.md").write_text("# Memory")
        
        context_files = self.integrator.find_context_files(package_dir)
        
        assert len(context_files) == 2
    
    # ========== _copy_prompts_to_references tests ==========
    
    def test_copy_prompts_to_references_creates_directory(self):
        """Test that references directory is created."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        (package_dir / "test.prompt.md").write_text("# Test Prompt")
        
        references_dir = self.project_root / "references"
        
        copied = self.integrator._copy_prompts_to_references(package_dir, references_dir)
        
        assert copied == 1
        assert references_dir.exists()
        assert (references_dir / "test.prompt.md").exists()
    
    def test_copy_prompts_to_references_copies_all_prompts(self):
        """Test that all prompt files are copied."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        apm_prompts = package_dir / ".apm" / "prompts"
        apm_prompts.mkdir(parents=True)
        
        (package_dir / "root.prompt.md").write_text("# Root")
        (apm_prompts / "nested.prompt.md").write_text("# Nested")
        
        references_dir = self.project_root / "references"
        
        copied = self.integrator._copy_prompts_to_references(package_dir, references_dir)
        
        assert copied == 2
        assert (references_dir / "root.prompt.md").exists()
        assert (references_dir / "nested.prompt.md").exists()
    
    def test_copy_prompts_to_references_returns_zero_when_no_prompts(self):
        """Test returns 0 when no prompt files exist."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        
        references_dir = self.project_root / "references"
        
        copied = self.integrator._copy_prompts_to_references(package_dir, references_dir)
        
        assert copied == 0
        assert not references_dir.exists()
    
    def test_copy_prompts_to_references_preserves_content(self):
        """Test that file content is preserved when copying."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        
        original_content = "# Test Prompt\n\nThis is the content."
        (package_dir / "test.prompt.md").write_text(original_content)
        
        references_dir = self.project_root / "references"
        
        self.integrator._copy_prompts_to_references(package_dir, references_dir)
        
        copied_content = (references_dir / "test.prompt.md").read_text()
        assert copied_content == original_content
    
    # ========== integrate_package_skill tests ==========
    
    def _create_package_info(
        self,
        name: str = "test-pkg",
        version: str = "1.0.0",
        commit: str = "abc123",
        install_path: Path = None,
        source: str = None,
        description: str = None
    ) -> PackageInfo:
        """Helper to create PackageInfo objects for tests."""
        package = APMPackage(
            name=name,
            version=version,
            package_path=install_path or self.project_root / "package",
            source=source or f"github.com/test/{name}",
            description=description
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit=commit,
            ref_name="main"
        )
        return PackageInfo(
            package=package,
            install_path=install_path or self.project_root / "package",
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat()
        )
    
    def test_integrate_package_skill_creates_skill_md(self):
        """Test that SKILL.md is created when package has content."""
        package_dir = self.project_root / "package"
        apm_instructions = package_dir / ".apm" / "instructions"
        apm_instructions.mkdir(parents=True)
        (apm_instructions / "coding.instructions.md").write_text("# Coding Guidelines")
        
        package_info = self._create_package_info(install_path=package_dir)
        
        result = self.integrator.integrate_package_skill(package_info, self.project_root)
        
        assert result.skill_created is True
        assert result.skill_updated is False
        assert result.skill_skipped is False
        assert result.skill_path == package_dir / "SKILL.md"
        assert (package_dir / "SKILL.md").exists()
    
    def test_integrate_package_skill_skips_when_no_content(self):
        """Test that integration is skipped when package has no primitives."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        
        package_info = self._create_package_info(install_path=package_dir)
        
        result = self.integrator.integrate_package_skill(package_info, self.project_root)
        
        assert result.skill_created is False
        assert result.skill_updated is False
        assert result.skill_skipped is True
        assert result.skill_path is None
        assert not (package_dir / "SKILL.md").exists()
    
    def test_integrate_package_skill_creates_references_directory(self):
        """Test that references directory is created with prompt files."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        (package_dir / "test.prompt.md").write_text("# Test Prompt")
        
        package_info = self._create_package_info(install_path=package_dir)
        
        result = self.integrator.integrate_package_skill(package_info, self.project_root)
        
        assert result.skill_created is True
        assert result.references_copied == 1
        assert (package_dir / "references").exists()
        assert (package_dir / "references" / "test.prompt.md").exists()
    
    def test_integrate_package_skill_yaml_frontmatter_has_required_fields(self):
        """Test that generated SKILL.md has required YAML frontmatter fields."""
        package_dir = self.project_root / "package"
        apm_agents = package_dir / ".apm" / "agents"
        apm_agents.mkdir(parents=True)
        (apm_agents / "helper.agent.md").write_text("# Helper Agent")
        
        package_info = self._create_package_info(
            name="my-package",
            version="2.0.0",
            commit="def456",
            install_path=package_dir,
            description="A test package"
        )
        
        self.integrator.integrate_package_skill(package_info, self.project_root)
        
        content = (package_dir / "SKILL.md").read_text()
        
        # Check YAML frontmatter structure
        assert content.startswith("---")
        assert "name:" in content
        assert "description:" in content
        assert "metadata:" in content
        assert "apm_package:" in content
        assert "apm_version:" in content
        assert "apm_commit:" in content
        assert "apm_installed_at:" in content
        assert "apm_content_hash:" in content
    
    def test_integrate_package_skill_name_follows_hyphen_case(self):
        """Test that skill name is in hyphen-case format."""
        package_dir = self.project_root / "package"
        apm_agents = package_dir / ".apm" / "agents"
        apm_agents.mkdir(parents=True)
        (apm_agents / "helper.agent.md").write_text("# Helper Agent")
        
        package_info = self._create_package_info(
            name="MyAwesomePackage",
            install_path=package_dir,
            source="github.com/owner/MyAwesomePackage"
        )
        
        self.integrator.integrate_package_skill(package_info, self.project_root)
        
        content = (package_dir / "SKILL.md").read_text()
        
        # The name should be converted to hyphen-case
        assert "name: my-awesome-package" in content
    
    def test_integrate_package_skill_includes_instructions_section(self):
        """Test that SKILL.md includes instructions content."""
        package_dir = self.project_root / "package"
        apm_instructions = package_dir / ".apm" / "instructions"
        apm_instructions.mkdir(parents=True)
        (apm_instructions / "coding.instructions.md").write_text("Follow coding standards")
        
        package_info = self._create_package_info(install_path=package_dir)
        
        self.integrator.integrate_package_skill(package_info, self.project_root)
        
        content = (package_dir / "SKILL.md").read_text()
        
        assert "## Instructions" in content
        assert "### Coding" in content
        assert "Follow coding standards" in content
    
    def test_integrate_package_skill_includes_agents_section(self):
        """Test that SKILL.md includes agents content."""
        package_dir = self.project_root / "package"
        apm_agents = package_dir / ".apm" / "agents"
        apm_agents.mkdir(parents=True)
        (apm_agents / "reviewer.agent.md").write_text("Review code for quality")
        
        package_info = self._create_package_info(install_path=package_dir)
        
        self.integrator.integrate_package_skill(package_info, self.project_root)
        
        content = (package_dir / "SKILL.md").read_text()
        
        assert "## Agents" in content
        assert "### Reviewer" in content
        assert "Review code for quality" in content
    
    def test_integrate_package_skill_includes_prompts_section(self):
        """Test that SKILL.md includes prompts reference section."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        (package_dir / "design-review.prompt.md").write_text("# Design Review")
        
        package_info = self._create_package_info(install_path=package_dir)
        
        self.integrator.integrate_package_skill(package_info, self.project_root)
        
        content = (package_dir / "SKILL.md").read_text()
        
        assert "## Available Prompts" in content
        assert "references/" in content
        assert "design-review.prompt.md" in content
    
    def test_integrate_package_skill_updates_when_version_changes(self):
        """Test that SKILL.md is updated when package version changes."""
        package_dir = self.project_root / "package"
        apm_agents = package_dir / ".apm" / "agents"
        apm_agents.mkdir(parents=True)
        (apm_agents / "helper.agent.md").write_text("# Helper")
        
        # Create initial SKILL.md with old version
        old_content = """---
name: test-pkg
description: Old description
metadata:
  apm_package: test-pkg@1.0.0
  apm_version: '1.0.0'
  apm_commit: abc123
  apm_installed_at: '2024-01-01T00:00:00'
  apm_content_hash: oldhash
---

# Old content"""
        skill_path = package_dir / "SKILL.md"
        skill_path.write_text(old_content)
        
        # Install with new version
        package_info = self._create_package_info(
            version="2.0.0",
            commit="abc123",
            install_path=package_dir
        )
        
        result = self.integrator.integrate_package_skill(package_info, self.project_root)
        
        assert result.skill_created is False
        assert result.skill_updated is True
        assert result.skill_skipped is False
        
        new_content = skill_path.read_text()
        assert "apm_version: '2.0.0'" in new_content or "apm_version: 2.0.0" in new_content
    
    def test_integrate_package_skill_updates_when_commit_changes(self):
        """Test that SKILL.md is updated when commit hash changes."""
        package_dir = self.project_root / "package"
        apm_agents = package_dir / ".apm" / "agents"
        apm_agents.mkdir(parents=True)
        (apm_agents / "helper.agent.md").write_text("# Helper")
        
        # Create initial SKILL.md with old commit
        old_content = """---
name: test-pkg
description: Old description
metadata:
  apm_package: test-pkg@1.0.0
  apm_version: '1.0.0'
  apm_commit: abc123
  apm_installed_at: '2024-01-01T00:00:00'
  apm_content_hash: oldhash
---

# Old content"""
        skill_path = package_dir / "SKILL.md"
        skill_path.write_text(old_content)
        
        # Install with new commit
        package_info = self._create_package_info(
            version="1.0.0",
            commit="def456",  # New commit
            install_path=package_dir
        )
        
        result = self.integrator.integrate_package_skill(package_info, self.project_root)
        
        assert result.skill_created is False
        assert result.skill_updated is True
        assert result.skill_skipped is False
    
    def test_integrate_package_skill_skips_when_unchanged(self):
        """Test that SKILL.md is skipped when version and commit unchanged."""
        package_dir = self.project_root / "package"
        apm_agents = package_dir / ".apm" / "agents"
        apm_agents.mkdir(parents=True)
        (apm_agents / "helper.agent.md").write_text("# Helper")
        
        # Create initial SKILL.md with same version and commit
        old_content = """---
name: test-pkg
description: Old description
metadata:
  apm_package: test-pkg@1.0.0
  apm_version: '1.0.0'
  apm_commit: abc123
  apm_installed_at: '2024-01-01T00:00:00'
  apm_content_hash: somehash
---

# Old content"""
        skill_path = package_dir / "SKILL.md"
        skill_path.write_text(old_content)
        
        # Install with same version and commit
        package_info = self._create_package_info(
            version="1.0.0",
            commit="abc123",
            install_path=package_dir
        )
        
        result = self.integrator.integrate_package_skill(package_info, self.project_root)
        
        assert result.skill_created is False
        assert result.skill_updated is False
        assert result.skill_skipped is True
    
    def test_integrate_package_skill_with_only_prompts(self):
        """Test integration works with only prompt files."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        (package_dir / "review.prompt.md").write_text("# Review Prompt")
        
        package_info = self._create_package_info(install_path=package_dir)
        
        result = self.integrator.integrate_package_skill(package_info, self.project_root)
        
        assert result.skill_created is True
        assert result.references_copied == 1
    
    def test_integrate_package_skill_with_only_context(self):
        """Test integration works with only context files."""
        package_dir = self.project_root / "package"
        apm_context = package_dir / ".apm" / "context"
        apm_context.mkdir(parents=True)
        (apm_context / "project.context.md").write_text("# Project Context")
        
        package_info = self._create_package_info(install_path=package_dir)
        
        result = self.integrator.integrate_package_skill(package_info, self.project_root)
        
        assert result.skill_created is True
        content = (package_dir / "SKILL.md").read_text()
        assert "## Context" in content
    
    # ========== YAML frontmatter validation tests ==========
    
    def test_skill_md_description_truncated_to_1024_chars(self):
        """Test that description is truncated to Claude Skills spec limit."""
        package_dir = self.project_root / "package"
        apm_agents = package_dir / ".apm" / "agents"
        apm_agents.mkdir(parents=True)
        (apm_agents / "helper.agent.md").write_text("# Helper")
        
        long_description = "A" * 2000  # Longer than 1024 limit
        package_info = self._create_package_info(
            install_path=package_dir,
            description=long_description
        )
        
        self.integrator.integrate_package_skill(package_info, self.project_root)
        
        content = (package_dir / "SKILL.md").read_text()
        
        # Parse the frontmatter to check description length
        import frontmatter
        post = frontmatter.loads(content)
        assert len(post.metadata.get('description', '')) <= 1024
    
    def test_skill_md_includes_content_hash(self):
        """Test that SKILL.md includes content hash for change detection."""
        package_dir = self.project_root / "package"
        apm_instructions = package_dir / ".apm" / "instructions"
        apm_instructions.mkdir(parents=True)
        (apm_instructions / "test.instructions.md").write_text("# Test Content")
        
        package_info = self._create_package_info(install_path=package_dir)
        
        self.integrator.integrate_package_skill(package_info, self.project_root)
        
        content = (package_dir / "SKILL.md").read_text()
        assert "apm_content_hash:" in content
    
    # ========== update_gitignore_for_skills tests ==========
    
    def test_update_gitignore_adds_skill_patterns(self):
        """Test that gitignore is updated with SKILL.md patterns."""
        gitignore = self.project_root / ".gitignore"
        gitignore.write_text("# Existing content\napm_modules/\n")
        
        updated = self.integrator.update_gitignore_for_skills(self.project_root)
        
        assert updated is True
        content = gitignore.read_text()
        assert "apm_modules/**/SKILL.md" in content
        assert "apm_modules/**/references/" in content
    
    def test_update_gitignore_skips_if_patterns_exist(self):
        """Test that gitignore update is skipped if patterns already exist."""
        gitignore = self.project_root / ".gitignore"
        gitignore.write_text("apm_modules/**/SKILL.md\napm_modules/**/references/\n")
        
        updated = self.integrator.update_gitignore_for_skills(self.project_root)
        
        assert updated is False
    
    def test_update_gitignore_creates_file_if_missing(self):
        """Test that gitignore is created if it doesn't exist."""
        updated = self.integrator.update_gitignore_for_skills(self.project_root)
        
        assert updated is True
        gitignore = self.project_root / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text()
        assert "apm_modules/**/SKILL.md" in content
    
    # ========== sync_integration tests ==========
    
    def test_sync_integration_returns_zero_stats(self):
        """Test that sync returns zero stats (cleanup handled by package removal)."""
        apm_package = Mock()
        apm_package.get_apm_dependencies.return_value = []
        
        result = self.integrator.sync_integration(apm_package, self.project_root)
        
        assert result == {'files_removed': 0, 'errors': 0}
    
    # ========== Edge cases ==========
    
    def test_integrate_handles_frontmatter_in_source_files(self):
        """Test that frontmatter is stripped from source files."""
        package_dir = self.project_root / "package"
        apm_instructions = package_dir / ".apm" / "instructions"
        apm_instructions.mkdir(parents=True)
        
        content_with_frontmatter = """---
title: Test Instructions
version: 1.0
---

# Actual Instructions

This is the content."""
        (apm_instructions / "test.instructions.md").write_text(content_with_frontmatter)
        
        package_info = self._create_package_info(install_path=package_dir)
        
        self.integrator.integrate_package_skill(package_info, self.project_root)
        
        skill_content = (package_dir / "SKILL.md").read_text()
        
        # The content should be included without duplicate frontmatter
        assert "# Actual Instructions" in skill_content
        assert "This is the content." in skill_content
    
    def test_integrate_with_multiple_primitive_types(self):
        """Test integration with all primitive types present."""
        package_dir = self.project_root / "package"
        
        # Create all types of primitives
        apm_instructions = package_dir / ".apm" / "instructions"
        apm_agents = package_dir / ".apm" / "agents"
        apm_context = package_dir / ".apm" / "context"
        
        apm_instructions.mkdir(parents=True)
        apm_agents.mkdir(parents=True)
        apm_context.mkdir(parents=True)
        
        (apm_instructions / "coding.instructions.md").write_text("# Coding")
        (apm_agents / "reviewer.agent.md").write_text("# Reviewer")
        (apm_context / "project.context.md").write_text("# Project")
        (package_dir / "workflow.prompt.md").write_text("# Workflow")
        
        package_info = self._create_package_info(install_path=package_dir)
        
        result = self.integrator.integrate_package_skill(package_info, self.project_root)
        
        assert result.skill_created is True
        assert result.references_copied == 1
        
        skill_content = (package_dir / "SKILL.md").read_text()
        assert "## Instructions" in skill_content
        assert "## Agents" in skill_content
        assert "## Context" in skill_content
        assert "## Available Prompts" in skill_content


class TestSkillIntegrationResult:
    """Test SkillIntegrationResult dataclass."""
    
    def test_result_defaults(self):
        """Test result dataclass default values."""
        result = SkillIntegrationResult(
            skill_created=False,
            skill_updated=False,
            skill_skipped=True,
            skill_path=None,
            references_copied=0
        )
        
        assert result.skill_created is False
        assert result.skill_updated is False
        assert result.skill_skipped is True
        assert result.skill_path is None
        assert result.references_copied == 0
        assert result.links_resolved == 0
    
    def test_result_with_values(self):
        """Test result dataclass with values."""
        skill_path = Path("/test/SKILL.md")
        result = SkillIntegrationResult(
            skill_created=True,
            skill_updated=False,
            skill_skipped=False,
            skill_path=skill_path,
            references_copied=3,
            links_resolved=5
        )
        
        assert result.skill_created is True
        assert result.skill_path == skill_path
        assert result.references_copied == 3
        assert result.links_resolved == 5

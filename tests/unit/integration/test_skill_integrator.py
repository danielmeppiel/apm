"""Tests for skill integration functionality (Claude Code SKILL.md support)."""

import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock
from datetime import datetime

from apm_cli.integration.skill_integrator import SkillIntegrator, SkillIntegrationResult, to_hyphen_case
from apm_cli.models.apm_package import PackageInfo, APMPackage, ResolvedReference, GitReferenceType, DependencyReference


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
    
    def _get_skill_path(self, package_info) -> Path:
        """Get the expected skill directory path for a package."""
        source = package_info.package.source or package_info.package.name
        skill_name = to_hyphen_case(source)
        return self.project_root / ".claude" / "skills" / skill_name
    
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
        
        skill_dir = self.project_root / "skill"
        skill_dir.mkdir()
        
        primitives = {'prompts': [package_dir / "test.prompt.md"]}
        copied = self.integrator._copy_primitives_to_skill(primitives, skill_dir)
        
        assert copied == 1
        assert (skill_dir / "prompts").exists()
        assert (skill_dir / "prompts" / "test.prompt.md").exists()
    
    def test_copy_primitives_copies_all_types(self):
        """Test that all primitive types are copied to correct subdirectories."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        apm_instructions = package_dir / ".apm" / "instructions"
        apm_instructions.mkdir(parents=True)
        apm_prompts = package_dir / ".apm" / "prompts"
        apm_prompts.mkdir(parents=True)
        
        (apm_instructions / "coding.instructions.md").write_text("# Coding")
        (apm_prompts / "review.prompt.md").write_text("# Review")
        (package_dir / "root.prompt.md").write_text("# Root")
        
        skill_dir = self.project_root / "skill"
        skill_dir.mkdir()
        
        primitives = {
            'instructions': [apm_instructions / "coding.instructions.md"],
            'prompts': [apm_prompts / "review.prompt.md", package_dir / "root.prompt.md"]
        }
        copied = self.integrator._copy_primitives_to_skill(primitives, skill_dir)
        
        assert copied == 3
        assert (skill_dir / "instructions" / "coding.instructions.md").exists()
        assert (skill_dir / "prompts" / "review.prompt.md").exists()
        assert (skill_dir / "prompts" / "root.prompt.md").exists()
    
    def test_copy_primitives_returns_zero_when_empty(self):
        """Test returns 0 when no primitives exist."""
        skill_dir = self.project_root / "skill"
        skill_dir.mkdir()
        
        primitives = {}
        copied = self.integrator._copy_primitives_to_skill(primitives, skill_dir)
        
        assert copied == 0
    
    def test_copy_primitives_preserves_content(self):
        """Test that file content is preserved when copying."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        
        original_content = "# Test Prompt\n\nThis is the content."
        (package_dir / "test.prompt.md").write_text(original_content)
        
        skill_dir = self.project_root / "skill"
        skill_dir.mkdir()
        
        primitives = {'prompts': [package_dir / "test.prompt.md"]}
        self.integrator._copy_primitives_to_skill(primitives, skill_dir)
        
        copied_content = (skill_dir / "prompts" / "test.prompt.md").read_text()
        assert copied_content == original_content
    
    # ========== integrate_package_skill tests ==========
    
    def _create_package_info(
        self,
        name: str = "test-pkg",
        version: str = "1.0.0",
        commit: str = "abc123",
        install_path: Path = None,
        source: str = None,
        description: str = None,
        dependency_ref: DependencyReference = None
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
            installed_at=datetime.now().isoformat(),
            dependency_ref=dependency_ref
        )
    
    def test_integrate_package_skill_creates_skill_md(self):
        """Test that SKILL.md is created when package has content."""
        package_dir = self.project_root / "package"
        apm_instructions = package_dir / ".apm" / "instructions"
        apm_instructions.mkdir(parents=True)
        (apm_instructions / "coding.instructions.md").write_text("# Coding Guidelines")
        
        package_info = self._create_package_info(install_path=package_dir)
        skill_dir = self._get_skill_path(package_info)
        
        result = self.integrator.integrate_package_skill(package_info, self.project_root)
        
        assert result.skill_created is True
        assert result.skill_updated is False
        assert result.skill_skipped is False
        assert result.skill_path == skill_dir / "SKILL.md"
        assert (skill_dir / "SKILL.md").exists()
    
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
    
    def test_integrate_package_skill_skips_virtual_packages(self):
        """Test that virtual packages (single files) do not generate Skills.
        
        Virtual packages are individual files like owner/repo/agents/myagent.agent.md.
        They should not generate Skills because:
        1. Multiple virtual packages from the same repo would collide on skill name
        2. A single file doesn't constitute a proper skill with context
        """
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        # Even if there's content, virtual packages should be skipped
        (package_dir / "terraform.agent.md").write_text("# Terraform Agent\nSome agent content")
        
        # Create a virtual package dependency reference
        virtual_dep_ref = DependencyReference.parse("github/awesome-copilot/agents/terraform.agent.md")
        assert virtual_dep_ref.is_virtual  # Sanity check
        
        package_info = self._create_package_info(
            install_path=package_dir,
            name="terraform",
            source="github/awesome-copilot",
            dependency_ref=virtual_dep_ref
        )
        
        result = self.integrator.integrate_package_skill(package_info, self.project_root)
        
        # Virtual packages should be skipped
        assert result.skill_created is False
        assert result.skill_updated is False
        assert result.skill_skipped is True
        assert result.skill_path is None
        # No skill directory should be created
        skill_dir = self.project_root / ".claude" / "skills" / "awesome-copilot"
        assert not skill_dir.exists()
    
    def test_integrate_package_skill_multiple_virtual_packages_no_collision(self):
        """Test that multiple virtual packages from same repo don't create conflicting Skills.
        
        This is a regression test: previously both would try to create 'awesome-copilot' skill.
        """
        # First virtual package
        pkg1_dir = self.project_root / "pkg1"
        pkg1_dir.mkdir()
        (pkg1_dir / "jfrog-sec.agent.md").write_text("# JFrog Security Agent")
        
        virtual_dep1 = DependencyReference.parse("github/awesome-copilot/agents/jfrog-sec.agent.md")
        pkg1_info = self._create_package_info(
            install_path=pkg1_dir,
            name="jfrog-sec",
            source="github/awesome-copilot",
            dependency_ref=virtual_dep1
        )
        
        # Second virtual package from same repo
        pkg2_dir = self.project_root / "pkg2"
        pkg2_dir.mkdir()
        (pkg2_dir / "terraform.agent.md").write_text("# Terraform Agent")
        
        virtual_dep2 = DependencyReference.parse("github/awesome-copilot/agents/terraform.agent.md")
        pkg2_info = self._create_package_info(
            install_path=pkg2_dir,
            name="terraform",
            source="github/awesome-copilot",
            dependency_ref=virtual_dep2
        )
        
        # Both should be skipped, no collision occurs
        result1 = self.integrator.integrate_package_skill(pkg1_info, self.project_root)
        result2 = self.integrator.integrate_package_skill(pkg2_info, self.project_root)
        
        assert result1.skill_skipped is True
        assert result2.skill_skipped is True
        
        # No skill directories should exist
        skills_dir = self.project_root / ".claude" / "skills"
        assert not skills_dir.exists()

    def test_integrate_package_skill_creates_prompts_subdirectory(self):
        """Test that prompts subdirectory is created with prompt files."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        (package_dir / "test.prompt.md").write_text("# Test Prompt")
        
        package_info = self._create_package_info(install_path=package_dir)
        skill_dir = self._get_skill_path(package_info)
        
        result = self.integrator.integrate_package_skill(package_info, self.project_root)
        
        assert result.skill_created is True
        assert result.references_copied == 1
        assert (skill_dir / "prompts").exists()
        assert (skill_dir / "prompts" / "test.prompt.md").exists()
    
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
        skill_dir = self._get_skill_path(package_info)
        
        self.integrator.integrate_package_skill(package_info, self.project_root)
        
        content = (skill_dir / "SKILL.md").read_text()
        
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
        skill_dir = self._get_skill_path(package_info)
        
        self.integrator.integrate_package_skill(package_info, self.project_root)
        
        content = (skill_dir / "SKILL.md").read_text()
        
        # The name should be converted to hyphen-case
        assert "name: my-awesome-package" in content
    
    def test_integrate_package_skill_includes_instructions_section(self):
        """Test that SKILL.md references instructions and copies files."""
        package_dir = self.project_root / "package"
        apm_instructions = package_dir / ".apm" / "instructions"
        apm_instructions.mkdir(parents=True)
        (apm_instructions / "coding.instructions.md").write_text("Follow coding standards")
        
        package_info = self._create_package_info(install_path=package_dir)
        skill_dir = self._get_skill_path(package_info)
        
        self.integrator.integrate_package_skill(package_info, self.project_root)
        
        # SKILL.md should be concise with resource table
        content = (skill_dir / "SKILL.md").read_text()
        assert "What's Included" in content
        assert "instructions/" in content
        
        # Actual file should be in subdirectory
        assert (skill_dir / "instructions" / "coding.instructions.md").exists()
        copied_content = (skill_dir / "instructions" / "coding.instructions.md").read_text()
        assert "Follow coding standards" in copied_content
    
    def test_integrate_package_skill_includes_agents_section(self):
        """Test that SKILL.md references agents and copies files."""
        package_dir = self.project_root / "package"
        apm_agents = package_dir / ".apm" / "agents"
        apm_agents.mkdir(parents=True)
        (apm_agents / "reviewer.agent.md").write_text("Review code for quality")
        
        package_info = self._create_package_info(install_path=package_dir)
        skill_dir = self._get_skill_path(package_info)
        
        self.integrator.integrate_package_skill(package_info, self.project_root)
        
        content = (skill_dir / "SKILL.md").read_text()
        assert "What's Included" in content
        assert "agents/" in content
        
        # Actual file should be in subdirectory
        assert (skill_dir / "agents" / "reviewer.agent.md").exists()
        copied_content = (skill_dir / "agents" / "reviewer.agent.md").read_text()
        assert "Review code for quality" in copied_content
    
    def test_integrate_package_skill_includes_prompts_section(self):
        """Test that SKILL.md references prompts and copies files."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        (package_dir / "design-review.prompt.md").write_text("# Design Review")
        
        package_info = self._create_package_info(install_path=package_dir)
        skill_dir = self._get_skill_path(package_info)
        
        self.integrator.integrate_package_skill(package_info, self.project_root)
        
        content = (skill_dir / "SKILL.md").read_text()
        assert "What's Included" in content
        assert "prompts/" in content
        
        # Actual file should be in subdirectory
        assert (skill_dir / "prompts" / "design-review.prompt.md").exists()
    
    def test_integrate_package_skill_updates_when_version_changes(self):
        """Test that SKILL.md is updated when package version changes."""
        package_dir = self.project_root / "package"
        apm_agents = package_dir / ".apm" / "agents"
        apm_agents.mkdir(parents=True)
        (apm_agents / "helper.agent.md").write_text("# Helper")
        
        # Create package_info first to get the skill path
        package_info = self._create_package_info(
            version="2.0.0",
            commit="abc123",
            install_path=package_dir
        )
        skill_dir = self._get_skill_path(package_info)
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_path = skill_dir / "SKILL.md"
        
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
        skill_path.write_text(old_content)
        
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
        
        # Create package_info first to get the skill path
        package_info = self._create_package_info(
            version="1.0.0",
            commit="def456",  # New commit
            install_path=package_dir
        )
        skill_dir = self._get_skill_path(package_info)
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_path = skill_dir / "SKILL.md"
        
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
        skill_path.write_text(old_content)
        
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
        
        # Create package_info first to get the skill path
        package_info = self._create_package_info(
            version="1.0.0",
            commit="abc123",
            install_path=package_dir
        )
        skill_dir = self._get_skill_path(package_info)
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_path = skill_dir / "SKILL.md"
        
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
        skill_path.write_text(old_content)
        
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
        skill_dir = self._get_skill_path(package_info)
        
        result = self.integrator.integrate_package_skill(package_info, self.project_root)
        
        assert result.skill_created is True
        assert result.references_copied == 1
        assert (skill_dir / "SKILL.md").exists()
    
    def test_integrate_package_skill_with_only_context(self):
        """Test integration works with only context files."""
        package_dir = self.project_root / "package"
        apm_context = package_dir / ".apm" / "context"
        apm_context.mkdir(parents=True)
        (apm_context / "project.context.md").write_text("# Project Context")
        
        package_info = self._create_package_info(install_path=package_dir)
        skill_dir = self._get_skill_path(package_info)
        
        result = self.integrator.integrate_package_skill(package_info, self.project_root)
        
        assert result.skill_created is True
        content = (skill_dir / "SKILL.md").read_text()
        assert "What's Included" in content
        assert "context/" in content
        assert (skill_dir / "context" / "project.context.md").exists()
    
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
        skill_dir = self._get_skill_path(package_info)
        
        self.integrator.integrate_package_skill(package_info, self.project_root)
        
        content = (skill_dir / "SKILL.md").read_text()
        
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
        skill_dir = self._get_skill_path(package_info)
        
        self.integrator.integrate_package_skill(package_info, self.project_root)
        
        content = (skill_dir / "SKILL.md").read_text()
        assert "apm_content_hash:" in content
    
    # ========== update_gitignore_for_skills tests ==========
    
    def test_update_gitignore_adds_skill_patterns(self):
        """Test that gitignore is updated with skill patterns."""
        gitignore = self.project_root / ".gitignore"
        gitignore.write_text("# Existing content\napm_modules/\n")
        
        updated = self.integrator.update_gitignore_for_skills(self.project_root)
        
        assert updated is True
        content = gitignore.read_text()
        assert ".claude/skills/*-apm/" in content
    
    def test_update_gitignore_skips_if_patterns_exist(self):
        """Test that gitignore update is skipped if patterns already exist."""
        gitignore = self.project_root / ".gitignore"
        gitignore.write_text(".claude/skills/*-apm/\n# APM-generated Claude skills\n")
        
        updated = self.integrator.update_gitignore_for_skills(self.project_root)
        
        assert updated is False
    
    def test_update_gitignore_creates_file_if_missing(self):
        """Test that gitignore is created if it doesn't exist."""
        updated = self.integrator.update_gitignore_for_skills(self.project_root)
        
        assert updated is True
        gitignore = self.project_root / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text()
        assert ".claude/skills/*-apm/" in content
    
    # ========== sync_integration tests ==========
    
    def test_sync_integration_returns_zero_stats(self):
        """Test that sync returns zero stats (cleanup handled by package removal)."""
        apm_package = Mock()
        apm_package.get_apm_dependencies.return_value = []
        
        result = self.integrator.sync_integration(apm_package, self.project_root)
        
        assert result == {'files_removed': 0, 'errors': 0}
    
    # ========== Edge cases ==========
    
    def test_integrate_handles_frontmatter_in_source_files(self):
        """Test that source files are copied to subdirectories (frontmatter preserved)."""
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
        skill_dir = self._get_skill_path(package_info)
        
        self.integrator.integrate_package_skill(package_info, self.project_root)
        
        # File should be copied to subdirectory
        copied_file = skill_dir / "instructions" / "test.instructions.md"
        assert copied_file.exists()
        
        copied_content = copied_file.read_text()
        assert "# Actual Instructions" in copied_content
        assert "This is the content." in copied_content
    
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
        skill_dir = self._get_skill_path(package_info)
        
        result = self.integrator.integrate_package_skill(package_info, self.project_root)
        
        assert result.skill_created is True
        assert result.references_copied == 4  # All 4 primitives copied
        
        skill_content = (skill_dir / "SKILL.md").read_text()
        assert "What's Included" in skill_content
        
        # All subdirectories should exist with files
        assert (skill_dir / "instructions" / "coding.instructions.md").exists()
        assert (skill_dir / "agents" / "reviewer.agent.md").exists()
        assert (skill_dir / "context" / "project.context.md").exists()
        assert (skill_dir / "prompts" / "workflow.prompt.md").exists()


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

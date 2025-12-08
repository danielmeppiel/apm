"""Tests for skill transformer functionality (SKILL.md → .agent.md conversion)."""

import tempfile
import shutil
from pathlib import Path

from apm_cli.integration.skill_transformer import SkillTransformer, to_hyphen_case
from apm_cli.primitives.models import Skill


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
    
    def test_with_underscores(self):
        """Test underscore replacement."""
        assert to_hyphen_case("my_package") == "my-package"
    
    def test_with_spaces(self):
        """Test space replacement."""
        assert to_hyphen_case("Brand Guidelines") == "brand-guidelines"
    
    def test_mixed_separators(self):
        """Test mixed underscores and camelCase."""
        assert to_hyphen_case("my_AwesomePackage") == "my-awesome-package"
    
    def test_removes_invalid_characters(self):
        """Test removal of invalid characters."""
        assert to_hyphen_case("my@package!name") == "mypackagename"
    
    def test_removes_consecutive_hyphens(self):
        """Test consecutive hyphens are collapsed."""
        assert to_hyphen_case("my--package") == "my-package"
    
    def test_strips_leading_trailing_hyphens(self):
        """Test leading/trailing hyphens are stripped."""
        assert to_hyphen_case("-mypackage-") == "mypackage"


class TestSkillTransformer:
    """Test SkillTransformer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)
        self.transformer = SkillTransformer()
    
    def teardown_method(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_transform_to_agent_creates_directory(self):
        """Test that transform_to_agent creates .github/agents/ directory."""
        skill = Skill(
            name="Test Skill",
            file_path=Path("/fake/SKILL.md"),
            description="A test skill",
            content="# Test Skill\n\nThis is a test skill.",
            source="local"
        )
        
        result = self.transformer.transform_to_agent(skill, self.project_root)
        
        assert result is not None
        assert (self.project_root / ".github" / "agents").exists()
    
    def test_transform_to_agent_creates_agent_file(self):
        """Test that transform_to_agent creates the agent file."""
        skill = Skill(
            name="Brand Guidelines",
            file_path=Path("/fake/SKILL.md"),
            description="Corporate brand guidelines",
            content="# Brand Guidelines\n\nFollow these guidelines.",
            source="local"
        )
        
        result = self.transformer.transform_to_agent(skill, self.project_root)
        
        assert result is not None
        assert result.exists()
        assert result.name == "brand-guidelines.agent.md"
    
    def test_transform_to_agent_file_content(self):
        """Test that the generated agent file has correct content."""
        skill = Skill(
            name="Brand Guidelines",
            file_path=Path("/fake/SKILL.md"),
            description="Corporate brand guidelines",
            content="# Brand Guidelines\n\nFollow these guidelines.",
            source="local"
        )
        
        result = self.transformer.transform_to_agent(skill, self.project_root)
        content = result.read_text()
        
        # Check frontmatter
        assert "---" in content
        assert "name: Brand Guidelines" in content
        assert "description: Corporate brand guidelines" in content
        
        # Check body content
        assert "# Brand Guidelines" in content
        assert "Follow these guidelines." in content
    
    def test_transform_to_agent_with_dependency_source(self):
        """Test that source attribution is included for dependency skills."""
        skill = Skill(
            name="Compliance Rules",
            file_path=Path("/fake/SKILL.md"),
            description="Compliance rules",
            content="# Compliance\n\nFollow these rules.",
            source="dependency:owner/repo"
        )
        
        result = self.transformer.transform_to_agent(skill, self.project_root)
        content = result.read_text()
        
        assert "<!-- Source: dependency:owner/repo -->" in content
    
    def test_transform_to_agent_dry_run(self):
        """Test that dry_run returns path but doesn't write file."""
        skill = Skill(
            name="Test Skill",
            file_path=Path("/fake/SKILL.md"),
            description="A test skill",
            content="# Test",
            source="local"
        )
        
        result = self.transformer.transform_to_agent(skill, self.project_root, dry_run=True)
        
        assert result is not None
        assert result.name == "test-skill.agent.md"
        assert not result.exists()
    
    def test_get_agent_name(self):
        """Test get_agent_name method."""
        skill = Skill(
            name="Brand Guidelines",
            file_path=Path("/fake/SKILL.md"),
            description="",
            content="",
            source="local"
        )
        
        result = self.transformer.get_agent_name(skill)
        
        assert result == "brand-guidelines"
    
    def test_transform_complex_skill_name(self):
        """Test transformation with complex skill name."""
        skill = Skill(
            name="My Awesome SKILL v2",
            file_path=Path("/fake/SKILL.md"),
            description="An awesome skill",
            content="# Content",
            source="local"
        )
        
        result = self.transformer.transform_to_agent(skill, self.project_root)
        
        assert result is not None
        # Should normalize the name
        assert result.name == "my-awesome-skill-v2.agent.md"


class TestAgentIntegratorSkillSupport:
    """Test AgentIntegrator's skill handling."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)
        self.package_dir = self.project_root / "apm_modules" / "test-package"
        self.package_dir.mkdir(parents=True)
    
    def teardown_method(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_find_skill_file_when_exists(self):
        """Test finding SKILL.md when it exists."""
        from apm_cli.integration.agent_integrator import AgentIntegrator
        
        # Create SKILL.md
        skill_file = self.package_dir / "SKILL.md"
        skill_file.write_text("---\nname: Test\n---\n# Content")
        
        integrator = AgentIntegrator()
        result = integrator.find_skill_file(self.package_dir)
        
        assert result is not None
        assert result == skill_file
    
    def test_find_skill_file_when_not_exists(self):
        """Test finding SKILL.md when it doesn't exist."""
        from apm_cli.integration.agent_integrator import AgentIntegrator
        
        integrator = AgentIntegrator()
        result = integrator.find_skill_file(self.package_dir)
        
        assert result is None
    
    def test_find_skill_file_case_sensitive(self):
        """Test SKILL.md detection on case-insensitive filesystems.
        
        Note: On macOS/Windows with case-insensitive filesystems, skill.md 
        will match SKILL.md. On Linux (case-sensitive), it won't.
        This test documents the expected behavior.
        """
        from apm_cli.integration.agent_integrator import AgentIntegrator
        
        # Create lowercase skill.md
        skill_file = self.package_dir / "skill.md"
        skill_file.write_text("---\nname: Test\n---\n# Content")
        
        integrator = AgentIntegrator()
        result = integrator.find_skill_file(self.package_dir)
        
        # On case-insensitive filesystems (macOS, Windows), this will match
        # On case-sensitive filesystems (Linux), it won't
        # We just verify the function doesn't crash
        if result is not None:
            assert result.name.upper() == "SKILL.MD"

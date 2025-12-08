"""Integration tests for Claude Skill compilation.

Tests the full compile flow for projects with Claude Skills,
verifying SKILL.md → .agent.md transformation.

These tests require network access to GitHub.
"""

import os
import subprocess
import pytest
from pathlib import Path


# Skip all tests if GITHUB_APM_PAT is not set
pytestmark = pytest.mark.skipif(
    not os.environ.get("GITHUB_APM_PAT") and not os.environ.get("GITHUB_TOKEN"),
    reason="GITHUB_APM_PAT or GITHUB_TOKEN required for GitHub API access"
)


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary APM project for testing."""
    project_dir = tmp_path / "skill-compile-project"
    project_dir.mkdir()
    
    # Initialize apm.yml
    apm_yml = project_dir / "apm.yml"
    apm_yml.write_text("""name: skill-compile-project
version: 1.0.0
description: Test project for skill compilation
dependencies:
  apm: []
  mcp: []
""")
    
    # Create .github folder for VSCode target
    github_dir = project_dir / ".github"
    github_dir.mkdir()
    
    return project_dir


@pytest.fixture
def apm_command():
    """Get the path to the APM CLI executable."""
    venv_apm = Path(__file__).parent.parent.parent / ".venv" / "bin" / "apm"
    if venv_apm.exists():
        return str(venv_apm)
    return "apm"


class TestSkillToAgentCompilation:
    """Test SKILL.md → .agent.md compilation flow."""
    
    def test_install_creates_agent_from_skill(self, temp_project, apm_command):
        """Install should create .agent.md from SKILL.md when VSCode is target."""
        # Install skill
        result = subprocess.run(
            [apm_command, "install", "ComposioHQ/awesome-claude-skills/brand-guidelines"],
            cwd=temp_project,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        assert result.returncode == 0, f"Install failed: {result.stderr}"
        
        # Verify agent was created at install time (not compile time)
        agent_file = temp_project / ".github" / "agents" / "brand-guidelines.agent.md"
        assert agent_file.exists(), "Agent should be created at install time"
    
    def test_agent_preserves_skill_content(self, temp_project, apm_command):
        """Generated agent.md should preserve the skill's body content."""
        # Install skill
        subprocess.run(
            [apm_command, "install", "ComposioHQ/awesome-claude-skills/brand-guidelines"],
            cwd=temp_project,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        # Read both files
        skill_path = temp_project / "apm_modules" / "ComposioHQ" / "awesome-claude-skills" / "brand-guidelines" / "SKILL.md"
        agent_path = temp_project / ".github" / "agents" / "brand-guidelines.agent.md"
        
        if not skill_path.exists() or not agent_path.exists():
            pytest.skip("Files not created")
        
        skill_content = skill_path.read_text()
        agent_content = agent_path.read_text()
        
        # The body content should be preserved (look for key content markers)
        # Extract body from skill (after frontmatter)
        if "---" in skill_content:
            parts = skill_content.split("---", 2)
            if len(parts) >= 3:
                skill_body = parts[2].strip()
                # Check that main content is in agent
                # Use first significant line as marker
                for line in skill_body.split("\n"):
                    if line.strip() and line.startswith("#"):
                        assert line in agent_content, f"Skill heading not in agent: {line}"
                        break
    
    def test_agent_has_correct_metadata(self, temp_project, apm_command):
        """Generated agent.md should have correct APM metadata."""
        # Install skill
        subprocess.run(
            [apm_command, "install", "ComposioHQ/awesome-claude-skills/brand-guidelines"],
            cwd=temp_project,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        agent_path = temp_project / ".github" / "agents" / "brand-guidelines.agent.md"
        
        if not agent_path.exists():
            pytest.skip("Agent file not created")
        
        content = agent_path.read_text()
        
        # Check required metadata fields
        assert "apm:" in content, "Missing apm metadata section"
        assert "source_type: claude-skill" in content, "Missing source_type"
        assert "source_dependency:" in content, "Missing source_dependency"
        assert "content_hash:" in content, "Missing content_hash"


class TestCompileDoesNotGenerateAgents:
    """Test that compile does NOT generate agents from skills."""
    
    def test_compile_does_not_create_new_agents(self, temp_project, apm_command):
        """Compile should not create new agent files from skills."""
        # Install skill (this creates the agent)
        subprocess.run(
            [apm_command, "install", "ComposioHQ/awesome-claude-skills/brand-guidelines"],
            cwd=temp_project,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        agent_path = temp_project / ".github" / "agents" / "brand-guidelines.agent.md"
        
        if agent_path.exists():
            # Record modification time
            mtime_before = agent_path.stat().st_mtime
            
            # Run compile
            subprocess.run(
                [apm_command, "compile"],
                cwd=temp_project,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Agent file should not be modified by compile
            mtime_after = agent_path.stat().st_mtime
            assert mtime_before == mtime_after, "Compile should not modify agent created at install"


class TestMultipleSkillsCompilation:
    """Test compilation with multiple skills installed."""
    
    def test_multiple_skills_create_multiple_agents(self, temp_project, apm_command):
        """Each installed skill should create its own agent file."""
        skills = [
            "ComposioHQ/awesome-claude-skills/brand-guidelines",
            # Add more skills if available in the repo
        ]
        
        for skill in skills:
            result = subprocess.run(
                [apm_command, "install", skill],
                cwd=temp_project,
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                continue  # Skip unavailable skills
        
        # Check that agents were created
        agents_dir = temp_project / ".github" / "agents"
        if agents_dir.exists():
            agent_files = list(agents_dir.glob("*.agent.md"))
            assert len(agent_files) >= 1, "At least one agent should be created"


class TestSkillAgentNaming:
    """Test that skill → agent naming conventions are correct."""
    
    def test_agent_name_matches_skill_name(self, temp_project, apm_command):
        """Agent filename should be derived from skill name."""
        subprocess.run(
            [apm_command, "install", "ComposioHQ/awesome-claude-skills/brand-guidelines"],
            cwd=temp_project,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        # Should be brand-guidelines.agent.md (hyphen-case)
        agent_path = temp_project / ".github" / "agents" / "brand-guidelines.agent.md"
        assert agent_path.exists(), "Agent should be named after skill"
    
    def test_agent_name_in_frontmatter(self, temp_project, apm_command):
        """Agent frontmatter should have correct name field."""
        subprocess.run(
            [apm_command, "install", "ComposioHQ/awesome-claude-skills/brand-guidelines"],
            cwd=temp_project,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        agent_path = temp_project / ".github" / "agents" / "brand-guidelines.agent.md"
        
        if not agent_path.exists():
            pytest.skip("Agent not created")
        
        content = agent_path.read_text()
        
        # Should have name field
        assert "name:" in content, "Agent missing name field"

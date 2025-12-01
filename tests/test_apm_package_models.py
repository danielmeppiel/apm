"""Unit tests for APM package data models and validation."""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open

from src.apm_cli.models.apm_package import (
    APMPackage,
    DependencyReference, 
    ValidationResult,
    ValidationError,
    ResolvedReference,
    PackageInfo,
    GitReferenceType,
    validate_apm_package,
    parse_git_reference,
)
from apm_cli.utils import github_host


class TestDependencyReference:
    """Test DependencyReference parsing and functionality."""
    
    def test_parse_simple_repo(self):
        """Test parsing simple user/repo format."""
        dep = DependencyReference.parse("user/repo")
        assert dep.repo_url == "user/repo"
        assert dep.reference is None
        assert dep.alias is None
    
    def test_parse_with_branch(self):
        """Test parsing with branch reference."""
        dep = DependencyReference.parse("user/repo#main")
        assert dep.repo_url == "user/repo"
        assert dep.reference == "main"
        assert dep.alias is None
    
    def test_parse_with_tag(self):
        """Test parsing with tag reference."""
        dep = DependencyReference.parse("user/repo#v1.0.0")
        assert dep.repo_url == "user/repo"
        assert dep.reference == "v1.0.0"
        assert dep.alias is None
    
    def test_parse_with_commit(self):
        """Test parsing with commit SHA."""
        dep = DependencyReference.parse("user/repo#abc123def")
        assert dep.repo_url == "user/repo"
        assert dep.reference == "abc123def"
        assert dep.alias is None
    
    def test_parse_with_alias(self):
        """Test parsing with alias."""
        dep = DependencyReference.parse("user/repo@myalias")
        assert dep.repo_url == "user/repo"
        assert dep.reference is None
        assert dep.alias == "myalias"
    
    def test_parse_with_reference_and_alias(self):
        """Test parsing with both reference and alias."""
        dep = DependencyReference.parse("user/repo#main@myalias")
        assert dep.repo_url == "user/repo"
        assert dep.reference == "main"
        assert dep.alias == "myalias"
    
    def test_parse_github_urls(self):
        """Test parsing various GitHub URL formats."""
        host = github_host.default_host()
        formats = [
            f"{host}/user/repo",
            f"https://{host}/user/repo",
            f"https://{host}/user/repo.git",
            f"git@{host}:user/repo",
            f"git@{host}:user/repo.git",
        ]
        
        for url_format in formats:
            dep = DependencyReference.parse(url_format)
            assert dep.repo_url == "user/repo"

    def test_parse_ghe_urls(self):
        """Test parsing GitHub Enterprise (GHE) hostname formats like orgname.ghe.com."""
        formats = [
            "orgname.ghe.com/user/repo",
            "https://orgname.ghe.com/user/repo",
            "https://orgname.ghe.com/user/repo.git",
        ]

        for url_format in formats:
            dep = DependencyReference.parse(url_format)
            assert dep.repo_url == "user/repo"
    
    def test_parse_invalid_formats(self):
        """Test parsing invalid dependency formats."""
        invalid_formats = [
            "",
            "   ",
            "just-repo-name",
            "user/",
        ]
        
        for invalid_format in invalid_formats:
            with pytest.raises(ValueError):
                DependencyReference.parse(invalid_format)
    
    def test_parse_malicious_url_bypass_attempts(self):
        """Test that malicious URL bypass attempts are properly rejected.
        
        This tests the security fix for CWE-20: Improper Input Validation.
        Prevents attacks where an attacker embeds allowed hostnames in unexpected locations.
        """
        # Attack vectors that should be REJECTED
        malicious_formats = [
            # Subdomain attack: attacker owns prefix subdomain
            "evil-github.com/user/repo",
            "malicious-github.com/user/repo",
            "github.com.evil.com/user/repo",
            
            # Path injection: embedding github.com in path
            "evil.com/github.com/user/repo",
            "attacker.net/github.com/malicious/repo",
            
            # Domain suffix attacks
            "fakegithub.com/user/repo",
            "notgithub.com/user/repo",
            
            # Protocol-relative URL attacks
            "//evil.com/github.com/user/repo",
            
            # Mixed case attacks (domains are case-insensitive)
            "GitHub.COM.evil.com/user/repo",
            "GITHUB.com.attacker.net/user/repo",
        ]
        
        for malicious_url in malicious_formats:
            with pytest.raises(ValueError, match="Unsupported Git host"):
                DependencyReference.parse(malicious_url)
    
    def test_parse_legitimate_github_enterprise_formats(self):
        """Test that legitimate GitHub Enterprise hostnames are accepted.
        
        Ensures the security fix doesn't break valid GHE instances.
        According to is_github_hostname(), only github.com and *.ghe.com are valid.
        """
        # These should be ACCEPTED (valid GitHub Enterprise hostnames)
        valid_ghe_formats = [
            "company.ghe.com/user/repo",
            "myorg.ghe.com/user/repo",
            "github.com/user/repo",  # Standard GitHub
        ]
        
        for valid_url in valid_ghe_formats:
            dep = DependencyReference.parse(valid_url)
            assert dep.repo_url == "user/repo"
            assert dep.host is not None
    
    def test_parse_azure_devops_formats(self):
        """Test that Azure DevOps hostnames are accepted with org/project/repo format.
        
        Azure DevOps uses 3 segments (org/project/repo) instead of GitHub's 2 segments (owner/repo).
        """
        # Full ADO URL with _git segment
        dep = DependencyReference.parse("dev.azure.com/dmeppiel-org/market-js-app/_git/compliance-rules")
        assert dep.host == "dev.azure.com"
        assert dep.ado_organization == "dmeppiel-org"
        assert dep.ado_project == "market-js-app"
        assert dep.ado_repo == "compliance-rules"
        assert dep.is_azure_devops() == True
        assert dep.repo_url == "dmeppiel-org/market-js-app/compliance-rules"
        
        # Simplified ADO format (without _git)
        dep = DependencyReference.parse("dev.azure.com/myorg/myproject/myrepo")
        assert dep.host == "dev.azure.com"
        assert dep.ado_organization == "myorg"
        assert dep.ado_project == "myproject"
        assert dep.ado_repo == "myrepo"
        assert dep.is_azure_devops() == True
        
        # Legacy visualstudio.com format
        dep = DependencyReference.parse("mycompany.visualstudio.com/myorg/myproject/myrepo")
        assert dep.host == "mycompany.visualstudio.com"
        assert dep.is_azure_devops() == True
        assert dep.ado_organization == "myorg"
        assert dep.ado_project == "myproject"
        assert dep.ado_repo == "myrepo"
    
    def test_parse_azure_devops_virtual_package(self):
        """Test ADO virtual package parsing with 4-segment format (org/project/repo/path)."""
        # ADO virtual package with host prefix
        dep = DependencyReference.parse("dev.azure.com/myorg/myproject/myrepo/prompts/code-review.prompt.md")
        assert dep.is_azure_devops() == True
        assert dep.is_virtual == True
        assert dep.repo_url == "myorg/myproject/myrepo"
        assert dep.virtual_path == "prompts/code-review.prompt.md"
        assert dep.ado_organization == "myorg"
        assert dep.ado_project == "myproject"
        assert dep.ado_repo == "myrepo"
        
        # ADO virtual package with _git segment
        dep = DependencyReference.parse("dev.azure.com/myorg/myproject/_git/myrepo/prompts/test.prompt.md")
        assert dep.is_azure_devops() == True
        assert dep.is_virtual == True
        assert dep.virtual_path == "prompts/test.prompt.md"

    def test_parse_azure_devops_invalid_virtual_package(self):
        """Test that incomplete ADO virtual packages are rejected."""
        # Test case: path looks like virtual package but not enough segments for ADO
        # This would be caught when trying to extract only 3 segments but path has extension
        # (4 segments after host needed: org/project/repo/file.ext)
        # Note: "myrepo.prompt.md" is treated as repo name, not as virtual path
        # The bounds check kicks in when we have a recognized virtual package format
        # but not enough segments. This test verifies ADO virtual package paths require
        # the full org/project/repo/path structure.
        
        # Valid 4-segment ADO virtual package should work
        dep = DependencyReference.parse("dev.azure.com/org/proj/repo/file.prompt.md")
        assert dep.is_virtual == True
        assert dep.repo_url == "org/proj/repo"
        
        # 3 segments after host (org/proj/repo) without a path - this is a regular package, not virtual
        dep = DependencyReference.parse("dev.azure.com/myorg/myproject/myrepo")
        assert dep.is_virtual == False
        assert dep.repo_url == "myorg/myproject/myrepo"
    
    def test_parse_virtual_package_with_malicious_host(self):
        """Test that virtual packages with malicious hosts are rejected."""
        malicious_virtual_formats = [
            "evil.com/github.com/user/repo/prompts/file.prompt.md",
            "github.com.evil.com/user/repo/prompts/file.prompt.md",
            "attacker.net/user/repo/prompts/file.prompt.md",
        ]
        
        for malicious_url in malicious_virtual_formats:
            with pytest.raises(ValueError):
                DependencyReference.parse(malicious_url)
    
    def test_parse_virtual_file_package(self):
        """Test parsing virtual file package (individual file)."""
        dep = DependencyReference.parse("github/awesome-copilot/prompts/code-review.prompt.md")
        assert dep.repo_url == "github/awesome-copilot"
        assert dep.is_virtual is True
        assert dep.virtual_path == "prompts/code-review.prompt.md"
        assert dep.is_virtual_file() is True
        assert dep.is_virtual_collection() is False
        assert dep.get_virtual_package_name() == "awesome-copilot-code-review"
    
    def test_parse_virtual_file_with_reference(self):
        """Test parsing virtual file package with git reference."""
        dep = DependencyReference.parse("github/awesome-copilot/prompts/code-review.prompt.md#v1.0.0")
        assert dep.repo_url == "github/awesome-copilot"
        assert dep.is_virtual is True
        assert dep.virtual_path == "prompts/code-review.prompt.md"
        assert dep.reference == "v1.0.0"
        assert dep.is_virtual_file() is True
    
    def test_parse_virtual_file_all_extensions(self):
        """Test parsing virtual files with all supported extensions."""
        extensions = ['.prompt.md', '.instructions.md', '.chatmode.md', '.agent.md']
        
        for ext in extensions:
            dep = DependencyReference.parse(f"user/repo/path/to/file{ext}")
            assert dep.is_virtual is True
            assert dep.is_virtual_file() is True
            assert dep.virtual_path == f"path/to/file{ext}"
    
    def test_parse_virtual_collection(self):
        """Test parsing virtual collection package."""
        dep = DependencyReference.parse("github/awesome-copilot/collections/project-planning")
        assert dep.repo_url == "github/awesome-copilot"
        assert dep.is_virtual is True
        assert dep.virtual_path == "collections/project-planning"
        assert dep.is_virtual_file() is False
        assert dep.is_virtual_collection() is True
        assert dep.get_virtual_package_name() == "awesome-copilot-project-planning"
    
    def test_parse_virtual_collection_with_reference(self):
        """Test parsing virtual collection with git reference."""
        dep = DependencyReference.parse("github/awesome-copilot/collections/testing#main")
        assert dep.repo_url == "github/awesome-copilot"
        assert dep.is_virtual is True
        assert dep.virtual_path == "collections/testing"
        assert dep.reference == "main"
        assert dep.is_virtual_collection() is True
    
    def test_parse_invalid_virtual_file_extension(self):
        """Test that invalid file extensions are rejected for virtual files."""
        invalid_paths = [
            "user/repo/path/to/file.txt",
            "user/repo/path/to/file.md",
            "user/repo/path/to/README.md",
            "user/repo/path/to/script.py",
        ]
        
        for path in invalid_paths:
            with pytest.raises(ValueError, match="Individual files must end with one of"):
                DependencyReference.parse(path)
    
    def test_virtual_package_str_representation(self):
        """Test string representation of virtual packages.
        
        Note: After PR #33, host is explicit in string representation.
        """
        dep = DependencyReference.parse("github/awesome-copilot/prompts/code-review.prompt.md#v1.0.0")
        # Check that key components are present (host may be explicit now)
        assert "github/awesome-copilot" in str(dep)
        assert "prompts/code-review.prompt.md" in str(dep)
        assert "#v1.0.0" in str(dep)
        
        dep_with_alias = DependencyReference.parse("github/awesome-copilot/prompts/test.prompt.md@myalias")
        assert "github/awesome-copilot" in str(dep_with_alias)
        assert "prompts/test.prompt.md" in str(dep_with_alias)
        assert "@myalias" in str(dep_with_alias)
    
    def test_regular_package_not_virtual(self):
        """Test that regular packages (2 segments) are not marked as virtual."""
        dep = DependencyReference.parse("user/repo")
        assert dep.is_virtual is False
        assert dep.virtual_path is None
        assert dep.is_virtual_file() is False
        assert dep.is_virtual_collection() is False
    
    def test_parse_control_characters_rejected(self):
        """Test that control characters are rejected."""
        invalid_formats = [
            "/repo",
            "user//repo",
            "user repo",
        ]
        
        for invalid_format in invalid_formats:
            with pytest.raises(ValueError, match="Unsupported Git host|Empty dependency string|Invalid repository|Use 'user/repo'|path component"):
                DependencyReference.parse(invalid_format)
    
    def test_to_github_url(self):
        """Test converting to GitHub URL."""
        dep = DependencyReference.parse("user/repo")
        expected = f"https://{github_host.default_host()}/user/repo"
        assert dep.to_github_url() == expected
    
    def test_get_display_name(self):
        """Test getting display name."""
        dep1 = DependencyReference.parse("user/repo")
        assert dep1.get_display_name() == "user/repo"
        
        dep2 = DependencyReference.parse("user/repo@myalias")
        assert dep2.get_display_name() == "myalias"
    
    def test_string_representation(self):
        """Test string representation.
        
        Note: After PR #33, bare "user/repo" references will have host defaulted
        to github.com, so string representation includes it explicitly.
        """
        dep1 = DependencyReference.parse("user/repo")
        # After PR #33 changes, host is explicit in string representation
        assert dep1.repo_url == "user/repo"
        assert "user/repo" in str(dep1)
        
        dep2 = DependencyReference.parse("user/repo#main")
        assert dep2.repo_url == "user/repo"
        assert dep2.reference == "main"
        assert "user/repo" in str(dep2) and "#main" in str(dep2)
        
        dep3 = DependencyReference.parse("user/repo@myalias")
        assert dep3.repo_url == "user/repo"
        assert dep3.alias == "myalias"
        assert "user/repo" in str(dep3) and "@myalias" in str(dep3)
        
        dep4 = DependencyReference.parse("user/repo#main@myalias")
        assert dep4.repo_url == "user/repo"
        assert dep4.reference == "main"
        assert dep4.alias == "myalias"
        assert "user/repo" in str(dep4) and "#main" in str(dep4) and "@myalias" in str(dep4)
    
    def test_string_representation_with_enterprise_host(self):
        """Test that string representation includes host for enterprise dependencies.
        
        This tests the fix from PR #33 where __str__ now includes the host prefix
        for dependencies from non-default GitHub hosts.
        """
        # Enterprise host with just repo
        dep1 = DependencyReference.parse("company.ghe.com/user/repo")
        assert str(dep1) == "company.ghe.com/user/repo"
        
        # Enterprise host with reference
        dep2 = DependencyReference.parse("company.ghe.com/user/repo#v1.0.0")
        assert str(dep2) == "company.ghe.com/user/repo#v1.0.0"
        
        # Enterprise host with alias
        dep3 = DependencyReference.parse("company.ghe.com/user/repo@myalias")
        assert str(dep3) == "company.ghe.com/user/repo@myalias"
        
        # Enterprise host with reference and alias
        dep4 = DependencyReference.parse("company.ghe.com/user/repo#main@myalias")
        assert str(dep4) == "company.ghe.com/user/repo#main@myalias"
        
        # Explicit github.com should also include host
        dep5 = DependencyReference.parse("github.com/user/repo")
        assert str(dep5) == "github.com/user/repo"


class TestAPMPackage:
    """Test APMPackage functionality."""
    
    def test_from_apm_yml_minimal(self):
        """Test loading minimal valid apm.yml."""
        apm_content = {
            'name': 'test-package',
            'version': '1.0.0'
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(apm_content, f)
            f.flush()
            
            package = APMPackage.from_apm_yml(Path(f.name))
            assert package.name == 'test-package'
            assert package.version == '1.0.0'
            assert package.description is None
            assert package.author is None
            assert package.dependencies is None
            
        Path(f.name).unlink()  # Clean up
    
    def test_from_apm_yml_complete(self):
        """Test loading complete apm.yml."""
        apm_content = {
            'name': 'test-package',
            'version': '1.0.0',
            'description': 'A test package',
            'author': 'Test Author',
            'license': 'MIT',
            'dependencies': {
                'apm': ['user/repo#main', 'another/repo@alias'],
                'mcp': ['some-mcp-server']
            },
            'scripts': {
                'start': 'echo hello'
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(apm_content, f)
            f.flush()
            
            package = APMPackage.from_apm_yml(Path(f.name))
            assert package.name == 'test-package'
            assert package.version == '1.0.0'
            assert package.description == 'A test package'
            assert package.author == 'Test Author'
            assert package.license == 'MIT'
            assert len(package.get_apm_dependencies()) == 2
            assert len(package.get_mcp_dependencies()) == 1
            assert package.scripts['start'] == 'echo hello'
            
        Path(f.name).unlink()  # Clean up
    
    def test_from_apm_yml_missing_file(self):
        """Test loading from non-existent file."""
        with pytest.raises(FileNotFoundError):
            APMPackage.from_apm_yml(Path("/non/existent/file.yml"))
    
    def test_from_apm_yml_missing_required_fields(self):
        """Test loading apm.yml with missing required fields."""
        # Missing name
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump({'version': '1.0.0'}, f)
            f.flush()
            
            with pytest.raises(ValueError, match="Missing required field 'name'"):
                APMPackage.from_apm_yml(Path(f.name))
                
        Path(f.name).unlink()
        
        # Missing version
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump({'name': 'test'}, f)
            f.flush()
            
            with pytest.raises(ValueError, match="Missing required field 'version'"):
                APMPackage.from_apm_yml(Path(f.name))
                
        Path(f.name).unlink()
    
    def test_from_apm_yml_invalid_yaml(self):
        """Test loading invalid YAML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("name: test\nversion: 1.0.0\ninvalid: [unclosed")
            f.flush()
            
            with pytest.raises(ValueError, match="Invalid YAML format"):
                APMPackage.from_apm_yml(Path(f.name))
                
        Path(f.name).unlink()
    
    def test_from_apm_yml_invalid_dependencies(self):
        """Test loading apm.yml with invalid dependency format."""
        apm_content = {
            'name': 'test-package',
            'version': '1.0.0',
            'dependencies': {
                'apm': ['invalid-repo-format']
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(apm_content, f)
            f.flush()
            
            with pytest.raises(ValueError, match="Invalid APM dependency"):
                APMPackage.from_apm_yml(Path(f.name))
                
        Path(f.name).unlink()
    
    def test_has_apm_dependencies(self):
        """Test checking for APM dependencies."""
        # Package without dependencies
        pkg1 = APMPackage(name="test", version="1.0.0")
        assert not pkg1.has_apm_dependencies()
        
        # Package with MCP dependencies only
        pkg2 = APMPackage(name="test", version="1.0.0", dependencies={'mcp': ['server']})
        assert not pkg2.has_apm_dependencies()
        
        # Package with APM dependencies
        apm_deps = [DependencyReference.parse("user/repo")]
        pkg3 = APMPackage(name="test", version="1.0.0", dependencies={'apm': apm_deps})
        assert pkg3.has_apm_dependencies()


class TestValidationResult:
    """Test ValidationResult functionality."""
    
    def test_initial_state(self):
        """Test initial validation result state."""
        result = ValidationResult()
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.package is None
        assert not result.has_issues()
    
    def test_add_error(self):
        """Test adding validation errors."""
        result = ValidationResult()
        result.add_error("Test error")
        
        assert result.is_valid is False
        assert "Test error" in result.errors
        assert result.has_issues()
    
    def test_add_warning(self):
        """Test adding validation warnings."""
        result = ValidationResult()
        result.add_warning("Test warning")
        
        assert result.is_valid is True  # Warnings don't make package invalid
        assert "Test warning" in result.warnings
        assert result.has_issues()
    
    def test_summary(self):
        """Test validation summary messages."""
        # Valid with no issues
        result1 = ValidationResult()
        assert "✅ Package is valid" in result1.summary()
        
        # Valid with warnings
        result2 = ValidationResult()
        result2.add_warning("Test warning")
        assert "⚠️ Package is valid with 1 warning(s)" in result2.summary()
        
        # Invalid with errors
        result3 = ValidationResult()
        result3.add_error("Test error")
        assert "❌ Package is invalid with 1 error(s)" in result3.summary()


class TestPackageValidation:
    """Test APM package validation functionality."""
    
    def test_validate_non_existent_directory(self):
        """Test validating non-existent directory."""
        result = validate_apm_package(Path("/non/existent/dir"))
        assert not result.is_valid
        assert any("does not exist" in error for error in result.errors)
    
    def test_validate_file_instead_of_directory(self):
        """Test validating a file instead of directory."""
        with tempfile.NamedTemporaryFile() as f:
            result = validate_apm_package(Path(f.name))
            assert not result.is_valid
            assert any("not a directory" in error for error in result.errors)
    
    def test_validate_missing_apm_yml(self):
        """Test validating directory without apm.yml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = validate_apm_package(Path(tmpdir))
            assert not result.is_valid
            assert any("Missing required file: apm.yml" in error for error in result.errors)
    
    def test_validate_invalid_apm_yml(self):
        """Test validating directory with invalid apm.yml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            apm_yml = Path(tmpdir) / "apm.yml"
            apm_yml.write_text("invalid: [yaml")
            
            result = validate_apm_package(Path(tmpdir))
            assert not result.is_valid
            assert any("Invalid apm.yml" in error for error in result.errors)
    
    def test_validate_missing_apm_directory(self):
        """Test validating package without .apm directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            apm_yml = Path(tmpdir) / "apm.yml"
            apm_yml.write_text("name: test\nversion: 1.0.0")
            
            result = validate_apm_package(Path(tmpdir))
            assert not result.is_valid
            assert any("Missing required directory: .apm/" in error for error in result.errors)
    
    def test_validate_apm_file_instead_of_directory(self):
        """Test validating package with .apm as file instead of directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            apm_yml = Path(tmpdir) / "apm.yml"
            apm_yml.write_text("name: test\nversion: 1.0.0")
            
            apm_file = Path(tmpdir) / ".apm"
            apm_file.write_text("this should be a directory")
            
            result = validate_apm_package(Path(tmpdir))
            assert not result.is_valid
            assert any(".apm must be a directory" in error for error in result.errors)
    
    def test_validate_empty_apm_directory(self):
        """Test validating package with empty .apm directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            apm_yml = Path(tmpdir) / "apm.yml"
            apm_yml.write_text("name: test\nversion: 1.0.0")
            
            apm_dir = Path(tmpdir) / ".apm"
            apm_dir.mkdir()
            
            result = validate_apm_package(Path(tmpdir))
            assert result.is_valid  # Should be valid but with warning
            assert any("No primitive files found" in warning for warning in result.warnings)
    
    def test_validate_valid_package(self):
        """Test validating completely valid package."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create apm.yml
            apm_yml = Path(tmpdir) / "apm.yml"
            apm_yml.write_text("name: test\nversion: 1.0.0\ndescription: Test package")
            
            # Create .apm directory with primitives
            apm_dir = Path(tmpdir) / ".apm"
            apm_dir.mkdir()
            
            instructions_dir = apm_dir / "instructions"
            instructions_dir.mkdir()
            (instructions_dir / "test.instructions.md").write_text("# Test instruction")
            
            chatmodes_dir = apm_dir / "chatmodes"
            chatmodes_dir.mkdir()
            (chatmodes_dir / "test.chatmode.md").write_text("# Test chatmode")
            
            result = validate_apm_package(Path(tmpdir))
            assert result.is_valid
            assert result.package is not None
            assert result.package.name == "test"
            assert result.package.version == "1.0.0"
    
    def test_validate_version_format_warning(self):
        """Test validation warning for non-semver version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            apm_yml = Path(tmpdir) / "apm.yml"
            apm_yml.write_text("name: test\nversion: v1.0")  # Not proper semver
            
            apm_dir = Path(tmpdir) / ".apm"
            apm_dir.mkdir()
            instructions_dir = apm_dir / "instructions"
            instructions_dir.mkdir()
            (instructions_dir / "test.instructions.md").write_text("# Test")
            
            result = validate_apm_package(Path(tmpdir))
            assert result.is_valid
            assert any("doesn't follow semantic versioning" in warning for warning in result.warnings)
    
    def test_validate_numeric_version_types(self):
        """Test that version validation handles YAML numeric types.
        
        This tests the fix from PR #33 for non-string version values.
        YAML may parse unquoted version numbers as numeric types (int/float).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            apm_yml = Path(tmpdir) / "apm.yml"
            # Write YAML with numeric version (no quotes)
            apm_yml.write_text("name: test\nversion: 1.0\ndescription: Test")
            
            apm_dir = Path(tmpdir) / ".apm"
            apm_dir.mkdir()
            instructions_dir = apm_dir / "instructions"
            instructions_dir.mkdir()
            (instructions_dir / "test.instructions.md").write_text("# Test")
            
            # Should not crash when validating
            result = validate_apm_package(Path(tmpdir))
            assert result is not None
            # May have warning about semver format, but should not crash
            if not result.is_valid:
                # Check that any errors are about semver format, not type errors
                for error in result.errors:
                    assert "AttributeError" not in error
                    assert "has no attribute" not in error


class TestGitReferenceUtils:
    """Test Git reference parsing utilities."""
    
    def test_parse_git_reference_branch(self):
        """Test parsing branch references."""
        ref_type, ref = parse_git_reference("main")
        assert ref_type == GitReferenceType.BRANCH
        assert ref == "main"
        
        ref_type, ref = parse_git_reference("feature/new-stuff")
        assert ref_type == GitReferenceType.BRANCH
        assert ref == "feature/new-stuff"
    
    def test_parse_git_reference_tag(self):
        """Test parsing tag references."""
        ref_type, ref = parse_git_reference("v1.0.0")
        assert ref_type == GitReferenceType.TAG
        assert ref == "v1.0.0"
        
        ref_type, ref = parse_git_reference("1.2.3")
        assert ref_type == GitReferenceType.TAG
        assert ref == "1.2.3"
    
    def test_parse_git_reference_commit(self):
        """Test parsing commit SHA references."""
        # Full SHA
        ref_type, ref = parse_git_reference("abcdef1234567890abcdef1234567890abcdef12")
        assert ref_type == GitReferenceType.COMMIT
        assert ref == "abcdef1234567890abcdef1234567890abcdef12"
        
        # Short SHA
        ref_type, ref = parse_git_reference("abcdef1")
        assert ref_type == GitReferenceType.COMMIT
        assert ref == "abcdef1"
    
    def test_parse_git_reference_empty(self):
        """Test parsing empty reference defaults to main branch."""
        ref_type, ref = parse_git_reference("")
        assert ref_type == GitReferenceType.BRANCH
        assert ref == "main"
        
        ref_type, ref = parse_git_reference(None)
        assert ref_type == GitReferenceType.BRANCH
        assert ref == "main"


class TestResolvedReference:
    """Test ResolvedReference functionality."""
    
    def test_string_representation(self):
        """Test string representation of resolved references."""
        # Commit reference
        commit_ref = ResolvedReference(
            original_ref="abc123",
            ref_type=GitReferenceType.COMMIT,
            resolved_commit="abc123def456",
            ref_name="abc123"
        )
        assert str(commit_ref) == "abc123de"  # First 8 chars
        
        # Branch reference
        branch_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123def456",
            ref_name="main"
        )
        assert str(branch_ref) == "main (abc123de)"
        
        # Tag reference
        tag_ref = ResolvedReference(
            original_ref="v1.0.0",
            ref_type=GitReferenceType.TAG,
            resolved_commit="abc123def456",
            ref_name="v1.0.0"
        )
        assert str(tag_ref) == "v1.0.0 (abc123de)"


class TestPackageInfo:
    """Test PackageInfo functionality."""
    
    def test_get_primitives_path(self):
        """Test getting primitives path."""
        package = APMPackage(name="test", version="1.0.0")
        install_path = Path("/tmp/package")
        
        info = PackageInfo(package=package, install_path=install_path)
        assert info.get_primitives_path() == install_path / ".apm"
    
    def test_has_primitives(self):
        """Test checking if package has primitives."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package = APMPackage(name="test", version="1.0.0")
            install_path = Path(tmpdir)
            
            info = PackageInfo(package=package, install_path=install_path)
            
            # No .apm directory
            assert not info.has_primitives()
            
            # Empty .apm directory
            apm_dir = install_path / ".apm"
            apm_dir.mkdir()
            assert not info.has_primitives()
            
            # .apm with empty subdirectories
            (apm_dir / "instructions").mkdir()
            assert not info.has_primitives()
            
            # .apm with primitive files
            (apm_dir / "instructions" / "test.md").write_text("# Test")
            assert info.has_primitives()
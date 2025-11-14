"""Tests for prompt integration functionality."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

from apm_cli.integration import PromptIntegrator
from apm_cli.models.apm_package import PackageInfo, APMPackage, ResolvedReference, GitReferenceType


class TestPromptIntegrator:
    """Test prompt integration logic."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)
        self.integrator = PromptIntegrator()
    
    def teardown_method(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_should_integrate_when_github_exists_and_enabled(self):
        """Test integration is enabled when .github exists and config is True."""
        github_dir = self.project_root / ".github"
        github_dir.mkdir()
        
        with patch('apm_cli.integration.prompt_integrator.get_auto_integrate', return_value=True):
            assert self.integrator.should_integrate(self.project_root) == True
    
    def test_should_not_integrate_when_github_missing(self):
        """Test integration is disabled when .github doesn't exist."""
        with patch('apm_cli.integration.prompt_integrator.get_auto_integrate', return_value=True):
            assert self.integrator.should_integrate(self.project_root) == False
    
    def test_should_not_integrate_when_config_disabled(self):
        """Test integration is disabled when config is False."""
        github_dir = self.project_root / ".github"
        github_dir.mkdir()
        
        with patch('apm_cli.integration.prompt_integrator.get_auto_integrate', return_value=False):
            assert self.integrator.should_integrate(self.project_root) == False
    
    def test_find_prompt_files_in_root(self):
        """Test finding .prompt.md files in package root."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        
        # Create test prompt files
        (package_dir / "test1.prompt.md").write_text("# Test 1")
        (package_dir / "test2.prompt.md").write_text("# Test 2")
        (package_dir / "readme.md").write_text("# Readme")  # Should not be found
        
        prompts = self.integrator.find_prompt_files(package_dir)
        assert len(prompts) == 2
        assert all(p.name.endswith('.prompt.md') for p in prompts)
    
    def test_find_prompt_files_in_apm_prompts(self):
        """Test finding .prompt.md files in .apm/prompts/."""
        package_dir = self.project_root / "package"
        apm_prompts = package_dir / ".apm" / "prompts"
        apm_prompts.mkdir(parents=True)
        
        (apm_prompts / "workflow.prompt.md").write_text("# Workflow")
        
        prompts = self.integrator.find_prompt_files(package_dir)
        assert len(prompts) == 1
        assert prompts[0].name == "workflow.prompt.md"
    
    def test_generate_header_comment(self):
        """Test header comment generation."""
        package = APMPackage(
            name="test-package",
            version="1.0.0",
            package_path=Path("/fake/path")
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123def456",
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=Path("/fake/install"),
            resolved_reference=resolved_ref,
            installed_at="2024-01-01T00:00:00"
        )
        
        original_path = Path("/fake/install/test.prompt.md")
        header = self.integrator.generate_header_comment(package_info, original_path)
        
        assert "test-package" in header
        assert "1.0.0" in header
        assert "abc123def456" in header
        assert "test.prompt.md" in header
    
    def test_get_target_filename(self):
        """Test target filename generation with -apm suffix (intent-first naming)."""
        source = Path("/package/accessibility-audit.prompt.md")
        package_name = "danielmeppiel/design-guidelines"
        
        target = self.integrator.get_target_filename(source, package_name)
        # Intent-first naming: -apm suffix before extension
        assert target == "accessibility-audit-apm.prompt.md"
    
    def test_copy_prompt_with_header(self):
        """Test copying prompt file with header prepended."""
        source = self.project_root / "source.prompt.md"
        target = self.project_root / "target.prompt.md"
        
        source_content = "# Original Content\n\nSome text here."
        source.write_text(source_content)
        
        header = "<!-- Test Header -->\n"
        
        self.integrator.copy_prompt_with_header(source, target, header)
        
        target_content = target.read_text()
        assert target_content.startswith(header)
        assert source_content in target_content
    
    def test_integrate_package_prompts_creates_directory(self):
        """Test that integration creates .github/prompts/ if missing."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        (package_dir / "test.prompt.md").write_text("# Test")
        
        github_dir = self.project_root / ".github"
        github_dir.mkdir()
        
        package = APMPackage(
            name="test-pkg",
            version="1.0.0",
            package_path=package_dir
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123",
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=package_dir,
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat()
        )
        
        with patch('apm_cli.integration.prompt_integrator.get_auto_integrate', return_value=True):
            result = self.integrator.integrate_package_prompts(package_info, self.project_root)
        
        assert result.files_integrated == 1
        assert (self.project_root / ".github" / "prompts").exists()
    
    def test_integrate_package_prompts_skips_unchanged_files(self):
        """Test that integration skips files with same version and commit."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        (package_dir / "test.prompt.md").write_text("# Test")
        
        github_prompts = self.project_root / ".github" / "prompts"
        github_prompts.mkdir(parents=True)
        
        # Pre-create the target file with matching header
        existing_content = """<!-- 
Source: test-pkg (github.com/test/repo)
Version: 1.0.0
Commit: abc123
Original: test.prompt.md
Installed: 2024-01-01T00:00:00
-->

# Existing"""
        (github_prompts / "test-apm.prompt.md").write_text(existing_content)
        
        package = APMPackage(
            name="test-pkg",
            version="1.0.0",
            package_path=package_dir,
            source="github.com/test/repo"
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123",
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=package_dir,
            resolved_reference=resolved_ref,
            installed_at="2024-01-01T00:00:00"
        )
        
        with patch('apm_cli.integration.prompt_integrator.get_auto_integrate', return_value=True):
            result = self.integrator.integrate_package_prompts(package_info, self.project_root)
        
        assert result.files_integrated == 0
        assert result.files_updated == 0
        assert result.files_skipped == 1
    
    def test_update_gitignore_adds_pattern(self):
        """Test that gitignore is updated with integrated prompts pattern."""
        gitignore = self.project_root / ".gitignore"
        gitignore.write_text("# Existing content\napm_modules/\n")
        
        updated = self.integrator.update_gitignore_for_integrated_prompts(self.project_root)
        
        assert updated == True
        content = gitignore.read_text()
        assert ".github/prompts/*-apm.prompt.md" in content
    
    def test_update_gitignore_skips_if_exists(self):
        """Test that gitignore update is skipped if pattern exists."""
        gitignore = self.project_root / ".gitignore"
        gitignore.write_text(".github/prompts/*-apm.prompt.md\n")
        
        updated = self.integrator.update_gitignore_for_integrated_prompts(self.project_root)
        
        assert updated == False
    
    # ========== Header-based Versioning Tests ==========
    
    def test_parse_header_metadata_valid(self):
        """Test parsing metadata from a valid header."""
        header_content = """<!-- 
Source: design-guidelines (danielmeppiel/design-guidelines)
Version: 1.0.0
Commit: abc123def456
Original: design-review.prompt.md
Installed: 2024-11-13T10:30:00Z
-->

# Prompt content here"""
        
        test_file = self.project_root / "test.prompt.md"
        test_file.write_text(header_content)
        
        metadata = self.integrator._parse_header_metadata(test_file)
        
        assert metadata['Source'] == 'design-guidelines (danielmeppiel/design-guidelines)'
        assert metadata['Version'] == '1.0.0'
        assert metadata['Commit'] == 'abc123def456'
        assert metadata['Original'] == 'design-review.prompt.md'
        assert metadata['Installed'] == '2024-11-13T10:30:00Z'
    
    def test_parse_header_metadata_no_header(self):
        """Test parsing file without header returns empty dict."""
        test_file = self.project_root / "test.prompt.md"
        test_file.write_text("# Just content, no header")
        
        metadata = self.integrator._parse_header_metadata(test_file)
        
        assert metadata == {}
    
    def test_parse_header_metadata_malformed(self):
        """Test parsing malformed header returns empty dict."""
        test_file = self.project_root / "test.prompt.md"
        test_file.write_text("<!-- Incomplete header\nNo closing tag")
        
        metadata = self.integrator._parse_header_metadata(test_file)
        
        assert metadata == {}
    
    def test_should_update_prompt_new_version(self):
        """Test that prompt should be updated when version changes."""
        existing_header = {
            'Version': '1.0.0',
            'Commit': 'abc123'
        }
        
        package = APMPackage(
            name="test-pkg",
            version="2.0.0",  # Version changed
            package_path=Path("/fake/path")
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123",
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=Path("/fake/install"),
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat()
        )
        
        should_update = self.integrator._should_update_prompt(existing_header, package_info)
        
        assert should_update == True
    
    def test_should_update_prompt_new_commit(self):
        """Test that prompt should be updated when commit changes."""
        existing_header = {
            'Version': '1.0.0',
            'Commit': 'abc123'
        }
        
        package = APMPackage(
            name="test-pkg",
            version="1.0.0",
            package_path=Path("/fake/path")
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="def456",  # Commit changed
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=Path("/fake/install"),
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat()
        )
        
        should_update = self.integrator._should_update_prompt(existing_header, package_info)
        
        assert should_update == True
    
    def test_should_update_prompt_no_change(self):
        """Test that prompt should not be updated when version and commit match."""
        existing_header = {
            'Version': '1.0.0',
            'Commit': 'abc123'
        }
        
        package = APMPackage(
            name="test-pkg",
            version="1.0.0",  # Same version
            package_path=Path("/fake/path")
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123",  # Same commit
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=Path("/fake/install"),
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat()
        )
        
        should_update = self.integrator._should_update_prompt(existing_header, package_info)
        
        assert should_update == False
    
    def test_should_update_prompt_no_header(self):
        """Test that prompt should be updated when no valid header exists."""
        existing_header = {}
        
        package = APMPackage(
            name="test-pkg",
            version="1.0.0",
            package_path=Path("/fake/path")
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123",
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=Path("/fake/install"),
            resolved_reference=resolved_ref,
            installed_at=datetime.now().isoformat()
        )
        
        should_update = self.integrator._should_update_prompt(existing_header, package_info)
        
        assert should_update == True
    
    def test_integrate_first_time_creates_with_header(self):
        """Test that first-time integration creates files with proper headers."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        (package_dir / "test.prompt.md").write_text("# Test Content")
        
        github_prompts = self.project_root / ".github" / "prompts"
        github_prompts.mkdir(parents=True)
        
        package = APMPackage(
            name="test-pkg",
            version="1.0.0",
            package_path=package_dir,
            source="github.com/test/repo"
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123",
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=package_dir,
            resolved_reference=resolved_ref,
            installed_at="2024-11-13T10:00:00"
        )
        
        result = self.integrator.integrate_package_prompts(package_info, self.project_root)
        
        assert result.files_integrated == 1
        assert result.files_updated == 0
        assert result.files_skipped == 0
        
        # Verify header was added
        target_file = github_prompts / "test-apm.prompt.md"
        content = target_file.read_text()
        assert content.startswith('<!--')
        assert 'Version: 1.0.0' in content
        assert 'Commit: abc123' in content
        assert '# Test Content' in content
    
    def test_integrate_with_new_version_updates_file(self):
        """Test that integration with new version updates existing file."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        (package_dir / "test.prompt.md").write_text("# Updated Content")
        
        github_prompts = self.project_root / ".github" / "prompts"
        github_prompts.mkdir(parents=True)
        
        # Pre-create file with old version
        old_content = """<!-- 
Source: test-pkg (github.com/test/repo)
Version: 1.0.0
Commit: abc123
Original: test.prompt.md
Installed: 2024-11-13T10:00:00
-->

# Old Content"""
        (github_prompts / "test-apm.prompt.md").write_text(old_content)
        
        package = APMPackage(
            name="test-pkg",
            version="2.0.0",  # New version
            package_path=package_dir,
            source="github.com/test/repo"
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="abc123",
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=package_dir,
            resolved_reference=resolved_ref,
            installed_at="2024-11-13T11:00:00"
        )
        
        result = self.integrator.integrate_package_prompts(package_info, self.project_root)
        
        assert result.files_integrated == 0
        assert result.files_updated == 1
        assert result.files_skipped == 0
        
        # Verify content was updated
        target_file = github_prompts / "test-apm.prompt.md"
        content = target_file.read_text()
        assert 'Version: 2.0.0' in content
        assert '# Updated Content' in content
        assert '# Old Content' not in content
    
    def test_integrate_with_new_commit_updates_file(self):
        """Test that integration with new commit hash updates existing file."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        (package_dir / "test.prompt.md").write_text("# Updated Content")
        
        github_prompts = self.project_root / ".github" / "prompts"
        github_prompts.mkdir(parents=True)
        
        # Pre-create file with old commit
        old_content = """<!-- 
Source: test-pkg (github.com/test/repo)
Version: 1.0.0
Commit: abc123
Original: test.prompt.md
Installed: 2024-11-13T10:00:00
-->

# Old Content"""
        (github_prompts / "test-apm.prompt.md").write_text(old_content)
        
        package = APMPackage(
            name="test-pkg",
            version="1.0.0",
            package_path=package_dir,
            source="github.com/test/repo"
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="def456",  # New commit
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=package_dir,
            resolved_reference=resolved_ref,
            installed_at="2024-11-13T11:00:00"
        )
        
        result = self.integrator.integrate_package_prompts(package_info, self.project_root)
        
        assert result.files_integrated == 0
        assert result.files_updated == 1
        assert result.files_skipped == 0
        
        # Verify commit was updated
        target_file = github_prompts / "test-apm.prompt.md"
        content = target_file.read_text()
        assert 'Commit: def456' in content
        assert '# Updated Content' in content
    
    def test_integrate_mixed_operations(self):
        """Test integration with mix of new, updated, and skipped files."""
        package_dir = self.project_root / "package"
        package_dir.mkdir()
        
        # Create 3 prompt files in package
        (package_dir / "new.prompt.md").write_text("# New File")
        (package_dir / "update.prompt.md").write_text("# Updated File")
        (package_dir / "skip.prompt.md").write_text("# Unchanged File")
        
        github_prompts = self.project_root / ".github" / "prompts"
        github_prompts.mkdir(parents=True)
        
        # Pre-create file to be updated (old version)
        update_old = """<!-- 
Source: test-pkg (github.com/test/repo)
Version: 1.0.0
Commit: abc123
Original: update.prompt.md
Installed: 2024-11-13T10:00:00
-->

# Old Content"""
        (github_prompts / "update-apm.prompt.md").write_text(update_old)
        
        # Pre-create file to be skipped (same version)
        skip_same = """<!-- 
Source: test-pkg (github.com/test/repo)
Version: 2.0.0
Commit: def456
Original: skip.prompt.md
Installed: 2024-11-13T10:00:00
-->

# Unchanged File"""
        (github_prompts / "skip-apm.prompt.md").write_text(skip_same)
        
        package = APMPackage(
            name="test-pkg",
            version="2.0.0",
            package_path=package_dir,
            source="github.com/test/repo"
        )
        resolved_ref = ResolvedReference(
            original_ref="main",
            ref_type=GitReferenceType.BRANCH,
            resolved_commit="def456",
            ref_name="main"
        )
        package_info = PackageInfo(
            package=package,
            install_path=package_dir,
            resolved_reference=resolved_ref,
            installed_at="2024-11-13T11:00:00"
        )
        
        result = self.integrator.integrate_package_prompts(package_info, self.project_root)
        
        assert result.files_integrated == 1  # new.prompt.md
        assert result.files_updated == 1      # update.prompt.md
        assert result.files_skipped == 1      # skip.prompt.md
        
        # Verify new file exists
        assert (github_prompts / "new-apm.prompt.md").exists()
        
        # Verify updated file has new version
        update_content = (github_prompts / "update-apm.prompt.md").read_text()
        assert 'Version: 2.0.0' in update_content
        
        # Verify skipped file is unchanged
        skip_content = (github_prompts / "skip-apm.prompt.md").read_text()
        assert skip_content == skip_same


class TestPromptSuffixPattern:
    """Test -apm suffix pattern edge cases."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.integrator = PromptIntegrator()
    
    def test_suffix_with_simple_filename(self):
        """Test suffix pattern with simple filename."""
        source = Path("test.prompt.md")
        result = self.integrator.get_target_filename(source, "pkg")
        assert result == "test-apm.prompt.md"
    
    def test_suffix_with_hyphenated_filename(self):
        """Test suffix pattern with hyphenated filename."""
        source = Path("design-review.prompt.md")
        result = self.integrator.get_target_filename(source, "pkg")
        assert result == "design-review-apm.prompt.md"
    
    def test_suffix_with_multi_part_filename(self):
        """Test suffix pattern with multi-part filename."""
        source = Path("accessibility-audit-wcag.prompt.md")
        result = self.integrator.get_target_filename(source, "pkg")
        assert result == "accessibility-audit-wcag-apm.prompt.md"
    
    def test_suffix_preserves_original_name(self):
        """Test that original filename structure is preserved."""
        source = Path("my_custom-workflow.prompt.md")
        result = self.integrator.get_target_filename(source, "pkg")
        assert result == "my_custom-workflow-apm.prompt.md"
    
    def test_gitignore_pattern_matches_suffix_files(self):
        """Test that gitignore pattern matches -apm suffix files."""
        import fnmatch
        pattern = "*-apm.prompt.md"
        
        # Should match
        assert fnmatch.fnmatch("design-review-apm.prompt.md", pattern)
        assert fnmatch.fnmatch("test-apm.prompt.md", pattern)
        assert fnmatch.fnmatch("a-b-c-apm.prompt.md", pattern)
        
        # Should NOT match
        assert not fnmatch.fnmatch("design-review.prompt.md", pattern)
        assert not fnmatch.fnmatch("apm.prompt.md", pattern)
        assert not fnmatch.fnmatch("@design-review.prompt.md", pattern)

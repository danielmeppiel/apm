"""
Integration tests for orphan detection with virtual packages.

Tests that virtual packages (individual files and collections) are correctly
recognized and not flagged as orphaned when they are declared in apm.yml.
"""

import tempfile
from pathlib import Path
import pytest
import yaml
from apm_cli.models.apm_package import APMPackage


@pytest.mark.integration
def test_virtual_collection_not_flagged_as_orphan(tmp_path):
    """Test that installed virtual collection is not flagged as orphaned."""
    # Create test project structure
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    
    # Create apm.yml with collection dependency
    apm_yml_content = {
        "name": "test-project",
        "version": "1.0.0",
        "dependencies": {
            "apm": [
                "github/awesome-copilot/collections/awesome-copilot"
            ]
        }
    }
    
    with open(project_dir / "apm.yml", "w") as f:
        yaml.dump(apm_yml_content, f)
    
    # Simulate installed virtual collection package
    # Virtual collections are installed as: apm_modules/{org}/{repo-name}-{collection-name}/
    collection_dir = project_dir / "apm_modules" / "github" / "awesome-copilot-awesome-copilot"
    collection_dir.mkdir(parents=True)
    
    # Create generated apm.yml in the collection
    collection_apm = {
        "name": "awesome-copilot-awesome-copilot",
        "version": "1.0.0",
        "description": "Virtual collection package"
    }
    with open(collection_dir / "apm.yml", "w") as f:
        yaml.dump(collection_apm, f)
    
    # Add some files to make it realistic
    (collection_dir / ".apm").mkdir()
    (collection_dir / ".apm" / "prompts").mkdir()
    (collection_dir / ".apm" / "prompts" / "test.prompt.md").write_text("# Test prompt")
    
    # Parse apm.yml and check for orphans
    apm_package = APMPackage.from_apm_yml(project_dir / "apm.yml")
    declared_deps = apm_package.get_apm_dependencies()
    
    # Build expected installed packages set (same logic as _check_orphaned_packages)
    expected_installed = set()
    for dep in declared_deps:
        repo_parts = dep.repo_url.split('/')
        if len(repo_parts) >= 2:
            org_name = repo_parts[0]
            if dep.is_virtual:
                package_name = dep.get_virtual_package_name()
                expected_installed.add(f"{org_name}/{package_name}")
            else:
                repo_name = repo_parts[1]
                expected_installed.add(f"{org_name}/{repo_name}")
    
    # Check installed packages
    apm_modules_dir = project_dir / "apm_modules"
    orphaned_packages = []
    for org_dir in apm_modules_dir.iterdir():
        if org_dir.is_dir() and not org_dir.name.startswith("."):
            for repo_dir in org_dir.iterdir():
                if repo_dir.is_dir() and not repo_dir.name.startswith("."):
                    org_repo_name = f"{org_dir.name}/{repo_dir.name}"
                    if org_repo_name not in expected_installed:
                        orphaned_packages.append(org_repo_name)
    
    # Assert no orphans found
    assert len(orphaned_packages) == 0, \
        f"Virtual collection should not be flagged as orphaned. Found: {orphaned_packages}"


@pytest.mark.integration
def test_virtual_file_not_flagged_as_orphan(tmp_path):
    """Test that installed virtual file package is not flagged as orphaned."""
    # Create test project structure
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    
    # Create apm.yml with virtual file dependency
    apm_yml_content = {
        "name": "test-project",
        "version": "1.0.0",
        "dependencies": {
            "apm": [
                "github/awesome-copilot/prompts/code-review.prompt.md"
            ]
        }
    }
    
    with open(project_dir / "apm.yml", "w") as f:
        yaml.dump(apm_yml_content, f)
    
    # Simulate installed virtual file package
    # Virtual files are installed as: apm_modules/{org}/{repo-name}-{file-name}/
    file_pkg_dir = project_dir / "apm_modules" / "github" / "awesome-copilot-code-review"
    file_pkg_dir.mkdir(parents=True)
    
    # Create generated apm.yml in the package
    file_pkg_apm = {
        "name": "awesome-copilot-code-review",
        "version": "1.0.0",
        "description": "Virtual file package"
    }
    with open(file_pkg_dir / "apm.yml", "w") as f:
        yaml.dump(file_pkg_apm, f)
    
    # Add the prompt file
    (file_pkg_dir / ".apm").mkdir()
    (file_pkg_dir / ".apm" / "prompts").mkdir()
    (file_pkg_dir / ".apm" / "prompts" / "code-review.prompt.md").write_text("# Code review prompt")
    
    # Parse apm.yml and check for orphans
    apm_package = APMPackage.from_apm_yml(project_dir / "apm.yml")
    declared_deps = apm_package.get_apm_dependencies()
    
    # Build expected installed packages set
    expected_installed = set()
    for dep in declared_deps:
        repo_parts = dep.repo_url.split('/')
        if len(repo_parts) >= 2:
            org_name = repo_parts[0]
            if dep.is_virtual:
                package_name = dep.get_virtual_package_name()
                expected_installed.add(f"{org_name}/{package_name}")
            else:
                repo_name = repo_parts[1]
                expected_installed.add(f"{org_name}/{repo_name}")
    
    # Check installed packages
    apm_modules_dir = project_dir / "apm_modules"
    orphaned_packages = []
    for org_dir in apm_modules_dir.iterdir():
        if org_dir.is_dir() and not org_dir.name.startswith("."):
            for repo_dir in org_dir.iterdir():
                if repo_dir.is_dir() and not repo_dir.name.startswith("."):
                    org_repo_name = f"{org_dir.name}/{repo_dir.name}"
                    if org_repo_name not in expected_installed:
                        orphaned_packages.append(org_repo_name)
    
    # Assert no orphans found
    assert len(orphaned_packages) == 0, \
        f"Virtual file should not be flagged as orphaned. Found: {orphaned_packages}"


@pytest.mark.integration
def test_mixed_dependencies_orphan_detection(tmp_path):
    """Test orphan detection with mix of regular and virtual packages."""
    # Create test project structure
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    
    # Create apm.yml with mixed dependencies
    apm_yml_content = {
        "name": "test-project",
        "version": "1.0.0",
        "dependencies": {
            "apm": [
                "danielmeppiel/design-guidelines",  # Regular package
                "github/awesome-copilot/collections/awesome-copilot",  # Virtual collection
                "danielmeppiel/compliance-rules/prompts/gdpr.prompt.md"  # Virtual file
            ]
        }
    }
    
    with open(project_dir / "apm.yml", "w") as f:
        yaml.dump(apm_yml_content, f)
    
    # Simulate installed packages
    apm_modules_dir = project_dir / "apm_modules"
    
    # Regular package
    regular_dir = apm_modules_dir / "danielmeppiel" / "design-guidelines"
    regular_dir.mkdir(parents=True)
    (regular_dir / "apm.yml").write_text("name: design-guidelines\nversion: 1.0.0")
    
    # Virtual collection
    collection_dir = apm_modules_dir / "github" / "awesome-copilot-awesome-copilot"
    collection_dir.mkdir(parents=True)
    (collection_dir / "apm.yml").write_text("name: awesome-copilot-awesome-copilot\nversion: 1.0.0")
    
    # Virtual file
    file_dir = apm_modules_dir / "danielmeppiel" / "compliance-rules-gdpr"
    file_dir.mkdir(parents=True)
    (file_dir / "apm.yml").write_text("name: compliance-rules-gdpr\nversion: 1.0.0")
    
    # Parse apm.yml and check for orphans
    apm_package = APMPackage.from_apm_yml(project_dir / "apm.yml")
    declared_deps = apm_package.get_apm_dependencies()
    
    # Build expected installed packages set
    expected_installed = set()
    for dep in declared_deps:
        repo_parts = dep.repo_url.split('/')
        if len(repo_parts) >= 2:
            org_name = repo_parts[0]
            if dep.is_virtual:
                package_name = dep.get_virtual_package_name()
                expected_installed.add(f"{org_name}/{package_name}")
            else:
                repo_name = repo_parts[1]
                expected_installed.add(f"{org_name}/{repo_name}")
    
    # Check installed packages
    orphaned_packages = []
    for org_dir in apm_modules_dir.iterdir():
        if org_dir.is_dir() and not org_dir.name.startswith("."):
            for repo_dir in org_dir.iterdir():
                if repo_dir.is_dir() and not repo_dir.name.startswith("."):
                    org_repo_name = f"{org_dir.name}/{repo_dir.name}"
                    if org_repo_name not in expected_installed:
                        orphaned_packages.append(org_repo_name)
    
    # Assert no orphans found
    assert len(orphaned_packages) == 0, \
        f"No packages should be flagged as orphaned. Found: {orphaned_packages}"
    
    # Verify expected counts
    assert len(expected_installed) == 3, "Should have 3 expected packages"
    assert "danielmeppiel/design-guidelines" in expected_installed
    assert "github/awesome-copilot-awesome-copilot" in expected_installed
    assert "danielmeppiel/compliance-rules-gdpr" in expected_installed

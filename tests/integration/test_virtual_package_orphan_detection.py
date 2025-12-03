"""
Integration tests for orphan detection with virtual packages.

Tests that virtual packages (individual files and collections) are correctly
recognized and not flagged as orphaned when they are declared in apm.yml.

Also tests Azure DevOps (ADO) packages which use a 3-level directory structure
(org/project/repo) instead of GitHub's 2-level structure (owner/repo).
"""

import tempfile
from pathlib import Path
import pytest
import yaml
from apm_cli.models.apm_package import APMPackage
from apm_cli.primitives.discovery import get_dependency_declaration_order


def _build_expected_installed_packages(declared_deps):
    """Build set of expected installed package paths from declared dependencies.
    
    This mirrors the logic in _check_orphaned_packages() for testing purposes.
    
    Args:
        declared_deps: List of DependencyReference objects from apm.yml
        
    Returns:
        set: Expected package paths in the format used by apm_modules/
    """
    expected_installed = set()
    for dep in declared_deps:
        repo_parts = dep.repo_url.split('/')
        if dep.is_virtual:
            package_name = dep.get_virtual_package_name()
            if dep.is_azure_devops() and len(repo_parts) >= 3:
                # ADO structure: org/project/virtual-pkg-name
                expected_installed.add(f"{repo_parts[0]}/{repo_parts[1]}/{package_name}")
            elif len(repo_parts) >= 2:
                # GitHub structure: owner/virtual-pkg-name
                expected_installed.add(f"{repo_parts[0]}/{package_name}")
        else:
            if dep.is_azure_devops() and len(repo_parts) >= 3:
                # ADO structure: org/project/repo
                expected_installed.add(f"{repo_parts[0]}/{repo_parts[1]}/{repo_parts[2]}")
            elif len(repo_parts) >= 2:
                # GitHub structure: owner/repo
                expected_installed.add(f"{repo_parts[0]}/{repo_parts[1]}")
    return expected_installed


def _find_installed_packages(apm_modules_dir):
    """Find all installed packages in apm_modules/, supporting both 2-level and 3-level structures.
    
    This mirrors the logic in _check_orphaned_packages() for testing purposes.
    
    Args:
        apm_modules_dir: Path to apm_modules/ directory
        
    Returns:
        list: Package paths found in apm_modules/
    """
    installed_packages = []
    if not apm_modules_dir.exists():
        return installed_packages
        
    for level1_dir in apm_modules_dir.iterdir():
        if level1_dir.is_dir() and not level1_dir.name.startswith("."):
            for level2_dir in level1_dir.iterdir():
                if level2_dir.is_dir() and not level2_dir.name.startswith("."):
                    # Check if level2 has apm.yml or .apm (GitHub 2-level structure)
                    if (level2_dir / "apm.yml").exists() or (level2_dir / ".apm").exists():
                        path_key = f"{level1_dir.name}/{level2_dir.name}"
                        installed_packages.append(path_key)
                    else:
                        # Check for ADO 3-level structure
                        for level3_dir in level2_dir.iterdir():
                            if level3_dir.is_dir() and not level3_dir.name.startswith("."):
                                if (level3_dir / "apm.yml").exists() or (level3_dir / ".apm").exists():
                                    path_key = f"{level1_dir.name}/{level2_dir.name}/{level3_dir.name}"
                                    installed_packages.append(path_key)
    return installed_packages


def _find_orphaned_packages(project_dir):
    """Find orphaned packages in a project by comparing installed vs declared.
    
    Args:
        project_dir: Path to project root containing apm.yml
        
    Returns:
        tuple: (orphaned_packages list, expected_installed set)
    """
    apm_package = APMPackage.from_apm_yml(project_dir / "apm.yml")
    declared_deps = apm_package.get_apm_dependencies()
    expected_installed = _build_expected_installed_packages(declared_deps)
    installed_packages = _find_installed_packages(project_dir / "apm_modules")
    orphaned_packages = [pkg for pkg in installed_packages if pkg not in expected_installed]
    return orphaned_packages, expected_installed


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
    
    # Check for orphans using shared helper
    orphaned_packages, _ = _find_orphaned_packages(project_dir)
    
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
    
    # Check for orphans using shared helper
    orphaned_packages, _ = _find_orphaned_packages(project_dir)
    
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
    
    # Check for orphans using shared helper
    orphaned_packages, expected_installed = _find_orphaned_packages(project_dir)
    
    # Assert no orphans found
    assert len(orphaned_packages) == 0, \
        f"No packages should be flagged as orphaned. Found: {orphaned_packages}"
    
    # Verify expected counts
    assert len(expected_installed) == 3, "Should have 3 expected packages"
    assert "danielmeppiel/design-guidelines" in expected_installed
    assert "github/awesome-copilot-awesome-copilot" in expected_installed
    assert "danielmeppiel/compliance-rules-gdpr" in expected_installed


@pytest.mark.integration
def test_azure_devops_virtual_collection_not_flagged_as_orphan(tmp_path):
    """Test that Azure DevOps virtual collection is not flagged as orphaned.
    
    ADO packages use 3-level directory structure (org/project/repo) unlike
    GitHub's 2-level structure (owner/repo).
    """
    # Create test project structure
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    
    # Create apm.yml with ADO collection dependency
    # Format: dev.azure.com/org/project/repo/collections/collection-name
    apm_yml_content = {
        "name": "test-project",
        "version": "1.0.0",
        "dependencies": {
            "apm": [
                "dev.azure.com/company/my-azurecollection/copilot-instructions/collections/csharp-ddd-cleanarchitecture"
            ]
        }
    }
    
    with open(project_dir / "apm.yml", "w") as f:
        yaml.dump(apm_yml_content, f)
    
    # Simulate installed ADO virtual collection package
    # ADO 3-level structure: apm_modules/org/project/virtual-pkg-name
    collection_dir = project_dir / "apm_modules" / "company" / "my-azurecollection" / "copilot-instructions-csharp-ddd-cleanarchitecture"
    collection_dir.mkdir(parents=True)
    
    # Create generated apm.yml in the collection
    collection_apm = {
        "name": "copilot-instructions-csharp-ddd-cleanarchitecture",
        "version": "1.0.0",
        "description": "Virtual collection package from Azure DevOps"
    }
    with open(collection_dir / "apm.yml", "w") as f:
        yaml.dump(collection_apm, f)
    
    # Add some files to make it realistic
    (collection_dir / ".apm").mkdir()
    (collection_dir / ".apm" / "instructions").mkdir()
    (collection_dir / ".apm" / "instructions" / "test.instructions.md").write_text("# Test instruction")
    
    # Check for orphans using shared helper
    orphaned_packages, expected_installed = _find_orphaned_packages(project_dir)
    
    # Assert no orphans found
    assert len(orphaned_packages) == 0, \
        f"ADO virtual collection should not be flagged as orphaned. Found: {orphaned_packages}. Expected: {expected_installed}"
    
    # Verify the expected path is correct for ADO 3-level structure
    assert "company/my-azurecollection/copilot-instructions-csharp-ddd-cleanarchitecture" in expected_installed


@pytest.mark.integration
def test_azure_devops_regular_package_not_flagged_as_orphan(tmp_path):
    """Test that Azure DevOps regular package is not flagged as orphaned.
    
    ADO regular packages use 3-level directory structure (org/project/repo).
    """
    # Create test project structure
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    
    # Create apm.yml with ADO regular dependency
    apm_yml_content = {
        "name": "test-project",
        "version": "1.0.0",
        "dependencies": {
            "apm": [
                "dev.azure.com/company/my-project/my-apm-package"
            ]
        }
    }
    
    with open(project_dir / "apm.yml", "w") as f:
        yaml.dump(apm_yml_content, f)
    
    # Simulate installed ADO regular package
    # ADO 3-level structure: apm_modules/org/project/repo
    pkg_dir = project_dir / "apm_modules" / "company" / "my-project" / "my-apm-package"
    pkg_dir.mkdir(parents=True)
    
    # Create apm.yml in the package
    pkg_apm = {
        "name": "my-apm-package",
        "version": "1.0.0",
        "description": "Regular APM package from Azure DevOps"
    }
    with open(pkg_dir / "apm.yml", "w") as f:
        yaml.dump(pkg_apm, f)
    
    # Check for orphans using shared helper
    orphaned_packages, expected_installed = _find_orphaned_packages(project_dir)
    
    # Assert no orphans found
    assert len(orphaned_packages) == 0, \
        f"ADO regular package should not be flagged as orphaned. Found: {orphaned_packages}. Expected: {expected_installed}"
    
    # Verify the expected path is correct for ADO 3-level structure
    assert "company/my-project/my-apm-package" in expected_installed


@pytest.mark.integration
def test_get_dependency_declaration_order_ado_virtual(tmp_path):
    """Test that get_dependency_declaration_order returns correct paths for ADO virtual packages."""
    # Create test project structure
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    
    # Create apm.yml with ADO virtual collection
    apm_yml_content = {
        "name": "test-project",
        "version": "1.0.0",
        "dependencies": {
            "apm": [
                "dev.azure.com/company/my-azurecollection/copilot-instructions/collections/csharp-ddd-cleanarchitecture"
            ]
        }
    }
    
    with open(project_dir / "apm.yml", "w") as f:
        yaml.dump(apm_yml_content, f)
    
    # Get dependency order
    dep_order = get_dependency_declaration_order(str(project_dir))
    
    # Should return the correct installed path for ADO virtual collection
    assert len(dep_order) == 1
    assert dep_order[0] == "company/my-azurecollection/copilot-instructions-csharp-ddd-cleanarchitecture"


@pytest.mark.integration
def test_get_dependency_declaration_order_mixed_github_and_ado(tmp_path):
    """Test that get_dependency_declaration_order returns correct paths for mixed GitHub and ADO packages."""
    # Create test project structure
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    
    # Create apm.yml with mixed dependencies
    apm_yml_content = {
        "name": "test-project",
        "version": "1.0.0",
        "dependencies": {
            "apm": [
                "danielmeppiel/design-guidelines",  # GitHub regular
                "github/awesome-copilot/prompts/code-review.prompt.md",  # GitHub virtual file
                "dev.azure.com/company/project/repo",  # ADO regular
                "dev.azure.com/company/my-azurecollection/copilot-instructions/collections/csharp-ddd"  # ADO virtual collection
            ]
        }
    }
    
    with open(project_dir / "apm.yml", "w") as f:
        yaml.dump(apm_yml_content, f)
    
    # Get dependency order
    dep_order = get_dependency_declaration_order(str(project_dir))
    
    # Verify all dependency paths are returned correctly
    assert len(dep_order) == 4
    assert dep_order[0] == "danielmeppiel/design-guidelines"  # GitHub regular: owner/repo
    assert dep_order[1] == "github/awesome-copilot-code-review"  # GitHub virtual: owner/virtual-pkg-name
    assert dep_order[2] == "company/project/repo"  # ADO regular: org/project/repo
    assert dep_order[3] == "company/my-azurecollection/copilot-instructions-csharp-ddd"  # ADO virtual: org/project/virtual-pkg-name

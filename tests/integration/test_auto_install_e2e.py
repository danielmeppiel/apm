"""
End-to-end tests for auto-install feature (README Hero Scenario).

Tests the exact zero-config flow from the README:
    apm run github/awesome-copilot/prompts/architecture-blueprint-generator

This validates that users can run virtual packages without manual installation.
"""

import os
import pytest
import subprocess
import tempfile
import shutil
from pathlib import Path


class TestAutoInstallE2E:
    """E2E tests for auto-install functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        # Create isolated test directory
        self.test_dir = tempfile.mkdtemp(prefix="apm-auto-install-e2e-")
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)
        
        # Create minimal apm.yml for testing
        with open("apm.yml", "w") as f:
            f.write("""name: auto-install-test
version: 1.0.0
description: Auto-install E2E test project
author: test
""")
    
    def teardown_method(self):
        """Clean up test environment."""
        os.chdir(self.original_dir)
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    @pytest.mark.skipif(
        os.getenv("APM_E2E_TESTS") != "1",
        reason="E2E tests only run when APM_E2E_TESTS=1"
    )
    def test_auto_install_virtual_prompt_first_run(self):
        """Test auto-install on first run with virtual package reference.
        
        This is the exact README hero scenario:
            apm run github/awesome-copilot/prompts/architecture-blueprint-generator
        
        Expected behavior:
        1. Package doesn't exist locally
        2. APM detects it's a virtual package reference
        3. Auto-installs to apm_modules/
        4. Discovers and attempts to run the prompt
        """
        # Verify package doesn't exist initially
        apm_modules = Path("apm_modules")
        assert not apm_modules.exists(), "apm_modules should not exist initially"
        
        # Run the exact README command - let it complete naturally (no timeout)
        # This is a full E2E test including model execution
        result = subprocess.run(
            [
                "apm",
                "run",
                "github/awesome-copilot/prompts/architecture-blueprint-generator"
            ],
            capture_output=True,
            text=True
        )
        
        # Check output for auto-install messages
        output = result.stdout + result.stderr
        assert "Auto-installing virtual package" in output or "📦" in output, \
            "Should show auto-install message"
        assert "Downloading from" in output or "📥" in output, \
            "Should show download message"
        
        # Verify package was installed
        package_path = apm_modules / "github" / "awesome-copilot-architecture-blueprint-generator"
        assert package_path.exists(), f"Package should be installed at {package_path}"
        
        # Verify apm.yml was created in the virtual package
        apm_yml = package_path / "apm.yml"
        assert apm_yml.exists(), "Virtual package should have apm.yml"
        
        # Verify the prompt file exists
        prompt_file = package_path / ".apm" / "prompts" / "architecture-blueprint-generator.prompt.md"
        assert prompt_file.exists(), f"Prompt file should exist at {prompt_file}"
        
        print(f"✅ Auto-install successful: {package_path}")
    
    @pytest.mark.skipif(
        os.getenv("APM_E2E_TESTS") != "1",
        reason="E2E tests only run when APM_E2E_TESTS=1"
    )
    def test_auto_install_uses_cache_on_second_run(self):
        """Test that second run uses cached package (no re-download).
        
        Expected behavior:
        1. First run installs package
        2. Second run discovers already-installed package
        3. No download happens on second run
        """
        # First run - install (no timeout, let model execute)
        subprocess.run(
            [
                "apm",
                "run",
                "github/awesome-copilot/prompts/architecture-blueprint-generator"
            ],
            capture_output=True,
            text=True
        )
        
        # Verify package exists
        package_path = Path("apm_modules/github/awesome-copilot-architecture-blueprint-generator")
        assert package_path.exists(), "Package should exist after first run"
        
        # Second run - should use cache (no timeout)
        result = subprocess.run(
            [
                "apm",
                "run",
                "github/awesome-copilot/prompts/architecture-blueprint-generator"
            ],
            capture_output=True,
            text=True
        )
        
        # Check output - should NOT show install/download messages
        output = result.stdout + result.stderr
        assert "Auto-installing" not in output, "Should not auto-install on second run"
        assert "Auto-discovered" in output or "ℹ" in output, \
            "Should show auto-discovery message (using cached package)"
        
        print("✅ Second run used cached package (no re-download)")
    
    @pytest.mark.skipif(
        os.getenv("APM_E2E_TESTS") != "1",
        reason="E2E tests only run when APM_E2E_TESTS=1"
    )
    def test_simple_name_works_after_install(self):
        """Test that simple name works after package is installed.
        
        Expected behavior:
        1. Install package with full path
        2. Run with simple name (just the prompt name)
        3. Should discover and run from installed package
        """
        # First install with full path (no timeout)
        subprocess.run(
            [
                "apm",
                "run",
                "github/awesome-copilot/prompts/architecture-blueprint-generator"
            ],
            capture_output=True,
            text=True
        )
        
        # Run with simple name (no timeout)
        result = subprocess.run(
            [
                "apm",
                "run",
                "architecture-blueprint-generator"
            ],
            capture_output=True,
            text=True
        )
        
        # Check output - should discover the installed prompt
        output = result.stdout + result.stderr
        assert "Auto-discovered" in output or "ℹ" in output, \
            "Should auto-discover prompt from installed package"
        
        print("✅ Simple name works after installation")
    
    @pytest.mark.skipif(
        os.getenv("APM_E2E_TESTS") != "1",
        reason="E2E tests only run when APM_E2E_TESTS=1"
    )
    def test_auto_install_with_qualified_path(self):
        """Test auto-install works with qualified path format.
        
        Tests both formats:
        - Full: github/awesome-copilot/prompts/file.prompt.md
        - Qualified: github/awesome-copilot/architecture-blueprint-generator
        """
        # Test with qualified path (without .prompt.md extension) - no timeout
        result = subprocess.run(
            [
                "apm",
                "run",
                "github/awesome-copilot/prompts/architecture-blueprint-generator"
            ],
            capture_output=True,
            text=True
        )
        
        # Check that package was installed
        package_path = Path("apm_modules/github/awesome-copilot-architecture-blueprint-generator")
        assert package_path.exists(), "Package should be installed"
        
        # Check that prompt file exists
        prompt_file = package_path / ".apm" / "prompts" / "architecture-blueprint-generator.prompt.md"
        assert prompt_file.exists(), "Prompt file should exist"
        
        print("✅ Auto-install works with qualified path")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

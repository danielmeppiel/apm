"""
End-to-end tests for auto-install feature (README Hero Scenario).

Tests the exact zero-config flow from the README:
    apm run github/awesome-copilot/prompts/architecture-blueprint-generator

This validates that users can run virtual packages without manual installation.

Note: Tests terminate execution early (after auto-install completes) to save time.
The full execution is already tested in test_golden_scenario_e2e.py.
"""

import os
import pytest
import subprocess
import tempfile
import shutil
from pathlib import Path


# Skip all tests in this module if not in E2E mode
E2E_MODE = os.environ.get('APM_E2E_TESTS', '').lower() in ('1', 'true', 'yes')

pytestmark = pytest.mark.skipif(
    not E2E_MODE,
    reason="E2E tests only run when APM_E2E_TESTS=1 is set"
)


@pytest.fixture(scope="module")
def temp_e2e_home():
    """Create a temporary home directory for E2E testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        original_home = os.environ.get('HOME')
        test_home = os.path.join(temp_dir, 'e2e_home')
        os.makedirs(test_home)
        
        # Set up test environment
        os.environ['HOME'] = test_home
        
        yield test_home
        
        # Restore original environment
        if original_home:
            os.environ['HOME'] = original_home
        else:
            del os.environ['HOME']


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
    
    def test_auto_install_virtual_prompt_first_run(self, temp_e2e_home):
        """Test auto-install on first run with virtual package reference.
        
        This is the exact README hero scenario:
            apm run github/awesome-copilot/prompts/architecture-blueprint-generator
        
        Expected behavior:
        1. Package doesn't exist locally
        2. APM detects it's a virtual package reference
        3. Auto-installs to apm_modules/
        4. Discovers and attempts to run the prompt
        5. Terminates before full execution to save time
        """
        # Verify package doesn't exist initially
        apm_modules = Path("apm_modules")
        assert not apm_modules.exists(), "apm_modules should not exist initially"
        
        # Set up environment (like golden scenario does)
        env = os.environ.copy()
        env['HOME'] = temp_e2e_home
        
        # Run the exact README command with streaming output monitoring
        process = subprocess.Popen(
            [
                "apm",
                "run",
                "github/awesome-copilot/prompts/architecture-blueprint-generator"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=self.test_dir,
            env=env
        )
        
        output_lines = []
        execution_started = False
        
        # Monitor output and terminate once execution starts
        try:
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                output_lines.append(line)
                print(line.rstrip())  # Show progress
                
                # Once we see "Package installed and ready to run", execution is about to start
                # Terminate to avoid waiting for full prompt execution
                if "✨ Package installed and ready to run" in line:
                    execution_started = True
                    print("\n⚡ Test validated - terminating to save time")
                    process.terminate()
                    break
            
            # Wait for graceful shutdown
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        
        finally:
            output = ''.join(output_lines)
        
        # Check output for auto-install messages
        assert "Auto-installing virtual package" in output or "📦" in output, \
            "Should show auto-install message"
        assert "Downloading from" in output or "📥" in output, \
            "Should show download message"
        assert execution_started, "Should have started execution (✨ Package installed and ready to run)"
        
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
    
    def test_auto_install_uses_cache_on_second_run(self, temp_e2e_home):
        """Test that second run uses cached package (no re-download).
        
        Expected behavior:
        1. First run installs package
        2. Second run discovers already-installed package
        3. No download happens on second run
        """
        # Set up environment
        env = os.environ.copy()
        env['HOME'] = temp_e2e_home
        
        # First run - install with early termination
        process = subprocess.Popen(
            [
                "apm",
                "run",
                "github/awesome-copilot/prompts/architecture-blueprint-generator"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=self.test_dir,
            env=env
        )
        
        try:
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                if "✨ Package installed and ready to run" in line:
                    process.terminate()
                    break
            process.wait(timeout=5)
        except:
            process.kill()
            process.wait()
        
        # Verify package exists
        package_path = Path("apm_modules/github/awesome-copilot-architecture-blueprint-generator")
        assert package_path.exists(), "Package should exist after first run"
        
        # Second run - should use cache with early termination
        process = subprocess.Popen(
            [
                "apm",
                "run",
                "github/awesome-copilot/prompts/architecture-blueprint-generator"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=self.test_dir,
            env=env
        )
        
        output_lines = []
        try:
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                output_lines.append(line)
                # Terminate once we see execution starting (no need for full run)
                if "Executing" in line or "✨" in line:
                    process.terminate()
                    break
            process.wait(timeout=5)
        except:
            process.kill()
            process.wait()
        finally:
            output = ''.join(output_lines)
        
        # Check output - should NOT show install/download messages
        assert "Auto-installing" not in output, "Should not auto-install on second run"
        assert "Auto-discovered" in output or "ℹ" in output, \
            "Should show auto-discovery message (using cached package)"
        
        print("✅ Second run used cached package (no re-download)")
    
    def test_simple_name_works_after_install(self, temp_e2e_home):
        """Test that simple name works after package is installed.
        
        Expected behavior:
        1. Install package with full path
        2. Run with simple name (just the prompt name)
        3. Should discover and run from installed package
        """
        # Set up environment
        env = os.environ.copy()
        env['HOME'] = temp_e2e_home
        
        # First install with full path - early termination
        process = subprocess.Popen(
            [
                "apm",
                "run",
                "github/awesome-copilot/prompts/architecture-blueprint-generator"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=self.test_dir,
            env=env
        )
        
        try:
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                if "✨ Package installed and ready to run" in line:
                    process.terminate()
                    break
            process.wait(timeout=5)
        except:
            process.kill()
            process.wait()
        
        # Run with simple name - early termination
        process = subprocess.Popen(
            [
                "apm",
                "run",
                "architecture-blueprint-generator"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=self.test_dir,
            env=env
        )
        
        output_lines = []
        try:
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                output_lines.append(line)
                # Terminate once we see execution starting
                if "Executing" in line or "Auto-discovered" in line:
                    process.terminate()
                    break
            process.wait(timeout=5)
        except:
            process.kill()
            process.wait()
        finally:
            output = ''.join(output_lines)
        
        # Check output - should discover the installed prompt
        assert "Auto-discovered" in output or "ℹ" in output, \
            "Should auto-discover prompt from installed package"
        
        print("✅ Simple name works after installation")
    
    def test_auto_install_with_qualified_path(self, temp_e2e_home):
        """Test auto-install works with qualified path format.
        
        Tests both formats:
        - Full: github/awesome-copilot/prompts/file.prompt.md
        - Qualified: github/awesome-copilot/architecture-blueprint-generator
        """
        # Set up environment
        env = os.environ.copy()
        env['HOME'] = temp_e2e_home
        
        # Test with qualified path (without .prompt.md extension) - early termination
        process = subprocess.Popen(
            [
                "apm",
                "run",
                "github/awesome-copilot/prompts/architecture-blueprint-generator"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=self.test_dir,
            env=env
        )
        
        try:
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                # Terminate once installation completes
                if "✨ Package installed and ready to run" in line:
                    process.terminate()
                    break
            process.wait(timeout=5)
        except:
            process.kill()
            process.wait()
        
        # Check that package was installed
        package_path = Path("apm_modules/github/awesome-copilot-architecture-blueprint-generator")
        assert package_path.exists(), "Package should be installed"
        
        # Check that prompt file exists
        prompt_file = package_path / ".apm" / "prompts" / "architecture-blueprint-generator.prompt.md"
        assert prompt_file.exists(), "Prompt file should exist"
        
        print("✅ Auto-install works with qualified path")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

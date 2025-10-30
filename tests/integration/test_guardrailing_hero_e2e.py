"""
End-to-end test for README Hero Scenario 2: 2-Minute Guardrailing

Tests the exact 2-minute guardrailing flow from README (lines 46-60):
1. apm init my-project && cd my-project
2. apm install danielmeppiel/design-guidelines
3. apm install danielmeppiel/compliance-rules
4. apm compile
5. apm run design-review

This validates that:
- Multiple APM packages can be installed
- AGENTS.md is generated with combined guardrails
- Prompts from installed packages work correctly
"""

import os
import subprocess
import tempfile
import pytest
from pathlib import Path


# Skip all tests in this module if not in E2E mode
E2E_MODE = os.environ.get('APM_E2E_TESTS', '').lower() in ('1', 'true', 'yes')

# Token detection for test requirements
GITHUB_APM_PAT = os.environ.get('GITHUB_APM_PAT')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
PRIMARY_TOKEN = GITHUB_APM_PAT or GITHUB_TOKEN

pytestmark = pytest.mark.skipif(
    not E2E_MODE, 
    reason="E2E tests only run when APM_E2E_TESTS=1 is set"
)


def run_command(cmd, check=True, capture_output=True, timeout=180, cwd=None, show_output=False, env=None):
    """Run a shell command with proper error handling."""
    try:
        if show_output:
            print(f"\n>>> Running command: {cmd}")
            result = subprocess.run(
                cmd, 
                shell=True, 
                check=check, 
                capture_output=False,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=env
            )
            result_capture = subprocess.run(
                cmd, 
                shell=True, 
                check=False,
                capture_output=True, 
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=env
            )
            result.stdout = result_capture.stdout
            result.stderr = result_capture.stderr
        else:
            result = subprocess.run(
                cmd, 
                shell=True, 
                check=check, 
                capture_output=capture_output, 
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=env
            )
        return result
    except subprocess.TimeoutExpired:
        pytest.fail(f"Command timed out after {timeout}s: {cmd}")
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Command failed: {cmd}\nStdout: {e.stdout}\nStderr: {e.stderr}")


@pytest.fixture(scope="module")
def apm_binary():
    """Get path to APM binary for testing."""
    possible_paths = [
        "apm",
        "./apm",
        "./dist/apm",
        Path(__file__).parent.parent.parent / "dist" / "apm",
    ]
    
    for path in possible_paths:
        try:
            result = subprocess.run([str(path), "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                return str(path)
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    
    pytest.skip("APM binary not found. Build it first with: python -m build")


class TestGuardrailingHeroScenario:
    """Test README Hero Scenario 2: 2-Minute Guardrailing"""
    
    @pytest.mark.skipif(not PRIMARY_TOKEN, reason="GitHub token required for E2E tests")
    def test_2_minute_guardrailing_flow(self, apm_binary):
        """Test the exact 2-minute guardrailing flow from README.
        
        Validates:
        1. apm init my-project creates minimal project
        2. apm install danielmeppiel/design-guidelines succeeds
        3. apm install danielmeppiel/compliance-rules succeeds
        4. apm compile generates AGENTS.md with both packages
        5. apm run design-review executes prompt from installed package
        """
        
        with tempfile.TemporaryDirectory() as workspace:
            # Step 1: apm init my-project
            print("\n=== Step 1: apm init my-project ===")
            result = run_command(f"{apm_binary} init my-project --yes", cwd=workspace, show_output=True)
            assert result.returncode == 0, f"Project init failed: {result.stderr}"
            
            project_dir = Path(workspace) / "my-project"
            assert project_dir.exists(), "Project directory not created"
            assert (project_dir / "apm.yml").exists(), "apm.yml not created"
            
            print("✓ Project initialized")
            
            # Step 2: apm install danielmeppiel/design-guidelines
            print("\n=== Step 2: apm install danielmeppiel/design-guidelines ===")
            env = os.environ.copy()
            result = run_command(
                f"{apm_binary} install danielmeppiel/design-guidelines", 
                cwd=project_dir, 
                show_output=True,
                env=env
            )
            assert result.returncode == 0, f"design-guidelines install failed: {result.stderr}"
            
            # Verify installation
            design_pkg = project_dir / "apm_modules" / "danielmeppiel" / "design-guidelines"
            assert design_pkg.exists(), "design-guidelines package not installed"
            assert (design_pkg / "apm.yml").exists(), "design-guidelines apm.yml not found"
            
            print("✓ design-guidelines installed")
            
            # Step 3: apm install danielmeppiel/compliance-rules
            print("\n=== Step 3: apm install danielmeppiel/compliance-rules ===")
            result = run_command(
                f"{apm_binary} install danielmeppiel/compliance-rules", 
                cwd=project_dir, 
                show_output=True,
                env=env
            )
            assert result.returncode == 0, f"compliance-rules install failed: {result.stderr}"
            
            # Verify installation
            compliance_pkg = project_dir / "apm_modules" / "danielmeppiel" / "compliance-rules"
            assert compliance_pkg.exists(), "compliance-rules package not installed"
            assert (compliance_pkg / "apm.yml").exists(), "compliance-rules apm.yml not found"
            
            print("✓ compliance-rules installed")
            
            # Step 4: apm compile
            print("\n=== Step 4: apm compile ===")
            result = run_command(f"{apm_binary} compile", cwd=project_dir, show_output=True)
            assert result.returncode == 0, f"Compilation failed: {result.stderr}"
            
            # Verify AGENTS.md was generated
            agents_md = project_dir / "AGENTS.md"
            assert agents_md.exists(), "AGENTS.md not generated"
            
            # Verify AGENTS.md contains content from both packages
            agents_content = agents_md.read_text()
            assert "design-guidelines" in agents_content.lower() or "design" in agents_content.lower(), \
                "AGENTS.md doesn't contain design-guidelines content"
            assert "compliance" in agents_content.lower() or "gdpr" in agents_content.lower(), \
                "AGENTS.md doesn't contain compliance-rules content"
            
            print(f"✓ AGENTS.md generated ({len(agents_content)} bytes)")
            print(f"  Contains design-guidelines: ✓")
            print(f"  Contains compliance-rules: ✓")
            
            # Step 5: apm run design-review
            print("\n=== Step 5: apm run design-review ===")
            
            # Use early termination pattern - we only need to verify prompt starts correctly
            # Don't wait for full Copilot CLI execution (takes minutes)
            process = subprocess.Popen(
                f"{apm_binary} run design-review",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=project_dir,
                env=env
            )
            
            # Monitor output for success signals
            output_lines = []
            prompt_started = False
            
            try:
                for line in iter(process.stdout.readline, ''):
                    if not line:
                        break
                    
                    output_lines.append(line.rstrip())
                    print(f"  {line.rstrip()}")
                    
                    # Look for signals that prompt execution started successfully
                    if any(signal in line for signal in [
                        "Subprocess execution:",  # Codex about to run
                    ]):
                        prompt_started = True
                        print("✓ design-review prompt execution started")
                        break
                
                # Terminate the process gracefully
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                
            except Exception as e:
                process.kill()
                process.wait()
                pytest.fail(f"Error monitoring design-review execution: {e}")
            
            # Verify prompt was found and started
            full_output = '\n'.join(output_lines)
            assert prompt_started or "design-review" in full_output, \
                f"Prompt execution didn't start correctly. Output:\n{full_output}"
            
            print("✓ design-review prompt found and started successfully")
            
            print("\n=== 2-Minute Guardrailing Hero Scenario: PASSED ✨ ===")
            print("✓ Project initialization")
            print("✓ Multiple APM package installation")
            print("✓ AGENTS.md compilation with combined guardrails")
            print("✓ Prompt execution from installed package")


if __name__ == "__main__":
    if E2E_MODE:
        pytest.main([__file__, "-v", "-s"])
    else:
        print("E2E mode not enabled. Set APM_E2E_TESTS=1 to run these tests.")

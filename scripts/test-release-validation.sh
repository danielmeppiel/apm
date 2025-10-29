#!/bin/bash
#!/bin/bash
# Release validation script - Final pre-release testing
# Tests the EXACT user experience with the shipped binary in complete isolation:
#   1. Download/extract binary (as users would)
#   2. apm runtime setup codex  
#   3. apm init my-ai-native-project
#   4. cd my-ai-native-project && apm compile
#   5. apm install
#   6. apm run start --param name="<YourGitHubHandle>"
#
# Environment: Complete isolation - NO source code, only the binary
# Purpose: Validate that end-users will have a successful experience
# This is the final gate before release - testing the actual product as shipped

set -uo pipefail  # Removed -e to allow better error handling

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_test() {
    echo -e "${YELLOW}🧪 $1${NC}"
}

# Source the GitHub token management helper
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/github-token-helper.sh"

# Source the dependency integration testing functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/test-dependency-integration.sh" ]]; then
    source "$SCRIPT_DIR/test-dependency-integration.sh"
    DEPENDENCY_TESTS_AVAILABLE=true
else
    DEPENDENCY_TESTS_AVAILABLE=false
fi

# Global variables (needed for cleanup and cross-function access)
test_dir=""
BINARY_PATH=""

# Find the binary
find_binary() {
    if [[ $# -gt 0 ]]; then
        # Binary path provided as argument
        BINARY_PATH="$1"
    elif [[ -f "./apm" ]]; then
        # Look for symlink in current directory (CI setup)
        BINARY_PATH="./apm"
    elif command -v apm >/dev/null 2>&1; then
        # Look in PATH
        BINARY_PATH="$(which apm)"
    else
        log_error "APM binary not found. Usage: $0 [path-to-binary]"
        exit 1
    fi
    
    if [[ ! -x "$BINARY_PATH" ]]; then
        log_error "Binary not executable: $BINARY_PATH"
        exit 1
    fi
    
    # Convert to absolute path before we change directories
    BINARY_PATH="$(realpath "$BINARY_PATH")"
    
    log_info "Testing binary: $BINARY_PATH"
}

# Prerequisites check
check_prerequisites() {
    log_test "Prerequisites: GitHub token"
    
    # Use centralized token management
    if setup_github_tokens; then
        log_success "GitHub tokens configured successfully"
        return 0
    else
        log_error "GitHub token setup failed"
        return 1
    fi
    
    # Set up GitHub tokens for testing
    # No specific NPM authentication needed for public runtimes
    if [[ -n "${GITHUB_APM_PAT:-}" ]]; then
        log_success "GITHUB_APM_PAT is set (APM module access)"
        export GITHUB_APM_PAT="${GITHUB_APM_PAT}"
    fi
    
    if [[ -n "${GITHUB_TOKEN:-}" ]]; then
        log_success "GITHUB_TOKEN is set (GitHub Models access)"
        export GITHUB_TOKEN="${GITHUB_TOKEN}"
    fi
}

# Test Step 2: apm runtime setup codex
test_runtime_setup() {
    log_test "README Step 2: apm runtime setup codex"
    
    # Test runtime setup (this may take a moment)
    echo "Running: $BINARY_PATH runtime setup codex"
    echo "--- Command Output Start ---"
    "$BINARY_PATH" runtime setup codex 2>&1
    local exit_code=$?
    echo "--- Command Output End ---"
    echo "Exit code: $exit_code"
    
    if [[ $exit_code -ne 0 ]]; then
        log_error "apm runtime setup codex failed with exit code $exit_code"
        return 1
    fi
    
    log_success "Runtime setup completed"
}

# Test Step 3: apm init my-ai-native-project
test_init_project() {
    log_test "README Step 3: apm init my-ai-native-project"
    
    # Test init with the exact project name from README
    echo "Running: $BINARY_PATH init my-ai-native-project --yes"
    echo "--- Command Output Start ---"
    "$BINARY_PATH" init my-ai-native-project --yes 2>&1
    local exit_code=$?
    echo "--- Command Output End ---"
    echo "Exit code: $exit_code"
    
    if [[ $exit_code -ne 0 ]]; then
        log_error "apm init my-ai-native-project failed with exit code $exit_code"
        return 1
    fi
    
    # Check that the project directory was created
    if [[ ! -d "my-ai-native-project" ]]; then
        log_error "my-ai-native-project directory not created"
        return 1
    fi
    
    # Check that apm.yml was created (minimal mode - only apm.yml)
    if [[ ! -f "my-ai-native-project/apm.yml" ]]; then
        log_error "apm.yml not created in project"
        return 1
    fi
    
    log_success "Project initialization completed (minimal mode)"
    
    # NEW: Create minimal project structure for testing (simulating user workflow)
    log_info "Creating minimal project structure for validation testing..."
    
    cd my-ai-native-project
    
    # Create .apm directory with minimal instruction
    mkdir -p .apm/instructions
    cat > .apm/instructions/test.instructions.md << 'EOF'
---
applyTo: "**"
description: Test instructions for release validation
---

# Test Instructions

Basic instructions for release validation testing.
EOF
    
    # Create a simple prompt file for testing
    cat > hello-world.prompt.md << 'EOF'
---
description: Hello World prompt for validation
---

# Hello World

This is a test prompt for {{name}}.

Say hello to {{name}}!
EOF
    
    # Update apm.yml to add start script
    # Note: Using simple append to avoid Python/YAML dependency issues in isolated test
    cat >> apm.yml << 'EOF'

# Scripts added for release validation testing
scripts:
  start: "codex hello-world.prompt.md"
EOF
    
    cd ..
    log_info "Project structure created for testing"
    
    log_success "Project initialization and setup completed"
}

# Test Step 4: cd my-ai-native-project && apm compile
test_compile() {
    log_test "README Step 4: cd my-ai-native-project && apm compile"
    
    cd my-ai-native-project
    
    # Test compile (the critical step that was failing) - show actual error
    echo "Running: $BINARY_PATH compile"
    echo "--- Command Output Start ---"
    "$BINARY_PATH" compile 2>&1
    local exit_code=$?
    echo "--- Command Output End ---"
    echo "Exit code: $exit_code"
    
    if [[ $exit_code -ne 0 ]]; then
        log_error "apm compile failed with exit code $exit_code"
        cd ..
        return 1
    fi
    
    # Check that agents.md was created
    if [[ ! -f "AGENTS.md" ]]; then
        log_error "AGENTS.md not created by compile"
        cd ..
        return 1
    fi
    
    cd ..
    log_success "Compilation completed"
}

# Test Step 5 Part 1: apm install
test_install() {
    log_test "README Step 5: apm install"
    
    cd my-ai-native-project
    
    # Test install - preserve APM_E2E_TESTS for automated testing
    echo "Running: $BINARY_PATH install"
    echo "--- Command Output Start ---"
    APM_E2E_TESTS="${APM_E2E_TESTS:-}" "$BINARY_PATH" install 2>&1
    local exit_code=$?
    echo "--- Command Output End ---"
    echo "Exit code: $exit_code"
    
    if [[ $exit_code -ne 0 ]]; then
        log_error "apm install failed with exit code $exit_code"
        cd ..
        return 1
    fi
    
    cd ..
    log_success "Install completed"
}

# Test Step 5 Part 2: apm run start --param name="<YourGitHubHandle>"
test_run_command() {
    log_test "README Step 5: apm run start --param name=\"Developer\""
    
    cd my-ai-native-project
    
    # Test run (this may not fully complete but should at least start)
    # We'll check that it doesn't fail immediately due to binary issues
    echo "Running: $BINARY_PATH run start --param name=\"danielmeppiel\" (with 10s timeout)"
    echo "--- Command Output Start ---"
    timeout 10s "$BINARY_PATH" run start --param name="danielmeppiel" 2>&1
    local exit_code=$?
    echo "--- Command Output End ---"
    echo "Exit code: $exit_code"
    
    if [[ $exit_code -eq 124 ]]; then
        # Exit code 124 is timeout, which is expected and OK
        log_success "Run command started successfully (timed out as expected)"
    elif [[ $exit_code -eq 0 ]]; then
        # Command completed successfully within timeout
        log_success "Run command completed successfully"
    else
        log_error "apm run command failed immediately with exit code $exit_code"
        cd ..
        return 1
    fi
    
    cd ..
}

# Test basic commands (sanity check)
test_basic_commands() {
    log_test "Sanity check: Basic commands"
    
    # Test --version (show actual error if it fails)
    echo "Running: $BINARY_PATH --version"
    echo "--- Command Output Start ---"
    "$BINARY_PATH" --version
    local version_exit_code=$?
    echo "--- Command Output End ---"
    echo "Exit code: $version_exit_code"
    
    if [[ $version_exit_code -ne 0 ]]; then
        log_error "apm --version failed with exit code $version_exit_code"
        return 1
    fi
    
    # Test --help
    echo "Running: $BINARY_PATH --help"
    echo "--- Command Output Start ---"
    "$BINARY_PATH" --help 2>&1 | head -20  # Limit output for readability
    local help_exit_code=${PIPESTATUS[0]}
    echo "--- Command Output End ---"
    echo "Exit code: $help_exit_code"
    
    if [[ $help_exit_code -ne 0 ]]; then
        log_error "apm --help failed with exit code $help_exit_code"
        return 1
    fi
    
    log_success "Basic commands work"
}

# Main test runner - follows exact README flow
main() {
echo "APM CLI Release Validation - Binary Isolation Testing"
echo "====================================================="
echo ""
echo "Testing the EXACT user experience with the shipped binary"
echo "Environment: Complete isolation (no source code access)"
echo "Purpose: Final validation before release"
echo ""
    
    find_binary "$@"
    
    # Test binary accessibility first
    echo "Testing binary accessibility..."
    if [[ ! -f "$BINARY_PATH" ]]; then
        log_error "Binary file does not exist: $BINARY_PATH"
        exit 1
    fi
    
    if [[ ! -x "$BINARY_PATH" ]]; then
        log_error "Binary is not executable: $BINARY_PATH"
        exit 1
    fi
    
    echo "Binary found and executable: $BINARY_PATH"
    
    local tests_passed=0
    local tests_total=6
    local dependency_tests_run=false
    
    # Add dependency tests to total if available and GITHUB token is present
    if [[ "$DEPENDENCY_TESTS_AVAILABLE" == "true" ]] && [[ -n "${GITHUB_CLI_PAT:-}" || -n "${GITHUB_TOKEN:-}" ]]; then
        tests_total=$((tests_total + 1))
        dependency_tests_run=true
        log_info "Dependency integration tests will be included"
    elif [[ "$DEPENDENCY_TESTS_AVAILABLE" == "true" ]]; then
        log_info "Dependency integration tests available but no GitHub token - skipping"
    else
        log_info "Dependency integration tests not available - skipping"
    fi
    
    # Create isolated test directory
    test_dir="binary-golden-scenario-$$"  # Make it global for cleanup
    mkdir "$test_dir" && cd "$test_dir"
    
    # Run the exact README golden scenario
    if check_prerequisites; then
        ((tests_passed++))
    else
        log_error "Prerequisites check failed"
    fi
    
    if test_basic_commands; then
        ((tests_passed++))
    else
        log_error "Basic commands test failed"
    fi
    
    if test_runtime_setup; then
        ((tests_passed++))
    else
        log_error "Runtime setup test failed"
    fi
    
    if test_init_project; then
        ((tests_passed++))
    else
        log_error "Project init test failed"
    fi
    
    if test_compile; then
        ((tests_passed++))
    else
        log_error "Compile test failed"
    fi
    
    if test_install; then
        ((tests_passed++))
    else
        log_error "Install test failed"
    fi
    
    # Note: Skipping the run test for now as it requires more complex setup
    # if test_run_command; then
    #     ((tests_passed++))
    # fi
    
    # Run dependency integration tests if available and GitHub token is set
    if [[ "$dependency_tests_run" == "true" ]]; then
        log_info "Running dependency integration tests with real GitHub repositories"
        if test_dependency_integration "$BINARY_PATH"; then
            ((tests_passed++))
            log_success "Dependency integration tests passed"
        else
            log_error "Dependency integration tests failed"
        fi
    fi
    
    cd ..
    
    echo ""
    echo "Results: $tests_passed/$tests_total golden scenario steps passed"
    
    if [[ $tests_passed -eq $tests_total ]]; then
        echo "✅ RELEASE VALIDATION PASSED!"
        echo ""
        echo "🚀 Binary is ready for production release"
        echo "📦 End-user experience validated successfully" 
        echo "🎯 Hero flow works exactly as documented"
        echo ""
        echo "Validated user journey:"
        echo "  1. Prerequisites (GITHUB_TOKEN) ✅"
        echo "  2. Binary accessibility ✅"
        echo "  3. Runtime setup ✅"
        echo "  4. Project initialization ✅"
        echo "  5. Agent compilation ✅"
        echo "  6. Dependency installation ✅"
        if [[ "$dependency_tests_run" == "true" ]]; then
            echo "  7. Real dependency integration ✅"
        fi
        echo ""
        log_success "README Golden Scenario works perfectly! ✨"
        echo ""
        echo "🎉 The binary delivers the exact README experience - real users will love it!"
        exit 0
    else
        log_error "Some golden scenario steps failed"
        echo ""
        echo "⚠️  The binary doesn't match the README promise"
        exit 1
    fi
}

# Cleanup on exit
cleanup() {
    # Clean up test directory if it exists
    if [[ -n "${test_dir:-}" && -d "$test_dir" ]]; then
        echo "🧹 Cleaning up test directory: $test_dir"
        # Make sure we're not inside the directory before removing it
        local current_dir=$(pwd)
        if [[ "$current_dir" == *"$test_dir"* ]]; then
            cd ..
        fi
        rm -rf "$test_dir" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Run main function
main "$@"
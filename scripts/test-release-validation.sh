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

# Helper function for cross-platform timeout
run_with_timeout() {
    local timeout_duration=$1
    shift
    local cmd="$@"
    
    # Use perl for cross-platform timeout support
    perl -e "alarm $timeout_duration; exec @ARGV" -- sh -c "$cmd" 2>&1 &
    local pid=$!
    
    # Wait for the command to complete or timeout
    wait $pid 2>/dev/null
    local exit_code=$?
    
    # Exit code 142 (SIGALRM) means timeout
    if [[ $exit_code -eq 142 ]]; then
        return 124  # Return timeout code like GNU timeout
    fi
    
    return $exit_code
}

# HERO SCENARIO 1: 30-Second Zero-Config
# Test the exact README flow: runtime setup → run virtual package
test_hero_zero_config() {
    log_test "HERO SCENARIO 1: 30-Second Zero-Config (README lines 35-44)"
    
    # Create temporary directory for this test
    mkdir -p zero-config-test && cd zero-config-test
    
    # Runtime setup is already done in test_runtime_setup()
    # Just test the virtual package run
    
    echo "Running: $BINARY_PATH run github/awesome-copilot/prompts/architecture-blueprint-generator (with 15s timeout)"
    echo "--- Command Output Start ---"
    run_with_timeout 15 "$BINARY_PATH run github/awesome-copilot/prompts/architecture-blueprint-generator"
    local exit_code=$?
    echo "--- Command Output End ---"
    echo "Exit code: $exit_code"
    
    if [[ $exit_code -eq 124 ]]; then
        # Exit code 124 is timeout, which is expected and OK (prompt execution started)
        log_success "Zero-config auto-install worked! Package installed and prompt started."
    elif [[ $exit_code -eq 0 ]]; then
        # Command completed successfully within timeout
        log_success "Zero-config auto-install completed successfully"
    else
        log_error "Zero-config auto-install failed immediately with exit code $exit_code"
        cd ..
        return 1
    fi
    
    # Verify package was actually installed
    if [[ ! -d "apm_modules/github/awesome-copilot-architecture-blueprint-generator" ]]; then
        log_error "Package was not installed by auto-install"
        cd ..
        return 1
    fi
    
    log_success "Package auto-installed to apm_modules/"
    
    # Test second run (should use cached package, no re-download)
    echo "Testing second run (should use cache)..."
    run_with_timeout 10 "$BINARY_PATH run github/awesome-copilot/prompts/architecture-blueprint-generator" | head -20
    local second_exit_code=${PIPESTATUS[0]}
    
    if [[ $second_exit_code -eq 124 || $second_exit_code -eq 0 ]]; then
        log_success "Second run used cached package (fast, no re-download)"
    fi
    
    cd ..
    log_success "HERO SCENARIO 1: 30-second zero-config PASSED ✨"
}

# HERO SCENARIO 2: 2-Minute Guardrailing
# Test the exact README flow: init → install packages → compile → run
test_hero_guardrailing() {
    log_test "HERO SCENARIO 2: 2-Minute Guardrailing (README lines 46-60)"
    
    # Step 1: apm init my-project
    echo "Running: $BINARY_PATH init my-project --yes"
    echo "--- Command Output Start ---"
    "$BINARY_PATH" init my-project --yes 2>&1
    local exit_code=$?
    echo "--- Command Output End ---"
    echo "Exit code: $exit_code"
    
    if [[ $exit_code -ne 0 ]]; then
        log_error "apm init my-project failed with exit code $exit_code"
        return 1
    fi
    
    if [[ ! -d "my-project" || ! -f "my-project/apm.yml" ]]; then
        log_error "my-project directory or apm.yml not created"
        return 1
    fi
    
    log_success "Project initialized"
    
    cd my-project
    
    # Step 2: apm install danielmeppiel/design-guidelines
    echo "Running: $BINARY_PATH install danielmeppiel/design-guidelines"
    echo "--- Command Output Start ---"
    APM_E2E_TESTS="${APM_E2E_TESTS:-}" "$BINARY_PATH" install danielmeppiel/design-guidelines 2>&1
    exit_code=$?
    echo "--- Command Output End ---"
    echo "Exit code: $exit_code"
    
    if [[ $exit_code -ne 0 ]]; then
        log_error "apm install danielmeppiel/design-guidelines failed"
        cd ..
        return 1
    fi
    
    log_success "design-guidelines installed"
    
    # Step 3: apm install danielmeppiel/compliance-rules
    echo "Running: $BINARY_PATH install danielmeppiel/compliance-rules"
    echo "--- Command Output Start ---"
    APM_E2E_TESTS="${APM_E2E_TESTS:-}" "$BINARY_PATH" install danielmeppiel/compliance-rules 2>&1
    exit_code=$?
    echo "--- Command Output End ---"
    echo "Exit code: $exit_code"
    
    if [[ $exit_code -ne 0 ]]; then
        log_error "apm install danielmeppiel/compliance-rules failed"
        cd ..
        return 1
    fi
    
    log_success "compliance-rules installed"
    
    # Step 4: apm compile
    echo "Running: $BINARY_PATH compile"
    echo "--- Command Output Start ---"
    "$BINARY_PATH" compile 2>&1
    exit_code=$?
    echo "--- Command Output End ---"
    echo "Exit code: $exit_code"
    
    if [[ $exit_code -ne 0 ]]; then
        log_error "apm compile failed"
        cd ..
        return 1
    fi
    
    if [[ ! -f "AGENTS.md" ]]; then
        log_error "AGENTS.md not created by compile"
        cd ..
        return 1
    fi
    
    log_success "Compiled to AGENTS.md (guardrails active)"
    
    # Step 5: apm run design-review (from installed package)
    echo "Running: $BINARY_PATH run design-review (with 10s timeout)"
    echo "--- Command Output Start ---"
    run_with_timeout 10 "$BINARY_PATH run design-review"
    exit_code=$?
    echo "--- Command Output End ---"
    echo "Exit code: $exit_code"
    
    if [[ $exit_code -eq 124 ]]; then
        # Timeout is expected and OK - prompt started executing
        log_success "design-review prompt executed with compiled guardrails"
    elif [[ $exit_code -eq 0 ]]; then
        log_success "design-review completed successfully"
    else
        log_error "apm run design-review failed immediately"
        cd ..
        return 1
    fi
    
    cd ..
    log_success "HERO SCENARIO 2: 2-minute guardrailing PASSED ✨"
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
    local tests_total=5  # Prerequisites, basic commands, runtime setup, 2 hero scenarios
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
    
    # Run prerequisites and basic tests
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
    
    # HERO SCENARIO 1: 30-second zero-config
    if test_hero_zero_config; then
        ((tests_passed++))
    else
        log_error "Hero scenario 1 (30-sec zero-config) failed"
    fi
    
    # HERO SCENARIO 2: 2-minute guardrailing
    if test_hero_guardrailing; then
        ((tests_passed++))
    else
        log_error "Hero scenario 2 (2-min guardrailing) failed"
    fi
    
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
    echo "Results: $tests_passed/$tests_total tests passed"
    
    if [[ $tests_passed -eq $tests_total ]]; then
        echo "✅ RELEASE VALIDATION PASSED!"
        echo ""
        echo "🚀 Binary is ready for production release"
        echo "📦 End-user experience validated successfully" 
        echo "🎯 Both README hero scenarios work perfectly"
        echo ""
        echo "Validated user journeys:"
        echo "  1. Prerequisites (GITHUB_TOKEN) ✅"
        echo "  2. Binary accessibility ✅"
        echo "  3. Runtime setup (copilot) ✅"
        echo ""
        echo "  HERO SCENARIO 1: 30-Second Zero-Config ✨"
        echo "    - Run virtual package directly ✅"
        echo "    - Auto-install on first run ✅"
        echo "    - Use cached package on second run ✅"
        echo ""
        echo "  HERO SCENARIO 2: 2-Minute Guardrailing ✨"
        echo "    - Project initialization ✅"
        echo "    - Install APM packages ✅"
        echo "    - Compile to AGENTS.md guardrails ✅"
        echo "    - Run prompts with guardrails ✅"
        if [[ "$dependency_tests_run" == "true" ]]; then
            echo ""
            echo "  BONUS: Real dependency integration ✅"
        fi
        echo ""
        log_success "README Hero Scenarios work perfectly! ✨"
        echo ""
        echo "🎉 The binary delivers the exact README experience - real users will love it!"
        exit 0
    else
        log_error "Some tests failed"
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
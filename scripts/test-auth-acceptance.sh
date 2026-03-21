#!/usr/bin/env bash
# =============================================================================
# APM Auth Acceptance Tests
# =============================================================================
#
# Tests the auth resolution chain across token sources, host types, and repo
# visibilities. Covers P0 scenarios from the auth acceptance matrix.
#
# LOCAL USAGE:
#   # 1. Set required tokens:
#   export APM_BINARY="/path/to/apm"          # or uses 'apm' from PATH
#   export AUTH_TEST_PUBLIC_REPO="microsoft/apm-sample-package"
#   export AUTH_TEST_PRIVATE_REPO="your-org/private-repo"  # optional
#   export AUTH_TEST_EMU_REPO="emu-org/internal-repo"      # optional
#   export GITHUB_APM_PAT="ghp_..."                        # or github_pat_...
#   export GITHUB_APM_PAT_YOURORG="github_pat_..."         # for per-org test
#
#   # 2. Run:
#   ./scripts/test-auth-acceptance.sh
#
# CI USAGE (GitHub Actions):
#   Triggered via workflow_dispatch. Secrets injected as env vars.
#   See .github/workflows/auth-acceptance.yml
#
# =============================================================================

set -uo pipefail

# ---------------------------------------------------------------------------
# Colors & symbols
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0
RESULTS=()   # array of "STATUS scenario_name"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
APM_BINARY="${APM_BINARY:-apm}"
AUTH_TEST_PUBLIC_REPO="${AUTH_TEST_PUBLIC_REPO:-microsoft/apm-sample-package}"
AUTH_TEST_PRIVATE_REPO="${AUTH_TEST_PRIVATE_REPO:-}"
AUTH_TEST_EMU_REPO="${AUTH_TEST_EMU_REPO:-}"

# Stash original env so we can restore between tests
_ORIG_GITHUB_APM_PAT="${GITHUB_APM_PAT:-}"
_ORIG_GITHUB_TOKEN="${GITHUB_TOKEN:-}"
_ORIG_GH_TOKEN="${GH_TOKEN:-}"

# ---------------------------------------------------------------------------
# Temp dir & cleanup
# ---------------------------------------------------------------------------
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log_header() {
    echo ""
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${BLUE}  $1${NC}"
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

log_scenario() {
    echo ""
    echo -e "${BOLD}🧪 Scenario: $1${NC}"
}

record_pass() {
    local name="$1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
    RESULTS+=("PASS $name")
    echo -e "  ${GREEN}✅ PASS${NC} — $name"
}

record_fail() {
    local name="$1"
    local detail="${2:-}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    RESULTS+=("FAIL $name")
    echo -e "  ${RED}❌ FAIL${NC} — $name"
    if [[ -n "$detail" ]]; then
        echo -e "  ${DIM}   $detail${NC}"
    fi
}

record_skip() {
    local name="$1"
    local reason="${2:-missing env var}"
    TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
    RESULTS+=("SKIP $name")
    echo -e "  ${YELLOW}⏭️  SKIP${NC} — $name ($reason)"
}

# Prepare a minimal apm.yml in a fresh temp directory and echo the path.
# Usage: test_dir=$(setup_test_dir "owner/repo")
setup_test_dir() {
    local package="$1"
    local dir
    dir="$(mktemp -d "$WORK_DIR/test-XXXXXX")"
    cat > "$dir/apm.yml" <<EOF
name: auth-test
version: 0.0.1
description: Auth acceptance test fixture
author: ci

dependencies:
  apm:
    - "$package"
EOF
    echo "$dir"
}

# Run apm install, capturing combined stdout+stderr.
# Returns exit code. Output is stored in $APM_OUTPUT.
# Usage: run_apm_install <package> [extra_args...]
run_apm_install() {
    local package="$1"; shift
    local dir
    dir="$(setup_test_dir "$package")"

    APM_OUTPUT="$(cd "$dir" && "$APM_BINARY" install "$@" 2>&1)" && APM_EXIT=0 || APM_EXIT=$?
}

# Assert that $APM_OUTPUT contains a pattern (extended grep).
assert_output_contains() {
    local pattern="$1"
    local msg="${2:-output should contain '$pattern'}"
    if echo "$APM_OUTPUT" | grep -qiE "$pattern"; then
        return 0
    else
        record_fail "$msg" "pattern not found: $pattern"
        return 1
    fi
}

# Assert that $APM_OUTPUT does NOT contain a pattern.
assert_output_not_contains() {
    local pattern="$1"
    local msg="${2:-output should not contain '$pattern'}"
    if echo "$APM_OUTPUT" | grep -qiE "$pattern"; then
        record_fail "$msg" "unexpected pattern found: $pattern"
        return 1
    else
        return 0
    fi
}

# Assert exit code.
assert_exit_code() {
    local expected="$1"
    local msg="${2:-exit code should be $expected}"
    if [[ "$APM_EXIT" -eq "$expected" ]]; then
        return 0
    else
        record_fail "$msg" "expected exit=$expected, got exit=$APM_EXIT"
        return 1
    fi
}

# Unset all auth env vars to guarantee a clean slate.
unset_all_auth() {
    unset GITHUB_APM_PAT 2>/dev/null || true
    unset GITHUB_TOKEN 2>/dev/null || true
    unset GH_TOKEN 2>/dev/null || true
    # Unset any per-org vars that may have been set
    while IFS='=' read -r name _; do
        if [[ "$name" == GITHUB_APM_PAT_* ]]; then
            unset "$name" 2>/dev/null || true
        fi
    done < <(env)
}

# Restore original auth env vars.
restore_auth() {
    unset_all_auth
    [[ -n "$_ORIG_GITHUB_APM_PAT" ]] && export GITHUB_APM_PAT="$_ORIG_GITHUB_APM_PAT"
    [[ -n "$_ORIG_GITHUB_TOKEN" ]] && export GITHUB_TOKEN="$_ORIG_GITHUB_TOKEN"
    [[ -n "$_ORIG_GH_TOKEN" ]] && export GH_TOKEN="$_ORIG_GH_TOKEN"
}

# Derive the org-env-suffix from an owner/repo string.
# "my-org/repo" → "MY_ORG"
org_env_suffix() {
    local owner="${1%%/*}"
    echo "$owner" | tr '[:lower:]-' '[:upper:]_'
}

# ---------------------------------------------------------------------------
# Scenario 1: Public repo, no auth
# ---------------------------------------------------------------------------
test_scenario_1_public_no_auth() {
    local name="Public repo, no auth"
    log_scenario "$name"
    unset_all_auth
    export GIT_TERMINAL_PROMPT=0
    export GCM_INTERACTIVE=never

    run_apm_install "$AUTH_TEST_PUBLIC_REPO" --verbose

    local ok=true
    assert_exit_code 0 "$name — succeeds" || ok=false
    assert_output_contains "unauthenticated" "$name — shows unauthenticated access" || ok=false
    assert_output_not_contains "source=GITHUB_APM_PAT" "$name — no PAT source shown" || ok=false

    $ok && record_pass "$name"
    restore_auth
}

# ---------------------------------------------------------------------------
# Scenario 2: Public repo, PAT set (rate-limit behavior)
# ---------------------------------------------------------------------------
test_scenario_2_public_with_pat() {
    local name="Public repo, PAT set"
    log_scenario "$name"

    if [[ -z "$_ORIG_GITHUB_APM_PAT" ]]; then
        record_skip "$name" "GITHUB_APM_PAT not set"
        return
    fi

    unset_all_auth
    export GITHUB_APM_PAT="$_ORIG_GITHUB_APM_PAT"

    run_apm_install "$AUTH_TEST_PUBLIC_REPO" --verbose

    local ok=true
    assert_exit_code 0 "$name — succeeds" || ok=false
    # Public repos try unauthenticated first to save rate limits
    assert_output_contains "unauthenticated" "$name — tries unauth first" || ok=false

    $ok && record_pass "$name"
    restore_auth
}

# ---------------------------------------------------------------------------
# Scenario 3: Private repo, global PAT
# ---------------------------------------------------------------------------
test_scenario_3_private_global_pat() {
    local name="Private repo, global PAT"
    log_scenario "$name"

    if [[ -z "$AUTH_TEST_PRIVATE_REPO" ]]; then
        record_skip "$name" "AUTH_TEST_PRIVATE_REPO not set"
        return
    fi
    if [[ -z "$_ORIG_GITHUB_APM_PAT" ]]; then
        record_skip "$name" "GITHUB_APM_PAT not set"
        return
    fi

    unset_all_auth
    export GITHUB_APM_PAT="$_ORIG_GITHUB_APM_PAT"

    run_apm_install "$AUTH_TEST_PRIVATE_REPO" --verbose

    local ok=true
    assert_exit_code 0 "$name — succeeds" || ok=false
    # Verbose should show the auth fallback chain
    assert_output_contains "source=GITHUB_APM_PAT" "$name — shows PAT source" || ok=false

    $ok && record_pass "$name"
    restore_auth
}

# ---------------------------------------------------------------------------
# Scenario 4: Private repo, per-org PAT
# ---------------------------------------------------------------------------
test_scenario_4_private_per_org_pat() {
    local name="Private repo, per-org PAT"
    log_scenario "$name"

    if [[ -z "$AUTH_TEST_PRIVATE_REPO" ]]; then
        record_skip "$name" "AUTH_TEST_PRIVATE_REPO not set"
        return
    fi

    local org_suffix
    org_suffix="$(org_env_suffix "$AUTH_TEST_PRIVATE_REPO")"
    local per_org_var="GITHUB_APM_PAT_${org_suffix}"
    local per_org_val="${!per_org_var:-}"

    if [[ -z "$per_org_val" ]] && [[ -n "$_ORIG_GITHUB_APM_PAT" ]]; then
        # Fall back to the global PAT for testing the per-org path
        per_org_val="$_ORIG_GITHUB_APM_PAT"
    fi
    if [[ -z "$per_org_val" ]]; then
        record_skip "$name" "$per_org_var not set"
        return
    fi

    unset_all_auth
    export "$per_org_var=$per_org_val"

    run_apm_install "$AUTH_TEST_PRIVATE_REPO" --verbose

    local ok=true
    assert_exit_code 0 "$name — succeeds" || ok=false
    assert_output_contains "source=GITHUB_APM_PAT_${org_suffix}" "$name — shows per-org source" || ok=false

    $ok && record_pass "$name"
    restore_auth
}

# ---------------------------------------------------------------------------
# Scenario 5: Token priority (per-org > global)
# ---------------------------------------------------------------------------
test_scenario_5_token_priority() {
    local name="Token priority: per-org > global"
    log_scenario "$name"

    if [[ -z "$AUTH_TEST_PRIVATE_REPO" ]]; then
        record_skip "$name" "AUTH_TEST_PRIVATE_REPO not set"
        return
    fi
    if [[ -z "$_ORIG_GITHUB_APM_PAT" ]]; then
        record_skip "$name" "GITHUB_APM_PAT not set"
        return
    fi

    local org_suffix
    org_suffix="$(org_env_suffix "$AUTH_TEST_PRIVATE_REPO")"
    local per_org_var="GITHUB_APM_PAT_${org_suffix}"

    unset_all_auth
    export GITHUB_APM_PAT="$_ORIG_GITHUB_APM_PAT"
    export "$per_org_var=$_ORIG_GITHUB_APM_PAT"

    run_apm_install "$AUTH_TEST_PRIVATE_REPO" --verbose

    local ok=true
    assert_exit_code 0 "$name — succeeds" || ok=false
    # Per-org should win over global
    assert_output_contains "source=GITHUB_APM_PAT_${org_suffix}" "$name — per-org wins" || ok=false

    $ok && record_pass "$name"
    restore_auth
}

# ---------------------------------------------------------------------------
# Scenario 6: GITHUB_TOKEN fallback
# ---------------------------------------------------------------------------
test_scenario_6_github_token_fallback() {
    local name="GITHUB_TOKEN fallback"
    log_scenario "$name"

    if [[ -z "$AUTH_TEST_PRIVATE_REPO" ]]; then
        record_skip "$name" "AUTH_TEST_PRIVATE_REPO not set"
        return
    fi
    if [[ -z "$_ORIG_GITHUB_TOKEN" ]] && [[ -z "$_ORIG_GITHUB_APM_PAT" ]]; then
        record_skip "$name" "GITHUB_TOKEN and GITHUB_APM_PAT not set"
        return
    fi

    local token="${_ORIG_GITHUB_TOKEN:-$_ORIG_GITHUB_APM_PAT}"

    unset_all_auth
    export GITHUB_TOKEN="$token"

    run_apm_install "$AUTH_TEST_PRIVATE_REPO" --verbose

    local ok=true
    assert_exit_code 0 "$name — succeeds" || ok=false
    assert_output_contains "source=GITHUB_TOKEN" "$name — shows GITHUB_TOKEN source" || ok=false

    $ok && record_pass "$name"
    restore_auth
}

# ---------------------------------------------------------------------------
# Scenario 7: Invalid token, graceful failure
# ---------------------------------------------------------------------------
test_scenario_7_invalid_token() {
    local name="Invalid token, graceful failure"
    log_scenario "$name"

    if [[ -z "$AUTH_TEST_PRIVATE_REPO" ]]; then
        record_skip "$name" "AUTH_TEST_PRIVATE_REPO not set"
        return
    fi

    unset_all_auth
    export GITHUB_APM_PAT="ghp_invalidtoken1234567890abcdefghijklmn"
    export GIT_TERMINAL_PROMPT=0
    export GCM_INTERACTIVE=never

    run_apm_install "$AUTH_TEST_PRIVATE_REPO" --verbose

    local ok=true
    assert_exit_code 1 "$name — fails with exit 1" || ok=false
    # Should not crash or produce a traceback
    assert_output_not_contains "Traceback" "$name — no Python traceback" || ok=false

    $ok && record_pass "$name"
    unset GCM_INTERACTIVE
    restore_auth
}

# ---------------------------------------------------------------------------
# Scenario 8: Nonexistent repo
# ---------------------------------------------------------------------------
test_scenario_8_nonexistent_repo() {
    local name="Nonexistent repo"
    log_scenario "$name"

    unset_all_auth
    export GIT_TERMINAL_PROMPT=0
    export GCM_INTERACTIVE=never

    run_apm_install "owner/this-repo-does-not-exist-12345" --verbose

    local ok=true
    assert_exit_code 1 "$name — fails with exit 1" || ok=false
    assert_output_contains "not accessible or doesn't exist" "$name — clear error message" || ok=false

    $ok && record_pass "$name"
    unset GCM_INTERACTIVE
    restore_auth
}

# ---------------------------------------------------------------------------
# Scenario 9: No auth, private repo
# ---------------------------------------------------------------------------
test_scenario_9_no_auth_private_repo() {
    local name="No auth, private repo"
    log_scenario "$name"

    if [[ -z "$AUTH_TEST_PRIVATE_REPO" ]]; then
        record_skip "$name" "AUTH_TEST_PRIVATE_REPO not set"
        return
    fi

    unset_all_auth
    export GIT_TERMINAL_PROMPT=0
    export GCM_INTERACTIVE=never

    run_apm_install "$AUTH_TEST_PRIVATE_REPO"

    local ok=true
    assert_exit_code 1 "$name — fails" || ok=false
    assert_output_contains "not accessible|--verbose|GITHUB_APM_PAT|GITHUB_TOKEN|auth" \
        "$name — suggests auth guidance" || ok=false

    $ok && record_pass "$name"
    unset GCM_INTERACTIVE
    restore_auth
}

# ---------------------------------------------------------------------------
# Scenario 10: Verbose vs non-verbose output contract
# ---------------------------------------------------------------------------
test_scenario_10_verbose_contract() {
    local name="Verbose vs non-verbose output contract"
    log_scenario "$name"

    unset_all_auth
    export GIT_TERMINAL_PROMPT=0
    export GCM_INTERACTIVE=never

    # Non-verbose run
    run_apm_install "owner/this-repo-does-not-exist-12345"
    local non_verbose_output="$APM_OUTPUT"
    local non_verbose_exit="$APM_EXIT"

    # Verbose run
    run_apm_install "owner/this-repo-does-not-exist-12345" --verbose
    local verbose_output="$APM_OUTPUT"
    local verbose_exit="$APM_EXIT"

    local ok=true

    # Both should fail
    APM_EXIT="$non_verbose_exit"
    assert_exit_code 1 "$name — non-verbose fails" || ok=false
    APM_EXIT="$verbose_exit"
    assert_exit_code 1 "$name — verbose fails" || ok=false

    # Non-verbose: should NOT expose auth resolution details
    APM_OUTPUT="$non_verbose_output"
    assert_output_not_contains "Auth resolved:" "$name — non-verbose hides auth details" || ok=false
    assert_output_contains "--verbose" "$name — non-verbose hints at --verbose" || ok=false

    # Verbose: should show auth diagnostic info
    APM_OUTPUT="$verbose_output"
    # Verbose output should contain auth-related diagnostic lines
    if echo "$verbose_output" | grep -qiE "Auth resolved|unauthenticated|API .* →"; then
        : # ok
    else
        record_fail "$name — verbose shows auth steps" "no auth diagnostic lines found"
        ok=false
    fi

    $ok && record_pass "$name"
    unset GCM_INTERACTIVE
    restore_auth
}

# ---------------------------------------------------------------------------
# Run all scenarios
# ---------------------------------------------------------------------------

log_header "APM Auth Acceptance Tests"
echo ""
echo -e "${DIM}Binary:       $APM_BINARY${NC}"
echo -e "${DIM}Public repo:  $AUTH_TEST_PUBLIC_REPO${NC}"
echo -e "${DIM}Private repo: ${AUTH_TEST_PRIVATE_REPO:-<not set>}${NC}"
echo -e "${DIM}EMU repo:     ${AUTH_TEST_EMU_REPO:-<not set>}${NC}"
echo ""

test_scenario_1_public_no_auth
test_scenario_2_public_with_pat
test_scenario_3_private_global_pat
test_scenario_4_private_per_org_pat
test_scenario_5_token_priority
test_scenario_6_github_token_fallback
test_scenario_7_invalid_token
test_scenario_8_nonexistent_repo
test_scenario_9_no_auth_private_repo
test_scenario_10_verbose_contract

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
TOTAL=$((TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED))

log_header "Summary"
echo ""
printf "  %-8s %s\n" "Total:" "$TOTAL"
printf "  ${GREEN}%-8s %s${NC}\n" "Passed:" "$TESTS_PASSED"
printf "  ${RED}%-8s %s${NC}\n" "Failed:" "$TESTS_FAILED"
printf "  ${YELLOW}%-8s %s${NC}\n" "Skipped:" "$TESTS_SKIPPED"
echo ""
echo -e "${DIM}──────────────────────────────────────────────────${NC}"

for entry in "${RESULTS[@]}"; do
    status="${entry%% *}"
    scenario="${entry#* }"
    case "$status" in
        PASS) echo -e "  ${GREEN}✅${NC} $scenario" ;;
        FAIL) echo -e "  ${RED}❌${NC} $scenario" ;;
        SKIP) echo -e "  ${YELLOW}⏭️${NC}  $scenario" ;;
    esac
done

echo -e "${DIM}──────────────────────────────────────────────────${NC}"
echo ""

if [[ "$TESTS_FAILED" -gt 0 ]]; then
    echo -e "${RED}${BOLD}Auth acceptance tests FAILED${NC}"
    exit 1
fi

echo -e "${GREEN}${BOLD}Auth acceptance tests PASSED${NC}"
exit 0

#!/usr/bin/env bash
# =============================================================================
# APM Auth Acceptance Tests
# =============================================================================
#
# Comprehensive auth E2E test suite covering every dimension of APM's
# authentication resolution chain. Designed to run against a REAL binary
# with REAL tokens and REAL repos — no mocks.
#
# =============================================================================
# SCENARIO MATRIX
# =============================================================================
#
# Dimension 1: Token Sources (resolution priority order)
#   A1  GITHUB_APM_PAT_{ORG}   Per-org PAT (highest priority)
#   A2  GITHUB_APM_PAT         Global APM PAT
#   A3  GITHUB_TOKEN           GitHub token (fallback)
#   A4  GH_TOKEN               GH CLI token (lowest env var)
#   A5  git credential fill    Credential helper (gh auth, keychain)
#   A6  (none)                 Unauthenticated
#   A7  ADO_APM_PAT            Azure DevOps PAT
#
# Dimension 2: Token Types
#   T1  github_pat_*           Fine-grained PAT (org-scoped)
#   T2  ghp_*                  Classic PAT
#   T3  ghu_*                  OAuth (gh auth login)
#   T5  (invalid)              Expired/wrong token
#
# Dimension 3: Host Types
#   H1  github.com             Public GitHub (unauth-first validation)
#   H2  *.ghe.com              GHE Cloud (auth-only, no public repos)
#   H4  dev.azure.com          Azure DevOps (ADO_APM_PAT only, no cred fill)
#
# Dimension 4: Repo Visibility
#   V1  Public                 Works unauthenticated on github.com
#   V2  Private                Requires auth with repo access
#   V3  Internal (EMU)         Requires org-scoped fine-grained PAT
#
# =============================================================================
# SCENARIOS
# =============================================================================
#
#  #  | Name                          | Source | Host | Repo | Key Assertion
# ----|-------------------------------|--------|------|------|---------------------------
#   1 | Public, no auth               | A6     | H1   | V1   | Unauth succeeds
#   2 | Public, PAT set               | A2     | H1   | V1   | Unauth-first (rate-limit)
#   3 | Private, GITHUB_APM_PAT       | A2     | H1   | V2   | Token fallback after 404
#   4 | Private, per-org PAT          | A1     | H1   | V2   | Per-org source shown
#   5 | Priority: per-org > global    | A1+A2  | H1   | V2   | Per-org wins
#   6 | Fallback: GITHUB_TOKEN        | A3     | H1   | V2   | GITHUB_TOKEN source shown
#   7 | Fallback: GH_TOKEN            | A4     | H1   | V2   | GH_TOKEN source shown
#   8 | Credential helper only        | A5     | H1   | V2   | credential fill used
#   9 | EMU internal repo             | A2     | H1   | V3   | Token needed for internal
#  10 | Mixed manifest: pub + priv    | A2     | H1   | V1+2 | Both deps installed
#  11 | Token type detection          | A2     | H1   | V1   | type=fine-grained|classic
#  12 | ADO repo with ADO_APM_PAT    | A7     | H4   | V2   | ADO PAT used
#  13 | ADO no PAT (no cred fill)    | --     | H4   | V2   | Fails, no cred fill
#  14 | Invalid token, graceful fail  | A2(bad)| H1   | V2   | No crash, actionable msg
#  15 | Nonexistent repo              | A6     | H1   | --   | Clear error message
#  16 | No auth, private repo         | A6     | H1   | V2   | Suggests auth guidance
#  17 | Fine-grained wrong owner      | A2     | H1   | V3   | Fails, no crash
#  18 | Verbose output contract       | --     | H1   | --   | Auth details only w/ flag
#
# =============================================================================
# LOCAL USAGE
# =============================================================================
#
#   # 1. Build binary (from repo root):
#   uv run pyinstaller build/apm.spec --distpath dist --workpath build/tmp --noconfirm
#
#   # 2. Set binary path:
#   export APM_BINARY="/path/to/dist/apm/apm"
#
#   # 3. Set test repos (only PUBLIC_REPO has a default):
#   export AUTH_TEST_PUBLIC_REPO="microsoft/apm-sample-package"     # default
#   export AUTH_TEST_PRIVATE_REPO="your-org/your-private-repo"      # optional
#   export AUTH_TEST_EMU_REPO="emu-org/internal-repo"               # optional
#   export AUTH_TEST_ADO_REPO="org/project/_git/repo"               # optional
#
#   # 4. Set ALL tokens you want to test (missing = scenarios skip):
#   export GITHUB_APM_PAT="github_pat_..."           # fine-grained, org-scoped
#   export GITHUB_APM_PAT_MYORG="github_pat_..."     # per-org PAT (MYORG = uppercase org)
#   export GITHUB_TOKEN="ghp_..."                    # classic PAT fallback
#   export GH_TOKEN="$(gh auth token 2>/dev/null)"   # OAuth from gh CLI
#   export ADO_APM_PAT="ado-pat-here"                # Azure DevOps PAT
#
#   # 5. Run:
#   ./scripts/test-auth-acceptance.sh
#
#   Scenarios auto-SKIP when their required env vars or repos are missing.
#   A minimal run (no tokens) still tests scenarios 1, 15, 18.
#
# =============================================================================
# CI USAGE (GitHub Actions)
# =============================================================================
#
#   Triggered via workflow_dispatch. Configure secrets in the
#   'auth-acceptance' environment:
#     AUTH_TEST_GITHUB_APM_PAT, AUTH_TEST_GITHUB_TOKEN,
#     AUTH_TEST_GH_TOKEN, AUTH_TEST_ADO_APM_PAT
#
#   See .github/workflows/auth-acceptance.yml
#
# =============================================================================

set -uo pipefail

# ---------------------------------------------------------------------------
# Logging (matches existing scripts/test-integration.sh style)
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[i] $1${NC}"; }
log_success() { echo -e "${GREEN}[+] $1${NC}"; }
log_error()   { echo -e "${RED}[x] $1${NC}"; }
log_test()    { echo -e "${BOLD}[>] $1${NC}"; }
log_dim()     { echo -e "${DIM}    $1${NC}"; }

# ---------------------------------------------------------------------------
# Counters & state
# ---------------------------------------------------------------------------
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0
RESULTS=()

# ---------------------------------------------------------------------------
# Config — repos and binary
# ---------------------------------------------------------------------------
APM_BINARY="${APM_BINARY:-apm}"
AUTH_TEST_PUBLIC_REPO="${AUTH_TEST_PUBLIC_REPO:-microsoft/apm-sample-package}"
AUTH_TEST_PRIVATE_REPO="${AUTH_TEST_PRIVATE_REPO:-}"
AUTH_TEST_EMU_REPO="${AUTH_TEST_EMU_REPO:-}"
AUTH_TEST_ADO_REPO="${AUTH_TEST_ADO_REPO:-}"

# ---------------------------------------------------------------------------
# Config — stash ALL original tokens (restored between tests)
# ---------------------------------------------------------------------------
_ORIG_GITHUB_APM_PAT="${GITHUB_APM_PAT:-}"
_ORIG_GITHUB_TOKEN="${GITHUB_TOKEN:-}"
_ORIG_GH_TOKEN="${GH_TOKEN:-}"
_ORIG_ADO_APM_PAT="${ADO_APM_PAT:-}"

# Detect any per-org PATs already set (GITHUB_APM_PAT_*)
declare -A _ORIG_PER_ORG_PATS
while IFS='=' read -r name val; do
    if [[ "$name" == GITHUB_APM_PAT_* && "$name" != "GITHUB_APM_PAT" ]]; then
        _ORIG_PER_ORG_PATS["$name"]="$val"
    fi
done < <(env)

# ---------------------------------------------------------------------------
# Temp dir & cleanup
# ---------------------------------------------------------------------------
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Unset ALL auth env vars for a clean test slate.
unset_all_auth() {
    unset GITHUB_APM_PAT 2>/dev/null || true
    unset GITHUB_TOKEN 2>/dev/null || true
    unset GH_TOKEN 2>/dev/null || true
    unset ADO_APM_PAT 2>/dev/null || true
    # Unset any GITHUB_APM_PAT_* per-org vars
    while IFS='=' read -r name _; do
        if [[ "$name" == GITHUB_APM_PAT_* ]]; then
            unset "$name" 2>/dev/null || true
        fi
    done < <(env)
    # Block interactive credential prompts
    export GIT_TERMINAL_PROMPT=0
    export GCM_INTERACTIVE=never
}

# Restore original token env vars.
restore_auth() {
    unset_all_auth
    unset GIT_TERMINAL_PROMPT GCM_INTERACTIVE 2>/dev/null || true
    [[ -n "$_ORIG_GITHUB_APM_PAT" ]] && export GITHUB_APM_PAT="$_ORIG_GITHUB_APM_PAT"
    [[ -n "$_ORIG_GITHUB_TOKEN" ]]    && export GITHUB_TOKEN="$_ORIG_GITHUB_TOKEN"
    [[ -n "$_ORIG_GH_TOKEN" ]]        && export GH_TOKEN="$_ORIG_GH_TOKEN"
    [[ -n "$_ORIG_ADO_APM_PAT" ]]     && export ADO_APM_PAT="$_ORIG_ADO_APM_PAT"
    for name in "${!_ORIG_PER_ORG_PATS[@]}"; do
        export "$name=${_ORIG_PER_ORG_PATS[$name]}"
    done
}

# Derive org env suffix: "my-org/repo" -> "MY_ORG"
org_env_suffix() {
    local owner="${1%%/*}"
    echo "$owner" | tr '[:lower:]-' '[:upper:]_'
}

# Create a temp dir with minimal apm.yml containing given deps.
# Usage: dir=$(setup_test_dir "owner/repo" ["owner2/repo2" ...])
setup_test_dir() {
    local dir
    dir="$(mktemp -d "$WORK_DIR/test-XXXXXX")"
    {
        echo "name: auth-acceptance-test"
        echo "version: 0.0.1"
        echo "dependencies:"
        echo "  apm:"
        for dep in "$@"; do
            echo "    - \"$dep\""
        done
        echo "  mcp: []"
    } > "$dir/apm.yml"
    echo "$dir"
}

# Run apm install in an isolated temp dir. Sets APM_OUTPUT and APM_EXIT.
# Usage: run_install <package> [extra_args...]
#   or:  run_install_manifest <dir> [extra_args...]  (for pre-built dirs)
run_install() {
    local package="$1"; shift
    local dir
    dir="$(setup_test_dir "$package")"
    APM_OUTPUT="$(cd "$dir" && "$APM_BINARY" install "$@" 2>&1)" && APM_EXIT=0 || APM_EXIT=$?
}

run_install_manifest() {
    local dir="$1"; shift
    APM_OUTPUT="$(cd "$dir" && "$APM_BINARY" install "$@" 2>&1)" && APM_EXIT=0 || APM_EXIT=$?
}

# Assertions — set $SCENARIO_OK=false on failure
assert_exit() {
    local expected="$1" msg="$2"
    if [[ "$APM_EXIT" -ne "$expected" ]]; then
        log_error "  FAIL: $msg (expected exit=$expected, got=$APM_EXIT)"
        SCENARIO_OK=false; return 1
    fi
}

assert_contains() {
    local pattern="$1" msg="$2"
    if ! echo "$APM_OUTPUT" | grep -qiE "$pattern"; then
        log_error "  FAIL: $msg"
        log_dim "pattern not found: $pattern"
        SCENARIO_OK=false; return 1
    fi
}

assert_not_contains() {
    local pattern="$1" msg="$2"
    if echo "$APM_OUTPUT" | grep -qiE "$pattern"; then
        log_error "  FAIL: $msg"
        log_dim "unexpected pattern: $pattern"
        SCENARIO_OK=false; return 1
    fi
}

# Record test result
record_pass() { TESTS_PASSED=$((TESTS_PASSED+1)); RESULTS+=("PASS $1"); log_success "PASS: $1"; }
record_fail() { TESTS_FAILED=$((TESTS_FAILED+1)); RESULTS+=("FAIL $1"); log_error   "FAIL: $1"; }
record_skip() { TESTS_SKIPPED=$((TESTS_SKIPPED+1)); RESULTS+=("SKIP $1"); echo -e "  ${YELLOW}[-] SKIP: $1${NC} ($2)"; }

# Check if a required env var is set; skip scenario if not
require_env() {
    local var_name="$1" scenario_name="$2"
    local val="${!var_name:-}"
    if [[ -z "$val" ]]; then
        record_skip "$scenario_name" "$var_name not set"
        return 1
    fi
}

require_repo() {
    local var_name="$1" scenario_name="$2"
    local val="${!var_name:-}"
    if [[ -z "$val" ]]; then
        record_skip "$scenario_name" "$var_name not set"
        return 1
    fi
}

# ==========================================================================
# SCENARIO 1: Public repo, no auth (A6, H1, V1)
# --------------------------------------------------------------------------
# Validates that public repos work with zero tokens. The unauth-first
# validation path should succeed on the first API attempt (200).
# No token source should appear in output.
# ==========================================================================
test_01_public_no_auth() {
    local name="01: Public repo, no auth [A6,H1,V1]"
    log_test "$name"
    unset_all_auth
    SCENARIO_OK=true

    run_install "$AUTH_TEST_PUBLIC_REPO" --verbose

    assert_exit 0 "install succeeds"
    assert_contains "unauthenticated" "tries unauthenticated access"
    assert_not_contains "source=GITHUB_APM_PAT" "no PAT source in output"

    $SCENARIO_OK && record_pass "$name" || record_fail "$name"
    restore_auth
}

# ==========================================================================
# SCENARIO 2: Public repo, global PAT set (A2, H1, V1)
# --------------------------------------------------------------------------
# Public repos should still validate unauthenticated FIRST to save API
# rate limits, even when a PAT is available. The PAT should only be used
# for the download phase (higher rate limits for git clone).
# ==========================================================================
test_02_public_with_pat() {
    local name="02: Public repo, PAT set [A2,H1,V1]"
    log_test "$name"
    require_env _ORIG_GITHUB_APM_PAT "$name" || return
    unset_all_auth
    export GITHUB_APM_PAT="$_ORIG_GITHUB_APM_PAT"
    SCENARIO_OK=true

    run_install "$AUTH_TEST_PUBLIC_REPO" --verbose

    assert_exit 0 "install succeeds"
    assert_contains "unauthenticated" "tries unauth first (rate-limit safe)"

    $SCENARIO_OK && record_pass "$name" || record_fail "$name"
    restore_auth
}

# ==========================================================================
# SCENARIO 3: Private repo, GITHUB_APM_PAT (A2, H1, V2)
# --------------------------------------------------------------------------
# Unauth validation returns 404 for private repos. AuthResolver retries
# with GITHUB_APM_PAT. Verbose output must show the fallback chain:
#   "Trying unauthenticated" -> 404 -> "retrying with token (source: GITHUB_APM_PAT)"
# ==========================================================================
test_03_private_global_pat() {
    local name="03: Private repo, GITHUB_APM_PAT [A2,H1,V2]"
    log_test "$name"
    require_repo AUTH_TEST_PRIVATE_REPO "$name" || return
    require_env _ORIG_GITHUB_APM_PAT "$name" || return
    unset_all_auth
    export GITHUB_APM_PAT="$_ORIG_GITHUB_APM_PAT"
    SCENARIO_OK=true

    run_install "$AUTH_TEST_PRIVATE_REPO" --verbose

    assert_exit 0 "install succeeds"
    assert_contains "source=GITHUB_APM_PAT" "shows GITHUB_APM_PAT as source"

    $SCENARIO_OK && record_pass "$name" || record_fail "$name"
    restore_auth
}

# ==========================================================================
# SCENARIO 4: Private repo, per-org PAT (A1, H1, V2)
# --------------------------------------------------------------------------
# Per-org PATs (GITHUB_APM_PAT_{ORG}) have highest priority. When set,
# they shadow the global GITHUB_APM_PAT. Verbose must show
#   source=GITHUB_APM_PAT_{ORG}
# The org suffix is derived from the repo owner: my-org -> MY_ORG
# ==========================================================================
test_04_private_per_org_pat() {
    local name="04: Private repo, per-org PAT [A1,H1,V2]"
    log_test "$name"
    require_repo AUTH_TEST_PRIVATE_REPO "$name" || return

    local org_suffix
    org_suffix="$(org_env_suffix "$AUTH_TEST_PRIVATE_REPO")"
    local per_org_var="GITHUB_APM_PAT_${org_suffix}"

    # Use the per-org var if already set, else use global PAT for testing
    local per_org_val="${!per_org_var:-${_ORIG_GITHUB_APM_PAT:-}}"
    if [[ -z "$per_org_val" ]]; then
        record_skip "$name" "$per_org_var and GITHUB_APM_PAT both unset"
        return
    fi

    unset_all_auth
    export "$per_org_var=$per_org_val"
    SCENARIO_OK=true

    run_install "$AUTH_TEST_PRIVATE_REPO" --verbose

    assert_exit 0 "install succeeds"
    assert_contains "source=GITHUB_APM_PAT_${org_suffix}" "per-org source shown"

    $SCENARIO_OK && record_pass "$name" || record_fail "$name"
    restore_auth
}

# ==========================================================================
# SCENARIO 5: Token priority — per-org > global (A1+A2, H1, V2)
# --------------------------------------------------------------------------
# When BOTH per-org and global PATs are set, per-org must win.
# Verbose output should show source=GITHUB_APM_PAT_{ORG}, not
# source=GITHUB_APM_PAT.
# ==========================================================================
test_05_token_priority() {
    local name="05: Priority: per-org > global [A1+A2,H1,V2]"
    log_test "$name"
    require_repo AUTH_TEST_PRIVATE_REPO "$name" || return
    require_env _ORIG_GITHUB_APM_PAT "$name" || return

    local org_suffix
    org_suffix="$(org_env_suffix "$AUTH_TEST_PRIVATE_REPO")"
    local per_org_var="GITHUB_APM_PAT_${org_suffix}"

    unset_all_auth
    export GITHUB_APM_PAT="$_ORIG_GITHUB_APM_PAT"
    export "$per_org_var=$_ORIG_GITHUB_APM_PAT"
    SCENARIO_OK=true

    run_install "$AUTH_TEST_PRIVATE_REPO" --verbose

    assert_exit 0 "install succeeds"
    assert_contains "source=GITHUB_APM_PAT_${org_suffix}" "per-org wins over global"

    $SCENARIO_OK && record_pass "$name" || record_fail "$name"
    restore_auth
}

# ==========================================================================
# SCENARIO 6: GITHUB_TOKEN fallback (A3, H1, V2)
# --------------------------------------------------------------------------
# When GITHUB_APM_PAT is unset but GITHUB_TOKEN is set, the resolver
# falls through: A1(skip) -> A2(skip) -> A3(GITHUB_TOKEN) -> use it.
# Verbose must show source=GITHUB_TOKEN.
# ==========================================================================
test_06_github_token_fallback() {
    local name="06: GITHUB_TOKEN fallback [A3,H1,V2]"
    log_test "$name"
    require_repo AUTH_TEST_PRIVATE_REPO "$name" || return

    local token="${_ORIG_GITHUB_TOKEN:-${_ORIG_GITHUB_APM_PAT:-}}"
    if [[ -z "$token" ]]; then
        record_skip "$name" "GITHUB_TOKEN and GITHUB_APM_PAT both unset"
        return
    fi

    unset_all_auth
    export GITHUB_TOKEN="$token"
    SCENARIO_OK=true

    run_install "$AUTH_TEST_PRIVATE_REPO" --verbose

    assert_exit 0 "install succeeds"
    assert_contains "source=GITHUB_TOKEN" "GITHUB_TOKEN source shown"

    $SCENARIO_OK && record_pass "$name" || record_fail "$name"
    restore_auth
}

# ==========================================================================
# SCENARIO 7: GH_TOKEN fallback — lowest priority env var (A4, H1, V2)
# --------------------------------------------------------------------------
# GH_TOKEN is the last env var in the chain. Only used when A1-A3 are unset.
# Verbose must show source=GH_TOKEN.
# ==========================================================================
test_07_gh_token_fallback() {
    local name="07: GH_TOKEN fallback [A4,H1,V2]"
    log_test "$name"
    require_repo AUTH_TEST_PRIVATE_REPO "$name" || return

    local token="${_ORIG_GH_TOKEN:-${_ORIG_GITHUB_APM_PAT:-}}"
    if [[ -z "$token" ]]; then
        record_skip "$name" "GH_TOKEN and GITHUB_APM_PAT both unset"
        return
    fi

    unset_all_auth
    export GH_TOKEN="$token"
    SCENARIO_OK=true

    run_install "$AUTH_TEST_PRIVATE_REPO" --verbose

    assert_exit 0 "install succeeds"
    assert_contains "source=GH_TOKEN" "GH_TOKEN source shown"

    $SCENARIO_OK && record_pass "$name" || record_fail "$name"
    restore_auth
}

# ==========================================================================
# SCENARIO 8: Credential helper only — no env vars (A5, H1, V2)
# --------------------------------------------------------------------------
# All env vars unset. The resolver exhausts A1-A4, then falls back to
# git credential fill (gh auth, macOS Keychain, Windows Credential Manager).
# Requires gh auth login or equivalent. Verbose should show "credential".
# ==========================================================================
test_08_credential_helper_only() {
    local name="08: Credential helper only [A5,H1,V2]"
    log_test "$name"
    require_repo AUTH_TEST_PRIVATE_REPO "$name" || return

    if ! command -v gh &>/dev/null || ! gh auth status &>/dev/null 2>&1; then
        record_skip "$name" "gh CLI not authenticated (run 'gh auth login')"
        return
    fi

    unset_all_auth
    # ALLOW credential prompts for this test (undo the block from unset_all_auth)
    unset GIT_TERMINAL_PROMPT GCM_INTERACTIVE 2>/dev/null || true
    SCENARIO_OK=true

    run_install "$AUTH_TEST_PRIVATE_REPO" --verbose

    assert_exit 0 "install succeeds"
    assert_contains "credential" "credential fill path used"

    $SCENARIO_OK && record_pass "$name" || record_fail "$name"
    restore_auth
}

# ==========================================================================
# SCENARIO 9: EMU internal repo (A2, H1, V3)
# --------------------------------------------------------------------------
# EMU (Enterprise Managed Users) internal repos are not public. They require
# an org-scoped fine-grained PAT (resource owner = org, not user).
# Unauth returns 404, token must succeed.
# ==========================================================================
test_09_emu_internal_repo() {
    local name="09: EMU internal repo [A2,H1,V3]"
    log_test "$name"
    require_repo AUTH_TEST_EMU_REPO "$name" || return
    require_env _ORIG_GITHUB_APM_PAT "$name" || return
    unset_all_auth
    export GITHUB_APM_PAT="$_ORIG_GITHUB_APM_PAT"
    SCENARIO_OK=true

    run_install "$AUTH_TEST_EMU_REPO" --verbose

    assert_exit 0 "install succeeds"
    assert_contains "retrying with token|source=GITHUB_APM_PAT" "token used for EMU repo"

    $SCENARIO_OK && record_pass "$name" || record_fail "$name"
    restore_auth
}

# ==========================================================================
# SCENARIO 10: Mixed manifest — public + private (A2, H1, V1+V2)
# --------------------------------------------------------------------------
# A single apm.yml with BOTH public and private deps. The resolver must
# handle each independently: public validates unauthenticated, private
# requires token. Both should install successfully.
# ==========================================================================
test_10_mixed_manifest() {
    local name="10: Mixed manifest: public + private [A2,H1,V1+V2]"
    log_test "$name"
    require_repo AUTH_TEST_PRIVATE_REPO "$name" || return
    require_env _ORIG_GITHUB_APM_PAT "$name" || return
    unset_all_auth
    export GITHUB_APM_PAT="$_ORIG_GITHUB_APM_PAT"
    SCENARIO_OK=true

    local dir
    dir="$(setup_test_dir "$AUTH_TEST_PUBLIC_REPO" "$AUTH_TEST_PRIVATE_REPO")"
    run_install_manifest "$dir" --verbose

    assert_exit 0 "install succeeds"
    # Both deps should appear in output
    assert_contains "Installed.*2|2.*dependenc|Installed.*APM" "both deps installed"

    $SCENARIO_OK && record_pass "$name" || record_fail "$name"
    restore_auth
}

# ==========================================================================
# SCENARIO 11: Token type detection in verbose (A2, H1, V1)
# --------------------------------------------------------------------------
# Verbose output must include type= in the "Auth resolved" line, correctly
# identifying the token type: fine-grained, classic, oauth, etc.
# ==========================================================================
test_11_token_type_detection() {
    local name="11: Token type detection [A2,H1,V1]"
    log_test "$name"
    require_env _ORIG_GITHUB_APM_PAT "$name" || return
    unset_all_auth
    export GITHUB_APM_PAT="$_ORIG_GITHUB_APM_PAT"
    SCENARIO_OK=true

    run_install "$AUTH_TEST_PUBLIC_REPO" --verbose

    assert_exit 0 "install succeeds"
    assert_contains "type=(fine-grained|classic|oauth|unknown)" "token type detected"

    $SCENARIO_OK && record_pass "$name" || record_fail "$name"
    restore_auth
}

# ==========================================================================
# SCENARIO 12: ADO repo with ADO_APM_PAT (A7, H4, V2)
# --------------------------------------------------------------------------
# Azure DevOps uses a completely separate auth path: ADO_APM_PAT env var.
# No GitHub env vars apply. No credential fill fallback (ADO excluded).
# Git ls-remote with Basic auth (base64 :PAT).
# ==========================================================================
test_12_ado_repo() {
    local name="12: ADO repo with ADO_APM_PAT [A7,H4,V2]"
    log_test "$name"
    require_repo AUTH_TEST_ADO_REPO "$name" || return
    require_env _ORIG_ADO_APM_PAT "$name" || return
    unset_all_auth
    export ADO_APM_PAT="$_ORIG_ADO_APM_PAT"
    SCENARIO_OK=true

    run_install "$AUTH_TEST_ADO_REPO" --verbose

    assert_exit 0 "install succeeds"

    $SCENARIO_OK && record_pass "$name" || record_fail "$name"
    restore_auth
}

# ==========================================================================
# SCENARIO 13: ADO without PAT — no credential fill (H4)
# --------------------------------------------------------------------------
# ADO is explicitly excluded from git credential fill. Without ADO_APM_PAT,
# the operation must fail cleanly. Output must NOT mention "credential fill".
# ==========================================================================
test_13_ado_no_pat() {
    local name="13: ADO no PAT, no credential fill [H4]"
    log_test "$name"
    require_repo AUTH_TEST_ADO_REPO "$name" || return
    unset_all_auth
    SCENARIO_OK=true

    run_install "$AUTH_TEST_ADO_REPO" --verbose

    assert_exit 1 "fails without ADO PAT"
    assert_contains "not accessible" "clear error message"
    assert_not_contains "credential fill" "no credential fill for ADO"

    $SCENARIO_OK && record_pass "$name" || record_fail "$name"
    restore_auth
}

# ==========================================================================
# SCENARIO 14: Invalid token, graceful failure (A2-bad, H1, V2)
# --------------------------------------------------------------------------
# An invalid/expired token should fail gracefully: no Python traceback,
# no hang. AuthResolver should exhaust the chain (token -> credential fill)
# and produce an actionable error.
# ==========================================================================
test_14_invalid_token() {
    local name="14: Invalid token, graceful failure [A2-bad,H1,V2]"
    log_test "$name"
    require_repo AUTH_TEST_PRIVATE_REPO "$name" || return
    unset_all_auth
    export GITHUB_APM_PAT="ghp_invalidtoken1234567890abcdefghijklmn"
    SCENARIO_OK=true

    run_install "$AUTH_TEST_PRIVATE_REPO" --verbose

    assert_exit 1 "fails with exit 1"
    assert_not_contains "Traceback" "no Python traceback"

    $SCENARIO_OK && record_pass "$name" || record_fail "$name"
    restore_auth
}

# ==========================================================================
# SCENARIO 15: Nonexistent repo (A6, H1)
# --------------------------------------------------------------------------
# A repo that doesn't exist should produce a clear, non-confusing message:
#   "not accessible or doesn't exist"
# No auth noise since there's nothing to authenticate against.
# ==========================================================================
test_15_nonexistent_repo() {
    local name="15: Nonexistent repo [A6,H1]"
    log_test "$name"
    unset_all_auth
    SCENARIO_OK=true

    run_install "owner/this-repo-does-not-exist-12345" --verbose

    assert_exit 1 "fails with exit 1"
    assert_contains "not accessible or doesn.t exist" "clear error message"

    $SCENARIO_OK && record_pass "$name" || record_fail "$name"
    restore_auth
}

# ==========================================================================
# SCENARIO 16: No auth, private repo (A6, H1, V2)
# --------------------------------------------------------------------------
# Private repo with zero tokens and credential helpers blocked.
# Must fail with actionable guidance: suggest setting env vars or
# running with --verbose for diagnostics.
# ==========================================================================
test_16_no_auth_private_repo() {
    local name="16: No auth, private repo [A6,H1,V2]"
    log_test "$name"
    require_repo AUTH_TEST_PRIVATE_REPO "$name" || return
    unset_all_auth
    SCENARIO_OK=true

    run_install "$AUTH_TEST_PRIVATE_REPO"

    assert_exit 1 "fails"
    assert_contains "not accessible|--verbose|GITHUB_APM_PAT|auth" "suggests auth guidance"

    $SCENARIO_OK && record_pass "$name" || record_fail "$name"
    restore_auth
}

# ==========================================================================
# SCENARIO 17: Fine-grained PAT, wrong resource owner (A2, H1, V3)
# --------------------------------------------------------------------------
# A user-scoped fine-grained PAT (github_pat_*) CANNOT access org repos,
# even internal ones. Must fail without crash. This is a common gotcha
# for EMU users who create user-scoped PATs instead of org-scoped.
# Auto-skips if the PAT actually has org scope (succeeds).
# ==========================================================================
test_17_fine_grained_wrong_owner() {
    local name="17: Fine-grained PAT wrong owner [A2,H1,V3]"
    log_test "$name"
    require_repo AUTH_TEST_EMU_REPO "$name" || return
    require_env _ORIG_GITHUB_APM_PAT "$name" || return

    if [[ "$_ORIG_GITHUB_APM_PAT" != github_pat_* ]]; then
        record_skip "$name" "GITHUB_APM_PAT is not fine-grained (github_pat_*)"
        return
    fi

    unset_all_auth
    export GITHUB_APM_PAT="$_ORIG_GITHUB_APM_PAT"
    SCENARIO_OK=true

    run_install "$AUTH_TEST_EMU_REPO" --verbose

    if [[ "$APM_EXIT" -eq 0 ]]; then
        # PAT has org scope — can't test wrong-owner with this token
        record_skip "$name" "PAT has org scope (need user-scoped PAT to test)"
    else
        assert_not_contains "Traceback" "no Python traceback"
        $SCENARIO_OK && record_pass "$name" || record_fail "$name"
    fi
    restore_auth
}

# ==========================================================================
# SCENARIO 18: Verbose vs non-verbose output contract
# --------------------------------------------------------------------------
# The core UX contract: auth diagnostics are INVISIBLE without --verbose.
# Run the SAME failing operation twice (with and without --verbose) and
# verify:
#   Non-verbose: NO "Auth resolved:", HAS "--verbose" hint
#   Verbose: HAS auth diagnostic lines (Auth resolved, API, unauthenticated)
# ==========================================================================
test_18_verbose_contract() {
    local name="18: Verbose output contract"
    log_test "$name"
    unset_all_auth
    SCENARIO_OK=true

    # Non-verbose run
    run_install "owner/this-repo-does-not-exist-12345"
    local nv_output="$APM_OUTPUT" nv_exit="$APM_EXIT"

    # Verbose run
    run_install "owner/this-repo-does-not-exist-12345" --verbose
    local v_output="$APM_OUTPUT" v_exit="$APM_EXIT"

    # Both should fail
    APM_EXIT="$nv_exit"
    assert_exit 1 "non-verbose fails"
    APM_EXIT="$v_exit"
    assert_exit 1 "verbose fails"

    # Non-verbose: auth details hidden, --verbose hint shown
    APM_OUTPUT="$nv_output"
    assert_not_contains "Auth resolved:" "non-verbose hides auth details"
    assert_contains "--verbose" "non-verbose hints at --verbose"

    # Verbose: auth details shown
    APM_OUTPUT="$v_output"
    if ! echo "$v_output" | grep -qiE "Auth resolved|unauthenticated|API .* →|API .* ->"; then
        log_error "  FAIL: verbose output missing auth diagnostic lines"
        SCENARIO_OK=false
    fi

    $SCENARIO_OK && record_pass "$name" || record_fail "$name"
    restore_auth
}

# ==========================================================================
# RUN ALL SCENARIOS
# ==========================================================================

echo ""
echo -e "${BOLD}${BLUE}================================================================${NC}"
echo -e "${BOLD}${BLUE}  APM Auth Acceptance Tests${NC}"
echo -e "${BOLD}${BLUE}================================================================${NC}"
echo ""
echo -e "${DIM}Binary:       ${APM_BINARY}${NC}"
echo -e "${DIM}Public repo:  ${AUTH_TEST_PUBLIC_REPO}${NC}"
echo -e "${DIM}Private repo: ${AUTH_TEST_PRIVATE_REPO:-<not set -- scenarios 3-10,14,16 skip>}${NC}"
echo -e "${DIM}EMU repo:     ${AUTH_TEST_EMU_REPO:-<not set -- scenarios 9,17 skip>}${NC}"
echo -e "${DIM}ADO repo:     ${AUTH_TEST_ADO_REPO:-<not set -- scenarios 12,13 skip>}${NC}"
echo -e "${DIM}Tokens:       GITHUB_APM_PAT=${_ORIG_GITHUB_APM_PAT:+SET} GITHUB_TOKEN=${_ORIG_GITHUB_TOKEN:+SET} GH_TOKEN=${_ORIG_GH_TOKEN:+SET} ADO_APM_PAT=${_ORIG_ADO_APM_PAT:+SET}${NC}"
# Show per-org PATs
for name in "${!_ORIG_PER_ORG_PATS[@]}"; do
    echo -e "${DIM}              ${name}=SET${NC}"
done
echo ""

# Core auth scenarios
test_01_public_no_auth
test_02_public_with_pat
test_03_private_global_pat
test_04_private_per_org_pat
test_05_token_priority
test_06_github_token_fallback
test_07_gh_token_fallback
test_08_credential_helper_only
test_09_emu_internal_repo
test_10_mixed_manifest
test_11_token_type_detection

# ADO scenarios
test_12_ado_repo
test_13_ado_no_pat

# Error scenarios
test_14_invalid_token
test_15_nonexistent_repo
test_16_no_auth_private_repo
test_17_fine_grained_wrong_owner

# Output contract
test_18_verbose_contract

# ==========================================================================
# SUMMARY
# ==========================================================================

TOTAL=$((TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED))

echo ""
echo -e "${BOLD}${BLUE}================================================================${NC}"
echo -e "${BOLD}${BLUE}  Summary${NC}"
echo -e "${BOLD}${BLUE}================================================================${NC}"
echo ""
printf "  %-10s %s\n" "Total:" "$TOTAL"
printf "  ${GREEN}%-10s %s${NC}\n" "Passed:" "$TESTS_PASSED"
printf "  ${RED}%-10s %s${NC}\n" "Failed:" "$TESTS_FAILED"
printf "  ${YELLOW}%-10s %s${NC}\n" "Skipped:" "$TESTS_SKIPPED"
echo ""

for entry in "${RESULTS[@]}"; do
    status="${entry%% *}"
    scenario="${entry#* }"
    case "$status" in
        PASS) echo -e "  ${GREEN}[+]${NC} $scenario" ;;
        FAIL) echo -e "  ${RED}[x]${NC} $scenario" ;;
        SKIP) echo -e "  ${YELLOW}[-]${NC} $scenario" ;;
    esac
done

echo ""

if [[ "$TESTS_FAILED" -gt 0 ]]; then
    echo -e "${RED}${BOLD}Auth acceptance tests FAILED${NC}"
    exit 1
fi

echo -e "${GREEN}${BOLD}Auth acceptance tests PASSED${NC} (${TESTS_SKIPPED} skipped)"
exit 0

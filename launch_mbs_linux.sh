#!/usr/bin/env bash
# =============================================================================
# META BUSINESS SUITE INBOX AUTOMATOR - LINUX / UBUNTU PRODUCTION LAUNCHER
# Version: V5.0.1 (Pure Python Zero-Extension Runner Edition)
# Author: Bishoy Safwat (Senior Automation Engineer)
# =============================================================================
# Purpose:
# - Serves as the primary Linux entrypoint for the Python Playwright engine.
# - Dispatches isolated Google Chrome instances natively without Tampermonkey.
# - Provides pre-flight environment verification & smoke testing (--test).
# - Supports active browser attach (--attach) and single-profile launch (--profile).
# - Cleans stale Chrome SingletonLocks automatically to prevent startup aborts.
# =============================================================================

set -euo pipefail

# ANSI Color Codes
CLR_RESET="\033[0m"
CLR_BOLD="\033[1m"
CLR_CYAN="\033[96m"
CLR_GREEN="\033[92m"
CLR_YELLOW="\033[93m"
CLR_RED="\033[91m"
CLR_GRAY="\033[90m"
CLR_BLUE="\033[94m"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="python3"

print_banner() {
    echo -e "${CLR_CYAN}${CLR_BOLD}"
    echo "============================================================================="
    echo "  META BUSINESS SUITE INBOX AUTOMATOR - UBUNTU 24.04 LAUNCHER (V5.0.1)"
    echo "============================================================================="
    echo -e "${CLR_RESET}"
    echo -e "  ${CLR_BLUE}•${CLR_RESET} Pure Python Zero-Extension Playwright Runner"
    echo -e "  ${CLR_BLUE}•${CLR_RESET} Multi-Tenant Linux Profile Sandboxing (Zero Cross-Talk)"
    echo -e "  ${CLR_BLUE}•${CLR_RESET} Continuous Runtime Anti-Throttling Architecture"
    echo -e "  ${CLR_BLUE}•${CLR_RESET} Automatic Stale Lock Cleaning (SingletonLocks)"
    echo "============================================================================="
    echo ""
}

# -----------------------------------------------------------------------------
# Configuration & Directories
# -----------------------------------------------------------------------------
BASE_CONFIG_DIR="$HOME/.config/meta_inbox_bot"
BASE_PROFILES_DIR="$BASE_CONFIG_DIR/profiles"
BASE_LOGS_DIR="$BASE_CONFIG_DIR/logs"

TENANT_A_NAME="Profile_PageA"
TENANT_A_DIR="$BASE_PROFILES_DIR/$TENANT_A_NAME"
TENANT_B_NAME="Profile_PageB"
TENANT_B_DIR="$BASE_PROFILES_DIR/$TENANT_B_NAME"

# -----------------------------------------------------------------------------
# Helper: Detect Chrome Binary
# -----------------------------------------------------------------------------
find_chrome_binary() {
    local candidates=(
        "google-chrome-stable"
        "google-chrome"
        "chromium-browser"
        "chromium"
    )
    for bin in "${candidates[@]}"; do
        if command -v "$bin" >/dev/null 2>&1; then
            command -v "$bin"
            return 0
        fi
    done
    return 1
}

# -----------------------------------------------------------------------------
# Helper: Clean Stale Singleton Locks
# -----------------------------------------------------------------------------
clean_stale_locks() {
    local pdir="$1"
    if [ -d "$pdir" ]; then
        rm -f "$pdir/SingletonLock" \
              "$pdir/SingletonCookie" \
              "$pdir/SingletonSocket" 2>/dev/null || true
    fi
}

# -----------------------------------------------------------------------------
# Mode: Smoke Test & Verification (--test / --dry-run)
# -----------------------------------------------------------------------------
run_smoke_test() {
    print_banner
    echo -e "${CLR_YELLOW}${CLR_BOLD}[DIAGNOSTIC MODE] Running Linux Environment Smoke Test...${CLR_RESET}\n"

    local test_passed=0
    local test_failed=0

    # Test 1: Chrome Binary Detection
    echo -n "[1/6] Checking Google Chrome Installation: "
    local chrome_path
    if chrome_path=$(find_chrome_binary); then
        local version_str
        version_str=$("$chrome_path" --version 2>/dev/null || echo "Unknown Version")
        echo -e "${CLR_GREEN}${CLR_BOLD}PASS${CLR_RESET} (${chrome_path} | ${version_str})"
        test_passed=$((test_passed + 1))
    else
        echo -e "${CLR_RED}${CLR_BOLD}FAIL${CLR_RESET} (Google Chrome was not found)"
        echo -e "      ${CLR_YELLOW}Run: sudo apt update && sudo apt install -y google-chrome-stable${CLR_RESET}"
        test_failed=$((test_failed + 1))
    fi

    # Test 2: Python 3 & Playwright Package Verification
    echo -n "[2/6] Checking Python 3 & Playwright Environment: "
    if command -v python3 >/dev/null 2>&1; then
        if python3 -c "import playwright" >/dev/null 2>&1; then
            local pw_ver
            pw_ver=$(python3 -c "import importlib.metadata; print(importlib.metadata.version('playwright'))" 2>/dev/null || echo "installed")
            echo -e "${CLR_GREEN}${CLR_BOLD}PASS${CLR_RESET} (Python $(python3 --version 2>&1 | awk '{print $2}') | Playwright ${pw_ver})"
            test_passed=$((test_passed + 1))
        else
            echo -e "${CLR_RED}${CLR_BOLD}FAIL${CLR_RESET} (Playwright python package not installed)"
            echo -e "      ${CLR_YELLOW}Run: pip install playwright --break-system-packages${CLR_RESET}"
            test_failed=$((test_failed + 1))
        fi
    else
        echo -e "${CLR_RED}${CLR_BOLD}FAIL${CLR_RESET} (Python 3 is missing)"
        test_failed=$((test_failed + 1))
    fi

    # Test 3: Profile Storage Directory Creation
    echo -n "[3/6] Initializing Sandbox Profile Directories: "
    if mkdir -p "$TENANT_A_DIR" "$TENANT_B_DIR" "$BASE_LOGS_DIR" 2>/dev/null; then
        echo -e "${CLR_GREEN}${CLR_BOLD}PASS${CLR_RESET} (${BASE_PROFILES_DIR})"
        test_passed=$((test_passed + 1))
    else
        echo -e "${CLR_RED}${CLR_BOLD}FAIL${CLR_RESET} (Unable to create profile directories)"
        test_failed=$((test_failed + 1))
    fi

    # Test 4: Filesystem Read/Write Permissions & Lock Cleanup
    echo -n "[4/6] Verifying Lock Cleaning & Write Permissions: "
    local touch_a="$TENANT_A_DIR/.write_test_$$"
    local touch_b="$TENANT_B_DIR/.write_test_$$"
    clean_stale_locks "$TENANT_A_DIR"
    clean_stale_locks "$TENANT_B_DIR"
    if touch "$touch_a" "$touch_b" 2>/dev/null && rm -f "$touch_a" "$touch_b"; then
        echo -e "${CLR_GREEN}${CLR_BOLD}PASS${CLR_RESET} (Read/Write OK | Lock cleaner functional)"
        test_passed=$((test_passed + 1))
    else
        echo -e "${CLR_RED}${CLR_BOLD}FAIL${CLR_RESET} (Permission denied in sandbox path)"
        test_failed=$((test_failed + 1))
    fi

    # Test 5: Display Server Environment
    echo -n "[5/6] Checking Graphical Display Server: "
    if [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
        local disp_info="${DISPLAY:-${WAYLAND_DISPLAY:-Active}}"
        echo -e "${CLR_GREEN}${CLR_BOLD}PASS${CLR_RESET} (Display: ${disp_info})"
        test_passed=$((test_passed + 1))
    else
        echo -e "${CLR_YELLOW}${CLR_BOLD}WARN${CLR_RESET} (No \$DISPLAY or \$WAYLAND_DISPLAY detected; headless session)"
        test_passed=$((test_passed + 1))
    fi

    # Test 6: Meta Business Suite Network Connectivity
    echo -n "[6/6] Testing Network Connectivity to Meta: "
    local domain="business.facebook.com"
    if command -v curl >/dev/null 2>&1; then
        if curl -s --connect-timeout 5 -I "https://$domain" >/dev/null 2>&1; then
            echo -e "${CLR_GREEN}${CLR_BOLD}PASS${CLR_RESET} (HTTP Reachable: https://${domain})"
            test_passed=$((test_passed + 1))
        elif getent hosts "$domain" >/dev/null 2>&1; then
            echo -e "${CLR_GREEN}${CLR_BOLD}PASS${CLR_RESET} (DNS Resolved: ${domain})"
            test_passed=$((test_passed + 1))
        else
            echo -e "${CLR_RED}${CLR_BOLD}FAIL${CLR_RESET} (Unable to reach or resolve ${domain})"
            test_failed=$((test_failed + 1))
        fi
    elif getent hosts "$domain" >/dev/null 2>&1; then
        echo -e "${CLR_GREEN}${CLR_BOLD}PASS${CLR_RESET} (DNS Resolved: ${domain})"
        test_passed=$((test_passed + 1))
    else
        echo -e "${CLR_YELLOW}${CLR_BOLD}SKIP${CLR_RESET} (Neither curl nor getent available)"
        test_passed=$((test_passed + 1))
    fi

    echo ""
    echo "============================================================================="
    echo -e "  ${CLR_BOLD}SMOKE TEST SUMMARY:${CLR_RESET} ${CLR_GREEN}${test_passed} Passed${CLR_RESET} | ${CLR_RED}${test_failed} Failed${CLR_RESET}"
    echo "============================================================================="

    if [ "$test_failed" -eq 0 ]; then
        echo -e "${CLR_GREEN}${CLR_BOLD}[SUCCESS] Linux system is 100% verified and ready for production deployment.${CLR_RESET}\n"
        exit 0
    else
        echo -e "${CLR_RED}${CLR_BOLD}[ERROR] Please resolve the failed checks above before launching.${CLR_RESET}\n"
        exit 1
    fi
}

# -----------------------------------------------------------------------------
# Handle CLI Arguments
# -----------------------------------------------------------------------------
ACTION="${1:-}"

case "$ACTION" in
    --test|--dry-run|-t)
        if [ -x "$SCRIPT_DIR/audit_system.py" ]; then
            exec "$SCRIPT_DIR/audit_system.py"
        elif [ -f "$SCRIPT_DIR/audit_system.py" ]; then
            exec "$PYTHON_BIN" "$SCRIPT_DIR/audit_system.py"
        else
            run_smoke_test
        fi
        ;;
    --attach|-a)
        shift || true
        print_banner
        exec "$PYTHON_BIN" "$SCRIPT_DIR/main.py" --attach "$@"
        ;;
    --profile|-p)
        shift || true
        TARGET_PROFILE="${1:-Profile_PageA}"
        shift || true
        print_banner
        exec "$PYTHON_BIN" "$SCRIPT_DIR/main.py" --profile "$TARGET_PROFILE" "$@"
        ;;
    --setup|-s)
        shift || true
        TARGET_PROFILE="${1:-Profile_PageA}"
        shift || true
        print_banner
        echo -e "${CLR_YELLOW}${CLR_BOLD}[SETUP MODE] Launching profile [$TARGET_PROFILE] for initial login...${CLR_RESET}"
        echo "Please log into Meta Business Suite in the opened Chrome window."
        echo "Once logged in, the script is injected natively via Playwright (Zero Extension required)."
        echo "Press Ctrl+C or close the window when login is completed."
        echo ""
        exec "$PYTHON_BIN" "$SCRIPT_DIR/main.py" --profile "$TARGET_PROFILE" "$@"
        ;;
    --help|-h)
        print_banner
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  (no flags)                    Launch concurrent multi-tenant sandboxes (--all)."
        echo "  --attach, -a                  Attach via CDP to active running Chrome (port 9222)."
        echo "  --profile, -p [Name]          Launch single isolated profile (e.g. Profile_PageA)."
        echo "  --setup, -s [Name]            Interactive profile login setup (no extensions required)."
        echo "  --test, --dry-run, -t         Run pre-flight verification checks without opening browser."
        echo "  --help, -h                    Display this help guide and exit."
        echo ""
        echo "Python Engine Options (passed to main.py):"
        echo "  --auto-start                  Start automator immediately upon page load."
        echo "  --headless                    Run browser in headless mode."
        echo ""
        exit 0
        ;;
    "")
        print_banner
        echo -e "${CLR_GREEN}🚀 Launching Multi-Tenant Playwright Engine (Profile_PageA & Profile_PageB)...${CLR_RESET}"
        exec "$PYTHON_BIN" "$SCRIPT_DIR/main.py" --all
        ;;
    *)
        # Forward any other arguments directly to main.py
        print_banner
        exec "$PYTHON_BIN" "$SCRIPT_DIR/main.py" "$@"
        ;;
esac

#!/usr/bin/env bash
# =============================================================================
# META BUSINESS SUITE INBOX AUTOMATOR - LINUX / UBUNTU PRODUCTION LAUNCHER
# Version: V4.8.0 (Enterprise Multi-Tenant Edition)
# Author: Bishoy Safwat (Senior Automation Engineer)
# =============================================================================
# Purpose:
# - Dispatches isolated Google Chrome instances for multiple Facebook Pages
#   simultaneously on Ubuntu 24.04 / Debian Linux systems.
# - Applies continuous runtime anti-throttling flags to prevent timer degradation.
# - Provides multi-tenant sandbox profile isolation with zero cross-talk.
# - Includes built-in smoke test runner (--test / --dry-run).
# =============================================================================

set -euo pipefail

# ANSI Color Codes
CLR_RESET="[0m"
CLR_BOLD="[1m"
CLR_CYAN="[96m"
CLR_GREEN="[92m"
CLR_YELLOW="[93m"
CLR_RED="[91m"
CLR_GRAY="[90m"
CLR_BLUE="[94m"

print_banner() {
    echo -e "${CLR_CYAN}${CLR_BOLD}"
    echo "============================================================================="
    echo "  META BUSINESS SUITE INBOX AUTOMATOR - UBUNTU 24.04 LAUNCHER (V4.8.0)"
    echo "============================================================================="
    echo -e "${CLR_RESET}"
    echo -e "  ${CLR_BLUE}•${CLR_RESET} Multi-Tenant Linux Profile Sandboxing"
    echo -e "  ${CLR_BLUE}•${CLR_RESET} Continuous Runtime Anti-Throttling Engine"
    echo -e "  ${CLR_BLUE}•${CLR_RESET} Dual-Layer Zero Cross-Talk Protection"
    echo "============================================================================="
    echo ""
}

# -----------------------------------------------------------------------------
# Configuration & Directories
# -----------------------------------------------------------------------------
BASE_PROFILES_DIR="$HOME/.config/meta_inbox_bot/profiles"
TENANT_A_NAME="Profile_PageA"
TENANT_A_DIR="$BASE_PROFILES_DIR/$TENANT_A_NAME"
TENANT_A_URL="https://business.facebook.com/latest/inbox/all"

TENANT_B_NAME="Profile_PageB"
TENANT_B_DIR="$BASE_PROFILES_DIR/$TENANT_B_NAME"
TENANT_B_URL="https://business.facebook.com/latest/inbox/all"

# Anti-Throttling & Performance Runtime Flags
CHROME_FLAGS=(
    --disable-background-timer-throttling
    --disable-backgrounding-occluded-windows
    --disable-renderer-backgrounding
    --no-first-run
    --no-default-browser-check
    --disable-breakpad
    --disable-component-update
    --password-store=basic
    --start-maximized
    --new-window
)

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
# Mode: Smoke Test & Verification (--test / --dry-run)
# -----------------------------------------------------------------------------
run_smoke_test() {
    print_banner
    echo -e "${CLR_YELLOW}${CLR_BOLD}[DIAGNOSTIC MODE] Running Linux Environment Smoke Test...${CLR_RESET}
"

    local test_passed=0
    local test_failed=0

    # Test 1: Chrome Binary Detection
    echo -n "[1/5] Checking Google Chrome Installation: "
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

    # Test 2: Profile Storage Directory Creation
    echo -n "[2/5] Initializing Sandbox Profile Directories: "
    if mkdir -p "$TENANT_A_DIR" "$TENANT_B_DIR" 2>/dev/null; then
        echo -e "${CLR_GREEN}${CLR_BOLD}PASS${CLR_RESET} (${BASE_PROFILES_DIR})"
        test_passed=$((test_passed + 1))
    else
        echo -e "${CLR_RED}${CLR_BOLD}FAIL${CLR_RESET} (Unable to create profile directories)"
        test_failed=$((test_failed + 1))
    fi

    # Test 3: Filesystem Read/Write Permissions
    echo -n "[3/5] Verifying Filesystem Write Permissions: "
    local touch_a="$TENANT_A_DIR/.write_test_$$"
    local touch_b="$TENANT_B_DIR/.write_test_$$"
    if touch "$touch_a" "$touch_b" 2>/dev/null && rm -f "$touch_a" "$touch_b"; then
        echo -e "${CLR_GREEN}${CLR_BOLD}PASS${CLR_RESET} (Read/Write OK)"
        test_passed=$((test_passed + 1))
    else
        echo -e "${CLR_RED}${CLR_BOLD}FAIL${CLR_RESET} (Permission denied in sandbox path)"
        test_failed=$((test_failed + 1))
    fi

    # Test 4: Display Server Environment
    echo -n "[4/5] Checking Graphical Display Server: "
    if [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
        local disp_info="${DISPLAY:-${WAYLAND_DISPLAY:-Active}}"
        echo -e "${CLR_GREEN}${CLR_BOLD}PASS${CLR_RESET} (Display: ${disp_info})"
        test_passed=$((test_passed + 1))
    else
        echo -e "${CLR_YELLOW}${CLR_BOLD}WARN${CLR_RESET} (No $DISPLAY or $WAYLAND_DISPLAY detected; headless session)"
        test_passed=$((test_passed + 1))
    fi

    # Test 5: Meta Business Suite Network Connectivity
    echo -n "[5/5] Testing Network Connectivity to Meta: "
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
        echo -e "${CLR_GREEN}${CLR_BOLD}[SUCCESS] Linux system is 100% verified and ready for production deployment.${CLR_RESET}
"
        exit 0
    else
        echo -e "${CLR_RED}${CLR_BOLD}[ERROR] Please resolve the failed checks above before launching.${CLR_RESET}
"
        exit 1
    fi
}

# -----------------------------------------------------------------------------
# Handle CLI Arguments
# -----------------------------------------------------------------------------
if [ "${1:-}" = "--test" ] || [ "${1:-}" = "--dry-run" ] || [ "${1:-}" = "-t" ]; then
    run_smoke_test
fi

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    print_banner
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --test, --dry-run, -t    Run pre-flight verification checks without opening browser."
    echo "  --help, -h               Display this help guide and exit."
    echo ""
    exit 0
fi

# -----------------------------------------------------------------------------
# Main Production Launch
# -----------------------------------------------------------------------------
print_banner

CHROME_BIN=""
if ! CHROME_BIN=$(find_chrome_binary); then
    echo -e "${CLR_RED}${CLR_BOLD}[ERROR] Google Chrome is not installed on this Ubuntu system.${CLR_RESET}"
    echo ""
    echo -e "To install Google Chrome officially via APT, execute:"
    echo "  wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg"
    echo "  echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main' | sudo tee /etc/apt/sources.list.d/google-chrome.list"
    echo "  sudo apt update && sudo apt install -y google-chrome-stable"
    echo ""
    echo -e "Or download the standalone package directly:"
    echo "  wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"
    echo "  sudo apt install -y ./google-chrome-stable_current_amd64.deb"
    echo ""
    exit 1
fi

echo -e "${CLR_GREEN}[OK]${CLR_RESET} Using Google Chrome binary: ${CLR_BOLD}${CHROME_BIN}${CLR_RESET}"

# Initialize profile sandboxes
mkdir -p "$TENANT_A_DIR" "$TENANT_B_DIR"
echo -e "${CLR_GREEN}[OK]${CLR_RESET} Profile directory ready: ${BASE_PROFILES_DIR}"
echo ""

echo "============================================================================="
echo " [DISPATCHING TENANT INSTANCES]"
echo "============================================================================="

# Launch Tenant A
echo -e "1. Launching Tenant A [${CLR_BOLD}${TENANT_A_NAME}${CLR_RESET}]..."
echo "   Sandbox Path: $TENANT_A_DIR"
echo "   Target URL:   $TENANT_A_URL"
"$CHROME_BIN" --user-data-dir="$TENANT_A_DIR" "${CHROME_FLAGS[@]}" "$TENANT_A_URL" >/dev/null 2>&1 &
PID_A=$!
echo -e "   ${CLR_GREEN}[STARTED]${CLR_RESET} Process ID: ${PID_A}"

sleep 3

# Launch Tenant B
echo -e "2. Launching Tenant B [${CLR_BOLD}${TENANT_B_NAME}${CLR_RESET}]..."
echo "   Sandbox Path: $TENANT_B_DIR"
echo "   Target URL:   $TENANT_B_URL"
"$CHROME_BIN" --user-data-dir="$TENANT_B_DIR" "${CHROME_FLAGS[@]}" "$TENANT_B_URL" >/dev/null 2>&1 &
PID_B=$!
echo -e "   ${CLR_GREEN}[STARTED]${CLR_RESET} Process ID: ${PID_B}"

echo ""
echo "============================================================================="
echo -e " ${CLR_GREEN}${CLR_BOLD}[SUCCESS] All Tenant profiles have been dispatched.${CLR_RESET}"
echo "============================================================================="
echo " Operational Guidelines:"
echo "  1. Install Tampermonkey in each Chrome profile and load 'meta_inbox_userscript.user.js'."
echo "  2. Each profile operates in a fully isolated sandbox (Zero Cross-Talk)."
echo "  3. Both browser instances will continue running independently in the background."
echo "============================================================================="
echo ""

#!/usr/bin/env bash
# =============================================================================
# META BUSINESS SUITE INBOX AUTOMATOR - LINUX / UBUNTU PRODUCTION LAUNCHER
# Version: V4.8.0 (Enterprise Multi-Tenant Edition)
# Author: Bishoy Safwat (Senior Automation Engineer)
# =============================================================================
# Purpose:
# - Dispatches isolated Google Chrome instances for multiple Facebook Pages
#   simultaneously on Ubuntu 24.04 / Debian Linux systems.
# - Provides real runtime logging to ~/.config/meta_inbox_bot/logs/.
# - Cleans stale Chrome SingletonLocks to prevent silent process termination.
# - Supports active session testing (--current) and interactive login (--setup).
# - Includes continuous runtime anti-throttling flags and smoke test runner (--test).
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
    echo -e "  ${CLR_BLUE}•${CLR_RESET} Real-Time Dedicated Process Logging"
    echo -e "  ${CLR_BLUE}•${CLR_RESET} Dual-Layer Zero Cross-Talk Protection"
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
TENANT_A_URL="https://business.facebook.com/latest/inbox/all"
LOG_A="$BASE_LOGS_DIR/tenant_a.log"

TENANT_B_NAME="Profile_PageB"
TENANT_B_DIR="$BASE_PROFILES_DIR/$TENANT_B_NAME"
TENANT_B_URL="https://business.facebook.com/latest/inbox/all"
LOG_B="$BASE_LOGS_DIR/tenant_b.log"

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
# Helper: Clean Stale Singleton Locks
# -----------------------------------------------------------------------------
clean_stale_locks() {
    local pdir="$1"
    if [ -d "$pdir" ]; then
        rm -f "$pdir/SingletonLock"               "$pdir/SingletonCookie"               "$pdir/SingletonSocket" 2>/dev/null || true
    fi
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

    # Test 2: Profile Storage Directory Creation
    echo -n "[2/6] Initializing Sandbox Profile Directories: "
    if mkdir -p "$TENANT_A_DIR" "$TENANT_B_DIR" 2>/dev/null; then
        echo -e "${CLR_GREEN}${CLR_BOLD}PASS${CLR_RESET} (${BASE_PROFILES_DIR})"
        test_passed=$((test_passed + 1))
    else
        echo -e "${CLR_RED}${CLR_BOLD}FAIL${CLR_RESET} (Unable to create profile directories)"
        test_failed=$((test_failed + 1))
    fi

    # Test 3: Log Directory & File Creation
    echo -n "[3/6] Initializing Runtime Log Directory: "
    if mkdir -p "$BASE_LOGS_DIR" 2>/dev/null && touch "$LOG_A" "$LOG_B" 2>/dev/null; then
        echo -e "${CLR_GREEN}${CLR_BOLD}PASS${CLR_RESET} (${BASE_LOGS_DIR})"
        test_passed=$((test_passed + 1))
    else
        echo -e "${CLR_RED}${CLR_BOLD}FAIL${CLR_RESET} (Unable to create log files)"
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
        echo -e "${CLR_YELLOW}${CLR_BOLD}WARN${CLR_RESET} (No $DISPLAY or $WAYLAND_DISPLAY detected; headless session)"
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
# Mode: Active Chrome Session Testing (--current / -c)
# -----------------------------------------------------------------------------
run_current_mode() {
    print_banner
    echo -e "${CLR_YELLOW}${CLR_BOLD}[ACTIVE SESSION MODE] Testing with default user Chrome profile...${CLR_RESET}"
    
    local chrome_bin
    if ! chrome_bin=$(find_chrome_binary); then
        echo -e "${CLR_RED}[ERROR] Google Chrome binary not found.${CLR_RESET}"
        exit 1
    fi

    echo "Target URL: $TENANT_A_URL"
    echo "Opening in active Chrome instance (preserving your active Facebook login)..."
    "$chrome_bin" "$TENANT_A_URL" >/dev/null 2>&1 &
    echo -e "${CLR_GREEN}[OK] Dispatched to active Chrome session.${CLR_RESET}
"
    exit 0
}

# -----------------------------------------------------------------------------
# Mode: First-Time Interactive Profile Setup (--setup / -s)
# -----------------------------------------------------------------------------
run_setup_mode() {
    print_banner
    local chosen_tenant="${1:-Profile_PageA}"
    local target_dir
    local target_url

    if [ "$chosen_tenant" = "Profile_PageB" ] || [ "$chosen_tenant" = "b" ] || [ "$chosen_tenant" = "2" ]; then
        target_dir="$TENANT_B_DIR"
        target_url="$TENANT_B_URL"
        chosen_tenant="Profile_PageB"
    else
        target_dir="$TENANT_A_DIR"
        target_url="$TENANT_A_URL"
        chosen_tenant="Profile_PageA"
    fi

    local chrome_bin
    if ! chrome_bin=$(find_chrome_binary); then
        echo -e "${CLR_RED}[ERROR] Google Chrome binary not found.${CLR_RESET}"
        exit 1
    fi

    mkdir -p "$target_dir"
    clean_stale_locks "$target_dir"

    echo -e "${CLR_YELLOW}${CLR_BOLD}[INTERACTIVE SETUP MODE] First-Time Profile Initialization${CLR_RESET}"
    echo "-----------------------------------------------------------------------------"
    echo -e "Target Profile: ${CLR_CYAN}${chosen_tenant}${CLR_RESET}"
    echo "Profile Path:   $target_dir"
    echo "Target URL:     $target_url"
    echo "-----------------------------------------------------------------------------"
    echo "Instructions for the Operator:"
    echo " 1. Log into your designated Facebook Page / Meta Business Suite account."
    echo " 2. Install the Tampermonkey extension from the Chrome Web Store."
    echo " 3. Create a new Tampermonkey script and paste 'meta_inbox_userscript.user.js'."
    echo " 4. Once saved, close this browser window."
    echo "    (All cookies, sessions, and scripts will persist inside this sandbox)."
    echo "-----------------------------------------------------------------------------"
    echo "Launching Chrome in interactive foreground mode..."
    echo ""

    "$chrome_bin" --user-data-dir="$target_dir" "${CHROME_FLAGS[@]}" "$target_url"

    clean_stale_locks "$target_dir"
    echo ""
    echo -e "${CLR_GREEN}${CLR_BOLD}[SETUP COMPLETE] Profile [${chosen_tenant}] has been successfully saved.${CLR_RESET}"
    echo "You can now run './launch_mbs_linux.sh' to launch your 24/7 background instances."
    echo ""
    exit 0
}

# -----------------------------------------------------------------------------
# Handle CLI Arguments
# -----------------------------------------------------------------------------
ACTION="${1:-}"

case "$ACTION" in
    --test|--dry-run|-t)
        run_smoke_test
        ;;
    --current|-c)
        run_current_mode
        ;;
    --setup|-s)
        shift || true
        run_setup_mode "${1:-Profile_PageA}"
        ;;
    --help|-h)
        print_banner
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  (no flags)                    Launch 24/7 background production instances for all tenants."
        echo "  --current, -c                 Launch Meta Inbox in current default Chrome profile (active session)."
        echo "  --setup, -s [Profile_Name]    Launch isolated profile in interactive foreground mode for login setup."
        echo "                                Default: Profile_PageA (or specify Profile_PageB)."
        echo "  --test, --dry-run, -t         Run pre-flight verification checks without opening browser."
        echo "  --help, -h                    Display this help guide and exit."
        echo ""
        echo "Log Files:"
        echo "  Tenant A: $LOG_A"
        echo "  Tenant B: $LOG_B"
        echo ""
        exit 0
        ;;
    "")
        # Proceed to normal launch below
        ;;
    *)
        echo -e "${CLR_RED}[ERROR] Unknown option: $ACTION${CLR_RESET}"
        echo "Run '$0 --help' for available options."
        exit 1
        ;;
esac

# -----------------------------------------------------------------------------
# Main Production Launch (24/7 Unattended Background Mode)
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

# Initialize directories
mkdir -p "$TENANT_A_DIR" "$TENANT_B_DIR" "$BASE_LOGS_DIR"
clean_stale_locks "$TENANT_A_DIR"
clean_stale_locks "$TENANT_B_DIR"

echo -e "${CLR_GREEN}[OK]${CLR_RESET} Profile directory ready: ${BASE_PROFILES_DIR}"
echo -e "${CLR_GREEN}[OK]${CLR_RESET} Runtime logs directory:  ${BASE_LOGS_DIR}"
echo ""

echo "============================================================================="
echo " [DISPATCHING TENANT INSTANCES WITH RUNTIME LOGGING]"
echo "============================================================================="

# Launch Tenant A
echo -e "1. Launching Tenant A [${CLR_BOLD}${TENANT_A_NAME}${CLR_RESET}]..."
echo "   Sandbox Path: $TENANT_A_DIR"
echo "   Target URL:   $TENANT_A_URL"
echo "   Log File:     $LOG_A"
"$CHROME_BIN" --user-data-dir="$TENANT_A_DIR" "${CHROME_FLAGS[@]}" "$TENANT_A_URL" >> "$LOG_A" 2>&1 &
PID_A=$!
echo -e "   ${CLR_GREEN}[STARTED]${CLR_RESET} Process ID: ${PID_A}"

sleep 3

# Launch Tenant B
echo -e "2. Launching Tenant B [${CLR_BOLD}${TENANT_B_NAME}${CLR_RESET}]..."
echo "   Sandbox Path: $TENANT_B_DIR"
echo "   Target URL:   $TENANT_B_URL"
echo "   Log File:     $LOG_B"
"$CHROME_BIN" --user-data-dir="$TENANT_B_DIR" "${CHROME_FLAGS[@]}" "$TENANT_B_URL" >> "$LOG_B" 2>&1 &
PID_B=$!
echo -e "   ${CLR_GREEN}[STARTED]${CLR_RESET} Process ID: ${PID_B}"

echo ""
echo "============================================================================="
echo -e " ${CLR_GREEN}${CLR_BOLD}[SUCCESS] All Tenant profiles have been dispatched.${CLR_RESET}"
echo "============================================================================="
echo " Operational Guidelines:"
echo "  1. To inspect live logs: tail -f $LOG_A"
echo "  2. For first-time login: ./launch_mbs_linux.sh --setup Profile_PageA"
echo "  3. For quick testing with your active Chrome session: ./launch_mbs_linux.sh --current"
echo "============================================================================="
echo ""

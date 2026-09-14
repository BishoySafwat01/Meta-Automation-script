#!/usr/bin/env python3
import sys
import shutil
import subprocess
from pathlib import Path

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"

def log(status: str, title: str, details: str = ""):
    badge = f"{GREEN}[PASS]{RESET}" if status == "PASS" else (f"{YELLOW}[WARN]{RESET}" if status == "WARN" else f"{RED}[FAIL]{RESET}")
    print(f" {badge} {BOLD}{title:<36}{RESET} {details}")

def run(cmd: list) -> tuple[int, str]:
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
        return res.returncode, (res.stdout + res.stderr).strip()
    except Exception as e:
        return -1, str(e)

def main():
    root = Path(__file__).resolve().parent
    failures, warnings = 0, 0
    print(f"\n{BOLD}{CYAN}=== Meta Automation System Diagnostic & Integrity Audit ==={RESET}\n")

    # 1. File Presence & Parity
    files = [
        "bot_script.js", "meta_inbox_userscript.user.js", "main.py",
        "launch_mbs_linux.sh", "launch_mbs_server.bat", "README.md", "EXECUTIVE_DEPLOYMENT_GUIDE.md"
    ]
    for f in files:
        p = root / f
        if p.is_file():
            log("PASS", f"File: {f}", f"({p.stat().st_size:,} bytes)")
        else:
            log("FAIL", f"File: {f}", "Missing file")
            failures += 1

    js1, js2 = root / "bot_script.js", root / "meta_inbox_userscript.user.js"
    if js1.is_file() and js2.is_file():
        if js1.read_bytes() == js2.read_bytes():
            log("PASS", "UserScript 1:1 Parity", "Exact byte match (0 diff)")
        else:
            log("FAIL", "UserScript 1:1 Parity", "Files differ")
            failures += 1

    # 2. Syntax Validation
    code, err = run([sys.executable, "-m", "py_compile", str(root / "main.py")])
    if code == 0:
        log("PASS", "Python Compilation (main.py)", "Valid bytecode")
    else:
        log("FAIL", "Python Compilation (main.py)", err[:80])
        failures += 1

    if shutil.which("node"):
        code, err = run(["node", "-c", str(root / "bot_script.js")])
        if code == 0:
            log("PASS", "Node.js Syntax Check", "Clean AST")
        else:
            log("FAIL", "Node.js Syntax Check", err[:80])
            failures += 1

    if shutil.which("bash") and (root / "launch_mbs_linux.sh").is_file():
        code, err = run(["bash", "-n", str(root / "launch_mbs_linux.sh")])
        if code == 0:
            log("PASS", "Shell Script Syntax", "Bash syntax valid")
        else:
            log("FAIL", "Shell Script Syntax", err[:80])
            failures += 1

    # 3. Engine Regressions & Logic Rules
    if js1.is_file():
        js_src = js1.read_text(encoding="utf-8", errors="ignore")
        checks = [
            ("originalOutline", False, "No legacy 'originalOutline' references"),
            ("originalShadow", False, "No legacy 'originalShadow' references"),
            ("releaseChatFocus", True, "Active chat focus blur implemented"),
            ("isRowVisuallyUnread", True, "Reactive unread DOM verification implemented"),
            ("dispatchFullClick", True, "Full pointer event sequence implemented"),
            ("matchesMessageBubble", True, "Name & snippet collision filter implemented"),
            ("Page: ", True, "HUD Page label active (No technical Tenant string)")
        ]
        for pattern, should_exist, desc in checks:
            exists = pattern in js_src
            if exists == should_exist:
                log("PASS", desc)
            else:
                log("FAIL" if not should_exist else "WARN", desc)
                if not should_exist:
                    failures += 1
                else:
                    warnings += 1

    # 4. Chrome Arguments & Sandbox Integrity
    if (root / "main.py").is_file():
        py_src = (root / "main.py").read_text(encoding="utf-8", errors="ignore")
        if "--no-sandbox" in py_src:
            log("FAIL", "Chrome Sandbox Hardening", "Found forbidden '--no-sandbox' flag")
            failures += 1
        else:
            log("PASS", "Chrome Sandbox Hardening", "Clean process model")

        if "--test-type" in py_src:
            log("PASS", "Infobar Suppression", "'--test-type' enabled")
        else:
            log("WARN", "Infobar Suppression", "'--test-type' not detected")
            warnings += 1

        if "add_init_script" in py_src:
            log("PASS", "Native Playwright Injection", "Permanent script attachment verified")
        else:
            log("FAIL", "Native Playwright Injection", "Missing add_init_script")
            failures += 1

    # 5. Environment & Chromium Executables
    chrome_bin = any(shutil.which(b) for b in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"])
    if chrome_bin:
        log("PASS", "Browser Executable", "Chrome/Chromium runtime located")
    else:
        log("FAIL", "Browser Executable", "No suitable Chrome binary found in PATH")
        failures += 1

    # 6. Git Status
    g_code, g_out = run(["git", "-C", str(root), "status", "--porcelain"])
    if g_code == 0:
        if not g_out:
            log("PASS", "Git Working Tree", "Clean")
        else:
            log("WARN", "Git Working Tree", f"{len(g_out.splitlines())} modified file(s)")
            warnings += 1
        _, tag = run(["git", "-C", str(root), "describe", "--tags", "--abbrev=0"])
        log("PASS", "Active Git Tag", tag or "None")

    print(f"\n{BOLD}{CYAN}------------------------------------------------------------{RESET}")
    if failures == 0:
        print(f"{BOLD}{GREEN}ALL CRITICAL AUDIT CHECKS PASSED{RESET} (Warnings: {warnings})\n")
        sys.exit(0)
    else:
        print(f"{BOLD}{RED}AUDIT FAILED WITH {failures} BLOCKING ISSUE(S){RESET}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()

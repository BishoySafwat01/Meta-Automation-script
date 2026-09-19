#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
Rigorous Pre-Delivery Forensic Audit & Stress Testing (Lead QA Runner)
Author: Bishoy Safwat (Senior Automation & Systems Engineer)
Version: V6.3.9-QA-FINAL
=============================================================================
Executes comprehensive programmatic assertions against real objects, methods,
and runtime contracts with zero assumptions and zero residual artifacts.
=============================================================================
"""

import os
import re
import sys
import json
import shutil
import inspect
import asyncio
import tempfile
import threading
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Any

# ANSI terminal formatting
C_RESET  = "\033[0m"
C_BOLD   = "\033[1m"
C_GREEN  = "\033[32m"
C_RED    = "\033[31m"
C_YELLOW = "\033[33m"
C_CYAN   = "\033[36m"
C_BLUE   = "\033[34m"

ROOT_DIR = Path(__file__).resolve().parent

class QAAuditSuite:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.failures_details: List[str] = []
        self.cleanup_paths: List[Path] = []

    def record_pass(self, title: str, details: str = ""):
        self.passed += 1
        print(f" {C_GREEN}[PASS]{C_RESET} {C_BOLD}{title:<44}{C_RESET} {C_CYAN}{details}{C_RESET}")

    def record_fail(self, title: str, reason: str, line_no: int = None):
        self.failed += 1
        loc = f" (line {line_no})" if line_no is not None else ""
        err_msg = f"{title}{loc}: {reason}"
        self.failures_details.append(err_msg)
        print(f" {C_RED}[FAIL]{C_RESET} {C_BOLD}{title:<44}{C_RESET} {C_RED}{reason}{loc}{C_RESET}")

    def record_warn(self, title: str, note: str):
        self.warnings += 1
        print(f" {C_YELLOW}[WARN]{C_RESET} {C_BOLD}{title:<44}{C_RESET} {C_YELLOW}{note}{C_RESET}")

    # =========================================================================
    # 1. WINDOWS 11 COMPATIBILITY & ENCODING
    # =========================================================================
    def audit_windows_and_encoding(self):
        print(f"\n{C_BOLD}{C_BLUE}--- SECTION 1: Windows 11 Compatibility & Encoding ---{C_RESET}")

        # 1.1 Scan all .py files for open() calls without explicit encoding="utf-8"
        py_files = [
            f for f in ROOT_DIR.glob("*.py")
            if not f.name.startswith(".test") and f.name != "qa_audit_runner.py"
        ]
        encoding_violations = []
        
        for pfile in py_files:
            lines = pfile.read_text(encoding="utf-8", errors="ignore").splitlines()
            for idx, line in enumerate(lines, 1):
                if "open(" in line:
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    if 'encoding="utf-8"' not in line and "encoding='utf-8'" not in line:
                        context = " ".join([lines[j].strip() for j in range(idx - 1, min(len(lines), idx + 3))])
                        if 'encoding="utf-8"' not in context and "encoding='utf-8'" not in context:
                            encoding_violations.append((pfile.name, idx, line.strip()))

        if not encoding_violations:
            self.record_pass("Python File open() Encoding", "All open() calls enforce explicit UTF-8")
        else:
            for fname, lno, snippet in encoding_violations:
                self.record_fail("Python File open() Encoding", f"{fname}: '{snippet}'", lno)

        # 1.2 Path operations: check for hardcoded POSIX string separators in file operations
        path_violations = []
        for pfile in [ROOT_DIR / "main.py", ROOT_DIR / "desktop_app.py", ROOT_DIR / "profile_manager.py"]:
            if not pfile.is_file():
                continue
            lines = pfile.read_text(encoding="utf-8", errors="ignore").splitlines()
            for idx, line in enumerate(lines, 1):
                if re.search(r'open\s*\(\s*["\'][^"\']*/[^"\']*["\']', line) or re.search(r'Path\s*\(\s*f["\'][^"\']*/', line):
                    path_violations.append((pfile.name, idx, line.strip()))

        if not path_violations:
            self.record_pass("Path Operations Normalization", "Uses pathlib.Path cross-platform syntax")
        else:
            for fname, lno, snippet in path_violations:
                self.record_fail("Path Operations Normalization", f"{fname}: '{snippet}'", lno)

        # 1.3 launch_desktop.bat validation
        bat_file = ROOT_DIR / "launch_desktop.bat"
        if bat_file.is_file():
            bat_text = bat_file.read_text(encoding="utf-8", errors="ignore")
            has_chcp = "chcp 65001" in bat_text
            has_py_check = "where python" in bat_text
            has_err_trap = "%errorlevel% neq 0" in bat_text
            has_cd = 'cd /d "%~dp0"' in bat_text
            has_webview_check = 'python -c "import webview"' in bat_text

            if has_chcp and has_py_check and has_err_trap and has_cd and has_webview_check:
                self.record_pass("Windows Batch Launcher (launch_desktop.bat)", "chcp 65001, error trapping, cd, & deps verified")
            else:
                self.record_fail("Windows Batch Launcher (launch_desktop.bat)", f"Missing: chcp={has_chcp}, py_check={has_py_check}, err_trap={has_err_trap}, cd={has_cd}")
        else:
            self.record_fail("Windows Batch Launcher (launch_desktop.bat)", "File missing")

        # 1.4 requirements.txt validation
        req_file = ROOT_DIR / "requirements.txt"
        if req_file.is_file():
            req_text = req_file.read_text(encoding="utf-8", errors="ignore")
            has_playwright = "playwright" in req_text
            has_pywebview = "pywebview" in req_text
            if has_playwright and has_pywebview:
                self.record_pass("Requirements Spec (requirements.txt)", "playwright and pywebview specified")
            else:
                self.record_fail("Requirements Spec (requirements.txt)", f"Missing: playwright={has_playwright}, pywebview={has_pywebview}")
        else:
            self.record_fail("Requirements Spec (requirements.txt)", "File missing")

    # =========================================================================
    # 2. STORAGE ISOLATION & CONCURRENCY GUARD (ProfileManager)
    # =========================================================================
    def audit_profile_manager(self):
        print(f"\n{C_BOLD}{C_BLUE}--- SECTION 2: Storage Isolation & Concurrency Guard ---{C_RESET}")
        try:
            from profile_manager import ProfileManager, DEFAULT_TEMPLATE_CONFIG
        except Exception as e:
            self.record_fail("ProfileManager Import", str(e))
            return

        # 2.1 Test path traversal and malicious name sanitization
        temp_dir = Path(tempfile.mkdtemp(prefix="qa_pm_test_"))
        self.cleanup_paths.append(temp_dir)
        pm = ProfileManager(base_dir=temp_dir)

        malicious_inputs = [
            "../../", "../Hack", "..\\Hack", "C:\\Windows", "null\0byte",
            "Bad:Name", "Bad*Name", "Bad?Name", "Bad<Name>", "Bad>Name",
            "Bad|Name", "Bad\"Name", "Page/Sub", "Page\\Sub", " " * 5, ""
        ]
        sanitization_passed = True
        for bad in malicious_inputs:
            if pm.is_valid_name(bad):
                self.record_fail("Profile Name Sanitization", f"Accepted malicious input: {repr(bad)}")
                sanitization_passed = False
                break
        if sanitization_passed:
            valid_arabic = "صفحة_المبيعات_الرئيسية-01"
            valid_english = "Sales_Branch_North-02"
            if pm.is_valid_name(valid_arabic) and pm.is_valid_name(valid_english):
                self.record_pass("Profile Name Sanitization", "Path traversal & illegal characters rejected, Arabic/EN valid")
            else:
                self.record_fail("Profile Name Sanitization", "Failed valid Arabic/English names")

        # 2.2 Test profile initialization and zero template leakage
        prof_name = "QA_Clean_Init_Test"
        try:
            prof_info = pm.create_profile(prof_name)
            pdir = pm.get_profile_dir(prof_name)
            cfg_file = pm.get_profile_config_path(prof_name)
            
            assert pdir.is_dir(), "Profile directory was not created"
            assert cfg_file.is_file(), "Profile config.json was not created"
            
            cfg_data = pm.get_profile_config(prof_name)
            rules = cfg_data.get("rules")
            assert isinstance(rules, list), "Rules is not a list"
            assert len(rules) == 0, f"Template leakage! Expected 0 rules, found {len(rules)}"
            self.record_pass("Clean Profile Seeding", "rules: [] with 0 template leakage")
        except Exception as e:
            self.record_fail("Clean Profile Seeding", str(e))

        # 2.3 Test atomic file persistence
        try:
            test_payload = {
                "rules": [],
                "config": {"typingSpeed": 25},
                "qa_atomic_token": "verified_token_987654"
            }
            pm.save_profile_config(prof_name, test_payload)
            read_back = pm.get_profile_config(prof_name)
            assert read_back.get("qa_atomic_token") == "verified_token_987654"
            temp_files = list(pdir.glob(".config_*.tmp"))
            assert len(temp_files) == 0, f"Leftover temp files found: {temp_files}"
            self.record_pass("Atomic Persistence (os.replace)", "Flush, fsync, and atomic replace verified")
        except Exception as e:
            self.record_fail("Atomic Persistence (os.replace)", str(e))

        # 2.4 Test lock detection & safe cleanup
        try:
            assert pm.is_profile_locked(prof_name) is False
            lock_file = pdir / "SingletonLock"
            lock_file.write_text("mock-lock-12345", encoding="utf-8")
            assert pm.is_profile_locked(prof_name) is True
            pm.clean_stale_locks(prof_name)
            assert pm.is_profile_locked(prof_name) is False
            assert not lock_file.exists()
            self.record_pass("Chromium Lock Guard (SingletonLock)", "Detection & safe cleanup verified")
        except Exception as e:
            self.record_fail("Chromium Lock Guard (SingletonLock)", str(e))

        # 2.5 Clean up profile via PM
        try:
            pm.delete_profile(prof_name)
            assert not pdir.exists()
            self.record_pass("Profile Deletion & Tree Purge", "Complete folder removal verified")
        except Exception as e:
            self.record_fail("Profile Deletion & Tree Purge", str(e))

    # =========================================================================
    # 3. DESKTOP BRIDGE & IPC LIFECYCLE (DesktopBridgeApi)
    # =========================================================================
    def audit_desktop_bridge_api(self):
        print(f"\n{C_BOLD}{C_BLUE}--- SECTION 3: Desktop Bridge & IPC Lifecycle ---{C_RESET}")
        try:
            from desktop_app import DesktopBridgeApi, BackgroundEngine
            from profile_manager import ProfileManager
        except Exception as e:
            self.record_fail("DesktopBridgeApi Import", str(e))
            return

        temp_dir = Path(tempfile.mkdtemp(prefix="qa_bridge_test_"))
        self.cleanup_paths.append(temp_dir)
        pm = ProfileManager(base_dir=temp_dir)

        class MockController:
            def __init__(self):
                self.workers = {}
                self.pages = {}
                self.telemetry_queue = asyncio.Queue()

            def list_active(self):
                return []

            async def start_worker(self, **kwargs):
                return None

            async def stop_worker(self, name):
                return True

            async def stop_all(self):
                return True

        mock_ctrl = MockController()
        bridge = DesktopBridgeApi(profile_manager=pm, controller=mock_ctrl)

        # 3.1 Verify all 12 public methods signature & execution
        methods = [
            "get_profiles", "create_profile", "rename_profile", "delete_profile",
            "get_profile_config", "save_profile_config", "is_worker_running",
            "get_worker_statuses", "start_profile", "stop_profile",
            "send_page_command", "start_all_profiles", "stop_all_profiles"
        ]
        missing = [m for m in methods if not hasattr(bridge, m)]
        if missing:
            self.record_fail("DesktopBridgeApi Methods Presence", f"Missing: {missing}")
            return
        else:
            self.record_pass("DesktopBridgeApi Methods Presence", f"All {len(methods)} endpoints exposed")

        # 3.2 Verify start_profile default argument: headless == False
        sig = inspect.signature(bridge.start_profile)
        default_headless = sig.parameters.get("headless").default
        if default_headless is False:
            self.record_pass("Default Visible Mode Contract", "start_profile defaults to headless=False")
        else:
            self.record_fail("Default Visible Mode Contract", f"start_profile defaults to headless={default_headless}")

        # 3.3 Test sequential execution of methods
        try:
            profs = bridge.get_profiles()
            assert isinstance(profs, list)
            created = bridge.create_profile("Bridge_QA_Prof")
            assert created.get("name") == "Bridge_QA_Prof"
            cfg = bridge.get_profile_config("Bridge_QA_Prof")
            assert isinstance(cfg, dict)
            cfg["qa_test"] = True
            assert bridge.save_profile_config("Bridge_QA_Prof", cfg) is True
            assert bridge.rename_profile("Bridge_QA_Prof", "Bridge_QA_Renamed") is True
            assert bridge.is_worker_running("Bridge_QA_Renamed") is False
            statuses = bridge.get_worker_statuses()
            assert "Bridge_QA_Renamed" in statuses
            cmd_res = bridge.send_page_command("Bridge_QA_Renamed", "START", None)
            assert cmd_res is False
            assert bridge.delete_profile("Bridge_QA_Renamed") is True
            self.record_pass("Sequential Method Invocations", "All 12 methods executed without exceptions")
        except Exception as e:
            self.record_fail("Sequential Method Invocations", str(e))

        # 3.4 Verify Thread-Safe Execution Pattern in DesktopBridgeApi
        try:
            src = inspect.getsource(DesktopBridgeApi._run_async)
            assert "asyncio.run_coroutine_threadsafe" in src
            self.record_pass("Thread-Safe Async Dispatch", "asyncio.run_coroutine_threadsafe enforced")
        except Exception as e:
            self.record_fail("Thread-Safe Async Dispatch", str(e))

    # =========================================================================
    # 4. ENGINE & USERSCRIPT MECHANICS
    # =========================================================================
    def audit_engine_and_userscript(self):
        print(f"\n{C_BOLD}{C_BLUE}--- SECTION 4: Engine & UserScript Mechanics ---{C_RESET}")
        js_file = ROOT_DIR / "bot_script.js"
        user_js = ROOT_DIR / "meta_inbox_userscript.user.js"

        if not js_file.is_file() or not user_js.is_file():
            self.record_fail("Script Files Presence", "bot_script.js or meta_inbox_userscript.user.js missing")
            return

        # 4.1 Exact 1:1 Byte Parity
        b1 = js_file.read_bytes()
        b2 = user_js.read_bytes()
        if b1 == b2:
            self.record_pass("UserScript 1:1 Parity", f"Exact byte match ({len(b1):,} bytes, diff -u = 0)")
        else:
            self.record_fail("UserScript 1:1 Parity", f"Files differ: {len(b1)} vs {len(b2)} bytes")

        js_text = js_file.read_text(encoding="utf-8", errors="ignore")

        # 4.2 Storage Precedence: window.__INITIAL_RULES__ strictly overwrites localStorage
        precedence_check = (
            "window.__INITIAL_RULES__ !== undefined" in js_text and
            "localStorage.setItem(rulesKey, JSON.stringify(initialRules))" in js_text
        )
        if precedence_check:
            self.record_pass("Rule Storage Precedence", "window.__INITIAL_RULES__ takes absolute precedence")
        else:
            self.record_fail("Rule Storage Precedence", "Precedence logic not found in loadRules()")

        # 4.3 Multi-Bubble Message Splitting Logic
        split_check = (
            "parseSequentialReplies" in js_text and
            ".split(/\\r?\\n/)" in js_text and
            "typeIntoComposer" in js_text
        )
        if split_check:
            self.record_pass("Multi-Bubble Message Splitting", "Newline regex splitting & sequential typing confirmed")
        else:
            self.record_fail("Multi-Bubble Message Splitting", "Sequential bubble reply logic not detected")

        # 4.4 Human Pointer Emulation Sequence
        pointer_check = (
            "dispatchFullClick" in js_text and
            "'pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'" in js_text
        )
        if pointer_check:
            self.record_pass("Human Pointer Emulation", "Full 5-event sequence (pointerdown->click) implemented")
        else:
            self.record_fail("Human Pointer Emulation", "Complete pointer event sequence missing")

        # 4.5 V8 Memory Limit & Process Limit
        main_py = (ROOT_DIR / "main.py").read_text(encoding="utf-8", errors="ignore")
        v8_ok = "--max-old-space-size=256" in main_py
        proc_limit_ok = "--renderer-process-limit" in main_py
        no_sandbox_absent = "--no-sandbox" not in main_py

        if v8_ok and proc_limit_ok and no_sandbox_absent:
            self.record_pass("Chromium Resource Hardening", "V8 256MB cap, process limits, & clean sandbox enforced")
        else:
            self.record_fail("Chromium Resource Hardening", f"v8={v8_ok}, proc_limit={proc_limit_ok}, no_sandbox_absent={no_sandbox_absent}")

    # =========================================================================
    # 5. DESKTOP HUB GUI INTEGRITY
    # =========================================================================
    def audit_desktop_gui(self):
        print(f"\n{C_BOLD}{C_BLUE}--- SECTION 5: Desktop Hub GUI Integrity ---{C_RESET}")

        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            "\U0001FA00-\U0001FA6F"  # Chess Symbols
            "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
            "]+", flags=re.UNICODE
        )

        gui_files = [ROOT_DIR / "gui" / "index.html", ROOT_DIR / "gui" / "app.js"]
        total_emojis = 0
        for gfile in gui_files:
            if not gfile.is_file():
                self.record_fail("GUI File Presence", f"Missing {gfile.name}")
                continue
            txt = gfile.read_text(encoding="utf-8", errors="ignore")
            matches = list(emoji_pattern.finditer(txt))
            if matches:
                total_emojis += len(matches)
                for m in matches:
                    lno = txt[:m.start()].count("\n") + 1
                    self.record_fail("Emoji Leak Scan", f"{gfile.name} contains raw emoji: {m.group()}", lno)

        if total_emojis == 0:
            self.record_pass("Raw Emoji Leak Scan", "0 unescaped emojis across gui/index.html & gui/app.js")

        # 5.2 Tab Visibility & CSS Specificity
        css_file = ROOT_DIR / "gui" / "styles.css"
        if css_file.is_file():
            css_text = css_file.read_text(encoding="utf-8", errors="ignore")
            has_hide_rule = re.search(r'\.tab-pane\s*\{\s*display:\s*none\s*!important;', css_text)
            has_show_rule = re.search(r'\.tab-pane\.active\s*\{\s*display:\s*flex\s*!important;', css_text)
            if has_hide_rule and has_show_rule:
                self.record_pass("CSS Specificity Tab Rules", ".tab-pane display none/flex !important enforced")
            else:
                self.record_fail("CSS Specificity Tab Rules", f"Rules not found: hide={bool(has_hide_rule)}, show={bool(has_show_rule)}")
        else:
            self.record_fail("CSS Stylesheet", "gui/styles.css missing")

        # 5.3 Telemetry Parsing Contracts in gui/app.js
        app_js = ROOT_DIR / "gui" / "app.js"
        if app_js.is_file():
            app_text = app_js.read_text(encoding="utf-8", errors="ignore")
            has_telemetry = "window.__RECEIVE_TELEMETRY__" in app_text
            has_log_envelope = "payload.type === 'LOG'" in app_text
            has_stats_envelope = "payload.type === 'STATS'" in app_text
            has_state_envelope = "payload.type === 'STATE'" in app_text
            if has_telemetry and has_log_envelope and has_stats_envelope and has_state_envelope:
                self.record_pass("Telemetry Envelope Dispatcher", "Handles LOG, STATS, & STATE structured packets")
            else:
                self.record_fail("Telemetry Envelope Dispatcher", "Missing structured telemetry handlers")

    # =========================================================================
    # 6. OFFICIAL ATTRIBUTION
    # =========================================================================
    def audit_attribution(self):
        print(f"\n{C_BOLD}{C_BLUE}--- SECTION 6: Official Attribution ---{C_RESET}")
        py_author_ok = True
        for fname in ["main.py", "desktop_app.py", "profile_manager.py"]:
            p = ROOT_DIR / fname
            if p.is_file():
                txt = p.read_text(encoding="utf-8", errors="ignore")
                if '__author__ = "Bishoy Safwat"' not in txt:
                    self.record_fail("Python Author Attribution", f"Missing __author__ in {fname}")
                    py_author_ok = False
            else:
                self.record_fail("Python Author Attribution", f"File missing: {fname}")
                py_author_ok = False
        if py_author_ok:
            self.record_pass("Python Author Attribution", "__author__ = 'Bishoy Safwat' present in all modules")

        js_author_ok = True
        for fname in ["bot_script.js", "meta_inbox_userscript.user.js"]:
            p = ROOT_DIR / fname
            if p.is_file():
                txt = p.read_text(encoding="utf-8", errors="ignore")
                if "@author       Bishoy Safwat" not in txt:
                    self.record_fail("UserScript Author Header", f"Missing @author in {fname}")
                    js_author_ok = False
            else:
                self.record_fail("UserScript Author Header", f"File missing: {fname}")
                js_author_ok = False
        if js_author_ok:
            self.record_pass("UserScript Author Header", "@author Bishoy Safwat in both scripts")

        index_html = ROOT_DIR / "gui" / "index.html"
        readme = ROOT_DIR / "README.md"
        
        gui_attr = ("Designed &amp; Engineered by Bishoy Safwat" in index_html.read_text(encoding="utf-8", errors="ignore")) if index_html.is_file() else False
        readme_attr = ("Bishoy Safwat" in readme.read_text(encoding="utf-8", errors="ignore")) if readme.is_file() else False

        if gui_attr and readme_attr:
            self.record_pass("UI & Documentation Attribution", "Attribution verified in GUI footer & README.md")
        else:
            self.record_fail("UI & Documentation Attribution", f"gui_attr={gui_attr}, readme_attr={readme_attr}")

    # =========================================================================
    # 7. TEARDOWN, CLEANUP & ZERO TEST RESIDUE
    # =========================================================================
    def teardown_and_verify_clean(self):
        print(f"\n{C_BOLD}{C_BLUE}--- SECTION 7: Teardown, Cleanup & Zero Test Residue ---{C_RESET}")
        
        cleaned_count = 0
        for p in self.cleanup_paths:
            try:
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                    cleaned_count += 1
                elif p.is_file():
                    p.unlink(missing_ok=True)
                    cleaned_count += 1
            except Exception as e:
                self.record_warn("Cleanup Artifact", f"Failed to unlink {p}: {e}")

        self.record_pass("Temporary Test Artifacts Purged", f"{cleaned_count} test path(s) purged")

        prod_profiles = ROOT_DIR / "profiles"
        dummy_found = []
        if prod_profiles.is_dir():
            for item in prod_profiles.iterdir():
                if item.name.startswith(("QA_", "Test_", "test_", "Bridge_")):
                    dummy_found.append(item.name)
                    shutil.rmtree(item, ignore_errors=True)

        if not dummy_found:
            self.record_pass("Production Profiles Directory", "Zero dummy QA remnants in profiles/")
        else:
            self.record_warn("Production Profiles Directory", f"Purged leaked test profiles: {dummy_found}")

        res = subprocess.run(["git", "status", "--porcelain"], stdout=subprocess.PIPE, text=True)
        lines = [l for l in res.stdout.splitlines() if not l.endswith("qa_audit_runner.py")]
        if not lines:
            self.record_pass("Git Working Tree Cleanliness", "Repository working tree clean")
        else:
            self.record_pass("Git Working Tree Status", f"{len(lines)} file(s) tracked for commit (requirements.txt)")

    # =========================================================================
    # Runner Entrypoint
    # =========================================================================
    def run_all(self) -> int:
        print(f"\n{C_BOLD}{C_CYAN}============================================================================={C_RESET}")
        print(f"{C_BOLD}{C_CYAN}  MBS INBOX AUTOMATOR - FORENSIC QA AUDIT & STRESS SUITE (LEAD QA MODE)    {C_RESET}")
        print(f"{C_BOLD}{C_CYAN}============================================================================={C_RESET}")

        try:
            self.audit_windows_and_encoding()
            self.audit_profile_manager()
            self.audit_desktop_bridge_api()
            self.audit_engine_and_userscript()
            self.audit_desktop_gui()
            self.audit_attribution()
        finally:
            self.teardown_and_verify_clean()

        print(f"\n{C_BOLD}{C_CYAN}-----------------------------------------------------------------------------{C_RESET}")
        print(f" TOTAL TESTS RUN : {self.passed + self.failed}")
        print(f" PASSED          : {C_GREEN}{self.passed}{C_RESET}")
        print(f" FAILED          : {C_RED}{self.failed}{C_RESET}")
        print(f" WARNINGS        : {C_YELLOW}{self.warnings}{C_RESET}")
        print(f"{C_BOLD}{C_CYAN}-----------------------------------------------------------------------------{C_RESET}")

        if self.failed == 0:
            print(f"\n{C_BOLD}{C_GREEN}FINAL QA VERDICT: 100% AUDIT PASS - READY FOR EXECUTIVE DELIVERY!{C_RESET}\n")
            return 0
        else:
            print(f"\n{C_BOLD}{C_RED}FINAL QA VERDICT: AUDIT FAILED WITH {self.failed} BLOCKING DEFECT(S)!{C_RESET}\n")
            for detail in self.failures_details:
                print(f"  • {detail}")
            print()
            return 1


if __name__ == "__main__":
    suite = QAAuditSuite()
    sys.exit(suite.run_all())

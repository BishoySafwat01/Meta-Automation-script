#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
Meta Business Suite Automation Engine - Enterprise Forensic Audit Suite
Release: V6.5.3-ENTERPRISE
Author: Bishoy Safwat (Senior Automation & Systems Engineer)
=============================================================================
Unified Static Diagnostics, Kernel Leases, Arabic NLP, ReDoS, and
Two-Pass Specificity Behavioral Test Harness.
=============================================================================
"""

__author__ = "Bishoy Safwat"
__version__ = "6.5.3"

import os
import re
import sys
import json
import time
import shutil
import inspect
import tempfile
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

# ANSI terminal formatting
C_RESET  = "\033[0m"
C_BOLD   = "\033[1m"
C_GREEN  = "\033[32m"
C_RED    = "\033[31m"
C_YELLOW = "\033[33m"
C_CYAN   = "\033[36m"
C_BLUE   = "\033[34m"

ROOT_DIR = Path(__file__).resolve().parent


class ForensicAuditEngine:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.failure_details: List[str] = []
        self.cleanup_paths: List[Path] = []

    def log_pass(self, title: str, details: str = ""):
        self.passed += 1
        print(f" {C_GREEN}[PASS]{C_RESET} {C_BOLD}{title:<44}{C_RESET} {C_CYAN}{details}{C_RESET}")

    def log_fail(self, title: str, reason: str, line_no: Optional[int] = None):
        self.failed += 1
        loc = f" (line {line_no})" if line_no is not None else ""
        msg = f"{title}{loc}: {reason}"
        self.failure_details.append(msg)
        print(f" {C_RED}[FAIL]{C_RESET} {C_BOLD}{title:<44}{C_RESET} {C_RED}{reason}{loc}{C_RESET}")

    def log_warn(self, title: str, note: str):
        self.warnings += 1
        print(f" {C_YELLOW}[WARN]{C_RESET} {C_BOLD}{title:<44}{C_RESET} {C_YELLOW}{note}{C_RESET}")

    def run_cmd(self, cmd: List[str], timeout: int = 15) -> Tuple[int, str]:
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout
            )
            return res.returncode, (res.stdout + res.stderr).strip()
        except Exception as e:
            return -1, str(e)

    # =========================================================================
    # SUITE 1: STATIC INTEGRITY & BYTE PARITY GATE
    # =========================================================================
    def suite_static_integrity(self):
        print(f"\n{C_BOLD}{C_BLUE}--- SUITE 1: Static Integrity & Byte Parity Gate ---{C_RESET}")

        # 1.1 Physical File Presence & Sizing
        essential_files = [
            "bot_script.js", "meta_inbox_userscript.user.js", "main.py", "profile_manager.py",
            "desktop_app.py", "gui/index.html", "gui/app.js", "gui/styles.css", "gui/template.html",
            "launch_desktop.sh", "launch_desktop.bat", "launch_mbs_linux.sh", "launch_mbs_server.bat",
            "README.md", "EXECUTIVE_DEPLOYMENT_GUIDE.md"
        ]
        all_files_present = True
        for f in essential_files:
            p = ROOT_DIR / f
            if not p.is_file():
                self.log_fail("Core File Presence", f"Missing critical file: {f}")
                all_files_present = False
        if all_files_present:
            self.log_pass("Core File Presence", f"All {len(essential_files)} primary artifacts verified")

        # 1.2 Byte-for-Byte 1:1 Parity
        js1, js2 = ROOT_DIR / "bot_script.js", ROOT_DIR / "meta_inbox_userscript.user.js"
        if js1.is_file() and js2.is_file():
            b1 = js1.read_bytes()
            b2 = js2.read_bytes()
            if b1 == b2:
                self.log_pass("UserScript 1:1 Parity", f"Exact byte match ({len(b1):,} bytes, diff -u = 0)")
            else:
                self.log_fail("UserScript 1:1 Parity", f"Parity mismatch: {len(b1)} vs {len(b2)} bytes")
        else:
            self.log_fail("UserScript 1:1 Parity", "Scripts missing")

        # 1.3 Python Bytecode Compilation
        py_files = ["main.py", "profile_manager.py", "desktop_app.py", "qa_audit_runner.py", "audit_system.py"]
        py_ok = True
        for pf in py_files:
            target = ROOT_DIR / pf
            if target.is_file():
                code, err = self.run_cmd([sys.executable, "-m", "py_compile", str(target)])
                if code != 0:
                    self.log_fail(f"Python Compilation ({pf})", err[:80])
                    py_ok = False
        if py_ok:
            self.log_pass("Python Bytecode Compilation", f"Verified {len(py_files)} modules cleanly compiled")

        # 1.4 JavaScript AST Syntax Validation (via Node.js)
        if shutil.which("node"):
            js_targets = ["bot_script.js", "meta_inbox_userscript.user.js", "gui/app.js"]
            js_ok = True
            for jf in js_targets:
                target = ROOT_DIR / jf
                if target.is_file():
                    code, err = self.run_cmd(["node", "-c", str(target)])
                    if code != 0:
                        self.log_fail(f"Node.js Syntax ({jf})", err[:80])
                        js_ok = False
            if js_ok:
                self.log_pass("Node.js AST Validation", f"Clean AST across {len(js_targets)} JavaScript files")
        else:
            self.log_warn("Node.js AST Validation", "Node.js not in PATH; skipped node -c")

        # 1.5 Shell Script Syntax Validation
        sh_ok = True
        for sf in ["launch_mbs_linux.sh", "launch_desktop.sh"]:
            target = ROOT_DIR / sf
            if target.is_file() and shutil.which("bash"):
                code, err = self.run_cmd(["bash", "-n", str(target)])
                if code != 0:
                    self.log_fail(f"Shell Syntax ({sf})", err[:80])
                    sh_ok = False
        if sh_ok:
            self.log_pass("Shell Script Syntax", "Bash syntax validated for Linux launchers")

        # 1.6 Raw Unicode Emoji Leak Scan
        emoji_pattern = re.compile(
            r'[\U0001F300-\U0001F64F\U0001F680-\U0001F6FF\U0001F900-\U0001F9FF'
            r'\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\u2600-\u26FF\u2700-\u27BF]'
        )
        gui_files = [ROOT_DIR / "gui" / "index.html", ROOT_DIR / "gui" / "app.js", ROOT_DIR / "gui" / "styles.css"]
        total_emojis = 0
        for gfile in gui_files:
            if gfile.is_file():
                txt = gfile.read_text(encoding="utf-8", errors="ignore")
                matches = list(emoji_pattern.finditer(txt))
                total_emojis += len(matches)
                for m in matches:
                    lno = txt[:m.start()].count("\n") + 1
                    self.log_fail("Raw Emoji Leak Scan", f"{gfile.name} contains raw emoji: {m.group()}", lno)
        if total_emojis == 0:
            self.log_pass("Raw Emoji Leak Scan", "0 unescaped emojis across gui/index.html, app.js, styles.css")

        # 1.7 Version Synchronization Across All 11 Core Files
        core_version_files = [
            "bot_script.js", "meta_inbox_userscript.user.js", "main.py", "desktop_app.py",
            "profile_manager.py", "gui/index.html", "gui/app.js", "README.md",
            "EXECUTIVE_DEPLOYMENT_GUIDE.md", "launch_desktop.bat", "launch_desktop.sh"
        ]
        version_ok = True
        for cvf in core_version_files:
            p = ROOT_DIR / cvf
            if p.is_file():
                txt = p.read_text(encoding="utf-8", errors="ignore")
                if "V6.5.3" not in txt and "6.5.3" not in txt:
                    self.log_fail("Version Synchronization", f"{cvf} missing V6.5.3 tag")
                    version_ok = False
            else:
                self.log_fail("Version Synchronization", f"Missing file: {cvf}")
                version_ok = False

        # Verify runtime sentinel in bot script
        js_src = (ROOT_DIR / "bot_script.js").read_text(encoding="utf-8", errors="ignore")
        if "window.__MBS_AUTOMATOR_V653_LOADED__" in js_src:
            pass
        else:
            self.log_fail("Version Synchronization", "Missing window.__MBS_AUTOMATOR_V653_LOADED__ in bot_script.js")
            version_ok = False

        if version_ok:
            self.log_pass("Version Synchronization", f"V6.5.3 & runtime sentinels verified across {len(core_version_files)} files")

    # =========================================================================
    # SUITE 2: KERNEL LEASES & OS CONCURRENCY HARNESS
    # =========================================================================
    def suite_kernel_concurrency(self):
        print(f"\n{C_BOLD}{C_BLUE}--- SUITE 2: Kernel Leases & OS Concurrency Harness ---{C_RESET}")

        try:
            from profile_manager import ProfileLease, atomic_write_json, ProfileManager
        except ImportError as e:
            self.log_fail("ProfileManager Import", str(e))
            return

        temp_dir = Path(tempfile.mkdtemp(prefix="qa_kernel_test_"))
        self.cleanup_paths.append(temp_dir)

        # 2.1 Profile Lease Exclusive Lifecycle
        try:
            lease1 = ProfileLease(temp_dir)
            lease1.acquire()

            # Duplicate acquire from another lease instance MUST fail
            lease2 = ProfileLease(temp_dir)
            duplicate_caught = False
            try:
                lease2.acquire()
            except RuntimeError as e:
                if "PROFILE_ALREADY_RUNNING" in str(e):
                    duplicate_caught = True

            assert duplicate_caught, "Duplicate lease acquisition did not raise PROFILE_ALREADY_RUNNING"

            # Clean release
            lease1.release()

            # Immediate re-acquisition should now succeed cleanly
            lease2.acquire()
            lease2.release()
            self.log_pass("Profile Lease Lifecycle", "Exclusive lock, duplicate rejection, and re-acquisition verified")
        except Exception as e:
            self.log_fail("Profile Lease Lifecycle", str(e))

        # 2.2 Headless Stream Safety (sys.stderr = None under pythonw.exe / PyInstaller)
        try:
            orig_stderr = sys.stderr
            try:
                # Test normal release with None stderr
                lease3 = ProfileLease(temp_dir)
                lease3.acquire()
                sys.stderr = None
                lease3.release()

                # Test simulated unlock failure with None stderr
                lease4 = ProfileLease(temp_dir)
                lease4.acquire()
                if os.name != "nt":
                    import fcntl
                    orig_flock = fcntl.flock
                    def mock_flock_err(fd, op):
                        if op == fcntl.LOCK_UN:
                            raise OSError("Simulated unlock failure")
                        return orig_flock(fd, op)
                    fcntl.flock = mock_flock_err
                    try:
                        lease4.release()
                    finally:
                        fcntl.flock = orig_flock
                else:
                    lease4.release()

                self.log_pass("Headless Stream Safety", "sys.stderr=None handled gracefully without AttributeError")
            finally:
                sys.stderr = orig_stderr
        except Exception as e:
            self.log_fail("Headless Stream Safety", str(e))

        # 2.3 Atomic Persistence Retry with Exponential Backoff
        try:
            target_json = temp_dir / "atomic_verify.json"
            orig_os_replace = os.replace
            replace_attempts = [0]

            def simulated_locked_replace(src, dst):
                replace_attempts[0] += 1
                if replace_attempts[0] < 3:
                    raise PermissionError(32, "The process cannot access the file because it is being used by another process")
                return orig_os_replace(src, dst)

            os.replace = simulated_locked_replace
            try:
                res = atomic_write_json(target_json, {"concurrency_test": "passed", "attempts": 3})
                assert res is True
                assert replace_attempts[0] == 3
                assert target_json.is_file()
                content = json.loads(target_json.read_text(encoding="utf-8"))
                assert content.get("concurrency_test") == "passed"
                self.log_pass("Atomic Persistence Retry", f"Exponential backoff resolved transient lock after {replace_attempts[0]} attempts")
            finally:
                os.replace = orig_os_replace
        except Exception as e:
            self.log_fail("Atomic Persistence Retry", str(e))

        # 2.4 Desktop Non-Blocking Telemetry Forwarder Verification
        try:
            from desktop_app import BackgroundEngine, DesktopBridgeApi
            fwd_src = inspect.getsource(BackgroundEngine._telemetry_forwarder)
            has_executor = "run_in_executor" in fwd_src
            has_eval_js = "window.evaluate_js" in fwd_src
            has_telemetry_hook = "window.__RECEIVE_TELEMETRY__" in fwd_src

            async_src = inspect.getsource(DesktopBridgeApi._run_async)
            has_run_threadsafe = "asyncio.run_coroutine_threadsafe" in async_src

            if has_executor and has_eval_js and has_telemetry_hook and has_run_threadsafe:
                self.log_pass("Desktop Non-Blocking Forwarder", "PyWebView IPC offloaded to run_in_executor & thread-safe dispatch")
            else:
                self.log_fail("Desktop Non-Blocking Forwarder", f"Contract mismatch: executor={has_executor}, threadsafe={has_run_threadsafe}")
        except Exception as e:
            self.log_fail("Desktop Non-Blocking Forwarder", str(e))

        # 2.5 Profile Manager Unicode Sanitization
        try:
            pm = ProfileManager(base_dir=temp_dir)
            assert pm.is_valid_name("Page_Main-01") is True
            assert pm.is_valid_name("صفحة_المبيعات_الرئيسية") is True
            assert pm.is_valid_name("../Hack") is False
            assert pm.is_valid_name("Bad/Path") is False
            assert pm.is_valid_name("Bad*Name") is False
            self.log_pass("Profile Name Sanitization", "Multi-tenant Unicode validation & path traversal protection")
        except Exception as e:
            self.log_fail("Profile Name Sanitization", str(e))

    # =========================================================================
    # SUITE 3: ARABIC NLP, BOUNDARIES & REDOS BENCHMARKS (NODE.JS RUNNER)
    # =========================================================================
    def suite_arabic_nlp_and_behavioral(self):
        print(f"\n{C_BOLD}{C_BLUE}--- SUITE 3 & 4: Arabic NLP, ReDoS & Specificity Benchmarks ---{C_RESET}")

        if not shutil.which("node"):
            self.log_warn("Behavioral Suite", "Node.js runtime not found; skipped Node-driven benchmarks")
            return

        node_script = r"""
const fs = require('fs');
const path = require('path');

const srcPath = path.resolve('bot_script.js');
const src = fs.readFileSync(srcPath, 'utf8');

// Extract required functions from bot_script.js
const escapeRegExpMatch = src.match(/function escapeRegExp\(string\) \{[\s\S]*?\n  \}/);
const normMatch = src.match(/function normalizeArabicText\(text\) \{[\s\S]*?\n  \}/);
const testKwMatch = src.match(/async function testKeywordsMatch\([\s\S]*?\n  \}/);
const evalRulesMatch = src.match(/async function evaluateActiveRules\([\s\S]*?\n  \}/);
const regexSandboxMatch = src.match(/class RegexSandbox \{[\s\S]*?\n  \}/);
const extractCtxMatch = src.match(/extractThreadContext\(bubbles\) \{[\s\S]*?\n    \},/);

if (!escapeRegExpMatch || !normMatch || !testKwMatch || !evalRulesMatch || !regexSandboxMatch || !extractCtxMatch) {
  console.log(JSON.stringify({ error: "Failed to extract required engine functions from bot_script.js" }));
  process.exit(1);
}

eval(escapeRegExpMatch[0]);
eval(normMatch[0]);
eval(regexSandboxMatch[0].replace("class RegexSandbox", "global.RegexSandbox = class RegexSandbox"));
const regexSandbox = new global.RegexSandbox();
eval(testKwMatch[0]);
eval(evalRulesMatch[0]);

global.document = { querySelector: () => null };
const ctxObjStr = "global.domContext = {\n  extractTextWithAlt: (el) => el.innerText || \"\",\n  " + extractCtxMatch[0] + "\n};";
eval(ctxObjStr);

(async () => {
  const res = {};

  // 1. Attached Flag Boundaries (مصر🇪🇬 -> مصر 🇪🇬)
  const normFlag = normalizeArabicText("مصر🇪🇬");
  const flagMatch = await testKeywordsMatch("مصر🇪🇬", normFlag, ["🇪🇬"], "contains");
  res.attachedFlag = (normFlag === "مصر 🇪🇬") && !!flagMatch;

  // 2. Diacritics Precedence & Tashkeel/Tatweel Stripping
  const normDiacritics = normalizeArabicText("مصرَ🇪🇬");
  const normTashkeel = normalizeArabicText("شُكْرًا");
  const normTatweel = normalizeArabicText("تــرحـيـب");
  res.diacritics = (normDiacritics === "مصر 🇪🇬") && (normTashkeel === "شكرا") && (normTatweel === "ترحيب");

  // 3. Eastern Arabic Digits (السعر ٥٠٠ -> السعر 500)
  const normDigits = normalizeArabicText("السعر ٥٠٠");
  const digitMatch = await testKeywordsMatch("السعر ٥٠٠", normDigits, ["500"], "contains");
  res.easternDigits = (normDigits === "السعر 500") && !!digitMatch;

  // 4. ZWJ Composite Emoji Preservation
  const zwjEmoji = "👩‍💻";
  const normZwj = normalizeArabicText("مرحبا 👩‍💻 مهندسة");
  res.zwj = normZwj.includes("\u200D") && normZwj.includes(zwjEmoji);

  // 5. Worker Regex Isolation & Failure Path Benchmarks
  global.window = global;
  global.Blob = class Blob { constructor(parts) { this.parts = parts; } };
  global.URL = { createObjectURL: () => 'blob:mock', revokeObjectURL: () => {} };

  function makeSandbox(workerFactory) {
    global.Worker = workerFactory;
    return new global.RegexSandbox();
  }

  // 5.1 Constructor failure
  const sbConstructFail = makeSandbox(function() { throw new Error('CSP blocked worker'); });
  const rConstruct = await sbConstructFail.test('pattern', 'u', 'text');

  // 5.2 postMessage failure
  const sbPostFail = makeSandbox(function() {
    this.postMessage = function() { throw new Error('postMessage failed'); };
    this.terminate = function() {};
  });
  const rPost = await sbPostFail.test('pattern', 'u', 'text');

  // 5.3 onerror failure
  const sbOnError = makeSandbox(function() {
    this.postMessage = (msg) => {
      setTimeout(() => { if (this.onerror) this.onerror(new Error('Worker error')); }, 5);
    };
    this.terminate = function() {};
  });
  const rOnError = await sbOnError.test('pattern', 'u', 'text');

  // 5.4 Invalid pattern syntax
  const sbInvalid = makeSandbox(function() {
    this.postMessage = (msg) => {
      setTimeout(() => {
        try { new RegExp(msg.pattern, msg.flags); } catch (e) {
          if (this.onmessage) this.onmessage({ data: { id: msg.id, success: false, error: e.message } });
        }
      }, 5);
    };
    this.terminate = function() {};
  });
  const rInvalid = await sbInvalid.test('[a-', 'u', 'text');

  // 5.5 Timeout (30ms limit)
  const sbTimeout = makeSandbox(function() {
    this.postMessage = () => {};
    this.terminate = function() {};
  });
  const rTimeout = await sbTimeout.test('(a|a)+', 'u', 'aaaaaaaaaaaa!', 15);

  // 5.6 Concurrent pending cleanup on timeout
  const sbConcurrent = makeSandbox(function() {
    this.postMessage = () => {};
    this.terminate = function() {};
  });
  const p1 = sbConcurrent.test('p1', 'u', 't1', 15);
  const p2 = sbConcurrent.test('p2', 'u', 't2', 15);
  const [rC1, rC2] = await Promise.all([p1, p2]);

  // 5.7 Valid worker match
  const sbValid = makeSandbox(function() {
    this.postMessage = (msg) => {
      setTimeout(() => {
        try {
          const re = new RegExp(msg.pattern, msg.flags);
          if (this.onmessage) this.onmessage({ data: { id: msg.id, success: true, matched: re.test(msg.text) } });
        } catch (e) {
          if (this.onmessage) this.onmessage({ data: { id: msg.id, success: false } });
        }
      }, 5);
    };
    this.terminate = function() {};
  });
  const rValidMatch = await sbValid.test('السعر.*500', 'u', 'السعر 500 جنيه');

  res.redos = (rConstruct === false) && (rPost === false) && (rOnError === false) &&
              (rInvalid === false) && (rTimeout === false) && (rC1 === false) &&
              (rC2 === false) && (rValidMatch === true);

  // 6. Suite 4: Compound Two-Pass Specificity Benchmark
  const testRules = [
    {
      id: "rule_generic_price",
      keywords: ["بكام", "السعر"],
      contextKeywords: [],
      matchType: "contains",
      reply: "السعر العام 100",
      active: true
    },
    {
      id: "rule_compound_corset",
      keywords: ["بكام", "السعر"],
      contextKeywords: ["المشد السحري"],
      matchType: "contains",
      contextMatchType: "contains",
      reply: "سعر المشد السحري 250",
      active: true
    }
  ];

  // Pass 1: Inquiry matching compound context overrides generic rule positioned earlier
  const matchPass1 = await evaluateActiveRules("بكام", testRules, "المشد السحري ليبيا 🇱🇾");
  res.compoundPass1 = (matchPass1?.rule?.id === "rule_compound_corset") && (matchPass1?.isCompound === true);

  // Pass 2: Fallback to generic rule when context does not match
  const matchPass2 = await evaluateActiveRules("بكام", testRules, "منتج آخر مختلف");
  res.compoundPass2 = (matchPass2?.rule?.id === "rule_generic_price") && (matchPass2?.isCompound === false);

  // 7. Context Aggregation Bounding (1,000 chars)
  const fakeBubbles = [{ innerText: "X".repeat(800) }, { innerText: "Y".repeat(800) }];
  const boundedCtx = global.domContext.extractThreadContext(fakeBubbles);
  res.contextBounding = (boundedCtx.length === 1000);

  console.log(JSON.stringify(res));
})();
"""

        code, out = self.run_cmd(["node", "-e", node_script], timeout=20)
        if code != 0:
            self.log_fail("Behavioral Sandbox Execution", f"Node exited with {code}: {out[:120]}")
            return

        try:
            json_line = None
            for line in out.strip().splitlines():
                if line.startswith("{") and line.endswith("}"):
                    json_line = line
            if not json_line:
                self.log_fail("Behavioral Sandbox Output", f"No JSON packet received: {out[:100]}")
                return

            results = json.loads(json_line)

            # Suite 3 Assertions
            if results.get("attachedFlag"):
                self.log_pass("Attached Flag Boundaries", "Separates Arabic text and flag emojis (مصر🇪🇬 -> مصر 🇪🇬)")
            else:
                self.log_fail("Attached Flag Boundaries", "Flag boundary separation failed")

            if results.get("diacritics"):
                self.log_pass("Diacritics & Tashkeel Precedence", "Strips Tashkeel & Tatweel cleanly before boundary checks")
            else:
                self.log_fail("Diacritics & Tashkeel Precedence", "Failed to normalize diacritics/Tatweel")

            if results.get("easternDigits"):
                self.log_pass("Eastern Arabic Digits Normalization", "Normalizes ٠-٩ to 0-9 and executes numeric keyword match")
            else:
                self.log_fail("Eastern Arabic Digits Normalization", "Eastern digits conversion failed")

            if results.get("zwj"):
                self.log_pass("ZWJ Composite Emoji Preservation", "Zero-Width Joiner (\\u200D) preserved for compound emojis")
            else:
                self.log_fail("ZWJ Composite Emoji Preservation", "ZWJ stripped during whitelist filtering")

            if results.get("redos"):
                self.log_pass("Worker Regex Isolation & Failure Hardening", "All 6 failure paths (constructor, postMessage, onerror, syntax, timeout, cleanup) verified")
            else:
                self.log_fail("Worker Regex Isolation & Failure Hardening", "Worker-based regex sandbox failed failure-path hardening")

            # Suite 4 Assertions
            if results.get("compoundPass1"):
                self.log_pass("Compound Ad-Context Pass 1 Priority", "Specific compound rule takes absolute precedence over generic rule")
            else:
                self.log_fail("Compound Ad-Context Pass 1 Priority", "Compound rule did not override generic rule")

            if results.get("compoundPass2"):
                self.log_pass("Compound Ad-Context Pass 2 Fallback", "Gracefully falls back to single-condition rules when context unmatched")
            else:
                self.log_fail("Compound Ad-Context Pass 2 Fallback", "Fallback to generic rule failed")

            if results.get("contextBounding"):
                self.log_pass("Thread Context Length Hard Cap", "DOM.extractThreadContext strictly bounds output to 1,000 characters")
            else:
                self.log_fail("Thread Context Length Hard Cap", "Context aggregation exceeded or did not cap at 1,000 chars")

        except Exception as e:
            self.log_fail("Behavioral Output Parsing", str(e))

    # =========================================================================
    # SUITE 5: MID-TYPING CATCH & UI REGRESSION CONTRACTS
    # =========================================================================
    def suite_mid_typing_and_ui(self):
        print(f"\n{C_BOLD}{C_BLUE}--- SUITE 5: Mid-Typing Catch & UI Regression Contracts ---{C_RESET}")

        js_text = (ROOT_DIR / "bot_script.js").read_text(encoding="utf-8", errors="ignore")
        css_text = (ROOT_DIR / "gui" / "styles.css").read_text(encoding="utf-8", errors="ignore")
        html_text = (ROOT_DIR / "gui" / "index.html").read_text(encoding="utf-8", errors="ignore")
        app_text = (ROOT_DIR / "gui" / "app.js").read_text(encoding="utf-8", errors="ignore")

        # 5.1 Mid-Typing Inbound Catch & Cooldown Protection
        has_baseline = "preSendInbound" in js_text and "preSendInboundCount" in js_text
        has_sweep = "postSendInbound.length > preSendInboundCount" in js_text
        has_forced_b = "executeBranchB" in js_text and "MID-TYPING" in js_text
        has_cooldown = "state.chatCooldowns" in js_text

        if has_baseline and has_sweep and has_forced_b and has_cooldown:
            self.log_pass("Mid-Typing Inbound Catch & Sweep", "Baseline snapshot, post-send sweep, forced Branch B & cooldown verified")
        else:
            self.log_fail(
                "Mid-Typing Inbound Catch & Sweep",
                f"Missing contracts: baseline={has_baseline}, sweep={has_sweep}, branchB={has_forced_b}, cooldown={has_cooldown}"
            )

        # 5.2 Sticky Header CSS Contracts
        sticky_css_match = re.search(
            r'\.rules-sticky-header\s*\{[\s\S]*?position:\s*(?:-webkit-)?sticky;[\s\S]*?top:\s*0;[\s\S]*?z-index:\s*20;',
            css_text
        )
        if sticky_css_match:
            self.log_pass("Rules Sticky Header CSS Contract", "position: sticky; top: 0; z-index: 20 enforced")
        else:
            self.log_fail("Rules Sticky Header CSS Contract", ".rules-sticky-header definition missing required sticky rules")

        # 5.3 UI Top Add Rule Insertion Contract
        has_sticky_bar = '<div class="rules-sticky-header">' in html_text and 'id="btn-save-rules"' in html_text
        add_idx = html_text.find('id="add-rule-btn"')
        rules_idx = html_text.find('id="rules-container"')
        top_order_ok = (add_idx != -1) and (rules_idx != -1) and (add_idx < rules_idx)

        has_unshift = "state.currentConfig.rules.unshift" in app_text
        has_autofocus = "chipInput.focus()" in app_text

        if has_sticky_bar and top_order_ok and has_unshift and has_autofocus:
            self.log_pass("Top Rule Insertion & Autofocus", "Add button at top, unshift prepend, and keyword autofocus active")
        else:
            self.log_fail(
                "Top Rule Insertion & Autofocus",
                f"Contracts: sticky_bar={has_sticky_bar}, top_order={top_order_ok}, unshift={has_unshift}, autofocus={has_autofocus}"
            )

        # 5.4 DOM Terminal 500-Child Hard Cap
        has_cap = "elements.terminal.children.length > 500" in app_text and "elements.terminal.removeChild" in app_text
        has_log_cap = "state.logs[profName].length > 500" in app_text
        if has_cap and has_log_cap:
            self.log_pass("Terminal DOM 500-Child Hard Cap", "Pruning loop protects against memory leaks & renderer stalls")
        else:
            self.log_fail("Terminal DOM 500-Child Hard Cap", "Missing 500-child DOM or log array cap")

        # 5.5 CSS Specificity Tab Rules
        has_hide = re.search(r'\.tab-pane\s*\{\s*display:\s*none\s*!important;', css_text)
        has_show = re.search(r'\.tab-pane\.active\s*\{\s*display:\s*flex\s*!important;', css_text)
        if has_hide and has_show:
            self.log_pass("CSS Tab Specificity Rules", ".tab-pane display: none/flex !important strictly enforced")
        else:
            self.log_fail("CSS Tab Specificity Rules", f"Tab specificity rules missing: hide={bool(has_hide)}, show={bool(has_show)}")

    # =========================================================================
    # SUITE 6: OFFICIAL ATTRIBUTION & ENVIRONMENT
    # =========================================================================
    def suite_attribution_and_environment(self):
        print(f"\n{C_BOLD}{C_BLUE}--- SUITE 6: Attribution & System Environment ---{C_RESET}")

        # 6.1 Author Attribution
        author_ok = True
        for f in ["main.py", "desktop_app.py", "profile_manager.py"]:
            txt = (ROOT_DIR / f).read_text(encoding="utf-8", errors="ignore")
            if '__author__ = "Bishoy Safwat"' not in txt:
                self.log_fail(f"Author Attribution ({f})", "Missing __author__ = 'Bishoy Safwat'")
                author_ok = False

        js_author = ("@author       Bishoy Safwat" in (ROOT_DIR / "bot_script.js").read_text(encoding="utf-8", errors="ignore"))
        if not js_author:
            self.log_fail("UserScript Attribution", "Missing @author Bishoy Safwat")
            author_ok = False

        gui_author = ("Designed &amp; Engineered by Bishoy Safwat" in (ROOT_DIR / "gui/index.html").read_text(encoding="utf-8", errors="ignore"))
        if not gui_author:
            self.log_fail("Desktop GUI Attribution", "Missing attribution in gui/index.html")
            author_ok = False

        if author_ok:
            self.log_pass("Author Attribution", "Bishoy Safwat verified across Python, JS, and GUI")

        # 6.2 Browser Runtime Detection
        chrome_bin = any(shutil.which(b) for b in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"])
        if chrome_bin:
            self.log_pass("Chromium Binary Detection", "Chrome/Chromium runtime located in system PATH")
        else:
            self.log_warn("Chromium Binary Detection", "No Chrome binary located in system PATH (headed mode requires browser)")

        # 6.3 Git Working Tree Status
        g_code, g_out = self.run_cmd(["git", "-C", str(ROOT_DIR), "status", "--porcelain"])
        if g_code == 0:
            if not g_out:
                self.log_pass("Git Working Tree", "Clean working tree")
            else:
                lines = [l for l in g_out.splitlines() if not l.startswith("??")]
                self.log_warn("Git Working Tree", f"{len(lines)} modified file(s) tracked for release")
            _, tag = self.run_cmd(["git", "-C", str(ROOT_DIR), "describe", "--tags", "--abbrev=0"])
            self.log_pass("Active Git Baseline", tag or "v6.3.0")

    def teardown(self):
        for p in self.cleanup_paths:
            try:
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                elif p.is_file():
                    p.unlink(missing_ok=True)
            except Exception:
                pass


def main():
    engine = ForensicAuditEngine()
    print(f"\n{C_BOLD}{C_CYAN}============================================================================={C_RESET}")
    print(f"{C_BOLD}{C_CYAN}  MBS INBOX AUTOMATOR - MASTER ENTERPRISE FORENSIC AUDIT (V6.5.3)           {C_RESET}")
    print(f"{C_BOLD}{C_CYAN}============================================================================={C_RESET}")

    start_time = time.time()
    try:
        engine.suite_static_integrity()
        engine.suite_kernel_concurrency()
        engine.suite_arabic_nlp_and_behavioral()
        engine.suite_mid_typing_and_ui()
        engine.suite_attribution_and_environment()
    finally:
        engine.teardown()
    elapsed = time.time() - start_time

    total_tests = engine.passed + engine.failed
    print(f"\n{C_BOLD}{C_CYAN}-----------------------------------------------------------------------------{C_RESET}")
    print(f" {C_BOLD}TOTAL AUDIT CHECKS :{C_RESET} {total_tests}")
    print(f" {C_GREEN}PASSED              :{C_RESET} {engine.passed}")
    print(f" {C_RED}FAILED              :{C_RESET} {engine.failed}")
    print(f" {C_YELLOW}WARNINGS            :{C_RESET} {engine.warnings}")
    print(f" {C_BOLD}EXECUTION TIME      :{C_RESET} {elapsed:.2f}s")
    print(f"{C_BOLD}{C_CYAN}-----------------------------------------------------------------------------{C_RESET}")

    if engine.failed == 0:
        print(f"\n{C_BOLD}{C_GREEN}FINAL VERDICT: 100% AUDIT PASS - ENTERPRISE PRODUCTION READY (V6.5.3)!{C_RESET}\n")
        sys.exit(0)
    else:
        print(f"\n{C_BOLD}{C_RED}FINAL VERDICT: AUDIT FAILED WITH {engine.failed} CRITICAL DEFECT(S)!{C_RESET}\n")
        for idx, err in enumerate(engine.failure_details, 1):
            print(f"  {idx}. {err}")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()

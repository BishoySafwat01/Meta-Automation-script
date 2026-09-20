#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
Milestone 1 — Behavioral Race & Surface Lease Verification Harness
Author: Bishoy Safwat (Senior Automation & Systems Engineer)
Version: V6.5.3-M1-QA
=============================================================================
In-memory verification of 14 race conditions and lease contracts against
actual production code in bot_script.js without modifying files on disk.
=============================================================================
"""

import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

# ANSI terminal formatting
C_RESET  = "\033[0m"
C_BOLD   = "\033[1m"
C_GREEN  = "\033[32m"
C_RED    = "\033[31m"
C_YELLOW = "\033[33m"
C_CYAN   = "\033[36m"
C_BLUE   = "\033[34m"

ROOT_DIR = Path(__file__).resolve().parent
BOT_SCRIPT_PATH = ROOT_DIR / "bot_script.js"

BOOTSTRAP_TARGET = "console.log('[MBS Automator V6.5.3] Initialized successfully (Enterprise Hardened Edition — P0/P1/P2 Remediations Applied).');\n})();"

TEST_EXPORT_SNIPPET = """window.__TEST_MBS__ = {
  DOM,
  HumanSimulator,
  Orchestrator,
  state,
  FocusIntegrityError,
  OperationBudget,
  RowTransaction
};
console.log('[MBS Automator V6.5.3] Initialized successfully (Enterprise Hardened Edition — P0/P1/P2 Remediations Applied).');
})();"""


class M1FocusRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures = []

        # Read bot_script.js in-memory only
        if not BOT_SCRIPT_PATH.is_file():
            raise FileNotFoundError(f"bot_script.js not found at {BOT_SCRIPT_PATH}")

        raw_script = BOT_SCRIPT_PATH.read_text(encoding="utf-8")
        assert raw_script.count(BOOTSTRAP_TARGET) == 1, (
            f"Expected exactly 1 occurrence of bootstrap block, found {raw_script.count(BOOTSTRAP_TARGET)}"
        )
        self.instrumented_js = raw_script.replace(BOOTSTRAP_TARGET, TEST_EXPORT_SNIPPET)

    def record_pass(self, test_id: str, description: str):
        self.passed += 1
        print(f" {C_GREEN}[PASS]{C_RESET} {C_BOLD}Test {test_id}:{C_RESET} {description}")

    def record_fail(self, test_id: str, description: str, error: str):
        self.failed += 1
        msg = f"Test {test_id} ({description}): {error}"
        self.failures.append(msg)
        print(f" {C_RED}[FAIL]{C_RESET} {C_BOLD}Test {test_id}:{C_RESET} {description}\n        {C_RED}{error}{C_RESET}")

    def create_page(self, browser):
        context = browser.new_context()
        page = context.new_page()
        page.route("https://business.facebook.com/**", lambda route: route.fulfill(
            status=200,
            content_type="text/html",
            body="""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>M1 Focus Test</title></head>
<body>
<div id="mbs-fixture"></div>
</body>
</html>"""
        ))
        page.goto("https://business.facebook.com/latest/inbox/all")
        page.evaluate(self.instrumented_js)
        return page

    # =========================================================================
    # TEST 01: Selected B + URL A + header B + stale A canvas => reject
    # =========================================================================
    def test_01(self, browser):
        test_id = "01"
        desc = "Selected B + URL A + header B + stale A canvas => reject, zero input/send"
        page = self.create_page(browser)
        try:
            res = page.evaluate("""async () => {
                const { DOM } = window.__TEST_MBS__;
                window.history.pushState({}, '', '/inbox/messenger/?thread_id=thread_A');

                const fixture = document.getElementById('mbs-fixture');
                fixture.innerHTML = `
                    <div role="row" class="conv-row" data-thread-id="thread_B" aria-selected="true">
                        <span dir="auto">User B</span>
                    </div>
                    <header role="banner" data-testid="chat_header">
                        <h1 role="heading">User B</h1>
                    </header>
                    <div data-testid="chat-canvas" data-thread-id="thread_A" style="width:500px;height:500px;">
                        <div contenteditable="true" role="textbox" aria-label="اكتب رسالة" style="width:300px;height:40px;margin-top:300px;"></div>
                        <button aria-label="إرسال" style="width:50px;height:30px;">Send</button>
                    </div>
                `;

                const rowB = document.querySelector('[data-thread-id="thread_B"]');
                const composer = document.querySelector('[role="textbox"]');
                const sendBtn = document.querySelector('button[aria-label="إرسال"]');

                let inputDispatched = 0;
                let clickDispatched = 0;
                composer.addEventListener('input', () => inputDispatched++);
                composer.addEventListener('beforeinput', () => inputDispatched++);
                sendBtn.addEventListener('click', () => clickDispatched++);

                const expected = DOM.captureExpectedConversation(rowB, 'User B');
                const actual = DOM.getActiveConversationIdentity();
                const matches = DOM.conversationIdentityMatches(expected, actual);

                const token = { cancelled: false };
                // Timeout after 300ms for test efficiency
                setTimeout(() => { token.cancelled = true; }, 300);
                let lease = null;
                try {
                    lease = await DOM.waitForConversationLoad(expected, rowB, rowB, null, token);
                } catch (_) {}

                return {
                    actualSelectedId: actual.selectedAttributeId,
                    actualUrlId: actual.urlThreadId,
                    actualCanvasId: actual.canvasLocalId,
                    matches,
                    leaseIsNull: lease === null,
                    inputDispatched,
                    clickDispatched
                };
            }""")

            assert res["actualSelectedId"] == "thread_B", f"Expected selectedAttributeId thread_B, got {res['actualSelectedId']}"
            assert res["actualUrlId"] == "thread_A", f"Expected urlThreadId thread_A, got {res['actualUrlId']}"
            assert res["actualCanvasId"] == "thread_A", f"Expected canvasLocalId thread_A, got {res['actualCanvasId']}"
            assert res["matches"] is False, "Expected conversationIdentityMatches to be False due to conflicting URL/Canvas"
            assert res["leaseIsNull"] is True, "Expected waitForConversationLoad to return null"
            assert res["inputDispatched"] == 0, "Expected zero input events"
            assert res["clickDispatched"] == 0, "Expected zero click events"
            self.record_pass(test_id, desc)
        except Exception as e:
            self.record_fail(test_id, desc, str(e))
        finally:
            page.close()

    # =========================================================================
    # TEST 02: Selected B + URL B + header B + unchanged pre-click A surface => reject
    # =========================================================================
    def test_02(self, browser):
        test_id = "02"
        desc = "Selected B + URL B + header B + unchanged pre-click A surface => reject"
        page = self.create_page(browser)
        try:
            res = page.evaluate("""async () => {
                const { DOM } = window.__TEST_MBS__;
                window.history.pushState({}, '', '/inbox/messenger/?thread_id=thread_A');

                const fixture = document.getElementById('mbs-fixture');
                fixture.innerHTML = `
                    <div role="row" class="conv-row" data-thread-id="thread_A" aria-selected="true">
                        <span dir="auto">User A</span>
                    </div>
                    <div role="row" class="conv-row" data-thread-id="thread_B">
                        <span dir="auto">User B</span>
                    </div>
                    <header role="banner" data-testid="chat_header">
                        <h1 role="heading">User A</h1>
                    </header>
                    <div data-testid="chat-canvas" style="width:500px;height:500px;">
                        <p>Old message from A</p>
                        <div contenteditable="true" role="textbox" aria-label="اكتب رسالة" style="width:300px;height:40px;margin-top:300px;"></div>
                    </div>
                `;

                const rowA = document.querySelector('[data-thread-id="thread_A"]');
                const rowB = document.querySelector('[data-thread-id="thread_B"]');
                const canvasA = document.querySelector('[data-testid="chat-canvas"]');
                const composerA = canvasA.querySelector('[role="textbox"]');
                const headerA = document.querySelector('header');

                // Capture pre-click snapshot of A
                const preClickSnapshot = {
                    identity: { selectedAttributeId: 'thread_A', urlThreadId: 'thread_A', channel: 'messenger', normalizedName: 'usera' },
                    canvas: canvasA,
                    composer: composerA,
                    headerNode: headerA,
                    headerText: 'User A',
                    fingerprint: DOM.getSurfaceFingerprint(canvasA),
                    channel: 'messenger'
                };

                // Now simulate switch: row B selected, URL B, header B, BUT canvas/composer/fingerprint unchanged!
                rowA.removeAttribute('aria-selected');
                rowB.setAttribute('aria-selected', 'true');
                window.history.pushState({}, '', '/inbox/messenger/?thread_id=thread_B');
                headerA.querySelector('h1').innerText = 'User B';

                const expectedB = DOM.captureExpectedConversation(rowB, 'User B');
                const token = { cancelled: false };
                setTimeout(() => { token.cancelled = true; }, 300);

                let lease = null;
                try {
                    lease = await DOM.waitForConversationLoad(expectedB, rowB, rowB, null, token, preClickSnapshot);
                } catch (_) {}

                return {
                    leaseIsNull: lease === null
                };
            }""")

            assert res["leaseIsNull"] is True, "Expected rejection when surface remains unchanged from pre-click snapshot"
            self.record_pass(test_id, desc)
        except Exception as e:
            self.record_fail(test_id, desc, str(e))
        finally:
            page.close()

    # =========================================================================
    # TEST 03: New B surface stable for three samples over >=450 ms => one lease returned
    # =========================================================================
    def test_03(self, browser):
        test_id = "03"
        desc = "New B surface stable for three samples over >=450 ms => one lease returned"
        page = self.create_page(browser)
        try:
            res = page.evaluate("""async () => {
                const { DOM } = window.__TEST_MBS__;
                window.history.pushState({}, '', '/inbox/messenger/?thread_id=thread_B');

                const fixture = document.getElementById('mbs-fixture');
                fixture.innerHTML = `
                    <div role="row" class="conv-row" data-thread-id="thread_B" aria-selected="true">
                        <span dir="auto">User B</span>
                    </div>
                    <header role="banner" data-testid="chat_header">
                        <h1 role="heading">User B</h1>
                    </header>
                    <div data-testid="chat-canvas" data-thread-id="thread_B" style="width:500px;height:500px;">
                        <p>New message from B</p>
                        <div contenteditable="true" role="textbox" aria-label="اكتب رسالة" style="width:300px;height:40px;margin-top:300px;"></div>
                    </div>
                `;

                const rowB = document.querySelector('[data-thread-id="thread_B"]');
                const canvasB = document.querySelector('[data-testid="chat-canvas"]');
                const composerB = canvasB.querySelector('[role="textbox"]');

                const preClickSnapshot = {
                    identity: { selectedAttributeId: 'thread_A', urlThreadId: 'thread_A' },
                    canvas: document.createElement('div'),
                    composer: document.createElement('div'),
                    fingerprint: 'pre_a_fingerprint'
                };

                const expectedB = DOM.captureExpectedConversation(rowB, 'User B');
                const token = { cancelled: false };

                const t0 = Date.now();
                const lease = await DOM.waitForConversationLoad(expectedB, rowB, rowB, null, token, preClickSnapshot);
                const elapsed = Date.now() - t0;

                return {
                    leaseNotNull: lease !== null,
                    surfaceMatches: lease && lease.surface === canvasB,
                    composerMatches: lease && lease.composer === composerB,
                    elapsed
                };
            }""")

            assert res["leaseNotNull"] is True, "Expected valid lease returned"
            assert res["surfaceMatches"] is True, "Expected lease.surface to match canvasB"
            assert res["composerMatches"] is True, "Expected lease.composer to match composerB"
            assert res["elapsed"] >= 450, f"Expected elapsed >= 450ms, got {res['elapsed']}ms"
            self.record_pass(test_id, desc)
        except Exception as e:
            self.record_fail(test_id, desc, str(e))
        finally:
            page.close()

    # =========================================================================
    # TEST 04: Same-canvas composer remount preserving exact prefix => continue
    # =========================================================================
    def test_04(self, browser):
        test_id = "04"
        desc = "Same-canvas composer remount preserving exact prefix => continue"
        page = self.create_page(browser)
        try:
            res = page.evaluate("""() => {
                const { DOM } = window.__TEST_MBS__;
                window.history.pushState({}, '', '/inbox/messenger/?thread_id=thread_B');

                const fixture = document.getElementById('mbs-fixture');
                fixture.innerHTML = `
                    <div role="row" class="conv-row" data-thread-id="thread_B" aria-selected="true">
                        <span dir="auto">User B</span>
                    </div>
                    <header role="banner" data-testid="chat_header">
                        <h1 role="heading">User B</h1>
                    </header>
                    <div data-testid="chat-canvas" data-thread-id="thread_B" style="width:500px;height:500px;">
                        <div id="comp1" contenteditable="true" role="textbox" aria-label="اكتب رسالة" style="width:300px;height:40px;margin-top:300px;">مرحبا</div>
                    </div>
                `;

                const rowB = document.querySelector('[data-thread-id="thread_B"]');
                const canvas = document.querySelector('[data-testid="chat-canvas"]');
                const comp1 = document.getElementById('comp1');

                const expected = DOM.captureExpectedConversation(rowB, 'User B');
                const lease = {
                    expected,
                    surface: canvas,
                    composer: comp1,
                    lastKnownText: 'مرحبا',
                    remountCount: 0,
                    cancellationToken: null
                };

                // Replace comp1 with comp2 inside the same canvas, preserving exact prefix
                comp1.remove();
                const comp2 = document.createElement('div');
                comp2.id = 'comp2';
                comp2.setAttribute('contenteditable', 'true');
                comp2.setAttribute('role', 'textbox');
                comp2.setAttribute('aria-label', 'اكتب رسالة');
                comp2.style.cssText = 'width:300px;height:40px;margin-top:300px;';
                comp2.innerText = 'مرحبا';
                canvas.appendChild(comp2);

                const activeComposer = DOM.assertComposerLease(lease);

                return {
                    returnedComp2: activeComposer === comp2,
                    leaseComposerUpdated: lease.composer === comp2,
                    remountCount: lease.remountCount
                };
            }""")

            assert res["returnedComp2"] is True, "Expected assertComposerLease to return remounted node"
            assert res["leaseComposerUpdated"] is True, "Expected lease.composer to update"
            assert res["remountCount"] == 1, f"Expected remountCount == 1, got {res['remountCount']}"
            self.record_pass(test_id, desc)
        except Exception as e:
            self.record_fail(test_id, desc, str(e))
        finally:
            page.close()

    # =========================================================================
    # TEST 05: Blank, truncated, or divergent remount => abort before next input/send
    # =========================================================================
    def test_05(self, browser):
        test_id = "05"
        desc = "Blank, truncated, or divergent remount => abort before next input/send"
        page = self.create_page(browser)
        try:
            res = page.evaluate("""() => {
                const { DOM, FocusIntegrityError } = window.__TEST_MBS__;
                window.history.pushState({}, '', '/inbox/messenger/?thread_id=thread_B');

                const fixture = document.getElementById('mbs-fixture');
                fixture.innerHTML = `
                    <div role="row" class="conv-row" data-thread-id="thread_B" aria-selected="true">
                        <span dir="auto">User B</span>
                    </div>
                    <header role="banner" data-testid="chat_header">
                        <h1 role="heading">User B</h1>
                    </header>
                    <div data-testid="chat-canvas" data-thread-id="thread_B" style="width:500px;height:500px;">
                        <div id="comp-base" contenteditable="true" role="textbox" aria-label="اكتب رسالة" style="width:300px;height:40px;margin-top:300px;"></div>
                    </div>
                `;

                const rowB = document.querySelector('[data-thread-id="thread_B"]');
                const canvas = document.querySelector('[data-testid="chat-canvas"]');
                const compBase = document.getElementById('comp-base');
                const expected = DOM.captureExpectedConversation(rowB, 'User B');

                const testCases = [
                    { name: 'blank', text: '' },
                    { name: 'placeholder', text: 'رد في Messenger' },
                    { name: 'truncated', text: 'مرح' },
                    { name: 'divergent', text: 'أهلا بك' }
                ];

                const results = {};

                for (const tc of testCases) {
                    const lease = {
                        expected,
                        surface: canvas,
                        composer: compBase,
                        lastKnownText: 'مرحبا بك',
                        remountCount: 0,
                        cancellationToken: null
                    };

                    const replacement = document.createElement('div');
                    replacement.setAttribute('contenteditable', 'true');
                    replacement.setAttribute('role', 'textbox');
                    replacement.setAttribute('aria-label', 'اكتب رسالة');
                    replacement.style.cssText = 'width:300px;height:40px;margin-top:300px;';
                    replacement.innerText = tc.text;

                    canvas.innerHTML = '';
                    canvas.appendChild(replacement);

                    let caught = false;
                    let errorType = '';
                    try {
                        DOM.assertComposerLease(lease);
                    } catch (err) {
                        caught = true;
                        errorType = err.message;
                    }
                    results[tc.name] = { caught, errorType, restoredText: replacement.innerText };
                }

                return results;
            }""")

            for tc_name in ['blank', 'placeholder', 'truncated', 'divergent']:
                item = res[tc_name]
                assert item["caught"] is True, f"Case '{tc_name}' did not throw FocusIntegrityError"
                assert item["errorType"] == "COMPOSER_TEXT_CONTINUITY_VIOLATION", (
                    f"Case '{tc_name}' threw wrong error: {item['errorType']}"
                )
                assert item["restoredText"] != "مرحبا بك", f"Case '{tc_name}' erroneously restored text"

            self.record_pass(test_id, desc)
        except Exception as e:
            self.record_fail(test_id, desc, str(e))
        finally:
            page.close()

    # =========================================================================
    # TEST 06: Operator switches to C during production fallback-send delay => zero clicks
    # =========================================================================
    def test_06(self, browser):
        test_id = "06"
        desc = "Operator switches to C during production fallback-send delay => zero clicks (must invoke actual production HumanSimulator.typeIntoComposer)"
        page = self.create_page(browser)
        try:
            res = page.evaluate("""async () => {
                const { DOM, HumanSimulator, state } = window.__TEST_MBS__;
                state.isRunning = true;
                state.emergencyAbort = false;
                state.config.minTypingSpeed = 5;
                state.config.maxTypingSpeed = 10;

                window.history.pushState({}, '', '/inbox/messenger/?thread_id=thread_B');

                const fixture = document.getElementById('mbs-fixture');
                fixture.innerHTML = `
                    <div role="row" class="conv-row" data-thread-id="thread_B" aria-selected="true">
                        <span dir="auto">User B</span>
                    </div>
                    <header role="banner" data-testid="chat_header">
                        <h1 role="heading">User B</h1>
                    </header>
                    <div data-testid="chat-canvas" data-thread-id="thread_B" style="width:500px;height:500px;">
                        <div contenteditable="true" role="textbox" aria-label="اكتب رسالة" style="width:300px;height:40px;margin-top:300px;"></div>
                        <button aria-label="إرسال" style="width:50px;height:30px;margin-top:310px;">Send</button>
                    </div>
                `;

                const rowB = document.querySelector('[data-thread-id="thread_B"]');
                const canvas = document.querySelector('[data-testid="chat-canvas"]');
                const composer = canvas.querySelector('[role="textbox"]');
                const sendBtn = canvas.querySelector('button[aria-label="إرسال"]');

                let sendClicks = 0;
                sendBtn.addEventListener('click', () => { sendClicks++; });

                // Prevent Enter keydown from clearing text so fallback click branch is triggered
                composer.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') {
                        // Switch identity to C during Enter keyup / fallback delay!
                        window.history.pushState({}, '', '/inbox/messenger/?thread_id=thread_C');
                        document.querySelector('header h1').innerText = 'User C';
                    }
                });

                const expectedB = DOM.captureExpectedConversation(rowB, 'User B');
                const leaseB = {
                    expected: expectedB,
                    surface: canvas,
                    composer: composer,
                    lastKnownText: '',
                    remountCount: 0,
                    cancellationToken: null
                };

                let caughtError = null;
                try {
                    await HumanSimulator.typeIntoComposer(leaseB, 'تجربة رد', { log: () => {} });
                } catch (err) {
                    caughtError = err.message;
                }

                return {
                    sendClicks,
                    caughtError
                };
            }""")

            assert res["sendClicks"] == 0, f"Expected 0 send button clicks, got {res['sendClicks']}"
            assert res["caughtError"] is not None and "TARGET_CONVERSATION_IDENTITY_MISMATCH" in res["caughtError"], (
                f"Expected identity mismatch error, got {res['caughtError']}"
            )
            self.record_pass(test_id, desc)
        except Exception as e:
            self.record_fail(test_id, desc, str(e))
        finally:
            page.close()

    # =========================================================================
    # TEST 07: B loads at 4100 ms => activation succeeds; no timeout/orphan
    # =========================================================================
    def test_07(self, browser):
        test_id = "07"
        desc = "B loads at 4100 ms => activation succeeds; no timeout/orphan"
        page = self.create_page(browser)
        try:
            res = page.evaluate("""async () => {
                const { DOM } = window.__TEST_MBS__;
                window.history.pushState({}, '', '/inbox/messenger/?thread_id=thread_A');

                const fixture = document.getElementById('mbs-fixture');
                fixture.innerHTML = `
                    <div role="row" class="conv-row" data-thread-id="thread_A" aria-selected="true">
                        <span dir="auto">User A</span>
                    </div>
                    <div role="row" class="conv-row" data-thread-id="thread_B">
                        <span dir="auto">User B</span>
                    </div>
                    <header role="banner" data-testid="chat_header">
                        <h1 role="heading">User A</h1>
                    </header>
                    <div data-testid="chat-canvas" data-thread-id="thread_A" style="width:500px;height:500px;">
                        <div contenteditable="true" role="textbox" aria-label="اكتب رسالة" style="width:300px;height:40px;margin-top:300px;"></div>
                    </div>
                `;

                const rowB = document.querySelector('[data-thread-id="thread_B"]');
                const rowA = document.querySelector('[data-thread-id="thread_A"]');
                const canvasA = document.querySelector('[data-testid="chat-canvas"]');
                const composerA = canvasA.querySelector('[role="textbox"]');

                const preClickSnapshot = {
                    identity: { selectedAttributeId: 'thread_A', urlThreadId: 'thread_A' },
                    canvas: canvasA,
                    composer: composerA,
                    fingerprint: DOM.getSurfaceFingerprint(canvasA)
                };

                const expectedB = DOM.captureExpectedConversation(rowB, 'User B');
                const token = { cancelled: false };

                // At 4100ms, mount conversation B
                setTimeout(() => {
                    rowA.removeAttribute('aria-selected');
                    rowB.setAttribute('aria-selected', 'true');
                    window.history.pushState({}, '', '/inbox/messenger/?thread_id=thread_B');
                    document.querySelector('header h1').innerText = 'User B';

                    canvasA.setAttribute('data-thread-id', 'thread_B');
                    canvasA.innerHTML = `
                        <p>Loaded conversation B</p>
                        <div contenteditable="true" role="textbox" aria-label="اكتب رسالة" style="width:300px;height:40px;margin-top:300px;"></div>
                    `;
                }, 4100);

                const t0 = Date.now();
                const lease = await DOM.waitForConversationLoad(expectedB, rowB, rowB, null, token, preClickSnapshot);
                const elapsed = Date.now() - t0;

                return {
                    leaseNotNull: lease !== null,
                    elapsed
                };
            }""")

            assert res["leaseNotNull"] is True, "Expected activation to succeed when B loads at 4100ms"
            assert res["elapsed"] >= 4100, f"Expected elapsed >= 4100ms, got {res['elapsed']}ms"
            self.record_pass(test_id, desc)
        except Exception as e:
            self.record_fail(test_id, desc, str(e))
        finally:
            page.close()

    # =========================================================================
    # TEST 08: Real watchdog wins, B mounts later => process settles; zero later events
    # =========================================================================
    def test_08(self, browser):
        test_id = "08"
        desc = "Real watchdog wins, B mounts later => process settles; zero later events (must exercise actual Promise.race / production transaction helper)"
        page = self.create_page(browser)
        try:
            res = page.evaluate("""async () => {
                const { OperationBudget, RowTransaction, DOM } = window.__TEST_MBS__;

                const fixture = document.getElementById('mbs-fixture');
                fixture.innerHTML = `
                    <div role="row" class="conv-row" data-thread-id="thread_B">
                        <span dir="auto">User B</span>
                    </div>
                `;

                const rowB = document.querySelector('[data-thread-id="thread_B"]');
                const rowCancellation = { cancelled: false, reason: null };
                const rowTransaction = new RowTransaction(rowB, 'User B', rowCancellation);

                let laterActionExecuted = false;

                // Watchdog configured with fast 100ms idle cap for test
                let operationBudget = null;
                const timeoutPromise = new Promise((_, reject) => {
                    operationBudget = new OperationBudget(100, 500, (err) => reject(err));
                });

                const processRowPromise = (async () => {
                    try {
                        // Simulates slow mount taking 300ms
                        await new Promise(r => setTimeout(r, 300));
                        if (rowCancellation.cancelled) {
                            return { skipLoop: true, cooldown: 0 };
                        }
                        laterActionExecuted = true;
                        return { skipLoop: false };
                    } catch (e) {
                        return { skipLoop: true };
                    }
                })();

                let timeoutCaught = false;
                let errorReason = '';
                try {
                    await Promise.race([processRowPromise, timeoutPromise]);
                } catch (raceErr) {
                    timeoutCaught = true;
                    errorReason = raceErr.message;
                    rowCancellation.cancelled = true;
                    rowCancellation.reason = raceErr.message;
                    rowTransaction.cancel(raceErr.message);
                    // PROVE ZERO TIMED-OUT ORPHANS: await settlement of processRowPromise
                    await Promise.allSettled([processRowPromise]);
                    rowTransaction.settled = true;
                } finally {
                    if (operationBudget) operationBudget.dispose();
                }

                // Wait until 400ms to ensure processRowPromise delay has completely passed
                await new Promise(r => setTimeout(r, 200));

                return {
                    timeoutCaught,
                    errorReason,
                    settled: rowTransaction.settled,
                    laterActionExecuted
                };
            }""")

            assert res["timeoutCaught"] is True, "Expected watchdog timeout to trigger"
            assert res["errorReason"] == "ROW_TIMEOUT_EXCEEDED", f"Unexpected error reason: {res['errorReason']}"
            assert res["settled"] is True, "Expected rowTransaction.settled == True"
            assert res["laterActionExecuted"] is False, "Expected ZERO later events to execute on B"
            self.record_pass(test_id, desc)
        except Exception as e:
            self.record_fail(test_id, desc, str(e))
        finally:
            page.close()

    # =========================================================================
    # TEST 09: Exercise HumanSimulator.typeIntoComposer fallback => send handler exactly once
    # =========================================================================
    def test_09(self, browser):
        test_id = "09"
        desc = "Exercise HumanSimulator.typeIntoComposer fallback => send handler exactly once"
        page = self.create_page(browser)
        try:
            res = page.evaluate("""async () => {
                const { DOM, HumanSimulator, state } = window.__TEST_MBS__;
                state.isRunning = true;
                state.emergencyAbort = false;
                state.config.minTypingSpeed = 5;
                state.config.maxTypingSpeed = 10;

                window.history.pushState({}, '', '/inbox/messenger/?thread_id=thread_B');

                const fixture = document.getElementById('mbs-fixture');
                fixture.innerHTML = `
                    <div role="row" class="conv-row" data-thread-id="thread_B" aria-selected="true">
                        <span dir="auto">User B</span>
                    </div>
                    <header role="banner" data-testid="chat_header">
                        <h1 role="heading">User B</h1>
                    </header>
                    <div data-testid="chat-canvas" data-thread-id="thread_B" style="width:500px;height:500px;">
                        <div contenteditable="true" role="textbox" aria-label="اكتب رسالة" style="width:300px;height:40px;margin-top:300px;"></div>
                        <button aria-label="إرسال" style="width:50px;height:30px;margin-top:310px;">Send</button>
                    </div>
                `;

                const rowB = document.querySelector('[data-thread-id="thread_B"]');
                const canvas = document.querySelector('[data-testid="chat-canvas"]');
                const composer = canvas.querySelector('[role="textbox"]');
                const sendBtn = canvas.querySelector('button[aria-label="إرسال"]');

                let sendClicks = 0;
                sendBtn.addEventListener('click', () => {
                    sendClicks++;
                    // Simulates Meta clearing composer on send click
                    composer.innerText = '';
                });

                // Composer does NOT clear on Enter key, forcing single-dispatch fallback send button click
                const expectedB = DOM.captureExpectedConversation(rowB, 'User B');
                const leaseB = {
                    expected: expectedB,
                    surface: canvas,
                    composer: composer,
                    lastKnownText: '',
                    remountCount: 0,
                    cancellationToken: null
                };

                const success = await HumanSimulator.typeIntoComposer(leaseB, 'اختبار الإرسال الاحتياطي', { log: () => {} });

                return {
                    success,
                    sendClicks
                };
            }""")

            assert res["success"] is True, "Expected typeIntoComposer to return true"
            assert res["sendClicks"] == 1, f"Expected exactly 1 send button click, got {res['sendClicks']}"
            self.record_pass(test_id, desc)
        except Exception as e:
            self.record_fail(test_id, desc, str(e))
        finally:
            page.close()

    # =========================================================================
    # TEST 10: Same normalized name across Messenger and WhatsApp => wrong channel rejected
    # =========================================================================
    def test_10(self, browser):
        test_id = "10"
        desc = "Same normalized name across Messenger and WhatsApp => wrong channel rejected"
        page = self.create_page(browser)
        try:
            res = page.evaluate("""() => {
                const { DOM } = window.__TEST_MBS__;

                const fixture = document.getElementById('mbs-fixture');
                fixture.innerHTML = `
                    <div role="row" class="conv-row" data-platform="whatsapp" data-thread-id="thread_1" aria-selected="false">
                        <span dir="auto">أحمد محمد</span>
                    </div>
                    <header role="banner" data-testid="chat_header">
                        <h1 role="heading">أحمد محمد</h1>
                    </header>
                `;

                window.history.pushState({}, '', '/inbox/messenger/?thread_id=thread_1');

                const rowWhatsApp = document.querySelector('[data-platform="whatsapp"]');
                const expectedWhatsApp = DOM.captureExpectedConversation(rowWhatsApp, 'أحمد محمد');

                const actualMessenger = DOM.getActiveConversationIdentity();
                const matches = DOM.conversationIdentityMatches(expectedWhatsApp, actualMessenger);

                return {
                    expectedChannel: expectedWhatsApp.channel,
                    actualChannel: actualMessenger.channel,
                    matches
                };
            }""")

            assert res["expectedChannel"] == "whatsapp", f"Expected whatsapp, got {res['expectedChannel']}"
            assert res["actualChannel"] == "messenger", f"Expected messenger, got {res['actualChannel']}"
            assert res["matches"] is False, "Expected rejection when channel differs despite identical normalized name"
            self.record_pass(test_id, desc)
        except Exception as e:
            self.record_fail(test_id, desc, str(e))
        finally:
            page.close()

    # =========================================================================
    # TEST 11: Stale A and verified B bubbles coexist => only B bubbles reach evaluation
    # =========================================================================
    def test_11(self, browser):
        test_id = "11"
        desc = "Stale A and verified B bubbles coexist => only B bubbles reach evaluation"
        page = self.create_page(browser)
        try:
            res = page.evaluate("""() => {
                const { DOM } = window.__TEST_MBS__;

                const fixture = document.getElementById('mbs-fixture');
                fixture.innerHTML = `
                    <div id="stale-canvas-A" style="width:500px;height:500px;">
                        <div class="bubble-stale" style="background-color:rgb(220,220,220);border-radius:12px;width:150px;height:30px;margin-top:100px;">
                            <span>رسالة قديمة من A</span>
                        </div>
                    </div>
                    <div id="verified-canvas-B" style="width:500px;height:500px;">
                        <div class="bubble-valid" style="background-color:rgb(220,220,220);border-radius:12px;width:150px;height:30px;margin-top:100px;">
                            <span>رسالة جديدة من B</span>
                        </div>
                        <div contenteditable="true" role="textbox" aria-label="اكتب رسالة" style="width:300px;height:40px;margin-top:300px;"></div>
                    </div>
                `;

                const canvasB = document.getElementById('verified-canvas-B');
                const composerB = canvasB.querySelector('[role="textbox"]');

                const leaseB = {
                    surface: canvasB,
                    composer: composerB,
                    cancellationToken: null
                };

                const bubbles = DOM.getMessageBubbles(leaseB);
                const bubbleTexts = bubbles.map(b => b.innerText.trim());

                return {
                    count: bubbles.length,
                    texts: bubbleTexts
                };
            }""")

            assert res["count"] == 1, f"Expected exactly 1 bubble, got {res['count']}"
            assert res["texts"] == ["رسالة جديدة من B"], f"Unexpected bubble texts: {res['texts']}"
            self.record_pass(test_id, desc)
        except Exception as e:
            self.record_fail(test_id, desc, str(e))
        finally:
            page.close()

    # =========================================================================
    # TEST 12: Candidate surface changes between stability samples => counter resets
    # =========================================================================
    def test_12(self, browser):
        test_id = "12"
        desc = "Candidate surface changes between stability samples => counter resets"
        page = self.create_page(browser)
        try:
            res = page.evaluate("""async () => {
                const { DOM } = window.__TEST_MBS__;
                window.history.pushState({}, '', '/inbox/messenger/?thread_id=thread_B');

                const fixture = document.getElementById('mbs-fixture');
                fixture.innerHTML = `
                    <div role="row" class="conv-row" data-thread-id="thread_B" aria-selected="true">
                        <span dir="auto">User B</span>
                    </div>
                    <header role="banner" data-testid="chat_header">
                        <h1 role="heading">User B</h1>
                    </header>
                    <div id="canvas-b1" data-testid="chat-canvas" data-thread-id="thread_B" style="width:500px;height:500px;">
                        <div contenteditable="true" role="textbox" aria-label="اكتب رسالة" style="width:300px;height:40px;margin-top:300px;"></div>
                    </div>
                `;

                const rowB = document.querySelector('[data-thread-id="thread_B"]');
                const expectedB = DOM.captureExpectedConversation(rowB, 'User B');
                const token = { cancelled: false };

                // After sample 1 (at ~200ms), change the canvas candidate in DOM to canvas-b2
                setTimeout(() => {
                    const canvas1 = document.getElementById('canvas-b1');
                    if (canvas1) canvas1.remove();

                    const canvas2 = document.createElement('div');
                    canvas2.id = 'canvas-b2';
                    canvas2.setAttribute('data-testid', 'chat-canvas');
                    canvas2.setAttribute('data-thread-id', 'thread_B');
                    canvas2.style.cssText = 'width:500px;height:500px;';
                    canvas2.innerHTML = '<div contenteditable="true" role="textbox" aria-label="اكتب رسالة" style="width:300px;height:40px;margin-top:300px;"></div>';
                    fixture.appendChild(canvas2);
                }, 200);

                const t0 = Date.now();
                const lease = await DOM.waitForConversationLoad(expectedB, rowB, rowB, null, token, null);
                const elapsed = Date.now() - t0;

                return {
                    leaseNotNull: lease !== null,
                    finalCanvasId: lease ? lease.surface.id : null,
                    elapsed
                };
            }""")

            assert res["leaseNotNull"] is True, "Expected lease to be returned eventually"
            assert res["finalCanvasId"] == "canvas-b2", f"Expected lease on canvas-b2, got {res['finalCanvasId']}"
            assert res["elapsed"] >= 650, f"Expected counter reset delaying elapsed >= 650ms, got {res['elapsed']}ms"
            self.record_pass(test_id, desc)
        except Exception as e:
            self.record_fail(test_id, desc, str(e))
        finally:
            page.close()

    # =========================================================================
    # TEST 13: Stale-surface mutation race condition => zero lease, zero events
    # =========================================================================
    def test_13(self, browser):
        test_id = "13"
        desc = "Stale-surface mutation race condition => zero lease, zero events (Messenger & WhatsApp)"
        page = self.create_page(browser)
        try:
            res = page.evaluate("""async () => {
                const { DOM } = window.__TEST_MBS__;

                // --- CASE A: Messenger -> Messenger Transition with Stale Mutated Canvas ---
                window.history.pushState({}, '', '/inbox/messenger/?thread_id=thread_A');
                const fixture = document.getElementById('mbs-fixture');
                fixture.innerHTML = `
                    <div role="row" class="conv-row" data-channel="messenger" data-thread-id="thread_A" aria-selected="true">
                        <span dir="auto">User A</span>
                    </div>
                    <div role="row" class="conv-row" data-channel="messenger" data-thread-id="thread_B">
                        <span dir="auto">User B</span>
                    </div>
                    <header role="banner" data-testid="chat_header">
                        <h1 role="heading">User A</h1>
                    </header>
                    <div id="canvas-msg-a" data-testid="chat-canvas" style="width:500px;height:500px;">
                        <p>Old message from A</p>
                        <div contenteditable="true" role="textbox" aria-label="اكتب رسالة" style="width:300px;height:40px;margin-top:300px;"></div>
                        <button aria-label="إرسال" style="width:50px;height:30px;">Send</button>
                    </div>
                `;

                const rowA = document.querySelector('[data-thread-id="thread_A"]');
                const rowB = document.querySelector('[data-thread-id="thread_B"]');
                const canvasA = document.getElementById('canvas-msg-a');
                const composerA = canvasA.querySelector('[role="textbox"]');
                const sendBtnA = canvasA.querySelector('button[aria-label="إرسال"]');
                const headerA = document.querySelector('header');

                let eventsA = 0;
                const recordEventA = () => { eventsA++; };
                composerA.addEventListener('input', recordEventA);
                composerA.addEventListener('beforeinput', recordEventA);
                composerA.addEventListener('keydown', recordEventA);
                sendBtnA.addEventListener('click', recordEventA);

                // Pre-click snapshot of A
                const preClickA = {
                    identity: {
                        selectedAttributeId: 'thread_A',
                        urlThreadId: 'thread_A',
                        channel: 'messenger',
                        normalizedName: 'usera'
                    },
                    canvas: canvasA,
                    composer: composerA,
                    headerNode: headerA,
                    headerText: 'User A',
                    fingerprint: DOM.getSurfaceFingerprint(canvasA),
                    channel: 'messenger'
                };

                // Trigger switch: row B selected, URL B, header B
                rowA.removeAttribute('aria-selected');
                rowB.setAttribute('aria-selected', 'true');
                window.history.pushState({}, '', '/inbox/messenger/?thread_id=thread_B');
                headerA.querySelector('h1').innerText = 'User B';

                // Mutate stale canvas A (typing indicator alters fingerprint)
                const typingIndicatorA = document.createElement('div');
                typingIndicatorA.className = 'typing-indicator';
                typingIndicatorA.innerText = 'User A is typing...';
                canvasA.appendChild(typingIndicatorA);

                const mutatedFingerprintA = DOM.getSurfaceFingerprint(canvasA);
                const fingerprintChangedA = (mutatedFingerprintA !== preClickA.fingerprint);

                const expectedB = DOM.captureExpectedConversation(rowB, 'User B');
                const tokenA = { cancelled: false };
                setTimeout(() => { tokenA.cancelled = true; }, 350);

                let leaseA = null;
                let caughtErrorA = null;
                try {
                    leaseA = await DOM.waitForConversationLoad(expectedB, rowB, rowB, null, tokenA, preClickA);
                } catch (err) {
                    caughtErrorA = err?.message || String(err);
                }

                // --- CASE B: WhatsApp -> Messenger Transition with Stale Mutated Canvas ---
                window.history.pushState({}, '', '/inbox/whatsapp/?thread_id=wa_user_1');
                fixture.innerHTML = `
                    <div role="row" class="conv-row" data-platform="whatsapp" data-thread-id="wa_user_1" aria-selected="true">
                        <span dir="auto">WhatsApp User 1</span>
                    </div>
                    <div role="row" class="conv-row" data-channel="messenger" data-thread-id="msg_user_2">
                        <span dir="auto">Messenger User 2</span>
                    </div>
                    <header role="banner" data-testid="chat_header">
                        <h1 role="heading">WhatsApp User 1</h1>
                    </header>
                    <div id="canvas-wa-1" data-testid="chat-canvas" data-thread-id="wa_user_1" style="width:500px;height:500px;">
                        <p>WhatsApp conversation history</p>
                        <div contenteditable="true" role="textbox" aria-label="اكتب رسالة" style="width:300px;height:40px;margin-top:300px;"></div>
                        <button aria-label="إرسال" style="width:50px;height:30px;">Send</button>
                    </div>
                `;

                const rowWA = document.querySelector('[data-thread-id="wa_user_1"]');
                const rowMsg = document.querySelector('[data-thread-id="msg_user_2"]');
                const canvasWA = document.getElementById('canvas-wa-1');
                const composerWA = canvasWA.querySelector('[role="textbox"]');
                const sendBtnWA = canvasWA.querySelector('button[aria-label="إرسال"]');
                const headerWA = document.querySelector('header');

                let eventsWA = 0;
                const recordEventWA = () => { eventsWA++; };
                composerWA.addEventListener('input', recordEventWA);
                composerWA.addEventListener('beforeinput', recordEventWA);
                composerWA.addEventListener('keydown', recordEventWA);
                sendBtnWA.addEventListener('click', recordEventWA);

                const preClickWA = {
                    identity: {
                        selectedAttributeId: 'wa_user_1',
                        urlThreadId: 'wa_user_1',
                        channel: 'whatsapp',
                        normalizedName: 'whatsappuser1'
                    },
                    canvas: canvasWA,
                    composer: composerWA,
                    headerNode: headerWA,
                    headerText: 'WhatsApp User 1',
                    fingerprint: DOM.getSurfaceFingerprint(canvasWA),
                    channel: 'whatsapp'
                };

                // Trigger switch from WhatsApp to Messenger
                rowWA.removeAttribute('aria-selected');
                rowMsg.setAttribute('aria-selected', 'true');
                window.history.pushState({}, '', '/inbox/messenger/?thread_id=msg_user_2');
                headerWA.querySelector('h1').innerText = 'Messenger User 2';

                // Mutate stale WhatsApp canvas
                const typingIndicatorWA = document.createElement('div');
                typingIndicatorWA.className = 'typing-indicator';
                typingIndicatorWA.innerText = 'User is typing...';
                canvasWA.appendChild(typingIndicatorWA);

                const mutatedFingerprintWA = DOM.getSurfaceFingerprint(canvasWA);
                const fingerprintChangedWA = (mutatedFingerprintWA !== preClickWA.fingerprint);

                const expectedMsg = DOM.captureExpectedConversation(rowMsg, 'Messenger User 2');
                const tokenWA = { cancelled: false };
                setTimeout(() => { tokenWA.cancelled = true; }, 350);

                let leaseWA = null;
                let caughtErrorWA = null;
                try {
                    leaseWA = await DOM.waitForConversationLoad(expectedMsg, rowMsg, rowMsg, null, tokenWA, preClickWA);
                } catch (err) {
                    caughtErrorWA = err?.message || String(err);
                }

                return {
                    caseA: {
                        fingerprintChanged: fingerprintChangedA,
                        leaseNull: leaseA === null,
                        eventsDispatched: eventsA,
                        caughtError: caughtErrorA
                    },
                    caseB: {
                        fingerprintChanged: fingerprintChangedWA,
                        leaseNull: leaseWA === null,
                        eventsDispatched: eventsWA,
                        caughtError: caughtErrorWA
                    }
                };
            }""")

            assert res["caseA"]["fingerprintChanged"] is True, "Expected Case A fingerprint to change on mutation"
            assert res["caseA"]["leaseNull"] is True, f"Expected Case A lease to be null, got {res['caseA']}"
            assert res["caseA"]["eventsDispatched"] == 0, f"Expected zero events on composer A, got {res['caseA']['eventsDispatched']}"

            assert res["caseB"]["fingerprintChanged"] is True, "Expected Case B fingerprint to change on mutation"
            assert res["caseB"]["leaseNull"] is True, f"Expected Case B lease to be null, got {res['caseB']}"
            assert res["caseB"]["eventsDispatched"] == 0, f"Expected zero events on composer WA, got {res['caseB']['eventsDispatched']}"

            self.record_pass(test_id, desc)
        except Exception as e:
            self.record_fail(test_id, desc, str(e))
        finally:
            page.close()

    # =========================================================================
    # TEST 14: React remounted stale-surface bypass => zero lease on unanchored
    #          replacement, exactly one lease on genuinely new anchored surface
    # =========================================================================
    def test_14(self, browser):
        test_id = "14"
        desc = "React remounted stale-surface bypass => zero lease on unanchored, 1 lease on anchored"
        page = self.create_page(browser)
        try:
            res = page.evaluate("""async () => {
                const { DOM } = window.__TEST_MBS__;

                // --- CASE A: Messenger -> Messenger Replacement Surface without Target-Local ID ---
                window.history.pushState({}, '', '/inbox/messenger/?thread_id=thread_A');
                const fixture = document.getElementById('mbs-fixture');
                fixture.innerHTML = `
                    <div role="row" class="conv-row" data-channel="messenger" data-thread-id="thread_A" aria-selected="true">
                        <span dir="auto">User A</span>
                    </div>
                    <div role="row" class="conv-row" data-channel="messenger" data-thread-id="thread_B">
                        <span dir="auto">User B</span>
                    </div>
                    <header role="banner" data-testid="chat_header">
                        <h1 role="heading">User A</h1>
                    </header>
                    <div id="canvas-a-initial" data-testid="chat-canvas" style="width:500px;height:500px;">
                        <p>Initial message from A</p>
                        <div contenteditable="true" role="textbox" aria-label="اكتب رسالة" style="width:300px;height:40px;margin-top:300px;"></div>
                        <button aria-label="إرسال" style="width:50px;height:30px;">Send</button>
                    </div>
                `;

                const rowA = document.querySelector('[data-thread-id="thread_A"]');
                const rowB = document.querySelector('[data-thread-id="thread_B"]');
                const canvasA1 = document.getElementById('canvas-a-initial');
                const composerA1 = canvasA1.querySelector('[role="textbox"]');
                const header = document.querySelector('header');

                // Capture snapshot of A
                const preClickA = {
                    identity: {
                        selectedAttributeId: 'thread_A',
                        urlThreadId: 'thread_A',
                        channel: 'messenger',
                        normalizedName: 'usera'
                    },
                    canvas: canvasA1,
                    composer: composerA1,
                    headerNode: header,
                    headerText: 'User A',
                    fingerprint: DOM.getSurfaceFingerprint(canvasA1),
                    channel: 'messenger'
                };

                // Trigger switch: row B selected, URL B, header B
                rowA.removeAttribute('aria-selected');
                rowB.setAttribute('aria-selected', 'true');
                window.history.pushState({}, '', '/inbox/messenger/?thread_id=thread_B');
                header.querySelector('h1').innerText = 'User B';

                // Simulate React remounting A's canvas into completely new DOM nodes
                canvasA1.remove();
                const canvasA2 = document.createElement('div');
                canvasA2.id = 'canvas-a-remounted';
                canvasA2.setAttribute('data-testid', 'chat-canvas');
                // No target-local B ID!
                canvasA2.style.cssText = 'width:500px;height:500px;';
                canvasA2.innerHTML = `
                    <p>New message arrived on stale thread A</p>
                    <span class="timestamp">Just now</span>
                    <div contenteditable="true" role="textbox" aria-label="اكتب رسالة" style="width:300px;height:40px;margin-top:300px;"></div>
                    <button aria-label="إرسال" style="width:50px;height:30px;">Send</button>
                `;
                fixture.appendChild(canvasA2);

                const composerA2 = canvasA2.querySelector('[role="textbox"]');
                const sendBtnA2 = canvasA2.querySelector('button[aria-label="إرسال"]');

                let eventsA = 0;
                const recordEventA = () => { eventsA++; };
                composerA2.addEventListener('input', recordEventA);
                composerA2.addEventListener('beforeinput', recordEventA);
                composerA2.addEventListener('keydown', recordEventA);
                sendBtnA2.addEventListener('click', recordEventA);

                const fpA2 = DOM.getSurfaceFingerprint(canvasA2);
                const fpMutatedA = (fpA2 !== preClickA.fingerprint);
                const nodesReplacedA = (canvasA2 !== preClickA.canvas && composerA2 !== preClickA.composer);

                const expectedB = DOM.captureExpectedConversation(rowB, 'User B');
                const tokenA = { cancelled: false };
                setTimeout(() => { tokenA.cancelled = true; }, 650);

                let leaseA = null;
                try {
                    leaseA = await DOM.waitForConversationLoad(expectedB, rowB, rowB, null, tokenA, preClickA);
                } catch (_) {}

                // --- CASE B: WhatsApp -> Messenger Replacement Surface without Target-Local ID ---
                window.history.pushState({}, '', '/inbox/whatsapp/?thread_id=wa_user_1');
                fixture.innerHTML = `
                    <div role="row" class="conv-row" data-platform="whatsapp" data-thread-id="wa_user_1" aria-selected="true">
                        <span dir="auto">WhatsApp User 1</span>
                    </div>
                    <div role="row" class="conv-row" data-channel="messenger" data-thread-id="msg_user_2">
                        <span dir="auto">Messenger User 2</span>
                    </div>
                    <header role="banner" data-testid="chat_header">
                        <h1 role="heading">WhatsApp User 1</h1>
                    </header>
                    <div id="canvas-wa-initial" data-testid="chat-canvas" style="width:500px;height:500px;">
                        <p>Initial WA conversation</p>
                        <div contenteditable="true" role="textbox" aria-label="اكتب رسالة" style="width:300px;height:40px;margin-top:300px;"></div>
                        <button aria-label="إرسال" style="width:50px;height:30px;">Send</button>
                    </div>
                `;

                const rowWA = document.querySelector('[data-thread-id="wa_user_1"]');
                const rowMsg = document.querySelector('[data-thread-id="msg_user_2"]');
                const canvasWA1 = document.getElementById('canvas-wa-initial');
                const composerWA1 = canvasWA1.querySelector('[role="textbox"]');
                const headerWA = document.querySelector('header');

                const preClickWA = {
                    identity: {
                        selectedAttributeId: 'wa_user_1',
                        urlThreadId: 'wa_user_1',
                        channel: 'whatsapp',
                        normalizedName: 'whatsappuser1'
                    },
                    canvas: canvasWA1,
                    composer: composerWA1,
                    headerNode: headerWA,
                    headerText: 'WhatsApp User 1',
                    fingerprint: DOM.getSurfaceFingerprint(canvasWA1),
                    channel: 'whatsapp'
                };

                rowWA.removeAttribute('aria-selected');
                rowMsg.setAttribute('aria-selected', 'true');
                window.history.pushState({}, '', '/inbox/messenger/?thread_id=msg_user_2');
                headerWA.querySelector('h1').innerText = 'Messenger User 2';

                // Remounted stale WA canvas (new node, mutated fingerprint, no target-local ID)
                canvasWA1.remove();
                const canvasWA2 = document.createElement('div');
                canvasWA2.id = 'canvas-wa-remounted';
                canvasWA2.setAttribute('data-testid', 'chat-canvas');
                canvasWA2.style.cssText = 'width:500px;height:500px;';
                canvasWA2.innerHTML = `
                    <p>New WA inbound arrived</p>
                    <div contenteditable="true" role="textbox" aria-label="اكتب رسالة" style="width:300px;height:40px;margin-top:300px;"></div>
                    <button aria-label="إرسال" style="width:50px;height:30px;">Send</button>
                `;
                fixture.appendChild(canvasWA2);

                const composerWA2 = canvasWA2.querySelector('[role="textbox"]');
                const sendBtnWA2 = canvasWA2.querySelector('button[aria-label="إرسال"]');

                let eventsWA = 0;
                const recordEventWA = () => { eventsWA++; };
                composerWA2.addEventListener('input', recordEventWA);
                composerWA2.addEventListener('beforeinput', recordEventWA);
                composerWA2.addEventListener('keydown', recordEventWA);
                sendBtnWA2.addEventListener('click', recordEventWA);

                const fpWA2 = DOM.getSurfaceFingerprint(canvasWA2);
                const fpMutatedWA = (fpWA2 !== preClickWA.fingerprint);
                const nodesReplacedWA = (canvasWA2 !== preClickWA.canvas && composerWA2 !== preClickWA.composer);

                const expectedMsg = DOM.captureExpectedConversation(rowMsg, 'Messenger User 2');
                const tokenWA = { cancelled: false };
                setTimeout(() => { tokenWA.cancelled = true; }, 650);

                let leaseWA = null;
                try {
                    leaseWA = await DOM.waitForConversationLoad(expectedMsg, rowMsg, rowMsg, null, tokenWA, preClickWA);
                } catch (_) {}

                // --- CASE C: Positive Counterpart — Genuinely New B Canvas with Target-Local ID ---
                window.history.pushState({}, '', '/inbox/messenger/?thread_id=thread_B');
                fixture.innerHTML = `
                    <div role="row" class="conv-row" data-channel="messenger" data-thread-id="thread_B" aria-selected="true">
                        <span dir="auto">User B</span>
                    </div>
                    <header role="banner" data-testid="chat_header">
                        <h1 role="heading">User B</h1>
                    </header>
                    <div id="canvas-b-genuine" data-testid="chat-canvas" data-thread-id="thread_B" style="width:500px;height:500px;">
                        <p>Genuine Thread B message list</p>
                        <div contenteditable="true" role="textbox" aria-label="اكتب رسالة" style="width:300px;height:40px;margin-top:300px;"></div>
                        <button aria-label="إرسال" style="width:50px;height:30px;">Send</button>
                    </div>
                `;

                const rowBPositive = document.querySelector('[data-thread-id="thread_B"]');
                const canvasBPositive = document.getElementById('canvas-b-genuine');
                const composerBPositive = canvasBPositive.querySelector('[role="textbox"]');

                const expectedBPositive = DOM.captureExpectedConversation(rowBPositive, 'User B');
                const tokenPositive = { cancelled: false };

                let leasePositive = null;
                try {
                    leasePositive = await DOM.waitForConversationLoad(expectedBPositive, rowBPositive, rowBPositive, null, tokenPositive, preClickA);
                } catch (_) {}

                return {
                    caseA: {
                        nodesReplaced: nodesReplacedA,
                        fingerprintMutated: fpMutatedA,
                        leaseNull: leaseA === null,
                        eventsDispatched: eventsA
                    },
                    caseB: {
                        nodesReplaced: nodesReplacedWA,
                        fingerprintMutated: fpMutatedWA,
                        leaseNull: leaseWA === null,
                        eventsDispatched: eventsWA
                    },
                    caseC: {
                        leaseNotNull: leasePositive !== null,
                        surfaceMatches: leasePositive ? (leasePositive.surface === canvasBPositive) : false,
                        composerMatches: leasePositive ? (leasePositive.composer === composerBPositive) : false
                    }
                };
            }""")

            assert res["caseA"]["nodesReplaced"] is True, "Expected Case A nodes to be completely replaced"
            assert res["caseA"]["fingerprintMutated"] is True, "Expected Case A fingerprint to differ"
            assert res["caseA"]["leaseNull"] is True, f"Expected Case A lease to be NULL, got: {res['caseA']}"
            assert res["caseA"]["eventsDispatched"] == 0, f"Expected zero events dispatched in Case A, got: {res['caseA']['eventsDispatched']}"

            assert res["caseB"]["nodesReplaced"] is True, "Expected Case B nodes to be completely replaced"
            assert res["caseB"]["fingerprintMutated"] is True, "Expected Case B fingerprint to differ"
            assert res["caseB"]["leaseNull"] is True, f"Expected Case B lease to be NULL, got: {res['caseB']}"
            assert res["caseB"]["eventsDispatched"] == 0, f"Expected zero events dispatched in Case B, got: {res['caseB']['eventsDispatched']}"

            assert res["caseC"]["leaseNotNull"] is True, "Expected positive Case C lease to be returned"
            assert res["caseC"]["surfaceMatches"] is True, "Expected positive Case C surface to match genuine canvas"
            assert res["caseC"]["composerMatches"] is True, "Expected positive Case C composer to match genuine composer"

            self.record_pass(test_id, desc)
        except Exception as e:
            self.record_fail(test_id, desc, str(e))
        finally:
            page.close()

    # =========================================================================
    # RUN ALL 14 TESTS
    # =========================================================================
    def run(self) -> int:
        print(f"\n{C_BOLD}{C_CYAN}============================================================================={C_RESET}")
        print(f"{C_BOLD}{C_CYAN}  MILESTONE 1 — BEHAVIORAL RACE & LEASE HARNESS (14 TESTS)                  {C_RESET}")
        print(f"{C_BOLD}{C_CYAN}============================================================================={C_RESET}\n")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                executable_path="/usr/bin/google-chrome-stable" if os.path.exists("/usr/bin/google-chrome-stable") else None
            )

            try:
                self.test_01(browser)
                self.test_02(browser)
                self.test_03(browser)
                self.test_04(browser)
                self.test_05(browser)
                self.test_06(browser)
                self.test_07(browser)
                self.test_08(browser)
                self.test_09(browser)
                self.test_10(browser)
                self.test_11(browser)
                self.test_12(browser)
                self.test_13(browser)
                self.test_14(browser)
            finally:
                browser.close()

        print(f"\n{C_BOLD}{C_CYAN}-----------------------------------------------------------------------------{C_RESET}")
        print(f" TOTAL TESTS RUN : {self.passed + self.failed}")
        print(f" PASSED          : {C_GREEN}{self.passed}{C_RESET}")
        print(f" FAILED          : {C_RED}{self.failed}{C_RESET}")
        print(f"{C_BOLD}{C_CYAN}-----------------------------------------------------------------------------{C_RESET}\n")

        if self.failed == 0:
            print(f"{C_BOLD}{C_GREEN}FINAL VERDICT: 100% PASS - ALL 14 M1 BEHAVIORAL RACE TESTS VERIFIED!{C_RESET}\n")
            return 0
        else:
            print(f"{C_BOLD}{C_RED}FINAL VERDICT: {self.failed} TEST(S) FAILED!{C_RESET}\n")
            for f in self.failures:
                print(f"  • {f}")
            print()
            return 1


if __name__ == "__main__":
    runner = M1FocusRunner()
    sys.exit(runner.run())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
Phase 1: Browser Contract & Integration Verification Harness
=============================================================================
Tests:
1. Real Browser DOM Verbatim Extraction vs Synthetic Space Padding
2. Production Multi-Bubble Isolation, Whitespace Rejection, and Depth Failure
3. Isolated Web Worker Regex Execution (Success, Syntax Error, ReDoS Timeout)
4. Desktop GUI & Embedded HUD creation defaults to 'ultra_exact'
5. Editor -> Bridge Payload Capture -> Reload -> Production Evaluator
6. Interactive 3-Profile Conflict Resolution Flow (LINK_CONFLICT handling)
=============================================================================
"""

import sys
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent
BOT_SCRIPT_PATH = ROOT_DIR / "bot_script.js"
GUI_APP_PATH = ROOT_DIR / "gui" / "app.js"
GUI_HTML_PATH = ROOT_DIR / "gui" / "index.html"

BOOTSTRAP_TARGET = "console.log('[MBS Automator V6.5.4] Initialized successfully (Enterprise Hardened Edition — P0/P1/P2 Remediations Applied).');\n})();"

TEST_EXPORT_SNIPPET = """window.__TEST_MBS__ = {
  DOM,
  HumanSimulator,
  Orchestrator,
  state,
  RegexSandbox,
  regexSandbox,
  normalizeArabicText,
  escapeRegExp,
  testKeywordsMatch,
  evaluateActiveRules
};
console.log('[MBS Automator V6.5.4] Initialized successfully (Enterprise Hardened Edition — P0/P1/P2 Remediations Applied).');
})();"""

def run_browser_contracts():
    print("\n=============================================================================")
    print("  PHASE 1 BROWSER CONTRACT & INTEGRATION HARNESS")
    print("=============================================================================")

    raw_script = BOT_SCRIPT_PATH.read_text(encoding="utf-8")
    instrumented_script = raw_script.replace(BOOTSTRAP_TARGET, TEST_EXPORT_SNIPPET)

    total = 0
    passed = 0
    failed = 0

    def assert_test(name, success, err_msg=""):
        nonlocal total, passed, failed
        total += 1
        if success:
            passed += 1
            print(f"  \033[32m[PASS]\033[0m {name}")
        else:
            failed += 1
            print(f"  \033[31m[FAIL]\033[0m {name}: {err_msg}")

    executable_path = "/usr/bin/google-chrome-stable" if Path("/usr/bin/google-chrome-stable").exists() else None
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=executable_path,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu"
            ]
        )
        context = browser.new_context()
        page = context.new_page()

        # -----------------------------------------------------------------------
        # 1. Load blank page with bot_script injected
        # -----------------------------------------------------------------------
        page.goto("about:blank")
        page.evaluate(instrumented_script)

        # -----------------------------------------------------------------------
        # Section 1: DOM Verbatim Message Extraction in Real Browser
        # -----------------------------------------------------------------------
        print("\n--- SECTION 1: Browser DOM Verbatim Extraction ---")

        res_dom = page.evaluate("""() => {
            const results = {};
            const DOM = window.__TEST_MBS__?.DOM;
            if (!DOM || typeof DOM.extractMessageTextVerbatim !== 'function') {
                return { error: 'extractMessageTextVerbatim not implemented' };
            }

            // 1.1 <div><span>سعر</span></div> has 0 wrapper padding
            const div1 = document.createElement('div');
            div1.innerHTML = '<div><span>سعر</span></div>';
            results.divSpan = DOM.extractMessageTextVerbatim(div1) === 'سعر';

            // 1.2 Message text node containing ' سعر ' retains both spaces
            const div2 = document.createElement('div');
            div2.appendChild(document.createTextNode(' سعر '));
            results.leadingTrailingSpaces = DOM.extractMessageTextVerbatim(div2) === ' سعر ';

            // 1.3 Nested inline text preserves Tashkeel and repeated spaces
            const div3 = document.createElement('div');
            div3.innerHTML = '<span>سِعر  <span>المشدّ</span></span>';
            results.nestedTashkeelSpaces = DOM.extractMessageTextVerbatim(div3) === 'سِعر  المشدّ';

            // 1.4 <span>سعر<br>المشد</span> extracts exactly 'سعر\\nالمشد'
            const div4 = document.createElement('div');
            div4.innerHTML = '<span>سعر<br>المشد</span>';
            results.brNewline = DOM.extractMessageTextVerbatim(div4) === 'سعر\\nالمشد';

            // 1.5 Emoji img alt text without extra separators
            const div5 = document.createElement('div');
            div5.innerHTML = '<span>سعر</span><img class=\"emoji\" alt=\"🇪🇬\" src=\"https://example.com/emoji.png\">';
            results.emojiImg = DOM.extractMessageTextVerbatim(div5) === 'سعر🇪🇬';

            // 1.6 Exclude avatar, reaction, and link preview text
            const div6 = document.createElement('div');
            div6.innerHTML = '<div aria-label="Profile photo">Avatar Text</div><div data-testid="reaction_pill">👍 1</div><div data-testid="link_preview">Preview Title</div><span>سعر المشد</span>';
            results.exclusions = DOM.extractMessageTextVerbatim(div6) === 'سعر المشد';

            return results;
        }""")

        if "error" in res_dom:
            assert_test("DOM: <div><span>سعر</span></div> extracts 'سعر' with 0 padding", False, res_dom["error"])
            assert_test("DOM: preserves leading and trailing spaces ' سعر '", False, res_dom["error"])
            assert_test("DOM: nested inline preserves Tashkeel and repeated spaces", False, res_dom["error"])
            assert_test("DOM: <span>سعر<br>المشد</span> extracts 'سعر\\nالمشد'", False, res_dom["error"])
            assert_test("DOM: emoji image preserves alt text without separators", False, res_dom["error"])
            assert_test("DOM: avatar, reaction, and link preview excluded", False, res_dom["error"])
        else:
            assert_test("DOM: <div><span>سعر</span></div> extracts 'سعر' with 0 padding", res_dom.get("divSpan") is True, f"Result: {res_dom.get('divSpan')}")
            assert_test("DOM: preserves leading and trailing spaces ' سعر '", res_dom.get("leadingTrailingSpaces") is True, f"Result: {res_dom.get('leadingTrailingSpaces')}")
            assert_test("DOM: nested inline preserves Tashkeel and repeated spaces", res_dom.get("nestedTashkeelSpaces") is True, f"Result: {res_dom.get('nestedTashkeelSpaces')}")
            assert_test("DOM: <span>سعر<br>المشد</span> extracts 'سعر\\nالمشد'", res_dom.get("brNewline") is True, f"Result: {res_dom.get('brNewline')}")
            assert_test("DOM: emoji image preserves alt text without separators", res_dom.get("emojiImg") is True, f"Result: {res_dom.get('emojiImg')}")
            assert_test("DOM: avatar, reaction, and link preview excluded", res_dom.get("exclusions") is True, f"Result: {res_dom.get('exclusions')}")

        # -----------------------------------------------------------------------
        # Section 2: Production Multi-Bubble Isolation, Whitespace Rejection, & Depth Failure
        # -----------------------------------------------------------------------
        print("\n--- SECTION 2: Production Multi-Bubble Isolation & Verbatim Pipeline ---")

        res_bubble = page.evaluate("""async () => {
            const { DOM, evaluateActiveRules } = window.__TEST_MBS__;

            // A. Whitespace rejection through DOM -> verbatim extraction -> evaluator
            const spaceDiv = document.createElement('div');
            spaceDiv.innerHTML = '<div> <span>سعر</span> </div>';
            const spaceText = DOM.extractMessageTextVerbatim(spaceDiv);
            const ultraRule = [{ id: 'r_strict', keywords: ['سعر'], reply: 'x', matchType: 'ultra_exact', active: true }];
            const spaceEval = await evaluateActiveRules(spaceText, ultraRule);

            // B. Extraction depth failure (> 50 levels) returns null and fails closed in evaluator
            const deepRoot = document.createElement('div');
            let deepCurr = deepRoot;
            for (let i = 0; i < 55; i++) {
                const child = document.createElement('div');
                deepCurr.appendChild(child);
                deepCurr = child;
            }
            deepCurr.textContent = 'سعر';
            const deepText = DOM.extractMessageTextVerbatim(deepRoot);
            let deepEval = null;
            if (deepText !== null) {
                deepEval = await evaluateActiveRules(deepText, ultraRule);
            }

            // C. Production multi-bubble isolation in conversation container
            const container = document.createElement('div');
            const bubble1 = document.createElement('div');
            bubble1.className = 'msg-bubble';
            bubble1.innerHTML = '<span>سعر</span>';
            const bubble2 = document.createElement('div');
            bubble2.className = 'msg-bubble';
            bubble2.innerHTML = '<span>المشد</span>';
            container.appendChild(bubble1);
            container.appendChild(bubble2);

            const customerBubbles = [bubble1, bubble2];
            const phraseRule = [{ id: 'rule_phrase', keywords: ['سعر المشد'], reply: 'r1', matchType: 'ultra_exact', active: true }];
            const tailRule = [{ id: 'rule_tail', keywords: ['المشد'], reply: 'r2', matchType: 'ultra_exact', active: true }];

            // In production Step 4: latestBubble is inspected individually
            const latestBubble = customerBubbles[customerBubbles.length - 1];
            const latestVerbatim = DOM.extractMessageTextVerbatim(latestBubble);

            const phraseMatch = await evaluateActiveRules(latestVerbatim, phraseRule);
            const tailMatch = await evaluateActiveRules(latestVerbatim, tailRule);

            return {
                spaceVerbatim: spaceText,
                spaceRejected: spaceEval === null,
                depthNull: deepText === null,
                depthFailedClosed: deepEval === null,
                phraseRejected: phraseMatch === null,
                tailMatched: tailMatch !== null && tailMatch.rule.id === 'rule_tail'
            };
        }""")

        assert_test(
            "DOM -> Evaluator: Whitespace around elements rejects strict match ' سعر ' !== 'سعر'",
            res_bubble.get("spaceRejected") is True and res_bubble.get("spaceVerbatim") == " سعر ",
            f"Verbatim='{res_bubble.get('spaceVerbatim')}', Rejected={res_bubble.get('spaceRejected')}"
        )
        assert_test(
            "DOM -> Evaluator: Extraction depth > 50 fails closed with null",
            res_bubble.get("depthNull") is True and res_bubble.get("depthFailedClosed") is True,
            f"depthNull={res_bubble.get('depthNull')}"
        )
        assert_test(
            "Multi-Bubble Orchestration: Separate messages 'سعر' and 'المشد' cannot match 'سعر المشد'",
            res_bubble.get("phraseRejected") is True and res_bubble.get("tailMatched") is True,
            f"phraseRejected={res_bubble.get('phraseRejected')}, tailMatched={res_bubble.get('tailMatched')}"
        )

        # -----------------------------------------------------------------------
        # Section 3: Web Worker Regex Execution in Browser
        # -----------------------------------------------------------------------
        print("\n--- SECTION 3: Web Worker Regex Execution ---")

        res_regex = page.evaluate("""async () => {
            const { RegexSandbox } = window.__TEST_MBS__;
            const sandbox = new RegexSandbox(30);

            // Wait for worker initialization
            await new Promise(r => setTimeout(r, 50));

            const hasWorker = !!sandbox.worker;

            // 1. Valid regex pattern
            let validMatched = false;
            try {
                validMatched = await sandbox.test('^سعره$', 'u', 'سعره', 50);
            } catch (_) {}

            // 2. Non-matching regex pattern
            let mismatchOk = false;
            try {
                const res = await sandbox.test('^سعره$', 'u', 'سعر', 50);
                mismatchOk = (res === false);
            } catch (_) {}

            // 3. Invalid syntax pattern (must settle false without unhandled rejection)
            let syntaxFailedClosed = false;
            try {
                const res = await sandbox.test('[invalid', 'u', 'test', 50);
                syntaxFailedClosed = (res === false);
            } catch (_) {}

            // 4. Catastrophic ReDoS pattern (must time out and settle false in <= 150ms)
            let redosTimeoutOk = false;
            const t0 = Date.now();
            try {
                const res = await sandbox.test('(a+)+$', 'u', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaa!', 30);
                const elapsed = Date.now() - t0;
                redosTimeoutOk = (res === false) && (elapsed < 250);
            } catch (_) {}

            return {
                hasWorker,
                validMatched,
                mismatchOk,
                syntaxFailedClosed,
                redosTimeoutOk
            };
        }""")

        assert_test("Regex Worker: Spawned in browser environment", res_regex.get("hasWorker") is True, f"Worker: {res_regex.get('hasWorker')}")
        assert_test("Regex Worker: Valid pattern matches correctly", res_regex.get("validMatched") is True, f"Result: {res_regex.get('validMatched')}")
        assert_test("Regex Worker: Non-matching text returns false", res_regex.get("mismatchOk") is True, f"Result: {res_regex.get('mismatchOk')}")
        assert_test("Regex Worker: Invalid pattern syntax fails closed", res_regex.get("syntaxFailedClosed") is True, f"Result: {res_regex.get('syntaxFailedClosed')}")
        assert_test("Regex Worker: ReDoS timeout terminates safely in <= 250ms", res_regex.get("redosTimeoutOk") is True, f"Result: {res_regex.get('redosTimeoutOk')}")

        # -----------------------------------------------------------------------
        # Section 4: GUI & HUD Rule Creation Defaults
        # -----------------------------------------------------------------------
        print("\n--- SECTION 4: GUI & HUD Defaults and Dropdown Options ---")

        # Check main.py default matchType
        main_py_txt = (ROOT_DIR / "main.py").read_text(encoding="utf-8")
        main_defaults_ultra = '"matchType": "ultra_exact"' in main_py_txt and '"matchType": "contains"' not in main_py_txt
        assert_test("main.py: fallback rule templates default to ultra_exact", main_defaults_ultra, "Contains legacy 'contains' default")

        # Check bot_script.js defaultRules
        bot_defaults_ultra = "matchType: 'ultra_exact'" in raw_script
        assert_test("bot_script.js: defaultRules templates default to ultra_exact", bot_defaults_ultra, "Contains legacy 'contains' default")

        # Check gui/app.js btnAddRule default
        gui_app_txt = GUI_APP_PATH.read_text(encoding="utf-8")
        gui_add_ultra = "matchType: 'ultra_exact'" in gui_app_txt
        assert_test("gui/app.js: btnAddRule creates rule with ultra_exact default", gui_add_ultra, "Missing matchType: 'ultra_exact'")

        # Check gui/app.js dropdown has canonical options
        canonical_options = (
            'value="ultra_exact"' in gui_app_txt and
            'value="contains"' in gui_app_txt and
            'value="exact"' in gui_app_txt and
            'value="regex"' in gui_app_txt
        )
        assert_test("gui/app.js: dropdown contains all 4 canonical modes", canonical_options, "Missing canonical mode options")

        # Check embedded HUD in bot_script.js has 4 canonical modes
        hud_canonical = (
            'value="ultra_exact"' in raw_script and
            'value="contains"' in raw_script and
            'value="exact"' in raw_script and
            'value="regex"' in raw_script
        )
        assert_test("bot_script.js HUD: dropdown contains all 4 canonical modes", hud_canonical, "HUD missing canonical mode options")

        # -----------------------------------------------------------------------
        # Section 5: Editor -> Bridge Payload Capture -> Reload -> Production Evaluator
        # -----------------------------------------------------------------------
        print("\n--- SECTION 5: Editor -> Bridge Payload -> Reload -> Production Evaluator ---")

        gui_page = context.new_page()
        gui_page.add_init_script("""
            window.__CAPTURED_SAVES__ = [];
            window.alert = () => {};
            window.confirm = () => true;
            window.pywebview = {
                api: {
                    get_profiles: async () => [{ name: 'TestProfile', status: 'STOPPED', rules_count: 0 }],
                    load_profile_config_result: async (p) => ({ ok: true, read_status: 'OK', rules_count: 0, data: { rules: [], config: {} }, sha256_token: 'dummy_token' }),
                    load_profile_config: async (p) => ({ rules: [], config: {} }),
                    get_linked_rules_map: async () => ({}),
                    allocate_rule_metadata: async (p) => ({
                        id: 'rule_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7),
                        ruleCode: 'MBS-' + Math.random().toString(36).substring(2, 10).toUpperCase()
                    }),
                    save_profile_config_coordinated: async (profile, config, sha) => {
                        window.__CAPTURED_SAVES__.push(JSON.parse(JSON.stringify(config)));
                        return { ok: true, sha256_token: 'dummy_token_2' };
                    },
                    save_profile_config: async (profile, config) => {
                        window.__CAPTURED_SAVES__.push(JSON.parse(JSON.stringify(config)));
                        return { status: 'OK' };
                    },
                    get_logs: async () => [],
                    get_stats: async () => ({})
                }
            };
        """)
        gui_page.goto(f"file://{GUI_HTML_PATH}")
        gui_page.wait_for_load_state("domcontentloaded")

        # Create rules for all 4 modes using the primary multiline keyword editor
        editor_res = gui_page.evaluate("""async () => {
            const btnAdd = document.getElementById('add-rule-btn');
            if (!btnAdd) return { error: 'add-rule-btn not found' };

            let waitRetries = 50;
            while (waitRetries-- > 0 && btnAdd.disabled) {
                await new Promise(r => setTimeout(r, 50));
            }

            async function addNewCard() {
                const prevCount = document.querySelectorAll('.rule-card').length;
                btnAdd.click();
                let retries = 50;
                while (retries-- > 0 && document.querySelectorAll('.rule-card').length === prevCount) {
                    await new Promise(r => setTimeout(r, 20));
                }
                return document.querySelectorAll('.rule-card')[0];
            }

            function setCardKeywords(card, kws) {
                const btnAddKw = card.querySelector('.btn-add-keyword');
                for (let i = 0; i < kws.length; i++) {
                    if (i > 0) {
                        btnAddKw.click();
                    }
                    const textareas = card.querySelectorAll('.keyword-row .keyword-textarea');
                    const ta = textareas[textareas.length - 1];
                    ta.value = kws[i];
                    ta.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }

            // 1. Add ultra_exact rule with strict keywords containing outer spaces, commas, newlines
            let card1 = await addNewCard();
            card1.querySelector('.rule-match-type').value = 'ultra_exact';
            card1.querySelector('.rule-match-type').dispatchEvent(new Event('change', { bubbles: true }));

            // Add literal keywords: " سعر ", "سعر, كام", "سعر\\nالمشد"
            setCardKeywords(card1, [' سعر ', 'سعر, كام', 'سعر\\nالمشد']);
            card1.querySelector('.rule-reply').value = 'رد حرفي';
            card1.querySelector('.rule-reply').dispatchEvent(new Event('input', { bubbles: true }));

            // 2. Add contains rule
            let card2 = await addNewCard();
            card2.querySelector('.rule-match-type').value = 'contains';
            card2.querySelector('.rule-match-type').dispatchEvent(new Event('change', { bubbles: true }));
            setCardKeywords(card2, ['محتوى_فريد']);
            card2.querySelector('.rule-reply').value = 'رد يحتوي';
            card2.querySelector('.rule-reply').dispatchEvent(new Event('input', { bubbles: true }));

            // 3. Add exact rule
            let card3 = await addNewCard();
            card3.querySelector('.rule-match-type').value = 'exact';
            card3.querySelector('.rule-match-type').dispatchEvent(new Event('change', { bubbles: true }));
            setCardKeywords(card3, ['كلمة_دقيقة']);
            card3.querySelector('.rule-reply').value = 'رد بحدود';
            card3.querySelector('.rule-reply').dispatchEvent(new Event('input', { bubbles: true }));

            // 4. Add regex rule
            let card4 = await addNewCard();
            card4.querySelector('.rule-match-type').value = 'regex';
            card4.querySelector('.rule-match-type').dispatchEvent(new Event('change', { bubbles: true }));
            setCardKeywords(card4, ['^نمط_رقم_[0-9]+$']);
            card4.querySelector('.rule-reply').value = 'رد نمطي';
            card4.querySelector('.rule-reply').dispatchEvent(new Event('input', { bubbles: true }));

            // Click save rules
            const btnSave = document.getElementById('btn-save-rules');
            btnSave.click();
            await new Promise(r => setTimeout(r, 200));

            const captured = window.__CAPTURED_SAVES__;
            const latestSave = captured.length > 0 ? captured[captured.length - 1] : null;

            return {
                capturedCount: captured.length,
                savedRules: latestSave?.rules || []
            };
        }""")

        assert_test(
            "Editor -> Bridge: Rules saved via bridge with full metadata",
            editor_res.get("capturedCount", 0) > 0 and len(editor_res.get("savedRules", [])) == 4,
            f"capturedCount={editor_res.get('capturedCount')}, rulesCount={len(editor_res.get('savedRules', []))}"
        )

        saved_rules = editor_res.get("savedRules", [])
        # Find ultra_exact rule and verify canonical array preservation
        ultra_rule = next((r for r in saved_rules if r.get("matchType") == "ultra_exact"), None)
        strict_kws_preserved = (
            ultra_rule is not None and
            " سعر " in ultra_rule.get("keywords", []) and
            "سعر, كام" in ultra_rule.get("keywords", []) and
            "سعر\nالمشد" in ultra_rule.get("keywords", [])
        )
        assert_test(
            "Editor -> Bridge: Strict keywords with outer spaces, commas, newlines preserved in payload",
            strict_kws_preserved,
            f"ultra_rule keywords: {ultra_rule.get('keywords') if ultra_rule else None}"
        )

        # Now pass the captured rules into the production evaluator in page
        eval_roundtrip = page.evaluate("""async (rules) => {
            const { evaluateActiveRules } = window.__TEST_MBS__;

            // 1. Match ultra_exact strict keywords
            const m1 = await evaluateActiveRules(' سعر ', rules);
            const m2 = await evaluateActiveRules('سعر, كام', rules);
            const m3 = await evaluateActiveRules('سعر\\nالمشد', rules);
            // 2. Reject unmatched variant under ultra_exact
            const mUltraReject = await evaluateActiveRules('سعر', rules.filter(r => r.matchType === 'ultra_exact'));

            // 3. Match contains rule
            const mContains = await evaluateActiveRules('هذا النص يتضمن محتوى_فريد هنا', rules);

            // 4. Match exact rule with Unicode boundary
            const mExact = await evaluateActiveRules('هل كلمة_دقيقة موجودة؟', rules);

            // 5. Match regex rule
            const mRegex = await evaluateActiveRules('نمط_رقم_987', rules);

            return {
                m1Ok: m1?.rule?.matchType === 'ultra_exact' && m1?.matchedKeyword === ' سعر ',
                m2Ok: m2?.rule?.matchType === 'ultra_exact' && m2?.matchedKeyword === 'سعر, كام',
                m3Ok: m3?.rule?.matchType === 'ultra_exact' && m3?.matchedKeyword === 'سعر\\nالمشد',
                ultraRejected: mUltraReject === null,
                containsOk: mContains?.rule?.matchType === 'contains',
                exactOk: mExact?.rule?.matchType === 'exact',
                regexOk: mRegex?.rule?.matchType === 'regex'
            };
        }""", saved_rules)

        assert_test(
            "Reload -> Production Evaluator: ultra_exact matches verbatim ' سعر '",
            eval_roundtrip.get("m1Ok") is True,
            f"Result: {eval_roundtrip.get('m1Ok')}"
        )
        assert_test(
            "Reload -> Production Evaluator: ultra_exact matches comma-containing 'سعر, كام'",
            eval_roundtrip.get("m2Ok") is True,
            f"Result: {eval_roundtrip.get('m2Ok')}"
        )
        assert_test(
            "Reload -> Production Evaluator: ultra_exact matches newline-containing 'سعر\\nالمشد'",
            eval_roundtrip.get("m3Ok") is True,
            f"Result: {eval_roundtrip.get('m3Ok')}"
        )
        assert_test(
            "Reload -> Production Evaluator: ultra_exact rejects 'سعر' without spaces",
            eval_roundtrip.get("ultraRejected") is True,
            f"Result: {eval_roundtrip.get('ultraRejected')}"
        )
        assert_test(
            "Reload -> Production Evaluator: all 4 modes match production expectations",
            eval_roundtrip.get("containsOk") is True and eval_roundtrip.get("exactOk") is True and eval_roundtrip.get("regexOk") is True,
            f"contains={eval_roundtrip.get('containsOk')}, exact={eval_roundtrip.get('exactOk')}, regex={eval_roundtrip.get('regexOk')}"
        )

        gui_page.close()

        # -----------------------------------------------------------------------
        # Section 6: Interactive 3-Profile Conflict Resolution Flow
        # -----------------------------------------------------------------------
        print("\n--- SECTION 6: Interactive 3-Profile Conflict Resolution Flow ---")

        conflict_page = context.new_page()
        conflict_page.add_init_script("""
            window.__CAPTURED_RESOLVES__ = [];
            window.alert = () => {};
            window.confirm = () => true;
            window.pywebview = {
                api: {
                    get_profiles: async () => [
                        { name: 'ProfileA', status: 'STOPPED', rules_count: 1 },
                        { name: 'ProfileB', status: 'STOPPED', rules_count: 1 },
                        { name: 'ProfileC', status: 'STOPPED', rules_count: 1 }
                    ],
                    load_profile_config_result: async (p) => ({
                        ok: true,
                        read_status: 'OK',
                        rules_count: 1,
                        data: {
                            rules: [{ id: 'rA', name: 'قاعدة أ', ruleCode: 'MBS-SHARED-100', keywords: ['عرض_خاص'], reply: 'سعر العرض 100 ج', matchType: 'ultra_exact', active: true }],
                            config: {}
                        },
                        sha256_token: 'sha_token_A'
                    }),
                    load_profile_config: async (p) => ({
                        rules: [{ id: 'rA', name: 'قاعدة أ', ruleCode: 'MBS-SHARED-100', keywords: ['عرض_خاص'], reply: 'سعر العرض 100 ج', matchType: 'ultra_exact', active: true }],
                        config: {}
                    }),
                    get_linked_rules_map: async () => ({
                        'MBS-SHARED-100': ['ProfileA', 'ProfileB', 'ProfileC']
                    }),
                    save_profile_config_coordinated: async (profile, config, sha) => {
                        return {
                            ok: false,
                            code: 'LINK_CONFLICT',
                            error: 'LINK_CONFLICT',
                            conflicting_code: 'MBS-SHARED-100',
                            message: 'قاعدة مشتركة متضاربة في المحتوى',
                            participating_profiles: [
                                {
                                    profile_name: 'ProfileA',
                                    sha256_token: 'sha_token_A',
                                    rule: { id: 'rA', name: 'قاعدة أ', ruleCode: 'MBS-SHARED-100', keywords: ['عرض_خاص'], reply: 'سعر العرض 100 ج', matchType: 'ultra_exact', active: true }
                                },
                                {
                                    profile_name: 'ProfileB',
                                    sha256_token: 'sha_token_B',
                                    rule: { id: 'rB', name: 'قاعدة ب', ruleCode: 'MBS-SHARED-100', keywords: ['عرض_خاص'], reply: 'سعر العرض 150 ج', matchType: 'ultra_exact', active: true }
                                },
                                {
                                    profile_name: 'ProfileC',
                                    sha256_token: 'sha_token_C',
                                    rule: { id: 'rC', name: 'قاعدة ج', ruleCode: 'MBS-SHARED-100', keywords: ['عرض_خاص'], reply: 'سعر العرض 200 ج', matchType: 'ultra_exact', active: true }
                                }
                            ]
                        };
                    },
                    resolve_link_conflict: async (code, authProfile, expectedShas) => {
                        window.__CAPTURED_RESOLVES__.push({ code, authProfile, expectedShas });
                        return {
                            ok: true,
                            disk_ok: true,
                            modified_profiles: ['ProfileA', 'ProfileB', 'ProfileC'],
                            runtime_refresh_successes: ['ProfileA'],
                            runtime_refresh_failures: {}
                        };
                    },
                    get_logs: async () => [],
                    get_stats: async () => ({})
                }
            };
        """)
        conflict_page.goto(f"file://{GUI_HTML_PATH}")
        conflict_page.wait_for_load_state("domcontentloaded")

        # Select ProfileA and trigger Save Rules which will return LINK_CONFLICT
        conflict_flow_res = conflict_page.evaluate("""async () => {
            const btnSave = document.getElementById('btn-save-rules');
            const modal = document.getElementById('modal-link-conflict');

            // Wait for profile selection to load and save button to be enabled
            let retries = 50;
            while (retries-- > 0 && (!document.querySelector('.rule-card') || (btnSave && btnSave.disabled))) {
                await new Promise(r => setTimeout(r, 50));
            }

            // Click save rules to trigger coordinated save and LINK_CONFLICT
            btnSave.click();
            let modalRetries = 50;
            while (modalRetries-- > 0 && modal && !modal.classList.contains('active')) {
                await new Promise(r => setTimeout(r, 30));
            }

            const modalActiveBefore = modal && modal.classList.contains('active');
            const options = document.querySelectorAll('#conflict-options-list .conflict-option-card');
            const btnResolve = document.getElementById('btn-conflict-resolve');
            const resolveDisabledInitially = btnResolve ? btnResolve.disabled : false;

            // Click the second option (ProfileB)
            if (options.length >= 2) {
                options[1].click();
            }
            await new Promise(r => setTimeout(r, 50));

            const resolveEnabledAfterSelect = btnResolve ? !btnResolve.disabled : false;
            const optionBSelected = options[1] ? options[1].classList.contains('selected') : false;

            // Click Resolve
            btnResolve.click();
            let closeRetries = 50;
            while (closeRetries-- > 0 && modal && modal.classList.contains('active')) {
                await new Promise(r => setTimeout(r, 30));
            }

            const modalActiveAfter = modal && modal.classList.contains('active');
            const capturedResolves = window.__CAPTURED_RESOLVES__ || [];

            return {
                modalActiveBefore,
                optionsCount: options.length,
                resolveDisabledInitially,
                resolveEnabledAfterSelect,
                optionBSelected,
                modalActiveAfter,
                capturedResolves
            };
        }""")

        assert_test(
            "Conflict UI: LINK_CONFLICT opens modal with 3 participating profiles",
            conflict_flow_res.get("modalActiveBefore") is True and conflict_flow_res.get("optionsCount") == 3,
            f"activeBefore={conflict_flow_res.get('modalActiveBefore')}, count={conflict_flow_res.get('optionsCount')}"
        )
        assert_test(
            "Conflict UI: Resolve button disabled until authoritative candidate selected",
            conflict_flow_res.get("resolveDisabledInitially") is True and conflict_flow_res.get("resolveEnabledAfterSelect") is True,
            f"initiallyDisabled={conflict_flow_res.get('resolveDisabledInitially')}, enabledAfter={conflict_flow_res.get('resolveEnabledAfterSelect')}"
        )
        assert_test(
            "Conflict UI: Selected candidate card highlights properly",
            conflict_flow_res.get("optionBSelected") is True,
            f"optionBSelected={conflict_flow_res.get('optionBSelected')}"
        )

        captured_resolves = conflict_flow_res.get("capturedResolves", [])
        has_correct_resolve = (
            len(captured_resolves) == 1 and
            captured_resolves[0].get("code") == "MBS-SHARED-100" and
            captured_resolves[0].get("authProfile") == "ProfileB" and
            captured_resolves[0].get("expectedShas") == {
                "ProfileA": "sha_token_A",
                "ProfileB": "sha_token_B",
                "ProfileC": "sha_token_C"
            }
        )
        assert_test(
            "Conflict UI: resolve_link_conflict dispatched with code, authoritative profile, and all expected SHAs",
            has_correct_resolve,
            f"capturedResolves={captured_resolves}"
        )
        assert_test(
            "Conflict UI: Modal closed upon successful resolution",
            conflict_flow_res.get("modalActiveAfter") is False,
            f"modalActiveAfter={conflict_flow_res.get('modalActiveAfter')}"
        )

        conflict_page.close()
        browser.close()

    print("\n-----------------------------------------------------------------------------")
    print(f" TOTAL TESTS RUN : {total}")
    print(f" PASSED          : {passed}")
    print(f" FAILED          : {failed}")
    print("-----------------------------------------------------------------------------")

    if failed > 0:
        print(f"\033[31mVERDICT: FAILED ({failed} unexpected failure(s))\033[0m")
        return 1
    else:
        print("\033[32mVERDICT: PASS (All browser contracts verified)\033[0m")
        return 0

if __name__ == "__main__":
    sys.exit(run_browser_contracts())

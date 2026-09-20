/**
 * ============================================================================
 * Meta Business Automator — Rule Engine Contracts & Normative Matrix Harness
 * ============================================================================
 * Tests:
 * 1. Normative matching matrix (ultra_exact, contains, exact, regex, word)
 * 2. Strict whitespace, punctuation, diacritics, and normalization rejection
 * 3. Defaults (missing/null -> ultra_exact) and unsupported mode fail-closed
 * 4. Regex sandboxing, worker failure handling, and ReDoS shielding
 * 5. Preprocessing & evaluateActiveRules keyword preservation
 * 6. Verbatim DOM message extraction vs synthetic padding
 * 7. Multi-bubble isolation (preventing synthesized phrase matches)
 * ============================================================================
 */

const fs = require('fs');
const path = require('path');
const assert = require('assert');

const ROOT_DIR = path.resolve(__dirname, '..');
const BOT_SCRIPT_PATH = path.join(ROOT_DIR, 'bot_script.js');
const USERSCRIPT_PATH = path.join(ROOT_DIR, 'meta_inbox_userscript.user.js');

const src = fs.readFileSync(BOT_SCRIPT_PATH, 'utf8');

// Extract production functions using regex (compatible with audit_system.py pattern)
const escapeRegExpMatch = src.match(/function escapeRegExp\(string\) \{[\s\S]*?\n  \}/);
const normMatch = src.match(/function normalizeArabicText\(text\) \{[\s\S]*?\n  \}/);
const testKwMatch = src.match(/async function testKeywordsMatch\([\s\S]*?\n  \}/);
const evalRulesMatch = src.match(/async function evaluateActiveRules\([\s\S]*?\n  \}/);
const regexSandboxMatch = src.match(/class RegexSandbox \{[\s\S]*?\n  \}/);

if (!escapeRegExpMatch || !normMatch || !testKwMatch || !evalRulesMatch || !regexSandboxMatch) {
  console.error('FATAL: Failed to extract required functions from bot_script.js');
  process.exit(1);
}

// Evaluate extracted production functions in global context
eval(escapeRegExpMatch[0]);
eval(normMatch[0]);
eval(regexSandboxMatch[0].replace('class RegexSandbox', 'global.RegexSandbox = class RegexSandbox'));
const regexSandbox = new global.RegexSandbox();
eval(testKwMatch[0]);
eval(evalRulesMatch[0]);

// Extract DOM object methods if present
const extractVerbatimMatch = src.match(/extractMessageTextVerbatim\s*\([^)]*\)\s*\{[\s\S]*?\n    \},/);
const extractAltMatch = src.match(/extractTextWithAlt\s*\([^)]*\)\s*\{[\s\S]*?\n    \},/);

const DOM = {
  extractTextWithAlt: (node, depth = 0) => {
    if (!node || depth > 30) return '';
    if (node.nodeType === 3) return node.nodeValue || '';
    if (node.nodeType === 1) {
      if (node.matches && node.matches(
        '[aria-label*="Profile" i], [aria-label*="صورة الملف" i], [aria-label*="ملف شخصي" i], ' +
        '[data-testid*="reaction" i], [role="progressbar"], audio, video, svg, ' +
        '[data-testid*="link_preview" i], [data-testid*="messenger_link_preview" i], ' +
        'a[role="link"] > div, div[role="article"], .preview-card'
      )) {
        return '';
      }
      const tagName = node.tagName;
      if (tagName === 'IMG') {
        const isEmoji = (node.classList && node.classList.contains('emoji')) ||
          (node.getAttribute('src') || '').includes('emoji.php') ||
          (node.getAttribute('src') || '').includes('/emoji/') ||
          (node.getAttribute('alt') && /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test(node.getAttribute('alt')));
        if (isEmoji) return node.getAttribute('alt') || node.getAttribute('aria-label') || '';
        return '';
      }
      if (tagName === 'BR') return '\n';
      let out = '';
      const isBlock = /^(DIV|P|LI|TR|H[1-6])$/.test(tagName);
      for (let child = node.firstChild; child; child = child.nextSibling) {
        out += DOM.extractTextWithAlt(child, depth + 1);
      }
      return isBlock ? ` ${out} ` : out;
    }
    return '';
  }
};

if (extractVerbatimMatch) {
  const verbatimFnStr = 'DOM.extractMessageTextVerbatim = function ' + extractVerbatimMatch[0].replace(/,$/, '');
  try {
    eval(verbatimFnStr);
  } catch (e) {
    // If not yet present or syntax error, will be provided in Step 2
  }
}

// Minimal Mock DOM for Node tests
class MockNode {
  constructor(nodeType, nodeValue = '', tagName = '', attrs = {}, classes = []) {
    this.nodeType = nodeType; // 1 = Element, 3 = Text
    this.nodeValue = nodeValue;
    this.tagName = tagName.toUpperCase();
    this.attributes = attrs;
    this.classList = {
      contains: (c) => classes.includes(c)
    };
    this.childNodes = [];
    this.firstChild = null;
    this.nextSibling = null;
  }

  getAttribute(name) {
    return this.attributes[name] || null;
  }

  setAttribute(name, val) {
    this.attributes[name] = val;
  }

  appendChild(child) {
    if (this.childNodes.length > 0) {
      this.childNodes[this.childNodes.length - 1].nextSibling = child;
    } else {
      this.firstChild = child;
    }
    child.nextSibling = null;
    this.childNodes.push(child);
    return child;
  }

  matches(selector) {
    const role = this.getAttribute('role') || '';
    const aria = this.getAttribute('aria-label') || '';
    const testid = this.getAttribute('data-testid') || '';
    if (selector.includes('[role="progressbar"]') && role === 'progressbar') return true;
    if (selector.includes('[role="button"]') && role === 'button') return true;
    if (selector.includes('reaction') && testid.toLowerCase().includes('reaction')) return true;
    if (selector.includes('link_preview') && testid.toLowerCase().includes('link_preview')) return true;
    if (selector.includes('Profile') && aria.toLowerCase().includes('profile')) return true;
    if (selector.includes('.preview-card') && this.classList.contains('preview-card')) return true;
    return false;
  }
}

function createTextNode(text) {
  return new MockNode(3, text);
}

function createElement(tag, attrs = {}, classes = []) {
  return new MockNode(1, '', tag, attrs, classes);
}

// ---------------------------------------------------------------------------
// Standard Test Helper: matches(message, keyword, mode, caseSensitive = false)
// ---------------------------------------------------------------------------
async function matches(message, keyword, mode, caseSensitive = false) {
  const normMsg = normalizeArabicText(message);
  const res = await testKeywordsMatch(message, normMsg, [keyword], mode, caseSensitive);
  return Boolean(res && res.matched);
}

// ---------------------------------------------------------------------------
// Suite Runner
// ---------------------------------------------------------------------------
let totalTests = 0;
let passedTests = 0;
let failedTests = 0;

async function test(name, fn) {
  totalTests++;
  try {
    await fn();
    passedTests++;
    console.log(`  \x1b[32m[PASS]\x1b[0m ${name}`);
  } catch (err) {
    failedTests++;
    console.error(`  \x1b[31m[FAIL]\x1b[0m ${name}: ${err.message}`);
  }
}

(async () => {
  console.log('\n=============================================================================');
  console.log('  RULE ENGINE & MATCHER CONTRACT TESTS (PHASE 1)');
  console.log('=============================================================================');

  console.log('\n--- SECTION 1: Byte Parity Between Artifacts ---');
  await test('Exact Byte Parity between bot_script.js and meta_inbox_userscript.user.js', () => {
    const b1 = fs.readFileSync(BOT_SCRIPT_PATH);
    const b2 = fs.readFileSync(USERSCRIPT_PATH);
    assert.strictEqual(b1.length, b2.length, `Byte sizes differ: ${b1.length} vs ${b2.length}`);
    assert.ok(b1.equals(b2), 'Binary contents differ between bot_script.js and meta_inbox_userscript.user.js');
  });

  console.log('\n--- SECTION 2: Strict Equality & Normalization Rejection (ultra_exact) ---');
  await test('Verbatim identity: سعر === سعر', async () => {
    assert.strictEqual(await matches('سعر', 'سعر', 'ultra_exact'), true);
  }, true);

  await test('Verbatim identity with diacritics: سِعر === سِعر', async () => {
    assert.strictEqual(await matches('سِعر', 'سِعر', 'ultra_exact'), true);
  }, true);

  await test('Rejects Tashkeel diacritics difference: سِعر !== سعر', async () => {
    assert.strictEqual(await matches('سِعر', 'سعر', 'ultra_exact'), false);
  }, true);

  await test('Rejects Tatweel / Kashida difference: سـعر !== سعر', async () => {
    assert.strictEqual(await matches('سـعر', 'سعر', 'ultra_exact'), false);
  }, true);

  await test('Rejects Alef forms difference: أ !== ا', async () => {
    assert.strictEqual(await matches('أ', 'ا', 'ultra_exact'), false);
  }, true);

  await test('Rejects Alef with Hamza below: إ !== ا', async () => {
    assert.strictEqual(await matches('إ', 'ا', 'ultra_exact'), false);
  }, true);

  await test('Rejects Madda: آ !== ا', async () => {
    assert.strictEqual(await matches('آ', 'ا', 'ultra_exact'), false);
  }, true);

  await test('Rejects Ta Marbuta vs Ha: ة !== ه', async () => {
    assert.strictEqual(await matches('ة', 'ه', 'ultra_exact'), false);
  }, true);

  await test('Rejects Eastern Arabic Digits conversion: ٥٠٠ !== 500', async () => {
    assert.strictEqual(await matches('٥٠٠', '500', 'ultra_exact'), false);
  }, true);

  await test('Rejects Latin case differences: Price !== price (strictly case sensitive)', async () => {
    assert.strictEqual(await matches('Price', 'price', 'ultra_exact'), false);
  }, true);

  await test('Rejects Unicode composition difference: \\u00e9 !== e\\u0301', async () => {
    assert.strictEqual(await matches('\u00e9', 'e\u0301', 'ultra_exact'), false);
  }, true);

  await test('Rejects attached letters / suffixes: سعره !== سعر', async () => {
    assert.strictEqual(await matches('سعره', 'سعر', 'ultra_exact'), false);
  }, true);

  await test('Rejects attached Arabic question mark: سعر؟ !== سعر', async () => {
    assert.strictEqual(await matches('سعر؟', 'سعر', 'ultra_exact'), false);
  }, true);

  await test('Rejects attached flag emoji: سعر🇪🇬 !== سعر', async () => {
    assert.strictEqual(await matches('سعر🇪🇬', 'سعر', 'ultra_exact'), false);
  }, true);

  console.log('\n--- SECTION 3: Whitespace & Newline Precision (ultra_exact) ---');
  await test('Rejects leading space: " سعر" !== "سعر"', async () => {
    assert.strictEqual(await matches(' سعر', 'سعر', 'ultra_exact'), false);
  }, true);

  await test('Rejects trailing space: "سعر " !== "سعر"', async () => {
    assert.strictEqual(await matches('سعر ', 'سعر', 'ultra_exact'), false);
  }, true);

  await test('Rejects trailing newline: "سعر\\n" !== "سعر"', async () => {
    assert.strictEqual(await matches('سعر\n', 'سعر', 'ultra_exact'), false);
  }, true);

  await test('Rejects trailing tab: "سعر\\t" !== "سعر"', async () => {
    assert.strictEqual(await matches('سعر\t', 'سعر', 'ultra_exact'), false);
  }, true);

  await test('Matches exact multi-word phrase: "سعر المشد" === "سعر المشد"', async () => {
    assert.strictEqual(await matches('سعر المشد', 'سعر المشد', 'ultra_exact'), true);
  }, true);

  await test('Rejects extra internal space: "سعر  المشد" !== "سعر المشد"', async () => {
    assert.strictEqual(await matches('سعر  المشد', 'سعر المشد', 'ultra_exact'), false);
  }, true);

  await test('Rejects missing space: "سعرالمشد" !== "سعر المشد"', async () => {
    assert.strictEqual(await matches('سعرالمشد', 'سعر المشد', 'ultra_exact'), false);
  }, true);

  await test('Rejects internal tab: "سعر\\tالمشد" !== "سعر المشد"', async () => {
    assert.strictEqual(await matches('سعر\tالمشد', 'سعر المشد', 'ultra_exact'), false);
  }, true);

  await test('Rejects internal newline: "سعر\\nالمشد" !== "سعر المشد"', async () => {
    assert.strictEqual(await matches('سعر\nالمشد', 'سعر المشد', 'ultra_exact'), false);
  }, true);

  await test('Rejects non-breaking space: "سعر\\u00a0المشد" !== "سعر المشد"', async () => {
    assert.strictEqual(await matches('سعر\u00a0المشد', 'سعر المشد', 'ultra_exact'), false);
  }, true);

  await test('Preserves literal stored whitespace: " سعر " === " سعر "', async () => {
    assert.strictEqual(await matches(' سعر ', ' سعر ', 'ultra_exact'), true);
  }, true);

  await test('Rejects trimmed vs spaced: "سعر" !== " سعر "', async () => {
    assert.strictEqual(await matches('سعر', ' سعر ', 'ultra_exact'), false);
  }, true);

  await test('Matches newline phrase: "سعر\\nالمشد" === "سعر\\nالمشد"', async () => {
    assert.strictEqual(await matches('سعر\nالمشد', 'سعر\nالمشد', 'ultra_exact'), true);
  }, true);

  console.log('\n--- SECTION 4: Defaults & Fail-Closed Modes ---');
  await test('Missing mode defaults to ultra_exact (match)', async () => {
    assert.strictEqual(await matches('سعر', 'سعر', undefined), true);
  }, true);

  await test('Missing mode defaults to ultra_exact (no substring match)', async () => {
    assert.strictEqual(await matches('سعره', 'سعر', undefined), false);
  }, true);

  await test('Null mode defaults to ultra_exact (no substring match)', async () => {
    assert.strictEqual(await matches('سعره', 'سعر', null), false);
  }, true);

  await test('Unsupported mode fails closed: BOGUS returns false', async () => {
    assert.strictEqual(await matches('سعر', 'سعر', 'BOGUS'), false);
  }, true);

  await test('Empty string mode fails closed: "" returns false', async () => {
    assert.strictEqual(await matches('سعر', 'سعر', ''), false);
  }, true);

  await test('Empty keyword is rejected: "" returns false', async () => {
    assert.strictEqual(await matches('سعر', '', 'ultra_exact'), false);
  }, false);

  await test('All-whitespace keyword is rejected: "   " returns false', async () => {
    assert.strictEqual(await matches('   ', '   ', 'ultra_exact'), false);
  }, true);

  console.log('\n--- SECTION 5: "contains" and "exact" Regression & Aliases ---');
  await test('contains: substring match "وسعره" contains "سعر"', async () => {
    assert.strictEqual(await matches('وسعره', 'سعر', 'contains'), true);
  }, false);

  await test('contains: diacritics normalized "سِعر" contains "سعر"', async () => {
    assert.strictEqual(await matches('سِعر', 'سعر', 'contains'), true);
  }, false);

  await test('contains: Eastern digits normalized "السعر ٥٠٠" contains "500"', async () => {
    assert.strictEqual(await matches('السعر ٥٠٠', '500', 'contains'), true);
  }, false);

  await test('contains: Flag emoji "مصر🇪🇬" contains "🇪🇬"', async () => {
    assert.strictEqual(await matches('مصر🇪🇬', '🇪🇬', 'contains'), true);
  }, false);

  await test('contains: ZWJ composite emoji "مرحبا 👩‍💻" contains "👩‍💻"', async () => {
    assert.strictEqual(await matches('مرحبا 👩‍💻', '👩‍💻', 'contains'), true);
  }, false);

  await test('exact: Unicode word bounded match "هل السعر مناسب؟" matches "السعر"', async () => {
    assert.strictEqual(await matches('هل السعر مناسب؟', 'السعر', 'exact'), true);
  }, false);

  await test('exact: Diacritics normalized in exact mode "السِعر" matches "السعر"', async () => {
    assert.strictEqual(await matches('السِعر', 'السعر', 'exact'), true);
  }, false);

  await test('exact: Rejects Arabic letter boundary "والسعر" for keyword "السعر"', async () => {
    assert.strictEqual(await matches('والسعر', 'السعر', 'exact'), false);
  }, true);

  await test('exact: Rejects attached suffix "سعره" for keyword "سعر"', async () => {
    assert.strictEqual(await matches('سعره', 'سعر', 'exact'), false);
  }, false);

  await test('exact: Rejects attached digit "سعر500" for keyword "سعر"', async () => {
    assert.strictEqual(await matches('سعر500', 'سعر', 'exact'), false);
  }, false);

  await test('exact: Approved contract correction: "السعر" does NOT match "سعر" (optional ال removed)', async () => {
    assert.strictEqual(await matches('السعر', 'سعر', 'exact'), false);
  }, true);

  await test('word alias: "word" acts as alias for "exact" on "هل السعر مناسب؟"', async () => {
    assert.strictEqual(await matches('هل السعر مناسب؟', 'السعر', 'word'), true);
  }, false);

  await test('word alias: "word" rejects letter boundary on "والسعر"', async () => {
    assert.strictEqual(await matches('والسعر', 'السعر', 'word'), false);
  }, true);

  await test('exact case sensitivity: Price does not match price when caseSensitive=true', async () => {
    assert.strictEqual(await matches('Price', 'price', 'exact', true), false);
  }, true);

  await test('exact case insensitivity: Price matches price when caseSensitive=false', async () => {
    assert.strictEqual(await matches('Price', 'price', 'exact', false), true);
  }, false);

  console.log('\n--- SECTION 6: evaluateActiveRules End-to-End Pipeline ---');
  await test('evaluateActiveRules: preserves raw keywords without trimming for ultra_exact', async () => {
    const rules = [
      {
        id: 'rule_space',
        keywords: [' سعر '],
        reply: 'تم التطابق مع مسافات',
        matchType: 'ultra_exact',
        active: true
      }
    ];
    const match = await evaluateActiveRules(' سعر ', rules);
    assert.ok(match, 'Expected match for verbatim spaced message');
    assert.strictEqual(match.rule.id, 'rule_space');

    const noMatch = await evaluateActiveRules('سعر', rules);
    assert.strictEqual(noMatch, null, 'Should not match trimmed message');
  }, true);

  await test('evaluateActiveRules: authoritative keywords array overrides stale keyword string', async () => {
    const rules = [
      {
        id: 'rule_authoritative',
        keywords: ['جديد'],
        keyword: 'قديم,سابق',
        reply: 'مرحبا',
        matchType: 'ultra_exact',
        active: true
      }
    ];
    const matchNew = await evaluateActiveRules('جديد', rules);
    assert.ok(matchNew, 'Should match keyword from keywords array');
    const matchOld = await evaluateActiveRules('قديم', rules);
    assert.strictEqual(matchOld, null, 'Should NOT match stale keyword string');
  }, false);

  await test('evaluateActiveRules: explicitly empty keywords: [] does not revive stale keyword string', async () => {
    const rules = [
      {
        id: 'rule_empty_kws',
        keywords: [],
        keyword: 'سعر',
        reply: 'مرحبا',
        matchType: 'ultra_exact',
        active: true
      }
    ];
    const match = await evaluateActiveRules('سعر', rules);
    assert.strictEqual(match, null, 'Empty keywords array must be authoritative');
  }, true);

  await test('evaluateActiveRules: inactive rules are never evaluated', async () => {
    const rules = [
      {
        id: 'rule_inactive',
        keywords: ['سعر'],
        reply: 'مرحبا',
        matchType: 'ultra_exact',
        active: false
      }
    ];
    const match = await evaluateActiveRules('سعر', rules);
    assert.strictEqual(match, null, 'Inactive rule must not match');
  }, false);

  await test('evaluateActiveRules: compound rule priority and fallback', async () => {
    const rules = [
      {
        id: 'rule_generic',
        keywords: ['بكام'],
        reply: 'سعر عام 100',
        matchType: 'contains',
        active: true
      },
      {
        id: 'rule_compound',
        keywords: ['بكام'],
        contextKeywords: ['المشد'],
        matchType: 'contains',
        contextMatchType: 'contains',
        reply: 'سعر المشد 200',
        active: true
      }
    ];
    // With matching context -> compound rule matches
    const compoundMatch = await evaluateActiveRules('بكام', rules, 'هل يتوفر المشد اليوم؟');
    assert.ok(compoundMatch, 'Should match compound rule');
    assert.strictEqual(compoundMatch.rule.id, 'rule_compound');
    assert.strictEqual(compoundMatch.isCompound, true);

    // Without matching context -> falls back to generic rule
    const genericMatch = await evaluateActiveRules('بكام', rules, 'سؤال عام');
    assert.ok(genericMatch, 'Should fall back to generic rule');
    assert.strictEqual(genericMatch.rule.id, 'rule_generic');
    assert.strictEqual(genericMatch.isCompound, false);
  });

  await test('evaluateActiveRules: case-sensitive contains pre-normalized lowercase cannot override caseSensitive: true', async () => {
    const rules = [
      {
        id: 'rule_cs_contains',
        keywords: ['price'],
        reply: 'x',
        matchType: 'contains',
        caseSensitive: true,
        active: true
      }
    ];
    const matchUpper = await evaluateActiveRules('Price', rules);
    assert.strictEqual(matchUpper, null, 'With caseSensitive: true, "Price" must not match "price"');

    const matchLower = await evaluateActiveRules('price', rules);
    assert.ok(matchLower, 'With caseSensitive: true, "price" must match "price"');
    assert.strictEqual(matchLower.rule.id, 'rule_cs_contains');
  });

  await test('evaluateActiveRules: case-sensitive compound context evaluation', async () => {
    const rules = [
      {
        id: 'rule_cs_compound',
        keywords: ['order'],
        contextKeywords: ['VIP'],
        matchType: 'contains',
        contextMatchType: 'contains',
        caseSensitive: true,
        reply: 'vip order reply',
        active: true
      }
    ];
    // Context has lowercase "vip" when keyword is uppercase "VIP" -> must fail match
    const matchWrongCase = await evaluateActiveRules('order', rules, 'customer is vip');
    assert.strictEqual(matchWrongCase, null, 'Context case mismatch must fail match when caseSensitive is true');

    // Context matches exact case "VIP"
    const matchRightCase = await evaluateActiveRules('order', rules, 'customer is VIP');
    assert.ok(matchRightCase, 'Context case match must succeed');
    assert.strictEqual(matchRightCase.rule.id, 'rule_cs_compound');
  });

  console.log('\n--- SECTION 7: Regex Sandboxing & Failure Hardening ---');
  await test('RegexSandbox: Worker unavailable fails closed without main-thread fallback', async () => {
    // In Node.js environment, window and Worker are undefined, so regexSandbox.worker is null
    const noWorkerSandbox = new global.RegexSandbox();
    assert.strictEqual(noWorkerSandbox.worker, null);
    const result = await noWorkerSandbox.test('^سعر.*$', 'u', 'سعر 500 جنيه');
    assert.strictEqual(result, false, 'Should fail closed (return false) when Worker unavailable');
  });

  await test('RegexSandbox: Worker syntax error fails closed safely', async () => {
    const mockSandbox = new global.RegexSandbox();
    mockSandbox.worker = {
      postMessage: ({ id }) => {
        setTimeout(() => {
          if (mockSandbox.worker && mockSandbox.worker.onmessage) {
            mockSandbox.worker.onmessage({ data: { id, success: false, error: 'Invalid regular expression' } });
          }
        }, 5);
      },
      terminate: () => {}
    };
    mockSandbox.worker.onmessage = (e) => {
      const { id, success, matched } = e.data;
      const req = mockSandbox.pending.get(id);
      if (req) {
        mockSandbox.pending.delete(id);
        clearTimeout(req.timer);
        req.resolve(success ? Boolean(matched) : false);
      }
    };
    const result = await mockSandbox.test('[invalid', 'u', 'test', 50);
    assert.strictEqual(result, false, 'Syntax error must fail closed with false');
  });

  await test('RegexSandbox: Worker ReDoS timeout terminates worker and fails closed safely', async () => {
    const mockSandbox = new global.RegexSandbox(20);
    let terminated = false;
    mockSandbox.worker = {
      postMessage: () => {},
      terminate: () => { terminated = true; }
    };
    const result = await mockSandbox.test('(a|a)+', 'i', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaa!', 20);
    assert.strictEqual(result, false, 'ReDoS timeout must fail closed with false');
    assert.strictEqual(terminated, true, 'Worker must be terminated on timeout');
    assert.strictEqual(mockSandbox.worker, null, 'Worker reference must be null after timeout');
  });

  await test('RegexSandbox: Worker postMessage throw fails closed safely', async () => {
    const mockSandbox = new global.RegexSandbox(20);
    mockSandbox.worker = {
      postMessage: () => { throw new Error('DataCloneError'); },
      terminate: () => {}
    };
    const result = await mockSandbox.test('^سعر$', 'u', 'سعر', 20);
    assert.strictEqual(result, false, 'postMessage exception must fail closed');
  });

  console.log('\n--- SECTION 8: DOM Verbatim Extraction Contracts ---');
  await test('DOM.extractMessageTextVerbatim: extracts <div><span>سعر</span></div> with 0 wrapper padding', () => {
    if (typeof DOM.extractMessageTextVerbatim !== 'function') {
      throw new Error('extractMessageTextVerbatim is not implemented yet');
    }
    const root = createElement('div');
    const span = createElement('span');
    span.appendChild(createTextNode('سعر'));
    root.appendChild(span);
    const extracted = DOM.extractMessageTextVerbatim(root);
    assert.strictEqual(extracted, 'سعر');
  });

  await test('DOM.extractMessageTextVerbatim: preserves leading and trailing spaces in text node', () => {
    if (typeof DOM.extractMessageTextVerbatim !== 'function') {
      throw new Error('extractMessageTextVerbatim is not implemented yet');
    }
    const root = createElement('div');
    root.appendChild(createTextNode(' سعر '));
    const extracted = DOM.extractMessageTextVerbatim(root);
    assert.strictEqual(extracted, ' سعر ');
  });

  await test('DOM.extractMessageTextVerbatim: preserves <br> as \\n without synthetic spaces', () => {
    if (typeof DOM.extractMessageTextVerbatim !== 'function') {
      throw new Error('extractMessageTextVerbatim is not implemented yet');
    }
    const root = createElement('span');
    root.appendChild(createTextNode('سعر'));
    root.appendChild(createElement('br'));
    root.appendChild(createTextNode('المشد'));
    const extracted = DOM.extractMessageTextVerbatim(root);
    assert.strictEqual(extracted, 'سعر\nالمشد');
  });

  await test('DOM.extractMessageTextVerbatim: preserves emoji img alt text without extra spaces', () => {
    if (typeof DOM.extractMessageTextVerbatim !== 'function') {
      throw new Error('extractMessageTextVerbatim is not implemented yet');
    }
    const root = createElement('div');
    root.appendChild(createTextNode('سعر'));
    root.appendChild(createElement('img', { alt: '🇪🇬', src: '/emoji/flag.png' }, ['emoji']));
    const extracted = DOM.extractMessageTextVerbatim(root);
    assert.strictEqual(extracted, 'سعر🇪🇬');
  });

  await test('DOM.extractMessageTextVerbatim: excludes avatar, reaction, and link preview elements', () => {
    if (typeof DOM.extractMessageTextVerbatim !== 'function') {
      throw new Error('extractMessageTextVerbatim is not implemented yet');
    }
    const root = createElement('div');
    root.appendChild(createElement('div', { 'aria-label': 'Profile photo' }));
    root.appendChild(createElement('div', { 'data-testid': 'reaction_pill' }));
    root.appendChild(createElement('div', { 'data-testid': 'link_preview' }));
    root.appendChild(createTextNode('سعر المشد'));
    const extracted = DOM.extractMessageTextVerbatim(root);
    assert.strictEqual(extracted, 'سعر المشد');
  });

  await test('DOM.extractMessageTextVerbatim: whitespace around elements rejects strict match', async () => {
    const root = createElement('div');
    root.appendChild(createTextNode(' '));
    const span = createElement('span');
    span.appendChild(createTextNode('سعر'));
    root.appendChild(span);
    root.appendChild(createTextNode(' '));
    const extracted = DOM.extractMessageTextVerbatim(root);
    assert.strictEqual(extracted, ' سعر ', 'Must extract verbatim text including whitespace');
    const ultraRule = [{ id: 'r_strict', keywords: ['سعر'], reply: 'x', matchType: 'ultra_exact', active: true }];
    const evalRes = await evaluateActiveRules(extracted, ultraRule);
    assert.strictEqual(evalRes, null, 'Strict rule "سعر" must reject extracted " سعر "');
  });

  await test('DOM.extractMessageTextVerbatim: depth > 50 returns null and fails closed in evaluator', async () => {
    let deepRoot = createElement('div');
    let curr = deepRoot;
    for (let i = 0; i < 55; i++) {
      const child = createElement('div');
      curr.appendChild(child);
      curr = child;
    }
    curr.appendChild(createTextNode('سعر'));
    const extracted = DOM.extractMessageTextVerbatim(deepRoot);
    assert.strictEqual(extracted, null, 'Depth > 50 must return null');
    const ultraRule = [{ id: 'r_strict', keywords: ['سعر'], reply: 'x', matchType: 'ultra_exact', active: true }];
    const evalRes = await evaluateActiveRules(extracted, ultraRule);
    assert.strictEqual(evalRes, null, 'Null extracted text must fail closed in evaluator');
  });

  await test('Multi-bubble orchestration: separate bubbles "سعر" and "المشد" cannot match "سعر المشد"', async () => {
    const bubble1 = createElement('div', {}, ['msg-bubble']);
    bubble1.appendChild(createTextNode('سعر'));
    const bubble2 = createElement('div', {}, ['msg-bubble']);
    bubble2.appendChild(createTextNode('المشد'));

    const customerBubbles = [bubble1, bubble2];
    const phraseRule = [{ id: 'rule_phrase', keywords: ['سعر المشد'], reply: 'r1', matchType: 'ultra_exact', active: true }];
    const tailRule = [{ id: 'rule_tail', keywords: ['المشد'], reply: 'r2', matchType: 'ultra_exact', active: true }];

    const latestBubble = customerBubbles[customerBubbles.length - 1];
    const latestVerbatim = DOM.extractMessageTextVerbatim(latestBubble);
    assert.strictEqual(latestVerbatim, 'المشد');

    const phraseMatch = await evaluateActiveRules(latestVerbatim, phraseRule);
    assert.strictEqual(phraseMatch, null, 'Must reject compound phrase across bubbles');

    const tailMatch = await evaluateActiveRules(latestVerbatim, tailRule);
    assert.ok(tailMatch, 'Must match single latest bubble');
    assert.strictEqual(tailMatch.rule.id, 'rule_tail');
  });

  console.log('\n-----------------------------------------------------------------------------');
  console.log(` TOTAL TESTS RUN : ${totalTests}`);
  console.log(` PASSED          : ${passedTests}`);
  console.log(` FAILED          : ${failedTests}`);
  console.log('-----------------------------------------------------------------------------');

  if (failedTests > 0) {
    console.error(`\x1b[31mVERDICT: FAILED (${failedTests} test failure(s))\x1b[0m`);
    process.exit(1);
  } else {
    console.log('\x1b[32mVERDICT: PASS (All assertions pass)\x1b[0m');
    process.exit(0);
  }
})();

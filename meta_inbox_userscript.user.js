// ==UserScript==
// @name         Meta Business Suite Inbox Auto-Responder & Unread Restorer (Enterprise V5.2.0)
// @namespace    https://github.com/meta-suite-automation/tampermonkey
// @version      5.2.0
// @description  Apple Prismatic Liquid Glass Edition: High-Translucency Prismatic UI & Liquid Glass Pill Highlights, Single-Field Duration & Typing Controls, Dynamic Page Storage Isolation, Resolution-Invariant Envelope Locator, Anti-False-Drop Ad Guard, LRU Ring-Buffer & Ghost Stealth Capsule.
// @author       Bishoy Safwat (Senior Automation Engineer)
// @match        https://business.facebook.com/latest/inbox/*
// @match        https://business.facebook.com/latest/inbox/all*
// @icon         https://www.facebook.com/favicon.ico
// @grant        none
// @run-at       document-idle
// ==/UserScript==

/**
 * ============================================================================
 * META BUSINESS SUITE INBOX AUTOMATOR (ENTERPRISE PRODUCTION RELEASE V5.2.0)
 * ============================================================================
 * ARCHITECTURAL SPECIFICATION & FEATURES:
 * 1. APPLE PRISMATIC LIQUID GLASS INTERFACE & PILL HIGHLIGHTS:
 *    - High-translucency liquid glass surface (blur 28px, saturate 200%, lavender/aqua refractive glow).
 *    - Apple liquid glass pill styling for active conversation row & customer message aura.
 *    - Subdued native Apple buttons (soft red glass stop, system blue start pill).
 *    - Pure white active tabs, crisp slate typography (#0f172a, #334155, #475569).
 *    - Clean "Meta Automation" branding with zero version chips.
 *    - Single-field typing speed control (ms/char) & decimal seconds duration controls.
 * 2. DYNAMIC PAGE STORAGE ISOLATION (ZERO CROSS-TALK):
 *    - Automatically detects active asset_id / mailbox_id from URL query/path.
 *    - Namespaces all localStorage keys: MBS_RULES_${asset_id}, MBS_CONFIG_${asset_id}, MBS_GHOST_${asset_id}.
 *    - Dynamic SPA re-hydration: auto-switches rules/config when operator navigates between pages.
 * 3. ZERO-LATENCY INSTANT HARD-STOP ENGINE:
 *    - Cancellable sleep infrastructure with active rejector registry (abortAllSleeps).
 *    - Instant breakout (<10ms) on Stop click or Escape key, clearing outlines and halting typing.
 * 4. BULLETPROOF RULES & CONFIG PERSISTENCE:
 *    - Strict null-check fallback preventing accidental overwrite of empty/custom rules by defaults.
 *    - Real-time two-way synchronization on both input and change events.
 * 5. RESOLUTION-INVARIANT ENVELOPE LOCATOR & DROPDOWN FALLBACK:
 *    - Scoped chat header & action toolbar discovery without hardcoded coordinates.
 *    - 4-Tier discovery strategy: attributes -> "Done" sibling -> envelope SVG path -> scoped dropdown fallback.
 * 6. ANTI-FALSE-DROP AD GUARD:
 *    - Length & Context gate prevents valid customer inquiries referencing ads from being dropped.
 * 7. LRU MEMORY RING-BUFFER:
 *    - Bounded cache eviction (max 350, prune 100) for 24/7 continuous operation without memory leaks.
 *    - Evicts stale thread IDs to prevent memory leaks during prolonged unattended runs.
 * 8. GHOST STEALTH DOCK:
 *    - Minimal fluid crystal capsule (100x32px) with monochrome counter and clean pulsing dot.
 *    - Delicate sky-blue rim & top specular reflection.
 * 9. INBOUND MESSAGE BOUNDARY PARSING:
 *    - Evaluates customer messages arriving strictly after the last staff/page reply.
 *    - Immediately skips and preserves unread status if the latest thread message is outbound.
 * 10. HUMAN SIMULATOR:
 *    - Character-by-character typing with natural jitter and punctuation delays.
 *    - Lexical composer clearing verification.
 *    - Natural human cooldowns.
 * ============================================================================
 */

(function () {
  'use strict';

  // Only run in top-level browsing context (ignore nested iframes)
  if (window.top !== window.self) return;

  if (window.__MBS_AUTOMATOR_V520_LOADED__) {
    console.log('[MBS Automator] Already mounted. Re-initializing HUD...');
    if (window.__MBS_AUTOMATOR_HUD__) {
      window.__MBS_AUTOMATOR_HUD__.init();
    }
    return;
  }
  window.__MBS_AUTOMATOR_V520_LOADED__ = true;

  // ---------------------------------------------------------------------------
  // 1. DYNAMIC TENANT EXTRACTION & STORAGE ISOLATION
  // ---------------------------------------------------------------------------
  function getActiveTenantId() {
    try {
      const url = new URL(window.location.href);
      // 1. Check Search Parameters
      const assetId = url.searchParams.get('asset_id');
      if (assetId && /^[0-9a-zA-Z_-]+$/.test(assetId)) return assetId;

      const mailboxId = url.searchParams.get('mailbox_id');
      if (mailboxId && /^[0-9a-zA-Z_-]+$/.test(mailboxId)) return mailboxId;

      const pageId = url.searchParams.get('page_id');
      if (pageId && /^[0-9a-zA-Z_-]+$/.test(pageId)) return pageId;

      const businessId = url.searchParams.get('business_id');
      if (businessId && /^[0-9a-zA-Z_-]+$/.test(businessId)) return businessId;

      // 2. Check Pathname: /inbox/(all/)?([0-9]{8,})
      const pathMatch = url.pathname.match(/\/inbox\/(?:all\/|messenger\/|instagram\/)?([0-9]{8,})/);
      if (pathMatch && pathMatch[1]) return pathMatch[1];

      // 3. Fallback: inspect anchor links in page navigation
      const pageLink = document.querySelector('a[href*="asset_id="]');
      if (pageLink) {
        const match = pageLink.href.match(/asset_id=([0-9a-zA-Z_-]+)/);
        if (match && match[1]) return match[1];
      }
    } catch (_) {}
    return 'default';
  }

  function getTenantStorageKeys() {
    const tenantId = getActiveTenantId();
    return {
      tenantId,
      rulesKey: `MBS_RULES_${tenantId}`,
      configKey: `MBS_CONFIG_${tenantId}`,
      ghostKey: `MBS_GHOST_${tenantId}`,
      legacyRulesKey: 'MBS_AUTO_RULES_V44',
      legacyConfigKey: 'MBS_AUTO_CONFIG_V44',
      legacyGhostKey: 'MBS_AUTO_GHOST_MODE_V46'
    };
  }

  function pruneLRUCache(collection, maxLimit = 350, pruneCount = 100) {
    if (!collection) return;
    if (collection instanceof Map || collection instanceof Set) {
      if (collection.size > maxLimit) {
        let removed = 0;
        for (const key of collection.keys()) {
          collection.delete(key);
          removed++;
          if (removed >= pruneCount) break;
        }
      }
    }
  }

  const defaultRules = [
    {
      id: 'rule_price',
      keyword: 'سعر,كام,بكام,اسعار,تكلفة,تفاصيل,التفاصيل',
      reply: 'أهلاً بك! تفاصيل الأسعار والعروض متاحة لدينا الآن، يسعدنا تواصلك وسنوافيك بالتفاصيل فوراً.',
      matchType: 'contains',
      active: true
    },
    {
      id: 'rule_location',
      keyword: 'مكان,عنوان,الفرع,لوكيشن,موقع,فين,عناوين',
      reply: 'أهلاً بك! فرعنا متاح لخدمتك دائماً. يمكنك معرفة أقرب موقع والتواصل عبر الرابط أو الرسائل هنا.',
      matchType: 'contains',
      active: true
    },
    {
      id: 'rule_phone',
      keyword: 'فون,تليفون,رقم,واتس,واتساب,موبايل',
      reply: 'أهلاً بك! رقم خدمة العملاء والواتساب متاح لمساعدتك على مدار الساعة، تفضل بالاستفسار في أي وقت.',
      matchType: 'contains',
      active: true
    }
  ];

  const defaultConfig = {
    typingSpeed: 45,
    minTypingSpeed: 35,
    maxTypingSpeed: 65,
    minCooldown: 1500,
    maxCooldown: 2500,
    scrollThread: false,
    highlightRows: true,
    monitoringInterval: 6000
  };

  const state = {
    isRunning: false,
    emergencyAbort: false,
    currentIndex: 0,
    currentTenantId: getActiveTenantId(),
    rules: loadRules(),
    config: loadConfig(),
    processedContacts: new Set(),
    lastRepliedSnippets: new Map(),
    processedSnapshots: new Set(),
    skippedRows: new Set(),
    activeRowElement: null,
    activeRowOriginalStyles: null,
    stats: {
      evaluated: 0,
      matched: 0,
      unreadRestored: 0,
      skippedOutbound: 0,
      errors: 0
    }
  };

  function loadRules() {
    try {
      if (window.__INITIAL_RULES__ && Array.isArray(window.__INITIAL_RULES__) && window.__INITIAL_RULES__.length > 0) {
        return window.__INITIAL_RULES__;
      }
      const { rulesKey, legacyRulesKey } = getTenantStorageKeys();
      const raw = localStorage.getItem(rulesKey);
      if (raw !== null) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) return parsed;
      }
      // Only fallback to legacy key if the tenant key is strictly null in localStorage
      const legacyRaw = localStorage.getItem(legacyRulesKey);
      if (legacyRaw !== null) {
        const legacyParsed = JSON.parse(legacyRaw);
        if (Array.isArray(legacyParsed)) return legacyParsed;
      }
    } catch (_) {}
    return JSON.parse(JSON.stringify(defaultRules));
  }

  let rulesDebounceTimer = null;
  function saveRules() {
    try {
      const { rulesKey } = getTenantStorageKeys();
      localStorage.setItem(rulesKey, JSON.stringify(state.rules));
    } catch (_) {}

    if (rulesDebounceTimer) clearTimeout(rulesDebounceTimer);
    rulesDebounceTimer = setTimeout(() => {
      if (window.pySaveConfig) {
        window.pySaveConfig(JSON.stringify(state.rules), JSON.stringify(state.config)).catch(() => {});
      }
    }, 400);
  }

  function loadConfig() {
    let cfg = { ...defaultConfig };
    try {
      if (window.__INITIAL_CONFIG__ && typeof window.__INITIAL_CONFIG__ === 'object') {
        cfg = { ...defaultConfig, ...window.__INITIAL_CONFIG__ };
      } else {
        const { configKey, legacyConfigKey } = getTenantStorageKeys();
        let data = localStorage.getItem(configKey);
        if (data === null) {
          data = localStorage.getItem(legacyConfigKey);
        }
        if (data !== null) {
          const parsed = JSON.parse(data);
          if (parsed && typeof parsed === 'object') cfg = { ...defaultConfig, ...parsed };
        }
      }
    } catch (_) {}
    cfg.typingSpeed = cfg.typingSpeed || Math.round(((cfg.minTypingSpeed || 35) + (cfg.maxTypingSpeed || 65)) / 2) || 45;
    return cfg;
  }

  let configDebounceTimer = null;
  function saveConfig() {
    try {
      const { configKey } = getTenantStorageKeys();
      localStorage.setItem(configKey, JSON.stringify(state.config));
    } catch (_) {}

    if (configDebounceTimer) clearTimeout(configDebounceTimer);
    configDebounceTimer = setTimeout(() => {
      if (window.pySaveConfig) {
        window.pySaveConfig(JSON.stringify(state.rules), JSON.stringify(state.config)).catch(() => {});
      }
    }, 400);
  }

  function checkAndRehydrateTenant(hud) {
    const latestTenantId = getActiveTenantId();
    if (latestTenantId !== state.currentTenantId) {
      const prevTenantId = state.currentTenantId;
      state.currentTenantId = latestTenantId;
      state.rules = loadRules();
      state.config = loadConfig();
      // Clear thread & contact tracking sets for clean transition between pages
      state.processedContacts.clear();
      state.processedSnapshots.clear();
      state.lastRepliedSnippets.clear();

      if (hud) {
        hud.updateTenantUI(latestTenantId);
        hud.renderRulesList();
        hud.updateConfigUI();
        hud.log('INFO', `[Page] تم تبديل الصفحة النشطة (Page Switch: [${prevTenantId}] ➔ [${latestTenantId}]). تم إعادة تحميل القواعد والإعدادات تلقائياً.`);
      }
      return true;
    }
    return false;
  }

  // ---------------------------------------------------------------------------
  // 2. ARABIC TEXT NORMALIZATION & KEYWORD MATCHING
  // ---------------------------------------------------------------------------
  function normalizeArabicText(text) {
    if (!text || typeof text !== 'string') return '';
    return text
      .toLowerCase()
      .replace(/[أإآ]/g, 'ا')
      .replace(/[ة]/g, 'ه')
      .replace(/[ى]/g, 'ي')
      .replace(/[ؤئ]/g, 'ء')
      .replace(/[\u064B-\u065F\u0670]/g, '') // حذف التشكيل
      .replace(/[^\u0600-\u06FFa-zA-Z0-9\s]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function evaluateActiveRules(text, rules) {
    if (!text) return null;
    const normMsg = normalizeArabicText(text);
    if (!normMsg) return null;

    const words = new Set(normMsg.split(' '));

    for (const rule of rules) {
      if (!rule.active || !rule.keyword || !rule.reply) continue;

      const rawKeywords = rule.keyword.split(/[,،\n]+/).map(k => k.trim()).filter(Boolean);
      for (const kw of rawKeywords) {
        const normKw = normalizeArabicText(kw);
        if (!normKw) continue;

        const mType = rule.matchType || 'contains';
        if (mType === 'exact') {
          if (normMsg === normKw) return { rule, matchedKeyword: kw };
        } else if (mType === 'word') {
          if (words.has(normKw)) return { rule, matchedKeyword: kw };
        } else {
          // 'contains' (default)
          if (normMsg.includes(normKw)) return { rule, matchedKeyword: kw };
        }
      }
    }
    return null;
  }

  const activeSleepRejectors = new Set();

  function sleep(ms) {
    if (state.emergencyAbort) {
      return Promise.reject(new Error('ABORT_SIGNAL'));
    }
    return new Promise((resolve, reject) => {
      let timer = null;
      const rejector = (err) => {
        if (timer) clearTimeout(timer);
        activeSleepRejectors.delete(rejector);
        reject(err || new Error('ABORT_SIGNAL'));
      };
      timer = setTimeout(() => {
        activeSleepRejectors.delete(rejector);
        resolve();
      }, ms);
      activeSleepRejectors.add(rejector);
    });
  }

  function abortAllSleeps() {
    for (const reject of Array.from(activeSleepRejectors)) {
      try {
        reject(new Error('ABORT_SIGNAL'));
      } catch (_) {}
    }
    activeSleepRejectors.clear();
  }

  const randomRange = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

  function dispatchFullClick(el) {
    if (!el) return;
    try {
      if (typeof el.scrollIntoView === 'function') {
        el.scrollIntoView({ behavior: 'instant', block: 'nearest', inline: 'nearest' });
      }
    } catch (_) {}
    ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(evt => {
      try {
        el.dispatchEvent(new MouseEvent(evt, { bubbles: true, cancelable: true, view: window }));
      } catch (_) {}
    });
  }

  function releaseChatFocus() {
    try {
      if (document.activeElement && typeof document.activeElement.blur === 'function') {
        document.activeElement.blur();
      }
      const composer = DOM.getComposer();
      if (composer) {
        composer.dispatchEvent(new FocusEvent('blur', { bubbles: true }));
      }
      const chatCanvas = DOM.getChatCanvas();
      if (chatCanvas) {
        chatCanvas.dispatchEvent(new FocusEvent('blur', { bubbles: true }));
      }
      const neutral = document.querySelector('header, div[role="banner"], #mbs-inbox-automator-root');
      if (neutral) {
        neutral.dispatchEvent(new MouseEvent('click', { bubbles: true, view: window }));
      }
    } catch (_) {}
  }

  // ---------------------------------------------------------------------------
  // 3. DOM QUERY ENGINE & SELECTORS
  // ---------------------------------------------------------------------------
  const DOM = {
    sanitizeName(str) {
      if (!str) return '';
      return str
        .replace(/[\u200B-\u200D\uFEFF\u200E\u200F\u202A-\u202E]/g, '') // Strip Bidi & invisible chars
        .replace(/\s+/g, ' ')
        .trim();
    },

    getConversationRows() {
      const minX = window.innerWidth * 0.48;
      const minY = 120;
      const timeRegex = /([0-9]{1,2}:[0-9]{2}[ ]*(م|ص)?|[0-9]+[ ]*(م|ص|د|س|h|m)|أمس|yesterday|اليوم|منذ|الآن|جمعة|سبت|أحد|اثنين|ثلاثاء|أربعاء|خميس|يناير|فبراير|مارس|أبريل|مايو|يونيو|يوليو|أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر)/i;

      const candidates = new Set();

      // 1. Text node scan with parent walk
      const textNodes = Array.from(document.querySelectorAll('span, div')).filter(el => {
        if (el.closest('#mbs-inbox-automator-root') || el.children.length > 0) return false;
        const rect = el.getBoundingClientRect();
        return rect.right >= minX && rect.top >= minY && timeRegex.test((el.innerText || '').trim());
      });

      for (const node of textNodes) {
        let curr = node.parentElement;
        while (curr && curr !== document.body) {
          const r = curr.getBoundingClientRect();
          if (r.height >= 45 && r.height <= 140 && r.width >= 240 && r.right >= minX) {
            candidates.add(curr);
            break;
          }
          curr = curr.parentElement;
        }
      }

      // 2. Direct selector fallback
      const selectors = [
        'a[href*="/inbox/"]',
        'a[href*="/latest/inbox/"]',
        'div[role="row"]',
        'div[role="listitem"]',
        'div[role="presentation"]',
        'div[tabindex="0"]'
      ];
      const elements = Array.from(document.querySelectorAll(selectors.join(',')));

      for (const el of elements) {
        if (el.closest('#mbs-inbox-automator-root')) continue;
        if (this.isAdOrMetadataElement(el)) continue;

        const rect = el.getBoundingClientRect();
        if (rect.right >= minX && rect.top >= minY && rect.height >= 45 && rect.height <= 140 && rect.width >= 240) {
          const txt = (el.innerText || '').trim();
          if (txt.length >= 2 && !txt.startsWith('غير مقروء') && !txt.startsWith('بحث') && !txt.startsWith('الأولوية') && !txt.includes('كل الرسائل')) {
            candidates.add(el);
          }
        }
      }

      const list = Array.from(candidates);
      const unique = list.filter(item => !list.some(other => other !== item && other.contains(item)));
      unique.sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
      return unique;
    },

    isTimestampOrBadge(text) {
      if (!text) return true;
      const t = text.trim();
      if (t.length < 2) return true;
      // Single numbers or counter badges like "1", "2", "99+"
      if (/^\d+\+?$/.test(t)) return true;
      // Exact time formats: e.g. "10:25", "10:25 ص", "10:25 م", "8:43 am", "8:43 pm"
      if (/^\d{1,2}:\d{2}(?:\s*(?:ص|م|am|pm|AM|PM))?$/i.test(t)) return true;
      // Arabic prefixed time: e.g. "ص 10:25", "م 8:43"
      if (/^(?:ص|م)\s*\d{1,2}:\d{2}$/i.test(t)) return true;
      // Relative time indicators (Arabic & English)
      if (/^(?:منذ\s+[\d\u0660-\u0669]+|أمس|اليوم|الآن|yesterday|today|now|[\d\u0660-\u0669]+\s*(?:د|س|ي|أ|ش|ث|m|h|d|w|mo|y|min|mins|hr|hrs|days?))$/i.test(t)) return true;
      // Common status pills, labels & Meta system words
      if (/^(?:غير مقروء|مقروء|نشط الآن|تم الرد|مغلق|طلب جديد|مكتمل|unread|read|active now|closed|new)$/i.test(t)) return true;
      if (['Messenger', 'Instagram', 'WhatsApp', 'Facebook', 'Meta Business Suite'].includes(t)) return true;
      return false;
    },

    isSnippetOrPreview(text) {
      if (!text) return false;
      const t = text.trim();
      // Prefix indicators for automated / agent previews
      if (t.startsWith('أنت:') || t.startsWith('أنت :') || t.startsWith('You:') || t.startsWith('You :') ||
          t.startsWith('تم إرسال:') || t.startsWith('تم إرسال') || t.startsWith('Sent:') || 
          t.startsWith('رد تلقائي:') || t.startsWith('رد آلي:') || t.startsWith('Automated response:')) {
        return true;
      }
      // Multiline text or long strings (>35 chars) in conversation rows are message previews, not names
      if (t.includes('\n') || t.length > 35) return true;
      return false;
    },

    getRowCustomerName(row) {
      if (!row) return '';

      const matchesMessageBubble = (txt) => {
        if (!txt) return false;
        const clean = txt.trim().toLowerCase();
        if (clean.length < 2) return false;
        try {
          const chatCanvas = this.getChatCanvas();
          if (chatCanvas) {
            const bubbles = Array.from(chatCanvas.querySelectorAll('div[dir="auto"], span[dir="auto"]'));
            for (const b of bubbles) {
              const bTxt = (b.innerText || '').trim().toLowerCase();
              if (bTxt && (bTxt === clean || (clean.length > 8 && bTxt.includes(clean)))) {
                return true;
              }
            }
          }
        } catch (_) {}
        return false;
      };

      const isValidName = (txt) => {
        if (!txt) return false;
        const clean = txt.trim();
        if (clean.length < 2 || clean.length > 35) return false;
        if (this.isTimestampOrBadge(clean)) return false;
        if (this.isSnippetOrPreview(clean)) return false;
        if (matchesMessageBubble(clean)) return false;
        return true;
      };

      // 1. Aria-label inspection (cleaning conversation/unread prefixes)
      const aria = row.getAttribute('aria-label');
      if (aria) {
        let cleanedAria = aria
          .replace(/^محادثة\s+(?:مع\s+)?/i, '')
          .replace(/^Conversation\s+with\s+/i, '')
          .replace(/^(?:غير مقروءة?|Unread)\s*[,،-]?\s*/i, '');
        const firstSegment = cleanedAria.split(/[,،\n•·|]/)[0].trim();
        if (isValidName(firstSegment)) {
          return this.sanitizeName(firstSegment);
        }
      }

      // 2. Primary header / title element inside the conversation row
      const headingEl = row.querySelector('[role="heading"], h2, h3, h4, [data-testid*="name"], [data-testid*="contact"]');
      if (headingEl) {
        const txt = (headingEl.innerText || headingEl.textContent || '').trim();
        const candidate = txt.split(/[,،\n•·|]/)[0].trim();
        if (isValidName(candidate)) return this.sanitizeName(candidate);
      }

      // 3. Inspect leaf text blocks: span[dir="auto"], div[dir="auto"], strong, span
      const candidates = Array.from(row.querySelectorAll('span[dir="auto"], div[dir="auto"], span, strong')).filter(el => {
        if (el.closest('#mbs-inbox-automator-root')) return false;
        // Prefer leaf nodes to avoid aggregating multiple lines
        if (el.children.length > 0 && Array.from(el.children).some(c => (c.innerText || '').trim().length > 0)) {
          return false;
        }
        const txt = (el.innerText || el.textContent || '').trim();
        return isValidName(txt);
      });

      // 3.a Prefer bold / semi-bold leaf candidate (MBS contact name weight >= 500)
      for (const el of candidates) {
        try {
          const weight = parseInt(window.getComputedStyle(el).fontWeight, 10) || 400;
          const txt = (el.innerText || el.textContent || '').trim();
          if (weight >= 500 && isValidName(txt)) {
            return this.sanitizeName(txt);
          }
        } catch (_) {}
      }

      // 3.b First valid leaf candidate
      if (candidates.length > 0) {
        const txt = (candidates[0].innerText || candidates[0].textContent || '').trim();
        if (isValidName(txt)) return this.sanitizeName(txt);
      }

      // 4. Fallback: Parse row lines, picking the first line matching valid name criteria
      const lines = (row.innerText || '').split('\n').map(l => l.trim()).filter(Boolean);
      for (const line of lines) {
        if (isValidName(line)) {
          return this.sanitizeName(line);
        }
      }

      return (lines[0] && isValidName(lines[0])) ? this.sanitizeName(lines[0]) : '';
    },

    getStableRowKey(row) {
      if (!row) return null;
      const href = row.getAttribute('href') || row.querySelector('a[href]')?.getAttribute('href') || '';
      if (href) {
        const matchSelected = href.match(/selected_item_id=([0-9a-zA-Z_-]+)/);
        if (matchSelected) return `id_${matchSelected[1]}`;
        const matchAsset = href.match(/asset_id=([0-9a-zA-Z_-]+)/);
        if (matchAsset) return `asset_${matchAsset[1]}`;
        const matchPath = href.match(/\/inbox\/(?:all\/)?([0-9]+)/);
        if (matchPath) return `id_${matchPath[1]}`;
      }

      const name = this.getRowCustomerName(row);
      if (name) return `contact_${normalizeArabicText(name)}`;
      return null;
    },

    getRowSnippet(row) {
      if (!row) return '';
      const name = this.getRowCustomerName(row);
      const lines = (row.innerText || '')
        .split('\n')
        .map(l => l.trim())
        .filter(l => l && l !== name && !this.isTimestampOrBadge(l));
      return lines.join(' | ');
    },

    isRowVisuallyUnread(row) {
      if (!row) return false;
      try {
        const aria = (row.getAttribute('aria-label') || '').toLowerCase();
        if (aria.includes('غير مقروء') || aria.includes('unread')) return true;

        const childUnread = row.querySelector('[aria-label*="غير مقروء" i], [aria-label*="unread" i], [title*="غير مقروء" i], [title*="unread" i]');
        if (childUnread) return true;

        const className = (typeof row.className === 'string') ? row.className.toLowerCase() : '';
        if (className.includes('unread')) return true;

        const dots = Array.from(row.querySelectorAll('span, div')).filter(el => {
          if (el.closest('#mbs-inbox-automator-root')) return false;
          if (el.children.length > 0) return false;
          const rect = el.getBoundingClientRect();
          if (rect.width >= 5 && rect.width <= 20 && rect.height >= 5 && rect.height <= 20) {
            const style = window.getComputedStyle(el);
            const br = style.borderRadius;
            const bg = style.backgroundColor;
            if ((br.includes('50%') || parseInt(br, 10) >= 4) && bg !== 'transparent' && bg !== 'rgba(0, 0, 0, 0)') {
              return true;
            }
          }
          return false;
        });
        if (dots.length > 0) return true;

        const bolds = Array.from(row.querySelectorAll('span[dir="auto"], span, div, strong')).filter(el => {
          if (el.closest('#mbs-inbox-automator-root')) return false;
          try {
            const w = parseInt(window.getComputedStyle(el).fontWeight, 10) || 400;
            return w >= 600;
          } catch (_) { return false; }
        });
        if (bolds.length > 0) return true;
      } catch (_) {}
      return false;
    },

    getRowClickTarget(row) {
      if (!row) return null;
      // Search for customer name or message text safely away from hover action buttons (like "نقل إلى المجلد تم")
      const textEl = Array.from(row.querySelectorAll('span, div')).find(el => {
        if (el.closest('[aria-label*="تم"], [aria-label*="done"], [aria-label*="متابعة"], [role="gridcell"]')) return false;
        return el.children.length === 0 && (el.innerText || '').trim().length >= 2;
      });
      return textEl || row;
    },

    getActiveChatContactName() {
      const isValid = (t) => t && t.length >= 2 && !['البريد الوارد', 'تفاصيل الاتصال', 'التسميات', 'الملاحظات', 'Inbox', 'Contact Details', 'Labels', 'Notes'].includes(t) && !this.isTimestampOrBadge(t) && !this.isSnippetOrPreview(t);

      // 1. Primary heading in contact details panel (top 70-160, left < 400)
      const headings = Array.from(document.querySelectorAll('[role="heading"], h1, h2, h3')).filter(el => {
        if (el.closest('#mbs-inbox-automator-root')) return false;
        const r = el.getBoundingClientRect();
        const t = (el.innerText || '').trim();
        return r.top >= 70 && r.top <= 160 && r.left < 400 && r.width > 0 && isValid(t);
      });
      if (headings.length > 0) {
        return this.sanitizeName(headings[0].innerText.trim());
      }

      // 2. Chat header / banner heading fallback
      const chatCanvas = this.getChatCanvas();
      if (chatCanvas) {
        const header = chatCanvas.querySelector('header, div[role="banner"]') || chatCanvas.parentElement?.querySelector('header');
        if (header) {
          const heading = header.querySelector('h1, h2, div[role="heading"], span[style*="font-weight"]');
          if (heading) {
            const txt = (heading.innerText || heading.textContent || '').trim();
            if (isValid(txt)) return this.sanitizeName(txt);
          }
        }
      }
      const topName = document.querySelector('div[role="main"] div[style*="font-weight"], main div[style*="font-weight"]');
      if (topName) {
        const txt = (topName.innerText || topName.textContent || '').trim();
        if (isValid(txt)) return this.sanitizeName(txt);
      }
      return '';
    },

    async waitForConversationLoad(targetRow, contactName, clickTarget, logger) {
      const cleanTarget = this.sanitizeName(contactName);
      const isGenericName = !cleanTarget || 
                            cleanTarget.startsWith('*row_') || 
                            cleanTarget.startsWith('row_') || 
                            cleanTarget.startsWith('contact_row_');
      const normTarget = isGenericName ? '' : normalizeArabicText(cleanTarget);
      const targetDigits = cleanTarget.replace(/\D/g, '');
      const startWait = Date.now();
      const maxTimeoutMs = 3500; // Hard timeout of 3.5 seconds max

      while (Date.now() - startWait < maxTimeoutMs) {
        if (state.emergencyAbort) throw new Error('ABORT_SIGNAL');

        const composer = this.getComposer();
        const chatCanvas = this.getChatCanvas();
        const isRowSelected = Boolean(targetRow && (
          targetRow.getAttribute('aria-selected') === 'true' ||
          (typeof targetRow.className === 'string' && (targetRow.className.includes('selected') || targetRow.className.includes('active'))) ||
          targetRow.querySelector('[aria-selected="true"]')
        ));

        // If expectedName is generic or missing, verify row selection or canvas/composer presence
        if (isGenericName) {
          if (isRowSelected || (composer && chatCanvas)) {
            return true;
          }
        } else {
          // Named contact check
          const headerName = this.getActiveChatContactName();
          const cleanHeader = this.sanitizeName(headerName);
          const normHeader = normalizeArabicText(cleanHeader);
          const headerDigits = cleanHeader.replace(/\D/g, '');

          // Numeric phone match (e.g. +44 7974 905044 vs 447974905044)
          const isNumericMatch = targetDigits.length >= 6 && headerDigits.length >= 6 &&
                                 (headerDigits.includes(targetDigits) || targetDigits.includes(headerDigits));

          if (composer && ((normHeader && normTarget && (normHeader.includes(normTarget) || normTarget.includes(normHeader))) || isNumericMatch)) {
            return true;
          }

          // If past 1.8s and row is selected or composer is present, accept if canvas rendered
          if (Date.now() - startWait > 1800 && (isRowSelected || composer) && chatCanvas) {
            return true;
          }
        }

        // Single gentle retry click after 1.2s if switch hasn't completed
        if (Date.now() - startWait > 1200 && Date.now() - startWait < 1400) {
          try {
            await HumanSimulator.naturalClick(clickTarget || targetRow);
          } catch (_) {}
        }

        await sleep(150);
      }

      // Hard timeout reached (3.5s): if composer or canvas is present, proceed rather than hang
      const finalComposer = this.getComposer();
      const finalCanvas = this.getChatCanvas();
      if (finalComposer || finalCanvas) {
        return true;
      }

      if (logger) logger.log('WARN', `مهلة انتظار تحميل المحادثة (${(maxTimeoutMs / 1000).toFixed(1)} ث) انتهت دون استجابة تامة. المتابعة بحذر...`);
      return false;
    },

    getSidebarScrollContainer() {
      const rows = this.getConversationRows();
      if (rows.length > 0) {
        let parent = rows[0].parentElement;
        while (parent && parent !== document.body) {
          const style = window.getComputedStyle(parent);
          if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && parent.clientHeight > 200) {
            return parent;
          }
          parent = parent.parentElement;
        }
      }

      const rightScrollables = Array.from(document.querySelectorAll('div')).filter(d => {
        if (d.closest('#mbs-inbox-automator-root')) return false;
        const r = d.getBoundingClientRect();
        const s = window.getComputedStyle(d);
        return (s.overflowY === 'auto' || s.overflowY === 'scroll') && r.right >= window.innerWidth * 0.48 && r.height > 250 && r.width >= 140;
      });
      return rightScrollables[0] || null;
    },

    isUnreadFilterActive() {
      const unreadBtn = Array.from(document.querySelectorAll('div[role="button"], button')).find(b => {
        if (b.closest('#mbs-inbox-automator-root')) return false;
        const r = b.getBoundingClientRect();
        const txt = (b.innerText || '').trim();
        return (txt === 'غير مقروء' || b.getAttribute('aria-label') === 'غير مقروء') &&
               r.top > 150 && r.top < 240 && r.right >= window.innerWidth * 0.48;
      });

      if (!unreadBtn) return false;

      const inner = unreadBtn.querySelector('div') || unreadBtn;
      const ics = window.getComputedStyle(inner);
      const cs = window.getComputedStyle(unreadBtn);

      const isBlueBg = (ics.backgroundColor.includes('225') && ics.backgroundColor.includes('237')) ||
                       (cs.backgroundColor.includes('225') && cs.backgroundColor.includes('237'));
      const isBlueColor = (ics.color.includes('10') && ics.color.includes('120')) ||
                          (cs.color.includes('10') && cs.color.includes('120')) ||
                          ics.color.includes('124') || cs.color.includes('124');

      return isBlueBg || isBlueColor;
    },

    async ensureUnreadFilterActive(logger) {
      if (this.isUnreadFilterActive()) return true;

      const unreadBtn = Array.from(document.querySelectorAll('div[role="button"], button')).find(b => {
        if (b.closest('#mbs-inbox-automator-root')) return false;
        const r = b.getBoundingClientRect();
        const txt = (b.innerText || '').trim();
        return (txt === 'غير مقروء' || b.getAttribute('aria-label') === 'غير مقروء') &&
               r.top > 150 && r.top < 240 && r.right >= window.innerWidth * 0.48;
      });

      if (unreadBtn) {
        if (logger) logger.log('INFO', 'تفعيل فلتر "غير مقروء" تلقائياً وتثبيته...');
        unreadBtn.focus();
        unreadBtn.click();
        await sleep(900);
        return true;
      }
      return false;
    },

    getChatCanvas() {
      const selectors = [
        'div[role="main"]',
        'div[data-testid*="message-list"]',
        'div[data-testid*="chat-canvas"]',
        'div[aria-label*="محادثة" i]',
        'div[aria-label*="Conversation" i]',
        'div[aria-label*="حاوية قائمة الرسائل" i]'
      ];

      for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el && el.offsetParent !== null && !el.closest('#mbs-inbox-automator-root')) return el;
      }

      const scrollables = Array.from(document.querySelectorAll('div')).filter(el => {
        if (el.closest('#mbs-inbox-automator-root')) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return (style.overflowY === 'auto' || style.overflowY === 'scroll') &&
               rect.width > 280 && rect.height > 250 &&
               rect.left > 120 && rect.right < (window.innerWidth - 120);
      });

      return scrollables[0] || document.querySelector('main') || null;
    },

    getMessageScrollContainer() {
      const composer = this.getComposer();
      const chat = this.getChatCanvas();
      if (!chat) return null;

      const chatStyle = window.getComputedStyle(chat);
      if ((chatStyle.overflowY === 'auto' || chatStyle.overflowY === 'scroll') && (!composer || !chat.contains(composer))) {
        return chat;
      }

      const scrollables = Array.from(chat.querySelectorAll('div')).filter(el => {
        if (el.closest('#mbs-inbox-automator-root')) return false;
        if (composer && (composer.contains(el) || el.contains(composer))) return false;
        const s = window.getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return (s.overflowY === 'auto' || s.overflowY === 'scroll') && r.height > 180 && r.width > 250;
      });

      return scrollables[0] || chat;
    },

    getComposer() {
      const selectors = [
        'div[role="textbox"][contenteditable="true"]',
        'div[contenteditable="true"][data-lexical-editor="true"]',
        'div[contenteditable="true"][aria-label*="رسالة" i]',
        'div[contenteditable="true"][aria-label*="message" i]',
        'div[role="textbox"]',
        'div[contenteditable="true"]',
        'textarea'
      ];

      for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el && el.offsetParent !== null && !el.closest('#mbs-inbox-automator-root')) {
          const rect = el.getBoundingClientRect();
          if (rect.bottom >= window.innerHeight - 250 && rect.width > 180) {
            return el;
          }
        }
      }
      return null;
    },

    getSendButton() {
      const selectors = [
        'div[aria-label*="إرسال" i][role="button"]',
        'div[aria-label*="Send" i][role="button"]',
        'button[aria-label*="إرسال" i]',
        'button[aria-label*="Send" i]',
        'button[type="submit"]'
      ];

      for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el && el.offsetParent !== null && !el.closest('#mbs-inbox-automator-root')) {
          const rect = el.getBoundingClientRect();
          if (rect.bottom >= window.innerHeight - 250) return el;
        }
      }
      return null;
    },

    async executeRestoreToUnread(logger, targetRow, contactKey) {
      // Container-Relative & Dynamic Coordinate Scope:
      // Dynamically scope toolbar horizontally using composer bounds (with safe fallback)
      const composer = this.getComposer();
      const compRect = composer ? composer.getBoundingClientRect() : null;
      const minLeft = compRect ? Math.max(0, compRect.left - 80) : 0;
      const maxRight = compRect ? Math.min(window.innerWidth, compRect.right + 80) : (window.innerWidth * 0.55);

      const getHeaderButtons = () => {
        return Array.from(document.querySelectorAll('button, div[role="button"]')).filter(b => {
          if (b.closest('#mbs-inbox-automator-root')) return false;
          const r = b.getBoundingClientRect();
          return r.top < 280 && r.left >= minLeft && r.right <= maxRight && r.width > 0 && r.height > 0;
        });
      };

      const findDirectButton = () => {
        // TIER 1: Direct Button with Unread Label Attributes in Chat Header
        const unreadSelectors = [
          'button[aria-label*="غير مقروء" i]',
          'button[aria-label*="unread" i]',
          'div[role="button"][aria-label*="غير مقروء" i]',
          'div[role="button"][aria-label*="unread" i]',
          'button[title*="غير مقروء" i]',
          'div[role="button"][title*="غير مقروء" i]',
          'button[aria-label*="علامة كغير" i]',
          'div[role="button"][aria-label*="علامة كغير" i]'
        ];

        for (const sel of unreadSelectors) {
          const btns = Array.from(document.querySelectorAll(sel)).filter(b => {
            if (b.closest('#mbs-inbox-automator-root')) return false;
            const r = b.getBoundingClientRect();
            return r.top < 280 && r.left >= minLeft && r.right <= maxRight && r.width > 0 && r.height > 0;
          });
          if (btns.length > 0) return btns[0];
        }

        // TIER 2: Sibling Check Relative to "Done" Button (CRITICAL: Only click the unread sibling, NEVER Done!)
        const allHeaderButtons = getHeaderButtons();
        const doneBtn = allHeaderButtons.find(b => {
          const txt = (b.innerText || '').trim();
          const aria = (b.getAttribute('aria-label') || '').trim();
          const title = (b.getAttribute('title') || '').trim();
          return /^(تم|نقل إلى تم|Done|Mark as done)$/i.test(txt) ||
                 /^(تم|نقل إلى تم|Done|Mark as done)$/i.test(aria) ||
                 /^(تم|نقل إلى تم|Done|Mark as done)$/i.test(title);
        });

        if (doneBtn && doneBtn.parentElement) {
          const siblings = Array.from(doneBtn.parentElement.children).filter(el => el !== doneBtn);
          for (const sib of siblings) {
            const targetBtn = (sib.matches && sib.matches('button, div[role="button"]')) ? sib : sib.querySelector('button, div[role="button"]');
            if (!targetBtn) continue;
            const sAria = (targetBtn.getAttribute('aria-label') || '').toLowerCase();
            const sTitle = (targetBtn.getAttribute('title') || '').toLowerCase();
            const sTxt = (targetBtn.innerText || '').toLowerCase();
            if (sAria.includes('done') || sAria.includes('تم') || sTitle.includes('تم') || sTxt.includes('تم')) continue;

            if (sAria.includes('غير مقروء') || sAria.includes('unread') ||
                sTitle.includes('غير مقروء') || sTitle.includes('unread') ||
                targetBtn.querySelector('svg')) {
              return targetBtn;
            }
          }
        }

        // TIER 3: Envelope SVG Path Discovery (Inspect paths in header buttons)
        for (const btn of allHeaderButtons) {
          const svg = btn.querySelector('svg');
          if (!svg) continue;
          const aria = (btn.getAttribute('aria-label') || svg.getAttribute('aria-label') || '').toLowerCase();
          const title = (btn.getAttribute('title') || '').toLowerCase();
          if (aria.includes('done') || aria.includes('تم') || title.includes('تم')) continue;

          const path = btn.querySelector('path');
          const d = path ? (path.getAttribute('d') || '') : '';
          if (aria.includes('unread') || aria.includes('غير مقروء') ||
              title.includes('unread') || title.includes('غير مقروء') ||
              (d.length > 25 && (d.includes('M') || d.includes('m')) && (aria.includes('mail') || aria.includes('envelope') || svg.innerHTML.includes('envelope')))) {
            return btn;
          }
        }
        return null;
      };

      let isAlreadyUnreadDetected = false;
      let isUnreadOptionUnavailable = false;

      const tryClickDropdown = async () => {
        if (logger) logger.log('SCAN', 'فحص القائمة المنسدلة العلوية للتمييز كغير مقروءة...');
        const allHeaderButtons = getHeaderButtons();
        const dropdownBtn = allHeaderButtons.find(b => {
          const t = (b.innerText || '').trim();
          const aria = (b.getAttribute('aria-label') || '').trim();
          const title = (b.getAttribute('title') || '').trim();
          return t.includes('فتح القائمة المنسدلة') || aria.includes('المزيد') || aria.includes('More') ||
                 title.includes('المزيد') || title.includes('More') || aria.includes('القائمة المنسدلة');
        });

        if (!dropdownBtn) return false;

        let result = false;
        try {
          await HumanSimulator.flashEnvelopeButton(dropdownBtn);
          releaseChatFocus();
          dispatchFullClick(dropdownBtn);
          await sleep(500);

          // Strictly target [role="menuitem"] inside [role="menu"] or floating popovers
          const menuItems = Array.from(document.querySelectorAll('[role="menu"] [role="menuitem"], [role="menuitem"], div[role="menu"] div[role="button"]')).filter(el => !el.closest('#mbs-inbox-automator-root'));

          // 1. Detect "Already Unread" State:
          // If menu contains "تمييز كمقروءة" (Mark as READ) and does NOT contain "غير مقروء" (Mark as UNREAD)
          const hasMarkAsRead = menuItems.some(el => {
            const allTxt = `${el.innerText || ''} ${el.getAttribute('aria-label') || ''}`.toLowerCase();
            return (allTxt.includes('كمقروءة') || allTxt.includes('كمقروء') || allTxt.includes('mark as read')) &&
                   !allTxt.includes('غير') && !allTxt.includes('unread');
          });

          const unreadMenuItem = menuItems.find(el => {
            const txt = (el.innerText || '').trim();
            const aria = (el.getAttribute('aria-label') || '').trim();
            const allTxt = `${txt} ${aria}`.toLowerCase();
            const r = el.getBoundingClientRect();
            return (allTxt.includes('غير مقروء') || allTxt.includes('unread')) &&
                   !allTxt.includes('نقل') && !allTxt.includes('المجلد') && !allTxt.includes('حذف') &&
                   r.height > 15 && r.height < 70 && r.width > 0;
          });

          if (hasMarkAsRead && !unreadMenuItem) {
            isAlreadyUnreadDetected = true;
            if (logger) logger.log('UNREAD', '[UNREAD] المحادثة غير مقروءة بالفعل في نظام Meta. تجاوز بأمان.');
            result = true;
            return true;
          }

          if (unreadMenuItem) {
            dispatchFullClick(unreadMenuItem);
            releaseChatFocus();
            await sleep(350);
            result = true;
            return true;
          } else if (menuItems.length > 0) {
            // 2. Safe Graceful Fallback (e.g. WhatsApp channel without unread action)
            isUnreadOptionUnavailable = true;
            if (logger) logger.log('UNREAD', '[UNREAD] تعذر العثور على خيار غير مقروء في هذه القناة (واتساب). إنهاء التعديل بأمان.');
            result = true;
            return true;
          }
        } finally {
          // Guaranteed Menu Dismissal: Always dispatch Escape so no popup or backdrop remains blocking the viewport
          try {
            window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }));
            releaseChatFocus();
          } catch (_) {}
        }
        return result;
      };

      const checkVerifiedUnread = () => {
        if (!targetRow) return true;
        let row = targetRow;
        if (!document.body.contains(row) && contactKey) {
          const rows = this.getConversationRows();
          row = rows.find(r => this.getStableRowKey(r) === contactKey) || targetRow;
        }
        return this.isRowVisuallyUnread(row);
      };

      const pollVerification = async (timeoutMs = 1500) => {
        if (!targetRow) return true;
        const start = Date.now();
        while (Date.now() - start < timeoutMs) {
          if (checkVerifiedUnread()) return true;
          await sleep(150);
        }
        return checkVerifiedUnread();
      };

      // ATTEMPT 1: Focus release -> Click Direct or Dropdown -> Focus release -> Verification poll
      releaseChatFocus();
      let clicked = false;
      let usedDropdown = false;
      const directBtn = findDirectButton();

      if (directBtn) {
        await HumanSimulator.flashEnvelopeButton(directBtn);
        releaseChatFocus();
        dispatchFullClick(directBtn);
        releaseChatFocus();
        clicked = true;
      } else {
        usedDropdown = true;
        clicked = await tryClickDropdown();
      }

      if (isAlreadyUnreadDetected || isUnreadOptionUnavailable) {
        return true;
      }

      if (clicked) {
        const verified = await pollVerification(1500);
        if (verified) return true;
      }

      // ATTEMPT 2 (RETRY with alternate selector / dropdown):
      if (logger) logger.log('WARN', 'لم يتم تأكيد حالة غير مقروء في المحاولة الأولى، جاري إعادة المحاولة...');
      releaseChatFocus();
      await sleep(250);

      if (!usedDropdown) {
        clicked = await tryClickDropdown();
      } else {
        const retryBtn = findDirectButton();
        if (retryBtn) {
          await HumanSimulator.flashEnvelopeButton(retryBtn);
          releaseChatFocus();
          dispatchFullClick(retryBtn);
          releaseChatFocus();
          clicked = true;
        } else {
          clicked = await tryClickDropdown();
        }
      }

      if (isAlreadyUnreadDetected || isUnreadOptionUnavailable) {
        return true;
      }

      if (clicked) {
        const verified = await pollVerification(1500);
        return verified;
      }

      return false;
    },

    isAdOrMetadataElement(el, txt) {
      if (!el) return false;
      const isAdContainer = Boolean(el.closest && (
        el.closest('a[href*="/ads/"], [data-ad-id]') ||
        el.closest('[aria-label*="إعلان ممول" i], [aria-label*="Sponsored" i]')
      ));
      if (isAdContainer) return true;

      const text = (txt || el.innerText || '').trim();
      if (!text) return false;

      // Anti-False-Drop Ad Guard:
      // Only drop text matching ad regex IF inside an ad container OR text is short (< 45 chars).
      // Longer customer inquiries referencing an ad (e.g. "شفت إعلان ممول وعايز أعرف السعر") are preserved.
      if (/(?:تم الإرسال من إعلان|الرد على الإعلان|إعلان ممول|محتوى ممول|Sponsored Ad|Sent from ad)/i.test(text)) {
        if (isAdContainer || text.length < 45) {
          return true;
        }
      }

      if (/^\+?201\d{9}\s+حاليا[ً]?\s+متوفر/i.test(text)) {
        return true;
      }
      return false;
    },

    getMessageBubbles() {
      const composer = this.getComposer();
      const compRect = composer ? composer.getBoundingClientRect() : null;

      const minX = compRect ? (compRect.left - 30) : (window.innerWidth * 0.20);
      const maxX = compRect ? (compRect.right + 30) : (window.innerWidth * 0.65);
      const minY = 90;
      const maxY = compRect ? (compRect.top - 6) : (window.innerHeight - 80);

      const viewport = this.getMessageScrollContainer() || this.getChatCanvas() || document.body;

      const candidateElements = Array.from(viewport.querySelectorAll('div, span, p')).filter(el => {
        if (el.closest('#mbs-inbox-automator-root')) return false;
        if (composer && (composer.contains(el) || el.contains(composer))) return false;
        if (el.closest('button, header, footer, nav, [role="toolbar"]')) return false;

        const rect = el.getBoundingClientRect();
        if (rect.left < minX || rect.right > maxX || rect.top < minY || rect.bottom > maxY) return false;
        if (rect.width < 14 || rect.height < 14 || rect.height > 600) return false;

        const text = (el.innerText || '').trim();
        if (!text) return false;
        if (/^[0-9]{1,2}:[0-9]{2}[ ]*(م|ص)?$/.test(text)) return false;

        if (this.isAdOrMetadataElement(el, text)) return false;

        const style = window.getComputedStyle(el);
        const hasBg = style.backgroundColor && style.backgroundColor !== 'rgba(0, 0, 0, 0)' && style.backgroundColor !== 'transparent';
        const hasRadius = parseInt(style.borderRadius, 10) >= 6;
        return hasBg && hasRadius;
      });

      const leaves = candidateElements.filter(item => {
        return !candidateElements.some(other => other !== item && other.contains(item));
      });

      leaves.sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
      return leaves;
    },

    isOutboundBubble(bubble) {
      if (!bubble) return false;
      const text = (bubble.innerText || '').trim();

      // 1. Text match: ONLY if the bubble text contains a substantial chunk of our configured reply (25+ characters)
      // CRITICAL FIX: NEVER check if r.reply includes text (short customer messages like "تفاصيل" or "سعر" must NEVER be marked outbound!)
      if (text.length >= 25 && state.rules.some(r => r.reply && text.includes(r.reply.slice(0, 25)))) {
        return true;
      }

      // 2. Immediate parent status (Meta Business Suite status labels on outbound messages)
      const parent = bubble.closest('div[data-testid*="message"]') || bubble.parentElement;
      if (parent) {
        const pText = parent.innerText || '';
        if (pText.includes('تم التسليم') || pText.includes('Delivered') || pText.includes('You:')) return true;
      }

      // 3. Color & Background checks (Messenger Blue & WhatsApp Light Green)
      let curr = bubble;
      let depth = 0;
      while (curr && curr !== document.body && depth < 8) {
        const style = window.getComputedStyle(curr);
        const bg = style.backgroundColor || '';
        // Messenger Blue
        if (
          /rgb\(\s*(0|8|10|24|45)\s*,\s*(100|102|119|122|132|136)\s*,\s*(224|242|255)/i.test(bg) ||
          bg.includes('0, 132, 255') || bg.includes('24, 119, 242') || bg.includes('8, 102, 255')
        ) {
          return true;
        }
        // WhatsApp Light Green
        if (
          /rgb\(\s*(210|215|217|220|225)\s*,\s*(240|245|248|253|255)\s*,\s*(190|198|199|205|211)\)/i.test(bg) ||
          bg.includes('225, 255, 199') || bg.includes('220, 248, 198') || bg.includes('217, 253, 211')
        ) {
          return true;
        }
        // White text on colored background (Messenger outbound)
        const color = style.color || '';
        if ((color === 'rgb(255, 255, 255)' || color === '#ffffff' || color === 'white') && bg && !bg.includes('rgba(0, 0, 0, 0)')) {
          return true;
        }
        curr = curr.parentElement;
        depth++;
      }

      // 4. Horizontal alignment in chat column:
      // In RTL Arabic layout:
      // Outbound (page) messages are left-aligned (rect.right < center)
      // Inbound (customer) messages are right-aligned (rect.left > center or rect.right >= center)
      const composer = this.getComposer();
      const compRect = composer ? composer.getBoundingClientRect() : null;
      if (compRect) {
        const center = (compRect.left + compRect.right) / 2;
        const rect = bubble.getBoundingClientRect();
        if (rect.right < center) {
          return true;
        }
      }

      return false;
    },

    parseInboundBoundary() {
      const bubbles = this.getMessageBubbles();
      if (bubbles.length === 0) {
        return { lastIsOutbound: false, customerBubbles: [] };
      }

      const lastBubble = bubbles[bubbles.length - 1];
      if (this.isOutboundBubble(lastBubble)) {
        return { lastIsOutbound: true, customerBubbles: [] };
      }

      const customerBubbles = [];
      for (let i = bubbles.length - 1; i >= 0; i--) {
        const b = bubbles[i];
        if (this.isOutboundBubble(b)) {
          break;
        }
        customerBubbles.unshift(b);
      }

      return { lastIsOutbound: false, customerBubbles };
    }
  };

  // ---------------------------------------------------------------------------
  // 4. HUMAN SIMULATOR
  // ---------------------------------------------------------------------------
  const HumanSimulator = {
    async naturalClick(element) {
      if (!element) return false;
      element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      await sleep(randomRange(50, 90));

      const rect = element.getBoundingClientRect();
      const clientX = rect.left + Math.min(rect.width * 0.25, 45) + randomRange(-2, 2);
      const clientY = rect.top + rect.height / 2 + randomRange(-2, 2);

      const events = [
        new PointerEvent('pointerdown', { bubbles: true, cancelable: true, clientX, clientY, pointerType: 'mouse' }),
        new MouseEvent('mousedown', { bubbles: true, cancelable: true, clientX, clientY, buttons: 1 }),
        new PointerEvent('pointerup', { bubbles: true, cancelable: true, clientX, clientY, pointerType: 'mouse' }),
        new MouseEvent('mouseup', { bubbles: true, cancelable: true, clientX, clientY }),
        new MouseEvent('click', { bubbles: true, cancelable: true, clientX, clientY })
      ];

      for (const ev of events) {
        element.dispatchEvent(ev);
      }

      try {
        if (typeof element.click === 'function') element.click();
      } catch (_) {}

      return true;
    },

    async highlightCustomerBubble(bubble) {
      if (!bubble) return;
      try {
        const origBorderRadius = bubble.style.borderRadius;
        const origShadow = bubble.style.boxShadow;
        const origTransition = bubble.style.transition;

        bubble.style.setProperty('border-radius', '16px', 'important');
        bubble.style.setProperty('box-shadow', '0 0 0 1.5px rgba(56, 189, 248, 0.45), 0 6px 20px rgba(14, 165, 233, 0.14)', 'important');
        bubble.style.setProperty('transition', 'all 0.25s cubic-bezier(0.16, 1, 0.3, 1)', 'important');

        await sleep(600);

        if (origBorderRadius) bubble.style.borderRadius = origBorderRadius;
        else bubble.style.removeProperty('border-radius');

        if (origShadow) bubble.style.boxShadow = origShadow;
        else bubble.style.removeProperty('box-shadow');

        if (origTransition) bubble.style.transition = origTransition;
        else bubble.style.removeProperty('transition');
      } catch (_) {}
    },

    async flashEnvelopeButton(btn) {
      if (!btn) return;
      try {
        const origOutline = btn.style.outline;
        const origShadow = btn.style.boxShadow;
        btn.style.outline = '2px solid #22c55e';
        btn.style.boxShadow = '0 0 12px rgba(34, 197, 94, 0.7)';
        await sleep(400);
        btn.style.outline = origOutline || '';
        btn.style.boxShadow = origShadow || '';
      } catch (_) {}
    },

    async simulateThreadScroll(logger) {
      const container = DOM.getMessageScrollContainer();
      if (!container) return;

      const peekDistance = Math.min(container.scrollHeight - container.clientHeight, randomRange(250, 400));
      if (peekDistance > 60) {
        logger.log('SCROLL', 'استعراض سريع للمحادثة (Scroll Glance)...');
        container.scrollBy({ top: -peekDistance, behavior: 'smooth' });
        await sleep(randomRange(200, 260));
        container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
        await sleep(randomRange(140, 180));
      }
    },

    async typeIntoComposer(composer, text, logger) {
      if (!composer) throw new Error('Composer element not found');

      composer.focus();
      await sleep(randomRange(70, 120));

      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(composer);
      selection.removeAllRanges();
      selection.addRange(range);
      try {
        document.execCommand('delete', false, null);
      } catch (_) {
        range.deleteContents();
      }
      await sleep(randomRange(50, 90));

      logger.log('TYPING', `محاكاة كتابة الرد (${text.length} حرف، تذبذب ${state.config.minTypingSpeed}-${state.config.maxTypingSpeed}ms)...`);

      for (let i = 0; i < text.length; i++) {
        if (state.emergencyAbort || !state.isRunning) throw new Error('ABORT_SIGNAL');

        const char = text[i];

        composer.dispatchEvent(new InputEvent('beforeinput', {
          bubbles: true,
          cancelable: true,
          inputType: 'insertText',
          data: char
        }));

        try {
          document.execCommand('insertText', false, char);
        } catch (_) {
          const sel = window.getSelection();
          if (sel && sel.rangeCount > 0) {
            const curRange = sel.getRangeAt(0);
            curRange.deleteContents();
            const textNode = document.createTextNode(char);
            curRange.insertNode(textNode);
            curRange.setStartAfter(textNode);
            curRange.collapse(true);
          }
        }

        composer.dispatchEvent(new InputEvent('input', {
          bubbles: true,
          cancelable: false,
          inputType: 'insertText',
          data: char
        }));

        let delay = randomRange(state.config.minTypingSpeed, state.config.maxTypingSpeed);
        if ([' ', '،', '.', '!', '؟'].includes(char)) {
          delay += randomRange(40, 80);
        }
        await sleep(delay);
      }

      if (state.emergencyAbort || !state.isRunning) throw new Error('ABORT_SIGNAL');
      await sleep(350);
      if (state.emergencyAbort || !state.isRunning) throw new Error('ABORT_SIGNAL');
      logger.log('TYPING', 'اكتملت الكتابة. إرسال عبر مفتاح Enter...');

      const enterDown = new KeyboardEvent('keydown', {
        key: 'Enter',
        code: 'Enter',
        keyCode: 13,
        which: 13,
        bubbles: true,
        cancelable: true
      });
      composer.dispatchEvent(enterDown);

      await sleep(80);

      const enterUp = new KeyboardEvent('keyup', {
        key: 'Enter',
        code: 'Enter',
        keyCode: 13,
        which: 13,
        bubbles: true,
        cancelable: true
      });
      composer.dispatchEvent(enterUp);

      await sleep(300);

      if (state.emergencyAbort || !state.isRunning) throw new Error('ABORT_SIGNAL');
      let currentContent = (composer.innerText || composer.textContent || '').trim();
      const isPlaceholder = currentContent.includes('رد في Messenger') || currentContent.includes('رد في Instagram') || currentContent.length === 0;

      if (!isPlaceholder && currentContent.length > 0) {
        logger.log('TYPING', 'الضغط الاحتياطي على زر الإرسال...');
        const sendBtn = DOM.getSendButton();
        if (sendBtn) {
          await this.naturalClick(sendBtn);
        }
      }

      // Verification that composer cleared
      await sleep(400);
      const postContent = (composer.innerText || composer.textContent || '').trim();
      if (!postContent.includes('رد في') && postContent.length > 0) {
        logger.log('WARN', 'تم التحقق: المربع يحتوي على نص متبقي، جاري تفريغه...');
        try {
          document.execCommand('selectAll', false, null);
          document.execCommand('delete', false, null);
        } catch (_) {}
      }

      await sleep(400);
    }
  };

  // ---------------------------------------------------------------------------
  // 5. HUD INTERFACE (Shadow DOM Isolated, RTL, Dark Glassmorphism)
  // ---------------------------------------------------------------------------
  class AutomatorHUD {
    constructor() {
      this.container = null;
      this.shadow = null;
      this.activeTab = 'console';
      this.isGhostMode = false;
      this.init();
    }

    init() {
      if (!document.body) {
        window.addEventListener('DOMContentLoaded', () => this.init(), { once: true });
        return;
      }

      const existing = document.getElementById('mbs-inbox-automator-root');
      if (existing) {
        existing.remove();
      }

      try {
        const { ghostKey, legacyGhostKey } = getTenantStorageKeys();
        const gVal = localStorage.getItem(ghostKey) || localStorage.getItem(legacyGhostKey);
        this.isGhostMode = gVal === 'true';
      } catch (_) {
        this.isGhostMode = false;
      }

      this.container = document.createElement('div');
      this.container.id = 'mbs-inbox-automator-root';
      this.container.style.position = 'fixed';
      this.container.style.bottom = '20px';
      this.container.style.left = '20px';
      this.container.style.zIndex = '9999999';
      this.container.style.direction = 'rtl';
      this.container.style.fontFamily = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Helvetica Neue", "Segoe UI", sans-serif';

      this.shadow = this.container.attachShadow({ mode: 'open' });
      this.render();
      document.body.appendChild(this.container);

      this.bindEvents();
      this.log('INIT', 'تم تحميل واجهة التحكم بنجاح (Apple Prismatic Liquid Glass Edition V5.2.0).');
    }

    render() {
      const cooldownSec = state.config.maxCooldown ? Number(((state.config.minCooldown + state.config.maxCooldown) / 2000).toFixed(1)) : 1.5;
      const monitoringSec = state.config.monitoringInterval ? Number((state.config.monitoringInterval / 1000).toFixed(1)) : 6;

      this.shadow.innerHTML = `
        <style>
          * { box-sizing: border-box; margin: 0; padding: 0; }
          .hud-card {
            resize: both;
            min-width: 320px;
            min-height: 52px;
            max-width: 95vw;
            max-height: 90vh;
            width: 480px;
            max-height: 620px;
            background: linear-gradient(135deg, 
              rgba(255, 255, 255, 0.62) 0%, 
              rgba(235, 248, 255, 0.52) 35%, 
              rgba(245, 240, 255, 0.48) 70%, 
              rgba(224, 250, 254, 0.55) 100%
            );
            -webkit-backdrop-filter: blur(28px) saturate(200%);
            backdrop-filter: blur(28px) saturate(200%);
            /* Prismatic crystal border */
            border: 1px solid rgba(255, 255, 255, 0.85);
            box-shadow: 
              0 20px 45px rgba(15, 23, 42, 0.10),
              inset 0 1.5px 1px rgba(255, 255, 255, 0.95),        /* Specular top light */
              inset 0 -1px 2px rgba(167, 139, 250, 0.15),        /* Subtle prismatic lavender glow */
              inset 1px 0 2px rgba(56, 189, 248, 0.20);          /* Aqua refractive side glow */
            border-radius: 22px;
            color: #0f172a;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            user-select: none;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Helvetica Neue", "Segoe UI", sans-serif;
            transition: width 0.3s cubic-bezier(0.16, 1, 0.3, 1), height 0.3s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.25s ease, border-radius 0.25s ease;
          }

          /* Ghost Stealth Mode Pill */
          .hud-card.ghost-mode {
            width: 100px !important;
            min-width: 100px !important;
            max-width: 100px !important;
            height: 32px !important;
            min-height: 32px !important;
            max-height: 32px !important;
            border-radius: 999px !important;
            padding: 0 12px !important;
            background: rgba(240, 249, 255, 0.88) !important;
            backdrop-filter: blur(24px) !important;
            -webkit-backdrop-filter: blur(24px) !important;
            border: 1px solid rgba(255, 255, 255, 0.95) !important;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.9) !important;
            color: #0f172a !important;
            opacity: 0.92;
            cursor: pointer;
            resize: none !important;
            flex-direction: row !important;
            align-items: center !important;
            justify-content: space-between !important;
          }
          .hud-card.ghost-mode:hover {
            opacity: 1.0 !important;
            box-shadow: 0 12px 28px rgba(2, 132, 199, 0.2) !important;
            border-color: #ffffff !important;
          }

          @keyframes pulse-dot {
            0% { transform: scale(0.9); opacity: 0.7; }
            50% { transform: scale(1.18); opacity: 1; }
            100% { transform: scale(0.9); opacity: 0.7; }
          }
          .ghost-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #94a3b8;
            display: inline-block;
            animation: pulse-dot 2s infinite ease-in-out;
          }
          .ghost-dot.running { background: #16a34a; box-shadow: 0 0 8px rgba(22, 163, 74, 0.5); }
          .ghost-dot.cooldown { background: #d97706; box-shadow: 0 0 8px rgba(217, 119, 6, 0.5); }
          .ghost-dot.monitoring { background: #0284c7; box-shadow: 0 0 8px rgba(2, 132, 199, 0.5); }
          .ghost-dot.stopped { background: #dc2626; box-shadow: 0 0 8px rgba(220, 38, 38, 0.5); }

          .ghost-dock-content {
            display: none;
            width: 100%;
            height: 100%;
            align-items: center;
            justify-content: space-between;
            font-size: 11px;
            font-weight: 600;
            color: #0f172a;
            user-select: none;
          }
          .hud-card.ghost-mode .ghost-dock-content {
            display: flex !important;
          }
          .hud-card.ghost-mode .hud-header,
          .hud-card.ghost-mode .hud-stats-bar,
          .hud-card.ghost-mode .hud-tabs,
          .hud-card.ghost-mode .hud-content,
          .hud-card.ghost-mode .hud-footer {
            display: none !important;
          }

          .header-icon-btn, .hud-btn {
            background: rgba(255, 255, 255, 0.65);
            border: 1px solid rgba(255, 255, 255, 0.9);
            color: #334155;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
            border-radius: 50%;
            width: 28px;
            height: 28px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            user-select: none;
          }
          .header-icon-btn:hover, .hud-btn:hover {
            background: rgba(255, 255, 255, 0.9);
            color: #0f172a;
            transform: scale(1.05);
          }
          .hud-header {
            cursor: grab;
            padding: 13px 18px;
            background: rgba(255, 255, 255, 0.35);
            border-bottom: 1px solid rgba(255, 255, 255, 0.5);
            display: flex;
            align-items: center;
            justify-content: space-between;
          }
          .hud-title {
            font-size: 13px;
            font-weight: 600;
            color: #0f172a;
            letter-spacing: -0.015em;
            display: flex;
            align-items: center;
            gap: 8px;
          }
          .hud-title-text {
            font-weight: 600;
            color: #0f172a;
            letter-spacing: -0.015em;
          }
          .hud-tenant-badge {
            font-size: 9.5px;
            font-weight: 500;
            padding: 2px 7px;
            border-radius: 6px;
            background: rgba(224, 242, 254, 0.85);
            color: #0369a1;
            border: 1px solid rgba(186, 230, 253, 0.9);
          }
          .status-badge {
            font-size: 9.5px;
            font-weight: 600;
            padding: 3px 9px;
            border-radius: 999px;
            letter-spacing: 0.3px;
            text-transform: uppercase;
          }
          .status-ready { background: rgba(148, 163, 184, 0.2); color: #475569; border: 1px solid rgba(148, 163, 184, 0.35); }
          .status-running { background: rgba(34, 197, 94, 0.16); color: #15803d; border: 1px solid rgba(34, 197, 94, 0.3); }
          .status-cooldown { background: rgba(245, 158, 11, 0.16); color: #b45309; border: 1px solid rgba(245, 158, 11, 0.3); }
          .status-monitoring { background: rgba(2, 132, 199, 0.16); color: #0284c7; border: 1px solid rgba(2, 132, 199, 0.3); }
          .status-stopped { background: rgba(239, 68, 68, 0.16); color: #b91c1c; border: 1px solid rgba(239, 68, 68, 0.3); }

          .hud-stats-bar, .hud-stats {
            padding: 10px 18px;
            background: transparent;
            border-bottom: 1px solid rgba(186, 230, 253, 0.4);
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 8px;
            text-align: center;
          }
          .stat-item {
            background: rgba(255, 255, 255, 0.30);
            border: 1px solid rgba(255, 255, 255, 0.65);
            border-radius: 14px;
            padding: 7px 4px;
            display: flex;
            flex-direction: column;
            gap: 2px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
          }
          .stat-value {
            font-size: 15px;
            font-weight: 700;
            color: #0f172a;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
          }
          .stat-label {
            font-size: 9.5px;
            font-weight: 500;
            color: #475569;
          }

          .hud-tabs {
            display: flex;
            background: rgba(219, 234, 254, 0.45);
            border: 1px solid rgba(255, 255, 255, 0.7);
            border-radius: 14px;
            padding: 3px;
            margin: 10px 18px 6px;
            gap: 3px;
          }
          .tab-btn {
            flex: 1;
            padding: 7px 12px;
            background: transparent;
            border: 1px solid transparent;
            color: #475569;
            font-size: 11.5px;
            font-weight: 500;
            cursor: pointer;
            border-radius: 11px;
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
            font-family: inherit;
          }
          .tab-btn:hover {
            color: #0f172a;
          }
          .tab-btn.active {
            background: #ffffff;
            color: #0284c7;
            border: 1px solid rgba(255, 255, 255, 0.9);
            box-shadow: 0 3px 10px rgba(2, 132, 199, 0.12), 0 1px 2px rgba(0, 0, 0, 0.04);
            border-radius: 11px;
            font-weight: 600;
          }

          .hud-content {
            padding: 10px 18px 14px;
            overflow-y: auto;
            max-height: 300px;
            min-height: 220px;
          }
          .tab-pane { display: none; }
          .tab-pane.active { display: block; }

          /* Terminal Tab */
          .terminal-box, .log-container {
            background: rgba(255, 255, 255, 0.55);
            border: 1px solid rgba(186, 230, 253, 0.6);
            border-radius: 14px;
            padding: 12px;
            font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
            font-size: 10.5px;
            height: 220px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 5px;
            color: #1e293b;
            box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.02);
          }
          .log-line { line-height: 1.45; word-break: break-word; }
          .log-time { color: #64748b; margin-left: 6px; font-size: 9.5px; }
          .log-tag-INIT { color: #64748b; font-weight: 500; }
          .log-tag-SCAN { color: #475569; }
          .log-tag-MATCH { color: #16a34a; font-weight: 600; }
          .log-tag-UNREAD { color: #d97706; font-weight: 600; }
          .log-tag-TYPING { color: #9333ea; font-weight: 500; }
          .log-tag-SCROLL { color: #64748b; }
          .log-tag-INFO { color: #0284c7; font-weight: 500; }
          .log-tag-WARN { color: #d97706; font-weight: 600; }
          .log-tag-ERROR { color: #dc2626; font-weight: 600; }
          .log-tag-STOP { color: #dc2626; font-weight: 600; }

          /* Rules Tab */
          .rule-card {
            background: rgba(255, 255, 255, 0.45);
            border: 1px solid rgba(186, 230, 253, 0.7);
            border-radius: 14px;
            padding: 12px;
            margin-bottom: 8px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            transition: background 0.2s ease, border-color 0.2s ease;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
          }
          .rule-card:hover {
            background: rgba(255, 255, 255, 0.75);
            border-color: rgba(186, 230, 253, 0.95);
          }
          .rule-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
          }
          .rule-title {
            font-size: 11px;
            font-weight: 600;
            color: #0284c7;
          }
          .rule-match-type {
            background: rgba(255, 255, 255, 0.85);
            border: 1px solid rgba(186, 230, 253, 0.85);
            border-radius: 8px;
            padding: 3px 8px;
            color: #0f172a;
            font-size: 10.5px;
            font-family: inherit;
            outline: none;
          }
          .rule-keywords-input, .rule-reply-input {
            width: 100%;
            background: rgba(255, 255, 255, 0.75);
            border: 1px solid rgba(186, 230, 253, 0.85);
            border-radius: 10px;
            padding: 7px 10px;
            color: #0f172a;
            font-size: 11px;
            font-family: inherit;
            direction: rtl;
            box-sizing: border-box;
            box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.02);
            transition: border-color 0.2s ease, background 0.2s ease;
          }
          .rule-keywords-input:focus, .rule-reply-input:focus {
            background: #ffffff;
            border-color: #0284c7;
            box-shadow: 0 0 0 2px rgba(2, 132, 199, 0.15);
            outline: none;
          }
          .rule-reply-input {
            min-height: 50px;
            resize: vertical;
          }
          .add-rule-btn {
            width: 100%;
            padding: 9px;
            background: rgba(255, 255, 255, 0.5);
            border: 1px dashed rgba(2, 132, 199, 0.45);
            border-radius: 12px;
            color: #0284c7;
            font-size: 11.5px;
            font-weight: 600;
            cursor: pointer;
            font-family: inherit;
            transition: all 0.2s ease;
          }
          .add-rule-btn:hover {
            background: rgba(224, 242, 254, 0.7);
            border-color: #0284c7;
          }

          /* Apple iOS Style Switch */
          .switch {
            position: relative;
            display: inline-block;
            width: 40px;
            height: 22px;
            flex-shrink: 0;
          }
          .switch input { opacity: 0; width: 0; height: 0; }
          .slider {
            position: absolute;
            cursor: pointer;
            top: 0; left: 0; right: 0; bottom: 0;
            background-color: rgba(203, 213, 225, 0.7);
            transition: background-color 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            border-radius: 999px;
          }
          .slider:before {
            position: absolute;
            content: "";
            height: 18px;
            width: 18px;
            left: 2px;
            bottom: 2px;
            background-color: #ffffff;
            border-radius: 50%;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.18);
            transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
          }
          input:checked + .slider { background-color: #0284c7; }
          input:checked + .slider:before { transform: translateX(18px); }

          /* Config Tab */
          .config-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid rgba(186, 230, 253, 0.4);
          }
          .config-label {
            font-size: 11.5px;
            color: #1e293b;
            font-weight: 500;
          }
          .config-input {
            background: rgba(255, 255, 255, 0.75);
            border: 1px solid rgba(186, 230, 253, 0.85);
            border-radius: 10px;
            padding: 6px 10px;
            color: #0f172a;
            font-weight: 600;
            font-size: 12px;
            text-align: center;
            font-family: inherit;
            box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.03);
            transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
            outline: none;
          }
          .config-input:focus {
            background: #ffffff;
            border-color: #0284c7;
            box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.15);
            outline: none;
          }

          /* Footer */
          .hud-footer {
            padding: 13px 18px;
            background: rgba(255, 255, 255, 0.45);
            border-top: 1px solid rgba(186, 230, 253, 0.45);
            display: flex;
            gap: 10px;
          }
          .btn-primary, #btn-start {
            flex: 2;
            padding: 10px 16px;
            background: linear-gradient(135deg, #0071E3 0%, #0091FF 100%);
            color: #ffffff;
            border: 1px solid rgba(255, 255, 255, 0.4);
            box-shadow: 0 4px 14px rgba(0, 113, 227, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.5);
            border-radius: 14px;
            font-size: 12.5px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            font-family: inherit;
          }
          .btn-primary:hover, #btn-start:hover {
            opacity: 0.95;
            transform: translateY(-1px);
            box-shadow: 0 6px 18px rgba(0, 113, 227, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.6);
          }
          .btn-primary:active, #btn-start:active {
            transform: translateY(0);
          }
          .btn-danger, #btn-stop {
            flex: 1;
            padding: 10px 16px;
            background: rgba(255, 59, 48, 0.08);
            color: #c53030;
            border: 1px solid rgba(255, 59, 48, 0.20);
            box-shadow: 0 2px 8px rgba(255, 59, 48, 0.06), inset 0 1px 0 rgba(255, 255, 255, 0.8);
            border-radius: 14px;
            font-size: 12.5px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            font-family: inherit;
          }
          .btn-danger:hover, #btn-stop:hover {
            background: rgba(255, 59, 48, 0.14);
            transform: translateY(-1px);
          }
          .btn-danger:active, #btn-stop:active {
            transform: translateY(0);
          }
        </style>

        <div class="hud-card${this.isGhostMode ? ' ghost-mode' : ''}">
          <!-- Ghost Stealth Mode Pill Content -->
          <div class="ghost-dock-content" id="ghost-dock" title="وضع الشبح النشط (انقر للتوسيع)">
            <div style="display: flex; align-items: center; gap: 6px;">
              <span class="ghost-dot ${state.isRunning ? 'running' : 'stopped'}" id="ghost-dot"></span>
              <span style="display: flex; align-items: center; gap: 4px; color: #0f172a; font-size: 11px; font-weight: 600;">
                <span id="ghost-reply-counter" style="color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, sans-serif;">${state.stats.matched}</span>
                <span style="font-size: 9.5px; color: #475569; font-weight: 500;">رد</span>
              </span>
            </div>
            <span style="font-size: 11px; color: #64748b; cursor: pointer; padding: 2px;" title="توسيع النافذة">⤢</span>
          </div>

          <div class="hud-header" id="hud-header">
            <div style="display: flex; gap: 8px; align-items: center;">
              <button class="header-icon-btn" id="btn-ghost" title="وضع الشبح (Ghost Mode)">👻</button>
              <button class="header-icon-btn" id="btn-minimize" title="تصغير إلى شريط مصغر">—</button>
              <button class="header-icon-btn" id="btn-maximize" title="تكبير / توسيع النافذة">⛶</button>
            </div>
            <div class="hud-title">
              <span class="hud-title-text">Meta Automation</span>
              <span id="hud-tenant-badge" class="hud-tenant-badge" title="معرّف الصفحة النشطة (Page ID)">${state.currentTenantId === 'default' ? 'Default Page' : `Page: ${state.currentTenantId}`}</span>
            </div>
            <div style="display: flex; gap: 8px; align-items: center;">
              <div id="hud-minimized-summary" style="display:none; align-items: center; gap: 8px;">
                <span style="font-size: 11px; color: #0f172a;">فحص: <b id="min-stat-eval">0</b></span>
                <span style="font-size: 11px; color: #16a34a;">رد: <b id="min-stat-match">0</b></span>
                <span style="font-size: 11px; color: #d97706;">استعادة: <b id="min-stat-unread">0</b></span>
              </div>
              <div id="hud-status" class="status-badge status-ready">READY</div>
            </div>
          </div>

          <div class="hud-stats-bar">
            <div class="stat-item">
              <span id="stat-evaluated" class="stat-value">0</span>
              <span class="stat-label">المفحوص</span>
            </div>
            <div class="stat-item">
              <span id="stat-matched" class="stat-value" style="color: #16a34a;">0</span>
              <span class="stat-label">تم الرد</span>
            </div>
            <div class="stat-item">
              <span id="stat-unread" class="stat-value" style="color: #d97706;">0</span>
              <span class="stat-label">غير مقروء</span>
            </div>
            <div class="stat-item">
              <span id="stat-skipped" class="stat-value" style="color: #64748b;">0</span>
              <span class="stat-label">مستبعد (حماية)</span>
            </div>
          </div>

          <div class="hud-tabs">
            <button class="tab-btn active" data-tab="console">سجل العمليات</button>
            <button class="tab-btn" data-tab="rules">إدارة القواعد</button>
            <button class="tab-btn" data-tab="config">الإعدادات البشرية</button>
          </div>

          <div class="hud-content">
            <!-- Terminal Tab -->
            <div id="tab-console" class="tab-pane active">
              <div id="terminal" class="terminal-box"></div>
            </div>

            <!-- Rules Tab -->
            <div id="tab-rules" class="tab-pane">
              <div id="rules-container"></div>
              <button id="add-rule-btn" class="add-rule-btn">+ إضافة قاعدة رد جديدة</button>
            </div>

            <!-- Config Tab -->
            <div id="tab-config" class="tab-pane">
              <div class="config-row">
                <span class="config-label">فترة التهدئة بين المحادثات (بالثواني)</span>
                <input type="number" id="cfg-cooldown-sec" class="config-input" style="width: 75px;" step="0.1" min="0.1" value="${cooldownSec}">
              </div>
              <div class="config-row">
                <span class="config-label">فترة فحص الرسائل الجديدة (بالثواني)</span>
                <input type="number" id="cfg-monitoring-sec" class="config-input" style="width: 75px;" step="0.5" min="1" value="${monitoringSec}">
              </div>
              <div class="config-row">
                <span class="config-label">سرعة الكتابة (مللي ثانية/حرف)</span>
                <input type="number" id="cfg-typing-speed" class="config-input" min="10" max="200" step="5" value="${state.config.typingSpeed || 45}">
              </div>
              <div class="config-row">
                <span class="config-label">تأطير بصري للمحادثة النشطة</span>
                <label class="switch">
                  <input type="checkbox" id="cfg-highlight-rows" ${state.config.highlightRows ? 'checked' : ''}>
                  <span class="slider"></span>
                </label>
              </div>
              <div class="config-row">
                <span class="config-label">محاكاة استعراض الرسائل السابقة (Scroll Peek)</span>
                <label class="switch">
                  <input type="checkbox" id="cfg-scroll-thread" ${state.config.scrollThread ? 'checked' : ''}>
                  <span class="slider"></span>
                </label>
              </div>
            </div>
          </div>

          <div class="hud-footer">
            <button id="btn-start" class="btn-primary">▶ تشغيل الأتمتة</button>
            <button id="btn-stop" class="btn-danger">⏹ إيقاف (Esc)</button>
          </div>
        </div>
      `;

      this.renderRulesList();
    }

    toggleGhostMode(enable) {
      this.isGhostMode = enable;
      try {
        const { ghostKey } = getTenantStorageKeys();
        localStorage.setItem(ghostKey, enable ? 'true' : 'false');
      } catch (_) {}

      const card = this.shadow.querySelector('.hud-card');
      if (!card) return;

      if (enable) {
        card.classList.add('ghost-mode');
        this.log('INFO', 'تفعيل وضع الشبح الفائق (Ghost Stealth Mode 👻). انقر على الشريط لاستعادة الواجهة.');
      } else {
        card.classList.remove('ghost-mode');
        this.log('INFO', 'استعادة واجهة التحكم الكاملة.');
      }
    }

    bindEvents() {
      // Draggable window implementation (supports both full header and ghost dock)
      const header = this.shadow.getElementById('hud-header');
      const ghostDock = this.shadow.getElementById('ghost-dock');
      let isDragging = false;
      let startX = 0, startY = 0;
      let initialLeft = 0, initialTop = 0;
      let dragDistance = 0;

      const handleStartDrag = (e) => {
        if (e.target.closest('button, input, select, label')) return;
        isDragging = true;
        dragDistance = 0;
        if (header) header.style.cursor = 'grabbing';
        startX = e.clientX;
        startY = e.clientY;
        
        const rect = this.container.getBoundingClientRect();
        initialLeft = rect.left;
        initialTop = rect.top;

        this.container.style.bottom = 'auto';
        this.container.style.right = 'auto';
        this.container.style.left = `${initialLeft}px`;
        this.container.style.top = `${initialTop}px`;

        const onMouseMove = (moveEvent) => {
          if (!isDragging) return;
          const dx = moveEvent.clientX - startX;
          const dy = moveEvent.clientY - startY;
          dragDistance = Math.hypot(dx, dy);

          let newLeft = initialLeft + dx;
          let newTop = initialTop + dy;

          const w = this.container.offsetWidth || 110;
          const h = this.container.offsetHeight || 32;

          newLeft = Math.max(10, Math.min(window.innerWidth - w - 10, newLeft));
          newTop = Math.max(10, Math.min(window.innerHeight - h - 10, newTop));

          this.container.style.left = `${newLeft}px`;
          this.container.style.top = `${newTop}px`;
        };

        const onMouseUp = () => {
          isDragging = false;
          if (header) header.style.cursor = 'grab';
          document.removeEventListener('mousemove', onMouseMove);
          document.removeEventListener('mouseup', onMouseUp);
        };

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
      };

      if (header) header.addEventListener('mousedown', handleStartDrag);
      if (ghostDock) {
        ghostDock.addEventListener('mousedown', handleStartDrag);
        ghostDock.addEventListener('click', (e) => {
          if (dragDistance > 5) return;
          e.stopPropagation();
          this.toggleGhostMode(false);
        });
      }

      // Ghost Mode Button Toggle
      const btnGhost = this.shadow.getElementById('btn-ghost');
      if (btnGhost) {
        btnGhost.addEventListener('click', (e) => {
          e.stopPropagation();
          this.toggleGhostMode(true);
        });
      }

      // Minimize / Restore Toggle
      const btnMin = this.shadow.getElementById('btn-minimize');
      const btnMax = this.shadow.getElementById('btn-maximize');
      let isMinimized = false;
      let isMaximized = false;

      btnMin.addEventListener('click', () => {
        if (this.isGhostMode) {
          this.toggleGhostMode(false);
        }
        isMinimized = !isMinimized;
        const card = this.shadow.querySelector('.hud-card');
        const stats = this.shadow.querySelector('.hud-stats-bar');
        const tabs = this.shadow.querySelector('.hud-tabs');
        const content = this.shadow.querySelector('.hud-content');
        const footer = this.shadow.querySelector('.hud-footer');
        const minSummary = this.shadow.getElementById('hud-minimized-summary');

        if (isMinimized) {
          stats.style.display = 'none';
          tabs.style.display = 'none';
          content.style.display = 'none';
          footer.style.display = 'none';
          minSummary.style.display = 'flex';
          card.style.width = '360px';
          card.style.maxHeight = '52px';
          card.style.resize = 'none';
          btnMin.textContent = '🗖';
          btnMin.title = 'استعادة النافذة بالحجم الطبيعي';
        } else {
          stats.style.display = 'grid';
          tabs.style.display = 'flex';
          content.style.display = 'block';
          footer.style.display = 'flex';
          minSummary.style.display = 'none';
          card.style.width = isMaximized ? '680px' : '480px';
          card.style.maxHeight = isMaximized ? '750px' : '620px';
          card.style.resize = 'both';
          btnMin.textContent = '—';
          btnMin.title = 'تصغير إلى شريط مصغر';
        }
      });

      btnMax.addEventListener('click', () => {
        if (this.isGhostMode) {
          this.toggleGhostMode(false);
        }
        if (isMinimized) {
          btnMin.click();
        }
        isMaximized = !isMaximized;
        const card = this.shadow.querySelector('.hud-card');
        const content = this.shadow.querySelector('.hud-content');
        const terminal = this.shadow.getElementById('terminal');

        if (isMaximized) {
          card.style.width = '680px';
          card.style.maxHeight = '750px';
          content.style.maxHeight = '480px';
          if (terminal) terminal.style.height = '380px';
          btnMax.textContent = '🗗';
          btnMax.title = 'الحجم الافتراضي';
        } else {
          card.style.width = '480px';
          card.style.maxHeight = '620px';
          content.style.maxHeight = '300px';
          if (terminal) terminal.style.height = '220px';
          btnMax.textContent = '⛶';
          btnMax.title = 'تكبير / توسيع النافذة';
        }
      });
      const tabBtns = this.shadow.querySelectorAll('.tab-btn');
      tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
          tabBtns.forEach(b => b.classList.remove('active'));
          this.shadow.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
          btn.classList.add('active');
          const targetTab = btn.getAttribute('data-tab');
          this.shadow.getElementById(`tab-${targetTab}`).classList.add('active');
        });
      });

      this.shadow.getElementById('btn-start').addEventListener('click', () => Orchestrator.start());
      this.shadow.getElementById('btn-stop').addEventListener('click', () => Orchestrator.stop());

      this.shadow.getElementById('add-rule-btn').addEventListener('click', () => {
        state.rules.push({
          id: 'rule_' + Date.now(),
          keyword: 'كلمة_مفتاحية',
          reply: 'نص الرد الآلي هنا...',
          matchType: 'contains',
          active: true
        });
        saveRules();
        this.renderRulesList();
      });

      const typingSpeedEl = this.shadow.getElementById('cfg-typing-speed');
      if (typingSpeedEl) {
        const handleTypingSpeed = (e) => {
          const speed = parseInt(e.target.value, 10) || 45;
          state.config.typingSpeed = speed;
          state.config.minTypingSpeed = Math.max(10, Math.round(speed * 0.75));
          state.config.maxTypingSpeed = Math.round(speed * 1.25);
          saveConfig();
        };
        typingSpeedEl.addEventListener('input', handleTypingSpeed);
        typingSpeedEl.addEventListener('change', handleTypingSpeed);
      }

      const cooldownSecEl = this.shadow.getElementById('cfg-cooldown-sec');
      if (cooldownSecEl) {
        const handleCooldown = (e) => {
          const sec = parseFloat(e.target.value) || 1.5;
          state.config.minCooldown = Math.max(100, Math.round(sec * 850));
          state.config.maxCooldown = Math.max(200, Math.round(sec * 1150));
          saveConfig();
        };
        cooldownSecEl.addEventListener('input', handleCooldown);
        cooldownSecEl.addEventListener('change', handleCooldown);
      }

      const monitoringSecEl = this.shadow.getElementById('cfg-monitoring-sec');
      if (monitoringSecEl) {
        const handleMonitoring = (e) => {
          const sec = parseFloat(e.target.value) || 6.0;
          state.config.monitoringInterval = Math.max(500, Math.round(sec * 1000));
          saveConfig();
        };
        monitoringSecEl.addEventListener('input', handleMonitoring);
        monitoringSecEl.addEventListener('change', handleMonitoring);
      }

      this.shadow.getElementById('cfg-highlight-rows').addEventListener('change', (e) => {
        state.config.highlightRows = e.target.checked;
        saveConfig();
      });
      this.shadow.getElementById('cfg-scroll-thread').addEventListener('change', (e) => {
        state.config.scrollThread = e.target.checked;
        saveConfig();
      });

      // Strict user trusted Escape keypress
      window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && e.isTrusted && state.isRunning) {
          this.log('STOP', 'تم تفعيل إيقاف الطوارئ عبر زر Escape من المستخدم.');
          Orchestrator.stop();
        }
      });

      // Multi-Tenant SPA Navigation & URL Watcher
      window.addEventListener('popstate', () => {
        checkAndRehydrateTenant(this);
      });

      setInterval(() => {
        checkAndRehydrateTenant(this);
      }, 2500);
    }

    updateTenantUI(tenantId) {
      const badge = this.shadow.getElementById('hud-tenant-badge');
      if (badge) {
        badge.textContent = tenantId === 'default' ? 'Default Page' : `Page: ${tenantId}`;
      }
    }

    updateConfigUI() {
      const typingSpeedEl = this.shadow.getElementById('cfg-typing-speed');
      if (typingSpeedEl) {
        typingSpeedEl.value = state.config.typingSpeed || Math.round(((state.config.minTypingSpeed || 35) + (state.config.maxTypingSpeed || 65)) / 2) || 45;
      }
      const cooldownEl = this.shadow.getElementById('cfg-cooldown-sec');
      if (cooldownEl) {
        const sec = state.config.maxCooldown ? ((state.config.minCooldown + state.config.maxCooldown) / 2000).toFixed(1) : '1.5';
        cooldownEl.value = Number(sec);
      }
      const monitoringEl = this.shadow.getElementById('cfg-monitoring-sec');
      if (monitoringEl) {
        const sec = state.config.monitoringInterval ? (state.config.monitoringInterval / 1000).toFixed(1) : '6.0';
        monitoringEl.value = Number(sec);
      }
      const hlRows = this.shadow.getElementById('cfg-highlight-rows');
      if (hlRows) hlRows.checked = state.config.highlightRows;
      const scrThr = this.shadow.getElementById('cfg-scroll-thread');
      if (scrThr) scrThr.checked = state.config.scrollThread;
    }

    renderRulesList() {
      const container = this.shadow.getElementById('rules-container');
      if (!container) return;

      container.innerHTML = state.rules.map((rule, idx) => `
        <div class="rule-card" data-idx="${idx}">
          <div class="rule-header">
            <span class="rule-title">قاعدة #${idx + 1}</span>
            <div style="display: flex; gap: 6px; align-items: center;">
              <select class="rule-match-type" data-idx="${idx}">
                <option value="contains" ${rule.matchType === 'contains' ? 'selected' : ''}>يحتوي</option>
                <option value="word" ${rule.matchType === 'word' ? 'selected' : ''}>كلمة مطابقة</option>
                <option value="exact" ${rule.matchType === 'exact' ? 'selected' : ''}>مطابقة تامة</option>
              </select>
              <label class="switch">
                <input type="checkbox" class="rule-toggle" data-idx="${idx}" ${rule.active ? 'checked' : ''}>
                <span class="slider"></span>
              </label>
              <button class="rule-del-btn" data-idx="${idx}" style="background:none; border:none; color:#FF453A; cursor:pointer; font-size:12px;">✕</button>
            </div>
          </div>
          <input type="text" class="rule-keywords-input" data-idx="${idx}" placeholder="الكلمات المفتاحية مفصولة بفاصلة" value="${rule.keyword || ''}">
          <textarea class="rule-reply-input" data-idx="${idx}" placeholder="نص الرد الفوري...">${rule.reply || ''}</textarea>
        </div>
      `).join('');

      container.querySelectorAll('.rule-match-type').forEach(el => {
        el.addEventListener('change', (e) => {
          const idx = parseInt(e.target.getAttribute('data-idx'), 10);
          state.rules[idx].matchType = e.target.value;
          saveRules();
        });
      });

      container.querySelectorAll('.rule-toggle').forEach(el => {
        el.addEventListener('change', (e) => {
          const idx = parseInt(e.target.getAttribute('data-idx'), 10);
          state.rules[idx].active = e.target.checked;
          saveRules();
        });
      });

      container.querySelectorAll('.rule-keywords-input').forEach(el => {
        const handler = (e) => {
          const idx = parseInt(e.target.getAttribute('data-idx'), 10);
          if (state.rules[idx]) {
            state.rules[idx].keyword = e.target.value;
            saveRules();
          }
        };
        el.addEventListener('input', handler);
        el.addEventListener('change', handler);
      });

      container.querySelectorAll('.rule-reply-input').forEach(el => {
        const handler = (e) => {
          const idx = parseInt(e.target.getAttribute('data-idx'), 10);
          if (state.rules[idx]) {
            state.rules[idx].reply = e.target.value;
            saveRules();
          }
        };
        el.addEventListener('input', handler);
        el.addEventListener('change', handler);
      });

      container.querySelectorAll('.rule-del-btn').forEach(el => {
        el.addEventListener('click', (e) => {
          const idx = parseInt(e.target.getAttribute('data-idx'), 10);
          state.rules.splice(idx, 1);
          saveRules();
          this.renderRulesList();
        });
      });
    }

    setStatus(text, type = 'ready') {
      const el = this.shadow.getElementById('hud-status');
      if (el) {
        el.textContent = text;
        el.className = `status-badge status-${type}`;
      }
      const gDot = this.shadow.getElementById('ghost-dot');
      if (gDot) {
        gDot.className = `ghost-dot ${type}`;
      }
      if (window.pyOnStateChange) {
        window.pyOnStateChange(text).catch(() => {});
      }
    }

    updateStats() {
      const sEval = this.shadow.getElementById('stat-evaluated');
      if (sEval) sEval.textContent = state.stats.evaluated;
      const mEval = this.shadow.getElementById('min-stat-eval');
      if (mEval) mEval.textContent = state.stats.evaluated;
      const mMatch = this.shadow.getElementById('min-stat-match');
      if (mMatch) mMatch.textContent = state.stats.matched;
      const mUnread = this.shadow.getElementById('min-stat-unread');
      if (mUnread) mUnread.textContent = state.stats.unreadRestored;
      const sMatch = this.shadow.getElementById('stat-matched');
      if (sMatch) sMatch.textContent = state.stats.matched;
      const sUnread = this.shadow.getElementById('stat-unread');
      if (sUnread) sUnread.textContent = state.stats.unreadRestored;
      const sSkip = this.shadow.getElementById('stat-skipped');
      if (sSkip) sSkip.textContent = state.stats.skippedOutbound;

      const gCounter = this.shadow.getElementById('ghost-reply-counter');
      if (gCounter) gCounter.textContent = state.stats.matched;

      if (window.pyUpdateStats) {
        window.pyUpdateStats(state.stats).catch(() => {});
      }
    }

    log(tag, message) {
      const terminal = this.shadow.getElementById('terminal');
      if (!terminal) return;

      const line = document.createElement('div');
      line.className = 'log-line';

      const time = new Date().toLocaleTimeString('ar-EG', { hour12: false });
      line.innerHTML = `
        <span class="log-tag-${tag}">[${tag}]</span>
        <span>${message}</span>
        <span class="log-time">${time}</span>
      `;

      terminal.appendChild(line);
      terminal.scrollTop = terminal.scrollHeight;

      while (terminal.children.length > 150) {
        terminal.removeChild(terminal.firstChild);
      }

      if (window.pyLog) {
        window.pyLog(tag, message).catch(() => {});
      }
    }
  }

  // ---------------------------------------------------------------------------
  // 6. ORCHESTRATION ENGINE (Sequential Step-By-Step Workflow)
  // ---------------------------------------------------------------------------
  const Orchestrator = {
    hud: null,

    init(hud) {
      this.hud = hud;
    },

    async start() {
      if (state.isRunning) return;

      abortAllSleeps();
      checkAndRehydrateTenant(this.hud);
      state.isRunning = true;
      state.emergencyAbort = false;
      state.currentIndex = 0;
      this.hud.setStatus('RUNNING', 'running');
      await DOM.ensureUnreadFilterActive(this.hud);
      this.hud.log('INIT', 'بدء فحص قائمة المحادثات (تثبيت فلتر غير مقروء التلقائي)...');

      try {
        await this.runLoop();
      } catch (err) {
        if (err.message === 'ABORT_SIGNAL') {
          this.hud.log('STOP', 'تم إيقاف الدورة فوراً بناءً على إشارة التوقف.');
        } else {
          state.stats.errors++;
          this.hud.log('ERROR', `خطأ غير متوقع: ${err.message}`);
          console.error(err);
        }
      } finally {
        this.stop();
      }
    },

    clearActiveRowHighlight(row = null) {
      try {
        const target = row || state.activeRowElement;
        if (target) {
          if (target.dataset) {
            if (target.dataset.origBorderRadius !== undefined) {
              target.style.borderRadius = target.dataset.origBorderRadius;
              delete target.dataset.origBorderRadius;
            } else {
              target.style.removeProperty('border-radius');
            }

            if (target.dataset.origBackground !== undefined) {
              target.style.background = target.dataset.origBackground;
              delete target.dataset.origBackground;
            } else {
              target.style.removeProperty('background');
            }

            if (target.dataset.origBoxShadow !== undefined) {
              target.style.boxShadow = target.dataset.origBoxShadow;
              delete target.dataset.origBoxShadow;
            } else {
              target.style.removeProperty('box-shadow');
            }

            if (target.dataset.origBorder !== undefined) {
              target.style.border = target.dataset.origBorder;
              delete target.dataset.origBorder;
            } else {
              target.style.removeProperty('border');
            }

            if (target.dataset.origBackdropFilter !== undefined) {
              target.style.backdropFilter = target.dataset.origBackdropFilter;
              delete target.dataset.origBackdropFilter;
            } else {
              target.style.removeProperty('backdrop-filter');
            }

            if (target.dataset.origWebkitBackdropFilter !== undefined) {
              target.style.webkitBackdropFilter = target.dataset.origWebkitBackdropFilter;
              delete target.dataset.origWebkitBackdropFilter;
            } else {
              target.style.removeProperty('-webkit-backdrop-filter');
            }

            if (target.dataset.origTransition !== undefined) {
              target.style.transition = target.dataset.origTransition;
              delete target.dataset.origTransition;
            } else {
              target.style.removeProperty('transition');
            }

            if (target.dataset.origOutline !== undefined) {
              target.style.outline = target.dataset.origOutline;
              delete target.dataset.origOutline;
            } else {
              target.style.removeProperty('outline');
            }
          } else {
            target.style.removeProperty('border-radius');
            target.style.removeProperty('background');
            target.style.removeProperty('box-shadow');
            target.style.removeProperty('border');
            target.style.removeProperty('backdrop-filter');
            target.style.removeProperty('-webkit-backdrop-filter');
            target.style.removeProperty('transition');
            target.style.removeProperty('outline');
          }
        }
      } catch (err) {
        console.warn('[MBS Automator] Error restoring active row styles:', err);
      } finally {
        state.activeRowElement = null;
        state.activeRowOriginalStyles = null;
      }
    },

    stop() {
      const wasRunning = state.isRunning;
      state.isRunning = false;
      state.emergencyAbort = true;
      abortAllSleeps();

      if (this.hud) {
        this.hud.setStatus('STOPPED', 'stopped');
        if (wasRunning) {
          this.hud.log('STOP', 'الأتمتة متوقفة حالياً.');
        }
      }

      this.clearActiveRowHighlight();
    },

    async runLoop() {
      while (state.isRunning && !state.emergencyAbort) {
        // STEP -1: Multi-Tenant Rehydration Check
        checkAndRehydrateTenant(this.hud);

        // STEP 0: Enforce "غير مقروء" (Unread) Filter Lock
        await DOM.ensureUnreadFilterActive(this.hud);

        // STEP 1: Query current rows
        let rows = DOM.getConversationRows();
        if (!rows || rows.length === 0) {
          this.hud.setStatus('MONITORING', 'monitoring');
          this.hud.log('INFO', 'لا توجد محادثات غير مقروءة حالياً. وضع المراقبة بانتظار رسائل جديدة...');
          await sleep(state.config.monitoringInterval || 4000);

          const sidebar = DOM.getSidebarScrollContainer();
          if (sidebar && sidebar.scrollTop > 0) {
            sidebar.scrollTo({ top: 0, behavior: 'smooth' });
            await sleep(800);
          }
          continue;
        }

        // Sequential Pointer Selection with Skip of already handled rows
        let targetRow = null;
        let selectedIndex = -1;
        let targetFingerprint = null;
        let targetContactKey = null;

        for (let i = 0; i < rows.length; i++) {
          const r = rows[i];
          const name = DOM.getRowCustomerName(r);
          const snippet = DOM.getRowSnippet(r);
          const key = DOM.getStableRowKey(r) || (name ? `contact_${normalizeArabicText(name)}` : null);
          const fingerprint = key ? `${key}__${snippet}` : null;

          const isSameSnippetReplied = key && snippet && state.lastRepliedSnippets.get(key) === snippet;
          const isProcessed = (fingerprint && state.processedSnapshots.has(fingerprint)) ||
                              (key && state.processedContacts.has(key)) ||
                              (key && state.skippedRows && state.skippedRows.has(key)) ||
                              (fingerprint && state.skippedRows && state.skippedRows.has(fingerprint));

          if (!isSameSnippetReplied && !isProcessed) {
            targetRow = r;
            selectedIndex = i;
            targetFingerprint = fingerprint;
            targetContactKey = key;
            break;
          }
        }

        // Check if sidebar scrolling is needed or queue finished
        if (!targetRow) {
          const sidebar = DOM.getSidebarScrollContainer();
          let canScrollMore = false;
          if (sidebar && sidebar.scrollTop + sidebar.clientHeight < sidebar.scrollHeight - 15) {
            this.hud.log('INFO', `تمت معالجة الصفوف الظاهرة (${rows.length}). جاري التمرير لأسفل لجلب المزيد...`);
            sidebar.scrollBy({ top: 220, behavior: 'smooth' });
            await sleep(1500);
            const updatedRows = DOM.getConversationRows();
            canScrollMore = updatedRows.some(r => {
              const n = DOM.getRowCustomerName(r);
              const s = DOM.getRowSnippet(r);
              const k = DOM.getStableRowKey(r) || (n ? `contact_${normalizeArabicText(n)}` : null);
              const fp = k ? `${k}__${s}` : null;
              const isSame = k && s && state.lastRepliedSnippets.get(k) === s;
              const isSkipped = (k && state.skippedRows && state.skippedRows.has(k)) ||
                                (fp && state.skippedRows && state.skippedRows.has(fp));
              return (!k || (!state.processedContacts.has(k) && !isSame)) &&
                     (!fp || !state.processedSnapshots.has(fp)) && !isSkipped;
            });

            if (canScrollMore) {
              continue;
            }
          }

          // Loop completed:
          // 1. Scroll back smoothly to top of sidebar
          if (sidebar && sidebar.scrollTop > 0) {
            this.hud.log('SCROLL', 'اكتمل فحص القائمة. العودة لأعلى القائمة (Scroll to Top)...');
            sidebar.scrollTo({ top: 0, behavior: 'smooth' });
            await sleep(1000);
          }

          // 2. Ensure filter is still active
          await DOM.ensureUnreadFilterActive(this.hud);

          // 3. Transition to Standby Monitoring Mode
          this.hud.setStatus('MONITORING', 'monitoring');
          this.hud.log('INFO', `اكتمل فحص جميع المحادثات غير المقروءة. وضع المراقبة الذكية بانتظار رسائل جديدة (إعادة الفحص من أول محادثة كل ${state.config.monitoringInterval / 1000} ثوانٍ)...`);
          await sleep(state.config.monitoringInterval);

          if (state.emergencyAbort) break;

          // 4. Clear processedContacts and skippedRows for the new cycle (preserves lastRepliedSnippets & processedSnapshots)
          state.processedContacts.clear();
          if (state.skippedRows) state.skippedRows.clear();
          this.hud.setStatus('RUNNING', 'running');
          continue;
        }

        const contactName = DOM.getRowCustomerName(targetRow);
        let contactKey = targetContactKey || DOM.getStableRowKey(targetRow) || (contactName ? `contact_${normalizeArabicText(contactName)}` : `row_${Date.now()}`);
        let rowFingerprint = targetFingerprint || `${contactKey}__${DOM.getRowSnippet(targetRow)}`;

        state.stats.evaluated++;
        this.hud.updateStats();
        this.hud.log('SCAN', `--- [محادثة #${selectedIndex + 1}/${rows.length}] تفعيل العميل: "${contactName || contactKey}" ---`);

        // Safe backup into dataset
        try {
          targetRow.dataset.origBorderRadius = targetRow.style.borderRadius || '';
          targetRow.dataset.origBackground = targetRow.style.background || '';
          targetRow.dataset.origBoxShadow = targetRow.style.boxShadow || '';
          targetRow.dataset.origBorder = targetRow.style.border || '';
          targetRow.dataset.origBackdropFilter = targetRow.style.backdropFilter || '';
          targetRow.dataset.origWebkitBackdropFilter = targetRow.style.webkitBackdropFilter || '';
          targetRow.dataset.origTransition = targetRow.style.transition || '';
          targetRow.dataset.origOutline = targetRow.style.outline || '';
        } catch (_) {}

        if (state.config.highlightRows) {
          try {
            targetRow.style.setProperty('border-radius', '18px', 'important');
            targetRow.style.setProperty('background', 'linear-gradient(135deg, rgba(224, 242, 254, 0.45), rgba(243, 232, 255, 0.35))', 'important');
            targetRow.style.setProperty('-webkit-backdrop-filter', 'blur(8px)', 'important');
            targetRow.style.setProperty('backdrop-filter', 'blur(8px)', 'important');
            targetRow.style.setProperty('border', '1px solid rgba(56, 189, 248, 0.45)', 'important');
            targetRow.style.setProperty('box-shadow', '0 4px 18px rgba(14, 165, 233, 0.12), inset 0 1px 0.5px rgba(255, 255, 255, 0.8)', 'important');
            targetRow.style.setProperty('transition', 'all 0.25s cubic-bezier(0.16, 1, 0.3, 1)', 'important');
          } catch (_) {}
          state.activeRowElement = targetRow;
        }

        try {
          const ROW_TIMEOUT_MS = 8000;
          let timeoutId = null;
          const timeoutPromise = new Promise((_, reject) => {
            timeoutId = setTimeout(() => reject(new Error('ROW_TIMEOUT_EXCEEDED')), ROW_TIMEOUT_MS);
          });

          const processRowPromise = (async () => {
            // STEP 2: Safe Thread Activation & Viewport Sync
            const clickTarget = DOM.getRowClickTarget(targetRow);
            await HumanSimulator.naturalClick(clickTarget);

            this.hud.log('SCAN', 'انتظار تطابق نافذة المحادثة مع العميل...');
            const chatLoaded = await DOM.waitForConversationLoad(targetRow, contactName, clickTarget, this.hud);

            if (!chatLoaded) {
              const currHeader = DOM.getActiveChatContactName();
              this.hud.log('WARN', `تعذر تبديل المحادثة للعميل "${contactName || contactKey}" (المحادثة المعروضة حالياً: "${currHeader || 'غير محددة'}"). تخطي لحماية المحادثة الحالية.`);
              state.processedContacts.add(contactKey);
              if (rowFingerprint) {
                state.processedSnapshots.add(rowFingerprint);
                pruneLRUCache(state.processedSnapshots, 350, 100);
              }
              return { skipLoop: true, cooldown: 0 };
            }

            const headerName = DOM.getActiveChatContactName();
            if (headerName) {
              contactKey = `contact_${normalizeArabicText(headerName)}`;
            }

            if (state.config.scrollThread) {
              await HumanSimulator.simulateThreadScroll(this.hud);
            } else {
              await sleep(randomRange(150, 250));
            }

            // STEP 3: Inbound Boundary Evaluation (Post-Representative Messages Only)
            this.hud.log('SCAN', 'فحص حدود الرسائل (الرسائل الواردة بعد آخر رد من الصفحة)...');
            const { lastIsOutbound, customerBubbles } = DOM.parseInboundBoundary();

            if (lastIsOutbound) {
              state.stats.skippedOutbound++;
              this.hud.updateStats();
              this.hud.log('INFO', '[حماية] آخر رسالة مرسلة من الصفحة مسبقاً (بانتظار رد العميل). الانتقال للمحادثة التالية دون إعادة التمييز كغير مقروءة...');

              // IMPORTANT: Do NOT executeBranchB (do NOT restore to unread) when we sent the last message!
              // This prevents the thread from being trapped in an infinite loop in the unread queue.
              if (contactKey) state.processedContacts.add(contactKey);
              if (rowFingerprint) {
                state.processedSnapshots.add(rowFingerprint);
                pruneLRUCache(state.processedSnapshots, 350, 100);
              }

              const cooldown = randomRange(state.config.minCooldown, state.config.maxCooldown);
              return { skipLoop: true, cooldown };
            }

            const customerTexts = (customerBubbles || []).map(b => (b ? (b.innerText || b.textContent || '') : '').trim()).filter(Boolean);

            // WhatsApp Unsupported Message Detection:
            const canvas = DOM.getChatCanvas();
            const canvasText = canvas ? (canvas.innerText || '') : '';
            const hasUnsupportedWhatsApp = [
              "Message can't be displayed",
              "which is not supported in Inbox",
              "WhatsApp Business App",
              "محتوى غير مدعوم"
            ].some(indicator => canvasText.includes(indicator));

            const validCustomerTexts = customerTexts.filter(t => 
              !t.includes("Message can't be displayed") &&
              !t.includes("which is not supported in Inbox") &&
              !t.includes("WhatsApp Business App") &&
              !t.includes("محتوى غير مدعوم")
            );

            if (hasUnsupportedWhatsApp && validCustomerTexts.length === 0) {
              this.hud.log('INFO', '[INFO] رسالة واتساب غير مدعومة على الويب (وسائط/طلب). تخطي فوري لمراجعة خدمة العملاء.');
              try {
                window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }));
                releaseChatFocus();
              } catch (_) {}
              if (contactKey) state.processedContacts.add(contactKey);
              if (rowFingerprint) {
                state.processedSnapshots.add(rowFingerprint);
                pruneLRUCache(state.processedSnapshots, 350, 100);
              }
              const cooldown = randomRange(state.config.minCooldown, state.config.maxCooldown);
              return { skipLoop: true, cooldown };
            }

            if (customerBubbles.length === 0 || customerTexts.length === 0) {
              this.hud.log('INFO', 'لا توجد نصوص رسائل واردة جديدة قابلة للمعالجة (وسائط أو رسالة نظام/واتساب). استعادة كغير مقروء...');
              await this.executeBranchB(contactKey, rowFingerprint, targetRow);

              const cooldown = randomRange(state.config.minCooldown, state.config.maxCooldown);
              return { skipLoop: true, cooldown };
            }

            // STEP 4: Visual Search & Keyword Evaluation
            const latestBubble = customerBubbles[customerBubbles.length - 1];
            await HumanSimulator.highlightCustomerBubble(latestBubble);

            const combinedText = customerTexts.join(' ');
            const snippet = combinedText.length > 40 ? combinedText.slice(0, 40) + '...' : combinedText;
            this.hud.log('SCAN', `فحص نصوص العميل الواردة (${customerTexts.length} فقاعات): "${snippet}"`);

            let matchResult = null;
            for (let i = customerTexts.length - 1; i >= 0; i--) {
              matchResult = evaluateActiveRules(customerTexts[i], state.rules);
              if (matchResult) break;
            }
            if (!matchResult && combinedText) {
              matchResult = evaluateActiveRules(combinedText, state.rules);
            }

            // STEP 5: Execution Branches
            if (matchResult) {
              // Branch A: Match Found
              const { rule, matchedKeyword } = matchResult;

              const activeSnippet = DOM.getRowSnippet(targetRow);
              if (contactKey && activeSnippet) {
                state.lastRepliedSnippets.set(contactKey, activeSnippet);
                pruneLRUCache(state.lastRepliedSnippets, 350, 100);
              }
              if (contactKey) state.processedContacts.add(contactKey);
              if (rowFingerprint) {
                state.processedSnapshots.add(rowFingerprint);
                pruneLRUCache(state.processedSnapshots, 350, 100);
              }

              state.stats.matched++;
              this.hud.updateStats();
              this.hud.log('MATCH', `تطابق الكلمة: "${matchedKeyword}". جاري إرسال الرد للعميل ${contactName || contactKey}...`);

              const composer = DOM.getComposer();
              if (!composer) {
                this.hud.log('ERROR', 'محرر الرسائل غير متاح. تعذر إرسال الرد.');
              } else {
                await HumanSimulator.typeIntoComposer(composer, rule.reply, this.hud);
                this.hud.log('INFO', `تم إرسال الرد بنجاح للعميل ${contactName || contactKey}.`);
              }
            } else {
              // Branch B: No Match / Media Message / Skip
              this.hud.log('SCAN', 'لا توجد كلمات مفتاحية مطابقة في رسالة العميل. استعادة المحادثة كغير مقروءة لمراجعة خدمة العملاء...');
              await this.executeBranchB(contactKey, rowFingerprint, targetRow);
            }

            return { skipLoop: false };
          })();

          let rowResult = null;
          try {
            rowResult = await Promise.race([processRowPromise, timeoutPromise]);
          } finally {
            if (timeoutId) clearTimeout(timeoutId);
          }

          if (rowResult && rowResult.skipLoop) {
            if (rowResult.cooldown && rowResult.cooldown > 0) {
              this.hud.setStatus(`COOLDOWN (${(rowResult.cooldown / 1000).toFixed(1)}s)`, 'cooldown');
              await sleep(rowResult.cooldown);
              this.hud.setStatus('RUNNING', 'running');
            }
            continue;
          }
        } catch (err) {
          if (err && err.message === 'ABORT_SIGNAL') throw err;
          if (err && err.message === 'ROW_TIMEOUT_EXCEEDED') {
            this.hud.log('WARN', 'تجاوزت المحادثة الحد الزمني الأقصى (8s). تخطي إجباري لحماية المحرك...');
            try {
              window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }));
              releaseChatFocus();
            } catch (_) {}
            if (targetContactKey) state.skippedRows.add(targetContactKey);
            if (contactKey) state.skippedRows.add(contactKey);
            if (rowFingerprint) {
              state.skippedRows.add(rowFingerprint);
              pruneLRUCache(state.skippedRows, 350, 100);
            }
            continue;
          }

          this.hud.log('WARN', `تخطي استثنائي للمحادثة الحالية لتفادي التجمد: ${err?.message || err}`);
          try {
            window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }));
            releaseChatFocus();
          } catch (_) {}
          if (contactKey) state.processedContacts.add(contactKey);
          if (rowFingerprint) {
            state.processedSnapshots.add(rowFingerprint);
            pruneLRUCache(state.processedSnapshots, 350, 100);
          }
        } finally {
          // STEP 6: Guaranteed Cleanup & Focus Blur
          this.clearActiveRowHighlight(targetRow);
          try {
            releaseChatFocus();
          } catch (_) {}
        }

        // Auto-scroll sidebar if nearing the bottom
        if (selectedIndex >= rows.length - 2) {
          const sidebar = DOM.getSidebarScrollContainer();
          if (sidebar) {
            this.hud.log('SCROLL', 'التمرير التلقائي للقائمة الجانبية لإظهار محادثات إضافية (scrollBy 220px)...');
            sidebar.scrollBy({ top: 220, behavior: 'smooth' });
          }
        }

        // Periodic LRU cache guard
        pruneLRUCache(state.lastRepliedSnippets, 350, 100);
        pruneLRUCache(state.processedSnapshots, 350, 100);

        const cooldown = randomRange(state.config.minCooldown, state.config.maxCooldown);
        this.hud.setStatus(`COOLDOWN (${(cooldown / 1000).toFixed(1)}s)`, 'cooldown');
        this.hud.log('INFO', `تهدئة بشرية: انتظار ${(cooldown / 1000).toFixed(1)} ثانية...`);
        await sleep(cooldown);
        this.hud.setStatus('RUNNING', 'running');
      }
    },

    async executeBranchB(contactKey, rowFingerprint, targetRow) {
      if (contactKey) state.processedContacts.add(contactKey);
      if (rowFingerprint) {
        state.processedSnapshots.add(rowFingerprint);
        pruneLRUCache(state.processedSnapshots, 350, 100);
      }

      await sleep(randomRange(150, 250));
      const restored = await DOM.executeRestoreToUnread(this.hud, targetRow, contactKey);

      if (restored) {
        state.stats.unreadRestored++;
        this.hud.updateStats();
        this.hud.log('UNREAD', '[UNREAD] تم تمييز المحادثة كغير مقروءة بنجاح.');
      } else {
        this.hud.log('WARN', 'تعذر تأكيد استعادة حالة غير مقروء للمحادثة في شريط الأدوات أو القائمة المنسدلة.');
      }
    }
  };

  // Expose global handles
  window.__MBS_AUTOMATOR_HUD__ = new AutomatorHUD();
  window.__MBS_AUTOMATOR_ORCHESTRATOR__ = Orchestrator;
  Orchestrator.init(window.__MBS_AUTOMATOR_HUD__);

  window.__MBS_AUTOMATOR_START__ = () => Orchestrator.start();
  window.__MBS_AUTOMATOR_STOP__ = () => Orchestrator.stop();
  window.__MBS_AUTOMATOR_GET_TENANT__ = () => state.currentTenantId;
  window.__MBS_AUTOMATOR_REHYDRATE__ = () => checkAndRehydrateTenant(window.__MBS_AUTOMATOR_HUD__);
  window.__MBS_AUTOMATOR_SET_RULES__ = (rulesJson) => {
    try {
      state.rules = JSON.parse(rulesJson);
      saveRules();
      window.__MBS_AUTOMATOR_HUD__.renderRulesList();
    } catch (_) {}
  };
  window.__MBS_AUTOMATOR_SET_CONFIG__ = (configJson) => {
    try {
      state.config = { ...state.config, ...JSON.parse(configJson) };
      saveConfig();
    } catch (_) {}
  };

  console.log('[MBS Automator V5.2.0] Initialized successfully (Apple Prismatic Liquid Glass Edition).');
})();

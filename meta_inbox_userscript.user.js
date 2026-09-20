// ==UserScript==
// @name         Meta Business Suite Inbox Auto-Responder & Unread Restorer (Enterprise V6.5.4)
// @namespace    https://github.com/meta-suite-automation/tampermonkey
// @version      6.5.4
// @description  V6.5.4-ENTERPRISE: Production Hardening, Concurrency Protection, Multiline Editor & Authoritative Conflict Resolution.
// @author       Bishoy Safwat
// @match        https://business.facebook.com/latest/inbox/*
// @match        https://business.facebook.com/latest/inbox/all*
// @icon         https://www.facebook.com/favicon.ico
// @grant        none
// @run-at       document-idle
// ==/UserScript==

/**
 * ============================================================================
 * META BUSINESS SUITE INBOX AUTOMATOR (ENTERPRISE PRODUCTION RELEASE V6.5.4)
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

  if (window.__MBS_AUTOMATOR_V654_LOADED__ || window.__MBS_AUTOMATOR_V652_LOADED__ || window.__MBS_AUTOMATOR_V651_LOADED__ || window.__MBS_AUTOMATOR_V650_LOADED__ || window.__MBS_AUTOMATOR_V641_LOADED__ || window.__MBS_AUTOMATOR_V640_LOADED__ || window.__MBS_AUTOMATOR_V639_LOADED__ || window.__MBS_AUTOMATOR_V638_LOADED__) {
    console.log('[MBS Automator] Already mounted. Re-initializing HUD...');
    if (window.__MBS_AUTOMATOR_HUD__) {
      window.__MBS_AUTOMATOR_HUD__.init();
    }
    return;
  }
  window.__MBS_AUTOMATOR_V654_LOADED__ = true;
  window.__MBS_AUTOMATOR_V652_LOADED__ = true;
  window.__MBS_AUTOMATOR_V651_LOADED__ = true;
  window.__MBS_AUTOMATOR_V650_LOADED__ = true;
  window.__MBS_AUTOMATOR_V641_LOADED__ = true;

  class FocusIntegrityError extends Error {
    constructor(message) {
      super(message);
      this.name = 'FocusIntegrityError';
    }
  }

  // ---------------------------------------------------------------------------
  // [P0-DOM-01] DUAL-LAYER DRAFT OWNERSHIP — WeakMap (in-session) + sessionStorage (reload-safe)
  // Survives soft tab reloads within a 60-second TTL so clearStaleComposerDraft never
  // misclassifies the bot's own partially-typed text as a human agent draft.
  // ---------------------------------------------------------------------------
  const botDraftOwnership = new WeakMap();
  const BOT_DRAFT_SS_PREFIX = '__MBS_DRAFT_';

  function claimBotDraft(composer, threadKey, text) {
    // Primary: in-memory WeakMap for current session
    botDraftOwnership.set(composer, { threadKey, text, timestamp: Date.now() });
    // Secondary: sessionStorage TTL record for reload recovery
    try {
      const fallbackKey = (typeof DOM !== 'undefined' && typeof DOM.getActiveChatContactName === 'function' ? DOM.getActiveChatContactName() : '') || 'unidentified_thread';
      const key = BOT_DRAFT_SS_PREFIX + (threadKey || fallbackKey);
      sessionStorage.setItem(key, JSON.stringify({
        text: typeof text === 'string' ? text.slice(0, 120) : '',
        expires: Date.now() + 60000
      }));
    } catch (_) {}
  }

  function getBotDraftOwnership(composer, threadKey) {
    // Fast path: in-memory WeakMap
    const inMem = botDraftOwnership.get(composer);
    if (inMem) return inMem;
    // Reload-recovery path: sessionStorage
    try {
      const fallbackKey = (typeof DOM !== 'undefined' && typeof DOM.getActiveChatContactName === 'function' ? DOM.getActiveChatContactName() : '') || 'unidentified_thread';
      const key = BOT_DRAFT_SS_PREFIX + (threadKey || fallbackKey);
      const raw = sessionStorage.getItem(key);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed.expires === 'number' && Date.now() < parsed.expires) {
          return { threadKey, text: parsed.text || '', timestamp: parsed.expires - 60000, reloaded: true };
        }
        sessionStorage.removeItem(key); // expired — purge
      }
    } catch (_) {}
    return undefined;
  }

  function clearBotDraftSessionRecord(threadKey) {
    try {
      const fallbackKey = (typeof DOM !== 'undefined' && typeof DOM.getActiveChatContactName === 'function' ? DOM.getActiveChatContactName() : '') || 'unidentified_thread';
      sessionStorage.removeItem(BOT_DRAFT_SS_PREFIX + (threadKey || fallbackKey));
    } catch (_) {}
  }

  class TTLMap {
    constructor(maxEntries = 2000, defaultTtlMs = 600000) {
      this.maxEntries = maxEntries;
      this.defaultTtlMs = defaultTtlMs;
      this.map = new Map();
      this.lastPrune = Date.now();
    }

    set(key, value, ttlMs = null) {
      const now = Date.now();
      // [P1-PERF-01] Amortized eviction: avoid full O(N) scan on every single insertion
      if (this.map.size >= this.maxEntries || (now - this.lastPrune > 15000)) {
        this.evictExpired();
        this.lastPrune = now;
      }
      if (this.map.size >= this.maxEntries) {
        const oldestKey = this.map.keys().next().value;
        if (oldestKey !== undefined) this.map.delete(oldestKey);
      }
      const duration = (typeof ttlMs === 'number' && ttlMs > 0) ? ttlMs : this.defaultTtlMs;
      let expires;
      if (typeof value === 'number' && value > now) {
        expires = value;
      } else {
        expires = now + duration;
      }
      this.map.set(key, { value, expires });
      return this;
    }

    get(key) {
      const entry = this.map.get(key);
      if (!entry) return undefined;
      if (Date.now() > entry.expires) {
        this.map.delete(key);
        return undefined;
      }
      return entry.value;
    }

    has(key) {
      return this.get(key) !== undefined;
    }

    delete(key) {
      return this.map.delete(key);
    }

    clear() {
      this.map.clear();
    }

    get size() {
      this.evictExpired();
      return this.map.size;
    }

    *keys() {
      this.evictExpired();
      for (const [key, entry] of this.map.entries()) {
        if (Date.now() <= entry.expires) yield key;
      }
    }

    evictExpired() {
      const now = Date.now();
      for (const [key, entry] of this.map.entries()) {
        if (now > entry.expires) {
          this.map.delete(key);
        }
      }
    }
  }

  class RegexSandbox {
    constructor(timeoutMs = 30) {
      this.timeoutMs = timeoutMs;
      this.seq = 0;
      this.pending = new Map();
      this.worker = null;
      try {
        this.#spawn();
      } catch (e) {
        console.warn('[MBS Automator] CSP prevented Worker creation. Using safe inline evaluation.', e);
        this.worker = null;
      }
    }

    #spawn() {
      if (typeof window === 'undefined' || typeof Worker === 'undefined' || typeof Blob === 'undefined') {
        this.worker = null;
        return;
      }
      try {
        const workerCode = `
          self.onmessage = function(e) {
            const { id, pattern, flags, text } = e.data;
            try {
              const re = new RegExp(pattern, flags);
              const matched = re.test(text);
              self.postMessage({ id, success: true, matched });
            } catch (err) {
              self.postMessage({ id, success: false, error: err.message });
            }
          };
        `;
        const blob = new Blob([workerCode], { type: 'application/javascript' });
        const url = URL.createObjectURL(blob);
        try {
          this.worker = new Worker(url);
        } finally {
          try { URL.revokeObjectURL(url); } catch (_) {}
        }

        this.worker.onmessage = (e) => {
          const { id, success, matched, error } = e.data;
          const req = this.pending.get(id);
          if (req) {
            this.pending.delete(id);
            clearTimeout(req.timer);
            if (success) {
              req.resolve(Boolean(matched));
            } else {
              req.resolve(false);
            }
          }
        };

        this.worker.onerror = (err) => {
          console.warn('[MBS Automator] Regex Worker error/CSP denial. Regex match failed closed.', err);
          try { if (this.worker) this.worker.terminate(); } catch (_) {}
          this.worker = null;
          this.terminatePending();
        };
      } catch (e) {
        console.warn('[MBS Automator] CSP prevented Worker creation. Regex match failed closed.', e);
        this.worker = null;
      }
    }

    terminatePending() {
      for (const req of this.pending.values()) {
        clearTimeout(req.timer);
        if (typeof req.resolve === 'function') {
          req.resolve(false);
        }
      }
      this.pending.clear();
    }

    async test(pattern, flags, text, timeoutMs = null) {
      if (!this.worker) {
        return false;
      }

      const id = ++this.seq;
      const timeout = timeoutMs || this.timeoutMs;

      return new Promise((resolve) => {
        const timer = setTimeout(() => {
          this.pending.delete(id);
          try {
            if (this.worker) this.worker.terminate();
          } catch (_) {}
          this.worker = null;
          this.terminatePending();
          try {
            this.#spawn();
          } catch (_) {}
          console.warn('[MBS RegexSandbox] تجاوز التعبير النمطي مهلة Worker (30ms). الإبلاغ الآمن بعدم التطابق (false). [REGEX HAZARD]');
          resolve(false);
        }, timeout);

        this.pending.set(id, { resolve, timer });

        try {
          this.worker.postMessage({ id, pattern, flags, text });
        } catch (_) {
          clearTimeout(timer);
          this.pending.delete(id);
          try { if (this.worker) this.worker.terminate(); } catch (_) {}
          this.worker = null;
          this.terminatePending();
          try { this.#spawn(); } catch (_) {}
          resolve(false);
        }
      });
    }
  }

  const regexSandbox = new RegexSandbox();

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
    if (collection instanceof TTLMap) {
      collection.evictExpired();
      return;
    }
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
      keywords: ['سعر', 'كام', 'بكام', 'اسعار', 'تكلفة', 'تفاصيل', 'التفاصيل'],
      keyword: 'سعر,كام,بكام,اسعار,تكلفة,تفاصيل,التفاصيل',
      reply: 'أهلاً بك! تفاصيل الأسعار والعروض متاحة لدينا الآن، يسعدنا تواصلك وسنوافيك بالتفاصيل فوراً.',
      matchType: 'ultra_exact',
      active: true
    },
    {
      id: 'rule_location',
      keywords: ['مكان', 'عنوان', 'الفرع', 'لوكيشن', 'موقع', 'فين', 'عناوين'],
      keyword: 'مكان,عنوان,الفرع,لوكيشن,موقع,فين,عناوين',
      reply: 'أهلاً بك! فرعنا متاح لخدمتك دائماً. يمكنك معرفة أقرب موقع والتواصل عبر الرابط أو الرسائل هنا.',
      matchType: 'ultra_exact',
      active: true
    },
    {
      id: 'rule_phone',
      keywords: ['فون', 'تليفون', 'رقم', 'واتس', 'واتساب', 'موبايل'],
      keyword: 'فون,تليفون,رقم,واتس,واتساب,موبايل',
      reply: 'أهلاً بك! رقم خدمة العملاء والواتساب متاح لمساعدتك على مدار الساعة، تفضل بالاستفسار في أي وقت.',
      matchType: 'ultra_exact',
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
    lastHeartbeat: Date.now(),
    currentIndex: 0,
    currentTenantId: getActiveTenantId(),
    rules: loadRules(),
    config: loadConfig(),
    chatCooldowns: new TTLMap(2000, 2 * 60 * 1000), // contactKey -> expiryTimestamp (2000 max, 2 min TTL)
    lastSeenSnippets: new TTLMap(2000, 30 * 60 * 1000), // contactKey -> latestSnippet (2000 max, 30 min TTL)
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
      const { rulesKey } = getTenantStorageKeys();

      // 1. Python / Supervisor seed MUST take absolute precedence over localStorage
      if (typeof window !== 'undefined' && window.__INITIAL_RULES__ !== undefined && Array.isArray(window.__INITIAL_RULES__)) {
        const initialRules = JSON.parse(JSON.stringify(window.__INITIAL_RULES__));
        try {
          localStorage.setItem(rulesKey, JSON.stringify(initialRules));
        } catch (_) {}
        return initialRules;
      }

      // 2. Fallback to localStorage (e.g. standalone UserScript mode without Python host)
      const raw = localStorage.getItem(rulesKey);
      if (raw !== null) {
        try {
          const parsed = JSON.parse(raw);
          if (Array.isArray(parsed)) {
            return parsed;
          }
        } catch (_) {}
      }

      // 3. Clean fallback to default rules
      const clonedDefaults = JSON.parse(JSON.stringify(defaultRules));
      try {
        localStorage.setItem(rulesKey, JSON.stringify(clonedDefaults));
      } catch (_) {}
      return clonedDefaults;
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
        window.pySaveConfig(JSON.stringify(state.rules), JSON.stringify(state.config), window.__CONFIG_SHA256__ || '').then((res) => {
          if (res && res.sha256_token) {
            window.__CONFIG_SHA256__ = res.sha256_token;
          }
        }).catch(() => {});
      }
    }, 400);
  }

  function loadConfig() {
    let cfg = { ...defaultConfig };
    try {
      const { configKey } = getTenantStorageKeys();
      // 1. Prioritize localStorage for this specific tenant
      const data = localStorage.getItem(configKey);
      if (data !== null) {
        const parsed = JSON.parse(data);
        if (parsed && typeof parsed === 'object') {
          if (window.__INITIAL_CONFIG__) {
            try { delete window.__INITIAL_CONFIG__; } catch (_) {}
          }
          cfg = { ...defaultConfig, ...parsed };
          cfg.typingSpeed = cfg.typingSpeed || Math.round(((cfg.minTypingSpeed || 35) + (cfg.maxTypingSpeed || 65)) / 2) || 45;
          return cfg;
        }
      }

      // 2. If no config exists in localStorage, check injected seed from Python
      if (window.__INITIAL_CONFIG__ && typeof window.__INITIAL_CONFIG__ === 'object') {
        const initialCfg = { ...defaultConfig, ...window.__INITIAL_CONFIG__ };
        try { delete window.__INITIAL_CONFIG__; } catch (_) {}
        try {
          localStorage.setItem(configKey, JSON.stringify(initialCfg));
        } catch (_) {}
        initialCfg.typingSpeed = initialCfg.typingSpeed || Math.round(((initialCfg.minTypingSpeed || 35) + (initialCfg.maxTypingSpeed || 65)) / 2) || 45;
        return initialCfg;
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
        window.pySaveConfig(JSON.stringify(state.rules), JSON.stringify(state.config), window.__CONFIG_SHA256__ || '').then((res) => {
          if (res && res.sha256_token) {
            window.__CONFIG_SHA256__ = res.sha256_token;
          }
        }).catch(() => {});
      }
    }, 400);
  }

  function checkAndRehydrateTenant(hud) {
    const latestTenantId = getActiveTenantId();
    if (latestTenantId !== state.currentTenantId) {
      const prevTenantId = state.currentTenantId;
      state.currentTenantId = latestTenantId;
      // Clear thread & contact tracking sets and flush skipped rows for clean transition between pages
      state.processedContacts.clear();
      state.processedSnapshots.clear();
      state.lastRepliedSnippets.clear();
      if (state.chatCooldowns) state.chatCooldowns.clear();
      if (state.lastSeenSnippets) state.lastSeenSnippets.clear();
      if (state.skippedRows) state.skippedRows.clear();

      // Reset statistics counters for the new page context
      state.stats = {
        evaluated: 0,
        matched: 0,
        unreadRestored: 0,
        skippedOutbound: 0,
        errors: 0
      };

      state.rules = loadRules();
      state.config = loadConfig();

      if (hud) {
        hud.updateTenantUI(latestTenantId);
        hud.renderRulesList();
        hud.updateConfigUI();
        hud.updateStats();
        hud.log('INFO', `[Page] تم تبديل الصفحة النشطة (Page Switch: [${prevTenantId}] ➔ [${latestTenantId}]). تم تصفير الكاش وإعادة تحميل القواعد والإعدادات تلقائياً.`);
      }
      return true;
    }
    return false;
  }

  // ---------------------------------------------------------------------------
  // 2. ARABIC TEXT NORMALIZATION & KEYWORD MATCHING
  // ---------------------------------------------------------------------------
  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function escapeRegExp(string) {
    if (!string || typeof string !== 'string') return '';
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function normalizeArabicText(text) {
    const caseFold = arguments.length > 1 ? Boolean(arguments[1]) : true;
    if (!text || typeof text !== 'string') return '';
    const easternDigits = ['٠','١','٢','٣','٤','٥','٦','٧','٨','٩'];
    let res = text
      // [P2-NLP-01] Step 1: Strip Tashkeel & Tatweel BEFORE toLowerCase to avoid casing ops on diacritic positions
      .replace(/[\u0640\u064B-\u065F\u0670]/g, '')
      // Step 2: Normalize eastern digits
      .replace(/[٠-٩]/g, d => easternDigits.indexOf(d))
      // [P2-NLP-01] Step 3: Separate emoji/flags BEFORE toLowerCase to preserve Regional Indicator surrogate pairs
      .replace(/([\p{L}\p{N}])([\p{So}\u{1F1E6}-\u{1F1FF}])/gu, '$1 $2')
      .replace(/([\p{So}\u{1F1E6}-\u{1F1FF}])([\p{L}\p{N}])/gu, '$1 $2');

    if (caseFold) {
      res = res.toLowerCase();
    }

    return res
      // Step 5: Unify Arabic character variants
      .replace(/[أإآ]/g, 'ا')
      .replace(/[ة]/g, 'ه')
      .replace(/[ى]/g, 'ي')
      .replace(/[ؤئ]/g, 'ء')
      // Step 6: Whitelist filter — preserve ZWJ/ZWNJ (\u200C و \u200D) لسلامة الإيموجي المركب
      .replace(/[^\u0600-\u06FFa-zA-Z0-9\s\u{1F1E6}-\u{1F1FF}\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE00}-\u{FE0F}\u200C\u200D/:.?=&_*-]/gu, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  let lastInvalidModeWarningTime = 0;
  function warnInvalidMode(mode) {
    const now = Date.now();
    if (now - lastInvalidModeWarningTime > 15000) {
      lastInvalidModeWarningTime = now;
      console.warn(`[MBS Automator] Unsupported matchType '${mode}'. Rule evaluation failed closed.`);
    }
  }

  async function testKeywordsMatch(text, normText, rawKeywords, matchType, caseSensitive = false) {
    if (!text || typeof text !== 'string' || !Array.isArray(rawKeywords) || rawKeywords.length === 0) return null;
    const mType = (matchType === undefined || matchType === null) ? 'ultra_exact' : matchType;

    switch (mType) {
      case 'ultra_exact': {
        for (const kw of rawKeywords) {
          if (typeof kw !== 'string' || kw.length === 0 || kw.trim().length === 0) continue;
          if (text === kw) {
            return { matched: true, matchedKeyword: kw };
          }
        }
        return null;
      }

      case 'contains': {
        const caseFold = !caseSensitive;
        const effectiveNormText = (normText && !caseSensitive) ? normText : normalizeArabicText(text, caseFold);
        for (const kw of rawKeywords) {
          if (!kw || typeof kw !== 'string' || kw.trim().length === 0) continue;
          const cleanKw = kw.trim();
          const normKw = normalizeArabicText(cleanKw, caseFold);
          if (!normKw && !cleanKw) continue;

          if (caseSensitive) {
            if (normKw && effectiveNormText && effectiveNormText.includes(normKw)) {
              return { matched: true, matchedKeyword: kw };
            }
            if (cleanKw && text.includes(cleanKw)) {
              return { matched: true, matchedKeyword: kw };
            }
          } else {
            if (normKw && effectiveNormText && effectiveNormText.toLowerCase().includes(normKw.toLowerCase())) {
              return { matched: true, matchedKeyword: kw };
            }
            if (cleanKw && text.toLowerCase().includes(cleanKw.toLowerCase())) {
              return { matched: true, matchedKeyword: kw };
            }
          }
        }
        return null;
      }

      case 'exact':
      case 'word': {
        const caseFold = !caseSensitive;
        const effectiveNormText = (normText && !caseSensitive) ? normText : normalizeArabicText(text, caseFold);
        const flags = caseSensitive ? 'u' : 'iu';
        for (const kw of rawKeywords) {
          if (!kw || typeof kw !== 'string' || kw.trim().length === 0) continue;
          const cleanKw = kw.trim();
          const normKw = normalizeArabicText(cleanKw, caseFold);
          if (!normKw && !cleanKw) continue;

          // 1. Unicode word boundary check against normalized text (without optional "ال" fuzziness)
          if (normKw && effectiveNormText) {
            const boundaryRegex = new RegExp(
              '(?:^|[^\\p{L}\\p{N}\\p{M}])' + escapeRegExp(normKw) + '(?=$|[^\\p{L}\\p{N}\\p{M}])',
              flags
            );
            if (boundaryRegex.test(effectiveNormText)) {
              return { matched: true, matchedKeyword: kw };
            }
          }

          // 2. Raw boundary check (essential for emoji / flag sequences or raw symbols)
          const rawBoundaryRegex = new RegExp(
            '(?:^|[^\\p{L}\\p{N}\\p{M}])' + escapeRegExp(cleanKw) + '(?=$|[^\\p{L}\\p{N}\\p{M}])',
            flags
          );
          if (rawBoundaryRegex.test(text)) {
            return { matched: true, matchedKeyword: kw };
          }
        }
        return null;
      }

      case 'regex': {
        const flags = caseSensitive ? 'u' : 'iu';
        for (const kw of rawKeywords) {
          if (!kw || typeof kw !== 'string' || kw.length === 0) continue;
          try {
            const matched = await regexSandbox.test(kw, flags, text, 30);
            if (matched) {
              return { matched: true, matchedKeyword: kw };
            }
          } catch (_) {
            continue;
          }
        }
        return null;
      }

      default: {
        try {
          if (typeof warnInvalidMode === 'function') {
            warnInvalidMode(mType);
          } else {
            console.warn(`[MBS Automator] Unsupported matchType '${mType}'. Rule evaluation failed closed.`);
          }
        } catch (_) {}
        return null;
      }
    }
  }

  async function evaluateActiveRules(text, rules, contextText = '') {
    if (!text || typeof text !== 'string' || !Array.isArray(rules) || rules.length === 0) return null;
    const normMsg = normalizeArabicText(text);
    const normContext = contextText ? normalizeArabicText(contextText) : '';

    const getRuleKeywords = (rule) => {
      if (Array.isArray(rule.keywords)) {
        return rule.keywords.filter(k => typeof k === 'string' && k.length > 0);
      } else if (typeof rule.keyword === 'string' && rule.keyword.trim()) {
        return rule.keyword.split(/[,،\n]+/).map(k => k.trim()).filter(Boolean);
      }
      return [];
    };

    const getRuleContextKeywords = (rule) => {
      if (Array.isArray(rule.contextKeywords)) {
        return rule.contextKeywords.filter(k => typeof k === 'string' && k.length > 0);
      } else if (typeof rule.contextKeyword === 'string' && rule.contextKeyword.trim()) {
        return rule.contextKeyword.split(/[,،\n]+/).map(k => k.trim()).filter(Boolean);
      }
      return [];
    };

    const activeRules = rules.filter(r => r && r.active && r.reply);
    const compoundRules = [];
    const genericRules = [];

    for (const rule of activeRules) {
      const cKws = getRuleContextKeywords(rule);
      if (cKws.length > 0) {
        compoundRules.push({ rule, contextKeywords: cKws });
      } else {
        genericRules.push(rule);
      }
    }

    // =========================================================================
    // PASS 1: Compound Ad-Context Priority
    // Evaluates rules requiring BOTH context match and customer keyword match
    // =========================================================================
    if (contextText && compoundRules.length > 0) {
      for (const { rule, contextKeywords } of compoundRules) {
        const rawKeywords = getRuleKeywords(rule);
        if (rawKeywords.length === 0) continue;

        // Condition 1: Context Match
        const contextMatch = await testKeywordsMatch(
          contextText,
          normContext,
          contextKeywords,
          rule.contextMatchType || 'contains',
          rule.caseSensitive
        );
        if (!contextMatch) continue;

        // Condition 2: Customer Trigger Match
        const keywordMatch = await testKeywordsMatch(
          text,
          normMsg,
          rawKeywords,
          rule.matchType,
          rule.caseSensitive
        );
        if (keywordMatch) {
          console.log(`[MBS Rules] [COMPOUND MATCH] Rule '${rule.id || 'unnamed'}' matched keyword: "${keywordMatch.matchedKeyword}" with context: "${contextMatch.matchedKeyword}"`);
          return {
            rule,
            matchedKeyword: keywordMatch.matchedKeyword,
            matchedContextKeyword: contextMatch.matchedKeyword,
            isCompound: true
          };
        }
      }
    }

    // =========================================================================
    // PASS 2: Generic Fallback Rules
    // Evaluates single-condition rules based solely on customer trigger text
    // =========================================================================
    for (const rule of genericRules) {
      const rawKeywords = getRuleKeywords(rule);
      if (rawKeywords.length === 0) continue;

      const keywordMatch = await testKeywordsMatch(
        text,
        normMsg,
        rawKeywords,
        rule.matchType,
        rule.caseSensitive
      );
      if (keywordMatch) {
        return {
          rule,
          matchedKeyword: keywordMatch.matchedKeyword,
          isCompound: false
        };
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

  function cancellableSleep(ms, cancellationToken = null) {
    if (state.emergencyAbort) {
      return Promise.reject(new Error('ABORT_SIGNAL'));
    }
    if (cancellationToken?.cancelled) {
      return Promise.reject(new Error('ROW_PROCESSING_CANCELLED'));
    }
    return new Promise((resolve, reject) => {
      let timer = null;
      let checkInterval = null;

      const cleanup = () => {
        if (timer) clearTimeout(timer);
        if (checkInterval) clearInterval(checkInterval);
        activeSleepRejectors.delete(rejector);
      };

      const rejector = (err) => {
        cleanup();
        reject(err || new Error('ABORT_SIGNAL'));
      };

      if (cancellationToken) {
        checkInterval = setInterval(() => {
          if (cancellationToken.cancelled) {
            cleanup();
            reject(new Error('ROW_PROCESSING_CANCELLED'));
          }
        }, 20);
      }

      timer = setTimeout(() => {
        cleanup();
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
    extractTextWithAlt(node, depth = 0) {
      if (!node || depth > 30) return '';
      if (node.nodeType === 3) return node.nodeValue || '';
      if (node.nodeType === 1) {
        // [P1-DOM-01] Exclude avatar elements, reaction popups, media players, and link preview cards
        // [P2-DOM-02] Added link preview card selectors to prevent OG-title text from polluting message extraction
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
          if (isEmoji) {
            return node.getAttribute('alt') || node.getAttribute('aria-label') || '';
          }
          return '';
        }
        if (tagName === 'BR') {
          return '\n';
        }
        if (node.getAttribute('role') === 'img' && node.getAttribute('aria-label') && !node.firstChild) {
          const aria = node.getAttribute('aria-label') || '';
          if (/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test(aria)) {
            return aria;
          }
          return '';
        }
        let out = '';
        const isBlock = /^(DIV|P|LI|TR|H[1-6])$/.test(tagName);
        for (let child = node.firstChild; child; child = child.nextSibling) {
          out += (this && typeof this.extractTextWithAlt === 'function')
            ? this.extractTextWithAlt(child, depth + 1)
            : DOM.extractTextWithAlt(child, depth + 1);
        }
        return isBlock ? ` ${out} ` : out;
      }
      return '';
    },

    extractMessageTextVerbatim(node, depth = 0) {
      if (!node) return '';
      if (depth > 50) return null;
      if (node.nodeType === 3) return node.nodeValue || '';
      if (node.nodeType === 1) {
        if (node.matches && node.matches(
          '[aria-label*="Profile" i], [aria-label*="صورة الملف" i], [aria-label*="ملف شخصي" i], ' +
          '[data-testid*="reaction" i], [role="progressbar"], audio, video, svg, ' +
          '[data-testid*="link_preview" i], [data-testid*="messenger_link_preview" i], ' +
          'a[role="link"] > div, div[role="article"], .preview-card, [role="button"]'
        )) {
          return '';
        }
        const tagName = node.tagName;
        if (tagName === 'IMG') {
          const isEmoji = (node.classList && node.classList.contains('emoji')) ||
            (node.getAttribute('src') || '').includes('emoji.php') ||
            (node.getAttribute('src') || '').includes('/emoji/') ||
            (node.getAttribute('alt') && /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test(node.getAttribute('alt')));
          if (isEmoji) {
            return node.getAttribute('alt') || node.getAttribute('aria-label') || '';
          }
          return '';
        }
        if (tagName === 'BR') {
          return '\n';
        }
        if (node.getAttribute('role') === 'img' && node.getAttribute('aria-label') && !node.firstChild) {
          const aria = node.getAttribute('aria-label') || '';
          if (/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test(aria)) {
            return aria;
          }
          return '';
        }
        let out = '';
        for (let child = node.firstChild; child; child = child.nextSibling) {
          const cText = (this && typeof this.extractMessageTextVerbatim === 'function')
            ? this.extractMessageTextVerbatim(child, depth + 1)
            : DOM.extractMessageTextVerbatim(child, depth + 1);
          if (cText === null) return null;
          out += cText;
        }
        return out;
      }
      return '';
    },

    sendEscape() {
      try {
        // [P1-STATE-01] Dispatch Escape to activeElement, document, and window for React portal dismissal
        const opts = { key: 'Escape', code: 'Escape', keyCode: 27, which: 27, bubbles: true, cancelable: true, view: window };
        if (document.activeElement && document.activeElement !== document.body) {
          document.activeElement.dispatchEvent(new KeyboardEvent('keydown', opts));
          document.activeElement.dispatchEvent(new KeyboardEvent('keyup', opts));
          if (typeof document.activeElement.blur === 'function') {
            document.activeElement.blur();
          }
        }
        document.dispatchEvent(new KeyboardEvent('keydown', opts));
        document.dispatchEvent(new KeyboardEvent('keyup', opts));
        window.dispatchEvent(new KeyboardEvent('keydown', opts));
        window.dispatchEvent(new KeyboardEvent('keyup', opts));
      } catch (_) {}
    },

    getActiveThreadKey() {
      try {
        if (typeof window !== 'undefined' && window.location) {
          const url = new URL(window.location.href);
          const selId = url.searchParams.get('selected_item_id');
          if (selId) return `id_${selId}`;
          const matchPath = url.pathname.match(/\/inbox\/(?:all\/)?([0-9]+)/);
          if (matchPath) return `id_${matchPath[1]}`;
        }
      } catch (_) {}

      try {
        const selectedRow = document.querySelector('[aria-selected="true"], [data-thread-id][aria-selected="true"], [data-selected="true"]');
        if (selectedRow) {
          const threadId = selectedRow.getAttribute('data-thread-id');
          if (threadId) return `thread_${threadId}`;
          const key = this.getStableRowKey(selectedRow);
          if (key) return key;
        }
      } catch (_) {}

      try {
        const headerName = this.getActiveChatContactName();
        if (headerName) return `contact_${normalizeArabicText(this.sanitizeName(headerName))}`;
      } catch (_) {}

      return null;
    },

    extractConversationIdFromHref(href) {
      if (!href || typeof href !== 'string') return null;

      try {
        const url = new URL(href, window.location.href);
        const selectedId = url.searchParams.get('selected_item_id');
        if (selectedId) return selectedId;

        const threadId = url.searchParams.get('thread_id');
        if (threadId) return threadId;
      } catch (_) {}

      const selectedMatch = href.match(
        /(?:selected_item_id|thread_id)=([0-9a-zA-Z_-]+)/
      );
      if (selectedMatch) return selectedMatch[1];

      const pathMatch = href.match(
        /\/inbox\/(?:all\/|messenger\/|instagram\/|whatsapp\/)?([0-9a-zA-Z_-]+)/
      );
      if (pathMatch && !['all', 'messenger', 'instagram', 'whatsapp'].includes(pathMatch[1])) {
        return pathMatch[1];
      }
      return null;
    },

    detectChannel(target) {
      if (!target) return null;
      let text = '';
      if (typeof target === 'string') {
        text = target;
      } else if (target instanceof Element || target?.nodeType === 1) {
        text = [
          target.getAttribute('data-platform') || '',
          target.getAttribute('data-channel') || '',
          target.getAttribute('href') || '',
          target.getAttribute('aria-label') || '',
          target.className || '',
          target.innerText || target.textContent || ''
        ].join(' ');
      }
      const lower = text.toLowerCase();
      if (lower.includes('whatsapp') || lower.includes('واتساب') || lower.includes('واتس')) return 'whatsapp';
      if (lower.includes('instagram') || lower.includes('إنستغرام') || lower.includes('انستغرام') || lower.includes('انستقرام')) return 'instagram';
      if (lower.includes('messenger') || lower.includes('ماسينجر') || lower.includes('مسنجر')) return 'messenger';
      return null;
    },

    getSurfaceFingerprint(canvas) {
      if (!canvas) return '';
      const childCount = canvas.querySelectorAll('*').length;
      const scrollHeight = canvas.scrollHeight || 0;
      const textSample = (canvas.innerText || canvas.textContent || '').slice(0, 120).replace(/\s+/g, ' ').trim();
      return `${childCount}_${scrollHeight}_${textSample}`;
    },

    captureExpectedConversation(targetRow, contactName = null) {
      if (!targetRow || !targetRow.isConnected) {
        return Object.freeze({
          valid: false,
          reason: targetRow ? 'TARGET_ROW_NOT_CONNECTED' : 'TARGET_ROW_MISSING',
          targetRow: null,
          strongId: null,
          selectedAttributeId: null,
          selectedHrefId: null,
          selectedRowKey: null,
          rowKey: null,
          cleanName: '',
          normalizedName: '',
          digits: '',
          channel: null,
          ambiguousName: false,
          leaseKey: null
        });
      }

      const cleanName = this.sanitizeName(
        contactName || this.getRowCustomerName(targetRow) || ''
      );
      const normalizedName = normalizeArabicText(cleanName);
      const rawDigits = cleanName.replace(/\D/g, '');
      const digits = rawDigits.length >= 6 ? rawDigits : '';

      const href =
        targetRow.getAttribute('href') ||
        targetRow.querySelector('a[href]')?.getAttribute('href') ||
        '';

      const selectedAttributeId =
        targetRow.getAttribute('data-thread-id') ||
        targetRow.querySelector('[data-thread-id]')?.getAttribute('data-thread-id') ||
        null;

      const selectedHrefId = this.extractConversationIdFromHref(href);

      const strongId =
        selectedAttributeId ||
        selectedHrefId ||
        null;

      const selectedRowKey = this.getStableRowKey(targetRow);
      const rowKey = selectedRowKey;
      const channel = this.detectChannel(targetRow) || this.detectChannel(href);

      const matchingNameRows = normalizedName
        ? this.getConversationRows().filter(row => {
            const rowName = this.sanitizeName(
              this.getRowCustomerName(row) || ''
            );
            return normalizeArabicText(rowName) === normalizedName;
          }).length
        : 0;

      const ambiguousName = !strongId && matchingNameRows > 1;
      const valid = Boolean(
        strongId ||
        (
          rowKey &&
          normalizedName &&
          !ambiguousName
        ) ||
        (
          rowKey &&
          digits &&
          !ambiguousName
        )
      );

      const leaseKey = strongId
        ? `thread_${strongId}`
        : rowKey || (
            normalizedName
              ? `contact_${normalizedName}`
              : null
          );

      return Object.freeze({
        valid,
        reason: valid
          ? null
          : (
              ambiguousName
                ? 'AMBIGUOUS_CONTACT_NAME_WITHOUT_THREAD_ID'
                : 'TARGET_IDENTITY_INSUFFICIENT'
            ),
        targetRow,
        strongId,
        selectedAttributeId,
        selectedHrefId,
        selectedRowKey,
        rowKey,
        cleanName,
        normalizedName,
        digits,
        channel,
        ambiguousName,
        leaseKey
      });
    },

    getActiveConversationIdentity() {
      const conversationRows = this.getConversationRows();
      let selectedRow = conversationRows.find(row => (
        row.getAttribute('aria-selected') === 'true' ||
        row.getAttribute('data-selected') === 'true' ||
        Boolean(row.querySelector('[aria-selected="true"]'))
      )) || null;

      if (!selectedRow) {
        const candidate = document.querySelector('[aria-selected="true"], [data-selected="true"]');
        if (candidate && !candidate.closest('#mbs-inbox-automator-root')) {
          selectedRow = candidate.closest('[role="row"], [role="listitem"], a[href*="/inbox/"], a[href*="/latest/inbox/"]') || candidate;
        }
      }

      const selectedHref = selectedRow
        ? (
            selectedRow.getAttribute('href') ||
            selectedRow.querySelector('a[href]')?.getAttribute('href') ||
            ''
          )
        : '';

      const selectedAttributeId = selectedRow
        ? (
            selectedRow.getAttribute('data-thread-id') ||
            selectedRow.querySelector('[data-thread-id]')?.getAttribute('data-thread-id') ||
            null
          )
        : null;

      const selectedHrefId = selectedRow
        ? this.extractConversationIdFromHref(selectedHref)
        : null;

      let urlThreadId = null;
      try {
        const url = new URL(window.location.href);
        urlThreadId =
          url.searchParams.get('selected_item_id') ||
          url.searchParams.get('thread_id') ||
          this.extractConversationIdFromHref(window.location.pathname) ||
          null;
      } catch (_) {}

      const selectedRowKey = selectedRow
        ? this.getStableRowKey(selectedRow)
        : null;

      const root = this.getConversationRoot();

      const headerName = this.sanitizeName(
        this.getActiveChatContactName(root) || ''
      );
      const normalizedName = normalizeArabicText(headerName);
      const rawDigits = headerName.replace(/\D/g, '');
      const digits = rawDigits.length >= 6 ? rawDigits : '';

      const channel =
        this.detectChannel(window.location.href) ||
        (selectedRow ? this.detectChannel(selectedRow) : null) ||
        this.detectChannel(headerName) ||
        null;

      let canvasLocalId = null;
      try {
        if (root) {
          const canvasCandidate = root.matches?.('div[data-testid*="chat-canvas" i], div[data-testid*="message-list" i]')
            ? root
            : root.querySelector('div[data-testid*="chat-canvas" i], div[data-testid*="message-list" i], div[aria-label*="محادثة" i], div[aria-label*="Conversation" i]');
          if (canvasCandidate) {
            canvasLocalId =
              canvasCandidate.getAttribute('data-thread-id') ||
              canvasCandidate.getAttribute('data-canvas-id') ||
              canvasCandidate.querySelector('[data-thread-id]')?.getAttribute('data-thread-id') ||
              null;
          }
        }
      } catch (_) {}

      const strongId =
        selectedAttributeId ||
        selectedHrefId ||
        urlThreadId ||
        canvasLocalId ||
        null;

      return {
        selectedAttributeId,
        selectedHrefId,
        urlThreadId,
        selectedRowKey,
        headerName,
        normalizedName,
        digits,
        channel,
        canvasLocalId,
        selectedRow,
        rowKey: selectedRowKey,
        cleanName: headerName,
        strongId
      };
    },

    conversationIdentityMatches(expected, actual) {
      if (!expected?.valid || !actual) return false;

      // 1. Conflict check among actual's own available ID sources:
      // Comparable available sources: selectedAttributeId, selectedHrefId, urlThreadId, canvasLocalId
      const actualIds = [
        { name: 'selectedAttributeId', val: actual.selectedAttributeId },
        { name: 'selectedHrefId', val: actual.selectedHrefId },
        { name: 'urlThreadId', val: actual.urlThreadId },
        { name: 'canvasLocalId', val: actual.canvasLocalId }
      ].filter(item => Boolean(item.val));

      for (let i = 0; i < actualIds.length; i++) {
        for (let j = i + 1; j < actualIds.length; j++) {
          if (actualIds[i].val !== actualIds[j].val) {
            // Conflict among actual available sources (e.g. Selected B + URL A)! Reject immediately!
            return false;
          }
        }
      }

      // 2. Channel / platform agreement:
      if (expected.channel && actual.channel) {
        if (expected.channel !== actual.channel) {
          return false;
        }
      }

      // 3. Expected strong ID comparison:
      const expectedId =
        expected.strongId ||
        expected.selectedAttributeId ||
        expected.selectedHrefId;

      if (expectedId) {
        // A matching selected row must NEVER mask a conflicting URL:
        if (actual.urlThreadId && actual.urlThreadId !== expectedId) {
          return false;
        }
        if (actual.selectedAttributeId && actual.selectedAttributeId !== expectedId) {
          return false;
        }
        if (actual.selectedHrefId && actual.selectedHrefId !== expectedId) {
          return false;
        }
        if (actual.canvasLocalId && actual.canvasLocalId !== expectedId) {
          return false;
        }

        // At least one ID source in actual must agree with expectedId
        const hasMatchingId = actualIds.some(item => item.val === expectedId);
        if (!hasMatchingId) {
          return false;
        }

        // Corroborate header name / digits if specified
        if (expected.normalizedName || expected.digits) {
          const exactNameMatch = Boolean(
            expected.normalizedName &&
            actual.normalizedName &&
            expected.normalizedName === actual.normalizedName
          );
          const exactPhoneMatch = Boolean(
            expected.digits &&
            actual.digits &&
            expected.digits === actual.digits
          );
          if (!exactNameMatch && !exactPhoneMatch) {
            return false;
          }
        }

        return true;
      }

      // 4. Fallback when expected has no strongId:
      if (expected.ambiguousName) return false;

      const expRowKey = expected.selectedRowKey || expected.rowKey;
      const actRowKey = actual.selectedRowKey || actual.rowKey;
      if (!expRowKey || !actRowKey || expRowKey !== actRowKey) {
        return false;
      }

      const exactNameMatch = Boolean(
        expected.normalizedName &&
        actual.normalizedName &&
        expected.normalizedName === actual.normalizedName
      );
      const exactPhoneMatch = Boolean(
        expected.digits &&
        actual.digits &&
        expected.digits === actual.digits
      );

      return exactNameMatch || exactPhoneMatch;
    },

    assertConversationIdentity(expected) {
      const actual = this.getActiveConversationIdentity();

      if (!this.conversationIdentityMatches(expected, actual)) {
        throw new FocusIntegrityError(
          `TARGET_CONVERSATION_IDENTITY_MISMATCH:` +
          `expected=${expected?.leaseKey || 'unknown'}:` +
          `actual=${actual?.strongId || actual?.selectedRowKey || actual?.urlThreadId || 'unknown'}`
        );
      }

      return actual;
    },

    getCanvasLocalThreadId(canvas) {
      if (!canvas || !(canvas instanceof Element)) return null;
      const attr =
        canvas.getAttribute('data-thread-id') ||
        canvas.getAttribute('data-canvas-id') ||
        canvas.getAttribute('data-conversation-id') ||
        canvas.getAttribute('data-item-id') ||
        canvas.getAttribute('data-selected-item-id') ||
        null;
      if (attr) return attr;

      const child = canvas.querySelector(
        '[data-thread-id], [data-canvas-id], [data-conversation-id], [data-item-id], [data-selected-item-id]'
      );
      if (child) {
        return (
          child.getAttribute('data-thread-id') ||
          child.getAttribute('data-canvas-id') ||
          child.getAttribute('data-conversation-id') ||
          child.getAttribute('data-item-id') ||
          child.getAttribute('data-selected-item-id') ||
          null
        );
      }
      return null;
    },

    verifySurfaceTargetIdentity(canvas, expected) {
      if (!canvas || !(canvas instanceof Element) || !canvas.isConnected) {
        return false;
      }
      if (!expected?.valid) {
        return false;
      }

      const canvasLocalId = this.getCanvasLocalThreadId(canvas);
      const cleanExpectedId = expected.strongId ? String(expected.strongId).replace(/^id_/, '') : '';
      const cleanCanvasId = canvasLocalId ? String(canvasLocalId).replace(/^id_/, '') : '';

      const hasConflictingId = Boolean(
        cleanCanvasId &&
        cleanExpectedId &&
        cleanCanvasId !== cleanExpectedId
      );

      if (hasConflictingId) {
        return false;
      }

      const hasAnchoredTargetId = Boolean(
        cleanExpectedId &&
        cleanCanvasId &&
        cleanCanvasId === cleanExpectedId
      );

      if (hasAnchoredTargetId) {
        const localChannel = this.detectChannel(canvas);
        if (expected.channel && localChannel && localChannel !== expected.channel) {
          return false;
        }
        return true;
      }

      // Check for a target header physically contained by the candidate surface itself
      const localHeader = canvas.querySelector(
        '[data-testid*="header" i], [data-testid*="chat_header" i], header, [role="banner"]'
      );
      if (localHeader && canvas.contains(localHeader)) {
        const headingEl = localHeader.querySelector('[role="heading"], h1, h2, h3, span[dir="auto"]') || localHeader;
        const headerText = (headingEl.innerText || headingEl.textContent || '').trim();
        const normText = normalizeArabicText(headerText);
        const nameMatched = Boolean(
          (expected.normalizedName && normText === expected.normalizedName) ||
          (expected.cleanName && headerText === expected.cleanName)
        );
        const rawHeaderDigits = headerText.replace(/\D/g, '');
        const phoneMatched = Boolean(
          expected.digits &&
          rawHeaderDigits.length >= 6 &&
          (rawHeaderDigits.includes(expected.digits) || expected.digits.includes(rawHeaderDigits))
        );

        const headerChannel = this.detectChannel(localHeader) || this.detectChannel(canvas);
        const channelMatched = !expected.channel || !headerChannel || (headerChannel === expected.channel);

        if ((nameMatched || phoneMatched) && channelMatched) {
          return true;
        }
      }

      // When target-local evidence is unavailable, fail closed
      return false;
    },

    getVerifiedConversationCanvas(expected = null) {
      if (expected) {
        const actual = this.getActiveConversationIdentity();
        if (!this.conversationIdentityMatches(expected, actual)) {
          return null;
        }

        // Corroborate selected row alignment
        const conversationRows = this.getConversationRows();
        let rowConfirmed = conversationRows.some(row => {
          const isSelected = row.getAttribute('aria-selected') === 'true' ||
                             row.getAttribute('data-selected') === 'true' ||
                             Boolean(row.querySelector('[aria-selected="true"]'));
          if (!isSelected) return false;
          if (expected.strongId) {
            const rowId = row.getAttribute('data-thread-id') ||
                          row.querySelector('[data-thread-id]')?.getAttribute('data-thread-id') ||
                          this.extractConversationIdFromHref(row.getAttribute('href') || row.querySelector('a[href]')?.getAttribute('href'));
            return rowId === expected.strongId;
          }
          return this.getStableRowKey(row) === (expected.selectedRowKey || expected.rowKey);
        });

        if (!rowConfirmed) {
          const directRow = (expected.targetRow && expected.targetRow.isConnected)
            ? expected.targetRow
            : document.querySelector('[aria-selected="true"], [data-selected="true"]');
          if (directRow && !directRow.closest('#mbs-inbox-automator-root')) {
            const rowElem = directRow.closest('[role="row"], [role="listitem"], a[href*="/inbox/"], a[href*="/latest/inbox/"]') || directRow;
            const isSelected = rowElem.getAttribute('aria-selected') === 'true' ||
                               rowElem.getAttribute('data-selected') === 'true' ||
                               Boolean(rowElem.querySelector('[aria-selected="true"]'));
            if (isSelected) {
              if (expected.strongId) {
                const rowId = rowElem.getAttribute('data-thread-id') ||
                              rowElem.querySelector('[data-thread-id]')?.getAttribute('data-thread-id') ||
                              this.extractConversationIdFromHref(rowElem.getAttribute('href') || rowElem.querySelector('a[href]')?.getAttribute('href'));
                rowConfirmed = (rowId === expected.strongId);
              } else {
                rowConfirmed = (this.getStableRowKey(rowElem) === (expected.selectedRowKey || expected.rowKey));
              }
            }
          }
        }

        if (!rowConfirmed) {
          return null;
        }
      }

      const rootSelectors = [
        'div[data-testid*="chat-canvas" i]',
        'div[data-testid*="message-list" i]',
        'div[aria-label*="حاوية قائمة الرسائل" i]',
        'div[aria-label*="محادثة" i]',
        'div[aria-label*="Conversation" i]',
        'div[role="main"]',
        'main'
      ];

      const composerSelectors = [
        'div[data-lexical-editor="true"][contenteditable="true"]',
        'div[role="textbox"][contenteditable="true"]',
        'div[contenteditable="true"][aria-label*="رسالة" i]',
        'div[contenteditable="true"][aria-label*="message" i]',
        'textarea[aria-label*="رسالة" i]',
        'textarea[aria-label*="message" i]'
      ];

      const roots = [];
      for (const selector of rootSelectors) {
        for (const root of document.querySelectorAll(selector)) {
          if (
            roots.includes(root) ||
            root.offsetParent === null ||
            root.closest('#mbs-inbox-automator-root')
          ) {
            continue;
          }

          const rootRect = root.getBoundingClientRect();
          if (rootRect.width < 280 || rootRect.height < 220) {
            continue;
          }

          const containsComposer = composerSelectors.some(composerSelector => (
            Array.from(root.querySelectorAll(composerSelector)).some(element => {
              if (
                element.offsetParent === null ||
                element.closest('#mbs-inbox-automator-root') ||
                element.closest(
                  '#inbox-search-input, [role="search"], [role="searchbox"]'
                )
              ) {
                return false;
              }

              const rect = element.getBoundingClientRect();
              return (
                rect.width >= 180 &&
                rect.height >= 15 &&
                (rect.top >= rootRect.top + rootRect.height * 0.45 || (root.contains(element) && rect.bottom <= rootRect.bottom + 2))
              );
            })
          ));

          if (containsComposer) roots.push(root);
        }
      }

      roots.sort((left, right) => {
        const leftRect = left.getBoundingClientRect();
        const rightRect = right.getBoundingClientRect();
        return (
          leftRect.width * leftRect.height -
          rightRect.width * rightRect.height
        );
      });

      if (expected) {
        const matchingRoot = roots.find(r => this.verifySurfaceTargetIdentity(r, expected));
        if (matchingRoot) return matchingRoot;
      }

      return roots[0] || null;
    },

    getConversationRoot(scopedTarget = null) {
      const target = scopedTarget?.surface || (scopedTarget instanceof Element ? scopedTarget : null);
      if (target && target.isConnected) {
        let root = target.closest('[role="main"], main, #mbs-fixture') || target.parentElement;
        while (root && root !== document.body && root !== document.documentElement) {
          if (root.querySelector('[role="textbox"], [contenteditable="true"]')) {
            return root;
          }
          root = root.parentElement;
        }
        return target;
      }

      const canvas = this.getVerifiedConversationCanvas();
      if (canvas && canvas.isConnected) {
        let root = canvas.closest('[role="main"], main, #mbs-fixture') || canvas.parentElement;
        while (root && root !== document.body && root !== document.documentElement) {
          if (root.querySelector('[role="textbox"], [contenteditable="true"]')) {
            return root;
          }
          root = root.parentElement;
        }
        return canvas;
      }

      const candidateRoot = document.querySelector('div[role="main"], main, #mbs-fixture, div[data-testid*="chat-canvas" i]');
      if (candidateRoot && !candidateRoot.closest('#mbs-inbox-automator-root') && candidateRoot.isConnected) {
        return candidateRoot;
      }

      return null;
    },

    resolveComposer(expected = null, canvasTarget = null) {
      if (expected && !canvasTarget) {
        this.assertConversationIdentity(expected);
      }

      const canvas = canvasTarget || this.getVerifiedConversationCanvas(expected);
      if (!canvas) return null;

      const canvasRect = canvas.getBoundingClientRect();
      const selectors = [
        'div[data-lexical-editor="true"][contenteditable="true"]',
        'div[role="textbox"][contenteditable="true"]',
        'div[contenteditable="true"][aria-label*="رسالة" i]',
        'div[contenteditable="true"][aria-label*="message" i]',
        'textarea[aria-label*="رسالة" i]',
        'textarea[aria-label*="message" i]'
      ];

      const candidates = [];

      for (const selector of selectors) {
        for (const element of canvas.querySelectorAll(selector)) {
          if (
            candidates.includes(element) ||
            !element.isConnected ||
            element.offsetParent === null ||
            element.closest('#mbs-inbox-automator-root') ||
            element.closest(
              '#inbox-search-input, [role="search"], [role="searchbox"]'
            )
          ) {
            continue;
          }

          const rect = element.getBoundingClientRect();
          if (
            rect.width >= 180 &&
            rect.height >= 15 &&
            (rect.top >= canvasRect.top + canvasRect.height * 0.45 || canvas.contains(element)) &&
            rect.left >= canvasRect.left - 2 &&
            rect.right <= canvasRect.right + 2 &&
            rect.bottom <= canvasRect.bottom + 2
          ) {
            candidates.push(element);
          }
        }
      }

      candidates.sort((left, right) => {
        const leftRect = left.getBoundingClientRect();
        const rightRect = right.getBoundingClientRect();
        return rightRect.bottom - leftRect.bottom;
      });

      return candidates[0] || null;
    },

    acquireConversationSurfaceLease(expectedOrLease, cancellationToken = null) {
      if (expectedOrLease?.surface && expectedOrLease?.expected) {
        if (cancellationToken && !expectedOrLease.cancellationToken) {
          expectedOrLease.cancellationToken = cancellationToken;
        }
        return expectedOrLease;
      }

      if (cancellationToken?.cancelled) {
        throw new Error('ROW_PROCESSING_CANCELLED');
      }

      const expected = expectedOrLease?.expected || expectedOrLease;
      this.assertConversationIdentity(expected);

      const surface = this.getVerifiedConversationCanvas(expected);
      if (!surface || !surface.isConnected) {
        throw new FocusIntegrityError('CONVERSATION_SURFACE_NOT_CORROBORATED');
      }

      if (!this.verifySurfaceTargetIdentity(surface, expected)) {
        throw new FocusIntegrityError('CONVERSATION_SURFACE_NOT_CORROBORATED');
      }

      const composer = this.resolveComposer(expected, surface);
      if (!composer || !composer.isConnected) {
        throw new FocusIntegrityError('COMPOSER_NOT_RESOLVED');
      }

      return {
        expected,
        surface,
        composer,
        timestamp: Date.now(),
        remountCount: 0,
        lastKnownText: '',
        cancellationToken
      };
    },

    acquireComposerLease(expectedOrLease, cancellationToken = null) {
      return this.acquireConversationSurfaceLease(expectedOrLease, cancellationToken);
    },

    assertComposerLease(lease) {
      if (!lease?.expected || !lease.composer) {
        throw new FocusIntegrityError('COMPOSER_LEASE_LOST');
      }

      if (lease.cancellationToken?.cancelled) {
        throw new Error('ROW_PROCESSING_CANCELLED');
      }

      this.assertConversationIdentity(lease.expected);

      const surface = lease.surface;
      if (!surface || !surface.isConnected) {
        // IMMUTABLE CANVAS LEASE: throw immediately; never assign globally rediscovered surface
        throw new FocusIntegrityError('CONVERSATION_SURFACE_LOST');
      }

      if (!this.verifySurfaceTargetIdentity(surface, lease.expected)) {
        throw new FocusIntegrityError('CONVERSATION_SURFACE_NOT_CORROBORATED');
      }

      // Remount only considered inside original connected canvas
      const currentComposer = this.resolveComposer(lease.expected, surface);
      if (!currentComposer || !currentComposer.isConnected || !surface.contains(currentComposer)) {
        throw new FocusIntegrityError('COMPOSER_LEASE_LOST');
      }

      if (currentComposer !== lease.composer) {
        lease.remountCount += 1;
        const expectedPrefix = lease.lastKnownText || '';
        const remountText = (currentComposer.innerText || currentComposer.textContent || '').trim();

        if (expectedPrefix.length > 0) {
          const cleanExpectedPrefix = expectedPrefix.trim();
          const isBlankOrPlaceholder =
            remountText === '' ||
            remountText.includes('رد في Messenger') ||
            remountText.includes('رد في Instagram') ||
            remountText.includes('رد في WhatsApp') ||
            remountText.includes('Reply in');

          if (isBlankOrPlaceholder) {
            // FAIL-CLOSED: throw if remounted composer is blank or placeholder-only
            throw new FocusIntegrityError('COMPOSER_TEXT_CONTINUITY_VIOLATION');
          }

          const preservesExactPrefix =
            remountText === expectedPrefix ||
            remountText.startsWith(expectedPrefix) ||
            remountText === cleanExpectedPrefix ||
            remountText.startsWith(cleanExpectedPrefix);

          if (!preservesExactPrefix) {
            // FAIL-CLOSED: throw if remounted composer is truncated or divergent
            throw new FocusIntegrityError('COMPOSER_TEXT_CONTINUITY_VIOLATION');
          }
        }

        lease.composer = currentComposer;
      }

      const activeElement = document.activeElement;
      if (
        activeElement?.matches?.(
          '#inbox-search-input, [role="searchbox"], ' +
          '[role="search"], input[type="search"]'
        ) ||
        activeElement?.closest?.(
          '#inbox-search-input, [role="searchbox"], [role="search"]'
        )
      ) {
        throw new FocusIntegrityError('SEARCH_FOCUS_HIJACK');
      }

      return currentComposer;
    },

    async materializeRowActions(row) {
      if (!row) return;
      try {
        const rect = row.getBoundingClientRect();
        const clientX = rect.left + Math.max(10, Math.min(50, rect.width * 0.2));
        const clientY = rect.top + (rect.height / 2);
        const eventOpts = {
          bubbles: true,
          cancelable: true,
          view: window,
          clientX,
          clientY
        };
        row.dispatchEvent(new PointerEvent('pointerover', eventOpts));
        row.dispatchEvent(new MouseEvent('mouseover', eventOpts));
        row.dispatchEvent(new MouseEvent('mousemove', eventOpts));

        await new Promise(r => {
          if (typeof window.requestAnimationFrame === 'function') {
            window.requestAnimationFrame(() => window.requestAnimationFrame(r));
          } else {
            setTimeout(r, 32);
          }
        });
      } catch (_) {}
    },

    clearStaleComposerDraft(logger = null, composerTarget = null) {
      try {
        const composer = composerTarget || this.resolveComposer();
        if (!composer) return { ok: true, humanDraft: false };
        const content = (composer.innerText || composer.textContent || '').trim();
        const isPlaceholder = content.includes('رد في Messenger') ||
                              content.includes('رد في Instagram') ||
                              content.includes('Reply in') ||
                              content.includes('اكتب رسالة') ||
                              content.includes('Type a message');
        if (!isPlaceholder && content.length > 0) {
          const currentThreadKey = this.getActiveThreadKey();
          // [P0-DOM-01] Dual-layer ownership lookup: WeakMap (in-session) + sessionStorage (reload-safe)
          const ownership = getBotDraftOwnership(composer, currentThreadKey);
          const isBotOwned = ownership &&
            ownership.text &&
            (content === ownership.text || content.includes(ownership.text) || ownership.text.includes(content)) &&
            (!ownership.threadKey || !currentThreadKey || ownership.threadKey === currentThreadKey);

          if (!isBotOwned) {
            if (logger) logger.log('WARN', '[DRAFT SAFETY] رصد نص في محرر الرد كتبه موظف بشري (غير تابع للبوت). الحفاظ على المسودة وتخطي الرد الآلي.');
            return { ok: false, humanDraft: true };
          }

          if (logger) logger.log('WARN', 'رصد مسودة قديمة غير مرسلة للبوت في محرر الرد. تفريغ النص الاحتياطي لمنع الإرسال الخطأ...');
          composer.focus();
          const sel = window.getSelection();
          const range = document.createRange();
          range.selectNodeContents(composer);
          sel.removeAllRanges();
          sel.addRange(range);
          try {
            document.execCommand('delete', false, null);
          } catch (_) {
            range.deleteContents();
          }
          // [P0-DOM-01] Clear sessionStorage record after successful stale draft removal
          clearBotDraftSessionRecord(currentThreadKey);
          this.deselectActiveChat();
        }
        return { ok: true, humanDraft: false };
      } catch (_) {
        return { ok: true, humanDraft: false };
      }
    },

    deselectActiveChat() {
      try {
        // 1. Send Escape keys to dismiss drawers/menus
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', keyCode: 27, which: 27, bubbles: true, cancelable: true }));
        window.dispatchEvent(new KeyboardEvent('keyup', { key: 'Escape', code: 'Escape', keyCode: 27, which: 27, bubbles: true, cancelable: true }));

        // 2. Pure blur of active element (no clicking any inputs)
        if (document.activeElement && typeof document.activeElement.blur === 'function') {
          document.activeElement.blur();
        }
        releaseChatFocus();
      } catch (_) {}
    },

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
      const rawText = DOM.extractTextWithAlt(row) || row.innerText || '';
      const lines = rawText
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

    getActiveChatContactName(scopedTarget = null) {
      const isValid = (t) => t && t.length >= 2 && !['البريد الوارد', 'تفاصيل الاتصال', 'التسميات', 'الملاحظات', 'Inbox', 'Contact Details', 'Labels', 'Notes'].includes(t) && !this.isTimestampOrBadge(t) && !this.isSnippetOrPreview(t);

      const headerNode = this.getActiveHeaderNode(scopedTarget);
      if (headerNode) {
        const heading = headerNode.querySelector('[role="heading"], h1, h2, h3, span[dir="auto"], span[style*="font-weight"]') || headerNode;
        const txt = (heading.innerText || heading.textContent || '').trim();
        if (isValid(txt)) return this.sanitizeName(txt);
      }

      const root = this.getConversationRoot(scopedTarget);
      if (root) {
        const headings = Array.from(root.querySelectorAll('[role="heading"], h1, h2, h3')).filter(el => {
          if (el.closest('#mbs-inbox-automator-root')) return false;
          const r = el.getBoundingClientRect();
          const t = (el.innerText || '').trim();
          return (r.width === 0 || (r.top >= 50 && r.top <= 200)) && isValid(t);
        });
        if (headings.length > 0) {
          return this.sanitizeName(headings[0].innerText.trim());
        }
      }

      return '';
    },

    getActiveHeaderNode(scopedTarget = null) {
      const isValid = (t) => t && t.length >= 2 && !['البريد الوارد', 'تفاصيل الاتصال', 'التسميات', 'الملاحظات', 'Inbox', 'Contact Details', 'Labels', 'Notes'].includes(t) && !this.isTimestampOrBadge(t) && !this.isSnippetOrPreview(t);

      const root = this.getConversationRoot(scopedTarget);
      if (root) {
        const headerCandidate = root.querySelector(
          '[data-testid*="chat_header" i], [data-testid*="chat-header" i], header[role="banner"], header, div[role="banner"]'
        );
        if (headerCandidate && !headerCandidate.closest('#mbs-inbox-automator-root')) {
          return headerCandidate;
        }

        const headings = Array.from(root.querySelectorAll('[role="heading"], h1, h2, h3, header, div[role="banner"]')).filter(el => {
          if (el.closest('#mbs-inbox-automator-root')) return false;
          const r = el.getBoundingClientRect();
          const t = (el.innerText || '').trim();
          return r.top <= 200 && r.width > 0 && (isValid(t) || el.tagName === 'HEADER' || el.getAttribute('role') === 'banner');
        });
        if (headings.length > 0) return headings[0];
      }

      if (scopedTarget instanceof Element && scopedTarget.isConnected) {
        const header = scopedTarget.querySelector?.('header, div[role="banner"]') || scopedTarget.parentElement?.querySelector?.('header, div[role="banner"]');
        if (header && !header.closest('#mbs-inbox-automator-root')) return header;
      }

      return null;
    },

    async waitForConversationLoad(
      expected,
      targetRow,
      clickTarget,
      logger,
      cancellationToken = null,
      preClickSnapshot = null
    ) {
      if (!expected?.valid) {
        if (logger) {
          logger.log(
            'ERROR',
            `[IDENTITY] هوية المحادثة المستهدفة غير صالحة: ` +
            `${expected?.reason || 'UNKNOWN'}`
          );
        }
        return null;
      }

      const startedAt = Date.now();
      const timeoutMs = 5500;
      let consecutiveStableMatches = 0;
      let firstSampleTime = null;
      let lastObservedRoot = null;
      let lastObservedCanvas = null;
      let lastObservedComposer = null;
      let retryPerformed = false;

      while (Date.now() - startedAt < timeoutMs) {
        if (state.emergencyAbort) {
          throw new Error('ABORT_SIGNAL');
        }
        if (cancellationToken?.cancelled) {
          throw new Error('ROW_PROCESSING_CANCELLED');
        }

        const actual = this.getActiveConversationIdentity();
        const identityMatches =
          this.conversationIdentityMatches(expected, actual);

        let composer = null;
        let canvas = null;

        if (identityMatches) {
          canvas = this.getVerifiedConversationCanvas(expected);
          composer = canvas
            ? this.resolveComposer(expected, canvas)
            : null;
        }

        const selectedRowConfirmed = expected.strongId
          ? Boolean(
              (actual.selectedAttributeId && actual.selectedAttributeId === expected.strongId) ||
              (actual.selectedHrefId && actual.selectedHrefId === expected.strongId) ||
              (actual.strongId && actual.strongId === expected.strongId)
            )
          : Boolean(
              actual.selectedRow &&
              actual.selectedRowKey &&
              actual.selectedRowKey === (expected.selectedRowKey || expected.rowKey)
            );

        // Header and composer in same shell
        let sameShell = false;
        if (canvas && composer) {
          const headerNode = this.getActiveHeaderNode(canvas);
          if (headerNode) {
            let boundedRoot = canvas.closest('[role="main"], main, div[data-testid*="chat-canvas"], div[data-testid*="message-list"], #mbs-fixture') || canvas.parentElement;
            while (boundedRoot && boundedRoot !== document.body && boundedRoot !== document.documentElement) {
              if (boundedRoot.contains(headerNode) && boundedRoot.contains(canvas) && boundedRoot.contains(composer)) {
                break;
              }
              boundedRoot = boundedRoot.parentElement;
            }

            if (
              boundedRoot &&
              boundedRoot !== document.body &&
              boundedRoot !== document.documentElement &&
              boundedRoot.contains(headerNode) &&
              boundedRoot.contains(canvas) &&
              boundedRoot.contains(composer)
            ) {
              sameShell = true;
            }
          }
        }

        // Proven transition from pre-click surface on switch
        let transitionProven = true;
        if (preClickSnapshot && canvas && composer) {
          const preId = preClickSnapshot.identity;
          const isSwitch = Boolean(
            preId &&
            (
              (preId.selectedAttributeId && expected.strongId && preId.selectedAttributeId !== expected.strongId) ||
              (preId.urlThreadId && expected.strongId && preId.urlThreadId !== expected.strongId) ||
              (preId.selectedRowKey && expected.selectedRowKey && preId.selectedRowKey !== (expected.selectedRowKey || expected.rowKey)) ||
              (preId.normalizedName && expected.normalizedName && preId.normalizedName !== expected.normalizedName)
            )
          );

          if (isSwitch) {
            // Target identity anchoring must apply to every candidate surface during a conversation switch,
            // regardless of whether canvas/composer nodes are unchanged, partially remounted, or completely replaced.
            // Delete the logic that allows canvas !== preClickSnapshot.canvas or composer !== preClickSnapshot.composer
            // plus a changed fingerprint to prove navigation.
            // A fingerprint may be used only for stability/change observation. It must never be positive conversation-identity evidence.
            if (!this.verifySurfaceTargetIdentity(canvas, expected)) {
              transitionProven = false;
            }
          }
        }

        const surfaceTargetValid = this.verifySurfaceTargetIdentity(canvas, expected);

        const candidateValid = Boolean(
          identityMatches &&
          selectedRowConfirmed &&
          canvas &&
          composer &&
          composer.isConnected &&
          canvas.contains(composer) &&
          sameShell &&
          surfaceTargetValid &&
          transitionProven
        );

        if (candidateValid) {
          const currentRoot = canvas.closest('[role="main"], main') || canvas;
          if (consecutiveStableMatches === 0) {
            consecutiveStableMatches = 1;
            firstSampleTime = Date.now();
            lastObservedRoot = currentRoot;
            lastObservedCanvas = canvas;
            lastObservedComposer = composer;
          } else if (
            currentRoot === lastObservedRoot &&
            canvas === lastObservedCanvas &&
            composer === lastObservedComposer
          ) {
            consecutiveStableMatches += 1;
            const elapsed = Date.now() - firstSampleTime;
            if (consecutiveStableMatches >= 3 && elapsed >= 450) {
              return {
                expected,
                surface: canvas,
                composer,
                timestamp: Date.now(),
                remountCount: 0,
                lastKnownText: '',
                cancellationToken
              };
            }
          } else {
            consecutiveStableMatches = 1;
            firstSampleTime = Date.now();
            lastObservedRoot = currentRoot;
            lastObservedCanvas = canvas;
            lastObservedComposer = composer;
          }
        } else {
          consecutiveStableMatches = 0;
          firstSampleTime = null;
          lastObservedRoot = null;
          lastObservedCanvas = null;
          lastObservedComposer = null;
        }

        const elapsed = Date.now() - startedAt;
        if (!retryPerformed && elapsed >= 1200) {
          retryPerformed = true;
          try {
            await HumanSimulator.naturalClick(
              clickTarget || targetRow
            );
          } catch (error) {
            if (logger) {
              logger.log(
                'WARN',
                `[IDENTITY] تعذر تنفيذ نقرة إعادة المحاولة: ` +
                `${error?.message || error}`
              );
            }
          }
        }

        await cancellableSleep(160, cancellationToken);
      }

      if (logger) {
        const actual = this.getActiveConversationIdentity();
        logger.log(
          'ERROR',
          `[IDENTITY TIMEOUT] لم تتطابق المحادثة المطلوبة ` +
          `"${expected.cleanName || expected.leaseKey}" مع المعروضة ` +
          `"${actual.headerName || actual.strongId || actual.selectedRowKey || 'غير محددة'}".`
        );
      }

      return null;
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
      // Clear stray text in search bar to avoid filtering conversation list
      try {
        const searchInputs = Array.from(document.querySelectorAll('input[type="text"], input[type="search"], input:not([type])')).filter(inp => {
          if (inp.closest('#mbs-inbox-automator-root')) return false;
          const ph = (inp.getAttribute('placeholder') || '').toLowerCase();
          const id = (inp.id || '').toLowerCase();
          const testid = (inp.getAttribute('data-testid') || '').toLowerCase();
          return ph.includes('بحث') || ph.includes('search') || id.includes('search') || testid.includes('search');
        });

        for (const input of searchInputs) {
          if (input.value && input.value.trim().length > 0) {
            if (logger) logger.log('WARN', 'تفريغ نص عالق في شريط البحث لمنع تشتيت المحادثات...');
            input.value = '';
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            if (typeof input.blur === 'function') {
              input.blur();
            }
          }
        }
      } catch (_) {}

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

    getChatCanvas(expectedOrLease = null) {
      if (expectedOrLease?.surface && expectedOrLease.surface.isConnected) {
        return expectedOrLease.surface;
      }
      const expected = expectedOrLease?.expected || expectedOrLease;
      return this.getVerifiedConversationCanvas(expected);
    },

    getMessageScrollContainer(expectedOrLease = null) {
      const composer = this.getComposer(expectedOrLease);
      const chat = this.getChatCanvas(expectedOrLease);
      if (!chat) return null;

      const chatStyle = window.getComputedStyle(chat);
      if (
        (
          chatStyle.overflowY === 'auto' ||
          chatStyle.overflowY === 'scroll'
        ) &&
        (!composer || !chat.contains(composer))
      ) {
        return chat;
      }

      const scrollables = Array.from(
        chat.querySelectorAll('div')
      ).filter(element => {
        if (element.closest('#mbs-inbox-automator-root')) {
          return false;
        }
        if (
          composer &&
          (
            composer.contains(element) ||
            element.contains(composer)
          )
        ) {
          return false;
        }

        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return (
          (
            style.overflowY === 'auto' ||
            style.overflowY === 'scroll'
          ) &&
          rect.height > 180 &&
          rect.width > 250
        );
      });

      return scrollables[0] || chat;
    },

    getComposer(expectedOrLease = null) {
      if (expectedOrLease?.surface && expectedOrLease.surface.isConnected) {
        return this.resolveComposer(expectedOrLease.expected, expectedOrLease.surface);
      }
      const expected = expectedOrLease?.expected || expectedOrLease;
      return this.resolveComposer(expected);
    },

    getSendButton(expectedOrLease, composerTarget = null) {
      const expected = expectedOrLease?.expected || expectedOrLease;
      if (!expected?.valid) return null;

      this.assertConversationIdentity(expected);

      const canvas = (expectedOrLease?.surface && expectedOrLease.surface.isConnected)
        ? expectedOrLease.surface
        : this.getVerifiedConversationCanvas(expected);

      const composer =
        composerTarget ||
        (expectedOrLease?.composer && canvas && canvas.contains(expectedOrLease.composer)
          ? expectedOrLease.composer
          : this.resolveComposer(expected, canvas));

      if (!canvas || !composer || !canvas.contains(composer)) {
        return null;
      }

      const composerRect = composer.getBoundingClientRect();
      const selectors = [
        'div[aria-label*="إرسال" i][role="button"]',
        'div[aria-label*="Send" i][role="button"]',
        'button[aria-label*="إرسال" i]',
        'button[aria-label*="Send" i]',
        'button[type="submit"]'
      ];

      for (const selector of selectors) {
        for (const button of canvas.querySelectorAll(selector)) {
          if (
            !button.isConnected ||
            button.offsetParent === null ||
            button.closest('#mbs-inbox-automator-root')
          ) {
            continue;
          }

          const style = window.getComputedStyle(button);
          const rect = button.getBoundingClientRect();

          if (
            button.getAttribute('aria-disabled') !== 'true' &&
            !button.disabled &&
            style.pointerEvents !== 'none' &&
            rect.width > 0 &&
            rect.height > 0 &&
            Math.abs(rect.top - composerRect.top) <= 400
          ) {
            return button;
          }
        }
      }

      return null;
    },

    parseSequentialReplies(rawText) {
      if (!rawText || typeof rawText !== 'string') return [];
      return rawText
        .split(/\r?\n/)
        .map(line => line.trim())
        .filter(line => line.length > 0);
    },

    async waitForComposerClear(
      expectedOrLease,
      maxWaitMs = 1500,
      cancellationToken = null
    ) {
      const expected = expectedOrLease?.expected || expectedOrLease;
      const token = cancellationToken || expectedOrLease?.cancellationToken;
      const startedAt = Date.now();

      while (Date.now() - startedAt < maxWaitMs) {
        if (token?.cancelled) {
          throw new Error('ROW_PROCESSING_CANCELLED');
        }
        if (state.emergencyAbort) {
          throw new Error('ABORT_SIGNAL');
        }

        this.assertConversationIdentity(expected);

        const composer = this.getComposer(expectedOrLease);
        if (!composer || !composer.isConnected) {
          throw new FocusIntegrityError(
            'COMPOSER_NOT_AVAILABLE_DURING_CLEAR_WAIT'
          );
        }

        const content = (
          composer.innerText ||
          composer.textContent ||
          ''
        ).trim();

        const isPlaceholder =
          content.length === 0 ||
          content.includes('رد في Messenger') ||
          content.includes('رد في Instagram') ||
          content.includes('رد في WhatsApp') ||
          content.includes('Reply in');

        if (isPlaceholder) return true;
        await cancellableSleep(100, cancellationToken);
      }

      return false;
    },

    async executeRestoreToUnread(logger, targetRow, contactKey, budget = null) {
      const neutralizeFocus = () => {
        releaseChatFocus();
        try {
          if (document.activeElement && typeof document.activeElement.blur === 'function') {
            document.activeElement.blur();
          }
        } catch (_) {}
      };

      // -------------------------------------------------------------------------
      // PRIMARY STRATEGY: Row-Level Action in left conversation list
      // -------------------------------------------------------------------------
      if (targetRow) {
        await this.materializeRowActions(targetRow);
        const rowUnreadBtn = targetRow.querySelector(
          'button[aria-label*="غير مقروء" i], button[aria-label*="unread" i], ' +
          'div[role="button"][aria-label*="غير مقروء" i], div[role="button"][aria-label*="unread" i], ' +
          '[data-testid*="mark_as_unread" i], [data-testid*="unread" i], ' +
          '[aria-label*="علامة كغير" i]'
        );
        if (rowUnreadBtn) {
          if (logger) logger.log('UNREAD', '[UNREAD] تم رصد زر غير مقروء مباشرة في صف المحادثة. النقر المباشر...');
          try {
            await HumanSimulator.flashEnvelopeButton(rowUnreadBtn);
            neutralizeFocus();
            dispatchFullClick(rowUnreadBtn);
            neutralizeFocus();
            const verified = await pollVerification(1500);
            if (verified) return { ok: true, alreadyUnread: false };
          } catch (_) {}
        }
      }

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
        const allHeaderButtons = getHeaderButtons();

        // -----------------------------------------------------------------------
        // SECONDARY STRATEGY: Direct Action Bar Detection
        // If direct action buttons (Done, Star, Delete) exist WITHOUT a three-dot menu,
        // do not search for dropdown menu - rely on direct button or row-level action.
        // -----------------------------------------------------------------------
        const hasDirectActionBar = allHeaderButtons.some(b => {
          const txt = (b.innerText || '').trim();
          const aria = (b.getAttribute('aria-label') || '').trim();
          const title = (b.getAttribute('title') || '').trim();
          return /^(تم|نقل إلى تم|Done|Mark as done|تمييز بنجمة|Star|حذف|Delete)$/i.test(txt) ||
                 /^(تم|نقل إلى تم|Done|Mark as done|تمييز بنجمة|Star|حذف|Delete)$/i.test(aria) ||
                 /^(تم|نقل إلى تم|Done|Mark as done|تمييز بنجمة|Star|حذف|Delete)$/i.test(title);
        });

        const dropdownBtn = allHeaderButtons.find(b => {
          const t = (b.innerText || '').trim();
          const aria = (b.getAttribute('aria-label') || '').trim();
          const title = (b.getAttribute('title') || '').trim();
          return t.includes('فتح القائمة المنسدلة') || aria.includes('المزيد') || aria.includes('More') ||
                 title.includes('المزيد') || title.includes('More') || aria.includes('القائمة المنسدلة') ||
                 aria.includes('خيارات') || title.includes('خيارات');
        });

        if (!dropdownBtn) {
          if (hasDirectActionBar && logger) {
            logger.log('INFO', '[DIRECT-BAR] رصد شريط الإجراءات المباشر بدون قائمة منسدلة (...). الاعتماد على الإجراء المباشر.');
          }
          return false;
        }

        if (logger) logger.log('SCAN', 'فحص القائمة المنسدلة العلوية للتمييز كغير مقروءة...');

        let result = false;
        try {
          if (budget && typeof budget.touch === 'function') budget.touch(3000);
          await HumanSimulator.flashEnvelopeButton(dropdownBtn);
          neutralizeFocus();
          dispatchFullClick(dropdownBtn);
          if (budget && typeof budget.touch === 'function') budget.touch(3000);
          await sleep(500);

          const menuItems = Array.from(document.querySelectorAll('[role="menu"] [role="menuitem"], [role="menuitem"], div[role="menu"] div[role="button"]')).filter(el => !el.closest('#mbs-inbox-automator-root'));

          const currentMenuState = () => {
            const hasMarkAsRead = menuItems.some(el => {
              const allTxt = `${el.innerText || ''} ${el.getAttribute('aria-label') || ''}`.toLowerCase();
              return (allTxt.includes('كمقروءة') || allTxt.includes('كمقروء') || allTxt.includes('mark as read')) &&
                     !allTxt.includes('غير') && !allTxt.includes('unread');
            });
            const unreadItem = menuItems.find(el => {
              const allTxt = `${el.innerText || ''} ${el.getAttribute('aria-label') || ''}`.toLowerCase();
              const r = el.getBoundingClientRect();
              return (allTxt.includes('غير مقروء') || allTxt.includes('unread')) &&
                     !allTxt.includes('نقل') && !allTxt.includes('المجلد') && !allTxt.includes('حذف') &&
                     r.height > 15 && r.height < 70 && r.width > 0;
            });
            if (hasMarkAsRead && !unreadItem) return 'ALREADY_UNREAD';
            if (unreadItem) return { action: 'MARK_UNREAD', item: unreadItem };
            return 'UNAVAILABLE';
          };

          const stateResult = currentMenuState();
          if (stateResult === 'ALREADY_UNREAD') {
            isAlreadyUnreadDetected = true;
            if (logger) logger.log('UNREAD', '[UNREAD] المحادثة غير مقروءة بالفعل في نظام Meta. تجاوز بأمان.');
            result = { ok: true, alreadyUnread: true };
            return result;
          }

          if (typeof stateResult === 'object' && stateResult.action === 'MARK_UNREAD') {
            neutralizeFocus();
            dispatchFullClick(stateResult.item);
            neutralizeFocus();
            if (budget && typeof budget.touch === 'function') budget.touch(3000);
            await sleep(350);
            result = { ok: true, alreadyUnread: false };
            return result;
          } else if (menuItems.length > 0) {
            isUnreadOptionUnavailable = true;
            if (logger) logger.log('UNREAD', '[UNREAD] تعذر العثور على خيار غير مقروء في هذه القناة (واتساب). إنهاء التعديل بأمان.');
            result = { ok: true, alreadyUnread: true };
            return result;
          }
        } finally {
          try {
            DOM.sendEscape();
            DOM.sendEscape();
            neutralizeFocus();
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

      const pollVerification = async (timeoutMs = 2000) => {
        if (!targetRow) return true;
        const start = Date.now();
        while (Date.now() - start < timeoutMs) {
          if (budget && typeof budget.touch === 'function') budget.touch(2000);
          if (checkVerifiedUnread()) return true;
          await sleep(100);
        }
        return checkVerifiedUnread();
      };

      // ATTEMPT 1: Focus release -> Click Direct or Dropdown -> Focus release -> Verification poll
      neutralizeFocus();
      let clicked = false;
      let usedDropdown = false;
      const directBtn = findDirectButton();

      if (directBtn) {
        await HumanSimulator.flashEnvelopeButton(directBtn);
        neutralizeFocus();
        dispatchFullClick(directBtn);
        neutralizeFocus();
        clicked = true;
      } else {
        usedDropdown = true;
        clicked = await tryClickDropdown();
      }

      if (isAlreadyUnreadDetected || isUnreadOptionUnavailable) {
        return true;
      }

      if (clicked) {
        const verified = await pollVerification(2000);
        if (verified) return true;
      }

      // ATTEMPT 2 (RETRY with alternate selector / dropdown):
      if (logger) logger.log('WARN', 'لم يتم تأكيد حالة غير مقروء في المحاولة الأولى، جاري إعادة المحاولة مع تحييد التركيز...');
      neutralizeFocus();
      await sleep(250);

      if (!usedDropdown) {
        clicked = await tryClickDropdown();
      } else {
        const retryBtn = findDirectButton();
        if (retryBtn) {
          await HumanSimulator.flashEnvelopeButton(retryBtn);
          neutralizeFocus();
          dispatchFullClick(retryBtn);
          neutralizeFocus();
          clicked = true;
        } else {
          clicked = await tryClickDropdown();
        }
      }

      if (isAlreadyUnreadDetected || isUnreadOptionUnavailable) {
        return true;
      }

      if (clicked) {
        const verified = await pollVerification(2000);
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

    isAudioOrMediaElement(el) {
      if (!el || !(el instanceof Element)) return false;
      try {
        if (el.tagName === 'AUDIO' || el.tagName === 'VIDEO') return true;
        if (el.matches && el.matches('audio, video, [data-testid*="audio" i], [data-testid*="voice" i]')) return true;
        if (el.querySelector && el.querySelector('audio, video, [data-testid*="audio" i], [data-testid*="voice" i]')) return true;

        const aria = (el.getAttribute && el.getAttribute('aria-label')) || '';
        if (/صوت|voice|audio|تسجيل صوتي|رسالة صوتية|Voice clip/i.test(aria)) return true;

        if (el.querySelector && el.querySelector('[aria-label*="صوت" i], [aria-label*="voice" i], [aria-label*="audio" i], [aria-label*="تسجيل صوتي" i], [aria-label*="رسالة صوتية" i], [aria-label*="Voice clip" i]')) {
          return true;
        }

        if (el.querySelector && el.querySelector('[class*="waveform" i], svg[class*="waveform" i], [role="progressbar"], [role="slider"]')) {
          return true;
        }

        if (el.querySelector && el.querySelector('button[aria-label*="تشغيل" i], button[aria-label*="Play" i], button[aria-label*="إيقاف مؤقت" i], button[aria-label*="Pause" i]')) {
          const txt = (el.innerText || '').trim();
          if (/^[0-9]{1,2}:[0-9]{2}$/.test(txt) || txt.length < 15) {
            return true;
          }
        }
      } catch (_) {}
      return false;
    },

    extractThreadContext(bubbles) {
      if (!Array.isArray(bubbles) || bubbles.length === 0) return '';
      
      const expectedOrLease = arguments[1] || null;
      const surface = (expectedOrLease?.surface && expectedOrLease.surface.isConnected)
        ? expectedOrLease.surface
        : (this && typeof this.getChatCanvas === 'function' ? this.getChatCanvas(expectedOrLease) : null);

      // 1. Direct ad referral element check in canvas
      const adEl = surface
        ? surface.querySelector('a[href*="/ads/"], [data-ad-id], [aria-label*="إعلان ممول" i], [aria-label*="Sponsored" i]')
        : null;
      const adText = adEl ? (this && typeof this.extractTextWithAlt === 'function' ? this.extractTextWithAlt(adEl) : (typeof DOM !== 'undefined' && DOM.extractTextWithAlt ? DOM.extractTextWithAlt(adEl) : '')).trim() : '';

      // 2. Thread inception window (first 2 bubbles - automated ad prompts / icebreakers)
      const inceptionBubbles = bubbles.slice(0, 2);
      const inceptionText = inceptionBubbles.map(b => (this && typeof this.extractTextWithAlt === 'function' ? this.extractTextWithAlt(b) : (typeof DOM !== 'undefined' && DOM.extractTextWithAlt ? DOM.extractTextWithAlt(b) : ''))).join(' ').trim();

      // 3. Recent history window (preceding 4 bubbles before tail)
      const recentBubbles = bubbles.length > 2 ? bubbles.slice(-5, -1) : [];
      const recentText = recentBubbles.map(b => (this && typeof this.extractTextWithAlt === 'function' ? this.extractTextWithAlt(b) : (typeof DOM !== 'undefined' && DOM.extractTextWithAlt ? DOM.extractTextWithAlt(b) : ''))).join(' ').trim();

      // Combine and cap at 1,000 characters to prevent regex performance overhead
      const combinedContext = [adText, inceptionText, recentText].filter(Boolean).join(' ');
      return combinedContext.slice(0, 1000).trim();
    },

    getMessageBubbles(expectedOrLease = null, cancellationToken = null) {
      const token = cancellationToken || expectedOrLease?.cancellationToken || null;
      if (token?.cancelled) throw new Error('ROW_PROCESSING_CANCELLED');

      const surface = (expectedOrLease?.surface && expectedOrLease.surface.isConnected)
        ? expectedOrLease.surface
        : this.getChatCanvas(expectedOrLease);

      if (!surface || !surface.isConnected) {
        throw new FocusIntegrityError('CONVERSATION_SURFACE_LOST');
      }

      const composer = expectedOrLease?.composer || this.getComposer(expectedOrLease);
      const compRect = composer ? composer.getBoundingClientRect() : null;

      const minX = compRect ? (compRect.left - 30) : (window.innerWidth * 0.20);
      const maxX = compRect ? (compRect.right + 30) : (window.innerWidth * 0.65);
      const minY = 90;
      const maxY = compRect ? (compRect.top - 6) : (window.innerHeight - 80);

      // Scoped strictly to surface - zero global document fallbacks
      const candidateElements = Array.from(surface.querySelectorAll('div, span, p, audio, video')).filter(el => {
        if (el.closest('#mbs-inbox-automator-root')) return false;
        if (composer && (composer.contains(el) || el.contains(composer))) return false;
        if (el.closest('button, header, footer, nav, [role="toolbar"]')) return false;

        const rect = el.getBoundingClientRect();
        if (rect.left < minX || rect.right > maxX || rect.top < minY || rect.bottom > maxY) return false;
        if (rect.width < 14 || rect.height < 14 || rect.height > 600) return false;

        const isAudioMedia = this.isAudioOrMediaElement(el);
        const text = DOM.extractTextWithAlt(el).trim();
        if (!text && !isAudioMedia) return false;
        if (!isAudioMedia && /^[0-9]{1,2}:[0-9]{2}[ ]*(م|ص)?$/.test(text)) return false;

        if (!isAudioMedia && this.isAdOrMetadataElement(el, text)) return false;

        const style = window.getComputedStyle(el);
        const hasBg = style.backgroundColor && style.backgroundColor !== 'rgba(0, 0, 0, 0)' && style.backgroundColor !== 'transparent';
        const hasRadius = parseInt(style.borderRadius, 10) >= 6;
        return isAudioMedia || (hasBg && hasRadius);
      });

      const leaves = candidateElements.filter(item => {
        return !candidateElements.some(other => other !== item && other.contains(item));
      });

      leaves.sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
      return leaves;
    },

    isOutboundBubble(bubble, leaseOrComposer = null) {
      if (!bubble) return false;
      const text = (DOM.extractTextWithAlt(bubble) || bubble.innerText || '').trim();

      // 1. Text match: ONLY if the bubble text contains a substantial chunk of our configured reply (25+ characters)
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
      const composer = leaseOrComposer?.composer || (leaseOrComposer instanceof Element ? leaseOrComposer : this.getComposer(leaseOrComposer));
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

    hasTrailingAudioOrMedia(expectedOrLease = null, cancellationToken = null) {
      const token = cancellationToken || expectedOrLease?.cancellationToken || null;
      if (token?.cancelled) throw new Error('ROW_PROCESSING_CANCELLED');

      const surface = (expectedOrLease?.surface && expectedOrLease.surface.isConnected)
        ? expectedOrLease.surface
        : this.getChatCanvas(expectedOrLease);
      if (!surface || !surface.isConnected) throw new FocusIntegrityError('CONVERSATION_SURFACE_LOST');

      const audioEls = Array.from(surface.querySelectorAll('audio, video, [data-testid*="audio" i], [data-testid*="voice" i], [aria-label*="صوت" i], [aria-label*="voice" i], [aria-label*="تسجيل صوتي" i], [aria-label*="رسالة صوتية" i]')).filter(el => {
        if (el.closest('#mbs-inbox-automator-root')) return false;
        if (el.closest('a[href], [data-testid*="link_preview" i], [data-testid*="preview" i], [class*="preview" i]')) return false;
        return true;
      });
      if (audioEls.length === 0) return false;
      const lastAudio = audioEls[audioEls.length - 1];
      if (this.isOutboundBubble(lastAudio, expectedOrLease)) return false;

      const bubbles = this.getMessageBubbles(expectedOrLease, token);
      if (bubbles.length === 0) return true;
      const lastBubble = bubbles[bubbles.length - 1];
      const audioRect = lastAudio.getBoundingClientRect();
      const bubbleRect = lastBubble.getBoundingClientRect();
      return audioRect.top >= bubbleRect.top - 15;
    },

    parseInboundBoundary(expectedOrLease = null, cancellationToken = null) {
      const token = cancellationToken || expectedOrLease?.cancellationToken || null;
      if (token?.cancelled) throw new Error('ROW_PROCESSING_CANCELLED');

      const bubbles = this.getMessageBubbles(expectedOrLease, token);
      if (bubbles.length === 0) {
        return { lastIsOutbound: false, customerBubbles: [], isVoiceOrMedia: false, tailBubble: null };
      }

      const lastBubble = bubbles[bubbles.length - 1];
      if (this.isOutboundBubble(lastBubble, expectedOrLease)) {
        return { lastIsOutbound: true, customerBubbles: [], isVoiceOrMedia: false, tailBubble: lastBubble };
      }

      const isVoiceOrMedia = this.isAudioOrMediaElement(lastBubble);

      const customerBubbles = [];
      for (let i = bubbles.length - 1; i >= 0; i--) {
        const b = bubbles[i];
        if (this.isOutboundBubble(b, expectedOrLease)) {
          break;
        }
        customerBubbles.unshift(b);
      }

      return { lastIsOutbound: false, customerBubbles, isVoiceOrMedia, tailBubble: lastBubble };
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

        await sleep(200);

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

    async simulateThreadScroll(logger, lease = null, cancellationToken = null) {
      const token = cancellationToken || lease?.cancellationToken || null;
      if (token?.cancelled) throw new Error('ROW_PROCESSING_CANCELLED');

      const container = lease?.surface ? DOM.getMessageScrollContainer(lease) : DOM.getMessageScrollContainer();
      if (!container) return;

      const peekDistance = Math.min(container.scrollHeight - container.clientHeight, randomRange(250, 400));
      if (peekDistance > 60) {
        if (logger) logger.log('SCROLL', 'استعراض سريع للمحادثة (Scroll Glance)...');
        container.scrollBy({ top: -peekDistance, behavior: 'smooth' });
        await cancellableSleep(randomRange(200, 260), token);
        container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
        await cancellableSleep(randomRange(140, 180), token);
      }
    },

    focusComposerAtEnd(composer) {
      if (!composer || !composer.isConnected) {
        throw new FocusIntegrityError('COMPOSER_NOT_CONNECTED');
      }

      composer.focus();

      const selection = window.getSelection();
      if (!selection) {
        throw new FocusIntegrityError(
          'COMPOSER_SELECTION_UNAVAILABLE'
        );
      }

      const range = document.createRange();
      range.selectNodeContents(composer);
      range.collapse(false);
      selection.removeAllRanges();
      selection.addRange(range);
    },

    async typeText(expectedOrLease, text, logger, cancellationToken = null) {
      return this.typeIntoComposer(expectedOrLease, text, logger, cancellationToken);
    },

    async typeReply(expectedOrLease, text, logger, cancellationToken = null) {
      return this.typeIntoComposer(expectedOrLease, text, logger, cancellationToken);
    },

    async typeIntoComposer(expectedOrLease, text, logger, cancellationToken = null) {
      if (state.emergencyAbort || !state.isRunning) {
        throw new Error('ABORT_SIGNAL');
      }

      const isLease = Boolean(expectedOrLease?.surface && expectedOrLease?.expected);
      const expected = isLease ? expectedOrLease.expected : expectedOrLease;
      const token = cancellationToken || (isLease ? expectedOrLease.cancellationToken : null);

      if (token?.cancelled) {
        throw new Error('ROW_PROCESSING_CANCELLED');
      }

      if (!expected?.valid) {
        throw new FocusIntegrityError(
          'EXPECTED_CONVERSATION_IDENTITY_MISSING'
        );
      }

      if (typeof text !== 'string' || text.length === 0) {
        throw new Error('EMPTY_REPLY_TEXT');
      }

      const lease = isLease
        ? expectedOrLease
        : DOM.acquireComposerLease(expected, token);
      if (token && !lease.cancellationToken) {
        lease.cancellationToken = token;
      }
      lease.lastKnownText = '';
      let composer = DOM.assertComposerLease(lease);

      const refreshComposer = () => {
        if (token?.cancelled) {
          throw new Error('ROW_PROCESSING_CANCELLED');
        }
        const previousComposer = composer;
        composer = DOM.assertComposerLease(lease);

        if (composer !== previousComposer) {
          this.focusComposerAtEnd(composer);
        }

        return composer;
      };

      const ensureComposerFocus = () => {
        refreshComposer();

        if (document.activeElement !== composer) {
          const activeElement = document.activeElement;
          if (
            activeElement?.matches?.(
              'input, textarea, [role="searchbox"], ' +
              '[placeholder*="بحث" i], [placeholder*="Search" i]'
            )
          ) {
            try {
              activeElement.blur();
            } catch (_) {}
          }

          this.focusComposerAtEnd(composer);
          refreshComposer();
        }

        if (document.activeElement !== composer) {
          throw new FocusIntegrityError(
            'COMPOSER_FOCUS_NOT_ACQUIRED'
          );
        }

        return composer;
      };

      ensureComposerFocus();
      await cancellableSleep(randomRange(70, 120), token);
      ensureComposerFocus();

      const selection = window.getSelection();
      const clearRange = document.createRange();
      clearRange.selectNodeContents(composer);
      selection.removeAllRanges();
      selection.addRange(clearRange);

      try {
        document.execCommand('delete', false, null);
      } catch (_) {
        clearRange.deleteContents();
      }

      refreshComposer();
      await cancellableSleep(randomRange(50, 90), token);
      ensureComposerFocus();

      // UNICODE-SAFE TYPING: code-point iteration via Array.from
      const codePoints = Array.from(text);
      let committedPrefix = '';

      if (logger) {
        logger.log(
          'TYPING',
          `محاكاة كتابة الرد (${codePoints.length} حرف، تذبذب ` +
          `${state.config.minTypingSpeed}-` +
          `${state.config.maxTypingSpeed}ms)...`
        );
      }

      for (let index = 0; index < codePoints.length; index += 1) {
        if (state.emergencyAbort || !state.isRunning) {
          throw new Error('ABORT_SIGNAL');
        }
        if (token?.cancelled) {
          throw new Error('ROW_PROCESSING_CANCELLED');
        }

        ensureComposerFocus();
        this.focusComposerAtEnd(composer);
        refreshComposer();

        const character = codePoints[index];
        const beforeInputAccepted = composer.dispatchEvent(
          new InputEvent('beforeinput', {
            bubbles: true,
            cancelable: true,
            inputType: 'insertText',
            data: character
          })
        );

        if (!beforeInputAccepted) {
          throw new FocusIntegrityError(
            'COMPOSER_BEFOREINPUT_REJECTED'
          );
        }

        let inserted = false;
        try {
          inserted = document.execCommand(
            'insertText',
            false,
            character
          );
        } catch (_) {
          inserted = false;
        }

        if (!inserted) {
          const activeSelection = window.getSelection();
          if (
            !activeSelection ||
            activeSelection.rangeCount === 0
          ) {
            throw new FocusIntegrityError(
              'COMPOSER_INSERT_SELECTION_LOST'
            );
          }

          const activeRange = activeSelection.getRangeAt(0);
          if (!composer.contains(activeRange.commonAncestorContainer)) {
            throw new FocusIntegrityError(
              'COMPOSER_INSERT_RANGE_ESCAPED'
            );
          }

          activeRange.deleteContents();
          const textNode = document.createTextNode(character);
          activeRange.insertNode(textNode);
          activeRange.setStartAfter(textNode);
          activeRange.collapse(true);
          activeSelection.removeAllRanges();
          activeSelection.addRange(activeRange);
        }

        composer.dispatchEvent(
          new InputEvent('input', {
            bubbles: true,
            cancelable: false,
            inputType: 'insertText',
            data: character
          })
        );

        committedPrefix += character;
        lease.lastKnownText = committedPrefix;

        refreshComposer();

        let delay = randomRange(
          state.config.minTypingSpeed,
          state.config.maxTypingSpeed
        );
        if ([' ', '،', '.', '!', '؟'].includes(character)) {
          delay += randomRange(40, 80);
        }

        await cancellableSleep(delay, token);
        refreshComposer();
      }

      if (state.emergencyAbort || !state.isRunning) {
        throw new Error('ABORT_SIGNAL');
      }
      if (token?.cancelled) {
        throw new Error('ROW_PROCESSING_CANCELLED');
      }

      await cancellableSleep(350, token);
      ensureComposerFocus();

      if (logger) {
        logger.log(
          'TYPING',
          'اكتملت الكتابة. إرسال عبر مفتاح Enter...'
        );
      }

      composer.dispatchEvent(
        new KeyboardEvent('keydown', {
          key: 'Enter',
          code: 'Enter',
          keyCode: 13,
          which: 13,
          bubbles: true,
          cancelable: true
        })
      );

      await cancellableSleep(80, token);
      ensureComposerFocus();

      composer.dispatchEvent(
        new KeyboardEvent('keyup', {
          key: 'Enter',
          code: 'Enter',
          keyCode: 13,
          which: 13,
          bubbles: true,
          cancelable: true
        })
      );

      await cancellableSleep(300, token);
      refreshComposer();

      if (state.emergencyAbort || !state.isRunning) {
        throw new Error('ABORT_SIGNAL');
      }
      if (token?.cancelled) {
        throw new Error('ROW_PROCESSING_CANCELLED');
      }

      const currentContent = (
        composer.innerText ||
        composer.textContent ||
        ''
      ).trim();

      const isPlaceholder =
        currentContent.length === 0 ||
        currentContent.includes('رد في Messenger') ||
        currentContent.includes('رد في Instagram') ||
        currentContent.includes('رد في WhatsApp') ||
        currentContent.includes('Reply in');

      if (!isPlaceholder) {
        if (logger) {
          logger.log(
            'TYPING',
            'الضغط الاحتياطي على زر الإرسال (single-dispatch)...'
          );
        }

        DOM.assertConversationIdentity(expected);
        DOM.assertComposerLease(lease);

        const sendButton = DOM.getSendButton(
          lease,
          composer,
          token
        );

        if (!sendButton || !sendButton.isConnected) {
          throw new FocusIntegrityError(
            'VERIFIED_SEND_BUTTON_NOT_FOUND'
          );
        }

        DOM.assertConversationIdentity(expected);
        DOM.assertComposerLease(lease);

        sendButton.dispatchEvent(new MouseEvent('click', {
          bubbles: true,
          cancelable: true,
          view: window
        }));
      }

      await cancellableSleep(600, token);
      refreshComposer();

      const postContent = (
        composer.innerText ||
        composer.textContent ||
        ''
      ).trim();

      const contentStillPresent =
        postContent.length > 0 &&
        !postContent.includes('رد في') &&
        !postContent.includes('Reply in');

      if (contentStillPresent) {
        if (logger) {
          logger.log(
            'ERROR',
            '[DELIVERY FAILED] تعذر إرسال الرسالة. ' +
            'نص الرد لا يزال عالقاً في المحرر.'
          );
        }
        throw new Error(
          'MESSAGE_DELIVERY_VERIFICATION_FAILED'
        );
      }

      await cancellableSleep(300, token);
      DOM.assertConversationIdentity(expected);
      return true;
    }
  };

  // ---------------------------------------------------------------------------
  // TELEMETRY BRIDGE (Bidirectional Remote GUI & Supervisor Telemetry)
  // ---------------------------------------------------------------------------
  function emitTelemetry(type, data) {
    if (typeof window.pyEmitTelemetry === 'function') {
      try {
        window.pyEmitTelemetry(JSON.stringify({
          type,
          data,
          tenantId: state.currentTenantId,
          timestamp: Date.now()
        }));
      } catch (_) {}
    }
  }

  // ---------------------------------------------------------------------------
  // 5. HUD INTERFACE (Shadow DOM Isolated, RTL, Dark Glassmorphism)
  // ---------------------------------------------------------------------------
  class AutomatorHUD {
    constructor() {
      this.container = null;
      this.shadow = null;
      this.activeTab = 'console';
      this.isGhostMode = false;
      this.isHeadless = Boolean(window.__MBS_HEADLESS_MODE__);
      this._popstateBound = false;
      this._rehydrateInterval = null;
      this.init();
    }

    init() {
      this.isHeadless = Boolean(window.__MBS_HEADLESS_MODE__);

      if (!this.isHeadless) {
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
      }

      if (!this._popstateBound) {
        this._popstateBound = true;
        window.addEventListener('popstate', () => {
          checkAndRehydrateTenant(this);
        });
      }

      if (!this._rehydrateInterval) {
        this._rehydrateInterval = setInterval(() => {
          checkAndRehydrateTenant(this);
        }, 2500);
      }

      this.setStatus('READY', 'ready');
      this.log('INIT', `تم تحميل واجهة التحكم بنجاح (Apple Prismatic Liquid Glass Edition V6.5.4)${this.isHeadless ? ' [Headless Agent Mode]' : ''}.`);
    }

    render() {
      if (!this.shadow) return;
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
      if (this.isHeadless || !this.shadow) return;
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
          keywords: ['كلمة_مفتاحية'],
          reply: 'نص الرد الآلي هنا...',
          matchType: 'ultra_exact',
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
    }

    updateTenantUI(tenantId) {
      if (!this.shadow) return;
      const badge = this.shadow.getElementById('hud-tenant-badge');
      if (badge) {
        badge.textContent = tenantId === 'default' ? 'Default Page' : `Page: ${tenantId}`;
      }
    }

    updateConfigUI() {
      if (!this.shadow) return;
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
      if (!this.shadow) return;
      const container = this.shadow.getElementById('rules-container');
      if (!container) return;

      container.innerHTML = state.rules.map((rule, idx) => `
        <div class="rule-card" data-idx="${idx}">
          <div class="rule-header">
            <span class="rule-title">قاعدة #${idx + 1}</span>
            <div style="display: flex; gap: 6px; align-items: center;">
              <select class="rule-match-type" data-idx="${idx}">
                <option value="ultra_exact" ${rule.matchType === 'ultra_exact' ? 'selected' : ''}>تطابق حرفي صارم</option>
                <option value="contains" ${rule.matchType === 'contains' ? 'selected' : ''}>يحتوي</option>
                <option value="exact" ${rule.matchType === 'exact' ? 'selected' : ''}>تطابق كلمة / عبارة بحدود</option>
                <option value="regex" ${rule.matchType === 'regex' ? 'selected' : ''}>تعبير نمطي</option>
              </select>
              <label class="switch">
                <input type="checkbox" class="rule-toggle" data-idx="${idx}" ${rule.active ? 'checked' : ''}>
                <span class="slider"></span>
              </label>
              <button class="rule-del-btn" data-idx="${idx}" style="background:none; border:none; color:#FF453A; cursor:pointer; font-size:12px;">✕</button>
            </div>
          </div>
          <div style="display: flex; gap: 4px; align-items: center;">
            <input type="text" class="rule-keywords-input" data-idx="${idx}" placeholder="الكلمات المفتاحية مفصولة بفاصلة" value="${escapeHtml(rule.keyword || (rule.keywords ? rule.keywords.join(', ') : ''))}">
            <button type="button" class="rule-toggle-literal-btn" data-idx="${idx}" style="background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); color: #38bdf8; border-radius: 4px; padding: 2px 6px; font-size: 10px; cursor: pointer; white-space: nowrap;" title="محرر الكلمات الحرفي (متعدد الأسطر)">محرر حرفي</button>
          </div>
          <div class="rule-literal-panel" data-idx="${idx}" style="display: none; margin-top: 4px; padding: 4px; background: rgba(0,0,0,0.25); border-radius: 4px;">
            <textarea class="rule-literal-textarea" data-idx="${idx}" rows="2" style="width: 100%; font-family: monospace; font-size: 11px; text-align: right;" placeholder="أدخل الكلمة الحرفية بدقة (مع حفظ المسافات والأسطر والفواصل)..."></textarea>
            <div style="display: flex; justify-content: flex-end; gap: 4px; margin-top: 2px;">
              <button type="button" class="rule-add-literal-btn" data-idx="${idx}" style="background: #0284c7; color: #fff; border: none; border-radius: 3px; padding: 2px 6px; font-size: 10px; cursor: pointer;">+ إضافة حرفياً</button>
            </div>
          </div>
          <textarea class="rule-reply-input" data-idx="${idx}" placeholder="نص الرد... (كل سطر جديد يرسل كفقاعة منفصلة)">${rule.reply || ''}</textarea>
          <div style="font-size: 10px; color: rgba(148, 163, 184, 0.9); margin-top: 2px; text-align: right;">💡 كل سطر جديد (Enter) يُرسل كرسالة منفصلة</div>
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

      container.querySelectorAll('.rule-toggle-literal-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const idx = btn.getAttribute('data-idx');
          const panel = container.querySelector(`.rule-literal-panel[data-idx="${idx}"]`);
          if (panel) {
            panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
          }
        });
      });

      container.querySelectorAll('.rule-add-literal-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const idx = parseInt(btn.getAttribute('data-idx'), 10);
          const panel = container.querySelector(`.rule-literal-panel[data-idx="${idx}"]`);
          const textarea = panel ? panel.querySelector('.rule-literal-textarea') : null;
          if (textarea && textarea.value && state.rules[idx]) {
            const r = state.rules[idx];
            if (!Array.isArray(r.keywords)) r.keywords = [];
            r.keywords.push(textarea.value);
            r.keyword = r.keywords.join(', ');
            saveRules();
            this.renderRulesList();
          }
        });
      });

      container.querySelectorAll('.rule-keywords-input').forEach(el => {
        const handler = (e) => {
          const idx = parseInt(e.target.getAttribute('data-idx'), 10);
          if (state.rules[idx]) {
            const r = state.rules[idx];
            r.keyword = e.target.value;
            if (r.matchType === 'ultra_exact') {
              r.keywords = e.target.value ? [e.target.value] : [];
            } else {
              r.keywords = e.target.value.split(/[,،\n]+/).map(k => k.trim()).filter(Boolean);
            }
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
      if (this.shadow) {
        const el = this.shadow.getElementById('hud-status');
        if (el) {
          el.textContent = text;
          el.className = `status-badge status-${type}`;
        }
        const gDot = this.shadow.getElementById('ghost-dot');
        if (gDot) {
          gDot.className = `ghost-dot ${type}`;
        }
      }
      if (window.pyOnStateChange) {
        window.pyOnStateChange(text).catch(() => {});
      }
      emitTelemetry('STATE', { status: text, type });
    }

    updateStats() {
      if (this.shadow) {
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
      }

      if (window.pyUpdateStats) {
        window.pyUpdateStats(state.stats).catch(() => {});
      }
      emitTelemetry('STATS', state.stats);
    }

    log(tag, message) {
      if (this.shadow) {
        const terminal = this.shadow.getElementById('terminal');
        if (terminal) {
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
        }
      }

      if (window.pyLog) {
        window.pyLog(tag, message).catch(() => {});
      }
      emitTelemetry('LOG', { tag, message });
    }
  }

  class OperationBudget {
    constructor(baseIdleMs = 6500, hardMaxMs = 30000, onTimeout = null) {
      this.baseIdleMs = baseIdleMs;
      this.hardMaxMs = hardMaxMs;
      this.onTimeout = onTimeout;
      this.startTime = Date.now();
      this.timer = null;
      this.touch();
    }

    touch(additionalIdleMs = null) {
      if (this.timer) clearTimeout(this.timer);
      const elapsed = Date.now() - this.startTime;
      const remainingHardCap = this.hardMaxMs - elapsed;
      if (remainingHardCap <= 0) {
        if (this.onTimeout) this.onTimeout(new Error('OPERATION_BUDGET_HARD_MAX_EXCEEDED'));
        return;
      }
      const idleTime = additionalIdleMs || this.baseIdleMs;
      const delay = Math.min(idleTime, remainingHardCap);
      this.timer = setTimeout(() => {
        if (this.onTimeout) this.onTimeout(new Error('ROW_TIMEOUT_EXCEEDED'));
      }, delay);
    }

    dispose() {
      if (this.timer) clearTimeout(this.timer);
    }
  }

  class RowTransaction {
    constructor(targetRow, contactName = null, cancellationToken = null) {
      this.targetRow = targetRow;
      this.contactName = contactName;
      this.cancellationToken = cancellationToken || { cancelled: false, reason: null };
      this.expected = DOM.captureExpectedConversation(targetRow, contactName);

      // Pre-click surface snapshot
      const activeIdentity = DOM.getActiveConversationIdentity();
      const activeCanvas = DOM.getVerifiedConversationCanvas();
      const activeComposer = activeCanvas ? DOM.resolveComposer(null, activeCanvas) : null;
      const activeHeaderNode = DOM.getActiveHeaderNode();
      const activeHeaderText = DOM.getActiveChatContactName();
      const activeFingerprint = DOM.getSurfaceFingerprint(activeCanvas);
      const channel = activeIdentity?.channel || null;

      this.preClickSnapshot = Object.freeze({
        identity: activeIdentity,
        canvas: activeCanvas,
        composer: activeComposer,
        headerNode: activeHeaderNode,
        headerText: activeHeaderText,
        fingerprint: activeFingerprint,
        channel: channel
      });

      this.lease = null;
      this.settled = false;
    }

    cancel(reason = 'ROW_PROCESSING_CANCELLED') {
      this.cancellationToken.cancelled = true;
      this.cancellationToken.reason = reason;
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

    _heartbeatInterval: null,
    _isRestarting: false,
    _isLoopActive: false,

    startHeartbeatWatchdog() {
      this.stopHeartbeatWatchdog();
      state.lastHeartbeat = Date.now();
      this._heartbeatInterval = setInterval(async () => {
        if (!state.isRunning || state.emergencyAbort) return;

        const now = Date.now();
        if (state.lastHeartbeat && (now - state.lastHeartbeat > 30000) && !this._isRestarting) {
          this._isRestarting = true;
          console.warn('[SUPERVISOR] تجمد حلقة الأتمتة لأكثر من 30 ثانية دون نبضات قلب. استرجاع ذاتي فوري...');
          if (this.hud) {
            this.hud.log('WARN', '[SUPERVISOR] رصد تجمد في حلقة الأتمتة (>30s). جارٍ الاسترجاع الذاتي وإيقاظ المهام المعلقة...');
          }
          try {
            DOM.deselectActiveChat();
            abortAllSleeps();
          } catch (_) {}
          setTimeout(() => {
            state.lastHeartbeat = Date.now();
            this._isRestarting = false;
            if (state.isRunning && !state.emergencyAbort && !this._isLoopActive) {
              this._isLoopActive = true;
              this.runLoop().catch(e => console.error('[SUPERVISOR] re-run error:', e)).finally(() => { this._isLoopActive = false; });
            }
          }, 1500);
        }
      }, 10000);
    },

    stopHeartbeatWatchdog() {
      if (this._heartbeatInterval) {
        clearInterval(this._heartbeatInterval);
        this._heartbeatInterval = null;
      }
      this._isRestarting = false;
    },

    async start() {
      if (state.isRunning) return;

      abortAllSleeps();
      checkAndRehydrateTenant(this.hud);
      state.isRunning = true;
      state.emergencyAbort = false;
      state.currentIndex = 0;
      state.lastHeartbeat = Date.now();
      this.startHeartbeatWatchdog();
      this.hud.setStatus('RUNNING', 'running');
      await DOM.ensureUnreadFilterActive(this.hud);
      this.hud.log('INIT', 'بدء فحص قائمة المحادثات (تثبيت فلتر غير مقروء التلقائي)...');

      try {
        await this.runLoop();
      } catch (err) {
        if (err.message === 'ABORT_SIGNAL' || state.emergencyAbort) {
          this.hud.log('STOP', 'تم إيقاف الدورة فوراً بناءً على إشارة التوقف.');
        } else {
          state.stats.errors++;
          this.hud.setStatus('ERROR', 'error');
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
      this.stopHeartbeatWatchdog();
      const wasRunning = state.isRunning;
      state.isRunning = false;
      state.emergencyAbort = true;
      abortAllSleeps();

      if (this.hud) {
        this.hud.setStatus('STANDBY', 'stopped');
        if (wasRunning) {
          this.hud.log('STOP', 'الأتمتة متوقفة حالياً.');
        }
      }

      this.clearActiveRowHighlight();
    },

    async runLoop() {
      this._isLoopActive = true;
      try {
        while (state.isRunning && !state.emergencyAbort) {
          try {
            state.lastHeartbeat = Date.now();
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

          // Invalidate active cooldown if snippet changed
          if (key && snippet && state.lastSeenSnippets && state.lastSeenSnippets.has(key)) {
            const prevSnippet = state.lastSeenSnippets.get(key);
            if (prevSnippet && prevSnippet !== snippet) {
              state.chatCooldowns.delete(key);
              state.lastSeenSnippets.set(key, snippet);
            }
          }

          const isCoolingDown = key && state.chatCooldowns && state.chatCooldowns.has(key) && Date.now() < state.chatCooldowns.get(key);
          if (isCoolingDown) {
            continue;
          }

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
              if (k && s && state.lastSeenSnippets && state.lastSeenSnippets.has(k)) {
                const prevS = state.lastSeenSnippets.get(k);
                if (prevS && prevS !== s) {
                  state.chatCooldowns.delete(k);
                  state.lastSeenSnippets.set(k, s);
                }
              }
              const isCoolingDown = k && state.chatCooldowns && state.chatCooldowns.has(k) && Date.now() < state.chatCooldowns.get(k);
              if (isCoolingDown) return false;
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
          try {
            DOM.deselectActiveChat();
          } catch (_) {}
          this.hud.setStatus('MONITORING', 'monitoring');
          this.hud.log('INFO', `اكتمل فحص جميع المحادثات غير المقروءة. وضع المراقبة الذكية بانتظار رسائل جديدة (إعادة الفحص من أول محادثة كل ${state.config.monitoringInterval / 1000} ثوانٍ)...`);
          await sleep(state.config.monitoringInterval);

          if (state.emergencyAbort) break;

          // 4. Clear processedContacts and skippedRows for the new cycle (preserves lastRepliedSnippets, processedSnapshots & chatCooldowns)
          state.processedContacts.clear();
          if (state.skippedRows) state.skippedRows.clear();
          this.hud.setStatus('RUNNING', 'running');
          continue;
        }

        const contactName = DOM.getRowCustomerName(targetRow);
        let contactKey = targetContactKey || DOM.getStableRowKey(targetRow) || (contactName ? `contact_${normalizeArabicText(contactName)}` : `row_${Date.now()}`);
        let rowFingerprint = targetFingerprint || `${contactKey}__${DOM.getRowSnippet(targetRow)}`;
        try {
          DOM.clearStaleComposerDraft();
        } catch (_) {}

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

        const rowCancellation = { cancelled: false, reason: null };
        const rowTransaction = new RowTransaction(targetRow, contactName, rowCancellation);
        let rowTimeoutId = null;
        let extendWatchdog = null;
        let operationBudget = null;
        try {
          const timeoutPromise = new Promise((_, reject) => {
            // Activation deadline is >= 5000ms, initialize with 6500ms base budget
            operationBudget = new OperationBudget(6500, 30000, (err) => reject(err));
            extendWatchdog = (additionalMs) => {
              if (operationBudget) operationBudget.touch(additionalMs);
            };
          });

          const processRowPromise = (async () => {
            try {
              if (rowCancellation.cancelled) {
                return { skipLoop: true, cooldown: 0 };
              }

              // STEP 2: Atomic Target Identity Capture & Activation
              const expectedConversation = rowTransaction.expected;

              if (!expectedConversation.valid) {
                throw new FocusIntegrityError(
                  `TARGET_IDENTITY_CAPTURE_FAILED:` +
                  `${expectedConversation.reason}`
                );
              }

              if (expectedConversation.leaseKey) {
                contactKey = expectedConversation.leaseKey;
                rowFingerprint =
                  `${contactKey}__${DOM.getRowSnippet(targetRow)}`;
              }

              if (typeof extendWatchdog === 'function') {
                extendWatchdog(6500);
              }

              const clickTarget = DOM.getRowClickTarget(targetRow);
              await HumanSimulator.naturalClick(clickTarget);

              this.hud.log(
                'SCAN',
                'انتظار تطابق هوية نافذة المحادثة مع العميل...'
              );

              const surfaceLease = await DOM.waitForConversationLoad(
                expectedConversation,
                targetRow,
                clickTarget,
                this.hud,
                rowCancellation,
                rowTransaction.preClickSnapshot
              );

              if (!surfaceLease) {
                throw new FocusIntegrityError(
                  'TARGET_CONVERSATION_DID_NOT_LOAD'
                );
              }

              rowTransaction.lease = surfaceLease;

              if (typeof extendWatchdog === 'function') {
                extendWatchdog(4000);
              }

              if (state.config.scrollThread) {
                await HumanSimulator.simulateThreadScroll(this.hud, surfaceLease, rowCancellation);
              } else {
                await cancellableSleep(randomRange(150, 250), rowCancellation);
              }

              DOM.assertComposerLease(surfaceLease);

              // STEP 3: Inbound Boundary Evaluation & Message Extraction Guard
              this.hud.log('SCAN', 'فحص حدود الرسائل (الرسائل الواردة بعد آخر رد من الصفحة)...');
              let boundaryResult = null;
              try {
                boundaryResult = DOM.parseInboundBoundary(surfaceLease, rowCancellation);
              } catch (boundaryErr) {
                this.hud.log('WARN', `استثناء أثناء فحص حدود الرسائل: ${boundaryErr?.message || boundaryErr}. استعادة كغير مقروء لمراجعة خدمة العملاء...`);
                if (typeof extendWatchdog === 'function') {
                  extendWatchdog(8500);
                }
                await this.executeBranchB(contactKey, rowFingerprint, targetRow, extendWatchdog);
                const cooldown = randomRange(state.config.minCooldown, state.config.maxCooldown);
                return { skipLoop: true, cooldown };
              }

              const { lastIsOutbound, customerBubbles, isVoiceOrMedia, tailBubble } = boundaryResult;

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

              // Detect Voice Note / Audio / Media at the tail of the conversation
              const isTrailingVoice = isVoiceOrMedia || DOM.hasTrailingAudioOrMedia(surfaceLease);
              if (isTrailingVoice) {
                this.hud.log('INFO', '[صوت/وسائط] آخر رسالة واردة من العميل هي تسجيل صوتي أو وسائط. تحويل لمراجعة خدمة العملاء كغير مقروءة مع كول داون دقيقتين...');
                if (typeof extendWatchdog === 'function') {
                  extendWatchdog(8500);
                }
                await this.executeBranchB(contactKey, rowFingerprint, targetRow, extendWatchdog);
                const cooldown = randomRange(state.config.minCooldown, state.config.maxCooldown);
                return { skipLoop: true, cooldown };
              }

              // WhatsApp Unsupported Message Detection:
              const canvas = DOM.getChatCanvas(surfaceLease);
              const canvasText = canvas ? (canvas.innerText || '') : '';
              const hasUnsupportedWhatsApp = [
                "Message can't be displayed",
                "which is not supported in Inbox",
                "WhatsApp Business App",
                "محتوى غير مدعوم"
              ].some(indicator => canvasText.includes(indicator));

              if (hasUnsupportedWhatsApp && customerBubbles.length === 0) {
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

              if (customerBubbles.length === 0) {
                this.hud.log('INFO', 'لا توجد نصوص رسائل واردة جديدة قابلة للمعالجة (وسائط أو رسالة نظام/واتساب). استعادة كغير مقروء...');
                if (typeof extendWatchdog === 'function') {
                  extendWatchdog(8500);
                }
                await this.executeBranchB(contactKey, rowFingerprint, targetRow, extendWatchdog);

                const cooldown = randomRange(state.config.minCooldown, state.config.maxCooldown);
                return { skipLoop: true, cooldown };
              }

              // STEP 4: Strict Customer Tail Message Evaluation
              const latestBubble = customerBubbles[customerBubbles.length - 1];
              await HumanSimulator.highlightCustomerBubble(latestBubble);

              const latestText = (latestBubble ? DOM.extractTextWithAlt(latestBubble) : '').trim();
              const verbatimText = latestBubble ? DOM.extractMessageTextVerbatim(latestBubble) : '';

              if (!latestText && !verbatimText) {
                this.hud.log('INFO', 'آخر رسالة من العميل لا تحتوي على نص قابل للمعالجة (ملصق/صورة/وسائط). استعادة كغير مقروء...');
                if (typeof extendWatchdog === 'function') {
                  extendWatchdog(8500);
                }
                await this.executeBranchB(contactKey, rowFingerprint, targetRow, extendWatchdog);

                const cooldown = randomRange(state.config.minCooldown, state.config.maxCooldown);
                return { skipLoop: true, cooldown };
              }

              const snippet = latestText.length > 40 ? latestText.slice(0, 40) + '...' : latestText;
              this.hud.log('SCAN', `فحص آخر رسالة واردة من العميل: "${snippet}"`);

              const allBubbles = DOM.getMessageBubbles(surfaceLease, rowCancellation);
              const contextText = DOM.extractThreadContext(allBubbles, surfaceLease);

              let matchResult = null;
              try {
                if (verbatimText !== null && verbatimText !== '') {
                  matchResult = await evaluateActiveRules(verbatimText, state.rules, contextText);
                } else if (verbatimText === '' && latestText) {
                  matchResult = await evaluateActiveRules(latestText, state.rules, contextText);
                }
              } catch (evalErr) {
                this.hud.log('WARN', `خطأ أثناء مطابقة القواعد: ${evalErr?.message || evalErr}`);
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
                if (matchResult.isCompound) {
                  this.hud.log('MATCH', `[تطابق مركب] تطابق الكلمة: "${matchedKeyword}" مع سياق الإعلان: "${matchResult.matchedContextKeyword}". جاري إرسال الرد المخصص للعميل ${contactName || contactKey}...`);
                } else {
                  this.hud.log('MATCH', `تطابق الكلمة: "${matchedKeyword}". جاري إرسال الرد للعميل ${contactName || contactKey}...`);
                }

                let composer = DOM.getComposer(surfaceLease);

                if (!composer) {
                  throw new FocusIntegrityError(
                    'VERIFIED_COMPOSER_UNAVAILABLE'
                  );
                }

                const replies = DOM.parseSequentialReplies(
                  rule.reply
                );

                if (replies.length === 0) {
                  this.hud.log(
                    'WARN',
                    'نص الرد فارغ. تعذر الإرسال.'
                  );
                } else {
                  const totalChars = replies.reduce(
                    (total, replyText) => total + replyText.length,
                    0
                  );
                  const neededMs = Math.max(
                    9000,
                    5000 +
                    totalChars * 80 +
                    replies.length * 2200
                  );

                  if (typeof extendWatchdog === 'function') {
                    extendWatchdog(neededMs);
                  }

                  DOM.assertComposerLease(surfaceLease);
                  composer = DOM.getComposer(surfaceLease);

                  const draftCheck = DOM.clearStaleComposerDraft(
                    this.hud,
                    composer
                  );

                  if (draftCheck?.humanDraft) {
                    this.hud.log(
                      'WARN',
                      '[DRAFT SAFETY] تم حفظ مسودة الموظف البشري. ' +
                      'تخطي الرد الآلي وتحويل المحادثة للمراجعة.'
                    );

                    await this.executeBranchB(
                      contactKey,
                      rowFingerprint,
                      targetRow,
                      operationBudget || extendWatchdog
                    );
                    return { skipLoop: false };
                  }

                  // Milestone 2 will replace this inbound baseline.
                  const preSendInbound = DOM.getMessageBubbles(surfaceLease)
                    .filter(bubble => !DOM.isOutboundBubble(bubble, surfaceLease));
                  const preSendTailInbound =
                    preSendInbound.length > 0
                      ? preSendInbound[preSendInbound.length - 1]
                      : null;
                  const preSendTailText = preSendTailInbound
                    ? DOM.extractTextWithAlt(preSendTailInbound).trim()
                    : '';
                  const preSendInboundCount = preSendInbound.length;

                  for (
                    let replyIndex = 0;
                    replyIndex < replies.length;
                    replyIndex += 1
                  ) {
                    if (state.emergencyAbort || !state.isRunning) {
                      break;
                    }
                    if (rowCancellation.cancelled) {
                      throw new Error('ROW_PROCESSING_CANCELLED');
                    }

                    composer = DOM.assertComposerLease(surfaceLease);

                    const replyText = replies[replyIndex];
                    const snippetText = replyText.length > 25
                      ? `${replyText.substring(0, 25)}...`
                      : replyText;

                    this.hud.log(
                      'TYPING',
                      `إرسال الفقاعة (` +
                      `${replyIndex + 1}/${replies.length}): ` +
                      `"${snippetText}"`
                    );

                    claimBotDraft(
                      composer,
                      expectedConversation.leaseKey,
                      replyText
                    );

                    try {
                      await HumanSimulator.typeIntoComposer(
                        surfaceLease,
                        replyText,
                        this.hud,
                        rowCancellation
                      );

                      clearBotDraftSessionRecord(
                        expectedConversation.leaseKey
                      );
                    } catch (typeError) {
                      if (
                        typeError instanceof FocusIntegrityError ||
                        typeError?.name === 'FocusIntegrityError' ||
                        typeError?.message ===
                          'MESSAGE_DELIVERY_VERIFICATION_FAILED'
                      ) {
                        this.hud.log(
                          'ERROR',
                          `[DELIVERY/FOCUS FAILURE] ` +
                          `فشل الإرسال أو انحراف التركيز ` +
                          `(${typeError.message}). ` +
                          `استعادة المحادثة كغير مقروءة...`
                        );

                        await this.executeBranchB(
                          contactKey,
                          rowFingerprint,
                          targetRow,
                          operationBudget || extendWatchdog
                        );

                        const cooldownKey =
                          contactKey || targetContactKey;
                        if (cooldownKey) {
                          state.chatCooldowns.set(
                            cooldownKey,
                            Date.now() + 3 * 60 * 1000
                          );
                        }

                        return {
                          skipLoop: true,
                          cooldown: 1800
                        };
                      }

                      throw typeError;
                    }

                    if (replyIndex < replies.length - 1) {
                      const cleared = await DOM.waitForComposerClear(
                        surfaceLease,
                        1800,
                        rowCancellation
                      );

                      if (!cleared) {
                        throw new Error(
                          'COMPOSER_DID_NOT_CLEAR_BETWEEN_REPLIES'
                        );
                      }

                      await cancellableSleep(randomRange(900, 1500), rowCancellation);
                    }
                  }

                  // [TASK-1] Post-Send Verification Sweep for mid-typing customer messages
                  await cancellableSleep(700, rowCancellation);

                  const postSendBubbles = DOM.getMessageBubbles(surfaceLease);
                  const postSendInbound = postSendBubbles.filter(b => !DOM.isOutboundBubble(b, surfaceLease));

                  let midFlightBubbles = [];
                  if (postSendInbound.length > preSendInboundCount) {
                    midFlightBubbles = postSendInbound.slice(preSendInboundCount);
                  } else if (postSendInbound.length > 0) {
                    const latestPostInbound = postSendInbound[postSendInbound.length - 1];
                    const latestPostText = DOM.extractTextWithAlt(latestPostInbound).trim();
                    if (latestPostText && latestPostText !== preSendTailText && !preSendInbound.includes(latestPostInbound)) {
                      midFlightBubbles = [latestPostInbound];
                    }
                  }

                  if (midFlightBubbles.length > 0) {
                    const midFlightText = midFlightBubbles.map(b => DOM.extractTextWithAlt(b)).join(' ').trim();
                    this.hud.log('WARN', `[MID-TYPING] رصد رسالة جديدة من العميل أثناء الكتابة: "${midFlightText.slice(0, 40)}..."`);

                    const postContextText = DOM.extractThreadContext(postSendBubbles, surfaceLease);
                    // Evaluate active rules against each mid-flight bubble individually (never concatenated)
                    let midMatch = null;
                    for (let bIdx = midFlightBubbles.length - 1; bIdx >= 0; bIdx--) {
                      const bubble = midFlightBubbles[bIdx];
                      const bubbleVerbatim = DOM.extractMessageTextVerbatim(bubble);
                      const bubbleAlt = (DOM.extractTextWithAlt(bubble) || '').trim();
                      const targetBubbleText = (bubbleVerbatim !== null && bubbleVerbatim !== '') ? bubbleVerbatim : bubbleAlt;
                      if (targetBubbleText) {
                        midMatch = await evaluateActiveRules(targetBubbleText, state.rules, postContextText);
                        if (midMatch) break;
                      }
                    }

                    if (midMatch && midMatch.rule) {
                      if (midMatch.isCompound) {
                        this.hud.log('MATCH', `[MID-TYPING] [تطابق مركب] مطابقة قاعدة للرسالة المتداخلة (${midMatch.matchedKeyword} + ${midMatch.matchedContextKeyword}). جاري إرسال الرد المكمل...`);
                      } else {
                        this.hud.log('MATCH', `[MID-TYPING] مطابقة قاعدة للرسالة المتداخلة (${midMatch.matchedKeyword}). جاري إرسال الرد المكمل...`);
                      }
                      const followUpReplies =
                        typeof splitMessage === 'function'
                          ? splitMessage(midMatch.rule.reply)
                          : DOM.parseSequentialReplies(
                              midMatch.rule.reply
                            );

                      for (
                        let followUpIndex = 0;
                        followUpIndex < followUpReplies.length;
                        followUpIndex += 1
                      ) {
                        if (rowCancellation.cancelled) {
                          throw new Error('ROW_PROCESSING_CANCELLED');
                        }

                        composer = DOM.assertComposerLease(surfaceLease);

                        const followUpText =
                          followUpReplies[followUpIndex];

                        claimBotDraft(
                          composer,
                          expectedConversation.leaseKey,
                          followUpText
                        );

                        try {
                          await HumanSimulator.typeIntoComposer(
                            surfaceLease,
                            followUpText,
                            this.hud,
                            rowCancellation
                          );

                          clearBotDraftSessionRecord(
                            expectedConversation.leaseKey
                          );
                        } catch (followUpError) {
                          if (
                            followUpError instanceof FocusIntegrityError ||
                            followUpError?.name === 'FocusIntegrityError' ||
                            followUpError?.message === 'ROW_PROCESSING_CANCELLED'
                          ) {
                            throw followUpError;
                          }

                          this.hud.log(
                            'ERROR',
                            `[MID-TYPING] تعذر إرسال الرد المكمل: ` +
                            `${followUpError.message}`
                          );
                          break;
                        }

                        if (
                          followUpIndex <
                          followUpReplies.length - 1
                        ) {
                          const cleared = await DOM.waitForComposerClear(
                            surfaceLease,
                            1800,
                            rowCancellation
                          );

                          if (!cleared) {
                            throw new Error(
                              'FOLLOW_UP_COMPOSER_DID_NOT_CLEAR'
                            );
                          }

                          await cancellableSleep(randomRange(800, 1400), rowCancellation);
                        }
                      }
                    } else {
                      // No match: Customer asked something else while we were typing -> Hand off to Human Agent
                      this.hud.log('UNREAD', '[MID-TYPING ESCALATION] لا توجد كلمات مطابقة للرسالة المتداخلة. إجبار استعادة المحادثة كغير مقروءة وتأمين التهدئة لمنع التجاهل...');

                      // 1. Evict from processed caches so it remains eligible for human review
                      if (contactKey) state.processedContacts.delete(contactKey);
                      if (rowFingerprint) state.processedSnapshots.delete(rowFingerprint);

                      // 2. Lock with 5-minute cooldown to neutralize the Re-Scan Trap
                      if (contactKey) {
                        state.chatCooldowns.set(contactKey, Date.now() + 5 * 60 * 1000);
                      }

                      // 3. Force unread restoration
                      await this.executeBranchB(contactKey, rowFingerprint, targetRow, operationBudget || extendWatchdog);
                      return { skipLoop: true, cooldown: 1500 };
                    }
                  }

                  this.hud.log('INFO', `تم إرسال كافة الردود بنجاح للعميل ${contactName || contactKey} (${replies.length} فقاعة).`);
                }
              } else {
                // Branch B: No Match / Media Message / Skip
                this.hud.log('SCAN', 'لا توجد كلمات مفتاحية مطابقة في رسالة العميل. استعادة المحادثة كغير مقروءة لمراجعة خدمة العملاء...');
                if (typeof extendWatchdog === 'function') {
                  extendWatchdog(8500);
                }
                await this.executeBranchB(contactKey, rowFingerprint, targetRow, extendWatchdog);
              }

              return { skipLoop: false };
            } catch (innerErr) {
              if (innerErr?.message === 'ROW_PROCESSING_CANCELLED' || rowCancellation.cancelled) {
                return { skipLoop: true, cooldown: 0 };
              }
              throw innerErr;
            }
          })();

          let rowResult = null;
          try {
            rowResult = await Promise.race([processRowPromise, timeoutPromise]);
          } catch (raceErr) {
            rowCancellation.cancelled = true;
            rowCancellation.reason = raceErr?.message || 'ROW_TIMEOUT_EXCEEDED';
            rowTransaction.cancel(rowCancellation.reason);
            await Promise.allSettled([processRowPromise]);
            rowTransaction.settled = true;
            throw raceErr;
          } finally {
            rowCancellation.cancelled = true;
            rowCancellation.reason = rowCancellation.reason || 'ROW_RACE_SETTLED_OR_TIMED_OUT';
            rowTransaction.cancel(rowCancellation.reason);
            await Promise.allSettled([processRowPromise]);
            rowTransaction.settled = true;
            // [P1-WATCH-01] Guaranteed OperationBudget disposal to prevent dangling timers
            if (operationBudget) operationBudget.dispose();
            if (rowTimeoutId) clearTimeout(rowTimeoutId);
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
          if (err && (err.message === 'ROW_TIMEOUT_EXCEEDED' || err.message === 'OPERATION_BUDGET_HARD_MAX_EXCEEDED')) {
            this.hud.log('WARN', `[WATCHDOG] تم تجاوز مهلة معالجة المحادثة (${err.message})، استعادة كغير مقروءة وتخطي فوري.`);
            try {
              await this.executeBranchB(contactKey, rowFingerprint, targetRow, null);
            } catch (_) {}
            try {
              DOM.sendEscape();
              releaseChatFocus();
            } catch (_) {}
            const cooldownKey = contactKey || targetContactKey;
            if (cooldownKey) {
              state.chatCooldowns.set(cooldownKey, Date.now() + (3 * 60 * 1000)); // 3 minutes cooldown
              pruneLRUCache(state.chatCooldowns, 500, 100);
            }
            if (targetContactKey) state.skippedRows.add(targetContactKey);
            if (contactKey) state.skippedRows.add(contactKey);
            if (rowFingerprint) {
              state.skippedRows.add(rowFingerprint);
              pruneLRUCache(state.skippedRows, 350, 100);
            }
            continue;
          }

          // [P0-DOM-01] Safety Guard: Focus or delivery failure must restore to unread and NOT mark as processed
          if (err instanceof FocusIntegrityError || (err && err.name === 'FocusIntegrityError') || (err && err.message === 'MESSAGE_DELIVERY_VERIFICATION_FAILED')) {
            this.hud.log('ERROR', `[SAFETY GUARD] تم رصد خطأ تركيز/إرسال (${err.message}). استعادة كغير مقروءة وتأمين المحادثة.`);
            try {
              await this.executeBranchB(contactKey, rowFingerprint, targetRow, null);
            } catch (_) {}
            try {
              DOM.sendEscape();
              releaseChatFocus();
            } catch (_) {}
            const cooldownKey = contactKey || targetContactKey;
            if (cooldownKey) {
              state.chatCooldowns.set(cooldownKey, Date.now() + (3 * 60 * 1000));
            }
            continue;
          }

          this.hud.log('WARN', `تخطي استثنائي للمحادثة الحالية لتفادي التجمد: ${err?.message || err}`);
          try {
            DOM.sendEscape();
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
            DOM.deselectActiveChat();
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
        pruneLRUCache(state.lastSeenSnippets, 500, 100);
        pruneLRUCache(state.processedSnapshots, 350, 100);
        pruneLRUCache(state.chatCooldowns, 500, 100);

        const cooldown = randomRange(state.config.minCooldown, state.config.maxCooldown);
        this.hud.setStatus(`COOLDOWN (${(cooldown / 1000).toFixed(1)}s)`, 'cooldown');
        this.hud.log('INFO', `تهدئة بشرية: انتظار ${(cooldown / 1000).toFixed(1)} ثانية...`);
        await sleep(cooldown);
        this.hud.setStatus('RUNNING', 'running');
          } catch (loopErr) {
            if (state.emergencyAbort || loopErr?.message === 'ABORT_SIGNAL') {
              break;
            }
            console.error('[SUPERVISOR] انقطاع غير متوقع في حلقة الأتمتة، جارٍ إعادة التشغيل الذاتي...', loopErr);
            if (this.hud) {
              this.hud.log('WARN', '[SUPERVISOR] رصد خطأ في حلقة الفحص. جارٍ الاسترجاع الذاتي خلال 3 ثوانٍ...');
            }
            try {
              this.clearActiveRowHighlight();
              DOM.deselectActiveChat();
            } catch (_) {}
            try {
              await sleep(3000);
            } catch (_) {}
          }
        }
      } finally {
        this._isLoopActive = false;
      }
    },

    async executeBranchB(contactKey, rowFingerprint, targetRow, watchdogExtender = null) {
      if (typeof watchdogExtender === 'function') {
        watchdogExtender(8500);
      }
      try {
        DOM.clearStaleComposerDraft(this.hud);
      } catch (_) {}
      if (contactKey) {
        state.processedContacts.add(contactKey);
        state.chatCooldowns.set(contactKey, Date.now() + (2 * 60 * 1000)); // 2 minutes cooldown (120s)
        pruneLRUCache(state.chatCooldowns, 500, 100);

        if (targetRow) {
          const s = DOM.getRowSnippet(targetRow);
          if (s) {
            state.lastSeenSnippets.set(contactKey, s);
            pruneLRUCache(state.lastSeenSnippets, 500, 100);
          }
        }
      }
      if (rowFingerprint) {
        state.processedSnapshots.add(rowFingerprint);
        pruneLRUCache(state.processedSnapshots, 350, 100);
      }

      await sleep(randomRange(150, 250));
      const restored = await DOM.executeRestoreToUnread(this.hud, targetRow, contactKey, watchdogExtender);
      try {
        DOM.deselectActiveChat();
      } catch (_) {}

      if (restored) {
        state.stats.unreadRestored++;
        this.hud.updateStats();
        this.hud.log('UNREAD', '[UNREAD] تم تمييز المحادثة كغير مقروءة بنجاح (كول داون دقيقتين).');
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
      if (window.__MBS_AUTOMATOR_HUD__ && !window.__MBS_AUTOMATOR_HUD__.isHeadless) {
        window.__MBS_AUTOMATOR_HUD__.updateConfigUI();
      }
    } catch (_) {}
  };

  // Remote Supervisor Runtime Command Dispatcher
  window.__MBS_EXEC_COMMAND__ = (cmd, payload) => {
    switch (cmd) {
      case 'START':
        return Orchestrator.start();
      case 'STOP':
        return Orchestrator.stop();
      case 'APPLY_RULE_SNAPSHOT':
        if (payload) {
          try {
            let parsed = typeof payload === 'string' ? JSON.parse(payload) : payload;
            let rulesList = parsed;
            if (parsed && typeof parsed === 'object' && !Array.isArray(parsed) && parsed.rules) {
              rulesList = parsed.rules;
              if (parsed.sha256_token) {
                window.__CONFIG_SHA256__ = parsed.sha256_token;
              }
            }
            state.rules = Array.isArray(rulesList) ? rulesList : [];
            window.__INITIAL_RULES__ = state.rules;
            // NON-PERSISTING: Strictly in-memory & HUD update.
            // MUST NOT call saveRules(), localStorage.setItem(), or window.pySaveConfig().
            if (window.__MBS_AUTOMATOR_HUD__) {
              window.__MBS_AUTOMATOR_HUD__.renderRulesList();
              window.__MBS_AUTOMATOR_HUD__.log('RULES', `تم استلام وتطبيق لقطة القواعد فورياً (${state.rules.length} قاعدة).`);
            }
          } catch (e) {
            console.warn('[MBS Automator] Failed to apply rule snapshot:', e);
          }
        }
        break;
      case 'RELOAD_RULES':
        if (payload) {
          try {
            state.rules = typeof payload === 'string' ? JSON.parse(payload) : payload;
            if (!Array.isArray(state.rules)) state.rules = [];
            window.__INITIAL_RULES__ = state.rules;
            saveRules();
            if (window.__MBS_AUTOMATOR_HUD__) {
              window.__MBS_AUTOMATOR_HUD__.renderRulesList();
              window.__MBS_AUTOMATOR_HUD__.log('RULES', `تم تحديث القواعد فورياً (${state.rules.length} قاعدة نشطة).`);
            }
          } catch (e) {
            console.warn('[MBS Automator] Failed to reload rules from payload:', e);
          }
        } else {
          checkAndRehydrateTenant(window.__MBS_AUTOMATOR_HUD__);
        }
        break;
      case 'RELOAD_CONFIG':
      case 'UPDATE_CONFIG':
        if (payload) {
          try {
            const cfg = typeof payload === 'string' ? JSON.parse(payload) : payload;
            state.config = { ...state.config, ...cfg };
            saveConfig();
            if (window.__MBS_AUTOMATOR_HUD__) {
              if (!window.__MBS_AUTOMATOR_HUD__.isHeadless) {
                window.__MBS_AUTOMATOR_HUD__.updateConfigUI();
              }
              window.__MBS_AUTOMATOR_HUD__.log('CONFIG', 'تم تحديث إعدادات الأتمتة فورياً من لوحة التحكم.');
            }
          } catch (e) {
            console.warn('[MBS Automator] Failed to update config from payload:', e);
          }
        }
        break;
      default:
        console.warn(`[MBS Automator] Unknown command: ${cmd}`);
    }
  };

  console.log('[MBS Automator V6.5.4] Initialized successfully (Enterprise Hardened Edition — P0/P1/P2 Remediations Applied).');
})();

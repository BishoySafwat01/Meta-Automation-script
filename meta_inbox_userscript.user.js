// ==UserScript==
// @name         Meta Business Suite Inbox Auto-Responder & Unread Restorer (Production V4.4.2)
// @namespace    https://github.com/meta-suite-automation/tampermonkey
// @version      4.4.2
// @description  Automates Meta Business Suite Inbox (RTL Arabic) with Sequential Queue, Expanded Envelope Locator & Dropdown Fallback, Clean Ad Filters, Visual Framing, Post-Agent Inbound Boundary Parsing, and Standby Monitoring.
// @author       Principal Frontend Architect & Reverse-Engineering Architect
// @match        https://business.facebook.com/latest/inbox/*
// @match        https://business.facebook.com/latest/inbox/all*
// @icon         https://www.facebook.com/favicon.ico
// @grant        none
// @run-at       document-idle
// ==/UserScript==

/**
 * ============================================================================
 * META BUSINESS SUITE INBOX AUTOMATOR (V4.4.2 PRODUCTION GRADE)
 * ============================================================================
 * ARCHITECTURAL SPECIFICATION & FEATURES:
 * 1. SEQUENTIAL & DYNAMIC QUEUE PROGRESSION:
 *    - Sequential traversal with natural sidebar scrolling (scrollBy top: 220).
 *    - Stable contact tracking to prevent duplicate processing.
 * 2. EXPANDED ENVELOPE (✉) LOCATOR & DROPDOWN MENU FALLBACK:
 *    - Direct toolbar query (top < 380, left < 55%).
 *    - Sibling search adjacent to Done (✓ / تم).
 *    - Responsive Dropdown Fallback: automatically expands "فتح القائمة المنسدلة"
 *      and triggers "تمييز كغير مقروءة" on compact and laptop displays.
 * 3. POST-AGENT INBOUND BOUNDARY PARSING:
 *    - Evaluates customer messages arriving strictly AFTER the last agent reply.
 *    - Immediately skips and restores unread if the latest thread message is outbound.
 * 4. COMPLETE VISUAL SUPERVISION & FRAMING:
 *    - Sky-blue border (3px solid #38bdf8 with soft glow) on active row.
 *    - Green dashed frame (2px dashed #22c55e) on evaluated customer bubble for 500ms.
 *    - Green pulse outline (2px solid #22c55e with glow) on envelope button for 400ms.
 * 5. HUMAN SIMULATOR:
 *    - Character-by-character typing with natural jitter (35-65ms) and punctuation delays.
 *    - Lexical composer clearing verification.
 *    - Natural human cooldowns (1.5s - 2.5s).
 * 6. ISOLATED SHADOW DOM HUD:
 *    - Complete dark glassmorphism HUD mounted in an open Shadow DOM.
 *    - Live terminal logs, live stats, rule manager with active toggles and match types,
 *      and human timing configuration.
 *    - Global [Escape] key emergency kill switch with e.isTrusted verification.
 * ============================================================================
 */

(function () {
  'use strict';

  if (window.__MBS_AUTOMATOR_V44_LOADED__) {
    console.log('[MBS Automator] Already mounted. Re-initializing HUD...');
    if (window.__MBS_AUTOMATOR_HUD__) {
      window.__MBS_AUTOMATOR_HUD__.init();
    }
    return;
  }
  window.__MBS_AUTOMATOR_V44_LOADED__ = true;

  // ---------------------------------------------------------------------------
  // 1. STATE CONFIGURATION & PERSISTENCE
  // ---------------------------------------------------------------------------
  const STORAGE_KEY_RULES = 'MBS_AUTO_RULES_V44';
  const STORAGE_KEY_CONFIG = 'MBS_AUTO_CONFIG_V44';

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
    rules: loadRules(),
    config: loadConfig(),
    processedContacts: new Set(),
    repliedContacts: new Set(),
    processedSnapshots: new Set(),
    activeRowElement: null,
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
      const data = localStorage.getItem(STORAGE_KEY_RULES);
      if (data) {
        const parsed = JSON.parse(data);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch (_) {}
    return JSON.parse(JSON.stringify(defaultRules));
  }

  function saveRules() {
    try {
      localStorage.setItem(STORAGE_KEY_RULES, JSON.stringify(state.rules));
      if (window.pySaveConfig) {
        window.pySaveConfig(JSON.stringify(state.rules), JSON.stringify(state.config)).catch(() => {});
      }
    } catch (_) {}
  }

  function loadConfig() {
    try {
      if (window.__INITIAL_CONFIG__ && typeof window.__INITIAL_CONFIG__ === 'object') {
        return { ...defaultConfig, ...window.__INITIAL_CONFIG__ };
      }
      const data = localStorage.getItem(STORAGE_KEY_CONFIG);
      if (data) return { ...defaultConfig, ...JSON.parse(data) };
    } catch (_) {}
    return { ...defaultConfig };
  }

  function saveConfig() {
    try {
      localStorage.setItem(STORAGE_KEY_CONFIG, JSON.stringify(state.config));
      if (window.pySaveConfig) {
        window.pySaveConfig(JSON.stringify(state.rules), JSON.stringify(state.config)).catch(() => {});
      }
    } catch (_) {}
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

  const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
  const randomRange = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

  // ---------------------------------------------------------------------------
  // 3. DOM REVERSE-ENGINEERING & SELECTORS
  // ---------------------------------------------------------------------------
  const DOM = {
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

    getRowCustomerName(row) {
      if (!row) return '';
      const aria = row.getAttribute('aria-label');
      if (aria && !aria.includes('inbox') && !aria.includes('message')) {
        return aria.split(/[,،\n]/)[0].trim();
      }

      const bolds = Array.from(row.querySelectorAll('span, div, h2, h3, strong')).filter(el => {
        const w = parseInt(window.getComputedStyle(el).fontWeight, 10) || 400;
        const txt = (el.innerText || '').trim();
        return w >= 600 && txt.length >= 2 && txt.length <= 40 &&
               !txt.includes(':') && !txt.includes('Messenger') && !txt.includes('Instagram');
      });

      if (bolds.length > 0) return bolds[0].innerText.trim();

      const lines = (row.innerText || '').split('\n').map(l => l.trim()).filter(Boolean);
      for (const line of lines) {
        if (line.length > 1 && !/^[0-9]+[ ]*(م|ص|د|س)$/.test(line) && !line.includes('Messenger') && !line.includes('Instagram') && !line.includes(':')) {
          return line;
        }
      }
      return lines[0] || '';
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
      const lines = (row.innerText || '').split('\n').map(l => l.trim()).filter(Boolean);
      return lines.slice(1).join(' | ');
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
      // 1. Primary heading in contact details panel (top 70-160, left < 400)
      const headings = Array.from(document.querySelectorAll('[role="heading"], h1, h2, h3')).filter(el => {
        if (el.closest('#mbs-inbox-automator-root')) return false;
        const r = el.getBoundingClientRect();
        const t = (el.innerText || '').trim();
        return r.top >= 70 && r.top <= 160 && r.left < 400 && r.width > 0 &&
               !['البريد الوارد', 'تفاصيل الاتصال', 'التسميات', 'الملاحظات', 'Inbox', 'Contact Details', 'Labels', 'Notes'].includes(t);
      });
      if (headings.length > 0) {
        return headings[0].innerText.trim();
      }

      // 2. Chat header / banner heading fallback
      const chatCanvas = this.getChatCanvas();
      if (chatCanvas) {
        const header = chatCanvas.querySelector('header, div[role="banner"]') || chatCanvas.parentElement?.querySelector('header');
        if (header) {
          const heading = header.querySelector('h1, h2, div[role="heading"], span[style*="font-weight"]');
          if (heading) return heading.innerText?.trim() || '';
        }
      }
      const topName = document.querySelector('div[role="main"] div[style*="font-weight"], main div[style*="font-weight"]');
      if (topName) return topName.innerText?.trim() || '';
      return '';
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

    async executeRestoreToUnread(logger) {
      const maxLeft = 500;

      // 1. Direct Envelope Button (in chat toolbar, strictly left < 500, top < 250)
      const selectors = [
        'button[aria-label*="غير مقروء" i]',
        'button[aria-label*="unread" i]',
        'div[role="button"][aria-label*="غير مقروء" i]',
        'div[role="button"][aria-label*="unread" i]',
        'button[title*="غير مقروء" i]',
        'div[role="button"][title*="غير مقروء" i]',
        'button[aria-label*="علامة كغير" i]'
      ];

      for (const sel of selectors) {
        const btns = Array.from(document.querySelectorAll(sel)).filter(b => {
          if (b.closest('#mbs-inbox-automator-root')) return false;
          const r = b.getBoundingClientRect();
          return r.top < 250 && r.left < maxLeft && r.width > 0 && r.height > 0;
        });
        if (btns.length > 0) {
          const btn = btns[0];
          await HumanSimulator.flashEnvelopeButton(btn);
          await HumanSimulator.naturalClick(btn);
          return true;
        }
      }

      // NOTE: Done Sibling Fallback is permanently REMOVED to prevent any accidental click on "تم" / Done!

      // 2. Responsive Dropdown Fallback: "فتح القائمة المنسدلة" -> "تمييز كغير مقروءة"
      logger.log('SCAN', 'فحص القائمة المنسدلة العلوية للتمييز كغير مقروءة...');
      const dropdownBtn = Array.from(document.querySelectorAll('div[role="button"], button')).find(b => {
        if (b.closest('#mbs-inbox-automator-root')) return false;
        const t = (b.innerText || '').trim();
        const aria = b.getAttribute('aria-label') || '';
        const r = b.getBoundingClientRect();
        return (t.includes('فتح القائمة المنسدلة') || aria.includes('المزيد') || aria.includes('More')) &&
               r.top > 100 && r.top < 220 && r.left < maxLeft && r.left > 150 && r.width > 0;
      });

      if (dropdownBtn) {
        await HumanSimulator.flashEnvelopeButton(dropdownBtn);
        dropdownBtn.focus();
        dropdownBtn.click();
        await sleep(500);

        // Strictly target [role="menuitem"] inside [role="menu"] or floating popovers
        const menuItems = Array.from(document.querySelectorAll('[role="menu"] [role="menuitem"], [role="menuitem"]'));
        const unreadMenuItem = menuItems.find(el => {
          if (el.closest('#mbs-inbox-automator-root')) return false;
          const txt = (el.innerText || '').trim();
          const r = el.getBoundingClientRect();
          return (txt.includes('غير مقروء') || txt.toLowerCase().includes('unread')) &&
                 !txt.includes('نقل') && !txt.includes('المجلد') && !txt.includes('حذف') &&
                 r.height > 15 && r.height < 60 && r.width > 0;
        });

        if (unreadMenuItem) {
          unreadMenuItem.focus();
          unreadMenuItem.click();
          await sleep(350);
          return true;
        } else {
          // Close menu gently with Escape if unread item wasn't found
          window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }));
        }
      }

      return false;
    },

    isAdOrMetadataElement(el, txt) {
      if (!el) return false;
      if (el.closest) {
        if (el.closest('a[href*="/ads/"], [data-ad-id]')) return true;
        if (el.closest('[aria-label*="إعلان ممول" i], [aria-label*="Sponsored" i]')) return true;
      }
      const text = (txt || el.innerText || '').trim();
      if (!text) return false;
      if (/(?:تم الإرسال من إعلان|الرد على الإعلان|إعلان ممول|محتوى ممول|Sponsored Ad|Sent from ad)/i.test(text)) {
        return true;
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

      if (state.rules.some(r => r.reply && (text.includes(r.reply.slice(0, 20)) || r.reply.includes(text.slice(0, 20))))) {
        return true;
      }

      const parent = bubble.closest('div[role="row"], div[data-testid*="message"]') || bubble.parentElement?.parentElement;
      if (parent) {
        const pText = parent.innerText || '';
        if (pText.includes('تم التسليم') || pText.includes('Delivered') || pText.includes('تم الإرسال') || pText.includes('You:')) return true;
      }

      let curr = bubble;
      while (curr && curr !== document.body) {
        const style = window.getComputedStyle(curr);
        const bg = style.backgroundColor || '';
        if (
          /rgb\(\s*(0|8|10|24|45)\s*,\s*(100|102|119|122|132|136)\s*,\s*(224|242|255)/i.test(bg) ||
          bg.includes('0, 132, 255') || bg.includes('24, 119, 242') || bg.includes('8, 102, 255')
        ) {
          return true;
        }

        const color = style.color || '';
        if (color === 'rgb(255, 255, 255)' || color === '#ffffff' || color === 'white') {
          if (bg && !bg.includes('rgba(0, 0, 0, 0)')) return true;
        }
        curr = curr.parentElement;
      }

      const rect = bubble.getBoundingClientRect();
      const canvas = this.getChatCanvas();
      if (canvas) {
        const cRect = canvas.getBoundingClientRect();
        const center = cRect.left + cRect.width / 2;
        if (rect.right < center) return true;
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
      const origOutline = bubble.style.outline;
      bubble.style.outline = '2px dashed #22c55e';
      bubble.style.transition = 'outline 0.2s ease';
      await sleep(500);
      bubble.style.outline = origOutline || '';
    },

    async flashEnvelopeButton(btn) {
      if (!btn) return;
      const origOutline = btn.style.outline;
      const origShadow = btn.style.boxShadow;
      btn.style.outline = '2px solid #22c55e';
      btn.style.boxShadow = '0 0 12px rgba(34, 197, 94, 0.7)';
      await sleep(400);
      btn.style.outline = origOutline || '';
      btn.style.boxShadow = origShadow || '';
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
        if (state.emergencyAbort) throw new Error('ABORT_SIGNAL');

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

      await sleep(350);
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
      this.init();
    }

    init() {
      const existing = document.getElementById('mbs-inbox-automator-root');
      if (existing) {
        existing.remove();
      }

      this.container = document.createElement('div');
      this.container.id = 'mbs-inbox-automator-root';
      this.container.style.position = 'fixed';
      this.container.style.bottom = '20px';
      this.container.style.left = '20px';
      this.container.style.zIndex = '9999999';
      this.container.style.direction = 'rtl';
      this.container.style.fontFamily = 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif';

      this.shadow = this.container.attachShadow({ mode: 'open' });
      this.render();
      document.body.appendChild(this.container);

      this.bindEvents();
      this.log('INIT', 'تم تحميل واجهة التحكم V4.4 بنجاح وجاهزة لبدء الأتمتة.');
    }

    render() {
      this.shadow.innerHTML = `
        <style>
          * { box-sizing: border-box; margin: 0; padding: 0; }
          .hud-card {
            resize: both;
            min-width: 320px;
            min-height: 52px;
            max-width: 95vw;
            max-height: 90vh;
            width: 470px;
            max-height: 610px;
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(18px);
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 14px;
            box-shadow: 0 20px 45px rgba(0, 0, 0, 0.65);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            color: #f8fafc;
            user-select: none;
          }
          .header-icon-btn {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.12);
            color: #cbd5e1;
            border-radius: 6px;
            width: 24px;
            height: 24px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s;
            user-select: none;
          }
          .header-icon-btn:hover {
            background: rgba(255, 255, 255, 0.2);
            color: #ffffff;
            transform: scale(1.05);
          }
          .hud-header {
            cursor: grab;
            padding: 12px 16px;
            background: rgba(30, 41, 59, 0.85);
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            align-items: center;
            justify-content: space-between;
          }
          .hud-title {
            font-size: 13px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
          }
          .status-badge {
            font-size: 10px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 999px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
          }
          .status-ready { background: #334155; color: #94a3b8; }
          .status-running { background: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid #22c55e; }
          .status-cooldown { background: rgba(234, 179, 8, 0.2); color: #facc15; border: 1px solid #eab308; }
          .status-monitoring { background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid #38bdf8; }
          .status-stopped { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }

          .hud-stats-bar {
            padding: 8px 16px;
            background: rgba(15, 23, 42, 0.65);
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 6px;
            text-align: center;
          }
          .stat-item {
            display: flex;
            flex-direction: column;
            gap: 2px;
          }
          .stat-value {
            font-size: 14px;
            font-weight: 700;
            color: #38bdf8;
            font-family: monospace;
          }
          .stat-label {
            font-size: 9px;
            color: #94a3b8;
          }

          .hud-tabs {
            display: flex;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            background: rgba(15, 23, 42, 0.45);
          }
          .tab-btn {
            flex: 1;
            padding: 9px;
            background: none;
            border: none;
            color: #94a3b8;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            border-bottom: 2px solid transparent;
          }
          .tab-btn.active {
            color: #38bdf8;
            border-bottom: 2px solid #38bdf8;
            background: rgba(56, 189, 248, 0.06);
          }

          .hud-content {
            padding: 12px 16px;
            overflow-y: auto;
            max-height: 290px;
            min-height: 220px;
          }
          .tab-pane { display: none; }
          .tab-pane.active { display: block; }

          /* Terminal Tab */
          .terminal-box {
            background: rgba(0, 0, 0, 0.65);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 8px;
            padding: 10px;
            font-family: monospace;
            font-size: 10.5px;
            height: 220px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 4px;
          }
          .log-line { line-height: 1.4; word-break: break-word; }
          .log-time { color: #64748b; margin-left: 6px; }
          .log-tag-INIT { color: #94a3b8; }
          .log-tag-SCAN { color: #38bdf8; }
          .log-tag-MATCH { color: #4ade80; font-weight: bold; }
          .log-tag-UNREAD { color: #facc15; }
          .log-tag-TYPING { color: #c084fc; }
          .log-tag-SCROLL { color: #38bdf8; }
          .log-tag-INFO { color: #60a5fa; }
          .log-tag-WARN { color: #fb923c; }
          .log-tag-ERROR { color: #f87171; font-weight: bold; }
          .log-tag-STOP { color: #ef4444; }

          /* Rules Tab */
          .rule-card {
            background: rgba(30, 41, 59, 0.55);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 10px;
            margin-bottom: 8px;
            display: flex;
            flex-direction: column;
            gap: 6px;
          }
          .rule-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
          }
          .rule-match-type {
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 4px;
            padding: 2px 6px;
            color: #93c5fd;
            font-size: 10px;
          }
          .rule-keywords-input {
            width: 100%;
            background: rgba(15, 23, 42, 0.75);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 6px;
            padding: 6px 8px;
            color: #f8fafc;
            font-size: 11px;
            direction: rtl;
          }
          .rule-reply-input {
            width: 100%;
            background: rgba(15, 23, 42, 0.75);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 6px;
            padding: 6px 8px;
            color: #f8fafc;
            font-size: 11px;
            min-height: 48px;
            direction: rtl;
            resize: vertical;
          }
          .add-rule-btn {
            width: 100%;
            padding: 8px;
            background: rgba(56, 189, 248, 0.15);
            border: 1px dashed rgba(56, 189, 248, 0.4);
            border-radius: 8px;
            color: #38bdf8;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
          }
          .add-rule-btn:hover { background: rgba(56, 189, 248, 0.25); }

          /* Switch */
          .switch {
            position: relative;
            display: inline-block;
            width: 34px;
            height: 18px;
          }
          .switch input { opacity: 0; width: 0; height: 0; }
          .slider {
            position: absolute;
            cursor: pointer;
            top: 0; left: 0; right: 0; bottom: 0;
            background-color: #334155;
            transition: .3s;
            border-radius: 34px;
          }
          .slider:before {
            position: absolute;
            content: "";
            height: 14px; width: 14px;
            left: 2px; bottom: 2px;
            background-color: white;
            transition: .3s;
            border-radius: 50%;
          }
          input:checked + .slider { background-color: #22c55e; }
          input:checked + .slider:before { transform: translateX(16px); }

          /* Config Tab */
          .config-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
          }
          .config-label { font-size: 11px; color: #cbd5e1; }
          .config-input {
            width: 65px;
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 4px;
            padding: 4px 6px;
            color: #f8fafc;
            font-size: 11px;
            text-align: center;
          }

          .hud-footer {
            padding: 12px 16px;
            background: rgba(30, 41, 59, 0.85);
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            gap: 8px;
          }
          .btn-primary {
            flex: 2;
            padding: 9px 12px;
            background: linear-gradient(135deg, #0284c7, #0369a1);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s;
            box-shadow: 0 4px 12px rgba(2, 132, 199, 0.3);
          }
          .btn-primary:hover { opacity: 0.95; transform: translateY(-1px); }
          .btn-danger {
            flex: 1;
            padding: 9px 12px;
            background: rgba(239, 68, 68, 0.15);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 8px;
            font-size: 12px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s;
          }
          .btn-danger:hover { background: rgba(239, 68, 68, 0.25); }
        </style>

        <div class="hud-card">
          <div class="hud-header" id="hud-header">
            <div style="display: flex; gap: 6px; align-items: center;">
              <button class="header-icon-btn" id="btn-minimize" title="تصغير إلى شريط مصغر">—</button>
              <button class="header-icon-btn" id="btn-maximize" title="تكبير / توسيع النافذة">⛶</button>
            </div>
            <div class="hud-title">
              <span>⚡ أتمتة Meta Business Suite</span>
              <span style="font-size: 10px; color: #64748b;">V4.4.2</span>
            </div>
            <div style="display: flex; gap: 6px; align-items: center;">
              <div id="hud-minimized-summary" style="display:none; align-items: center; gap: 8px;">
                <span style="font-size: 11px; color: #38bdf8;">فحص: <b id="min-stat-eval">0</b></span>
                <span style="font-size: 11px; color: #4ade80;">رد: <b id="min-stat-match">0</b></span>
                <span style="font-size: 11px; color: #facc15;">استعادة: <b id="min-stat-unread">0</b></span>
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
              <span id="stat-matched" class="stat-value" style="color: #4ade80;">0</span>
              <span class="stat-label">تم الرد</span>
            </div>
            <div class="stat-item">
              <span id="stat-unread" class="stat-value" style="color: #facc15;">0</span>
              <span class="stat-label">غير مقروء</span>
            </div>
            <div class="stat-item">
              <span id="stat-skipped" class="stat-value" style="color: #fb923c;">0</span>
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
                <span class="config-label">تذبذب سرعة الكتابة البشرية (ms)</span>
                <div style="display: flex; gap: 4px; align-items: center;">
                  <input type="number" id="cfg-min-typing" class="config-input" value="${state.config.minTypingSpeed}">
                  <span style="font-size: 10px; color: #64748b;">-</span>
                  <input type="number" id="cfg-max-typing" class="config-input" value="${state.config.maxTypingSpeed}">
                </div>
              </div>
              <div class="config-row">
                <span class="config-label">فترة التهدئة بين المحادثات (ms)</span>
                <div style="display: flex; gap: 4px; align-items: center;">
                  <input type="number" id="cfg-min-cooldown" class="config-input" value="${state.config.minCooldown}">
                  <span style="font-size: 10px; color: #64748b;">-</span>
                  <input type="number" id="cfg-max-cooldown" class="config-input" value="${state.config.maxCooldown}">
                </div>
              </div>
              <div class="config-row">
                <span class="config-label">فترة انتظار وضع المراقبة (ms)</span>
                <input type="number" id="cfg-monitoring-interval" class="config-input" style="width: 80px;" value="${state.config.monitoringInterval}">
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

    bindEvents() {
      // Draggable window implementation
      const header = this.shadow.getElementById('hud-header');
      let isDragging = false;
      let startX = 0, startY = 0;
      let initialLeft = 0, initialTop = 0;

      header.addEventListener('mousedown', (e) => {
        if (e.target.closest('button, input, select, label')) return;
        isDragging = true;
        header.style.cursor = 'grabbing';
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

          let newLeft = initialLeft + dx;
          let newTop = initialTop + dy;

          const w = this.container.offsetWidth || 470;
          const h = this.container.offsetHeight || 300;

          newLeft = Math.max(10, Math.min(window.innerWidth - w - 10, newLeft));
          newTop = Math.max(10, Math.min(window.innerHeight - h - 10, newTop));

          this.container.style.left = `${newLeft}px`;
          this.container.style.top = `${newTop}px`;
        };

        const onMouseUp = () => {
          isDragging = false;
          header.style.cursor = 'grab';
          document.removeEventListener('mousemove', onMouseMove);
          document.removeEventListener('mouseup', onMouseUp);
        };

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
      });

      // Minimize / Restore Toggle
      const btnMin = this.shadow.getElementById('btn-minimize');
      const btnMax = this.shadow.getElementById('btn-maximize');
      let isMinimized = false;
      let isMaximized = false;

      btnMin.addEventListener('click', () => {
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
          card.style.width = isMaximized ? '680px' : '470px';
          card.style.maxHeight = isMaximized ? '750px' : '610px';
          card.style.resize = 'both';
          btnMin.textContent = '—';
          btnMin.title = 'تصغير إلى شريط مصغر';
        }
      });

      btnMax.addEventListener('click', () => {
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
          card.style.width = '470px';
          card.style.maxHeight = '610px';
          content.style.maxHeight = '290px';
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

      this.shadow.getElementById('cfg-min-typing').addEventListener('change', (e) => {
        state.config.minTypingSpeed = parseInt(e.target.value, 10) || 35;
        saveConfig();
      });
      this.shadow.getElementById('cfg-max-typing').addEventListener('change', (e) => {
        state.config.maxTypingSpeed = parseInt(e.target.value, 10) || 65;
        saveConfig();
      });
      this.shadow.getElementById('cfg-min-cooldown').addEventListener('change', (e) => {
        state.config.minCooldown = parseInt(e.target.value, 10) || 1500;
        saveConfig();
      });
      this.shadow.getElementById('cfg-max-cooldown').addEventListener('change', (e) => {
        state.config.maxCooldown = parseInt(e.target.value, 10) || 2500;
        saveConfig();
      });
      this.shadow.getElementById('cfg-monitoring-interval').addEventListener('change', (e) => {
        state.config.monitoringInterval = parseInt(e.target.value, 10) || 6000;
        saveConfig();
      });
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

    renderRulesList() {
      const container = this.shadow.getElementById('rules-container');
      if (!container) return;

      container.innerHTML = state.rules.map((rule, idx) => `
        <div class="rule-card" data-idx="${idx}">
          <div class="rule-header">
            <span style="font-size: 11px; font-weight: 700; color: #38bdf8;">قاعدة #${idx + 1}</span>
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
              <button class="rule-del-btn" data-idx="${idx}" style="background:none; border:none; color:#ef4444; cursor:pointer; font-size:12px;">✕</button>
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
        el.addEventListener('input', (e) => {
          const idx = parseInt(e.target.getAttribute('data-idx'), 10);
          state.rules[idx].keyword = e.target.value;
          saveRules();
        });
      });

      container.querySelectorAll('.rule-reply-input').forEach(el => {
        el.addEventListener('input', (e) => {
          const idx = parseInt(e.target.getAttribute('data-idx'), 10);
          state.rules[idx].reply = e.target.value;
          saveRules();
        });
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
      if (!el) return;
      el.textContent = text;
      el.className = `status-badge status-${type}`;
      if (window.pyOnStateChange) {
        window.pyOnStateChange(text).catch(() => {});
      }
    }

    updateStats() {
      this.shadow.getElementById('stat-evaluated').textContent = state.stats.evaluated;
      const mEval = this.shadow.getElementById('min-stat-eval');
      if (mEval) mEval.textContent = state.stats.evaluated;
      const mMatch = this.shadow.getElementById('min-stat-match');
      if (mMatch) mMatch.textContent = state.stats.matched;
      const mUnread = this.shadow.getElementById('min-stat-unread');
      if (mUnread) mUnread.textContent = state.stats.unreadRestored;
      this.shadow.getElementById('stat-matched').textContent = state.stats.matched;
      this.shadow.getElementById('stat-unread').textContent = state.stats.unreadRestored;
      this.shadow.getElementById('stat-skipped').textContent = state.stats.skippedOutbound;

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

    stop() {
      state.isRunning = false;
      state.emergencyAbort = true;
      this.hud.setStatus('STOPPED', 'stopped');
      this.hud.log('STOP', 'الأتمتة متوقفة حالياً.');

      if (state.activeRowElement) {
        state.activeRowElement.style.outline = '';
        state.activeRowElement.style.boxShadow = '';
        state.activeRowElement = null;
      }
    },

    async runLoop() {
      while (state.isRunning && !state.emergencyAbort) {
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

          const isReplied = key && state.repliedContacts.has(key);
          const isProcessed = (fingerprint && state.processedSnapshots.has(fingerprint)) ||
                              (key && state.processedContacts.has(key));

          if (!isReplied && !isProcessed) {
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
              return (!k || (!state.processedContacts.has(k) && !state.repliedContacts.has(k))) &&
                     (!fp || !state.processedSnapshots.has(fp));
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

          // 3. Clear processedContacts for the new cycle (preserves repliedContacts & processedSnapshots)
          state.processedContacts.clear();
          this.hud.setStatus('RUNNING', 'running');
          continue;
        }

        const contactName = DOM.getRowCustomerName(targetRow);
        let contactKey = targetContactKey || DOM.getStableRowKey(targetRow) || (contactName ? `contact_${normalizeArabicText(contactName)}` : `row_${Date.now()}`);
        let rowFingerprint = targetFingerprint || `${contactKey}__${DOM.getRowSnippet(targetRow)}`;

        state.stats.evaluated++;
        this.hud.updateStats();
        this.hud.log('SCAN', `--- [محادثة #${selectedIndex + 1}/${rows.length}] تفعيل العميل: "${contactName || contactKey}" ---`);

        // Visual Framing: Sky-blue border with soft glow on active row
        const originalOutline = targetRow.style.outline;
        const originalShadow = targetRow.style.boxShadow;
        if (state.config.highlightRows) {
          targetRow.style.outline = '3px solid #38bdf8';
          targetRow.style.boxShadow = '0 0 12px rgba(56, 189, 248, 0.4)';
          state.activeRowElement = targetRow;
        }

        // STEP 2: Safe Thread Activation & Viewport Sync
        const clickTarget = DOM.getRowClickTarget(targetRow);
        await HumanSimulator.naturalClick(clickTarget);

        this.hud.log('SCAN', 'انتظار تطابق نافذة المحادثة مع العميل...');
        let chatLoaded = false;
        const normTarget = normalizeArabicText(contactName);
        const startHydrate = Date.now();

        while (Date.now() - startHydrate < 2800) {
          if (state.emergencyAbort) throw new Error('ABORT_SIGNAL');
          const headerName = DOM.getActiveChatContactName();
          const normHeader = normalizeArabicText(headerName);
          const composer = DOM.getComposer();

          if (composer && normTarget && normHeader && (normHeader.includes(normTarget) || normTarget.includes(normHeader))) {
            chatLoaded = true;
            break;
          }

          // Retry click if switch hasn't happened after 1.2s
          if (Date.now() - startHydrate > 1200 && !chatLoaded) {
            await HumanSimulator.naturalClick(clickTarget);
          }
          await sleep(150);
        }

        // Looser check if composer exists and contact matches
        if (!chatLoaded) {
          const headerName = DOM.getActiveChatContactName();
          const normHeader = normalizeArabicText(headerName);
          if (DOM.getComposer() && (!normTarget || (normHeader && (normHeader.includes(normTarget) || normTarget.includes(normHeader))))) {
            chatLoaded = true;
          }
        }

        if (!chatLoaded) {
          const currHeader = DOM.getActiveChatContactName();
          this.hud.log('WARN', `تعذر تبديل المحادثة للعميل "${contactName}" (المحادثة المعروضة حالياً: "${currHeader || 'غير محددة'}"). تخطي لحماية المحادثة الحالية.`);
          state.processedContacts.add(contactKey);
          if (rowFingerprint) state.processedSnapshots.add(rowFingerprint);
          targetRow.style.outline = originalOutline || '';
          targetRow.style.boxShadow = originalShadow || '';
          continue;
        }

        const headerName = DOM.getActiveChatContactName();
        if (headerName) {
          const refinedKey = `contact_${normalizeArabicText(headerName)}`;
          if (state.repliedContacts.has(refinedKey)) {
            this.hud.log('INFO', `المحادثة مع ${headerName} تم الرد عليها مسبقاً من الأتمتة. تخطي...`);
            state.processedContacts.add(contactKey);
            if (rowFingerprint) state.processedSnapshots.add(rowFingerprint);
            targetRow.style.outline = originalOutline || '';
            targetRow.style.boxShadow = originalShadow || '';
            continue;
          }
          contactKey = refinedKey;
        }

        if (state.config.scrollThread) {
          await HumanSimulator.simulateThreadScroll(this.hud);
        } else {
          await sleep(randomRange(150, 250));
        }

        // STEP 3: Message Boundary Parsing (Post-Agent Messages Only)
        this.hud.log('SCAN', 'فحص حدود الرسائل (الرسائل الواردة بعد آخر رد من الصفحة)...');
        const { lastIsOutbound, customerBubbles } = DOM.parseInboundBoundary();

        if (lastIsOutbound) {
          state.stats.skippedOutbound++;
          this.hud.updateStats();
          this.hud.log('WARN', '[Inbound Guard] آخر رسالة مرسلة من الصفحة مسبقاً. تخطي الرد واستعادة غير مقروء...');

          await this.executeBranchB(contactKey, rowFingerprint);
          targetRow.style.outline = originalOutline || '';
          targetRow.style.boxShadow = originalShadow || '';

          const cooldown = randomRange(state.config.minCooldown, state.config.maxCooldown);
          this.hud.setStatus(`COOLDOWN (${(cooldown / 1000).toFixed(1)}s)`, 'cooldown');
          await sleep(cooldown);
          this.hud.setStatus('RUNNING', 'running');
          continue;
        }

        if (customerBubbles.length === 0) {
          this.hud.log('INFO', 'لا توجد رسائل نصية واردة جديدة (وسائط/صورة فقط). استعادة كغير مقروء...');
          await this.executeBranchB(contactKey, rowFingerprint);
          targetRow.style.outline = originalOutline || '';
          targetRow.style.boxShadow = originalShadow || '';

          const cooldown = randomRange(state.config.minCooldown, state.config.maxCooldown);
          this.hud.setStatus(`COOLDOWN (${(cooldown / 1000).toFixed(1)}s)`, 'cooldown');
          await sleep(cooldown);
          this.hud.setStatus('RUNNING', 'running');
          continue;
        }

        // STEP 4: Visual Search & Keyword Evaluation
        const latestBubble = customerBubbles[customerBubbles.length - 1];
        await HumanSimulator.highlightCustomerBubble(latestBubble);

        const customerTexts = customerBubbles.map(b => (b.innerText || '').trim()).filter(Boolean);
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

          state.repliedContacts.add(contactKey);
          state.processedContacts.add(contactKey);
          if (rowFingerprint) state.processedSnapshots.add(rowFingerprint);

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
          this.hud.log('SCAN', 'لا توجد كلمات مفتاحية مطابقة. استعادة المحادثة كغير مقروءة لمراجعة الكول سنتر...');
          await this.executeBranchB(contactKey, rowFingerprint);
        }

        // STEP 6: Viewport Scrolling & Next-Row Progression
        targetRow.style.outline = originalOutline || '';
        targetRow.style.boxShadow = originalShadow || '';
        state.activeRowElement = null;

        // Auto-scroll sidebar if nearing the bottom
        if (selectedIndex >= rows.length - 2) {
          const sidebar = DOM.getSidebarScrollContainer();
          if (sidebar) {
            this.hud.log('SCROLL', 'التمرير التلقائي للقائمة الجانبية لإظهار محادثات إضافية (scrollBy 220px)...');
            sidebar.scrollBy({ top: 220, behavior: 'smooth' });
          }
        }

        const cooldown = randomRange(state.config.minCooldown, state.config.maxCooldown);
        this.hud.setStatus(`COOLDOWN (${(cooldown / 1000).toFixed(1)}s)`, 'cooldown');
        this.hud.log('INFO', `تهدئة بشرية: انتظار ${(cooldown / 1000).toFixed(1)} ثانية...`);
        await sleep(cooldown);
        this.hud.setStatus('RUNNING', 'running');
      }
    },

    async executeBranchB(contactKey, rowFingerprint) {
      if (contactKey) state.processedContacts.add(contactKey);
      if (rowFingerprint) state.processedSnapshots.add(rowFingerprint);

      await sleep(randomRange(150, 250));
      const restored = await DOM.executeRestoreToUnread(this.hud);

      if (restored) {
        state.stats.unreadRestored++;
        this.hud.updateStats();
        this.hud.log('UNREAD', '[UNREAD] تم تمييز المحادثة كغير مقروءة بنجاح.');
      } else {
        this.hud.log('WARN', 'تعذر العثور على زر تمييز كغير مقروءة في شريط الأدوات أو القائمة المنسدلة.');
      }
    }
  };

  // Expose global handles
  window.__MBS_AUTOMATOR_HUD__ = new AutomatorHUD();
  window.__MBS_AUTOMATOR_ORCHESTRATOR__ = Orchestrator;
  Orchestrator.init(window.__MBS_AUTOMATOR_HUD__);

  window.__MBS_AUTOMATOR_START__ = () => Orchestrator.start();
  window.__MBS_AUTOMATOR_STOP__ = () => Orchestrator.stop();
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

  console.log('[MBS Automator V4.4.2] Bootstrapped successfully.');
})();

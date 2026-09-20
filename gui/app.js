/**
 * Meta Automation Desktop Control Center (V6.5.2-ENTERPRISE)
 * Apple Prismatic Liquid Glass Client Application
 * Cupertino / SF Symbols Vector SVG Integration
 */

(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Cupertino / SF Symbols SVG Icons Catalog
  // ---------------------------------------------------------------------------
  const ICONS = {
    play: `<svg class="sf-icon" viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>`,
    stop: `<svg class="sf-icon" viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>`,
    pencil: `<svg class="sf-icon" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>`,
    trash: `<svg class="sf-icon" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>`,
    bolt: `<svg class="sf-icon" viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
    info: `<svg class="sf-icon" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
    copy: `<svg class="sf-icon" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`,
    check: `<svg class="sf-icon" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
    save: `<svg class="sf-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>`
  };

  const state = {
    profiles: [],
    selectedProfile: null,
    currentConfig: null,
    automationState: {}, // profile_name -> in-page status ('RUNNING' | 'PAUSED' | 'READY' | 'STOPPED' | etc.)
    logs: {}, // profile_name -> array of html log entries
    stats: {}, // profile_name -> { evaluated, matched, unread, skipped }
    modalMode: null, // 'create' | 'rename'
    modalTargetProfile: null
  };

  // ---------------------------------------------------------------------------
  // API Bridge Helpers
  // ---------------------------------------------------------------------------
  async function callApi(method, ...args) {
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api[method] === 'function') {
      try {
        return await window.pywebview.api[method](...args);
      } catch (err) {
        console.error(`[API Error] ${method}:`, err);
        throw err;
      }
    } else {
      console.warn(`[API Mock] pywebview.api.${method} not ready, returning fallback.`);
      return null;
    }
  }

  // ---------------------------------------------------------------------------
  // DOM Elements
  // ---------------------------------------------------------------------------
  const elements = {
    profilesList: document.getElementById('profiles-list'),
    activeProfileName: document.getElementById('active-profile-name'),
    activeProfileStatus: document.getElementById('active-profile-status'),
    btnActiveStart: document.getElementById('btn-active-start'),
    btnActiveStop: document.getElementById('btn-active-stop'),
    btnNewProfile: document.getElementById('btn-new-profile'),
    btnStartAll: document.getElementById('btn-start-all'),
    btnStopAll: document.getElementById('btn-stop-all'),
    statEvaluated: document.getElementById('stat-evaluated'),
    statMatched: document.getElementById('stat-matched'),
    statUnread: document.getElementById('stat-unread'),
    statSkipped: document.getElementById('stat-skipped'),
    terminal: document.getElementById('terminal'),
    btnClearLogs: document.getElementById('btn-clear-logs'),
    rulesContainer: document.getElementById('rules-container'),
    tabRules: document.getElementById('tab-rules'),
    btnAddRule: document.getElementById('add-rule-btn'),
    btnSaveRules: document.getElementById('btn-save-rules'),
    cfgInboxUrl: document.getElementById('cfg-inbox-url'),
    cfgCooldown: document.getElementById('cfg-cooldown-sec'),
    cfgMonitoring: document.getElementById('cfg-monitoring-sec'),
    cfgTypingSpeed: document.getElementById('cfg-typing-speed'),
    cfgHighlight: document.getElementById('cfg-highlight-row'),
    cfgAutoStart: document.getElementById('cfg-auto-start'),
    btnSaveConfig: document.getElementById('btn-save-config'),
    modalProfile: document.getElementById('modal-profile'),
    modalTitle: document.getElementById('modal-profile-title'),
    modalInput: document.getElementById('modal-profile-input'),
    btnModalCancel: document.getElementById('btn-modal-cancel'),
    btnModalConfirm: document.getElementById('btn-modal-confirm'),
    btnImportRules: document.getElementById('btn-import-rules'),
    modalImportRules: document.getElementById('modal-import-rules'),
    importSourceSelect: document.getElementById('import-source-profile-select'),
    importSelectionArea: document.getElementById('import-rules-selection-area'),
    btnImportSelectAll: document.getElementById('btn-import-select-all'),
    importRulesList: document.getElementById('import-rules-list'),
    importEmptyState: document.getElementById('import-rules-empty-state'),
    importError: document.getElementById('import-rules-error'),
    btnImportCancel: document.getElementById('btn-import-cancel'),
    btnImportConfirm: document.getElementById('btn-import-confirm'),
    modalLinkConflict: document.getElementById('modal-link-conflict'),
    conflictCodeBadge: document.getElementById('conflict-code-badge'),
    conflictOptionsList: document.getElementById('conflict-options-list'),
    btnConflictCancel: document.getElementById('btn-conflict-cancel'),
    btnConflictResolve: document.getElementById('btn-conflict-resolve'),
    tabs: document.querySelectorAll('.tab-btn'),
    tabPanes: document.querySelectorAll('.tab-pane')
  };

  // ---------------------------------------------------------------------------
  // Real-Time Telemetry Dispatcher (Normalized Envelope Handler)
  // ---------------------------------------------------------------------------
  window.__RECEIVE_TELEMETRY__ = function (payload) {
    if (!payload || typeof payload !== 'object') return;
    const profName = payload.profile_name || 'Default';

    // 1. Logs (Unpacks {type: "LOG", data: {tag, message}} and flat {level, message})
    if (payload.type === 'LOG' && payload.data) {
      const tag = payload.data.tag || 'INFO';
      const msg = payload.data.message || '';
      appendLog(profName, tag, msg, payload.prefix);
    } else if (payload.level && payload.message) {
      appendLog(profName, payload.level, payload.message, payload.prefix);
    }

    // 2. Stats (Unpacks {type: "STATS", data: {...}} and flat metrics)
    let statsObj = null;
    if (payload.type === 'STATS' && payload.data && typeof payload.data === 'object') {
      statsObj = payload.data;
    } else if (payload.evaluated !== undefined || payload.matched !== undefined) {
      statsObj = payload;
    }

    if (statsObj) {
      if (!state.stats[profName]) {
        state.stats[profName] = { evaluated: 0, matched: 0, unread: 0, skipped: 0 };
      }
      if (statsObj.evaluated !== undefined) state.stats[profName].evaluated = statsObj.evaluated;
      if (statsObj.matched !== undefined) state.stats[profName].matched = statsObj.matched;
      if (statsObj.unreadRestored !== undefined) state.stats[profName].unread = statsObj.unreadRestored;
      else if (statsObj.unread !== undefined) state.stats[profName].unread = statsObj.unread;
      if (statsObj.skippedOutbound !== undefined) state.stats[profName].skipped = statsObj.skippedOutbound;
      else if (statsObj.skipped !== undefined) state.stats[profName].skipped = statsObj.skipped;

      if (state.selectedProfile === profName) {
        updateStatsUI(state.stats[profName]);
      }
    }

    // 3. Status (Unpacks {type: "STATE", data: {status, type}} and flat status)
    let statusText = null;
    if (payload.type === 'STATE' && payload.data) {
      statusText = typeof payload.data === 'object' ? (payload.data.status || payload.data.type) : String(payload.data);
    } else if (payload.status) {
      statusText = payload.status;
    }

    if (statusText) {
      state.automationState[profName] = statusText;
      const prof = state.profiles.find(p => p.name === profName);
      if (prof) {
        prof.rawStatus = statusText;
        renderProfilesList();
        if (state.selectedProfile === profName) {
          updateProfileHeaderUI(prof);
        }
      }
    }
  };

  function appendLog(profName, level, message, prefix) {
    if (!state.logs[profName]) state.logs[profName] = [];
    const timeStr = new Date().toLocaleTimeString('ar-EG', { hour12: false });
    const levelColors = {
      INIT: '#0284c7',
      INFO: '#475569',
      MATCH: '#16a34a',
      UNREAD: '#d97706',
      SKIP: '#94a3b8',
      WARN: '#f59e0b',
      ERROR: '#dc2626'
    };
    const color = levelColors[level] || '#475569';
    const logItem = `
      <div class="log-entry" style="display: flex; gap: 8px; margin-bottom: 4px; font-size: 11.5px; font-family: ui-monospace, SFMono-Regular, monospace;">
        <span style="color: #94a3b8; min-width: 55px;">[${timeStr}]</span>
        <span style="color: ${color}; font-weight: 700; min-width: 50px;">[${level}]</span>
        ${prefix ? `<span style="color: #6366f1; font-weight: 600;">${prefix}</span>` : ''}
        <span style="color: #1e293b; flex: 1; word-break: break-word;">${escapeHtml(message)}</span>
      </div>
    `;
    state.logs[profName].push(logItem);
    if (state.logs[profName].length > 500) state.logs[profName].shift();

    if (state.selectedProfile === profName && elements.terminal) {
      elements.terminal.insertAdjacentHTML('beforeend', logItem);
      while (elements.terminal.children.length > 500) {
        elements.terminal.removeChild(elements.terminal.firstChild);
      }
      elements.terminal.scrollTop = elements.terminal.scrollHeight;
    }
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ---------------------------------------------------------------------------
  // Profile Loading & Selection
  // ---------------------------------------------------------------------------
  async function refreshProfiles() {
    const list = await callApi('get_profiles');
    if (Array.isArray(list)) {
      state.profiles = list;
      renderProfilesList();
      if (!state.selectedProfile && state.profiles.length > 0) {
        selectProfile(state.profiles[0].name);
      } else if (state.selectedProfile) {
        const current = state.profiles.find(p => p.name === state.selectedProfile);
        if (current) {
          updateProfileHeaderUI(current);
        }
      }
    }
  }

  function renderProfilesList() {
    if (!elements.profilesList) return;
    elements.profilesList.innerHTML = '';

    state.profiles.forEach(p => {
      const isRunning = p.status === 'RUNNING';
      const isSelected = p.name === state.selectedProfile;
      const card = document.createElement('div');
      card.className = `profile-card ${isSelected ? 'active' : ''}`;

      let rulesTagHtml = '';
      if (p.read_status === 'MISSING') {
        rulesTagHtml = `<span class="profile-card-rules-tag error">تهيئة مفقودة</span>`;
      } else if (p.read_status === 'MALFORMED') {
        rulesTagHtml = `<span class="profile-card-rules-tag error">تهيئة تالفة</span>`;
      } else if (p.read_status === 'UNREADABLE') {
        rulesTagHtml = `<span class="profile-card-rules-tag error">تعذر القراءة</span>`;
      } else {
        const countVal = (p.rules_count !== undefined && p.rules_count !== null) ? p.rules_count : 0;
        rulesTagHtml = `<span class="profile-card-rules-tag">${countVal} قاعدة رد</span>`;
      }

      card.innerHTML = `
        <div class="profile-card-top">
          <div class="profile-card-info">
            <span class="ghost-dot ${isRunning ? 'running' : 'stopped'}"></span>
            <span class="profile-card-name" title="${escapeHtml(p.name)}">${escapeHtml(p.name)}</span>
          </div>
          <div class="profile-card-actions">
            <button class="icon-action-btn btn-rename" title="إعادة تسمية">${ICONS.pencil}</button>
            <button class="icon-action-btn btn-delete" title="حذف البروفايل">${ICONS.trash}</button>
          </div>
        </div>
        <div class="profile-card-bottom">
          ${rulesTagHtml}
          <button class="btn-card-toggle ${isRunning ? 'stop' : 'start'}">
            ${isRunning ? `${ICONS.stop} <span>إغلاق المتصفح</span>` : `${ICONS.play} <span>فتح المتصفح</span>`}
          </button>
        </div>
      `;

      // Events
      card.addEventListener('click', (e) => {
        if (e.target.closest('button')) return;
        selectProfile(p.name);
      });

      card.querySelector('.btn-card-toggle').addEventListener('click', async (e) => {
        e.stopPropagation();
        if (isRunning) {
          await callApi('stop_profile', p.name);
          state.automationState[p.name] = 'STOPPED';
        } else {
          // Launch browser visibly
          await callApi('start_profile', p.name, false);
        }
        await refreshProfiles();
      });

      card.querySelector('.btn-rename').addEventListener('click', (e) => {
        e.stopPropagation();
        openProfileModal('rename', p.name);
      });

      card.querySelector('.btn-delete').addEventListener('click', async (e) => {
        e.stopPropagation();
        if (confirm(`هل أنت متأكد من حذف بروفايل "${p.name}" وبياناته بالكامل؟`)) {
          await callApi('delete_profile', p.name);
          if (state.selectedProfile === p.name) state.selectedProfile = null;
          await refreshProfiles();
        }
      });

      elements.profilesList.appendChild(card);
    });
  }

  function enableProfileControls(enabled) {
    if (elements.btnSaveRules) elements.btnSaveRules.disabled = !enabled;
    if (elements.btnSaveConfig) elements.btnSaveConfig.disabled = !enabled;
    if (elements.btnAddRule) elements.btnAddRule.disabled = !enabled;
    if (elements.btnImportRules) elements.btnImportRules.disabled = !enabled;
  }

  function renderProfileErrorUI(status, errorMsg) {
    enableProfileControls(false);
    let title = 'خطأ في تحميل البروفايل';
    let desc = errorMsg || 'تعذر قراءة ملف التهيئة.';
    if (status === 'MISSING') {
      title = 'ملف التهيئة مفقود (config.json)';
      desc = 'لم يتم العثور على ملف التهيئة الخاص بهذا البروفايل على القرص.';
    } else if (status === 'MALFORMED') {
      title = 'ملف التهيئة تالف (Invalid JSON)';
      desc = 'محتوى ملف التهيئة تالف ولا يمكن تحليله بأمان. تم قفل التعديل لمنع فقدان البيانات.';
    } else if (status === 'UNREADABLE') {
      title = 'تعذر قراءة ملف التهيئة';
      desc = 'حدث خطأ في صلاحيات القراءة أو الوصول لملف التهيئة.';
    }

    const bannerHtml = `
      <div class="profile-error-banner">
        <strong>${escapeHtml(title)}</strong>
        <span>${escapeHtml(desc)}</span>
        <small style="opacity: 0.8; margin-top: 4px;">لحماية بياناتك، تم تعطيل أزرار الحفظ والإضافة مؤقتاً.</small>
      </div>
    `;

    if (elements.rulesContainer) {
      elements.rulesContainer.innerHTML = bannerHtml;
    }
  }

  async function selectProfile(profileName) {
    state.selectedProfile = profileName;
    renderProfilesList();

    const prof = state.profiles.find(p => p.name === profileName);
    if (prof) updateProfileHeaderUI(prof);

    // Render Stats
    const stats = state.stats[profileName] || { evaluated: 0, matched: 0, unread: 0, skipped: 0 };
    updateStatsUI(stats);

    // Render Logs
    if (elements.terminal) {
      elements.terminal.innerHTML = (state.logs[profileName] || []).join('');
      elements.terminal.scrollTop = elements.terminal.scrollHeight;
    }

    state.selectSeq = (state.selectSeq || 0) + 1;
    const currentSeq = state.selectSeq;

    let res = null;
    try {
      res = await callApi('load_profile_config_result', profileName);
    } catch (_) {}

    // Anti-race protection: discard stale response
    if (state.selectSeq !== currentSeq || state.selectedProfile !== profileName) {
      return;
    }

    if (res && res.read_status && res.read_status !== 'OK') {
      state.currentConfig = null;
      state.currentConfigSha256 = null;
      renderProfileErrorUI(res.read_status, res.error);
      return;
    }

    try {
      state.linkedRulesMap = (await callApi('get_linked_rules_map')) || {};
    } catch (_) {
      state.linkedRulesMap = {};
    }

    if (state.selectSeq !== currentSeq || state.selectedProfile !== profileName) {
      return;
    }

    if (res && res.ok && res.data) {
      state.currentConfig = res.data;
      state.currentConfigSha256 = res.sha256_token;
    } else {
      const cfg = await callApi('get_profile_config', profileName);
      if (state.selectSeq !== currentSeq || state.selectedProfile !== profileName) return;
      state.currentConfig = cfg || { rules: [], config: {} };
    }

    enableProfileControls(true);
    renderRulesUI();
    renderConfigUI();
  }

  function updateProfileHeaderUI(prof) {
    if (!prof) return;
    elements.activeProfileName.textContent = prof.name;
    const isBrowserRunning = prof.status === 'RUNNING';
    const autoState = (state.automationState[prof.name] || prof.rawStatus || '').toUpperCase();

    if (!isBrowserRunning) {
      // a. Browser Stopped
      elements.activeProfileStatus.innerHTML = `
        <span class="ghost-dot stopped" style="margin-left: 6px;"></span>
        <span>المتصفح مغلق</span>
      `;
      elements.activeProfileStatus.className = 'stage-status-badge status-ready';
      elements.btnActiveStart.style.display = 'inline-flex';
      elements.btnActiveStop.style.display = 'none';
    } else {
      const isLoopActive = autoState === 'RUNNING' || 
                           autoState === 'MONITORING' || 
                           autoState === 'SEARCHING' || 
                           (typeof autoState === 'string' && autoState.startsWith('COOLDOWN'));
      if (isLoopActive) {
        // c. Browser Running & Loop Active
        let label = 'الأتمتة قيد العمل';
        let dotStyle = '';
        if (autoState === 'MONITORING') {
          label = 'الأتمتة قيد المراقبة';
        } else if (autoState.startsWith('COOLDOWN')) {
          const match = autoState.match(/COOLDOWN\s*\(([^)]+)\)/);
          label = `تهدئة مؤقتة (${match ? match[1] : 'نشطة'})`;
          dotStyle = 'background: #06b6d4;';
        }

        elements.activeProfileStatus.innerHTML = `
          <span class="ghost-dot running" style="margin-left: 6px; ${dotStyle}"></span>
          <span>${label}</span>
        `;
        elements.activeProfileStatus.className = 'stage-status-badge status-running';
        elements.btnActiveStart.style.display = 'none';
        elements.btnActiveStop.style.display = 'inline-flex';
      } else {
        // b. Browser Running & Loop Paused (or READY)
        elements.activeProfileStatus.innerHTML = `
          <span class="ghost-dot paused" style="margin-left: 6px;"></span>
          <span>جاهز (الأتمتة متوقفة)</span>
        `;
        elements.activeProfileStatus.className = 'stage-status-badge status-paused';
        elements.btnActiveStart.style.display = 'inline-flex';
        elements.btnActiveStop.style.display = 'none';
      }
    }
  }

  function updateStatsUI(s) {
    elements.statEvaluated.textContent = s.evaluated || 0;
    elements.statMatched.textContent = s.matched || 0;
    elements.statUnread.textContent = s.unread || 0;
    elements.statSkipped.textContent = s.skipped || 0;
  }

  // ---------------------------------------------------------------------------
  // Rules Tab UI
  // ---------------------------------------------------------------------------
  function renderRulesUI() {
    if (!elements.rulesContainer) return;
    elements.rulesContainer.innerHTML = '';

    const rules = (state.currentConfig && state.currentConfig.rules) || [];
    rules.forEach((rule, idx) => {
      if (!Array.isArray(rule.keywords)) {
        if (typeof rule.keyword === 'string' && rule.keyword.length > 0) {
          rule.keywords = [rule.keyword];
        } else {
          rule.keywords = [''];
        }
      }
      if (rule.keywords.length === 0) {
        rule.keywords = [''];
      }
      if (!rule.matchType) {
        rule.matchType = 'ultra_exact';
      }

      if (!Array.isArray(rule.contextKeywords)) {
        if (typeof rule.contextKeyword === 'string' && rule.contextKeyword.length > 0) {
          rule.contextKeywords = [rule.contextKeyword];
        } else {
          rule.contextKeywords = [];
        }
      }
      if (!rule.contextMatchType) {
        rule.contextMatchType = 'contains';
      }

      const isLinked = state.linkedRulesMap && rule.ruleCode && (state.linkedRulesMap[rule.ruleCode] > 1);
      const linkedCount = isLinked ? state.linkedRulesMap[rule.ruleCode] : 0;

      const card = document.createElement('div');
      card.className = 'rule-card';
      card.innerHTML = `
        <div class="rule-meta-bar">
          <div class="rule-meta-left" style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
            <label class="switch">
              <input type="checkbox" class="rule-active" ${rule.active !== false ? 'checked' : ''}>
              <span class="slider"></span>
            </label>
            <span class="rule-title">قاعدة #${idx + 1}: <span class="rule-name-display">${escapeHtml(rule.name || 'بدون اسم')}</span> — (كود: <bdi dir="ltr">${escapeHtml(rule.ruleCode || 'MBS-XXXXXXXX')}</bdi>)</span>
            ${rule.ruleCode ? `
              <button type="button" class="btn-copy-rule-code" data-rule-code="${escapeHtml(rule.ruleCode)}" title="نسخ كود القاعدة">
                ${ICONS.copy}
                <span class="copy-code-feedback">نسخ الكود</span>
              </button>
            ` : ''}
            ${isLinked ? `
              <span class="badge-linked" title="مشتركة بين ${linkedCount} بروفايلات">
                مرتبطة (Linked — ${linkedCount} بروفايلات)
              </span>
              <button type="button" class="btn-unlink-rule" data-rule-id="${escapeHtml(rule.id || '')}" title="فك ارتباط هذه القاعدة">
                فك الارتباط
              </button>
            ` : ''}
          </div>
          <div class="rule-meta-right">
            <select class="glass-select rule-match-type" title="نوع المطابقة">
              <option value="ultra_exact" ${rule.matchType === 'ultra_exact' ? 'selected' : ''}>تطابق حرفي صارم (Ultra Exact)</option>
              <option value="contains" ${rule.matchType === 'contains' ? 'selected' : ''}>يحتوي (Contains)</option>
              <option value="exact" ${(rule.matchType === 'exact' || rule.matchType === 'word') ? 'selected' : ''}>تطابق كلمة / عبارة بحدود (Exact)</option>
              <option value="regex" ${rule.matchType === 'regex' ? 'selected' : ''}>تعبير نمطي (Regex)</option>
            </select>
            <button class="icon-action-btn rule-delete-btn" style="color: #dc2626;" title="حذف القاعدة">${ICONS.trash}</button>
          </div>
        </div>

        <div class="rule-field-group" style="margin-bottom: 8px;">
          <label style="font-size: 11.5px; font-weight: 600; color: #334155; display: block; margin-bottom: 2px;">
            اسم القاعدة:
          </label>
          <input type="text" class="config-input rule-name-input" placeholder="اسم القاعدة (مثال: استفسار عن السعر)..." value="${escapeHtml(rule.name || '')}">
        </div>

        <div class="rule-section">
          <div class="rule-section-header" style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <label class="rule-section-label" style="margin-bottom: 0;">الكلمات المفتاحية:</label>
              <span class="rule-section-hint">كل مربع نص يحفظ الكلمة أو العبارة بدقة (مع الفواصل والمسافات والأسطر)</span>
            </div>
            <button type="button" class="btn-copy-keywords" data-rule-id="${rule.id || idx}" title="نسخ كافة الكلمات">
              ${ICONS.copy}
              <span>نسخ الكلمات</span>
            </button>
          </div>
          <div class="keywords-list-container"></div>
          <div style="margin-top: 6px;">
            <button type="button" class="btn-add-keyword action-btn">+ إضافة كلمة مفتاحية</button>
          </div>
        </div>

        <div class="rule-field-group context-group" style="margin-top: 8px; border-top: 1px dashed rgba(255,255,255,0.08); padding-top: 8px;">
          <label style="font-size: 11px; opacity: 0.8; display: block; margin-bottom: 4px;">
            سياق الإعلان أو الرسالة التلقائية (اختياري - اتركها فارغة للقواعد العامة):
          </label>
          <div class="context-keywords-list-container"></div>
          <div style="margin-top: 4px;">
            <button type="button" class="btn-add-context-keyword action-btn">+ إضافة سياق إعلان</button>
          </div>
        </div>

        <div class="rule-section" style="margin-bottom: 0;">
          <div class="rule-section-header">
            <label class="rule-section-label">نص الرد التلقائي:</label>
            <span style="display: inline-flex; align-items: center; gap: 4px; font-size: 10.5px; color: #0284c7; font-weight: 600;">
              ${ICONS.info}
              <span>كل سطر جديد (Enter) يُرسل كرسالة منفصلة</span>
            </span>
          </div>
          <textarea class="rule-reply config-input" rows="3" style="width: 100%; text-align: right; resize: vertical; line-height: 1.5;">${escapeHtml(rule.reply || '')}</textarea>
        </div>
      `;

      // Name input listener
      const nameInput = card.querySelector('.rule-name-input');
      const nameDisplay = card.querySelector('.rule-name-display');
      if (nameInput && nameDisplay) {
        nameInput.addEventListener('input', () => {
          rule.name = nameInput.value;
          nameDisplay.textContent = rule.name.trim() || 'بدون اسم';
        });
      }

      // Copy Rule Code button listener
      const btnCopyCode = card.querySelector('.btn-copy-rule-code');
      if (btnCopyCode) {
        btnCopyCode.addEventListener('click', async (e) => {
          e.stopPropagation();
          const codeVal = rule.ruleCode;
          if (!codeVal) return;
          let copied = false;
          if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
            try {
              await navigator.clipboard.writeText(codeVal);
              copied = true;
            } catch (_) {}
          }
          if (!copied) {
            try {
              const ta = document.createElement('textarea');
              ta.value = codeVal;
              ta.style.position = 'fixed';
              ta.style.opacity = '0';
              document.body.appendChild(ta);
              ta.focus();
              ta.select();
              document.execCommand('copy');
              document.body.removeChild(ta);
              copied = true;
            } catch (_) {}
          }
          if (copied) {
            const feedbackSpan = btnCopyCode.querySelector('.copy-code-feedback');
            btnCopyCode.classList.add('copied');
            if (feedbackSpan) feedbackSpan.textContent = 'تم النسخ!';
            setTimeout(() => {
              btnCopyCode.classList.remove('copied');
              if (feedbackSpan) feedbackSpan.textContent = 'نسخ الكود';
            }, 1800);
          }
        });
      }

      // Unlink button listener
      const btnUnlink = card.querySelector('.btn-unlink-rule');
      if (btnUnlink) {
        btnUnlink.addEventListener('click', async (e) => {
          e.stopPropagation();
          if (!confirm('هل أنت متأكد من فك ارتباط هذه القاعدة؟ سيتم توليد كود جديد مستقل ولن تتأثر البروفايلات الأخرى.')) return;
          const res = await callApi('unlink_rule', state.selectedProfile, rule.id);
          if (res && res.ok) {
            alert('تم فك ارتباط القاعدة بنجاح وتوليد كود جديد مستقل.');
            await selectProfile(state.selectedProfile);
            await refreshProfiles();
          } else {
            alert('تعذر فك الارتباط: ' + (res ? res.message : 'فشل غير معروف'));
          }
        });
      }

      // Primary Multiline Keyword Rows
      const keywordsContainer = card.querySelector('.keywords-list-container');
      const btnAddKeyword = card.querySelector('.btn-add-keyword');

      function renderKeywordRows() {
        keywordsContainer.innerHTML = '';
        if (!Array.isArray(rule.keywords) || rule.keywords.length === 0) {
          rule.keywords = [''];
        }
        rule.keywords.forEach((kw, kwIdx) => {
          const row = document.createElement('div');
          row.className = 'keyword-row';
          row.innerHTML = `
            <textarea class="keyword-textarea" rows="1" placeholder="اكتب الكلمة أو العبارة الحرفية...">${escapeHtml(kw)}</textarea>
            <button type="button" class="btn-remove-keyword" title="حذف الكلمة">&times;</button>
          `;
          const ta = row.querySelector('.keyword-textarea');
          ta.addEventListener('input', () => {
            rule.keywords[kwIdx] = ta.value;
            rule.keyword = rule.keywords.join(', ');
          });
          row.querySelector('.btn-remove-keyword').addEventListener('click', () => {
            if (rule.keywords.length > 1) {
              rule.keywords.splice(kwIdx, 1);
            } else {
              rule.keywords[0] = '';
            }
            rule.keyword = rule.keywords.join(', ');
            renderKeywordRows();
          });
          keywordsContainer.appendChild(row);
        });
      }
      renderKeywordRows();

      if (btnAddKeyword) {
        btnAddKeyword.addEventListener('click', () => {
          if (!Array.isArray(rule.keywords)) rule.keywords = [];
          rule.keywords.push('');
          renderKeywordRows();
          const textareas = keywordsContainer.querySelectorAll('.keyword-textarea');
          if (textareas.length > 0) {
            textareas[textareas.length - 1].focus();
          }
        });
      }

      // Primary Multiline Context Keyword Rows
      const contextContainer = card.querySelector('.context-keywords-list-container');
      const btnAddContext = card.querySelector('.btn-add-context-keyword');

      function renderContextKeywordRows() {
        contextContainer.innerHTML = '';
        if (!Array.isArray(rule.contextKeywords)) {
          rule.contextKeywords = [];
        }
        rule.contextKeywords.forEach((ckw, ckwIdx) => {
          const row = document.createElement('div');
          row.className = 'context-keyword-row';
          row.innerHTML = `
            <textarea class="context-keyword-textarea" rows="1" placeholder="اكتب سياق الإعلان...">${escapeHtml(ckw)}</textarea>
            <button type="button" class="btn-remove-context-keyword" title="حذف السياق">&times;</button>
          `;
          const ta = row.querySelector('.context-keyword-textarea');
          ta.addEventListener('input', () => {
            rule.contextKeywords[ckwIdx] = ta.value;
            rule.contextKeyword = rule.contextKeywords.join(', ');
          });
          row.querySelector('.btn-remove-context-keyword').addEventListener('click', () => {
            rule.contextKeywords.splice(ckwIdx, 1);
            rule.contextKeyword = rule.contextKeywords.join(', ');
            renderContextKeywordRows();
          });
          contextContainer.appendChild(row);
        });
      }
      renderContextKeywordRows();

      if (btnAddContext) {
        btnAddContext.addEventListener('click', () => {
          if (!Array.isArray(rule.contextKeywords)) rule.contextKeywords = [];
          rule.contextKeywords.push('');
          renderContextKeywordRows();
          const textareas = contextContainer.querySelectorAll('.context-keyword-textarea');
          if (textareas.length > 0) {
            textareas[textareas.length - 1].focus();
          }
        });
      }

      // Copy Keywords Button
      const copyBtn = card.querySelector('.btn-copy-keywords');
      if (copyBtn) {
        copyBtn.addEventListener('click', async (e) => {
          e.stopPropagation();
          const kwList = Array.isArray(rule.keywords) && rule.keywords.length > 0
            ? rule.keywords.filter(k => k.length > 0)
            : [];
          const textToCopy = kwList.join('\n');
          if (!textToCopy) return;

          let copied = false;
          if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
            try {
              await navigator.clipboard.writeText(textToCopy);
              copied = true;
            } catch (_) {}
          }
          if (!copied) {
            try {
              const ta = document.createElement('textarea');
              ta.value = textToCopy;
              ta.style.position = 'fixed';
              ta.style.opacity = '0';
              document.body.appendChild(ta);
              ta.focus();
              ta.select();
              document.execCommand('copy');
              document.body.removeChild(ta);
              copied = true;
            } catch (_) {}
          }
          if (copied) {
            const origHtml = copyBtn.innerHTML;
            copyBtn.classList.add('copied');
            copyBtn.innerHTML = `
              ${ICONS.check}
              <span>تم النسخ</span>
            `;
            setTimeout(() => {
              copyBtn.classList.remove('copied');
              copyBtn.innerHTML = origHtml;
            }, 1500);
          }
        });
      }

      // Card Action Handlers
      card.querySelector('.rule-delete-btn').addEventListener('click', () => {
        rules.splice(idx, 1);
        renderRulesUI();
      });

      card.querySelector('.rule-active').addEventListener('change', (e) => {
        rule.active = e.target.checked;
      });

      card.querySelector('.rule-match-type').addEventListener('change', (e) => {
        rule.matchType = e.target.value;
      });

      card.querySelector('.rule-reply').addEventListener('input', (e) => {
        rule.reply = e.target.value;
      });

      elements.rulesContainer.appendChild(card);
    });
  }

  // ---------------------------------------------------------------------------
  // Config Tab UI
  // ---------------------------------------------------------------------------
  function renderConfigUI() {
    if (!state.currentConfig) return;
    const c = state.currentConfig.config || {};
    const cooldownSec = c.maxCooldown ? Number(((c.minCooldown + c.maxCooldown) / 2000).toFixed(1)) : 1.5;
    const monitoringSec = c.monitoringInterval ? Number((c.monitoringInterval / 1000).toFixed(1)) : 5.0;

    if (elements.cfgInboxUrl) {
      elements.cfgInboxUrl.value = state.currentConfig.inboxUrl || (c.inboxUrl || '');
    }
    elements.cfgCooldown.value = cooldownSec;
    elements.cfgMonitoring.value = monitoringSec;
    elements.cfgTypingSpeed.value = c.typingSpeed || 15;
    elements.cfgHighlight.checked = c.highlightRows !== false;
    elements.cfgAutoStart.checked = state.currentConfig.auto_start === true;
  }

  // ---------------------------------------------------------------------------
  // Modal Interactions
  // ---------------------------------------------------------------------------
  function openProfileModal(mode, targetProfile = null) {
    state.modalMode = mode;
    state.modalTargetProfile = targetProfile;
    elements.modalTitle.textContent = mode === 'create' ? 'إضافة بروفايل صفحة جديد' : `إعادة تسمية "${targetProfile}"`;
    elements.modalInput.value = mode === 'rename' ? targetProfile : '';
    elements.modalProfile.classList.add('active');
    elements.modalInput.focus();
  }

  function closeProfileModal() {
    elements.modalProfile.classList.remove('active');
    state.modalMode = null;
    state.modalTargetProfile = null;
  }

  async function confirmProfileModal() {
    const name = elements.modalInput.value.trim();
    if (!name) return alert('يرجى إدخال اسم صحيح.');

    try {
      if (state.modalMode === 'create') {
        await callApi('create_profile', name);
      } else if (state.modalMode === 'rename') {
        await callApi('rename_profile', state.modalTargetProfile, name);
      }
      closeProfileModal();
      await refreshProfiles();
      selectProfile(name);
    } catch (e) {
      alert(`تعذر تنفيذ العملية: ${e.message || e}`);
    }
  }

  // ---------------------------------------------------------------------------
  // Event Listeners
  // ---------------------------------------------------------------------------
  function setupEventListeners() {
    // Tabs
    elements.tabs.forEach(btn => {
      btn.addEventListener('click', () => {
        elements.tabs.forEach(t => t.classList.remove('active'));
        elements.tabPanes.forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        const targetId = `tab-${btn.dataset.tab}`;
        const pane = document.getElementById(targetId);
        if (pane) pane.classList.add('active');

        if (btn.dataset.tab === 'rules') {
          renderRulesUI();
        } else if (btn.dataset.tab === 'config') {
          renderConfigUI();
        }
      });
    });

    // Profile actions
    elements.btnNewProfile.addEventListener('click', () => openProfileModal('create'));
    elements.btnModalCancel.addEventListener('click', closeProfileModal);
    elements.btnModalConfirm.addEventListener('click', confirmProfileModal);
    elements.modalInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') confirmProfileModal();
      if (e.key === 'Escape') closeProfileModal();
    });

    // Active Start / Stop (In-page automation loop)
    elements.btnActiveStart.addEventListener('click', async () => {
      if (!state.selectedProfile) return;
      const current = state.profiles.find(p => p.name === state.selectedProfile);
      const isBrowserRunning = current && current.status === 'RUNNING';
      if (!isBrowserRunning) {
        // Browser stopped: launch browser visibly first (main.py sends START once loaded)
        await callApi('start_profile', state.selectedProfile, false);
      } else {
        // Browser already running: resume/start in-page automation
        await callApi('send_page_command', state.selectedProfile, 'START');
        state.automationState[state.selectedProfile] = 'RUNNING';
      }
      await refreshProfiles();
      const updated = state.profiles.find(p => p.name === state.selectedProfile);
      if (updated) updateProfileHeaderUI(updated);
    });

    elements.btnActiveStop.addEventListener('click', async () => {
      if (!state.selectedProfile) return;
      // Pause in-page automation without stopping the browser
      await callApi('send_page_command', state.selectedProfile, 'STOP');
      state.automationState[state.selectedProfile] = 'STOPPED';
      const current = state.profiles.find(p => p.name === state.selectedProfile);
      if (current) updateProfileHeaderUI(current);
    });

    // Start / Stop All
    elements.btnStartAll.addEventListener('click', async () => {
      await callApi('start_all_profiles');
      await refreshProfiles();
    });
    elements.btnStopAll.addEventListener('click', async () => {
      await callApi('stop_all_profiles');
      await refreshProfiles();
    });

    // Clear logs
    elements.btnClearLogs.addEventListener('click', () => {
      if (state.selectedProfile) {
        state.logs[state.selectedProfile] = [];
        elements.terminal.innerHTML = '';
      }
    });

    // Add Rule
    elements.btnAddRule.addEventListener('click', async () => {
      if (!state.currentConfig) state.currentConfig = { rules: [] };
      if (!state.currentConfig.rules) state.currentConfig.rules = [];

      let meta = null;
      try {
        meta = await callApi('allocate_rule_metadata', state.selectedProfile);
      } catch (_) {}

      const newId = (meta && meta.id) ? meta.id : `rule_${Date.now()}`;
      const newCode = (meta && meta.ruleCode) ? meta.ruleCode : '';

      state.currentConfig.rules.unshift({
        id: newId,
        ruleCode: newCode,
        name: '',
        keywords: [''],
        keyword: '',
        contextKeywords: [],
        contextKeyword: '',
        contextMatchType: 'contains',
        reply: '',
        matchType: 'ultra_exact',
        active: true
      });

      renderRulesUI();

      if (elements.tabRules) {
        elements.tabRules.scrollTo({ top: 0, behavior: 'smooth' });
      }

      const firstCard = elements.rulesContainer?.querySelector('.rule-card');
      const kwTa = firstCard?.querySelector('.keyword-textarea');
      if (kwTa) {
        setTimeout(() => kwTa.focus(), 60); // chipInput.focus()
      }
    });

    // Save Rules
    elements.btnSaveRules.addEventListener('click', async () => {
      if (!state.selectedProfile || !state.currentConfig) return;

      const cards = elements.rulesContainer ? elements.rulesContainer.querySelectorAll('.rule-card') : [];
      if (cards.length > 0 && Array.isArray(state.currentConfig.rules)) {
        cards.forEach((card, idx) => {
          const rule = state.currentConfig.rules[idx];
          if (!rule) return;

          const nameInput = card.querySelector('.rule-name-input');
          if (nameInput) rule.name = nameInput.value;

          const matchSelect = card.querySelector('.rule-match-type');
          if (matchSelect) rule.matchType = matchSelect.value || 'ultra_exact';

          const activeCheck = card.querySelector('.rule-active');
          if (activeCheck) rule.active = activeCheck.checked;

          const replyTa = card.querySelector('.rule-reply');
          if (replyTa) rule.reply = replyTa.value;

          const cardKeywords = [];
          card.querySelectorAll('.keyword-row .keyword-textarea').forEach(ta => {
            if (ta.value.length > 0) cardKeywords.push(ta.value);
          });
          rule.keywords = cardKeywords;
          rule.keyword = cardKeywords.join(', ');

          const cardContextKeywords = [];
          card.querySelectorAll('.context-keyword-row .context-keyword-textarea').forEach(ta => {
            if (ta.value.length > 0) cardContextKeywords.push(ta.value);
          });
          rule.contextKeywords = cardContextKeywords;
          rule.contextKeyword = cardContextKeywords.join(', ');
        });
      }

      let res = null;
      try {
        res = await callApi('save_profile_config_coordinated', state.selectedProfile, state.currentConfig, state.currentConfigSha256);
      } catch (_) {
        res = await callApi('save_profile_config', state.selectedProfile, state.currentConfig);
      }

      if (res && (res.ok || res === true)) {
        if (res.sha256_token) state.currentConfigSha256 = res.sha256_token;
        if (res.runtime_refresh_failures && Object.keys(res.runtime_refresh_failures).length > 0) {
          alert('تم الحفظ على القرص، ولكن تعذر تحديث المتصفح النشط تلقائياً');
        } else {
          alert('تم حفظ وتحديث القواعد بنجاح');
        }
        await refreshProfiles();
        await selectProfile(state.selectedProfile);
      } else if (res && (res.code === 'LINK_CONFLICT' || res.error === 'LINK_CONFLICT')) {
        openLinkConflictModal(res);
      } else if (res && (res.code === 'STALE_CONFIG' || res.error === 'STALE_CONFIG')) {
        alert(res.message || 'تم تعديل ملف التهيئة بواسطة عملية أخرى منذ آخر تحميل. يرجى إعادة التحميل قبل الحفظ.');
        await selectProfile(state.selectedProfile);
      } else {
        alert('حدث خطأ أثناء حفظ القواعد: ' + (res ? res.message || res.error || 'فشل الحفظ' : 'فشل غير معروف'));
      }
    });

    // -------------------------------------------------------------------------
    // Import Rules Modal Actions
    // -------------------------------------------------------------------------
    let importSourceRules = [];

    function updateImportConfirmState() {
      if (!elements.importRulesList || !elements.btnImportConfirm) return;
      const checkedBoxes = elements.importRulesList.querySelectorAll('.import-rule-check:checked');
      const count = checkedBoxes.length;
      elements.btnImportConfirm.disabled = (count === 0);
      elements.btnImportConfirm.textContent = count > 0 ? `استيراد القواعد المحددة (${count})` : 'استيراد القواعد المحددة';
    }

    function renderImportRulesList(rules) {
      if (!elements.importRulesList) return;
      elements.importRulesList.innerHTML = '';
      rules.forEach((r, rIdx) => {
        const item = document.createElement('div');
        item.className = 'import-rule-item';
        item.style.cssText = 'padding: 8px; margin-bottom: 6px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; display: flex; gap: 8px; align-items: flex-start;';

        const kwList = Array.isArray(r.keywords) ? r.keywords : (r.keyword ? [r.keyword] : []);
        const kwText = kwList.join(', ');
        const replyText = r.reply || '';
        const codeDisplay = r.ruleCode || '';

        item.innerHTML = `
          <input type="checkbox" class="import-rule-check" data-rule-id="${escapeHtml(r.id || String(rIdx))}" style="margin-top: 4px; cursor: pointer;">
          <div style="flex: 1; min-width: 0;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
              <span style="font-weight: 600; font-size: 11.5px; color: #1e293b;">${escapeHtml(r.name || ('قاعدة #' + (rIdx + 1)))}</span>
              ${codeDisplay ? `<span style="font-family: monospace; font-size: 10.5px; color: #0284c7; background: rgba(56,189,248,0.1); padding: 1px 5px; border-radius: 4px;">${escapeHtml(codeDisplay)}</span>` : ''}
            </div>
            <div style="font-size: 11px; color: #475569; margin-bottom: 3px; word-break: break-word;">
              <strong>الكلمات:</strong> <span style="font-family: monospace; white-space: pre-wrap;">${escapeHtml(kwText)}</span>
            </div>
            <div style="font-size: 11px; color: #64748b; white-space: pre-wrap; max-height: 44px; overflow: hidden; text-overflow: ellipsis; word-break: break-word;">
              <strong>الرد:</strong> ${escapeHtml(replyText)}
            </div>
          </div>
        `;
        elements.importRulesList.appendChild(item);
      });

      elements.importRulesList.querySelectorAll('.import-rule-check').forEach(chk => {
        chk.addEventListener('change', updateImportConfirmState);
      });
    }

    if (elements.btnImportRules) {
      elements.btnImportRules.addEventListener('click', () => {
        if (!state.selectedProfile) {
          alert('يرجى اختيار بروفايل أولاً لاستيراد القواعد إليه.');
          return;
        }
        if (elements.importSourceSelect) {
          elements.importSourceSelect.innerHTML = '<option value="">-- اختر بروفايل مصدر --</option>';
          state.profiles.forEach(p => {
            if (p.name !== state.selectedProfile) {
              const opt = document.createElement('option');
              opt.value = p.name;
              opt.textContent = p.name;
              elements.importSourceSelect.appendChild(opt);
            }
          });
        }
        if (elements.importSelectionArea) elements.importSelectionArea.style.display = 'none';
        if (elements.importEmptyState) elements.importEmptyState.style.display = 'none';
        if (elements.importError) elements.importError.style.display = 'none';
        if (elements.btnImportConfirm) {
          elements.btnImportConfirm.disabled = true;
          elements.btnImportConfirm.textContent = 'استيراد القواعد المحددة';
        }
        importSourceRules = [];
        if (elements.modalImportRules) elements.modalImportRules.classList.add('active');
      });
    }

    if (elements.importSourceSelect) {
      elements.importSourceSelect.addEventListener('change', async () => {
        const src = elements.importSourceSelect.value;
        if (elements.importError) elements.importError.style.display = 'none';
        if (!src) {
          if (elements.importSelectionArea) elements.importSelectionArea.style.display = 'none';
          if (elements.importEmptyState) elements.importEmptyState.style.display = 'none';
          if (elements.btnImportConfirm) elements.btnImportConfirm.disabled = true;
          importSourceRules = [];
          return;
        }

        const cfg = await callApi('get_profile_config', src);
        importSourceRules = (cfg && Array.isArray(cfg.rules)) ? cfg.rules : [];
        if (!importSourceRules.length) {
          if (elements.importSelectionArea) elements.importSelectionArea.style.display = 'none';
          if (elements.importEmptyState) elements.importEmptyState.style.display = 'block';
          if (elements.btnImportConfirm) elements.btnImportConfirm.disabled = true;
        } else {
          if (elements.importEmptyState) elements.importEmptyState.style.display = 'none';
          if (elements.importSelectionArea) elements.importSelectionArea.style.display = 'block';
          renderImportRulesList(importSourceRules);
          updateImportConfirmState();
        }
      });
    }

    if (elements.btnImportSelectAll) {
      elements.btnImportSelectAll.addEventListener('click', () => {
        if (!elements.importRulesList) return;
        const boxes = elements.importRulesList.querySelectorAll('.import-rule-check');
        const allChecked = Array.from(boxes).every(b => b.checked);
        boxes.forEach(b => { b.checked = !allChecked; });
        updateImportConfirmState();
      });
    }

    if (elements.btnImportCancel) {
      elements.btnImportCancel.addEventListener('click', () => {
        if (elements.modalImportRules) elements.modalImportRules.classList.remove('active');
      });
    }

    if (elements.btnImportConfirm) {
      elements.btnImportConfirm.addEventListener('click', async () => {
        if (!state.selectedProfile) return;
        const src = elements.importSourceSelect ? elements.importSourceSelect.value : '';
        if (!src) return;

        const checkedBoxes = elements.importRulesList ? elements.importRulesList.querySelectorAll('.import-rule-check:checked') : [];
        const ruleIds = Array.from(checkedBoxes).map(b => b.dataset.ruleId);
        if (!ruleIds.length) return;

        const modeInput = document.querySelector('input[name="import-mode"]:checked');
        const mode = modeInput ? modeInput.value : 'clone';

        elements.btnImportConfirm.disabled = true;
        elements.btnImportConfirm.textContent = 'جاري الاستيراد...';

        const res = await callApi('import_rules_from_profile', state.selectedProfile, src, ruleIds, mode);
        if (res && res.ok) {
          if (elements.modalImportRules) elements.modalImportRules.classList.remove('active');
          await selectProfile(state.selectedProfile);
          await refreshProfiles();
          alert(`تم استيراد ${res.importedCount} قاعدة بنجاح إلى "${state.selectedProfile}" (${mode === 'link' ? 'ربط مشترك' : 'نسخ مستقل'})`);
        } else {
          const errMsg = (res && res.message) ? res.message : 'فشل استيراد القواعد.';
          if (elements.importError) {
            elements.importError.textContent = errMsg;
            elements.importError.style.display = 'block';
          } else {
            alert(errMsg);
          }
          elements.btnImportConfirm.disabled = false;
          updateImportConfirmState();
        }
      });
    }

    // -------------------------------------------------------------------------
    // Conflict Resolution Modal Actions
    // -------------------------------------------------------------------------
    let activeConflictData = null;
    let selectedAuthoritativeProfile = null;

    function openLinkConflictModal(conflictData) {
      if (!elements.modalLinkConflict) return;
      activeConflictData = conflictData;
      selectedAuthoritativeProfile = null;

      if (elements.conflictCodeBadge) {
        elements.conflictCodeBadge.textContent = conflictData.conflicting_code ? `كود القاعدة: ${conflictData.conflicting_code}` : '';
      }

      if (elements.conflictOptionsList) {
        elements.conflictOptionsList.innerHTML = '';
        const parts = conflictData.participating_profiles || [];
        parts.forEach((item) => {
          const pName = item.profile_name;
          const r = item.rule || {};
          const card = document.createElement('div');
          card.className = 'conflict-option-card';
          card.dataset.profileName = pName;

          const ruleNameDisplay = (r.name && r.name.trim()) ? r.name : 'بدون اسم';
          const kwSnippet = Array.isArray(r.keywords) ? r.keywords.join(', ') : (r.keyword || '');
          const replySnippet = (r.reply || '').slice(0, 70) + ((r.reply && r.reply.length > 70) ? '...' : '');

          card.innerHTML = `
            <div class="conflict-option-header">
              <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; width: 100%;">
                <input type="radio" name="conflict-auth-radio" value="${escapeHtml(pName)}">
                <span class="conflict-profile-badge">بروفايل: ${escapeHtml(pName)}</span>
                <span style="font-size: 11px; color: #64748b;">(قاعدة: ${escapeHtml(ruleNameDisplay)})</span>
              </label>
            </div>
            <div class="conflict-rule-preview">
              <div><strong>الكلمات المفتاحية:</strong> ${escapeHtml(kwSnippet || '—')}</div>
              <div><strong>نص الرد:</strong> ${escapeHtml(replySnippet || '—')}</div>
            </div>
          `;

          card.addEventListener('click', () => {
            const radio = card.querySelector('input[type="radio"]');
            if (radio) radio.checked = true;
            elements.conflictOptionsList.querySelectorAll('.conflict-option-card').forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
            selectedAuthoritativeProfile = pName;
            if (elements.btnConflictResolve) elements.btnConflictResolve.disabled = false;
          });

          elements.conflictOptionsList.appendChild(card);
        });
      }

      if (elements.btnConflictResolve) elements.btnConflictResolve.disabled = true;
      elements.modalLinkConflict.classList.add('active');
    }

    function closeLinkConflictModal() {
      if (elements.modalLinkConflict) {
        elements.modalLinkConflict.classList.remove('active');
      }
      activeConflictData = null;
      selectedAuthoritativeProfile = null;
    }

    if (elements.btnConflictCancel) {
      elements.btnConflictCancel.addEventListener('click', async () => {
        closeLinkConflictModal();
        if (state.selectedProfile) {
          await selectProfile(state.selectedProfile);
        }
      });
    }

    if (elements.btnConflictResolve) {
      elements.btnConflictResolve.addEventListener('click', async () => {
        if (!activeConflictData || !selectedAuthoritativeProfile) return;
        const code = activeConflictData.conflicting_code;
        const expectedShas = {};
        if (activeConflictData.participating_profiles) {
          activeConflictData.participating_profiles.forEach(p => {
            expectedShas[p.profile_name] = p.sha256_token;
          });
        }

        elements.btnConflictResolve.disabled = true;
        let res = null;
        try {
          res = await callApi('resolve_link_conflict', code, selectedAuthoritativeProfile, expectedShas);
        } catch (err) {
          alert('حدث خطأ أثناء تسوية التضارب: ' + err);
          elements.btnConflictResolve.disabled = false;
          return;
        }

        if (res && res.ok) {
          closeLinkConflictModal();
          if (res.runtime_refresh_failures && Object.keys(res.runtime_refresh_failures).length > 0) {
            alert('تم الحفظ على القرص، ولكن تعذر تحديث المتصفح النشط تلقائياً');
          } else {
            alert('تمت تسوية تضارب القاعدة المشتركة وتطبيق التحديثات بنجاح');
          }
          await refreshProfiles();
          if (state.selectedProfile) {
            await selectProfile(state.selectedProfile);
          }
        } else {
          alert('فشل تسوية التضارب: ' + (res ? res.message || res.error || 'خطأ غير معروف' : 'فشل الاتصال'));
          elements.btnConflictResolve.disabled = false;
        }
      });
    }

    // Save Config
    elements.btnSaveConfig.addEventListener('click', async () => {
      if (!state.selectedProfile || !state.currentConfig) return;
      const cooldownSec = parseFloat(elements.cfgCooldown.value) || 1.5;
      const monitoringSec = parseFloat(elements.cfgMonitoring.value) || 5.0;
      const speed = parseInt(elements.cfgTypingSpeed.value, 10) || 15;
      const inboxUrl = elements.cfgInboxUrl ? elements.cfgInboxUrl.value.trim() : '';

      if (!state.currentConfig.config) state.currentConfig.config = {};
      state.currentConfig.inboxUrl = inboxUrl;
      state.currentConfig.config.inboxUrl = inboxUrl;
      state.currentConfig.config.typingSpeed = speed;
      state.currentConfig.config.minTypingSpeed = Math.max(10, speed - 4);
      state.currentConfig.config.maxTypingSpeed = speed + 4;
      state.currentConfig.config.minCooldown = Math.max(200, Math.round(cooldownSec * 1000 - 150));
      state.currentConfig.config.maxCooldown = Math.round(cooldownSec * 1000 + 150);
      state.currentConfig.config.monitoringInterval = Math.round(monitoringSec * 1000);
      state.currentConfig.config.highlightRows = elements.cfgHighlight.checked;
      state.currentConfig.auto_start = elements.cfgAutoStart.checked;

      let res = null;
      try {
        res = await callApi('save_profile_config_coordinated', state.selectedProfile, state.currentConfig, state.currentConfigSha256);
      } catch (err) {
        alert('حدث خطأ أثناء حفظ الإعدادات: ' + err);
        return;
      }

      if (res && res.ok) {
        if (res.sha256_token) state.currentConfigSha256 = res.sha256_token;
        // [P2-GUI-01] Synchronize live runtime configuration with running browser
        const current = state.profiles.find(p => p.name === state.selectedProfile);
        const isRunning = current && current.status === 'RUNNING';
        if (isRunning) {
          await callApi('send_page_command', state.selectedProfile, 'RELOAD_CONFIG', state.currentConfig.config);
        }
        if (res.runtime_refresh_failures && Object.keys(res.runtime_refresh_failures).length > 0) {
          alert('تم الحفظ على القرص، ولكن تعذر تحديث المتصفح النشط تلقائياً');
        } else {
          alert('تم حفظ الإعدادات وتطبيقها بنجاح');
        }
        await refreshProfiles();
      } else if (res && (res.code === 'LINK_CONFLICT' || res.error === 'LINK_CONFLICT')) {
        openLinkConflictModal(res);
      } else if (res && (res.code === 'STALE_CONFIG' || res.error === 'STALE_CONFIG')) {
        alert(res.message || 'تم تعديل ملف التهيئة بواسطة عملية أخرى منذ آخر تحميل. يرجى إعادة التحميل قبل الحفظ.');
        await selectProfile(state.selectedProfile);
      } else {
        alert('حدث خطأ أثناء حفظ الإعدادات: ' + (res ? res.message || res.error || 'فشل الحفظ' : 'فشل غير معروف'));
      }
    });
  }

  // ---------------------------------------------------------------------------
  // App Initialization
  // ---------------------------------------------------------------------------
  function init() {
    setupEventListeners();
    refreshProfiles();
  }

  if (window.pywebview) {
    init();
  } else {
    window.addEventListener('pywebviewready', init);
    // Fallback timer if event already fired
    setTimeout(() => {
      if (!state.profiles.length) refreshProfiles();
    }, 1000);
  }
})();

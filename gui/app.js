/**
 * Meta Automation Desktop Control Center (V6.2.1)
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
    save: `<svg class="sf-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>`
  };

  const state = {
    profiles: [],
    selectedProfile: null,
    currentConfig: null,
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
    btnAddRule: document.getElementById('add-rule-btn'),
    btnSaveRules: document.getElementById('btn-save-rules'),
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
      const prof = state.profiles.find(p => p.name === profName);
      if (prof) {
        const isStopped = statusText === 'READY' || statusText === 'جاهز' || statusText === 'STOPPED';
        prof.status = isStopped ? 'STOPPED' : 'RUNNING';
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
          <span class="profile-card-rules-tag">${p.rules_count || 0} قاعدة رد</span>
          <button class="btn-card-toggle ${isRunning ? 'stop' : 'start'}">
            ${isRunning ? `${ICONS.stop} <span>إيقاف</span>` : `${ICONS.play} <span>تشغيل</span>`}
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

    // Load Config & Rules
    const cfg = await callApi('get_profile_config', profileName);
    state.currentConfig = cfg || { rules: [], config: {} };
    renderRulesUI();
    renderConfigUI();
  }

  function updateProfileHeaderUI(prof) {
    if (!prof) return;
    elements.activeProfileName.textContent = prof.name;
    const isRunning = prof.status === 'RUNNING';

    elements.activeProfileStatus.innerHTML = `
      <span class="ghost-dot ${isRunning ? 'running' : 'stopped'}" style="margin-left: 6px;"></span>
      <span>${isRunning ? 'يعمل بالمتصفح' : 'جاهز للتشغيل'}</span>
    `;
    elements.activeProfileStatus.className = `stage-status-badge ${isRunning ? 'status-running' : 'status-ready'}`;

    elements.btnActiveStart.style.display = isRunning ? 'none' : 'inline-flex';
    elements.btnActiveStop.style.display = isRunning ? 'inline-flex' : 'none';
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
      const card = document.createElement('div');
      card.className = 'rule-item';
      card.style.cssText = 'background: rgba(255, 255, 255, 0.45); border: 1px solid rgba(255, 255, 255, 0.7); border-radius: 14px; padding: 14px; margin-bottom: 12px; box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);';
      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <label class="switch">
              <input type="checkbox" class="rule-active" ${rule.active !== false ? 'checked' : ''}>
              <span class="slider"></span>
            </label>
            <span style="font-size: 13px; font-weight: 600; color: #0f172a;">قاعدة #${idx + 1}</span>
          </div>
          <button class="icon-action-btn rule-delete-btn" style="color: #dc2626;" title="حذف القاعدة">${ICONS.trash}</button>
        </div>
        <div style="margin-bottom: 10px;">
          <label style="display: block; font-size: 11.5px; color: #475569; margin-bottom: 4px; font-weight: 500;">الكلمات الدلالية المفتاحية (مفصولة بفواصل):</label>
          <input type="text" class="rule-keyword config-input" style="width: 100%; text-align: right;" value="${escapeHtml(rule.keyword || '')}">
        </div>
        <div>
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <label style="font-size: 11.5px; color: #475569; font-weight: 500;">نص الرد التلقائي:</label>
            <span style="display: inline-flex; align-items: center; gap: 4px; font-size: 10.5px; color: #0284c7; font-weight: 600;">
              ${ICONS.info}
              <span>كل سطر جديد (Enter) يُرسل كرسالة منفصلة</span>
            </span>
          </div>
          <textarea class="rule-reply config-input" rows="3" style="width: 100%; text-align: right; resize: vertical; line-height: 1.5;">${escapeHtml(rule.reply || '')}</textarea>
        </div>
      `;

      card.querySelector('.rule-delete-btn').addEventListener('click', () => {
        rules.splice(idx, 1);
        renderRulesUI();
      });

      card.querySelector('.rule-active').addEventListener('change', (e) => {
        rule.active = e.target.checked;
      });

      card.querySelector('.rule-keyword').addEventListener('input', (e) => {
        rule.keyword = e.target.value;
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

    // Active Start / Stop
    elements.btnActiveStart.addEventListener('click', async () => {
      if (!state.selectedProfile) return;
      const current = state.profiles.find(p => p.name === state.selectedProfile);
      const isRunning = current && current.status === 'RUNNING';
      if (!isRunning) {
        await callApi('start_profile', state.selectedProfile, false);
      } else {
        await callApi('send_page_command', state.selectedProfile, 'START');
      }
      await refreshProfiles();
    });
    elements.btnActiveStop.addEventListener('click', async () => {
      if (!state.selectedProfile) return;
      await callApi('send_page_command', state.selectedProfile, 'STOP');
      await refreshProfiles();
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
    elements.btnAddRule.addEventListener('click', () => {
      if (!state.currentConfig) state.currentConfig = { rules: [] };
      if (!state.currentConfig.rules) state.currentConfig.rules = [];
      state.currentConfig.rules.push({
        id: `rule_${Date.now()}`,
        keyword: '',
        reply: '',
        matchType: 'contains',
        active: true
      });
      renderRulesUI();
    });

    // Save Rules
    elements.btnSaveRules.addEventListener('click', async () => {
      if (!state.selectedProfile || !state.currentConfig) return;
      await callApi('save_profile_config', state.selectedProfile, state.currentConfig);

      const current = state.profiles.find(p => p.name === state.selectedProfile);
      const isRunning = current && current.status === 'RUNNING';
      if (isRunning) {
        await callApi('send_page_command', state.selectedProfile, 'RELOAD_RULES', state.currentConfig.rules);
      }

      alert('تم حفظ وتحديث القواعد بنجاح');
      await refreshProfiles();
    });

    // Save Config
    elements.btnSaveConfig.addEventListener('click', async () => {
      if (!state.selectedProfile || !state.currentConfig) return;
      const cooldownSec = parseFloat(elements.cfgCooldown.value) || 1.5;
      const monitoringSec = parseFloat(elements.cfgMonitoring.value) || 5.0;
      const speed = parseInt(elements.cfgTypingSpeed.value, 10) || 15;

      if (!state.currentConfig.config) state.currentConfig.config = {};
      state.currentConfig.config.typingSpeed = speed;
      state.currentConfig.config.minTypingSpeed = Math.max(10, speed - 4);
      state.currentConfig.config.maxTypingSpeed = speed + 4;
      state.currentConfig.config.minCooldown = Math.max(200, Math.round(cooldownSec * 1000 - 150));
      state.currentConfig.config.maxCooldown = Math.round(cooldownSec * 1000 + 150);
      state.currentConfig.config.monitoringInterval = Math.round(monitoringSec * 1000);
      state.currentConfig.config.highlightRows = elements.cfgHighlight.checked;
      state.currentConfig.auto_start = elements.cfgAutoStart.checked;

      await callApi('save_profile_config', state.selectedProfile, state.currentConfig);
      alert('تم حفظ الإعدادات وتطبيقها بنجاح');
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

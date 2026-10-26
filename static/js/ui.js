/* ===== Voz Cloud — funciones de interfaz (solo DOM, sin red) ===== */
(function (global) {
  'use strict';

  const $ = id => document.getElementById(id);
  const LEVELS = [
    { k: 'INFO',    label: 'Info' },
    { k: 'SUCCESS', label: 'Éxito' },
    { k: 'WARNING', label: 'Advertencia' },
    { k: 'ERROR',   label: 'Error' },
    { k: 'ACTION',  label: 'Intervención' }
  ];
  const LEVEL_LABEL = {}; LEVELS.forEach(l => { LEVEL_LABEL[l.k] = l.label; });
  const AGENT_STATES = { idle: 'Ocioso', working: 'Trabajando', done: 'Terminado', failed: 'Fallido', waiting: 'En espera' };
  const STATE_CLASS = { idle: '', working: 'st-working', done: 'st-done', failed: 'st-failed', waiting: 'st-waiting' };

  const esc = s => String(s === undefined || s === null ? '' : s).replace(/[&<>"']/g, c => (
    { '&': '&', '<': '<', '>': '>', '"': '"', "'": ''' }[c]));
  const p2 = n => String(n).padStart(2, '0');
  const toMs = ts => (ts && ts < 1e12 ? ts * 1000 : ts || Date.now());
  const fmtTime = ts => { const d = new Date(toMs(ts)); return p2(d.getHours()) + ':' + p2(d.getMinutes()) + ':' + p2(d.getSeconds()); };
  function ago(ts) {
    const s = Math.max(0, Math.round((Date.now() - toMs(ts)) / 1000));
    if (s < 5) return 'ahora';
    if (s < 60) return 'hace ' + s + ' s';
    if (s < 3600) return 'hace ' + Math.floor(s / 60) + ' min';
    return 'hace ' + Math.floor(s / 3600) + ' h';
  }

  /* ----- Toasts ----- */
  function toast(msg, level) {
    const box = $('toasts'); if (!box) return;
    const el = document.createElement('div');
    el.className = 'toast' + (level ? ' lv-' + level : '');
    el.textContent = msg;
    box.appendChild(el);
    while (box.children.length > 4) box.removeChild(box.firstChild);
    setTimeout(() => { if (el.parentNode) el.parentNode.removeChild(el); }, 4500);
  }

  /* ----- Estado global / demo ----- */
  function setGlobal(worst) {
    const el = $('globalStatus'); if (!el) return;
    const map = {
      ok:   ['pill pill-ok',   'Todo funcionando'],
      warn: ['pill pill-warn', 'Atención: revisar componentes'],
      fail: ['pill pill-fail', 'Hay componentes caídos'],
      unknown: ['pill pill-unknown', 'Comprobando…']
    };
    const m = map[worst] || map.unknown;
    el.className = m[0]; el.textContent = m[1];
  }
  function setDemoBadge(n) {
    const el = $('demoBadge'); if (!el) return;
    el.hidden = n === 0;
    el.textContent = 'DEMO · ' + n + ' ruta' + (n === 1 ? '' : 's') + ' simulada' + (n === 1 ? '' : 's');
  }

  /* ----- Salud ----- */
  function renderHealth(data) {
    const list = $('healthList'); if (!list) return 'unknown';
    const checks = (data && data.checks) || [];
    list.innerHTML = checks.map(c => {
      const st = ['ok', 'warn', 'fail'].indexOf(c.status) >= 0 ? c.status : 'warn';
      return '<div class="health-item"><span class="dot dot-' + st + '" aria-hidden="true"></span>' +
        '<div><div class="name">' + esc(c.name) + '</div><div class="detail">' + esc(c.detail || '') + '</div></div>' +
        '<span class="lat">' + (c.latency_ms !== undefined && c.latency_ms !== null ? esc(c.latency_ms) + ' ms' : '—') + '</span></div>';
    }).join('') || '<p class="empty">Sin datos de salud</p>';
    const ts = $('healthTs'); if (ts) ts.textContent = 'Actualizado ' + fmtTime(data && data.ts);
    let worst = 'ok';
    checks.forEach(c => { if (c.status === 'fail') worst = 'fail'; else if (c.status === 'warn' && worst !== 'fail') worst = 'warn'; });
    return checks.length ? worst : 'unknown';
  }

  /* ----- Cola de voz ----- */
  function renderQueue(s) {
    s = s || {};
    const t = $('speakingText');
    if (t) {
      if (s.current && s.current.text) { t.textContent = s.current.text; t.className = 'speaking-text live'; }
      else { t.textContent = '— silencio —'; t.className = 'speaking-text muted'; }
    }
    const max = s.max || 8, q = s.queue || 0;
    const bar = $('queueBar');
    if (bar) { bar.style.width = Math.min(100, Math.round(q / max * 100)) + '%'; bar.className = 'meter-bar' + (q / max > 0.7 ? ' hot' : ''); }
    const set = (id, v) => { const el = $(id); if (el) el.textContent = v; };
    set('qSize', q + ' / ' + max);
    set('qDropped', s.dropped || 0);
    set('qMuted', s.muted ? 'Silenciada' : 'Activa');
    const b = $('btnMute');
    if (b) { b.setAttribute('aria-pressed', s.muted ? 'true' : 'false'); b.textContent = s.muted ? '🔇 Voz silenciada' : '🔊 Voz activa'; }
  }

  /* ----- Conexión por rutas ----- */
  function renderConn(routes, states) {
    const ul = $('connList'); if (!ul) return;
    ul.innerHTML = Object.keys(routes).map(k => {
      const st = states[k] || 'wait';
      const tag = st === 'live' ? ['tag tag-live', 'EN VIVO'] : st === 'demo' ? ['tag tag-demo', 'DEMO'] : ['tag tag-wait', '…'];
      return '<li><span class="route" title="' + esc(routes[k].method + ' ' + routes[k].path) + '">' +
        esc(routes[k].method) + ' ' + esc(routes[k].path) + '</span><span class="' + tag[0] + '">' + tag[1] + '</span></li>';
    }).join('');
  }

  /* ----- Agentes ----- */
  function renderAgents(list) {
    const grid = $('agentGrid'); if (!grid) return;
    list = list || [];
    const cnt = $('agentCount'); if (cnt) cnt.textContent = list.length + ' agente' + (list.length === 1 ? '' : 's');
    grid.innerHTML = list.map(a => {
      const sc = STATE_CLASS[a.state] || '';
      const stateLabel = AGENT_STATES[a.state] || a.state;
      // Determinar tarea actual basada en el estado y la última actividad
      let tareaActual = '—';
      if (a.state === 'working') tareaActual = 'Procesando';
      if (a.state === 'waiting') tareaActual = 'En espera de confirmación';
      if (a.state === 'failed') tareaActual = 'Error detectado';
      if (a.state === 'done') tareaActual = 'Tarea completada';
      return '<div class="agent ' + sc + '">' +
        '<div class="agent-top"><div><div class="agent-name">' + esc(a.name) + '</div><div class="agent-role">' + esc(a.role || '') + '</div></div>' +
        '<span class="badge ' + sc + '" title="Estado: ' + esc(stateLabel) + '">' + esc(stateLabel) + '</span></div>' +
        '<div class="agent-last">' + esc(a.last || '—') + '</div>' +
        '<div class="agent-foot">' +
          '<span>' + ago(a.ts) + '</span>' +
          (a.state !== 'idle' ? '<span class="muted small" title="Última actividad">' + ago(a.ts) + '</span>' : '') +
        '</div>' +
        (a.state !== 'idle' ? '<div class="agent-commands small">' +
          '<span class="cmd-ver">Ver comandos</span>' : '') +
        '</div>' +
        '</div>';
    }).join('') || '<p class="empty">Aún no hay agentes conectados</p>';
    // selector de filtro por agente
    const sel = $('feedAgent');
    if (sel) {
      const cur = sel.value;
      const names = list.map(a => a.name);
      const have = Array.prototype.map.call(sel.options, o => o.value).slice(1);
      if (names.join('|') !== have.join('|')) {
        sel.innerHTML = '<option value="">Todos los agentes</option>' + names.map(n => '<option value="' + esc(n) + '">' + esc(n) + '</option>').join('');
        sel.value = names.indexOf(cur) >= 0 ? cur : '';
      }
    }
  }

  /* ----- Eventos ----- */
  function buildLevelFilters(activeSet, onToggle) {
    const box = $('levelFilters'); if (!box) return;
    box.innerHTML = '';
    LEVELS.forEach(l => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'chip lv-' + l.k; b.textContent = l.label;
      b.setAttribute('aria-pressed', activeSet.has(l.k) ? 'true' : 'false');
      b.addEventListener('click', () => {
        if (activeSet.has(l.k)) activeSet.delete(l.k); else activeSet.add(l.k);
        b.setAttribute('aria-pressed', activeSet.has(l.k) ? 'true' : 'false');
        onToggle();
      });
      box.appendChild(b);
    });
  }
  function renderFeed(events, filters, auto) {
    const feed = $('feedList'); if (!feed) return;
    const list = events.filter(e => filters.levels.has(e.level) && (!filters.agent || e.agent === filters.agent)).slice(-200);
    feed.innerHTML = list.length ? list.map(e =>
      '<li data-text="' + esc(e.agent + ': ' + e.text) + '" title="Clic para copiar">' +
      '<span class="t">' + fmtTime(e.ts) + '</span>' +
      '<span class="lv lv-' + esc(e.level) + '">' + esc(LEVEL_LABEL[e.level] || e.level) + '</span>' +
      '<span class="ag">' + esc(e.agent) + '</span>' +
      '<span class="tx">' + esc(e.text) + '</span></li>').join('')
      : '<li class="empty" style="display:block">Sin eventos con estos filtros</li>';
    if (auto) feed.scrollTop = feed.scrollHeight;
  }

  /* ----- Voz ----- */
  function setMic(on, label) {
    const b = $('btnMic'); if (!b) return;
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
    const l = $('micLabel'); if (l) l.textContent = label || (on ? 'Escuchando…' : 'Micrófono apagado');
  }
  function setTranscript(text) { const t = $('transcript'); if (t) t.textContent = text || '—' }
  
  // Estado de voz en tiempo real
  const VOICE_STATES = {
    listening: { label: 'Escuchando', class: 'lv-listening' },
    processing: { label: 'Procesando', class: 'lv-processing' },
    confirming: { label: 'Confirmando', class: 'lv-confirming' },
    speaking: { label: 'Hablando', class: 'lv-speaking' },
    error: { label: 'Error', class: 'lv-error' }
  };
  function setVoiceState(stateKey) {
    const s = VOICE_STATES[stateKey] || VOICE_STATES.error;
    $('voiceState').className = 'voice-state ' + s.class;
    $('voiceState').textContent = s.label;
  }
  function clearVoiceState() {
    $('voiceState').className = 'voice-state';
    $('voiceState').textContent = '';
  }
  
  function addVoice(heard, reply) {
    const ul = $('voiceHistory'); if (!ul) return;
    const li = document.createElement('li');
    li.innerHTML = '<div class="heard">🎙 ' + esc(heard) + '</div><div class="reply">↳ ' + esc(reply) + '</div>';
    ul.insertBefore(li, ul.firstChild);
    while (ul.children.length > 20) ul.removeChild(ul.lastChild);
  }

  /* ----- Indicador JARVIS ----- */
  const JARVIS_STATE = {
    normal: 'normal',
    listening: 'listening',
    thinking: 'thinking',
    speaking: 'speaking',
    error: 'error'
  };
  let jarvisMode = false;
  function setJarvisMode(on) {
    jarvisMode = on;
    const root = document.documentElement;
    if (on) {
      root.classList.add('jarvis-mode');
    } else {
      root.classList.remove('jarvis-mode');
    }
  }
  function updateJarvisStatus(text, state) {
    const statusEl = $('jarvisStatus'); if (!statusEl) return;
    statusEl.textContent = text || '';
    statusEl.className = 'jarvis-status ' + (state || 'normal');
  }
  
  // Animación sutil para agentes activos
  function pulseAgent(agentEl) {
    if (!agentEl) return;
    agentEl.style.transition = 'box-shadow 0.3s';
    agentEl.style.boxShadow = '0 0 15px rgba(0, 255, 255, 0.4)';
    setTimeout(() => {
      agentEl.style.boxShadow = '';
    }, 300);
  }
  
  // Efecto de "activación" al recibir voz
  function activateJARVIS() {
    setJarvisMode(true);
    updateJarvisStatus('Sistema activo', 'listening');
    // Pulse todos los agentes visibles
    document.querySelectorAll('.agent').forEach(pulseAgent);
    // Reset after 3 seconds
    setTimeout(() => {
      updateJarvisStatus('Listo', 'normal');
      setJarvisMode(false);
    }, 3000);
  }

  /* ----- Modal de confirmación (con cuenta atrás) ----- */
  let modalOpen = false;
  function confirmModal(text, seconds) {
    if (modalOpen) return Promise.resolve(false);
    modalOpen = true;
    return new Promise(resolve => {
      const m = $('modal'), bar = $('modalBar'), yes = $('modalYes'), no = $('modalNo');
      $('modalText').textContent = text;
      m.hidden = false; yes.focus();
      const total = (seconds || 8) * 1000, t0 = Date.now();
      bar.style.transition = 'none'; bar.style.width = '100%';
      const tick = setInterval(() => {
        const left = Math.max(0, 1 - (Date.now() - t0) / total);
        bar.style.width = (left * 100) + '%';
        if (left <= 0) done(false);
      }, 100);
      function onKey(e) { if (e.key === 'Escape') done(false); }
      function done(v) {
        clearInterval(tick);
        document.removeEventListener('keydown', onKey);
        yes.onclick = null; no.onclick = null;
        m.hidden = true; modalOpen = false; resolve(v);
      }
      yes.onclick = () => done(true);
      no.onclick = () => done(false);
      document.addEventListener('keydown', onKey);
    });
  }

  /* ----- Configuración ----- */
  function buildCfgLevels() {
    const box = $('cfgLevels'); if (!box) return;
    box.innerHTML = LEVELS.map(l =>
      '<label class="check lv-' + l.k + '"><input type="checkbox" value="' + l.k + '"> ' + l.label + '</label>').join('');
  }
  function fillConfig(c) {
    c = c || {};
    document.querySelectorAll('#cfgLevels input').forEach(i => { i.checked = (c.levels || []).indexOf(i.value) >= 0; });
    const set = (id, v) => { const el = $(id); if (el) el.value = v === undefined || v === null ? '' : v; };
    set('cfgQuietStart', c.quiet_start); set('cfgQuietEnd', c.quiet_end);
    set('cfgDedupe', c.dedupe_s); set('cfgQueueMax', c.queue_max); set('cfgQueueAge', c.queue_age_s);
  }
  function readConfig() {
    const num = (id, d) => { const v = Number($(id).value); return isFinite(v) && $(id).value !== '' ? v : d; };
    return {
      levels: Array.prototype.map.call(document.querySelectorAll('#cfgLevels input:checked'), i => i.value),
      quiet_start: $('cfgQuietStart').value,
      quiet_end: $('cfgQuietEnd').value,
      dedupe_s: num('cfgDedupe', 30),
      queue_max: num('cfgQueueMax', 8),
      queue_age_s: num('cfgQueueAge', 60)
    };
  }

  /* ----- Reloj ----- */
  function tickClock() { const c = $('clock'); if (c) c.textContent = fmtTime(Date.now()); }

  global.UI = {
    $, LEVELS, LEVEL_LABEL, esc, fmtTime, ago, toMs, toast, setGlobal, setDemoBadge,
    renderHealth, renderQueue, renderConn, renderAgents, buildLevelFilters, renderFeed,
    setMic, setTranscript, addVoice, confirmModal, buildCfgLevels, fillConfig, readConfig, tickClock,
    setVoiceState, clearVoiceState, setJarvisMode, updateJarvisStatus, activateJARVIS
  };
})(window);
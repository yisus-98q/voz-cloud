/* ===== Voz Cloud — lógica de la aplicación (usa API y UI) ===== */
(function () {
  'use strict';

  const $ = UI.$;
  const S = {
    events: [], lastEventId: 0, firstEventLoad: true,
    voiceSeen: new Set(), lastVoiceId: 0,
    filters: { agent: '', levels: new Set(UI.LEVELS.map(l => l.k)) },
    muted: false, mic: false, recog: null,
    voiceState: 'idle', voiceStateTimer: null
  };

  /* Bucle sin solapamiento: espera a que termine antes de programar el siguiente */
  function loop(fn, ms) {
    (async function run() {
      try { await fn(); } catch (e) { console.error(fn.name, e); }
      setTimeout(run, ms);
    })();
  }

  /* ---------- Salud ---------- */
  async function pollHealth() {
    const d = await API.call('health', {});
    // Usar detalles si están disponibles, sino el reporte simple
    if (d && d.checks) {
      UI.setGlobal(UI.renderHealth(d));
      // Actualizar indicador de rutas según peor estado
      UI.setDemoBadge(Object.keys(d.checks).filter(k => d.checks[k].status === 'fail').length > 0 ? 1 : 0);
    } else {
      UI.setGlobal(UI.renderHealth(d));
    }
  }

  /* ---------- Estado de la cola ---------- */
  async function pollStatus() {
    const s = await API.call('status');
    S.muted = !!s.muted;
    UI.renderQueue(s);
    if (typeof s.mic === 'boolean' && s.mic !== S.mic && !S.recog) { S.mic = s.mic; UI.setMic(S.mic); }
    // Sincronizar estado visual de voz con el backend
    if (s.voice_state) {
      S.voiceState = s.voice_state;
      UI.setVoiceState(s.voice_state);
    }
  }

  /* ---------- Agentes ---------- */
  async function pollAgents() {
    const d = await API.call('agents');
    UI.renderAgents(d.agents || []);
  }

  // Manejar ejecución de comandos de agente
  async function execAgentCommand(agentId, command) {
    // Ejecutar comando mediante el interpretador de voz
    const r = await API.call('voice', { body: { text: command } });
    await handleVoiceItem(r);
    pollAgents(); pollStatus();
  }

  /* ---------- Eventos ---------- */
  function refreshFeed() { UI.renderFeed(S.events, S.filters, $('feedAuto').checked); }

  async function pollEvents() {
    const d = await API.call('events', { query: { since: S.lastEventId } });
    const fresh = (d.events || []).filter(e => e.id > S.lastEventId);
    if (!fresh.length) return;
    fresh.forEach(e => {
      e.ts = UI.toMs(e.ts);
      S.lastEventId = Math.max(S.lastEventId, e.id);
      S.events.push(e);
      if (!S.firstEventLoad && (e.level === 'ERROR' || e.level === 'ACTION')) UI.toast(e.agent + ': ' + e.text, e.level);
    });
    if (S.events.length > 500) S.events = S.events.slice(-500);
    S.firstEventLoad = false;
    refreshFeed();
  }

  /* ---------- Voz: comandos, confirmaciones y feed ---------- */
  async function handleVoiceItem(item) {
    if (!item || S.voiceSeen.has(item.id)) return;
    S.voiceSeen.add(item.id);
    S.lastVoiceId = Math.max(S.lastVoiceId, Number(item.id) || 0);
    UI.setTranscript(item.heard);
    UI.addVoice(item.heard, item.reply);
    
    // Gestionar estados de voz en tiempo real
    if (item.voice_state) {
      S.voiceState = item.voice_state;
      UI.setVoiceState(item.voice_state);
      // Limpiar estado automáticamente después de un retraso
      clearTimeout(S.voiceStateTimer);
      S.voiceStateTimer = setTimeout(() => {
        S.voiceState = 'idle';
        UI.clearVoiceState();
      }, 3000);
    }
    
    // Reproducir la respuesta por voz
    if (item.reply) {
      try { await API.call('speak', { body: { text: item.reply } }); } catch (e) { /* silencioso */ }
    }
    // Interrumpir TTS actual si hay nueva respuesta
    else if (item.voice_state === 'speaking') {
      try { await API.call('stt/speak-response'); } catch (e) { /* silencioso */ }
    }
    
    if (item.confirm) {
      const ok = await UI.confirmModal(item.confirm.text, item.confirm.timeout_s || 8);
      const r = await API.call('confirm', { body: { id: item.confirm.id, accept: ok } });
      if (r && r.reply) { S.voiceSeen.add(r.id); UI.addVoice(ok ? '(confirmado)' : '(cancelado)', r.reply); }
      pollAgents(); pollStatus();
    }
  }

  async function sendCommand(text) {
    text = String(text || '').trim();
    if (!text) return;
    UI.setTranscript(text);
    // Establecer estado "procesando" mientras se envía
    S.voiceState = 'processing';
    UI.setVoiceState('processing');
    clearTimeout(S.voiceStateTimer);
    S.voiceStateTimer = setTimeout(() => {
      if (S.voiceState === 'processing') {
        S.voiceState = 'idle';
        UI.clearVoiceState();
      }
    }, 5000);
    const item = await API.call('voice', { body: { text } });
    await handleVoiceItem(item);
    pollStatus();
  }

  async function pollVoiceFeed() {
    const d = await API.call('voiceFeed', { query: { since: S.lastVoiceId } });
    for (const it of (d.items || [])) await handleVoiceItem(it);
  }

  /* ---------- Micrófono ---------- */
  function startBrowserRecognition() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return false;
    const r = new SR();
    r.lang = 'es-PE'; r.continuous = true; r.interimResults = true;
    r.onresult = ev => {
      let interim = '';
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const t = ev.results[i][0].transcript;
        if (ev.results[i].isFinal) {
          if (/voz\s*cloud/i.test(t)) sendCommand(t);
          else UI.setTranscript('(ignorado, falta «Voz Cloud»): ' + t);
        } else interim += t;
      }
      if (interim) UI.setTranscript(interim + '…');
    };
    r.onerror = e => UI.toast('Micrófono: ' + e.error, 'WARNING');
    r.onend = () => { if (S.mic && S.recog === r) { try { r.start(); } catch (e) { /* ya iniciado */ } } };
    try { r.start(); } catch (e) { return false; }
    S.recog = r;
    return true;
  }
  function stopBrowserRecognition() {
    if (S.recog) { const r = S.recog; S.recog = null; try { r.stop(); } catch (e) { /* nada */ } }
  }

  async function toggleMic() {
    const want = !S.mic;
    const res = await API.call('mic', { value: want ? 'on' : 'off' });
    S.mic = !!(res && res.listening);
    if (API.states().mic === 'demo') {
      // Sin backend: usar el reconocimiento del navegador si existe
      if (want) {
        if (startBrowserRecognition()) S.mic = true;
        else { S.mic = false; UI.toast('Tu navegador no soporta voz. Escribe el comando en el cuadro.', 'WARNING'); }
      } else { stopBrowserRecognition(); S.mic = false; }
    }
    UI.setMic(S.mic);
  }

  /* ---------- Silencio ---------- */
  async function toggleMute() {
    const r = await API.call('mute', { value: String(!S.muted) });
    S.muted = !!(r && r.muted);
    pollStatus();
  }

  /* ---------- Configuración ---------- */
  async function loadConfig() { UI.fillConfig(await API.call('configGet')); }
  async function saveConfig(ev) {
    ev.preventDefault();
    const cfg = UI.readConfig();
    if (!cfg.levels.length) { UI.toast('Elige al menos un nivel para hablar.', 'WARNING'); return; }
    const saved = await API.call('configSet', { body: cfg });
    UI.fillConfig(saved);
    UI.toast('Configuración guardada.', 'SUCCESS');
  }

  /* ---------- Copiar diagnóstico ---------- */
  async function copyDiagnostic() {
    let text = await API.call('report');
    if (typeof text !== 'string') text = JSON.stringify(text, null, 2);
    try {
      await navigator.clipboard.writeText(text);
    } catch (e) {
      const ta = document.createElement('textarea');
      ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); } catch (e2) { /* sin permiso */ }
      document.body.removeChild(ta);
    }
    UI.toast('Diagnóstico copiado al portapapeles.', 'SUCCESS');
  }

  /* ---------- Indicador de rutas EN VIVO / DEMO ---------- */
  function onRouteState(states) {
    UI.renderConn(API.routes, states);
    UI.setDemoBadge(Object.keys(states).filter(k => states[k] === 'demo').length);
  }

  /* ---------- Arranque ---------- */
  function init() {
    UI.buildCfgLevels();
    UI.buildLevelFilters(S.filters.levels, refreshFeed);
    UI.renderConn(API.routes, API.states());
    API.onState(onRouteState);
    UI.tickClock(); setInterval(UI.tickClock, 1000);

    $('btnMute').addEventListener('click', toggleMute);
    $('btnMic').addEventListener('click', toggleMic);
    $('btnCopyDiag').addEventListener('click', copyDiagnostic);
    $('btnListenExplain').addEventListener('click', async () => {
      try {
        const r = await API.call('speakResponse');
        UI.toast(r.message || 'Reproduciendo…', 'INFO');
      } catch (e) {
        UI.toast('No hay respuesta para reproducir.', 'WARNING');
      }
    });
    $('btnClearFeed').addEventListener('click', () => { S.events = []; refreshFeed(); });
    $('feedAgent').addEventListener('change', e => { S.filters.agent = e.target.value; refreshFeed(); });
    $('feedAuto').addEventListener('change', refreshFeed);
    $('feedList').addEventListener('click', e => {
      const li = e.target.closest('li[data-text]'); if (!li) return;
      navigator.clipboard.writeText(li.getAttribute('data-text')).then(() => UI.toast('Evento copiado.', 'INFO'), () => { /* sin permiso */ });
    });
    $('voiceForm').addEventListener('submit', e => {
      e.preventDefault();
      const inp = $('voiceInput'); const t = inp.value; inp.value = '';
      sendCommand(t);
    });
    // Manejar comandos de agentes desde la cuadrícula
    $('agentGrid').addEventListener('click', e => {
      const cmdLink = e.target.closest('.cmd-ver'); if (!cmdLink) return;
      const agentCard = e.target.closest('.agent'); if (!agentCard) return;
      const agentState = agentCard.querySelector('.badge')?.textContent || '';
      if (agentState === 'Ocioso') return;
      if (confirm('Ejecutar comando por voz al agente?')) {
        const t = 'cuánto avanza el proyecto';
        sendCommand(t);
      }
    });
    $('configForm').addEventListener('submit', saveConfig);
    document.addEventListener('keydown', e => {
      const tag = (e.target.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === 'm' || e.key === 'M') toggleMute();
    });

    loadConfig();
    loop(pollHealth, 5000);
    loop(pollStatus, 1000);
    loop(pollAgents, 2000);
    loop(pollEvents, 1500);
    loop(pollVoiceFeed, 1500);
  }

  document.addEventListener('DOMContentLoaded', init);
})();
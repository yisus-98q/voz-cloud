/* ===== Voz Cloud — capa de API =====
 * Cada ruta intenta primero el backend real (OpenCode lo conecta).
 * Si no responde, usa el motor DEMO interno para que la interfaz funcione sola.
 * Estado por ruta: "wait" (sin probar) · "live" (backend responde) · "demo" (simulada)
 * Backend por defecto: mismo origen. Cambiar con ?api=http://127.0.0.1:8000
 */
(function (global) {
  'use strict';

  let BASE = '';
  try {
    BASE = (new URLSearchParams(location.search).get('api') || localStorage.getItem('vc_api') || '').replace(/\/$/, '');
  } catch (e) { /* storage bloqueado */ }

  const TIMEOUT_MS = 2500;

  // key -> contrato de la ruta (ver CONTRATO-API.md)
  const ROUTES = {
    health:    { method: 'GET',  path: '/health',                demo: 'health' },
    report:    { method: 'GET',  path: '/health/report',         demo: 'report' },
    status:    { method: 'GET',  path: '/status',                demo: 'status' },
    agents:    { method: 'GET',  path: '/agents',                demo: 'agents' },
    events:    { method: 'GET',  path: '/events',                demo: 'events' },
    mute:      { method: 'POST', path: '/mute/{value}',          demo: 'mute' },
    configGet: { method: 'GET',  path: '/config',                demo: 'configGet' },
    configSet: { method: 'PUT',  path: '/config',                demo: 'configSet' },
    voice:     { method: 'POST', path: '/voice/command',         demo: 'voice' },
    voiceFeed: { method: 'GET',  path: '/voice/feed',            demo: 'voiceFeed' },
    confirm:   { method: 'POST', path: '/voice/confirm',         demo: 'confirm' },
    mic:       { method: 'POST', path: '/stt/{value}',           demo: 'mic' },
    speak:     { method: 'POST', path: '/speak',                 demo: 'speak' },
    speakResponse: { method: 'POST', path: '/stt/speak-response', demo: 'speakResponse' }
  };

  const routeState = {};
  const listeners = [];
  Object.keys(ROUTES).forEach(k => { routeState[k] = 'wait'; });

  function setState(key, st) {
    if (routeState[key] === st) return;
    routeState[key] = st;
    listeners.forEach(fn => { try { fn(routeState); } catch (e) { /* ignorar */ } });
  }

  /* ---------------------------------------------------------------
   * MOTOR DEMO (datos simulados, solo vive en el navegador)
   * ------------------------------------------------------------- */
  const Demo = (function () {
    const LV_RANK = { INFO: 0, SUCCESS: 1, WARNING: 2, ERROR: 3, ACTION: 4 };
    const cfg = { levels: ['SUCCESS', 'WARNING', 'ERROR', 'ACTION'], quiet_start: '', quiet_end: '', dedupe_s: 30, queue_max: 8, queue_age_s: 60 };
    const agents = [
      { id: 'a1', name: 'Agente 1', role: 'Pruebas',      state: 'working', last: 'Ejecutando pruebas…',   ts: Date.now() },
      { id: 'a2', name: 'Agente 2', role: 'Correcciones', state: 'working', last: 'Editando auth.py',      ts: Date.now() },
      { id: 'a3', name: 'Agente 3', role: 'Funciones',    state: 'working', last: 'Compilando reportes',   ts: Date.now() },
      { id: 'a4', name: 'Agente 4', role: 'Seguridad',    state: 'idle',    last: 'Esperando tarea',       ts: Date.now() }
    ];
    const events = [];
    const voiceItems = [];
    const seen = new Map();
    const pending = new Map();
    let queue = [], dropped = 0, muted = false, current = null, mic = false;
    let evId = 0, vId = 0, cId = 0;

    const TEMPLATES = [
      ['a1', 'SUCCESS', '12 pruebas pasaron', 'done'],
      ['a1', 'ERROR',   '3 pruebas fallidas', 'failed'],
      ['a1', 'INFO',    'Ejecutando suite de pruebas', 'working'],
      ['a2', 'SUCCESS', 'Corrección aplicada', 'done'],
      ['a2', 'INFO',    'Editando auth.py', 'working'],
      ['a3', 'INFO',    'Compilando función de reportes', 'working'],
      ['a3', 'ACTION',  'Necesita aprobación para instalar un paquete', 'waiting'],
      ['a3', 'SUCCESS', 'Función de reportes terminada', 'done'],
      ['a4', 'WARNING', '2 advertencias de seguridad', 'done'],
      ['a4', 'INFO',    'Analizando dependencias', 'working']
    ];

    const agentById = id => agents.find(a => a.id === id);
    const agentByNum = n => agents[Number(n) - 1];
    const norm = s => String(s).toLowerCase().replace(/\d+/g, '#');
    const pad = n => String(n).padStart(2, '0');

    function inQuiet() {
      if (!cfg.quiet_start || !cfg.quiet_end) return false;
      const d = new Date(), now = pad(d.getHours()) + ':' + pad(d.getMinutes());
      const a = cfg.quiet_start, b = cfg.quiet_end;
      return a <= b ? (now >= a && now < b) : (now >= a || now < b);
    }

    function speakText(ev) {
      const pre = { ACTION: 'Atención', ERROR: 'Error', WARNING: 'Advertencia', SUCCESS: 'Listo', INFO: '' }[ev.level];
      const ag = agentById(ev.agentId);
      return ((pre ? pre + ': ' : '') + (ag ? ag.name : ev.agent) + '. ' + ev.text).trim();
    }

    function enqueue(ev) {
      queue.push(ev);
      while (queue.length > cfg.queue_max) {
        let vi = 0;
        queue.forEach((q, i) => {
          const v = queue[vi];
          if (LV_RANK[q.level] < LV_RANK[v.level] || (LV_RANK[q.level] === LV_RANK[v.level] && q.ts < v.ts)) vi = i;
        });
        queue.splice(vi, 1); dropped++;
      }
    }

    function pushEvent(agentId, level, text, state) {
      const ag = agentById(agentId);
      const ev = { id: ++evId, ts: Date.now(), agent: ag.name, agentId, level, text };
      events.push(ev); if (events.length > 500) events.shift();
      ag.last = text; ag.ts = ev.ts; if (state) ag.state = state;
      // dedupe + niveles + silencio
      const k = agentId + '|' + norm(text), now = Date.now();
      const prev = seen.get(k);
      if (prev && now - prev < cfg.dedupe_s * 1000) return ev;
      seen.set(k, now);
      if (!cfg.levels.includes(level)) return ev;
      if (inQuiet() && level !== 'ACTION') return ev;
      enqueue(ev);
      return ev;
    }

    // Simula eventos de los agentes
    setInterval(() => {
      const t = TEMPLATES[Math.floor(Math.random() * TEMPLATES.length)];
      pushEvent(t[0], t[1], t[2], t[3]);
    }, 3500);

    // Simula a Piper hablando
    setInterval(() => {
      const now = Date.now();
      queue = queue.filter(e => e.level === 'ACTION' || now - e.ts < cfg.queue_age_s * 1000);
      if (current || muted || !queue.length) return;
      let bi = 0;
      queue.forEach((q, i) => {
        const b = queue[bi];
        if (LV_RANK[q.level] > LV_RANK[b.level] || (LV_RANK[q.level] === LV_RANK[b.level] && q.ts < b.ts)) bi = i;
      });
      const ev = queue.splice(bi, 1)[0];
      current = { text: speakText(ev), level: ev.level };
      setTimeout(() => { current = null; }, 2600);
    }, 400);

    // Inicio con algunos eventos para que no se vea vacío
    pushEvent('a1', 'INFO', 'Ejecutando suite de pruebas', 'working');
    pushEvent('a2', 'INFO', 'Editando auth.py', 'working');
    pushEvent('a4', 'INFO', 'Analizando dependencias', 'working');

    function summary() {
      const f = agents.filter(a => a.state === 'failed'), w = agents.filter(a => a.state === 'waiting'),
            d = agents.filter(a => a.state === 'done'), k = agents.filter(a => a.state === 'working');
      const parts = [];
      if (w.length) parts.push('Atención: ' + w.map(a => a.name).join(' y ') + ' necesita tu intervención');
      if (f.length) parts.push(f.map(a => a.name).join(' y ') + ' falló');
      if (d.length) parts.push(d.map(a => a.name).join(' y ') + ' terminó');
      if (k.length) parts.push(k.length + ' agente(s) siguen trabajando');
      return (parts.join('. ') || 'Todo en calma') + '.';
    }

    function addVoice(heard, reply, confirm) {
      const item = { id: ++vId, ts: Date.now(), heard, reply, confirm: confirm || null };
      voiceItems.push(item); if (voiceItems.length > 100) voiceItems.shift();
      return item;
    }

    function askConfirm(text, run) {
      const id = 'c' + (++cId);
      pending.set(id, run);
      setTimeout(() => pending.delete(id), 9000);
      return { id, text, timeout_s: 8 };
    }

    return {
      health() {
        const j = () => Math.round(5 + Math.random() * 40);
        return { ts: Date.now(), checks: [
          { name: 'OpenCode',   status: 'ok', detail: 'Proceso activo (demo)',               latency_ms: j() },
          { name: 'Piper (TTS)', status: 'ok', detail: 'Voz es_ES cargada (demo)',            latency_ms: j() * 10 },
          { name: 'STT',        status: 'ok', detail: mic ? 'Escuchando (demo)' : 'Micrófono apagado', latency_ms: j() },
          { name: 'Supervisor', status: 'ok', detail: 'Cola ' + queue.length + '/' + cfg.queue_max, latency_ms: j() },
          { name: 'Servidor',   status: 'ok', detail: 'Datos de demostración',               latency_ms: j() }
        ] };
      },
      report() {
        const h = this.health();
        const lines = ['VOZ CLOUD — DIAGNÓSTICO (DEMO)', 'Fecha: ' + new Date().toLocaleString('es-PE'), ''];
        h.checks.forEach(c => lines.push('[' + c.status.toUpperCase() + '] ' + c.name + ' — ' + c.detail + ' (' + c.latency_ms + ' ms)'));
        lines.push('', 'Últimos eventos:');
        events.slice(-20).forEach(e => lines.push(new Date(e.ts).toLocaleTimeString('es-PE') + ' [' + e.level + '] ' + e.agent + ': ' + e.text));
        return lines.join('\n');
      },
      status() { return { queue: queue.length, dropped, muted, max: cfg.queue_max, current, mic }; },
      agents() { return { agents: agents.map(a => Object.assign({}, a)) }; },
      events(o) {
        const since = Number(o && o.query && o.query.since) || 0;
        return { events: events.filter(e => e.id > since) };
      },
      mute(o) { muted = String(o.value) === 'true'; return { muted }; },
      configGet() { return Object.assign({}, cfg); },
      configSet(o) { Object.assign(cfg, o.body || {}); return Object.assign({}, cfg); },
      mic(o) { mic = o.value === 'on'; return { listening: mic }; },
      speak(o) { return { ok: true, message: 'Reproduciendo… (demo)' }; },
      speakResponse(o) { return { ok: true, message: 'Reproduciendo… (demo)' }; },
      voiceFeed(o) {
        const since = Number(o && o.query && o.query.since) || 0;
        return { items: voiceItems.filter(v => v.id > since) };
      },
      voice(o) {
        const raw = String((o.body && o.body.text) || '').trim();
        const t = raw.toLowerCase().replace(/^voz\s*cloud[\s,:.-]*/i, '').replace(/[¿?¡!]/g, '').trim();
        let m;
        if (!t) return addVoice(raw, 'Te escucho. Di un comando después de «Voz Cloud».');
        if (/silencio|callate|cállate/.test(t)) { muted = true; return addVoice(raw, 'Voz silenciada.'); }
        if (/habla otra vez|activa la voz|quita el silencio/.test(t)) { muted = false; return addVoice(raw, 'Voz activada.'); }
        if (/como va|cómo va|proyecto|resumen/.test(t)) return addVoice(raw, summary());
        if (/repite/.test(t)) {
          const last = events[events.length - 1];
          if (!last) return addVoice(raw, 'No hay nada que repetir.');
          enqueue(last); return addVoice(raw, 'Repito: ' + last.text);
        }
        if ((m = t.match(/que pas[oó] con (?:el )?agente (\d)/) || t.match(/qué pas[oó] con (?:el )?agente (\d)/))) {
          const ag = agentByNum(m[1]);
          return addVoice(raw, ag ? ag.name + ' (' + ag.role + '): ' + ag.last : 'No existe ese agente.');
        }
        if (/reintentar pruebas/.test(t)) {
          const c = askConfirm('¿Confirmas reintentar las pruebas del Agente 1?', () => { pushEvent('a1', 'INFO', 'Reintentando pruebas', 'working'); return 'Reintentando pruebas del Agente 1.'; });
          return addVoice(raw, 'Necesito tu confirmación.', c);
        }
        if ((m = t.match(/pausar agente (\d)/))) {
          const ag = agentByNum(m[1]);
          if (!ag) return addVoice(raw, 'No existe ese agente.');
          const c = askConfirm('¿Confirmas pausar al ' + ag.name + '?', () => { ag.state = 'idle'; ag.last = 'Pausado por voz'; return ag.name + ' en pausa.'; });
          return addVoice(raw, 'Necesito tu confirmación.', c);
        }
        if ((m = t.match(/abrir terminal (\d)/))) {
          const ag = agentByNum(m[1]);
          if (!ag) return addVoice(raw, 'No existe ese agente.');
          const c = askConfirm('¿Confirmas abrir la terminal del ' + ag.name + '?', () => 'Abriendo terminal del ' + ag.name + ' (demo).');
          return addVoice(raw, 'Necesito tu confirmación.', c);
        }
        return addVoice(raw, 'No tengo esa acción autorizada.');
      },
      confirm(o) {
        const b = o.body || {}, run = pending.get(b.id);
        pending.delete(b.id);
        if (!run) return addVoice('(confirmación)', 'La confirmación expiró.');
        return addVoice('(confirmación)', b.accept ? run() : 'Acción cancelada.');
      }
    };
  })();

  /* ---------------------------------------------------------------
   * Llamada genérica: backend real -> si falla, DEMO
   * ------------------------------------------------------------- */
  async function call(key, opts) {
    opts = opts || {};
    const r = ROUTES[key];
    if (!r) throw new Error('Ruta desconocida: ' + key);
    let path = r.path.replace('{value}', encodeURIComponent(opts.value === undefined ? '' : opts.value));
    if (opts.query) path += '?' + new URLSearchParams(opts.query).toString();

    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    try {
      const init = { method: r.method, signal: ctrl.signal };
      if (opts.body !== undefined) {
        init.headers = { 'Content-Type': 'application/json' };
        init.body = JSON.stringify(opts.body);
      }
      const res = await fetch(BASE + path, init);
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const ct = res.headers.get('content-type') || '';
      const data = ct.indexOf('json') >= 0 ? await res.json() : await res.text();
      setState(key, 'live');
      return data;
    } catch (e) {
      setState(key, 'demo');
      return Demo[r.demo](opts);
    } finally {
      clearTimeout(timer);
    }
  }

  global.API = {
    call,
    routes: ROUTES,
    base: () => BASE,
    states: () => Object.assign({}, routeState),
    onState: fn => { listeners.push(fn); }
  };
})(window);

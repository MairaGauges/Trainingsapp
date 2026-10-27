/* Laufzeit-Adapter: stellt dieselbe kleine Schnittstelle bereit wie die Artifact-Umgebung
 * (window.claude.use('db') und 'downloads'), damit das Dashboard unverändert läuft.
 *
 * Speicher: Supabase (wenn config.js URL und Schlüssel setzt, z. B. auf Vercel) oder der eigene
 * Server (/api/db). Schreibzugriffe werden sofort lokal übernommen und in einer Warteschlange
 * (localStorage) gesendet. Ohne Netz geht nichts verloren, sie werden gesendet, sobald der
 * Speicher wieder erreichbar ist. Bei Konflikten gewinnt die letzte Änderung. */
(function () {
  'use strict';
  const K_CACHE = 'ef27.app.cache', K_OUT = 'ef27.app.outbox', K_SESSION = 'ef27.app.session';
  const clone = x => JSON.parse(JSON.stringify(x));
  const lsGet = (k, d) => { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } };
  const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* voll oder gesperrt */ } };
  const lsDel = k => { try { localStorage.removeItem(k); } catch (e) { /* gesperrt */ } };
  const httpError = (status, msg) => { const e = new Error(msg || ('HTTP ' + status)); e.status = status; return e; };

  const CFG = window.EF27_CONFIG || {};
  const SB = CFG.supabaseUrl && CFG.supabaseKey ? { url: CFG.supabaseUrl.replace(/\/+$/, ''), key: CFG.supabaseKey } : null;

  let data = lsGet(K_CACHE, {});          // { collection: { id: doc } }
  let outbox = lsGet(K_OUT, []);          // [{ op: 'set'|'delete', col, id, doc }]
  let version = null, loaded = false, flushing = false;
  const subs = [];                        // { col, id|null, cb }
  const readyCbs = [];

  const col = c => data[c] || (data[c] = {});
  const persist = () => { lsSet(K_CACHE, data); lsSet(K_OUT, outbox); };

  function snapOf(s) {
    if (s.id === null) {
      const c = col(s.col);
      return { docs: Object.keys(c).map(id => ({ id, data: () => clone(c[id]) })) };
    }
    const d = col(s.col)[s.id];
    return { exists: d !== undefined, id: s.id, data: () => (d === undefined ? undefined : clone(d)) };
  }
  function notify(only) {
    if (!loaded) return;
    subs.forEach(s => { if (!only || only === s.col) { try { s.cb(snapOf(s)); } catch (e) { /* Callback-Fehler gehören der Seite */ } } });
  }
  function applyLocal(op) {
    if (op.op === 'set') col(op.col)[op.id] = clone(op.doc);
    else delete col(op.col)[op.id];
  }

  /* ---------- Backend 1: eigener Server (server/server.py) ---------- */
  async function api(path, opt) {
    const r = await fetch('api/' + path, Object.assign({ credentials: 'same-origin', cache: 'no-store' }, opt));
    if (!r.ok) throw httpError(r.status);
    return r.status === 204 ? null : r.json();
  }
  const serverBackend = {
    async load() { const j = await api('db'); return { version: j.version, data: j.data || {} }; },
    async version() { return (await api('db/version')).version; },
    async put(c, id, doc) { await api('db/' + encodeURIComponent(c) + '/' + encodeURIComponent(id), { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(doc) }); },
    async del(c, id) { await api('db/' + encodeURIComponent(c) + '/' + encodeURIComponent(id), { method: 'DELETE' }); }
  };

  /* ---------- Backend 2: Supabase (Tabelle docs, siehe supabase/schema.sql) ---------- */
  let session = SB ? lsGet(K_SESSION, null) : null;   // { access_token, refresh_token, expires_at, email }
  let refreshing = null;

  async function authCall(path, body, token) {
    const r = await fetch(SB.url + '/auth/v1/' + path, {
      method: 'POST', cache: 'no-store',
      headers: Object.assign({ apikey: SB.key, 'Content-Type': 'application/json' }, token ? { Authorization: 'Bearer ' + token } : {}),
      body: JSON.stringify(body || {})
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw httpError(r.status, j.error_description || j.msg || j.message || ('HTTP ' + r.status));
    return j;
  }
  function keepSession(j) {
    session = { access_token: j.access_token, refresh_token: j.refresh_token, expires_at: j.expires_at || (Math.floor(Date.now() / 1000) + (j.expires_in || 3600)), email: (j.user && j.user.email) || (session && session.email) || '' };
    lsSet(K_SESSION, session);
  }
  function dropSession() { session = null; lsDel(K_SESSION); }
  async function token() {
    if (!session) throw httpError(401, 'nicht angemeldet');
    if (session.expires_at - 60 > Date.now() / 1000) return session.access_token;
    if (!refreshing) {
      refreshing = authCall('token?grant_type=refresh_token', { refresh_token: session.refresh_token })
        .then(keepSession)
        .catch(e => { if (e.status >= 400 && e.status < 500) { dropSession(); showLogin('Bitte erneut anmelden.'); } throw e; })
        .finally(() => { refreshing = null; });
    }
    await refreshing;
    return session.access_token;
  }
  async function rest(path, opt) {
    opt = opt || {};
    const r = await fetch(SB.url + '/rest/v1/' + path, {
      method: opt.method || 'GET', cache: 'no-store', body: opt.body,
      headers: Object.assign({ apikey: SB.key, Authorization: 'Bearer ' + await token(), 'Content-Type': 'application/json' }, opt.headers || {})
    });
    if (r.status === 401) { dropSession(); showLogin('Bitte erneut anmelden.'); }
    if (!r.ok) throw httpError(r.status);
    const t = await r.text();
    return t ? JSON.parse(t) : null;
  }
  const eq = v => 'eq.' + encodeURIComponent(v);
  const supabaseBackend = {
    async load() {
      const v = await this.version(), out = {}, page = 1000;
      for (let off = 0; ; off += page) {
        const rows = await rest('docs?select=col,id,doc&order=col,id&limit=' + page + '&offset=' + off);
        rows.forEach(r => { (out[r.col] || (out[r.col] = {}))[r.id] = r.doc; });
        if (rows.length < page) break;
      }
      return { version: v, data: out };
    },
    async version() { return rest('rpc/docs_version', { method: 'POST', body: '{}' }); },
    async put(c, id, doc) { await rest('docs?on_conflict=user_id,col,id', { method: 'POST', headers: { Prefer: 'resolution=merge-duplicates,return=minimal' }, body: JSON.stringify({ col: c, id, doc }) }); },
    async del(c, id) { await rest('docs?col=' + eq(c) + '&id=' + eq(id), { method: 'DELETE', headers: { Prefer: 'return=minimal' } }); }
  };

  const backend = SB ? supabaseBackend : serverBackend;

  /* ---------- Anmeldung (nur Supabase) ---------- */
  let loginEl = null, loginWaiters = [];
  function showLogin(msg) {
    if (!SB) return;
    const build = () => {
      if (!loginEl) {
        loginEl = document.createElement('div');
        loginEl.setAttribute('role', 'dialog');
        loginEl.setAttribute('aria-modal', 'true');
        loginEl.setAttribute('aria-labelledby', 'ef27-login-h');
        loginEl.style.cssText = 'position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;background:#0e161c;color:#e8eef2;font:15px system-ui,sans-serif';
        loginEl.innerHTML = '<form style="width:100%;max-width:340px;display:grid;gap:12px">' +
          '<h1 id="ef27-login-h" style="margin:0 0 4px;font-size:22px">Eschborn-Frankfurt 2027</h1>' +
          '<p data-msg style="margin:0;color:#9fb3c1;min-height:1.3em" aria-live="polite"></p>' +
          '<label style="display:grid;gap:4px">E-Mail<input name="email" type="email" autocomplete="username" required style="font:inherit;padding:10px;border-radius:8px;border:1px solid #3a4b57;background:#16222b;color:inherit"></label>' +
          '<label style="display:grid;gap:4px">Passwort<input name="password" type="password" autocomplete="current-password" required style="font:inherit;padding:10px;border-radius:8px;border:1px solid #3a4b57;background:#16222b;color:inherit"></label>' +
          '<button style="font:inherit;font-weight:600;padding:11px;border:0;border-radius:8px;background:#e9b949;color:#0e161c;cursor:pointer">Anmelden</button></form>';
        loginEl.querySelector('form').addEventListener('submit', async ev => {
          ev.preventDefault();
          const f = ev.target, btn = f.querySelector('button'), m = loginEl.querySelector('[data-msg]');
          btn.disabled = true; m.textContent = 'Anmelden …';
          try {
            keepSession(await authCall('token?grant_type=password', { email: f.email.value.trim(), password: f.password.value }));
            f.password.value = '';
            loginEl.remove(); loginEl = null;
            const w = loginWaiters; loginWaiters = []; w.forEach(r => r());
            if (!w.length) sync(true);         // erneute Anmeldung im laufenden Betrieb; beim Start lädt ready
          } catch (e) {
            m.textContent = e.status === 400 ? 'E-Mail oder Passwort falsch.' : ('Anmeldung fehlgeschlagen: ' + e.message);
            btn.disabled = false;
          }
        });
      }
      loginEl.querySelector('[data-msg]').textContent = msg || '';
      if (!loginEl.isConnected) { document.body.appendChild(loginEl); loginEl.querySelector('input').focus(); }
    };
    if (document.body) build(); else document.addEventListener('DOMContentLoaded', build, { once: true });
  }
  const signedIn = () => (!SB || session) ? Promise.resolve() : new Promise(r => { loginWaiters.push(r); showLogin(); });

  /* ---------- Abgleich ---------- */
  async function flush() {
    if (flushing || !outbox.length) return;
    flushing = true;
    try {
      while (outbox.length) {
        const op = outbox[0];
        try {
          if (op.op === 'set') await backend.put(op.col, op.id, op.doc);
          else await backend.del(op.col, op.id);
        } catch (e) {
          if (e.status >= 400 && e.status < 500 && e.status !== 408 && e.status !== 401) { outbox.shift(); persist(); continue; } // unbrauchbare Änderung verwerfen
          throw e;
        }
        outbox.shift(); persist();
      }
    } finally { flushing = false; }
  }

  async function pull() {
    const j = await backend.load();
    version = j.version;
    data = j.data;
    outbox.forEach(applyLocal);          // noch nicht gesendete Änderungen bleiben sichtbar
    persist();
  }

  async function sync(first) {
    if (SB && !session) return;
    try {
      await flush();
      if (!first) {
        const v = await backend.version();
        if (v === version && !outbox.length) return;
      }
      await pull();
      notify();
    } catch (e) { /* offline: Cache und Warteschlange bleiben */ }
  }

  const ready = (async () => {
    // Ohne Anmeldung keine Daten zeigen; mit Anmeldung, aber offline, reicht der Cache
    if (SB && !session) { await signedIn(); }
    await Promise.race([sync(true), new Promise(r => setTimeout(r, 4000))]);
    loaded = true;
    notify();
    readyCbs.forEach(f => f());
  })();

  setInterval(() => { if (!document.hidden) sync(false); }, SB ? 15000 : 8000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) sync(false); });
  window.addEventListener('online', () => sync(false));

  function write(op) {
    applyLocal(op);
    outbox.push(op);
    // mehrere Änderungen am selben Dokument zusammenfassen (nur die letzte zählt)
    outbox = outbox.filter((o, i) => !outbox.some((p, j) => j > i && p.col === o.col && p.id === o.id));
    persist();
    notify(op.col);
    flush().catch(() => {});
    return Promise.resolve();
  }

  const mkDoc = (c, id) => ({
    set: d => write({ op: 'set', col: c, id, doc: clone(d) }),
    delete: () => write({ op: 'delete', col: c, id }),
    onSnapshot(cb) { const s = { col: c, id, cb }; subs.push(s); if (loaded) cb(snapOf(s)); else readyCbs.push(() => cb(snapOf(s))); return () => { const i = subs.indexOf(s); if (i >= 0) subs.splice(i, 1); }; }
  });
  const dbApi = {
    collection: c => ({
      doc: id => mkDoc(c, id),
      onSnapshot(cb) { const s = { col: c, id: null, cb }; subs.push(s); if (loaded) cb(snapOf(s)); else readyCbs.push(() => cb(snapOf(s))); return () => { const i = subs.indexOf(s); if (i >= 0) subs.splice(i, 1); }; }
    }),
    doc(path) { const p = path.split('/'); return mkDoc(p[0], p[1]); }
  };

  const downloadsApi = {
    async save({ filename, data: blob }) {
      const url = URL.createObjectURL(blob), a = document.createElement('a');
      a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    }
  };

  window.claude = {
    use: async name => (name === 'db' ? dbApi : name === 'downloads' ? downloadsApi : null)
  };

  // Für eigene API-Aufrufe der Seite (Garmin): hängt bei Supabase das Anmelde-Token an
  window.apiFetch = async (url, opt) => {
    opt = Object.assign({ credentials: 'same-origin' }, opt);
    if (SB) opt.headers = Object.assign({}, opt.headers, { Authorization: 'Bearer ' + await token() });
    return fetch(url, opt);
  };

  // Abmelden: Sitzung, Cache und Warteschlange auf diesem Gerät löschen
  window.ef27Logout = async () => {
    if (!SB) return;
    const t = session && session.access_token;
    dropSession(); lsDel(K_CACHE); lsDel(K_OUT);
    if (t) authCall('logout', {}, t).catch(() => {});
    location.reload();
  };

  // Garmin-Abruf nur anzeigen, wenn der Server einen Schlüssel kennt
  window.GARMIN_SYNC = false;
  ready.then(() => window.apiFetch('api/garmin/status', { cache: 'no-store' })
    .then(r => r.ok ? r.json() : {})
    .then(j => {
      window.GARMIN_SYNC = !!j.configured;
      if (window.GARMIN_SYNC && typeof window.render === 'function') window.render();
    }).catch(() => {}));

  if ('serviceWorker' in navigator && window.isSecureContext) {
    window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => {}));
  }
})();

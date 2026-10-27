/* Laufzeit-Adapter: stellt dieselbe kleine Schnittstelle bereit wie die Artifact-Umgebung
 * (window.claude.use('db') und 'downloads'), damit das Dashboard unverändert läuft.
 *
 * Speicher: eigener Server (/api/db). Schreibzugriffe werden sofort lokal übernommen und in einer
 * Warteschlange (localStorage) an den Server gesendet. Ohne Netz geht nichts verloren, sie werden
 * gesendet, sobald der Server wieder erreichbar ist. Bei Konflikten gewinnt die letzte Änderung. */
(function () {
  'use strict';
  const K_CACHE = 'ef27.app.cache', K_OUT = 'ef27.app.outbox';
  const clone = x => JSON.parse(JSON.stringify(x));
  const lsGet = (k, d) => { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } };
  const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* voll oder gesperrt */ } };

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

  async function api(path, opt) {
    const r = await fetch('api/' + path, Object.assign({ credentials: 'same-origin', cache: 'no-store' }, opt));
    if (!r.ok) { const e = new Error('HTTP ' + r.status); e.status = r.status; throw e; }
    return r.status === 204 ? null : r.json();
  }

  async function flush() {
    if (flushing || !outbox.length) return;
    flushing = true;
    try {
      while (outbox.length) {
        const op = outbox[0], url = 'db/' + encodeURIComponent(op.col) + '/' + encodeURIComponent(op.id);
        try {
          if (op.op === 'set') await api(url, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(op.doc) });
          else await api(url, { method: 'DELETE' });
        } catch (e) {
          if (e.status >= 400 && e.status < 500 && e.status !== 408 && e.status !== 401) { outbox.shift(); persist(); continue; } // unbrauchbare Änderung verwerfen
          throw e;
        }
        outbox.shift(); persist();
      }
    } finally { flushing = false; }
  }

  async function pull() {
    const j = await api('db');
    version = j.version;
    data = j.data || {};
    outbox.forEach(applyLocal);          // noch nicht gesendete Änderungen bleiben sichtbar
    persist();
  }

  async function sync(first) {
    try {
      await flush();
      if (!first) {
        const v = await api('db/version');
        if (v.version === version && !outbox.length) return;
      }
      await pull();
      notify();
    } catch (e) { /* offline: Cache und Warteschlange bleiben */ }
  }

  const ready = (async () => {
    await Promise.race([sync(true), new Promise(r => setTimeout(r, 4000))]);
    loaded = true;
    notify();
    readyCbs.forEach(f => f());
  })();

  setInterval(() => { if (!document.hidden) sync(false); }, 8000);
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

  // Garmin-Abruf nur anzeigen, wenn der Server einen Schlüssel kennt
  window.GARMIN_SYNC = false;
  ready.then(() => api('garmin/status').then(j => {
    window.GARMIN_SYNC = !!j.configured;
    if (window.GARMIN_SYNC && typeof window.render === 'function') window.render();
  }).catch(() => {}));

  if ('serviceWorker' in navigator && window.isSecureContext) {
    window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => {}));
  }
})();

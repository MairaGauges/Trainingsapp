#!/usr/bin/env python3
"""Vorhandene Daten nach Supabase übernehmen (nur Standardbibliothek).

Liest eine Datei im Format von data/store.json ({"version": …, "data": {Sammlung: {id: Dokument}}})
oder direkt {Sammlung: {id: Dokument}}, meldet sich mit deinem App-Konto an und schreibt jedes
Dokument in die Tabelle docs. Vorhandene Dokumente mit gleicher ID werden überschrieben.

  SUPABASE_URL=https://xyz.supabase.co SUPABASE_ANON_KEY=… python3 tools/import_supabase.py data/store.json du@example.com
"""
import getpass
import json
import os
import sys
import urllib.error
import urllib.request


def call(url, key, body, token=None, prefer=None):
    h = {"apikey": key, "Content-Type": "application/json", "Authorization": "Bearer " + (token or key)}
    if prefer:
        h["Prefer"] = prefer
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            t = r.read()
            return json.loads(t) if t else None
    except urllib.error.HTTPError as e:
        sys.exit("Fehler HTTP %d: %s" % (e.code, e.read().decode(errors="replace")[:300]))


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_ANON_KEY") or ""
    if not (url and key):
        sys.exit("SUPABASE_URL und SUPABASE_ANON_KEY setzen (Supabase → Project Settings → API).")
    src = json.load(open(sys.argv[1], encoding="utf-8"))
    data = src.get("data", src) if isinstance(src, dict) else {}
    rows = [{"col": c, "id": i, "doc": d} for c, docs in data.items() if isinstance(docs, dict)
            for i, d in docs.items() if isinstance(d, dict)]
    if not rows:
        sys.exit("Keine Dokumente in der Datei gefunden.")
    pw = getpass.getpass("Passwort für %s: " % sys.argv[2])
    tok = call(url + "/auth/v1/token?grant_type=password", key, {"email": sys.argv[2], "password": pw})["access_token"]
    for n in range(0, len(rows), 200):
        call(url + "/rest/v1/docs?on_conflict=user_id,col,id", key, rows[n:n + 200], tok, "resolution=merge-duplicates,return=minimal")
    by = {}
    for r in rows:
        by[r["col"]] = by.get(r["col"], 0) + 1
    print("Übernommen:", ", ".join("%s %d" % kv for kv in sorted(by.items())))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Eigener Server für das Trainings-Dashboard (nur Python-Standardbibliothek).

- liefert die App aus (web/)
- speichert Plan-Logs, Kraftplan und Aktivitäten in data/store.json
- fragt Garmins Personal API ab; der API-Schlüssel bleibt auf dem Server und geht nie an den Browser

Konfiguration über Umgebungsvariablen (siehe .env.example):
  HOST, PORT, APP_PASSWORD, DATA_DIR, GARMIN_PERSONAL_API_KEY, GARMIN_BASE
"""
import base64
import hmac
import json
import os
import re
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from garmin_client import Garmin, GarminError  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WEB = os.path.join(ROOT, "web")
DATA_DIR = os.path.abspath(os.environ.get("DATA_DIR", os.path.join(ROOT, "data")))
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8080"))
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
MAX_BODY = 2 * 1024 * 1024
NAME_RE = re.compile(r"^[A-Za-z0-9_\-.:@+]{1,200}$")

MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".png": "image/png",
        ".webmanifest": "application/manifest+json", ".json": "application/json", ".css": "text/css; charset=utf-8"}


# ----------------------------------------------------------------- Speicher
class Store:
    """Dokumente je Sammlung in einer JSON-Datei. Jede Änderung erhöht die Version."""

    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.state = {"version": 1, "data": {}}
        try:
            with open(path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict) and isinstance(loaded.get("data"), dict):
                self.state = {"version": int(loaded.get("version", 1)), "data": loaded["data"]}
        except FileNotFoundError:
            pass

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.state, fh, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, self.path)

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.state))

    def version(self):
        with self.lock:
            return self.state["version"]

    def put(self, col, doc_id, doc):
        with self.lock:
            self.state["data"].setdefault(col, {})[doc_id] = doc
            self.state["version"] += 1
            self._save()

    def delete(self, col, doc_id):
        with self.lock:
            if doc_id in self.state["data"].get(col, {}):
                del self.state["data"][col][doc_id]
                self.state["version"] += 1
                self._save()


# ----------------------------------------------------------------- HTTP
store = Store(os.path.join(DATA_DIR, "store.json"))
garmin = Garmin(os.path.join(DATA_DIR, "garmin_key"))


class Handler(BaseHTTPRequestHandler):
    server_version = "ef27"
    protocol_version = "HTTP/1.0"

    def log_message(self, fmt, *args):  # keine Query-Strings, keine Header ins Log
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), (fmt % args).split("?")[0]))

    # --- Hilfen
    def _send(self, code, body=b"", ctype="application/json", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if ctype == "application/json" else "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _authorized(self):
        if not APP_PASSWORD:
            return True
        h = self.headers.get("Authorization", "")
        if h.startswith("Basic "):
            try:
                pw = base64.b64decode(h[6:]).decode("utf-8").split(":", 1)[-1]
                return hmac.compare_digest(pw.encode(), APP_PASSWORD.encode())
            except Exception:
                return False
        return False

    def _guard(self):
        if self._authorized():
            return True
        self._send(401, b"Anmeldung erforderlich", "text/plain; charset=utf-8", {"WWW-Authenticate": 'Basic realm="EF2027", charset="UTF-8"'})
        return False

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            return None
        return self.rfile.read(n)

    # --- Routen
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self._guard():
            return
        path = urllib.parse.urlsplit(self.path)
        p, q = path.path, urllib.parse.parse_qs(path.query)
        if p == "/api/db":
            return self._json(200, store.snapshot())
        if p == "/api/db/version":
            return self._json(200, {"version": store.version()})
        m = re.fullmatch(r"/api/db/([^/]+)/([^/]+)", p)
        if m:
            c, i = (urllib.parse.unquote(x) for x in m.groups())
            d = store.snapshot()["data"].get(c, {}).get(i)
            return self._json(200, d) if d is not None else self._json(404, {"error": "nicht gefunden"})
        if p == "/api/garmin/status":
            return self._json(200, {"configured": garmin.configured()})
        if p == "/api/garmin/diag":
            return self._json(200, garmin.diag())
        if p == "/api/garmin/activities":
            try:
                days = max(1, min(int((q.get("days") or ["14"])[0]), 90))
                return self._json(200, {"activities": garmin.activities(days)})
            except (GarminError, ValueError) as e:
                return self._json(502, {"error": str(e)})
        m = re.fullmatch(r"/api/garmin/file/([0-9A-Za-z_\-]{1,40})", p)
        if m:
            try:
                return self._send(200, garmin.file(m.group(1)), "application/zip")
            except GarminError as e:
                return self._json(502, {"error": str(e)})
        if p.startswith("/api/"):
            return self._json(404, {"error": "unbekannt"})
        return self._static(p)

    def do_PUT(self):
        if not self._guard():
            return
        m = re.fullmatch(r"/api/db/([^/]+)/([^/]+)", urllib.parse.urlsplit(self.path).path)
        if not m:
            return self._json(404, {"error": "unbekannt"})
        c, i = (urllib.parse.unquote(x) for x in m.groups())
        if not (NAME_RE.match(c) and NAME_RE.match(i)):
            return self._json(400, {"error": "ungültiger Name"})
        raw = self._body()
        if raw is None:
            return self._json(413, {"error": "zu groß"})
        try:
            doc = json.loads(raw)
        except ValueError:
            return self._json(400, {"error": "kein JSON"})
        if not isinstance(doc, dict):
            return self._json(400, {"error": "Objekt erwartet"})
        store.put(c, i, doc)
        return self._json(200, {"version": store.version()})

    def do_DELETE(self):
        if not self._guard():
            return
        m = re.fullmatch(r"/api/db/([^/]+)/([^/]+)", urllib.parse.urlsplit(self.path).path)
        if not m:
            return self._json(404, {"error": "unbekannt"})
        c, i = (urllib.parse.unquote(x) for x in m.groups())
        store.delete(c, i)
        return self._json(200, {"version": store.version()})

    def _static(self, p):
        rel = "index.html" if p in ("/", "") else p.lstrip("/")
        full = os.path.abspath(os.path.join(WEB, rel))
        if not full.startswith(WEB + os.sep) or not os.path.isfile(full):
            if rel == "index.html":
                return self._send(503, "web/index.html fehlt. Erst bauen: make build".encode(), "text/plain; charset=utf-8")
            return self._send(404, b"nicht gefunden", "text/plain; charset=utf-8")
        with open(full, "rb") as fh:
            body = fh.read()
        self._send(200, body, MIME.get(os.path.splitext(full)[1], "application/octet-stream"))


def main():
    loopback = HOST in ("127.0.0.1", "localhost", "::1")
    if not loopback and not APP_PASSWORD:
        sys.exit("Abbruch: HOST=%s ist von außen erreichbar, aber APP_PASSWORD ist leer. Bitte ein Passwort setzen." % HOST)
    os.makedirs(DATA_DIR, exist_ok=True)
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print("Dashboard läuft auf http://%s:%d  (Passwort: %s, Garmin-Schlüssel: %s)" % (
        HOST, PORT, "ja" if APP_PASSWORD else "nein", "ja" if garmin.configured() else "nein"))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

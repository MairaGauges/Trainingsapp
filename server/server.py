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
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WEB = os.path.join(ROOT, "web")
DATA_DIR = os.path.abspath(os.environ.get("DATA_DIR", os.path.join(ROOT, "data")))
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8080"))
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
GARMIN_BASE = os.environ.get("GARMIN_BASE", "https://personal.connectapi.garmin.com").rstrip("/")
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"
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


# ----------------------------------------------------------------- Garmin
class GarminError(Exception):
    pass


class Garmin:
    """Garmin Connect Personal API. Pfade nach Garmins Python-Client (garmin/connect-personal-api-python)."""

    def __init__(self, key_path):
        self.key_path = key_path
        self.token = None
        self.expires = 0.0
        self.lock = threading.Lock()

    def key(self):
        k = os.environ.get("GARMIN_PERSONAL_API_KEY", "").strip()
        if not k:
            try:
                with open(self.key_path, encoding="utf-8") as fh:
                    k = fh.read().strip()
            except OSError:
                k = ""
        return k

    def configured(self):
        return bool(self.key())

    def _request(self, method, path, headers, timeout=30):
        req = urllib.request.Request(GARMIN_BASE + path, method=method, headers=headers, data=b"" if method == "POST" else None)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers.get("Content-Type", "")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise GarminError("Garmin nicht erreichbar: %s" % getattr(e, "reason", e))

    def _fresh_token(self, force=False):
        with self.lock:
            if not force and self.token and time.time() < self.expires - 300:
                return self.token
            k = self.key()
            if not k:
                raise GarminError("Kein Garmin-Schlüssel hinterlegt")
            status, body, _ = self._request("POST", TOKEN_PATH, {"Authorization": "ApiKey " + k, "Accept": "application/json"})
            if status != 200:
                raise GarminError("Schlüssel abgelehnt (HTTP %d). Abgelaufen oder gelöscht?" % status)
            try:
                j = json.loads(body)
            except ValueError:
                raise GarminError("Token-Antwort ist kein JSON")
            tok = j.get("access_token") or j.get("accessToken") or j.get("token")
            if not tok:
                raise GarminError("Token-Antwort ohne access_token (Felder: %s)" % ", ".join(sorted(j)[:8]))
            ttl = j.get("expires_in") or j.get("expiresIn")
            exp = j.get("expires_at") or j.get("expiresAt")
            if isinstance(ttl, (int, float)):
                self.expires = time.time() + float(ttl)
            elif isinstance(exp, (int, float)):
                self.expires = float(exp) / (1000.0 if exp > 1e12 else 1.0)
            else:
                self.expires = time.time() + 23 * 3600
            self.token = tok
            return tok

    def get(self, path):
        for attempt in (0, 1):
            tok = self._fresh_token(force=attempt == 1)
            status, body, ctype = self._request("GET", path, {"Authorization": "Bearer " + tok})
            if status == 401 and attempt == 0:
                continue
            if status != 200:
                raise GarminError("Garmin antwortet mit HTTP %d" % status)
            return body, ctype

    def activities(self, days):
        start = (date.today() - timedelta(days=days)).isoformat()
        end = (date.today() + timedelta(days=1)).isoformat()
        out, offset = [], 0
        while offset < 300:
            q = urllib.parse.urlencode({"start": offset, "limit": 50, "startDate": start, "endDate": end})
            body, _ = self.get("/activitylist-service/activities/search/activities?" + q)
            try:
                j = json.loads(body)
            except ValueError:
                raise GarminError("Aktivitätsliste ist kein JSON")
            items = j if isinstance(j, list) else next((j[k] for k in ("activityList", "activities", "items", "results") if isinstance(j.get(k), list)), [])
            for it in items:
                aid = it.get("activityId", it.get("id"))
                if aid is None:
                    continue
                t = it.get("activityType") or {}
                out.append({"id": str(aid), "name": it.get("activityName") or "",
                            "start": it.get("startTimeLocal") or it.get("startTimeGMT") or "",
                            "type": (t.get("typeKey") if isinstance(t, dict) else str(t)) or ""})
            if len(items) < 50:
                break
            offset += 50
        return out

    def file(self, activity_id):
        body, _ = self.get("/download-service/files/activity/" + urllib.parse.quote(activity_id, safe=""))
        return body

    def diag(self):
        """Nur die Form der Antworten (Feldnamen), nie Werte oder der Schlüssel."""
        info = {"configured": self.configured(), "base": GARMIN_BASE}
        try:
            self._fresh_token()
            info["token"] = "ok"
            body, _ = self.get("/activitylist-service/activities/search/activities?start=0&limit=1")
            j = json.loads(body)
            first = j[0] if isinstance(j, list) and j else j
            info["list_type"] = type(j).__name__
            info["list_keys"] = sorted(first.keys())[:40] if isinstance(first, dict) else None
        except (GarminError, ValueError) as e:
            info["error"] = str(e)
        return info


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

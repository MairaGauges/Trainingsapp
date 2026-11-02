"""Strava als Vercel-Funktion (/api/strava/...): Spinning-Fahrten vom ICG-Rad mit Leistung holen.

Routen: status, auth (Weiterleitung zu Strava), callback (zurück in die App), exchange, activities, streams/<id>.
Zugriff außer auth/callback nur mit Supabase-Anmeldung und nur für ALLOWED_EMAILS. Client-ID und -Secret liegen
in Vercel (STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET); der Refresh-Token in der eigenen Supabase-Zeile.
"""
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))
import strava_client as st  # noqa: E402
from sb_auth import SUPABASE_KEY, SUPABASE_URL, check  # noqa: E402

MAX_BODY = 64 * 1024


def _rest(method, path, auth, body=None):
    h = {"apikey": SUPABASE_KEY, "Authorization": auth, "Content-Type": "application/json"}
    if method == "POST":
        h["Prefer"] = "resolution=merge-duplicates,return=minimal"
    req = urllib.request.Request(SUPABASE_URL + "/rest/v1/" + path, method=method, headers=h,
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            t = r.read()
            return json.loads(t) if t else None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise st.StravaError("Supabase: %s" % getattr(e, "reason", e))


def load_token(auth):
    rows = _rest("GET", "docs?col=eq.strava&id=eq.token&select=doc", auth) or []
    return rows[0]["doc"] if rows else None


def save_token(auth, doc):
    _rest("POST", "docs?on_conflict=user_id,col,id", auth, {"col": "strava", "id": "token", "doc": doc})


def access_token(auth):
    tok = load_token(auth)
    if not tok or not tok.get("refresh_token"):
        raise st.StravaError("Strava ist noch nicht verbunden")
    if tok.get("access_token") and tok.get("expires_at", 0) > time.time() + 120:
        return tok["access_token"]
    j = st.refresh(tok["refresh_token"])
    save_token(auth, {"refresh_token": j.get("refresh_token") or tok["refresh_token"], "access_token": j["access_token"],
                      "expires_at": j.get("expires_at", 0), "athlete": tok.get("athlete")})
    return j["access_token"]


class handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # ohne Query-Strings (dort steht der OAuth-Code)
        sys.stderr.write((fmt % args).split("?")[0] + "\n")

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, url):
        self.send_response(302)
        self.send_header("Location", url)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _route(self):
        url = urllib.parse.urlsplit(self.path)
        q = urllib.parse.parse_qs(url.query)
        return (q.get("p") or [re.sub(r"^/api/strava/?", "", url.path)])[0].strip("/"), q

    def _origin(self):
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or ""
        return "https://" + host.split(",")[0].strip()

    def do_GET(self):
        p, q = self._route()
        if p == "auth":
            if not st.configured():
                return self._json(503, {"error": "STRAVA_CLIENT_ID/SECRET fehlen in Vercel"})
            return self._redirect(st.authorize_url(self._origin() + "/api/strava/callback", secrets.token_urlsafe(8)))
        if p == "callback":
            code = (q.get("code") or [""])[0]
            if not code or "activity:read" not in (q.get("scope") or [""])[0]:
                return self._redirect("/#strava-error")
            return self._redirect("/#strava=" + urllib.parse.quote(code, safe=""))
        auth = self.headers.get("Authorization", "")
        err = check(auth)
        if err:
            return self._json(err[0], {"error": err[1]})
        try:
            if p == "status":
                tok = load_token(auth) if st.configured() else None
                return self._json(200, {"configured": st.configured(), "connected": bool(tok and tok.get("refresh_token"))})
            if p == "activities":
                days = max(1, min(int((q.get("days") or ["120"])[0]), 730))
                return self._json(200, {"activities": st.activities(access_token(auth), days)})
            m = re.fullmatch(r"streams/(\d{1,20})", p)
            if m:
                return self._json(200, st.streams(access_token(auth), m.group(1)))
        except (st.StravaError, ValueError) as e:
            return self._json(502, {"error": str(e)})
        return self._json(404, {"error": "unbekannt"})

    def do_POST(self):
        p, _ = self._route()
        auth = self.headers.get("Authorization", "")
        err = check(auth)
        if err:
            return self._json(err[0], {"error": err[1]})
        if p != "exchange":
            return self._json(404, {"error": "unbekannt"})
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            return self._json(413, {"error": "zu groß"})
        try:
            code = str((json.loads(self.rfile.read(n) or b"{}") or {}).get("code") or "")
            if not re.fullmatch(r"[A-Za-z0-9]{10,100}", code):
                return self._json(400, {"error": "Code ungültig"})
            j = st.exchange(code)
            save_token(auth, {"refresh_token": j["refresh_token"], "access_token": j.get("access_token"),
                              "expires_at": j.get("expires_at", 0), "athlete": (j.get("athlete") or {}).get("id")})
            return self._json(200, {"ok": True})
        except (st.StravaError, ValueError) as e:
            return self._json(502, {"error": str(e)})

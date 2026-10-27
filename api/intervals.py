"""intervals.icu als Vercel-Funktion (/api/intervals/...): Workouts in den Kalender, von dort nach MyWhoosh.

Zugriff nur mit gültiger Supabase-Anmeldung und nur für ALLOWED_EMAILS. Der Schlüssel (INTERVALS_API_KEY)
bleibt in Vercel und geht nie an den Browser.
"""
import json
import os
import re
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))
import intervals_client as icu  # noqa: E402
from sb_auth import check  # noqa: E402

MAX_BODY = 2 * 1024 * 1024


class handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write((fmt % args).split("?")[0] + "\n")

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _route(self):
        url = urllib.parse.urlsplit(self.path)
        q = urllib.parse.parse_qs(url.query)
        return (q.get("p") or [re.sub(r"^/api/intervals/?", "", url.path)])[0].strip("/")

    def _denied(self):
        err = check(self.headers.get("Authorization", ""))
        if err:
            self._json(err[0], {"error": err[1]})
        return bool(err)

    def do_GET(self):
        if self._denied():
            return
        if self._route() == "status":
            return self._json(200, {"configured": icu.configured()})
        return self._json(404, {"error": "unbekannt"})

    def do_POST(self):
        if self._denied():
            return
        if self._route() != "events":
            return self._json(404, {"error": "unbekannt"})
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            return self._json(413, {"error": "zu groß"})
        try:
            events = json.loads(self.rfile.read(n) or b"null")
        except ValueError:
            return self._json(400, {"error": "kein JSON"})
        try:
            icu.clean(events)
        except icu.IntervalsError as e:
            return self._json(400, {"error": str(e)})
        try:
            return self._json(200, {"count": icu.push(events)})
        except icu.IntervalsError as e:
            return self._json(502, {"error": str(e)})

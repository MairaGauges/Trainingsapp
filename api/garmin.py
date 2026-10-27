"""Garmin-Abruf als Vercel-Funktion (/api/garmin/...). Gleiche Routen wie server/server.py.

Zugriff nur mit gültiger Supabase-Anmeldung (Bearer-Token aus der App) und nur für Adressen in
ALLOWED_EMAILS. Der Garmin-Schlüssel (GARMIN_PERSONAL_API_KEY) bleibt in Vercel und geht nie an den Browser.
"""
import json
import os
import re
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))
from garmin_client import Garmin, GarminError  # noqa: E402
from sb_auth import check  # noqa: E402

garmin = Garmin("/nonexistent")  # Schlüssel nur aus der Umgebung


class handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # keine Query-Strings ins Log
        sys.stderr.write((fmt % args).split("?")[0] + "\n")

    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        q = urllib.parse.parse_qs(url.query)
        # Pfad nach /api/garmin/ – direkt oder über die Rewrite-Regel (?p=...)
        p = (q.get("p") or [re.sub(r"^/api/garmin/?", "", url.path)])[0].strip("/")
        err = check(self.headers.get("Authorization", ""))
        if err:
            return self._json(err[0], {"error": err[1]})
        if p == "status":
            return self._json(200, {"configured": garmin.configured()})
        if p == "diag":
            return self._json(200, garmin.diag())
        if p == "activities":
            try:
                days = max(1, min(int((q.get("days") or ["14"])[0]), 90))
                return self._json(200, {"activities": garmin.activities(days)})
            except (GarminError, ValueError) as e:
                return self._json(502, {"error": str(e)})
        m = re.fullmatch(r"file/([0-9A-Za-z_\-]{1,40})", p)
        if m:
            try:
                return self._send(200, garmin.file(m.group(1)), "application/zip")
            except GarminError as e:
                return self._json(502, {"error": str(e)})
        return self._json(404, {"error": "unbekannt"})

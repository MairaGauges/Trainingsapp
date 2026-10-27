"""Ende-zu-Ende-Test: App-Server + simulierte Garmin-Personal-API + Browser (Playwright).

Die Garmin-Seite ist ein Mock nach den Pfaden aus Garmins Python-Client. Das prüft unsere Logik
(Token-Austausch, Erneuerung bei 401, Abruf, Import), nicht Garmins echtes Verhalten.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import gen_test_files as g  # noqa: E402  (erzeugt tests/testfiles)

KEY = "TESTKEY-nicht-echt-123"
TMP = os.path.join(HERE, ".tmp")
PW = "geheim"
fails = []


def check(name, cond, info=""):
    print(("ok   " if cond else "FAIL ") + name + ((" | " + str(info)) if (info and not cond) else ""))
    if not cond:
        fails.append(name)


# ------------------------------------------------------------ Garmin-Mock
FIT = g.bike(g.d(2026, 10, 20, 16, 0))
ZIPPED = io.BytesIO()
with zipfile.ZipFile(ZIPPED, "w") as z:
    z.writestr("777_ACTIVITY.fit", FIT)
ZIPPED = ZIPPED.getvalue()
mock_state = {"tokens": 0, "expire_next": True, "seen_auth": []}


class Mock(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _j(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        if self.path.endswith("/personal-api-key/token"):
            if self.headers.get("Authorization") != "ApiKey " + KEY:
                return self._j(401, {"error": "bad key"})
            mock_state["tokens"] += 1
            return self._j(200, {"access_token": "tok%d" % mock_state["tokens"], "expires_in": 86400})
        self._j(404, {})

    def do_GET(self):
        auth = self.headers.get("Authorization", "")
        mock_state["seen_auth"].append(auth)
        if mock_state["expire_next"] and auth == "Bearer tok1":   # erstes Token „abgelaufen“ -> Server muss erneuern
            mock_state["expire_next"] = False
            return self._j(401, {})
        if not auth.startswith("Bearer tok"):
            return self._j(401, {})
        if self.path.startswith("/activitylist-service/activities/search/activities"):
            return self._j(200, [{"activityId": 777, "activityName": "Rolle", "startTimeLocal": "2026-10-20 18:00:00", "activityType": {"typeKey": "cycling"}}])
        if self.path == "/download-service/files/activity/777":
            self.send_response(200); self.send_header("Content-Type", "application/zip"); self.send_header("Content-Length", str(len(ZIPPED))); self.end_headers(); self.wfile.write(ZIPPED); return
        self._j(404, {})


def free_port():
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def call(base, method, path, body=None, auth=True):
    req = urllib.request.Request(base + path, method=method, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    if auth:
        import base64
        req.add_header("Authorization", "Basic " + base64.b64encode(("u:" + PW).encode()).decode())
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main():
    shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
    subprocess.run([sys.executable, os.path.join(ROOT, "build", "build_zwo.py")], check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, os.path.join(ROOT, "build", "build_dash.py")], check=True, stdout=subprocess.DEVNULL)

    mp = free_port(); mock = ThreadingHTTPServer(("127.0.0.1", mp), Mock)
    threading.Thread(target=mock.serve_forever, daemon=True).start()

    sp = free_port(); base = "http://127.0.0.1:%d" % sp
    env = dict(os.environ, PORT=str(sp), HOST="127.0.0.1", DATA_DIR=TMP, APP_PASSWORD=PW,
               GARMIN_BASE="http://127.0.0.1:%d" % mp, GARMIN_PERSONAL_API_KEY=KEY)
    srv = subprocess.Popen([sys.executable, os.path.join(ROOT, "server", "server.py")], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(base, timeout=1); break
            except urllib.error.HTTPError:
                break
            except Exception:
                time.sleep(0.1)

        # --- Zugriffsschutz und Speicher
        check("ohne Passwort 401", call(base, "GET", "/api/db", auth=False)[0] == 401)
        check("Startseite mit Passwort", call(base, "GET", "/")[0] == 200)
        code, _ = call(base, "PUT", "/api/db/test/a1", {"x": 1}); check("PUT", code == 200)
        code, b = call(base, "GET", "/api/db"); d = json.loads(b)
        check("GET zeigt Dokument", d["data"].get("test", {}).get("a1") == {"x": 1})
        check("ungültiger Name abgelehnt", call(base, "PUT", "/api/db/te%20st/a1", {"x": 1})[0] == 400)
        check("Pfad-Ausbruch blockiert", call(base, "GET", "/..%2f..%2fetc/passwd")[0] in (403, 404))
        call(base, "DELETE", "/api/db/test/a1")
        check("DELETE", "a1" not in json.loads(call(base, "GET", "/api/db")[1])["data"].get("test", {}))

        # --- Garmin über den Server
        check("status configured", json.loads(call(base, "GET", "/api/garmin/status")[1])["configured"] is True)
        code, b = call(base, "GET", "/api/garmin/activities?days=14")
        check("Aktivitätsliste (mit Token-Erneuerung)", code == 200 and json.loads(b)["activities"][0]["id"] == "777", (code, b[:200]))
        check("Token wurde bei 401 erneuert", mock_state["tokens"] >= 2, mock_state["tokens"])
        code, b = call(base, "GET", "/api/garmin/file/777")
        check("Datei = ZIP mit FIT", code == 200 and zipfile.ZipFile(io.BytesIO(b)).namelist() == ["777_ACTIVITY.fit"])
        for path in ("/api/garmin/status", "/api/garmin/diag", "/api/garmin/activities"):
            check("Schlüssel nie in Antwort " + path, KEY.encode() not in call(base, "GET", path)[1])
        check("Datei-ID wird geprüft", call(base, "GET", "/api/garmin/file/..%2f..%2fx")[0] in (400, 404))

        # --- Browser
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            exe = "/opt/pw-browsers/chromium"
            b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
            ctx = b.new_context(viewport={"width": 400, "height": 860}, has_touch=True, is_mobile=True, timezone_id="Europe/Berlin",
                                locale="de-DE", http_credentials={"username": "u", "password": PW})
            page = ctx.new_page(); errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            call(base, "PUT", "/api/db/strength/plan", json.load(open(os.path.join(ROOT, "seed", "store.example.json")))["data"]["strength"]["plan"])
            page.goto(base + "/"); page.wait_for_timeout(1200)
            check("Seite lädt ohne Skriptfehler", not errs, errs)

            page.tap("#tabbar [data-view='kraft']"); page.wait_for_timeout(300)
            inp = "input[data-ex='e11'][data-set='0']"
            page.fill(inp, "42,5"); page.press(inp, "Tab"); page.wait_for_timeout(600)
            page.tap("input[data-exd][data-ex='e11']"); page.wait_for_timeout(900)
            logs = json.loads(call(base, "GET", "/api/db")[1])["data"].get("strengthlogs", {})
            check("Gewicht + Haken auf dem Server", any(v.get("ex", {}).get("e11", {}).get("w", [""])[0] == "42,5" and v["ex"]["e11"].get("d") for v in logs.values()), logs)

            page.reload(); page.wait_for_timeout(1200); page.tap("#tabbar [data-view='kraft']")
            check("Werte nach Neuladen sichtbar", page.input_value(inp) == "42,5")

            # Offline: Änderung geht in die Warteschlange und kommt später an
            ctx.set_offline(True)
            page.fill("input[data-ex='e13'][data-set='1']", "30"); page.press("input[data-ex='e13'][data-set='1']", "Tab"); page.wait_for_timeout(500)
            off = json.loads(call(base, "GET", "/api/db")[1])["data"].get("strengthlogs", {})
            check("offline: noch nicht auf dem Server", not any("e13" in v.get("ex", {}) for v in off.values()))
            ctx.set_offline(False); page.evaluate("window.dispatchEvent(new Event('online'))"); page.wait_for_timeout(1500)
            on = json.loads(call(base, "GET", "/api/db")[1])["data"].get("strengthlogs", {})
            check("online: Warteschlange geleert", any(v.get("ex", {}).get("e13", {}).get("w", ["", ""])[1] == "30" for v in on.values()), on)

            # Garmin-Abruf per Knopf
            page.tap("#tabbar [data-view='garmin']"); page.wait_for_timeout(300)
            check("Garmin-Knopf sichtbar", page.locator("[data-action='g-sync']").count() == 1)
            page.tap("[data-action='g-sync']"); page.wait_for_timeout(2500)
            acts = json.loads(call(base, "GET", "/api/db")[1])["data"].get("activities", {})
            check("Aktivität importiert", len(acts) == 1 and list(acts.values())[0].get("sport") == "rad", list(acts)[:2])
            a = list(acts.values())[0]
            check("Leistungsdaten gelesen", a.get("avgP") and a.get("np"), {k: a.get(k) for k in ("avgP", "np", "dur")})
            page.tap("[data-action='g-sync']"); page.wait_for_timeout(2000)
            check("zweiter Abruf erzeugt kein Duplikat", len(json.loads(call(base, "GET", "/api/db")[1])["data"].get("activities", {})) == 1)
            page.screenshot(path=os.path.join(TMP, "garmin.png"))
            sw = page.evaluate("navigator.serviceWorker ? navigator.serviceWorker.getRegistrations().then(r => r.length) : -1")
            print("info: Service-Worker-Registrierungen (localhost = sicherer Kontext):", sw)
            check("keine Skriptfehler am Ende", not errs, errs)
            b.close()
    finally:
        srv.terminate(); mock.shutdown()
    print("\n%d Fehler" % len(fails) if fails else "\nalle Tests bestanden")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

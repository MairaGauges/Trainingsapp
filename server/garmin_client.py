"""Garmin Connect Personal API (nur Standardbibliothek). Genutzt von server/server.py und api/garmin.py (Vercel)."""
import base64
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

GARMIN_BASE = os.environ.get("GARMIN_BASE", "https://personal.connectapi.garmin.com").rstrip("/")
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"


class GarminError(Exception):
    pass


# Kennzahlen je Aktivität aus Garmins Liste (VO2max-Schätzung, Trainingseffekt, Zeit in Pulszonen)
ACT_KEYS = re.compile(r"^(vO2MaxValue|aerobicTrainingEffect|anaerobicTrainingEffect|trainingEffectLabel|activityTrainingLoad|averageHR|maxHR|hrTimeInZone_\d|startTimeGMT)$")
# Persönliches, das die App nicht braucht, verlässt den Server nie
DROP = re.compile(r"birth|weight|height|email|name|gender|location|phone|address|handedness|picture|image|locale|timeZone|userId|profileId|displayName", re.I)
DAILY_KEYS = ("calendarDate", "restingHeartRate", "minHeartRate", "maxHeartRate", "lastSevenDaysAvgRestingHeartRate",
              "averageStressLevel", "bodyBatteryHighestValue", "bodyBatteryLowestValue", "sleepingSeconds")


def scrub(x, depth=0):
    """Rekursiv alle Felder ohne persönliche Angaben behalten (Tiefe und Listen begrenzt)."""
    if depth > 6:
        return None
    if isinstance(x, dict):
        return {k: scrub(v, depth + 1) for k, v in x.items() if not DROP.search(k)}
    if isinstance(x, list):
        return [scrub(v, depth + 1) for v in x[:400]]
    return x


def as_list(j):
    if isinstance(j, list):
        return j
    if isinstance(j, dict):
        return next((v for v in j.values() if isinstance(v, list)), [])
    return []


def jwt_exp(tok):
    """exp-Claim eines JWT (Sekunden) oder None."""
    try:
        part = tok.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))).get("exp")
    except (IndexError, ValueError, AttributeError):
        return None


def parse_token(body):
    """Token-Antwort als JSON-Objekt, JSON-String oder rohes JWT."""
    text = body.decode("utf-8", "replace").strip()
    try:
        j = json.loads(text)
    except ValueError:
        j = text
    if isinstance(j, str):
        if j.count(".") != 2:
            raise GarminError("Token-Antwort nicht lesbar")
        return {"access_token": j}
    if not isinstance(j, dict):
        raise GarminError("Token-Antwort nicht lesbar")
    return j


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
        # wie Garmins curl-Beispiel: POST ohne Körper, kein Content-Type, Accept */*
        headers = dict({"Accept": "*/*", "User-Agent": "ef27-trainer/1.0"}, **headers)
        req = urllib.request.Request(GARMIN_BASE + path, method=method, headers=headers)
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
            status, body, ctype = self._request("POST", TOKEN_PATH, {"Authorization": "ApiKey " + k})
            if status in (401, 403):
                raise GarminError("Schlüssel abgelehnt (HTTP %d). Abgelaufen oder gelöscht?" % status)
            if status != 200:
                hint = body[:160].decode("utf-8", "replace").replace(k, "***").strip()
                raise GarminError("Token-Abruf fehlgeschlagen (HTTP %d, %s)%s" % (status, ctype or "ohne Typ", ": " + hint if hint else ""))
            j = parse_token(body)
            tok = j.get("access_token") or j.get("accessToken") or j.get("token")
            if not tok:
                raise GarminError("Token-Antwort ohne access_token (Felder: %s)" % ", ".join(sorted(j)[:8]))
            ttl = j.get("expires_in") or j.get("expiresIn")
            exp = j.get("expires_at") or j.get("expiresAt") or jwt_exp(tok)
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
        while offset < 2000:
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
                            "type": (t.get("typeKey") if isinstance(t, dict) else str(t)) or "",
                            "g": {k: v for k, v in it.items() if ACT_KEYS.match(k) and v is not None}})
            if len(items) < 50:
                break
            offset += 50
        return out

    def _json(self, path):
        body, _ = self.get(path)
        try:
            return json.loads(body)
        except ValueError:
            raise GarminError("Antwort ist kein JSON")

    def profile(self, days=120):
        """Pulszonen, Profilwerte (VO2max, Laktatschwelle), HRV, Ruhepuls-Verlauf, Fitnessalter.
        Jeder Teil einzeln: fällt einer aus, kommen die anderen trotzdem."""
        today = date.today()
        start = today - timedelta(days=days)
        out = {"fetched": today.isoformat(), "errors": {}}

        def grab(name, path, fn=scrub):
            try:
                out[name] = fn(self._json(path))
            except GarminError as e:
                out["errors"][name] = str(e)

        grab("zones", "/biometric-service/heartRateZones/v2")
        grab("settings", "/userprofile-service/userprofile/settings")
        grab("fitnessAge", "/fitnessage-service/fitnessage/v2/%s" % today)
        grab("hrv", "/hrv-service/hrv/daily/%s/%s" % (start, today))
        grab("daily", "/usersummary-service/v2/dailysummaries?startDate=%s&endDate=%s" % (start, today),
             lambda j: [{k: d.get(k) for k in DAILY_KEYS if d.get(k) is not None} for d in as_list(j) if isinstance(d, dict)])
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

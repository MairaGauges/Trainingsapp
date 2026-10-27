"""intervals.icu: geplante Workouts (.zwo) in den Kalender schreiben. MyWhoosh übernimmt sie von dort,
wenn es in MyWhoosh mit intervals.icu verbunden ist. Genutzt von server/server.py und api/intervals.py.

API: POST /api/v1/athlete/0/events/bulk?upsert=true (0 = Athlet des API-Schlüssels),
Anmeldung per Basic-Auth mit Benutzer "API_KEY" und dem Schlüssel als Passwort.
"""
import base64
import json
import os
import re
import urllib.error
import urllib.request

BASE = os.environ.get("INTERVALS_BASE", "https://intervals.icu").rstrip("/")
MAX_EVENTS = 14
MAX_FILE = 200 * 1024
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T00:00:00$")
FILE_RE = re.compile(r"^[A-Za-z0-9_\-.]{1,120}\.zwo$")
EXT_RE = re.compile(r"^ef27-[A-Za-z0-9_\-]{1,60}$")


class IntervalsError(Exception):
    pass


def key():
    return os.environ.get("INTERVALS_API_KEY", "").strip()


def configured():
    return bool(key())


def clean(events):
    """Nur geplante Rad-Workouts mit .zwo-Datei durchlassen, alles andere abweisen."""
    if not isinstance(events, list) or not 1 <= len(events) <= MAX_EVENTS:
        raise IntervalsError("1 bis %d Workouts erwartet" % MAX_EVENTS)
    out = []
    for e in events:
        if not isinstance(e, dict):
            raise IntervalsError("Workout ist kein Objekt")
        date, fn, xml, ext, name = (e.get(k) for k in ("start_date_local", "filename", "file_contents", "external_id", "name"))
        if not (isinstance(date, str) and DATE_RE.match(date)):
            raise IntervalsError("Datum ungültig")
        if not (isinstance(fn, str) and FILE_RE.match(fn)):
            raise IntervalsError("Dateiname ungültig")
        if not (isinstance(xml, str) and 0 < len(xml) <= MAX_FILE and "<workout_file>" in xml):
            raise IntervalsError("Workout-Datei ungültig")
        if not (isinstance(ext, str) and EXT_RE.match(ext)):
            raise IntervalsError("external_id ungültig")
        out.append({"category": "WORKOUT", "type": "VirtualRide", "start_date_local": date, "filename": fn,
                    "file_contents": xml, "external_id": ext, "name": str(name or fn)[:120]})
    return out


def _call(method, path, payload):
    k = key()
    if not k:
        raise IntervalsError("Kein intervals.icu-Schlüssel hinterlegt")
    auth = base64.b64encode(("API_KEY:" + k).encode()).decode()
    req = urllib.request.Request(BASE + "/api/v1/athlete/0/" + path, data=json.dumps(payload).encode("utf-8"), method=method,
                                 headers={"Authorization": "Basic " + auth, "Content-Type": "application/json", "Accept": "application/json",
                                          "User-Agent": "ef27-trainer/1.0"})  # Cloudflare sperrt Python-urllib (Fehler 1010)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        hint = e.read()[:160].decode("utf-8", "replace").replace(k, "***").strip()
        if e.code == 401:
            raise IntervalsError("intervals.icu lehnt den Schlüssel ab (HTTP 401)")
        raise IntervalsError("intervals.icu antwortet mit HTTP %d%s" % (e.code, ": " + hint if hint else ""))
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise IntervalsError("intervals.icu nicht erreichbar: %s" % getattr(e, "reason", e))
    except ValueError:
        return None


def clean_ids(ids):
    if not isinstance(ids, list) or not 1 <= len(ids) <= MAX_EVENTS or not all(isinstance(i, str) and EXT_RE.match(i) for i in ids):
        raise IntervalsError("Liste mit external_ids erwartet")
    return ids


def delete(ids):
    """Entfernt eigene Termine (nur external_id mit ef27-). Nicht vorhandene werden ignoriert."""
    res = _call("PUT", "events/bulk-delete", [{"external_id": i} for i in clean_ids(ids)])
    return res if isinstance(res, int) else len(ids)


def push(events):
    """Schreibt die Workouts (upsert über external_id) und liefert die Anzahl."""
    res = _call("POST", "events/bulk?upsert=true", clean(events))
    return len(res) if isinstance(res, list) else len(events)

"""Strava: Fahrten mit Leistung (z. B. vom ICG-Rad über die ICG-App) samt Verlauf holen. Genutzt von api/strava.py.

Einmalige Freigabe per OAuth (Scope activity:read_all). Den Refresh-Token speichert die Funktion mit dem
Supabase-Token der angemeldeten Person in deren eigener Zeile (Tabelle docs, col "strava", id "token").
Die App lädt diese Zeile nie (siehe web/shim.js), der Token bleibt auf dem Server.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://www.strava.com/api/v3"
OAUTH = "https://www.strava.com/oauth"
UA = {"User-Agent": "ef27-trainer/1.0"}


class StravaError(Exception):
    pass


def client():
    return os.environ.get("STRAVA_CLIENT_ID", "").strip(), os.environ.get("STRAVA_CLIENT_SECRET", "").strip()


def configured():
    cid, sec = client()
    return bool(cid and sec)


def _req(method, url, data=None, headers=None, timeout=30):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    h = dict(UA, **(headers or {}))
    if body is not None:
        h["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        hint = e.read()[:200].decode("utf-8", "replace")
        raise StravaError("Strava antwortet mit HTTP %d: %s" % (e.code, hint))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise StravaError("Strava nicht erreichbar: %s" % getattr(e, "reason", e))


def authorize_url(redirect_uri, state=""):
    cid, _ = client()
    return OAUTH + "/authorize?" + urllib.parse.urlencode({
        "client_id": cid, "response_type": "code", "redirect_uri": redirect_uri,
        "approval_prompt": "auto", "scope": "activity:read_all", "state": state})


def exchange(code):
    cid, sec = client()
    j = _req("POST", OAUTH + "/token", {"client_id": cid, "client_secret": sec, "code": code, "grant_type": "authorization_code"})
    if not j or not j.get("refresh_token"):
        raise StravaError("Strava hat keinen Token geliefert")
    return j


def refresh(refresh_token):
    cid, sec = client()
    j = _req("POST", OAUTH + "/token", {"client_id": cid, "client_secret": sec, "refresh_token": refresh_token, "grant_type": "refresh_token"})
    if not j or not j.get("access_token"):
        raise StravaError("Strava-Freigabe abgelaufen. Bitte in der App neu verbinden.")
    return j


def activities(access, days):
    after = int(time.time()) - days * 86400
    out, page = [], 1
    while page <= 10:
        items = _req("GET", API + "/athlete/activities?" + urllib.parse.urlencode({"after": after, "per_page": 100, "page": page}),
                     headers={"Authorization": "Bearer " + access})
        if not isinstance(items, list):
            break
        for a in items:
            out.append({"id": str(a.get("id")), "name": a.get("name") or "", "start": a.get("start_date") or "",
                        "elapsed": a.get("elapsed_time"), "moving": a.get("moving_time"), "type": a.get("sport_type") or a.get("type") or "",
                        "trainer": bool(a.get("trainer")), "watts": bool(a.get("device_watts") or a.get("average_watts")),
                        "avgW": a.get("average_watts"), "hr": bool(a.get("has_heartrate")), "device": a.get("device_name") or ""})
        if len(items) < 100:
            break
        page += 1
    return out


def streams(access, activity_id):
    j = _req("GET", API + "/activities/%s/streams?keys=time,watts,heartrate,cadence&key_by_type=true" % urllib.parse.quote(activity_id, safe=""),
             headers={"Authorization": "Bearer " + access})
    if not isinstance(j, dict):
        raise StravaError("Keine Verlaufsdaten")
    return {k: (j.get(k) or {}).get("data") for k in ("time", "watts", "heartrate", "cadence") if j.get(k)}

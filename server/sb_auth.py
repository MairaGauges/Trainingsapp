"""Anmeldeprüfung für die Vercel-Funktionen: Supabase-Token prüfen, nur Adressen aus ALLOWED_EMAILS zulassen."""
import json
import os
import urllib.error
import urllib.request

SUPABASE_URL = (os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = (os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
                or os.environ.get("SUPABASE_PUBLISHABLE_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY") or "")
ALLOWED = {e.strip().lower() for e in os.environ.get("ALLOWED_EMAILS", "").split(",") if e.strip()}


def user_email(auth_header):
    """Prüft das Supabase-Token beim Auth-Server und liefert die E-Mail oder None."""
    if not (auth_header.startswith("Bearer ") and SUPABASE_URL and SUPABASE_KEY):
        return None
    req = urllib.request.Request(SUPABASE_URL + "/auth/v1/user", headers={"apikey": SUPABASE_KEY, "Authorization": auth_header})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return (json.loads(r.read()).get("email") or "").lower() or None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None


def check(auth_header):
    """(HTTP-Status, Fehlertext) bei Ablehnung, sonst None."""
    if not ALLOWED:
        return 503, "ALLOWED_EMAILS ist in Vercel nicht gesetzt"
    if user_email(auth_header) not in ALLOWED:
        return 401, "Anmeldung erforderlich"
    return None

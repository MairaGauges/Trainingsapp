import json, os, re, sys, glob
from datetime import date, timedelta
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
ZWO = os.path.join(ROOT, "dist", "zwo")
DIST = os.path.join(ROOT, "dist")
WEB = os.path.join(ROOT, "web")
sys.path.insert(0, HERE)
from plan_data import phases, C_TXT, D_TXT, D_TXT_DELOAD  # noqa: E402

rows = {}
for _title, ph_rows in phases:
    for (w, d, n, a, b, typ) in ph_rows:
        rows[w] = (a, b, typ)

# ---- Workouts je Woche/Tag
workouts, titles, mins = {}, {}, {}
byweek = {}
for path in sorted(glob.glob(os.path.join(ZWO, "*.zwo"))):
    fn = os.path.basename(path)
    xml = open(path, encoding="utf-8").read()
    workouts[fn] = xml
    name = ET.fromstring(xml).find("name").text
    t = name.split(": ", 1)[1] if ": " in name else name
    t = re.sub(r"(\d)x(\d)", r"\1×\2", t)
    titles[fn] = t
    m = re.match(r"W(\d\d)_(Mo|Di|Do|Sa)_(A|B|C|D)_", fn)
    if m:
        byweek.setdefault(int(m.group(1)), {})[m.group(3)] = fn
    m = re.match(r"Taper_(Mo|Mi|Fr)_", fn)
    if m:
        byweek.setdefault(26, {})[m.group(1)] = fn
    tot = 0
    for e in ET.fromstring(xml).find("workout"):
        tot += int(e.get("Duration"))
    mins[fn] = round(tot / 60)

KRAFT1 = {
    1: "Kniebeuge, Rumänisches Kreuzheben, Ausfallschritte, Hip Thrust: 3–4×6–10, moderat bis schwer. <b>Satzpause 90–120 s</b>",
    2: "Wie Phase 1, Gewichte steigern: 3×5–8. <b>Satzpause 2–3 min</b>",
    3: "Erhalt: Kniebeuge und Kreuzheben 3×3–5 schwer, eine explosive Übung. <b>Satzpause 2–3 min</b>",
    4: "Eine kurze Einheit: 2×3–5 schwer, nicht ermüden. <b>Satzpause 2–3 min</b>",
}
KRAFT2 = {
    1: "Klimmzüge oder Rudern, Liegestütz oder Bankdrücken, Core, Single-Leg: 3×8–12. <b>Satzpause 60–90 s</b>",
    2: "Wie Phase 1, mehr Rumpf und Stabilität. <b>Satzpause 60–90 s</b>",
    3: "Oberkörper und Core, 2 Sätze pro Übung. <b>Satzpause 60 s</b>",
    4: "Optional, darf entfallen.",
}
PHASE_NAMES = {1: "Phase 1 · Grundlage", 2: "Phase 2 · Aufbau", 3: "Phase 3 · Build", 4: "Phase 4 · Rennspezifisch", 5: "Taper"}
DELOAD = {4, 8, 12, 16, 20, 24}
SOLO = 15  # ab 8.2.2027 (Woche 15) kein Spinning und kein Schwimmen mehr
# Gesetzliche Feiertage in Bayern im Planzeitraum: dann gibt es kein Spinning und kein Schwimmen
FEIERTAGE = {date(2026, 12, 25): "1. Weihnachtstag", date(2026, 12, 26): "2. Weihnachtstag", date(2027, 1, 1): "Neujahr",
             date(2027, 1, 6): "Heilige Drei Könige", date(2027, 3, 26): "Karfreitag", date(2027, 3, 29): "Ostermontag",
             date(2027, 5, 1): "Tag der Arbeit"}
FREI = {date(2027, 1, 3): "Geburtstag"}  # keine Einheit an diesen Tagen
TEST = {7, 13, 19}

weeks = []
for n in range(1, 27):
    start = date(2026, 11, 2) + timedelta(days=7 * (n - 1))
    ph = 1 if n <= 6 else 2 if n <= 12 else 3 if n <= 20 else 4 if n <= 25 else 5
    kind = "taper" if n == 26 else "deload" if n in DELOAD else "test" if n in TEST else "normal"
    files = byweek.get(n, {})
    S = [None] * 7
    deload_note = " Entlastung: gleiche Gewichte, nur 2 Sätze." if kind == "deload" else ""
    if n < 26:
        a_txt, b_txt, _ = rows[n]
        a_tag = "Test" if kind == "test" else "locker" if kind == "deload" or n == 2 else "Z2"
        a_note = (" Empfohlen, damit die Zonen stimmen. Danach am Dienstag " + ("beim Spinning nicht voll gehen." if n < SOLO else "nur locker.")) if kind == "test" else ""
        S[0] = dict(type="A", sport="rad", title="Rolle A", slot="Rolle A", detail=a_txt + a_note, tag=a_tag, opt=True, file=files.get("A"), min=mins.get(files.get("A")))
        S[1] = dict(type="spin", sport="rad", title="Spinning", detail="Intervallkurs, 60 min. Die harte Einheit der Woche.", tag="hart")
        if n == 2:
            S[1] = dict(type="spin", sport="rad", title="Spinning · FTP-Test", detail="FTP-Test im Spinningkurs, am besten 20 min so gleichmäßig hart wie möglich (FTP = 95 % vom Schnitt). Davor 15 min einfahren mit 2–3 kurzen Steigerungen. Wenn das Rad Leistung misst, mit Garmin aufzeichnen, dann liest die App die FTP aus. Danach neue FTP oben und in MyWhoosh eintragen.", tag="Test")
        S[2] = dict(type="kraft", sport="kraft", title="Kraft 1 · Beine und Ganzkörper", detail=KRAFT1[ph] + deload_note, tag="Beine")
        S[3] = dict(type="swim", sport="schwimmen", title="Schwimmen", detail="Schwimmtraining, gute Entlastung für die Beine.", tag="locker")
        S[4] = dict(type="frei", title="Ruhetag", detail="Frei oder 15 min Mobility. Ruhe vor der langen Einheit am Samstag.", tag="frei")
        outdoor = (n == 23)
        S[5] = dict(type="B", sport="rad", title="Ausfahrt draußen" if outdoor else "Rolle B", slot="Rolle B", detail=b_txt, tag="lang", stabi=True, file=files.get("B"), min=mins.get(files.get("B")))
        S[6] = dict(type="kraft", sport="kraft", title="Kraft 2 · Oberkörper und Rumpf", detail=KRAFT2[ph] + deload_note, tag="Oberkörper")
        note = {2: "FTP-Test beim Spinning am Dienstag", 7: "FTP-Test am Montag", 13: "FTP-Test am Montag", 19: "FTP-Test am Montag", 21: "Samstag 2 h (Ausnahme)", 22: "Samstag besser draußen", 23: "Samstag draußen fahren"}.get(n, "")
        note = (note + " · " if note else "") + "Spinning + Rolle B · Rolle A optional"
        if SOLO <= n <= 24:  # W25 ist das Trainingslager
            # kein Spinning und Schwimmen mehr: Dienstag die harte Einheit auf der Rolle, Donnerstag locker
            S[1] = dict(type="B", sport="rad", title="Rolle C", slot="Rolle C", detail=C_TXT[n] + (" Statt Spinning." if n == SOLO else ""),
                        tag="locker" if kind == "test" else "hart", file=files.get("C"), min=mins.get(files.get("C")))
            S[3] = dict(type="B", sport="rad", title="Rolle D · locker", slot="Rolle D", detail=D_TXT_DELOAD if kind == "deload" else D_TXT,
                        tag="locker", opt=True, file=files.get("D"), min=mins.get(files.get("D")))
            note = note.replace("Spinning + Rolle B · Rolle A optional", "Rolle C + Rolle B · A und D optional")
            if n == SOLO:
                note = "Ab jetzt kein Spinning und Schwimmen: Di Rolle C (Intervalle), Do optional locker"
    else:
        def tp(day, tag):
            f = files.get(day)
            return f, mins.get(f)
        f, m = tp("Mo", "")
        S[0] = dict(type="B", sport="rad", title="Taper 1", slot="Taper Montag", detail="45 min Z2 mit 3×3' @ 203 W, <b>Pause 3' @ 110 W</b>.", tag="kurz", file=f, min=m)
        S[1] = dict(type="frei", title="Ruhetag", detail="Frei.", tag="frei")
        f, m = tp("Mi", "")
        S[2] = dict(type="B", sport="rad", title="Taper 2", slot="Taper Mittwoch", detail="40 min Z2 mit 3×1' @ 212 W, <b>Pause 2' @ 110 W</b>.", tag="kurz", file=f, min=m)
        S[3] = dict(type="frei", title="Ruhetag", detail="Frei oder 15 min Core und Mobility. Keine Beinkraft mehr in dieser Woche.", tag="frei")
        f, m = tp("Fr", "")
        S[4] = dict(type="B", sport="rad", title="Taper 3 · Aktivierung", slot="Taper Freitag", detail="30 min locker mit 2×1' @ 203 W, <b>Pause 2' @ 110 W</b>.", tag="kurz", file=f, min=m)
        S[5] = dict(type="race", sport="rad", title="Rennen · Eschborn-Frankfurt", detail="92 km, ca. 1.300 Höhenmeter. Verpflegung: 60–80 g Kohlenhydrate pro Stunde.", tag="Renntag")
        S[6] = dict(type="frei", title="Erholung", detail="Frei.", tag="frei")
        note = "Rennwoche"
    if n == 8:
        # Weihnachten 21.–27.12.: kein Spinning, kein Schwimmen, keine Rolle (Rad im Gym), 25. und 26.12. frei
        S[0] = dict(type="B", sport="rad", gym=True, title="Gym-Rad · Intervalle", slot="Gym-Rad", tag="lang", stabi=True, file=files.get("B"), min=mins.get(files.get("B")),
                    detail="Statt Spinning und Rolle B, auf dem Rad im Gym: 70 min mit 10' einfahren, 2×10' @ 170 W, <b>Pause 5' @ 120 W</b>, Rest Z2. "
                           "Zeigt das Rad keine Watt: Intervalle zügig, aber noch ruhig sprechbar (Tempo, Z3 nach Puls), sonst Z2.")
        S[1] = dict(type="frei", title="Ruhetag", detail="Kein Spinning in dieser Woche.", tag="frei")
        S[3] = dict(type="B", sport="rad", gym=True, title="Gym-Rad · locker", slot="Gym-Rad", tag="locker", opt=True, file=files.get("A"), min=mins.get(files.get("A")),
                    detail="Statt Schwimmen: 45 min ganz locker, Z1–Z2 (100–130 W oder nach Puls). Optional.")
        S[4] = dict(type="frei", title="Weihnachten", detail="Frei.", tag="frei")
        S[5] = dict(type="frei", title="Weihnachten", detail="Frei.", tag="frei")
        note = "Weihnachten: Rad im Gym, kein Spinning und Schwimmen, 25. und 26.12. frei"
    for i in range(7):
        d = start + timedelta(days=i)
        if d in FREI:
            gone = S[i]["title"] if S[i]["type"] != "frei" else ""
            S[i] = dict(type="frei", title=FREI[d], detail="Kein Training." + (" " + gone + " entfällt." if gone else ""), tag="frei")
            note = "%s %d.%d. %s, kein Training · " % (["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][i], d.day, d.month, FREI[d]) + note
        elif d in FEIERTAGE and S[i]["type"] in ("spin", "swim"):
            S[i] = dict(type="frei", title="Ruhetag", detail=FEIERTAGE[d] + ": kein " + ("Spinning" if S[i]["type"] == "spin" else "Schwimmen") + ".", tag="frei")
    camp = False
    if n == 24:
        S[6] = dict(type="camp", sport="rad", title="Trainingslager · Tag 1", detail="Anreise. 1,5–2 h locker, Rad und Sitzposition prüfen. Kraft 2 entfällt.", tag="locker", tss=70)
        note = "Trainingslager ab Sonntag · " + note
    if n == 25:
        camp = True
        S[0] = dict(type="camp", sport="rad", title="Lange Fahrt · bis 110 km", detail="Fast alles Z2 (120–140 W), Anstiege gleichmäßig, nicht über 185 W. Generalprobe Verpflegung: ab der ersten halben Stunde 60–80 g Kohlenhydrate pro Stunde.", tag="lang", tss=220)
        S[1] = dict(type="frei", title="Ruhetag", detail="Ruhetag nach der langen Fahrt. Wenn ihr doch fahrt: höchstens 1 h ganz locker.", tag="frei")
        S[2] = dict(type="camp", sport="rad", title="Anstiege im Renntempo", detail="2,5–3 h: 2–3 Anstiege à 8–15 min @ 175–185 W, dazwischen und danach Z2. Letzte harte Fahrt vor dem Rennen.", tag="hart", tss=160)
        S[3] = dict(type="camp", sport="rad", title="Mittellange Fahrt · bis 80 km", detail="Z2, Anstiege ruhig (höchstens 165 W). Kein Gruppenrennen.", tag="lang", tss=150)
        S[4] = dict(type="camp", sport="rad", title="Lockere Runde", detail="1–1,5 h locker, gern mit Kaffeepause. Ab heute nur noch locker bis zum Rennen.", tag="locker", tss=50)
        S[5] = dict(type="frei", title="Rückreise", detail="Frei. Wer mag: 30–45 min ganz locker.", tag="frei")
        S[6] = dict(type="frei", title="Erholung", detail="Frei. Kraft entfällt in dieser Woche.", tag="frei")
        note = "Trainingslager So 18.4. – Fr 23.4. · Ruhepuls morgens 5–7 Schläge über normal: an dem Tag nur 1 h locker"
    weeks.append(dict(n=n, start=start.isoformat(), phase=ph, phaseName=PHASE_NAMES[ph], kind=kind, note=note, camp=camp, sessions=S))

data = dict(weeks=weeks, workouts=workouts, titles=titles, race="2027-05-01", ftp=193)
js = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
page = tpl.replace("__DATA__", js)

os.makedirs(DIST, exist_ok=True)
# 1) Artifact-Variante (claude.ai): vollständiges Dokument mit dem Grundgerüst, das claude.ai bisher selbst ergänzt hat
ART_HEAD = ('<!doctype html><html><head><meta charset=utf8><meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<style>:root{color-scheme:light;box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
            'html{scroll-padding-top:env(safe-area-inset-top,0px)}body{margin:0;padding:0;font:14px -apple-system,BlinkMacSystemFont,sans-serif;background:#fff;color:#000}'
            'img{max-width:100%}[hidden]:not([hidden=until-found i]){display:none!important}</style></head><body>\n')
open(os.path.join(DIST, "artifact.html"), "w", encoding="utf-8").write(ART_HEAD + page + "\n</body></html>\n")

# 2) Eigenständige App (Server + PWA)
app = ('<!doctype html><html lang="de"><head><meta charset="utf-8">'
       '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
       '<meta name="theme-color" content="#0e161c">'
       '<meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes">'
       '<meta name="apple-mobile-web-app-title" content="EF 2027">'
       '<link rel="manifest" href="manifest.webmanifest"><link rel="apple-touch-icon" href="icons/icon-180.png">'
       '<link rel="icon" href="icons/icon-192.png">'
       '<style>html{-webkit-text-size-adjust:100%}body{margin:0;font:14px system-ui}[hidden]{display:none!important}img{max-width:100%}</style>'
       '<script src="config.js"></script><script src="shim.js"></script></head><body>' + page + "</body></html>")
open(os.path.join(WEB, "index.html"), "w", encoding="utf-8").write(app)

# 3) Speicher-Konfiguration: mit Supabase-Variablen (Vercel) speichert die App in Supabase, sonst beim eigenen Server.
#    Nur URL und öffentlicher Schlüssel (anon/publishable) – nie den service_role-Schlüssel.
env = lambda *ks: next((os.environ[k].strip() for k in ks if os.environ.get(k, "").strip()), "")
sb_url = env("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL")
sb_key = env("SUPABASE_ANON_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY", "SUPABASE_PUBLISHABLE_KEY", "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
cfg = dict(supabaseUrl=sb_url, supabaseKey=sb_key) if sb_url and sb_key else None
open(os.path.join(WEB, "config.js"), "w", encoding="utf-8").write("window.EF27_CONFIG = %s;\n" % json.dumps(cfg))
print("Speicher:", "Supabase " + sb_url if cfg else "eigener Server")
print("web/index.html:", len(app.encode()), "Bytes, Workouts:", len(workouts))
for w in weeks:
    miss = [i for i, s in enumerate(w["sessions"]) if s["type"] in ("A", "B") and not s.get("file") and not (w["n"] == 23 and i == 5)]
    if miss:
        print("keine Datei:", w["n"], miss)

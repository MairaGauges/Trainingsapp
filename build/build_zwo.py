import os, zipfile, datetime
import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr, escape

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "..", "dist")
OUT = os.path.join(BASE, "zwo")
os.makedirs(OUT, exist_ok=True)
for fn in os.listdir(OUT):
    os.remove(os.path.join(OUT, fn))

FTP = 193
Z2 = 125
START = datetime.date(2026, 11, 2)


def f(w):
    return round(w / FTP, 3)


def wu(m, lo=100, hi=145):
    return ("ramp", "Warmup", m * 60, lo, hi)


def cd(m, lo=110, hi=100):
    return ("ramp", "Cooldown", m * 60, lo, hi)


def st(sec, w, cad=None, msg=None):
    return ("steady", sec, w, cad, msg)


def z2(m, w=Z2):
    return st(m * 60, w, None, "Z2 locker")


FILL = ("fill",)


def reps(n, on_s, on_w, off_s, off_w, cad_on=None, cad_off=None):
    out = []
    for i in range(n):
        c = cad_on[i] if isinstance(cad_on, list) else cad_on
        out.append(st(on_s, on_w, c, f"Block {i+1}/{n}: {on_w} W"))
        if i < n - 1:
            out.append(st(off_s, off_w, cad_off, f"Pause {off_s//60} min locker, {off_w} W"))
    return out


def dur(s):
    if s[0] == "ramp":
        return s[2]
    return s[1]


def resolve(steps, total_min):
    if FILL in steps:
        fixed = sum(dur(s) for s in steps if s != FILL)
        rem = total_min * 60 - fixed
        assert rem > 0, (steps, rem)
        steps = [st(rem, Z2, None, "Z2 locker") if s == FILL else s for s in steps]
    return steps


def to_xml(name, desc, steps):
    L = ['<?xml version="1.0" encoding="UTF-8"?>', "<workout_file>",
         "  <author>Claude</author>",
         f"  <name>{escape(name)}</name>",
         f"  <description>{escape(desc)}</description>",
         "  <sportType>bike</sportType>", "  <tags/>", "  <workout>"]
    for s in steps:
        if s[0] == "ramp":
            _, tag, d, lo, hi = s
            L.append(f'    <{tag} Duration="{d}" PowerLow="{f(lo)}" PowerHigh="{f(hi)}"/>')
        elif s[0] == "steady":
            _, d, w, cad, msg = s
            a = f'Duration="{d}" Power="{f(w)}"'
            if cad:
                a += f' Cadence="{cad}"'
            if msg:
                L.append(f"    <SteadyState {a}><textevent timeoffset=\"0\" message={quoteattr(msg)}/></SteadyState>")
            else:
                L.append(f"    <SteadyState {a}/>")
        elif s[0] == "free":
            _, d, msg = s
            L.append(f'    <FreeRide Duration="{d}" FlatRoad="1"><textevent timeoffset="0" message={quoteattr(msg)}/></FreeRide>')
    L += ["  </workout>", "</workout_file>"]
    return "\n".join(L)


catalog = []


def add(wk, day, sess, slug, title, desc, steps, total_min=None, date_off=0):
    steps = resolve(steps, total_min)
    mon = START + datetime.timedelta(days=7 * (wk - 1) + date_off)
    ds = f"{mon.day}.{mon.month}."
    wk_lbl = "Taper" if sess == "Taper" else f"W{wk:02d}"
    name = f"{wk_lbl} {day} {ds} {sess}: {title}"
    fname = f"{wk_lbl}_{day}_{sess}_{slug}.zwo".replace(" ", "")
    xml = to_xml(name, desc, steps)
    with open(os.path.join(OUT, fname), "w", encoding="utf-8") as fh:
        fh.write(xml)
    ET.fromstring(xml.encode("utf-8"))
    tot = sum(dur(s) for s in steps) / 60
    if total_min:
        assert abs(tot - total_min) < 0.01, (fname, tot, total_min)
    catalog.append((wk_lbl, day, ds, fname, round(tot, 1), title))


def A(wk, m):
    """Optionale A-Einheit am Montag: Z2 durchgehend (vor dem Spinning am Dienstag, daher keine Intervalle)."""
    add(wk, "Mo", "A", f"{m}min_Z2", f"{m} min Z2",
        f"Optional. 10' Einfahren, {m - 15}' Z2 um {Z2} W (115-140 W), 5' Ausfahren. Ruhig rollen, am Dienstag ist Spinning.",
        [wu(10), FILL, cd(5, 120, 100)], m)


def AL(wk):
    """Entlastungswoche: 45 min ganz locker."""
    add(wk, "Mo", "A", "45min_locker", "45 min locker",
        "Entlastungswoche, optional. 45 min ganz locker, Z1-Z2 (100-130 W).",
        [wu(10, 100, 120), st(30 * 60, 115, None, "Ganz locker"), cd(5, 110, 100)], 45)


def TEST(wk):
    steps = [wu(15), st(60, 200, None, "Aktivierung 1/3: 200 W"), st(60, 110), st(60, 200, None, "Aktivierung 2/3: 200 W"),
             st(60, 110), st(60, 200, None, "Aktivierung 3/3: 200 W"), st(300, 110, None, "5 min locker vor dem Test"),
             ("free", 1200, "20-min-Test: gleichmaessig so hart wie moeglich. FTP = 95 % vom Schnitt"), cd(10)]
    add(wk, "Mo", "A", "FTP-Test", "FTP-Test (20 min)",
        "15' Einfahren, 3x1' @ 200 W mit 1' Pause @ 110 W, 5' locker @ 110 W, 20-min-Test ohne ERG, 10' Ausfahren. "
        "FTP = 95 % des 20-min-Schnitts. Alternativ den Ramp-Test in MyWhoosh nutzen.",
        steps)


def B(wk, title, slug, desc, steps, total):
    add(wk, "Sa", "B", slug, title, desc, steps, total, date_off=5)


# -------- Phase 1 (W1-6)
for wk in (1, 2, 3, 5, 6):
    A(wk, 60)
B(1, "60 min Z2", "60min_Z2", "60 min Z2, ca. 125 W.", [wu(10), FILL], 60)
B(2, "75 min Z2", "75min_Z2", "75 min Z2, ca. 125 W.", [wu(10), FILL], 75)
B(3, "80 min Z2", "80min_Z2", "80 min Z2, ca. 125 W.", [wu(10), FILL], 80)
B(4, "60 min, 2x8' @ 170 W", "60min_2x8min_170W", "Entlastungswoche. 10' Einfahren, 2x8' @ 170 W, Pause 5' @ 120 W, Rest Z2.",
  [wu(10)] + reps(2, 480, 170, 300, 120) + [FILL], 60)
B(5, "90 min Z2", "90min_Z2", "90 min Z2, ca. 125 W.", [wu(10), FILL], 90)
B(6, "90 min Z2, 4x5' @ 95-100 U/min", "90min_Z2_Kadenz",
  "10' Einfahren, 20' Z2, 4x5' @ 135 W bei 97 U/min, Pause 5' @ 110 W bei 85 U/min, Rest Z2.",
  [wu(10), z2(20)] + reps(4, 300, 135, 300, 110, 97, 85) + [FILL], 90)

# -------- Phase 2 (W7-12)
TEST(7)
B(7, "90 min Z2, 3x5' @ 154 W", "90min_3x5min_154W", "10' Einfahren, 20' Z2, 3x5' @ 154 W, Pause 5' @ 120 W, Rest Z2.",
  [wu(10), z2(20)] + reps(3, 300, 154, 300, 120) + [FILL], 90)
B(8, "70 min, 2x10' @ 170 W", "70min_2x10min_170W", "Entlastungswoche. 10' Einfahren, 2x10' @ 170 W, Pause 5' @ 120 W, Rest Z2.",
  [wu(10)] + reps(2, 600, 170, 300, 120) + [FILL], 70)
for wk in (9, 10, 11):
    A(wk, 70)
B(9, "90 min Z2, 3x5' @ 154 W", "90min_3x5min_154W", "10' Einfahren, 20' Z2, 3x5' @ 154 W, Pause 5' @ 120 W, Rest Z2.",
  [wu(10), z2(20)] + reps(3, 300, 154, 300, 120) + [FILL], 90)
B(10, "90 min, 2x15' @ 159 W", "90min_2x15min_159W", "15' Einfahren, 2x15' @ 159 W, Pause 5' @ 120 W, Rest Z2.",
  [wu(15)] + reps(2, 900, 159, 300, 120) + [FILL], 90)
B(11, "90 min Z2, 3x6' @ 157 W", "90min_3x6min_157W", "10' Einfahren, 20' Z2, 3x6' @ 157 W, Pause 5' @ 120 W, Rest Z2.",
  [wu(10), z2(20)] + reps(3, 360, 157, 300, 120) + [FILL], 90)
B(12, "75 min, 2x12' @ 174 W", "75min_2x12min_174W", "Entlastungswoche. 10' Einfahren, 2x12' @ 174 W, Pause 5' @ 120 W, Rest Z2.",
  [wu(10)] + reps(2, 720, 174, 300, 120) + [FILL], 75)

# -------- Phase 3 (W13-20)
TEST(13)
B(13, "90 min, 3x8' @ 180 W, 65 U/min", "90min_3x8min_180W_Kraft",
  "15' Einfahren, 3x8' @ 180 W bei 65 U/min, Pause 5' @ 120 W bei 90 U/min, Rest Z2.",
  [wu(15)] + reps(3, 480, 180, 300, 120, 65, 90) + [FILL], 90)
B(14, "90 min, 2x20' @ 160 W", "90min_2x20min_160W", "15' Einfahren, 2x20' @ 160 W, Pause 5' @ 120 W, Rest Z2.",
  [wu(15)] + reps(2, 1200, 160, 300, 120) + [FILL], 90)


for wk in (14, 15, 17, 18, 21, 22, 23):
    A(wk, 75)
B(15, "90 min, 3x10' @ 180 W, 65 U/min", "90min_3x10min_180W_Kraft",
  "15' Einfahren, 3x10' @ 180 W bei 65 U/min, Pause 5' @ 120 W bei 90 U/min, Rest Z2.",
  [wu(15)] + reps(3, 600, 180, 300, 120, 65, 90) + [FILL], 90)
B(16, "75 min, 2x10' @ 188 W", "75min_2x10min_188W", "Entlastungswoche. 10' Einfahren, 2x10' @ 188 W, Pause 5' @ 120 W, Rest Z2.",
  [wu(10)] + reps(2, 600, 188, 300, 120) + [FILL], 75)
B(17, "90 min, 4x10' @ 183 W, Kadenzwechsel", "90min_4x10min_183W_Kadenz",
  "15' Einfahren, 4x10' @ 183 W, Kadenz im Wechsel 65/90/65/90 U/min, Pause 4' @ 120 W, Rest Z2.",
  [wu(15)] + reps(4, 600, 183, 240, 120, [65, 90, 65, 90], None) + [FILL], 90)
B(18, "90 min, 3x12' @ 183 W", "90min_3x12min_183W", "15' Einfahren, 3x12' @ 183 W, Pause 5' @ 120 W, Rest Z2.",
  [wu(15)] + reps(3, 720, 183, 300, 120) + [FILL], 90)
TEST(19)
B(19, "90 min, 3x15' @ 175 W", "90min_3x15min_175W", "15' Einfahren, 3x15' @ 175 W (Sweet Spot), Pause 5' @ 120 W, Rest Z2.",
  [wu(15)] + reps(3, 900, 175, 300, 120) + [FILL], 90)
B(20, "75 min, 2x10' @ 190 W", "75min_2x10min_190W", "Entlastungswoche. 10' Einfahren, 2x10' @ 190 W, Pause 5' @ 120 W, Rest Z2.",
  [wu(10)] + reps(2, 600, 190, 300, 120) + [FILL], 75)

# -------- Phase 4 (W21-25)
B(21, "2 h Z2, 3x10' @ 174 W am Ende", "120min_3x10min_174W",
  "10' Einfahren, lange Z2-Phase, im letzten Drittel 3x10' @ 174 W, Pause 5' @ 120 W, 5' Ausfahren. Ausnahme-Einheit (2 h).",
  [wu(10), FILL] + reps(3, 600, 174, 300, 120) + [cd(5)], 120)
B(22, "2 h Z2, 3x12' @ 183 W", "120min_3x12min_183W",
  "10' Einfahren, 20' Z2, 3x12' @ 183 W, Pause 5' @ 120 W, Rest Z2. Ausnahme-Einheit (2 h), besser draussen.",
  [wu(10), z2(20)] + reps(3, 720, 183, 300, 120) + [FILL], 120)
B(24, "75 min, 3x5' @ 193 W", "75min_3x5min_193W", "Entlastungswoche. 10' Einfahren, 3x5' @ 193 W, Pause 4' @ 120 W, Rest Z2.",
  [wu(10)] + reps(3, 300, 193, 240, 120) + [FILL], 75)
# W25: Trainingslager draussen (So 18.4. - Fr 23.4.), keine Rollen-Dateien

# -------- Entlastungswochen: A ganz locker
for wk in (4, 8, 12, 16, 20, 24):
    AL(wk)

# -------- Taper (Woche 26)
add(26, "Mo", "Taper", "45min_3x3min_203W", "45 min, 3x3' @ 203 W, Pause 3' @ 110 W",
    "Taper. 10' Einfahren, 15' Z2, 3x3' @ 203 W, Pause 3' @ 110 W, 5' Ausfahren.",
    [wu(10), z2(15)] + reps(3, 180, 203, 180, 110) + [cd(5)], 45, 0)
add(26, "Mi", "Taper", "40min_3x1min_212W", "40 min, 3x1' @ 212 W, Pause 2' @ 110 W",
    "Taper. 10' Einfahren, Z2, 3x1' @ 212 W, Pause 2' @ 110 W, 5' Ausfahren.",
    [wu(10), FILL] + reps(3, 60, 212, 120, 110) + [cd(5)], 40, 2)
add(26, "Fr", "Taper", "30min_2x1min_203W", "30 min, 2x1' @ 203 W, Pause 2' @ 110 W",
    "Aktivierung vor dem Rennen. 10' Einfahren, Z2, 2x1' @ 203 W, Pause 2' @ 110 W, 5' Ausfahren.",
    [wu(10), FILL] + reps(2, 60, 203, 120, 110) + [cd(5)], 30, 4)

# -------- README + Katalog
cat_lines = ["Datei | Tag | Datum | Dauer min | Inhalt"]
for wk_lbl, day, ds, fname, tot, title in sorted(catalog, key=lambda r: (r[0] == "Taper", r[0], r[1] != "Mo")):
    cat_lines.append(f"{fname} | {day} | {ds} | {tot:g} | {title}")

readme = f"""MyWhoosh-Workouts fuer Eschborn-Frankfurt 2027
================================================

Alle Zielwerte sind in Prozent der FTP gespeichert (FTP {FTP} W = 100 %).
Setze deine FTP im MyWhoosh-Profil auf {FTP} W. Nach jedem FTP-Test (W7, W13, W19)
traegst du die neue FTP ein, dann passen sich alle Workouts automatisch an.

Import (Stand der Recherche, bitte mit einer Datei testen):
1. Im Browser den MyWhoosh Workout Builder / Workout-Editor oeffnen und einloggen.
2. .zwo-Datei hochladen/importieren, Vorschau pruefen (Dauer, Bloecke, Pausen).
3. Als Workout speichern bzw. "Export to MyWhoosh". Es erscheint im Ordner "MyWorkout".
   Falls es nicht auftaucht: MyWhoosh neu starten.
4. Im Workout laeuft der Kickr im ERG-Modus (Zielleistung wird vorgegeben).
   Der 20-min-FTP-Test ist als freie Fahrt (ohne ERG) angelegt.

Hinweise
- Pausen sind eigene Schritte mit Ziel-Watt (110 W nach A-Bloecken, 120 W in B).
- In W23 gibt es keine B-Datei: dort steht eine Ausfahrt draussen im Plan.
- In W25 gibt es keine Dateien: Trainingslager draussen (So 18.4. - Fr 23.4.).
- Plan startet am Montag 2.11.2026. Jede Woche: B (Samstag) fest, A (Montag, Z2) optional, Freitag Ruhetag.
  In Entlastungswochen ist A eine lockere 45-min-Einheit, in W7/W13/W19 der FTP-Test. W26 ist die Rennwoche mit drei kurzen Taper-Dateien.

Katalog
-------
""" + "\n".join(cat_lines) + "\n"
with open(os.path.join(OUT, "README.txt"), "w", encoding="utf-8") as fh:
    fh.write(readme)

zpath = os.path.join(BASE, "MyWhoosh_Workouts_Eschborn-Frankfurt.zip")
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    for fn in sorted(os.listdir(OUT)):
        z.write(os.path.join(OUT, fn), fn)

print(len(catalog), "workouts")
for r in sorted(catalog, key=lambda r: (r[0] == "Taper", r[0], r[1] != "Mo")):
    print(r)

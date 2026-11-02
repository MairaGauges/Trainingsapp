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
SOLO = 15  # ab Woche 15 (8.2.) gibt es kein Spinning und kein Schwimmen mehr: Di Rolle C, Do Rolle D
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
    """Optionale A-Einheit am Montag: Z2 durchgehend (vor den Intervallen am Dienstag, daher keine Intervalle)."""
    tue = "am Dienstag ist Spinning" if wk < SOLO else "am Dienstag kommt Rolle C mit Intervallen"
    add(wk, "Mo", "A", f"{m}min_Z2", f"{m} min Z2",
        f"Optional. 10' Einfahren, {m - 15}' Z2 um {Z2} W (115-140 W), 5' Ausfahren. Ruhig rollen, {tue}.",
        [wu(10), FILL, cd(5, 120, 100)], m)


def AL(wk):
    """Entlastungswoche: 45 min ganz locker."""
    add(wk, "Mo", "A", "45min_locker", "45 min locker",
        "Entlastungswoche, optional. 45 min ganz locker, Z1-Z2 (100-130 W).",
        [wu(10, 100, 120), st(30 * 60, 115, None, "Ganz locker"), cd(5, 110, 100)], 45)


def APRE(wk):
    """Montag vor einem FTP-Test: 45 min locker mit kurzen Öffnern, damit die Beine frisch sind."""
    add(wk, "Mo", "A", "45min_locker_Oeffner", "45 min locker, 3x1' Öffner",
        "Vor dem FTP-Test am Dienstag: 10' Einfahren, Z2 locker, 3x1' @ 175 W mit 2' Pause @ 110 W, 5' Ausfahren. Nicht mehr.",
        [wu(10), FILL] + reps(3, 60, 175, 120, 110) + [cd(5, 110, 100)], 45)


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


def C(wk, title, slug, desc, steps, total):
    """Dienstag ab W15: Intervalle auf der Rolle statt Spinning (kurz und hart, VO2max)."""
    add(wk, "Di", "C", slug, title, desc, steps, total, date_off=1)


def D(wk, deload=False):
    """Donnerstag ab W15, optional: locker statt Schwimmen, als aktive Erholung."""
    if deload:
        add(wk, "Do", "D", "40min_locker", "40 min ganz locker",
            "Optional, statt Schwimmen. 40 min ganz locker, Z1-Z2 (100-130 W), gern hohe Kadenz.",
            [wu(10, 100, 120), st(25 * 60, 115, 90, "Ganz locker"), cd(5, 110, 100)], 40, 3)
    else:
        add(wk, "Do", "D", "45min_locker_Kadenz", "45 min locker, 4x1' hohe Kadenz",
            "Optional, statt Schwimmen. 10' Einfahren, Z2, 4x1' @ 130 W bei 105 U/min, Pause 2' @ 115 W, 5' Ausfahren. Aktive Erholung, nicht hart.",
            [wu(10), FILL] + reps(4, 60, 130, 120, 115, 105, 90) + [cd(5)], 45, 3)


def overunder(n, hi, lo, pause):
    """n Blöcke à 6 min: 2' über, 1' unter der Schwelle, zweimal; dazwischen Pause."""
    out = []
    for i in range(n):
        for k in range(2):
            out.append(st(120, hi, None, f"Block {i+1}/{n}: {hi} W"))
            out.append(st(60, lo, None, f"Block {i+1}/{n}: {lo} W halten"))
        if i < n - 1:
            out.append(st(pause * 60, 110, None, f"Pause {pause} min locker, 110 W"))
    return out


def thirty(sets, n, on, off, rest):
    """sets x (n x 30" an / 30" locker), dazwischen rest Minuten."""
    out = []
    for s in range(sets):
        for i in range(n):
            out.append(st(30, on, None, f"Satz {s+1}/{sets}, {i+1}/{n}: {on} W"))
            if i < n - 1:
                out.append(st(30, off))
        if s < sets - 1:
            out.append(st(rest * 60, 110, None, f"Satzpause {rest} min locker"))
    return out


# -------- Phase 1 (W1-6)
for wk in (1, 3, 5, 6):
    A(wk, 60)
APRE(2)  # Dienstag W2: FTP-Test beim Spinning
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
# -------- Ab W15 (8.2.): kein Spinning, kein Schwimmen. Di Rolle C (Intervalle), Do Rolle D (optional locker)
C(15, "60 min, 5x3' @ 215 W", "60min_5x3min_215W", "15' Einfahren, 5x3' @ 215 W, Pause 3' @ 110 W, Rest Z2, 5' Ausfahren.",
  [wu(15)] + reps(5, 180, 215, 180, 110) + [FILL, cd(5)], 60)
C(16, "50 min, 3x3' @ 210 W", "50min_3x3min_210W", "Entlastungswoche. 15' Einfahren, 3x3' @ 210 W, Pause 3' @ 110 W, Rest Z2, 5' Ausfahren.",
  [wu(15)] + reps(3, 180, 210, 180, 110) + [FILL, cd(5)], 50)
C(17, "65 min, 5x4' @ 215 W", "65min_5x4min_215W", "15' Einfahren, 5x4' @ 215 W, Pause 4' @ 110 W, Rest Z2, 5' Ausfahren.",
  [wu(15)] + reps(5, 240, 215, 240, 110) + [FILL, cd(5)], 65)
C(18, "60 min, 3x 8x30/30 @ 270 W", "60min_3x8x30s_270W",
  "15' Einfahren, 3 Saetze 8x 30\" @ 270 W / 30\" @ 110 W, Satzpause 5' @ 110 W, Rest Z2, 5' Ausfahren.",
  [wu(15)] + thirty(3, 8, 270, 110, 5) + [FILL, cd(5)], 60)
C(19, "60 min Z2, 4x30\" Steigerung", "60min_Z2_Steigerungen",
  "Tag nach dem FTP-Test: 10' Einfahren, Z2, 4x30\" @ 230 W mit 90\" locker, 5' Ausfahren. Nicht mehr.",
  [wu(10), FILL] + reps(4, 30, 230, 90, 120) + [cd(5)], 60)
C(20, "50 min, 3x3' @ 215 W", "50min_3x3min_215W", "Entlastungswoche. 15' Einfahren, 3x3' @ 215 W, Pause 3' @ 110 W, Rest Z2, 5' Ausfahren.",
  [wu(15)] + reps(3, 180, 215, 180, 110) + [FILL, cd(5)], 50)
C(21, "70 min, 4x6' Over-Under 205/175 W", "70min_4x6min_OverUnder",
  "15' Einfahren, 4x6' im Wechsel 2' @ 205 W / 1' @ 175 W, Pause 4' @ 110 W, Rest Z2, 5' Ausfahren. Wie Tempowechsel am Anstieg.",
  [wu(15)] + overunder(4, 205, 175, 4) + [FILL, cd(5)], 70)
C(22, "70 min, 5x4' @ 220 W", "70min_5x4min_220W", "15' Einfahren, 5x4' @ 220 W, Pause 3' @ 110 W, Rest Z2, 5' Ausfahren.",
  [wu(15)] + reps(5, 240, 220, 180, 110) + [FILL, cd(5)], 70)
C(23, "65 min, 6x3' @ 220 W", "65min_6x3min_220W", "15' Einfahren, 6x3' @ 220 W, Pause 3' @ 110 W, Rest Z2, 5' Ausfahren.",
  [wu(15)] + reps(6, 180, 220, 180, 110) + [FILL, cd(5)], 65)
C(24, "50 min, 3x2' @ 215 W", "50min_3x2min_215W", "Entlastungswoche vor dem Trainingslager. 15' Einfahren, 3x2' @ 215 W, Pause 3' @ 110 W, Rest Z2, 5' Ausfahren.",
  [wu(15)] + reps(3, 120, 215, 180, 110) + [FILL, cd(5)], 50)
for wk in range(SOLO, 25):
    D(wk, deload=wk in (16, 20, 24))

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
- Ab W15 (8.2.) gibt es kein Spinning und kein Schwimmen mehr: Dienstag Rolle C (Intervalle), Donnerstag Rolle D (optional, locker).

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

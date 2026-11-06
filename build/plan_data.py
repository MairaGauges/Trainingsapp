"""Wochenplan: 26 Wochen ab 2.11.2026. Wird von build_plan.py (PDF) und build_dash.py (App) genutzt."""

import re


def kadenz(txt):
    """Kadenz-Empfehlung zu einer Radeinheit, aus der Beschreibung abgeleitet (höchste Zielleistung, Test, draußen)."""
    if "Kadenz" in txt:
        return ""
    if "FTP-Test" in txt or "FTP = " in txt:
        return "Kadenz: frei wählen, meist 90–100 U/min; im Test die Trittfrequenz, bei der du am gleichmäßigsten drückst."
    if "draußen" in txt or "Ausfahrt" in txt:
        return "Kadenz: in der Ebene 85–95 U/min, am Anstieg 70–85 U/min, früh runterschalten statt drücken."
    if "U/min" in txt:
        return "Kadenz sonst 85–95 U/min."
    w = [int(x) for x in re.findall(r"@ (\d{3}) ?W", txt)]
    hi = max([x for x in w if x > 125] or [0])
    if hi >= 250:
        return "Kadenz: 30-Sekunden-Stöße 100–110 U/min, sonst 85–95 U/min."
    if hi > 200:
        return "Kadenz: Intervalle 95–105 U/min (spart Kraft in den Beinen, fordert Herz und Lunge), Pausen und Z2 85–95 U/min."
    if hi > 145:
        return "Kadenz: 85–95 U/min, auch in den Blöcken."
    return "Kadenz: 85–95 U/min, rund und locker treten."


def mit_kadenz(txt):
    k = kadenz(txt)
    if not k:
        return txt
    txt = txt.rstrip()
    end = re.sub(r"<[^>]+>", "", txt).rstrip()
    return txt + ("" if end.endswith((".", "!", ")")) else ".") + " " + k


# ---------------------------------------------------------------- Wochen
# (Woche, Datum, Pflicht-Rolleneinheiten, A (optional), B, Typ)  Typ: "" | "d" (Entlastung) | "t" (FTP-Test)
TEST_A = ("<b>FTP-Test</b> (Ramp- oder 20-min-Test): 15' einfahren, 3×1' @ 200 W "
          "mit je <b>1' Pause</b> @ 110 W, <b>5' locker</b> @ 110 W, Test, "
          "10' ausfahren. Danach fragt die App nach der neuen FTP, trag sie auch in MyWhoosh ein.")

# Dienstag: Spinning-Kurs; ab Woche 15 (8.2.) Rolle C. Donnerstag ab Woche 15 Schwimmen nach eigenem Programm (SWIM)
# Rolle C (Dienstag, Intervalle statt Spinning) ab Woche 15
C_TXT = {
    15: "60 min: 15' einfahren, 5×3' @ 215 W, <b>Pause 3' @ 110 W</b>, Rest Z2.",
    16: "50 min: 15' einfahren, 3×3' @ 210 W, <b>Pause 3' @ 110 W</b>, Rest Z2.",
    17: "65 min: 15' einfahren, 5×4' @ 215 W, <b>Pause 4' @ 110 W</b>, Rest Z2.",
    18: "60 min: 15' einfahren, 3 Sätze 8× 30\" @ 270 W / 30\" @ 110 W, <b>Satzpause 5' @ 110 W</b>, Rest Z2.",
    19: "60 min Z2 mit 4×30\" @ 230 W, <b>dazwischen 90\" locker</b>. Tag nach dem FTP-Test, nicht mehr.",
    20: "50 min: 15' einfahren, 3×3' @ 215 W, <b>Pause 3' @ 110 W</b>, Rest Z2.",
    21: "70 min: 15' einfahren, 4×6' im Wechsel 2' @ 205 W / 1' @ 175 W, <b>Pause 4' @ 110 W</b>, Rest Z2. Übt Tempowechsel am Anstieg.",
    22: "70 min: 15' einfahren, 5×4' @ 220 W, <b>Pause 3' @ 110 W</b>, Rest Z2.",
    23: "65 min: 15' einfahren, 6×3' @ 220 W, <b>Pause 3' @ 110 W</b>, Rest Z2.",
    24: "50 min: 15' einfahren, 3×2' @ 215 W, <b>Pause 3' @ 110 W</b>, Rest Z2. Kurz vor dem Trainingslager.",
}
# Schwimmen (Kraul, wenn nicht anders genannt). ruhig = könntest lange so weiter, zügig = leicht außer Atem, schnell = deutlich außer Atem.
# P = Pause am Beckenrand. Technik: Abschlagschwimmen und einarmig im Wechsel. Pull = mit Pullbuoy, schont die Beine fürs Rad.
SWIM = {
    15: (2200, ["300 ein, locker gemischt", "4×50 Technik, P 20\"", "6×200 ruhig und gleichmäßig, P 30\"", "4×50 Pull zügig, P 20\"", "300 aus, locker"]),
    16: (2000, ["300 ein", "4×50 Technik, P 20\"", "10×100 ruhig, P 20\"", "200 Rücken oder Brust locker", "300 aus"]),
    17: (2300, ["400 ein", "4×50 Technik, P 20\"", "3×400 ruhig und gleichmäßig, P 45\"", "4×50 schnell, P 40\"", "300 aus"]),
    18: (2400, ["300 ein", "6×50 Technik, P 20\"", "Pyramide 100–200–300–400–300–200–100 zügig, P 20–40\" (je länger, desto mehr)", "200 aus"]),
    19: (2200, ["300 ein", "4×50 Technik, P 20\"", "12×100 zügig, P 15\"", "4×50 Pull locker", "300 aus"]),
    20: (2000, ["400 ein", "4×50 Technik, P 20\"", "4×200 ruhig, P 30\"", "4×50 Rücken locker", "400 aus"]),
    21: (2500, ["400 ein", "4×50 Technik, P 20\"", "2×800 ruhig und gleichmäßig, P 60\"", "300 aus"]),
    22: (2400, ["300 ein", "4×50 Technik, P 20\"", "5×300, die letzten 100 jeweils zügig, P 30\"", "4×50 Pull locker", "200 aus"]),
    23: (2200, ["300 ein", "4×50 Technik, P 20\"", "1000 durchgehend ruhig", "4×100 Pull ruhig, P 20\"", "300 aus"]),
    24: (2000, ["400 ein", "4×50 Technik, P 20\"", "8×100 ruhig, P 20\"", "4×50 Pull locker", "400 aus"]),
}
for _w, (_m, _l) in SWIM.items():  # Summe prüfen
    _s = 0
    for x in _l:
        m = re.match(r"(?:(\d+)×)?(\d+)", x)
        if x.startswith("Pyramide"):
            _s += 1600
        elif m:
            _s += int(m.group(1) or 1) * int(m.group(2))
    assert _s == _m, (_w, _s, _m)


def swim_txt(n, sep="<br>"):
    m, lines = SWIM[n]
    return "<b>%s km</b>: " % ("%.1f" % (m / 1000)).replace(".", ",") + sep.join(lines) + "."
DI = {2: "<b>Spinning · FTP-Test</b>: 20 min so gleichmäßig hart wie möglich",
      8: "Frei: kein Spinning. Mo 21.12. Intervalle im Gym (siehe links), Do 24.12. 45 min locker im Gym (optional), 25./26.12. frei",
      9: "Spinning. <b>So 3.1. Geburtstag: frei</b>, Kraft 2 entfällt"}

phases = []

phases.append(('Phase 1: Grundlage (2.11. – 13.12.)', [
    (1, '2.11.', 1, '60 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag ist Spinning.', '60 min Z2 (115–140 W) durchgehend', ''),
    (2, '9.11.', 1, "45 min locker mit 3×1' @ 175 W, <b>Pause 2' @ 110 W</b>: Beine frisch halten für den FTP-Test am Dienstag.", '75 min Z2 durchgehend', ''),
    (3, '16.11.', 1, '60 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag ist Spinning.', '80 min Z2 durchgehend', ''),
    (4, '23.11.', 1, '45 min ganz locker, Z1–Z2 (100–130 W). Optional.', "60 min: 10' einfahren, 2×8' @ 170 W, <b>Pause 5' @ 120 W</b>, Rest Z2", 'd'),
    (5, '30.11.', 1, '60 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag ist Spinning.', '90 min Z2 durchgehend', ''),
    (6, '7.12.', 1, '60 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag ist Spinning.', "90 min Z2 mit 4×5' bei 95–100 U/min, <b>Pause 5' locker</b> @ 110 W / 85 U/min", ''),
]))

phases.append(('Phase 2: Aufbau (14.12. – 24.1.)', [
    (7, '14.12.', 1, TEST_A, "90 min Z2 mit 3×5' @ 154 W, <b>Pause 5' @ 120 W</b>", 't'),
    (8, '21.12.', 1, "Im Gym statt Rolle B: 70 min, 10' einfahren, 2×10' @ 170 W, <b>Pause 5' @ 120 W</b>, Rest Z2", 'Frei (Weihnachten). Rolle B ist auf Montag gewandert.', 'd'),
    (9, '28.12.', 1, '70 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag ist Spinning.', "90 min Z2 mit 3×5' @ 154 W, <b>Pause 5' @ 120 W</b>", ''),
    (10, '4.1.', 1, '70 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag ist Spinning.', "90 min: 15' einfahren, 2×15' @ 159 W, <b>Pause 5' @ 120 W</b>, Rest Z2", ''),
    (11, '11.1.', 1, '70 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag ist Spinning.', "90 min Z2 mit 3×6' @ 157 W, <b>Pause 5' @ 120 W</b>", ''),
    (12, '18.1.', 1, '45 min ganz locker, Z1–Z2 (100–130 W). Optional.', "75 min: 10' einfahren, 2×12' @ 174 W, <b>Pause 5' @ 120 W</b>, Rest Z2", 'd'),
]))

phases.append(('Phase 3: Build (25.1. – 21.3.)', [
    (13, '25.1.', 1, TEST_A, "90 min: 15' einfahren, 3×8' @ 180 W bei 60–70 U/min, <b>Pause 5' @ 120 W</b> (90 U/min), Rest Z2", 't'),
    (14, '1.2.', 1, '75 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag ist Spinning.', "90 min: 15' einfahren, 2×20' @ 160 W, <b>Pause 5' @ 120 W</b>, Rest Z2", ''),
    (15, '8.2.', 1, '75 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag kommt Rolle C.', "90 min: 15' einfahren, 3×10' @ 180 W bei 60–70 U/min, <b>Pause 5' @ 120 W</b> (90 U/min), Rest Z2", ''),
    (16, '15.2.', 1, '45 min ganz locker, Z1–Z2 (100–130 W). Optional.', "75 min: 10' einfahren, 2×10' @ 188 W, <b>Pause 5' @ 120 W</b>, Rest Z2", 'd'),
    (17, '22.2.', 1, '75 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag kommt Rolle C.', "90 min: 15' einfahren, 4×10' @ 183 W (Kadenz im Wechsel 65 / 90 U/min), <b>Pause 4' @ 120 W</b>, Rest Z2", ''),
    (18, '1.3.', 1, '75 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag kommt Rolle C.', "90 min: 15' einfahren, 3×12' @ 183 W, <b>Pause 5' @ 120 W</b>, Rest Z2", ''),
    (19, '8.3.', 1, TEST_A, "90 min: 15' einfahren, 3×15' @ 175 W, <b>Pause 5' @ 120 W</b>, Rest Z2", 't'),
    (20, '15.3.', 1, '45 min ganz locker, Z1–Z2 (100–130 W). Optional.', "75 min: 10' einfahren, 2×10' @ 190 W, <b>Pause 5' @ 120 W</b>, Rest Z2", 'd'),
]))

phases.append(('Phase 4: Rennspezifisch (22.3. – 25.4.)', [
    (21, '22.3.', 1, '75 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag kommt Rolle C.', "2 h: Z2, im letzten Drittel 3×10' @ 174 W, <b>Pause 5' @ 120 W</b>", ''),
    (22, '29.3.', 1, '75 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag kommt Rolle C.', "2 h (besser draußen): 20' Z2, 3×12' @ 183 W, <b>Pause 5' @ 120 W</b>, Rest Z2", ''),
    (23, '5.4.', 1, '75 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag kommt Rolle C.', 'Ausfahrt draußen, ca. 2,5 h, möglichst mit Höhenmetern; Verpflegung 60–80 g KH/h', ''),
    (24, '12.4.', 1, '45 min ganz locker, Z1–Z2 (100–130 W). Optional.', "75 min: 10' einfahren, 3×5' @ 193 W, <b>Pause 4' @ 120 W</b>, Rest Z2", 'd'),
    (25, '19.4.', 1, "<b>Trainingslager</b> So 18.4. – Fr 23.4.: Mo 110 km Z2, Di Ruhetag, Mi 2,5–3 h mit Anstiegen im Renntempo, Do bis 80 km Z2, Fr locker", "Rückreise oder frei, keine Rolle", ''),
]))



# ---------------------------------------------------------------- Z2-Dauer (ab Woche 3)
# Progressive Steigerung um etwa 10 % pro Woche, jede 4. Woche Entlastung (rund 25–30 % kürzer).
# Rolle höchstens 2 h; Rolle A (Montag, optional) bis 90 min. Danach wächst der Reiz über die Blöcke in B
# und über längere Ausfahrten draußen.
A_MIN = {3: 65, 5: 70, 6: 75, 9: 75, 10: 80, 11: 85, 14: 90, 15: 90, 17: 90, 18: 90, 21: 90, 22: 90, 23: 75}
B_MIN = {3: 90, 5: 100, 6: 105, 7: 110, 9: 120, 10: 120, 11: 120, 12: 90, 13: 120, 14: 120, 15: 120, 16: 90,
         17: 120, 18: 120, 19: 120, 20: 90, 24: 80}


def _dauer(txt, m):
    new, n = re.subn(r"^\d+ min", "%d min" % m, txt, count=1)
    assert n == 1, txt
    return new


phases = [(title, [(w, d, n, _dauer(a, A_MIN[w]) if w in A_MIN else a, _dauer(b, B_MIN[w]) if w in B_MIN else b, typ)
                   for (w, d, n, a, b, typ) in rows]) for title, rows in phases]

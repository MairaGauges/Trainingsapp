"""Wochenplan: 26 Wochen ab 2.11.2026. Wird von build_plan.py (PDF) und build_dash.py (App) genutzt."""

# ---------------------------------------------------------------- Wochen
# (Woche, Datum, Pflicht-Rolleneinheiten, A (optional), B, Typ)  Typ: "" | "d" (Entlastung) | "t" (FTP-Test)
TEST_A = ("<b>FTP-Test</b> (Ramp- oder 20-min-Test): 15' einfahren, 3×1' @ 200 W "
          "mit je <b>1' Pause</b> @ 110 W, <b>5' locker</b> @ 110 W, Test, "
          "10' ausfahren. Danach Zonen neu berechnen.")

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
    (8, '21.12.', 1, '45 min ganz locker, Z1–Z2 (100–130 W). Optional.', "70 min: 10' einfahren, 2×10' @ 170 W, <b>Pause 5' @ 120 W</b>, Rest Z2", 'd'),
    (9, '28.12.', 1, '70 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag ist Spinning.', "90 min Z2 mit 3×5' @ 154 W, <b>Pause 5' @ 120 W</b>", ''),
    (10, '4.1.', 1, '70 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag ist Spinning.', "90 min: 15' einfahren, 2×15' @ 159 W, <b>Pause 5' @ 120 W</b>, Rest Z2", ''),
    (11, '11.1.', 1, '70 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag ist Spinning.', "90 min Z2 mit 3×6' @ 157 W, <b>Pause 5' @ 120 W</b>", ''),
    (12, '18.1.', 1, '45 min ganz locker, Z1–Z2 (100–130 W). Optional.', "75 min: 10' einfahren, 2×12' @ 174 W, <b>Pause 5' @ 120 W</b>, Rest Z2", 'd'),
]))

phases.append(('Phase 3: Build (25.1. – 21.3.)', [
    (13, '25.1.', 1, TEST_A, "90 min: 15' einfahren, 3×8' @ 180 W bei 60–70 U/min, <b>Pause 5' @ 120 W</b> (90 U/min), Rest Z2", 't'),
    (14, '1.2.', 1, '75 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag ist Spinning.', "90 min: 15' einfahren, 2×20' @ 160 W, <b>Pause 5' @ 120 W</b>, Rest Z2", ''),
    (15, '8.2.', 1, '75 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag ist Spinning.', "90 min: 15' einfahren, 3×10' @ 180 W bei 60–70 U/min, <b>Pause 5' @ 120 W</b> (90 U/min), Rest Z2", ''),
    (16, '15.2.', 1, '45 min ganz locker, Z1–Z2 (100–130 W). Optional.', "75 min: 10' einfahren, 2×10' @ 188 W, <b>Pause 5' @ 120 W</b>, Rest Z2", 'd'),
    (17, '22.2.', 1, '75 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag ist Spinning.', "90 min: 15' einfahren, 4×10' @ 183 W (Kadenz im Wechsel 65 / 90 U/min), <b>Pause 4' @ 120 W</b>, Rest Z2", ''),
    (18, '1.3.', 1, '75 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag ist Spinning.', "90 min: 15' einfahren, 3×12' @ 183 W, <b>Pause 5' @ 120 W</b>, Rest Z2", ''),
    (19, '8.3.', 1, TEST_A, "90 min: 15' einfahren, 3×15' @ 175 W, <b>Pause 5' @ 120 W</b>, Rest Z2", 't'),
    (20, '15.3.', 1, '45 min ganz locker, Z1–Z2 (100–130 W). Optional.', "75 min: 10' einfahren, 2×10' @ 190 W, <b>Pause 5' @ 120 W</b>, Rest Z2", 'd'),
]))

phases.append(('Phase 4: Rennspezifisch (22.3. – 25.4.)', [
    (21, '22.3.', 1, '75 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag ist Spinning.', "2 h (Ausnahme): Z2, im letzten Drittel 3×10' @ 174 W, <b>Pause 5' @ 120 W</b>", ''),
    (22, '29.3.', 1, '75 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag ist Spinning.', "2 h (besser draußen): 20' Z2, 3×12' @ 183 W, <b>Pause 5' @ 120 W</b>, Rest Z2", ''),
    (23, '5.4.', 1, '75 min Z2 (115–140 W) durchgehend, ruhig rollen. Optional; am Dienstag ist Spinning.', 'Ausfahrt draußen, ca. 2,5 h, möglichst mit Höhenmetern; Verpflegung 60–80 g KH/h', ''),
    (24, '12.4.', 1, '45 min ganz locker, Z1–Z2 (100–130 W). Optional.', "75 min: 10' einfahren, 3×5' @ 193 W, <b>Pause 4' @ 120 W</b>, Rest Z2", 'd'),
    (25, '19.4.', 1, "<b>Trainingslager</b> So 18.4. – Fr 23.4.: Mo 110 km Z2, Di Ruhetag, Mi 2,5–3 h mit Anstiegen im Renntempo, Do bis 80 km Z2, Fr locker", "Rückreise oder frei, keine Rolle", ''),
]))


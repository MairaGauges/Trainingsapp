from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak, KeepTogether)

import os
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "dist", "Trainingsplan_Eschborn-Frankfurt_2027.pdf")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

DARK = colors.HexColor("#1f2a44")
ACCENT = colors.HexColor("#d9480f")
LIGHT = colors.HexColor("#f1f3f7")
DELOAD = colors.HexColor("#e3f2e8")
TEST = colors.HexColor("#fff1d6")

base = ParagraphStyle("base", fontName="Helvetica", fontSize=8.6, leading=11)
small = ParagraphStyle("small", parent=base, fontSize=8, leading=10.2)
hdr = ParagraphStyle("hdr", parent=base, fontName="Helvetica-Bold",
                     textColor=colors.white)
h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=22, leading=27,
                    textColor=DARK, spaceAfter=4)
sub = ParagraphStyle("sub", fontName="Helvetica", fontSize=11, leading=15,
                     textColor=colors.HexColor("#555555"), spaceAfter=10)
h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=14, leading=18,
                    textColor=ACCENT, spaceBefore=4, spaceAfter=6)
body = ParagraphStyle("body", parent=base, fontSize=9.5, leading=13.5,
                      spaceAfter=3)


def P(t, s=base):
    return Paragraph(t, s)


def tbl(data, widths, extra=None, header=True):
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c5cad6")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), DARK)]
    if extra:
        st += extra
    t.setStyle(TableStyle(st))
    return t


from plan_data import phases, TEST_A  # noqa: E402

# ---------------------------------------------------------------- Story
story = []
story.append(P("Trainingsplan Eschborn-Frankfurt 2027", h1))
story.append(P("Radmarathon-Jedermann 92 km, ca. 1300 hm · Rennen am 1. Mai 2027 · "
               "Rolle (MyWhoosh, Wahoo Kickr Core) · FTP 193 W", sub))

story.append(P("Wochenstruktur", h2))
week = [[P(x, hdr) for x in ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]],
        [P(x, small) for x in [
            "Rolle <b>A</b> (Z2, optional)", "Spinning (Intervalle, 1 h)",
            "Kraft 1 (Beine, Ganzkörper)", "Schwimmen",
            "frei / 15 min Mobility",
            "Rolle <b>B</b> (lang, Z2 mit Tempoblöcken), danach 15 min Stabi",
            "Kraft 2 (Oberkörper, Rumpf)"]]]
story.append(tbl(week, [3.8*cm]*7))
story.append(Spacer(1, 6))
story.append(P("<b>Rhythmus:</b> Plan-Start ist Montag 2.11.2026, das Rennen am 1.5.2027 "
               "fällt in Woche 26. <b>Jede Woche</b> fährst du Spinning + Einheit <b>B</b> (Samstag). "
               "Einheit <b>A</b> (Montag, Z2) ist <b>optional</b>: fahr sie, wenn du dich frisch fühlst. "
               "Die Wochen 4, 8, 12, 16, 20 und 24 sind Entlastungswochen (B verkürzt, A nur "
               "45 min ganz locker).", body))

story.append(P("Zonen und Pausen", h2))
zones = [[P(x, hdr) for x in ["Zone", "% FTP", "Watt (FTP 193 W)"]],
         ["Z2 Grundlage", "56–75 %", "108–145 W"],
         ["Tempo", "76–87 %", "147–168 W"],
         ["Sweet Spot", "88–94 %", "170–181 W"],
         ["Schwelle", "95–105 %", "183–203 W"],
         ["VO2max", "106–120 %", "205–232 W"]]
zones = [zones[0]] + [[P(c, small) for c in r] for r in zones[1:]]
story.append(tbl(zones, [4*cm, 3*cm, 4.5*cm]))
story.append(Spacer(1, 6))
story.append(P("<b>Pausen:</b> Alle Pausen sind aktive Pausen, also weiterkurbeln bei lockeren "
               "110 W (nach Sweet-Spot- und Schwellenblöcken in A) bzw. 120 W (in den "
               "B-Einheiten), Kadenz frei und eher hoch (85–95 U/min). In ERG nicht pausieren, "
               "sondern das Ziel-Watt im Workout auf die Pausenleistung stellen. "
               "<b>Einfahren</b> immer 15 min (steigernd von 100 auf 145 W), "
               "<b>Ausfahren</b> 10 min @ 100–110 W.", body))
story.append(P("<b>FTP-Tests</b> in W7, W13 und W19 (Montag). Danach alle Wattwerte neu "
               "berechnen: Sweet Spot 88–94 %, Schwelle 95–105 %, VO2max 106–120 %, "
               "Z2 56–75 %.", body))
story.append(P("<b>Legende:</b> grün = Entlastungswoche (kürzer, A nur locker), "
               "gelb = FTP-Test. Z2 = 108–145 W, Pausen fett markiert.", body))

story.append(PageBreak())

cw = [1.2*cm, 1.6*cm, 1.2*cm, 10.9*cm, 10.9*cm]
for title, rows in phases:
    block = [P(title, h2)]
    data = [[P(x, hdr) for x in ["Wo.", "ab", "Pflicht", "Fr: Einheit A (optional)", "Sa: Einheit B"]]]
    extra = []
    for i, (w, d, n, a, b, typ) in enumerate(rows, start=1):
        data.append([P(f"<b>{w}</b>", small), P(d, small), P(str(n), small),
                     P(a, small), P(b, small)])
        if typ == "d":
            extra.append(("BACKGROUND", (0, i), (-1, i), DELOAD))
        elif typ == "t":
            extra.append(("BACKGROUND", (0, i), (-1, i), TEST))
        elif i % 2 == 0:
            extra.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
    block.append(tbl(data, cw, extra))
    story.append(KeepTogether(block))
    story.append(Spacer(1, 10))

# Taper
story.append(KeepTogether([
    P("Rennwoche / Taper (W26, 26.4. – 1.5.)", h2),
    tbl([[P(x, hdr) for x in ["Tag", "Einheit"]]] + [
        [P(a, small), P(b, small)] for a, b in [
            ("Mo 26.4.", "45 min Z2 mit 3×3' @ 203 W, <b>Pause 3' @ 110 W</b>"),
            ("Mi 28.4.", "40 min Z2 mit 3×1' @ 212 W, <b>Pause 2' @ 110 W</b>"),
            ("Fr 30.4.", "30 min locker mit 2×1' @ 203 W, <b>Pause 2' @ 110 W</b> (Aktivierung)"),
            ("Sa 1.5.", "<b>Rennen</b>"),
        ]],
        [3*cm, 20*cm]),
    Spacer(1, 4),
    P("Spinning in dieser Woche locker oder ganz auslassen. Keine Beinkraft mehr, "
      "höchstens 15 min Core und Mobility.", body),
]))

story.append(PageBreak())
story.append(P("Kraft, Schwimmen und Hinweise", h2))
kraft = [[P(x, hdr) for x in ["Phase", "Kraft 1 (Mi)", "Kraft 2 (So)"]]] + [
    [P(a, small), P(b, small), P(c, small)] for a, b, c in [
        ("1 (W1–6)", "Kniebeuge, Rumänisches Kreuzheben, Ausfallschritte, Hip Thrust: "
                     "3–4×6–10, moderat bis schwer. <b>Satzpause 90–120 s</b>",
         "Klimmzüge/Rudern, Liegestütz/Bankdrücken, Core, Single-Leg: 3×8–12. "
         "<b>Satzpause 60–90 s</b>"),
        ("2 (W7–12)", "wie Phase 1, Gewichte steigern, 3×5–8. <b>Satzpause 2–3 min</b>",
         "wie Phase 1, mehr Rumpf und Stabilität. <b>Satzpause 60–90 s</b>"),
        ("3 (W13–20)", "Erhalt: Kniebeuge und Kreuzheben 3×3–5 schwer, 1 explosive Übung. "
                       "<b>Satzpause 2–3 min</b>",
         "Oberkörper und Core, 2 Sätze pro Übung. <b>Satzpause 60 s</b>"),
        ("4 (W21–25)", "1 kurze Einheit, 2×3–5 schwer, keine Ermüdung. <b>Satzpause 2–3 min</b>",
         "optional streichen"),
        ("Taper (W26)", "keine Beinkraft, höchstens 15 min Core und Mobility", "–"),
    ]]
story.append(tbl(kraft, [3*cm, 11.5*cm, 11.5*cm]))
story.append(Spacer(1, 6))
story.append(P("In den Entlastungswochen: gleiche Gewichte, aber nur 2 statt 3–4 Sätze.", body))
story.append(P("Hinweise", h2))
for t in [
    "<b>Flexibel tauschen:</b> Wird eine Woche zu voll, lass die optionale Einheit A weg. Verschiebe lieber die Entlastungswoche nach vorn, statt sie zu streichen.",
    "<b>Draußen:</b> Ab März ersetzt eine Ausfahrt am Samstag möglichst die Rolle B. Vor dem "
    "1.5. solltest du mindestens zwei Ausfahrten über 2,5 h geschafft haben.",
    "<b>Verpflegung:</b> Bei langen Einheiten ab Phase 3 schon 60–80 g Kohlenhydrate pro "
    "Stunde üben, damit der Magen im Rennen mitmacht.",
    "<b>Rolle:</b> Ventilator und Handtuch sind Pflicht, sonst sinkt die Leistung spürbar.",
    "<b>Stabi nach Rolle B:</b> ca. 15 min Rumpf und Hüfte direkt nach der Fahrt (z. B. Unterarmstütz, Seitstütz, Bird Dog, Glute Bridge, Rückenstrecker). Übungen in der App anpassbar.",
    "<b>Müdigkeit:</b> Priorität haben Spinning und Einheit B. Zuerst Kraft 2 streichen, "
    "dann Einheit A, dann Kraft 1 kürzen.",
]:
    story.append(P("• " + t, body))


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#777777"))
    canvas.drawString(1.5*cm, 0.9*cm, "Trainingsplan Eschborn-Frankfurt 2027 · FTP 193 W")
    canvas.drawRightString(landscape(A4)[0] - 1.5*cm, 0.9*cm, f"Seite {doc.page}")
    canvas.restoreState()


doc = SimpleDocTemplate(OUT, pagesize=landscape(A4), leftMargin=1.5*cm,
                        rightMargin=1.5*cm, topMargin=1.4*cm, bottomMargin=1.6*cm,
                        title="Trainingsplan Eschborn-Frankfurt 2027",
                        author="Claude")
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("ok")

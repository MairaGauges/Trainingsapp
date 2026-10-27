# Eschborn-Frankfurt 2027: Trainings-Dashboard

Persönliche Trainings-App für den Radmarathon am 1.5.2027 (92 km, ca. 1.300 hm):
Wochenplan (Rolle B fest, Rolle A jede Woche optional), MyWhoosh-Workouts (.zwo), jede Einheit zum Abhaken,
Kraft- und Stabiplan (Stabi-Block nach Rolle B) mit Gewichten bzw. Zeiten, Garmin-Auswertung und Trainingsfortschritt (Fitness, Form, Leistung, Grundlagenausdauer).
Läuft auf Vercel mit Supabase als Speicher, alternativ auf dem eigenen Rechner oder Raspberry Pi; installierbar als App auf dem Handy (PWA).

## Was drin ist

| Pfad | Inhalt |
|---|---|
| `build/plan_data.py` | der Wochenplan (26 Wochen ab 2.11.2026, Texte und Pausen) |
| `build/build_zwo.py` | erzeugt die 52 `.zwo`-Workouts für MyWhoosh (ERG) nach `dist/` |
| `build/build_plan.py` | erzeugt den Plan als PDF (braucht `reportlab`) |
| `build/build_dash.py`, `build/template.html` | bauen die App `web/index.html` und die Artifact-Variante `dist/artifact.html` |
| `server/server.py` | kleiner Server (nur Standardbibliothek): App ausliefern, Daten speichern, Garmin abfragen |
| `server/garmin_client.py` | Garmin-Abruf, genutzt vom Server und von der Vercel-Funktion |
| `api/garmin.py`, `api/intervals.py`, `vercel.json` | Vercel: Build, Auslieferung von `web/`, Garmin und intervals.icu |
| `server/intervals_client.py`, `server/sb_auth.py` | intervals.icu-Abruf und Anmeldeprüfung der Vercel-Funktionen |
| `supabase/schema.sql` | Tabelle `docs` mit Zeilenschutz (einmal im SQL Editor ausführen) |
| `tools/import_supabase.py` | vorhandene Daten (`store.json`-Format) nach Supabase übernehmen |
| `web/` | `shim.js` (Speicher mit Offline-Warteschlange), `sw.js`, Manifest, Icons |
| `seed/store.example.json` | Beispiel-Kraftplan (einbeinig, Knie-Stabilität) |
| `tests/test_all.py` | Ende-zu-Ende-Test mit simulierter Garmin-Schnittstelle |

## Vercel + Supabase

Die App ist eine statische Seite. Mit Supabase-Variablen speichert `web/shim.js` direkt in Supabase
(Anmeldung mit E-Mail und Passwort), ohne Variablen beim eigenen Server. Einrichtung einmalig:

1. **Supabase, Tabelle:** SQL Editor → `supabase/schema.sql` einfügen → Run.
2. **Supabase, Konto:** Authentication → Users → „Add user“ (E-Mail, Passwort, „Auto Confirm“).
   Danach unter Authentication → Sign In / Providers **„Allow new users to sign up“ ausschalten**,
   damit sich niemand sonst ein Konto anlegt.
3. **Vercel:** Projekt aus dem GitHub-Repo importieren (Framework „Other“, alles Weitere steht in `vercel.json`).
   Umgebungsvariablen (Settings → Environment Variables), danach neu deployen:
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY` – setzt die Supabase-Integration von Vercel automatisch
     (`NEXT_PUBLIC_…`-Namen und der neue „publishable key“ gehen auch). **Nie** den `service_role`-Schlüssel nehmen.
   - `ALLOWED_EMAILS` – deine E-Mail; nur diese Konten dürfen Garmin abrufen.
   - optional `GARMIN_PERSONAL_API_KEY` – dann erscheint „Von Garmin laden“.
   - optional `INTERVALS_API_KEY` – dann erscheint „An MyWhoosh senden“ (siehe unten).
4. **Daten übernehmen** (optional): `SUPABASE_URL=… SUPABASE_ANON_KEY=… python3 tools/import_supabase.py data/store.json du@example.com`

Jedes Gerät meldet sich einmal an; die Sitzung bleibt gespeichert. „Abmelden“ steht unten im Tab Garmin
und löscht auch den Zwischenspeicher auf dem Gerät. Offline geht weiter wie oben beschrieben.

### Workouts direkt nach MyWhoosh (über intervals.icu)

MyWhoosh hat keine öffentliche Schnittstelle, übernimmt aber geplante Workouts aus intervals.icu.

1. intervals.icu-Konto anlegen und in MyWhoosh mit intervals.icu verbinden.
2. In intervals.icu unter Settings → Developer Settings einen API-Schlüssel erzeugen und in Vercel als
   `INTERVALS_API_KEY` eintragen, neu deployen.
3. In der App (Woche, rechts „Workouts für MyWhoosh“) einzelne Workouts oder die ganze Woche senden.
   Jede Einheit hat eine feste ID: nach Verschieben oder Anpassen zeigt die App „Neu senden“, und der
   Termin in intervals.icu wird ersetzt statt verdoppelt.

Grenzen (Berichte aus dem intervals.icu-Forum, 2025): MyWhoosh übernimmt nur die nächsten 7 Tage, und
Kadenz-Vorgaben (W06, W13, W15, W17 Sa) kommen eventuell nicht mit; diese dann als Datei importieren.

## Schnellstart (eigener Rechner)

```bash
make build        # Workouts + App bauen (nur Python 3, keine Pakete nötig)
make run          # http://127.0.0.1:8080
```

Daten liegen in `data/store.json` (nicht im Git). Eigene Daten übernehmen: Datei dorthin kopieren,
Server neu starten. Mit `seed/store.example.json` startest du mit dem Beispiel-Kraftplan.

## Garmin direkt laden

Garmin bietet seit Oktober 2026 einen persönlichen API-Schlüssel an (Connect-Web, Einstellungen,
Personal API Key). Den Schlüssel erzeugst du selbst, er gilt 30 Tage bis 1 Jahr und wird nur einmal angezeigt.

1. Schlüssel in `data/garmin_key` speichern (nur der Schlüssel, `chmod 600`) **oder** als
   `GARMIN_PERSONAL_API_KEY` in `.env` setzen. Beides ist per `.gitignore` ausgeschlossen.
2. Server neu starten. Im Tab „Garmin“ erscheint „Von Garmin laden · letzte 14 Tage“.
3. Der Server tauscht den Schlüssel gegen ein 24-h-Token, holt die Aktivitäten und die FIT-Dateien
   und gibt sie an die App. **Der Schlüssel verlässt den Server nie** und wird nicht geloggt.
   Mehrfaches Laden erzeugt keine Duplikate.

**Wichtig, ehrlich gesagt:** Die Endpunkte stammen aus Garmins Python-Client-README
(`/activitylist-service/activities/search/activities`, `/download-service/files/activity/{id}`).
Getestet ist die Logik nur gegen einen Mock, nicht gegen Garmin selbst. Wenn etwas hakt, zeigt
`/api/garmin/diag` (im Browser, eingeloggt) die Antwortform ohne Werte und ohne Schlüssel.
Der Dateiupload (FIT/TCX/GPX/ZIP) bleibt als Fallback.

## Zugriff vom Handy

- **Passwort ist Pflicht**, sobald der Server nicht nur auf `127.0.0.1` lauscht (`APP_PASSWORD`, Browser-Anmeldung).
  Ohne Passwort verweigert der Server den Start.
- Für „Zum Home-Bildschirm“ als echte App samt Offline-Gerüst braucht der Browser **HTTPS**.
  Am einfachsten über Tailscale: `tailscale serve --bg 8080` auf dem Rechner/Pi, dann die
  `https://…ts.net`-Adresse am Handy öffnen. Eine offene Portfreigabe ins Internet würde ich nicht machen.
- Offline: Eingaben (Gewichte, Haken) landen in einer Warteschlange im Handy und werden gesendet,
  sobald der Server wieder erreichbar ist. Bei gleichzeitiger Änderung an zwei Geräten gewinnt die letzte.

## Docker / Raspberry Pi

```bash
cp .env.example .env     # APP_PASSWORD setzen, optional GARMIN_PERSONAL_API_KEY
docker compose up -d --build
```

## Plan ändern

`build/plan_data.py` (Texte, PDF und App) und `build/build_zwo.py` (Workout-Dateien) anpassen,
dann `make build` (und `make pdf`). Die Watt-Werte in den `.zwo`-Dateien sind Prozent der FTP;
nach einem FTP-Test den neuen Wert in MyWhoosh eintragen, die Dateien bleiben gleich.

## Als claude.ai-Artifact

`dist/artifact.html` ist dieselbe Seite ohne Server, sie nutzt dort die Datenbank- und
Download-Funktion des Artifacts. Der Garmin-Knopf erscheint nur mit eigenem Server.

## Tests

```bash
pip install playwright && playwright install chromium
make test
```

## Sicherheit in Kürze

- Schlüssel und Passwörter nie einchecken, nie in Chats oder Issues posten. Bei Verdacht den Garmin-Schlüssel in Connect löschen.
- Der Server hat keine Benutzerverwaltung: ein Passwort, ein Nutzer. Er ist für den privaten Gebrauch gedacht.
- Garmins Bedingungen: Die Personal API ist für den Eigengebrauch gedacht.

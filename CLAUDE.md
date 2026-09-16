# CLAUDE.md

Kurzbriefing für Claude Code. Ausführliche Doku: `README.md` (36 KB, nur bei
Bedarf gezielt lesen).

## Was das ist

Statische Webseite mit einer filterbaren Liste von Ausdauersport-Events
(Laufen, Schwimmen, Fahrrad, Triathlon) in Deutschland, Österreich und der
Schweiz. Läuft auf GitHub Pages, kein Build-Schritt, kein Framework.
Datenbasis ist `events.json`, gefüllt von Python-Scrapern.

## Entwicklungs-Branch

Alle Arbeit auf **`claude/endurance-events-website-v1wruf`** (PR #1).
Nicht auf einen anderen Branch pushen.

## Dateien

| Datei | Zweck |
|---|---|
| `events.json` | die Daten (**~450 KB**, wächst mit jedem Lauf) |
| `index.html` | Startseite (statisch, kein Kartenlink – bewusst entfernt) |
| `events.html` | die Liste; Tabelle mit 7 Spalten, Filter pro Spalte |
| `karte.html` | Leaflet-Karte, ein Marker pro Standort |
| `auth.js`, `firebase-config.js`, `firestore.rules`, `functions/` | Login + „Benachrichtige mich" |
| `scripts/scraper_lib.py` | gemeinsame Engine (robots.txt, Parsing, Dedupe, Geocoding, CLI) |
| `scripts/*_scraper.py` | ein Skript pro Quelle |
| `scripts/clean_events.py` | räumt bestehende `events.json` nach allen Regeln auf, idempotent |
| `scripts/update_events.py` | führt alle Scraper + Aufräumen aus (nutzt der Workflow) |
| `scripts/manual_overrides.json` | einzeln recherchierte Korrekturen |
| `scripts/review_reports.py` | Nutzer-Fehlermeldungen bündeln → Vorschlag → Bestätigung |
| `scripts/pending_overrides.json` | Vorschläge, die auf die Bestätigung des Nutzers warten |
| `scripts/test_scraper_lib.py` | Regressionstests, ohne Netzwerk |

**`events.json` NIE komplett lesen** – das frisst den halben Kontext. Immer
gezielt abfragen:

```bash
python3 -c "import json; ev=json.load(open('events.json')); print(len(ev))"
```

## Vor jedem Commit

```bash
python3 scripts/test_scraper_lib.py     # muss grün sein
```

Bei Änderungen an `events.html`/`index.html`/`karte.html` zusätzlich die
Inline-Skripte syntaktisch prüfen (`node --check`) und, wenn sinnvoll, einen
Playwright-Smoke-Test. Chromium liegt unter
`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`; in dieser Sandbox
blockt der Proxy CDNs per TLS – mit `args=['--ignore-certificate-errors']`
laden Leaflet und Firebase.

## Datenregeln (hart erkämpft – nicht aufweichen)

1. **Jede Strecke ein eigener Eintrag.** Veranstaltungen bieten mehrere
   Wettbewerbe an; jeder wird eine Zeile mit eigener `laenge_km` und eigenem
   `wettbewerb`-Label. Der Veranstaltungs-*name* bleibt identisch (er ist Teil
   des Duplikat-Schlüssels). Siehe `parse_competitions()`/`expand_competitions()`.
2. **`veranstalter_url` = offizielle Seite des Laufs**, nie das Kalenderportal.
   Ein gespeicherter Portallink wird ersetzt, sobald die offizielle bekannt ist,
   auch quellenübergreifend (`update_existing_event()`, `PORTAL_DOMAINS`).
   Geraten wird nie.
3. **Distanzen immer auf eine Dezimalstelle** (`round_km()`): 42,195 → 42.2.
4. **`land` nie aus dem Event-Namen raten.** Der „Fränkische-Schweiz-Marathon"
   liegt in Bayern. Quelle: Landesangabe der Seite (`(Schweiz)`, `(AUT)`) oder
   Reverse-Geocoding der Koordinaten.
5. **5-km-Mindestdistanz nur für `art1 == "Laufen"`** und nur bei *bekannter*
   Distanz. 3,5 km Freiwasserschwimmen ist eine ernsthafte Distanz.
6. **`art2`: spezifisch vor generisch.** „Straße"/Marathon steht in
   `ART2_KEYWORDS_LAUFEN` bewusst ZULETZT, sonst wird ein „Bergtrail
   Trail-Marathon" zum Straßenlauf. Zusätzlich: ab 20 Höhenmetern pro km gilt
   eine Strecke als Berglauf (`art2_from_elevation()`).
7. **Duplikate**: gleiches Datum + ähnlicher Name + Ort ≤ 30 km + kompatible
   Distanz (`is_same_event()`). Gleiche Veranstaltung mit *unterschiedlichen*
   Distanzen bleibt absichtlich getrennt.
8. **Vergangene Events raus.** Maßgeblich ist `datum_ende` (sonst
   `datum_start`); der heutige Tag bleibt, ein mehrtägiges Rennen bleibt bis
   zu seinem letzten Tag, ein Event mit unlesbarem Datum wird nicht
   gelöscht. An drei Stellen: `scraper_lib.filter_past()` beim Einsammeln,
   `clean_events.drop_past_events()` rückwirkend, und `dropPastEvents()`
   beim Laden in `events.html`/`karte.html` (zwischen zwei Läufen liegt
   eine Woche).

### Die wichtigste Lektion

**Keine automatische Löschregel auf Heuristik-Basis.** Eine Regel, die
widersprüchliche Distanzen automatisch entfernen sollte, traf bei 7 Fällen
2 echte Rennen (Halbmarathon des NRZ Klosterlauf, 42-km-Strecke der Mud
Masters) – die Streckenlisten der Quellen sind nicht verlässlich vollständig.
Solche Fälle daher nur **melden** (`report_suspicious_distances()`), einzeln
per Websuche prüfen und bestätigte Fehler mit `"exclude": true` in
`manual_overrides.json` eintragen. Schlüssel dort:
`"<Name>|<Datum>|<km>"` (distanzgenau) oder `"<Name>|<Datum>"`.

Zu viel gelöscht ist schlimmer als eine Zahl zu großzügig – es ist unsichtbar.

### Nutzer-Fehlermeldungen

In `events.html` gibt es pro Event „Fehler zu diesem Event melden"
(Drop-down + Freitext → Firestore-Collection `errorReports`, anonyme
Anmeldung). Die Meldungen werden **nie automatisch** übernommen:

```bash
python3 scripts/review_reports.py fetch --credentials <serviceaccount.json>
python3 scripts/review_reports.py show          # gebündelt, häufigste zuerst
python3 scripts/review_reports.py propose --key "<Name>|<Datum>|<km>" \
        --set laenge_km=12,4 --grund "…" --quelle "…"
python3 scripts/review_reports.py confirm       # fragt den Nutzer, j/n
```

Der Vorschlag bleibt bis zur Bestätigung in `pending_overrides.json`;
erst `confirm` schreibt ihn nach `manual_overrides.json`. Also: Meldungen
ansehen, jede einzeln per Websuche gegen die offizielle Ausschreibung
prüfen, Vorschlag anlegen, **vom Nutzer bestätigen lassen** – nicht
selbst durchwinken. Details im README („Fehler zu diesem Event melden").

## Frontend-Fallen (events.html)

- **`refreshOpenPanel()` zeichnet das offene Filter-Panel nicht neu,
  solange der Fokus darin liegt** (damit eine Eingabe im Namensfeld nicht
  abreißt). Jeder Button *im* Panel, der den Filterzustand ändert, muss
  daher vor `render()` den Fokus abgeben – siehe `geoBtn.blur()` beim
  Standort-Button; ohne das sah „Aktuellen Standort verwenden" kaputt aus
  (Status blieb „wird ermittelt…", Radius-Auswahl ausgegraut).
- **Chips nie pro Wert aufzählen.** Mengen-Filter fassen sich zusammen:
  alles ausgewählt → „Stadt/Ort: Alle", mehr als `MAX_VALUE_CHIPS` (5) →
  „Stadt/Ort: 12 ausgewählt". „Alle" bei Stadt/Ort sind ~2000 Orte.
- **Reihenfolge im Skript beachten**: `const`-Tabellen (z. B.
  `CANONICAL_RACE_NAMES`) müssen VOR ihrer ersten Verwendung stehen –
  sonst Temporal-Dead-Zone-Fehler.
- **Texte immer in DE und EN** (`I18N`-Objekte, oben in der Datei).

## Quellen

Acht geprüft, **vier aktiv**: laufen.de (`laufkalender_scraper.py`,
größte Quelle), running.life, runningcompany.de, planet-marathon.de.

**Vier übersprungen** – die Skripte brechen selbst mit `sys.exit(0)` ab und
rufen die Seite *nicht* ab. Diese Entscheidungen nicht ohne Rückfrage
umdrehen:

- `ironman_scraper.py` – robots.txt verbietet ClaudeBot ausdrücklich
- `runnersworld_scraper.py` – Nutzungsbedingungen verbieten automatisiertes Auslesen
- `ahotu_scraper.py` – Cloudflare-Sperre (403); kein Umgehen
- `blvsport_scraper.py` – auf Wunsch des Nutzers wegen Datenqualität (liefert
  weder Distanz noch Link); die recherchierten Events bleiben über
  `manual_overrides.json` erhalten

laufen.de und running.life rufen **zusätzlich die Detailseite jedes Events**
ab – nur dort stehen die einzelnen Wettbewerbe, das Land und die offizielle
Seite. `--no-details` schaltet es ab, `--max-details N` begrenzt es für
Testläufe.

**Ein vollständiger Lauf dauert ~2 Stunden** (running.life schöpft mit
`--max-pages 110` den ganzen Kalender aus, ~2020 Detailseiten mit 2 s
Pause; dazu laufen.de mit ~750). Deshalb niemals im Chat abwarten – den
Workflow auslösen und später nachsehen. Für Tests immer
`--max-pages 2 --no-details` o. Ä.

## Automatik

`.github/workflows/update-events.yml` läuft **wöchentlich montags 5:00 UTC**
(vorher täglich – solange die Seite nicht live ist, bringt ein täglicher
Lauf nur Laufzeit und große events.json-Diffs): alle Scraper, dann
`clean_events.py`, dann Commit auf den Branch. Für einen Datenlauf ist
also **keine Claude-Session nötig** – Workflow manuell auslösen reicht
(Actions → „Events automatisch aktualisieren" → Run workflow).

## Wo das Projekt gerade steht

Die Seite ist **noch nicht live**. Gearbeitet wird derzeit an der Webseite
selbst, nicht an den Daten – also sparsam mit Tokens umgehen: keine
Scraper-Läufe „zur Kontrolle", `events.json` nicht lesen, für Daten-
Änderungen den Workflow auslösen statt im Chat zu warten.

**Geplant zum Schluss**: Der Nutzer liefert eine größere Menge Links, aus
denen dann alle Events herausgesucht werden – erwartet werden **über
20.000 Events**. Das ist der Moment für einen großen Datenlauf; bis dahin
ist der Datenstand (~4.100) bewusst nur Arbeitsmaterial.

## Offene Punkte / To-dos

- **E-Mail-Versand für „Benachrichtige mich" braucht Blaze** – vom Nutzer
  bewusst zurückgestellt. Login und Firestore laufen (Projekt
  `endurance-5177a`, Spark-Tarif), Abos landen korrekt in
  `filterSubscriptions`. Es fehlen nur die zwei Blaze-Schritte: Cloud
  Function `checkNewEvents` deployen und die Extension „Trigger Email"
  plus SMTP einrichten.
  **Code-seitig ist alles vorbereitet**: `firebase.json` und `.firebaserc`
  liegen im Repo (`firebase init` also nicht nötig), das Shared Secret
  läuft über `defineSecret`, und ohne gesetztes `NOTIFY_WEBHOOK_SECRET`
  antwortet die Function mit 503 statt offen zu stehen. Deploy-Befehle im
  Kopf von `functions/index.js` und im README.
  Vorhandene Abos bleiben mit `notified: false` gültig, werden aber
  **nicht rückwirkend** gegen die schon vorhandenen Events geprüft – die
  Function sieht nur, was `update_events.py` ihr als neu meldet.
- **Apple-Login**: per `SHOW_APPLE_SIGNIN = false` in `auth.js`
  ausgeblendet. Vom Nutzer **bewusst zurückgestellt** – Apple verlangt
  99 $ im Jahr, und das Projekt soll vorerst ohne laufende Kosten
  auskommen. Nicht ohne Rückfrage angehen.
  Zu beachten: `true` allein reicht nicht, es gibt nur die Hülle
  (Button-Markup, fest `disabled`, ohne Klick-Behandlung). Eine
  `signInWithApple()` existiert **nicht** – der Kommentar dort
  behauptete das früher. Was tatsächlich nötig wäre, steht jetzt im
  Kommentar bei `SHOW_APPLE_SIGNIN` und im README.
- ~~Popup-Fallback für den Google-Login~~ **erledigt**: `signInWithPopup`
  schaltet bei blockiertem Popup auf `signInWithRedirect` um,
  `handleRedirectResult()` wertet die Rückkehr aus. In-App-Browser
  (Instagram etc.) bleiben ein Sonderfall – dort blockt der
  Speicherschutz auch die Weiterleitung; der Nutzer bekommt dann im
  Klartext den Hinweis, die Seite im normalen Browser zu öffnen. Details
  im README („Google-Login: Popup, Weiterleitung, In-App-Browser").
- **Anbieter „Anonym" in Firebase aktivieren** (Sicherheit →
  Authentication → Sign-in method → Neuer Anbieter → Native Anbieter).
  Am 16.09.2026 gegen das echte Projekt geprüft: noch **nicht aktiv**,
  `signInAnonymously()` antwortet mit `auth/admin-restricted-operation`
  (nicht `auth/operation-not-allowed`, wie hier früher stand – das
  Formular fängt beide Codes ab und sagt es im Klartext). Bis dahin
  funktioniert „Fehler zu diesem Event melden" nicht.
  Außerdem die erweiterten `firestore.rules` (Collection `errorReports`)
  veröffentlichen – seit `firebase.json` im Repo liegt, geht das ohne
  Copy-Paste per `firebase deploy --only firestore:rules`, auch im
  Spark-Tarif.
- **5 Seed-Links** – recherchiert (Stand 09/2026), warten auf die
  Entscheidung des Nutzers, nichts davon ist eingetragen:
  1. *Bodensee-Schwimmen*: findet statt, aber der Name ist mehrdeutig.
     „Bodensee Openwater" (bodensee-openwater.com) hat 2027 drei Termine
     (Konstanz 26.06., 5/10 km; Friedrichshafen 31.07., 11 km;
     Wallhausen 28.08., 2,5/5 km); daneben gibt es die eigenständige
     „Bodenseequerung" (bodenseequerung.de). Welche gemeint war, ist
     offen.
  2. *Engadin Bike Giro*: **eingestellt**. Letzte (8.) Austragung 2023,
     abgesagt bei nur ~200 Teilnehmenden. Eine „mögliche Wiederbelebung
     2025" wurde angekündigt, aber nie umgesetzt; die offizielle Seite
     antwortet nur noch mit HTTP 503.
  3. *Basel Marathon*: **eingestellt seit 2018** (IWB Basel Marathon,
     wirtschaftliche Gründe, der Kanton strich 80.000 CHF Swisslos-
     Förderung). **Achtung**: In `events.json` steht trotzdem ein
     Eintrag „Basel Marathon | 2027-05-09 | 42,2 km" mit
     `veranstalter_url` `basel-marathon.ch` – die Domain löst nicht mehr
     auf. Kandidat für `"exclude": true`, aber erst nach Bestätigung.
     In Basel gibt es stattdessen den 3Länderlauf (Marathon/HM/10 km,
     Mai, Start Marktplatz) und den Basler Stadtlauf (5,5 km, November).
  4. *Silvesterlauf Salzburg*: Der Salzburger Silvesterlauf in der Stadt
     (1998–2000, 2002–2004) ist **eingestellt**. Im Bundesland gibt es
     den Leimüller Silvesterlauf in Seekirchen am Wallersee, jährlich am
     31.12. (leimueller-silvesterlauf.at), Distanzen nicht erhoben.
  5. *Swiss Athletics Bahnmeeting*: kein einzelnes Event, sondern der
     Wettkampfkalender von Swiss Athletics. Bahnmeetings sind
     Leichtathletik-Stadionwettkämpfe inklusive Sprint, Wurf und Sprung
     – das passt nur teilweise zum Ausdauersport-Zuschnitt der Seite.
     Grundsatzentscheidung, keine Recherchefrage.

## Sprache

Code-Kommentare, Docstrings, README, Commit-Messages und Antworten an den
Nutzer: **Deutsch**. Die Webseite ist zweisprachig (DE/EN) über `I18N`-Objekte
in den HTML-Dateien – Textänderungen immer in *beiden* Sprachen.

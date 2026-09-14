# Enduranceevents

Öffentliche Webseite mit einer gefilterten Liste von Ausdauersport-Events
(Laufen, Schwimmen, Fahrrad, Triathlon) in Deutschland, Österreich und der
Schweiz.

## Struktur

- `events.json` – Datenquelle mit den Beispiel-Events. Felder pro Event:
  - `land` – Deutschland / Österreich / Schweiz
  - `name` – Name des Events
  - `standort` – Ort des Events
  - `lat` / `lon` – Koordinaten des Standorts (Dezimalgrad), werden für die
    Umkreissuche benötigt
  - `art1` – Laufen / Schwimmen / Fahrrad / Triathlon
  - `art2` – Unterkategorie, abhängig von `art1` (siehe `ART2_BY_ART1` unten)
  - `datum_start` / `datum_ende` – Datum im Format `YYYY-MM-DD`
  - `anmeldeschluss` – Anmeldeschluss-Datum im Format `YYYY-MM-DD` (optional;
    fehlt es bei einem Event, zeigt die Tabelle dort „–")
  - `laenge_km` – Streckenlänge in Kilometern
  - `veranstalter_url` – Link zur Veranstalter-Website

  **Neues Event ergänzen**: Ort per Kartendienst (z. B. Google Maps – Rechtsklick
  auf den Punkt zeigt die Koordinaten) nachschlagen und als `lat`/`lon` eintragen,
  sonst funktioniert die Umkreissuche für dieses Event nicht.

- `index.html` – Willkommensseite (Hero mit Slogan, Sportart-Kacheln,
  Kennzahlen-Leiste). Rein statisch, keine Datenabhängigkeit. Die
  Hero-Grafik (Verlauf, Konturlinien, gestrichelte Streckenroute mit
  Ziel-Pin und weißen Lauf-/Rad-/Schwimm-Linien-Icons auf der Route,
  im selben Stil wie die Icons der Sportart-Kacheln) ist selbst
  gebautes Inline-SVG statt eines Fotos – in dieser Umgebung sind
  externe Bild-CDNs (Unsplash, Wikimedia, Pexels, …) netzwerkseitig
  blockiert, daher kein Hotlinking/Download echter Fotos möglich. Die
  „Events entdecken"-Buttons verlinken auf `events.html`
  ohne Filter; jede Sportart-Kachel verlinkt mit
  `events.html?sportart=<Sportart>` (z. B. `?sportart=Fahrrad`) – die
  Liste liest diesen Parameter beim Laden aus und selektiert den
  Sportart-Filter direkt. Zweisprachig (DE/EN) über denselben
  `localStorage`-Schlüssel wie `events.html`, sodass die Sprachwahl beim
  Wechsel zur Liste erhalten bleibt.
- `events.html` – die eigentliche, filterbare Event-Liste. Kopfbereich im
  selben Verlauf-Design wie die Willkommensseite (Tabelle, Schriftart und
  Ausrichtung unverändert – nur die Optik von Kopfbereich und Buttons ist
  angeglichen); oben rechts ein „Startseite"-Button zurück zu
  `index.html`. Liest `events.json` per `fetch` ein. Excel-ähnliche
  Tabelle in dieser Spaltenreihenfolge, jede
  Spalte hat einen eigenen Filter im Spaltenkopf
  (▾-Symbol):
  1. **Name** – Textsuche (Eingabefeld, filtert live während des Tippens)
  2. **Datum** – aufklappbarer Baum Jahr → Monat → Tag (wie Excels
     Datums-AutoFilter); ein Jahr oder Monat auswählen selektiert
     automatisch alle enthaltenen Tage, einzelne Tage sind ebenfalls wählbar
  3. **Anmeldung** – Checkbox-Filter „Offen" / „Geschlossen": wird aus
     `anmeldeschluss` und dem heutigen Datum berechnet (Anmeldeschluss in
     der Zukunft = Offen, in der Vergangenheit = Geschlossen). Das konkrete
     Anmeldeschluss-Datum selbst wird nicht in der Tabelle angezeigt,
     sondern nur in der Detailansicht beim Klick auf ein Event.
  4. **Land** – Checkbox-Liste
  5. **Stadt/Ort** – Checkbox-Liste mit *allen* Städten (unabhängig von
     anderen Filtern) plus Umkreissuche: „Aktuellen Standort verwenden"
     (Browser-Geolocation) oder eine Stadt als Ausgangspunkt wählen, dann
     Radius 0–5 / 5–20 / 20–50 / 50+ km wählen
  6. **Sportart** – Checkbox-Liste (Laufen/Schwimmen/Fahrrad/Triathlon)
  7. **Kategorie** – Checkbox-Liste, deren Optionen von der Sportart-Auswahl
     abhängen. Zuordnung (als `ART2_BY_ART1` oben im `<script>`-Block in
     `events.html`, dort anpassbar):
     - *Laufen*: Straße, Trail, Bahn, Berg, Cross, Hindernis
     - *Schwimmen*: Freiwasser, Becken
     - *Fahrrad*: Straße, Zeitfahren, Mountainbike, Gravel, Bahn, Cyclecross
     - *Triathlon* hat keine Kategorie-Unterteilung.
  8. **Länge** – Sportart-Tabs (Laufen/Fahrrad/Schwimmen/Triathlon) mit
     sportartspezifischen Distanz-Schnellauswahlen plus dem allgemeinen
     Zahlenbereich von/bis (siehe unten); die Einheit „km" steht bereits in
     jeder Zelle, daher nur „Länge" als Spaltenname

  Die Spaltenbreiten sind fix zugeteilt (Name breiter, Länge schmaler) statt
  gleich verteilt, über `nth-child`-Selektoren im `<style>`-Block von
  `events.html`, dort bei Bedarf anpassbar. `body` hat `min-height: 100vh`,
  damit der Seitenhintergrund immer bis zum unteren Bildschirmrand reicht,
  auch wenn die Tabelle (z. B. bei wenigen Events oder auf sehr hohen
  Bildschirmen) nicht die volle Höhe ausfüllt.

  Aktive Filter erscheinen als Chips direkt neben der Ergebnisanzahl links
  oben (einzeln entfernbar), „Alle Filter zurücksetzen" löscht alles auf
  einmal. Klick auf eine Zeile zeigt rechts die Detailansicht.

  **Zweisprachig (DE/EN)**: Umschalter oben rechts, geteilt mit
  `index.html` über denselben `localStorage`-Schlüssel. Übersetzt werden
  alle UI-Texte sowie die Werte für Land/Sportart/Kategorie (z. B.
  „Laufen" ↔ „Running"); Event-Namen, Städte und Veranstalter-Links
  bleiben unverändert. Die Übersetzungstabellen (`I18N`,
  `VALUE_TRANSLATIONS`) stehen oben im `<script>`-Block in `events.html`
  – dort auch anpassbar/erweiterbar.

  **Distanz-Schnellauswahl bei „Länge"**: Die Sportart-Tabs im Länge-Filter
  folgen dem Sportart-Filter: ist dort z. B. nur „Laufen" ausgewählt, zeigt
  „Länge" direkt (ohne Tabs) nur die Laufen-Kategorien; bei mehreren gewählten
  Sportarten stehen nur deren Tabs zur Wahl; ist keine Sportart gefiltert,
  stehen alle vier Tabs zur Verfügung. Wird die Sportart-Auswahl später
  eingeschränkt, werden nicht mehr passende Distanz-Auswahlen automatisch
  entfernt (sonst würde die Länge-Auswahl „ins Leere laufen"). Kategorien:
  - *Laufen*: 5 km, 10 km, Halbmarathon, Marathon, Ultramarathon. 5 km und
    10 km sind „Aufrunde-Kategorien" (ein 4-km-Lauf erscheint unter 5 km),
    Halbmarathon/Marathon sind nur die offiziellen Distanzen (21,0975 km /
    42,195 km, ±0,5 km Toleranz für Rundungsunterschiede in den Daten),
    Ultramarathon ist alles darüber.
  - *Fahrrad*: bis 50 km, 50–100 km, 100–150 km, 150–200 km, 200+ km.
  - *Schwimmen*: 1/2/3/5 km, 10+ km (Marathonschwimmen).
  - *Triathlon*: Sprintdistanz, Olympische Distanz (51,5 km), Mitteldistanz /
    70.3 (113 km), Langdistanz / Ironman (226 km) – jeweils mit Toleranz für
    die offiziellen Distanzen.

  Diese Kategorien sind zusätzlich zum allgemeinen Von/Bis-Zahlenbereich
  wählbar (beide Filter werden kombiniert, UND-verknüpft) und stehen als
  `DISTANCE_CATEGORIES`/`DISTANCE_CATEGORY_LABELS` oben in `events.html` –
  dort anpassbar, falls andere Schwellenwerte gewünscht sind.
- `.github/workflows/pages.yml` – Deployt die Seite automatisch auf
  GitHub Pages bei jedem Push auf diesen Branch.

## Eigene Events hinzufügen

Einfach `events.json` um weitere Objekte im gleichen Format ergänzen und
committen – die Seite liest die Datei bei jedem Aufruf neu ein.

### Automatisch von laufen.de/laufkalender importieren

`scripts/laufkalender_scraper.py` liest Lauf-Events vom Laufkalender auf
[laufen.de](https://laufen.de/laufkalender) aus und ergänzt sie in
`events.json` – im selben Format, ohne Duplikate (Abgleich über Name +
Startdatum). Details, Funktionsweise und wichtige Hinweise stehen im
Docstring am Kopf der Datei. Kurzfassung:

```bash
pip install -r scripts/requirements.txt

# Erst zur Kontrolle, ohne events.json zu verändern:
python3 scripts/laufkalender_scraper.py --dry-run --max-pages 1

# Danach der echte Lauf:
python3 scripts/laufkalender_scraper.py
```

Das Skript prüft bei jedem Lauf automatisch live die `robots.txt` von
laufen.de und bricht ab, falls der Kalender-Pfad dort gesperrt ist (inkl.
Beachtung eines eventuellen Crawl-Delays). Es wurde in der Entwicklungs­umgebung
selbst nicht gegen die echte Seite getestet, da dort der Netzwerkzugriff auf
laufen.de von einer Firewall-/Proxy-Richtlinie blockiert war – die Kernlogik
(Datum-Parsing, Land-/Kategorie-Erkennung, Dedupe/Merge, JSON-LD-Normalisierung)
ist aber mit simulierten Daten getestet. Die HTML-Fallback-Selektoren
(`HTML_FALLBACK_SELECTORS` im Skript) sind Platzhalter und sollten nach einem
Blick in den echten Seitenquelltext kalibriert werden, falls die Seite kein
JSON-LD liefert.

### Automatisch von ironman.com (Europa) importieren

`scripts/ironman_scraper.py` liest Triathlon-Events von der
[IRONMAN-Renn-Übersicht für Europa](https://www.ironman.com/races?facet%5B0%5D=region%3AEurope)
aus und ergänzt sie in `events.json` (als `art1: "Triathlon"`, keine
`art2`-Kategorie – passend zur Projekt-Taxonomie). Standardmäßig werden nur
Events in Deutschland, Österreich und der Schweiz übernommen (`--include-all-europe`
für alle europäischen IRONMAN-Rennen). Distanzen werden aus dem Renntyp
abgeleitet (70.3 → 113 km, 5150 → 51,5 km, volle Distanz → 226 km).

```bash
pip install -r scripts/requirements.txt
python3 scripts/ironman_scraper.py --dry-run --max-pages 1
python3 scripts/ironman_scraper.py
```

Auch hier: live `robots.txt`-Check vor jedem Zugriff, in der
Entwicklungsumgebung nicht gegen die echte Seite testbar (Netzwerkzugriff auf
ironman.com ebenfalls blockiert), Kernlogik mit simulierten Daten getestet.
Eine Besonderheit dieser Seite: Die Renn-Übersicht filtert per URL-Facette
und lädt die Ergebnisse vermutlich per JavaScript aus einer API nach – ein
einfacher HTML-Abruf findet dann evtl. keine Events. Für diesen Fall bietet
das Skript zwei Auswege: `--api-url <JSON-Endpunkt>` (per Browser-
Entwicklertools/Netzwerk-Tab finden) oder `--render-js` (rendert die Seite
per Playwright/Chromium inkl. JavaScript-Ausführung, erfordert
`pip install playwright` + `playwright install chromium`). Details und
weitere Optionen im Docstring am Kopf der Datei.

### Sechs weitere Lauf-Kalender: `scraper_lib.py` + dünne Site-Skripte

Für sechs weitere deutsche Lauf-Kalender gibt es je ein eigenes,
schlankes Scraper-Skript (`--events-json`, `--dry-run`, `--render-js`,
`--api-url`, `--include-all-europe` – alles wie gehabt):

| Skript | Quelle |
|---|---|
| `runnersworld_scraper.py` | runnersworld.de/laufkalender |
| `runninglife_scraper.py` | running.life/laufkalender/deutschland |
| `runningcompany_scraper.py` | runningcompany.de/runners-high/laufkalender |
| `blvsport_scraper.py` | blv-sport.de/laufsport/laufkalender (vermutlich regional auf Bayern begrenzt) |
| `ahotu_scraper.py` | ahotu.com/de/kalender/laufen/deutschland (vermutlich JS-gerendert wie ironman.com) |
| `planetmarathon_scraper.py` | planet-marathon.de/marathon_d.html (vermutlich alte, klassenlose HTML-Tabellenseite – generische Selektoren greifen hier mit hoher Wahrscheinlichkeit nicht, siehe Docstring im Skript) |

Diese sechs (sowie künftige weitere Lauf-Kalender-Scraper) teilen sich die
gemeinsame Logik in `scraper_lib.py` (robots.txt-Prüfung, Datum-/Land-/
Kategorie-/Distanz-Erkennung, JSON-LD- und HTML-Fallback-Parsing,
Geocoding-Cache, Dedupe/Merge) statt sie zu duplizieren – ein einzelnes
Skript besteht dadurch nur noch aus einer `SiteConfig` (Basis-URL,
Kalender-URL, ggf. abweichende Selektoren) und einem Aufruf von
`run_scraper_cli(CONFIG)`. `scraper_lib.py` selbst endet nicht auf
`_scraper.py` und wird von `update_events.py`s Auto-Discovery daher
korrekt nicht als eigener Scraper ausgeführt. Die bereits gegen echte
Infrastruktur verifizierten `laufkalender_scraper.py` und
`ironman_scraper.py` nutzen `scraper_lib.py` bewusst nicht, um ihr
getestetes Verhalten nicht anzufassen.

Wie bei den ersten beiden Skripten: In der Entwicklungsumgebung war der
Netzwerkzugriff auf alle sechs Domains blockiert, die Skripte konnten
daher nicht gegen die echten Seiten getestet werden – nur die
Kernlogik in `scraper_lib.py` (Datum-/Land-/Distanz-Erkennung, JSON-LD-
und generisches API-JSON-Parsing, HTML-Fallback inkl. eines gefundenen
und behobenen Bugs mit zu breiten CSS-Selektoren, DACH-Filter,
Dedupe/Merge) ist mit simulierten Daten getestet, ebenso ein
End-to-End-Test des `--api-url`-Pfads gegen einen lokalen Mock-Server.
Die HTML-Fallback-Selektoren jedes Skripts sind Platzhalter und müssen
nach einem Blick in den jeweils echten Seitenquelltext kalibriert
werden – Details und seitenspezifische Hinweise (z. B. Verdacht auf
JavaScript-Rendering) stehen im Docstring jedes einzelnen Skripts.

**Echter Testlauf & dabei gefundener Bugfix**: Über einen manuell
ausgelösten Lauf des `update-events`-Workflows (mit echtem Internetzugriff,
anders als die Entwicklungsumgebung) wurden alle 8 Scraper einmal live
getestet. Ergebnis: robots.txt wird bei allen 8 Seiten korrekt geladen und
ausgewertet; ironman.com und ahotu.com blocken den eigentlichen Seitenabruf
trotz erlaubter robots.txt mit HTTP 403 (vermutlich Cloudflare-Bot-Schutz,
`--render-js` oder ein API-Endpunkt wären hier vermutlich nötig);
running.life liefert echte `?page=N`-Pagination-Links, aber (noch) 0 Events
pro Seite (JSON-LD/HTML-Fallback ohne Treffer); die übrigen Seiten laden
erfolgreich, liefern aber ebenfalls 0 Events, weil die Platzhalter-Selektoren
nicht zur jeweils echten Seitenstruktur passen. Dabei fiel auf: `blv-sport.de`
hat schlicht **keine** robots.txt (HTTP 404) – das wurde ursprünglich fälschlich
als Abbruchgrund behandelt. Nach robots.txt-Konvention (RFC 9309) bedeutet ein
404 aber „keine Einschränkungen angegeben", nicht „Zugriff verboten"; das ist
jetzt in `scraper_lib.py` sowie `laufkalender_scraper.py` und
`ironman_scraper.py` korrigiert (ein fehlendes robots.txt bricht nicht mehr
ab, sondern wird als uneingeschränkt erlaubt behandelt).

### Alle Scraper gemeinsam ausführen: `update_events.py`

`scripts/update_events.py` ist das Hauptskript: Es findet automatisch alle
Scraper-Skripte in `scripts/` (Namensmuster `*_scraper.py` – aktuell
`laufkalender_scraper.py` und `ironman_scraper.py`, neue Scraper werden ohne
Codeänderung automatisch mit erkannt) und führt sie nacheinander aus. Da
jeder Scraper sein Ergebnis bereits selbst dedupliziert (Name + Startdatum)
direkt in `events.json` schreibt, ergibt sich die Zusammenführung einfach
daraus, dass jeder nachfolgende Scraper schon die Ergebnisse der vorherigen
sieht und dagegen dedupliziert. Ein einzelner fehlschlagender Scraper (z. B.
weil eine Quelle gerade nicht erreichbar ist) bricht den Gesamtlauf nicht ab
– nur wenn *alle* Scraper fehlschlagen, endet das Skript mit Exit-Code 1.

```bash
pip install -r scripts/requirements.txt
python3 scripts/update_events.py --list        # gefundene Scraper anzeigen
python3 scripts/update_events.py --dry-run      # Testlauf, nichts verändern
python3 scripts/update_events.py                # echter Lauf, aktualisiert events.json
python3 scripts/update_events.py --only ironman_scraper.py   # nur ein Skript
```

Die Kernlogik (Auto-Discovery, Verkettung/Merge über mehrere Skripte hinweg,
Umgang mit teilweise fehlschlagenden Scrapern) ist mit simulierten
Mock-Scraper-Skripten end-to-end getestet.

### Tägliche automatische Aktualisierung (GitHub Action)

`.github/workflows/update-events.yml` führt `update_events.py` jeden Tag
automatisch aus (Cron `0 5 * * *` UTC, entspricht ca. 06:00 Uhr deutscher
Zeit – GitHub-Cron kennt keine Zeitzonen, siehe Kommentar in der
Workflow-Datei für Details zur CET/CEST-Abweichung) und zusätzlich manuell
über den "Run workflow"-Button im Actions-Tab. Ändert sich `events.json`
dabei, wird sie automatisch committet und auf `claude/endurance-events-website-v1wruf`
gepusht – das stößt wiederum automatisch den bestehenden Pages-Deploy-Workflow
an, die Seite aktualisiert sich also von selbst. Der Geocoding-Cache
(`scripts/.geocode_cache.json`) wird dabei über GitHub Actions Cache
zwischen den Läufen wiederverwendet, um wiederholte Nominatim-Anfragen für
bereits bekannte Städte zu vermeiden.

## Lokal testen

Da `events.html` die Datei `events.json` per `fetch` lädt, funktioniert
das direkte Öffnen per Doppelklick in manchen Browsern nicht
(CORS-Einschränkung bei `file://`). Stattdessen lokal einen einfachen
Webserver starten, z. B.:

```bash
python3 -m http.server 8000
```

und dann `http://localhost:8000` im Browser öffnen.

## GitHub Pages aktivieren (einmalig)

1. Im Repository zu **Settings → Pages** gehen.
2. Unter **Build and deployment → Source** die Option **GitHub Actions**
   auswählen.
3. Nach dem nächsten Push auf diesen Branch deployt der Workflow
   automatisch, und die Seite ist unter der von GitHub angezeigten URL
   erreichbar (üblicherweise
   `https://antdon930.github.io/Enduranceevents/`).

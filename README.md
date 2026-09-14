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
  - `anmeldeschluss` – Anmeldeschluss-Datum im Format `YYYY-MM-DD` (optional,
    wird von keinem Scraper befüllt und in der UI nicht mehr angezeigt/
    gefiltert - die Daten dazu sind bei den meisten Quellen nicht
    zuverlässig auffindbar, siehe "Entfernte Anmeldung-Spalte" unten;
    das Feld bleibt im Schema für eigene, manuell gepflegte Events)
  - `laenge_km` – Streckenlänge in Kilometern
  - `veranstalter_url` – Link zur Veranstalter-Website

  **Neues Event ergänzen**: Ort per Kartendienst (z. B. Google Maps – Rechtsklick
  auf den Punkt zeigt die Koordinaten) nachschlagen und als `lat`/`lon` eintragen,
  sonst funktioniert die Umkreissuche für dieses Event nicht.

  **Duplikat-Prüfung**: Ein Event gilt als Duplikat, wenn Name + Startdatum
  + (gerundete) Distanz übereinstimmen (siehe `scraper_lib.dedupe_key()`
  bzw. die gleichnamige Funktion in `laufkalender_scraper.py`). Die
  Distanz ist bewusst Teil des Schlüssels: dieselbe Veranstaltung bietet
  am selben Tag oft mehrere Distanzen an (z. B. 10 km, Halbmarathon UND
  Marathon) - das sind unterschiedliche Einträge und erscheinen absichtlich
  einzeln in der Liste statt als ein zusammengefasster/verworfener
  Eintrag. Jeder Scraper prüft das selbst beim Schreiben in `events.json`;
  `update_events.py` meldet zusätzlich, welche Events dabei neu
  hinzukamen (für die optionale "Benachrichtige mich"-Anbindung, siehe
  unten).

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
  `index.html`, ein „Karte"-Button zu `karte.html` (siehe unten) sowie
  der Login-Button (siehe „Login/Anmeldung einrichten"). Liest
  `events.json` per `fetch` ein. Excel-ähnliche Tabelle in dieser
  Spaltenreihenfolge, jede Spalte hat einen eigenen Filter im Spaltenkopf
  (▾-Symbol):
  1. **Name** – Textsuche (Eingabefeld, filtert live während des Tippens)
  2. **Datum** – aufklappbarer Baum Jahr → Monat → Tag (wie Excels
     Datums-AutoFilter); ein Jahr oder Monat auswählen selektiert
     automatisch alle enthaltenen Tage, einzelne Tage sind ebenfalls wählbar
  3. **Land** – Checkbox-Liste
  4. **Stadt/Ort** – Checkbox-Liste mit *allen* Städten (unabhängig von
     anderen Filtern) plus Umkreissuche: „Aktuellen Standort verwenden"
     (Browser-Geolocation) oder eine Stadt als Ausgangspunkt wählen, dann
     Radius 0–5 / 5–20 / 20–50 / 50+ km wählen. Wird die Seite mit
     `?standort=<Stadt>` aufgerufen (Deep-Link von `karte.html`), ist
     dieser Filter beim Laden schon gesetzt.
  5. **Sportart** – Checkbox-Liste (Laufen/Schwimmen/Fahrrad/Triathlon)
  6. **Kategorie** – Checkbox-Liste, deren Optionen von der Sportart-Auswahl
     abhängen. Zuordnung (als `ART2_BY_ART1` oben im `<script>`-Block in
     `events.html`, dort anpassbar):
     - *Laufen*: Straße, Trail, Bahn, Berg, Cross, Hindernis
     - *Schwimmen*: Freiwasser, Becken
     - *Fahrrad*: Straße, Zeitfahren, Mountainbike, Gravel, Bahn, Cyclecross
     - *Triathlon* hat keine Kategorie-Unterteilung.
  7. **Länge** – Sportart-Tabs (Laufen/Fahrrad/Schwimmen/Triathlon) mit
     sportartspezifischen Distanz-Schnellauswahlen plus dem allgemeinen
     Zahlenbereich von/bis (siehe unten); die Einheit „km" steht bereits in
     jeder Zelle, daher nur „Länge" als Spaltenname

  **Entfernte Anmeldung-Spalte**: Es gab früher eine achte Spalte
  „Anmeldung" (Offen/Geschlossen, aus `anmeldeschluss` berechnet). Sie
  wurde entfernt, weil der Anmeldeschluss bei so gut wie keiner der
  gescrapten Quellen zuverlässig im HTML steht - keine belastbare
  Datenbasis für einen Filter.

  **Sortierung**: Die Liste ist immer nach Datum sortiert, das
  nächstliegende/aktuellste (bevorstehende) Datum zuerst. Bereits
  vergangene Events (Startdatum vor heute) werden dabei ans Ende
  sortiert statt - wie ein reiner Textvergleich es tun würde - vor alle
  künftigen Events zu rutschen.

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
- `karte.html` – Kartenansicht (Leaflet + OpenStreetMap-Kacheln, keine
  API-Keys nötig) mit einem Marker pro **Standort** (nicht pro Event):
  ein Ort mit z. B. 10 Events zeigt einen einzelnen Marker mit der Zahl
  "10" statt zehn übereinanderliegenden Punkten. Klick auf einen Marker
  öffnet ein Popup mit Ortsname, Länderangabe und einem Link „N Events
  in der Liste anzeigen", der zu `events.html?standort=<Ort>` führt und
  dort automatisch den Standort-Filter auf genau diesen Ort setzt. Erreichbar
  über den „Karte"-Button in `events.html`/`index.html`.
- `.github/workflows/pages.yml` – Deployt die Seite automatisch auf
  GitHub Pages bei jedem Push auf diesen Branch.

## Eigene Events hinzufügen

Einfach `events.json` um weitere Objekte im gleichen Format ergänzen und
committen – die Seite liest die Datei bei jedem Aufruf neu ein.

### Acht Quellen geprüft, fünf davon aktiv genutzt

Für dieses Projekt wurden acht Lauf-/Event-Kalender auf automatisiertes
Auslesen geprüft (robots.txt live abgerufen und ausgewertet, dazu
stichprobenartig Nutzungsbedingungen/Impressum auf ein explizites
Scraping-Verbot durchsucht). Fünf erlauben es und werden aktiv
gescraped, drei werden bewusst übersprungen:

| Quelle | Status | Skript |
|---|---|---|
| [laufen.de](https://laufen.de/laufkalender) | ✅ aktiv | `laufkalender_scraper.py` |
| [runningcompany.de](https://www.runningcompany.de/runners-high/laufkalender/) | ✅ aktiv | `runningcompany_scraper.py` |
| [running.life](https://running.life/laufkalender/deutschland) | ✅ aktiv | `runninglife_scraper.py` |
| [blv-sport.de](https://blv-sport.de/laufsport/laufkalender) | ✅ aktiv | `blvsport_scraper.py` |
| [planet-marathon.de](http://www.planet-marathon.de/marathon_d.html) | ✅ aktiv | `planetmarathon_scraper.py` |
| [ironman.com](https://www.ironman.com/races) | ⏭ übersprungen | `ironman_scraper.py` |
| [runnersworld.de](https://www.runnersworld.de/laufkalender/) | ⏭ übersprungen | `runnersworld_scraper.py` |
| [ahotu.com](https://www.ahotu.com/de/kalender/laufen/deutschland) | ⏭ übersprungen | `ahotu_scraper.py` |

Alle acht Skripte akzeptieren dieselben CLI-Optionen
(`--events-json`, `--dry-run`, `--max-pages`, `--no-geocoding`,
`--render-js`, `--api-url`, `--include-all-europe`) und schreiben
direkt (dedupliziert über Name + Startdatum) in `events.json`.

#### Die drei übersprungenen Quellen

- **ironman.com**: robots.txt erlaubt zwar `User-agent: *` generell
  (`Allow: /`), sperrt aber ausdrücklich einzelne KI-Crawler namentlich
  per `Disallow: /` – darunter **ClaudeBot** (Anthropics eigener
  Crawler) sowie u. a. GPTBot, Google-Extended und CCBot. Da diese
  Aufgabe von einem Claude-Agenten ausgeführt wird, wird diese
  namentliche Sperre respektiert, statt sie über einen anderen
  User-Agent zu umgehen. (Zusätzlich blockt Cloudflare den eigentlichen
  Seitenabruf ohnehin mit HTTP 403.)
- **runnersworld.de**: robots.txt enthält neben den technischen
  `Disallow`-Regeln einen expliziten rechtlichen Hinweis: *"The use of
  robots or other automated means to access [...] or collect or mine
  data without the express permission of [...] is strictly
  prohibited."* – ein ausdrückliches Verbot, das unabhängig von den
  einzelnen gesperrten Pfaden gilt.
- **ahotu.com**: Schon `robots.txt` selbst liefert HTTP 403 mit einer
  aktiven Cloudflare-Bot-Challenge ("Just a moment...") statt Klartext
  – die Domain lässt sich ohne Umgehung dieser Challenge gar nicht
  automatisiert erreichen.

Alle drei Skripte brechen deshalb selbst sofort ab (Exit-Code 0, klare
Meldung, kein Netzwerkzugriff), bevor `update_events.py` sie überhaupt
aufruft – sie bleiben als dokumentierte Vorlage im Repo, falls sich die
jeweilige Situation künftig ändert. Details je Quelle stehen im
Docstring am Kopf jedes Skripts.

#### Besonderheiten der fünf aktiven Quellen

- **laufen.de**: Die Kalenderseite selbst liefert kein JSON-LD und im
  initialen HTML keine Event-Liste – sie lädt die Ergebnisse per
  JavaScript aus einem AJAX-Endpunkt (`POST /laufkalender/ajax/search`)
  nach, den das Skript direkt anspricht (kein `--render-js` nötig).
- **runningcompany.de**: Ein Akkordeon aus zwölf Monatstabellen ohne
  Jahresangabe im Datum (Jahr wird aus dem Seitentext gelesen). Eigene
  Laufreise-/Laufcamp-/Trainingsangebote (an ihrem internen Link
  erkennbar) werden von echten Renn-Events unterschieden und
  aussortiert.
- **running.life**: Liefert Events server-seitig als schema.org
  **ItemList** mit eingebetteten `SportsEvent`-Objekten – wird von
  `scraper_lib.py` automatisch erkannt und normalisiert.
- **blv-sport.de**: Hat gar keine robots.txt (HTTP 404) – nach
  robots.txt-Konvention (RFC 9309) bedeutet das „keine Einschränkungen
  angegeben", nicht „Zugriff verboten". Einfache HTML-Tabelle ohne
  Distanz-/Link-Spalte.
- **planet-marathon.de**: Alte, klassenlose HTML-Tabelle (nur
  Deutschland, ausschließlich Marathons mit offizieller Distanz von
  42,195 km laut Seitenhinweis).

### Alle Scraper gemeinsam ausführen: `update_events.py`

`scripts/update_events.py` ist das Hauptskript: Es findet automatisch alle
Scraper-Skripte in `scripts/` (Namensmuster `*_scraper.py` – aktuell alle
acht oben genannten, neue Scraper werden ohne Codeänderung automatisch mit
erkannt) und führt sie nacheinander aus. Die drei bewusst übersprungenen
Skripte (siehe oben) melden dabei einen Erfolg (Exit-Code 0) ohne
Änderung an `events.json`. Da
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

## Login/Anmeldung einrichten

`index.html`, `events.html` und `karte.html` haben rechts neben dem
Home-Button einen „Anmelden"-Button (siehe `auth.js`). Er nutzt
**Firebase Authentication** (Google + E-Mail/Passwort mit Bestätigungs-
E-Mail; „Mit Apple anmelden" ist im Modal sichtbar, aber bewusst
**deaktiviert** - Apple Sign-In erfordert ein kostenpflichtiges
Apple-Developer-Konto, das für dieses Projekt noch nicht existiert;
sobald eines vorhanden ist, in `auth.js` das `disabled`-Attribut der
beiden `#ee-apple-btn`-Buttons entfernen und die Apple-Provider-Logik
ergänzen).

**Ohne Konfiguration ist der Button bereits jetzt sichtbar und öffnet
das fertige Modal**, zeigt darin aber einen Hinweis „Login ist in dieser
Vorschau noch nicht eingerichtet" statt kaputter Funktionalität - die
Seite bleibt also voll benutzbar, auch ohne die folgenden Schritte.

### Einmaliges Setup

1. Firebase-Projekt anlegen: <https://console.firebase.google.com/> ->
   "Projekt hinzufügen" (kostenlos, kein Kreditkarte nötig für die
   folgenden Schritte).
2. **Build → Authentication → Sign-in method**: "Google" und
   "E-Mail/Passwort" aktivieren.
3. **Authentication → Settings → Autorisierte Domains**:
   `antdon930.github.io` eintragen (sonst funktioniert der Login live auf
   GitHub Pages nicht, auch wenn er lokal geht).
4. **Build → Firestore Database → Datenbank erstellen** (Produktionsmodus).
   Danach unter **Rules** den Inhalt von `firestore.rules` (in diesem
   Repo) einfügen und veröffentlichen.
5. **Projekteinstellungen (Zahnrad oben links) → "Meine Apps" → Web-App
   hinzufügen**. Das dort angezeigte Config-Objekt in `firebase-config.js`
   einfügen (ersetzt die `REPLACE_ME`-Platzhalter).
6. Committen und pushen - der Login funktioniert danach auf allen drei
   Seiten (dasselbe `firebase-config.js`/`auth.js` wird überall geladen).

### „Benachrichtige mich" (0 Treffer in der Liste)

Setzt jemand in `events.html` Filter, für die aktuell **kein** Event
existiert, erscheint statt der leeren Tabelle ein Hinweis mit einem
Button „Benachrichtigen, sobald verfügbar" (nicht angemeldet: „Anmelden,
um benachrichtigt zu werden", öffnet das Login-Modal). Ein Klick
speichert die aktuell aktiven Filter - **ohne den Datumsfilter** (das
gesuchte Event liegt ja per Annahme in der Zukunft und ist deshalb noch
nicht in `events.json`) - als Dokument in der Firestore-Collection
`filterSubscriptions` (siehe `auth.js: saveFilterSubscription()`).

Das Speichern des Abos funktioniert bereits mit den obigen 6 Schritten.
Damit bei einem passenden neuen Event auch tatsächlich eine E-Mail
rausgeht, sind zwei weitere, **optionale** Schritte nötig (siehe
`functions/index.js` für die vollständige Anleitung im Datei-Kopf):

1. Firebase-Projekt auf den **Blaze-Tarif** upgraden (nötig, damit Cloud
   Functions ausgehende HTTPS-Aufrufe von `update_events.py` entgegennehmen
   dürfen - im Rahmen dieses Projekts fallen dabei praktisch keine Kosten
   an) und die Function deployen:
   ```bash
   npm install -g firebase-tools
   firebase login
   firebase init functions   # bestehendes Projekt wählen, functions/ nutzen
   cd functions && npm install && cd ..
   firebase deploy --only functions
   ```
   Die ausgegebene Function-URL als GitHub-Actions-Secret
   `NOTIFY_WEBHOOK_URL` hinterlegen (Repo → Settings → Secrets and
   variables → Actions) sowie optional ein selbst gewähltes
   `NOTIFY_WEBHOOK_SECRET` (schützt die Function vor fremden Aufrufen -
   denselben Wert dann auch als Umgebungsvariable beim Function-Deployment
   setzen). `update_events.py` ruft die URL danach automatisch nach jedem
   Lauf auf, in dem sich `events.json` geändert hat.
2. In der Firebase-Konsole unter **Extensions** die offizielle Extension
   **"Trigger Email from Firestore"** installieren und dort SMTP-
   Zugangsdaten (z. B. von SendGrid, Mailgun oder einem eigenen Postfach)
   hinterlegen - sie übernimmt den eigentlichen Versand für die
   `mail`-Dokumente, die `functions/index.js` anlegt.

**Bekannte Einschränkung**: Der Matching-Code in `functions/index.js`
prüft Land/Sportart/Kategorie/Standort/Länge/Umkreis, aber (noch) nicht
die feingranularen Distanz-Kategorien (Marathon/Halbmarathon/...) aus
`events.html` (`DISTANCE_CATEGORIES`) - diese Tabelle müsste dafür
zwischen `events.html` und der Cloud Function geteilt werden. Ein Abo
mit einer solchen Kategorie wird aktuell nur über die einfachen
Länge-von/bis-Werte geprüft, falls zusätzlich gesetzt.

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

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
  - `laenge_km` – Streckenlänge in Kilometern, **immer auf eine
    Dezimalstelle gerundet**. Die Quellen geben dieselbe Strecke
    unterschiedlich genau an (Marathon mal als „42,195 km", mal als
    „42,2 km"; Halbmarathon als „21,0975 km"); gespeichert und angezeigt
    wird einheitlich `42.2` bzw. `21.1` (siehe `scraper_lib.round_km()`).
  - `wettbewerb` – Bezeichnung der konkreten Strecke innerhalb der
    Veranstaltung (optional, z. B. `"Moslig 8000"` oder `"Halbmarathon"`).
    Veranstaltungen bieten fast immer mehrere Strecken an; jede wird zu
    einem eigenen Eintrag, und dieses Feld sagt, welche gemeint ist (siehe
    „Mehrere Strecken pro Veranstaltung" unten). In der Liste steht es als
    kleine Zeile unter dem Veranstaltungsnamen.
  - `veranstalter_url` – Link zur **offiziellen Webseite des Laufs**, nicht
    zum Kalenderportal, über das wir ihn gefunden haben. Die Portale nennen
    die offizielle Seite auf ihrer Detailseite (running.life als Button
    „Webseite", laufen.de als „Mehr Infos und Anmeldung"), also gibt es
    keinen Grund, auf das Portal zu verlinken. Ein bereits gespeicherter
    Portallink wird ersetzt, sobald die offizielle Seite bekannt ist – auch
    über Quellgrenzen hinweg: laufen.de nennt für viele Events keine
    offizielle Seite, running.life aber schon, und über die
    Duplikat-Erkennung landet sie dann trotzdem im Eintrag (siehe
    `scraper_lib.update_existing_event()` und `PORTAL_DOMAINS`). Nur wenn
    keine Quelle eine offizielle Seite kennt, bleibt der Portallink als
    Notlösung stehen – geraten wird nie (die laufen.de-Detailseiten
    verlinken z. B. Dutzende Sponsoren, darunter irgendwo die echte Seite).

  **Neues Event ergänzen**: Ort per Kartendienst (z. B. Google Maps – Rechtsklick
  auf den Punkt zeigt die Koordinaten) nachschlagen und als `lat`/`lon` eintragen,
  sonst funktioniert die Umkreissuche für dieses Event nicht. `land` wird aus
  den Koordinaten abgeleitet und muss nicht per Hand gepflegt werden (siehe
  „Land" unten).

  **Mehrere Strecken pro Veranstaltung**: Eine Laufveranstaltung bietet
  fast immer mehrere Wettbewerbe an. Jeder Wettbewerb wird zu einem
  EIGENEN Eintrag mit eigener `laenge_km` und eigenem `wettbewerb`-Label;
  Name, Ort und Datum bleiben identisch. Beispiel „10. Schnebelhorn
  Panoramatrail" (Mosnang, CH): die Quelle listet sieben Wettbewerbe, nach
  der 5-km-Regel bleiben zwei Einträge übrig – „Moslig 8000" (8,5 km) und
  „Halbmarathon" (21,1 km). Die Kategorie (`art2`) wird pro Strecke
  bestimmt, damit bei einer Veranstaltung mit Halbmarathon UND Trailrun
  nicht beide Zeilen dieselbe Kategorie bekommen.

  Umgesetzt in `scraper_lib.parse_competitions()` /
  `expand_competitions()`; wo die Wettbewerbsliste steht, ist je Quelle
  unterschiedlich – siehe Docstring des jeweiligen Scrapers:

  | Quelle | Wo die Strecken stehen |
  |---|---|
  | laufen.de | Detailseite, zwei Layouts (`ul.all` und `ul.races` mit Streckenart) |
  | running.life | Aufzählung im Beschreibungstext der Detailseite (genau: „14,6 km"), sonst die Chips der Kalenderseite |
  | runningcompany.de | Distanz-Spalte der Monatstabelle, an Komma/Schrägstrich getrennt |

  Bei running.life ist die Aufzählung im Text die genauere Quelle: die
  Zusammenfassungs-Karten derselben Seite runden 14,6 km auf „15 km".
  Beim BraunenBerg-Lauf ergibt das die drei Strecken 32 km, 14,6 km und
  8,2 km.

  **Höhenprofil als Kategorie-Signal**: Nennt die Quelle Höhenmeter pro
  Strecke und sagt der Name nichts Spezifischeres, entscheidet der Anstieg
  pro Kilometer: ab 20 m/km gilt die Strecke als Berglauf
  (`scraper_lib.art2_from_elevation()`). Der „VR Bank – BraunenBerg-Lauf"
  über 14,6 km mit ca. 400 Hm (27 m/km) galt vorher als Straßenlauf. Ein
  flacher Stadtmarathon liegt bei unter 5 m/km und bleibt unberührt; eine
  aus dem Namen erkannte Kategorie (Trail, Cross, …) wird nie
  überschrieben.

  **Land**: Kalender nennen oft nur eine Postleitzahl, und eine
  vierstellige PLZ unterscheidet Österreich nicht von der Schweiz.
  `land` wird daher vorrangig aus der Landesangabe der Quelle gelesen
  (`(Schweiz)` ebenso wie Kürzel wie `(AUT)`, siehe
  `scraper_lib.LAND_ABBREVIATIONS`) und sonst per Reverse-Geocoding aus
  den Koordinaten bestimmt (`Geocoder.reverse_land()`, Ergebnisse
  gecacht). Bewusst NICHT aus dem Event-Namen geraten: der „25.
  Fränkische-Schweiz-Marathon" liegt in Bayern, nicht in der Schweiz
  (dieser Fehler stand real in `events.json`).

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
  über den „Karte"-Button in `events.html` (auf der Startseite gibt es
  bewusst keinen Kartenlink).
- `.github/workflows/pages.yml` – Deployt die Seite automatisch auf
  GitHub Pages bei jedem Push auf diesen Branch.

## Eigene Events hinzufügen

Einfach `events.json` um weitere Objekte im gleichen Format ergänzen und
committen – die Seite liest die Datei bei jedem Aufruf neu ein.

## Datenqualität

Sieben Mechanismen sorgen dafür, dass nur sinnvolle, korrekt kategorisierte
und eindeutige Events in `events.json` landen:

- **5-km-Mindestdistanz** (`scraper_lib.filter_min_distance()`,
  gleichnamige Funktion in `laufkalender_scraper.py`): Events mit
  **bekannter** Distanz unter 5 km (Bambini-/Kinder-/Firmen-Kurzläufe)
  werden nicht aufgenommen. Events **ohne** bekannte Distanz sind davon
  bewusst NICHT betroffen - das Kriterium lässt sich sonst nicht anwenden,
  und ein pauschaler Ausschluss würde auch echte, längere Events
  verwerfen, deren Distanz die Quelle nur nicht nennt. Schwellenwert:
  `MIN_DISTANCE_KM` in `scraper_lib.py`.
- **Kategorie-Erkennung (art2) nach Priorität, nicht nach erstem
  Treffer** (`ART2_KEYWORDS_LAUFEN` in `scraper_lib.py`, dieselbe Liste
  dupliziert in `laufkalender_scraper.py`): Ein Name wie "5. Beck
  HochRhön Bergtrail 42k Trail-Marathon" enthält das Wort "Marathon" -
  ohne eine bewusste Reihenfolge (Hindernis → Trail → Berg
  [inkl. "Höhenmeter" im Text] → Cross → Bahn → erst zuletzt Straße/
  Marathon/Stadtlauf) hätte die generische Straße-Regel zuerst zugetroffen
  und das Event fälschlich als Straßenlauf statt als Trail eingestuft
  (echter, mit realen Daten verifizierter Bug).
- **Duplikaterkennung über Quellgrenzen hinweg**
  (`scraper_lib.is_same_event()`): Dieselbe Veranstaltung steht meist in
  mehreren Kalendern – unter abweichendem Namen und mit leicht
  abweichender Distanz („52. Int. Bodensee-Marathon" / „52.
  Bodensee-Marathon" / „Bodensee Marathon", 42,195 vs. 42,2 km). Ein
  Abgleich über den exakten Namen erkennt das nicht; beim ersten
  vollständigen Lauf steckten dadurch **65 Duplikat-Gruppen** in
  `events.json`. Zwei Events gelten jetzt als identisch, wenn *alle* vier
  Bedingungen zutreffen: gleiches Startdatum, ähnlicher Name (normalisiert
  ohne Auflagen-Nummer, Satzzeichen, Umlaute und Füllwörter; sonst
  Ähnlichkeit ≥ 0,88), derselbe Ort (Ortsname oder Koordinaten ≤ 30 km)
  und kompatible Distanz (Toleranz ±0,5 km bzw. 5 %). Die Orts-Bedingung
  verhindert Fehltreffer bei generischen Namen („Silvesterlauf" in
  Salzburg vs. München), die Distanz-Toleranz ist klein genug, dass echte
  Distanz-Varianten desselben Events (5 km / 10 km / Halbmarathon)
  erhalten bleiben. Beim Zusammenführen wird der vollständigste Eintrag
  behalten, fehlende Felder werden aus den Duplikaten ergänzt und ein
  direkter Veranstalter-Link einem Kalender-Portal-Link vorgezogen – der
  Datensatz gewinnt durch jede zusätzliche Quelle, statt doppelte Zeilen
  zu erzeugen.
- **Alle Strecken auslesen, nicht nur die längste**
  (`scraper_lib.parse_competitions()` / `expand_competitions()`): Früher
  hat jeder Scraper aus der Wettbewerbsliste einer Veranstaltung nur EINE
  Zahl gemacht (die längste) und alle anderen Strecken verworfen. Beim
  „10. Schnebelhorn Panoramatrail" stand dadurch nur der Halbmarathon in
  der Liste, der ebenfalls angebotene „Moslig 8000" über 8,5 km fehlte –
  obwohl die Quelle ihn ausweist. Jetzt wird jede Strecke ein eigener
  Eintrag mit eigenem `wettbewerb`-Label und eigener Kategorie (siehe
  „Mehrere Strecken pro Veranstaltung" oben). Für laufen.de heißt das,
  dass zusätzlich die **Detailseite** jedes Events abgerufen wird – nur
  dort stehen die einzelnen Wettbewerbe, das Land und der echte
  Veranstalter-Link.
- **Immer auf die offizielle Seite des Laufs verlinken**
  (`scraper_lib.update_existing_event()`, `PORTAL_DOMAINS`): Ein Link auf
  das Kalenderportal, über das wir ein Event gefunden haben, ist für
  Nutzer/innen ein Umweg – und unnötig, weil die Portale die offizielle
  Seite selbst nennen (running.life als Button „Webseite", laufen.de als
  „Mehr Infos und Anmeldung"). Ein gespeicherter Portallink wird ersetzt,
  sobald die offizielle Seite bekannt ist, auch wenn sie aus einer anderen
  Quelle kommt: laufen.de kennt für viele Events keine offizielle Seite,
  running.life aber schon. Geraten wird nie – die laufen.de-Detailseiten
  verlinken Dutzende Sponsoren, darunter irgendwo die echte Seite.
- **Nur Quellen, die Distanz UND Veranstalter-Link mitliefern**: Genau
  daran ist `blv-sport.de` gescheitert und wurde deshalb aus dem
  automatischen Scraping genommen (siehe Tabelle unten). Ohne Distanz
  greift die 5-km-Regel nicht, ohne Link ist nichts überprüfbar – und
  beides pro Event manuell zu recherchieren skaliert nicht. Neue Quellen
  sollten an diesem Maßstab gemessen werden.
- **Manuelle Korrekturen** (`scripts/manual_overrides.json`): Generischer
  Mechanismus, um einzelne Events zu korrigieren (Distanz, Kategorie,
  Link) oder ganz auszuschließen (`exclude: true`, z. B. ein verifiziertes
  Duplikat, das unter abweichendem Namen ein zweites Mal gelistet war).
  Wird von `apply_manual_overrides()` vor der 5-km-Filterung angewendet
  (Schlüssel: `"<Name>|<Datum>"`, Abgleich nicht case-sensitiv). Aktuell
  enthält die Datei die Recherche-Ergebnisse zu den 40 Events, die
  blv-sport.de vor der Deaktivierung geliefert hatte – diese Events
  bleiben damit vollständig in `events.json` erhalten (mit Distanz,
  Kategorie und Link aus der jeweils offiziellen Ausschreibung). Die
  Einträge bleiben wirksam, falls dieselben Events künftig über eine
  andere Quelle mit identischem Namen + Datum hereinkommen.

### Bestehende Daten nachträglich aufräumen: `clean_events.py`

Die Scraper verändern vorhandene Einträge nie (sie fügen nur neue an) –
neue Regeln oder Bugfixes wirken daher nicht rückwirkend. Genau dafür gibt
es `scripts/clean_events.py`: es wendet die manuellen Korrekturen an,
bestimmt die Kategorie aus dem Namen neu, zieht eine einmalige
Distanz-Korrektur nach (behobener Bug: „Halbmarathon" wurde mit 42,2 km
statt 21,1 km eingetragen, weil das Stichwort „marathon" zuerst prüfte),
rundet alle Längenangaben auf eine Dezimalstelle, ergänzt bzw. korrigiert
`land` per Reverse-Geocoding der Koordinaten,
entfernt zu kurze Laufevents und führt Duplikate zusammen. Zum Schluss
wird nach Datum sortiert (kleine Git-Diffs). Das Skript ist idempotent –
ein zweiter Lauf ändert nichts mehr.

```bash
python3 scripts/clean_events.py --dry-run   # nur Bericht, nichts ändern
python3 scripts/clean_events.py             # events.json aufräumen
```

### Regressionstests: `test_scraper_lib.py`

```bash
python3 scripts/test_scraper_lib.py
```

Prüft die Textauswertung der Scraper (Distanz, Kategorie, Land,
Wettbewerbsliste, Duplikat-Erkennung) ohne Netzwerkzugriff und ohne
zusätzliche Test-Bibliothek; Exit-Code 0/1, also direkt CI-fähig. Fast
alle Fehler in diesem Projekt saßen in genau dieser Ecke und sind erst
beim Nachschlagen einzelner Events in der fertigen Liste aufgefallen
(„42,195 km" als 195 km gelesen, „Halbmarathon" mit 42,2 km, ein
Trail-Marathon als Straßenlauf, „Fränkische Schweiz" als Land Schweiz).
Jeder dieser echten Fehler steht dort als Testfall mit Kommentar – **neue
Parsing-Regeln bitte mit einem Testfall dort ergänzen.**

`update_events.py` ruft es nach jedem echten Lauf automatisch auf (nach
allen Scrapern, da Duplikate erst im Zusammenspiel mehrerer Quellen
entstehen, und vor der „Benachrichtige mich"-Meldung, damit keine Events
gemeldet werden, die gleich wieder zusammengeführt werden). Ein Fehler
beim Aufräumen bricht den Gesamtlauf nicht ab.

### Acht Quellen geprüft, vier davon aktiv genutzt

Für dieses Projekt wurden acht Lauf-/Event-Kalender auf automatisiertes
Auslesen geprüft (robots.txt live abgerufen und ausgewertet, dazu
stichprobenartig Nutzungsbedingungen/Impressum auf ein explizites
Scraping-Verbot durchsucht). Vier werden aktiv gescraped, vier werden
bewusst übersprungen – drei aus rechtlichen/technischen Gründen, eine
(blv-sport.de) wegen mangelnder Datenqualität:

| Quelle | Status | Skript |
|---|---|---|
| [laufen.de](https://laufen.de/laufkalender) | ✅ aktiv | `laufkalender_scraper.py` |
| [runningcompany.de](https://www.runningcompany.de/runners-high/laufkalender/) | ✅ aktiv | `runningcompany_scraper.py` |
| [running.life](https://running.life/laufkalender/deutschland) | ✅ aktiv | `runninglife_scraper.py` |
| [planet-marathon.de](http://www.planet-marathon.de/marathon_d.html) | ✅ aktiv | `planetmarathon_scraper.py` |
| [blv-sport.de](https://blv-sport.de/laufsport/laufkalender) | ⏭ übersprungen (Datenqualität) | `blvsport_scraper.py` |
| [ironman.com](https://www.ironman.com/races) | ⏭ übersprungen (robots.txt) | `ironman_scraper.py` |
| [runnersworld.de](https://www.runnersworld.de/laufkalender/) | ⏭ übersprungen (robots.txt) | `runnersworld_scraper.py` |
| [ahotu.com](https://www.ahotu.com/de/kalender/laufen/deutschland) | ⏭ übersprungen (Bot-Sperre) | `ahotu_scraper.py` |

Alle acht Skripte akzeptieren dieselben CLI-Optionen
(`--events-json`, `--dry-run`, `--max-pages`, `--no-geocoding`,
`--render-js`, `--api-url`, `--include-all-europe`) und schreiben
direkt (dedupliziert über Name + Startdatum + Distanz) in `events.json`.

#### Die vier übersprungenen Quellen

- **blv-sport.de** (Datenqualität, nicht robots.txt): Der Zugriff wäre
  einwandfrei erlaubt (keine robots.txt = keine Einschränkungen), aber
  die Tabelle liefert nur Datum, Bezeichnung und Ort – **keine Distanz
  und keinen Veranstalter-Link**. Damit fehlen genau die zwei Angaben,
  von denen die Datenqualität abhängt: ohne Distanz greift die
  5-km-Mindestdistanz-Regel nicht (reine Kinderläufe landen unbemerkt in
  der Liste), ohne Link ist nichts überprüfbar. Beide Lücken lassen sich
  nur durch manuelle Recherche pro Event schließen (siehe
  `scripts/manual_overrides.json`), was bei jedem neuen Event erneut
  anfallen würde. Da ein Großteil der bayerischen Läufe ohnehin über
  laufen.de **mit** Distanz und Link erfasst wird, ist diese Quelle
  deaktiviert. Die bereits recherchierten Events bleiben in `events.json`
  erhalten.
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

Alle vier Skripte brechen deshalb selbst sofort ab (Exit-Code 0, klare
Meldung, kein Netzwerkzugriff), bevor `update_events.py` sie überhaupt
aufruft – sie bleiben als dokumentierte Vorlage im Repo, falls sich die
jeweilige Situation künftig ändert (bei blv-sport.de genügt dann das
Entfernen des `sys.exit(0)`-Blocks). Details je Quelle stehen im
Docstring am Kopf jedes Skripts.

#### Besonderheiten der vier aktiven Quellen

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
  `scraper_lib.py` automatisch erkannt und normalisiert. Die Distanzen
  stehen dort nicht drin, daher zusätzlich die Strecken-Chips der
  Kalenderseite und die genaue Aufzählung im Beschreibungstext der
  Detailseite (siehe oben). Der Kalender wird in voller Tiefe abgerufen:
  `SCRIPT_EXTRA_ARGS` in `update_events.py` übergibt `--max-pages 110`,
  das deckt die ~101 Seiten (rund 2000 deutsche Events) ab. Mit dem
  Standardwert von 10 Seiten kämen nur ~200 Events herein – und für alle
  übrigen fehlte auch die offizielle Veranstalter-Seite.
- **planet-marathon.de**: Alte, klassenlose HTML-Tabelle (nur
  Deutschland, ausschließlich Marathons mit offizieller Distanz von
  42,195 km laut Seitenhinweis).

### Laufzeit

Ein **vollständiger Lauf dauert rund zwei Stunden**: laufen.de und
running.life rufen die Detailseite jedes Events ab (nur dort stehen die
einzelnen Wettbewerbe, das Land und die offizielle Veranstalter-Seite),
und die Pause zwischen den Requests kommt aus der jeweiligen robots.txt.
Grobe Verteilung: running.life ~71 Minuten (~2020 Detailseiten),
laufen.de ~26 Minuten (~750), Rest wenige Minuten, plus Geocoding neuer
Orte beim ersten Lauf.

Das ist der Grund, warum der Workflow `timeout-minutes: 300` setzt – und
warum man einen Datenlauf besser über „Actions → Run workflow" auslöst
als ihn lokal abzuwarten. Für schnelle Tests eines Scrapers:
`--max-pages 2 --no-details`.

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
E-Mail).

„Mit Apple anmelden" ist **ausgeblendet**: Apple Sign-In erfordert ein
kostenpflichtiges Apple-Developer-Konto, das für dieses Projekt nicht
existiert – ein dauerhaft ausgegrauter Button war nur Ballast im Dialog.
Der Code dafür ist aber vorbereitet: in `auth.js`
`SHOW_APPLE_SIGNIN = true` setzen und in der Firebase-Konsole den
Apple-Anbieter einrichten (Service ID, Key, Team ID), dann ist er wieder
da.

**Ohne Konfiguration ist der Button bereits jetzt sichtbar und öffnet
das fertige Modal**, zeigt darin aber einen Hinweis „Login ist in dieser
Vorschau noch nicht eingerichtet" statt kaputter Funktionalität - die
Seite bleibt also voll benutzbar, auch ohne die folgenden Schritte.

### Einmaliges Setup

> **Navigation**: Die Firebase-Konsole hat die linke Spalte umgestellt.
> Ältere Anleitungen (auch von Google selbst) sprechen noch von
> „Build → Authentication"; heute liegt **Authentication unter
> „Sicherheit"** und **Firestore unter „Datenbanken und Speicher"**.

1. Firebase-Projekt anlegen: <https://console.firebase.google.com/> →
   „Projekt hinzufügen". Der kostenlose **Spark-Tarif genügt** für Login
   und Firestore, keine Kreditkarte nötig. (Nur die optionale
   E-Mail-Benachrichtigung per Cloud Function braucht „Blaze", siehe
   unten.)
2. **Sicherheit → Authentication → Jetzt starten**, dann im Reiter
   „Sign-in method" bzw. „Anbieter" **Google** und **E-Mail/Passwort**
   aktivieren. Bei Google verlangt Firebase eine *Support-E-Mail* – die
   eigene Adresse genügt; sie erscheint im Google-Anmeldedialog.
3. **Authentication → Einstellungen → Autorisierte Domains**:
   `antdon930.github.io` eintragen. **Dieser Schritt wird gern
   vergessen** – ohne ihn funktioniert der Login lokal, aber live auf
   GitHub Pages bricht er mit `auth/unauthorized-domain` ab.
4. **Datenbanken und Speicher → Firestore Database → Datenbank
   erstellen** (Produktionsmodus). Danach unter **Rules** den Inhalt von
   `firestore.rules` (in diesem Repo) einfügen und veröffentlichen. Nur
   für „Benachrichtige mich" nötig, nicht für den Login selbst – dieser
   Schritt lässt sich also nachholen.
5. **Projektübersicht → „App hinzufügen" → Web (`</>`)**, Namen vergeben,
   registrieren. Das dort angezeigte Config-Objekt in
   `firebase-config.js` einfügen (ersetzt die `REPLACE_ME`-Platzhalter).
   **Firebase Hosting dabei nicht einrichten** – die Seite läuft auf
   GitHub Pages.
6. Committen und pushen – der Login funktioniert danach auf allen drei
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

Dass der Datumsfilter ignoriert wird, steht bewusst **nicht** im
Hinweistext (der Text ist auf „Kein Event entspricht deinen Filtern?
Lass dich per E-Mail benachrichtigen, sobald ein passendes Event
hinzugefügt wird." gekürzt) - technischer Hintergrund, der die
Aufforderung nur verwässert hätte.

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

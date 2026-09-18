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
| `places.json` | **~1,4 MB**, alle Orte + PLZ von DE/AT/CH für die Umkreissuche (nie komplett lesen) |
| `laender.json` | **69 KB**, Umrisse von DE/AT/CH für die graue Maske auf der Karte |
| `scripts/build_laender.py` | baut `laender.json` aus Natural Earth; läuft nicht im Workflow mit |
| `scripts/build_places.py` | baut `places.json` aus GeoNames; läuft nicht im Workflow mit |
| `favicon.svg`, `apple-touch-icon.png` | Seitensymbol; das PNG entsteht aus dem SVG (nach Änderung neu erzeugen) |
| `karte.html` | Leaflet-Karte, ein Marker pro Standort, gebündelt (markercluster) – filtert wie die Liste |
| `filters.js` | gemeinsamer Filterzustand von `events.html` und `karte.html` |
| `filter-ui.js`, `filter-ui.css` | die Filterknöpfe + das Panel – beide Seiten bedienen dieselben |
| `scripts/stamp_assets.py` | setzt die `?v=`-Stempel an den geteilten Dateien (**nach jeder Änderung daran laufen lassen**) |
| `kalender/*.ics` | **~4.150 Dateien**, eine je Event, fertig für den Kalender (nie alle lesen) |
| `scripts/build_ics.py` | erzeugt `kalender/` aus `events.json` und räumt verwaiste Dateien weg |
| `auth.js`, `firebase-config.js`, `firestore.rules`, `functions/` | Login + „Benachrichtige mich" |
| `scripts/scraper_lib.py` | gemeinsame Engine (robots.txt, Parsing, Dedupe, Geocoding, CLI) |
| `scripts/*_scraper.py` | ein Skript pro Quelle |
| `scripts/clean_events.py` | räumt bestehende `events.json` nach allen Regeln auf, idempotent |
| `scripts/audit_events.py` | **prüft einzelne Zeilen** und meldet Verdachtsfälle – ändert nichts |
| `scripts/geprueft.json` | **Protokoll der Einzelprüfungen** – wer hier steht, ist geprüft (`audit_events.py --offen` blendet ihn aus) |
| `scripts/update_events.py` | führt alle Scraper + Aufräumen aus (nutzt der Workflow) |
| `scripts/manual_overrides.json` | einzeln recherchierte Korrekturen an **vorhandenen** Zeilen |
| `scripts/manual_events.json` | einzeln recherchierte **fehlende** Strecken – ein Override kann keine Zeile anlegen |
| `scripts/review_reports.py` | Nutzer-Fehlermeldungen bündeln → Vorschlag → Bestätigung; `suggestions` zeigt die Hinweise auf **fehlende** Events |
| `scripts/pending_overrides.json` | Vorschläge, die auf die Bestätigung des Nutzers warten |
| `scripts/test_scraper_lib.py` | Regressionstests, ohne Netzwerk |
| `scripts/smoke_test_frontend.py` | Rauchtest der Seite in Chromium (lokaler Server, Handybreite) |
| `impressum.html`, `datenschutz.html` | Pflichtseiten, Anschrift steht – **es fehlt nur die E-Mail-Adresse** (gelb markiert); von jeder Seite aus verlinkt |
| `seite.css` | Stile der beiden Textseiten (ohne `?v=`-Stempel, Begründung in der Datei) |
| `vendor/` | Leaflet, markercluster und die Firebase-SDKs – **selbst gehostet**, kein CDN |
| `scripts/bench_frontend.py` | misst das Tempo der Liste – heute und mit einem synthetischen Stand (`--faktor 5` = ~20.000 Events); fasst `events.json` nie an |

**`events.json` NIE komplett lesen** – das frisst den halben Kontext. Immer
gezielt abfragen:

```bash
python3 -c "import json; ev=json.load(open('events.json')); print(len(ev))"
```

## Vor jedem Commit

```bash
python3 scripts/test_scraper_lib.py     # muss grün sein
```

Der Test prüft auch, ob `kalender/` zu `events.json` passt. Schlägt er
dort an (typisch nach einem Datenlauf), hilft:

```bash
python3 scripts/build_ics.py            # und die Dateien mitcommitten
```

Wurde `filters.js`, `filter-ui.js` oder `filter-ui.css` angefasst,
**vorher** stempeln (der Test schlägt sonst fehl und sagt es auch):

```bash
python3 scripts/stamp_assets.py
```

`node --check` über die Inline-Skripte und die geteilten JS-Dateien
steckt **im Test** (`test_js_syntax`) – von Hand nötig ist es nicht mehr.
Bei Änderungen an `events.html`/`index.html`/`karte.html` zusätzlich den
Rauchtest laufen lassen:

```bash
python3 scripts/smoke_test_frontend.py     # startet selbst einen Server
```

Er öffnet die drei Seiten auf Handybreite in Chromium und prüft 143 Punkte:
Laden ohne Fehler und ohne 404, Kopfangaben, kein Überlauf, Aufklappen der
zusammengefassten Veranstaltungen, Filter-Panel, Kalenderdatei hinter dem
Knopf, Bündelung der Marker (Summe der Bündel-Zahlen = Kopfzeile),
Ausgangspunkt ungebündelt, das Fenster der Tabelle (nur ein Schub im
DOM, volle Trefferzahl, Knopf hängt nach), Teilen eines Events (was an
`navigator.share` geht und der Rückweg über den geteilten Link),
Impressum und Datenschutz (erreichbar von jeder Seite, Platzhalter
sichtbar, Sprachumschalter), der Abo-Dialog (Knopf, Zusammenfassung,
drei Rhythmen, `?abos=1`, Null-Treffer-Box, die Filterleiste darin –
vorbelegt, Panel im Dialog und davor, Liste dahinter unberührt),
Tastaturbedienung (ein Tab-Stopp, Pfeile,
Enter **auch auf einer aufklappbaren Veranstaltung**, Leertaste,
Escape, Fokusfessel der Dialoge), „Wir haben dein Event nicht?"
(Knopf unter der Liste, die drei Felder, eigene Fehlermeldungen, beide
Wege bei null Treffern), gleiche Zeilenhöhe aller Zeilen und das
Dezimaltrennzeichen in DE und EN, die **Mastersuche** (Ort UND Name,
Chip, `?s=` in der Adresse, das ✕), das **zweizeilige Datum** bei
mehrtägigen Rennen, der **Events-Knopf der Startseite** (gleiches Ziel
wie „Events entdecken“, links von der Anmeldung), der **Kartenrahmen**
(Herauszoomen hat eine Grenze, keine zweite Weltkarte daneben), die
**graue Maske** (vorhanden, unter den Markern, fängt keine Klicks ab,
Länder ausgespart) und der Popup-Link ohne Pfeil, Filter über den Weg
Liste → Karte → Liste. Ohne Playwright bricht er
mit Hinweis ab (Rückgabewert 0). Chromium liegt unter
`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`; in dieser Sandbox
blockt der Proxy CDNs per TLS – mit `args=['--ignore-certificate-errors']`
laden Leaflet und Firebase (das Skript setzt es schon).

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

   **„Trail" und „Cross" sind EINE Kategorie: „Trail/Cross".** Beides ist
   Geländelauf, die Quellen benennen dieselbe Strecke mal so, mal so, und
   eine verlässliche Trennung gibt es nicht (so vom Nutzer entschieden).
   Die beiden Stichwort-Zeilen bleiben trotzdem **getrennt und an ihrer
   Stelle** – ihre Position ist bedeutungstragend: „trail" steht VOR der
   Berg-Regel, „cross" DAHINTER. Ein „Bergtrail" ist damit Trail/Cross,
   ein „Alpiner Crosslauf" bleibt Berglauf. Nicht zu einer Zeile
   zusammenziehen. Bestehende Daten zieht
   `clean_events.merge_trail_cross()` nach (idempotent); die Filterliste
   steht in `filter-ui.js` (`ART2_BY_ART1`), die Übersetzung in
   `filters.js` – `test_scraper_lib.py` prüft, dass beide dieselben Werte
   kennen.
7. **Duplikate**: gleiches Datum + ähnlicher Name + Ort ≤ 30 km + kompatible
   Distanz (`is_same_event()`). Gleiche Veranstaltung mit *unterschiedlichen*
   Distanzen bleibt absichtlich getrennt.
   „Ähnlicher Name" hat fünf Wege (siehe `_same_name()`); der fünfte ist
   neu: **gleicher Veranstaltungsname ohne Wettbewerb gerechnet, und
   höchstens eine Seite nennt einen Wettbewerb, bei gleicher `art1`**.
   Damit fiel der doppelte SAARathon (42,2 km, einmal mit Portallink)
   weg. Beide Zusatzbedingungen sind nötig: Nennen BEIDE einen
   Wettbewerb, ist das Label das Unterscheidende („10 km Lauf" vs.
   „10 km Nordic Walking"), und Lauf vs. Wandern über dieselbe Strecke
   sind zwei Einträge.
   **Was das Dedupe NICHT erkennt**: Zwei Schreibweisen ohne ein
   gemeinsames Wort. „13. Fichtelgebirgstrailrun" und „Fichtellauf"
   (19.09.2026, Gefrees, beide 21 km) sind dieselbe Veranstaltung – der
   Veranstalter nennt sie „Fichtellauf (Trail + Nordic Walking)", der
   Trail Run IST der Fichtellauf. Kein Namensvergleich kann das sehen.
   `clean_events.report_moegliche_duplikate()` **meldet** solche Paare
   (gleicher Tag + Ort + Distanz, verschiedene Namen; 60 Stück), geprüft
   und ausgeschlossen wird einzeln über `manual_overrides.json`.
   **Nicht automatisch zusammenführen**: Ein Straßenlauf und ein
   Trailrun desselben Veranstalters am selben Tag über dieselbe Distanz
   sind ein häufiger, echter Fall – die Regel würde ein echtes Rennen
   unsichtbar machen.

8. **Zeitrennen haben `dauer_h`, nicht `laenge_km`.** Ein 24-Stunden-Lauf
   hat keine feste Strecke; die Dauer in Stunden steht in `dauer_h` und
   erscheint in derselben Spalte („24 h"). Eine bekannte Distanz hat in der
   Anzeige Vorrang – „24h Mad Chicken Run | Marathon, 42 km" ist eine
   42-km-Strecke, das „24h" ist der Veranstaltungsname.
   `parse_duration_h()` sichert gegen „229 hm" (Höhenmeter) und
   „Zeitlimit 6 Stunden" (Zielschlusszeit) ab; nachgetragen wird nur bei
   Einträgen ohne Distanz (`clean_events.fill_duration()`).
   Filter: Kategorie „Zeitrennen" im Länge-Panel, gespiegelt in
   `functions/index.js` (`ZEIT_CATEGORY_KEY`).

   **Ein „Stundenlauf" ist eine Stunde, ein „Halbstundenlauf" eine
   halbe.** Das Muster `_DURATION_PATTERN` verlangt eine ZAHL vor dem
   Wort – der klassische Ein-Stunden-Lauf heißt aber einfach
   „Stundenlauf". 13 Veranstaltungen standen dadurch ganz ohne Maßzahl
   in der Liste. `_STUNDENLAUF_OHNE_ZAHL` fängt das jetzt ab, **die
   Reihenfolge der beiden Zeilen ist bedeutungstragend**: „Halb·
   stundenlauf" enthält „stundenlauf" als Teilzeichenkette und wäre
   sonst doppelt so lang. Definition gegen Wikipedia/Brockhaus geprüft
   (möglichst viele Runden in einer Stunde); `test_stundenlauf` hält
   beides fest.
   Steht bei einem Zeitrennen trotzdem eine Distanz („Emder
   Stundenlauf – 10 km"), meldet das `audit_events.py` – `fill_duration()`
   füllt bewusst nur, wo gar nichts steht.

   **Die Rundenlänge ist keine Renndistanz** – inzwischen die vierte
   Begegnung mit dieser Fehlerklasse (Backyard-Runde, „Running Paule
   Marathon" 6,4 km, „Warendorfer Weihnachtslauf" 6 km, „Borsig
   Halbmarathon" 5,3 km, „Helgoland Marathon" 5,2 km). Das Label
   verrät sie: Nennt es „N Runden à X km" und steht im Feld X statt
   N·X, ist die Runde gespeichert (`audit_events.RUNDEN_MAL_RE`).
   **Eine STAFFEL ist etwas anderes** (`STAFFEL_RE`): Bei „2x5 km
   Staffel" läuft man wirklich 5 km, und die Staffel ist ein eigener
   Wettbewerb. Ohne diese Unterscheidung meldete die Regel sechs
   Staffeln als Fehler, die keine waren.
9. **`art2` „Backcountry Ultra"** (nur Laufen). Zwei Stichwörter mit
   **unterschiedlicher Position** in `ART2_KEYWORDS_LAUFEN` – das ist
   Absicht, nicht Zufall:
   - „backcountry" steht **VOR** „Trail": ein „Backcountry Ultra Trail"
     ist ein Backcountry Ultra.
   - „backyard" (und „last man/person standing") steht **NACH** „Trail":
     ein reiner „Backyard Ultra" ist Last-Man-Standing und damit
     Backcountry Ultra, ein „Backyard Ultra **Trail**" dagegen ein
     Trailrun, der das Wort nur im Namen trägt.

   So ausdrücklich vom Nutzer entschieden. Reihenfolge nicht „aufräumen".

   **Die Backyard-Runde ist keine Distanz.** Ein Backyard läuft dieselbe
   Runde (klassisch 4,167 Meilen = 6,706 km, in den Quellen „6,7" oder
   „7 km") zur gleichen Stunde, bis nur noch eine Person weiterläuft.
   Deshalb:
   - Länge-Spalte zeigt **„–"**, wenn das Rennen zeitlich offen ist, und
     **„24 h"**, wenn es auf 24 Stunden begrenzt ist.
   - `clean_events.clear_backyard_lap_km()` nimmt bei Backcountry-Ultra-
     Einträgen eine Distanz **bis 10 km** heraus (das ist die Runde; 18
     Einträge betroffen). Größere Angaben (34/67/80 km) bleiben stehen
     und werden nur **gemeldet** – unklar, ob Zielvorgabe, Teamwertung
     oder Runde.
   - Ein Override darf jetzt auch `dauer_h` und `wettbewerb` setzen, und
     `null` löscht ein Feld – so wurde „Murr BackYard 12h" auf 12 h ohne
     Distanz gebracht (die beiden Zeilen mit 67/34 km sind dadurch zu
     einer verschmolzen). Offen bleibt nur noch „RET-Team Backyard
     80 km".
   - Nennt ein Wettbewerb eine Dauer, verwirft `parse_competitions()`
     eine km-Angabe daneben („24h Solo auf einer 2km MotoCross-Strecke
     (2km)" → 24 h, keine 2 km). Vorher wurde daraus ein 2-km-Eintrag,
     den die 5-km-Mindestdistanz gleich wieder verwarf – so fehlten die
     vier 24h-Wettbewerbe des Mad Chicken Run komplett.
10. **Vergangene Events raus.** Maßgeblich ist `datum_ende` (sonst
   `datum_start`); der heutige Tag bleibt, ein mehrtägiges Rennen bleibt bis
   zu seinem letzten Tag, ein Event mit unlesbarem Datum wird nicht
   gelöscht. An drei Stellen: `scraper_lib.filter_past()` beim Einsammeln,
   `clean_events.drop_past_events()` rückwirkend, und `dropPastEvents()`
   beim Laden in `events.html`/`karte.html` (zwischen zwei Läufen liegt
   eine Woche).

11. **Die Sportart kommt nicht von der Quelle.** Alle vier aktiven
   Quellen sind **Laufkalender**; ihre `SiteConfig` trägt
   `default_art1 = "Laufen"` – und damit stand jeder Triathlon als
   Laufveranstaltung in der Liste. Aufgefallen ist es dem Nutzer an einer
   Zeile, die es nicht geben darf: „Ironman 70.3 Kraichgau · Laufen ·
   Straße". Bei einem Ironman kann man sich nicht für den Lauf allein
   anmelden. 132 Einträge waren betroffen.
   - `guess_art1()` (`scraper_lib.py`, `ART1_KEYWORDS`) überschreibt die
     Voreinstellung der Quelle, wenn der Name eindeutig eine andere
     Sportart nennt. `clean_events.fix_multisport_art1()` holt den
     Bestand nach (idempotent, respektiert Overrides).
   - **Nur eindeutige Stichwörter.** „Triathlon" und „Ironman" sind
     eindeutig, ein „Rad" im Namen ist es nicht („Radrennbahn-Lauf").
     Was nicht eindeutig ist, bleibt draußen – dieselbe Linie wie bei
     der wichtigsten Lektion unten.
   - **„Triathlon" ist die Mehrsport-Schublade.** Duathlon
     (Laufen-Rad-Laufen), Aquathlon (Schwimmen-Laufen), SwimRun und
     Quadrathlon sind keine Triathlons im Wortsinn, gehören aber zur
     selben Familie; die Seite hat nur vier Sportarten. Die genaue Form
     steht in **`art2`** (`ART2_KEYWORDS_TRIATHLON`): Straße, Cross,
     Duathlon, Aquathlon, Swimrun, Quadrathlon, Indoor. Damit ist auch
     `ART2_BY_ART1['Triathlon']` gefüllt, das bis dahin fehlte.
   - **Das Format steht vor dem Gelände**: Ein „Baltic X Cross Duathlon"
     ist ein **Duathlon**, der im Gelände stattfindet – danach filtert
     jemand, nicht nach „Cross". Deshalb stehen Swimrun/Aquathlon/
     Duathlon in der Liste VOR „Cross". Dieselbe Sorte Reihenfolge wie
     bei `ART2_KEYWORDS_LAUFEN`, also nicht „aufräumen".
   - **`guess_art2(text, config, art1)`** nimmt die Kategorie-Liste zur
     Sportart (`ART2_LISTEN`). Ohne das dritte Argument bleibt es bei
     der Lauf-Liste – ältere Aufrufe funktionieren unverändert, ein
     Cross-Triathlon bekäme dort aber „Trail/Cross", also eine
     Laufkategorie an einer Nicht-Laufveranstaltung.
   - **Zwei Meldungen, keine automatische Korrektur** (siehe Lektion
     unten): `report_multisport_teilstrecken()` findet Zeilen, die nur
     eine Teilstrecke beschreiben („Ironman Hamburg · 42,2 km Laufen
     entlang der Alster" – der Laufteil eines Triathlons, keine
     Anmeldemöglichkeit; 5 Fälle), und `report_triathlon_distanzen()`
     Zeilen, deren Distanz zu keinem gängigen Format passt (~26, ~52,
     113, 226 km; 44 Fälle, nur für den klassischen Triathlon – ein
     15-km-SwimRun ist normal). Beide gehören einzeln geprüft und als
     Override eingetragen.

12. **Das Wettbewerbs-Label darf eine andere Sportart nennen als die
   Veranstaltung.** Der „Drei Talsperren Marathon" hat neben Marathon,
   Halbmarathon und 8 km auch „Rad 100 km", „Rad 50 km" und „Rad 30 km" -
   laut Ausschreibung eigenständige Wettbewerbe. Bei uns standen sie als
   **Lauf** in der Liste, also als 100-km-Lauf.
   `clean_events.fix_fremde_sportart_im_wettbewerb()` stellt das um. Die
   Abgrenzung zur Triathlon-Teilstrecke ist der ganze Aufwand daran, und
   sie steckt in der **Verbform** des Labels:

   | Label | heißt | Folge |
   |---|---|---|
   | „Rad 100 km", „Mountainbike Rennen 42 km" | ein Rennen, das man bucht | `art1` → Fahrrad |
   | „21,5 km Radfahren", „7,3 km Laufen", „Run 1" | eine Etappe, die man absolviert | unangetastet |

   Geprüft wird nicht die einzelne Zeile, sondern die ganze
   **Veranstaltung** (`TEILSTRECKEN_VERB_RE`,
   `_ist_mehrsport_veranstaltung()`): Trägt IRGENDEINE ihrer Zeilen eine
   Verbform, bleibt alles stehen. An den zwölf Veranstaltungen, die die
   Regel sonst getroffen hätte, trennt das sauber - Aluman, RömerMan,
   Trifun Pellworm, Mainathlon, Dirty Race und Speck Race sind
   Triathlons und bleiben; Drei Talsperren, Possenlauf, Elsterlauf,
   Frickinger Apfellauf und Schneeglöckchen-Lauf haben wirklich ein
   eigenes Radrennen. Die erste Fassung der Regel hatte nur das Label
   geprüft und aus sechs Triathlon-Etappen Radrennen gemacht.
   **`art1 == "Triathlon"` wird nie überschrieben.**

   Damit stehen die **ersten Radrennen überhaupt** in `events.json` (9).
   `ART2_KEYWORDS_FAHRRAD` gibt es deshalb jetzt - **ohne
   Voreinstellung**: „Mountainbike" wird zu Mountainbike, „Rad 100 km"
   bleibt ohne Kategorie. Aus „Rad 100 km" geht der Untergrund nicht
   hervor, und eine geratene Kategorie ist schlechter als keine - sie
   sieht aus wie eine Angabe.

13. **Zwei Rennen in einer Zeile.** „15 km / 21 km Crosslauf" ist nicht
   ein Rennen über 21 km. `guess_distance_km()` nimmt bei mehreren Zahlen
   die größte - der 15-km-Lauf des Limberglaufs Ranis **fehlte dadurch
   komplett** in der Liste. `_trenne_doppelte_distanzen()` teilt solche
   Zeilen jetzt vor `parse_competitions()`.
   Bewusst eng: Das Label muss **mit** „A km / B km" anfangen. „19 km
   (14 + 5 km)", „100 km (10 x 10 km)" und „3 Runden je 15,5 km" sind
   Aufteilungen derselben Strecke, kein zweites Rennen.
   **Ein fehlendes Event ist die unangenehmere Sorte Fehler**: Eine
   falsche Zahl sieht man, eine fehlende Zeile nicht.

14. **HYROX gehört nicht in die Liste.** Die Seite führt Laufen,
   Schwimmen, Fahrrad und Triathlon. HYROX ist achtmal ein Kilometer
   Laufen im Wechsel mit acht Kraftstationen (Sled Push, Burpees, Wall
   Balls, Rudern) – man kann sich dafür nicht als Läufer anmelden.
   Vom Nutzer am 18.09.2026 entschieden, ausdrücklich „erst einmal".
   - `NICHT_AUSDAUER` in `scraper_lib.py` hält die Liste, angewendet
     beim Einsammeln (`filter_nicht_ausdauer`) und rückwirkend
     (`clean_events.drop_nicht_ausdauer`) – dieselbe Aufteilung wie bei
     den vergangenen Events.
   - **Die Liste ist winzig und leicht umzudrehen**: Zeile heraus, und
     beim nächsten Datenlauf sind die Events wieder da.
   - **Nur eindeutige Markennamen.** Ein Stichwort wie „Fitness" oder
     „Hindernis" wäre falsch: Ein Hindernislauf (Spartan, XLETIX,
     CrossDeLuxe, Muddy Angel, Tough Mudder) IST ein Laufformat und
     bleibt. `test_nicht_ausdauer` hält beide Seiten fest.
   - Jeder Ausschluss wird **gemeldet**, nicht stillschweigend gemacht.

### Die wichtigste Lektion

**Keine automatische Löschregel auf Heuristik-Basis.** Eine Regel, die
widersprüchliche Distanzen automatisch entfernen sollte, traf bei 7 Fällen
2 echte Rennen (Halbmarathon des NRZ Klosterlauf, 42-km-Strecke der Mud
Masters) – die Streckenlisten der Quellen sind nicht verlässlich vollständig.
Solche Fälle daher nur **melden** (`report_suspicious_distances()`), einzeln
per Websuche prüfen und bestätigte Fehler mit `"exclude": true` in
`manual_overrides.json` eintragen. Schlüssel dort:
`"<Name>|<Datum>|<km>"` (distanzgenau) oder `"<Name>|<Datum>"`.

**Die Distanz im Schlüssel wird mit `:g` formatiert** – also `|21`, nicht
`|21.0`. Ein Schlüssel in der falschen Schreibweise wird
**stillschweigend nie gefunden**: Der Override steht in der Datei, sieht
richtig aus und tut nichts. Genau das ist beim Eintragen des
Fichtel-Duplikats passiert. `test_override_schluessel` prüft jetzt jeden
Schlüssel gegen `override_keys()`.

Zu viel gelöscht ist schlimmer als eine Zahl zu großzügig – es ist unsichtbar.

### Fehlende Strecken nachtragen (`scripts/manual_events.json`)

**Ein Override ändert eine Zeile, er legt keine an.** Beim Durchgehen
der Streckenlisten kam derselbe Fall immer wieder: Die Veranstaltung
steht in der Liste, aber nicht alle ihre Wettbewerbe. Die Bühlauer
Winterlaufserie hat fünf Termine à vier Distanzen – wir hatten einen
Termin. Der proWissen-Lauf hat 5 km UND 10 km – wir hatten die 10 km.
Und ein fehlendes Event ist die unangenehmere Sorte Fehler: Eine falsche
Zahl sieht man, eine fehlende Zeile nicht.

Deshalb `scripts/manual_events.json` – das Gegenstück zu
`manual_overrides.json`, gelesen von `clean_events.add_manual_events()`.
Fünf Dinge daran:

- **Nur einzeln geprüft.** Jeder Eintrag ist an der offiziellen
  Ausschreibung belegt, die Stelle steht als `_quelle`/`_note` in der
  Datei. Dieselbe Linie wie bei den Overrides: geraten wird nie.
- **Felder mit `_` am Anfang sind Dokumentation** und landen nicht in
  `events.json`.
- **Doppelt kann nichts entstehen**: Übersprungen wird jeder Eintrag,
  zu dem `is_same_event()` schon eine Zeile findet – also genau die
  Duplikat-Definition des Projekts. Damit ist der Schritt idempotent
  und verträgt sich mit einem späteren Scraper-Lauf, der dieselbe
  Strecke selbst einsammelt: Dann greift er nicht mehr.
- **Der Name muss der sein, den die Veranstaltung nach dem Aufräumen
  TRÄGT** (`unify_event_names` kann ihn vereinheitlichen) – sonst
  erkennt `is_same_event()` die eigene Zeile beim nächsten Lauf nicht
  wieder und legt sie erneut an. Real passiert: Die nachgetragene
  Lindensee-Strecke heißt am 21.11. „44. Lindenseelaufserie".
- **`add_manual_events()` läuft NACH `apply_overrides()`.** Ein Override
  mit dem Schlüssel `"<Name>|<Datum>"` trifft sonst jede Strecke dieser
  Veranstaltung an diesem Tag – auch eine gerade nachgetragene. Beim ASV
  Duisburg hat genau das die neue 5-km-Zeile auf 10 km gesetzt und damit
  zum Duplikat gemacht.

Danach laufen die nachgetragenen Zeilen durch **dieselben** Regeln wie
alles andere (Kategorie, Rundung, Mindestdistanz, vergangene Events,
Zusammenführen). `test_manuelle_events` hält Pflichtfelder und
Idempotenz fest.

### Was die Einzelprüfung von 200 Events gelehrt hat (18.09.2026)

Der Nutzer hat darum gebeten, 200 Events ganz genau anzusehen. Geprüft
wurden die ersten 200 nach Datum (18./19.09.2026). Von 80 maschinellen
Verdachtsfällen blieben nach der Einzelprüfung **7 echte Fehler** übrig;
alle sind behoben. Wichtiger als die sieben sind vier Lektionen:

1. **Die Prüfregel irrt öfter als die Daten.** Drei der vier größten
   Fundgruppen waren Fehler meiner *Prüfung*:
   - „Wochentag Mo-Fr" (45 Treffer) - die 200 Events liegen auf Fr/Sa,
     und ein Freitagabend-Stadtlauf ist völlig normal. Regel auf Mo-Do
     eingeengt.
   - „‚Halbmarathon', aber Distanz passt nicht" - der *Veranstaltungs*name
     ist „Bernburger Halbmarathon", der *Wettbewerb* sind 12 km. Die
     Regel muss das **Label** lesen, nicht den Namen.
   - „Cross im Namen, Kategorie Hindernis" - der „Family-CrossDeLuxe
     Leipzig" ist tatsächlich ein Hindernislauf. Die Regel
     „spezifisch vor generisch" hat richtig gearbeitet.

2. **Eine naheliegende „Verbesserung" hätte 57 richtige Einordnungen
   zerstört.** `berglauf` steht ohne Wortgrenze in
   `ART2_KEYWORDS_LAUFEN`, und „Lim·berglauf" trifft darauf. Der Reflex
   war, `\bberglauf\b` daraus zu machen. Gemessen: Von 58 betroffenen
   Events sind 57 **echte** Bergläufe - „Belchen·berglauf",
   „Turm·berglauf", „Nebelhorn·berglauf". Deutsche Komposita sind hier
   die Regel, nicht die Ausnahme. **Die fehlende Wortgrenze bleibt.**
   Vor jedem „das sieht falsch aus" erst zählen, was die Änderung
   anrichtet.

3. **Koordinaten sind Daten, keine Dekoration.** Der „Bodensee
   Marathon" lag mit seiner Marathon-Strecke auf 49.07/10.14 - das ist
   Franken, 168 km vom Bodensee. Der Ortsname war auf „Kressbronn"
   verkürzt (statt „Kressbronn am Bodensee"), und dafür fand der
   Geocoder einen gleichnamigen Ort anderswo. Umkreissuche und Karte
   bauen allein darauf auf: Wer im Umkreis von Friedrichshafen suchte,
   bekam den Marathon nicht zu sehen.
   Neu deshalb: **`lat`/`lon` dürfen im Override stehen**
   (`OVERRIDE_FIELDS`, jetzt EINE Liste für beide Wege statt zweier),
   und `report_widerspruechliche_koordinaten()` meldet Veranstaltungen,
   die am selben Tag an zwei über 30 km entfernten Punkten liegen.

   Der Bericht fand **neun weitere Fälle**, alle einzeln an der
   offiziellen Seite geprüft und behoben (der Bericht meldet jetzt 0):
   Steverlauf → Senden in Westfalen statt bei Neu-Ulm (400 km);
   Pokallauf → Roßbach bei Braunsbedra statt im Westerwald;
   Quickborn → Kreis Pinneberg statt Dithmarschen; Cross der Deutschen
   Einheit → Weißensee in Thüringen statt Berlin-Weißensee;
   Hohenloher Silvesterlauf → Wallhausen-Hengstfeld statt Wallhausen an
   der Nahe; Laubacher Ramsberglauf → Laubach in Hessen statt im
   Hunsrück; Rodenbacher Lauftag → Rodenbach im Main-Kinzig-Kreis statt
   bei Kaiserslautern; Zeiler Waldmarathon → Zeil am Main statt Raum
   Frankfurt; Königsforst-Marathon → Bergisch Gladbach statt bei Kassel.

   Zwei Nachwirkungen, die zeigen, wie weit so ein Fehler reicht:
   - Beim **Königsforst-Marathon** war die falsch verortete Zeile ein
     unerkanntes Duplikat: Die Orts-Bedingung der Duplikat-Erkennung
     erlaubt 30 km, 158 km sprengen sie. Mit den richtigen Koordinaten
     fielen die beiden 42,2-km-Zeilen zusammen. Die Veranstaltung hat
     jetzt genau die drei Strecken, die ihre Ausschreibung nennt.
     Damit trägt auch die alte Begründung für den **Ort im
     ICS-Dateinamen** nicht mehr - sie steht an vier Stellen und ist
     auf „TEAG - Legend of Cross - Mühlberg" umgestellt.
   - Beim **Rodenbacher Lauftag** wäre die 50-km-Strecke fast
     gelöscht worden: Die Cup-Seite main-lauf-cup.de listet sie nicht.
     Die Ausschreibung des Veranstalters nennt sie sehr wohl
     (50-km-Harry-Arndt-Lauf, Start 9:31 Uhr). Wieder dieselbe Lektion:
     **Streckenlisten der Quellen sind nicht verlässlich vollständig.**

4. **Dieselbe Veranstalter-SEITE ist ein starkes Signal - und trotzdem
   keine Regel.** „45. Hörnle Berglauf Bad Kohlgrub" und „Hörnlelauf
   Bad Kohlgrub" tragen dieselbe vollständige Adresse
   (`…veranstaltungen.php?id=94`), dasselbe Datum, dieselben 7 km - ein
   Rennen. Durchgerechnet über den ganzen Bestand hätte diese Regel aber
   **48 Paare** verschmolzen, darunter echte Wettbewerbe: den Marathon
   des „24h Mad Chicken Run" mit dem 24-Stunden-Rennen, den „Kolberger
   Berglauf" mit der Wanderung über dieselbe Strecke, „Tour Werder
   61,8 km" mit „Tour City Berlin 63,0 km". Also
   `report_gleiche_seite_gleiche_distanz()` - **melden, nicht
   zusammenführen** (36 Fälle offen). Die DOMAIN allein bleibt auch
   weiterhin kein Kriterium, siehe `_same_name()`.

Die sieben behobenen Fehler: Bodensee Marathon falsch verortet; ONW-Lauf
Dannenberg doppelt (mit der Jahreszahl 2025 im Namen); Hörnlelauf Bad
Kohlgrub doppelt (und als „Straße" statt Berglauf); „BFUTR EXTREME" mit
18 km/Straße statt der 105 km des Black Forest ULTRA Trail Run, den wir
bereits vollständig hatten; drei Radrennen des Drei Talsperren Marathons
als Lauf geführt; der 15-km-Lauf des Limberglaufs Ranis fehlte ganz.
Jeder Fall gegen die offizielle Ausschreibung geprüft, die Belege stehen
als `_note` in `manual_overrides.json`.

**Was in den 200 bleibt**: 21 Einträge mit einem Portallink statt der
offiziellen Seite. Das ist kein falscher Datensatz, nur ein schlechterer
Link - und Datenregel 2 verbietet das Raten. Er wird ersetzt, sobald
eine Quelle die offizielle Seite nennt (`update_existing_event()`).

### Zweiter Durchgang: die Events 201-400 (18.09.2026)

Auf Wunsch des Nutzers gleich weiter mit den nächsten 200 (19./20.09.2026).
Von 72 maschinellen Verdachtsfällen blieben **sechs echte Fehler** - und
ein Fund, der mit den Daten gar nichts zu tun hatte (siehe unten).

Die sechs: der Kinderlauf des Karlsfelder Seelaufs stand mit **21,1 km**
in der Liste (er ist 999 m lang - die Distanz war das Maximum aus der
Streckenliste); der Stadtlauf Erding stand unter **drei** Namen
(„23. Stadtlauf Erding 2026", „Erdinger Stadtlauf", „Stadtlauf Erding");
der „Alagastlauf" doppelt, weil laufen.de ihn als „Alagastaluf" führt
(ein fehlendes l); der Laacher See Naturlauf trug das Label „9 km" bei
8,5 km echter Strecke; und der „Running Paule Marathon" stand mit
**6,4 km** da - das ist die RUNDENLÄNGE (4× 6,4 km + 4× 4,2 km = ein
Marathon), dieselbe Fehlerklasse wie die Backyard-Runde.

Drei Lektionen:

1. **Ein Trennzeichen kostete elf Veranstaltungen.** `ART1_KEYWORDS`
   enthielt `swim ?run` - nur ein optionales LEERZEICHEN. „Wunnebad
   Swim&Run", „DSW Swim & Run", „Kronberger Bike+Run" und „Run and Bike
   Berlin" blieben deshalb Laufveranstaltungen. Jetzt steht dort
   `_ZWEI_SPORTARTEN` (`&`, `+`, „and", „und", Bindestrich), und
   Run&Bike/Bike&Run ist als Duathlon-Format dabei.
   **Nicht** daraus geworden ist das naheliegende Stichwort „athlon":
   Unter den zwölf Events mit „athlon" im Namen sind die „Decathlon
   Hybrid Series" (der Sporthändler), der „Weinathlon" und der
   „Eschathlon Halbmarathon". Dieselbe Linie wie bei „berglauf" im
   ersten Durchgang - erst zählen, was eine Regel anrichtet.
   `test_zwei_sportarten_im_namen` hält beide Seiten fest.

2. **Ein Override kann nicht umbenennen.** Beim Stadtlauf Erding heißt
   die Veranstaltung offiziell „Stadtlauf Erding", die brauchbarste
   Zeile aber „Erdinger Stadtlauf" (sie hat die offizielle Seite UND
   beide Strecken). Der Name ist Teil des Override-Schlüssels, also
   ging nur: die Duplikate ausschließen und den Namen stehen lassen.
   Falls das öfter vorkommt, wäre ein `name`-Feld im Override der
   nächste Schritt - dann muss `find_override` aber über den ALTEN
   Namen suchen und darf den Schlüssel nicht mit sich selbst brechen.

3. **Eine Datenänderung hat einen Frontend-Fehler aufgedeckt, der nichts
   mit Daten zu tun hatte.** Nach dem Entfernen von fünf Zeilen war der
   Rauchtest rot: „Enter springt in die Angaben". Kein Zufall und kein
   Wackler - **Enter klappte auf einer Veranstaltungszeile nur um**,
   statt in den Detailbereich zu springen, und ein Tastatur-Nutzer kam
   bei jeder Veranstaltung mit mehreren Strecken nie an Kalenderdatei
   und Veranstalter-Link. Der Rauchtest hatte den Fall bis dahin nur
   zufällig NICHT getroffen (am Ende des Fensters lag immer eine
   einzelne Strecke). Behoben in `events.html`, und der Fall steht
   jetzt ausdrücklich im Rauchtest - siehe Frontend-Fallen,
   „Tastaturbedienung".
   Die Lehre: Ein roter Test nach einer Datenänderung ist nicht
   automatisch „die Daten haben sich verschoben". Erst nachsehen.

**Was auch hier bleibt**: 56 Portallinks und 11 Einträge ohne
Distanzangabe. Beides sind keine falschen Daten - die Quelle nennt sie
schlicht nicht, und Datenregel 2 verbietet das Raten.

### Was davon den großen Datenlauf überlebt (ehrliche Bilanz)

Der Nutzer hat gefragt, ob bei den erwarteten 20.000+ Events weniger
Fehler passieren. Die 13 gefundenen Fehler, danach sortiert, was beim
nächsten Lauf wirklich geschieht:

| | Klasse | Wirkung |
|---|---|---|
| **3** | Rad-Wettbewerbe, „A km / B km", Swim&Run/Bike+Run | **verhindert** – eine Regel in `scraper_lib.py`/`clean_events.py` greift automatisch |
| **3** | falsche Koordinaten, Duplikate über dieselbe Seite, Rundenlänge | **gemeldet** – `clean_events.py` findet sie, ein Mensch entscheidet |
| **5** | BFUTR, Kinderlauf mit 21 km, Tippfehler-Duplikat, Label ≠ Distanz, Jahreszahl im Namen | fand nur ein **Wegwerf-Skript** |

Die letzte Zeile war die eigentliche Lücke: Diese fünf hätte beim
großen Datenlauf **niemand** gefunden. Deshalb gibt es jetzt
`scripts/audit_events.py` im Repo - dieselben Prüfungen, dauerhaft,
mit `test_audit_pruefungen` abgesichert. Der Test hält vor allem die
**Gegenproben** fest (Jugendlauf über 5,6 km, „Bernburger
Halbmarathon" mit 12-km-Label, „Winterlaufserie 2026/2027",
Freitagslauf, „(L)auf zur Venus", Hindernislauf mit „Cross" im Namen):
Drei der vier größten Fundgruppen waren Fehler der REGEL, nicht der
Daten - und genau die rutschen beim nächsten Umbau zurück, wenn sie
nicht festgenagelt sind.

**Was sich damit NICHT löst**, und das ist die ehrliche Grenze:

- **Ein Override gilt für genau einen Termin.** Der Schlüssel ist
  `<Name>|<Datum>|<km>` - die Ausgabe 2028 derselben Veranstaltung
  trifft er nicht mehr. Die 76 Einträge sind Einzelfallpflege, keine
  Regel.
- **Die Meldungen skalieren mit.** Heute stehen 168 offene Hinweise
  aus `clean_events.py` bei 4.335 Events; bei 20.000 werden daraus
  rund 800. Jeder einzelne gehört gegen die offizielle Ausschreibung
  geprüft - das ist Arbeit für den Nutzer, nicht für eine Regel.
  `audit_events.py` meldet im bisher ungeprüften Bestand zusätzlich
  1.536 Fälle, davon aber 944 Portallinks und 312 ohne Distanz (beides
  keine Fehler). Scharf sind rund 70.
- **Die Trefferquote bleibt ähnlich.** In beiden geprüften Hundertern
  waren ~3 % der Zeilen falsch. Was die neuen Regeln abfangen, war
  etwa ein Drittel davon - bei 20.000 Events also grob 400 statt 600
  Fehler. Deutlich weniger, aber nicht wenige.

Der wirksamste Hebel für den großen Lauf ist deshalb **nicht** noch
eine Regel, sondern: nach dem Datenlauf `audit_events.py` laufen
lassen, die scharfen Kategorien durchgehen (nicht die Portallinks) und
die bestätigten Fälle als Override eintragen.

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

Fehlt eine Veranstaltung ganz, kommt sie über „Wir haben dein Event
nicht?" (Collection `eventSuggestions`) – angesehen mit:

```bash
python3 scripts/review_reports.py suggestions --credentials <serviceaccount.json>
```

Auch hier gilt: nur ansehen. Was daraus wird (Scraper oder Override),
entscheidet der Nutzer, nachdem robots.txt und Nutzungsbedingungen der
Quelle geprüft sind.

Der Vorschlag bleibt bis zur Bestätigung in `pending_overrides.json`;
erst `confirm` schreibt ihn nach `manual_overrides.json`. Also: Meldungen
ansehen, jede einzeln per Websuche gegen die offizielle Ausschreibung
prüfen, Vorschlag anlegen, **vom Nutzer bestätigen lassen** – nicht
selbst durchwinken. Details im README („Fehler zu diesem Event melden").

## Frontend-Fallen (events.html)

- **Das Filter-Panel folgt seinem Spaltenknopf beim Scrollen, es schließt
  sich nicht mehr** (jetzt in `filter-ui.js`) (`folgeDemKnopf`/`isTriggerVisible`). Früher schloss
  jedes `scroll`/`resize` das Panel – auf 390 px ließ sich der
  Stadt/Ort-Filter damit gar nicht öffnen (das Scroll-Ereignis vom
  waagerechten Wischen kommt erst nach dem Klick an), und die
  Android-Tastatur (`resize`) hätte jedes Suchfeld sofort wieder
  geschlossen. Nicht zurückdrehen.

- **Der Panel-Anker überlebt `buildHeader()`.** Ein Ausgangspunkt
  schaltet die Entfernungs-Spalte zu, `setOrigin()` baut dafür den
  Tabellenkopf neu – der Knopf, an dem das offene Panel hängt, wird durch
  einen neuen ersetzt. Der alte liefert dann `getBoundingClientRect()`
  = lauter Nullen, und das Panel sprang in die linke obere Ecke (vom
  Nutzer gemeldet). Deshalb in `filter-ui.js`: `attachButton()` übergibt
  dem neuen Knopf derselben Spalte die Ankerrolle, `isTriggerVisible()`
  und `positionFloatingPanel()` prüfen `isConnected`, und `reposition()`
  richtet am **Ende** von `render()` neu aus – das `refresh()` am Anfang
  ist zu früh, die Spaltenbreiten (`table.with-distance`) stehen dort
  noch nicht.

- **Stadt/Ort ist eine Umkreissuche, keine Ortsliste mehr.** Reihenfolge
  im Panel: Standort-Button → Regler 1–200 km → Suchfeld für Ort/PLZ
  (aus `places.json`, ~32.600 Orte; wird erst beim Öffnen des Panels
  geladen). Ein Ausgangspunkt schaltet den Umkreis auf 25 km
  (`RADIUS_DEFAULT_KM`). Der Regler filtert erst bei `change`, nicht bei
  `input` – sonst baut sich die Tabelle bei jeder Fingerbewegung neu auf.
  `normalizePlaceText()` hier und `normalisiere()` in `build_places.py`
  müssen dasselbe tun. Im Panel steht nur, was beim Suchen hilft – die
  GeoNames-Namensnennung (CC BY 4.0 verlangt sie) steht in der Fußzeile
  von `index.html`, nicht im Filter.

- **Den Standort-Dialog kann die Seite nicht erzwingen.** Der Browser
  fragt nur beim ersten Mal und merkt sich die Antwort; systemweit
  abgeschaltete Ortung liefert Fehlercode 1 sofort, ganz ohne Dialog.
  Deshalb unterscheidet der Fehler-Zweig nach der Dauer: unter 800 ms
  = nie gefragt → nummerierte Anleitung für die Einstellungen
  (iOS-Pfade bei Apple-Geräten) einblenden; länger = gerade selbst
  abgelehnt → „noch einmal tippen". Nicht zu einem einzigen Text
  zusammenfassen, die beiden Fälle brauchen verschiedene Schritte.

- **`refreshOpenPanel()` zeichnet das offene Filter-Panel nicht neu,
  solange der Fokus darin liegt** (damit eine Eingabe im Namensfeld nicht
  abreißt). Jeder Button *im* Panel, der den Filterzustand ändert, muss
  daher vor `render()` den Fokus abgeben – siehe `geoBtn.blur()` beim
  Standort-Button; ohne das sah „Aktuellen Standort verwenden" kaputt aus
  (Status blieb „wird ermittelt…", Radius-Auswahl ausgegraut).
- **Chips nie pro Wert aufzählen.** Mengen-Filter fassen sich zusammen:
  alles ausgewählt → „Stadt/Ort: Alle", mehr als `MAX_VALUE_CHIPS` (5) →
  „Stadt/Ort: 12 ausgewählt". „Alle" bei Stadt/Ort sind ~2000 Orte.
- **Reihenfolge im Skript beachten**: `const`/`let` auf oberster Ebene
  müssen VOR ihrer ersten Verwendung stehen – sonst
  Temporal-Dead-Zone-Fehler. Beim Bau der Zeitraum-Knöpfe und des
  Deep-Links ist das zweimal passiert: `DATE_PRESETS` und
  `urlZustandGelesen` werden schon beim Laden gebraucht (readUrlState
  bzw. der erste `render()`), standen aber weiter unten. Beide stehen
  jetzt oben bei `state`, mit Begründung im Kommentar.
- **`writeUrlState()` schreibt nur nach `readUrlState()`**
  (`urlZustandGelesen`). `EndauranceAuth.onAuthChange` ruft `render()`
  schon auf, während `events.json` noch lädt – ohne die Flagge löschte
  dieser erste Durchlauf die Parameter eines geteilten Links, bevor sie
  gelesen waren.
- **Sortierung**: jede Spaltenüberschrift ist ein Knopf, Schlüssel in
  `SORT_KEYS` (Rückgabe `[Gruppe, Wert]`, damit Zeilen ohne Angabe immer
  hinten landen). Bei der Länge gibt es drei Stufen: Distanz, dann
  Zeitrennen nach Dauer, dann leer – km und Stunden werden NICHT in eine
  Zahlenreihe gemischt.
- **Entfernungs-Spalte** erscheint nur mit Ausgangspunkt
  (`activeColumns()`), Breiten dafür unter `table.with-distance`. Zellen
  werden aus `activeColumns()` gebaut, nicht fest untereinander – sonst
  müsste die Spaltenreihenfolge an zwei Stellen gepflegt werden.
- **Der Schalter „Veranstaltungen zusammenfassen" steht direkt hinter der
  Trefferzahl**, nicht bei den Knöpfen rechts: er verändert, wie diese
  Zahl zu lesen ist („810 Veranstaltungen (1413 Strecken)").
  `.toolbar-actions` behält dafür `margin-left: auto`, damit „Alle Filter
  zurücksetzen" am rechten Rand bleibt. Die Chips dazwischen NICHT
  `flex: 1` geben – dann rutscht der Knopf beim Umbruch nach links.
- **Zusammenfassen ist reine Anzeige** (`state.gruppiert`,
  `buildGroups()`): Datenregel 1 (eine Zeile pro Strecke) bleibt gültig,
  die Tabelle bündelt sie nur nach Name + Datum + Ort und zeigt die
  Spanne der Distanzen.
- **Die Spalte „#" (Anzahl) gibt es nicht mehr.** Sie stand beim
  Zusammenfassen ganz links und wurde als Durchnummerierung der Events
  gelesen – „1, 2, 1, 1, 3" sah nach einer kaputten Liste aus (vom
  Nutzer gemeldet). An ihrer Stelle steht jetzt der **Aufklapp-Pfeil**
  (der saß immer schon im Namensfeld, hat ohne die Zahl davor aber den
  Platz ganz links). Wie viele Strecken sich hinter einer Veranstaltung
  verbergen, muss man vorher nicht wissen – die Gesamtzahl steht in der
  Trefferzeile („7 Veranstaltungen (10 Strecken)"). Nicht
  wieder einführen.
- **Aufgeklappt zeigt die Veranstaltungszeile die erste Strecke selbst**
  (`groupRowHtml()` mit `offen`, `subRowsHtml()` gibt nur `rows.slice(1)`
  aus): zwei Strecken = zwei Zeilen. Die frühere dritte Zeile war die
  Zusammenfassung über ihren eigenen Strecken – vom Nutzer als Doppelung
  gemeldet. Zugeklappt bleiben die Marken mit allen Längen.
  `klappeGruppe()` zeichnet die Veranstaltungszeile dafür neu (immer noch
  ohne `render()`).
- **Eine Veranstaltung mit nur einer Strecke klappt nicht auf**
  (`istEinzelgruppe()`, `tr.group-row.single`): die Unterzeile würde
  dasselbe wiederholen. Kein Pfeil, kein `aria-expanded`, kein
  Aufklappen – der Klick wählt die Strecke nur aus. Statt des Pfeils ein
  gleich breiter Platzhalter (`.chevron-spacer`), sonst beginnen die
  Namen einzelner Strecken weiter links als die der aufklappbaren.
- **Die Anzahl-Zahl steht schlicht in der Tabelle.** Eine Variante, in
  der sie als Kapsel halb über der linken Rahmenlinie lag, war gebaut und
  vom Nutzer wieder verworfen („wie ein aufgeklebtes Etikett"). Der
  Rahmen sitzt daher wieder auf `.table-wrap`, das Zwischen-`div`
  `.table-frame` ist weg. Falls das noch einmal aufkommt: `.table-wrap`
  scrollt und beschneidet, der Überhang braucht also einen inneren Frame
  plus Innenabstand – und `width: max-content` am Frame geht NICHT
  (bemisst sich gegenseitig mit `width: 100%` der Tabelle, die Tabelle
  rutscht aus dem Bild).
- **Kalender-Einträge sind immer ganztägig**: Startzeiten stehen in
  keiner Quelle verlässlich. `DTEND` bzw. `dates=`/`enddt=` ist
  **exklusiv**, also Enddatum + 1 Tag – ohne das +1 fehlt der letzte Tag.
- **Die `.ics`-Dateien liegen fertig im Repo** (`kalender/`, erzeugt von
  `scripts/build_ics.py`, aufgerufen von `update_events.py` nach dem
  Aufräumen). Grund: Auf iPhone/iPad übergibt Safari einen Termin nur an
  den Kalender, wenn die Datei **vom Server** mit
  `Content-Type: text/calendar` kommt. Drei Versuche, das im Browser zu
  lösen, sind am Gerät gescheitert – data-URI, Blob und eine vom Service
  Worker erfundene Antwort landeten alle als Download („Unknown.ics",
  Teilen-Liste ohne Kalender) bzw. auf der 404-Seite von GitHub Pages.
  Der Service Worker (`sw.js`) ist deshalb wieder **entfernt**, ebenso
  die ICS-Erzeugung in `events.html`: **einzige Quelle ist jetzt Python.**
  Der Link im Detailbereich trägt bewusst **kein `download`-Attribut** –
  das würde Safari das Übergeben an den Kalender wieder verbieten.
- **Der Dateiname wird zweimal berechnet**: `ics_dateiname()` in
  `build_ics.py` und `icsFileName()` in `events.html`
  (`<datum>-<name>-<distanz>-<ort>.ics`). Weichen sie ab, zeigt der Knopf
  ins Leere – `test_scraper_lib.py` prüft beide gegeneinander und lässt
  dafür den echten JS-Code in `node` laufen. Der **Ort** gehört in den
  Namen, weil Name + Datum + Distanz nicht eindeutig sind: „TEAG -
  Legend of Cross - Mühlberg" steht am 31.10.2026 mit 10, 17 und 30 km
  je zweimal in den Daten, einmal unter „Mühlberg" und einmal unter
  „Drei Gleichen". Das frühere Beispiel „Königsforst-Marathon" trägt
  nicht mehr: Dessen zweite 42,2-km-Zeile war ein Verortungsfehler und
  ist seit der Einzelprüfung vom 18.09.2026 zusammengeführt.
- **`DTSTAMP` ist fest** (`20260101T000000Z`), nicht „jetzt": sonst
  änderte jeder Lauf alle 4.150 Dateien und der wöchentliche Commit wäre
  ein Riesen-Diff ohne inhaltliche Änderung.
- **Spaltenbreiten über Klassen** (`.col-name`, `.col-anzahl`, …), nicht
  `nth-child`: Entfernung und Anzahl kommen und gehen, jede Kombination
  bräuchte sonst eigene Regeln. `CHEVRON_SVG` steht oben bei `state` -
  der erste `render()` braucht es bei aktiver Gruppierung sofort (TDZ).
- **`.group-name` ist ein Flex-Element ohne `.cell-clamp`**: dessen
  `display: -webkit-box` widerspricht dem Flex, der Name rutschte sonst
  unter das Chevron. Gekürzt wird stattdessen `.group-name-text`.
- **Ein Tippen auf eine Zeile scrollt zu den Angaben** – aber nur auf
  dem Handy und nur beim Auswählen. Unter 900 px hat die Seite eine
  Spalte, der Detailbereich steht also unter der 78vh hohen Tabelle; ein
  Tippen wirkte vorher folgenlos (vom Nutzer gemeldet).
  `zeigeDetailbereich()` prüft erst, ob der Bereich wirklich außerhalb
  des Bildes liegt – am Rechner steht er daneben und darf sich nicht
  bewegen –, achtet auf `prefers-reduced-motion` und wird **nicht**
  gerufen, wenn der Klick eine Veranstaltung auf- oder zugeklappt hat
  (dann will man die Strecken an dieser Stelle sehen) und nicht bei der
  Pfeiltasten-Navigation (sonst schiebt sich die Tabelle weg, in der man
  gerade navigiert).
- **Tastaturbedienung der Tabelle: „roving tabindex".** Jede Zeile trägt
  `tabindex="-1"`, aber nur **eine** ist per Tab erreichbar
  (`setzeTabStop()`, `tabStopZeile` steht oben bei `state` – als `let`
  weiter unten warf sie beim ersten `render()` einen
  Temporal-Dead-Zone-Fehler und brach `render()` mitten ab). 4.155
  Tab-Stopps wären eine Falle. Bewegt wird mit ↑/↓, Home/End, →/←
  (Veranstaltung auf/zu), Leertaste klappt um, Enter springt in den
  Detailbereich (`tabindex="-1"` am `#detail-panel`). Alles über **einen**
  `keydown`-Listener am `<tbody>` – kein Listener je Zeile, das
  Ein-String-Zeichnen bleibt.
  **Enter klappt NICHT um, auch nicht auf einer Veranstaltungszeile.**
  Dafür gibt es schon →, ← und die Leertaste – drei Wege. Enter ist der
  **einzige** Weg in den Detailbereich, und dort stehen Kalenderdatei,
  Veranstalter-Seite und „Fehler melden". Bis zum 18.09.2026 stand im
  Enter-/Leertaste-Zweig ein gemeinsames `return` vor dem Sprung: Wer
  die Liste mit der Tastatur bedient, kam bei jeder Veranstaltung mit
  **mehreren Strecken** nie an diese Links. Gemerkt hat es niemand,
  weil der Rauchtest Enter am Ende des Fensters drückt – und dort lag
  zufällig immer eine einzelne Strecke. Erst als die Einzelprüfung der
  Events 201–400 fünf Zeilen entfernte, rutschte eine aufklappbare
  Zeile dorthin. Der Fall steht deshalb jetzt **ausdrücklich** im
  Rauchtest (beide Seiten: Enter springt, Leertaste klappt um), nicht
  dem Zufall überlassen.
- **Die Tabelle zeichnet nur ein FENSTER** (`FENSTER_SCHRITT = 200`,
  `zeigeMehr()`), gefiltert und sortiert wird aber über **alle** Events.
  Gemessen mit 20.770 Events (`scripts/bench_frontend.py`): alle Zeilen
  im DOM waren 317.913 Knoten und 12,2 MB HTML, und jede Änderung baute
  sie neu – Sortieren 4,6 s, Zusammenfassen 8,2 s, Filter zurücksetzen
  4,4 s. Mit Fenster: 742 / 237 / 145 ms. Vier Dinge nicht aufweichen:
  - Die **Trefferzahl bleibt die volle Zahl** – das Fenster ist reine
    Anzeige, wie `state.gruppiert`.
  - `idxZuGruppe` wird für **alle** Gruppen gefüllt, nicht nur die
    gezeichneten (ausgewählt sein kann eine Strecke außerhalb des
    Fensters).
  - `data-g` trägt die **absolute** Gruppennummer (`gruppenHtml(…,
    startNr)`), sonst liest `klappeGruppe()` die falsche Gruppe.
  - **Tastatur**: ↓ am Rand des Fensters holt den nächsten Schub
    (`nachbarZeile()`), `End` führt ans Ende des Geladenen – ohne das
    wäre per Tastatur nur die erste Seite erreichbar.
  Der Knopf steht in einem `position: sticky; left: 0`-Element: Die
  Zelle spannt über alle Spalten (800 px), ein mittiger Knopf lag auf
  Handybreite außerhalb des Bildes, sobald man waagerecht gescrollt
  hatte. Beim Scrollen lädt ohnehin von selbst nach – der Knopf ist für
  die Tastatur, für Screenreader und als ehrliche Anzeige, wie viel
  noch fehlt.
  `fenster` und `nachladeFrame` stehen oben bei `state`: `render()` ruft
  `pruefeNachladen()` am Ende, und weiter unten deklariert gab es
  „Cannot access 'nachladeFrame' before initialization" (der Rauchtest
  hat es gemeldet – dieselbe Falle wie bei `DATE_PRESETS`).
- **Ein Event teilen: Link, kein PDF.** Der Knopf oben rechts in der Box
  gibt `navigator.share()` Titel, die Angaben aus der Box und einen
  **absoluten Link auf genau dieses Event** (`?event=<eventSlug>`);
  ohne Teilen-Dialog (Firefox am Rechner) wird Text + Link kopiert.
  Begründung im Kommentar bei `teileEvent()`: Ein Link führt zum Event
  samt Kalender-Knopf und Veranstalter-Seite und veraltet nicht, ein PDF
  bräuchte eine Bibliothek für ein schlechteres Ergebnis. Ein PDF lohnt
  erst für die ganze gefilterte Liste (Saisonplan) - und dafür reicht
  ein Druck-Stylesheet.
  - **`eventSlug(e)`** ist die Kennung (Datum, Name, Maßzahl, Ort) und
    steht nur EINMAL da: `icsFileName()` baut darauf auf, und
    `test_scraper_lib.py` prüft sie gegen `build_ics.ics_dateiname()`
    (schneidet dafür `eventSlug` mit aus der Seite heraus - beim
    Umbenennen dort nachziehen). Eine laufende Nummer wäre wertlos: Sie
    verschiebt sich, sobald ein Event dazukommt oder ein vergangenes
    wegfällt, und ein geteilter Link zeigte auf ein fremdes Rennen.
  - `?event=…` wird **gelesen** (readUrlState) und bleibt in der Adresse
    stehen, solange dieses Event ausgewählt ist (writeUrlState) - aber
    **nicht** in `currentParams()`: Das speist auch den Kartenknopf, und
    die Karte kennt kein einzelnes Event. `deepEventSlug` steht oben bei
    `state` (TDZ).
  - Beim Öffnen eines geteilten Links wird zur Box gescrollt
    (`zeigeDetailbereich()`), sonst sieht der Empfänger auf dem Handy nur
    eine Liste.
- **Abos sind Filter + Rhythmus** („Neue Events per E-Mail"). Der Knopf
  steht in der Werkzeugleiste und ist **immer** erreichbar – die alte
  Box erschien nur bei null Treffern, wer „alle neuen Schwimm-Events in
  Thüringen" wollte, kam nie an sie heran. Die Box bei null Treffern
  führt jetzt in denselben Dialog: **ein** Weg, an dem ein Abo
  entsteht.
  - **„Welche Events?" steht im Dialog selbst.** Die Filter der Liste
    *sind* die Auswahl, aber das war unsichtbar: Wer ohne Filter auf den
    Knopf tippte, las nur „Alle neuen Events" und hatte keine
    Möglichkeit, „nur Radrennen im Umkreis" einzustellen (vom Nutzer
    gemeldet). Der Dialog trägt deshalb **dieselbe Knopfreihe wie die
    Karte** (`aboUi.buildButtonBar(…, { ohne: ['datum'] })`) – keine
    zweite Kopie der Filterlogik, nur eine zweite Bedieneinheit auf
    einem **eigenen Zustand** (`aboState`). Vier Dinge daran nicht
    aufweichen:
    - **Eigener Zustand, beim Öffnen aus der Suche gefüllt**
      (`uebernehmeSucheInAbo()` → `EF.copyState(state, true)`, ohne
      Datum). Wer schon gefiltert hat, findet seine Filter vor; was er
      im Dialog umstellt, verändert die Liste dahinter **nicht**.
      `EF.copyState` kopiert die Sets, nicht die Verweise – sonst wäre
      es derselbe Filter.
    - **Das Panel hängt IM Dialog** (`panelParent: () => aboOverlay` in
      `EFU.create`). An `<body>` gehängt lag es hinter dem Overlay
      (z-index 1000 gegen 2000) und außerhalb der Fokusfessel von
      `dialogTasten()` – per Tastatur nicht erreichbar. Als Funktion
      übergeben, weil `aboOverlay` weiter unten steht; umgehängt wird
      erst beim Öffnen.
    - **`alleWerte: true`.** Die Liste bietet nur Werte an, zu denen es
      Events gibt; ein Abo schaut in die Zukunft. Ohne diese Flagge
      stand „Fahrrad" gar nicht zur Wahl – damals stand in
      `events.json` kein einziges Radrennen, und genau das wollte der
      Nutzer abonnieren. (Inzwischen sind es neun, siehe Datenregel 12 –
      die Flagge bleibt trotzdem nötig: Für die Schweiz oder fürs
      Schwimmen gilt dasselbe Argument weiter.) Die Liste steht in
      `filter-ui.js` (`BEKANNTE_WERTE` = `EF.LAENDER` + die Sportarten
      aus `DISTANCE_CATEGORIES`, dazu `ALLE_ART2` aus `ART2_BY_ART1`).
    - **`updateIndicators()` färbt nur die eigenen Knöpfe.** Es läuft
      über die `buttons`-Sammlung der Bedieneinheit (gelöste Knöpfe
      fliegen dabei raus), nicht über
      `document.querySelectorAll('.col-filter-btn')` – sonst malte der
      Dialog die Spaltenköpfe der Liste an und umgekehrt.
  - Die Zusammenfassung im Dialog entsteht aus **genau den Feldern, die
    gespeichert werden** (`serializeFiltersForNotify` →
    `aboBeschreibung`), nicht aus den Chips: Die zeigen auch den
    Datumsfilter, und der gehört nicht ins Abo (ein Abo schaut in die
    Zukunft). Neu gezeichnet wird bei jeder Änderung **nur der Kasten**
    (`zeichneAboZusammenfassung()`, `#abo-umfasst`) – ein `render()` des
    ganzen Dialogs nähme den gewählten Rhythmus und den Fokus mit.
  - **`nameQuery` und `suche` gehören ins Abo.** Ohne diese Felder wäre
    ein Abo stiller weiter gefasst als die Suche, aus der es entstand –
    wer „marathon" gesucht hat, bekäme alles. `functions/index.js` prüft
    beide mit.
  - **Drei Rhythmen** (`sofort`, `woechentlich`, `monatlich`) stehen an
    **vier** Stellen: `auth.js` (`ABO_RHYTHMEN`), `functions/index.js`
    (+ `RHYTHMUS_TAGE`), `firestore.rules` und die Texte in
    `events.html`. `test_abo_rhythmen` vergleicht alle vier – läuft eine
    weg, wird ein Abo gespeichert, von dem nie eine E-Mail kommt.
  - „Sofort" ist ehrlich beschriftet: Die Daten werden **wöchentlich**
    erneuert, schneller als der Datenlauf kann kein Abo sein. Der Text
    sagt das (`abo_r_sofort_note`).
  - **`?abos=1` öffnet die Verwaltung** (darauf zeigt der Abmelde-Link
    der E-Mails, solange `UNSUBSCRIBE_URL` fehlt). Gelesen wird der
    Parameter in `readUrlState()`, **nicht** im Ladeteil: Dazwischen
    liegt `writeUrlState()`, und das hatte `abos` längst aus der Adresse
    geworfen. Geöffnet wird er über `EE_AUTH_QUEUE` – `auth.js` trägt
    `defer`, beim Laden gibt es `window.EndauranceAuth` noch nicht.
    Beide Fallen sind hier zugeschlagen, bevor sie auffielen.
  - **Kein `try/catch` um den Aufruf.** Im ersten Versuch lag er mit im
    `try` – der Temporal-Dead-Zone-Fehler wurde verschluckt, und
    `?abos=1` tat einfach nichts, ohne Spur in der Konsole. Ein
    `try/catch` fängt die eine erwartete Ausnahme, nicht jeden
    Programmierfehler darin.
- **Dialoge: `dialogTasten()` steht in `auth.js`** (Escape + Fokusfessel,
  `aria-modal="true"` verspricht genau das) und wird von `events.html`
  für den Melde-Dialog mitbenutzt – **erst beim ersten Öffnen**
  eingehängt, weil `auth.js` `defer` trägt und beim Inline-Skript noch
  nicht existiert (dieselbe Reihenfolge wie bei `EE_AUTH_QUEUE`). Nicht
  kopieren, sonst laufen zwei Fesseln auseinander.
- **Die Kopfzeile: Knöpfe immer rechts, EINE Reihe, keine E-Mail.**
  Drei Dinge, die zusammengehören (alle am 18.09.2026 vom Nutzer
  gemeldet):
  - `.top-actions` trägt **`margin-left: auto`**. Bricht die Knopfreihe
    unter den Titel um, beginnt ein einzelnes Flex-Element dort am
    **linken** Rand – genau so standen Startseite/Karte/DE/EN plötzlich
    links. `justify-content: flex-end` am `.top-bar` hilft dagegen
    nicht, es gilt nur innerhalb einer Zeile.
  - **Eine Reihe statt zwei**: Der Teilen-Knopf lag früher unter DE/EN
    (eigenes `.top-actions-row` in einer Spalte). Jetzt sind alle Knöpfe
    Geschwister in einer umbrechenden Reihe – der blaue Kasten ist damit
    flacher. `.top-bar-text` (`flex: 1 1 260px; min-width: 0`) nimmt den
    Rest.
  - **Die E-Mail-Adresse steht nicht mehr im Kopf** (`renderAuthButton`
    in `auth.js`): unnötig, in Screenshots eine Preisgabe ohne
    Gegenwert – und sie machte die Reihe so breit, dass sie umbrach.
    „Abmelden" allein sagt, dass jemand angemeldet ist; um welches Konto
    es geht, steht im Abo-Dialog. `loggedInShort` ist deshalb aus beiden
    `I18N`-Blöcken von `auth.js` entfernt.
  Der Untertitel ist **kein Bedienhinweis** mehr („Klicke auf eine
  Kopfzeile-Filterschaltfläche …" war ein Handbuchsatz für etwas, das man
  sieht), sondern sagt in einer Zeile, was die Liste ist und dass sie
  wöchentlich neu eingesammelt wird. Kurz halten – jede Zeile mehr macht
  den Kasten höher. Der lange **Titel** ist der nächste Hebel dafür, der
  gehört aber zum Design-Punkt „Marke und einheitliche Kopfzeile"
  (Fahrplan 4) und nicht in eine Nebenänderung.

- **Ab 901 px ist die SEITE fensterhoch, und nur die Liste scrollt.**
  Vorher war die Tabelle auf `78vh` begrenzt, die Seite selbst aber
  höher: Wer die Seite statt der Liste scrollte, sah die Liste enden und
  darunter eine leere Fläche – und scrollte in zwei verschiedenen Dingen
  (vom Nutzer gemeldet). Deshalb in der `@media (min-width: 901px)`:
  `body { height: 100vh; overflow: hidden; display: flex; flex-direction:
  column }`, `.layout { flex: 1; min-height: 0; align-items: stretch }`,
  `.table-wrap { height: 100% }`. **`min-height: 0` an beiden Stellen ist
  nicht Kosmetik** – ohne das wächst das Grid auf seine Inhaltshöhe und
  schiebt die Fußzeile aus dem Bild, statt selbst zu scrollen.
  Fußzeile und der Knopf „Event fehlt?" stehen damit immer sichtbar
  unten. **Auf dem Handy bleibt der Seiten-Scroll** (eine Spalte, der
  Detailbereich steht UNTER der Tabelle und `zeigeDetailbereich()`
  scrollt die Seite dorthin) – die Regel darf also nicht unter 901 px
  gelten. Das Nachladen des nächsten Schubs hängt schon an beidem
  (`wrapEl` **und** `window`, siehe `pruefeNachladen`), da war nichts zu
  ändern.

- **Alle Zeilen sind gleich hoch (52 px), und kein Text geht über zwei
  Zeilen** (so vom Nutzer gewünscht). `tbody tr { height: 52px }` wirkt
  wie eine Mindesthöhe; dass nichts darüber hinauswächst, sichern drei
  Dinge: `.cell-clamp` (zwei Zeilen), `.group-row.open .group-name-text`
  (dort ebenfalls zwei – vorher `white-space: normal` ohne Grenze) und
  die **Längen-Spanne**:
  - `laengeSpanne(g)` schreibt bei einer zusammengefassten Veranstaltung
    nur noch `5–51 km` statt einer Marke je Strecke. Die
    „Globetrotter Wandertage" mit 15 Wettbewerben hatten vorher 15
    Marken in einer Zelle und waren vierfach so hoch wie jede andere
    Zeile. Ohne Leerzeichen um den Gedankenstrich – die Spalte ist
    schmal.
  - **Eine bekannte Distanz hat Vorrang** (Datenregel 8): Bietet eine
    Veranstaltung Strecken UND ein Zeitrennen, nennt die Zeile die
    Strecken; nur ohne jede Distanz steht dort die Spanne der Dauern.
  - **Die Marken (`.badge`) sind weg** – sie sahen mit Rahmen und
    abgesetztem Hintergrund aus, als ließen sie sich anklicken. Nicht
    wieder einführen: In der Tabelle gilt **eine** Schrift und **ein**
    Aussehen. Aus demselben Grund sind die kleineren Schriftgrößen von
    `.sub-row` und `.group-row.open` (0.82rem) gefallen; Veranstaltung
    und Strecke unterscheiden sich über Pfeil, Anzahl und Einrückung.

- **Dezimaltrennzeichen: DE Komma, EN Punkt.** Alles, was eine Zahl mit
  Nachkommastelle anzeigt, geht durch `EF.formatNumber(wert, lang,
  stellen)` bzw. `EF.formatKm`/`EF.formatHours` in `filters.js` – die
  Liste (`formatKm`, `formatLength`, `formatDistance`, `laengeSpanne`),
  die Chips (`Länge ab …`, aus einem `<input type="number">` kommt immer
  ein Punkt) und die deutschen Kategorie-Labels („Olympische Distanz
  (51,5 km)"; „70.3" bleibt mit Punkt, das ist der Markenname).
  **Bewusst kein `toLocaleString()`**: Das hängt an der
  Spracheinstellung des Browsers, nicht am Umschalter DE/EN der Seite –
  ein Deutscher mit englischem System hätte im deutschen Text Punkte
  gesehen. **Nicht** durch diese Funktion gehen darf `icsMasszahl()`:
  Der Dateiname der Kalenderdatei und der `eventSlug` müssen
  sprachunabhängig sein, sonst zeigt ein geteilter Link ins Leere
  (`test_scraper_lib.py` prüft sie gegen `build_ics.py`).

- **„Wir haben dein Event nicht?"** – der zweite Fall bei null Treffern.
  Ein Abo hilft nur, wenn das Event noch nicht existiert; unsere Liste
  kann aber auch einfach unvollständig sein. Zwei Wege, **ein** Dialog
  (`openSuggestModal`): die leise Leiste `.fehlt-bar` unter der Liste
  (immer da) und ein zweiter Knopf in der Null-Treffer-Box.
  - Gefragt wird **nur nach der Adresse der offiziellen Seite und dem
    Namen** (plus optionalem Hinweis). Datum, Strecken, Ort und Sportart
    holen wir uns von genau dieser Seite: Abgetippte Angaben wären eine
    dritte Datenquelle neben Scraper und `manual_overrides.json`, und
    Datenregel 2 verlangt die offizielle Seite ohnehin.
  - `normalisiereUrl()` ergänzt ein fehlendes `https://` (der häufigste
    Fall beim Eintippen), weist aber alles ohne Punkt im Hostnamen und
    jedes andere Schema ab. Dieselbe Bedingung steht in
    `firestore.rules` (`matches('^https?://.+')`).
  - Gespeichert wird in der neuen Collection **`eventSuggestions`**
    (anonyme Anmeldung wie bei den Fehlermeldungen, geschlossene
    Feldliste, `allow read, update, delete: if false`). Angesehen wird
    sie mit `python3 scripts/review_reports.py suggestions`.
  - **Übernommen wird nichts automatisch.** Ein Hinweis von außen ist
    eine Adresse, kein Datensatz: erst robots.txt und
    Nutzungsbedingungen der Quelle prüfen, dann Scraper oder Override –
    dieselbe Linie wie bei den Fehlermeldungen.
  - Die **Datenschutzerklärung** hat dafür einen eigenen Abschnitt
    (`h_fehlt`/`t_fehlt`, DE und EN). Kommt ein weiteres Feld dazu, muss
    er mit.

- **Die Mastersuche ist ein eigener Filter, nicht `nameQuery`.** Das
  Feld links von der Trefferzahl sucht über **Name, Wettbewerb UND Ort**
  und liegt in `filters.js` als `state.suche` (Adresse: `?s=`), neben
  dem unveränderten `nameQuery` (`?q=`, nur Name + Wettbewerb, das
  Textfeld der Spalte „Name"). Zwei Felder statt einem, mit Absicht:
  - Würde die Mastersuche auf `nameQuery` schreiben, hieße der
    Spaltenfilter „Name" plötzlich auch „Ort" – ein Spaltenfilter, der
    etwas anderes filtert als seine Spalte.
  - Weil sie in `EF.matchEvent()` steckt, filtert sie die **Karte**
    mit, steht im Chip, in der Adresse und überlebt den Seitenwechsel.
  - Sie gehört ins **Abo** (`serializeFiltersForNotify` → Feld `suche`)
    und ist deshalb ein **drittes Mal** in `functions/index.js`
    nachgebaut – wie `nameQuery`. Die Regel ist dort absichtlich so
    schlicht wie hier (kleinschreiben, `includes`): Je einfacher, desto
    eher bleiben beide Kopien gleich. Wer hier normalisiert (Umlaute,
    Akzente), muss es dort genauso tun, sonst bekommt jemand E-Mails
    über Events, die seine Suche nie gezeigt hat.
  - Gefiltert wird bei jedem Tastendruck, **neu gezeichnet erst nach
    180 ms** (`sucheTimer`): Über 4.000 Events filtern und die Tabelle
    bauen kostet auf einem Handy mehr als der Abstand zwischen zwei
    Tastendrücken. Enter zeichnet sofort.
  - `syncMasterSearch()` gleicht das Feld an den Zustand an (der Chip
    „Suche: …" und „Filter zurücksetzen" ändern ihn, ohne das Feld
    anzufassen) – **nicht**, während jemand darin tippt, sonst
    überschreibt ein Renderlauf die Eingabe.

- **Ein mehrtägiges Datum steht in zwei Zeilen.** `formatRangeHtml()`
  setzt ein `<br>` nach dem Gedankenstrich; vorher brach die Zelle dort
  um, wo gerade Platz war („18 Sep 2026 – 20" / „Sep 2026", vom Nutzer
  gemeldet). Zwei Zeilen passen genau in die 52 px Zeilenhöhe.
  **`formatRange()` (Text) bleibt daneben bestehen** – Melde-Dialog und
  Teilen-Text escapen ihren Wert, dort stünde ein `<br>` als Zeichenfolge
  im Text.

- **Die Werkzeugleiste muss in EINE Zeile passen** – auf 1024 px, der
  Breite eines iPads. Sie hatte früher dasselbe Raster wie `.layout`
  (rechter Rand exakt auf dem Tabellenrand, zweite Spalte für den
  Detailbereich frei); damit blieben ihr nur ~676 px, und Suchfeld,
  Trefferzahl, Schalter und die zwei Knöpfe brachen um (vom Nutzer
  gemeldet). Jetzt nutzt sie die **ganze Breite**, und die Texte sind
  kürzer: „Filter löschen" statt „Filter zurücksetzen", „Events
  zusammenfassen" statt „Veranstaltungen zusammenfassen", und die
  Trefferzeile nennt beim Zusammenfassen nur noch **eine** Zahl
  (`%d von %d Events` statt „… Veranstaltungen (… Strecken) von …
  Events"). Wer hier Text hinzufügt, bricht die Zeile wieder.

- **Städte mit eigenem englischen Namen** stehen in
  `VALUE_TRANSLATIONS.standort` (München → Munich, Köln → Cologne, …).
  Nur **echte Exonyme** – Orte, die im Englischen anders *heißen*, nicht
  bloß anders geschrieben werden („Wurzburg" ohne Umlaut gehört NICHT
  dazu). Angezeigt wird überall über `tv('standort', …)`: Tabelle,
  Detailbereich, Chips, Karten-Popup, Teilen-Text und Melde-Dialog. Die
  übrigen ~1.500 Orte gibt `tv()` unverändert zurück.

- **Die Mastersuche schlägt Serien und Orte vor** („Iron" → „Ironman").
  Entstanden aus der Frage nach einer **Veranstalter-Spalte**. Gemessen
  an den Daten lohnt die nicht: Die größte Serie hat 21
  Veranstaltungen, nennenswert sind rund elf (Wings for Life World Run
  21, Ahmadiyya Charity Walk 18, Muddy Angel Run 13, Rats-Run 9,
  Ironman 7, XLETIX 6, SportScheck RUN 6, HYROX 5, Spartan 3). Eine
  Spalte kostete Platz, den die Werkzeugleiste auf dem Laptop nicht hat
  – der Vorschlag im Suchfeld kostet keinen. „Sparkasse" (30) und
  „Stadtwerke" (6) sind übrigens **Sponsoren**, keine Veranstalter, und
  „Backyard" (21) ein Format.
  - **Gerechnet aus den Daten, nicht aus einer Liste im Code**
    (`EF.buildSuggestions`, `EF.matchSuggestions` in `filters.js`). Eine
    gepflegte Markenliste würde veralten, sobald eine Serie dazukommt –
    und beim großen Datenlauf kommen 16.000 Events dazu.
  - **Wortgruppen an JEDER Stelle des Namens, nicht nur am Anfang.**
    „Kulmbach Spartan Trifecta Weekend" beginnt mit dem Ort; nur mit
    Wortanfängen wäre „Spartan" kein Vorschlag geworden. Dasselbe gilt
    für „… Charity Walk".
  - **Der längere Begriff verdrängt den kürzeren bei gleicher
    Trefferzahl**: „Wings" und „Wings for Life" treffen beide 21,
    angeboten wird der längere. **Die Richtung dieses Vergleichs ist
    Tempo, nicht Stil**: Naheliegend wäre, für jeden Begriff die
    Begriffe mit derselben Trefferzahl zu durchsuchen – gemessen 533 ms
    bei 4.335 Events und 1,7 s bei 20.000, weil allein die Gruppe
    „1 Treffer" 6.209 Einträge hat. Umgedreht (jeder LANGE Begriff
    markiert seine höchstens fünf Teilstücke) sind es **35 ms bzw.
    112 ms**. Nicht zurückdrehen.
  - **Ein ORT wird nie verdrängt** und unterliegt nicht der
    Vier-Zeichen-Mindestlänge: „Ulm" muss vorkommen, „Berlin" ist eine
    eigene Auskunft neben „Berlin Marathon". Der Test hält beides fest.
  - **Der Index entsteht erst beim ersten Tippen** (`holeVorschlagIndex`),
    nicht beim Laden: Er gehört nicht in den ersten Seitenaufbau, für
    den die ganze Tempo-Arbeit gemacht wurde.
  - Gegenproben, die alle beim Bauen aufgetreten sind und jetzt im Test
    stehen: kein Vorschlag endet auf einem **Bindestrich** („Wings for
    Life -"), keine **Jahreszahl** („2026", „Silvesterlauf 2026"),
    Schreibvarianten sind **ein** Vorschlag („UltraTrail" /
    „Ultratrail" / „ULTRATRAIL"), und ein Ort steht **einmal** da (vorher
    zweimal: als Ort und aus den Namen).
  - Bedienung wie ein Auswahlfeld: `role="combobox"` +
    `role="listbox"`, ↑/↓ (über den Rand hinaus zurück ins Feld, kein
    Ring), Enter übernimmt, Escape schließt, `aria-activedescendant`.
    **`mousedown` statt `click`** an der Liste – ein Klick löste erst
    das `focusout` des Feldes aus, das die Liste schließt, und ging dann
    ins Leere.
  - **`t(key, ...args)` ruft einen Funktions-Text SELBST auf.** Beim
    ersten Versuch stand hier `t('vorschlag_serie')(v.anzahl)`, und die
    Seite warf bei jedem Tastendruck „t(...) is not a function" – ohne
    dass man es sah, weil die Liste einfach zublieb.

- **Die Mastersuche sucht in BEIDEN Sprachen** (`sucheHeuhaufen()` in
  `filters.js`): Wer die Seite auf Deutsch stehen hat, findet mit
  „Germany", „Munich" oder „running" dieselben Events wie mit
  „Deutschland", „München", „Laufen" (so vom Nutzer gewünscht).
  Durchsucht werden Name, Wettbewerb, Ort **und** die Übersetzungen von
  Land, Sportart, Kategorie und Ort.
  **Dieselbe Regel steht ein zweites Mal in `functions/index.js`**
  (`SUCH_UEBERSETZUNGEN` + `sucheHeuhaufen()`), damit ein Abo genau das
  trifft, was die Suche gezeigt hat. `test_suche_uebersetzungen`
  vergleicht beide Tabellen Wert für Wert – wird in `filters.js` eine
  Übersetzung ergänzt, muss die Kopie mit.

- **Texte immer in DE und EN** (`I18N`-Objekte, oben in der Datei).

## Tempo (gemessen, nicht geraten)

Die Seite war zäh; unter Handy-Bedingungen (4× gebremste CPU,
1,6 Mbit/s, gzip wie GitHub Pages) gemessen und behoben – Details und
Zahlen im README („Tempo der Seite"). Fünf Punkte, die **nicht**
zurückgedreht werden sollten:

1. **Die Firebase-Skripte tragen `defer`, und Firestore fehlt im HTML.**
   `firebase-firestore-compat.js` (344 KB) lädt `auth.js` per
   `ensureDb()` erst nach, wenn geschrieben wird;
   `EndauranceAuth.prepareFirestore()` stößt es beim Öffnen des
   Melde-Dialogs und der Abo-Box vorausschauend an. Ohne `defer` wartete
   `events.json` auf eine halbe Megabyte Firebase.
2. **`window.EE_AUTH_QUEUE`** ist die Folge davon: Das Inline-Skript
   läuft vor `auth.js`, kann also noch kein `onAuthChange` registrieren
   und legt den Listener dort ab. Nicht durch einen direkten Aufruf
   ersetzen – der liefe ins Leere.
3. **Die Tabelle entsteht als EIN HTML-String, die Klicks laufen über
   EINEN Listener am `<tbody>`** (`data-idx` = welches Event, `data-g` =
   welche Gruppe, `data-klapp` = aufklappbar). Nie wieder pro Zeile
   `createElement` + `innerHTML` + `addEventListener`: das kostete 605 ms
   pro Klick, jetzt sind es 14 ms.
   - `waehleZeile()` zeichnet **nicht** neu, es hängt nur die Markierung
     um (`markiereAuswahl()`, zwei Zeilen bei Gruppierung) und füllt den
     Detailbereich. `selectedIndex` steht in keinem Link, also auch kein
     `writeUrlState()`.
   - `klappeGruppe()` fügt nur die Unterzeilen dieser einen
     Veranstaltung ein bzw. entfernt sie. Die Trefferzahl ändert sich
     dabei nicht.
   - `gruppenAktuell`/`idxZuGruppe` stehen oben bei `state`: `render()`
     läuft über `setLanguage()` lange vor der Tabelle – sonst
     Temporal-Dead-Zone-Fehler (dieselbe Falle wie bei `DATE_PRESETS`).
4. **`tbody tr { content-visibility: auto }`** überspringt Layout und
   Zeichnen für Zeilen außerhalb des Bildes. Erlaubt ist das nur wegen
   `table-layout: fixed`; fielen die festen Spaltenbreiten weg, müsste
   die Regel mit.
5. **`preload`/`prefetch`**: `events.html` und `karte.html` fordern
   `events.json` im Kopf per `preload` an (mit `crossorigin="anonymous"`,
   sonst lädt der `fetch()` die Datei ein zweites Mal), `index.html`
   holt `events.html` + `events.json` per `prefetch` vor. Deshalb steht
   die Liste nach dem Klick auf „Events" in 814 statt 2.112 ms.

Der **Rahmen der Karte ist Europa**, und die Welt steht genau einmal da
(beides vom Nutzer gemeldet: „die Weltkarte wird immer dupliziert"):

- **`noWrap: true`** an der Kachel-Ebene. Ohne das zeichnet Leaflet die
  Kacheln links und rechts der Datumsgrenze beliebig oft weiter.
- **`maxBounds: EUROPA_BOUNDS`** (`maxBoundsViscosity: 1`, harte Kante)
  begrenzt das Verschieben. Europa statt DACH, damit die Karte bei einer
  Erweiterung der Länder nicht angefasst werden muss (so vom Nutzer
  entschieden).
- **Der kleinste Zoom wird gerechnet, nicht festgelegt**
  (`setzeMinZoomAufEuropa()`, auch bei `resize`) – und zwar über Europas
  **Breite**: `map.getBoundsZoom()` auf einen flachen Streifen über
  Europas Längengrade. Die beiden naheliegenden Varianten waren beide
  falsch, weil Europa hochkant liegt und ein Fenster quer:
  „Europa passt ganz ins Bild" ergab auf einem breiten, niedrigen
  Fenster Zoom 3 (Europa als Briefmarke, daneben Kanada bis China),
  „das Fenster liegt ganz in Europa" (`getBoundsZoom(…, true)`) ergab
  Zoom 6 (DACH war nicht mehr am Stück zu sehen). Senkrecht begrenzt
  `maxBounds`.
**Alles außerhalb der abgedeckten Länder liegt unter einer grauen
Maske** (`zeichneMaske()`, vom Nutzer am 18.09.2026 so entschieden:
eigene Daten, kein fremder Server). Sechs Dinge daran:

- **Ein einziges Polygon**: ein Rechteck über die halbe Welt, mit den
  Ländern als Aussparungen. Möglich macht das `fill-rule: evenodd`
  (Leaflet-Voreinstellung) – jeder weitere Ring kehrt die Füllung um.
  Deshalb wird ein Loch INNERHALB eines Landes von selbst wieder grau;
  das ist kein Sonderfall für Sonderfälle, Büsingen am Hochrhein ist
  deutsch und liegt mitten in der Schweiz.
- **Eigene Ebene** (`map.createPane('maskePane')`, z-index **250**):
  über den Kacheln (200), unter Markern und Umkreis (400). Läge sie
  oben, wären die Bündel-Zahlen matt und der Ausgangspunkt halb
  verdeckt.
- **`pointerEvents: none` am Pane und `interactive: false` am Polygon.**
  Ohne beides fängt die Maske die Klicks ab und kein Marker öffnet mehr
  sein Popup. Der Rauchtest prüft es.
- **Die Umrisse liegen in `laender.json`** (69 KB, 24 KB gezippt),
  erzeugt von `scripts/build_laender.py` aus **Natural Earth**
  (`ne_10m_admin_0_countries`, Public Domain, im Impressum genannt).
  1:10 Mio ist Absicht: Bei 1:50 Mio läge die Maskenkante an Orten wie
  Basel oder Konstanz sichtbar neben der Grenze. Vereinfacht auf
  ~100 m, Koordinaten auf vier Stellen.
- **Die Schlüssel in `laender.json` sind die Länder-Namen aus
  `EF.LAENDER`** (und damit aus `events.json`). Ein Land dazu heißt:
  Zeile in `build_laender.py` eintragen, Skript laufen lassen – sonst
  liegt das neue Land stillschweigend unter dem Schleier.
  `test_laender_maske` vergleicht beide Listen.
- **Geladen wird sie NACH den Events** (`ladeMaske()`, ohne `await`,
  Fehlschlag bleibt still): Die Maske ist Beiwerk, die Marker sind der
  Zweck. Ohne die Datei ist die Karte vollständig, nur überall gleich
  hell.

Auf der Karte entstehen die Popups erst beim Öffnen (`bindPopup(fn)`)
statt ~1.500 Stück im Voraus. Die Marker werden **gebündelt**
(Leaflet.markercluster): `createMarkerLayer()` fällt ohne das Plugin auf
`L.layerGroup()` zurück, die Bündel-Zahl ist die **Summe der Events**
(`options.eeCount`, addiert in `clusterIcon()`), und Ausgangspunkt +
Umkreis liegen in einer eigenen, **ungebündelten** Ebene
(`overlayLayer`) – im Bündel wären sie unsichtbar. Marker werden mit
`addLayers()` in einem Zug eingehängt, nicht einzeln.

6. **Die Tabelle zeichnet nur ein Fenster von 200 Einträgen**
   (`zeigeMehr()`, siehe Frontend-Fallen). Das ist der Punkt, der den
   großen Datenlauf überhaupt tragbar macht.

**Was beim großen Datenlauf (>20.000 Events) noch fehlt**: `events.json`
ist dann ~7,5 MB (830 KB gzip) und braucht unter Handy-Bedingungen
**5,4 s** – das ist nach dem Fenster der ganze Rest. Die Varianten sind
gemessen und der Weg steht im README („Vorbereitung auf über 20.000
Events"): Spalten-Arrays + Wörterbuch bringen 300 KB statt 830 KB, die
kompakte Datei wird im Pages-Workflow erzeugt statt committet, der
Dekodierer gehört in `filters.js`, und der Loader fällt auf
`events.json` zurück. Kurze Schlüssel allein bringen fast nichts – gzip
frisst Wiederholungen ohnehin.

## Liste und Karte teilen die Filter (`filters.js`, `filter-ui.js`)

**Ein Filter gilt für beide Seiten, und beide können ihn setzen.**
Deshalb liegt alles Gemeinsame in zwei Dateien, die `events.html` und
`karte.html` einbinden:

- **`filters.js`** (`window.EnduranceFilters`, in den Seiten `EF`) – der
  Zustand und die Regeln: `createState()`, `matchEvent()`,
  Distanzkategorien, `readParams()`/`toParams()` (Filter in der
  Adresse), `buildChips()` samt Chip-Texten und `VALUE_TRANSLATIONS`,
  die Zeitraum-Knöpfe, `dropPastEvents()`, die Mastersuche
  (`state.suche`, siehe Frontend-Fallen), `copyState(state,
  ohneDatum)` (Kopie samt Sets – der Abo-Dialog filtert damit ohne die
  Liste anzufassen) und die Helfer `escapeHtml()`,
  `uniqueSorted(values, lang)`, `formatDate(iso, lang)` sowie
  `formatNumber(wert, lang, stellen)` / `formatKm` / `formatHours`
  (Dezimaltrennzeichen je Sprache – siehe Frontend-Fallen).
- **`filter-ui.js`** (`window.EnduranceFilterUI`, in den Seiten `EFU`) +
  **`filter-ui.css`** – die Bedienung: Filterknöpfe und das schwebende
  Panel mit allem darin (Häkchenlisten, Datums-Baum, Umkreissuche mit
  `places.json`, Distanz-Tabs, Von/Bis). `EFU.create({ state,
  getEvents, t, tv, getLang, onChange, setOrigin, panelParent,
  alleWerte })` gibt den Bedienteil: `attachButton()` (Liste: eigene
  Spaltenköpfe), `buildButtonBar(container, { ohne })` (Karte und
  Abo-Dialog: beschriftete Knopfreihe), `refresh()`,
  `updateIndicators()`, `close()`, `options()`, `resetTransient()`.
  **Mehrere Bedieneinheiten je Seite sind erlaubt** (Liste + Abo-Dialog)
  – jede hält ihre eigenen Knöpfe, ihr eigenes Panel und ihren eigenen
  Zustand.

Die beiden Haken sind der ganze Unterschied zwischen den Seiten:
`onChange` zeichnet neu (Liste: Tabelle, Karte: Marker), `setOrigin`
darf mehr tun – die Liste schaltet dort die Entfernungs-Spalte und ihre
Sortierung mit. `panelParent` (wohin das Panel gehängt wird) und
`alleWerte` (auch Werte ohne heutige Events anbieten) braucht nur der
Abo-Dialog; Begründung bei den Abos weiter oben.

- Die Knöpfe „Karte" und „Liste" hängen den Filterzustand an die
  Adresse (`updateMapLink()` bzw. `linkTo()`), die andere Seite liest
  ihn mit `readParams()`. Nur so gilt ein Filter über den Seitenwechsel.
- `sort`/`gruppiert` versteht die Karte nicht, sie reicht sie aber
  weiter – sonst verliert der Weg Liste → Karte → Liste die Ansicht.
  `sort=entfernung` verwirft die Liste ohne Ausgangspunkt (die Spalte
  gibt es dann nicht).
- **Nichts davon zurück in eine Seite kopieren.** Zwei Kopien derselben
  Kategorien oder desselben Panels laufen auseinander (eine hier
  geändert, dort vergessen). In `events.html` bleibt nur, was allein die
  Liste hat: Spalten, Sortierung, Zusammenfassen, Detailbereich,
  Kalender, Fehlermeldung.
- Kurzformen in `events.html`, die auf `state` zugreifen
  (`matchesDistanceCategory`, `haversineKm`, `dropPastEvents`,
  `setOrigin`), sind **Funktions-Deklarationen statt `const`**:
  hochgezogen und damit auch vor ihrer Textstelle aufrufbar
  (`dropPastEvents()` läuft direkt nach dem `fetch`, weit oberhalb
  seiner Zeile).
- Die Texte werden mit
  `Object.assign(I18N.de, EF.I18N.de, EFU.I18N.de)` in das `I18N` der
  Seite gemischt, damit `t()` unverändert bleibt. Ein Text, den beide
  Seiten brauchen, gehört ins Modul – nicht in beide `I18N`-Objekte.
- **Das Panel per Tastatur**: Escape schließt es und gibt den Fokus an
  seinen Knopf zurück (`closePanel(true)`), Pfeil nach unten am Knopf
  öffnet es und geht hinein, ein `focusout` mit echtem `relatedTarget`
  schließt es (bei `null` **nicht** – dann hat sich das Panel nur selbst
  neu gezeichnet). Die Knöpfe tragen `aria-haspopup`/`aria-expanded`
  (gesetzt in `updateIndicators()`).
- Das Panel liegt bei `z-index: 1000`: über den Leaflet-Bedienelementen
  (800), unter Anmelde-Fenster (2000) und Kurzmeldung (3000). Mit den
  früheren 100 verschwand es auf der Karte hinter Zoom-Knöpfen und
  Markern.
- Auf der Karte bleibt die Knopfreihe immer stehen, nur die Chip-Zeile
  ist ohne Filter leer (`.active-chips:empty { display: none }`) -
  ausgeblendet wäre die Karte nicht mehr filterbar.

### Die Stempel an den geteilten Dateien (bitter gelernt)

GitHub Pages liefert **jede** Datei mit `Cache-Control: max-age=600`. Ein
Browser kann deshalb die neue `events.html` mit einer bis zu zehn Minuten
alten `filters.js` kombinieren. Genau das ist passiert: Die alte Datei
kannte `EF.uniqueSorted` noch nicht, das Inline-Skript brach in seiner
ersten Zeile ab (`readUrlState()`) - und die Seite war **leer**, nur
blauer Kopf. Kein Tippfehler, keine Safari-Eigenheit: ein halber
Cache-Stand.

Zwei Vorkehrungen, beide nicht wegnehmen:

1. **`?v=<Stempel>`** an `filters.js`, `filter-ui.js` und
   `filter-ui.css` in allen HTML-Dateien - der Stempel ist die ersten
   acht Hex-Stellen des SHA-256 über den Dateiinhalt. Ändert sich der
   Inhalt, ändert sich die Adresse, und der Browser MUSS neu laden.
   Gesetzt von `scripts/stamp_assets.py`, geprüft von
   `test_scraper_lib.py` (`test_asset_stempel`) - vergessen kann man es
   also nicht, aber laufen lassen muss man es.
2. Die **Notbremse** oben im Inline-Skript beider Seiten: fehlen `EF`,
   `EFU` oder eine erwartete Funktion, steht im Kopf „Bitte neu laden"
   samt Hinweis (DE/EN), statt dass die Seite leer bleibt.

## Nichts von fremden Servern (`vendor/`)

Leaflet, Leaflet.markercluster und die Firebase-SDKs liegen **im Repo**
(`vendor/`, 752 KB), nicht auf unpkg bzw. gstatic.com. Grund: Ein
CDN-Abruf überträgt die IP-Adresse jedes Besuchers an Dritte, bei JEDEM
Aufruf – auch wenn sich niemand anmeldet und niemand die Karte öffnet.
Was die Seite gar nicht an Dritte schickt, muss die
Datenschutzerklärung auch nicht erklären.

- Es sind die **unveränderten Originale**; ihre SHA-256-Summen stimmen
  mit den SRI-Werten überein, die vorher im HTML standen.
- `test_keine_fremden_dateien` hält das fest: kein `src`/`<link href>`
  auf einen fremden Server, kein nachgeladenes fremdes Skript, und jede
  `vendor/`-Datei existiert. Ein `<a href>` zählt nicht mit – ein Link
  überträgt nichts, solange niemand klickt.
- **Dieselbe Linie bei der grauen Maske**: Ein Kachel-Anbieter mit
  label-armem Stil hätte sie ohne eigene Daten geliefert – wäre aber
  ein zweiter fremder Server. Der Nutzer hat deshalb die eigene Datei
  gewählt (`laender.json`, 69 KB). Nicht umdrehen, ohne zu fragen.
- **Einzige Ausnahme: die OpenStreetMap-Kacheln** auf `karte.html`.
  Eine Karte ohne Kartenbilder gibt es nicht; sie stehen deshalb in der
  Datenschutzerklärung. (Wer strenger sein will: Kacheln erst nach
  einem Klick laden – vom Nutzer nicht gewünscht, weil die Karte dann
  nicht mehr sofort da ist.)
- **Aktualisieren**: neue Version in einen neuen Ordner
  (`vendor/leaflet-1.9.4` → `…-1.9.5`) und die Verweise umhängen. Der
  Pfad ist die Versionsangabe; ein Browser-Cache kann damit keinen
  halben Stand mischen.
- Nachgeprüft mit blockiertem Netz (jede Anfrage außer 127.0.0.1
  abgewiesen): alle Seiten laden vollständig, Bündelung und
  Anmelde-Knopf stehen.

## Impressum und Datenschutz (es fehlt nur die E-Mail-Adresse)

`impressum.html` und `datenschutz.html` sind gebaut. **Name und
Anschrift stehen seit dem 17.09.2026 drin** (Anton Donauer,
Christophstraße 3, 80538 München, Deutschland) – offen ist **nur noch
die E-Mail-Adresse**: Der Nutzer richtet dafür eine eigene Adresse ein
(seine private soll nicht öffentlich stehen). Sie ist auf beiden Seiten
gelb markiert (`.platzhalter`), und oben steht ein Kasten „Es fehlt noch
die Kontaktadresse". Der Rauchtest prüft, dass die Platzhalter sichtbar
sind: So kann die Seite nicht unbemerkt mit fehlender Kontaktangabe
online gehen. **Wenn die Adresse eingetragen wird**, müssen beide
Hinweiskästen weg (HTML + `vorlage_titel`/`vorlage_text` in beiden
`I18N`-Blöcken) – und der Rauchtest muss sich umdrehen: statt
„Platzhalter sichtbar" dann „keine Platzhalter mehr, Name und Kontakt
vorhanden" (`smoke_test_frontend.py`, die Prüfung bei
`stand["platzhalter"]`).

- **Die Seite ist ein privates Angebot ohne Gewinnerzielungsabsicht**
  (so vom Nutzer am 17.09.2026 gesagt). Die Überschrift im Impressum
  nennt deshalb **§ 18 Abs. 1 MStV** statt § 5 DDG: § 5 DDG gilt für
  geschäftsmäßige Telemedien, § 18 Abs. 1 MStV dagegen für alle, die
  „nicht ausschließlich persönlichen oder familiären Zwecken dienen" –
  und verlangt genauso Namen und Anschrift. **Umsatzsteuer-ID,
  Registereintrag und Telefonnummer entfallen damit**; die
  Telefon-Zeile ist raus. Wird die Seite später doch gewerblich
  (Werbung, Affiliate, Provisionen), muss § 5 DDG samt USt-ID zurück.

- **Beide sind von jeder Seite aus verlinkt** (Fußzeile in
  `index.html`, `events.html`, `karte.html`) – § 5 DDG verlangt
  „unmittelbar erreichbar".
- Die **Datenschutzerklärung beschreibt den echten Stand** der Seite:
  GitHub Pages (Server-Logs), OpenStreetMap nur auf der Kartenseite,
  Standort bleibt im Browser, Firebase erst bei der Anmeldung, anonyme
  Kennung erst beim Absenden einer Fehlermeldung oder eines Hinweises auf
  ein fehlendes Event, `endurance-lang` und
  `endurance-gruppiert` im lokalen Speicher, keine Analyse, keine
  Werbung. Wird an der Seite etwas verändert, das Daten betrifft,
  **muss dieser Text mit**.
- Die **GeoNames-Namensnennung ist umgezogen**: Sie stand in der
  Fußzeile von `index.html` und steht jetzt im Impressum unter
  „Datenquellen und Lizenzen", zusammen mit OpenStreetMap (ODbL),
  Leaflet und dem Firebase-SDK. Nicht löschen – CC BY 4.0 verlangt sie.
- Keine Rechtsberatung: Vor dem Livegang muss der Nutzer die Texte
  prüfen (lassen).

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

`.github/workflows/ci.yml` läuft bei **jedem Push und jedem Pull Request**
(zwei Jobs): `test_scraper_lib.py` samt `node --check` und Stempel-Prüfung,
dazu die Idempotenz von `clean_events.py` (zweimal laufen lassen und die
zwei Ergebnisse vergleichen – NICHT den committeten Stand gegen den
ersten Lauf: Aufräumen entfernt vergangene Events, das ändert die Datei
also jeden Tag zu Recht; mit `--no-geocoding`, damit nicht jeder Push
Nominatim befragt) und die Frage, ob `kalender/` zu `events.json` passt – und getrennt davon `smoke_test_frontend.py` in
Chromium. Das Repository ist öffentlich, Actions-Minuten sind kostenlos.
**Keine Scraper-Läufe in der CI** (Höflichkeit gegenüber den Quellen).

**⚠ Der Zeitplan läuft aus der Fassung auf `main`, nicht aus der auf
diesem Branch.** GitHub liest `schedule`-Trigger nur aus dem
Standard-Branch – und die Datei dort ist ein **älterer Stand**: täglich
statt wöchentlich, `git add events.json` **ohne `kalender`**, ohne
`timeout-minutes`, ohne die NOTIFY-Secrets. Genau daran ist die CI am
18.09.2026 viermal hintereinander rot geworden: Der Datenlauf committete
eine neue `events.json` (4.154 → 4.344 Events) und ließ die
`.ics`-Dateien liegen; der CI-Schritt „kalender/ passt zu events.json"
schlug deshalb bei JEDEM folgenden Push fehl, auch bei solchen, die mit
den Daten nichts zu tun hatten. Behoben wurde die Folge
(`build_ics.py` laufen lassen und mitcommitten) und die Erkennung
(`test_kalenderdateien` vergleicht jetzt auch `kalender/` mit
`events.json`, siehe „Vor jedem Commit"). **Die Ursache bleibt, bis die
Datei auf `main` aktualisiert wird** – dafür braucht es einen Push auf
`main`, also die ausdrückliche Erlaubnis des Nutzers.

**Die Einzelprüfung geht über mehrere Sitzungen**, deshalb gibt es
`scripts/geprueft.json`: Wer dort steht, wurde gegen die offizielle
Ausschreibung geprüft. Ohne dieses Protokoll fängt jede Sitzung von
vorn an. Fünf Ergebnisse, und der Unterschied ist wichtig:

| `ergebnis` | heißt |
|---|---|
| `quelle_ok` | offizielle Seite (oder mehrere unabhängige Kalender) abgerufen, alles richtig |
| `korrigiert` | Fehler gefunden, Korrektur in `manual_overrides.json` bzw. `manual_events.json` |
| `label_ok` | **nur am Wettbewerbs-Label entschieden**, ohne Abruf – schwächer |
| `unklar` | angesehen, aber an der Quelle **nicht zu entscheiden** – die Begründung sagt, was fehlt |
| `entfernt` | gehört nicht in die Liste (`NICHT_AUSDAUER`) |

`label_ok` nicht mit `quelle_ok` verwechseln: „Halbmarathon 22,8 km"
nennt seine Distanz selbst, das reicht für diese eine Frage – aber die
Zeile ist damit nicht vollständig geprüft.

`unklar` blendet `--offen` mit aus – sonst wird derselbe Fall jede
Sitzung neu recherchiert. Damit er nicht stillschweigend verschwindet,
nennt `audit_events.py` im Kopf die Zahl der `unklar`-Fälle
(`zaehle_unklar()`). Offen stehen dort z. B. die Walking-Distanz des
Freundschaftslaufs Marpingen (Veranstalterseite löst nicht mehr auf) und
die virtuelle „XMAS-Challenge" des Blauen Landes – **die braucht eine
Entscheidung des Nutzers**: „Egal wo, egal wann", fünf Wochen lang, ohne
Ort und ohne Koordinaten. Die Liste ist auf Veranstaltungen an einem Ort
und an einem Termin gebaut; ob virtuelle Läufe wie HYROX über eine
eigene Regel herausfallen sollen, entscheidet nicht Claude.

**Nach einem großen Datenlauf** gehört die Einzelprüfung dazu:

```bash
python3 scripts/audit_events.py --quiet        # welche Kategorien, wie viele
python3 scripts/audit_events.py --ab 0 --anzahl 200
```

Sie ändert nichts und ist kein Test (Rückgabewert immer 0) - sie sagt,
wo man hinsehen sollte. Die scharfen Kategorien zuerst („… aber Distanz
passt nicht", „Kinderlauf-Label mit Erwachsenendistanz", „Zahl im Label
weicht ab", „Koordinaten passen nicht zum Land"); Portallinks und
fehlende Distanzen sind keine Fehler.

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
ist der Datenstand (~4.150) bewusst nur Arbeitsmaterial.

**Was als Nächstes dran ist, steht unten im „Fahrplan".** Die fünf
Punkte sind mit dem Nutzer besprochen; Punkt 2 (Vorbereitung auf den
großen Datenstand) ist zur Hälfte gebaut.

## Fahrplan (Stand 17.09.2026)

Die fünf Punkte, die zuletzt mit dem Nutzer besprochen wurden – in
dieser Reihenfolge, mit Stand. **Nicht ohne Rückfrage umsortieren.**

1. **Daten für AT/CH, Schwimmen und Rennrad** – der größte inhaltliche
   Mangel: 4.137 Events in Deutschland, **15** in Österreich, **2** in
   der Schweiz, fast alles Laufen. **Der Nutzer liefert dafür Listen
   von Links** (so am 17.09.2026 entschieden) – also ein Scraper je
   Quelle, und vorher je Quelle robots.txt und Nutzungsbedingungen
   prüfen. **Kein Scraper ohne sein Ja**; die vier übersprungenen
   Quellen zeigen, warum.
   Was dafür vorher fehlt (und ohne die Links schon gebaut werden
   kann): **`art2`-Stichwörter für Fahrrad und Schwimmen** –
   für diese beiden Sportarten gibt es noch keine Liste, sie bekämen
   also „–" in der Kategorie-Spalte. **Triathlon ist seit dem
   18.09.2026 erledigt** (`ART2_KEYWORDS_TRIATHLON`,
   `ART2_BY_ART1['Triathlon']`, siehe Datenregel 11) – und mit
   `guess_art1()` steht auch das Muster, nach dem Fahrrad und Schwimmen
   erkannt werden könnten. Die Distanzkategorien je Sportart
   (`DISTANCE_CATEGORIES`) stehen ohnehin schon.
2. **Vorbereitung auf >20.000 Events** – *erste Hälfte erledigt*: Die
   Tabelle zeichnet nur ein Fenster von 200 Einträgen (siehe
   Frontend-Fallen und „Tempo"), gemessen mit `bench_frontend.py`.
   **Offen ist die Datei selbst**: 5,4 s von 6,3 s gehen für
   `events.json` weg. Der Weg ist gemessen und im README beschrieben
   („Vorbereitung auf über 20.000 Events"): `scripts/build_web_data.py`
   erzeugt eine kompakte Fassung (Spalten-Arrays + Wörterbuch, 300 statt
   830 KB gzip), erzeugt **im Pages-Workflow statt committet**,
   Dekodierer in `filters.js`, Loader mit Rückfall auf `events.json`,
   CI prüft den Rückweg. `events.json` bleibt die lesbare Quelle.
3. **Restliche Datenfälle**
   - „RET-Team Backyard 80 km": unklar, ob 80 km Zielvorgabe, Runde oder
     Teamwertung – per Websuche klären und als Override vorschlagen.
   - Die **Testmeldung** in `errorReports` („TEST - bitte verwerfen",
     16.09.2026) beim ersten `review_reports.py`-Durchgang mit `reject`
     verwerfen. Braucht einen Service-Account-Key oder den Nutzer in der
     Konsole.
4. **Design** – der Nutzer findet die Seite „noch nicht
   professionell". Reihenfolge nach seiner Wahl (17.09.2026):
   **Impressum + Datenschutz zuerst** (erledigt, siehe oben – es
   fehlt nur noch die E-Mail-Adresse).

   Am 18.09.2026 sind daraus die Punkte erledigt, die der Nutzer selbst
   gemeldet hat (siehe Frontend-Fallen): Knöpfe wieder rechts und in
   einer Reihe, flacherer blauer Kasten, E-Mail-Adresse raus,
   Bedienhinweis durch eine kurze Beschreibung ersetzt, Liste über die
   ganze Seitenhöhe, einheitliche Zeilenhöhe und Schrift in der Tabelle,
   Längen-Spanne statt Marken, Dezimalkomma im Deutschen. **„Fehler
   melden" bleibt wie es ist** – der Nutzer findet den Knopf so gut
   (ausdrücklich am 18.09.2026 gesagt).

   Im zweiten Durchgang am 18.09.2026 dazu: **Mastersuche** (ein Feld
   für Name oder Ort), **zweizeiliges Datum** bei mehrtägigen Rennen,
   **Events-Knopf im Kopf der Startseite**, kürzere Knopftexte („Filter
   zurücksetzen", „Events per E-Mail"), **kein ↗** mehr an Links, und
   der **Kartenrahmen** (keine zweite Weltkarte, Europa als Grenze).
   Im dritten Durchgang (18.09.2026): der **Anmelden-Knopf** ist nicht
   mehr weiß gefüllt (er war das Auffälligste auf der Startseite,
   obwohl das Konto nur Zubehör ist), und die **Spalte „#"** ist weg –
   an ihrer Stelle steht der Aufklapp-Pfeil.

   Ebenfalls erledigt: die **graue Maske** über allem außerhalb von
   DACH. Der Nutzer hat sich für die eigene GeoJSON-Datei entschieden
   und **gegen einen fremden Kachel-Anbieter** (18.09.2026) – siehe
   „Tempo"/Karte und `scripts/build_laender.py`.

   Offen, in dieser Wirkung:
   - **Handy: Karten statt Tabelle.** Unter ~700 px liegen Länge und
     Sportart außerhalb des Bildes, man muss waagerecht scrollen. Eine
     Karte je Event (Name, Datum, Ort, Marken) ist der größte Hebel.
   - **Marke und einheitliche Kopfzeile**: Startseite und Liste sehen
     aus wie zwei Projekte; der dicke blaue Kasten mit langem Titel und
     Hinweissatz wirkt wie ein internes Werkzeug.
   - **Detail-Box aufwerten**: Datum groß und zuerst, Marken statt
     Label/Wert-Liste, Knöpfe klar gestuft („Fehler melden" sieht
     derzeit aus wie deaktiviert).
   - Kleinteiliger: Sportart-Icons in der Liste, Ladezustand statt
     „Lade Events…", „Beispielprojekt" und „DACH" aus den Texten,
     `og:image`.
5. **Live schalten** – GitHub Pages läuft, die CI schützt seit dem
   16.09. davor, dass etwas Kaputtes deployt. Einziger Blocker ist noch
   die **E-Mail-Adresse** für Impressum und Datenschutz (der Nutzer
   richtet sie ein) – Name und Anschrift stehen seit dem 17.09.2026.

## Offene Punkte / To-dos

- **`og:image` nachtragen, sobald die Domain feststeht** – die
  Vorschau beim Teilen (`description`/Open Graph, in allen drei
  Seiten) hat bisher kein Bild, weil `og:image` eine absolute
  Adresse verlangt.

- ~~GeoNames-Namensnennung ins Impressum~~ **erledigt** (17.09.2026):
  Sie steht jetzt in `impressum.html` unter „Datenquellen und
  Lizenzen", zusammen mit OpenStreetMap, Leaflet und dem
  Firebase-SDK; `footer_places` ist aus `index.html` entfernt. Nicht
  löschen – CC BY 4.0 verlangt die Nennung mit Link.
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
- ~~Anbieter „Anonym" + `firestore.rules` veröffentlichen~~
  **erledigt** (16.09.2026, vom Nutzer in der Konsole). Gegen das echte
  Projekt `endurance-5177a` nachgeprüft:
  - anonyme Anmeldung funktioniert (vorher
    `auth/admin-restricted-operation`),
  - eine echte Meldung aus `events.html` wird angenommen – „Fehler zu
    diesem Event melden" läuft damit **end-to-end**,
  - die Regeln weisen ab: zu kurze Beschreibung, erfundene Kategorie,
    manipulierter `status`, fremde `uid`, Zusatzfeld, selbst gesetzter
    Zeitstempel, Lesen der Meldungen, Abo ohne E-Mail.

  In `errorReports` steht eine **Testmeldung vom 16.09.2026** („TEST -
  bitte verwerfen", Kategorie `sonstiges`, Event „16. AOK Firmenlauf
  Waiblingen") – beim ersten `review_reports.py`-Durchgang einfach mit
  `reject` verwerfen.

  Zu wissen fürs nächste Mal: Der **Erfolgsfall lässt sich nicht per
  REST** testen. Die Regel verlangt `createdAt == request.time`, und
  einen Server-Zeitstempel kann nur das SDK erzeugen – der Echttest
  läuft also über den Browser (Playwright gegen `events.html`). Die
  Negativfälle gehen dagegen gut per REST mit einem anonymen ID-Token.
  Zum **Lesen** der Meldungen braucht es einen Service-Account-Key
  (Projekteinstellungen → Dienstkonten) oder den Reiter „Daten" in der
  Konsole; die Regeln sperren das Lesen für alle Clients.
- ~~5 Seed-Links~~ **erledigt** (16.09.2026 recherchiert, vom Nutzer
  entschieden):
  1. *Bodensee-Schwimmen* → als „Bodensee Openwater" aufgenommen:
     Konstanz 26.06.2027 (5/10 km), Friedrichshafen 31.07.2027 (11 km),
     Wallhausen 28.08.2027 (2,5/5 km) – fünf Einträge, je Strecke einer.
     **Das sind die ersten Schwimm-Events überhaupt** (`art1`
     „Schwimmen", `art2` „Freiwasser“); vorher bestand `events.json` zu
     100 % aus Laufveranstaltungen. Die 2,5-km-Strecke überlebt die
     Mindestdistanz korrekt, weil Regel 5 nur für `art1 == "Laufen"`
     gilt. Die eigenständige „Bodenseequerung" wurde nicht verfolgt.
  2. *Engadin Bike Giro* → **eingestellt**, nicht aufgenommen. Letzte
     (8.) Austragung 2023, abgesagt bei nur ~200 Teilnehmenden; die
     angekündigte „Wiederbelebung 2025" kam nie, die offizielle Seite
     antwortet mit HTTP 503.
  3. *Basel Marathon* → **entfernt**. Der IWB Basel Marathon wurde 2018
     eingestellt (der Kanton strich 80.000 CHF Swisslos-Förderung), die
     hinterlegte `basel-marathon.ch` löst nicht mehr auf. Der Eintrag
     vom 09.05.2027 stand trotzdem in `events.json` und steht jetzt mit
     `"exclude": true` in `manual_overrides.json`. Woher sein Termin
     stammt, blieb offen – er passt zum 3Länderlauf (Marathon ab
     Marktplatz Basel, Mitte Mai), das wäre aber geraten gewesen.
  4. *Silvesterlauf Salzburg* → Der Lauf in der Stadt (1998–2004) ist
     eingestellt; stattdessen der **Leimüller Silvesterlauf** in
     Seekirchen am Wallersee aufgenommen (31.12.2026, 5,4 km). Nordic
     Walking und Junior-Race bewusst weggelassen.
  5. *Swiss Athletics Bahnmeeting* → **nicht aufgenommen**. Kein
     einzelnes Event, sondern ein Wettkampfkalender, und Bahnmeetings
     umfassen Sprint, Wurf und Sprung – das passt nicht zum
     Ausdauersport-Zuschnitt der Seite.

## Sprache

Code-Kommentare, Docstrings, README, Commit-Messages und Antworten an den
Nutzer: **Deutsch**. Die Webseite ist zweisprachig (DE/EN) über `I18N`-Objekte
in den HTML-Dateien – Textänderungen immer in *beiden* Sprachen.

# CLAUDE.md

Kurzbriefing für Claude Code. Ausführliche Doku: `README.md` (36 KB, nur bei
Bedarf gezielt lesen).

## Was das ist

Statische Webseite mit einer filterbaren Liste von Ausdauersport-Events
(Laufen, Schwimmen, Fahrrad, Triathlon) im deutschsprachigen Raum:
Deutschland, Österreich, Schweiz und **Südtirol** (seit dem 21.09.2026,
im Filter „Italien (Südtirol)"). Läuft auf GitHub Pages, kein
Build-Schritt, kein Framework.
Datenbasis ist `events.json`, gefüllt von Python-Scrapern.

## Entwicklungs-Branch

Alle Arbeit auf **`claude/endurance-events-website-v1wruf`** (PR #1).
Nicht auf einen anderen Branch pushen.

**Zweiter Name für denselben Stand**: Seit dem 21.09.2026 gibt es
daneben `claude/website-access-9d9tg1`. Beide Branches werden **auf
demselben Commit gehalten** (vom Nutzer am 21.09.2026 so entschieden:
„die beiden Branches zusammenführen") – jeder Push geht auf beide. Wer
nur einen sieht, sieht trotzdem alles.

## Dateien

| Datei | Zweck |
|---|---|
| `events.json` | die Daten (**~450 KB**, wächst mit jedem Lauf) |
| `index.html` | Startseite (statisch, kein Kartenlink – bewusst entfernt) |
| `events.html` | die Liste; Tabelle mit 7 Spalten, Filter pro Spalte |
| `places.json` | **~1,5 MB**, alle Orte + PLZ von DE/AT/CH und Südtirol (GeoNames IT, nur Provinz Bozen) für die Umkreissuche (nie komplett lesen) |
| `laender.json` | **73 KB**, Umrisse von DE/AT/CH und Südtirol für die Maske und die Landfläche der Karte – und für `scraper_lib.in_suedtirol()` |
| `scripts/build_laender.py` | baut `laender.json` aus Natural Earth (Staaten aus admin_0, Südtirol als Provinz IT-BZ aus admin_1); läuft nicht im Workflow mit |
| `scripts/build_places.py` | baut `places.json` aus GeoNames (`TEILGEBIET`: Italien nur admin2 „BZ"); läuft nicht im Workflow mit |
| `favicon.svg`, `apple-touch-icon.png` | das Zeichen des Style Guides (Navy-Kachel, weiße Route, oranger Punkt); das PNG entsteht aus dem SVG – neu erzeugen per Chromium-Screenshot (Playwright, 180 px, randvoll ohne Rundung), `cairosvg` gibt es in der Sandbox nicht |
| `vendor/fonts/` | **Barlow und Barlow Condensed** als woff2 (SIL OFL, Lizenztexte daneben), eingebunden über `vendor/fonts/barlow.css` in allen fünf Seiten – selbst gehostet, nichts von Google-Servern; ohne Stempel wie alles in `vendor/` |
| `karte.html` | Leaflet-Karte, ein Marker pro Standort, gebündelt (markercluster) – filtert wie die Liste |
| `filters.js` | gemeinsamer Filterzustand von `events.html` und `karte.html` |
| `site.css` | **Farben (ZWEI Schemata: dunkel = `:root`, hell = `:root[data-theme="light"]`), Kopfzeile (Marke, Navigation, Hell/Dunkel-Knopf, DE/EN, Anmelden), Filterleiste, Werkzeugleiste, Fußzeile** – geteilt von Liste, Karte und Startseite; seit dem Umbau vom 21.09.2026 nach den Vorlagen des Nutzers (Liste dunkel, Karte hell) |
| `filter-ui.js`, `filter-ui.css` | die Filterknöpfe (**Pillen mit gesetztem Wert**, `buildButtonBar` mit `order`) + das Panel + die **Mastersuche** (`buildSearch`) – beide Seiten bedienen dieselben |
| `event-detail.js`, `event-detail.css` | die **Detail-Box** eines Events (Datum groß, Abzeichen, **Strecken-Pillen** über `siblings`/`onSelect`, vier Fakten mit Symbol, Kalender-Menü, Teilen, `eventSlug`/`icsFileName`, `sportIcon`, Toast) – Liste (neben der Tabelle) und Karte (oben rechts, bis zu zwei) zeigen dieselbe |
| `scripts/stamp_assets.py` | setzt die `?v=`-Stempel an den sechs geteilten Dateien (`site.css`, `filters.js`, `filter-ui.js`, `filter-ui.css`, `event-detail.js`, `event-detail.css`; **nach jeder Änderung daran laufen lassen**) |
| `kalender/*.ics` | **~4.150 Dateien**, eine je Event, fertig für den Kalender (nie alle lesen) |
| `scripts/build_ics.py` | erzeugt `kalender/` aus `events.json` und räumt verwaiste Dateien weg |
| `auth.js`, `firebase-config.js`, `firestore.rules`, `functions/` | Login + „Benachrichtige mich" |
| `scripts/scraper_lib.py` | gemeinsame Engine (robots.txt, Parsing, Dedupe, Geocoding, CLI) |
| `scripts/*_scraper.py` | ein Skript pro Quelle |
| `scripts/clean_events.py` | räumt bestehende `events.json` nach allen Regeln auf, idempotent |
| `scripts/audit_events.py` | **prüft einzelne Zeilen** und meldet Verdachtsfälle – ändert nichts |
| `scripts/geprueft.json` | **Protokoll der Einzelprüfungen** – wer hier steht, ist geprüft (`audit_events.py --offen` blendet ihn aus) |
| `scripts/links_geprueft.json` | **Protokoll der Linkprüfung** (nur `veranstalter_url`, 500 Veranstaltungen am 19.09.2026) – bewusst getrennt von `geprueft.json`, damit die Datenprüfung diese Events nicht für „erledigt" hält |
| `scripts/update_events.py` | führt alle Scraper + Aufräumen aus (nutzt der Workflow) |
| `scripts/manual_overrides.json` | einzeln recherchierte Korrekturen an **vorhandenen** Zeilen |
| `scripts/manual_events.json` | einzeln recherchierte **fehlende** Strecken – ein Override kann keine Zeile anlegen |
| `scripts/veranstalter_links.py` | sucht für Zeitnehmer-/Anmelde-/Portallinks die **Veranstalterseite** – `sammeln` (raceresult-Kontaktseite, externe Links der Portalseite), `verifizieren` (Adressen aus einer Websuche), `pruefen` (eigene Seiten: tot? nennt den Lauf?), `anwenden` (Overrides + Protokoll); jede Kandidatenseite muss den Lauf am Namen nennen (bei `verifizieren` zählt auch der Ort im Hostnamen), siehe „Neunter/Zehnter Durchgang" |
| `scripts/seitenabgleich.py` | hält jede Veranstaltung mit eigener Seite gegen den **Seitentext** (Datum da? Distanzen da?) und meldet DATUM/DISTANZ/LEER/FEHLER – nur Bericht, siehe „Elfter Durchgang" |
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

Wurde `site.css`, `filters.js`, `filter-ui.js`, `filter-ui.css`,
`event-detail.js` oder `event-detail.css` angefasst, **vorher** stempeln
(der Test schlägt sonst fehl und sagt es auch):

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

Er öffnet die drei Seiten auf Handybreite in Chromium und prüft 197 Punkte:
Laden ohne Fehler und ohne 404, Kopfangaben, kein Überlauf, Aufklappen der
zusammengefassten Veranstaltungen (samt Rahmen um den Block), Filter-Panel, Kalenderdatei hinter dem
Knopf, Bündelung der Marker (Summe der Bündel-Zahlen = Kopfzeile),
Ausgangspunkt ungebündelt, das Fenster der Tabelle (nur ein Schub im
DOM, volle Trefferzahl, Knopf hängt nach), Teilen eines Events (was an
`navigator.share` geht und der Rückweg über den geteilten Link),
Impressum und Datenschutz (erreichbar von jeder Seite, Platzhalter
sichtbar, Sprachumschalter), **Enter im Namens-Panel** (schließt es,
Filter bleibt, Fokus zurück am Knopf), die **Suche auf der Karte**
(vor den Filterknöpfen, filtert Marker, `?s=`, Chip, Listen-Knopf nimmt
sie mit), die **Detail-Box auf der Karte** (Marker „2" öffnet direkt
zwei Boxen oben rechts, ab drei Events listet das Popup, Klick öffnet
die Box, zwei Boxen, Verdrängen, ✕, „Fehler melden" führt in die Liste
und öffnet den Dialog), der Abo-Dialog (Knopf, Zusammenfassung,
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
Länder ausgespart), der **Aufbau der Karte nach der Vorlage** (Legende
unten links mit Trefferzahl und vier Sportarten, „Mein Standort" öffnet
das Ort-Panel, Werkzeugleiste ohne Filter weg, Landfläche unter den
Kacheln, flache Übersicht und Kacheln ab Zoom 8, Bündel mit Ortsnamen,
Orientierungsorte, „E-Mail-Abo" in die Liste), der Popup-Link ohne
Pfeil, Filter über den Weg Liste → Karte → Liste und das **Farbschema**
(der Knopf schaltet um, die Wahl bleibt gespeichert und gilt auf der
nächsten Seite). Ohne Playwright bricht er
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
   **Bei `my.raceresult.com` steht die offizielle Seite auf der
   KONTAKT-Seite der Anmeldung** (`…/<nr>/contact`, Feld „Organizer-URL"
   samt Veranstalter-Anschrift) – vom Nutzer am 19.09.2026 am
   Backyardman Würzburg gezeigt (`410433/contact` → `backyardman.de`).
   **Das bei raceresult-Links immer prüfen** – seit dem 19.09.2026 macht
   das `scripts/veranstalter_links.py sammeln` (Kontaktseite abrufen,
   Organizer-URL prüfen, ob die Seite den Lauf nennt, dann `anwenden`).
   **Zeitnehmer und Anmeldeplattformen sind Portallinks** (vom Nutzer
   am 19.09.2026 entschieden: „zieh die anderen Zeitnehmer genauso
   nach"): raceresult, datasport, lanet3, racepedia, runtix, davengo,
   myracepartner, sas-online, maxx-timing, rennmeldung, time-and-voice,
   anmeldungs-service, laufmanager, triathlon-service, zeitgemaess,
   sportstiming, laufauswertung, berlin-timing, dazu die Kalender ladv,
   laufen-os und strassenlauf.org – alle in `PORTAL_DOMAINS`.
   `rennmeldung.de` sperrt `/cgi-bin/` per robots.txt: eintragen ja,
   abrufen nie (das Skript achtet robots.txt selbst).
3. **Distanzen immer auf eine Dezimalstelle** (`round_km()`): 42,195 → 42.2.
4. **`land` nie aus dem Event-Namen raten.** Der „Fränkische-Schweiz-Marathon"
   liegt in Bayern. Quelle: Landesangabe der Seite (`(Schweiz)`, `(AUT)`) oder
   Reverse-Geocoding der Koordinaten.

   **Südtirol ist die vierte Region** (vom Nutzer am 21.09.2026
   aufgenommen: „sehr viele Radrennen, ein sehr sportliches Bundesland –
   damit alle Ausdauer-Events im deutschsprachigen Raum"). Der Wert heißt
   **„Italien (Südtirol)"** (`scraper_lib.SUEDTIROL`), damit niemand ganz
   Italien erwartet, und steht in `LAENDER` (`scraper_lib`, `filters.js`,
   `laender.json`, `functions/index.js`, `filter-ui.js` `LAND_BY_CODE`
   `IT`). **„Italien" allein ist kein gültiger Wert**, nur ein
   Zwischenstand: `guess_land()` macht daraus Südtirol, wenn eine
   Südtiroler PLZ dabeisteht (`39010–39100` = genau die Provinz Bozen,
   `praezisiere_italien()`), `reverse_land()` und `filter_dach()` über
   die Koordinaten (`in_suedtirol()`: Punkt-in-Polygon gegen den Umriss
   in `laender.json` – Nominatim nennt die Provinz je nach Sprache
   „Bozen", „Bolzano" oder „Südtirol", der Umriss ist eindeutig; Trient
   liegt in derselben Region, aber außerhalb). Was danach noch „Italien"
   heißt, wirft `clean_events.drop_ausserhalb()` heraus (nach
   `fix_land()`, mit Bericht). `test_land` hält Meran (PLZ), Mailand
   (bleibt „Italien"), Bozen/Sterzing (drin), Innsbruck/Trient (draußen)
   fest. Die Ortsauswahl kennt 750 Südtiroler Orte (deutsch UND
   italienisch, wie GeoNames sie führt), Region „Südtirol".
5. **5-km-Mindestdistanz nur für `art1 == "Laufen"`** und nur bei *bekannter*
   Distanz. 3,5 km Freiwasserschwimmen ist eine ernsthafte Distanz.
   **Die Grenze ist hart** (vom Nutzer am 19.09.2026 entschieden: „Die
   Läufe unter 5km nicht aufnehmen"): Eine als „5 km" beworbene Strecke
   mit 4,80 km (Sedus Firmenlauf), eine 4,66-km-Runde (Bramfelder
   Winterlaufserie), 4,6 km (Hochplatten Berglauf) und 4,8 km
   (Herbstcross Saalfeld) stehen mit ihrer echten Länge im Override und
   fallen damit heraus. Wer eine solche Zeile prüft, trägt die gemessene
   Länge ein und lässt die Regel entscheiden – nicht die Marketingzahl.
6. **`art2`: spezifisch vor generisch.** „Straße"/Marathon steht in
   `ART2_KEYWORDS_LAUFEN` bewusst ZULETZT, sonst wird ein „Bergtrail
   Trail-Marathon" zum Straßenlauf. Zusätzlich: ab 20 Höhenmetern pro km gilt
   eine Strecke als Geländelauf und bekommt „Trail" (`art2_from_elevation()`).

   **„Trail", „Cross" und „Berglauf" sind EINE Kategorie: „Trail".** Alles
   drei ist Geländelauf, die Quellen benennen dieselbe Strecke mal so, mal
   so, und eine verlässliche Trennung gibt es nicht. **Treppenläufe
   (Towerruns, Schanzenläufe, „Stäffeleslauf") sind seit dem 21.09.2026
   ebenfalls Trail** („Ja Treppenläufe als Trail aufnehmen"); sie haben
   meist keine Distanz, nur Stufen, die Länge bleibt leer. Erst „Trail/Cross"
   (mit „Berg" daneben), am 19.09.2026 vom Nutzer erweitert und umbenannt:
   „Berglauf der Kategorie Trail/Cross hinzufügen und die Kategorie nur
   ‚Trail' nennen, das ist die beste Bezeichnung einfach für die ganzen
   Events." Die Laufen-Kategorien sind damit: Straße, Trail, Bahn,
   Hindernis, Backyard Ultra.
   Die drei Stichwort-Zeilen (trail / berg+höhenmeter / cross) bleiben
   trotzdem **getrennt und an ihrer Stelle**, weil „backyard" dazwischen
   steht (siehe Datenregel 9): „trail" VOR „backyard", Berg und Cross
   DAHINTER. Bestehende Daten zieht `clean_events.merge_art2()` nach
   (je Sportart, idempotent – „Cross" beim Triathlon bleibt); die
   Filterliste steht in `filter-ui.js` (`ART2_BY_ART1`), die Übersetzung
   in `filters.js` und `functions/index.js`, wo die alten Werte
   („Trail/Cross", „Berg") für geteilte Links von früher weiter
   übersetzbar sind – `test_scraper_lib.py` prüft, dass Stichwortliste
   und Filter dieselben Werte kennen.
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

   **Zwei Dauern sind zwei Wettbewerbe.** `_compatible_distance()`
   vergleicht bei Zeilen ohne Distanz die `dauer_h` – Stundenlauf und
   Halbstundenlauf des Döbelner Fackellaufs sind sonst EINE Zeile, und
   `manual_events.json` konnte den zweiten nicht anlegen, weil
   `is_same_event()` ihn für den ersten hielt. Fehlt eine der beiden
   Dauern, bleibt es beim Alten (unbekannt schließt nichts aus);
   `test_duplikate` hält alle drei Fälle fest.
   **Distanz gegen Dauer ist seit dem 21.09.2026 ebenfalls unvereinbar**:
   Ein 24-Stunden-Lauf ist nicht der Marathon derselben Veranstaltung.
   Vorher galt „unbekannte Distanz schließt nichts aus", und deshalb
   ließen sich Rokathon 24 h, die 24 Stunden van Halen und die
   6-/12-h-Challenge des Winterloop nicht neben ihre Marathon-Zeilen
   tragen (Elfter Durchgang). Am Bestand nachgezählt: Fünf
   Veranstaltungen trugen genau diese Struktur schon (Remshalden Run,
   Mad Chicken Run, …), dort hielt nur das abweichende Label die Zeilen
   auseinander – die Regel macht ausdrücklich, was der Bestand zeigte.
   Ohne JEDE Angabe bleibt es ein Duplikat.

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
9. **`art2` „Backyard Ultra"** – EIN Wert für Laufen UND Triathlon (vom
   Nutzer am 19.09.2026 zusammengelegt: „die Kategorie Backyard und
   Backyard Ultra zusammenfügen zu ‚Backyard Ultra'"; vorher hieß die
   Laufkategorie „Backcountry Ultra" und die Triathlon-Kategorie
   „Backyard"). Das Stichwort „backyard" (und „last man/person standing")
   steht in `ART2_KEYWORDS_LAUFEN` an einer bestimmten Stelle – Absicht,
   nicht Zufall:
   - **NACH** „Trail": ein reiner „Backyard Ultra" ist Last-Man-Standing,
     ein „Backyard Ultra **Trail**" dagegen ein Trailrun, der das Wort nur
     im Namen trägt.
   - **VOR** der Berg-/Höhenmeter-Zeile: ein Backyard mit „120 Höhenmeter
     pro Runde" bleibt ein Backyard.

   Das frühere Stichwort „backcountry" ist mit der Umbenennung
   **weggefallen**: Ein „Backcountry Ultra" ist ein langer Trailrun
   durch unwegsames Gelände, kein Rundenformat – er fällt über „trail"
   in die Trail-Kategorie. Kein Event im Bestand trug das Wort.
   Reihenfolge nicht „aufräumen".

   **Backyard Ultra TRIATHLON gibt es auch** (vom Nutzer am 19.09.2026
   genannt – „das ist jetzt neu, das gibts"): Der „Backyardman Würzburg"
   ist laut backyardman.de „die Weltpremiere eines neuen Ultra-Formats:
   ein Backyard-Ultra, erstmals kombiniert mit dem Triathlon" – je
   Zwei-Stunden-Runde 500 m Schwimmen, 20 km Rad, 5 km Laufen, bis nur
   eine Person übrig ist. Dafür steht **„Backyard Ultra" auch unter
   Triathlon** (`ART2_KEYWORDS_TRIATHLON`, ganz vorn – das Format zählt
   vor dem Gelände; `ART2_BY_ART1['Triathlon']`, Übersetzung in
   `filters.js` und `functions/index.js`). Die Länge bleibt leer wie bei
   jedem Backyard. `guess_art1()` entscheidet zuerst die Sportart, dann
   kommt aus beiden Listen derselbe Kategorie-Wert.

   **Die Backyard-Runde ist keine Distanz.** Ein Backyard läuft dieselbe
   Runde (klassisch 4,167 Meilen = 6,706 km, in den Quellen „6,7" oder
   „7 km") zur gleichen Stunde, bis nur noch eine Person weiterläuft.
   Deshalb:
   - Länge-Spalte zeigt **„–"**, wenn das Rennen zeitlich offen ist, und
     **„24 h"**, wenn es auf 24 Stunden begrenzt ist.
   - `clean_events.clear_backyard_lap_km()` nimmt bei Backyard-Ultra-
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
     Cross-Triathlon bekäme dort aber „Trail", also eine
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
   - **Der umgekehrte Fall: ein LAUF im Triathlon-Kalender** (vom
     Nutzer am 21.09.2026 am „O-SEE Ultra Trail" gemeldet: „Das ist ein
     reines Trail lauf Event. Triathlons können auch nicht wirklich ein
     Trail Event sein"). running.life führt die Trailläufe von O-SEE
     Sports (100K bis Minis) im Triathlon-Kalender, weil derselbe
     Veranstalter die O-SEE Challenge ausrichtet; `default_art1 =
     "Triathlon"` machte daraus Triathlons mit Kategorie „Trail" – eine
     Kategorie, die es beim Triathlon gar nicht gibt. Folge: Die vier
     Kinder-/Canicross-Zeilen unter 5 km blieben stehen, weil
     Datenregel 5 nur für Laufen gilt. Drei Dinge dagegen:
     - `guess_art1()` fällt bei `default_art1 == "Triathlon"` auf
       „Laufen" zurück, wenn der Name ein Laufwort trägt
       (`LAUF_IM_TRIATHLONKALENDER`: trail, marathon, lauf, run, ultra)
       und KEIN Mehrsport-Stichwort – die `ART1_KEYWORDS` laufen vorher,
       „XTERRA", „Cross Triathlon Trail Edition" und „Swimrun" bleiben
       Triathlon. Nur im Triathlon-Kalender: Im Laufkalender ändert sich
       nichts, im Radkalender bleibt ein „MTB Trail Marathon" Rad.
     - `fix_multisport_art1()` konvertiert nur Laufen → Triathlon, nie
       zurück; der Bestand braucht deshalb den **Override** (`art1:
       "Laufen"`, beide Datumsschlüssel, siehe „Die wichtigste Lektion").
       Mit `art1` Laufen greift Datenregel 5, die vier Zeilen fallen.
     - `report_triathlon_mit_laufkategorie()` meldet jede Triathlon-Zeile
       mit einer reinen Laufkategorie (`LAUF_KATEGORIEN_NUR_LAUFEN`:
       Trail, Bahn, Hindernis) – nur Hinweis, Override prüfen.
     `test_lauf_im_triathlonkalender` hält Treffer und Gegenproben fest.

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

14. **HYROX gehört nicht in die Liste – und Gymrace und die Decathlon
   Hybrid Series ebenso** (dieselbe Klasse, vom Nutzer am 19.09.2026
   bestätigt: „Ja HYROX ausschließen"). Die Seite führt Laufen,
   Schwimmen, Fahrrad und Triathlon. HYROX ist achtmal ein Kilometer
   Laufen im Wechsel mit acht Kraftstationen (Sled Push, Burpees, Wall
   Balls, Rudern) – man kann sich dafür nicht als Läufer anmelden.
   Vom Nutzer am 18.09.2026 entschieden, ausdrücklich „erst einmal".
   - `NICHT_AUSDAUER` in `scraper_lib.py` hält die Liste, angewendet
     beim Einsammeln (`filter_nicht_ausdauer`) und rückwirkend
     (`clean_events.drop_nicht_ausdauer`) – dieselbe Aufteilung wie bei
     den vergangenen Events.
   - **Die Liste ist winzig und leicht umzudrehen**: Zeile heraus, und
     beim nächsten Datenlauf sind die Events wieder da. Seit dem
     21.09.2026 (Entscheidungen des Nutzers) stehen dort: HYROX, Gymrace,
     Decathlon Hybrid Series, Runworx, Black Forest Team Battle
     („Keine Hyrox oder ähnliche Events mit Kraft Übungen"); **Gehen**
     (Race Walking, Geher-Wettbewerbe) und **Skilanglauf** („Gehen und
     Skilanglauf nicht aufnehmen"); **virtuelle Läufe** („Virtuelle
     Läufe rausnehmen" – geprüft wird auch der ORT, die XMAS-Challenge
     des Blauen Landes trug „virtuell" nur dort, `nicht_ausdauer_text()`).
     **Nicht** darunter fallen die Walking-/Nordic-Walking-Strecken
     innerhalb eines Volkslaufs (145 Zeilen) – das ist eine offene
     Frage an den Nutzer, siehe unten.
   - **Nur eindeutige Markennamen.** Ein Stichwort wie „Fitness" oder
     „Hindernis" wäre falsch: Ein Hindernislauf (Spartan, XLETIX,
     CrossDeLuxe, Muddy Angel, Tough Mudder) IST ein Laufformat und
     bleibt. `test_nicht_ausdauer` hält beide Seiten fest.

15. **Die Länge eines Triathlons ist die SUMME seiner Teilstrecken.**
   Der größte systematische Datenfehler, den die Einzelprüfung gefunden
   hat: `guess_distance_km()` nimmt bei mehreren Zahlen die größte – bei
   einem Triathlon ist das die **Radstrecke**. Deshalb stand die
   Kurzdistanz des Triathlon Höchstadt mit „40 km" in der Liste statt
   mit 51,5 km (1,5 + 40 + 10), der Niederrhein N3T mit 38 statt 49,5,
   Frankfurt City mit 80 statt 102, Indeland mit 88 statt 109,9, der
   Schloss-Triathlon Moritzburg mit 173 statt 218,8. Nennt die Quelle
   nur EINE Zahl, ist es stattdessen oft die Laufstrecke (Möhnesee 5 /
   10 / 15 statt 25,5 / 51,5 / 87).

   Eine Radstrecke als Länge des Rennens auszuweisen ist doppelt falsch:
   Die Zahl stimmt nicht, und sie sieht aus wie ein Radrennen.

   `summiere_teilstrecken()` (`scraper_lib.py`) fängt das beim
   Einsammeln ab. Drei Bedingungen, alle nötig, damit die Regel nur
   dort zuschlägt, wo wirklich Teilstrecken aufgezählt sind:
   - **Mindestens zwei verschiedene Disziplinen** mit eigener Zahl.
   - **Schwimmen oder Rad muss dabei sein.** Ein reiner Lauftext kann
     damit nie hineinrutschen.
   - **Je Disziplin genau EINE Angabe.** Zählt ein Text mehrere
     Wettbewerbe auf („Jedermann 400m Swim 20km Bike 5km Run …
     Kurzdistanz 1.500m Swim 40km Bike 10km Run"), lässt sich nicht
     sagen, welche Zahlen zusammengehören – dann lieber nichts.

   Die beiden Schreibweisen (Zahl vor dem Wort, Wort vor der Zahl)
   werden **getrennt** ausgewertet und nicht gemischt: In „400m Swim
   20km Bike 5km Run" passt auf „Swim 20km" auch die zweite
   Schreibweise, und Schwimmen bekäme 20 km statt 400 m.
   `test_mehrsport_teilstrecken` hält Treffer und Gegenproben fest.

   **Der Bestand ist damit NICHT geheilt** – die Regel wirkt erst beim
   nächsten Datenlauf, weil `clean_events.py` den Quelltext nicht mehr
   hat. Die vorhandenen Zeilen gehören einzeln geprüft;
   `report_triathlon_distanzen()` meldet sie (40 → 18 am 18.09.2026).
   Und eine Zuordnung Label → Standarddistanz wäre falsch: Deutsche
   Veranstaltungen weichen ab (Moritzburgs „Langdistanz" hat 173 km
   Rad, Frankfurts „Mitteldistanz" 80 km, Indelands 88 km).
   - Jeder Ausschluss wird **gemeldet**, nicht stillschweigend gemacht.

16. **Erst einmal keine Staffeln** (vom Nutzer am 21.09.2026
   entschieden). Eine Staffel ist ein Team-Wettbewerb; im Bestand stand
   mal die Team-Gesamtstrecke, mal die Teilstrecke. `ist_staffel()` in
   `scraper_lib.py` entscheidet in zwei Stufen, beide **am Bestand
   gezählt** (49 Zeilen mit „Staffel", 29 entfernt): Ein **Label**, das
   nur die Staffel beschreibt („ZEISS Marathon Staffel", „2x5 km
   Staffel", „DUO Marathon 2 x 21,1 km", „H/21 for Two"), nimmt diese
   eine Zeile; ein **Name**, der eine Staffelveranstaltung nennt
   (Staffellauf, Staffelmarathon, Firmenstaffel, Marathonstaffel,
   Staffel-Mix), nimmt alle Zeilen – auch die „5 km" des Ostsee
   Staffelmarathons, das ist seine Rundenlänge. **Gegenproben, die
   bleiben müssen**: Einzelrennen mit Staffel-Option („10 km Lauf und
   Staffel", „Einzel oder Staffel", „Solo oder Staffel"); Namen, in
   denen die Staffel nur Zusatz ist („Nikolauslauf mit Fun/Firmenstaffel",
   „Volks- und Staffeltriathlon"); die „GVG-Winterstaffel Pulheim"
   (Seite geprüft: Staffel PLUS Einzelstrecken 5/10/21,1/42,2 km) und
   die „Meckenheimer Apfelstaffel" („Einzelläufe und Staffeln") – deshalb
   fällt bewusst NICHT jedes „Staffel" im Namen; Orte (Staffelsee, Bad
   Staffelstein). `filter_staffeln()` beim Einsammeln,
   `clean_events.drop_staffeln()` rückwirkend, `test_staffeln` hält beide
   Seiten fest. Wer Staffeln zurückwill, nimmt die beiden Aufrufe heraus.

17. **Charity ist eine MARKIERUNG, keine Kategorie** – und der Weg
   dorthin ist die Lehre. Am 21.09.2026 wollte der Nutzer „eine neue
   Kategorie … die ‚Charity' heißt … alle Schwimmen, Lauf und Rennrad
   Charity Events"; sie kam als `art2`-Wert ganz vorn in die
   Stichwortlisten, vor jedes Gelände-Stichwort. **Am selben Tag hat er
   es zurückgenommen**: „Ich weiß das wir jetzt in der Kategorie
   ‚Charity' stehen drinnen haben. Aber da bitte wieder die Kategorie
   einfügen."

   Der Grund ist allgemein und steht deshalb hier: **Ein Merkmal, das
   QUER zu einer Einteilung liegt, darf nicht als weiterer Wert in sie
   hinein.** Ein Benefiz-Crosslauf ist ein Crosslauf, der für einen
   guten Zweck läuft – als Kategorie verdrängte „Charity" genau die
   Auskunft, die sie ergänzen sollte (der Bietlauf verlor sein „Trail",
   43 Zeilen verloren ihre Kategorie). Dieselbe Frage kommt wieder, bei
   „Frauenlauf", „Firmenlauf", „Nachtlauf", „Kinderlauf": Das sind alles
   Eigenschaften NEBEN dem Untergrund, keine Untergründe.

   Wie es jetzt aussieht:
   - **`charity: true` am Event** (`ist_charity()` in `scraper_lib.py`,
     gesetzt von `clean_events.fix_charity()`; wie `datum_vorlaeufig`
     None statt False, damit `to_dict()` es weglässt). `art2` bleibt die
     echte Kategorie, `refresh_art2()` holt sie für die Altbestände
     zurück.
   - **Stichwörter** wie bisher (charity, benefiz, spendenlauf/-marathon/
     -run, sponsorenlauf, wohltätig) plus **„guter Zweck"** in allen
     Beugungen: „Lauf für einen guten Zweck – Rastenberg" trug keines
     der alten und stand unmarkiert da (vom Nutzer am 21.09.2026
     gemeldet). Erkannt wird nur, was der NAME sagt – „Lauf gegen Krebs"
     und der Wings for Life World Run tragen kein Stichwort und bleiben
     unmarkiert. Ein Override kann `charity` setzen **und mit `false`
     abschalten**.
   - **Angezeigt** wird es als Herz in der Spalte **Kategorie** (nicht
     hinter dem Namen – die Namensspalte ist 23 % breit und kürzt mit
     „…", dort war das Herz bei jedem langen Namen unsichtbar). Eine
     leicht rosa hinterlegte Zeile dazu war gebaut und **vom Nutzer am
     selben Tag verworfen** („Das Herz … reicht aus"); die Klasse
     `.charity-row` bleibt an der Zeile, ohne Fläche. Die Detail-Box trägt ein eigenes
     Abzeichen neben dem Sport-Abzeichen. Farbe, Tonfläche und Textfarbe
     stehen als `--charity*` in beiden Schemata, nach demselben Muster
     wie die vier Sportfarben.
   - **Gefiltert** wird weiter über die Kategorie-Pille: „Charity" steht
     in `ART2_BY_ART1` (Laufen, Schwimmen, Fahrrad – nicht Triathlon,
     der Nutzer nannte drei Sportarten), und `EF.matchesKategorie()`
     löst den Sonderfall auf (`e.charity`, dazu `art2 === 'Charity'` für
     geteilte Links von früher). **Dieselbe Auflösung steht in
     `functions/index.js`** – laufen die beiden auseinander, bekommt
     jemand E-Mails über Events, die seine Suche nie gezeigt hat.
   - `test_kategorie` hält beides fest: dass `ist_charity()` greift UND
     dass die Kategorie dabei erhalten bleibt.

18. **Abgesagt, nicht öffentlich, Schule – per Override** (vom Nutzer am
   21.09.2026 entschieden: „Abgesagte Veranstaltungen bitte nicht
   aufführen", „Nicht öffentliche Läufe nicht aufnehmen. Es soll jeder
   die Chance haben sich … anzumelden", „Schul Events bitte nicht
   aufnehmen"). Keine Regel kann das erkennen, deshalb `exclude` mit
   Beleg in `manual_overrides.json`: Marner Kohltagelauf 2026 (beide
   Zeilen), Benefizlauf der Wiehenläufer 2026 („krankheitsbedingt …
   AUSFALLEN"), Belgershainer Crosslauf (seit 2022 nicht mehr
   ausgeschrieben), ClimAid Plant a Tree Run (Getränkemarke, kein Lauf
   2026); 67. Panorama Marathon (Running Paule, „nicht öffentlicher
   Trainingsmarathon"), X-Mas StairRun Oberhof (nur Feuerwehr/Polizei),
   Schanzenlauf Oberstdorf (Feuerwehr-Treppenlauf in Teams, umkehrbar);
   Bonner Friedenslauf (Schul-Spendenlauf). **Meisterschaften bleiben,
   wenn jeder starten kann** – die sieben im Rahmen eines Volkslaufs
   sind Duplikate des Volkslaufs und bleiben draußen (der Volkslauf
   steht in der Liste), die Polizeimeisterschaft (Potsdamer Cross) ist
   nicht offen. Spenden- und Spaßformate ohne Distanz (Sterntaler, STELP,
   ProSana, The Quest, Tragathlon, Pace Race) **bleiben** („Ja bitte
   aufnehmen"), Weinathlon auch (keine Kraftübungen). `seitenabgleich.py`
   meldet seit dem Tag **ABGESAGT**, wenn die Veranstalterseite von
   Absage/Ausfall spricht – nur Hinweis, der Kohltagelauf wirbt neben
   der Absage weiter mit „Melde dich jetzt an". Der Neunkirchner
   Sommerlauf ist KEIN Absage-Fall mehr: Die Seite dankt inzwischen für
   die Teilnahme 2026.

19. **Vorläufige Termine tragen `datum_vorlaeufig`** (vom Nutzer am
   21.09.2026 entschieden: „kein konkretes Datum auf jeden Fall, wenn
   noch kein genauer Tag genannt wurde"). Viele Kalender tragen den
   Termin des nächsten Jahres vor, bevor der Veranstalter ihn
   veröffentlicht hat (der Elfte Durchgang fand ~180 „Seite zeigt 2026,
   2027 nicht ausgeschrieben"). Solche Zeilen zeigen in Liste, Box,
   Karten-Popup und E-Mail nur **„Juni 2027*"** (`EF.formatEventDate`,
   `EED.formatEventRangeHtml`, `datumText` in `functions/index.js`), die
   Box sagt „Termin noch nicht veröffentlicht" statt „in 6 Tagen", die
   Fußzeile trägt die Fußnote (nur sichtbar, wenn es markierte Zeilen
   gibt), die Kalenderdatei „(Termin vorläufig)" im Titel. Gefiltert und
   sortiert wird weiter mit dem Prognose-Tag – er ist die beste Schätzung.
   - **Nur per Override** (`OVERRIDE_FIELDS`), aus der Einzelprüfung:
     Keine Regel kann eine Prognose von einem echten Termin
     unterscheiden. 56 Veranstaltungen (94 Zeilen) sind markiert –
     die `unklar`-Fälle des Elften Durchgangs ohne Silvester-/
     Neujahrsläufe (der Tag ist dort durch den Kalender fest).
   - **Der Override hängt am vorläufigen Datum**: Bringt der Datenlauf
     einen anderen Tag, greift er nicht mehr, das Sternchen verschwindet
     von selbst. Bringt er denselben Tag, bleibt es – deshalb meldet
     `seitenabgleich.py` **BESTAETIGT**, wenn die Seite unser Datum
     inzwischen nennt; dann den Override löschen. Neue Prognosen findet
     derselbe Lauf als DATUM.
   - `test_datum_vorlaeufig` hält Override-Feld, `to_dict()` (kein
     `false` in events.json) und die Kalenderdatei fest.

20. **Hindernisläufe: die Marke oder der PLURAL.** Vom Nutzer am
   21.09.2026 an einer einzigen Zeile gemeldet („Xletix Challenge -
   Berlin ist ein Hindernis lauf und kein Lauf auf der Straße") – die
   Nachzählung machte daraus **58 Zeilen**: alle 18 XLETIX-, 13 Muddy-
   Angel-, 5 CrossDeLuxe-, 4 Mud-Masters-Zeilen und die Rats-Run-/
   Hotfoot-Serien standen als Straßenlauf da. Die Stichwortliste kannte
   nur `hindernislauf|obstacle|ocr|spartan|tough mudder`, und kein
   Veranstalter nennt seine Veranstaltung „Hindernislauf" – er nennt
   sie „XLETIX Challenge" und schreibt „mit 15 Hindernissen" daneben.
   Zwei Wege deshalb:
   - **Die Markennamen** (xletix, muddy angel, mud masters, crossdeluxe,
     rats-run, hotfoot, dazu die alten). Eindeutig, also eine Tatsache –
     dieselbe Linie wie bei `NICHT_AUSDAUER`: „Fitness" wäre geraten,
     „XLETIX" ist es nicht.
   - **Die PLURALFORM „Hindernisse(n)"** und „Hindernis-Lauf". Der
     Plural ist der ganze Trick: Ein Hindernislauf wirbt mit ihrer ZAHL
     („mit 15 Hindernissen", „25+ Hindernisse", „mind. 30 Hindernissen"),
     der SINGULAR steht dagegen in gewöhnlichen Läufen – der „TIME2RUN
     Silvesterlauf in Schwabmünchen" nennt „kein Wasserhindernis" bzw.
     „mögliches Wasserhindernis". Ein Muster auf „hindernis" ohne Plural
     hätte ausgerechnet die Zeile zum Hindernislauf gemacht, die es
     ausdrücklich VERNEINT. Beide Gegenproben stehen in
     `test_kategorie`.

   Zwei Änderungen an `clean_events.refresh_art2()` gehören dazu, beide
   am Bestand nachgezählt (die Linie der „wichtigsten Lektion": erst
   zählen, was eine Regel anrichtet):
   - Es liest jetzt **Name UND Wettbewerbs-Label**. Die Gattung steht oft
     nur im Label („Hot-20 (40 Hindernisse)", „9,2 km Crosslauf"), und
     `expand_competitions()` liest es beim Einsammeln längst mit. Vier
     Zeilen ändern sich zusätzlich, alle vier zu Recht (Crossläufe, die
     als Straße standen).
   - **Hindernis schlägt Trail.** Sonst bleibt es dabei, nur Generisches
     zu ersetzen; hier ist die Ausnahme die Reihenfolge der
     Stichwortliste selbst (Hindernis steht VOR Trail, weil ein
     Hindernislauf durchs Gelände immer noch ein Hindernislauf ist).
     Fünf Zeilen standen nur deshalb als Trail, weil „Cross" in ihrem
     Namen steht (CrossDeLuxe Erzgebirge, „Puls 300 Cross- und
     Hindernis-Lauf", der Berserker des Legend of Cross) – und ihre
     Schwesterveranstaltungen wären danach Hindernis gewesen, sie nicht.

   **Die allgemeine Lehre**: Eine gemeldete Zeile ist selten eine
   einzelne Zeile. Erst zählen, wie viele derselben Klasse angehören,
   dann eine Regel bauen – ein Override hätte hier 1 von 58 Fällen
   erledigt und die anderen 57 beim nächsten Datenlauf erneut erzeugt.

21. **Die Länge eines Triathlons entscheidet auch das SCHWIMMEN.** Vom
   Nutzer am 21.09.2026 am „2. Weinstadt Triathlon" gemeldet: 0,3 km
   Schwimmen / 18,7 km Rad / 4,6 km Laufen, und die Box schrieb „Sprint"
   – richtig ist **Super-Sprint**. Die Summe 23,6 km liegt knapp über
   der Sprint-Grenze (23 km), der Schwimmteil von 300 m aber unter dem
   kleinsten Sprint-Schwimmen (500 m).

   Zwei Zeilen daneben zeigen, dass die Summe das **grundsätzlich** nicht
   leisten kann: Der Berliner Volkstriathlon hat bei 23,7 km Gesamtlänge
   700 m Schwimmen (ein echter Sprint), der Stadttriathlon Erding bei
   25,4 km nur 400 m. Dieselbe Summe, verschiedene Formate – die
   Radstrecke gleicht den kurzen Schwimmteil wieder aus.

   `triathlonFormat()` (`event-detail.js`) liest deshalb die
   Schwimm-Teilstrecke aus dem Label, wenn sie dort steht. Bewusst eng:
   nur wenn das Label sie überhaupt nennt, nur NACH unten (auf
   Super-Sprint) und nur, wenn **kein** Format-Stichwort im Label steht –
   ein als „Jedermann Sprint" ausgeschriebenes Rennen bleibt ein Sprint,
   auch mit 400 m Schwimmen. Am Bestand nachgezählt: **zwei** Zeilen
   ändern sich (Erding und der Günzburger Cross Triathlon, beide 400 m).

   Damit das greift, gehört die Aufteilung ins Label – die Schreibweise
   steht schon in „Elfter Durchgang": Gesamtlänge vorn, Teilstrecken in
   Klammern. Für Weinstadt ist das ein Override.

   **Filter und Anzeige sagen dasselbe** (seit dem 21.09.2026, abends):
   `triathlonFormat()` wohnt in `filters.js`, `event-detail.js` ruft es
   von dort, und `matchesDistanceCategory()` prüft beim Triathlon das
   FORMAT gegen die gewählte Kategorie (`TRIATHLON_FORMAT_KATEGORIE`:
   olympisch → `olympic`, ultra → `tultra`), nicht die rohen Kilometer.
   Vorher zeigten drei Zeilen ein Format, das ihre Filterkategorie nicht
   teilte. `functions/index.js` trägt die Kopie für den Abo-Filter;
   `test_triathlon_format_kopie` vergleicht beide Fassungen Zeile für
   Zeile UND prüft an jeder Triathlon-Zeile des Bestands, dass der Filter
   genau die Kategorie trifft, die die Spalte anzeigt.

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

**Ein Override, der `laenge_km` ändert, bricht seinen eigenen
distanzgenauen Schlüssel.** Die Distanz im Schlüssel ist die ALTE; sobald
der Override gegriffen und die Zahl in `events.json` geändert hat, findet
`find_override()` ihn über die NEUE Distanz nicht mehr. Zwei Folgen, beide
real aufgetreten:

- **Innerhalb desselben Laufs**: Schritte, die den Override erneut
  abfragen, sehen ihn nicht. Beim OstseeMan Glücksburg setzte ein
  Override den „6 km Triathlon"-Eintrag auf 5,5 km Laufen (es ist der
  Charity Run der Veranstaltung) – `fix_multisport_art1()` suchte den
  Override dann mit 5,5 km, fand ihn nicht und setzte `art1` wegen des
  Wortes „Triathlon" im Veranstaltungsnamen wieder zurück.
- **Beim nächsten Lauf**: Ein `exclude` unter dem alten Schlüssel trifft
  nichts mehr.

**Allgemeiner und distanzgenauer Schlüssel liegen seit dem 20.09.2026
ÜBEREINANDER**: `find_override()` mischt „<Name>|<Datum>“ und
„<Name>|<Datum>|<km>“, der distanzgenaue gewinnt bei Widerspruch.
Vorher gewann der erste Treffer allein, und ein `veranstalter_url` im
allgemeinen Eintrag war für jede Strecke mit eigenem Eintrag unsichtbar
(sechs Fälle, siehe „Zehnter Durchgang“).

Deshalb: **`laenge_km` und `art1` nie im selben Override ändern.** Wo
eine Zeile eigentlich eine andere Veranstaltung ist (ein Volkslauf im
Rahmen eines Triathlons), gehört sie unter ihren eigenen Namen in
`manual_events.json` – dann greift `guess_art1()` richtig. Und wo beides
nötig ist, beide Schlüssel eintragen (alte UND neue Distanz).

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
   die Regel, nicht die Ausnahme. **Die fehlende Wortgrenze bleibt** –
   auch jetzt, wo das Stichwort „Trail" statt „Berg" ergibt: Ein
   Limberglauf ist ein Geländelauf, kein Straßenlauf.
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
     Damit trug auch die alte Begründung für den **Ort im
     ICS-Dateinamen** nicht mehr; das Ersatzbeispiel „TEAG - Legend of
     Cross - Mühlberg" ist am 21.09.2026 denselben Weg gegangen (Drei
     Gleichen = Mühlberg, zusammengeführt). Der Ort bleibt im Namen -
     Begründung an der Stelle in `event-detail.js`.
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

### Dritter Durchgang: die Berichte abgearbeitet (18./19.09.2026)

Statt der nächsten 200 nach Datum wurden diesmal die **Berichte**
durchgegangen – `audit_events.py --offen` und die `⚠`-Meldungen von
`clean_events.py`. Das ist die ergiebigere Reihenfolge: Dort steht, wo
etwas nicht stimmen KANN, statt jede Zeile gleich zu behandeln.

Stand danach (4.335 → **4.248 Events**, 279 Overrides, 194 Einzel­prüfungen
im Protokoll, 46 nachgetragene Strecken):

| Bericht | vorher | nachher |
|---|---|---|
| Gleicher Tag, Ort und Distanz, anderer Name | 57 | 7 |
| Triathlon-Distanz passt zu keinem Format | 40 | 15 |
| Gleiche Veranstalter-Seite, gleiche Distanz | 32 | 5 |
| Verdächtige Distanz | 23 | 18 |
| Mehrsport: Zeile sieht nach Teilstrecke aus | 3 | 0 |
| `audit`: Veranstaltung >1 Woche | 44 | 0 |
| `audit`: auffällige Distanz | 24 | 0 |
| `audit`: keine Koordinaten | 12 | 0 |
| `audit`: Zahl im Label weicht ab / Berglauf / „Marathon" / Name sehr lang | 5/4/6/5 | 0 |

**Die scharfen Kategorien von `audit_events.py --offen` sind damit leer.**
Übrig bleiben dort nur 897 Portallinks, 320 Zeilen ohne Distanzangabe und
120 Termine von Montag bis Donnerstag – alles drei keine Fehler, sondern
Lücken oder Eigenheiten der Quellen.

Die Reste in den `clean_events.py`-Berichten sind **geprüft und keine
Fehler** – gemeldet werden sie nur, weil die Bedingung grob ist (± 0,5 km,
oder „passt zu keinem der vier Standardformate").

Fünf Muster, die dabei herauskamen und beim großen Datenlauf wieder
auftreten werden:

1. **Dieselbe Veranstaltung unter zwei Namen.** Einmal der förmliche
   Kalendername von laufen.de (ohne Wettbewerbs-Label, mit Portallink),
   einmal die Seite des Veranstalters (mit allen Strecken und Labels).
   `is_same_event()` sieht das nicht – „33. Lauf Rund um den Grengel"
   und „Grengellauf" haben kein gemeinsames Wort. 29 Fälle.
2. **Meisterschaften, die IM Rahmen eines Volkslaufs laufen**, stehen
   ein zweites Mal im Kalender (Bayerische Halbmarathon-Meisterschaften
   = Aschaffenburger Halbmarathon, Deutsche Polizeimeisterschaften =
   Crosslauf in den Ravensbergen). Wer starten will, meldet sich beim
   Volkslauf an. 7 Fälle – das ist eine Entscheidung, die der Nutzer
   umdrehen kann.
3. **Laufserien**: `expand_competitions()` hängt jede Distanz an jeden
   Termin. Bei der Hammer Winterlaufserie waren von neun Zeilen sechs
   erfunden. Und die Zeilen des ERSTEN Termins spannen oft bis zum Ende
   der Serie (Bramfelder, Alfter, Bühlauer, Wilhelmsburg, HKK).
4. **Ein Datenfehler verdeckt ein Duplikat.** Dreimal an einem Tag:
   Fehlende Koordinaten beim Rodheimer Volkslauf, ein falsches Datum
   beim Britzinger Silvesterlauf, ein falscher Ort beim Isar-Lauf Bad
   Tölz – erst nach der Korrektur griff die Duplikat-Erkennung (ihre
   Ortsbedingung erlaubt 30 km, mehr nicht).
5. **Die Radstrecke als Länge des Triathlons** – siehe Datenregel 15,
   der größte systematische Fehler im ganzen Bestand.

Offen geblieben und im Protokoll als `unklar` abgelegt (11 Fälle),
darunter drei, die eine **Entscheidung des Nutzers** brauchen:

- **Virtuelle Läufe**: „Blaues Land läuft – XMAS-Challenge" ist „Egal wo,
  egal wann", fünf Wochen lang, ohne Ort und ohne Koordinaten. Gehören
  solche Events in eine Liste, die auf Karte und Umkreissuche gebaut ist?
- **Abgesagte Veranstaltungen** erkennt niemand – weder die Scraper noch
  `clean_events.py`. Beim Marner Kohltagelauf schreibt der Veranstalter
  „Leider müssen wir den Kohltagelauf 2026 … absagen!", wirbt daneben
  aber weiter mit „Melde dich jetzt für 2026 an!".
- **Staffeln**: Beim Celler Staffelmarathon steht die TEAM-Gesamtstrecke
  in `laenge_km` (42,195 km auf vier Läufer), beim „DUO Marathon
  2 x 21,1 km" dagegen die Teilstrecke. Das gehört vereinheitlicht.

### Vierter Durchgang: die Veranstalter-Links von 500 Veranstaltungen (19.09.2026)

Auf Wunsch des Nutzers („checke 500 Events, ob die alle die richtige
Veranstalter-Webseite haben – auch googeln"). Geprüft wurden die
**ersten 500 Veranstaltungen nach Datum** (18.09.–03.10.2026, ~900
Zeilen), Protokoll in `scripts/links_geprueft.json`. Vorgehen:

1. **Jeden Link abgerufen** (Status, Titel, ob die Seite Event oder Ort
   nennt). 379 eigene Seiten, davon 352 erreichbar und passend, 27 mit
   403/404/Timeout.
2. **`my.raceresult.com` → `/contact`** (47 Fälle; robots.txt erlaubt
   die Seite). Die Organizer-URL steht dort im JSON-LD
   (`"organizer":{…,"url":…}`) – 24-mal brauchbar, sonst leer,
   Platzhaltertext („Geben Sie hier die Veranstaltungs-Website an"),
   Facebook, Zeitnehmer oder Stadt-Homepage.
3. **Portal- und Anmeldelinks (74) sowie tote Links per Websuche**, die
   gefundene Seite abgerufen und gegen Event/Datum geprüft. Geraten
   wurde nichts: Wo nur Kalender und Anmeldeportale auftauchten, bleibt
   der alte Link (`unklar`).

Ergebnis: **77 korrigiert** (Overrides in `manual_overrides.json`, je
mit `_note` und Quelle), **394 in Ordnung**, **29 unklar**. Was dabei
außer Links herauskam – **alles Entscheidungen des Nutzers, nichts
davon ist umgesetzt**:

- **Sechs Duplikate unter zwei Namen** (jetzt mit derselben Seite,
  deshalb meldet `report_gleiche_seite_gleiche_distanz()` 12 statt 5):
  Wehringer Wertachlauf (19.09.), Panoramalauf Kriegsheim/Monsheim
  (20.09.), Herbstlauf Fleckenberg (20.09.), Zonser Nachtlauf (25.09.),
  Ellernstaffellauf Rastede (27.09.), Weezer Staffellauf (26.09.). Dazu
  die **Saarländische 5-km-Meisterschaft**, die IM Altstadtlauf
  Ottweiler läuft (Meisterschaft-im-Rahmen-Fall).
- **Abgesagt laut Veranstalter**: Bordesholmer SEE&RUN 2026
  („Fokus auf 2027"); wahrscheinlich auch Benefizlauf der Wiehenläufer
  („krankheitsbedingt", ohne Jahr) und Crosslauf Jüchen (Vereinsseite:
  „wird nicht mehr durchgeführt", raceresult-Seite weg).
- **Datenhinweise**: Running Paule RP-Marathon steht bei uns am 20.09.,
  die Seite nennt den 19.09.; VfL Nagold bewirbt den 18.09. als
  „Herbstlauf unter Flutlicht" (bei uns „Mittsommerlauf"); Schildberglauf
  liegt laut Kalendern in Schildau, nicht Lossatal; Wunnebad Swim&Run
  ist 2026 nur für Jugendliche; DKB Staffellauf Liebenberg laut
  kulturfeste.de am 14.09. statt 19.09.
- **Ein Fehler im Code**: `is_portal_link()` verglich Teilzeichenketten
  – `tsv-weeze-leichtathletik.de` galt als Portal („leichtathletik.de"
  steckt drin), der echte Veranstalter-Link wäre beim nächsten Datenlauf
  ersetzbar gewesen. Jetzt Hostname-Vergleich, mit Test.

**Zeitnehmer-Seiten sind Portallinks** (vom Nutzer am 19.09.2026 am
Kallinchen Triathlon gemeldet: berlin-timing.de schreibt fett
„Informationen zur Veranstaltung entnehmen Sie bitte der
Veranstalterseite" samt Link – und bei uns stand der Zeitnehmer). Warum
das durchgerutscht war: Die Linkprüfung hatte nur die ersten 500
Veranstaltungen nach Datum (bis 03.10.2026) angesehen, der Triathlon
liegt im August 2027; und `berlin-timing.de` stand in keiner Liste, also
meldete auch `audit_events.py` ihn nicht als Portallink. Jetzt: alle
acht Veranstaltungen mit diesem Zeitnehmer auf die dort genannte
Veranstalterseite gesetzt (Protokoll in `links_geprueft.json`; Krummensee
aus der Sandbox nicht abrufbar, Volkstriathlon unter neuem Pfad),
`berlin-timing.de` in `PORTAL_DOMAINS` und
`WEITERLEITUNG_KEIN_VERANSTALTER`. **Die anderen Zeitnehmer** (raceresult,
datasport, lanet3, racepedia, runtix, davengo, …) stehen seit dem
19.09.2026 ebenfalls in `PORTAL_DOMAINS` (vom Nutzer so entschieden);
bei raceresult liegt die Veranstalterseite auf `/contact`, und
`scripts/veranstalter_links.py` holt sie (Punkt 10, gebaut).

Was die Sandbox nicht kann: Einige Seiten blocken automatische Abrufe
(403, Sicherheitscheck) oder scheitern am Proxy; die stehen als
`link_ok` mit Hinweis, weil die Adresse eventspezifisch und in der
Websuche belegt ist.

### Fünfter Durchgang: „Verdächtige Distanz" leer geprüft (19.09.2026)

Die zwölf offenen Fälle aus `report_suspicious_distances()` einzeln an
der offiziellen Ausschreibung geprüft (Protokoll in `geprueft.json`).
**Fünf Zeilen waren falsch** und stehen als `exclude` in
`manual_overrides.json`: Möhnesee-Pokal-Lauf 30 km (2026 durch den
Halbmarathon ersetzt, die 30 km waren das Programm 2025), Entega
Nightrun 10 km (nur 2,5 / 5 / 7,5 km), Crosslauf Friedrichsruh 25 km
(laufen.de führt „2,5km Kreismeisterschaft" mit „25 km"), und zwei
Serienzeilen der Winterlaufserie Drelsdorf (15 km am 10.01., 10 km am
07.02. – jeder Termin hat andere Distanzen). **Der Chiemgauer100
StundenRundenLauf ist ein 24-Stunden-Rennen** (Stundenrunden à 6,7 km,
100 km und 100 Meilen werden nur „gesondert ausgezeichnet") und steht
jetzt mit `dauer_h` 24 statt „100 km". Drei Veranstalter-Links dabei
nachgetragen (Werdau, Thülsfelder Talsperre, Rodenbach), einer davon
über die raceresult-Kontaktseite (Chiemgauer100).

**Die übrigen neun Meldungen sind echte Strecken** (Mud Masters 42 km,
Helbetal-Halbmarathon 21 km, Harry-Arndt-Lauf 50 km, L³ 47 km Ultratrail
aus drei Runden, Porz 21,1 km, Thülsfelder 10 englische Meilen, Drelsdorf
15 und 21,1 km, Werdau ¾-Marathon 31 km) – der Bericht meldet sie
weiter, weil die Bedingung grob ist; wer dort steht, steht auch in
`geprueft.json`. Damit sind **alle** `clean_events.py`-Berichte
abgearbeitet; was sie noch nennen, ist geprüft und wartet auf eine
Entscheidung des Nutzers (siehe „Was der Nutzer noch entscheiden muss").

Nebenbefund: **PDF-Ausschreibungen lassen sich in der Sandbox lesen** –
`pypdf` ist kaputt (`cryptography`-Backend), aber ein kleiner
Zlib-plus-ToUnicode-Dekoder (im Chat gebaut, nicht im Repo) reichte für
die Werdauer Ausschreibung. Falls das öfter gebraucht wird, lohnt sich
ein `scripts/pdf_text.py`.

### Sechster Durchgang: die Wochentage Mo–Do (19.09.2026)

Die 120 Zeilen der Audit-Kategorie „Wochentag Mo–Do“ durchgesehen
und die ~45 Veranstaltungen mit echtem Zweifel an der offiziellen
Seite geprüft (Feiertage, Silvester, Heiligabend, Dreikönig,
Rosenmontag, Buß- und Bettag und die Mittwochabend-Stadt- und
Campusläufe brauchten keine Prüfung). **Kein einziges Datum war
falsch** – Stundenläufe, Firmenläufe und Campusläufe liegen wirklich
unter der Woche. Gefunden wurden dafür sechs andere Fehler:

- **Falscher Link auf ein anderes Rennen**: Der „Sparkassen
  Uni-Triathlon“ (Magdeburg, Barleber See) zeigte auf den *Berliner*
  Uni-Triathlon. Jetzt usc-triathlon.de, dazu die Sprintdistanz
  500 m / 20 km / 5 km = 25,5 km.
- **Gerundete Distanzen**: Karlsruhe Volkslauf 11 → 10,5 km,
  Frühlingslauf Schwerin 11 → 10,5 km, Martinslauf Sindorf 7 → 6,6 km.
- **Zeitrennen ohne Maßzahl**: Rastenberg (4-Stunden-Spendenlauf auf
  der 400-m-Runde), Döbelner Fackellauf (Stundenlauf; der
  Halbstundenlauf nachgetragen – dafür musste `_compatible_distance()`
  Dauern vergleichen lernen, siehe Datenregel 8).
- **Idar-Obersteiner Felsenkirche Treppenlauf mit 42,2 km** – es sind
  5,4 und 8,1 km (aus „Marathonteam Hagner“ wurde ein Marathon).
- Drei Veranstalter-Links über die **raceresult-Kontaktseite** (Haus
  Vortlage, Wild & Run, Idar-Oberstein); bei PULSEDAY, Töwerland und
  Fun & Erlebnis Marathons nannte sie nur Verband, Kurverwaltung oder
  einen abgeschalteten Blog – Link bleibt.

Was daraus als **Entscheidung** übrig bleibt: Treppenläufe (neuer Punkt
13), zwei weitere 4,6/4,8-km-Läufe für Punkt 4, und drei
2027-Termine, die nur Prognosen sind (Borkener Citylauf 07.06.2027 ist
ein Montag – die 2026-Ausgabe war Sonntag, der 7.6.; Wild & Run und
Uni-Triathlon Magdeburg haben ihren 2027-Termin noch nicht
veröffentlicht). Solche **Jahreswechsel-Prognosen** erkennt keine Regel;
sie fallen erst auf, wenn der Wochentag nicht passt.

**Die Audit-Kategorie bleibt** – sie hat die sechs Fehler gefunden,
nicht als Datumsfehler, sondern weil man dafür die Seite aufruft.

### Siebter Durchgang: Zeilen ohne Distanzangabe (19.09.2026)

316 Zeilen stehen ohne `laenge_km` und ohne `dauer_h` in der Liste –
sie zeigen „–" und treffen nie einen Längenfilter. Die frühesten ~90
davon an der offiziellen Seite geprüft (Protokoll in `geprueft.json`,
Stand danach 268 offen). Ergebnis, ehrlich gerechnet:

- **~30 % bekamen ihre Distanz** – meist erst auf der Unterseite
  „Strecken"/„Ausschreibung", die Startseite nennt sie fast nie. Oft
  waren es gleich mehrere Wettbewerbe (Balkantrassenlauf 42,2 / 21,1 /
  10 / 5 km, Run and Bike Berlin 42 / 21 / 10 km, triathlon.de CUP
  Königsbrunn 25,5 / 51,5 / 101,9 km, Pöhl Trail 21 / 12 / 5 km,
  Remshalden Run 11,4 / 5,7 km + Staffel + Stundenlauf) – **eine Zeile
  ohne Distanz verbirgt häufig eine ganze Veranstaltung.**
- **Ein Viertel sind Runden- oder Zeitformate** (Stundenläufe,
  Paarläufe, Spendenläufe auf der 400-m-Bahn) – die mit fester Dauer
  stehen jetzt als Zeitrennen, der Rest wartet auf Punkt 14.
- **Fehler nebenbei**: Drachentriathlon ist 2026 ein Duathlon am 20.09.
  (19.09. war der Kinderduathlon); Hünsborn 2 be Wild ist ein
  Lauf-MTB-Lauf-Duathlon (29 / 43,4 km), stand als Trailrun; Wetzede
  fand am 12.09. statt (stand am 19.09.); drei Bergsprints und ein
  Jugend-Staffelcross unter 5 km fielen heraus.
- **raceresult-Kontaktseiten** (vom Nutzer gewünscht): 17 abgerufen,
  6 brauchbare Organizer-URLs (Remshalden, Meckenheim, Sägerserie,
  Chiemgauer100, Haus Vortlage, Wild & Run); der Rest Platzhalter,
  Zeitnahme-Firma, Stadt oder Verband.

Womit die Sandbox nicht weiterkommt: Strecken nur als **Bild** (Northeim),
als **PDF mit kaputter Zeichenzuordnung** (Sondershausen), hinter
**Polar-Flow-Links** (Rimsingen) oder auf **raceresult-Infoseiten**
(dynamisch, nicht lesbar – Oppau, Apfelstaffel). Und **Jahreswechsel-
Prognosen** (Borken) sieht keine Regel.

### Achter Durchgang: die laufen.de-Weiterleitungen (19.09.2026)

Beim Prüfen eines Portallinks fiel auf, dass **jeder gespeicherte
`laufen.de/laufkalender/details/<id>`-Link per 302 weiterleitet** –
auf genau den Veranstalter-Link, den der DLV-Kalender selbst hinterlegt
hat. 208 verschiedene Detaillinks (215 Zeilen) per HEAD aufgelöst
(2 s Pause), 182 hatten ein Ziel. Dann jede Zielseite abgerufen und
geprüft, ob sie den Lauf nennt (ein unverwechselbares Wort des Namens
oder das Datum im Text bzw. im Hostnamen – „lauf", „marathon",
„Sparkasse" zählen nicht):

| | Zahl | Folge |
|---|---|---|
| Zielseite nennt den Lauf | **120** Veranstaltungen | Override `veranstalter_url`, protokolliert in `links_geprueft.json` (`korrigiert`) |
| Zielseite nennt ihn nicht erkennbar / leer | 45 | `unklar` mit dem Ziel in der Notiz – Portallink bleibt |
| Ziel ist selbst Portal oder Anmeldung (lanet3, raceresult, datasport, racepedia) oder gar keine Adresse | 14 | `link_ok`, kein besserer Link |
| kein Redirect (laufen.de zeigt die Detailseite selbst) | 26 | nichts zu tun |

Damit sind von 215 laufen.de-Portalzeilen **98 übrig**; die
Audit-Kategorie „Portallink" fällt von 791 auf rund 100 laufen.de- plus
die raceresult-Zeilen. Für NEUE Events erledigt das seit dem 19.09.2026
der Scraper selbst (Punkt 15, gebaut). Die Werkzeuge liegen nicht im Repo (zwei kurze
Skripte im Chat); wenn der Nutzer Punkt 15 ablehnt, lohnt ein
`scripts/laufen_redirects.py` nach demselben Muster.

**Die raceresult-Kontaktseiten sind dagegen mager**: 23 weitere
abgerufen, alle schon in der Linkprüfung vom Vortag – und zwei
„Funde" (crossfitrecklinghausen.de, tusem-leichtathletik.de) waren
dort bereits als 404 bzw. leere Domain abgelegt. **Vor jeder
Linkarbeit `links_geprueft.json` UND `geprueft.json` filtern**, nicht
nur eines von beiden. 225 raceresult-Veranstaltungen sind noch ganz
ungeprüft (Punkt 10).

### Neunter Durchgang: die Veranstalterseite hinter Zeitnehmer- und Portallinks (19.09.2026)

Auf Wunsch des Nutzers („zieh die anderen Zeitnehmer genauso nach … check
ob es ein Link zu der offiziellen Webseite gibt, so viele wie möglich
seriös"). Dafür gibt es jetzt `scripts/veranstalter_links.py` mit vier
Modi, alle ohne Raten – übernommen wird nur, was die Zielseite am
Namen des Laufs belegt (`nennt_den_lauf()`: ein unverwechselbares
Wort des Namens im Text oder im Hostnamen, oder das Datum):

| Modus | tut | Ergebnis |
|---|---|---|
| `sammeln --bericht` | ruft jeden Portallink ab (raceresult: die `/contact`-Seite, sonst die externen Links der Seite), prüft jede Kandidatenseite | 404 Veranstaltungen: **95 gefunden**, 3 abgelehnt, 267 unklar, 32 `link_ok` |
| `pruefen --bericht` | ruft die EIGENEN Veranstalterseiten ab (tot? nennt den Lauf?) | 1.247 Seiten, 1.110 in Ordnung, **4 Adressen korrigiert** |
| `verifizieren --kandidaten <json> --bericht` | prüft Adressen aus einer **Websuche** (Handarbeit) mit derselben Regel | 122 Veranstaltungen: **88 gefunden**, 34 unklar |
| `anwenden --bericht [--auch-geprueft]` | schreibt Overrides (`veranstalter_url` + `_note`) und `links_geprueft.json` | – |

Zusammen mit dem achten Durchgang fallen die Portalzeilen damit von
847 auf **555** (695 vor der Websuche). Was übrig ist, sind fast nur
noch Veranstaltungen, die **wirklich keine eigene Seite haben**:
private Ultra-Serien mit raceresult als einziger Adresse (Uwe Laig
rund um Ibbenbüren/Osnabrück – Dörenther Klippen, Silbersee-Hüggel,
Wassermühlen, Gut Sutthausen, Sloopsteener, Mühlenweg, Holter Wald,
Mops-Ultra …; die Bremer Marathons von Bergmarathon bis Zeitsprung;
Fun & Erlebnis Marathons; SOBVL und „Wir wollen doch nur laufen" in
Berlin; Speck-weg-Serie; Northeimer Heiligabend-/Neujahrsmarathon),
dazu Vereine, deren Seite den Lauf nicht nennt (`unklar`).

Sechs Lektionen aus dem Bau, alle im Code festgehalten:

1. **Ortsnamen zählen nur im Hostnamen.** Die erste Fassung nahm
   „Cross", „Martin" oder den Ort als Beleg – und fand damit die
   Stadtverwaltung, den Sportladen und den Ergebnisdienst. Jetzt:
   Namenswörter ab fünf Buchstaben außerhalb der `ALLGEMEIN`-Liste,
   der Ort nur, wenn er im Hostnamen steckt (`tsg-giengen.de`).
   **Aber**: Der Ort im Hostnamen ist auch die Stadt-Homepage –
   `niedenstein.de` nennt den Panoramalauf im Namen, Veranstalter ist
   die SG Chattengau. Eine Kandidatenadresse aus der Websuche muss
   deshalb schon die des VERANSTALTERS sein; die Regel prüft nur, ob
   die Seite den Lauf nennt, nicht, wem sie gehört. Und **Umlaute im
   Host**: „Dülmen" heißt `tsg-duelmen.de` – `host_woerter()` prüft
   seit dem 19.09.2026 beide Schreibweisen (sieben Treffer mehr;
   `test_veranstalter_links` hält es fest).
2. **Ergebnisdienste und Karten sind keine Veranstalter**
   (`KEIN_VERANSTALTER`: live-results.de, ddmess.de, sportstiming,
   maximalpuls.com, yumpu, stay22 …; `KEIN_VERANSTALTER_PFAD`:
   Datenschutz/Impressum/AGB/Cookie-Seiten). **Ausnahme von Hand**:
   `leipzigrun.maximalpuls.com` IST die Veranstaltungsseite – die
   maximalPULS GmbH veranstaltet den Leipzig Run selbst. Steht als
   Override mit Begründung, nicht als Regel.
3. **Ein tröpfelnder Server hängt das Skript 20 Minuten.** Der
   `Abrufer` liest gestreamt mit 30-s-Frist und 2-MB-Grenze, hält 2 s
   Pause je Host, respektiert robots.txt, und `--fortsetzen` führt
   einen Bericht weiter. `ironman.com` steht in `NIE_ABRUFEN`.
4. **Die Websuche ist Handarbeit, die Prüfung nicht.** Eine
   gefundene Adresse landet nie direkt in den Daten; `verifizieren`
   ruft sie ab und lässt dieselbe Regel entscheiden. 41 von 122
   Kandidaten fielen zunächst durch – meist Vereinsseiten, die den
   Lauf nur in einem Menüpunkt oder als Bild führen (SG Bad Schönborn,
   TSV Hasede, HSG Uni Greifswald), oder tote Unterseiten (404);
   sieben davon holte ein zweiter Anlauf mit der Startseite bzw. der
   Umlaut-Schreibweise des Hosts. Die Adresse steht
   dann in der `unklar`-Notiz, für einen zweiten Blick.
5. **Das Budget für Websuchen ist endlich** (200 je Sitzung). 122 der
   309 offenen Fälle waren damit drin. Für die Fortsetzung: `python3
   scripts/veranstalter_links.py sammeln` erneut laufen lassen, dann nur
   die `unklar`-Fälle ohne Notiz „Websuche" suchen. Serien (siehe
   oben) lohnen die Suche nicht.
6. **`anwenden` braucht `--auch-geprueft`, wenn `sammeln` dieselben
   Schlüssel schon als `unklar` eingetragen hat** – sonst werden 0
   Overrides geschrieben, ohne Fehlermeldung. Die Notiz sagt dann
   „per Websuche gefunden (nicht auf der Portalseite verlinkt)".

Nebenbefunde (alle in `geprueft.json`): **Österberg 333** ist ein
Bergsprint über 333 m (Länge 0,3 km eingetragen, fällt über Datenregel 5
heraus), **Klaar Kiming Throwdown** ein CrossFit-Wettkampf (`exclude`,
dieselbe Klasse wie HYROX), der **13. Alstätter Sandhasenlauf 2030**
eine DLV-Serienprognose drei Jahre voraus mit toter Quellseite
(`exclude`). Offen als `unklar`: Silvesterlauf Amberg steht bei uns
in Kallmünz, Kalender nennen den Marktplatz Amberg (25 km); Hainberglauf
laut Kalendern 4,8 statt 5 km (Veranstalterseite 503); **Runworx**
(5-km-Hindernislauf plus Kraft-WOD) gehört wahrscheinlich in die
HYROX-Klasse – Punkt 14. Und ein neues Meisterschaft-im-Rahmen-Paar:
„Rennbahncross in Herxheim" und „Rennbahncross mit
rheinland-pfälzischen Crosslaufmeisterschaften" (15.11.2026, dieselbe
Seite) – Punkt 12.

### Zehnter Durchgang: die Websuche fortgesetzt (20.09.2026)

Auf Wunsch des Nutzers („noch einmal so viele Quellen googeln … und die
neue URL hinzufügen“). Von den 224 Portallink-Veranstaltungen ohne
Websuche blieben nach Abzug der privaten Ultra-Serien und der im vierten
Durchgang schon gesuchten Fälle **161**; dafür rund 120 Websuchen, die
Kandidaten über `verifizieren` geprüft, mit `anwenden --auch-geprueft`
übernommen. Ergebnis: **88 Veranstaltungen** haben jetzt ihre
Veranstalterseite (81 über die Regel, 7 von Hand belegt), die
Portalzeilen fallen von 555 auf **394**. Vier Dinge, die dabei
herauskamen:

1. **Ein allgemeiner Override war unsichtbar, sobald eine Strecke einen
   distanzgenauen hatte.** `find_override()` nahm den ERSTEN Treffer
   und hörte auf – ein `veranstalter_url` unter „Taubertal 100|2026-10-03“
   griff für die 161-km-Zeile nie, weil sie „…|161“ (Wettbewerbs-Label)
   hatte. Sechs Links aus der Linkprüfung vom Vortag standen deshalb
   wirkungslos in der Datei (Taubertal 100, Mössinger Apfellauf,
   Freundschaftslauf Wustweiler, Steverlauf ×2, Marner Kohltagelauf).
   Jetzt legt `find_override()` beide Einträge übereinander, der
   distanzgenaue gewinnt bei Widerspruch; `test_override_schluessel`
   hält es fest. **Ein Override, der nichts tut, fällt niemandem auf** –
   dieselbe Klasse wie der `|21.0`-Schlüssel.
2. **Umlaut-Domains stehen als Punycode in der Adresse.**
   `tus-mörschied.de` ist `xn--tus-mrschied-8ib.de`, und darin steckt
   kein „mörschied“ – `host_von()` dekodiert jetzt (`idna`).
3. **Der Ort im Hostnamen zählte entgegen der Doku gar nicht.** Die
   Regel prüfte nur Namenswörter gegen den Host; `djk-herzogenrath.de`
   für den „46. Internationaler Halbmarathon, 56. Internationaler
   Volkslauf“ (lauter Allgemeinwörter) fiel durch. Jetzt gilt der Ort
   im Host **nur bei `verifizieren`** (`ort_im_host=True`) – dort sind
   die Kandidaten handverlesen. Bei `sammeln` bleibt es aus: Dort ist
   jeder externe Link der Portalseite Kandidat, und `herzogenrath.de`
   wäre die Stadtverwaltung.
4. **Bot-Sperren sind kein Nein.** `seelauf-teisendorf.de` (403) und
   die Jimdo-Seite des Endurance Team Pirmasens (Ruppertslauf) lassen
   sich aus der Sandbox nicht lesen; die Domain nennt den Lauf, die
   Websuche belegt den Veranstalter – als Override mit Begründung
   eingetragen, wie im vierten Durchgang. Ebenso von Hand: LSV Porz
   (Seite sagt „Winterlaufserie“, laufen.de „Winterserie“, und „Porz“
   hat vier Buchstaben), Firmenlauf Lörrach (Ort nur im Text) und der
   Robert-Hannemann-Lauf (am 19.09. als „korrigiert“ protokolliert,
   Override vergessen).

Was ohne eigene Seite bleibt (`unklar` mit Notiz „Websuche“): Vereine
ohne Netzauftritt (SFG Nellschütz, TV Langen, SV Broggingen, TuS
Dallmin, SC Freital …), Veranstaltungen nur auf raceresult (Nebelseelauf,
Treßsee Marathon, Mauritz-Lindenweg-Marathon, Rund um Detmold) und
Seiten, die den Lauf nicht nennen (tvelm.de, lcfru.de, hs-wismar.de nach
404 der Unterseite). Neu für den Nutzer (siehe „Was der Nutzer noch
entscheiden muss“, Punkt 17): ein Duplikat unter zwei Namen (FT Jahn
Nikolauslauf = Nikolauslauf Landsberg a. Lech, 06.12.2026), drei
Formate der HYROX-/Treppenlauf-Klasse und ein Ortsfehler (Rheine).

### Elfter Durchgang: Abgleich mit den Veranstalterseiten (21.09.2026)

Auf Wunsch des Nutzers („alle Einträge checken, ob es noch Fehler gibt,
bis die Nutzung aufgebraucht ist – alles so seriös wie irgendwie möglich,
ich checke es dann händisch danach"). Statt der nächsten 200 nach Datum
wurde **jede Veranstaltung mit eigener Veranstalterseite** maschinell
gegen den Seitentext gehalten: `scripts/seitenabgleich.py` ruft die
1.849 Seiten ab (~65 Minuten) und meldet, ob unser Datum und unsere
Distanzen im Text stehen. Ergebnis des Laufs: 1.154 ohne Befund, 348
DISTANZ, 287 DATUM, 58 LEER, 64 FEHLER. Die gemeldeten Fälle wurden dann
einzeln angesehen (Seite und Unterseiten „Strecken"/„Ausschreibung",
notfalls das PDF), Korrekturen als Override bzw. in `manual_events.json`.

Stand danach (Protokoll `geprueft.json`, 534 Einträge vom 21.09.2026):
**202 quelle_ok, 151 korrigiert, 180 unklar, 1 entfernt**; 3.761 →
3.754 Events, 1.093 Overrides, 115 nachgetragene Strecken. Die
Fehlerklassen, grob gezählt:

1. **Mehrsport-Veranstaltungen als Lauf mit der RADSTRECKE als Länge** –
   die größte Klasse und genau der Bestand, den Datenregel 15 nicht
   heilt: O-SEE Challenge/XTERRA (vier Zeilen, „37 km" war das MTB),
   Trinale, ksp MöWathlon, ÖTILLÖ Rügen, NordseeMan, Mountain
   Challenge, Berliner Volkstriathlon, Swim & Run Köln/Werdersee/
   Winnweiler/Darmstadt, Jag de Wuidsau. Jetzt Triathlon mit der Summe
   der Teilstrecken; reine Etappen (Laufetappe des MöWathlon, die
   Einzeletappen des Berchtesgaden Stage Run) ausgeschlossen.
2. **Doppelte Terminsätze** – die Kalenderprognose UND der echte Termin
   standen beide in der Liste: Marburger Lahntallauf (27.02./06.03.),
   Rostocker Citylauf (23.05./30.05.), Klausdorfer Nikolauslauf (unter
   zweitem Namen), Mitteldeutscher Marathon. Der falsche Satz per
   `exclude`.
3. **Ungenaue Distanzen** (~50 Zeilen): Rundenvielfache (Bramfelder
   Winterlaufserie 4,66 km, Winterloop 7,5 km), Marathon-Bruchteile
   (Berliner Nikolauslauf: Achtel/Viertel/Drittel/Big 5; Bremerhaven
   3/4; Regensburg), Marketingzahlen – „5 km" mit 4,5–4,9 km beim
   Kerner Nachtlauf, Stimberg-Haardlauf, Geilenkirchen, Burgkirchen,
   Oktoberlauf Petershagen, Belgenbachtrail, Col d'Allrath (2,5 km
   bergauf) – sie fallen über Datenregel 5 heraus; und Walking-Zeilen,
   die als Lauf standen (Saaletal Marathon, Citylauf Telgte, Neiße
   Adventure Race).
4. **Zeitrennen als Distanz**: SV Schwindegg Ultralauf ist die Deutsche
   Meisterschaft im 6-Stunden-Lauf (stand als Marathon + 50 km), 6h
   Adventslauf Langenhagen (Marathon + 46 km waren 10 und 11 Runden),
   Lauf mit Musik (30-Minuten-Lauf) – Datenregel 8.
5. **Nicht im Programm**: Possenlauf MTB 28/42 km, Berlin City Night
   „20 km" (der Doppelstart Skaten + Laufen), KäseKross 9 km, Frickinger
   MTB (2026 ausgesetzt), Winterloop 8 km, Kinderrennen (O-SEE X'Kids) –
   und der **Internationale Kammlauf Klingenthal ist Skilanglauf**
   (klassisch/Freestyle), vier Zeilen entfernt.
6. **Termine**: Winterlaufserie München (Nikolauslauf 15 statt 10 km),
   Grüngürtel Ultra (Terminänderung auf der Seite), Frühlingsultra,
   Ingelheimer Halbe, Apfelblütenlauf, Schluchseelauf (Hauptlauf am
   Sonntag), Landkreislauf Schwandorf (Nachholtermin nach Hitzeabsage –
   unser Datum war richtig), Enddaten mehrtägiger Trails (Yeti,
   Frostwiese, 3Kings3Hills, Lindwurm), Starttage je Strecke (Zugspitz
   Ultra Trail, Berchtesgaden).
7. **Orte**: Bühlauer Winterlaufserie (Dresden-Bühlau, nicht Radeberg),
   EnergieSüdwest Cup (Göcklingen bzw. Offenbach an der Queich, nicht
   Landau).
8. **Fehlende Strecken** (~35 Zeilen): Werderseelauf (fünf Strecken
   neben dem Marathon), Seligenstädter Winterlaufserie (5 km an vier
   Terminen), Alten-Busecker Winterlaufserie, Eschweiler Volkslauf,
   Hollenmarsch 21/42 km, Monschau Ultra K56, Tharandter-Wald-Lauf HM,
   Donatuslauf, Saaletal 3/4-Marathon, Bergische 5 (37-km-Etappe),
   Einetallauf 21 km, Pönitz 7,5 km, Hasenmelker 5 km, Rainbow Run 5 km,
   Schmachtendorf 5 km, Berliner Nikolauslauf HM.

Sieben Lektionen, alle im Code oder in den Notizen festgehalten:

- **Ein Label, das eine Rundenlänge oder Teilstrecke nennt, verschwindet
  oder wird gemeldet.** `drop_contradicting_wettbewerb()` liest JEDE Zahl
  vor „km" – „Marathon (6 Runden à 7,5 km)" widerspricht 45 km und wird
  gelöscht; `audit_events.py` liest die ERSTE Zahl. Deshalb steht die
  Gesamtlänge im Label und vorn: „Full Distance 49,3 km (1,5 km
  Schwimmen / 37 km MTB / 10,8 km Laufen)".
- **Ein Zeitrennen lässt sich neben einer Distanz-Zeile nicht
  nachtragen.** `is_same_event()` hält eine Zeile ohne Distanz für
  kompatibel mit jeder Distanz („unbekannt schließt nichts aus"); die
  nachgetragene 6-h-Challenge des Winterloop verschmolz mit der
  45-km-Zeile, `dauer_h` landete am Marathon. Rokathon 24 h, 24 Stunden
  van Halen, Winterloop 6/12 h stehen deshalb nur in den Notizen. Wer
  das lösen will, muss `_compatible_distance()` „Distanz gegen Dauer" als
  unvereinbar werten lassen – und vorher zählen, was das im Bestand
  anrichtet.
- **Ein Override, der Distanz oder Datum ändert, braucht den zweiten
  Schlüssel** – bekannt („Die wichtigste Lektion"), hier erneut
  zugeschlagen: Die Labels für O-SEE & Co. griffen im zweiten Lauf nicht
  mehr, weil aus `|37` `|49.3` und aus dem 13.08. der 14.08. geworden
  war. Beide Schlüssel eingetragen (der alte für den frischen
  Scraper-Stand, der neue für den Bestand).
- **Allgemeiner Schlüssel plus nachgetragene Strecke** ist die
  ASV-Duisburg-Falle in neuer Form: Bei Zeilen OHNE Distanz (Hasenmelker,
  Poggenhagen) geht nur der allgemeine Schlüssel; setzt er `laenge_km`,
  trifft er beim nächsten Lauf auch die nachgetragene 5-km-Zeile,
  verschmilzt sie, und `add_manual_events()` legt sie danach wieder an.
  Idempotent, aber ein Umweg – wo es geht, distanzgenaue Schlüssel.
- **Veranstalterseiten zeigen oft noch das Vorjahr.** Fast alle 180
  `unklar` heißen „Seite zeigt 2026, 2027 nicht ausgeschrieben". Solche
  Zeilen sind Kalenderprognosen; die Zählung im Namen verrät sie
  manchmal („44. Winser Silvesterlauf" ist die Nummer von 2025, „54.
  Kißlegger" ebenso). Kein Fehler – aber nichts Belegtes. Nach dem
  nächsten Datenlauf `seitenabgleich.py` erneut laufen lassen.
- **Gekaperte Domains bestehen die Namensprüfung.** harzlauf-thale.de
  (Lotterie-Spam) und tus-kaisersesch.de (Shop) trugen den Lauf im
  Hostnamen; erst das Zählen von Laufvokabular im Seitentext
  (`hostcheck`, Wegwerf-Skript) fand sie. Idee für `pruefen`.
- **sportprogramme.org und baer-service.de** sind Anmelde-/Zeitnahme-
  portale (Oberpfalz bzw. Sachsen) → `PORTAL_DOMAINS`.

Was der Nutzer daraus entscheiden muss, steht unter Punkt 18.

### Zwölfter Durchgang: alle Triathlons (21.09.2026)

Auf Wunsch des Nutzers („Bitte noch einmal alle Triathlons checken und
die Länge dann ausfüllen"; Anlass: der Munich Triathlon stand ohne
Länge, gehört „Sprint & Kurzdistanz" – mit den sechs Formaten vom
selben Tag heißt das „Sprint & Olympisch"). Stand vorher: 149 Triathlon-
Zeilen in 103 Veranstaltungen, **43 Veranstaltungen ohne jede Länge** –
alle aus dem running.life-Triathlon-Kalender, dessen Detailseiten keine
Wettbewerbe liefern. Jede der 43 an der Veranstalterseite gelesen
(Wegwerf-Skript mit `veranstalter_links.Abrufer` über Start- und
Unterseiten „Strecken/Ausschreibung", dann von Hand; wo die Seite nur
ein PDF oder Bilder hat, der **DTU-Veranstaltungskalender**
`triathlondeutschland.de/…/veranstaltungskalender/` – er nennt je
Wettbewerb Schwimmen/Rad/Laufen und ist damit die beste zweite Quelle).
Ergebnis: **41 Veranstaltungen mit 98 Strecken** (41 Overrides an der
vorhandenen Zeile, 57 neue Zeilen in `manual_events.json`), 2 `unklar`
(Indoor-Triathlon Aschersleben und 1. Friedberger Triathlon – 2027 noch
nicht ausgeschrieben). Dazu die Gegenprüfung der 50 Triathlon-Zeilen
unter 20 km: **Teilstrecken** bei Ironman Hamburg (3,8 km Schwimmen),
Aluman, Dirty Race, Stralsund, Jedermanntriathlon Neustrelitz, Wanzleben,
Berlin Triathlon (5/9/19 km = drei Laufstrecken) und triathlon.de CUP
München (10/20 km) – zusammengeführt bzw. durch die Summen ersetzt,
Kinder-/Jugendzeilen (Lipperland) und ein Duplikat (O-SEE „Family &
Kids Races") ausgeschlossen. Protokoll: 55 Einträge in `geprueft.json`.
Vier Dinge daraus:

- **Eine Triathlon-Zeile ohne Länge ist fast immer eine ganze
  Veranstaltung** – im Schnitt 2,4 Wettbewerbe (Sprint/Volks, Olympisch/
  Kurz, oft Mittel, dazu Schnupper). Dieselbe Lehre wie im siebten
  Durchgang bei den Läufen.
- **Der allgemeine Override-Schlüssel plus nachgetragene Strecken** ist
  hier 41-mal der Normalfall (die Zeile hat keine Distanz, also gibt es
  keinen distanzgenauen Schlüssel): Beim nächsten Lauf trifft der
  Override alle Zeilen der Veranstaltung, sie verschmelzen, und
  `add_manual_events()` legt die weiteren wieder an – idempotent (CI
  prüft es), aber ein Umweg (siehe Elfter Durchgang, Hasenmelker).
- **`report_triathlon_distanzen()` meldet jetzt 35 statt 31 Fälle** –
  erwartbar, weil deutsche Veranstaltungen von 25,75/51,5/113/226 km
  abweichen (Tübingen 27,4/54,2, Heilbronn 27,8/57/106,4, Bonn 84,2 km).
  Alle sind an der Ausschreibung belegt; der Bericht ist damit eher ein
  Hinweis auf Abweichler als auf Fehler.
- **Was die Sandbox nicht liest**: raceresult-Seiten (dynamisch), manche
  PDFs (Heilbronn ging über die rohen Streams), Jimdo-/Squarespace-Seiten
  nur teilweise. Für die Zukunft: `running.life` liefert bei Triathlons
  keine Wettbewerbe – jede neue Zeile dort landet ohne Länge und gehört
  in denselben Durchgang.

### Dreizehnter Durchgang: aus einer Nutzer-Meldung eine Regel machen (21.09.2026)

Der Nutzer hat an diesem Tag eine Liste von Beobachtungen geschickt und
einen Auftrag dazu, der über die einzelnen Fälle hinausgeht:

> „Es ist außerdem sehr wichtig, das du aus allen Verbesserungen die ich
> dir über die Datenqualität gebe lernst damit wir ständig die Qualität
> verbessern können und bei neuen Events nicht die gleichen Fehler
> entstehen."

**Das ist eine Arbeitsanweisung, kein Kommentar.** Sie heißt: Eine
gemeldete Zeile wird nicht als Zeile erledigt. Das Vorgehen, das sich
an diesem Durchgang bewährt hat, in vier Schritten:

1. **Den Fall an der Quelle prüfen.** Wie immer (Datenregel 2).
2. **Die KLASSE zählen, nicht den Fall.** Ein kurzes Wegwerf-Skript über
   `events.json`: Wie viele Zeilen haben denselben Fehler? Das ist der
   Schritt, der am ehesten übersprungen wird, und der mit Abstand
   wertvollste.
3. **Eine Regel bauen, wenn die Klasse größer als eins ist** – und die
   Regel wieder am Bestand nachzählen, samt Gegenproben (die Linie der
   „wichtigsten Lektion": erst zählen, was eine Änderung anrichtet).
4. **Einen Override nur, wenn die Klasse wirklich eins ist** (ein
   falscher Termin, eine falsche Distanz auf genau einer Seite).

Was das an diesem Tag gebracht hat – fünf Meldungen, vier Klassen:

| Meldung des Nutzers | Klasse | Ergebnis |
|---|---|---|
| „Xletix Challenge - Berlin ist ein Hindernis lauf" | **58 Zeilen** | Regel (Datenregel 20) |
| „Lauf für einen guten Zweck - Rastenberg ist ein Charity Event" | 1 + 43 unmarkierte | Stichwort + Umbau (Datenregel 17) |
| „2. Weinstadt Triathlon … müsste da stehen Super-Sprint" | 3 Zeilen | Regel (Datenregel 21) |
| „Winterlauf … Originalstrecke über 18 Kilometer" | 1 | Override |
| „Gaudilauf 27 und 14 – woher kommen die Informationen?" | 2 | Override + `manual_events.json` |

Die erste Zeile ist das Argument für den ganzen Abschnitt: Ein Override
hätte **1 von 58** Fällen erledigt, und die anderen 57 wären beim
nächsten Datenlauf unverändert wieder entstanden.

**Der Gaudilauf war kein Datenfehler** – die Nachfrage lohnte trotzdem.
Der DLV-Laufkalender (laufen.de) führt bei dieser Veranstaltung **jede
Distanz als eigene Veranstaltung** und schreibt die Kilometer in den
NAMEN: „Gaudilauf 27", „Gaudilauf 14". Datum, Ort, Distanzen und
Veranstalter stimmten alle (20. Gaudilauf am 04.10.2026, LWV 05 / SG
Medizin Bad Liebenwerda, 27 km ab München im Landkreis Elbe-Elster und
14 km ab Bad Liebenwerda); nur der Name verstieß gegen Datenregel 1 –
der Veranstaltungsname bleibt identisch, die Distanz steht in
`laenge_km`. Dass der Nutzer nichts fand, lag zusätzlich daran, dass
der gespeicherte Link auf die Startseite von `elsterlauf.de` zeigte, wo
der **Elsterlauf** (30.05.2027) steht – dieselbe Veranstalterseite, eine
andere Veranstaltung. Behoben über `exclude` beider Zeilen plus einen
Eintrag „Gaudilauf" mit zwei Strecken in `manual_events.json` und den
Link auf die Gaudilauf-Seite.

Drei Lehren daraus, alle allgemein:

- **Eine Distanz im NAMEN ist ein Warnzeichen.** Wo sie steht, hat eine
  Quelle eine Veranstaltung in ihre Strecken zerlegt – dann gehören die
  Zeilen zusammengeführt. Ein Override kann das nicht (der Name ist Teil
  seines Schlüssels); der Weg ist `exclude` plus `manual_events.json`,
  und der läuft in dieser Reihenfolge von selbst richtig, weil
  `add_manual_events()` nach `apply_overrides()` kommt.
- **Ein Link auf die Startseite des Veranstalters kann der falsche sein**,
  wenn derselbe Verein mehrere Veranstaltungen ausrichtet. „Die Seite
  nennt den Lauf" (die Regel aus dem neunten Durchgang) prüft nicht, ob
  sie ihn auf der verlinkten SEITE nennt.
- **Was ins Wettbewerbs-Label kommt, durchsucht die Mastersuche.** Der
  Startort der 27 km stand kurz als „27 km (Start München,
  Elsterbrücke)" im Label – und damit fand eine Ortssuche nach „München"
  eine Veranstaltung in Bad Liebenwerda. Der Rauchtest hat es gemeldet.
  Ein Startort ist kein Ort im Sinne der Liste.

### Vierzehnter Durchgang: Zeilen ohne Maßzahl, zweite Runde (21.09.2026, ohne den Nutzer)

Der Nutzer war einige Stunden weg („möchte aber das du weiter an der
Webseite baust") – gearbeitet wurde deshalb nur, was in diesem Dokument
als „nur Arbeit, keine Entscheidung" steht, und alles Neue, das eine
Entscheidung braucht, steht unten in der Liste. Erledigt in dieser
Reihenfolge: Zeitrennen neben Distanz-Zeilen (Datenregel 8), Duplikate
unter zwei Namen (offene Punkte, Nr. 19), Ladezustand der Liste
(Frontend-Fallen), dann die **96 ungeprüften Zeilen ohne Distanz und
ohne Dauer** an ihren Veranstalterseiten (Protokoll `geprueft.json`,
`am` = 2026-09-21).

Bilanz der 96, ehrlich gerechnet: **17 bekamen eine Maßzahl** (davon
sechs Veranstaltungen mit nachgetragenen weiteren Strecken – Leipziger
Frauenlauf, Nürnberger Winterlaufserie mit drei Terminen, Paul-Ultralauf
50/100/150 Meilen, Ruhr Trail Run, Besenbinderlauf, Schwelmer Citylauf),
**vier wurden Zeitrennen** (Klosterparklauf Harsefeld 6 h, Sommer24hLauf
24/48 h, Sixdaysrun 144 h), **zwei wurden Triathlons** (HavelMan,
neuseenMAN – beide noch ohne Kilometer), **elf flogen** (siehe unten),
**23 Wings-for-Life-Standorte** sind belegt ohne Distanz und tragen jetzt
`charity` per Override, der Rest ist `unklar` – fast immer „2027 noch
nicht ausgeschrieben" oder „Strecken nur als PDF/auf raceresult".

Drei Klassen, die dabei sichtbar wurden (alle nach Punkt 2 des
Dreizehnten Durchgangs gezählt, nicht einzeln behandelt):

1. **Hybrid-Fitness-Formate unter neuen Marken.** THE ROX (Wildau),
   Deadly Dozen („Deadly Sprint", „Deadly Gross": 12 Stunden lang je
   Stunde 400 m plus zwölf Kraftübungen) und ATHX Games (vier Termine:
   Strength Zone, MetCon X, Messehalle) – dieselbe Klasse wie HYROX
   (Datenregel 14). Alle **per Override** ausgeschlossen, nicht über
   `NICHT_AUSDAUER`: Eine Zeile dort braucht das Ja des Nutzers (so am
   Runworx gelernt). Kandidaten für die Liste: `the rox`, `deadly
   dozen|deadly sprint|deadly gross`, `athx`.
2. **Staffeln ohne Staffel-Wort im Namen.** „Landkreislauf" heißt in
   Amberg-Sulzbach (11 Läufer je Team) und Günzburg (Staffellauf, jedes
   Jahr andere Strecke) eine reine Staffel – `ist_staffel()` sieht das
   nicht. Beide per Override (Datenregel 16). Beim nächsten Datenlauf
   lohnt ein Blick auf jeden weiteren „Landkreislauf".
3. **Paarläufe** (Paarlauf mit Musik des SCC, Holger Anders
   Flutlicht-Paarlauf, Paarlauf des ABC-Zentrum: zwei Läufer wechseln
   sich über 30 bzw. 60 Minuten ab) sind Zweier-Teams – ob sie unter die
   Staffel-Regel fallen, ist nicht entschieden (Frage unten).

Nebenbefunde: `_same_name()` hält „5 km Walking" und „5 km Lauf" für
dieselbe Zeile (die kürzere Wortmenge steckt in der längeren), ein
Walking-Nachtrag neben dem Lauf derselben Länge geht also nicht – und
`test_manuelle_events` merkt es sofort (zwei Einträge weniger als
erwartet). Eine Laufserie hängt in den Quellen jede Distanz an jeden
Termin (Nürnberger Winterlaufserie: 5 km am 17.01., den es nicht gibt –
Dritter Durchgang, Muster 3, erneut). Ein Sponsorwechsel wechselt die
Domain (`brooks-ruhr-trail-run.de` → `altra-ruhr-trail-run.de`, per
302). Und `firmenlauf-oberschwaben.de` ist ein Hosting-Platzhalter – ob
es die Veranstaltung 2027 gibt, weiß niemand.

### Fünfzehnter Durchgang: die Websuche zu Ende geführt (21.09.2026, ohne den Nutzer)

Alle Portallink-Veranstaltungen, die noch keine Websuche hatten (nach
dem Zehnten Durchgang 224, davon ~100 als private Serien übersprungen),
in vier weiteren Runden gesucht, mit `verifizieren` geprüft und mit
`anwenden --auch-geprueft` übernommen (Commits „fünfte" bis „achte
Runde"). **Die Portalzeilen fallen von 394 auf 239.** Was übrig ist,
steht jetzt vollständig als `unklar` mit Notiz „Websuche" in
`links_geprueft.json` – die Filterung `quelle == "Websuche"` liefert
also keine Kandidaten mehr; die nächste Linkarbeit beginnt erst nach
dem nächsten Datenlauf. Drei Dinge daraus:

1. **Die „privaten Ultra-Serien" hatten doch eine Seite.** Uwe Laigs
   Läufe rund um Osnabrück, Ibbenbüren und Bielefeld (Gut Sutthausen,
   Dörenther Klippen, Silbersee-Hüggel, Wassermühlen, Sloopsteene,
   Kletterfelsen, Lengerich, Eversburg, Tatenhausen, Werther, Hohe Ward,
   Langenberg, Dyckerhoff, Oerlinghausen, Detmold, Holter Wald, Mops –
   19 Zeilen) stehen mit Termin auf **„Uwes Laufangebote"**
   (`ultra-uwe-unterwegs.de/veranstaltungen/uwes-laufangebote/`), der
   Terminseite des Veranstalters. Gefunden über die Websuche nach dem
   Dyckerhoff Steinbruch Marathon – der Neunte Durchgang hatte die Serie
   als „nur raceresult, keine Websuche wert" abgehakt. **Eine Serie
   lohnt EINE Suche**: Findet sie die Seite des Veranstalters, gilt sie
   für alle seine Läufe. Die übrigen Serien (Fun & Erlebnis Marathons
   Hamburg, Bremer Marathons, SOBVL, „Wir wollen doch nur laufen",
   Speck-weg, Northeim, Witzenhausen) haben wirklich keine – je einmal
   gesucht, Kontaktseiten gelesen, als `unklar` protokolliert.
2. **Kurze Namen und Allgemeinwörter sieht die Regel nicht.** „OTB
   Silvesterlauf" (drei Buchstaben plus Allgemeinwort), „Rund um
   Detmold" (der Ort steht auf der Seite als eigene Zeile), „Sloopsteener
   Seenrunden" (die Seite schreibt „Sloopsteene") und der Borna Half
   (Seite ohne JavaScript leer) sind von Hand belegt – Override mit
   Begründung, wie im Zehnten Durchgang. Vier von 60, der Rest über die
   Regel.
3. **Nebenbefund**: „Cross im Grund" (Erfurt) ist laut Veranstalter
   (OCR-Squad) ein 13-km-Lauf mit rund 30 Hindernissen – Kategorie
   Hindernis statt Trail, per Override.
4. **Nach jeder Linkrunde `seitenabgleich.py` über die neuen Seiten**
   (über einen vorbesetzten Bericht mit `--fortsetzen`, ~2 s je Seite –
   die 74 Seiten des Tages in 90 s). Das fand vier Datenfehler
   (Frauenlauf Bremen 8,5 statt 10 km, Ratzeburger Adventslauf 7,5 km
   statt 7,3 und 8, Remseck 8 statt 7,5 km, Burgdorf ohne 11 km), den
   Double Ultra Triathlon Lensahn (452 km, fehlte), acht 2027-Prognosen
   (Datenregel 19) – und **zwei falsche Links der Regel**: Der Ort im
   Hostnamen (`ort_im_host`) hat bei `falkensteinlauf.de` einen anderen
   Falkenstein-Lauf und bei `tsg-leutkirch.de/…/volkslauf/` den
   Juli-Volkslauf statt der Stadtmeisterschaft belegt. Beide zurück auf
   raceresult – **direkt in `events.json`**: Ein gelöschter Override
   nimmt nichts zurück, und ein Override darf keinen Portallink über
   einen Veranstalter-Link setzen (`apply_overrides()` blockt das).
   Der Ort im Host ist ein Beleg für den VEREIN, nicht für den Lauf;
   bei Vereinen mit mehreren Läufen die Unterseite prüfen.

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

- **Weniger anzeigen ist eine Datenqualitäts-Entscheidung.** Der Nutzer
  hat das am 21.09.2026 in einem Satz begründet, der für die ganze Seite
  gilt: „Wir wollen nicht zu viele Infos zeigen, weil das erhöht die
  chance, dass sie Infos auch falsch sind." Daraus drei Änderungen, die
  **nicht** zurückgedreht werden sollen:
  - **Das Feld „Strecke" in der Detail-Box zeigt nur die Länge** –
    „5,6km", nicht „5,6 km · 5.555 m (Berglauf auf den Lousberg)". Das
    Wettbewerbs-Label ist die unzuverlässigste Angabe im Datensatz (es
    kommt wörtlich aus dem Kalendereintrag) und wiederholte dort meist
    ohnehin die Distanz. Bei einem Triathlon ist „die Länge" das FORMAT
    („Super-Sprint"), ohne den Zusatz des Labels.
  - **Unter dem Namen steht keine Maßzahl mehr.**
    `EED.displayWettbewerb()` schneidet jede Maßzahl aus dem Label
    (km, m, hm, Stunden, Minuten, auch „2x5 km" und „400-m-Runde") und
    gibt null zurück, wenn nichts Eigenes übrig bleibt. Begründung des
    Nutzers: „Wir haben die Länge in der Liste schon und in der
    Detailansicht dann auch. Man muss es nicht 3x sehen. Wenn ein Event
    zum Beispiel ein Geh event ist, dann kann man da schon ‚Walking'
    oder so hinschreiben … Aber keine Informationen die bereits genannt
    wurden." Aus „Brian Trail (15,5 km, 500 hm)" wird „Brian Trail", aus
    „5.555 m (Berglauf auf den Lousberg)" „Berglauf auf den Lousberg",
    aus „10 km Fuchsburg Lauf (ab Jahrgang 2015)" „Fuchsburg Lauf (ab
    Jahrgang 2015)". Zwei Feinheiten, beide nötig: Eine **Klammer mit
    Maßzahl fliegt GANZ** (sonst bliebe „( Schwimmen / Rad / Laufen)"
    stehen), eine Klammer OHNE Maßzahl bleibt (das ist genau die Art
    Zusatz, die gemeint ist); und eine Klammer, die danach den ganzen
    Rest ausmacht, verliert sie. Nach dem Kürzen tragen von 3.877 Zeilen
    noch 1.312 einen Zusatz.
    **Der Rückfall auf die Länge im aufgeklappten Block ist weg** – er
    stand dort, damit sich die Strecken einer Veranstaltung im Namen
    unterscheiden; die Längen-Spalte in derselben Zeile tut das bereits.
  - **Das Wettbewerbs-Feld in `events.json` bleibt unangetastet.** Die
    Duplikat-Erkennung der Scraper braucht den vollen Text, und die
    Strecken-Pille zeigt ihn als Tooltip. Gekürzt wird nur die ANZEIGE.

- **Maßzahlen ohne Leerzeichen: „16km", „6h".** Vom Nutzer am 21.09.2026
  so gewünscht. Es gilt für die Maßzahl eines Events (`EF.formatKm`,
  `EF.formatHours`, `EF.formatDistanceKm`, `EED.formatLengthSpan`) –
  also Länge-Spalte, Spanne einer Veranstaltung, Strecken-Pillen,
  Entfernung und Detail-Box. **Nicht** betroffen sind Sätze, in denen
  eine Zahl vorkommt („Umkreis: 25 km", „Länge ab 10 km", „bis 50 km" im
  Filter): Dort ist die Einheit ein Wort im Satz, kein Etikett an einer
  Zahl.

- **Das Sternchen erklärt sich selbst.** Die Fußnote zu „Juni 2027*"
  stand von Anfang an in der Fußzeile – der Nutzer hat sie am 21.09.2026
  trotzdem nicht gefunden („finde ich als user nirgendwo was genau das
  ‚*' bedeutet"), und zu Recht: klein, grau, am Seitenende, auf dem
  Handy hinter vierhundert Zeilen. Das Zeichen selbst ist jetzt ein
  `<abbr class="vorlaeufig-stern">` mit Erklärung im `title`, gepunktet
  unterstrichen und in der Signalfarbe (`EED.vorlaeufigStern`, gilt für
  Liste UND Karte). Die Fußzeile behält den Text – ein `title` erscheint
  auf einem Touchgerät nicht –, jetzt mit 78 % statt 60 % Deckung, und
  er steht als `datum_fussnote` nur noch EINMAL in `event-detail.js`
  statt in beiden Seiten.
  **Die allgemeine Lehre**: Eine Erklärung gehört an die Stelle, an der
  die Frage entsteht, nicht dorthin, wo Platz ist.

- **Die Detail-Box hat auch in der Liste ein ✕.** Die Karte hatte es von
  Anfang an, die Liste nicht (`onClose` war optional und wurde dort nicht
  übergeben) – bis der Nutzer es am 21.09.2026 auch hier wollte. Drei
  Dinge gehören dazu, sonst schließt sich nur die Hälfte: die Markierung
  in der Tabelle (`selectedIndex = null` plus `markiereAuswahl`), der
  Parameter `?event=` in der Adresse (`writeUrlState`), und der **Fokus**
  – er steht im ✕, und das verschwindet gerade; ohne Zurücksetzen landet
  er am `<body>`, und wer mit der Tastatur arbeitet, beginnt wieder ganz
  oben. Er geht an die Zeile, die eben gewählt war.

- **`.sr-only` gehört nicht in die Tabelle.** Das Charity-Herz trug
  zuerst eine `.sr-only`-Beschriftung; die ist `position: absolute`, und
  ein absolut positioniertes Element bezieht sich auf den nächsten
  POSITIONIERTEN Vorfahren – `overflow-x: auto` an `.table-wrap` ist
  keiner. Die Beschriftungen landeten damit am Dokument, an der x-Stelle
  ihrer Zelle in der 900 px breiten Tabelle, und zogen die ganze SEITE
  124 px in die Breite: Auf dem Handy scrollte danach alles waagerecht,
  und der sticky „Weitere 200 anzeigen"-Knopf war nicht mehr klickbar.
  Für eine Beschriftung in einer Tabellenzelle also `role="img"` +
  `aria-label` am Element selbst. **Der Rauchtest hat genau das
  gemeldet** („kein waagerechter Überlauf der Seite (124 px)") – die
  Prüfung ist keine Formalie.

- **Die Startseite zählt die Events je Sportart** (vom Nutzer am
  21.09.2026 gewünscht). Gezählt wird nach `EF.dropPastEvents()`, also
  mit derselben Grenze, die `events.html` beim Laden zieht – sonst
  verspräche die Startseite Events, die einen Klick später nicht mehr da
  sind. Dafür lädt `index.html` seit dem Tag **`filters.js`** (mit
  `defer`): Die zwei Helfer nachzubauen wäre eine zweite Kopie, die beim
  nächsten Umbau ausschert, und die Datei braucht `events.html` – das
  die Startseite ohnehin per `prefetch` vorlädt – danach sowieso, der
  Abruf wärmt also den Cache. Die Zahlen sind `hidden`, bis der Abruf
  zurück ist: Eine „0" oder ein Platzhalter, der später springt, wäre
  schlechter als eine Kachel ohne Zahl, und schlägt der Abruf fehl,
  bleibt die Seite wie vorher. Sie tragen kein `data-i` (ihr Text kommt
  aus den Daten), müssen aber in `applyLang()` mitgezeichnet werden –
  das Tausendertrennzeichen hängt am Umschalter DE/EN.
  **Sie machen die Datenlücke sichtbar**: 3.667 Laufen, 201 Triathlon,
  5 Schwimmen, 4 Fahrrad. Das ist Fahrplan-Punkt 1.

- **Der Style Guide des Nutzers gilt („Design-System v1", Richtung
  „Morgenstart", 21.09.2026: „Bitte an den Style Guide halten").** Er
  steht als Bild im Chat und hier in Zahlen; wer eine Farbe, Schrift oder
  einen Radius ändert, ändert den Guide – also vorher fragen.
  - **Farben** (`site.css`, helles Schema = der Guide): Nacht `#0B1B33`
    (Marke, Kopf der Startseite, Fußzeile, Primär-Buttons, gewählte
    Filter), Tiefe `#163B6B` (Hover, Illustration, Links), Signal
    `#E8590C` (Marke, Sportfarbe Laufen, Akzente – **nie als Fläche
    unter weißem Text**), Sonne `#F97316` (**nur** der Hero-CTA, mit
    Navy-Text, und die Sonne der Illustration), Kreide `#F4F2ED`
    (Seitenhintergrund, warm statt Grau), Weiß (Karten, Tabelle, Panels),
    Linie `#E2DED5`, Tinte `#0F1B20` (Text), Grau `#66707F`
    (Beschriftungen), Ton `#EDF1F7` (gewählte Zeile, aufgeklappter Block,
    Icon-Flächen). **Sportfarben** als zweite Ebene für Icons, Marker und
    Tags – nie als Textfarbe auf Weiß, dafür je eine Tonfläche und eine
    dunklere Textfarbe darauf: Laufen `#E8590C`/`#FFF1E8`/`#9A3B05`,
    Fahrrad `#2B8A3E`/`#E9F7EC`/`#1B5E2B`, Schwimmen
    `#1971C2`/`#E7F1FC`/`#0F4C86`, Triathlon `#7048E8`/`#F1ECFF`/`#482FA6`
    (`--sport-<art>`, `-bg`, `-fg`). Der **Dunkelmodus** ist die
    Dunkelmodus-Zeile des Guides: Navy wird zur Fläche (Grund `#0B1B33`,
    Fläche `#13233D`, Linie `#2A3A56`, Ton `#1C2C48`, Text `#EDF1F7`),
    Signal bleibt Signal, die Sportfarben sind aufgehellt.
  - **Schrift**: Barlow Condensed für alles Große (Überschriften, Datum,
    Distanzen, Zahlen – `--font-display`), Barlow für Text und
    Bedienelemente (`--font-text`). Größen: Display 88 px/700 (Hero),
    H1 56/700, H2 44/600, H3 24/600 (Kartentitel, `.detail-panel h2`),
    Zahl/Datum 30/700 (`.result-count`, `.detail-date`), Lead 20/400,
    Fließtext 16/400, Bedienelemente/Tabelle 14/500, Beschriftung 12/600
    versal. **Selbst gehostet** (`vendor/fonts/barlow.css`, woff2 mit
    unicode-range latin/latin-ext) – kein Google-Server, dieselbe Linie
    wie bei Leaflet und Firebase.
  - **Komponenten**: Radius **10 px** für Bedienelemente
    (`--radius-ctl`), 14–16 px für Karten und Panels; Klickflächen
    mindestens 40 px (Kopfzeile 44). Primär ist Navy, das Orange bleibt
    dem Hero-CTA vorbehalten. Filterpillen: leer weiß mit Linie, gewählt
    Navy mit weißer Schrift, **geöffnet weiß mit 2 px Navy-Rand**
    (`.open:not(.has-filter)`). Chips als Pillen auf Ton. Der Sport-Tag
    in der Box (`.detail-badge`) trägt Tonfläche und Textfarbe seiner
    Sportart. Icons: Konturicons mit **1,8 px** Strich, runde Enden, als
    Inline-SVG.
  - **Marke**: Navy-Kachel, weiße Route, oranger Punkt auf hellem Grund;
    auf Navy (Kopf der Startseite `.site-header--navy`, dunkles Schema)
    weiße Kachel mit Navy-Route, der Punkt bleibt orange
    (`--logo-bg/-fg/-dot`). Dasselbe Zeichen ist `favicon.svg`.
  - **Fußzeile ist Navy** in beiden Schemata (`--footer-bg`), die
    Kopfzeile der Startseite auch; Liste und Karte tragen die helle
    Kopfzeile (`--header-bg`).
  - **Bildsprache**: Illustration statt Stockfoto – der Hero der
    Startseite ist ein Inline-SVG (~4 KB): drei Bergketten in Navy-Tönen,
    Höhenlinien, die Route als helles Band mit gestrichelter Signal-Linie,
    Pins in den Sportfarben, die Sonne als Ziel; unten ausgerichtet
    (`xMidYMax slice`), der Text steht links, Sonne und Pins rechts
    davon. Fotos sind laut Guide ein optionaler zweiter Schritt (unter
    einer Navy-Fläche mit 55–65 % Deckung, selbst gehostet als WebP) –
    nicht gebaut.
  - Die beiden Textseiten (`seite.css`) tragen dieselben Farben und
    Schriften, folgen aber weiter der Systemeinstellung (kein Knopf).
  - **Die Seite nennt sich „Ausdauersport im deutschsprachigen Raum"**
    (seit Südtirol, 21.09.2026): Titel, `og:site_name` „Endurance
    Events", Beschreibungen („Deutschland, Österreich, Schweiz und
    Südtirol"), Hero-Zeile, „4 Regionen" – kein „DACH"/„D/A/CH" mehr in
    sichtbaren Texten (in Code-Kommentaren darf es stehen).

- **Das Aussehen ist seit dem 21.09.2026 die Vorlage des Nutzers** (ein
  Bild: dunkle Fläche, Marke mit orangem Zeichen, Navigation „Events /
  Karte“, Filterpillen ÜBER der Tabelle, Trefferzahl groß mit Schalter,
  Chips und „Stand“, Tabelle mit Sportart-Symbolen, Detail-Box mit
  großem Datum und Strecken-Pillen, Fußzeile „Dein Event fehlt?“ links
  und Impressum rechts). Was daran nicht zurückgedreht werden soll:
  - **`site.css` ist das gemeinsame Gerüst** (Farben, Kopf, Filterleiste,
    Werkzeugleiste, Fußzeile) für alle drei Seiten – nichts davon zurück
    in eine Seite kopieren. In `events.html` steht nur noch Tabelle,
    Detailbereich und die Dialoge, in `karte.html` nur die Karte.
  - **ZWEI Farbschemata, ein Knopf.** Die Vorlage der Liste war dunkel,
    die der Karte (am selben Tag) hell – beide gelten. Das Schema hängt
    an `data-theme` am `<html>` („dark" = die Werte in `:root`, „light"
    = der Block `:root[data-theme="light"]` in `site.css`); gesetzt wird
    es von einem **wortgleichen Skript im `<head>` aller drei Seiten**
    (gespeicherte Wahl `endurance-theme` vor der Systemeinstellung, und
    im Kopf, damit die Seite nicht erst im falschen Schema aufblitzt),
    der Knopf `.theme-btn` in der Kopfzeile schaltet um (Sonne im
    Dunkeln, Mond im Hellen). `test_farbschema_skript` vergleicht die drei
    Kopien und verbietet `prefers-color-scheme` in `site.css` – darüber
    hätte der Knopf keine Wirkung. **Feste Farben gibt es nur, wo eine
    Fläche in beiden Schemata gleich aussieht** (Leaflet-Popup, das Weiß
    in der Marker-Nadel, die Sportfarben); alles andere über die
    Variablen. Die wichtigsten: `--accent` ist die Hervorhebung (dunkel:
    HELL, hell: Marine `#0f1b33`), `--on-accent` die Schrift darauf – ein
    festes `#fff` auf einer Akzentfläche ist im Dunkeln unsichtbar;
    `--pill-active-bg/-fg/-border` für gesetzte Pillen und DE/EN (dunkel
    leise, hell Marine mit weißer Schrift); `--logo-bg/-fg/-dot` für die
    Marke (dunkel: orange Kachel, weißer Punkt; hell: Marine, oranger
    Punkt); `--shadow`; `--sport-laufen/-fahrrad/-schwimmen/-triathlon`
    (eine Farbe je Sportart – Symbole in der Tabelle, Abzeichen der Box,
    Nadeln und Legende der Karte; Laufen ist Orange = `--brand`);
    `--map-*` für die Karte. `--frame` für die Linien um einen
    aufgeklappten Block.
  - **Die Filterknöpfe sitzen nicht mehr in den Spaltenköpfen**, sondern
    als Pillen in der Filterleiste (`ui.buildButtonBar(…, { order:
    FILTER_ORDER })`, gebaut in `setLanguage`, weil sie die Spaltennamen
    tragen). **Die Pille zeigt nur den Spaltennamen** und ob sie gesetzt
    ist (gefüllte Fläche) – den WERT nennt allein die Chip-Zeile neben
    „Filter löschen“. Am 21.09.2026 stand kurz „Sportart: Laufen“ in der
    Pille (gerechnet aus den Chips); der Nutzer hat es am selben Abend
    zurückgenommen: doppelt zur Chip-Zeile, und die Leiste wurde zu lang
    („Ort & Umkreis: 25 km um Aktueller Standort“). Gilt für Liste UND
    Karte. Der Datum-Chip nennt bei einem Zeitraum-Knopf
    den ZEITRAUM („26.09.–26.12.2026“), nicht den Knopfnamen. Die Spalte
    „Name“ hat weiterhin eine Pille (ganz rechts; die Mastersuche deckt
    das meiste ab, der Rauchtest prüft das Namens-Panel dort).
  - **Die Marke führt zur Startseite** (Punkt 11 der offenen Fragen: der
    Rückweg über das Logo ist die übliche Konvention). `#page-title` ist
    der Markenname; die Notbremse („Bitte neu laden“) schreibt in
    `#page-title` und die sonst leere `.page-note` (`#subtitle`).
  - **Tabelle**: Reihenfolge Datum, Name, Sportart, Ort, Land, Kategorie,
    Länge (`TABLE_ORDER`; die Entfernung rutscht hinter den Ort); Datum
    mit Wochentag (`EF.formatDateWeekday`, in der Zelle `nowrap`);
    Sportart mit Symbol (`EED.sportIcon`, Inline-SVG – kein `<img>` je
    Zeile); im aufgeklappten Block steht unter jedem Namen IMMER der
    Wettbewerb, notfalls die Länge (`cellHtml(…, { zweiteZeile: true })`).
    Spaltenbreiten sind auf 900 px Mindestbreite gerechnet, „So
    27.09.2026“, „Deutschland“ und „Triathlon“ mit Symbol passen genau –
    wer eine Spalte schmaler macht, prüft die drei.
  - **Trefferzahl** ist nur noch die Zahl („1.889 Events“,
    `EF.formatInt`), kein „von N“ mehr; **„Stand: Mo, 21.09.2026“** kommt
    aus dem `Last-Modified` der `events.json` (GitHub Pages schickt ihn,
    der lokale Server auch); fehlt er, bleibt die Zeile verborgen.
  - **Detail-Box**: `EED.render(container, e, { …, siblings, onSelect,
    mapLink, listLink, distanceText })`. `siblings` sind die Zeilen derselben Veranstaltung (Liste:
    über `groupKey` aus ALLEN Events, nicht den gefilterten; Karte: Name +
    Datum + Ort), `onSelect(idx)` wechselt die Strecke (Liste:
    `waehleZeile` ohne Scrollen; Karte: tauscht das Event dieser Box aus),
    `mapLink` (nur Liste) ist `karte.html?s=<Name>`, `listLink` (nur
    Karte) `EED.eventLink(e)` – je Seite nur der Knopf zur ANDEREN.
    `distanceText` („14 km", `EF.formatDistanceKm`, in beiden Seiten
    dieselbe Schreibweise) ersetzt den vierten Fakt „Veranstalter" durch
    „Entfernung: 14 km von deinem Standort", sobald ein Ausgangspunkt
    gesetzt ist (Vorlage der Karte); die Veranstalterseite bleibt als
    Hauptknopf. Das Abzeichen trägt `sportClass(e.art1)` und damit die
    Farbe der Sportart. Das Kalender-Menü
    liegt absolut unter dem Knopf, die Klassen `.event-share-btn`,
    `.report-open-btn`, `.cal-open-btn`, `.cal-ics`, `.detail-close`,
    `.detail-grid dt` bleiben – der Rauchtest hängt daran.
  - **Karte**: dieselbe Kopf- und Filterleiste; die Trefferzeile
    („3.830 Events an 1.363 Orten“, `#map-hint`) steht in der
    Werkzeugleiste, nicht mehr als Kasten über der Karte; Marker orange,
    Kacheln leicht abgedunkelt; das Popup behält feste helle Farben
    (Leaflet-Popup ist immer weiß).
  - **Startseite**: dieselbe Kopfzeile über dem Hero (der `.events-btn`
    ist der Navigationslink „Events“, links von der Anmeldung), Hero
    dunkel mit orangem Schimmer, Fußzeile wie überall.

- **Die Karte ist seit dem 21.09.2026 die zweite Vorlage des Nutzers**
  („Die Map bitte so gut wie möglich in dem Format darstellen"; ein
  helles Bild – daher das zweite Farbschema, siehe oben). Was daran
  nicht zurückgedreht werden soll (alles in `karte.html`):
  - **Ein Punkt je VERANSTALTUNG, nicht je Strecke** (vom Nutzer am
    21.09.2026: „auf der Karte gibt es nur die zusammengefassten Events;
    wenn man draufklickt, sieht man, welche Distanzen möglich sind").
    `renderMarkers()` fasst die gefilterten Zeilen über `EED.groupKey`
    (Name + Starttag + Ort, klein – derselbe Schlüssel wie beim
    Zusammenfassen der Liste und bei den Strecken-Pillen der Box, seit
    dem Tag in `event-detail.js`) zu Veranstaltungen zusammen; die erste
    Zeile vertritt sie (`g.e`), die Zeilen stehen in `g.rows`. Ein Marker
    je Ort trägt die Zahl seiner Veranstaltungen (`eeCount`), die Bündel
    summieren sie, die Legende zählt sie („N Events" – dieselbe Zahl wie
    die Liste beim Zusammenfassen). Ein Ort mit EINER Veranstaltung ist
    eine Nadel, bis zwei öffnet der Klick die Boxen direkt, ab drei
    listet das Popup **je Veranstaltung einen Eintrag** mit der Spanne
    ihrer Strecken (`EED.formatLengthSpan`, dieselbe Funktion wie die
    Längen-Spalte der Liste) und „4 Strecken". Die Distanzen sieht man
    dann in der Box (Pillen). Der Rauchtest sucht dafür einen Ort mit
    genau zwei VERANSTALTUNGEN (`ort_mit_zwei_veranstaltungen()`).
  - **Flach bis Zoom 7, Kacheln ab Zoom 8** (`TILES_AB_ZOOM`,
    `aktualisiereFlach`): Die Übersicht zeigt nur die Landfläche der
    drei Länder (hell, aus `laender.json`, eigenes Pane `landPane` mit
    z-index **150 – UNTER den Kacheln** (200), `fillRule: nonzero`) auf
    grauer Fläche mit feinem Raster (CSS-Hintergrund von `#map`, wandert
    nicht mit). Die Kacheln werden **nicht abgeschaltet, sondern per CSS
    ausgeblendet** (`.map-flach .leaflet-tile-pane { visibility: hidden }`):
    So sind sie beim Hineinzoomen sofort da, und der Rauchtest kann sie
    weiter zählen (noWrap-Prüfung bei kleinstem Zoom). Die Maske (250,
    evenodd) bleibt darüber, ihre Farbe kommt jetzt aus dem Stylesheet
    (`path.maske-pfad`, ebenso `path.land-pfad`, `path.umkreis-pfad`):
    Leaflet schreibt `fill`/`stroke` als Attribut, eine CSS-Regel gewinnt
    – so folgen sie dem Farbschema.
  - **Orientierungsorte** enthalten seit dem 21.09.2026 Bozen, Meran,
    Brixen und Bruneck; die Landfläche und die Maske kommen automatisch
    aus `laender.json` (vier Schlüssel).
  - **Bündel: Kreis in der Akzentfarbe + Ortsname** des größten Ortes im
    Bündel (`options.eeStandort`, „349 Köln"). Die Zahl steht ALLEIN in
    `.cluster-badge`/`.marker-badge` – der Rauchtest addiert die Kreise
    mit `parseInt` gegen die Legende. **Ein Ort mit genau einer
    Veranstaltung ist eine Nadel** (`.marker-pin`, Farbe und Symbol der
    Sportart ihrer ersten Zeile) mit einer unsichtbaren „1"
    (`.marker-badge.sr-only`) für dieselbe Rechnung.
  - **Beschriftungen werden geordnet** (`ordneBeschriftungen`, nach
    `moveend`/`zoomend`/`animationend` in EINEM Animationsframe plus
    einem zweiten Durchgang nach 450 ms, weil markercluster die Marker
    animiert schiebt): größte Bündel zuerst; ein Name, der einen Nachbarn
    überschneidet, wandert nach links (`.label-links`), sonst
    verschwindet er (`.label-versteckt`). Dann die **Orientierungsorte**
    (`REFERENZ_ORTE`, ~37 Städte fest im Code, graue Punkte, nur in der
    flachen Ansicht, Pane 300): weg, wenn ein Bündel, ein Name oder ein
    wichtigerer Ort auf ihnen liegt, oder ein Bündel denselben Namen
    trägt. Ausgeblendet wird mit `visibility`, nicht `display` – sonst
    hätte ein Kasten keine Maße mehr und käme nie zurück.
  - **„Mein Standort"** (`StandortControl`, unter den Zoom-Knöpfen)
    öffnet das Ort-Panel an seiner Pille (`ui.open`, kein künstlicher
    Klick – der liefe bis zum Dokument und schlösse das Panel gleich
    wieder) und drückt dort `.geo-btn`: derselbe Weg wie im Panel, kein
    zweiter.
  - **Legende unten links** (`.map-legend`) mit `#map-hint` („3.830
    Events" – die Werkzeugleiste zeigt keine Trefferzahl mehr und ist
    **ohne Filter ausgeblendet**, `toolbarEl.hidden`) und den vier
    Sportfarben; Quellenangabe unten rechts ohne Leaflet-Vorspann
    (`attributionControl`, Text je Sprache). **„E-Mail-Abo"** in der
    Filterleiste führt in die Liste mit diesen Filtern und `?abos=1`.
    Der Umkreis ist gestrichelt (`dashArray`), der Ausschnitt knapp um
    die Marker (`pad(0.04)`, sonst fiel D/A/CH auf 1440×700 in Zoom 5)
    und höchstens Zoom 13 (ein einzelner Ort zoomte bis zur Hausnummer).
  - Auf der Karte gibt es KEINE festen Farben außer im Popup und im Weiß
    der Nadel – alles über `--map-*`, `--accent`, `--sport-*`.

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
- **Zusammenfassen ist die VOREINSTELLUNG** (so vom Nutzer gewünscht,
  19.09.2026): `state.gruppiert` startet mit `true`. Drei Stellen hängen
  daran, alle drei müssen zusammenpassen:
  - `localStorage` (`endurance-gruppiert`) überschreibt die
    Voreinstellung **nur, wenn ein Eintrag da ist** – also nur eine
    eigene Entscheidung. Die frühere Zeile `=== '1'` hätte einen
    fehlenden Eintrag wie „aus" behandelt und die Voreinstellung
    stillschweigend ausgehebelt.
  - `currentParams()` schreibt nur die **Abweichung** in die Adresse:
    `gruppiert=0`, wenn aus. Die Karte reicht den Wert unverändert
    zurück; ohne ihn käme der Weg Liste (aus) → Karte → Liste
    zusammengefasst zurück. Alte Links mit `gruppiert=1` bleiben gültig.
  - `readUrlState()` versteht `1` UND `0`; fehlt der Parameter, bleibt
    es bei Voreinstellung bzw. gemerkter Wahl.
  Der Rauchtest prüft den ersten Besuch in einem frischen
  Browser-Kontext (an, nichts im Speicher, nichts in der Adresse), das
  Merken nach dem Abschalten und den Rückweg von der Karte mit
  abgeschalteter Gruppierung.
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
- **Aufgeklappt bekommt die Veranstaltung einen RAHMEN**: eine Linie oben
  an der Veranstaltungszeile, eine unten an der letzten Strecke, je ein
  senkrechter Strich links UND rechts durch alle Zeilen dazwischen – alles
  in `var(--accent)`. Der rechte Strich kam am 19.09.2026 auf Wunsch des
  Nutzers dazu (vorher eine offene Klammer); er hängt an `:last-child`,
  weil die letzte Spalte mit der Entfernungs-Spalte wechselt. Ohne ihn standen die Strecken einer Veranstaltung
  mitten in der Liste, ohne dass man ihnen ansah, dass sie
  zusammengehören; man konnte nicht erkennen, ob eine Veranstaltung drei
  oder fünf Läufe hat (vom Nutzer gemeldet). Drei Entscheidungen daran:
  - **`box-shadow: inset` statt `border`.** Ein Rahmen aus Rändern
    verschöbe die Zeilen: `border-collapse: collapse` teilt sich die
    Ränder zwischen zwei Zeilen, und eine 2-px-Linie gegen die 1-px-Linie
    daneben macht die Zeile einen Pixel höher. Alle Zeilen sind aber
    gleich hoch (52 px), und der Rauchtest prüft das auf den Pixel. Ein
    Schatten wirkt nie auf das Layout.
  - **Der Block ist durchgehend in EINEM Blau hinterlegt** (`--accent-bg`,
    vom Nutzer am 19.09.2026 so gewünscht – vorher bewusst ohne Farbe).
    Die Regel steht zwischen Zebra und Auswahl. **Die gewählte Strecke
    im Block trägt dieselbe Farbe** – ein kräftigerer Ton für sie
    (`--row-active-block`) war gebaut und am selben Tag vom Nutzer
    verworfen („bitte die gleiche blaue Farbe benutzen"): In der Liste
    sah das wie zwei verschiedene Blautöne aus. Welche Strecke gewählt
    ist, zeigt der Detailbereich; die Klasse `active` bleibt an genau
    einer Zeile (Tastatur, `markiereAuswahl()`), färbt im Block aber
    nicht. Die Veranstaltungszeile wird **aufgeklappt nicht mehr
    mitmarkiert**, wenn eine andere Strecke gewählt ist (`aktiv` in
    `gruppenHtml`): Sie zeigt die erste Strecke selbst. Zugeklappt
    bleibt es beim Alten – dort steht sie für die verborgene Strecke.
    Der Rauchtest prüft eine Farbe im Block, anders als außen, genau
    eine als gewählt markierte Zeile darin mit derselben Farbe. Nicht
    wieder einen zweiten Ton einführen.
  - **Oben und unten über die ganze Breite.** Der senkrechte Strich
    allein reichte nicht: Die Tabelle ist mindestens 800 px breit und
    scrollt auf dem Handy waagerecht – wer nach rechts schiebt, sähe ihn
    nicht mehr. Die beiden waagerechten Linien laufen über alle Spalten.

  Die letzte Unterzeile trägt dafür die Klasse `letzte` (`subRowsHtml`).
  Bewusst eine Klasse und **kein** `.sub-row:not(:has(+ .sub-row))`: Der
  Selektor müsste bei über 4.000 Zeilen für jede davon die Nachbarschaft
  prüfen, und die Tabelle ist genau an dieser Stelle auf Tempo gebaut.
  Die Reihenfolge der acht CSS-Regeln ist bedeutungstragend – die
  Kombinationen für die Eckzellen (`:first-child`/`:last-child` mit zwei
  Schatten) müssen NACH den allgemeinen stehen: `box-shadow` ist EINE Eigenschaft,
  die spätere Regel ersetzt die frühere vollständig statt sie zu
  ergänzen.

  **Eine Zahl („5 Strecken") steht bewusst nicht dabei.** Sie hätte nur
  in die Namensspalte gepasst, und die ist 22 % breit – auf Handybreite
  176 px. Dort noch ein Textstück unterzubringen heißt, den Namen
  abzuschneiden. Der Rahmen zeigt die Zusammengehörigkeit, gezählt sind
  die Zeilen in einem Blick.
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
  `build_ics.py` und `icsFileName()` in `event-detail.js`
  (`<datum>-<name>-<distanz>-<ort>.ics`). Weichen sie ab, zeigt der Knopf
  ins Leere – `test_scraper_lib.py` prüft beide gegeneinander und lässt
  dafür den echten JS-Code in `node` laufen. Der **Ort** gehört in den
  Namen, weil Name + Datum + Distanz nicht eindeutig sein MÜSSEN: Zweimal
  stand dieselbe Strecke unter zwei Orten in den Daten (Königsforst-
  Marathon 18.09.2026, Legend of Cross Mühlberg/Drei Gleichen 21.09.2026)
  – beide Male ein Verortungsfehler, beide zusammengeführt, und danach
  gab es kein solches Paar mehr. Der Ort bleibt trotzdem: Der nächste
  Datenlauf bringt den nächsten Fall, und ein Dateiname, der sich mit
  jeder Bereinigung ändert, bräche geteilte Links und Kalender.
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
    steht nur EINMAL da, in `event-detail.js`: `icsFileName()` baut
    darauf auf, und `test_scraper_lib.py` prüft sie gegen
    `build_ics.ics_dateiname()` (schneidet dafür `icsSlug`,
    `icsMasszahl`, `eventSlug`, `icsFileName` aus dem Modul heraus -
    beim Umbenennen dort nachziehen). `EED.eventLink()` zeigt IMMER auf
    `events.html`, auch von der Karte aus – nur die Liste kennt
    `?event=`. Eine laufende Nummer wäre wertlos: Sie
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
- **Die Detail-Box ist ein Modul (`event-detail.js`/`.css`,
  `window.EnduranceDetail` = `EED`).** `EED.render(container, e, { t,
  tv, lang, onReport, onClose })` baut sie – in der Liste in
  `#detail-panel` (mit `onReport` → Melde-Dialog, ohne `onClose`), auf
  der Karte in `#map-details` **oben rechts über der Karte, bis zu zwei
  Boxen, die neueste oben, die dritte verdrängt die älteste** (vom
  Nutzer am 19.09.2026 so gewünscht: „genau gleiche Struktur wie wenn
  man auf eins von der Liste klickt"). **Ein Marker mit 1 oder 2
  Events öffnet die Boxen direkt beim Klick, ohne Popup**
  (`zeigeDetails(loc.events)`; „wenn ich auf die 1 klicke, soll sich
  rechts oben einfach die Info öffnen"). Erst ab drei Events listet das
  **Popup des Ortes seine Events** (`.popup-event`, `data-idx`); ein
  Klick öffnet die Box (`zeigeDetail`), EIN Zuhörer am Kartencontainer,
  weil Leaflet den Popup-Inhalt bei jedem Öffnen neu baut. `MAX_DETAILS`
  entscheidet beides. Vier Dinge daran:
  - **Keine Ids in der Box, nur Klassen** (`.event-share-btn`,
    `.report-open-btn`, `.cal-open-btn`, `.cal-menu`, `.cal-ics`, …):
    auf der Karte stehen zwei Boxen zugleich. Der Rauchtest sucht
    entsprechend `#detail-panel .event-share-btn`.
  - **„Fehler melden" auf der Karte führt in die Liste**
    (`EED.eventLink(e) + '&melden=1'`): Der Melde-Dialog mit Firestore
    lebt nur dort, `readUrlState()` liest `melden=1` (`deepMelden`) und
    öffnet ihn nach dem ersten Zeichnen; `writeUrlState()` wirft den
    Parameter gleich wieder aus der Adresse.
  - **Der Toast (`EED.showToast`) erzeugt sein Element selbst** – kein
    `#toast` mehr im Markup; `events.html` ruft ihn über den Wrapper
    `showToast()` auch für „Suche teilen".
  - **Ab 900 px stehen die zwei Boxen NEBENEINANDER** (`row-reverse`,
    die neueste rechts außen) – übereinander passten zwei nicht in die
    Kartenhöhe, die zweite war abgeschnitten. Unter 600 px beginnt der
    Stapel bei 84 px, unter Zoom-Knöpfen und Kopfzeile der Karte.
  - **Die Popup-Einträge haben feste Farben**, nicht die Seitenvariablen:
    Das Leaflet-Popup ist immer weiß, im Dunkelmodus waren die hellen
    Seitenfarben darauf unlesbar.
  - Auf Handybreite **liegt die Box über dem Popup** (die Karte ist nur
    390 px breit); der Rauchtest klickt weitere Popup-Einträge deshalb
    per JavaScript an. Am Rechner stören sie sich nicht.
  `formatRange`/`formatRangeHtml`/`formatLength`/`displayWettbewerb`
  wohnen ebenfalls im Modul; `events.html` behält nur Wrapper mit
  `currentLang` für die Tabelle.

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
  Textfeld der Spalte „Name"). **Gebaut wird das Feld von
  `filter-ui.js` (`ui.buildSearch(container)` → `{ sync, input }`),
  seit dem 19.09.2026 steht es auch auf der Karte** (vom Nutzer
  gewünscht) – ganz links in der Filterleiste, vor den Knöpfen. Markup,
  Vorschläge, Tastatur und CSS (`filter-ui.css`) liegen deshalb EINMAL
  im Modul; die Seiten rufen nur `suche.sync()` in ihrem `render()`
  (Platzhalter, ✕-Beschriftung und Feldinhalt folgen so Sprache und
  Zustand). Die Ids `master-search`, `-clear`, `-list` sind fest – ein
  Feld je Seite, der Rauchtest greift darauf zu. Zwei Felder statt
  einem, mit Absicht:
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

- **Die Länge eines Triathlons ist ein FORMAT, keine Zahl** – und zwar
  eines von SECHS (vom Nutzer am 21.09.2026 als Bild vorgegeben, „genau
  so aufnehmen"): **Super-Sprint, Sprint, Olympisch, Mitteldistanz
  (70.3), Langstrecke (140.6), Ultra-Triathlon**. Die Normdistanzen
  dahinter (DTU-Sportordnung, World Triathlon, Ironman):

  | Format | Schwimmen / Rad / Laufen | Summe |
  |---|---|---|
  | Super-Sprint | 250–500 m / 6,5–13 km / 1,7–3,5 km | ~9–17 km |
  | Sprint (Volks-/Jedermann) | 500–750 m / 18–22 km / 4,5–5,5 km | ~25,75 km |
  | Olympisch (Kurz-/Standarddistanz) | 1,5 / 40 / 10 km | 51,5 km |
  | Mitteldistanz (70.3) | 1,9 / 90 / 21,1 km | 113 km = 70,3 Meilen |
  | Langstrecke (140.6) | 3,8 / 180 / 42,2 km | 226 km = 140,6 Meilen |
  | Ultra-Triathlon | Vielfache der Langstrecke (Double, Triple, Deca) | ab 452 km |

  Die Kilometerzahl (Summe der Teilstrecken, Datenregel 15) bleibt in
  `events.json` und entscheidet Filter und Sortierung; ANGEZEIGT wird
  das Format – `triathlonFormat(e)` in `event-detail.js`, gebraucht von
  `formatLength()` (Tabelle, Box, Pillen), `formatLengthSpan()`
  (zusammengefasste Zeile und Karten-Popup: „Sprint & Olympisch",
  „Sprint, Olympisch & Mitteldistanz (70.3)") und dem Teilen-Text. Vier
  Dinge daran:
  - **Erst das Label des Veranstalters, dann die Summe.**
    `FORMAT_IM_LABEL` liest Ultra/Double/Deca, 140.6/Langdistanz/
    Langstrecke, 70.3/Mitteldistanz/Halbdistanz, Olympisch/Kurzdistanz/
    Standard (Kurzdistanz IST die Olympische Distanz), Super-Sprint,
    Sprint. Ohne Stichwort entscheidet die Summe – Regel des Nutzers
    (21.09.2026): „alles, was weniger als ein Sprint ist, ist Super-Sprint,
    alles über der 140.6 ist Ultra". Also: unter 23 km Super-Sprint (23 km
    ist der kleinste DTU-Sprint 0,5 / 18 / 4,5; darunter liegen Schnupper-,
    Einsteiger- und Fitnessdistanzen), bis 40 km Sprint (auch Volks- und
    Jedermann), bis 80 km Olympisch, bis 160 km Mitteldistanz, bis 230 km
    Langstrecke (226 km plus Spielraum für die Vermessung), darüber Ultra.
  - **Das sind GRENZEN zwischen den Formaten, keine Toleranzen um die
    Normdistanzen.** Deutsche Veranstaltungen weichen ab (Moritzburgs
    Langdistanz 218,8 km, Cross-Triathlons 41,5 km, Heilbronns
    Mitteldistanz 106,4 km); mit den früheren Bändern (51,5 ± 3 usw.)
    fielen sie in keine Filterkategorie. `DISTANCE_CATEGORIES.Triathlon`
    in `filters.js` und die Kopie in `functions/index.js` tragen die
    sechs Kategorien mit denselben Grenzen (Schlüssel `supersprint`,
    `sprint`, `olympic`, `middle`, `long`, `tultra` – nicht `ultra`, der
    ist der Ultramarathon, und die Beschriftungen hängen am Schlüssel).
  - **Swimrun und Quadrathlon kennen die Formate nicht** (ein 40-km-Swimrun
    ist kein „Olympisch"): dort zählt nur ein Stichwort im Label, sonst
    die Kilometer. Ein **Duathlon** über Mittel-/Langstrecke heißt
    „Mitteldistanz"/„Langstrecke" ohne den Zusatz 70.3/140.6 – das sind
    Triathlon-Marken.
  - **Zwei Strecken mit demselben Format bekommen die Kilometer dazu**
    (Jedermann 500/20/5 und Sprint 750/20/5 sind beide „Sprint"):
    Pillen als „Sprint (25,5 km)" / „Sprint (25,8 km)", der Fakt in der
    Box immer „Olympisch (51,5 km)" (`formatLength(e, lang, { mitKm: true })`).
  Das Wettbewerbs-Label trägt die Gesamtlänge VORN und die Teilstrecken
  in Klammern („Kurzdistanz 51,5 km (1,5 km Schwimmen / 40 km Rad /
  10 km Laufen)") – so bleibt `drop_contradicting_wettbewerb()` still,
  und die Box zeigt die Aufteilung. Die Länge-Spalte ist dafür auf 16 %
  verbreitert (Name 23 %, Sportart 11 %, Ort 12 %; Land bleibt 12 %, mit
  10 % brach „Deutschland" bei 900 px um): „Mitteldistanz (70.3)" braucht
  zwei Zeilen, drei Formate passen in die zwei Zeilen der `.cell-clamp`;
  nur `.cell-clamp.format` darf in der Länge-Spalte umbrechen.

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

- **Der Rauchtest sucht seinen Kartenort aus `events.json`**
  (`ort_mit_zwei_veranstaltungen()` in `smoke_test_frontend.py`): der
  alphabetisch erste Ort mit genau zwei künftigen Veranstaltungen (Name +
  Starttag – die Karte zählt seit dem 21.09.2026 Veranstaltungen, nicht
  Strecken), für den Marker „2". Vorher stand dort fest „Mosnang" (Schnebelhorn
  Panoramatrail) – am 19.09.2026 fiel das Event als vergangen aus der
  Liste, und die Prüfung meldete „0 Boxen", ohne dass sich an der Karte
  etwas geändert hatte. **Ein roter Rauchtest nach einer Datenänderung
  kann ein fest eingetragenes Beispiel sein** – dieselbe Lehre wie beim
  Enter-Fall im zweiten Durchgang. Keine festen Ortsnamen mehr in den
  Prüfungen.

- **Der Rauchtest zählt die Strecken einer Veranstaltung über Name +
  Datum + Ort**, nicht über die Suchtreffer zum Namen
  (`pruefe_gruppierung()`). Nach dem Datenlauf vom 21.09.2026 war die
  erste aufklappbare Veranstaltung „Fun & Erlebnis Marathons“ – eine
  Serie mit 17 Zeilen an acht Terminen. Die Mastersuche zeigte 17,
  aufgeklappt waren es 2, vier CI-Läufe rot („Run failed“-Mails), ohne
  dass sich an Seite oder Daten etwas geändert hatte. Der Name allein
  ist kein Schlüssel; der Schlüssel ist derselbe wie beim Zusammenfassen
  (`groupKey`). Dritte Begegnung mit dieser Fehlerklasse (Enter-Fall,
  Kartenort, Serie).

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
  **Seit dem 21.09.2026 zeichnet `zeichneMaske()` aus denselben Ringen
  zusätzlich die LANDFLÄCHE** (Pane `landPane`, z-index 150 unter den
  Kacheln, `fillRule: nonzero`, hell gefüllt): Sie ist die flache Karte
  der Übersicht, solange die Kacheln ausgeblendet sind (siehe
  Frontend-Fallen, „Die Karte ist seit dem 21.09.2026 …“).
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
  `updateIndicators()`, `close()`, `options()`, `resetTransient()`,
  `buildSearch(container)` (die Mastersuche, siehe Frontend-Fallen).
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
  seinen Knopf zurück (`closePanel(true)`), **Enter im Textfeld des
  Namens-Panels ebenso** – der Filter griff schon beim Tippen, aber das
  Panel blieb stehen (vom Nutzer am 19.09.2026 gemeldet); das Feld
  trägt `enterkeyhint="done"`. Pfeil nach unten am Knopf
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

1. **`?v=<Stempel>`** an `site.css`, `filters.js`, `filter-ui.js`,
   `filter-ui.css`, `event-detail.js` und `event-detail.css` in allen
   HTML-Dateien - der Stempel ist die ersten
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

**running.life liest seit dem 21.09.2026 alle sechs Kalender** (vom
Nutzer freigegeben: „Du hast mein Ja"): Laufen und Triathlon je
Deutschland, Österreich, Schweiz – `KALENDER` in
`runninglife_scraper.py`, je Kalender mit eigener Sportart-Voreinstellung
(Triathlon-Kalender → „Triathlon"; `expand_competitions()` nimmt seit
dem Tag die Kategorie-Liste der Sportart, sonst bekäme ein
Cross-Triathlon „Trail"). Die Adresse für Österreich heißt
`/laufkalender/osterreich` (mit oe ist 404). `--max-pages 110` gilt je
Kalender, die kleinen enden von selbst. Probelauf (eine Seite je
Kalender, ohne Details): 104 neue Events, davon die ersten Schweizer
überhaupt. **Der nächste Datenlauf bringt sie** – Workflow auslösen,
nicht im Chat warten (Laufzeit steigt um grob eine Stunde, das
`timeout-minutes: 300` reicht).

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

**Der Zeitplan läuft aus der Fassung auf `main`, nicht aus der auf
diesem Branch.** GitHub liest `schedule`-Trigger nur aus dem
Standard-Branch. `main` enthält deshalb genau zwei Dateien:
`.github/workflows/update-events.yml` und `README.md`. Die Skripte holt
der Workflow vom Entwicklungs-Branch, den er ausdrücklich auscheckt
(`ref: claude/endurance-events-website-v1wruf`).

**Seit dem 19.09.2026 ist die Datei dort auf dem aktuellen Stand**
(vom Nutzer freigegeben, Commit `c7af0ba` auf `main`). Vorher war sie
ein älterer Stand, und jeder der vier Unterschiede hatte Folgen – das
ist der Grund, warum die beiden Fassungen **nicht auseinanderlaufen
dürfen**:

| war auf `main` | Folge |
|---|---|
| `git add events.json` **ohne `kalender`** | Der Datenlauf ließ die `.ics`-Dateien uncommittet liegen. Der CI-Schritt „kalender/ passt zu events.json" schlug danach bei JEDEM Push fehl, auch bei solchen ohne Datenbezug – am 18.09.2026 viermal hintereinander |
| täglicher Cron statt wöchentlich montags | Laufzeit und tägliche `events.json`-Diffs von ~450 KB, solange die Seite nicht live ist |
| kein `timeout-minutes` | Ein Lauf dauert ~2 Stunden; ohne Grenze lässt GitHub sechs zu, eine hängende Quelle verbrennt sie |
| keine NOTIFY-Secrets | `update_events.py` ruft den Webhook für „Benachrichtige mich" gar nicht erst auf |

**Wird die Workflow-Datei hier geändert, muss sie auf `main` mit** –
sonst ist die Änderung wirkungslos oder, schlimmer, sie wirkt
halb. Damals behoben wurden auch die Folge (`build_ics.py` laufen lassen
und mitcommitten) und die Erkennung (`test_kalenderdateien` vergleicht
`kalender/` mit `events.json`, siehe „Vor jedem Commit").

**`stage_kalender()` in `update_events.py` bleibt als Gürtel neben den
Hosenträgern**: Es legt die frisch erzeugten `.ics`-Dateien nach
`build_ics.py` in den Git-Index – nur in GitHub Actions, lokal nie.
`git commit` committet den INDEX, nicht nur die Pfade hinter `git add`;
was dort gestaget ist, geht also mit, auch wenn eine Workflow-Datei das
`kalender` hinter `git add` einmal wieder verliert. Mit der jetzigen
Fassung (`git add events.json kalender`) ist der Aufruf ein No-op.
`test_kalender_staging` hält vor allem die Gegenprobe fest: **lokal darf
das Skript den Index NIE anfassen.**

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
   Was dafür vorher fehlte, ist gebaut: `ART2_KEYWORDS_FAHRRAD` (seit
   Datenregel 12) und `ART2_KEYWORDS_SCHWIMMEN` (21.09.2026, mit
   „Charity", siehe Datenregel 17); running.life liefert seit dem
   21.09.2026 AT/CH und Triathlon (siehe „Quellen"). **Triathlon ist seit dem
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

   **Am 21.09.2026 nach der Vorlage des Nutzers umgebaut** (ein Bild
   der gewünschten Liste, „Können wir die Liste so aufbauen“): Marke und
   einheitliche Kopfzeile auf allen drei Seiten, dunkles Farbschema,
   Filterpillen über der Tabelle, Sportart-Symbole, Detail-Box mit großem
   Datum, Abzeichen, Strecken-Pillen und gestuften Knöpfen, „Stand“ in
   der Werkzeugleiste, Fußzeile – siehe Frontend-Fallen, erster Punkt.
   **Am selben Tag die Karte nach der zweiten Vorlage** („Die Map bitte
   so gut wie möglich in dem Format darstellen“, ein helles Bild): flache
   Landfläche, Bündel mit Ortsnamen, Nadeln in Sportfarbe, „Mein
   Standort“, Legende, Entfernung in der Box – und weil die eine Vorlage
   dunkel und die andere hell war, gibt es seitdem **beide Schemata mit
   Umschalter** in der Kopfzeile (Voreinstellung: die Systemeinstellung).
   Siehe Frontend-Fallen, erster und zweiter Punkt.

   Offen, in dieser Wirkung:
   - **Handy: Karten statt Tabelle.** Unter ~700 px liegen Länge und
     Sportart außerhalb des Bildes, man muss waagerecht scrollen. Eine
     Karte je Event (Name, Datum, Ort, Marken) ist der größte Hebel.
   - Kleinteiliger: ~~`og:image`~~ **gebaut** (21.09.2026: `og-image.png`
     mit der GitHub-Pages-Adresse; bei einem Domainwechsel in allen drei
     Seiten nachziehen). ~~Ladezustand~~
     **gebaut** (21.09.2026: acht Platzhalterzeilen im `<tbody>`, und
     `render()` lässt sie stehen, bis `events.json` da ist –
     `eventsGeladen`. Die Sperre ist der eigentliche Teil: Ein früher
     `render()` aus `onAuthChange` zeigte vorher bei jedem Aufruf „0
     Events / Keine Events gefunden" samt Abo-Kasten, bis die Daten da
     waren; der Platzhalter allein wäre sofort überschrieben worden. Das
     kam erst mit einem Bildschirmfoto bei angehaltenem Abruf heraus –
     der Rauchtest wartet auf die Daten und sieht diesen Zustand nie);
     „DACH" und
     „Beispielprojekt" kommen in sichtbaren Texten nicht mehr vor
     (nur noch in Code-Kommentaren, geprüft 21.09.2026).
5. **Live schalten** – GitHub Pages läuft, die CI schützt seit dem
   16.09. davor, dass etwas Kaputtes deployt. Einziger Blocker ist noch
   die **E-Mail-Adresse** für Impressum und Datenschutz (der Nutzer
   richtet sie ein) – Name und Anschrift stehen seit dem 17.09.2026.

## Offene Punkte / To-dos

### Was der Nutzer noch entscheiden muss (Stand 19.09.2026)

Gesammelt aus der Einzelprüfung und dem Design-Durchgang. **Jeder Punkt
wartet auf ein Ja/Nein des Nutzers** – nichts davon entscheidet Claude
allein. Die Belege stehen in `scripts/geprueft.json` (Ergebnis `unklar`).

1. ~~Virtuelle Läufe – rein oder raus?~~ **entschieden** (21.09.2026:
   „rausnehmen") – Regel in `NICHT_AUSDAUER`, prüft auch den Ort; siehe
   Datenregel 14.
2. ~~Abgesagte Veranstaltungen~~ **entschieden** (21.09.2026: „nicht
   aufführen") – per Override mit Beleg, `seitenabgleich.py` meldet
   ABGESAGT; siehe Datenregel 18.
3. ~~Staffeln~~ **entschieden** (21.09.2026: „Erst einmal keine Staffeln
   aufnehmen") – Datenregel 16.
4. ~~Die 5-km-Grenze bei „5 km" mit 4,8 km~~ **entschieden** (19.09.2026):
   Läufe unter 5 km bleiben draußen, auch die als „5 km" beworbenen. Sedus
   (4,80 km), Bramfelder Winterlaufserie (4,66-km-Runde), Hochplatten
   (4,6 km) und Herbstcross Saalfeld (4,8 km) stehen mit ihrer echten
   Länge im Override und sind heraus – siehe Datenregel 5.
5. **Meisterschaften im Rahmen eines Volkslaufs** stehen NICHT mehr
   doppelt (7 Fälle entfernt, z. B. Bayerische Halbmarathon-
   Meisterschaften = Aschaffenburger Halbmarathon). Umkehrbar, falls
   die Meisterschaft als eigener Eintrag gewünscht ist.
6. ~~Zahl der Strecken am aufgeklappten Block?~~ **entschieden**
   (21.09.2026: „nicht relevant") – keine Zahl.
7. ~~`runninglife_scraper.py` auf alle sechs Kalender ausweiten~~
   **gebaut** (21.09.2026, „Du hast mein Ja") – siehe „Quellen"; die
   Events kommen mit dem nächsten Datenlauf.
8. **Die Quellenliste für die 20.000+** steht seit dem 21.09.2026 im
   README („Quellen für den großen Datenlauf": 19 Kandidaten mit
   robots.txt-Stand; die Recherche vom 18.09. war nie im Repo gelandet).
   Gesperrte Quellen stehen auf Wunsch des Nutzers nicht in der Liste
   (radsport-events.de, schwimmkalender.de, tri2b.com, triafreunde.com,
   hdsports.org, datasport.com, alpen-open-watercup.de, rad-net.de,
   swiss-cycling.ch, ahotu.com). Der Nutzer sieht die Liste durch; kein
   Scraper ohne sein Ja.
9. ~~Backyard Ultra TRIATHLON – eigene Kategorie „Backyard"?~~
   **entschieden** (19.09.2026): Laufen und Triathlon tragen denselben
   Wert „Backyard Ultra" (siehe Datenregel 9); der „Backyardman
   Würzburg" steht so in der Liste.
10. ~~raceresult-Kontaktseiten auswerten~~ **gebaut** (19.09.2026, vom
   Nutzer freigegeben): `scripts/veranstalter_links.py` – für ALLE
   Zeitnehmer-, Anmelde- und Portallinks, nicht nur raceresult. Kein
   `pending_overrides.json`-Umweg: Übernommen wird nur, was die
   Zielseite am Namen des Laufs belegt; alles andere steht als `unklar`
   im Linkprotokoll. Ergebnisse siehe „Neunter Durchgang".

12. **Ergebnisse der Linkprüfung** (19.09.2026, siehe „Vierter
   Durchgang"): sechs Duplikate unter zwei Namen zusammenführen oder
   ausschließen? Dazu aus dem neunten Durchgang: „Rennbahncross in
   Herxheim" / „Rennbahncross mit rheinland-pfälzischen
   Crosslaufmeisterschaften" (15.11.2026, dieselbe Seite). Bordesholmer SEE&RUN 2026 (abgesagt), Wiehenläufer und
   Crosslauf Jüchen ausschließen? Und `raceresult_kontakt.py` (Punkt 10)
   lohnt sich: Von 47 Kontaktseiten nannten 24 eine brauchbare
   Organizer-URL.

20. **Farbschema und Pillen (21.09.2026, aus dem Kartenumbau)** – drei
   Kleinigkeiten, die ein Ja/Nein brauchen:
   - **Voreinstellung hell oder dunkel?** Heute folgt die Seite der
     Systemeinstellung (`prefers-color-scheme` im Kopf-Skript), der
     Knopf überschreibt sie dauerhaft. Soll IMMER dunkel (Vorlage der
     Liste) oder IMMER hell (Vorlage der Karte) die Voreinstellung sein,
     ist es eine Zeile im Kopf-Skript aller drei Seiten.
   - **Die Pille „Name"** steht weiter ganz rechts in der Filterleiste
     (beide Vorlagen zeigen sie nicht; die Mastersuche deckt Name und
     Ort ab). Weg damit hieße: `'name'` aus `FILTER_ORDER` in beiden
     Seiten streichen und die Rauchtest-Prüfung des Namens-Panels
     umziehen.
   - **Das Raster der Karte** steht fest (CSS-Hintergrund) und wandert
     beim Schieben nicht mit – wie Papier. Ein echtes Gradnetz wäre eine
     eigene Ebene aus Linien; nur, wenn es stört.

11. ~~Weg zurück zur Startseite~~ **gebaut** (21.09.2026, mit dem
   Umbau nach der Vorlage): Die Marke „Endurance Events" im Kopf ist ein
   Link auf `index.html` (übliche Konvention). Falls der Nutzer das
   nicht will, ist es ein `href` in `site.css`-Markup aller drei Seiten.

13. ~~Treppenläufe – rein oder raus?~~ **entschieden** (21.09.2026: „als
   Trail aufnehmen", Datenregel 6). Ursprünglich: Sieben Zeilen sind Towerruns
   (ADAC Charity Treppenlauf München: „472 Stufen, 22 Etagen“, TK
   Elevator Towerrun, ALTIMATE Treppenlauf Berlin, Teltschikturm,
   Monschau, Lotto Thüringen Treppenlauf). Das ist ein eigenes Format
   ohne Laufdistanz – dieselbe Frage wie bei HYROX, nur ist es Laufen.
   Der Idar-Obersteiner Felsenkirche Treppenlauf ist KEIN Towerrun,
   sondern ein Berglauf über 5,4 / 8,1 km mit Treppen im Kurs – der
   bleibt in jedem Fall (stand fälschlich mit 42,2 km, korrigiert).
   Vorschlag: raus, per `NICHT_AUSDAUER`-Zeile `treppenlauf|towerrun`,
   mit dem Idar-Obersteiner als Gegenprobe im Test.

14. ~~Spenden-, Schul- und Fitnessformate ohne Wettkampfdistanz~~
   **entschieden** (21.09.2026): Spenden- und Spaßformate bleiben und
   bekommen die Kategorie „Charity" (Datenregel 17), Schul-Events
   fliegen per Override (Bonner Friedenslauf), Runworx und Black Forest
   Team Battle stehen in `NICHT_AUSDAUER`. Ursprünglich: Beim
   Durchgehen der Zeilen ohne Maßzahl (19.09.2026) kamen drei Sorten
   zusammen, alle im Protokoll als `unklar`:
   - **Runden-Spendenläufe mit frei gewählter Dauer** (Sterntaler
     Spendenlauf Mannheim, STELP Spendenlauf Stuttgart, ProSana
     Gesundheitslauf Schramberg) und ein **Schul-Spendenlauf** (Bonner
     Friedenslauf, „hunderte Schüler*innen"). Wo die Dauer FEST ist
     (Waschmühle 6 h, Rotary Albstadt 1 h, Meißen 1 h, Rastenberg 4 h),
     stehen sie jetzt als Zeitrennen – das ist Datenregel 8. Ohne feste
     Dauer bleibt nur „–", oder sie fliegen raus.
   - ~~Fitness-Rennen mit Kraftstationen~~ **entschieden** (19.09.2026,
     „Ja HYROX ausschließen"): Gymrace und Decathlon Hybrid Series stehen
     in `NICHT_AUSDAUER`, drei Zeilen sind heraus. Die Spenden-, Schul-
     und Spaßformate darunter und darüber bleiben offen.
     **Nachzügler (19.09.2026, neunter Durchgang)**: „Runworx" in
     Vogtei (31.10.2026) ist laut runworx.de ein 5-km-Hindernislauf mit
     anschließendem Kraft-WOD im Gym – dieselbe Klasse; steht als
     `unklar` im Protokoll, weil eine weitere `NICHT_AUSDAUER`-Zeile
     ohne Ja des Nutzers nicht dazukommt. Der „Klaar Kiming Throwdown"
     (Bredstedt, 24.04.2027) ist dagegen ein reiner CrossFit-Wettkampf
     ohne Lauf und per `exclude` heraus.
   - **Spaßformate**: Schweiger Tragathlon (Bierkasten-Tragen in
     Viererteams), The Quest Auwald (Checkpoint-Jagd über 2/3 h,
     Strecke frei), Pace Race Nürnberg („Social Racing"-Arena).

15. ~~Scraper-Ergänzung: die laufen.de-Weiterleitung mitnehmen~~
   **gebaut** (19.09.2026, vom Nutzer freigegeben):
   `veranstalter_link_aus_weiterleitung()` in `laufkalender_scraper.py`;
   `enrich_from_details()` ruft die Detailseite mit
   `allow_redirects=False` ab und nimmt bei einem 302 das Ziel als
   `veranstalter_url`, außer es liegt auf laufen.de, einem Anmeldeportal
   (lanet3, raceresult, datasport, racepedia), einem sozialen Netz oder
   einer `PORTAL_DOMAINS`-Adresse (`WEITERLEITUNG_KEIN_VERANSTALTER`).
   Bei einer Weiterleitung gibt es keine Detailseite zum Parsen –
   Wettbewerbe und Land bleiben dann auf dem Stand der Ergebnisliste,
   wie vorher auch (die Veranstalterseite lieferte nie welche).
   `test_laufen_weiterleitung` prüft Helfer und Abrufschleife mit einer
   Fake-Session. Die 120 Overrides aus dem achten Durchgang bleiben
   stehen; beim nächsten Datenlauf sind sie für diese Events ein No-op.

16. ~~Vereinsinterne Leichtathletik-Veranstaltungen~~ **zurückgenommen**
   (19.09.2026, am selben Tag): Der „4. Zülpicher Seepark Nikolauslauf"
   war kurz per `exclude` draußen, weil der Veranstalter die
   Leichtathletik-Abteilung des TuS Zülpich ist. Die Seite zeigt aber
   einen offenen Volkslauf (Jedermannlauf, Firmenstaffel, 9,5-km-
   Hauptlauf mit Online-Anmeldung), und der Nutzer hat ihn zurückgeholt.
   Dabei fiel auf, dass der **Chlodwiglauf 2027** (14.03.2027, ca. 10 km
   Eifelcup + ca. 5 km Jedermannlauf) ganz fehlte – nachgetragen in
   `manual_events.json`; die Ausschreibung 2027 ist noch nicht
   erschienen, die Distanzen stehen dort als „ca.". Lehre wie bei
   Punkt 4 der Einzelprüfung: **Der Hostname („leichtathletik") sagt
   nichts über die Offenheit** – 17 Domains, 34 Zeilen, fast alles
   Volksläufe, die ein LA-Verein ausrichtet. Nie am Domainnamen
   entscheiden.

17. **Funde des zehnten Durchgangs (20.09.2026)** – alles nur notiert:
   - **Duplikat unter zwei Namen**: „32. FT Jahn Nikolauslauf“ und
     „Nikolauslauf Landsberg a. Lech“ (06.12.2026) sind derselbe Lauf
     der FT Jahn Landsberg; beide zeigen jetzt auf ftjahn-landsberg.de,
     `report_gleiche_seite_gleiche_distanz()` meldet sie.
   - **HYROX-/Treppenlauf-Klasse** (Punkte 13/14): „Black Forest Team
     Battle“ (Oberreichenbach, 5×1 km plus Kraftstationen in
     Zweierteams – laut Veranstalter „functional fitness competition“),
     „Bad Wildbader Stäffeleslauf“ (1.987 Stufen, 720 m) und „X-Mas
     StairRun Oberhof“ (701 Stufen der Schanze, **nur für Feuerwehr und
     Polizei** mit Atemschutz – für Läufer gar nicht buchbar). Dazu
     „Weinathlon“ (Mücheln, 8,5 km mit sieben Weinstationen, „kein
     klassischer Wettkampf“) und „Die Ha(a)rd Winter“ (laut raceresult
     eine **Backyard-Wanderveranstaltung**, 02.–04.01.2027).
   - **Ortsfehler?** „Cross- und Waldlaufmeisterschaften“ (31.10.2026)
     steht bei uns in Rheine; laut LG Emsdetten findet die Kreis-Cross-
     und Waldlaufmeisterschaft 2026 in Ibbenbüren-Dickenberg statt (SV
     Dickenberg). Nicht geändert – ladv.de nennt Rheine.
   - **Private Ultras mit ~20 Plätzen** wie „Rund um Schloß Holte“ (50 km,
     GPX-Navigation, mindestens drei Anmeldungen) gehören zur Uwe-Laig-
     Klasse: nur raceresult, keine Seite, keine Websuche wert.

18. **Funde des elften Durchgangs (21.09.2026)** – Belege in
   `geprueft.json` (`am` = 2026-09-21), nichts davon entschieden:
   - **Duplikate unter zwei Namen**: „25. Altstadtfestlauf in Lauf"
     (10 km) und „Altstadtfestlauf in Lauf" (5 km) sind ein Lauf des
     Skiclubs Lauf; „TEAG – Legend of Cross" steht mit zwei Terminsätzen
     (31.10./01.11.); Altwarmbüchen unter zwei Namen. Die 12,5-km-Zeile
     des „31. Griesheimer Silvesterlaufs" steht in Flörsheim-Weilbach mit
     TG-Weilbach-Link – wohl der Weilbacher Silvesterlauf, zusammengeführt
     unter dem falschen Namen (Seite nennt 2026 noch nicht).
   - **Nicht öffentliche Läufe**: Der „67. Panorama Marathon" (Running
     Paule, 24.10.2026) ist laut Ausschreibung ein „gemeinsamer, nicht
     öffentlicher Trainingsmarathon" – dieselbe Klasse wie die privaten
     Ultra-Serien. Rein oder raus?
   - **Staffeln** (Punkt 3 weiter): Landkreislauf Schwandorf (10 Läufer,
     49,5 km / 3 Walker, 12,5 km), Weeze 3×5 km, Dinkelsbühl 4×3 km,
     Firmenstaffel Sachsen-Anhalt 5×3 km – stehen mit der
     Team-Gesamtstrecke und sagen es im Label.
   - **Zeitrennen neben Distanz-Zeilen fehlen** (Rokathon 24 h, 24 Stunden
     van Halen, Winterloop 6/12 h) – braucht eine Code-Änderung an
     `_compatible_distance()`, siehe Elfter Durchgang.
   - ~~Termine, die wahrscheinlich falsch sind~~ **entschieden**
     (21.09.2026): als vorläufig markiert („Juni 2027*", Datenregel 19) –
     Mittsommernachtslauf Hannover, Haasower Waldlauf, LST Super Sunday,
     Wolfhager Volkslauf, Gläserner Mönch Lauf, Triathlon Offenburg,
     Ibbenbürener Klippenlauf und 49 weitere Prognosen.
   - **Sonstiges**: ClimAid Plant a Tree Run ist nur für 2024 belegt;
     Teltowkanal 14 km, Bremer Kuhcross, Warendorfer Garagen-Backyard,
     Neunkirchner Sommerlauf 2026 abgesagt, Belgershainer Crosslauf
     möglicherweise eingestellt, Distanzen von Kulmbach Trails / Zötler /
     Marienhagen nicht prüfbar (siehe Notizen).
   - **Umkehrbar**: Internationaler Kammlauf Klingenthal (Skilanglauf)
     ist per `exclude` heraus.
   - **Aus den Portal- und laufen.de-Seiten** (Nachtrag, 21.09.2026):
     weitere Duplikate unter zwei Namen – „49. Herbstlauf Ready4Run
     Niederwangen" (5,4 km) = „Herbstlauf Niederwangen" (5 / 10,5 km),
     „Schwollener Crosslauf – 2. Lauf der OIE-Serie" (6,4 km) = „Lauf
     der Nahe-Crosslauf-Serie in Schwollen" (6 km), „2. Potsdamer Cross
     im Rahmen der 22. DPM" (5,5 km) = wohl „Crosslauf in den
     Ravensbergen" (5/7/9 km, gleicher Tag). Ausgeschlossen, weil die
     Seite es belegt: „30. Braunsteichlauf Weißwasser" (= Spendenlauf am
     Braunsteich), „Crosslauf-Kreismeisterschaften" (im Oelder Berg- und
     Crosslauf), die 90-km-Zeile des SCC Cross Country (Tippfehler für
     9 km). Und **„Lusatian Race Walking"** (24.10.2026, 42,2 km) ist
     Gehen, keine Laufveranstaltung – dieselbe Frage wie beim Kammlauf.

19. **Stand nach den Entscheidungen vom 21.09.2026 – was offen bleibt:**
   - **Walking-Strecken innerhalb von Volksläufen** (145 Zeilen, „5 km
     Nordic Walking" neben dem Hauptlauf) und reine Wanderformate: Der
     Nutzer hat Gehen (Race Walking) und Skilanglauf ausgeschlossen;
     ob Nordic Walking dazugehört, ist nicht entschieden. Die Walking-
     Zeilen stehen als `art1` Laufen in der Liste. Die „Ahmadiyya
     Charity Walks" sind als Charity MARKIERT und behalten seit dem
     Umbau vom 21.09.2026 ihre Kategorie (siehe Datenregel 17).
     **Der Zusatz unter dem Namen macht einen Teil davon sichtbar**:
     Seit die Anzeige die Maßzahlen herausschneidet, steht dort bei
     **76 Zeilen** „Walking" bzw. „Nordic Walking" (aus „5 km Walking,
     Jahrgang 2012 und älter" wird „Walking, Jahrgang 2012 und älter") –
     genau der Fall, den der Nutzer als Beispiel für einen guten Zusatz
     genannt hat. Die 18 „Ahmadiyya Charity Walk" gehören NICHT dazu:
     Ihr Label ist schlicht „5 km", die Gattung steht nur im Namen. Wer
     die Walking-Zeilen zählen will, darf sich also nicht auf den Zusatz
     verlassen.
   - ~~Duplikate unter zwei Namen~~ **abgearbeitet** (21.09.2026, nach
     Belegen): FT Jahn Nikolauslauf, Altstadtfestlauf in Lauf (10 km
     unter den anderen Namen umgezogen), Niederwangen, Schwollen, TEAG
     Legend of Cross (Mühlberg = Drei Gleichen; zusammengeführt über
     drei gleiche Label-Overrides, weil `_same_name()` zwei
     verschiedene Labels für zwei Wettbewerbe hält und der
     Override-Schlüssel nicht nach Ort oder Link unterscheidet). Zwei
     **Meisterschaft-im-Rahmen**-Fälle dazu, umkehrbar wie die sieben
     anderen (Punkt 5): Potsdamer Cross (Polizeimeisterschaft) und die
     rheinland-pfälzischen Crosslaufmeisterschaften in Herxheim. Die
     übrigen Paare der Liste waren durch die Datenläufe seit dem 19.09.
     schon verschwunden (Zons, Grengel, Altwarmbüchen, Bordesholm,
     Wiehenläufer, Jüchen, Wertach, Kriegsheim, Fleckenberg,
     Staffelläufe). Offen: Rellinger Citylauf (17,3 km UND 1 h, Seite
     503).
   - **Neu aus dem Vierzehnten Durchgang (21.09.2026), je ein Ja/Nein:**
     - **Paarläufe** (Zweier-Teams über 30/60 Minuten) – Staffel im
       Sinne von Datenregel 16, also raus? Drei im Bestand.
     - **Firmenläufe nur für Teams** (Firmenlauf Ratingen: „Teams von
       Unternehmen, Institutionen, Vereinen", keine Einzelstarter) –
       rein oder raus? „Es soll jeder die Chance haben sich anzumelden"
       spräche für raus. **Stichprobe von 8 der 28 Firmenläufe
       (21.09.2026, Veranstalterseiten)**: Essen lässt Einzelstarter
       ausdrücklich zu (Solo im „bunert Essen Team"), Gießen und
       Sauerland nennen nur Teams (Sauerland: auch Einzelunternehmer),
       Bonn, Landshut, Bamberg, Ludwigsburg und Soest sagen es nicht
       (Bamberg: hybrid mit 4-wöchiger Sammelphase). Die Klasse ist also
       gemischt; eine Regel „Firmenlauf = raus" träfe auch offene.
     - **THE ROX, Deadly Dozen, ATHX** in `NICHT_AUSDAUER` aufnehmen?
       Heute per Override draußen (sieben Zeilen); mit der Liste blieben
       sie beim nächsten Datenlauf von selbst draußen.
     - **Wings for Life World Run** trägt jetzt `charity` per Override
       (100 % Startgeld für Rückenmarksforschung, belegt) – 23 Zeilen.
       Falls nicht gewünscht: die Overrides tragen `"charity": true`,
       ein `false` schaltet es ab.
   - ~~2027-Termine, die Prognosen sind~~ **entschieden** (21.09.2026):
     „Juni 2027*" mit Fußnote, Datenregel 19.
   - ~~Zeitrennen neben Distanz-Zeilen~~ **gebaut** (21.09.2026):
     `_compatible_distance()` trennt Distanz und Dauer, die vier Zeilen
     (Rokathon 24 h, van Halen 24 h, Winterloop 6/12 h) stehen in
     `manual_events.json` – Datenregel 8.
   - ~~Cross- und Waldlaufmeisterschaften Rheine/Ibbenbüren~~ **erledigt**
     (Websuche 21.09.2026: lg-emsdetten.de nennt Ibbenbüren/Dickenberg,
     Ausrichter SV Dickenberg – Override mit Koordinaten des Ortsteils).
     ~~Zahl der Strecken am Block~~ **entschieden** (21.09.2026: nein).
     ~~Quellenliste~~ **steht jetzt im README** („Quellen für den großen
     Datenlauf", 21.09.2026, ohne die gesperrten Quellen) – der Nutzer
     sieht sie durch; kein Scraper ohne sein Ja.

Dazu die Punkte, die kein Ja brauchen, aber Arbeit sind: E-Mail-Adresse
für Impressum/Datenschutz (nur der Nutzer), die zwei Blaze-Schritte für
den E-Mail-Versand, `og:image` sobald die Domain steht, und die
Testmeldung in `errorReports` verwerfen.


- ~~`og:image` nachtragen~~ **erledigt** (21.09.2026): `og-image.png`
  mit der Adresse `antdon930.github.io/Enduranceevents/`; bei einem
  Domainwechsel die Adresse in allen drei Seiten ändern.

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

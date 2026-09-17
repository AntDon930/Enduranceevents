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
| `scripts/update_events.py` | führt alle Scraper + Aufräumen aus (nutzt der Workflow) |
| `scripts/manual_overrides.json` | einzeln recherchierte Korrekturen |
| `scripts/review_reports.py` | Nutzer-Fehlermeldungen bündeln → Vorschlag → Bestätigung |
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

Er öffnet die drei Seiten auf Handybreite in Chromium und prüft 73 Punkte:
Laden ohne Fehler und ohne 404, Kopfangaben, kein Überlauf, Aufklappen der
zusammengefassten Veranstaltungen, Filter-Panel, Kalenderdatei hinter dem
Knopf, Bündelung der Marker (Summe der Bündel-Zahlen = Kopfzeile),
Ausgangspunkt ungebündelt, das Fenster der Tabelle (nur ein Schub im
DOM, volle Trefferzahl, Knopf hängt nach), Teilen eines Events (was an
`navigator.share` geht und der Rückweg über den geteilten Link),
Impressum und Datenschutz (erreichbar von jeder Seite, Platzhalter
sichtbar, Sprachumschalter), Tastaturbedienung (ein Tab-Stopp, Pfeile,
Enter, Escape, Fokusfessel der Dialoge), Filter über den Weg
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
  die Tabelle bündelt sie nur nach Name + Datum + Ort, zeigt die
  Distanzen als Marken und vorn die Spalte „Anzahl" (auch „1").
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
  Namen, weil Name + Datum + Distanz nicht eindeutig sind
  („Königsforst-Marathon" steht mit 42,2 km zweimal in den Daten).
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
- **Dialoge: `dialogTasten()` steht in `auth.js`** (Escape + Fokusfessel,
  `aria-modal="true"` verspricht genau das) und wird von `events.html`
  für den Melde-Dialog mitbenutzt – **erst beim ersten Öffnen**
  eingehängt, weil `auth.js` `defer` trägt und beim Inline-Skript noch
  nicht existiert (dieselbe Reihenfolge wie bei `EE_AUTH_QUEUE`). Nicht
  kopieren, sonst laufen zwei Fesseln auseinander.
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
  die Zeitraum-Knöpfe, `dropPastEvents()` und die drei Helfer
  `escapeHtml()`, `uniqueSorted(values, lang)`, `formatDate(iso, lang)`.
- **`filter-ui.js`** (`window.EnduranceFilterUI`, in den Seiten `EFU`) +
  **`filter-ui.css`** – die Bedienung: Filterknöpfe und das schwebende
  Panel mit allem darin (Häkchenlisten, Datums-Baum, Umkreissuche mit
  `places.json`, Distanz-Tabs, Von/Bis). `EFU.create({ state,
  getEvents, t, tv, getLang, onChange, setOrigin })` gibt den
  Bedienteil: `attachButton()` (Liste: eigene Spaltenköpfe),
  `buildButtonBar()` (Karte: beschriftete Knopfreihe), `refresh()`,
  `updateIndicators()`, `close()`, `options()`, `resetTransient()`.

Die beiden Haken sind der ganze Unterschied zwischen den Seiten:
`onChange` zeichnet neu (Liste: Tabelle, Karte: Marker), `setOrigin`
darf mehr tun – die Liste schaltet dort die Entfernungs-Spalte und ihre
Sortierung mit.

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
  Kennung erst beim Absenden einer Fehlermeldung, `endurance-lang` und
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
   kann): **`art2`-Stichwörter für Fahrrad, Schwimmen und Triathlon** –
   `ART2_KEYWORDS_LAUFEN` ist die einzige Liste, alle anderen Sportarten
   bekämen also „–" in der Kategorie-Spalte. Und
   **`ART2_BY_ART1['Triathlon']` fehlt ganz**, das Kategorie-Panel wäre
   für Triathlon leer. Die Distanzkategorien je Sportart
   (`DISTANCE_CATEGORIES`) stehen dagegen schon.
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
   fehlt nur noch die E-Mail-Adresse). Danach in dieser Wirkung:
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

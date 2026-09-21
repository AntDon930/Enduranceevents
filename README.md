# Enduranceevents

[![Tests](https://github.com/AntDon930/Enduranceevents/actions/workflows/ci.yml/badge.svg)](https://github.com/AntDon930/Enduranceevents/actions/workflows/ci.yml)

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
  - `dauer_h` – Dauer in **Stunden** bei zeitlich begrenzten Rennen
    (24-Stunden-Lauf, 6h, 12h). Solche Rennen haben keine feste Strecke:
    gelaufen wird, so weit man in der Zeit kommt. In der Liste erscheint
    die Dauer in derselben Spalte wie die Distanz („24 h" statt
    „42.2 km", siehe `formatLength()` in `events.html`), und im
    Länge-Filter gibt es dafür die Kategorie „Zeitrennen".

    Bewusst ein **eigenes Feld**: eine Dauer in `laenge_km` zu schreiben
    würde den Von/Bis-Filter, die Sortierung und die Distanz-Kategorien
    durcheinanderbringen (was ist „zwischen 10 und 20" bei einem
    24-Stunden-Lauf?). Ist eine Distanz bekannt, hat sie in der Anzeige
    **Vorrang**: beim „24h Mad Chicken Run | Marathon, 42 km" ist das
    „24h" der Name der Veranstaltung, die Zeile selbst aber eine feste
    42-km-Strecke.
  - `wettbewerb` – Bezeichnung der konkreten Strecke innerhalb der
    Veranstaltung (optional, z. B. `"Moslig 8000"` oder `"Halbmarathon"`).
    Veranstaltungen bieten fast immer mehrere Strecken an; jede wird zu
    einem eigenen Eintrag, und dieses Feld sagt, welche gemeint ist (siehe
    „Mehrere Strecken pro Veranstaltung" unten).

    **In der Anzeige nur, wenn es etwas sagt**: Die Quellen benennen einen
    Wettbewerb oft schlicht mit seiner Distanz („50 km") oder deren
    kanonischem Namen („Halbmarathon"). Das steht schon in der
    Längen-Spalte – im Detailbereich erschien es dadurch zweimal („Race
    50 km" über „Length 50 km"), und bei gerundeten Quellenangaben sah es
    nach einem Widerspruch aus (Unterzeile „6 km" über der Spalte
    „5.5 km"). `displayWettbewerb()` in `events.html` blendet solche
    Labels aus; „Laufen", „Wandern", „Moslig 8000" oder „5×5 km Staffel"
    bleiben sichtbar. Von 3417 Labels sind damit 1273 sichtbar.

    Das Feld bleibt dabei **in `events.json` erhalten** – die
    Duplikat-Erkennung braucht es: Über das Label „Halbmarathon" wurde der
    doppelte München-Halbmarathon überhaupt erst gefunden (siehe
    `_name_tokens()`).
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
  pro Kilometer: ab 20 m/km gilt die Strecke als Berg-/Geländelauf und
  bekommt die Kategorie „Trail" (`scraper_lib.art2_from_elevation()`).
  Der „VR Bank – BraunenBerg-Lauf" über 14,6 km mit ca. 400 Hm (27 m/km)
  galt vorher als Straßenlauf. Ein flacher Stadtmarathon liegt bei unter
  5 m/km und bleibt unberührt; eine aus dem Namen erkannte Kategorie
  (Hindernis, Backyard Ultra, …) wird nie überschrieben.

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
  4. **Stadt/Ort** – reine **Umkreissuche**, in dieser Reihenfolge:
     „Aktuellen Standort verwenden" (Browser-Geolocation), darunter ein
     Regler für den Umkreis von **1 bis 200 km**, darunter ein Suchfeld
     für **Ort oder Postleitzahl**. Sobald ein Ausgangspunkt feststeht,
     schaltet sich der Umkreis mit 25 km ein (`RADIUS_DEFAULT_KM`); der
     Chip „Umkreis: 40 km um Fürth ×" entfernt beides wieder. Wird die
     Seite mit `?standort=<Stadt>` aufgerufen (Deep-Link von
     `karte.html`), ist der Ortsfilter beim Laden gesetzt und lässt sich
     über seinen Chip entfernen.

     Das Suchfeld kennt **alle** Orte und Postleitzahlen in Deutschland,
     Österreich und der Schweiz – nicht nur die mit Event (siehe
     „Ortsverzeichnis (places.json)"). Genau darum ging es: Wer in einem
     Ort ohne Rennen wohnt, will trotzdem wissen, was in 40 km Umkreis
     läuft. Die frühere Checkbox-Liste mit den ~2000 Orten aus
     `events.json` ist deshalb entfallen.

     Im Panel steht **nur, was beim Suchen hilft**: Meldungen wie „Kein
     Ort gefunden." oder „Ortsverzeichnis wird geladen…", sonst nichts.
     Ein erklärender Hinweistext und die Quellenangabe zu den Ortsdaten
     standen dort anfangs auch – beides war beim Suchen nur im Weg. Die
     von der Lizenz verlangte Namensnennung (GeoNames, CC BY 4.0) steht
     jetzt in der **Fußzeile von `index.html`** – und soll am Ende ins
     Impressum umziehen, sobald es eines gibt (siehe To-dos in
     `CLAUDE.md`): umziehen, nicht löschen.

     **Was der Regler tut**: Beim Ziehen (`input`) läuft nur die
     Beschriftung mit, gefiltert wird erst beim Loslassen (`change`) –
     sonst baut sich die ganze Tabelle bei jeder Fingerbewegung neu auf.
     Der Regler behält dabei bewusst den Fokus (Pfeiltasten), das Panel
     wird also nicht neu gezeichnet; Stellung und Beschriftung stimmen
     zu dem Zeitpunkt schon.

     **Zur Geolocation**: Der Standort-Button braucht einen sicheren
     Kontext – auf GitHub Pages (HTTPS) und über `http://localhost` geht
     er, über eine nackte `http://`-Adresse oder `file://` lehnen die
     Browser ihn ab; das sagt die Statuszeile dann auch so.

     Ob der Browser den Erlaubnis-Dialog überhaupt zeigt, entscheidet
     allein der Browser – eine Webseite kann ihn nicht erzwingen und
     nicht selbst einblenden. Gefragt wird nur beim *ersten* Mal pro
     Seite; danach merkt sich der Browser die Antwort. Ein „Nicht
     erlauben" wirkt deshalb dauerhaft, und ist die Ortung systemweit
     aus (iOS: Ortungsdienste, oder Safari steht auf „Ablehnen"),
     kommt gar kein Dialog: `getCurrentPosition()` antwortet sofort mit
     Fehlercode 1.

     Genau daran hängt die Unterscheidung im Fehler-Zweig: Kommt
     Fehlercode 1 in **unter 800 ms**, hat der Browser nicht gefragt –
     dann hilft nur die Einstellung, und das Panel blendet eine
     nummerierte Anleitung ein (iOS-Pfade für Apple-Geräte, sonst der
     Hinweis auf das Schloss-Symbol in der Adresszeile) plus den
     Hinweis, dass die Ort-/PLZ-Suche darunter ohne Freigabe
     funktioniert. Dauert die Ablehnung länger, hat der Nutzer den
     Dialog gerade selbst weggetippt – dann fragt der Browser beim
     nächsten Klick wieder, und die Statuszeile sagt genau das. Der
     Knopf wird nach einem Fehlversuch wieder aktiv und heißt dann
     „Standort erneut versuchen". Zeitüberschreitung (Fehlercode 3)
     hat weiterhin einen eigenen Text.

     Wo `navigator.permissions.query({name:'geolocation'})` unterstützt
     wird (Chrome, Firefox – Safari nicht überall, deshalb in
     `try/catch` **und** mit `.catch()`), steht der Hinweis schon beim
     Öffnen des Panels da, statt erst nach einem Klick, der nichts
     bewirken kann. `maximumAge: 300000` erlaubt dem Browser, eine
     Position aus den letzten fünf Minuten direkt zurückzugeben.

     Die iOS-Einstellungen liegen an zwei Stellen, beide müssen stimmen:
     Einstellungen → Apps → Safari → Standort (ältere iOS-Versionen:
     Einstellungen → Safari → Standort) und Einstellungen → Datenschutz
     & Sicherheit → Ortungsdienste → Safari-Websites.

     **Fallstrick, der hier einmal zugeschlagen hat**: Der Erfolgs-
     Callback setzt `state.origin` und ruft `render()`. `render()`
     zeichnet über `ui.refresh()` auch das offene Filter-Panel neu –
     aber nur, wenn der Fokus *nicht* darin liegt (sonst reißt eine
     Eingabe im Namensfeld ab). Der gerade geklickte Standort-Button liegt
     genau dort: das Panel blieb bei „Standort wird ermittelt…" stehen und
     der Umkreis-Regler ausgegraut, obwohl der Standort längst gespeichert
     war. Deshalb `geoBtn.blur()` vor `render()`. Wer an dieser Stelle
     etwas ändert: Jeder Button *innerhalb* eines Filter-Panels, der den
     Filterzustand ändert, braucht dasselbe.
  **Das Panel folgt seinem Spaltenknopf, es schließt sich nicht beim
  Scrollen.** Früher tat es das (`scroll` und `resize` riefen
  `closeFloatingPanel()`), und auf schmalen Bildschirmen war der
  Stadt/Ort-Filter damit **gar nicht zu öffnen**: Die Tabelle ist breiter
  als ein Telefon, die Spalten ab „Stadt/Ort" erreicht man nur durch
  waagerechtes Wischen – und das Scroll-Ereignis von kurz vor dem Tippen
  wird erst *nach* dem Klick zugestellt. Das Panel ging auf und sofort
  wieder zu. Dasselbe beim Verkleinern: Auf Android schiebt die
  Bildschirmtastatur das Fenster zusammen und löst `resize` aus – ein
  Tippen ins Namens- oder Ortssuchfeld hätte das Panel geschlossen,
  bevor der erste Buchstabe drin war.

  Diese ganze Mechanik – Knöpfe, Panel, Panel-Inhalte – steht seit dem
  Umbau in `filter-ui.js`/`filter-ui.css`, weil die Karte dieselben
  Filter bedienbar macht (siehe dort und bei `karte.html`). Beschrieben
  ist sie hier, weil man sie in der Liste zuerst sieht.

  Statt zu schließen positioniert sich das Panel jetzt neu
  (`folgeDemKnopf`, gedrosselt über `requestAnimationFrame`, weil
  Scroll-Ereignisse während eines Schwungs dicht an dicht feuern).
  Geschlossen wird nur, wenn sein Knopf gar nicht mehr zu sehen ist –
  geprüft gegen das Fenster **und** gegen den scrollenden
  Tabellen-Container (`isTriggerVisible`), denn ein waagerecht aus der
  Tabelle geschobener Spaltenkopf liegt zwar noch im Fenster, ist aber
  vom Container abgeschnitten.

  **Der Anker überlebt einen neu gebauten Tabellenkopf.** Ein
  Ausgangspunkt im Stadt/Ort-Filter schaltet die Entfernungs-Spalte zu,
  also ruft `setOrigin()` in `events.html` `buildHeader()` auf – und
  ersetzt dabei jeden Spaltenknopf durch einen neuen. Der alte Knopf, an
  dem das offene Panel hing, war danach aus dem Dokument gelöst; sein
  `getBoundingClientRect()` liefert lauter Nullen, und das Panel klebte
  in der linken oberen Ecke der Seite (vom Nutzer gemeldet, mit Foto).
  Drei Vorkehrungen, alle in `filter-ui.js`:

  1. `attachButton()` übergibt dem neuen Knopf derselben Spalte die
     Ankerrolle, wenn deren Panel gerade offen ist.
  2. `positionFloatingPanel()` und `isTriggerVisible()` prüfen
     `isConnected` – ein abgehängter Knopf verschiebt das Panel nicht
     mehr, es bleibt lieber stehen, wo es ist.
  3. `reposition()` richtet das offene Panel am **Ende** von `render()`
     neu aus. Früher genügte das `refresh()` am Anfang; seit es die
     Entfernungs-Spalte gibt, stehen die Spaltenbreiten dort noch gar
     nicht fest (`table.with-distance` wird erst beim Zeichnen gesetzt),
     der Knopf wandert danach noch um die Breite der neuen Spalte.

  5. **Sportart** – Checkbox-Liste (Laufen/Schwimmen/Fahrrad/Triathlon)
  6. **Kategorie** – Checkbox-Liste, deren Optionen von der Sportart-Auswahl
     abhängen. Zuordnung (als `ART2_BY_ART1` in `filter-ui.js`, dort
     anpassbar – die Liste und die Karte teilen sie sich):
     - *Laufen*: Straße, Trail, Bahn, Hindernis, Backyard Ultra.
       **„Trail" umfasst Trail-, Cross- UND Bergläufe** (vom Nutzer am
       19.09.2026 so entschieden – vorher „Trail/Cross" und daneben
       „Berg"). „Backyard Ultra" trifft „backyard" bzw. „last man
       standing" (gleiche Runde zur gleichen Stunde, bis nur noch eine
       Person weiterläuft); das Stichwort steht in der Prioritätsliste
       **hinter** „Trail" – ein „Backyard Ultra **Trail**" ist ein
       Trailrun, der das Wort nur im Namen trägt – und **vor** der
       Berg-/Höhenmeter-Zeile, damit ein Backyard mit Höhenmeter-Angabe
       ein Backyard bleibt. (Die Kategorie hieß bis zum 19.09.2026
       „Backcountry Ultra" und hatte das Stichwort „backcountry"; das ist
       weg, weil ein Backcountry Ultra ein langer Trailrun ist, kein
       Rundenformat.)
     - *Schwimmen*: Freiwasser, Becken
     - *Fahrrad*: Straße, Zeitfahren, Mountainbike, Gravel, Bahn, Cyclecross
     - *Triathlon*: Straße, Cross, Duathlon, Aquathlon, Swimrun,
       Quadrathlon, Indoor, Backyard Ultra – derselbe Wert wie beim
       Laufen, das Format ist dasselbe (Backyardman Würzburg).
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
  nächstliegende (bevorstehende) Datum zuerst - ein einfacher
  ISO-Textvergleich genügt, weil vergangene Events gar nicht in der
  Liste stehen (siehe „Vergangene Events" unten). Der frühere
  Sonderfall, der sie ans Ende sortierte, ist damit entfallen.

  Die Spaltenbreiten sind fix zugeteilt (Name breiter, Länge schmaler) statt
  gleich verteilt, über `nth-child`-Selektoren im `<style>`-Block von
  `events.html`, dort bei Bedarf anpassbar. `body` hat `min-height: 100vh`,
  damit der Seitenhintergrund immer bis zum unteren Bildschirmrand reicht,
  auch wenn die Tabelle (z. B. bei wenigen Events oder auf sehr hohen
  Bildschirmen) nicht die volle Höhe ausfüllt.

  Aktive Filter erscheinen als Chips direkt neben der Ergebnisanzahl links
  oben (einzeln entfernbar), „Alle Filter zurücksetzen" rechts daneben -
  direkt über der Tabelle - löscht alles auf einmal. Klick auf eine Zeile
  zeigt rechts die Detailansicht.

  **Sortierung**: Jede Spaltenüberschrift ist ein Knopf - erster Klick
  sortiert aufsteigend, der zweite dreht die Richtung, ein Pfeil zeigt
  den Zustand (und `aria-sort` sagt es Vorleseprogrammen). Standard ist
  Datum aufsteigend, also der nächste Termin zuerst. Die Schlüssel stehen
  in `SORT_KEYS` und geben `[Gruppe, Wert]` zurück: Zeilen ohne
  verwertbare Angabe landen immer hinten, unabhängig von der Richtung.
  Bei der Länge gibt es drei Stufen - bekannte Distanz, dann Zeitrennen
  nach Dauer, dann alles ohne beides; Kilometer und Stunden werden nicht
  in eine Zahlenreihe gemischt.

  **Entfernungs-Spalte**: Sobald ein Ausgangspunkt gesetzt ist, erscheint
  hinter Stadt/Ort eine Spalte „Entfernung" (unter 10 km mit einer
  Dezimalstelle, darüber gerundet), und die Liste sortiert von selbst
  danach - solange noch die Standard-Sortierung aktiv ist; eine selbst
  gewählte bleibt unangetastet. Fällt der Ausgangspunkt weg, verschwinden
  Spalte und Sortierung wieder. Die Spaltenbreiten für diesen Fall stehen
  unter `table.with-distance` (`table-layout` ist fix).

  **Veranstaltungen zusammenfassen** (Schalter direkt hinter der
  Trefferzahl – er verändert, wie diese Zahl zu lesen ist): Eine
  Veranstaltung mit sechs Strecken füllt sonst sechs Zeilen. Der Schalter
  bündelt sie nach Name + Datum + Ort zu einer Zeile und zeigt in der
  Länge-Spalte die Spanne („5–42,2 km"). **Voreinstellung: an** – wer die
  Seite zum ersten Mal öffnet, sieht eine Zeile je Veranstaltung (so vom
  Nutzer gewünscht). Schaltet jemand um, merkt sich der Browser das in
  `localStorage` (`endurance-gruppiert`); nur eine solche eigene
  Entscheidung überschreibt die Voreinstellung, ein fehlender Eintrag
  nicht. In der Adresse steht deshalb nur die Abweichung (`gruppiert=0`),
  alte Links mit `gruppiert=1` bleiben gültig. Ein Klick auf die Zeile
  klappt die Strecken auf (Pfeil im runden Feld dreht sich,
  `aria-expanded` sagt es Vorleseprogrammen, und der Block bekommt einen
  Rahmen), ein Klick auf eine Strecke zeigt ihre Details. Die frühere
  Spalte „#" mit der Zahl der Strecken gibt es nicht mehr – sie wurde als
  Durchnummerierung gelesen.

  **Aufgeklappt zeigt die Veranstaltungszeile die erste Strecke selbst.**
  Zwei Strecken sind dann auch zwei Zeilen. Vorher waren es drei: die
  Zusammenfassung blieb stehen und wiederholte mit ihren Marken nur, was
  direkt darunter Zeile für Zeile stand (vom Nutzer gemeldet). Die
  Veranstaltungszeile wechselt daher ihren Inhalt - zugeklappt alle
  Längen als Marken und alle Kategorien, aufgeklappt Wettbewerb, Kategorie
  und Länge der ersten Strecke (`groupRowHtml()` prüft dafür `offen`),
  während `subRowsHtml()` nur noch `rows.slice(1)` ausgibt. Pfeil und
  Anzahl bleiben als Kennzeichen der Veranstaltung, die Schrift wird die
  der Unterzeilen (`tr.group-row.open`), damit die Zeilen einer
  Veranstaltung wie ein Block wirken. `klappeGruppe()` zeichnet deshalb
  jetzt auch die Veranstaltungszeile neu, statt nur den Pfeil zu drehen -
  weiterhin ohne `render()`, es bleibt bei den Zeilen dieser einen
  Veranstaltung.

  **Eine Veranstaltung mit nur einer Strecke lässt sich nicht
  aufklappen**: Die Unterzeile würde Wort für Wort dasselbe zeigen wie die
  Zeile darüber. Solche Zeilen (`tr.group-row.single`, erkannt an
  `istEinzelgruppe()`) bekommen deshalb keinen Pfeil, kein
  `aria-expanded` und kein Aufklapp-Verhalten - ein Klick wählt nur die
  Strecke für den Detailbereich aus. Anstelle des Pfeils steht ein gleich
  breiter Platzhalter (`.chevron-spacer`, 16 px), damit die Namen aller
  Zeilen der Spalte auf einer Linie beginnen. Die Zahl „1" in der
  Anzahl-Spalte bleibt.

  Die Spaltenbreiten stehen als **Klassen** (`.col-name`, `.col-anzahl`,
  …) statt über `nth-child`: die Spalten wechseln je nach Zustand
  (Entfernung nur mit Ausgangspunkt, Anzahl nur beim Zusammenfassen), und
  mit `nth-child` bräuchte jede Kombination ihren eigenen Satz Regeln. Das ist **reine
  Anzeige** - die Daten bleiben eine Zeile pro Strecke (Datenregel 1),
  damit Filter und Duplikat-Erkennung weiter funktionieren. Die
  Ergebnisanzeige zählt dann beides: „810 Veranstaltungen (1413
  Strecken) von 4155 Events".

  **Zum Kalender hinzufügen**: Im Detailbereich steht zwischen dem
  Veranstalter-Link und „Fehler melden" ein Knopf, der drei Wege anbietet
  – **Google Kalender / Gmail** und **Outlook** als Links, **Apple
  Kalender und alles andere** als `.ics`-Datei. Der Eintrag ist
  immer ein **ganztägiger Termin**: eine verlässliche Startzeit liefert
  keine Quelle, und ein ganztägiger Eintrag behauptet keine Uhrzeit, die
  wir nicht kennen. Mehrtägige Veranstaltungen übernehmen ihren ganzen
  Zeitraum.

  **Die `.ics`-Dateien liegen fertig im Repo**, eine je Event unter
  `kalender/` (~4.150 Stück, je ~500 Byte), erzeugt von
  `scripts/build_ics.py` – der Link im Detailbereich zeigt einfach
  dorthin. Das ist der einzige Weg, der auf dem iPhone funktioniert:
  Safari übergibt einen Termin nur an den Kalender, wenn die Datei
  **vom Server** mit `Content-Type: text/calendar` kommt. Drei Versuche,
  das im Browser zu erzeugen, sind am Gerät gescheitert – ein data-URI,
  ein Blob und sogar eine von einem Service Worker erfundene Antwort
  landeten als Download („Unknown.ics", Teilen-Liste ohne Kalender) bzw.
  auf der 404-Seite von GitHub Pages. Der Link trägt deshalb auch
  **kein `download`-Attribut**: das würde das Übergeben an den Kalender
  wieder verbieten.

  Der Dateiname ist `<datum>-<name>-<distanz>-<ort>.ics`. Er wird an
  **zwei** Stellen berechnet – in `build_ics.py` (erzeugt die Dateien)
  und in `events.html` (verlinkt sie); `test_scraper_lib.py` prüft beide
  gegeneinander und lässt dafür den echten JS-Code in `node` laufen. Der
  Ort gehört dazu, weil Name + Datum + Distanz nicht eindeutig sind:
  „TEAG - Legend of Cross - Mühlberg" steht am 31.10.2026 mit 10, 17 und
  30 km je zweimal in den Daten – einmal unter „Mühlberg", einmal unter
  „Drei Gleichen" (Mühlberg ist ein Ortsteil davon). Das frühere
  Beispiel „Königsforst-Marathon" trägt nicht mehr: Dessen zweite
  42,2-km-Zeile lag durch einen Geocoding-Fehler bei Kassel, deshalb
  griff die Duplikat-Erkennung nicht (sie erlaubt 30 km Abstand). Seit
  der Einzelprüfung vom 18.09.2026 sind die beiden zusammengeführt.

  `DTSTAMP` ist absichtlich ein **fester** Zeitstempel und nicht „jetzt":
  sonst änderte jeder Wochenlauf alle 4.150 Dateien, und der Commit wäre
  ein Riesen-Diff ohne inhaltliche Änderung. `build_ics.py` schreibt
  ohnehin nur, was sich unterscheidet, und löscht Dateien, deren Event
  weggefallen ist.

  Ein Detail, an dem solche Links oft scheitern: `DTEND` im
  iCalendar-Format (RFC 5545) und ebenso `dates=` bei Google und `enddt=`
  bei Outlook sind **exklusiv** – das Enddatum muss einen Tag später
  stehen, sonst fehlt der letzte Tag. Der Text in der `.ics`-Datei wird
  maskiert (`icsEscape`) und ab 75 Zeichen gefaltet (`icsFold`), weil
  manche Kalender über lange Zeilen stolpern.

  **Zeitraum-Schnellfilter**: Über dem Jahr/Monat/Tag-Baum stehen vier
  Knöpfe - „Dieses Wochenende", „Nächste 30 Tage", „Nächste 3 Monate",
  „Dieses Jahr". Sie setzen dieselben `selectedDays` wie der Baum (es
  kommt also kein zweiter Filtermechanismus dazu) und merken sich nur das
  Etikett für den Chip; wer danach von Hand einzelne Tage anfasst,
  verliert das Etikett, nicht die Auswahl.

  **Teilbarer Link**: Der vollständige Filterzustand steht in der Adresse
  (`?sportart=Laufen&art2=Trail&zeitraum=m3&sort=laenge_km:desc&…`) und
  wird beim Laden wieder übernommen - **„Suche mit Freunden teilen"** im
  blauen Kopfbereich (unter DE/EN) legt ihn in die Zwischenablage und
  zeigt für knapp zwei Sekunden ein kleines Fenster „✓ Link kopiert!".
  Der Knopf steht dort und nicht in der Werkzeugleiste, weil er die Seite
  als Ganzes betrifft; zwischen Filter-Chips und „Zurücksetzen" ging er
  unter. Geschrieben wird mit
  `history.replaceState`, nicht `pushState`: sonst legte jeder
  Häkchen-Klick einen Eintrag in der Zurück-Geschichte an. Die beiden
  alten Deep-Links (`?sportart=` von der Startseite, `?standort=` von der
  Karte) funktionieren unverändert. Denselben Filterteil der Adresse
  liest und schreibt `karte.html` (`filters.js`), deshalb nimmt der
  „Karte"-Button die Filter mit. Eine **Grenze** gibt es bei den
  Einzeltagen: mehr als 60 ausgewählte Tage stehen nicht in der Adresse
  (sie würde unbrauchbar lang) - genau diese großen Bereiche deckt der
  `zeitraum`-Parameter der vier Knöpfe ab.

  **Chips werden zusammengefasst, nicht aufgezählt.** Ein Klick auf
  „Alle" im damaligen Stadt/Ort-Filter wählte ~2000 Orte aus und schob
  die Tabelle mit „Stadt/Ort: Aachen ×"-Chips aus dem Bild. Diese Liste
  gibt es nicht mehr (der Filter ist heute eine Umkreissuche), die Regel
  gilt aber unverändert für alle Mengen-Filter (Land, Stadt/Ort aus einem
  Kartenlink, Sportart, Kategorie):

  | Auswahl | Chip |
  |---|---|
  | alle vorhandenen Werte | `Stadt/Ort: Alle` |
  | mehr als `MAX_VALUE_CHIPS` (5) | `Stadt/Ort: 12 ausgewählt` |
  | bis zu 5 Werte | ein Chip pro Wert, wie gehabt |

  Das ✕ eines Sammel-Chips löscht den ganzen Filter. Dasselbe gilt für
  das Datum (`Datum: Alle` statt „812 Tage ausgewählt", wenn alle Termine
  gewählt sind) und für die Distanz-Kategorien (`Länge: 8 ausgewählt`).
  Schwellenwert: `MAX_VALUE_CHIPS` in `filters.js`; die Chips selbst baut
  dort `buildChips()`, damit die Karte sie wortgleich anzeigt.

  **Zweisprachig (DE/EN)**: Umschalter oben rechts, geteilt mit
  `index.html` über denselben `localStorage`-Schlüssel. Übersetzt werden
  alle UI-Texte sowie die Werte für Land/Sportart/Kategorie (z. B.
  „Laufen" ↔ „Running"); Event-Namen, Städte und Veranstalter-Links
  bleiben unverändert. Die Übersetzungstabelle `I18N` steht oben im
  `<script>`-Block in `events.html` – dort auch anpassbar/erweiterbar;
  die Chip- und Zeitraum-Texte sowie `VALUE_TRANSLATIONS` stehen in
  `filters.js`, weil die Karte dieselben braucht.

  **Distanz-Schnellauswahl bei „Länge"**: Die Sportart-Tabs im Länge-Filter
  folgen dem Sportart-Filter: ist dort z. B. nur „Laufen" ausgewählt, zeigt
  „Länge" direkt (ohne Tabs) nur die Laufen-Kategorien; bei mehreren gewählten
  Sportarten stehen nur deren Tabs zur Wahl; ist keine Sportart gefiltert,
  stehen alle vier Tabs zur Verfügung. Wird die Sportart-Auswahl später
  eingeschränkt, werden nicht mehr passende Distanz-Auswahlen automatisch
  entfernt (sonst würde die Länge-Auswahl „ins Leere laufen"). Kategorien:
  - **Zeitrennen** (in jeder Sportart, die solche Events hat): trifft
    alles mit gesetztem `dauer_h` – 6-, 12-, 24-Stunden-Läufe. Die
    Kategorie erscheint im Panel nur, wenn die gewählte Sportart
    überhaupt ein zeitlich begrenztes Event enthält; eine Auswahl mit
    garantiert 0 Treffern wäre nur Ballast.
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
  `DISTANCE_CATEGORIES`/`DISTANCE_CATEGORY_LABELS` in `filters.js` –
  dort anpassbar, falls andere Schwellenwerte gewünscht sind (die Karte
  filtert mit denselben Tabellen).
- `karte.html` – Kartenansicht (Leaflet + OpenStreetMap-Kacheln, keine
  API-Keys nötig) mit gebündelten Markern und einem Marker pro
  **Standort** (nicht pro Event):
  ein Ort mit z. B. 10 Events zeigt einen einzelnen Marker mit der Zahl
  "10" statt zehn übereinanderliegenden Punkten. Klick auf einen Marker
  öffnet ein Popup mit Ortsname, Länderangabe und einem Link „N Events
  in der Liste anzeigen", der zu `events.html?standort=<Ort>` führt und
  dort automatisch den Standort-Filter auf genau diesen Ort setzt. Erreichbar
  über den „Karte"-Button in `events.html` (auf der Startseite gibt es
  bewusst keinen Kartenlink).

  **Die Karte hat dieselben Filter wie die Liste – und man kann sie dort
  auch bedienen.** Über der Karte steht eine Leiste mit denselben sieben
  Filterknöpfen (Name, Datum, Land, Stadt/Ort, Sportart, Kategorie,
  Länge), die dieselben Panels öffnen wie die Spaltenköpfe der Liste –
  es ist derselbe Code (`filter-ui.js`, `filter-ui.css`), nicht ein
  Nachbau. Darunter stehen die gesetzten Filter als Chips.
  - **Ein Filter gilt für beide Seiten**: Beide schreiben ihn in
    dieselbe Adresse (`filters.js`), und die Knöpfe „Karte" und „Liste"
    nehmen sie mit. Wer auf der Karte „Land: Schweiz" wählt und dann auf
    „Liste" tippt, sieht dort dieselbe Auswahl – und umgekehrt.
  - Damit stehen auf der Karte nur die Marker der Events, die auch in
    der Liste stünden – vorher zeigte die Karte immer alle ~4.100.
  - Die Knöpfe färben sich blau, sobald ihre Spalte filtert
    (`.col-filter-btn.has-filter`), genau wie in der Tabelle. Auf der
    Karte tragen sie zusätzlich ihren Namen: ohne Spaltenkopf daneben
    wüsste sonst niemand, welcher Knopf welcher Filter ist.
  - Das ✕ eines Chips und **„Alle Filter zurücksetzen"** wirken sofort
    auf der Karte und schreiben die Adresse mit (`history.replaceState`).
    Ohne Filter bleibt die Chip-Zeile einfach leer
    (`.active-chips:empty { display: none }`) – die Knöpfe bleiben
    stehen, sonst könnte man nichts mehr auswählen.
  - **Die Marker werden gebündelt** (Leaflet.markercluster, 34 KB von
    unpkg): Ohne das lagen bei 1.486 Orten so viele Marker
    übereinander, dass Deutschland auf dem Handy eine blaue Wolke war –
    und mit den geplanten >20.000 Events wäre die Karte unbedienbar.
    Jetzt steht weit draußen ein Bündel je Region, ein Klick klappt es
    auf (aus 6 Zeichen werden 15, dann die einzelnen Orte), ab
    Zoomstufe 11 (`disableClusteringAtZoom`) steht jeder Ort für sich.
    Drei Dinge daran sind bewusst so:
    - **Die Zahl im Bündel ist die Summe der Events, nicht der Orte.**
      Jeder Marker trägt seine Event-Zahl in `options.eeCount`,
      `clusterIcon()` addiert sie. Sonst widerspräche die Karte ihrer
      eigenen Kopfzeile („4.143 Events an 1.486 Orten") – der Rauchtest
      prüft die Summe deshalb gegen genau diese Zeile.
    - **Ausgangspunkt und Umkreis liegen in einer zweiten Ebene**
      (`overlayLayer`), nicht in der Bündel-Ebene: sonst verschwände der
      rote Punkt beim Herauszoomen in einem Bündel.
    - **Fehlt das Plugin** (unpkg nicht erreichbar, Netzsperre), fällt
      `createMarkerLayer()` auf eine einfache `L.layerGroup` zurück –
      dann liegen die Marker wieder einzeln da, statt dass die Karte
      leer bleibt. Vom Plugin wird nur `MarkerCluster.css` geladen
      (Bewegung beim Auf- und Zuklappen); das Aussehen steht als
      `.cluster-badge` in `karte.html`, `MarkerCluster.Default.css`
      braucht es dafür nicht.
  - Ein **Umkreis-Filter wird gezeichnet**: der Ausgangspunkt als roter
    Punkt (`.origin-dot`), der Umkreis als Kreis. Erst damit ist zu
    sehen, *warum* außerhalb keine Marker stehen; der Kartenausschnitt
    richtet sich dann nach dem Kreis, sonst nach den Markern.
  - Die Hinweiszeile oben links zählt mit: „699 von 4155 Events an 324
    Orten", bzw. „Kein Event entspricht den Filtern."
  - Der „Liste"-Button und die Popup-Links nehmen die Filter mit zurück
    (das Popup setzt zusätzlich seinen Ort). Die Ansichts-Parameter der
    Liste (`sort`, `gruppiert`) versteht die Karte nicht, sie reicht sie
    aber unverändert weiter – der Weg Liste → Karte → Liste verliert die
    Ansicht also nicht. Nur `sort=entfernung` verwirft die Liste, wenn
    kein Ausgangspunkt (mehr) gesetzt ist: ohne einen gibt es die
    Entfernungs-Spalte nicht, und die Liste stünde ohne sichtbare
    Sortierung da.
- `filters.js` – der **gemeinsame Filterzustand von `events.html` und
  `karte.html`**: Distanzkategorien, Umkreis-Grenzen, die Prüfung
  „trifft dieses Event die Filter?" (`matchEvent`), das Lesen und
  Schreiben der Filter-Parameter in der Adresse (`readParams`/`toParams`),
  die Beschriftung der Filter-Chips (`buildChips`) samt der dafür nötigen
  Texte und Wertübersetzungen, die Zeitraum-Knöpfe und
  `dropPastEvents()`. Vorher stand das alles im Inline-Skript von
  `events.html`, und die Karte kannte gar keine Filter; ein zweiter
  Nachbau in `karte.html` wäre mit der Zeit auseinandergelaufen (eine
  Kategorie hier geändert, dort vergessen). Was **nur** die Liste
  betrifft – Spalten, Sortierung, Zusammenfassen, der Detailbereich –
  bleibt in `events.html`. Dazu kommen drei kleine Helfer, die überall
  gebraucht werden: `escapeHtml()`, `uniqueSorted(values, lang)` und
  `formatDate(iso, lang)` (die Sprache als Parameter – das Modul kennt
  den Umschalter der Seite nicht).

  Zwei Fallen dabei: Die Seiten mischen die Texte aus `filters.js` und
  `filter-ui.js` mit
  `Object.assign(I18N.de, EF.I18N.de, EFU.I18N.de)` in ihr eigenes
  `I18N`-Objekt (`t()` bleibt dadurch unverändert), und die Kurzformen in
  `events.html`, die auf `state` zugreifen (`matchesDistanceCategory`,
  `haversineKm`, `dropPastEvents`), sind **Funktions-Deklarationen statt
  `const`** – hochgezogen und damit auch vor ihrer Textstelle aufrufbar
  (die Temporal-Dead-Zone-Falle, die dieses Skript schon zweimal
  erwischt hat).
- `filter-ui.js` / `filter-ui.css` – die **Filter-Bedienelemente beider
  Seiten**: die Filterknöpfe und das schwebende Panel mit allem, was
  darin steckt (Häkchenlisten, Jahr/Monat/Tag-Baum samt
  Zeitraum-Knöpfen, Umkreissuche mit Standort-Knopf, Regler und
  Ortssuche über `places.json`, Distanz-Tabs und Kategorien,
  Von/Bis-Felder). `EnduranceFilterUI.create({ state, getEvents, t, tv,
  getLang, onChange, setOrigin })` gibt einen Bedienteil zurück:
  - `attachButton(btn, col)` hängt einen selbst gebauten Knopf an ein
    Panel – so benutzt die Liste ihre Spaltenköpfe weiter;
  - `buildButtonBar(container)` baut die beschriftete Knopfreihe der
    Karte;
  - `refresh()`, `updateIndicators()`, `close()`, `options(key)` und
    `resetTransient()` für alles, was die Seiten beim Neuzeichnen und
    Zurücksetzen brauchen.

  Die beiden Haken sind der ganze Unterschied zwischen den Seiten:
  `onChange` zeichnet die Seite auf ihre Art neu (Liste: Tabelle, Karte:
  Marker), `setOrigin` darf mehr tun, als den Ausgangspunkt zu setzen –
  die Liste schaltet dort die Entfernungs-Spalte und ihre Sortierung mit.
  Das Panel liegt bei `z-index: 1000`: über den Leaflet-Bedienelementen
  der Karte (800), unter dem Anmelde-Fenster (2000) und der Kurzmeldung
  (3000).
- `scripts/stamp_assets.py` – hängt an `filters.js`, `filter-ui.js` und
  `filter-ui.css` in allen HTML-Dateien einen Inhalts-Stempel
  (`?v=<8 Hex des SHA-256>`).

  **Warum das nötig ist** (einmal teuer gelernt): GitHub Pages liefert
  jede Datei mit `Cache-Control: max-age=600`. Ein Browser kann deshalb
  die *neue* `events.html` mit einer bis zu zehn Minuten *alten*
  `filters.js` kombinieren. Nach dem Auslagern der Filterlogik fehlte in
  der alten Datei `EF.uniqueSorted`; das Inline-Skript brach in seiner
  ersten Zeile ab (`readUrlState()`), und die Seite blieb **leer** – nur
  der blaue Kopfbereich stand da. Mit dem Stempel ändert sich die Adresse
  der Datei, sobald sich ihr Inhalt ändert, und der Browser muss sie neu
  holen.

  Nach jeder Änderung an einer der drei Dateien also
  `python3 scripts/stamp_assets.py` – `scripts/test_scraper_lib.py`
  prüft die Stempel mit (`--check` macht dasselbe einzeln) und nennt den
  Befehl, wenn etwas nicht passt.

  Dazu gibt es in beiden Seiten eine **Notbremse**: Fehlen `EF`, `EFU`
  oder eine erwartete Funktion daraus, steht im Kopfbereich „Bitte neu
  laden" mit dem Hinweis, dass der Browser eine veraltete Datei
  gespeichert hat (auf iPhone/iPad: Tab schließen und neu öffnen) –
  statt einer leeren Seite ohne jede Erklärung.
- `places.json` – Ortsverzeichnis für die Umkreissuche: alle Orte und
  Postleitzahlen aus Deutschland, Österreich und der Schweiz, auch die
  ohne Event. Wird von `scripts/build_places.py` aus GeoNames-Daten
  gebaut und von `events.html` erst beim Öffnen des Stadt/Ort-Filters
  nachgeladen (siehe „Ortsverzeichnis (`places.json`)").
- `scripts/build_places.py` – baut ebendiese Datei.
- `scripts/review_reports.py` – der Ablauf für die Fehlermeldungen aus
  der Liste (siehe „Fehler melden" unten): bündelt sie pro Strecke,
  legt daraus Vorschläge an und schreibt sie erst **nach Bestätigung**
  in `scripts/manual_overrides.json`.
- `.github/workflows/pages.yml` – Deployt die Seite automatisch auf
  GitHub Pages bei jedem Push auf diesen Branch.

## Ortsverzeichnis (`places.json`)

Die Umkreissuche in `events.html` braucht einen Ausgangspunkt, und zwar
auch für Orte **ohne** Event. `places.json` liefert ihn: ~32.600 Orte mit
Koordinaten und Postleitzahlen aus Deutschland, Österreich und der
Schweiz (~1,4 MB, gzip-komprimiert etwa 540 KB).

Die Datei wird **erst geladen, wenn jemand den Stadt/Ort-Filter öffnet** –
nicht beim Seitenaufruf. Wer die Liste nur nach Datum durchsieht, lädt
sie nie.

Gebaut wird sie von `scripts/build_places.py` aus zwei GeoNames-Dateien
(CC BY 4.0; die Namensnennung mit Link steht in der Fußzeile von
`index.html` – wer die Datei ersetzt, lässt sie bitte dort stehen):

```bash
python3 scripts/build_places.py          # lädt, baut, schreibt places.json
```

Ein Lauf dauert ein paar Sekunden plus Download (~11 MB, landet im
ignorierten `.geonames-cache/`). Das Skript läuft **nicht** im
Wochen-Workflow mit: Ortsnamen und Postleitzahlen ändern sich praktisch
nie, ein Lauf pro Jahr genügt.

**Was beim Bauen passiert** (die Fälle, die Arbeit gemacht haben):

- **Ein Eintrag je Ort, nicht je Postleitzahl.** Berlin steht ~190-mal in
  der PLZ-Datei; zusammengefasst wird auf Name + Bundesland, die
  Koordinate ist der Mittelpunkt aller Bezirke.
- **Großempfänger raus.** Die deutsche Post vergibt eigene
  Postleitzahlen an Behörden und Konzerne; im Ortsfeld steht dann
  „Finanzamt Fürth" oder „Mercedes-Benz Vertrieb NFZ GmbH". Erkannt wird
  das über eine Rechtsform im Namen **und** über den Abgleich mit dem
  GeoNames-Gazetteer: Was dort im Umkreis von 30 km keine Entsprechung
  hat, ist kein Ort. Geprüft wird dabei auch der *Anfang* des Namens,
  denn viele Einträge heißen „Gemeinde Ortsteil" („Hamburg Stellingen") –
  das Ende zu prüfen wäre falsch, sonst holt „Fürth" das Finanzamt
  wieder herein.
- **Dieser Abgleich gilt nur für Deutschland** (`ORTSBEZUG_PRUEFEN`).
  Österreich und die Schweiz führen echte Ortschaften in ihren
  PLZ-Dateien, und viele kleine Weiler (Kohlergraben, Abländschen,
  Jungfraujoch) fehlen schlicht im Gazetteer – die Prüfung hätte dort
  über 1000 richtige Orte gelöscht.
- **Rechtsform nur als ganzes Wort.** Ein simples „AG" als Zeichenkette
  traf „Bad **Ag**lasterhausen" und die Schweizer Gemeinden mit
  Kantonskürzel („Wohlen AG", „Reinach AG"). Die Endungsregel („Deutz
  AG", „Eppendorf SE") läuft deshalb ebenfalls nur für Deutschland.
- **Verwaltungseinheiten zählen als Beleg mit.** Sie auszuschließen
  hätte zwar „Kreis Borken" erwischt, aber auch 663 echte Gemeinden
  mitgerissen, die im Gazetteer nur als Gemeinde stehen (Crinitzberg,
  Nuthe-Urstromtal, Ammersbek). Ein Kreisname zu viel in der Auswahl ist
  harmlos – seine Koordinaten stimmen –, ein fehlender Wohnort nicht.
- **Einwohnerzahl nur zur Sortierung.** Wer „Mün" tippt, will München
  sehen und nicht Münchendorf. Zugeordnet wird sie über Namen und Nähe,
  nicht über Verwaltungscodes: die deutsche PLZ-Datei führt mal „01",
  mal „BY" als admin1. Indiziert werden auch die fremdsprachigen Namen –
  München heißt im Gazetteer „Munich", Wien „Vienna". Regierungsbezirke
  (ADM2) bleiben außen vor, sonst erbt Arnsberg die 3,5 Millionen seines
  Bezirks und steht über Berlin.
- **Gleichnamige Nachbarn verschmelzen.** Postleitzahlbezirke halten
  sich nicht an Landesgrenzen: die PLZ 22113 liegt teils in Hamburg,
  teils in Schleswig-Holstein – „Hamburg" stand deshalb zweimal in der
  Liste, 4 km auseinander. Zwei echte „Neustadt" 200 km auseinander
  bleiben dagegen getrennt.

**Format** (Arrays statt Objekte, das spart rund ein Drittel):

```json
{"quelle": "GeoNames …", "erstellt": "2026-09-16",
 "laender": ["DE","AT","CH"], "regionen": ["Bayern", …],
 "orte": [["München", 0, 0, 48.144, 11.56, 1505005, "80331 80333 …"], …]}
```

Die Reihenfolge der `orte` ist Teil des Datenformats: absteigend nach
Einwohnerzahl. `searchPlaces()` in `events.html` sortiert nur nach
Trefferart (PLZ, Namensanfang, Wortanfang, irgendwo im Namen) und
verlässt sich innerhalb einer Trefferart auf diese Reihenfolge.

**Suchschlüssel**: `normalisiere()` in `build_places.py` und
`normalizePlaceText()` in `events.html` müssen dasselbe tun – klein,
ohne Umlaute („muenchen"), ohne Akzente, und „Sankt" = „St.", sonst
findet „Sankt Anton am Arlberg" den Ort nicht, der in den Daten
„St. Anton am Arlberg" heißt. Beide Seiten werden von
`test_scraper_lib.py` abgedeckt.

## Eigene Events hinzufügen

Einfach `events.json` um weitere Objekte im gleichen Format ergänzen und
committen – die Seite liest die Datei bei jedem Aufruf neu ein.

## Veranstalter: kein eigenes Feld, sondern Vorschläge in der Suche

Die Frage war, ob man nach Veranstalter filtern können sollte (Ironman,
Challenge …). Ausgezählt über die 2.374 Veranstaltungen: Die größte
Serie hat **21** Einträge, nennenswert sind rund elf – Wings for Life
World Run 21, Ahmadiyya Charity Walk 18, Muddy Angel Run 13, Rats-Run 9,
Fun & Erlebnis Marathons 8, Ironman 7, XLETIX Challenge 6, SportScheck
RUN 6, HYROX 5, Spartan 3, Obstacle City Run 3. „Sparkasse" (30) und
„Stadtwerke" (6) sind Sponsoren, keine Veranstalter; „Backyard" (21) ist
ein Format.

Für elf Serien eine achte Spalte einzuführen wäre teuer: Die
Werkzeugleiste muss auf 1024 px in eine Zeile passen (siehe
CLAUDE.md). Stattdessen schlägt die Mastersuche vor, was in den Daten
steht – „Iron" bringt „Ironman (7)". Details und die Tempo-Messung in
CLAUDE.md unter „Die Mastersuche schlägt Serien und Orte vor".

## Datenqualität

Elf Mechanismen sorgen dafür, dass nur sinnvolle, korrekt kategorisierte
und eindeutige Events in `events.json` landen:

> **Die Einzelprüfung von 400 Events (18.09.2026, in zwei Durchgängen)**
> hat mehrere davon
> hervorgebracht bzw. geschärft und ist in `CLAUDE.md` unter „Was die
> Einzelprüfung von 200 Events gelehrt hat" im Detail festgehalten -
> mit den drei Fällen, in denen sich die *Prüfregel* geirrt hat und
> nicht die Daten, und mit der „Verbesserung", die 57 richtige
> Einordnungen zerstört hätte. Lesen, bevor jemand die nächste
> naheliegende Regel einbaut – und die drei Lektionen des zweiten
> Durchgangs, darunter ein Frontend-Fehler, den eine Datenänderung
> aufgedeckt hat.

- **Vergangene Events werden entfernt** (`scraper_lib.filter_past()` beim
  Einsammeln, `clean_events.drop_past_events()` rückwirkend für die
  bestehende Datei). Die Kalender der Quellen führen abgelaufene Termine
  teils monatelang weiter; ohne diesen Schritt sammelt sich Vergangenheit
  in der Liste an. Drei Details:
  - Maßgeblich ist das **Ende** der Veranstaltung (`datum_ende`, sonst
    `datum_start`) - ein dreitägiges Etappenrennen, das gestern begonnen
    hat, läuft noch und bleibt bis zu seinem letzten Tag.
  - Der **heutige Tag bleibt immer drin**.
  - Ein Event mit fehlendem oder unlesbarem Datum wird **nicht** gelöscht,
    sondern behalten - dieselbe Linie wie bei den Distanzen weiter unten:
    nicht auf Unsicherheit hin löschen.

  Zusätzlich filtern `events.html` und `karte.html` beim Laden
  (`dropPastEvents()`): `events.json` wird nur **einmal pro Woche**
  aufgeräumt, ohne den Filter stünden dazwischen bis zu sieben Tage
  Vergangenheit in der Liste. `clean_events.py --today YYYY-MM-DD` setzt
  den Stichtag für Tests von Hand.
- **Die Sportart aus dem Wettbewerbs-Label**
  (`clean_events.fix_fremde_sportart_im_wettbewerb()`). Nennt das Label
  ausdrücklich eine andere Sportart als die Veranstaltung („Rad 100 km"
  beim „Drei Talsperren Marathon"), ist das die Angabe der Quelle
  selbst - kein Raten. Abgegrenzt wird gegen die Triathlon-Teilstrecke
  über die **Verbform** („21,5 km Radfahren" ist eine Etappe), und
  geprüft wird die ganze Veranstaltung, nicht die einzelne Zeile. Ein
  `art1 == "Triathlon"` wird nie überschrieben. Details in `CLAUDE.md`,
  Datenregel 12.
- **Zwei Rennen in einer Zeile werden geteilt**
  (`scraper_lib._trenne_doppelte_distanzen()`): „15 km / 21 km
  Crosslauf" sind zwei Wettbewerbe. Vorher nahm `guess_distance_km()`
  die größere Zahl, und der 15-km-Lauf fehlte ganz. Aufteilungen
  derselben Strecke („19 km (14 + 5 km)") bleiben unangetastet.
  Details in `CLAUDE.md`, Datenregel 13.
- **Dauer statt Distanz bei Zeitrennen**
  (`scraper_lib.parse_duration_h()`, nachgetragen von
  `clean_events.fill_duration()`). Erkannt werden „24-Stunden-Lauf",
  „6h", „12 Stunden", „24 hours"; plausibel sind 1–72 Stunden. Zwei
  Fehlerquellen sichert die Erkennung ausdrücklich ab, beide aus echten
  Daten:
  - **„229 hm" sind Höhenmeter**, keine 229 Stunden (negativer Lookahead
    hinter dem „h").
  - **„Zeitlimit: 6 Stunden" ist eine Zielschlusszeit** und macht aus
    einem Marathon kein 6-Stunden-Rennen. Steht „Zeitlimit", „Karenz",
    „Cut-off", „Startzeit" o. Ä. kurz davor, wird der Treffer verworfen.

  Ein „E2H10K Ultratrail" ergab in einem Probelauf 2 Stunden – seither
  darf vor der Zahl kein Buchstabe stehen. Ein **Umrechnungssatz** wie
  „6,708 km pro Runde; 24 Stunden ergeben 100 Meilen" ist ebenfalls keine
  Zeitvorgabe (er beschreibt das Backyard-Format) und wird verworfen.

  **Nennt ein Wettbewerb eine Dauer, ist eine km-Angabe daneben die
  Rundenlänge** und wird verworfen: „24h Solo auf einer 2km
  MotoCross-Strecke mit je 60HM (2km)" ergibt 24 h und *keine* 2 km.
  Vorher entstand daraus ein 2-km-Eintrag, den die 5-km-Mindestdistanz
  anschließend verwarf – deshalb fehlten die vier 24h-Wettbewerbe des
  Mad Chicken Run in der Liste, obwohl die Quelle sie ausweist.

  Bei **Backyard Ultras** gilt dasselbe rückwirkend
  (`clean_events.clear_backyard_lap_km()`): eine Distanz bis 10 km ist
  auf so einer Zeile die Runde und wird entfernt (18 Einträge standen mit
  „7 km" bzw. „6,7 km" in der Liste – wer nach „5–10 km" filterte, fand
  Rennen, bei denen man 200 km läuft). Die Länge zeigt dann „–", oder die
  Dauer, wenn das Rennen begrenzt ist. Größere Angaben (34/67/80 km)
  werden **nur gemeldet**, nicht angetastet – bis auf „Murr BackYard 12h"
  (67 und 34 km), der per `manual_overrides.json` auf 12 h ohne Distanz
  steht; seine beiden Zeilen sind dadurch zu einer verschmolzen. Offen
  bleibt „RET-Team Backyard 80 km".

  Ein Override darf dafür jetzt auch `dauer_h` und `wettbewerb` setzen,
  und **`null` löscht ein Feld** (siehe `_readme` in
  `scripts/manual_overrides.json`). Nachgetragen wird die Dauer
  außerdem nur bei Einträgen **ohne** Distanz (Begründung siehe
  `dauer_h` oben), und ein Zeitrennen fällt nicht der
  5-km-Mindestdistanz zum Opfer: beim 24-Stunden-Lauf auf einer
  1-km-Runde ist die Rundenlänge keine Wettkampfdistanz.
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
  ohne eine bewusste Reihenfolge (Hindernis → Trail → Backyard →
  Berg/Höhenmeter → Cross → Bahn → erst zuletzt Straße/Marathon/
  Stadtlauf) hätte die generische Straße-Regel zuerst zugetroffen und
  das Event fälschlich als Straßenlauf statt als Geländelauf eingestuft
  (echter, mit realen Daten verifizierter Bug).
- **"Trail", "Cross" und "Berglauf" sind EINE Kategorie: "Trail".** Alles
  drei beschreibt einen Geländelauf; die Quellen nennen dieselbe Strecke
  mal "Crosslauf", mal "Trail", mal "Berglauf", und wer sie
  auseinanderhalten will, rät. Erst zu "Trail/Cross" zusammengefasst, am
  19.09.2026 auf Wunsch des Nutzers um "Berg" erweitert und in "Trail"
  umbenannt. Die drei Stichwort-Zeilen der Prioritätsliste bleiben
  getrennt, weil das backyard-Stichwort dazwischen steht (siehe oben).
  Bereits gespeicherte Werte zieht `clean_events.merge_art2()` nach
  (auch "Backcountry Ultra"/"Backyard" → "Backyard Ultra"); der Schritt
  ist je Sportart definiert und idempotent, "Cross" beim Triathlon und
  "Cyclecross" beim Fahrrad bleiben unangetastet.
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

  **Ein fünfter Weg zum Namens-Treffer** kam dazu, als die neue
  CI-Prüfung („passt `kalender/` zu `events.json`") einen Doppeleintrag
  aufdeckte: Der *SAARathon* stand am 11.10.2026 zweimal mit 42,2 km in
  den Daten – einmal mit „42,195 km Weltkulturerbe-Marathon" und der
  offiziellen Seite, einmal ohne Wettbewerb und mit einem Portallink.
  „SAARathon" ist **ein** Wort, also zu kurz für die Teilmengen-Regel
  (die verlangt mindestens zwei, damit nicht schon „marathon" allein
  reicht), und gegen die lange Wettbewerbs-Bezeichnung reichte die
  Ähnlichkeit nicht. Jetzt gilt zusätzlich: **gleicher
  Veranstaltungsname** (ohne den Wettbewerb gerechnet) **und höchstens
  eine Seite nennt einen Wettbewerb und dieselbe Sportart**. Beide
  Zusatzbedingungen sind nötig – nennen *beide* einen Wettbewerb, ist
  das Label das Unterscheidende („10 km Lauf" gegen „10 km Nordic
  Walking"), und ein Lauf- und ein Wander-Wettbewerb über dieselbe
  Strecke sind zwei Einträge (Datenregel 1), kein Duplikat. Über den
  ganzen Bestand trifft die Regel genau dieses eine Paar (4.155 → 4.154
  Events); drei Regressionstests halten sie fest.
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
entfernt zu kurze Laufevents **und alle Events, die bereits vorbei sind**,
führt Duplikate zusammen und
**vereinheitlicht die Namen innerhalb einer Veranstaltung**. Zum Schluss
wird nach Datum sortiert (kleine Git-Diffs). Das Skript ist idempotent –
ein zweiter Lauf ändert nichts mehr.

```bash
python3 scripts/clean_events.py --dry-run   # nur Bericht, nichts ändern
python3 scripts/clean_events.py             # events.json aufräumen
```

#### Namen innerhalb einer Veranstaltung

Eine Veranstaltung steht mit je einem Eintrag pro Strecke in der Liste.
Kommen diese Einträge aus verschiedenen Quellen, tragen sie
unterschiedliche Schreibweisen desselben Namens – beim Münchner Marathon
etwa „MARATHON MÜNCHEN" (42,2 km) neben „Marathon München by Brooks"
(21,1 und 10 km). In der Liste sah das nach drei Veranstaltungen aus.

`unify_event_names()` gibt allen Einträgen einer Veranstaltung denselben
Namen. Die Auswahl in der Reihenfolge ihrer Priorität:

1. **Nicht durchgehend GROSSGESCHRIEBEN** – eine Mehrheit darf das nicht
   durchsetzen.
2. **Häufigkeit in der Gruppe** – die Quellenmehrheit entscheidet den
   häufigsten Streitfall, nämlich Auflagen-Nummer vorhanden oder nicht
   („20. Lauf in den Herbst" gegen „Lauf in den Herbst"). Es wird bewusst
   *nicht* versucht, die Nummer generell zu entfernen oder zu ergänzen –
   das wäre eine inhaltliche Änderung, keine Vereinheitlichung.
3. **Sinnvolle Länge, dann länger** – ein 108 Zeichen langer „Name", der
   die ganze Ausschreibung wiedergibt, verliert gegen „Wiesent
   Challenge"; darunter trägt der längere Name meist mehr Information.
4. **Alphabetisch** als letzter Anker, damit das Ergebnis reproduzierbar
   und der Lauf idempotent ist.

Zwei Dinge sind ausdrücklich *keine* Auswahlkriterien, sondern
**Reparaturen** am Gewinner:

- **Formatierung** (`tidy_name()`, auf alle Namen angewendet): mehrfache
  Leerzeichen, Rand, fehlendes Leerzeichen nach der Nummer
  („37.Bessunger Merck-Lauf" → „37. Bessunger Merck-Lauf").
- **Umlaute/ß** (`repair_umlaut_spelling()`): „Bädleslauf" ist richtig und
  „Baedleslauf" falsch, unabhängig von der Häufigkeit. Ersetzt wird nur
  der Text *nach* der Auflagen-Nummer, und nur wenn er sich vom Gewinner
  ausschließlich in der Umschrift unterscheidet. Zwei einfachere Ansätze
  sind vorher gescheitert: „enthält Umlaut" als allgemeines
  Qualitätsmerkmal ließ „Wiesent Challenge" gegen den 108-Zeichen-Namen
  verlieren, nur weil darin „Straßenlauf" vorkam; und ein Zusammenführen
  über die gefaltete Form griff nicht, sobald sich die Varianten
  zusätzlich in der Nummer unterschieden.

**Zusammenführen und Vereinheitlichen bedingen sich gegenseitig** und
laufen daher in einer Schleife bis zum Fixpunkt (`MAX_MERGE_PASSES`): Nach
dem Zusammenführen ändern sich die Mehrheiten, und umgekehrt lässt ein
vereinheitlichter Name zwei Einträge erst als Duplikat erkennbar werden.
Ein einzelner Durchlauf war nicht idempotent.

Events mit einem Eintrag in `manual_overrides.json` werden **nicht**
umbenannt – die Schlüssel dort beginnen mit dem Namen, ein Umbenennen
würde den Override unwirksam machen. Das betrifft aktuell 12 von 4291
Einträgen, die dadurch zwei Schreibweisen behalten.

### Tests bei jedem Push (GitHub Actions)

`.github/workflows/ci.yml` prüft bei jedem Push und jedem Pull Request
genau das, was vor einem Commit ohnehin laufen soll. Vorher lief beim
Push nur der Pages-Deploy – eine kaputte `events.html` wäre unbemerkt
live gegangen.

Zwei Jobs, damit auf einen Blick zu sehen ist, *was* kaputt ist:

- **Regressionstests** (Sekunden, kein Netz, kein Browser):
  `test_scraper_lib.py` (Datenregeln, Dedupe, Zeitrennen,
  Kalender-Dateinamen gegen den echten JS-Code, `node --check` über alle
  Inline-Skripte, die `?v=`-Stempel), dazu zwei Fragen, die nur im
  Zusammenspiel auffallen: **ist `clean_events.py` idempotent**
  (verglichen werden erster und zweiter Lauf – nicht der committete
  Stand mit dem ersten Lauf: das war der erste Versuch und schlug schon
  am nächsten Tag fehl, weil Aufräumen vergangene Events entfernt und
  die committete Datei damit zu Recht verändert)
  und **passt `kalender/` zu `events.json`** (die `.ics`-Dateien liegen
  fertig im Repo, siehe „Zum Kalender hinzufügen"). Genau diese zweite
  Prüfung hat beim Einbauen 490 veraltete Dateien gefunden – der
  Trail/Cross-Umbau war in `events.json`, aber nicht in den
  Kalenderdateien.
- **Rauchtest im Browser**: `smoke_test_frontend.py` mit Playwright und
  Chromium (~1 Minute Einrichtung, deshalb getrennt).

**Keine Scraper-Läufe in der CI**: Die Quellen sollen nicht bei jedem
Push abgerufen werden (Höflichkeit und robots.txt); Daten aktualisiert
allein `update-events.yml`. Das Repository ist öffentlich,
Actions-Minuten sind dafür kostenlos.

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

### Quellen für den großen Datenlauf (Stand 21.09.2026)

Kandidaten für die geplanten 20.000+ Events, gesammelt per Websuche am
21.09.2026 und mit der `robots.txt` jeder Seite abgeglichen (live
abgerufen). **Nichts davon wird gescraped, bevor der Nutzer die Quelle
freigibt** und die Nutzungsbedingungen gelesen sind – die vier
übersprungenen Quellen oben zeigen, warum. Quellen, die den Abruf
sperren oder ausdrücklich verbieten, stehen auf Wunsch des Nutzers
NICHT in dieser Liste (geprüft und ausgeschlossen: radsport-events.de,
schwimmkalender.de, tri2b.com, triafreunde.com, hdsports.org,
datasport.com, alpen-open-watercup.de, rad-net.de, swiss-cycling.ch,
ahotu.com).

| Quelle | Inhalt | robots.txt (21.09.2026) | Anmerkung |
|---|---|---|---|
| `laufevent.at/events/` | Laufkalender Österreich, ~550 Events/Jahr, Filter nach Region | aus der Sandbox nicht erreichbar (kein Abruf) | vor dem Bau vom Rechner aus prüfen |
| `sparkasse.at/running/laufkalender` | Laufkalender Österreich (Erste Bank Sparkasse Running) | erlaubt (nur Bank-Bereiche gesperrt) | Kalender einer Bank, Daten vermutlich aus laufkalender.at |
| `oelv.at/de/sport/laufsport` | ÖLV-Laufkalender (Verband) | erlaubt (nur `/login/`) | Verbandstermine, Volksläufe unvollständig |
| `wlv.or.at/wettkaempfe-termine/laufkalender` | Wiener LV, Laufkalender | erlaubt (keine Sperre) | regional |
| `runme.at`, `runme.ch` | Laufkalender AT und CH | Kalender erlaubt (`/call/` gesperrt); **sperrt GPTBot und CCBot ausdrücklich** | Betreiber will keine KI-Crawler – nur mit Nachfrage beim Betreiber |
| `laufkalender-schweiz.ch` | Laufkalender Schweiz, „fast 1.000 Läufe“, Filter nach Kanton/Distanz | keine robots.txt (404) | Nutzungsbedingungen lesen |
| `lauftermine.ch` | Laufkalender Schweiz (älteres Verzeichnis) | keine robots.txt (404) | Struktur prüfen |
| `laufkalender-nws.ch` | Nordwestschweiz, Herbst-/Winterläufe | erlaubt (`/app/`, `/j/` gesperrt) | klein, regional |
| `trophyrunners.de/laufevents/oesterreich/`, `trophyrunners.com` (CH) | Volksläufe AT/CH | aus der Sandbox nicht erreichbar | vom Rechner aus prüfen |
| `finishers.com` (Schweiz u. a.) | Laufkalender mit Detailseiten | erlaubt (Konto/Buchung/Filter-Adressen gesperrt) | internationale Plattform, ToS lesen |
| `running.life` – `traillauf-kalender/…`, `hindernislauf-kalender/…` | dieselbe Quelle wie heute, weitere Kalender | erlaubt (wie bisher) | prüfen, ob die Trail-/OCR-Kalender Events enthalten, die im Laufkalender fehlen |
| `triathlon-austria.at/de/service-termine` | Verbandstermine Triathlon Österreich | erlaubt (nur `/login/`) | Verband, vollständig für AT |
| `mission-triathlon.de/saisonplanung-…` | redaktionelle Liste ~250 Triathlons DE/AT/CH | erlaubt | Liste, keine Datenbank – eher als Abgleich |
| `events.endure-cycling.com` | Radrennen, Jedermannrennen, Radmarathons UND Triathlons AT/DE/EU, mit Karte und Filtern | erlaubt (keine Sperre) | vielversprechend für Fahrrad; ToS prüfen |
| `bike-x.de/rennrad/news/termine-jedermannrennen-und-radmarathons/` | Termine Jedermannrennen/Radmarathons DE | erlaubt (nur `/irelements/`) | redaktionelle Liste |
| `brv-breitensport.de/termine/rtf-kalender/` | RTF-Kalender Berlin/Mitteldeutschland | erlaubt | regional |
| `dsv.de/…/freiwasserschwimmen/wettkampf/kalender/` | DSV-Freiwasser-Kalender (Verband) | erlaubt | Wettkampfsport, keine Jedermann-Schwimmen |
| `openwaterschwimmen.com/openwater` | Freiwasser-Termine im deutschsprachigen Raum | erlaubt (`?lightbox=` gesperrt) | Wix-Seite, evtl. JS-gerendert |
| `team-warmduscher.de/open-water/open-water-in-deutschland/` | Liste Open-Water-Veranstaltungen DE | erlaubt | Vereinsseite, Liste ohne Struktur |

Je Quelle vor dem Bau: Nutzungsbedingungen/Impressum auf ein
Scraping-Verbot durchsehen, Detailseiten auf Veranstalter-Link und
Strecken prüfen, `--max-pages 2 --no-details` als Probelauf.

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

### Wöchentliche automatische Aktualisierung (GitHub Action)

`.github/workflows/update-events.yml` führt `update_events.py` **einmal
pro Woche, montags** automatisch aus (Cron `0 5 * * 1` UTC, entspricht ca.
06:00 Uhr deutscher Zeit – GitHub-Cron kennt keine Zeitzonen, siehe Kommentar in der
Workflow-Datei für Details zur CET/CEST-Abweichung) und zusätzlich manuell
über den "Run workflow"-Button im Actions-Tab. Ändert sich `events.json`
dabei, wird sie automatisch committet und auf `claude/endurance-events-website-v1wruf`
gepusht – das stößt wiederum automatisch den bestehenden Pages-Deploy-Workflow
an, die Seite aktualisiert sich also von selbst. Der Geocoding-Cache
(`scripts/.geocode_cache.json`) wird dabei über GitHub Actions Cache
zwischen den Läufen wiederverwendet, um wiederholte Nominatim-Anfragen für
bereits bekannte Städte zu vermeiden.

**Vorher lief der Workflow täglich.** Solange die Seite nicht live ist,
bringt ein täglicher Lauf nichts außer ~2 Stunden Laufzeit und einem
großen `events.json`-Diff pro Tag; ein Veranstaltungskalender ändert sich
ohnehin nicht stündlich. Für einen Lauf zwischendurch genügt der
"Run workflow"-Button. Zurück auf täglich: `- cron: '0 5 * * *'`.

## Login/Anmeldung einrichten

`index.html`, `events.html` und `karte.html` haben rechts neben dem
Home-Button einen „Anmelden"-Button (siehe `auth.js`). Er nutzt
**Firebase Authentication** (Google + E-Mail/Passwort mit Bestätigungs-
E-Mail).

„Mit Apple anmelden" ist **ausgeblendet**: Apple Sign-In erfordert ein
Apple-Developer-Konto für 99 $ im Jahr. Das Projekt soll vorerst ohne
laufende Kosten auskommen – und ein dauerhaft ausgegrauter Button war
nur Ballast im Dialog.

`SHOW_APPLE_SIGNIN = true` in `auth.js` allein genügt dafür **nicht**.
Vorhanden ist bisher nur die Hülle: das Button-Markup (fest auf
`disabled`, ohne Klick-Behandlung) und das Icon. Eine
`signInWithApple()` gibt es nicht. Wer den Login wirklich will, braucht
drei Schritte: das Developer-Konto samt Service ID, Key und Team ID in
der Firebase-Konsole; eine `signInWithApple()` analog zu
`signInWithGoogle()` (`new firebase.auth.OAuthProvider('apple.com')`
statt `GoogleAuthProvider` – Popup, Weiterleitungs-Fallback und
`handleRedirectResult()` gelten unverändert); und das Entfernen des
`disabled` samt Verdrahtung des Buttons.

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
   Zusätzlich über „Neuer Anbieter → Native Anbieter" den Anbieter
   **Anonym** aktivieren – den braucht das Melden von Datenfehlern
   (siehe „Fehler zu diesem Event melden" unten); ohne ihn bleibt der
   Rest des Logins unberührt, nur das Melde-Formular meldet einen
   Hinweis.
3. **Authentication → Einstellungen → Autorisierte Domains**:
   `antdon930.github.io` eintragen. **Dieser Schritt wird gern
   vergessen** – ohne ihn funktioniert der Login lokal, aber live auf
   GitHub Pages bricht er mit `auth/unauthorized-domain` ab.
4. **Datenbanken und Speicher → Firestore Database → Datenbank
   erstellen**. Der Assistent fragt drei Dinge:
   - *Version*: **Standardversion** (automatische Indexierung). Die
     Enterprise-Version ist für MongoDB-kompatible Workloads mit
     selbstverwalteter Indexierung – hier unnötig und teurer.
   - *Datenbank-ID und Speicherort*: ID **`(default)`** lassen (siehe
     Hinweis in `firestore.rules`: `auth.js` spricht immer die
     Standard-Datenbank an). Speicherort z. B. `europe-west3`
     (Frankfurt) – **nicht mehr änderbar**.
   - *Konfigurieren*: **Produktionsmodus**, nicht Testmodus – der wäre
     30 Tage lang weltweit lesbar UND beschreibbar.

   Danach unter **Regeln** den Inhalt von `firestore.rules` (in diesem
   Repo) einfügen und veröffentlichen. Nur für „Benachrichtige mich"
   nötig, nicht für den Login selbst – dieser Schritt lässt sich also
   nachholen.

   Wer die Firebase-CLI ohnehin installiert hat, spart sich das
   Kopieren: `firebase.json` verweist auf `firestore.rules`, also genügt

   ```bash
   firebase deploy --only firestore:rules
   ```

   Das geht auch im **Spark-Tarif** – nur das Deployen von *Functions*
   verlangt Blaze, Regeln nicht. Vorteil gegenüber der Konsole: Was live
   ist, entspricht dann garantiert der Datei im Repo.
5. **Projektübersicht → „App hinzufügen" → Web (`</>`)**, Namen vergeben,
   registrieren. Das dort angezeigte Config-Objekt in
   `firebase-config.js` einfügen (ersetzt die `REPLACE_ME`-Platzhalter).
   **Firebase Hosting dabei nicht einrichten** – die Seite läuft auf
   GitHub Pages.
6. Committen und pushen – der Login funktioniert danach auf allen drei
   Seiten (dasselbe `firebase-config.js`/`auth.js` wird überall geladen).

### Google-Login: Popup, Weiterleitung, In-App-Browser

Der Google-Login versucht zuerst ein **Popup**
(`signInWithPopup`) – das ist der angenehmere Weg, weil die Seite dabei
nicht verlassen und kein Filterzustand verworfen wird. Öffnet der
Browser gar kein Popup, schaltet `signInWithGoogle()` in `auth.js`
automatisch auf **Weiterleitung** um (`signInWithRedirect`) und zeigt
kurz „Weiterleitung zu Google …".

Umgeschaltet wird nur bei Fehlercodes, die bedeuten „das Popup ging
nicht auf": `auth/popup-blocked`,
`auth/operation-not-supported-in-this-environment`,
`auth/web-storage-unsupported`, `auth/internal-error`. **Nicht** bei
`auth/popup-closed-by-user` – wer das Fenster selbst zumacht, will sich
gerade nicht anmelden; eine Weiterleitung wäre übergriffig. Ein zweiter
Klick während ein Popup noch läuft (`auth/cancelled-popup-request`) wird
stillschweigend ignoriert.

Nach der Rückkehr wertet `handleRedirectResult()` das Ergebnis aus. Es
läuft beim Laden **jeder** Seite und ist ohne vorangegangene
Weiterleitung ein No-op. Dass überhaupt eine lief, merkt sich
`sessionStorage` unter `endurance-google-redirect`.

**Die Grenze des Fallbacks**: In eingebetteten Browsern (Instagram,
Facebook, LinkedIn) blockiert der Speicherschutz – auf iOS Safaris ITP –
den Datenaustausch mit der `*.firebaseapp.com`-Domain. Die Weiterleitung
kann dort also trotzdem scheitern, und zwar *stumm*: der Nutzer kommt
zurück und ist einfach nicht angemeldet. Genau diesen Fall fängt
`handleRedirectResult()` ab (Weiterleitung lief, aber kein `user`) und
sagt im Klartext, dass die Seite im normalen Browser geöffnet werden
muss. Lieber ein ehrlicher Hinweis als ein Button, der scheinbar nichts
tut.

Vollständig lösen ließe sich das nur, indem `authDomain` in
`firebase-config.js` auf eine eigene Domain zeigt, die per Reverse-Proxy
auf Firebase weiterleitet – das setzt eine eigene Domain samt Server
voraus und ist auf GitHub Pages nicht möglich.

### „Benachrichtige mich" (0 Treffer in der Liste)

Setzt jemand in `events.html` Filter, für die aktuell **kein** Event
existiert, erscheint statt der leeren Tabelle ein Hinweis mit einem
Button „Benachrichtigen, sobald verfügbar" (nicht angemeldet: „Anmelden,
um benachrichtigt zu werden", öffnet das Login-Modal). Ein Klick
speichert die aktuell aktiven Filter - **ohne den Datumsfilter** (das
gesuchte Event liegt ja per Annahme in der Zukunft und ist deshalb noch
nicht in `events.json`) - als Dokument in der Firestore-Collection
`filterSubscriptions` (siehe `auth.js: saveFilterSubscription()`).

Der Umkreis steht im Abo als `radiusKm` (Zahl in Kilometern) neben dem
`origin`. Ältere Abos tragen noch das Feld `radius` mit einer der vier
alten Stufen (`"0-5"` … `"50+"`); `eventMatchesFilters()` in
`functions/index.js` rechnet die weiterhin um - auf die Obergrenze der
Stufe, aus dem Ring wird also eine Kreisfläche. Das schließt höchstens
ein paar nähere Events zusätzlich ein und ist allemal besser, als ein
bestehendes Abo verstummen zu lassen.

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
   cd functions && npm install && cd ..
   firebase functions:secrets:set NOTIFY_WEBHOOK_SECRET   # Wert frei wählen
   firebase deploy --only functions
   ```
   **`firebase init functions` ist nicht nötig** – `firebase.json` und
   `.firebaserc` liegen fertig im Repo (Projekt `endurance-5177a`). Der
   Assistent würde ohnehin anbieten, die vorhandene `functions/index.js`
   zu überschreiben.

   Der Secret-Schritt ist **Pflicht, nicht optional**: Ohne gesetztes
   `NOTIFY_WEBHOOK_SECRET` beantwortet die Function jeden Aufruf mit
   `503`. Das ist Absicht – früher stand in der Function
   `if (expectedSecret && …)`, die Prüfung entfiel also stillschweigend,
   wenn die Variable fehlte. Und genau das war der Normalfall: Bei
   Functions der 2. Generation ist `process.env` nach einem gewöhnlichen
   Deployment leer, der Wert muss im Secret Manager liegen. Ergebnis wäre
   eine Function gewesen, in die jeder mit Kenntnis der URL erfundene
   „neue Events" posten kann – echte Abonnenten bekommen eine E-Mail, und
   ihr Abo wird dabei auf `notified: true` verbrannt.

   Danach die ausgegebene Function-URL als GitHub-Actions-Secret
   `NOTIFY_WEBHOOK_URL` hinterlegen (Repo → Settings → Secrets and
   variables → Actions) und **denselben** Geheimniswert als
   `NOTIFY_WEBHOOK_SECRET`. `update_events.py` ruft die URL danach
   automatisch nach jedem Lauf auf, in dem sich `events.json` geändert
   hat, und weist sich per Header `X-Notify-Secret` aus.
2. In der Firebase-Konsole unter **Extensions** die offizielle Extension
   **"Trigger Email from Firestore"** installieren und dort SMTP-
   Zugangsdaten (z. B. von SendGrid, Mailgun oder einem eigenen Postfach)
   hinterlegen - sie übernimmt den eigentlichen Versand für die
   `mail`-Dokumente, die `functions/index.js` anlegt.

**Was die Function nicht tut**: Sie prüft ausschließlich die Events, die
`update_events.py` ihr als *neu* meldet. Bestehende Abos werden also
**nicht** rückwirkend gegen die bereits vorhandenen Events geprüft – ein
gespeichertes Abo schlägt erst an, wenn nach dem Deployment ein passendes
Event dazukommt. Die Abos bleiben mit `notified: false` gültig und gehen
nicht verloren, aber wer heute ein Abo anlegt, dessen Event schon in
`events.json` steht, bekommt dafür keine Mail (er hätte es in der Liste
ja auch gefunden).

**Die Distanz-Kategorien sind doppelt gepflegt**: `DISTANCE_CATEGORIES`
steht sowohl in `events.html` als auch in `functions/index.js` und
**muss an beiden Stellen übereinstimmen**. Beim Ändern einer Kategorie
also immer beide anpassen.

Die Function ignorierte diesen Filter früher ganz, mit zwei Folgen, die
beide real auftraten:

- Ein Abo mit **nur** einer Kategorie („Marathon", ohne Von/Bis-Werte)
  traf auf **jedes** Event – es hätte eine E-Mail pro neuem Event gegeben
  (gegen den echten Datenstand geprüft: 1372 von 1372 Treffern statt der
  korrekten 155).
- Das erste echte Abo (Schwimmen 10+ km, zusätzlich 400–500 km) traf auf
  42 Events, obwohl die Webseite dafür 0 Treffer anzeigt. Ursache: Die
  Von/Bis-Prüfung überspringt Events **ohne** Distanzangabe, der
  Kategorie-Filter der Webseite verlangt dagegen eine bekannte Distanz –
  genau diese 42 Events ohne Distanz rutschten durch.

Beides ist behoben; die Function liefert jetzt dieselben Treffer wie die
Liste. Falls die Tabelle irgendwann wirklich geteilt statt kopiert werden
soll, wäre eine gemeinsame `distance-categories.js` der Weg – dafür
müsste `functions/` aber auf ES-Module oder einen Build-Schritt umgestellt
werden, was für eine Tabelle mit vier Sportarten unverhältnismäßig ist.

### „Fehler zu diesem Event melden" (Meldungen der Nutzer/innen)

Wer in `events.html` ein Event anklickt, findet im Detailbereich unter
dem Link zur Veranstalter-Website den Button **„Fehler zu diesem Event
melden"**. Er öffnet ein Formular mit einem Drop-down („Wo liegt der
Fehler?" – Länge, Datum, Ort/Land, Link, Sportart, Name, Doppelt,
Abgesagt, Sonstiges) und einem Freitextfeld (10–600 Zeichen).

**Warum überhaupt**: Die Liste hat über 4000 Einträge aus vier Quellen.
Ob bei einem einzelnen Lauf die Distanz stimmt, weiß realistisch nur,
wer ihn kennt – fast alle bisher gefundenen Datenfehler kamen aus
solchen Stichproben. Melden ist deshalb absichtlich niederschwellig:
**ohne Anmeldung**. Technisch meldet `auth.js` dafür bei Bedarf *anonym*
bei Firebase an (`signInAnonymously`), damit die Security Rules trotzdem
`request.auth != null` verlangen können – ein offener, völlig
unauthentifizierter Schreib-Endpunkt wäre eine Einladung zum Zuspammen.
Dafür muss in der Firebase-Konsole der Anbieter **„Anonym"** aktiv sein
(Authentication → Sign-in method → Neuer Anbieter → Native Anbieter →
Anonym). Ist er es nicht, sagt das Formular das im Klartext statt mit
einem Firebase-Fehlercode.

Gespeichert wird je Meldung ein Dokument in der Firestore-Collection
`errorReports`: Kategorie, Beschreibung, `uid`/`anonym` (und die E-Mail,
falls angemeldet), `status: "neu"` und ein **Schnappschuss des Events**
(Name, Datum, Standort, Land, Sportart, Distanz, Wettbewerb, Link). Der
Schnappschuss ist wichtig: die Daten ändern sich täglich, ohne ihn wäre
später nicht nachvollziehbar, worauf sich die Meldung bezog. Lesen kann
die Meldungen niemand über die Webseite (`firestore.rules`:
`allow read, update, delete: if false`) – nur das Admin-SDK.

#### Der Ablauf: gebündelt ansehen, einzeln bestätigen

Meldungen werden **nie automatisch** übernommen. Eine Meldung ist ein
Hinweis, kein Beweis – jemand kann sich irren, das Jahr verwechseln oder
Unsinn schreiben. Für alles andere gilt dieselbe Lektion wie bei den
Heuristiken weiter oben: erst prüfen, dann ändern.

```bash
# 1. Meldungen holen und pro Strecke bündeln
python3 scripts/review_reports.py fetch --credentials ~/serviceaccount.json
#    (ohne Zugangsdaten: Export aus der Konsole und
#     python3 scripts/review_reports.py fetch --from-json export.json)

# 2. ansehen - am häufigsten gemeldete Events zuerst
python3 scripts/review_reports.py show

# 3. nach Einzelprüfung (Websuche gegen die offizielle Ausschreibung)
#    einen Vorschlag anlegen - wirkt noch NICHT
python3 scripts/review_reports.py propose \
    --key "48. Hochgratlauf|2026-09-06|12.8" \
    --set laenge_km=12,4 \
    --grund "Ausschreibung 2026 nennt 12,4 km" \
    --quelle "https://www.tsv-oberstaufen.de/hochgratlauf" \
    --report-id <Meldungs-ID>

# 4. bestätigen (fragt jeden Vorschlag einzeln mit j/n ab)
python3 scripts/review_reports.py confirm
#    nicht-interaktiv: confirm --key 2026-09-16-01  bzw.  reject --key ...

# 5. Meldungen in Firestore abhaken, damit 'fetch' sie nicht wieder holt
python3 scripts/review_reports.py mark-done --credentials ~/serviceaccount.json
```

Erst Schritt 4 schreibt den Eintrag nach `scripts/manual_overrides.json`
(mit Begründung und Quelle im `_note`); wirksam wird er beim nächsten
`clean_events.py`-Lauf bzw. der nächtlichen Action. Dazwischen liegen die
Vorschläge in `scripts/pending_overrides.json` – die Datei ist im
Repository, der Zwischenstand also im PR sichtbar.

Drei Details, die in der Praxis zählen:

- **Gebündelt wird pro Strecke, nicht pro Veranstaltung.** Der
  Bündel-Schlüssel ist genau der distanzgenaue Override-Schlüssel
  `"<Name>|<Datum>|<km>"` (siehe `scraper_lib.override_keys()`). Sonst
  würde eine Meldung zur 10-km-Strecke am Ende die Marathonzeile
  derselben Veranstaltung korrigieren.
- **Der Schlüssel enthält die alte, falsche Distanz** – gewollt: der
  Override greift, *bevor* er die Distanz ersetzt, und muss das Event
  daher unter seinem gescrapten Wert finden.
- **Mehrfachmeldungen zuerst.** `show` sortiert nach Anzahl: drei
  unabhängige Meldungen zur selben Strecke sind ein deutlich stärkerer
  Hinweis als eine.

`scripts/reports_inbox.json` (die gebündelten Rohmeldungen) enthält
`uid` und ggf. E-Mail-Adressen und ist deshalb per `.gitignore` aus dem
Repository ausgenommen. In `manual_overrides.json` landet nur die
fachliche Begründung, nie die Person.

## Bedienung ohne Maus, und das Tippen auf dem Handy

Zwei Lücken, die beim Durchsehen der Seite aufgefallen sind und die
zusammengehören: Beide betreffen nicht das Aussehen, sondern ob man die
Liste überhaupt benutzen kann.

### Tippen auf eine Zeile zeigte nichts

Unter 900 px hat die Seite **eine** Spalte – der Detailbereich steht
also unter der Tabelle, und die ist 78vh hoch. Ein Tippen auf eine Zeile
füllte die Angaben rund einen Bildschirm weiter unten, ohne dass etwas
darauf hinwies: auf dem Handy wirkte es folgenlos.

`zeigeDetailbereich()` in `events.html` scrollt jetzt hin – aber nur,
wenn nötig:

- Es scrollt **nur, wenn der Bereich außerhalb des Bildes liegt**. Am
  Rechner steht er neben der Tabelle; dort darf sich nichts bewegen.
- Es scrollt **nicht beim Auf- und Zuklappen** einer zusammengefassten
  Veranstaltung: dann will man die Strecken sehen, die gerade an dieser
  Stelle erscheinen.
- Es scrollt **nicht bei der Pfeiltasten-Navigation** – sonst schöbe
  sich die Tabelle weg, in der man gerade navigiert.
- `prefers-reduced-motion` schaltet das sanfte Scrollen ab.

### Tastaturbedienung

Die Tabellenzeilen sind `<tr>` mit einem Listener am `<tbody>` (so
bleibt das Zeichnen schnell, siehe „Tempo der Seite") – von sich aus
sind sie damit weder fokussierbar noch auslösbar. Die Liste war ohne
Maus nicht zu bedienen.

Nachgerüstet ist das Muster, das Browser für lange Listen kennen
(**roving tabindex**): Jede Zeile trägt `tabindex="-1"`, aber nur
**eine** ist per Tab erreichbar (`setzeTabStop()`). 4.155 Tab-Stopps
wären eine Falle – man käme aus der Tabelle nicht mehr heraus. Innerhalb
der Tabelle bewegt man sich mit den Pfeiltasten, über **einen**
`keydown`-Listener am `<tbody>`:

| Taste | Wirkung |
|---|---|
| ↑ / ↓ | eine Zeile weiter; die Zeile wird dabei ausgewählt, die Angaben stehen sofort daneben |
| Home / End | erste / letzte Zeile |
| → / ← | zusammengefasste Veranstaltung auf- / zuklappen (nur bei mehreren Strecken) |
| Leertaste | klappt um (und blättert nicht die Seite weiter) |
| Enter | springt in die Angaben; von dort erreicht Tab die Links (Veranstalter, Kalender, Fehler melden) |

Am **Filter-Panel** (`filter-ui.js`, gilt für Liste *und* Karte):
Enter/Leertaste am Spaltenknopf öffnet es, Pfeil nach unten geht hinein,
**Escape** schließt es und gibt den Fokus an den Knopf zurück. Verlässt
der Fokus das Panel per Tab, schließt es sich – ein Panel, das man
verlassen hat, schwebte sonst weiter über der Seite. Wichtig dabei: ein
`focusout` **ohne** `relatedTarget` ist *kein* Verlassen (das Panel hat
sich nur selbst neu gezeichnet und das fokussierte Element ersetzt) und
darf nicht schließen. Die Knöpfe tragen `aria-haspopup="dialog"` und
`aria-expanded`.

**Dialoge** (Anmelden, „Fehler zu diesem Event melden") versprechen mit
`aria-modal="true"`, dass der Fokus darin bleibt – jetzt tut er das
auch: `dialogTasten(box, schliessen)` in `auth.js` fesselt Tab im Dialog
und schließt bei Escape, `openModal()`/`openReportModal()` merken sich,
woher der Fokus kam, und geben ihn beim Schließen zurück. Die Funktion
steht **einmal** in `auth.js` und wird von `events.html` mitbenutzt;
eingehängt wird sie dort erst beim ersten Öffnen, weil `auth.js` `defer`
trägt und beim Inline-Skript noch nicht existiert (dieselbe Reihenfolge
wie bei `EE_AUTH_QUEUE`).

Sichtbar ist der Fokus über `:focus-visible` (Zeile und Detailbereich
bekommen einen Rahmen in der Akzentfarbe) – `:focus-visible` statt
`:focus`, damit ein Mausklick, der die Zeile ebenfalls fokussiert,
keinen Rahmen hinterlässt.

Der Rauchtest prüft die ganze Kette: ein Tab-Stopp, Pfeiltaste bewegt
und wählt, End springt ans Ende, Enter landet im Detailbereich, Escape
schließt Panel und Dialog und gibt den Fokus zurück.

## Nichts von fremden Servern (`vendor/`)

Leaflet, Leaflet.markercluster und die Firebase-SDKs liegen **im Repo**
(`vendor/`, 752 KB) statt auf unpkg bzw. gstatic.com. Zwei Gründe:

1. **Datenschutz.** Ein CDN-Abruf überträgt die IP-Adresse jedes
   Besuchers an Dritte – und zwar bei *jedem* Seitenaufruf, auch wenn
   sich niemand anmeldet und niemand die Karte öffnet. Was die Seite
   gar nicht an Dritte schickt, muss die Datenschutzerklärung auch
   nicht erklären.
2. **Verlässlichkeit.** Die Version im Ordner ist die Version, die
   ausgeliefert wird: kein fremder Ausfall, keine stille Änderung, und
   keine `integrity`-Prüfung nötig (gleiche Herkunft).

Es sind die unveränderten Originale – die SHA-256-Summen stimmen mit
den SRI-Werten überein, die vorher im HTML standen. Nachgeprüft mit
**blockiertem Netz** (jede Anfrage außer `127.0.0.1` abgewiesen): Alle
Seiten laden vollständig, Leaflet und die Bündelung arbeiten, Firebase
und der Anmelden-Knopf stehen, die Liste zeigt ihr Fenster – kein
Skriptfehler, kein 404.

**Die einzige fremde Anfrage bleiben die OpenStreetMap-Kacheln**, und
nur auf der Kartenseite: Eine Karte ohne Kartenbilder gibt es nicht.
Sie stehen deshalb in der Datenschutzerklärung. Strenger wäre, die
Kacheln erst nach einem Klick zu laden („Karte anzeigen") – das kostet
die Karte ihre Unmittelbarkeit und ist deshalb nicht gebaut.

`test_keine_fremden_dateien` hält den Zustand fest: kein `src` und kein
`<link href>` auf einen fremden Server in den fünf Seiten, kein
nachgeladenes fremdes Skript in `auth.js`/`filters.js`/`filter-ui.js`,
und jede `vendor/`-Datei, auf die verwiesen wird, liegt wirklich im
Repo. Ein `<a href>` auf `geonames.org` zählt bewusst **nicht** mit –
ein Link überträgt nichts, solange niemand klickt (genau daran ist die
Prüfung im ersten Versuch gescheitert).

**Aktualisieren**: neue Version in einen neuen Ordner
(`vendor/leaflet-1.9.4` → `…-1.9.5`) und die Verweise umhängen. Damit
ist der Pfad die Versionsangabe, und kein Browser-Cache kann einen
halben Stand mischen.

## Impressum und Datenschutzerklärung

`impressum.html` und `datenschutz.html` sind gebaut und von **jeder**
Seite aus verlinkt (§ 5 DDG verlangt „unmittelbar erreichbar"). Beide
sind **noch Vorlagen**: Jede offene Stelle ist gelb markiert
(`.platzhalter`), und oben steht ein Kasten „Diese Seite ist noch eine
Vorlage". Der Rauchtest prüft, dass diese Markierungen sichtbar sind –
so kann die Vorlage nicht unbemerkt als fertiges Impressum live gehen.

**Was noch eingetragen werden muss** (alles im Impressum bzw. im
Abschnitt „Verantwortlicher" der Datenschutzerklärung): Name bzw.
Firma, Anschrift, E-Mail-Adresse, optional Telefon, und das Datum
unter „Stand". Nichts davon kann aus dem Projekt kommen.

Die **Datenschutzerklärung beschreibt den tatsächlichen Stand** der
Seite, nicht eine Wunschvorstellung:

| Was | Wann | Wohin |
|---|---|---|
| Server-Protokolle (IP, Zeit, Datei) | bei jedem Aufruf | GitHub Pages |
| Kartenbilder | nur auf `karte.html` | OpenStreetMap Foundation |
| Standort für die Umkreissuche | nach Erlaubnis | **bleibt im Browser** |
| Anmeldung, Konto | nur beim Anmelden | Firebase Auth (Google Irland) |
| anonyme Kennung | erst beim Absenden einer Fehlermeldung | Firebase Auth |
| Fehlermeldung, Abo-Filter | beim Absenden | Cloud Firestore (EU) |
| `endurance-lang`, `endurance-gruppiert` | immer | lokaler Speicher, bleibt auf dem Gerät |

Kein Tracking, keine Analyse, keine Werbung, keine Profilbildung –
und das steht so auch in der Erklärung. **Wird an der Seite etwas
verändert, das Daten betrifft, muss dieser Text mit.**

Die **GeoNames-Namensnennung ist umgezogen**: Sie stand in der Fußzeile
von `index.html` und steht jetzt im Impressum unter „Datenquellen und
Lizenzen" – zusammen mit OpenStreetMap (ODbL), Leaflet und dem
Firebase-SDK. Das Impressum ist von überall verlinkt, damit ist der
Namensnennung nach CC BY 4.0 Genüge getan.

Beide Seiten sind zweisprachig (dieselbe `data-i`-Mechanik wie die
Startseite, dieselbe Spracheinstellung in `localStorage`); die
deutsche Fassung ist die verbindliche. **Keine Rechtsberatung** – vor
dem Livegang prüfen (lassen).

## E-Mail-Abos: neue Events, im gewünschten Rhythmus

„Benachrichtige mich" war eine **Einmal-Zusage**: Eine Suche ging leer
aus, man hinterlegte die Filter, und sobald ein passendes Event auftauchte,
kam eine E-Mail – genau eine. Der Knopf erschien auch nur bei null
Treffern. Wer „alle neuen Schwimm-Events in Thüringen" oder „alles neue
im Umkreis von 25 km um München" wollte, kam gar nicht an ihn heran.

Daraus ist ein **Abo** geworden: dieselben Filter, aber dauerhaft, und
mit einem Rhythmus.

- **Der Knopf steht in der Werkzeugleiste** („Neue Events per E-Mail")
  und ist immer erreichbar. Die Box bei null Treffern führt jetzt in
  denselben Dialog – es gibt genau **einen** Weg, an dem ein Abo
  entsteht, und der kennt den Rhythmus.
- **„Welche Events?" steht im Dialog.** Die Filter der Liste *sind* die
  Auswahl – nur sah man das nicht: Wer ohne Filter auf den Knopf tippte,
  las „Alle neuen Events" und hatte im Dialog keine Möglichkeit, daraus
  „nur Radrennen im Umkreis von 25 km" zu machen. Der Dialog trägt
  deshalb dieselbe Knopfreihe wie die Karte (Name, Land, Stadt/Ort,
  Sportart, Kategorie, Länge), nur ohne „Datum".

  Drei Dinge waren dafür nötig, und alle drei sind dort begründet, wo sie
  stehen:

  1. **Ein eigener Filterzustand.** Der Dialog arbeitet auf einer Kopie
     der laufenden Suche (`EF.copyState(state, true)`, ohne Datum): Wer
     schon gefiltert hat, findet seine Filter vor, und was er im Dialog
     umstellt, verändert die Liste dahinter nicht. Es ist dieselbe
     Bedien-Datei (`filter-ui.js`), nur eine zweite Instanz – keine
     Kopie der Filterlogik.
  2. **Das Panel gehört in den Dialog.** An `<body>` gehängt lag es
     hinter dem Dialog (z-index 1000 gegen 2000) und außerhalb seiner
     Fokusfessel, war also per Tastatur unerreichbar. `EFU.create`
     nimmt dafür `panelParent`.
  3. **Auch Werte ohne heutige Events** (`alleWerte: true`). Die Liste
     bietet nur an, was in den Daten steht – sinnvoll dort, falsch hier:
     Als der Dialog entstand, stand in `events.json` kein einziges
     Radrennen, „Fahrrad" stand also gar nicht zur Wahl. (Inzwischen
     sind es neun – für die Schweiz und fürs Schwimmen gilt das
     Argument aber unverändert.) Ein Abo schaut aber in die Zukunft,
     und genau das war der Wunsch. Angeboten werden deshalb alle
     Sportarten und Länder, die die Seite kennt.

- **Der Dialog zeigt, was das Abo umfasst** – gebaut aus genau den
  Feldern, die auch gespeichert werden („Laufen · 25 km um München").
  Nicht aus den Filter-Chips: Die zeigen auch den Datumsfilter, und der
  gehört nicht dazu. Ein Abo schaut in die Zukunft; mit einem
  Datumsfilter könnte nie ein neues Event passen. Eine Änderung in der
  Filterleiste schreibt **nur diesen Kasten** neu – ein Neuzeichnen des
  ganzen Dialogs nähme den gewählten Rhythmus und den Fokus mit.
- **Drei Rhythmen**: `sofort`, `woechentlich`, `monatlich`. „Sofort" ist
  ehrlich beschriftet – die Daten werden wöchentlich erneuert, schneller
  als der Datenlauf kann kein Abo sein.
- **Mehrere Abos je Person** sind möglich, und der Dialog listet sie mit
  einem Löschen-Knopf. Ohne diese Liste käme man nur über die E-Mail
  wieder heraus.
- **Jede E-Mail hat einen Abmelde-Link, der ohne Anmeldung
  funktioniert.** Dafür trägt jedes Abo einen zufälligen `token`
  (16 Byte aus `crypto.getRandomValues`), und es gibt eine zweite Cloud
  Function `unsubscribe`, die Kennung und Token zeitkonstant vergleicht
  und das Abo auf `aktiv: false` setzt. Der Link steht zusätzlich im
  `List-Unsubscribe`-Kopf, damit Mail-Programme ihren eigenen
  Abmelde-Knopf zeigen – wer den nutzt, markiert die Nachricht nicht als
  Spam.

**Wie die Function sammelt und verschickt** (`functions/index.js`): Sie
wird nach jedem Datenlauf mit den **neu hinzugekommenen** Events
aufgerufen. Je Abo sammelt sie die Treffer in `wartend` (höchstens 50,
darüber zählt sie nur noch mit – Firestore-Dokumente dürfen 1 MB groß
werden) und schickt, sobald der Rhythmus fällig ist: `sofort` immer,
`woechentlich` nach 6 Tagen, `monatlich` nach 28. Sechs statt sieben Tage
ist Absicht: Der Lauf startet montags, aber nicht auf die Sekunde – bei
genau sieben Tagen fiele sonst eine Woche aus.

**Alte Abos behalten ihre Zusage.** Dokumente ohne `rhythmus` sind die
Einmal-Benachrichtigungen von früher; sie bleiben genau das („einmal,
dann Ruhe"). Kein Datenumzug nötig, und niemand bekommt plötzlich einen
Newsletter, den er nie bestellt hat.

**Die E-Mail verlinkt bewusst nicht die Detailseite** eines Events:
Deren Adresse enthält den `eventSlug`, und diese Regel steht schon
zweimal im Projekt (`events.html` und `build_ics.py`, gegeneinander
geprüft). Eine dritte Kopie in der Function würde irgendwann abweichen
und tote Links verschicken – die E-Mail verlinkt deshalb die
Veranstalter-Seite und die Liste.

**Was noch fehlt**: der Versand selbst. Er braucht die zwei
Blaze-Schritte (Cloud Functions deployen, Extension „Trigger Email"
plus SMTP) – siehe unten. Abos werden also schon gespeichert, aber es
geht noch keine E-Mail heraus; die Datenschutzerklärung sagt das auch so.

## Ein Ironman ist kein Lauf

Die vier aktiven Quellen sind **Laufkalender**. Ihre Konfiguration trägt
deshalb `default_art1 = "Laufen"` – und genau das stand dann auch bei
jedem Triathlon, den sie nebenbei mitlisten. Aufgefallen ist es an einer
Zeile, die es nicht geben darf:

> Ironman 70.3 Kraichgau · **Laufen** · Straße · 52 km

Bei einem Ironman kann man sich nicht für den Lauf allein anmelden.
**132 Einträge** waren betroffen: Triathlons, Duathlons, SwimRuns.

**Die Sportart kommt jetzt aus dem Namen**, nicht aus der Quelle:
`guess_art1()` (`scraper_lib.py`) überschreibt die Voreinstellung bei
einem eindeutigen Stichwort, `clean_events.fix_multisport_art1()` holt
den Bestand nach. Nur **eindeutige** Begriffe stehen in der Liste –
„Triathlon" und „Ironman" sind eindeutig, ein „Rad" im Namen ist es
nicht („Radrennbahn-Lauf"). Was nicht eindeutig ist, bleibt draußen;
dieselbe Vorsicht wie beim Löschen (siehe „Datenqualität").

**„Triathlon" ist die Mehrsport-Schublade.** Duathlon
(Laufen-Rad-Laufen), Aquathlon (Schwimmen-Laufen), SwimRun und
Quadrathlon sind keine Triathlons im Wortsinn, gehören aber zur selben
Familie – und die Seite hat nur vier Sportarten. Die genaue Form steht
in `art2`: **Straße, Cross, Duathlon, Aquathlon, Swimrun, Quadrathlon,
Indoor**. Damit ist auch das Kategorie-Panel für Triathlon gefüllt, das
bis dahin leer gewesen wäre.

Dabei gilt: **das Format vor dem Gelände**. Ein „Baltic X Cross
Duathlon" ist ein *Duathlon*, der im Gelände stattfindet – danach sucht
jemand, nicht nach „Cross".

### Was dabei noch aufgefallen ist (und nur gemeldet wird)

Zwei Sorten Fehler stecken noch in den Triathlon-Daten. Beide werden von
`clean_events.py` **gemeldet, nicht korrigiert** – aus demselben Grund
wie bei den verdächtigen Distanzen:

1. **Teilstrecken als eigene Zeile** (5 Fälle). Die Quellen listen bei
   einem Triathlon oft die drei Disziplinen einzeln auf, und daraus
   wurde je eine Zeile: „Ironman Hamburg · 42,2 km Laufen entlang der
   Alster" ist der Laufteil, keine Anmeldemöglichkeit. Ob so eine Zeile
   wirklich eine Teilstrecke ist oder doch ein eigener Wettbewerb (es
   gibt Staffeln und Einzelstarts), sagt die Ausschreibung – nicht ein
   Muster.
2. **Distanzen, die zu keinem Format passen** (44 Fälle). Ein Triathlon
   ist die Summe aus Schwimmen, Rad und Laufen; die üblichen Formate
   liegen bei ~26, ~52, 113 und 226 km. „Ironman Hamburg · 178 km" ist
   die Radstrecke, „Ironman 70.3 Kraichgau · 52 km" die olympische
   Distanz statt der 113 km einer 70.3. Automatisch überschreiben wäre
   falsch: Viele Ironman-Veranstaltungen tragen an einem Wochenende
   mehrere Wettbewerbe aus, die 52 km könnten also der 5150 sein, nur
   falsch zugeordnet. Geprüft wird das einzeln, bestätigte Fälle kommen
   als Override in `manual_overrides.json`.

Die Meldungen stehen bei jedem Lauf von `clean_events.py` im Bericht
(mit `--quiet` nur als Zahl).

## Die Mastersuche

Ein Feld links von der Trefferzahl, das über **Eventname, Wettbewerb und
Ort** sucht: „münchen" findet die Events in München, „marathon" die
Marathons – **und zwar in beiden Sprachen**. Wer die Seite auf Deutsch
stehen hat, kann „Germany", „Munich" oder „running" eingeben und bekommt
dieselben Treffer wie mit „Deutschland", „München", „Laufen". Dafür
durchsucht `sucheHeuhaufen()` zusätzlich die Übersetzungen von Land,
Sportart, Kategorie und Ort. Dieselbe Regel steht ein zweites Mal in
`functions/index.js`, damit ein **Abo** genau das trifft, was die Suche
gezeigt hat; `test_suche_uebersetzungen` vergleicht beide Tabellen.

Städte mit einem eigenen englischen Namen stehen in der englischen
Fassung auch so da: **München → Munich, Köln → Cologne, Nürnberg →
Nuremberg, Hannover → Hanover, Braunschweig → Brunswick, Konstanz →
Constance, Wien → Vienna, Zürich → Zurich, Genf → Geneva, Luzern →
Lucerne**. Bewusst nur echte Exonyme – Orte, die im Englischen anders
*heißen*, nicht bloß anders geschrieben werden. Die übrigen ~1.500 Orte
bleiben in beiden Sprachen gleich. Die Filter je Spalte bleiben daneben bestehen – sie sind das
genaue Werkzeug (Umkreis, Zeitraum, Distanzkategorie), die Mastersuche
der schnelle Zugriff.

Drei Entscheidungen dahinter:

1. **Ein eigener Filter, nicht das Namensfeld.** In `filters.js` gibt es
   jetzt `state.suche` (Adresse `?s=`) **neben** dem unveränderten
   `nameQuery` (`?q=`, Textfeld der Spalte „Name"). Würde die
   Mastersuche auf `nameQuery` schreiben, filterte der Spaltenfilter
   „Name" plötzlich auch nach Orten – ein Filter, der etwas anderes tut
   als seine Spalte sagt.
2. **Sie gilt auch für die Karte.** Weil sie in `EF.matchEvent()` steckt,
   filtert sie beide Seiten, steht als Chip in der Leiste und übersteht
   den Wechsel Liste → Karte → Liste.
3. **Sie gehört ins Abo.** Wer „München" gesucht hat und dann
   abonniert, will Events aus München – nicht alles. Damit steht die
   Regel ein drittes Mal in `functions/index.js` (wie schon
   `nameQuery`); sie ist dort absichtlich so schlicht wie hier
   (kleinschreiben, `includes`), damit die Kopien nicht auseinander
   laufen.

Gefiltert wird bei jedem Tastendruck, **neu gezeichnet erst nach
180 ms**: Über 4.000 Events zu filtern und die Tabelle zu bauen kostet
auf einem Handy mehr Zeit als der Abstand zwischen zwei Tastendrücken –
ohne die kurze Pause ruckelte das Tippen. Enter zeichnet sofort.

## Zwei Namen, ein Rennen

Am 19.09.2026 standen in Gefrees zwei Einträge mit 21 km nebeneinander:
„13. Fichtelgebirgstrailrun" und „Fichtellauf · Halbmarathon". Der
Veranstalter (SC Gefrees, fnwm.de) führt die Veranstaltung selbst als
**„Fichtellauf (Trail + Nordic Walking)"** mit den Strecken 8/14/21 km –
der Trail Run *ist* der Fichtellauf. Zwei Namen, ein Rennen.

Das automatische Dedupe hatte keine Chance: Es vergleicht Datum, Ort,
Distanz und **Namen**, und diese beiden Namen teilen kein einziges Wort.
Der Fall ist per Websuche gegen die Ausschreibung geprüft und mit
`"exclude": true` in `manual_overrides.json` erledigt (dazu die
Korrektur, dass der Fichtellauf ein Trailrun ist und nicht „Straße").

**Automatisch zusammenführen wäre hier falsch.** Die naheliegende Regel
„gleicher Tag + gleicher Ort + gleiche Distanz = Duplikat" würde auch
einen Straßenlauf und einen Trailrun desselben Veranstalters am selben
Tag verschmelzen – ein häufiger, echter Fall. Stattdessen **meldet**
`clean_events.py` solche Paare (aktuell 60), und sie werden einzeln
geprüft. Das ist dieselbe Linie wie bei den verdächtigen Distanzen, aus
demselben Grund.

Eine Falle dabei, die einen Nachmittag kosten kann: Die Distanz im
Override-Schlüssel wird mit `:g` formatiert, also `|21` und **nicht**
`|21.0`. Ein Schlüssel in der falschen Schreibweise wird stillschweigend
nie gefunden – der Override steht in der Datei, sieht richtig aus und
tut nichts. `test_override_schluessel` prüft das jetzt.

## Die Karte zeigt Europa, und die Welt nur einmal

Beim Herauszoomen lag Europa als Briefmarke in einer mehrfach
nebeneinander gezeichneten Weltkarte. Drei Einstellungen beheben das:

- **`noWrap: true`** an der Kachel-Ebene – das ist der Punkt gegen die
  Wiederholung: Ohne das zeichnet Leaflet die Kacheln links und rechts
  der Datumsgrenze beliebig oft weiter.
- **`maxBounds`** auf Europa, mit `maxBoundsViscosity: 1` (harte Kante
  statt Zurückfedern, das sich nach Fehler anfühlt). Europa statt DACH,
  damit die Karte nicht angefasst werden muss, wenn weitere Länder
  dazukommen.
- **Ein gerechneter kleinster Zoom.** Eine feste Zahl geht nicht: Auf
  390 px passt Europa erst bei Zoom 3 ins Bild, auf 1.400 px schon bei
  5. Gerechnet wird über Europas **Breite** (`getBoundsZoom` auf einen
  flachen Streifen über Europas Längengrade) – beide naheliegenden
  Varianten waren daneben, weil Europa hochkant liegt und ein
  Browserfenster quer: „Europa passt ganz ins Bild" ergab auf einem
  breiten, niedrigen Fenster Zoom 3 und damit Kanada bis China im Bild,
  „das Fenster liegt ganz in Europa" ergab Zoom 6 und man konnte DACH
  nicht mehr am Stück sehen.

### Die graue Maske: Deutschland, Österreich, Schweiz heben sich ab

Frankreich und Polen sind auf der Karte zu sehen – sie grenzen an –,
aber sie sind hier nicht das Thema, und ohne Maske sahen sie genauso aus
wie Deutschland. Jetzt liegt alles außerhalb der abgedeckten Länder
unter einem grauen Schleier: Städtenamen und Straßen bleiben lesbar,
treten aber zurück.

Es gab zwei Wege dorthin, und der Nutzer hat sich am 18.09.2026 für den
zweiten entschieden:

1. **Ein Kachel-Anbieter mit label-armem Stil.** Kostet keine eigenen
   Daten – wäre aber ein **zweiter fremder Server**, an den die
   IP-Adresse jedes Besuchers geht. Die OSM-Kacheln sind bisher die
   einzige Ausnahme, die dieses Projekt sich erlaubt. Verworfen.
2. **Eigene Ländergrenzen.** `scripts/build_laender.py` holt sie aus
   **Natural Earth** (`ne_10m_admin_0_countries`, Public Domain),
   schneidet die drei Länder heraus, vereinfacht sie auf ~100 m und
   schreibt `laender.json` (69 KB, 24 KB gezippt). Die Datei liegt im
   Repo und wird vom eigenen Server geliefert – es geht nichts an
   Dritte.

Wie die Maske gezeichnet wird:

- **Ein einziges Polygon**: ein Rechteck über die halbe Welt, mit den
  Ländern als Aussparungen. Das macht `fill-rule: evenodd` möglich, die
  Voreinstellung von Leaflet – jeder weitere Ring kehrt die Füllung um.
  Angenehmer Nebeneffekt: Ein Loch *innerhalb* eines Landes wird von
  selbst wieder grau, und genau das braucht es für Büsingen am
  Hochrhein (deutsch, liegt mitten in der Schweiz).
- **Eine eigene Ebene mit z-index 250**: über den Kartenbildern (200),
  unter Markern und Umkreis (400). Läge sie oben, wären die
  Bündel-Zahlen matt und der Ausgangspunkt halb verdeckt.
- **Sie fängt keine Klicks ab** (`pointer-events: none` und
  `interactive: false`) – sonst wäre kein Marker unter ihr mehr
  anklickbar. Der Rauchtest prüft beides.
- **Geladen wird sie nach den Events**, ohne `await`, und ein Fehlschlag
  bleibt still: Die Maske ist Beiwerk, die Marker sind der Zweck.

### Die flache Karte: Landfläche statt Kacheln in der Übersicht

Seit dem 21.09.2026 folgt die Karte einer Vorlage des Nutzers: In der
Übersicht (bis Zoom 7) ist sie **flach** – die drei Länder als helle
Fläche auf grauem Grund mit feinem Raster, ohne Straßen und Ortsnamen;
erst ab Zoom 8 kommen die OpenStreetMap-Kacheln, weil man dann Orte und
Wege braucht. Dafür zeichnet `zeichneMaske()` aus denselben Umrissen ein
zweites Polygon, die **Landfläche**, in ein Pane mit z-index 150 – also
*unter* den Kacheln (200): Solange die Kacheln per CSS ausgeblendet
sind (`.map-flach`), ist sie die Karte; mit Kacheln verschwindet sie
darunter. Die Kacheln werden dabei nicht abgeschaltet, nur unsichtbar
gemacht – so sind sie beim Hineinzoomen sofort da, und der Rauchtest
kann sie weiter zählen (die Prüfung gegen die doppelte Weltkarte).

**Ein Punkt je Veranstaltung, nicht je Strecke** (vom Nutzer am
21.09.2026 so gewünscht): Die Karte fasst die Zeilen wie die Liste über
Name + Starttag + Ort zusammen (`EED.groupKey`, ein Schlüssel für beide
Seiten und für die Strecken-Pillen der Box). Ein Marker zeigt die Zahl
der Veranstaltungen an seinem Ort, die Bündel summieren sie, und die
Legende nennt dieselbe Zahl wie die Liste beim Zusammenfassen. Welche
Distanzen eine Veranstaltung anbietet, sieht man nach dem Klick: in der
Box als Pillen, im Popup (ab drei Veranstaltungen an einem Ort) als
Spanne („5–42,2 km · 4 Strecken").

Was sonst zur Vorlage gehört: **Bündel** als Kreise in der Akzentfarbe
mit der Zahl der Veranstaltungen und dem Namen des größten Ortes darin
(„349 Köln"); **ein Ort mit genau einer Veranstaltung als Nadel** in der
Farbe ihrer Sportart (Orange Laufen, Grün Fahrrad, Blau Schwimmen, Violett
Triathlon – dieselben Farben wie die Legende unten links und die
Symbole in der Liste); **Orientierungsorte** (graue Punkte: Basel,
Bern, Linz, Wien, Graz …) dort, wo kein Bündel steht; **„Mein
Standort"** unter den Zoom-Knöpfen (öffnet das Ort-Panel und startet die
Ortung – derselbe Weg wie im Panel); die Trefferzahl in der **Legende**
statt in der Werkzeugleiste, die ohne Filter ganz verschwindet; ein
gestrichelter Umkreis; und in der Detail-Box statt des Veranstalters
die **Entfernung** vom Ausgangspunkt („14 km von deinem Standort") sowie
ein Knopf „In der Liste".

Die Beschriftungen ordnen sich selbst: Nach jedem Schwenk oder Zoom
prüft `ordneBeschriftungen()`, welche Ortsnamen einen Nachbarn
überschneiden – die wandern auf die linke Seite ihres Kreises oder
verschwinden (größte Bündel zuerst) –, und welche Orientierungsorte
unter einem Bündel, einem Namen oder einem wichtigeren Ort liegen. Ohne
das stand bei Zoom 6 „252 Hamburg" über dem Namen von Bremerhaven.

## Zwei Farbschemata: hell und dunkel

Die Vorlage der Liste war dunkel, die der Karte hell – beide gelten.
Das Schema hängt an `data-theme` am `<html>` (die Werte in `site.css`:
`:root` dunkel, `:root[data-theme="light"]` hell). Gesetzt wird es von
einem kleinen, in allen drei Seiten wortgleichen Skript im `<head>` –
im Kopf, damit die Seite nicht erst im falschen Schema aufblitzt –, das
die gespeicherte Wahl (`endurance-theme` im lokalen Speicher) vor die
Systemeinstellung stellt. Der Knopf in der Kopfzeile (Sonne im Dunkeln,
Mond im Hellen) schaltet um und merkt sich die Wahl.
`test_farbschema_skript` vergleicht die drei Kopien; der Rauchtest
drückt den Knopf und prüft, dass die Wahl die nächste Seite überlebt.

**Ein weiteres Land dazu** heißt: eine Zeile in `build_laender.py`
(Name → ISO-Code), Skript laufen lassen, `laender.json` mit committen.
Die Schlüssel der Datei sind dieselben Ländernamen wie in `filters.js`
(`LAENDER`) und in `events.json` – `test_laender_maske` vergleicht die
Listen, damit ein neues Land nicht stillschweigend unter dem Schleier
liegen bleibt.

## Die Tabelle: eine Schrift, eine Zeilenhöhe, die ganze Seite

Nach dem ersten Blick des Nutzers auf die fertige Seite (18.09.2026) sind
fünf Dinge an der Liste geändert worden. Alle fünf sind kleine
Eingriffe mit einer klaren Begründung – und keiner davon sollte
zurückgedreht werden:

1. **Die Knöpfe stehen wieder rechts.** Sie waren nach links gerutscht,
   sobald die Reihe unter den Titel umbrach: Ein einzelnes Flex-Element
   auf einer neuen Zeile beginnt am linken Rand, und
   `justify-content: flex-end` am Kasten gilt nur innerhalb einer Zeile.
   `margin-left: auto` an der Knopfreihe löst beides. Dazu liegen alle
   Knöpfe jetzt in **einer** umbrechenden Reihe (der Teilen-Knopf lag
   vorher darunter) – der blaue Kasten ist damit rund 50 px flacher.

2. **Die E-Mail-Adresse steht nicht mehr im Kopf.** „Abmelden" allein
   sagt, dass jemand angemeldet ist; um welches Konto es geht, steht im
   Abo-Dialog. Nebeneffekt, der den Anstoß gab: Die lange Adresse machte
   die Knopfreihe so breit, dass sie überhaupt umbrach.

3. **Der Untertitel beschreibt die Liste, statt sie zu erklären.**
   „Klicke auf eine Kopfzeile-Filterschaltfläche (▾) …" war ein
   Handbuchsatz für etwas, das man sieht. Jetzt steht dort in einer
   Zeile, was drin ist und dass die Liste wöchentlich neu eingesammelt
   wird.

4. **Ab 901 px ist die Seite genau fensterhoch, und nur die Liste
   scrollt.** Vorher war die Tabelle auf `78vh` begrenzt, die Seite aber
   höher: Wer die Seite statt der Liste scrollte, sah die Liste enden und
   darunter eine leere Fläche. Jetzt ist `body` ein Flex-Container über
   die Fensterhöhe, die Liste nimmt den Rest, und Fußzeile samt
   „Event melden" stehen immer sichtbar unten. Auf dem Handy bleibt der
   Seiten-Scroll – dort steht der Detailbereich unter der Tabelle.

5. **Jede Zeile ist 52 px hoch, überall dieselbe Schrift.** Vorher
   sprangen drei Dinge: Unterzeilen und aufgeklappte Veranstaltungen
   waren kleiner gesetzt (0.82rem), die Längen standen als dunkel
   hinterlegte Marken – die aussahen, als könnte man sie anklicken –,
   und eine Veranstaltung mit 15 Wettbewerben hatte 15 solche Marken in
   einer Zelle und war vierfach so hoch wie jede andere Zeile.
   Stattdessen steht dort jetzt die **Spanne**: „5–51 km". Die einzelnen
   Distanzen sieht man aufgeklappt, eine Zeile je Strecke – Datenregel 1
   bleibt unberührt, das war schon vorher nur Anzeige.

Dazu das **Dezimaltrennzeichen**: im Deutschen ein Komma („42,2 km"), im
Englischen ein Punkt. Alles, was eine Zahl mit Nachkommastelle anzeigt,
geht durch `EF.formatNumber()` in `filters.js` – die Länge-Spalte, die
Entfernung, die Spanne, die Filter-Chips und die deutschen
Kategorie-Labels („Olympische Distanz (51,5 km)"; „70.3" bleibt mit
Punkt, das ist der Markenname). Bewusst **kein** `toLocaleString()`: Das
richtet sich nach der Spracheinstellung des Browsers, nicht nach dem
Umschalter DE/EN der Seite. Und bewusst **nicht** im Dateinamen der
Kalenderdatei bzw. im `eventSlug` – die müssen sprachunabhängig bleiben,
sonst zeigt ein geteilter Link ins Leere.

## „Wir haben dein Event nicht?"

Die Liste kommt aus vier Quellen und ist deshalb **nicht vollständig** –
für Österreich, die Schweiz, Schwimmen und Radrennen ist sie es
ausdrücklich nicht. Ein leerer Filter hat damit zwei mögliche Gründe, und
bis jetzt kannte die Seite nur einen davon:

1. Das Event findet noch nicht statt → **Abo** („Neue Events per
   E-Mail"), es kommt eine E-Mail, sobald es auftaucht.
2. Das Event findet statt, steht aber **nicht in unserer Liste** → dieser
   Weg hier.

Deshalb gibt es jetzt „Wir haben dein Event nicht?" – eine leise Zeile
unter der Liste (immer erreichbar) und ein zweiter Knopf in der Box bei
null Treffern. Beide öffnen denselben Dialog.

**Gefragt wird nur nach der Adresse der offiziellen Seite und dem
Namen**, dazu ein optionaler Hinweis. Das ist Absicht:

- Datum, Strecken, Ort und Sportart holen wir uns von genau dieser
  Seite. Abgetippte Angaben wären eine dritte Datenquelle neben den
  Scrapern und `manual_overrides.json` – und die offizielle Seite
  brauchen wir nach Datenregel 2 ohnehin.
- Je weniger Felder, desto eher wird das Formular auch ausgefüllt.
- Ein fehlendes `https://` ergänzt die Seite selbst; alles ohne Punkt im
  Hostnamen und jedes andere Schema wird abgewiesen – dieselbe Bedingung
  steht in den Security Rules.

Gespeichert wird in der Collection `eventSuggestions`: anonyme Anmeldung
wie bei den Fehlermeldungen (ein offener Schreib-Endpunkt wäre eine
Einladung zum Zuspammen), geschlossene Feldliste, und **niemand kann die
Collection lesen** – nur das Admin-SDK:

```bash
python3 scripts/review_reports.py suggestions --credentials <serviceaccount.json>
python3 scripts/review_reports.py suggestions --from-json export.json   # ohne Key
```

**Übernommen wird nichts automatisch.** Ein Hinweis von außen ist eine
Adresse, kein Datensatz: erst robots.txt und Nutzungsbedingungen der
Quelle prüfen, dann ein Scraper oder ein Eintrag in
`manual_overrides.json`. Das ist dieselbe Linie wie bei den
Fehlermeldungen – und sie hat denselben Grund (siehe „Datenqualität").

## Ein einzelnes Event teilen

In der Detail-Box steht oben rechts ein Teilen-Knopf. Geteilt werden die
Angaben, die in der Box stehen, **plus ein Link auf genau dieses Event**
– kein PDF und kein Bild. Die Entscheidung, mit Begründung:

- **Der Link ist für den Empfänger mehr wert als ein Dokument.** Wer ihn
  antippt, landet genau bei diesem Event – mit „Zum Kalender
  hinzufügen", der Veranstalter-Seite und der Karte daneben. Ein PDF
  kann das nicht, und es veraltet: Verlegt der Veranstalter das Rennen,
  ist das PDF für immer falsch.
- **`navigator.share()` öffnet den Teilen-Dialog des Geräts.** Damit
  funktionieren WhatsApp, iMessage, Mail, Signal, Notizen und AirDrop
  auf einmal, ohne dass die Seite einen einzigen Dienst kennen muss.
- **Ein PDF bräuchte eine Bibliothek** (jsPDF o. Ä., ~150–400 KB) für
  ein schlechteres Ergebnis. Wo ein PDF wirklich etwas brächte: die
  ganze gefilterte Liste als Saisonplan. Das ist eine andere Funktion,
  und dafür reicht später ein Druck-Stylesheet (`@media print`) – der
  Browser schreibt daraus selbst ein PDF, ohne eine Zeile Bibliothek.
- **Ohne Teilen-Dialog** (Firefox am Rechner, ältere Safari-Versionen)
  wird Text + Link in die Ablage kopiert, mit derselben Kurzmeldung wie
  „Suche mit Freunden teilen".

Geteilt wird zum Beispiel:

```
Kölner TSC Marathons
17.09.2026 · Köln, Deutschland
Laufen / Straße · 42.2 km
https://…/events.html?event=2026-09-17-kolner-tsc-marathons-42-2km-koln
```

**Die Kennung im Link** ist der `eventSlug` – Datum, Name, Maßzahl, Ort,
dieselbe Zeichenfolge, die auch die `.ics`-Datei benennt (und die
`test_scraper_lib.py` gegen `build_ics.py` prüft). Eine laufende Nummer
wäre wertlos: Sie verschiebt sich, sobald ein Event dazukommt oder ein
vergangenes wegfällt – ein geteilter Link zeigte dann auf ein fremdes
Rennen.

Beim Öffnen eines geteilten Links wählt die Liste das Event aus, lässt
die Filter unangetastet (wer ein Event teilt, teilt nicht seine Suche)
und **scrollt auf Handybreite zur Box** – sonst sähe der Empfänger nur
eine Liste. Der Rauchtest prüft genau diesen Rückweg.

## Seitensymbol und Vorschau beim Teilen

`favicon.svg` (498 Byte) ist das Symbol für Tab und Lesezeichen,
`apple-touch-icon.png` (180 × 180) das für den Startbildschirm von iPhone
und iPad. Beide zeigen dasselbe Streckenprofil in der Akzentfarbe
`#2563eb`; das PNG ist randvoll, weil iOS die Ecken selbst rundet, das SVG
bringt seine Rundung mit (`rx="14"`). Bewusst nur drei Linien und ein
Punkt: bei 16 px bleibt von mehr nichts übrig. Das PNG entsteht aus dem
SVG (Chromium, 180 × 180 abfotografiert) – wird das SVG geändert, muss es
neu erzeugt werden.

Vorher gab es gar kein Symbol. Jeder Browser fragt von sich aus
`/favicon.ico` an, und GitHub Pages antwortete darauf mit seiner
404-Seite: leerer Tab, und auf dem Startbildschirm ein Bildschirmfoto der
Seite statt eines Symbols.

Dazu im Kopf aller drei Seiten `description` und die Open-Graph-Angaben
(`og:title`, `og:description`, `og:site_name`, `twitter:card`). „Suche mit
Freunden teilen" verschickt einen Link auf `events.html`; ohne diese
Angaben zeigen WhatsApp, iMessage und Co. nur die nackte Adresse. Ein
`og:image` fehlt **bewusst**: es verlangt eine absolute Adresse, und die
Domain steht noch nicht fest – nachzutragen, sobald die Seite live ist.

## Tempo der Seite

Die Seite lud spürbar träge – das Aufrufen der Liste ebenso wie jeder
Klick darin. Gemessen wurde mit Playwright unter Handy-Bedingungen
(vierfach gebremste CPU, 1,6 Mbit/s, 150 ms Latenz, Auslieferung mit
gzip wie bei GitHub Pages):

| Weg | vorher | nachher |
|---|---|---|
| `events.html` direkt aufrufen, bis die Liste steht | 3.041 ms | 2.356 ms |
| Startseite → Klick auf „Events" | 2.112 ms | 814 ms |
| Klick auf eine Zeile | 605 ms | 14 ms |
| JavaScript beim Seitenaufruf | + 344 KB Firestore | – |

Fünf Ursachen, fünf Änderungen:

**1. Das Firestore-SDK lud bei jedem Seitenaufruf mit.**
`firebase-firestore-compat.js` ist 344 KB (102 KB gzip) – mehr als App
und Auth zusammen. Gebraucht wird es an genau zwei Stellen, beide sind
Nutzerhandlungen: ein Filterabo speichern und eine Fehlermeldung
abschicken. `auth.js` lädt es jetzt selbst nach
(`ensureDb()`), und `prepareFirestore()` stößt das vorausschauend an,
sobald der Melde-Dialog aufgeht oder die Abo-Box erscheint – beim
Absenden ist dann nichts mehr zu warten.

**2. Die Firebase-Skripte blockierten den Start der Liste.**
Sie standen ohne `defer` vor dem Inline-Skript, und ein klassisches
Skript wartet auf alle davor: `events.json` wurde also erst angefordert,
nachdem eine halbe Megabyte Firebase da war. Jetzt hängt an allen vier
Skripten `defer`. Weil `window.EndauranceAuth` damit später da ist als
das Inline-Skript, gibt es die Warteschlange `window.EE_AUTH_QUEUE`:
Wer zu früh dran ist, legt seinen `onAuthChange`-Listener dort ab,
`auth.js` meldet ihn nach.

**3. Jeder Klick zeichnete die ganze Tabelle neu.**
`render()` baute pro Zeile ein `<tr>`, setzte dessen `innerHTML` (ein
eigener HTML-Parser-Lauf je Zeile), hängte einen eigenen Click-Listener
an und fügte es einzeln ein – bei 4.155 Einträgen viertausendmal alles
davon, und das auch dann, wenn nur eine Zeile ausgewählt wurde. Jetzt
entstehen alle Zeilen als **ein** HTML-String, die Klicks laufen über
**einen** Listener am `<tbody>` (Event-Delegation, die Zeile verrät sich
über `data-idx`/`data-g`). Zwei Folgen davon:

- `waehleZeile()` zeichnet die Tabelle **nicht** neu – eine Auswahl
  hängt nur die Markierung um und füllt den Detailbereich.
- `klappeGruppe()` rührt nur die Zeilen der einen Veranstaltung an
  (`insertAdjacentHTML` bzw. die `.sub-row`-Geschwister entfernen).
  Die Trefferzahl ändert sich dabei ohnehin nicht.

**4. Der Browser maß über 4.000 Zeilen, von denen zwanzig zu sehen sind.**
`tbody tr { content-visibility: auto; contain-intrinsic-size: auto 41px; }`
lässt ihn Layout und Zeichnen für alles überspringen, was gerade nicht
im Bild ist. Das geht nur, weil die Spaltenbreiten fest sind
(`table-layout: fixed`) – sonst müsste er doch jede Zeile ausmessen, um
die Spalten zu verteilen. Ältere Browser ignorieren beide Zeilen.

**5. `events.json` wurde erst am Ende angefordert.**
In `events.html` und `karte.html` steht jetzt ganz oben im Kopf
`<link rel="preload" href="events.json" as="fetch" crossorigin="anonymous">`
– der Download beginnt, bevor der Browser Stylesheet und Skripte
gesehen hat. (Das `crossorigin` muss sein: ohne es passt der
vorgeladene Eintrag nicht zum späteren `fetch()`, und die Datei käme ein
zweites Mal.) Die **Startseite** holt zusätzlich schon einmal
`events.html` und `events.json` per `rel="prefetch"` in den Cache –
niedrige Priorität, läuft erst, wenn die Startseite fertig ist. Deshalb
ist der Klick auf „Events" der Weg, der sich am deutlichsten geändert
hat.

Dazu auf der Karte: Die Popups der ~1.500 Marker entstanden alle sofort,
jedes mit eigenem `linkTo()`-Aufruf. `bindPopup()` nimmt auch eine
Funktion – der Inhalt entsteht jetzt beim Öffnen, und der Link trägt
dadurch sogar die Filter von genau diesem Moment.

Den größeren Teil bringt aber das **Bündeln der Marker**: Statt 1.486
Markern liegen bei Blick auf ganz D/A/CH nur noch 6 Zeichen im DOM.
Gemessen unter Handy-Bedingungen (4× gebremste CPU, 390 px, zwei Läufe
je Fall):

| | mit Bündeln | ohne |
|---|---|---|
| Laden bis zum ersten Marker | 727 / 1.511 ms | 2.000 / 2.437 ms |
| Umkreis 200 km um Stuttgart setzen | 374 / 429 ms | 809 / 885 ms |
| Marker im DOM | 7 | 539–1.486 |

Gemessen wurde mit derselben Seite: Der Fall „ohne" entsteht, indem man
`leaflet.markercluster.js` blockiert – dann greift der Rückfall auf
`L.layerGroup()`. Bei den geplanten >20.000 Events wächst der Unterschied
mit.

## Vorbereitung auf über 20.000 Events

Geplant ist ein großer Datenlauf mit **über 20.000 Events**. Ob die Seite
das trägt, war bisher geschätzt – jetzt ist es gemessen.
`scripts/bench_frontend.py` baut dafür einen synthetischen Datenstand
(die echten Events mehrfach, mit verschobenen Jahren, anderen Namen und
teils anderen Orten) und misst beide Stände unter denselben
Handy-Bedingungen wie oben: 4× gebremste CPU, 1,6 Mbit/s, gzip.

```bash
python3 scripts/bench_frontend.py               # heute + 5-facher Stand
python3 scripts/bench_frontend.py --faktor 10   # ~41.000 Events
```

Die echte `events.json` fasst das Skript nie an und prüft das am Ende
auch nach (einmal ist genau das schiefgegangen: der Messordner entstand
mit *Hardlinks*, und `open(..., "w")` traf dieselbe Inode).

### Gefunden: nicht die Datei war das Problem, sondern der DOM

Mit 20.770 Events lagen **alle** Zeilen im DOM: 317.913 Knoten, 12,2 MB
HTML. Und weil jede Änderung die Tabelle neu baut, kostete danach
*jeder* Handgriff Sekunden:

| 20.770 Events, Handy-Bedingungen | alle Zeilen im DOM | nur ein Fenster |
|---|---|---|
| bis die Liste steht | 8.559 ms | **6.272 ms** |
| Zeilen im DOM | 20.762 (317.913 Knoten, 12,2 MB) | **201 (3.195 Knoten, 0,2 MB)** |
| Zusammenfassen an | 8.203 ms | **237 ms** |
| Zusammenfassen aus | 5.217 ms | **135 ms** |
| nach Name sortieren | 4.580 ms | **742 ms** |
| Filter zurücksetzen | 4.404 ms | **145 ms** |
| Zeile auswählen | 350 ms | **44 ms** |
| Stadt/Ort-Panel öffnen | 4.691 ms | **357 ms** |

Auch beim heutigen Stand (4.154) ist der Unterschied deutlich:
Sortieren 982 → 137 ms, Zusammenfassen 758 → 89 ms, Filter zurücksetzen
736 → 53 ms.

**Das Fenster** (`FENSTER_SCHRITT = 200`, `zeigeMehr()` in
`events.html`) zeichnet nur die ersten 200 Einträge und hängt beim
Scrollen den nächsten Schub an – dieselbe Linie wie `klappeGruppe()`:
anhängen statt neu zeichnen. Wichtig dabei:

- **Gefiltert und sortiert wird weiter über alle Events.** Nur das
  Zeichnen ist begrenzt; die Trefferzahl nennt unverändert die volle
  Zahl („20.762 von 20.762 Events"). Der Rauchtest prüft genau das.
- Unter der letzten Zeile steht ein **Knopf** („Weitere 200 von 3.946
  anzeigen"). Beim Scrollen lädt der nächste Schub von selbst nach –
  der Knopf ist für die Tastatur, für Screenreader und weil die Zahl
  ehrlich sagt, wie viel noch kommt.
- **Mit der Tastatur** holt ↓ am unteren Rand des Fensters den nächsten
  Schub (`nachbarZeile()`), und `End` führt ans Ende des Geladenen. Ohne
  das wäre per Tastatur nur die erste Seite erreichbar.
- `idxZuGruppe` wird für **alle** Gruppen gefüllt, nicht nur für die
  gezeichneten: ausgewählt sein kann auch eine Strecke, die noch nicht
  im DOM steht.
- `content-visibility: auto` bleibt – es spart das Zeichnen der Zeilen
  im Fenster, die gerade nicht im Bild sind.

### Bleibt: die Datei selbst

Nach dem Fenster sind von den 6.272 ms noch **5.405 ms `events.json`**
(827 KB gzip, davon der größte Teil Download bei 1,6 Mbit/s). Das ist
der nächste Schritt, und die Varianten sind durchgerechnet (20.770
Events, gzip-Stufe 6):

| Format | roh | gzip |
|---|---|---|
| wie heute (`indent=2`) | 7,5 MB | 834 KB |
| ohne Einrückung | 6,4 MB | 812 KB |
| + leere Felder weg, `datum_ende` nur wenn mehrtägig | 5,9 MB | 799 KB |
| + Koordinaten auf 4 Stellen (11 m) | 5,8 MB | 747 KB |
| + kurze Schlüssel (`n`, `o`, `d`, …) | 4,5 MB | 714 KB |
| **Spalten-Arrays** (ein Array je Feld) | 3,9 MB | 516 KB |
| **Spalten-Arrays + Wörterbuch** für wiederkehrende Werte | 2,0 MB | **300 KB** |

Die Lehre daraus: Kürzere Schlüssel bringen fast nichts – gzip frisst
Wiederholungen ohnehin. Was wirklich zählt, ist die **Struktur**: ein
Array je Feld, und für Felder mit wenigen verschiedenen Werten (`land`,
`art1`, `art2`, `standort`, `veranstalter_url`) ein Wörterbuch plus
Zahlen-Indizes. 300 statt 827 KB heißt bei 1,6 Mbit/s rund 1,5 s statt
4,1 s.

**Vorgeschlagener Weg** (noch nicht gebaut, absichtlich):

1. `events.json` bleibt **die Quelle**: lesbar, einzeln diffbar – der
   wöchentliche Commit muss durchsehbar bleiben. Scraper,
   `clean_events.py`, `manual_overrides.json`, `build_ics.py` und
   `review_reports.py` arbeiten weiter darauf.
2. Ein neues `scripts/build_web_data.py` erzeugt daraus die kompakte
   Fassung (`events.web.json`) – genau wie `build_ics.py` den Ordner
   `kalender/` erzeugt.
3. Die kompakte Datei wird **nicht committet**, sondern im
   Pages-Workflow vor dem Upload erzeugt. Sonst stünde in jedem
   wöchentlichen Commit ein 2-MB-Klotz, der sich komplett ändert, sobald
   ein Event dazukommt.
4. `filters.js` bekommt den Dekodierer (beide Seiten brauchen ihn), und
   der Loader versucht zuerst die kompakte Datei und **fällt auf
   `events.json` zurück**, wenn sie fehlt – damit `python3 -m
   http.server` lokal unverändert funktioniert.
5. Die CI prüft den Rückweg: `build_web_data.py` erzeugen, dekodieren,
   mit `events.json` vergleichen. Ein Format, das beim Dekodieren etwas
   verliert, fällt sofort auf.

Erst wenn das nicht mehr reicht (deutlich über 40.000 Events), lohnt das
Aufteilen nach Jahr mit Nachladen beim Filtern – das kostet die
Filterlisten ihre Vollständigkeit und ist deshalb der schwerere
Eingriff.

Kleinigkeit am Rande: Ein `favicon.ico` gibt es nicht, jeder
Seitenaufruf holt sich dafür eine 404.

## Lokal testen

Da `events.html` die Datei `events.json` per `fetch` lädt, funktioniert
das direkte Öffnen per Doppelklick in manchen Browsern nicht
(CORS-Einschränkung bei `file://`). Stattdessen lokal einen einfachen
Webserver starten, z. B.:

```bash
python3 -m http.server 8000
```

und dann `http://localhost:8000` im Browser öffnen.

### Rauchtest der Seite

`scripts/smoke_test_frontend.py` nimmt einem das Durchklicken ab. Das
Skript startet selbst einen Server auf einem freien Port, öffnet die drei
Seiten auf Handybreite (390 px) in Chromium und prüft 127 Punkte:

```bash
python3 scripts/smoke_test_frontend.py        # alles, unsichtbar
python3 scripts/smoke_test_frontend.py --sichtbar   # mit Browserfenster
```

Geprüft werden: Laden ohne Skriptfehler und ohne 404, Symbol- und
Vorschau-Angaben im Kopf, Knopfreihe innerhalb des blauen Kastens, kein
waagerechter Überlauf, Detailbereich samt Kalenderdatei (die `.ics` wird
wirklich abgerufen und muss als `text/calendar` kommen, ohne
`download`-Attribut), das Filter-Panel auf Handybreite, das Aufklappen der
zusammengefassten Veranstaltungen (N Strecken = N Zeilen, Marken nur im
zugeklappten Zustand), die Bündelung der Marker auf der Karte (Summe der
Bündel-Zahlen = Event-Zahl der Kopfzeile, Klick klappt ein Bündel auf,
Ausgangspunkt und Umkreis bleiben ungebündelt und verschwinden mit ihrem
Chip), das Fenster der Tabelle (nur ein Schub Zeilen im DOM, volle
Trefferzahl, der Knopf hängt den nächsten Schub an, Filter greifen über
alle Events), die Tastaturbedienung der Liste (genau ein Tab-Stopp,
Pfeiltasten, End, Enter in die Angaben, Escape am Filter-Panel, Fessel
und Fokusrückgabe im Melde-Dialog), der Abo-Dialog samt seiner
Filterleiste (vorbelegt aus der laufenden Suche, das Panel liegt im
Dialog und davor, auch Sportarten ohne heutige Events stehen zur Wahl,
die Liste dahinter bleibt unberührt, Escape schließt erst das Panel und
dann den Dialog), „Wir haben dein Event nicht?" (der Knopf unter der
Liste, die drei Felder, die eigenen Fehlermeldungen statt der
Browser-Blase, beide Wege in der Null-Treffer-Box), dass **alle Zeilen
der Tabelle gleich hoch** sind und dass die Distanz im Deutschen mit
Komma und im Englischen mit Punkt steht, die **Mastersuche** (findet
Orte UND Namen, Chip, `?s=` in der Adresse), das **zweizeilige Datum**
bei mehrtägigen Rennen, den **Events-Knopf der Startseite**, den
**Kartenrahmen** (Herauszoomen endet bei Europa, keine zweite Weltkarte
daneben), die **graue Maske** (vorhanden, unter den Markern, fängt keine
Klicks ab) sowie die Filter über den Weg Liste → Karte → Liste.

Ohne Playwright oder ohne startbares Chromium bricht das Skript mit einem
Hinweis ab und gibt 0 zurück – wie die übersprungenen Scraper. Es ersetzt
`test_scraper_lib.py` nicht, sondern ergänzt es um das, was sich nur im
Browser prüfen lässt.

## GitHub Pages aktivieren (einmalig)

1. Im Repository zu **Settings → Pages** gehen.
2. Unter **Build and deployment → Source** die Option **GitHub Actions**
   auswählen.
3. Nach dem nächsten Push auf diesen Branch deployt der Workflow
   automatisch, und die Seite ist unter der von GitHub angezeigten URL
   erreichbar (üblicherweise
   `https://antdon930.github.io/Enduranceevents/`).

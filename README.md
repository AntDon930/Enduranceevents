# Enduranceevents

Öffentliche Webseite mit einer gefilterten Liste von Ausdauersport-Events
(Laufen, Schwimmen, Rennrad, Triathlon) in Deutschland, Österreich und der
Schweiz.

## Struktur

- `events.json` – Datenquelle mit den Beispiel-Events. Felder pro Event:
  - `land` – Deutschland / Österreich / Schweiz
  - `name` – Name des Events
  - `standort` – Ort des Events
  - `lat` / `lon` – Koordinaten des Standorts (Dezimalgrad), werden für die
    Umkreissuche benötigt
  - `art1` – Laufen / Schwimmen / Rennrad / Triathlon
  - `art2` – Unterkategorie, z. B. Trail / Straße / Mountainbike / Bahn / Freiwasser
  - `datum_start` / `datum_ende` – Datum im Format `YYYY-MM-DD`
  - `laenge_km` – Streckenlänge in Kilometern
  - `veranstalter_url` – Link zur Veranstalter-Website

  **Neues Event ergänzen**: Ort per Kartendienst (z. B. Google Maps – Rechtsklick
  auf den Punkt zeigt die Koordinaten) nachschlagen und als `lat`/`lon` eintragen,
  sonst funktioniert die Umkreissuche für dieses Event nicht.

- `index.html` – Statische Seite (HTML/CSS/JS, keine Build-Schritte), liest
  `events.json` per `fetch` ein. Excel-ähnliche Tabelle: jede Spalte hat einen
  eigenen Filter im Spaltenkopf (▾-Symbol):
  - **Land** – Checkbox-Liste
  - **Name** – Textsuche (Eingabefeld, filtert live während des Tippens)
  - **Standort** – Checkbox-Liste mit *allen* Städten (unabhängig von anderen
    Filtern) plus Umkreissuche: „Aktuellen Standort verwenden" (Browser-
    Geolocation) oder eine Stadt als Ausgangspunkt wählen, dann Radius
    0–5 / 5–20 / 20–50 / 50+ km wählen
  - **Sportart** – Checkbox-Liste (Laufen/Schwimmen/Rennrad/Triathlon)
  - **Kategorie** – Checkbox-Liste, deren Optionen von der Sportart-Auswahl
    abhängen (z. B. bei Schwimmen nur Freiwasser/Schwimmbad, keine
    Trail-Option). Die genaue Zuordnung steht als `ART2_BY_ART1` oben im
    `<script>`-Block in `index.html` und ist als **Platzhalter** markiert –
    bitte anpassen, sobald die endgültige Aufteilung feststeht.
  - **Datum** – aufklappbarer Baum Jahr → Monat → Tag (wie Excels
    Datums-AutoFilter); ein Jahr oder Monat auswählen selektiert automatisch
    alle enthaltenen Tage, einzelne Tage sind ebenfalls wählbar
  - **Länge (km)** – Sportart-Tabs (Laufen/Rennrad/Schwimmen/Triathlon) mit
    sportartspezifischen Distanz-Schnellauswahlen plus dem allgemeinen
    Zahlenbereich von/bis (siehe unten)

  Aktive Filter erscheinen als Chips direkt neben der Ergebnisanzahl links
  oben (einzeln entfernbar), „Alle Filter zurücksetzen" löscht alles auf
  einmal. Klick auf eine Zeile zeigt rechts die Detailansicht.

  **Zweisprachig (DE/EN)**: Umschalter oben rechts. Übersetzt werden alle
  UI-Texte sowie die Werte für Land/Sportart/Kategorie (z. B. „Laufen" ↔
  „Running"); Event-Namen, Städte und Veranstalter-Links bleiben unverändert.
  Die Übersetzungstabellen (`I18N`, `VALUE_TRANSLATIONS`) stehen oben im
  `<script>`-Block in `index.html` – dort auch anpassbar/erweiterbar.

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
  - *Rennrad*: bis 50 km, 50–100 km, 100–150 km, 150–200 km, 200+ km.
  - *Schwimmen*: 1/2/3/5 km, 10+ km (Marathonschwimmen).
  - *Triathlon*: Sprintdistanz, Olympische Distanz (51,5 km), Mitteldistanz /
    70.3 (113 km), Langdistanz / Ironman (226 km) – jeweils mit Toleranz für
    die offiziellen Distanzen.

  Diese Kategorien sind zusätzlich zum allgemeinen Von/Bis-Zahlenbereich
  wählbar (beide Filter werden kombiniert, UND-verknüpft) und stehen als
  `DISTANCE_CATEGORIES`/`DISTANCE_CATEGORY_LABELS` oben in `index.html` –
  dort anpassbar, falls andere Schwellenwerte gewünscht sind.
- `.github/workflows/pages.yml` – Deployt die Seite automatisch auf
  GitHub Pages bei jedem Push auf diesen Branch.

## Eigene Events hinzufügen

Einfach `events.json` um weitere Objekte im gleichen Format ergänzen und
committen – die Seite liest die Datei bei jedem Aufruf neu ein.

## Lokal testen

Da die Seite `events.json` per `fetch` lädt, funktioniert das direkte
Öffnen der `index.html` per Doppelklick in manchen Browsern nicht
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

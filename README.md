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
  - **Länge (km)** – Zahlenbereich von/bis

  Aktive Filter erscheinen als Chips direkt neben der Ergebnisanzahl links
  oben (einzeln entfernbar), „Alle Filter zurücksetzen" löscht alles auf
  einmal. Klick auf eine Zeile zeigt rechts die Detailansicht.
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

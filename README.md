# Enduranceevents

Öffentliche Webseite mit einer gefilterten Liste von Ausdauersport-Events
(Laufen, Schwimmen, Rennrad, Triathlon) in Deutschland, Österreich und der
Schweiz.

## Struktur

- `events.json` – Datenquelle mit den Beispiel-Events. Felder pro Event:
  - `land` – Deutschland / Österreich / Schweiz
  - `name` – Name des Events
  - `standort` – Ort des Events
  - `art1` – Laufen / Schwimmen / Rennrad / Triathlon
  - `art2` – Unterkategorie, z. B. Trail / Straße / Mountainbike / Bahn / Freiwasser
  - `datum_start` / `datum_ende` – Datum im Format `YYYY-MM-DD`
  - `laenge_km` – Streckenlänge in Kilometern
  - `veranstalter_url` – Link zur Veranstalter-Website
- `index.html` – Statische Seite (HTML/CSS/JS, keine Build-Schritte), liest
  `events.json` per `fetch` ein. Links eine filterbare Eventliste, rechts die
  Detailansicht des ausgewählten Events. Filter oben: Art I, Art II,
  Standort und Zeitraum (von/bis).
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

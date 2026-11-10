# Blog-Themenplan

Vom Nutzer am 04.11.2026 gewünscht: „Ja mach eine Liste mit Themen und dann
veröffentlichen wir immer montags einen Blog Artikel!“, kurz darauf: „lass mal
2x in der Woche einen Blog posten. Donnerstag und Montag“. Jeden Montag und
Donnerstag (06:37 Berlin) schreibt die geplante Aufgabe „Blog-Artikel am
Montag und Donnerstag“ (`trig_015LFqPsP972Ny6SzfzezXw2`) das nächste offene Thema
(oberste Zeile mit `[ ]`), hakt es ab (`[x]` + Slug) und veröffentlicht es
auf der Live-Seite (Entwicklungs-Branch, beide Live-Namen). Seit dem 04.11.2026 ist der Blog live (vom Nutzer: „Ja, bitte veröffentliche den Blog … und schreib noch ein paar weitere Artikel dazu“) – die ersten drei Themen sind am selben Tag erschienen.

**Regeln (README „Blog“):**
- Leicht lesbar, motivierend, du-Form, kurze Sätze, keine Angstthemen.
- **Schlüsselthema (Q)**: Gesundheit, Ernährung, Sicherheit, Regeln – hier
  Fußnoten und Quellenliste aus seriösen Quellen (Verbände, Behörden,
  Fachgesellschaften, begutachtete Studien, über Europe PMC geprüft).
  Trotzdem nicht wissenschaftlich schreiben: Ergebnis statt Studiendesign.
- **Lockeres Thema (L)**: Erfahrungswissen, Tipps, Inspiration – ohne
  Fußnoten; nur, wo eine Zahl oder Regel genannt wird, eine Quelle.
- **Event-Thema (E)**: baut auf unseren Daten auf (`events.json`) und
  verlinkt gefilterte Listen; nur echte, sichtbare Events nennen.
- Bild aus `marketing/instagram/hintergruende/` (Bildregel: keine
  erkennbaren Gesichter), nach `bilder/blog/<slug>.webp` + `-480`.
- Abwechseln zwischen Sportarten.
- **Jeder Beitrag auch auf Englisch** (seit dem 10.11.2026, vom Nutzer
  gewählt: „Alles auf Englisch“): Text zusätzlich als
  `scripts/blog_texte/en/<slug>.html` (gleicher Aufbau, gleiche Fußnoten,
  „Sources“/„All sources accessed on …“, Verweise auf andere Beiträge ohne
  Pfad) und in `blog.json` `titel_en`, `teaser_en`, `bild_alt_en`,
  `bild_nachweis_en`. `build_blog.py` baut daraus `blog/en/<slug>.html`;
  `test_blog` ist rot, solange die englische Fassung fehlt. Im Bericht an
  den Nutzer beide Links nennen (`/blog/<slug>.html` und
  `/blog/en/<slug>.html`). Die englische Fassung wird NEU geschrieben,
  nicht übersetzt: flüssig wie ein englischer Laufblog, eigener knackiger
  Titel (Vorbild des Nutzers: „Tapering: slow is smooth, and smooth is
  fast“), spannende Zwischenüberschriften – Fakten, Fußnoten und Links wie
  im deutschen Text. Einzelheiten README „Blog“, Punkt „Sprache“.

| Termin | Status | Typ | Sportart | Thema |
|---|---|---|---|---|
| Do 05.11.2026 | [x] `carboloading` (04.11.) | Q | Laufen | Carboloading: Was du in den Tagen vor dem Rennen essen solltest |
| Mo 09.11.2026 | [x] `laufen-im-winter` (04.11.) | L | Laufen | Laufen im Winter: So macht Training bei Kälte und Dunkelheit Spaß |
| Do 12.11.2026 | [x] `silvesterlaeufe` (04.11.) | E | Laufen | Silvesterläufe: Das Jahr laufend beenden – die schönsten Läufe zum Jahreswechsel |
| Mo 16.11.2026 | [x] `krafttraining-fuer-laeufer` (05.11.) | Q | Laufen | Krafttraining für Läufer: Die besten Übungen und warum sie helfen |
| Do 19.11.2026 | [x] `crosslaeufe-winterlaufserien` (09.11.) | E | Laufen | Crossläufe und Winterlaufserien: Wettkampfspaß in der kalten Jahreszeit |
| Mo 23.11.2026 | [ ] | L | Triathlon | Wintertraining im Triathlon: Schwimmen, Rolle und Laufband sinnvoll kombinieren |
| Do 26.11.2026 | [ ] | L | Fahrrad | Rollentraining im Winter: So bleibst du auf dem Rad fit, bis die Saison startet |
| Mo 30.11.2026 | [ ] | Q | alle | Regeneration: Schlaf, Muskelkater und lockere Tage richtig nutzen |
| Do 03.12.2026 | [ ] | L | Laufen | Dein erster 10-km-Lauf: Vom Einsteiger zur ersten Startnummer |
| Mo 07.12.2026 | [ ] | E | alle | Geschenkideen für Ausdauersportler: Eine Startnummer statt Socken |
| Do 10.12.2026 | [ ] | L | alle | Saisonplanung 2027: So findest du deine Ziele für das neue Jahr |
| Mo 14.12.2026 | [ ] | E | Laufen | Neujahrsläufe 2027: Mit Schwung ins neue Jahr |
| Do 17.12.2026 | [ ] | Q | Triathlon | Koppeltraining: Warum sich die Beine nach dem Rad so komisch anfühlen |
| Mo 21.12.2026 | [ ] | L | Laufen | Dein erster Trailrun: Was anders ist als auf der Straße |
| Do 24.12.2026 | [ ] | Q | alle | Mentale Stärke: Wie du mit Nervosität vor dem Start umgehst |
| Mo 28.12.2026 | [ ] | L | Fahrrad | Gravel-Events: Das musst du vor deinem ersten Rennen wissen |
| Do 31.12.2026 | [ ] | L | Schwimmen | Kraulen lernen als Erwachsener: Der Weg zum ersten Freiwasserschwimmen |
| Mo 04.01.2027 | [ ] | E | Laufen | Frühjahrs-Halbmarathons 2027: Die schönsten Rennen im März und April |
| Do 07.01.2027 | [ ] | Q | Laufen | Laufschuhe: Worauf es wirklich ankommt (und worauf nicht) |
| Mo 11.01.2027 | [ ] | L | Laufen | Backyard Ultra erklärt: Das Rennen, das erst endet, wenn nur noch einer läuft |
| Do 14.01.2027 | [ ] | Q | alle | Ernährung im Training: Was Ausdauersportler im Alltag wirklich brauchen |
| Mo 18.01.2027 | [ ] | E | Fahrrad | RTF-Saisonstart 2027: Die ersten Radtourenfahrten des Frühjahrs |
| Do 21.01.2027 | [ ] | L | Laufen | Laufen in der Gruppe: Warum ein Lauftreff dich schneller macht |
| Mo 25.01.2027 | [ ] | L | Fahrrad | Dein erster Radmarathon: Vorbereitung auf 200 Kilometer |
| Do 28.01.2027 | [ ] | Q | Laufen | Intervalltraining für Einsteiger: Schneller werden ohne Überforderung |
| Mo 01.02.2027 | [ ] | E | Triathlon | Volkstriathlons 2027: Die besten Rennen für Einsteiger |
| Do 04.02.2027 | [ ] | L | Triathlon | Die Wechselzone: Zehn Tipps für schnelle und entspannte Wechsel |
| Mo 08.02.2027 | [ ] | E | Laufen | Marathons im Frühjahr 2027: Wien, Hamburg, Zürich und mehr |
| Do 11.02.2027 | [ ] | Q | alle | Hitze und Kälte im Wettkampf: Richtig anziehen bei jedem Wetter |
| Mo 15.02.2027 | [ ] | L | Schwimmen | Neoprenanzug kaufen oder leihen: Was du für dein erstes Freiwasserrennen brauchst |
| Do 18.02.2027 | [ ] | E | Schwimmen | Seequerungen: Die schönsten Freiwasser-Events in den Alpen |
| Mo 22.02.2027 | [ ] | L | Laufen | Stadtläufe mit Aussicht: Laufen, wo andere Urlaub machen |
| Do 25.02.2027 | [ ] | Q | alle | Gesund durch Ausdauer: Was regelmäßiges Training für Herz, Kopf und Schlaf tut |
| Mo 01.03.2027 | [ ] | E | Fahrrad | Alpenpässe für alle: Radmarathons über die schönsten Pässe |
| Do 04.03.2027 | [ ] | L | alle | Das erste Rennen nach der Winterpause: So startest du locker in die Saison |
| Mo 08.03.2027 | [ ] | E | Laufen | Trailruns in den Alpen 2027: Die schönsten Einsteiger-Strecken |

Neue Ideen einfach unten anfügen; die Aufgabe nimmt immer die oberste
offene Zeile (das Datum ist nur die Planung). Sind weniger als vier Themen
offen, ergänzt die Aufgabe fünf neue.

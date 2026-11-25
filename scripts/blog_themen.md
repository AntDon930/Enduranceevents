# Blog-Themenplan

Vom Nutzer am 04.11.2026 gewünscht: „Ja mach eine Liste mit Themen und dann
veröffentlichen wir immer montags einen Blog Artikel!“, kurz darauf: „lass mal
2x in der Woche einen Blog posten. Donnerstag und Montag“. Jeden Montag und
Donnerstag – **seit dem 20.11.2026 nachts um 01:23 Berlin** (vom Nutzer: „Wir
haben am Ende der Woche immer noch sehr viele Token offen. Da kannst du nachts
einmal eine aktuelle Sitzung für den Blog Eintrag aufbrauchen.“; **die Nacht
gehört dem Beitrag: gründlich recherchieren, schreiben, gegenlesen,
verbessern – Aufwand ist ausdrücklich erwünscht**, morgens ist er live) –
schreibt die geplante Aufgabe „Blog-Artikel am
Montag und Donnerstag“ (`trig_015LFqPsP972Ny6SzfzezXw2`) das nächste offene Thema
(oberste Zeile mit `[ ]`), hakt es ab (`[x]` + Slug) und veröffentlicht es
auf der Live-Seite (Entwicklungs-Branch, beide Live-Namen). Seit dem 04.11.2026 ist der Blog live (vom Nutzer: „Ja, bitte veröffentliche den Blog … und schreib noch ein paar weitere Artikel dazu“) – die ersten drei Themen sind am selben Tag erschienen.

**Qualitätsanspruch – gilt für JEDEN Beitrag und geht allem anderen vor**
(vom Nutzer am 20.11.2026: „Kannst du in die Blog Beiträge bitte immer schon
viel Aufwand/Arbeit reinstecken. Das soll nicht so klingen als wäre es von
einem 5 Klasseleute geschrieben. Das soll schon alles fundiert sein. Aber
nicht zu wissenschaftlich.“). Wo der Auftrag der geplanten Aufgabe noch
„leicht lesbar“, „keine Studiendetails“ oder „Typ L: ohne Fußnoten,
Erfahrungswissen“ sagt, gilt **das hier**. Maßstab ist ein gutes Fachmagazin
für Hobbysportler: erwachsene Leser, die selbst trainieren und etwas lernen
wollen – kein Schulaufsatz, keine Vorlesung.

1. **Erst recherchieren, dann schreiben.** Vor dem ersten Satz mindestens
   vier bis sechs seriöse Quellen lesen (Verbände, Fachgesellschaften,
   Übersichtsarbeiten und Studien über Europe PMC, Trainingslehre; Hersteller
   nur für Technikdaten). Dabei trennen: Was ist belegt, was ist
   Erfahrungswissen von Trainern, was ist umstritten?
2. **Tiefe statt Tipps-Liste.** Jeder Abschnitt erklärt das *Warum* in ein,
   zwei Sätzen (was im Körper, am Material, im Rennen passiert) und dann die
   praktische Folge. Konkrete Zahlen mit Einheit und Spannbreite (Minuten,
   Puls- oder Wattbereiche, Gramm je Kilogramm, Wochen), Beispiele aus echten
   Trainingssituationen, Unterschiede zwischen Einsteigern und
   Fortgeschrittenen, typische Fehler und woran man sie merkt. Wo die
   Fachwelt uneins ist, sagt der Text das.
3. **5 bis 8 Minuten Lesezeit, Länge aus Inhalt statt Füllstoff** (vom
   Nutzer am 20.11.2026: „Die Länge soll jetzt aber auch nicht länger als
   5-8min Lesezeit sein.“): Ratgeber (Q, L) 1.000–1.600 Wörter,
   Event-Beiträge (E) 900–1.600 (mit Einordnung, nicht nur Aufzählung),
   Wissenschaft (W) 1.300–1.600. **Nie über 1.600 Wörter** – lieber ein
   Unterthema weglassen (und für einen eigenen Beitrag vormerken) als alles
   anzureißen. Gezählt wird der deutsche Text bis zum Abschlusskasten; die
   Lesezeit in `blog.json` ist Wörter ÷ 200, aufgerundet. Das Fazit
   wiederholt nicht den Text, es gibt die zwei, drei Entscheidungen mit, auf
   die es ankommt.
4. **Sprache eines erfahrenen Trainers**, der einem interessierten
   Erwachsenen etwas erklärt. Du-Form und Motivation bleiben (keine
   Angstthemen), aber: wechselnde Satzlängen, Fließtext mit Argument (Listen
   nur, wo es wirklich eine Liste ist), Fachbegriffe erlaubt und beim ersten
   Vorkommen in einem Halbsatz erklärt (Trittfrequenz, Laktatschwelle,
   Superkompensation …). Nicht: leere Superlative („der wichtigste Tipp
   überhaupt“, „super einfach“), Füllsätze („Hier erfährst du …“, „Mehr
   braucht es nicht“), lauter Zwei-Satz-Absätze, Ausrufezeichen-Ton.
5. **Belegt in jedem Beitragstyp.** Jede Zahl und jede Wirkungsaussage
   bekommt eine Fußnote – auch bei L (mindestens drei Quellen) und bei E,
   sobald der Text über unsere Liste hinaus etwas behauptet (Format, Regeln,
   Geschichte). Erfahrungswissen sagt der Text im Satz („Unter Radtrainern
   gilt …“); den Sammelsatz „Alle Tipps sind Erfahrungswerte“ gibt es nicht
   mehr. Nichts schätzen oder zuspitzen, was keine Quelle trägt („fühlt sich
   an wie eineinhalb Stunden“, „du schwitzt doppelt so viel“).
6. **Nicht zu wissenschaftlich** (Ratgeber, Q/L/E): Ergebnis vor Methode –
   kein Studiendesign (Teilnehmerzahl, p-Werte, Konfidenzintervalle), kein
   Jargon ohne Erklärung. Die Tiefe zeigt sich im Verständnis, nicht in
   Fachwörtern. Genauer wird es nur in der Serie Wissenschaft (unten).
7. **Selbstprüfung vor dem Push** – den Text einmal als kritischer Redakteur
   lesen: Lernt jemand, der seit zwei Jahren läuft oder fährt, etwas Neues?
   Ist jede Zahl belegt? Stünde der Absatz so in einem Fachmagazin? Welche
   Sätze kann man streichen, ohne dass etwas fehlt – streichen und durch
   Substanz ersetzen. Die englische Fassung hält denselben Anspruch.

`test_blog` prüft für jeden Beitrag ab dem 21.11.2026 Mindest- und
Höchstlänge, Quellenzahl, Lesezeit und die Länge der englischen Fassung – erfüllt ein
Beitrag das nicht, ist der Test rot und der Beitrag geht nicht live.

**Typen:**
- **Schlüsselthema (Q)**: Gesundheit, Ernährung, Sicherheit, Regeln –
  Fußnoten an jeder nachprüfbaren Aussage, mindestens fünf Quellen
  (Verbände, Behörden, Fachgesellschaften, begutachtete Studien, über Europe
  PMC geprüft).
- **Praxis-Thema (L)**: Training, Ausrüstung, Taktik, Inspiration –
  genauso gründlich recherchiert, mindestens drei Quellen; Fußnoten an
  Zahlen und Wirkungsaussagen.
- **Event-Thema (E)**: baut auf unseren Daten auf (`events.json`) und
  verlinkt gefilterte Listen; nur echte, sichtbare Events nennen.
- **Serie Wissenschaft (W)** (vom Nutzer am 20.11.2026: „Man kann mal als
  Abwechslung einen Wissenschaftlichen Blog hinzufügen wo man wirklich genau
  auf die Biologie und Ausdauer vom laufen eingeht. Aber das ist dann eine
  andere Serie.“): **alle zwei Wochen donnerstags**, im Plan jede vierte
  Zeile. In `blog.json` `"serie": "wissenschaft"` – die Seite zeigt dann das
  Etikett „Wissenschaft“/„Science“, einen Hinweis auf die Serie unter dem
  Titel und in der Übersicht den Filter „Wissenschaft“. Hier darf und soll
  es genau werden: was in Muskel, Herz, Blut, Stoffwechsel und Nervensystem
  passiert, Schritt für Schritt; Fachbegriffe mit Erklärung; Größenordnungen
  mit Einheit; wichtige Studien beim Namen (wer, wann, was gemessen wurde);
  was gesichert ist und was diskutiert wird. Geschrieben für interessierte
  Laien, nicht für Fachkollegen – am Ende ein Abschnitt „Was das für dein
  Training heißt“ (EN „What it means for your training“). 1.300–1.600
  Wörter (7–8 Minuten – ein Mechanismus gründlich statt fünf oberflächlich)
  und mindestens acht Quellen, vorrangig Übersichtsarbeiten und
  Grundlagenstudien, jede über Europe PMC geprüft; Fußnoten an jeder
  Aussage. Verweist auf passende Ratgeber und umgekehrt (Zone 2 ↔
  Mitochondrien, Carboloading ↔ Energie). Eine Tabelle oder eine schlichte
  Grafik (Inline-SVG, Farben über die Variablen, beide Schemata) ist
  willkommen, wenn sie einen Mechanismus zeigt.
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
  Titel („Tapering: train less, race faster“ – die Pointe muss stimmen:
  „slow is smooth, and smooth is fast“ wurde zurückgenommen, weil man beim
  Tapering nur den Umfang senkt, nicht langsamer läuft; der Spruch gehört zum
  Zone-2-Artikel im Plan unten), spannende Zwischenüberschriften – Fakten, Fußnoten und Links wie
  im deutschen Text. Keine ausgedachten Vergleiche (vom Nutzer: „Das
  Beispiel mit der Kerze. Das sagt doch niemand so“) – ein Bild nur, wenn es
  geläufig ist, in beiden Sprachen. Nur Wendungen, die es im Englischen
  wirklich gibt (vom Nutzer: „Run out the year – das ist kein gutes Englisch“;
  richtig war „Finish the year strong“). Einzelheiten README „Blog“, Punkt „Sprache“.

| Termin | Status | Typ | Sportart | Thema |
|---|---|---|---|---|
| Mi 04.11.2026 | [x] `carboloading` (04.11.) | Q | Laufen | Carboloading: Was du in den Tagen vor dem Rennen essen solltest |
| Mi 04.11.2026 | [x] `laufen-im-winter` (04.11.) | L | Laufen | Laufen im Winter: So macht Training bei Kälte und Dunkelheit Spaß |
| Mi 04.11.2026 | [x] `silvesterlaeufe` (04.11.) | E | Laufen | Silvesterläufe: Das Jahr laufend beenden – die schönsten Läufe zum Jahreswechsel |
| Do 05.11.2026 | [x] `krafttraining-fuer-laeufer` (05.11.) | Q | Laufen | Krafttraining für Läufer: Die besten Übungen und warum sie helfen |
| Mo 09.11.2026 | [x] `crosslaeufe-winterlaufserien` (09.11.) | E | Laufen | Crossläufe und Winterlaufserien: Wettkampfspaß in der kalten Jahreszeit |
| Do 12.11.2026 | [x] `wintertraining-triathlon` (12.11.) | L | Triathlon | Wintertraining im Triathlon: Schwimmen, Rolle und Laufband sinnvoll kombinieren |
| Mo 16.11.2026 | [x] `winterkleidung` (16.11.) | L | alle | Winterkleidung für Läufer und Radfahrer: So bleibst du warm, trocken und sichtbar (Vorschlag des Nutzers 12.11.2026; Zwiebelprinzip ausdrücklich gewünscht – im Deutschen so nennen und erklären (Funktionsschicht, wärmende Schicht, Wind-/Regenschutz, welche Materialien wohin), im Englischen „layering“ / „the layering system“, nicht „onion“; Kopf/Hände/Füße, Laufen vs. Rad, Regen und Schnee, Licht und Reflektoren; Überschneidung mit „Laufen im Winter“ verlinken statt wiederholen) |
| Do 19.11.2026 | [x] `rollentraining-winter` (19.11.) | L | Fahrrad | Rollentraining im Winter: So bleibst du auf dem Rad fit, bis die Saison startet |
| Mo 23.11.2026 | [x] `regeneration` (23.11.) | Q | alle | Regeneration: Schlaf, Muskelkater und lockere Tage richtig nutzen |
| Do 26.11.2026 | [ ] | Q | alle | Zone-2-Training: Warum langsam trainieren dich schneller macht (EN-Titel vom Nutzer am 11.11.2026: „Zone 2 training: slow is smooth, and smooth is fast“; Laufen und Rad, Grundlagenausdauer im Winter; Zone 2 ist auch ein Modewort – nur versprechen, was Studien zeigen, Zonen über Herzfrequenz/Atmung/„noch reden können“ erklären) |
| Mo 30.11.2026 | [ ] | L | Laufen | Dein erster 10-km-Lauf: Vom Einsteiger zur ersten Startnummer |
| Do 03.12.2026 | [ ] | W | alle | Mitochondrien und Kapillaren: Was im Muskel passiert, wenn du Grundlagenausdauer trainierst (folgt auf den Zone-2-Beitrag; Kapillarisierung, Mitochondrienbiogenese, Fett- und Kohlenhydratverbrennung, wie schnell Anpassungen kommen und gehen) |
| Mo 07.12.2026 | [ ] | E | alle | Geschenkideen für Ausdauersportler: Eine Startnummer statt Socken |
| Do 10.12.2026 | [ ] | L | alle | Saisonplanung 2027: So findest du deine Ziele für das neue Jahr |
| Mo 14.12.2026 | [ ] | E | Laufen | Neujahrsläufe 2027: Mit Schwung ins neue Jahr |
| Do 17.12.2026 | [ ] | W | alle | Laktat: Warum die „Milchsäure“ kein Abfallprodukt ist (Laktat-Shuttle nach Brooks, Laktatschwelle, warum Laktat nicht den Muskelkater macht, wie Schwellen gemessen werden) |
| Mo 21.12.2026 | [ ] | Q | Triathlon | Koppeltraining: Warum sich die Beine nach dem Rad so komisch anfühlen |
| Do 24.12.2026 | [ ] | L | Laufen | Dein erster Trailrun: Was anders ist als auf der Straße |
| Mo 28.12.2026 | [ ] | Q | alle | Mentale Stärke: Wie du mit Nervosität vor dem Start umgehst |
| Do 31.12.2026 | [ ] | W | alle | VO2max: Was die maximale Sauerstoffaufnahme über deine Ausdauer verrät – und was nicht (Herzminutenvolumen, Sauerstofftransport, Trainierbarkeit und Erblichkeit, Schätzungen der Uhren) |
| Mo 04.01.2027 | [ ] | L | Fahrrad | Gravel-Events: Das musst du vor deinem ersten Rennen wissen |
| Do 07.01.2027 | [ ] | L | Schwimmen | Kraulen lernen als Erwachsener: Der Weg zum ersten Freiwasserschwimmen |
| Mo 11.01.2027 | [ ] | E | Laufen | Frühjahrs-Halbmarathons 2027: Die schönsten Rennen im März und April |
| Do 14.01.2027 | [ ] | W | alle | Das Sportlerherz: Wie sich das Herz an Ausdauertraining anpasst (Schlagvolumen, Ruhepuls, Unterschied zur krankhaften Verdickung freundlich erklärt, keine Angstthemen) |
| Mo 18.01.2027 | [ ] | Q | Laufen | Laufschuhe: Worauf es wirklich ankommt (und worauf nicht) |
| Do 21.01.2027 | [ ] | L | Laufen | Backyard Ultra erklärt: Das Rennen, das erst endet, wenn nur noch einer läuft |
| Mo 25.01.2027 | [ ] | Q | alle | Ernährung im Training: Was Ausdauersportler im Alltag wirklich brauchen |
| Do 28.01.2027 | [ ] | W | Laufen | Woher die Energie kommt: Glykogen, Fett und der Mann mit dem Hammer (Glykogenspeicher, Fettoxidation, warum der Einbruch bei km 30 kommt, Verbindung zu Carboloading) |
| Mo 01.02.2027 | [ ] | E | Fahrrad | RTF-Saisonstart 2027: Die ersten Radtourenfahrten des Frühjahrs |
| Do 04.02.2027 | [ ] | L | Laufen | Laufen in der Gruppe: Warum ein Lauftreff dich schneller macht |
| Mo 08.02.2027 | [ ] | L | Fahrrad | Dein erster Radmarathon: Vorbereitung auf 200 Kilometer |
| Do 11.02.2027 | [ ] | W | Laufen | Laufökonomie: Warum zwei Läufer mit gleicher VO2max verschieden schnell sind (Sauerstoffkosten je km, Sehnen als Federn, Schuhe mit Carbonplatte, was Training daran ändert) |
| Mo 15.02.2027 | [ ] | Q | Laufen | Intervalltraining für Einsteiger: Schneller werden ohne Überforderung |
| Do 18.02.2027 | [ ] | E | Triathlon | Volkstriathlons 2027: Die besten Rennen für Einsteiger |
| Mo 22.02.2027 | [ ] | L | Triathlon | Die Wechselzone: Zehn Tipps für schnelle und entspannte Wechsel |
| Do 25.02.2027 | [ ] | W | alle | Muskelfasern: Sind Ausdauersportler geboren oder gemacht? (Fasertypen I/IIa/IIx, Biopsie-Befunde, Umwandlung durch Training, Rolle der Gene) |
| Mo 01.03.2027 | [ ] | E | Laufen | Marathons im Frühjahr 2027: Wien, Hamburg, Zürich und mehr |
| Do 04.03.2027 | [ ] | Q | alle | Hitze und Kälte im Wettkampf: Richtig anziehen bei jedem Wetter |
| Mo 08.03.2027 | [ ] | L | Schwimmen | Neoprenanzug kaufen oder leihen: Was du für dein erstes Freiwasserrennen brauchst |
| Do 11.03.2027 | [ ] | W | alle | Ermüdung: Kopf oder Muskel? Was dich im Rennen langsamer werden lässt (periphere und zentrale Ermüdung, Modell des „zentralen Gouverneurs“ und seine Kritik, Rolle von Motivation) |
| Mo 15.03.2027 | [ ] | E | Schwimmen | Seequerungen: Die schönsten Freiwasser-Events in den Alpen |
| Do 18.03.2027 | [ ] | L | Laufen | Stadtläufe mit Aussicht: Laufen, wo andere Urlaub machen |
| Mo 22.03.2027 | [ ] | Q | alle | Gesund durch Ausdauer: Was regelmäßiges Training für Herz, Kopf und Schlaf tut |
| Do 25.03.2027 | [ ] | W | alle | Thermoregulation: Wie dein Körper beim Sport die Hitze loswird (Schweiß, Hautdurchblutung, Hitzeakklimatisierung in Tagen, Unterschiede Laufen/Rad/Schwimmen) |
| Mo 29.03.2027 | [ ] | E | Fahrrad | Alpenpässe für alle: Radmarathons über die schönsten Pässe |
| Do 01.04.2027 | [ ] | L | alle | Das erste Rennen nach der Winterpause: So startest du locker in die Saison |
| Mo 05.04.2027 | [ ] | E | Laufen | Trailruns in den Alpen 2027: Die schönsten Einsteiger-Strecken |
| Do 08.04.2027 | [ ] | W | alle | Höhentraining: Was in den Bergen mit deinem Blut passiert (EPO, Hämoglobinmasse, „Live high – train low“, was es Hobbysportlern bringt) |

Neue Ideen einfach unten anfügen; die Aufgabe nimmt immer die oberste
offene Zeile (das Datum ist nur die Planung – am 20.11.2026 für alle offenen
Zeilen auf die tatsächlichen Montage und Donnerstage ab dem 23.11.2026
gesetzt, die erledigten tragen ihren Erscheinungstag). Sind weniger als vier Themen offen, ergänzt die Aufgabe fünf neue –
und hält dabei den Rhythmus: jede vierte Zeile ein Thema der Serie
Wissenschaft (W).

# Auftrag der Blog-Aufgabe

Der Auftragstext der geplanten Aufgabe „Blog-Artikel am Montag und
Donnerstag“ (`trig_015LFqPsP972Ny6SzfzezXw2`), angepasst an
`scripts/blog_themen.md` (vom Nutzer am 20.11.2026: „Bitte den Auftrag an
scripts/blog_themen.md anpassen.“). Ändern lässt sich der Auftrag nur aus der
Unterhaltung, in die die Aufgabe schreibt (`session_01L57Yy3FBRNA6iNmqDySEXr`,
„Clubs I“) – dort genügt: „Bitte setze den Auftrag der Blog-Aufgabe auf den
Text in scripts/blog_auftrag.md.“ Der Text steht unten zwischen den Linien,
genau so übernehmen (`update_trigger`, Feld `prompt`). Wer die Regeln in
`blog_themen.md` später ändert, zieht diese Datei nach.

---

Blog-Artikel (vom Nutzer gewünscht: am 04.11.2026 „immer montags einen Blog Artikel“, kurz danach „2x in der Woche … Donnerstag und Montag“). Läuft seit dem 20.11.2026 nachts um 01:23 Berlin (vom Nutzer: „Da kannst du nachts einmal eine aktuelle Sitzung für den Blog Eintrag aufbrauchen“) – die Nacht gehört dem Beitrag: gründlich recherchieren, schreiben, gegenlesen, verbessern; Aufwand ist ausdrücklich erwünscht. Blog und Clubs sind LIVE; es gibt nur den Entwicklungs-Branch. Arbeite auf dem Live-Stand: git fetch origin claude/endurance-events-website-v1wruf, dann in einem eigenen Worktree auf origin/claude/endurance-events-website-v1wruf arbeiten. Der Menüpunkt „Clubs“ trägt das Schildchen „new“ – nicht anfassen.

MASSGEBLICH sind die Regeln in scripts/blog_themen.md (Abschnitt „Qualitätsanspruch“, „Typen“, Englisch-Pflicht) und im README-Abschnitt „Blog“ – sie gehen diesem Auftrag vor, wo etwas abweicht.

1. Lies scripts/blog_themen.md und den README-Abschnitt „Blog“ (Qualitätsanspruch, Typen Q/L/E/W, Sprache, Quellen, Bildregel). Nimm die oberste Zeile mit Status [ ].
2. Recherchiere ZUERST: mindestens vier bis sechs seriöse Quellen lesen (Verbände, Fachgesellschaften, Behörden, Übersichtsarbeiten und Studien – jede Studie über die Europe-PMC-API geprüft, nichts erfinden, bei 403 nicht umgehen). Trenne Belegtes, Erfahrungswissen von Trainern und Umstrittenes.
3. Schreib den Artikel als scripts/blog_texte/<slug>.html im Aufbau der vorhandenen Beiträge (beitrag-lead, beitrag-text mit h2-Abschnitten, beitrag-cta mit gefiltertem Link auf events.html/karte.html – bei passenden Themen auch auf clubs.html –, danach die beitrag-quellen-Liste). Maßstab: ein gutes Fachmagazin für Hobbysportler – du-Form, motivierend, aber erwachsen; jeder Abschnitt erklärt das Warum und dann die Praxis, mit konkreten Zahlen (Einheit, Spannbreite), Einsteiger vs. Fortgeschrittene, typischen Fehlern; Fließtext statt Tipps-Liste; Fachbegriffe beim ersten Vorkommen erklärt; keine Angstthemen, keine leeren Superlative, keine Füllsätze. Nicht zu wissenschaftlich (kein Studiendesign, keine p-Werte) – außer in der Serie Wissenschaft.
   - Länge 5–8 Minuten: Ratgeber (Q, L) 1.000–1.600 Wörter, Events (E) 900–1.600, Wissenschaft (W) 1.300–1.600 – NIE über 1.600 Wörter; lieber ein Unterthema weglassen und für einen eigenen Beitrag vormerken. lesezeit_min = Wörter ÷ 200, aufgerundet.
   - Typ Q: Fußnote an jeder nachprüfbaren Aussage, mindestens fünf Quellen. Typ L: genauso gründlich, mindestens drei Quellen, Fußnoten an Zahlen und Wirkungsaussagen; Erfahrungswissen sagt der Text im Satz – KEIN Sammelsatz „Alle Tipps sind Erfahrungswerte“. Typ E: nur Events, die in events.json sichtbar sind (ohne pruefung_offen, mit fangzeile.entfernen), mit gefilterten Links (z. B. ?sportart=…&s=…, ?tage=JJJJ-MM-TT); Einordnung statt Aufzählung, Fußnoten, sobald der Text über unsere Liste hinaus etwas behauptet. Typ W (Serie Wissenschaft): "serie": "wissenschaft" in blog.json, mindestens acht Quellen (vorrangig Übersichtsarbeiten und Grundlagenstudien), Mechanismus Schritt für Schritt, wichtige Studien beim Namen, am Ende der Abschnitt „Was das für dein Training heißt“.
   - Wo es passt, auf frühere Beiträge verlinken. Zweispaltige Tabellen mit class="zweispaltig".
4. Englische Fassung: scripts/blog_texte/en/<slug>.html – NEU geschrieben, nicht übersetzt (flüssig wie ein englischer Laufblog, eigener Titel, nur Wendungen, die es im Englischen gibt, keine ausgedachten Vergleiche), gleiche Fakten, Fußnoten und Links, mindestens 85 % so lang wie der deutsche Text; in blog.json titel_en, teaser_en, bild_alt_en, bild_nachweis_en.
5. Titelbild: ein noch nicht im Blog benutztes Foto aus marketing/instagram/hintergruende/ (Nachweis aus hintergruende.json) oder ein freies Wikimedia-Commons-Foto (CC0/CC BY/CC BY-SA, Bildregel: keine Einzelpersonen, keine erkennbaren Gesichter); sonst das am längsten nicht benutzte derselben Sportart, aber nie dasselbe wie im vorigen Beitrag. Als bilder/blog/<slug>.webp 960×640 und -480.webp 480×320; Eintrag in blog.json (indent=1, neuer Beitrag OBEN = Aufmacher) mit datum = heutiges Datum, sportart, kategorie, lesezeit_min, bild, bild_klein, bild_alt, bild_nachweis (und serie bei Typ W).
6. Selbstprüfung als kritischer Redakteur (Punkt 7 in blog_themen.md): Lernt jemand, der seit zwei Jahren trainiert, etwas Neues? Ist jede Zahl belegt? Streichbare Sätze durch Substanz ersetzen – in beiden Sprachen.
7. python3 scripts/build_blog.py (schreibt auch sitemap.xml und blog-suche.json); python3 scripts/build_blog.py --qualitaet darf für den neuen Beitrag nichts melden; python3 scripts/test_scraper_lib.py und python3 scripts/smoke_test_frontend.py müssen grün sein. Ist test_blog rot, den Beitrag verbessern – nie den Test lockern.
8. In scripts/blog_themen.md die Zeile auf [x] setzen und den Slug dahinterschreiben. Commit („Blog: Artikel …“), vorher git pull --rebase, und push auf BEIDE Live-Branches: claude/endurance-events-website-v1wruf und claude/website-access-9d9tg1 (derselbe Commit).
9. Dem Nutzer in zwei, drei Sätzen sagen, welcher Artikel erschienen ist, mit beiden Links (https://endurance-events.de/blog/<slug>.html und https://endurance-events.de/blog/en/<slug>.html). Sind weniger als vier Themen offen: fünf neue Themen unten in die Liste schreiben (abwechselnd Sportarten, Typ Q/L/E, jede vierte Zeile Typ W an einem Donnerstag) und dem Nutzer nennen.

---

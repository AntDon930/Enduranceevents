#!/usr/bin/env python3
"""Was ansteht: der Plan der nächsten Wochen für das Dashboard.

Vom Nutzer am 12.11.2026 gewünscht: „Ich brauch auf der admin Seite bitte
eine Übersicht was alles ansteht. Also ich brauch die Woche (nächsten 7 Tage
inkl. Heute) in Kalenderformat und dann was alles ansteht. Wann suchst du
nach welchen Daten, wann wird ein Blog veröffentlicht, welcher Blog wird
veröffentlicht, Wann suchst du nach weiteren Events,…“

Das Skript sammelt die Termine aus den Stellen, an denen sie wirklich
festgelegt sind, und schreibt sie als JSON (Pages-Workflow, nie committet,
wie marketing/instagram/plan.json); admin.html zeigt daraus die sieben Tage
ab heute als Kalender, dazu „laufend“ und „danach“:

- Datenlauf und Instagram-Läufe: die Zeitpläne in .github/workflows/*.yml
  (UTC, hier in Berliner Zeit umgerechnet). GitHub startet geplante Läufe
  oft Stunden später - die Texte sagen das.
- Geplante Aufgaben (claude.ai): Blog, Clubs-Abgleich, Monatssuche,
  Erinnerungen. Sie stehen nicht im Repo; ihre Zeiten stehen unten in
  GEPLANTE_AUFGABEN und müssen nachgezogen werden, wenn eine Aufgabe
  geändert wird (CLAUDE.md, „Die längeren Rhythmen“).
- Welcher Blog: die offenen Themen in scripts/blog_themen.md der Reihe nach
  (die geplante Aufgabe nimmt immer die oberste Zeile mit „[ ]“), erschienene
  Beiträge aus blog.json.
- Instagram: die Beiträge aus marketing/instagram/plan.json (fehlt die
  Datei, fehlen nur diese Einträge).
- Monat, Quartal, Jahr: die Rhythmen aus CLAUDE.md.

    python3 scripts/wochenplan.py --json wochenplan.json [--tage 60] [--heute JJJJ-MM-TT]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

WURZEL = Path(__file__).resolve().parent.parent
BERLIN = ZoneInfo("Europe/Berlin")
UTC = dt.timezone.utc
ACTIONS = "https://github.com/AntDon930/Enduranceevents/actions/workflows/"

# Die geplanten Aufgaben auf claude.ai (nicht im Repo). Wochentage wie bei
# datetime: Montag = 0. Wer eine Aufgabe ändert, zieht sie hier nach.
GEPLANTE_AUFGABEN = {
    "blog": {"id": "trig_015LFqPsP972Ny6SzfzezXw2", "wochentage": (0, 3), "zeit": "06:37"},
    "clubs": {"id": "trig_01MvVHbqKGeJjdmGLQ7mBqd3", "wochentage": (0, 3), "zeit": "08:56"},
    "monatssuche": {"id": "trig_01NhaaENGay2NUU5tZLraZiP", "monatstag": 1, "zeit": "10:41"},
    "firebase": {"id": "trig_013AV7Nn2GVq1m3LgxL3ukcq", "datum": "2027-01-11", "zeit": "09:00"},
}

TYP_TEXT = {
    "Q": ("Schlüsselthema mit Quellen und Fußnoten", "key topic with sources and footnotes"),
    "L": ("lockeres Thema, Erfahrungswissen", "light topic, practical tips"),
    "E": ("Event-Thema mit Links in unsere Liste", "event topic with links into our list"),
}


def zweisprachig(de: str, en: str) -> dict:
    return {"de": de, "en": en}


# ---------------------------------------------------------------------------
# Zeitpläne der Workflows
# ---------------------------------------------------------------------------
def crons(datei: Path) -> list[str]:
    """Die cron-Ausdrücke einer Workflow-Datei, in ihrer Reihenfolge."""
    text = datei.read_text(encoding="utf-8")
    return re.findall(r"^\s*-\s*cron:\s*['\"]([^'\"]+)['\"]", text, re.M)


def _feld_passt(feld: str, wert: int) -> bool:
    if feld == "*":
        return True
    for teil in feld.split(","):
        if "-" in teil:
            a, b = teil.split("-")
            if int(a) <= wert <= int(b):
                return True
        elif int(teil) == wert:
            return True
    return False


def cron_zeit_berlin(ausdruck: str, tag: dt.date) -> str | None:
    """Läuft der UTC-cron-Ausdruck an diesem Berliner Tag? Dann die Uhrzeit in
    Berliner Zeit („06:00“), sonst None. Nur Minute/Stunde als Zahl, Tag des
    Monats und Monat als *, Wochentag als Liste - mehr brauchen unsere
    Workflows nicht (der Test prüft das)."""
    minute, stunde, mtag, monat, wtag = ausdruck.split()
    if mtag != "*" or monat != "*":
        raise ValueError(f"cron mit festem Tag wird nicht unterstützt: {ausdruck}")
    # Der UTC-Lauf am selben Kalendertag; um 05:00/06:47/15:47 UTC liegt er
    # auch in Berlin am selben Tag.
    utc = dt.datetime(tag.year, tag.month, tag.day, int(stunde), int(minute), tzinfo=UTC)
    cron_wtag = (utc.weekday() + 1) % 7  # cron: Sonntag = 0
    if not _feld_passt(wtag, cron_wtag):
        return None
    lokal = utc.astimezone(BERLIN)
    if lokal.date() != tag:
        return None
    return lokal.strftime("%H:%M")


def scraper_quellen() -> list[str]:
    """Die Hosts der aktiven Scraper (übersprungene Quellen brechen mit
    sys.exit(0) ab und rufen nichts ab - siehe CLAUDE.md „Quellen“)."""
    hosts = []
    for datei in sorted((WURZEL / "scripts").glob("*_scraper.py")):
        text = datei.read_text(encoding="utf-8")
        if re.search(r"^\s*sys\.exit\(0\)", text, re.M):
            continue
        m = re.search(r"https?://(?:www\.)?([a-z0-9.-]+\.[a-z]+)", text)
        if m:
            hosts.append(m.group(1))
    return hosts


# ---------------------------------------------------------------------------
# Blog
# ---------------------------------------------------------------------------
def offene_themen(md: str) -> list[dict]:
    """Die Zeilen mit „[ ]“ aus der Tabelle in blog_themen.md, in ihrer
    Reihenfolge - genau so nimmt sie die geplante Aufgabe."""
    themen = []
    for zeile in md.splitlines():
        if not zeile.startswith("|") or "[ ]" not in zeile:
            continue
        spalten = [s.strip() for s in zeile.strip().strip("|").split("|")]
        if len(spalten) < 5:
            continue
        thema = " | ".join(spalten[4:]).strip()
        # Lange Klammern am Ende sind Arbeitsnotizen („Vorschlag des Nutzers
        # …“), kurze gehören zum Titel („(und worauf nicht)“).
        m = re.search(r"\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)\s*$", thema)
        if m and len(m.group(1)) > 30:
            thema = thema[: m.start()].strip()
        themen.append({"typ": spalten[2], "sportart": spalten[3], "thema": thema})
    return themen


def blog_termine(tage: list[dt.date], heute: dt.date, themen: list[dict], beitraege: list[dict]) -> list[dict]:
    aufgabe = GEPLANTE_AUFGABEN["blog"]
    nach_datum = {}
    for b in beitraege:
        nach_datum.setdefault(b.get("datum"), b)
    offen = list(themen)
    termine = []
    for tag in tage:
        if tag.weekday() not in aufgabe["wochentage"]:
            continue
        b = nach_datum.get(tag.isoformat())
        if b:
            termine.append({
                "datum": tag.isoformat(), "zeit": aufgabe["zeit"], "art": "blog", "wer": "claude",
                "titel": zweisprachig("Blog erschienen: " + b["titel"],
                                      "Blog published: " + (b.get("titel_en") or b["titel"])),
                "text": zweisprachig("Auf Deutsch und Englisch online.", "Online in German and English."),
                "link": zweisprachig(f"blog/{b['slug']}.html", f"blog/en/{b['slug']}.html"),
            })
            continue
        if tag < heute or not offen:
            continue
        th = offen.pop(0)
        typ = TYP_TEXT.get(th["typ"], ("", ""))
        termine.append({
            "datum": tag.isoformat(), "zeit": aufgabe["zeit"], "art": "blog", "wer": "claude",
            "titel": zweisprachig("Blog: " + th["thema"], "Blog: " + th["thema"]),
            "text": zweisprachig(
                f"Die geplante Aufgabe schreibt das nächste Thema aus der Liste ({typ[0]}, "
                f"{th['sportart']}), auf Deutsch und Englisch, und stellt es online.",
                f"The scheduled task writes the next topic on the list ({typ[1]}, "
                f"{th['sportart']}), in German and English, and publishes it."),
            "punkte": zweisprachig(
                ["Thema: oberste offene Zeile in scripts/blog_themen.md",
                 "Titelbild, Tests, Push auf beide Live-Branches → Deploy"],
                ["Topic: first open row in scripts/blog_themen.md (German title)",
                 "Cover photo, tests, push to both live branches → deploy"]),
        })
    return termine


# ---------------------------------------------------------------------------
# Instagram
# ---------------------------------------------------------------------------
def instagram_termine(plan: dict | None, von: dt.date) -> list[dict]:
    termine = []
    for b in (plan or {}).get("beitraege", []):
        datum = b.get("datum", "")
        if datum < von.isoformat():
            continue
        # Die erste Zeile der Caption ist der Satz, mit dem der Beitrag
        # anfängt („Würdest du das schwimmen? 🤔 3,5 km …“); ohne Caption
        # der Text der ersten Folie.
        satz = (b.get("caption") or "").strip().split("\n", 1)[0].strip()
        if not satz:
            folien = b.get("folien") or []
            erste = folien[0] if folien else {}
            satz = " ".join(str(erste.get(k, "")) for k in ("frage", "ueber", "titel", "text") if erste.get(k)).strip()
        termine.append({
            "datum": datum, "zeit": "", "art": "instagram", "wer": "du", "format": b.get("format", ""),
            "titel": zweisprachig("Instagram", "Instagram"),
            "text": zweisprachig(
                (satz + " – " if satz else "") + "Video ab dem Morgen unter „View“ in der Freigabe-Karte, du postest von Hand.",
                (satz + " – " if satz else "") + "Video from the morning under “View” in the approval card, you post it by hand."),
        })
    return termine


# ---------------------------------------------------------------------------
# Der Plan
# ---------------------------------------------------------------------------
def plan(heute: dt.date, tage_anzahl: int = 60) -> dict:
    tage = [heute + dt.timedelta(days=i) for i in range(tage_anzahl)]
    termine: list[dict] = []
    wf = WURZEL / ".github" / "workflows"
    datenlauf_cron = crons(wf / "update-events.yml")
    insta_cron = crons(wf / "instagram.yml")
    quellen = scraper_quellen()

    for tag in tage:
        iso = tag.isoformat()
        # Datenlauf (montags)
        for c in datenlauf_cron:
            zeit = cron_zeit_berlin(c, tag)
            if zeit:
                termine.append({
                    "datum": iso, "zeit": zeit, "art": "daten", "wer": "auto",
                    "titel": zweisprachig("Datenlauf: alle Quellen nach neuen Events",
                                          "Data run: all sources for new events"),
                    "text": zweisprachig(
                        "GitHub Actions, dauert gut 4 Stunden; GitHub startet geplante Läufe oft "
                        "einige Stunden später. Danach Deploy und die Abo-Mails.",
                        "GitHub Actions, takes a good 4 hours; GitHub often starts scheduled runs "
                        "a few hours late. Then deploy and the subscription emails."),
                    "punkte": zweisprachig(
                        [f"{len(quellen)} Quellen: " + ", ".join(quellen),
                         "Gedächtnis: bis 600 Veranstalterseiten vergangener Events – gibt es schon die nächste Ausgabe?",
                         "Instagram-Konten: bis 400 Veranstalterseiten",
                         "Aufräumen, Kalenderdateien, neue auffällige Zeilen in die Korrekturliste",
                         "Commit → Deploy → E-Mails an die Abonnenten"],
                        [f"{len(quellen)} sources: " + ", ".join(quellen),
                         "Memory: up to 600 organiser pages of past events – is the next edition out yet?",
                         "Instagram accounts: up to 400 organiser pages",
                         "Clean-up, calendar files, new suspicious rows into the correction list",
                         "Commit → deploy → emails to subscribers"]),
                    "link": zweisprachig(ACTIONS + "update-events.yml", ACTIONS + "update-events.yml"),
                })
        # Club-Instagram-Profile (montags, Job clubs-instagram)
        for c in insta_cron[2:]:
            zeit = cron_zeit_berlin(c, tag)
            if zeit:
                termine.append({
                    "datum": iso, "zeit": zeit, "art": "clubs", "wer": "auto",
                    "titel": zweisprachig("Club-Profile auf Instagram abholen", "Fetch club profiles from Instagram"),
                    "text": zweisprachig("Job „clubs-instagram“ – liefert erst nach der Einrichtung (To-do 11).",
                                         "Job “clubs-instagram” – delivers only once set up (to-do 11)."),
                })
        # Clubs-Abgleich (Mo + Do, geplante Aufgabe)
        a = GEPLANTE_AUFGABEN["clubs"]
        if tag.weekday() in a["wochentage"]:
            montag = tag.weekday() == 0
            termine.append({
                "datum": iso, "zeit": a["zeit"], "art": "clubs", "wer": "claude",
                "titel": zweisprachig("Clubs: Termine aus Strava" + (" und Instagram" if montag else ""),
                                      "Clubs: dates from Strava" + (" and Instagram" if montag else "")),
                "text": zweisprachig(
                    "Neue Treffs und Einzeltermine der nächsten Tage in clubs.json, vergangene raus, Push → Deploy.",
                    "New meet-ups and one-off dates for the coming days into clubs.json, past ones out, push → deploy."),
            })
        # Wochen-Check (montags, mit Claude in einer Sitzung)
        if tag.weekday() == 0:
            termine.append({
                "datum": iso, "zeit": "", "art": "routine", "wer": "sitzung",
                "titel": zweisprachig("Wochen-Check nach dem Datenlauf", "Weekly check after the data run"),
                "text": zweisprachig(
                    "Wenn du eine Sitzung öffnest: Lauf und Deploy ansehen, Berichte durchgehen, "
                    "neue Ausgaben aus dem Gedächtnis prüfen, Korrekturseite neu bauen.",
                    "When you open a session: check the run and deploy, go through the reports, "
                    "check new editions from memory, rebuild the correction page."),
            })
            termine.append({
                "datum": iso, "zeit": "", "art": "du", "wer": "du",
                "titel": zweisprachig("Firebase-Konsole: Meldungen ansehen", "Firebase console: check reports"),
                "text": zweisprachig("Neue Fehlermeldungen (errorReports) und Event-Vorschläge (eventSuggestions) – "
                                     "was neu ist, im Chat melden.",
                                     "New error reports (errorReports) and event suggestions (eventSuggestions) – "
                                     "report anything new in the chat."),
            })
        # Monatsanfang
        m = GEPLANTE_AUFGABEN["monatssuche"]
        if tag.day == m["monatstag"]:
            termine.append({
                "datum": iso, "zeit": m["zeit"], "art": "suche", "wer": "claude", "selten": True,
                "titel": zweisprachig("Große Monatssuche: neue Quellen, Clubs und Events",
                                      "Big monthly search: new sources, clubs and events"),
                "text": zweisprachig(
                    "Geplante Aufgabe in der Sitzung „Clubs I“ (wie Blog und Clubs), Bericht in scripts/monatssuche/ – "
                    "früher alle drei Monate, seit dem 12.11.2026 jeden Monat.",
                    "Scheduled task in the “Clubs I” session (like blog and clubs), report in scripts/monatssuche/ – "
                    "used to be every three months, monthly since 12 Nov 2026."),
                "punkte": zweisprachig(
                    ["Neue Kalender und Scraper-Quellen je Sportart und Region (robots.txt, Nutzungsbedingungen) – "
                     "ein neuer Scraper nur mit deinem Ja",
                     "Gesperrte Quellen: Haben sich robots.txt oder Bedingungen geändert?",
                     "Neue Clubs und Lauftreffs, die wir noch nicht kennen",
                     "Große Events, die noch fehlen – einzeln an der Veranstalterseite geprüft",
                     "Monatsroutine: raceresult-Kontaktseiten, Seitenabgleich aller Veranstalterseiten"],
                    ["New calendars and scraper sources per sport and region (robots.txt, terms) – "
                     "a new scraper only with your yes",
                     "Blocked sources: have robots.txt or terms changed?",
                     "New clubs and run groups we don't know yet",
                     "Big events still missing – each checked on the organiser's page",
                     "Monthly routine: raceresult contact pages, check against all organiser pages"]),
            })
            termine.append({
                "datum": iso, "zeit": "", "art": "du", "wer": "du",
                "selten": True, "titel": zweisprachig("Monat auswerten", "Review the month"),
                "text": zweisprachig("Statistik und Instagram-Auswertung des Vormonats ansehen.",
                                     "Look at the previous month's statistics and Instagram results."),
            })
            if tag.month in (1, 4, 7, 10):
                termine.append({
                    "datum": iso, "zeit": "", "art": "routine", "wer": "sitzung",
                    "selten": True, "titel": zweisprachig("Quartals-Check", "Quarterly check"),
                    "text": zweisprachig(
                        "In deiner nächsten Sitzung: Geräte-Check (Handy, iPad, Rechner), Updates für "
                        "Leaflet, markercluster und Firebase; du liest Impressum und Datenschutz gegen, "
                        "wenn sich etwas an Daten oder Statistik geändert hat.",
                        "In your next session: device check (phone, iPad, computer), updates for Leaflet, "
                        "markercluster and Firebase; you re-read the legal notice and privacy policy if "
                        "anything about data or statistics changed."),
                })
            if tag.month == 3:
                termine.append({
                    "datum": iso, "zeit": "", "art": "routine", "wer": "sitzung",
                    "selten": True, "titel": zweisprachig("Saisonstart der Quellen", "Sources start the season"),
                    "text": zweisprachig(
                        "BOE, Fricktaler Cup, dsergebnis, swimsports, BRV Timing und fsieben tragen die neue Saison "
                        "ein; von Hand: NordCup, Freiwassercup Bayern, RAD RACE.",
                        "BOE, Fricktal Cup, dsergebnis, swimsports, BRV Timing and fsieben add the new season; "
                        "by hand: NordCup, Freiwassercup Bayern, RAD RACE."),
                })
        f = GEPLANTE_AUFGABEN["firebase"]
        if iso == f["datum"]:
            termine.append({
                "datum": iso, "zeit": f["zeit"], "art": "routine", "wer": "claude", "selten": True,
                "titel": zweisprachig("Erinnerung: Firebase Extensions enden am 31.03.2027",
                                      "Reminder: Firebase Extensions end on 31 Mar 2027"),
                "text": zweisprachig("Mail-Versand auf eine eigene Cloud Function umstellen (To-do 5).",
                                     "Move email sending to our own Cloud Function (to-do 5)."),
            })

    # Blog und Instagram
    try:
        md = (WURZEL / "scripts" / "blog_themen.md").read_text(encoding="utf-8")
        beitraege = json.loads((WURZEL / "blog.json").read_text(encoding="utf-8"))
        termine += blog_termine(tage, heute, offene_themen(md), beitraege)
    except (OSError, ValueError) as fehler:
        print(f"⚠ Blog-Termine fehlen: {fehler}", file=sys.stderr)
    plan_datei = WURZEL / "marketing" / "instagram" / "plan.json"
    insta = None
    if plan_datei.exists():
        try:
            insta = json.loads(plan_datei.read_text(encoding="utf-8"))
        except ValueError:
            insta = None
    termine += [x for x in instagram_termine(insta, heute) if x["datum"] <= tage[-1].isoformat()]

    reihenfolge = {"daten": 0, "blog": 1, "instagram": 2, "clubs": 3, "suche": 4, "routine": 5, "du": 6}
    termine.sort(key=lambda x: (x["datum"], x["zeit"] or "99:99", reihenfolge.get(x["art"], 9)))

    morgens = next((cron_zeit_berlin(c, heute) for c in insta_cron[:1]), None) or "07:47"
    laufend = [
        {"art": "instagram", "wer": "auto",
         "titel": zweisprachig("Instagram-Vorschau", "Instagram preview"),
         "text": zweisprachig(f"jeden Morgen (ab {morgens}): die Videos der nächsten 7 Tage für „View“",
                              f"every morning (from {morgens}): the videos for the next 7 days for “View”")},
        {"art": "daten", "wer": "auto",
         "titel": zweisprachig("Besucherstatistik", "Visitor statistics"),
         "text": zweisprachig("stündlich zusammengerechnet", "aggregated every hour")},
        {"art": "daten", "wer": "auto",
         "titel": zweisprachig("Deploy", "Deploy"),
         "text": zweisprachig("bei jedem Push, nur wenn alle Tests grün sind", "on every push, only when all tests pass")},
        {"art": "du", "wer": "du",
         "titel": zweisprachig("Korrekturseite", "Correction page"),
         "text": zweisprachig("rund 50 Zeilen am Tag prüfen, dann „Korrekturen übernehmen“ im Chat",
                              "check about 50 rows a day, then “apply corrections” in the chat")},
    ]
    return {
        "erzeugt": dt.datetime.now(BERLIN).isoformat(timespec="minutes"),
        "von": tage[0].isoformat(), "bis": tage[-1].isoformat(),
        "termine": termine, "laufend": laufend,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", required=True, help="Zieldatei, z. B. wochenplan.json")
    ap.add_argument("--tage", type=int, default=60)
    ap.add_argument("--heute", help="JJJJ-MM-TT (Tests); Vorgabe: heute in Berlin")
    args = ap.parse_args(argv)
    heute = dt.date.fromisoformat(args.heute) if args.heute else dt.datetime.now(BERLIN).date()
    daten = plan(heute, args.tage)
    Path(args.json).write_text(json.dumps(daten, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(daten['termine'])} Termine {daten['von']} bis {daten['bis']} → {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

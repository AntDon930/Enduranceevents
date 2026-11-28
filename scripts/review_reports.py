#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
review_reports.py
=================

Ablauf für die Fehlermeldungen der Nutzer/innen ("Fehler zu diesem Event
melden" in events.html). Ziel des Ganzen: Die Liste hat inzwischen über
4000 Einträge aus vier Quellen - Fehler findet realistisch nur, wer das
Event kennt. Die Meldungen sind deshalb die beste Datenquelle, die es
hier gibt. Sie werden aber NIE automatisch übernommen: jede Änderung
geht durch die Bestätigung des Betreibers.

Die vier Schritte:

    1. python3 scripts/review_reports.py fetch
       Holt die Meldungen aus Firestore (Collection "errorReports") und
       bündelt sie pro Event in scripts/reports_inbox.json.
       Alternativ ohne Zugangsdaten:  fetch --from-json export.json
       (Export aus der Firebase-Konsole).

    2. python3 scripts/review_reports.py show
       Zeigt die gebündelten Meldungen und alle offenen Vorschläge.
       -> Hier schaut Claude sich die Meldungen an, prüft sie einzeln per
          Websuche gegen die offizielle Ausschreibung und legt daraus
          Vorschläge an (Schritt 3).

    3. python3 scripts/review_reports.py propose \
           --key "48. Hochgratlauf|2026-09-06|12.8" \
           --set laenge_km=12.4 --quelle https://... \
           --grund "Offizielle Ausschreibung nennt 12,4 km"
       Schreibt einen VORSCHLAG in scripts/pending_overrides.json.
       Noch ändert sich an events.json nichts.

    4. python3 scripts/review_reports.py confirm
       Fragt jeden Vorschlag einzeln ab (j/n). Bestätigte Vorschläge
       landen in scripts/manual_overrides.json und wirken ab dem
       nächsten clean_events.py-Lauf; abgelehnte werden verworfen.
       Nicht-interaktiv: confirm --key "..." bzw. reject --key "...".

Warum so umständlich? Siehe README, Abschnitt "Datenqualität": eine
automatische Lösch-/Korrekturregel auf Heuristik-Basis hat in diesem
Projekt schon einmal echte Rennen erwischt. Eine Meldung ist ein Hinweis,
kein Beweis - jemand kann sich irren, das Jahr verwechseln oder Unsinn
schreiben.

Daneben gibt es einen fünften Befehl, der nichts mit den Overrides zu tun
hat:

    python3 scripts/review_reports.py suggestions
       Zeigt die Hinweise auf Veranstaltungen, die in der Liste FEHLEN
       ("Wir haben dein Event nicht?", Collection "eventSuggestions").
       Nur Anzeigen: Ein Hinweis von außen ist eine Adresse, kein
       Datensatz - was daraus wird (Scraper oder Override), entscheidet
       der Betreiber, nachdem robots.txt und Nutzungsbedingungen der
       Quelle geprüft sind.

Personenbezug: reports_inbox.json enthält uid und (bei angemeldeten
Melder/innen) die E-Mail-Adresse und ist deshalb per .gitignore aus dem
Repository ausgenommen. In manual_overrides.json landet nur die fachliche
Begründung, nie die Person.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
INBOX_PATH = SCRIPT_DIR / "reports_inbox.json"
PENDING_PATH = SCRIPT_DIR / "pending_overrides.json"
OVERRIDES_PATH = SCRIPT_DIR / "manual_overrides.json"

COLLECTION = "errorReports"
# Zweite Collection: Hinweise auf Veranstaltungen, die in der Liste FEHLEN
# ("Wir haben dein Event nicht?", siehe auth.js: suggestEvent). Sie werden
# nur ANGEZEIGT - was daraus wird (ein Scraper für die Quelle, ein
# Override, oder nichts), entscheidet der Betreiber. Automatisch
# aufgenommen wird nichts; dieselbe Linie wie bei den Fehlermeldungen.
SUGGESTION_COLLECTION = "eventSuggestions"

# Muss mit REPORT_CATEGORIES in events.html und der Liste in
# firestore.rules übereinstimmen.
CATEGORIES = {
    "laenge": "Länge / Distanz",
    "datum": "Datum",
    "ort": "Stadt / Ort oder Land",
    "url": "Link zur Veranstalter-Website",
    "sportart": "Sportart oder Kategorie",
    "name": "Name der Veranstaltung",
    "doppelt": "Event ist doppelt in der Liste",
    "abgesagt": "Event findet nicht statt / ist abgesagt",
    "sonstiges": "Sonstiges",
}

# Felder, die ein Override setzen darf (siehe _readme in
# manual_overrides.json). Alles andere wäre ein stiller Datenfehler.
ALLOWED_FIELDS = {
    "laenge_km": float,
    "art1": str,
    "art2": str,
    "land": str,
    "standort": str,
    "name": str,
    "veranstalter_url": str,
    "datum_start": str,
    "datum_ende": str,
    "wettbewerb": str,
    "exclude": bool,
}

PENDING_README = (
    "Vorschläge aus Nutzer-Fehlermeldungen, die noch auf die Bestätigung des "
    "Betreibers warten. Angelegt von scripts/review_reports.py propose, "
    "bestätigt/abgelehnt mit confirm bzw. reject. Erst die Bestätigung "
    "schreibt den Eintrag nach manual_overrides.json - nichts hieraus wirkt "
    "von sich aus auf events.json."
)


# ---------------------------------------------------------------------
# JSON-Helfer
# ---------------------------------------------------------------------
def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def load_pending() -> dict:
    data = load_json(PENDING_PATH, None)
    if not data:
        return {"_readme": PENDING_README, "vorschlaege": []}
    data.setdefault("vorschlaege", [])
    return data


# ---------------------------------------------------------------------
# Bündeln
# ---------------------------------------------------------------------
def bundle_key(event: dict) -> str:
    """Der Schlüssel, unter dem Meldungen zusammengefasst werden - und
    zugleich der distanzgenaue Override-Schlüssel (siehe
    scraper_lib.override_keys): "<Name>|<Datum>|<km>". Jede Strecke ist
    ein eigener Eintrag, also muss auch jede Strecke einzeln gemeldet
    und korrigiert werden können."""
    name = (event.get("name") or "?").strip()
    datum = event.get("datum_start") or "?"
    km = event.get("laenge_km")
    if isinstance(km, (int, float)):
        return f"{name}|{datum}|{round(float(km), 1):g}"
    return f"{name}|{datum}"


def bundle_reports(reports: list[dict]) -> dict:
    """Gruppiert die Rohmeldungen pro Event und sortiert die Bündel nach
    Anzahl der Meldungen (die am häufigsten gemeldeten zuerst) - drei
    unabhängige Meldungen zur selben Distanz sind ein deutlich stärkerer
    Hinweis als eine."""
    buckets: dict[str, dict] = OrderedDict()
    for rep in reports:
        event = rep.get("event") or {}
        key = bundle_key(event)
        bucket = buckets.setdefault(key, {
            "schluessel": key,
            "event": event,
            "anzahl": 0,
            "kategorien": {},
            "meldungen": [],
        })
        bucket["anzahl"] += 1
        kat = rep.get("kategorie") or "sonstiges"
        bucket["kategorien"][kat] = bucket["kategorien"].get(kat, 0) + 1
        bucket["meldungen"].append({
            "id": rep.get("id"),
            "kategorie": kat,
            "beschreibung": rep.get("beschreibung") or "",
            "anonym": rep.get("anonym"),
            "email": rep.get("email"),
            "uid": rep.get("uid"),
            "createdAt": rep.get("createdAt"),
            "status": rep.get("status") or "neu",
        })
    ordered = sorted(buckets.values(), key=lambda b: (-b["anzahl"], b["schluessel"]))
    return {
        "_readme": ("Gebündelte Nutzer-Fehlermeldungen, Stand siehe 'abgerufen'. "
                    "Nicht im Repository (enthält uid/E-Mail) - siehe .gitignore."),
        "abgerufen": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "anzahl_meldungen": len(reports),
        "buendel": ordered,
    }


# ---------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------
def firestore_client(credentials: str | None):
    """Admin-Zugriff auf Firestore. Braucht `pip install
    google-cloud-firestore` und einen Service-Account-Key (Firebase-
    Konsole -> Projekteinstellungen -> Dienstkonten -> "Neuen privaten
    Schlüssel generieren"). Das Admin-SDK umgeht die Security Rules -
    nur so sind die Meldungen überhaupt lesbar (siehe firestore.rules:
    allow read: if false)."""
    try:
        from google.cloud import firestore  # type: ignore
    except ImportError:  # pragma: no cover - reine Umgebungsfrage
        sys.exit("google-cloud-firestore fehlt. Entweder\n"
                 "  pip install google-cloud-firestore\n"
                 "oder die Meldungen aus der Konsole exportieren und\n"
                 "  review_reports.py fetch --from-json export.json\n"
                 "benutzen.")
    if credentials:
        return firestore.Client.from_service_account_json(credentials)
    return firestore.Client()


def normalize_report(doc_id: str, data: dict) -> dict:
    created = data.get("createdAt")
    if hasattr(created, "isoformat"):
        created = created.isoformat()
    return {
        "id": doc_id,
        "uid": data.get("uid"),
        "email": data.get("email"),
        "anonym": data.get("anonym"),
        "kategorie": data.get("kategorie"),
        "beschreibung": data.get("beschreibung"),
        "event": data.get("event") or {},
        "status": data.get("status") or "neu",
        "createdAt": created,
    }


def cmd_fetch(args) -> int:
    if args.from_json:
        raw = load_json(Path(args.from_json), None)
        if raw is None:
            sys.exit(f"Datei nicht gefunden: {args.from_json}")
        # Konsolen-Export ist entweder eine Liste von Dokumenten oder ein
        # Objekt {docId: {...}}.
        if isinstance(raw, dict):
            reports = [normalize_report(k, v) for k, v in raw.items()]
        else:
            reports = [normalize_report(d.get("id", str(i)), d)
                       for i, d in enumerate(raw)]
    else:
        client = firestore_client(args.credentials)
        query = client.collection(COLLECTION)
        if not args.all:
            query = query.where("status", "==", "neu")
        reports = [normalize_report(doc.id, doc.to_dict()) for doc in query.stream()]

    inbox = bundle_reports(reports)
    save_json(INBOX_PATH, inbox)
    print(f"{len(reports)} Meldung(en) zu {len(inbox['buendel'])} Event(s) "
          f"gespeichert in {INBOX_PATH.relative_to(SCRIPT_DIR.parent)}")
    return 0


# ---------------------------------------------------------------------
# show
# ---------------------------------------------------------------------
def cmd_show(args) -> int:
    inbox = load_json(INBOX_PATH, None)
    if inbox:
        print(f"Meldungen ({inbox.get('anzahl_meldungen', 0)}), abgerufen "
              f"{inbox.get('abgerufen', '?')}:\n")
        for bucket in inbox.get("buendel", []):
            ev = bucket.get("event", {})
            kats = ", ".join(f"{CATEGORIES.get(k, k)} ({v}x)"
                             for k, v in sorted(bucket["kategorien"].items(),
                                                key=lambda kv: -kv[1]))
            print(f"  [{bucket['anzahl']}x] {bucket['schluessel']}")
            print(f"        {ev.get('standort') or '?'} · {ev.get('art1') or '?'}"
                  f" / {ev.get('art2') or '-'} · {ev.get('veranstalter_url') or 'kein Link'}")
            print(f"        {kats}")
            for m in bucket["meldungen"]:
                print(f"        - \"{m['beschreibung']}\"")
            print()
    else:
        print(f"Keine Inbox ({INBOX_PATH.name} fehlt) - erst 'fetch' laufen lassen.\n")

    pending = load_pending()
    offen = [v for v in pending["vorschlaege"] if v.get("status") == "offen"]
    print(f"Offene Vorschläge: {len(offen)}")
    for v in offen:
        print_proposal(v)
    return 0


def print_proposal(v: dict) -> None:
    print(f"\n  #{v['id']}  {v['schluessel']}")
    for feld, wert in v["aenderung"].items():
        print(f"      {feld}: {v.get('alt', {}).get(feld, '?')}  ->  {wert}")
    print(f"      Grund:  {v.get('grund', '-')}")
    print(f"      Quelle: {v.get('quelle', '-')}")
    if v.get("melder_ids"):
        print(f"      aus Meldung(en): {', '.join(v['melder_ids'])}")


# ---------------------------------------------------------------------
# propose
# ---------------------------------------------------------------------
def parse_set(pairs: list[str]) -> dict:
    out: dict = {}
    for pair in pairs:
        if "=" not in pair:
            sys.exit(f"--set erwartet feld=wert, bekommen: {pair!r}")
        feld, wert = pair.split("=", 1)
        feld = feld.strip()
        wert = wert.strip()
        if feld not in ALLOWED_FIELDS:
            sys.exit(f"Feld {feld!r} ist kein Override-Feld. Erlaubt: "
                     + ", ".join(sorted(ALLOWED_FIELDS)))
        typ = ALLOWED_FIELDS[feld]
        if typ is float:
            try:
                out[feld] = round(float(wert.replace(",", ".")), 1)
            except ValueError:
                sys.exit(f"{feld}: {wert!r} ist keine Zahl.")
        elif typ is bool:
            out[feld] = wert.lower() in {"1", "true", "ja", "yes"}
        else:
            out[feld] = wert
    if not out:
        sys.exit("Ein Vorschlag ohne --set ändert nichts.")
    return out


def next_proposal_id(pending: dict) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    used = {v["id"] for v in pending["vorschlaege"]}
    for i in range(1, 100):
        candidate = f"{today}-{i:02d}"
        if candidate not in used:
            return candidate
    sys.exit("Mehr als 99 Vorschläge an einem Tag - bitte erst abarbeiten.")


def cmd_propose(args) -> int:
    pending = load_pending()
    aenderung = parse_set(args.set)
    alt = {}
    inbox = load_json(INBOX_PATH, None) or {}
    for bucket in inbox.get("buendel", []):
        if bucket["schluessel"] == args.key:
            alt = {f: bucket["event"].get(f) for f in aenderung if f in bucket["event"]}
            break
    vorschlag = {
        "id": next_proposal_id(pending),
        "schluessel": args.key,
        "aenderung": aenderung,
        "alt": alt,
        "grund": args.grund or "",
        "quelle": args.quelle or "",
        "melder_ids": args.report_id or [],
        "status": "offen",
        "angelegt": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    pending["vorschlaege"].append(vorschlag)
    pending["_readme"] = PENDING_README
    save_json(PENDING_PATH, pending)
    print("Vorschlag angelegt (noch NICHT angewendet):")
    print_proposal(vorschlag)
    return 0


# ---------------------------------------------------------------------
# confirm / reject
# ---------------------------------------------------------------------
def apply_to_overrides(vorschlag: dict) -> None:
    """Schreibt einen bestätigten Vorschlag nach manual_overrides.json.
    Ein bereits vorhandener Eintrag zum selben Schlüssel wird ergänzt,
    nicht ersetzt - dort steckt oft schon recherchierte Arbeit."""
    overrides = load_json(OVERRIDES_PATH, {})
    key = vorschlag["schluessel"]
    # Vorhandenen Schlüssel case-insensitiv wiederfinden, damit nicht
    # zwei Einträge für dasselbe Event entstehen.
    existing_key = next((k for k in overrides
                         if k != "_readme" and k.casefold() == key.casefold()), key)
    entry = dict(overrides.get(existing_key) or {})
    entry.update(vorschlag["aenderung"])
    note_parts = []
    if vorschlag.get("grund"):
        note_parts.append(vorschlag["grund"])
    if vorschlag.get("quelle"):
        note_parts.append(f"Quelle: {vorschlag['quelle']}")
    note_parts.append(f"Nutzer-Meldung, bestätigt am "
                      f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')} "
                      f"(Vorschlag {vorschlag['id']}).")
    note = " ".join(note_parts)
    entry["_note"] = f"{entry['_note']} | {note}" if entry.get("_note") else note
    overrides[existing_key] = entry
    save_json(OVERRIDES_PATH, overrides)


def resolve_proposals(pending: dict, keys: list[str] | None, alle: bool) -> list[dict]:
    offen = [v for v in pending["vorschlaege"] if v.get("status") == "offen"]
    if alle:
        return offen
    if not keys:
        return offen
    wanted = {k.casefold() for k in keys}
    hits = [v for v in offen
            if v["id"].casefold() in wanted or v["schluessel"].casefold() in wanted]
    missing = wanted - {v["id"].casefold() for v in hits} - {v["schluessel"].casefold() for v in hits}
    if missing:
        sys.exit("Kein offener Vorschlag zu: " + ", ".join(sorted(missing)))
    return hits


def cmd_confirm(args) -> int:
    pending = load_pending()
    kandidaten = resolve_proposals(pending, args.key, args.all)
    if not kandidaten:
        print("Keine offenen Vorschläge.")
        return 0

    interaktiv = not args.key and not args.all
    angewendet = 0
    for v in kandidaten:
        if interaktiv:
            print_proposal(v)
            antwort = input("\n    Übernehmen? [j]a / [n]ein / [ü]berspringen: ").strip().lower()
            if antwort.startswith("n"):
                v["status"] = "abgelehnt"
                v["entschieden"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                print("    -> abgelehnt.")
                continue
            if not antwort.startswith("j"):
                print("    -> übersprungen, bleibt offen.")
                continue
        apply_to_overrides(v)
        v["status"] = "angewendet"
        v["entschieden"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        angewendet += 1
        print(f"    -> übernommen in {OVERRIDES_PATH.name}.")

    # Erledigte Vorschläge fliegen aus der Datei; die Begründung steht ab
    # jetzt im _note des Overrides, das ist die dauerhafte Spur.
    pending["vorschlaege"] = [v for v in pending["vorschlaege"]
                              if v.get("status") == "offen"]
    save_json(PENDING_PATH, pending)
    print(f"\n{angewendet} Vorschlag/Vorschläge übernommen. "
          f"Wirksam nach dem nächsten 'python3 scripts/clean_events.py'.")
    return 0


def cmd_reject(args) -> int:
    pending = load_pending()
    kandidaten = resolve_proposals(pending, args.key, args.all)
    for v in kandidaten:
        v["status"] = "abgelehnt"
        v["entschieden"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        print(f"abgelehnt: #{v['id']} {v['schluessel']}")
    pending["vorschlaege"] = [v for v in pending["vorschlaege"]
                              if v.get("status") == "offen"]
    save_json(PENDING_PATH, pending)
    return 0


# ---------------------------------------------------------------------
# mark-done
# ---------------------------------------------------------------------
def cmd_mark_done(args) -> int:
    """Setzt den Status der abgearbeiteten Meldungen in Firestore, damit
    'fetch' sie nicht jedes Mal wieder anschleppt."""
    client = firestore_client(args.credentials)
    collection = getattr(args, "collection", COLLECTION) or COLLECTION
    ids = args.report_id
    if not ids:
        if collection != COLLECTION:
            sys.exit("Für eventSuggestions bitte --report-id angeben "
                     "(es gibt dafür keine Inbox-Datei).")
        inbox = load_json(INBOX_PATH, None) or {}
        ids = [m["id"] for b in inbox.get("buendel", []) for m in b["meldungen"]
               if m.get("id")]
    for doc_id in ids:
        client.collection(collection).document(doc_id).update({"status": args.status})
    print(f"{len(ids)} Meldung(en) auf status={args.status} gesetzt.")
    return 0


# ---------------------------------------------------------------------
# suggestions ("Wir haben dein Event nicht?")
# ---------------------------------------------------------------------
def normalize_suggestion(doc_id: str, data: dict) -> dict:
    created = data.get("createdAt")
    if hasattr(created, "isoformat"):
        created = created.isoformat()
    return {
        "id": doc_id,
        "url": data.get("url"),
        "name": data.get("name"),
        "hinweis": data.get("hinweis") or "",
        "email": data.get("email"),
        "anonym": data.get("anonym"),
        "status": data.get("status") or "neu",
        "createdAt": created,
    }


def cmd_suggestions(args) -> int:
    """Zeigt die Hinweise auf fehlende Veranstaltungen, neueste zuerst.

    Bewusst nur Anzeigen und kein 'propose': Ein Vorschlag von außen ist
    eine Adresse, kein Datensatz. Was daraus wird, hängt an der Quelle -
    robots.txt und Nutzungsbedingungen prüfen, dann ein Scraper oder ein
    Eintrag in manual_overrides.json (siehe CLAUDE.md, Fahrplan Punkt 1).
    Nichts davon lässt sich sinnvoll automatisieren.
    """
    if args.from_json:
        raw = load_json(Path(args.from_json), None)
        if raw is None:
            sys.exit(f"Datei nicht gefunden: {args.from_json}")
        if isinstance(raw, dict):
            eintraege = [normalize_suggestion(k, v) for k, v in raw.items()]
        else:
            eintraege = [normalize_suggestion(d.get("id", str(i)), d)
                         for i, d in enumerate(raw)]
    else:
        client = firestore_client(args.credentials)
        query = client.collection(SUGGESTION_COLLECTION)
        if not args.all:
            query = query.where("status", "==", "neu")
        eintraege = [normalize_suggestion(doc.id, doc.to_dict())
                     for doc in query.stream()]

    eintraege.sort(key=lambda e: e.get("createdAt") or "", reverse=True)
    if not eintraege:
        print("Keine offenen Hinweise auf fehlende Veranstaltungen.")
        return 0
    print(f"{len(eintraege)} Hinweis(e) auf fehlende Veranstaltungen:\n")
    for e in eintraege:
        print(f"  {e['name'] or '(ohne Namen)'}")
        print(f"    {e['url']}")
        if e["hinweis"]:
            print(f"    Hinweis: {e['hinweis']}")
        print(f"    {e['createdAt'] or '?'} · id={e['id']} · status={e['status']}")
        print()
    print("Weiter: Quelle prüfen (robots.txt, Nutzungsbedingungen), dann\n"
          "Scraper oder manual_overrides.json - nie automatisch übernehmen.\n"
          "Erledigt markieren: review_reports.py mark-done --collection "
          "eventSuggestions --report-id <id>")
    return 0


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Nutzer-Fehlermeldungen bündeln, prüfen und nach "
                    "Bestätigung als manuellen Override übernehmen.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_fetch = sub.add_parser("fetch", help="Meldungen aus Firestore holen und bündeln")
    p_fetch.add_argument("--credentials", help="Pfad zum Service-Account-JSON")
    p_fetch.add_argument("--from-json", help="statt Firestore: Export-Datei einlesen")
    p_fetch.add_argument("--all", action="store_true",
                         help="auch bereits erledigte Meldungen")
    p_fetch.set_defaults(func=cmd_fetch)

    p_show = sub.add_parser("show", help="Bündel und offene Vorschläge anzeigen")
    p_show.set_defaults(func=cmd_show)

    p_prop = sub.add_parser("propose", help="Vorschlag anlegen (wirkt noch nicht)")
    p_prop.add_argument("--key", required=True,
                        help='Override-Schlüssel "<Name>|<Datum>|<km>"')
    p_prop.add_argument("--set", action="append", default=[], metavar="FELD=WERT",
                        help="zu setzendes Feld, mehrfach erlaubt")
    p_prop.add_argument("--grund", help="Begründung (landet im _note)")
    p_prop.add_argument("--quelle", help="URL der offiziellen Ausschreibung")
    p_prop.add_argument("--report-id", action="append", default=[],
                        help="zugehörige Meldungs-ID(s)")
    p_prop.set_defaults(func=cmd_propose)

    p_conf = sub.add_parser("confirm", help="Vorschläge bestätigen und übernehmen")
    p_conf.add_argument("--key", action="append",
                        help="Vorschlags-ID oder Schlüssel (ohne: interaktiv)")
    p_conf.add_argument("--all", action="store_true", help="alle offenen übernehmen")
    p_conf.set_defaults(func=cmd_confirm)

    p_rej = sub.add_parser("reject", help="Vorschläge verwerfen")
    p_rej.add_argument("--key", action="append", help="Vorschlags-ID oder Schlüssel")
    p_rej.add_argument("--all", action="store_true", help="alle offenen verwerfen")
    p_rej.set_defaults(func=cmd_reject)

    p_sugg = sub.add_parser("suggestions",
                            help='Hinweise auf fehlende Veranstaltungen anzeigen')
    p_sugg.add_argument("--credentials", help="Pfad zum Service-Account-JSON")
    p_sugg.add_argument("--from-json", help="statt Firestore: Export-Datei einlesen")
    p_sugg.add_argument("--all", action="store_true",
                        help="auch bereits erledigte Hinweise")
    p_sugg.set_defaults(func=cmd_suggestions)

    p_done = sub.add_parser("mark-done", help="Meldungen in Firestore als erledigt markieren")
    p_done.add_argument("--credentials", help="Pfad zum Service-Account-JSON")
    p_done.add_argument("--collection", default=COLLECTION,
                        choices=[COLLECTION, SUGGESTION_COLLECTION],
                        help="welche Collection (Standard: errorReports)")
    p_done.add_argument("--report-id", action="append", default=[],
                        help="einzelne Meldungs-ID(s); ohne: alle aus der Inbox")
    p_done.add_argument("--status", default="erledigt",
                        choices=["erledigt", "abgelehnt", "neu"])
    p_done.set_defaults(func=cmd_mark_done)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

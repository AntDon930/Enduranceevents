#!/usr/bin/env python3
"""
scripts/insta_lauf.py
=====================

Ein Tag des Instagram-Accounts „AusdauerMaschine" in einem Aufruf:
planen (insta_inhalte.py) → Video und Stories rendern (insta_video.py)
→ Caption schreiben, Veranstalter erwähnen (insta_veranstalter.py) → auf
Wunsch veröffentlichen, erst das Reel, dann die Stories (insta_posten.py)
→ Auswertung der letzten Beiträge in die Zusammenfassung des Laufs.

    python3 scripts/insta_lauf.py                         # heute, nur rendern
    python3 scripts/insta_lauf.py --datum 2026-10-16      # ein bestimmter Tag
    python3 scripts/insta_lauf.py --format moment         # Format erzwingen
    python3 scripts/insta_lauf.py --vorschau              # nur PNGs der Folien
    python3 scripts/insta_lauf.py --posten                # und veröffentlichen

Ausgabe in marketing/instagram/ausgabe/<datum>/ (nicht im Repo):
reel.mp4, cover.jpg, story-1.jpg …, caption.txt, beitrag.json. Der Workflow
`.github/workflows/instagram.yml` ruft genau das täglich auf.

Veröffentlicht wird nur mit `--posten` UND dem Google-Zugang des
Workflows (GCP_ACCESS_TOKEN, insta_posten.py – der Instagram-Schlüssel
liegt im Google-Tresor, nicht in GitHub). Mit dem Zugang pflegt JEDER
Lauf den Schlüssel (erneuert ihn nach sieben Tagen), auch ohne
`--posten`; ein Fehler dabei macht den Lauf rot (Mail an den Nutzer),
damit der Schlüssel nicht still in die 60 Tage läuft.
Ein Fehler beim Veröffentlichen lässt den Lauf fehlschlagen (rot in
Actions, Mail an den Nutzer) - das Video liegt trotzdem als Artefakt
bereit und kann von Hand gepostet werden.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import insta_inhalte as inhalte  # noqa: E402
import insta_video as video  # noqa: E402

AUSGABE = inhalte.MARKETING / "ausgabe"


def caption_mit_nachweis(caption: str, nachweis: str | None) -> str:
    """Namensnennung (CC BY/BY-SA verlangt sie) vor die Hashtags."""
    if not nachweis or nachweis in caption:
        return caption
    teile = caption.rsplit("\n\n", 1)
    if len(teile) == 2 and teile[1].startswith("#"):
        return f"{teile[0]}\n\n📷 {nachweis}\n\n{teile[1]}"[:2200]
    return f"{caption}\n\n📷 {nachweis}"[:2200]


def zusammenfassung(text: str) -> None:
    pfad = os.environ.get("GITHUB_STEP_SUMMARY")
    if pfad:
        with open(pfad, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--datum", help="YYYY-MM-DD, Vorgabe: heute (Europe/Berlin)")
    ap.add_argument("--format", choices=inhalte.FORMATE)
    ap.add_argument("--ausgabe", type=Path, help="Zielordner, Vorgabe marketing/instagram/ausgabe/<datum>")
    ap.add_argument("--vorschau", action="store_true", help="nur die Folien als PNG, kein Video")
    ap.add_argument("--posten", action="store_true", help="nach dem Rendern veröffentlichen")
    ap.add_argument("--ohne-erwaehnung", action="store_true",
                    help="die Veranstalterseiten nicht nach Instagram-Namen fragen")
    ap.add_argument("--vorschau-tage", type=int, default=None,
                    help="so viele Tage ab heute als Vorschau für das Dashboard in den Speicher legen "
                         "(Vorgabe: 7 ohne --posten, also im Morgenlauf; 0 mit --posten)")
    ap.add_argument("--freigabe", action="store_true",
                    help="mit --posten: nur veröffentlichen, wenn der Tag im Dashboard freigegeben "
                         "ist oder INSTAGRAM_AUTOPOST=ja gilt (insta_freigabe.py)")
    a = ap.parse_args()

    datum = dt.date.fromisoformat(a.datum) if a.datum else dt.datetime.now(ZoneInfo("Europe/Berlin")).date()
    ziel = a.ausgabe or AUSGABE / datum.isoformat()
    beitrag = inhalte.plane(datum, format_=a.format)
    # Kennung des Inhalts VOR dem Rendern (die Namensnennung des
    # Hintergrunds kommt erst danach in die Caption) - dieselbe, die
    # plan.json trägt und die das Dashboard mit der Freigabe speichert.
    beitrag["hash"] = inhalte.beitrag_hash(beitrag)
    print(f"{datum} ({inhalte.WOCHENTAGE[datum.weekday()]}): Format {beitrag['format']}"
          + (f", Moment {beitrag['moment_id']}" if beitrag.get("moment_id") else "")
          + (f", Clip {beitrag['clip']['id']}" if beitrag.get("clip") else ""))

    logos_holen(beitrag)
    if a.vorschau:
        for p in video.vorschau(beitrag, ziel):
            print(f"  {p}")
        for i, st in enumerate(beitrag.get("stories") or [], 1):
            print(f"  {video.rendere_story(st, ziel / f'story-{i}.jpg', datum.toordinal() + i)}")
        (ziel / "caption.txt").write_text(beitrag["caption"], encoding="utf-8")
        return 0

    if not video.ffmpeg_vorhanden():
        print("ffmpeg/ffprobe fehlen – kein Video möglich.", file=sys.stderr)
        return 1
    meta = video.rendere(beitrag, ziel, seed=datum.toordinal())
    beitrag["video"] = meta
    beitrag["caption"] = caption_mit_nachweis(beitrag["caption"], meta.get("nachweis"))
    # Veranstalter erwähnen - NACH der Kennung, wie die Namensnennung.
    if not a.ohne_erwaehnung:
        try:
            import insta_veranstalter as veranstalter
            namen = veranstalter.erwaehnungen(beitrag)
            beitrag["erwaehnt"] = namen
            beitrag["caption"] = veranstalter.caption_mit_erwaehnung(beitrag["caption"], namen)
            if namen:
                print(f"  Veranstalter erwähnt: {' '.join('@' + n for n in namen)}")
        except Exception as e:                               # noqa: BLE001 - Erwähnung ist Beiwerk
            print(f"  Veranstalter-Namen nicht ermittelt ({type(e).__name__}) - Caption ohne Erwähnung")
    (ziel / "caption.txt").write_text(beitrag["caption"], encoding="utf-8")
    print(f"  Video: {ziel / 'reel.mp4'} ({meta['dauer_s']} s, Hintergrund {meta['hintergrund']['art']}, "
          f"Ton: {meta.get('musik') or 'still'})")
    stories = []
    for i, st in enumerate(beitrag.get("stories") or [], 1):
        pfad = video.rendere_story(st, ziel / f"story-{i}.jpg", datum.toordinal() + i)
        stories.append(pfad)
        print(f"  Story {i} ({st['art']}): {pfad}")

    zusammenfassung(f"## Instagram {datum} – {beitrag['format']}\n\n"
                    f"Video {meta['dauer_s']} s, Hintergrund: {meta['hintergrund']}\n\n"
                    f"```\n{beitrag['caption']}\n```\n")

    # Den Instagram-Schlüssel pflegen - in jedem Lauf mit Google-Zugang,
    # damit er auch ohne Posten nie die 60 Tage erreicht.
    import insta_posten as posten
    z, pflege, pflege_fehler = posten.zugang(), None, None
    if z:
        try:
            pflege = posten.pflege_schluessel(z)
            print(f"  Instagram-Schlüssel: {pflege['alter_tage']} Tage alt"
                  + (f", erneuert (gültig {pflege['gueltig_tage']} Tage)" if pflege["erneuert"] else ""))
        except posten.PostenFehler as e:
            pflege_fehler = str(e)
            print(f"  Instagram-Schlüssel: {pflege_fehler}", file=sys.stderr)
            zusammenfassung(f"**Instagram-Schlüssel:** {pflege_fehler}\n")

    vorschau_tage = a.vorschau_tage if a.vorschau_tage is not None else (0 if a.posten else 7)
    if z and vorschau_tage > 0:
        vorschauen(datum, vorschau_tage, ziel, beitrag["hash"], z)

    darf, grund, story_fehler = True, "", None
    if a.posten and a.freigabe:
        import insta_freigabe as freigabe
        darf, grund = freigabe.darf_posten(beitrag["datum"], beitrag["hash"])
        print(f"  Freigabe: {'posten' if darf else 'NICHT posten'} - {grund}")
        zusammenfassung(f"Freigabe: **{'posten' if darf else 'nicht posten'}** - {grund}\n")
        beitrag["freigabe"] = {"posten": darf, "grund": grund}
    if a.posten and not darf:
        beitrag["veroeffentlicht"] = None
    elif a.posten:
        if not z:
            print("  --posten: kein Google-Zugang (GCP_ACCESS_TOKEN, nur im Workflow nach der "
                  "Einrichtung) – nur gerendert.")
            beitrag["veroeffentlicht"] = None
        elif not pflege:
            print("  --posten: ohne gültigen Instagram-Schlüssel nicht möglich (siehe oben).", file=sys.stderr)
            beitrag["veroeffentlicht"] = None
        else:
            erg = posten.poste_reel(ziel / "reel.mp4", beitrag["caption"], meta.get("thumb_offset_ms"),
                                    z, pflege["token"], kennung=f"reel-{beitrag['datum']}")
            beitrag["veroeffentlicht"] = erg
            print(f"  veröffentlicht: {erg.get('permalink') or erg['media_id']}")
            zusammenfassung(f"Veröffentlicht: {erg.get('permalink') or erg['media_id']}\n")
            # Danach die Stories - ein Fehler hier macht den Lauf rot, das
            # Reel ist dann trotzdem draußen.
            beitrag["stories_veroeffentlicht"] = []
            for i, pfad in enumerate(stories, 1):
                try:
                    st = posten.poste_story(pfad, z, pflege["token"], kennung=f"story-{beitrag['datum']}-{i}")
                    beitrag["stories_veroeffentlicht"].append(st)
                    print(f"  Story {i} veröffentlicht: {st['media_id']}")
                except posten.PostenFehler as e:
                    story_fehler = str(e)
                    print(f"  Story {i}: {story_fehler}", file=sys.stderr)
                    zusammenfassung(f"**Story {i}:** {story_fehler}\n")
            zusammenfassung(f"Stories: {len(beitrag['stories_veroeffentlicht'])} von {len(stories)} veröffentlicht\n")
    (ziel / "beitrag.json").write_text(json.dumps(beitrag, ensure_ascii=False, indent=1), encoding="utf-8")
    if z and pflege:
        try:
            zusammenfassung(auswertung_text(posten.auswertung(z, pflege["token"])))
        except posten.PostenFehler as e:
            print(f"  Auswertung nicht möglich: {e}")
    # Ein kaputter Schlüssel ist rot (Mail an den Nutzer), auch wenn heute
    # nicht gepostet werden sollte - sonst liefe er still in die 60 Tage.
    return 1 if pflege_fehler or story_fehler else 0


def logos_holen(beitrag: dict) -> None:
    """Meldet, welche Logo-Folien (Formate monat/anmeldung) ein GEPRÜFTES
    Logo haben (marketing/instagram/logos/, insta_logos.py) - die übrigen
    zeigen den Namen. Der Lauf holt bewusst nichts aus dem Netz: Ungeprüft
    kam jedes vierte Mal ein Sponsorlogo."""
    import insta_logos
    n, ohne = insta_logos.vorhanden(beitrag)
    if n or ohne:
        print(f"  Logos: {n} geprüft" + (f", Namenskarte für: {', '.join(ohne)}" if ohne else ""))


def vorschauen(datum: dt.date, tage: int, ziel: Path, kennung_heute: str, z: dict) -> None:
    """Die Reels der nächsten Tage rendern und als Vorschau ablegen
    (insta_posten.lade_vorschau) – der „View"-Knopf der Freigabe-Karte in
    admin.html spielt sie ab. Heute ist schon gerendert; die übrigen Tage
    mit demselben Seed wie ihr späterer Lauf, also dasselbe Video (der
    Hintergrund kann sich nur ändern, wenn Pexels anderes liefert). Ein
    Fehler hier lässt den Lauf grün – die Vorschau ist Beiwerk."""
    import tempfile
    import insta_posten as posten
    ok = 0
    for i in range(tage):
        tag = datum + dt.timedelta(days=i)
        try:
            if i == 0:
                ordner, kennung = ziel, kennung_heute
            else:
                b = inhalte.plane(tag)
                kennung = inhalte.beitrag_hash(b)
                logos_holen(b)
                ordner = Path(tempfile.mkdtemp(prefix=f"vorschau-{tag.isoformat()}-"))
                video.rendere(b, ordner, seed=tag.toordinal())
            posten.lade_vorschau(ordner, tag.isoformat(), kennung, z)
            ok += 1
        except Exception as e:                               # noqa: BLE001 - Vorschau ist Beiwerk
            print(f"  Vorschau {tag}: nicht abgelegt ({type(e).__name__}: {str(e)[:120]})")
    print(f"  Vorschauen für das Dashboard: {ok} von {tage} Tagen abgelegt")
    zusammenfassung(f"Vorschauen für das Dashboard: {ok} von {tage} Tagen\n")


def auswertung_text(daten: dict) -> str:
    """Die Auswertung als Markdown für die Zusammenfassung des Laufs:
    je Beitrag eine Zeile, dann der Schnitt je Format (das Format kommt
    aus dem Wochenplan des Tages, insta_inhalte.format_am)."""
    from collections import defaultdict
    zeilen = [f"## Auswertung · {daten.get('follower', '?')} Follower · {daten.get('beitraege_gesamt', '?')} Beiträge\n"]
    if daten.get("hinweis"):
        zeilen.append(f"> {daten['hinweis']}\n")
    felder = ["views", "reach", "likes", "kommentare", "saved", "shares"]
    zeilen.append("| Tag | Format | " + " | ".join(felder) + " |")
    zeilen.append("|---|---|" + "---|" * len(felder))
    je_format: dict[str, list[dict]] = defaultdict(list)
    for b in daten.get("beitraege", []):
        try:
            tag = dt.datetime.fromisoformat(str(b["zeit"]).replace("+0000", "+00:00")).astimezone(ZoneInfo("Europe/Berlin")).date()
        except (KeyError, ValueError):
            continue
        fmt = inhalte.format_am(tag)
        je_format[fmt].append(b)
        werte = " | ".join("" if b.get(f) is None else str(b[f]) for f in felder)
        zeilen.append(f"| [{tag.isoformat()}]({b.get('link') or ''}) | {fmt} | {werte} |")
    if je_format:
        zeilen.append("\n**Schnitt je Format**\n")
        zeilen.append("| Format | Beiträge | " + " | ".join(felder) + " |")
        zeilen.append("|---|---|" + "---|" * len(felder))
        for fmt, liste in sorted(je_format.items()):
            def schnitt(f):
                w = [b[f] for b in liste if isinstance(b.get(f), (int, float))]
                return f"{sum(w) / len(w):.0f}" if w else ""
            zeilen.append(f"| {fmt} | {len(liste)} | " + " | ".join(schnitt(f) for f in felder) + " |")
    return "\n".join(zeilen) + "\n"


if __name__ == "__main__":
    sys.exit(main())

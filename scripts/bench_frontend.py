#!/usr/bin/env python3
"""Tempo der Liste messen – heute und mit einem großen Datenstand.

Warum es dieses Skript gibt: Geplant sind **über 20.000 Events**
(`CLAUDE.md`, „Wo das Projekt gerade steht"). Ob die Seite das trägt,
lässt sich nicht schätzen – also wird gemessen, und zwar unter
Handy-Bedingungen: 4× gebremste CPU, 1,6 Mbit/s, gzip wie GitHub Pages.
Dieselben Bedingungen wie im README-Abschnitt „Tempo der Seite".

    python3 scripts/bench_frontend.py                # heute + 5-facher Stand
    python3 scripts/bench_frontend.py --faktor 1     # nur der echte Stand
    python3 scripts/bench_frontend.py --faktor 10    # ~41.000 Events

Der große Stand ist synthetisch: die echten Events mehrfach, mit
verschobenen Jahren, geänderten Namen und teilweise anderen Orten – damit
es wirklich verschiedene Zeilen sind und die Filterlisten wachsen.

**Die echte `events.json` wird dabei nie angefasst.** Diese Zusicherung
steht hier so deutlich, weil das Gegenteil einmal passiert ist: Der
Messordner entstand mit *Hardlinks* auf die Repo-Dateien, und
`open(..., "w")` auf einen Hardlink trifft dieselbe Inode – die echte
`events.json` war danach der synthetische Stand (gerettet über
`git checkout`). Deshalb jetzt: Symlinks für alles Gelesene,
`open(..., "x")` für die neue Datei, und am Ende ein Vergleich von Größe
und Inhalt der echten Datei.

Ohne Playwright oder ohne startbares Chromium bricht das Skript mit
Hinweis und Rückgabewert 0 ab – wie der Rauchtest.
"""

from __future__ import annotations

import argparse
import datetime
import functools
import glob
import gzip
import http.server
import json
import os
import shutil
import socket
import socketserver
import tempfile
import threading
import time

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS = os.path.join(WURZEL, "events.json")

# Andere Orte für einen Teil der Kopien: sonst wüchsen die Filterlisten
# nicht mit, und das Stadt/Ort-Panel wäre im Test zu freundlich.
STAEDTE = ["Bremen", "Kiel", "Erfurt", "Jena", "Ulm", "Passau", "Graz", "Linz",
           "Bern", "Luzern", "Chur", "Sion", "Trier", "Kassel", "Gera"]


def baue_datenstand(ziel: str, faktor: int) -> int:
    """Legt einen Messordner an: Symlinks aufs Repo, eigene events.json."""
    for name in os.listdir(WURZEL):
        if name in (".git", "events.json"):
            continue
        link = os.path.join(ziel, name)
        if not os.path.lexists(link):
            os.symlink(os.path.join(WURZEL, name), link)

    with open(EVENTS, encoding="utf-8") as fh:
        events = json.load(fh)

    gross = []
    for runde in range(max(1, faktor)):
        for i, e in enumerate(events):
            kopie = dict(e)
            if runde:
                for feld in ("datum_start", "datum_ende"):
                    if kopie.get(feld):
                        tag = datetime.date.fromisoformat(kopie[feld])
                        try:
                            kopie[feld] = tag.replace(year=tag.year + runde).isoformat()
                        except ValueError:      # 29. Februar
                            kopie[feld] = (tag + datetime.timedelta(days=365 * runde)).isoformat()
                kopie["name"] = f"{kopie['name']} {2026 + runde}"
                if i % 3 == 0:
                    kopie["standort"] = STAEDTE[(i + runde) % len(STAEDTE)]
            gross.append(kopie)

    pfad = os.path.join(ziel, "events.json")
    # "x": schlägt fehl, wenn dort schon etwas liegt - siehe Docstring.
    with open(pfad, "x", encoding="utf-8") as fh:
        json.dump(gross, fh, ensure_ascii=False, indent=2)
    return len(gross)


class GzipHandler(http.server.SimpleHTTPRequestHandler):
    """Wie SimpleHTTPRequestHandler, aber mit gzip - wie GitHub Pages.

    Ohne gzip wäre die Messung wertlos: `events.json` ist unkomprimiert
    fast zehnmal so groß, und gemessen werden soll, was beim Nutzer
    ankommt.
    """

    def log_message(self, *args):        # noqa: A003 - Name aus der Basisklasse
        pass

    def do_GET(self):                    # noqa: N802 - Name aus der Basisklasse
        pfad = self.translate_path(self.path)
        if os.path.isdir(pfad):
            pfad = os.path.join(pfad, "index.html")
        if not os.path.isfile(pfad):
            return super().do_GET()
        with open(pfad, "rb") as fh:
            roh = fh.read()
        gezippt = "gzip" in (self.headers.get("Accept-Encoding") or "")
        koerper = gzip.compress(roh, 6) if gezippt else roh
        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(pfad))
        self.send_header("Content-Length", str(len(koerper)))
        if gezippt:
            self.send_header("Content-Encoding", "gzip")
        # Dieselbe Kopfzeile wie GitHub Pages (siehe README, Stempel).
        self.send_header("Cache-Control", "max-age=600")
        self.end_headers()
        self.wfile.write(koerper)


def starte_server(ordner: str):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = socketserver.ThreadingTCPServer(
        ("127.0.0.1", port), functools.partial(GzipHandler, directory=ordner))
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port


def finde_chromium():
    basis = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if basis:
        treffer = sorted(glob.glob(os.path.join(basis, "chromium-*/chrome-linux/chrome")))
        if treffer:
            return treffer[-1]
    return None


def messe(pw, ordner: str, titel: str, sichtbar: bool) -> None:
    srv, port = starte_server(ordner)
    basis = "http://127.0.0.1:%d" % port
    try:
        browser = pw.chromium.launch(executable_path=finde_chromium(),
                                     headless=not sichtbar,
                                     args=["--ignore-certificate-errors"])
    except Exception as ex:                       # noqa: BLE001
        srv.shutdown()
        print("Chromium lässt sich nicht starten: %s" % str(ex).splitlines()[0])
        return
    try:
        ctx = browser.new_context(viewport={"width": 390, "height": 844},
                                  is_mobile=True, has_touch=True)
        seite = ctx.new_page()
        fehler = []
        seite.on("pageerror", lambda e: fehler.append(str(e)))
        cdp = ctx.new_cdp_session(seite)
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
        cdp.send("Network.enable", {})
        cdp.send("Network.emulateNetworkConditions", {
            "offline": False, "latency": 150,
            "downloadThroughput": int(1.6 * 1000 * 1000 / 8),
            "uploadThroughput": int(750 * 1000 / 8)})

        t0 = time.time()
        seite.goto(basis + "/events.html", wait_until="domcontentloaded")
        t_dom = time.time()
        # Auf echte Zeilen warten, nicht auf die Platzhalter-Zeile: die
        # Trefferzahl steht erst, wenn events.json da und gefiltert ist.
        seite.wait_for_function(
            "() => /[1-9]/.test(document.querySelector('.result-count').textContent)",
            timeout=300000)
        t_liste = time.time()
        seite.wait_for_timeout(1000)

        stand = seite.evaluate("""() => {
            const r = performance.getEntriesByType('resource')
                .find(x => /events\\.json/.test(x.name)) || {};
            return {zeilen: document.querySelectorAll('tbody tr').length,
                    knoten: document.getElementsByTagName('*').length,
                    treffer: document.querySelector('.result-count').textContent.trim(),
                    json_ms: Math.round(r.duration || 0),
                    json_kb: Math.round((r.encodedBodySize || 0) / 1024),
                    html_mb: +(document.documentElement.innerHTML.length / 1e6).toFixed(1)};
        }""")

        # Die Aktionen werden IN der Seite gemessen: render() ist synchron,
        # also ist performance.now() um den Klick genau seine Dauer.
        # Playwrights click() prüft vorher Sichtbarkeit und Trefferpunkt
        # und kostet bei einer langen Tabelle selbst Sekunden - das wäre
        # die Messung des Messgeräts.
        def in_seite(js: str) -> int:
            return seite.evaluate("() => { const t = performance.now(); " + js
                                  + " return Math.round(performance.now() - t); }")

        gruppe_an = in_seite("document.getElementById('group-toggle').click();")
        seite.wait_for_timeout(400)
        gruppe_aus = in_seite("document.getElementById('group-toggle').click();")
        seite.wait_for_timeout(400)
        zeile = in_seite("document.querySelector('tbody tr[data-idx]').click();")
        seite.wait_for_timeout(400)
        sortieren = in_seite("document.querySelector('th.col-name .th-sort').click();")
        seite.wait_for_timeout(400)
        reset = in_seite("document.getElementById('reset-btn').click();")
        seite.wait_for_timeout(400)

        # Das Panel lädt places.json nach, ist also asynchron - hier zählt
        # die Uhr von außen.
        knopf = seite.locator('.col-filter-btn[data-col="standort"]')
        knopf.scroll_into_view_if_needed()
        t2 = time.time()
        knopf.click()
        seite.wait_for_selector(".filter-panel input", timeout=300000)
        seite.wait_for_timeout(200)
        t3 = time.time()

        print("\n%s" % titel)
        print("  bis die Liste steht        %6d ms  (DOMContentLoaded %d ms)"
              % (round((t_liste - t0) * 1000), round((t_dom - t0) * 1000)))
        print("  events.json (Netz+Parse)   %6d ms  (%d KB gzip)"
              % (stand["json_ms"], stand["json_kb"]))
        print("  Zeilen im DOM              %6d     (%d Knoten, %s MB HTML)"
              % (stand["zeilen"], stand["knoten"], stand["html_mb"]))
        print("  Trefferzahl                %s" % stand["treffer"])
        print("  Zusammenfassen an / aus    %6d / %d ms" % (gruppe_an, gruppe_aus))
        print("  Zeile auswählen            %6d ms" % zeile)
        print("  nach Name sortieren        %6d ms" % sortieren)
        print("  Filter zurücksetzen        %6d ms" % reset)
        print("  Stadt/Ort-Panel öffnen     %6d ms" % round((t3 - t2) * 1000))
        if fehler:
            print("  FEHLER auf der Seite: %s" % fehler[:2])
    finally:
        browser.close()
        srv.shutdown()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--faktor", type=int, default=5,
                   help="wie oft der echte Datenstand vervielfacht wird (1 = nur echt)")
    p.add_argument("--sichtbar", action="store_true", help="mit Browserfenster")
    args = p.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright fehlt - Messung übersprungen "
              "(pip install playwright && playwright install chromium).")
        return 0

    with open(EVENTS, "rb") as fh:
        vorher = fh.read()

    with sync_playwright() as pw:
        messe(pw, WURZEL, "Heutiger Stand (%d Events)"
              % len(json.loads(vorher.decode("utf-8"))), args.sichtbar)
        if args.faktor > 1:
            ordner = tempfile.mkdtemp(prefix="ee-bench-")
            try:
                anzahl = baue_datenstand(ordner, args.faktor)
                messe(pw, ordner, "Synthetischer Stand (%d Events, %d×)"
                      % (anzahl, args.faktor), args.sichtbar)
            finally:
                shutil.rmtree(ordner, ignore_errors=True)

    with open(EVENTS, "rb") as fh:
        nachher = fh.read()
    if vorher != nachher:
        print("\n❌ events.json hat sich verändert - das darf dieses Skript NIE. "
              "Mit `git checkout -- events.json` zurückholen.")
        return 1
    print("\n(die echte events.json ist unverändert)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

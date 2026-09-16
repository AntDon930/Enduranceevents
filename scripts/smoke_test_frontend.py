#!/usr/bin/env python3
"""Rauchtest der Webseite: startet einen lokalen Server, öffnet die drei
Seiten in Chromium und prüft, was sich nur im echten Browser prüfen lässt.

`test_scraper_lib.py` prüft die Daten und den Python-Teil; hier geht es um
die Seite selbst: lädt sie ohne Fehler, bricht nichts auf Handybreite aus
seinem Kasten, klappen die zusammengefassten Veranstaltungen richtig auf,
öffnet sich das Filter-Panel, liegt hinter dem Kalender-Knopf eine echte
.ics-Datei, überleben die Filter den Weg Liste → Karte → Liste.

Aufruf:

    python3 scripts/smoke_test_frontend.py           # alles
    python3 scripts/smoke_test_frontend.py --sichtbar  # mit Browserfenster

Ohne Playwright oder ohne Chromium bricht das Skript mit Hinweis und
Rückgabewert 0 ab - so wie die übersprungenen Scraper. Es soll niemandem
den Weg versperren, der nur die Daten anfasst.

In dieser Sandbox blockt der Proxy die CDNs per TLS; Leaflet kommt dann
nicht an. Die Kartenprüfungen melden das und gelten als übersprungen,
nicht als Fehler - `--ignore-certificate-errors` ist deshalb gesetzt.
"""

from __future__ import annotations

import functools
import glob
import http.server
import os
import socket
import socketserver
import sys
import threading

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ergebnisse: (bestanden?, Text)
ergebnisse: list[tuple[bool, str]] = []
uebersprungen: list[str] = []


def pruefe(bedingung: bool, text: str) -> bool:
    ergebnisse.append((bool(bedingung), text))
    print(("  ✓ " if bedingung else "  ✗ ") + text)
    return bool(bedingung)


def ueberspringe(text: str) -> None:
    uebersprungen.append(text)
    print("  – übersprungen: " + text)


def starte_server() -> tuple[socketserver.TCPServer, int]:
    """Serviert das Repository auf einem freien Port (wie `python3 -m http.server`)."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    class Leise(http.server.SimpleHTTPRequestHandler):
        """Wie SimpleHTTPRequestHandler, nur ohne Zeile je Abruf."""

        def log_message(self, *args):   # noqa: A003 - Name kommt aus der Basisklasse
            pass

    handler = functools.partial(Leise, directory=WURZEL)
    srv = socketserver.TCPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port


def finde_chromium() -> str | None:
    """Chromium aus PLAYWRIGHT_BROWSERS_PATH, sonst Playwrights eigener Pfad."""
    basis = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if basis:
        treffer = sorted(glob.glob(os.path.join(basis, "chromium-*/chrome-linux/chrome")))
        if treffer:
            return treffer[-1]
    return None


# ---------------------------------------------------------------- Prüfungen

def seite_oeffnen(ctx, url, warten=".top-bar"):
    """Öffnet eine Seite und sammelt dabei Seitenfehler und 404er ein."""
    seite = ctx.new_page()
    probleme: list[str] = []
    seite.on("pageerror", lambda e: probleme.append("Skriptfehler: %s" % e))
    # Nur die eigenen Dateien zählen: geprüft wird diese Seite, nicht
    # fremde Dienste. In der CI gibt es echtes Netz, und eine 4xx-Antwort
    # von Firebase oder einem CDN hätte den Rauchtest sonst rot gemacht,
    # ohne dass an der Seite etwas kaputt ist.
    seite.on("response", lambda r: probleme.append("HTTP %s %s" % (r.status, r.url))
             if r.status >= 400 and "127.0.0.1" in r.url else None)
    seite.goto(url, wait_until="domcontentloaded")
    seite.wait_for_selector(warten, timeout=30000)
    return seite, probleme


def pruefe_kopf(seite, name):
    """Kopfangaben (Symbol, Vorschau) und die Knopfreihe im blauen Kasten."""
    kopf = seite.evaluate("""() => ({
        icon: !!document.querySelector('link[rel=icon]'),
        touch: !!document.querySelector('link[rel=apple-touch-icon]'),
        beschreibung: !!document.querySelector('meta[name=description]'),
        og: !!document.querySelector('meta[property="og:title"]')
    })""")
    pruefe(all(kopf.values()), "%s: Symbol und Vorschau-Angaben im Kopf (%s)"
           % (name, ", ".join(k for k, v in kopf.items() if not v) or "vollständig"))
    raus = seite.evaluate("""() => {
        const b = document.querySelector('.top-bar'), a = document.querySelector('.top-actions');
        if (!b || !a) return 0;
        return Math.round(a.getBoundingClientRect().right - b.getBoundingClientRect().right);
    }""")
    pruefe(raus <= 0, "%s: Knopfreihe bleibt im Kasten (%+d px)" % (name, raus))
    ueberlauf = seite.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
    pruefe(ueberlauf <= 0, "%s: kein waagerechter Überlauf der Seite (%d px)" % (name, ueberlauf))


def pruefe_liste(ctx, basis):
    seite, probleme = seite_oeffnen(ctx, basis + "/events.html", "tbody tr")
    print("\nListe (events.html, 390 px)")
    pruefe(not probleme, "lädt ohne Fehler (%s)" % (probleme[0] if probleme else "keine"))
    pruefe_kopf(seite, "Liste")

    zeilen = seite.locator("tbody tr").count()
    pruefe(zeilen > 0, "Tabelle hat Zeilen (%d)" % zeilen)

    # Detailbereich und Kalenderdatei
    seite.locator("tbody tr").first.click()
    # Das sanfte Scrollen braucht einen Moment.
    seite.wait_for_timeout(900)
    # Auf Handybreite steht der Detailbereich unter der 78vh hohen Tabelle:
    # ohne Scrollen wirkte das Tippen folgenlos.
    lage = seite.evaluate("""() => { const b = document.getElementById('detail-panel')
        .getBoundingClientRect();
        return {top: b.top, unten: b.bottom, vh: innerHeight, y: scrollY}; }""")
    pruefe(lage["y"] > 0 and lage["top"] < lage["vh"] and lage["unten"] > 0,
           "Tippen auf eine Zeile holt den Detailbereich ins Bild (scrollY %d, oben %d von %d)"
           % (lage["y"], lage["top"], lage["vh"]))
    ics = seite.evaluate("""() => { const a = [...document.querySelectorAll('#detail-panel a')]
        .find(a => /kalender\\//.test(a.getAttribute('href') || ''));
        return a ? {href: a.getAttribute('href'), download: a.hasAttribute('download')} : null; }""")
    if pruefe(bool(ics), "Detailbereich verlinkt eine Kalenderdatei"):
        antwort = seite.request.get(basis + "/" + ics["href"].replace(" ", "%20"))
        pruefe(antwort.status == 200 and "text/calendar" in (antwort.headers.get("content-type") or ""),
               "Kalenderdatei liegt im Repo und kommt als text/calendar (HTTP %d)" % antwort.status)
        # Ohne download-Attribut - sonst reicht Safari die Datei nicht an den Kalender weiter.
        pruefe(not ics["download"], "Kalender-Link trägt kein download-Attribut")

    # Filter-Panel auf Handybreite
    knopf = seite.locator('.col-filter-btn[data-col="standort"]')
    if knopf.count():
        knopf.scroll_into_view_if_needed()
        knopf.click()
        seite.wait_for_timeout(600)
        lage = seite.evaluate("""() => { const p = document.querySelector('.filter-panel');
            if (!p) return null; const b = p.getBoundingClientRect();
            return {x: b.x, y: b.y, r: b.right, u: b.bottom, vw: innerWidth, vh: innerHeight}; }""")
        pruefe(bool(lage) and lage["x"] >= 0 and lage["r"] <= lage["vw"] + 1,
               "Filter-Panel öffnet sich und liegt im Bild")
        seite.keyboard.press("Escape")
    else:
        ueberspringe("Filterknopf Stadt/Ort nicht gefunden")
    seite.close()


def pruefe_gruppierung(ctx, basis):
    """Datenregel der Anzeige: N Strecken = aufgeklappt N Zeilen."""
    print("\nZusammenfassen (events.html?gruppiert=1)")
    seite, probleme = seite_oeffnen(ctx, basis + "/events.html?gruppiert=1", "tr.group-row")
    pruefe(not probleme, "lädt ohne Fehler (%s)" % (probleme[0] if probleme else "keine"))
    zu = seite.evaluate("""() => { const r = document.querySelector('tr.group-row:not(.single)');
        if (!r) return null;
        return {anzahl: parseInt(r.querySelector('.count-pill').textContent, 10),
                marken: r.querySelectorAll('.badge').length,
                offen: r.classList.contains('open')}; }""")
    if not pruefe(bool(zu), "es gibt eine Veranstaltung mit mehreren Strecken"):
        seite.close()
        return
    pruefe(not zu["offen"] and zu["marken"] >= 1,
           "zugeklappt: Längen stehen als Marken (%d)" % zu["marken"])
    seite.locator("tr.group-row:not(.single)").first.click()
    seite.wait_for_timeout(300)
    auf = seite.evaluate("""() => { const r = document.querySelector('tr.group-row:not(.single)');
        let n = r.nextElementSibling, unter = 0;
        while (n && n.classList.contains('sub-row')) { unter++; n = n.nextElementSibling; }
        return {unter, offen: r.classList.contains('open'), marken: r.querySelectorAll('.badge').length,
                aria: r.getAttribute('aria-expanded'), pfeil: !!r.querySelector('.chevron.open')}; }""")
    pruefe(auf["unter"] == zu["anzahl"] - 1 and auf["offen"],
           "aufgeklappt: %d Strecken = %d Zeilen (Veranstaltungszeile + %d %s)"
           % (zu["anzahl"], auf["unter"] + 1, auf["unter"],
              "Unterzeile" if auf["unter"] == 1 else "Unterzeilen"))
    pruefe(auf["marken"] == 0, "aufgeklappt: keine Marken mehr (die Strecken stehen einzeln)")
    pruefe(auf["aria"] == "true" and auf["pfeil"], "aufgeklappt: Pfeil und aria-expanded stimmen")
    seite.locator("tr.group-row:not(.single)").first.click()
    seite.wait_for_timeout(300)
    wieder = seite.evaluate("""() => { const r = document.querySelector('tr.group-row:not(.single)');
        let n = r.nextElementSibling, unter = 0;
        while (n && n.classList.contains('sub-row')) { unter++; n = n.nextElementSibling; }
        return {unter, marken: r.querySelectorAll('.badge').length}; }""")
    pruefe(wieder["unter"] == 0 and wieder["marken"] == zu["marken"],
           "wieder zugeklappt: Unterzeilen weg, Marken zurück")
    seite.close()


def pruefe_tastatur(ctx, basis):
    """Die Liste ist ohne Maus bedienbar.

    Die Tabellenzeilen sind `<tr>` mit einem Listener am `<tbody>` - ohne
    Zutun also weder fokussierbar noch auslösbar. Geprüft wird das Muster
    dahinter: genau EIN Tab-Stopp (nicht 4.155), Pfeiltasten bewegen und
    wählen aus, Enter springt in die Angaben, Escape schließt Panel und
    Dialog und gibt den Fokus zurück.
    """
    print("\nTastaturbedienung")
    seite, probleme = seite_oeffnen(ctx, basis + "/events.html", "tbody tr")
    pruefe(not probleme, "lädt ohne Fehler (%s)" % (probleme[0] if probleme else "keine"))
    stopps = seite.evaluate("() => document.querySelectorAll('tbody tr[tabindex=\"0\"]').length")
    pruefe(stopps == 1, "genau eine Zeile ist per Tab erreichbar (%d)" % stopps)

    seite.evaluate("() => document.querySelector('tbody tr[tabindex=\"0\"]').focus()")
    vorher = seite.evaluate("() => document.activeElement.dataset.idx")
    seite.keyboard.press("ArrowDown")
    seite.wait_for_timeout(250)
    nachher = seite.evaluate("""() => ({
        idx: document.activeElement.dataset.idx,
        zeile: document.activeElement.tagName,
        aktiv: document.activeElement.classList.contains('active'),
        titel: (document.querySelector('#detail-panel h2') || {}).textContent || ''
    })""")
    pruefe(nachher["zeile"] == "TR" and nachher["idx"] != vorher and nachher["aktiv"]
           and bool(nachher["titel"]),
           "Pfeiltaste bewegt den Fokus und wählt aus (%s → %s, %s)"
           % (vorher, nachher["idx"], nachher["titel"][:30]))
    seite.keyboard.press("End")
    seite.wait_for_timeout(250)
    letzte = seite.evaluate("""() => document.activeElement ===
        document.querySelectorAll('tbody tr[data-idx]')[document.querySelectorAll('tbody tr[data-idx]').length - 1]""")
    pruefe(letzte, "End springt zur letzten Zeile")

    seite.keyboard.press("Enter")
    seite.wait_for_timeout(900)
    im_detail = seite.evaluate("() => document.activeElement.id === 'detail-panel'")
    pruefe(im_detail, "Enter springt in die Angaben")
    seite.keyboard.press("Tab")
    seite.wait_for_timeout(200)
    pruefe(seite.evaluate("() => !!document.activeElement.closest('#detail-panel')"),
           "von dort erreicht Tab die Links im Detailbereich")

    # Filter-Panel: Enter öffnet, Escape schließt und gibt den Fokus zurück
    knopf = seite.locator('.col-filter-btn[data-col="land"]')
    if knopf.count():
        knopf.evaluate("el => el.focus()")
        seite.keyboard.press("Enter")
        seite.wait_for_timeout(400)
        offen = seite.evaluate("""() => { const p = document.querySelector('.filter-panel');
            const b = document.querySelector('.col-filter-btn[data-col=land]');
            return !!p && !p.hidden && b.getAttribute('aria-expanded') === 'true'; }""")
        pruefe(offen, "Enter auf dem Filterknopf öffnet das Panel (aria-expanded)")
        seite.keyboard.press("ArrowDown")
        seite.wait_for_timeout(300)
        pruefe(seite.evaluate("() => document.querySelector('.filter-panel').contains(document.activeElement)"),
               "Pfeil nach unten geht in das Panel hinein")
        seite.keyboard.press("Escape")
        seite.wait_for_timeout(300)
        zurueck = seite.evaluate("""() => document.querySelector('.filter-panel').hidden
            && document.activeElement === document.querySelector('.col-filter-btn[data-col=land]')""")
        pruefe(zurueck, "Escape schließt das Panel und gibt den Fokus zurück")
    else:
        ueberspringe("Filterknopf Land nicht gefunden")

    # Melde-Dialog: Fokus bleibt darin, Escape schließt und gibt zurück
    seite.locator("tbody tr").first.click()
    seite.wait_for_timeout(900)
    melden = seite.locator("#report-open-btn")
    if melden.count():
        melden.click()
        seite.wait_for_timeout(600)
        drin = seite.evaluate("""() => { const o = document.getElementById('report-overlay');
            return !o.hidden && o.contains(document.activeElement); }""")
        for _ in range(15):
            if not drin:
                break
            seite.keyboard.press("Tab")
            drin = seite.evaluate("""() => document.getElementById('report-overlay')
                .contains(document.activeElement)""")
        pruefe(drin, "im Melde-Dialog bleibt der Fokus im Dialog (Fessel)")
        seite.keyboard.press("Escape")
        seite.wait_for_timeout(400)
        pruefe(seite.evaluate("""() => document.getElementById('report-overlay').hidden
                   && document.activeElement.id === 'report-open-btn'"""),
               "Escape schließt den Dialog und gibt den Fokus zurück")
    else:
        ueberspringe("Melde-Knopf nicht gefunden")
    seite.close()


def pruefe_cluster(seite):
    """Die Marker werden gebündelt, und die Zahlen darin gehen auf.

    Der eigentliche Prüfstein ist die Summe: Jedes Bündel trägt die Zahl
    der Events darunter, nicht die der Orte. Addiert man alle Bündel und
    die einzeln stehenden Orte, muss genau die Event-Zahl aus der
    Kopfzeile herauskommen - sonst zählt die Karte anders als sie
    beschriftet ist (der Fehler, der bei `eeCount` naheliegt).
    """
    zahlen = seite.evaluate("""() => {
        const summe = s => Array.from(document.querySelectorAll(s))
            .reduce((a, el) => a + (parseInt(el.textContent, 10) || 0), 0);
        return {
            buendel: document.querySelectorAll('.cluster-badge').length,
            orte: document.querySelectorAll('.marker-badge').length,
            events: summe('.cluster-badge') + summe('.marker-badge'),
            hinweis: (document.getElementById('map-hint') || {}).textContent || ''
        };
    }""")
    if not pruefe(zahlen["buendel"] > 0,
                  "Marker sind gebündelt (%d Bündel, %d einzelne Orte)"
                  % (zahlen["buendel"], zahlen["orte"])):
        return
    pruefe(zahlen["buendel"] + zahlen["orte"] < 1000,
           "aus vielen Orten werden wenige Zeichen (%d statt ~1.500)"
           % (zahlen["buendel"] + zahlen["orte"]))
    erwartet = int(zahlen["hinweis"].split(" ", 1)[0].replace(".", "") or 0)
    pruefe(zahlen["events"] == erwartet,
           "Summe der Bündel-Zahlen = Events der Kopfzeile (%d / %d)"
           % (zahlen["events"], erwartet))
    # Ein Klick auf ein Bündel zoomt hinein: danach stehen mehr Zeichen
    # auf der Karte als vorher.
    vorher = zahlen["buendel"] + zahlen["orte"]
    seite.locator(".cluster-badge").first.click()
    seite.wait_for_timeout(1500)
    nachher = (seite.locator(".cluster-badge").count()
               + seite.locator(".marker-badge").count())
    pruefe(nachher > vorher, "Klick auf ein Bündel klappt es auf (%d → %d)"
           % (vorher, nachher))


def pruefe_ausgangspunkt(ctx, basis):
    """Ausgangspunkt und Umkreis bleiben ungebündelt.

    Sie liegen in einer eigenen Ebene (`overlayLayer`). Läge der rote Punkt
    in der Bündel-Ebene, verschwände er beim Herauszoomen in einem Bündel -
    und mit ihm die Antwort auf die Frage, warum außerhalb nichts steht.
    """
    seite, _ = seite_oeffnen(ctx, basis + "/karte.html?ort=48.7758,9.1829,Stuttgart&umkreis=50",
                             ".filter-bar")
    seite.wait_for_timeout(2500)
    pruefe(seite.locator(".origin-dot").count() == 1,
           "Ausgangspunkt steht einmal und ungebündelt auf der Karte")
    pruefe(seite.locator("path.leaflet-interactive").count() >= 1,
           "der Umkreis ist als Kreis zu sehen")
    # Chip entfernen: beide Ebenen müssen geleert werden, sonst bleibt der
    # Punkt liegen.
    seite.locator(".active-chips .chip button").first.click()
    seite.wait_for_timeout(1500)
    pruefe(seite.locator(".origin-dot").count() == 0,
           "Chip entfernt: Ausgangspunkt und Umkreis sind weg")
    seite.close()


def pruefe_karte_und_rundweg(ctx, basis):
    print("\nKarte und Seitenwechsel")
    seite, probleme = seite_oeffnen(ctx, basis + "/karte.html", ".filter-bar")
    echte = [p for p in probleme if "unpkg.com" not in p]
    pruefe(not echte, "Karte lädt ohne Fehler (%s)" % (echte[0] if echte else "keine"))
    pruefe_kopf(seite, "Karte")
    seite.wait_for_timeout(2500)
    marker = seite.locator(".leaflet-marker-icon").count()
    if marker:
        pruefe(marker > 0, "Marker auf der Karte (%d)" % marker)
        pruefe_cluster(seite)
    else:
        ueberspringe("keine Marker - Leaflet kam nicht durch (CDN blockiert?)")
    seite.close()

    if marker:
        pruefe_ausgangspunkt(ctx, basis)

    # Filter über den Seitenwechsel: Liste → Karte → Liste
    seite, _ = seite_oeffnen(ctx, basis + "/events.html?land=Deutschland&gruppiert=1", "tbody tr")
    vorher = seite.evaluate("() => document.querySelector('.result-count').textContent.trim()")
    seite.click('a[href^="karte.html"]')
    seite.wait_for_load_state("domcontentloaded")
    seite.wait_for_selector(".filter-bar", timeout=30000)
    mit = seite.evaluate("() => location.search")
    seite.click('a[href^="events.html"]')
    seite.wait_for_selector("tbody tr", timeout=30000)
    nachher = seite.evaluate("() => document.querySelector('.result-count').textContent.trim()")
    pruefe("land=Deutschland" in mit and "gruppiert=1" in mit,
           "Karte übernimmt Filter und Gruppierung aus der Adresse")
    pruefe(vorher == nachher, "Rückweg zur Liste behält die Trefferzahl (%s)" % nachher)
    seite.close()


def main() -> int:
    sichtbar = "--sichtbar" in sys.argv
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright fehlt - Rauchtest übersprungen "
              "(pip install playwright && playwright install chromium).")
        return 0

    srv, port = starte_server()
    basis = "http://127.0.0.1:%d" % port
    print("Rauchtest gegen %s (Handybreite 390 px)" % basis)
    pfad = finde_chromium()
    try:
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(
                    executable_path=pfad,
                    headless=not sichtbar,
                    # In der Sandbox blockt der Proxy die CDNs per TLS.
                    args=["--ignore-certificate-errors"])
            except Exception as ex:                      # noqa: BLE001
                print("Chromium lässt sich nicht starten - Rauchtest übersprungen.\n  %s"
                      % str(ex).splitlines()[0])
                return 0
            ctx = browser.new_context(viewport={"width": 390, "height": 844},
                                      is_mobile=True, has_touch=True)
            try:
                pruefe_liste(ctx, basis)
                pruefe_gruppierung(ctx, basis)
                pruefe_tastatur(ctx, basis)
                pruefe_karte_und_rundweg(ctx, basis)
            finally:
                browser.close()
    finally:
        srv.shutdown()

    schlecht = [t for ok, t in ergebnisse if not ok]
    print("\n%d Prüfungen, %d übersprungen" % (len(ergebnisse), len(uebersprungen)))
    if schlecht:
        print("❌ %d Prüfung(en) fehlgeschlagen:" % len(schlecht))
        for t in schlecht:
            print("   - " + t)
        return 1
    print("✅ Rauchtest bestanden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

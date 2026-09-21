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
import re
import os
import socket
import socketserver
import sys
import threading
import urllib.parse

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

    # Detailbereich und Kalenderdatei. Zusammenfassen ist die
    # Voreinstellung, und ein Tippen auf eine aufklappbare Veranstaltung
    # klappt sie AUF statt sie auszuwählen - dann scrollt absichtlich
    # nichts (man will die Strecken an dieser Stelle sehen). Getippt wird
    # deshalb auf die erste Zeile, die sich auswählen lässt: eine einzelne
    # Strecke (kein data-klapp).
    seite.locator("tbody tr[data-idx]:not([data-klapp])").first.click()
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


def pruefe_startseite(ctx, basis):
    """Der Weg von der Startseite in die Liste - oben im Kopf und im Bild.

    Bis jetzt führte nur der Knopf mitten im Bild ("Events entdecken")
    dorthin; wer schon weiß, was er will, musste erst scrollen. Beide
    müssen dasselbe Ziel haben.
    """
    print("\nStartseite")
    seite, probleme = seite_oeffnen(ctx, basis + "/index.html", ".top-bar")
    pruefe(not probleme, "lädt ohne Fehler (%s)" % (probleme[0] if probleme else "keine"))
    seite.wait_for_timeout(600)
    stand = seite.evaluate("""() => {
        const oben = document.querySelector('.top-bar .events-btn');
        const mitte = document.querySelector('.hero-cta-row a.cta-btn');
        const anmelden = document.querySelector('#auth-mount');
        return {
            text: oben ? oben.textContent.trim() : null,
            ziel: oben ? oben.getAttribute('href') : null,
            heroZiel: mitte ? mitte.getAttribute('href') : null,
            vorAnmelden: !!(oben && anmelden
                && oben.getBoundingClientRect().left < anmelden.getBoundingClientRect().left)
        };
    }""")
    pruefe(bool(stand["text"]), "im Kopf steht ein Events-Knopf (%s)" % stand["text"])
    pruefe(stand["ziel"] == stand["heroZiel"] == "events.html",
           "er führt zur Liste, wie „Events entdecken“ (%s / %s)"
           % (stand["ziel"], stand["heroZiel"]))
    pruefe(stand["vorAnmelden"], "er steht links von der Anmeldung")
    seite.close()


def pruefe_mastersuche(ctx, basis):
    """Die Mastersuche: EIN Feld über Eventname, Wettbewerb und Ort.

    Der Prüfstein ist, dass sie beides findet - einen Namen UND einen
    Ort - und dass sie in der Adresse steht (sonst überlebt sie den
    Seitenwechsel zur Karte nicht).
    """
    print("\nMastersuche")
    seite, probleme = seite_oeffnen(ctx, basis + "/events.html", "tbody tr")
    pruefe(not probleme, "lädt ohne Fehler (%s)" % (probleme[0] if probleme else "keine"))
    seite.wait_for_timeout(1400)
    feld = seite.locator("#master-search")
    if not pruefe(feld.count() == 1, "das Suchfeld steht in der Werkzeugleiste"):
        seite.close()
        return
    # Vor der Trefferzahl (so vom Nutzer gewünscht): auf breiten
    # Bildschirmen links daneben, auf Handybreite darüber - beides ist
    # dasselbe "davor". Geprüft wird deshalb die Reihenfolge, nicht die
    # x-Koordinate: Auf 390 px bricht die Zeile um, und dann haben beide
    # denselben linken Rand.
    lage = seite.evaluate("""() => {
        const feld = document.querySelector('.master-search');
        const zahl = document.getElementById('result-count');
        const s = feld.getBoundingClientRect();
        const z = zahl.getBoundingClientRect();
        return {
            davorImDom: !!(feld.compareDocumentPosition(zahl)
                           & Node.DOCUMENT_POSITION_FOLLOWING),
            davorImBild: s.top < z.top - 2 || (Math.abs(s.top - z.top) <= 2 && s.left < z.left)
        };
    }""")
    pruefe(lage["davorImDom"] and lage["davorImBild"],
           "es steht vor der Trefferzahl (%s)" % lage)

    seite.fill("#master-search", "münchen")
    seite.wait_for_timeout(700)
    # Die Mastersuche sucht über Name, Wettbewerb UND Ort (in beiden
    # Sprachen): Ein „Munich Marathon" in Oberschleißheim ist ein
    # richtiger Treffer, obwohl sein Ort das Wort nicht trägt. Geprüft
    # wird deshalb je Zeile, dass Name ODER Ort passt - und dass der Ort
    # mindestens einmal wirklich München ist.
    ort = seite.evaluate("""() => ({
        treffer: document.getElementById('result-count').textContent,
        zeilen: [...document.querySelectorAll('tbody tr[data-idx]')].slice(0, 8).map(tr => ({
            name: (tr.querySelector('td.col-name') || {}).textContent || '',
            ort: ((tr.querySelector('td.col-standort') || {}).textContent || '').trim()
        })),
        chip: [...document.querySelectorAll('#active-chips')].map(c => c.textContent).join(' '),
        url: location.search
    })""")
    passt = lambda z: any(w in (z["name"] + " " + z["ort"]).lower() for w in ("münchen", "munich"))
    orte = [z["ort"] for z in ort["zeilen"]]
    pruefe(bool(orte) and all(passt(z) for z in ort["zeilen"]) and any("ünchen" in o for o in orte),
           "eine Ortseingabe findet Events an diesem Ort (%s)" % ", ".join(orte[:3]))
    pruefe("Suche" in ort["chip"], "es entsteht ein Chip „Suche: …\u201c")
    pruefe("s=" in ort["url"], "die Suche steht in der Adresse (%s)" % ort["url"])

    seite.fill("#master-search", "marathon")
    seite.wait_for_timeout(700)
    namen = seite.evaluate("""() => [...document.querySelectorAll('tbody tr td.col-name')]
        .slice(0, 8).map(t => t.textContent.toLowerCase())""")
    pruefe(bool(namen), "eine Namenseingabe liefert Treffer (%d Zeilen)" % len(namen))

    # Das ✕ leert Feld und Filter.
    seite.evaluate("() => document.getElementById('master-search-clear').click()")
    seite.wait_for_timeout(500)
    pruefe(seite.evaluate("""() => document.getElementById('master-search').value === ''
               && !location.search.includes('s=')"""),
           "das ✕ leert Suche und Adresse")

    # Der Spaltenfilter "Name": Enter im Textfeld schließt das Panel und
    # behält den Filter (vom Nutzer gemeldet: der Filter griff, aber das
    # Fenster blieb stehen). Der Fokus geht zurück an den Knopf.
    knopf = seite.locator('.col-filter-btn[data-col="name"]')
    if pruefe(knopf.count() == 1, "der Spaltenfilter „Name“ hat einen Knopf"):
        knopf.click()
        seite.wait_for_timeout(300)
        feld_im_panel = seite.locator('.filter-panel:not([hidden]) input[type="text"]')
        pruefe(feld_im_panel.count() == 1, "das Namens-Panel öffnet ein Textfeld")
        feld_im_panel.fill("marathon")
        seite.wait_for_timeout(400)
        feld_im_panel.press("Enter")
        seite.wait_for_timeout(400)
        nach_enter = seite.evaluate("""() => ({
            zu: !document.querySelector('.filter-panel:not([hidden])'),
            filter: location.search.includes('q=marathon'),
            fokus: document.activeElement === document.querySelector('.col-filter-btn[data-col=name]'),
            zeilen: document.querySelectorAll('tbody tr[data-idx]').length
        })""")
        pruefe(nach_enter["zu"], "Enter im Namensfeld schließt das Panel")
        pruefe(nach_enter["filter"] and nach_enter["zeilen"] > 0,
               "… und der Filter bleibt gesetzt (q=marathon, %d Zeilen)" % nach_enter["zeilen"])
        pruefe(nach_enter["fokus"], "… der Fokus liegt wieder auf dem Knopf")
    seite.close()


def pruefe_such_vorschlaege(ctx, basis):
    """„Iron" muss „Ironman" anbieten.

    Entstanden aus der Frage nach einer VERANSTALTER-Spalte: Gemessen an
    den Daten lohnt die nicht (größte Serie 21 Veranstaltungen, rund elf
    nennenswerte), und eine Spalte kostete Platz, den die Werkzeugleiste
    auf dem Laptop nicht hat. Der Vorschlag im Suchfeld kostet keinen.

    Geprüft wird das Versprechen und die Tastatur - ein Auswahlfeld, das
    nur mit der Maus geht, ist keins.
    """
    print("\nVorschläge in der Mastersuche")
    seite, probleme = seite_oeffnen(ctx, basis + "/events.html", "tbody tr")
    pruefe(not probleme, "lädt ohne Fehler (%s)" % (probleme[0] if probleme else "keine"))
    feld = seite.locator("#master-search")
    liste = seite.locator("#master-search-list")

    # Ein Zeichen ist zu wenig - sonst poppt die Liste bei jedem Tippen auf.
    feld.click()
    feld.type("I", delay=40)
    seite.wait_for_timeout(300)
    pruefe(seite.evaluate("() => document.getElementById('master-search-list').hidden"),
           "bei einem Zeichen bleibt die Liste zu")

    feld.type("ron", delay=40)
    seite.wait_for_timeout(400)
    stand = seite.evaluate("""() => {
        const l = document.getElementById('master-search-list');
        const f = document.getElementById('master-search');
        return {offen: !l.hidden,
                texte: [...l.querySelectorAll('.vs-text')].map(e => e.textContent),
                zahlen: [...l.querySelectorAll('.vs-anzahl')].map(e => e.textContent),
                rolle: l.getAttribute('role'),
                expanded: f.getAttribute('aria-expanded')}; }""")
    pruefe(stand["offen"], "„Iron\u201c öffnet die Vorschlagsliste")
    pruefe("Ironman" in stand["texte"],
           "„Ironman\u201c wird vorgeschlagen (%s)" % ", ".join(stand["texte"][:3]))
    pruefe(stand["rolle"] == "listbox" and stand["expanded"] == "true",
           "die Liste ist ein listbox mit aria-expanded")
    pruefe(all(z.strip().isdigit() for z in stand["zahlen"]) and bool(stand["zahlen"]),
           "je Vorschlag steht die Zahl der Veranstaltungen dabei (%s)"
           % ", ".join(stand["zahlen"][:3]))

    # Tastatur: Pfeil nach unten hebt hervor, Enter übernimmt.
    seite.keyboard.press("ArrowDown")
    seite.wait_for_timeout(200)
    pruefe(seite.evaluate("""() => {
               const f = document.getElementById('master-search');
               const li = document.querySelector('#master-search-list li[aria-selected=true]');
               return !!li && f.getAttribute('aria-activedescendant') === li.id; }"""),
           "Pfeil nach unten hebt einen Vorschlag hervor (aria-activedescendant)")
    seite.keyboard.press("Enter")
    seite.wait_for_timeout(700)
    danach = seite.evaluate("""() => ({
        wert: document.getElementById('master-search').value,
        zu: document.getElementById('master-search-list').hidden,
        treffer: document.querySelector('.result-count').textContent.trim(),
        adresse: location.search})""")
    pruefe(danach["wert"] == "Ironman", "Enter übernimmt den Vorschlag (%s)" % danach["wert"])
    pruefe(danach["zu"], "und schließt die Liste")
    # Die Trefferzeile nennt die gefilterte UND die Gesamtzahl
    # („7 von 4331 Events"). Nicht mit dem Stand VOR dem Enter
    # vergleichen: Die 180-ms-Verzögerung hat da schon gezeichnet, die
    # Zahl ist also längst dieselbe - der erste Versuch dieser Prüfung
    # schlug genau daran an.
    zahlen = [int(z) for z in re.findall(r"\d+", danach["treffer"])]
    pruefe(len(zahlen) >= 1 and 0 < zahlen[0] < 200,
           "die Liste ist auf die Serie gefiltert (%s)" % danach["treffer"])
    pruefe("s=Ironman" in danach["adresse"].replace("%20", " "),
           "die Suche steht in der Adresse (%s)" % danach["adresse"][:40])

    # Escape schließt, ohne die Suche zu ändern.
    feld.click()
    feld.fill("")
    feld.type("Wings", delay=30)
    seite.wait_for_timeout(400)
    pruefe(not seite.evaluate("() => document.getElementById('master-search-list').hidden"),
           "„Wings\u201c öffnet die Liste erneut")
    seite.keyboard.press("Escape")
    seite.wait_for_timeout(250)
    pruefe(seite.evaluate("""() => { const l = document.getElementById('master-search-list');
               return l.hidden && document.getElementById('master-search')
                        .getAttribute('aria-expanded') === 'false'; }"""),
           "Escape schließt die Liste")
    seite.close()


def pruefe_datum_zweizeilig(ctx, basis):
    """Ein mehrtägiges Rennen steht in zwei Zeilen, nicht irgendwie umgebrochen.

    Vorher brach die Zelle dort um, wo gerade Platz war ("18 Sep 2026 –
    20" / "Sep 2026") - vom Nutzer gemeldet. Geprüft wird der
    Zeilenumbruch NACH dem Gedankenstrich und dass die Zeile dadurch
    nicht höher wird als jede andere.
    """
    print("\nDatum über mehrere Tage")
    seite, _ = seite_oeffnen(ctx, basis + "/events.html", "tbody tr")
    seite.wait_for_timeout(1400)
    stand = seite.evaluate("""() => {
        const zellen = [...document.querySelectorAll('tbody tr td.col-datum')];
        const mehrtaegig = zellen.find(z => z.textContent.includes('–'));
        if (!mehrtaegig) return null;
        const alle = [...document.querySelectorAll('tbody tr')].slice(0, 30)
            .map(r => Math.round(r.getBoundingClientRect().height));
        return {
            html: mehrtaegig.querySelector('.cell-clamp').innerHTML,
            hoehe: Math.round(mehrtaegig.closest('tr').getBoundingClientRect().height),
            hoehen: [...new Set(alle)]
        };
    }""")
    if not pruefe(bool(stand), "es gibt ein mehrtägiges Event in der ersten Seite"):
        seite.close()
        return
    pruefe(stand["html"].count("<br>") == 1 and stand["html"].strip().split("<br>")[0].endswith("–"),
           "Anfangsdatum mit Gedankenstrich, Enddatum darunter (%s)" % stand["html"])
    pruefe(stand["hoehen"] == [stand["hoehe"]],
           "die zweizeilige Zelle macht die Zeile nicht höher (%s)"
           % ", ".join("%d px" % h for h in stand["hoehen"]))
    seite.close()


def pruefe_gruppierung(ctx, basis):
    """Datenregel der Anzeige: N Strecken = aufgeklappt N Zeilen."""
    print("\nZusammenfassen (events.html?gruppiert=1)")
    seite, probleme = seite_oeffnen(ctx, basis + "/events.html?gruppiert=1", "tr.group-row")
    pruefe(not probleme, "lädt ohne Fehler (%s)" % (probleme[0] if probleme else "keine"))
    # Die Spalte „#" gibt es nicht mehr (sie wurde als Durchnummerierung
    # der Events gelesen). Die Zahl der Strecken kommt deshalb aus der
    # Trefferzeile: Auf EINE Veranstaltung eingegrenzt steht dort
    # „1 Veranstaltung (N Strecken)" - und genau N Zeilen müssen sich
    # aufklappen.
    zu = seite.evaluate("""() => { const r = document.querySelector('tr.group-row:not(.single)');
        if (!r) return null;
        return {name: r.querySelector('.group-name-text').textContent.trim(),
                datum: ((r.querySelector('.col-datum') || {}).textContent || '').trim(),
                ort: ((r.querySelector('.col-standort') || {}).textContent || '').trim(),
                laenge: (r.querySelector('.col-laenge_km') || {}).textContent || '',
                marken: r.querySelectorAll('.badge').length,
                hoehe: Math.round(r.getBoundingClientRect().height),
                spalten: [...document.querySelectorAll('thead th')].map(th => th.className),
                offen: r.classList.contains('open')}; }""")
    if not pruefe(bool(zu), "es gibt eine Veranstaltung mit mehreren Strecken"):
        seite.close()
        return
    pruefe(not any("col-anzahl" in k for k in zu["spalten"]),
           "es gibt keine „#\u201c-Spalte mehr (%d Spalten)" % len(zu["spalten"]))
    # Der Pfeil sitzt jetzt ganz links, an der Stelle der alten Zahl.
    pruefe(seite.evaluate("""() => { const r = document.querySelector('tr.group-row:not(.single)');
               const pfeil = r.querySelector('.chevron');
               const zelle = r.querySelector('td');
               if (!pfeil || !zelle) return false;
               return pfeil.getBoundingClientRect().left - zelle.getBoundingClientRect().left < 16; }"""),
           "der Aufklapp-Pfeil steht am linken Rand der ersten Spalte")

    # Auf diese eine Veranstaltung eingrenzen (über die Mastersuche) und
    # ihre Strecken ZÄHLEN - einmal ohne Zusammenfassen, da steht je
    # Strecke eine Zeile. Die Trefferzeile nennt die Zahl nicht mehr
    # (sie ist kürzer geworden, damit die Werkzeugleiste in eine Zeile
    # passt), das Zählen ist ohnehin die direktere Probe.
    #
    # Gezählt wird NICHT alles, was die Suche zeigt, sondern nur die
    # Zeilen mit demselben Namen, Datum UND Ort - der Schlüssel, nach dem
    # die Seite zusammenfasst. Der Name allein reicht nicht: Nach dem
    # Datenlauf vom 21.09.2026 war die erste aufklappbare Veranstaltung
    # „Fun & Erlebnis Marathons“, eine Serie mit 17 Zeilen an acht
    # Terminen - die Suche zeigte 17, aufgeklappt waren es 2, und die
    # Prüfung war rot, ohne dass sich an der Seite etwas geändert hatte.
    # Dieselbe Lehre wie beim festen Kartenort: kein Beispiel aus den
    # Daten darf die Prüfung tragen.
    seite.fill("#master-search", zu["name"])
    seite.wait_for_timeout(700)
    seite.evaluate("() => document.getElementById('group-toggle').click()")   # aus
    seite.wait_for_timeout(500)
    strecken = seite.evaluate("""(zu) => {
        const txt = (tr, sel) => ((tr.querySelector(sel) || {}).textContent || '').trim();
        // Die Namenszelle hängt den Wettbewerb als Span an den Namen; ihr
        // Titel dagegen lautet "Name" oder "Name – Wettbewerb".
        const gleicheVeranstaltung = tr => {
            const el = tr.querySelector('.col-name [title]');
            const titel = el ? el.getAttribute('title') : '';
            return (titel === zu.name || titel.startsWith(zu.name + ' – '))
                && txt(tr, '.col-datum') === zu.datum
                && txt(tr, '.col-standort') === zu.ort;
        };
        const alle = [...document.querySelectorAll('tbody tr[data-idx]')];
        return {
            zeilen: alle.filter(gleicheVeranstaltung).length,
            gruppiert: document.getElementById('group-toggle').checked
        }; }""", zu)
    seite.evaluate("() => document.getElementById('group-toggle').click()")   # wieder an
    seite.wait_for_timeout(500)
    if strecken["gruppiert"] or not strecken["zeilen"]:
        ueberspringe("Zusammenfassen ließ sich nicht umschalten")
        seite.close()
        return
    zu["anzahl"] = strecken["zeilen"]
    # Zugeklappt steht in der Länge-Spalte die SPANNE ("5–42,2 km"), keine
    # Marke je Strecke: Eine Veranstaltung mit vielen Wettbewerben machte
    # die Zeile sonst vielfach höher als alle anderen.
    pruefe(not zu["offen"] and "–" in zu["laenge"] and zu["marken"] == 0,
           "zugeklappt: die Länge steht als Spanne, ohne Marken (%s)" % zu["laenge"].strip())
    # Deutsches Dezimaltrennzeichen: im deutschen Text ein Komma.
    pruefe("." not in zu["laenge"],
           "deutsche Fassung schreibt die Distanz mit Komma (%s)" % zu["laenge"].strip())
    # Aufklappen - und zwar GENAU diese Veranstaltung, nicht die erste
    # aufklappbare Zeile der Suchtreffer: Bei einer Serie kann davor ein
    # anderer Termin mit demselben Namen stehen.
    finde_gruppe = """(zu) => [...document.querySelectorAll('tr.group-row:not(.single)')].find(r =>
        r.querySelector('.group-name-text').textContent.trim() === zu.name
        && ((r.querySelector('.col-datum') || {}).textContent || '').trim() === zu.datum
        && ((r.querySelector('.col-standort') || {}).textContent || '').trim() === zu.ort)"""
    seite.evaluate("(zu) => { const r = (" + finde_gruppe + ")(zu); if (r) r.click(); }", zu)
    seite.wait_for_timeout(300)
    auf = seite.evaluate("""(zu) => { const r = (""" + finde_gruppe + """)(zu);
        if (!r) return {unter: -1, offen: false, marken: 0, aria: null, pfeil: false};
        let n = r.nextElementSibling, unter = 0;
        while (n && n.classList.contains('sub-row')) { unter++; n = n.nextElementSibling; }
        return {unter, offen: r.classList.contains('open'), marken: r.querySelectorAll('.badge').length,
                aria: r.getAttribute('aria-expanded'), pfeil: !!r.querySelector('.chevron.open')}; }""", zu)
    pruefe(auf["unter"] == zu["anzahl"] - 1 and auf["offen"],
           "aufgeklappt: %d Strecken = %d Zeilen (Veranstaltungszeile + %d %s)"
           % (zu["anzahl"], auf["unter"] + 1, auf["unter"],
              "Unterzeile" if auf["unter"] == 1 else "Unterzeilen"))
    pruefe(auf["marken"] == 0, "aufgeklappt: keine Marken (die Strecken stehen einzeln)")
    pruefe(auf["aria"] == "true" and auf["pfeil"], "aufgeklappt: Pfeil und aria-expanded stimmen")
    # Der Rahmen um die aufgeklappte Veranstaltung: Linie oben an der
    # Veranstaltungszeile, Linie unten an der letzten Strecke, senkrechter
    # Strich links UND rechts durch alle Zeilen dazwischen. Ohne ihn sah man den
    # Strecken einer Veranstaltung nicht an, dass sie zusammengehören
    # (vom Nutzer gemeldet). Geprüft wird der berechnete Stil, nicht die
    # Klasse - eine Klasse ohne passende CSS-Regel wäre unsichtbar.
    rahmen = seite.evaluate("""() => {
        const r = document.querySelector('tr.group-row:not(.single)');
        const schatten = (tr) => getComputedStyle(tr.querySelector('td')).boxShadow || 'none';
        const schattenRechts = (tr) => getComputedStyle(tr.querySelector('td:last-child')).boxShadow || 'none';
        // Der Strich links liegt bei x = +3px, der rechts bei -3px (inset).
        const strichRechts = (s) => /inset\s+-3px/.test(s) || /-3px\s+0px\s+0px\s+0px\s+inset/.test(s);
        const zeilen = [r];
        let n = r.nextElementSibling;
        while (n && n.classList.contains('sub-row')) { zeilen.push(n); n = n.nextElementSibling; }
        const letzte = zeilen[zeilen.length - 1];
        return {
          zeilen: zeilen.length,
          mitStrich: zeilen.filter(z => schatten(z).includes('inset')).length,
          mitStrichRechts: zeilen.filter(z => strichRechts(schattenRechts(z))).length,
          kopfLinie: schatten(r),
          fussKlasse: letzte.classList.contains('letzte'),
          fussLinie: schatten(letzte),
          fussLinieRechts: schattenRechts(letzte),
          nurEineLetzte: document.querySelectorAll('tr.sub-row.letzte').length
        }; }""")
    pruefe(rahmen["mitStrich"] == rahmen["zeilen"],
           "aufgeklappt: alle %d Zeilen des Blocks tragen den senkrechten Strich links"
           % rahmen["zeilen"])
    # Rechts das Gegenstück (vom Nutzer am 19.09.2026 nachgefordert) -
    # ohne ihn war der Rahmen eine offene Klammer.
    pruefe(rahmen["mitStrichRechts"] == rahmen["zeilen"],
           "aufgeklappt: alle %d Zeilen des Blocks tragen den senkrechten Strich rechts"
           % rahmen["zeilen"])
    pruefe("-2px" in rahmen["fussLinieRechts"].replace(" ", ""),
           "aufgeklappt: die untere Linie reicht bis in die rechte Eckzelle")
    pruefe(rahmen["fussKlasse"] and "-2px" in rahmen["fussLinie"].replace(" ", ""),
           "aufgeklappt: die letzte Strecke schließt den Rahmen unten ab")
    pruefe(rahmen["nurEineLetzte"] == 1,
           "genau EINE Zeile trägt „letzte\u201c (%d)" % rahmen["nurEineLetzte"])
    # Der ganze Block ist in EINEM Blau hinterlegt (vom Nutzer am
    # 19.09.2026 entschieden: "die gleiche blaue Farbe"), die gewählte
    # Strecke darin trägt dieselbe Farbe - ein kräftigerer Ton für sie
    # war gebaut und wieder verworfen. Als gewählt markiert (Klasse
    # `active`) ist trotzdem genau EINE Zeile: Die Veranstaltungszeile
    # wird aufgeklappt nicht mehr mitmarkiert, wenn eine andere Strecke
    # gewählt ist. Die Maus erst weg, sonst färbt :hover die Zeile.
    seite.mouse.move(0, 0)
    seite.wait_for_timeout(100)
    farben = seite.evaluate("""() => {
        const bg = (tr) => getComputedStyle(tr).backgroundColor;
        const r = document.querySelector('tr.group-row:not(.single)');
        const zeilen = [r];
        let n = r.nextElementSibling;
        while (n && n.classList.contains('sub-row')) { zeilen.push(n); n = n.nextElementSibling; }
        const aussen = [...document.querySelectorAll('tbody tr')]
          .filter(tr => !zeilen.includes(tr) && !tr.classList.contains('mehr-row')).slice(0, 2);
        const gewaehlt = zeilen.filter(z => z.classList.contains('active'));
        const rest = zeilen.filter(z => !z.classList.contains('active'));
        return {
          block: [...new Set(rest.map(bg))],
          gewaehlt: gewaehlt.length,
          gewaehltFarbe: gewaehlt.map(bg),
          aussen: aussen.map(bg)
        }; }""")
    pruefe(len(farben["block"]) == 1,
           "aufgeklappt: alle nicht gewählten Zeilen des Blocks tragen EINE Farbe (%s)"
           % ", ".join(farben["block"]))
    pruefe(all(f != farben["block"][0] for f in farben["aussen"]),
           "die Blockfarbe unterscheidet sich von den Zeilen außerhalb (Zebra)")
    pruefe(farben["gewaehlt"] == 1,
           "aufgeklappt: genau EINE Zeile des Blocks ist als gewählt markiert (%d)"
           % farben["gewaehlt"])
    pruefe(farben["gewaehlt"] == 1 and farben["gewaehltFarbe"][0] == farben["block"][0],
           "die gewählte Strecke trägt dieselbe Blockfarbe wie die anderen")
    # Der Rahmen darf die Zeilenhöhe nicht anfassen - deshalb box-shadow
    # und nicht border (border-collapse teilt sich die Ränder zwischen
    # zwei Zeilen, eine dickere Linie macht die Zeile höher).
    hoehen_offen = seite.evaluate("""() => {
        const r = document.querySelector('tr.group-row:not(.single)');
        const h = [Math.round(r.getBoundingClientRect().height)];
        let n = r.nextElementSibling;
        while (n && n.classList.contains('sub-row')) {
          h.push(Math.round(n.getBoundingClientRect().height)); n = n.nextElementSibling; }
        return h; }""")
    pruefe(len(set(hoehen_offen)) == 1,
           "der Rahmen ändert die Zeilenhöhe nicht (%s)"
           % ", ".join("%d px" % h for h in sorted(set(hoehen_offen))))
    seite.locator("tr.group-row:not(.single)").first.click()
    seite.wait_for_timeout(300)
    wieder = seite.evaluate("""() => { const r = document.querySelector('tr.group-row:not(.single)');
        let n = r.nextElementSibling, unter = 0;
        while (n && n.classList.contains('sub-row')) { unter++; n = n.nextElementSibling; }
        return {unter, marken: r.querySelectorAll('.badge').length}; }""")
    pruefe(wieder["unter"] == 0,
           "wieder zugeklappt: Unterzeilen weg")
    pruefe(seite.evaluate("""() => {
               const r = document.querySelector('tr.group-row:not(.single)');
               const s = getComputedStyle(r.querySelector('td')).boxShadow || 'none';
               return s === 'none' || !s.includes('inset'); }"""),
           "wieder zugeklappt: der Rahmen ist weg")

    # Alle Zeilen gleich hoch, und keine höher als zwei Textzeilen (so vom
    # Nutzer gewünscht). Geprüft wird über die ersten Zeilen im Fenster -
    # darunter sind Veranstaltungen mit einer und mit vielen Strecken.
    hoehen = seite.evaluate("""() => [...document.querySelectorAll('tbody tr')]
        .filter(r => !r.classList.contains('mehr-row'))
        .slice(0, 60)
        .map(r => Math.round(r.getBoundingClientRect().height))""")
    if hoehen:
        pruefe(len(set(hoehen)) == 1,
               "alle Zeilen sind gleich hoch (%s)"
               % ", ".join("%d px" % h for h in sorted(set(hoehen))[:4]))
    else:
        pruefe(False, "Zeilen zum Messen gefunden")
    seite.close()

    # Englische Fassung: Punkt als Dezimaltrennzeichen.
    seite, _ = seite_oeffnen(ctx, basis + "/events.html?gruppiert=1&lang=en", "tr.group-row")
    seite.wait_for_timeout(600)
    seite.evaluate("() => document.querySelector('.lang-btn[data-lang=en]').click()")
    seite.wait_for_timeout(500)
    en_laenge = seite.evaluate("""() => { const r = document.querySelector('tr.group-row:not(.single)');
        return ((r.querySelector('.col-laenge_km') || {}).textContent || '').trim(); }""")
    pruefe("," not in en_laenge,
           "englische Fassung schreibt die Distanz mit Punkt (%s)" % en_laenge)
    # Sprache zurückstellen: Der Umschalter merkt sich die Wahl im
    # localStorage, und das gilt für ALLE weiteren Prüfungen dieses
    # Browser-Kontexts (die Prüfung der Rechtsseiten erwartet deutsche
    # Überschriften).
    seite.evaluate("() => document.querySelector('.lang-btn[data-lang=de]').click()")
    seite.wait_for_timeout(300)
    seite.close()


def pruefe_abo(ctx, basis):
    """Der Abo-Dialog: erreichbar, Zusammenfassung, Rhythmus, Escape.

    Was ohne echtes Konto nicht prüfbar ist, ist das Speichern selbst -
    dafür braucht es eine Anmeldung. Prüfbar (und genau das, was beim
    Bauen dreimal schiefging) ist der Weg dorthin: der Knopf, die
    Zusammenfassung aus GENAU den Feldern, die gespeichert werden, die
    drei Rhythmen, und der Link `?abos=1` aus den E-Mails.
    """
    print("\nAbo: neue Events per E-Mail")
    seite, probleme = seite_oeffnen(
        ctx, basis + "/events.html?ort=48.1372,11.5755,M%C3%BCnchen&umkreis=25&sportart=Laufen",
        "tbody tr")
    pruefe(not probleme, "lädt ohne Fehler (%s)" % (probleme[0] if probleme else "keine"))
    seite.wait_for_timeout(1200)
    knopf = seite.locator("#abo-open-btn")
    if not pruefe(knopf.count() == 1, "der Abo-Knopf steht in der Werkzeugleiste"):
        seite.close()
        return
    knopf.scroll_into_view_if_needed()
    knopf.click()
    seite.wait_for_timeout(700)
    stand = seite.evaluate("""() => ({
        offen: !document.getElementById('abo-overlay').hidden,
        zusammenfassung: (document.querySelector('.abo-summary span') || {}).textContent || '',
        rhythmen: [...document.querySelectorAll('input[name=abo-rhythmus]')].map(i => i.value),
        gewaehlt: (document.querySelector('input[name=abo-rhythmus]:checked') || {}).value,
        fokus: document.getElementById('abo-overlay').contains(document.activeElement)
    })""")
    pruefe(stand["offen"], "Klick öffnet den Dialog")
    pruefe("München" in stand["zusammenfassung"] and "25" in stand["zusammenfassung"],
           "die Zusammenfassung nennt Filter und Umkreis (%s)" % stand["zusammenfassung"][:50])
    pruefe(stand["rhythmen"] == ["sofort", "woechentlich", "monatlich"],
           "drei Rhythmen zur Wahl (%s)" % ", ".join(stand["rhythmen"]))
    pruefe(bool(stand["gewaehlt"]), "einer ist vorausgewählt (%s)" % stand["gewaehlt"])
    pruefe(stand["fokus"], "der Fokus liegt im Dialog")

    # „Welche Events?" - dieselben Filterknöpfe wie in der Liste, aber auf
    # einem eigenen Zustand. Geprüft wird genau das, was daran schiefgehen
    # kann: der Dialog muss die laufende Suche vorbelegen, das Panel muss
    # VOR dem Dialog liegen (an <body> gehängt läge es dahinter) und darf
    # die Liste dahinter nicht anfassen.
    leiste = seite.evaluate("""() => ({
        knoepfe: [...document.querySelectorAll('#abo-filter-bar .col-filter-btn')]
                   .map(b => b.dataset.col),
        markiert: [...document.querySelectorAll('#abo-filter-bar .col-filter-btn.has-filter')]
                   .map(b => b.dataset.col)
    })""")
    pruefe(len(leiste["knoepfe"]) > 0 and "datum" not in leiste["knoepfe"],
           "der Dialog hat eine Filterleiste ohne Datum (%s)" % ", ".join(leiste["knoepfe"]))
    pruefe(set(leiste["markiert"]) >= {"standort", "art1"},
           "die Filter der Suche sind vorbelegt (%s)" % ", ".join(leiste["markiert"]))
    knopf_art1 = seite.locator("#abo-filter-bar .col-filter-btn[data-col=art1]")
    if knopf_art1.count() == 1:
        knopf_art1.click()
        seite.wait_for_timeout(400)
        panel = seite.evaluate("""() => {
            const p = document.querySelector('.filter-panel:not([hidden])');
            if (!p) return null;
            const r = p.getBoundingClientRect();
            const oben = document.elementFromPoint(r.left + r.width / 2, r.top + 12);
            return {
              imDialog: document.getElementById('abo-overlay').contains(p),
              davor: !!(oben && oben.closest('.filter-panel')),
              werte: [...p.querySelectorAll('input[type=checkbox]')].map(i => i.value)
            };
        }""")
        pruefe(bool(panel) and panel["imDialog"] and panel["davor"],
               "das Panel hängt im Dialog und liegt davor (%s)" % panel)
        # Ein Abo schaut in die Zukunft: „Fahrrad" muss zur Wahl stehen,
        # obwohl in events.json noch kein einziges Radrennen steht.
        pruefe(bool(panel) and "Fahrrad" in panel["werte"],
               "auch Sportarten ohne heutige Events stehen zur Wahl (%s)"
               % ", ".join(panel["werte"] if panel else []))
        treffer_vorher = seite.evaluate("() => document.getElementById('result-count').textContent")
        seite.evaluate("""() => {
            const p = document.querySelector('.filter-panel:not([hidden])');
            const kaesten = [...p.querySelectorAll('input[type=checkbox]')];
            const rad = kaesten.find(i => i.value === 'Fahrrad');
            const lauf = kaesten.find(i => i.value === 'Laufen');
            if (rad && !rad.checked) rad.click();
            if (lauf && lauf.checked) lauf.click();
        }""")
        seite.wait_for_timeout(400)
        danach = seite.evaluate("""() => ({
            umfasst: document.getElementById('abo-umfasst').textContent,
            treffer: document.getElementById('result-count').textContent
        })""")
        pruefe("Fahrrad" in danach["umfasst"],
               "die Zusammenfassung folgt der Auswahl (%s)" % danach["umfasst"][:60])
        pruefe(danach["treffer"] == treffer_vorher,
               "die Liste dahinter bleibt unverändert (%s)" % danach["treffer"])
        # Escape im Panel schließt nur das Panel - der Dialog bleibt offen.
        seite.evaluate("""() => { const p = document.querySelector('.filter-panel:not([hidden])');
            const el = p && p.querySelector('input'); if (el) el.focus(); }""")
        seite.keyboard.press("Escape")
        seite.wait_for_timeout(300)
        pruefe(seite.evaluate("""() => !document.querySelector('.filter-panel:not([hidden])')
                   && !document.getElementById('abo-overlay').hidden"""),
               "Escape im Panel schließt das Panel, nicht den Dialog")
    else:
        pruefe(False, "der Dialog hat einen Knopf für die Sportart")

    seite.keyboard.press("Escape")
    seite.wait_for_timeout(400)
    pruefe(seite.evaluate("""() => document.getElementById('abo-overlay').hidden
               && document.activeElement.id === 'abo-open-btn'"""),
           "Escape schließt und gibt den Fokus zurück")
    seite.close()

    # Der Weg aus der E-Mail: ?abos=1 öffnet die Verwaltung.
    seite, _ = seite_oeffnen(ctx, basis + "/events.html?abos=1", "tbody tr")
    seite.wait_for_timeout(1600)
    pruefe(seite.evaluate("() => !document.getElementById('abo-overlay').hidden"),
           "?abos=1 öffnet die Abo-Verwaltung (Abmelde-Link der E-Mails)")
    seite.close()

    # Null Treffer: die Box führt in denselben Dialog.
    seite, _ = seite_oeffnen(ctx, basis + "/events.html?q=zzzgibtesnicht", "body")
    seite.wait_for_timeout(1600)
    pruefe(seite.evaluate("""() => { const b = document.getElementById('notify-box');
               return !b.hidden && !!b.querySelector('#notify-open-btn'); }"""),
           "bei null Treffern führt die Box in denselben Dialog")
    seite.close()


def pruefe_fehlendes_event(ctx, basis):
    """„Wir haben dein Event nicht?" - der Weg für fehlende Veranstaltungen.

    Zwei Wege führen in denselben Dialog: die Leiste unter der Liste und
    die Box bei null Treffern. Prüfbar ist alles bis zum Absenden - das
    Speichern selbst ginge nach Firestore und gehört nicht in einen
    Rauchtest.
    """
    print("\nFehlendes Event melden")
    seite, probleme = seite_oeffnen(ctx, basis + "/events.html", "tbody tr")
    pruefe(not probleme, "lädt ohne Fehler (%s)" % (probleme[0] if probleme else "keine"))
    seite.wait_for_timeout(1000)
    knopf = seite.locator("#fehlt-open-btn")
    if not pruefe(knopf.count() == 1 and bool(knopf.text_content().strip()),
                  "unter der Liste steht ein Knopf mit Beschriftung"):
        seite.close()
        return
    knopf.scroll_into_view_if_needed()
    knopf.click()
    seite.wait_for_timeout(500)
    stand = seite.evaluate("""() => ({
        offen: !document.getElementById('suggest-overlay').hidden,
        felder: [...document.querySelectorAll('#suggest-form input, #suggest-form textarea')]
                  .map(el => el.id),
        fokus: document.getElementById('suggest-overlay').contains(document.activeElement)
    })""")
    pruefe(stand["offen"], "der Klick öffnet den Dialog")
    pruefe(stand["felder"] == ["suggest-url", "suggest-name", "suggest-hinweis"],
           "gefragt wird nach Adresse, Name und Hinweis (%s)" % ", ".join(stand["felder"]))
    pruefe(stand["fokus"], "der Fokus liegt im Dialog")

    # Leer abschicken: eigene Fehlermeldung, kein Absenden.
    seite.evaluate("() => document.getElementById('suggest-submit').click()")
    seite.wait_for_timeout(300)
    pruefe(seite.evaluate("""() => { const m = document.querySelector('#suggest-msg .ee-form-msg');
               return !!m && m.classList.contains('error'); }"""),
           "ohne Adresse kommt eine Fehlermeldung statt eines Absendens")
    # Adresse ohne http:// wird ergänzt, ein Name ohne Punkt bleibt Fehler.
    seite.fill("#suggest-url", "zuerichmarathon.ch")
    seite.evaluate("() => document.getElementById('suggest-submit').click()")
    seite.wait_for_timeout(300)
    pruefe(seite.evaluate("""() => { const m = document.querySelector('#suggest-msg .ee-form-msg');
               return !!m && m.classList.contains('error'); }"""),
           "ohne Namen kommt ebenfalls eine Fehlermeldung")
    seite.keyboard.press("Escape")
    seite.wait_for_timeout(300)
    pruefe(seite.evaluate("() => document.getElementById('suggest-overlay').hidden"),
           "Escape schließt den Dialog")
    seite.close()

    # Null Treffer: beide Wege stehen in der Box.
    seite, _ = seite_oeffnen(ctx, basis + "/events.html?q=zzzgibtesnicht", "body")
    seite.wait_for_timeout(1600)
    pruefe(seite.evaluate("""() => { const b = document.getElementById('notify-box');
               return !b.hidden && !!b.querySelector('#notify-open-btn')
                      && !!b.querySelector('#notify-fehlt-btn'); }"""),
           "bei null Treffern führen beide Wege weiter (Abo und fehlendes Event)")
    seite.evaluate("() => document.getElementById('notify-fehlt-btn').click()")
    seite.wait_for_timeout(500)
    pruefe(seite.evaluate("() => !document.getElementById('suggest-overlay').hidden"),
           "der Knopf in der Box öffnet denselben Dialog")
    seite.close()


def pruefe_rechtsseiten(ctx, basis):
    """Impressum und Datenschutz: erreichbar, lesbar, zweisprachig.

    Beide müssen von JEDER Seite aus unmittelbar erreichbar sein
    (§ 5 DDG) - geprüft wird deshalb der Link auf allen drei
    Hauptseiten, nicht nur die Seite selbst. Und die gelb markierten
    Platzhalter müssen sichtbar sein, damit die Vorlage nicht
    versehentlich als fertiges Impressum live geht.
    """
    print("\nImpressum und Datenschutz")
    for seite_name, kopf in (("impressum.html", "Impressum"),
                             ("datenschutz.html", "Datenschutzerklärung")):
        seite, probleme = seite_oeffnen(ctx, basis + "/" + seite_name, ".karte")
        pruefe(not probleme, "%s lädt ohne Fehler (%s)"
               % (seite_name, probleme[0] if probleme else "keine"))
        stand = seite.evaluate("""() => ({
            titel: document.querySelector('.top-bar h1').textContent.trim(),
            platzhalter: document.querySelectorAll('.platzhalter').length,
            ueberschriften: document.querySelectorAll('.karte h2').length,
            ueberlauf: document.documentElement.scrollWidth - innerWidth
        })""")
        pruefe(stand["titel"] == kopf, "%s trägt den richtigen Kopf (%s)"
               % (seite_name, stand["titel"]))
        pruefe(stand["platzhalter"] > 0,
               "%s: die offenen Angaben sind markiert (%d Platzhalter)"
               % (seite_name, stand["platzhalter"]))
        pruefe(stand["ueberschriften"] >= 5, "%s: %d Abschnitte"
               % (seite_name, stand["ueberschriften"]))
        pruefe(stand["ueberlauf"] <= 0, "%s: kein waagerechter Überlauf (%+d px)"
               % (seite_name, stand["ueberlauf"]))
        # Sprachumschalter
        seite.click('.lang-btn[data-lang="en"]')
        seite.wait_for_timeout(300)
        englisch = seite.evaluate("""() => ({
            titel: document.querySelector('.top-bar h1').textContent.trim(),
            lang: document.documentElement.lang })""")
        pruefe(englisch["lang"] == "en" and englisch["titel"] != kopf,
               "%s: EN schaltet um (%s)" % (seite_name, englisch["titel"]))
        seite.click('.lang-btn[data-lang="de"]')
        seite.wait_for_timeout(200)
        seite.close()

    # Von jeder Hauptseite aus erreichbar
    for haupt in ("index.html", "events.html", "karte.html"):
        seite, _ = seite_oeffnen(ctx, basis + "/" + haupt, "body")
        seite.wait_for_timeout(500)
        links = seite.evaluate("""() => ({
            impressum: !!document.querySelector('a[href="impressum.html"]'),
            datenschutz: !!document.querySelector('a[href="datenschutz.html"]') })""")
        pruefe(links["impressum"] and links["datenschutz"],
               "%s verlinkt Impressum und Datenschutz" % haupt)
        seite.close()


def pruefe_teilen(ctx, basis):
    """Ein einzelnes Event teilen: Knopf, Teilen-Dialog, geteilter Link.

    Geteilt wird ein Link auf genau dieses Event (`?event=<slug>`) plus
    die Angaben aus der Box. Der Prüfstein ist der Rückweg: Wer dem Link
    folgt, muss dasselbe Event sehen - und auf Handybreite muss die Box
    dabei im Bild landen, sonst sieht der Empfänger nur eine Liste.
    """
    print("\nEin Event teilen")
    seite = ctx.new_page()
    probleme = []
    seite.on("pageerror", lambda e: probleme.append("Skriptfehler: %s" % e))
    # navigator.share gibt es in Chromium unter Linux nicht - hier
    # vorgetäuscht, damit geprüft werden kann, WAS übergeben wird.
    seite.add_init_script("""
        window.__geteilt = [];
        navigator.share = (daten) => { window.__geteilt.push(daten); return Promise.resolve(); };
    """)
    seite.goto(basis + "/events.html", wait_until="domcontentloaded")
    seite.wait_for_selector("tbody tr[data-idx]", timeout=30000)
    seite.wait_for_timeout(400)
    seite.locator("tbody tr[data-idx]").nth(2).click()
    seite.wait_for_timeout(900)
    name = seite.evaluate("() => document.querySelector('#detail-panel h2').textContent")
    if not pruefe(seite.locator("#detail-panel .event-share-btn").count() == 1,
                  "Teilen-Knopf steht in der Box (%s)" % name):
        seite.close()
        return
    seite.locator("#detail-panel .event-share-btn").click()
    seite.wait_for_timeout(400)
    daten = seite.evaluate("() => window.__geteilt[0] || null")
    if not pruefe(bool(daten), "Klick öffnet den Teilen-Dialog des Geräts"):
        seite.close()
        return
    pruefe(daten["title"] == name and name in daten["text"] and "·" in daten["text"],
           "geteilt werden die Angaben aus der Box (%s)"
           % daten["text"].replace("\n", " | ")[:70])
    pruefe("?event=" in daten["url"] and daten["url"].startswith("http"),
           "dazu ein absoluter Link auf genau dieses Event")
    geteilt = daten["url"]
    seite.close()

    # Der Rückweg: der Link zeigt dasselbe Event, und die Box ist im Bild.
    seite, probleme = seite_oeffnen(ctx, geteilt, "#detail-panel h2")
    seite.wait_for_timeout(1500)
    zurueck = seite.evaluate("""() => { const b = document.getElementById('detail-panel')
        .getBoundingClientRect();
        return {name: document.querySelector('#detail-panel h2').textContent,
                markiert: !!document.querySelector('tbody tr.active'),
                adresse: location.search,
                sichtbar: b.top < innerHeight && b.bottom > 0}; }""")
    pruefe(not probleme, "geteilter Link lädt ohne Fehler (%s)"
           % (probleme[0] if probleme else "keine"))
    pruefe(zurueck["name"] == name, "geteilter Link zeigt dasselbe Event (%s)" % zurueck["name"])
    pruefe(zurueck["markiert"], "die Zeile ist in der Tabelle markiert")
    pruefe("event=" in zurueck["adresse"], "der Parameter bleibt in der Adresse stehen")
    pruefe(zurueck["sichtbar"], "die Box steht im Bild (auf Handybreite wird hingescrollt)")
    seite.close()

    # Ohne navigator.share (Firefox am Rechner): kopieren statt Dialog.
    seite = ctx.new_page()
    seite.add_init_script("delete navigator.share;")
    seite.goto(basis + "/events.html", wait_until="domcontentloaded")
    seite.wait_for_selector("tbody tr[data-idx]", timeout=30000)
    seite.wait_for_timeout(400)
    seite.locator("tbody tr[data-idx]").first.click()
    seite.wait_for_timeout(700)
    seite.locator("#detail-panel .event-share-btn").click()
    seite.wait_for_timeout(700)
    toast = seite.evaluate("() => (document.querySelector('.toast') || {}).textContent || ''")
    pruefe(bool(toast.strip()), "ohne Teilen-Dialog wird kopiert (%s)" % toast.strip())
    seite.close()


def pruefe_fenster(ctx, basis):
    """Die Tabelle zeichnet nur ein Fenster, filtert aber über alles.

    Mit 20.770 Events (synthetisch gemessen) kostete jede Änderung 4-8
    Sekunden, weil alle Zeilen neu in den DOM gingen. Geprüft wird
    deshalb: im DOM steht nur ein Schub, die Trefferzahl nennt trotzdem
    die volle Zahl, der Knopf sagt wie viel fehlt, und ein Klick hängt
    den nächsten Schub an.
    """
    print("\nFenster (nur ein Schub Zeilen im DOM)")
    seite, probleme = seite_oeffnen(ctx, basis + "/events.html", "tbody tr")
    pruefe(not probleme, "lädt ohne Fehler (%s)" % (probleme[0] if probleme else "keine"))
    seite.wait_for_timeout(600)
    stand = seite.evaluate("""() => ({
        zeilen: document.querySelectorAll('tbody tr[data-idx]').length,
        treffer: document.querySelector('.result-count').textContent.trim(),
        knopf: (document.querySelector('.mehr-btn') || {}).textContent || ''
    })""")
    gesamt = int(stand["treffer"].split(" ")[0])
    pruefe(0 < stand["zeilen"] < gesamt,
           "nur ein Teil der Zeilen im DOM (%d von %d)" % (stand["zeilen"], gesamt))
    pruefe(str(gesamt - stand["zeilen"]) in stand["knopf"],
           "der Knopf nennt den Rest (%s)" % stand["knopf"])
    seite.locator(".mehr-btn").click()
    seite.wait_for_timeout(600)
    danach = seite.evaluate("""() => ({
        zeilen: document.querySelectorAll('tbody tr[data-idx]').length,
        treffer: document.querySelector('.result-count').textContent.trim()
    })""")
    pruefe(danach["zeilen"] > stand["zeilen"],
           "Klick hängt den nächsten Schub an (%d → %d)" % (stand["zeilen"], danach["zeilen"]))
    pruefe(danach["treffer"] == stand["treffer"],
           "die Trefferzahl bleibt die volle Zahl (%s)" % danach["treffer"])
    seite.close()
    # Filtern muss über ALLE Events gehen, nicht nur über das Fenster.
    # Der Namensfilter heißt in der Adresse `q` (siehe filters.js).
    seite, _ = seite_oeffnen(ctx, basis + "/events.html?q=silvester", "tbody tr")
    seite.wait_for_timeout(600)
    gefiltert = seite.evaluate("""() => ({
        treffer: document.querySelector('.result-count').textContent.trim(),
        zeilen: document.querySelectorAll('tbody tr[data-idx]').length })""")
    teile = gefiltert["treffer"].split(" ")
    pruefe(gefiltert["zeilen"] > 0 and teile[0] != "0" and teile[0] != teile[2],
           "Filter greift über alle Events, nicht nur über das Fenster (%s)"
           % gefiltert["treffer"])
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
    vorher = seite.evaluate("() => document.querySelectorAll('tbody tr[data-idx]').length")
    seite.keyboard.press("End")
    seite.wait_for_timeout(400)
    ende = seite.evaluate("""() => { const z = document.querySelectorAll('tbody tr[data-idx]');
        return {letzte: document.activeElement === z[z.length - 1], anzahl: z.length,
                zeile: document.activeElement.tagName}; }""")
    # Die Tabelle zeichnet nur ein Fenster (siehe zeigeMehr): End führt
    # ans Ende des Geladenen, und weil das den nächsten Schub anstößt,
    # kann danach schon wieder eine Zeile dahinter stehen.
    pruefe(ende["zeile"] == "TR" and (ende["letzte"] or ende["anzahl"] > vorher),
           "End springt ans Ende des Geladenen (%d → %d Zeilen)" % (vorher, ende["anzahl"]))

    seite.keyboard.press("Enter")
    seite.wait_for_timeout(900)
    im_detail = seite.evaluate("() => document.activeElement.id === 'detail-panel'")
    pruefe(im_detail, "Enter springt in die Angaben")
    seite.keyboard.press("Tab")
    seite.wait_for_timeout(200)
    pruefe(seite.evaluate("() => !!document.activeElement.closest('#detail-panel')"),
           "von dort erreicht Tab die Links im Detailbereich")
    seite.close()

    # Enter auf einer AUFKLAPPBAREN Veranstaltungszeile - der Fall, der
    # lange unentdeckt blieb. Bis zum 18.09.2026 klappte Enter dort nur
    # um (wie →/← und die Leertaste) und sprang NICHT in die Angaben;
    # ein Tastatur-Nutzer kam bei jeder Veranstaltung mit mehreren
    # Strecken also nie an Kalenderdatei und Veranstalter-Seite.
    #
    # Aufgefallen ist das nur, weil eine Datenänderung zufällig eine
    # solche Zeile ans Ende des Fensters geschoben hat, wo die Prüfung
    # oben Enter drückt. Deshalb steht der Fall jetzt AUSDRÜCKLICH hier
    # und nicht dem Zufall überlassen.
    seite, _ = seite_oeffnen(ctx, basis + "/events.html?gruppiert=1", "tr.group-row")
    seite.wait_for_timeout(600)
    hat = seite.evaluate("""() => { const r =
        document.querySelector('tr.group-row[data-klapp]');
        if (!r) return null;
        r.tabIndex = 0; r.focus();
        return {idx: r.dataset.idx, offen: r.getAttribute('aria-expanded')}; }""")
    if hat:
        seite.keyboard.press("Enter")
        seite.wait_for_timeout(900)
        pruefe(seite.evaluate("() => document.activeElement.id === 'detail-panel'"),
               "Enter auf einer aufklappbaren Veranstaltung springt in die Angaben")
        pruefe(seite.evaluate("""() => { const h = document.querySelector('#detail-panel h2');
                   return !!h && !!h.textContent.trim(); }"""),
               "und die Angaben sind gefüllt")
        # Die Leertaste bleibt der Weg zum Umklappen.
        seite.evaluate("""() => document.querySelector('tr.group-row[data-klapp]').focus()""")
        vorher_offen = seite.evaluate(
            """() => document.querySelector('tr.group-row[data-klapp]')
                   .getAttribute('aria-expanded')""")
        seite.keyboard.press(" ")
        seite.wait_for_timeout(500)
        pruefe(seite.evaluate(
            """() => document.querySelector('tr.group-row[data-klapp]')
                   .getAttribute('aria-expanded')""") != vorher_offen,
            "die Leertaste klappt weiterhin um (%s → umgekehrt)" % vorher_offen)
    else:
        ueberspringe("keine aufklappbare Veranstaltung gefunden")

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
    melden = seite.locator("#detail-panel .report-open-btn")
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
                   && document.activeElement.classList.contains('report-open-btn')"""),
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


def pruefe_kartenrahmen(seite):
    """Die Welt genau EINMAL, und nicht weiter heraus als Europa.

    Beim Herauszoomen zeichnete Leaflet die Weltkarte vorher beliebig oft
    nebeneinander (vom Nutzer gemeldet). Geprüft wird beides, was das
    behebt: `noWrap` an der Kachel-Ebene (keine zwei Kacheln, die
    dieselbe Stelle der Welt zeigen) und der kleinste Zoom (der
    Herauszoomen-Knopf muss irgendwann abschalten - sonst landet man
    wieder bei der ganzen Welt).
    """
    for _ in range(9):
        seite.evaluate("""() => { const b = document.querySelector('.leaflet-control-zoom-out');
            if (b) b.click(); }""")
        seite.wait_for_timeout(160)
    seite.wait_for_timeout(900)
    stand = seite.evaluate("""() => ({
        ende: !!document.querySelector('.leaflet-control-zoom-out.leaflet-disabled'),
        kacheln: [...document.querySelectorAll('img.leaflet-tile')].map(i => i.src)
    })""")
    pruefe(stand["ende"],
           "Herauszoomen hat eine Grenze (Europa, nicht die ganze Welt)")
    # Eine Kachel ist /{z}/{x}/{y}.png. Zwei Kacheln zeigen dieselbe
    # Stelle der Welt, wenn ihre x-Werte sich um genau 2^z unterscheiden -
    # genau das entsteht ohne noWrap.
    kacheln = set()
    doppelt = []
    for url in stand["kacheln"]:
        teile = url.rstrip(".png").split("/")[-3:]
        if len(teile) != 3 or not all(t.lstrip("-").isdigit() for t in teile):
            continue
        z, x, y = (int(t) for t in teile)
        schluessel = (z, x % (2 ** z), y)
        if schluessel in kacheln:
            doppelt.append(url)
        kacheln.add(schluessel)
    pruefe(bool(kacheln) and not doppelt,
           "die Weltkarte steht nur einmal da (%d Kacheln, %d doppelt)"
           % (len(kacheln), len(doppelt)))


def pruefe_maske(seite):
    """Die graue Maske über allem außerhalb der abgedeckten Länder.

    Drei Dinge können daran schiefgehen, und alle drei wären still:
    die Maske fehlt (laender.json nicht gefunden), sie liegt ÜBER den
    Markern (dann sind die Bündel-Zahlen matt), oder sie fängt Klicks ab
    (dann ist kein Marker mehr anklickbar). Dass Klicks durchgehen,
    prüft zusätzlich das Popup weiter unten.
    """
    stand = seite.evaluate("""() => {
        const pane = document.querySelector('.leaflet-maske-pane');
        const pfad = pane ? pane.querySelector('path') : null;
        const marker = document.querySelector('.leaflet-marker-pane');
        return {
            da: !!pfad,
            zIndex: pane ? parseInt(getComputedStyle(pane).zIndex, 10) : null,
            markerZ: marker ? parseInt(getComputedStyle(marker).zIndex, 10) : null,
            klicks: pane ? getComputedStyle(pane).pointerEvents : null,
            regel: pfad ? pfad.getAttribute('fill-rule') : null
        };
    }""")
    if not pruefe(stand["da"], "die graue Maske liegt auf der Karte (laender.json)"):
        return
    pruefe(stand["zIndex"] > 200 and stand["zIndex"] < stand["markerZ"],
           "sie liegt über den Kacheln und unter den Markern (%s < %s)"
           % (stand["zIndex"], stand["markerZ"]))
    pruefe(stand["klicks"] == "none", "sie fängt keine Klicks ab (%s)" % stand["klicks"])
    # Ohne evenodd wären die Länder nicht ausgespart, sondern die Maske
    # läge als eine große Fläche über allem.
    pruefe(stand["regel"] == "evenodd",
           "die Länder sind ausgespart (fill-rule: %s)" % stand["regel"])


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


def pruefe_karten_suche(ctx, basis):
    """Die Mastersuche auf der Karte (vom Nutzer am 19.09.2026 gewünscht).

    Dasselbe Feld wie in der Liste (filter-ui.js baut es), vor den
    Filterknöpfen. Eine Eingabe filtert die Marker, steht als ?s= in der
    Adresse und geht so mit in die Liste.
    """
    seite, _ = seite_oeffnen(ctx, basis + "/karte.html", ".filter-bar")
    seite.wait_for_timeout(2500)
    feld = seite.locator("#master-search")
    if not pruefe(feld.count() == 1, "Karte: das Suchfeld steht in der Filterleiste"):
        seite.close()
        return
    lage = seite.evaluate("""() => {
        const f = document.querySelector('.master-search');
        const k = document.querySelector('#filter-buttons');
        return !!(f.compareDocumentPosition(k) & Node.DOCUMENT_POSITION_FOLLOWING); }""")
    pruefe(lage, "Karte: es steht vor den Filterknöpfen, wie in der Liste")
    vorher = seite.evaluate("() => document.getElementById('map-hint').textContent")
    seite.fill("#master-search", "ironman")
    seite.wait_for_timeout(900)
    nachher = seite.evaluate("""() => ({
        hinweis: document.getElementById('map-hint').textContent,
        url: location.search,
        chip: document.getElementById('active-chips').textContent,
        liste: document.getElementById('list-btn-label').getAttribute('href')
    })""")
    zahl = lambda txt: int(re.search(r"\d+", txt).group(0)) if re.search(r"\d+", txt) else -1
    pruefe(0 < zahl(nachher["hinweis"]) < zahl(vorher),
           "Karte: die Suche filtert die Marker (%s → %s)" % (vorher, nachher["hinweis"]))
    pruefe("s=ironman" in nachher["url"], "Karte: die Suche steht in der Adresse (%s)" % nachher["url"])
    pruefe("Suche" in nachher["chip"], "Karte: es entsteht ein Chip „Suche: …“")
    pruefe("s=ironman" in (nachher["liste"] or ""), "Karte: der Listen-Knopf nimmt die Suche mit")
    seite.close()


def ort_mit_zwei_strecken() -> str | None:
    """Der alphabetisch erste Ort, an dem genau zwei künftige Strecken
    liegen - für den Marker "2" auf der Karte (ein Marker je `standort`,
    siehe karte.html). Vergangene Events zählen nicht: Die Seite wirft
    sie beim Laden weg (dropPastEvents), der Marker sähe sie nie."""
    import datetime
    import json
    heute = datetime.date.today().isoformat()
    pfad = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "events.json")
    with open(pfad, encoding="utf-8") as f:
        events = json.load(f)
    je_ort: dict[str, int] = {}
    for e in events:
        ende = e.get("datum_ende") or e.get("datum_start") or ""
        if ende and ende < heute:
            continue
        if e.get("standort"):
            je_ort[e["standort"]] = je_ort.get(e["standort"], 0) + 1
    kandidaten = sorted(o for o, n in je_ort.items() if n == 2)
    return kandidaten[0] if kandidaten else None


def pruefe_karten_details(ctx, basis):
    """Die Detail-Box auf der Karte (vom Nutzer am 19.09.2026 gewünscht).

    Ein Marker mit einem oder zwei Events öffnet deren Boxen DIREKT oben
    rechts - dieselbe Box wie in der Liste (event-detail.js). Erst ab
    drei Events listet das Popup sie, ein Klick öffnet die Box.
    Höchstens zwei zugleich, die neueste oben, ein ✕ schließt; "Fehler
    melden" führt in die Liste und öffnet dort den Melde-Dialog.
    """
    print("\nDetail-Box auf der Karte")
    # Ein Ort mit genau zwei Strecken: der Marker "2" öffnet beide Boxen.
    # Der Ort wird aus events.json gesucht, nicht fest eingetragen: Der
    # frühere Ort (Mosnang, Schnebelhorn Panoramatrail) fiel am 19.09.2026
    # als vergangenes Event aus der Liste, und die Prüfung lief ins Leere.
    ort = ort_mit_zwei_strecken()
    if ort is None:
        pruefe(False, "kein Ort mit genau zwei künftigen Strecken in events.json")
        return
    seite, probleme = seite_oeffnen(ctx, basis + "/karte.html?standort=" + urllib.parse.quote(ort), ".filter-bar")
    seite.wait_for_timeout(2800)
    seite.evaluate("""() => { const m = document.querySelector('.leaflet-marker-icon');
        if (m) m.click(); }""")
    seite.wait_for_timeout(600)
    namen = lambda: seite.evaluate("""() => [...document.querySelectorAll('#map-details .detail-panel h2')]
        .map(h => h.textContent)""")
    box = seite.evaluate("""() => {
        const b = [...document.querySelectorAll('#map-details .detail-panel')];
        const wrap = document.querySelector('.map-wrap').getBoundingClientRect();
        const r = b[0] ? b[0].getBoundingClientRect() : null;
        return {
          anzahl: b.length,
          popup: !!document.querySelector('.leaflet-popup'),
          felder: b[0] ? b[0].querySelectorAll('.detail-grid dt').length : 0,
          ics: b[0] ? !!b[0].querySelector('a.cal-ics[href^="kalender/"]') : false,
          teilen: b[0] ? !!b[0].querySelector('.event-share-btn') : false,
          melden: b[0] ? !!b[0].querySelector('.report-open-btn') : false,
          schliessen: b[0] ? !!b[0].querySelector('.detail-close') : false,
          obenRechts: r ? (r.top - wrap.top < 100 && wrap.right - r.right < 40) : false
        }; }""")
    if not pruefe(box["anzahl"] == 2 and not box["popup"],
                  "Marker „2\u201c öffnet direkt zwei Boxen, ohne Popup (%d Boxen)" % box["anzahl"]):
        seite.close()
        return
    pruefe(box["felder"] >= 6, "dieselbe Struktur wie in der Liste (%d Felder)" % box["felder"])
    pruefe(box["ics"] and box["teilen"] and box["melden"] and box["schliessen"],
           "Kalenderdatei, Teilen, Fehler melden und ✕ sind da")
    pruefe(box["obenRechts"], "die Boxen stehen oben rechts über der Karte")
    pruefe(not probleme, "ohne Skriptfehler (%s)" % (probleme[0] if probleme else "keine"))
    seite.locator("#map-details .detail-close").first.click()
    seite.wait_for_timeout(300)
    pruefe(len(namen()) == 1, "das ✕ schließt eine Box")

    # "Fehler melden" führt in die Liste und öffnet dort den Dialog.
    seite.locator("#map-details .report-open-btn").first.click()
    seite.wait_for_load_state("domcontentloaded")
    seite.wait_for_selector("#detail-panel h2", timeout=30000)
    seite.wait_for_timeout(1200)
    melden = seite.evaluate("""() => ({
        liste: location.pathname.endsWith('events.html'),
        offen: !document.getElementById('report-overlay').hidden,
        adresse: location.search })""")
    pruefe(melden["liste"] and melden["offen"],
           "Fehler melden führt in die Liste und öffnet den Melde-Dialog")
    pruefe("melden=" not in melden["adresse"], "… und der Parameter bleibt nicht in der Adresse")
    seite.close()

    # Ein Ort mit vielen Events: das Popup listet sie, ein Klick öffnet
    # die Box, die zweite kommt obenauf, die dritte verdrängt die älteste.
    seite, _ = seite_oeffnen(ctx, basis + "/karte.html?standort=Berlin", ".filter-bar")
    seite.wait_for_timeout(2800)
    seite.evaluate("""() => { const m = document.querySelector('.leaflet-marker-icon');
        if (m) m.click(); }""")
    seite.wait_for_timeout(700)
    knoepfe = seite.locator(".leaflet-popup .popup-event")
    if not pruefe(knoepfe.count() >= 3, "ab drei Events listet das Popup sie (%d)" % knoepfe.count()):
        seite.close()
        return
    # Auf Handybreite liegt die Box ÜBER dem Popup (die Karte ist nur
    # 390 px breit) - ein Nutzer schiebt die Karte kurz beiseite, der
    # Test klickt die Einträge deshalb direkt an.
    klick = lambda i: knoepfe.nth(i).evaluate("b => b.click()")
    erster = knoepfe.nth(0).locator(".pe-name").text_content()
    zweiter = knoepfe.nth(1).locator(".pe-name").text_content()
    klick(0)
    seite.wait_for_timeout(400)
    eins = namen()
    pruefe(len(eins) == 1 and eins[0] == erster, "ein Klick im Popup öffnet die Box (%s)" % (eins or [''])[0])
    klick(1)
    seite.wait_for_timeout(400)
    zwei = namen()
    pruefe(len(zwei) == 2 and zwei[0] == zweiter, "das zweite Event kommt als zweite Box obenauf")
    klick(2)
    seite.wait_for_timeout(400)
    pruefe(len(namen()) == 2, "ein drittes Event verdrängt das älteste - es bleiben zwei")
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
        pruefe_maske(seite)
        pruefe_kartenrahmen(seite)
    else:
        ueberspringe("keine Marker - Leaflet kam nicht durch (CDN blockiert?)")
    seite.close()

    if marker:
        pruefe_ausgangspunkt(ctx, basis)
        pruefe_karten_suche(ctx, basis)
        pruefe_karten_details(ctx, basis)

        # Der Link im Popup: ohne "↗" (der Pfeil sah aus wie ein
        # Stempel - vom Nutzer gemeldet). Ein einzelner Ort, damit kein
        # Bündel den Klick abfängt - und einer mit mehr als zwei Events,
        # denn bei ein oder zwei öffnet der Marker die Boxen direkt und
        # kein Popup (siehe pruefe_karten_details).
        seite, _ = seite_oeffnen(ctx, basis + "/karte.html?standort=Berlin", ".filter-bar")
        seite.wait_for_timeout(2800)
        seite.evaluate("""() => { const m = document.querySelector('.leaflet-marker-icon');
            if (m) m.click(); }""")
        seite.wait_for_timeout(700)
        link = seite.evaluate("""() => { const a = document.querySelector('.popup-link');
            return a ? a.textContent.trim() : null; }""")
        pruefe(bool(link) and "↗" not in link and "Liste" in link,
               "Popup verlinkt die Liste, ohne Pfeil-Symbol (%s)" % link)
        seite.close()

    # Filter über den Seitenwechsel: Liste → Karte → Liste. Zusammenfassen
    # ist die Voreinstellung; in der Adresse steht nur die ABWEICHUNG
    # davon ("gruppiert=0"), und genau die muss den Weg über die Karte
    # überleben - sonst käme man mit einzelnen Strecken hin und mit
    # zusammengefassten zurück.
    seite, _ = seite_oeffnen(ctx, basis + "/events.html?land=Deutschland&gruppiert=0", "tbody tr")
    vorher = seite.evaluate("() => document.querySelector('.result-count').textContent.trim()")
    seite.click('a[href^="karte.html"]')
    seite.wait_for_load_state("domcontentloaded")
    seite.wait_for_selector(".filter-bar", timeout=30000)
    mit = seite.evaluate("() => location.search")
    seite.click('a[href^="events.html"]')
    seite.wait_for_selector("tbody tr", timeout=30000)
    nachher = seite.evaluate("() => document.querySelector('.result-count').textContent.trim()")
    pruefe("land=Deutschland" in mit and "gruppiert=0" in mit,
           "Karte übernimmt Filter und die abgeschaltete Gruppierung aus der Adresse")
    pruefe(vorher == nachher, "Rückweg zur Liste behält die Trefferzahl (%s)" % nachher)
    pruefe(not seite.evaluate("() => document.getElementById('group-toggle').checked"),
           "Rückweg zur Liste behält die Ansicht: Zusammenfassen bleibt aus")
    seite.close()

    # Erster Besuch: Zusammenfassen ist AN (so vom Nutzer gewünscht), ohne
    # dass etwas im Speicher liegt oder in der Adresse steht. Nachgestellt
    # wird das im vorhandenen Kontext: gemerkte Wahl löschen und neu laden
    # (ein zweiter Browser-Kontext neben dem ersten ließ den
    # Ein-Thread-Server der Prüfung hängen - Page.goto lief in den
    # Timeout).
    seite, _ = seite_oeffnen(ctx, basis + "/events.html", "tbody tr")
    seite.evaluate("() => { try { localStorage.removeItem('endurance-gruppiert'); } catch (e) {} }")
    seite.reload(wait_until="domcontentloaded")
    seite.wait_for_selector("tbody tr", timeout=30000)
    erster = seite.evaluate("""() => ({
        an: document.getElementById('group-toggle').checked,
        gruppen: document.querySelectorAll('tr.group-row').length,
        gemerkt: (() => { try { return localStorage.getItem('endurance-gruppiert'); } catch (e) { return 'x'; } })(),
        adresse: location.search })""")
    pruefe(erster["an"] and erster["gruppen"] > 0,
           "erster Besuch: Zusammenfassen ist an (%d Veranstaltungszeilen)" % erster["gruppen"])
    pruefe(erster["gemerkt"] is None,
           "erster Besuch: nichts im Speicher - die Voreinstellung gilt, nicht ein gemerkter Wert")
    pruefe("gruppiert" not in erster["adresse"],
           "erster Besuch: die Voreinstellung steht nicht in der Adresse (%s)" % (erster["adresse"] or "leer"))
    # Selbst abschalten: das wird gemerkt und überlebt ein Neuladen.
    seite.evaluate("() => document.getElementById('group-toggle').click()")
    seite.wait_for_timeout(400)
    seite.reload(wait_until="domcontentloaded")
    seite.wait_for_selector("tbody tr", timeout=30000)
    pruefe(not seite.evaluate("() => document.getElementById('group-toggle').checked"),
           "selbst abgeschaltet: bleibt nach dem Neuladen aus")
    # Aufräumen: die Wahl gilt für den ganzen Browser-Kontext.
    seite.evaluate("() => { try { localStorage.removeItem('endurance-gruppiert'); } catch (e) {} }")
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
                pruefe_startseite(ctx, basis)
                pruefe_mastersuche(ctx, basis)
                pruefe_such_vorschlaege(ctx, basis)
                pruefe_datum_zweizeilig(ctx, basis)
                pruefe_gruppierung(ctx, basis)
                pruefe_fenster(ctx, basis)
                pruefe_teilen(ctx, basis)
                pruefe_fehlendes_event(ctx, basis)
                pruefe_rechtsseiten(ctx, basis)
                pruefe_abo(ctx, basis)
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Erzeugt og-image.png (1200 x 630) aus og-vorlage.html per Chromium.

Die Vorlage liegt daneben und nutzt die Schriften aus vendor/fonts; sie
wird kurz als _og.html in die Repo-Wurzel kopiert, damit die relativen
Pfade stimmen, und danach gelöscht. Aufruf aus der Repo-Wurzel:

    python3 scripts/og/render_og.py

Läuft nicht im Workflow mit - das Bild ist committet und ändert sich nur,
wenn Marke oder Text sich ändern (21.09.2026)."""
import threading, http.server, socketserver, functools, os, pathlib  # noqa: E401
WURZEL = pathlib.Path(__file__).resolve().parent.parent.parent
os.chdir(WURZEL)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
httpd = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(WURZEL)))
port = httpd.server_address[1]; threading.Thread(target=httpd.serve_forever, daemon=True).start()
html = pathlib.Path(__file__).with_name('og-vorlage.html').read_text()
(WURZEL / '_og.html').write_text(html)
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args=['--ignore-certificate-errors'])
    p = b.new_page(viewport={'width':1200,'height':630}, device_scale_factor=1)
    p.goto(f'http://127.0.0.1:{port}/_og.html', wait_until='networkidle'); p.wait_for_timeout(500)
    p.evaluate("document.fonts.ready"); p.wait_for_timeout(300)
    p.screenshot(path=str(WURZEL / 'og-image.png'), clip={'x':0,'y':0,'width':1200,'height':630})
    b.close()
(WURZEL / '_og.html').unlink(missing_ok=True)
httpd.shutdown(); print('og-image.png geschrieben')

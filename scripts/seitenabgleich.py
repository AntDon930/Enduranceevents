"""Abgleich jeder Veranstaltung mit ihrer Veranstalterseite - nur Bericht.

Für jede Veranstaltung (Name + Datum) mit eigener `veranstalter_url` (kein
Portallink, siehe PORTAL_DOMAINS/KEIN_VERANSTALTER) wird die Seite einmal
abgerufen (Abrufer aus veranstalter_links.py: robots.txt, 1 s Pause je
Host, 30-s-Frist) und der Text gegen unsere Daten gehalten:

    DATUM    unser datum_start steht nicht im Text, die Seite nennt aber
             Termine im selben, vorigen oder nächsten Jahr
    DISTANZ  mindestens eine unserer laenge_km fehlt im Text, obwohl die
             Seite km-Angaben hat (±0,15 km bzw. gleiche gerundete Zahl)
    ABGESAGT die Seite spricht von Absage/Ausfall (abgesagt, findet nicht
             statt, fällt aus, cancelled) - seit dem 21.09.2026, weil der
             Nutzer abgesagte Veranstaltungen nicht in der Liste will;
             nur ein Hinweis (der Kohltagelauf wirbt neben der Absage
             weiter mit "Melde dich jetzt an"), geprüft wird von Hand
    LEER     unter 300 Zeichen Text (JS-Seite, Frames, Platzhalter)
    FEHLER   Abruf gescheitert (Status, robots, Timeout)

Nichts davon ist ein Fehler in den Daten - es sagt nur, wo man hinsehen
sollte. Am 21.09.2026 (Elfter Durchgang, siehe CLAUDE.md): 1.849
Veranstaltungen in ~65 Minuten, 1.154 ohne Befund; von den gemeldeten
blieben nach dem Blick auf die Seite rund 150 echte Korrekturen.

    python3 scripts/seitenabgleich.py bericht.json [--fortsetzen] [--max N]

`--fortsetzen` führt einen unterbrochenen Bericht weiter (die Schlüssel
sind "<Name>|<datum_start>"). events.json wird nie angefasst.
"""
import json, re, sys, time
from collections import OrderedDict, Counter
from pathlib import Path
sys.path.insert(0, "scripts")
from veranstalter_links import Abrufer, text_von, kein_veranstalter, host_von
from scraper_lib import is_portal_link

BERICHT = Path(sys.argv[1]); FORTSETZEN = "--fortsetzen" in sys.argv
MAX = int(sys.argv[sys.argv.index("--max")+1]) if "--max" in sys.argv else 0
MONATE = {m: i+1 for i, m in enumerate(["januar","februar","marz","april","mai","juni","juli","august","september","oktober","november","dezember"])}
MONATE.update({"jan":1,"feb":2,"mar":3,"apr":4,"jun":6,"jul":7,"aug":8,"sep":9,"sept":9,"okt":10,"nov":11,"dez":12})

def daten_aus(txt):
    out=set()
    for t,m,j in re.findall(r"\b(\d{1,2})\.\s?(\d{1,2})\.\s?(20\d{2})\b", txt):
        if 1<=int(m)<=12 and 1<=int(t)<=31: out.add(f"{j}-{int(m):02d}-{int(t):02d}")
    for t,m,j in re.findall(r"\b(\d{1,2})\.\s?([a-z]{3,9})\.?\s?(20\d{2})\b", txt):
        if m in MONATE and 1<=int(t)<=31: out.add(f"{j}-{MONATE[m]:02d}-{int(t):02d}")
    for j,m,t in re.findall(r"\b(20\d{2})-(\d{2})-(\d{2})\b", txt):
        if 1<=int(m)<=12: out.add(f"{j}-{m}-{t}")
    return out

def distanzen_aus(txt):
    out=set()
    for z in re.findall(r"\b(\d{1,3}(?:[.,]\d{1,3})?)\s?(?:km|kilometer)\b", txt):
        try: out.add(round(float(z.replace(",", ".")),1))
        except ValueError: pass
    for z in re.findall(r"\b(\d{3,5})\s?(?:m|meter)\b", txt):
        v=int(z)
        if 300<=v<=5000: out.add(round(v/1000,1))
    if re.search(r"\bhalbmarathon|\bhalf marathon|\b21[.,]1\b|\b21[.,]0975", txt): out.add(21.1)
    if re.search(r"(?<!halb)(?<!half )marathon", txt): out.add(42.2)
    return out

ABGESAGT_RE = re.compile(r"abgesagt|absage\b|findet nicht statt|f[aä]llt (?:in diesem jahr |dieses jahr |\d{4} )?aus|muss(?:te)? (?:\w+ ){0,3}ausfallen|cancell?ed|wird nicht mehr durchgeführt", re.I)

def passt(km, gefunden):
    return any(abs(km-g) <= 0.15 or (abs(km-g) < 0.6 and abs(round(km)-round(g)) == 0) for g in gefunden)

events=json.load(open("events.json"))
gruppen=OrderedDict()
for e in sorted(events, key=lambda e:(e.get("datum_start") or "", e.get("name") or "")):
    url=e.get("veranstalter_url") or ""
    if not url or is_portal_link(url) or kein_veranstalter(url): continue
    if "ironman.com" in url: continue
    k=f"{e.get('name')}|{e.get('datum_start')}"
    g=gruppen.setdefault(k,{"name":e.get("name"),"datum":e.get("datum_start"),"ende":e.get("datum_ende"),"url":url,"ort":e.get("standort"),"art1":e.get("art1"),"km":[],"dauer":[]})
    if isinstance(e.get("laenge_km"),(int,float)): g["km"].append(e["laenge_km"])
    if isinstance(e.get("dauer_h"),(int,float)): g["dauer"].append(e["dauer_h"])
if MAX: gruppen=OrderedDict(list(gruppen.items())[:MAX])
bericht=OrderedDict()
if FORTSETZEN and BERICHT.exists(): bericht=json.load(open(BERICHT),object_pairs_hook=OrderedDict)
print(len(gruppen),"Veranstaltungen mit eigener Seite;", len(bericht), "schon im Bericht", flush=True)
ab=Abrufer(pause=1.0)
t0=time.time()
for i,(k,g) in enumerate(gruppen.items(),1):
    if k in bericht: continue
    status, body = ab.hole(g["url"])
    r=OrderedDict(name=g["name"],datum=g["datum"],url=g["url"],ort=g["ort"],km=sorted(set(g["km"])),status=status if status is not None else body)
    if status==200:
        txt=text_von(body)
        daten=daten_aus(txt); dist=distanzen_aus(txt)
        jahr=g["datum"][:4]
        nah=sorted(d for d in daten if d[:4] in (jahr, str(int(jahr)-1), str(int(jahr)+1)))
        r["datum_ok"]=g["datum"] in daten
        r["seiten_daten"]=nah[:40]
        r["km_fehlt"]=[km for km in r["km"] if not passt(km,dist)]
        r["seiten_km"]=sorted(x for x in dist if x>=1)[:40]
        r["textlaenge"]=len(txt)
        flags=[]
        if not r["datum_ok"] and nah: flags.append("DATUM")
        if r["km_fehlt"] and dist: flags.append("DISTANZ")
        if len(txt)<300: flags.append("LEER")
        m=ABGESAGT_RE.search(txt)
        if m:
            flags.append("ABGESAGT"); r["absage"]=txt[max(0,m.start()-80):m.end()+80].strip()
        r["flags"]=flags
    else:
        r["flags"]=["FEHLER"]
    bericht[k]=r
    if i%25==0 or i==len(gruppen):
        c=Counter(f for b in bericht.values() for f in (b.get("flags") or ["ok"]))
        print(f"  … {i}/{len(gruppen)} ({int(time.time()-t0)} s): {dict(c)}", flush=True)
        BERICHT.write_text(json.dumps(bericht,ensure_ascii=False,indent=1))
BERICHT.write_text(json.dumps(bericht,ensure_ascii=False,indent=1))
print("fertig", flush=True)

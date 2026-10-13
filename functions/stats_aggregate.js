/**
 * functions/stats_aggregate.js
 * ============================
 *
 * Die Rechenregeln der Besucherstatistik - OHNE Firestore, ohne Netz,
 * damit sie sich mit node allein prüfen lassen (test_scraper_lib.py,
 * test_statistik). Benutzt von `aggregateStats` in index.js: Die Function
 * liest die Rohtreffer eines Tages aus der Collection `hits` und schreibt
 * das Ergebnis von aggregiere() als EIN Dokument nach `stats_daily/<Tag>`.
 * Die Seite statistik.html liest nur diese Tagesdokumente.
 *
 * Was ein Rohtreffer enthält (Feldnamen kurz, es sind viele):
 *   t   Zeitpunkt in Millisekunden          h   Stunde 0-23 (Europe/Berlin)
 *   e   Ereignis: 'pv' (Seitenaufruf) oder eine Aktion (detail, kalender …)
 *   p   Seite (index, events, karte …)      r   Referrer-Host ('' = direkt)
 *   q/m/c  utm_source / utm_medium / utm_campaign
 *   ld  Region (Code, siehe landAus)        la  Browsersprache ('de-AT')
 *   sl  Seitensprache ('de'/'en')           th  Farbschema ('dark'/'light')
 *   dv  Gerät (handy/tablet/rechner)        br/os  Browser / Betriebssystem
 *   v   Besucher-Kennung des Tages (Hash aus IP + Browser + Tagesschlüssel,
 *       siehe index.js - die IP selbst wird nie gespeichert)
 *   s   Sitzungs-Kennung des Tabs (Zufallswert aus sessionStorage)
 *   pr  Zusatzangaben einer Aktion ({ev, sp}, {art}, {q}, {k, w} …)
 *
 * Begriffe, wie sie die Seite zeigt:
 *   Seitenaufrufe  = Zahl der 'pv'-Treffer
 *   Besucher       = verschiedene v je Tag. Über mehrere Tage SUMMIERT die
 *                    Seite die Tageswerte - der Tagesschlüssel wechselt,
 *                    dieselbe Person ist am nächsten Tag absichtlich nicht
 *                    wiedererkennbar.
 *   Besuche        = zusammenhängende Folgen von Seitenaufrufen derselben
 *                    Sitzung; eine Pause über SITZUNGS_LUECKE_MS beginnt
 *                    einen neuen Besuch.
 *   Absprung       = Besuch mit genau einem Seitenaufruf.
 *   Besuchsdauer   = letzter minus erster Aufruf eines Besuchs mit
 *                    mindestens zwei Aufrufen (ein Einzelaufruf hat keine
 *                    messbare Dauer - wie bei Plausible/Matomo).
 *   Referrer/Kampagne zählen je BESUCH (am ersten Aufruf), nicht je Seite -
 *   sonst zählte ein Besucher mit fünf Seiten fünfmal für Google.
 *
 * Aufschlüsselungen sind Listen `[{k, n}, …]` absteigend nach n, nicht
 * Maps: Firestore-Feldnamen dürfen keinen Punkt und kein `/` enthalten,
 * und genau die stehen in Hostnamen ("google.com") und Suchbegriffen.
 */
"use strict";

const SITZUNGS_LUECKE_MS = 30 * 60 * 1000;
const MAX_EINTRAEGE = 200;        // je Aufschlüsselung
const MAX_EINTRAEGE_LANG = 500;   // Events, Veranstalter, Suchbegriffe, Filter

// Welche Zusatzangabe einer Aktion gezählt wird (und unter welchem Namen
// die Liste im Tagesdokument steht). Aktionen ohne Eintrag werden nur in
// `aktionen` gezählt.
const AKTIONS_DETAIL = {
  detail: ["ev", "events"],
  veranstalter: ["ev", "veranstalter"],
  kalender: ["art", "kalender"],
  teilen: ["art", "teilen"],
  abo: ["rhythmus", "abo"],
  melden: ["kategorie", "melden"],
  suche: ["q", "suche"],
};

function zaehle(map, key, n) {
  if (key == null || key === "") return;
  map.set(key, (map.get(key) || 0) + (n == null ? 1 : n));
}

function top(map, max) {
  return Array.from(map, ([k, n]) => ({ k, n }))
    .sort((a, b) => b.n - a.n || (a.k < b.k ? -1 : a.k > b.k ? 1 : 0))
    .slice(0, max || MAX_EINTRAEGE);
}

/**
 * Rechnet die Rohtreffer EINES Tages zu einem Tagesdokument zusammen.
 * `tag` ist der Kalendertag (YYYY-MM-DD, Europe/Berlin), zu dem die
 * Treffer gehören; die Funktion prüft das nicht noch einmal.
 */
function aggregiere(hits, tag) {
  const pv = hits.filter((h) => h && h.e === "pv");

  const besucher = new Set();
  const stunden = new Array(24).fill(0);
  const seiten = new Map();
  const laender = new Map();
  const sprachen = new Map();
  const seitensprache = new Map();
  const schema = new Map();
  const geraete = new Map();
  const browser = new Map();
  const systeme = new Map();
  const proSitzung = new Map();

  pv.forEach((h) => {
    besucher.add(h.v || h.s || "?");
    const st = Number(h.h);
    if (Number.isInteger(st) && st >= 0 && st < 24) stunden[st]++;
    zaehle(seiten, h.p);
    zaehle(laender, h.ld);
    zaehle(sprachen, h.la);
    zaehle(seitensprache, h.sl);
    zaehle(schema, h.th);
    zaehle(geraete, h.dv);
    zaehle(browser, h.br);
    zaehle(systeme, h.os);
    const schluessel = h.s || h.v || "?";
    if (!proSitzung.has(schluessel)) proSitzung.set(schluessel, []);
    proSitzung.get(schluessel).push(h);
  });

  let besuche = 0;
  let absprung = 0;
  let dauerSek = 0;
  let dauerN = 0;
  const einstieg = new Map();
  const ausstieg = new Map();
  const referrer = new Map();
  const quellen = new Map();
  const medien = new Map();
  const kampagnen = new Map();

  function schliesseBesuch(folge) {
    if (!folge.length) return;
    const erster = folge[0];
    const letzter = folge[folge.length - 1];
    besuche++;
    zaehle(einstieg, erster.p);
    zaehle(ausstieg, letzter.p);
    zaehle(referrer, erster.r || "(direkt)");
    zaehle(quellen, erster.q);
    zaehle(medien, erster.m);
    zaehle(kampagnen, erster.c);
    if (folge.length === 1) {
      absprung++;
    } else {
      dauerSek += (Number(letzter.t) - Number(erster.t)) / 1000;
      dauerN++;
    }
  }

  proSitzung.forEach((liste) => {
    liste.sort((a, b) => Number(a.t) - Number(b.t));
    let folge = [];
    liste.forEach((h) => {
      if (folge.length && Number(h.t) - Number(folge[folge.length - 1].t) > SITZUNGS_LUECKE_MS) {
        schliesseBesuch(folge);
        folge = [];
      }
      folge.push(h);
    });
    schliesseBesuch(folge);
  });

  const aktionen = new Map();
  const details = {};
  Object.keys(AKTIONS_DETAIL).forEach((e) => { details[AKTIONS_DETAIL[e][1]] = new Map(); });
  const filter = new Map();
  hits.forEach((h) => {
    if (!h || !h.e || h.e === "pv") return;
    zaehle(aktionen, h.e);
    const pr = h.pr && typeof h.pr === "object" ? h.pr : {};
    if (h.e === "filter") {
      if (pr.k) zaehle(filter, `${pr.k}=${pr.w == null ? "" : pr.w}`);
      return;
    }
    const regel = AKTIONS_DETAIL[h.e];
    if (regel) zaehle(details[regel[1]], pr[regel[0]]);
  });

  return {
    d: tag,
    pv: pv.length,
    besucher: besucher.size,
    besuche,
    absprung,
    dauer_sek: Math.round(dauerSek),
    dauer_n: dauerN,
    stunden,
    seiten: top(seiten),
    einstieg: top(einstieg),
    ausstieg: top(ausstieg),
    referrer: top(referrer),
    quellen: top(quellen),
    medien: top(medien),
    kampagnen: top(kampagnen),
    laender: top(laender),
    sprachen: top(sprachen),
    seitensprache: top(seitensprache),
    schema: top(schema),
    geraete: top(geraete),
    browser: top(browser),
    systeme: top(systeme),
    aktionen: top(aktionen),
    events: top(details.events, MAX_EINTRAEGE_LANG),
    veranstalter: top(details.veranstalter, MAX_EINTRAEGE_LANG),
    kalender: top(details.kalender),
    teilen: top(details.teilen),
    abo: top(details.abo),
    melden: top(details.melden),
    suche: top(details.suche, MAX_EINTRAEGE_LANG),
    filter: top(filter, MAX_EINTRAEGE_LANG),
  };
}

// Die Region aus Zeitzone und Browsersprache - ohne IP-Ortung. Für den
// deutschsprachigen Raum reicht das: Deutschland, Österreich und die
// Schweiz haben je eine eigene IANA-Zeitzone. Südtirol lässt sich von
// Italien nicht trennen (Europe/Rome). Codes statt Namen, damit die Seite
// sie in beiden Sprachen beschriften kann.
const ZEITZONE_LAND = {
  "Europe/Berlin": "DE", "Europe/Busingen": "DE",
  "Europe/Vienna": "AT",
  "Europe/Zurich": "CH",
  "Europe/Rome": "IT",
  "Europe/Vaduz": "LI", "Europe/Luxembourg": "LU", "Europe/Brussels": "BE",
  "Europe/Amsterdam": "NL", "Europe/Paris": "FR", "Europe/Prague": "CZ",
  "Europe/Warsaw": "PL", "Europe/Copenhagen": "DK", "Europe/Stockholm": "SE",
  "Europe/Oslo": "NO", "Europe/Helsinki": "FI", "Europe/London": "GB",
  "Europe/Dublin": "IE", "Europe/Madrid": "ES", "Europe/Lisbon": "PT",
  "Europe/Budapest": "HU", "Europe/Ljubljana": "SI", "Europe/Zagreb": "HR",
  "Europe/Bratislava": "SK", "Europe/Athens": "GR",
};
const ERDTEIL_CODE = {
  Europe: "EU", America: "AM", Asia: "AS", Australia: "OC", Pacific: "OC",
  Africa: "AF", Atlantic: "EU", Indian: "AS", Antarctica: "??",
};
const SPRACHREGION_LAND = { AT: "AT", CH: "CH", DE: "DE", IT: "IT", LI: "LI", LU: "LU" };

function landAus(tz, la) {
  const zone = typeof tz === "string" ? tz : "";
  if (ZEITZONE_LAND[zone]) return ZEITZONE_LAND[zone];
  const sprache = typeof la === "string" ? la : "";
  const m = /^[a-z]{2,3}[-_]([A-Za-z]{2})\b/.exec(sprache);
  if (m && SPRACHREGION_LAND[m[1].toUpperCase()]) return SPRACHREGION_LAND[m[1].toUpperCase()];
  const erdteil = zone.split("/")[0];
  if (ERDTEIL_CODE[erdteil]) return ERDTEIL_CODE[erdteil];
  return "??";
}

module.exports = {
  aggregiere,
  landAus,
  top,
  SITZUNGS_LUECKE_MS,
  MAX_EINTRAEGE,
  MAX_EINTRAEGE_LANG,
  AKTIONS_DETAIL,
};

/**
 * functions/stats_aggregate.js
 * ============================
 *
 * Die Rechenregeln der Besucherstatistik - OHNE Firestore, ohne Netz,
 * damit sie sich mit node allein prüfen lassen (test_scraper_lib.py,
 * test_statistik). Benutzt von `aggregateStats` in index.js: Die Function
 * liest die Rohtreffer eines Tages aus der Collection `hits` und schreibt
 * das Ergebnis von aggregiere() als EIN Dokument nach `stats_daily/<Tag>`.
 * Die Seite admin.html liest nur diese Tagesdokumente.
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
 *   pr  Zusatzangaben einer Aktion ({ev, sp}, {art, ev, sp}, {q}, {k, w},
 *       {platz} …)
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
 *   Kanal          = Referrer und Kampagne gebündelt (kanal(): instagram,
 *                    suche, sozial, kampagne, verweis, direkt), ebenfalls
 *                    je Besuch. `instagram` im Tagesdokument trägt Besucher,
 *                    Besuche, Aufrufe, Absprung und Dauer NUR der Besuche
 *                    aus Instagram, `instagram_aktionen` was sie taten.
 *
 * Aufschlüsselungen sind Listen `[{k, n}, …]` absteigend nach n, nicht
 * Maps: Firestore-Feldnamen dürfen keinen Punkt und kein `/` enthalten,
 * und genau die stehen in Hostnamen ("google.com") und Suchbegriffen.
 */
"use strict";

const SITZUNGS_LUECKE_MS = 30 * 60 * 1000;
const MAX_EINTRAEGE = 200;        // je Aufschlüsselung
const MAX_EINTRAEGE_LANG = 500;   // Events, Veranstalter, Suchbegriffe, Filter

// Welche Zusatzangaben einer Aktion gezählt werden (und unter welchem
// Namen die Liste im Tagesdokument steht): je Aktion eine Liste von
// [Feld, Listenname]. Aktionen ohne Eintrag werden nur in `aktionen`
// gezählt. Seit dem 14.10.2026 (Werbekunden-Kennzahlen) zählen Event
// geöffnet und Veranstalter-Klick auch je SPORTART (`sp`, die Zielgruppe:
// wie viel Publikum hat Laufen, wie viel Rad), Kalender und Teilen auch
// je EVENT (`ev`, für den Bericht je Veranstaltung in admin.html), und
// die beiden Werbeplatz-Aktionen je Platz (`platz`, Einblendungen und
// Klicks → Klickrate). Die Listennamen stehen als Kopie in admin.html
// (LISTEN_FELDER) - test_statistik vergleicht.
const AKTIONS_DETAIL = {
  detail: [["ev", "events"], ["sp", "sport_events"]],
  veranstalter: [["ev", "veranstalter"], ["sp", "sport_veranstalter"]],
  kalender: [["art", "kalender"], ["ev", "events_kalender"]],
  teilen: [["art", "teilen"], ["ev", "events_teilen"]],
  abo: [["rhythmus", "abo"]],
  melden: [["kategorie", "melden"]],
  suche: [["q", "suche"]],
  anzeige_sicht: [["platz", "anzeige_sicht"]],
  anzeige_klick: [["platz", "anzeige_klick"]],
};
// Listen, die mehr Einträge brauchen als MAX_EINTRAEGE (je Event, je
// Suchbegriff - alles andere hat wenige verschiedene Werte).
const LANGE_LISTEN = new Set(["events", "veranstalter", "events_kalender", "events_teilen", "suche", "filter"]);

// Der KANAL eines Besuchs (14.10.2026, für den Instagram-Account
// „AusdauerMaschine"): woher der Besuch kam, grob gebündelt. Entschieden
// wird am ERSTEN Aufruf des Besuchs, wie bei Referrer und Kampagne.
// Instagram erkennt drei Spuren - jede allein genügt:
//   - utm_source "instagram"/"ig" (der Link in der Profilbeschreibung und
//     die Story-Links tragen ihn, siehe README „Instagram"),
//   - ein Referrer von instagram.com (auch l.instagram.com, der
//     Weiterleiter für Links aus der App),
//   - der eingebaute Browser der App (stats.js: br = "Instagram").
const SUCHMASCHINEN_RE = /(^|\.)(google\.[a-z.]+|bing\.com|duckduckgo\.com|ecosia\.org|yahoo\.[a-z.]+|qwant\.com|startpage\.com|search\.brave\.com|yandex\.[a-z.]+)$/;
const SOZIAL_RE = /(^|\.)(facebook\.com|fb\.me|t\.co|x\.com|twitter\.com|linkedin\.com|lnkd\.in|pinterest\.[a-z.]+|reddit\.com|tiktok\.com|youtube\.com|whatsapp\.com|wa\.me|t\.me|telegram\.org|strava\.com|threads\.net)$/;
const KANAELE = ["instagram", "suche", "sozial", "kampagne", "verweis", "direkt"];

function istInstagram(h) {
  const q = String((h && h.q) || "").toLowerCase();
  const r = String((h && h.r) || "").toLowerCase();
  return q === "instagram" || q === "ig" || /(^|\.)instagram\.com$/.test(r) || (h && h.br === "Instagram");
}

function kanal(h) {
  if (istInstagram(h)) return "instagram";
  const r = String(h.r || "").toLowerCase();
  if (r && SUCHMASCHINEN_RE.test(r)) return "suche";
  if (r && SOZIAL_RE.test(r)) return "sozial";
  if (h.q) return "kampagne";
  if (r) return "verweis";
  return "direkt";
}

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
  // Region je Sitzung (vom ersten Seitenaufruf) - Aktionen tragen selbst
  // keine Region, die Zielgruppe "Sportart je Region" braucht sie aber.
  const sitzungRegion = new Map();

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
    if (h.s && h.ld && !sitzungRegion.has(h.s)) sitzungRegion.set(h.s, h.ld);
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
  const kanaele = new Map();
  // Instagram (14.10.2026): dieselben Kennzahlen wie oben, nur für die
  // Besuche, die von Instagram kamen - dazu, was diese Besucher taten.
  const ig = { besuche: 0, absprung: 0, pv: 0, dauer_sek: 0, dauer_n: 0 };
  const igBesucher = new Set();
  const igSitzungen = new Set();
  const igMedien = new Map();
  const igKampagnen = new Map();
  const igEinstieg = new Map();

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
    const k = kanal(erster);
    zaehle(kanaele, k);
    if (folge.length === 1) {
      absprung++;
    } else {
      dauerSek += (Number(letzter.t) - Number(erster.t)) / 1000;
      dauerN++;
    }
    if (k === "instagram") {
      ig.besuche++;
      ig.pv += folge.length;
      igBesucher.add(erster.v || erster.s || "?");
      if (erster.s) igSitzungen.add(erster.s);
      zaehle(igMedien, erster.m || "(ohne)");
      zaehle(igKampagnen, erster.c);
      zaehle(igEinstieg, erster.p);
      if (folge.length === 1) {
        ig.absprung++;
      } else {
        ig.dauer_sek += (Number(letzter.t) - Number(erster.t)) / 1000;
        ig.dauer_n++;
      }
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
  Object.keys(AKTIONS_DETAIL).forEach((e) => {
    AKTIONS_DETAIL[e].forEach(([, liste]) => { details[liste] = new Map(); });
  });
  const filter = new Map();
  // Zielgruppe: geöffnete Events je Sportart UND Region der Sitzung
  // ("Laufen|DE"). Ohne bekannte Region "??" - admin.html beschriftet es.
  const sportRegion = new Map();
  const igAktionen = new Map();
  hits.forEach((h) => {
    if (!h || !h.e || h.e === "pv") return;
    zaehle(aktionen, h.e);
    if (h.s && igSitzungen.has(h.s)) zaehle(igAktionen, h.e);
    const pr = h.pr && typeof h.pr === "object" ? h.pr : {};
    if (h.e === "filter") {
      if (pr.k) zaehle(filter, `${pr.k}=${pr.w == null ? "" : pr.w}`);
      return;
    }
    const regeln = AKTIONS_DETAIL[h.e];
    if (regeln) regeln.forEach(([feld, liste]) => zaehle(details[liste], pr[feld]));
    if (h.e === "detail" && pr.sp) {
      zaehle(sportRegion, `${pr.sp}|${sitzungRegion.get(h.s) || "??"}`);
    }
  });

  const ergebnis = {
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
    filter: top(filter, MAX_EINTRAEGE_LANG),
    sport_region: top(sportRegion),
    kanaele: top(kanaele),
    instagram: {
      besucher: igBesucher.size,
      besuche: ig.besuche,
      pv: ig.pv,
      absprung: ig.absprung,
      dauer_sek: Math.round(ig.dauer_sek),
      dauer_n: ig.dauer_n,
    },
    instagram_medien: top(igMedien),
    instagram_kampagnen: top(igKampagnen),
    instagram_einstieg: top(igEinstieg),
    instagram_aktionen: top(igAktionen),
  };
  Object.keys(details).forEach((liste) => {
    ergebnis[liste] = top(details[liste], LANGE_LISTEN.has(liste) ? MAX_EINTRAEGE_LANG : MAX_EINTRAEGE);
  });
  return ergebnis;
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
  kanal,
  istInstagram,
  KANAELE,
  landAus,
  top,
  SITZUNGS_LUECKE_MS,
  MAX_EINTRAEGE,
  MAX_EINTRAEGE_LANG,
  AKTIONS_DETAIL,
  LANGE_LISTEN,
};

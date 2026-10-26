/**
 * functions/index.js
 * =====================
 *
 * Cloud Function "checkNewEvents": wird von scripts/update_events.py nach
 * jedem Scraper-Lauf per HTTPS-POST aufgerufen (nur wenn events.json sich
 * geändert hat) und bekommt die Liste der NEU hinzugefügten Events. Für
 * jedes gespeicherte Filterabo (Firestore-Collection
 * "filterSubscriptions", angelegt über auth.js/events.html "Benachrichtige
 * mich") wird geprüft, ob eines der neuen Events zu den gespeicherten
 * Filtern passt (Datum wird dabei absichtlich NICHT geprüft - das war ja
 * der Grund für das Abo: das Event lag zum Zeitpunkt der Filtersuche noch
 * in der Zukunft). Bei einem Treffer wird ein Dokument in die Collection
 * "mail" geschrieben - im Format der offiziellen Firebase-Extension
 * "Trigger Email from Firestore", die den eigentlichen E-Mail-Versand
 * übernimmt (SMTP/SendGrid-Zugangsdaten werden bei der Extension-
 * Installation hinterlegt, NICHT hier im Code).
 *
 * DEPLOYMENT (Voraussetzung: Firebase-Projekt mit Blaze-Tarif, da Cloud
 * Functions ausgehende Netzwerkaufrufe von update_events.py entgegennehmen
 * müssen - siehe README.md für die vollständige Anleitung):
 *
 *   npm install -g firebase-tools
 *   firebase login
 *   cd functions && npm install && cd ..
 *   firebase functions:secrets:set NOTIFY_WEBHOOK_SECRET   # Wert frei wählen
 *   firebase deploy --only functions
 *
 * `firebase init functions` ist NICHT nötig und sollte auch nicht
 * ausgeführt werden: firebase.json und .firebaserc liegen fertig im Repo,
 * und der Assistent würde anbieten, genau diese index.js zu überschreiben.
 *
 * Der Secret-Schritt ist Pflicht, nicht Kür - ohne gesetztes
 * NOTIFY_WEBHOOK_SECRET verweigert die Function den Dienst (siehe unten).
 * Denselben Wert danach als GitHub-Actions-Secret hinterlegen.
 *
 * Danach die ausgegebene Function-URL als GitHub-Actions-Secret
 * NOTIFY_WEBHOOK_URL hinterlegen (Repo -> Settings -> Secrets and
 * variables -> Actions) - scripts/update_events.py ruft sie dann
 * automatisch nach jedem Lauf auf, in dem sich events.json geändert hat.
 *
 * Zusätzlich einmalig die Extension "Trigger Email from Firestore"
 * installieren (Firebase Console -> Extensions) und dort SMTP-Zugangs-
 * daten (z. B. SendGrid) hinterlegen - ohne diese Extension werden zwar
 * "mail"-Dokumente angelegt, aber keine E-Mails tatsächlich verschickt.
 *
 * WAS DIE FUNCTION NICHT TUT: Sie prüft ausschließlich die Events, die
 * update_events.py ihr als NEU meldet. Bestehende Abos werden also nicht
 * rückwirkend gegen die bereits vorhandenen ~4.100 Events geprüft - ein
 * Abo schlägt erst an, wenn nach dem Deployment ein passendes Event
 * dazukommt.
 */

const { onRequest } = require("firebase-functions/v2/https");
const { defineSecret, defineString } = require("firebase-functions/params");
const { initializeApp } = require("firebase-admin/app");
const { getFirestore, FieldValue } = require("firebase-admin/firestore");
const crypto = require("crypto");

initializeApp();
const db = getFirestore();

// Das gemeinsame Geheimnis, mit dem sich scripts/update_events.py
// ausweist. defineSecret() statt process.env: Bei Functions der 2.
// Generation ist process.env.NOTIFY_WEBHOOK_SECRET nach einem normalen
// Deployment schlicht leer - der Wert muss im Secret Manager liegen und
// der Function ausdrücklich zugeteilt werden (secrets: [...] unten).
// Firebase fragt beim Deploy danach, wenn das Secret noch nicht
// existiert, und genau das ist erwünscht: ohne Geheimnis kein Betrieb.
//
//   firebase functions:secrets:set NOTIFY_WEBHOOK_SECRET
const NOTIFY_WEBHOOK_SECRET = defineSecret("NOTIFY_WEBHOOK_SECRET");

// Vergleicht zwei Zeichenketten in konstanter Zeit. Ein gewöhnliches
// !== verrät über die Antwortzeit, wie viele Zeichen am Anfang schon
// stimmen - über genügend Versuche lässt sich ein Geheimnis so Zeichen
// für Zeichen erraten.
function secretsMatch(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  const bufA = Buffer.from(a, "utf8");
  const bufB = Buffer.from(b, "utf8");
  // timingSafeEqual verlangt gleiche Länge und wirft sonst. Die Länge
  // selbst ist kein nennenswertes Geheimnis.
  if (bufA.length !== bufB.length) return false;
  return crypto.timingSafeEqual(bufA, bufB);
}

// Distanz-Kategorien, identisch zu DISTANCE_CATEGORIES in events.html.
//
// Diese Liste MUSS mit events.html übereinstimmen. Sie stand früher nur
// dort, und die Cloud Function ignorierte den Kategorie-Filter komplett -
// mit zwei Folgen, die beide real aufgetreten sind:
//
//   * Ein Abo mit NUR einer Kategorie ("Marathon", ohne Von/Bis-Werte)
//     traf auf JEDES Event - es gab dann eine E-Mail pro neuem Event.
//   * Das erste echte Abo (Schwimmen 10+ km, zusätzlich 400-500 km)
//     traf auf 42 Events, obwohl die Webseite dafür 0 Treffer anzeigt:
//     Die Von/Bis-Prüfung überspringt Events OHNE Distanzangabe, der
//     Kategorie-Filter der Webseite verlangt dagegen eine bekannte
//     Distanz. Genau diese 42 Events ohne Distanz rutschten durch.
//
// Beim Ändern der Kategorien also immer BEIDE Stellen anpassen.
const DISTANCE_CATEGORIES = {
  Laufen: {
    "5k": (km) => km > 0 && km <= 5,
    "10k": (km) => km > 5 && km <= 10,
    half: (km) => Math.abs(km - 21.0975) <= 0.5,
    marathon: (km) => Math.abs(km - 42.195) <= 0.5,
    ultra: (km) => km > 42.195 + 0.5,
    // Zeitrennen (24-Stunden-Lauf, 6h, 12h): keine Distanz, die sich
    // testen ließe - hier entscheidet dauer_h, siehe ZEIT_CATEGORY_KEY
    // unten und formatLength() in events.html.
    zeit: null,
  },
  Fahrrad: {
    r50: (km) => km > 0 && km <= 50,
    r100: (km) => km > 50 && km <= 100,
    r150: (km) => km > 100 && km <= 150,
    r200: (km) => km > 150 && km <= 200,
    rultra: (km) => km > 200,
    zeit: null,
  },
  Schwimmen: {
    s1: (km) => km > 0 && km <= 1,
    s2: (km) => km > 1 && km <= 2,
    s3: (km) => km > 2 && km <= 3,
    s5: (km) => km > 3 && km <= 5,
    s10: (km) => km > 5,
    zeit: null,
  },
  Triathlon: {
    // Grenzen zwischen den Formaten wie in filters.js (21.09.2026).
    supersprint: (km) => km > 0 && km < 23,
    sprint: (km) => km >= 23 && km < 40,
    olympic: (km) => km >= 40 && km < 80,
    middle: (km) => km >= 80 && km < 160,
    long: (km) => km >= 160 && km < 230,
    tultra: (km) => km >= 230,
  },
};

// Prüft ein Event gegen die gewählten Kategorien. Der Schlüssel ist
// "<Sportart>:<Kategorie>" (z. B. "Schwimmen:s10"), so speichert es
// events.html. Ein Event passt, wenn MINDESTENS eine gewählte Kategorie
// zutrifft (ODER-Verknüpfung, wie in der Liste).
// Kategorie-Schlüssel der Zeitrennen. Sie prüfen dauer_h statt laenge_km;
// in DISTANCE_CATEGORIES steht dafür null statt einer Testfunktion.
const ZEIT_CATEGORY_KEY = "zeit";

// Triathlon-Format - eine KOPIE von triathlonFormat() in filters.js
// (Label, Schwimm-Teilstrecke, Summe; Datenregel 21). Der Längen-Filter
// beim Triathlon prüft das Format, nicht die rohen Kilometer, damit ein
// Abo genau das trifft, was die Liste zeigt. test_triathlon_format_kopie
// vergleicht beide Fassungen Zeile für Zeile.
// Reihenfolge: das Längste zuerst - "Langdistanz" enthält kein "kurz",
// "Super-Sprint" enthält "Sprint", also steht er davor.
const TRIATHLON_FORMAT_IM_LABEL = [
  [/ultra|double|doppel|triple|dreifach|\bdeca\b|quintuple/i, "ultra"],
  [/140[.,]6|langdist|langstreck|lange\s*distanz|\blang\b|long\s*dist|volldist|full\s*dist|ironman[\s-]*dist/i, "lang"],
  [/70[.,]3|mitteldist|\bmittel\b|middle|halbdist|half[\s-]*dist|halb-?ironman/i, "mittel"],
  [/olymp|standard[\s-]*dist|kurzdist|kurz-?distanz|\bkurz\b|short[\s-]*dist/i, "olympisch"],
  [/super[\s-]*sprint/i, "supersprint"],
  [/sprint/i, "sprint"]
];
// Das Schwimmen aus dem Label ("0,3 km Schwimmen", "400 m Swim") in
// Kilometern, oder null. Die Teilstrecken stehen dort in Klammern
// hinter der Gesamtlänge (siehe CLAUDE.md, Elfter Durchgang).
const TRIATHLON_SCHWIMMEN_IM_LABEL = /(\d+(?:[.,]\d+)?)\s*(km|m)\s*(?:schwimmen|swim)/i;
function schwimmKm(e) {
const treffer = TRIATHLON_SCHWIMMEN_IM_LABEL.exec(e.wettbewerb || "");
  if (!treffer) return null;
const wert = parseFloat(treffer[1].replace(",", "."));
  if (Number.isNaN(wert)) return null;
  return treffer[2].toLowerCase() === "m" ? wert / 1000 : wert;
}

function triathlonFormat(e) {
  if (!e || e.art1 !== "Triathlon") return null;
const label = e.wettbewerb || "";
  for (const [muster, key] of TRIATHLON_FORMAT_IM_LABEL) if (muster.test(label)) return key;
  if (e.art2 === "Swimrun" || e.art2 === "Quadrathlon") return null;
const km = Number(e.laenge_km);
  if (e.laenge_km == null || Number.isNaN(km) || km <= 0) return null;
  // Das SCHWIMMEN entscheidet, wo die Summe es nicht kann. Vom Nutzer
  // am 21.09.2026 am "2. Weinstadt Triathlon" gemeldet: 0,3 km
  // Schwimmen / 18,7 km Rad / 4,6 km Laufen, also 23,6 km - knapp
  // ÜBER der Sprint-Grenze von 23 km, und die Box schrieb "Sprint".
  // Richtig ist Super-Sprint, und der Grund steht in den 300 Metern:
  // Ein Sprint schwimmt 500-750 m, ein Super-Sprint 250-500 m.
  //
  // Zwei Zeilen daneben zeigen, warum die Summe das grundsätzlich
  // nicht leisten kann: Der Berliner Volkstriathlon hat bei 23,7 km
  // Gesamtlänge 700 m Schwimmen (ein echter Sprint), der
  // Stadttriathlon Erding bei 25,4 km nur 400 m. Dieselbe Summe,
  // verschiedene Formate - die Radstrecke gleicht den kurzen
  // Schwimmteil wieder aus.
  //
  // Bewusst eng gehalten: Die Regel greift nur, wenn das Label die
  // Teilstrecke überhaupt nennt, nur NACH unten (auf Super-Sprint)
  // und nur, wenn kein Format-Stichwort im Label steht - ein als
  // "Jedermann Sprint" ausgeschriebenes Rennen bleibt ein Sprint,
  // auch mit 400 m Schwimmen. Am Bestand vom 21.09.2026 nachgezählt:
  // zwei Zeilen ändern sich (Erding und der Günzburger Cross
  // Triathlon, beide 400 m).
const schwimmen = schwimmKm(e);
  if (schwimmen != null && schwimmen < 0.5) return "supersprint";
  if (km < 23) return "supersprint";
  if (km < 40) return "sprint";
  if (km < 80) return "olympisch";
  if (km < 160) return "mittel";
  if (km < 230) return "lang";
  return "ultra";
}
const TRIATHLON_FORMAT_KATEGORIE = {
  supersprint: "supersprint", sprint: "sprint", olympisch: "olympic",
  mittel: "middle", lang: "long", ultra: "tultra",
};

function matchesDistanceCategories(event, keys) {
  return keys.some((key) => {
    const [sport, category] = String(key).split(":");
    if (event.art1 !== sport) return false;
    const sportCats = DISTANCE_CATEGORIES[sport] || {};
    if (!(category in sportCats)) return false;
    if (category === ZEIT_CATEGORY_KEY) return event.dauer_h != null;
    // Triathlon: das angezeigte Format entscheidet (wie in filters.js).
    if (sport === "Triathlon") {
      const format = triathlonFormat(event);
      if (format) return TRIATHLON_FORMAT_KATEGORIE[format] === category;
    }
    // Wie in der Liste: ohne bekannte Distanz kein Treffer.
    if (event.laenge_km == null) return false;
    const test = sportCats[category];
    return typeof test === "function" && test(event.laenge_km);
  });
}

// Die Übersetzungen, die die Mastersuche mitdurchsucht - eine KOPIE aus
// filters.js (VALUE_TRANSLATIONS). Nötig, weil die Function den
// Browser-Code nicht laden kann; `test_suche_uebersetzungen` in
// scripts/test_scraper_lib.py vergleicht beide Listen, damit sie nicht
// auseinanderlaufen. Nur die Felder, in denen die Suche sucht.
const SUCH_UEBERSETZUNGEN = {
  land: {
    "Deutschland": ["Deutschland", "Germany"],
    "Österreich": ["Österreich", "Austria"],
    "Schweiz": ["Schweiz", "Switzerland"],
    "Italien (Südtirol)": ["Italien (Südtirol)", "Italy (South Tyrol)"],
  },
  art1: {
    "Laufen": ["Laufen", "Running"],
    "Schwimmen": ["Schwimmen", "Swimming"],
    "Fahrrad": ["Fahrrad", "Cycling"],
    "Triathlon": ["Triathlon", "Triathlon"],
  },
  art2: {
    "Straße": ["Straße", "Road"],
    "Trail": ["Trail", "Trail"],
    "Trail/Cross": ["Trail", "Trail"],
    "Berg": ["Trail", "Trail"],
    "Bahn": ["Bahn", "Track"],
    "Cross": ["Cross", "Cross Country"],
    "Hindernis": ["Hindernis", "Obstacle"],
    "Marsch": ["Marsch", "Walking"],
    "Backyard Ultra": ["Backyard Ultra", "Backyard Ultra"],
    "Backcountry Ultra": ["Backyard Ultra", "Backyard Ultra"],
    "Backyard": ["Backyard Ultra", "Backyard Ultra"],
    "Charity": ["Charity", "Charity"],
    "Freiwasser": ["Freiwasser", "Open Water"],
    "Becken": ["Becken", "Pool"],
    "Zeitfahren": ["Zeitfahren", "Time Trial"],
    "Mountainbike": ["Mountainbike", "Mountain Bike"],
    "Gravel": ["Gravel", "Gravel"],
    "Cyclecross": ["Cyclecross", "Cyclocross"],
    "Duathlon": ["Duathlon", "Duathlon"],
    "Aquathlon": ["Aquathlon", "Aquathlon"],
    "Swimrun": ["Swimrun", "Swimrun"],
    "Quadrathlon": ["Quadrathlon", "Quadrathlon"],
    "Indoor": ["Indoor", "Indoor"],
  },
  standort: {
    "München": ["München", "Munich"],
    "Köln": ["Köln", "Cologne"],
    "Nürnberg": ["Nürnberg", "Nuremberg"],
    "Hannover": ["Hannover", "Hanover"],
    "Braunschweig": ["Braunschweig", "Brunswick"],
    "Konstanz": ["Konstanz", "Constance"],
    "Wien": ["Wien", "Vienna"],
    "Zürich": ["Zürich", "Zurich"],
    "Genf": ["Genf", "Geneva"],
    "Luzern": ["Luzern", "Lucerne"],
    "Basel": ["Basel", "Basel"],
  },
};

// Gegenstück zu sucheHeuhaufen() in filters.js.
function sucheHeuhaufen(event) {
  const teile = [event.name, event.wettbewerb, event.standort,
                 event.land, event.art1, event.art2];
  // Wie in filters.js (sucheHeuhaufen): Ein markiertes Charity-Event
  // soll die Suche nach "Charity"/"Benefiz" auch dann finden, wenn es
  // nicht so heißt.
  if (event.charity) teile.push("Charity", "Benefiz");
  ["land", "art1", "art2", "standort"].forEach((feld) => {
    const werte = SUCH_UEBERSETZUNGEN[feld] && SUCH_UEBERSETZUNGEN[feld][event[feld]];
    if (werte) teile.push(werte[0], werte[1]);
  });
  return teile.filter(Boolean).join(" ").toLowerCase();
}

// Portierte Version der Filterlogik aus events.html getFiltered() - ohne
// den Datumsfilter (das gesuchte Event liegt annahmegemäß in der Zukunft,
// siehe README).
function eventMatchesFilters(event, filters) {
  // Namensfilter wie in filters.js matchEvent(): Name UND Wettbewerb
  // zusammen, damit "Halbmarathon" auch die Halbmarathon-Strecke einer
  // Veranstaltung findet, die das Wort nicht im Namen trägt. Alte Abos
  // haben das Feld nicht - dann wird nicht gefiltert.
  if (filters.nameQuery && String(filters.nameQuery).trim()) {
    const needle = String(filters.nameQuery).trim().toLowerCase();
    const haystack = `${event.name || ""} ${event.wettbewerb || ""}`.toLowerCase();
    if (!haystack.includes(needle)) return false;
  }
  // Die Mastersuche (ein Feld über Name, Wettbewerb, Ort - und Land,
  // Sportart, Kategorie in BEIDEN Sprachen). Muss Zeichen für Zeichen
  // dieselbe Regel sein wie in filters.js sucheHeuhaufen() - sonst
  // bekäme jemand E-Mails über Events, die seine Suche nie gezeigt
  // hätte. Alte Abos haben das Feld nicht.
  if (filters.suche && String(filters.suche).trim()) {
    const needle = String(filters.suche).trim().toLowerCase();
    if (!sucheHeuhaufen(event).includes(needle)) return false;
  }
  if (filters.land && filters.land.length && !filters.land.includes(event.land)) return false;
  if (filters.art1 && filters.art1.length && !filters.art1.includes(event.art1)) return false;
  // Kategorie - mit dem Sonderfall "Charity": Das ist seit dem
  // 21.09.2026 keine Kategorie mehr, sondern ein eigenes Merkmal am
  // Event (event.charity). Dieselbe Auflösung steht in filters.js
  // (matchesKategorie); laufen die beiden auseinander, bekommt jemand
  // E-Mails über Events, die seine Suche nie gezeigt hat.
  if (filters.art2 && filters.art2.length &&
      !filters.art2.includes(event.art2) &&
      !(filters.art2.includes("Charity") &&
        (event.charity === true || event.art2 === "Charity"))) return false;
  if (filters.standort && filters.standort.length && !filters.standort.includes(event.standort)) return false;
  if (filters.laengeMin && event.laenge_km != null && event.laenge_km < parseFloat(filters.laengeMin)) return false;
  if (filters.laengeMax && event.laenge_km != null && event.laenge_km > parseFloat(filters.laengeMax)) return false;
  if (filters.distanceCategories && filters.distanceCategories.length
      && !matchesDistanceCategories(event, filters.distanceCategories)) return false;
  // Umkreis: `radiusKm` ist eine Zahl in Kilometern (Regler in
  // events.html). `radius` ist das alte Format mit vier festen Stufen -
  // Abos aus der Zeit davor liegen noch in Firestore und sollen weiter
  // funktionieren: die alten Stufen waren Ringe ("5-20" = mehr als 5 und
  // höchstens 20 km), hier zählt nur noch die Obergrenze. Das schließt
  // höchstens ein paar nähere Events zusätzlich ein - besser, als ein
  // bestehendes Abo verstummen zu lassen.
  const radiusKm = filters.radiusKm != null
    ? Number(filters.radiusKm)
    : ({ "0-5": 5, "5-20": 20, "20-50": 50, "50+": Infinity })[filters.radius];
  if (radiusKm != null && !Number.isNaN(radiusKm) && filters.origin && filters.origin.lat != null) {
    if (event.lat == null || event.lon == null) return false;
    if (haversineKm(filters.origin.lat, filters.origin.lon, event.lat, event.lon) > radiusKm) return false;
  }
  return true;
}

function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// Die erlaubten Rhythmen. Dieselbe Liste steht in auth.js
// (ABO_RHYTHMEN) und in firestore.rules - test_scraper_lib.py vergleicht
// alle drei gegeneinander, damit sie nicht auseinanderlaufen.
const ABO_RHYTHMEN = ["sofort", "woechentlich", "monatlich"];

// Wie viele Tage zwischen zwei E-Mails mindestens liegen müssen.
//
// Sechs statt sieben Tage bei "woechentlich" ist Absicht: Der Datenlauf
// startet montags um 5:00 UTC, aber nicht auf die Sekunde. Bei genau
// sieben Tagen fiele eine Woche aus, sobald ein Lauf ein paar Minuten
// früher dran ist als der vorige.
const RHYTHMUS_TAGE = { sofort: 0, woechentlich: 6, monatlich: 28 };

// Höchstens so viele Events sammelt ein Abo zwischen zwei E-Mails.
// Firestore-Dokumente dürfen 1 MB groß werden; ein Monatsabo auf "alle
// Events" könnte sonst über die Grenze wachsen. Was darüber liegt, wird
// als Zahl genannt ("und 37 weitere").
const MAX_WARTEND = 50;

// Adresse der Seite - steckt in den Links der E-Mail und im
// Abmelde-Link. Als Parameter, damit sie beim Domainwechsel nicht im
// Code gesucht werden muss: `firebase functions:config` ist veraltet,
// `defineString` liest SITE_URL aus der Umgebung (oder nimmt den
// Vorgabewert).
const SITE_URL = defineString("SITE_URL", {
  default: "https://endurance-events.de",
});

function tageSeit(zeitstempel) {
  if (!zeitstempel) return Infinity;
  const millis = typeof zeitstempel.toMillis === "function"
    ? zeitstempel.toMillis()
    : Date.parse(zeitstempel);
  if (!Number.isFinite(millis)) return Infinity;
  return (Date.now() - millis) / 86400000;
}

// Ist für dieses Abo jetzt eine E-Mail fällig?
function istFaellig(sub) {
  const grenze = RHYTHMUS_TAGE[sub.rhythmus];
  if (grenze == null) return true;          // unbekannt -> nicht zurückhalten
  return tageSeit(sub.zuletztGesendet) >= grenze;
}

// ==== Abo-Mail: Anfang ====
// (test_abo_mail schneidet diesen Abschnitt heraus und rendert ihn in
// node - Marken nicht entfernen.)
//
// Die Abo-Mail im Stil der Seite (seit dem 20.10.2026, vom Nutzer: „Ja,
// bitte die schönere Mail-Vorlage bauen"). Vorher: ISO-Datum, "6.6 km",
// jede Strecke einzeln, und ohne Filter hieß der Betreff „542 neue Events
// für Alle neuen Events". Jetzt:
//
//   - EINE Karte je Veranstaltung (Name + Tag + Ort), darin alle Längen,
//     geschrieben wie in der Liste ("21,1km", "40min", "Sprint").
//   - Datum mit Wochentag, ein vorläufiger Termin nur als Monat mit *.
//   - Farben des Style Guides (Navy, Kreide, Sportfarben) - nur als
//     Inline-Stile in Tabellen: Mail-Programme kennen kein Stylesheet,
//     kein Flexbox, keine Webschrift. KEINE Bilder: Ein Bild vom eigenen
//     Server verriete beim Öffnen, wer die Mail gelesen hat.
//   - Eine Textfassung daneben (`text`), für Programme ohne HTML und
//     gegen den Spam-Filter.
//   - Alles aus den Daten wird maskiert - Namen kommen aus Kalendern.
//
// Ein Event auf das, was in die E-Mail gehört. Bewusst KEIN Link auf die
// Detailseite (?event=<slug>): Der Slug entsteht aus Datum, Name, Maßzahl
// und Ort, und diese Regel steht schon zweimal im Projekt (events.html
// und build_ics.py, gegeneinander geprüft). Eine dritte Kopie hier würde
// irgendwann abweichen und tote Links verschicken - die E-Mail verlinkt
// deshalb die Liste mit der Suche nach dem Namen (`?s=`) und die
// Veranstalter-Seite.
function eventKurz(event) {
  return {
    name: String(event.name || "").slice(0, 200),
    wettbewerb: event.wettbewerb ? String(event.wettbewerb).slice(0, 200) : null,
    datum_start: event.datum_start || null,
    datum_ende: event.datum_ende || null,
    datum_vorlaeufig: event.datum_vorlaeufig ? true : null,
    standort: String(event.standort || "").slice(0, 120),
    land: event.land || null,
    art1: event.art1 || null,
    art2: event.art2 || null,
    charity: event.charity === true,
    laenge_km: event.laenge_km != null ? event.laenge_km : null,
    gedaechtnis: event.gedaechtnis === true,
    dauer_h: event.dauer_h != null ? event.dauer_h : null,
    hoehenmeter: event.hoehenmeter != null ? event.hoehenmeter : null,
    veranstalter_url: event.veranstalter_url || null,
  };
}

// Der Abmelde-Link für die E-Mail. Er zeigt auf die zweite Function
// (`unsubscribe`) und trägt Abo-Kennung und Token - damit genügt EIN
// Klick, ohne Anmeldung. Die Adresse der Function steht erst nach dem
// ersten Deployment fest, deshalb ein Parameter: `firebase deploy` mit
// gesetztem UNSUBSCRIBE_URL. Fehlt sie, verweist die E-Mail auf die
// Abo-Verwaltung der Seite - das verlangt eine Anmeldung, ist aber
// besser als gar kein Weg heraus.
const UNSUBSCRIBE_URL = defineString("UNSUBSCRIBE_URL", { default: "" });

function seitenBasis() {
  return SITE_URL.value().replace(/\/+$/, "");
}

function abmeldeLink(subId, token) {
  const funktion = UNSUBSCRIBE_URL.value();
  if (funktion && token) {
    return `${funktion}?abo=${encodeURIComponent(subId)}&token=${encodeURIComponent(token)}`;
  }
  return `${seitenBasis()}/events.html?abos=1`;
}

function esc(text) {
  return String(text == null ? "" : text)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// Nur http(s) wird verlinkt - eine Adresse aus einem Kalender ist Text,
// kein Vertrauen.
function sichereUrl(url) {
  return /^https?:\/\/[^\s"'<>]+$/i.test(String(url || "")) ? String(url) : null;
}

// Zahlen wie auf der Seite (EF.formatNumber, Deutsch): eine Stelle,
// Komma, ganze Zahlen ohne ",0".
function zahl(wert, stellen) {
  const n = Math.round(Number(wert) * Math.pow(10, stellen)) / Math.pow(10, stellen);
  return (Number.isInteger(n) ? String(n) : n.toFixed(stellen)).replace(".", ",");
}

const TRIATHLON_FORMAT_NAME = {
  supersprint: "Super-Sprint", sprint: "Sprint", olympisch: "Olympisch",
  mittel: "Mitteldistanz (70.3)", lang: "Langstrecke (140.6)", ultra: "Ultra-Triathlon",
};
// Wie DUATHLON_NAMEN in event-detail.js: "70.3"/"140.6" sind
// Triathlon-Marken, und ein Ultra-Duathlon ist kein Ultra-Triathlon.
const DUATHLON_NAME = { mittel: "Mitteldistanz", lang: "Langstrecke", ultra: "Ultra-Duathlon" };

// Die Länge einer Strecke wie in der Länge-Spalte der Liste
// (EED.formatLength): Triathlon-Format, sonst km, sonst Dauer (unter
// einer Stunde in Minuten), sonst Höhenmeter, beim Backyard "Open End".
function laengeText(e) {
  const format = triathlonFormat(e);
  if (format) {
    if (e.art2 === "Duathlon" && DUATHLON_NAME[format]) return DUATHLON_NAME[format];
    return TRIATHLON_FORMAT_NAME[format];
  }
  if (e.laenge_km != null && Number(e.laenge_km) > 0) return `${zahl(e.laenge_km, 1)}km`;
  if (e.dauer_h != null && Number(e.dauer_h) > 0) {
    const h = Number(e.dauer_h);
    return h < 1 ? `${Math.round(h * 60)}min` : `${zahl(h, 1)}h`;
  }
  if (e.hoehenmeter != null && Number(e.hoehenmeter) > 0) {
    return `${Number(e.hoehenmeter).toLocaleString("de-DE")}hm`;
  }
  if (e.art2 === "Backyard Ultra") return "Open End";
  return null;
}

const WOCHENTAGE = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];
const MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
  "August", "September", "Oktober", "November", "Dezember"];

function isoTeile(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
  if (!m) return null;
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
  return { j: m[1], m: m[2], t: m[3], wt: WOCHENTAGE[d.getUTCDay()] };
}

// "Sa, 25.10.2026", mehrtägig "Sa, 24.10. – So, 25.10.2026"; ein
// vorläufiger Termin (datum_vorlaeufig) wie auf der Seite nur als Monat
// mit Sternchen: "Juni 2027*".
function datumText(e) {
  const a = isoTeile(e.datum_start);
  if (!a) return "";
  if (e.datum_vorlaeufig) return `${MONATE[Number(a.m) - 1]} ${a.j}*`;
  const b = isoTeile(e.datum_ende);
  if (!b || e.datum_ende === e.datum_start) return `${a.wt}, ${a.t}.${a.m}.${a.j}`;
  const links = a.j === b.j ? `${a.wt}, ${a.t}.${a.m}.` : `${a.wt}, ${a.t}.${a.m}.${a.j}`;
  return `${links} – ${b.wt}, ${b.t}.${b.m}.${b.j}`;
}

// Farben des Style Guides: Linie, Tonfläche, Schrift auf der Tonfläche.
const SPORT_FARBE = {
  Laufen: ["#E8590C", "#FFF1E8", "#9A3B05"],
  Fahrrad: ["#2B8A3E", "#E9F7EC", "#1B5E2B"],
  Schwimmen: ["#1971C2", "#E7F1FC", "#0F4C86"],
  Triathlon: ["#7048E8", "#F1ECFF", "#482FA6"],
};
const NAVY = "#0B1B33";
const KREIDE = "#F4F2ED";
const LINIE = "#E2DED5";
const TINTE = "#0F1B20";
const GRAU = "#66707F";
const SCHRIFT = "Arial, Helvetica, sans-serif";
const SCHRIFT_GROSS = "'Barlow Condensed', 'Arial Narrow', Arial, sans-serif";

// Die Strecken eines Abos zu Veranstaltungen: Name + Tag + Ort, wie das
// Zusammenfassen der Liste. Längen ohne Doppel, kürzeste zuerst.
function veranstaltungen(wartend) {
  const gruppen = new Map();
  for (const e of wartend) {
    const key = `${String(e.name || "").toLowerCase()}|${e.datum_start}|${String(e.standort || "").toLowerCase()}`;
    if (!gruppen.has(key)) gruppen.set(key, { e, zeilen: [] });
    gruppen.get(key).zeilen.push(e);
  }
  const rang = (z) => (z.laenge_km != null ? Number(z.laenge_km) : z.dauer_h != null ? 10000 + Number(z.dauer_h) : 99999);
  return [...gruppen.values()]
    .map((g) => {
      const zeilen = g.zeilen.slice().sort((x, y) => rang(x) - rang(y));
      const laengen = [...new Set(zeilen.map(laengeText).filter(Boolean))];
      return {
        e: g.e,
        laengen,
        vorlaeufig: zeilen.some((z) => z.datum_vorlaeufig),
        gedaechtnis: zeilen.some((z) => z.gedaechtnis),
        charity: zeilen.some((z) => z.charity),
        url: sichereUrl(zeilen.map((z) => z.veranstalter_url).find(Boolean)),
      };
    })
    .sort((x, y) => String(x.e.datum_start).localeCompare(String(y.e.datum_start)));
}

function listenLink(name) {
  return `${seitenBasis()}/events.html?s=${encodeURIComponent(String(name || "").slice(0, 80))}`;
}

function knopf(href, text, hell) {
  const farbe = hell ? `background:#ffffff;color:${NAVY};border:1px solid ${LINIE};` : `background:${NAVY};color:#ffffff;border:1px solid ${NAVY};`;
  return `<a href="${esc(href)}" style="${farbe}display:inline-block;margin:0 6px 6px 0;padding:9px 14px;border-radius:10px;` +
    `font-family:${SCHRIFT};font-size:14px;font-weight:bold;text-decoration:none;">${esc(text)}</a>`;
}

function karteHtml(g) {
  const [linie, ton, tonSchrift] = SPORT_FARBE[g.e.art1] || [NAVY, "#EDF1F7", NAVY];
  const ort = [g.e.standort, g.e.land].filter(Boolean).join(" · ");
  const abzeichen = [g.e.art1, g.e.art2].filter(Boolean).join(" · ");
  const marken =
    (abzeichen ? `<span style="display:inline-block;background:${ton};color:${tonSchrift};border-radius:999px;padding:3px 10px;` +
      `font-family:${SCHRIFT};font-size:12px;font-weight:bold;">${esc(abzeichen)}</span>` : "") +
    (g.charity ? ` <span style="display:inline-block;background:#FDECEF;color:#A3123A;border-radius:999px;padding:3px 10px;` +
      `font-family:${SCHRIFT};font-size:12px;font-weight:bold;">&#9829; Charity</span>` : "");
  const strecken = g.laengen.length
    ? `<p style="margin:10px 0 0;font-family:${SCHRIFT};font-size:14px;color:${TINTE};">` +
      `<span style="color:${GRAU};">${g.laengen.length > 1 ? "Strecken" : "Strecke"}:</span> ` +
      `<strong>${g.laengen.map(esc).join(" &middot; ")}</strong>${g.gedaechtnis ? "*" : ""}</p>`
    : "";
  const hinweise = [];
  if (g.vorlaeufig) hinweise.push("* Termin noch zu bestätigen");
  if (g.gedaechtnis) hinweise.push("* Strecke aus dem Vorjahr, noch zu bestätigen");
  const knoepfe = knopf(listenLink(g.e.name), "Zum Event", false) +
    (g.url ? knopf(g.url, "Veranstalter-Seite", true) : "");
  return (
    `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" ` +
    `style="background:#ffffff;border:1px solid ${LINIE};border-left:4px solid ${linie};border-radius:12px;margin:0 0 14px;">` +
    `<tr><td style="padding:16px 18px;">` +
    `<p style="margin:0 0 4px;font-family:${SCHRIFT};font-size:13px;font-weight:bold;color:${tonSchrift};text-transform:uppercase;letter-spacing:.04em;">${esc(datumText(g.e))}</p>` +
    `<p style="margin:0 0 6px;font-family:${SCHRIFT_GROSS};font-size:22px;line-height:1.2;font-weight:bold;color:${TINTE};">${esc(g.e.name)}</p>` +
    (ort ? `<p style="margin:0 0 10px;font-family:${SCHRIFT};font-size:14px;color:${GRAU};">${esc(ort)}</p>` : "") +
    marken + strecken +
    (hinweise.length ? `<p style="margin:6px 0 0;font-family:${SCHRIFT};font-size:12px;color:${GRAU};">${esc(hinweise.join(" · "))}</p>` : "") +
    `<p style="margin:14px 0 -6px;">${knoepfe}</p>` +
    `</td></tr></table>`
  );
}

function karteText(g) {
  const zeilen = [`${datumText(g.e)}  ${g.e.name}`];
  const ort = [g.e.standort, g.e.land].filter(Boolean).join(", ");
  const art = [g.e.art1, g.e.art2].filter(Boolean).join(" · ");
  if (ort || art) zeilen.push([ort, art].filter(Boolean).join(" – "));
  if (g.laengen.length) zeilen.push(`${g.laengen.length > 1 ? "Strecken" : "Strecke"}: ${g.laengen.join(", ")}${g.gedaechtnis ? "*" : ""}`);
  if (g.vorlaeufig) zeilen.push("* Termin noch zu bestätigen");
  if (g.gedaechtnis) zeilen.push("* Strecke aus dem Vorjahr, noch zu bestätigen");
  zeilen.push(listenLink(g.e.name));
  if (g.url) zeilen.push(`Veranstalter: ${g.url}`);
  return zeilen.join("\n");
}

// Das Gerüst: Navy-Kopf mit der Marke, Kreide-Fläche, Fußzeile. Breite
// höchstens 600 px - die übliche Breite, die jedes Mail-Programm zeigt.
function mailGeruest({ titel, vorschau, kopf, inhalt, fuss }) {
  return (
    `<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">` +
    `<meta name="viewport" content="width=device-width, initial-scale=1">` +
    `<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light">` +
    `<title>${esc(titel)}</title></head>` +
    `<body style="margin:0;padding:0;background:${KREIDE};">` +
    `<div style="display:none;max-height:0;overflow:hidden;opacity:0;">${esc(vorschau)}</div>` +
    `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:${KREIDE};">` +
    `<tr><td align="center" style="padding:24px 12px;">` +
    `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;">` +
    `<tr><td style="background:${NAVY};border-radius:14px 14px 0 0;padding:18px 24px;">` +
    `<a href="${esc(seitenBasis())}/" style="text-decoration:none;font-family:${SCHRIFT_GROSS};font-size:22px;font-weight:bold;color:#ffffff;">` +
    `Endurance Events<span style="color:#E8590C;">&#9679;</span></a>` +
    `<div style="font-family:${SCHRIFT};font-size:12px;color:#B8C2D3;margin-top:2px;">Ausdauersport im deutschsprachigen Raum</div>` +
    `</td></tr>` +
    `<tr><td style="background:#ffffff;padding:22px 24px 18px;border:1px solid ${LINIE};border-top:0;border-radius:0 0 14px 14px;">` +
    kopf + `</td></tr>` +
    `<tr><td style="background:${KREIDE};padding:18px 0 4px;">` + inhalt + `</td></tr>` +
    `<tr><td style="padding:10px 4px 0;font-family:${SCHRIFT};font-size:12px;line-height:1.6;color:${GRAU};">` +
    fuss + `</td></tr>` +
    `</table></td></tr></table></body></html>`
  );
}

function rhythmusText(rhythmus) {
  if (rhythmus === "woechentlich") return "wöchentlich";
  if (rhythmus === "monatlich") return "monatlich";
  return "sofort bei neuen Events";
}

const OHNE_FILTER = ["alle neuen events", "all new events"];

// Höchstens so viele Karten je Mail: eine Karte sind gut 2 KB, und Gmail
// kürzt eine Nachricht ab etwa 100 KB („Nachricht gekürzt"). Der Rest
// steht als Zahl darunter, mit dem Weg in die Liste.
const MAX_KARTEN = 30;

function restText(weitere, uebersprungen) {
  const teile = [];
  if (weitere > 0) teile.push(`${weitere} weitere Events`);
  if (uebersprungen > 0) teile.push(`${teile.length ? "dazu " : ""}${uebersprungen} weitere Strecken`);
  return teile.length ? `… und ${teile.join(", ")} – alle in der Liste.` : "";
}

// Die Nachricht eines Abos: eine Karte je Veranstaltung, ein Knopf in
// die Liste, der Abmelde-Weg. `wartend` sind eventKurz()-Zeilen.
function aboMail(subId, sub, wartend, uebersprungen) {
  const gruppen = veranstaltungen(wartend);
  const name = String(sub.name || "").trim();
  const mitFilter = name && !OHNE_FILTER.includes(name.toLowerCase());
  const mehr = uebersprungen > 0 ? "+" : "";
  const betreff = gruppen.length === 1 && !mehr
    ? `Neues Event: ${gruppen[0].e.name}`
    : `${gruppen.length}${mehr} neue Events${mitFilter ? `: ${name}` : " auf Endurance Events"}`;
  const ueberschrift = gruppen.length === 1 && !mehr ? "1 neues Event für dich" : `${gruppen.length}${mehr} neue Events für dich`;
  const passend = mitFilter
    ? `Neu auf endurance-events.de und passend zu deinem Abo <strong>${esc(name)}</strong>:`
    : "Neu auf endurance-events.de:";
  const karten = gruppen.slice(0, MAX_KARTEN);
  const rest = restText(gruppen.length - karten.length, uebersprungen);
  const abmelden = abmeldeLink(subId, sub.token);
  const liste = `${seitenBasis()}/events.html`;
  const html = mailGeruest({
    titel: betreff,
    vorschau: karten.slice(0, 3).map((g) => g.e.name).join(" · "),
    kopf:
      `<p style="margin:0 0 6px;font-family:${SCHRIFT_GROSS};font-size:28px;line-height:1.15;font-weight:bold;color:${TINTE};">${esc(ueberschrift)}</p>` +
      `<p style="margin:0;font-family:${SCHRIFT};font-size:15px;line-height:1.5;color:${TINTE};">${passend}</p>`,
    inhalt: karten.map(karteHtml).join("") +
      (rest ? `<p style="margin:0 0 14px;font-family:${SCHRIFT};font-size:14px;color:${GRAU};">${esc(rest)}</p>` : "") +
      `<p style="margin:6px 0 0;text-align:center;">${knopf(liste, "Alle Events ansehen", false)}</p>`,
    fuss:
      `Du bekommst diese E-Mail, weil du auf endurance-events.de ein Abo für neue Events angelegt hast ` +
      `(${esc(rhythmusText(sub.rhythmus))}).<br>` +
      `<a href="${esc(abmelden)}" style="color:${GRAU};">Abo beenden</a> &middot; ` +
      `<a href="${esc(liste)}?abos=1" style="color:${GRAU};">Abos verwalten</a> &middot; ` +
      `<a href="${esc(seitenBasis())}/impressum.html" style="color:${GRAU};">Impressum</a>`,
  });
  const text = [
    `${ueberschrift}${mitFilter ? ` – passend zu deinem Abo „${name}“` : ""}`,
    "",
    karten.map(karteText).join("\n\n"),
    rest ? `\n${rest}` : "",
    "",
    `Alle Events: ${liste}`,
    "",
    `Du bekommst diese E-Mail, weil du auf endurance-events.de ein Abo für neue Events angelegt hast (${rhythmusText(sub.rhythmus)}).`,
    `Abo beenden: ${abmelden}`,
  ].join("\n");
  return { subject: betreff, html, text };
}

// Die alten Einmal-Abos (vor den Rhythmen, ohne `rhythmus`): EIN Event,
// danach Ruhe - im selben Gewand.
function einmalMail(event) {
  const gruppe = veranstaltungen([eventKurz(event)])[0];
  const liste = `${seitenBasis()}/events.html`;
  return {
    subject: `Neues Event gefunden: ${gruppe.e.name}`,
    html: mailGeruest({
      titel: `Neues Event gefunden: ${gruppe.e.name}`,
      vorschau: gruppe.e.name,
      kopf:
        `<p style="margin:0 0 6px;font-family:${SCHRIFT_GROSS};font-size:28px;line-height:1.15;font-weight:bold;color:${TINTE};">Dein Event ist da</p>` +
        `<p style="margin:0;font-family:${SCHRIFT};font-size:15px;line-height:1.5;color:${TINTE};">Ein neues Event passt zu deinem gespeicherten Filter:</p>`,
      inhalt: karteHtml(gruppe),
      fuss:
        `Du bekommst diese E-Mail einmal, weil du dich auf endurance-events.de für eine Benachrichtigung angemeldet hast.<br>` +
        `<a href="${esc(liste)}?abos=1" style="color:${GRAU};">Abos verwalten</a> &middot; ` +
        `<a href="${esc(seitenBasis())}/impressum.html" style="color:${GRAU};">Impressum</a>`,
    }),
    text: `Dein Event ist da – es passt zu deinem gespeicherten Filter:\n\n${karteText(gruppe)}\n\nAbos verwalten: ${liste}?abos=1`,
  };
}
// ==== Abo-Mail: Ende ====

// Abmelden mit einem Klick, OHNE Anmeldung: Abo-Kennung und Token stehen
// im Link der E-Mail. Der Token ist das einzige Geheimnis - deshalb wird
// er zeitkonstant verglichen (wie das Webhook-Secret), damit sich aus der
// Antwortzeit nichts ablesen lässt.
//
// GET und POST: Ein Klick im Mail-Programm ist ein GET, der
// "One-Click"-Knopf aus dem List-Unsubscribe-Kopf ein POST.
exports.unsubscribe = onRequest(
  { region: "europe-west1", cors: false },
  async (req, res) => {
    if (req.method !== "GET" && req.method !== "POST") {
      res.status(405).send("Method Not Allowed");
      return;
    }
    const id = String((req.query && req.query.abo) || (req.body && req.body.abo) || "");
    const token = String((req.query && req.query.token) || (req.body && req.body.token) || "");
    if (!id || !token) {
      res.status(400).send("Fehlende Angaben.");
      return;
    }
    const ref = db.collection("filterSubscriptions").doc(id);
    const snap = await ref.get();
    // Gleiche Antwort für "gibt es nicht" und "Token falsch": Sonst
    // liesse sich über die Antwort herausfinden, welche Abo-Kennungen
    // existieren.
    if (!snap.exists || !secretsMatch(String(snap.data().token || ""), token)) {
      res.status(404).send(seite("Abo nicht gefunden", "Der Link ist nicht (mehr) gültig."));
      return;
    }
    await ref.update({ aktiv: false, abgemeldetAm: FieldValue.serverTimestamp() });
    res.status(200).send(seite(
      "Abo beendet",
      "Du bekommst zu diesem Abo keine E-Mails mehr. Ein neues Abo kannst du auf der Seite jederzeit anlegen."));
  }
);

// Eine winzige Antwortseite - die Function liegt nicht auf der eigenen
// Domain, ein Weiterleiten dorthin würde den Token in den Verlauf
// schreiben.
function seite(titel, text) {
  return `<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">` +
    `<meta name="viewport" content="width=device-width, initial-scale=1">` +
    `<title>${titel}</title><style>` +
    `body{font-family:system-ui,sans-serif;max-width:32rem;margin:10vh auto;padding:0 1rem;` +
    `color:#1c1f24;line-height:1.6}h1{font-size:1.25rem}a{color:#14509a}` +
    `</style></head><body><h1>${titel}</h1><p>${text}</p>` +
    `<p><a href="${seitenBasis()}/events.html">Zur Event-Liste</a></p></body></html>`;
}

exports.checkNewEvents = onRequest(
  { region: "europe-west1", cors: false, secrets: [NOTIFY_WEBHOOK_SECRET] },
  async (req, res) => {
    if (req.method !== "POST") {
      res.status(405).send("Method Not Allowed");
      return;
    }

    // Shared-Secret-Schutz: scripts/update_events.py sendet denselben Wert
    // im Header "X-Notify-Secret" (aus dem GitHub-Actions-Secret
    // NOTIFY_WEBHOOK_SECRET).
    //
    // Fehlt das Geheimnis, verweigert die Function den Dienst, statt die
    // Prüfung zu überspringen. Früher stand hier `if (expectedSecret &&
    // ...)` - war die Variable nicht gesetzt, war die Function für jeden
    // offen, der ihre URL kannte: beliebige erfundene "neue Events"
    // hineinposten, echten Abonnenten eine E-Mail schicken und deren Abo
    // dabei auf notified: true verbrennen. Eine unabsichtlich offene Tür
    // ist schlimmer als eine, die klemmt.
    const expectedSecret = NOTIFY_WEBHOOK_SECRET.value();
    if (!expectedSecret) {
      console.error("NOTIFY_WEBHOOK_SECRET ist nicht gesetzt - Aufruf abgelehnt.");
      res.status(503).send("Service Unavailable: Secret nicht konfiguriert");
      return;
    }
    if (!secretsMatch(req.get("X-Notify-Secret") || "", expectedSecret)) {
      res.status(401).send("Unauthorized");
      return;
    }

    const newEvents = Array.isArray(req.body) ? req.body : req.body && req.body.events;
    if (!Array.isArray(newEvents)) {
      res.status(400).send("Body muss ein Array von Events sein (oder {events: [...]})");
      return;
    }

    // ALLE Abos holen, nicht `where("aktiv", "==", true)`: Abos aus der
    // Zeit vor den Rhythmen haben das Feld gar nicht, und eine
    // Abfrage auf ein fehlendes Feld findet sie nicht. Die Collection
    // ist klein (ein Dokument je Abo je Person); gefiltert wird unten
    // in JavaScript.
    const subsSnap = await db.collection("filterSubscriptions").get();

    let gesendet = 0;
    let gesammelt = 0;
    const batch = db.batch();

    subsSnap.forEach((subDoc) => {
      const sub = subDoc.data();
      if (sub.aktiv === false) return;          // abgemeldet

      const treffer = newEvents.filter((e) => eventMatchesFilters(e, sub.filters || {}));

      // --- Alte Abos: ein einziges Mal benachrichtigen ---
      //
      // Vor den Rhythmen war ein Abo eine Einmal-Zusage ("sag mir, wenn
      // es dieses Event gibt") - angelegt aus der Box bei null Treffern.
      // Diese Zusage bleibt gültig: kein `rhythmus` im Dokument heißt
      // weiter "einmal, dann Ruhe". Kein Datenumzug nötig, und niemand
      // bekommt plötzlich einen Newsletter, den er nie bestellt hat.
      if (!sub.rhythmus) {
        if (sub.notified === true || treffer.length === 0) return;
        gesendet++;
        batch.set(db.collection("mail").doc(), {
          to: sub.email,
          message: einmalMail(treffer[0]),
          createdAt: FieldValue.serverTimestamp(),
        });
        batch.update(subDoc.ref, { notified: true, notifiedAt: FieldValue.serverTimestamp() });
        return;
      }

      // --- Abos mit Rhythmus: sammeln, dann fällig werden ---
      const wartend = Array.isArray(sub.wartend) ? sub.wartend.slice() : [];
      const uebersprungenVorher = Number(sub.uebersprungen) || 0;
      let uebersprungen = uebersprungenVorher;
      treffer.forEach((e) => {
        if (wartend.length < MAX_WARTEND) wartend.push(eventKurz(e));
        else uebersprungen++;
      });

      if (wartend.length === 0) return;         // nichts zu erzählen

      if (!istFaellig(sub)) {
        // Noch nicht fällig (Monatsabo) - nur merken. Die E-Mail kommt
        // beim nächsten Lauf, der nach der Frist liegt.
        if (treffer.length > 0) {
          gesammelt += treffer.length;
          batch.update(subDoc.ref, { wartend, uebersprungen });
        }
        return;
      }

      gesendet++;
      batch.set(db.collection("mail").doc(), {
        to: sub.email,
        // Der Abmelde-Link gehört in den Kopf der Nachricht, nicht nur in
        // den Text: Mail-Programme zeigen daraus einen eigenen
        // Abmelde-Knopf, und wer den nutzt, markiert die Mail nicht als
        // Spam. Die Extension "Trigger Email" übernimmt `headers`.
        headers: {
          "List-Unsubscribe": `<${abmeldeLink(subDoc.id, sub.token)}>`,
          "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
        message: aboMail(subDoc.id, sub, wartend, uebersprungen),
        createdAt: FieldValue.serverTimestamp(),
      });
      batch.update(subDoc.ref, {
        wartend: [],
        uebersprungen: 0,
        zuletztGesendet: FieldValue.serverTimestamp(),
      });
    });

    if (gesendet > 0 || gesammelt > 0) await batch.commit();

    res.status(200).json({
      checkedSubscriptions: subsSnap.size,
      mailsQueued: gesendet,
      collectedForLater: gesammelt,
    });
  }
);

// ======================================================================
// Besucherstatistik (seit dem 13.10.2026, vom Nutzer gewünscht: "ein
// Analytics Dashboard … wie viele Leute meine Webseite besucht haben")
// ======================================================================
//
// Zwei Functions, ein Modul:
//
//   collect        nimmt die Treffer von stats.js entgegen (POST, Text als
//                  JSON), prüft sie streng, hängt Tag/Stunde (Europe/Berlin)
//                  und die Besucher-Kennung des Tages an und schreibt sie
//                  nach `hits`. Die Kennung ist ein HMAC aus IP-Adresse und
//                  Browser-String mit einem Schlüssel, der jeden Tag neu
//                  gewürfelt und dabei überschrieben wird (`stats_meta/salt`)
//                  - die Adresse selbst wird nie gespeichert, und am
//                  nächsten Tag ist dieselbe Person nicht wiedererkennbar.
//                  Das ist das Verfahren von Plausible und Umami.
//   aggregateStats läuft stündlich, rechnet heute und gestern (und Lücken
//                  der letzten Woche) aus `hits` zu je EINEM Dokument in
//                  `stats_daily` zusammen (stats_aggregate.js) und löscht
//                  Rohtreffer, die älter als HITS_AUFBEWAHRUNG_TAGE sind.
//
// admin.html liest nur `stats_daily` - und nur, wer in `admins/<uid>`
// steht (firestore.rules). Die Herkunft der Treffer prüft `collect` über
// den Origin-Header gegen STATS_ORIGINS; bei einem Domainwechsel die
// neue Adresse dort eintragen (Parameter, kein Code):
//
//   firebase functions:config ist veraltet - beim Deploy fragt die CLI
//   nach dem Wert, oder er steht in functions/.env (STATS_ORIGINS=…).
//
// Deploy wie gehabt: `firebase deploy --only functions` (der Zeitplan
// braucht die Cloud-Scheduler-API; die CLI schaltet sie beim ersten
// Deploy frei und fragt gegebenenfalls nach).

const { onSchedule } = require("firebase-functions/v2/scheduler");
const { Timestamp } = require("firebase-admin/firestore");
const statsAgg = require("./stats_aggregate.js");

const STATS_ORIGINS = defineString("STATS_ORIGINS", {
  default: "https://antdon930.github.io,https://endurance-events.de,https://www.endurance-events.de",
});

// Kopie von EREIGNISSE in stats.js - test_statistik vergleicht beide.
// `anzeige_sicht`/`anzeige_klick` (14.10.2026) sind die Werbeplatz-Zahlen;
// sie werden erst gesendet, wenn eine Seite EnduranceStats.anzeige() an
// einen Werbeplatz hängt - VORHER gehört der Abschnitt „Besucherstatistik"
// der Datenschutzerklärung ergänzt (siehe stats.js).
const STATS_EREIGNISSE = new Set(['pv', 'detail', 'veranstalter', 'kalender', 'teilen', 'abo', 'melden', 'fehlt', 'suche', 'filter', 'standort', 'anzeige_sicht', 'anzeige_klick']);
// Jede Seite, die stats.js lädt (test_statistik prüft die Liste gegen
// die HTML-Dateien).
const STATS_SEITEN = new Set(["index", "events", "karte", "impressum", "datenschutz", "admin"]);
// Zusatzangaben je Aktion: Feld -> Höchstlänge. Alles andere fliegt.
// Kalender und Teilen tragen seit dem 14.10.2026 auch Event und Sportart
// (für den Bericht je Veranstaltung) - dieselbe Angabe, die „Event
// geöffnet" und der Veranstalter-Klick schon immer mitschicken.
const STATS_PROPS = {
  detail: { ev: 120, sp: 20 },
  veranstalter: { ev: 120, sp: 20 },
  kalender: { art: 20, ev: 120, sp: 20 },
  teilen: { art: 20, ev: 120, sp: 20 },
  abo: { rhythmus: 20 },
  melden: { kategorie: 20 },
  suche: { q: 60 },
  filter: { k: 20, w: 60 },
  anzeige_sicht: { platz: 40 },
  anzeige_klick: { platz: 40 },
};
const STATS_BOT_RE = /bot|crawl|spider|slurp|headless|lighthouse|python-requests|python-urllib|curl\/|wget\/|go-http-client|java\//i;
const HITS_AUFBEWAHRUNG_TAGE = 35;
const HITS_LOESCHEN_JE_LAUF = 4000;

function berlinTeile(date) {
  const teile = {};
  new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Europe/Berlin", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", hour12: false,
  }).formatToParts(date).forEach((p) => { teile[p.type] = p.value; });
  // "24" kommt bei manchen ICU-Versionen für Mitternacht.
  const h = Number(teile.hour) % 24;
  return { d: `${teile.year}-${teile.month}-${teile.day}`, h };
}

function tagMinus(tag, n) {
  const [j, m, d] = tag.split("-").map(Number);
  const dt = new Date(Date.UTC(j, m - 1, d - n));
  return dt.toISOString().slice(0, 10);
}

function statsText(wert, max) {
  return typeof wert === "string" ? wert.trim().slice(0, max) : "";
}

function statsWahl(wert, erlaubt, sonst) {
  return erlaubt.includes(wert) ? wert : sonst;
}

// Aus dem, was der Browser schickt, wird genau das, was gespeichert wird -
// nichts, was hier nicht steht, erreicht die Datenbank.
function pruefeHit(body) {
  if (!body || typeof body !== "object") return null;
  const e = statsText(body.e, 20);
  if (!STATS_EREIGNISSE.has(e)) return null;
  const p = statsText(body.p, 20).toLowerCase();
  if (!STATS_SEITEN.has(p)) return null;
  const s = statsText(body.s, 32).toLowerCase();
  if (!/^[0-9a-f]{8,32}$/.test(s)) return null;
  const hit = { e, p, s };
  if (e === "pv") {
    hit.r = statsText(body.r, 100).toLowerCase().replace(/^www\./, "");
    hit.q = statsText(body.q, 60).toLowerCase();
    hit.m = statsText(body.m, 60).toLowerCase();
    hit.c = statsText(body.c, 60).toLowerCase();
    hit.la = statsText(body.la, 12);
    hit.sl = statsWahl(body.sl, ["de", "en"], "de");
    hit.th = statsWahl(body.th, ["dark", "light"], "dark");
    hit.dv = statsWahl(body.dv, ["handy", "tablet", "rechner"], "rechner");
    hit.br = statsText(body.br, 24) || "Sonstige";
    hit.os = statsText(body.os, 24) || "Sonstige";
    hit.n = body.n === true;
    hit.ld = statsAgg.landAus(statsText(body.tz, 40), hit.la);
    return hit;
  }
  const regeln = STATS_PROPS[e];
  if (regeln && body.pr && typeof body.pr === "object") {
    const pr = {};
    Object.keys(regeln).forEach((feld) => {
      const wert = statsText(body.pr[feld], regeln[feld]);
      if (wert) pr[feld] = wert;
    });
    if (Object.keys(pr).length) hit.pr = pr;
  }
  return hit;
}

let statsSalt = { d: null, salt: null };

// Der Tagesschlüssel: einmal je Tag gewürfelt, beim ersten Treffer des
// neuen Tages ÜBERSCHRIEBEN - der alte ist damit weg, und die
// Besucher-Kennungen von gestern lassen sich mit nichts mehr nachrechnen.
async function tagesSchluessel(d) {
  if (statsSalt.d === d && statsSalt.salt) return statsSalt.salt;
  const ref = db.collection("stats_meta").doc("salt");
  const salt = await db.runTransaction(async (tx) => {
    const snap = await tx.get(ref);
    const daten = snap.exists ? snap.data() : null;
    if (daten && daten.d === d && typeof daten.salt === "string" && daten.salt.length >= 32) {
      return daten.salt;
    }
    const neu = crypto.randomBytes(32).toString("hex");
    tx.set(ref, { d, salt: neu, erneuert: FieldValue.serverTimestamp() });
    return neu;
  });
  statsSalt = { d, salt };
  return salt;
}

function besucherKennung(salt, ip, ua) {
  return crypto.createHmac("sha256", salt).update(`${ip}|${ua}`).digest("hex").slice(0, 16);
}

function clientIp(req) {
  const xff = req.headers["x-forwarded-for"];
  if (typeof xff === "string" && xff) return xff.split(",")[0].trim();
  return String(req.ip || "");
}

function erlaubteOrigins() {
  return new Set(STATS_ORIGINS.value().split(",").map((s) => s.trim()).filter(Boolean));
}

exports.collect = onRequest(
  { region: "europe-west1", cors: false, maxInstances: 5 },
  async (req, res) => {
    const origin = String(req.headers.origin || "");
    if (!erlaubteOrigins().has(origin)) {
      res.status(403).end();
      return;
    }
    res.set("Access-Control-Allow-Origin", origin);
    res.set("Vary", "Origin");
    if (req.method === "OPTIONS") {
      res.set("Access-Control-Allow-Methods", "POST");
      res.set("Access-Control-Allow-Headers", "Content-Type");
      res.set("Access-Control-Max-Age", "86400");
      res.status(204).end();
      return;
    }
    if (req.method !== "POST") {
      res.status(405).end();
      return;
    }
    const ua = String(req.headers["user-agent"] || "");
    if (!ua || STATS_BOT_RE.test(ua)) {
      res.status(204).end();           // still verwerfen, kein Hinweis nach außen
      return;
    }
    let body;
    try {
      const roh = req.rawBody
        ? req.rawBody.toString("utf8")
        : (typeof req.body === "string" ? req.body : JSON.stringify(req.body || {}));
      if (roh.length > 4096) throw new Error("zu groß");
      body = JSON.parse(roh);
    } catch (e) {
      res.status(400).end();
      return;
    }
    const hit = pruefeHit(body);
    if (!hit) {
      res.status(400).end();
      return;
    }
    const jetzt = new Date();
    const { d, h } = berlinTeile(jetzt);
    hit.t = Timestamp.fromDate(jetzt);
    hit.d = d;
    hit.h = h;
    hit.v = besucherKennung(await tagesSchluessel(d), clientIp(req), ua);
    await db.collection("hits").add(hit);
    res.status(204).end();
  }
);

async function aggregiereTag(tag, zusatz) {
  const snap = await db.collection("hits").where("d", "==", tag).get();
  if (snap.empty) return false;
  const hits = snap.docs.map((doc) => {
    const x = doc.data();
    const t = x.t && typeof x.t.toMillis === "function" ? x.t.toMillis() : Number(x.t) || 0;
    return Object.assign({}, x, { t });
  });
  const ergebnis = statsAgg.aggregiere(hits, tag);
  if (zusatz) Object.assign(ergebnis, zusatz);
  ergebnis.aktualisiert = FieldValue.serverTimestamp();
  await db.collection("stats_daily").doc(tag).set(ergebnis);
  return true;
}

// Die aktiven E-Mail-Abos - als Tagesstand ins Dokument von HEUTE
// (14.10.2026, Kennzahl für Werbekunden: das eigene Publikum, und über
// die Tagesdokumente das Wachstum). Gezählt mit Zählabfragen (eine
// Lesung je 1.000 Dokumente), nicht gelesen: Das Dashboard bekommt nur
// die Zahl, nie die Adressen. `aktiv` fehlt an den ältesten Abos - ein
// Abo ohne das Feld ist aktiv, deshalb „alle minus abgemeldete".
async function zaehleAbos() {
  const abos = db.collection("filterSubscriptions");
  const zahl = async (q) => (await q.count().get()).data().count;
  const gesamt = (await zahl(abos)) - (await zahl(abos.where("aktiv", "==", false)));
  const rhythmus = [];
  for (const r of ABO_RHYTHMEN) {
    const n = (await zahl(abos.where("rhythmus", "==", r)))
      - (await zahl(abos.where("rhythmus", "==", r).where("aktiv", "==", false)));
    if (n > 0) rhythmus.push({ k: r, n });
  }
  return { abos_aktiv: gesamt, abos_rhythmus: rhythmus };
}

async function loescheAlteHits(grenze) {
  let geloescht = 0;
  while (geloescht < HITS_LOESCHEN_JE_LAUF) {
    const snap = await db.collection("hits").where("d", "<", grenze).limit(400).get();
    if (snap.empty) break;
    const batch = db.batch();
    snap.docs.forEach((doc) => batch.delete(doc.ref));
    await batch.commit();
    geloescht += snap.size;
    if (snap.size < 400) break;
  }
  return geloescht;
}

exports.aggregateStats = onSchedule(
  { schedule: "7 * * * *", timeZone: "Europe/Berlin", region: "europe-west1", timeoutSeconds: 300, memory: "512MiB" },
  async () => {
    const heute = berlinTeile(new Date()).d;
    const tage = [heute, tagMinus(heute, 1)];
    // Lücken der letzten Woche nachholen (ein verpasster Lauf, ein neues
    // Deployment): Fehlt das Tagesdokument, obwohl es Treffer gibt,
    // entsteht es hier.
    for (let i = 2; i <= 7; i++) {
      const tag = tagMinus(heute, i);
      const vorhanden = await db.collection("stats_daily").doc(tag).get();
      if (!vorhanden.exists) tage.push(tag);
    }
    let abos = null;
    try {
      abos = await zaehleAbos();
    } catch (e) {
      console.warn("aggregateStats: Abos nicht gezählt:", e && e.message ? e.message : e);
    }
    let geschrieben = 0;
    for (const tag of tage) {
      if (await aggregiereTag(tag, tag === heute ? abos : null)) geschrieben++;
    }
    const geloescht = await loescheAlteHits(tagMinus(heute, HITS_AUFBEWAHRUNG_TAGE));
    console.log(`aggregateStats: ${geschrieben} Tagesdokument(e) geschrieben, ${geloescht} alte Treffer gelöscht`);
  }
);

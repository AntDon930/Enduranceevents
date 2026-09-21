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
    sprint: (km) => km > 0 && km < 40,
    olympic: (km) => Math.abs(km - 51.5) <= 3,
    middle: (km) => Math.abs(km - 113) <= 5,
    long: (km) => Math.abs(km - 226) <= 8,
  },
};

// Prüft ein Event gegen die gewählten Kategorien. Der Schlüssel ist
// "<Sportart>:<Kategorie>" (z. B. "Schwimmen:s10"), so speichert es
// events.html. Ein Event passt, wenn MINDESTENS eine gewählte Kategorie
// zutrifft (ODER-Verknüpfung, wie in der Liste).
// Kategorie-Schlüssel der Zeitrennen. Sie prüfen dauer_h statt laenge_km;
// in DISTANCE_CATEGORIES steht dafür null statt einer Testfunktion.
const ZEIT_CATEGORY_KEY = "zeit";

function matchesDistanceCategories(event, keys) {
  return keys.some((key) => {
    const [sport, category] = String(key).split(":");
    if (event.art1 !== sport) return false;
    const sportCats = DISTANCE_CATEGORIES[sport] || {};
    if (!(category in sportCats)) return false;
    if (category === ZEIT_CATEGORY_KEY) return event.dauer_h != null;
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
  if (filters.art2 && filters.art2.length && !filters.art2.includes(event.art2)) return false;
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
  default: "https://antdon930.github.io/Enduranceevents",
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

// Ein Event auf das, was in die E-Mail gehört. Bewusst KEIN Link auf die
// Detailseite (?event=<slug>): Der Slug entsteht aus Datum, Name, Maßzahl
// und Ort, und diese Regel steht schon zweimal im Projekt (events.html
// und build_ics.py, gegeneinander geprüft). Eine dritte Kopie hier würde
// irgendwann abweichen und tote Links verschicken - die E-Mail verlinkt
// deshalb die Veranstalter-Seite und die Liste.
function eventKurz(event) {
  return {
    name: String(event.name || "").slice(0, 200),
    datum_start: event.datum_start || null,
    datum_ende: event.datum_ende || null,
    datum_vorlaeufig: event.datum_vorlaeufig ? true : null,
    standort: String(event.standort || "").slice(0, 120),
    land: event.land || null,
    art1: event.art1 || null,
    art2: event.art2 || null,
    laenge_km: event.laenge_km != null ? event.laenge_km : null,
    dauer_h: event.dauer_h != null ? event.dauer_h : null,
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

// Ein vorläufiger Termin (datum_vorlaeufig, Kalenderprognose) steht wie
// auf der Seite nur als Monat: "Juni 2027 (Termin noch nicht
// veröffentlicht)".
const MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
  "August", "September", "Oktober", "November", "Dezember"];
function datumText(event) {
  const iso = event.datum_start || "";
  if (!event.datum_vorlaeufig || !/^\d{4}-\d{2}/.test(iso)) return iso;
  return `${MONATE[Number(iso.slice(5, 7)) - 1]} ${iso.slice(0, 4)} (Termin noch nicht veröffentlicht)`;
}

function eventEmailHtml(event) {
  const link = event.veranstalter_url
    ? `<p><a href="${event.veranstalter_url}">Zur Veranstalter-Website</a></p>`
    : "";
  return (
    `<h2>${event.name}</h2>` +
    `<p>${event.standort || ""}, ${event.land || ""}<br>` +
    `${datumText(event)}${event.laenge_km ? " · " + event.laenge_km + " km" : ""}</p>` +
    link
  );
}

// Die eigentliche Nachricht eines Abos: eine Liste der neuen Events,
// ein Link in die Liste und der Abmelde-Weg. Bewusst schlicht gehalten
// (keine Bilder, keine Schriften) - so kommt sie überall an und wird
// nicht als Werbung einsortiert.
function aboMail(subId, sub, wartend, uebersprungen) {
  const titel = sub.name ? sub.name : "deinem Abo";
  const anzahl = wartend.length + (uebersprungen || 0);
  const betreff = anzahl === 1
    ? `1 neues Event: ${wartend[0].name}`
    : `${anzahl} neue Events für ${titel}`;
  const rest = uebersprungen > 0
    ? `<p>… und ${uebersprungen} weitere.</p>`
    : "";
  const abmelden = abmeldeLink(subId, sub.token);
  return {
    subject: betreff,
    html:
      `<p>Hallo,</p>` +
      `<p>diese Events sind neu dazugekommen und passen zu <strong>${titel}</strong>:</p>` +
      wartend.map(eventEmailHtml).join("") +
      rest +
      `<p><a href="${seitenBasis()}/events.html">Alle Events ansehen</a></p>` +
      `<p style="color:#888;font-size:0.85em;">Du bekommst diese E-Mail, weil du auf der ` +
      `Ausdauersport-Events-Seite ein Abo für neue Events angelegt hast ` +
      `(${rhythmusText(sub.rhythmus)}). ` +
      `<a href="${abmelden}">Abo beenden</a>.</p>`,
  };
}

function rhythmusText(rhythmus) {
  if (rhythmus === "woechentlich") return "wöchentlich";
  if (rhythmus === "monatlich") return "monatlich";
  return "sofort bei neuen Events";
}

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
          message: {
            subject: `Neues Event gefunden: ${treffer[0].name}`,
            html:
              `<p>Hallo,</p>` +
              `<p>ein neues Event passend zu deinem gespeicherten Filter wurde gefunden:</p>` +
              eventEmailHtml(treffer[0]) +
              `<p style="color:#888;font-size:0.85em;">Du erhältst diese E-Mail, weil du dich auf ` +
              `der Ausdauersport-Events-Seite für eine Benachrichtigung angemeldet hast.</p>`,
          },
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

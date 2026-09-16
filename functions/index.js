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
const { defineSecret } = require("firebase-functions/params");
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

// Portierte Version der Filterlogik aus events.html getFiltered() - ohne
// den Datumsfilter (das gesuchte Event liegt annahmegemäß in der Zukunft,
// siehe README).
function eventMatchesFilters(event, filters) {
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

function eventEmailHtml(event) {
  const link = event.veranstalter_url
    ? `<p><a href="${event.veranstalter_url}">Zur Veranstalter-Website</a></p>`
    : "";
  return (
    `<h2>${event.name}</h2>` +
    `<p>${event.standort || ""}, ${event.land || ""}<br>` +
    `${event.datum_start || ""}${event.laenge_km ? " · " + event.laenge_km + " km" : ""}</p>` +
    link
  );
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

    const subsSnap = await db
      .collection("filterSubscriptions")
      .where("notified", "==", false)
      .get();

    let matchesFound = 0;
    const batch = db.batch();

    subsSnap.forEach((subDoc) => {
      const sub = subDoc.data();
      const matched = newEvents.find((e) => eventMatchesFilters(e, sub.filters || {}));
      if (!matched) return;

      matchesFound++;
      const mailRef = db.collection("mail").doc();
      batch.set(mailRef, {
        to: sub.email,
        message: {
          subject: `Neues Event gefunden: ${matched.name}`,
          html:
            `<p>Hallo,</p>` +
            `<p>ein neues Event passend zu deinem gespeicherten Filter wurde gefunden:</p>` +
            eventEmailHtml(matched) +
            `<p style="color:#888;font-size:0.85em;">Du erhältst diese E-Mail, weil du dich auf ` +
            `der Ausdauersport-Events-Seite für eine Benachrichtigung angemeldet hast.</p>`,
        },
        createdAt: FieldValue.serverTimestamp(),
      });
      batch.update(subDoc.ref, { notified: true, notifiedAt: FieldValue.serverTimestamp() });
    });

    if (matchesFound > 0) await batch.commit();

    res.status(200).json({ checkedSubscriptions: subsSnap.size, matchesFound });
  }
);

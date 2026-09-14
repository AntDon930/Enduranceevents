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
 *   firebase init functions   # bestehendes Projekt wählen, dieses Verzeichnis nutzen
 *   cd functions && npm install
 *   firebase deploy --only functions
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
 */

const { onRequest } = require("firebase-functions/v2/https");
const { initializeApp } = require("firebase-admin/app");
const { getFirestore, FieldValue } = require("firebase-admin/firestore");

initializeApp();
const db = getFirestore();

// Portierte (bewusst vereinfachte) Version der Filterlogik aus
// events.html getFiltered() - ohne Datumsfilter, ohne die feingranularen
// Distanz-Kategorien (Marathon/Halbmarathon/...): diese sind nur in
// events.html definiert (DISTANCE_CATEGORIES) und würden hier dupliziert
// werden müssen. Ein Abo mit einer solchen Kategorie wird daher aktuell
// nur über die einfachen laengeMin/laengeMax-Werte geprüft, falls
// vorhanden - siehe README.md, Abschnitt "Bekannte Einschränkung".
function eventMatchesFilters(event, filters) {
  if (filters.land && filters.land.length && !filters.land.includes(event.land)) return false;
  if (filters.art1 && filters.art1.length && !filters.art1.includes(event.art1)) return false;
  if (filters.art2 && filters.art2.length && !filters.art2.includes(event.art2)) return false;
  if (filters.standort && filters.standort.length && !filters.standort.includes(event.standort)) return false;
  if (filters.laengeMin && event.laenge_km != null && event.laenge_km < parseFloat(filters.laengeMin)) return false;
  if (filters.laengeMax && event.laenge_km != null && event.laenge_km > parseFloat(filters.laengeMax)) return false;
  if (filters.radius && filters.origin && filters.origin.lat != null) {
    if (event.lat == null || event.lon == null) return false;
    const distKm = haversineKm(filters.origin.lat, filters.origin.lon, event.lat, event.lon);
    const buckets = { "0-5": [0, 5], "5-20": [5, 20], "20-50": [20, 50], "50+": [50, Infinity] };
    const [min, max] = buckets[filters.radius] || [0, Infinity];
    if (!(distKm > min && distKm <= max) && !(min === 0 && distKm <= max)) return false;
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
  { region: "europe-west1", cors: false },
  async (req, res) => {
    if (req.method !== "POST") {
      res.status(405).send("Method Not Allowed");
      return;
    }

    // Einfacher Shared-Secret-Schutz statt offener, von jedem aufrufbarer
    // Function: scripts/update_events.py sendet denselben Wert im Header
    // "X-Notify-Secret" (aus dem GitHub-Actions-Secret NOTIFY_WEBHOOK_SECRET).
    const expectedSecret = process.env.NOTIFY_WEBHOOK_SECRET;
    if (expectedSecret && req.get("X-Notify-Secret") !== expectedSecret) {
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

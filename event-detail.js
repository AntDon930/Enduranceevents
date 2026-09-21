// Die Detail-Box eines Events - in der Liste (events.html, neben der
// Tabelle) UND auf der Karte (karte.html, oben rechts über der Karte,
// bis zu zwei nebeneinander gestapelt; vom Nutzer am 19.09.2026
// gewünscht: "genau gleiche Struktur wie wenn man auf eins von der Liste
// klickt").
//
// Warum ausgelagert: Die Box hängt an einem Dutzend Helfern - Kennung
// des Events (eventSlug), Name der Kalenderdatei, Kalender-Menü,
// Teilen, Formatierung von Datum und Länge, Kurzmeldung (Toast) - und
// zwei Kopien davon wären beim nächsten Umbau auseinandergelaufen.
// Dieselbe Linie wie bei filters.js und filter-ui.js.
//
// Anbindung: EnduranceDetail.render(container, event, { t, tv, lang,
// onReport, onClose }). `onReport` (Fehler melden) und `onClose` (das ✕)
// sind optional: Fehlt onClose, gibt es kein ✕ (Liste); fehlt onReport,
// gibt es keinen Melde-Knopf. Die Texte (I18N) mischt jede Seite in ihr
// eigenes I18N-Objekt, wie bei den anderen Modulen.
//
// Innerhalb der Box gibt es KEINE Ids, nur Klassen: Auf der Karte stehen
// bis zu zwei Boxen zugleich, und Ids müssten eindeutig sein.
(function (global) {
  'use strict';

  const EF = global.EnduranceFilters;

  const I18N = {
    de: {
      detail_empty: 'Wähle eine Zeile aus, um Details zu sehen.',
      detail_datum: 'Datum', detail_sportart: 'Sportart', detail_kategorie: 'Kategorie',
      detail_standort: 'Stadt/Ort', detail_land: 'Land', detail_laenge: 'Länge',
      detail_wettbewerb: 'Wettbewerb',
      detail_strecke: 'Strecke',
      detail_veranstalter: 'Veranstalter',
      detail_ort: 'Ort',
      detail_strecken_titel: 'Strecken dieser Veranstaltung',
      detail_link: 'Zur Veranstalterseite',
      detail_map: 'Auf der Karte',
      detail_list: 'In der Liste',
      detail_entfernung: 'Entfernung',
      detail_entfernung_von: (d) => `${d} von deinem Standort`,
      detail_vorlaeufig: 'Termin noch nicht veröffentlicht',
      cal_vorlaeufig: '(Termin vorläufig)',
      detail_close: 'Schließen',
      share_event: 'Dieses Event teilen',
      share_event_done: 'Event kopiert!',
      share_fail: 'Kopieren nicht möglich – bitte die Adresszeile verwenden',
      report_btn: 'Fehler zu diesem Event melden',
      cal_btn: 'Kalender',
      cal_google: 'Google Kalender / Gmail',
      cal_outlook: 'Outlook',
      cal_ics: 'Apple Kalender & andere (.ics)',
      cal_note: 'Ganztägiger Termin. Die .ics-Datei wird geladen – zum Eintragen öffnen.',
      cal_note_apple: 'Ganztägiger Termin. Öffnet sich im Kalender – dort auf „Hinzufügen" tippen. Lädt Safari stattdessen eine Datei, diese in „Dateien" antippen.'
    },
    en: {
      detail_empty: 'Select a row to see details.',
      detail_datum: 'Date', detail_sportart: 'Sport', detail_kategorie: 'Category',
      detail_standort: 'City', detail_land: 'Country', detail_laenge: 'Length',
      detail_wettbewerb: 'Race',
      detail_strecke: 'Distance',
      detail_veranstalter: 'Organizer',
      detail_ort: 'Place',
      detail_strecken_titel: 'Races of this event',
      detail_link: 'Organizer website',
      detail_map: 'On the map',
      detail_list: 'In the list',
      detail_entfernung: 'Distance',
      detail_entfernung_von: (d) => `${d} from your location`,
      detail_vorlaeufig: 'Date not yet published',
      cal_vorlaeufig: '(date provisional)',
      detail_close: 'Close',
      share_event: 'Share this event',
      share_event_done: 'Event copied!',
      share_fail: 'Could not copy – please use the address bar',
      report_btn: 'Report an error in this event',
      cal_btn: 'Calendar',
      cal_google: 'Google Calendar / Gmail',
      cal_outlook: 'Outlook',
      cal_ics: 'Apple Calendar & others (.ics)',
      cal_note: 'All-day event. The .ics file will download – open it to add the event.',
      cal_note_apple: 'All-day event. Opens in Calendar – tap "Add" there. If Safari downloads a file instead, tap it in "Files".'
    }
  };

  const escapeHtml = (s) => EF.escapeHtml(s);

  // ---------- Wettbewerbs-Label ----------

  const CANONICAL_RACE_NAMES = {
    'marathon': 42.2,
    'halbmarathon': 21.1,
    'half marathon': 21.1,
    'halbmarathon (hm)': 21.1
  };

  // Die Wettbewerbs-Bezeichnung, ODER null wenn sie nur die Länge
  // wiederholt.
  //
  // Die Quellen benennen einen Wettbewerb oft schlicht mit seiner Distanz
  // ("50 km", "6 km") oder mit deren kanonischem Namen ("Halbmarathon").
  // Beides steht schon in der Längen-Spalte; im Detailbereich erschien es
  // dadurch zweimal ("Race 50 km" über "Length 50 km"), in der Liste als
  // Unterzeile unter dem Namen. Bei gerundeten Quellenangaben sah es sogar
  // nach einem Widerspruch aus: Unterzeile "6 km" über der Spalte "5.5 km".
  //
  // Bezeichnungen mit eigener Aussage bleiben: "Laufen", "Wandern",
  // "Moslig 8000", "5×5 km Staffel", "26 km Trail". Das Feld selbst bleibt
  // in events.json erhalten - die Duplikat-Erkennung der Scraper braucht
  // es (über "Halbmarathon" wurde der doppelte München-Halbmarathon
  // gefunden).
  function displayWettbewerb(e) {
    const label = (e.wettbewerb || '').trim();
    if (!label) return null;
    const km = e.laenge_km;

    // Kanonischer Name, der genau die gespeicherte Länge bezeichnet?
    const canonical = CANONICAL_RACE_NAMES[label.toLowerCase()];
    if (canonical != null && km != null && Math.abs(canonical - Number(km)) <= 0.5) return null;

    // Bleibt nach Abzug der Distanzangaben und Füllwörter noch etwas übrig?
    const rest = label
      .replace(/\d{1,3}(?:[.,]\d+)?\s*(?:km|kilometer)\b/gi, ' ')
      .replace(/\b(?:ca|circa|etwa|rund|ungefähr|approx|ungefaehr)\b\.?/gi, ' ')
      .replace(/[\s.,;:\-–|~()]+/g, '')
      .trim();
    return rest ? label : null;
  }

  // ---------- Datum und Länge ----------

  function formatDate(iso, lang) {
    return EF.formatDate(iso, lang);
  }

  function formatRange(start, end, lang) {
    if (start === end) return formatDate(start, lang);
    return `${formatDate(start, lang)} – ${formatDate(end, lang)}`;
  }

  // Dasselbe für die Tabelle und die Detail-Box: Ein mehrtägiges Rennen
  // steht in ZWEI Zeilen - Anfangsdatum samt Gedankenstrich, Enddatum
  // darunter. Vorher brach die Zelle dort um, wo gerade Platz war
  // ("18 Sep 2026 – 20" / "Sep 2026", vom Nutzer gemeldet). Ein <br>
  // statt zweier Blöcke, damit `.cell-clamp` (zwei Zeilen) weiter greift
  // und die Zeilenhöhe von 52 px stimmt.
  // Die Textfassung oben bleibt für Melde-Dialog und Teilen-Text - dort
  // wird der Rückgabewert escaped, ein <br> stünde als Zeichenfolge da.
  // `weekday`: mit Wochentag davor ("So 27.09.2026") - die Tabelle seit
  // dem 21.09.2026 (Vorlage des Nutzers).
  function formatRangeHtml(start, end, lang, weekday) {
    const f = weekday ? EF.formatDateWeekday : formatDate;
    if (start === end) return escapeHtml(f(start, lang));
    return `${escapeHtml(f(start, lang))} –<br>${escapeHtml(f(end, lang))}`;
  }
  // Dasselbe für ein EVENT: ein vorläufiger Termin (datum_vorlaeufig)
  // steht als "Juni 2027*", ohne Tag.
  function formatEventRangeHtml(e, lang, weekday) {
    if (e.datum_vorlaeufig) return escapeHtml(EF.formatMonthYear(e.datum_start, lang)) + '*';
    return formatRangeHtml(e.datum_start, e.datum_ende, lang, weekday);
  }

  // Was in der Spalte "Länge" und in der Box steht. Nicht jedes Rennen
  // hat eine Strecke: ein 24-Stunden-Lauf ist über die ZEIT begrenzt,
  // gelaufen wird so weit man kommt. Solche Einträge tragen `dauer_h`
  // statt `laenge_km` und zeigen "24 h".
  //
  // Eine bekannte Distanz hat dabei VORRANG, auch wenn beide Felder
  // gesetzt sind: Beim "24h Mad Chicken Run | Marathon, 42 km" ist das
  // "24h" der Name der Veranstaltung, die Zeile selbst aber eine feste
  // 42-km-Strecke. Sie als "24 h" anzuzeigen würde die Distanz
  // verschlucken.
  // ---------- Triathlon: die Länge ist ein Format ----------

  // Vom Nutzer am 21.09.2026 vorgegeben - erst "Sprint, Kurz, Olympisch,
  // 70.3, 140.6", dann als Bild die sechs Kategorien, die die Liste
  // "genau so" führen soll: Super-Sprint, Sprint, Olympisch,
  // Mitteldistanz (70.3), Langstrecke (140.6), Ultra-Triathlon. Die
  // Normdistanzen dahinter (DTU-Sportordnung, World Triathlon, Ironman):
  //   Super-Sprint   250-500 m / 6,5-13 km / 1,7-3,5 km  (~9-17 km)
  //   Sprint         500-750 m / 18-22 km / 4,5-5,5 km   (~25,75 km)
  //   Olympisch      1,5 / 40 / 10 km = 51,5 km ("Kurz-"/"Standarddistanz")
  //   Mitteldistanz  1,9 / 90 / 21,1 km = 113 km = 70.3 Meilen
  //   Langstrecke    3,8 / 180 / 42,2 km = 226 km = 140.6 Meilen
  //   Ultra          Vielfache der Langstrecke (Double 452 km, Triple, Deca)
  // Die Kilometerzahl - die Summe der Teilstrecken, Datenregel 15 - bleibt
  // in events.json, sie entscheidet Filter und Sortierung; ANGEZEIGT wird
  // das Format. Zwei Quellen, in dieser Reihenfolge:
  // 1. Das Wettbewerbs-Label des Veranstalters ("Kurzdistanz" ist die
  //    Olympische Distanz, "Supersprint" der Super-Sprint).
  // 2. Sonst die Summe: unter 20 km Super-Sprint (Schnupper-, Einsteiger-,
  //    Fitnessdistanzen), bis 40 km Sprint (auch Volks- und Jedermann),
  //    bis 80 km Olympisch, bis 160 km Mitteldistanz, bis 300 km
  //    Langstrecke, darüber Ultra. Das sind GRENZEN zwischen den
  //    Formaten, keine Toleranzen um die Normdistanzen herum, weil
  //    deutsche Veranstaltungen abweichen (Moritzburgs Langdistanz hat
  //    218,8 km, ein Cross-Triathlon 41,5 km) - dieselben Grenzen wie die
  //    Kategorien in filters.js, damit Filter und Spalte dasselbe sagen.
  // Swimrun und Quadrathlon kennen diese Formate nicht (ein 40-km-Swimrun
  // ist kein "Olympisch"): dort zählt nur das Label, sonst die Kilometer.
  const TRIATHLON_FORMATE = {
    supersprint: { rang: 0, de: 'Super-Sprint',         en: 'Super sprint' },
    sprint:      { rang: 1, de: 'Sprint',               en: 'Sprint' },
    olympisch:   { rang: 2, de: 'Olympisch',            en: 'Olympic' },
    mittel:      { rang: 3, de: 'Mitteldistanz (70.3)', en: 'Middle distance (70.3)' },
    lang:        { rang: 4, de: 'Langstrecke (140.6)',  en: 'Long distance (140.6)' },
    ultra:       { rang: 5, de: 'Ultra-Triathlon',      en: 'Ultra triathlon' }
  };
  // Reihenfolge: das Längste zuerst - "Langdistanz" enthält kein "kurz",
  // "Super-Sprint" enthält "Sprint", also steht er davor.
  const FORMAT_IM_LABEL = [
    [/ultra|double|doppel|triple|dreifach|\bdeca\b|quintuple/i, 'ultra'],
    [/140[.,]6|langdist|langstreck|lange\s*distanz|\blang\b|long\s*dist|volldist|full\s*dist|ironman[\s-]*dist/i, 'lang'],
    [/70[.,]3|mitteldist|\bmittel\b|middle|halbdist|half[\s-]*dist|halb-?ironman/i, 'mittel'],
    [/olymp|standard[\s-]*dist|kurzdist|kurz-?distanz|\bkurz\b|short[\s-]*dist/i, 'olympisch'],
    [/super[\s-]*sprint/i, 'supersprint'],
    [/sprint/i, 'sprint']
  ];
  function triathlonFormat(e) {
    if (!e || e.art1 !== 'Triathlon') return null;
    const label = e.wettbewerb || '';
    for (const [muster, key] of FORMAT_IM_LABEL) if (muster.test(label)) return key;
    if (e.art2 === 'Swimrun' || e.art2 === 'Quadrathlon') return null;
    const km = Number(e.laenge_km);
    if (e.laenge_km == null || Number.isNaN(km) || km <= 0) return null;
    if (km < 20) return 'supersprint';
    if (km < 40) return 'sprint';
    if (km < 80) return 'olympisch';
    if (km < 160) return 'mittel';
    if (km < 300) return 'lang';
    return 'ultra';
  }
  // "70.3" und "140.6" sind Triathlon-Marken; ein Duathlon über die
  // Mittel- oder Langdistanz (Spreewald: 19 km Laufen / 84 km Rad / 5 km
  // Laufen) heißt "Mitteldistanz" bzw. "Langstrecke" ohne den Zusatz.
  const DUATHLON_NAMEN = {
    mittel: { de: 'Mitteldistanz', en: 'Middle distance' },
    lang: { de: 'Langstrecke', en: 'Long distance' },
    ultra: { de: 'Ultra-Duathlon', en: 'Ultra duathlon' }
  };
  function formatName(key, lang, e) {
    const sprache = lang === 'en' ? 'en' : 'de';
    if (e && e.art2 === 'Duathlon' && DUATHLON_NAMEN[key]) return DUATHLON_NAMEN[key][sprache];
    return TRIATHLON_FORMATE[key][sprache];
  }

  // `opts.mitKm`: "Kurz (51,5 km)" - für den Fakt in der Box und den
  // Teilen-Text; Tabelle und Pillen zeigen nur das Format.
  function formatLength(e, lang, opts) {
    const format = triathlonFormat(e);
    if (format) {
      const name = formatName(format, lang, e);
      return opts && opts.mitKm && e.laenge_km != null
        ? `${name} (${EF.formatKm(e.laenge_km, lang)})` : name;
    }
    if (e.laenge_km != null) return EF.formatKm(e.laenge_km, lang);
    if (e.dauer_h != null && !Number.isNaN(Number(e.dauer_h))) {
      return EF.formatHours(e.dauer_h, lang);
    }
    // Backyard Ultra ohne Zeitbegrenzung: bewusst "–". Der Lauf endet,
    // wenn nur noch eine Person weiterläuft - es gibt keine Länge, und
    // die Rundenlänge ist keine (siehe clear_backyard_lap_km()).
    return EF.formatKm(null, lang);
  }

  // ---------- Die Kennung eines Events ----------

  // Dateiname der fertigen .ics-Datei. **Muss mit ics_dateiname() in
  // scripts/build_ics.py übereinstimmen** - sonst zeigt der Knopf auf
  // eine Datei, die es nicht gibt. scripts/test_scraper_lib.py prüft
  // beide Umsetzungen gegeneinander (schneidet die vier Funktionen aus
  // DIESER Datei und lässt sie in node laufen), also beim Ändern immer
  // beide anfassen.
  //
  // Aufbau: <datum>-<name>-<distanz>-<ort>.ics. Der Ort gehört dazu, weil
  // Name + Datum + Distanz nicht eindeutig sind ("TEAG - Legend of Cross
  // - Mühlberg" steht am 31.10.2026 mit 10, 17 und 30 km je zweimal in
  // den Daten, einmal unter "Mühlberg" und einmal unter "Drei Gleichen").
  function icsSlug(text) {
    return (text || '')
      .normalize('NFD').replace(/[̀-ͯ]/g, '')
      .toLowerCase()
      .replace(/ß/g, 'ss')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 48)
      .replace(/^-+|-+$/g, '');
  }

  // Sprachunabhängig, bewusst NICHT über EF.formatKm: Dateiname und Slug
  // müssen in DE und EN gleich sein, sonst zeigt ein geteilter Link ins
  // Leere.
  function icsMasszahl(e) {
    if (e.laenge_km != null) {
      return `${(Math.round(Number(e.laenge_km) * 10) / 10)}km`.replace('.', '-');
    }
    if (e.dauer_h != null) {
      return `${(Math.round(Number(e.dauer_h) * 10) / 10)}h`.replace('.', '-');
    }
    return 'x';
  }

  // Die dauerhafte Kennung eines Events: Datum, Name, Maßzahl, Ort.
  // Zwei Dinge hängen daran, deshalb steht sie nur EINMAL hier:
  //   - der Name der Kalenderdatei (icsFileName, muss zu build_ics.py
  //     passen - test_scraper_lib.py prüft beide gegeneinander),
  //   - der Link auf ein einzelnes Event (?event=…, siehe teileEvent).
  // Eine ID in events.json gibt es nicht, und eine laufende Nummer wäre
  // wertlos: Sie verschiebt sich, sobald ein Event dazukommt oder ein
  // vergangenes wegfällt - ein geteilter Link zeigte dann auf ein
  // fremdes Rennen.
  function eventSlug(e) {
    const teile = [e.datum_start || 'ohne-datum', icsSlug(e.name), icsMasszahl(e)];
    const ort = icsSlug(e.standort);
    if (ort) teile.push(ort);
    return teile.join('-');
  }

  function icsFileName(e) {
    return eventSlug(e) + '.ics';
  }

  // Der Link auf genau dieses Event - immer auf die LISTE, auch von der
  // Karte aus (nur sie kennt ?event=). Absolut, damit er in einer
  // Nachricht anklickbar ist.
  function eventLink(e) {
    const basis = new URL('events.html', global.location.href);
    basis.search = '';
    basis.hash = '';
    return `${basis.toString()}?event=${encodeURIComponent(eventSlug(e))}`;
  }

  // ---------- Kurzmeldung (Toast) ----------

  // Kurz aufpoppende Rückmeldung, mittig unten. Das Element entsteht
  // beim ersten Aufruf - die Seiten müssen es nicht vorhalten.
  let toastEl = null;
  let toastTimer = null;
  function showToast(text) {
    if (!toastEl) {
      toastEl = document.createElement('div');
      toastEl.className = 'toast';
      toastEl.setAttribute('role', 'status');
      toastEl.setAttribute('aria-live', 'polite');
      toastEl.hidden = true;
      document.body.appendChild(toastEl);
    }
    global.clearTimeout(toastTimer);
    toastEl.textContent = text;
    toastEl.hidden = false;
    // Ein Bildaufbau muss zwischen hidden=false und der Klasse liegen,
    // sonst gibt es keinen Übergang, sondern einen Sprung.
    global.requestAnimationFrame(() => toastEl.classList.add('visible'));
    toastTimer = global.setTimeout(() => {
      toastEl.classList.remove('visible');
      toastTimer = global.setTimeout(() => { toastEl.hidden = true; }, 220);
    }, 1800);
  }

  // Kopieren mit Rückfallweg: `navigator.clipboard` braucht einen
  // sicheren Kontext (https oder localhost). Ohne den hilft ein
  // unsichtbares Textfeld samt execCommand - alt, aber es funktioniert
  // überall.
  function kopiereInAblage(text, t) {
    if (navigator.clipboard && global.isSecureContext !== false) {
      navigator.clipboard.writeText(text)
        .then(() => showToast(t('share_event_done')))
        .catch(() => showToast(t('share_fail')));
      return;
    }
    try {
      const feld = document.createElement('textarea');
      feld.value = text;
      feld.setAttribute('readonly', '');
      feld.style.cssText = 'position:fixed;top:-1000px;opacity:0';
      document.body.appendChild(feld);
      feld.select();
      const ok = document.execCommand('copy');
      feld.remove();
      showToast(ok ? t('share_event_done') : t('share_fail'));
    } catch (err) {
      showToast(t('share_fail'));
    }
  }

  // ---------- Ein einzelnes Event teilen ----------
  //
  // Geteilt wird ein LINK auf genau dieses Event plus die Angaben, die
  // in der Box stehen - kein PDF und kein Bild. Gründe, der Reihe nach:
  //
  //   - Die Box enthält eine Handvoll Fakten und zwei Links. Wer den
  //     Link antippt, landet genau hier: mit "Zum Kalender hinzufügen",
  //     der Veranstalter-Seite und der Karte daneben. Ein PDF kann das
  //     alles nicht, und es veraltet - verlegt der Veranstalter das
  //     Rennen, ist das PDF für immer falsch.
  //   - `navigator.share()` öffnet den Teilen-Dialog des Geräts.
  //     Damit funktionieren WhatsApp, iMessage, Mail, Signal, Notizen
  //     und AirDrop auf einmal, ohne dass die Seite einen einzigen
  //     Dienst kennen muss.
  //   - Ein PDF bräuchte eine Bibliothek (jsPDF o. Ä., ~150-400 KB) für
  //     ein schlechteres Ergebnis. Wo ein PDF sinnvoll wäre: die ganze
  //     gefilterte Liste als Saisonplan - das ist eine andere Funktion,
  //     und dafür reicht später ein Druck-Stylesheet (der Browser
  //     schreibt daraus selbst ein PDF).
  //
  // Ohne `navigator.share` (Firefox am Rechner, Safari am Mac je nach
  // Version) wird Text + Link in die Ablage kopiert.

  // Die Angaben aus der Box, in der Reihenfolge, in der sie dort stehen.
  function eventShareText(e, ctx) {
    const { tv, lang } = ctx;
    const zeilen = [
      e.name,
      `${EF.formatEventDate(e, lang)} · ${tv('standort', e.standort)}, ${tv('land', e.land)}`,
      `${tv('art1', e.art1)}${e.art2 ? ' / ' + tv('art2', e.art2) : ''} · ${formatLength(e, lang, { mitKm: true })}`
    ];
    const wb = displayWettbewerb(e);
    if (wb) zeilen.splice(2, 0, wb);
    return zeilen.join('\n');
  }

  function teileEvent(e, ctx) {
    const url = eventLink(e);
    const text = eventShareText(e, ctx);
    if (navigator.share) {
      // Bricht jemand den Dialog ab, kommt ein AbortError - das ist
      // keine Panne und darf keine Meldung auslösen.
      navigator.share({ title: e.name, text, url }).catch((err) => {
        if (err && (err.name === 'AbortError' || err.name === 'NotAllowedError')) return;
        kopiereInAblage(text + '\n' + url, ctx.t);
      });
      return;
    }
    kopiereInAblage(text + '\n' + url, ctx.t);
  }

  // ---------- Zum Kalender hinzufügen ----------

  // Alle Termine sind GANZTÄGIG. Startzeiten stehen in keiner Quelle
  // verlässlich (und wenn, dann pro Wettbewerb verschieden) - ein
  // ganztägiger Eintrag behauptet keine Uhrzeit, die wir nicht kennen.
  //
  // Ganztägige Termine enden im iCalendar-Format (RFC 5545) am FOLGETAG:
  // DTEND ist exklusiv. Dasselbe gilt für den dates-Parameter von Google
  // und startdt/enddt von Outlook. Ohne das +1 fehlt der letzte Tag.
  function calDatePlusDays(iso, tage) {
    const [j, m, d] = iso.split('-').map(Number);
    const dt = new Date(Date.UTC(j, m - 1, d));
    dt.setUTCDate(dt.getUTCDate() + tage);
    return dt.toISOString().slice(0, 10);
  }

  function calFields(e, ctx) {
    const { t, tv, lang } = ctx;
    const start = e.datum_start;
    const endeInklusiv = e.datum_ende && e.datum_ende > start ? e.datum_ende : start;
    const wb = displayWettbewerb(e);
    // Ein vorläufiger Termin trägt es im Titel: Der Kalendereintrag muss
    // einen Tag haben, aber niemand soll ihn für veröffentlicht halten.
    const titel = (wb ? `${e.name} – ${wb}` : e.name) + (e.datum_vorlaeufig ? ' ' + t('cal_vorlaeufig') : '');
    const zeilen = [
      `${t('detail_sportart')}: ${tv('art1', e.art1)}${e.art2 ? ' / ' + tv('art2', e.art2) : ''}`,
      `${t('detail_laenge')}: ${formatLength(e, lang, { mitKm: true })}`
    ];
    if (e.datum_vorlaeufig) zeilen.unshift(t('detail_vorlaeufig'));
    if (e.veranstalter_url) zeilen.push(e.veranstalter_url);
    return {
      titel,
      ort: `${tv('standort', e.standort)}${e.land ? ', ' + tv('land', e.land) : ''}`,
      beschreibung: zeilen.join('\n'),
      start,
      endeExklusiv: calDatePlusDays(endeInklusiv, 1),
      url: e.veranstalter_url || ''
    };
  }

  function istIosGeraet() {
    const ua = navigator.userAgent || '';
    return /iPhone|iPad|iPod/.test(ua) || (/Mac/.test(ua) && navigator.maxTouchPoints > 1);
  }

  // Mac ohne Touch = Schreibtisch-macOS. Dort ist der Kalender die
  // Standard-App für .ics, das Öffnen lohnt also genauso.
  function istAppleGeraet() {
    return istIosGeraet() || /Mac/.test(navigator.userAgent || '');
  }

  function schliesseKalenderMenu(box) {
    const menu = box.querySelector('.cal-menu');
    const btn = box.querySelector('.cal-open-btn');
    if (!menu || menu.hidden) return;
    menu.hidden = true;
    if (btn) btn.setAttribute('aria-expanded', 'false');
  }

  function setupCalendarBox(box, e, ctx) {
    const btn = box.querySelector('.cal-open-btn');
    const menu = box.querySelector('.cal-menu');
    if (!btn || !menu) return;
    const f = calFields(e, ctx);
    const kompakt = (iso) => iso.replace(/-/g, '');

    box.querySelector('.cal-google').href =
      'https://calendar.google.com/calendar/render?action=TEMPLATE'
      + `&text=${encodeURIComponent(f.titel)}`
      + `&dates=${kompakt(f.start)}/${kompakt(f.endeExklusiv)}`
      + `&details=${encodeURIComponent(f.beschreibung)}`
      + `&location=${encodeURIComponent(f.ort)}`;

    // Outlook.com deckt private Konten ab; Outlook für Arbeit/Schule
    // (outlook.office.com) versteht dieselbe Adresse und leitet um.
    box.querySelector('.cal-outlook').href =
      'https://outlook.live.com/calendar/0/deeplink/compose?path=/calendar/action/compose&rru=addevent'
      + '&allday=true'
      + `&subject=${encodeURIComponent(f.titel)}`
      + `&startdt=${f.start}`
      + `&enddt=${f.endeExklusiv}`
      + `&body=${encodeURIComponent(f.beschreibung)}`
      + `&location=${encodeURIComponent(f.ort)}`;

    // Die .ics-Datei liegt fertig im Ordner kalender/ (erzeugt von
    // scripts/build_ics.py, eine je Event). Ein einfacher Link genügt -
    // und nur so kommt die Datei mit dem Inhaltstyp text/calendar vom
    // Server, den iOS braucht, um den Termin dem Kalender anzubieten.
    // Alles, was die Seite selbst erzeugte (Blob, data-URI, sogar eine
    // vom Service Worker erfundene Antwort), war für Safari ein Download.
    //
    // Bewusst OHNE download-Attribut: das würde Safari das Übergeben an
    // den Kalender wieder verbieten. Der Pfad ist relativ - Liste und
    // Karte liegen im selben Ordner wie kalender/.
    box.querySelector('.cal-ics').href = `kalender/${icsFileName(e)}`;
    const noteEl = box.querySelector('.cal-note');
    if (noteEl) noteEl.textContent = ctx.t(istAppleGeraet() ? 'cal_note_apple' : 'cal_note');

    btn.addEventListener('click', (ev) => {
      ev.stopPropagation();
      const offen = !menu.hidden;
      menu.hidden = offen;
      btn.setAttribute('aria-expanded', offen ? 'false' : 'true');
    });
    menu.addEventListener('click', () => schliesseKalenderMenu(box));

    // Klick daneben oder Escape schließt das Menü - EIN Zuhörer für alle
    // Boxen der Seite, nur einmal angemeldet (render() baut die Box bei
    // jedem Klick neu, sonst sammelten sich die Zuhörer an).
    if (!setupCalendarBox.listenersAttached) {
      setupCalendarBox.listenersAttached = true;
      document.addEventListener('click', (ev) => {
        document.querySelectorAll('.detail-panel').forEach((b) => {
          const m = b.querySelector('.cal-menu');
          if (!m || m.hidden) return;
          if (m.contains(ev.target) || b.querySelector('.cal-open-btn').contains(ev.target)) return;
          schliesseKalenderMenu(b);
        });
      });
      document.addEventListener('keydown', (ev) => {
        if (ev.key !== 'Escape') return;
        document.querySelectorAll('.detail-panel').forEach(schliesseKalenderMenu);
      });
    }
  }

  // ---------- Die Box ----------

  // ---------- Sportart-Icons ----------
  //
  // Ein Strich-Icon je Sportart, in der Tabelle vor der Sportart und
  // im Abzeichen der Box (Vorlage des Nutzers, 21.09.2026). Inline-SVG
  // statt Bilddateien: kein weiterer Abruf, färbbar über currentColor,
  // und die Liste zeichnet 200 Zeilen als EINEN String - ein <img> je
  // Zeile wäre ein Abruf je Zeile.
  const SPORT_SVG = {
    Laufen: '<circle cx="15" cy="4.5" r="2"/><path d="M9.5 20.5l2.5-5 3 2.5 1-4M6.5 19l3-5.5L8 11l2.5-3.5 4 1.5 1.5 3 3 1"/>',
    Schwimmen: '<circle cx="16.5" cy="6" r="2"/><path d="M4 12l3.5-2.5 3 2.5 3-2.5 2 1.5"/><path d="M2 18c1.7 1.3 3.3 1.3 5 0s3.3-1.3 5 0 3.3 1.3 5 0 3.3-1.3 5 0"/><path d="M8 12l1-4.5 4-1 2 3"/>',
    Fahrrad: '<circle cx="5.5" cy="17" r="3.5"/><circle cx="18.5" cy="17" r="3.5"/><path d="M5.5 17l4.5-9h3l4.5 9M10 8h3.5M13.5 8l2.5 4"/>',
    Triathlon: '<circle cx="12" cy="4" r="1.8"/><path d="M12 6v5l-3 4M12 11l3 4M5 20h14M8 17.5l-1.5 2.5M16 17.5l1.5 2.5"/>'
  };
  // Die CSS-Klasse der Sportart (sport-laufen …): färbt das Abzeichen der
  // Box, die Marker-Nadeln und die Legende der Karte über die Variablen
  // --sport-<art> aus site.css. Unbekannte Sportart -> Laufen.
  const SPORT_KLASSE = { Laufen: 'laufen', Schwimmen: 'schwimmen', Fahrrad: 'fahrrad', Triathlon: 'triathlon' };
  function sportClass(art1) {
    return 'sport-' + (SPORT_KLASSE[art1] || 'laufen');
  }

  function sportIcon(art1, size) {
    const pfad = SPORT_SVG[art1] || SPORT_SVG.Laufen;
    const px = size || 16;
    return `<svg class="sport-icon" viewBox="0 0 24 24" width="${px}" height="${px}" fill="none"`
      + ' stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'
      + ` aria-hidden="true">${pfad}</svg>`;
  }

  const FACT_SVG = {
    ort: '<path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
    strecke: '<path d="M4 17c3-6 5-6 8 0s5 6 8 0"/><circle cx="4" cy="17" r="1.5"/><circle cx="20" cy="17" r="1.5"/>',
    kategorie: '<path d="M20 12l-8 8-9-9V4h7l10 8z"/><circle cx="7.5" cy="7.5" r="1.3"/>',
    veranstalter: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    entfernung: '<circle cx="12" cy="12" r="9"/><path d="M15.5 8.5l-2.2 5.3-5.3 2.2 2.2-5.3z"/>'
  };
  function factIcon(key) {
    return `<span class="fact-icon" aria-hidden="true"><svg viewBox="0 0 24 24" width="16" height="16" fill="none"`
      + ' stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
      + `${FACT_SVG[key]}</svg></span>`;
  }
  const MAP_SVG = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"'
    + ' stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    + '<path d="M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2z"/><path d="M9 4v14M15 6v14"/></svg>';
  const LIST_SVG = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"'
    + ' stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    + '<path d="M4 6h16M4 12h16M4 18h16"/></svg>';
  const EXT_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor"'
    + ' stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    + '<path d="M14 4h6v6M20 4l-9 9"/><path d="M19 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h6"/></svg>';
  const CARET_SVG = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor"'
    + ' stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>';

  // Der Veranstalter als Hostname ohne "www." - "kraichgaulauf.de"
  // statt der ganzen Adresse. Der Link selbst bleibt vollständig.
  function hostVon(url) {
    try { return new URL(url).hostname.replace(/^www\./, ''); } catch (e) { return url; }
  }

  // Der Schlüssel einer VERANSTALTUNG: Name + Starttag + Ort, klein
  // geschrieben. Die Liste fasst damit ihre Zeilen zusammen, die Karte
  // setzt je Schlüssel EINEN Punkt (vom Nutzer am 21.09.2026 gewünscht:
  // "eine Veranstaltung soll auch immer ein Punkt sein auf der Karte"),
  // und die Box sucht damit ihre Strecken-Pillen (siblings). EIN
  // Schlüssel für alle drei - sonst zählte die Karte anders als die Liste.
  function groupKey(e) {
    return `${(e.name || '').toLowerCase()}|${e.datum_start}|${(e.standort || '').toLowerCase()}`;
  }

  // Die Spanne der Längen einer Veranstaltung ("5–42,2 km") für die
  // zusammengefasste Zeile der Liste und das Popup der Karte: Distanzen
  // haben Vorrang, sonst die Dauern der Zeitrennen (Datenregel 8). Ohne
  // Leerzeichen um den Gedankenstrich - die Spalte der Liste ist schmal,
  // "5 – 42,2 km" bräuchte dort zwei Zeilen.
  // Die Formate der Triathlon-Zeilen einer Veranstaltung, nach Länge
  // geordnet und ohne Doppelte ("Sprint & Kurz") - oder null, wenn die
  // Zeilen keine Triathlons sind oder eine Zeile mit Länge kein Format
  // hat (Swimrun): dann gilt die Kilometer-Spanne wie überall. Zeilen
  // ganz ohne Angabe werden übergangen, wie bei der Spanne auch.
  function triathlonFormate(rows) {
    if (!rows.length || !rows.every(e => e.art1 === 'Triathlon')) return null;
    const formate = [];
    for (const e of rows) {
      const f = triathlonFormat(e);
      if (!f) {
        if (e.laenge_km != null || e.dauer_h != null) return null;
        continue;
      }
      if (!formate.includes(f)) formate.push(f);
    }
    if (!formate.length) return null;
    return formate.sort((a, b) => TRIATHLON_FORMATE[a].rang - TRIATHLON_FORMATE[b].rang || a.localeCompare(b));
  }
  // "Sprint & Olympisch", "Sprint, Olympisch & Mitteldistanz (70.3)" - so
  // hat der Nutzer die Angabe für den Munich Triathlon vorgegeben
  // ("Sprint & Kurzdistanz").
  function verbindeNamen(namen) {
    if (namen.length <= 1) return namen[0] || '–';
    return `${namen.slice(0, -1).join(', ')} & ${namen[namen.length - 1]}`;
  }

  function formatLengthSpan(rows, lang) {
    const formate = triathlonFormate(rows);
    if (formate) return verbindeNamen(formate.map(f => formatName(f, lang, rows[0])));
    const km = [];
    const stunden = [];
    rows.forEach(e => {
      if (e.laenge_km != null && !Number.isNaN(Number(e.laenge_km))) km.push(Number(e.laenge_km));
      else if (e.dauer_h != null && !Number.isNaN(Number(e.dauer_h))) stunden.push(Number(e.dauer_h));
    });
    const werte = km.length ? km : stunden;
    if (!werte.length) return '–';
    const einheit = km.length ? 'km' : 'h';
    const zahl = (v) => EF.formatNumber(v, lang, 1);
    const von = zahl(Math.min.apply(null, werte));
    const bis = zahl(Math.max.apply(null, werte));
    return von === bis ? `${von} ${einheit}` : `${von}–${bis} ${einheit}`;
  }

  // Die Strecken einer Veranstaltung als Pillen: nach Länge sortiert,
  // Zeitrennen dahinter, die gewählte hervorgehoben.
  function streckenPillen(e, ctx) {
    const geschwister = (ctx.siblings || []).slice();
    if (geschwister.length < 2) return '';
    const wert = x => x.e.laenge_km != null ? [0, Number(x.e.laenge_km)]
                    : x.e.dauer_h != null ? [1, Number(x.e.dauer_h)] : [2, 0];
    geschwister.sort((a, b) => { const va = wert(a), vb = wert(b); return va[0] - vb[0] || va[1] - vb[1]; });
    const t = ctx.t;
    // Zwei Strecken mit demselben Format (Jedermann 500/20/5 und Sprint
    // 750/20/5 sind beide "Sprint") bekommen die Kilometer dazu - sonst
    // stünden zwei gleiche Pillen nebeneinander.
    const namen = geschwister.map(x => formatLength(x.e, ctx.lang));
    const doppelt = new Set(namen.filter((n, i) => namen.indexOf(n) !== i));
    return `<div class="detail-section-title">${escapeHtml(t('detail_strecken_titel'))}</div>`
      + '<div class="detail-strecken" role="group">'
      + geschwister.map((x, i) => {
          const aktiv = x.e === e;
          const wb = displayWettbewerb(x.e);
          const beschriftung = doppelt.has(namen[i]) ? formatLength(x.e, ctx.lang, { mitKm: true }) : namen[i];
          return `<button type="button" class="strecke-pill${aktiv ? ' active' : ''}" data-idx="${x.idx}"`
            + `${aktiv ? ' aria-pressed="true"' : ''}${wb ? ` title="${escapeHtml(wb)}"` : ''}>${escapeHtml(beschriftung)}</button>`;
        }).join('')
      + '</div>';
  }

  const SHARE_SVG = '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor"'
    + ' stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    + '<path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7"/>'
    + '<path d="M16 6l-4-4-4 4"/><path d="M12 2v13"/></svg>';
  const CAL_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor"'
    + ' stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    + '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 11h18"/></svg>';

  function renderEmpty(container, ctx) {
    container.innerHTML = `<div class="detail-empty">${escapeHtml(ctx.t('detail_empty'))}</div>`;
  }

  // ctx: { t, tv, lang, onReport?, onClose?, siblings?, onSelect?, mapLink?,
  //        listLink?, distanceText? }.
  // Gibt nichts zurück; die Knöpfe hängen an der Box selbst.
  //
  // Aufbau seit dem 21.09.2026 (Vorlage des Nutzers): das Datum groß
  // und zuerst, darunter "in 6 Tagen"; ein Abzeichen mit Sportart und
  // Kategorie; der Name; die STRECKEN der Veranstaltung als Pillen (nur
  // wenn es mehrere gibt - `siblings` sind die Zeilen derselben
  // Veranstaltung, `onSelect(idx)` wechselt); vier Fakten mit Symbol
  // (Ort, Strecke, Kategorie, Veranstalter); dann die Knöpfe, klar
  // gestuft: die Veranstalterseite als Hauptknopf, Kalender und Karte
  // daneben, "Fehler melden" als leiser Link. `mapLink` (Liste) ist die
  // Adresse der Karte mit diesem Event, `listLink` (Karte) die der Liste
  // mit diesem Event - je Seite gibt es nur den Knopf zur ANDEREN.
  // `distanceText` ("14 km") ersetzt den vierten Fakt (Veranstalter)
  // durch die Entfernung vom Ausgangspunkt (Vorlage der Karte); die
  // Veranstalterseite bleibt als Hauptknopf darunter.
  function render(container, e, ctx) {
    const { t, tv, lang } = ctx;
    const wb = displayWettbewerb(e);
    // Vorläufiger Termin: nur Monat und Jahr mit Sternchen, darunter
    // statt "in 6 Tagen" der Hinweis, dass der Tag nicht veröffentlicht ist.
    const relativ = e.datum_vorlaeufig ? t('detail_vorlaeufig') : EF.relativeDays(e.datum_start, lang);
    const mehrtaegig = e.datum_ende && e.datum_ende !== e.datum_start;
    const datumGross = e.datum_vorlaeufig
      ? escapeHtml(EF.formatMonthYear(e.datum_start, lang)) + '*'
      : mehrtaegig
        ? `${escapeHtml(EF.formatDateLong(e.datum_start, lang))} –<br>${escapeHtml(EF.formatDateLong(e.datum_ende, lang))}`
        : escapeHtml(EF.formatDateLong(e.datum_start, lang));
    const kategorie = `${tv('art1', e.art1)}${e.art2 ? ' · ' + tv('art2', e.art2) : ''}`;
    const strecke = `${formatLength(e, lang)}${wb ? ' · ' + wb : ''}`;
    container.innerHTML = `
      <div class="detail-head">
        <div class="detail-head-text">
          <div class="detail-date">${datumGross}</div>
          ${relativ ? `<div class="detail-relative">${escapeHtml(relativ)}</div>` : ''}
        </div>
        <button type="button" class="detail-share event-share-btn"
                title="${escapeHtml(t('share_event'))}" aria-label="${escapeHtml(t('share_event'))}">${SHARE_SVG}</button>
        ${ctx.onClose ? `<button type="button" class="detail-share detail-close"
                title="${escapeHtml(t('detail_close'))}" aria-label="${escapeHtml(t('detail_close'))}">&#10005;</button>` : ''}
      </div>
      <div class="detail-badge ${sportClass(e.art1)}">${sportIcon(e.art1, 15)}<span>${escapeHtml(kategorie)}</span></div>
      <h2>${escapeHtml(e.name)}</h2>
      ${streckenPillen(e, ctx)}
      <dl class="detail-grid">
        <div class="fact">${factIcon('ort')}<div><dt>${escapeHtml(t('detail_ort'))}</dt><dd>${escapeHtml(tv('standort', e.standort))},<br>${escapeHtml(tv('land', e.land))}</dd></div></div>
        <div class="fact">${factIcon('strecke')}<div><dt>${escapeHtml(t('detail_strecke'))}</dt><dd>${escapeHtml(strecke)}</dd></div></div>
        <div class="fact">${factIcon('kategorie')}<div><dt>${escapeHtml(t('detail_kategorie'))}</dt><dd>${escapeHtml(kategorie)}</dd></div></div>
        ${ctx.distanceText
          ? `<div class="fact">${factIcon('entfernung')}<div><dt>${escapeHtml(t('detail_entfernung'))}</dt><dd>${escapeHtml(t('detail_entfernung_von', ctx.distanceText))}</dd></div></div>`
          : `<div class="fact">${factIcon('veranstalter')}<div><dt>${escapeHtml(t('detail_veranstalter'))}</dt><dd>${e.veranstalter_url
            ? `<a class="detail-host" href="${escapeHtml(e.veranstalter_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(hostVon(e.veranstalter_url))}</a>`
            : '–'}</dd></div></div>`}
      </dl>
      ${e.veranstalter_url ? `<a class="detail-link" href="${escapeHtml(e.veranstalter_url)}" target="_blank" rel="noopener noreferrer"><span>${escapeHtml(t('detail_link'))}</span>${EXT_SVG}</a>` : ''}
      <div class="detail-actions">
        <div class="cal-box">
          <button type="button" class="cal-btn cal-open-btn" aria-expanded="false">
            ${CAL_SVG}<span>${escapeHtml(t('cal_btn'))}</span>${CARET_SVG}
          </button>
          <div class="cal-menu" hidden>
            <a class="cal-google" target="_blank" rel="noopener noreferrer">${escapeHtml(t('cal_google'))}</a>
            <a class="cal-outlook" target="_blank" rel="noopener noreferrer">${escapeHtml(t('cal_outlook'))}</a>
            <a class="cal-ics">${escapeHtml(t('cal_ics'))}</a>
            <div class="cal-note"></div>
          </div>
        </div>
        ${ctx.mapLink ? `<a class="cal-btn detail-map-btn" href="${escapeHtml(ctx.mapLink)}">${MAP_SVG}<span>${escapeHtml(t('detail_map'))}</span></a>` : ''}
        ${ctx.listLink ? `<a class="cal-btn detail-list-btn" href="${escapeHtml(ctx.listLink)}">${LIST_SVG}<span>${escapeHtml(t('detail_list'))}</span></a>` : ''}
      </div>
      ${ctx.onReport ? `<button type="button" class="report-btn report-open-btn">${escapeHtml(t('report_btn'))}</button>` : ''}
    `;
    container.querySelector('.event-share-btn').addEventListener('click', () => teileEvent(e, ctx));
    if (ctx.onReport) {
      container.querySelector('.report-open-btn').addEventListener('click', () => ctx.onReport(e));
    }
    if (ctx.onClose) {
      container.querySelector('.detail-close').addEventListener('click', () => ctx.onClose(e));
    }
    if (ctx.onSelect) {
      container.querySelectorAll('.strecke-pill').forEach(btn => {
        btn.addEventListener('click', () => ctx.onSelect(Number(btn.dataset.idx)));
      });
    }
    setupCalendarBox(container, e, ctx);
  }

  global.EnduranceDetail = {
    I18N,
    render,
    renderEmpty,
    displayWettbewerb,
    formatRange,
    formatRangeHtml,
    formatEventRangeHtml,
    formatLength,
    triathlonFormat,
    eventSlug,
    icsFileName,
    icsMasszahl,
    eventLink,
    eventShareText,
    teileEvent,
    showToast,
    kopiereInAblage,
    sportIcon,
    sportClass,
    hostVon,
    groupKey,
    formatLengthSpan
  };
})(typeof window !== 'undefined' ? window : globalThis);

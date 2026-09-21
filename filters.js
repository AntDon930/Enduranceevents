// Gemeinsamer Filterzustand von events.html und karte.html.
//
// Die Liste und die Karte zeigen dieselben Daten unter denselben Filtern -
// vorher stand die ganze Logik (Distanzkategorien, Umkreis, Deep-Link,
// Filter-Chips) NUR im Inline-Skript von events.html, und die Karte kannte
// gar keine Filter. Ein zweiter Nachbau in karte.html wäre auf Dauer
// auseinandergelaufen (eine Kategorie hier geändert, dort vergessen), also
// steht alles Gemeinsame jetzt genau einmal hier.
//
// Was hier NICHT hingehört: alles, was nur die Liste betrifft (Sortierung,
// Zusammenfassen, Spalten, Filter-Panels) - das bleibt in events.html.
(function (global) {
  'use strict';

  // Texte, die BEIDE Seiten brauchen: die Filter-Chips und die
  // Zeitraum-Knöpfe. Jede Seite mischt sie in ihr eigenes I18N-Objekt
  // (Object.assign), damit t() unverändert funktioniert.
  const I18N = {
    de: {
      chip_datum: (n) => `Datum: ${n} Tag${n === 1 ? '' : 'e'} ausgewählt`,
      chip_value_all: 'Alle',
      chip_value_count: (n) => `${n} ausgewählt`,
      chip_value_days: (n) => `${n} Tag${n === 1 ? '' : 'e'} ausgewählt`,
      chip_datum_all: 'Datum: Alle',
      chip_datum_preset: (label) => `Datum: ${label}`,
      chip_datum_wert: (v) => `Datum: ${v}`,
      chip_ab_km: (v) => `ab ${v} km`,
      chip_bis_km: (v) => `bis ${v} km`,
      chip_umkreis_wert: (km, label) => `${km} km um ${label}`,
      preset_weekend: 'Dieses Wochenende',
      preset_d30: 'Nächste 30 Tage',
      preset_m3: 'Nächste 3 Monate',
      preset_year: 'Dieses Jahr',
      chip_distanz_count: (n) => `Länge: ${n} ausgewählt`,
      chip_suche: (q) => `Suche: „${q}"`,
      chip_name: (q) => `Name: „${q}"`,
      chip_sportart: (v) => `Sportart: ${v}`,
      chip_standort: (v) => `Ort: ${v}`,
      chip_land: (v) => `Land: ${v}`,
      chip_kategorie: (v) => `Kategorie: ${v}`,
      chip_laenge_ab: (v) => `Länge ab ${v} km`,
      chip_laenge_bis: (v) => `Länge bis ${v} km`,
      chip_umkreis: (km, label) => `Umkreis: ${km} km um ${label}`,
      chip_distanz: (sport, cat) => `Länge: ${cat} (${sport})`
    },
    en: {
      chip_datum: (n) => `Date: ${n} day${n === 1 ? '' : 's'} selected`,
      chip_value_all: 'All',
      chip_value_count: (n) => `${n} selected`,
      chip_value_days: (n) => `${n} day${n === 1 ? '' : 's'} selected`,
      chip_datum_all: 'Date: All',
      chip_datum_preset: (label) => `Date: ${label}`,
      chip_datum_wert: (v) => `Date: ${v}`,
      chip_ab_km: (v) => `from ${v} km`,
      chip_bis_km: (v) => `up to ${v} km`,
      chip_umkreis_wert: (km, label) => `${km} km around ${label}`,
      preset_weekend: 'This weekend',
      preset_d30: 'Next 30 days',
      preset_m3: 'Next 3 months',
      preset_year: 'This year',
      chip_distanz_count: (n) => `Length: ${n} selected`,
      chip_suche: (q) => `Search: "${q}"`,
      chip_name: (q) => `Name: "${q}"`,
      chip_sportart: (v) => `Sport: ${v}`,
      chip_standort: (v) => `Place: ${v}`,
      chip_land: (v) => `Country: ${v}`,
      chip_kategorie: (v) => `Category: ${v}`,
      chip_laenge_ab: (v) => `Length from ${v} km`,
      chip_laenge_bis: (v) => `Length up to ${v} km`,
      chip_umkreis: (km, label) => `Radius: ${km} km around ${label}`,
      chip_distanz: (sport, cat) => `Length: ${cat} (${sport})`
    }
  };

  // Übersetzung der Datenwerte (Land/Sportart/Kategorie). Die gespeicherten
  // Filterwerte bleiben intern immer auf Deutsch (Datenformat) - hier wird
  // nur die ANZEIGE übersetzt.
  const VALUE_TRANSLATIONS = {
    land: {
      'Deutschland': { de: 'Deutschland', en: 'Germany' },
      'Österreich': { de: 'Österreich', en: 'Austria' },
      'Schweiz': { de: 'Schweiz', en: 'Switzerland' },
      'Italien (Südtirol)': { de: 'Italien (Südtirol)', en: 'Italy (South Tyrol)' }
    },
    art1: {
      'Laufen': { de: 'Laufen', en: 'Running' },
      'Schwimmen': { de: 'Schwimmen', en: 'Swimming' },
      'Fahrrad': { de: 'Fahrrad', en: 'Cycling' },
      'Triathlon': { de: 'Triathlon', en: 'Triathlon' }
    },
    art2: {
      'Straße': { de: 'Straße', en: 'Road' },
      // Trail, Cross und Berglauf sind EIN Wert: alles Geländelauf, die
      // Quellen benennen dieselbe Strecke mal so, mal so (Wunsch des
      // Nutzers, seit 19.09.2026 nur noch "Trail"). Die alten Werte
      // bleiben übersetzbar - ein geteilter Link von früher
      // (?art2=Trail/Cross, ?art2=Berg) soll keinen rohen Schlüssel
      // anzeigen. "Cross" braucht der Triathlon weiterhin.
      'Trail': { de: 'Trail', en: 'Trail' },
      'Trail/Cross': { de: 'Trail', en: 'Trail' },
      'Berg': { de: 'Trail', en: 'Trail' },
      'Bahn': { de: 'Bahn', en: 'Track' },
      'Cross': { de: 'Cross', en: 'Cross Country' },
      'Hindernis': { de: 'Hindernis', en: 'Obstacle' },
      // Englischer Fachbegriff, in beiden Sprachen gleich: das
      // Last-Man-Standing-Format (gleiche Runde zur gleichen Stunde, bis
      // nur eine Person übrig ist) - beim Laufen UND beim Triathlon
      // derselbe Wert. Die alten Schlüssel bleiben für geteilte Links.
      'Backyard Ultra': { de: 'Backyard Ultra', en: 'Backyard Ultra' },
      'Backcountry Ultra': { de: 'Backyard Ultra', en: 'Backyard Ultra' },
      'Backyard': { de: 'Backyard Ultra', en: 'Backyard Ultra' },
      // Der Zweck als Kategorie (Laufen, Schwimmen, Fahrrad) - in beiden
      // Sprachen dasselbe Wort.
      'Charity': { de: 'Charity', en: 'Charity' },
      'Freiwasser': { de: 'Freiwasser', en: 'Open Water' },
      'Becken': { de: 'Becken', en: 'Pool' },
      'Zeitfahren': { de: 'Zeitfahren', en: 'Time Trial' },
      'Mountainbike': { de: 'Mountainbike', en: 'Mountain Bike' },
      'Gravel': { de: 'Gravel', en: 'Gravel' },
      'Cyclecross': { de: 'Cyclecross', en: 'Cyclocross' },
      // Mehrsport (art1 "Triathlon"): die Form des Wettkampfs. Alle vier
      // Begriffe sind international dieselben; "Indoor" heißt der
      // Hallen-Triathlon (Becken, Ergometer, Laufband).
      'Duathlon': { de: 'Duathlon', en: 'Duathlon' },
      'Aquathlon': { de: 'Aquathlon', en: 'Aquathlon' },
      'Swimrun': { de: 'Swimrun', en: 'Swimrun' },
      'Quadrathlon': { de: 'Quadrathlon', en: 'Quadrathlon' },
      'Indoor': { de: 'Indoor', en: 'Indoor' }
    },
    // Städte mit einem eigenen englischen Namen. Nur ECHTE Exonyme -
    // Orte, die im Englischen anders heißen, nicht bloß anders
    // geschrieben werden: „Munich" gehört hierher, „Wurzburg" (nur ohne
    // Umlaut) nicht. Wer in der englischen Fassung „Munich" sucht oder
    // liest, soll München finden; alle anderen der ~1.500 Orte stehen in
    // beiden Sprachen gleich da (tv() gibt den Wert dann unverändert
    // zurück).
    //
    // Die Liste gilt AUCH für die Suche: `matchEvent` schaut in beide
    // Sprachen, damit „Munich" auch auf der deutschen Seite trifft
    // (siehe unten). Wird hier ein Ort ergänzt, muss die Kopie in
    // functions/index.js mit - `test_suche_uebersetzungen` vergleicht
    // beide.
    standort: {
      'München': { de: 'München', en: 'Munich' },
      'Köln': { de: 'Köln', en: 'Cologne' },
      'Nürnberg': { de: 'Nürnberg', en: 'Nuremberg' },
      'Hannover': { de: 'Hannover', en: 'Hanover' },
      'Braunschweig': { de: 'Braunschweig', en: 'Brunswick' },
      'Konstanz': { de: 'Konstanz', en: 'Constance' },
      'Wien': { de: 'Wien', en: 'Vienna' },
      'Zürich': { de: 'Zürich', en: 'Zurich' },
      'Genf': { de: 'Genf', en: 'Geneva' },
      'Luzern': { de: 'Luzern', en: 'Lucerne' },
      'Basel': { de: 'Basel', en: 'Basel' }
    }
  };

  // Die drei Länder, die die Daten überhaupt enthalten. Gebraucht als
  // Prüfung beim Lesen der Adresse (?land=…).
  // Südtirol (Provinz Bozen) seit dem 21.09.2026 als vierte Region - im
  // Filter "Italien (Südtirol)", damit niemand ganz Italien erwartet.
  const LAENDER = ['Deutschland', 'Österreich', 'Schweiz', 'Italien (Südtirol)'];

  // ---------- Distanzkategorien (nach Sportart) ----------

  // "Rundet nach oben": z. B. ein 4-km-Lauf erscheint unter der 5-km-Kategorie.
  // Halbmarathon/Marathon sind nur die offiziellen Distanzen (mit kleiner Toleranz
  // für Rundungsunterschiede in den Daten), Ultramarathon ist alles darüber.
  const DISTANCE_CATEGORIES = {
    'Laufen': [
      { key: '5k', test: km => km > 0 && km <= 5 },
      { key: '10k', test: km => km > 5 && km <= 10 },
      { key: 'half', test: km => Math.abs(km - 21.0975) <= 0.5 },
      { key: 'marathon', test: km => Math.abs(km - 42.195) <= 0.5 },
      { key: 'ultra', test: km => km > 42.195 + 0.5 },
      // Zeitlich begrenzte Rennen haben keine Distanz, auf die sich ein
      // Test anwenden ließe - `zeit: true` trifft jedes Event mit
      // gesetztem dauer_h (siehe matchesDistanceCategory).
      { key: 'zeit', zeit: true }
    ],
    'Fahrrad': [
      { key: 'r50', test: km => km > 0 && km <= 50 },
      { key: 'r100', test: km => km > 50 && km <= 100 },
      { key: 'r150', test: km => km > 100 && km <= 150 },
      { key: 'r200', test: km => km > 150 && km <= 200 },
      { key: 'rultra', test: km => km > 200 },
      { key: 'zeit', zeit: true }
    ],
    'Schwimmen': [
      { key: 's1', test: km => km > 0 && km <= 1 },
      { key: 's2', test: km => km > 1 && km <= 2 },
      { key: 's3', test: km => km > 2 && km <= 3 },
      { key: 's5', test: km => km > 3 && km <= 5 },
      { key: 's10', test: km => km > 5 },
      { key: 'zeit', zeit: true }
    ],
    // Triathlon: Grenzen ZWISCHEN den Formaten, keine Toleranzen um die
    // Normdistanzen (25,75 / 51,5 / 113 / 226 km) herum - deutsche
    // Veranstaltungen weichen ab (Moritzburgs Langdistanz hat 218,8 km,
    // ein Cross-Triathlon 41,5 km) und fielen sonst in keine Kategorie.
    // Die Grenzen sind die Rückfallebene von triathlonFormat() (unten);
    // matchesDistanceCategory prüft beim Triathlon das FORMAT, das die
    // Spalte anzeigt - Label und Schwimmteil können es verschieben. Die sechs
    // Kategorien sind die Vorgabe des Nutzers (Bild vom 21.09.2026):
    // Super-Sprint, Sprint, Olympisch, Mitteldistanz (70.3), Langstrecke
    // (140.6), Ultra-Triathlon. Kopie in functions/index.js. Der Schlüssel
    // 'tultra' statt 'ultra', weil 'ultra' schon der Ultramarathon ist
    // (die Beschriftungen hängen am Schlüssel).
    'Triathlon': [
      { key: 'supersprint', test: km => km > 0 && km < 23 },
      { key: 'sprint', test: km => km >= 23 && km < 40 },
      { key: 'olympic', test: km => km >= 40 && km < 80 },
      { key: 'middle', test: km => km >= 80 && km < 160 },
      { key: 'long', test: km => km >= 160 && km < 230 },
      { key: 'tultra', test: km => km >= 230 },
      { key: 'zeit', zeit: true }
    ]
  };

  const DISTANCE_CATEGORY_LABELS = {
    de: {
      '5k': '5 km', '10k': '10 km', 'half': 'Halbmarathon', 'marathon': 'Marathon', 'ultra': 'Ultramarathon',
      'r50': 'bis 50 km', 'r100': '50–100 km', 'r150': '100–150 km', 'r200': '150–200 km', 'rultra': '200+ km',
      's1': '1 km', 's2': '2 km', 's3': '3 km', 's5': '5 km', 's10': '10+ km (Marathonschwimmen)',
      // "70.3" ist der Markenname (Ironman 70.3) und bleibt mit Punkt;
      // die echten Distanzangaben tragen das deutsche Komma.
      'supersprint': 'Super-Sprint', 'sprint': 'Sprint', 'olympic': 'Olympisch',
      'middle': 'Mitteldistanz (70.3)', 'long': 'Langstrecke (140.6)', 'tultra': 'Ultra-Triathlon',
      'zeit': 'Zeitrennen (6 h, 12 h, 24 h …)'
    },
    en: {
      '5k': '5 km', '10k': '10 km', 'half': 'Half Marathon', 'marathon': 'Marathon', 'ultra': 'Ultramarathon',
      'r50': 'up to 50 km', 'r100': '50–100 km', 'r150': '100–150 km', 'r200': '150–200 km', 'rultra': '200+ km',
      's1': '1 km', 's2': '2 km', 's3': '3 km', 's5': '5 km', 's10': '10+ km (marathon swim)',
      'supersprint': 'Super sprint', 'sprint': 'Sprint', 'olympic': 'Olympic',
      'middle': 'Middle distance (70.3)', 'long': 'Long distance (140.6)', 'tultra': 'Ultra triathlon',
      'zeit': 'Timed race (6 h, 12 h, 24 h …)'
    }
  };

  // Grenzen des Umkreis-Reglers. Früher gab es vier feste Stufen
  // (0-5, 5-20, 20-50, 50+ km) - ein Regler trifft genauer, was jemand
  // sucht ("alles im Umkreis von 40 km"), und braucht weniger Platz.
  const RADIUS_MIN_KM = 1;
  const RADIUS_MAX_KM = 200;
  // Voreinstellung, sobald ein Ausgangspunkt feststeht: ohne Umkreis
  // hätte der Ausgangspunkt gar keine Wirkung.
  const RADIUS_DEFAULT_KM = 25;

  // Ab wie vielen ausgewählten Werten ein Mengen-Filter zu EINEM Chip
  // zusammengefasst wird (siehe buildChips). Fünf Chips sind noch lesbar,
  // fünfzig nicht mehr.
  const MAX_VALUE_CHIPS = 5;

  // Bewusste Grenze für ?tage=…: eine Auswahl von Hunderten Tagen würde
  // die Adresse unbrauchbar lang machen. Die vier Zeitraum-Knöpfe decken
  // genau diese großen Bereiche ab und stehen als 'zeitraum' drin.
  const URL_MAX_DAYS = 60;

  // Drei kleine Helfer, die Liste, Karte und Filter-Panels alle drei
  // brauchen. Die Sprache kommt als Parameter: das Modul kennt den
  // Umschalter der Seite nicht.
  function escapeHtml(str) {
    // null/undefined als leerer Text: an vielen Stellen wird ein Feld
    // eingesetzt, das fehlen darf - "null" im Markup wäre schlimmer.
    if (str == null) return '';
    return String(str).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function uniqueSorted(values, lang) {
    return Array.from(new Set(values.filter(v => v !== undefined && v !== null && v !== '')))
      .sort((a, b) => String(a).localeCompare(String(b), lang === 'en' ? 'en' : 'de'));
  }

  function formatDate(iso, lang) {
    if (!iso) return '';
    const [y, m, d] = iso.split('-').map(Number);
    if (lang === 'en') {
      const date = new Date(Date.UTC(y, m - 1, d));
      return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' });
    }
    return `${String(d).padStart(2, '0')}.${String(m).padStart(2, '0')}.${y}`;
  }

  // Wochentag und Monatsnamen für die Anzeige (Tabelle und Detail-Box,
  // seit dem Umbau vom 21.09.2026 nach der Vorlage des Nutzers: "So
  // 27.09.2026" in der Tabelle, "So, 27. Sep. 2026" groß in der Box).
  // Eigene Listen statt toLocaleDateString: Das hängt an der
  // Spracheinstellung des Browsers, nicht am Umschalter DE/EN der Seite
  // - dieselbe Begründung wie bei formatNumber.
  const WOCHENTAGE = {
    de: ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'],
    en: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
  };
  const MONATE_KURZ = {
    de: ['Jan.', 'Feb.', 'März', 'Apr.', 'Mai', 'Juni', 'Juli', 'Aug.', 'Sep.', 'Okt.', 'Nov.', 'Dez.'],
    en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  };
  function wochentagVon(iso, lang) {
    const [y, m, d] = iso.split('-').map(Number);
    const wt = new Date(Date.UTC(y, m - 1, d)).getUTCDay();
    return (WOCHENTAGE[lang] || WOCHENTAGE.de)[wt];
  }
  // "So 27.09.2026" / "Sun 27 Sep 2026" - die Tabelle.
  function formatDateWeekday(iso, lang, komma) {
    if (!iso) return '';
    return `${wochentagVon(iso, lang)}${komma ? ',' : ''} ${formatDate(iso, lang)}`;
  }
  // "So, 27. Sep. 2026" / "Sun, 27 Sep 2026" - die Detail-Box.
  function formatDateLong(iso, lang) {
    if (!iso) return '';
    const [y, m, d] = iso.split('-').map(Number);
    const monat = (MONATE_KURZ[lang] || MONATE_KURZ.de)[m - 1];
    return lang === 'en'
      ? `${wochentagVon(iso, lang)}, ${d} ${monat} ${y}`
      : `${wochentagVon(iso, lang)}, ${d}. ${monat} ${y}`;
  }
  // Ein Zeitraum, knapp: "26.09.–26.12.2026" (gleiches Jahr nur einmal),
  // "26 Sep – 26 Dec 2026". Für die Datum-Pille und den Datum-Chip.
  function formatDateRangeShort(a, b, lang) {
    if (!a) return '';
    if (!b || a === b) return formatDate(a, lang);
    const [ya, ma, da] = a.split('-').map(Number);
    const [yb] = b.split('-').map(Number);
    if (lang === 'en') {
      const mon = MONATE_KURZ.en;
      const [, mb, db] = b.split('-').map(Number);
      return ya === yb
        ? `${da} ${mon[ma - 1]} – ${db} ${mon[mb - 1]} ${yb}`
        : `${formatDate(a, lang)} – ${formatDate(b, lang)}`;
    }
    const kurz = `${String(da).padStart(2, '0')}.${String(ma).padStart(2, '0')}.`;
    return ya === yb ? `${kurz}–${formatDate(b, lang)}` : `${formatDate(a, lang)}–${formatDate(b, lang)}`;
  }
  // Ganze Zahlen mit Tausendertrennzeichen: "1.889" / "1,889".
  function formatInt(n, lang) {
    const s = String(Math.round(Number(n) || 0));
    const mitPunkt = s.replace(/\B(?=(\d{3})+(?!\d))/g, lang === 'en' ? ',' : '.');
    return mitPunkt;
  }

  // Eine Entfernung in km: unter 10 km mit einer Nachkommastelle (dort
  // macht sie einen Unterschied), darüber gerundet - und immer mit dem
  // Trennzeichen der gewählten Sprache. Liste (Spalte und Box) und Karte
  // (Box: "14 km von deinem Standort") zeigen sie damit gleich.
  function formatDistanceKm(d, lang) {
    return d < 10 ? `${formatNumber(d, lang, 1)}km` : `${Math.round(d)}km`;
  }
  // "in 6 Tagen", "heute", "morgen", "in 3 Wochen", "in 5 Monaten" - die
  // Zeile unter dem großen Datum der Box. Leer für Vergangenes.
  function relativeDays(iso, lang, heute) {
    if (!iso) return '';
    const [y, m, d] = iso.split('-').map(Number);
    const ziel = Date.UTC(y, m - 1, d);
    const jetzt = heute ? Date.UTC(heute.getFullYear(), heute.getMonth(), heute.getDate())
                        : (() => { const n = new Date(); return Date.UTC(n.getFullYear(), n.getMonth(), n.getDate()); })();
    const tage = Math.round((ziel - jetzt) / 86400000);
    if (tage < 0) return '';
    const en = lang === 'en';
    if (tage === 0) return en ? 'today' : 'heute';
    if (tage === 1) return en ? 'tomorrow' : 'morgen';
    if (tage < 21) return en ? `in ${tage} days` : `in ${tage} Tagen`;
    if (tage < 90) { const w = Math.round(tage / 7); return en ? `in ${w} weeks` : `in ${w} Wochen`; }
    const mon = Math.round(tage / 30.4);
    if (mon < 24) return en ? `in ${mon} months` : `in ${mon} Monaten`;
    const j = Math.round(tage / 365);
    return en ? `in ${j} years` : `in ${j} Jahren`;
  }

  const MONATE_LANG = {
    de: ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'],
    en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
  };
  // "Juni 2027" - für vorläufige Termine (datum_vorlaeufig): Der Tag ist
  // eine Kalenderprognose, veröffentlicht ist nur, dass der Lauf in etwa
  // in diesem Monat stattfindet (vom Nutzer am 21.09.2026 entschieden:
  // "kein konkretes Datum, wenn noch kein genauer Tag genannt wurde").
  function formatMonthYear(iso, lang) {
    if (!iso) return '';
    const [y, m] = iso.split('-').map(Number);
    return `${(MONATE_LANG[lang] || MONATE_LANG.de)[m - 1]} ${y}`;
  }
  // Das Datum EINES Events als Text: vorläufig -> "Juni 2027*", sonst der
  // Tag bzw. der Zeitraum; opts.weekday / opts.long wie bei den
  // Einzelfunktionen. Das Sternchen verweist auf die Fußnote der Seite.
  function formatEventDate(e, lang, opts) {
    const o = opts || {};
    if (e.datum_vorlaeufig) return formatMonthYear(e.datum_start, lang) + '*';
    const f = o.long ? formatDateLong : o.weekday ? formatDateWeekday : formatDate;
    if (!e.datum_ende || e.datum_ende === e.datum_start) return f(e.datum_start, lang);
    return `${f(e.datum_start, lang)} – ${f(e.datum_ende, lang)}`;
  }

  // Dezimaltrennzeichen je Sprache: im Deutschen das Komma, im Englischen
  // der Punkt. Vorher stand in der Liste auch auf Deutsch "42.2 km" - für
  // deutsche Augen liest sich das wie eine Tausendertrennung. Alle Stellen,
  // die eine Zahl mit Nachkommastelle anzeigen, gehen durch diese Funktion;
  // deshalb steht sie hier und nicht in einer der Seiten.
  //
  // Bewusst KEIN toLocaleString(): Das hängt von der Spracheinstellung des
  // Browsers ab, nicht von der Sprache, die auf der Seite gewählt ist -
  // ein Deutscher mit englischem System hätte im deutschen Text Punkte
  // gesehen. Maßgeblich ist der Umschalter DE/EN.
  function formatNumber(value, lang, stellen) {
    const zahl = Number(value);
    if (value == null || Number.isNaN(zahl)) return '';
    const gerundet = stellen == null
      ? zahl
      : Math.round(zahl * Math.pow(10, stellen)) / Math.pow(10, stellen);
    const text = Number.isInteger(gerundet)
      ? String(gerundet)
      : gerundet.toFixed(stellen == null ? 1 : stellen);
    return lang === 'en' ? text : text.replace('.', ',');
  }

  // "42,2km" bzw. "42.2km". Ganze Zahlen ohne Nachkommastelle ("10km").
  //
  // OHNE Leerzeichen zwischen Zahl und Einheit - vom Nutzer am
  // 21.09.2026 so gewünscht ("16 km wird zu 16km zum Beispiel und 6 h zu
  // 6h"). Das gilt für die MASSZAHL eines Events: Länge-Spalte, Spanne
  // einer Veranstaltung, Strecken-Pillen, Entfernung, Detail-Box. Nicht
  // betroffen sind Sätze, in denen eine Zahl vorkommt ("Umkreis: 25 km",
  // "Länge ab 10 km", "bis 50 km" im Filter) - dort ist die Einheit ein
  // eigenes Wort im Satz, kein Etikett an einer Zahl.
  function formatKm(km, lang) {
    if (km == null || Number.isNaN(Number(km))) return '–';
    return `${formatNumber(km, lang, 1)}km`;
  }

  // "24h" bzw. "1,5h" - Zeitrennen haben keine Distanz (Datenregel 8).
  function formatHours(h, lang) {
    if (h == null || Number.isNaN(Number(h))) return '–';
    return `${formatNumber(h, lang, 1)}h`;
  }

  function isoOf(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }

  function todayIso() {
    return isoOf(new Date());
  }

  // Zeitraum-Schnellfilter. Der Jahr/Monat/Tag-Baum ist genau, aber für
  // "dieses Wochenende" oder "die nächsten drei Monate" muss man sich
  // durchklicken - diese vier Knöpfe kosten eine Zeile Platz und nehmen
  // den häufigsten Fällen die Arbeit ab. Sie setzen dieselben
  // state.selectedDays wie der Baum, es kommt also kein zweiter
  // Filtermechanismus dazu.
  const DATE_PRESETS = [
    { key: 'weekend', labelKey: 'preset_weekend', range: () => {
        // Kommendes Wochenende; ist heute schon Samstag oder Sonntag, ist
        // dieses Wochenende gemeint.
        const heute = new Date();
        const wt = heute.getDay();                 // 0 = So, 6 = Sa
        if (wt === 0) return [isoOf(heute), isoOf(heute)];
        const von = new Date(heute);
        von.setDate(heute.getDate() + (6 - wt));
        const bis = new Date(von);
        bis.setDate(von.getDate() + 1);
        return [isoOf(wt === 6 ? heute : von), isoOf(bis)];
      } },
    { key: 'd30', labelKey: 'preset_d30', range: () => {
        const heute = new Date(); const bis = new Date();
        bis.setDate(heute.getDate() + 30);
        return [isoOf(heute), isoOf(bis)];
      } },
    { key: 'm3', labelKey: 'preset_m3', range: () => {
        const heute = new Date(); const bis = new Date();
        bis.setMonth(heute.getMonth() + 3);
        return [isoOf(heute), isoOf(bis)];
      } },
    { key: 'year', labelKey: 'preset_year', range: () => {
        const heute = new Date();
        return [isoOf(heute), `${heute.getFullYear()}-12-31`];
      } }
  ];

  // Der reine Filterzustand - ohne Ansichtssachen (Sortierung,
  // Zusammenfassen), die nur die Liste kennt.
  function createState() {
    return {
      land: new Set(),
      art1: new Set(),
      art2: new Set(),
      standort: new Set(),
      // Die Mastersuche: EIN Feld über Eventname, Wettbewerb und Ort.
      // Bewusst getrennt von `nameQuery` (dem Textfeld der Spalte
      // "Name"): Die Spaltenfilter bleiben die genauen Werkzeuge, die
      // Mastersuche ist der schnelle Weg ("München", "Marathon").
      suche: '',
      nameQuery: '',
      selectedDays: new Set(),       // ausgewählte datum_start-Werte (aus dem Jahr/Monat/Tag-Baum)
      datePreset: null,              // 'weekend' | 'd30' | 'm3' | 'year' - nur fürs Etikett
      laengeMin: '',
      laengeMax: '',
      distanceCategories: new Set(), // "Sportart:kategorieKey", z. B. "Laufen:marathon"
      origin: null,                  // { lat, lon, label }
      radiusKm: null                 // Umkreis in km (1-200) oder null = kein Umkreis-Filter
    };
  }

  // ---------- Vorschläge für die Mastersuche ----------
  //
  // Wer "Iron" eintippt, soll "Ironman" angeboten bekommen (so vom
  // Nutzer gewünscht). Der Anlass war die Frage nach einer
  // VERANSTALTER-Spalte: Gemessen an den Daten lohnt die nicht - die
  // größte Serie hat 21 Veranstaltungen, nennenswert sind rund elf
  // (Wings for Life World Run 21, Ahmadiyya Charity Walk 18, Muddy
  // Angel Run 13, Rats-Run 9, Ironman 7, XLETIX 6, SportScheck RUN 6,
  // HYROX 5 …). Eine eigene Spalte kostete Platz, den die Liste auf
  // dem Laptop nicht hat; ein Vorschlag im Suchfeld kostet keinen.
  //
  // Die Vorschläge werden AUS DEN DATEN gerechnet, nicht aus einer
  // gepflegten Liste. Eine Markenliste im Code würde veralten, sobald
  // eine Serie dazukommt oder aufhört - und beim großen Datenlauf
  // kommen 16.000 Events dazu.
  //
  // Zwei Sorten Vorschlag, weil die Mastersuche über beides geht:
  //   SERIE - der Wortanfang eines Veranstaltungsnamens, der mehrere
  //           Veranstaltungen trägt ("Ironman", "Wings for Life")
  //   ORT   - ein Standort ("München")
  const VORSCHLAG_MIN_VERANSTALTUNGEN = 3;   // darunter ist es keine Serie
  // Drei Wörter reichen für jede Serie in den Daten ("Ahmadiyya
  // Charity Walk", "Wings for Life"); eine vierte Stufe kostete ein
  // Viertel mehr Rechenzeit und brachte nur Satzfetzen.
  const VORSCHLAG_MAX_WORTE = 3;
  // Wörter, die als Vorschlag nichts bringen: Sie stehen in so vielen
  // Namen, dass der Vorschlag die Trefferliste nicht verkleinert. Ein
  // zusammengesetztes Wort wie "Silvesterlauf" oder "Crosslauf" bleibt
  // drin - danach sucht man wirklich.
  const VORSCHLAG_STOPP = new Set([
    'lauf', 'laufen', 'run', 'running', 'int', 'internationaler',
    'internationale', 'internationales', 'der', 'die', 'das', 'rund',
    'um', 'am', 'im', 'in', 'und', 'von', 'zum', 'zur', 'grosser',
    'großer', 'kleiner', 'neuer', 'erster'
  ]);

  // Die Regex-Literale stehen ABSICHTLICH hier oben und nicht in den
  // Funktionen. Ein Literal wird bei jeder Auswertung neu gebaut - in
  // `vorschlagsWorte` und `istZahl` also rund 130.000-mal je
  // Index-Aufbau. Gemessen: 650 ms mit den Literalen in den Funktionen,
  // **31 ms** mit ihnen hier. Dieselbe Falle wie bei den
  // Temporal-Dead-Zone-Fehlern - sieht harmlos aus, kostet den Faktor 20.
  const VORSCHLAG_AUFLAGE_RE = /^\s*\d+\s*\.?\s*/;
  const VORSCHLAG_TRENNER_RE = /[\s,;:|/()\[\]]+/;
  const VORSCHLAG_RAND_RE = /^[^\wÄÖÜäöüß]+|[^\wÄÖÜäöüß]+$/g;
  const VORSCHLAG_WORT_RE = /[\wÄÖÜäöüß]/;
  const VORSCHLAG_ZAHL_RE = /^\d+$/;

  function vorschlagsWorte(name) {
    // Führende Auflagen-Nummer weg ("13. Fichtelgebirgstrailrun"), dann
    // an allem trennen, was kein Wort ist. Der Bindestrich TRENNT hier
    // ("Rats-Run - Auhausen" -> "Rats", "Run", "Auhausen") wäre falsch,
    // deshalb bleibt er im Wort: "Rats-Run" ist die Serie.
    return String(name || '')
      .replace(VORSCHLAG_AUFLAGE_RE, '')
      .split(VORSCHLAG_TRENNER_RE)
      .map(w => w.replace(VORSCHLAG_RAND_RE, ''))
      // Reine Satzzeichen sind kein Wort. Ohne diese Zeile stand
      // "Wings for Life -" als eigener Vorschlag in der Liste (der
      // Bindestrich aus "Wings for Life - Frankfurt am Main").
      .filter(w => VORSCHLAG_WORT_RE.test(w));
  }

  /** Baut den Vorschlags-Index. EINMAL nach dem Laden aufrufen, nicht
   *  je Tastendruck: über 4.000 Events kostet das ~20 ms, über 20.000
   *  entsprechend mehr - pro Anschlag wäre das zu viel. */
  function buildSuggestions(events) {
    // EIN Eimer je Vorschlag, klein geschrieben als Schlüssel: Sonst
    // stehen "UltraTrail", "Ultratrail" und "ULTRATRAIL" dreimal da,
    // und "München" zweimal (einmal als Ort, einmal aus den Namen).
    // Gezählt wird die VEREINIGUNG der Veranstaltungen - das ist die
    // Zahl, die der Nutzer nach dem Klick auch bekommt.
    const eimer = new Map();
    function merke(text, schluessel, istOrt) {
      const k = text.toLowerCase();
      let v = eimer.get(k);
      // Angezeigt wird die ZUERST gesehene Schreibweise. Die häufigste
      // zu nehmen wäre schöner, kostete aber eine eigene Map je Eimer
      // und damit bei 20.000 Events mehrere hundert Millisekunden -
      // für einen Unterschied, den man nur bei "UltraTrail" gegen
      // "Ultratrail" überhaupt sieht.
      if (!v) { v = { text, menge: new Set(), istOrt: false }; eimer.set(k, v); }
      v.menge.add(schluessel);
      if (istOrt) v.istOrt = true;
    }
    const istZahl = (w) => VORSCHLAG_ZAHL_RE.test(w);

    (events || []).forEach(e => {
      const schluessel = `${e.name}|${e.datum_start}`;
      const worte = vorschlagsWorte(e.name);
      const klein = worte.map(w => w.toLowerCase());
      // Wortgruppen an JEDER Stelle, nicht nur am Namensanfang. Sonst
      // fehlt jede Serie, die nicht vornsteht: "Kulmbach Spartan
      // Trifecta Weekend" beginnt mit dem Ort, und "Spartan" wäre kein
      // Vorschlag geworden. Gleiches gilt für "… Charity Walk".
      //
      // Die Reihenfolge der Abbrüche ist hier Tempo: Ist das ERSTE Wort
      // ein Füllwort oder eine Zahl, sind alle Gruppen ab dieser Stelle
      // hinfällig - dann gleich weiter, statt vier Zeichenketten zu
      // bauen und wieder zu verwerfen.
      for (let i = 0; i < worte.length; i++) {
        if (VORSCHLAG_STOPP.has(klein[i]) || istZahl(klein[i])) continue;
        let text = worte[i];
        for (let n = 1; n <= VORSCHLAG_MAX_WORTE && i + n <= worte.length; n++) {
          if (n > 1) text += ' ' + worte[i + n - 1];
          const letztes = klein[i + n - 1];
          if (istZahl(letztes) || VORSCHLAG_STOPP.has(letztes)) continue;
          if (n === 1 && text.length < 4) continue;
          merke(text, schluessel, false);
        }
      }
      const ort = (e.standort || '').trim();
      if (ort) merke(ort, schluessel, true);
    });

    // Ein kürzerer Begriff mit GLEICH vielen Veranstaltungen sagt nichts
    // Eigenes: "Wings" und "Wings for Life" treffen beide 21, angeboten
    // wird der längere. Ohne das stünden vier Stufen derselben Serie da.
    // Ein kürzerer Begriff mit GLEICH vielen Veranstaltungen sagt nichts
    // Eigenes: "Wings" und "Wings for Life" treffen beide 21, angeboten
    // wird der längere. Ohne das stünden drei Stufen derselben Serie da.
    //
    // Die Richtung ist Tempo. Naheliegend wäre: für jeden Begriff die
    // Begriffe mit derselben Trefferzahl durchsuchen. Gemessen war das
    // 533 ms bei 4.335 Events und 1,7 s bei 20.000 - die Gruppe
    // "1 Treffer" allein hat 6.209 Einträge, und der Test schlägt fast
    // nie an (88 von 1.500).
    //
    // Umgedreht kostet es nichts: Jeder LANGE Begriff kennt seine
    // eigenen Teilstücke (bei höchstens drei Wörtern sind das fünf) und
    // markiert sie, wenn sie dieselbe Trefferzahl haben. Aus
    // "Gruppengröße" wird damit eine Konstante.
    const verdraengt = new Set();
    eimer.forEach((v, k) => {
      if (v.istOrt) return;
      const worte = k.split(' ');
      if (worte.length < 2) return;
      for (let i = 0; i < worte.length; i++) {
        for (let n = 1; n <= worte.length - i; n++) {
          if (n === worte.length) continue;          // der Begriff selbst
          const teil = worte.slice(i, i + n).join(' ');
          const andere = eimer.get(teil);
          if (andere && !andere.istOrt && andere.menge.size === v.menge.size) {
            verdraengt.add(teil);
          }
        }
      }
    });

    const liste = [];
    eimer.forEach((v, k) => {
      if (v.istOrt) {
        // Ein ORT wird nie verdrängt: "Berlin" ist eine eigene Auskunft,
        // auch wenn "Berlin Marathon" dieselbe Trefferzahl hätte.
        liste.push({ text: v.text, anzahl: v.menge.size, art: 'ort' });
        return;
      }
      if (v.menge.size < VORSCHLAG_MIN_VERANSTALTUNGEN) return;
      if (verdraengt.has(k)) return;
      liste.push({ text: v.text, anzahl: v.menge.size, art: 'serie' });
    });
    liste.sort((a, b) => b.anzahl - a.anzahl || a.text.localeCompare(b.text, 'de'));
    return liste;
  }

  /** Die passenden Vorschläge zu einer Eingabe, beste zuerst.
   *  Ein Treffer am WORTANFANG zählt mehr als einer in der Mitte -
   *  "Iron" soll "Ironman" bringen und nicht "Eisenbahn-Lauf". */
  function matchSuggestions(index, eingabe, grenze) {
    const q = String(eingabe || '').trim().toLowerCase();
    if (q.length < 2) return [];
    const treffer = [];
    (index || []).forEach(v => {
      const t = v.text.toLowerCase();
      if (t === q) return;                       // schon eingetippt
      let rang;
      if (t.startsWith(q)) rang = 0;
      else if (new RegExp('\\b' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i').test(v.text)) rang = 1;
      else if (t.includes(q)) rang = 2;
      else return;
      treffer.push({ ...v, rang });
    });
    treffer.sort((a, b) => a.rang - b.rang
      || b.anzahl - a.anzahl
      || a.text.localeCompare(b.text, 'de'));
    return treffer.slice(0, grenze || 8);
  }

  // Eine unabhängige Kopie eines Filterzustands. Nötig, weil Sets und
  // `origin` sonst geteilt wären: Der Abo-Dialog in events.html arbeitet
  // mit einer Kopie der aktuellen Suche - was dort umgestellt wird, darf
  // die Liste dahinter NICHT verändern.
  //
  // `ohneDatum` lässt die Tagesauswahl weg: Ein Abo schaut in die
  // Zukunft, ein Datumsfilter aus der Vergangenheit dieser Suche würde
  // dafür nie passen.
  function copyState(state, ohneDatum) {
    const kopie = createState();
    ['land', 'art1', 'art2', 'standort', 'distanceCategories'].forEach(k => {
      state[k].forEach(v => kopie[k].add(v));
    });
    if (!ohneDatum) {
      state.selectedDays.forEach(v => kopie.selectedDays.add(v));
      kopie.datePreset = state.datePreset;
    }
    kopie.suche = state.suche;
    kopie.nameQuery = state.nameQuery;
    kopie.laengeMin = state.laengeMin;
    kopie.laengeMax = state.laengeMax;
    kopie.origin = state.origin ? Object.assign({}, state.origin) : null;
    kopie.radiusKm = state.radiusKm;
    return kopie;
  }

  function clearFilters(state) {
    state.land.clear();
    state.art1.clear();
    state.art2.clear();
    state.standort.clear();
    state.suche = '';
    state.nameQuery = '';
    state.selectedDays.clear();
    state.datePreset = null;
    state.laengeMin = '';
    state.laengeMax = '';
    state.distanceCategories.clear();
    state.origin = null;
    state.radiusKm = null;
  }

  // Filtert der Zustand überhaupt etwas? Die Karte blendet die
  // Chip-Zeile ohne aktive Filter komplett aus.
  function hasFilters(state) {
    return !!(state.land.size || state.art1.size || state.art2.size || state.standort.size
      || state.suche.trim() || state.nameQuery.trim() || state.selectedDays.size
      || state.laengeMin !== '' || state.laengeMax !== ''
      || state.distanceCategories.size || (state.origin && state.radiusKm != null));
  }

  function haversineKm(lat1, lon1, lat2, lon2) {
    const R = 6371;
    const toRad = d => d * Math.PI / 180;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat / 2) ** 2 +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  // Vergangene Events erscheinen gar nicht. Aufgeräumt wird events.json
  // zwar auch serverseitig (clean_events.drop_past_events), aber nur
  // einmal pro Woche - ohne diesen Filter stünden dazwischen bis zu
  // sieben Tage Vergangenheit in der Liste. Maßgeblich ist das Ende:
  // ein mehrtägiges Rennen bleibt bis zu seinem letzten Tag; ein Event
  // ohne verwertbares Datum bleibt drin (nicht auf Unsicherheit hin
  // ausblenden).
  function dropPastEvents(list) {
    const today = todayIso();
    return list.filter(e => {
      const ende = e.datum_ende || e.datum_start;
      if (typeof ende !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(ende)) return true;
      return ende >= today;
    });
  }

  function distanceFromOrigin(state, e) {
    if (!state.origin || e.lat == null || e.lon == null) return null;
    return haversineKm(state.origin.lat, state.origin.lon, e.lat, e.lon);
  }

  // ---------- Triathlon: die Länge ist ein FORMAT ----------
  //
  // Sechs Formate (Vorgabe des Nutzers, 21.09.2026): Super-Sprint, Sprint,
  // Olympisch, Mitteldistanz (70.3), Langstrecke (140.6), Ultra. Die
  // Kilometer in events.json sind die Summe der Teilstrecken (Datenregel
  // 15); WELCHES Format eine Zeile ist, entscheidet diese Funktion - in
  // dieser Reihenfolge: das Label des Veranstalters, dann die
  // Schwimm-Teilstrecke im Label (Datenregel 21), dann die Summe. Die
  // Anzeigenamen stehen in event-detail.js (TRIATHLON_FORMATE); der
  // Filter "Länge" nimmt dieselbe Funktion (matchesDistanceCategory), damit
  // Spalte und Filter nie Verschiedenes sagen. Eine KOPIE steht in
  // functions/index.js (Abo-Filter); test_triathlon_format_kopie hält
  // beide gleich.
  // Reihenfolge: das Längste zuerst - "Langdistanz" enthält kein "kurz",
  // "Super-Sprint" enthält "Sprint", also steht er davor.
  const TRIATHLON_FORMAT_IM_LABEL = [
    [/ultra|double|doppel|triple|dreifach|\bdeca\b|quintuple/i, 'ultra'],
    [/140[.,]6|langdist|langstreck|lange\s*distanz|\blang\b|long\s*dist|volldist|full\s*dist|ironman[\s-]*dist/i, 'lang'],
    [/70[.,]3|mitteldist|\bmittel\b|middle|halbdist|half[\s-]*dist|halb-?ironman/i, 'mittel'],
    [/olymp|standard[\s-]*dist|kurzdist|kurz-?distanz|\bkurz\b|short[\s-]*dist/i, 'olympisch'],
    [/super[\s-]*sprint/i, 'supersprint'],
    [/sprint/i, 'sprint']
  ];
  // Das Schwimmen aus dem Label ("0,3 km Schwimmen", "400 m Swim") in
  // Kilometern, oder null. Die Teilstrecken stehen dort in Klammern
  // hinter der Gesamtlänge (siehe CLAUDE.md, Elfter Durchgang).
  const TRIATHLON_SCHWIMMEN_IM_LABEL = /(\d+(?:[.,]\d+)?)\s*(km|m)\s*(?:schwimmen|swim)/i;
  function schwimmKm(e) {
    const treffer = TRIATHLON_SCHWIMMEN_IM_LABEL.exec(e.wettbewerb || '');
    if (!treffer) return null;
    const wert = parseFloat(treffer[1].replace(',', '.'));
    if (Number.isNaN(wert)) return null;
    return treffer[2].toLowerCase() === 'm' ? wert / 1000 : wert;
  }

  function triathlonFormat(e) {
    if (!e || e.art1 !== 'Triathlon') return null;
    const label = e.wettbewerb || '';
    for (const [muster, key] of TRIATHLON_FORMAT_IM_LABEL) if (muster.test(label)) return key;
    if (e.art2 === 'Swimrun' || e.art2 === 'Quadrathlon') return null;
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
    if (schwimmen != null && schwimmen < 0.5) return 'supersprint';
    if (km < 23) return 'supersprint';
    if (km < 40) return 'sprint';
    if (km < 80) return 'olympisch';
    if (km < 160) return 'mittel';
    if (km < 230) return 'lang';
    return 'ultra';
  }
  // Format-Schlüssel -> Kategorie-Schlüssel des Längen-Filters
  // (DISTANCE_CATEGORIES.Triathlon: 'olympic', nicht 'olympisch';
  // 'tultra', weil 'ultra' der Ultramarathon ist).
  const TRIATHLON_FORMAT_KATEGORIE = {
    supersprint: 'supersprint', sprint: 'sprint', olympisch: 'olympic',
    mittel: 'middle', lang: 'long', ultra: 'tultra'
  };

  function matchesDistanceCategory(state, e) {
    if (state.distanceCategories.size === 0) return true;
    for (const compositeKey of state.distanceCategories) {
      const sep = compositeKey.indexOf(':');
      const sport = compositeKey.slice(0, sep);
      const catKey = compositeKey.slice(sep + 1);
      if (e.art1 !== sport) continue;
      const cat = (DISTANCE_CATEGORIES[sport] || []).find(c => c.key === catKey);
      if (!cat) continue;
      // Zeitrennen: die Dauer entscheidet, nicht die (fehlende) Distanz.
      if (cat.zeit) {
        if (e.dauer_h != null) return true;
        continue;
      }
      // Triathlon: das ANGEZEIGTE Format entscheidet (Label, Schwimmen,
      // Summe - siehe triathlonFormat), nicht die rohen Kilometer. Ohne
      // Format (Swimrun, Quadrathlon, keine Länge) wie überall die km.
      if (sport === 'Triathlon') {
        const format = triathlonFormat(e);
        if (format) {
          if (TRIATHLON_FORMAT_KATEGORIE[format] === catKey) return true;
          continue;
        }
      }
      if (e.laenge_km == null) continue;
      if (cat.test(e.laenge_km)) return true;
    }
    return false;
  }

  // Worin die Mastersuche sucht: Name, Wettbewerb, Ort - und Land,
  // Sportart und Kategorie in BEIDEN Sprachen.
  //
  // Die zweite Hälfte ist der Punkt: Wer die Seite auf Deutsch stehen
  // hat, soll trotzdem „Germany" oder „Munich" eingeben können und
  // dieselben Events bekommen (so vom Nutzer gewünscht). Umgekehrt
  // findet „Laufen" in der englischen Fassung die Running-Events. Das
  // kostet nichts an Genauigkeit: Gesucht wird weiterhin als Teiltext,
  // nur eben über ein paar Wörter mehr.
  function sucheHeuhaufen(e) {
    const teile = [e.name, e.wettbewerb, e.standort, e.land, e.art1, e.art2];
    // Ein markiertes Charity-Event soll die Suche nach "Charity" bzw.
    // "Benefiz" auch dann finden, wenn es nicht so heißt - die Kategorie
    // trug das Wort früher, jetzt tut es das Merkmal.
    if (e.charity) teile.push('Charity', 'Benefiz');
    ['land', 'art1', 'art2', 'standort'].forEach(feld => {
      const eintrag = VALUE_TRANSLATIONS[feld] && VALUE_TRANSLATIONS[feld][e[feld]];
      if (eintrag) teile.push(eintrag.de, eintrag.en);
    });
    return teile.filter(Boolean).join(' ').toLowerCase();
  }

  // Trifft ein einzelnes Event alle aktiven Filter? Die Liste und die
  // Karte fragen dieselbe Funktion - sonst zeigte ein Kartenmarker
  // Events, die in der Liste herausgefiltert sind.
  // Der Kategorie-Filter. "Charity" ist der Sonderfall darin: Es ist
  // seit dem 21.09.2026 keine Kategorie mehr, sondern ein eigenes
  // Merkmal am Event (e.charity) - der Nutzer wollte die echte
  // Kategorie zurück, ein Benefiz-Crosslauf ist ein Trail UND ein
  // Charity-Event. Im Filter-Panel steht "Charity" trotzdem weiter bei
  // den Kategorien: Danach zu suchen war der ursprüngliche Wunsch
  // ("alle Schwimmen, Lauf und Rennrad Charity Events"), und eine
  // eigene Filterreihe nur dafür wäre eine Pille mehr in einer Leiste,
  // die auf 1024 px ohnehin knapp ist.
  //
  // `e.art2 === 'Charity'` bleibt mitgeprüft: Ein geteilter Link aus
  // der Zeit, als es die Kategorie noch gab, soll weiter etwas finden.
  // Dasselbe steht in functions/index.js (ABO-Filter).
  function matchesKategorie(state, e) {
    if (state.art2.has(e.art2)) return true;
    return state.art2.has('Charity') && (e.charity === true || e.art2 === 'Charity');
  }

  function matchEvent(state, e) {
    if (state.land.size && !state.land.has(e.land)) return false;
    if (state.art1.size && !state.art1.has(e.art1)) return false;
    if (state.art2.size && !matchesKategorie(state, e)) return false;
    if (state.standort.size && !state.standort.has(e.standort)) return false;
    // Die Suche greift auch auf die Wettbewerbsbezeichnung zu, damit
    // z. B. "Halbmarathon" die Halbmarathon-Strecke einer Veranstaltung
    // findet, die diesen Begriff nicht im Namen trägt.
    if (state.nameQuery.trim()) {
      const needle = state.nameQuery.trim().toLowerCase();
      const haystack = `${e.name || ''} ${e.wettbewerb || ''}`.toLowerCase();
      if (!haystack.includes(needle)) return false;
    }
    // Die Mastersuche sucht zusätzlich im Ort: EIN Feld für "Marathon"
    // und für "München". Absichtlich dieselbe schlichte Regel wie oben
    // (kleinschreiben, `includes`) - sie muss in `functions/index.js`
    // noch einmal stehen, damit ein Abo genau das trifft, was die Suche
    // zeigte. Je einfacher die Regel, desto eher bleiben beide gleich.
    if (state.suche.trim()) {
      const needle = state.suche.trim().toLowerCase();
      if (!sucheHeuhaufen(e).includes(needle)) return false;
    }
    if (state.selectedDays.size && !state.selectedDays.has(e.datum_start)) return false;
    if (state.laengeMin !== '' && e.laenge_km != null && e.laenge_km < parseFloat(state.laengeMin)) return false;
    if (state.laengeMax !== '' && e.laenge_km != null && e.laenge_km > parseFloat(state.laengeMax)) return false;
    if (!matchesDistanceCategory(state, e)) return false;
    if (state.radiusKm != null && state.origin) {
      if (e.lat == null || e.lon == null) return false;
      if (haversineKm(state.origin.lat, state.origin.lon, e.lat, e.lon) > state.radiusKm) return false;
    }
    return true;
  }

  // `alleTage` sind alle in den Daten vorkommenden datum_start-Werte: der
  // Zeitraum-Knopf wählt daraus die Tage im Bereich aus, statt einen
  // Bereich zu speichern (der Baum arbeitet genauso, also bleibt es EIN
  // Filtermechanismus).
  function applyDatePreset(state, preset, alleTage) {
    const [von, bis] = preset.range();
    state.selectedDays.clear();
    (alleTage || []).filter(d => d >= von && d <= bis).forEach(d => state.selectedDays.add(d));
    state.datePreset = preset.key;
  }

  function setOriginPlain(state, origin) {
    state.origin = origin;
    if (origin && state.radiusKm == null) state.radiusKm = RADIUS_DEFAULT_KM;
    if (!origin) state.radiusKm = null;
  }

  // ---------- Filter in der Adresse (teilbarer Link) ----------

  // Die Adresse trägt den vollständigen Filterzustand, damit eine
  // gefilterte Liste weitergegeben werden kann ("alle Trails im Umkreis
  // von 50 km um Stuttgart") - und damit der Wechsel zwischen Liste und
  // Karte die Filter mitnimmt.
  function toParams(state) {
    const p = new URLSearchParams();
    if (state.suche.trim()) p.set('s', state.suche.trim());
    if (state.nameQuery.trim()) p.set('q', state.nameQuery.trim());
    if (state.land.size) p.set('land', Array.from(state.land).join(','));
    if (state.art1.size) p.set('sportart', Array.from(state.art1).join(','));
    if (state.art2.size) p.set('art2', Array.from(state.art2).join(','));
    if (state.standort.size) p.set('standort', Array.from(state.standort).join(','));
    if (state.laengeMin !== '') p.set('kmmin', state.laengeMin);
    if (state.laengeMax !== '') p.set('kmmax', state.laengeMax);
    if (state.distanceCategories.size) p.set('kat', Array.from(state.distanceCategories).join(','));
    if (state.datePreset) p.set('zeitraum', state.datePreset);
    else if (state.selectedDays.size && state.selectedDays.size <= URL_MAX_DAYS) {
      p.set('tage', Array.from(state.selectedDays).sort().join(','));
    }
    if (state.origin) {
      p.set('ort', `${state.origin.lat.toFixed(4)},${state.origin.lon.toFixed(4)},${state.origin.label}`);
      if (state.radiusKm != null) p.set('umkreis', String(state.radiusKm));
    }
    return p;
  }

  // Liest die Filter-Parameter aus einer Adresse in den Zustand.
  // opts.knownStandort  - Prüfung, ob ein Ortsname in den Daten vorkommt
  // opts.setOrigin      - eigene Behandlung des Ausgangspunkts (die Liste
  //                       schaltet dabei die Entfernungs-Spalte zu)
  // opts.alleTage       - Tage für die Zeitraum-Knöpfe (siehe applyDatePreset)
  // opts.geoLabel       - Ersatzbezeichnung, wenn ?ort= keine mitbringt
  function readParams(state, search, opts) {
    opts = opts || {};
    let p;
    try { p = new URLSearchParams(search); } catch (e) { return; }
    const mengen = [
      // Sportart und Kategorie gegen die bekannten Werte prüfen: ein
      // Tippfehler in der Adresse soll keine leere Liste erzeugen, die
      // dann nach einem Fehler der Seite aussieht.
      ['land', state.land, v => LAENDER.includes(v)],
      ['sportart', state.art1, v => Object.prototype.hasOwnProperty.call(DISTANCE_CATEGORIES, v)],
      ['art2', state.art2, null],
      ['standort', state.standort, opts.knownStandort || null],
      ['kat', state.distanceCategories, null]
    ];
    mengen.forEach(([name, ziel, gueltig]) => {
      const wert = p.get(name);
      if (!wert) return;
      wert.split(',').filter(Boolean).forEach(v => { if (!gueltig || gueltig(v)) ziel.add(v); });
    });
    const q = p.get('q');
    if (q) state.nameQuery = q;
    const suche = p.get('s');
    if (suche) state.suche = suche;
    const kmmin = p.get('kmmin'); if (kmmin) state.laengeMin = kmmin;
    const kmmax = p.get('kmmax'); if (kmmax) state.laengeMax = kmmax;
    const zeitraum = p.get('zeitraum');
    const preset = DATE_PRESETS.find(x => x.key === zeitraum);
    if (preset) applyDatePreset(state, preset, opts.alleTage || []);
    else {
      const tage = p.get('tage');
      if (tage) tage.split(',').filter(Boolean).forEach(d => state.selectedDays.add(d));
    }
    const ort = p.get('ort');
    if (ort) {
      const teile = ort.split(',');
      const lat = parseFloat(teile[0]);
      const lon = parseFloat(teile[1]);
      if (Number.isFinite(lat) && Number.isFinite(lon)) {
        const label = teile.slice(2).join(',') || opts.geoLabel || '';
        (opts.setOrigin || setOriginPlain)(state, { lat, lon, label });
        const umkreis = parseInt(p.get('umkreis') || '', 10);
        if (Number.isFinite(umkreis) && umkreis > 0) state.radiusKm = umkreis;
      }
    }
  }

  // ---------- Filter-Chips ----------

  // Die aktiven Filter als Liste von { label, clear } - die Anzeige
  // (DOM) baut jede Seite selbst, die Beschriftung und das, was das ✕
  // entfernt, ist überall gleich.
  //
  // Mengen-Filter (Land, Stadt/Ort, Sportart, Kategorie) werden NICHT
  // je ausgewähltem Wert aufgezählt. "Alle" im Stadt/Ort-Filter wählte
  // sonst ~2000 Orte aus und schob die ganze Liste mit
  // "Stadt/Ort: Aachen ×"-Chips aus dem Bild. Stattdessen:
  //   alles ausgewählt         -> ein Chip "Stadt/Ort: Alle"
  //   mehr als MAX_VALUE_CHIPS -> ein Chip "Stadt/Ort: 12 ausgewählt"
  //   wenige Werte             -> ein Chip pro Wert
  //
  // ctx.t / ctx.tv      - Übersetzungsfunktionen der Seite
  // ctx.lang            - 'de' | 'en' (für die Distanz-Kategorienamen)
  // ctx.optionCount(k)  - wie viele Werte der Filter k überhaupt hat
  // ctx.dayCount        - wie viele Termine es überhaupt gibt
  // ctx.setOrigin       - eigene Behandlung beim Entfernen des Umkreises
  function buildChips(state, ctx) {
    const t = ctx.t;
    const tv = ctx.tv;
    const chips = [];
    // Jeder Chip trägt `col` (welcher Filterknopf) und `value` (der
    // Wert ohne "Datum: "-Vorsatz): Die Filterknöpfe über der Liste
    // zeigen seit dem 21.09.2026 den gesetzten Wert direkt in der
    // Pille ("Sportart: Laufen"), gerechnet aus genau diesen Chips -
    // keine zweite Zusammenfassung (filter-ui.js, filterSummary).
    if (state.suche.trim()) chips.push({ col: 'suche', value: state.suche.trim(), label: t('chip_suche', state.suche.trim()), clear: () => { state.suche = ''; } });
    if (state.nameQuery.trim()) chips.push({ col: 'name', value: state.nameQuery.trim(), label: t('chip_name', state.nameQuery.trim()), clear: () => { state.nameQuery = ''; } });
    if (state.selectedDays.size > 0) {
      // Sind alle vorhandenen Termine ausgewählt, ist "Datum: Alle"
      // aussagekräftiger als "Datum: 812 Tage ausgewählt" - gleiche
      // Logik wie bei den Mengen-Filtern. Ein Zeitraum-Knopf ("Nächste
      // 3 Monate") steht als ZEITRAUM da ("26.09.–26.12.2026"): Das
      // sagt, was gefiltert ist, der Knopfname nicht.
      const alleTage = ctx.dayCount || 0;
      const preset = DATE_PRESETS.find(x => x.key === state.datePreset);
      const tage = Array.from(state.selectedDays).sort();
      let value;
      if (preset) value = formatDateRangeShort(tage[0], tage[tage.length - 1], ctx.lang);
      else if (alleTage > 0 && state.selectedDays.size >= alleTage) value = t('chip_value_all');
      else if (tage.length === 1) value = formatDate(tage[0], ctx.lang);
      else value = t('chip_value_days', tage.length);
      chips.push({ col: 'datum', value, label: t('chip_datum_wert', value),
                   clear: () => { state.selectedDays.clear(); state.datePreset = null; } });
    }

    function pushSetChips(stateKey, chipKey, format) {
      const selected = state[stateKey];
      if (selected.size === 0) return;
      const optionCount = ctx.optionCount ? ctx.optionCount(stateKey) : 0;
      if (optionCount > 0 && selected.size >= optionCount) {
        chips.push({ col: stateKey, value: t('chip_value_all'), label: t(chipKey, t('chip_value_all')), clear: () => selected.clear() });
        return;
      }
      if (selected.size > MAX_VALUE_CHIPS) {
        chips.push({
          col: stateKey, value: t('chip_value_count', selected.size),
          label: t(chipKey, t('chip_value_count', selected.size)),
          clear: () => selected.clear()
        });
        return;
      }
      selected.forEach(v => chips.push({ col: stateKey, value: format(v), label: t(chipKey, format(v)), clear: () => selected.delete(v) }));
    }
    pushSetChips('land', 'chip_land', v => tv('land', v));
    pushSetChips('standort', 'chip_standort', v => tv('standort', v));
    pushSetChips('art1', 'chip_sportart', v => tv('art1', v));
    pushSetChips('art2', 'chip_kategorie', v => tv('art2', v));

    // Die Zahl kommt aus einem <input type="number"> und trägt dort immer
    // einen Punkt - im deutschen Chip muss ein Komma stehen.
    if (state.laengeMin !== '') chips.push({ col: 'laenge_km', value: t('chip_ab_km', formatNumber(state.laengeMin, ctx.lang, 1)), label: t('chip_laenge_ab', formatNumber(state.laengeMin, ctx.lang, 1)), clear: () => { state.laengeMin = ''; } });
    if (state.laengeMax !== '') chips.push({ col: 'laenge_km', value: t('chip_bis_km', formatNumber(state.laengeMax, ctx.lang, 1)), label: t('chip_laenge_bis', formatNumber(state.laengeMax, ctx.lang, 1)), clear: () => { state.laengeMax = ''; } });
    if (state.distanceCategories.size > MAX_VALUE_CHIPS) {
      chips.push({
        col: 'laenge_km', value: t('chip_value_count', state.distanceCategories.size),
        label: t('chip_distanz_count', state.distanceCategories.size),
        clear: () => state.distanceCategories.clear()
      });
    } else state.distanceCategories.forEach(compositeKey => {
      const sep = compositeKey.indexOf(':');
      const sport = compositeKey.slice(0, sep);
      const catKey = compositeKey.slice(sep + 1);
      const label = DISTANCE_CATEGORY_LABELS[ctx.lang][catKey] || catKey;
      chips.push({ col: 'laenge_km', value: label, label: t('chip_distanz', tv('art1', sport), label), clear: () => state.distanceCategories.delete(compositeKey) });
    });
    if (state.origin && state.radiusKm != null) {
      // Das Kreuz am Chip entfernt den Ausgangspunkt gleich mit: ein
      // Ausgangspunkt ohne Umkreis filtert nichts und stünde nur noch
      // unsichtbar im Panel.
      chips.push({
        col: 'standort', value: t('chip_umkreis_wert', state.radiusKm, state.origin.label),
        label: t('chip_umkreis', state.radiusKm, state.origin.label),
        clear: () => { (ctx.setOrigin || setOriginPlain)(state, null); }
      });
    }
    return chips;
  }

  global.EnduranceFilters = {
    formatMonthYear,
    formatEventDate,
    formatDateWeekday,
    formatDateLong,
    formatDateRangeShort,
    formatInt,
    formatDistanceKm,
    relativeDays,
    I18N,
    VALUE_TRANSLATIONS,
    LAENDER,
    DISTANCE_CATEGORIES,
    DISTANCE_CATEGORY_LABELS,
    DATE_PRESETS,
    RADIUS_MIN_KM,
    RADIUS_MAX_KM,
    RADIUS_DEFAULT_KM,
    MAX_VALUE_CHIPS,
    URL_MAX_DAYS,
    escapeHtml,
    sucheHeuhaufen,
    uniqueSorted,
    formatDate,
    formatNumber,
    formatKm,
    formatHours,
    triathlonFormat,
    isoOf,
    todayIso,
    createState,
    copyState,
    buildSuggestions,
    matchSuggestions,
    clearFilters,
    hasFilters,
    haversineKm,
    dropPastEvents,
    distanceFromOrigin,
    matchesDistanceCategory,
    matchEvent,
    applyDatePreset,
    setOriginPlain,
    toParams,
    readParams,
    buildChips
  };
})(typeof window !== 'undefined' ? window : globalThis);

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
      chip_datum_all: 'Datum: Alle',
      chip_datum_preset: (label) => `Datum: ${label}`,
      preset_weekend: 'Dieses Wochenende',
      preset_d30: 'Nächste 30 Tage',
      preset_m3: 'Nächste 3 Monate',
      preset_year: 'Dieses Jahr',
      chip_distanz_count: (n) => `Länge: ${n} ausgewählt`,
      chip_name: (q) => `Name: „${q}"`,
      chip_sportart: (v) => `Sportart: ${v}`,
      chip_standort: (v) => `Stadt/Ort: ${v}`,
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
      chip_datum_all: 'Date: All',
      chip_datum_preset: (label) => `Date: ${label}`,
      preset_weekend: 'This weekend',
      preset_d30: 'Next 30 days',
      preset_m3: 'Next 3 months',
      preset_year: 'This year',
      chip_distanz_count: (n) => `Length: ${n} selected`,
      chip_name: (q) => `Name: "${q}"`,
      chip_sportart: (v) => `Sport: ${v}`,
      chip_standort: (v) => `City: ${v}`,
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
      'Schweiz': { de: 'Schweiz', en: 'Switzerland' }
    },
    art1: {
      'Laufen': { de: 'Laufen', en: 'Running' },
      'Schwimmen': { de: 'Schwimmen', en: 'Swimming' },
      'Fahrrad': { de: 'Fahrrad', en: 'Cycling' },
      'Triathlon': { de: 'Triathlon', en: 'Triathlon' }
    },
    art2: {
      'Straße': { de: 'Straße', en: 'Road' },
      // Trail und Cross sind EIN Wert: beides Geländelauf, die Quellen
      // benennen dieselbe Strecke mal so, mal so (Wunsch des Nutzers).
      // Die beiden alten Werte bleiben übersetzbar - ein geteilter Link
      // von früher (?art2=Trail) soll keinen rohen Schlüssel anzeigen.
      'Trail/Cross': { de: 'Trail/Cross', en: 'Trail/Cross' },
      'Trail': { de: 'Trail', en: 'Trail' },
      'Bahn': { de: 'Bahn', en: 'Track' },
      'Berg': { de: 'Berg', en: 'Mountain' },
      'Cross': { de: 'Cross', en: 'Cross Country' },
      'Hindernis': { de: 'Hindernis', en: 'Obstacle' },
      // Englischer Fachbegriff, in beiden Sprachen gleich: abseits
      // ausgebauter Wege, oft ohne Verpflegung und teils zeitlich
      // begrenzt statt über eine feste Strecke.
      'Backcountry Ultra': { de: 'Backcountry Ultra', en: 'Backcountry Ultra' },
      'Freiwasser': { de: 'Freiwasser', en: 'Open Water' },
      'Becken': { de: 'Becken', en: 'Pool' },
      'Zeitfahren': { de: 'Zeitfahren', en: 'Time Trial' },
      'Mountainbike': { de: 'Mountainbike', en: 'Mountain Bike' },
      'Gravel': { de: 'Gravel', en: 'Gravel' },
      'Cyclecross': { de: 'Cyclecross', en: 'Cyclocross' }
    }
  };

  // Die drei Länder, die die Daten überhaupt enthalten. Gebraucht als
  // Prüfung beim Lesen der Adresse (?land=…).
  const LAENDER = ['Deutschland', 'Österreich', 'Schweiz'];

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
    'Triathlon': [
      { key: 'sprint', test: km => km > 0 && km < 40 },
      { key: 'olympic', test: km => Math.abs(km - 51.5) <= 3 },
      { key: 'middle', test: km => Math.abs(km - 113) <= 5 },
      { key: 'long', test: km => Math.abs(km - 226) <= 8 },
      { key: 'zeit', zeit: true }
    ]
  };

  const DISTANCE_CATEGORY_LABELS = {
    de: {
      '5k': '5 km', '10k': '10 km', 'half': 'Halbmarathon', 'marathon': 'Marathon', 'ultra': 'Ultramarathon',
      'r50': 'bis 50 km', 'r100': '50–100 km', 'r150': '100–150 km', 'r200': '150–200 km', 'rultra': '200+ km',
      's1': '1 km', 's2': '2 km', 's3': '3 km', 's5': '5 km', 's10': '10+ km (Marathonschwimmen)',
      'sprint': 'Sprintdistanz', 'olympic': 'Olympische Distanz (51.5 km)',
      'middle': 'Mitteldistanz / 70.3 (113 km)', 'long': 'Langdistanz / Ironman (226 km)',
      'zeit': 'Zeitrennen (6 h, 12 h, 24 h …)'
    },
    en: {
      '5k': '5 km', '10k': '10 km', 'half': 'Half Marathon', 'marathon': 'Marathon', 'ultra': 'Ultramarathon',
      'r50': 'up to 50 km', 'r100': '50–100 km', 'r150': '100–150 km', 'r200': '150–200 km', 'rultra': '200+ km',
      's1': '1 km', 's2': '2 km', 's3': '3 km', 's5': '5 km', 's10': '10+ km (marathon swim)',
      'sprint': 'Sprint Distance', 'olympic': 'Olympic Distance (51.5 km)',
      'middle': 'Middle Distance / 70.3 (113 km)', 'long': 'Long Distance / Ironman (226 km)',
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

  function clearFilters(state) {
    state.land.clear();
    state.art1.clear();
    state.art2.clear();
    state.standort.clear();
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
      || state.nameQuery.trim() || state.selectedDays.size
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
      if (e.laenge_km == null) continue;
      if (cat.test(e.laenge_km)) return true;
    }
    return false;
  }

  // Trifft ein einzelnes Event alle aktiven Filter? Die Liste und die
  // Karte fragen dieselbe Funktion - sonst zeigte ein Kartenmarker
  // Events, die in der Liste herausgefiltert sind.
  function matchEvent(state, e) {
    if (state.land.size && !state.land.has(e.land)) return false;
    if (state.art1.size && !state.art1.has(e.art1)) return false;
    if (state.art2.size && !state.art2.has(e.art2)) return false;
    if (state.standort.size && !state.standort.has(e.standort)) return false;
    // Die Suche greift auch auf die Wettbewerbsbezeichnung zu, damit
    // z. B. "Halbmarathon" die Halbmarathon-Strecke einer Veranstaltung
    // findet, die diesen Begriff nicht im Namen trägt.
    if (state.nameQuery.trim()) {
      const needle = state.nameQuery.trim().toLowerCase();
      const haystack = `${e.name || ''} ${e.wettbewerb || ''}`.toLowerCase();
      if (!haystack.includes(needle)) return false;
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
    if (state.nameQuery.trim()) chips.push({ label: t('chip_name', state.nameQuery.trim()), clear: () => { state.nameQuery = ''; } });
    if (state.selectedDays.size > 0) {
      // Sind alle vorhandenen Termine ausgewählt, ist "Datum: Alle"
      // aussagekräftiger als "Datum: 812 Tage ausgewählt" - gleiche
      // Logik wie bei den Mengen-Filtern.
      const alleTage = ctx.dayCount || 0;
      const preset = DATE_PRESETS.find(x => x.key === state.datePreset);
      const label = preset
        ? t('chip_datum_preset', t(preset.labelKey))
        : alleTage > 0 && state.selectedDays.size >= alleTage
          ? t('chip_datum_all')
          : t('chip_datum', state.selectedDays.size);
      chips.push({ label, clear: () => { state.selectedDays.clear(); state.datePreset = null; } });
    }

    function pushSetChips(stateKey, chipKey, format) {
      const selected = state[stateKey];
      if (selected.size === 0) return;
      const optionCount = ctx.optionCount ? ctx.optionCount(stateKey) : 0;
      if (optionCount > 0 && selected.size >= optionCount) {
        chips.push({ label: t(chipKey, t('chip_value_all')), clear: () => selected.clear() });
        return;
      }
      if (selected.size > MAX_VALUE_CHIPS) {
        chips.push({
          label: t(chipKey, t('chip_value_count', selected.size)),
          clear: () => selected.clear()
        });
        return;
      }
      selected.forEach(v => chips.push({ label: t(chipKey, format(v)), clear: () => selected.delete(v) }));
    }
    pushSetChips('land', 'chip_land', v => tv('land', v));
    pushSetChips('standort', 'chip_standort', v => v);
    pushSetChips('art1', 'chip_sportart', v => tv('art1', v));
    pushSetChips('art2', 'chip_kategorie', v => tv('art2', v));

    if (state.laengeMin !== '') chips.push({ label: t('chip_laenge_ab', state.laengeMin), clear: () => { state.laengeMin = ''; } });
    if (state.laengeMax !== '') chips.push({ label: t('chip_laenge_bis', state.laengeMax), clear: () => { state.laengeMax = ''; } });
    if (state.distanceCategories.size > MAX_VALUE_CHIPS) {
      chips.push({
        label: t('chip_distanz_count', state.distanceCategories.size),
        clear: () => state.distanceCategories.clear()
      });
    } else state.distanceCategories.forEach(compositeKey => {
      const sep = compositeKey.indexOf(':');
      const sport = compositeKey.slice(0, sep);
      const catKey = compositeKey.slice(sep + 1);
      const label = DISTANCE_CATEGORY_LABELS[ctx.lang][catKey] || catKey;
      chips.push({ label: t('chip_distanz', tv('art1', sport), label), clear: () => state.distanceCategories.delete(compositeKey) });
    });
    if (state.origin && state.radiusKm != null) {
      // Das Kreuz am Chip entfernt den Ausgangspunkt gleich mit: ein
      // Ausgangspunkt ohne Umkreis filtert nichts und stünde nur noch
      // unsichtbar im Panel.
      chips.push({
        label: t('chip_umkreis', state.radiusKm, state.origin.label),
        clear: () => { (ctx.setOrigin || setOriginPlain)(state, null); }
      });
    }
    return chips;
  }

  global.EnduranceFilters = {
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
    uniqueSorted,
    formatDate,
    isoOf,
    todayIso,
    createState,
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

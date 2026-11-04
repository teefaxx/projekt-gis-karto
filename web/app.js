/* global maplibregl */
// Interaktive Karte «Bundesbeschluss Velo 2018»
// Daten: web/data/*, erzeugt mit `python -m pipeline webdata`
// Gemeindegrenzen: swissBOUNDARIES3D, Seen: swissTLM3D (beide swisstopo) als Vektorkacheln.
// Hintergrund: swisstopo Basiskarte (Vektor) bzw. WMTS-Rasterkarten.

const COLORS = {
  2: '#1f9a4c',
  1: '#d9a3e2',
  0: '#a6db9c',
  '-1': '#983aa8',
  '-7': '#c7e0f5', // Seefläche (Kantonsgebiet)
  '-8': '#ececec', // Kommunanz
  '-9': '#d4d4d4', // keine Daten
};
const WATER = '#c7e0f5';
const ORANGE = '#f8a51b';

const CLASS_TEXT = {
  2: ['Überdurchschnittlich viele Velowege', 'überdurchschnittlich viele Ja-Stimmen'],
  1: ['Überdurchschnittlich viele Velowege', 'unterdurchschnittlich viele Ja-Stimmen'],
  0: ['Unterdurchschnittlich viele Velowege', 'überdurchschnittlich viele Ja-Stimmen'],
  '-1': ['Unterdurchschnittlich viele Velowege', 'unterdurchschnittlich viele Ja-Stimmen'],
};

const MOBILE = window.innerWidth <= 760;
const CANTON_SIZES = [26, 32, 40, 50].map((s) => Math.round(s * (MOBILE ? 0.7 : 1))); // Durchmesser px
const CH_BOUNDS = [[5.956, 45.818], [10.492, 47.808]];
const SWISSTOPO_STYLE = 'https://vectortiles.geo.admin.ch/styles/ch.swisstopo.lightbasemap.vt/style.json';
const WMTS = (layer) => `https://wmts.geo.admin.ch/1.0.0/${layer}/default/current/3857/{z}/{x}/{y}.jpeg`;
const RASTERS = {
  farbe: WMTS('ch.swisstopo.pixelkarte-farbe'),
  grau: WMTS('ch.swisstopo.pixelkarte-grau'),
  luftbild: WMTS('ch.swisstopo.swissimage'),
};
// Diese Layer der swisstopo-Basiskarte bleiben im Modus «Ohne» sichtbar
const WATER_LAYERS = ['water', 'water_outline', 'water_line', 'water_line_intermittent'];

// Quellenangaben in der Detailansicht
const link = (href, text) => `<a href="${href}" target="_blank" rel="noopener">${text}</a>`;
const SRC = {
  vote: link('https://www.bfs.admin.ch/bfs/de/home/statistiken/politik/abstimmungen.html', 'BFS, Volksabstimmung vom 23.09.2018'),
  bikes: `${link('https://www.openstreetmap.org/copyright', 'OpenStreetMap')} (Velowege 2023, Strassennetz) und ${link('https://www.schweizmobil.ch/de/veloland', 'Veloland Schweiz')}`,
  reference: link('https://www.prixvelo.ch/de/prix-velo-infrastruktur', 'Mittel der Prix-Velo-Städte'),
  accidents: link('https://data.geo.admin.ch/browser/index.html#/collections/ch.astra.unfaelle-personenschaeden_alle', 'ASTRA, Strassenverkehrsunfälle mit Personenschaden'),
  popBFS: link('https://www.bfs.admin.ch/bfs/de/home/statistiken/bevoelkerung/stand-entwicklung.html', 'BFS STATPOP, Stand 1.1.2021'),
  popSB3D: link('https://www.swisstopo.admin.ch/de/landschaftsmodell-swissboundaries3d', 'swisstopo swissBOUNDARIES3D 2023 (Gemeinde nach 2021 fusioniert)'),
  boundaries: link('https://www.swisstopo.admin.ch/de/landschaftsmodell-swissboundaries3d', 'swisstopo swissBOUNDARIES3D, Stand 1.1.2023'),
};
const source = (label, html) => `<p class="src"><span>${label}:</span> ${html}</p>`;

const fmt = new Intl.NumberFormat('de-CH');
const fmt1 = new Intl.NumberFormat('de-CH', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const fmt2 = new Intl.NumberFormat('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const pct = (v, f = fmt1) => (v == null ? '–' : `${f.format(v)} %`);
const num = (v) => (v == null ? '–' : fmt.format(v));

const $ = (sel) => document.querySelector(sel);
const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const absolute = (path) => new URL(path, document.baseURI).href;

// ---------------------------------------------------------------------------
// Daten laden
// ---------------------------------------------------------------------------
const load = (url) => fetch(url).then((r) => {
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
});

const [gemeinden, kantone, kantonePunkte, meta, baseStyle] = await Promise.all([
  load('data/gemeinden.json'),
  load('data/kantone.json'),
  load('data/kantone_punkte.geojson'),
  load('data/meta.json'),
  load(SWISSTOPO_STYLE),
]);

const byId = new Map(gemeinden.map((g) => [g.id, g]));
const cantonById = new Map(kantone.map((k) => [k.id, k]));

document.querySelectorAll('[data-meta]').forEach((el) => {
  const v = meta[el.dataset.meta];
  el.textContent = pct(v, Number.isInteger(v) ? fmt : fmt2);
});

const counts = {};
gemeinden.forEach((g) => { counts[g.cls] = (counts[g.cls] || 0) + 1; });
document.querySelectorAll('.sw').forEach((b) => {
  b.querySelector('.n').textContent = `${num(counts[b.dataset.cls] || 0)} Gem.`;
});

$('#circle-legend').innerHTML = meta.accLabels.map((label, i) => {
  const s = CANTON_SIZES[i];
  return `<li><span class="dot" style="width:${s}px;height:${s}px"></span><span>${label}</span></li>`;
}).join('');

// ---------------------------------------------------------------------------
// Kartenstil: swisstopo-Basiskarte + eigene Layer unterhalb der Gewässer
// ---------------------------------------------------------------------------
const colorExpr = ['match', ['get', 'cls'],
  2, COLORS[2], 1, COLORS[1], 0, COLORS[0], -1, COLORS['-1'],
  -7, COLORS['-7'], -8, COLORS['-8'], COLORS['-9']];
const state = (key) => ['boolean', ['feature-state', key], false];
const src = (layer) => ({ source: 'data', 'source-layer': layer });

const dataLayers = [
  { id: 'gemeinden-fill', type: 'fill', ...src('gemeinden'), paint: { 'fill-color': colorExpr } },
  { id: 'seen-fill', type: 'fill', ...src('seen'), paint: { 'fill-color': WATER } },
  {
    id: 'gemeinden-line',
    type: 'line',
    ...src('gemeinden'),
    filter: ['!=', ['get', 'cls'], -7],
    paint: {
      'line-color': '#3a1f40',
      'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.25, 10, 0.8, 14, 1.6],
    },
  },
  {
    id: 'kantone-fill',
    type: 'fill',
    ...src('kantone_flaechen'),
    paint: {
      'fill-color': '#1d1720',
      'fill-opacity': ['case', state('selected'), 0, state('hover'), 0.1, 0],
    },
  },
  {
    id: 'kantone-line',
    type: 'line',
    ...src('kantone'),
    layout: { 'line-join': 'round', 'line-cap': 'round' },
    paint: { 'line-color': '#1d1720', 'line-opacity': 0.55 },
  },
  {
    id: 'gemeinden-hover',
    type: 'line',
    ...src('gemeinden'),
    paint: { 'line-color': '#1d1720', 'line-width': ['case', state('hover'), 1.6, 0] },
  },
  {
    id: 'gemeinden-selected',
    type: 'line',
    ...src('gemeinden'),
    layout: { 'line-join': 'round' },
    paint: { 'line-color': '#e3262b', 'line-width': ['case', state('selected'), 3, 0] },
  },
  {
    id: 'kantone-selected',
    type: 'line',
    ...src('kantone_flaechen'),
    layout: { 'line-join': 'round' },
    paint: {
      'line-color': '#e3262b',
      'line-width': ['case', state('selected'), 3.5, state('hover'), 0, 0],
    },
  },
];

const topLayers = [
  {
    id: 'gemeinden-label',
    type: 'symbol',
    ...src('labels'),
    minzoom: 10,
    layout: {
      'text-field': ['get', 'name'],
      'text-font': ['Frutiger Neue Condensed Medium'],
      'text-size': ['interpolate', ['linear'], ['zoom'], 10, 12, 14, 16],
      'text-max-width': 8,
      'text-padding': 4,
    },
    paint: { 'text-color': '#1d1720', 'text-halo-color': 'rgba(255,255,255,.9)', 'text-halo-width': 1.4 },
  },
  // Kantonssymbole als Kartenlayer: bewegen sich ohne Verzögerung mit der Karte
  {
    id: 'kantone-kreise',
    type: 'circle',
    source: 'kantone-punkte',
    paint: {
      // Radius = halber Durchmesser je Unfallklasse
      'circle-radius': ['match', ['get', 'accClass'],
        0, CANTON_SIZES[0] / 2, 1, CANTON_SIZES[1] / 2, 2, CANTON_SIZES[2] / 2, CANTON_SIZES[3] / 2],
      'circle-color': ORANGE,
      'circle-stroke-color': ['case', state('selected'), '#e3262b', '#b06a00'],
      'circle-stroke-width': ['case', state('selected'), 3, state('hover'), 2.5, 1.5],
      'circle-pitch-alignment': 'map',
    },
  },
  {
    id: 'kantone-kuerzel',
    type: 'symbol',
    source: 'kantone-punkte',
    layout: {
      'text-field': ['get', 'abbr'],
      'text-font': ['Frutiger Neue Condensed Bold'],
      'text-size': ['match', ['get', 'accClass'], 0, CANTON_SIZES[0] * 0.42, 1, CANTON_SIZES[1] * 0.42, 2, CANTON_SIZES[2] * 0.42, CANTON_SIZES[3] * 0.42],
      'text-allow-overlap': true,
      'text-ignore-placement': true,
    },
    paint: { 'text-color': '#1d1720' },
  },
];

function buildStyle() {
  const style = structuredClone(baseStyle);
  style.sources.data = {
    type: 'vector',
    tiles: [`${absolute('data/tiles/')}{z}/{x}/{y}.pbf`],
    minzoom: 5,
    maxzoom: meta.maxTileZoom,
    bounds: [5.9, 45.8, 10.5, 47.85],
    attribution: '© <a href="https://www.swisstopo.admin.ch/">swisstopo</a> swissBOUNDARIES3D, swissTLM3D',
  };
  style.sources['kantone-punkte'] = { type: 'geojson', data: kantonePunkte, promoteId: 'kt' };
  Object.entries(RASTERS).forEach(([key, url]) => {
    style.sources[`raster-${key}`] = { type: 'raster', tiles: [url], tileSize: 256, maxzoom: 19 };
  });

  const layers = [];
  for (const layer of style.layers) {
    if (layer.id === 'water_line_intermittent') layers.push(...dataLayers);
    layers.push(layer);
    if (layer.id === 'background') {
      Object.keys(RASTERS).forEach((key) => layers.push({
        id: `raster-${key}`, type: 'raster', source: `raster-${key}`, layout: { visibility: 'none' },
      }));
    }
  }
  if (!layers.some((l) => l.id === 'gemeinden-fill')) layers.push(...dataLayers);
  layers.push(...topLayers);
  style.layers = layers;
  return style;
}

const baseLayerIds = baseStyle.layers.map((l) => l.id);
const originalBackground = baseStyle.layers.find((l) => l.id === 'background')?.paint?.['background-color'] ?? '#fcfcfc';

// ---------------------------------------------------------------------------
// Karte
// ---------------------------------------------------------------------------
const map = new maplibregl.Map({
  container: 'map',
  style: buildStyle(),
  bounds: CH_BOUNDS,
  fitBoundsOptions: { padding: framePadding() },
  maxBounds: [[0.5, 42.5], [16.5, 51]],
  minZoom: 5,
  maxZoom: 17,
  dragRotate: false,
  pitchWithRotate: false,
  attributionControl: false,
});

map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
map.addControl(new maplibregl.FullscreenControl(), 'top-right');
map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: 'metric' }), 'bottom-right');
map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');

function framePadding() {
  if (MOBILE) return { top: 90, bottom: 80, left: 10, right: 10 };
  return { top: 40, bottom: 50, left: Math.min(280, window.innerWidth * 0.2), right: 340 };
}

const ui = { view: 'gemeinden', basemap: 'none' };
const activeClasses = new Set([2, 1, 0, -1, -7, -8, -9]);
const hovered = { gemeinden: null, kantone: null, kreise: null };
let selection = null; // { type: 'gemeinde' | 'kanton', id }

const REF = {
  gemeinden: (id) => ({ source: 'data', sourceLayer: 'gemeinden', id }),
  kantone: (id) => ({ source: 'data', sourceLayer: 'kantone_flaechen', id }),
  kreise: (id) => ({ source: 'kantone-punkte', id }),
};

map.on('load', () => {
  applyStyleState();
  bindMapEvents();
  readHash();
});

// ---------------------------------------------------------------------------
// Darstellung je nach Hintergrund und Ansicht
// ---------------------------------------------------------------------------
function applyStyleState() {
  const { basemap, view } = ui;
  const vectorOn = basemap === 'light';
  const plain = basemap === 'none';

  baseLayerIds.forEach((id) => {
    if (id === 'background') return;
    // Ohne Basiskarte: nur Gewässer. Rasterkarten: keine Vektorlayer, Seen bleiben transparent.
    const show = vectorOn || (plain && WATER_LAYERS.includes(id));
    map.setLayoutProperty(id, 'visibility', show ? 'visible' : 'none');
  });
  Object.keys(RASTERS).forEach((key) => {
    map.setLayoutProperty(`raster-${key}`, 'visibility', key === basemap ? 'visible' : 'none');
  });
  map.setPaintProperty('background', 'background-color', plain ? '#ffffff' : originalBackground);

  // Seeflächen nur ohne Basiskarte füllen, sonst sieht man die Seen der Basiskarte
  map.setLayoutProperty('seen-fill', 'visibility', plain ? 'visible' : 'none');
  map.setFilter('gemeinden-fill', ['all',
    ['in', ['get', 'cls'], ['literal', [...activeClasses]]],
    plain ? true : ['!=', ['get', 'cls'], -7]]);

  const cantonView = view === 'kantone';
  const base = { none: 1, light: 0.6, farbe: 0.55, grau: 0.6, luftbild: 0.5 }[basemap];
  const fillOpacity = cantonView ? base * 0.3 : base;
  map.setPaintProperty('gemeinden-fill', 'fill-opacity',
    ['case', state('hover'), cantonView ? fillOpacity : Math.max(0.3, base - 0.25), fillOpacity]);
  map.setPaintProperty('gemeinden-line', 'line-opacity',
    cantonView ? 0.15 : ['interpolate', ['linear'], ['zoom'], 6, 0.35, 10, 0.6]);
  map.setPaintProperty('kantone-line', 'line-width', cantonView
    ? ['interpolate', ['linear'], ['zoom'], 6, 1.6, 10, 3, 14, 4.5]
    : ['interpolate', ['linear'], ['zoom'], 6, 0.9, 10, 2.2, 14, 3.5]);
  map.setPaintProperty('kantone-line', 'line-opacity', cantonView ? 0.8 : 0.55);
  map.setLayoutProperty('kantone-line', 'visibility', cantonView || $('#tg-borders').checked ? 'visible' : 'none');
  map.setLayoutProperty('kantone-fill', 'visibility', cantonView ? 'visible' : 'none');
  map.setLayoutProperty('gemeinden-label', 'visibility',
    !cantonView && basemap !== 'light' && $('#tg-labels').checked ? 'visible' : 'none');
  const circles = $('#tg-cantons-pts').checked ? 'visible' : 'none';
  map.setLayoutProperty('kantone-kreise', 'visibility', circles);
  map.setLayoutProperty('kantone-kuerzel', 'visibility', circles);

  document.body.dataset.basemap = basemap;
  document.body.dataset.view = view;
}

function setView(view) {
  if (ui.view === view) return;
  ui.view = view;
  document.querySelectorAll('input[name="view"]').forEach((i) => { i.checked = i.value === view; });
  clearHover();
  hideTooltip();
  if (view === 'gemeinden' && selection?.type === 'kanton') select(null);
  if (view === 'kantone' && selection?.type === 'gemeinde') {
    select({ type: 'kanton', id: byId.get(selection.id).kt });
  }
  applyStyleState();
}

document.querySelectorAll('input[name="basemap"]').forEach((input) => {
  input.addEventListener('change', () => { if (input.checked) { ui.basemap = input.value; applyStyleState(); } });
});
document.querySelectorAll('input[name="view"]').forEach((input) => {
  input.addEventListener('change', () => { if (input.checked) setView(input.value); });
});

// ---------------------------------------------------------------------------
// Hover, Tooltip und Auswahl
// ---------------------------------------------------------------------------
const tooltip = $('#tooltip');
const hideTooltip = () => { tooltip.hidden = true; };
const canHover = window.matchMedia('(hover: hover)').matches;

function setHover(kind, id) {
  if (hovered[kind] === id) return;
  if (hovered[kind] != null) map.setFeatureState(REF[kind](hovered[kind]), { hover: false });
  hovered[kind] = id;
  if (id != null) map.setFeatureState(REF[kind](id), { hover: true });
}
function clearHover() { Object.keys(hovered).forEach((k) => setHover(k, null)); }

function showTooltip(e, html) {
  if (!canHover) return;
  tooltip.innerHTML = html;
  tooltip.style.left = `${e.originalEvent.clientX}px`;
  tooltip.style.top = `${e.originalEvent.clientY}px`;
  tooltip.hidden = false;
}

const cantonTooltip = (k) => `<b>Kanton ${escapeHtml(k.name)}</b><br>
  Ja ${pct(k.yes)} <span>·</span> Velowege ${pct(k.bike, fmt2)} <span>·</span> ${fmt.format(Math.round(k.acc100k))} Unfälle/100k`;

// Welches Objekt liegt unter dem Mauszeiger? Kreise haben Vorrang.
function pick(point) {
  const circle = map.queryRenderedFeatures(point, { layers: ['kantone-kreise'] })[0];
  if (circle) return { type: 'kreis', id: circle.id };
  if (ui.view === 'kantone') {
    const c = map.queryRenderedFeatures(point, { layers: ['kantone-fill'] })[0];
    return c && cantonById.has(c.id) ? { type: 'kanton', id: c.id } : null;
  }
  const g = map.queryRenderedFeatures(point, { layers: ['gemeinden-fill'] }).find((f) => byId.has(f.id));
  return g ? { type: 'gemeinde', id: g.id } : null;
}

function bindMapEvents() {
  map.on('mousemove', (e) => {
    const hit = pick(e.point);
    setHover('kreise', hit?.type === 'kreis' ? hit.id : null);
    setHover('kantone', hit?.type === 'kanton' || (hit?.type === 'kreis' && ui.view === 'kantone') ? hit.id : null);
    setHover('gemeinden', hit?.type === 'gemeinde' ? hit.id : null);
    map.getCanvas().style.cursor = hit ? 'pointer' : '';
    if (!hit) { hideTooltip(); return; }

    if (hit.type === 'gemeinde') {
      const g = byId.get(hit.id);
      showTooltip(e, g.yes === undefined
        ? `<b>${escapeHtml(g.name)}</b> <span>${meta.cantonNames[g.kt]}</span><br><span>kein Gemeindegebiet</span>`
        : `<b>${escapeHtml(g.name)}</b> <span>${meta.cantonNames[g.kt]}</span><br>
          Ja ${pct(g.yes)} <span>·</span> Velowege ${pct(g.bike, fmt2)}`);
    } else {
      showTooltip(e, cantonTooltip(cantonById.get(hit.id)));
    }
  });
  map.on('mouseout', () => { clearHover(); hideTooltip(); });
  map.on('click', (e) => {
    const hit = pick(e.point);
    if (!hit) { select(null); return; }
    if (hit.type === 'kreis') {
      setView('kantone');
      select({ type: 'kanton', id: hit.id }, { fly: true });
    } else {
      select(hit);
    }
  });
  map.on('movestart', hideTooltip);
}

function setSelected(sel, on) {
  if (!sel) return;
  if (sel.type === 'gemeinde') map.setFeatureState(REF.gemeinden(sel.id), { selected: on });
  else {
    map.setFeatureState(REF.kantone(sel.id), { selected: on });
    map.setFeatureState(REF.kreise(sel.id), { selected: on });
  }
}

function showInfo() {
  $('#info').hidden = false;
  $('#info').scrollTop = 0;
  document.body.classList.add('has-info');
}

function select(sel, { fly = false } = {}) {
  setSelected(selection, false);
  selection = sel;
  if (!sel) {
    $('#info').hidden = true;
    document.body.classList.remove('has-info');
    history.replaceState(null, '', location.pathname + location.search);
    return;
  }
  const item = sel.type === 'gemeinde' ? byId.get(sel.id) : cantonById.get(sel.id);
  if (!item) { selection = null; return; }
  setSelected(sel, true);
  if (sel.type === 'gemeinde') renderMunicipality(item); else renderCanton(item);
  history.replaceState(null, '', `#${sel.type}=${sel.id}`);
  if (fly) {
    const pad = framePadding();
    const [w, s, e, n] = item.bbox;
    map.fitBounds([[w, s], [e, n]], {
      padding: { ...pad, bottom: MOBILE ? window.innerHeight * 0.6 : pad.bottom },
      maxZoom: sel.type === 'kanton' ? 10 : (MOBILE ? 11 : 12),
      duration: 900,
    });
  }
}

// ---------------------------------------------------------------------------
// Detailansicht
// ---------------------------------------------------------------------------
function bar(value, max, color, marks) {
  const w = Math.max(0, Math.min(100, (value / max) * 100));
  const m = marks.map(({ v, label, alt }) => `<span class="mark${alt ? ' alt' : ''}" style="left:${(v / max) * 100}%"><span>${label}</span></span>`).join('');
  return `<div class="bar" style="--c:${color}"><span class="fill" style="width:${w}%"></span>${m}</div>`;
}

const yesMarks = (withAverage) => [
  ...(withAverage ? [{ v: meta.yesThreshold, label: `Ø Gemeinden ${fmt.format(meta.yesThreshold)} %` }] : []),
  { v: meta.nationalYes, label: `CH ${fmt1.format(meta.nationalYes)} %`, alt: withAverage },
];

function bikeBlock(p) {
  const bikeColor = p.bike >= meta.bikeThreshold ? COLORS[2] : COLORS['-1'];
  const bikeMax = Math.max(15, Math.ceil(((p.bike ?? 0) + 1) / 5) * 5);
  return `
    <div class="metric">
      <div class="metric-top"><span class="metric-label">Anteil Velowege am Strassennetz</span><span class="metric-value">${pct(p.bike, fmt2)}</span></div>
      ${p.bike == null ? '' : bar(p.bike, bikeMax, bikeColor, [{ v: meta.bikeThreshold, label: `Referenz ${fmt2.format(meta.bikeThreshold)} %` }])}
      <div class="metric-sub">${p.bike_km ? `${fmt1.format(p.bike_km)} km Velowege` : 'Keine Velowege erfasst'}${p.street_km != null ? ` · ${fmt.format(Math.round(p.street_km))} km Strassennetz` : ''}</div>
      ${source('Quellen', `${SRC.bikes}; Referenzwert: ${SRC.reference}`)}
    </div>`;
}

function accidentBlock(p, note, popSource) {
  return `
    <div class="metric">
      <div class="metric-top"><span class="metric-label">Velounfälle</span><span class="metric-sub">${meta.accidentPeriod}</span></div>
      <div class="stats">
        <div><b>${num(p.acc)}</b><span>Unfälle</span></div>
        <div><b>${p.acc100k == null ? '–' : fmt.format(Math.round(p.acc100k))}</b><span>pro 100'000 EW</span></div>
        <div><b>${num(p.pop)}</b><span>Einwohner</span></div>
      </div>
      <p class="note">${note}</p>
      ${source('Quellen', `Unfälle: ${SRC.accidents}; Einwohner: ${popSource}`)}
    </div>`;
}

function renderMunicipality(p) {
  const canton = cantonById.get(p.kt);
  const head = `
    <div class="info-head">
      <h3>${escapeHtml(p.name)}</h3>
      <button class="kt link" data-canton="${p.kt}">${escapeHtml(canton.name)} (${canton.abbr})</button>
      <span class="kt">BFS-Nr. ${p.id}</span>
    </div>`;

  if (p.yes === undefined) {
    $('#info-body').innerHTML = `${head}
      <div class="badge" style="--c:${COLORS[p.cls]}"><i></i><span><b>Kein Gemeindegebiet</b>,
      gemeinsam verwaltete Fläche (Kommunanz bzw. Staatswald)</span></div>`;
  } else {
    const noVote = p.yes == null;
    const [t1, t2] = CLASS_TEXT[p.cls]
      || ['Keine eigenen Abstimmungsdaten', `gemeinsame Urne${p.urne ? ` mit ${escapeHtml(p.urne)}` : ''}`];
    const yesColor = p.yes >= meta.yesThreshold ? COLORS[2] : COLORS['-1'];
    $('#info-body').innerHTML = `${head}
      <div class="badge" style="--c:${COLORS[p.cls]}"><i></i><span><b>${t1}</b>, ${t2}</span></div>
      <div class="metric">
        <div class="metric-top"><span class="metric-label">Ja-Stimmen</span><span class="metric-value">${noVote ? 'keine Daten' : pct(p.yes)}</span></div>
        ${noVote ? '' : bar(p.yes, 100, yesColor, yesMarks(true))}
        <div class="metric-sub">${noVote ? `Die Stimmen wurden ${p.urne ? `in ${escapeHtml(p.urne)} ` : ''}gemeinsam ausgezählt.`
          : `${num(p.ja)} Ja · ${num(p.nein)} Nein · Stimmbeteiligung ${pct(p.turnout)}`}</div>
        ${source('Quelle', SRC.vote)}
      </div>
      ${bikeBlock(p)}
      ${accidentBlock(p, `Kanton ${canton.abbr}: ${fmt1.format(canton.acc100k)} Unfälle pro 100'000 EW.
        Polizeilich registrierte Unfälle mit Velobeteiligung.`, p.pop_src === 'swissBOUNDARIES3D' ? SRC.popSB3D : SRC.popBFS)}
      ${source('Gemeindegrenze', SRC.boundaries)}`;
  }
  $('#info-body').querySelector('[data-canton]')?.addEventListener('click', () => {
    setView('kantone');
    select({ type: 'kanton', id: p.kt }, { fly: true });
  });
  showInfo();
}

function renderCanton(k) {
  const order = [2, 1, 0, -1, -9];
  const total = order.reduce((s, c) => s + (k.classes[c] || 0), 0);
  const segments = order.filter((c) => k.classes[c]).map((c) => {
    const n = k.classes[c];
    return `<span style="--c:${COLORS[c]};flex:${n}" title="${n} Gemeinden"></span>`;
  }).join('');
  const legend = order.filter((c) => k.classes[c]).map((c) => `<li><i style="--c:${COLORS[c]}"></i>${k.classes[c]}</li>`).join('');
  const yesColor = k.yes >= meta.nationalYes ? COLORS[2] : COLORS['-1'];

  $('#info-body').innerHTML = `
    <div class="info-head">
      <h3>${escapeHtml(k.name)}</h3>
      <span class="kt">Kanton ${k.abbr} · ${k.municipalities} Gemeinden</span>
    </div>
    <div class="badge" style="--c:${ORANGE}"><i class="round"></i><span><b>Rang ${k.rank} von 26</b> bei den Velounfällen
      pro 100'000 Einwohner</span></div>

    <div class="metric">
      <div class="metric-top"><span class="metric-label">Ja-Stimmen</span><span class="metric-value">${pct(k.yes)}</span></div>
      ${bar(k.yes, 100, yesColor, yesMarks(false))}
      <div class="metric-sub">${num(k.ja)} Ja · ${num(k.nein)} Nein · Stimmbeteiligung ${pct(k.turnout)}<br>
        Summe der Gemeinden (ohne Auslandschweizer)</div>
      ${source('Quelle', SRC.vote)}
    </div>
    ${bikeBlock(k)}
    ${accidentBlock(k, 'Unfälle des Kantons ÷ Einwohner des Kantons. Polizeilich registrierte Unfälle mit Velobeteiligung.', `${SRC.popBFS}, ergänzt aus swissBOUNDARIES3D`)}

    <div class="metric">
      <div class="metric-top"><span class="metric-label">Gemeinden nach Klasse</span><span class="metric-sub">${total} Gemeinden</span></div>
      <div class="stack">${segments}</div>
      <ul class="stack-legend">${legend}</ul>
    </div>`;
  showInfo();
}

$('#info-close').addEventListener('click', () => select(null));
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') select(null); });

function readHash() {
  const g = location.hash.match(/gemeinde=(\d+)/);
  const k = location.hash.match(/kanton=(\d+)/);
  if (g) { setView('gemeinden'); select({ type: 'gemeinde', id: Number(g[1]) }, { fly: true }); }
  if (k) { setView('kantone'); select({ type: 'kanton', id: Number(k[1]) }, { fly: true }); }
}
window.addEventListener('hashchange', readHash);

document.querySelectorAll('[data-goto]').forEach((b) => {
  b.addEventListener('click', () => { setView('gemeinden'); select({ type: 'gemeinde', id: Number(b.dataset.goto) }, { fly: true }); });
});

// ---------------------------------------------------------------------------
// Legende: Klassen filtern, Ebenen schalten
// ---------------------------------------------------------------------------
document.querySelectorAll('.sw').forEach((b) => {
  b.addEventListener('click', () => {
    const cls = Number(b.dataset.cls);
    if (activeClasses.has(cls)) activeClasses.delete(cls); else activeClasses.add(cls);
    b.setAttribute('aria-pressed', String(activeClasses.has(cls)));
    applyStyleState();
  });
});
['#tg-cantons-pts', '#tg-borders', '#tg-labels'].forEach((sel) => $(sel).addEventListener('change', applyStyleState));

const legendToggle = $('#legend-toggle');
legendToggle.addEventListener('click', () => {
  const open = legendToggle.getAttribute('aria-expanded') !== 'true';
  legendToggle.setAttribute('aria-expanded', String(open));
  $('#legend-body').hidden = !open;
});
if (MOBILE) legendToggle.click();

// ---------------------------------------------------------------------------
// Suche (Gemeinden und Kantone)
// ---------------------------------------------------------------------------
const normalize = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const index = [
  ...kantone.map((k) => ({ type: 'kanton', id: k.id, name: k.name, label: 'Kanton', color: ORANGE, keys: [normalize(k.name), normalize(k.abbr)] })),
  ...gemeinden.filter((g) => g.yes !== undefined).map((g) => ({
    type: 'gemeinde', id: g.id, name: g.name, label: meta.cantonNames[g.kt], color: COLORS[g.cls], keys: [normalize(g.name)],
  })),
].sort((a, b) => a.name.localeCompare(b.name, 'de'));

const input = $('#search');
const results = $('#search-results');
let hits = [];
let cursor = -1;

function renderResults() {
  const q = normalize(input.value.trim());
  if (!q) { results.hidden = true; input.setAttribute('aria-expanded', 'false'); return; }
  const starts = index.filter((d) => d.keys.some((k) => k.startsWith(q)));
  const contains = index.filter((d) => !starts.includes(d) && d.keys.some((k) => k.includes(q)));
  hits = [...starts.filter((d) => d.type === 'kanton'), ...starts.filter((d) => d.type !== 'kanton'), ...contains].slice(0, 8);
  cursor = hits.length ? 0 : -1;
  results.innerHTML = hits.length
    ? hits.map((d, i) => `<li role="option" data-i="${i}" aria-selected="${i === cursor}" style="--c:${d.color}">
        <i class="${d.type === 'kanton' ? 'round' : ''}"></i>${escapeHtml(d.name)}<small>${d.label}</small></li>`).join('')
    : '<li class="empty">Nichts gefunden</li>';
  results.hidden = false;
  input.setAttribute('aria-expanded', 'true');
}

function choose(d) {
  results.hidden = true;
  input.setAttribute('aria-expanded', 'false');
  input.value = d.name;
  input.blur();
  setView(d.type === 'kanton' ? 'kantone' : 'gemeinden');
  select({ type: d.type, id: d.id }, { fly: true });
}

input.addEventListener('input', renderResults);
input.addEventListener('focus', () => { if (input.value) renderResults(); });
input.addEventListener('keydown', (e) => {
  if (results.hidden || !hits.length) return;
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    cursor = (cursor + (e.key === 'ArrowDown' ? 1 : -1) + hits.length) % hits.length;
    results.querySelectorAll('li').forEach((li, i) => li.setAttribute('aria-selected', String(i === cursor)));
  } else if (e.key === 'Enter' && cursor >= 0) {
    e.preventDefault();
    choose(hits[cursor]);
  } else if (e.key === 'Escape') {
    results.hidden = true;
  }
});
results.addEventListener('mousedown', (e) => {
  const li = e.target.closest('li[data-i]');
  if (li) { e.preventDefault(); choose(hits[Number(li.dataset.i)]); }
});
input.addEventListener('blur', () => setTimeout(() => { results.hidden = true; }, 100));

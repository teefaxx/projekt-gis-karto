/* global maplibregl */
// Interaktive Karte «Bundesbeschluss Velo 2018»
// Daten: web/data/*, erzeugt mit `python -m pipeline webdata`
// Gemeindegrenzen: swissBOUNDARIES3D (swisstopo) als Vektorkacheln,
// Hintergrund und Gewässer: swisstopo Basiskarte (Vektor) bzw. WMTS-Rasterkarten.

const COLORS = {
  2: '#1f9a4c',
  1: '#d9a3e2',
  0: '#a6db9c',
  '-1': '#983aa8',
  '-7': '#c7e0f5', // Seefläche
  '-8': '#ececec', // Kommunanz
  '-9': '#d4d4d4', // keine Daten
};

const CLASS_TEXT = {
  2: ['Überdurchschnittlich viele Velowege', 'überdurchschnittlich viele Ja-Stimmen'],
  1: ['Überdurchschnittlich viele Velowege', 'unterdurchschnittlich viele Ja-Stimmen'],
  0: ['Unterdurchschnittlich viele Velowege', 'überdurchschnittlich viele Ja-Stimmen'],
  '-1': ['Unterdurchschnittlich viele Velowege', 'unterdurchschnittlich viele Ja-Stimmen'],
};

const CANTON_SIZES = [26, 32, 40, 50].map((s) => Math.round(s * (window.innerWidth <= 760 ? 0.7 : 1))); // px, je Unfallklasse
const CH_BOUNDS = [[5.956, 45.818], [10.492, 47.808]];
const SWISSTOPO_STYLE = 'https://vectortiles.geo.admin.ch/styles/ch.swisstopo.lightbasemap.vt/style.json';
const WMTS = (layer, ext = 'jpeg') => `https://wmts.geo.admin.ch/1.0.0/${layer}/default/current/3857/{z}/{x}/{y}.${ext}`;
const RASTERS = {
  farbe: WMTS('ch.swisstopo.pixelkarte-farbe'),
  grau: WMTS('ch.swisstopo.pixelkarte-grau'),
  luftbild: WMTS('ch.swisstopo.swissimage'),
};
// Diese Layer der swisstopo-Basiskarte bleiben auch im Modus «Ohne» sichtbar
const WATER_LAYERS = ['water', 'water_outline', 'water_line', 'water_line_intermittent'];

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

const [gemeinden, kantonePunkte, meta, baseStyle] = await Promise.all([
  load('data/gemeinden.json'),
  load('data/kantone_punkte.geojson'),
  load('data/meta.json'),
  load(SWISSTOPO_STYLE),
]);

const byId = new Map(gemeinden.map((g) => [g.id, g]));
const cantonById = new Map(kantonePunkte.features.map((f) => [f.properties.kt, f.properties]));

// Schwellenwerte in die statischen Texte einsetzen
document.querySelectorAll('[data-meta]').forEach((el) => {
  const v = meta[el.dataset.meta];
  el.textContent = pct(v, Number.isInteger(v) ? fmt : fmt2);
});

// Anzahl Gemeinden je Klasse in der Legende
const counts = {};
gemeinden.forEach((g) => { counts[g.cls] = (counts[g.cls] || 0) + 1; });
document.querySelectorAll('.sw').forEach((b) => {
  b.querySelector('.n').textContent = `${num(counts[b.dataset.cls] || 0)} Gem.`;
});

// Kreis-Legende
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

const hoverOpacity = (normal, hover) => ['case', ['boolean', ['feature-state', 'hover'], false], hover, normal];

const dataLayers = [
  {
    id: 'gemeinden-fill',
    type: 'fill',
    source: 'gemeinden',
    'source-layer': 'gemeinden',
    paint: { 'fill-color': colorExpr, 'fill-opacity': hoverOpacity(1, 0.78) },
  },
  {
    id: 'gemeinden-line',
    type: 'line',
    source: 'gemeinden',
    'source-layer': 'gemeinden',
    filter: ['!=', ['get', 'cls'], -7],
    paint: {
      'line-color': '#3a1f40',
      'line-opacity': ['interpolate', ['linear'], ['zoom'], 6, 0.35, 10, 0.6],
      'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.25, 10, 0.8, 14, 1.6],
    },
  },
  {
    id: 'kantone-line',
    type: 'line',
    source: 'gemeinden',
    'source-layer': 'kantone',
    layout: { 'line-join': 'round', 'line-cap': 'round' },
    paint: {
      'line-color': '#1d1720',
      'line-opacity': 0.55,
      'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.9, 10, 2.2, 14, 3.5],
    },
  },
  {
    id: 'gemeinden-hover',
    type: 'line',
    source: 'gemeinden',
    'source-layer': 'gemeinden',
    paint: { 'line-color': '#1d1720', 'line-width': ['case', ['boolean', ['feature-state', 'hover'], false], 1.6, 0] },
  },
  {
    id: 'gemeinden-selected',
    type: 'line',
    source: 'gemeinden',
    'source-layer': 'gemeinden',
    layout: { 'line-join': 'round' },
    paint: { 'line-color': '#e3262b', 'line-width': ['case', ['boolean', ['feature-state', 'selected'], false], 3, 0] },
  },
];

const labelLayer = {
  id: 'gemeinden-label',
  type: 'symbol',
  source: 'gemeinden',
  'source-layer': 'labels',
  minzoom: 10,
  layout: {
    'text-field': ['get', 'name'],
    'text-font': ['Frutiger Neue Condensed Medium'],
    'text-size': ['interpolate', ['linear'], ['zoom'], 10, 12, 14, 16],
    'text-max-width': 8,
    'text-padding': 4,
  },
  paint: { 'text-color': '#1d1720', 'text-halo-color': 'rgba(255,255,255,.9)', 'text-halo-width': 1.4 },
};

function buildStyle() {
  const style = structuredClone(baseStyle);
  style.sources.gemeinden = {
    type: 'vector',
    tiles: [absolute('data/tiles/') + '{z}/{x}/{y}.pbf'],
    minzoom: 5,
    maxzoom: meta.maxTileZoom,
    bounds: [5.9, 45.8, 10.5, 47.85],
    attribution: '© <a href="https://www.swisstopo.admin.ch/de/landschaftsmodell-swissboundaries3d">swisstopo swissBOUNDARIES3D</a>',
  };
  Object.entries(RASTERS).forEach(([key, url]) => {
    style.sources[`raster-${key}`] = {
      type: 'raster', tiles: [url], tileSize: 256, maxzoom: 19, // Attribution: siehe swisstopo-Vektorquelle
    };
  });

  const layers = [];
  for (const layer of style.layers) {
    if (layer.id === 'water_line_intermittent') {
      // eigene Daten direkt unter den Gewässern einfügen
      layers.push(...dataLayers);
    }
    layers.push(layer);
    if (layer.id === 'background') {
      Object.keys(RASTERS).forEach((key) => layers.push({
        id: `raster-${key}`, type: 'raster', source: `raster-${key}`, layout: { visibility: 'none' },
      }));
    }
  }
  if (!layers.some((l) => l.id === 'gemeinden-fill')) layers.push(...dataLayers);
  layers.push(labelLayer);
  style.layers = layers;
  return style;
}

const style = buildStyle();
const baseLayerIds = baseStyle.layers.map((l) => l.id);
const originalPaint = Object.fromEntries(baseStyle.layers.map((l) => [l.id, l.paint || {}]));

// ---------------------------------------------------------------------------
// Karte
// ---------------------------------------------------------------------------
const map = new maplibregl.Map({
  container: 'map',
  style,
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
  if (window.innerWidth <= 760) return { top: 90, bottom: 80, left: 10, right: 10 };
  return { top: 40, bottom: 50, left: Math.min(280, window.innerWidth * 0.2), right: 340 };
}

let hoveredId = null;
let selectedId = null;
const activeClasses = new Set([2, 1, 0, -1, -7, -8, -9]);
const featureRef = (id) => ({ source: 'gemeinden', sourceLayer: 'gemeinden', id });

map.on('load', () => {
  setBasemap('none');
  addCantonMarkers();
  bindMapEvents();
  readHash();
});

// ---------------------------------------------------------------------------
// Hintergrundkarten
// ---------------------------------------------------------------------------
function setBasemap(mode) {
  const vectorOn = mode === 'light';
  baseLayerIds.forEach((id) => {
    if (id === 'background') return;
    const show = vectorOn || WATER_LAYERS.includes(id);
    map.setLayoutProperty(id, 'visibility', show ? 'visible' : 'none');
  });
  Object.keys(RASTERS).forEach((key) => {
    map.setLayoutProperty(`raster-${key}`, 'visibility', key === mode ? 'visible' : 'none');
  });

  map.setPaintProperty('background', 'background-color',
    mode === 'none' ? '#ffffff' : originalPaint.background['background-color']);
  // Gewässer: auf dem Luftbild halbtransparent, sonst deckend
  map.setPaintProperty('water', 'fill-opacity', mode === 'luftbild' ? 0.45 : 1);

  const opacity = { none: 1, light: 0.6, farbe: 0.55, grau: 0.6, luftbild: 0.5 }[mode];
  map.setPaintProperty('gemeinden-fill', 'fill-opacity', hoverOpacity(opacity, Math.max(0.3, opacity - 0.25)));
  // In der Basiskarte sind Ortsnamen bereits enthalten
  map.setLayoutProperty('gemeinden-label', 'visibility', mode !== 'light' && $('#tg-labels').checked ? 'visible' : 'none');
  document.body.dataset.basemap = mode;
}

document.querySelectorAll('input[name="basemap"]').forEach((input) => {
  input.addEventListener('change', () => { if (input.checked) setBasemap(input.value); });
});

// ---------------------------------------------------------------------------
// Kantonssymbole (HTML-Marker, damit Schrift und Kreisgrösse fix bleiben)
// ---------------------------------------------------------------------------
const cantonMarkers = [];
const cantonRanking = [...kantonePunkte.features]
  .sort((a, b) => b.properties.acc100k - a.properties.acc100k)
  .map((f) => f.properties.kt);

function addCantonMarkers() {
  kantonePunkte.features.forEach((f) => {
    const p = f.properties;
    const size = CANTON_SIZES[p.accClass];
    const el = document.createElement('button');
    el.className = 'canton';
    el.style.width = `${size}px`;
    el.style.height = `${size}px`;
    el.style.setProperty('--fs', `${Math.round(size * 0.42)}px`);
    el.textContent = p.abbr;
    el.setAttribute('aria-label', `${p.name}: ${fmt1.format(p.acc100k)} Velounfälle pro 100'000 Einwohner`);

    const popup = new maplibregl.Popup({ offset: size / 2 + 4, closeButton: false, className: 'canton-popup' })
      .setHTML(`<b>${escapeHtml(p.name)}</b><br>${fmt1.format(p.acc100k)} Velounfälle pro 100'000 EW<br>
        <span style="color:#7a7280">${num(p.acc)} Unfälle · ${num(p.pop)} EW · Rang ${cantonRanking.indexOf(p.kt) + 1} von 26</span>`);

    const marker = new maplibregl.Marker({ element: el }).setLngLat(f.geometry.coordinates).setPopup(popup).addTo(map);
    el.addEventListener('mouseenter', () => { hideTooltip(); if (!popup.isOpen()) marker.togglePopup(); });
    el.addEventListener('mouseleave', () => { if (popup.isOpen()) marker.togglePopup(); });
    el.addEventListener('click', (e) => e.stopPropagation());
    cantonMarkers.push(marker);
  });
}

// ---------------------------------------------------------------------------
// Interaktion
// ---------------------------------------------------------------------------
const tooltip = $('#tooltip');
const hideTooltip = () => { tooltip.hidden = true; };

function setHover(id) {
  if (hoveredId === id) return;
  if (hoveredId != null) map.setFeatureState(featureRef(hoveredId), { hover: false });
  hoveredId = id;
  if (id != null) map.setFeatureState(featureRef(id), { hover: true });
}

function bindMapEvents() {
  const canHover = window.matchMedia('(hover: hover)').matches;

  map.on('mousemove', 'gemeinden-fill', (e) => {
    const g = byId.get(e.features[0].id);
    if (!g) { map.getCanvas().style.cursor = ''; setHover(null); hideTooltip(); return; }
    map.getCanvas().style.cursor = 'pointer';
    setHover(g.id);
    if (!canHover) return;
    tooltip.innerHTML = g.yes === undefined
      ? `<b>${escapeHtml(g.name)}</b> <span>${meta.cantonNames[g.kt]}</span><br><span>kein Gemeindegebiet</span>`
      : `<b>${escapeHtml(g.name)}</b> <span>${meta.cantonNames[g.kt]}</span><br>
        Ja ${pct(g.yes)} <span>·</span> Velowege ${pct(g.bike, fmt2)}`;
    tooltip.style.left = `${e.originalEvent.clientX}px`;
    tooltip.style.top = `${e.originalEvent.clientY}px`;
    tooltip.hidden = false;
  });
  map.on('mouseleave', 'gemeinden-fill', () => {
    map.getCanvas().style.cursor = '';
    setHover(null);
    hideTooltip();
  });
  map.on('click', (e) => {
    const hit = map.queryRenderedFeatures(e.point, { layers: ['gemeinden-fill'] })
      .find((f) => byId.has(f.id));
    select(hit ? hit.id : null);
  });
  map.on('movestart', hideTooltip);
}

function select(id, { fly = false } = {}) {
  if (selectedId != null) map.setFeatureState(featureRef(selectedId), { selected: false });
  selectedId = id;
  if (id == null) {
    $('#info').hidden = true;
    history.replaceState(null, '', location.pathname + location.search);
    return;
  }
  const g = byId.get(id);
  if (!g) return;
  map.setFeatureState(featureRef(id), { selected: true });
  renderInfo(g);
  history.replaceState(null, '', `#gemeinde=${id}`);
  if (fly) {
    const pad = framePadding();
    const [w, s, e, n] = g.bbox;
    map.fitBounds([[w, s], [e, n]], {
      padding: { ...pad, bottom: window.innerWidth <= 760 ? window.innerHeight * 0.6 : pad.bottom },
      maxZoom: window.innerWidth <= 760 ? 11 : 12,
      duration: 900,
    });
  }
}

function bar(value, max, color, marks) {
  const w = Math.max(0, Math.min(100, (value / max) * 100));
  const m = marks.map(({ v, label, alt }) => `<span class="mark${alt ? ' alt' : ''}" style="left:${(v / max) * 100}%"><span>${label}</span></span>`).join('');
  return `<div class="bar" style="--c:${color}"><span class="fill" style="width:${w}%"></span>${m}</div>`;
}

function renderInfo(p) {
  const canton = cantonById.get(p.kt);
  const head = `
    <div class="info-head">
      <h3>${escapeHtml(p.name)}</h3>
      <span class="kt">${escapeHtml(canton.name)} (${canton.abbr}) · BFS-Nr. ${p.id}</span>
    </div>`;

  if (p.yes === undefined) {
    $('#info-body').innerHTML = `${head}
      <div class="badge" style="--c:${COLORS[p.cls]}"><i></i><span><b>Kein Gemeindegebiet</b>,
      gemeinsam verwaltete Fläche (Kommunanz bzw. Staatswald)</span></div>`;
    $('#info').hidden = false;
    return;
  }

  const noVote = p.yes == null;
  const [t1, t2] = CLASS_TEXT[p.cls]
    || ['Keine eigenen Abstimmungsdaten', `gemeinsame Urne${p.urne ? ` mit ${escapeHtml(p.urne)}` : ''}`];
  const yesColor = p.yes >= meta.yesThreshold ? COLORS[2] : COLORS['-1'];
  const bikeColor = p.bike >= meta.bikeThreshold ? COLORS[2] : COLORS['-1'];
  const bikeMax = Math.max(15, Math.ceil(((p.bike ?? 0) + 1) / 5) * 5);

  $('#info-body').innerHTML = `${head}
    <div class="badge" style="--c:${COLORS[p.cls]}"><i></i><span><b>${t1}</b>, ${t2}</span></div>

    <div class="metric">
      <div class="metric-top"><span class="metric-label">Ja-Stimmen</span><span class="metric-value">${noVote ? 'keine Daten' : pct(p.yes)}</span></div>
      ${noVote ? '' : bar(p.yes, 100, yesColor, [
        { v: meta.yesThreshold, label: `Ø Gemeinden ${fmt.format(meta.yesThreshold)} %` },
        { v: meta.nationalYes, label: `CH ${fmt1.format(meta.nationalYes)} %`, alt: true },
      ])}
      <div class="metric-sub">${noVote ? `Die Stimmen wurden ${p.urne ? `in ${escapeHtml(p.urne)} ` : ''}gemeinsam ausgezählt.`
        : `${num(p.ja)} Ja · ${num(p.nein)} Nein · Stimmbeteiligung ${pct(p.turnout)}`}</div>
    </div>

    <div class="metric">
      <div class="metric-top"><span class="metric-label">Anteil Velowege am Strassennetz</span><span class="metric-value">${pct(p.bike, fmt2)}</span></div>
      ${p.bike == null ? '' : bar(p.bike, bikeMax, bikeColor, [{ v: meta.bikeThreshold, label: `Referenz ${fmt2.format(meta.bikeThreshold)} %` }])}
      <div class="metric-sub">${p.bike_km ? `${fmt1.format(p.bike_km)} km Velowege` : 'Keine Velowege erfasst'}${p.street_km != null ? ` · ${fmt1.format(p.street_km)} km Strassennetz` : ''}</div>
    </div>

    <div class="metric">
      <div class="metric-top"><span class="metric-label">Velounfälle</span><span class="metric-sub">${meta.accidentPeriod}</span></div>
      <div class="stats">
        <div><b>${num(p.acc)}</b><span>Unfälle</span></div>
        <div><b>${p.acc100k == null ? '–' : fmt.format(Math.round(p.acc100k))}</b><span>pro 100'000 EW</span></div>
        <div><b>${num(p.pop)}</b><span>Einwohner</span></div>
      </div>
      <p class="note">Kanton ${canton.abbr}: ${fmt1.format(canton.acc100k)} Unfälle pro 100'000 EW.
        Polizeilich registrierte Unfälle mit Velobeteiligung (ASTRA).</p>
    </div>`;
  $('#info').hidden = false;
}

$('#info-close').addEventListener('click', () => select(null));
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') select(null); });

function readHash() {
  const m = location.hash.match(/gemeinde=(\d+)/);
  if (m) select(Number(m[1]), { fly: true });
}
window.addEventListener('hashchange', readHash);

document.querySelectorAll('[data-goto]').forEach((b) => {
  b.addEventListener('click', () => select(Number(b.dataset.goto), { fly: true }));
});

// ---------------------------------------------------------------------------
// Legende: Klassen filtern, Ebenen schalten
// ---------------------------------------------------------------------------
function applyClassFilter() {
  map.setFilter('gemeinden-fill', ['in', ['get', 'cls'], ['literal', [...activeClasses]]]);
}

document.querySelectorAll('.sw').forEach((b) => {
  b.addEventListener('click', () => {
    const cls = Number(b.dataset.cls);
    if (activeClasses.has(cls)) activeClasses.delete(cls); else activeClasses.add(cls);
    b.setAttribute('aria-pressed', String(activeClasses.has(cls)));
    applyClassFilter();
  });
});

const setVisible = (layer, on) => map.setLayoutProperty(layer, 'visibility', on ? 'visible' : 'none');

$('#tg-cantons-pts').addEventListener('change', (e) => {
  cantonMarkers.forEach((m) => { m.getElement().style.display = e.target.checked ? '' : 'none'; });
});
$('#tg-borders').addEventListener('change', (e) => setVisible('kantone-line', e.target.checked));
$('#tg-labels').addEventListener('change', (e) => setVisible('gemeinden-label', e.target.checked && document.body.dataset.basemap !== 'light'));

const legendToggle = $('#legend-toggle');
legendToggle.addEventListener('click', () => {
  const open = legendToggle.getAttribute('aria-expanded') !== 'true';
  legendToggle.setAttribute('aria-expanded', String(open));
  $('#legend-body').hidden = !open;
});
if (window.innerWidth <= 760) legendToggle.click();

// ---------------------------------------------------------------------------
// Suche
// ---------------------------------------------------------------------------
const normalize = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const index = gemeinden
  .filter((g) => g.yes !== undefined)
  .map((g) => ({ ...g, key: normalize(g.name) }))
  .sort((a, b) => a.name.localeCompare(b.name, 'de'));

const input = $('#search');
const results = $('#search-results');
let hits = [];
let cursor = -1;

function renderResults() {
  const q = normalize(input.value.trim());
  if (!q) { results.hidden = true; input.setAttribute('aria-expanded', 'false'); return; }
  const starts = index.filter((d) => d.key.startsWith(q));
  const contains = index.filter((d) => !d.key.startsWith(q) && d.key.includes(q));
  hits = [...starts, ...contains].slice(0, 8);
  cursor = hits.length ? 0 : -1;
  results.innerHTML = hits.length
    ? hits.map((d, i) => `<li role="option" data-id="${d.id}" aria-selected="${i === cursor}" style="--c:${COLORS[d.cls]}">
        <i></i>${escapeHtml(d.name)}<small>${meta.cantonNames[d.kt]}</small></li>`).join('')
    : '<li class="empty">Keine Gemeinde gefunden</li>';
  results.hidden = false;
  input.setAttribute('aria-expanded', 'true');
}

function choose(id) {
  results.hidden = true;
  input.setAttribute('aria-expanded', 'false');
  input.value = byId.get(id).name;
  input.blur();
  select(id, { fly: true });
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
    choose(hits[cursor].id);
  } else if (e.key === 'Escape') {
    results.hidden = true;
  }
});
results.addEventListener('mousedown', (e) => {
  const li = e.target.closest('li[data-id]');
  if (li) { e.preventDefault(); choose(Number(li.dataset.id)); }
});
input.addEventListener('blur', () => setTimeout(() => { results.hidden = true; }, 100));

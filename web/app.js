/* global maplibregl */
// Interaktive Karte «Bundesbeschluss Velo 2018»
// Daten: web/data/*.geojson, erzeugt mit `python -m pipeline webdata`

const COLORS = {
  2: '#1f9a4c',
  1: '#d9a3e2',
  0: '#a6db9c',
  '-1': '#983aa8',
  '-9': '#d4d4d4',
};

const CLASS_TEXT = {
  2: ['Überdurchschnittlich viele Velowege', 'überdurchschnittlich viele Ja-Stimmen'],
  1: ['Überdurchschnittlich viele Velowege', 'unterdurchschnittlich viele Ja-Stimmen'],
  0: ['Unterdurchschnittlich viele Velowege', 'überdurchschnittlich viele Ja-Stimmen'],
  '-1': ['Unterdurchschnittlich viele Velowege', 'unterdurchschnittlich viele Ja-Stimmen'],
};

const CANTON_SIZES = [26, 32, 40, 50]; // px, je Unfallklasse
const CH_BOUNDS = [[5.956, 45.818], [10.492, 47.808]];

const fmt = new Intl.NumberFormat('de-CH');
const fmt1 = new Intl.NumberFormat('de-CH', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const fmt2 = new Intl.NumberFormat('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const pct = (v, f = fmt1) => (v == null ? '–' : `${f.format(v)} %`);
const num = (v) => (v == null ? '–' : fmt.format(v));

const $ = (sel) => document.querySelector(sel);
const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// ---------------------------------------------------------------------------
// Daten laden
// ---------------------------------------------------------------------------
const load = (name) => fetch(`data/${name}`).then((r) => {
  if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`);
  return r.json();
});

const [gemeinden, kantone, kantonePunkte, seen, meta] = await Promise.all([
  load('gemeinden.geojson'),
  load('kantone.geojson'),
  load('kantone_punkte.geojson'),
  load('seen.geojson'),
  load('meta.json'),
]);

const byId = new Map(gemeinden.features.map((f) => [f.properties.id, f]));
const cantonById = new Map(kantonePunkte.features.map((f) => [f.properties.kt, f.properties]));

// Schwellenwerte in die statischen Texte einsetzen
document.querySelectorAll('[data-meta]').forEach((el) => {
  const v = meta[el.dataset.meta];
  el.textContent = pct(v, Number.isInteger(v) ? fmt : fmt2).replace(',00', '');
});

// Anzahl Gemeinden je Klasse in der Legende
const counts = {};
gemeinden.features.forEach((f) => { counts[f.properties.cls] = (counts[f.properties.cls] || 0) + 1; });
document.querySelectorAll('.sw').forEach((b) => {
  b.querySelector('.n').textContent = `${num(counts[b.dataset.cls] || 0)} Gem.`;
});

// Kreis-Legende
$('#circle-legend').innerHTML = meta.accLabels.map((label, i) => {
  const s = CANTON_SIZES[i];
  return `<li><span class="dot" style="width:${s}px;height:${s}px"></span><span>${label}</span></li>`;
}).join('');

// ---------------------------------------------------------------------------
// Karte
// ---------------------------------------------------------------------------
const map = new maplibregl.Map({
  container: 'map',
  bounds: CH_BOUNDS,
  fitBoundsOptions: { padding: framePadding() },
  maxBounds: [[3.5, 44.8], [13, 48.9]],
  minZoom: 6,
  maxZoom: 14,
  dragRotate: false,
  pitchWithRotate: false,
  attributionControl: false,
  style: {
    version: 8,
    glyphs: 'https://protomaps.github.io/basemaps-assets/fonts/{fontstack}/{range}.pbf',
    sources: {
      swisstopo: {
        type: 'raster',
        tiles: ['https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.pixelkarte-grau/default/current/3857/{z}/{x}/{y}.jpeg'],
        tileSize: 256,
        maxzoom: 18,
        attribution: '© <a href="https://www.swisstopo.admin.ch/">swisstopo</a>',
      },
    },
    layers: [
      { id: 'background', type: 'background', paint: { 'background-color': '#ffffff' } },
      { id: 'basemap', type: 'raster', source: 'swisstopo', layout: { visibility: 'none' }, paint: { 'raster-opacity': 0.9 } },
    ],
  },
});

map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
map.addControl(new maplibregl.FullscreenControl(), 'top-right');
map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: 'metric' }), 'bottom-right');
map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');

function framePadding() {
  const mobile = window.innerWidth <= 760;
  if (mobile) return { top: 90, bottom: 80, left: 10, right: 10 };
  return { top: 40, bottom: 50, left: Math.min(280, window.innerWidth * 0.2), right: 340 };
}

let hoveredId = null;
let selectedId = null;
const activeClasses = new Set([2, 1, 0, -1, -9]);

map.on('load', () => {
  map.addSource('gemeinden', { type: 'geojson', data: gemeinden, promoteId: 'id' });
  map.addSource('kantone', { type: 'geojson', data: kantone });
  map.addSource('seen', { type: 'geojson', data: seen });

  const colorExpr = ['match', ['get', 'cls'],
    2, COLORS[2], 1, COLORS[1], 0, COLORS[0], -1, COLORS['-1'], COLORS['-9']];

  map.addLayer({
    id: 'gemeinden-fill',
    type: 'fill',
    source: 'gemeinden',
    paint: {
      'fill-color': colorExpr,
      'fill-opacity': ['case', ['boolean', ['feature-state', 'hover'], false], 0.78, 1],
    },
  });
  map.addLayer({
    id: 'gemeinden-line',
    type: 'line',
    source: 'gemeinden',
    paint: {
      'line-color': '#3a1f40',
      'line-opacity': ['interpolate', ['linear'], ['zoom'], 6, 0.35, 10, 0.6],
      'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.25, 10, 0.8, 13, 1.4],
    },
  });
  map.addLayer({
    id: 'seen-fill',
    type: 'fill',
    source: 'seen',
    paint: { 'fill-color': '#b9e1f6', 'fill-outline-color': '#4c9fd6' },
  });
  map.addLayer({
    id: 'seen-line',
    type: 'line',
    source: 'seen',
    paint: { 'line-color': '#4c9fd6', 'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.6, 12, 1.5] },
  });
  map.addLayer({
    id: 'kantone-line',
    type: 'line',
    source: 'kantone',
    layout: { 'line-join': 'round' },
    paint: {
      'line-color': '#1d1720',
      'line-opacity': 0.55,
      'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.9, 10, 2.2],
    },
  });
  map.addLayer({
    id: 'gemeinden-hover',
    type: 'line',
    source: 'gemeinden',
    paint: {
      'line-color': '#1d1720',
      'line-width': ['case', ['boolean', ['feature-state', 'hover'], false], 1.6, 0],
    },
  });
  map.addLayer({
    id: 'gemeinden-selected',
    type: 'line',
    source: 'gemeinden',
    layout: { 'line-join': 'round' },
    paint: {
      'line-color': '#e3262b',
      'line-width': ['case', ['boolean', ['feature-state', 'selected'], false], 3, 0],
    },
  });
  map.addLayer({
    id: 'gemeinden-label',
    type: 'symbol',
    source: 'gemeinden',
    minzoom: 10,
    layout: {
      'text-field': ['get', 'name'],
      'text-font': ['Noto Sans Medium'],
      'text-size': ['interpolate', ['linear'], ['zoom'], 10, 11, 13, 14],
      'text-max-width': 8,
      'text-padding': 4,
    },
    paint: { 'text-color': '#1d1720', 'text-halo-color': 'rgba(255,255,255,.9)', 'text-halo-width': 1.4 },
  });

  addCantonMarkers();
  bindMapEvents();
  readHash();
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
        <span style="color:#7a7280">Rang ${cantonRanking.indexOf(p.kt) + 1} von 26</span>`);

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
  if (hoveredId != null) map.setFeatureState({ source: 'gemeinden', id: hoveredId }, { hover: false });
  hoveredId = id;
  if (id != null) map.setFeatureState({ source: 'gemeinden', id }, { hover: true });
}

function bindMapEvents() {
  const canHover = window.matchMedia('(hover: hover)').matches;

  map.on('mousemove', 'gemeinden-fill', (e) => {
    const f = e.features[0];
    map.getCanvas().style.cursor = 'pointer';
    setHover(f.id);
    if (!canHover) return;
    const p = byId.get(f.id).properties;
    tooltip.innerHTML = `<b>${escapeHtml(p.name)}</b> <span>${meta.cantonNames[p.kt]}</span><br>
      Ja ${pct(p.yes)} <span>·</span> Velowege ${pct(p.bike, fmt2)}`;
    tooltip.style.left = `${e.originalEvent.clientX}px`;
    tooltip.style.top = `${e.originalEvent.clientY}px`;
    tooltip.hidden = false;
  });
  map.on('mouseleave', 'gemeinden-fill', () => {
    map.getCanvas().style.cursor = '';
    setHover(null);
    hideTooltip();
  });
  map.on('click', 'gemeinden-fill', (e) => select(e.features[0].id));
  map.on('click', (e) => {
    const hit = map.queryRenderedFeatures(e.point, { layers: ['gemeinden-fill'] });
    if (!hit.length) select(null);
  });
  map.on('movestart', hideTooltip);
}

function select(id, { fly = false } = {}) {
  if (selectedId != null) map.setFeatureState({ source: 'gemeinden', id: selectedId }, { selected: false });
  selectedId = id;
  if (id == null) {
    $('#info').hidden = true;
    history.replaceState(null, '', location.pathname + location.search);
    return;
  }
  const f = byId.get(id);
  if (!f) return;
  map.setFeatureState({ source: 'gemeinden', id }, { selected: true });
  renderInfo(f.properties);
  history.replaceState(null, '', `#gemeinde=${id}`);
  if (fly) {
    const pad = framePadding();
    map.fitBounds(bbox(f.geometry), {
      padding: { ...pad, bottom: window.innerWidth <= 760 ? window.innerHeight * 0.6 : pad.bottom },
      maxZoom: window.innerWidth <= 760 ? 10.5 : 11.5,
      duration: 900,
    });
  }
}

function bbox(geom) {
  let minX = Infinity; let minY = Infinity; let maxX = -Infinity; let maxY = -Infinity;
  const walk = (c) => {
    if (typeof c[0] === 'number') {
      if (c[0] < minX) minX = c[0];
      if (c[0] > maxX) maxX = c[0];
      if (c[1] < minY) minY = c[1];
      if (c[1] > maxY) maxY = c[1];
    } else c.forEach(walk);
  };
  walk(geom.coordinates);
  return [[minX, minY], [maxX, maxY]];
}

function bar(value, max, color, marks) {
  const w = Math.max(0, Math.min(100, (value / max) * 100));
  const m = marks.map(({ v, label, alt }) => `<span class="mark${alt ? ' alt' : ''}" style="left:${(v / max) * 100}%"><span>${label}</span></span>`).join('');
  return `<div class="bar" style="--c:${color}"><span class="fill" style="width:${w}%"></span>${m}</div>`;
}

function renderInfo(p) {
  const canton = cantonById.get(p.kt);
  const color = COLORS[p.cls];
  const noData = p.cls === -9;
  const [t1, t2] = CLASS_TEXT[p.cls] || ['Keine eigenen Abstimmungsdaten', `gemeinsame Urne${p.urne ? ` mit ${p.urne}` : ''}`];
  const yesColor = p.yes >= meta.yesThreshold ? COLORS[2] : COLORS['-1'];
  const bikeColor = p.bike >= meta.bikeThreshold ? COLORS[2] : COLORS['-1'];
  const bikeMax = Math.max(15, Math.ceil((p.bike + 1) / 5) * 5);

  $('#info-body').innerHTML = `
    <div class="info-head">
      <h3>${escapeHtml(p.name)}</h3>
      <span class="kt">${escapeHtml(canton.name)} (${canton.abbr}) · BFS-Nr. ${p.id}</span>
    </div>
    <div class="badge" style="--c:${color}"><i></i><span><b>${t1}</b>, ${t2}</span></div>

    <div class="metric">
      <div class="metric-top"><span class="metric-label">Ja-Stimmen</span><span class="metric-value">${noData ? 'keine Daten' : pct(p.yes)}</span></div>
      ${noData ? '' : bar(p.yes, 100, yesColor, [
        { v: meta.yesThreshold, label: `Ø Gemeinden ${fmt.format(meta.yesThreshold)} %` },
        { v: meta.nationalYes, label: `CH ${fmt1.format(meta.nationalYes)} %`, alt: true },
      ])}
      <div class="metric-sub">${noData ? `Stimmen wurden ${p.urne ? `in ${escapeHtml(p.urne)} ` : ''}gemeinsam ausgezählt.`
        : `${num(p.ja)} Ja · ${num(p.nein)} Nein · Stimmbeteiligung ${pct(p.turnout)}`}</div>
    </div>

    <div class="metric">
      <div class="metric-top"><span class="metric-label">Anteil Velowege am Strassennetz</span><span class="metric-value">${pct(p.bike, fmt2)}</span></div>
      ${bar(p.bike ?? 0, bikeMax, bikeColor, [{ v: meta.bikeThreshold, label: `Referenz ${fmt2.format(meta.bikeThreshold)} %` }])}
      <div class="metric-sub">${p.bike_km != null ? `${fmt1.format(p.bike_km)} km Velowege` : 'Keine Velowege erfasst'} · ${fmt1.format(p.street_km ?? 0)} km Strassennetz</div>
    </div>

    <div class="metric">
      <div class="metric-top"><span class="metric-label">Velounfälle</span></div>
      <div class="stats">
        <div><b>${num(p.acc)}</b><span>Unfälle</span></div>
        <div><b>${!p.pop || p.acc100k == null ? '–' : fmt.format(Math.round(p.acc100k))}</b><span>pro 100'000 EW</span></div>
        <div><b>${p.pop ? num(p.pop) : '–'}</b><span>Einwohner</span></div>
      </div>
      <p class="note">Kanton ${canton.abbr}: ${fmt1.format(canton.acc100k)} Unfälle pro 100'000 EW (Mittel der Gemeinden).
        Erfasst sind polizeilich registrierte Unfälle mit Velobeteiligung ab 2011.</p>
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
  const filter = ['in', ['get', 'cls'], ['literal', [...activeClasses]]];
  ['gemeinden-fill', 'gemeinden-label'].forEach((id) => map.setFilter(id, filter));
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
$('#tg-labels').addEventListener('change', (e) => setVisible('gemeinden-label', e.target.checked));
$('#tg-basemap').addEventListener('change', (e) => {
  setVisible('basemap', e.target.checked);
  map.setPaintProperty('background', 'background-color', e.target.checked ? '#f2f2f2' : '#ffffff');
  map.setPaintProperty('gemeinden-fill', 'fill-opacity', e.target.checked
    ? ['case', ['boolean', ['feature-state', 'hover'], false], 0.45, 0.62]
    : ['case', ['boolean', ['feature-state', 'hover'], false], 0.78, 1]);
});

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
const index = gemeinden.features
  .map((f) => ({ id: f.properties.id, name: f.properties.name, kt: f.properties.kt, cls: f.properties.cls, key: normalize(f.properties.name) }))
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
  input.value = byId.get(id).properties.name;
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

// Urban Resilience Index — site logic (vanilla JS + MapLibre GL)
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const fmt = (v, d = 0) => Number(v).toLocaleString("en-SG", { minimumFractionDigits: d, maximumFractionDigits: d });
const sign = (v, d = 1) => (v >= 0 ? "+" : "−") + fmt(Math.abs(v), d);

const PILLARS = ["heat", "shade", "green", "community", "access", "flood"];
const PNAME = { heat: "Heat exposure", shade: "Shade & cooling", green: "Green-blue space", community: "Community & green use", access: "Access & mobility", flood: "Flood resilience" };
const PSHORT = { heat: "Heat", shade: "Shade", green: "Green-blue", community: "Community", access: "Access", flood: "Flood" };
const PCOL = { heat: "#eb6834", shade: "#1baf7a", green: "#008300", community: "#e87ba4", access: "#2a78d6", flood: "#4a3aa7" };
const PDESC = {
  heat: ["Surface temperature near the block (Landsat, 30 m)", "Live NEA WBGT shown as context (phase 2: block-level felt heat)"],
  shade: ["Tree canopy within 200 m (Sentinel-2)", "Shaded share of walkways within 400 m (OSM covered ways + canopy)"],
  green: ["Walk to nearest park (Green Plan's 10-minute target)", "Park area within 800 m", "Distance to park connector or water"],
  community: ["Community gardens within 400 m (proxy)", "Phase 2: verified use, upkeep, comfort, species from residents"],
  access: ["Heat-adjusted walk to eldercare / AAC, clinic, hawker centre, MRT exit, bus stop"],
  flood: ["Distance to PUB flood-prone locations (Nov 2025 list)"],
};
const PWHY = {
  heat: "The outcome itself; Landsat gives open, current, 30 m data.",
  shade: "Street shade cut extreme heat-stress occurrences by 92% in one-north (CARES).",
  green: "Green Plan's 10-minute park target; park cooling reach is measurable.",
  community: "What open data cannot give: how spaces are actually used and kept.",
  access: "Seniors walk to daily needs; HDB blocks average 294 m to amenities (Lee et al.).",
  flood: "Completes the blue-green brief; PUB publishes current flood-prone locations.",
};
// scores use a colour-blind-safe brown <-> teal diverging scale (same as figures/)
const DIV_STOPS = [[10, "#8c510a"], [30, "#d8b365"], [50, "#f2f1ec"], [70, "#7fc8b8"], [90, "#01665e"]];   // BrBG: brown = less resilient
function divColor(v) {
  for (let i = 1; i < DIV_STOPS.length; i++) {
    const [a, ca] = DIV_STOPS[i - 1], [b, cb] = DIV_STOPS[i];
    if (v <= b) return mix(ca, cb, Math.max(0, (v - a) / (b - a)));
  }
  return DIV_STOPS.at(-1)[1];
}
function mix(a, b, t) {
  const p = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const x = p(a), y = p(b);
  return "#" + x.map((v, i) => Math.round(v + (y[i] - v) * t).toString(16).padStart(2, "0")).join("");
}

// Basemap: OneMap (Singapore Land Authority), free with attribution
const BASEMAP = { version: 8, sources: { onemap: { type: "raster", tileSize: 256, minzoom: 11, maxzoom: 19,
  tiles: ["https://www.onemap.gov.sg/maps/tiles/Grey/{z}/{x}/{y}.png"],
  attribution: '<img src="https://www.onemap.gov.sg/web-assets/images/logo/om_logo.png" style="height:14px;width:14px;vertical-align:middle"> <a href="https://www.onemap.gov.sg/" target="_blank" rel="noopener">OneMap</a> © contributors | <a href="https://www.sla.gov.sg/" target="_blank" rel="noopener">Singapore Land Authority</a>' } },
  layers: [{ id: "bg", type: "background", paint: { "background-color": "#eef0f1" } }, { id: "onemap", type: "raster", source: "onemap" }] };

const tip = $("#tip");
function showTip(e, html) { tip.innerHTML = html; tip.style.opacity = 1; moveTip(e); }
function moveTip(e) {
  const w = tip.offsetWidth, h = tip.offsetHeight;
  let x = e.clientX + 14, y = e.clientY + 14;
  if (x + w > innerWidth - 8) x = e.clientX - w - 14;
  if (y + h > innerHeight - 8) y = e.clientY - h - 14;
  tip.style.left = x + "px"; tip.style.top = y + "px";
}
function hideTip() { tip.style.opacity = 0; }

async function getJSON(p) { const r = await fetch(p); if (!r.ok) throw new Error(p); return r.json(); }

// ------------------------------------------------------------------ chrome: rails and nav highlight (no scroll hijacking)
function chrome() {
  $$(".rail-ctrl button").forEach((b) => b.addEventListener("click", () => {
    const r = document.getElementById(b.dataset.rail);
    r.scrollBy({ left: Number(b.dataset.dir) * (r.querySelector(".card")?.offsetWidth + 20 || 340), behavior: "smooth" });
  }));
  const links = $$(".nav ul a");
  const io = new IntersectionObserver((es) => es.forEach((e) => {
    if (e.isIntersecting) links.forEach((a) => a.classList.toggle("active", a.getAttribute("href") === "#" + e.target.id));
  }), { rootMargin: "-45% 0px -50% 0px" });
  $$("section[id], header[id]").forEach((s) => io.observe(s));
}

// ------------------------------------------------------------------ pillars + five tests
function pillarCards(meta) {
  const conf = {};
  meta.indicators.forEach((i) => { (conf[i.pillar] ||= []).push(i.confidence); });
  $("#pillarrail").innerHTML = PILLARS.map((p) => {
    const c = conf[p].includes("low") ? "low" : conf[p].includes("medium") ? "medium" : "high";
    return `<article class="card pillar" style="--pc:${PCOL[p]}">
      <div class="tag">Pillar · ${meta.indicators.filter((i) => i.pillar === p).length} indicator${meta.indicators.filter((i) => i.pillar === p).length > 1 ? "s" : ""}</div>
      <div class="w">${meta.weights[p]}<small>% default weight</small></div>
      <h4 style="margin-top:10px">${PNAME[p]}</h4>
      <ul>${PDESC[p].map((d) => `<li>${d}</li>`).join("")}</ul>
      <p class="small">${PWHY[p]}</p>
      <div class="foot">Confidence <span class="conf ${c}">${c}</span></div></article>`;
  }).join("");
  const rows = [
    ["Surface heat (Landsat) — the outcome", 1, 1, 1, 1, 1],
    ["Tree canopy ≤200 m — strongest cooling lever (Fig. 1d)", 1, 1, 1, 1, 1],
    ["Shaded walkways ≤400 m", 1, 1, 1, 1, "—"],
    ["Park walk / area / blue", 1, 1, 1, 1, "—"],
    ["Heat-adjusted walks (5)", 1, 1, 1, 1, "—"],
    ["Flood-prone distance", 1, 1, 1, 1, "—"],
    ["Community gardens (proxy)", 1, 1, 1, 1, "—"],
    ["NEA WBGT hours (27 stations)", 1, 1, 0, 1, 0],
  ];
  const cell = (v) => v === 1 ? '<span class="pass">✓</span>' : v === 0 ? '<span class="x">✗</span>' : '<span class="muted">to test</span>';
  $("#teststable tbody").innerHTML = rows.map((r) => `<tr class="${r.includes(0) ? "fail" : ""}"><td>${r[0]}</td>${r.slice(1).map((v) => `<td>${cell(v)}</td>`).join("")}</tr>`).join("");
  $("#wbgtnote").innerHTML = `WBGT is the right heat-stress measure, but 27 stations cannot resolve blocks: interpolated to blocks it correlates with satellite surface heat at ρ = ${meta.wbgt_vs_lst_spearman.toFixed(2)}, and its highest values sit at forest and waterfront stations. It stays a live context layer until denser sensors or resident readings exist. "Predictive" is tested once community data on use and comfort exists.`;
}

// ------------------------------------------------------------------ atlas
const state = { w: {}, layer: "score", blocks: null, towns: null, focusTown: null };
function blockScores() {
  const { cols, rows } = state.blocks, ix = Object.fromEntries(cols.map((c, i) => [c, i]));
  const tot = PILLARS.reduce((a, p) => a + state.w[p], 0) || 1;
  return rows.map((r) => PILLARS.reduce((a, p) => a + state.w[p] * r[ix[p]], 0) / tot);
}
function townTable(scores) {
  const { cols, rows } = state.blocks, ix = Object.fromEntries(cols.map((c, i) => [c, i]));
  const g = {};
  rows.forEach((r, k) => { const t = r[ix.town]; (g[t] ||= { s: [], n: [], units: 0, rental: 0, blocks: 0 }); g[t].s.push(scores[k]); g[t].n.push(r[ix.need]); g[t].units += r[ix.units]; g[t].rental += r[ix.rental]; g[t].blocks++; });
  return Object.entries(g).map(([town, v]) => {
    const wsum = v.n.reduce((a, b) => a + b, 0);
    const score = v.s.reduce((a, s, i) => a + s * v.n[i], 0) / wsum;
    const srt = [...v.s].sort((a, b) => a - b), q = Math.max(1, Math.floor(srt.length * 0.2));
    const med = srt.length % 2 ? srt[(srt.length - 1) / 2] : (srt[srt.length / 2 - 1] + srt[srt.length / 2]) / 2;
    const worst = srt.slice(0, q).reduce((a, b) => a + b, 0) / q;
    return { town, score, gap: med - worst, units: v.units, rental: v.rental, blocks: v.blocks };
  });
}

function hbars(el, data, { key, max, color, label, fmtv, onClick }) {
  const H = 18, padL = 118, padR = 40, W = el.clientWidth || 600, h = data.length * H + 26;
  const x = (v) => padL + (W - padL - padR) * Math.max(0, v) / max;
  const ticks = [0, max / 4, max / 2, (3 * max) / 4, max].map((t) => Math.round(t));
  el.innerHTML = `<svg viewBox="0 0 ${W} ${h}" role="img" aria-label="${label}">
    ${ticks.map((t) => `<line x1="${x(t)}" x2="${x(t)}" y1="0" y2="${h - 20}" stroke="#e1e7e3" stroke-width="1"/><text x="${x(t)}" y="${h - 6}" text-anchor="middle">${t}</text>`).join("")}
    ${data.map((d, i) => `<g class="row ${d.hl ? "hl" : ""}" data-i="${i}" style="cursor:${onClick ? "pointer" : "default"}">
      <rect x="0" y="${i * H}" width="${W}" height="${H}" fill="transparent"/>
      <text x="${padL - 8}" y="${i * H + 13}" text-anchor="end">${d.town}</text>
      <rect class="bar" x="${padL}" y="${i * H + 3}" width="${Math.max(1, x(d[key]) - padL)}" height="${H - 6}" rx="2" fill="${color(d)}"/>
      <text x="${x(d[key]) + 5}" y="${i * H + 13}" style="font-variant-numeric:tabular-nums">${fmtv(d[key])}</text></g>`).join("")}
  </svg>`;
  $$(".row", el).forEach((g) => {
    const d = data[g.dataset.i];
    g.addEventListener("mousemove", (e) => showTip(e, `<b>${d.town}</b><br>Town score ${fmt(d.score, 1)} · inclusion gap ${fmt(d.gap, 1)}<br>${fmt(d.blocks)} blocks · ${fmt(d.units)} flats · ${fmt(d.rental)} rental`));
    g.addEventListener("mouseleave", hideTip);
    if (onClick) g.addEventListener("click", () => onClick(d));
  });
}

function renderTownCharts() {
  const scores = blockScores();
  const t = townTable(scores).sort((a, b) => b.score - a.score);
  t.forEach((d) => (d.hl = d.town === state.focusTown));
  hbars($("#rankchart"), t, { key: "score", max: 80, label: "Town score ranking", color: (d) => (d.hl ? "#111a15" : "#1f7a52"), fmtv: (v) => fmt(v, 1), onClick: (d) => focusTown(d.town) });
  const top = [...t].sort((a, b) => b.gap - a.gap).slice(0, 3).map((d) => d.town);
  hbars($("#gapchart"), t, { key: "gap", max: 30, label: "Inclusion gap by town", color: (d) => (d.hl ? "#111a15" : top.includes(d.town) ? "#1f7a52" : "#c9d3cc"), fmtv: (v) => fmt(v, 1), onClick: (d) => focusTown(d.town) });
  return scores;
}

let map, mapReady = false;
function geojson(scores) {
  const { cols, rows } = state.blocks, ix = Object.fromEntries(cols.map((c, i) => [c, i]));
  return { type: "FeatureCollection", features: rows.map((r, k) => ({
    type: "Feature", id: k, geometry: { type: "Point", coordinates: [r[ix.lon], r[ix.lat]] },
    properties: { k, v: state.layer === "score" || !PILLARS.includes(state.layer) ? scores[k] : r[ix[state.layer]] },
  })) };
}
function setLegend() {
  const L = state.layer, bar = $("#legendbar");
  bar.className = "legend-bar" + (["lst", "lstchange"].includes(L) ? " heat" : L === "ndvi" ? " green" : "");
  const lab = { lst: ["−6 °C cooler", "+6 °C hotter"], lstchange: ["cooled vs 1990s", "warmed vs 1990s"], ndvi: ["sparse", "dense vegetation"], s2: ["Sentinel-2 true colour, 2024–25", ""] }[L] || ["less resilient (0)", "more resilient (100)"];
  $("#leglo").textContent = lab[0]; $("#leghi").textContent = lab[1];
  bar.style.visibility = L === "s2" ? "hidden" : "visible";
}
function applyLayer(scores) {
  if (!mapReady) return;
  const R = { lst: "r-lst", lstchange: "r-change", ndvi: "r-ndvi", s2: "r-s2" };
  Object.values(R).forEach((id) => map.setLayoutProperty(id, "visibility", "none"));
  if (R[state.layer]) {
    map.setLayoutProperty(R[state.layer], "visibility", "visible");
    map.setPaintProperty("blocks", "circle-color", "#ffffff");
    map.setPaintProperty("blocks", "circle-stroke-color", "#111a15");
    map.setPaintProperty("blocks", "circle-opacity", 0.85);
  } else {
    map.getSource("blocks").setData(geojson(scores));
    map.setPaintProperty("blocks", "circle-color", ["interpolate", ["linear"], ["get", "v"], ...DIV_STOPS.flat()]);
    map.setPaintProperty("blocks", "circle-stroke-color", "#ffffff");
    map.setPaintProperty("blocks", "circle-opacity", 0.95);
  }
  setLegend();
}
function focusTown(town) {
  state.focusTown = town;
  const { cols, rows } = state.blocks, ix = Object.fromEntries(cols.map((c, i) => [c, i]));
  const pts = rows.filter((r) => r[ix.town] === town);
  if (map && pts.length) {
    const lo = pts.map((r) => r[ix.lon]), la = pts.map((r) => r[ix.lat]);
    map.fitBounds([[Math.min(...lo), Math.min(...la)], [Math.max(...lo), Math.max(...la)]], { padding: 50, duration: 900 });
    $("#atlas").scrollIntoView({ behavior: "smooth" });
  }
  renderTownCharts();
}
function blockCard(k, scores) {
  const { cols, rows } = state.blocks, ix = Object.fromEntries(cols.map((c, i) => [c, i])), r = rows[k];
  $("#blockcard").classList.remove("muted");
  $("#blockcard").innerHTML = `<div class="t">Blk ${r[ix.blk]} ${r[ix.street]}</div>
    <div class="muted">${r[ix.town]} · built ${r[ix.year]} · ${fmt(r[ix.units])} flats${r[ix.rental] ? ` (${fmt(r[ix.rental])} rental)` : ""} · ~${fmt(r[ix.seniors])} seniors</div>
    <div style="margin:10px 0 8px"><span style="font-family:var(--serif);font-size:34px;font-weight:600;color:${divColor(scores[k])}">${fmt(scores[k], 0)}</span> <span class="muted">/ 100 with your weights</span></div>
    ${PILLARS.map((p) => `<div class="pbar" style="--pc:${PCOL[p]}"><span>${PSHORT[p]}</span><i><b style="width:${r[ix[p]]}%"></b></i><span>${fmt(r[ix[p]])}</span></div>`).join("")}
    <div class="tiny muted" style="margin-top:8px">Surface heat ${sign(r[ix.lst_anom])} °C vs island median${r[ix.lst_change] != null ? ` (${sign(r[ix.lst_change])} since 1990s)` : ""} · canopy ≤200 m ${fmt(r[ix.canopy200])}% · walk to AAC ${fmt(r[ix.walk_aac])} m · MRT ${fmt(r[ix.walk_mrt])} m (heat-adjusted)</div>`;
}

function atlas(meta, analysis) {
  state.w = { ...meta.weights };
  const lenses = analysis.robustness.lenses;
  $("#lenses").innerHTML = Object.keys(lenses).map((k) => `<button data-lens="${k}">${k.replace(" (brief default)", "")}</button>`).join("");
  $("#sliders").innerHTML = PILLARS.map((p) => `<div class="slider" style="--pc:${PCOL[p]}"><span class="dot"></span><label>${PNAME[p]}<input type="range" min="0" max="50" step="1" value="${state.w[p]}" data-p="${p}" aria-label="${PNAME[p]} weight"></label><output>${state.w[p]}</output></div>`).join("");
  let scores = renderTownCharts();
  const update = () => { scores = renderTownCharts(); applyLayer(scores); if (state.sel != null) blockCard(state.sel, scores); };
  let raf;
  $$("#sliders input").forEach((i) => i.addEventListener("input", () => {
    state.w[i.dataset.p] = Number(i.value); i.closest(".slider").querySelector("output").textContent = i.value;
    if (state.layer !== "score") { state.layer = "score"; $$("#layerseg button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.layer === "score")); }
    cancelAnimationFrame(raf); raf = requestAnimationFrame(update);
  }));
  $$("#lenses button").forEach((b) => b.addEventListener("click", () => {
    const w = lenses[b.dataset.lens].weights;
    PILLARS.forEach((p) => { state.w[p] = Math.round(w[p] * 100); const i = $(`#sliders input[data-p="${p}"]`); i.value = state.w[p]; i.closest(".slider").querySelector("output").textContent = state.w[p]; });
    state.layer = "score"; $$("#layerseg button").forEach((x) => x.setAttribute("aria-pressed", x.dataset.layer === "score"));
    update();
  }));
  $$("#layerseg button").forEach((b) => b.addEventListener("click", () => {
    state.layer = b.dataset.layer; $$("#layerseg button").forEach((x) => x.setAttribute("aria-pressed", x === b)); applyLayer(scores);
  }));

  const C = meta.rasters.corners;
  map = new maplibregl.Map({
    container: "map", center: [103.835, 1.36], zoom: 11, minZoom: 10.5, maxZoom: 17, attributionControl: false, cooperativeGestures: true,
    style: BASEMAP,
  });
  map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: "Landsat: USGS · Sentinel-2: Copernicus · data.gov.sg (SG Open Data Licence)" }));
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
  map.on("load", () => {
    const img = (id, url, op) => { map.addSource(id, { type: "image", url, coordinates: C }); map.addLayer({ id: "r-" + id, type: "raster", source: id, layout: { visibility: "none" }, paint: { "raster-opacity": op, "raster-fade-duration": 0 } }); };
    img("lst", "assets/img/maps/lst_2021_2025.png", 0.85); img("change", "assets/img/maps/lst_change.png", 0.85);
    img("ndvi", "assets/img/maps/ndvi_2024_2025.png", 0.85); img("s2", "assets/img/maps/s2_truecolor.jpg", 1);
    map.addSource("blocks", { type: "geojson", data: geojson(scores) });
    map.addLayer({ id: "blocks", type: "circle", source: "blocks", paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 1.8, 13, 4, 16, 9],
      "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 10, 0, 13, 0.6], "circle-stroke-color": "#fff",
      "circle-color": ["interpolate", ["linear"], ["get", "v"], ...DIV_STOPS.flat()] } });
    mapReady = true; applyLayer(scores);
    const pop = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 8 });
    const ix = Object.fromEntries(state.blocks.cols.map((c, i) => [c, i]));
    map.on("mousemove", "blocks", (e) => {
      map.getCanvas().style.cursor = "pointer";
      const k = e.features[0].properties.k, r = state.blocks.rows[k];
      pop.setLngLat(e.lngLat).setHTML(`<b>Blk ${r[ix.blk]} ${r[ix.street]}</b><br>${r[ix.town]} · score ${fmt(scores[k], 0)}`).addTo(map);
    });
    map.on("mouseleave", "blocks", () => { map.getCanvas().style.cursor = ""; pop.remove(); });
    map.on("click", "blocks", (e) => { state.sel = e.features[0].properties.k; blockCard(state.sel, scores); });
  });
}

// ------------------------------------------------------------------ compare slider
function compare() {
  const c = $("#compare"), top = $(".top", c), h = $(".handle", c), inp = $("input", c);
  const set = (v) => { top.style.clipPath = `inset(0 0 0 ${v}%)`; h.style.left = v + "%"; };
  inp.addEventListener("input", () => set(inp.value)); set(50);
}

// ------------------------------------------------------------------ benchmark targets
function targets(an) {
  const f = (t, v) => (t.unit.startsWith("m") ? fmt(v) + " m" : t.unit === "ha" ? fmt(v, 1) + " ha" : t.unit === "count" ? fmt(v) : fmt(v, 0) + "%");
  $("#targets tbody").innerHTML = an.benchmark.design_targets.map((t) => `<tr><td>${t.label}</td><td class="r">${f(t, t.island_median)}</td><td class="r"><b>${f(t, t.target)}</b></td><td class="small muted">${t.best_towns.slice(0, 3).join(", ")}</td></tr>`).join("");
  $("#canopyc").textContent = (an.heat_drivers.canopy_10pp_effect_c).toFixed(1).replace("-", "−");
}

// ------------------------------------------------------------------ tweaks
function tweaks(tw, blocksCsv) {
  const TYPE = { green_pocket: ["Green pocket", "#1f7a52"], rooftop_farm: ["Rooftop farm", "#b5527f"], shade_walkway: ["Shaded walkway", "#2a78d6"] };
  const pretty = (l) => l.replace(/ a open/g, " an open").replace(/m2/g, "m²");
  const key = (c) => c.type + "|" + c.label;                     // keyed on the raw label from the engine
  const cands = tw.candidates.map((c, i) => ({ ...c, i, nice: pretty(c.label) }));
  const pkgs = { inclusion_aware: new Set(tw.inclusion_aware.package.map(key)), average_first: new Set(tw.average_first.package.map(key)), none: new Set() };
  let sel = new Set(pkgs.inclusion_aware), current = "inclusion_aware";
  const lines = blocksCsv.trim().split(/\r?\n/), head = lines[0].split(",");
  const B = lines.slice(1).map((l) => { const v = l.split(","); return Object.fromEntries(head.map((h, i) => [h, isNaN(v[i]) ? v[i] : Number(v[i])])); });

  $("#titems").innerHTML = cands.map((c) => `<label class="titem" data-k="${key(c)}"><input type="checkbox" ${sel.has(key(c)) ? "checked" : ""}>
    <div><div class="ty" style="color:${TYPE[c.type][1]}">${TYPE[c.type][0]}</div>${c.nice}<div class="tiny muted">${fmt(c.blocks)} blocks · ${fmt(c.seniors)} seniors · ${fmt(c.rental_households)} rental households gain ≥0.5</div></div>
    <div class="g">${sign(c.d_score, 2)}<small>worst-20% ${sign(c.d_worst20, 2)}</small></div></label>`).join("");

  const base = tw.baseline;
  const summary = () => {
    const exact = Object.entries(pkgs).find(([k, s]) => k !== "none" && s.size === sel.size && [...s].every((x) => sel.has(x)));
    let score, worst, gap, note;
    if (exact) {
      const p = tw[exact[0]]; score = p.final.score; worst = p.worst20; gap = p.final.gap;
      note = `Exact re-evaluation of the ${exact[0] === "inclusion_aware" ? "inclusion-aware" : "average-first"} package. Today: score ${fmt(base.score, 1)}, worst-20% ${fmt(tw.baseline_worst20, 1)}, gap ${fmt(base.gap, 1)}.`;
    } else {
      const S = cands.filter((c) => sel.has(key(c)));
      score = base.score + S.reduce((a, c) => a + c.d_score, 0); worst = tw.baseline_worst20 + S.reduce((a, c) => a + c.d_worst20, 0);
      gap = base.gap + S.reduce((a, c) => a + c.d_gap, 0);
      note = `${S.length} selected · sum of individual effects (approximate when tweaks overlap). Today: score ${fmt(base.score, 1)}, gap ${fmt(base.gap, 1)}.`;
    }
    $("#t-score").textContent = fmt(score, 1); $("#t-worst").textContent = fmt(worst, 1); $("#t-gap").textContent = fmt(gap, 1);
    $("#t-gap").style.color = gap > base.gap + 0.05 ? "#8c510a" : gap < base.gap - 0.05 ? "#1f7a52" : "";
    $("#t-note").textContent = note;
    if (tmapReady) {
      tmap.getSource("cands").setData(candFC());
      const col = exact ? (exact[0] === "inclusion_aware" ? "score_after_inclusive" : "score_after_average") : null;
      tmap.getSource("tb").setData(blockFC(col));
    }
  };
  const A = tw.average_first, I = tw.inclusion_aware;
  $("#pkgcallout").innerHTML = `<b>The inclusion check changes the answer.</b> Ranked by town average, six tweaks lift the score by ${sign(A.final.score - base.score)} but widen the inclusion gap from ${fmt(base.gap, 1)} to ${fmt(A.final.gap, 1)}. Ranked by gains for the worst-served 20% as well, the same candidate pool lifts the score by ${sign(I.final.score - base.score)}, raises the worst-served blocks by ${sign(I.worst20 - tw.baseline_worst20)}, and narrows the gap to ${fmt(I.final.gap, 1)}.`;

  $$("#titems .titem").forEach((el) => el.querySelector("input").addEventListener("change", (e) => {
    e.target.checked ? sel.add(el.dataset.k) : sel.delete(el.dataset.k);
    $$("#pkgseg button").forEach((b) => b.setAttribute("aria-pressed", "false")); summary();
  }));
  $$("#pkgseg button").forEach((b) => b.addEventListener("click", () => {
    current = b.dataset.pkg; sel = new Set(pkgs[current]);
    $$("#pkgseg button").forEach((x) => x.setAttribute("aria-pressed", x === b));
    $$("#titems .titem").forEach((el) => (el.querySelector("input").checked = sel.has(el.dataset.k))); summary();
  }));

  const candFC = () => ({ type: "FeatureCollection", features: cands.map((c) => ({ type: "Feature", geometry: { type: "Point", coordinates: [c.lon, c.lat] }, properties: { t: c.type, on: sel.has(key(c)) ? 1 : 0, g: c.d_score, label: c.nice } })) });
  const blockFC = (col) => ({ type: "FeatureCollection", features: B.map((b) => ({ type: "Feature", geometry: { type: "Point", coordinates: [b.lon, b.lat] },
    properties: { v: col ? b[col] - b.score_before : -1, s: b.score_before, w: b.worst20 === "True" ? 1 : 0, name: `Blk ${b.blk} ${String(b.street).replace(/\b\w+/g, (x) => x[0] + x.slice(1).toLowerCase())}` } })) });

  let tmap, tmapReady = false;
  const lo = B.map((b) => b.lon), la = B.map((b) => b.lat);
  tmap = new maplibregl.Map({ container: "tmap", bounds: [[Math.min(...lo), Math.min(...la)], [Math.max(...lo), Math.max(...la)]], fitBoundsOptions: { padding: 40 },
    attributionControl: false, cooperativeGestures: true,
    style: BASEMAP });
  tmap.addControl(new maplibregl.AttributionControl({ compact: true }));
  tmap.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
  tmap.on("load", () => {
    tmap.addSource("tb", { type: "geojson", data: blockFC("score_after_inclusive") });
    tmap.addLayer({ id: "tb", type: "circle", source: "tb", paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 12, 3, 16, 8],
      "circle-color": ["case", ["<", ["get", "v"], 0], ["interpolate", ["linear"], ["get", "s"], ...DIV_STOPS.flat()],
        ["interpolate", ["linear"], ["get", "v"], 0, "#e6e9e6", 0.5, "#8cc9a8", 2, "#1f7a52", 4, "#0b4a30"]],
      "circle-stroke-color": ["case", ["==", ["get", "w"], 1], "#111a15", "#ffffff"], "circle-stroke-width": ["case", ["==", ["get", "w"], 1], 1.1, 0.4] } });
    tmap.addSource("cands", { type: "geojson", data: candFC() });
    tmap.addLayer({ id: "cands", type: "circle", source: "cands", paint: {
      "circle-radius": ["case", ["==", ["get", "on"], 1], 9, 5],
      "circle-color": ["match", ["get", "t"], "green_pocket", "#1f7a52", "rooftop_farm", "#b5527f", "#2a78d6"],
      "circle-opacity": ["case", ["==", ["get", "on"], 1], 1, 0.45], "circle-stroke-color": "#fff", "circle-stroke-width": 2 } });
    const pop = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 });
    tmap.on("mousemove", "cands", (e) => { const p = e.features[0].properties; pop.setLngLat(e.lngLat).setHTML(`<b>${p.label}</b><br>town score ${sign(p.g, 2)}`).addTo(tmap); });
    tmap.on("mouseleave", "cands", () => pop.remove());
    tmap.on("mousemove", "tb", (e) => { const p = e.features[0].properties; pop.setLngLat(e.lngLat).setHTML(`<b>${p.name}</b><br>score today ${fmt(p.s, 0)}${p.v >= 0 ? ` · gain ${sign(p.v, 1)}` : ""}${p.w ? "<br>worst-served 20%" : ""}`).addTo(tmap); });
    tmap.on("mouseleave", "tb", () => pop.remove());
    tmapReady = true; summary();
  });
  summary();
}

// ------------------------------------------------------------------ value lens chart
function valueChart(an) {
  const v = an.value_lens, el = $("#valuechart");
  const rows = Object.entries(v.effects).map(([k, e]) => ({ k: k.replace("degC", "°C"), ...e }));
  const W = el.clientWidth || 640, H = 46 * rows.length + 54, padL = 200, padR = 56;
  const lo = Math.min(...rows.map((r) => r.lo)) - 0.08, hi = Math.max(...rows.map((r) => r.hi)) + 0.08;
  const x = (val) => padL + (W - padL - padR) * (val - lo) / (hi - lo);
  const ticks = [-0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75].filter((t) => t >= lo && t <= hi);
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Value lens coefficients with 95% and 50% confidence intervals">
    ${ticks.map((t) => `<line x1="${x(t)}" x2="${x(t)}" y1="10" y2="${H - 38}" stroke="${t === 0 ? "#8a918c" : "#e1e7e3"}"/><text x="${x(t)}" y="${H - 22}" text-anchor="middle">${t > 0 ? "+" : ""}${t}%</text>`).join("")}
    ${rows.map((r, i) => { const y = 30 + i * 46, lead = /canopy|heat/.test(r.k), c = lead ? "#1f7a52" : "#7d8580", cl = lead ? "#dcefe4" : "#e9ece9"; return `<g class="row" data-i="${i}">
      <text x="${padL - 12}" y="${y + 4}" text-anchor="end" style="fill:#111a15">${r.k}</text>
      <rect x="${x(r.lo)}" y="${y - 10}" width="${x(r.hi) - x(r.lo)}" height="20" fill="${cl}"/>
      <rect x="${x(r.lo50)}" y="${y - 4}" width="${Math.max(2, x(r.hi50) - x(r.lo50))}" height="8" fill="${c}"/>
      <circle cx="${x(r.pct)}" cy="${y}" r="5" fill="#fff" stroke="${c}" stroke-width="2"/>
      <text x="${x(r.hi) + 8}" y="${y + 4}" style="fill:${c}">${r.pct > 0 ? "+" : ""}${r.pct.toFixed(2)}%</text></g>`; }).join("")}
    <text x="${padL}" y="${H - 2}" style="fill:#8a918c">% change in resale price · bars: 95% and 50% CI</text>
  </svg>`;
  $$(".row", el).forEach((g) => { const r = rows[g.dataset.i]; g.addEventListener("mousemove", (e) => showTip(e, `<b>${r.k}</b><br>${r.pct > 0 ? "+" : ""}${r.pct.toFixed(2)}% (95% CI ${r.lo.toFixed(2)} to ${r.hi.toFixed(2)})<br>p = ${r.p < 0.001 ? "< 0.001" : r.p.toFixed(3)}`)); g.addEventListener("mouseleave", hideTip); });
  $("#vl-n").textContent = fmt(v.n);
}

// ------------------------------------------------------------------ case + business
function caseStudy(cs) {
  const D = cs.designs, up = D["Index-guided design"], sh = D["Typical showcase"];
  $("#cs-lcc").textContent = "−" + Math.round(100 * (1 - up.lcc / sh.lcc)) + "%";
  $("#cs-reach").textContent = fmt(up.r200); $("#cs-naive").textContent = fmt(D.naive_edge_best.r200);
  $("#cs-gain").textContent = "+S$" + (cs.mc.uplift_vs_showcase.p50 / 1e6).toFixed(1) + "M";
  $("#cs-prob").textContent = Math.round(100 * cs.mc.uplift_vs_showcase.prob_positive) + "%";
  $("#cs-fee").textContent = `S$${Math.round(sh.fee_unit_month)}→${Math.round(up.fee_unit_month)}`;
  $("#biz-roi").textContent = cs.business.client_roi.toFixed(1);
  const b = cs.business, el = $("#bizchart");
  const seg = [["rev_pass", "Project Pass", "#1f7a52"], ["rev_mon", "Monitoring", "#8cc9a8"], ["rev_retro", "Retrofit monitoring", "#c9d3cc"]];
  const W = el.clientWidth || 600, H = 240, padL = 40, padB = 28, max = Math.max(...b.rev_total) * 1.12, bw = (W - padL) / b.years.length * 0.56;
  const y = (v) => (H - padB) - (H - padB - 10) * v / max;
  let bars = "";
  b.years.forEach((yr, i) => {
    let acc = 0; const cx = padL + (W - padL) * (i + 0.5) / b.years.length;
    seg.forEach(([k, , c]) => { const v = b[k][i]; bars += `<rect class="seg" data-i="${i}" x="${cx - bw / 2}" y="${y(acc + v) + 1}" width="${bw}" height="${Math.max(0, y(acc) - y(acc + v) - 2)}" fill="${c}" rx="2"/>`; acc += v; });
    bars += `<text x="${cx}" y="${y(acc) - 6}" text-anchor="middle" style="fill:#111a15;font-weight:600">S$${(acc / 1e6).toFixed(1)}M</text><text x="${cx}" y="${H - 8}" text-anchor="middle">Year ${yr}</text>`;
  });
  el.innerHTML = `<div style="display:flex;gap:16px;font-size:12.5px;margin-bottom:6px">${seg.map(([, n, c]) => `<span><i style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${c};margin-right:6px"></i>${n}</span>`).join("")}</div>
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Five-year revenue build-up">${[0, 2e6, 4e6, 6e6].map((t) => `<line x1="${padL}" x2="${W}" y1="${y(t)}" y2="${y(t)}" stroke="#e1e7e3"/><text x="${padL - 6}" y="${y(t) + 4}" text-anchor="end">${t / 1e6}M</text>`).join("")}${bars}</svg>`;
  $$(".seg", el).forEach((r) => { const i = r.dataset.i; r.addEventListener("mousemove", (e) => showTip(e, `<b>Year ${b.years[i]}</b><br>${b.new_sites[i]} new sites · ${b.monitored[i]} monitored<br>Pass S$${fmt(b.rev_pass[i] / 1e3)}k · Monitoring S$${fmt(b.rev_mon[i] / 1e3)}k · Retrofit S$${fmt(b.rev_retro[i] / 1e3)}k`)); r.addEventListener("mouseleave", hideTip); });
}

async function heroPins() {
  try {
    const a = await getJSON("data/hero_anchors.json"), el = $("#heromap");
    const txt = {
      "Bedok": (d) => `<b>Bedok</b>score ${fmt(d.score, 0)} · <span class="w">inclusion gap ${fmt(d.gap, 0)}</span>`,
      "Tengah": (d) => `<b>Tengah, the newest town</b><span class="w">lowest score ${fmt(d.score, 0)}</span>: trees still growing`,
      "Woodlands": () => `<b>Woodlands</b><span class="g">6 tweaks: worst-served +2.8</span>`,
      "Punggol": () => `<b>Punggol</b><span class="g">coolest town surfaces</span>`,
    };
    el.insertAdjacentHTML("beforeend", Object.entries(txt).map(([t, f]) => `<div class="pin-card" style="left:${a[t].left}%;top:${a[t].top}%">${f(a[t])}</div>`).join(""));
  } catch (e) { /* the map image stands on its own */ }
}

async function credits() {
  try {
    const c = await getJSON("assets/img/photos/credits.json");
    $("#photocredits").innerHTML = Object.values(c).map((p) => `<li><a href="${p.source}">${p.title}</a> · ${p.author} · ${p.license}</li>`).join("");
  } catch (e) { /* credits stay in captions */ }
}

// ------------------------------------------------------------------ boot
(async function main() {
  chrome(); compare(); credits(); heroPins();
  const [meta, analysis, blocks, tw, tbcsv, cs] = await Promise.all([
    getJSON("data/meta.json"), getJSON("data/analysis.json"), getJSON("data/blocks.json"),
    getJSON("data/tweaks_woodlands.json"), fetch("data/tweaks_woodlands_blocks.csv").then((r) => r.text()), getJSON("data/case.json"),
  ]);
  state.blocks = blocks;
  pillarCards(meta); targets(analysis); valueChart(analysis); caseStudy(cs);
  $("#lstrmse").textContent = meta.lst_now_validation.rmse_c.toFixed(2); $("#m-rmse").textContent = meta.lst_now_validation.rmse_c.toFixed(2);
  $("#m-scenes").textContent = `${meta.lst_now_scenes} + ${meta.lst_then_scenes}`;
  atlas(meta, analysis); tweaks(tw, tbcsv);
  let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { renderTownCharts(); valueChart(analysis); caseStudy(cs); }, 200); });
})();

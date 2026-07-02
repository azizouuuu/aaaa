import { niceMax } from "./format.js";

const SVGNS = "http://www.w3.org/2000/svg";

function el(tag, attrs = {}, parent) {
  const e = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}

function htmlEl(tag, attrs = {}, parent) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else e.setAttribute(k, v);
  }
  if (parent) parent.appendChild(e);
  return e;
}

let tooltipEl = null;
function tooltip() {
  if (!tooltipEl) {
    tooltipEl = htmlEl("div", { class: "tooltip" }, document.body);
  }
  return tooltipEl;
}

function showTooltip(x, y, rows) {
  const t = tooltip();
  t.textContent = "";
  for (const r of rows) {
    const row = htmlEl("div", { class: "row" }, t);
    const key = htmlEl("span", { class: "name" }, row);
    if (r.swatch) {
      const sw = htmlEl("span", {
        style: `display:inline-block;width:9px;height:9px;border-radius:50%;` +
               `background:${r.swatch};margin-right:5px;vertical-align:middle;`,
      }, key);
      sw.textContent = "";
    }
    key.appendChild(document.createTextNode(r.label));
    const val = htmlEl("span", { class: "val" }, row);
    val.textContent = r.value;
  }
  t.style.display = "block";
  const pad = 14;
  let left = x + pad, top = y + pad;
  const vw = window.innerWidth, vh = window.innerHeight;
  if (left + 220 > vw) left = x - 220 - pad;
  if (top + 90 > vh) top = y - 90 - pad;
  t.style.left = left + "px";
  t.style.top = top + "px";
}
function hideTooltip() {
  if (tooltipEl) tooltipEl.style.display = "none";
}

function legend(container, items) {
  if (items.length < 2) return; // single series needs no legend box
  const wrap = htmlEl("div", { class: "legend" }, container);
  for (const it of items) {
    const item = htmlEl("div", { class: "item" }, wrap);
    const sw = htmlEl("span", {
      class: it.shape === "dot" ? "dot" : "swatch",
      style: `background:${it.color}`,
    }, item);
    sw.textContent = "";
    item.appendChild(document.createTextNode(it.label));
  }
}

function tableToggle(container, table) {
  const head = container.querySelector(".chart-head");
  const link = htmlEl("span", { class: "table-toggle" }, head || container);
  link.textContent = "Table view";
  table.classList.add("chart-table");
  link.addEventListener("click", () => {
    const show = !table.classList.contains("show");
    table.classList.toggle("show", show);
    link.textContent = show ? "Hide table" : "Table view";
  });
}

function buildTable(columns, rows) {
  const table = htmlEl("table");
  const thead = htmlEl("thead", {}, table);
  const htr = htmlEl("tr", {}, thead);
  for (const c of columns) {
    const th = htmlEl("th", {}, htr);
    th.textContent = c.label;
  }
  const tbody = htmlEl("tbody", {}, table);
  for (const row of rows) {
    const tr = htmlEl("tr", {}, tbody);
    for (const c of columns) {
      const td = htmlEl("td", { class: c.num ? "num" : "" }, tr);
      td.textContent = c.value(row);
    }
  }
  return table;
}

/**
 * Horizontal bar chart. rows: [{label, value, sub?, hub?}]. Single series ->
 * no legend box; color follows the entity's fixed role (export/import/etc),
 * never row rank.
 */
export function barChart(container, rows, opts) {
  container.textContent = "";
  const head = htmlEl("div", { class: "chart-head" }, container);
  if (opts.title) {
    const h = htmlEl("span", {}, head);
    h.textContent = opts.title;
  }
  const barH = 20, gap = 10, leftW = 130, rightPad = 70, width = opts.width || 640;
  const height = rows.length * (barH + gap) + gap;
  const plotW = width - leftW - rightPad;
  const max = niceMax(Math.max(1, ...rows.map((r) => r.value)));

  const svg = el("svg", {
    viewBox: `0 0 ${width} ${height}`, width: "100%",
    height, role: "img",
  }, container);

  rows.forEach((r, i) => {
    const y = gap + i * (barH + gap);
    const w = Math.max(0, (r.value / max) * plotW);
    const label = el("text", {
      x: leftW - 10, y: y + barH / 2 + 4, "text-anchor": "end",
      fill: "var(--text-secondary)", "font-size": 12.5,
    }, svg);
    label.textContent = r.label;

    const g = el("g", { style: "cursor:" + (opts.onClick ? "pointer" : "default") }, svg);
    el("rect", {
      x: leftW, y, width: plotW, height: barH, fill: "transparent",
    }, g); // hit target = full row width
    const bar = el("rect", {
      x: leftW, y, width: w, height: barH, rx: 4, ry: 4,
      fill: opts.color || "var(--series-export)",
    }, g);

    const valText = el("text", {
      x: leftW + w + 8, y: y + barH / 2 + 4, "font-size": 12.5,
      fill: "var(--text-primary)", "font-variant-numeric": "tabular-nums",
    }, svg);
    valText.textContent = opts.format(r.value);
    if (r.badge) {
      const badge = el("text", {
        x: leftW + w + 8 + valText.getComputedTextLength?.() + 8 || leftW + 60,
        y: y + barH / 2 + 4, "font-size": 11, fill: "var(--series-import)",
      }, svg);
      badge.textContent = r.badge;
    }

    g.addEventListener("pointermove", (e) => {
      bar.setAttribute("opacity", "0.85");
      showTooltip(e.clientX, e.clientY, [
        { label: r.label, value: opts.format(r.value), swatch: opts.color },
        ...(r.sub ? [{ label: r.subLabel || "detail", value: r.sub }] : []),
      ]);
    });
    g.addEventListener("pointerleave", () => { bar.setAttribute("opacity", "1"); hideTooltip(); });
    if (opts.onClick) g.addEventListener("click", () => opts.onClick(r));
  });

  if (opts.tableColumns) {
    const table = buildTable(opts.tableColumns, rows);
    container.appendChild(table);
    tableToggle(container, table);
  }
}

/**
 * Multi-series line chart. series: [{key,label,color,values:[{x,y}]}]
 * x assumed to be years (shared across series).
 */
export function lineChart(container, years, series, opts = {}) {
  container.textContent = "";
  const width = opts.width || 640, height = opts.height || 260;
  const padL = 56, padR = 16, padT = 16, padB = 28;
  const plotW = width - padL - padR, plotH = height - padT - padB;
  const allVals = series.flatMap((s) => s.values);
  const max = niceMax(Math.max(1, ...allVals));
  const n = years.length;
  const xAt = (i) => padL + (n === 1 ? plotW / 2 : (i / (n - 1)) * plotW);
  const yAt = (v) => padT + plotH - (v / max) * plotH;

  legend(container, series.map((s) => ({ label: s.label, color: s.color, shape: "line" })));

  const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, width: "100%", height }, container);

  // gridlines (4 steps) + y labels
  const steps = 4;
  for (let i = 0; i <= steps; i++) {
    const v = (max / steps) * i;
    const y = yAt(v);
    el("line", { x1: padL, x2: width - padR, y1: y, y2: y, stroke: "var(--grid)", "stroke-width": 1 }, svg);
    const t = el("text", { x: padL - 8, y: y + 4, "text-anchor": "end", "font-size": 11, fill: "var(--text-muted)" }, svg);
    t.textContent = opts.format ? opts.format(v) : v.toFixed(0);
  }
  years.forEach((y, i) => {
    const t = el("text", { x: xAt(i), y: height - 6, "text-anchor": "middle", "font-size": 11, fill: "var(--text-muted)" }, svg);
    t.textContent = y;
  });

  const crosshair = el("line", {
    x1: 0, x2: 0, y1: padT, y2: padT + plotH, stroke: "var(--baseline)", "stroke-width": 1,
    opacity: 0,
  }, svg);

  series.forEach((s) => {
    const points = s.values.map((v, i) => [xAt(i), yAt(v)]);
    const d = points.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
    el("path", { d, fill: "none", stroke: s.color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
    const last = points[points.length - 1];
    el("circle", { cx: last[0], cy: last[1], r: 4, fill: s.color, stroke: "var(--surface-1)", "stroke-width": 2 }, svg);
    const endLabel = el("text", {
      x: last[0] - 4, y: last[1] - 10, "text-anchor": "end", "font-size": 11.5, fill: "var(--text-primary)",
    }, svg);
    endLabel.textContent = opts.format ? opts.format(s.values[s.values.length - 1]) : s.values[s.values.length - 1];
  });

  const hitLayer = el("rect", { x: padL, y: padT, width: plotW, height: plotH, fill: "transparent" }, svg);
  hitLayer.addEventListener("pointermove", (e) => {
    const rect = svg.getBoundingClientRect();
    const relX = ((e.clientX - rect.left) / rect.width) * width;
    let idx = Math.round(((relX - padL) / plotW) * (n - 1));
    idx = Math.max(0, Math.min(n - 1, idx));
    crosshair.setAttribute("x1", xAt(idx));
    crosshair.setAttribute("x2", xAt(idx));
    crosshair.setAttribute("opacity", "1");
    showTooltip(e.clientX, e.clientY, [
      { label: String(years[idx]), value: "" },
      ...series.map((s) => ({ label: s.label, value: opts.format ? opts.format(s.values[idx]) : s.values[idx], swatch: s.color })),
    ]);
  });
  hitLayer.addEventListener("pointerleave", () => { crosshair.setAttribute("opacity", "0"); hideTooltip(); });

  if (opts.tableColumns) {
    const rows = years.map((y, i) => ({ year: y, ...Object.fromEntries(series.map((s) => [s.key, s.values[i]])) }));
    const table = buildTable(opts.tableColumns, rows);
    container.appendChild(table);
    tableToggle(container, table);
  }
}

/** 12-point sparkline: de-emphasis gray with the current period in the accent. */
export function sparkline(values, color, width = 96, height = 26) {
  const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, width, height });
  if (!values.length) return svg;
  const max = Math.max(1, ...values), min = Math.min(0, ...values);
  const span = max - min || 1;
  const n = values.length;
  const xAt = (i) => (n === 1 ? width / 2 : (i / (n - 1)) * width);
  const yAt = (v) => height - ((v - min) / span) * height;
  const pts = values.map((v, i) => [xAt(i), yAt(v)]);
  const d = pts.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  el("path", { d, fill: "none", stroke: "var(--text-muted)", "stroke-width": 1.5, "stroke-linejoin": "round" }, svg);
  const last = pts[pts.length - 1];
  el("circle", { cx: last[0], cy: last[1], r: 3, fill: color }, svg);
  return svg;
}

export { buildTable, htmlEl };

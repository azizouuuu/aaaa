import { api } from "../api.js";
import { htmlEl, lineChart } from "../charts.js";
import { renderFilters } from "../filters.js";
import { fmtTonnes, fmtUsd } from "../format.js";

export async function render(container, params) {
  container.textContent = "";
  const filterHost = htmlEl("div", {}, container);
  const card = htmlEl("div", { class: "card" }, container);
  const title = htmlEl("h2", {}, card);
  const sub = htmlEl("div", { class: "sub" }, card);
  const metricRow = htmlEl("div", { class: "flow-toggle", style: "margin-bottom:12px;" }, card);
  const bWgt = htmlEl("button", { class: "active" }, metricRow);
  bWgt.textContent = "Volume (tonnes)";
  const bVal = htmlEl("button", {}, metricRow);
  bVal.textContent = "Value (USD)";
  const chartHost = htmlEl("div", {}, card);

  const { state, meta } = await renderFilters(filterHost, { cmd: params.cmd }, {
    hideFlow: true, hideYear: true, onChange: (s) => load(s),
  });

  let metric = "net_wgt_t";
  bVal.addEventListener("click", () => { metric = "value_usd"; paintMetric(); load(state); });
  bWgt.addEventListener("click", () => { metric = "net_wgt_t"; paintMetric(); load(state); });
  function paintMetric() {
    bVal.classList.toggle("active", metric === "value_usd");
    bWgt.classList.toggle("active", metric === "net_wgt_t");
  }

  async function load(s) {
    const cmd = meta.commodities.find((c) => c.slug === s.cmd);
    title.textContent = `World trade trend — ${cmd.name}`;
    sub.textContent = `${cmd.hs_label} · ${meta.years[0]}–${meta.years[meta.years.length - 1]}`;
    const { data } = await api("/trend/world", { cmd: s.cmd });
    const fmt = metric === "value_usd" ? fmtUsd : fmtTonnes;
    const series = [
      { key: "exports", label: "Exports", color: "var(--series-export)", values: data.exports.map((p) => p[metric] || 0) },
      { key: "imports", label: "Imports", color: "var(--series-import)", values: data.imports.map((p) => p[metric] || 0) },
    ];
    lineChart(chartHost, data.years, series, {
      format: fmt,
      tableColumns: [
        { label: "Year", value: (r) => r.year },
        { label: "Exports", value: (r) => fmt(r.exports), num: true },
        { label: "Imports", value: (r) => fmt(r.imports), num: true },
      ],
    });
  }
  await load(state);
}

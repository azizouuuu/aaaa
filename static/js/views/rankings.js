import { api } from "../api.js";
import { barChart, htmlEl } from "../charts.js";
import { renderFilters } from "../filters.js";
import { fmtPct, fmtTonnes, fmtUnitValue, fmtUsd } from "../format.js";

export async function render(container, params) {
  container.textContent = "";
  const filterHost = htmlEl("div", {}, container);
  const card = htmlEl("div", { class: "card" }, container);
  const title = htmlEl("h2", {}, card);
  const sub = htmlEl("div", { class: "sub" }, card);
  const chartHost = htmlEl("div", {}, card);

  const { state, meta } = await renderFilters(filterHost, params, {
    onChange: (s) => load(s),
  });

  async function load(s) {
    const cmd = meta.commodities.find((c) => c.slug === s.cmd);
    title.textContent = `Top ${s.flow === "X" ? "exporters" : "importers"} — ${cmd.name}`;
    sub.textContent = `${cmd.hs_label} · ${s.year}`;
    const { data } = await api("/rankings", { cmd: s.cmd, flow: s.flow, year: s.year, top: 15 });
    const rows = data.rows.map((r) => ({
      label: r.name, value: r.value_usd,
      sub: `${fmtTonnes(r.net_wgt_t)} · ${fmtUnitValue(r.unit_value)} · ${fmtPct(r.share)} of world`,
      subLabel: "detail",
      onClickParams: r.iso3,
    }));
    barChart(chartHost, rows, {
      format: fmtUsd,
      color: s.flow === "X" ? "var(--series-export)" : "var(--series-import)",
      onClick: (r) => { location.hash = `#/partners?cmd=${s.cmd}&flow=${s.flow}&year=${s.year}&reporter=${r.onClickParams}`; },
      tableColumns: [
        { label: "#", value: (r) => rows.indexOf(r) + 1 },
        { label: "Country", value: (r) => r.label },
        { label: "Value", value: (r) => fmtUsd(r.value), num: true },
        { label: "Detail", value: (r) => r.sub },
      ],
    });
  }
  await load(state);
}

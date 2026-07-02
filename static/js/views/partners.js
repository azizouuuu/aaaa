import { api, getMeta } from "../api.js";
import { barChart, htmlEl, lineChart } from "../charts.js";
import { renderFilters } from "../filters.js";
import { fmtPct, fmtTonnes, fmtUnitValue, fmtUsd } from "../format.js";

export async function render(container, params) {
  container.textContent = "";
  const filterHost = htmlEl("div", {}, container);
  const repWrap = htmlEl("div", { class: "filters" }, container);
  htmlEl("label", {}, repWrap).textContent = "Reporter";
  const repSel = htmlEl("select", {}, repWrap);

  const card = htmlEl("div", { class: "card" }, container);
  const title = htmlEl("h2", {}, card);
  const sub = htmlEl("div", { class: "sub" }, card);
  const chartHost = htmlEl("div", {}, card);

  const trendCard = htmlEl("div", { class: "card" }, container);
  htmlEl("h2", {}, trendCard).textContent = "Reporter trend (world total)";
  const trendHost = htmlEl("div", {}, trendCard);

  const meta = await getMeta();
  for (const [iso, name] of Object.entries(meta.countries)) {
    if (iso === "WLD") continue;
    const o = htmlEl("option", { value: iso }, repSel);
    o.textContent = name;
  }
  repSel.value = meta.countries[params.reporter] ? params.reporter : "IDN";

  const { state } = await renderFilters(filterHost, params, { onChange: () => load() });
  repSel.addEventListener("change", load);

  async function load() {
    const s = state;
    const reporter = repSel.value;
    const cmd = meta.commodities.find((c) => c.slug === s.cmd);
    const repName = meta.countries[reporter];
    title.textContent = `${repName} — ${s.flow === "X" ? "export" : "import"} partners`;
    sub.textContent = `${cmd.name} (${cmd.hs_label}) · ${s.year}`;

    const { data } = await api("/partners", { cmd: s.cmd, reporter, flow: s.flow, year: s.year, top: 12 });
    const rows = data.rows.map((r) => ({
      label: r.name, value: r.value_usd, badge: r.is_hub ? "hub" : null,
      sub: `${fmtTonnes(r.net_wgt_t)} · ${fmtUnitValue(r.unit_value)} · ${fmtPct(r.share)}`,
    }));
    barChart(chartHost, rows, {
      format: fmtUsd,
      color: s.flow === "X" ? "var(--series-export)" : "var(--series-import)",
      tableColumns: [
        { label: "Partner", value: (r) => r.label },
        { label: "Value", value: (r) => fmtUsd(r.value), num: true },
        { label: "Hub", value: (r) => (r.badge ? "yes" : "") },
        { label: "Detail", value: (r) => r.sub },
      ],
    });

    const trend = await api("/partners/trend", { cmd: s.cmd, reporter, flow: s.flow });
    lineChart(trendHost, trend.data.rows.map((r) => r.year), [
      {
        key: "value", label: `${repName} ${s.flow === "X" ? "exports" : "imports"}`,
        color: s.flow === "X" ? "var(--series-export)" : "var(--series-import)",
        values: trend.data.rows.map((r) => r.value_usd),
      },
    ], { format: fmtUsd });
  }
  await load();
}

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
  const note = htmlEl("div", { class: "muted", style: "margin-bottom:8px;" }, card);
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

  const { state } = await renderFilters(filterHost, params, { showMetric: true, onChange: () => load() });
  repSel.addEventListener("change", load);

  async function load() {
    const s = state;
    const byWeight = s.metric === "wgt";
    const reporter = repSel.value;
    const cmd = meta.commodities.find((c) => c.slug === s.cmd);
    const repName = meta.countries[reporter];
    title.textContent = `${repName} — ${s.flow === "X" ? "export" : "import"} partners`;
    sub.textContent = `${cmd.name} (${cmd.hs_label}) · ${s.year} · ranked by ${byWeight ? "volume (tonnes)" : "value (USD)"}`;

    const { data } = await api("/partners", {
      cmd: s.cmd, reporter, flow: s.flow, year: s.year, top: 12, metric: s.metric,
    });
    note.textContent = data.excluded_no_weight
      ? `${data.excluded_no_weight} partners omitted — no weight reported for this flow/year.`
      : "";
    const fmt = byWeight ? fmtTonnes : fmtUsd;
    const rows = data.rows.map((r) => ({
      label: r.name, value: byWeight ? r.net_wgt_t : r.value_usd, badge: r.is_hub ? "hub" : null,
      sub: byWeight
        ? `${fmtUsd(r.value_usd)} · ${fmtUnitValue(r.unit_value)} · ${fmtPct(r.share)}`
        : `${fmtTonnes(r.net_wgt_t)} · ${fmtUnitValue(r.unit_value)} · ${fmtPct(r.share)}`,
    }));
    barChart(chartHost, rows, {
      format: fmt,
      color: s.flow === "X" ? "var(--series-export)" : "var(--series-import)",
      tableColumns: [
        { label: "Partner", value: (r) => r.label },
        { label: byWeight ? "Volume" : "Value", value: (r) => fmt(r.value), num: true },
        { label: "Hub", value: (r) => (r.badge ? "yes" : "") },
        { label: "Detail", value: (r) => r.sub },
      ],
    });

    const trend = await api("/partners/trend", { cmd: s.cmd, reporter, flow: s.flow });
    lineChart(trendHost, trend.data.rows.map((r) => r.year), [
      {
        key: "value", label: `${repName} ${s.flow === "X" ? "exports" : "imports"}`,
        color: s.flow === "X" ? "var(--series-export)" : "var(--series-import)",
        values: trend.data.rows.map((r) => (byWeight ? r.net_wgt_t : r.value_usd) || 0),
      },
    ], { format: fmt });
  }
  await load();
}

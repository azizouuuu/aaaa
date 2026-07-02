import { api } from "../api.js";
import { barChart, htmlEl } from "../charts.js";
import { renderFilters } from "../filters.js";
import { fmtPct, fmtTonnes, fmtUnitValue, fmtUsd } from "../format.js";

export async function render(container, params) {
  container.textContent = "";
  const filterHost = htmlEl("div", {}, container);
  const euWrap = htmlEl("label", { style: "display:flex;align-items:center;gap:6px;font-size:13px;color:var(--text-secondary);margin-bottom:14px;" }, container);
  const euCheck = htmlEl("input", { type: "checkbox" }, euWrap);
  euWrap.appendChild(document.createTextNode("Show EU27 as one bloc (excludes intra-EU trade)"));

  const card = htmlEl("div", { class: "card" }, container);
  const title = htmlEl("h2", {}, card);
  const sub = htmlEl("div", { class: "sub" }, card);
  const note = htmlEl("div", { class: "muted", style: "margin-bottom:8px;" }, card);
  const chartHost = htmlEl("div", {}, card);

  const { state, meta } = await renderFilters(filterHost, params, {
    showMetric: true, onChange: (s) => load(s),
  });
  euCheck.checked = params.eu_as_bloc === "true" || params.eu_as_bloc === true;
  euCheck.addEventListener("change", () => load(state));

  async function load(s) {
    const cmd = meta.commodities.find((c) => c.slug === s.cmd);
    const byWeight = s.metric === "wgt";
    const euAsBloc = euCheck.checked;
    title.textContent = `Top ${s.flow === "X" ? "exporters" : "importers"} — ${cmd.name}`;
    sub.textContent = `${cmd.hs_label} · ${s.year} · ranked by ${byWeight ? "volume (tonnes)" : "value (USD)"}`;
    const { data } = await api("/rankings", {
      cmd: s.cmd, flow: s.flow, year: s.year, top: 15, metric: s.metric, eu_as_bloc: euAsBloc,
    });
    const notes = [];
    if (data.excluded_no_weight) {
      notes.push(`${data.excluded_no_weight} countries omitted — no weight reported for this flow/year.`);
    }
    notes.push(
      euAsBloc
        ? "EU27 shown as one consolidated entity — intra-EU trade excluded."
        : "World total excludes intra-EU trade (Rotterdam effect); EU country rows below may still include their own intra-EU re-exports."
    );
    note.textContent = notes.join(" ");
    const fmt = byWeight ? fmtTonnes : fmtUsd;
    const rows = data.rows.map((r) => ({
      label: r.name + (r.is_eu_member ? " *" : ""), value: byWeight ? r.net_wgt_t : r.value_usd,
      sub: byWeight
        ? `${fmtUsd(r.value_usd)} · ${fmtUnitValue(r.unit_value)} · ${fmtPct(r.share)} of world`
        : `${fmtTonnes(r.net_wgt_t)} · ${fmtUnitValue(r.unit_value)} · ${fmtPct(r.share)} of world`,
      subLabel: "detail",
      onClickParams: r.iso3,
      isBloc: r.is_bloc,
    }));
    barChart(chartHost, rows, {
      format: fmt,
      color: s.flow === "X" ? "var(--series-export)" : "var(--series-import)",
      onClick: (r) => { location.hash = `#/partners?cmd=${s.cmd}&flow=${s.flow}&year=${s.year}&reporter=${r.onClickParams}`; },
      tableColumns: [
        { label: "#", value: (r) => rows.indexOf(r) + 1 },
        { label: "Country", value: (r) => r.label },
        { label: byWeight ? "Volume" : "Value", value: (r) => fmt(r.value), num: true },
        { label: "Detail", value: (r) => r.sub },
      ],
    });
    if (rows.some((r) => r.label.endsWith(" *"))) {
      const legend = htmlEl("div", { class: "muted", style: "margin-top:8px;" }, chartHost);
      legend.textContent = "* EU member — total may include intra-EU re-exports.";
    }
  }
  await load(state);
}

import { api } from "../api.js";
import { barChart, htmlEl } from "../charts.js";
import { renderFilters } from "../filters.js";
import { fmtPct, fmtUsd } from "../format.js";

export async function render(container, params) {
  container.textContent = "";
  const intro = htmlEl("div", { class: "disclaimer-box" }, container);
  intro.textContent =
    "China's customs portal is not freely automatable (registration requires " +
    "mainland real-name verification) and its direct reporting to UN Comtrade " +
    "has been sparse — so China's flows are triangulated from the demand side: " +
    "what a panel of major buyer countries reports trading WITH China. Mirror " +
    "imports are CIF (~5–10% above FOB) and only listed destinations count.";

  const filterHost = htmlEl("div", {}, container);

  const kpi = htmlEl("div", { class: "card" }, container);
  const kpiTitle = htmlEl("h2", {}, kpi);
  const kpiSub = htmlEl("div", { class: "sub" }, kpi);
  const chips = htmlEl("div", {}, kpi);
  const notes = htmlEl("ul", {
    style: "margin:10px 0 0;padding-left:18px;color:var(--text-secondary);font-size:13px;",
  }, kpi);

  const card = htmlEl("div", { class: "card" }, container);
  htmlEl("h2", {}, card).textContent = "Mirror panel breakdown";
  const sub = htmlEl("div", { class: "sub" }, card);
  const chartHost = htmlEl("div", {}, card);

  const { state, meta } = await renderFilters(filterHost, params, {
    onChange: () => load(),
  });

  async function load() {
    const s = state;
    const cmd = meta.commodities.find((c) => c.slug === s.cmd);
    const { data } = await api("/china-mirror", { cmd: s.cmd, year: s.year, flow: s.flow });

    kpiTitle.textContent = `China — ${cmd.name}, ${s.flow === "X" ? "exports" : "imports"} ${s.year}`;
    kpiSub.textContent = `${cmd.hs_label} · ${data.breakdown.length} of the mirror-panel reporters show flows`;

    chips.textContent = "";
    const mirrorChip = htmlEl("span", { class: "chip" }, chips);
    mirrorChip.appendChild(document.createTextNode("Mirror panel total "));
    htmlEl("b", {}, mirrorChip).textContent = fmtUsd(data.mirror_total_usd);
    const ownChip = htmlEl("span", { class: "chip" }, chips);
    ownChip.appendChild(document.createTextNode("China's own declaration "));
    htmlEl("b", {}, ownChip).textContent = fmtUsd(data.own_declared_usd);
    if (data.ratio != null) {
      const cls = data.ratio < 0.75 || data.ratio > 1.25 ? "conf-low" : "conf-high";
      const ratioChip = htmlEl("span", { class: `chip ${cls}` }, chips);
      ratioChip.appendChild(document.createTextNode("own / mirror "));
      htmlEl("b", {}, ratioChip).textContent = fmtPct(data.ratio);
    }

    notes.textContent = "";
    for (const n of data.notes) htmlEl("li", {}, notes).textContent = n;

    sub.textContent = s.flow === "X"
      ? "What each mirror reporter says it imported from China"
      : "What each mirror reporter says it exported to China";
    const rows = data.breakdown.map((r) => ({ label: r.name, value: r.value_usd }));
    barChart(chartHost, rows, {
      format: fmtUsd,
      color: "var(--series-import)",
      tableColumns: [
        { label: "Mirror reporter", value: (r) => r.label },
        { label: "Value", value: (r) => fmtUsd(r.value), num: true },
      ],
    });
  }
  await load();
}

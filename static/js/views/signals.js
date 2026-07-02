import { api } from "../api.js";
import { htmlEl } from "../charts.js";
import { renderFilters } from "../filters.js";
import { fmtPct, fmtUnitValue, fmtUsd } from "../format.js";

export async function render(container, params) {
  container.textContent = "";
  const intro = htmlEl("div", { class: "disclaimer-box" }, container);
  intro.textContent =
    "Heuristic disaggregation: several HS headings mix multiple feedstocks. " +
    "These estimates combine unit-value bands, origin priors, destination-hub " +
    "share, and mirror-data consistency — they are NOT measured splits. See " +
    "Methodology for the full basis.";

  const filterHost = htmlEl("div", {}, container);
  const card = htmlEl("div", { class: "card" }, container);
  const title = htmlEl("h2", {}, card);
  const sub = htmlEl("div", { class: "sub" }, card);
  const list = htmlEl("div", {}, card);

  const { state, meta } = await renderFilters(filterHost, params, {
    commodityFilter: (c) => c.shared_heading,
    onChange: () => load(),
  });

  async function load() {
    const s = state;
    const cmd = meta.commodities.find((c) => c.slug === s.cmd);
    title.textContent = `Corridor disaggregation — ${cmd.name}`;
    sub.textContent = `${cmd.hs_label} shares: ${cmd.cohabitants.join(", ")}`;
    list.textContent = "";
    const { data } = await api("/signals/summary", { cmd: s.cmd, flow: s.flow, year: s.year, top: 10 });
    if (!data.rows.length) {
      htmlEl("p", { class: "muted" }, list).textContent = "No corridors found for this selection.";
      return;
    }
    for (const row of data.rows) {
      const item = htmlEl("div", { style: "padding:14px 0;border-bottom:1px solid var(--border);" }, list);
      const head = htmlEl("div", { style: "display:flex;justify-content:space-between;align-items:baseline;" }, item);
      const h = htmlEl("strong", {}, head);
      h.textContent = `${row.reporter.name} → ${row.partner.name}`;
      const val = htmlEl("span", { class: "muted" }, head);
      val.textContent = `${fmtUsd(row.value_usd)} · ${fmtUnitValue(row.unit_value)}`;

      const chipRow = htmlEl("div", {}, item);
      for (const c of row.candidates) {
        const chip = htmlEl("span", { class: "chip" }, chipRow);
        chip.appendChild(document.createTextNode(c.label + " "));
        const b = htmlEl("b", {}, chip);
        b.textContent = fmtPct(c.prob);
      }
      const conf = htmlEl("span", { class: `chip conf-${row.confidence}` }, chipRow);
      conf.textContent = `${row.confidence} confidence`;

      const explain = htmlEl("ul", { style: "margin:8px 0 0;padding-left:18px;color:var(--text-secondary);font-size:13px;" }, item);
      for (const e of row.explanations) {
        htmlEl("li", {}, explain).textContent = e;
      }
    }
  }
  await load();
}

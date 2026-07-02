import { api } from "../api.js";
import { htmlEl } from "../charts.js";

export async function render(container) {
  container.textContent = "";
  const { data } = await api("/methodology");

  const hvo = htmlEl("div", { class: "card" }, container);
  htmlEl("h2", {}, hvo).textContent = "HVO / SAF data gap";
  htmlEl("p", { class: "sub" }, hvo).textContent = data.hvo_saf_note;

  if (data.eu_bloc) {
    const eu = htmlEl("div", { class: "card" }, container);
    htmlEl("h2", {}, eu).textContent = "Intra-EU double-counting (the Rotterdam effect)";
    htmlEl("p", { class: "sub" }, eu).textContent = data.eu_bloc.problem;
    htmlEl("p", { class: "sub" }, eu).textContent = data.eu_bloc.fix;
    htmlEl("p", { class: "sub" }, eu).textContent = data.eu_bloc.uk_note;
    htmlEl("p", { class: "sub" }, eu).textContent = data.eu_bloc.features;
  }

  const weights = htmlEl("div", { class: "card" }, container);
  htmlEl("h2", {}, weights).textContent = "Disaggregation signal weights";
  htmlEl("div", { class: "sub" }, weights).textContent =
    `Unit-value band ${(data.signal_weights.unit_value * 100).toFixed(0)}% · ` +
    `Origin prior ${(data.signal_weights.origin * 100).toFixed(0)}% · ` +
    `Destination hub ${(data.signal_weights.destination * 100).toFixed(0)}% · ` +
    `Mirror consistency ${(data.signal_weights.mirror * 100).toFixed(0)}% ` +
    `(bands are ${data.band_vintage} — review before trusting)`;

  const shared = htmlEl("div", { class: "card" }, container);
  htmlEl("h2", {}, shared).textContent = "Shared HS headings & candidates";
  for (const group of data.shared_headings) {
    const h3 = htmlEl("h3", { style: "font-size:13.5px;margin:14px 0 6px;" }, shared);
    h3.textContent = group.slug;
    const table = htmlEl("table", {}, shared);
    const thead = htmlEl("thead", {}, table);
    const htr = htmlEl("tr", {}, thead);
    for (const c of ["Candidate", "Fuel-bound", "Band ($/t)", "Top origins"]) {
      htmlEl("th", {}, htr).textContent = c;
    }
    const tbody = htmlEl("tbody", {}, table);
    for (const cand of group.candidates) {
      const tr = htmlEl("tr", {}, tbody);
      htmlEl("td", {}, tr).textContent = cand.label;
      htmlEl("td", {}, tr).textContent = cand.fuel_bound ? "yes" : "no";
      htmlEl("td", { class: "num" }, tr).textContent =
        `${cand.band_usd_per_t[0]}–${cand.band_usd_per_t[1]}`;
      htmlEl("td", {}, tr).textContent = cand.top_origins.map(([iso, p]) => `${iso} ${(p * 100).toFixed(0)}%`).join(", ");
    }
  }

  const national = htmlEl("div", { class: "card" }, container);
  htmlEl("h2", {}, national).textContent = "National tariff-line registry (drill-down targets)";
  htmlEl("div", { class: "sub" }, national).textContent =
    "Indicative 8–10 digit lines for the progressive per-country pipelines. Verify against the current schedule before operational use.";
  const ntable = htmlEl("table", {}, national);
  const nthead = htmlEl("thead", {}, ntable);
  const nhtr = htmlEl("tr", {}, nthead);
  for (const c of ["Jurisdiction", "Commodity", "Lines"]) htmlEl("th", {}, nhtr).textContent = c;
  const ntbody = htmlEl("tbody", {}, ntable);
  for (const row of data.national_lines) {
    const tr = htmlEl("tr", {}, ntbody);
    htmlEl("td", {}, tr).textContent = row.jurisdiction;
    htmlEl("td", {}, tr).textContent = row.commodity;
    htmlEl("td", {}, tr).textContent = row.lines.map((l) => `${l.code} (${l.system})`).join("; ");
  }

  const roadmap = htmlEl("div", { class: "card" }, container);
  htmlEl("h2", {}, roadmap).textContent = "Pipeline roadmap";
  const rtable = htmlEl("table", {}, roadmap);
  const rthead = htmlEl("thead", {}, rtable);
  const rhtr = htmlEl("tr", {}, rthead);
  for (const c of ["Phase", "Pipeline", "Status"]) htmlEl("th", {}, rhtr).textContent = c;
  const rtbody = htmlEl("tbody", {}, rtable);
  for (const row of data.pipeline_roadmap) {
    const tr = htmlEl("tr", {}, rtbody);
    htmlEl("td", {}, tr).textContent = row.phase;
    htmlEl("td", {}, tr).textContent = row.pipeline;
    htmlEl("td", {}, tr).textContent = row.status;
  }

  const sources = htmlEl("div", { class: "card" }, container);
  htmlEl("h2", {}, sources).textContent = "Sources";
  const ul = htmlEl("ul", {}, sources);
  for (const s of data.sources) {
    const li = htmlEl("li", {}, ul);
    li.textContent = `${s.name} — ${s.notes}`;
  }
}

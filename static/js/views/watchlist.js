import { api, getMeta } from "../api.js";
import { htmlEl, sparkline } from "../charts.js";
import { fmtPct, fmtTonnes, fmtUsd } from "../format.js";

export async function render(container, params) {
  container.textContent = "";
  const filterHost = htmlEl("div", { class: "filters" }, container);
  const tabWrap = htmlEl("span", { class: "flow-toggle" }, filterHost);
  const bAsia = htmlEl("button", {}, tabWrap);
  bAsia.textContent = "Asia";
  const bSam = htmlEl("button", {}, tabWrap);
  bSam.textContent = "South America";

  const yWrap = htmlEl("span", {}, filterHost);
  htmlEl("label", {}, yWrap).textContent = "Year";
  const ysel = htmlEl("select", {}, yWrap);

  const metricWrap = htmlEl("span", { class: "flow-toggle" }, filterHost);
  const bWgt = htmlEl("button", {}, metricWrap);
  bWgt.textContent = "Volume (t)";
  const bUsd = htmlEl("button", {}, metricWrap);
  bUsd.textContent = "Value ($)";

  const card = htmlEl("div", { class: "card" }, container);
  const title = htmlEl("h2", {}, card);
  const sub = htmlEl("div", { class: "sub" }, card);
  const note = htmlEl("div", { class: "muted", style: "margin-bottom:8px;" }, card);
  const body = htmlEl("div", {}, card);

  const meta = await getMeta();
  for (const y of meta.years) htmlEl("option", { value: y }, ysel).textContent = y;
  ysel.value = params.year || 2024;

  let region = params.region || "asia";
  let metric = params.metric || "wgt";
  function paintTabs() {
    bAsia.classList.toggle("active", region === "asia");
    bSam.classList.toggle("active", region === "sam");
  }
  function paintMetric() {
    bWgt.classList.toggle("active", metric === "wgt");
    bUsd.classList.toggle("active", metric === "usd");
  }
  paintTabs();
  paintMetric();
  bAsia.addEventListener("click", () => { region = "asia"; paintTabs(); load(); });
  bSam.addEventListener("click", () => { region = "sam"; paintTabs(); load(); });
  bWgt.addEventListener("click", () => { metric = "wgt"; paintMetric(); load(); });
  bUsd.addEventListener("click", () => { metric = "usd"; paintMetric(); load(); });
  ysel.addEventListener("change", load);

  async function load() {
    const year = Number(ysel.value);
    const byWeight = metric === "wgt";
    const fmt = byWeight ? fmtTonnes : fmtUsd;
    const { data } = await api("/watchlist", { region, year, metric });
    title.textContent = `${data.region} — feedstock export watchlist`;
    sub.textContent = `Total waste-residue & crop-oil feedstock exports · ${year} · ranked by ${byWeight ? "volume (tonnes)" : "value (USD)"}`;
    const missing = data.rows.filter((r) => r.metric_value == null).length;
    note.textContent = byWeight && missing
      ? `${missing} countries show no volume for this year (no weight reported).`
      : "";
    body.textContent = "";
    const table = htmlEl("table", {}, body);
    const thead = htmlEl("thead", {}, table);
    const htr = htmlEl("tr", {}, thead);
    for (const h of ["Country", byWeight ? "Volume" : "Value", "YoY", "Trend", "Top commodities"]) {
      htmlEl("th", {}, htr).textContent = h;
    }
    const tbody = htmlEl("tbody", {}, table);
    for (const row of data.rows) {
      const tr = htmlEl("tr", {}, tbody);
      const nameTd = htmlEl("td", {}, tr);
      const link = htmlEl("a", { class: "rowlink" }, nameTd);
      link.textContent = row.name;
      link.addEventListener("click", () => {
        location.hash = `#/partners?cmd=${row.top_commodities[0]?.slug || "uco"}&flow=X&year=${year}&reporter=${row.iso3}`;
      });
      htmlEl("td", { class: "num" }, tr).textContent = fmt(row.metric_value);
      const yoyTd = htmlEl("td", { class: "num" }, tr);
      if (row.yoy != null) {
        yoyTd.textContent = fmtPct(row.yoy, true);
        yoyTd.style.color = row.yoy >= 0 ? "var(--good)" : "var(--critical)";
      } else {
        yoyTd.textContent = "—";
      }
      const sparkTd = htmlEl("td", {}, tr);
      const sparkValues = row.by_year.map((p) => (byWeight ? p.net_wgt_t : p.value_usd) || 0);
      sparkTd.appendChild(sparkline(sparkValues, "var(--series-export)"));
      const topTd = htmlEl("td", {}, tr);
      topTd.textContent = row.top_commodities.map((c) => c.name).join(", ");
    }
  }
  await load();
}

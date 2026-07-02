import { api, getMeta } from "../api.js";
import { htmlEl, sparkline } from "../charts.js";
import { fmtPct, fmtUsd } from "../format.js";

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

  const card = htmlEl("div", { class: "card" }, container);
  const title = htmlEl("h2", {}, card);
  const sub = htmlEl("div", { class: "sub" }, card);
  const body = htmlEl("div", {}, card);

  const meta = await getMeta();
  for (const y of meta.years) htmlEl("option", { value: y }, ysel).textContent = y;
  ysel.value = params.year || 2024;

  let region = params.region || "asia";
  function paintTabs() {
    bAsia.classList.toggle("active", region === "asia");
    bSam.classList.toggle("active", region === "sam");
  }
  paintTabs();
  bAsia.addEventListener("click", () => { region = "asia"; paintTabs(); load(); });
  bSam.addEventListener("click", () => { region = "sam"; paintTabs(); load(); });
  ysel.addEventListener("change", load);

  async function load() {
    const year = Number(ysel.value);
    const { data } = await api("/watchlist", { region, year });
    title.textContent = `${data.region} — feedstock export watchlist`;
    sub.textContent = `Total waste-residue & crop-oil feedstock exports · ${year}`;
    body.textContent = "";
    const table = htmlEl("table", {}, body);
    const thead = htmlEl("thead", {}, table);
    const htr = htmlEl("tr", {}, thead);
    for (const h of ["Country", "Value", "YoY", "Trend", "Top commodities"]) {
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
      htmlEl("td", { class: "num" }, tr).textContent = fmtUsd(row.value_usd);
      const yoyTd = htmlEl("td", { class: "num" }, tr);
      if (row.yoy != null) {
        yoyTd.textContent = fmtPct(row.yoy, true);
        yoyTd.style.color = row.yoy >= 0 ? "var(--good)" : "var(--critical)";
      } else {
        yoyTd.textContent = "—";
      }
      const sparkTd = htmlEl("td", {}, tr);
      sparkTd.appendChild(sparkline(row.by_year.map((p) => p.value_usd), "var(--series-export)"));
      const topTd = htmlEl("td", {}, tr);
      topTd.textContent = row.top_commodities.map((c) => c.name).join(", ");
    }
  }
  await load();
}

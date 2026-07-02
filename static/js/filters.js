import { getMeta } from "./api.js";
import { htmlEl } from "./charts.js";

/** Renders a commodity <select> grouped by category, a flow toggle, and a
 * year <select> into `container`, calling onChange(state) whenever any
 * control changes. Returns the current state object (mutated in place). */
export async function renderFilters(container, initial, opts = {}) {
  const meta = await getMeta();
  const state = { cmd: initial.cmd, flow: initial.flow || "X", year: initial.year || 2024 };
  container.textContent = "";
  const bar = htmlEl("div", { class: "filters" }, container);

  const cmdWrap = htmlEl("span", {}, bar);
  htmlEl("label", {}, cmdWrap).textContent = "Commodity";
  const sel = htmlEl("select", {}, cmdWrap);
  const pool = opts.commodityFilter
    ? meta.commodities.filter(opts.commodityFilter)
    : meta.commodities;
  const groups = {};
  for (const c of pool) (groups[c.group] ||= []).push(c);
  for (const [group, list] of Object.entries(groups)) {
    const og = htmlEl("optgroup", { label: meta.groups[group] || group }, sel);
    for (const c of list) {
      const o = htmlEl("option", { value: c.slug }, og);
      o.textContent = c.name + (c.shared_heading ? " *" : "");
    }
  }
  sel.value = pool.some((c) => c.slug === state.cmd) ? state.cmd : pool[0]?.slug;
  state.cmd = sel.value;
  sel.addEventListener("change", () => { state.cmd = sel.value; opts.onChange(state); });

  if (!opts.hideFlow) {
    const flowWrap = htmlEl("span", { class: "flow-toggle" }, bar);
    const bx = htmlEl("button", {}, flowWrap);
    bx.textContent = "Exports";
    const bm = htmlEl("button", {}, flowWrap);
    bm.textContent = "Imports";
    const paint = () => {
      bx.classList.toggle("active", state.flow === "X");
      bm.classList.toggle("active", state.flow === "M");
    };
    paint();
    bx.addEventListener("click", () => { state.flow = "X"; paint(); opts.onChange(state); });
    bm.addEventListener("click", () => { state.flow = "M"; paint(); opts.onChange(state); });
  }

  if (!opts.hideYear) {
    const yWrap = htmlEl("span", {}, bar);
    htmlEl("label", {}, yWrap).textContent = "Year";
    const ysel = htmlEl("select", {}, yWrap);
    for (const y of meta.years) {
      const o = htmlEl("option", { value: y }, ysel);
      o.textContent = y;
    }
    ysel.value = state.year;
    ysel.addEventListener("change", () => { state.year = Number(ysel.value); opts.onChange(state); });
  }

  if (pool.find((c) => c.slug === state.cmd)?.shared_heading) {
    const note = htmlEl("span", { class: "muted" }, bar);
    note.textContent = "* shared HS heading — see Signals";
  }

  return { state, meta };
}

const routes = {
  rankings: () => import("./views/rankings.js"),
  trend: () => import("./views/trend.js"),
  partners: () => import("./views/partners.js"),
  watchlist: () => import("./views/watchlist.js"),
  signals: () => import("./views/signals.js"),
  china: () => import("./views/china.js"),
  methodology: () => import("./views/methodology.js"),
};
const DEFAULT_PARAMS = { cmd: "uco", flow: "X", year: 2024 };

function parseHash() {
  const hash = location.hash.replace(/^#\/?/, "");
  const [path, query] = hash.split("?");
  const params = { ...DEFAULT_PARAMS };
  if (query) {
    for (const [k, v] of new URLSearchParams(query)) {
      params[k] = /^\d+$/.test(v) ? Number(v) : v;
    }
  }
  return { path: path || "rankings", params };
}

function paintNav(path) {
  document.querySelectorAll(".nav a").forEach((a) => {
    a.classList.toggle("active", a.dataset.route === path);
  });
}

async function dispatch() {
  const { path, params } = parseHash();
  paintNav(path);
  const loader = routes[path] || routes.rankings;
  const mod = await loader();
  const view = document.getElementById("view");
  try {
    await mod.render(view, params);
  } catch (err) {
    view.textContent = "";
    const box = document.createElement("div");
    box.className = "card";
    box.textContent = "Failed to load view: " + err.message;
    view.appendChild(box);
  }
}

function initTheme() {
  const saved = localStorage.getItem("theme");
  const theme = saved || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  document.documentElement.setAttribute("data-theme", theme);
  const btn = document.getElementById("theme-toggle");
  btn.textContent = theme === "dark" ? "☀ Light" : "🌙 Dark";
  btn.addEventListener("click", () => {
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
    btn.textContent = next === "dark" ? "☀ Light" : "🌙 Dark";
  });
}

window.addEventListener("hashchange", dispatch);
window.addEventListener("DOMContentLoaded", () => {
  initTheme();
  if (!location.hash) location.hash = "#/rankings";
  dispatch();
});

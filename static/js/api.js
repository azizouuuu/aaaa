let sampleBannerShown = false;

export async function api(path, params = {}) {
  const qs = new URLSearchParams(
    Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ""))
  );
  const url = "/api" + path + (qs.toString() ? "?" + qs.toString() : "");
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status} ${res.statusText}`);
  }
  const body = await res.json();
  onDataMode(body.meta?.data_mode);
  return body;
}

function onDataMode(mode) {
  const banner = document.getElementById("sample-banner");
  if (!banner) return;
  if (mode === "sample") {
    banner.classList.add("show");
  }
}

let metaCache = null;
export async function getMeta() {
  if (!metaCache) metaCache = (await api("/meta")).data;
  return metaCache;
}

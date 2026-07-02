export function fmtUsd(v) {
  if (v == null || Number.isNaN(v)) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e9) return "$" + (v / 1e9).toFixed(abs >= 10e9 ? 1 : 2) + "B";
  if (abs >= 1e6) return "$" + (v / 1e6).toFixed(abs >= 10e6 ? 1 : 2) + "M";
  if (abs >= 1e3) return "$" + (v / 1e3).toFixed(0) + "K";
  return "$" + v.toFixed(0);
}

export function fmtTonnes(v) {
  if (v == null || Number.isNaN(v)) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e6) return (v / 1e6).toFixed(2) + "Mt";
  if (abs >= 1e3) return (v / 1e3).toFixed(0) + "kt";
  return v.toFixed(0) + "t";
}

export function fmtUnitValue(v) {
  if (v == null || Number.isNaN(v)) return "—";
  return "$" + v.toFixed(0) + "/t";
}

export function fmtPct(v, signed) {
  if (v == null || Number.isNaN(v)) return "—";
  const s = (v * 100).toFixed(0) + "%";
  return signed && v > 0 ? "+" + s : s;
}

export function niceMax(v) {
  if (v <= 0) return 1;
  const mag = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / mag;
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  return step * mag;
}

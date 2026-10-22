// Chart colours shared by the dashboard, candidate modal and comparison view.
const PALETTE = [
  "#2563eb", "#059669", "#db2777", "#d97706", "#8b5cf6",
  "#e11d48", "#0ea5a6", "#1f2937", "#065f46", "#be185d",
];

/** Colour for series number `index` (wraps around the palette). */
export function colorAt(index) {
  return PALETTE[Math.abs(index) % PALETTE.length];
}

/** Convert "#rrggbb" to an rgba() string with the given opacity (for chart fills). */
export function hexToRGBA(hex, alpha = 1) {
  const h = hex.replace("#", "");
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

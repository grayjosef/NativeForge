export function str(v: unknown): string {
  return typeof v === "string" ? v : v != null ? String(v) : "";
}

export function formatIsoMaybe(v: unknown): string {
  const s = str(v);
  return s || "—";
}

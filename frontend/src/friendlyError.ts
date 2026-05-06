/** Map raw API messages to operator-friendly copy with recovery hints. */

const GENERIC_SHORT =
  "Something went wrong. Wait a moment and try again, or refresh the page.";

export function friendlyError(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err);
  const t = raw.trim();
  const lower = t.toLowerCase();

  if (
    lower.includes("grant spark not found") ||
    (lower.includes("spark") && lower.includes("not found"))
  ) {
    return "Couldn't load this opportunity. It may have been removed. Pick another opportunity or add a new demo opportunity.";
  }

  if (lower.includes("pursuit") && lower.includes("not found")) {
    return "Couldn't load this pursuit. Refresh the page or open the pursuit again from your opportunity.";
  }

  if (
    lower.includes("no score") ||
    lower.includes("404") && lower.includes("score")
  ) {
    return "No readiness score yet. Score this opportunity after requirements are extracted.";
  }

  if (
    lower.includes("form package") &&
    (lower.includes("already exists") || lower.includes("409"))
  ) {
    return "A preview package already exists for this pursuit. Use Refresh to view it.";
  }

  if (
    lower.includes("tribal profile") &&
    (lower.includes("required") || lower.includes("not found"))
  ) {
    return "Create or refresh your tribal profile first — it's required for scoring and previews.";
  }

  if (
    lower.includes("nofo") ||
    lower.includes("extraction") ||
    lower.includes("requirements")
  ) {
    if (lower.includes("not found") || lower.includes("no extraction")) {
      return "Extract NOFO requirements first, then reload the checklist.";
    }
  }

  if (lower.includes("failed to fetch") || lower.includes("network")) {
    return "Can't reach the workspace. Check your connection, or run nf-up if you're working locally.";
  }

  if (t.length > 180) {
    return GENERIC_SHORT;
  }

  return t || GENERIC_SHORT;
}

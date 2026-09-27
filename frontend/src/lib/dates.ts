/**
 * Deadline arithmetic, in one place.
 *
 * Three surfaces were about to each decide what "due soon" means and how to
 * word "in 4 days", and three answers to that question is how a workspace
 * ends up calling the same opportunity urgent on one page and routine on the
 * next.
 *
 * ## Unparsable is null, never today
 *
 * `new Date("")` is Invalid Date and `new Date("soon")` is too; subtracting
 * either yields NaN, and NaN compared against a threshold is false, so a bad
 * date silently becomes "not urgent". Every function here returns null for
 * input it cannot read, and callers drop those rows rather than ranking them
 * against a date nobody stated.
 */

/** Whole days from now until `iso`, or null if it cannot be read. */
export function daysUntil(iso: string, now: Date = new Date()): number | null {
  const text = (iso || "").trim();
  if (!text) return null;
  const when = new Date(text);
  const ms = when.getTime();
  if (Number.isNaN(ms)) return null;
  // Rounded up: something closing in twenty hours is "in 1 day", not "today".
  return Math.ceil((ms - now.getTime()) / 86_400_000);
}

/** "Closed", "Today", "Tomorrow", "In 12 days". */
export function formatDeadline(days: number): string {
  if (days < 0) return "Closed";
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  return `In ${days} days`;
}

/**
 * Urgency, as the workspace means it.
 *
 * Fourteen days is the boundary because a federal application that has not
 * been started two weeks out is the one worth interrupting someone about; the
 * thresholds are named here so changing that judgement is one edit.
 */
export function deadlineTone(days: number): "bad" | "warn" | "neutral" | "muted" {
  if (days < 0) return "muted";
  if (days <= 3) return "bad";
  if (days <= 14) return "warn";
  return "neutral";
}

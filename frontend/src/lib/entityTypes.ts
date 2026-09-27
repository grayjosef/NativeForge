/**
 * Organization classifications, in English.
 *
 * `TribalEntityType` has ten values and the product doctrine is that they are
 * not interchangeable: a federally recognized Tribe, a Tribal college, an
 * Alaska Native village and a Native Hawaiian organization have different
 * eligibility under different programs. The backend keeps them distinct; this
 * is the single place the customer-facing wording for each one lives, so that
 * three surfaces cannot come to disagree about what to call the same thing.
 */

const LABELS: Record<string, string> = {
  federally_recognized_tribe: "Federally recognized Tribe",
  tribal_government: "Tribal government",
  tribal_organization: "Tribal organization",
  tribal_nonprofit: "Tribal nonprofit",
  tribal_college: "Tribal college or university",
  alaska_native_corporation: "Alaska Native corporation",
  alaska_native_village: "Alaska Native village",
  native_hawaiian_organization: "Native Hawaiian organization",
  native_serving_nonprofit: "Native-serving nonprofit",
  other: "Other Native-serving entity",
};

/** A classification's customer-facing name, or a readable fallback. */
export function humanEntity(value: string): string {
  return LABELS[value] ?? (value ? value.replace(/_/g, " ") : "");
}

/** "a, b and c" — an English list, not a JavaScript one. */
export function joinList(items: string[]): string {
  if (items.length === 0) return "";
  if (items.length === 1) return items[0];
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

/**
 * The scoring engine's disqualification reason, rewritten for a customer.
 *
 * The engine produces, verbatim:
 *
 *     Entity type 'federally_recognized_tribe' is not in the extracted
 *     eligible types ['tribal_government', 'tribal_nonprofit'].
 *
 * Every complaint the brief makes about internal vocabulary, in one sentence a
 * grants office would be shown at the exact moment it is told it cannot apply:
 * enum names, quoted identifiers, and a Python list literal. The information
 * is genuinely useful and genuinely correct, so it is translated rather than
 * suppressed - hiding it would replace a confusing answer with no answer.
 *
 * Anything this does not recognise is returned unchanged. A reason nobody has
 * written a translation for is still better than silence, and the alternative
 * - a generic "you are not eligible" - would discard the one fact that tells
 * a customer what to do next.
 */
export function humanDisqualification(raw: string): string {
  const text = (raw || "").trim();
  if (!text) return "";

  const match = text.match(
    /Entity type '([a-z_]+)' is not in the extracted eligible types \[([^\]]*)\]/i,
  );
  if (!match) return text;

  const actual = humanEntity(match[1]);
  const eligible = match[2]
    .split(",")
    .map((s) => s.trim().replace(/^['"]|['"]$/g, ""))
    .filter(Boolean)
    .map(humanEntity);

  if (eligible.length === 0) {
    return `This notice does not list ${actual} among the organization types it accepts.`;
  }
  return `This notice accepts ${joinList(eligible)}. Your organization is registered as ${actual}.`;
}

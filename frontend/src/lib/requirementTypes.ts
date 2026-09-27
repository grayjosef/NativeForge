/**
 * Requirement types, as a grants manager would say them.
 *
 * `narrative_section` and `budget_narrative` are the extractor's vocabulary.
 * They are not wrong, they are simply not English, and a checklist a Tribal
 * grants office works from should not make anybody learn our enum names.
 *
 * Lives here rather than beside either surface that renders a checklist,
 * because both do and the first version of this table was duplicated.
 */

const LABELS: Record<string, string> = {
  eligibility: "Eligibility",
  form: "Form",
  attachment: "Attachment",
  narrative_section: "Narrative",
  budget_narrative: "Budget narrative",
  reporting: "Reporting",
  certification: "Certification",
  other: "Other",
};

/**
 * An unmapped value has its underscores removed rather than being hidden: a
 * requirement type this table has not caught up with is still information,
 * and an em dash would throw away the only thing the row had to say about
 * what kind of requirement it is.
 */
export function humanRequirementType(value: string): string {
  return LABELS[value] ?? (value ? value.replace(/_/g, " ") : "Requirement");
}

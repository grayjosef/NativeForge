export type Stage12StepId =
  | "source-discovery"
  | "source-quality-review"
  | "activation-readiness-preview"
  | "opportunity-intake"
  | "native-relevance-review"
  | "profile-match-readiness"
  | "operator-decision"
  | "evidence-audit-trail";

export const STAGE12_STEPS: { id: Stage12StepId; label: string }[] = [
  { id: "source-discovery", label: "Source discovery" },
  { id: "source-quality-review", label: "Source quality review" },
  { id: "activation-readiness-preview", label: "Activation readiness (preview)" },
  { id: "opportunity-intake", label: "Opportunity intake" },
  { id: "native-relevance-review", label: "Native relevance review" },
  { id: "profile-match-readiness", label: "Profile match + readiness" },
  { id: "operator-decision", label: "Operator decision" },
  { id: "evidence-audit-trail", label: "Evidence / audit trail" },
];

export type AsyncBlock<T> = {
  loading: boolean;
  error: string | null;
  data: T;
};

export function str(v: unknown): string {
  return typeof v === "string" ? v : v != null ? String(v) : "";
}

export interface AsyncList<T = unknown> {
  loading: boolean;
  error: string | null;
  data: T;
}

export type WorkbenchTabId =
  | "source-review"
  | "intake"
  | "native-relevance"
  | "org-profile"
  | "matching"
  | "ledger";

export const WORKBENCH_TABS: { id: WorkbenchTabId; label: string }[] = [
  { id: "source-review", label: "Source review" },
  { id: "intake", label: "Discovery intake" },
  { id: "native-relevance", label: "Native relevance" },
  { id: "org-profile", label: "Org profile" },
  { id: "matching", label: "Matching + readiness" },
  { id: "ledger", label: "Ledger + decisions" },
];

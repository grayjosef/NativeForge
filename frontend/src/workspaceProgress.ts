import type { ProgressStep, ProgressStepState } from "./components/ProgressStrip";

export interface ProgressInputs {
  profileRecord: Record<string, unknown> | null;
  orgProfileErr: boolean;
  sparkDetail: Record<string, unknown> | null;
  /** True only when list/create Spark APIs failed — not stale selection */
  sparkApiErr: boolean;
  requirementsLen: number;
  nofoErr: boolean;
  score: Record<string, unknown> | null;
  scoreErr: boolean;
  pursuitId: string;
  pursuit: Record<string, unknown> | null;
  pursuitErr: boolean;
  formPkg: Record<string, unknown> | null;
  formErr: boolean;
  trustManifest: Record<string, unknown> | null;
  reviewSummary: Record<string, unknown> | null;
  trustCenterErr: boolean;
}

export type NextActionId =
  | "profile"
  | "spark"
  | "nofo_extract"
  | "score"
  | "pursuit"
  | "sf424"
  | "trust_export"
  | "trust_refresh"
  | "none";

export interface WhatsNextResult {
  headline: string;
  detail: string;
  actionId: NextActionId;
  primaryLabel: string | null;
}

function step(
  id: string,
  short: string,
  label: string,
  state: ProgressStepState,
  lineSummary: string,
): ProgressStep {
  return { id, shortLabel: short, label, state, lineSummary };
}

export function buildProgressSteps(i: ProgressInputs): ProgressStep[] {
  const hasProfile = i.profileRecord !== null;
  const hasSpark = i.sparkDetail !== null;
  const hasReq = i.requirementsLen > 0;
  const hasScore = i.score !== null;
  const disqualified = Boolean(i.score && i.score.disqualified);
  const hasPursuit =
    !!i.pursuitId.trim() && i.pursuit !== null;
  const hasForm = i.formPkg !== null;
  const hasTrust =
    i.trustManifest !== null && i.reviewSummary !== null;

  return [
    step(
      "profile",
      "Profile",
      "Tribal profile",
      i.orgProfileErr
        ? "error"
        : hasProfile
          ? "complete"
          : "needs_setup",
      i.orgProfileErr
        ? "Fix profile error"
        : hasProfile
          ? "On file"
          : "Ready to start",
    ),
    step(
      "spark",
      "Opportunity",
      "Grant Spark",
      i.sparkApiErr
        ? "error"
        : !hasProfile
          ? "locked"
          : !hasSpark
            ? "needs_setup"
            : "complete",
      i.sparkApiErr
        ? "Could not load opportunities"
        : !hasProfile
          ? "After profile"
          : !hasSpark
            ? "Ready to add"
            : "Selected",
    ),
    step(
      "nofo",
      "NOFO",
      "NOFO requirements",
      i.nofoErr
        ? "error"
        : !hasSpark
          ? "locked"
          : !hasReq
            ? "needs_setup"
            : "complete",
      i.nofoErr
        ? "Extraction issue"
        : !hasSpark
          ? "Needs opportunity"
          : !hasReq
            ? "Extract when ready"
            : "Checklist ready",
    ),
    step(
      "score",
      "Score",
      "Readiness score",
      i.scoreErr
        ? "error"
        : disqualified
          ? "needs_attention"
          : !hasReq
            ? "locked"
            : !hasScore
              ? "needs_setup"
              : "complete",
      i.scoreErr
        ? "Scoring issue"
        : disqualified
          ? "Review flags"
          : !hasReq
            ? "Needs requirements"
            : !hasScore
              ? "Run when ready"
              : "Scored",
    ),
    step(
      "pursuit",
      "Pursuit",
      "Pursuit",
      i.pursuitErr
        ? "error"
        : !hasScore
          ? "locked"
          : !hasPursuit
            ? "needs_setup"
            : "complete",
      i.pursuitErr
        ? "Could not open pursuit"
        : !hasScore
          ? "Needs score"
          : !hasPursuit
            ? "Open when ready"
            : "Active",
    ),
    step(
      "forms",
      "SF-424",
      "SF-424 preview",
      i.formErr
        ? "error"
        : !hasPursuit
          ? "locked"
          : !hasForm
            ? "needs_setup"
            : "complete",
      i.formErr
        ? "Preview issue"
        : !hasPursuit
          ? "Needs pursuit"
          : !hasForm
            ? "Create when ready"
            : "Preview ready",
    ),
    step(
      "trust",
      "Trust",
      "Trust & export",
      i.trustCenterErr
        ? "error"
        : hasTrust
          ? "complete"
          : "needs_setup",
      i.trustCenterErr
        ? "Trust unavailable"
        : hasTrust
          ? "Current"
          : "Refresh to load",
    ),
  ];
}

export function buildWhatsNext(flags: {
    orgOk: boolean;
    anyBusy: boolean;
    hasProfile: boolean;
    hasSpark: boolean;
    hasReq: boolean;
    hasScore: boolean;
    hasPursuit: boolean;
    hasForm: boolean;
}): WhatsNextResult {
  if (!flags.orgOk) {
    return {
      headline: "Organization needed",
      detail:
        "Open Context and enter a valid organization identifier to begin.",
      actionId: "none",
      primaryLabel: null,
    };
  }
  if (flags.anyBusy) {
    return {
      headline: "Working…",
      detail: "Your workspace is updating.",
      actionId: "none",
      primaryLabel: null,
    };
  }

  if (!flags.hasProfile) {
    return {
      headline: "Set up your tribal profile",
      detail:
        "This is the first step. It powers previews, review artifacts, and exports.",
      actionId: "profile",
      primaryLabel: "Create tribal profile",
    };
  }
  if (!flags.hasSpark) {
    return {
      headline: "Add or select an opportunity",
      detail:
        "No active opportunity yet. Start with a demo or pick one from your list.",
      actionId: "spark",
      primaryLabel: "Add demo opportunity",
    };
  }
  if (!flags.hasReq) {
    return {
      headline: "Extract NOFO requirements",
      detail:
        "Pull checklist rows from your opportunity text, then reload to review.",
      actionId: "nofo_extract",
      primaryLabel: "Extract NOFO requirements",
    };
  }
  if (!flags.hasScore) {
    return {
      headline: "Score this opportunity",
      detail: "Get an advisory readiness score based on your checklist.",
      actionId: "score",
      primaryLabel: "Score this opportunity",
    };
  }
  if (!flags.hasPursuit) {
    return {
      headline: "Open a pursuit",
      detail: "Create tasks and calendar anchors for application prep.",
      actionId: "pursuit",
      primaryLabel: "Open pursuit",
    };
  }
  if (!flags.hasForm) {
    return {
      headline: "Create an SF-424 preview",
      detail:
        "Generate an internal preview package for staff — not a filing.",
      actionId: "sf424",
      primaryLabel: "Create SF-424 preview package",
    };
  }

  return {
    headline: "Export or refresh trust data",
    detail:
      "Download an organization-owned snapshot or refresh the Trust Center.",
    actionId: "trust_export",
    primaryLabel: "Export organization snapshot",
  };
}

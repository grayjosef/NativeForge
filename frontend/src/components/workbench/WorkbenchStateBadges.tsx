import { str } from "./workbenchFormat";

export interface WorkbenchStateBadgesProps {
  matchLabel?: string;
  readinessLabel?: string;
  humanReviewRequired?: boolean;
  unknownFieldCount?: number;
  overclaimBlocked?: boolean;
  claimBlocked?: boolean;
}

export function WorkbenchStateBadges({
  matchLabel,
  readinessLabel,
  humanReviewRequired,
  unknownFieldCount,
  overclaimBlocked,
  claimBlocked,
}: WorkbenchStateBadgesProps) {
  const badges: { key: string; label: string; tone: string }[] = [];

  if (humanReviewRequired || matchLabel === "needs_operator_review") {
    badges.push({
      key: "review",
      label: "Needs operator review",
      tone: "warn",
    });
  }
  if (overclaimBlocked) {
    badges.push({
      key: "overclaim",
      label: "Overclaim blocked",
      tone: "error",
    });
  }
  if (claimBlocked) {
    badges.push({
      key: "claim",
      label: "Eligibility claim blocked",
      tone: "error",
    });
  }
  if (unknownFieldCount && unknownFieldCount > 0) {
    badges.push({
      key: "unknown",
      label: `UNKNOWN fields: ${unknownFieldCount}`,
      tone: "muted",
    });
  }
  if (matchLabel) {
    badges.push({
      key: "match",
      label: `Match: ${matchLabel}`,
      tone: "info",
    });
  }
  if (readinessLabel) {
    badges.push({
      key: "readiness",
      label: `Readiness: ${readinessLabel}`,
      tone: "info",
    });
  }

  if (badges.length === 0) {
    return null;
  }

  return (
    <div className="nf-wb-badges" role="list" aria-label="Advisory state badges">
      {badges.map((b) => (
        <span
          key={b.key}
          role="listitem"
          className={`nf-wb-badge nf-wb-badge--${b.tone}`}
        >
          {b.label}
        </span>
      ))}
    </div>
  );
}

export function extractOverclaimBlocked(record: Record<string, unknown>): boolean {
  const cls = record.classification as Record<string, unknown> | undefined;
  const guard = cls?.overclaim_guard as Record<string, unknown> | undefined;
  return guard?.overclaim_blocked === true;
}

export function extractUnknownCount(profileRecord: Record<string, unknown>): number {
  const evaluation = profileRecord.evaluation as Record<string, unknown> | undefined;
  return Number(evaluation?.unknown_field_count ?? 0);
}

export function strField(obj: Record<string, unknown> | undefined, key: string): string {
  return str(obj?.[key]);
}

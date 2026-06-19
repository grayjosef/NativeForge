import type { Plane } from "../../../m0Flow";
import { PriorityActionsCard } from "../PriorityActionsCard";
import { OperatorLedgerCard } from "../OperatorLedgerCard";
import type { AsyncList } from "../stage11Types";

interface OperatorLedgerDecisionScreenProps {
  baseUrl: string;
  plane: Plane;
  orgId: string;
  pack: AsyncList<Record<string, unknown> | null>;
  ledgerSummary: AsyncList<Record<string, unknown> | null>;
  ledgerOpen: AsyncList<Record<string, unknown> | null>;
}

export function OperatorLedgerDecisionScreen({
  baseUrl,
  plane,
  orgId,
  pack,
  ledgerSummary,
  ledgerOpen,
}: OperatorLedgerDecisionScreenProps) {
  return (
    <div className="nf-wb-screen-stack" data-screen="operator-ledger-decisions">
      <PriorityActionsCard baseUrl={baseUrl} plane={plane} orgId={orgId} block={pack} />
      <OperatorLedgerCard
        baseUrl={baseUrl}
        plane={plane}
        orgId={orgId}
        summary={ledgerSummary}
        list={ledgerOpen}
      />
    </div>
  );
}

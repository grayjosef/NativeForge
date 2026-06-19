import { useState } from "react";
import type { Plane } from "../m0Flow";
import { DiscoveryIntakeReviewScreen } from "../components/workbench/stage11/DiscoveryIntakeReviewScreen";
import { MatchingReadinessScreen } from "../components/workbench/stage11/MatchingReadinessScreen";
import { NativeRelevanceReviewScreen } from "../components/workbench/stage11/NativeRelevanceReviewScreen";
import { OperatorLedgerDecisionScreen } from "../components/workbench/stage11/OperatorLedgerDecisionScreen";
import { OrgApplicantProfileScreen } from "../components/workbench/stage11/OrgApplicantProfileScreen";
import { SourceReviewQueueScreen } from "../components/workbench/stage11/SourceReviewQueueScreen";
import {
  WORKBENCH_TABS,
  type AsyncList,
  type WorkbenchTabId,
} from "../components/workbench/stage11Types";

export interface WorkbenchStage11Props {
  plane: Plane;
  orgId: string;
  orgOk: boolean;
  baseUrl: string;
  advisoryBundle: AsyncList<Record<string, unknown> | null>;
  reviewItems: AsyncList<Record<string, unknown>[] | null>;
  pack: AsyncList<Record<string, unknown> | null>;
  ledgerSummary: AsyncList<Record<string, unknown> | null>;
  ledgerOpen: AsyncList<Record<string, unknown> | null>;
}

export function WorkbenchStage11({
  plane,
  orgId,
  orgOk,
  baseUrl,
  advisoryBundle,
  reviewItems,
  pack,
  ledgerSummary,
  ledgerOpen,
}: WorkbenchStage11Props) {
  const [tab, setTab] = useState<WorkbenchTabId>("source-review");

  if (!orgOk) {
    return (
      <p className="nf-muted">Enter a valid organization ID to load the workbench.</p>
    );
  }

  return (
    <div className="nf-workbench-stage11" data-nf-workbench="1">
      <nav className="nf-wb-tabs" aria-label="Operator workbench sections">
        {WORKBENCH_TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`nf-wb-tab${tab === t.id ? " nf-wb-tab--active" : ""}`}
            aria-current={tab === t.id ? "page" : undefined}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>
      <div className="nf-wb-tab-panel">
        {tab === "source-review" ? (
          <SourceReviewQueueScreen
            baseUrl={baseUrl}
            plane={plane}
            orgId={orgId}
            reviewItems={reviewItems}
            advisoryBundle={advisoryBundle}
          />
        ) : null}
        {tab === "intake" ? (
          <DiscoveryIntakeReviewScreen advisoryBundle={advisoryBundle} />
        ) : null}
        {tab === "native-relevance" ? (
          <NativeRelevanceReviewScreen advisoryBundle={advisoryBundle} />
        ) : null}
        {tab === "org-profile" ? (
          <OrgApplicantProfileScreen advisoryBundle={advisoryBundle} />
        ) : null}
        {tab === "matching" ? (
          <MatchingReadinessScreen advisoryBundle={advisoryBundle} />
        ) : null}
        {tab === "ledger" ? (
          <OperatorLedgerDecisionScreen
            baseUrl={baseUrl}
            plane={plane}
            orgId={orgId}
            pack={pack}
            ledgerSummary={ledgerSummary}
            ledgerOpen={ledgerOpen}
          />
        ) : null}
      </div>
    </div>
  );
}

import { useEffect, useMemo, useState } from "react";
import type { Plane } from "../m0Flow";
import { apiFetchBase } from "../m0ApiClient";
import { friendlyError } from "../friendlyError";
import {
  getCoverageGapIntelligence,
  getOperatorDecisionPack,
  getOperatorLedgerSummary,
  getSourceRecommendations,
  getSourcesFreshnessSummary,
  listDiscoveryReviewItems,
  listOperatorLedgerActions,
  listSourcesOverdue,
} from "../discoveryApiClient";
import { CoverageGapsCard } from "../components/workbench/CoverageGapsCard";
import { EvidenceLinksCard } from "../components/workbench/EvidenceLinksCard";
import { collectEvidenceLinkRows } from "../components/workbench/evidenceUrls";
import { OperatorLedgerCard } from "../components/workbench/OperatorLedgerCard";
import { PriorityActionsCard } from "../components/workbench/PriorityActionsCard";
import { ReviewQueueCard } from "../components/workbench/ReviewQueueCard";
import { SourcesOverdueCard } from "../components/workbench/SourcesOverdueCard";

type RecordBlock = {
  loading: boolean;
  error: string | null;
  data: Record<string, unknown> | null;
};

type ListBlock = {
  loading: boolean;
  error: string | null;
  data: Record<string, unknown>[] | null;
};

const emptyRecord = (): RecordBlock => ({
  loading: false,
  error: null,
  data: null,
});

const emptyList = (): ListBlock => ({
  loading: false,
  error: null,
  data: null,
});

export interface WorkbenchPageProps {
  plane: Plane;
  orgId: string;
  orgOk: boolean;
}

export function WorkbenchPage({ plane, orgId, orgOk }: WorkbenchPageProps) {
  const base = apiFetchBase();
  const o = orgId.trim();

  const [pack, setPack] = useState<RecordBlock>(emptyRecord);
  const [ledgerSummary, setLedgerSummary] = useState<RecordBlock>(emptyRecord);
  const [ledgerOpen, setLedgerOpen] = useState<RecordBlock>(emptyRecord);
  const [reviewItems, setReviewItems] = useState<ListBlock>(emptyList);
  const [overdue, setOverdue] = useState<ListBlock>(emptyList);
  const [freshness, setFreshness] = useState<RecordBlock>(emptyRecord);
  const [intel, setIntel] = useState<RecordBlock>(emptyRecord);
  const [recs, setRecs] = useState<RecordBlock>(emptyRecord);

  useEffect(() => {
    if (!orgOk) {
      setPack(emptyRecord());
      setLedgerSummary(emptyRecord());
      setLedgerOpen(emptyRecord());
      setReviewItems(emptyList());
      setOverdue(emptyList());
      setFreshness(emptyRecord());
      setIntel(emptyRecord());
      setRecs(emptyRecord());
      return;
    }

    setPack({ loading: true, error: null, data: null });
    setLedgerSummary({ loading: true, error: null, data: null });
    setLedgerOpen({ loading: true, error: null, data: null });
    setReviewItems({ loading: true, error: null, data: null });
    setOverdue({ loading: true, error: null, data: null });
    setFreshness({ loading: true, error: null, data: null });
    setIntel({ loading: true, error: null, data: null });
    setRecs({ loading: true, error: null, data: null });

    let alive = true;

    void (async () => {
      try {
        const d = await getOperatorDecisionPack(base, plane, o, { limit: 50 });
        if (alive) {
          setPack({ loading: false, error: null, data: d });
        }
      } catch (e) {
        if (alive) {
          setPack({ loading: false, error: friendlyError(e), data: null });
        }
      }
    })();

    void (async () => {
      try {
        const d = await getOperatorLedgerSummary(base, plane, o);
        if (alive) {
          setLedgerSummary({ loading: false, error: null, data: d });
        }
      } catch (e) {
        if (alive) {
          setLedgerSummary({ loading: false, error: friendlyError(e), data: null });
        }
      }
    })();

    void (async () => {
      try {
        const d = await listOperatorLedgerActions(base, plane, o, {
          open_only: true,
          limit: 50,
        });
        if (alive) {
          setLedgerOpen({ loading: false, error: null, data: d });
        }
      } catch (e) {
        if (alive) {
          setLedgerOpen({ loading: false, error: friendlyError(e), data: null });
        }
      }
    })();

    void (async () => {
      try {
        const d = await listDiscoveryReviewItems(base, plane, o, {
          open_queue_only: true,
          limit: 200,
        });
        if (alive) {
          setReviewItems({ loading: false, error: null, data: d });
        }
      } catch (e) {
        if (alive) {
          setReviewItems({ loading: false, error: friendlyError(e), data: null });
        }
      }
    })();

    void (async () => {
      try {
        const d = await listSourcesOverdue(base, plane, o);
        if (alive) {
          setOverdue({ loading: false, error: null, data: d });
        }
      } catch (e) {
        if (alive) {
          setOverdue({ loading: false, error: friendlyError(e), data: null });
        }
      }
    })();

    void (async () => {
      try {
        const d = await getSourcesFreshnessSummary(base, plane, o);
        if (alive) {
          setFreshness({ loading: false, error: null, data: d });
        }
      } catch (e) {
        if (alive) {
          setFreshness({ loading: false, error: friendlyError(e), data: null });
        }
      }
    })();

    void (async () => {
      try {
        const d = await getCoverageGapIntelligence(base, plane, o, {
          limit: 50,
        });
        if (alive) {
          setIntel({ loading: false, error: null, data: d });
        }
      } catch (e) {
        if (alive) {
          setIntel({ loading: false, error: friendlyError(e), data: null });
        }
      }
    })();

    void (async () => {
      try {
        const d = await getSourceRecommendations(base, plane, o, { limit: 50 });
        if (alive) {
          setRecs({ loading: false, error: null, data: d });
        }
      } catch (e) {
        if (alive) {
          setRecs({ loading: false, error: friendlyError(e), data: null });
        }
      }
    })();

    return () => {
      alive = false;
    };
  }, [base, plane, o, orgOk]);

  const evidenceRows = useMemo(
    () =>
      collectEvidenceLinkRows({
        decisionPack: pack.data,
        ledgerList: ledgerOpen.data,
        reviewItems: reviewItems.data,
        overdueSources: overdue.data,
        coverageIntel: intel.data,
        sourceRecs: recs.data,
      }),
    [
      pack.data,
      ledgerOpen.data,
      reviewItems.data,
      overdue.data,
      intel.data,
      recs.data,
    ],
  );

  return (
    <div className="nf-workbench">
      <header className="nf-workbench-intro">
        <h2 className="nf-workbench-title">Operator workbench</h2>
        <p className="nf-workbench-blurb">
          Read-mostly view of discovery engine outputs for this organization.
          Cards load independently — a failure in one section does not block the
          others.
        </p>
      </header>

      <div className="nf-workbench-grid">
        <PriorityActionsCard
          baseUrl={base}
          plane={plane}
          orgId={o}
          block={pack}
        />
        <OperatorLedgerCard
          baseUrl={base}
          plane={plane}
          orgId={o}
          summary={{ loading: ledgerSummary.loading, error: ledgerSummary.error, data: ledgerSummary.data }}
          list={{ loading: ledgerOpen.loading, error: ledgerOpen.error, data: ledgerOpen.data }}
        />
        <ReviewQueueCard
          baseUrl={base}
          plane={plane}
          orgId={o}
          block={{
            loading: reviewItems.loading,
            error: reviewItems.error,
            data: reviewItems.data,
          }}
        />
        <SourcesOverdueCard
          baseUrl={base}
          plane={plane}
          orgId={o}
          overdue={overdue}
          freshness={freshness}
        />
        <CoverageGapsCard intel={intel} recs={recs} />
        <EvidenceLinksCard
          baseUrl={base}
          plane={plane}
          orgId={o}
          rows={evidenceRows}
        />
      </div>
    </div>
  );
}

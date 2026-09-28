import { useCallback, useState } from "react";

import { StateView } from "../components/StateView";
import {
  MetricCard,
  MetricRow,
  PageHeader,
  Section,
  StatusBadge,
} from "../components/ui/primitives";

export interface LiveFederalRow {
  opportunity_number?: string;
  title?: string;
  funder?: string;
  program?: string;
  funding?: string;
  deadline?: string;
  eligibility_label?: string;
  coverage_lane?: string;
  why_it_matches?: string;
  source?: string;
  source_url?: string;
}

export interface DiscoverPageProps {
  trackedCount: number;
  onGoToOpportunities: () => void;
  onAddDemo: () => void;
  canAdd: boolean;
  onSearchLive?: () => Promise<Record<string, unknown>>;
  onPursue?: (row: LiveFederalRow) => void;
}

export function DiscoverPage(props: DiscoverPageProps) {
  const { trackedCount, onGoToOpportunities, onAddDemo, canAdd, onSearchLive, onPursue } = props;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<Record<string, unknown> | null>(null);

  const search = useCallback(async () => {
    if (!onSearchLive) return;
    setBusy(true);
    setError(null);
    try {
      setPayload(await onSearchLive());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Live federal search failed.");
    } finally {
      setBusy(false);
    }
  }, [onSearchLive]);

  const results = Array.isArray(payload?.results) ? (payload?.results as LiveFederalRow[]) : [];
  const status = String(payload?.status || "");
  const live = payload?.search_live === true;
  const collectorsOff = payload?.collectors_live !== true;

  return (
    <div className="nf-page">
      <PageHeader
        eyebrow="Find funding"
        title="Discover"
        lead="Public federal opportunities from Grants.gov, plus the opportunities you already track. Publisher applicant classes and broadly posted or forecasted notices. NativeForge has not decided relevance."
        actions={
          <>
            <button type="button" className="nf-btn nf-btn-primary nf-btn-sm" onClick={() => void search()} disabled={!onSearchLive || busy}>
              {busy ? "Searching Grants.gov…" : "Search live Grants.gov"}
            </button>
            <button type="button" className="nf-btn nf-btn-secondary nf-btn-sm" onClick={onGoToOpportunities}>
              View tracked opportunities
            </button>
          </>
        }
      />

      <Section title="At a glance" lead="Measured, not projected.">
        <MetricRow>
          <MetricCard
            label="Sources collecting"
            value={String(Number(payload?.collectors_live || 0))}
            tone="muted"
            note="Live only when every collection gate is true"
          />
          <MetricCard
            label="Live federal results"
            value={payload ? String(results.length) : "—"}
            tone={results.length ? "positive" : "muted"}
            note={live ? "From Grants.gov search2" : "Run a live search"}
          />
          <MetricCard
            label="Opportunities tracked"
            value={String(trackedCount)}
            tone={trackedCount > 0 ? "positive" : "muted"}
            onClick={onGoToOpportunities}
            note="Added by you"
          />
          <MetricCard
            label="Collectors live"
            value={Number(payload?.collectors_live || 0) > 0 ? String(payload?.collectors_live) : "No"}
            tone="muted"
            note={collectorsOff ? "No source has passed every gate" : "Gate evidence"}
          />
        </MetricRow>
      </Section>

      {error ? (
        <StateView
          state={{ tone: "error", title: "Live search could not run", body: error, actionLabel: "Try again" }}
          onAction={() => void search()}
        />
      ) : null}

      {status === "live_search_not_authorized" ? (
        <StateView
          state={{
            tone: "blocked",
            title: "Live federal search is not authorized on this deployment",
            body: "Set NF_CUSTOMER_LIVE_FEDERAL_SEARCH on the server to permit a customer-initiated public Grants.gov query. Until then, track an opportunity you already know.",
            actionLabel: canAdd ? "Track an opportunity instead" : undefined,
          }}
          onAction={canAdd ? onAddDemo : undefined}
        />
      ) : null}

      {payload && results.length === 0 && status !== "live_search_not_authorized" && !error ? (
        <StateView
          state={{
            tone: "empty",
            title: "No opportunities in this query",
            body: "Grants.gov returned no rows for the publisher applicant classes or the broad posted and forecasted index.",
          }}
        />
      ) : null}

      {results.length > 0 ? (
        <Section title="Live federal inventory" lead="Publisher class and broad posted or forecasted notices. NativeForge has not decided relevance or tenant eligibility.">
          <ul className="nf-source-list">
            {results.map((row) => (
              <li key={`${row.opportunity_number}-${row.title}`} className="nf-source">
                <div>
                  <p className="nf-source-name">{row.title || "Untitled opportunity"}</p>
                  <p className="nf-source-detail">
                    {[row.funder, row.opportunity_number, row.deadline ? `Due ${row.deadline}` : "", row.funding]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                  <p className="nf-source-detail">{row.why_it_matches}</p>
                </div>
                <div className="nf-source-actions">
                  <StatusBadge tone="info">
                    {row.eligibility_label ||
                      (row.coverage_lane === "broad_posted_or_forecasted"
                        ? "Broad posted or forecasted"
                        : "Grants.gov")}
                  </StatusBadge>
                  {row.source_url ? (
                    <a className="nf-btn nf-btn-ghost nf-btn-sm" href={row.source_url} target="_blank" rel="noreferrer">
                      Open
                    </a>
                  ) : null}
                  {onPursue ? (
                    <button type="button" className="nf-btn nf-btn-primary nf-btn-sm" onClick={() => onPursue(row)}>
                      Pursue
                    </button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {!payload && !error ? (
        <StateView
          state={{
            tone: "empty",
            title: "No live search has been run in this session",
            body: "Search live Grants.gov for publisher applicant classes and the broad posted and forecasted index, or track an opportunity you already know. A collector runs only after every gate is true.",
            actionLabel: onSearchLive ? "Search live Grants.gov" : undefined,
          }}
          onAction={onSearchLive ? () => void search() : undefined}
        />
      ) : null}
    </div>
  );
}

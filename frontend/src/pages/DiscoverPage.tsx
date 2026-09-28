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
        lead="Live public federal opportunities, plus the opportunities you already track. Collectors stay off."
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
          <MetricCard label="Sources collecting" value="0" tone="muted" note="Collector fleet is not authorized" />
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
          <MetricCard label="Collectors live" value="No" tone="muted" note={collectorsOff ? "By design" : ""} />
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
            title: "No posted Tribal-class opportunities in this query",
            body: "Grants.gov returned no current rows for the three publisher applicant classes NativeForge is allowed to search.",
          }}
        />
      ) : null}

      {results.length > 0 ? (
        <Section title="Live federal inventory" lead="Publisher eligibility class only. NativeForge has not decided relevance or tenant eligibility.">
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
                  <StatusBadge tone="info">{row.eligibility_label || "Grants.gov"}</StatusBadge>
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
            body: "Automatic collectors are built and remain unauthorized. Search live Grants.gov to see current public federal opportunities, or track one you already know.",
            actionLabel: onSearchLive ? "Search live Grants.gov" : undefined,
          }}
          onAction={onSearchLive ? () => void search() : undefined}
        />
      ) : null}
    </div>
  );
}

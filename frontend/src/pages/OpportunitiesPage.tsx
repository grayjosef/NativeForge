import { useMemo, useState } from "react";

import { EmptyState, StateView } from "../components/StateView";
import type { CustomerState } from "../customerState";
import {
  PageHeader,
  Section,
  StatusBadge,
  type BadgeTone,
} from "../components/ui/primitives";
import { daysUntil, deadlineTone, formatDeadline } from "../lib/dates";

/**
 * The opportunities an organization is tracking.
 *
 * ## Filters only over fields that exist
 *
 * Search, agency and deadline window are all computed from fields present on
 * every opportunity record the API returns. There is no relevance filter and
 * no eligibility facet, because no endpoint supplies either, and a control
 * that silently matches everything is worse than an absent one - it tells a
 * customer NativeForge considered something it did not.
 *
 * ## Sorting puts undated last and says so
 *
 * An opportunity with no stated deadline cannot be ranked against one that
 * has a date. Rather than treating a missing deadline as the far future - the
 * usual accident, which quietly hides a closing opportunity behind an undated
 * one - undated rows sort to the end and the section header counts them.
 */

function str(v: unknown): string {
  return typeof v === "string" ? v : v != null ? String(v) : "";
}

export interface OpportunitiesPageProps {
  sparks: Record<string, unknown>[];
  selectedSparkId: string;
  onSelectSpark: (id: string) => void;
  /** Opens the opportunity in the guided workflow. */
  onOpenSpark: (id: string) => void;
  busy: boolean;
  error: CustomerState | null;
  onRefresh: () => void;
  onAddDemo: () => void;
  canAdd: boolean;
  /** Why adding is unavailable, when it is. */
  addBlockedReason?: string;
}

type Window = "all" | "30" | "90";

export function OpportunitiesPage(props: OpportunitiesPageProps) {
  const {
    sparks,
    selectedSparkId,
    onSelectSpark,
    onOpenSpark,
    busy,
    error,
    onRefresh,
    onAddDemo,
    canAdd,
    addBlockedReason,
  } = props;

  const [query, setQuery] = useState("");
  const [agency, setAgency] = useState("");
  const [window, setWindow] = useState<Window>("all");

  const agencies = useMemo(() => {
    const set = new Set<string>();
    for (const s of sparks) {
      const a = str(s.agency).trim();
      if (a) set.add(a);
    }
    return Array.from(set).sort();
  }, [sparks]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const limit = window === "all" ? null : Number(window);
    return sparks
      .map((spark) => ({ spark, days: daysUntil(str(spark.application_deadline)) }))
      .filter(({ spark, days }) => {
        if (agency && str(spark.agency) !== agency) return false;
        if (limit !== null && (days === null || days < 0 || days > limit)) return false;
        if (!q) return true;
        return [
          str(spark.opportunity_title),
          str(spark.agency),
          str(spark.program_name),
          str(spark.opportunity_number),
        ]
          .join(" ")
          .toLowerCase()
          .includes(q);
      })
      .sort((a, b) => {
        if (a.days === null && b.days === null) return 0;
        if (a.days === null) return 1;
        if (b.days === null) return -1;
        return a.days - b.days;
      });
  }, [sparks, query, agency, window]);

  const undated = rows.filter((r) => r.days === null).length;
  const filtered = sparks.length - rows.length;

  return (
    <div className="nf-page">
      <PageHeader
        eyebrow="Find funding"
        title="Opportunities"
        lead="Everything your organization is tracking, soonest deadline first."
        actions={
          <>
            <button
              type="button"
              className="nf-btn nf-btn-secondary nf-btn-sm"
              onClick={onRefresh}
              disabled={busy}
            >
              Refresh
            </button>
            <button
              type="button"
              className="nf-btn nf-btn-primary nf-btn-sm"
              onClick={onAddDemo}
              disabled={busy || !canAdd}
              title={canAdd ? undefined : addBlockedReason}
            >
              Add demo opportunity
            </button>
          </>
        }
      />

      {error ? <StateView state={error} /> : null}

      <Section
        title="Tracked opportunities"
        lead="Filters apply only to information the funding notice actually states."
        aside={
          <span className="nf-count">
            {rows.length} of {sparks.length}
            {undated > 0 ? ` · ${undated} undated` : ""}
          </span>
        }
      >
        <div className="nf-filterbar">
          <div className="nf-field nf-field--grow">
            <label htmlFor="opp-q">Search</label>
            <input
              id="opp-q"
              type="search"
              className="nf-input"
              placeholder="Title, funder, program or number"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <div className="nf-field">
            <label htmlFor="opp-agency">Funder</label>
            <select
              id="opp-agency"
              className="nf-select"
              value={agency}
              onChange={(e) => setAgency(e.target.value)}
              disabled={agencies.length === 0}
            >
              <option value="">All funders</option>
              {agencies.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </div>
          <div className="nf-field">
            <label htmlFor="opp-window">Closing within</label>
            <select
              id="opp-window"
              className="nf-select"
              value={window}
              onChange={(e) => setWindow(e.target.value as Window)}
            >
              <option value="all">Any time</option>
              <option value="30">30 days</option>
              <option value="90">90 days</option>
            </select>
          </div>
        </div>

        {sparks.length === 0 ? (
          <EmptyState
            title="No opportunities yet."
            body="Add a demo opportunity to walk the pursuit workflow end to end, or connect a source to begin discovery."
            actionLabel={canAdd ? "Add demo opportunity" : undefined}
            onAction={canAdd ? onAddDemo : undefined}
          />
        ) : rows.length === 0 ? (
          <EmptyState
            title="Nothing matches those filters."
            body={`${filtered} tracked opportunit${filtered === 1 ? "y is" : "ies are"} hidden by the current search, funder or deadline window.`}
            actionLabel="Clear filters"
            onAction={() => {
              setQuery("");
              setAgency("");
              setWindow("all");
            }}
          />
        ) : (
          <ul className="nf-opp-list">
            {rows.map(({ spark, days }) => {
              const id = str(spark.id);
              const selected = id === selectedSparkId;
              const tone: BadgeTone =
                days === null
                  ? "muted"
                  : (deadlineTone(days) as BadgeTone);
              return (
                <li key={id} className="nf-opp" data-selected={selected}>
                  <div className="nf-opp-main">
                    <p className="nf-opp-title">
                      {str(spark.opportunity_title) || `Opportunity ${id.slice(0, 8)}`}
                    </p>
                    <p className="nf-opp-meta">
                      {[str(spark.agency), str(spark.program_name)]
                        .filter(Boolean)
                        .join(" · ") || "Funder not stated"}
                    </p>
                    <div className="nf-opp-tags">
                      <StatusBadge tone={tone}>
                        {days === null ? "No stated deadline" : formatDeadline(days)}
                      </StatusBadge>
                      {str(spark.pipeline_stage) ? (
                        <StatusBadge tone="muted">{str(spark.pipeline_stage)}</StatusBadge>
                      ) : null}
                      {selected ? <StatusBadge tone="info">Active</StatusBadge> : null}
                    </div>
                  </div>
                  <div className="nf-opp-actions">
                    <button
                      type="button"
                      className="nf-btn nf-btn-secondary nf-btn-sm"
                      onClick={() => onSelectSpark(id)}
                      disabled={selected}
                    >
                      {selected ? "Active" : "Make active"}
                    </button>
                    <button
                      type="button"
                      className="nf-btn nf-btn-primary nf-btn-sm"
                      onClick={() => onOpenSpark(id)}
                    >
                      Open
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Section>
    </div>
  );
}

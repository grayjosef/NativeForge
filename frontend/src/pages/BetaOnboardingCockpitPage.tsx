/**
 * Gate 144D: the beta onboarding cockpit.
 *
 * Shows what this DEPLOYMENT can do — not what any customer's pipeline
 * contains. No Tribe name, no grant, no eligibility, no deadline appears here,
 * because none of those is what an operator asking "is this ready" needs.
 *
 * Every false lane is shown as false, with its blocker named. A cockpit that
 * displayed only the green lanes would be the most dangerous thing this
 * campaign could ship.
 */

import { useCallback, useEffect, useState } from "react";
import { apiFetchBase } from "../m0ApiClient";

export type CockpitLane = {
  lane: string;
  status: string;
  value: boolean;
  scope: string | null;
  summary: string;
  evidence: string;
  blockers: string[];
  owner: string | null;
  usable_today: boolean;
};

export type CockpitReadiness = {
  organization_id: string;
  cockpit_scope: string;
  lanes: CockpitLane[];
  operational_lanes: string[];
  blocked_lanes: string[];
  requires_human_approval_lanes: string[];
  not_configured_lanes: string[];
  usable_today_count: number;
  invariant_failures: string[];
  production_rollout: boolean;
  controlled_customer_pilot: boolean;
};

export type CockpitNextActions = {
  next_safe_action: string;
  why: string;
  safe_because: string;
  not_this_yet: string[];
};

/** Human labels. The lane KEY stays the contract; this is only the caption. */
const LANE_LABELS: Record<string, string> = {
  login: "Login",
  customer_persistence: "Customer Persistence",
  awarded_grants: "Awarded Grants",
  tenant_digest: "Tenant Digest",
  document_metadata: "Document Metadata",
  document_body_storage: "Document Storage",
  email_delivery_readiness: "Email Readiness",
  email_delivery: "Email Delivery",
  source_monitoring_preflight: "Source Monitoring Preflight",
  source_monitoring: "Source Monitoring",
  object_storage: "Object Storage",
  customer_auth: "Customer Auth",
  verified_operational_binding: "Verified Operational Binding",
  controlled_customer_pilot: "Controlled Customer Pilot",
  production_rollout: "Production Readiness",
};

/** What each status means, in words an operator can act on. */
const STATUS_LABELS: Record<string, string> = {
  operational: "Working",
  readiness_only: "Proved, not activated",
  preview_only: "Preview only",
  blocked: "Blocked",
  not_configured: "Not configured",
  requires_human_approval: "Needs a person",
  production_false: "Not approved",
};

export type BetaOnboardingCockpitPageProps = {
  orgId: string;
  readiness?: CockpitReadiness | null;
  nextActions?: CockpitNextActions | null;
  loading?: boolean;
  error?: string | null;
};

function laneLabel(lane: string): string {
  return LANE_LABELS[lane] ?? lane;
}

function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

export function BetaOnboardingCockpitPage({
  orgId,
  readiness: readinessProp,
  nextActions: nextActionsProp,
  loading: loadingProp,
  error: errorProp,
}: BetaOnboardingCockpitPageProps) {
  const injected = readinessProp !== undefined;
  const [readiness, setReadiness] = useState<CockpitReadiness | null>(
    readinessProp ?? null,
  );
  const [nextActions, setNextActions] = useState<CockpitNextActions | null>(
    nextActionsProp ?? null,
  );
  const [loading, setLoading] = useState<boolean>(loadingProp ?? !injected);
  const [error, setError] = useState<string | null>(errorProp ?? null);

  const load = useCallback(async () => {
    if (injected || !orgId) return;
    setLoading(true);
    setError(null);
    try {
      const base = `${apiFetchBase()}/v1/nf/demo/orgs/${orgId}/beta-cockpit`;
      const [r, a] = await Promise.all([
        fetch(`${base}/readiness`, { credentials: "include" }),
        fetch(`${base}/next-actions`, { credentials: "include" }),
      ]);
      if (!r.ok) {
        // 401 is the honest answer for a signed-out operator, not an error to
        // paper over.
        setError(
          r.status === 401
            ? "Sign in to your demo organization to see readiness."
            : `Readiness unavailable (HTTP ${r.status}).`,
        );
        setReadiness(null);
        return;
      }
      setReadiness((await r.json()) as CockpitReadiness);
      if (a.ok) setNextActions((await a.json()) as CockpitNextActions);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Readiness unavailable.");
    } finally {
      setLoading(false);
    }
  }, [injected, orgId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <main className="nf-beta-cockpit" data-testid="beta-cockpit-page">
        <p data-testid="beta-cockpit-loading">Reading deployment readiness…</p>
      </main>
    );
  }

  if (error || !readiness) {
    return (
      <main className="nf-beta-cockpit" data-testid="beta-cockpit-page">
        <h1>Beta Onboarding Cockpit</h1>
        <p data-testid="beta-cockpit-error">{error ?? "No readiness to show."}</p>
      </main>
    );
  }

  return (
    <main className="nf-beta-cockpit" data-testid="beta-cockpit-page">
      <header>
        <h1>Beta Onboarding Cockpit</h1>
        <p data-testid="beta-cockpit-scope">
          Scope: <strong>{readiness.cockpit_scope}</strong>. This is what the
          deployment can do — not a customer&rsquo;s pipeline.
        </p>
        <p data-testid="beta-cockpit-production" className="nf-muted">
          Production rollout:{" "}
          <strong>{readiness.production_rollout ? "true" : "false"}</strong>.
          Controlled customer pilot:{" "}
          <strong>
            {readiness.controlled_customer_pilot ? "true" : "false"}
          </strong>
          .
        </p>
      </header>

      <section aria-label="Readiness lanes">
        <ul className="nf-cockpit-lanes" data-testid="beta-cockpit-lanes">
          {readiness.lanes.map((lane) => (
            <li
              key={lane.lane}
              className={`nf-cockpit-lane nf-cockpit-lane--${lane.status}`}
              data-testid={`beta-cockpit-lane-${lane.lane}`}
              data-lane-status={lane.status}
              data-lane-value={String(lane.value)}
            >
              <h2>{laneLabel(lane.lane)}</h2>
              <p className="nf-cockpit-status">
                <span data-testid={`beta-cockpit-status-${lane.lane}`}>
                  {statusLabel(lane.status)}
                </span>
                {lane.scope ? <span className="nf-muted"> · {lane.scope}</span> : null}
              </p>
              <p className="nf-cockpit-summary">{lane.summary}</p>
              {lane.blockers.length > 0 ? (
                <ul
                  className="nf-cockpit-blockers"
                  data-testid={`beta-cockpit-blockers-${lane.lane}`}
                >
                  {lane.blockers.map((blocker) => (
                    <li key={blocker}>{blocker}</li>
                  ))}
                </ul>
              ) : null}
              {lane.owner ? (
                <p className="nf-muted">Owner: {lane.owner}</p>
              ) : null}
            </li>
          ))}
        </ul>
      </section>

      {nextActions ? (
        <section aria-label="Next safe action" data-testid="beta-cockpit-next">
          <h2>Next safe action</h2>
          <p data-testid="beta-cockpit-next-action">
            {nextActions.next_safe_action}
          </p>
          <p className="nf-muted">{nextActions.why}</p>
          <p className="nf-muted">Safe because: {nextActions.safe_because}</p>
          <h3>Not yet</h3>
          <ul data-testid="beta-cockpit-not-yet">
            {nextActions.not_this_yet.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {readiness.invariant_failures.length > 0 ? (
        <section aria-label="Invariant failures">
          <h2>Invariant failures</h2>
          <ul data-testid="beta-cockpit-invariants">
            {readiness.invariant_failures.map((failure) => (
              <li key={failure}>{failure}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </main>
  );
}

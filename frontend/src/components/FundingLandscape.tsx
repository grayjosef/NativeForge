import type { OrgFunnelResponse } from "../fundingLandscapeApiClient";
import { formatUsdCompact } from "../fundingLandscapeApiClient";
import { MetricCard, MetricRow, Section } from "./ui/primitives";

export function FundingLandscape(props: { data: OrgFunnelResponse | null }) {
  const { data } = props;
  if (!data) return null;

  const active = data.stages.active;
  const native = data.stages.native_relevant;
  const elig = data.stages.eligibility;
  const pursuing = data.stages.pursuing;
  const da = data.decision_advantage ?? data.funding_landscape_v3;
  const expiring30 = da?.expiring_value?.windows?.["30d"]?.active;
  const gap = da?.gap_closure;
  const notPursued = da?.not_currently_pursued;

  const activeUsd = formatUsdCompact(active?.known_value_total_usd ?? null);
  const nativeUsd = formatUsdCompact(native?.known_value_total_usd ?? null);
  const expiringUsd = formatUsdCompact(
    expiring30?.expiring_known_value_by_currency?.USD ?? null,
  );

  return (
    <Section
      title="Funding landscape"
      lead="Known funding value by stage. Stages overlap — totals are not additive."
    >
      <MetricRow>
        <MetricCard
          label="Known active value"
          value={activeUsd ?? "—"}
          note={
            active
              ? `${active.known_count ?? "—"} of ${active.count ?? "—"} with known value`
              : undefined
          }
        />
        <MetricCard
          label="Native-relevant known"
          value={nativeUsd ?? "—"}
          note={
            native?.supported
              ? `${native.known_count ?? "—"} of ${native.count ?? "—"} relevant`
              : "Relevance assessments pending"
          }
        />
        <MetricCard
          label="Eligible (your org)"
          value={formatUsdCompact(elig?.eligible?.known_value_total_usd) ?? "—"}
          note={`${elig?.eligible?.known_count ?? "—"} opportunities`}
        />
        <MetricCard
          label="Currently pursuing"
          value={formatUsdCompact(pursuing?.known_value_total_usd) ?? "—"}
          note={`${pursuing?.known_count ?? "—"} with known value`}
        />
        {expiring30 ? (
          <MetricCard
            label="Known value expiring (30d)"
            value={expiringUsd ?? "—"}
            note={`${expiring30.expiring_known_count ?? "—"} of ${expiring30.expiring_opportunity_count ?? "—"} closing`}
          />
        ) : null}
        {notPursued ? (
          <MetricCard
            label="Not currently pursued"
            value={formatUsdCompact(notPursued.known_value_total_usd) ?? "—"}
            note={`${notPursued.known_count ?? "—"} eligible/conditional with known value`}
          />
        ) : null}
      </MetricRow>
      {gap?.supported && gap.by_condition ? (
        <p className="nf-muted-copy" style={{ marginTop: "0.5rem", fontSize: "0.85rem" }}>
          Gap-closure conditions are non-additive — do not sum condition slices.
        </p>
      ) : null}
      <p className="nf-muted-copy" style={{ marginTop: "0.75rem", fontSize: "0.85rem" }}>
        Based on opportunities with source-supported monetary values. Incomplete coverage is
        shown explicitly — not every active opportunity has a defensible dollar amount yet.
      </p>
    </Section>
  );
}

/** Read-only NM/WA operator surfacing demo page (demo/dev only). */

import { loadNmWaOperatorDemoPayload } from "../demo/loadNmWaOperatorDemo";
import type { NmWaOperatorDemoPayload } from "../demo/nmWaOperatorDemoTypes";

export type NmWaOperatorDemoPageProps = {
  payload?: NmWaOperatorDemoPayload;
};

export function NmWaOperatorDemoPage({ payload }: NmWaOperatorDemoPageProps) {
  const data = payload ?? loadNmWaOperatorDemoPayload();
  const sample = data.rows.slice(0, 12);

  return (
    <main className="nf-nm-wa-demo" data-testid="nm-wa-operator-demo-page">
      <header className="nf-nm-wa-demo-header">
        <h1 data-testid="nm-wa-demo-title">{data.title}</h1>
        <p className="nf-muted" data-testid="nm-wa-demo-banner">
          {data.ui_flags.advisory_banner}
        </p>
        <p className="nf-muted" data-testid="nm-wa-demo-flags">
          demo_dev_only={String(data.demo_dev_only)} offline_only=
          {String(data.offline_only)} auth_required={String(data.auth_required)}{" "}
          final_eligibility_claim_allowed=
          {String(data.final_eligibility_claim_allowed)} source_activation=
          {String(data.source_activation)}
        </p>
      </header>

      <section data-testid="nm-wa-demo-nm-summary">
        <h2>NM summary</h2>
        <p>
          fixtures={data.nm_summary.profile_count}/
          {data.nm_summary.expected}; classify+match=
          {data.nm_summary.classify_match_profiles}; operator report rows=
          {data.nm_summary.operator_report_rows}
        </p>
      </section>

      <section data-testid="nm-wa-demo-wa-summary">
        <h2>WA summary</h2>
        <p>
          fixtures={data.wa_summary.profile_count}/
          {data.wa_summary.expected}; classify+match=
          {data.wa_summary.classify_match_profiles}; operator report rows=
          {data.wa_summary.operator_report_rows}
        </p>
      </section>

      <section data-testid="nm-wa-demo-combined-summary">
        <h2>Combined review queue</h2>
        <p>
          combined={data.combined_summary.combined_profile_count}; review
          needed={data.combined_summary.combined_review_needed_count}; missing
          data rows={data.combined_summary.combined_missing_data_count}
        </p>
        <p data-testid="nm-wa-demo-confidence">
          confidence=
          {JSON.stringify(data.combined_summary.confidence_distribution)}
        </p>
      </section>

      <section data-testid="nm-wa-demo-missing-data">
        <h2>Missing-data summary</h2>
        <p>
          hidden_missing_data=
          {String(data.missing_data_summary.hidden_missing_data)}; combined
          missing=
          {data.missing_data_summary.combined_missing_data_count}
        </p>
        <pre>{JSON.stringify(data.missing_data_summary, null, 2)}</pre>
      </section>

      <section data-testid="nm-wa-demo-next-check">
        <h2>Human review + operator next-checks</h2>
        <p>
          human_review_required_count=
          {data.operator_next_check_summary.human_review_required_count}; rows
          with next-checks=
          {data.operator_next_check_summary.rows_with_next_checks}
        </p>
      </section>

      <section data-testid="nm-wa-demo-provenance">
        <h2>Provenance / evidence</h2>
        <p>
          notes_visible=
          {String(data.provenance_evidence_summary.notes_visible)}
        </p>
        <pre>
          {JSON.stringify(
            data.provenance_evidence_summary.combined_evidence_provenance_summary,
            null,
            2,
          )}
        </pre>
      </section>

      <section data-testid="nm-wa-demo-review-table">
        <h2>Sample operator review rows</h2>
        <table>
          <thead>
            <tr>
              <th>State</th>
              <th>Profile</th>
              <th>Readiness</th>
              <th>Confidence</th>
              <th>Human review</th>
              <th>Missing data</th>
              <th>Next checks</th>
              <th>Final claim allowed</th>
              <th>Discoverability</th>
            </tr>
          </thead>
          <tbody>
            {sample.map((r) => (
              <tr key={`${r.state_cohort}:${r.profile_id}`}>
                <td>{r.state_cohort}</td>
                <td>{r.profile_id}</td>
                <td>{r.match_readiness_label}</td>
                <td>{r.confidence}</td>
                <td>{String(r.human_review_required)}</td>
                <td>{r.missing_data.join(", ") || "(none listed)"}</td>
                <td>{r.operator_next_check.join("; ")}</td>
                <td>{String(r.final_eligibility_claim_allowed)}</td>
                <td>{r.discoverability}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <p className="nf-muted" data-testid="nm-wa-demo-digest">
        content_digest={data.content_digest}; prior_offline_smoke=
        {data.prior_offline_smoke_run_id}
      </p>
    </main>
  );
}

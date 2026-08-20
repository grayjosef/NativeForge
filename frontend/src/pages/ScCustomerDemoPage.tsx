/** Read-only SC Monday customer demo — curated state + federal opportunities. */

import { loadScCustomerDemoPayload } from "../demo/loadScCustomerDemo";
import type { ScCustomerDemoPayload } from "../demo/scCustomerDemoTypes";

export type ScCustomerDemoPageProps = {
  payload?: ScCustomerDemoPayload;
};

export function ScCustomerDemoPage({ payload }: ScCustomerDemoPageProps) {
  const data = payload ?? loadScCustomerDemoPayload();
  const scRows = data.rows.filter((r) => r.funding_geography === "south_carolina");
  const fedRows = data.rows.filter((r) => r.funding_geography === "federal");
  const sample = [...scRows.slice(0, 8), ...fedRows.slice(0, 12)];

  return (
    <main className="nf-sc-customer-demo" data-testid="sc-customer-demo-page">
      <header className="nf-sc-customer-demo-header">
        <h1 data-testid="sc-demo-title">{data.title}</h1>
        <p className="nf-muted" data-testid="sc-demo-banner">
          {data.ui_flags.advisory_banner}
        </p>
        <p className="nf-muted" data-testid="sc-demo-flags">
          demo_dev_only={String(data.demo_dev_only)} offline_only=
          {String(data.offline_only)} live_ingestion=
          {String(data.live_ingestion)} source_activation=
          {String(data.source_activation)} auth_required=
          {String(data.auth_required)} final_eligibility_claim_allowed=
          {String(data.final_eligibility_claim_allowed)} pack_id={data.pack_id}{" "}
          capture_date={data.capture_date}
        </p>
      </header>

      <section data-testid="sc-demo-what-nf-did">
        <h2>What NativeForge did</h2>
        <ul>
          {data.what_nativeforge_did.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>

      <section data-testid="sc-demo-attention">
        <h2>What requires your attention</h2>
        <ul>
          {data.what_requires_attention.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>

      <section data-testid="sc-demo-next-actions">
        <h2>What to do next</h2>
        <ol>
          {data.next_actions.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ol>
      </section>

      <section data-testid="sc-demo-profiles">
        <h2>Organization profiles (South Carolina)</h2>
        <p>
          profiles={data.profiles.profile_count}; federal_recognized=
          {data.profiles.federal_recognized_count}; state_only=
          {data.profiles.state_only_count}
        </p>
      </section>

      <section data-testid="sc-demo-opportunities">
        <h2>Curated opportunities (state + federal)</h2>
        <p>
          total={data.opportunities.total}; south_carolina=
          {data.opportunities.south_carolina_count}; federal=
          {data.opportunities.federal_count}
        </p>
        <p data-testid="sc-demo-labels">
          by_data_label={JSON.stringify(data.opportunities.by_data_label)}
        </p>
      </section>

      <section data-testid="sc-demo-combined-summary">
        <h2>Combined review queue</h2>
        <p>
          rows={data.combined_summary.row_count}; sc_rows=
          {data.combined_summary.south_carolina_row_count}; federal_rows=
          {data.combined_summary.federal_row_count}; human_review=
          {data.combined_summary.human_review_required_count}
        </p>
        <p data-testid="sc-demo-confidence">
          confidence=
          {JSON.stringify(data.combined_summary.confidence_distribution)}
        </p>
      </section>

      <section data-testid="sc-demo-missing-data">
        <h2>Missing data</h2>
        <p>
          hidden_missing_data=
          {String(data.missing_data_summary.hidden_missing_data)}; rows_with_missing=
          {data.missing_data_summary.rows_with_missing_data}
        </p>
      </section>

      <section data-testid="sc-demo-provenance">
        <h2>Provenance / evidence</h2>
        <p>
          notes_visible=
          {String(data.provenance_evidence_summary.notes_visible)};
          pack_evidence_required=
          {String(data.provenance_evidence_summary.pack_evidence_required)}
        </p>
      </section>

      <section data-testid="sc-demo-review-table">
        <h2>Sample org × opportunity rows</h2>
        <p className="nf-muted">{data.row_sample_note}</p>
        <table>
          <thead>
            <tr>
              <th>Profile</th>
              <th>Recognition</th>
              <th>Geography</th>
              <th>Opportunity</th>
              <th>Label</th>
              <th>Classification</th>
              <th>Readiness</th>
              <th>Discoverability</th>
              <th>Human review</th>
              <th>Final claim</th>
            </tr>
          </thead>
          <tbody>
            {sample.map((r) => (
              <tr key={`${r.profile_id}-${r.grant_id}`}>
                <td>{r.profile_id}</td>
                <td>{r.recognition_type}</td>
                <td>{r.funding_geography}</td>
                <td>{r.opportunity_title}</td>
                <td>{r.data_label}</td>
                <td>{r.classification_label}</td>
                <td>{r.match_readiness_label}</td>
                <td>{r.discoverability}</td>
                <td>{String(r.human_review_required)}</td>
                <td>{String(r.final_eligibility_claim_allowed)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}

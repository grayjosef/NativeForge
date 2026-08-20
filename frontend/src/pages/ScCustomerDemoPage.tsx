/** Read-only SC Monday customer demo — curated state + federal opportunities. */

import { loadScCustomerDemoPayload } from "../demo/loadScCustomerDemo";
import type { ScCustomerDemoPayload } from "../demo/scCustomerDemoTypes";

export type ScCustomerDemoPageProps = {
  payload?: ScCustomerDemoPayload | null;
  loading?: boolean;
  error?: string | null;
};

export function ScCustomerDemoPage({
  payload,
  loading = false,
  error = null,
}: ScCustomerDemoPageProps) {
  if (loading) {
    return (
      <main className="nf-sc-customer-demo" data-testid="sc-customer-demo-page">
        <p data-testid="sc-demo-loading">Loading South Carolina customer demo…</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="nf-sc-customer-demo" data-testid="sc-customer-demo-page">
        <p data-testid="sc-demo-error">Demo unavailable: {error}</p>
        <p className="nf-muted">
          Fallback: run `bash scripts/sc_monday_demo_staging_verify.sh` offline.
        </p>
      </main>
    );
  }

  const data = payload === undefined ? loadScCustomerDemoPayload() : payload;
  if (!data || !data.rows || data.rows.length === 0) {
    return (
      <main className="nf-sc-customer-demo" data-testid="sc-customer-demo-page">
        <p data-testid="sc-demo-empty">
          No curated opportunities loaded. Regen bridge JSON from assembler.
        </p>
      </main>
    );
  }

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
          {String(data.final_eligibility_claim_allowed)} data_mode=curated_current{" "}
          live_ingest_claimed=false automated_refresh_claimed=false pack_id=
          {data.pack_id} capture_date={data.capture_date}
        </p>
        <p data-testid="sc-demo-nofo-proposal-honesty" className="nf-muted">
          nofo_pdf_extraction=NOT_IN_THIS_BLOCK proposal_drafting=NOT_IN_THIS_BLOCK
        </p>
      </header>

      <section data-testid="sc-demo-what-nf-did">
        <h2>What NativeForge found / did</h2>
        <ul>
          {data.what_nativeforge_did.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>

      <section data-testid="sc-demo-attention">
        <h2>What is uncertain / needs your attention</h2>
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
        <h2>Which opportunities fit (curated state + federal)</h2>
        <p>
          total={data.opportunities.total}; south_carolina=
          {data.opportunities.south_carolina_count}; federal=
          {data.opportunities.federal_count}
        </p>
        <p data-testid="sc-demo-labels">
          by_data_label={JSON.stringify(data.opportunities.by_data_label)}{" "}
          curated_current_labels_visible=true
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
        <h2>Missing data / uncertainty</h2>
        <p>
          hidden_missing_data=
          {String(data.missing_data_summary.hidden_missing_data)}; rows_with_missing=
          {data.missing_data_summary.rows_with_missing_data}
        </p>
      </section>

      <section data-testid="sc-demo-provenance">
        <h2>Provenance / source evidence</h2>
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
              <th>Round</th>
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
                <td>{(r as { current_round_status?: string }).current_round_status || "n/a"}</td>
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

      {data.nofo_showcase ? (
        <section data-testid="sc-demo-nofo-showcase">
          <h2>{data.nofo_showcase.title}</h2>
          <p data-testid="sc-demo-nofo-showcase-flags" className="nf-muted">
            selected={data.nofo_showcase.selected_count} sc=
            {data.nofo_showcase.sc_selected_count} federal=
            {data.nofo_showcase.federal_selected_count} live_ingest_claimed=
            {String(data.nofo_showcase.live_ingest_claimed)} nofo_pdf_extraction_claimed=
            {String(data.nofo_showcase.nofo_pdf_extraction_claimed)}{" "}
            proposal_drafting_claimed=
            {String(data.nofo_showcase.proposal_drafting_claimed)}
          </p>
          <p data-testid="sc-demo-nofo-buyer-sections">
            {data.nofo_showcase.buyer_sections.join(" · ")}
          </p>
          {data.nofo_showcase.cards.map((card) => (
            <article
              key={card.opportunity_id}
              data-testid={`sc-demo-nofo-card-${card.opportunity_id}`}
              data-source-layer={card.source_layer}
            >
              <h3>
                {card.title || card.opportunity_id}{" "}
                <span className="nf-muted">({card.source_layer})</span>
              </h3>
              <p data-testid={`sc-demo-nofo-status-${card.opportunity_id}`}>
                field_status_counts={JSON.stringify(card.field_status_counts)}
              </p>
              <div data-testid={`sc-demo-nofo-found-${card.opportunity_id}`}>
                <h4>What NativeForge found</h4>
                <p>eligibility={String(card.what_nativeforge_found.eligibility ?? "")}</p>
                <p>
                  deadline=
                  {String(card.what_nativeforge_found.deadline ?? "n/a")} status=
                  {String(card.what_nativeforge_found.deadline_status ?? "")}
                </p>
              </div>
              <div data-testid={`sc-demo-nofo-means-${card.opportunity_id}`}>
                <h4>What this means</h4>
                <p>{card.what_this_means}</p>
              </div>
              <div data-testid={`sc-demo-nofo-missing-${card.opportunity_id}`}>
                <h4>What is missing</h4>
                <ul>
                  {card.what_is_missing.slice(0, 8).map((m) => (
                    <li key={String(m.field)}>
                      {String(m.field)}={String(m.status)}
                    </li>
                  ))}
                </ul>
              </div>
              <div data-testid={`sc-demo-nofo-human-${card.opportunity_id}`}>
                <h4>What needs human review</h4>
                <ul>
                  {card.what_needs_human_review.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              <div data-testid={`sc-demo-nofo-next-${card.opportunity_id}`}>
                <h4>What to do next</h4>
                <ol>
                  {card.what_to_do_next.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ol>
              </div>
              <div data-testid={`sc-demo-nofo-plan-${card.opportunity_id}`}>
                <h4>Application plan skeleton</h4>
                <p>
                  recommendation={card.application_plan.recommendation_label}{" "}
                  checklist_items=
                  {(card.application_plan.application_checklist || []).length}{" "}
                  missing_questions=
                  {(card.application_plan.missing_information_questions || []).length}{" "}
                  ready_for_submission=
                  {String(card.application_plan.completeness?.ready_for_submission)}{" "}
                  ready_for_narrative_drafting=
                  {String(
                    card.application_plan.completeness?.ready_for_narrative_drafting,
                  )}
                </p>
                <ul data-testid={`sc-demo-nofo-checklist-${card.opportunity_id}`}>
                  {(card.application_plan.application_checklist || [])
                    .slice(0, 6)
                    .map((item) => (
                      <li key={String(item.item)}>
                        {String(item.item)} [{String(item.status)}]
                      </li>
                    ))}
                </ul>
              </div>
              <div data-testid={`sc-demo-nofo-evidence-${card.opportunity_id}`}>
                <h4>Evidence / provenance</h4>
                <p>
                  captured_at={String(card.evidence_provenance.captured_at ?? "")}{" "}
                  source_reference=
                  {String(card.evidence_provenance.source_reference ?? "")}
                </p>
              </div>
              <div data-testid={`sc-demo-nofo-limits-${card.opportunity_id}`}>
                <h4>Limitations</h4>
                <ul>
                  {card.limitations.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </article>
          ))}
        </section>
      ) : null}
    </main>
  );
}

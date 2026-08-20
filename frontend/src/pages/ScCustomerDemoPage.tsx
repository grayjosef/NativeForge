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
  const buyer = data.buyer_demo;
  const opening =
    buyer?.opening_line ||
    "NativeForge structures South Carolina and federal grant opportunities for your organization.";
  const closing =
    buyer?.closing_line ||
    "Next step: human review of missing evidence — NativeForge will not submit or invent facts.";

  return (
    <main className="nf-sc-customer-demo" data-testid="sc-customer-demo-page">
      <header className="nf-sc-customer-demo-header">
        <p className="nf-sc-demo-kicker" data-testid="sc-demo-kicker">
          Monday buyer demo · South Carolina customer story
        </p>
        <h1 data-testid="sc-demo-title">{data.title}</h1>
        <p className="nf-sc-demo-opening" data-testid="sc-demo-opening-line">
          {opening}
        </p>
        <p className="nf-muted" data-testid="sc-demo-banner">
          {data.ui_flags.advisory_banner}
        </p>
        <div className="nf-sc-demo-trust-strip" data-testid="sc-demo-trust-strip">
          <span>curated-current</span>
          <span>not automated live ingest</span>
          <span>demo/real isolation</span>
          <span>human review required</span>
          <span>no final eligibility claim</span>
          <span>application-plan skeleton only</span>
          <span>NOFO PDF extraction not supported</span>
          <span>proposal drafting not supported</span>
        </div>
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
          nofo_pdf_extraction=NOT_SUPPORTED proposal_drafting=NOT_SUPPORTED
          application_plan=SKELETON_ONLY
        </p>
      </header>

      <section data-testid="sc-demo-what-nf-did" className="nf-sc-demo-section">
        <h2>What NativeForge found / did</h2>
        <p className="nf-sc-demo-why">Why this matters: structures discovery so your team reviews evidence, not raw noise.</p>
        <ul>
          {data.what_nativeforge_did.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>

      {data.why_this_matters && data.why_this_matters.length > 0 ? (
        <section data-testid="sc-demo-why-matters" className="nf-sc-demo-section">
          <h2>Why this matters</h2>
          <ul>
            {data.why_this_matters.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          {data.workload_reduction_statement ? (
            <p data-testid="sc-demo-workload">{data.workload_reduction_statement}</p>
          ) : null}
        </section>
      ) : null}

      <section data-testid="sc-demo-attention" className="nf-sc-demo-section">
        <h2>What is uncertain / needs your attention</h2>
        <p className="nf-sc-demo-why">What needs attention: active rounds, blockers, and missing evidence stay visible.</p>
        <ul>
          {data.what_requires_attention.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>

      <section data-testid="sc-demo-next-actions" className="nf-sc-demo-section">
        <h2>What to do next</h2>
        <p className="nf-sc-demo-why">What happens next: walk opportunities → intelligence → plan → human decision.</p>
        <ol>
          {data.next_actions.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ol>
      </section>

      <section data-testid="sc-demo-profiles" className="nf-sc-demo-section">
        <h2>Organization context (South Carolina)</h2>
        <p className="nf-sc-demo-why">What NativeForge did: loaded SC organization profiles with recognition tiers.</p>
        <p>
          profiles={data.profiles.profile_count}; federal_recognized=
          {data.profiles.federal_recognized_count}; state_only=
          {data.profiles.state_only_count}
        </p>
      </section>

      <section data-testid="sc-demo-opportunities" className="nf-sc-demo-section">
        <h2>South Carolina + federal opportunities (curated-current)</h2>
        <p className="nf-sc-demo-why">
          Why this matters: one review queue for state and federal lanes — not live ingest.
        </p>
        <p>
          total={data.opportunities.total}; south_carolina=
          {data.opportunities.south_carolina_count}; federal=
          {data.opportunities.federal_count}
        </p>
        <p data-testid="sc-demo-labels">
          by_data_label={JSON.stringify(data.opportunities.by_data_label)}{" "}
          curated_current_labels_visible=true not_automated_live_ingest=true
        </p>
      </section>

      <section data-testid="sc-demo-combined-summary" className="nf-sc-demo-section">
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

      <section data-testid="sc-demo-missing-data" className="nf-sc-demo-section">
        <h2>Missing data / uncertainty</h2>
        <p className="nf-sc-demo-why">Missing fields remain visible — they are not silently filled.</p>
        <p>
          hidden_missing_data=
          {String(data.missing_data_summary.hidden_missing_data)}; rows_with_missing=
          {data.missing_data_summary.rows_with_missing_data}
        </p>
      </section>

      <section data-testid="sc-demo-provenance" className="nf-sc-demo-section">
        <h2>Trust / provenance / source evidence</h2>
        <p className="nf-sc-demo-why">
          Source evidence and capture dates stay visible. This is not a pen-test claim or
          production-auth claim.
        </p>
        <p>
          notes_visible=
          {String(data.provenance_evidence_summary.notes_visible)};
          pack_evidence_required=
          {String(data.provenance_evidence_summary.pack_evidence_required)}; capture_date=
          {data.capture_date}; demo_real_isolation=visible
        </p>
      </section>

      {buyer ? (
        <section data-testid="sc-demo-claim-guardrails" className="nf-sc-demo-section">
          <h2>Claim guardrails (say this / do not say this)</h2>
          <div data-testid="sc-demo-allowed-claims">
            <h3>Allowed claims</h3>
            <ul>
              {buyer.allowed_claims.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
          <div data-testid="sc-demo-forbidden-claims">
            <h3>Forbidden claims</h3>
            <ul>
              {buyer.forbidden_claims.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}

      {data.opportunity_engine ? (
        <section data-testid="sc-demo-opportunity-engine" className="nf-sc-demo-section">
          <h2>Durable opportunity engine foundation</h2>
          <p className="nf-sc-demo-why">
            Product spine behind the Monday demo: SC reference-state adapter + federal
            layer + combined workflow (curated-current only).
          </p>
          <p data-testid="sc-demo-engine-flags" className="nf-muted">
            campaign_block={data.opportunity_engine.campaign_block} live_ingest_claimed=
            {String(data.opportunity_engine.live_ingest_claimed)} source_activation_claimed=
            {String(data.opportunity_engine.source_activation_claimed)}{" "}
            final_eligibility_claim_allowed=
            {String(data.opportunity_engine.final_eligibility_claim_allowed)}{" "}
            org_geo_filters_federal=
            {String(
              data.opportunity_engine.combined_workflow
                .organization_geography_filters_federal,
            )}
          </p>
          <p data-testid="sc-demo-engine-adapter">
            sc_adapter={String(data.opportunity_engine.sc_state_adapter.adapter_key)}{" "}
            reference_state=
            {String(
              data.opportunity_engine.sc_state_adapter.is_reference_state_implementation,
            )}{" "}
            data_mode_default=
            {String(data.opportunity_engine.sc_state_adapter.data_mode_default)}
          </p>
          <p data-testid="sc-demo-engine-counts">
            combined_counts=
            {JSON.stringify(data.opportunity_engine.combined_workflow.counts)}
          </p>
          <ul data-testid="sc-demo-engine-summary">
            {data.opportunity_engine.buyer_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          {data.opportunity_engine.combined_workflow.eligibility_evidence_handoff ? (
            <div data-testid="sc-demo-eligibility-evidence">
              <h3>Evidence-backed eligibility (recognition tier)</h3>
              <p className="nf-sc-demo-why">
                What NativeForge explains: applicant category, recognition tier, evidence,
                uncertainty, and next checks — without claiming final eligibility.
              </p>
              <p data-testid="sc-demo-eligibility-flags" className="nf-muted">
                pairs=
                {
                  data.opportunity_engine.combined_workflow.eligibility_evidence_handoff
                    .pair_count
                }{" "}
                federal_pairs_visible=
                {String(
                  data.opportunity_engine.combined_workflow.eligibility_evidence_handoff
                    .federal_pairs_visible,
                )}{" "}
                final_eligibility_claimed=
                {String(
                  data.opportunity_engine.combined_workflow.eligibility_evidence_handoff
                    .final_eligibility_claimed,
                )}{" "}
                scoring_math_changed=
                {String(
                  data.opportunity_engine.combined_workflow.eligibility_evidence_handoff
                    .scoring_math_changed,
                )}{" "}
                human_review_required=
                {String(
                  data.opportunity_engine.combined_workflow.eligibility_evidence_handoff
                    .human_review_required,
                )}
              </p>
              <ul data-testid="sc-demo-eligibility-samples">
                {(
                  data.opportunity_engine.combined_workflow.eligibility_evidence_handoff
                    .sample_pairs || []
                )
                  .slice(0, 6)
                  .map((p) => (
                    <li
                      key={`${p.profile_id}-${p.opportunity_id}`}
                      data-testid={`sc-demo-eligibility-pair-${p.profile_id}-${p.opportunity_id}`}
                    >
                      profile={String(p.profile_id)} opportunity=
                      {String(p.opportunity_id)} layer={String(p.source_layer)} category=
                      {String(p.applicant_category)} recognition_tier=
                      {String(p.recognition_tier)} evidence_status=
                      {String(p.evidence_status)} missing=
                      {JSON.stringify(p.missing_evidence || [])} gate=
                      {String(p.gate_outcome)} final_eligibility_claimed=
                      {String(p.final_eligibility_claimed)}
                    </li>
                  ))}
              </ul>
              <p data-testid="sc-demo-eligibility-tier-why" className="nf-muted">
                {
                  (
                    data.opportunity_engine.combined_workflow.eligibility_evidence_handoff
                      .sample_pairs || []
                  )[0]?.why_federal_recognition_matters
                }{" "}
                {
                  (
                    data.opportunity_engine.combined_workflow.eligibility_evidence_handoff
                      .sample_pairs || []
                  )[0]?.why_state_recognition_matters
                }
              </p>
            </div>
          ) : null}
        </section>
      ) : null}

      <section data-testid="sc-demo-review-table" className="nf-sc-demo-section">
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
                <td>
                  {(r as { current_round_status?: string }).current_round_status || "n/a"}
                </td>
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
        <section data-testid="sc-demo-nofo-showcase" className="nf-sc-demo-section">
          <h2>{data.nofo_showcase.title}</h2>
          <p className="nf-sc-demo-why">
            What happens after you pick an opportunity: honest synopsis intelligence and an
            application-plan skeleton — not a finished proposal.
          </p>
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
              className="nf-sc-demo-nofo-card"
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

      <footer className="nf-sc-demo-close" data-testid="sc-demo-closing">
        <h2>Close the demo</h2>
        <p data-testid="sc-demo-closing-line">{closing}</p>
      </footer>
    </main>
  );
}

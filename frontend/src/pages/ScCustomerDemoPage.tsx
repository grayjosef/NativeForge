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
                {String(
                  (
                    data.opportunity_engine.combined_workflow.eligibility_evidence_handoff
                      .sample_pairs || []
                  )[0]?.why_federal_recognition_matters ?? "",
                )}{" "}
                {String(
                  (
                    data.opportunity_engine.combined_workflow.eligibility_evidence_handoff
                      .sample_pairs || []
                  )[0]?.why_state_recognition_matters ?? "",
                )}
              </p>
            </div>
          ) : null}
        </section>
      ) : null}

      {data.pursuit_workspace ? (
        <section data-testid="sc-demo-pursuit-workspace" className="nf-sc-demo-section">
          <h2>Pursuit workspace / application package</h2>
          <p className="nf-sc-demo-why">
            What happens after you decide an opportunity is worth pursuing: a review-gated
            workspace and evidence binder — not a finished proposal or submission.
          </p>
          <p data-testid="sc-demo-pursuit-flags" className="nf-muted">
            workspaces={data.pursuit_workspace.workspace_count} final_submission_allowed=
            {String(data.pursuit_workspace.final_submission_allowed)}{" "}
            submission_ready_claimed=
            {String(data.pursuit_workspace.submission_ready_claimed)}{" "}
            proposal_drafting_claimed=
            {String(data.pursuit_workspace.proposal_drafting_claimed)} live_ingest_claimed=
            {String(data.pursuit_workspace.live_ingest_claimed)} scoring_math_changed=
            {String(data.pursuit_workspace.scoring_math_changed)}
          </p>
          <ul data-testid="sc-demo-pursuit-summary">
            {data.pursuit_workspace.buyer_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          {data.pursuit_workspace.workspaces.slice(0, 4).map((item) => {
            const ws = item.workspace;
            return (
              <article
                key={ws.pursuit_workspace_id}
                className="nf-sc-demo-nofo-card"
                data-testid={`sc-demo-pursuit-card-${ws.pursuit_workspace_id}`}
                data-source-layer={ws.opportunity_source_layer}
              >
                <h3>
                  {ws.opportunity_id} × {ws.organization_profile_id}{" "}
                  <span className="nf-muted">({ws.opportunity_source_layer})</span>
                </h3>
                <p>
                  readiness={ws.readiness_status} pursuit_status={ws.pursuit_status}{" "}
                  not_submission_ready=
                  {String(ws.not_submission_ready_label ?? true)} human_review=
                  {String(ws.human_review_required)} final_submission_allowed=
                  {String(ws.final_submission_allowed)}
                </p>
                <p data-testid={`sc-demo-pursuit-why-${ws.pursuit_workspace_id}`}>
                  why_worth_review={ws.why_worth_review}
                </p>
                <p>
                  binder_items={item.evidence_binder.item_count} missing_or_needs_conf=
                  {item.evidence_binder.missing_or_needs_confirmation_ids.length}{" "}
                  nofo_linked={String(item.nofo_intelligence_present)} checklist=
                  {String(
                    (item.application_plan_summary as { checklist_count?: number })
                      ?.checklist_count ?? 0,
                  )}
                </p>
                <div>
                  <h4>Missing information</h4>
                  <ul>
                    {ws.missing_information_summary.slice(0, 6).map((m) => (
                      <li key={m}>{m}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4>Operator next actions</h4>
                  <ol>
                    {ws.operator_next_actions.slice(0, 5).map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ol>
                </div>
                <div>
                  <h4>What NativeForge pre-built</h4>
                  <ul>
                    {(ws.what_nativeforge_prebuilt || []).map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4>What the customer must provide</h4>
                  <ul>
                    {(ws.what_customer_must_provide || []).map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                </div>
                <p className="nf-muted">
                  proposal_drafting_claimed=
                  {String(ws.proposal_drafting_claimed)} submission_ready_claimed=
                  {String(ws.submission_ready_claimed)} — no submit control
                </p>
              </article>
            );
          })}
        </section>
      ) : null}

      {data.application_plan_workspace ? (
        <section
          data-testid="sc-demo-application-checklist"
          className="nf-sc-demo-section"
        >
          <h2>Application checklist / package build plan</h2>
          <p className="nf-sc-demo-why">
            What exactly is needed to move the application forward: executable checklist
            sections, missing-information questions, and review gates — not a finished
            proposal or submission.
          </p>
          <p data-testid="sc-demo-checklist-flags" className="nf-muted">
            workspaces={data.application_plan_workspace.workspace_count}{" "}
            submission_allowed=
            {String(data.application_plan_workspace.submission_allowed)}{" "}
            submission_ready_claimed=
            {String(data.application_plan_workspace.submission_ready_claimed)}{" "}
            proposal_drafting_claimed=
            {String(data.application_plan_workspace.proposal_drafting_claimed)}{" "}
            application_complete_claimed=
            {String(data.application_plan_workspace.application_complete_claimed)}{" "}
            nofo_pdf_extraction_claimed=
            {String(data.application_plan_workspace.nofo_pdf_extraction_claimed)}
          </p>
          <ul data-testid="sc-demo-checklist-summary">
            {data.application_plan_workspace.buyer_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          {data.application_plan_workspace.workspaces.slice(0, 3).map((item) => {
            const aw = item.application_workspace;
            return (
              <article
                key={aw.application_workspace_id}
                className="nf-sc-demo-nofo-card"
                data-testid={`sc-demo-checklist-card-${aw.application_workspace_id}`}
                data-source-layer={item.opportunity_source_layer}
              >
                <h3>
                  {item.opportunity_id} × {item.organization_profile_id}{" "}
                  <span className="nf-muted">({item.opportunity_source_layer})</span>
                </h3>
                <p>
                  sections={aw.section_count} items={aw.item_count} incomplete=
                  {item.incomplete_item_count} questions={item.question_count}{" "}
                  submission_allowed={String(item.submission_allowed)}
                </p>
                <p data-testid={`sc-demo-checklist-why-${aw.application_workspace_id}`}>
                  why_submission_not_allowed={item.why_submission_not_allowed}
                </p>
                <div>
                  <h4>Checklist sections</h4>
                  <ul>
                    {aw.checklist_sections.slice(0, 8).map((s) => (
                      <li key={s.section_id}>{s.title}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4>Item status sample</h4>
                  <ul>
                    {aw.checklist_items.slice(0, 6).map((ci) => (
                      <li key={ci.item_id}>
                        {ci.label} — status={ci.item_status}
                        {ci.unsupported_claim_guard ? " [unsupported]" : ""}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4>Missing information questions</h4>
                  <ul>
                    {item.questionnaire.questions.slice(0, 5).map((q) => (
                      <li key={q.question_id}>
                        [{q.group}] {q.prompt}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4>What NativeForge already knows</h4>
                  <ul>
                    {(item.what_nativeforge_knows || []).map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4>What the customer must provide</h4>
                  <ul>
                    {(item.what_customer_must_provide || []).slice(0, 6).map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4>What requires human review</h4>
                  <ul>
                    {(item.what_requires_human_review || []).slice(0, 5).map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4>Unsupported claims</h4>
                  <ul data-testid={`sc-demo-checklist-unsupported-${aw.application_workspace_id}`}>
                    {(item.unsupported_claims || []).map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                </div>
                <p className="nf-muted">
                  No submit control. No proposal generation. Application not complete.
                </p>
              </article>
            );
          })}
        </section>
      ) : null}

      {data.intake_approval_workspace ? (
        <section
          data-testid="sc-demo-intake-approvals"
          className="nf-sc-demo-section"
        >
          <h2>Intake &amp; approvals / package gaps</h2>
          <p className="nf-sc-demo-why">
            Where documents, confirmations, and human approvals go to close checklist
            gaps — planned intake only. No binary upload persistence and no approval
            persistence claimed in this layer.
          </p>
          <p data-testid="sc-demo-intake-flags" className="nf-muted">
            workspaces={data.intake_approval_workspace.workspace_count}{" "}
            upload_persistence_supported=
            {String(
              data.intake_approval_workspace.binary_upload_persistence_supported,
            )}{" "}
            upload_persistence_claimed=
            {String(data.intake_approval_workspace.binary_upload_persistence_claimed)}{" "}
            approval_persistence_supported=
            {String(data.intake_approval_workspace.approval_persistence_supported)}{" "}
            approval_persistence_claimed=
            {String(data.intake_approval_workspace.approval_persistence_claimed)}{" "}
            package_readiness_unlocked=
            {String(data.intake_approval_workspace.package_readiness_unlocked)}{" "}
            submission_ready_claimed=
            {String(data.intake_approval_workspace.submission_ready_claimed)}
          </p>
          <ul data-testid="sc-demo-intake-summary">
            {data.intake_approval_workspace.buyer_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          {data.intake_approval_workspace.workspaces.slice(0, 3).map((item) => (
            <article
              key={item.application_workspace_id}
              className="nf-sc-demo-nofo-card"
              data-testid={`sc-demo-intake-card-${item.application_workspace_id}`}
              data-source-layer={item.opportunity_source_layer}
            >
              <h3>
                {item.opportunity_id} × {item.organization_profile_id}{" "}
                <span className="nf-muted">({item.opportunity_source_layer})</span>
              </h3>
              <p>
                intake_items={item.intake_item_count} approvals={item.approval_count}{" "}
                open_approvals={item.open_approval_count}
              </p>
              <p data-testid={`sc-demo-intake-why-${item.application_workspace_id}`}>
                why_package_not_ready={item.why_package_not_ready}
              </p>
              <div>
                <h4>Required intake items</h4>
                <ul>
                  {item.intake_plan.intake_items.slice(0, 6).map((ii) => (
                    <li key={ii.intake_item_id}>
                      [{ii.intake_type}] {ii.item_label} — status={ii.current_status}{" "}
                      evidence=
                      {(ii.accepted_evidence_types || []).join("|")} section=
                      {ii.source_checklist_section}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h4>What the customer must provide</h4>
                <ul>
                  {(item.customer_must_provide || []).slice(0, 6).map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h4>What the operator must verify</h4>
                <ul>
                  {(item.operator_must_verify || []).slice(0, 6).map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h4>Required reviewer roles</h4>
                <ul>
                  {(item.required_reviewer_roles || []).map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h4>Approval status sample</h4>
                <ul>
                  {item.approval_workflow.approvals.slice(0, 5).map((a) => (
                    <li key={a.approval_id}>
                      {a.approval_type} — role={a.required_reviewer_role} status=
                      {a.approval_status}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h4>What remains blocked</h4>
                <ul>
                  {(item.what_remains_blocked || []).map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              </div>
              <p className="nf-muted">
                No upload storage claim. No approval persistence claim. No submit
                control. No proposal generation.
              </p>
            </article>
          ))}
        </section>
      ) : null}

      {data.narrative_budget_scaffold ? (
        <section
          data-testid="sc-demo-narrative-budget"
          className="nf-sc-demo-section"
        >
          <h2>Narrative &amp; budget scaffold</h2>
          <p className="nf-sc-demo-why">
            What sections this application probably needs, what evidence exists, and
            what budget/match facts must be gathered before anyone writes — no generated
            proposal prose.
          </p>
          <p data-testid="sc-demo-narrative-flags" className="nf-muted">
            workspaces={data.narrative_budget_scaffold.workspace_count}{" "}
            drafting_supported=
            {String(data.narrative_budget_scaffold.drafting_supported)}{" "}
            generated_prose_produced=
            {String(data.narrative_budget_scaffold.generated_prose_produced)}{" "}
            proposal_drafting_claimed=
            {String(data.narrative_budget_scaffold.proposal_drafting_claimed)}{" "}
            budget_claimed_complete=
            {String(data.narrative_budget_scaffold.budget_claimed_complete)}{" "}
            match_claimed_complete=
            {String(data.narrative_budget_scaffold.match_claimed_complete)}
          </p>
          <ul data-testid="sc-demo-narrative-summary">
            {data.narrative_budget_scaffold.buyer_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          {data.narrative_budget_scaffold.workspaces.slice(0, 3).map((item) => (
            <article
              key={`${item.application_workspace_id}-nb`}
              className="nf-sc-demo-nofo-card"
              data-testid={`sc-demo-narrative-card-${item.application_workspace_id}`}
              data-source-layer={item.opportunity_source_layer}
            >
              <h3>
                {item.opportunity_id} × {item.organization_profile_id}{" "}
                <span className="nf-muted">({item.opportunity_source_layer})</span>
              </h3>
              <p>
                sections={item.section_count} drafting_supported=
                {String(item.drafting_supported)} generated_prose=
                {String(item.generated_prose_produced)}
              </p>
              <p data-testid={`sc-demo-narrative-why-${item.application_workspace_id}`}>
                why_drafting_not_supported={item.why_drafting_not_supported}
              </p>
              <div>
                <h4>Likely / required narrative sections</h4>
                <ul>
                  {item.narrative_scaffold.sections.slice(0, 8).map((s) => (
                    <li key={s.section_id}>
                      {s.section_label} — status={s.section_required_status}
                      {s.unsupported_claim_guard ? " [unsupported]" : ""} known=
                      {(s.known_evidence || []).length} missing=
                      {(s.missing_evidence || []).length}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h4>Missing narrative questions</h4>
                <ul>
                  {(item.customer_questions || []).slice(0, 5).map((q) => (
                    <li key={q}>{q}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h4>Budget / match evidence</h4>
                <p>
                  budget_required={item.budget_match_evidence.budget_required_status}{" "}
                  match_required={item.budget_match_evidence.match_required_status}{" "}
                  cost_share=
                  {item.budget_match_evidence.cost_share_required_status}{" "}
                  amount_requested_known=
                  {String(item.budget_match_evidence.amount_requested_known)}{" "}
                  match_amount_known=
                  {String(item.budget_match_evidence.match_amount_known)}{" "}
                  budget_complete=
                  {String(item.budget_match_evidence.budget_claimed_complete)}{" "}
                  match_complete=
                  {String(item.budget_match_evidence.match_claimed_complete)}
                </p>
                <ul>
                  {(item.budget_match_evidence.missing_budget_facts || [])
                    .slice(0, 6)
                    .map((f) => (
                      <li key={f}>{f}</li>
                    ))}
                </ul>
              </div>
              <div>
                <h4>Budget customer questions</h4>
                <ul>
                  {(item.budget_customer_questions || []).slice(0, 5).map((q) => (
                    <li key={q}>{q}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h4>Operator checks</h4>
                <ul>
                  {(item.operator_checks || []).slice(0, 5).map((q) => (
                    <li key={q}>{q}</li>
                  ))}
                </ul>
              </div>
              <p className="nf-muted">
                No generate-proposal control. No fabricated budget. No match claim
                without evidence.
              </p>
            </article>
          ))}
        </section>
      ) : null}

      {data.package_readiness_queue ? (
        <section
          data-testid="sc-demo-readiness-queue"
          className="nf-sc-demo-section"
        >
          <h2>Readiness &amp; review queue</h2>
          <p className="nf-sc-demo-why">
            Total package status across eligibility, binder, checklist, intake,
            approvals, narrative, and budget — with human-review priorities and the
            next safest action. Not submission-ready.
          </p>
          <p data-testid="sc-demo-readiness-flags" className="nf-muted">
            workspaces={data.package_readiness_queue.workspace_count}{" "}
            submission_ready_claimed=
            {String(data.package_readiness_queue.submission_ready_claimed)}{" "}
            final_eligibility_claimed=
            {String(data.package_readiness_queue.final_eligibility_claimed)}{" "}
            proposal_drafting_claimed=
            {String(data.package_readiness_queue.proposal_drafting_claimed)}{" "}
            live_ingest_claimed=
            {String(data.package_readiness_queue.live_ingest_claimed)}{" "}
            not_submission_ready=
            {String(data.package_readiness_queue.not_submission_ready_label)}
          </p>
          <ul data-testid="sc-demo-readiness-summary">
            {data.package_readiness_queue.buyer_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          {data.package_readiness_queue.workspaces.slice(0, 3).map((item) => (
            <article
              key={`${item.application_workspace_id}-rq`}
              className="nf-sc-demo-nofo-card"
              data-testid={`sc-demo-readiness-card-${item.application_workspace_id}`}
              data-source-layer={item.opportunity_source_layer}
            >
              <h3>
                {item.opportunity_id} × {item.organization_profile_id}{" "}
                <span className="nf-muted">({item.opportunity_source_layer})</span>
              </h3>
              <p>
                overall={item.overall_readiness_status} missing=
                {item.missing_information_count} human_review=
                {item.human_review_count} unsupported=
                {item.unsupported_capability_count} queue_items=
                {item.review_item_count} critical={item.critical_count}
              </p>
              <p data-testid={`sc-demo-readiness-next-${item.application_workspace_id}`}>
                next_safest_action={item.next_safest_action}
              </p>
              <div>
                <h4>Per-layer readiness</h4>
                <ul>
                  <li>
                    eligibility={item.package_readiness.eligibility_readiness}
                  </li>
                  <li>binder={item.package_readiness.binder_readiness}</li>
                  <li>checklist={item.package_readiness.checklist_readiness}</li>
                  <li>intake={item.package_readiness.intake_readiness}</li>
                  <li>approval={item.package_readiness.approval_readiness}</li>
                  <li>
                    narrative=
                    {item.package_readiness.narrative_scaffold_readiness}
                  </li>
                  <li>
                    budget_match={item.package_readiness.budget_match_readiness}
                  </li>
                </ul>
              </div>
              <div>
                <h4>Blockers</h4>
                <ul>
                  {(item.blocked_reasons || []).slice(0, 6).map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h4>Operator review queue</h4>
                <ol>
                  {item.operator_review_queue.items.slice(0, 8).map((ri) => (
                    <li key={ri.review_item_id}>
                      [{ri.priority}] {ri.review_type}: {ri.issue_label}
                      {ri.unsupported_claim_guard ? " [unsupported]" : ""}
                    </li>
                  ))}
                </ol>
              </div>
              <div>
                <h4>Customer actions</h4>
                <ul>
                  {(item.customer_next_actions || []).slice(0, 5).map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h4>Operator actions</h4>
                <ul>
                  {(item.operator_next_actions || []).slice(0, 5).map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              </div>
              <p className="nf-muted">
                No submit control. No proposal generation. No final eligibility claim.
                No live ingest claim.
              </p>
            </article>
          ))}
        </section>
      ) : null}

      {data.organization_evidence_memory ? (
        <section
          data-testid="sc-demo-org-evidence-memory"
          className="nf-sc-demo-section"
        >
          <h2>Organization evidence memory</h2>
          <p className="nf-sc-demo-why">
            Durable fixture-backed org context for recognition, UEI/SAM gaps,
            attachments, governance, and prohibited claims — so packages are not a
            blank slate. No customer persistence claimed. No final eligibility from
            memory alone.
          </p>
          <p data-testid="sc-demo-org-memory-flags" className="nf-muted">
            profiles={data.organization_evidence_memory.profile_count} federal=
            {data.organization_evidence_memory.federal_count} state_only=
            {data.organization_evidence_memory.state_only_count}{" "}
            customer_data_persistence_claimed=
            {String(
              data.organization_evidence_memory.customer_data_persistence_claimed,
            )}{" "}
            final_eligibility_claimed=
            {String(data.organization_evidence_memory.final_eligibility_claimed)}{" "}
            live_ingest_claimed=
            {String(data.organization_evidence_memory.live_ingest_claimed)}{" "}
            binary_upload_persistence_supported=
            {String(
              data.organization_evidence_memory.binary_upload_persistence_supported,
            )}
          </p>
          <ul data-testid="sc-demo-org-memory-summary">
            {data.organization_evidence_memory.buyer_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          {data.organization_evidence_memory.cards.slice(0, 4).map((card) => (
            <article
              key={card.organization_evidence_profile_id}
              className="nf-sc-demo-nofo-card"
              data-testid={`sc-demo-org-memory-card-${card.organization_profile_id}`}
            >
              <h3>
                {card.organization_name}{" "}
                <span className="nf-muted">
                  ({card.recognition_tier} / {card.recognition_status})
                </span>
              </h3>
              <p>
                evidence_status={card.evidence_status} uei={card.uei_status} sam=
                {card.sam_status} geography=
                {card.service_geography || "unknown"} human_review=
                {String(card.human_review_required)}
              </p>
              <div>
                <h4>Approved facts</h4>
                {(card.approved_org_facts || []).length === 0 ? (
                  <p className="nf-muted">None auto-approved without review.</p>
                ) : (
                  <ul>
                    {card.approved_org_facts.map((f) => (
                      <li key={String(f.fact_id)}>{String(f.label)}</li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <h4>Must not claim</h4>
                <ul>
                  {(card.prohibited_org_claims || []).slice(0, 4).map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h4>Missing evidence</h4>
                <ul>
                  {(card.missing_evidence || []).slice(0, 6).map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h4>Standard attachments / governance</h4>
                <ul>
                  {(card.standard_attachments || []).slice(0, 4).map((a) => (
                    <li key={String(a.attachment_id)}>
                      {String(a.label)}: {String(a.status)}
                    </li>
                  ))}
                  {(card.governance_documents || []).slice(0, 2).map((g) => (
                    <li key={String(g.document_id)}>
                      {String(g.label)}: {String(g.status)}
                    </li>
                  ))}
                  {(card.tribal_resolution_requirements || [])
                    .slice(0, 2)
                    .map((r) => (
                      <li key={String(r.requirement_id)}>
                        {String(r.label)}: {String(r.status)}
                      </li>
                    ))}
                </ul>
              </div>
              <div>
                <h4>How memory helps readiness</h4>
                <ul>
                  {(card.how_memory_helps_readiness || []).slice(0, 4).map((h) => (
                    <li key={h}>{h}</li>
                  ))}
                </ul>
              </div>
              <p className="nf-muted">
                No fabricated org facts. No binary upload persistence. Federal and
                state recognition stay distinct.
              </p>
            </article>
          ))}
        </section>
      ) : null}

      {data.nofo_extraction_pilot ? (
        <section
          data-testid="sc-demo-nofo-extraction-pilot"
          className="nf-sc-demo-section"
        >
          <h2>NOFO extraction pilot</h2>
          <p className="nf-sc-demo-why">
            Controlled extraction for one showcase opportunity from fixture text
            derived from Grants.gov synopsis. PDF bytes are not parsed. Not
            generalized. Human review required.
          </p>
          <p data-testid="sc-demo-nofo-extract-flags" className="nf-muted">
            opportunity={data.nofo_extraction_pilot.pilot_opportunity_id} status=
            {data.nofo_extraction_pilot.extraction_status} scope=
            {data.nofo_extraction_pilot.extraction_scope}{" "}
            full_pdf_extraction_claimed=
            {String(data.nofo_extraction_pilot.full_pdf_extraction_claimed)}{" "}
            broad_pdf_support_claimed=
            {String(data.nofo_extraction_pilot.broad_pdf_support_claimed)}{" "}
            pdf_bytes_parsed=
            {String(data.nofo_extraction_pilot.pdf_bytes_parsed)}{" "}
            proposal_drafting_claimed=
            {String(data.nofo_extraction_pilot.proposal_drafting_claimed)}{" "}
            final_eligibility_claimed=
            {String(data.nofo_extraction_pilot.final_eligibility_claimed)}
          </p>
          <ul data-testid="sc-demo-nofo-extract-summary">
            {data.nofo_extraction_pilot.buyer_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p className="nf-muted">
            source={data.nofo_extraction_pilot.source_document_label} named_pdf=
            {data.nofo_extraction_pilot.named_pdf_attachment_referenced || "none"}
          </p>
          <div>
            <h3>Sections</h3>
            <ul data-testid="sc-demo-nofo-extract-sections">
              {data.nofo_extraction_pilot.sections.slice(0, 12).map((s) => (
                <li key={String(s.section_id)}>
                  {String(s.heading)}: {String(s.status)} / confidence=
                  {String(s.confidence)}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3>Requirements map</h3>
            <ul data-testid="sc-demo-nofo-extract-requirements">
              {data.nofo_extraction_pilot.requirements_map.map((r) => (
                <li key={String(r.requirement_id || r.field_id)}>
                  {String(r.label)}: {String(r.status)} / confidence=
                  {String(r.confidence)}
                </li>
              ))}
            </ul>
          </div>
          <p className="nf-muted">
            No full PDF claim. No broad coverage. No proposal drafting. No final
            eligibility from extraction.
          </p>
        </section>
      ) : null}

      {data.source_freshness_pilot ? (
        <section
          data-testid="sc-demo-source-freshness"
          className="nf-sc-demo-section"
        >
          <h2>Source freshness / source health</h2>
          <p className="nf-sc-demo-why">
            Read-only freshness pilot for controlled sources. Fixture-backed
            checks only — external live network check not run. Not continuous
            monitoring. Not production activation.
          </p>
          <p data-testid="sc-demo-source-freshness-flags" className="nf-muted">
            sources={data.source_freshness_pilot.source_count}{" "}
            external_live_check_not_run=
            {String(data.source_freshness_pilot.external_live_check_not_run)}{" "}
            live_ingest_claimed=
            {String(data.source_freshness_pilot.live_ingest_claimed)}{" "}
            continuous_monitoring_claimed=
            {String(data.source_freshness_pilot.continuous_monitoring_claimed)}{" "}
            production_activation_claimed=
            {String(data.source_freshness_pilot.production_activation_claimed)}
          </p>
          <ul data-testid="sc-demo-source-freshness-summary">
            {data.source_freshness_pilot.buyer_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          {data.source_freshness_pilot.records.map((rec) => (
            <article
              key={rec.source_id}
              className="nf-sc-demo-nofo-card"
              data-testid={`sc-demo-source-card-${rec.source_id}`}
            >
              <h3>
                {rec.source_name}{" "}
                <span className="nf-muted">({rec.source_layer})</span>
              </h3>
              <p>
                freshness={rec.freshness_status} health={rec.source_health}{" "}
                retrieval={rec.retrieval_status} change={rec.change_status}{" "}
                last_checked={rec.last_checked_at || "not_checked"}
              </p>
              <p>
                deadline_risk={rec.known_deadline_risk} expiration_risk=
                {rec.known_expiration_risk}
              </p>
              <p>operator_next_check={rec.operator_next_check}</p>
            </article>
          ))}
          <div>
            <h3>Verify before customer reliance</h3>
            <ul>
              {(
                data.source_freshness_pilot
                  .what_must_be_verified_before_customer_reliance || []
              ).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
          <p className="nf-muted">
            No live ingest claim. No continuous monitoring claim. No production
            activation claim.
          </p>
        </section>
      ) : null}

      {data.draft_workspace ? (
        <section
          data-testid="sc-demo-draft-workspace"
          className="nf-sc-demo-section"
        >
          <h2>Draft workspace (human-authored)</h2>
          <p className="nf-sc-demo-why">
            Organize customer/human prose by narrative section, link evidence,
            and flag unsupported claims. AI drafting is disabled here. No generate
            proposal control.
          </p>
          <p data-testid="sc-demo-draft-ws-flags" className="nf-muted">
            workspaces={data.draft_workspace.workspace_count} ai_drafting_enabled=
            {String(data.draft_workspace.ai_drafting_enabled)}{" "}
            generated_prose_present=
            {String(data.draft_workspace.generated_prose_present)}{" "}
            customer_prose_persistence_claimed=
            {String(data.draft_workspace.customer_prose_persistence_claimed)}{" "}
            submission_ready_claimed=
            {String(data.draft_workspace.submission_ready_claimed)}{" "}
            final_application_claimed=
            {String(data.draft_workspace.final_application_claimed)}
          </p>
          <ul data-testid="sc-demo-draft-ws-summary">
            {data.draft_workspace.buyer_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          {data.draft_workspace.workspaces.slice(0, 2).map((ws) => (
            <article
              key={ws.draft_workspace_id}
              className="nf-sc-demo-nofo-card"
              data-testid={`sc-demo-draft-ws-card-${ws.draft_workspace_id}`}
            >
              <h3>
                {ws.opportunity_id} × {ws.organization_profile_id}
              </h3>
              <p>
                mode={ws.draft_mode} status={ws.draft_status} sections=
                {ws.section_count}
              </p>
              <ul>
                {ws.sections.slice(0, 6).map((s) => (
                  <li key={s.draft_section_id}>
                    {s.section_label}: text_source={s.text_source} review=
                    {s.review_status} unsupported=
                    {(s.unsupported_claim_flags || []).length} missing_citations=
                    {(s.missing_citation_flags || []).length} generated_text=
                    {String(s.generated_text)}
                  </li>
                ))}
              </ul>
              <p className="nf-muted">
                Reviewer notes placeholder: human review required. Persistence not
                claimed.
              </p>
            </article>
          ))}
        </section>
      ) : null}

      {data.controlled_drafting ? (
        <section
          data-testid="sc-demo-controlled-drafting"
          className="nf-sc-demo-section"
        >
          <h2>Controlled draft v0</h2>
          <p className="nf-sc-demo-why">
            Evidence-cited drafting only. Missing facts become placeholders and
            questions. Not a complete proposal. Not submission-ready.
          </p>
          <p data-testid="sc-demo-controlled-draft-flags" className="nf-muted">
            workspaces={data.controlled_drafting.workspace_count}{" "}
            complete_proposal_claimed=
            {String(data.controlled_drafting.complete_proposal_claimed)}{" "}
            submission_ready_claimed=
            {String(data.controlled_drafting.submission_ready_claimed)}{" "}
            final_text_claimed=
            {String(data.controlled_drafting.final_text_claimed)}{" "}
            proposal_drafting_claimed=
            {String(data.controlled_drafting.proposal_drafting_claimed)}
          </p>
          <ul data-testid="sc-demo-controlled-draft-summary">
            {data.controlled_drafting.buyer_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          {data.controlled_drafting.workspaces.slice(0, 2).map((ws) => (
            <article
              key={ws.draft_workspace_id}
              className="nf-sc-demo-nofo-card"
              data-testid={`sc-demo-controlled-draft-card-${ws.draft_workspace_id}`}
            >
              <h3>
                {ws.opportunity_id} — from_evidence=
                {ws.generated_from_evidence_count} placeholder_or_blocked=
                {ws.placeholder_or_blocked_count}
              </h3>
              <ul>
                {ws.drafts.slice(0, 6).map((d) => (
                  <li key={d.section_id}>
                    {d.section_id}: mode={d.drafting_mode} status=
                    {d.generation_status} citations=
                    {(d.citation_requirements || []).length}
                    {d.generated_text ? " [DRAFT TEXT]" : " [NO CLAIM PROSE]"}
                  </li>
                ))}
              </ul>
              <p className="nf-muted">
                No submit control. No budget fabrication. Human review required.
              </p>
            </article>
          ))}
        </section>
      ) : null}

      {data.ai_governance ? (
        <section
          data-testid="sc-demo-ai-governance"
          className="nf-sc-demo-section"
        >
          <h2>AI governance / QA gates</h2>
          <p className="nf-sc-demo-why">
            Deterministic checks against org evidence, citations, recognition
            tier, and claim guards. QA does not replace human review.
          </p>
          <p data-testid="sc-demo-ai-gov-flags" className="nf-muted">
            workspaces={data.ai_governance.workspace_count} qa_passed=
            {String(data.ai_governance.qa_passed)} export_allowed=
            {String(data.ai_governance.export_allowed)} submission_allowed=
            {String(data.ai_governance.submission_allowed)}{" "}
            submission_ready_claimed=
            {String(data.ai_governance.submission_ready_claimed)}{" "}
            governance_complete_claimed=
            {String(data.ai_governance.governance_complete_claimed)}
          </p>
          <ul data-testid="sc-demo-ai-gov-summary">
            {data.ai_governance.buyer_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          {data.ai_governance.workspaces.slice(0, 2).map((ws) => (
            <article
              key={ws.draft_workspace_id}
              className="nf-sc-demo-nofo-card"
              data-testid={`sc-demo-ai-gov-card-${ws.draft_workspace_id}`}
            >
              <h3>
                {ws.opportunity_id} — qa={ws.overall_qa_status} blockers=
                {ws.blocker_count}
              </h3>
              <div>
                <h4>Hard blockers</h4>
                <ul>
                  {(ws.hard_blockers || []).slice(0, 5).map((b, idx) => (
                    <li key={`${String(b.section_id)}-${idx}`}>
                      [{String(b.check_scope)}] {String(b.issue_summary)}
                    </li>
                  ))}
                </ul>
              </div>
              <p className="nf-muted">
                export_allowed={String(ws.export_allowed)} submission_allowed=
                {String(ws.submission_allowed)} human_review_required=
                {String(ws.human_review_required)}
              </p>
            </article>
          ))}
        </section>
      ) : null}

      {data.feedback_loop ? (
        <section
          data-testid="sc-demo-feedback-loop"
          className="nf-sc-demo-section"
        >
          <h2>Customer feedback / reporting</h2>
          <p className="nf-sc-demo-why">
            Report hooks on major panels capture route, surface, claim flags, and
            blockers. Slack plumbing is dry-run safe. Collaboration remains dark
            and off.
          </p>
          <p data-testid="sc-demo-feedback-flags" className="nf-muted">
            report_hooks={data.feedback_loop.report_hook_count}{" "}
            slack_live_sent_claimed=
            {String(data.feedback_loop.slack_live_sent_claimed)}{" "}
            persistence_claimed=
            {String(data.feedback_loop.persistence_claimed)}{" "}
            collaboration_feature_enabled=
            {String(
              data.feedback_loop.collaboration.collaboration_feature_enabled,
            )}{" "}
            partner_matching_live_claimed=
            {String(
              data.feedback_loop.collaboration.partner_matching_live_claimed,
            )}
          </p>
          <ul data-testid="sc-demo-feedback-summary">
            {data.feedback_loop.buyer_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <div>
            <h3>Report hooks</h3>
            <ul data-testid="sc-demo-feedback-hooks">
              {data.feedback_loop.report_hooks.map((h) => (
                <li key={h.surface_id}>
                  {h.user_visible_label} ({h.surface_id}) — report available
                </li>
              ))}
            </ul>
          </div>
          <p className="nf-muted">
            Collaboration dark foundation: global=
            {String(data.feedback_loop.collaboration.collaboration_global_enabled)}{" "}
            cohort=
            {String(data.feedback_loop.collaboration.collaboration_cohort_enabled)}{" "}
            opt_in_required=
            {String(data.feedback_loop.collaboration.organization_opt_in_required)}
          </p>
        </section>
      ) : null}

      {data.package_export_preview ? (
        <section
          data-testid="sc-demo-package-export-preview"
          className="nf-sc-demo-section"
        >
          <h2>Package export preview</h2>
          <p className="nf-sc-demo-why">
            Structured preview of package materials, evidence map, missing items,
            and blockers. Preview-only — not final export and not
            submission-ready.
          </p>
          <p data-testid="sc-demo-export-preview-flags" className="nf-muted">
            workspaces={data.package_export_preview.workspace_count}{" "}
            export_allowed=
            {String(data.package_export_preview.export_allowed)}{" "}
            final_export_claimed=
            {String(data.package_export_preview.final_export_claimed)}{" "}
            submission_ready_claimed=
            {String(data.package_export_preview.submission_ready_claimed)}{" "}
            download_supported=
            {String(data.package_export_preview.download_supported)}
          </p>
          <ul data-testid="sc-demo-export-preview-summary">
            {data.package_export_preview.buyer_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          {data.package_export_preview.workspaces.slice(0, 2).map((ws) => (
            <article
              key={ws.package_export_preview_id}
              className="nf-sc-demo-nofo-card"
              data-testid={`sc-demo-export-preview-card-${ws.package_export_preview_id}`}
            >
              <h3>
                {ws.opportunity_id} — mode={ws.export_mode} status=
                {ws.export_status}
              </h3>
              <p className="nf-muted">
                included={ws.included_sections.length} excluded=
                {ws.excluded_sections.length} missing={ws.missing_items.length}{" "}
                blocked={ws.blocked_items.length} human_review_required=
                {String(ws.human_review_required)}
              </p>
              <div>
                <h4>Included sections (preview)</h4>
                <ul>
                  {ws.included_sections.slice(0, 8).map((s) => (
                    <li key={String(s.section_id)}>
                      {String(s.section_label)} — {String(s.status)}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h4>Missing / blocked</h4>
                <ul>
                  {ws.missing_items.slice(0, 5).map((m) => (
                    <li key={`m-${m}`}>{m}</li>
                  ))}
                  {ws.blocked_items.slice(0, 5).map((b) => (
                    <li key={`b-${b}`}>{b}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h4>Evidence map (sample)</h4>
                <ul>
                  {(ws.evidence_map || []).slice(0, 6).map((row, idx) => (
                    <li key={`${String(row.evidence_item)}-${idx}`}>
                      {String(row.evidence_item)} → exported=
                      {String(row.exported_in_preview)} ({String(row.reason)})
                    </li>
                  ))}
                </ul>
              </div>
            </article>
          ))}
        </section>
      ) : null}

      {data.forms_attachments_map ? (
        <section
          data-testid="sc-demo-forms-attachments-map"
          className="nf-sc-demo-section"
        >
          <h2>Forms &amp; attachments map</h2>
          <p className="nf-sc-demo-why">
            Requirement mapping from NOFO pilot, checklist, and org evidence
            memory. Forms are not completed; uploads and persistence are not
            supported.
          </p>
          <p data-testid="sc-demo-forms-map-flags" className="nf-muted">
            workspaces={data.forms_attachments_map.workspace_count}{" "}
            binary_upload_supported=
            {String(data.forms_attachments_map.binary_upload_supported)}{" "}
            attachment_persistence_claimed=
            {String(data.forms_attachments_map.attachment_persistence_claimed)}{" "}
            form_completion_claimed=
            {String(data.forms_attachments_map.form_completion_claimed)}{" "}
            submission_ready_claimed=
            {String(data.forms_attachments_map.submission_ready_claimed)}
          </p>
          <ul data-testid="sc-demo-forms-map-summary">
            {data.forms_attachments_map.buyer_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          {data.forms_attachments_map.workspaces.slice(0, 2).map((ws) => (
            <article
              key={ws.forms_attachment_map_id}
              className="nf-sc-demo-nofo-card"
              data-testid={`sc-demo-forms-map-card-${ws.forms_attachment_map_id}`}
            >
              <h3>
                {ws.opportunity_id} — mapping={ws.mapping_status}
              </h3>
              <div>
                <h4>Forms</h4>
                <ul>
                  {(ws.form_items || []).slice(0, 8).map((f) => (
                    <li key={String(f.item_id)}>
                      {String(f.label)} — {String(f.requirement_status)} (complete=
                      {String(f.completed)})
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h4>Attachments (missing stay visible)</h4>
                <ul>
                  {(ws.missing_attachments || []).slice(0, 8).map((a) => (
                    <li key={String(a.item_id)}>
                      {String(a.label)} — {String(a.requirement_status)} / evidence=
                      {String(a.current_evidence_status)}
                    </li>
                  ))}
                </ul>
              </div>
              <p className="nf-muted">
                human_review_required={String(ws.human_review_required)}{" "}
                upload_supported=false persistence=false
              </p>
            </article>
          ))}
        </section>
      ) : null}

      {data.multi_org_pilot ? (
        <section
          data-testid="sc-demo-multi-org-pilot"
          className="nf-sc-demo-section"
        >
          <h2>Multi-organization pilot / cohort readiness</h2>
          <p className="nf-sc-demo-why">
            Fixture-backed SC Native/tribal cohort with isolated per-org package
            state. Production multi-tenant isolation and live customer login are
            not claimed.
          </p>
          <p data-testid="sc-demo-multi-org-flags" className="nf-muted">
            orgs={data.multi_org_pilot.cohort.organization_count} data_mode=
            {data.multi_org_pilot.cohort.cohort_data_mode}{" "}
            collaboration_enabled=
            {String(data.multi_org_pilot.collaboration_enabled)}{" "}
            production_multi_tenant_claimed=
            {String(data.multi_org_pilot.production_multi_tenant_claimed)}{" "}
            live_customer_login_claimed=
            {String(data.multi_org_pilot.live_customer_login_claimed)}
          </p>
          <ul data-testid="sc-demo-multi-org-summary">
            {data.multi_org_pilot.buyer_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p className="nf-muted">
            Selected org: {data.multi_org_pilot.selected_organization_profile_id}{" "}
            | cohort next:{" "}
            {data.multi_org_pilot.operator_rollup.cohort_next_safest_action}
          </p>
          {data.multi_org_pilot.organizations.slice(0, 4).map((org) => (
            <article
              key={org.organization_profile_id}
              className="nf-sc-demo-nofo-card"
              data-testid={`sc-demo-multi-org-card-${org.organization_profile_id}`}
            >
              <h3>
                {org.organization_name || org.organization_profile_id} — readiness=
                {org.overall_readiness_status}
              </h3>
              <p className="nf-muted">
                recognition={String(org.recognition_status)} opportunities=
                {org.opportunity_count} qa_blockers={org.qa_blocker_count}{" "}
                export_allowed={String(org.export_allowed)}{" "}
                submission_ready_claimed=
                {String(org.submission_ready_claimed)}
              </p>
              <div>
                <h4>Blockers</h4>
                <ul>
                  {(org.blockers || []).slice(0, 4).map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              </div>
              <p className="nf-muted">
                feedback_context={org.feedback_context_id} next=
                {org.next_safest_action}
              </p>
            </article>
          ))}
        </section>
      ) : null}

      {data.collaboration_dark_launch ? (
        <section
          data-testid="sc-demo-collaboration-dark-launch"
          className="nf-sc-demo-section"
        >
          <h2>Future collaboration / dark launch</h2>
          <p className="nf-sc-demo-why">
            Architecture for future opt-in partnership discovery. Feature remains
            OFF — no matching, recommendations, introductions, or data sharing.
          </p>
          <p data-testid="sc-demo-collab-dark-flags" className="nf-muted">
            feature_enabled=
            {String(data.collaboration_dark_launch.collaboration_feature_enabled)}{" "}
            global_enabled=
            {String(data.collaboration_dark_launch.collaboration_global_enabled)}{" "}
            cohort_enabled=
            {String(data.collaboration_dark_launch.collaboration_cohort_enabled)}{" "}
            opt_in_required=
            {String(data.collaboration_dark_launch.organization_opt_in_required)}{" "}
            data_sharing_allowed=
            {String(data.collaboration_dark_launch.data_sharing_allowed)}{" "}
            partner_matching_live_claimed=
            {String(
              data.collaboration_dark_launch.partner_matching_live_claimed,
            )}{" "}
            partner_recommendations_claimed=
            {String(
              data.collaboration_dark_launch.partner_recommendations_claimed,
            )}
          </p>
          <ul data-testid="sc-demo-collab-dark-summary">
            {data.collaboration_dark_launch.buyer_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p className="nf-muted">
            rollout_stage=
            {data.collaboration_dark_launch.rollout_controls.rollout_stage}{" "}
            exposure=
            {
              data.collaboration_dark_launch.rollout_controls
                .feature_exposure_status
            }{" "}
            fit_dims=
            {data.collaboration_dark_launch.fit_model.dimensions.length}{" "}
            fit_score_claimed=
            {String(data.collaboration_dark_launch.fit_score_claimed)}
          </p>
          <p className="nf-muted">
            {data.collaboration_dark_launch.fit_model.not_live_reason}
          </p>
        </section>
      ) : null}

      {data.evidence_intake ? (
        <section
          data-testid="sc-demo-evidence-intake"
          className="nf-sc-demo-section"
        >
          <h2>Evidence intake / uploads</h2>
          <p className="nf-sc-demo-why">
            Evidence needed is linked to checklist, binder, forms map, and package
            preview. Storage is fixture/planned — durable binary upload is not
            claimed. No upload UI unless validated storage exists.
          </p>
          <p data-testid="sc-demo-evidence-intake-flags" className="nf-muted">
            workspaces={data.evidence_intake.workspace_count} adapter=
            {data.evidence_intake.storage_adapter} upload_ui_supported=
            {String(data.evidence_intake.upload_ui_supported)}{" "}
            upload_persistence_claimed=
            {String(data.evidence_intake.upload_persistence_claimed)}{" "}
            customer_data_persistence_claimed=
            {String(data.evidence_intake.customer_data_persistence_claimed)}{" "}
            production_storage_claimed=
            {String(data.evidence_intake.production_storage_claimed)}{" "}
            package_unlock_claimed=
            {String(data.evidence_intake.package_unlock_claimed)}{" "}
            migration_required=
            {String(data.evidence_intake.migration_required)}
          </p>
          <ul data-testid="sc-demo-evidence-intake-summary">
            {data.evidence_intake.buyer_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p className="nf-muted">
            Storage proposal: {data.evidence_intake.storage_proposal_path}
          </p>
          {data.evidence_intake.workspaces.slice(0, 2).map((ws) => (
            <article
              key={ws.organization_profile_id}
              className="nf-sc-demo-nofo-card"
              data-testid={`sc-demo-evidence-intake-card-${ws.organization_profile_id}`}
            >
              <h3>
                {ws.organization_profile_id} — records={ws.record_count}
              </h3>
              <ul>
                {(ws.records || []).slice(0, 5).map((r) => (
                  <li key={String(r.evidence_intake_id)}>
                    {String(r.evidence_label)} — mode={String(r.storage_mode)}{" "}
                    review={String(r.review_status)} persist=
                    {String(r.upload_persistence_claimed)}
                  </li>
                ))}
              </ul>
              <p className="nf-muted">
                unlock=
                {String(
                  (ws.unlock_evaluation || {}).package_unlock_claimed ?? false,
                )}{" "}
                human_review_required={String(ws.human_review_required)}
              </p>
            </article>
          ))}
        </section>
      ) : null}

      {data.operator_readiness ? (
        <section
          data-testid="sc-demo-operator-readiness"
          className="nf-sc-demo-section"
        >
          <h2>Operator enablement / production readiness</h2>
          <p className="nf-sc-demo-why">
            Go/no-go checklist for demo, pilot, upload, collaboration, and
            production. Production-ready and pen-test passed remain false.
          </p>
          <p data-testid="sc-demo-operator-ready-flags" className="nf-muted">
            head={data.operator_readiness.contract.current_head} monday=
            {String(data.operator_readiness.monday_demo_status)} production=
            {String(data.operator_readiness.production_rollout_status)} upload=
            {String(data.operator_readiness.upload_rollout_status)} collab=
            {String(data.operator_readiness.collaboration_rollout_status)}{" "}
            production_ready_claimed=
            {String(data.operator_readiness.production_ready_claimed)}{" "}
            pen_test_passed_claimed=
            {String(data.operator_readiness.pen_test_passed_claimed)}{" "}
            upload_persistence_claimed=
            {String(data.operator_readiness.upload_persistence_claimed)}
          </p>
          <ul data-testid="sc-demo-operator-ready-summary">
            {data.operator_readiness.buyer_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <div>
            <h3>Go / no-go</h3>
            <ul data-testid="sc-demo-operator-go-nogo">
              {data.operator_readiness.go_no_go_matrix.map((row) => (
                <li key={String(row.target)}>
                  {String(row.target)}: {String(row.status)}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3>Blockers</h3>
            <ul>
              {data.operator_readiness.blockers.slice(0, 6).map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          </div>
          <p className="nf-muted">
            Commands: {(data.operator_readiness.required_commands || []).join(" | ")}
          </p>
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

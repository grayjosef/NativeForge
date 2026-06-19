import { str } from "../../stage12GuidedFlowTypes";

interface SourceQualityReviewStepProps {
  payload: Record<string, unknown>;
}

export function SourceQualityReviewStep({ payload }: SourceQualityReviewStepProps) {
  const summary = (payload.quality_summary as Record<string, unknown>) ?? {};
  return (
    <section
      className="nf-card nf-card-pad nf-stage12-step"
      data-step="source-quality-review"
    >
      <h2 className="nf-card-title">Source quality review</h2>
      <p className="nf-card-one-liner">
        Review source quality posture before any activation consideration.
      </p>
      <table className="nf-wb-table">
        <thead>
          <tr>
            <th>Source</th>
            <th>Quality posture</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(summary).map(([key, val]) => (
            <tr key={key}>
              <td>{key}</td>
              <td>{str(val)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

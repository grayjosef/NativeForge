export interface WhatsNextCardProps {
  headline: string;
  detail: string;
  busy?: boolean;
  primaryLabel: string | null;
  onPrimary?: () => void;
  primaryDisabled?: boolean;
}

export function WhatsNextCard({
  headline,
  detail,
  busy,
  primaryLabel,
  onPrimary,
  primaryDisabled,
}: WhatsNextCardProps) {
  const showPrimary =
    primaryLabel && onPrimary && !busy && primaryLabel.length > 0;

  return (
    <section className="nf-rail-card nf-rail-card--command" aria-labelledby="nf-next-heading">
      <h2 id="nf-next-heading" className="nf-rail-card-title">
        What&apos;s next
      </h2>
      <p className="nf-next-headline">{busy ? "Working…" : headline}</p>
      <p className="nf-rail-card-lead">{detail}</p>
      {showPrimary ? (
        <div className="nf-rail-card-actions">
          <button
            type="button"
            className="nf-btn nf-btn-primary nf-btn-block-sm"
            disabled={primaryDisabled}
            onClick={() => onPrimary?.()}
          >
            {primaryLabel}
          </button>
        </div>
      ) : null}
    </section>
  );
}

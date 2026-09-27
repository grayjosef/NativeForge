export interface WhatsNextCardProps {
  headline: string;
  detail: string;
  busy?: boolean;
  primaryLabel: string | null;
  onPrimary?: () => void;
  primaryDisabled?: boolean;
}

/**
 * "What's next": orientation, not a second set of controls.
 *
 * This used to render the current step's primary action as its own button.
 * Because the card sits on the same screen as the step it describes, the
 * workspace showed two identical "Create tribal profile" buttons a few
 * hundred pixels apart, and a third entry point in the progress strip above.
 * Three doors to one room is not convenience; it is a customer wondering
 * whether the buttons do different things.
 *
 * So the action is named rather than repeated. The card answers "where am I
 * and what happens next", and the step's own card owns the doing. The props
 * are kept so the caller does not have to change, and `primaryLabel` is used
 * as the name of the next step rather than as a control.
 */
export function WhatsNextCard({
  headline,
  detail,
  busy,
  primaryLabel,
}: WhatsNextCardProps) {
  const next = primaryLabel?.trim();

  return (
    <section className="nf-rail-card nf-rail-card--command" aria-labelledby="nf-next-heading">
      <h2 id="nf-next-heading" className="nf-rail-card-title">
        What&apos;s next
      </h2>
      <p className="nf-next-headline">{busy ? "Working…" : headline}</p>
      <p className="nf-rail-card-lead">{detail}</p>
      {next && !busy ? (
        <p className="nf-next-step">
          <span className="nf-next-step-label">Next step</span>
          <span className="nf-next-step-name">{next}</span>
        </p>
      ) : null}
    </section>
  );
}

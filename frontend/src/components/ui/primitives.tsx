import type { ReactNode } from "react";

/**
 * The shared presentation layer.
 *
 * Every surface in NativeForge was building its own page title, its own
 * section heading, its own bordered box and its own little status pill out of
 * raw divs and one-off class names. Nine files, nine slightly different
 * answers to "how big is a section heading", and no way to change the answer
 * once.
 *
 * These are deliberately thin. They own spacing, hierarchy and the accessible
 * shape; they do not own content decisions, and none of them fetches
 * anything. A component that both lays out a panel and knows what goes in it
 * is a component that gets copied the next time the content differs.
 */

export function PageHeader(props: {
  /** Small line above the title: where you are. */
  eyebrow?: string;
  title: string;
  /** One sentence. What this page answers. */
  lead?: string;
  actions?: ReactNode;
}) {
  const { eyebrow, title, lead, actions } = props;
  return (
    <header className="nf-pagehead">
      <div className="nf-pagehead-text">
        {eyebrow ? <p className="nf-pagehead-eyebrow">{eyebrow}</p> : null}
        {/* h2, not h1. The shell's brand is the document's h1 and there is
            exactly one per page; a second would leave a screen reader with
            two competing top-level headings. */}
        <h2 className="nf-pagehead-title">{title}</h2>
        {lead ? <p className="nf-pagehead-lead">{lead}</p> : null}
      </div>
      {actions ? <div className="nf-pagehead-actions">{actions}</div> : null}
    </header>
  );
}

let sectionSeq = 0;

export function Section(props: {
  title: string;
  /** Short explanation under the heading. */
  lead?: string;
  /** Right-aligned controls or a count. */
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const { title, lead, aside, children, className = "" } = props;
  // Generated rather than derived from the title: two sections legitimately
  // share a title across pages, and duplicate ids break the labelling.
  const id = `nf-sec-${(sectionSeq += 1)}`;
  return (
    <section className={`nf-section ${className}`.trim()} aria-labelledby={id}>
      <div className="nf-section-head">
        <div>
          <h3 id={id} className="nf-section-title">
            {title}
          </h3>
          {lead ? <p className="nf-section-lead">{lead}</p> : null}
        </div>
        {aside ? <div className="nf-section-aside">{aside}</div> : null}
      </div>
      {children}
    </section>
  );
}

export type BadgeTone = "neutral" | "positive" | "warn" | "bad" | "muted" | "info";

export function StatusBadge({
  tone = "neutral",
  children,
}: {
  tone?: BadgeTone;
  children: ReactNode;
}) {
  return (
    <span className="nf-badge" data-tone={tone}>
      {children}
    </span>
  );
}

/**
 * A single measured number.
 *
 * `value` is a string so the caller decides how an unknown is written. An
 * unmeasured metric renders as "—" and says why in `note`; rendering it as 0
 * would state a measurement nobody took, which is the one thing a grant
 * intelligence product cannot do.
 */
export function MetricCard(props: {
  label: string;
  value: string;
  note?: string;
  tone?: BadgeTone;
  onClick?: () => void;
}) {
  const { label, value, note, tone = "neutral", onClick } = props;
  const body = (
    <>
      <span className="nf-metric-label">{label}</span>
      <span className="nf-metric-value" data-tone={tone}>
        {value}
      </span>
      {note ? <span className="nf-metric-note">{note}</span> : null}
    </>
  );
  if (!onClick) {
    return <div className="nf-metric">{body}</div>;
  }
  return (
    <button type="button" className="nf-metric is-clickable" onClick={onClick}>
      {body}
    </button>
  );
}

/** A row of metrics that wraps rather than scrolls. */
export function MetricRow({ children }: { children: ReactNode }) {
  return <div className="nf-metric-row">{children}</div>;
}

export function Panel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`nf-panel ${className}`.trim()}>{children}</div>;
}

/**
 * One thing that needs doing, with exactly one way to do it.
 *
 * The workspace previously offered the same action from three places at once
 * - the card that owns it, the "what's next" panel and the progress strip -
 * so the honest constraint is built into the shape: an ActionCard takes a
 * single action and has nowhere to put a second.
 */
export function ActionCard(props: {
  title: string;
  body: string;
  actionLabel?: string;
  onAction?: () => void;
  tone?: BadgeTone;
  badge?: string;
  disabled?: boolean;
}) {
  const { title, body, actionLabel, onAction, tone = "neutral", badge, disabled } = props;
  return (
    <div className="nf-action-card" data-tone={tone}>
      <div className="nf-action-card-head">
        <p className="nf-action-card-title">{title}</p>
        {badge ? <StatusBadge tone={tone}>{badge}</StatusBadge> : null}
      </div>
      <p className="nf-action-card-body">{body}</p>
      {actionLabel && onAction ? (
        <button
          type="button"
          className="nf-btn nf-btn-primary nf-btn-sm"
          onClick={onAction}
          disabled={disabled}
        >
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}

/** A responsive grid that does not need a column count at every call site. */
export function CardGrid({
  children,
  min = 260,
}: {
  children: ReactNode;
  min?: number;
}) {
  return (
    <div
      className="nf-card-grid"
      style={{ ["--nf-grid-min" as string]: `${min}px` }}
    >
      {children}
    </div>
  );
}

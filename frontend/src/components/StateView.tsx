import type { ReactNode } from "react";

import { diagnosticsVisible, type CustomerState, type StateTone } from "../customerState";

/**
 * The one way NativeForge tells a customer that something is loading, empty,
 * refused, incomplete or broken.
 *
 * Every surface used to improvise: a red box here, a bare sentence there, a
 * raw payload somewhere else. Improvised states are how internal vocabulary
 * escapes, so there is now a single component and it takes a `CustomerState`
 * rather than a string.
 *
 * ## Why blocked does not look like an error
 *
 * A tenant boundary refusing an unverified organization is the product
 * working correctly. Rendering that in the same red as a crash teaches
 * customers that NativeForge is broken whenever it is being careful. Blocked
 * is treated as a requirement to satisfy, with the requirement stated and
 * the way forward offered.
 *
 * ## Why status never rests on colour alone
 *
 * Each tone carries a label as well as a hue, so the state survives
 * greyscale, low vision and colour blindness.
 */

const TONE_LABEL: Record<StateTone, string> = {
  loading: "Working",
  empty: "Nothing here yet",
  blocked: "Action needed",
  partial: "Incomplete",
  error: "Problem",
  success: "Done",
};

export interface StateViewProps {
  state: CustomerState;
  /** Invoked by the primary action, when the state offers one. */
  onAction?: () => void;
  /** Overrides the action label from the state. */
  actionLabel?: string;
  secondary?: ReactNode;
  /** Compact form, for inside a card rather than a whole panel. */
  inline?: boolean;
  className?: string;
}

export function StateView({
  state,
  onAction,
  actionLabel,
  secondary,
  inline = false,
  className = "",
}: StateViewProps) {
  const label = actionLabel ?? state.actionLabel;
  const showAction = Boolean(label && onAction);

  return (
    <div
      className={`nf-state nf-state-${state.tone} ${inline ? "is-inline" : ""} ${className}`.trim()}
      role={state.tone === "error" ? "alert" : "status"}
      data-tone={state.tone}
    >
      <p className="nf-state-eyebrow">
        <span className="nf-state-dot" aria-hidden="true" />
        {TONE_LABEL[state.tone]}
      </p>
      <p className="nf-state-title">{state.title}</p>
      <p className="nf-state-body">{state.body}</p>

      {showAction || secondary ? (
        <div className="nf-state-actions">
          {showAction ? (
            <button type="button" className="nf-btn nf-btn-primary" onClick={onAction}>
              {label}
            </button>
          ) : null}
          {secondary}
        </div>
      ) : null}

      {/* Diagnostics are a development and operator concern. The original
          text is kept on the state so it is never lost, and shown only
          where it is appropriate: a customer gets the designed copy. */}
      {state.technical && diagnosticsVisible() ? (
        <details className="nf-state-technical">
          <summary>Technical detail (development only)</summary>
          <code>{state.technical}</code>
        </details>
      ) : null}
    </div>
  );
}

/** A quiet, accessible busy state. */
export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="nf-state nf-state-loading is-inline" role="status" aria-live="polite">
      <span className="nf-spinner" aria-hidden="true" />
      <span className="nf-state-body">{label}</span>
    </div>
  );
}

/** An empty state that says what would fill it, and how. */
export function EmptyState(props: {
  title: string;
  body: string;
  actionLabel?: string;
  onAction?: () => void;
  inline?: boolean;
}) {
  const { title, body, actionLabel, onAction, inline } = props;
  return (
    <StateView
      state={{ tone: "empty", title, body, actionLabel }}
      onAction={onAction}
      inline={inline}
    />
  );
}

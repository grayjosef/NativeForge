import type { CustomerState } from "../customerState";
import { StateView } from "./StateView";

export interface OrgReadinessCardProps {
  busy: boolean;
  profileFields: {
    legalName?: string;
    entityType?: string;
    city?: string;
    state?: string;
    grantsContact?: string;
  } | null;
  /** The blocking or failing state, already interpreted for a customer. */
  error: CustomerState | null;
  statusChip: string;
  onCreateRefresh: () => void;
}

/**
 * The organization profile card.
 *
 * ## One card, one action
 *
 * This used to render up to three calls to action at once when the profile
 * could not be read: a "Create tribal profile" button, a red box containing
 * whatever the backend said, and a "Fix profile error" chip in the progress
 * strip above. Three doors to the same room, one of them a raw payload.
 *
 * A blocking state now replaces the card's body rather than stacking beneath
 * it, and carries the single action itself. When the profile loads normally
 * the button returns. The customer is never offered the same next step twice.
 */
export function OrgReadinessCard({
  busy,
  profileFields,
  error,
  statusChip,
  onCreateRefresh,
}: OrgReadinessCardProps) {
  const hasDetails = !!profileFields;
  // A refusal or fault owns the card. Anything else would be a second door.
  const blocking = error && (error.tone === "blocked" || error.tone === "error");

  return (
    <section className="nf-card nf-card-pad" aria-labelledby="nf-org-heading">
      <div className="nf-card-head-row">
        <h2 id="nf-org-heading" className="nf-card-title">
          Tribal profile
        </h2>
        <span className="nf-chip nf-chip--rail">{statusChip}</span>
      </div>

      {blocking ? (
        <StateView
          state={error}
          onAction={() => void onCreateRefresh()}
          actionLabel={busy ? "Saving…" : (error.actionLabel ?? "Create tribal profile")}
          inline
        />
      ) : (
        <>
          <p className="nf-card-one-liner">
            Create the profile used for previews, review artifacts, and exports.
          </p>
          {hasDetails ? (
            <dl className="nf-dl nf-dl-tight">
              <div>
                <dt>Legal name</dt>
                <dd>{profileFields!.legalName ?? "—"}</dd>
              </div>
              <div>
                <dt>Entity type</dt>
                <dd>{profileFields!.entityType ?? "—"}</dd>
              </div>
              <div>
                <dt>Location</dt>
                <dd>
                  {[profileFields!.city, profileFields!.state].filter(Boolean).join(", ") ||
                    "—"}
                </dd>
              </div>
              <div>
                <dt>Grants contact</dt>
                <dd>{profileFields!.grantsContact ?? "—"}</dd>
              </div>
            </dl>
          ) : (
            <div className="nf-empty nf-empty--calm">
              <p className="nf-empty-title">Start here on first visit.</p>
              <p className="nf-empty-hint">
                Nothing is wrong. We just need your tribal profile on file.
              </p>
            </div>
          )}
          <div className="nf-card-actions">
            <button
              type="button"
              className="nf-btn nf-btn-primary nf-btn-block-sm"
              disabled={busy}
              onClick={() => void onCreateRefresh()}
            >
              {busy ? "Saving…" : "Create tribal profile"}
            </button>
          </div>
        </>
      )}
    </section>
  );
}

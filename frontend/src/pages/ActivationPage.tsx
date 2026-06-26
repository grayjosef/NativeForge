import { useCallback, useEffect, useState } from "react";
import type { Plane } from "../m0Flow";
import {
  getActivationState,
  postGovernedActivationAction,
  type ActivationState,
  type ActorRole,
} from "../activationApiClient";
import { friendlyError } from "../friendlyError";

const LS_ROLE = "nf-actor-role";

export interface ActivationPageProps {
  plane: Plane;
  orgId: string;
  orgOk: boolean;
  actorId: string;
}

function readActorRole(): ActorRole {
  try {
    const r = localStorage.getItem(LS_ROLE);
    if (r === "admin" || r === "agent" || r === "operator") return r;
  } catch {
    /* ignore */
  }
  return "operator";
}

function FlagRow({
  label,
  enabled,
  onToggle,
  disabled,
  highRisk,
}: {
  label: string;
  enabled: boolean;
  onToggle: (next: boolean) => void;
  disabled: boolean;
  highRisk?: boolean;
}) {
  return (
    <div className="nf-activation-flag-row">
      <div>
        <strong>{label}</strong>
        {highRisk ? (
          <p className="nf-muted nf-activation-flag-hint">
            High-risk enable requires confirm + reason (audited).
          </p>
        ) : null}
      </div>
      <button
        type="button"
        className={`nf-btn nf-activation-toggle ${enabled ? "is-on" : ""}`}
        disabled={disabled}
        onClick={() => onToggle(!enabled)}
        aria-pressed={enabled}
      >
        {enabled ? "ON" : "OFF"}
      </button>
    </div>
  );
}

export function ActivationPage({ plane, orgId, orgOk, actorId }: ActivationPageProps) {
  const [state, setState] = useState<ActivationState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [role, setRole] = useState<ActorRole>(() => readActorRole());
  const [pending, setPending] = useState<{
    toggle: string;
    value: boolean;
    governed_action: string;
    title: string;
  } | null>(null);
  const [reason, setReason] = useState("");

  const canMutate = orgOk && role !== "agent";

  const refresh = useCallback(async () => {
    if (!orgOk) return;
    setLoading(true);
    setError(null);
    try {
      const s = await getActivationState(plane, orgId);
      setState(s);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setLoading(false);
    }
  }, [orgOk, plane, orgId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onRoleChange = (r: ActorRole) => {
    setRole(r);
    localStorage.setItem(LS_ROLE, r);
  };

  const dispatch = async (body: Record<string, unknown>) => {
    setError(null);
    try {
      const res = await postGovernedActivationAction(
        plane,
        orgId,
        actorId,
        role,
        body,
      );
      setState(res.activation_state);
      setPending(null);
      setReason("");
    } catch (e) {
      setError(friendlyError(e));
    }
  };

  const engageKillSwitch = () => {
    void dispatch({
      governed_action: "activation:toggle",
      toggle: "kill_switch",
      value: true,
    });
  };

  const releaseKillSwitch = () => {
    void dispatch({
      governed_action: "activation:toggle",
      toggle: "kill_switch",
      value: false,
    });
  };

  const requestToggle = (
    toggle: string,
    value: boolean,
    governed_action: string,
    title: string,
    highRisk: boolean,
  ) => {
    if (!canMutate) return;
    if (highRisk && value) {
      setPending({ toggle, value, governed_action, title });
      return;
    }
    void dispatch({ governed_action, toggle, value });
  };

  const confirmPending = () => {
    if (!pending || !reason.trim()) return;
    void dispatch({
      governed_action: pending.governed_action,
      toggle: pending.toggle,
      value: pending.value,
      reason: reason.trim(),
    });
  };

  if (!orgOk) {
    return (
      <main className="nf-activation-page">
        <p className="nf-muted">Set a valid org UUID to view activation state.</p>
      </main>
    );
  }

  return (
    <main className="nf-activation-page">
      <header className="nf-activation-header">
        <div>
          <h2 className="nf-activation-title">Activation</h2>
          <p className="nf-muted">
            Per-workspace live publish, attribution, auto-publish, and kill-switch
            — default OFF, governed, audited.
          </p>
        </div>
        <div className="nf-activation-role">
          <label htmlFor="nf-actor-role">Actor role</label>
          <select
            id="nf-actor-role"
            value={role}
            onChange={(e) => onRoleChange(e.target.value as ActorRole)}
          >
            <option value="operator">operator</option>
            <option value="admin">admin</option>
            <option value="agent">agent (read-only)</option>
          </select>
        </div>
      </header>

      {error ? <p className="nf-error-banner">{error}</p> : null}
      {loading && !state ? <p className="nf-muted">Loading activation state…</p> : null}

      {state ? (
        <>
          <section
            className={`nf-kill-switch-panel ${state.kill_switch_engaged ? "is-engaged" : ""}`}
            aria-label="Kill switch"
          >
            <div>
              <h3>Kill switch</h3>
              <p className="nf-muted">
                Emergency stop — halts live publish and auto-publish queueing. One
                click to engage; no confirmation dialog.
              </p>
              <p>
                Status:{" "}
                <strong>
                  {state.kill_switch_engaged ? "ENGAGED" : "Released"}
                </strong>
              </p>
            </div>
            <div className="nf-kill-switch-actions">
              <button
                type="button"
                className="nf-btn nf-kill-engage"
                disabled={!canMutate || state.kill_switch_engaged}
                onClick={engageKillSwitch}
              >
                Engage kill switch
              </button>
              <button
                type="button"
                className="nf-btn"
                disabled={!canMutate || !state.kill_switch_engaged}
                onClick={releaseKillSwitch}
              >
                Release
              </button>
            </div>
          </section>

          <section className="nf-card nf-activation-flags">
            <h3>Flags</h3>
            <p className="nf-muted nf-activation-meta">
              State v{state.state_version}
              {state.current_auto_publish_config_version != null
                ? ` · auto-publish config v${state.current_auto_publish_config_version}`
                : ""}
              {state.updated_at ? ` · updated ${state.updated_at}` : ""}
            </p>
            <FlagRow
              label="Live publish"
              enabled={state.live_publish_enabled}
              highRisk
              disabled={!canMutate || state.kill_switch_engaged}
              onToggle={(v) =>
                requestToggle(
                  "live_publish",
                  v,
                  "activation:toggle",
                  "Enable live publish",
                  true,
                )
              }
            />
            <FlagRow
              label="Live attribution"
              enabled={state.live_attribution_enabled}
              disabled={!canMutate || state.kill_switch_engaged}
              onToggle={(v) =>
                requestToggle(
                  "live_attribution",
                  v,
                  "activation:toggle",
                  "Live attribution",
                  false,
                )
              }
            />
            <FlagRow
              label="Auto-publish"
              enabled={state.auto_publish_enabled}
              highRisk
              disabled={!canMutate || state.kill_switch_engaged}
              onToggle={(v) =>
                requestToggle(
                  "auto_publish",
                  v,
                  v ? "policy:change" : "activation:toggle",
                  v ? "Enable auto-publish" : "Disable auto-publish",
                  v,
                )
              }
            />
          </section>

          <section className="nf-card nf-activation-audit">
            <h3>Recent audit</h3>
            {(state.recent_audit ?? []).length === 0 ? (
              <p className="nf-muted">No activation audit events yet.</p>
            ) : (
              <ul className="nf-activation-audit-list">
                {(state.recent_audit ?? []).map((ev, i) => (
                  <li key={`${ev.action}-${ev.created_at ?? i}`}>
                    <code>{ev.action}</code>
                    {ev.created_at ? ` · ${ev.created_at}` : ""}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      ) : null}

      {pending ? (
        <div className="nf-modal-backdrop" role="dialog" aria-modal="true">
          <div className="nf-card nf-activation-modal">
            <h3>{pending.title}</h3>
            <p className="nf-muted">
              Provide a reason — recorded in audit (override-reason pattern).
            </p>
            <textarea
              className="nf-textarea"
              rows={4}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Operator reason for this high-risk enable…"
            />
            <div className="nf-activation-modal-actions">
              <button
                type="button"
                className="nf-btn nf-btn-primary"
                disabled={!reason.trim()}
                onClick={confirmPending}
              >
                Confirm enable
              </button>
              <button
                type="button"
                className="nf-btn"
                onClick={() => {
                  setPending(null);
                  setReason("");
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}

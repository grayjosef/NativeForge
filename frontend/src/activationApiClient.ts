/**
 * M8: operator activation console API (durable workspace flags).
 */

import { buildM0Path, type Plane } from "./m0Flow";
import { apiFetchBase, readHttpError } from "./m0ApiClient";

export type ActorRole = "operator" | "admin" | "agent";

export type ActivationState = {
  schema_version?: string;
  live_publish_enabled: boolean;
  live_attribution_enabled: boolean;
  auto_publish_enabled: boolean;
  kill_switch_engaged: boolean;
  current_auto_publish_config_version: number | null;
  state_version: number;
  updated_at: string | null;
  updated_by_actor_role: string | null;
  defaults_off?: boolean;
  publish_gate?: {
    publish_permitted: boolean;
    auto_publish_queue_permitted: boolean;
    live_attribution_permitted: boolean;
    kill_switch_engaged: boolean;
    halt_reason: string | null;
  };
  recent_audit?: Array<{
    action: string;
    created_at: string | null;
    payload?: Record<string, unknown>;
    actor_id?: string | null;
  }>;
};

function headers(orgId: string, role: ActorRole): Record<string, string> {
  return {
    "X-NF-Org-Id": orgId.trim(),
    "X-NF-Actor-Role": role,
    "Content-Type": "application/json",
  };
}

export async function getActivationState(
  plane: Plane,
  orgId: string,
): Promise<ActivationState> {
  const base = apiFetchBase();
  const path = buildM0Path(plane, orgId, "/operator/activation");
  const res = await fetch(`${base}${path}`, {
    headers: { "X-NF-Org-Id": orgId.trim() },
  });
  if (!res.ok) throw new Error(await readHttpError(res));
  return (await res.json()) as ActivationState;
}

export async function postGovernedActivationAction(
  plane: Plane,
  orgId: string,
  actorId: string,
  role: ActorRole,
  body: Record<string, unknown>,
): Promise<{ activation_state: ActivationState }> {
  const base = apiFetchBase();
  const path = buildM0Path(plane, orgId, "/operator/activation/governed-action");
  const q = actorId ? `?actor_id=${encodeURIComponent(actorId)}` : "";
  const res = await fetch(`${base}${path}${q}`, {
    method: "POST",
    headers: headers(orgId, role),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await readHttpError(res));
  return (await res.json()) as { activation_state: ActivationState };
}

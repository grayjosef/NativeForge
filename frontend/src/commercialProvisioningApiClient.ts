export type ProvisioningStatus = {
  schema_version: string;
  has_request?: boolean;
  request_id?: string;
  lifecycle_status?: string | null;
  customer_status_label?: string;
  requested_org_display_name?: string | null;
  organization_id?: string | null;
  workspace_lane?: string;
  next_step_summary?: string;
  blocked_reasons?: string[];
};

export async function fetchProvisioningStatus(baseUrl: string): Promise<ProvisioningStatus> {
  const res = await fetch(`${baseUrl}/api/commercial-provisioning/status`, {
    credentials: "include",
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return (await res.json()) as ProvisioningStatus;
}

export async function submitCommercialIntent(
  baseUrl: string,
  requestedOrgDisplayName: string,
): Promise<ProvisioningStatus> {
  const res = await fetch(`${baseUrl}/api/commercial-provisioning/intent`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ requested_org_display_name: requestedOrgDisplayName }),
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return (await res.json()) as ProvisioningStatus;
}

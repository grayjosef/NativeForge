import { useEffect, useState } from "react";
import {
  fetchProvisioningStatus,
  submitCommercialIntent,
  type ProvisioningStatus,
} from "../commercialProvisioningApiClient";
import type { CustomerState } from "../customerState";
import { interpretError } from "../friendlyError";

type Props = {
  baseUrl: string;
  onBackToDemo: () => void;
};

export function CommercialActivationPage({ baseUrl, onBackToDemo }: Props) {
  const [status, setStatus] = useState<ProvisioningStatus | null>(null);
  const [orgName, setOrgName] = useState("");
  const [error, setError] = useState<CustomerState | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const data = await fetchProvisioningStatus(baseUrl);
        if (!cancelled) setStatus(data);
      } catch (e) {
        if (!cancelled) setError(interpretError(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [baseUrl]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const data = await submitCommercialIntent(baseUrl, orgName.trim());
      setStatus(data);
    } catch (err) {
      setError(interpretError(err));
    } finally {
      setBusy(false);
    }
  }

  if (error && !status) {
    return (
      <section className="nf-panel">
        <h2>{error.title}</h2>
        <p>{error.body}</p>
      </section>
    );
  }

  const label = status?.customer_status_label ?? "Loading…";

  return (
    <div className="nf-commercial-activation" data-testid="commercial-activation">
      <header className="nf-panel">
        <h1>Activate your organization</h1>
        <p className="nf-lead">
          Request NativeForge Pro for your nation or Native-serving organization. This step records
          commercial intent only — not payment and not Tribal authority verification.
        </p>
        <p className="nf-env nf-demo-workspace-badge">Status: {label}</p>
        {status?.next_step_summary ? <p>{status.next_step_summary}</p> : null}
      </header>

      {status?.has_request ? (
        <section className="nf-panel">
          <h2>What happens next</h2>
          <ul className="nf-list">
            <li>NativeForge confirms commercial entitlement with your organization.</li>
            <li>Your organization workspace is provisioned and you complete your profile.</li>
            <li>Authority and affiliation review remain separate from purchase.</li>
          </ul>
          <button type="button" className="nf-btn nf-btn-ghost" onClick={onBackToDemo}>
            Return to demo workspace
          </button>
        </section>
      ) : (
        <form className="nf-panel" onSubmit={(e) => void onSubmit(e)}>
          <h2>Organization details</h2>
          <label htmlFor="org-display-name">Organization name</label>
          <input
            id="org-display-name"
            className="nf-input"
            value={orgName}
            onChange={(ev) => setOrgName(ev.target.value)}
            minLength={2}
            required
          />
          <button type="submit" className="nf-btn nf-btn-primary" disabled={busy}>
            {busy ? "Submitting…" : "Request activation"}
          </button>
        </form>
      )}
    </div>
  );
}

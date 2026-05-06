import { useCallback, useEffect, useState } from "react";
import {
  type Plane,
  M0_STEPS,
  buildM0Path,
  expandPathSuffix,
} from "./m0Flow";

const LS_ORG = "nf-m0-org-id";
const LS_PLANE = "nf-m0-plane";
const LS_SPARK = "nf-m0-spark-id";
const LS_PUR = "nf-m0-pursuit-id";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function looksLikeUuid(s: string): boolean {
  return UUID_RE.test(s.trim());
}

function apiFetchBase(): string {
  if (import.meta.env.DEV) {
    return "";
  }
  const fromEnv = import.meta.env.VITE_API_BASE as string | undefined;
  return fromEnv?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";
}

function curlDisplayBase(): string {
  const b = apiFetchBase();
  if (b) {
    return b;
  }
  return "http://127.0.0.1:8000";
}

export default function App() {
  const [plane, setPlane] = useState<Plane>("demo");
  const [orgId, setOrgId] = useState("");
  const [sparkId, setSparkId] = useState("");
  const [pursuitId, setPursuitId] = useState("");
  const [healthStatus, setHealthStatus] = useState<string | null>(null);
  const [healthErr, setHealthErr] = useState(false);
  const [trustStatus, setTrustStatus] = useState<string | null>(null);
  const [trustErr, setTrustErr] = useState(false);

  useEffect(() => {
    try {
      const o = localStorage.getItem(LS_ORG);
      const p = localStorage.getItem(LS_PLANE) as Plane | null;
      const s = localStorage.getItem(LS_SPARK);
      const u = localStorage.getItem(LS_PUR);
      if (o) {
        setOrgId(o);
      }
      if (p === "demo" || p === "real") {
        setPlane(p);
      }
      if (s) {
        setSparkId(s);
      }
      if (u) {
        setPursuitId(u);
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(LS_ORG, orgId);
      localStorage.setItem(LS_PLANE, plane);
      localStorage.setItem(LS_SPARK, sparkId);
      localStorage.setItem(LS_PUR, pursuitId);
    } catch {
      /* ignore */
    }
  }, [orgId, plane, sparkId, pursuitId]);

  const orgOk = looksLikeUuid(orgId);

  const pingHealth = useCallback(async () => {
    setHealthStatus(null);
    setHealthErr(false);
    const base = apiFetchBase();
    try {
      const r = await fetch(`${base}/health`);
      const j = await r.json().catch(() => ({}));
      if (!r.ok) {
        throw new Error(`HTTP ${r.status}`);
      }
      setHealthStatus(JSON.stringify(j));
    } catch (e) {
      setHealthErr(true);
      setHealthStatus(e instanceof Error ? e.message : "request failed");
    }
  }, []);

  const pingTrustManifest = useCallback(async () => {
    setTrustStatus(null);
    setTrustErr(false);
    if (!orgOk) {
      setTrustErr(true);
      setTrustStatus("Set a valid org UUID first.");
      return;
    }
    const base = apiFetchBase();
    const path = buildM0Path(plane, orgId.trim(), "/trust/manifest");
    try {
      const r = await fetch(`${base}${path}`, {
        headers: { "X-NF-Org-Id": orgId.trim() },
      });
      const text = await r.text();
      if (!r.ok) {
        throw new Error(`HTTP ${r.status}: ${text.slice(0, 180)}`);
      }
      setTrustStatus(
        text.length > 280 ? `${text.slice(0, 280)}…` : text,
      );
    } catch (e) {
      setTrustErr(true);
      setTrustStatus(e instanceof Error ? e.message : "request failed");
    }
  }, [orgId, orgOk, plane]);

  const displayBase = curlDisplayBase();

  return (
    <div className="app-shell">
      <header className="hero">
        <div className="pill-row" aria-hidden="true">
          <span className="pill">M0 walkthrough</span>
          <span className="pill">Buyer demo shell</span>
        </div>
        <h1>NativeForge — minimal M0 flow</h1>
        <p className="tagline">
          This surface explains the end-to-end backend spine already shipped and
          tested: tribal profile through trust, audit, and export. It is not a
          full product UI — it is a clean narrative you can pair with OpenAPI
          or automated demos.
        </p>
      </header>

      <section className="panel commitments">
        <h2>Buyer-safe framing (M0)</h2>
        <ul>
          <li>
            <strong>No auto-submit</strong> — NativeForge does not submit
            applications to Grants.gov or agency portals in M0.
          </li>
          <li>
            <strong>Human review</strong> — Draft outputs and review artifacts
            are gated; reviewers approve before anything is treated as final.
          </li>
          <li>
            <strong>SF-424 previews are non-final</strong> — JSON previews are
            snapshots, not submission-ready agency PDFs.
          </li>
          <li>
            <strong>Tenant-owned data</strong> — Scoped storage; see trust
            manifest and org export for portability commitments.
          </li>
          <li>
            <strong>Demo isolation</strong> — Use the <code>demo</code> API
            plane for synthetic orgs and the <code>real</code> plane only with
            matching <code>organizations.org_type</code>.
          </li>
        </ul>
      </section>

      <section className="panel">
        <h2>Connect to the API (optional)</h2>
        <p className="flow-intro">
          Product routes require header{" "}
          <code>X-NF-Org-Id</code> and <code>NF_DEV_ORG_HEADERS=true</code> for
          local simulation (see{" "}
          <code>docs/m0-demo-runbook.md</code>). With{" "}
          <code>npm run dev</code>, requests below use the Vite proxy to{" "}
          <code>127.0.0.1:8000</code>.
        </p>
        <div className="conn-grid split">
          <div className="field">
            <label htmlFor="plane">API plane</label>
            <select
              id="plane"
              value={plane}
              onChange={(e) => setPlane(e.target.value as Plane)}
            >
              <option value="demo">demo — /v1/nf/demo/orgs/…</option>
              <option value="real">real — /v1/nf/real/orgs/…</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="org">Organization UUID</label>
            <input
              id="org"
              value={orgId}
              onChange={(e) => setOrgId(e.target.value)}
              placeholder="bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
              autoComplete="off"
              spellCheck={false}
            />
          </div>
          <div className="field">
            <label htmlFor="spark">Grant Spark UUID (steps 3–6)</label>
            <input
              id="spark"
              value={sparkId}
              onChange={(e) => setSparkId(e.target.value)}
              placeholder="After POST /grant-sparks"
              autoComplete="off"
              spellCheck={false}
            />
          </div>
          <div className="field">
            <label htmlFor="pursuit">Pursuit UUID (steps 7–8)</label>
            <input
              id="pursuit"
              value={pursuitId}
              onChange={(e) => setPursuitId(e.target.value)}
              placeholder="After POST …/pursuit"
              autoComplete="off"
              spellCheck={false}
            />
          </div>
        </div>
        <div className="btn-row">
          <button type="button" className="primary" onClick={pingHealth}>
            Ping GET /health
          </button>
          <button
            type="button"
            onClick={pingTrustManifest}
            disabled={!orgOk}
          >
            GET trust/manifest (with header)
          </button>
        </div>
        {healthStatus !== null && (
          <p className={`status-line ${healthErr ? "err" : "ok"}`}>
            <strong>Health:</strong> {healthStatus}
          </p>
        )}
        {trustStatus !== null && (
          <p className={`status-line ${trustErr ? "err" : "ok"}`}>
            <strong>Trust manifest:</strong> {trustStatus}
          </p>
        )}
      </section>

      <section className="panel">
        <h2>M0 spine — twelve steps</h2>
        <p className="flow-intro">
          Paths expand with your plane and org. Substitute{" "}
          <code>{`{SPARK}`}</code> and <code>{`{PURSUIT}`}</code> after those
          resources exist. Copy uses base <code>{displayBase}</code> for curl —
          adjust if your API listens elsewhere.
        </p>
        <div className="steps">
          {M0_STEPS.map((step) => {
            const suffix = expandPathSuffix(
              step.pathSuffix,
              sparkId.trim(),
              pursuitId.trim(),
            );
            const path = buildM0Path(plane, orgId.trim(), suffix);
            const curl = `curl -sS -X ${step.method} \\
  -H 'X-NF-Org-Id: ${orgId.trim() || "<ORG_UUID>"}' \\
  '${displayBase}${path}'`;

            return (
              <article key={step.n} className="step-card">
                <div className="step-head">
                  <div className="step-num">{step.n}</div>
                  <div className="step-meta">
                    <div className="phase">{step.phase}</div>
                    <h3>{step.title}</h3>
                  </div>
                  <span className="method">{step.method}</span>
                </div>
                <div className="step-body">
                  <p>{step.summary}</p>
                  <pre className="path-box">{path}</pre>
                  <button
                    type="button"
                    className="primary"
                    style={{ marginTop: "0.6rem" }}
                    onClick={() => void navigator.clipboard.writeText(curl)}
                  >
                    Copy curl command
                  </button>
                </div>
              </article>
            );
          })}
        </div>
        <div className="links-row">
          <span>OpenAPI UI:</span>
          <a href="/docs" target="_blank" rel="noreferrer">
            /docs
          </a>
          <span>
            Full operator sequence:{" "}
            <code>docs/m0-demo-runbook.md</code> in this repo.
          </span>
        </div>
      </section>

      <p className="footnote">
        Automated full-chain proof:{" "}
        <code>tests/test_m0_full_chain_demo.py</code>. Before commits:{" "}
        <code>bash scripts/nativeforge_full_validation.sh</code>.
      </p>
    </div>
  );
}

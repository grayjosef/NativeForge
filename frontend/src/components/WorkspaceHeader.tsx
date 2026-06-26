import { useState } from "react";
import type { Plane } from "../m0Flow";

export interface WorkspaceHeaderProps {
  plane: Plane;
  orgId: string;
  onPlaneChange: (p: Plane) => void;
  onOrgChange: (id: string) => void;
  backendOk: boolean | null;
  backendHint: string;
  trustVersion: string | null;
  trustErr: boolean;
  onRefreshConnectivity: () => void;
  /** When set, shows Workspace / Workbench / Activation toggle (Sprint 21+ / M8). */
  surface?: "workspace" | "workbench" | "activation";
  onSurfaceChange?: (s: "workspace" | "workbench" | "activation") => void;
}

export function WorkspaceHeader({
  plane,
  orgId,
  onPlaneChange,
  onOrgChange,
  backendOk,
  backendHint,
  trustVersion,
  trustErr,
  onRefreshConnectivity,
  surface,
  onSurfaceChange,
}: WorkspaceHeaderProps) {
  const [contextOpen, setContextOpen] = useState(false);

  const trustOkShort = trustErr
    ? "Trust"
    : trustVersion
      ? `Trust · ${trustVersion}`
      : "Trust";

  return (
    <header className="nf-header-shell">
      <div className="nf-header-bar">
        <div className="nf-header-brand-block">
          <p className="nf-header-product">Grant pursuit workspace</p>
          <h1 className="nf-wordmark">NativeForge</h1>
          <p className="nf-header-promise">
            Review-ready pursuits — without auto-submitting applications.
          </p>
        </div>

        <div className="nf-header-cluster" aria-label="Workspace controls">
          {onSurfaceChange ? (
            <div className="nf-segment" role="group" aria-label="Product surface">
              <button
                type="button"
                className={`nf-segment-btn ${(surface ?? "workspace") === "workspace" ? "is-active" : ""}`}
                onClick={() => onSurfaceChange("workspace")}
              >
                Workspace
              </button>
              <button
                type="button"
                className={`nf-segment-btn ${(surface ?? "workspace") === "workbench" ? "is-active" : ""}`}
                onClick={() => onSurfaceChange("workbench")}
              >
                Workbench
              </button>
              <button
                type="button"
                className={`nf-segment-btn ${(surface ?? "workspace") === "activation" ? "is-active" : ""}`}
                onClick={() => onSurfaceChange("activation")}
              >
                Activation
              </button>
            </div>
          ) : null}

          <div className="nf-segment" role="group" aria-label="Environment">
            <button
              type="button"
              className={`nf-segment-btn ${plane === "demo" ? "is-active" : ""}`}
              onClick={() => onPlaneChange("demo")}
            >
              Demo
            </button>
            <button
              type="button"
              className={`nf-segment-btn ${plane === "real" ? "is-active" : ""}`}
              onClick={() => onPlaneChange("real")}
            >
              Real
            </button>
          </div>

          <div className="nf-cluster-pills" aria-live="polite">
            <span
              className={`nf-cluster-pill ${backendOk === true ? "is-ok" : backendOk === false ? "is-bad" : "is-wait"}`}
            >
              {backendOk === null
                ? "…"
                : backendOk
                  ? "Online"
                  : "Offline"}
            </span>
            <span
              className={`nf-cluster-pill nf-cluster-pill--trust ${trustErr ? "is-bad" : ""}`}
            >
              {trustOkShort}
            </span>
          </div>

          <button
            type="button"
            className="nf-icon-action"
            onClick={() => void onRefreshConnectivity()}
            title="Refresh workspace"
            aria-label="Refresh workspace"
          >
            <span className="nf-icon-refresh" aria-hidden="true" />
            <span className="nf-icon-action-text nf-hide-mobile">Refresh workspace</span>
          </button>

          <button
            type="button"
            className="nf-btn nf-btn-context"
            onClick={() => setContextOpen((v) => !v)}
            aria-expanded={contextOpen}
          >
            Context
          </button>
        </div>
      </div>

      {backendHint ? (
        <p className="nf-header-banner" role="status">
          {backendHint}
        </p>
      ) : null}

      {contextOpen ? (
        <div className="nf-context-drawer">
          <div className="nf-field">
            <label htmlFor="nf-org-context">Organization identifier</label>
            <input
              id="nf-org-context"
              className="nf-input"
              value={orgId}
              onChange={(e) => onOrgChange(e.target.value)}
              spellCheck={false}
              autoComplete="off"
              placeholder="Organization UUID"
            />
            <p className="nf-field-hint">
              Demo default:{" "}
              <code className="nf-code-inline">
                bbbbbbbb-cccc-dddd-eeee-ffffffffffff
              </code>
            </p>
          </div>
        </div>
      ) : null}
    </header>
  );
}

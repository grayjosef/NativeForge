import { useCallback, useEffect, useMemo, useState } from "react";
import { WorkbenchPage } from "./pages/WorkbenchPage";
import type { Plane } from "./m0Flow";
import {
  apiFetchBase,
  createGrantSpark,
  createOrUpdateTribalProfile,
  demoGrantSparkBody,
  demoTribalProfileBody,
  getAuditEvents,
  getFormPackage,
  getGrantSpark,
  getHealth,
  getNofoRequirements,
  getOrgDataSnapshot,
  getPursuitDetail,
  getReviewSummary,
  getScoreLatest,
  getTribalProfile,
  getTrustManifest,
  listGrantSparks,
  openPursuit,
  patchPursuitTask,
  postFormPackage,
  postNofoExtractStub,
  postScoreSpark,
} from "./m0ApiClient";
import { friendlyError } from "./friendlyError";
import {
  runM0LiveDemoSequence,
  type RunnerLogStep,
} from "./m0LiveDemoRunner";
import { ProgressStrip } from "./components/ProgressStrip";
import { WhatsNextCard } from "./components/WhatsNextCard";
import { WorkspaceHeader } from "./components/WorkspaceHeader";
import { OrgReadinessCard } from "./components/OrgReadinessCard";
import { GrantSparkCard } from "./components/GrantSparkCard";
import { NofoRequirementsCard } from "./components/NofoRequirementsCard";
import { ScoreCard } from "./components/ScoreCard";
import { PursuitCard } from "./components/PursuitCard";
import { FormPreviewCard } from "./components/FormPreviewCard";
import { TrustCenterCard } from "./components/TrustCenterCard";
import { OperatorTools } from "./components/OperatorTools";
import {
  buildProgressSteps,
  buildWhatsNext,
  type NextActionId,
} from "./workspaceProgress";

const LS_ORG = "nf-m0-org-id";
const LS_PLANE = "nf-m0-plane";
const LS_SPARK = "nf-m0-spark-id";
const LS_PUR = "nf-m0-pursuit-id";
const LS_ACTOR = "nf-m0-actor-id";
const DEFAULT_ORG = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function looksLikeUuid(s: string): boolean {
  return UUID_RE.test(s.trim());
}

function readSurface(): "workspace" | "workbench" {
  try {
    const q = new URLSearchParams(window.location.search).get("view");
    return q === "workbench" ? "workbench" : "workspace";
  } catch {
    return "workspace";
  }
}

function str(v: unknown): string {
  return typeof v === "string" ? v : v != null ? String(v) : "";
}

export default function App() {
  const base = apiFetchBase();

  const [plane, setPlane] = useState<Plane>("demo");
  const [orgId, setOrgId] = useState("");
  const [sparkId, setSparkId] = useState("");
  const [pursuitId, setPursuitId] = useState("");
  const [actorId, setActorId] = useState("");

  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [backendHint, setBackendHint] = useState("");
  const [trustVersion, setTrustVersion] = useState<string | null>(null);
  const [trustErr, setTrustErr] = useState(false);

  const [profileRecord, setProfileRecord] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [orgBusy, setOrgBusy] = useState(false);
  const [orgErr, setOrgErr] = useState<string | null>(null);

  const [sparks, setSparks] = useState<Record<string, unknown>[]>([]);
  const [sparkDetail, setSparkDetail] = useState<Record<string, unknown> | null>(
    null,
  );
  const [sparkBusy, setSparkBusy] = useState(false);
  const [sparkErr, setSparkErr] = useState<string | null>(null);

  const [requirements, setRequirements] = useState<Record<string, unknown>[]>(
    [],
  );
  const [nofoBusy, setNofoBusy] = useState(false);
  const [nofoErr, setNofoErr] = useState<string | null>(null);

  const [score, setScore] = useState<Record<string, unknown> | null>(null);
  const [scoreBusy, setScoreBusy] = useState(false);
  const [scoreErr, setScoreErr] = useState<string | null>(null);

  const [pursuit, setPursuit] = useState<Record<string, unknown> | null>(null);
  const [pursuitBusy, setPursuitBusy] = useState(false);
  const [pursuitErr, setPursuitErr] = useState<string | null>(null);

  const [formPkg, setFormPkg] = useState<Record<string, unknown> | null>(null);
  const [formBusy, setFormBusy] = useState(false);
  const [formErr, setFormErr] = useState<string | null>(null);

  const [trustManifest, setTrustManifest] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [auditCount, setAuditCount] = useState<number | null>(null);
  const [reviewSummary, setReviewSummary] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [exportHint, setExportHint] = useState<string | null>(null);
  const [trustBusy, setTrustBusy] = useState(false);
  const [trustCardErr, setTrustCardErr] = useState<string | null>(null);

  const [runnerSteps, setRunnerSteps] = useState<RunnerLogStep[]>([]);
  const [runnerBusy, setRunnerBusy] = useState(false);
  const [operatorOpen, setOperatorOpen] = useState(false);

  const [surface, setSurfaceState] = useState<"workspace" | "workbench">(() =>
    readSurface(),
  );

  const setSurface = useCallback((s: "workspace" | "workbench") => {
    setSurfaceState(s);
    try {
      const u = new URL(window.location.href);
      if (s === "workbench") {
        u.searchParams.set("view", "workbench");
      } else {
        u.searchParams.delete("view");
      }
      window.history.replaceState({}, "", u.toString());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    const onPop = () => setSurfaceState(readSurface());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  useEffect(() => {
    try {
      const o = localStorage.getItem(LS_ORG);
      const p = localStorage.getItem(LS_PLANE) as Plane | null;
      const s = localStorage.getItem(LS_SPARK);
      const u = localStorage.getItem(LS_PUR);
      let a = localStorage.getItem(LS_ACTOR);
      if (!a || !looksLikeUuid(a)) {
        a = crypto.randomUUID();
        localStorage.setItem(LS_ACTOR, a);
      }
      setActorId(a);
      setOrgId(o && looksLikeUuid(o) ? o : DEFAULT_ORG);
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
      setOrgId(DEFAULT_ORG);
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(LS_ORG, orgId);
      localStorage.setItem(LS_PLANE, plane);
      localStorage.setItem(LS_SPARK, sparkId);
      localStorage.setItem(LS_PUR, pursuitId);
      if (actorId) {
        localStorage.setItem(LS_ACTOR, actorId);
      }
    } catch {
      /* ignore */
    }
  }, [orgId, plane, sparkId, pursuitId, actorId]);

  const orgOk = looksLikeUuid(orgId);
  const o = orgId.trim();
  const sparkSelected = orgOk && !!sparkId.trim();

  const refreshConnectivity = useCallback(async () => {
    setTrustErr(false);
    try {
      const h = await getHealth(base);
      setBackendOk(h.ok);
      setBackendHint(
        h.ok
          ? ""
          : "We couldn't reach the workspace service. If you're on a local demo, start the API (nf-up) and try again.",
      );
    } catch {
      setBackendOk(false);
      setBackendHint(
        "We couldn't reach the workspace service. Check your connection or start the local API.",
      );
    }
    if (!orgOk) {
      setTrustVersion(null);
      setTrustErr(true);
      return;
    }
    try {
      const m = await getTrustManifest(base, plane, o);
      setTrustVersion(str(m.manifest_schema_version) || "ok");
      setTrustErr(false);
    } catch {
      setTrustVersion(null);
      setTrustErr(true);
    }
  }, [base, orgOk, plane, o]);

  useEffect(() => {
    void refreshConnectivity();
  }, [refreshConnectivity]);

  const loadProfile = useCallback(async () => {
    if (!orgOk) {
      return;
    }
    setOrgErr(null);
    try {
      const p = await getTribalProfile(base, plane, o);
      if (p === null) {
        setProfileRecord(null);
      } else {
        setProfileRecord(p);
      }
    } catch (e) {
      setProfileRecord(null);
      setOrgErr(friendlyError(e));
    }
  }, [base, orgOk, plane, o]);

  useEffect(() => {
    void loadProfile();
  }, [loadProfile]);

  const profileFields = useMemo(() => {
    if (!profileRecord) {
      return null;
    }
    const addr = profileRecord.physical_address as
      | Record<string, unknown>
      | undefined;
    const gm = profileRecord.grants_manager as
      | Record<string, unknown>
      | undefined;
    return {
      legalName: str(profileRecord.legal_name),
      entityType: str(profileRecord.entity_type),
      city: addr ? str(addr.city) : "",
      state: addr ? str(addr.state) : "",
      grantsContact: gm
        ? [str(gm.name), str(gm.email)].filter(Boolean).join(" · ")
        : "",
    };
  }, [profileRecord]);

  const onCreateRefreshProfile = useCallback(async () => {
    if (!orgOk) {
      return;
    }
    setOrgBusy(true);
    setOrgErr(null);
    try {
      const { profile } = await createOrUpdateTribalProfile(
        base,
        plane,
        o,
        demoTribalProfileBody(),
      );
      setProfileRecord(profile);
    } catch (e) {
      setOrgErr(friendlyError(e));
    } finally {
      setOrgBusy(false);
    }
  }, [base, orgOk, plane, o]);

  const loadSparksAndDetail = useCallback(async () => {
    if (!orgOk) {
      return;
    }
    setSparkErr(null);
    setSparkBusy(true);
    try {
      const list = await listGrantSparks(base, plane, o);
      setSparks(list);
      const sid = sparkId.trim();
      if (!sid) {
        setSparkDetail(null);
      } else if (list.some((r) => str(r.id) === sid)) {
        try {
          const d = await getGrantSpark(base, plane, o, sid);
          setSparkDetail(d);
        } catch (e) {
          setSparkErr(friendlyError(e));
          setSparkDetail(null);
        }
      } else {
        setSparkId("");
        setPursuitId("");
        setSparkDetail(null);
      }
    } catch (e) {
      setSparkErr(friendlyError(e));
    } finally {
      setSparkBusy(false);
    }
  }, [base, orgOk, plane, o, sparkId]);

  useEffect(() => {
    void loadSparksAndDetail();
  }, [loadSparksAndDetail]);

  useEffect(() => {
    setRequirements([]);
    setScore(null);
    setScoreErr(null);
  }, [sparkId]);

  const onCreateDemoSpark = useCallback(async () => {
    if (!orgOk) {
      return;
    }
    setSparkBusy(true);
    setSparkErr(null);
    try {
      const deadline = new Date(Date.now() + 50 * 86_400_000).toISOString();
      const body = demoGrantSparkBody(
        `workspace-${crypto.randomUUID()}`,
        deadline,
      );
      const row = await createGrantSpark(base, plane, o, body);
      const id = str(row.id);
      setSparkId(id);
      setSparkDetail(row);
      await loadSparksAndDetail();
    } catch (e) {
      setSparkErr(friendlyError(e));
    } finally {
      setSparkBusy(false);
    }
  }, [base, orgOk, plane, o, loadSparksAndDetail]);

  const onExtractNofo = useCallback(async () => {
    if (!sparkSelected) {
      return;
    }
    setNofoBusy(true);
    setNofoErr(null);
    try {
      await postNofoExtractStub(base, plane, o, sparkId.trim());
    } catch (e) {
      setNofoErr(friendlyError(e));
    } finally {
      setNofoBusy(false);
    }
  }, [base, o, plane, sparkId, sparkSelected]);

  const onLoadRequirements = useCallback(async () => {
    if (!sparkSelected) {
      return;
    }
    setNofoBusy(true);
    setNofoErr(null);
    try {
      const r = await getNofoRequirements(base, plane, o, sparkId.trim());
      setRequirements(r.requirements ?? []);
    } catch (e) {
      setNofoErr(friendlyError(e));
    } finally {
      setNofoBusy(false);
    }
  }, [base, o, plane, sparkId, sparkSelected]);

  const onScore = useCallback(async () => {
    if (!sparkSelected) {
      return;
    }
    setScoreBusy(true);
    setScoreErr(null);
    try {
      const s = await postScoreSpark(
        base,
        plane,
        o,
        sparkId.trim(),
        actorId || null,
      );
      setScore(s);
    } catch (e) {
      setScoreErr(friendlyError(e));
    } finally {
      setScoreBusy(false);
    }
  }, [actorId, base, o, plane, sparkId, sparkSelected]);

  const onRefreshScore = useCallback(async () => {
    if (!sparkSelected) {
      return;
    }
    setScoreBusy(true);
    setScoreErr(null);
    try {
      const s = await getScoreLatest(base, plane, o, sparkId.trim());
      setScore(s);
    } catch (e) {
      setScoreErr(friendlyError(e));
      setScore(null);
    } finally {
      setScoreBusy(false);
    }
  }, [base, o, plane, sparkId, sparkSelected]);

  const onOpenPursuit = useCallback(async () => {
    if (!sparkSelected || !actorId) {
      return;
    }
    setPursuitBusy(true);
    setPursuitErr(null);
    try {
      const p = await openPursuit(
        base,
        plane,
        o,
        sparkId.trim(),
        actorId,
        "Workspace pursuit.",
      );
      const id = str(p.id);
      setPursuitId(id);
      setPursuit(p);
    } catch (e) {
      setPursuitErr(friendlyError(e));
    } finally {
      setPursuitBusy(false);
    }
  }, [actorId, base, o, plane, sparkId, sparkSelected]);

  const onRefreshPursuit = useCallback(async () => {
    if (!orgOk || !pursuitId.trim()) {
      return;
    }
    setPursuitBusy(true);
    setPursuitErr(null);
    try {
      const p = await getPursuitDetail(base, plane, o, pursuitId.trim());
      setPursuit(p);
    } catch (e) {
      setPursuitErr(friendlyError(e));
    } finally {
      setPursuitBusy(false);
    }
  }, [base, orgOk, o, plane, pursuitId]);

  useEffect(() => {
    if (!orgOk || !pursuitId.trim()) {
      setPursuit(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const p = await getPursuitDetail(base, plane, o, pursuitId.trim());
        if (!cancelled) {
          setPursuit(p);
        }
      } catch {
        if (!cancelled) {
          setPursuitId("");
          setPursuit(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [base, orgOk, o, plane, pursuitId]);

  useEffect(() => {
    if (!orgOk || !pursuitId.trim()) {
      setFormPkg(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const pkg = await getFormPackage(base, plane, o, pursuitId.trim());
        if (!cancelled) {
          setFormPkg(pkg);
          setFormErr(null);
        }
      } catch {
        if (!cancelled) {
          setFormPkg(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [base, orgOk, o, plane, pursuitId]);

  const onToggleTask = useCallback(
    async (taskId: string, currentStatus: string) => {
      if (!orgOk || !pursuitId.trim()) {
        return;
      }
      const next = currentStatus === "done" ? "pending" : "done";
      setPursuitBusy(true);
      setPursuitErr(null);
      try {
        await patchPursuitTask(base, plane, o, pursuitId.trim(), taskId, {
          status: next,
        });
        await onRefreshPursuit();
      } catch (e) {
        setPursuitErr(friendlyError(e));
      } finally {
        setPursuitBusy(false);
      }
    },
    [base, onRefreshPursuit, orgOk, o, plane, pursuitId],
  );

  const onCreateFormPackage = useCallback(async () => {
    if (!orgOk || !pursuitId.trim()) {
      return;
    }
    setFormBusy(true);
    setFormErr(null);
    try {
      const pkg = await postFormPackage(
        base,
        plane,
        o,
        pursuitId.trim(),
        actorId || null,
      );
      setFormPkg(pkg);
    } catch (e) {
      setFormErr(friendlyError(e));
    } finally {
      setFormBusy(false);
    }
  }, [actorId, base, orgOk, o, plane, pursuitId]);

  const onRefreshFormPackage = useCallback(async () => {
    if (!orgOk || !pursuitId.trim()) {
      return;
    }
    setFormBusy(true);
    setFormErr(null);
    try {
      const pkg = await getFormPackage(base, plane, o, pursuitId.trim());
      setFormPkg(pkg);
    } catch (e) {
      setFormErr(friendlyError(e));
      setFormPkg(null);
    } finally {
      setFormBusy(false);
    }
  }, [base, orgOk, o, plane, pursuitId]);

  const refreshTrustCenter = useCallback(async () => {
    if (!orgOk) {
      return;
    }
    setTrustBusy(true);
    setTrustCardErr(null);
    try {
      const [m, a, r] = await Promise.all([
        getTrustManifest(base, plane, o),
        getAuditEvents(base, plane, o, 200),
        getReviewSummary(base, plane, o),
      ]);
      setTrustManifest(m);
      setTrustVersion(str(m.manifest_schema_version) || null);
      setAuditCount(Array.isArray(a.events) ? a.events.length : 0);
      setReviewSummary(r);
      setExportHint(null);
    } catch (e) {
      setTrustCardErr(friendlyError(e));
    } finally {
      setTrustBusy(false);
    }
  }, [base, orgOk, o, plane]);

  useEffect(() => {
    void refreshTrustCenter();
  }, [refreshTrustCenter]);

  const onExportDownload = useCallback(async () => {
    if (!orgOk || !actorId) {
      return;
    }
    setTrustBusy(true);
    setTrustCardErr(null);
    try {
      const snap = await getOrgDataSnapshot(base, plane, o, {
        actorId,
        auditSampleLimit: 50,
        includeSf424Previews: false,
      });
      setExportHint(
        "Organization-owned snapshot saved to your Downloads folder.",
      );
      const blob = new Blob([JSON.stringify(snap, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `nativeforge-org-snapshot-${o.slice(0, 8)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setTrustCardErr(friendlyError(e));
    } finally {
      setTrustBusy(false);
    }
  }, [actorId, base, o, orgOk, plane]);

  const runLiveSequence = useCallback(async () => {
    if (!orgOk) {
      return;
    }
    setRunnerBusy(true);
    try {
      const result = await runM0LiveDemoSequence(
        base,
        plane,
        orgId.trim(),
        setRunnerSteps,
      );
      if (result.ok && result.sparkId && result.pursuitId) {
        setSparkId(result.sparkId);
        setPursuitId(result.pursuitId);
      }
      await refreshConnectivity();
      await loadProfile();
      await loadSparksAndDetail();
      await refreshTrustCenter();
    } finally {
      setRunnerBusy(false);
    }
  }, [
    base,
    loadProfile,
    loadSparksAndDetail,
    orgId,
    orgOk,
    plane,
    refreshConnectivity,
    refreshTrustCenter,
  ]);

  const progressSteps = useMemo(
    () =>
      buildProgressSteps({
        profileRecord,
        orgProfileErr: !!orgErr,
        sparkDetail,
        sparkApiErr: !!sparkErr,
        requirementsLen: requirements.length,
        nofoErr: !!nofoErr,
        score,
        scoreErr: !!scoreErr,
        pursuitId,
        pursuit,
        pursuitErr: !!pursuitErr,
        formPkg,
        formErr: !!formErr,
        trustManifest,
        reviewSummary,
        trustCenterErr: !!trustCardErr,
      }),
    [
      profileRecord,
      orgErr,
      sparkDetail,
      sparkErr,
      requirements.length,
      nofoErr,
      score,
      scoreErr,
      pursuitId,
      pursuit,
      pursuitErr,
      formPkg,
      formErr,
      trustManifest,
      reviewSummary,
      trustCardErr,
    ],
  );

  const stepChip = useCallback(
    (id: string) =>
      progressSteps.find((s) => s.id === id)?.lineSummary ?? "—",
    [progressSteps],
  );

  const hasProfile = profileRecord !== null;
  const hasSpark = sparkDetail !== null;
  const hasReq = requirements.length > 0;
  const hasScore = score !== null;
  const hasPursuit =
    !!pursuitId.trim() && pursuit !== null;
  const hasForm = formPkg !== null;

  const whatsNext = useMemo(
    () =>
      buildWhatsNext({
        orgOk,
        anyBusy:
          orgBusy ||
          sparkBusy ||
          nofoBusy ||
          scoreBusy ||
          pursuitBusy ||
          formBusy ||
          trustBusy ||
          runnerBusy,
        hasProfile,
        hasSpark,
        hasReq,
        hasScore,
        hasPursuit,
        hasForm,
      }),
    [
      orgOk,
      sparkBusy,
      nofoBusy,
      scoreBusy,
      pursuitBusy,
      formBusy,
      orgBusy,
      trustBusy,
      runnerBusy,
      hasProfile,
      hasSpark,
      hasReq,
      hasScore,
      hasPursuit,
      hasForm,
    ],
  );

  const runPrimaryNext = useCallback(() => {
    const id: NextActionId = whatsNext.actionId;
    if (id === "profile") {
      void onCreateRefreshProfile();
    } else if (id === "spark") {
      void onCreateDemoSpark();
    } else if (id === "nofo_extract") {
      void onExtractNofo();
    } else if (id === "score") {
      void onScore();
    } else if (id === "pursuit") {
      void onOpenPursuit();
    } else if (id === "sf424") {
      void onCreateFormPackage();
    } else if (id === "trust_export") {
      void onExportDownload();
    } else if (id === "trust_refresh") {
      void refreshTrustCenter();
    }
  }, [
    whatsNext.actionId,
    onCreateRefreshProfile,
    onCreateDemoSpark,
    onExtractNofo,
    onScore,
    onOpenPursuit,
    onCreateFormPackage,
    onExportDownload,
    refreshTrustCenter,
  ]);

  return (
    <div className="nf-app">
      <WorkspaceHeader
        plane={plane}
        orgId={orgId}
        onPlaneChange={setPlane}
        onOrgChange={setOrgId}
        backendOk={backendOk}
        backendHint={backendHint}
        trustVersion={trustVersion}
        trustErr={trustErr}
        onRefreshConnectivity={refreshConnectivity}
        surface={surface}
        onSurfaceChange={setSurface}
      />

      {surface === "workspace" ? (
        <ProgressStrip steps={progressSteps} />
      ) : null}

      {surface === "workspace" ? (
      <div className="nf-layout">
        <main className="nf-workflow">
          <OrgReadinessCard
            busy={orgBusy}
            profileFields={profileFields}
            error={orgErr}
            statusChip={stepChip("profile")}
            onCreateRefresh={onCreateRefreshProfile}
          />
          <GrantSparkCard
            sparks={sparks}
            selectedSparkId={sparkId}
            onSelectSpark={setSparkId}
            detail={sparkDetail}
            busy={sparkBusy}
            error={sparkErr}
            statusChip={stepChip("spark")}
            profileReady={hasProfile}
            onRefreshList={loadSparksAndDetail}
            onCreateDemoSpark={onCreateDemoSpark}
          />
          <NofoRequirementsCard
            sparkSelected={sparkSelected}
            requirements={requirements}
            busy={nofoBusy}
            error={nofoErr}
            statusChip={stepChip("nofo")}
            locked={!hasSpark}
            onExtract={onExtractNofo}
            onLoadRequirements={onLoadRequirements}
          />
          <ScoreCard
            sparkSelected={sparkSelected}
            score={score}
            busy={scoreBusy}
            error={scoreErr}
            statusChip={stepChip("score")}
            locked={!hasReq}
            onScore={onScore}
            onRefreshLatest={onRefreshScore}
          />
          <PursuitCard
            sparkSelected={sparkSelected}
            pursuitId={pursuitId}
            pursuit={pursuit}
            busy={pursuitBusy}
            error={pursuitErr}
            statusChip={stepChip("pursuit")}
            locked={!hasScore}
            onOpenPursuit={onOpenPursuit}
            onRefreshDetail={onRefreshPursuit}
            onToggleTask={onToggleTask}
          />
          <FormPreviewCard
            pursuitId={pursuitId}
            pkg={formPkg}
            busy={formBusy}
            error={formErr}
            statusChip={stepChip("forms")}
            locked={!hasPursuit}
            onCreatePreview={onCreateFormPackage}
            onRefresh={onRefreshFormPackage}
          />
        </main>

        <aside className="nf-rail" aria-label="Guidance and trust">
          <WhatsNextCard
            headline={whatsNext.headline}
            detail={whatsNext.detail}
            primaryLabel={whatsNext.primaryLabel}
            onPrimary={runPrimaryNext}
            busy={
              orgBusy ||
              sparkBusy ||
              nofoBusy ||
              scoreBusy ||
              pursuitBusy ||
              formBusy ||
              trustBusy ||
              runnerBusy
            }
          />
          <TrustCenterCard
            manifest={trustManifest}
            auditCount={auditCount}
            reviewSummary={reviewSummary}
            exportHint={exportHint}
            busy={trustBusy}
            error={trustCardErr}
            statusChip={stepChip("trust")}
            onRefresh={refreshTrustCenter}
            onExportDownload={onExportDownload}
          />
        </aside>
      </div>
      ) : (
        <WorkbenchPage plane={plane} orgId={orgId.trim()} orgOk={orgOk} />
      )}

      <OperatorTools
        open={operatorOpen}
        onToggle={() => setOperatorOpen((v) => !v)}
        runnerBusy={runnerBusy}
        runnerSteps={runnerSteps}
        orgOk={orgOk}
        onRunSequence={runLiveSequence}
      />

      <p className="nf-footnote">
        NativeForge does not submit to Grants.gov. Previews are for internal
        review only.
      </p>
    </div>
  );
}

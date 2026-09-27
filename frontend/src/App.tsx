import { useCallback, useEffect, useMemo, useState } from "react";
import { WorkbenchPage } from "./pages/WorkbenchPage";
import { ActivationPage } from "./pages/ActivationPage";
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
  extractApplyPath,
  getApplyPath,
  getNofoLatest,
  getNofoRequirements,
  getOrgDataSnapshot,
  getPursuitDetail,
  listPursuits,
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
import { interpretError } from "./friendlyError";
import type { CustomerState } from "./customerState";
import {
  runM0LiveDemoSequence,
  type RunnerLogStep,
} from "./m0LiveDemoRunner";
import { WorkspacePage } from "./pages/WorkspacePage";
import { OpportunitiesPage } from "./pages/OpportunitiesPage";
import { AddOpportunityPage } from "./pages/AddOpportunityPage";
import { draftToCreateBody, type IntakeDraft } from "./lib/opportunityIntake";
import { DiscoverPage } from "./pages/DiscoverPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { PursuitsPage } from "./pages/PursuitsPage";
import { TrustPage } from "./pages/TrustPage";
import { OrganizationPage } from "./pages/OrganizationPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SignInPage } from "./pages/SignInPage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { WhatsNextCard } from "./components/WhatsNextCard";
import { AppShell } from "./components/shell/AppShell";
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
import { isSurface, readSurface, writeSurface, type AppSurface } from "./viewSurface";
import { daysUntil } from "./lib/dates";
import { surfaceForNav } from "./components/shell/navigation";
import { getAuthSession, signOut } from "./authApiClient";
import { NmWaOperatorDemoPage } from "./pages/NmWaOperatorDemoPage";
import { ScCustomerDemoPage } from "./pages/ScCustomerDemoPage";
import { BetaOnboardingCockpitPage } from "./pages/BetaOnboardingCockpitPage";

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
  const [orgErr, setOrgErr] = useState<CustomerState | null>(null);

  const [sparks, setSparks] = useState<Record<string, unknown>[]>([]);
  const [sparkDetail, setSparkDetail] = useState<Record<string, unknown> | null>(
    null,
  );
  const [sparkBusy, setSparkBusy] = useState(false);
  const [sparkErr, setSparkErr] = useState<CustomerState | null>(null);

  const [requirements, setRequirements] = useState<Record<string, unknown>[]>(
    [],
  );
  const [nofoBusy, setNofoBusy] = useState(false);
  const [nofoErr, setNofoErr] = useState<CustomerState | null>(null);

  const [score, setScore] = useState<Record<string, unknown> | null>(null);
  const [scoreBusy, setScoreBusy] = useState(false);
  const [scoreErr, setScoreErr] = useState<CustomerState | null>(null);

  const [pursuit, setPursuit] = useState<Record<string, unknown> | null>(null);
  const [pursuitBusy, setPursuitBusy] = useState(false);
  const [pursuitErr, setPursuitErr] = useState<CustomerState | null>(null);

  const [formPkg, setFormPkg] = useState<Record<string, unknown> | null>(null);
  const [formBusy, setFormBusy] = useState(false);
  const [formErr, setFormErr] = useState<CustomerState | null>(null);

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
  const [trustCardErr, setTrustCardErr] = useState<CustomerState | null>(null);

  const [runnerSteps, setRunnerSteps] = useState<RunnerLogStep[]>([]);
  const [runnerBusy, setRunnerBusy] = useState(false);
  const [operatorOpen, setOperatorOpen] = useState(false);

  const [surface, setSurfaceState] = useState<AppSurface>(() => readSurface());
  const [nofoLatest, setNofoLatest] = useState<Record<string, unknown> | null>(null);
  const [applyPath, setApplyPath] = useState<Record<string, unknown> | null>(null);
  const [applyBusy, setApplyBusy] = useState(false);
  const [session, setSession] = useState<{
    authenticated: boolean;
    organizationId: string | null;
  } | null>(null);

  /** The `?auth=` code the callback leaves behind when it returns a browser. */
  const authNotice = useMemo(() => {
    try {
      return new URLSearchParams(window.location.search).get("auth");
    } catch {
      return null;
    }
  }, []);

  /**
   * When an organization-scoped request may be issued at all.
   *
   * SC, NM/WA and the beta cockpit render entirely from bundled JSON, so
   * firing one makes a viewer's own browser probe 127.0.0.1:8000 - which can
   * never succeed, is mixed content on an https page, and puts eight red
   * errors in front of a buyer who opens DevTools.
   *
   * Sign-in has no organization yet, and neither does an unauthenticated
   * visitor anywhere else: every data route resolves its organization from a
   * membership row and refuses without one. Firing them anyway produced a
   * workspace carrying three red "Problem" cards - profile, opportunities and
   * trust - which is one missing cookie reported as three product failures.
   *
   * Unknown counts as not-yet. `session` is null until the check answers, and
   * gating on "definitely unauthenticated" let everything fire on the first
   * render, before the answer arrived: 51 refusals in the console of the
   * first page a buyer opens. We do not know whether we may call, so we do
   * not call.
   */
  const mayLoadOrgData = session?.authenticated === true;
  const offlineDemoSurface =
    surface === "sc_customer_demo" ||
    surface === "nm_wa_operator_demo" ||
    surface === "beta_onboarding_cockpit" ||
    surface === "sign_in" ||
    !mayLoadOrgData;

  const setSurface = useCallback((s: AppSurface) => {
    setSurfaceState(s);
    writeSurface(s);
    // A destination change that leaves the page scrolled halfway down the
    // previous one reads as the navigation not having worked.
    //
    // Only when there is something to scroll. jsdom defines `scrollTo` and
    // has it report "Not implemented" to stderr rather than throwing, so
    // neither a try/catch nor an existence check stopped every test run
    // printing a stack trace for something working exactly as intended. A
    // page already at the top does not need scrolling anyway.
    try {
      if (window.scrollY > 0) {
        window.scrollTo({ top: 0 });
      }
    } catch {
      /* a page that cannot be scrolled is still on the right destination */
    }
  }, []);

  /**
   * Navigate by destination, for callers that only know where they want to go.
   *
   * Takes a navigation id or a surface name. Nav ids are tried first, because
   * most destinations are rail items; surfaces cover the ones that are not.
   * "Add an opportunity" is an action taken from two pages rather than a
   * ninth entry in the rail, and a resolver that knew only nav ids silently
   * did nothing when asked for it - a dead button with no error anywhere.
   */
  const setSurfaceByNav = useCallback(
    (destination: string) => {
      const target = surfaceForNav(destination);
      if (target) {
        setSurface(target);
      } else if (isSurface(destination)) {
        setSurface(destination);
      }
    },
    [setSurface],
  );

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
    if (offlineDemoSurface) return;
    void refreshConnectivity();
  }, [refreshConnectivity, offlineDemoSurface]);

  // Asked once, on load. A session that cannot be read is reported as no
  // session rather than as an error: not being signed in is the ordinary
  // state of this application today, not a fault.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await getAuthSession(base);
        if (!cancelled) {
          setSession({
            authenticated: res.authenticated,
            organizationId: res.organization_id,
          });
        }
      } catch {
        if (!cancelled) setSession({ authenticated: false, organizationId: null });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [base]);

  /**
   * First-run routing.
   *
   * An unauthenticated visitor cannot see anything: every data route resolves
   * its organization from a membership row and refuses without a session. So
   * they are sent to sign in rather than shown an empty workspace that
   * reports three separate failures for one missing cookie.
   *
   * The operator and offline demo surfaces are exempt because they genuinely
   * work without a session - they render from bundled data - and onboarding
   * is exempt because it is where a signed-in visitor without a profile is
   * sent next.
   */
  useEffect(() => {
    if (session === null || session.authenticated) return;
    if (
      surface === "sign_in" ||
      surface === "onboarding" ||
      surface === "sc_customer_demo" ||
      surface === "nm_wa_operator_demo" ||
      surface === "beta_onboarding_cockpit"
    ) {
      return;
    }
    setSurface("sign_in");
  }, [session, surface, setSurface]);

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
      setOrgErr(interpretError(e));
    }
  }, [base, orgOk, plane, o]);

  useEffect(() => {
    if (offlineDemoSurface) return;
    void loadProfile();
  }, [loadProfile, offlineDemoSurface]);

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
      setOrgErr(interpretError(e));
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
          setSparkErr(interpretError(e));
          setSparkDetail(null);
        }
      } else {
        setSparkId("");
        setPursuitId("");
        setSparkDetail(null);
      }
    } catch (e) {
      setSparkErr(interpretError(e));
    } finally {
      setSparkBusy(false);
    }
  }, [base, orgOk, plane, o, sparkId]);

  useEffect(() => {
    if (offlineDemoSurface) return;
    void loadSparksAndDetail();
  }, [loadSparksAndDetail, offlineDemoSurface]);

  useEffect(() => {
    setRequirements([]);
    setScore(null);
    setScoreErr(null);
    setNofoLatest(null);
    setApplyPath(null);
  }, [sparkId]);

  // Everything already known about the selected opportunity, on arrival.
  //
  // The extraction run and the requirements it produced are one fact shown two
  // ways, so they are fetched together: loading only the requirements leaves
  // "read but produced nothing" indistinguishable from "never read".
  //
  // The score is here for a blunter reason. It used to be set only by pressing
  // the button, so a customer who scored an opportunity, navigated, and came
  // back was told to score it again - and the Pursuits page, which unlocks on
  // a score, refused to open a pursuit against an opportunity that had already
  // been evaluated. Work the product had done and stored was invisible the
  // moment anybody changed page.
  useEffect(() => {
    if (offlineDemoSurface || !sparkSelected) return;
    let cancelled = false;
    void (async () => {
      const [reqs, latest, latestScore, openPursuits, apply] = await Promise.all([
        getNofoRequirements(base, plane, o, sparkId.trim()).catch(() => null),
        getNofoLatest(base, plane, o, sparkId.trim()).catch(() => null),
        // A 404 here is "not scored yet", which is the ordinary state of a new
        // opportunity rather than a failure worth reporting on arrival.
        getScoreLatest(base, plane, o, sparkId.trim()).catch(() => null),
        listPursuits(base, plane, o).catch(() => null),
        getApplyPath(base, plane, o, sparkId.trim()).catch(() => null),
      ]);
      if (cancelled) return;
      if (reqs) setRequirements(reqs.requirements ?? []);
      setNofoLatest(latest);
      if (latestScore) setScore(latestScore);
      setApplyPath(apply);

      // Recover the pursuit that already exists for this opportunity.
      //
      // Without this the workspace only knew about a pursuit it had opened on
      // this page. After a reload it offered "Open a pursuit", the API
      // correctly refused with 409 because one was already open, and the
      // customer was shown a generic failure over work the product had
      // already done. The id is on the server; it was simply never asked for.
      if (openPursuits && !pursuitId.trim()) {
        const mine = openPursuits.find((p) => str(p.grant_spark_id) === sparkId.trim());
        if (mine) setPursuitId(str(mine.id));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [base, o, plane, sparkId, sparkSelected, offlineDemoSurface]);

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
      setSparkErr(interpretError(e));
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
      setNofoErr(interpretError(e));
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
      setNofoErr(interpretError(e));
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
      setScoreErr(interpretError(e));
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
      setScoreErr(interpretError(e));
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
      setPursuitErr(interpretError(e));
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
      setPursuitErr(interpretError(e));
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
        setPursuitErr(interpretError(e));
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
      setFormErr(interpretError(e));
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
      setFormErr(interpretError(e));
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
      setTrustCardErr(interpretError(e));
    } finally {
      setTrustBusy(false);
    }
  }, [base, orgOk, o, plane]);

  useEffect(() => {
    if (offlineDemoSurface) return;
    void refreshTrustCenter();
  }, [refreshTrustCenter, offlineDemoSurface]);

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
      setTrustCardErr(interpretError(e));
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

  /**
   * Any in-flight request, as one value.
   *
   * The same eight-way disjunction was written out at three call sites and
   * had already drifted at one of them, so a card could offer an action while
   * another request was still running against the same organization.
   */
  const anyBusy =
    orgBusy ||
    sparkBusy ||
    nofoBusy ||
    scoreBusy ||
    pursuitBusy ||
    formBusy ||
    trustBusy ||
    runnerBusy;

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

  /**
   * Save the organization profile from the onboarding wizard.
   *
   * Returns whether it was written, so the wizard can show its success step
   * only when there is something to succeed about. A wizard that advances on
   * a failed save is a wizard that tells the customer their organization is
   * set up when it is not.
   */
  const onSaveProfile = useCallback(
    async (body: Record<string, unknown>): Promise<boolean> => {
      if (!orgOk) return false;
      setOrgBusy(true);
      setOrgErr(null);
      try {
        const { profile } = await createOrUpdateTribalProfile(base, plane, o, body);
        setProfileRecord(profile);
        return true;
      } catch (e) {
        setOrgErr(interpretError(e));
        return false;
      } finally {
        setOrgBusy(false);
      }
    },
    [base, orgOk, plane, o],
  );

  /**
   * Read a notice and load what came out of it, as one action.
   *
   * Extraction and requirement loading were two separate buttons, and a
   * customer who pressed only the first saw an empty checklist and concluded
   * the notice had no requirements - the exact inference the evidence rules
   * exist to prevent.
   */
  const onExtractAndLoad = useCallback(async () => {
    if (!sparkSelected) return;
    setNofoBusy(true);
    setNofoErr(null);
    try {
      await postNofoExtractStub(base, plane, o, sparkId.trim());
      const [reqs, latest] = await Promise.all([
        getNofoRequirements(base, plane, o, sparkId.trim()),
        getNofoLatest(base, plane, o, sparkId.trim()),
      ]);
      setRequirements(reqs.requirements ?? []);
      setNofoLatest(latest);
    } catch (e) {
      setNofoErr(interpretError(e));
    } finally {
      setNofoBusy(false);
    }
  }, [base, o, plane, sparkId, sparkSelected]);

  /**
   * Read the stored notice for contacts and a submission route.
   *
   * Separate from requirement extraction rather than folded into it: a
   * customer often wants to know who to ask before deciding to work the
   * checklist, and the two reads answer different questions.
   */
  const onExtractApplyPath = useCallback(async () => {
    if (!sparkSelected) return;
    setApplyBusy(true);
    try {
      await extractApplyPath(base, plane, o, sparkId.trim());
      setApplyPath(await getApplyPath(base, plane, o, sparkId.trim()));
    } catch (e) {
      setNofoErr(interpretError(e));
    } finally {
      setApplyBusy(false);
    }
  }, [base, o, plane, sparkId, sparkSelected]);

  /**
   * Create an opportunity the customer already had.
   *
   * Goes through the ordinary create endpoint, so what comes out is an
   * opportunity like any other - the same detail page, the same documents,
   * the same pursuit. `source: "manual"` records where it came from without
   * putting it anywhere different.
   *
   * When the customer pasted the notice, its contacts and submission route
   * are extracted immediately: that is the answer they came for, and making
   * them press a second button for it would be a strange way to deliver it.
   */
  const onCreateIntake = useCallback(
    async (draft: IntakeDraft): Promise<string | null> => {
      if (!orgOk) return null;
      setSparkBusy(true);
      setSparkErr(null);
      try {
        const row = await createGrantSpark(base, plane, o, draftToCreateBody(draft));
        const id = str(row.id);
        setSparkId(id);
        setSparkDetail(row);
        await loadSparksAndDetail();
        if (draft.noticeText.trim()) {
          await extractApplyPath(base, plane, o, id).catch(() => null);
          setApplyPath(await getApplyPath(base, plane, o, id).catch(() => null));
        }
        return id;
      } catch (e) {
        setSparkErr(interpretError(e));
        return null;
      } finally {
        setSparkBusy(false);
      }
    },
    [base, loadSparksAndDetail, orgOk, o, plane],
  );

  const onSignOut = useCallback(async () => {
    await signOut(base);
    setSession({ authenticated: false, organizationId: null });
    setSurface("sign_in");
  }, [base, setSurface]);

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

  if (surface === "sign_in") {
    return (
      // No "continue to the demo workspace" link. It went to a workspace that
      // cannot load anything without a session and would have bounced the
      // visitor straight back here - an escape hatch that escapes nowhere.
      <SignInPage notice={authNotice} />
    );
  }

  if (surface === "onboarding") {
    return (
      <OnboardingPage
        busy={orgBusy}
        error={orgErr}
        onSubmit={onSaveProfile}
        onEnterWorkspace={() => setSurface("workspace")}
        initial={
          profileFields
            ? {
                legal_name: profileFields.legalName,
                entity_type: profileFields.entityType,
                city: profileFields.city,
                state: profileFields.state,
              }
            : undefined
        }
      />
    );
  }

  return (
    <AppShell
      surface={surface}
      onSurfaceChange={setSurface}
      organization={profileFields?.legalName ?? null}
      // The shell speaks in customer terms. "real" is the internal plane
      // name; a customer is in their live organization or in the demo.
      environment={plane === "demo" ? "demo" : "live"}
      onEnvironmentChange={(next) => setPlane(next === "demo" ? "demo" : "real")}
      // null means "not checked yet", which is not the same as unreachable.
      // Treating unknown as offline would flash a failure banner on load.
      online={backendOk !== false}
      offlineHint={backendHint}
      attention={{ trust: trustErr, organization: Boolean(orgErr) }}
      // The account menu is about a person, and the organization's name was
      // standing in for one - so a signed-in user saw their Tribe's name in
      // an avatar circle, which reads as being logged in as the organization.
      // `/api/auth/session` reports no display name or email today, so the
      // menu says "Account" rather than naming the wrong thing.
      account={session?.authenticated ? { name: "Account" } : null}
      onSignIn={() => setSurface("sign_in")}
      onSignOut={onSignOut}
      topBarExtra={
        <>
          {/* The Trust manifest's schema version used to be printed here as
              "Trust ml2_trust_v1". It is an internal identifier, it told a
              customer nothing, and it sat in the most prominent chrome in the
              product. The Trust page reports the manifest in its own terms. */}
          <button
            type="button"
            className="nf-btn nf-btn-ghost"
            onClick={() => void refreshConnectivity()}
          >
            Refresh
          </button>
        </>
      }
    >

      {surface === "workspace" ? (
      <WorkspacePage
        organizationName={profileFields?.legalName ?? null}
        entityType={profileFields?.entityType ?? null}
        identityVerified={false}
        hasProfile={hasProfile}
        steps={progressSteps}
        sparks={sparks}
        selectedSparkId={sparkId}
        onSelectSpark={setSparkId}
        requirementsCount={requirements.length}
        reviewSummary={reviewSummary}
        score={score}
        pursuit={pursuit}
        formPackage={formPkg}
        trustVersion={trustVersion}
        auditCount={auditCount}
        nextHeadline={whatsNext.headline}
        nextDetail={whatsNext.detail}
        nextActionLabel={whatsNext.primaryLabel}
        onNextAction={runPrimaryNext}
        busy={anyBusy}
        onGoTo={setSurfaceByNav}
        aside={
          <>
            <WhatsNextCard
              headline={whatsNext.headline}
              detail={whatsNext.detail}
              primaryLabel={whatsNext.primaryLabel}
              onPrimary={runPrimaryNext}
              busy={anyBusy}
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
          </>
        }
        workflow={
          <>
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
          </>
        }
      />
      ) : surface === "discover" ? (
        <DiscoverPage
          trackedCount={sparks.length}
          onGoToOpportunities={() => setSurface("opportunities")}
          onAddDemo={() => void onCreateDemoSpark()}
          canAdd={hasProfile && !anyBusy}
        />
      ) : surface === "add_opportunity" ? (
        <AddOpportunityPage
          tracked={sparks}
          busy={sparkBusy}
          error={sparkErr}
          onCreate={onCreateIntake}
          onOpenExisting={(id) => {
            setSparkId(id);
            setSurface("documents");
          }}
          onCancel={() => setSurface("opportunities")}
        />
      ) : surface === "opportunities" ? (
        <OpportunitiesPage
          sparks={sparks}
          selectedSparkId={sparkId}
          onSelectSpark={setSparkId}
          onOpenSpark={(id) => {
            setSparkId(id);
            setSurface("documents");
          }}
          busy={sparkBusy}
          error={sparkErr}
          onRefresh={() => void loadSparksAndDetail()}
          onAddDemo={() => void onCreateDemoSpark()}
          canAdd={hasProfile}
          addBlockedReason="Complete your organization profile first."
          onAddYourOwn={() => setSurface("add_opportunity")}
        />
      ) : surface === "documents" ? (
        <DocumentsPage
          opportunityTitle={
            sparkDetail ? str(sparkDetail.opportunity_title) || null : null
          }
          sparkSelected={sparkSelected}
          requirements={requirements}
          extraction={nofoLatest}
          busy={nofoBusy}
          error={nofoErr}
          onExtract={() => void onExtractAndLoad()}
          onReload={() => void onLoadRequirements()}
          onGoToOpportunities={() => setSurface("opportunities")}
          applyPath={applyPath as never}
          applyBusy={applyBusy}
          onExtractApplyPath={() => void onExtractApplyPath()}
        />
      ) : surface === "pursuits" ? (
        <PursuitsPage
          pursuit={pursuit}
          opportunityTitle={
            sparkDetail ? str(sparkDetail.opportunity_title) || null : null
          }
          score={score}
          formPackage={formPkg}
          busy={pursuitBusy || formBusy}
          error={pursuitErr ?? formErr}
          canOpen={hasScore}
          deadlineDays={daysUntil(str(sparkDetail?.application_deadline))}
          onOpenPursuit={() => void onOpenPursuit()}
          onToggleTask={(id, status) => void onToggleTask(id, status)}
          onRefresh={() => void onRefreshPursuit()}
          onCreateFormPackage={() => void onCreateFormPackage()}
          onGoToOpportunities={() => setSurface("opportunities")}
        />
      ) : surface === "trust" ? (
        <TrustPage
          manifest={trustManifest}
          auditCount={auditCount}
          reviewSummary={reviewSummary}
          exportHint={exportHint}
          busy={trustBusy}
          error={trustCardErr}
          onRefresh={() => void refreshTrustCenter()}
          onExport={() => void onExportDownload()}
        />
      ) : surface === "organization" ? (
        <OrganizationPage
          profile={profileRecord}
          identityVerified={Boolean(session?.authenticated)}
          busy={orgBusy}
          error={orgErr}
          onEditProfile={() => setSurface("onboarding")}
          onRefresh={() => void loadProfile()}
        />
      ) : surface === "settings" ? (
        <SettingsPage
          environment={plane === "demo" ? "demo" : "live"}
          onEnvironmentChange={(next) => setPlane(next === "demo" ? "demo" : "real")}
          organizationId={orgId}
          onOrganizationIdChange={setOrgId}
          organizationIdValid={orgOk}
          onOpen={(view) => setSurface(view as AppSurface)}
          onSignOut={session?.authenticated ? onSignOut : undefined}
        />
      ) : surface === "workbench" ? (
        <WorkbenchPage plane={plane} orgId={orgId.trim()} orgOk={orgOk} />
      ) : surface === "nm_wa_operator_demo" ? (
        <NmWaOperatorDemoPage />
      ) : surface === "sc_customer_demo" ? (
        <ScCustomerDemoPage />
      ) : surface === "beta_onboarding_cockpit" ? (
        <BetaOnboardingCockpitPage orgId={orgId.trim()} />
      ) : (
        <ActivationPage
          plane={plane}
          orgId={orgId.trim()}
          orgOk={orgOk}
          actorId={actorId}
        />
      )}

      {/* Settings only. "Advanced · Operator" sat at the bottom of every
          customer page - Workspace, Documents, Trust - offering to run an
          internal demo sequence. A control whose own subtitle says it is "not
          part of the grant workflow" does not belong on seven pages that are.
          It is still one click away, from the page that collects the other
          operator surfaces. */}
      {surface === "settings" ? (
        <OperatorTools
          open={operatorOpen}
          onToggle={() => setOperatorOpen((v) => !v)}
          runnerBusy={runnerBusy}
          runnerSteps={runnerSteps}
          orgOk={orgOk}
          onRunSequence={runLiveSequence}
        />
      ) : null}

      <p className="nf-footnote">
        NativeForge does not submit to Grants.gov. Previews are for internal
        review only.
      </p>
    </AppShell>
  );
}

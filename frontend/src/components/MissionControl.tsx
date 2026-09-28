import { useMemo, useState } from "react";

import { EmptyState } from "./StateView";
import {
  MetricCard,
  MetricRow,
  Section,
  StatusBadge,
  type BadgeTone,
} from "./ui/primitives";

export interface MissionWorkItem {
  id: string;
  kind: string;
  attention: string;
  title: string;
  detail: string | null;
  explanation: string;
  pursuit_id: string;
  grant_spark_id: string;
  opportunity_title: string;
  funder: string;
  stage_id: string | null;
  status: string | null;
  due_at: string | null;
  days: number | null;
  owner_membership_id: string | null;
  owner_label: string | null;
  view: string;
}

export interface MissionControlPayload {
  schema_version: string;
  viewer_membership_id: string | null;
  metrics: {
    active_pursuits: number;
    open_work: number;
    blocked: number;
    overdue: number;
    due_this_week: number;
    awaiting_response: number;
    needs_review: number;
  };
  next: MissionWorkItem | null;
  open_work: MissionWorkItem[];
  active_pursuits: {
    pursuit_id: string;
    grant_spark_id: string;
    title: string;
    funder: string;
    deadline: string | null;
    current_stage_id: string | null;
    next_action: { headline: string; detail: string; view: string | null };
    open_count: number;
    blocked_count: number;
    overdue_count: number;
    stalled: boolean;
    stalled_reason: string | null;
  }[];
  blockers: MissionWorkItem[];
  waiting: MissionWorkItem[];
  reviews: MissionWorkItem[];
  deadlines: {
    kind: string;
    label: string;
    occurs_at: string | null;
    bucket: string | null;
    opportunity_title: string;
  }[];
  recently_completed: {
    id: string;
    title: string;
    completed_at: string | null;
    opportunity_title: string;
  }[];
  empty: boolean;
  caught_up: boolean;
  next_deadline: { label: string; occurs_at: string | null } | null;
}

const FILTERS = [
  { id: "all", label: "All" },
  { id: "blocked", label: "Blocked" },
  { id: "overdue", label: "Overdue" },
  { id: "due_soon", label: "Due soon" },
  { id: "waiting", label: "Waiting" },
  { id: "review", label: "Review" },
  { id: "mine", label: "My work" },
  { id: "unassigned", label: "Unassigned" },
] as const;

const TONE: Record<string, BadgeTone> = {
  blocked: "bad",
  overdue: "warn",
  due_soon: "warn",
  needs_review: "info",
  waiting: "neutral",
  in_progress: "info",
  ready: "muted",
};

function matches(
  item: MissionWorkItem,
  filter: string,
  viewer: string | null,
): boolean {
  if (filter === "all") return true;
  if (filter === "blocked") return item.attention === "blocked";
  if (filter === "overdue") return item.attention === "overdue";
  if (filter === "due_soon") return item.attention === "due_soon";
  if (filter === "waiting") return item.kind === "follow_up";
  if (filter === "review") return item.kind === "review";
  if (filter === "mine") return Boolean(viewer && item.owner_membership_id === viewer);
  if (filter === "unassigned") return !item.owner_membership_id && !item.owner_label;
  return true;
}

export function MissionControl(props: {
  data: MissionControlPayload | null;
  onGoTo: (view: string) => void;
  onOpenOpportunity: (sparkId: string) => void;
}) {
  const { data, onGoTo, onOpenOpportunity } = props;
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["id"]>("all");
  const items = useMemo(() => {
    if (!data) return [];
    return data.open_work.filter((item) =>
      matches(item, filter, data.viewer_membership_id),
    );
  }, [data, filter]);

  if (!data) return null;

  return (
    <div className="nf-mission">
      <Section
        title="Mission Control"
        lead="Everything this organization is pursuing, from persisted work — not a second task list."
      >
        {data.empty ? (
          <EmptyState
            title="No active pursuits yet."
            body="Discovered opportunities stay in the database until you start a pursuit. NativeForge will not invent progress."
            actionLabel="Find an opportunity"
            onAction={() => onGoTo("opportunities")}
            inline
          />
        ) : null}

        {data.caught_up ? (
          <p className="nf-command-next">
            You're caught up.
            {data.next_deadline?.occurs_at
              ? ` Next deadline is ${data.next_deadline.label} (${data.next_deadline.occurs_at.slice(0, 10)}).`
              : " No authoritative deadline is on file."}
          </p>
        ) : null}

        <MetricRow>
          <MetricCard
            label="Active pursuits"
            value={String(data.metrics.active_pursuits)}
            onClick={() => setFilter("all")}
          />
          <MetricCard
            label="Open work"
            value={String(data.metrics.open_work)}
            onClick={() => setFilter("all")}
          />
          <MetricCard
            label="Blocked"
            value={String(data.metrics.blocked)}
            tone={data.metrics.blocked ? "bad" : "muted"}
            onClick={() => setFilter("blocked")}
          />
          <MetricCard
            label="Overdue"
            value={String(data.metrics.overdue)}
            tone={data.metrics.overdue ? "warn" : "muted"}
            onClick={() => setFilter("overdue")}
          />
          <MetricCard
            label="Due this week"
            value={String(data.metrics.due_this_week)}
            onClick={() => setFilter("due_soon")}
          />
          <MetricCard
            label="Waiting"
            value={String(data.metrics.awaiting_response)}
            onClick={() => setFilter("waiting")}
          />
          <MetricCard
            label="Needs review"
            value={String(data.metrics.needs_review)}
            onClick={() => setFilter("review")}
          />
        </MetricRow>
      </Section>

      {data.next && !data.caught_up && !data.empty ? (
        <Section title="What you should do next" lead={data.next.explanation}>
          <p className="nf-command-next">{data.next.title}</p>
          <p className="nf-note">
            {data.next.opportunity_title} · {data.next.funder}
            {data.next.due_at ? ` · ${data.next.due_at.slice(0, 10)}` : ""}
          </p>
          <button
            type="button"
            className="nf-btn nf-btn-primary nf-btn-sm"
            onClick={() => {
              onOpenOpportunity(data.next!.grant_spark_id);
              onGoTo(data.next!.view);
            }}
          >
            Open that work
          </button>
        </Section>
      ) : null}

      {!data.empty ? (
        <Section
          title="Open work"
          lead="Blocked, overdue, waiting, and ready work across every active pursuit."
        >
          <div className="nf-mission-filters">
            {FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                className="nf-btn nf-btn-ghost nf-btn-sm"
                data-active={filter === f.id}
                onClick={() => setFilter(f.id)}
              >
                {f.label}
              </button>
            ))}
          </div>
          {items.length === 0 ? (
            <p className="nf-note">Nothing in this filter.</p>
          ) : (
            <ul className="nf-command-list">
              {items.slice(0, 20).map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className="nf-mission-item"
                    onClick={() => {
                      onOpenOpportunity(item.grant_spark_id);
                      onGoTo(item.view);
                    }}
                  >
                    <StatusBadge tone={TONE[item.attention] || "muted"}>
                      {item.attention.replace("_", " ")}
                    </StatusBadge>{" "}
                    <strong>{item.title}</strong>
                    <span className="nf-note">
                      {" "}
                      {item.opportunity_title} · {item.explanation}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Section>
      ) : null}

      {data.active_pursuits.length > 0 ? (
        <Section title="What we have started" lead="Each pursuit keeps its own workflow state.">
          <ul className="nf-command-list">
            {data.active_pursuits.map((p) => (
              <li key={p.pursuit_id}>
                <button
                  type="button"
                  className="nf-mission-item"
                  onClick={() => {
                    onOpenOpportunity(p.grant_spark_id);
                    onGoTo("pursuits");
                  }}
                >
                  <strong>{p.title}</strong>
                  <span className="nf-note">
                    {" "}
                    {p.funder}
                    {p.deadline ? ` · due ${p.deadline.slice(0, 10)}` : ""}
                    {p.current_stage_id ? ` · ${p.current_stage_id}` : ""}
                    {p.blocked_count ? ` · ${p.blocked_count} blocked` : ""}
                    {p.stalled && p.stalled_reason ? ` · ${p.stalled_reason}` : ""}
                  </span>
                  <p className="nf-note">{p.next_action.headline}</p>
                </button>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {data.recently_completed.length > 0 ? (
        <Section title="Recently completed" lead="Why work left the queue.">
          {data.recently_completed.map((item) => (
            <p key={item.id} className="nf-note">
              {item.title} — {item.opportunity_title}
              {item.completed_at ? ` · ${item.completed_at.slice(0, 10)}` : ""}
            </p>
          ))}
        </Section>
      ) : null}
    </div>
  );
}

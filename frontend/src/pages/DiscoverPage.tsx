import { StateView } from "../components/StateView";
import {
  MetricCard,
  MetricRow,
  PageHeader,
  Section,
  StatusBadge,
} from "../components/ui/primitives";

/**
 * Discover: where funding will come from, and where it comes from today.
 *
 * ## Why this page does not list opportunities
 *
 * NativeForge's source collectors are built and deliberately not activated.
 * No collector has fetched from Grants.gov, SAM, BIA, IHS or anywhere else,
 * so there is no discovered inventory to show. The honest options were to
 * hide the page, to fill it with sample rows, or to say so.
 *
 * Sample rows were the tempting one and would have been the worst: a buyer
 * looking at a list of plausible federal opportunities has no way to tell
 * that NativeForge did not find them, and every later number they see would
 * inherit that assumption.
 *
 * So the page states the position, names the sources the engine is built
 * against, and points at the one path that does work today - tracking an
 * opportunity you already know about. When collection is switched on, the
 * discovered inventory belongs here and nothing else on this page has to
 * change.
 */

const SOURCES: Array<{ name: string; detail: string }> = [
  { name: "Grants.gov", detail: "Federal discretionary opportunity announcements" },
  { name: "SAM.gov assistance listings", detail: "Assistance listings and program data" },
  { name: "Bureau of Indian Affairs", detail: "BIA program announcements" },
  { name: "Indian Health Service", detail: "IHS funding announcements" },
  { name: "Administration for Native Americans", detail: "ANA program announcements" },
  { name: "COPS Tribal Access (CTAS)", detail: "Coordinated Tribal Assistance Solicitation" },
  { name: "HUD", detail: "Indian Housing Block Grant and competitive programs" },
  { name: "USDA Rural Development", detail: "Rural and Tribal infrastructure programs" },
];

export interface DiscoverPageProps {
  trackedCount: number;
  onGoToOpportunities: () => void;
  onAddDemo: () => void;
  canAdd: boolean;
}

export function DiscoverPage(props: DiscoverPageProps) {
  const { trackedCount, onGoToOpportunities, onAddDemo, canAdd } = props;

  return (
    <div className="nf-page">
      <PageHeader
        eyebrow="Find funding"
        title="Discover"
        lead="Where NativeForge looks for funding your organization can actually win."
        actions={
          <button
            type="button"
            className="nf-btn nf-btn-secondary nf-btn-sm"
            onClick={onGoToOpportunities}
          >
            View tracked opportunities
          </button>
        }
      />

      <StateView
        state={{
          tone: "blocked",
          title: "Automatic discovery is not switched on",
          body: "NativeForge's source collectors are built but have not been authorized to run against live federal sources. Until they are, this page shows no discovered opportunities rather than examples — a list you cannot distinguish from real findings would be worse than an empty one.",
          actionLabel: canAdd ? "Track an opportunity instead" : undefined,
        }}
        onAction={canAdd ? onAddDemo : undefined}
        secondary={
          <button type="button" className="nf-btn nf-btn-ghost" onClick={onGoToOpportunities}>
            Open Opportunities
          </button>
        }
      />

      <Section title="Current position" lead="Measured, not projected.">
        <MetricRow>
          <MetricCard
            label="Sources collecting"
            value="0"
            tone="muted"
            note="No collector has been authorized to run"
          />
          <MetricCard
            label="Opportunities discovered"
            value="0"
            tone="muted"
            note="Nothing has been fetched"
          />
          <MetricCard
            label="Opportunities tracked"
            value={String(trackedCount)}
            tone={trackedCount > 0 ? "positive" : "muted"}
            onClick={onGoToOpportunities}
            note="Added by you"
          />
          <MetricCard
            label="Last collection run"
            value="—"
            tone="muted"
            note="Never run"
          />
        </MetricRow>
      </Section>

      <Section
        title="Sources NativeForge is built against"
        lead="The ingestion path for each of these exists. None is authorized to run."
      >
        <ul className="nf-source-list">
          {SOURCES.map((s) => (
            <li key={s.name} className="nf-source">
              <div>
                <p className="nf-source-name">{s.name}</p>
                <p className="nf-source-detail">{s.detail}</p>
              </div>
              <StatusBadge tone="muted">Not activated</StatusBadge>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}

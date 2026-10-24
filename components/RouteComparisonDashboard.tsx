"use client";

import { CompareRoutesResponse, RouteAlternative, RouteMetrics } from "@/lib/api";
import { gapSentence, phaseSentence } from "@/lib/moonbaseDisplay";

interface RouteComparisonDashboardProps {
  comparison: CompareRoutesResponse | null;
  loading: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

const NASA_COLUMNS: {
  label: string;
  value: (metrics: RouteMetrics) => string;
}[] = [
  {
    label: "Shadow",
    value: (metrics) =>
      metrics.shadow_fraction == null ? "—" : `${(metrics.shadow_fraction * 100).toFixed(0)}%`,
  },
  {
    label: "PSR",
    value: (metrics) =>
      metrics.psr_fraction == null ? "—" : `${(metrics.psr_fraction * 100).toFixed(0)}%`,
  },
  {
    label: "Comms",
    value: (metrics) =>
      metrics.comms_gap_fraction == null
        ? "—"
        : `${(metrics.comms_gap_fraction * 100).toFixed(0)}%`,
  },
  {
    label: "Power",
    value: (metrics) =>
      metrics.power_margin_m == null ? "—" : `${metrics.power_margin_m.toLocaleString()} m`,
  },
  {
    label: "Keep-out",
    value: (metrics) => (metrics.enters_keepout ? "Entered" : "Clear"),
  },
];

const SCORE_CHIPS: { key: keyof RouteAlternative["scores"]; label: string }[] = [
  { key: "safety", label: "Safety" },
  { key: "time", label: "Time" },
  { key: "slope", label: "Slope" },
  { key: "distance", label: "Distance" },
  { key: "energy", label: "Energy" },
];

function Chip({
  label,
  value,
  best = false,
  warn = false,
}: {
  label: string;
  value: string;
  best?: boolean;
  warn?: boolean;
}) {
  return (
    <span className={`compare-chip${best ? " compare-chip-best" : ""}${warn ? " compare-chip-warn" : ""}`}>
      <span className="compare-chip-label">{label}</span>
      <span className="compare-chip-value">
        {value}
        {best && <span className="compare-star" aria-label="Best"> ★</span>}
      </span>
    </span>
  );
}

export default function RouteComparisonDashboard({
  comparison,
  loading,
  selectedId,
  onSelect,
}: RouteComparisonDashboardProps) {
  const alternatives = comparison?.alternatives ?? [];
  const bestBy = comparison?.best_by_metric ?? {};

  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <h2>Route Comparison</h2>
          <p className="panel-subtitle">
            Astrolab vs Pegasus vs a Safest path — click a route to view it.
          </p>
        </div>
      </div>

      <p className="compare-intro">
        Column scores are scaled 60–100 within each comparison so alternatives are
        easier to compare. Overall uses TOPSIS. With a Moon Base mission selected,
        that score also weighs shadow, PSR access, comms gaps, power margin, and
        keep-outs. ★ marks the best value per column.
      </p>
      {comparison?.moonbase && (
        <p className="control-hint">
          {phaseSentence(comparison.moonbase.phase)}{" "}
          {gapSentence(comparison.moonbase.functional_gaps)}
        </p>
      )}

      {!comparison && !loading && (
        <div className="empty-state empty-state-compact">
          <p>No comparison yet.</p>
          <p className="empty-state-hint">
            Use <strong>Compare rovers</strong> in the panel after placing A and B.
          </p>
        </div>
      )}

      {loading && (
        <p className="loading">Comparing rover routes…</p>
      )}

      {comparison && (
        <>
          {bestBy.overall && (
            <div className="compare-recommended">
              Recommended:{" "}
              <strong>
                {alternatives.find((a) => a.id === bestBy.overall)?.label}
              </strong>
              {" "}
              (
              {alternatives.find((a) => a.id === bestBy.overall)?.scores.overall}
              /100 overall)
            </div>
          )}

          <div className="compare-cards">
            {alternatives.map((alt) => {
              const isSelected = selectedId === alt.id;
              const isRecommended = bestBy.overall === alt.id;
              const found = alt.route_found;

              return (
                <div
                  key={alt.id}
                  className={`compare-card${isSelected ? " compare-card-selected" : ""}${
                    !found ? " compare-card-failed" : ""
                  }`}
                  onClick={() => found && onSelect(alt.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      if (found) onSelect(alt.id);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                >
                  <div className="compare-card-head">
                    <span
                      className="compare-color-dot"
                      style={{ background: alt.color }}
                      aria-hidden="true"
                    />
                    <span className="compare-card-title">
                      {alt.label}
                      {isRecommended && <span className="compare-badge">Best</span>}
                    </span>
                    <span className="compare-sub">
                      {alt.rover_name}
                      {alt.id === "safest" && ` · avoidance ${alt.hazard_weight}`}
                    </span>
                    <span className={`compare-overall${isRecommended && found ? " compare-chip-best" : ""}`}>
                      {found ? alt.scores.overall.toFixed(1) : "—"}
                      <span className="compare-chip-label"> overall</span>
                    </span>
                    {!found && <span className="compare-fail">No route</span>}
                  </div>
                  <div className="compare-chips">
                    {SCORE_CHIPS.map(({ key, label }) => (
                      <Chip
                        key={label}
                        label={label}
                        value={found ? alt.scores[key].toFixed(1) : "—"}
                        best={found && bestBy[key] === alt.id}
                      />
                    ))}
                    <Chip
                      label="Dist"
                      value={found ? `${alt.metrics.distance_m.toLocaleString()} m` : "—"}
                    />
                    <Chip
                      label="Min"
                      value={found ? `${alt.metrics.estimated_time_min.toFixed(1)}` : "—"}
                    />
                    <Chip
                      label="Hazard"
                      value={found ? alt.metrics.average_hazard_score.toFixed(4) : "—"}
                    />
                    <Chip
                      label="Range"
                      value={
                        found
                          ? `${alt.metrics.distance_m.toLocaleString()} / ${alt.metrics.max_range_m.toLocaleString()} m`
                          : "—"
                      }
                      warn={found && alt.metrics.range_exceeded}
                    />
                  </div>
                  {comparison.moonbase && (
                    <div className="compare-chips compare-chips-nasa">
                      {NASA_COLUMNS.map((column) => (
                        <Chip
                          key={column.label}
                          label={column.label}
                          value={found ? column.value(alt.metrics) : "—"}
                        />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="compare-legend">
            {alternatives
              .filter((a) => a.route_found)
              .map((a) => (
                <span key={a.id} className="compare-legend-item">
                  <span
                    className="compare-color-dot"
                    style={{ background: a.color }}
                    aria-hidden="true"
                  />
                  {a.label}
                </span>
              ))}
          </div>
        </>
      )}
    </div>
  );
}

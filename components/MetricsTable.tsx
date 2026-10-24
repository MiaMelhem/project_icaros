"use client";

import { RouteMetrics } from "@/lib/api";

interface MetricsTableProps {
  metrics: RouteMetrics | null;
  routeFound: boolean;
  validationMessage?: string;
  subtitle?: string;
  compact?: boolean;
}

const METRIC_DEFS = [
  { key: "distance", label: "Distance", unit: "m", format: (v: number) => v.toLocaleString() },
  { key: "time", label: "Est. Time", unit: "min", format: (v: number) => v.toFixed(1) },
  { key: "maxSlope", label: "Max Slope", unit: "°", format: (v: number) => v.toFixed(1) },
  { key: "avgSlope", label: "Avg Slope", unit: "°", format: (v: number) => v.toFixed(1) },
  { key: "hazard", label: "Raw Hazard", unit: "", format: (v: number) => v.toFixed(4) },
  { key: "energy", label: "Energy", unit: "", format: (v: number) => v.toLocaleString() },
] as const;

function getMetricValue(key: string, metrics: RouteMetrics): number {
  switch (key) {
    case "distance": return metrics.distance_m;
    case "time": return metrics.estimated_time_min;
    case "maxSlope": return metrics.max_slope_deg;
    case "avgSlope": return metrics.average_slope_deg;
    case "hazard": return metrics.average_hazard_score;
    case "energy": return metrics.energy_score;
    default: return 0;
  }
}

function RangeMetric({ metrics }: { metrics: RouteMetrics }) {
  const usedPct =
    metrics.max_range_m > 0
      ? Math.round((metrics.distance_m / metrics.max_range_m) * 100)
      : 0;

  return (
    <div
      className={`metrics-range-item${metrics.range_exceeded ? " metrics-range-exceeded" : ""}`}
    >
      <span className="metrics-strip-label">Travel range</span>
      <span className="metrics-strip-value">
        {metrics.distance_m.toLocaleString()} / {metrics.max_range_m.toLocaleString()} m
        <span className="metric-unit"> ({usedPct}%)</span>
      </span>
      {metrics.range_exceeded && (
        <span className="metrics-range-warning">Exceeds rover max travel range</span>
      )}
    </div>
  );
}

export default function MetricsTable({
  metrics,
  routeFound,
  validationMessage,
  subtitle,
  compact = false,
}: MetricsTableProps) {
  const title = subtitle ? `Route Metrics · ${subtitle}` : "Route Metrics";

  if (!metrics) {
    if (compact) return null;
    return (
      <div className="panel">
        <div className="panel-header">
          <h2>{title}</h2>
        </div>
        <p className="loading">No route computed yet.</p>
      </div>
    );
  }

  if (!routeFound) {
    if (compact) return null;
    return (
      <div className="panel">
        <div className="panel-header">
          <h2>{title}</h2>
        </div>
        <p className="error">
          {validationMessage ??
            "No route found. Try adjusting start/goal or terrain avoidance."}
        </p>
      </div>
    );
  }

  if (compact) {
    return (
      <>
        <div className="metrics-strip">
          {METRIC_DEFS.map(({ key, label, unit, format }) => (
            <div key={key} className="metrics-strip-item">
              <span className="metrics-strip-label">{label}</span>
              <span className="metrics-strip-value">
                {format(getMetricValue(key, metrics))}
                {unit && <span className="metric-unit">{unit}</span>}
              </span>
            </div>
          ))}
          <RangeMetric metrics={metrics} />
        </div>
        <ArchitectureMetrics metrics={metrics} />
      </>
    );
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>{title}</h2>
      </div>
      <div className="metrics-grid">
        {METRIC_DEFS.map(({ key, label, unit, format }) => (
          <div key={key} className="metric-card">
            <div className="metric-label">{label}</div>
            <div className="metric-value">
              {format(getMetricValue(key, metrics))}
              {unit && <span className="metric-unit">{unit}</span>}
            </div>
          </div>
        ))}
        <div
          className={`metric-card${metrics.range_exceeded ? " metric-card-warning" : ""}`}
        >
          <div className="metric-label">Travel range</div>
          <div className="metric-value">
            {metrics.distance_m.toLocaleString()} / {metrics.max_range_m.toLocaleString()}
            <span className="metric-unit">m</span>
          </div>
          {metrics.range_exceeded && (
            <p className="metric-warning">Exceeds rover max travel range</p>
          )}
        </div>
      </div>
      <ArchitectureMetrics metrics={metrics} />
    </div>
  );
}

function ArchitectureMetrics({ metrics }: { metrics: RouteMetrics }) {
  if (metrics.shadow_fraction == null) return null;
  return (
    <div className="metrics-strip moonbase-metrics">
      <div className="metrics-strip-item">
        <span className="metrics-strip-label">Shadow</span>
        <span className="metrics-strip-value">
          {(metrics.shadow_fraction * 100).toFixed(0)}%
        </span>
      </div>
      <div className="metrics-strip-item">
        <span className="metrics-strip-label">Dark time</span>
        <span className="metrics-strip-value">
          {(metrics.time_in_darkness_min ?? 0).toFixed(1)}
          <span className="metric-unit">min</span>
        </span>
      </div>
      <div className="metrics-strip-item">
        <span className="metrics-strip-label">PSR</span>
        <span className="metrics-strip-value">
          {((metrics.psr_fraction ?? 0) * 100).toFixed(0)}%
        </span>
      </div>
      <div className="metrics-strip-item">
        <span className="metrics-strip-label">Comms gap</span>
        <span className="metrics-strip-value">
          {((metrics.comms_gap_fraction ?? 0) * 100).toFixed(0)}%
        </span>
      </div>
      <div className="metrics-strip-item">
        <span className="metrics-strip-label">Power margin</span>
        <span className="metrics-strip-value">
          {(metrics.power_margin_m ?? 0).toLocaleString()}
          <span className="metric-unit">m</span>
        </span>
      </div>
      <div className="metrics-strip-item">
        <span className="metrics-strip-label">Cargo</span>
        <span className="metrics-strip-value">
          {(metrics.cargo_kg ?? 0).toLocaleString()}
          <span className="metric-unit">kg</span>
        </span>
      </div>
      <div className="metrics-strip-item">
        <span className="metrics-strip-label">Keep-out</span>
        <span className="metrics-strip-value">
          {metrics.enters_keepout ? "Entered" : "Clear"}
        </span>
      </div>
    </div>
  );
}

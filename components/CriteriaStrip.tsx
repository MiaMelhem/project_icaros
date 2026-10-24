"use client";

import { CriterionId, CriterionRow } from "@/lib/moonbaseDisplay";

interface CriteriaStripProps {
  phaseLine: string;
  missionLine: string;
  gaps: string;
  rows: CriterionRow[];
  enabled: Partial<Record<CriterionId, boolean>>;
  onToggle: (id: CriterionId) => void;
}

export default function CriteriaStrip({
  phaseLine,
  missionLine,
  gaps,
  rows,
  enabled,
  onToggle,
}: CriteriaStripProps) {
  return (
    <div className="criteria-strip">
      <div>
        <p className="criteria-phase">{phaseLine}</p>
        {missionLine && <p className="criteria-mission">{missionLine}</p>}
        <p className="criteria-mission">
          These chips are the rules drawn on the map. Click one to show or hide that layer.
        </p>
        {gaps && <p className="criteria-gaps">{gaps}</p>}
      </div>
      <div className="criteria-rows">
        {rows.map((row) => {
          const on = !row.spatial || enabled[row.id] !== false;
          if (!row.spatial) {
            return (
              <div key={row.id} className="criterion-chip criterion-chip-compact">
                <span className="criterion-swatch" style={{ background: row.swatch }} />
                <span className="criterion-label">{row.label}</span>
              </div>
            );
          }
          return (
            <button
              key={row.id}
              type="button"
              className={`criterion-chip criterion-chip-compact${on ? "" : " off"}`}
              aria-pressed={on}
              title={row.detail}
              onClick={() => onToggle(row.id)}
            >
              <span className="criterion-swatch" style={{ background: row.swatch }} />
              <span className="criterion-label">{row.label}</span>
            </button>
          );
        })}
      </div>
      <details className="criteria-details">
        <summary>What each color means</summary>
        <div className="criteria-detail-list">
          {rows.map((row) => (
            <p key={row.id}>
              <strong>{row.label}.</strong> {row.detail}
            </p>
          ))}
        </div>
      </details>
    </div>
  );
}

"use client";

import {
  MoonbaseCatalog,
  MoonbaseSettings,
  PickMode,
} from "@/lib/api";
import { PHASE_GUIDE, phaseSentence } from "@/lib/moonbaseDisplay";

const FALLBACK_MISSIONS = [
  { id: "landing_site", label: "Landing-site check", summary: "Check slope and plume keep-out.", phase_min: 1, functional_gaps: [] },
  { id: "reconnaissance", label: "Reconnaissance", summary: "Survey. PSR cells need a capable rover.", phase_min: 1, functional_gaps: [] },
  { id: "sunlit_traverse", label: "Sunlit traverse", summary: "Drive in sunlight. PSR cells are blocked.", phase_min: 1, functional_gaps: [] },
  { id: "psr_access", label: "PSR access", summary: "Enter a shadowed crater if the rover can.", phase_min: 1, functional_gaps: [] },
  { id: "cargo_reposition", label: "Cargo reposition", summary: "Move a few hundred kilograms in sunlight.", phase_min: 1, functional_gaps: [] },
  { id: "site_prep", label: "Site preparation", summary: "Reach a work area. Excavation is not simulated.", phase_min: 3, functional_gaps: [] },
  { id: "isru_prospecting", label: "ISRU prospecting", summary: "Prospect a shadowed crater. Grades are not invented.", phase_min: 3, functional_gaps: [] },
];

interface MoonbaseControlsProps {
  catalog: MoonbaseCatalog | null;
  settings: MoonbaseSettings;
  pickMode: PickMode;
  onChange: (settings: MoonbaseSettings) => void;
  onPickModeChange: (mode: PickMode) => void;
  part?: "phase" | "rules";
}

export default function MoonbaseControls({
  catalog,
  settings,
  onChange,
  part = "rules",
}: MoonbaseControlsProps) {
  const missions = (catalog?.missions ?? FALLBACK_MISSIONS).filter(
    (mission) => mission.phase_min <= settings.phase
  );
  const selected =
    missions.find((mission) => mission.id === settings.mission) ?? missions[0];

  function update(next: Partial<MoonbaseSettings>) {
    const merged = { ...settings, ...next };
    const allowed = (catalog?.missions ?? FALLBACK_MISSIONS).filter(
      (mission) => mission.phase_min <= merged.phase
    );
    if (allowed.length && !allowed.some((mission) => mission.id === merged.mission)) {
      merged.mission = "sunlit_traverse";
    }
    if (merged.phase < 3) merged.uncrewed = false;
    onChange(merged);
  }

  const needsPsr =
    settings.mission === "psr_access" ||
    settings.mission === "isru_prospecting" ||
    settings.mission === "reconnaissance";

  const phaseIds = (catalog?.phases.map((item) => item.id) ?? [1, 2, 3]) as Array<1 | 2 | 3>;

  if (part === "phase") {
    return (
      <section className="control-section moonbase-controls">
        <h2 className="control-section-title">1 · Phase</h2>
        <p className="control-section-help">
          Start here. This choice changes what the rest of the panel can do.
        </p>
        <label htmlFor="moonbase-phase">Moon Base phase</label>
        <select
          id="moonbase-phase"
          value={settings.phase}
          onChange={(event) =>
            update({ phase: Number(event.target.value) as 1 | 2 | 3 })
          }
        >
          {phaseIds.map((id) => (
            <option key={id} value={id}>
              {PHASE_GUIDE[id]?.short ?? `Phase ${id}`}
            </option>
          ))}
        </select>
        <p className="control-hint">
          {PHASE_GUIDE[settings.phase]?.detail ?? phaseSentence(settings.phase)}
        </p>
      </section>
    );
  }

  return (
    <section className="control-section moonbase-controls">
      <h2 className="control-section-title">6 · Mission rules</h2>
      <p className="control-section-help">
        These change where the rover may drive within the phase you picked.
      </p>

      <label htmlFor="moonbase-mission">What this drive is for</label>
      <select
        id="moonbase-mission"
        value={settings.mission}
        onChange={(event) => update({ mission: event.target.value })}
      >
        {missions.map((mission) => (
          <option key={mission.id} value={mission.id}>
            {mission.label}
          </option>
        ))}
      </select>
      {selected && <p className="control-hint">{selected.summary}</p>}

      <p className="control-section-help">Rover capabilities</p>
      <label className="moonbase-check" title="Lets this rover enter a permanently shadowed crater when the mission allows it. The slope limit does not change.">
        <input
          type="checkbox"
          checked={settings.psrCapable}
          onChange={(event) => update({ psrCapable: event.target.checked })}
        />
        Can drive in permanent shadow
      </label>
      {needsPsr && !settings.psrCapable && (
        <p className="control-hint">
          This mission stays out of shadow until you turn that on.
        </p>
      )}
      <label className="moonbase-check" title="A rover that can last 120 hours without sunlight barely pays extra energy for time in shadow.">
        <input
          type="checkbox"
          checked={settings.nightSurvival}
          onChange={(event) => update({ nightSurvival: event.target.checked })}
        />
        Can last 120 hours in the dark
      </label>
      <label htmlFor="moonbase-cargo">Cargo on the rover (kg)</label>
      <input
        id="moonbase-cargo"
        type="number"
        min={0}
        max={1000}
        value={settings.cargoKg}
        onChange={(event) => update({ cargoKg: Number(event.target.value) })}
      />
      <p className="control-hint">
        Heavier cargo costs more energy. 500 kg doubles that cost. Cargo reposition uses at least 200 kg.
      </p>

      {settings.phase >= 3 && (
        <label className="moonbase-check" title="This drive has no crew aboard.">
          <input
            type="checkbox"
            checked={settings.uncrewed}
            onChange={(event) => update({ uncrewed: event.target.checked })}
          />
          No crew on board
        </label>
      )}
    </section>
  );
}

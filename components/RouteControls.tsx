"use client";

import { useState } from "react";
import RoverSelector from "./RoverSelector";
import RoverCustomizer from "./RoverCustomizer";
import { LunarSite, PickMode, RoverConfig, TerrainMode } from "@/lib/api";
import { PresetRoverMode, RoverMode } from "@/lib/customRovers";

export interface RouteControlValues {
  terrainMode: TerrainMode;
  siteId: string;
  terrainSize: number;
  resolution: number;
  startRow: number;
  startCol: number;
  goalRow: number;
  goalCol: number;
  hazardWeight: number;
}

interface RouteControlsProps {
  roverMode: RoverMode;
  activeRoverConfig: RoverConfig;
  astrolabPreset?: RoverConfig;
  pegasusPreset?: RoverConfig;
  presetOverrides: Partial<Record<PresetRoverMode, RoverConfig>>;
  customRovers: RoverConfig[];
  selectedSavedCustomName: string;
  isRoverDirty: boolean;
  roverSaveMessage?: string | null;
  sites?: LunarSite[];
  values: RouteControlValues;
  pickMode: PickMode;
  onPickModeChange: (mode: PickMode) => void;
  onChange: (values: RouteControlValues) => void;
  onRoverModeChange: (mode: RoverMode) => void;
  onPresetConfigChange: (mode: PresetRoverMode, config: RoverConfig) => void;
  onResetPreset: (mode: PresetRoverMode) => void;
  onRoverConfigChange: (config: RoverConfig) => void;
  onLoadSavedCustom: (name: string) => void;
  onSaveCustomRover: () => void;
  onDeleteCustomRover: () => void;
  onRun: () => void;
  onCompare?: () => void;
  loading: boolean;
  compareLoading?: boolean;
  previewLoading: boolean;
  runDisabled?: boolean;
  compareDisabled?: boolean;
  demUpload?: React.ReactNode;
  beforeActions?: React.ReactNode;
  leading?: React.ReactNode;
}

export default function RouteControls({
  roverMode,
  activeRoverConfig,
  astrolabPreset,
  pegasusPreset,
  presetOverrides,
  customRovers,
  selectedSavedCustomName,
  isRoverDirty,
  roverSaveMessage,
  sites = [],
  values,
  pickMode,
  onPickModeChange,
  onChange,
  onRoverModeChange,
  onPresetConfigChange,
  onResetPreset,
  onRoverConfigChange,
  onLoadSavedCustom,
  onSaveCustomRover,
  onDeleteCustomRover,
  onRun,
  onCompare,
  loading,
  compareLoading = false,
  previewLoading,
  runDisabled = false,
  compareDisabled = false,
  demUpload,
  beforeActions,
  leading,
}: RouteControlsProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false);

  function update(field: keyof RouteControlValues, value: string | number) {
    onChange({ ...values, [field]: value });
  }

  function swapPoints() {
    onChange({
      ...values,
      startRow: values.goalRow,
      startCol: values.goalCol,
      goalRow: values.startRow,
      goalCol: values.startCol,
    });
  }

  const controlsBusy = loading || compareLoading || previewLoading;
  const actionsDisabled = controlsBusy || runDisabled;

  function avoidanceHint(weight: number): string {
    if (weight <= 0) return "Shortest path — terrain risk is mostly ignored.";
    if (weight < 5) return "Light avoidance — prefers shorter routes.";
    if (weight < 10) return "Balanced — some detours around steep or rough terrain.";
    if (weight < 15) return "Strong avoidance — longer routes to stay on safer ground.";
    return "Maximum avoidance — similar to the Safest compare option.";
  }

  return (
    <div className="panel panel-sidebar">
      <div className="control-stack">
        {leading}
        <section className="control-section">
          <h2 className="control-section-title">2 · Where</h2>
          <p className="control-section-help">
            Choose the ground. A catalog site is real south-pole terrain. Synthetic is a demo map.
          </p>
          <div className="controls-grid controls-grid-compact">
            <div className="control-span-2">
              <label htmlFor="terrain-mode">Terrain</label>
              <select
                id="terrain-mode"
                value={values.terrainMode}
                onChange={(e) =>
                  update("terrainMode", e.target.value as TerrainMode)
                }
              >
                <option value="synthetic">Synthetic (demo)</option>
                <option value="site">Lunar site (catalog)</option>
              </select>
            </div>

            {values.terrainMode === "site" && (
              <div className="control-span-2">
                <label htmlFor="lunar-site">Site</label>
                <select
                  id="lunar-site"
                  value={values.siteId}
                  onChange={(e) => update("siteId", e.target.value)}
                >
                  {sites.map((site) => (
                    <option key={site.id} value={site.id}>
                      {site.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <div className="label-row">
                <label htmlFor="terrain-size">Window size</label>
                <span className="value-badge">
                  {values.terrainSize} cells · {(values.terrainSize * values.resolution).toLocaleString()} m
                </span>
              </div>
              <input
                id="terrain-size"
                type="range"
                min={50}
                max={300}
                step={10}
                value={values.terrainSize}
                onChange={(e) => update("terrainSize", Number(e.target.value))}
              />
            </div>

            <div>
              <label htmlFor="resolution">Meters per pixel</label>
              <input
                id="resolution"
                type="number"
                min={1}
                max={100}
                value={values.resolution}
                onChange={(e) => update("resolution", Number(e.target.value))}
              />
            </div>
          </div>
        </section>

        <section className="control-section">
          <h2 className="control-section-title">3 · Start and goal</h2>
          <p className="control-section-help">
            Select A or B, then click the map. Green is the start. Red is the goal.
          </p>
          <div className="controls-grid controls-grid-compact">
            <div className="control-span-2 pick-mode-group">
              <div className="label-row">
                <span className="pick-mode-label">Click the map to place</span>
                <button
                  type="button"
                  className="link-btn"
                  onClick={swapPoints}
                  disabled={controlsBusy}
                  title="Swap Point A and Point B"
                >
                  Swap A ↔ B
                </button>
              </div>
              <div className="pick-mode-buttons">
                <button
                  type="button"
                  className={pickMode === "start" ? "pick-btn active" : "pick-btn"}
                  onClick={() => onPickModeChange("start")}
                >
                  <span className="pick-dot start" aria-hidden="true" />
                  Point A
                </button>
                <button
                  type="button"
                  className={pickMode === "goal" ? "pick-btn active" : "pick-btn"}
                  onClick={() => onPickModeChange("goal")}
                >
                  <span className="pick-dot goal" aria-hidden="true" />
                  Point B
                </button>
              </div>
            </div>
          </div>
        </section>

        <section className="control-section">
          <h2 className="control-section-title">4 · Rover</h2>
          <p className="control-section-help">
            The rover’s slope limit decides which ground is blocked.
          </p>
          <div className="controls-grid controls-grid-compact">
            <div className="control-span-2">
          <RoverSelector
            roverMode={roverMode}
            activeConfig={activeRoverConfig}
            astrolabPreset={astrolabPreset}
            pegasusPreset={pegasusPreset}
            presetOverrides={presetOverrides}
            onModeChange={onRoverModeChange}
            onPresetConfigChange={onPresetConfigChange}
            onResetPreset={onResetPreset}
          />
          {isRoverDirty && roverMode !== "custom" && (
            <p className="rover-custom-badge" role="status">
              Using customized preset values for this session.
            </p>
          )}
          {roverMode === "custom" && (
            <RoverCustomizer
              config={activeRoverConfig}
              customRovers={customRovers}
              selectedSavedName={selectedSavedCustomName}
              saveMessage={roverSaveMessage}
              onConfigChange={onRoverConfigChange}
              onLoadSaved={onLoadSavedCustom}
              onSave={onSaveCustomRover}
              onDeleteSaved={onDeleteCustomRover}
            />
          )}
            </div>
          </div>
        </section>

        <section className="control-section">
          <h2 className="control-section-title">5 · How careful</h2>
          <p className="control-section-help">
            Higher avoidance takes a longer path to stay off steep or rough ground.
          </p>
          <div className="controls-grid controls-grid-compact">
            <div className="control-span-2">
              <div className="label-row">
                <label
                  htmlFor="hazard-weight"
                  title="How strongly the planner penalizes steep, rough cells. Higher = longer but safer routes."
                >
                  Terrain avoidance
                </label>
                <span className="value-badge">{values.hazardWeight.toFixed(1)}</span>
              </div>
              <input
                id="hazard-weight"
                type="range"
                min={0}
                max={20}
                step={0.5}
                value={values.hazardWeight}
                onChange={(e) => update("hazardWeight", Number(e.target.value))}
                aria-describedby="hazard-weight-hint"
              />
              <p id="hazard-weight-hint" className="control-hint">
                {avoidanceHint(values.hazardWeight)}
              </p>
            </div>

            <div className="control-span-2">
              <button
                type="button"
                className="accordion-trigger accordion-trigger-compact"
                onClick={() => setAdvancedOpen(!advancedOpen)}
                aria-expanded={advancedOpen}
              >
                Type coordinates instead of clicking
                <span className={`accordion-chevron${advancedOpen ? " open" : ""}`} aria-hidden="true">
                  ▾
                </span>
              </button>
              {advancedOpen && (
                <div className="accordion-content controls-grid controls-grid-compact">
                  <div>
                    <label htmlFor="start-row">Start row</label>
                    <input
                      id="start-row"
                      type="number"
                      min={0}
                      max={values.terrainSize - 1}
                      value={values.startRow}
                      onChange={(e) => update("startRow", Number(e.target.value))}
                    />
                  </div>
                  <div>
                    <label htmlFor="start-col">Start column</label>
                    <input
                      id="start-col"
                      type="number"
                      min={0}
                      max={values.terrainSize - 1}
                      value={values.startCol}
                      onChange={(e) => update("startCol", Number(e.target.value))}
                    />
                  </div>
                  <div>
                    <label htmlFor="goal-row">Goal row</label>
                    <input
                      id="goal-row"
                      type="number"
                      min={0}
                      max={values.terrainSize - 1}
                      value={values.goalRow}
                      onChange={(e) => update("goalRow", Number(e.target.value))}
                    />
                  </div>
                  <div>
                    <label htmlFor="goal-col">Goal column</label>
                    <input
                      id="goal-col"
                      type="number"
                      min={0}
                      max={values.terrainSize - 1}
                      value={values.goalCol}
                      onChange={(e) => update("goalCol", Number(e.target.value))}
                    />
                  </div>
                  {demUpload}
                </div>
              )}
            </div>
          </div>
        </section>

        {beforeActions}
      </div>

      <div className="action-row action-row-inline">
        <button
          className="btn-primary btn-compact"
          onClick={onRun}
          disabled={actionsDisabled}
          title="Find one route for the rover selected above"
        >
          {loading
            ? "Planning…"
            : previewLoading
              ? "Loading map…"
              : runDisabled
                ? "Path is blocked"
                : "Plan this route"}
        </button>
        {onCompare && (
          <button
            type="button"
            className="btn-secondary-full btn-compact"
            onClick={onCompare}
            disabled={controlsBusy || compareDisabled}
            title="Score Astrolab and Pegasus on this same terrain"
          >
            {compareLoading ? "Comparing…" : "Compare rovers"}
          </button>
        )}
      </div>
      <p className="action-caption">
        Plan uses the rover above. Compare scores both built-in rovers on the same ground.
      </p>
    </div>
  );
}

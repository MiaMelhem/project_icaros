"use client";

import { useState } from "react";
import { RoverConfig } from "@/lib/api";
import {
  PresetRoverMode,
  ROVER_MODE_LABELS,
  RoverMode,
  isPresetCustomized,
} from "@/lib/customRovers";
import { RoverEditPanel, RoverEditTrigger } from "./RoverEditMenu";

const MODES: RoverMode[] = ["astrolab", "pegasus", "custom"];

interface RoverSelectorProps {
  roverMode: RoverMode;
  activeConfig: RoverConfig;
  astrolabPreset?: RoverConfig;
  pegasusPreset?: RoverConfig;
  presetOverrides: Partial<Record<PresetRoverMode, RoverConfig>>;
  onModeChange: (mode: RoverMode) => void;
  onPresetConfigChange: (mode: PresetRoverMode, config: RoverConfig) => void;
  onResetPreset: (mode: PresetRoverMode) => void;
}

export default function RoverSelector({
  roverMode,
  activeConfig,
  astrolabPreset,
  pegasusPreset,
  presetOverrides,
  onModeChange,
  onPresetConfigChange,
  onResetPreset,
}: RoverSelectorProps) {
  const [editOpen, setEditOpen] = useState(false);

  const astrolabCustomized = isPresetCustomized(
    "astrolab",
    presetOverrides.astrolab ?? astrolabPreset ?? null,
    astrolabPreset
  );
  const pegasusCustomized = isPresetCustomized(
    "pegasus",
    presetOverrides.pegasus ?? pegasusPreset ?? null,
    pegasusPreset
  );

  const activePresetMode = roverMode === "astrolab" || roverMode === "pegasus" ? roverMode : null;
  const activePreset = activePresetMode === "astrolab" ? astrolabPreset : pegasusPreset;
  const activeOverride = activePresetMode ? presetOverrides[activePresetMode] : undefined;
  const activeCustomized =
    activePresetMode === "astrolab" ? astrolabCustomized : pegasusCustomized;

  function handleModeChange(mode: RoverMode) {
    setEditOpen(false);
    onModeChange(mode);
  }

  return (
    <div className="rover-selector">
      <div className="label-row rover-selector-header">
        <span className="pick-mode-label">Rover</span>
        {activePresetMode && activePreset && (
          <RoverEditTrigger
            mode={activePresetMode}
            isCustomized={activeCustomized}
            isOpen={editOpen}
            onToggle={() => setEditOpen((open) => !open)}
          />
        )}
      </div>

      <div className="rover-mode-segment" role="group" aria-label="Rover profile">
        {MODES.map((mode) => {
          const customized =
            mode === "astrolab"
              ? astrolabCustomized
              : mode === "pegasus"
                ? pegasusCustomized
                : false;

          return (
            <button
              key={mode}
              type="button"
              className={`rover-mode-btn${roverMode === mode ? " active" : ""}${
                customized ? " has-override" : ""
              }`}
              onClick={() => handleModeChange(mode)}
              aria-pressed={roverMode === mode}
            >
              {ROVER_MODE_LABELS[mode]}
              {customized && roverMode !== mode && (
                <span className="rover-mode-dot" aria-hidden="true" />
              )}
            </button>
          );
        })}
      </div>

      {editOpen && activePresetMode && activePreset && (
        <RoverEditPanel
          mode={activePresetMode}
          config={activeOverride ?? activePreset}
          presetDefault={activePreset}
          isCustomized={activeCustomized}
          onChange={(config) => onPresetConfigChange(activePresetMode, config)}
          onReset={() => onResetPreset(activePresetMode)}
          onClose={() => setEditOpen(false)}
        />
      )}

      {roverMode !== "custom" && activeConfig.description && (
        <p className="rover-description">{activeConfig.description}</p>
      )}
    </div>
  );
}

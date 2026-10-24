"use client";

import { RoverConfig } from "@/lib/api";
import { PresetRoverMode, ROVER_MODE_LABELS } from "@/lib/customRovers";
import RoverParameterFields from "./RoverParameterFields";

interface RoverEditPanelProps {
  mode: PresetRoverMode;
  config: RoverConfig;
  presetDefault: RoverConfig;
  isCustomized: boolean;
  onChange: (config: RoverConfig) => void;
  onReset: () => void;
  onClose: () => void;
}

export function RoverEditPanel({
  mode,
  config,
  presetDefault,
  isCustomized,
  onChange,
  onReset,
  onClose,
}: RoverEditPanelProps) {
  return (
    <div className="rover-edit-panel" role="dialog" aria-label={`Edit ${ROVER_MODE_LABELS[mode]}`}>
      <div className="rover-edit-panel-header">
        <strong>{ROVER_MODE_LABELS[mode]} parameters</strong>
        <p className="control-hint">
          Adjust within each allowed range to explore what-if scenarios. Built-in presets stay
          unchanged.
        </p>
      </div>

      <RoverParameterFields
        config={config}
        onChange={onChange}
        presetDefault={presetDefault}
        presetLabel={ROVER_MODE_LABELS[mode]}
        compact
      />

      <div className="rover-edit-panel-actions">
        <button
          type="button"
          className="link-btn"
          onClick={() => {
            onReset();
            onClose();
          }}
          disabled={!isCustomized}
        >
          Reset to default
        </button>
        <button type="button" className="btn-secondary-full btn-compact" onClick={onClose}>
          Done
        </button>
      </div>
    </div>
  );
}

interface RoverEditTriggerProps {
  mode: PresetRoverMode;
  isCustomized: boolean;
  isOpen: boolean;
  onToggle: () => void;
}

export function RoverEditTrigger({
  mode,
  isCustomized,
  isOpen,
  onToggle,
}: RoverEditTriggerProps) {
  return (
    <button
      type="button"
      className={`rover-edit-trigger${isCustomized ? " customized" : ""}${isOpen ? " open" : ""}`}
      onClick={onToggle}
      aria-expanded={isOpen}
      aria-haspopup="dialog"
      title={`Edit ${ROVER_MODE_LABELS[mode]} parameters`}
    >
      <span aria-hidden="true">⋮</span>
      {isCustomized && <span className="rover-edit-dot" aria-hidden="true" />}
    </button>
  );
}

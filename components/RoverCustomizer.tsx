"use client";

import { RoverConfig } from "@/lib/api";
import RoverParameterFields from "./RoverParameterFields";

interface RoverCustomizerProps {
  config: RoverConfig;
  customRovers: RoverConfig[];
  selectedSavedName: string;
  saveMessage?: string | null;
  onConfigChange: (config: RoverConfig) => void;
  onLoadSaved: (name: string) => void;
  onSave: () => void;
  onDeleteSaved: () => void;
}

export default function RoverCustomizer({
  config,
  customRovers,
  selectedSavedName,
  saveMessage,
  onConfigChange,
  onLoadSaved,
  onSave,
  onDeleteSaved,
}: RoverCustomizerProps) {
  const canDelete =
    selectedSavedName.length > 0 &&
    customRovers.some((r) => r.name === selectedSavedName);

  return (
    <div className="rover-custom-panel">
      <p className="control-hint rover-custom-intro">
        Set each parameter within its allowed range to define your custom rover.
      </p>
      {customRovers.length > 0 && (
        <div>
          <label htmlFor="saved-custom-rover">Load saved</label>
          <select
            id="saved-custom-rover"
            value={selectedSavedName}
            onChange={(e) => onLoadSaved(e.target.value)}
          >
            <option value="">New custom rover…</option>
            {customRovers.map((rover) => (
              <option key={rover.name} value={rover.name}>
                {rover.name}
              </option>
            ))}
          </select>
        </div>
      )}

      <RoverParameterFields
        config={config}
        onChange={onConfigChange}
        showName
        showDescription
      />

      <div className="rover-custom-actions">
        <button
          type="button"
          className="btn-secondary-full btn-compact"
          onClick={onSave}
          disabled={!config.name.trim()}
        >
          Save custom rover
        </button>
        {canDelete && (
          <button type="button" className="link-btn link-btn-danger" onClick={onDeleteSaved}>
            Delete saved rover
          </button>
        )}
      </div>

      {saveMessage && (
        <p className="rover-save-message" role="status">
          {saveMessage}
        </p>
      )}
    </div>
  );
}

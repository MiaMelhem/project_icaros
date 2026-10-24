"use client";

import { RoverConfig } from "@/lib/api";
import {
  ROVER_PARAM_KEYS,
  ROVER_PARAM_LIMITS,
  RoverParamKey,
  formatParamRange,
  getPresetParamValue,
} from "@/lib/roverParamRanges";

interface RoverParameterFieldsProps {
  config: RoverConfig;
  onChange: (config: RoverConfig) => void;
  presetDefault?: RoverConfig;
  presetLabel?: string;
  showName?: boolean;
  showDescription?: boolean;
  compact?: boolean;
}

function fieldHint(field: RoverParamKey, compact: boolean): string {
  if (compact) {
    switch (field) {
      case "max_slope_deg":
        return "Steepness limit — higher allows steeper terrain.";
      case "nominal_speed_mps":
        return "Affects estimated travel time.";
      case "roughness_tolerance":
        return "Higher = tolerates bumpier ground.";
      case "energy_factor":
        return "Higher = higher energy score.";
      case "max_range_m":
        return "Warns if a planned route is longer than this.";
      default:
        return "";
    }
  }

  switch (field) {
    case "max_slope_deg":
      return "Higher = can climb steeper slopes; lower = more terrain blocked.";
    case "nominal_speed_mps":
      return "Affects estimated travel time along the route.";
    case "roughness_tolerance":
      return "Higher = tolerates bumpier ground in the hazard model.";
    case "energy_factor":
      return "Higher = higher energy score for the same distance.";
    case "max_range_m":
      return "Maximum distance the rover can cover in one leg.";
    default:
      return "";
  }
}

interface ParamSliderProps {
  paramKey: RoverParamKey;
  hint: string;
  value: number;
  presetValue?: number;
  presetLabel?: string;
  onChange: (value: number) => void;
}

function ParamSlider({
  paramKey,
  hint,
  value,
  presetValue,
  presetLabel,
  onChange,
}: ParamSliderProps) {
  const limit = ROVER_PARAM_LIMITS[paramKey];
  const id = `rover-${paramKey.replace(/_/g, "-")}`;
  const presetPercent =
    presetValue !== undefined
      ? ((presetValue - limit.min) / (limit.max - limit.min)) * 100
      : null;

  return (
    <div className="rover-param-field">
      <div className="label-row rover-param-label-row">
        <label htmlFor={id}>
          {limit.label}
          {limit.unit === "°" ? " (°)" : limit.unit ? ` (${limit.unit})` : ""}
        </label>
        <span className="value-badge">{limit.format(value)}</span>
      </div>

      <p className="rover-param-range-caption">
        Allowed range: <strong>{formatParamRange(limit)}</strong>
        {presetValue !== undefined && presetLabel && (
          <>
            {" · "}
            <span className="rover-param-preset-ref">
              {presetLabel} default: {limit.format(presetValue)}
            </span>
          </>
        )}
      </p>

      <div className="rover-param-slider-wrap">
        {presetPercent !== null && (
          <div
            className="rover-param-preset-marker"
            style={{ left: `${presetPercent}%` }}
            title={`${presetLabel} default: ${limit.format(presetValue!)}`}
            aria-hidden="true"
          />
        )}
        <input
          id={id}
          type="range"
          min={limit.min}
          max={limit.max}
          step={limit.step}
          value={value}
          aria-label={`${limit.label}, ${formatParamRange(limit)}`}
          aria-valuemin={limit.min}
          aria-valuemax={limit.max}
          aria-valuenow={value}
          onChange={(e) => onChange(Number(e.target.value))}
        />
      </div>

      <div className="rover-param-range-ticks" aria-hidden="true">
        <span>{limit.format(limit.min)}</span>
        <span>{limit.format(limit.max)}</span>
      </div>

      <p className="control-hint rover-param-hint">{hint}</p>
    </div>
  );
}

export default function RoverParameterFields({
  config,
  onChange,
  presetDefault,
  presetLabel,
  showName = false,
  showDescription = false,
  compact = false,
}: RoverParameterFieldsProps) {
  function update(field: keyof RoverConfig, value: string | number) {
    onChange({ ...config, [field]: value });
  }

  return (
    <div className={`rover-param-fields${compact ? " rover-param-fields-compact" : ""}`}>
      {showName && (
        <div className="rover-param-field rover-param-field-full">
          <label htmlFor="rover-custom-name">Rover name</label>
          <input
            id="rover-custom-name"
            type="text"
            value={config.name}
            maxLength={120}
            placeholder="e.g. Artemis Cargo Rover"
            onChange={(e) => update("name", e.target.value)}
          />
        </div>
      )}

      {ROVER_PARAM_KEYS.map((key) => (
        <ParamSlider
          key={key}
          paramKey={key}
          hint={fieldHint(key, compact)}
          value={config[key]}
          presetValue={getPresetParamValue(presetDefault, key)}
          presetLabel={presetLabel}
          onChange={(v) => update(key, v)}
        />
      ))}

      {showDescription && (
        <div className="rover-param-field rover-param-field-full">
          <label htmlFor="rover-description">Notes (optional)</label>
          <textarea
            id="rover-description"
            rows={2}
            value={config.description}
            placeholder="Mission assumptions, cargo load, etc."
            onChange={(e) => update("description", e.target.value)}
          />
        </div>
      )}
    </div>
  );
}

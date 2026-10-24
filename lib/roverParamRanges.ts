import { RoverConfig } from "@/lib/api";

export type RoverParamKey =
  | "max_slope_deg"
  | "nominal_speed_mps"
  | "roughness_tolerance"
  | "energy_factor"
  | "max_range_m";

export interface RoverParamLimit {
  key: RoverParamKey;
  label: string;
  min: number;
  max: number;
  step: number;
  unit: string;
  format: (value: number) => string;
}

export const ROVER_PARAM_LIMITS: Record<RoverParamKey, RoverParamLimit> = {
  max_slope_deg: {
    key: "max_slope_deg",
    label: "Max slope",
    min: 5,
    max: 45,
    step: 0.5,
    unit: "°",
    format: (v) => `${v.toFixed(1)}°`,
  },
  nominal_speed_mps: {
    key: "nominal_speed_mps",
    label: "Speed",
    min: 0.5,
    max: 10,
    step: 0.1,
    unit: "m/s",
    format: (v) => `${v.toFixed(1)} m/s`,
  },
  roughness_tolerance: {
    key: "roughness_tolerance",
    label: "Roughness tolerance",
    min: 0,
    max: 1,
    step: 0.05,
    unit: "",
    format: (v) => v.toFixed(2),
  },
  energy_factor: {
    key: "energy_factor",
    label: "Energy factor",
    min: 0.5,
    max: 3,
    step: 0.01,
    unit: "",
    format: (v) => v.toFixed(2),
  },
  max_range_m: {
    key: "max_range_m",
    label: "Max travel range",
    min: 500,
    max: 15000,
    step: 100,
    unit: "m",
    format: (v) => `${v.toLocaleString()} m`,
  },
};

export const ROVER_PARAM_KEYS = Object.keys(ROVER_PARAM_LIMITS) as RoverParamKey[];

export function formatParamRange(limit: RoverParamLimit): string {
  return `${limit.format(limit.min)} – ${limit.format(limit.max)}`;
}

export function getPresetParamValue(
  preset: RoverConfig | undefined,
  key: RoverParamKey
): number | undefined {
  if (!preset) return undefined;
  return preset[key];
}

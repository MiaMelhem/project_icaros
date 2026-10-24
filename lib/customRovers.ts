import { RoverConfig } from "@/lib/api";

export type RoverMode = "astrolab" | "pegasus" | "custom";

export type PresetRoverMode = Exclude<RoverMode, "custom">;

export const ROVER_PRESET_NAMES: Record<PresetRoverMode, string> = {
  astrolab: "Astrolab CLV-1",
  pegasus: "Lunar Outpost Pegasus",
};

export const ROVER_MODE_LABELS: Record<RoverMode, string> = {
  astrolab: "Astrolab",
  pegasus: "Pegasus",
  custom: "Custom",
};

const STORAGE_KEY = "icaros-custom-rovers";

export function defaultCustomRover(): RoverConfig {
  return {
    name: "",
    max_slope_deg: 20,
    nominal_speed_mps: 3,
    roughness_tolerance: 0.3,
    energy_factor: 1.12,
    max_range_m: 5000,
    description: "User-defined rover for mission what-if analysis.",
  };
}

export function loadCustomRovers(): RoverConfig[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as RoverConfig[];
    return Array.isArray(parsed)
      ? parsed
          .filter((r) => r.name?.trim())
          .map((r) => ({ ...defaultCustomRover(), ...r, name: r.name.trim() }))
      : [];
  } catch {
    return [];
  }
}

export function saveCustomRover(rover: RoverConfig): RoverConfig[] {
  const trimmed = rover.name.trim();
  if (!trimmed) return loadCustomRovers();

  const normalized: RoverConfig = { ...rover, name: trimmed };
  const existing = loadCustomRovers().filter((r) => r.name !== trimmed);
  const updated = [...existing, normalized];
  localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  return updated;
}

export function deleteCustomRover(name: string): RoverConfig[] {
  const updated = loadCustomRovers().filter((r) => r.name !== name);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  return updated;
}

export function roverConfigsEqual(a: RoverConfig, b: RoverConfig): boolean {
  return (
    a.max_slope_deg === b.max_slope_deg &&
    a.nominal_speed_mps === b.nominal_speed_mps &&
    a.roughness_tolerance === b.roughness_tolerance &&
    a.energy_factor === b.energy_factor &&
    a.max_range_m === b.max_range_m
  );
}

export function findBuiltinPreset(
  mode: PresetRoverMode,
  builtinRovers: RoverConfig[]
): RoverConfig | undefined {
  const name = ROVER_PRESET_NAMES[mode];
  return builtinRovers.find((r) => r.name === name);
}

export function isPresetCustomized(
  mode: PresetRoverMode,
  active: RoverConfig | null,
  preset: RoverConfig | undefined
): boolean {
  if (!active || !preset) return false;
  return !roverConfigsEqual(active, preset);
}

/** Build API rover fields. Returns null when config is not ready for a request. */
export function buildRoverApiFields(
  mode: RoverMode,
  active: RoverConfig | null,
  preset: RoverConfig | undefined
): { rover_name: string; rover_config?: RoverConfig } | null {
  if (!active) return null;

  if (mode === "custom") {
    const name = active.name.trim();
    if (!name) return null;
    return { rover_name: name, rover_config: { ...active, name } };
  }

  const presetName = ROVER_PRESET_NAMES[mode];
  if (preset && roverConfigsEqual(active, preset)) {
    return { rover_name: presetName };
  }

  return {
    rover_name: presetName,
    rover_config: { ...active, name: presetName },
  };
}

export function roverModeLabel(mode: RoverMode, active: RoverConfig | null): string {
  if (mode === "custom") return active?.name.trim() || "Custom";
  return ROVER_MODE_LABELS[mode];
}

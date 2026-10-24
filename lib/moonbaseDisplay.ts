import {
  AssetKind,
  MoonbasePhase,
  MoonbaseSettings,
  SurfaceAsset,
} from "@/lib/api";

/** Same cutoff the planner uses for a low-sun shadow cell. */
export const SHADOW_LIT_FRACTION = 0.25;

/** Planning distances used by the route model. The guide names the effects, not these radii. */
export const PLANNING_RADII_M = {
  comms: 1500,
  power: 2000,
  hardwareShadow: 60,
  habitat: 80,
  lander: 150,
  infrastructure: 40,
} as const;

export const ASSET_LABELS: Record<AssetKind, string> = {
  habitat: "Habitat",
  lander: "Lander",
  power_node: "Power",
  wireless_charger: "Charger",
  relay: "Relay",
  infrastructure: "Structure",
};

export const ASSET_COLORS: Record<AssetKind, string> = {
  habitat: "#38bdf8",
  lander: "#fb923c",
  power_node: "#facc15",
  wireless_charger: "#a3e635",
  relay: "#22d3ee",
  infrastructure: "#c4b5fd",
};

export const GAP_SENTENCES: Record<string, string> = {
  "FN-A-103": "Robotic reconnaissance",
  "FN-U-103": "Resource identification on the surface",
  "FN-M-302": "Sunlit mobility outside permanently shadowed regions",
  "FN-M-304": "Mobility inside permanently shadowed regions",
  "FN-M-401": "Unload a few hundred kilograms",
  "FN-M-501": "Reposition a few hundred kilograms",
  "FN-A-302": "Safeguards for automated assets near the crew",
  "FN-A-401": "Command assets from Earth while the base is uncrewed",
  "FN-P-301": "Distribute power on the surface",
  "FN-C-101": "Communications between the lunar surface and Earth",
  "FN-C-201": "South Pole position, navigation, and timing",
  "FN-C-103": "Communications between assets on the surface",
};

export const PHASE_GUIDE: Record<
  1 | 2 | 3,
  { short: string; detail: string }
> = {
  1: {
    short: "Phase 1 — First visits",
    detail:
      "The route is the rover, the terrain, light, and shadow.",
  },
  2: {
    short: "Phase 2 — A small base",
    detail:
      "The drive is still the rover, the terrain, light, and shadow.",
  },
  3: {
    short: "Phase 3 — Staying",
    detail:
      "Adds site preparation, prospecting in shadow, and driving with no crew aboard.",
  },
};

export function phaseSentence(phaseId: number): string {
  const guide = PHASE_GUIDE[phaseId as 1 | 2 | 3];
  if (!guide) return `Phase ${phaseId}`;
  return `${guide.short}. ${guide.detail}`;
}

export type CriterionId =
  | "lighting"
  | "psr"
  | "slope"
  | "cargo"
  | "power"
  | "comms"
  | "keepout"
  | "landing";

export interface CriterionRow {
  id: CriterionId;
  label: string;
  detail: string;
  swatch: string;
  spatial: boolean;
}

const PSR_OPEN_MISSIONS = new Set(["psr_access", "isru_prospecting"]);
const PSR_IF_CAPABLE = new Set(["reconnaissance"]);

const MISSION_SUMMARIES: Record<string, string> = {
  landing_site: "Landing-site check. Slope, blocks, and plume keep-out.",
  reconnaissance: "Reconnaissance. Shadow is open only for a PSR-capable rover.",
  sunlit_traverse: "Sunlit traverse. Permanently shadowed regions are blocked.",
  psr_access: "PSR access. Enter a shadowed crater if the rover can.",
  cargo_reposition: "Cargo reposition. Move a few hundred kilograms in sunlight.",
  site_prep: "Site preparation. Reach a work area. Excavation is not simulated.",
  isru_prospecting: "ISRU prospecting. Shadowed crater, without invented resource grades.",
};

export function missionSummary(missionId: string): string {
  return MISSION_SUMMARIES[missionId] ?? "";
}

export function phaseLine(phase: MoonbasePhase | null | undefined, fallbackPhase: number): string {
  if (!phase) return `Phase ${fallbackPhase}`;
  return phaseSentence(phase.id);
}

export function gapSentence(ids: string[] | undefined): string {
  if (!ids?.length) return "";
  return ids.map((id) => GAP_SENTENCES[id] ?? id).join(". ") + ".";
}

function psrDetail(settings: MoonbaseSettings): string {
  if (PSR_OPEN_MISSIONS.has(settings.mission)) {
    if (settings.psrCapable) {
      return "Open. The rover's own slope limit still applies inside the shadow (FN-M-304).";
    }
    return "Blocked until the rover is PSR-capable (FN-M-304).";
  }
  if (PSR_IF_CAPABLE.has(settings.mission) && settings.psrCapable) {
    return "Open for this rover. Reconnaissance may enter shadow (FN-A-103).";
  }
  return "Blocked. Sunlit mobility stays out of permanently shadowed regions (FN-M-302).";
}

export function activeCriteria(
  settings: MoonbaseSettings,
  maxSlopeDeg: number
): CriterionRow[] {
  const rows: CriterionRow[] = [
    {
      id: "lighting",
      label: "Lighting",
      detail: settings.nightSurvival
        ? "Low Sun and long shadows. This rover survives 120 hours of darkness, so shadow barely changes the energy."
        : "Low Sun and long shadows. Time in shadow raises energy unless the rover survives 120 hours of darkness.",
      swatch: "#334155",
      spatial: true,
    },
    {
      id: "psr",
      label: "PSR",
      detail: psrDetail(settings),
      swatch: "#581c87",
      spatial: true,
    },
    {
      id: "slope",
      label: "Slope",
      detail: `${maxSlopeDeg}° driving limit, including inside a permanently shadowed region.`,
      swatch: "#f97316",
      spatial: false,
    },
  ];

  if (settings.mission === "cargo_reposition" || settings.cargoKg > 0) {
    const kg =
      settings.mission === "cargo_reposition"
        ? Math.max(200, settings.cargoKg)
        : settings.cargoKg;
    rows.push({
      id: "cargo",
      label: "Cargo",
      detail: `${kg.toLocaleString()} kg. 500 kg doubles the energy factor (FN-M-401, FN-M-501).`,
      swatch: "#eab308",
      spatial: false,
    });
  }

  rows.push({
    id: "comms",
    label: "Communications",
    detail:
      "PSR cells and closed horizons lose Earth view. This is coverage, not a link budget.",
    swatch: "#22d3ee",
    spatial: true,
  });

  if (settings.mission === "landing_site") {
    rows.push({
      id: "landing",
      label: "Landing",
      detail: "Slope and roughness stand in for surface blocks and plume risk to nearby assets.",
      swatch: "#fb923c",
      spatial: false,
    });
  }

  return rows;
}

export function hardwareShadowAssets(assets: SurfaceAsset[]): SurfaceAsset[] {
  return assets.filter(
    (asset) => asset.kind === "habitat" || asset.kind === "infrastructure"
  );
}

export function keepoutAssets(assets: SurfaceAsset[]): SurfaceAsset[] {
  return assets.filter(
    (asset) =>
      asset.kind === "habitat" ||
      asset.kind === "lander" ||
      asset.kind === "infrastructure"
  );
}

export function powerAssets(
  assets: SurfaceAsset[],
  wirelessCharge: boolean
): SurfaceAsset[] {
  return assets.filter(
    (asset) =>
      asset.kind === "power_node" ||
      (wirelessCharge && asset.kind === "wireless_charger")
  );
}

export function keepoutRadiusM(kind: AssetKind): number | null {
  if (kind === "habitat") return PLANNING_RADII_M.habitat;
  if (kind === "lander") return PLANNING_RADII_M.lander;
  if (kind === "infrastructure") return PLANNING_RADII_M.infrastructure;
  return null;
}

export function inRadius(
  row: number,
  col: number,
  originRow: number,
  originCol: number,
  radiusM: number,
  resolutionM: number
): boolean {
  if (resolutionM <= 0) return false;
  const radiusCells = radiusM / resolutionM;
  const dr = row - originRow;
  const dc = col - originCol;
  return dr * dr + dc * dc <= radiusCells * radiusCells;
}

export type RouteMark = "keepout" | "psr" | "comms" | "lighting" | "hardware";

export const MARK_COLORS: Record<RouteMark, string> = {
  keepout: "#b91c1c",
  psr: "#c084fc",
  comms: "#22d3ee",
  lighting: "#94a3b8",
  hardware: "#818cf8",
};

export function routeMarkAt(
  row: number,
  col: number,
  enabled: Partial<Record<CriterionId, boolean>>,
  grids: {
    illumination?: number[][] | null;
    psr?: boolean[][] | null;
    comms?: boolean[][] | null;
    keepout?: boolean[][] | null;
    assets?: SurfaceAsset[];
    resolutionM?: number;
  }
): RouteMark | null {
  if (enabled.keepout && grids.keepout?.[row]?.[col]) return "keepout";
  if (enabled.psr && grids.psr?.[row]?.[col]) return "psr";
  if (enabled.comms && grids.comms?.[row]?.[col]) return "comms";
  const lit = grids.illumination?.[row]?.[col];
  if (
    enabled.lighting &&
    lit != null &&
    Number(lit) < SHADOW_LIT_FRACTION &&
    !grids.psr?.[row]?.[col]
  ) {
    return "lighting";
  }
  return null;
}

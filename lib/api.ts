/**
 * API client for ICAROS FastAPI backend.
 * Uses relative URLs so the same code works locally (Next.js rewrite) and on Vercel.
 */

import { getSupabaseClient } from "@/lib/supabaseClient";

export interface RoverConfig {
  name: string;
  max_slope_deg: number;
  nominal_speed_mps: number;
  roughness_tolerance: number;
  energy_factor: number;
  max_range_m: number;
  description: string;
}

export interface LunarSite {
  id: string;
  name: string;
  description: string;
  center_lat: number;
  center_lon: number;
  window_size_m: number;
  resolution_m: number;
  source: string;
  dem_filename?: string;
}

export interface TerrainMetadata {
  size: number;
  resolution_m_per_pixel: number;
  source: string;
  description: string;
  site_id?: string;
  site_name?: string;
  center_lat?: number;
  center_lon?: number;
  window_size_m?: number;
  terrain_kind?: string;
  center_rule?: string;
  center_note?: string;
  coverage_status?: string;
  coverage_note?: string;
  nodata_fraction?: number;
}

export interface CoordinateInfo {
  start_m: [number, number];
  goal_m: [number, number];
  start_latlon?: [number, number];
  goal_latlon?: [number, number];
}

export interface RouteMetrics {
  distance_m: number;
  estimated_time_min: number;
  max_slope_deg: number;
  average_slope_deg: number;
  average_hazard_score: number;
  energy_score: number;
  max_range_m: number;
  range_exceeded: boolean;
  shadow_fraction?: number;
  time_in_darkness_min?: number;
  psr_fraction?: number;
  comms_gap_fraction?: number;
  power_margin_m?: number;
  cargo_kg?: number;
  enters_keepout?: boolean;
  cargo_factor?: number;
  shadow_factor?: number;
}

export type TerrainMode = "synthetic" | "site";
export type AssetKind =
  | "habitat"
  | "lander"
  | "power_node"
  | "wireless_charger"
  | "relay"
  | "infrastructure";
export type PickMode = "start" | "goal" | AssetKind;

export interface SurfaceAsset {
  kind: AssetKind;
  row: number;
  col: number;
}

export interface MoonbaseMission {
  id: string;
  label: string;
  summary: string;
  phase_min: number;
  functional_gaps: string[];
}

export interface MoonbasePhase {
  id: number;
  name: string;
  summary: string;
  payload_kg: number;
  launches: number;
  landings: number;
  mars_forward: string;
}

export interface MoonbaseCatalog {
  phases: MoonbasePhase[];
  missions: MoonbaseMission[];
  asset_kinds: AssetKind[];
  thresholds: {
    survive_the_night_hours: number;
    power_generation_kw: number;
    cargo_mission_kg: number;
  };
  uncertainty: string[];
}

export interface MoonbaseSummary {
  phase: number;
  phase_name: string;
  phase_summary: string;
  payload_kg: number;
  mars_forward: string;
  mission: string;
  mission_label: string;
  mission_summary: string;
  functional_gaps: string[];
  cargo_kg: number;
  uncrewed: boolean;
  psr_capable: boolean;
  night_survival_hours: number;
  wireless_charge: boolean;
  ignored_assets: string[];
  assets: SurfaceAsset[];
  uncertainty: string[];
}

export interface MoonbaseSettings {
  phase: 1 | 2 | 3;
  mission: string;
  uncrewed: boolean;
  psrCapable: boolean;
  cargoKg: number;
  nightSurvival: boolean;
  wirelessCharge: boolean;
  assets: SurfaceAsset[];
}

export const DEFAULT_MOONBASE: MoonbaseSettings = {
  phase: 1,
  mission: "sunlit_traverse",
  uncrewed: false,
  psrCapable: false,
  cargoKg: 0,
  nightSurvival: false,
  wirelessCharge: false,
  assets: [],
};

export function moonbaseRequestFields(settings: MoonbaseSettings) {
  return {
    phase: settings.phase,
    mission: settings.mission,
    uncrewed: settings.phase >= 3 && settings.uncrewed,
    assets: settings.phase >= 2 ? settings.assets : [],
    psr_capable: settings.psrCapable,
    cargo_kg: settings.cargoKg,
    night_survival_hours: settings.nightSurvival ? 120 : 0,
    wireless_charge: settings.wirelessCharge,
  };
}

export interface MoonbaseRequestFields {
  phase?: number;
  mission?: string;
  uncrewed?: boolean;
  assets?: SurfaceAsset[];
  psr_capable?: boolean;
  cargo_kg?: number;
  night_survival_hours?: number;
  wireless_charge?: boolean;
}

export interface PlanRouteParams extends MoonbaseRequestFields {
  terrain_mode: TerrainMode;
  site_id?: string;
  terrain_size: number;
  resolution_m_per_pixel: number;
  rover_name: string;
  rover_config?: RoverConfig;
  start: [number, number];
  goal: [number, number];
  hazard_weight: number;
}

export interface TerrainPreviewParams extends MoonbaseRequestFields {
  terrain_mode: TerrainMode;
  site_id?: string;
  terrain_size: number;
  resolution_m_per_pixel: number;
  rover_name?: string;
  rover_config?: RoverConfig;
}

export interface TerrainPreviewResponse {
  terrain: number[][];
  slope: number[][];
  hillshade: number[][];
  illumination?: number[][];
  psr_mask?: boolean[][];
  comms_gap_mask?: boolean[][];
  keepout_mask?: boolean[][];
  blocked_mask: boolean[][];
  nodata_mask: boolean[][];
  max_slope_deg: number;
  metadata: TerrainMetadata;
  moonbase?: MoonbaseSummary;
}

export interface RouteValidationResult {
  feasible: boolean;
  reason_code: string;
  message: string;
  blocked_fraction?: number;
}

export interface ValidateRouteParams extends PlanRouteParams {}

export interface PlanRouteResponse {
  route_found: boolean;
  terrain: number[][];
  slope: number[][];
  hazard_score: number[][];
  route: number[][];
  metrics: RouteMetrics;
  csv_data: string;
  metadata?: TerrainMetadata;
  coordinates?: CoordinateInfo;
  start?: [number, number];
  goal?: [number, number];
  validation?: RouteValidationResult;
  moonbase?: MoonbaseSummary;
}

export interface RouteScores {
  safety: number;
  time: number;
  distance: number;
  slope: number;
  energy: number;
  overall: number;
}

export interface RouteAlternative {
  id: string;
  label: string;
  rover_name: string;
  hazard_weight: number;
  color: string;
  route_found: boolean;
  route: number[][];
  metrics: RouteMetrics;
  scores: RouteScores;
  csv_data?: string;
  validation?: RouteValidationResult;
}

export interface CompareRoutesParams extends MoonbaseRequestFields {
  terrain_mode: TerrainMode;
  site_id?: string;
  terrain_size: number;
  resolution_m_per_pixel: number;
  rover_name: string;
  rover_config?: RoverConfig;
  start: [number, number];
  goal: [number, number];
  hazard_weight: number;
}

export interface CompareRoutesResponse {
  alternatives: RouteAlternative[];
  best_by_metric: Record<string, string | null>;
  terrain: number[][];
  hazard_score: number[][];
  metadata: TerrainMetadata;
  coordinates: CoordinateInfo;
  start: [number, number];
  goal: [number, number];
  safest_hazard_weight: number;
  moonbase?: MoonbaseSummary;
}

export interface UploadDemResponse {
  uploaded: boolean;
  site_id: string;
  filename: string;
  path: string;
  message: string;
}

export interface SaveRunParams {
  rover_name: string;
  terrain_size: number;
  resolution_m_per_pixel: number;
  start_row: number;
  start_col: number;
  goal_row: number;
  goal_col: number;
  hazard_weight: number;
  route_found: boolean;
  distance_m: number;
  estimated_time_min: number;
  max_slope_deg: number;
  average_slope_deg: number;
  average_hazard_score: number;
  energy_score: number;
  route_json: number[][];
}

export interface SaveRunResponse {
  saved: boolean;
  message: string;
  id?: number;
}

/** Built-in fallback when API/Supabase are unavailable (e.g. stale backend). */
export const FALLBACK_LUNAR_SITES: LunarSite[] = [
  {
    id: "shackleton-rim",
    name: "Shackleton Crater Rim",
    description: "Permanently shadowed interior with sunlit rim — key Artemis candidate region.",
    center_lat: -89.9,
    center_lon: 0.0,
    window_size_m: 4000,
    resolution_m: 20,
    source: "LROC NAC DTM",
    dem_filename: "shackleton-rim.tif",
  },
  {
    id: "malapert-massif",
    name: "Malapert Massif",
    description: "Elevated peak near the South Pole with extended sun exposure.",
    center_lat: -86.0,
    center_lon: 2.0,
    window_size_m: 4000,
    resolution_m: 20,
    source: "LROC NAC DTM (NAC_DTM_ESALL_MP1, ~2 m/px)",
    dem_filename: "malapert-massif.tif",
  },
  {
    id: "haworth-crater",
    name: "Haworth Crater",
    description: "Large complex crater on the lunar South Pole highlands.",
    center_lat: -87.5,
    center_lon: 320.0,
    window_size_m: 4000,
    resolution_m: 20,
    source: "NASA LOLA 5 m/px LDEM (PGDA Haworth)",
    dem_filename: "haworth-crater.tif",
  },
  {
    id: "nobile-crater",
    name: "Nobile Crater",
    description: "Artemis landing candidate site in the South Pole region.",
    center_lat: -84.73,
    center_lon: 29.13,
    window_size_m: 4000,
    resolution_m: 20,
    source: "LROC NAC DTM (NAC_DTM_NOBILE03, 4 m/px)",
    dem_filename: "nobile-crater.tif",
  },
  {
    id: "amundsen-rim",
    name: "Amundsen Crater Rim",
    description: "Rugged rim terrain with mixed slopes and crater features.",
    center_lat: -88.5,
    center_lon: 80.0,
    window_size_m: 4000,
    resolution_m: 20,
    source: "NASA LOLA 5 m/px LDEM (PGDA DM1 Amundsen rim)",
    dem_filename: "amundsen-rim.tif",
  },
];

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API error (${response.status}): ${text}`);
  }
  return response.json();
}

export async function fetchRovers(): Promise<RoverConfig[]> {
  const response = await fetch("/api/rovers");
  const data = await handleResponse<{ rovers: RoverConfig[] }>(response);
  return data.rovers;
}

export async function fetchLunarSites(): Promise<LunarSite[]> {
  try {
    const response = await fetch("/api/lunar-sites");
    const data = await handleResponse<{ sites: LunarSite[] }>(response);
    if (data.sites?.length) {
      return data.sites;
    }
  } catch {
    // Fall through to Supabase or built-in catalog.
  }

  const supabase = getSupabaseClient();
  if (supabase) {
    const { data, error } = await supabase
      .from("lunar_sites")
      .select("*")
      .order("name");
    if (!error && data?.length) {
      return data as LunarSite[];
    }
  }

  return FALLBACK_LUNAR_SITES;
}

interface RoverRequestBody {
  rover_name?: string;
  rover_config?: RoverConfig;
}

function withRoverFields<T extends RoverRequestBody>(params: T): T & { rover_name: string } {
  const body = {
    ...params,
    rover_name: params.rover_name ?? "Astrolab CLV-1",
  } as T & { rover_name: string };
  if (params.rover_config) {
    body.rover_config = params.rover_config;
  }
  return body;
}

export async function fetchMoonbase(): Promise<MoonbaseCatalog> {
  const response = await fetch("/api/moonbase");
  return handleResponse<MoonbaseCatalog>(response);
}

export async function fetchTerrainPreview(
  params: TerrainPreviewParams
): Promise<TerrainPreviewResponse> {
  const response = await fetch("/api/terrain-preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(withRoverFields(params)),
  });
  return handleResponse<TerrainPreviewResponse>(response);
}

export async function validateRoute(
  params: ValidateRouteParams
): Promise<RouteValidationResult> {
  const response = await fetch("/api/validate-route", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return handleResponse<RouteValidationResult>(response);
}

export async function planRoute(params: PlanRouteParams): Promise<PlanRouteResponse> {
  const response = await fetch("/api/plan-route", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(withRoverFields(params)),
  });
  return handleResponse<PlanRouteResponse>(response);
}

export async function compareRoutes(
  params: CompareRoutesParams
): Promise<CompareRoutesResponse> {
  const response = await fetch("/api/compare-routes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(withRoverFields(params)),
  });
  return handleResponse<CompareRoutesResponse>(response);
}

export async function uploadDem(
  siteId: string,
  file: File
): Promise<UploadDemResponse> {
  const formData = new FormData();
  formData.append("site_id", siteId);
  formData.append("file", file);

  const response = await fetch("/api/upload-dem", {
    method: "POST",
    body: formData,
  });
  return handleResponse<UploadDemResponse>(response);
}

export async function saveRun(params: SaveRunParams): Promise<SaveRunResponse> {
  const response = await fetch("/api/save-run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return handleResponse<SaveRunResponse>(response);
}

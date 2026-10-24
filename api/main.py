"""
ICAROS FastAPI application.

This is the HTTP layer that connects the frontend to the Python route engine.
The FastAPI instance must be named `app` for Vercel deployment.
"""

import os
import sys

# Allow imports from the backend/ package when running from api/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Load .env.local for local development (Supabase keys, etc.)
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env.local"))

from typing import Literal, Optional

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.coordinates import grid_to_meters, meters_to_grid
from backend.dem_loader import DEM_DIR, load_site_terrain, load_synthetic_terrain_full
from backend.export_utils import (
    calculate_route_metrics,
    dataframe_to_csv_string,
    empty_route_metrics,
    enrich_metrics_with_range,
    route_to_dataframe,
)
from backend.lunar_sites import get_lunar_site, list_lunar_sites
from backend.moonbase import apply_architecture_metrics, build_route_constraints, catalog
from backend.route_planner import find_route
from backend.route_scoring import score_alternatives
from backend.route_validation import hover_message, validate_route
from backend.rover_config import list_rovers, resolve_rover_config
from backend.terrain_analysis import build_terrain_analysis

app = FastAPI(title="ICAROS", description="Intelligent Crater-Aware Route Optimization System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request / response models ---


class RoverConfigOverride(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    max_slope_deg: float = Field(ge=5, le=45)
    nominal_speed_mps: float = Field(gt=0, le=20)
    roughness_tolerance: float = Field(ge=0, le=1)
    energy_factor: float = Field(gt=0, le=5)
    max_range_m: float = Field(ge=500, le=15000)
    psr_capable: bool = False
    cargo_kg: float = Field(default=0, ge=0, le=1000)
    night_survival_hours: float = Field(default=0, ge=0, le=5000)
    wireless_charge: bool = False
    description: str = ""


class SurfaceAsset(BaseModel):
    kind: Literal[
        "habitat",
        "lander",
        "power_node",
        "wireless_charger",
        "relay",
        "infrastructure",
    ]
    row: int = Field(ge=0)
    col: int = Field(ge=0)


class MoonbaseFields(BaseModel):
    """Phase, mission, and optional surface assets from the Moon Base guide."""

    phase: int = Field(default=1, ge=1, le=3)
    mission: str = "sunlit_traverse"
    uncrewed: bool = False
    assets: list[SurfaceAsset] = []
    psr_capable: Optional[bool] = None
    cargo_kg: Optional[float] = Field(default=None, ge=0, le=1000)
    night_survival_hours: Optional[float] = Field(default=None, ge=0, le=5000)
    wireless_charge: Optional[bool] = None


class PlanRouteRequest(MoonbaseFields):
    terrain_mode: Literal["synthetic", "site"] = "synthetic"
    site_id: Optional[str] = None
    terrain_size: int = Field(default=200, ge=50, le=500)
    resolution_m_per_pixel: float = Field(default=20.0, gt=0)
    rover_name: str = "Astrolab CLV-1"
    rover_config: Optional[RoverConfigOverride] = None
    start: Optional[list[int]] = Field(default=[20, 20])
    goal: Optional[list[int]] = Field(default=[170, 170])
    start_m: Optional[list[float]] = None
    goal_m: Optional[list[float]] = None
    hazard_weight: float = Field(default=5.0, ge=0)


class TerrainPreviewRequest(MoonbaseFields):
    terrain_mode: Literal["synthetic", "site"] = "synthetic"
    site_id: Optional[str] = None
    terrain_size: int = Field(default=200, ge=50, le=500)
    resolution_m_per_pixel: float = Field(default=20.0, gt=0)
    rover_name: str = "Astrolab CLV-1"
    rover_config: Optional[RoverConfigOverride] = None


class ValidateRouteRequest(MoonbaseFields):
    terrain_mode: Literal["synthetic", "site"] = "synthetic"
    site_id: Optional[str] = None
    terrain_size: int = Field(default=200, ge=50, le=500)
    resolution_m_per_pixel: float = Field(default=20.0, gt=0)
    rover_name: str = "Astrolab CLV-1"
    rover_config: Optional[RoverConfigOverride] = None
    start: list[int] = Field(default=[20, 20])
    goal: list[int] = Field(default=[170, 170])
    hover_row: Optional[int] = None
    hover_col: Optional[int] = None


class SaveRunRequest(BaseModel):
    rover_name: str
    terrain_size: int
    resolution_m_per_pixel: float
    start_row: int
    start_col: int
    goal_row: int
    goal_col: int
    hazard_weight: float
    route_found: bool
    distance_m: float
    estimated_time_min: float
    max_slope_deg: float
    average_slope_deg: float
    average_hazard_score: float
    energy_score: float
    route_json: list[list[int]]


class CompareRoutesRequest(MoonbaseFields):
    terrain_mode: Literal["synthetic", "site"] = "synthetic"
    site_id: Optional[str] = None
    terrain_size: int = Field(default=200, ge=50, le=500)
    resolution_m_per_pixel: float = Field(default=20.0, gt=0)
    rover_name: str = "Astrolab CLV-1"
    rover_config: Optional[RoverConfigOverride] = None
    start: Optional[list[int]] = Field(default=[20, 20])
    goal: Optional[list[int]] = Field(default=[170, 170])
    start_m: Optional[list[float]] = None
    goal_m: Optional[list[float]] = None
    hazard_weight: float = Field(default=5.0, ge=0)


SAFEST_HAZARD_WEIGHT = 15.0


def rover_override_dict(override: RoverConfigOverride | None) -> dict | None:
    """Convert optional Pydantic override to a plain dict for the engine."""
    if override is None:
        return None
    return override.model_dump()


def resolve_rover_from_request(rover_name: str, override: RoverConfigOverride | None) -> dict:
    """Resolve rover config, translating validation errors to HTTP 400."""
    try:
        return resolve_rover_config(rover_name, rover_override_dict(override))
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


# --- Helpers ---


def is_supabase_configured():
    """Return True if server-side Supabase credentials are available."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    return bool(url and key)


def get_supabase_client():
    """Create a Supabase client using the service role key."""
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    return create_client(url, key)


def load_terrain_for_request(request: PlanRouteRequest | TerrainPreviewRequest | ValidateRouteRequest) -> dict:
    """Load elevation grid based on terrain mode."""
    if request.terrain_mode == "site":
        if not request.site_id:
            raise HTTPException(status_code=400, detail="site_id is required for site terrain mode")
        try:
            return load_site_terrain(
                site_id=request.site_id,
                size=request.terrain_size,
                resolution_m_per_pixel=request.resolution_m_per_pixel,
            )
        except KeyError as error:
            raise HTTPException(status_code=400, detail=str(error))

    return load_synthetic_terrain_full(
        size=request.terrain_size,
        resolution_m_per_pixel=request.resolution_m_per_pixel,
    )


def effective_resolution(metadata: dict, fallback: float) -> float:
    """Use DEM-native resolution when available for accurate slope."""
    return float(metadata.get("effective_resolution_m_per_pixel", fallback))


def analysis_for_request(request, rover_name: str | None = None) -> dict:
    """Load terrain and compute analysis grids for preview/validation/routing."""
    name = rover_name or request.rover_name
    rover_config = resolve_rover_from_request(name, getattr(request, "rover_config", None))

    terrain_result = load_terrain_for_request(request)
    metadata = terrain_result["metadata"]
    res = effective_resolution(metadata, request.resolution_m_per_pixel)

    analysis = build_terrain_analysis(
        terrain_result["elevation"],
        terrain_result["nodata_mask"],
        res,
        rover_config,
    )
    analysis["metadata"] = metadata
    analysis["rover_config"] = rover_config
    return attach_moonbase(analysis, request)


def resolve_start_goal(
    request: PlanRouteRequest,
    grid_size: int,
) -> tuple[list[int], list[int]]:
    """Resolve start/goal from row/col or local meters."""
    if request.start_m is not None and request.goal_m is not None:
        if len(request.start_m) != 2 or len(request.goal_m) != 2:
            raise HTTPException(status_code=400, detail="start_m and goal_m must be [x_m, y_m]")
        start = list(
            meters_to_grid(
                request.start_m[0],
                request.start_m[1],
                grid_size,
                request.resolution_m_per_pixel,
            )
        )
        goal = list(
            meters_to_grid(
                request.goal_m[0],
                request.goal_m[1],
                grid_size,
                request.resolution_m_per_pixel,
            )
        )
        return start, goal

    start = request.start or [20, 20]
    goal = request.goal or [170, 170]
    if len(start) != 2 or len(goal) != 2:
        raise HTTPException(status_code=400, detail="start and goal must be [row, col]")
    return start, goal


def build_coordinate_info(
    start: list[int],
    goal: list[int],
    grid_size: int,
    resolution_m_per_pixel: float,
    metadata: dict,
) -> dict:
    """Attach local meter and approximate lat/lon info for the UI."""
    from backend.coordinates import approximate_latlon_from_meters

    start_x, start_y = grid_to_meters(start[0], start[1], grid_size, resolution_m_per_pixel)
    goal_x, goal_y = grid_to_meters(goal[0], goal[1], grid_size, resolution_m_per_pixel)

    info = {
        "start_m": [round(start_x, 1), round(start_y, 1)],
        "goal_m": [round(goal_x, 1), round(goal_y, 1)],
    }

    if metadata.get("center_lat") is not None:
        start_lat, start_lon = approximate_latlon_from_meters(
            metadata["center_lat"], metadata["center_lon"], start_x, start_y
        )
        goal_lat, goal_lon = approximate_latlon_from_meters(
            metadata["center_lat"], metadata["center_lon"], goal_x, goal_y
        )
        info["start_latlon"] = [round(start_lat, 4), round(start_lon, 4)]
        info["goal_latlon"] = [round(goal_lat, 4), round(goal_lon, 4)]

    return info


def plan_single_route(
    analysis: dict,
    start: list[int],
    goal: list[int],
    hazard_weight: float,
) -> dict:
    """Run A* once and return route, metrics, and CSV for a prepared analysis."""
    elevation = analysis["elevation"]
    rover_config = analysis["rover_config"]
    res = analysis["resolution_m_per_pixel"]
    slope = analysis["slope"]
    hazard_score = analysis["hazard_score"]
    blocked_mask = analysis["blocked_mask"]

    route_result = find_route(
        start=start,
        goal=goal,
        hazard_score=hazard_score,
        blocked_mask=blocked_mask,
        hazard_weight=hazard_weight,
        extra_cost=analysis.get("extra_cost"),
    )

    route = route_result["route"]
    route_found = route_result["route_found"]

    if route_found and len(route) > 0:
        route_df = route_to_dataframe(route, elevation, slope, hazard_score, res)
        metrics = enrich_metrics_with_range(
            calculate_route_metrics(route_df, rover_config, res),
            rover_config,
        )
        csv_data = dataframe_to_csv_string(route_df)
    else:
        metrics = empty_route_metrics(rover_config)
        csv_data = "step,row,col,x_m,y_m,elevation_m,slope_deg,hazard_score\n"

    if analysis.get("moonbase") is not None:
        metrics = apply_architecture_metrics(
            metrics,
            route if route_found else [],
            analysis,
            rover_config,
        )

    return {
        "route_found": route_found,
        "route": route,
        "metrics": metrics,
        "csv_data": csv_data,
        "total_cost": route_result["total_cost"],
    }


def analysis_for_rover(
    request,
    rover_name: str,
    rover_config_override: RoverConfigOverride | None = None,
) -> dict:
    """Build terrain analysis for a specific rover on the request terrain."""
    rover_config = resolve_rover_from_request(rover_name, rover_config_override)

    terrain_result = load_terrain_for_request(request)
    metadata = terrain_result["metadata"]
    res = effective_resolution(metadata, request.resolution_m_per_pixel)

    analysis = build_terrain_analysis(
        terrain_result["elevation"],
        terrain_result["nodata_mask"],
        res,
        rover_config,
    )
    analysis["metadata"] = metadata
    analysis["rover_config"] = rover_config
    return attach_moonbase(analysis, request)


def moonbase_rover(request, rover_config: dict) -> dict:
    """Copy rover config and apply per-request capability toggles."""
    rover = dict(rover_config)
    if request.psr_capable is not None:
        rover["psr_capable"] = bool(request.psr_capable)
    if request.cargo_kg is not None:
        rover["cargo_kg"] = float(request.cargo_kg)
    if request.night_survival_hours is not None:
        rover["night_survival_hours"] = float(request.night_survival_hours)
    if request.wireless_charge is not None:
        rover["wireless_charge"] = bool(request.wireless_charge)
    return rover


def attach_moonbase(analysis: dict, request) -> dict:
    """Apply Moon Base blocking and cost grids for this request."""
    rover = moonbase_rover(request, analysis["rover_config"])
    assets = [asset.model_dump() for asset in request.assets]
    try:
        constraints = build_route_constraints(
            analysis,
            rover,
            phase=request.phase,
            mission_id=request.mission,
            assets=assets,
            uncrewed=request.uncrewed,
        )
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    analysis["rover_config"] = rover
    analysis["blocked_mask"] = constraints["blocked_mask"]
    analysis["extra_cost"] = constraints["extra_cost"]
    analysis["illumination"] = constraints["illumination"]
    analysis["psr_mask"] = constraints["psr_mask"]
    analysis["shadow_mask"] = constraints["shadow_mask"]
    analysis["comms_gap_mask"] = constraints["comms_gap_mask"]
    analysis["keepout_mask"] = constraints["keepout_mask"]
    analysis["moonbase"] = constraints["summary"]
    return analysis


def _mask_list(mask: np.ndarray) -> list:
    """JSON list of bools for a numpy mask."""
    return np.array(mask, dtype=bool).tolist()


# --- Endpoints ---


@app.get("/")
def health_check():
    """Basic health check."""
    return {
        "status": "ok",
        "service": "ICAROS",
        "message": "Intelligent Crater-Aware Route Optimization System",
    }


@app.get("/api/moonbase")
def get_moonbase():
    """Phases, missions, and thresholds from the Moon Base user's guide."""
    return catalog()


@app.get("/api/rovers")
def get_rovers():
    """Return all available rover configuration profiles."""
    return {"rovers": list_rovers()}


@app.get("/api/lunar-sites")
def get_lunar_sites():
    """Return catalog of selectable lunar surface sites."""
    sites = list_lunar_sites()

    if is_supabase_configured():
        try:
            client = get_supabase_client()
            result = client.table("lunar_sites").select("*").order("name").execute()
            if result.data:
                return {"sites": result.data}
        except Exception:
            pass

    return {"sites": sites}


@app.post("/api/terrain-preview")
def terrain_preview(request: TerrainPreviewRequest):
    """Return terrain analysis grids for map display, hover, and point picking."""
    analysis = analysis_for_request(request, request.rover_name)
    elevation = analysis["elevation"]
    # Replace NaN with null-friendly values for JSON (frontend uses nodata_mask)
    elev_list = np.where(np.isfinite(elevation), elevation, 0).tolist()

    return {
        "terrain": elev_list,
        "slope": analysis["slope"].tolist(),
        "hillshade": analysis["hillshade"].tolist(),
        "illumination": analysis["illumination"].tolist(),
        "psr_mask": _mask_list(analysis["psr_mask"]),
        "comms_gap_mask": _mask_list(analysis["comms_gap_mask"]),
        "keepout_mask": _mask_list(analysis["keepout_mask"]),
        "blocked_mask": _mask_list(analysis["blocked_mask"]),
        "nodata_mask": _mask_list(analysis["nodata_mask"]),
        "metadata": analysis["metadata"],
        "max_slope_deg": analysis["rover_config"]["max_slope_deg"],
        "moonbase": analysis["moonbase"],
    }


@app.post("/api/validate-route")
def validate_route_endpoint(request: ValidateRouteRequest):
    """Check route feasibility and optional hover cell info."""
    analysis = analysis_for_request(request, request.rover_name)
    start = request.start
    goal = request.goal

    if len(start) != 2 or len(goal) != 2:
        raise HTTPException(status_code=400, detail="start and goal must be [row, col]")

    validation = validate_route(
        start=start,
        goal=goal,
        elevation=analysis["elevation"],
        slope=analysis["slope"],
        nodata_mask=analysis["nodata_mask"],
        blocked_mask=analysis["blocked_mask"],
        rover_config=analysis["rover_config"],
        resolution_m_per_pixel=analysis["resolution_m_per_pixel"],
    )

    response = validation

    if request.hover_row is not None and request.hover_col is not None:
        response["hover"] = hover_message(
            request.hover_row,
            request.hover_col,
            analysis["elevation"],
            analysis["slope"],
            analysis["nodata_mask"],
            analysis["blocked_mask"],
            analysis["rover_config"]["max_slope_deg"],
            start=start,
        )

    return response


@app.get("/api/lunar-sites/{site_id}/preview")
def site_preview(
    site_id: str,
    terrain_size: int = Query(default=200, ge=50, le=500),
    resolution_m_per_pixel: float = Query(default=20.0, gt=0),
):
    """Shortcut GET preview for a lunar site."""
    request = TerrainPreviewRequest(
        terrain_mode="site",
        site_id=site_id,
        terrain_size=terrain_size,
        resolution_m_per_pixel=resolution_m_per_pixel,
    )
    return terrain_preview(request)


@app.post("/api/plan-route")
def plan_route(request: PlanRouteRequest):
    """
    Full route planning pipeline:
    1. Load terrain (synthetic or lunar site)
    2. Compute slope, roughness, hazard
    3. Run A* pathfinding
    4. Calculate metrics and CSV export
    """
    analysis = analysis_for_request(request, request.rover_name)
    elevation = analysis["elevation"]
    metadata = analysis["metadata"]
    rover_config = analysis["rover_config"]
    grid_size = elevation.shape[0]
    res = analysis["resolution_m_per_pixel"]

    start, goal = resolve_start_goal(request, grid_size)

    validation = validate_route(
        start=start,
        goal=goal,
        elevation=elevation,
        slope=analysis["slope"],
        nodata_mask=analysis["nodata_mask"],
        blocked_mask=analysis["blocked_mask"],
        rover_config=rover_config,
        resolution_m_per_pixel=res,
    )

    plan = plan_single_route(analysis, start, goal, request.hazard_weight)
    route = plan["route"]
    route_found = plan["route_found"]
    metrics = plan["metrics"]
    csv_data = plan["csv_data"]

    coordinates = build_coordinate_info(start, goal, grid_size, res, metadata)

    elev_json = np.where(np.isfinite(elevation), elevation, 0).tolist()

    return {
        "route_found": route_found,
        "terrain": elev_json,
        "slope": analysis["slope"].tolist(),
        "hazard_score": analysis["hazard_score"].tolist(),
        "route": route,
        "metrics": metrics,
        "csv_data": csv_data,
        "metadata": metadata,
        "coordinates": coordinates,
        "start": start,
        "goal": goal,
        "validation": validation,
        "moonbase": analysis["moonbase"],
    }


@app.post("/api/compare-routes")
def compare_routes(request: CompareRoutesRequest):
    """
    Plan multiple route alternatives on identical terrain endpoints:
    - Astrolab CLV-1 at the user's hazard weight
    - Lunar Outpost Pegasus at the same hazard weight
    - Safest path for the selected rover at high hazard avoidance (hw=15)
    """
    grid_size = request.terrain_size
    start, goal = resolve_start_goal(request, grid_size)

    scenarios = [
        {
            "id": "astrolab",
            "label": "Astrolab CLV-1",
            "rover_name": "Astrolab CLV-1",
            "hazard_weight": request.hazard_weight,
            "color": "#6366f1",
        },
        {
            "id": "pegasus",
            "label": "Lunar Outpost Pegasus",
            "rover_name": "Lunar Outpost Pegasus",
            "hazard_weight": request.hazard_weight,
            "color": "#22d3ee",
        },
        {
            "id": "safest",
            "label": "Safest",
            "rover_name": request.rover_name,
            "rover_config_override": request.rover_config,
            "hazard_weight": SAFEST_HAZARD_WEIGHT,
            "color": "#22c55e",
        },
    ]

    alternatives = []
    reference_analysis = None
    reference_metadata = None

    for scenario in scenarios:
        analysis = analysis_for_rover(
            request,
            scenario["rover_name"],
            scenario.get("rover_config_override"),
        )
        if reference_analysis is None:
            reference_analysis = analysis
            reference_metadata = analysis["metadata"]

        display_rover_name = analysis["rover_config"]["name"]

        validation = validate_route(
            start=start,
            goal=goal,
            elevation=analysis["elevation"],
            slope=analysis["slope"],
            nodata_mask=analysis["nodata_mask"],
            blocked_mask=analysis["blocked_mask"],
            rover_config=analysis["rover_config"],
            resolution_m_per_pixel=analysis["resolution_m_per_pixel"],
        )

        plan = plan_single_route(
            analysis,
            start,
            goal,
            scenario["hazard_weight"],
        )

        alternatives.append(
            {
                "id": scenario["id"],
                "label": scenario["label"],
                "rover_name": display_rover_name,
                "hazard_weight": scenario["hazard_weight"],
                "color": scenario["color"],
                "route_found": plan["route_found"],
                "route": plan["route"],
                "metrics": plan["metrics"],
                "csv_data": plan["csv_data"],
                "validation": validation,
            }
        )

    moonbase = reference_analysis["moonbase"]
    alternatives, best_by_metric = score_alternatives(
        alternatives,
        mission_id=moonbase["mission"],
        uncrewed=moonbase["uncrewed"],
    )

    res = reference_analysis["resolution_m_per_pixel"]
    coordinates = build_coordinate_info(start, goal, grid_size, res, reference_metadata)
    elevation = reference_analysis["elevation"]
    elev_json = np.where(np.isfinite(elevation), elevation, 0).tolist()

    return {
        "alternatives": alternatives,
        "best_by_metric": best_by_metric,
        "terrain": elev_json,
        "hazard_score": reference_analysis["hazard_score"].tolist(),
        "metadata": reference_metadata,
        "coordinates": coordinates,
        "start": start,
        "goal": goal,
        "safest_hazard_weight": SAFEST_HAZARD_WEIGHT,
        "moonbase": moonbase,
    }


@app.post("/api/upload-dem")
async def upload_dem(
    site_id: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Upload a GeoTIFF DEM for a lunar catalog site.

    Saves to data/dems/{dem_filename} for local development use.
    """
    site = get_lunar_site(site_id)
    filename = site.get("dem_filename", f"{site_id}.tif")
    if not filename.lower().endswith((".tif", ".tiff")):
        filename = f"{filename}.tif"

    if not file.filename or not file.filename.lower().endswith((".tif", ".tiff")):
        raise HTTPException(status_code=400, detail="Only GeoTIFF (.tif) files are supported.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        from backend.dem_loader import probe_geotiff

        probe = probe_geotiff(content)
        if probe is None:
            raise HTTPException(
                status_code=400,
                detail="Could not read GeoTIFF. Ensure rasterio is installed and the file is valid.",
            )
        if not probe["usable_meter_grid"]:
            raise HTTPException(
                status_code=400,
                detail=probe["reason"] or "This GeoTIFF cannot be used as a meter grid.",
            )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Invalid GeoTIFF: {error}")

    os.makedirs(DEM_DIR, exist_ok=True)
    dest_path = os.path.join(DEM_DIR, filename)
    with open(dest_path, "wb") as output:
        output.write(content)

    return {
        "uploaded": True,
        "site_id": site_id,
        "filename": filename,
        "path": dest_path,
        "message": f"DEM saved for {site['name']}. Reload terrain preview to use real elevation.",
    }


@app.post("/api/save-run")
def save_run(request: SaveRunRequest):
    """
    Save a route run to Supabase.

    If Supabase is not configured, returns a helpful message instead of crashing.
    """
    if not is_supabase_configured():
        return {
            "saved": False,
            "message": "Supabase not configured yet.",
        }

    try:
        client = get_supabase_client()
        record = {
            "rover_name": request.rover_name,
            "terrain_size": request.terrain_size,
            "resolution_m_per_pixel": request.resolution_m_per_pixel,
            "start_row": request.start_row,
            "start_col": request.start_col,
            "goal_row": request.goal_row,
            "goal_col": request.goal_col,
            "hazard_weight": request.hazard_weight,
            "route_found": request.route_found,
            "distance_m": request.distance_m,
            "estimated_time_min": request.estimated_time_min,
            "max_slope_deg": request.max_slope_deg,
            "average_slope_deg": request.average_slope_deg,
            "average_hazard_score": request.average_hazard_score,
            "energy_score": request.energy_score,
            "route_json": request.route_json,
        }
        result = client.table("route_runs").insert(record).execute()
        return {
            "saved": True,
            "message": "Route run saved successfully.",
            "id": result.data[0]["id"] if result.data else None,
        }
    except Exception as error:
        return {
            "saved": False,
            "message": f"Failed to save run: {error}",
        }

"""
Shared terrain analysis for preview, validation, and routing.
"""

import numpy as np

from backend.hillshade import compute_hillshade, compute_south_pole_lighting
from backend.terrain_metrics import compute_hazard_score, compute_roughness, compute_slope


def build_terrain_analysis(
    elevation: np.ndarray,
    nodata_mask: np.ndarray,
    resolution_m_per_pixel: float,
    rover_config: dict,
) -> dict:
    """
    Compute slope, hazard, blocked mask, and hillshade for a terrain grid.

    Nodata cells are always blocked. Slope uses effective resolution from metadata
    when available (caller passes corrected resolution).
    """
    elev = np.array(elevation, dtype=float)
    nodata = np.array(nodata_mask, dtype=bool)

    valid = ~nodata & np.isfinite(elev)
    if np.any(valid):
        fill = float(np.nanmedian(elev[valid]))
    else:
        fill = 0.0

    elev_for_metrics = np.where(valid, elev, fill)

    slope = compute_slope(elev_for_metrics, resolution_m_per_pixel)
    roughness = compute_roughness(elev_for_metrics)
    hazard_result = compute_hazard_score(slope, roughness, rover_config)

    slope_blocked = hazard_result["blocked_mask"]
    blocked_mask = slope_blocked | nodata
    hillshade = compute_hillshade(elev, resolution_m_per_pixel)
    lighting = compute_south_pole_lighting(elev, resolution_m_per_pixel)
    valid = ~nodata

    return {
        "elevation": elev,
        "slope": slope,
        "roughness": roughness,
        "hazard_score": hazard_result["hazard_score"],
        "slope_blocked": slope_blocked,
        "blocked_mask": blocked_mask,
        "nodata_mask": nodata,
        "hillshade": hillshade,
        "illumination": np.where(valid, lighting["illumination"], 0.0),
        "psr_mask": lighting["psr_mask"] & valid,
        "shadow_mask": lighting["shadow_mask"] & valid,
        "resolution_m_per_pixel": resolution_m_per_pixel,
    }

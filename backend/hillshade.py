"""
Hillshade rendering and South Pole illumination for lunar terrain.

The display hillshade stays at a 45° sun (LROC-style). Routing uses a low
South Pole sun: about 1.5° above the horizon, sampled around the compass.
"""

import math

import numpy as np

# Sun sits on the horizon at a Moon Base in the lunar South Pole region.
SOUTH_POLE_SUN_ALTITUDE_DEG = 1.5
# Eight compass directions. 0 is north (decreasing row; row increases south).
SOUTH_POLE_AZIMUTHS_DEG = (0, 45, 90, 135, 180, 225, 270, 315)
# Lit in fewer than this fraction of azimuths counts as prolonged shadow.
SHADOW_LIT_FRACTION = 0.25
# Earth stays near the horizon as seen from the south pole. The guide gives no
# elevation for it. Half a degree ignores pebble-scale noise and still treats a
# closed crater horizon as loss of Earth view.
EARTH_ALTITUDE_DEG = 0.5

# Step toward the sun, in (row, col). Row increases south.
_SUN_STEPS = {
    0: (-1, 0),
    45: (-1, 1),
    90: (0, 1),
    135: (1, 1),
    180: (1, 0),
    225: (1, -1),
    270: (0, -1),
    315: (-1, -1),
}


def compute_hillshade(
    elevation: np.ndarray,
    resolution_m_per_pixel: float,
    azimuth_deg: float = 315.0,
    altitude_deg: float = 45.0,
) -> np.ndarray:
    """
    Compute hillshade brightness grid in range [0, 1].

    NaN elevations produce 0.0 (shadow / no-data).
    """
    elev = np.array(elevation, dtype=float)
    valid = np.isfinite(elev)

    filled = elev.copy()
    if np.any(valid):
        fill_value = float(np.nanmedian(elev[valid]))
        filled = np.where(valid, elev, fill_value)

    grad_y, grad_x = np.gradient(filled, resolution_m_per_pixel)

    azimuth = np.radians(azimuth_deg)
    altitude = np.radians(altitude_deg)

    sx = np.sin(azimuth) * np.cos(altitude)
    sy = np.cos(azimuth) * np.cos(altitude)
    sz = np.sin(altitude)

    denom = np.sqrt(grad_x ** 2 + grad_y ** 2 + 1.0)
    shade = (sx * grad_x + sy * grad_y + sz) / denom
    shade = np.clip(shade, 0.0, 1.0)
    shade = np.where(valid, shade, 0.0)

    return shade


def _sample_toward(elevation: np.ndarray, row_offset: int, col_offset: int) -> np.ndarray:
    """
    Elevation of the cell `offset` steps away, or -inf where that cell is off the grid.

    sampled[r, c] = elevation[r + row_offset, c + col_offset]
    """
    rows, cols = elevation.shape
    sampled = np.full((rows, cols), -np.inf)
    dst_r0 = max(0, -row_offset)
    dst_r1 = min(rows, rows - row_offset)
    dst_c0 = max(0, -col_offset)
    dst_c1 = min(cols, cols - col_offset)
    if dst_r1 <= dst_r0 or dst_c1 <= dst_c0:
        return sampled

    sampled[dst_r0:dst_r1, dst_c0:dst_c1] = elevation[
        dst_r0 + row_offset : dst_r1 + row_offset,
        dst_c0 + col_offset : dst_c1 + col_offset,
    ]
    return sampled


def window_horizon_m(shape: tuple[int, int], resolution_m_per_pixel: float) -> float:
    """Distance from one corner of the grid to the opposite corner, in meters."""
    rows, cols = shape
    return float(resolution_m_per_pixel) * math.hypot(max(rows - 1, 1), max(cols - 1, 1))


def _horizon_angle_from_azimuth(
    elevation: np.ndarray,
    resolution_m_per_pixel: float,
    azimuth_deg: int,
    max_distance_m: float,
) -> np.ndarray:
    """Highest terrain elevation angle along one azimuth. -inf if the ray leaves the grid immediately."""
    d_row, d_col = _SUN_STEPS[azimuth_deg]
    step_m = resolution_m_per_pixel * math.hypot(d_row, d_col)
    max_steps = max(1, int(max_distance_m / step_m))
    horizon = np.full(elevation.shape, -np.inf)

    for step in range(1, max_steps + 1):
        sampled = _sample_toward(elevation, step * d_row, step * d_col)
        on_grid = np.isfinite(sampled)
        rise = sampled - elevation
        angle = np.arctan2(rise, step * step_m)
        horizon = np.where(on_grid, np.maximum(horizon, angle), horizon)

    return horizon


def compute_south_pole_lighting(
    elevation: np.ndarray,
    resolution_m_per_pixel: float,
    altitude_deg: float = SOUTH_POLE_SUN_ALTITUDE_DEG,
    max_distance_m: float | None = None,
    earth_altitude_deg: float = EARTH_ALTITUDE_DEG,
) -> dict:
    """
    Low-sun illumination, a PSR proxy, and a closed-horizon Earth mask.

    The Sun is sampled at several azimuths around the horizon. Illumination is
    the fraction of those directions that reach the cell. A cell that is dark
    in every sample is the PSR proxy. A cell whose horizon is closed in every
    sample loses Earth as well.

    Rays run to the edge of this elevation window. This is terrain
    self-shadowing inside that window, not a lunar-year PSR catalog.
    """
    elev = np.array(elevation, dtype=float)
    valid = np.isfinite(elev)
    filled = elev.copy()
    if np.any(valid):
        filled = np.where(valid, elev, float(np.nanmedian(elev[valid])))
    else:
        filled = np.zeros_like(elev)

    if max_distance_m is None:
        max_distance_m = window_horizon_m(filled.shape, resolution_m_per_pixel)

    horizon_stack = [
        _horizon_angle_from_azimuth(
            filled,
            resolution_m_per_pixel,
            azimuth,
            max_distance_m,
        )
        for azimuth in SOUTH_POLE_AZIMUTHS_DEG
    ]
    horizon = np.stack(horizon_stack, axis=0)
    sun_alt = math.radians(altitude_deg)
    earth_alt = math.radians(earth_altitude_deg)
    shadowed = horizon > sun_alt
    earth_closed = horizon > earth_alt
    lit_fraction = 1.0 - shadowed.mean(axis=0)
    lit_fraction = np.where(valid, lit_fraction, 0.0)

    # Dark from every sampled azimuth. Nodata is not a PSR.
    psr_mask = shadowed.all(axis=0) & valid
    shadow_mask = ((lit_fraction < SHADOW_LIT_FRACTION) | psr_mask) & valid
    earth_blocked_mask = earth_closed.all(axis=0) & valid

    return {
        "illumination": lit_fraction,
        "psr_mask": psr_mask,
        "shadow_mask": shadow_mask,
        "earth_blocked_mask": earth_blocked_mask,
    }

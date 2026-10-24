"""
Terrain metric calculations: slope, roughness, and hazard scoring.

All functions work on 2D numpy grids and are written for readability.
"""

import numpy as np


def compute_slope(elevation, resolution_m_per_pixel):
    """
    Compute slope angle in degrees at each grid cell.

    Uses numpy gradient to estimate elevation change in x and y,
    then converts to slope angle in degrees.
    """
    # Gradient gives rate of change in elevation per grid cell
    grad_y, grad_x = np.gradient(elevation, resolution_m_per_pixel)

    # Slope angle = arctan(sqrt(dx^2 + dy^2))
    slope_rad = np.arctan(np.sqrt(grad_x ** 2 + grad_y ** 2))
    slope_deg = np.degrees(slope_rad)

    return slope_deg


def compute_roughness(elevation, window_size=5):
    """
    Compute local surface roughness using a sliding window.

    Roughness is the standard deviation of elevation within each window.
    Higher values mean bumpier terrain.
    """
    from scipy.ndimage import uniform_filter

    size = elevation.shape[0]
    half_window = window_size // 2

    # Mean elevation in each window
    mean_elevation = uniform_filter(elevation, size=window_size, mode="nearest")

    # Mean of squared elevation in each window
    mean_squared = uniform_filter(elevation ** 2, size=window_size, mode="nearest")

    # Variance = E[X^2] - E[X]^2, then standard deviation
    variance = np.clip(mean_squared - mean_elevation ** 2, 0, None)
    roughness = np.sqrt(variance)

    return roughness


def normalize_grid(grid):
    """
    Normalize a grid to the range [0, 1].

    If all values are the same, return zeros.
    """
    grid_min = grid.min()
    grid_max = grid.max()

    if grid_max - grid_min < 1e-10:
        return np.zeros_like(grid)

    return (grid - grid_min) / (grid_max - grid_min)


def compute_hazard_score(slope, roughness, rover_config):
    """
    Combine slope and roughness into a hazard score grid.

    Also returns a blocked_mask where slope exceeds the rover's max capability.

    Parameters
    ----------
    slope : 2D array of slope in degrees
    roughness : 2D array of roughness values
    rover_config : dict with max_slope_deg and roughness_tolerance

    Returns
    -------
    dict with:
        hazard_score : 2D array (higher = more dangerous)
        blocked_mask : 2D boolean array (True = impassable)
    """
    max_slope = rover_config["max_slope_deg"]
    roughness_tolerance = rover_config["roughness_tolerance"]

    # Normalize slope and roughness to 0-1 range
    norm_slope = normalize_grid(slope)
    norm_roughness = normalize_grid(roughness)

    # Base hazard is a weighted combination
    hazard_score = 0.6 * norm_slope + 0.4 * norm_roughness

    # Extra penalty when slope is close to or above rover limit
    # Penalty ramps up as slope approaches max_slope_deg
    slope_ratio = slope / max_slope
    penalty = np.where(
        slope_ratio > 0.7,
        (slope_ratio - 0.7) * 3.0,
        0.0,
    )
    hazard_score = hazard_score + penalty

    # Cells where slope exceeds rover max are completely blocked
    blocked_mask = slope > max_slope

    # Roughness above tolerance adds extra hazard (but does not block)
    roughness_penalty = np.where(
        roughness > roughness_tolerance * roughness.max(),
        0.5,
        0.0,
    )
    hazard_score = hazard_score + roughness_penalty

    return {
        "hazard_score": hazard_score,
        "blocked_mask": blocked_mask,
    }

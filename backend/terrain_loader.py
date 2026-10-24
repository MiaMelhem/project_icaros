"""
Synthetic lunar-like terrain generation for the ICAROS MVP.

Real NASA DEM data can be loaded here in a future version.
For now we create a grid with rolling hills, noise, and crater depressions.
"""

import numpy as np


def load_synthetic_terrain(size=200, resolution_m_per_pixel=20, seed=42):
    """
    Generate a synthetic lunar South Pole-like elevation grid.

    Parameters
    ----------
    size : int
        Number of rows and columns in the square grid.
    resolution_m_per_pixel : float
        Meters represented by each grid cell (used in metadata only here).
    seed : int
        Random seed so the same terrain can be reproduced.

    Returns
    -------
    dict with keys:
        elevation : 2D numpy array of elevation values in meters
        metadata : dict with size, resolution, and generation info
    """
    rng = np.random.default_rng(seed)

    # Create coordinate grids from -1 to 1
    x = np.linspace(-1, 1, size)
    y = np.linspace(-1, 1, size)
    xx, yy = np.meshgrid(x, y)

    # Rolling base terrain using sine waves
    rolling = (
        30 * np.sin(3 * xx)
        + 20 * np.cos(2 * yy)
        + 15 * np.sin(xx + yy)
    )

    # Small-scale random noise for surface texture
    noise = rng.normal(0, 3, size=(size, size))

    # Start with rolling terrain plus noise
    elevation = rolling + noise

    # Add several crater-like circular depressions
    num_craters = 8
    for _ in range(num_craters):
        # Random crater center within the grid
        center_row = rng.integers(20, size - 20)
        center_col = rng.integers(20, size - 20)

        # Random crater radius in grid cells
        radius = rng.integers(8, 25)

        # Random crater depth in meters
        depth = rng.uniform(15, 40)

        # Distance from each cell to crater center
        row_indices = np.arange(size)[:, None]
        col_indices = np.arange(size)[None, :]
        distance = np.sqrt(
            (row_indices - center_row) ** 2 + (col_indices - center_col) ** 2
        )

        # Bowl-shaped depression: subtract elevation inside the crater
        crater_mask = distance <= radius
        bowl_shape = depth * (1 - (distance / radius) ** 2)
        bowl_shape = np.clip(bowl_shape, 0, None)
        elevation[crater_mask] -= bowl_shape[crater_mask]

    # Shift so minimum elevation is near zero (easier to read)
    elevation = elevation - elevation.min() + 10

    metadata = {
        "size": size,
        "resolution_m_per_pixel": resolution_m_per_pixel,
        "source": "synthetic",
        "description": "Synthetic lunar-like terrain with craters for MVP demo.",
    }

    return {
        "elevation": elevation,
        "metadata": metadata,
    }

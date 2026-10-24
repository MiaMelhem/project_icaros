"""
Site-specific synthetic elevation models for lunar catalog sites.

Each site gets a distinct terrain character (massif, crater, landing plain, rim)
so elevation and hillshade maps look unique until real NASA DEMs are added.
"""

import numpy as np
from scipy.ndimage import gaussian_filter

from backend.lunar_sites import get_lunar_site, site_seed


def _crater_bowl(
    elevation: np.ndarray,
    center_row: float,
    center_col: float,
    radius: float,
    depth: float,
    rng: np.random.Generator,
    rim_height: float = 0.0,
) -> None:
    """Subtract a bowl depression; optional raised rim ring."""
    size = elevation.shape[0]
    rows = np.arange(size)[:, None]
    cols = np.arange(size)[None, :]
    distance = np.sqrt((rows - center_row) ** 2 + (cols - center_col) ** 2)

    inside = distance <= radius
    bowl = depth * (1 - (distance / max(radius, 1)) ** 2)
    bowl = np.clip(bowl, 0, None)
    elevation[inside] -= bowl[inside]

    if rim_height > 0:
        rim_band = (distance > radius * 0.85) & (distance < radius * 1.15)
        elevation[rim_band] += rim_height * rng.uniform(0.6, 1.0)


def _gaussian_peak(
    elevation: np.ndarray,
    center_row: float,
    center_col: float,
    amplitude: float,
    sigma: float,
) -> None:
    size = elevation.shape[0]
    rows = np.arange(size)[:, None]
    cols = np.arange(size)[None, :]
    distance_sq = (rows - center_row) ** 2 + (cols - center_col) ** 2
    elevation += amplitude * np.exp(-distance_sq / (2 * sigma**2))


def _rim_wall(
    elevation: np.ndarray,
    axis: str,
    position: float,
    height: float,
    width: float,
) -> None:
    """Add a steep scarp along a row or column fraction."""
    size = elevation.shape[0]
    coords = np.linspace(0, 1, size)
    if axis == "row":
        profile = np.exp(-((coords - position) ** 2) / (2 * (width / size) ** 2))
        elevation += height * profile[:, None]
    else:
        profile = np.exp(-((coords - position) ** 2) / (2 * (width / size) ** 2))
        elevation += height * profile[None, :]


def generate_malapert_massif(size: int, rng: np.random.Generator) -> np.ndarray:
    """Elevated peak with sunlit ridges — Malapert Massif."""
    elevation = np.zeros((size, size), dtype=float)
    _gaussian_peak(elevation, size * 0.45, size * 0.52, amplitude=85, sigma=size * 0.12)
    _gaussian_peak(elevation, size * 0.38, size * 0.58, amplitude=45, sigma=size * 0.08)

    x = np.linspace(-1, 1, size)
    xx, yy = np.meshgrid(x, x)
    elevation += 12 * np.sin(2.5 * xx + 0.4) * np.cos(1.8 * yy)
    elevation += rng.normal(0, 1.5, (size, size))
    elevation = gaussian_filter(elevation, sigma=1.2)

    _crater_bowl(elevation, size * 0.72, size * 0.28, radius=size * 0.06, depth=18, rng=rng)
    _crater_bowl(elevation, size * 0.22, size * 0.75, radius=size * 0.04, depth=10, rng=rng)
    return elevation


def generate_haworth_crater(size: int, rng: np.random.Generator) -> np.ndarray:
    """Large complex crater with central peaks — Haworth."""
    elevation = rng.normal(0, 2, (size, size)) + 40
    elevation = gaussian_filter(elevation, sigma=2.0)

    _crater_bowl(
        elevation,
        size * 0.5,
        size * 0.5,
        radius=size * 0.32,
        depth=55,
        rng=rng,
        rim_height=8,
    )
    _gaussian_peak(elevation, size * 0.5, size * 0.5, amplitude=22, sigma=size * 0.04)

    for _ in range(5):
        _crater_bowl(
            elevation,
            rng.uniform(size * 0.15, size * 0.85),
            rng.uniform(size * 0.15, size * 0.85),
            radius=rng.uniform(size * 0.03, size * 0.08),
            depth=rng.uniform(8, 22),
            rng=rng,
        )
    return elevation


def generate_nobile_crater(size: int, rng: np.random.Generator) -> np.ndarray:
    """Relatively flat Artemis candidate landing terrain — Nobile."""
    elevation = np.full((size, size), 32.0, dtype=float)
    x = np.linspace(-1, 1, size)
    xx, yy = np.meshgrid(x, x)
    elevation += 4 * np.sin(1.2 * xx) + 3 * np.cos(1.0 * yy)
    elevation += rng.normal(0, 0.8, (size, size))
    elevation = gaussian_filter(elevation, sigma=2.5)

    _crater_bowl(elevation, size * 0.62, size * 0.38, radius=size * 0.09, depth=12, rng=rng)
    _crater_bowl(elevation, size * 0.25, size * 0.68, radius=size * 0.05, depth=6, rng=rng)
    return elevation


def generate_amundsen_rim(size: int, rng: np.random.Generator) -> np.ndarray:
    """Rugged rim with mixed slopes — Amundsen."""
    elevation = rng.normal(0, 3, (size, size)) + 25
    elevation = gaussian_filter(elevation, sigma=1.5)

    _rim_wall(elevation, "row", 0.35, height=35, width=size * 0.08)
    _crater_bowl(
        elevation,
        size * 0.55,
        size * 0.5,
        radius=size * 0.28,
        depth=40,
        rng=rng,
        rim_height=12,
    )

    for _ in range(6):
        _crater_bowl(
            elevation,
            rng.uniform(size * 0.1, size * 0.9),
            rng.uniform(size * 0.1, size * 0.9),
            radius=rng.uniform(size * 0.02, size * 0.06),
            depth=rng.uniform(6, 16),
            rng=rng,
            rim_height=3,
        )
    return elevation


def generate_shackleton_fallback(size: int, rng: np.random.Generator) -> np.ndarray:
    """Fallback if real Shackleton DEM missing — rim-focused crater."""
    elevation = np.full((size, size), 20.0, dtype=float)
    _crater_bowl(
        elevation,
        size * 0.55,
        size * 0.48,
        radius=size * 0.35,
        depth=60,
        rng=rng,
        rim_height=15,
    )
    _rim_wall(elevation, "col", 0.42, height=25, width=size * 0.06)
    elevation += rng.normal(0, 2, (size, size))
    return gaussian_filter(elevation, sigma=1.0)


GENERATORS = {
    "shackleton-rim": generate_shackleton_fallback,
    "malapert-massif": generate_malapert_massif,
    "haworth-crater": generate_haworth_crater,
    "nobile-crater": generate_nobile_crater,
    "amundsen-rim": generate_amundsen_rim,
}


def generate_site_elevation(site_id: str, size: int = 1024) -> np.ndarray:
    """
    Build a square elevation grid (meters) for a catalog site.

    Uses a site-specific generator and deterministic seed.
    """
    if site_id not in GENERATORS:
        raise KeyError(f"No terrain generator for site: {site_id}")

    seed = site_seed(site_id)
    rng = np.random.default_rng(seed)
    elevation = GENERATORS[site_id](size, rng)
    elevation = elevation - np.nanmin(elevation) + 10.0
    return elevation.astype(np.float32)


def site_elevation_metadata(site_id: str) -> dict:
    """Human-readable metadata for generated site DEMs."""
    site = get_lunar_site(site_id)
    return {
        "site_id": site_id,
        "site_name": site["name"],
        "center_lat": site["center_lat"],
        "center_lon": site["center_lon"],
        "window_size_m": site["window_size_m"],
        "source": "ICAROS site elevation model",
        "description": (
            f"Site-specific elevation model for {site['name']} "
            f"({site['description']}). Replace with NASA GeoTIFF when available."
        ),
    }

"""
Load lunar terrain for a catalog site.

Resolution order:
1. Local GeoTIFF at data/dems/{filename}
2. Supabase Storage (lunar-dems bucket) when dem_storage_path is set
3. Site-seeded synthetic terrain fallback

Real DEMs are not stretched onto a square. The output is a window of
``size * resolution_m_per_pixel`` meters. At the defaults that is 4 km at 20 m.

Center rule (Option B):
- Use the catalog latitude/longitude when it falls inside the source footprint.
- Otherwise center the window on the source raster bounds. That center is the
  middle of the file, not the named landmark. The catalog coordinate and the
  offset are kept in the metadata.

Each output cell is the mean of valid source pixel centers that fall inside it.
A cell with less than half of the expected source samples stays nodata. Missing
elevation is not filled. Geographic degree rasters are rejected rather than
treated as meters.
"""

import math
import os
import re

import numpy as np

from backend.dem_storage import download_dem_bytes
from backend.lunar_sites import get_lunar_site, site_seed
from backend.terrain_loader import load_synthetic_terrain

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
DEM_DIR = os.path.join(PROJECT_ROOT, "data", "dems")
STORAGE_BUCKET = "lunar-dems"

# Output cell stays nodata below this fraction of a full cell's source samples.
MIN_VALID_FRACTION = 0.5
# Below this nodata fraction the crop is called complete. Above 0.5 it is unsuitable.
PARTIAL_NODATA_FRACTION = 0.05
UNSUITABLE_NODATA_FRACTION = 0.5

_PARAM_RE = re.compile(
    r'PARAMETER\["([^"]+)",\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\]'
)
_SPHEROID_RE = re.compile(r'SPHEROID\["[^"]+",\s*([+-]?\d+(?:\.\d+)?)')


class DemNotUsable(Exception):
    """The file opened, but it cannot supply a meter grid."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _dem_path(site_id: str) -> str:
    site = get_lunar_site(site_id)
    return os.path.join(DEM_DIR, site.get("dem_filename", f"{site_id}.tif"))


def _is_nodata_value(value: np.ndarray, nodata) -> np.ndarray:
    """Identify invalid DEM pixels, including extreme sentinel values."""
    invalid = ~np.isfinite(value)
    if nodata is not None and np.isfinite(nodata):
        invalid = invalid | np.isclose(value, float(nodata), rtol=0, atol=1.0)
    invalid = invalid | (value < -1e9)
    return invalid


def _open_dataset(source):
    """Open a path or bytes. Returns (memory_file_or_none, dataset)."""
    import rasterio
    from rasterio.io import MemoryFile

    if isinstance(source, bytes):
        memory = MemoryFile(source)
        return memory, memory.open()
    if not isinstance(source, str) or not os.path.isfile(source):
        return None, None
    return None, rasterio.open(source)


def _close_dataset(memory, dataset) -> None:
    if dataset is not None:
        dataset.close()
    if memory is not None:
        memory.close()


def _rotated(transform) -> bool:
    return abs(transform.b) > 1e-6 or abs(transform.d) > 1e-6


def _projection_params(crs) -> dict | None:
    """Return a meter-grid description, or None for a geographic CRS."""
    if crs is None or getattr(crs, "is_geographic", False):
        return None
    units = (getattr(crs, "linear_units", "") or "").lower()
    if units not in {"metre", "meter", "m"}:
        return None
    wkt = crs.to_wkt() or ""
    if "Polar_Stereographic" not in wkt:
        return {"kind": "projected_meters"}

    params = {name.lower(): float(value) for name, value in _PARAM_RE.findall(wkt)}
    radius_match = _SPHEROID_RE.search(wkt)
    radius = float(radius_match.group(1)) if radius_match else None
    lat0 = params.get("latitude_of_origin", params.get("lat_0"))
    lon0 = params.get("central_meridian", params.get("lon_0", 0.0))
    false_easting = params.get("false_easting", params.get("x_0", 0.0))
    false_northing = params.get("false_northing", params.get("y_0", 0.0))
    if radius is None or lat0 is None or abs(lat0 + 90.0) > 1e-6:
        return {"kind": "projected_meters"}
    return {
        "kind": "south_polar_stereographic",
        "radius_m": radius,
        "lon0_deg": lon0,
        "false_easting": false_easting,
        "false_northing": false_northing,
    }


def forward_south_polar(lat_deg: float, lon_deg: float, projection: dict) -> tuple[float, float]:
    """South-polar stereographic on a sphere, matching the included DEM CRS."""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg - projection["lon0_deg"])
    rho = 2.0 * projection["radius_m"] * math.tan(math.pi / 4.0 + lat / 2.0)
    x = rho * math.sin(lon) + projection["false_easting"]
    y = rho * math.cos(lon) + projection["false_northing"]
    return x, y


def inverse_south_polar(x: float, y: float, projection: dict) -> tuple[float, float]:
    """Inverse of forward_south_polar. Returns latitude, longitude in degrees."""
    x = x - projection["false_easting"]
    y = y - projection["false_northing"]
    rho = math.hypot(x, y)
    lon = math.degrees(math.atan2(x, y)) + projection["lon0_deg"]
    lon = ((lon + 180.0) % 360.0) - 180.0
    if rho == 0.0:
        return -90.0, lon
    lat = math.degrees(2.0 * math.atan(rho / (2.0 * projection["radius_m"])) - math.pi / 2.0)
    return lat, lon


def _snap(value: float, origin: float, step: float) -> float:
    """Nearest source-grid edge. Step may be negative."""
    if step == 0:
        return value
    slots = round((value - origin) / step)
    return origin + slots * step


def _point_inside(x: float, y: float, bounds) -> bool:
    return bounds.left <= x <= bounds.right and bounds.bottom <= y <= bounds.top


def choose_crop_center(dataset, catalog_lat: float, catalog_lon: float, projection: dict) -> dict:
    """Pick the window center. A fallback center is the file center, not the landmark."""
    bounds = dataset.bounds
    raster_x = (bounds.left + bounds.right) / 2.0
    raster_y = (bounds.bottom + bounds.top) / 2.0
    choice = {
        "x": raster_x,
        "y": raster_y,
        "rule": "source_bounds_center",
        "catalog_inside": False,
        "catalog_x": None,
        "catalog_y": None,
        "catalog_offset_m": None,
    }
    if projection.get("kind") != "south_polar_stereographic":
        choice["note"] = (
            "Catalog latitude and longitude were not projected. "
            "This file is a meter grid, but it is not the Moon south-polar "
            "stereographic projection of the included DEMs. "
            "The window is centered on the raster bounds, not on the landmark name."
        )
        return choice

    catalog_x, catalog_y = forward_south_polar(catalog_lat, catalog_lon, projection)
    offset = math.hypot(catalog_x - raster_x, catalog_y - raster_y)
    inside = _point_inside(catalog_x, catalog_y, bounds)
    choice["catalog_x"] = catalog_x
    choice["catalog_y"] = catalog_y
    choice["catalog_offset_m"] = offset
    choice["catalog_inside"] = inside
    if inside:
        choice["x"] = catalog_x
        choice["y"] = catalog_y
        choice["rule"] = "catalog_latlon"
        choice["note"] = (
            f"Window centered on the catalog coordinate {catalog_lat:.4f}°, "
            f"{catalog_lon:.4f}°, which falls inside this DEM "
            f"({offset:.0f} m from the raster center)."
        )
        return choice

    choice["note"] = (
        f"Catalog label {catalog_lat:.4f}°, {catalog_lon:.4f}° is {offset:.0f} m "
        "outside this DEM. The window is centered on the source raster bounds, "
        "not on the named landmark."
    )
    return choice


def coverage_status(nodata_fraction: float) -> str:
    """complete, partial, or unsuitable. Partial crops are returned and flagged."""
    if nodata_fraction >= UNSUITABLE_NODATA_FRACTION:
        return "unsuitable"
    if nodata_fraction >= PARTIAL_NODATA_FRACTION:
        return "partial"
    return "complete"


def resample_valid_mean(
    elevation: np.ndarray,
    transform,
    nodata,
    left: float,
    top: float,
    size: int,
    resolution_m: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Average valid source pixel centers into a north-up grid.

    A source pixel contributes only to the output cell that contains its center.
    Cells below the valid-sample threshold stay nodata.
    """
    rows, cols = np.indices(elevation.shape)
    x = transform.c + (cols + 0.5) * transform.a
    y = transform.f + (rows + 0.5) * transform.e
    valid = ~_is_nodata_value(elevation, nodata)

    out_col = np.floor((x - left) / resolution_m).astype(np.int64)
    out_row = np.floor((top - y) / resolution_m).astype(np.int64)
    inside = (
        valid
        & (out_col >= 0)
        & (out_col < size)
        & (out_row >= 0)
        & (out_row < size)
    )

    flat = out_row[inside] * size + out_col[inside]
    sums = np.bincount(flat, weights=elevation[inside], minlength=size * size)
    counts = np.bincount(flat, minlength=size * size).astype(float)

    src_area = abs(float(transform.a) * float(transform.e))
    expected = (resolution_m ** 2) / src_area if src_area > 0 else 1.0
    keep = counts >= (MIN_VALID_FRACTION * expected)

    averaged = np.full(size * size, np.nan, dtype=float)
    averaged[keep] = sums[keep] / counts[keep]
    grid = np.reshape(averaged, (size, size))
    nodata_mask = np.reshape(~keep, (size, size))
    return grid, nodata_mask


def _source_indexes(dataset, left, right, bottom, top) -> tuple[int, int, int, int]:
    transform = dataset.transform
    col_a = (left - transform.c) / transform.a
    col_b = (right - transform.c) / transform.a
    row_a = (top - transform.f) / transform.e
    row_b = (bottom - transform.f) / transform.e
    col0 = max(0, math.floor(min(col_a, col_b)) - 1)
    col1 = min(dataset.width, math.ceil(max(col_a, col_b)) + 1)
    row0 = max(0, math.floor(min(row_a, row_b)) - 1)
    row1 = min(dataset.height, math.ceil(max(row_a, row_b)) + 1)
    return row0, row1, col0, col1


def load_dem_grid(
    dataset,
    catalog_lat: float,
    catalog_lon: float,
    size: int,
    resolution_m: float,
) -> dict:
    """Crop and resample one open raster to a square meter grid."""
    if _rotated(dataset.transform):
        raise DemNotUsable(
            "This DEM has a rotated geotransform. ICAROS does not resample rotated rasters."
        )
    if abs(dataset.transform.a) <= 0 or abs(dataset.transform.e) <= 0:
        raise DemNotUsable("This DEM has a zero pixel size.")

    projection = _projection_params(dataset.crs)
    if projection is None:
        raise DemNotUsable(
            "This DEM is not a projected meter grid. "
            "Geographic degree rasters are not treated as meters."
        )

    center = choose_crop_center(dataset, catalog_lat, catalog_lon, projection)
    window_m = float(size) * float(resolution_m)
    left = _snap(center["x"] - window_m / 2.0, dataset.transform.c, dataset.transform.a)
    top = _snap(center["y"] + window_m / 2.0, dataset.transform.f, dataset.transform.e)
    right = left + window_m
    bottom = top - window_m
    center_x = (left + right) / 2.0
    center_y = (bottom + top) / 2.0

    row0, row1, col0, col1 = _source_indexes(dataset, left, right, bottom, top)
    if row1 <= row0 or col1 <= col0:
        elevation = np.full((size, size), np.nan)
        nodata_mask = np.ones((size, size), dtype=bool)
    else:
        from rasterio.windows import Window
        from rasterio.windows import transform as window_transform

        window = Window(col0, row0, col1 - col0, row1 - row0)
        band = dataset.read(1, window=window)
        raw = np.empty(band.shape, dtype=float)
        raw[:] = band
        elevation, nodata_mask = resample_valid_mean(
            raw,
            window_transform(window, dataset.transform),
            dataset.nodata,
            left,
            top,
            size,
            resolution_m,
        )

    crop_lat = None
    crop_lon = None
    if projection.get("kind") == "south_polar_stereographic":
        crop_lat, crop_lon = inverse_south_polar(center_x, center_y, projection)

    src_res_x = abs(float(dataset.transform.a))
    src_res_y = abs(float(dataset.transform.e))
    if src_res_x <= resolution_m + 1e-6 and src_res_y <= resolution_m + 1e-6:
        resolution_note = (
            f"Source pixels are {src_res_x:.2f} m by {src_res_y:.2f} m. "
            f"Each {resolution_m:.0f} m cell is the mean of valid source pixel centers. "
            "Resampling does not add terrain detail."
        )
    else:
        resolution_note = (
            f"Source pixels are {src_res_x:.2f} m by {src_res_y:.2f} m, coarser than "
            f"the {resolution_m:.2f} m output. Cells without a source pixel center are "
            "nodata. The grid does not invent elevation detail."
        )

    nodata_fraction = float(nodata_mask.mean())
    status = coverage_status(nodata_fraction)
    if status == "unsuitable":
        coverage_note = (
            f"{nodata_fraction:.1%} of this crop has no elevation. "
            "The crop is not suitable for routing and was not replaced with synthetic terrain."
        )
    elif status == "partial":
        coverage_note = (
            f"{nodata_fraction:.1%} of output cells have no elevation and stay blocked. "
            "The crop is usable, but it is not a complete map."
        )
    else:
        coverage_note = f"Nodata fraction is {nodata_fraction:.1%}."

    return {
        "elevation": elevation,
        "nodata_mask": nodata_mask,
        "source_width": int(dataset.width),
        "source_height": int(dataset.height),
        "source_res_x_m": src_res_x,
        "source_res_y_m": src_res_y,
        "source_crs": dataset.crs.to_wkt() if dataset.crs else "",
        "source_bounds_m": [
            float(dataset.bounds.left),
            float(dataset.bounds.bottom),
            float(dataset.bounds.right),
            float(dataset.bounds.top),
        ],
        "crop_left_m": float(left),
        "crop_bottom_m": float(bottom),
        "crop_right_m": float(right),
        "crop_top_m": float(top),
        "crop_center_x_m": float(center_x),
        "crop_center_y_m": float(center_y),
        "crop_center_lat": None if crop_lat is None else float(crop_lat),
        "crop_center_lon": None if crop_lon is None else float(crop_lon),
        "center_rule": center["rule"],
        "center_note": center.get("note", ""),
        "catalog_inside_source": bool(center["catalog_inside"]),
        "catalog_offset_m": (
            None if center["catalog_offset_m"] is None else float(center["catalog_offset_m"])
        ),
        "window_m": float(window_m),
        "output_cell_m": float(resolution_m),
        "resolution_note": resolution_note,
        "resampling": "mean_of_valid_source_pixel_centers",
        "min_valid_fraction": MIN_VALID_FRACTION,
        "nodata_fraction": nodata_fraction,
        "coverage_status": status,
        "coverage_note": coverage_note,
    }


def probe_geotiff(source) -> dict | None:
    """Open a GeoTIFF and report whether it can be used as a meter grid."""
    memory, dataset = _open_dataset(source)
    if dataset is None:
        return None
    try:
        projection = _projection_params(dataset.crs)
        rotated = _rotated(dataset.transform)
        if rotated:
            reason = "Rotated geotransforms are not resampled."
        elif projection is None:
            reason = (
                "The file is not a projected meter grid. "
                "Degree coordinates are not treated as meters."
            )
        else:
            reason = ""
        return {
            "width": int(dataset.width),
            "height": int(dataset.height),
            "crs": dataset.crs.to_string() if dataset.crs else None,
            "res_m": [abs(float(dataset.transform.a)), abs(float(dataset.transform.e))],
            "usable_meter_grid": projection is not None and not rotated,
            "reason": reason,
        }
    finally:
        _close_dataset(memory, dataset)


def _load_geotiff_grid(source, site: dict, size: int, resolution_m: float) -> dict | None:
    """Load one DEM source. None if missing. Raises DemNotUsable if unusable."""
    memory, dataset = _open_dataset(source)
    if dataset is None:
        return None
    try:
        return load_dem_grid(
            dataset,
            float(site["center_lat"]),
            float(site["center_lon"]),
            size,
            resolution_m,
        )
    finally:
        _close_dataset(memory, dataset)


def _metadata_from_grid(site: dict, grid: dict, size: int, source: str, description: str) -> dict:
    center_lat = grid["crop_center_lat"]
    center_lon = grid["crop_center_lon"]
    if center_lat is None:
        center_lat = float(site["center_lat"])
        center_lon = float(site["center_lon"])
    return {
        "size": size,
        "resolution_m_per_pixel": float(grid["output_cell_m"]),
        "effective_resolution_m_per_pixel": float(grid["output_cell_m"]),
        "source": source,
        "terrain_kind": "real_dem",
        "site_id": site["id"],
        "site_name": site["name"],
        "center_lat": float(center_lat),
        "center_lon": float(center_lon),
        "catalog_center_lat": float(site["center_lat"]),
        "catalog_center_lon": float(site["center_lon"]),
        "window_size_m": float(grid["window_m"]),
        "description": description,
        "nodata_fraction": float(grid["nodata_fraction"]),
        "coverage_status": grid["coverage_status"],
        "coverage_note": grid["coverage_note"],
        "center_rule": grid["center_rule"],
        "center_note": grid["center_note"],
        "catalog_inside_source": grid["catalog_inside_source"],
        "catalog_offset_m": grid["catalog_offset_m"],
        "source_width": grid["source_width"],
        "source_height": grid["source_height"],
        "source_res_x_m": grid["source_res_x_m"],
        "source_res_y_m": grid["source_res_y_m"],
        "source_crs": grid["source_crs"],
        "source_bounds_m": grid["source_bounds_m"],
        "crop_bounds_m": [
            grid["crop_left_m"],
            grid["crop_bottom_m"],
            grid["crop_right_m"],
            grid["crop_top_m"],
        ],
        "crop_center_xy_m": [grid["crop_center_x_m"], grid["crop_center_y_m"]],
        "resampling": grid["resampling"],
        "min_valid_fraction": grid["min_valid_fraction"],
        "resolution_note": grid["resolution_note"],
    }


def _real_description(site: dict, grid: dict) -> str:
    return (
        f"{site.get('source', 'GeoTIFF')} for {site['name']}. "
        f"Cropped to {grid['window_m']:.0f} m at {grid['output_cell_m']:.0f} m cells. "
        f"{grid['center_note']} {grid['coverage_note']} {grid['resolution_note']}"
    )


def load_site_terrain(
    site_id: str,
    size: int = 200,
    resolution_m_per_pixel: float = 20.0,
) -> dict:
    """
    Load elevation for a lunar catalog site.

    Real DEM grids use ``resolution_m_per_pixel`` as the output cell size.
    ``terrain_kind`` is ``real_dem`` or ``synthetic``.
    """
    site = get_lunar_site(site_id)
    dem_path = _dem_path(site_id)
    skipped = []

    try:
        grid = _load_geotiff_grid(dem_path, site, size, resolution_m_per_pixel)
    except DemNotUsable as error:
        grid = None
        skipped.append(f"Local file skipped: {error.reason}")

    source_name = "dem_local"
    if grid is None and not skipped and not os.path.isfile(dem_path):
        skipped.append("No local GeoTIFF.")

    if grid is None:
        storage_path = _resolve_storage_path(site_id, site)
        if storage_path:
            dem_bytes = download_dem_bytes(storage_path, bucket=STORAGE_BUCKET)
            if dem_bytes:
                try:
                    grid = _load_geotiff_grid(dem_bytes, site, size, resolution_m_per_pixel)
                    source_name = "dem_supabase"
                except DemNotUsable as error:
                    skipped.append(f"Stored file skipped: {error.reason}")

    if grid is not None:
        description = _real_description(site, grid)
        if skipped:
            description = f"{description} {' '.join(skipped)}"
        return {
            "elevation": grid["elevation"],
            "nodata_mask": grid["nodata_mask"],
            "metadata": _metadata_from_grid(site, grid, size, source_name, description),
        }

    seed = site_seed(site_id)
    synthetic = load_synthetic_terrain(
        size=size,
        resolution_m_per_pixel=resolution_m_per_pixel,
        seed=seed,
    )
    elevation = synthetic["elevation"]
    why = " ".join(skipped) if skipped else "No DEM file was found."
    description = (
        f"Site-seeded synthetic terrain for {site['name']}, not a NASA DEM. {why} "
        "The catalog latitude and longitude are labels only."
    )
    metadata = {
        "size": size,
        "resolution_m_per_pixel": float(resolution_m_per_pixel),
        "effective_resolution_m_per_pixel": float(resolution_m_per_pixel),
        "source": "site_synthetic",
        "terrain_kind": "synthetic",
        "site_id": site_id,
        "site_name": site["name"],
        "center_lat": float(site["center_lat"]),
        "center_lon": float(site["center_lon"]),
        "catalog_center_lat": float(site["center_lat"]),
        "catalog_center_lon": float(site["center_lon"]),
        "window_size_m": float(size) * float(resolution_m_per_pixel),
        "description": description,
        "nodata_fraction": 0.0,
        "coverage_status": "synthetic",
        "coverage_note": "Synthetic terrain has no source nodata mask.",
        "center_rule": "catalog_label_only",
        "center_note": (
            "Synthetic terrain has no DEM georeferencing. "
            "Displayed latitude and longitude are the catalog label, not a measured crop."
        ),
        "catalog_inside_source": False,
        "catalog_offset_m": None,
        "resampling": "none",
        "resolution_note": "Synthetic elevations are generated on the requested grid.",
    }
    return {
        "elevation": elevation,
        "nodata_mask": np.zeros(elevation.shape, dtype=bool),
        "metadata": metadata,
    }


def load_synthetic_terrain_full(
    size: int = 200,
    resolution_m_per_pixel: float = 20.0,
) -> dict:
    """Load synthetic terrain with a consistent return shape."""
    synthetic = load_synthetic_terrain(
        size=size,
        resolution_m_per_pixel=resolution_m_per_pixel,
    )
    elevation = synthetic["elevation"]
    metadata = {
        **synthetic["metadata"],
        "effective_resolution_m_per_pixel": resolution_m_per_pixel,
        "nodata_fraction": 0.0,
        "terrain_kind": "synthetic",
        "coverage_status": "synthetic",
        "center_rule": "none",
        "center_note": "Synthetic terrain is not a georeferenced DEM crop.",
        "window_size_m": float(size) * float(resolution_m_per_pixel),
        "resampling": "none",
    }
    return {
        "elevation": elevation,
        "nodata_mask": np.zeros(elevation.shape, dtype=bool),
        "metadata": metadata,
    }


def _resolve_storage_path(site_id: str, site: dict) -> str | None:
    """Get Supabase storage path from site dict or DB."""
    if site.get("dem_storage_path"):
        return site["dem_storage_path"]

    try:
        from backend.dem_storage import get_supabase_client, is_supabase_storage_configured

        if not is_supabase_storage_configured():
            return None
        client = get_supabase_client()
        result = (
            client.table("lunar_sites")
            .select("dem_storage_path")
            .eq("id", site_id)
            .execute()
        )
        if result.data and result.data[0].get("dem_storage_path"):
            return result.data[0]["dem_storage_path"]
    except Exception:
        pass

    return None

"""
Coordinate conversions for ICAROS lunar terrain grids.

Grid convention:
- Origin (row=0, col=0) is the northwest corner of the window.
- col increases east; row increases south.
- Site center is at the middle of the grid in local meters (0, 0).
"""


def meters_to_grid(
    x_m: float,
    y_m: float,
    grid_size: int,
    resolution_m_per_pixel: float,
) -> tuple[int, int]:
    """
    Convert local meters (relative to site center) to grid row/col.

    x_m: east-positive meters from center
    y_m: south-positive meters from center
    """
    center = grid_size / 2.0
    col = int(round(x_m / resolution_m_per_pixel + center))
    row = int(round(y_m / resolution_m_per_pixel + center))
    col = max(0, min(grid_size - 1, col))
    row = max(0, min(grid_size - 1, row))
    return row, col


def grid_to_meters(
    row: int,
    col: int,
    grid_size: int,
    resolution_m_per_pixel: float,
) -> tuple[float, float]:
    """Convert grid row/col to local meters relative to site center."""
    center = grid_size / 2.0
    x_m = (col - center) * resolution_m_per_pixel
    y_m = (row - center) * resolution_m_per_pixel
    return x_m, y_m


def approximate_latlon_from_meters(
    center_lat: float,
    center_lon: float,
    x_m: float,
    y_m: float,
) -> tuple[float, float]:
    """
    Approximate lat/lon from local meters near the lunar South Pole.

    Uses a simple equirectangular approximation suitable for small windows
    (a few km). For production GeoTIFF workflows, use pyproj with IAU Moon 2000.
    """
    # ~1 degree latitude ≈ 30.3 km on the Moon near the pole
    meters_per_deg_lat = 30300.0
    cos_lat = max(0.01, abs(__import__("math").cos(__import__("math").radians(center_lat))))
    meters_per_deg_lon = meters_per_deg_lat * cos_lat

    lat = center_lat - (y_m / meters_per_deg_lat)
    lon = center_lon + (x_m / meters_per_deg_lon)
    return lat, lon

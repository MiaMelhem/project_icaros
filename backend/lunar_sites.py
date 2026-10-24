"""
Catalog of lunar South Pole sites for ICAROS terrain selection.

Each site defines a catalog center and metadata. Those latitude and longitude
values are labels. The DEM loader uses one as the crop center only when it
falls inside that site's GeoTIFF. Otherwise the crop is centered on the file's
own bounds, which is not the same as the named landmark.

Real NASA GeoTIFFs can be placed at data/dems/{site_id}.tif. A missing or
unusable file falls back to site-seeded synthetic terrain, labeled as synthetic.
"""

LUNAR_SITES = [
    {
        "id": "shackleton-rim",
        "name": "Shackleton Crater Rim",
        "description": "Permanently shadowed interior with sunlit rim — key Artemis candidate region.",
        "center_lat": -89.9,
        "center_lon": 0.0,
        "window_size_m": 4000,
        "resolution_m": 20,
        "source": "LROC NAC DTM",
        "dem_filename": "shackleton-rim.tif",
        "dem_storage_path": "shackleton-rim.tif",
    },
    {
        "id": "malapert-massif",
        "name": "Malapert Massif",
        "description": "Elevated peak near the South Pole with extended sun exposure.",
        "center_lat": -86.0,
        "center_lon": 2.0,
        "window_size_m": 4000,
        "resolution_m": 20,
        "source": "LROC NAC DTM (NAC_DTM_ESALL_MP1, ~2 m/px)",
        "dem_filename": "malapert-massif.tif",
    },
    {
        "id": "haworth-crater",
        "name": "Haworth Crater",
        "description": "Large complex crater on the lunar South Pole highlands.",
        "center_lat": -87.5,
        "center_lon": 320.0,
        "window_size_m": 4000,
        "resolution_m": 20,
        "source": "NASA LOLA 5 m/px LDEM (PGDA Haworth)",
        "dem_filename": "haworth-crater.tif",
    },
    {
        "id": "nobile-crater",
        "name": "Nobile Crater",
        "description": "Artemis landing candidate site in the South Pole region.",
        "center_lat": -84.73,
        "center_lon": 29.13,
        "window_size_m": 4000,
        "resolution_m": 20,
        "source": "LROC NAC DTM (NAC_DTM_NOBILE03, 4 m/px)",
        "dem_filename": "nobile-crater.tif",
    },
    {
        "id": "amundsen-rim",
        "name": "Amundsen Crater Rim",
        "description": "Rugged rim terrain with mixed slopes and crater features.",
        "center_lat": -88.5,
        "center_lon": 80.0,
        "window_size_m": 4000,
        "resolution_m": 20,
        "source": "NASA LOLA 5 m/px LDEM (PGDA DM1 Amundsen rim)",
        "dem_filename": "amundsen-rim.tif",
    },
]


def list_lunar_sites():
    """Return all lunar sites for the API."""
    return LUNAR_SITES


def get_lunar_site(site_id: str) -> dict:
    """Look up a site by id; raises KeyError if not found."""
    for site in LUNAR_SITES:
        if site["id"] == site_id:
            return site
    raise KeyError(f"Unknown lunar site: {site_id}")


def site_seed(site_id: str) -> int:
    """Deterministic seed so each site gets unique but reproducible terrain."""
    return sum(ord(char) for char in site_id) * 9973 % (2**31)

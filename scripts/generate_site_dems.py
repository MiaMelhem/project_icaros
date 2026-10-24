#!/usr/bin/env python3
"""
Generate GeoTIFF elevation files for lunar catalog sites missing local DEMs.

Usage:
    python scripts/generate_site_dems.py
    python scripts/generate_site_dems.py --site malapert-massif
    python scripts/generate_site_dems.py --force   # overwrite existing files
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.lunar_sites import LUNAR_SITES
from backend.site_terrain_generator import generate_site_elevation, site_elevation_metadata

DEM_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "dems")
DEFAULT_SIZE = 1024


def write_geotiff(path: str, elevation, site: dict) -> None:
    """Write elevation array as a georeferenced GeoTIFF."""
    import rasterio
    from rasterio.transform import from_bounds

    height, width = elevation.shape
    window_m = site["window_size_m"]
    center_lat = site["center_lat"]
    center_lon = site["center_lon"]

    # Approximate degree extent for polar sites (demo georeferencing).
    half_deg = (window_m / 2) / 111_000
    west = center_lon - half_deg
    east = center_lon + half_deg
    south = center_lat - half_deg
    north = center_lat + half_deg
    transform = from_bounds(west, south, east, north, width, height)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
        nodata=-9999.0,
        compress="deflate",
    ) as dataset:
        dataset.write(elevation, 1)
        dataset.update_tags(
            ICAROS_SITE_ID=site["id"],
            ICAROS_SOURCE="ICAROS site elevation model",
        )


def main():
    parser = argparse.ArgumentParser(description="Generate site GeoTIFF DEMs for ICAROS")
    parser.add_argument("--site", help="Generate only this site id")
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE, help="Grid pixels per side")
    parser.add_argument("--force", action="store_true", help="Overwrite existing GeoTIFF files")
    args = parser.parse_args()

    sites = LUNAR_SITES
    if args.site:
        sites = [s for s in LUNAR_SITES if s["id"] == args.site]
        if not sites:
            raise SystemExit(f"Unknown site: {args.site}")

    for site in sites:
        filename = site.get("dem_filename", f"{site['id']}.tif")
        path = os.path.join(DEM_DIR, filename)

        if os.path.isfile(path) and not args.force:
            print(f"Skip {site['id']} — already exists: {path}")
            continue

        print(f"Generating {site['name']} ({site['id']})…")
        elevation = generate_site_elevation(site["id"], size=args.size)
        write_geotiff(path, elevation, site)
        meta = site_elevation_metadata(site["id"])
        print(f"  Wrote {path} ({os.path.getsize(path) / 1024:.1f} KB)")
        print(f"  {meta['description']}")

    print("Done.")


if __name__ == "__main__":
    main()

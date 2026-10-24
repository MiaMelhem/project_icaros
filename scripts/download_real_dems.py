#!/usr/bin/env python3
"""
Download real NASA lunar elevation GeoTIFFs for ICAROS catalog sites.

Sources:
- LROC NAC DTMs (PDS): Shackleton, Malapert, Nobile — ~2–4 m/px stereo
- NASA PGDA LOLA LDEMs: Haworth, Amundsen — 5 m/px laser altimetry

Usage:
    python scripts/download_real_dems.py
    python scripts/download_real_dems.py --site haworth-crater
"""

import argparse
import os
import sys
import tempfile
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.lunar_sites import LUNAR_SITES, get_lunar_site

DEM_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "dems")

# site_id -> (url, source_label, attribution)
REAL_DEM_CATALOG = {
    "shackleton-rim": (
        "https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/LROLRC_2001/DATA/SDP/NAC_DTM/ESALL_SR12/NAC_DTM_ESALL_SR12.TIF",
        "LROC NAC DTM (NAC_DTM_ESALL_SR12, ~2 m/px)",
        "NASA/GSFC/Arizona State University — LROC NAC stereo DTM",
    ),
    "malapert-massif": (
        "https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/LROLRC_2001/DATA/SDP/NAC_DTM/ESALL_MP1/NAC_DTM_ESALL_MP1.TIF",
        "LROC NAC DTM (NAC_DTM_ESALL_MP1, Malapert Massif, ~2 m/px)",
        "NASA/GSFC/Arizona State University — LROC NAC stereo DTM",
    ),
    "nobile-crater": (
        "https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/LROLRC_2001/DATA/SDP/NAC_DTM/NOBILE03/NAC_DTM_NOBILE03.TIF",
        "LROC NAC DTM (NAC_DTM_NOBILE03, Nobile rim, 4 m/px)",
        "NASA/GSFC/Arizona State University — LROC NAC stereo DTM",
    ),
    "haworth-crater": (
        "https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Haworth/Haworth_final_adj_5mpp_surf.tif",
        "NASA LOLA 5 m/px LDEM (PGDA Haworth)",
        "NASA GSFC PGDA — Barker et al. 2021, Planetary & Space Science",
    ),
    "amundsen-rim": (
        "https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/DM1/DM1_final_adj_5mpp_surf.tif",
        "NASA LOLA 5 m/px LDEM (PGDA DM1 Amundsen rim)",
        "NASA GSFC PGDA — Barker et al. 2021, Planetary & Space Science",
    ),
}


def download_file(url: str, dest_path: str) -> None:
    """Stream download to dest_path with a temp file for atomic replace."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    print(f"  Downloading {url}")

    with tempfile.NamedTemporaryFile(delete=False, dir=os.path.dirname(dest_path)) as tmp:
        temp_path = tmp.name

    try:
        def report(block_num, block_size, total_size):
            if total_size > 0 and block_num % 500 == 0:
                pct = min(100, block_num * block_size * 100 // total_size)
                print(f"    … {pct}%", end="\r", flush=True)

        urllib.request.urlretrieve(url, temp_path, reporthook=report)
        print()

        with open(temp_path, "rb") as handle:
            header = handle.read(4)
        if header not in (b"II*\x00", b"MM\x00*"):
            raise RuntimeError("Downloaded file is not a valid GeoTIFF")

        os.replace(temp_path, dest_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def validate_geotiff(path: str) -> dict:
    """Check that the file opens as a meter grid and has some valid elevation."""
    import numpy as np
    import rasterio

    from backend.dem_loader import probe_geotiff

    probe = probe_geotiff(path)
    if probe is None or not probe["usable_meter_grid"]:
        reason = None if probe is None else probe["reason"]
        raise RuntimeError(reason or "rasterio could not read a meter-grid DEM")

    with rasterio.open(path) as dataset:
        sample = dataset.read(1, out_shape=(64, 64)).astype(float)
        nodata = dataset.nodata
        valid = np.isfinite(sample)
        if nodata is not None and np.isfinite(nodata):
            valid = valid & ~np.isclose(sample, nodata, rtol=0, atol=1.0)
        valid = valid & (sample > -1e9)
        if not np.any(valid):
            raise RuntimeError("No valid elevation pixels in the preview sample")
        native_res = abs(float(dataset.transform.a))

    return {
        "min": float(sample[valid].min()),
        "max": float(sample[valid].max()),
        "native_res_m": native_res,
    }


def main():
    parser = argparse.ArgumentParser(description="Download real NASA DEMs for ICAROS sites")
    parser.add_argument("--site", help="Download only this site id")
    parser.add_argument("--skip-existing", action="store_true", help="Skip if output file exists")
    args = parser.parse_args()

    site_ids = list(REAL_DEM_CATALOG.keys())
    if args.site:
        if args.site not in REAL_DEM_CATALOG:
            raise SystemExit(f"Unknown site: {args.site}")
        site_ids = [args.site]

    for site_id in site_ids:
        site = get_lunar_site(site_id)
        filename = site.get("dem_filename", f"{site_id}.tif")
        dest = os.path.join(DEM_DIR, filename)
        url, source, _attribution = REAL_DEM_CATALOG[site_id]

        if args.skip_existing and os.path.isfile(dest):
            print(f"Skip {site_id} — {dest} exists")
            continue

        print(f"\n{site['name']} ({site_id})")
        download_file(url, dest)
        stats = validate_geotiff(dest)
        size_mb = os.path.getsize(dest) / (1024 * 1024)
        print(f"  Saved {dest} ({size_mb:.1f} MB)")
        print(f"  Source: {source}")
        print(f"  Elevation sample: {stats['min']:.1f} – {stats['max']:.1f} m")
        print(f"  Native resolution {stats['native_res_m']:.2f} m/px")

    print("\nDone. Restart the backend and reload terrain preview in the app.")


if __name__ == "__main__":
    main()

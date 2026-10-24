#!/usr/bin/env python3
"""Upload lunar DEM files to Supabase Storage and update lunar_sites metadata."""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env.local"))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.lunar_sites import LUNAR_SITES

BUCKET = "lunar-dems"
DEM_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "dems")

SITE_SOURCES = {
    "shackleton-rim": "LROC NAC DTM (NAC_DTM_ESALL_SR12, ~2 m/px)",
    "malapert-massif": "LROC NAC DTM (NAC_DTM_ESALL_MP1, ~2 m/px)",
    "nobile-crater": "LROC NAC DTM (NAC_DTM_NOBILE03, 4 m/px)",
    "haworth-crater": "NASA LOLA 5 m/px LDEM (PGDA Haworth)",
    "amundsen-rim": "NASA LOLA 5 m/px LDEM (PGDA DM1 Amundsen rim)",
}


def get_client():
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required in .env.local")
    return create_client(url, key)


def ensure_bucket(client):
    """Create public bucket if it does not exist."""
    try:
        client.storage.create_bucket(BUCKET, options={"public": True})
        print(f"Created bucket: {BUCKET}")
    except Exception as error:
        message = str(error).lower()
        if "already exists" in message or "duplicate" in message:
            print(f"Bucket already exists: {BUCKET}")
        else:
            raise


def upload_dem(client, local_path: str, storage_path: str):
    with open(local_path, "rb") as handle:
        data = handle.read()

    bucket = client.storage.from_(BUCKET)
    try:
        bucket.upload(
            storage_path,
            data,
            file_options={"content-type": "image/tiff", "upsert": "true"},
        )
    except Exception as error:
        if "already exists" in str(error).lower():
            bucket.update(storage_path, data, file_options={"content-type": "image/tiff"})
        else:
            raise

    public_url = client.storage.from_(BUCKET).get_public_url(storage_path)
    print(f"Uploaded {local_path} -> {BUCKET}/{storage_path}")
    print(f"Public URL: {public_url}")
    return public_url


def update_site_record(client, site_id: str, storage_path: str, source: str):
    client.table("lunar_sites").update(
        {
            "dem_storage_path": storage_path,
            "source": source,
        }
    ).eq("id", site_id).execute()
    print(f"Updated lunar_sites row: {site_id}")


def upload_site(client, site_id: str):
    site = next((s for s in LUNAR_SITES if s["id"] == site_id), None)
    if not site:
        raise SystemExit(f"Unknown site: {site_id}")

    filename = site.get("dem_filename", f"{site_id}.tif")
    dem_path = os.path.join(DEM_DIR, filename)
    if not os.path.isfile(dem_path):
        raise SystemExit(f"DEM file not found: {dem_path}")

    storage_path = filename
    upload_dem(client, dem_path, storage_path)
    update_site_record(
        client,
        site_id=site_id,
        storage_path=storage_path,
        source=SITE_SOURCES.get(site_id, site.get("source", "GeoTIFF DEM")),
    )


def main():
    parser = argparse.ArgumentParser(description="Upload DEMs to Supabase Storage")
    parser.add_argument("--site", help="Upload a single site id")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Upload all catalog sites that have local GeoTIFF files",
    )
    args = parser.parse_args()

    client = get_client()
    ensure_bucket(client)

    if args.all:
        for site in LUNAR_SITES:
            filename = site.get("dem_filename", f"{site['id']}.tif")
            if os.path.isfile(os.path.join(DEM_DIR, filename)):
                upload_site(client, site["id"])
            else:
                print(f"Skip {site['id']} — no local file")
        return

    site_id = args.site or "shackleton-rim"
    upload_site(client, site_id)


if __name__ == "__main__":
    main()

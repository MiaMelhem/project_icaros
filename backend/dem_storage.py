"""
Fetch lunar DEM GeoTIFF bytes from Supabase Storage.
"""

import os
import tempfile


def is_supabase_storage_configured() -> bool:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    return bool(url and key)


def get_supabase_client():
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    return create_client(url, key)


def download_dem_bytes(storage_path: str, bucket: str = "lunar-dems") -> bytes | None:
    """
    Download a DEM file from Supabase Storage.

    Returns None if Supabase is not configured or the file is missing.
    """
    if not is_supabase_storage_configured() or not storage_path:
        return None

    try:
        client = get_supabase_client()
        return client.storage.from_(bucket).download(storage_path)
    except Exception:
        return None


def download_dem_to_tempfile(storage_path: str, bucket: str = "lunar-dems") -> str | None:
    """Download DEM to a temporary file for rasterio. Caller should delete when done."""
    data = download_dem_bytes(storage_path, bucket=bucket)
    if data is None:
        return None

    temp = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
    temp.write(data)
    temp.close()
    return temp.name

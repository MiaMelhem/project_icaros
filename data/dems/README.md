# Lunar site elevation data (`data/dems/`)

Each catalog site expects a GeoTIFF named `{site_id}.tif`:

| File | Source |
|------|--------|
| `shackleton-rim.tif` | LROC NAC DTM (NAC_DTM_ESALL_SR12, ~2 m/px) |
| `malapert-massif.tif` | LROC NAC DTM (NAC_DTM_ESALL_MP1, ~2 m/px) |
| `nobile-crater.tif` | LROC NAC DTM (NAC_DTM_NOBILE03, 4 m/px) |
| `haworth-crater.tif` | NASA LOLA 5 m/px LDEM (PGDA Haworth) |
| `amundsen-rim.tif` | NASA LOLA 5 m/px LDEM (PGDA DM1 Amundsen rim) |

## Download real NASA DEMs

```bash
source .venv/bin/activate
python scripts/download_real_dems.py
```

This fetches LROC NAC stereo DTMs and NASA GSFC LOLA LDEMs from PDS/PGDA (~250 MB total).

Use `--site haworth-crater` for one site. Use `--skip-existing` to avoid re-downloading.

## Synthetic fallback (dev only)

If a file is missing, run `python scripts/generate_site_dems.py` for placeholder terrain.

## Supabase Storage (production)

```bash
python scripts/upload_dem_to_supabase.py --all
```

Or upload via the in-app **Upload NASA GeoTIFF DEM** control when a lunar site is selected.

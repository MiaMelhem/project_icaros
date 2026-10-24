-- Add Supabase Storage path for lunar DEM files

ALTER TABLE lunar_sites
ADD COLUMN IF NOT EXISTS dem_storage_path TEXT;

UPDATE lunar_sites
SET
    dem_storage_path = 'shackleton-rim.tif',
    source = 'LROC NAC DTM (NAC_DTM_ESALL_SR12, 2 m/px)'
WHERE id = 'shackleton-rim';

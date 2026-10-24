-- ICAROS lunar sites catalog

CREATE TABLE IF NOT EXISTS lunar_sites (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    center_lat DOUBLE PRECISION NOT NULL,
    center_lon DOUBLE PRECISION NOT NULL,
    window_size_m INTEGER NOT NULL DEFAULT 4000,
    resolution_m DOUBLE PRECISION NOT NULL DEFAULT 20,
    source TEXT,
    dem_filename TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO lunar_sites (id, name, description, center_lat, center_lon, window_size_m, resolution_m, source, dem_filename)
VALUES
    (
        'shackleton-rim',
        'Shackleton Crater Rim',
        'Permanently shadowed interior with sunlit rim — key Artemis candidate region.',
        -89.9, 0.0, 4000, 20, 'LOLA (placeholder)', 'shackleton-rim.tif'
    ),
    (
        'malapert-massif',
        'Malapert Massif',
        'Elevated peak near the South Pole with extended sun exposure.',
        -86.0, 2.0, 4000, 20, 'LOLA (placeholder)', 'malapert-massif.tif'
    ),
    (
        'haworth-crater',
        'Haworth Crater',
        'Large complex crater on the lunar South Pole highlands.',
        -87.5, 320.0, 4000, 20, 'LOLA (placeholder)', 'haworth-crater.tif'
    ),
    (
        'nobile-crater',
        'Nobile Crater',
        'Artemis landing candidate site in the South Pole region.',
        -85.5, 345.0, 4000, 20, 'LOLA (placeholder)', 'nobile-crater.tif'
    ),
    (
        'amundsen-rim',
        'Amundsen Crater Rim',
        'Rugged rim terrain with mixed slopes and crater features.',
        -88.5, 80.0, 4000, 20, 'LOLA (placeholder)', 'amundsen-rim.tif'
    )
ON CONFLICT (id) DO NOTHING;

GRANT SELECT ON public.lunar_sites TO anon, authenticated, service_role;

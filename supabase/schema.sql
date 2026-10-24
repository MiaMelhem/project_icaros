-- ICAROS Supabase schema
-- Run this in the Supabase SQL editor to set up the database.

CREATE TABLE IF NOT EXISTS rovers (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    max_slope_deg DOUBLE PRECISION NOT NULL,
    nominal_speed_mps DOUBLE PRECISION NOT NULL,
    roughness_tolerance DOUBLE PRECISION NOT NULL,
    energy_factor DOUBLE PRECISION NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS route_runs (
    id BIGSERIAL PRIMARY KEY,
    rover_name TEXT NOT NULL,
    terrain_size INTEGER NOT NULL,
    resolution_m_per_pixel DOUBLE PRECISION NOT NULL,
    start_row INTEGER NOT NULL,
    start_col INTEGER NOT NULL,
    goal_row INTEGER NOT NULL,
    goal_col INTEGER NOT NULL,
    hazard_weight DOUBLE PRECISION NOT NULL,
    route_found BOOLEAN NOT NULL,
    distance_m DOUBLE PRECISION,
    estimated_time_min DOUBLE PRECISION,
    max_slope_deg DOUBLE PRECISION,
    average_slope_deg DOUBLE PRECISION,
    average_hazard_score DOUBLE PRECISION,
    energy_score DOUBLE PRECISION,
    route_json JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO rovers (name, max_slope_deg, nominal_speed_mps, roughness_tolerance, energy_factor, description)
VALUES
    (
        'Astrolab CLV-1',
        20.0,
        2.8,
        0.3,
        1.18,
        'Crewed Lunar Vehicle 1, an adapted, 2,000-pound version of Astrolab FLEX architecture built with Axiom Space. Top speed 10 kph.'
    ),
    (
        'Lunar Outpost Pegasus',
        20.0,
        4.0,
        0.3,
        1.10,
        'Lighter, agile evolution of the Eagle rover built with GM and Lockheed Martin. Speeds exceeding 9 mph over rugged South Pole terrain.'
    )
ON CONFLICT (name) DO NOTHING;

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
    dem_storage_path TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO lunar_sites (id, name, description, center_lat, center_lon, window_size_m, resolution_m, source, dem_filename, dem_storage_path)
VALUES
    ('shackleton-rim', 'Shackleton Crater Rim', 'Permanently shadowed interior with sunlit rim.', -89.9, 0.0, 4000, 20, 'LROC NAC DTM (NAC_DTM_ESALL_SR12, 2 m/px)', 'shackleton-rim.tif', 'shackleton-rim.tif'),
    ('malapert-massif', 'Malapert Massif', 'Elevated peak near the South Pole.', -86.0, 2.0, 4000, 20, 'LROC NAC DTM (NAC_DTM_ESALL_MP1, ~2 m/px)', 'malapert-massif.tif', NULL),
    ('haworth-crater', 'Haworth Crater', 'Large complex crater on the South Pole highlands.', -87.5, 320.0, 4000, 20, 'NASA LOLA 5 m/px LDEM (PGDA Haworth)', 'haworth-crater.tif', NULL),
    ('nobile-crater', 'Nobile Crater', 'Artemis landing candidate site.', -84.73, 29.13, 4000, 20, 'LROC NAC DTM (NAC_DTM_NOBILE03, 4 m/px)', 'nobile-crater.tif', NULL),
    ('amundsen-rim', 'Amundsen Crater Rim', 'Rugged rim terrain with mixed slopes.', -88.5, 80.0, 4000, 20, 'NASA LOLA 5 m/px LDEM (PGDA DM1 Amundsen rim)', 'amundsen-rim.tif', NULL)
ON CONFLICT (id) DO NOTHING;

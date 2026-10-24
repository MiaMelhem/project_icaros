-- ICAROS initial schema migration

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

GRANT SELECT, INSERT, UPDATE, DELETE ON public.rovers TO anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.route_runs TO anon, authenticated, service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;

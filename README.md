# ICAROS: Intelligent Crater-Aware Route Optimization System

ICAROS is a lunar rover route-planning application. It generates synthetic lunar South Pole terrain, calculates terrain hazards, and finds optimized routes between two points for different rover configurations.

## What ICAROS Is

ICAROS is the **route-planning and decision-support layer** for lunar rover missions. It:

- Generates synthetic lunar-like terrain (real NASA DEM support planned)
- Computes elevation, slope, roughness, and hazard scores
- Uses A* pathfinding to find safe, efficient routes
- Compares route metrics (distance, time, energy, slopes)
- Exports routes as CSV for downstream use

## ICAROS vs Project Chrono

| ICAROS | Project Chrono |
|--------|----------------|
| Route planning and scoring | Physics simulation |
| Identifies candidate routes | Tests routes with realistic dynamics |
| Fast grid-based analysis | Detailed multibody simulation |
| Decision support tool | Validation engine |

ICAROS does **not** replace Project Chrono. It identifies and scores candidate routes that can later be exported and tested in Project Chrono.

## Architecture

```
Next.js Frontend  →  FastAPI Python Engine  →  Supabase (optional)  →  Project Chrono (future)
```

- **Frontend**: Next.js with TypeScript, canvas heatmap visualization
- **Backend**: Python FastAPI with beginner-readable modules
- **Database**: Supabase for saving route runs (optional for MVP)
- **Deployment**: Vercel

## Rover Profiles

| Rover | Max Slope | Speed | Roughness Tolerance | Energy Factor |
|-------|-----------|-------|---------------------|---------------|
| Astrolab CLV-1 | 20° | 2.8 m/s | 0.3 | 1.18 |
| Lunar Outpost Pegasus | 20° | 4.0 m/s | 0.3 | 1.10 |

## Local Development

### Python Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload
```

Backend runs at http://127.0.0.1:8000

### Frontend

```bash
npm install
npm run dev
```

Frontend runs at http://localhost:3000 and proxies API calls to the backend.

## Supabase Setup (Optional)

1. Create a Supabase project at https://supabase.com
2. Run `supabase/schema.sql` in the SQL editor
3. Copy credentials to `.env.local`:

```
NEXT_PUBLIC_SUPABASE_URL=your_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
SUPABASE_URL=your_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```

The app works without Supabase — it will show "Supabase not configured yet."

## Deploy to Vercel

1. Push the repo to GitHub
2. Import the project in Vercel
3. Set environment variables in the Vercel dashboard
4. Deploy — both Next.js frontend and FastAPI backend deploy together

The FastAPI instance in `api/main.py` must be named `app` (already configured).

## How the Python Route Planner Works

1. **Terrain generation** (`terrain_loader.py`): Creates a grid with rolling hills, noise, and crater depressions
2. **Metric computation** (`terrain_metrics.py`): Calculates slope, roughness, and hazard scores per cell
3. **A* pathfinding** (`route_planner.py`): Finds the lowest-cost path from start to goal, penalizing hazardous terrain
4. **Export** (`export_utils.py`): Builds a step-by-step DataFrame and calculates summary metrics

### A* in Plain Language

A* is like GPS for a grid map. It:

1. Starts at the start cell
2. Looks at all 8 neighboring cells (including diagonals)
3. Skips cells that are too steep (blocked)
4. Picks the neighbor with the lowest cost (distance + hazard penalty)
5. Repeats until it reaches the goal
6. Traces back through its choices to build the full path

## Files to Study First

If you're learning Python with this project, start here:

1. `backend/terrain_loader.py` — how synthetic terrain is generated
2. `backend/terrain_metrics.py` — slope, roughness, hazard calculations
3. `backend/route_planner.py` — A* pathfinding algorithm
4. `backend/export_utils.py` — route metrics and CSV export
5. `api/main.py` — how the HTTP API connects everything

## Future Improvements

- Real NASA lunar South Pole DEM import
- Illumination/shadow constraints
- Thermal constraints
- Battery/solar energy model
- Verified rover specifications
- Project Chrono route export
- Route comparison dashboard (Stage 8)
- 3D visualization
- Validation with rover-terrain simulation

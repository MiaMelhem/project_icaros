"""
Moon Base architecture constraints for ICAROS route planning.

Phases, mission modes, and cost weights come from the NASA Moon Base User's
Guide (March 2026). A* still finds the path. This module only decides which
cells are blocked and what extra cost each cell adds.

Launch counts, habitat life support, and Mars systems are labels and notes.
They are not route physics. Regolith mechanics, radiation, and resource grades
are data gaps in the guide and are not invented here.
"""

import math

import numpy as np

from backend.hillshade import compute_south_pole_lighting

# Guide targets used as thresholds, not as something a short drive will last.
SURVIVE_THE_NIGHT_HOURS = 120.0
POWER_GENERATION_KW = 5.0
# Cargo of a few hundred kg. 500 kg doubles the cargo factor.
CARGO_REFERENCE_KG = 500.0
CARGO_MISSION_KG = 200.0

COMMS_RADIUS_M = 1500.0
POWER_RADIUS_M = 2000.0
INFRASTRUCTURE_SHADOW_M = 60.0
KEEPOUT_RADIUS_M = {
    "habitat": 80.0,
    "lander": 150.0,
    "infrastructure": 40.0,
}

ASSET_KINDS = (
    "habitat",
    "lander",
    "power_node",
    "wireless_charger",
    "relay",
    "infrastructure",
)
PHASE2_ASSETS = set(ASSET_KINDS)

UNCERTAINTY_NOTES = [
    "Illumination is local terrain shadow at a 1.5° sun, not a lunar-year PSR catalog.",
    "Regolith mechanics, dust damage, radiation, gravity anomalies, and resource grades are open data gaps and are not simulated.",
    "Communications cost is loss of Earth view in a PSR or behind a closed horizon. A relay clears that gap inside its radius. It is not a link budget.",
    "120 hours of darkness is a site power threshold. Routes pay for time in shadow.",
]


def _mission(
    mission_id: str,
    label: str,
    summary: str,
    phase_min: int,
    functional_gaps: list[str],
    *,
    block_psr: bool,
    allow_psr_if_capable: bool,
    shadow_weight: float,
    comms_weight: float,
    power_weight: float,
    landing_weight: float,
    default_cargo_kg: float,
    scoring: tuple,
) -> dict:
    return {
        "id": mission_id,
        "label": label,
        "summary": summary,
        "phase_min": phase_min,
        "functional_gaps": functional_gaps,
        "block_psr": block_psr,
        "allow_psr_if_capable": allow_psr_if_capable,
        "shadow_weight": shadow_weight,
        "comms_weight": comms_weight,
        "power_weight": power_weight,
        "landing_weight": landing_weight,
        "default_cargo_kg": default_cargo_kg,
        "scoring": scoring,
    }


# (criterion, benefit|cost, weight). Weights in each mission sum to 1.
_SUNLIT_SCORING = (
    ("safety", "benefit", 0.22),
    ("range", "benefit", 0.08),
    ("time", "cost", 0.14),
    ("slope", "cost", 0.12),
    ("distance", "cost", 0.08),
    ("energy", "cost", 0.12),
    ("shadow", "cost", 0.12),
    ("comms", "cost", 0.04),
    ("power", "benefit", 0.04),
    ("keepout", "cost", 0.04),
)
_PSR_SCORING = (
    ("safety", "benefit", 0.20),
    ("range", "benefit", 0.08),
    ("time", "cost", 0.12),
    ("slope", "cost", 0.14),
    ("distance", "cost", 0.08),
    ("energy", "cost", 0.10),
    ("psr", "benefit", 0.16),
    ("comms", "cost", 0.04),
    ("power", "benefit", 0.04),
    ("keepout", "cost", 0.04),
)
_CARGO_SCORING = (
    ("safety", "benefit", 0.20),
    ("range", "benefit", 0.08),
    ("time", "cost", 0.12),
    ("slope", "cost", 0.10),
    ("distance", "cost", 0.08),
    ("energy", "cost", 0.18),
    ("shadow", "cost", 0.12),
    ("comms", "cost", 0.04),
    ("power", "benefit", 0.04),
    ("keepout", "cost", 0.04),
)
_LANDING_SCORING = (
    ("safety", "benefit", 0.26),
    ("range", "benefit", 0.06),
    ("time", "cost", 0.10),
    ("slope", "cost", 0.16),
    ("distance", "cost", 0.06),
    ("energy", "cost", 0.08),
    ("shadow", "cost", 0.08),
    ("comms", "cost", 0.04),
    ("power", "benefit", 0.04),
    ("keepout", "cost", 0.12),
)
_RECON_SCORING = (
    ("safety", "benefit", 0.20),
    ("range", "benefit", 0.08),
    ("time", "cost", 0.12),
    ("slope", "cost", 0.12),
    ("distance", "cost", 0.08),
    ("energy", "cost", 0.10),
    ("shadow", "cost", 0.08),
    ("psr", "benefit", 0.06),
    ("comms", "cost", 0.08),
    ("power", "benefit", 0.04),
    ("keepout", "cost", 0.04),
)

MISSIONS = {
    "landing_site": _mission(
        "landing_site",
        "Landing-site check",
        "Score a traverse for blocks, slope, and plume keep-out around a lander.",
        1,
        ["FN-A-103"],
        block_psr=True,
        allow_psr_if_capable=False,
        shadow_weight=3.0,
        comms_weight=2.0,
        power_weight=1.0,
        landing_weight=4.0,
        default_cargo_kg=0.0,
        scoring=_LANDING_SCORING,
    ),
    "reconnaissance": _mission(
        "reconnaissance",
        "Reconnaissance",
        "Remote survey. Permanently shadowed cells are allowed only if the rover can drive them.",
        1,
        ["FN-A-103", "FN-U-103"],
        block_psr=True,
        allow_psr_if_capable=True,
        shadow_weight=2.0,
        comms_weight=3.0,
        power_weight=1.5,
        landing_weight=0.0,
        default_cargo_kg=0.0,
        scoring=_RECON_SCORING,
    ),
    "sunlit_traverse": _mission(
        "sunlit_traverse",
        "Sunlit traverse",
        "Local driving in sunlight. Permanently shadowed regions are blocked.",
        1,
        ["FN-M-302"],
        block_psr=True,
        allow_psr_if_capable=False,
        shadow_weight=4.0,
        comms_weight=2.0,
        power_weight=1.5,
        landing_weight=0.0,
        default_cargo_kg=0.0,
        scoring=_SUNLIT_SCORING,
    ),
    "psr_access": _mission(
        "psr_access",
        "PSR access",
        "Enter a shadowed crater if the rover can drive the slope. The guide sets no higher slope cap.",
        1,
        ["FN-M-304", "FN-U-103"],
        block_psr=False,
        allow_psr_if_capable=True,
        shadow_weight=0.4,
        comms_weight=2.0,
        power_weight=2.0,
        landing_weight=0.0,
        default_cargo_kg=0.0,
        scoring=_PSR_SCORING,
    ),
    "cargo_reposition": _mission(
        "cargo_reposition",
        "Cargo reposition",
        "Move a few hundred kilograms in sunlight. Energy scales with cargo mass.",
        1,
        ["FN-M-401", "FN-M-501"],
        block_psr=True,
        allow_psr_if_capable=False,
        shadow_weight=3.0,
        comms_weight=2.0,
        power_weight=1.5,
        landing_weight=0.0,
        default_cargo_kg=CARGO_MISSION_KG,
        scoring=_CARGO_SCORING,
    ),
    "site_prep": _mission(
        "site_prep",
        "Site preparation",
        "Reach a work area for regolith preparation. Excavation itself is not simulated.",
        3,
        ["FN-M-302"],
        block_psr=True,
        allow_psr_if_capable=False,
        shadow_weight=3.0,
        comms_weight=2.0,
        power_weight=1.5,
        landing_weight=1.0,
        default_cargo_kg=0.0,
        scoring=_SUNLIT_SCORING,
    ),
    "isru_prospecting": _mission(
        "isru_prospecting",
        "ISRU prospecting",
        "Prospect a shadowed crater for volatiles. Resource grades are not invented.",
        3,
        ["FN-M-304", "FN-U-103"],
        block_psr=False,
        allow_psr_if_capable=True,
        shadow_weight=0.4,
        comms_weight=2.0,
        power_weight=2.0,
        landing_weight=0.0,
        default_cargo_kg=0.0,
        scoring=_PSR_SCORING,
    ),
}

PHASES = {
    1: {
        "id": 1,
        "name": "Phase 1",
        "summary": "Ground truth, experiments, and the first crewed Moon Base mission.",
        "payload_kg": 4000,
        "launches": 25,
        "landings": 21,
        "mars_forward": (
            "Phase 1 buys down risk for later Mars-forward systems. "
            "Nuclear propulsion and Mars helicopters are not part of this lunar route."
        ),
    },
    2: {
        "id": 2,
        "name": "Phase 2",
        "summary": "Initial surface infrastructure: habitat, power, communications, and chargers.",
        "payload_kg": 60000,
        "launches": 27,
        "landings": 24,
        "mars_forward": (
            "Shared power and logistics here are practice for deep-space logistics. "
            "They do not add a Mars cost to the lunar path."
        ),
    },
    3: {
        "id": 3,
        "name": "Phase 3",
        "summary": "Site preparation, resource prospecting, and continuous crew presence.",
        "payload_kg": 150000,
        "launches": 29,
        "landings": 28,
        "mars_forward": (
            "Continuous presence produces operational experience for Mars. "
            "Planetary protection and fission power stay outside the pathfinder."
        ),
    },
}


def get_phase(phase: int) -> dict:
    """Return a phase record. Raises KeyError if the phase is not 1, 2, or 3."""
    if phase not in PHASES:
        raise KeyError(f"Unknown Moon Base phase '{phase}'. Use 1, 2, or 3.")
    return PHASES[phase]


def get_mission(mission_id: str) -> dict:
    """Return a mission mode. Raises KeyError if the id is unknown."""
    if mission_id not in MISSIONS:
        known = ", ".join(MISSIONS.keys())
        raise KeyError(f"Unknown mission '{mission_id}'. Available: {known}")
    return MISSIONS[mission_id]


def missions_for_phase(phase: int) -> list[dict]:
    """Mission modes unlocked at this phase or earlier."""
    get_phase(phase)
    return [mission for mission in MISSIONS.values() if mission["phase_min"] <= phase]


def scoring_spec(mission_id: str, uncrewed: bool = False) -> tuple:
    """
    TOPSIS rows (criterion, type, weight) for a mission.

    Uncrewed operation (phase 3, FN-A-401) shifts a little weight onto keep-outs
    so autonomous driving stays farther from crew and landers.
    """
    mission = get_mission(mission_id)
    rows = list(mission["scoring"])
    if not uncrewed:
        return tuple(rows)

    adjusted = []
    for name, kind, weight in rows:
        if name == "time":
            weight = max(0.0, weight - 0.04)
        elif name == "keepout":
            weight = weight + 0.04
        adjusted.append((name, kind, weight))
    return tuple(adjusted)


def cargo_factor(cargo_kg: float) -> float:
    """1 with no cargo. 500 kg doubles the factor."""
    return 1.0 + max(0.0, float(cargo_kg)) / CARGO_REFERENCE_KG


def shadow_energy_factor(shadow_fraction: float, night_survival_hours: float) -> float:
    """
    Multiply route energy by time spent in shadow.

    A rover that can survive 120 hours without sunlight (for example an RTG)
    barely pays extra. Everyone else pays more as the shadowed fraction grows.
    """
    fraction = min(1.0, max(0.0, float(shadow_fraction)))
    if float(night_survival_hours) >= SURVIVE_THE_NIGHT_HOURS:
        return 1.0 + 0.05 * fraction
    return 1.0 + 0.8 * fraction


def catalog() -> dict:
    """JSON-ready description of phases, missions, and thresholds for the UI."""
    missions = []
    for mission in MISSIONS.values():
        missions.append(
            {
                "id": mission["id"],
                "label": mission["label"],
                "summary": mission["summary"],
                "phase_min": mission["phase_min"],
                "functional_gaps": list(mission["functional_gaps"]),
            }
        )
    return {
        "phases": list(PHASES.values()),
        "missions": missions,
        "asset_kinds": list(ASSET_KINDS),
        "thresholds": {
            "survive_the_night_hours": SURVIVE_THE_NIGHT_HOURS,
            "power_generation_kw": POWER_GENERATION_KW,
            "cargo_mission_kg": CARGO_MISSION_KG,
        },
        "uncertainty": list(UNCERTAINTY_NOTES),
    }


def _disk_mask(shape: tuple[int, int], row: int, col: int, radius_m: float, resolution: float) -> np.ndarray:
    """True inside a circle around one cell."""
    rows, cols = shape
    if radius_m <= 0 or resolution <= 0:
        return np.zeros(shape, dtype=bool)
    radius_cells = radius_m / resolution
    rr, cc = np.ogrid[0:rows, 0:cols]
    return (rr - row) ** 2 + (cc - col) ** 2 <= radius_cells ** 2


def _distance_to_points(
    shape: tuple[int, int],
    points: list[tuple[int, int]],
    resolution: float,
) -> np.ndarray | None:
    """Meters from each cell to the nearest point. None if there are no points."""
    if not points:
        return None
    rows, cols = shape
    rr, cc = np.indices((rows, cols))
    distance = np.full(shape, np.inf)
    for row, col in points:
        step = np.hypot((rr - row) * resolution, (cc - col) * resolution)
        distance = np.minimum(distance, step)
    return distance


def _in_grid(row: int, col: int, shape: tuple[int, int]) -> bool:
    rows, cols = shape
    return 0 <= row < rows and 0 <= col < cols


def _asset_points(assets: list[dict], kinds: set[str], shape: tuple[int, int]) -> list[tuple[int, int]]:
    points = []
    for asset in assets:
        if asset.get("kind") not in kinds:
            continue
        row = int(asset["row"])
        col = int(asset["col"])
        if _in_grid(row, col, shape):
            points.append((row, col))
    return points


def apply_infrastructure_shadows(
    illumination: np.ndarray,
    shadow_mask: np.ndarray,
    points: list[tuple[int, int]],
    resolution: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Darken cells around emplaced infrastructure.

    The guide calls out new shadows cast by surface hardware. Those cells join
    the shadow cost. They are not marked as geologic PSRs.
    """
    illum = np.array(illumination, dtype=float, copy=True)
    shadow = np.array(shadow_mask, dtype=bool, copy=True)
    for row, col in points:
        disk = _disk_mask(illum.shape, row, col, INFRASTRUCTURE_SHADOW_M, resolution)
        illum = np.where(disk, np.minimum(illum, 0.05), illum)
        shadow = shadow | disk
    return illum, shadow


def _should_block_psr(mission: dict, psr_capable: bool) -> bool:
    """Sunlit missions block PSRs. Recon and PSR missions open them only if the rover can drive them."""
    if mission["block_psr"]:
        if mission["allow_psr_if_capable"] and psr_capable:
            return False
        return True
    if not psr_capable:
        return True
    return False


def build_route_constraints(
    analysis: dict,
    rover_config: dict,
    phase: int,
    mission_id: str,
    assets: list[dict] | None = None,
    uncrewed: bool = False,
) -> dict:
    """
    Build the blocked mask and extra cost grid for one mission.

    Extra cost is a grid the existing A* adds to each step:
    shadow, comms gaps, and landing hazard. Placed surface hardware is ignored.
    """
    phase_info = get_phase(int(phase))
    mission = get_mission(mission_id)
    if mission["phase_min"] > int(phase):
        raise ValueError(
            f"{mission['label']} is a phase {mission['phase_min']} mission. "
            f"Phase {phase} cannot run it."
        )

    assets = list(assets or [])
    shape = analysis["slope"].shape
    resolution = float(analysis["resolution_m_per_pixel"])
    nodata = np.array(analysis["nodata_mask"], dtype=bool)
    slope = np.array(analysis["slope"], dtype=float)
    roughness = np.array(analysis["roughness"], dtype=float)

    lighting = compute_south_pole_lighting(analysis["elevation"], resolution)
    illumination = lighting["illumination"]
    psr_mask = lighting["psr_mask"] & ~nodata
    shadow_mask = lighting["shadow_mask"] & ~nodata

    # The guide names habitats, landers, power, and relays. It does not give
    # positions or radii, so a request that still sends them does not move the path.
    ignored = [str(asset.get("kind")) for asset in assets]
    active_assets: list[dict] = []

    psr_capable = bool(rover_config.get("psr_capable", False))
    night_hours = float(rover_config.get("night_survival_hours", 0.0))
    wireless = bool(rover_config.get("wireless_charge", False))

    blocked = np.array(analysis["slope_blocked"], dtype=bool) | nodata
    # The guide asks for mobility in PSRs. It does not raise the rover's slope limit there.
    if _should_block_psr(mission, psr_capable):
        blocked = blocked | psr_mask
    blocked = blocked | nodata

    # Shadow penalty. Night-surviving rovers barely pay it.
    shadow_scale = 0.05 if night_hours >= SURVIVE_THE_NIGHT_HOURS else 1.0
    extra = shadow_mask.astype(float) * mission["shadow_weight"] * shadow_scale

    # Loss of Earth view from the terrain. A placed relay does not clear it.
    earth_blocked = np.array(lighting["earth_blocked_mask"], dtype=bool) & ~nodata
    comms_gap = (psr_mask | earth_blocked) & ~nodata
    extra = extra + comms_gap.astype(float) * mission["comms_weight"]

    keepout = np.zeros(shape, dtype=bool)

    if mission["landing_weight"] > 0:
        slope_span = float(np.nanmax(slope)) if np.any(np.isfinite(slope)) else 1.0
        rough_span = float(np.nanmax(roughness)) if np.any(np.isfinite(roughness)) else 1.0
        slope_span = slope_span if slope_span > 1e-6 else 1.0
        rough_span = rough_span if rough_span > 1e-6 else 1.0
        landing = 0.6 * (slope / slope_span) + 0.4 * (roughness / rough_span)
        extra = extra + landing * mission["landing_weight"]

    extra = np.where(nodata, 0.0, extra)

    cargo_kg = max(
        float(rover_config.get("cargo_kg", 0.0)),
        float(mission["default_cargo_kg"]),
    )

    use_uncrewed = bool(uncrewed) and int(phase) >= 3
    gaps = list(mission["functional_gaps"])
    if use_uncrewed and "FN-A-401" not in gaps:
        gaps.append("FN-A-401")
    if "FN-C-101" not in gaps:
        gaps.append("FN-C-101")

    summary = {
        "phase": int(phase),
        "phase_name": phase_info["name"],
        "phase_summary": phase_info["summary"],
        "payload_kg": phase_info["payload_kg"],
        "mars_forward": phase_info["mars_forward"],
        "mission": mission["id"],
        "mission_label": mission["label"],
        "mission_summary": mission["summary"],
        "functional_gaps": gaps,
        "cargo_kg": cargo_kg,
        "uncrewed": use_uncrewed,
        "psr_capable": psr_capable,
        "night_survival_hours": night_hours,
        "wireless_charge": wireless,
        "ignored_assets": ignored,
        "assets": active_assets,
        "uncertainty": list(UNCERTAINTY_NOTES),
    }

    return {
        "blocked_mask": blocked,
        "extra_cost": extra,
        "illumination": illumination,
        "psr_mask": psr_mask,
        "shadow_mask": shadow_mask,
        "comms_gap_mask": comms_gap,
        "keepout_mask": keepout,
        "summary": summary,
    }


def fraction_along_route(route: list, mask: np.ndarray, resolution: float) -> float:
    """Share of route distance whose destination cell is inside mask."""
    if len(route) < 2:
        return 0.0
    shadowed = 0.0
    total = 0.0
    for index in range(1, len(route)):
        row0, col0 = route[index - 1]
        row1, col1 = route[index]
        step = math.hypot(row1 - row0, col1 - col0) * resolution
        total += step
        if mask[row1, col1]:
            shadowed += step
    if total <= 0:
        return 0.0
    return shadowed / total


def blank_architecture_metrics(rover_config: dict, cargo_kg: float = 0.0) -> dict:
    """Zero architecture metrics for a route that was not found."""
    return {
        "shadow_fraction": 0.0,
        "time_in_darkness_min": 0.0,
        "psr_fraction": 0.0,
        "comms_gap_fraction": 0.0,
        "power_margin_m": round(float(rover_config.get("max_range_m", 0.0)), 2),
        "cargo_kg": round(float(cargo_kg), 2),
        "enters_keepout": False,
        "cargo_factor": round(cargo_factor(cargo_kg), 3),
        "shadow_factor": 1.0,
    }


def apply_architecture_metrics(
    metrics: dict,
    route: list,
    analysis: dict,
    rover_config: dict,
) -> dict:
    """
    Fold cargo and shadow into energy, and add Moon Base route metrics.

    energy = distance × energy_factor × (1 + hazard) × cargo_factor × shadow_factor
    The first three terms are already in metrics["energy_score"].
    """
    summary = analysis.get("moonbase") or {}
    cargo_kg = float(summary.get("cargo_kg", rover_config.get("cargo_kg", 0.0)))
    if not route:
        updated = dict(metrics)
        updated.update(blank_architecture_metrics(rover_config, cargo_kg))
        updated["energy_score"] = 0.0
        return updated

    resolution = float(analysis["resolution_m_per_pixel"])
    shadow_fraction = fraction_along_route(route, analysis["shadow_mask"], resolution)
    psr_fraction = fraction_along_route(route, analysis["psr_mask"], resolution)
    comms_fraction = fraction_along_route(route, analysis["comms_gap_mask"], resolution)
    enters_keepout = any(bool(analysis["keepout_mask"][cell[0], cell[1]]) for cell in route)

    night_hours = float(rover_config.get("night_survival_hours", 0.0))
    c_factor = cargo_factor(cargo_kg)
    s_factor = shadow_energy_factor(shadow_fraction, night_hours)

    base_energy = float(metrics.get("energy_score", 0.0))
    energy = base_energy * c_factor * s_factor
    distance_m = float(metrics.get("distance_m", 0.0))
    max_range_m = float(metrics.get("max_range_m", rover_config.get("max_range_m", 0.0)))
    effective_distance = distance_m * c_factor * s_factor
    time_min = float(metrics.get("estimated_time_min", 0.0))

    return {
        **metrics,
        "energy_score": round(energy, 2),
        "shadow_fraction": round(shadow_fraction, 4),
        "time_in_darkness_min": round(time_min * shadow_fraction, 2),
        "psr_fraction": round(psr_fraction, 4),
        "comms_gap_fraction": round(comms_fraction, 4),
        "power_margin_m": round(max_range_m - effective_distance, 2),
        "cargo_kg": round(cargo_kg, 2),
        "enters_keepout": bool(enters_keepout),
        "cargo_factor": round(c_factor, 3),
        "shadow_factor": round(s_factor, 3),
        "range_exceeded": effective_distance > max_range_m,
    }

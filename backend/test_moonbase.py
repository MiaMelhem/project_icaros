"""Tests for South Pole lighting and Moon Base route constraints."""

import numpy as np

from backend.hillshade import compute_south_pole_lighting
from backend.moonbase import (
    build_route_constraints,
    cargo_factor,
    shadow_energy_factor,
)
from backend.route_planner import find_route


def _bowl(size: int = 40) -> np.ndarray:
    """Flat crater floor with a rising rim. Center is row/col size//2."""
    rr, cc = np.indices((size, size))
    dist = np.hypot(rr - size // 2, cc - size // 2)
    return np.clip(dist - 8, 0, None) * 30.0


def _analysis(elevation: np.ndarray, slope: np.ndarray | None = None) -> dict:
    slope_grid = np.zeros_like(elevation) if slope is None else slope
    nodata = np.zeros(elevation.shape, dtype=bool)
    return {
        "elevation": elevation,
        "slope": slope_grid,
        "roughness": np.zeros_like(elevation),
        "slope_blocked": slope_grid > 20.0,
        "nodata_mask": nodata,
        "resolution_m_per_pixel": 20.0,
    }


def _rover(**overrides) -> dict:
    rover = {
        "max_slope_deg": 20.0,
        "psr_capable": False,
        "cargo_kg": 0.0,
        "night_survival_hours": 0.0,
        "wireless_charge": False,
    }
    rover.update(overrides)
    return rover


def test_flat_terrain_is_not_a_psr():
    lighting = compute_south_pole_lighting(np.zeros((20, 20)), 20.0)
    assert not lighting["psr_mask"].any()
    assert not lighting["shadow_mask"].any()


def test_crater_floor_is_psr_proxy():
    lighting = compute_south_pole_lighting(_bowl(), 20.0)
    assert lighting["psr_mask"][20, 20]
    assert not lighting["psr_mask"][0, 0]


def test_sunlit_mission_blocks_psr_and_psr_mission_opens_it():
    elevation = _bowl()
    analysis = _analysis(elevation)

    sunlit = build_route_constraints(analysis, _rover(), 1, "sunlit_traverse")
    assert sunlit["psr_mask"][20, 20]
    assert sunlit["blocked_mask"][20, 20]

    opened = build_route_constraints(
        analysis, _rover(psr_capable=True), 1, "psr_access"
    )
    assert not opened["blocked_mask"][20, 20]


def test_psr_access_keeps_the_rover_slope_limit():
    """The guide never raises the slope cap inside a PSR. 30° stays blocked at a 20° limit."""
    elevation = _bowl()
    slope = np.zeros_like(elevation)
    slope[20, 20] = 30.0
    analysis = _analysis(elevation, slope)

    blocked = build_route_constraints(analysis, _rover(), 1, "sunlit_traverse")
    assert blocked["blocked_mask"][20, 20]

    opened = build_route_constraints(
        analysis, _rover(psr_capable=True), 1, "psr_access"
    )
    assert opened["blocked_mask"][20, 20]


def test_distant_rim_shadows_across_the_window():
    """A rim beyond 600 m still shadows. Rays run to the edge of the grid."""
    elevation = np.zeros((80, 40))
    elevation[:, -1] = 80.0
    lighting = compute_south_pole_lighting(elevation, 20.0)
    assert lighting["illumination"][40, 2] < 1.0


def test_psr_is_a_comms_gap_before_any_relay():
    elevation = _bowl()
    analysis = _analysis(elevation)
    result = build_route_constraints(analysis, _rover(psr_capable=True), 1, "psr_access")
    assert result["comms_gap_mask"][20, 20]
    assert not result["comms_gap_mask"][0, 0]
    assert "FN-C-101" in result["summary"]["functional_gaps"]


def test_relay_does_not_clear_a_terrain_comms_gap():
    elevation = np.zeros((30, 110))
    rr, cc = np.indices(elevation.shape)
    for center_col in (15, 95):
        dist = np.hypot(rr - 15, cc - center_col)
        elevation = np.where(dist <= 5, -80.0, elevation)
    analysis = _analysis(elevation)
    relay = [{"kind": "relay", "row": 15, "col": 15}]
    result = build_route_constraints(
        analysis, _rover(psr_capable=True), 2, "psr_access", relay
    )
    assert result["psr_mask"][15, 15]
    assert result["psr_mask"][15, 95]
    assert result["comms_gap_mask"][15, 15]
    assert result["comms_gap_mask"][15, 95]
    assert "relay" in result["summary"]["ignored_assets"]


def test_placed_hardware_does_not_change_the_path():
    elevation = np.zeros((40, 40))
    analysis = _analysis(elevation)
    assets = [
        {"kind": "lander", "row": 20, "col": 20},
        {"kind": "habitat", "row": 10, "col": 10},
        {"kind": "power_node", "row": 12, "col": 18},
    ]
    bare = build_route_constraints(analysis, _rover(), 2, "sunlit_traverse")
    placed = build_route_constraints(
        analysis, _rover(wireless_charge=True), 2, "sunlit_traverse", assets
    )
    assert not placed["keepout_mask"].any()
    assert not placed["blocked_mask"][20, 20]
    assert np.array_equal(placed["blocked_mask"], bare["blocked_mask"])
    assert np.array_equal(placed["extra_cost"], bare["extra_cost"])
    assert placed["summary"]["ignored_assets"] == ["lander", "habitat", "power_node"]


def test_phase_2_ignores_infrastructure_shadow():
    elevation = np.full((30, 30), 100.0)
    analysis = _analysis(elevation)
    asset = [{"kind": "infrastructure", "row": 15, "col": 15}]

    phase2 = build_route_constraints(analysis, _rover(), 2, "sunlit_traverse", asset)
    assert "infrastructure" in phase2["summary"]["ignored_assets"]
    assert not phase2["shadow_mask"][15, 15]


def test_shadow_and_cargo_factors():
    assert shadow_energy_factor(1.0, 0) == 1.8
    assert shadow_energy_factor(1.0, 120) == 1.05
    assert cargo_factor(0) == 1.0
    assert cargo_factor(250) == 1.5


def test_extra_cost_pushes_the_path_off_a_cell():
    hazard = np.zeros((3, 3))
    blocked = np.zeros((3, 3), dtype=bool)
    extra = np.zeros((3, 3))
    extra[0, 1] = 50.0
    result = find_route([0, 0], [0, 2], hazard, blocked, hazard_weight=1.0, extra_cost=extra)
    assert result["route_found"]
    assert [0, 1] not in result["route"]


def test_phase_3_mission_rejected_in_phase_1():
    analysis = _analysis(np.zeros((10, 10)))
    try:
        build_route_constraints(analysis, _rover(), 1, "isru_prospecting")
        raised = False
    except ValueError:
        raised = True
    assert raised

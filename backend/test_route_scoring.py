"""Unit tests for TOPSIS route scoring."""

from backend.route_scoring import (
    SCORE_FLOOR,
    _compress_score_spread,
    _criterion_value,
    _raw_criteria_vector,
    _topsis_overall_scores,
    score_alternatives,
)


def _metrics(
    *,
    hazard: float = 0.2,
    distance: float = 1000,
    max_range: float = 5000,
    time_min: float = 10,
    max_slope: float = 10,
    rover_max_slope: float = 20,
    energy: float = 1200,
    shadow_fraction: float = 0.0,
    psr_fraction: float = 0.0,
    comms_gap_fraction: float = 0.0,
    power_margin_m: float | None = None,
    cargo_kg: float = 0.0,
    enters_keepout: bool = False,
) -> dict:
    return {
        "average_hazard_score": hazard,
        "distance_m": distance,
        "max_range_m": max_range,
        "range_exceeded": distance > max_range,
        "estimated_time_min": time_min,
        "max_slope_deg": max_slope,
        "rover_max_slope_deg": rover_max_slope,
        "energy_score": energy,
        "shadow_fraction": shadow_fraction,
        "psr_fraction": psr_fraction,
        "comms_gap_fraction": comms_gap_fraction,
        "power_margin_m": max_range - distance if power_margin_m is None else power_margin_m,
        "cargo_kg": cargo_kg,
        "enters_keepout": enters_keepout,
    }


def _alt(alt_id: str, metrics: dict, route_found: bool = True) -> dict:
    return {
        "id": alt_id,
        "label": alt_id,
        "route_found": route_found,
        "metrics": metrics,
    }


def test_single_feasible_route_scores_100():
    alts = [_alt("only", _metrics())]
    scored, best = score_alternatives(alts)
    assert scored[0]["scores"]["overall"] == 100.0
    assert best["overall"] == "only"


def test_failed_route_gets_zero_overall_and_is_excluded():
    alts = [
        _alt("ok", _metrics()),
        _alt("blocked", _metrics(), route_found=False),
    ]
    scored, best = score_alternatives(alts)
    assert scored[0]["scores"]["overall"] == 100.0
    assert scored[1]["scores"]["overall"] == 0.0
    assert best["overall"] == "ok"


def test_range_headroom_affects_topsis_ranking():
    alts = [
        _alt("short", _metrics(distance=500, max_range=5000, hazard=0.25, time_min=12)),
        _alt("long", _metrics(distance=4500, max_range=5000, hazard=0.25, time_min=12)),
    ]
    scored, best = score_alternatives(alts)
    short_overall = scored[0]["scores"]["overall"]
    long_overall = scored[1]["scores"]["overall"]
    assert short_overall > long_overall
    assert best["overall"] == "short"


def test_slope_utilization_affects_topsis_ranking():
    alts = [
        _alt("gentle", _metrics(max_slope=8, rover_max_slope=20, hazard=0.2, time_min=10)),
        _alt("steep", _metrics(max_slope=19, rover_max_slope=20, hazard=0.2, time_min=10)),
    ]
    scored, best = score_alternatives(alts)
    assert scored[0]["scores"]["overall"] > scored[1]["scores"]["overall"]
    assert best["overall"] == "gentle"


def test_display_scores_unchanged_for_columns():
    alts = [
        _alt("a", _metrics(hazard=0.1, time_min=5, max_slope=8, distance=800, energy=900)),
        _alt("b", _metrics(hazard=0.3, time_min=15, max_slope=16, distance=2000, energy=2000)),
    ]
    scored, best = score_alternatives(alts)
    assert "safety" in scored[0]["scores"]
    assert "time" in scored[0]["scores"]
    assert "slope" in scored[0]["scores"]
    assert best["safety"] == "a"
    assert best["time"] == "a"


def test_raw_criteria_includes_slope_utilization():
    vector = _raw_criteria_vector(_metrics(max_slope=10, rover_max_slope=20))
    assert vector[3] == 0.5


def test_topsis_three_route_matrix():
    raw = [
        _raw_criteria_vector(_metrics(hazard=0.1, distance=800, time_min=8, max_slope=8)),
        _raw_criteria_vector(_metrics(hazard=0.3, distance=2500, time_min=20, max_slope=15)),
        _raw_criteria_vector(_metrics(hazard=0.2, distance=1500, time_min=12, max_slope=12)),
    ]
    scores = _topsis_overall_scores(raw)
    assert len(scores) == 3
    assert scores[0] == max(scores)


def test_compress_score_spread_maps_to_floor_and_100():
    compressed = _compress_score_spread([100.0, 50.0, 0.0])
    assert compressed == [100.0, 80.0, SCORE_FLOOR]


def test_three_route_feasible_scores_never_hit_zero():
    alts = [
        _alt("best", _metrics(hazard=0.1, time_min=8, max_slope=8, distance=800, energy=900)),
        _alt("mid", _metrics(hazard=0.2, time_min=12, max_slope=12, distance=1500, energy=1500)),
        _alt("worst", _metrics(hazard=0.3, time_min=20, max_slope=16, distance=2500, energy=2500)),
    ]
    scored, best = score_alternatives(alts)

    for alt in scored:
        for key in ("overall", "safety", "time", "slope", "distance", "energy"):
            assert alt["scores"][key] >= SCORE_FLOOR

    assert best["overall"] == "best"
    assert best["time"] == "best"
    assert scored[0]["scores"]["overall"] > scored[2]["scores"]["overall"]


def test_sunlit_mission_prefers_lit_route_and_psr_mission_prefers_shadow():
    shared = dict(hazard=0.2, distance=1000, time_min=10, max_slope=10, energy=1200)
    lit = _alt("lit", _metrics(**shared, shadow_fraction=0.05, psr_fraction=0.0))
    dark = _alt("dark", _metrics(**shared, shadow_fraction=0.9, psr_fraction=0.85))

    sunlit, sunlit_best = score_alternatives([lit, dark], mission_id="sunlit_traverse")
    psr, psr_best = score_alternatives(
        [_alt("lit", _metrics(**shared, shadow_fraction=0.05, psr_fraction=0.0)),
         _alt("dark", _metrics(**shared, shadow_fraction=0.9, psr_fraction=0.85))],
        mission_id="psr_access",
    )

    assert sunlit[0]["scores"]["overall"] > sunlit[1]["scores"]["overall"]
    assert sunlit_best["overall"] == "lit"
    assert psr[1]["scores"]["overall"] > psr[0]["scores"]["overall"]
    assert psr_best["overall"] == "dark"


def test_range_uses_cargo_and_shadow_distance():
    metrics = _metrics(distance=1000, max_range=5000)
    metrics["cargo_factor"] = 2.0
    metrics["shadow_factor"] = 1.5
    assert _criterion_value(metrics, "range") == 5000 - 1000 * 2.0 * 1.5


def test_cargo_energy_lowers_cargo_mission_score():
    from backend.moonbase import cargo_factor

    assert cargo_factor(0) == 1.0
    assert cargo_factor(500) == 2.0

    light = _alt("light", _metrics(energy=1000, cargo_kg=0))
    heavy = _alt("heavy", _metrics(energy=2200, cargo_kg=400))
    scored, best = score_alternatives([light, heavy], mission_id="cargo_reposition")
    assert best["overall"] == "light"
    assert scored[0]["scores"]["overall"] > scored[1]["scores"]["overall"]


def test_worst_feasible_overall_at_least_floor():
    alts = [
        _alt("short", _metrics(distance=500, max_range=5000, hazard=0.25, time_min=12)),
        _alt("long", _metrics(distance=4500, max_range=5000, hazard=0.25, time_min=12)),
    ]
    scored, _ = score_alternatives(alts)
    assert min(scored[0]["scores"]["overall"], scored[1]["scores"]["overall"]) >= SCORE_FLOOR

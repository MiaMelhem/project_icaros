"""
Normalize route metrics into 0–100 comparison scores.

Display columns (Safety, Time, Slope, Distance, Energy) use absolute or relative
scales, then compress to [SCORE_FLOOR, 100] within each comparison set.
Overall uses TOPSIS on raw criteria, then the same compression.
"""

import math

from backend.moonbase import scoring_spec

SCORE_FLOOR = 60.0

TOPSIS_CRITERIA = ("safety", "range", "time", "slope", "distance", "energy")

CRITERION_TYPES = {
    "safety": "benefit",
    "range": "benefit",
    "time": "cost",
    "slope": "cost",
    "distance": "cost",
    "energy": "cost",
}

TOPSIS_WEIGHTS = {
    "safety": 0.30,
    "range": 0.10,
    "time": 0.22,
    "slope": 0.18,
    "distance": 0.10,
    "energy": 0.10,
}


def _score_absolute_safety(average_hazard_score: float | None) -> float:
    """Map average hazard to 0–100 where lower hazard means higher safety."""
    if average_hazard_score is None:
        return 0.0
    return round(max(0.0, min(100.0, (1.0 - average_hazard_score) * 100)), 1)


def _compress_score_spread(
    scores: list[float],
    *,
    floor: float = SCORE_FLOOR,
    eligible: list[bool] | None = None,
) -> list[float]:
    """
    Rescale scores within a comparison set to [floor, 100].

    Best eligible route maps to 100, worst eligible to floor. Ranking unchanged.
    Ineligible routes (e.g. failed) stay 0.
    """
    if not scores:
        return []

    if eligible is None:
        eligible = [True] * len(scores)

    eligible_pairs = [(i, scores[i]) for i in range(len(scores)) if eligible[i]]

    if len(eligible_pairs) <= 1:
        result = list(scores)
        for i in range(len(scores)):
            if not eligible[i]:
                result[i] = 0.0
            elif len(eligible_pairs) == 1:
                result[i] = 100.0
        return result

    values = [value for _, value in eligible_pairs]
    lo = min(values)
    hi = max(values)

    result = list(scores)
    for i in range(len(scores)):
        if not eligible[i]:
            result[i] = 0.0
        elif hi == lo:
            result[i] = 100.0
        else:
            result[i] = round(
                floor + (scores[i] - lo) / (hi - lo) * (100.0 - floor),
                1,
            )
    return result


def _score_lower_is_better(raw_values: list[float | None], index: int) -> float:
    """Map a metric to 0–100 where the minimum raw value scores 100."""
    valid = [v for v in raw_values if v is not None]
    if not valid:
        return 0.0

    minimum = min(valid)
    maximum = max(valid)
    if maximum == minimum:
        return 100.0

    raw = raw_values[index]
    if raw is None:
        return 0.0

    normalized = 1.0 - (raw - minimum) / (maximum - minimum)
    return round(max(0.0, min(100.0, normalized * 100)), 1)


def _slope_utilization(metrics: dict) -> float:
    """Route max slope as a fraction of the rover's passability limit (cost)."""
    route_max = float(metrics.get("max_slope_deg", 0))
    rover_max = float(metrics.get("rover_max_slope_deg", 0))
    if rover_max <= 0:
        return route_max
    return route_max / rover_max


def _raw_criteria_vector(metrics: dict) -> list[float]:
    """Extract six raw TOPSIS criteria values from route metrics."""
    return [_criterion_value(metrics, name) for name in TOPSIS_CRITERIA]


def _criterion_value(metrics: dict, name: str) -> float:
    """One raw TOPSIS input. Missing Moon Base fields count as zero."""
    distance_m = float(metrics.get("distance_m", 0))
    max_range_m = float(metrics.get("max_range_m", 0))
    if name == "safety":
        return 1.0 - float(metrics.get("average_hazard_score", 0))
    if name == "range":
        cargo = float(metrics.get("cargo_factor", 1.0))
        shadow = float(metrics.get("shadow_factor", 1.0))
        effective = distance_m * cargo * shadow
        return max_range_m - effective
    if name == "time":
        return float(metrics.get("estimated_time_min", 0))
    if name == "slope":
        return _slope_utilization(metrics)
    if name == "distance":
        return distance_m
    if name == "energy":
        return float(metrics.get("energy_score", 0))
    if name == "shadow":
        return float(metrics.get("shadow_fraction", 0))
    if name == "psr":
        return float(metrics.get("psr_fraction", 0))
    if name == "comms":
        return float(metrics.get("comms_gap_fraction", 0))
    if name == "power":
        if "power_margin_m" in metrics:
            return float(metrics["power_margin_m"])
        return max(0.0, max_range_m - distance_m)
    if name == "keepout":
        return 1.0 if metrics.get("enters_keepout") else 0.0
    raise KeyError(f"Unknown scoring criterion '{name}'")


def _topsis_overall_scores(
    raw_matrix: list[list[float]],
    weights: list[float] | None = None,
    types: list[str] | None = None,
) -> list[float]:
    """
    Compute TOPSIS relative closeness (0–100) for each row in the decision matrix.

    Steps: vector normalization, weighting, ideal best/worst, Euclidean distances,
    C* = S- / (S* + S-).
    """
    n = len(raw_matrix)
    if n == 0:
        return []
    if n == 1:
        return [100.0]

    m = len(raw_matrix[0])
    if weights is None:
        weights = [TOPSIS_WEIGHTS[criterion] for criterion in TOPSIS_CRITERIA]
    if types is None:
        types = [CRITERION_TYPES[criterion] for criterion in TOPSIS_CRITERIA]

    # Vector normalization per criterion (column)
    normalized_cols: list[list[float]] = []
    for j in range(m):
        column = [raw_matrix[i][j] for i in range(n)]
        denom = math.sqrt(sum(value * value for value in column))
        if denom == 0:
            normalized_cols.append([0.0] * n)
        else:
            normalized_cols.append([value / denom for value in column])

    # Weighted matrix v[i][j]
    weighted = [
        [weights[j] * normalized_cols[j][i] for j in range(m)]
        for i in range(n)
    ]

    # Ideal best and worst per criterion
    ideal_best: list[float] = []
    ideal_worst: list[float] = []
    for j in range(m):
        column = [weighted[i][j] for i in range(n)]
        if types[j] == "benefit":
            ideal_best.append(max(column))
            ideal_worst.append(min(column))
        else:
            ideal_best.append(min(column))
            ideal_worst.append(max(column))

    scores: list[float] = []
    for i in range(n):
        dist_best = math.sqrt(
            sum((weighted[i][j] - ideal_best[j]) ** 2 for j in range(m))
        )
        dist_worst = math.sqrt(
            sum((weighted[i][j] - ideal_worst[j]) ** 2 for j in range(m))
        )
        if dist_best + dist_worst == 0:
            closeness = 1.0
        else:
            closeness = dist_worst / (dist_best + dist_worst)
        scores.append(round(closeness * 100, 1))

    return scores


def score_alternatives(
    alternatives: list[dict],
    mission_id: str | None = None,
    uncrewed: bool = False,
) -> tuple[list[dict], dict]:
    """
    Add per-metric display scores and TOPSIS overall scores to each alternative.

    Each alternative must have route_found and metrics dict when found.
    Returns updated alternatives and best_by_metric mapping.
    """
    if not alternatives:
        return [], {}

    def metric_values(key: str) -> list[float | None]:
        values: list[float | None] = []
        for alt in alternatives:
            if not alt.get("route_found"):
                values.append(None)
                continue
            metrics = alt.get("metrics") or {}
            values.append(float(metrics.get(key, 0)))
        return values

    relative_metric_keys = {
        "time": "estimated_time_min",
        "distance": "distance_m",
        "slope": "max_slope_deg",
        "energy": "energy_score",
    }

    scored_metrics: dict[str, list[float]] = {
        "safety": [],
        **{name: [] for name in relative_metric_keys},
    }

    for index, alt in enumerate(alternatives):
        if alt.get("route_found"):
            metrics = alt.get("metrics") or {}
            scored_metrics["safety"].append(
                _score_absolute_safety(float(metrics.get("average_hazard_score", 0)))
            )
        else:
            scored_metrics["safety"].append(0.0)

        for score_name, metric_key in relative_metric_keys.items():
            scored_metrics[score_name].append(
                _score_lower_is_better(metric_values(metric_key), index)
            )

    eligible = [bool(alt.get("route_found")) for alt in alternatives]

    compressed_metrics: dict[str, list[float]] = {}
    for score_name, values in scored_metrics.items():
        compressed_metrics[score_name] = _compress_score_spread(values, eligible=eligible)

    best_by_metric: dict[str, str | None] = {}
    for score_name, scores in compressed_metrics.items():
        if not scores:
            best_by_metric[score_name] = None
            continue
        eligible_scores = [
            (i, scores[i]) for i in range(len(scores)) if eligible[i]
        ]
        if not eligible_scores:
            best_by_metric[score_name] = None
            continue
        best_index, best_score = max(eligible_scores, key=lambda pair: pair[1])
        if best_score <= 0:
            best_by_metric[score_name] = None
            continue
        best_by_metric[score_name] = alternatives[best_index]["id"]

    # TOPSIS overall on feasible routes only
    feasible_indices = [
        i for i, alt in enumerate(alternatives) if alt.get("route_found")
    ]
    if mission_id:
        spec = scoring_spec(mission_id, uncrewed=uncrewed)
        raw_matrix = [
            [
                _criterion_value(alternatives[i].get("metrics") or {}, name)
                for name, _kind, _weight in spec
            ]
            for i in feasible_indices
        ]
        topsis_raw = _topsis_overall_scores(
            raw_matrix,
            weights=[weight for _name, _kind, weight in spec],
            types=[kind for _name, kind, _weight in spec],
        )
    else:
        raw_matrix = [
            _raw_criteria_vector(alternatives[i].get("metrics") or {})
            for i in feasible_indices
        ]
        topsis_raw = _topsis_overall_scores(raw_matrix)

    overall_raw = [0.0] * len(alternatives)
    for idx, score in zip(feasible_indices, topsis_raw):
        overall_raw[idx] = score
    overall_compressed = _compress_score_spread(overall_raw, eligible=eligible)

    score_names = ["safety", *relative_metric_keys.keys()]

    for index, alt in enumerate(alternatives):
        display_scores = {
            name: compressed_metrics[name][index] for name in score_names
        }
        alt["scores"] = {**display_scores, "overall": overall_compressed[index]}

    eligible_overall = [
        (i, overall_compressed[i]) for i in range(len(alternatives)) if eligible[i]
    ]
    if eligible_overall:
        best_index, best_score = max(eligible_overall, key=lambda pair: pair[1])
        best_by_metric["overall"] = (
            alternatives[best_index]["id"] if best_score > 0 else None
        )
    else:
        best_by_metric["overall"] = None

    return alternatives, best_by_metric

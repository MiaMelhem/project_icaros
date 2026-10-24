"""
Route feasibility checks with human-readable reasons.
"""

import math
from collections import deque

import numpy as np


def flood_reachable(blocked_mask: np.ndarray, start: tuple[int, int]) -> set[tuple[int, int]]:
    """Return all passable cells reachable from start via 8-connectivity."""
    rows, cols = blocked_mask.shape
    start_row, start_col = start

    if (
        start_row < 0
        or start_row >= rows
        or start_col < 0
        or start_col >= cols
        or blocked_mask[start_row, start_col]
    ):
        return set()

    visited = set()
    queue = deque([start])
    visited.add(start)

    directions = [
        (-1, 0),
        (1, 0),
        (0, -1),
        (0, 1),
        (-1, -1),
        (-1, 1),
        (1, -1),
        (1, 1),
    ]

    while queue:
        row, col = queue.popleft()
        for d_row, d_col in directions:
            nr, nc = row + d_row, col + d_col
            if (
                0 <= nr < rows
                and 0 <= nc < cols
                and not blocked_mask[nr, nc]
                and (nr, nc) not in visited
            ):
                visited.add((nr, nc))
                queue.append((nr, nc))

    return visited


def describe_cell(
    row: int,
    col: int,
    elevation: np.ndarray,
    slope: np.ndarray,
    nodata_mask: np.ndarray,
    blocked_mask: np.ndarray,
    max_slope_deg: float,
) -> dict:
    """Describe a single grid cell for hover / click feedback."""
    if nodata_mask[row, col]:
        return {
            "row": row,
            "col": col,
            "passable": False,
            "reason_code": "nodata",
            "message": "No DEM data — pick a point on mapped terrain.",
            "elevation_m": None,
            "slope_deg": None,
        }

    elev = float(elevation[row, col])
    slope_deg = float(slope[row, col])
    blocked = bool(blocked_mask[row, col])

    if blocked:
        return {
            "row": row,
            "col": col,
            "passable": False,
            "reason_code": "too_steep",
            "message": f"Too steep ({slope_deg:.1f}° > {max_slope_deg:.0f}° rover limit).",
            "elevation_m": round(elev, 1),
            "slope_deg": round(slope_deg, 1),
        }

    return {
        "row": row,
        "col": col,
        "passable": True,
        "reason_code": "ok",
        "message": f"Passable ({slope_deg:.1f}° slope).",
        "elevation_m": round(elev, 1),
        "slope_deg": round(slope_deg, 1),
    }


def validate_route(
    start: list[int],
    goal: list[int],
    elevation: np.ndarray,
    slope: np.ndarray,
    nodata_mask: np.ndarray,
    blocked_mask: np.ndarray,
    rover_config: dict,
    resolution_m_per_pixel: float = 20.0,
) -> dict:
    """
    Check whether a route can exist between start and goal.

    Returns feasible flag, reason_code, message, and per-point details.
    """
    max_slope = rover_config["max_slope_deg"]
    start_tuple = (start[0], start[1])
    goal_tuple = (goal[0], goal[1])

    start_info = describe_cell(
        start[0], start[1], elevation, slope, nodata_mask, blocked_mask, max_slope
    )
    goal_info = describe_cell(
        goal[0], goal[1], elevation, slope, nodata_mask, blocked_mask, max_slope
    )

    blocked_fraction = float(blocked_mask.mean())

    if not start_info["passable"]:
        return {
            "feasible": False,
            "reason_code": f"start_{start_info['reason_code']}",
            "message": f"Point A cannot be used: {start_info['message']}",
            "start": start_info,
            "goal": goal_info,
            "blocked_fraction": round(blocked_fraction, 3),
        }

    if not goal_info["passable"]:
        return {
            "feasible": False,
            "reason_code": f"goal_{goal_info['reason_code']}",
            "message": f"Point B cannot be used: {goal_info['message']}",
            "start": start_info,
            "goal": goal_info,
            "blocked_fraction": round(blocked_fraction, 3),
        }

    reachable = flood_reachable(blocked_mask, start_tuple)
    if goal_tuple not in reachable:
        return {
            "feasible": False,
            "reason_code": "disconnected",
            "message": (
                "No passable path between Point A and Point B — impassable terrain "
                "or missing DEM data blocks the way. Pick both points on the same "
                "connected terrain."
            ),
            "start": start_info,
            "goal": goal_info,
            "blocked_fraction": round(blocked_fraction, 3),
        }

    row_diff = goal[0] - start[0]
    col_diff = goal[1] - start[1]
    straight_line_m = math.sqrt(row_diff ** 2 + col_diff ** 2) * resolution_m_per_pixel
    max_range_m = float(rover_config.get("max_range_m", float("inf")))

    message = "Route looks feasible — run optimization to compute the path."
    if straight_line_m > max_range_m:
        message += (
            " Straight-line distance exceeds rover range — the optimized route "
            "may also exceed it."
        )

    return {
        "feasible": True,
        "reason_code": "ok",
        "message": message,
        "start": start_info,
        "goal": goal_info,
        "blocked_fraction": round(blocked_fraction, 3),
    }


def hover_message(
    row: int,
    col: int,
    elevation: np.ndarray,
    slope: np.ndarray,
    nodata_mask: np.ndarray,
    blocked_mask: np.ndarray,
    max_slope_deg: float,
    start: list[int] | None = None,
) -> dict:
    """Build hover tooltip content for a cell, including reachability from start."""
    cell = describe_cell(
        row, col, elevation, slope, nodata_mask, blocked_mask, max_slope_deg
    )

    if start is not None and cell["passable"]:
        reachable = flood_reachable(blocked_mask, (start[0], start[1]))
        if (row, col) not in reachable:
            cell = {
                **cell,
                "reachable_from_start": False,
                "message": (
                    f"{cell['message']} Not reachable from Point A — blocked terrain in the way."
                ),
            }
        else:
            cell = {**cell, "reachable_from_start": True}

    return cell

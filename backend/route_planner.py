"""
A* pathfinding for lunar rover route planning.

This module finds a low-hazard path from start to goal on a terrain grid.
Written for beginner readability — each step is explicit.
"""

import heapq
import math


def is_valid_cell(row, col, grid_shape, blocked_mask):
    """
    Check if a grid cell can be visited.

    A cell is valid if it is inside the grid and not blocked.
    """
    num_rows, num_cols = grid_shape

    if row < 0 or row >= num_rows:
        return False
    if col < 0 or col >= num_cols:
        return False
    if blocked_mask[row, col]:
        return False

    return True


def heuristic(cell_a, cell_b):
    """
    Estimate straight-line distance between two cells.

    Uses Euclidean distance — a common A* heuristic for grid maps.
    """
    row_a, col_a = cell_a
    row_b, col_b = cell_b
    return math.sqrt((row_a - row_b) ** 2 + (col_a - col_b) ** 2)


def reconstruct_path(came_from, current):
    """
    Walk backwards through came_from links to rebuild the full path.

    Returns a list of [row, col] pairs from start to goal.
    """
    path = [list(current)]
    while current in came_from:
        current = came_from[current]
        path.append(list(current))
    path.reverse()
    return path


# 8-direction movement: up, down, left, right, and 4 diagonals
DIRECTIONS = [
    (-1, 0),   # up
    (1, 0),    # down
    (0, -1),   # left
    (0, 1),    # right
    (-1, -1),  # up-left
    (-1, 1),   # up-right
    (1, -1),   # down-left
    (1, 1),    # down-right
]


def find_route(start, goal, hazard_score, blocked_mask, hazard_weight=5.0, extra_cost=None):
    """
    Find an optimized route using A* pathfinding.

    Parameters
    ----------
    start : [row, col]
        Starting grid cell.
    goal : [row, col]
        Goal grid cell.
    hazard_score : 2D numpy array
        Hazard value at each cell (higher = worse).
    blocked_mask : 2D boolean array
        True where the rover cannot pass.
    hazard_weight : float
        How much to penalize hazardous terrain in the path cost.
    extra_cost : 2D array or None
        Added to each step. Moon Base missions put shadow, comms, keep-out,
        and power cost here. None keeps the original hazard-only cost.

    Returns
    -------
    dict with:
        route : list of [row, col] pairs (empty if no path found)
        route_found : bool
        total_cost : float cost of the path (infinity if not found)
    """
    import numpy as np

    grid_shape = hazard_score.shape
    start_tuple = (start[0], start[1])
    goal_tuple = (goal[0], goal[1])

    # Check that start and goal are valid
    if not is_valid_cell(start[0], start[1], grid_shape, blocked_mask):
        return {"route": [], "route_found": False, "total_cost": float("inf")}

    if not is_valid_cell(goal[0], goal[1], grid_shape, blocked_mask):
        return {"route": [], "route_found": False, "total_cost": float("inf")}

    # Priority queue: (f_score, counter, current_cell)
    # counter breaks ties so heapq does not compare tuples of cells
    counter = 0
    open_set = []
    heapq.heappush(open_set, (heuristic(start_tuple, goal_tuple), counter, start_tuple))

    # g_score[cell] = cost from start to that cell
    g_score = {start_tuple: 0.0}

    # came_from[cell] = previous cell on the best path
    came_from = {}

    while open_set:
        _, _, current = heapq.heappop(open_set)

        # Found the goal
        if current == goal_tuple:
            path = reconstruct_path(came_from, current)
            return {
                "route": path,
                "route_found": True,
                "total_cost": g_score[current],
            }

        current_row, current_col = current

        for d_row, d_col in DIRECTIONS:
            neighbor_row = current_row + d_row
            neighbor_col = current_col + d_col
            neighbor = (neighbor_row, neighbor_col)

            if not is_valid_cell(neighbor_row, neighbor_col, grid_shape, blocked_mask):
                continue

            # Movement cost: base step cost + hazard penalty
            # Diagonal steps cost sqrt(2), straight steps cost 1
            if d_row != 0 and d_col != 0:
                step_cost = math.sqrt(2)
            else:
                step_cost = 1.0

            hazard_at_cell = float(hazard_score[neighbor_row, neighbor_col])
            architecture_cost = 0.0
            if extra_cost is not None:
                architecture_cost = float(extra_cost[neighbor_row, neighbor_col])
            move_cost = step_cost + hazard_weight * hazard_at_cell + architecture_cost

            tentative_g = g_score[current] + move_cost

            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + heuristic(neighbor, goal_tuple)
                counter += 1
                heapq.heappush(open_set, (f_score, counter, neighbor))

    # No path found
    return {"route": [], "route_found": False, "total_cost": float("inf")}

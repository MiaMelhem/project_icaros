"""
Route export and metrics calculation for ICAROS.

Converts a planned route into a pandas DataFrame, computes summary metrics,
and exports to CSV string format.
"""

import math

import pandas as pd


def route_to_dataframe(route, elevation, slope, hazard_score, resolution_m_per_pixel):
    """
    Build a DataFrame with one row per step along the route.

    Columns: step, row, col, x_m, y_m, elevation_m, slope_deg, hazard_score
    """
    rows = []

    for step_index, cell in enumerate(route):
        row = cell[0]
        col = cell[1]

        x_m = col * resolution_m_per_pixel
        y_m = row * resolution_m_per_pixel

        rows.append(
            {
                "step": step_index,
                "row": row,
                "col": col,
                "x_m": round(x_m, 2),
                "y_m": round(y_m, 2),
                "elevation_m": round(float(elevation[row, col]), 2),
                "slope_deg": round(float(slope[row, col]), 2),
                "hazard_score": round(float(hazard_score[row, col]), 4),
            }
        )

    return pd.DataFrame(rows)


def calculate_route_metrics(route_df, rover_config, resolution_m_per_pixel):
    """
    Calculate summary metrics for a planned route.

    Returns distance, time estimate, slope stats, hazard average, and energy score.
    """
    if len(route_df) < 2:
        return {
            "distance_m": 0.0,
            "estimated_time_min": 0.0,
            "max_slope_deg": 0.0,
            "average_slope_deg": 0.0,
            "average_hazard_score": 0.0,
            "energy_score": 0.0,
        }

    # Sum step-to-step distances in meters
    total_distance_m = 0.0
    for i in range(1, len(route_df)):
        row_diff = route_df.iloc[i]["row"] - route_df.iloc[i - 1]["row"]
        col_diff = route_df.iloc[i]["col"] - route_df.iloc[i - 1]["col"]
        step_distance_cells = math.sqrt(row_diff ** 2 + col_diff ** 2)
        total_distance_m += step_distance_cells * resolution_m_per_pixel

    nominal_speed = rover_config["nominal_speed_mps"]
    energy_factor = rover_config["energy_factor"]

    estimated_time_min = (total_distance_m / nominal_speed) / 60.0

    max_slope_deg = float(route_df["slope_deg"].max())
    average_slope_deg = float(route_df["slope_deg"].mean())
    average_hazard_score = float(route_df["hazard_score"].mean())

    # Simple energy model: distance × rover energy factor × hazard multiplier
    energy_score = total_distance_m * energy_factor * (1.0 + average_hazard_score)

    return {
        "distance_m": round(total_distance_m, 2),
        "estimated_time_min": round(estimated_time_min, 2),
        "max_slope_deg": round(max_slope_deg, 2),
        "average_slope_deg": round(average_slope_deg, 2),
        "average_hazard_score": round(average_hazard_score, 4),
        "energy_score": round(energy_score, 2),
    }


def enrich_metrics_with_range(metrics: dict, rover_config: dict) -> dict:
    """Add rover limit fields used for range warnings and TOPSIS scoring."""
    max_range_m = float(rover_config["max_range_m"])
    distance_m = float(metrics["distance_m"])
    return {
        **metrics,
        "max_range_m": max_range_m,
        "range_exceeded": distance_m > max_range_m,
        "rover_max_slope_deg": float(rover_config["max_slope_deg"]),
    }


def empty_route_metrics(rover_config: dict) -> dict:
    """Zero metrics for a failed route, including range fields."""
    return enrich_metrics_with_range(
        {
            "distance_m": 0.0,
            "estimated_time_min": 0.0,
            "max_slope_deg": 0.0,
            "average_slope_deg": 0.0,
            "average_hazard_score": 0.0,
            "energy_score": 0.0,
        },
        rover_config,
    )


def dataframe_to_csv_string(route_df):
    """Convert a route DataFrame to a CSV string for download."""
    return route_df.to_csv(index=False)

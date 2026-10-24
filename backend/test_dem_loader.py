"""Tests for the georeferenced 4 km DEM crop."""

import os

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from backend.dem_loader import (
    DemNotUsable,
    coverage_status,
    load_dem_grid,
    load_site_terrain,
)
from backend.export_utils import calculate_route_metrics, route_to_dataframe
from backend.lunar_sites import LUNAR_SITES
from backend.rover_config import get_rover_config
from backend.terrain_analysis import build_terrain_analysis
from backend.terrain_metrics import compute_slope

DEM_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "dems")
POLAR_WKT = (
    'PROJCS["PolarStereographic Moon",'
    'GEOGCS["GCS_Moon",DATUM["D_Moon",SPHEROID["Moon_polarRadius",1737400,0]],'
    'PRIMEM["Reference_Meridian",0],UNIT["degree",0.0174532925199433]],'
    'PROJECTION["Polar_Stereographic"],'
    'PARAMETER["latitude_of_origin",-90],'
    'PARAMETER["central_meridian",0],'
    'PARAMETER["false_easting",0],'
    'PARAMETER["false_northing",0],'
    'UNIT["metre",1]]'
)

# Measured from the corrected loader. Bounds are left, bottom, right, top.
EXPECTED = {
    "nobile-crater": {
        "rule": "catalog_latlon",
        "center_xy": (77846.0, 139690.0),
        "bounds": (75846.0, 137690.0, 79846.0, 141690.0),
        "nodata": 0.225725,
        "coverage": "partial",
    },
    "shackleton-rim": {
        "rule": "source_bounds_center",
        "center_xy": (-2641.0, -7359.0),
        "bounds": (-4641.0, -9359.0, -641.0, -5359.0),
        "nodata": 0.192325,
        "coverage": "partial",
    },
    "malapert-massif": {
        "rule": "source_bounds_center",
        "center_xy": (-5041.0, 122001.0),
        "bounds": (-7041.0, 120001.0, -3041.0, 124001.0),
        "nodata": 0.020375,
        "coverage": "complete",
    },
    "haworth-crater": {
        "rule": "source_bounds_center",
        "center_xy": (-38000.0, 90500.0),
        "bounds": (-40000.0, 88500.0, -36000.0, 92500.0),
        "nodata": 0.0,
        "coverage": "complete",
    },
    "amundsen-rim": {
        "rule": "source_bounds_center",
        "center_xy": (164000.0, 61500.0),
        "bounds": (162000.0, 59500.0, 166000.0, 63500.0),
        "nodata": 0.0,
        "coverage": "complete",
    },
}


def _write_polar(path, elevation, origin_x, origin_y, pixel_m, nodata=-1.0e38):
    height, width = elevation.shape
    transform = from_origin(origin_x, origin_y, pixel_m, pixel_m)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs=POLAR_WKT,
        transform=transform,
        nodata=nodata,
    ) as dataset:
        dataset.write(elevation.astype(np.float32), 1)


def test_rectangular_crop_keeps_meter_spacing_and_nodata(tmp_path):
    """A wide source must not be stretched, and nodata must not be filled."""
    pixel_m = 10.0
    width, height = 80, 40  # 800 m by 400 m
    origin_x, origin_y = 10000.0, 20000.0
    cols = np.arange(width)[None, :]
    rows = np.arange(height)[:, None]
    x_center = origin_x + (cols + 0.5) * pixel_m
    elevation = np.broadcast_to(x_center, (height, width)).copy()
    # Nodata begins inside the central 200 m crop, at easting 10440 m.
    elevation[:, 44:] = -1.0e38
    path = tmp_path / "rect.tif"
    _write_polar(path, elevation, origin_x, origin_y, pixel_m)

    with rasterio.open(path) as dataset:
        # Catalog point is outside this small raster, so the file center is used.
        grid = load_dem_grid(dataset, catalog_lat=-80.0, catalog_lon=10.0, size=10, resolution_m=20.0)

    assert grid["center_rule"] == "source_bounds_center"
    assert grid["elevation"].shape == (10, 10)
    assert grid["output_cell_m"] == 20.0
    assert grid["window_m"] == 200.0
    assert grid["crop_right_m"] - grid["crop_left_m"] == pytest.approx(200.0)
    assert grid["crop_top_m"] - grid["crop_bottom_m"] == pytest.approx(200.0)
    assert "not on the named landmark" in grid["center_note"]

    # Cell centers of a 20 m mean of 10 m samples equal the cell-center easting.
    left = grid["crop_left_m"]
    for col in range(6):
        cell = grid["elevation"][5, col]
        expected_x = left + (col + 0.5) * 20.0
        assert cell == pytest.approx(expected_x, abs=0.2)
        assert not grid["nodata_mask"][5, col]

    # Output columns from easting 10440 m onward contain only nodata samples.
    assert grid["nodata_mask"][:, 7:].all()
    assert np.isnan(grid["elevation"][:, 7:]).all()


def test_catalog_center_is_used_when_it_falls_inside(tmp_path):
    pixel_m = 20.0
    size = 300  # 6 km, large enough for a 2 km window at the catalog point
    # Place the raster so the Nobile catalog point is inside, away from the edges.
    from backend.dem_loader import forward_south_polar, _projection_params

    with rasterio.open(os.path.join(DEM_DIR, "nobile-crater.tif")) as sample:
        projection = _projection_params(sample.crs)
    catalog_x, catalog_y = forward_south_polar(-84.73, 29.13, projection)
    origin_x = catalog_x - 3000.0
    origin_y = catalog_y + 3000.0
    elevation = np.zeros((size, size), dtype=np.float32)
    path = tmp_path / "inside.tif"
    _write_polar(path, elevation, origin_x, origin_y, pixel_m, nodata=-9999.0)

    with rasterio.open(path) as dataset:
        grid = load_dem_grid(dataset, -84.73, 29.13, size=100, resolution_m=20.0)

    assert grid["center_rule"] == "catalog_latlon"
    assert grid["catalog_inside_source"] is True
    assert grid["crop_center_x_m"] == pytest.approx(catalog_x, abs=pixel_m)
    assert grid["crop_center_y_m"] == pytest.approx(catalog_y, abs=pixel_m)
    assert grid["nodata_fraction"] == 0.0


def test_geographic_raster_is_rejected(tmp_path):
    path = tmp_path / "degrees.tif"
    transform = from_origin(-10.0, -80.0, 0.01, 0.01)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=20,
        width=40,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
    ) as dataset:
        dataset.write(np.ones((20, 40), dtype=np.float32), 1)

    with rasterio.open(path) as dataset:
        with pytest.raises(DemNotUsable, match="not a projected meter grid"):
            load_dem_grid(dataset, -85.0, 0.0, size=10, resolution_m=20.0)


def test_missing_file_is_labeled_synthetic(monkeypatch):
    monkeypatch.setattr(
        "backend.dem_loader._dem_path",
        lambda site_id: "/tmp/icaros-missing-dem.tif",
    )
    monkeypatch.setattr("backend.dem_loader._resolve_storage_path", lambda site_id, site: None)
    result = load_site_terrain("nobile-crater", size=80, resolution_m_per_pixel=20.0)
    meta = result["metadata"]
    assert meta["terrain_kind"] == "synthetic"
    assert meta["source"] == "site_synthetic"
    assert "not a NASA DEM" in meta["description"]
    assert result["nodata_mask"].shape == (80, 80)


def test_slope_and_distance_use_twenty_meter_cells():
    elevation = np.zeros((5, 5), dtype=float)
    elevation += np.arange(5)[None, :] * 20.0  # 20 m rise per 20 m cell
    slope = compute_slope(elevation, 20.0)
    assert slope[2, 2] == pytest.approx(45.0, abs=0.05)

    route = [[2, 1], [2, 3]]
    frame = route_to_dataframe(route, elevation, slope, np.zeros_like(slope), 20.0)
    metrics = calculate_route_metrics(
        frame,
        {"nominal_speed_mps": 2.0, "energy_factor": 1.0},
        20.0,
    )
    assert metrics["distance_m"] == pytest.approx(40.0)

    diagonal = [[0, 0], [1, 1]]
    frame = route_to_dataframe(diagonal, elevation, slope, np.zeros_like(slope), 20.0)
    metrics = calculate_route_metrics(
        frame,
        {"nominal_speed_mps": 2.0, "energy_factor": 1.0},
        20.0,
    )
    # Route metrics are rounded to 0.01 m. 20 * sqrt(2) = 28.284... m.
    assert metrics["distance_m"] == pytest.approx(28.28, abs=0.011)


def test_coverage_status_flags_partial_and_unsuitable():
    assert coverage_status(0.0) == "complete"
    assert coverage_status(0.02) == "complete"
    assert coverage_status(0.19) == "partial"
    assert coverage_status(0.23) == "partial"
    assert coverage_status(0.5) == "unsuitable"


@pytest.mark.parametrize("site", LUNAR_SITES, ids=lambda site: site["id"])
def test_real_site_crop_matches_measured_grid(site):
    path = os.path.join(DEM_DIR, site["dem_filename"])
    if not os.path.isfile(path):
        pytest.skip(f"missing {path}")

    result = load_site_terrain(site["id"], size=200, resolution_m_per_pixel=20.0)
    meta = result["metadata"]
    expected = EXPECTED[site["id"]]

    assert result["elevation"].shape == (200, 200)
    assert result["nodata_mask"].shape == (200, 200)
    assert meta["terrain_kind"] == "real_dem"
    assert meta["source"] == "dem_local"
    assert meta["resolution_m_per_pixel"] == 20.0
    assert meta["effective_resolution_m_per_pixel"] == 20.0
    assert meta["window_size_m"] == 4000.0
    assert meta["center_rule"] == expected["rule"]
    assert meta["coverage_status"] == expected["coverage"]
    assert meta["nodata_fraction"] == pytest.approx(expected["nodata"], abs=1e-4)
    assert meta["crop_center_xy_m"][0] == pytest.approx(expected["center_xy"][0], abs=0.1)
    assert meta["crop_center_xy_m"][1] == pytest.approx(expected["center_xy"][1], abs=0.1)
    for actual, wanted in zip(meta["crop_bounds_m"], expected["bounds"]):
        assert actual == pytest.approx(wanted, abs=0.1)
    assert meta["crop_bounds_m"][2] - meta["crop_bounds_m"][0] == pytest.approx(4000.0)
    assert meta["crop_bounds_m"][3] - meta["crop_bounds_m"][1] == pytest.approx(4000.0)
    assert "Polar_Stereographic" in meta["source_crs"]
    assert meta["source_width"] != 200 or meta["source_height"] != 200

    if expected["rule"] == "source_bounds_center":
        assert "not on the named landmark" in meta["center_note"]
        assert meta["catalog_inside_source"] is False
    else:
        assert meta["catalog_inside_source"] is True

    valid = ~result["nodata_mask"]
    assert np.isnan(result["elevation"][result["nodata_mask"]]).all()
    assert np.isfinite(result["elevation"][valid]).all()

    rover = get_rover_config("Astrolab CLV-1")
    analysis = build_terrain_analysis(
        result["elevation"],
        result["nodata_mask"],
        meta["effective_resolution_m_per_pixel"],
        rover,
    )
    assert analysis["resolution_m_per_pixel"] == 20.0
    filled = np.where(valid, result["elevation"], np.nanmedian(result["elevation"][valid]))
    gradient_y, gradient_x = np.gradient(filled, 20.0)
    manual = np.degrees(np.arctan(np.sqrt(gradient_x**2 + gradient_y**2)))
    interior = valid.copy()
    interior[0, :] = interior[-1, :] = interior[:, 0] = interior[:, -1] = False
    assert np.allclose(analysis["slope"][interior], manual[interior], atol=1e-6)

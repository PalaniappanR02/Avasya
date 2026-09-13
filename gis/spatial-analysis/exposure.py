from __future__ import annotations

import geopandas as gpd

DEMO_PROJECTED_CRS = "EPSG:32643"
WGS84 = "EPSG:4326"


def calculate_hazard_exposure(
    habitations: gpd.GeoDataFrame,
    hazards: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:

    projected_habitations = habitations.to_crs(DEMO_PROJECTED_CRS)
    projected_hazards = hazards.to_crs(DEMO_PROJECTED_CRS)

    hazard_union = projected_hazards.geometry.union_all()

    exposures = []

    for geometry in projected_habitations.geometry:
        area = geometry.area

        if area == 0:
            exposures.append(0.0)
            continue

        intersection_area = geometry.intersection(hazard_union).area
        exposure = intersection_area / area

        exposures.append(min(max(exposure, 0.0), 1.0))

    result = habitations.copy()

    result["hazard_exposure"] = exposures

    result["population_exposed"] = (
        result["population"].astype(float)
        * result["hazard_exposure"]
    )

    return result


def calculate_nearest_distance(
    habitations: gpd.GeoDataFrame,
    facilities: gpd.GeoDataFrame,
    output_column: str,
) -> gpd.GeoDataFrame:

    habitation_projected = habitations.to_crs(DEMO_PROJECTED_CRS)
    facilities_projected = facilities.to_crs(DEMO_PROJECTED_CRS)

    distances = []

    for habitation_geometry in habitation_projected.geometry:
        distance = facilities_projected.geometry.distance(
            habitation_geometry
        ).min()

        distances.append(round(float(distance / 1000), 2))

    result = habitations.copy()
    result[output_column] = distances

    return result


def habitation_centroid(
    geometry,
    source_crs: str = WGS84,
):
    projected = gpd.GeoSeries(
        [geometry],
        crs=source_crs,
    ).to_crs(DEMO_PROJECTED_CRS)

    return projected.centroid.to_crs(WGS84).iloc[0]
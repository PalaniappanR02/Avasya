from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

import geopandas as gpd
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
OUTPUT_FILE = BASE_DIR / "data" / "habitation_evidence.json"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
THANJAVUR_BBOX = (10.2, 78.7, 11.3, 79.9)


def _load_helper(folder: str, filename: str, module_name: str):
    path = Path(__file__).resolve().parent / folder / filename

    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
    )

    if spec is None or spec.loader is None:
        raise ImportError(
            f"Unable to load pipeline helper: {path}"
        )

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return module


validation = _load_helper(
    "validation",
    "validate.py",
    "p4_validation",
)

preprocessing = _load_helper(
    "preprocessing",
    "clean.py",
    "p4_preprocessing",
)

spatial_analysis = _load_helper(
    "spatial-analysis",
    "exposure.py",
    "exposure",
)

feature_generation = _load_helper(
    "feature-generation",
    "evidence.py",
    "p4_evidence",
)


def load_gis_dataset(
    filename: str,
    label: str,
) -> gpd.GeoDataFrame:

    path = RAW_DIR / filename

    if not path.exists():
        raise FileNotFoundError(
            f"{label} dataset not found: {path}"
        )

    frame = gpd.read_file(path)

    if frame.empty:
        raise ValueError(
            f"{label} dataset is empty"
        )

    print(
        f"Loaded {len(frame)} {label.lower()} records"
    )

    return frame


def fetch_thanjavur_roads() -> Path:
    """Fetch OSM road ways for Thanjavur district via Overpass."""

    south, west, north, east = THANJAVUR_BBOX

    query = f"""
[out:json][timeout:180];
(
  way[highway]({south},{west},{north},{east});
);
out tags geom;
""".strip()

    request = Request(
        OVERPASS_URL,
        data=query.encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        },
        method="POST",
    )

    with urlopen(request, timeout=240) as response:
        payload = json.load(response)

    features = []

    for element in payload.get("elements", []):
        geometry = element.get("geometry", [])

        if len(geometry) < 2:
            continue

        tags = element.get("tags", {})

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "road_id": f"OSM_WAY_{element['id']}",
                    "road_type": tags.get("highway", "unknown"),
                    "name": tags.get("name"),
                    "data_source": "OpenStreetMap Overpass API",
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [point["lon"], point["lat"]]
                        for point in geometry
                    ],
                },
            }
        )

    if not features:
        raise ValueError(
            "Overpass returned no usable road geometries"
        )

    output_path = (
        RAW_DIR / "roads_thanjavur_overpass.geojson"
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            {
                "type": "FeatureCollection",
                "name": "thanjavur_osm_roads",
                "crs": {
                    "type": "name",
                    "properties": {
                        "name": "EPSG:4326"
                    },
                },
                "features": features,
            },
            file,
            indent=2,
        )

    print(
        f"Fetched {len(features)} roads "
        "from OpenStreetMap Overpass API"
    )

    return output_path


def load_csv_dataset(
    filename: str,
    label: str,
) -> pd.DataFrame:

    path = RAW_DIR / filename

    if not path.exists():
        raise FileNotFoundError(
            f"{label} dataset not found: {path}"
        )

    frame = pd.read_csv(path)

    if frame.empty:
        raise ValueError(
            f"{label} dataset is empty"
        )

    print(
        f"Loaded {len(frame)} {label.lower()} records"
    )

    return frame


def integrate_population(
    habitations: gpd.GeoDataFrame,
    population: pd.DataFrame,
) -> gpd.GeoDataFrame:

    required = {
        "habitation_id",
        "population",
        "vulnerability",
    }

    missing = required - set(population.columns)

    if missing:
        raise ValueError(
            f"Population dataset missing columns: "
            f"{sorted(missing)}"
        )

    population = population.copy()

    population["population"] = pd.to_numeric(
        population["population"],
        errors="coerce",
    )

    population["vulnerability"] = pd.to_numeric(
        population["vulnerability"],
        errors="coerce",
    )

    result = habitations.drop(
        columns=["population", "vulnerability"],
        errors="ignore",
    ).merge(
        population[
            [
                "habitation_id",
                "population",
                "vulnerability",
            ]
        ],
        on="habitation_id",
        how="left",
        validate="one_to_one",
    )

    if result["population"].isna().any():
        raise ValueError(
            "Population data missing for one or more habitations"
        )

    return gpd.GeoDataFrame(
        result,
        geometry="geometry",
        crs=habitations.crs,
    )


def integrate_historical_events(
    habitations: gpd.GeoDataFrame,
    historical_events: pd.DataFrame,
) -> gpd.GeoDataFrame:

    required = {
        "habitation_id",
        "event_id",
        "event_type",
        "event_year",
        "severity",
    }

    missing = required - set(historical_events.columns)

    if missing:
        raise ValueError(
            f"Historical events dataset missing columns: "
            f"{sorted(missing)}"
        )

    event_counts = (
        historical_events
        .groupby("habitation_id")
        .size()
        .rename("historical_events")
        .reset_index()
    )

    result = habitations.drop(
        columns=["historical_events"],
        errors="ignore",
    ).merge(
        event_counts,
        on="habitation_id",
        how="left",
    )

    result["historical_events"] = (
        result["historical_events"]
        .fillna(0)
        .astype(int)
    )

    return gpd.GeoDataFrame(
        result,
        geometry="geometry",
        crs=habitations.crs,
    )


def calculate_road_accessibility(
    habitations: gpd.GeoDataFrame,
    roads: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:

    projected_habitations = habitations.to_crs(
        spatial_analysis.DEMO_PROJECTED_CRS
    )

    projected_roads = roads.to_crs(
        spatial_analysis.DEMO_PROJECTED_CRS
    )

    distances = []
    accessibility = []

    for geometry in projected_habitations.geometry:

        distance = projected_roads.geometry.distance(
            geometry
        ).min()

        distance_km = float(distance / 1000)

        distances.append(
            round(distance_km, 2)
        )

        # Closer roads receive higher accessibility.
        accessibility.append(
            1.0 / (1.0 + distance_km)
        )

    result = habitations.copy()

    result["nearest_road_distance_km"] = distances
    result["road_accessibility"] = accessibility

    return result


def add_relief_centres(
    habitations: gpd.GeoDataFrame,
    relief_centers: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:

    result = spatial_analysis.calculate_nearest_distance(
        habitations,
        relief_centers,
        "nearest_relief_center_distance_km",
    )

    projected_habitations = result.to_crs(
        spatial_analysis.DEMO_PROJECTED_CRS
    )

    projected_centers = relief_centers.to_crs(
        spatial_analysis.DEMO_PROJECTED_CRS
    )

    nearest_ids = []
    nearest_capacities = []
    nearest_water_availability = []

    for geometry in projected_habitations.geometry:

        distances = projected_centers.geometry.distance(
            geometry
        )

        nearest_index = distances.idxmin()

        nearest_center = projected_centers.loc[
            nearest_index
        ]

        nearest_ids.append(
            str(nearest_center["center_id"])
        )

        nearest_capacities.append(
            int(nearest_center["capacity"])
        )

        nearest_water_availability.append(
            bool(nearest_center["water_available"])
        )

    result["nearest_relief_center_id"] = nearest_ids

    result["nearest_relief_center_capacity"] = (
        nearest_capacities
    )

    result["nearest_relief_center_water_available"] = (
        nearest_water_availability
    )

    return result


def save_evidence(
    records: list[dict],
) -> None:

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            records,
            file,
            indent=2,
        )

    print(
        f"Saved {len(records)} habitation evidence "
        f"records to {OUTPUT_FILE}"
    )


def main(
    fetch_real_roads: bool = False,
) -> None:

    print(
        "=== AVASYA P4 MULTI-SOURCE GIS PIPELINE ==="
    )

    # --------------------------------------------------
    # 1. LOAD RAW GIS DATA
    # --------------------------------------------------

    habitations = load_gis_dataset(
        "habitations.geojson",
        "Habitation",
    )

    hazards = load_gis_dataset(
        "hazards.geojson",
        "Hazard",
    )

    roads_filename = "roads.geojson"

    if fetch_real_roads:
        roads_filename = (
            fetch_thanjavur_roads().name
        )

    roads = load_gis_dataset(
        roads_filename,
        "Road",
    )

    hospitals = load_gis_dataset(
        "hospitals.geojson",
        "Hospital",
    )

    relief_centers = load_gis_dataset(
        "relief_centers.geojson",
        "Relief centre",
    )

    # --------------------------------------------------
    # 2. LOAD TABULAR DATA
    # --------------------------------------------------

    population = load_csv_dataset(
        "population.csv",
        "Population",
    )

    historical_events = load_csv_dataset(
        "historical_events.csv",
        "Historical event",
    )

    # --------------------------------------------------
    # 3. VALIDATION
    # --------------------------------------------------

    habitations = validation.validate_habitations(
        habitations
    )

    hazards = validation.validate_hazards(
        hazards
    )

    print("Validation: PASSED")

    # --------------------------------------------------
    # 4. CLEANING + CRS NORMALIZATION
    # --------------------------------------------------

    habitations, hazards = (
        preprocessing.prepare_geometries(
            habitations,
            hazards,
        )
    )

    roads = roads.to_crs("EPSG:4326")
    hospitals = hospitals.to_crs("EPSG:4326")
    relief_centers = relief_centers.to_crs("EPSG:4326")

    print(
        "CRS normalization: WGS84 / EPSG:4326"
    )

    # --------------------------------------------------
    # 5. POPULATION INTEGRATION
    # --------------------------------------------------

    habitations = integrate_population(
        habitations,
        population,
    )

    print(
        "Population integration: PASSED"
    )

    # --------------------------------------------------
    # 6. HISTORICAL EVENT INTEGRATION
    # --------------------------------------------------

    habitations = integrate_historical_events(
        habitations,
        historical_events,
    )

    print(
        "Historical event integration: PASSED"
    )

    # --------------------------------------------------
    # 7. HAZARD SPATIAL INTERSECTION
    # --------------------------------------------------

    habitations = (
        spatial_analysis.calculate_hazard_exposure(
            habitations,
            hazards,
        )
    )

    print(
        "Hazard spatial intersection: PASSED"
    )

    # --------------------------------------------------
    # 8. ROAD ACCESSIBILITY
    # --------------------------------------------------

    habitations = calculate_road_accessibility(
        habitations,
        roads,
    )

    print(
        "Road accessibility analysis: PASSED"
    )

    # --------------------------------------------------
    # 9. NEAREST HOSPITAL
    # --------------------------------------------------

    habitations = (
        spatial_analysis.calculate_nearest_distance(
            habitations,
            hospitals,
            "hospital_distance_km",
        )
    )

    print(
        "Nearest hospital analysis: PASSED"
    )

    # --------------------------------------------------
    # 10. NEAREST RELIEF CENTRE
    # --------------------------------------------------

    habitations = add_relief_centres(
        habitations,
        relief_centers,
    )

    print(
        "Relief centre analysis: PASSED"
    )

    # --------------------------------------------------
    # 11. FEATURE GENERATION
    # --------------------------------------------------

    records = feature_generation.generate_evidence(
        habitations
    )

    # --------------------------------------------------
    # 12. EXPORT
    # --------------------------------------------------

    save_evidence(records)

    print(
        "Pipeline completed successfully"
    )


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--fetch-real-roads",
        action="store_true",
        help=(
            "Fetch Thanjavur roads from "
            "OpenStreetMap Overpass API"
        ),
    )

    main(
        fetch_real_roads=(
            parser.parse_args().fetch_real_roads
        )
    )
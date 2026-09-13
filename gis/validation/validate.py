from __future__ import annotations

import geopandas as gpd
import pandas as pd


HABITATION_COLUMNS = {
    "habitation_id",
    "name",
    "population",
    "vulnerability",
    "historical_events",
    "hospital_distance_km",
    "road_accessibility",
    "district",
    "data_source",
}


def _validate_geometry(frame: gpd.GeoDataFrame, label: str) -> gpd.GeoDataFrame:
    if frame.geometry.isna().any() or frame.geometry.is_empty.any():
        raise ValueError(f"{label} contains missing or empty geometries")
    invalid = ~frame.geometry.is_valid
    if invalid.any():
        frame = frame.copy()
        frame.loc[invalid, "geometry"] = frame.loc[invalid, "geometry"].make_valid()
        if (~frame.geometry.is_valid).any():
            raise ValueError(f"{label} contains geometries that could not be repaired")
    return frame


def validate_habitations(habitations: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if habitations.empty:
        raise ValueError("Habitation dataset is empty")
    missing = HABITATION_COLUMNS - set(habitations.columns)
    if missing:
        raise ValueError(f"Habitation dataset missing required columns: {sorted(missing)}")
    if habitations.crs is None:
        raise ValueError("Habitation dataset must declare a CRS")
    habitations = _validate_geometry(habitations, "Habitation dataset")
    numeric_ranges = {
        "population": (0, None),
        "vulnerability": (0, 1),
        "historical_events": (0, None),
        "hospital_distance_km": (0, None),
        "road_accessibility": (0, 1),
    }
    for column, (minimum, maximum) in numeric_ranges.items():
        values = pd.to_numeric(habitations[column], errors="coerce")
        invalid = values.isna() | (values < minimum)
        if maximum is not None:
            invalid = invalid | (values > maximum)
        if invalid.any():
            limit = f"between {minimum} and {maximum}" if maximum is not None else f">= {minimum}"
            raise ValueError(f"Habitation field '{column}' must be numeric and {limit}")
    if habitations["habitation_id"].duplicated().any():
        raise ValueError("Habitation IDs must be unique")
    return habitations


def validate_hazards(hazards: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if hazards.empty:
        raise ValueError("Hazard dataset is empty")
    if hazards.crs is None:
        raise ValueError("Hazard dataset must declare a CRS")
    return _validate_geometry(hazards, "Hazard dataset")
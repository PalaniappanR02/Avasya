from __future__ import annotations

import geopandas as gpd


WGS84 = "EPSG:4326"


def prepare_geometries(
    habitations: gpd.GeoDataFrame, hazards: gpd.GeoDataFrame
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Normalize geographic storage to WGS84."""
    return habitations.to_crs(WGS84), hazards.to_crs(WGS84)
from __future__ import annotations

from typing import Any

from .errors import ValidationError


def point_wkt(feature: dict[str, Any], source_epsg: int) -> tuple[str, float, float]:
    geometry = feature.get("geometry")
    if not geometry or geometry.get("type") != "Point":
        raise ValidationError(
            f"Expected Point geometry for the existing point-only schema; got "
            f"{geometry.get('type') if geometry else 'missing'}."
        )
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
        raise ValidationError("Point geometry must contain longitude and latitude.")
    longitude, latitude = float(coordinates[0]), float(coordinates[1])
    if source_epsg != 4326:
        try:
            from pyproj import Transformer
        except ImportError as exc:
            raise ValidationError("CRS conversion requires pyproj.") from exc
        transformer = Transformer.from_crs(source_epsg, 4326, always_xy=True)
        longitude, latitude = transformer.transform(longitude, latitude)
    if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
        raise ValidationError("Transformed point is outside WGS84 bounds.")
    return f"SRID=4326;POINT({longitude} {latitude})", longitude, latitude

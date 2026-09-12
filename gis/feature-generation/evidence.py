from __future__ import annotations

from typing import Any

from exposure import habitation_centroid


def generate_evidence(habitations) -> list[dict[str, Any]]:
    records = []

    for _, row in habitations.iterrows():

        centroid = habitation_centroid(
            row.geometry,
            habitations.crs,
        )

        records.append(
            {
                "habitation_id": str(
                    row["habitation_id"]
                ),

                "name": str(
                    row["name"]
                ),

                "population": int(
                    row["population"]
                ),

                "population_exposed": round(
                    float(
                        row["population_exposed"]
                    ),
                    2,
                ),

                "hazard_exposure": round(
                    float(
                        row["hazard_exposure"]
                    ),
                    4,
                ),

                "vulnerability": round(
                    float(
                        row["vulnerability"]
                    ),
                    4,
                ),

                "historical_events": int(
                    row["historical_events"]
                ),

                "hospital_distance_km": round(
                    float(
                        row["hospital_distance_km"]
                    ),
                    2,
                ),

                "nearest_road_distance_km": round(
                    float(
                        row["nearest_road_distance_km"]
                    ),
                    2,
                ),

                "road_accessibility": round(
                    float(
                        row["road_accessibility"]
                    ),
                    4,
                ),

                "nearest_relief_center_id": str(
                    row["nearest_relief_center_id"]
                ),

                "nearest_relief_center_distance_km": round(
                    float(
                        row[
                            "nearest_relief_center_distance_km"
                        ]
                    ),
                    2,
                ),

                "nearest_relief_center_capacity": int(
                    row[
                        "nearest_relief_center_capacity"
                    ]
                ),

                "nearest_relief_center_water_available": bool(
                    row[
                        "nearest_relief_center_water_available"
                    ]
                ),

                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        round(float(centroid.x), 6),
                        round(float(centroid.y), 6),
                    ],
                },

                "district": str(
                    row["district"]
                ),

                "data_source": "SYNTHETIC_DEMO",

                "data_quality": "SYNTHETIC_DEMO",
            }
        )

    return records
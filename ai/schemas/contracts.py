"""
Typed contracts for everything that flows into and out of the AI module.

Why this file exists: if Priya's GIS pipeline ever silently renames a field
or sends a string where a float is expected, importing this model should
make that failure loud and immediate (a Pydantic ValidationError with a
clear message) - never a silent wrong number three steps downstream.

HabitationEvidence below matches Priya's REAL habitation_evidence.json
output (confirmed against her actual sample data, not the older/thinner
shape in the written project guide). If her format changes again, update
this file first and everything downstream will fail loudly until it's
updated to match - that is the point.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Geometry(BaseModel):
    type: Literal["Point"]
    coordinates: tuple[float, float]  # [longitude, latitude]


class HabitationEvidence(BaseModel):
    """One habitation record, exactly as produced by gis/pipeline.py (P4)."""

    habitation_id: str
    name: str
    population: int = Field(ge=0)
    population_exposed: float = Field(ge=0)
    hazard_exposure: float = Field(ge=0.0, le=1.0)
    vulnerability: float = Field(ge=0.0, le=1.0)
    historical_events: int = Field(ge=0)
    hospital_distance_km: float = Field(ge=0)
    nearest_road_distance_km: float = Field(ge=0)
    road_accessibility: float = Field(ge=0.0, le=1.0)

    # Pre-attached nearest relief center. NOTE: this is only ONE candidate -
    # the destination ranker needs a separate standalone destinations list
    # (pending from Priya) to compare multiple options. Do not treat this
    # single field as sufficient input for destination_ranker.py.
    nearest_relief_center_id: str
    nearest_relief_center_distance_km: float = Field(ge=0)
    nearest_relief_center_capacity: int = Field(ge=0)
    nearest_relief_center_water_available: bool

    geometry: Geometry
    district: str
    data_source: str
    data_quality: str

    @field_validator("population_exposed")
    @classmethod
    def exposed_not_greater_than_population(cls, v: float, info) -> float:
        population = info.data.get("population")
        if population is not None and v > population:
            raise ValueError(
                f"population_exposed ({v}) cannot exceed population ({population}) "
                "- this indicates an upstream GIS data error, not a valid input."
            )
        return v


class RiskBreakdown(BaseModel):
    """Per-factor contribution to the final risk_score. Every number here
    must sum to risk_score - this is what makes the score auditable."""

    hazard_exposure_contribution: float
    population_contribution: float
    vulnerability_contribution: float
    historical_contribution: float
    road_contribution: float


class RiskResult(BaseModel):
    habitation_id: str
    risk_score: float = Field(ge=0, le=100)
    risk_level: Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]
    risk_breakdown: RiskBreakdown
    explanation: str


class PriorityResult(BaseModel):
    habitation_id: str
    risk_score: float
    priority: Literal["IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM"]
    reasons: list[str]
    population_requiring_relocation: float


class Destination(BaseModel):
    """One candidate relocation destination, matching data/destinations.json
    exactly as it exists in the repo today. NOTE: shared/contracts/destination.schema.json
    is currently empty (unfrozen) - this Pydantic model is the de facto contract
    for the ai/ module until that file is written. If the shared contract is
    frozen later with different field names, update this model to match it,
    not the other way around."""

    destination_id: str
    name: str
    nominal_capacity: int = Field(ge=0)
    existing_occupancy: int = Field(ge=0)
    water_available: bool
    sanitation_ok: bool
    healthcare_distance_km: float = Field(ge=0)
    road_access: float = Field(ge=0.0, le=1.0)
    geometry: Geometry
    district: str
    data_source: str
    data_quality: str

    @field_validator("existing_occupancy")
    @classmethod
    def occupancy_not_greater_than_nominal(cls, v: int, info) -> int:
        nominal = info.data.get("nominal_capacity")
        if nominal is not None and v > nominal:
            raise ValueError(
                f"existing_occupancy ({v}) cannot exceed nominal_capacity ({nominal}) "
                "- this indicates a data error, not a valid input."
            )
        return v


class CapacityBreakdown(BaseModel):
    """Every deduction applied on the way from nominal to usable capacity.
    Every number here must be traceable to config/weights.py - nothing here
    should ever be a number typed directly into capacity_engine.py."""

    nominal_capacity: int
    existing_occupancy: int
    available_space: int
    water_constraint: int
    sanitation_constraint: int
    healthcare_constraint: int
    safety_reserve: int
    usable_capacity: int


class CapacityResult(BaseModel):
    destination_id: str
    population_requiring_relocation: float
    capacity_breakdown: CapacityBreakdown
    capacity_sufficient: bool
    reasons: list[str]
    explanation: str


class SuitabilityBreakdown(BaseModel):
    """Per-factor contribution to the destination's suitability_score.
    NOTE: the project guide's full suitability criteria list includes
    Electricity, Food, and destination-level Hazard Exposure. Those three
    are deliberately EXCLUDED from this breakdown because no data source
    currently provides them (data/destinations.json has no such fields) -
    we do not invent values for missing evidence. This is a documented gap
    to raise with Priya, not a silent omission."""

    capacity_adequacy_contribution: float
    water_contribution: float
    sanitation_contribution: float
    healthcare_access_contribution: float
    road_access_contribution: float
    distance_contribution: float


class SuitabilityResult(BaseModel):
    destination_id: str
    habitation_id: str
    suitability_score: float = Field(ge=0, le=100)
    distance_km: float
    capacity_sufficient: bool
    suitability_breakdown: SuitabilityBreakdown
    reasons: list[str]
    explanation: str


class RecommendationResult(BaseModel):
    """The final officer-facing output. Matches the guide's explainable
    recommendation format exactly: a recommended destination with reasons
    FOR it, and the next-best alternative with reasons it was NOT selected.
    Includes an audit trail timestamp per the guide's
    Recommendation -> Risk -> Factors -> Evidence -> Calculation -> Timestamp
    chain."""

    habitation_id: str
    recommended_destination_id: str | None
    recommended_reasons: list[str]
    next_best_destination_id: str | None
    next_best_rejected_reasons: list[str]
    destinations_ranked: list[SuitabilityResult]
    excluded_destination_ids: list[str]
    generated_at: str
    explanation: str
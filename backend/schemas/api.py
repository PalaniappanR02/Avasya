from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HabitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    village_or_ward: str | None = None
    district: str | None = None
    state: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    population: int | None = None
    households: int | None = None
    data_origin: str


class RiskResponse(BaseModel):
    id: int
    habitation_id: int
    overall_risk_score: float
    risk_level: str
    confidence_score: float | None = None
    model_version: str | None = None
    input_snapshot: dict[str, Any] | None = None
    normalized_values: dict[str, Any] | None = None
    weights: dict[str, Any] | None = None
    contributions: dict[str, Any] | None = None
    reasons: dict[str, Any] | None = None
    warnings: dict[str, Any] | None = None
    freshness: dict[str, Any] | None = None
    data_quality: dict[str, Any] | None = None
    calculation_details: dict[str, Any] | None = None
    data_origin: str
    generated_at: datetime


class CapacityResponse(BaseModel):
    id: int
    destination_id: int
    habitation_id: int
    nominal_capacity: int
    existing_occupancy: int
    water_constraint: float | None = None
    sanitation_constraint: float | None = None
    safety_reserve: float | None = None
    usable_capacity: int
    required_capacity: int
    capacity_gap: int
    eligibility: bool
    status: str | None = None
    assessment_details: dict[str, Any] | None = None
    data_origin: str


class DestinationResponse(BaseModel):
    id: int
    name: str
    destination_type: str | None = None
    district: str | None = None
    state: str | None = None
    country: str | None = None
    capacity: CapacityResponse | None = None
    risk_score: float | None = None
    data_origin: str


class RelocationResponse(BaseModel):
    id: int
    habitation_id: int
    destination_id: int | None = None
    priority_score: float
    priority_label: str | None = None
    rationale: dict[str, Any] | None = None
    destination: DestinationResponse | None = None
    data_origin: str


class RecommendationResponse(BaseModel):
    id: int
    summary: str
    recommendation_type: str | None = None
    details: dict[str, Any] | None = None
    confidence_score: float | None = None
    destination_id: int | None = None
    data_origin: str
    created_at: datetime


class ApprovalRequest(BaseModel):
    action: str = Field(pattern="^(APPROVE|OVERRIDE)$")
    final_destination_id: int | None = None
    override_note: str | None = Field(default=None, min_length=1, max_length=4000)


class ApprovalResponse(BaseModel):
    id: int
    recommendation_id: int
    officer_user_id: int
    action: str
    original_recommendation: dict[str, Any] | None = None
    final_destination_id: int | None = None
    override_note: str | None = None
    data_origin: str
    created_at: datetime

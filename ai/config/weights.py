"""
Every scoring weight and threshold used by the AI module lives here, and
ONLY here. If you find yourself typing a raw number like 0.35 or 70 inside
risk_engine.py or priority_engine.py, stop - it belongs in this file instead.

This is what you hand a judge who asks "why did H001 score 87?" - point at
this file and walk them through it line by line.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# RISK ENGINE WEIGHTS
# ---------------------------------------------------------------------------
# Five factors, each normalized to a 0-100 scale, combined by these weights.
# Weights must sum to 1.0 - this is asserted at import time below so a typo
# can never silently produce a risk score that isn't out of 100.
#
# Reasoning for each weight (say this out loud to a judge, don't just show it):
#   hazard_exposure (35%)     - the single strongest driver of physical danger
#   population (20%)          - more people affected = higher operational urgency
#   vulnerability (20%)       - elderly/disabled/low-income residents are harder
#                                to evacuate safely and recover slower
#   historical_events (12%)   - proven repeat disaster history at this location
#   road_accessibility (13%)  - poor roads directly slow down evacuation itself
RISK_WEIGHTS: dict[str, float] = {
    "hazard_exposure": 0.35,
    "population": 0.20,
    "vulnerability": 0.20,
    "historical_events": 0.12,
    "road_accessibility": 0.13,
}

assert abs(sum(RISK_WEIGHTS.values()) - 1.0) < 1e-9, (
    "RISK_WEIGHTS must sum to 1.0 - fix config/weights.py before running anything."
)

# ---------------------------------------------------------------------------
# NORMALIZATION RANGES
# ---------------------------------------------------------------------------
# population and historical_events arrive as raw counts, not 0-1 ratios, so
# they need a documented min-max range before they can be weighted alongside
# the factors that are already 0-1. These caps are team-chosen assumptions
# for the demo district (Thanjavur, synthetic data) - NOT authoritative
# national figures. Document this honestly if a judge asks.
POPULATION_MIN = 0
POPULATION_MAX = 10_000  # habitations larger than this still score 100 (capped)

HISTORICAL_EVENTS_MIN = 0
HISTORICAL_EVENTS_MAX = 10  # 10+ past events still scores 100 (capped)

# ---------------------------------------------------------------------------
# PRIORITY ENGINE THRESHOLDS
# ---------------------------------------------------------------------------
# Risk score (0-100) -> relocation priority bucket.
# These are TEAM-DEFINED thresholds for the demo, not an official government
# standard - say this plainly if asked. They should be revisited once real
# historical outcome data is available to validate against.
PRIORITY_THRESHOLDS = {
    "IMMEDIATE": 70,    # risk_score >= 70
    "SHORT_TERM": 40,   # 40 <= risk_score < 70
    # anything below SHORT_TERM threshold falls into MEDIUM_TERM
}

# Escalation rule: even a moderate risk score can still demand IMMEDIATE
# action if a very large number of people are physically exposed to the
# hazard right now. This mirrors the guide's own formula:
#   Risk + Vulnerability + Exposure + Urgency -> Priority
# rather than collapsing everything into a single risk number and ignoring
# raw exposed-population scale.
LARGE_EXPOSED_POPULATION_ESCALATION_THRESHOLD = 500  # people

# ---------------------------------------------------------------------------
# CAPACITY ENGINE CONSTANTS
# ---------------------------------------------------------------------------
# Nominal capacity -> usable emergency capacity, per the guide's waterfall:
#   Nominal -> minus existing occupancy -> minus water/sanitation/healthcare
#   constraints -> minus safety reserve -> Usable Emergency Capacity.
#
# Our real destinations.json stores water/sanitation as booleans and
# healthcare as a distance in km, not pre-computed deduction amounts, so we
# need a documented, defensible rule to turn those into numbers. These
# ratios are TEAM-CHOSEN ASSUMPTIONS for the demo, not sourced from any
# official standard - say this plainly if a judge asks "where did 15% come
# from".
#
# Reasoning:
#   - Even a destination WITH water/sanitation available still gets a small
#     buffer deducted, because "available" doesn't mean "unlimited" - real
#     shelters have throughput limits even when the service exists.
#   - A destination WITHOUT water/sanitation gets a much larger deduction,
#     reflecting a severe (not total) reduction in safely usable capacity -
#     we do not zero it out entirely, because officers may still stage
#     limited/temporary use, but it should rank far below a fully-serviced
#     destination.
WATER_AVAILABLE_BUFFER_RATIO = 0.03      # -3% of nominal even when water IS available
WATER_UNAVAILABLE_PENALTY_RATIO = 0.15   # -15% of nominal when water is NOT available

SANITATION_OK_BUFFER_RATIO = 0.03        # -3% of nominal even when sanitation IS ok
SANITATION_UNAVAILABLE_PENALTY_RATIO = 0.12  # -12% of nominal when sanitation is NOT ok

# Healthcare is a distance, not a boolean - only penalize capacity when the
# nearest healthcare facility is far enough to matter operationally.
HEALTHCARE_DISTANCE_THRESHOLD_KM = 5.0
HEALTHCARE_FAR_PENALTY_RATIO = 0.05      # -5% of nominal if healthcare is farther than threshold

# Fixed emergency safety buffer, applied to every destination regardless of
# its other attributes - space intentionally held back for emergencies
# (medical incidents, overflow, staff operations) rather than filled to the
# last usable seat.
SAFETY_RESERVE_RATIO = 0.10              # -10% of nominal, always

# ---------------------------------------------------------------------------
# SUITABILITY / DESTINATION SCORING WEIGHTS
# ---------------------------------------------------------------------------
# The project guide lists suitability criteria as: Safety, Usable Capacity,
# Water, Sanitation, Healthcare, Electricity, Food, Road Access, Distance,
# Hazard Exposure.
#
# IMPORTANT / HONEST LIMITATION: Electricity, Food, and destination-level
# Hazard Exposure are NOT scored here, because data/destinations.json does
# not currently provide those fields. We do not invent values for missing
# evidence - this is a documented data gap, not a silent one. If Priya adds
# those fields later, extend SUITABILITY_WEIGHTS and destination_scorer.py
# together, and re-normalize all weights so they still sum to 1.0.
#
# "Safety" itself isn't a standalone field in our data either - we treat
# capacity adequacy + water + sanitation + healthcare access as the
# practical proxy for a destination being safe to actually use, since a
# technically "safe" location that can't provide water or capacity isn't
# safe to relocate people to in practice.
SUITABILITY_WEIGHTS: dict[str, float] = {
    "capacity_adequacy": 0.30,   # can it actually hold the affected population - the guide's core "trap"
    "water": 0.15,
    "sanitation": 0.15,
    "healthcare_access": 0.15,
    "road_access": 0.15,
    "distance": 0.10,
}

assert abs(sum(SUITABILITY_WEIGHTS.values()) - 1.0) < 1e-9, (
    "SUITABILITY_WEIGHTS must sum to 1.0 - fix config/weights.py before running anything."
)

# Distance/healthcare normalization ranges. Beyond these distances, the
# factor score floors at 0 rather than going negative. Team-chosen for a
# single-district demo scale, not an official standard - say so if asked.
HEALTHCARE_ACCESS_MAX_KM = 15.0   # healthcare_access score reaches 0 at this distance
DESTINATION_DISTANCE_MAX_KM = 30.0  # distance score reaches 0 at this distance
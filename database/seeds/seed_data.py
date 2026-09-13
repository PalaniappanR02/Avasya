from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SeedBatch:
    name: str
    rows: list[dict[str, Any]] = field(default_factory=list)


def synthetic_demo_row(**kwargs: Any) -> dict[str, Any]:
    payload = dict(kwargs)
    payload["data_origin"] = "SYNTHETIC_DEMO"
    return payload


SEED_BATCHES: tuple[SeedBatch, ...] = (
    SeedBatch("users", []),
    SeedBatch("habitations", []),
    SeedBatch("hazards", []),
    SeedBatch("evidence", []),
    SeedBatch("risk_assessments", []),
    SeedBatch("relocation_priorities", []),
    SeedBatch("destinations", []),
    SeedBatch("capacity_assessments", []),
    SeedBatch("recommendations", []),
)

SEED_ORDER = [batch.name for batch in SEED_BATCHES]

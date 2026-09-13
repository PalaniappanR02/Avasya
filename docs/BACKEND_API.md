# AVASYA Backend API Handoff

## Runtime

Start the API from the repository root with the configured environment:

```powershell
$env:DATABASE_URL="postgresql+psycopg://<user>:<password>@<host>:<port>/<database>"
$env:PORT="8000"
$env:CORS_ORIGINS="http://localhost:3000"
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port $env:PORT
```

The application entrypoint is `backend.main:app`.

- Local base URL: `http://localhost:8000`
- API base path: `http://localhost:8000/api/v1`
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

`DATABASE_URL` is required. The API does not run ingestion or reset the database at startup.

## Endpoints

### Health

- `GET /health` returns `{"status":"ok"}`.
- `GET /health/db` executes `SELECT 1` and returns `{"status":"ok","database":"ok"}`.

Database failures return HTTP `503`.

### Habitations

`GET /api/v1/habitations?offset=0&limit=100`

Returns a JSON array with:

```text
id, name, village_or_ward, district, state, country,
latitude, longitude, population, households, data_origin
```

`limit` is between 1 and 500. Invalid query parameters return `422`.

`GET /api/v1/habitations/{habitation_id}`

Returns one habitation. An unknown ID returns `404`.

### Risk

`GET /api/v1/habitations/{habitation_id}/risk`

Returns the latest persisted risk assessment:

```text
id, habitation_id, overall_risk_score, risk_level,
confidence_score, model_version, input_snapshot,
normalized_values, weights, contributions, reasons,
warnings, freshness, data_quality, calculation_details,
data_origin, generated_at
```

If the habitation exists but no assessment is persisted, the endpoint returns `503`.

The locked weights are:

```text
hazard_exposure       35%
population            20%
vulnerability         20%
historical_events     12%
road_accessibility    13%
```

Risk levels are:

```text
0–49   LOW
50–74  MEDIUM
75–100 HIGH
```

Missing or non-habitation-level evidence is not fabricated. The response records warnings, missing components, data quality, and linked evidence IDs where available.

### Relocation

`GET /api/v1/habitations/{habitation_id}/relocation`

Returns:

```text
id, habitation_id, destination_id, priority_score,
priority_label, rationale, destination, data_origin
```

The nested destination includes capacity details when a destination is selected. Insufficient destinations are removed from the returned eligible destination.

If no relocation assessment exists, the endpoint returns `503`.

### Eligible destinations

`GET /api/v1/habitations/{habitation_id}/destinations`

Returns only destinations whose persisted capacity assessment satisfies:

```text
usable_capacity >= required_capacity
```

Each destination includes:

```text
id, name, destination_type, district, state, country,
capacity, risk_score, data_origin
```

### Capacity

`GET /api/v1/destinations/{destination_id}/capacity`

Returns:

```text
id, destination_id, habitation_id,
nominal_capacity, existing_occupancy,
water_constraint, sanitation_constraint, safety_reserve,
usable_capacity, required_capacity, capacity_gap,
eligibility, status, assessment_details, data_origin
```

Eligibility is calculated as `usable_capacity >= required_capacity`. A missing capacity assessment returns `503`; an unknown destination returns `404`.

The signed `capacity_gap` is preserved. Demo capacity details also retain the raw negative calculation in `assessment_details.calculated_usable_capacity` when schema constraints require `usable_capacity` to be stored at zero.

### Recommendation

`GET /api/v1/habitations/{habitation_id}/recommendation`

Returns:

```text
id, summary, recommendation_type, details,
confidence_score, destination_id, data_origin, created_at
```

If no recommendation is persisted, the endpoint returns `503`.

When no destination passes the capacity gate, the persisted summary is `NO_ELIGIBLE_DESTINATION`.

### Approval and override

`POST /api/v1/recommendations/{recommendation_id}/approval`

Request body:

```json
{
  "action": "APPROVE",
  "final_destination_id": 4,
  "override_note": null
}
```

For an override:

```json
{
  "action": "OVERRIDE",
  "final_destination_id": 4,
  "override_note": "Officer confirms the final destination."
}
```

Authentication is the current local/demo mechanism:

```text
X-Officer-Email: demo.officer@avasya.local
```

`Authorization: Bearer <persisted-user-email>` is also accepted for local compatibility. The email is resolved to a persisted user; the client cannot provide an officer ID. The user must have role `officer` or `admin`.

Missing or invalid authentication returns `401`. Override requests without a note return `422`. Unknown recommendations or destinations return `404`. Missing capacity evidence returns `503`; insufficient capacity returns `422`.

The response contains:

```text
id, recommendation_id, officer_user_id, action,
original_recommendation, final_destination_id,
override_note, data_origin, created_at
```

The original recommendation is copied into `original_recommendation` and is never overwritten.

## Current local demo records

These IDs are from the verified local database and are not portable identifiers:

| Record | Current ID | Origin |
|---|---:|---|
| Real habitation used by seed | 1 | REAL |
| D02 Synthetic Insufficient Shelter | 3 | SYNTHETIC_DEMO |
| D04 Synthetic Eligible Shelter | 4 | SYNTHETIC_DEMO |
| Current recommendation | 1 | MIXED |
| Demo officer | `demo.officer@avasya.local` | SYNTHETIC_DEMO |

The demo seed is non-destructive and idempotent:

```powershell
$env:DATABASE_URL="postgresql+psycopg://<user>:<password>@<host>:<port>/<database>"
.venv\Scripts\python.exe -m backend.seed_demo
```

Synthetic destinations and the demo officer are explicitly marked `SYNTHETIC_DEMO`. They must not be presented as real shelters or real officers.

## Database and migrations

Apply existing migrations with:

```powershell
.venv\Scripts\python.exe -m alembic upgrade head
```

The verified current head is `20260913_000003`.

## Validation commands

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m compileall backend tests database/migrations
.venv\Scripts\python.exe -m alembic heads
```

## Known data limitation

The current real habitation data is available and persisted, but not every real evidence source is linked at habitation granularity. District/state vulnerability data is not treated as habitation-level, and unavailable road-distance or direct hazard evidence is reported through warnings and data-quality fields rather than fabricated values. The deterministic H001-style test fixture still produces `87 / HIGH`.

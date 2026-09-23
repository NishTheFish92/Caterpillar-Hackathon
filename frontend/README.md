# CAT Smart Operator Assistant — Backend Template

An end-to-end template for a multi-functional operator interface for CAT
machine operators: daily task dashboard, real-time safety monitoring,
a training hub, unusual-machine-usage detection, and task time estimation.

This is a **backend + data pipeline template**, meant to be a scalable
starting point — swap the synthetic data for real telemetry and the CSV
storage for a real database, and the API layer doesn't need to change.

## Architecture

```
data_generator/generate_data.py     Raw data synthesis (4 CSVs)
        │
        ▼
feature_engineering/build_features.py   Batch feature engineering
        │                                (joins raw data → feature tables)
        ▼
data/*.csv                          Raw + engineered tables
        │
        ▼
backend/                            FastAPI application
  ├── data_access/repository.py       ← the ONE place that knows where
  │                                     data physically lives (swap this
  │                                     to move from CSV → Postgres, etc.)
  ├── dependencies.py                 ← DI wiring; one-line backend swap
  ├── config.py                       ← thresholds & tunables, not hardcoded
  ├── schemas.py                      ← Pydantic request/response contracts
  ├── routers/
  │     dashboard.py    → Daily Task Dashboard
  │     safety.py       → Seatbelt / Proximity / Incident Logging
  │     training.py     → Training Hub (videos, simulation, instructor booking)
  │     behavior.py     → Unusual Machine Usage Detection
  │     estimation.py   → Task Time Estimation
  └── main.py            FastAPI app, wires routers together
tests/test_api.py                   Smoke tests for every endpoint
```

### Why this structure scales

1. **Batch feature engineering is separate from the API.** The API never
   does a heavy join or groupby at request time — it only reads small,
   pre-aggregated tables. In production, `build_features.py` becomes a
   scheduled job (Airflow/cron/Lambda) that reruns as new telemetry lands.
2. **The repository pattern isolates storage.** `DataRepositoryBase` is an
   abstract interface; `CsvDataRepository` is one implementation. Write a
   `PostgresDataRepository` / `TimescaleDataRepository` implementing the
   same interface, swap one line in `dependencies.py`, and every router
   keeps working unchanged.
3. **Thresholds live in `config.py`, not scattered through route code** —
   so tuning "what counts as excessive idling" doesn't require touching
   business logic, and could later be moved into a rules table per
   site/machine type.
4. **Rule-based anomaly detection is isolated in one function**
   (`behavior.py::_evaluate_anomalies`) — the natural place to later drop
   in a real model (e.g. isolation forest / seasonal baseline) without
   touching the API contract.
5. **Real-time vs. historical data are already split**: `telemetry.csv`
   (raw, high-frequency) feeds live safety checks; `task_features.csv` /
   `operator_daily_features.csv` (pre-aggregated) feed dashboards and
   anomaly detection. This mirrors a real hot-path/cold-path split (e.g.
   a live telemetry stream + a nightly warehouse table).

## Data model (kept intentionally simple)

Only 4 raw CSVs, as specified:

| File              | Grain                        | Key fields |
|-------------------|-------------------------------|------------|
| `operators.csv`   | one row per operator          | operator_id, license_type, experience_years, shift |
| `machines.csv`    | one row per machine            | machine_id, machine_type, model, fuel_type |
| `tasks.csv`       | one row per scheduled task      | task_id, operator_id, machine_id, task_type, environmental_condition, terrain_type, scheduled_start/end |
| `telemetry.csv`   | one row per machine per minute per task | seatbelt_status (yes/no), proximity_alert (yes/no), engine_status, speed_kmph, engine_temp_c, ... |

`feature_engineering/build_features.py` produces 3 derived tables:

- **`task_features.csv`** — per-task rollup: actual vs. scheduled duration,
  idle %, seatbelt compliance %, proximity/unsafe *episode* counts (not
  raw minute counts — see note below), overrun.
- **`operator_daily_features.csv`** — per-operator-per-day rollup, the
  input to anomaly detection.
- **`duration_benchmarks.csv`** — historical average/median duration
  grouped by task_type × environmental_condition × terrain_type, the
  input to task time estimation.

**Note on "episode" counting:** proximity alerts and unsafe-behavior flags
are counted as discrete *events* (state transitions), not summed minute-
by-minute — a proximity alert lasting 3 consecutive minutes is 1 event,
not 3. This is what makes the counts meaningful rather than just a proxy
for how long telemetry ran. (Watch out if you extend this: `pandas`
silently upcasts a boolean column to `object` dtype on `.shift()`, which
breaks `~` negation — cast back to `bool` after `.fillna()`.)

Seeded behavior for demoing anomaly detection: operators `OP-002`,
`OP-007`, `OP-011` are generated with elevated idling/unsafe-speed
patterns; `OP-004` and `OP-009` are generated as frequent seatbelt
offenders. Query `/behavior/OP-002/anomalies` vs `/behavior/OP-001/anomalies`
to see the contrast.

## Running it

```bash
cd cat_operator_assistant
pip install -r requirements.txt

# 1. Generate raw data
python data_generator/generate_data.py --out-dir data

# 2. Build engineered features
python feature_engineering/build_features.py --data-dir data

# 3. Run the API (from the project root)
uvicorn backend.main:app --reload --port 8000
```

Then open **http://127.0.0.1:8000/docs** for interactive Swagger UI.

Run the smoke tests any time (no live server needed — uses FastAPI's
`TestClient` in-process):

```bash
python tests/test_api.py
```

## Frontend

A minimal single-page HTML+JS dashboard (`frontend/index.html`) covers
every endpoint above — no build step, no npm, just a static file that
talks to the FastAPI backend over `fetch`. Swagger's `/docs` is fine for
poking at individual endpoints, but this gives you tabs for each feature
area (Dashboard / Safety / Training / Behavior / Task Time) with real
forms and rendered results instead of raw JSON.

To use it:
1. Start the backend (`uvicorn backend.main:app --reload --port 8000`).
2. Open `frontend/index.html` directly in a browser (double-click it).
3. Confirm the "API base" field in the header matches where your backend
   is running (defaults to `http://127.0.0.1:8000`), click Connect.

It's plain HTML/CSS/vanilla JS on purpose — functional rather than
styled, so it's easy to read and easy to swap for React or another
framework later without fighting generated design decisions.

## Endpoints

| Feature | Method & Path |
|---|---|
| Daily Task Dashboard | `GET /dashboard/{operator_id}/tasks?for_date=YYYY-MM-DD` |
| Seatbelt compliance (real-time) | `GET /safety/seatbelt/{machine_id}` |
| Proximity hazard (single machine) | `GET /safety/proximity/{machine_id}` |
| Proximity hazard (site-wide feed) | `GET /safety/proximity` |
| Log a safety incident | `POST /safety/incidents` |
| List incidents | `GET /safety/incidents?operator_id=&machine_id=` |
| Training module catalog | `GET /training/modules?format=` |
| Book an instructor session | `POST /training/book` |
| View bookings | `GET /training/bookings/{operator_id}` |
| Unusual behavior / anomaly report | `GET /behavior/{operator_id}/anomalies?days=7` |
| Task time estimation | `POST /estimation/task-time` |

## Extending this template

- **Swap storage:** implement `DataRepositoryBase` against Postgres/
  TimescaleDB, point `dependencies.py` at it. Nothing else changes.
- **Real-time ingestion:** replace the CSV telemetry read with a
  Kafka/MQTT consumer writing into the same repository interface.
- **Smarter estimation:** replace the benchmark lookup in
  `estimation.py` with a trained regression model — same request/response
  contract, so front-ends don't need to change.
- **Smarter anomaly detection:** replace `_evaluate_anomalies`'s
  threshold rules with a statistical/ML model trained on
  `operator_daily_features.csv`.
- **Scale the data generator:** bump `NUM_OPERATORS`, `NUM_MACHINES`,
  `NUM_DAYS` in `generate_data.py` — everything downstream (feature
  pipeline, API) works unchanged at any size.

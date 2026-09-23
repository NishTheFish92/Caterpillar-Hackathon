# CAT Smart Operator Assistant — Project Guide

Hackathon project for Caterpillar: "Smart Operator Assistant for CAT
machinery." Two-person team (both working with Claude Code). Stack is
fixed: **FastAPI backend, React frontend**. No hard deadline stated, but
build for demo-readiness over gold-plating.

## Mandatory scope — do not cut any of these

Per the original problem statement AND an explicit instruction from a
teammate ("ALL 5 functional requirements are a must, nothing can be
deleted"), the app must cover:

1. **Daily Task Dashboard** — scheduled tasks for the day. *(Design +
   build: Claude. Teammate left this fully open — no spec constraints.)*
2. **Safety Features** — seatbelt compliance, proximity hazards, incident
   logging. *(Spec owner: teammate; build: Claude, following their spec.)*
   Must be: strict rule-based **+** an AI/ML model that predicts
   *upcoming* hazards, where the ML output is then re-checked by a
   rule-based pipeline before it's allowed to be marked as a hazard (ML
   never fires an alert directly).
3. **Training Hub** — creative learning formats. *(Spec owner: teammate;
   build: Claude.)* Deliberately kept simple: a catalog of links/resources
   tiered by operator experience/skill level. Not meant to be built deep.
4. **Unusual Behavior Detection** — excessive idling, unsafe operation
   patterns. *(Design + build: Claude. Teammate left this fully open — no
   spec constraints.)*
5. **Task Time Estimation** — predict duration from past data + conditions.
   *(Spec owner: teammate; build: Claude, following their spec.)* Must use
   ML trained on historical data, not just a lookup table.

Note: "owner" above means who set the functional spec, not who writes the
code — Claude builds all five either way. For #1 and #4 there is no
external spec to satisfy, so design choices are made directly with the
user rather than inferred from teammate instructions.

Cross-cutting, owned by teammate: **dataset generation + feature
engineering** should be made "much more comprehensive" and tied directly
to whatever the above features need (not just the illustrative columns
from the original problem statement).

## Repo layout — read this first

`Prototype/` is a **reference-only** scaffold built by a teammate. Do not
edit it — it stays untouched as the architectural precedent to build from.
The real, live project lives at the repo root, mirroring the same
structure and conventions:

```
backend/               ← live FastAPI app (copied from Prototype/backend, then extended)
data_generator/         ← live data generator (copied from Prototype/data_generator, then extended)
feature_engineering/    ← live feature pipeline (copied from Prototype/feature_engineering, then extended)
ml/                      ← NEW: model training scripts + ml/models/*.joblib (gitignored, regenerate via scripts)
data/                    ← generated CSVs (tracked in git, same precedent as Prototype/data)
frontend/                ← NEW: React app (replacing Prototype's throwaway static HTML)
tests/                   ← live smoke tests (copied from Prototype/tests, then extended)
requirements.txt
.venv/                   ← Python virtualenv, managed with `uv`, gitignored, lives at repo root
```

Tooling state (`.venv/`, `ml/models/`, `node_modules/` once the frontend
exists) never lives inside `Prototype/` or gets committed — see
`.gitignore` at repo root.

## Original state of the reference prototype (`Prototype/`, for context only)

Already built and working end-to-end when handed off (see
`Prototype/README.md` for full detail) — described here for context on
what the live `backend/`/`data_generator/`/`feature_engineering/` above
were copied from and are diverging from:

```
data_generator/generate_data.py   → 4 raw CSVs (operators, machines, tasks, telemetry)
feature_engineering/build_features.py → 3 derived CSVs (task_features,
                                          operator_daily_features, duration_benchmarks)
backend/
  data_access/repository.py   ← ONLY place that touches CSV/pandas directly
                                 (DataRepositoryBase interface + CsvDataRepository impl)
  dependencies.py             ← DI wiring, one-line backend swap point
  config.py                   ← thresholds/tunables (idle %, unsafe rate, etc.)
  schemas.py                  ← Pydantic contracts — the API surface
  routers/{dashboard,safety,training,behavior,estimation}.py  ← one per outcome
tests/test_api.py             ← in-process smoke tests (TestClient, no server needed)
frontend/frontend_index.html  ← static HTML/JS demo UI, explicitly a throwaway
                                 stand-in until React exists
```

Everything currently "smart" is rule-based/lookup-based, by design, as a
seam to swap in ML without touching the API contract:
- Safety: reads latest telemetry ping, checks seatbelt/proximity directly
  — no forward-looking prediction yet.
- Task Time Estimation: historical benchmark average lookup with
  environment/terrain multiplier fallback — no trained model yet.
- Unusual Behavior: threshold rules in `behavior.py::_evaluate_anomalies`
  over daily rollups (idle %, unsafe events/day, proximity/day, seatbelt
  compliance). Data generator seeds `OP-002/007/011` as idling/unsafe-speed
  outliers and `OP-004/009` as seatbelt offenders, specifically so this
  detection has something real to find.
- Training Hub: static in-memory list of modules — already matches the
  "just links, tiered by level" target design.
- Dashboard: straight CSV lookup by operator + date.

## Current implementation state (all 5 outcomes built)

- **Dashboard** — unchanged from prototype design (CSV lookup by operator + date).
- **Safety** — seatbelt/proximity endpoints unchanged (reactive, rule-based).
  NEW: `GET /safety/hazard-prediction/{machine_id}` — a RandomForestClassifier
  (`ml/train_safety_model.py`) predicts probability of a proximity-alert
  episode in the next 5 minutes from a rolling window of telemetry
  (closing distance, proximity rate, speed, seatbelt/idle rates) + machine
  health + site conditions. Per spec, this NEVER surfaces as a hazard on
  its own — `routers/safety.py::_apply_hazard_gate` requires the ML
  probability to clear `config.HAZARD_PROBABILITY_THRESHOLD` **and** at
  least one independent rule condition (min distance, proximity rate,
  speed) to also hold. Holdout ROC-AUC ~0.84, precision ~0.23 at the 0.5
  threshold — low precision at default threshold is expected/intentional
  for a rare-event classifier and is exactly why the rule gate exists.
- **Training Hub** — rebuilt as a wiki: `GET /training/articles` (filter by
  `skill_level`/`category`/`format`), `GET /training/articles/{id}`, 12
  dummy articles across Safety/Operating Technique/Maintenance/Operations,
  tiered Beginner→Advanced. Booking flow (`POST /training/book`) kept for
  the one instructor-led article (ART-010).
- **Unusual Behavior Detection** — unchanged, stays rule-based per decision 3.
- **Task Time Estimation** — `POST /estimation/task-time` now runs a
  RandomForestRegressor (`ml/train_estimation_model.py`) on task_type,
  terrain, environment, operator experience/certification, machine
  type/age/health. Holdout MAE ~15.8 min, R²~0.79. `operator_id`/
  `machine_id` in the request are optional — if given, real
  experience/machine data feeds the model; otherwise dataset medians are
  used (see `ml/models/task_time_model_meta.json::defaults`). The old
  historical-benchmark lookup is now returned alongside the ML prediction
  as a reference/sanity-check field, not the prediction itself.
- **Frontend** — React (Vite, JS not TS) at `frontend/`, one page per
  outcome, CAT-branded design system (see below). Talks to the backend via
  `frontend/src/api.js` (`VITE_API_BASE_URL`, defaults to
  `http://127.0.0.1:8000`).

Data generator additions that made the ML models learnable (not just
plausible-looking): task duration now has a REAL causal structure
(`TASK_TYPE_BASE_MIN` × terrain/environment multipliers × operator
experience × machine health, in `data_generator/generate_data.py`) instead
of pure random noise — the first version of the regressor trained on
noise-only durations and got R²≈-0.02 (worse than predicting the mean),
which is why this exists. Similarly `distance_to_hazard_m` in telemetry
ramps down for 3-6 minutes *before* every proximity-alert episode (a real
leading indicator), which is what the hazard classifier actually learns
from.

## Frontend design system (`frontend/src/index.css`)

CAT-brand yellow (`--cat-yellow: #ffcd11`) + black, deliberately boxy
(`--radius: 0` everywhere, thick borders), diagonal hazard-stripe bands
(`.hazard-stripe` / `.hazard-stripe-thick`) used as section dividers.
Mobile-responsive breakpoints at 720px/480px collapse the nav. Reusable
pieces: `Badge` (severity→color mapping), `StatCard`, `.panel`,
`.article-card`, `.alert-block`. Keep new UI within these classes/tokens
rather than one-off inline styles, so the brand stays consistent as pages
are added.

## Working conventions established by the prototype — keep following these

- **Repository pattern is load-bearing.** Routers must never import
  pandas/CSV directly — always go through `DataRepositoryBase` /
  `get_repository()`. This is what makes a later storage swap (CSV →
  Postgres/Timescale) a one-file change.
- **Thresholds/tunables live in `config.py`**, never hardcoded inline in
  route logic.
- **Rule-based logic is isolated in single evaluator functions**
  (`behavior.py::_evaluate_anomalies`, the risk-level calc in
  `safety.py`, the benchmark-vs-fallback branch in `estimation.py`) —
  this is deliberately the exact seam where a model gets dropped in later
  without changing the router or the response schema.
- **Batch feature engineering is separate from the API.** `build_features.py`
  does the heavy joins/groupbys; the API only ever reads small
  pre-aggregated tables at request time.
- **Pydantic schemas in `schemas.py` are the real API contract.** Frontend
  work should be built against these shapes, not ad hoc dict inspection.
- **"Episode" counting, not per-minute counting**, for proximity/unsafe
  events (state transitions, not raw minute sums) — see the dtype-upcast
  gotcha noted in `build_features.py` around `.shift()` on boolean columns
  if this logic is touched.

## Decisions log

1. **Storage backend: keep CSV.** `CsvDataRepository` stays for the
   demo — already working end-to-end, and the repository interface makes
   a later DB swap a one-file change if it's ever actually needed. Do not
   introduce SQLAlchemy/SQLite unless a concrete new requirement forces
   it (e.g. real concurrent writes, live ingestion).
2. **Ownership: confirmed.** Claude designs + builds Dashboard and
   Unusual Behavior Detection with no external spec constraints (decide
   with the user, not the teammate). Safety, Task Time Estimation, and
   Training Hub follow the teammate's spec above. Claude also builds the
   React frontend and the ML models (Safety hazard prediction + Task Time
   regression) — "owner" in the spec section means who set requirements,
   not who writes code.
3. **Unusual Behavior Detection: stays rule-based.** No ML layer for now
   — keep `_evaluate_anomalies`'s threshold approach, refine it if needed,
   but don't add a model. Matches the "strict rule based" precedent set
   for Safety's gating layer.
4. **React frontend: scaffold now.** Build it against the current,
   already-stable Pydantic response schemas rather than waiting on the
   Safety/Task-Time ML work — ML changes happen inside route handlers and
   shouldn't change response shape.

## Still open / worth revisiting

- No DB migration (decision 1 stands — CSV is fine for the demo).
- Safety hazard-gate thresholds (`config.HAZARD_PROBABILITY_THRESHOLD`
  etc.) were picked reasonably, not tuned against a target precision/
  recall — revisit if the demo shows it firing too often/rarely.
- No auth/multi-tenancy anywhere (not asked for; hackathon scope).
- Frontend has no automated tests (build + lint verified clean; UI was not
  visually verified in a real browser in this environment — check it live
  before a demo).

## Python tooling: `uv`, properly

This is a real `uv` project, not just `uv` used as a faster pip. `pyproject.toml`
(deps + `[tool.uv] package = false` since this is loose top-level dirs, not
an installable package) and `uv.lock` (tracked in git, reproducible
resolution) are the source of truth. `requirements.txt` is kept as a
secondary plain-pip manifest at the user's request — keep it in sync by
hand if `pyproject.toml`'s dependency list changes, but don't rely on it
for actually setting up the environment; `uv sync` does that from
`pyproject.toml`/`uv.lock`.

Run everything via `uv run <cmd>` (auto-syncs the venv if needed) rather
than reaching into `.venv/bin/` directly.

```bash
# --- backend setup (creates .venv, installs from pyproject.toml/uv.lock) ---
uv sync

# --- data pipeline (rebuild after touching the generator or feature engineering) ---
uv run python data_generator/generate_data.py --out-dir data
uv run python feature_engineering/build_features.py --data-dir data

# --- ML models (retrain after regenerating data) ---
uv run python ml/train_estimation_model.py --data-dir data --out-dir ml/models
uv run python ml/train_safety_model.py --data-dir data --out-dir ml/models

# --- run ---
uv run uvicorn backend.main:app --reload --port 8000   # docs at /docs
uv run python tests/test_api.py                         # in-process smoke tests

# --- frontend (separate npm-managed toolchain, unrelated to uv) ---
cd frontend && npm install && npm run dev                  # http://127.0.0.1:5173
```

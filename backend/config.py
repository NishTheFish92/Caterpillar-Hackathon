import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("CAT_DATA_DIR", os.path.join(BASE_DIR, "data"))
ML_MODELS_DIR = os.environ.get("CAT_ML_MODELS_DIR", os.path.join(BASE_DIR, "ml", "models"))

# --- Hazard-prediction gate ---
# The ML model (backend/ml_models.py::SafetyHazardModel) only ever RAISES a
# candidate; it never marks something a hazard by itself. A prediction is
# only surfaced as "Predicted Hazard" if it clears BOTH of these:
#   1. model probability >= HAZARD_PROBABILITY_THRESHOLD
#   2. at least one independent rule-based condition also holds
# See routers/safety.py::_apply_hazard_gate.
HAZARD_PROBABILITY_THRESHOLD = 0.35
HAZARD_GATE_MAX_DISTANCE_M = 15.0   # rule: currently within this range of a hazard
HAZARD_GATE_MIN_PROXIMITY_RATE = 0.2  # rule: proximity alerts in >=20% of the last 5 min
HAZARD_GATE_MIN_SPEED_KMPH = 10.0    # rule: moving fast enough to matter

# --- Behavior / safety thresholds (tune freely, or later load from a rules table) ---
IDLE_PCT_WARNING = 20.0        # % of shift time idling before flagging "excessive idling"
IDLE_PCT_CRITICAL = 35.0
# Rate-based (per day) so the flags stay meaningful regardless of the
# `days` window the caller asks for, rather than raw totals over the window.
UNSAFE_EVENTS_PER_DAY_WARNING = 0.4
UNSAFE_EVENTS_PER_DAY_CRITICAL = 1.0
SEATBELT_COMPLIANCE_MIN_PCT = 90.0   # below this = compliance concern
PROXIMITY_ALERTS_PER_DAY_WARNING = 1.2

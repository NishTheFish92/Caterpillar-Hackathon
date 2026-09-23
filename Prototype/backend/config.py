import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("CAT_DATA_DIR", os.path.join(BASE_DIR, "data"))

# --- Behavior / safety thresholds (tune freely, or later load from a rules table) ---
IDLE_PCT_WARNING = 20.0        # % of shift time idling before flagging "excessive idling"
IDLE_PCT_CRITICAL = 35.0
# Rate-based (per day) so the flags stay meaningful regardless of the
# `days` window the caller asks for, rather than raw totals over the window.
UNSAFE_EVENTS_PER_DAY_WARNING = 0.4
UNSAFE_EVENTS_PER_DAY_CRITICAL = 1.0
SEATBELT_COMPLIANCE_MIN_PCT = 90.0   # below this = compliance concern
PROXIMITY_ALERTS_PER_DAY_WARNING = 1.2

# Simple environment/terrain multipliers applied on top of the historical
# benchmark for task-time estimation (used only as a fallback when there
# isn't a benchmark row for the exact combination requested).
ENV_DURATION_MULTIPLIER = {
    "Clear": 1.00,
    "Rain": 1.15,
    "Dust Storm": 1.25,
    "High Wind": 1.10,
}
TERRAIN_DURATION_MULTIPLIER = {
    "Soft Soil": 1.00,
    "Hard Soil": 1.10,
    "Rocky": 1.25,
    "Muddy": 1.20,
}

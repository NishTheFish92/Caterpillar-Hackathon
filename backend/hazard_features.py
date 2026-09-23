"""
hazard_features.py
--------------------
Computes the same rolling 5-minute window features at request time
(from live/recent telemetry) that feature_engineering/build_features.py
computes in bulk at training time. Keeping this in one small function is
what keeps train/serve feature parity honest - both read the same
column names and apply the same aggregations.
"""

from __future__ import annotations


def compute_rolling_features(pings: list[dict]) -> dict | None:
    """`pings`: telemetry rows for one machine, oldest first (as returned by
    DataRepositoryBase.get_recent_telemetry). Returns None if there's no
    telemetry to compute from."""
    if not pings:
        return None

    distances = [p["distance_to_hazard_m"] for p in pings]
    speeds = [p["speed_kmph"] for p in pings]
    alerts = [1.0 if p["proximity_alert"] == "yes" else 0.0 for p in pings]
    seatbelt_off = [1.0 if p["seatbelt_status"] == "no" else 0.0 for p in pings]
    idle = [1.0 if p["engine_status"] == "idle" else 0.0 for p in pings]

    return {
        "avg_distance_5min": sum(distances) / len(distances),
        "min_distance_5min": min(distances),
        "distance_trend_5min": distances[-1] - distances[0],
        "proximity_rate_5min": sum(alerts) / len(alerts),
        "avg_speed_5min": sum(speeds) / len(speeds),
        "seatbelt_off_rate_5min": sum(seatbelt_off) / len(seatbelt_off),
        "idle_rate_5min": sum(idle) / len(idle),
        "latest_speed_kmph": speeds[-1],
        "latest_distance_m": distances[-1],
    }

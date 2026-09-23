"""
build_features.py
------------------
Joins the raw CSVs and engineers the feature tables both the FastAPI
backend and the ML training scripts read from. This is intentionally a
*batch* job (run on a schedule / after new telemetry lands) so neither the
API nor model training ever does a heavy join at request time.

Outputs (all written to the same data directory):
    - task_features.csv              one row per task: actual vs scheduled
                                       duration, idle %, seatbelt compliance,
                                       proximity/unsafe event counts, PLUS
                                       operator/machine/site context
                                       (experience, certification, machine
                                       age/health, weather, traffic) used as
                                       features for task-time estimation.
    - operator_daily_features.csv    one row per operator per day: rollups
                                       used for behavior/anomaly detection.
    - duration_benchmarks.csv        historical avg/median duration grouped
                                       by task_type x environmental_condition
                                       x terrain_type -> a fallback baseline
                                       for task time estimation.
    - hazard_training_data.csv       one row per telemetry minute: rolling
                                       5-minute window features (closing
                                       distance, proximity rate, speed,
                                       seatbelt/idle rates) + machine/site
                                       context, labeled with whether a
                                       proximity alert occurs in the NEXT 5
                                       minutes. Input to the safety
                                       hazard-prediction model.

Run:
    python build_features.py --data-dir ../data
"""

import argparse
import os

import numpy as np
import pandas as pd

# Thresholds used while engineering safety/behavior signals.
SPEED_LIMIT_KMPH = 15.0          # speeds above this are "fast"
UNSAFE_SPEED_NEAR_HAZARD = 12.0   # speed threshold that counts as unsafe during a proximity alert

ROLLING_WINDOW_MIN = 5    # trailing window for hazard-prediction features
LOOKAHEAD_MIN = 5          # how far ahead we're predicting a hazard


def load_raw(data_dir):
    operators = pd.read_csv(os.path.join(data_dir, "operators.csv"))
    machines = pd.read_csv(os.path.join(data_dir, "machines.csv"))
    tasks = pd.read_csv(os.path.join(data_dir, "tasks.csv"), parse_dates=["scheduled_start", "scheduled_end"])
    telemetry = pd.read_csv(os.path.join(data_dir, "telemetry.csv"), parse_dates=["timestamp"])
    return operators, machines, tasks, telemetry


def build_task_features(tasks, telemetry, operators, machines):
    telemetry = telemetry.sort_values(["task_id", "timestamp"]).copy()

    # per-ping unsafe flag: speeding while a proximity alert is active, or
    # engine running with the seatbelt off
    telemetry["is_unsafe_event"] = (
        ((telemetry["proximity_alert"] == "yes") & (telemetry["speed_kmph"] >= UNSAFE_SPEED_NEAR_HAZARD))
        | ((telemetry["seatbelt_status"] == "no") & (telemetry["engine_status"] != "off"))
    )
    telemetry["is_idle"] = telemetry["engine_status"] == "idle"
    telemetry["is_seatbelt_on"] = telemetry["seatbelt_status"] == "yes"
    telemetry["is_proximity_alert"] = telemetry["proximity_alert"] == "yes"

    # Sustained conditions (proximity alerts, unsafe behavior) fire on every
    # ping while they're active. We want discrete EVENT counts, not minutes
    # of exposure, so we count "rising edges" (transition into the state)
    # per task rather than summing every ping where the flag is true.
    # NOTE: shift() on a boolean column upcasts it to `object` dtype, which
    # makes `~` do bitwise-not on Python bools (~False == -1, truthy!)
    # instead of logical negation. Explicitly cast back to bool after
    # fillna to avoid silently over-counting episodes.
    grp = telemetry.groupby("task_id")
    telemetry["_prev_unsafe"] = grp["is_unsafe_event"].shift(1).fillna(False).astype(bool)
    telemetry["unsafe_episode_start"] = telemetry["is_unsafe_event"] & (~telemetry["_prev_unsafe"])
    telemetry["_prev_proximity"] = grp["is_proximity_alert"].shift(1).fillna(False).astype(bool)
    telemetry["proximity_episode_start"] = telemetry["is_proximity_alert"] & (~telemetry["_prev_proximity"])

    agg = telemetry.groupby("task_id").agg(
        actual_start=("timestamp", "min"),
        actual_end=("timestamp", "max"),
        ping_count=("timestamp", "count"),
        idle_minutes=("is_idle", "sum"),
        seatbelt_on_minutes=("is_seatbelt_on", "sum"),
        proximity_alert_count=("proximity_episode_start", "sum"),
        unsafe_event_count=("unsafe_episode_start", "sum"),
        avg_speed_kmph=("speed_kmph", "mean"),
        max_speed_kmph=("speed_kmph", "max"),
        avg_engine_temp_c=("engine_temp_c", "mean"),
        avg_vibration=("vibration_level", "mean"),
        min_distance_to_hazard_m=("distance_to_hazard_m", "min"),
    ).reset_index()

    agg["actual_duration_min"] = (
        (agg["actual_end"] - agg["actual_start"]).dt.total_seconds() / 60.0
    ).round(1)
    agg["idle_pct"] = (agg["idle_minutes"] / agg["ping_count"] * 100).round(1)
    agg["seatbelt_compliance_pct"] = (agg["seatbelt_on_minutes"] / agg["ping_count"] * 100).round(1)

    merged = tasks.merge(agg, on="task_id", how="left")
    merged["scheduled_duration_min"] = (
        (merged["scheduled_end"] - merged["scheduled_start"]).dt.total_seconds() / 60.0
    ).round(1)
    merged["overrun_min"] = (merged["actual_duration_min"] - merged["scheduled_duration_min"]).round(1)

    # --- context joins: this is what makes task-time estimation and
    # anomaly detection use real operator/machine signal instead of just
    # task-type averages.
    op_cols = operators[["operator_id", "experience_years", "certification_level"]]
    merged = merged.merge(op_cols, on="operator_id", how="left")

    machines_ctx = machines[["machine_id", "machine_type", "year", "health_score", "total_engine_hours_lifetime"]].copy()
    machines_ctx["machine_age_years"] = pd.Timestamp.now().year - machines_ctx["year"]
    merged = merged.merge(
        machines_ctx[["machine_id", "machine_type", "machine_age_years", "health_score", "total_engine_hours_lifetime"]],
        on="machine_id", how="left",
    )
    merged = merged.rename(columns={"health_score": "machine_health_score"})

    cols = [
        "task_id", "date", "operator_id", "machine_id", "site_id", "task_type",
        "environmental_condition", "terrain_type", "ambient_temp_c", "visibility_pct",
        "site_traffic_density", "priority", "status",
        "scheduled_duration_min", "actual_duration_min", "overrun_min",
        "idle_pct", "seatbelt_compliance_pct", "proximity_alert_count",
        "unsafe_event_count", "avg_speed_kmph", "max_speed_kmph",
        "avg_engine_temp_c", "avg_vibration", "min_distance_to_hazard_m",
        "experience_years", "certification_level",
        "machine_type", "machine_age_years", "machine_health_score", "total_engine_hours_lifetime",
    ]
    return merged[cols]


def build_operator_daily_features(task_features):
    daily = task_features.groupby(["operator_id", "date"]).agg(
        tasks_completed=("task_id", "count"),
        total_engine_minutes=("actual_duration_min", "sum"),
        avg_idle_pct=("idle_pct", "mean"),
        avg_seatbelt_compliance_pct=("seatbelt_compliance_pct", "mean"),
        total_unsafe_events=("unsafe_event_count", "sum"),
        total_proximity_alerts=("proximity_alert_count", "sum"),
        avg_overrun_min=("overrun_min", "mean"),
    ).reset_index()

    daily["total_engine_hours"] = (daily["total_engine_minutes"] / 60).round(2)
    return daily.drop(columns=["total_engine_minutes"])


def build_duration_benchmarks(task_features):
    bench = task_features.groupby(["task_type", "environmental_condition", "terrain_type"]).agg(
        sample_size=("task_id", "count"),
        mean_duration_min=("actual_duration_min", "mean"),
        median_duration_min=("actual_duration_min", "median"),
        std_duration_min=("actual_duration_min", "std"),
    ).reset_index()
    bench["mean_duration_min"] = bench["mean_duration_min"].round(1)
    bench["median_duration_min"] = bench["median_duration_min"].round(1)
    bench["std_duration_min"] = bench["std_duration_min"].fillna(0).round(1)
    return bench


def _future_window_sum(s: pd.Series, window: int) -> pd.Series:
    """Sum of the NEXT `window` values (excluding the current one), NaN
    wherever fewer than `window` future values exist (end of a task)."""
    shifted = [s.shift(-j) for j in range(1, window + 1)]
    stacked = pd.concat(shifted, axis=1)
    return stacked.sum(axis=1, min_count=window)


def build_hazard_training_table(telemetry, tasks, machines):
    t = telemetry.sort_values(["task_id", "timestamp"]).copy()
    t["is_alert"] = (t["proximity_alert"] == "yes").astype(float)
    t["is_idle"] = (t["engine_status"] == "idle").astype(float)
    t["is_seatbelt_off"] = (t["seatbelt_status"] == "no").astype(float)

    grp = t.groupby("task_id", group_keys=False)
    w = ROLLING_WINDOW_MIN

    t["avg_distance_5min"] = grp["distance_to_hazard_m"].transform(lambda s: s.rolling(w, min_periods=1).mean())
    t["min_distance_5min"] = grp["distance_to_hazard_m"].transform(lambda s: s.rolling(w, min_periods=1).min())
    t["distance_trend_5min"] = grp["distance_to_hazard_m"].transform(lambda s: s.diff(w - 1))
    t["proximity_rate_5min"] = grp["is_alert"].transform(lambda s: s.rolling(w, min_periods=1).mean())
    t["avg_speed_5min"] = grp["speed_kmph"].transform(lambda s: s.rolling(w, min_periods=1).mean())
    t["seatbelt_off_rate_5min"] = grp["is_seatbelt_off"].transform(lambda s: s.rolling(w, min_periods=1).mean())
    t["idle_rate_5min"] = grp["is_idle"].transform(lambda s: s.rolling(w, min_periods=1).mean())

    future_alert_sum = grp["is_alert"].transform(lambda s: _future_window_sum(s, LOOKAHEAD_MIN))
    t["hazard_next_5min"] = (future_alert_sum > 0).astype("Int64")
    t.loc[future_alert_sum.isna(), "hazard_next_5min"] = pd.NA

    # static context: machine health + site/weather conditions for the task
    machine_health = machines.set_index("machine_id")["health_score"]
    t["machine_health_score"] = t["machine_id"].map(machine_health)

    task_ctx = tasks.set_index("task_id")[["site_traffic_density", "visibility_pct", "ambient_temp_c"]]
    t = t.merge(task_ctx, on="task_id", how="left")

    t = t.dropna(subset=["hazard_next_5min"])
    t["hazard_next_5min"] = t["hazard_next_5min"].astype(int)

    cols = [
        "timestamp", "task_id", "operator_id", "machine_id",
        "avg_distance_5min", "min_distance_5min", "distance_trend_5min",
        "proximity_rate_5min", "avg_speed_5min", "seatbelt_off_rate_5min", "idle_rate_5min",
        "machine_health_score", "site_traffic_density", "visibility_pct", "ambient_temp_c",
        "hazard_next_5min",
    ]
    out = t[cols].copy()
    for c in ["avg_distance_5min", "min_distance_5min", "distance_trend_5min",
              "proximity_rate_5min", "avg_speed_5min", "seatbelt_off_rate_5min", "idle_rate_5min"]:
        out[c] = out[c].round(3)
    return out


def main(data_dir):
    operators, machines, tasks, telemetry = load_raw(data_dir)

    task_features = build_task_features(tasks, telemetry, operators, machines)
    operator_daily_features = build_operator_daily_features(task_features)
    duration_benchmarks = build_duration_benchmarks(task_features)
    hazard_training_data = build_hazard_training_table(telemetry, tasks, machines)

    task_features.to_csv(os.path.join(data_dir, "task_features.csv"), index=False)
    operator_daily_features.to_csv(os.path.join(data_dir, "operator_daily_features.csv"), index=False)
    duration_benchmarks.to_csv(os.path.join(data_dir, "duration_benchmarks.csv"), index=False)
    hazard_training_data.to_csv(os.path.join(data_dir, "hazard_training_data.csv"), index=False)

    print(f"task_features.csv            : {len(task_features):>6} rows")
    print(f"operator_daily_features.csv  : {len(operator_daily_features):>6} rows")
    print(f"duration_benchmarks.csv      : {len(duration_benchmarks):>6} rows")
    print(f"hazard_training_data.csv     : {len(hazard_training_data):>6} rows "
          f"({hazard_training_data['hazard_next_5min'].mean():.1%} positive)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="../data")
    args = parser.parse_args()
    main(args.data_dir)

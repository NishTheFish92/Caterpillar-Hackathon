"""
build_features.py
------------------
Joins the 4 raw CSVs and engineers the feature tables the FastAPI backend
serves from. This is intentionally a *batch* job (run on a schedule / after
new telemetry lands) so the API layer never has to do heavy joins at
request time -> the API only ever reads small, pre-aggregated tables.

Outputs (all written to the same data directory):
    - task_features.csv              one row per task: actual vs scheduled
                                       duration, idle %, seatbelt compliance,
                                       proximity/unsafe event counts
    - operator_daily_features.csv    one row per operator per day: rollups
                                       used for behavior/anomaly detection
    - duration_benchmarks.csv        historical avg/median duration grouped
                                       by task_type x machine_type x
                                       environmental_condition x terrain_type
                                       -> used for task time estimation

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


def load_raw(data_dir):
    operators = pd.read_csv(os.path.join(data_dir, "operators.csv"))
    machines = pd.read_csv(os.path.join(data_dir, "machines.csv"))
    tasks = pd.read_csv(os.path.join(data_dir, "tasks.csv"), parse_dates=["scheduled_start", "scheduled_end"])
    telemetry = pd.read_csv(os.path.join(data_dir, "telemetry.csv"), parse_dates=["timestamp"])
    return operators, machines, tasks, telemetry


def build_task_features(tasks, telemetry):
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

    cols = [
        "task_id", "date", "operator_id", "machine_id", "site_id", "task_type",
        "environmental_condition", "terrain_type", "priority", "status",
        "scheduled_duration_min", "actual_duration_min", "overrun_min",
        "idle_pct", "seatbelt_compliance_pct", "proximity_alert_count",
        "unsafe_event_count", "avg_speed_kmph", "max_speed_kmph",
        "avg_engine_temp_c", "avg_vibration",
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
    group_cols = ["task_type", "machine_id", "environmental_condition", "terrain_type"]
    # machine_type would be more general than machine_id for a benchmark - keep both grains
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


def main(data_dir):
    operators, machines, tasks, telemetry = load_raw(data_dir)

    task_features = build_task_features(tasks, telemetry)
    operator_daily_features = build_operator_daily_features(task_features)
    duration_benchmarks = build_duration_benchmarks(task_features)

    task_features.to_csv(os.path.join(data_dir, "task_features.csv"), index=False)
    operator_daily_features.to_csv(os.path.join(data_dir, "operator_daily_features.csv"), index=False)
    duration_benchmarks.to_csv(os.path.join(data_dir, "duration_benchmarks.csv"), index=False)

    print(f"task_features.csv            : {len(task_features):>6} rows")
    print(f"operator_daily_features.csv  : {len(operator_daily_features):>6} rows")
    print(f"duration_benchmarks.csv      : {len(duration_benchmarks):>6} rows")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="../data")
    args = parser.parse_args()
    main(args.data_dir)

"""
generate_data.py
-----------------
Synthesizes raw operational data for the CAT Smart Operator Assistant.

Produces exactly 4 CSV files (kept deliberately simple / flat, so the
feature engineering layer has to do the real work):

    1. operators.csv   - operator master data
    2. machines.csv     - machine master data
    3. tasks.csv         - scheduled jobs (one row per task)
    4. telemetry.csv    - time-series sensor pings per task (1-minute cadence)

A handful of operators/machines are deliberately seeded with "bad behavior"
(excessive idling, seatbelt violations, unsafe speed near proximity alerts)
so that the downstream anomaly-detection features have something to find.

Run:
    python generate_data.py --out-dir ../data
"""

import argparse
import os
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# Config - tweak these to scale the dataset up/down
# --------------------------------------------------------------------------
SEED = 42
NUM_OPERATORS = 15
NUM_MACHINES = 10
NUM_DAYS = 30
SITES = ["SITE-A", "SITE-B", "SITE-C", "SITE-D"]
MACHINE_TYPES = ["Excavator", "Wheel Loader", "Bulldozer", "Backhoe"]
TASK_TYPES = ["Excavation", "Grading", "Material Loading", "Trenching", "Demolition"]
ENV_CONDITIONS = ["Clear", "Rain", "Dust Storm", "High Wind"]
TERRAIN_TYPES = ["Soft Soil", "Hard Soil", "Rocky", "Muddy"]
SHIFTS = ["Day", "Night"]

# Operators flagged (by index) to exhibit risky behavior patterns.
# Downstream behavior-analytics features should be able to surface these.
RISKY_OPERATOR_IDXS = {2, 7, 11}      # excessive idling + occasional unsafe speed
SEATBELT_OFFENDER_IDXS = {4, 9}        # frequently skip seatbelt

random.seed(SEED)
np.random.seed(SEED)


def gen_operators(n):
    rows = []
    first = ["Raj", "Amit", "Suresh", "Vikram", "Arjun", "Karthik", "Manoj", "Deepak",
              "Ganesh", "Naveen", "Prakash", "Sanjay", "Ramesh", "Vinod", "Anil"]
    for i in range(1, n + 1):
        rows.append({
            "operator_id": f"OP-{i:03d}",
            "name": f"{first[(i - 1) % len(first)]} {i:03d}",
            "license_type": random.choice(["Heavy Equipment - Class A", "Heavy Equipment - Class B"]),
            "experience_years": int(np.clip(np.random.normal(6, 4), 0, 25)),
            "shift": SHIFTS[i % 2],
        })
    return pd.DataFrame(rows)


def gen_machines(n):
    rows = []
    for i in range(1, n + 1):
        rows.append({
            "machine_id": f"MC-{i:03d}",
            "machine_type": MACHINE_TYPES[i % len(MACHINE_TYPES)],
            "model": f"CAT-{random.choice(['320', '336', 'D6', '950', '420'])}",
            "year": random.randint(2015, 2024),
            "fuel_type": random.choice(["Diesel", "Diesel", "Hybrid"]),
        })
    return pd.DataFrame(rows)


def gen_tasks(operators_df, machines_df, num_days):
    rows = []
    task_counter = 1
    start_date = datetime.now().date() - timedelta(days=num_days)

    for day_offset in range(num_days):
        the_date = start_date + timedelta(days=day_offset)
        # Each operator gets 1-3 tasks per day
        for _, op in operators_df.iterrows():
            n_tasks = random.choice([1, 1, 2, 3])
            shift_start_hour = 7 if op["shift"] == "Day" else 19
            cursor = datetime.combine(the_date, datetime.min.time()) + timedelta(hours=shift_start_hour)

            for _ in range(n_tasks):
                machine = machines_df.sample(1).iloc[0]
                duration_min = int(np.clip(np.random.normal(90, 30), 30, 240))
                sched_start = cursor
                sched_end = cursor + timedelta(minutes=duration_min)
                cursor = sched_end + timedelta(minutes=random.choice([10, 15, 20, 30]))

                rows.append({
                    "task_id": f"TSK-{task_counter:05d}",
                    "date": the_date.isoformat(),
                    "operator_id": op["operator_id"],
                    "machine_id": machine["machine_id"],
                    "site_id": random.choice(SITES),
                    "task_type": random.choice(TASK_TYPES),
                    "environmental_condition": random.choices(
                        ENV_CONDITIONS, weights=[0.6, 0.2, 0.1, 0.1]
                    )[0],
                    "terrain_type": random.choice(TERRAIN_TYPES),
                    "scheduled_start": sched_start.isoformat(),
                    "scheduled_end": sched_end.isoformat(),
                    "priority": random.choice(["Low", "Medium", "High"]),
                    "status": "Scheduled",
                })
                task_counter += 1
    return pd.DataFrame(rows)


def gen_telemetry(tasks_df, operators_df):
    """1-minute cadence telemetry for the duration of each task (+/- overrun)."""
    risky_ops = {f"OP-{i:03d}" for i in RISKY_OPERATOR_IDXS}
    seatbelt_offenders = {f"OP-{i:03d}" for i in SEATBELT_OFFENDER_IDXS}

    records = []
    for _, task in tasks_df.iterrows():
        sched_start = datetime.fromisoformat(task["scheduled_start"])
        sched_end = datetime.fromisoformat(task["scheduled_end"])
        scheduled_minutes = int((sched_end - sched_start).total_seconds() // 60)

        is_risky = task["operator_id"] in risky_ops
        is_seatbelt_offender = task["operator_id"] in seatbelt_offenders

        # actual duration can overrun/underrun the schedule a bit
        overrun_factor = np.random.normal(1.0, 0.15)
        if is_risky:
            overrun_factor += 0.25  # risky operators tend to run long (idling)
        actual_minutes = max(10, int(scheduled_minutes * max(0.6, overrun_factor)))

        # --- Seatbelt: a per-task decision, not a per-minute coin flip. In
        # practice an operator either buckles in for the job or doesn't -
        # this keeps the "yes/no" signal clean and realistic rather than
        # flickering minute to minute.
        seatbelt_off_prob = 0.30 if is_seatbelt_offender else 0.02
        task_seatbelt_off = np.random.rand() < seatbelt_off_prob

        # --- Proximity alerts: a small number of short, discrete episodes
        # scattered through the task, rather than independent per-minute noise.
        n_alert_episodes = np.random.choice([0, 1, 2, 3], p=[0.55, 0.25, 0.13, 0.07])
        alert_minutes = set()
        for _ in range(n_alert_episodes):
            episode_start = random.randint(0, max(0, actual_minutes - 1))
            episode_len = random.randint(1, 2)
            alert_minutes.update(range(episode_start, min(actual_minutes, episode_start + episode_len)))

        for minute in range(actual_minutes):
            ts = sched_start + timedelta(minutes=minute)

            # idle probability - elevated for risky operators
            idle_prob = 0.25 if is_risky else 0.05
            is_idle = np.random.rand() < idle_prob
            engine_status = "idle" if is_idle else "on"

            seatbelt_status = "no" if task_seatbelt_off else "yes"
            proximity_alert = "yes" if minute in alert_minutes else "no"

            # speed - risky operators occasionally speed even during a proximity alert
            base_speed = np.random.normal(8, 3) if engine_status == "on" else np.random.normal(0.5, 0.3)
            if is_risky and proximity_alert == "yes" and np.random.rand() < 0.5:
                base_speed = np.random.normal(18, 4)  # unsafe: speeding near a hazard
            speed_kmph = float(np.clip(base_speed, 0, 30))

            records.append({
                "timestamp": ts.isoformat(),
                "task_id": task["task_id"],
                "operator_id": task["operator_id"],
                "machine_id": task["machine_id"],
                "engine_status": engine_status,          # on / idle / off
                "seatbelt_status": seatbelt_status,        # yes / no
                "proximity_alert": proximity_alert,        # yes / no
                "speed_kmph": round(speed_kmph, 1),
                "engine_temp_c": round(float(np.clip(np.random.normal(85, 8), 60, 120)), 1),
                "fuel_level_pct": round(float(np.clip(100 - minute * 0.05 - np.random.rand() * 2, 5, 100)), 1),
                "hydraulic_pressure_psi": round(float(np.clip(np.random.normal(2200, 150), 1500, 3000)), 0),
                "vibration_level": round(float(np.clip(np.random.normal(3, 1.2), 0, 10)), 2),
            })
    return pd.DataFrame(records)


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)

    operators_df = gen_operators(NUM_OPERATORS)
    machines_df = gen_machines(NUM_MACHINES)
    tasks_df = gen_tasks(operators_df, machines_df, NUM_DAYS)
    telemetry_df = gen_telemetry(tasks_df, operators_df)

    operators_df.to_csv(os.path.join(out_dir, "operators.csv"), index=False)
    machines_df.to_csv(os.path.join(out_dir, "machines.csv"), index=False)
    tasks_df.to_csv(os.path.join(out_dir, "tasks.csv"), index=False)
    telemetry_df.to_csv(os.path.join(out_dir, "telemetry.csv"), index=False)

    print(f"operators.csv   : {len(operators_df):>7} rows")
    print(f"machines.csv     : {len(machines_df):>7} rows")
    print(f"tasks.csv         : {len(tasks_df):>7} rows")
    print(f"telemetry.csv    : {len(telemetry_df):>7} rows")
    print(f"Written to: {os.path.abspath(out_dir)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="../data")
    args = parser.parse_args()
    main(args.out_dir)

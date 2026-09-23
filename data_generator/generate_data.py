"""
generate_data.py
-----------------
Synthesizes raw operational data for the CAT Smart Operator Assistant.

Produces 4 CSV files:

    1. operators.csv   - operator master data (+ derived certification tier)
    2. machines.csv     - machine master data (+ lifetime usage / health signals)
    3. tasks.csv         - scheduled jobs, one row per task (+ site conditions)
    4. telemetry.csv    - time-series sensor pings per task, 1-minute cadence
                            (+ a continuous hazard-distance signal that leads
                             into every proximity-alert episode, so a rolling
                             window model has something real to learn from)

A handful of operators/machines are deliberately seeded with "bad behavior"
(excessive idling, seatbelt violations, unsafe speed near proximity alerts)
so the downstream anomaly-detection and hazard-prediction features have
real signal to find, not just noise.

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
TRAFFIC_LEVELS = ["Low", "Medium", "High"]

# Each site has a baseline congestion profile (weights over Low/Medium/High).
SITE_TRAFFIC_PROFILE = {
    "SITE-A": [0.15, 0.35, 0.50],   # busy urban-adjacent site
    "SITE-B": [0.30, 0.45, 0.25],
    "SITE-C": [0.55, 0.35, 0.10],   # quiet rural site
    "SITE-D": [0.30, 0.40, 0.30],
}

# Duration model: task type sets a base, terrain/environment scale it. This
# is what the scheduling desk would estimate up front, before knowing which
# operator/machine gets assigned - so it lives on the SCHEDULE, not the
# actual outcome. Real-world variance (who's driving, what machine, how
# busy the site is) is layered on afterward in gen_telemetry.
TASK_TYPE_BASE_MIN = {
    "Material Loading": 55,
    "Grading": 80,
    "Excavation": 100,
    "Trenching": 115,
    "Demolition": 135,
}
TERRAIN_DURATION_MULT = {"Soft Soil": 0.90, "Hard Soil": 1.00, "Rocky": 1.25, "Muddy": 1.15}
ENV_DURATION_MULT = {"Clear": 1.00, "Rain": 1.12, "Dust Storm": 1.20, "High Wind": 1.08}

# Operators flagged (by index) to exhibit risky behavior patterns.
# Downstream behavior-analytics / hazard-prediction features should be able
# to surface these.
RISKY_OPERATOR_IDXS = {2, 7, 11}      # excessive idling + occasional unsafe speed
SEATBELT_OFFENDER_IDXS = {4, 9}        # frequently skip seatbelt

random.seed(SEED)
np.random.seed(SEED)


def certification_level(experience_years: int) -> str:
    if experience_years < 3:
        return "Beginner"
    if experience_years < 8:
        return "Intermediate"
    return "Advanced"


def gen_operators(n):
    rows = []
    first = ["Raj", "Amit", "Suresh", "Vikram", "Arjun", "Karthik", "Manoj", "Deepak",
              "Ganesh", "Naveen", "Prakash", "Sanjay", "Ramesh", "Vinod", "Anil"]
    for i in range(1, n + 1):
        experience_years = int(np.clip(np.random.normal(6, 4), 0, 25))
        rows.append({
            "operator_id": f"OP-{i:03d}",
            "name": f"{first[(i - 1) % len(first)]} {i:03d}",
            "license_type": random.choice(["Heavy Equipment - Class A", "Heavy Equipment - Class B"]),
            "experience_years": experience_years,
            "certification_level": certification_level(experience_years),
            "shift": SHIFTS[i % 2],
        })
    return pd.DataFrame(rows)


def gen_machines(n):
    now_year = datetime.now().year
    rows = []
    for i in range(1, n + 1):
        year = random.randint(2015, 2024)
        age_years = max(0, now_year - year)
        lifetime_hours = max(0.0, round(age_years * random.uniform(900, 1500) + random.uniform(-200, 200), 0))
        last_service_days_ago = random.randint(5, 200)
        health_score = float(np.clip(
            100
            - age_years * 2.2
            - last_service_days_ago * 0.15
            - (lifetime_hours / 1000) * 3
            + np.random.normal(0, 4),
            35, 100,
        ))
        rows.append({
            "machine_id": f"MC-{i:03d}",
            "machine_type": MACHINE_TYPES[i % len(MACHINE_TYPES)],
            "model": f"CAT-{random.choice(['320', '336', 'D6', '950', '420'])}",
            "year": year,
            "fuel_type": random.choice(["Diesel", "Diesel", "Hybrid"]),
            "total_engine_hours_lifetime": lifetime_hours,
            "last_service_days_ago": last_service_days_ago,
            "health_score": round(health_score, 1),
        })
    return pd.DataFrame(rows)


def _ambient_temp_c(env_condition, shift):
    base = {
        "Clear": (28, 5),
        "Rain": (22, 4),
        "Dust Storm": (33, 6),
        "High Wind": (25, 5),
    }[env_condition]
    temp = np.random.normal(*base)
    if shift == "Night":
        temp -= random.uniform(4, 9)
    return float(np.clip(temp, 5, 48))


def _visibility_pct(env_condition, shift):
    base = {
        "Clear": (92, 6),
        "Rain": (65, 12),
        "Dust Storm": (35, 15),
        "High Wind": (75, 10),
    }[env_condition]
    vis = np.random.normal(*base)
    if shift == "Night":
        vis -= random.uniform(10, 25)
    return float(np.clip(vis, 5, 100))


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

                site_id = random.choice(SITES)
                env_condition = random.choices(ENV_CONDITIONS, weights=[0.6, 0.2, 0.1, 0.1])[0]
                terrain_type = random.choice(TERRAIN_TYPES)
                task_type = random.choice(TASK_TYPES)
                traffic_density = random.choices(TRAFFIC_LEVELS, weights=SITE_TRAFFIC_PROFILE[site_id])[0]

                planned_min = (
                    TASK_TYPE_BASE_MIN[task_type]
                    * TERRAIN_DURATION_MULT[terrain_type]
                    * ENV_DURATION_MULT[env_condition]
                    * np.random.normal(1.0, 0.1)
                )
                duration_min = int(np.clip(planned_min, 25, 300))
                sched_start = cursor
                sched_end = cursor + timedelta(minutes=duration_min)
                cursor = sched_end + timedelta(minutes=random.choice([10, 15, 20, 30]))

                rows.append({
                    "task_id": f"TSK-{task_counter:05d}",
                    "date": the_date.isoformat(),
                    "operator_id": op["operator_id"],
                    "machine_id": machine["machine_id"],
                    "site_id": site_id,
                    "task_type": task_type,
                    "environmental_condition": env_condition,
                    "terrain_type": terrain_type,
                    "ambient_temp_c": round(_ambient_temp_c(env_condition, op["shift"]), 1),
                    "visibility_pct": round(_visibility_pct(env_condition, op["shift"]), 1),
                    "site_traffic_density": traffic_density,
                    "scheduled_start": sched_start.isoformat(),
                    "scheduled_end": sched_end.isoformat(),
                    "priority": random.choice(["Low", "Medium", "High"]),
                    "status": "Scheduled",
                })
                task_counter += 1
    return pd.DataFrame(rows)


def _n_alert_episodes(traffic_density, visibility_pct, is_risky):
    """Episode-count distribution shifts with congestion/visibility/operator risk
    so the hazard signal is genuinely predictable from context, not pure noise."""
    base = np.array([0.55, 0.25, 0.13, 0.07])
    if traffic_density == "High" or visibility_pct < 50:
        base = np.array([0.35, 0.30, 0.20, 0.15])
    if is_risky:
        base = base * np.array([0.7, 1.0, 1.2, 1.4])
        base = base / base.sum()
    return np.random.choice([0, 1, 2, 3], p=base)


def _hazard_distance_series(actual_minutes, alert_minutes_by_episode):
    """Continuous 'distance to nearest hazard' signal (metres). Ramps down for a
    few minutes BEFORE each proximity-alert episode (a leading indicator the
    hazard-prediction model can learn from), bottoms out during the episode,
    then recovers afterward."""
    baseline = np.clip(np.random.normal(30, 8, size=actual_minutes), 5, 60)
    distance = baseline.copy()

    for episode_start, episode_len in alert_minutes_by_episode:
        episode_end = episode_start + episode_len - 1
        min_dist = random.uniform(2, 6)
        lead_in = random.randint(3, 6)
        trail_out = random.randint(2, 4)

        ramp_start = max(0, episode_start - lead_in)
        for m in range(ramp_start, episode_start):
            frac = (m - ramp_start) / max(1, episode_start - ramp_start)
            distance[m] = min(distance[m], baseline[m] * (1 - frac) + min_dist * frac)

        for m in range(episode_start, min(actual_minutes, episode_end + 1)):
            distance[m] = min_dist + np.random.normal(0, 0.6)

        ramp_end = min(actual_minutes, episode_end + 1 + trail_out)
        for m in range(episode_end + 1, ramp_end):
            frac = (m - episode_end) / max(1, ramp_end - episode_end)
            distance[m] = min(distance[m], min_dist * (1 - frac) + baseline[m] * frac)

    return np.clip(distance, 1, 60)


def gen_telemetry(tasks_df, operators_df, machines_df):
    """1-minute cadence telemetry for the duration of each task (+/- overrun)."""
    risky_ops = {f"OP-{i:03d}" for i in RISKY_OPERATOR_IDXS}
    seatbelt_offenders = {f"OP-{i:03d}" for i in SEATBELT_OFFENDER_IDXS}
    machine_health = machines_df.set_index("machine_id")["health_score"].to_dict()
    operator_experience = operators_df.set_index("operator_id")["experience_years"].to_dict()

    records = []
    for _, task in tasks_df.iterrows():
        sched_start = datetime.fromisoformat(task["scheduled_start"])
        sched_end = datetime.fromisoformat(task["scheduled_end"])
        scheduled_minutes = int((sched_end - sched_start).total_seconds() // 60)

        is_risky = task["operator_id"] in risky_ops
        is_seatbelt_offender = task["operator_id"] in seatbelt_offenders

        # actual duration deviates from the schedule based on who's actually
        # doing the work: a more experienced operator finishes faster, a
        # less healthy machine runs slower, on top of the same real-world
        # frictions (heavy site traffic / poor visibility) applied as
        # multiplicative factors around a small noise term.
        experience_years = operator_experience.get(task["operator_id"], 6)
        exp_factor = 1.0 - 0.015 * min(experience_years, 20)   # up to ~30% faster at 20+ yrs
        machine_health_score = machine_health.get(task["machine_id"], 80.0)
        health_factor = 1.0 + (100 - machine_health_score) / 100 * 0.25  # up to ~16% slower at low health

        overrun_factor = np.random.normal(1.0, 0.08) * exp_factor * health_factor
        if is_risky:
            overrun_factor += 0.20  # risky operators tend to run long (idling)
        if task["site_traffic_density"] == "High":
            overrun_factor += 0.06
        if task["visibility_pct"] < 50:
            overrun_factor += 0.05
        actual_minutes = max(10, int(scheduled_minutes * max(0.5, overrun_factor)))

        # --- Seatbelt: a per-task decision, not a per-minute coin flip. In
        # practice an operator either buckles in for the job or doesn't -
        # this keeps the "yes/no" signal clean and realistic rather than
        # flickering minute to minute.
        seatbelt_off_prob = 0.30 if is_seatbelt_offender else 0.02
        task_seatbelt_off = np.random.rand() < seatbelt_off_prob

        # --- Proximity alerts: a small number of short, discrete episodes
        # scattered through the task, rather than independent per-minute
        # noise. Episode frequency shifts with site congestion/visibility.
        n_alert_episodes = _n_alert_episodes(task["site_traffic_density"], task["visibility_pct"], is_risky)
        alert_minutes = set()
        episodes = []
        for _ in range(n_alert_episodes):
            episode_start = random.randint(0, max(0, actual_minutes - 1))
            episode_len = random.randint(1, 2)
            episodes.append((episode_start, episode_len))
            alert_minutes.update(range(episode_start, min(actual_minutes, episode_start + episode_len)))

        distance_series = _hazard_distance_series(actual_minutes, episodes)

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
                "distance_to_hazard_m": round(float(distance_series[minute]), 1),
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
    telemetry_df = gen_telemetry(tasks_df, operators_df, machines_df)

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

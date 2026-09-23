"""
repository.py
-------------
This is the ONE place in the codebase that knows where data physically
lives. Every router talks to `DataRepository` through the abstract
interface below, never to pandas/CSV directly.

Why this matters for scalability:
    Today `CsvDataRepository` reads flat files into memory once at startup.
    Tomorrow you can write `PostgresDataRepository` / `TimescaleDataRepository`
    that implements the exact same `DataRepositoryBase` interface (backed by
    real queries instead of dataframe filtering) and swap it in with a single
    line change in `dependencies.py` - no router/service code changes needed.

    Similarly, `log_incident` currently appends to a CSV; swapping it for a
    Kafka producer / DB insert is a one-file change.
"""

from __future__ import annotations

import os
import threading
from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import Optional

import pandas as pd

from backend import config


class DataRepositoryBase(ABC):
    """Interface every concrete data backend must implement."""

    @abstractmethod
    def get_operator(self, operator_id: str) -> Optional[dict]: ...

    @abstractmethod
    def get_machine(self, machine_id: str) -> Optional[dict]: ...

    @abstractmethod
    def get_tasks_for_operator(self, operator_id: str, for_date: Optional[str] = None) -> list[dict]: ...

    @abstractmethod
    def get_latest_telemetry(self, machine_id: str) -> Optional[dict]: ...

    @abstractmethod
    def get_active_proximity_alerts(self) -> list[dict]: ...

    @abstractmethod
    def get_operator_daily_features(self, operator_id: str, days: int) -> list[dict]: ...

    @abstractmethod
    def get_duration_benchmark(self, task_type: str, environmental_condition: str, terrain_type: str) -> Optional[dict]: ...

    @abstractmethod
    def log_incident(self, incident: dict) -> dict: ...

    @abstractmethod
    def get_incidents(self, operator_id: Optional[str] = None, machine_id: Optional[str] = None) -> list[dict]: ...


class CsvDataRepository(DataRepositoryBase):
    """
    Reference implementation backed by the CSVs produced by
    `data_generator/generate_data.py` and `feature_engineering/build_features.py`.

    Loaded once into memory at startup (refresh() can be called to reload,
    e.g. from a scheduled job after the batch feature pipeline reruns).
    """

    def __init__(self, data_dir: str = config.DATA_DIR):
        self.data_dir = data_dir
        self._lock = threading.Lock()
        self.refresh()

    def refresh(self):
        with self._lock:
            self.operators = pd.read_csv(os.path.join(self.data_dir, "operators.csv"))
            self.machines = pd.read_csv(os.path.join(self.data_dir, "machines.csv"))
            self.tasks = pd.read_csv(
                os.path.join(self.data_dir, "tasks.csv"),
                parse_dates=["scheduled_start", "scheduled_end"],
            )
            self.telemetry = pd.read_csv(
                os.path.join(self.data_dir, "telemetry.csv"), parse_dates=["timestamp"]
            )
            self.task_features = pd.read_csv(os.path.join(self.data_dir, "task_features.csv"))
            self.operator_daily_features = pd.read_csv(
                os.path.join(self.data_dir, "operator_daily_features.csv")
            )
            self.duration_benchmarks = pd.read_csv(os.path.join(self.data_dir, "duration_benchmarks.csv"))

            incidents_path = os.path.join(self.data_dir, "incidents.csv")
            if os.path.exists(incidents_path):
                self.incidents = pd.read_csv(incidents_path)
            else:
                self.incidents = pd.DataFrame(columns=[
                    "incident_id", "timestamp", "operator_id", "machine_id",
                    "task_id", "incident_type", "severity", "description",
                ])

    # ---------- master data ----------
    def get_operator(self, operator_id: str) -> Optional[dict]:
        row = self.operators[self.operators["operator_id"] == operator_id]
        return row.iloc[0].to_dict() if not row.empty else None

    def get_machine(self, machine_id: str) -> Optional[dict]:
        row = self.machines[self.machines["machine_id"] == machine_id]
        return row.iloc[0].to_dict() if not row.empty else None

    # ---------- dashboard ----------
    def get_tasks_for_operator(self, operator_id: str, for_date: Optional[str] = None) -> list[dict]:
        df = self.tasks[self.tasks["operator_id"] == operator_id]
        if for_date:
            df = df[df["date"] == for_date]
        df = df.sort_values("scheduled_start")
        return df.to_dict(orient="records")

    # ---------- safety ----------
    def get_latest_telemetry(self, machine_id: str) -> Optional[dict]:
        df = self.telemetry[self.telemetry["machine_id"] == machine_id]
        if df.empty:
            return None
        row = df.sort_values("timestamp").iloc[-1]
        return row.to_dict()

    def get_active_proximity_alerts(self) -> list[dict]:
        # "Active" here = most recent ping per machine shows an alert.
        latest_per_machine = (
            self.telemetry.sort_values("timestamp").groupby("machine_id").tail(1)
        )
        alerts = latest_per_machine[latest_per_machine["proximity_alert"] == "yes"]
        return alerts.to_dict(orient="records")

    def log_incident(self, incident: dict) -> dict:
        with self._lock:
            incident = dict(incident)
            incident["incident_id"] = f"INC-{len(self.incidents) + 1:05d}"
            incident["timestamp"] = incident.get("timestamp") or datetime.utcnow().isoformat()
            self.incidents = pd.concat(
                [self.incidents, pd.DataFrame([incident])], ignore_index=True
            )
            self.incidents.to_csv(os.path.join(self.data_dir, "incidents.csv"), index=False)
            return incident

    def get_incidents(self, operator_id: Optional[str] = None, machine_id: Optional[str] = None) -> list[dict]:
        df = self.incidents
        if operator_id:
            df = df[df["operator_id"] == operator_id]
        if machine_id:
            df = df[df["machine_id"] == machine_id]
        df = df.sort_values("timestamp", ascending=False)
        # CSV round-tripping turns missing optional fields (e.g. task_id=None)
        # into NaN; convert back to None so the response model validates.
        df = df.astype(object).where(pd.notnull(df), None)
        return df.to_dict(orient="records")

    # ---------- behavior / anomaly ----------
    def get_operator_daily_features(self, operator_id: str, days: int) -> list[dict]:
        df = self.operator_daily_features[self.operator_daily_features["operator_id"] == operator_id]
        df = df.sort_values("date", ascending=False).head(days)
        return df.to_dict(orient="records")

    # ---------- task time estimation ----------
    def get_duration_benchmark(self, task_type: str, environmental_condition: str, terrain_type: str) -> Optional[dict]:
        df = self.duration_benchmarks[
            (self.duration_benchmarks["task_type"] == task_type)
            & (self.duration_benchmarks["environmental_condition"] == environmental_condition)
            & (self.duration_benchmarks["terrain_type"] == terrain_type)
        ]
        if df.empty:
            return None
        return df.iloc[0].to_dict()

    def get_task_type_baseline(self, task_type: str) -> Optional[dict]:
        """Fallback: average duration for the task type alone, ignoring conditions."""
        df = self.task_features[self.task_features["task_type"] == task_type]
        if df.empty:
            return None
        return {
            "sample_size": int(len(df)),
            "mean_duration_min": round(float(df["actual_duration_min"].mean()), 1),
            "median_duration_min": round(float(df["actual_duration_min"].median()), 1),
        }

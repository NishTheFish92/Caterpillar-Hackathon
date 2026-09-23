from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------- Dashboard ----------
class TaskOut(BaseModel):
    task_id: str
    date: str
    operator_id: str
    machine_id: str
    site_id: str
    task_type: str
    environmental_condition: str
    terrain_type: str
    scheduled_start: datetime
    scheduled_end: datetime
    priority: str
    status: str


# ---------- Safety ----------
class SeatbeltStatusOut(BaseModel):
    machine_id: str
    operator_id: Optional[str]
    timestamp: Optional[datetime]
    seatbelt_status: Optional[str]
    compliant: bool


class ProximityAlertOut(BaseModel):
    machine_id: str
    operator_id: Optional[str]
    timestamp: Optional[datetime]
    proximity_alert: str
    speed_kmph: Optional[float]
    risk_level: str


class IncidentCreate(BaseModel):
    operator_id: str
    machine_id: str
    task_id: Optional[str] = None
    incident_type: str = Field(..., description="e.g. Near-Miss, Collision, Seatbelt Violation, Mechanical Fault")
    severity: str = Field(..., description="Low / Medium / High / Critical")
    description: Optional[str] = None


class IncidentOut(IncidentCreate):
    incident_id: str
    timestamp: datetime


# ---------- Training ----------
class TrainingModuleOut(BaseModel):
    module_id: str
    title: str
    format: str  # e-learning-video / simulation / instructor-led
    duration_min: int
    skill_level: str
    description: str


class InstructorBookingCreate(BaseModel):
    operator_id: str
    module_id: str
    preferred_datetime: datetime
    notes: Optional[str] = None


class InstructorBookingOut(InstructorBookingCreate):
    booking_id: str
    status: str


# ---------- Behavior / Anomaly ----------
class AnomalyFlag(BaseModel):
    flag: str
    severity: str
    detail: str


class OperatorBehaviorReport(BaseModel):
    operator_id: str
    days_analyzed: int
    avg_idle_pct: float
    avg_seatbelt_compliance_pct: float
    total_unsafe_events: int
    total_proximity_alerts: int
    anomalies: list[AnomalyFlag]


# ---------- Task Time Estimation ----------
class TaskTimeEstimateRequest(BaseModel):
    task_type: str
    environmental_condition: str
    terrain_type: str


class TaskTimeEstimateOut(BaseModel):
    task_type: str
    environmental_condition: str
    terrain_type: str
    predicted_duration_min: float
    confidence: str
    basis: str
    sample_size: int

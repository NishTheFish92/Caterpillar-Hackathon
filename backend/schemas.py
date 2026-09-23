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


class HazardPredictionOut(BaseModel):
    machine_id: str
    operator_id: Optional[str]
    window_minutes: int
    ml_hazard_probability: float
    rule_conditions_met: list[str]
    predicted_hazard: bool = Field(
        ..., description="True only if the ML probability cleared the threshold AND at least one rule condition also held."
    )
    basis: str


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


# ---------- Training Hub (wiki) ----------
class ArticleOut(BaseModel):
    article_id: str
    title: str
    category: str
    format: str  # article / e-learning-video / simulation / instructor-led
    skill_level: str  # Beginner / Intermediate / Advanced / All Levels
    read_time_min: int
    summary: str
    content: str


class InstructorBookingCreate(BaseModel):
    operator_id: str
    article_id: str
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
    operator_id: Optional[str] = Field(
        None, description="If given, the operator's real experience/certification feed the model instead of dataset averages."
    )
    machine_id: Optional[str] = Field(
        None, description="If given, the machine's real age/health feed the model instead of dataset averages."
    )


class TaskTimeEstimateOut(BaseModel):
    task_type: str
    environmental_condition: str
    terrain_type: str
    predicted_duration_min: float
    confidence: str
    basis: str
    benchmark_mean_min: Optional[float] = Field(
        None, description="Historical average for this exact task/condition/terrain combo, shown alongside the ML prediction for a sanity check."
    )
    benchmark_sample_size: int = 0

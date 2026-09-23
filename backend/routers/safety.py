from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend import config
from backend.data_access.repository import DataRepositoryBase
from backend.dependencies import get_repository
from backend.hazard_features import compute_rolling_features
from backend.ml_models import SafetyHazardModel, get_safety_hazard_model
from backend.schemas import (
    HazardPredictionOut,
    IncidentCreate,
    IncidentOut,
    ProximityAlertOut,
    SeatbeltStatusOut,
)

router = APIRouter(prefix="/safety", tags=["Safety"])


@router.get("/seatbelt/{machine_id}", response_model=SeatbeltStatusOut)
def get_seatbelt_status(machine_id: str, repo: DataRepositoryBase = Depends(get_repository)):
    """Real-time seatbelt compliance for whoever is currently on the machine."""
    ping = repo.get_latest_telemetry(machine_id)
    if ping is None:
        raise HTTPException(status_code=404, detail="No telemetry found for this machine")
    return SeatbeltStatusOut(
        machine_id=machine_id,
        operator_id=ping.get("operator_id"),
        timestamp=ping.get("timestamp"),
        seatbelt_status=ping.get("seatbelt_status"),
        compliant=ping.get("seatbelt_status") == "yes",
    )


@router.get("/proximity/{machine_id}", response_model=ProximityAlertOut)
def get_proximity_status(machine_id: str, repo: DataRepositoryBase = Depends(get_repository)):
    """Real-time proximity hazard status for a single machine (rule-based,
    reacts to what telemetry shows RIGHT NOW). For a forward-looking
    prediction see /safety/hazard-prediction/{machine_id}."""
    ping = repo.get_latest_telemetry(machine_id)
    if ping is None:
        raise HTTPException(status_code=404, detail="No telemetry found for this machine")

    alert = ping.get("proximity_alert") == "yes"
    speed = ping.get("speed_kmph")
    if alert and speed is not None and speed >= 12.0:
        risk_level = "High"
    elif alert:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    return ProximityAlertOut(
        machine_id=machine_id,
        operator_id=ping.get("operator_id"),
        timestamp=ping.get("timestamp"),
        proximity_alert=ping.get("proximity_alert"),
        speed_kmph=speed,
        risk_level=risk_level,
    )


@router.get("/proximity", response_model=list[ProximityAlertOut])
def get_all_active_proximity_alerts(repo: DataRepositoryBase = Depends(get_repository)):
    """Site-wide feed of machines currently showing an active proximity hazard."""
    alerts = repo.get_active_proximity_alerts()
    out = []
    for ping in alerts:
        speed = ping.get("speed_kmph")
        risk_level = "High" if speed is not None and speed >= 12.0 else "Medium"
        out.append(ProximityAlertOut(
            machine_id=ping.get("machine_id"),
            operator_id=ping.get("operator_id"),
            timestamp=ping.get("timestamp"),
            proximity_alert=ping.get("proximity_alert"),
            speed_kmph=speed,
            risk_level=risk_level,
        ))
    return out


def _apply_hazard_gate(ml_probability: float, rolling: dict) -> tuple[bool, list[str]]:
    """The rule-based gate the ML model's output must clear before it's ever
    surfaced as a hazard. Two independent checks:
      1. ml_probability >= HAZARD_PROBABILITY_THRESHOLD
      2. at least one rule-based condition below also holds - the model
         can't raise a hazard purely on a pattern rules can't explain.
    Returns (predicted_hazard, list of rule conditions that held)."""
    conditions_met = []

    if rolling["min_distance_5min"] <= config.HAZARD_GATE_MAX_DISTANCE_M:
        conditions_met.append(
            f"Minimum distance in last 5 min ({rolling['min_distance_5min']:.1f}m) "
            f"<= gate threshold ({config.HAZARD_GATE_MAX_DISTANCE_M}m)"
        )
    if rolling["proximity_rate_5min"] >= config.HAZARD_GATE_MIN_PROXIMITY_RATE:
        conditions_met.append(
            f"Proximity alerts in {rolling['proximity_rate_5min']:.0%} of last 5 min "
            f">= gate threshold ({config.HAZARD_GATE_MIN_PROXIMITY_RATE:.0%})"
        )
    if rolling["latest_speed_kmph"] >= config.HAZARD_GATE_MIN_SPEED_KMPH:
        conditions_met.append(
            f"Current speed ({rolling['latest_speed_kmph']:.1f} km/h) "
            f">= gate threshold ({config.HAZARD_GATE_MIN_SPEED_KMPH} km/h)"
        )

    predicted_hazard = ml_probability >= config.HAZARD_PROBABILITY_THRESHOLD and len(conditions_met) > 0
    return predicted_hazard, conditions_met


@router.get("/hazard-prediction/{machine_id}", response_model=HazardPredictionOut)
def predict_hazard(
    machine_id: str,
    repo: DataRepositoryBase = Depends(get_repository),
    model: SafetyHazardModel = Depends(get_safety_hazard_model),
):
    """
    Forward-looking hazard prediction: given the machine's last 5 minutes
    of telemetry (closing distance, proximity-alert rate, speed, seatbelt/
    idle rates) plus machine health and site conditions, a
    RandomForestClassifier estimates the probability of a proximity-alert
    episode in the NEXT 5 minutes.

    Per spec, the model's output is never surfaced directly - it only
    becomes a "predicted hazard" after also clearing an independent
    rule-based gate (see `_apply_hazard_gate`). The model raises
    candidates; rules decide what gets shown.
    """
    pings = repo.get_recent_telemetry(machine_id, minutes=5)
    rolling = compute_rolling_features(pings)
    if rolling is None:
        raise HTTPException(status_code=404, detail="No telemetry found for this machine")

    machine = repo.get_machine(machine_id)
    latest = pings[-1]

    features = {
        "avg_distance_5min": rolling["avg_distance_5min"],
        "min_distance_5min": rolling["min_distance_5min"],
        "distance_trend_5min": rolling["distance_trend_5min"],
        "proximity_rate_5min": rolling["proximity_rate_5min"],
        "avg_speed_5min": rolling["avg_speed_5min"],
        "seatbelt_off_rate_5min": rolling["seatbelt_off_rate_5min"],
        "idle_rate_5min": rolling["idle_rate_5min"],
        "machine_health_score": machine.get("health_score") if machine else None,
    }

    ml_probability = model.predict_proba(features)
    predicted_hazard, conditions_met = _apply_hazard_gate(ml_probability, rolling)

    return HazardPredictionOut(
        machine_id=machine_id,
        operator_id=latest.get("operator_id"),
        window_minutes=len(pings),
        ml_hazard_probability=round(ml_probability, 3),
        rule_conditions_met=conditions_met,
        predicted_hazard=predicted_hazard,
        basis=(
            f"RandomForestClassifier (holdout ROC-AUC {model.meta['holdout_roc_auc']}) "
            "gated by rule-based proximity/speed/distance checks before being marked a hazard."
        ),
    )


@router.post("/incidents", response_model=IncidentOut, status_code=201)
def log_incident(incident: IncidentCreate, repo: DataRepositoryBase = Depends(get_repository)):
    """Manually or automatically log a safety incident (near-miss, violation, fault, etc.)."""
    saved = repo.log_incident(incident.model_dump())
    return saved


@router.get("/incidents", response_model=list[IncidentOut])
def list_incidents(
    operator_id: Optional[str] = None,
    machine_id: Optional[str] = None,
    repo: DataRepositoryBase = Depends(get_repository),
):
    return repo.get_incidents(operator_id=operator_id, machine_id=machine_id)

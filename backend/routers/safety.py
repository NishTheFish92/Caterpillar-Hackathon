from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend import config
from backend.data_access.repository import DataRepositoryBase
from backend.dependencies import get_repository
from backend.schemas import (
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
    """Real-time proximity hazard status for a single machine."""
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

from fastapi import APIRouter, Depends, HTTPException

from backend import config
from backend.data_access.repository import DataRepositoryBase
from backend.dependencies import get_repository
from backend.schemas import AnomalyFlag, OperatorBehaviorReport

router = APIRouter(prefix="/behavior", tags=["Unusual Behavior Detection"])


def _evaluate_anomalies(avg_idle_pct, unsafe_per_day, proximity_per_day, total_unsafe, total_proximity) -> list[AnomalyFlag]:
    """
    Rule-based anomaly detection over the engineered daily rollups.
    Thresholds are rate-based (per day) so the flags stay meaningful no
    matter how wide a `days` window the caller asks for. Simple thresholds
    today; this function is the single place you'd swap in a real model
    (e.g. an isolation forest over the same feature set) later without
    touching the router or the response schema.
    """
    flags = []

    if avg_idle_pct >= config.IDLE_PCT_CRITICAL:
        flags.append(AnomalyFlag(
            flag="Excessive Idling",
            severity="Critical",
            detail=f"Average idle time is {avg_idle_pct:.1f}%, well above the {config.IDLE_PCT_CRITICAL:.0f}% threshold.",
        ))
    elif avg_idle_pct >= config.IDLE_PCT_WARNING:
        flags.append(AnomalyFlag(
            flag="Elevated Idling",
            severity="Warning",
            detail=f"Average idle time is {avg_idle_pct:.1f}%, above the {config.IDLE_PCT_WARNING:.0f}% warning threshold.",
        ))

    if unsafe_per_day >= config.UNSAFE_EVENTS_PER_DAY_CRITICAL:
        flags.append(AnomalyFlag(
            flag="Unsafe Operation Pattern",
            severity="Critical",
            detail=f"{total_unsafe} unsafe events recorded (~{unsafe_per_day:.1f}/day) - speeding near hazards or seatbelt off while running.",
        ))
    elif unsafe_per_day >= config.UNSAFE_EVENTS_PER_DAY_WARNING:
        flags.append(AnomalyFlag(
            flag="Unsafe Operation Pattern",
            severity="Warning",
            detail=f"{total_unsafe} unsafe events recorded (~{unsafe_per_day:.1f}/day) in the analyzed window.",
        ))

    if proximity_per_day >= config.PROXIMITY_ALERTS_PER_DAY_WARNING:
        flags.append(AnomalyFlag(
            flag="Frequent Proximity Alerts",
            severity="Warning",
            detail=f"{total_proximity} proximity alerts recorded (~{proximity_per_day:.1f}/day) - review site congestion or route planning.",
        ))

    return flags


@router.get("/{operator_id}/anomalies", response_model=OperatorBehaviorReport)
def get_operator_anomalies(
    operator_id: str,
    days: int = 7,
    repo: DataRepositoryBase = Depends(get_repository),
):
    if repo.get_operator(operator_id) is None:
        raise HTTPException(status_code=404, detail="Operator not found")

    rows = repo.get_operator_daily_features(operator_id, days=days)
    if not rows:
        raise HTTPException(status_code=404, detail="No behavior data available for this operator")

    n = len(rows)
    avg_idle_pct = sum(r["avg_idle_pct"] for r in rows) / n
    avg_seatbelt = sum(r["avg_seatbelt_compliance_pct"] for r in rows) / n
    total_unsafe = sum(r["total_unsafe_events"] for r in rows)
    total_proximity = sum(r["total_proximity_alerts"] for r in rows)
    unsafe_per_day = total_unsafe / n
    proximity_per_day = total_proximity / n

    anomalies = _evaluate_anomalies(avg_idle_pct, unsafe_per_day, proximity_per_day, total_unsafe, total_proximity)
    if avg_seatbelt < config.SEATBELT_COMPLIANCE_MIN_PCT:
        anomalies.append(AnomalyFlag(
            flag="Seatbelt Compliance Concern",
            severity="Warning" if avg_seatbelt >= 75 else "Critical",
            detail=f"Average seatbelt compliance is {avg_seatbelt:.1f}%, below the {config.SEATBELT_COMPLIANCE_MIN_PCT:.0f}% target.",
        ))

    return OperatorBehaviorReport(
        operator_id=operator_id,
        days_analyzed=n,
        avg_idle_pct=round(avg_idle_pct, 1),
        avg_seatbelt_compliance_pct=round(avg_seatbelt, 1),
        total_unsafe_events=int(total_unsafe),
        total_proximity_alerts=int(total_proximity),
        anomalies=anomalies,
    )

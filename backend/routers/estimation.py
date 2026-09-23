from fastapi import APIRouter, Depends, HTTPException

from backend import config
from backend.data_access.repository import DataRepositoryBase
from backend.dependencies import get_repository
from backend.schemas import TaskTimeEstimateOut, TaskTimeEstimateRequest

router = APIRouter(prefix="/estimation", tags=["Task Time Estimation"])


@router.post("/task-time", response_model=TaskTimeEstimateOut)
def estimate_task_time(
    request: TaskTimeEstimateRequest,
    repo: DataRepositoryBase = Depends(get_repository),
):
    """
    Predicts task duration.

    Strategy (simple + explainable, swap for a regression/ML model later
    without changing the API contract):
      1. Look up the exact historical benchmark for
         (task_type, environmental_condition, terrain_type).
      2. If there isn't enough history for that exact combination, fall back
         to the task type's overall average and apply environment/terrain
         multipliers instead.
    """
    exact = repo.get_duration_benchmark(
        request.task_type, request.environmental_condition, request.terrain_type
    )
    if exact and exact.get("sample_size", 0) >= 3:
        return TaskTimeEstimateOut(
            task_type=request.task_type,
            environmental_condition=request.environmental_condition,
            terrain_type=request.terrain_type,
            predicted_duration_min=exact["mean_duration_min"],
            confidence="High" if exact["sample_size"] >= 10 else "Medium",
            basis="Historical average for this exact task/condition/terrain combination.",
            sample_size=int(exact["sample_size"]),
        )

    baseline = repo.get_task_type_baseline(request.task_type)
    if baseline is None:
        raise HTTPException(status_code=404, detail="No historical data available for this task type")

    env_mult = config.ENV_DURATION_MULTIPLIER.get(request.environmental_condition, 1.0)
    terrain_mult = config.TERRAIN_DURATION_MULTIPLIER.get(request.terrain_type, 1.0)
    adjusted = round(baseline["mean_duration_min"] * env_mult * terrain_mult, 1)

    return TaskTimeEstimateOut(
        task_type=request.task_type,
        environmental_condition=request.environmental_condition,
        terrain_type=request.terrain_type,
        predicted_duration_min=adjusted,
        confidence="Low",
        basis="Task-type baseline adjusted by environment/terrain multipliers (insufficient exact-match history).",
        sample_size=int(baseline["sample_size"]),
    )

from datetime import datetime

from fastapi import APIRouter, Depends

from backend.data_access.repository import DataRepositoryBase
from backend.dependencies import get_repository
from backend.ml_models import TaskTimeModel, get_task_time_model
from backend.schemas import TaskTimeEstimateOut, TaskTimeEstimateRequest

router = APIRouter(prefix="/estimation", tags=["Task Time Estimation"])


@router.post("/task-time", response_model=TaskTimeEstimateOut)
def estimate_task_time(
    request: TaskTimeEstimateRequest,
    repo: DataRepositoryBase = Depends(get_repository),
    model: TaskTimeModel = Depends(get_task_time_model),
):
    """
    Predicts task duration with a RandomForestRegressor trained on
    historical tasks (task type, terrain, weather, operator experience,
    machine age/health - see ml/train_estimation_model.py).

    If `operator_id` / `machine_id` are supplied, their real experience/
    certification/age/health are looked up and fed to the model; otherwise
    the model falls back to dataset-wide medians for those features.

    The historical benchmark average for the exact (task_type,
    environmental_condition, terrain_type) combination is also returned
    alongside the prediction, purely as a sanity-check reference point -
    the model is the actual prediction.
    """
    features = {
        "task_type": request.task_type,
        "environmental_condition": request.environmental_condition,
        "terrain_type": request.terrain_type,
    }

    if request.operator_id:
        operator = repo.get_operator(request.operator_id)
        if operator:
            features["experience_years"] = operator.get("experience_years")
            features["certification_level"] = operator.get("certification_level")

    if request.machine_id:
        machine = repo.get_machine(request.machine_id)
        if machine:
            features["machine_type"] = machine.get("machine_type")
            features["machine_health_score"] = machine.get("health_score")
            if machine.get("year") is not None:
                features["machine_age_years"] = datetime.now().year - int(machine["year"])

    prediction = model.predict(features)

    benchmark = repo.get_duration_benchmark(
        request.task_type, request.environmental_condition, request.terrain_type
    )

    return TaskTimeEstimateOut(
        task_type=request.task_type,
        environmental_condition=request.environmental_condition,
        terrain_type=request.terrain_type,
        predicted_duration_min=prediction["predicted_duration_min"],
        confidence=prediction["confidence"],
        basis=(
            "RandomForestRegressor trained on historical tasks "
            f"(model holdout MAE: {model.meta['holdout_mae_min']} min, R^2: {model.meta['holdout_r2']})."
        ),
        benchmark_mean_min=benchmark.get("mean_duration_min") if benchmark else None,
        benchmark_sample_size=int(benchmark.get("sample_size", 0)) if benchmark else 0,
    )

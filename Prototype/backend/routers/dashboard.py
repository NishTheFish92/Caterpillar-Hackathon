from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.data_access.repository import DataRepositoryBase
from backend.dependencies import get_repository
from backend.schemas import TaskOut

router = APIRouter(prefix="/dashboard", tags=["Daily Task Dashboard"])


@router.get("/{operator_id}/tasks", response_model=list[TaskOut])
def get_today_tasks(
    operator_id: str,
    for_date: Optional[str] = None,
    repo: DataRepositoryBase = Depends(get_repository),
):
    """Scheduled tasks for an operator. Defaults to today if `for_date` omitted."""
    if repo.get_operator(operator_id) is None:
        raise HTTPException(status_code=404, detail="Operator not found")

    target_date = for_date or date.today().isoformat()
    tasks = repo.get_tasks_for_operator(operator_id, for_date=target_date)

    if not tasks:
        # Fall back to the most recent day with tasks so the demo isn't empty
        # when the synthetic data doesn't happen to include "today".
        all_tasks = repo.get_tasks_for_operator(operator_id)
        if all_tasks:
            latest_date = max(t["date"] for t in all_tasks)
            tasks = [t for t in all_tasks if t["date"] == latest_date]
    return tasks

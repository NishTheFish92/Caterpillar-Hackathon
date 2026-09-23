"""
Training hub: a small static catalog of learning content (mixing e-learning
videos, a simulation module, and instructor-led sessions) plus a simple
booking endpoint. In production the catalog would live in its own table/
service; kept as an in-memory list here to stay in scope for the template.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.data_access.repository import DataRepositoryBase
from backend.dependencies import get_repository
from backend.schemas import InstructorBookingCreate, InstructorBookingOut, TrainingModuleOut

router = APIRouter(prefix="/training", tags=["Training Hub"])

_MODULES = [
    {
        "module_id": "MOD-001",
        "title": "Excavator Safety Fundamentals",
        "format": "e-learning-video",
        "duration_min": 20,
        "skill_level": "Beginner",
        "description": "Pre-shift inspection, blind spots, and stable digging posture.",
    },
    {
        "module_id": "MOD-002",
        "title": "Proximity Hazard Awareness",
        "format": "e-learning-video",
        "duration_min": 15,
        "skill_level": "Beginner",
        "description": "Recognizing and responding to proximity detection alerts on active sites.",
    },
    {
        "module_id": "MOD-003",
        "title": "Grading on Uneven Terrain - VR Simulation",
        "format": "simulation",
        "duration_min": 40,
        "skill_level": "Intermediate",
        "description": "Hands-on simulator module practicing grading technique on rocky/muddy terrain.",
    },
    {
        "module_id": "MOD-004",
        "title": "Trenching & Excavation Safety - VR Simulation",
        "format": "simulation",
        "duration_min": 35,
        "skill_level": "Intermediate",
        "description": "Simulated trench collapse scenarios and safe spoil placement.",
    },
    {
        "module_id": "MOD-005",
        "title": "1:1 Advanced Operating Techniques",
        "format": "instructor-led",
        "duration_min": 60,
        "skill_level": "Advanced",
        "description": "Book time with a certified instructor for personalized coaching.",
    },
]

# In-memory bookings store; swap for a DB table in production.
_BOOKINGS: list[dict] = []
_booking_counter = 0


@router.get("/modules", response_model=list[TrainingModuleOut])
def list_modules(format: Optional[str] = None):
    if format:
        return [m for m in _MODULES if m["format"] == format]
    return _MODULES


@router.post("/book", response_model=InstructorBookingOut, status_code=201)
def book_session(
    booking: InstructorBookingCreate,
    repo: DataRepositoryBase = Depends(get_repository),
):
    global _booking_counter
    if repo.get_operator(booking.operator_id) is None:
        raise HTTPException(status_code=404, detail="Operator not found")
    if not any(m["module_id"] == booking.module_id for m in _MODULES):
        raise HTTPException(status_code=404, detail="Training module not found")

    _booking_counter += 1
    record = booking.model_dump()
    record["booking_id"] = f"BK-{_booking_counter:05d}"
    record["status"] = "Confirmed"
    _BOOKINGS.append(record)
    return record


@router.get("/bookings/{operator_id}", response_model=list[InstructorBookingOut])
def get_bookings(operator_id: str):
    return [b for b in _BOOKINGS if b["operator_id"] == operator_id]

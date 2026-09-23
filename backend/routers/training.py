"""
Training hub: an organized wiki of short articles operators can read at
their own pace, tiered by skill level, plus a lightweight instructor
booking flow for the handful of articles that are instructor-led sessions
rather than self-serve reading. Content is dummy/placeholder text - in
production this would live in a CMS; kept as an in-memory list here to
stay in scope for the hackathon build.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.data_access.repository import DataRepositoryBase
from backend.dependencies import get_repository
from backend.schemas import ArticleOut, InstructorBookingCreate, InstructorBookingOut

router = APIRouter(prefix="/training", tags=["Training Hub"])

_ARTICLES = [
    {
        "article_id": "ART-001",
        "title": "Safety Fundamentals: Pre-Shift Inspection",
        "category": "Safety",
        "format": "article",
        "skill_level": "Beginner",
        "read_time_min": 6,
        "summary": "The walk-around checklist every operator runs before starting a machine.",
        "content": (
            "Before starting any CAT machine, complete a full walk-around: check tire/track "
            "condition, fluid levels (engine oil, hydraulic, coolant), and look for leaks "
            "underneath the machine. Test the seatbelt buckle and retraction, confirm all "
            "mirrors and cameras are clean and adjusted, and verify the backup alarm sounds "
            "when reverse is engaged. Report anything unusual to your supervisor before "
            "starting the shift - a two-minute inspection prevents most on-site incidents "
            "before they happen."
        ),
    },
    {
        "article_id": "ART-002",
        "title": "Proximity Hazard Awareness",
        "category": "Safety",
        "format": "e-learning-video",
        "skill_level": "Beginner",
        "read_time_min": 12,
        "summary": "Recognizing and responding to proximity detection alerts on active sites.",
        "content": (
            "Proximity alerts fire when the machine's sensors detect a person, vehicle, or "
            "obstacle inside the configured safety radius. On alert: stop all machine "
            "movement immediately, sound the horn, and visually confirm the area is clear "
            "before resuming. Never override or silence a proximity alert to 'work faster' - "
            "alerts near blind spots (rear-swing radius, behind the counterweight) are the "
            "leading cause of struck-by incidents on active sites. If alerts are firing "
            "frequently in a low-traffic area, report it - it may mean a sensor needs "
            "recalibration, not that it's safe to ignore."
        ),
    },
    {
        "article_id": "ART-003",
        "title": "Seatbelt & PPE Compliance",
        "category": "Safety",
        "format": "article",
        "skill_level": "Beginner",
        "read_time_min": 4,
        "summary": "Why seatbelt compliance is tracked and non-negotiable, every shift.",
        "content": (
            "The seatbelt is your primary rollover protection - the cab's ROPS structure "
            "only works if you're restrained inside it. Buckle in before releasing the "
            "parking brake, every time, for every task, regardless of duration. Hard hats, "
            "high-visibility vests, and steel-toe boots are required whenever you're outside "
            "the cab. Seatbelt status is logged continuously; compliance below site targets "
            "triggers a review, not as a punishment, but because it's the single strongest "
            "predictor of injury severity when an incident does occur."
        ),
    },
    {
        "article_id": "ART-004",
        "title": "Understanding Your Dashboard: Alerts & Telemetry",
        "category": "Operations",
        "format": "article",
        "skill_level": "Beginner",
        "read_time_min": 5,
        "summary": "What the dashboard, safety, and behavior screens are actually telling you.",
        "content": (
            "The Daily Dashboard shows your scheduled tasks for the shift - site, machine, "
            "terrain, and expected conditions. The Safety tab reflects real-time sensor "
            "state (seatbelt, proximity) plus a forward-looking hazard prediction for the "
            "next few minutes. The Unusual Behavior report is a weekly-style rollup, not a "
            "per-minute score - a single flagged day usually means a specific task ran long "
            "or had more idling than usual, not that something is systemically wrong. Use it "
            "as a coaching signal, not a scoreboard."
        ),
    },
    {
        "article_id": "ART-005",
        "title": "Grading on Uneven Terrain",
        "category": "Operating Technique",
        "format": "simulation",
        "skill_level": "Intermediate",
        "read_time_min": 40,
        "summary": "Hands-on simulator module practicing grading technique on rocky/muddy terrain.",
        "content": (
            "This simulation places you on a mixed rocky/muddy grading site and scores blade "
            "control, pass overlap, and slope consistency. Rocky terrain rewards slower, "
            "shallower passes over aggressive single-pass grading - forcing the blade "
            "increases both fuel burn and undercarriage wear. On muddy terrain, watch for "
            "track slip; reduce throttle before you lose traction rather than after. Complete "
            "the module's three site scenarios to unlock the assessment score, which factors "
            "into your certification tier review."
        ),
    },
    {
        "article_id": "ART-006",
        "title": "Trenching & Excavation Safety",
        "category": "Safety",
        "format": "simulation",
        "skill_level": "Intermediate",
        "read_time_min": 35,
        "summary": "Simulated trench collapse scenarios and safe spoil placement.",
        "content": (
            "Trench walls fail more often than operators expect, especially after rain "
            "saturates soil. This module simulates progressive wall failure so you can "
            "practice reading warning signs (tension cracks, slight bulging, water seepage) "
            "before they become a collapse. Spoil piles must be set back at least the trench "
            "depth from the edge - stacking material close to the edge is one of the most "
            "common causes of secondary collapse during excavation work."
        ),
    },
    {
        "article_id": "ART-007",
        "title": "Fuel-Efficient Operation Techniques",
        "category": "Operating Technique",
        "format": "article",
        "skill_level": "Intermediate",
        "read_time_min": 8,
        "summary": "Idling costs more than most operators think - practical habits that cut it down.",
        "content": (
            "Every minute of unnecessary idling burns fuel and adds engine hours without "
            "moving material. Shut down rather than idle for waits longer than ~3 minutes. "
            "Match engine RPM to the task instead of running at max RPM by default - most "
            "grading and loading work doesn't need it. Plan approach paths to minimize "
            "repositioning; each unnecessary reverse-and-realign cycle adds both time and "
            "idle minutes to a task that should be a single clean pass."
        ),
    },
    {
        "article_id": "ART-008",
        "title": "Hydraulic System Basics",
        "category": "Maintenance",
        "format": "article",
        "skill_level": "Intermediate",
        "read_time_min": 7,
        "summary": "Reading hydraulic pressure signals and knowing when to flag a machine for service.",
        "content": (
            "Normal operating hydraulic pressure sits in a healthy band for each machine "
            "type - sustained readings well outside that band usually mean a developing "
            "seal or pump issue, not a one-off spike. Sluggish or jerky attachment movement, "
            "unusual heat off the hydraulic lines, or visible fluid around fittings are all "
            "signs to flag the machine for service rather than 'wait and see' - a small "
            "hydraulic leak caught early is a fitting replacement; caught late, it's a pump "
            "rebuild."
        ),
    },
    {
        "article_id": "ART-009",
        "title": "Emergency Response Procedures",
        "category": "Safety",
        "format": "article",
        "skill_level": "All Levels",
        "read_time_min": 6,
        "summary": "What to do in the first 60 seconds after an incident, before anything else.",
        "content": (
            "Stop the machine and shut down if it's safe to do so. Assess for immediate "
            "danger to yourself and others before approaching. Call site emergency contacts "
            "first - not your supervisor, not a text message. Do not move an injured person "
            "unless they're in immediate further danger. Log the incident through the Safety "
            "tab as soon as it's safe to do so; timely, accurate incident logs are what let "
            "the site fix the underlying hazard instead of it happening again."
        ),
    },
    {
        "article_id": "ART-010",
        "title": "1:1 Advanced Operating Techniques",
        "category": "Operating Technique",
        "format": "instructor-led",
        "skill_level": "Advanced",
        "read_time_min": 60,
        "summary": "Book time with a certified instructor for personalized coaching.",
        "content": (
            "A 60-minute 1:1 session with a certified instructor, built around your own "
            "recent task history - bring specific scenarios you want to work through "
            "(tight-clearance grading, complex multi-machine coordination, difficult terrain "
            "you've hit on site). This is coaching, not certification testing; come with "
            "questions rather than expecting a scripted curriculum. Book a slot below."
        ),
    },
    {
        "article_id": "ART-011",
        "title": "Site Communication Protocols",
        "category": "Operations",
        "format": "article",
        "skill_level": "All Levels",
        "read_time_min": 5,
        "summary": "Standard radio calls and hand signals for coordinating with ground crew.",
        "content": (
            "Confirm ground crew are clear before any swing or reverse move - a radio call "
            "and a visual check, not one or the other. Standard hand signals (stop, swing "
            "left/right, raise/lower, all-clear) should be used even when radios are in use, "
            "since radio traffic can be missed in noisy conditions. If you lose visual or "
            "radio contact with ground crew mid-task, stop and re-establish contact before "
            "continuing - never assume their position hasn't changed."
        ),
    },
    {
        "article_id": "ART-012",
        "title": "Machine Health Alerts, Explained",
        "category": "Maintenance",
        "format": "e-learning-video",
        "skill_level": "All Levels",
        "read_time_min": 10,
        "summary": "What a machine health score is built from, and what to do when it drops.",
        "content": (
            "A machine's health score factors in age, lifetime engine hours, and days since "
            "last service - it's a leading indicator, not a fault code. A dropping score "
            "doesn't mean stop work immediately; it means the machine is statistically more "
            "likely to need attention soon, which shows up elsewhere too (slightly longer "
            "task times, more sensitivity to rough terrain). Flag persistently low-health "
            "machines for a service slot rather than waiting for an actual breakdown."
        ),
    },
]

# In-memory bookings store; swap for a DB table in production.
_BOOKINGS: list[dict] = []
_booking_counter = 0


@router.get("/articles", response_model=list[ArticleOut])
def list_articles(
    skill_level: Optional[str] = None,
    category: Optional[str] = None,
    format: Optional[str] = None,
):
    articles = _ARTICLES
    if skill_level:
        articles = [a for a in articles if a["skill_level"] in (skill_level, "All Levels")]
    if category:
        articles = [a for a in articles if a["category"] == category]
    if format:
        articles = [a for a in articles if a["format"] == format]
    return articles


@router.get("/articles/{article_id}", response_model=ArticleOut)
def get_article(article_id: str):
    for article in _ARTICLES:
        if article["article_id"] == article_id:
            return article
    raise HTTPException(status_code=404, detail="Article not found")


@router.post("/book", response_model=InstructorBookingOut, status_code=201)
def book_session(
    booking: InstructorBookingCreate,
    repo: DataRepositoryBase = Depends(get_repository),
):
    global _booking_counter
    if repo.get_operator(booking.operator_id) is None:
        raise HTTPException(status_code=404, detail="Operator not found")
    if not any(a["article_id"] == booking.article_id for a in _ARTICLES):
        raise HTTPException(status_code=404, detail="Article not found")

    _booking_counter += 1
    record = booking.model_dump()
    record["booking_id"] = f"BK-{_booking_counter:05d}"
    record["status"] = "Confirmed"
    _BOOKINGS.append(record)
    return record


@router.get("/bookings/{operator_id}", response_model=list[InstructorBookingOut])
def get_bookings(operator_id: str):
    return [b for b in _BOOKINGS if b["operator_id"] == operator_id]

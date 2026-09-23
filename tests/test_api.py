import json

from fastapi.testclient import TestClient

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.main import app

client = TestClient(app)


def show(label, resp):
    print(f"\n=== {label} [{resp.status_code}] ===")
    try:
        data = resp.json()
        print(json.dumps(data, indent=2)[:1200])
    except Exception:
        print(resp.text[:500])


show("health", client.get("/health"))
show("dashboard OP-001 tasks", client.get("/dashboard/OP-001/tasks"))

show("seatbelt MC-005", client.get("/safety/seatbelt/MC-005"))
show("proximity MC-005", client.get("/safety/proximity/MC-005"))
show("active proximity alerts", client.get("/safety/proximity"))
show("hazard prediction MC-005", client.get("/safety/hazard-prediction/MC-005"))
show("log incident", client.post("/safety/incidents", json={
    "operator_id": "OP-003", "machine_id": "MC-002", "incident_type": "Near-Miss",
    "severity": "Medium", "description": "Pedestrian near swing radius"
}))
show("list incidents", client.get("/safety/incidents"))

show("training articles", client.get("/training/articles"))
show("training articles - beginner only", client.get("/training/articles?skill_level=Beginner"))
show("training single article", client.get("/training/articles/ART-005"))
show("book training", client.post("/training/book", json={
    "operator_id": "OP-001", "article_id": "ART-010",
    "preferred_datetime": "2026-09-25T10:00:00", "notes": "Grading technique"
}))

# Seeded risky operators: OP-002, OP-007, OP-011 (excessive idling / unsafe speed)
# Seeded seatbelt offenders: OP-004, OP-009
show("behavior anomalies - RISKY operator OP-002", client.get("/behavior/OP-002/anomalies?days=21"))
show("behavior anomalies - SEATBELT offender OP-004", client.get("/behavior/OP-004/anomalies?days=21"))
show("behavior anomalies - NORMAL operator OP-001", client.get("/behavior/OP-001/anomalies?days=21"))

show("task-time estimate (no operator/machine context)", client.post("/estimation/task-time", json={
    "task_type": "Excavation", "environmental_condition": "Clear", "terrain_type": "Hard Soil"
}))
show("task-time estimate (with operator/machine context)", client.post("/estimation/task-time", json={
    "task_type": "Demolition", "environmental_condition": "Dust Storm", "terrain_type": "Muddy",
    "operator_id": "OP-001", "machine_id": "MC-001",
}))

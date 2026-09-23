"""
main.py
-------
Smart Operator Assistant - FastAPI backend entrypoint.

Run (from the project root, one level above `backend/`):
    uvicorn backend.main:app --reload --port 8000

Then open http://127.0.0.1:8000/docs for interactive Swagger UI covering
every endpoint below.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import behavior, dashboard, estimation, safety, training

app = FastAPI(
    title="CAT Smart Operator Assistant API",
    description=(
        "Backend for the operator-facing app: daily task dashboard, "
        "real-time safety monitoring, a training hub, machine-usage "
        "anomaly detection, and task time estimation."
    ),
    version="0.1.0",
)

# Wide-open CORS for the prototype/template stage; scope this down per
# environment (mobile app origin, in-cab tablet origin, etc.) in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(safety.router)
app.include_router(training.router)
app.include_router(behavior.router)
app.include_router(estimation.router)


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "cat-smart-operator-assistant"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}

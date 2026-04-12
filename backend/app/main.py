import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings, validate_startup
from app.routes import (
    ai,
    allowance,
    auth,
    calendar,
    chores,
    daily_wins,
    dashboard,
    families,
    finance,
    grocery,
    health_fitness,
    integrations,
    meals,
    notes,
    personal_tasks,
    routines,
    task_instances,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("scout")


@asynccontextmanager
async def lifespan(app: FastAPI):
    warnings = validate_startup()
    for w in warnings:
        logger.warning(w)
    logger.info("Scout backend started")
    yield
    logger.info("Scout backend shutting down")


app = FastAPI(title="Scout", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(families.router)
app.include_router(routines.router)
app.include_router(chores.router)
app.include_router(task_instances.router)
app.include_router(daily_wins.router)
app.include_router(allowance.router)
app.include_router(calendar.router)
app.include_router(meals.router)
app.include_router(personal_tasks.router)
app.include_router(notes.router)
app.include_router(finance.router)
app.include_router(health_fitness.router)
app.include_router(integrations.router)
app.include_router(grocery.router)
app.include_router(dashboard.router)
app.include_router(ai.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness check: app booted, database reachable, config loaded."""
    from sqlalchemy import func, select as sa_select, text
    from app.database import SessionLocal
    from app.models.foundation import UserAccount
    db = None
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        account_count = db.scalar(sa_select(func.count()).select_from(UserAccount)) or 0
    except Exception as e:
        return {"status": "not_ready", "reason": f"database: {e}"}
    finally:
        if db:
            db.close()

    return {
        "status": "ready",
        "auth_required": settings.auth_required,
        "bootstrap_enabled": settings.enable_bootstrap,
        "accounts_exist": account_count > 0,
        "ai_available": settings.ai_available,
        "meal_generation": settings.enable_meal_generation,
    }

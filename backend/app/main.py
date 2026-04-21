import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings, validate_startup
from app.database import SessionLocal
from app.routes import (
    affirmations,
    ai,
    allowance,
    auth,
    calendar,
    canonical,
    chores,
    client_errors,
    daily_wins,
    dashboard,
    families,
    finance,
    grocery,
    health_fitness,
    integrations,
    mcp_http,
    meals,
    memory as memory_routes,
    notes,
    personal_tasks,
    routines,
    home_maintenance,
    storage,
    task_instances,
)
from app.routes.admin import config as admin_config
from app.routes.admin import permissions as admin_permissions
from app.routes.admin import chores as admin_chores
from app.routes.admin import allowance as admin_allowance
from app.routes.admin import integrations as admin_integrations
from app.routes.admin import affirmations as admin_affirmations

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

    scheduler = None
    # Start the proactive-jobs scheduler unless explicitly disabled.
    # Disabled by default during pytest (SCOUT_ENVIRONMENT=test) and
    # when SCOUT_SCHEDULER_ENABLED=false. The job runners themselves
    # stay importable and directly-callable for tests.
    if os.environ.get("SCOUT_SCHEDULER_ENABLED", "true").lower() != "false":
        try:
            from app.scheduler import start_scheduler
            scheduler = start_scheduler(lambda: SessionLocal())
            logger.info("Scout backend started (scheduler=on)")
        except Exception as e:
            logger.error("scheduler_start_failed: %s", str(e)[:200])
            logger.info("Scout backend started (scheduler=off)")
    else:
        logger.info("Scout backend started (scheduler=off)")

    yield
    logger.info("Scout backend shutting down")
    if scheduler is not None:
        try:
            from app.scheduler import stop_scheduler
            stop_scheduler()
        except Exception:
            pass


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
app.include_router(home_maintenance.router)
app.include_router(dashboard.router)
app.include_router(ai.router)
app.include_router(storage.router)
app.include_router(client_errors.router)
app.include_router(memory_routes.router)
app.include_router(mcp_http.router)
app.include_router(canonical.router)
app.include_router(affirmations.router)
app.include_router(admin_permissions.router)
app.include_router(admin_config.router)
app.include_router(admin_chores.router)
app.include_router(admin_allowance.router)
app.include_router(admin_integrations.router)
app.include_router(admin_affirmations.router)


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
        "environment": settings.environment,
        "auth_required": settings.auth_required,
        "bootstrap_enabled": settings.enable_bootstrap,
        "accounts_exist": account_count > 0,
        "ai_available": settings.ai_available,
        "transcribe_available": settings.transcribe_available,
        "meal_generation": settings.enable_meal_generation,
    }

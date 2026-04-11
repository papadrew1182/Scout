from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import (
    ai,
    allowance,
    calendar,
    chores,
    daily_wins,
    families,
    finance,
    health_fitness,
    integrations,
    meals,
    notes,
    personal_tasks,
    routines,
    task_instances,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Scout", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8081", "http://localhost:19006"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(ai.router)


@app.get("/health")
def health():
    return {"status": "ok"}

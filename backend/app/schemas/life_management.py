import uuid
from datetime import date, datetime, time

from pydantic import BaseModel


# --- Routine ---

class RoutineCreate(BaseModel):
    family_member_id: uuid.UUID
    name: str
    block: str
    recurrence: str = "daily"
    due_time_weekday: time
    due_time_weekend: time | None = None


class RoutineRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    family_member_id: uuid.UUID
    name: str
    block: str
    recurrence: str
    due_time_weekday: time
    due_time_weekend: time | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- RoutineStep ---

class RoutineStepCreate(BaseModel):
    name: str
    sort_order: int


class RoutineStepRead(BaseModel):
    id: uuid.UUID
    routine_id: uuid.UUID
    name: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RoutineWithStepsRead(RoutineRead):
    steps: list[RoutineStepRead] = []


# --- ChoreTemplate ---

class ChoreTemplateCreate(BaseModel):
    name: str
    description: str | None = None
    recurrence: str = "daily"
    due_time: time
    assignment_type: str
    assignment_rule: dict = {}


class ChoreTemplateRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    name: str
    description: str | None
    recurrence: str
    due_time: time
    assignment_type: str
    assignment_rule: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- TaskInstance ---

class TaskInstanceRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    family_member_id: uuid.UUID
    routine_id: uuid.UUID | None
    chore_template_id: uuid.UUID | None
    instance_date: date
    due_at: datetime
    is_completed: bool
    completed_at: datetime | None
    override_completed: bool | None
    override_by: uuid.UUID | None
    override_note: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskInstanceComplete(BaseModel):
    completed_at: datetime | None = None


class TaskInstanceOverride(BaseModel):
    override_completed: bool
    override_by: uuid.UUID
    override_note: str | None = None


# --- StepCompletion ---

class StepCompletionRead(BaseModel):
    id: uuid.UUID
    task_instance_id: uuid.UUID
    routine_step_id: uuid.UUID
    is_completed: bool
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class StepCompletionUpdate(BaseModel):
    is_completed: bool
    completed_at: datetime | None = None


# --- DailyWin ---

class DailyWinRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    family_member_id: uuid.UUID
    win_date: date
    is_win: bool
    task_count: int
    completed_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- AllowanceLedger ---

class AllowanceLedgerRead(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    family_member_id: uuid.UUID
    entry_type: str
    amount_cents: int
    week_start: date | None
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AllowanceLedgerCreate(BaseModel):
    family_member_id: uuid.UUID
    entry_type: str
    amount_cents: int
    week_start: date | None = None
    note: str | None = None


class WeeklyPayoutRequest(BaseModel):
    week_start: date


class BalanceRead(BaseModel):
    family_member_id: uuid.UUID
    balance_cents: int

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.life_management import DailyWinRead
from app.services import daily_win_service

router = APIRouter(prefix="/families/{family_id}/daily-wins", tags=["daily-wins"])


@router.get("", response_model=list[DailyWinRead])
def list_daily_wins(
    family_id: uuid.UUID,
    member_id: uuid.UUID | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db: Session = Depends(get_db),
):
    return daily_win_service.list_daily_wins(db, family_id, member_id, start_date, end_date)


@router.post("/compute", response_model=list[DailyWinRead], status_code=201)
def compute_daily_wins(
    family_id: uuid.UUID,
    win_date: date = Query(...),
    db: Session = Depends(get_db),
):
    return daily_win_service.compute_for_family_date(db, family_id, win_date)

"""Kid-specific homework detection + session tracking.

Runs on every child chat turn (after moderation, before the
orchestrator calls the model). Cheap: deterministic keyword + regex
classifier, no extra AI call. When a turn looks like homework, upserts
a row in ``ai_homework_sessions`` so parents can see a weekly rollup
on their dashboard.

Subject taxonomy matches migration 018's CHECK:
    math | reading | writing | science | history | language | other

Session stitching rule: a turn within 30 minutes of the same
conversation's most recent OPEN homework row extends that row
(turn_count += 1, ended_at = now). Otherwise a new row is opened.
Sessions close on the next non-homework turn or after a 2-hour
idle timeout enforced at read time (not runtime).
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pytz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.foundation import FamilyMember
from app.models.homework import HomeworkSession

logger = logging.getLogger("scout.ai.homework")

SESSION_STITCH_MINUTES = 30
VALID_SUBJECTS = {"math", "reading", "writing", "science", "history", "language", "other"}


@dataclass
class HomeworkClassification:
    is_homework: bool
    subject: str       # one of VALID_SUBJECTS; "other" when is_homework is False
    confidence: float  # 0.0..1.0, rough


# --- Classifier patterns -------------------------------------------------
# Keywords / phrases per subject. Any hit marks the turn as homework AND
# tags it with the matched subject. Math is also matched by inline
# arithmetic expressions so "what is 2+2" is detected.

_SUBJECT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "math",
        re.compile(
            r"\b(math|algebra|geometry|arithmetic|fraction|fractions|"
            r"divide|dividing|multiply|multiplying|multiplication|"
            r"division|subtract|subtracting|add|adding|equation|equations|"
            r"solve for|numerator|denominator|percent|percentage|decimal|"
            r"long division|word problem|homework math)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "math",
        # Inline arithmetic expressions like "2 + 2" or "15 - 7"
        re.compile(r"\b\d+\s*[\+\-\*/x×÷]\s*\d+\b"),
    ),
    (
        "reading",
        re.compile(
            r"\b(reading|read a book|book report|chapter|chapters|"
            r"summary of|main character|plot|theme|author|library book|"
            r"reading log|what is .* about)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "writing",
        re.compile(
            r"\b(essay|paragraph|outline|thesis|write about|narrative|"
            r"writing assignment|story for school|compare and contrast|"
            r"persuasive|grammar|spelling|vocabulary word|vocab word)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "science",
        re.compile(
            r"\b(science|biology|chemistry|physics|photosynthesis|"
            r"atom|atoms|molecule|cell|cells|gravity|ecosystem|"
            r"experiment|lab report|solar system|planets|evolution|"
            r"plant cycle|water cycle|weather cycle|force|energy)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "history",
        re.compile(
            r"\b(history|ancient|medieval|civil war|world war|"
            r"president|presidents|revolution|civil rights|colony|"
            r"colonies|founding fathers|constitution|bill of rights)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "language",
        re.compile(
            r"\b(spanish|french|german|latin|chinese|translate|"
            r"conjugate|verb tense|present tense|past tense|"
            r"vocabulary in|in spanish|in french|how do you say)\b",
            re.IGNORECASE,
        ),
    ),
]

# Generic homework framing — if the message mentions "homework" or
# "assignment" without a subject match, we still mark it as homework
# and classify it as "other".
_GENERIC_HOMEWORK = re.compile(
    r"\b(homework|my assignment|my worksheet|my packet|"
    r"for school|help me with|explain to me|teach me|"
    r"how do (i|you) (do|solve|figure out))\b",
    re.IGNORECASE,
)


def classify_homework(message: str) -> HomeworkClassification:
    """Deterministic homework classifier. Returns is_homework + subject."""
    if not message or not message.strip():
        return HomeworkClassification(False, "other", 0.0)

    text = message.strip()

    for subject, rx in _SUBJECT_PATTERNS:
        if rx.search(text):
            return HomeworkClassification(True, subject, 0.8)

    if _GENERIC_HOMEWORK.search(text):
        return HomeworkClassification(True, "other", 0.5)

    return HomeworkClassification(False, "other", 0.0)


# --- Session upsert -------------------------------------------------------


def record_homework_turn(
    db: Session,
    *,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    message: str,
    role: str,
    surface: str,
) -> HomeworkSession | None:
    """Classify a child chat turn and, if it's homework, extend or
    create a HomeworkSession row. Returns the row or None.

    Runs ONLY when the actor is on the child surface (child role or
    child surface). Adults asking homework-shaped questions do NOT
    create rows — this is a kid-specific feature.

    Transaction-neutral: caller commits.
    """
    is_child = role == "child" or surface == "child"
    if not is_child:
        return None
    if conversation_id is None:
        return None

    cls = classify_homework(message)
    if not cls.is_homework:
        return None

    now = datetime.now(pytz.UTC)
    stitch_cutoff = now - timedelta(minutes=SESSION_STITCH_MINUTES)

    # Find an open session for this conversation that started recently
    recent = db.scalars(
        select(HomeworkSession)
        .where(HomeworkSession.conversation_id == conversation_id)
        .where(HomeworkSession.member_id == member_id)
        .where(HomeworkSession.started_at >= stitch_cutoff)
        .order_by(HomeworkSession.started_at.desc())
        .limit(1)
    ).first()

    if recent is not None:
        recent.turn_count = (recent.turn_count or 1) + 1
        recent.ended_at = now
        if recent.session_length_sec is None:
            recent.session_length_sec = 0
        delta = (now - recent.started_at).total_seconds()
        recent.session_length_sec = int(delta)
        db.flush()
        logger.info(
            "homework_session_extended member=%s conv=%s subject=%s turns=%d",
            member_id, conversation_id, recent.subject, recent.turn_count,
        )
        return recent

    # Capture grade_level_at_time from the current member state
    grade = None
    mem = db.get(FamilyMember, member_id)
    if mem is not None:
        grade = mem.grade_level

    session = HomeworkSession(
        family_id=family_id,
        member_id=member_id,
        conversation_id=conversation_id,
        subject=cls.subject,
        grade_level_at_time=grade,
        started_at=now,
        ended_at=now,
        turn_count=1,
        session_length_sec=0,
    )
    db.add(session)
    db.flush()
    logger.info(
        "homework_session_opened member=%s conv=%s subject=%s",
        member_id, conversation_id, cls.subject,
    )
    return session


# --- Parent dashboard rollup ---------------------------------------------


def homework_summary(
    db: Session, *, family_id: uuid.UUID, days: int = 7
) -> dict[str, Any]:
    """Parent-facing rollup: per-child counts and subject distribution
    over the last N days. No raw session content returned."""
    since = datetime.now(pytz.UTC) - timedelta(days=days)

    rows = list(db.scalars(
        select(HomeworkSession)
        .where(HomeworkSession.family_id == family_id)
        .where(HomeworkSession.started_at >= since)
        .order_by(HomeworkSession.started_at.desc())
    ).all())

    # Build per-child rollup
    by_child: dict[str, dict[str, Any]] = {}
    for r in rows:
        key = str(r.member_id)
        slot = by_child.setdefault(
            key,
            {
                "member_id": key,
                "sessions": 0,
                "subjects": {},
                "last_at": None,
            },
        )
        slot["sessions"] += 1
        slot["subjects"][r.subject] = slot["subjects"].get(r.subject, 0) + 1
        if slot["last_at"] is None or (r.started_at and r.started_at > slot["last_at"]):
            slot["last_at"] = r.started_at

    # Attach first_name
    member_ids = [uuid.UUID(k) for k in by_child.keys()]
    if member_ids:
        members = {
            str(m.id): m.first_name
            for m in db.scalars(
                select(FamilyMember).where(FamilyMember.id.in_(member_ids))
            ).all()
        }
        for key, slot in by_child.items():
            slot["first_name"] = members.get(key, "?")
            slot["last_at"] = slot["last_at"].isoformat() if slot["last_at"] else None

    return {
        "days": days,
        "total_sessions": len(rows),
        "children": list(by_child.values()),
    }

"""Chore template schema-expansion tests (Batch 2 PR 1b).

The Phase 3 scope-contract columns (included, not_included,
done_means_done) plus supplies, photo_example_url,
estimated_duration_minutes, and consequence_on_miss have been on the
SQLAlchemy model since that phase shipped, but were not exposed
through the ChoreTemplateCreate / ChoreTemplateRead schemas. Batch 2
PR 1b adds them to both sides. These tests pin the round-trip so a
future silent schema narrowing would fail here.
"""

from __future__ import annotations

from datetime import time

import pytest
from sqlalchemy.orm import Session

from app.models.foundation import Family
from app.schemas.life_management import (
    ChoreTemplateCreate,
    ChoreTemplateRead,
)
from app.services import chore_service


def test_create_chore_template_defaults_new_fields_when_omitted(
    db: Session, family: Family
):
    """Callers who POST without the new fields still get a valid row.
    The lists default to empty arrays; the optional strings and int
    default to None. Matches the SQLAlchemy model defaults so existing
    callers continue to work after the schema expansion."""
    payload = ChoreTemplateCreate(
        name="Take out trash",
        description=None,
        recurrence="daily",
        due_time=time(18, 0),
        assignment_type="fixed",
        assignment_rule={},
    )

    created = chore_service.create_chore_template(db, family.id, payload)

    assert created.included == []
    assert created.not_included == []
    assert created.supplies == []
    assert created.done_means_done is None
    assert created.photo_example_url is None
    assert created.estimated_duration_minutes is None
    assert created.consequence_on_miss is None


def test_create_chore_template_persists_scope_contract_fields(
    db: Session, family: Family
):
    """Scope-contract fields supplied at create time persist through
    the service and round-trip through ChoreTemplateRead."""
    payload = ChoreTemplateCreate(
        name="Clean bedroom",
        description="Weekly deep-clean of the bedroom.",
        recurrence="weekly",
        due_time=time(17, 0),
        assignment_type="fixed",
        assignment_rule={},
        included=[
            "Make bed",
            "Vacuum floor",
            "Empty trash",
        ],
        not_included=[
            "Wash windows (handled by parents)",
            "Dust baseboards (handled by parents)",
        ],
        done_means_done=(
            "Bed made with pillows stacked, floor clear of clutter, "
            "trash bag tied and in the hallway."
        ),
        supplies=["Vacuum", "Trash bag"],
        photo_example_url="https://example.test/bedroom-clean.jpg",
        estimated_duration_minutes=25,
        consequence_on_miss="Skip allowance for the week.",
    )

    created = chore_service.create_chore_template(db, family.id, payload)

    assert created.included == [
        "Make bed",
        "Vacuum floor",
        "Empty trash",
    ]
    assert created.not_included == [
        "Wash windows (handled by parents)",
        "Dust baseboards (handled by parents)",
    ]
    assert "Bed made with pillows stacked" in (created.done_means_done or "")
    assert created.supplies == ["Vacuum", "Trash bag"]
    assert created.photo_example_url == (
        "https://example.test/bedroom-clean.jpg"
    )
    assert created.estimated_duration_minutes == 25
    assert created.consequence_on_miss == "Skip allowance for the week."

    # Round-trip through the response schema.
    dumped = ChoreTemplateRead.model_validate(created).model_dump()
    assert dumped["included"] == [
        "Make bed",
        "Vacuum floor",
        "Empty trash",
    ]
    assert dumped["estimated_duration_minutes"] == 25
    assert dumped["photo_example_url"] == (
        "https://example.test/bedroom-clean.jpg"
    )


def test_chore_template_create_accepts_empty_lists_explicitly(
    db: Session, family: Family
):
    """Explicit empty lists at create time match the omit-field
    default. Both paths produce the same row shape."""
    payload = ChoreTemplateCreate(
        name="Simple chore",
        recurrence="daily",
        due_time=time(8, 0),
        assignment_type="fixed",
        assignment_rule={},
        included=[],
        not_included=[],
        supplies=[],
    )

    created = chore_service.create_chore_template(db, family.id, payload)

    assert created.included == []
    assert created.not_included == []
    assert created.supplies == []


def test_photo_example_url_stores_path_not_signed_url(
    db: Session, family: Family
):
    """The photo_example_url column holds a Supabase Storage PATH
    after Batch 2 PR 1b. Signed URLs expire in 1 hour, so persisting
    one would break the photo within the hour. The form captures the
    path from /api/storage/upload's response and saves THAT; render-
    side consumers resolve path -> fresh signed URL via
    GET /api/storage/signed-url.

    This test pins the contract: the value we persist is a path, not
    a URL, so a future change that accidentally stores a signed URL
    would be visible.
    """
    payload = ChoreTemplateCreate(
        name="Dust shelves",
        recurrence="weekly",
        due_time=time(17, 0),
        assignment_type="fixed",
        assignment_rule={},
        photo_example_url=(
            "fbe71860-a1a2-42b0-a0b5-df72017ced7c/"
            "b684226c-1217-44ca-84d0-3bf7c4ea4e82/"
            "2026-04-22/dusting_example.jpg"
        ),
    )

    created = chore_service.create_chore_template(db, family.id, payload)

    # Stored verbatim; path-shape not URL-shape.
    assert created.photo_example_url is not None
    assert not created.photo_example_url.startswith("http")
    assert "/2026-04-22/" in created.photo_example_url
    assert created.photo_example_url.endswith(".jpg")

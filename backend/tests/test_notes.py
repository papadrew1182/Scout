"""Tests for notes_service.

Covers:
- create / read / update / delete
- title-not-blank constraint
- list filters (member, category, archive visibility)
- recent ordering by updated_at desc
- ILIKE search across title + body
- archive / unarchive
- tenant isolation
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.foundation import Family, FamilyMember
from app.schemas.notes import NoteCreate, NoteUpdate
from app.services.notes_service import (
    archive_note,
    create_note,
    delete_note,
    get_note,
    list_notes,
    list_recent_notes,
    search_notes,
    unarchive_note,
    update_note,
)


class TestCreate:
    def test_create_basic(self, db: Session, family, adults):
        andrew = adults["robert"]
        note = create_note(
            db, family.id,
            NoteCreate(
                family_member_id=andrew.id,
                title="Strategic priorities",
                body="Q2 priorities",
                category="work",
            ),
        )
        assert note.id is not None
        assert note.title == "Strategic priorities"
        assert note.body == "Q2 priorities"
        assert note.category == "work"
        assert note.is_archived is False

    def test_create_minimal(self, db: Session, family, adults):
        note = create_note(
            db, family.id,
            NoteCreate(family_member_id=adults["robert"].id, title="Minimal"),
        )
        assert note.body == ""
        assert note.category is None

    def test_blank_title_rejected(self, db: Session, family, adults):
        with pytest.raises(IntegrityError):
            create_note(
                db, family.id,
                NoteCreate(family_member_id=adults["robert"].id, title="   "),
            )

    def test_assignee_must_be_in_family(self, db: Session, family):
        other = Family(name="Other", timezone="America/New_York")
        db.add(other)
        db.flush()
        other_member = FamilyMember(
            family_id=other.id, first_name="Stranger", role="adult"
        )
        db.add(other_member)
        db.flush()

        with pytest.raises(HTTPException) as exc:
            create_note(
                db, family.id,
                NoteCreate(family_member_id=other_member.id, title="Bad"),
            )
        assert exc.value.status_code == 404


class TestUpdateAndDelete:
    def test_update(self, db: Session, family, adults):
        note = create_note(
            db, family.id,
            NoteCreate(family_member_id=adults["robert"].id, title="Original"),
        )
        updated = update_note(
            db, family.id, note.id,
            NoteUpdate(title="Renamed", body="New body"),
        )
        assert updated.title == "Renamed"
        assert updated.body == "New body"

    def test_delete(self, db: Session, family, adults):
        note = create_note(
            db, family.id,
            NoteCreate(family_member_id=adults["robert"].id, title="Doomed"),
        )
        delete_note(db, family.id, note.id)
        with pytest.raises(HTTPException) as exc:
            get_note(db, family.id, note.id)
        assert exc.value.status_code == 404


class TestListAndFilters:
    def test_list_filters_by_member(self, db: Session, family, adults):
        andrew = adults["robert"]
        sally = adults["megan"]
        create_note(db, family.id, NoteCreate(family_member_id=andrew.id, title="A"))
        create_note(db, family.id, NoteCreate(family_member_id=sally.id, title="S"))

        andrew_notes = list_notes(db, family.id, family_member_id=andrew.id)
        titles = {n.title for n in andrew_notes}
        assert titles == {"A"}

    def test_list_filters_by_category(self, db: Session, family, adults):
        andrew = adults["robert"]
        create_note(db, family.id, NoteCreate(family_member_id=andrew.id, title="W", category="work"))
        create_note(db, family.id, NoteCreate(family_member_id=andrew.id, title="H", category="home"))

        results = list_notes(db, family.id, category="work")
        titles = {n.title for n in results}
        assert titles == {"W"}

    def test_archived_excluded_by_default(self, db: Session, family, adults):
        andrew = adults["robert"]
        active = create_note(db, family.id, NoteCreate(family_member_id=andrew.id, title="Active"))
        archived = create_note(db, family.id, NoteCreate(family_member_id=andrew.id, title="Archived"))
        archive_note(db, family.id, archived.id)

        default_results = list_notes(db, family.id)
        titles = {n.title for n in default_results}
        assert titles == {"Active"}

        all_results = list_notes(db, family.id, include_archived=True)
        titles_all = {n.title for n in all_results}
        assert titles_all == {"Active", "Archived"}


class TestRecent:
    def test_recent_orders_by_updated_at(self, db: Session, family, adults):
        andrew = adults["robert"]
        first = create_note(db, family.id, NoteCreate(family_member_id=andrew.id, title="First"))
        second = create_note(db, family.id, NoteCreate(family_member_id=andrew.id, title="Second"))
        third = create_note(db, family.id, NoteCreate(family_member_id=andrew.id, title="Third"))

        # Touch first to make it most recent
        update_note(db, family.id, first.id, NoteUpdate(body="touched"))

        results = list_recent_notes(db, family.id, limit=3)
        # Most recently updated first
        assert results[0].id == first.id

    def test_recent_excludes_archived(self, db: Session, family, adults):
        andrew = adults["robert"]
        active = create_note(db, family.id, NoteCreate(family_member_id=andrew.id, title="Active"))
        archived = create_note(db, family.id, NoteCreate(family_member_id=andrew.id, title="Archived"))
        archive_note(db, family.id, archived.id)

        results = list_recent_notes(db, family.id)
        titles = {n.title for n in results}
        assert "Archived" not in titles
        assert "Active" in titles


class TestSearch:
    def test_search_in_title(self, db: Session, family, adults):
        andrew = adults["robert"]
        create_note(db, family.id, NoteCreate(family_member_id=andrew.id, title="Garden plan"))
        create_note(db, family.id, NoteCreate(family_member_id=andrew.id, title="Work strategy"))

        results = search_notes(db, family.id, "garden")
        titles = {n.title for n in results}
        assert titles == {"Garden plan"}

    def test_search_in_body(self, db: Session, family, adults):
        andrew = adults["robert"]
        create_note(
            db, family.id,
            NoteCreate(
                family_member_id=andrew.id,
                title="Notes",
                body="Need to talk to financial advisor about 529 plans",
            ),
        )
        create_note(
            db, family.id,
            NoteCreate(family_member_id=andrew.id, title="Other", body="random stuff"),
        )

        results = search_notes(db, family.id, "529")
        titles = {n.title for n in results}
        assert titles == {"Notes"}

    def test_search_case_insensitive(self, db: Session, family, adults):
        andrew = adults["robert"]
        create_note(db, family.id, NoteCreate(family_member_id=andrew.id, title="MEETING NOTES"))
        results = search_notes(db, family.id, "meeting")
        assert len(results) == 1

    def test_search_empty_query_returns_empty(self, db: Session, family, adults):
        andrew = adults["robert"]
        create_note(db, family.id, NoteCreate(family_member_id=andrew.id, title="Anything"))
        results = search_notes(db, family.id, "   ")
        assert results == []


class TestArchive:
    def test_archive_then_unarchive(self, db: Session, family, adults):
        note = create_note(
            db, family.id,
            NoteCreate(family_member_id=adults["robert"].id, title="Toggle me"),
        )
        archived = archive_note(db, family.id, note.id)
        assert archived.is_archived is True

        unarchived = unarchive_note(db, family.id, note.id)
        assert unarchived.is_archived is False


class TestTenantIsolation:
    def test_get_note_from_wrong_family_404(self, db: Session, family):
        other = Family(name="Other", timezone="America/New_York")
        db.add(other)
        db.flush()
        other_member = FamilyMember(family_id=other.id, first_name="Stranger", role="adult")
        db.add(other_member)
        db.flush()

        note = create_note(
            db, other.id,
            NoteCreate(family_member_id=other_member.id, title="Theirs"),
        )
        with pytest.raises(HTTPException) as exc:
            get_note(db, family.id, note.id)
        assert exc.value.status_code == 404

    def test_list_notes_only_returns_own_family(self, db: Session, family, adults):
        other = Family(name="Other", timezone="America/New_York")
        db.add(other)
        db.flush()
        other_member = FamilyMember(family_id=other.id, first_name="Stranger", role="adult")
        db.add(other_member)
        db.flush()

        create_note(db, family.id, NoteCreate(family_member_id=adults["robert"].id, title="Mine"))
        create_note(db, other.id, NoteCreate(family_member_id=other_member.id, title="Theirs"))

        results = list_notes(db, family.id)
        titles = {n.title for n in results}
        assert "Mine" in titles
        assert "Theirs" not in titles

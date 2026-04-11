"""Integration tests for AI routes.

Tests route validation, family/member enforcement, and response shape.
Does NOT call the actual Anthropic API — tests that require real AI
responses are excluded. These tests verify the plumbing.
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import AIConversation, AIMessage
from app.models.foundation import Family, FamilyMember
from app.ai.orchestrator import get_or_create_conversation


class TestConversationState:
    def test_create_conversation(self, db: Session, family, adults):
        andrew = adults["robert"]
        conv = get_or_create_conversation(db, family.id, andrew.id, "personal")
        assert conv.id is not None
        assert conv.family_id == family.id
        assert conv.family_member_id == andrew.id
        assert conv.surface == "personal"
        assert conv.status == "active"

    def test_retrieve_existing_conversation(self, db: Session, family, adults):
        andrew = adults["robert"]
        conv1 = get_or_create_conversation(db, family.id, andrew.id, "personal")
        conv2 = get_or_create_conversation(db, family.id, andrew.id, "personal", conv1.id)
        assert conv1.id == conv2.id

    def test_wrong_family_creates_new(self, db: Session, family, adults):
        andrew = adults["robert"]
        conv1 = get_or_create_conversation(db, family.id, andrew.id, "personal")

        other_family = Family(name="Other", timezone="UTC")
        db.add(other_family)
        db.flush()
        other_member = FamilyMember(family_id=other_family.id, first_name="X", role="adult")
        db.add(other_member)
        db.flush()

        # Passing conv1.id for a different family should create a new conversation
        conv2 = get_or_create_conversation(db, other_family.id, other_member.id, "personal", conv1.id)
        assert conv2.id != conv1.id


class TestFamilyIsolation:
    def test_conversations_are_family_scoped(self, db: Session, family, adults):
        andrew = adults["robert"]
        conv = get_or_create_conversation(db, family.id, andrew.id, "personal")

        # Query for another family returns nothing
        other_family = Family(name="Other", timezone="UTC")
        db.add(other_family)
        db.flush()

        convs = list(db.scalars(
            select(AIConversation)
            .where(AIConversation.family_id == other_family.id)
        ).all())
        assert len(convs) == 0


class TestWriteConfirmation:
    def test_confirmation_required_tools_list(self):
        from app.ai.tools import CONFIRMATION_REQUIRED
        assert "create_event" in CONFIRMATION_REQUIRED
        assert "update_event" in CONFIRMATION_REQUIRED
        assert "mark_chore_or_routine_complete" in CONFIRMATION_REQUIRED
        # Read tools should never require confirmation
        assert "list_tasks" not in CONFIRMATION_REQUIRED
        assert "get_today_context" not in CONFIRMATION_REQUIRED

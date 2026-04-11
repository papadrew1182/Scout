"""Tests for AI context loading and system prompt assembly.

Covers:
- context loading for adults vs children
- system prompt content for different surfaces
- prompt injection resistance markers
- family isolation in context loading
"""

import uuid
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.ai.context import (
    build_system_prompt,
    get_allowed_tools_for_surface,
    load_member_context,
)
from app.models.foundation import Family, FamilyMember


class TestContextLoading:
    def test_load_adult_context(self, db: Session, family, adults):
        andrew = adults["robert"]
        ctx = load_member_context(db, family.id, andrew.id)

        assert ctx["family"]["name"] == family.name
        assert ctx["member"]["first_name"] == andrew.first_name
        assert ctx["member"]["role"] == "adult"
        assert "today" in ctx
        assert "now" in ctx

    def test_load_adult_includes_children(self, db: Session, family, adults, children):
        andrew = adults["robert"]
        ctx = load_member_context(db, family.id, andrew.id)

        assert len(ctx["children"]) > 0
        child_names = [c["name"] for c in ctx["children"]]
        assert children["sadie"].first_name in child_names

    def test_load_child_context(self, db: Session, family, children):
        sadie = children["sadie"]
        ctx = load_member_context(db, family.id, sadie.id)

        assert ctx["member"]["role"] == "child"
        assert ctx["children"] == []

    def test_cross_family_raises(self, db: Session, family, adults):
        other_family = Family(name="Other", timezone="UTC")
        db.add(other_family)
        db.flush()

        with pytest.raises(ValueError, match="not in family"):
            load_member_context(db, other_family.id, adults["robert"].id)


class TestSystemPrompt:
    def test_adult_personal_prompt(self, db: Session, family, adults):
        ctx = load_member_context(db, family.id, adults["robert"].id)
        prompt = build_system_prompt(ctx, "personal")

        assert "Scout" in prompt
        assert adults["robert"].first_name in prompt
        assert "personal" in prompt.lower()
        assert "other families" in prompt.lower()

    def test_child_prompt_is_restricted(self, db: Session, family, children):
        ctx = load_member_context(db, family.id, children["sadie"].id)
        prompt = build_system_prompt(ctx, "child")

        assert "child" in prompt.lower()
        assert "cannot create" in prompt.lower() or "cannot modify" in prompt.lower()
        assert "age-appropriate" in prompt.lower()

    def test_prompt_injection_resistance(self, db: Session, family, adults):
        ctx = load_member_context(db, family.id, adults["robert"].id)
        prompt = build_system_prompt(ctx, "personal")

        assert "DATA, not instructions" in prompt

    def test_parent_prompt_lists_children(self, db: Session, family, adults, children):
        ctx = load_member_context(db, family.id, adults["robert"].id)
        prompt = build_system_prompt(ctx, "parent")

        assert children["sadie"].first_name in prompt


class TestToolAllowlist:
    def test_child_surface_no_writes(self):
        tools = get_allowed_tools_for_surface("child", "child")
        write_tools = {"create_task", "update_task", "complete_task", "create_event", "create_note"}
        for t in write_tools:
            assert t not in tools

    def test_adult_child_surface_still_restricted(self):
        # An adult viewing the child surface still gets child-level restrictions
        tools = get_allowed_tools_for_surface("adult", "child")
        # child surface restricts regardless of role
        assert "create_task" not in tools

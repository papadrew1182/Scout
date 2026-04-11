"""Tests for task_generation_service.

Covers:
- idempotency
- routine-sourced instances create step completion rows
- chore-sourced instances do NOT create step completion rows
- dog walk assistant rotation by day parity
- weekday recurrence filtering
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.life_management import TaskInstance, TaskInstanceStepCompletion
from app.services.task_generation_service import generate_for_date


class TestIdempotency:
    def test_generate_twice_same_date_no_duplicates(self, db: Session, family, children, sadie_routines):
        target = date(2026, 3, 30)  # Monday
        first = generate_for_date(db, family.id, target)
        second = generate_for_date(db, family.id, target)

        assert len(first) > 0
        assert len(second) == 0

    def test_generate_different_dates_creates_separate_instances(self, db: Session, family, children, sadie_routines):
        mon = date(2026, 3, 30)
        tue = date(2026, 3, 31)

        first = generate_for_date(db, family.id, mon)
        second = generate_for_date(db, family.id, tue)

        assert len(first) > 0
        assert len(second) > 0


class TestRoutineStepCompletions:
    def test_routine_instance_creates_step_completions(self, db: Session, family, children, sadie_routines):
        target = date(2026, 3, 30)  # Monday
        generate_for_date(db, family.id, target)

        sadie = children["sadie"]
        morning_routine = sadie_routines[0]

        instance = db.scalars(
            select(TaskInstance)
            .where(TaskInstance.family_member_id == sadie.id)
            .where(TaskInstance.routine_id == morning_routine.id)
            .where(TaskInstance.instance_date == target)
        ).first()

        assert instance is not None

        step_completions = list(
            db.scalars(
                select(TaskInstanceStepCompletion)
                .where(TaskInstanceStepCompletion.task_instance_id == instance.id)
            ).all()
        )

        # Morning routine has 3 steps in fixture
        assert len(step_completions) == 3
        assert all(sc.is_completed is False for sc in step_completions)

    def test_chore_instance_has_no_step_completions(self, db: Session, family, children, dishwasher_template):
        target = date(2026, 3, 30)  # Monday (weekday)
        generate_for_date(db, family.id, target)

        sadie = children["sadie"]
        instance = db.scalars(
            select(TaskInstance)
            .where(TaskInstance.family_member_id == sadie.id)
            .where(TaskInstance.chore_template_id == dishwasher_template.id)
            .where(TaskInstance.instance_date == target)
        ).first()

        assert instance is not None

        step_completions = list(
            db.scalars(
                select(TaskInstanceStepCompletion)
                .where(TaskInstanceStepCompletion.task_instance_id == instance.id)
            ).all()
        )
        assert len(step_completions) == 0


class TestDogWalkAssistant:
    def test_odd_day_assigns_townes(self, db: Session, family, children, dog_walk_templates):
        # March 31 = day 31 = odd → Townes
        target = date(2026, 3, 31)
        generate_for_date(db, family.id, target)

        townes = children["townes"]
        assistant_template = dog_walk_templates["assistant"]

        instance = db.scalars(
            select(TaskInstance)
            .where(TaskInstance.family_member_id == townes.id)
            .where(TaskInstance.chore_template_id == assistant_template.id)
            .where(TaskInstance.instance_date == target)
        ).first()

        assert instance is not None

    def test_even_day_assigns_river(self, db: Session, family, children, dog_walk_templates):
        # March 30 = day 30 = even → River
        target = date(2026, 3, 30)
        generate_for_date(db, family.id, target)

        river = children["river"]
        assistant_template = dog_walk_templates["assistant"]

        instance = db.scalars(
            select(TaskInstance)
            .where(TaskInstance.family_member_id == river.id)
            .where(TaskInstance.chore_template_id == assistant_template.id)
            .where(TaskInstance.instance_date == target)
        ).first()

        assert instance is not None

    def test_sadie_always_gets_lead(self, db: Session, family, children, dog_walk_templates):
        sadie = children["sadie"]
        lead_template = dog_walk_templates["lead"]

        for d in [date(2026, 3, 30), date(2026, 3, 31)]:
            generate_for_date(db, family.id, d)

        instances = list(
            db.scalars(
                select(TaskInstance)
                .where(TaskInstance.family_member_id == sadie.id)
                .where(TaskInstance.chore_template_id == lead_template.id)
            ).all()
        )
        assert len(instances) == 2


class TestRecurrenceFiltering:
    def test_weekday_chore_skipped_on_weekend(self, db: Session, family, children, dishwasher_template):
        saturday = date(2026, 4, 4)
        created = generate_for_date(db, family.id, saturday)

        chore_instances = [i for i in created if i.chore_template_id == dishwasher_template.id]
        assert len(chore_instances) == 0

    def test_weekday_routine_after_school_skipped_on_weekend(self, db: Session, family, children, sadie_routines):
        saturday = date(2026, 4, 4)
        generate_for_date(db, family.id, saturday)

        sadie = children["sadie"]
        after_school = sadie_routines[1]  # recurrence="weekdays"

        instance = db.scalars(
            select(TaskInstance)
            .where(TaskInstance.family_member_id == sadie.id)
            .where(TaskInstance.routine_id == after_school.id)
            .where(TaskInstance.instance_date == saturday)
        ).first()

        assert instance is None

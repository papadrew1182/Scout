"""Deterministic smoke-test seed: family, members, accounts, meal plan, groceries, action items.

Idempotent. Run after migrations:
    python seed_smoke.py

Creates:
- Whitfield family
- Adult: Andrew (adult@test.com / testpass123)
- Child: Sadie (child@test.com / testpass123)
- 3 more members (Sally, Townes, Tyler)
- Approved weekly meal plan with grocery sync
- Parent action items from child grocery submission
"""

import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.models.foundation import Family, FamilyMember, UserAccount, Session
from app.models.grocery import GroceryItem
from app.models.meals import WeeklyMealPlan
from app.models.action_items import ParentActionItem
from app.services.auth_service import hash_password


def get_db_url():
    url = os.environ.get("SCOUT_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Set SCOUT_DATABASE_URL or DATABASE_URL")
    return url


ADULT_EMAIL = "adult@test.com"
CHILD_EMAIL = "child@test.com"
PASSWORD = "testpass123"


def seed_smoke():
    engine = create_engine(get_db_url())
    DB = sessionmaker(bind=engine)
    db = DB()

    # --- Family ---
    family = db.scalars(select(Family).where(Family.name == "Whitfield")).first()
    if not family:
        family = Family(name="Whitfield", timezone="America/Chicago")
        db.add(family)
        db.flush()
        print(f"Created family: {family.name} (id={family.id})")
    else:
        print(f"Family exists: {family.name} (id={family.id})")

    # --- Members ---
    def ensure_member(first, last, role, bdate):
        m = db.scalars(
            select(FamilyMember)
            .where(FamilyMember.family_id == family.id)
            .where(FamilyMember.first_name == first)
        ).first()
        if not m:
            m = FamilyMember(family_id=family.id, first_name=first, last_name=last, role=role, birthdate=bdate)
            db.add(m)
            db.flush()
            print(f"  Created member: {first} ({role})")
        return m

    andrew = ensure_member("Andrew", "Whitfield", "adult", date(1985, 6, 14))
    sally = ensure_member("Sally", "Whitfield", "adult", date(1987, 3, 22))
    sadie = ensure_member("Sadie", "Whitfield", "child", date(2012, 9, 10))
    townes = ensure_member("Townes", "Whitfield", "child", date(2015, 11, 28))
    tyler = ensure_member("Tyler", "Whitfield", "child", date(2017, 7, 4))
    db.commit()

    # --- Accounts ---
    def ensure_account(member, email):
        acct = db.scalars(select(UserAccount).where(UserAccount.email == email)).first()
        if not acct:
            acct = UserAccount(
                family_member_id=member.id, email=email,
                auth_provider="email", password_hash=hash_password(PASSWORD),
                is_primary=True, is_active=True,
            )
            db.add(acct)
            db.flush()
            print(f"  Created account: {email}")
        return acct

    ensure_account(andrew, ADULT_EMAIL)
    ensure_account(sadie, CHILD_EMAIL)
    db.commit()

    # --- Approved weekly meal plan ---
    monday = date.today() - timedelta(days=date.today().weekday())  # current week Monday
    existing_plan = db.scalars(
        select(WeeklyMealPlan)
        .where(WeeklyMealPlan.family_id == family.id)
        .where(WeeklyMealPlan.status == "approved")
    ).first()
    if not existing_plan:
        plan = WeeklyMealPlan(
            family_id=family.id,
            created_by_member_id=andrew.id,
            week_start_date=monday,
            source="ai",
            status="approved",
            title="Smoke Test Week",
            constraints_snapshot={},
            week_plan={
                "dinners": {
                    "monday": {"title": "Sheet-pan chicken", "description": "with roasted vegetables"},
                    "tuesday": {"title": "Taco night", "description": "ground turkey tacos"},
                    "wednesday": {"title": "Pasta bake", "description": "leftover friendly"},
                    "thursday": {"title": "Stir fry", "description": "quick wok vegetables and rice"},
                    "friday": {"title": "Homemade pizza", "description": "family pizza night"},
                },
                "breakfast": {"plan": "Eggs, yogurt, cereal rotation"},
                "lunch": {"plan": "Sandwiches and leftovers"},
                "snacks": ["fruit", "cheese sticks", "granola bars"],
            },
            prep_plan={
                "tasks": [
                    {"title": "Cook rice batch", "supports": ["monday", "thursday"], "duration_min": 25},
                    {"title": "Chop vegetables", "supports": ["monday", "tuesday"], "duration_min": 20},
                ],
                "timeline": [{"block": "0:00-0:45", "items": ["rice", "chop vegetables"]}],
            },
            grocery_plan={
                "stores": [
                    {"name": "Costco", "items": [
                        {"title": "Chicken thighs", "quantity": 4, "unit": "lb", "category": "protein"},
                        {"title": "Ground turkey", "quantity": 2, "unit": "lb", "category": "protein"},
                    ]},
                    {"name": "H-E-B", "items": [
                        {"title": "Tortillas", "quantity": 1, "unit": "pack"},
                        {"title": "Broccoli", "quantity": 2, "unit": "heads"},
                        {"title": "Pizza dough", "quantity": 2, "unit": "balls"},
                    ]},
                ]
            },
            plan_summary="Five weeknight dinners with Sunday batch cook",
            approved_by_member_id=andrew.id,
            approved_at=datetime.now(timezone.utc),
        )
        db.add(plan)
        db.flush()
        print(f"  Created approved meal plan: {plan.id}")

        # Sync grocery items from plan
        for store in plan.grocery_plan.get("stores", []):
            for item in store.get("items", []):
                gi = GroceryItem(
                    family_id=family.id, added_by_member_id=andrew.id,
                    title=item["title"], quantity=item.get("quantity"),
                    unit=item.get("unit"), category=item.get("category"),
                    preferred_store=store["name"], source="meal_ai",
                    approval_status="active", weekly_plan_id=plan.id,
                )
                db.add(gi)
        db.flush()
        print(f"  Created {len([i for s in plan.grocery_plan['stores'] for i in s['items']])} grocery items")
    else:
        print(f"  Meal plan already exists: {existing_plan.id}")

    # --- Parent action item (from child grocery submission) ---
    existing_action = db.scalars(
        select(ParentActionItem)
        .where(ParentActionItem.family_id == family.id)
        .where(ParentActionItem.status == "pending")
    ).first()
    if not existing_action:
        # Child adds a grocery item (pending review)
        child_item = GroceryItem(
            family_id=family.id, added_by_member_id=sadie.id,
            title="Gummy bears", source="manual",
            approval_status="pending_review",
        )
        db.add(child_item)
        db.flush()
        action = ParentActionItem(
            family_id=family.id, created_by_member_id=sadie.id,
            action_type="grocery_review",
            title=f"Sadie added 'Gummy bears' to the grocery list",
            entity_type="grocery_item", entity_id=child_item.id,
        )
        db.add(action)
        db.flush()
        print(f"  Created parent action item: {action.id}")
    else:
        print(f"  Action item already exists: {existing_action.id}")

    db.commit()
    db.close()
    print("\nSmoke seed complete.")
    print(f"  Adult login: {ADULT_EMAIL} / {PASSWORD}")
    print(f"  Child login: {CHILD_EMAIL} / {PASSWORD}")


if __name__ == "__main__":
    seed_smoke()

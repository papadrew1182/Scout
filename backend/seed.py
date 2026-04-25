"""Seed the database with the Roberts family for private launch.

Run once after migrations:
    python seed.py

Idempotent: skips if family already exists.

Maintenance gate (PR 1.5)
-------------------------
While the canonical rewrite sprint is in flight (Phase 1 dropped the
public.* tables this script's ORM models target), running seed.py
against the post-057 schema would crash on the first ORM query. The
guard below short-circuits cleanly when SCOUT_CANONICAL_MAINTENANCE=true,
so backend/start.sh can keep invoking ``python seed.py`` without
edits. Default is ``false`` — non-rewrite environments are unaffected.

The guard runs before any SQLAlchemy/app.* imports because those
imports themselves can fail or trigger DB metadata work that depends
on the dropped public.* shape. PR 3.1 owns rewriting or retiring this
script against canonical scout.* tables; until then, the guard stays.
"""

import os
import sys

if os.getenv("SCOUT_CANONICAL_MAINTENANCE", "false").strip().lower() == "true":
    print(
        "seed.py: SCOUT_CANONICAL_MAINTENANCE=true; "
        "skipping seed during canonical rewrite",
        file=sys.stderr,
    )
    sys.exit(0)

from datetime import date

# Add backend to path so app modules can be imported
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.access import RoleTier, RoleTierOverride
from app.models.foundation import Family, FamilyMember


def get_db_url():
    url = os.environ.get("SCOUT_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Set SCOUT_DATABASE_URL or DATABASE_URL")
    return url


def seed():
    engine = create_engine(get_db_url())
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    # Check if family already exists
    existing = db.scalars(select(Family).where(Family.name == "Roberts")).first()
    if existing:
        print(f"Family 'Roberts' already exists (id={existing.id}). Skipping seed.")
        db.close()
        return

    # Create family
    family = Family(name="Roberts", timezone="America/Chicago")
    db.add(family)
    db.flush()
    print(f"Created family: {family.name} (id={family.id})")

    # Create members
    members_data = [
        FamilyMember(family_id=family.id, first_name="Andrew", last_name="Roberts", role="adult", birthdate=date(1985, 6, 14)),
        FamilyMember(family_id=family.id, first_name="Sally", last_name="Roberts", role="adult", birthdate=date(1987, 3, 22)),
        FamilyMember(family_id=family.id, first_name="Sadie", last_name="Roberts", role="child", birthdate=date(2012, 9, 10)),
        FamilyMember(family_id=family.id, first_name="Townes", last_name="Roberts", role="child", birthdate=date(2015, 11, 28)),
        FamilyMember(family_id=family.id, first_name="Tyler", last_name="Roberts", role="child", birthdate=date(2017, 7, 4)),
    ]
    db.add_all(members_data)
    db.commit()

    for m in members_data:
        db.refresh(m)
        print(f"  Created member: {m.first_name} ({m.role}, id={m.id})")

    # Assign role tiers (migration 022 seeds the canonical tier rows; if running
    # seed.py outside of migrations context the tiers may not exist yet —
    # skip silently).  Canonical UPPERCASE names as established by migration 022
    # and unified by migration 034.
    tier_name_map = {
        "Andrew": "PRIMARY_PARENT",
        "Sally":  "PRIMARY_PARENT",
        "Tyler":  "TEEN",
        "Sadie":  "TEEN",
        "Townes": "CHILD",
    }
    for m in members_data:
        tier_name = tier_name_map.get(m.first_name)
        if not tier_name:
            continue
        tier = db.scalars(select(RoleTier).where(RoleTier.name == tier_name)).first()
        if not tier:
            print(f"  Skipping tier assignment for {m.first_name}: tier '{tier_name}' not found (run migration 024 first)")
            continue
        existing = db.scalars(select(RoleTierOverride).where(RoleTierOverride.family_member_id == m.id)).first()
        if not existing:
            db.add(RoleTierOverride(
                family_member_id=m.id,
                role_tier_id=tier.id,
                override_permissions={},
                override_behavior={},
            ))
            print(f"  Assigned tier '{tier_name}' to {m.first_name}")
    db.commit()

    db.close()
    print("\nSeed complete. Run bootstrap to create the first login account:")
    print(f'  curl -X POST https://YOUR_DOMAIN/api/auth/bootstrap \\')
    print(f'    -H "Content-Type: application/json" \\')
    print(f'    -d \'{{"email": "your@email.com", "password": "your-password"}}\'')


if __name__ == "__main__":
    seed()

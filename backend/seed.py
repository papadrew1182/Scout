"""Seed the database with the Whitfield family for private launch.

Run once after migrations:
    python seed.py

Idempotent: skips if family already exists.
"""

import os
import sys
from datetime import date

# Add backend to path so app modules can be imported
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
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
    existing = db.scalars(select(Family).where(Family.name == "Whitfield")).first()
    if existing:
        print(f"Family 'Whitfield' already exists (id={existing.id}). Skipping seed.")
        db.close()
        return

    # Create family
    family = Family(name="Whitfield", timezone="America/Chicago")
    db.add(family)
    db.flush()
    print(f"Created family: {family.name} (id={family.id})")

    # Create members
    members = [
        FamilyMember(family_id=family.id, first_name="Andrew", last_name="Whitfield", role="adult", birthdate=date(1985, 6, 14)),
        FamilyMember(family_id=family.id, first_name="Sally", last_name="Whitfield", role="adult", birthdate=date(1987, 3, 22)),
        FamilyMember(family_id=family.id, first_name="Sadie", last_name="Whitfield", role="child", birthdate=date(2012, 9, 10)),
        FamilyMember(family_id=family.id, first_name="Townes", last_name="Whitfield", role="child", birthdate=date(2015, 11, 28)),
        FamilyMember(family_id=family.id, first_name="Tyler", last_name="Whitfield", role="child", birthdate=date(2017, 7, 4)),
    ]
    db.add_all(members)
    db.commit()

    for m in members:
        db.refresh(m)
        print(f"  Created member: {m.first_name} ({m.role}, id={m.id})")

    db.close()
    print("\nSeed complete. Run bootstrap to create the first login account:")
    print(f'  curl -X POST https://YOUR_DOMAIN/api/auth/bootstrap \\')
    print(f'    -H "Content-Type: application/json" \\')
    print(f'    -d \'{{"email": "your@email.com", "password": "your-password"}}\'')


if __name__ == "__main__":
    seed()

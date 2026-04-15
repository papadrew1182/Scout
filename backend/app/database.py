from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, echo=settings.echo_sql)


# Session 2 F22 added the `scout` schema. When the database role name
# matches the schema name (as it does in dev and CI — role "scout",
# schema "scout"), Postgres's default search_path
#   "$user", public
# resolves "$user" to "scout" and picks up scout.* before public.*
# for unqualified names. Every existing app query uses unqualified
# names that target public, so this shadow breaks things like
# `INSERT INTO routine_steps ...` against the old public shape.
# Force an explicit search_path at connection time so public is the
# primary and scout is a secondary fallback for anything that
# genuinely lives in scout only.
@event.listens_for(engine, "connect")
def _set_search_path(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("SET search_path TO public, scout")
    finally:
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

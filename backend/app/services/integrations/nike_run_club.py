"""Nike Run Club ingestion — placeholder only.

Not implemented in this package. The shape will mirror google_calendar.py:
a payload schema, an ingest_run function that delegates to upsert_via_mapping
with internal_table='activity_records' and connector_name='nike_run_club'.

NOTE: The connector_mappings.connector_name CHECK constraint does NOT yet
include 'nike_run_club'. Adding it requires a follow-up migration similar
to 004_connector_ical_support.sql.
"""

from fastapi import HTTPException, status


def ingest_run(*args, **kwargs):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Nike Run Club ingestion is not implemented yet",
    )

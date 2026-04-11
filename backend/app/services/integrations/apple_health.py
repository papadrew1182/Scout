"""Apple Health ingestion — placeholder only.

Not implemented in this package. The shape will mirror google_calendar.py
and ynab.py: a payload schema, a single ingest_<resource> function that
delegates to upsert_via_mapping with internal_table='health_summaries' or
'activity_records' and connector_name='apple_health'.
"""

from fastapi import HTTPException, status


def ingest_summary(*args, **kwargs):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Apple Health ingestion is not implemented yet",
    )


def ingest_activity(*args, **kwargs):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Apple Health activity ingestion is not implemented yet",
    )

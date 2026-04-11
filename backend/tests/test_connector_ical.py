"""Regression test for migration 004_connector_ical_support.

Confirms that the connector_configs and connector_mappings CHECK constraints
accept 'ical' as a connector_name after the migration is applied.
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.connectors import ConnectorConfig, ConnectorMapping


class TestICalConnectorSupport:
    def test_connector_config_accepts_ical(self, db: Session, family):
        config = ConnectorConfig(
            family_id=family.id,
            family_member_id=None,
            connector_name="ical",
            config={"feed_url": "https://example.com/school.ics"},
            scope="family",
            sync_direction="read",
            authority_level="secondary",
        )
        db.add(config)
        db.flush()
        assert config.id is not None
        assert config.connector_name == "ical"

    def test_connector_mapping_accepts_ical(self, db: Session, family):
        mapping = ConnectorMapping(
            connector_name="ical",
            internal_table="events",
            internal_id=uuid.uuid4(),
            external_id="ical_event_xyz_123",
            metadata_={"resource_type": "event", "feed": "school_calendar"},
        )
        db.add(mapping)
        db.flush()
        assert mapping.id is not None
        assert mapping.connector_name == "ical"

    def test_unknown_connector_name_still_rejected(self, db: Session):
        mapping = ConnectorMapping(
            connector_name="not_a_real_connector",
            internal_table="events",
            internal_id=uuid.uuid4(),
            external_id="x",
            metadata_={},
        )
        db.add(mapping)
        with pytest.raises(IntegrityError):
            db.flush()

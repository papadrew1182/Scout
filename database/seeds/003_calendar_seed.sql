-- Seed 003: Calendar / Scheduling
-- Realistic fake events for the Roberts household.
-- Requires: 003_calendar.sql migration applied first.
--
-- UUID reference (from foundation seed):
-- family:  a1b2c3d4-0000-4000-8000-000000000001
-- Andrew:  b1000000-0000-4000-8000-000000000001
-- Sally:   b1000000-0000-4000-8000-000000000002
-- Sadie:   b1000000-0000-4000-8000-000000000003
-- Townes:  b1000000-0000-4000-8000-000000000004
-- River:   b1000000-0000-4000-8000-000000000005

BEGIN;

-- ============================================================================
-- events
-- ============================================================================

-- Sadie soccer practice — recurring every Tuesday + Thursday at 5pm
INSERT INTO events (id, family_id, created_by, title, description, location,
                    starts_at, ends_at, recurrence_rule, source, is_hearth_visible)
VALUES
    ('80000000-0001-4000-8000-000000000001',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000002',
     'Sadie Soccer Practice',
     'Bring water bottle and shin guards',
     'Lakeview Sports Complex, Field 3',
     '2026-04-07 17:00:00-05', '2026-04-07 18:30:00-05',
     'FREQ=WEEKLY;BYDAY=TU,TH',
     'scout', true);

-- Edited instance: Tuesday 2026-04-14 practice cancelled (rain)
INSERT INTO events (id, family_id, created_by, title, description, location,
                    starts_at, ends_at,
                    recurrence_parent_id, recurrence_instance_date,
                    is_cancelled, source, is_hearth_visible)
VALUES
    ('80000000-0001-4000-8000-000000000002',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000002',
     'Sadie Soccer Practice — CANCELLED',
     'Cancelled due to weather',
     'Lakeview Sports Complex, Field 3',
     '2026-04-14 17:00:00-05', '2026-04-14 18:30:00-05',
     '80000000-0001-4000-8000-000000000001', '2026-04-14',
     true, 'scout', true);

-- Family dinner Friday — one-off
INSERT INTO events (id, family_id, created_by, title, description, location,
                    starts_at, ends_at, source, is_hearth_visible)
VALUES
    ('80000000-0001-4000-8000-000000000003',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'Family Dinner — Grandparents',
     'Grandma and Grandpa coming over',
     'Home',
     '2026-04-10 18:00:00-05', '2026-04-10 20:30:00-05',
     'scout', true);

-- River pediatrician appointment — one-off
INSERT INTO events (id, family_id, created_by, title, description, location,
                    starts_at, ends_at, source, is_hearth_visible)
VALUES
    ('80000000-0001-4000-8000-000000000004',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000002',
     'River Pediatrician Checkup',
     'Annual wellness visit with Dr. Martinez',
     'Children''s Health Clinic',
     '2026-04-15 09:30:00-05', '2026-04-15 10:30:00-05',
     'scout', true);

-- Andrew work meeting — one-off, NOT hearth visible (personal)
INSERT INTO events (id, family_id, created_by, title, description, location,
                    starts_at, ends_at, source, is_hearth_visible)
VALUES
    ('80000000-0001-4000-8000-000000000005',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'Q2 Planning Review',
     'Quarterly leadership planning session',
     'Conference Room A',
     '2026-04-13 14:00:00-05', '2026-04-13 16:00:00-05',
     'google_cal', false);

-- All-day school holiday
INSERT INTO events (id, family_id, created_by, title, starts_at, ends_at,
                    all_day, source, is_hearth_visible)
VALUES
    ('80000000-0001-4000-8000-000000000006',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000002',
     'No School — Spring Break',
     '2026-04-13 00:00:00-05', '2026-04-17 23:59:59-05',
     true, 'ical', true);

-- ============================================================================
-- event_attendees
-- ============================================================================

-- Sadie soccer: Sadie attends, Sally drives (accepted)
INSERT INTO event_attendees (id, event_id, family_member_id, response_status)
VALUES
    ('81000000-0001-4000-8000-000000000001',
     '80000000-0001-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000003', 'accepted'),
    ('81000000-0001-4000-8000-000000000002',
     '80000000-0001-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000002', 'accepted');

-- Family dinner: everyone
INSERT INTO event_attendees (id, event_id, family_member_id, response_status)
VALUES
    ('81000000-0001-4000-8000-000000000003',
     '80000000-0001-4000-8000-000000000003',
     'b1000000-0000-4000-8000-000000000001', 'accepted'),
    ('81000000-0001-4000-8000-000000000004',
     '80000000-0001-4000-8000-000000000003',
     'b1000000-0000-4000-8000-000000000002', 'accepted'),
    ('81000000-0001-4000-8000-000000000005',
     '80000000-0001-4000-8000-000000000003',
     'b1000000-0000-4000-8000-000000000003', 'accepted'),
    ('81000000-0001-4000-8000-000000000006',
     '80000000-0001-4000-8000-000000000003',
     'b1000000-0000-4000-8000-000000000004', 'accepted'),
    ('81000000-0001-4000-8000-000000000007',
     '80000000-0001-4000-8000-000000000003',
     'b1000000-0000-4000-8000-000000000005', 'accepted');

-- River pediatrician: River + Sally
INSERT INTO event_attendees (id, event_id, family_member_id, response_status)
VALUES
    ('81000000-0001-4000-8000-000000000008',
     '80000000-0001-4000-8000-000000000004',
     'b1000000-0000-4000-8000-000000000005', 'accepted'),
    ('81000000-0001-4000-8000-000000000009',
     '80000000-0001-4000-8000-000000000004',
     'b1000000-0000-4000-8000-000000000002', 'accepted');

-- Andrew work meeting: Andrew only
INSERT INTO event_attendees (id, event_id, family_member_id, response_status)
VALUES
    ('81000000-0001-4000-8000-000000000010',
     '80000000-0001-4000-8000-000000000005',
     'b1000000-0000-4000-8000-000000000001', 'accepted');

-- Spring break: all kids
INSERT INTO event_attendees (id, event_id, family_member_id, response_status)
VALUES
    ('81000000-0001-4000-8000-000000000011',
     '80000000-0001-4000-8000-000000000006',
     'b1000000-0000-4000-8000-000000000003', 'accepted'),
    ('81000000-0001-4000-8000-000000000012',
     '80000000-0001-4000-8000-000000000006',
     'b1000000-0000-4000-8000-000000000004', 'accepted'),
    ('81000000-0001-4000-8000-000000000013',
     '80000000-0001-4000-8000-000000000006',
     'b1000000-0000-4000-8000-000000000005', 'accepted');

-- ============================================================================
-- connector_mappings — example external IDs for synced events
-- ============================================================================

-- Andrew's Q2 Planning Review came from Google Calendar
INSERT INTO connector_mappings (id, connector_name, internal_table, internal_id,
                                 external_id, metadata)
VALUES
    ('aa000000-0001-4000-8000-000000000010',
     'google_calendar', 'events',
     '80000000-0001-4000-8000-000000000005',
     'gcal_event_q2_planning_001',
     '{"resource_type": "event", "calendar_id": "andrew@whitfield.family"}');

-- Spring break came from school iCal feed
-- Requires migration 004_connector_ical_support.sql to be applied first.
INSERT INTO connector_mappings (id, connector_name, internal_table, internal_id,
                                 external_id, metadata)
VALUES
    ('aa000000-0001-4000-8000-000000000011',
     'ical', 'events',
     '80000000-0001-4000-8000-000000000006',
     'ical_school_spring_break_2026',
     '{"resource_type": "event", "feed": "school_calendar"}');

COMMIT;

-- Seed 009: Health / Fitness
-- Realistic health summaries and activity records for the Whitfield family.
-- Requires: 009_health_fitness.sql migration applied first.
--
-- UUID reference (from foundation seed):
-- family:  a1b2c3d4-0000-4000-8000-000000000001
-- Andrew:  b1000000-0000-4000-8000-000000000001
-- Sally:   b1000000-0000-4000-8000-000000000002
-- Sadie:   b1000000-0000-4000-8000-000000000003

BEGIN;

-- ============================================================================
-- health_summaries (one week of daily summaries for Andrew + Sally)
-- ============================================================================

-- Andrew: Mon-Fri this week
INSERT INTO health_summaries (id, family_id, family_member_id, summary_date,
                                steps, active_minutes, resting_heart_rate,
                                sleep_minutes, weight_grams, source) VALUES
    ('d0000000-0001-4000-8000-000000000001',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     '2026-04-06', 8243, 42, 58, 432, 81600, 'apple_health'),
    ('d0000000-0001-4000-8000-000000000002',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     '2026-04-07', 11502, 65, 56, 421, 81500, 'apple_health'),
    ('d0000000-0001-4000-8000-000000000003',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     '2026-04-08', 6890, 28, 59, 396, 81700, 'apple_health'),
    ('d0000000-0001-4000-8000-000000000004',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     '2026-04-09', 9421, 51, 57, 445, 81500, 'apple_health');

-- Sally: Mon-Wed (manual scout entries, partial data)
INSERT INTO health_summaries (id, family_id, family_member_id, summary_date,
                                steps, active_minutes, source, notes) VALUES
    ('d0000000-0001-4000-8000-000000000005',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000002',
     '2026-04-06', 7234, 30, 'scout', 'Walking meeting in the morning'),
    ('d0000000-0001-4000-8000-000000000006',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000002',
     '2026-04-07', 9105, 45, 'scout', NULL),
    ('d0000000-0001-4000-8000-000000000007',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000002',
     '2026-04-08', 5621, 20, 'scout', 'Mostly desk day');

-- ============================================================================
-- activity_records (specific workouts/runs)
-- ============================================================================

-- Andrew: Tuesday morning run from Nike Run Club
INSERT INTO activity_records (id, family_id, family_member_id, activity_type,
                                title, started_at, ended_at, duration_seconds,
                                distance_meters, calories, source) VALUES
    ('d1000000-0001-4000-8000-000000000001',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'run', 'Tuesday Easy Run',
     '2026-04-07 06:30:00-05', '2026-04-07 07:08:00-05',
     2280, 5200, 412, 'nike_run_club');

-- Andrew: Thursday strength session
INSERT INTO activity_records (id, family_id, family_member_id, activity_type,
                                title, started_at, ended_at, duration_seconds,
                                calories, source, notes) VALUES
    ('d1000000-0001-4000-8000-000000000002',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'strength', 'Garage Lifting',
     '2026-04-09 06:00:00-05', '2026-04-09 06:45:00-05',
     2700, 280, 'scout', 'Squats, deadlifts, pull-ups');

-- Sally: Monday yoga
INSERT INTO activity_records (id, family_id, family_member_id, activity_type,
                                title, started_at, ended_at, duration_seconds,
                                source) VALUES
    ('d1000000-0001-4000-8000-000000000003',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000002',
     'yoga', 'Morning Flow',
     '2026-04-06 06:30:00-05', '2026-04-06 07:15:00-05',
     2700, 'scout');

-- Sadie: Bike ride
INSERT INTO activity_records (id, family_id, family_member_id, activity_type,
                                title, started_at, ended_at, duration_seconds,
                                distance_meters, source) VALUES
    ('d1000000-0001-4000-8000-000000000004',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000003',
     'bike', 'After-school neighborhood loop',
     '2026-04-08 16:30:00-05', '2026-04-08 17:10:00-05',
     2400, 6800, 'scout');

-- ============================================================================
-- connector_mappings — Andrew's apple_health summaries linked to external ids
-- ============================================================================

INSERT INTO connector_mappings (id, connector_name, internal_table, internal_id,
                                 external_id, metadata) VALUES
    ('aa000000-0009-4000-8000-000000000001',
     'apple_health', 'health_summaries',
     'd0000000-0001-4000-8000-000000000004',
     'apple_health_summary_andrew_2026_04_09',
     '{"resource_type": "daily_summary"}');

COMMIT;

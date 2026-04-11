-- Seed 006: Personal Tasks
-- Realistic personal tasks for Andrew (and a couple for Sally).
-- Requires: 006_personal_tasks.sql migration applied first.
--
-- UUID reference (from foundation seed):
-- family:  a1b2c3d4-0000-4000-8000-000000000001
-- Andrew:  b1000000-0000-4000-8000-000000000001
-- Sally:   b1000000-0000-4000-8000-000000000002
-- Sadie:   b1000000-0000-4000-8000-000000000003
-- Townes:  b1000000-0000-4000-8000-000000000004
-- River:   b1000000-0000-4000-8000-000000000005
--
-- Calendar event reference (from 003_calendar_seed.sql):
-- Andrew Q2 Planning Review: 80000000-0001-4000-8000-000000000005

BEGIN;

-- ============================================================================
-- Andrew's personal tasks
-- ============================================================================

-- Urgent: due today
INSERT INTO personal_tasks (id, family_id, assigned_to, created_by, title,
                             description, status, priority, due_at)
VALUES
    ('a0000000-0001-4000-8000-000000000001',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'Submit expense report',
     'March travel expenses, due to finance by EOD',
     'pending', 'urgent',
     '2026-04-09 17:00:00-05');

-- High priority: due tomorrow, linked to a calendar event
INSERT INTO personal_tasks (id, family_id, assigned_to, created_by, title,
                             description, notes, status, priority, due_at, event_id)
VALUES
    ('a0000000-0001-4000-8000-000000000002',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'Prepare Q2 planning deck',
     'Review last quarter''s metrics and draft strategic priorities',
     'Get feedback from the leadership team beforehand',
     'in_progress', 'high',
     '2026-04-13 13:00:00-05',
     '80000000-0001-4000-8000-000000000005');

-- Medium priority: due Friday
INSERT INTO personal_tasks (id, family_id, assigned_to, created_by, title,
                             description, status, priority, due_at)
VALUES
    ('a0000000-0001-4000-8000-000000000003',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'Renew car registration',
     'Tags expire end of month',
     'pending', 'medium',
     '2026-04-10 17:00:00-05');

-- Medium priority: no specific due date
INSERT INTO personal_tasks (id, family_id, assigned_to, created_by, title,
                             description, status, priority)
VALUES
    ('a0000000-0001-4000-8000-000000000004',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'Schedule annual physical',
     'Call Dr. Reed''s office',
     'pending', 'medium');

-- Low priority: no due date
INSERT INTO personal_tasks (id, family_id, assigned_to, created_by, title,
                             status, priority)
VALUES
    ('a0000000-0001-4000-8000-000000000005',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'Clean garage workbench',
     'pending', 'low');

-- A completed task for history
INSERT INTO personal_tasks (id, family_id, assigned_to, created_by, title,
                             status, priority, due_at, completed_at)
VALUES
    ('a0000000-0001-4000-8000-000000000006',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'Pay water bill',
     'done', 'high',
     '2026-04-07 17:00:00-05',
     '2026-04-07 14:30:00-05');

-- ============================================================================
-- Sally's personal tasks
-- ============================================================================

-- High priority: due Monday
INSERT INTO personal_tasks (id, family_id, assigned_to, created_by, title,
                             description, status, priority, due_at)
VALUES
    ('a0000000-0001-4000-8000-000000000007',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000002',
     'b1000000-0000-4000-8000-000000000002',
     'Confirm River''s pediatrician appointment',
     'Tuesday 4/15 at 9:30 AM — call to confirm',
     'pending', 'high',
     '2026-04-13 17:00:00-05');

-- Medium priority: ongoing
INSERT INTO personal_tasks (id, family_id, assigned_to, created_by, title,
                             status, priority)
VALUES
    ('a0000000-0001-4000-8000-000000000008',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000002',
     'b1000000-0000-4000-8000-000000000002',
     'Plan Sadie''s birthday party',
     'pending', 'medium');

COMMIT;

-- Migration 023: Session 2 block 2 — Roberts family household seed
--
-- Encodes the Roberts family's chore + routine system from
-- family_chore_system.md as data in the canonical scout.* tables.
-- All inserts are conditional on `families.name = 'Roberts'` and use
-- `WHERE NOT EXISTS` guards so the migration is fully idempotent
-- against re-run, repeated test setup, and partial prior seeds.
--
-- Encoded behavior:
--   * household_rules: one_owner_per_task, finishable_lists,
--     explicit_standards_of_done, quiet_enforcement, one_reminder_max
--   * standards_of_done: room_reset, common_area_closeout, trash
--   * routine_templates: Morning, After School, Evening per kid
--     (Sadie 13, Townes 10, River 8) with the right due_time_weekday
--     and weekend offsets per the family file
--   * routine_steps: per-kid checklist items per routine
--   * task_templates: Sadie Dishwasher Captain, Townes Table Captain,
--     River Living Room Reset Captain, Common Area Closeout (rotating),
--     Dog Walks (Sadie lead), Power 60 (weekly Saturday), Backyard
--     Poop Patrol (weekly Saturday)
--   * task_assignment_rules:
--       - fixed: per-kid ownership chores
--       - day_parity: Common Area Closeout (Townes odd / River even)
--       - dog_walk_assistant: Sadie lead, Townes odd / River even
--       - week_rotation: Backyard Poop Patrol (Townes owner / River
--         assistant, swap every 8 weeks anchored on 2026-01-05)
--   * time_blocks: morning, after_school, evening with the family's
--     local-time offsets, applies_weekday/weekend flags
--   * reward_policies: $12 Sadie, $9 Townes, $7 River with the
--     5-day Daily Win schedule
--   * reward_extras_catalog: a small starter "Extras Menu"
--
-- The seed is family-scoped — it does NOT touch any other family's
-- rows, and it does NOT modify connector tables.

BEGIN;

-- All inserts pivot on this family lookup. If no Roberts family
-- exists yet, the entire seed becomes a no-op (all WHERE clauses
-- match zero rows). The seed will activate the first time a
-- Roberts family is present in public.families.
DO $$
DECLARE
    v_family_id uuid;
    v_sadie_id uuid;
    v_townes_id uuid;
    v_river_id uuid;
    v_andrew_id uuid;
    v_sally_id uuid;
    v_morning_routine_sadie uuid;
    v_morning_routine_townes uuid;
    v_morning_routine_river uuid;
    v_after_routine_sadie uuid;
    v_after_routine_townes uuid;
    v_after_routine_river uuid;
    v_evening_routine_sadie uuid;
    v_evening_routine_townes uuid;
    v_evening_routine_river uuid;
    v_sod_room_reset uuid;
    v_sod_common_area uuid;
    v_sod_trash uuid;
    v_template_dishwasher uuid;
    v_template_table_captain uuid;
    v_template_living_reset uuid;
    v_template_common_area uuid;
    v_template_dog_walks uuid;
    v_template_power60 uuid;
    v_template_poop_patrol uuid;
    v_policy_sadie uuid;
    v_policy_townes uuid;
    v_policy_river uuid;
BEGIN
    -- Resolve Roberts family. If absent, abort the seed silently.
    SELECT id INTO v_family_id
    FROM public.families
    WHERE name ILIKE 'Roberts%'
    ORDER BY created_at ASC
    LIMIT 1;

    IF v_family_id IS NULL THEN
        RAISE NOTICE 'roberts seed skipped: no Roberts family found';
        RETURN;
    END IF;

    -- Resolve named members. Each is best-effort — if the member is
    -- missing, downstream rows that reference it become NULL or are
    -- skipped via the per-row WHERE NOT EXISTS guards.
    SELECT id INTO v_sadie_id  FROM public.family_members WHERE family_id = v_family_id AND first_name = 'Sadie'  AND is_active LIMIT 1;
    SELECT id INTO v_townes_id FROM public.family_members WHERE family_id = v_family_id AND first_name = 'Townes' AND is_active LIMIT 1;
    SELECT id INTO v_river_id  FROM public.family_members WHERE family_id = v_family_id AND first_name = 'River'  AND is_active LIMIT 1;
    SELECT id INTO v_andrew_id FROM public.family_members WHERE family_id = v_family_id AND first_name = 'Andrew' AND is_active LIMIT 1;
    SELECT id INTO v_sally_id  FROM public.family_members WHERE family_id = v_family_id AND first_name = 'Sally'  AND is_active LIMIT 1;

    -- ====================================================================
    -- household_rules — locked invariants from family_chore_system.md §1
    -- ====================================================================
    INSERT INTO scout.household_rules (family_id, rule_key, rule_value, description)
    SELECT v_family_id, rule_key, rule_value::jsonb, description
    FROM (VALUES
        ('one_owner_per_task',         'true'::text,  'If a task is shared, it is orphaned. Every task has exactly one owner.'),
        ('finishable_lists',           'true',        'Routines doable in 15 to 25 minutes per block.'),
        ('explicit_standards_of_done', 'true',        'No vague tasks. Every chore has a written standard of done.'),
        ('quiet_enforcement',          'true',        'The checklist + deadline is the boss, not parent mood.'),
        ('one_reminder_max',           'true',        'One reminder. After that: "Check Hearth." No nagging.')
    ) AS seed(rule_key, rule_value, description)
    WHERE NOT EXISTS (
        SELECT 1 FROM scout.household_rules hr
        WHERE hr.family_id = v_family_id AND hr.rule_key = seed.rule_key
    );

    -- ====================================================================
    -- standards_of_done — checklist text from family file
    -- ====================================================================
    INSERT INTO scout.standards_of_done (family_id, standard_key, label, checklist, notes)
    SELECT v_family_id, standard_key, label, checklist::jsonb, notes
    FROM (VALUES
        (
            'room_reset',
            'Room Reset',
            '["Floor mostly clear (no loose clothes/toys)","Clothes in hamper","Dishes/cups removed","Trash in trash can","Bed made (simple is fine)"]'::text,
            'Per-kid bedroom reset. Scope adjusts by age — River uses small scope.'
        ),
        (
            'common_area_closeout',
            'Common Area Closeout',
            '["Cups/plates/trash moved to kitchen","Blankets folded to basket","Toys/items put in bins","Remotes returned","Floor clear enough a robot vacuum could run"]',
            'Living room + kitchen-adjacent shared spaces.'
        ),
        (
            'trash',
            'Trash',
            '["Kitchen can checked; if ~75% full → taken out","Bag tied, taken to outdoor bin","New bag installed"]',
            'Standalone — not embedded in a routine.'
        )
    ) AS seed(standard_key, label, checklist, notes)
    WHERE NOT EXISTS (
        SELECT 1 FROM scout.standards_of_done sod
        WHERE sod.family_id = v_family_id AND sod.standard_key = seed.standard_key
    );

    SELECT id INTO v_sod_room_reset   FROM scout.standards_of_done WHERE family_id = v_family_id AND standard_key = 'room_reset';
    SELECT id INTO v_sod_common_area  FROM scout.standards_of_done WHERE family_id = v_family_id AND standard_key = 'common_area_closeout';
    SELECT id INTO v_sod_trash        FROM scout.standards_of_done WHERE family_id = v_family_id AND standard_key = 'trash';

    -- ====================================================================
    -- time_blocks — Morning / After School / Evening anchors
    -- ====================================================================
    INSERT INTO scout.time_blocks (family_id, block_key, label, start_offset, end_offset, applies_weekday, applies_weekend, sort_order)
    SELECT v_family_id, block_key, label, start_offset::interval, end_offset::interval, weekday, weekend, sort_order
    FROM (VALUES
        ('morning',     'Morning Routine',      '06:30:00', '07:30:00', true,  true,  10),
        ('after_school','After School Routine', '15:00:00', '17:30:00', true,  false, 20),
        ('evening',     'Evening Routine',      '20:00:00', '21:30:00', true,  true,  30),
        ('power_60',    'Saturday Power 60',    '10:00:00', '11:00:00', false, true,  40)
    ) AS seed(block_key, label, start_offset, end_offset, weekday, weekend, sort_order)
    WHERE NOT EXISTS (
        SELECT 1 FROM scout.time_blocks tb
        WHERE tb.family_id = v_family_id AND tb.block_key = seed.block_key
    );

    -- ====================================================================
    -- routine_templates — Morning, After School, Evening per kid
    -- ====================================================================
    -- Note: per-kid + per-block uniqueness via the constraint
    --   uq_routine_template UNIQUE (family_id, routine_key, owner_family_member_id)
    -- so we use the same routine_key across kids and let owner_family_member_id
    -- distinguish them.

    -- Morning routines
    IF v_sadie_id IS NOT NULL THEN
        INSERT INTO scout.routine_templates (family_id, routine_key, label, block_label, recurrence, due_time_weekday, due_time_weekend, owner_family_member_id)
        SELECT v_family_id, 'morning', 'Sadie Morning', 'Morning', 'daily', '07:25', '09:00', v_sadie_id
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.routine_templates
            WHERE family_id = v_family_id AND routine_key = 'morning' AND owner_family_member_id = v_sadie_id
        );
    END IF;
    IF v_townes_id IS NOT NULL THEN
        INSERT INTO scout.routine_templates (family_id, routine_key, label, block_label, recurrence, due_time_weekday, due_time_weekend, owner_family_member_id)
        SELECT v_family_id, 'morning', 'Townes Morning', 'Morning', 'daily', '07:25', '09:00', v_townes_id
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.routine_templates
            WHERE family_id = v_family_id AND routine_key = 'morning' AND owner_family_member_id = v_townes_id
        );
    END IF;
    IF v_river_id IS NOT NULL THEN
        INSERT INTO scout.routine_templates (family_id, routine_key, label, block_label, recurrence, due_time_weekday, due_time_weekend, owner_family_member_id)
        SELECT v_family_id, 'morning', 'River Morning', 'Morning', 'daily', '07:25', '09:00', v_river_id
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.routine_templates
            WHERE family_id = v_family_id AND routine_key = 'morning' AND owner_family_member_id = v_river_id
        );
    END IF;

    -- After School routines (weekdays only)
    IF v_sadie_id IS NOT NULL THEN
        INSERT INTO scout.routine_templates (family_id, routine_key, label, block_label, recurrence, due_time_weekday, owner_family_member_id)
        SELECT v_family_id, 'after_school', 'Sadie After School', 'After School', 'weekdays', '17:30', v_sadie_id
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.routine_templates
            WHERE family_id = v_family_id AND routine_key = 'after_school' AND owner_family_member_id = v_sadie_id
        );
    END IF;
    IF v_townes_id IS NOT NULL THEN
        INSERT INTO scout.routine_templates (family_id, routine_key, label, block_label, recurrence, due_time_weekday, owner_family_member_id)
        SELECT v_family_id, 'after_school', 'Townes After School', 'After School', 'weekdays', '17:30', v_townes_id
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.routine_templates
            WHERE family_id = v_family_id AND routine_key = 'after_school' AND owner_family_member_id = v_townes_id
        );
    END IF;
    IF v_river_id IS NOT NULL THEN
        INSERT INTO scout.routine_templates (family_id, routine_key, label, block_label, recurrence, due_time_weekday, owner_family_member_id)
        SELECT v_family_id, 'after_school', 'River After School', 'After School', 'weekdays', '17:30', v_river_id
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.routine_templates
            WHERE family_id = v_family_id AND routine_key = 'after_school' AND owner_family_member_id = v_river_id
        );
    END IF;

    -- Evening routines (per-kid due times from family file)
    IF v_sadie_id IS NOT NULL THEN
        INSERT INTO scout.routine_templates (family_id, routine_key, label, block_label, recurrence, due_time_weekday, due_time_weekend, owner_family_member_id)
        SELECT v_family_id, 'evening', 'Sadie Evening', 'Evening', 'daily', '21:30', '21:30', v_sadie_id
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.routine_templates
            WHERE family_id = v_family_id AND routine_key = 'evening' AND owner_family_member_id = v_sadie_id
        );
    END IF;
    IF v_townes_id IS NOT NULL THEN
        INSERT INTO scout.routine_templates (family_id, routine_key, label, block_label, recurrence, due_time_weekday, due_time_weekend, owner_family_member_id)
        SELECT v_family_id, 'evening', 'Townes Evening', 'Evening', 'daily', '21:00', '21:00', v_townes_id
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.routine_templates
            WHERE family_id = v_family_id AND routine_key = 'evening' AND owner_family_member_id = v_townes_id
        );
    END IF;
    IF v_river_id IS NOT NULL THEN
        INSERT INTO scout.routine_templates (family_id, routine_key, label, block_label, recurrence, due_time_weekday, due_time_weekend, owner_family_member_id)
        SELECT v_family_id, 'evening', 'River Evening', 'Evening', 'daily', '20:30', '20:30', v_river_id
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.routine_templates
            WHERE family_id = v_family_id AND routine_key = 'evening' AND owner_family_member_id = v_river_id
        );
    END IF;

    -- Resolve routine ids for step inserts
    SELECT id INTO v_morning_routine_sadie  FROM scout.routine_templates WHERE family_id = v_family_id AND routine_key = 'morning'      AND owner_family_member_id = v_sadie_id;
    SELECT id INTO v_morning_routine_townes FROM scout.routine_templates WHERE family_id = v_family_id AND routine_key = 'morning'      AND owner_family_member_id = v_townes_id;
    SELECT id INTO v_morning_routine_river  FROM scout.routine_templates WHERE family_id = v_family_id AND routine_key = 'morning'      AND owner_family_member_id = v_river_id;
    SELECT id INTO v_after_routine_sadie    FROM scout.routine_templates WHERE family_id = v_family_id AND routine_key = 'after_school' AND owner_family_member_id = v_sadie_id;
    SELECT id INTO v_after_routine_townes   FROM scout.routine_templates WHERE family_id = v_family_id AND routine_key = 'after_school' AND owner_family_member_id = v_townes_id;
    SELECT id INTO v_after_routine_river    FROM scout.routine_templates WHERE family_id = v_family_id AND routine_key = 'after_school' AND owner_family_member_id = v_river_id;
    SELECT id INTO v_evening_routine_sadie  FROM scout.routine_templates WHERE family_id = v_family_id AND routine_key = 'evening'      AND owner_family_member_id = v_sadie_id;
    SELECT id INTO v_evening_routine_townes FROM scout.routine_templates WHERE family_id = v_family_id AND routine_key = 'evening'      AND owner_family_member_id = v_townes_id;
    SELECT id INTO v_evening_routine_river  FROM scout.routine_templates WHERE family_id = v_family_id AND routine_key = 'evening'      AND owner_family_member_id = v_river_id;

    -- ====================================================================
    -- routine_steps — Sadie morning/after-school/evening
    -- ====================================================================
    -- Sadie morning
    IF v_morning_routine_sadie IS NOT NULL THEN
        INSERT INTO scout.routine_steps (routine_template_id, sort_order, label, standard_of_done_id)
        SELECT v_morning_routine_sadie, sort_order, label, NULL
        FROM (VALUES
            (1, 'Get dressed'),
            (2, 'Make bed'),
            (3, 'Hygiene: brush teeth, deodorant, hair'),
            (4, 'Breakfast + dish to sink/dishwasher'),
            (5, 'Backpack check (homework/device/water bottle)'),
            (6, 'Lunch check (packed or plan confirmed)')
        ) AS seed(sort_order, label)
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.routine_steps
            WHERE routine_template_id = v_morning_routine_sadie AND sort_order = seed.sort_order
        );
    END IF;

    -- Townes morning
    IF v_morning_routine_townes IS NOT NULL THEN
        INSERT INTO scout.routine_steps (routine_template_id, sort_order, label)
        SELECT v_morning_routine_townes, sort_order, label
        FROM (VALUES
            (1, 'Get dressed'),
            (2, 'Make bed'),
            (3, 'Brush teeth'),
            (4, 'Breakfast + dish away'),
            (5, 'Backpack check (homework/water bottle)'),
            (6, 'Shoes/coat at launch spot')
        ) AS seed(sort_order, label)
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.routine_steps
            WHERE routine_template_id = v_morning_routine_townes AND sort_order = seed.sort_order
        );
    END IF;

    -- River morning
    IF v_morning_routine_river IS NOT NULL THEN
        INSERT INTO scout.routine_steps (routine_template_id, sort_order, label)
        SELECT v_morning_routine_river, sort_order, label
        FROM (VALUES
            (1, 'Get dressed (clothes chosen night before)'),
            (2, 'Make bed (blanket up, pillow placed)'),
            (3, 'Brush teeth'),
            (4, 'Breakfast + dish away'),
            (5, 'Backpack + shoes at launch spot')
        ) AS seed(sort_order, label)
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.routine_steps
            WHERE routine_template_id = v_morning_routine_river AND sort_order = seed.sort_order
        );
    END IF;

    -- Sadie after school
    IF v_after_routine_sadie IS NOT NULL THEN
        INSERT INTO scout.routine_steps (routine_template_id, sort_order, label)
        SELECT v_after_routine_sadie, sort_order, label
        FROM (VALUES
            (1, 'Snack (15 min max)'),
            (2, 'Homework / Study (30 to 45 min timer)'),
            (3, '10 minute zone reset (timer)'),
            (4, 'Dog Walks led (Memphis + Willie completed)'),
            (5, 'Permission check: screens / free time only after completed')
        ) AS seed(sort_order, label)
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.routine_steps
            WHERE routine_template_id = v_after_routine_sadie AND sort_order = seed.sort_order
        );
    END IF;

    -- Townes after school
    IF v_after_routine_townes IS NOT NULL THEN
        INSERT INTO scout.routine_steps (routine_template_id, sort_order, label)
        SELECT v_after_routine_townes, sort_order, label
        FROM (VALUES
            (1, 'Snack (15 min max)'),
            (2, 'Homework / Reading (25 to 35 min timer)'),
            (3, '10 minute zone reset (timer)'),
            (4, 'Willie walk done if ODD day (with Sadie leading)')
        ) AS seed(sort_order, label)
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.routine_steps
            WHERE routine_template_id = v_after_routine_townes AND sort_order = seed.sort_order
        );
    END IF;

    -- River after school
    IF v_after_routine_river IS NOT NULL THEN
        INSERT INTO scout.routine_steps (routine_template_id, sort_order, label)
        SELECT v_after_routine_river, sort_order, label
        FROM (VALUES
            (1, 'Snack (15 min max)'),
            (2, 'Homework / Reading (15 to 25 min timer)'),
            (3, '10 minute zone reset (timer)'),
            (4, 'Willie walk done if EVEN day (with Sadie leading)')
        ) AS seed(sort_order, label)
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.routine_steps
            WHERE routine_template_id = v_after_routine_river AND sort_order = seed.sort_order
        );
    END IF;

    -- Sadie evening (room reset linked to standard_of_done)
    IF v_evening_routine_sadie IS NOT NULL THEN
        INSERT INTO scout.routine_steps (routine_template_id, sort_order, label, standard_of_done_id)
        SELECT v_evening_routine_sadie, sort_order, label, sod_id
        FROM (VALUES
            (1, 'Pack backpack for tomorrow', NULL::uuid),
            (2, 'Outfit set out',              NULL),
            (3, 'Room reset (standard of done)', v_sod_room_reset),
            (4, 'Hygiene',                     NULL),
            (5, 'Devices to charging station', NULL)
        ) AS seed(sort_order, label, sod_id)
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.routine_steps
            WHERE routine_template_id = v_evening_routine_sadie AND sort_order = seed.sort_order
        );
    END IF;

    -- Townes evening
    IF v_evening_routine_townes IS NOT NULL THEN
        INSERT INTO scout.routine_steps (routine_template_id, sort_order, label, standard_of_done_id)
        SELECT v_evening_routine_townes, sort_order, label, sod_id
        FROM (VALUES
            (1, 'Pack backpack',               NULL::uuid),
            (2, 'Outfit set out',              NULL),
            (3, 'Room reset',                  v_sod_room_reset),
            (4, 'Brush teeth',                 NULL),
            (5, 'Devices to charging station', NULL)
        ) AS seed(sort_order, label, sod_id)
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.routine_steps
            WHERE routine_template_id = v_evening_routine_townes AND sort_order = seed.sort_order
        );
    END IF;

    -- River evening
    IF v_evening_routine_river IS NOT NULL THEN
        INSERT INTO scout.routine_steps (routine_template_id, sort_order, label, standard_of_done_id)
        SELECT v_evening_routine_river, sort_order, label, sod_id
        FROM (VALUES
            (1, 'Outfit set out (parent check if needed)', NULL::uuid),
            (2, 'Backpack packed',                         NULL),
            (3, 'Room reset (small scope)',                v_sod_room_reset),
            (4, 'Brush teeth',                             NULL),
            (5, 'Devices to charging station',             NULL)
        ) AS seed(sort_order, label, sod_id)
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.routine_steps
            WHERE routine_template_id = v_evening_routine_river AND sort_order = seed.sort_order
        );
    END IF;

    -- ====================================================================
    -- task_templates — ownership chores + rotating + dog walks + Power 60
    --                  + Backyard Poop Patrol
    -- ====================================================================

    INSERT INTO scout.task_templates (family_id, template_key, label, recurrence, due_time, standard_of_done_id, notes, is_active)
    SELECT v_family_id, template_key, label, recurrence, due_time::time, sod_id, notes, true
    FROM (VALUES
        ('dishwasher_captain',   'Dishwasher Captain (Sadie)',         'weekdays', '20:00', NULL::uuid, 'Sadie ownership chore. Choose Option A (load + run after dinner) or Option B (unload at 7:10 AM) and keep consistent for 6-8 weeks.'),
        ('table_captain',        'Table Captain + Sweep (Townes)',     'weekdays', '20:00', NULL,        'Townes ownership chore. Set table 6:15 PM, clear after dinner 7:45 PM, sweep kitchen/dining 8:00 PM.'),
        ('living_room_reset',    'Living Room Reset Captain (River)',  'weekdays', '19:30', NULL,        'River ownership chore. Blankets, toys, dishes to kitchen.'),
        ('common_area_closeout', 'Common Area Closeout (rotating)',    'daily',    '19:30', v_sod_common_area, 'ODD day = Townes, EVEN day = River. Charter §rotating chore.'),
        ('dog_walks',            'Dog Walks (Sadie lead)',             'daily',    '19:30', NULL,        'Sadie lead. Memphis 15 to 20 min, Willie 10 to 15 min. Assistant rule: ODD day = Townes, EVEN day = River.'),
        ('power_60',             'Power 60 (House Reset)',             'weekly',   '11:00', NULL,        'Saturday 10 to 11 AM. Sadie bathroom, Townes vacuum, River dust.'),
        ('poop_patrol',          'Backyard Poop Patrol',               'weekly',   '11:00', NULL,        'Saturday during Power 60. Owner/assistant swap every 8 weeks.')
    ) AS seed(template_key, label, recurrence, due_time, sod_id, notes)
    WHERE NOT EXISTS (
        SELECT 1 FROM scout.task_templates tt
        WHERE tt.family_id = v_family_id AND tt.template_key = seed.template_key
    );

    SELECT id INTO v_template_dishwasher    FROM scout.task_templates WHERE family_id = v_family_id AND template_key = 'dishwasher_captain';
    SELECT id INTO v_template_table_captain FROM scout.task_templates WHERE family_id = v_family_id AND template_key = 'table_captain';
    SELECT id INTO v_template_living_reset  FROM scout.task_templates WHERE family_id = v_family_id AND template_key = 'living_room_reset';
    SELECT id INTO v_template_common_area   FROM scout.task_templates WHERE family_id = v_family_id AND template_key = 'common_area_closeout';
    SELECT id INTO v_template_dog_walks     FROM scout.task_templates WHERE family_id = v_family_id AND template_key = 'dog_walks';
    SELECT id INTO v_template_power60       FROM scout.task_templates WHERE family_id = v_family_id AND template_key = 'power_60';
    SELECT id INTO v_template_poop_patrol   FROM scout.task_templates WHERE family_id = v_family_id AND template_key = 'poop_patrol';

    -- ====================================================================
    -- task_assignment_rules — fixed / day_parity / dog_walk_assistant / week_rotation
    -- ====================================================================

    -- Fixed: Sadie owns Dishwasher Captain
    IF v_template_dishwasher IS NOT NULL AND v_sadie_id IS NOT NULL THEN
        INSERT INTO scout.task_assignment_rules (task_template_id, rule_type, rule_params, priority)
        SELECT v_template_dishwasher, 'fixed', jsonb_build_object('family_member_id', v_sadie_id::text), 0
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.task_assignment_rules WHERE task_template_id = v_template_dishwasher
        );
    END IF;

    -- Fixed: Townes owns Table Captain
    IF v_template_table_captain IS NOT NULL AND v_townes_id IS NOT NULL THEN
        INSERT INTO scout.task_assignment_rules (task_template_id, rule_type, rule_params, priority)
        SELECT v_template_table_captain, 'fixed', jsonb_build_object('family_member_id', v_townes_id::text), 0
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.task_assignment_rules WHERE task_template_id = v_template_table_captain
        );
    END IF;

    -- Fixed: River owns Living Room Reset
    IF v_template_living_reset IS NOT NULL AND v_river_id IS NOT NULL THEN
        INSERT INTO scout.task_assignment_rules (task_template_id, rule_type, rule_params, priority)
        SELECT v_template_living_reset, 'fixed', jsonb_build_object('family_member_id', v_river_id::text), 0
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.task_assignment_rules WHERE task_template_id = v_template_living_reset
        );
    END IF;

    -- day_parity: Common Area Closeout
    IF v_template_common_area IS NOT NULL AND v_townes_id IS NOT NULL AND v_river_id IS NOT NULL THEN
        INSERT INTO scout.task_assignment_rules (task_template_id, rule_type, rule_params, priority)
        SELECT v_template_common_area, 'day_parity',
               jsonb_build_object('odd', v_townes_id::text, 'even', v_river_id::text),
               0
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.task_assignment_rules WHERE task_template_id = v_template_common_area
        );
    END IF;

    -- dog_walk_assistant: Sadie lead, Townes odd / River even
    IF v_template_dog_walks IS NOT NULL AND v_sadie_id IS NOT NULL AND v_townes_id IS NOT NULL AND v_river_id IS NOT NULL THEN
        INSERT INTO scout.task_assignment_rules (task_template_id, rule_type, rule_params, priority)
        SELECT v_template_dog_walks, 'dog_walk_assistant',
               jsonb_build_object('lead', v_sadie_id::text, 'odd', v_townes_id::text, 'even', v_river_id::text),
               0
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.task_assignment_rules WHERE task_template_id = v_template_dog_walks
        );
    END IF;

    -- Power 60 — fixed Sadie owner per family file (family does it together but Sadie owns the bathroom block)
    IF v_template_power60 IS NOT NULL AND v_sadie_id IS NOT NULL THEN
        INSERT INTO scout.task_assignment_rules (task_template_id, rule_type, rule_params, priority)
        SELECT v_template_power60, 'fixed', jsonb_build_object('family_member_id', v_sadie_id::text), 0
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.task_assignment_rules WHERE task_template_id = v_template_power60
        );
    END IF;

    -- week_rotation: Backyard Poop Patrol — Townes owner, River assistant, swap every 8 weeks anchored on 2026-01-05 (Monday)
    IF v_template_poop_patrol IS NOT NULL AND v_townes_id IS NOT NULL AND v_river_id IS NOT NULL THEN
        INSERT INTO scout.task_assignment_rules (task_template_id, rule_type, rule_params, priority)
        SELECT v_template_poop_patrol, 'week_rotation',
               jsonb_build_object(
                   'owner', v_townes_id::text,
                   'assistant', v_river_id::text,
                   'period_weeks', 8,
                   'anchor_date', '2026-01-05'
               ),
               0
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.task_assignment_rules WHERE task_template_id = v_template_poop_patrol
        );
    END IF;

    -- ====================================================================
    -- reward_policies — baseline allowance per kid
    -- ====================================================================
    -- charter §Greenlight Allowance: $12 Sadie, $9 Townes, $7 River
    -- Mon-Fri Daily Wins → 100% / 80% / 60% / 0% schedule

    IF v_sadie_id IS NOT NULL THEN
        INSERT INTO scout.reward_policies (family_id, family_member_id, policy_key, baseline_amount_cents, payout_schedule, wins_required, extras_allowed, effective_from)
        SELECT v_family_id, v_sadie_id, 'weekly_allowance', 1200,
               '{"5_wins": 100, "4_wins": 80, "3_wins": 60, "less": 0}'::jsonb,
               '[{"type": "daily_win", "count": 5}]'::jsonb,
               true, '2026-01-01'
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.reward_policies
            WHERE family_id = v_family_id AND family_member_id = v_sadie_id AND policy_key = 'weekly_allowance'
        );
    END IF;
    IF v_townes_id IS NOT NULL THEN
        INSERT INTO scout.reward_policies (family_id, family_member_id, policy_key, baseline_amount_cents, payout_schedule, wins_required, extras_allowed, effective_from)
        SELECT v_family_id, v_townes_id, 'weekly_allowance', 900,
               '{"5_wins": 100, "4_wins": 80, "3_wins": 60, "less": 0}'::jsonb,
               '[{"type": "daily_win", "count": 5}]'::jsonb,
               true, '2026-01-01'
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.reward_policies
            WHERE family_id = v_family_id AND family_member_id = v_townes_id AND policy_key = 'weekly_allowance'
        );
    END IF;
    IF v_river_id IS NOT NULL THEN
        INSERT INTO scout.reward_policies (family_id, family_member_id, policy_key, baseline_amount_cents, payout_schedule, wins_required, extras_allowed, effective_from)
        SELECT v_family_id, v_river_id, 'weekly_allowance', 700,
               '{"5_wins": 100, "4_wins": 80, "3_wins": 60, "less": 0}'::jsonb,
               '[{"type": "daily_win", "count": 5}]'::jsonb,
               true, '2026-01-01'
        WHERE NOT EXISTS (
            SELECT 1 FROM scout.reward_policies
            WHERE family_id = v_family_id AND family_member_id = v_river_id AND policy_key = 'weekly_allowance'
        );
    END IF;

    -- ====================================================================
    -- reward_extras_catalog — small starter "Extras Menu"
    -- ====================================================================
    INSERT INTO scout.reward_extras_catalog (family_id, extra_key, label, amount_cents, notes, is_active)
    SELECT v_family_id, extra_key, label, amount_cents, notes, true
    FROM (VALUES
        ('extra_yard',   'Yard work — extras (raking, weeding, trimming)', 500, 'Per session, with photo.'),
        ('extra_garage', 'Garage organize / tidy session',                  500, 'Per session, parent-approved.'),
        ('extra_dishes', 'Big sink session beyond ownership chore',         200, 'Only when sink is overloaded.')
    ) AS seed(extra_key, label, amount_cents, notes)
    WHERE NOT EXISTS (
        SELECT 1 FROM scout.reward_extras_catalog
        WHERE family_id = v_family_id AND extra_key = seed.extra_key
    );

    RAISE NOTICE 'roberts seed applied for family %', v_family_id;
END $$;

COMMIT;

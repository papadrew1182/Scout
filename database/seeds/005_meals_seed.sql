-- Seed 005: Meals
-- Realistic fake meal data for the Roberts household.
-- Requires: 005_meals.sql migration applied first.
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
-- meal_plans (one weekly plan: week of 2026-04-06)
-- ============================================================================

INSERT INTO meal_plans (id, family_id, created_by, week_start, notes)
VALUES
    ('90000000-0001-4000-8000-000000000001',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000002',
     '2026-04-06',
     'Lighter dinners this week — Sally has late meetings Tuesday and Thursday');

-- ============================================================================
-- meals (Mon-Fri breakfast/lunch/dinner for week of 2026-04-06)
-- ============================================================================

-- Monday 2026-04-06
INSERT INTO meals (id, family_id, meal_plan_id, created_by, meal_date, meal_type, title, description) VALUES
    ('91000000-0406-4000-8000-000000000001', 'a1b2c3d4-0000-4000-8000-000000000001',
     '90000000-0001-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000002',
     '2026-04-06', 'breakfast', 'Oatmeal & Berries', 'Steel-cut oats with strawberries and brown sugar'),
    ('91000000-0406-4000-8000-000000000002', 'a1b2c3d4-0000-4000-8000-000000000001',
     '90000000-0001-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000002',
     '2026-04-06', 'lunch', 'Turkey Sandwiches', 'Packed lunches for school'),
    ('91000000-0406-4000-8000-000000000003', 'a1b2c3d4-0000-4000-8000-000000000001',
     '90000000-0001-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000002',
     '2026-04-06', 'dinner', 'Sheet Pan Chicken', 'Chicken thighs with roasted vegetables');

-- Tuesday 2026-04-07
INSERT INTO meals (id, family_id, meal_plan_id, created_by, meal_date, meal_type, title, description) VALUES
    ('91000000-0407-4000-8000-000000000001', 'a1b2c3d4-0000-4000-8000-000000000001',
     '90000000-0001-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000002',
     '2026-04-07', 'breakfast', 'Yogurt Parfaits', 'Greek yogurt, granola, honey'),
    ('91000000-0407-4000-8000-000000000002', 'a1b2c3d4-0000-4000-8000-000000000001',
     '90000000-0001-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000002',
     '2026-04-07', 'lunch', 'Bento Boxes', 'Crackers, cheese, fruit, veggies'),
    ('91000000-0407-4000-8000-000000000003', 'a1b2c3d4-0000-4000-8000-000000000001',
     '90000000-0001-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000002',
     '2026-04-07', 'dinner', 'Taco Tuesday', 'Ground turkey, all the fixings');

-- Wednesday 2026-04-08
INSERT INTO meals (id, family_id, meal_plan_id, created_by, meal_date, meal_type, title, description) VALUES
    ('91000000-0408-4000-8000-000000000001', 'a1b2c3d4-0000-4000-8000-000000000001',
     '90000000-0001-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000002',
     '2026-04-08', 'breakfast', 'Scrambled Eggs', 'With toast and orange slices'),
    ('91000000-0408-4000-8000-000000000002', 'a1b2c3d4-0000-4000-8000-000000000001',
     '90000000-0001-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000002',
     '2026-04-08', 'lunch', 'Pasta Salad', 'Cold pasta with veggies and Italian dressing'),
    ('91000000-0408-4000-8000-000000000003', 'a1b2c3d4-0000-4000-8000-000000000001',
     '90000000-0001-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000002',
     '2026-04-08', 'dinner', 'Spaghetti & Meatballs', 'Family favorite with garlic bread');

-- Thursday 2026-04-09 (today)
INSERT INTO meals (id, family_id, meal_plan_id, created_by, meal_date, meal_type, title, description, notes) VALUES
    ('91000000-0409-4000-8000-000000000001', 'a1b2c3d4-0000-4000-8000-000000000001',
     '90000000-0001-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000002',
     '2026-04-09', 'breakfast', 'Pancakes', 'Buttermilk pancakes with maple syrup', NULL),
    ('91000000-0409-4000-8000-000000000002', 'a1b2c3d4-0000-4000-8000-000000000001',
     '90000000-0001-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000002',
     '2026-04-09', 'lunch', 'PB&J', 'Classic peanut butter and jelly', 'River prefers crusts off'),
    ('91000000-0409-4000-8000-000000000003', 'a1b2c3d4-0000-4000-8000-000000000001',
     '90000000-0001-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000002',
     '2026-04-09', 'dinner', 'Leftovers Night', 'Clean out the fridge', 'Sally has a late meeting');

-- Friday 2026-04-10
INSERT INTO meals (id, family_id, meal_plan_id, created_by, meal_date, meal_type, title, description) VALUES
    ('91000000-0410-4000-8000-000000000001', 'a1b2c3d4-0000-4000-8000-000000000001',
     '90000000-0001-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000002',
     '2026-04-10', 'breakfast', 'Cereal Bar', 'Self-serve cereal & milk'),
    ('91000000-0410-4000-8000-000000000002', 'a1b2c3d4-0000-4000-8000-000000000001',
     '90000000-0001-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000002',
     '2026-04-10', 'lunch', 'Pizza Lunchables', 'Friday treat lunches'),
    ('91000000-0410-4000-8000-000000000003', 'a1b2c3d4-0000-4000-8000-000000000001',
     '90000000-0001-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000002',
     '2026-04-10', 'dinner', 'Family Dinner with Grandparents', 'Andrew is grilling steaks');

-- ============================================================================
-- dietary_preferences (sample for kids only)
-- ============================================================================

INSERT INTO dietary_preferences (id, family_member_id, label, kind, notes) VALUES
    ('92000000-0001-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000004',
     'mushrooms', 'preference', 'Townes does not like mushrooms in anything'),
    ('92000000-0001-4000-8000-000000000002',
     'b1000000-0000-4000-8000-000000000005',
     'tree_nuts', 'allergy', 'River — strict avoidance, EpiPen at school');

COMMIT;

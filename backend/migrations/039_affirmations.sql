-- Migration 039: Affirmations feature
--
-- Creates three tables in the scout schema:
--   1. scout.affirmations        — content library
--   2. scout.affirmation_feedback — user reactions (heart/thumbs_down/skip/reshow)
--   3. scout.affirmation_delivery_log — delivery tracking for cooldown + analytics
--
-- Also:
--   - Inserts the affirmations.manage_config permission key
--   - Grants it to PRIMARY_PARENT and ADMIN tiers
--   - Seeds 25 starter affirmations across categories/tones/audiences
--
-- All DDL is guarded with IF NOT EXISTS so the migration is safe to re-run.

BEGIN;

-- 1. Content library
CREATE TABLE IF NOT EXISTS scout.affirmations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    text            TEXT NOT NULL,
    category        TEXT,
    tags            JSONB NOT NULL DEFAULT '[]'::jsonb,
    tone            TEXT,
    philosophy      TEXT,
    audience_type   TEXT NOT NULL DEFAULT 'general',
    length_class    TEXT NOT NULL DEFAULT 'short',
    active          BOOLEAN NOT NULL DEFAULT true,
    source_type     TEXT NOT NULL DEFAULT 'curated',
    created_by      UUID REFERENCES family_members(id) ON DELETE SET NULL,
    updated_by      UUID REFERENCES family_members(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Feedback (reactions)
CREATE TABLE IF NOT EXISTS scout.affirmation_feedback (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_member_id    UUID NOT NULL REFERENCES family_members(id) ON DELETE CASCADE,
    affirmation_id      UUID NOT NULL REFERENCES scout.affirmations(id) ON DELETE CASCADE,
    reaction_type       TEXT NOT NULL CHECK (reaction_type IN ('heart', 'thumbs_down', 'skip', 'reshow')),
    context             TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_affirmation_feedback_member
    ON scout.affirmation_feedback (family_member_id, affirmation_id, created_at DESC);

-- 3. Delivery log
CREATE TABLE IF NOT EXISTS scout.affirmation_delivery_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_member_id    UUID NOT NULL REFERENCES family_members(id) ON DELETE CASCADE,
    affirmation_id      UUID NOT NULL REFERENCES scout.affirmations(id) ON DELETE CASCADE,
    surfaced_at         TIMESTAMPTZ NOT NULL,
    surfaced_in         TEXT NOT NULL,
    dismissed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_affirmation_delivery_member_time
    ON scout.affirmation_delivery_log (family_member_id, surfaced_at DESC);

-- 4. Permission key
INSERT INTO scout.permissions (key, description)
VALUES ('affirmations.manage_config', 'Manage affirmation library, rules, targeting, and analytics')
ON CONFLICT (key) DO NOTHING;

-- Grant to PRIMARY_PARENT and ADMIN tiers
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('PRIMARY_PARENT', 'ADMIN')
  AND p.key = 'affirmations.manage_config'
ON CONFLICT DO NOTHING;

-- 5. Seed starter affirmations (25 across categories/tones/audiences)
INSERT INTO scout.affirmations (text, category, tone, philosophy, audience_type, length_class) VALUES
-- Encouraging / Growth
('You are building something that matters.', 'growth', 'encouraging', 'discipline', 'general', 'short'),
('Every small step today adds up to something big tomorrow.', 'growth', 'encouraging', 'resilience', 'general', 'short'),
('Your effort today is shaping who you become.', 'growth', 'encouraging', 'discipline', 'general', 'short'),
('Progress is progress, no matter how small.', 'growth', 'encouraging', 'gratitude', 'general', 'short'),
-- Encouraging / Gratitude
('There is always something to be thankful for.', 'gratitude', 'encouraging', 'gratitude', 'general', 'short'),
('The people around you are a gift. Tell them.', 'gratitude', 'encouraging', 'family-first', 'parent', 'short'),
('Gratitude turns what we have into enough.', 'gratitude', 'reflective', 'gratitude', 'general', 'short'),
-- Challenging / Discipline
('Hard work compounds. Show up again today.', 'discipline', 'challenging', 'discipline', 'general', 'short'),
('Comfort is the enemy of growth. Push a little further.', 'discipline', 'challenging', 'resilience', 'parent', 'short'),
('What you do when no one is watching defines you.', 'discipline', 'challenging', 'discipline', 'general', 'short'),
-- Reflective / Resilience
('Tough days build tough people.', 'resilience', 'reflective', 'resilience', 'general', 'short'),
('You have survived every hard day so far. That is 100%% success.', 'resilience', 'reflective', 'resilience', 'general', 'short'),
('Storms do not last forever. Neither does this.', 'resilience', 'reflective', 'resilience', 'general', 'short'),
-- Practical / Family
('A kind word at breakfast sets the tone for the whole day.', 'family', 'practical', 'family-first', 'parent', 'short'),
('Ask your kids one real question today. Then listen.', 'family', 'practical', 'family-first', 'parent', 'short'),
('Showing up is the most important thing you can do as a parent.', 'family', 'encouraging', 'family-first', 'parent', 'short'),
-- Child-targeted
('You can do hard things.', 'growth', 'encouraging', 'resilience', 'child', 'short'),
('Being kind is always the right choice.', 'kindness', 'encouraging', 'gratitude', 'child', 'short'),
('Mistakes help you learn. Keep trying.', 'growth', 'encouraging', 'resilience', 'child', 'short'),
('Your family is proud of you.', 'family', 'encouraging', 'family-first', 'child', 'short'),
('Doing your best is always enough.', 'growth', 'encouraging', 'discipline', 'child', 'short'),
-- Faith-based
('You are fearfully and wonderfully made.', 'faith', 'encouraging', 'faith-based', 'general', 'short'),
('Let your light shine before others.', 'faith', 'encouraging', 'faith-based', 'general', 'short'),
-- Medium length
('The way you handle today''s small frustrations is practice for life''s bigger challenges. Stay steady.', 'resilience', 'reflective', 'resilience', 'parent', 'medium'),
('Your children are watching how you treat yourself. Model grace, patience, and persistence.', 'family', 'reflective', 'family-first', 'parent', 'medium');

COMMIT;

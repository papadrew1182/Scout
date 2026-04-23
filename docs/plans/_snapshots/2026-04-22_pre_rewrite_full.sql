--
-- PostgreSQL database dump
--

\restrict fraiDJtPATubgn6kbqfyb0jPLkeOTlEyUFWVuV5bh623guEe0epToeE37OukaYX

-- Dumped from database version 18.3 (Debian 18.3-1.pgdg13+1)
-- Dumped by pg_dump version 18.3

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: connector_apple_health; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA connector_apple_health;


--
-- Name: connector_google_calendar; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA connector_google_calendar;


--
-- Name: connector_greenlight; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA connector_greenlight;


--
-- Name: connector_nike_run_club; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA connector_nike_run_club;


--
-- Name: connector_rex; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA connector_rex;


--
-- Name: connector_ynab; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA connector_ynab;


--
-- Name: scout; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA scout;


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: _connector_mappings_default_object_type(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public._connector_mappings_default_object_type() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.external_object_type IS NULL THEN
        NEW.external_object_type := NEW.internal_table;
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: _scout_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public._scout_migrations (
    filename text NOT NULL,
    applied_at timestamp with time zone DEFAULT now()
);


--
-- Name: activity_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.activity_records (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    family_member_id uuid NOT NULL,
    activity_type text NOT NULL,
    title text,
    started_at timestamp with time zone NOT NULL,
    ended_at timestamp with time zone,
    duration_seconds integer,
    distance_meters integer,
    calories integer,
    source text DEFAULT 'scout'::text NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_activity_records_activity_type CHECK ((activity_type = ANY (ARRAY['run'::text, 'walk'::text, 'bike'::text, 'swim'::text, 'strength'::text, 'yoga'::text, 'other'::text]))),
    CONSTRAINT chk_activity_records_calories_nonneg CHECK (((calories IS NULL) OR (calories >= 0))),
    CONSTRAINT chk_activity_records_distance_nonneg CHECK (((distance_meters IS NULL) OR (distance_meters >= 0))),
    CONSTRAINT chk_activity_records_duration_nonneg CHECK (((duration_seconds IS NULL) OR (duration_seconds >= 0))),
    CONSTRAINT chk_activity_records_source CHECK ((source = ANY (ARRAY['scout'::text, 'apple_health'::text, 'nike_run_club'::text]))),
    CONSTRAINT chk_activity_records_time_order CHECK (((ended_at IS NULL) OR (ended_at >= started_at)))
);


--
-- Name: ai_conversations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_conversations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    family_member_id uuid NOT NULL,
    surface text DEFAULT 'personal'::text NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    conversation_kind text DEFAULT 'chat'::text NOT NULL,
    title text,
    last_active_at timestamp with time zone DEFAULT now() NOT NULL,
    is_pinned boolean DEFAULT false NOT NULL,
    CONSTRAINT chk_ai_conversations_kind CHECK ((conversation_kind = ANY (ARRAY['chat'::text, 'tool'::text, 'mixed'::text, 'moderation'::text]))),
    CONSTRAINT chk_ai_conversations_status CHECK ((status = ANY (ARRAY['active'::text, 'archived'::text, 'ended'::text]))),
    CONSTRAINT chk_ai_conversations_surface CHECK ((surface = ANY (ARRAY['personal'::text, 'parent'::text, 'child'::text])))
);


--
-- Name: ai_daily_insights; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_daily_insights (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    insight_type text NOT NULL,
    as_of_date date NOT NULL,
    status text NOT NULL,
    content text NOT NULL,
    model text,
    input_tokens integer,
    output_tokens integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_ai_daily_insights_type CHECK ((insight_type = 'off_track'::text))
);


--
-- Name: ai_homework_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_homework_sessions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    member_id uuid NOT NULL,
    conversation_id uuid,
    subject text DEFAULT 'other'::text NOT NULL,
    summary text,
    grade_level_at_time text,
    started_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    ended_at timestamp with time zone,
    turn_count integer DEFAULT 1 NOT NULL,
    session_length_sec integer,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    CONSTRAINT chk_homework_subject CHECK ((subject = ANY (ARRAY['math'::text, 'reading'::text, 'writing'::text, 'science'::text, 'history'::text, 'language'::text, 'other'::text])))
);


--
-- Name: ai_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    conversation_id uuid NOT NULL,
    role text NOT NULL,
    content text,
    tool_calls jsonb,
    tool_results jsonb,
    model text,
    token_usage jsonb,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    metadata jsonb,
    CONSTRAINT chk_ai_messages_role CHECK ((role = ANY (ARRAY['user'::text, 'assistant'::text, 'system'::text, 'tool'::text])))
);


--
-- Name: ai_tool_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_tool_audit (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    actor_member_id uuid NOT NULL,
    conversation_id uuid,
    tool_name text NOT NULL,
    arguments jsonb DEFAULT '{}'::jsonb NOT NULL,
    result_summary text,
    target_entity text,
    target_id uuid,
    status text DEFAULT 'success'::text NOT NULL,
    error_message text,
    duration_ms integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_ai_tool_audit_status CHECK ((status = ANY (ARRAY['success'::text, 'error'::text, 'denied'::text, 'confirmation_required'::text, 'moderation_blocked'::text])))
);


--
-- Name: allowance_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.allowance_ledger (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    family_member_id uuid NOT NULL,
    entry_type text NOT NULL,
    amount_cents integer NOT NULL,
    week_start date,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_allowance_ledger_entry_type CHECK ((entry_type = ANY (ARRAY['weekly_payout'::text, 'school_reward'::text, 'extra'::text, 'adjustment'::text]))),
    CONSTRAINT chk_allowance_ledger_week_start_monday CHECK (((week_start IS NULL) OR (EXTRACT(isodow FROM week_start) = (1)::numeric))),
    CONSTRAINT chk_allowance_ledger_weekly_payout CHECK (((entry_type <> 'weekly_payout'::text) OR (week_start IS NOT NULL)))
);


--
-- Name: bills; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bills (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    created_by uuid,
    title text NOT NULL,
    description text,
    notes text,
    amount_cents integer NOT NULL,
    due_date date NOT NULL,
    status text DEFAULT 'upcoming'::text NOT NULL,
    paid_at timestamp with time zone,
    source text DEFAULT 'scout'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_bills_amount_nonneg CHECK ((amount_cents >= 0)),
    CONSTRAINT chk_bills_paid_consistency CHECK ((((status = 'paid'::text) AND (paid_at IS NOT NULL)) OR ((status <> 'paid'::text) AND (paid_at IS NULL)))),
    CONSTRAINT chk_bills_source CHECK ((source = ANY (ARRAY['scout'::text, 'ynab'::text]))),
    CONSTRAINT chk_bills_status CHECK ((status = ANY (ARRAY['upcoming'::text, 'paid'::text, 'overdue'::text, 'cancelled'::text]))),
    CONSTRAINT chk_bills_title_not_blank CHECK ((length(btrim(title)) > 0))
);


--
-- Name: chore_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chore_templates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    name text NOT NULL,
    description text,
    recurrence text DEFAULT 'daily'::text NOT NULL,
    due_time time without time zone NOT NULL,
    assignment_type text NOT NULL,
    assignment_rule jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    included jsonb DEFAULT '[]'::jsonb,
    not_included jsonb DEFAULT '[]'::jsonb,
    done_means_done text,
    supplies jsonb DEFAULT '[]'::jsonb,
    photo_example_url text,
    estimated_duration_minutes integer,
    consequence_on_miss text,
    CONSTRAINT chk_chore_templates_assignment_type CHECK ((assignment_type = ANY (ARRAY['fixed'::text, 'rotating_daily'::text, 'rotating_weekly'::text]))),
    CONSTRAINT chk_chore_templates_recurrence CHECK ((recurrence = ANY (ARRAY['daily'::text, 'weekdays'::text, 'weekends'::text, 'weekly'::text])))
);


--
-- Name: connector_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.connector_configs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid,
    family_member_id uuid,
    connector_name text NOT NULL,
    auth_token text,
    refresh_token text,
    config jsonb DEFAULT '{}'::jsonb NOT NULL,
    scope text NOT NULL,
    sync_direction text NOT NULL,
    authority_level text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_connector_configs_authority_level CHECK ((authority_level = ANY (ARRAY['source_of_truth'::text, 'secondary'::text]))),
    CONSTRAINT chk_connector_configs_connector_name CHECK ((connector_name = ANY (ARRAY['google_calendar'::text, 'hearth'::text, 'hearth_display'::text, 'greenlight'::text, 'rex'::text, 'ynab'::text, 'apple_health'::text, 'nike_run_club'::text, 'google_maps'::text, 'exxir'::text, 'ical'::text]))),
    CONSTRAINT chk_connector_configs_scope CHECK ((scope = ANY (ARRAY['family'::text, 'member'::text]))),
    CONSTRAINT chk_connector_configs_scope_family CHECK (((scope <> 'family'::text) OR ((family_id IS NOT NULL) AND (family_member_id IS NULL)))),
    CONSTRAINT chk_connector_configs_scope_member CHECK (((scope <> 'member'::text) OR ((family_member_id IS NOT NULL) AND (family_id IS NULL)))),
    CONSTRAINT chk_connector_configs_sync_direction CHECK ((sync_direction = ANY (ARRAY['read'::text, 'write'::text, 'bidirectional'::text])))
);


--
-- Name: connector_mappings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.connector_mappings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    connector_name text NOT NULL,
    internal_table text NOT NULL,
    internal_id uuid NOT NULL,
    external_id text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    external_object_type text NOT NULL,
    family_id uuid,
    user_account_id uuid,
    CONSTRAINT chk_connector_mappings_connector_name CHECK ((connector_name = ANY (ARRAY['google_calendar'::text, 'hearth'::text, 'hearth_display'::text, 'greenlight'::text, 'rex'::text, 'ynab'::text, 'apple_health'::text, 'nike_run_club'::text, 'google_maps'::text, 'exxir'::text, 'ical'::text])))
);


--
-- Name: daily_wins; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.daily_wins (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    family_member_id uuid NOT NULL,
    win_date date NOT NULL,
    is_win boolean NOT NULL,
    task_count integer NOT NULL,
    completed_count integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_daily_wins_counts CHECK (((completed_count >= 0) AND (completed_count <= task_count) AND (task_count >= 0))),
    CONSTRAINT chk_daily_wins_weekday CHECK (((EXTRACT(isodow FROM win_date) >= (1)::numeric) AND (EXTRACT(isodow FROM win_date) <= (5)::numeric)))
);


--
-- Name: dietary_preferences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dietary_preferences (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_member_id uuid NOT NULL,
    label text NOT NULL,
    kind text NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_dietary_preferences_kind CHECK ((kind = ANY (ARRAY['preference'::text, 'restriction'::text, 'allergy'::text])))
);


--
-- Name: event_attendees; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.event_attendees (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    event_id uuid NOT NULL,
    family_member_id uuid NOT NULL,
    response_status text DEFAULT 'pending'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_event_attendees_response_status CHECK ((response_status = ANY (ARRAY['pending'::text, 'accepted'::text, 'declined'::text, 'tentative'::text])))
);


--
-- Name: events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    created_by uuid,
    title text NOT NULL,
    description text,
    location text,
    starts_at timestamp with time zone NOT NULL,
    ends_at timestamp with time zone NOT NULL,
    all_day boolean DEFAULT false NOT NULL,
    recurrence_rule text,
    recurrence_parent_id uuid,
    recurrence_instance_date date,
    source text DEFAULT 'scout'::text NOT NULL,
    is_hearth_visible boolean DEFAULT true NOT NULL,
    task_instance_id uuid,
    is_cancelled boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_events_edited_instance CHECK ((((recurrence_parent_id IS NULL) AND (recurrence_instance_date IS NULL)) OR ((recurrence_parent_id IS NOT NULL) AND (recurrence_instance_date IS NOT NULL)))),
    CONSTRAINT chk_events_series_root CHECK (((recurrence_rule IS NULL) OR ((recurrence_parent_id IS NULL) AND (recurrence_instance_date IS NULL)))),
    CONSTRAINT chk_events_source CHECK ((source = ANY (ARRAY['scout'::text, 'google_cal'::text, 'ical'::text]))),
    CONSTRAINT chk_events_time_order CHECK ((ends_at >= starts_at))
);


--
-- Name: families; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.families (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    timezone text DEFAULT 'America/Chicago'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    allow_general_chat boolean DEFAULT true NOT NULL,
    allow_homework_help boolean DEFAULT true NOT NULL,
    home_location text
);


--
-- Name: family_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.family_members (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    first_name text NOT NULL,
    last_name text,
    role text NOT NULL,
    birthdate date,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    grade_level text,
    learning_notes text,
    read_aloud_enabled boolean DEFAULT false NOT NULL,
    personality_notes text,
    CONSTRAINT chk_family_members_role CHECK ((role = ANY (ARRAY['adult'::text, 'child'::text])))
);


--
-- Name: family_memories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.family_memories (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    member_id uuid,
    memory_type text NOT NULL,
    scope text DEFAULT 'family'::text NOT NULL,
    content text NOT NULL,
    tags jsonb DEFAULT '[]'::jsonb NOT NULL,
    source_kind text DEFAULT 'parent_edit'::text NOT NULL,
    source_conversation_id uuid,
    created_by_kind text DEFAULT 'parent'::text NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    confidence real DEFAULT 1.0 NOT NULL,
    last_confirmed_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    updated_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    CONSTRAINT chk_family_memory_scope CHECK ((scope = ANY (ARRAY['parent'::text, 'family'::text, 'child'::text]))),
    CONSTRAINT chk_family_memory_source_kind CHECK ((source_kind = ANY (ARRAY['parent_edit'::text, 'ai_proposed'::text, 'auto_structured'::text]))),
    CONSTRAINT chk_family_memory_status CHECK ((status = ANY (ARRAY['proposed'::text, 'active'::text, 'archived'::text])))
);


--
-- Name: grocery_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.grocery_items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    added_by_member_id uuid NOT NULL,
    title text NOT NULL,
    quantity numeric,
    unit text,
    category text,
    preferred_store text,
    notes text,
    source text DEFAULT 'manual'::text NOT NULL,
    approval_status text DEFAULT 'active'::text NOT NULL,
    purchase_request_id uuid,
    is_purchased boolean DEFAULT false NOT NULL,
    purchased_at timestamp with time zone,
    purchased_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    weekly_plan_id uuid,
    linked_meal_ref text,
    CONSTRAINT chk_grocery_items_approval_status CHECK ((approval_status = ANY (ARRAY['active'::text, 'pending_review'::text, 'approved'::text, 'rejected'::text]))),
    CONSTRAINT chk_grocery_items_source CHECK ((source = ANY (ARRAY['meal_ai'::text, 'manual'::text, 'purchase_request'::text]))),
    CONSTRAINT chk_grocery_items_title_not_blank CHECK ((length(btrim(title)) > 0))
);


--
-- Name: health_summaries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.health_summaries (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    family_member_id uuid NOT NULL,
    summary_date date NOT NULL,
    steps integer,
    active_minutes integer,
    resting_heart_rate integer,
    sleep_minutes integer,
    weight_grams integer,
    source text DEFAULT 'scout'::text NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_health_summaries_active_minutes_nonneg CHECK (((active_minutes IS NULL) OR (active_minutes >= 0))),
    CONSTRAINT chk_health_summaries_resting_hr_nonneg CHECK (((resting_heart_rate IS NULL) OR (resting_heart_rate >= 0))),
    CONSTRAINT chk_health_summaries_sleep_minutes_nonneg CHECK (((sleep_minutes IS NULL) OR (sleep_minutes >= 0))),
    CONSTRAINT chk_health_summaries_source CHECK ((source = ANY (ARRAY['scout'::text, 'apple_health'::text, 'nike_run_club'::text]))),
    CONSTRAINT chk_health_summaries_steps_nonneg CHECK (((steps IS NULL) OR (steps >= 0))),
    CONSTRAINT chk_health_summaries_weight_grams_nonneg CHECK (((weight_grams IS NULL) OR (weight_grams >= 0)))
);


--
-- Name: meal_plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.meal_plans (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    created_by uuid,
    week_start date NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_meal_plans_week_start_monday CHECK ((EXTRACT(isodow FROM week_start) = (1)::numeric))
);


--
-- Name: meal_reviews; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.meal_reviews (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    weekly_plan_id uuid,
    reviewed_by_member_id uuid NOT NULL,
    linked_meal_ref text,
    meal_title text NOT NULL,
    rating_overall integer NOT NULL,
    kid_acceptance integer,
    effort integer,
    cleanup integer,
    leftovers text,
    repeat_decision text NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_meal_reviews_cleanup CHECK (((cleanup IS NULL) OR ((cleanup >= 1) AND (cleanup <= 5)))),
    CONSTRAINT chk_meal_reviews_effort CHECK (((effort IS NULL) OR ((effort >= 1) AND (effort <= 5)))),
    CONSTRAINT chk_meal_reviews_kid_acceptance CHECK (((kid_acceptance IS NULL) OR ((kid_acceptance >= 1) AND (kid_acceptance <= 5)))),
    CONSTRAINT chk_meal_reviews_leftovers CHECK (((leftovers IS NULL) OR (leftovers = ANY (ARRAY['none'::text, 'some'::text, 'plenty'::text])))),
    CONSTRAINT chk_meal_reviews_meal_title_not_blank CHECK ((length(btrim(meal_title)) > 0)),
    CONSTRAINT chk_meal_reviews_rating_overall CHECK (((rating_overall >= 1) AND (rating_overall <= 5))),
    CONSTRAINT chk_meal_reviews_repeat_decision CHECK ((repeat_decision = ANY (ARRAY['repeat'::text, 'tweak'::text, 'retire'::text])))
);


--
-- Name: meals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.meals (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    meal_plan_id uuid,
    created_by uuid,
    meal_date date NOT NULL,
    meal_type text NOT NULL,
    title text NOT NULL,
    description text,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_base_cook boolean DEFAULT false,
    base_cook_yield_servings integer,
    base_cook_keeps_days integer,
    storage_notes text,
    CONSTRAINT chk_meals_meal_type CHECK ((meal_type = ANY (ARRAY['breakfast'::text, 'lunch'::text, 'dinner'::text, 'snack'::text])))
);


--
-- Name: member_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.member_config (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_member_id uuid NOT NULL,
    key text NOT NULL,
    value jsonb NOT NULL,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: notes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    family_member_id uuid NOT NULL,
    title text NOT NULL,
    body text DEFAULT ''::text NOT NULL,
    category text,
    is_archived boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_notes_title_not_blank CHECK ((length(btrim(title)) > 0))
);


--
-- Name: parent_action_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.parent_action_items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    created_by_member_id uuid NOT NULL,
    action_type text NOT NULL,
    title text NOT NULL,
    detail text,
    entity_type text,
    entity_id uuid,
    status text DEFAULT 'pending'::text NOT NULL,
    resolved_by uuid,
    resolved_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_parent_action_items_action_type CHECK ((action_type = ANY (ARRAY['grocery_review'::text, 'purchase_request'::text, 'chore_override'::text, 'general'::text, 'meal_plan_review'::text, 'moderation_alert'::text, 'daily_brief'::text, 'weekly_retro'::text, 'moderation_digest'::text, 'anomaly_alert'::text, 'nudge.overdue_task'::text, 'nudge.upcoming_event'::text, 'nudge.missed_routine'::text, 'nudge.custom_rule'::text, 'nudge.ai_suggested'::text]))),
    CONSTRAINT chk_parent_action_items_status CHECK ((status = ANY (ARRAY['pending'::text, 'resolved'::text, 'dismissed'::text])))
);


--
-- Name: personal_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.personal_tasks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    assigned_to uuid NOT NULL,
    created_by uuid,
    title text NOT NULL,
    description text,
    notes text,
    status text DEFAULT 'pending'::text NOT NULL,
    priority text DEFAULT 'medium'::text NOT NULL,
    due_at timestamp with time zone,
    completed_at timestamp with time zone,
    event_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    source_project_task_id uuid,
    CONSTRAINT chk_personal_tasks_completed_consistency CHECK ((((status = 'done'::text) AND (completed_at IS NOT NULL)) OR ((status <> 'done'::text) AND (completed_at IS NULL)))),
    CONSTRAINT chk_personal_tasks_priority CHECK ((priority = ANY (ARRAY['low'::text, 'medium'::text, 'high'::text, 'urgent'::text]))),
    CONSTRAINT chk_personal_tasks_status CHECK ((status = ANY (ARRAY['pending'::text, 'in_progress'::text, 'done'::text, 'cancelled'::text])))
);


--
-- Name: planner_bundle_applies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.planner_bundle_applies (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    bundle_apply_id text NOT NULL,
    family_id uuid NOT NULL,
    actor_member_id uuid NOT NULL,
    conversation_id uuid,
    status text DEFAULT 'applied'::text NOT NULL,
    tasks_created integer DEFAULT 0 NOT NULL,
    events_created integer DEFAULT 0 NOT NULL,
    grocery_items_created integer DEFAULT 0 NOT NULL,
    errors jsonb,
    summary text,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    CONSTRAINT chk_planner_bundle_apply_status CHECK ((status = ANY (ARRAY['applied'::text, 'failed'::text])))
);


--
-- Name: purchase_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.purchase_requests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    requested_by_member_id uuid NOT NULL,
    type text DEFAULT 'grocery'::text NOT NULL,
    title text NOT NULL,
    details text,
    quantity numeric,
    unit text,
    preferred_brand text,
    preferred_store text,
    urgency text,
    status text DEFAULT 'pending'::text NOT NULL,
    linked_grocery_item_id uuid,
    reviewed_by_member_id uuid,
    reviewed_at timestamp with time zone,
    review_note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_purchase_requests_status CHECK ((status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text, 'converted'::text, 'fulfilled'::text]))),
    CONSTRAINT chk_purchase_requests_title_not_blank CHECK ((length(btrim(title)) > 0)),
    CONSTRAINT chk_purchase_requests_type CHECK ((type = ANY (ARRAY['grocery'::text, 'household'::text, 'personal'::text, 'other'::text]))),
    CONSTRAINT chk_purchase_requests_urgency CHECK (((urgency IS NULL) OR (urgency = ANY (ARRAY['low'::text, 'normal'::text, 'high'::text, 'urgent'::text]))))
);


--
-- Name: role_tier_overrides; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.role_tier_overrides (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_member_id uuid NOT NULL,
    role_tier_id uuid NOT NULL,
    override_permissions jsonb DEFAULT '{}'::jsonb NOT NULL,
    override_behavior jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: role_tiers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.role_tiers (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    permissions jsonb DEFAULT '{}'::jsonb NOT NULL,
    behavior_config jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    description text
);


--
-- Name: routine_steps; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.routine_steps (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    routine_id uuid NOT NULL,
    name text NOT NULL,
    sort_order integer NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: routines; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.routines (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    family_member_id uuid NOT NULL,
    name text NOT NULL,
    block text NOT NULL,
    recurrence text DEFAULT 'daily'::text NOT NULL,
    due_time_weekday time without time zone NOT NULL,
    due_time_weekend time without time zone,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_routines_block CHECK ((block = ANY (ARRAY['morning'::text, 'after_school'::text, 'evening'::text]))),
    CONSTRAINT chk_routines_recurrence CHECK ((recurrence = ANY (ARRAY['daily'::text, 'weekdays'::text, 'weekends'::text])))
);


--
-- Name: scout_anomaly_suppressions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scout_anomaly_suppressions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    anomaly_type text NOT NULL,
    signature text NOT NULL,
    first_seen_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    last_seen_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    suppress_until timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: scout_mcp_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scout_mcp_tokens (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    member_id uuid,
    token_hash text NOT NULL,
    label text,
    scope text DEFAULT 'parent'::text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    last_used_at timestamp with time zone,
    created_by_member_id uuid,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    revoked_at timestamp with time zone,
    CONSTRAINT chk_scout_mcp_token_scope CHECK ((scope = ANY (ARRAY['parent'::text, 'child'::text])))
);


--
-- Name: scout_scheduled_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scout_scheduled_runs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    job_name text NOT NULL,
    family_id uuid NOT NULL,
    member_id uuid,
    run_date date NOT NULL,
    status text DEFAULT 'success'::text NOT NULL,
    duration_ms integer,
    result jsonb,
    error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_scout_scheduled_runs_status CHECK ((status = ANY (ARRAY['success'::text, 'error'::text, 'skipped'::text])))
);


--
-- Name: sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sessions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_account_id uuid NOT NULL,
    token text NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: task_instance_step_completions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.task_instance_step_completions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    task_instance_id uuid NOT NULL,
    routine_step_id uuid NOT NULL,
    is_completed boolean DEFAULT false NOT NULL,
    completed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: task_instances; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.task_instances (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    family_member_id uuid NOT NULL,
    routine_id uuid,
    chore_template_id uuid,
    instance_date date NOT NULL,
    due_at timestamp with time zone NOT NULL,
    is_completed boolean DEFAULT false NOT NULL,
    completed_at timestamp with time zone,
    override_completed boolean,
    override_by uuid,
    override_note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    in_scope_confirmed boolean DEFAULT false,
    scope_dispute_opened_at timestamp with time zone,
    CONSTRAINT chk_task_instances_override CHECK ((((override_completed IS NULL) AND (override_by IS NULL) AND (override_note IS NULL)) OR ((override_completed IS NOT NULL) AND (override_by IS NOT NULL)))),
    CONSTRAINT chk_task_instances_source CHECK ((((routine_id IS NOT NULL) AND (chore_template_id IS NULL)) OR ((routine_id IS NULL) AND (chore_template_id IS NOT NULL))))
);


--
-- Name: user_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_accounts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_member_id uuid NOT NULL,
    email text,
    phone text,
    auth_provider text NOT NULL,
    password_hash text,
    is_primary boolean DEFAULT false NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    last_login_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_user_accounts_auth_provider CHECK ((auth_provider = ANY (ARRAY['email'::text, 'apple'::text, 'google'::text]))),
    CONSTRAINT chk_user_accounts_email_auth CHECK (((auth_provider <> 'email'::text) OR (password_hash IS NOT NULL)))
);


--
-- Name: weekly_meal_plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.weekly_meal_plans (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    created_by_member_id uuid NOT NULL,
    week_start_date date NOT NULL,
    source text DEFAULT 'ai'::text NOT NULL,
    status text DEFAULT 'draft'::text NOT NULL,
    title text,
    constraints_snapshot jsonb DEFAULT '{}'::jsonb NOT NULL,
    week_plan jsonb DEFAULT '{}'::jsonb NOT NULL,
    prep_plan jsonb DEFAULT '{}'::jsonb NOT NULL,
    grocery_plan jsonb DEFAULT '{}'::jsonb NOT NULL,
    plan_summary text,
    approved_by_member_id uuid,
    approved_at timestamp with time zone,
    archived_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_weekly_meal_plans_approved_fields CHECK (((status <> 'approved'::text) OR ((approved_by_member_id IS NOT NULL) AND (approved_at IS NOT NULL)))),
    CONSTRAINT chk_weekly_meal_plans_source CHECK ((source = ANY (ARRAY['ai'::text, 'manual'::text]))),
    CONSTRAINT chk_weekly_meal_plans_status CHECK ((status = ANY (ARRAY['draft'::text, 'approved'::text, 'archived'::text]))),
    CONSTRAINT chk_weekly_meal_plans_week_start_monday CHECK ((EXTRACT(isodow FROM week_start_date) = (1)::numeric))
);


--
-- Name: activity_events; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.activity_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    family_member_id uuid,
    source text NOT NULL,
    activity_key text NOT NULL,
    started_at timestamp with time zone NOT NULL,
    duration_sec integer,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    imported_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    CONSTRAINT chk_activity_source CHECK ((source = ANY (ARRAY['apple_health'::text, 'nike_run_club'::text])))
);


--
-- Name: affirmation_delivery_log; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.affirmation_delivery_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_member_id uuid NOT NULL,
    affirmation_id uuid NOT NULL,
    surfaced_at timestamp with time zone NOT NULL,
    surfaced_in text NOT NULL,
    dismissed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: affirmation_feedback; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.affirmation_feedback (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_member_id uuid NOT NULL,
    affirmation_id uuid NOT NULL,
    reaction_type text NOT NULL,
    context text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT affirmation_feedback_reaction_type_check CHECK ((reaction_type = ANY (ARRAY['heart'::text, 'thumbs_down'::text, 'skip'::text, 'reshow'::text])))
);


--
-- Name: affirmations; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.affirmations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    text text NOT NULL,
    category text,
    tags jsonb DEFAULT '[]'::jsonb NOT NULL,
    tone text,
    philosophy text,
    audience_type text DEFAULT 'general'::text NOT NULL,
    length_class text DEFAULT 'short'::text NOT NULL,
    active boolean DEFAULT true NOT NULL,
    source_type text DEFAULT 'curated'::text NOT NULL,
    created_by uuid,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: allowance_periods; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.allowance_periods (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    period_key text NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    status text DEFAULT 'draft'::text NOT NULL,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    updated_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    CONSTRAINT chk_allowance_status CHECK ((status = ANY (ARRAY['draft'::text, 'pending_approval'::text, 'approved'::text, 'exported'::text, 'paid'::text])))
);


--
-- Name: allowance_results; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.allowance_results (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    allowance_period_id uuid NOT NULL,
    family_member_id uuid NOT NULL,
    reward_policy_id uuid,
    baseline_amount_cents integer NOT NULL,
    wins_earned integer DEFAULT 0 NOT NULL,
    wins_required integer DEFAULT 0 NOT NULL,
    payout_percent numeric(5,4) DEFAULT 0 NOT NULL,
    projected_cents integer DEFAULT 0 NOT NULL,
    final_cents integer,
    miss_reasons jsonb DEFAULT '[]'::jsonb NOT NULL,
    approved_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    updated_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: bill_snapshots; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.bill_snapshots (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    source text DEFAULT 'ynab'::text NOT NULL,
    as_of_date date NOT NULL,
    bill_key text NOT NULL,
    label text NOT NULL,
    due_date date NOT NULL,
    amount_cents integer NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    imported_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: budget_snapshots; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.budget_snapshots (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    source text DEFAULT 'ynab'::text NOT NULL,
    as_of_date date NOT NULL,
    category_key text NOT NULL,
    available_cents integer NOT NULL,
    budgeted_cents integer,
    activity_cents integer,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    imported_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: calendar_exports; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.calendar_exports (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    source_type text NOT NULL,
    source_id uuid NOT NULL,
    target text DEFAULT 'google_calendar'::text NOT NULL,
    label text NOT NULL,
    starts_at timestamp with time zone NOT NULL,
    ends_at timestamp with time zone NOT NULL,
    hearth_visible boolean DEFAULT true NOT NULL,
    export_status text DEFAULT 'pending'::text NOT NULL,
    last_exported_at timestamp with time zone,
    error_message text,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    updated_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    CONSTRAINT chk_export_source CHECK ((source_type = ANY (ARRAY['routine_block'::text, 'task_occurrence'::text, 'time_block'::text, 'weekly_anchor'::text]))),
    CONSTRAINT chk_export_status CHECK ((export_status = ANY (ARRAY['pending'::text, 'exported'::text, 'error'::text, 'stale'::text, 'cancelled'::text])))
);


--
-- Name: connector_accounts; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.connector_accounts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    connector_id uuid NOT NULL,
    family_id uuid NOT NULL,
    user_account_id uuid,
    account_label text,
    status text DEFAULT 'configured'::text NOT NULL,
    last_success_at timestamp with time zone,
    last_error_at timestamp with time zone,
    last_error_message text,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    updated_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    CONSTRAINT chk_connector_account_status CHECK ((status = ANY (ARRAY['disconnected'::text, 'configured'::text, 'connected'::text, 'syncing'::text, 'stale'::text, 'error'::text, 'disabled'::text, 'decision_gated'::text])))
);


--
-- Name: connector_configs; Type: VIEW; Schema: scout; Owner: -
--

CREATE VIEW scout.connector_configs AS
 SELECT id,
    family_id,
    family_member_id,
    connector_name,
    auth_token,
    refresh_token,
    config,
    scope,
    sync_direction,
    authority_level,
    is_active,
    created_at,
    updated_at
   FROM public.connector_configs;


--
-- Name: connector_event_log; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.connector_event_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    connector_account_id uuid,
    event_type text NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    severity text DEFAULT 'info'::text NOT NULL,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    CONSTRAINT chk_event_severity CHECK ((severity = ANY (ARRAY['info'::text, 'warn'::text, 'error'::text, 'critical'::text])))
);


--
-- Name: connector_mappings; Type: VIEW; Schema: scout; Owner: -
--

CREATE VIEW scout.connector_mappings AS
 SELECT id,
    connector_name,
    internal_table,
    internal_id,
    external_id,
    metadata,
    created_at,
    external_object_type,
    family_id,
    user_account_id
   FROM public.connector_mappings;


--
-- Name: connectors; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.connectors (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    connector_key text NOT NULL,
    label text NOT NULL,
    tier integer DEFAULT 2 NOT NULL,
    is_enabled boolean DEFAULT true NOT NULL,
    decision_gated boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    updated_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    CONSTRAINT chk_connector_key CHECK ((connector_key = ANY (ARRAY['google_calendar'::text, 'hearth_display'::text, 'greenlight'::text, 'rex'::text, 'ynab'::text, 'apple_health'::text, 'nike_run_club'::text, 'google_maps'::text, 'exxir'::text])))
);


--
-- Name: daily_win_results; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.daily_win_results (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    family_member_id uuid NOT NULL,
    for_date date NOT NULL,
    earned boolean DEFAULT false NOT NULL,
    total_required integer DEFAULT 0 NOT NULL,
    total_complete integer DEFAULT 0 NOT NULL,
    missing_items jsonb DEFAULT '[]'::jsonb NOT NULL,
    computed_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: device_registrations; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.device_registrations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_account_id uuid NOT NULL,
    device_token text NOT NULL,
    platform text NOT NULL,
    label text,
    last_seen_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    revoked_at timestamp with time zone,
    CONSTRAINT chk_device_platform CHECK ((platform = ANY (ARRAY['ios'::text, 'android'::text, 'web'::text])))
);


--
-- Name: external_calendar_events; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.external_calendar_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    source text NOT NULL,
    title text NOT NULL,
    starts_at timestamp with time zone NOT NULL,
    ends_at timestamp with time zone NOT NULL,
    location text,
    all_day boolean DEFAULT false NOT NULL,
    imported_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: families; Type: VIEW; Schema: scout; Owner: -
--

CREATE VIEW scout.families AS
 SELECT id,
    name,
    timezone,
    created_at,
    updated_at,
    allow_general_chat,
    allow_homework_help,
    home_location
   FROM public.families;


--
-- Name: family_members; Type: VIEW; Schema: scout; Owner: -
--

CREATE VIEW scout.family_members AS
 SELECT id,
    family_id,
    first_name,
    last_name,
    role,
    birthdate,
    is_active,
    created_at,
    updated_at,
    grade_level,
    learning_notes,
    read_aloud_enabled,
    personality_notes
   FROM public.family_members;


--
-- Name: greenlight_exports; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.greenlight_exports (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    settlement_batch_id uuid NOT NULL,
    family_member_id uuid NOT NULL,
    amount_cents integer NOT NULL,
    greenlight_external_ref text,
    export_status text DEFAULT 'pending'::text NOT NULL,
    error_message text,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    CONSTRAINT chk_greenlight_export_status CHECK ((export_status = ANY (ARRAY['pending'::text, 'exported'::text, 'confirmed'::text, 'error'::text, 'cancelled'::text])))
);


--
-- Name: home_assets; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.home_assets (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    zone_id uuid,
    name text NOT NULL,
    asset_type text,
    model text,
    serial text,
    purchase_date date,
    warranty_expires_at timestamp with time zone,
    manual_url text,
    receipt_url text,
    notes text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: home_zones; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.home_zones (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    name text NOT NULL,
    zone_type text DEFAULT 'room'::text NOT NULL,
    notes text,
    sort_order integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: household_rules; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.household_rules (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    rule_key text NOT NULL,
    rule_value jsonb DEFAULT '{}'::jsonb NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    updated_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: maintenance_instances; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.maintenance_instances (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    template_id uuid NOT NULL,
    owner_member_id uuid NOT NULL,
    scheduled_for timestamp with time zone NOT NULL,
    completed_at timestamp with time zone,
    completed_by_member_id uuid,
    notes text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: maintenance_templates; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.maintenance_templates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    zone_id uuid,
    asset_id uuid,
    name text NOT NULL,
    description text,
    cadence_type text DEFAULT 'monthly'::text NOT NULL,
    rotation_month_mod integer,
    included jsonb DEFAULT '[]'::jsonb NOT NULL,
    not_included jsonb DEFAULT '[]'::jsonb NOT NULL,
    done_means_done text,
    supplies jsonb DEFAULT '[]'::jsonb NOT NULL,
    estimated_duration_minutes integer,
    default_owner_member_id uuid,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: meal_transformations; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.meal_transformations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    base_staple_id uuid NOT NULL,
    transformed_staple_id uuid NOT NULL,
    transformation_name text NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: nudge_dispatch_items; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.nudge_dispatch_items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    dispatch_id uuid NOT NULL,
    family_member_id uuid NOT NULL,
    trigger_kind text NOT NULL,
    trigger_entity_kind text NOT NULL,
    trigger_entity_id uuid,
    occurrence_at_utc timestamp with time zone NOT NULL,
    occurrence_local_date date NOT NULL,
    source_dedupe_key text NOT NULL,
    source_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_nudge_dispatch_items_trigger_kind CHECK ((trigger_kind = ANY (ARRAY['overdue_task'::text, 'upcoming_event'::text, 'missed_routine'::text, 'custom_rule'::text, 'ai_suggested'::text])))
);


--
-- Name: nudge_dispatches; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.nudge_dispatches (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_member_id uuid NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    severity text DEFAULT 'normal'::text NOT NULL,
    suppressed_reason text,
    deliver_after_utc timestamp with time zone NOT NULL,
    delivered_at_utc timestamp with time zone,
    parent_action_item_id uuid,
    push_delivery_id uuid,
    delivered_channels jsonb DEFAULT '[]'::jsonb NOT NULL,
    source_count integer DEFAULT 1 NOT NULL,
    body text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_nudge_dispatches_severity CHECK ((severity = ANY (ARRAY['low'::text, 'normal'::text, 'high'::text]))),
    CONSTRAINT chk_nudge_dispatches_status CHECK ((status = ANY (ARRAY['pending'::text, 'delivered'::text, 'suppressed'::text])))
);


--
-- Name: nudge_rules; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.nudge_rules (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    name text NOT NULL,
    description text,
    is_active boolean DEFAULT true NOT NULL,
    source_kind text NOT NULL,
    template_sql text,
    canonical_sql text,
    template_params jsonb DEFAULT '{}'::jsonb NOT NULL,
    trigger_kind text DEFAULT 'custom_rule'::text NOT NULL,
    default_lead_time_minutes integer DEFAULT 0 NOT NULL,
    severity text DEFAULT 'normal'::text NOT NULL,
    created_by_family_member_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_nudge_rules_lead_time CHECK (((default_lead_time_minutes >= 0) AND (default_lead_time_minutes <= 1440))),
    CONSTRAINT chk_nudge_rules_severity CHECK ((severity = ANY (ARRAY['low'::text, 'normal'::text, 'high'::text]))),
    CONSTRAINT chk_nudge_rules_source_kind CHECK ((source_kind = ANY (ARRAY['sql_template'::text, 'predicate'::text]))),
    CONSTRAINT chk_nudge_rules_sql_template_has_sql CHECK (((source_kind <> 'sql_template'::text) OR (template_sql IS NOT NULL))),
    CONSTRAINT chk_nudge_rules_trigger_kind CHECK ((trigger_kind = 'custom_rule'::text))
);


--
-- Name: permissions; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.permissions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    permission_key text NOT NULL,
    description text NOT NULL,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: project_budget_entries; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.project_budget_entries (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    project_id uuid NOT NULL,
    project_task_id uuid,
    amount_cents integer NOT NULL,
    kind text NOT NULL,
    vendor text,
    notes text,
    recorded_at timestamp with time zone DEFAULT now() NOT NULL,
    recorded_by_family_member_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT project_budget_entries_kind_check CHECK ((kind = ANY (ARRAY['estimate'::text, 'expense'::text, 'refund'::text])))
);


--
-- Name: project_milestones; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.project_milestones (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    project_id uuid NOT NULL,
    name text NOT NULL,
    target_date date NOT NULL,
    is_complete boolean DEFAULT false NOT NULL,
    completed_at timestamp with time zone,
    order_index integer DEFAULT 0 NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: project_tasks; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.project_tasks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    project_id uuid NOT NULL,
    title text NOT NULL,
    description text,
    status text DEFAULT 'todo'::text NOT NULL,
    owner_family_member_id uuid,
    due_date date,
    estimated_duration_minutes integer,
    actual_duration_minutes integer,
    budget_cents integer,
    spent_cents integer,
    depends_on_project_task_id uuid,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT project_tasks_status_check CHECK ((status = ANY (ARRAY['todo'::text, 'in_progress'::text, 'blocked'::text, 'done'::text, 'skipped'::text])))
);


--
-- Name: project_template_tasks; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.project_template_tasks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    project_template_id uuid NOT NULL,
    title text NOT NULL,
    description text,
    order_index integer DEFAULT 0 NOT NULL,
    relative_day_offset integer DEFAULT 0 NOT NULL,
    default_owner_role text,
    estimated_duration_minutes integer,
    has_budget_impact boolean DEFAULT false NOT NULL,
    has_grocery_impact boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: project_templates; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.project_templates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid,
    name text NOT NULL,
    description text,
    category text NOT NULL,
    estimated_duration_days integer,
    default_lead_time_days integer DEFAULT 0 NOT NULL,
    default_budget_cents integer,
    created_by_family_member_id uuid,
    is_active boolean DEFAULT true NOT NULL,
    is_builtin boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT project_templates_category_check CHECK ((category = ANY (ARRAY['birthday'::text, 'holiday'::text, 'trip'::text, 'school_event'::text, 'home_project'::text, 'weekend_reset'::text, 'custom'::text])))
);


--
-- Name: projects; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.projects (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    project_template_id uuid,
    name text NOT NULL,
    description text,
    category text NOT NULL,
    status text DEFAULT 'draft'::text NOT NULL,
    start_date date NOT NULL,
    target_end_date date,
    actual_end_date date,
    budget_cents integer,
    actual_spent_cents integer,
    primary_owner_family_member_id uuid,
    created_by_family_member_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT projects_category_check CHECK ((category = ANY (ARRAY['birthday'::text, 'holiday'::text, 'trip'::text, 'school_event'::text, 'home_project'::text, 'weekend_reset'::text, 'custom'::text]))),
    CONSTRAINT projects_status_check CHECK ((status = ANY (ARRAY['draft'::text, 'active'::text, 'paused'::text, 'complete'::text, 'cancelled'::text])))
);


--
-- Name: push_deliveries; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.push_deliveries (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    notification_group_id uuid NOT NULL,
    family_member_id uuid NOT NULL,
    push_device_id uuid NOT NULL,
    provider text DEFAULT 'expo'::text NOT NULL,
    category text NOT NULL,
    title text NOT NULL,
    body text NOT NULL,
    data jsonb DEFAULT '{}'::jsonb NOT NULL,
    trigger_source text NOT NULL,
    status text DEFAULT 'queued'::text NOT NULL,
    provider_ticket_id text,
    provider_receipt_status text,
    provider_receipt_payload jsonb,
    error_message text,
    sent_at timestamp with time zone,
    receipt_checked_at timestamp with time zone,
    provider_handoff_at timestamp with time zone,
    tapped_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT push_deliveries_provider_check CHECK ((provider = 'expo'::text)),
    CONSTRAINT push_deliveries_status_check CHECK ((status = ANY (ARRAY['queued'::text, 'provider_accepted'::text, 'provider_handoff_ok'::text, 'provider_error'::text])))
);


--
-- Name: push_devices; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.push_devices (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_member_id uuid NOT NULL,
    expo_push_token text NOT NULL,
    device_label text,
    platform text NOT NULL,
    app_version text,
    is_active boolean DEFAULT true NOT NULL,
    last_registered_at timestamp with time zone DEFAULT now() NOT NULL,
    last_successful_delivery_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT push_devices_platform_check CHECK ((platform = ANY (ARRAY['ios'::text, 'android'::text, 'web'::text])))
);


--
-- Name: quiet_hours_family; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.quiet_hours_family (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    start_local_minute integer DEFAULT 1320 NOT NULL,
    end_local_minute integer DEFAULT 420 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_quiet_hours_family_end_range CHECK (((end_local_minute >= 0) AND (end_local_minute < 1440))),
    CONSTRAINT chk_quiet_hours_family_start_end CHECK ((start_local_minute <> end_local_minute)),
    CONSTRAINT chk_quiet_hours_family_start_range CHECK (((start_local_minute >= 0) AND (start_local_minute < 1440)))
);


--
-- Name: reward_extras_catalog; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.reward_extras_catalog (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    extra_key text NOT NULL,
    label text NOT NULL,
    amount_cents integer NOT NULL,
    notes text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: reward_ledger_entries; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.reward_ledger_entries (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    family_member_id uuid NOT NULL,
    allowance_result_id uuid,
    extras_catalog_id uuid,
    entry_type text NOT NULL,
    amount_cents integer NOT NULL,
    memo text,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    CONSTRAINT chk_ledger_entry_type CHECK ((entry_type = ANY (ARRAY['baseline_payout'::text, 'extra'::text, 'school_reward'::text, 'bonus'::text, 'correction'::text])))
);


--
-- Name: reward_policies; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.reward_policies (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    family_member_id uuid,
    policy_key text NOT NULL,
    baseline_amount_cents integer NOT NULL,
    payout_schedule jsonb DEFAULT '{}'::jsonb NOT NULL,
    wins_required jsonb DEFAULT '[]'::jsonb NOT NULL,
    extras_allowed boolean DEFAULT true NOT NULL,
    effective_from date DEFAULT CURRENT_DATE NOT NULL,
    effective_until date,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    updated_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: role_tier_overrides; Type: VIEW; Schema: scout; Owner: -
--

CREATE VIEW scout.role_tier_overrides AS
 SELECT id,
    family_member_id,
    role_tier_id,
    override_permissions,
    override_behavior,
    created_at,
    updated_at
   FROM public.role_tier_overrides;


--
-- Name: role_tier_permissions; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.role_tier_permissions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    role_tier_id uuid NOT NULL,
    permission_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: role_tiers; Type: VIEW; Schema: scout; Owner: -
--

CREATE VIEW scout.role_tiers AS
 SELECT id,
    name,
    permissions,
    behavior_config,
    created_at,
    updated_at,
    description
   FROM public.role_tiers;


--
-- Name: routine_steps; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.routine_steps (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    routine_template_id uuid NOT NULL,
    standard_of_done_id uuid,
    sort_order integer NOT NULL,
    label text NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: routine_templates; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.routine_templates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    routine_key text NOT NULL,
    label text NOT NULL,
    block_label text NOT NULL,
    recurrence text NOT NULL,
    due_time_weekday time without time zone,
    due_time_weekend time without time zone,
    owner_family_member_id uuid,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    updated_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    CONSTRAINT chk_routine_recurrence CHECK ((recurrence = ANY (ARRAY['daily'::text, 'weekdays'::text, 'weekends'::text, 'weekly'::text])))
);


--
-- Name: sessions; Type: VIEW; Schema: scout; Owner: -
--

CREATE VIEW scout.sessions AS
 SELECT id,
    user_account_id,
    token,
    expires_at,
    created_at
   FROM public.sessions;


--
-- Name: settlement_batches; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.settlement_batches (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    batch_key text NOT NULL,
    status text DEFAULT 'draft'::text NOT NULL,
    submitted_at timestamp with time zone,
    exported_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    updated_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    CONSTRAINT chk_settlement_status CHECK ((status = ANY (ARRAY['draft'::text, 'pending'::text, 'exported'::text, 'failed'::text, 'cancelled'::text])))
);


--
-- Name: stale_data_alerts; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.stale_data_alerts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    connector_account_id uuid NOT NULL,
    entity_key text NOT NULL,
    stale_since timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    acknowledged_at timestamp with time zone
);


--
-- Name: standards_of_done; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.standards_of_done (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    standard_key text NOT NULL,
    label text NOT NULL,
    checklist jsonb DEFAULT '[]'::jsonb NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    updated_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: sync_cursors; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.sync_cursors (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    connector_account_id uuid NOT NULL,
    cursor_key text NOT NULL,
    cursor_value text,
    updated_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: sync_jobs; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.sync_jobs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    connector_account_id uuid NOT NULL,
    entity_key text NOT NULL,
    cadence_seconds integer DEFAULT 900 NOT NULL,
    is_enabled boolean DEFAULT true NOT NULL,
    last_run_started_at timestamp with time zone,
    last_run_finished_at timestamp with time zone,
    next_run_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: sync_runs; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.sync_runs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    sync_job_id uuid NOT NULL,
    started_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    finished_at timestamp with time zone,
    status text DEFAULT 'running'::text NOT NULL,
    records_processed integer DEFAULT 0 NOT NULL,
    error_message text,
    CONSTRAINT chk_sync_run_status CHECK ((status = ANY (ARRAY['running'::text, 'success'::text, 'partial'::text, 'error'::text])))
);


--
-- Name: task_assignment_rules; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.task_assignment_rules (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    task_template_id uuid NOT NULL,
    rule_type text NOT NULL,
    rule_params jsonb DEFAULT '{}'::jsonb NOT NULL,
    priority integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    CONSTRAINT chk_rule_type CHECK ((rule_type = ANY (ARRAY['fixed'::text, 'day_parity'::text, 'week_rotation'::text, 'dog_walk_assistant'::text, 'custom'::text])))
);


--
-- Name: task_completions; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.task_completions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    task_occurrence_id uuid NOT NULL,
    completed_by uuid,
    completed_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    completion_mode text DEFAULT 'manual'::text NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    CONSTRAINT chk_completion_mode CHECK ((completion_mode = ANY (ARRAY['manual'::text, 'auto'::text, 'parent_override'::text, 'ai_recorded'::text])))
);


--
-- Name: task_exceptions; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.task_exceptions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    task_occurrence_id uuid NOT NULL,
    reason text NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: task_notes; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.task_notes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    task_occurrence_id uuid NOT NULL,
    author_id uuid,
    body text NOT NULL,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: task_occurrences; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.task_occurrences (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    task_template_id uuid,
    routine_template_id uuid,
    assigned_to uuid,
    occurrence_date date NOT NULL,
    due_at timestamp with time zone NOT NULL,
    status text DEFAULT 'open'::text NOT NULL,
    generated_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    updated_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    CONSTRAINT chk_occurrence_status CHECK ((status = ANY (ARRAY['open'::text, 'complete'::text, 'late'::text, 'blocked'::text, 'skipped'::text])))
);


--
-- Name: task_templates; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.task_templates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    template_key text NOT NULL,
    label text NOT NULL,
    recurrence text NOT NULL,
    due_time time without time zone,
    standard_of_done_id uuid,
    notes text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    updated_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    CONSTRAINT chk_task_recurrence CHECK ((recurrence = ANY (ARRAY['daily'::text, 'weekdays'::text, 'weekends'::text, 'weekly'::text, 'one_off'::text])))
);


--
-- Name: time_blocks; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.time_blocks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    block_key text NOT NULL,
    label text NOT NULL,
    start_offset interval NOT NULL,
    end_offset interval NOT NULL,
    applies_weekday boolean DEFAULT true NOT NULL,
    applies_weekend boolean DEFAULT true NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: travel_estimates; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.travel_estimates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    origin text NOT NULL,
    destination text NOT NULL,
    requested_for timestamp with time zone NOT NULL,
    duration_sec integer,
    distance_meters integer,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    fetched_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: user_accounts; Type: VIEW; Schema: scout; Owner: -
--

CREATE VIEW scout.user_accounts AS
 SELECT id,
    family_member_id,
    email,
    phone,
    auth_provider,
    password_hash,
    is_primary,
    is_active,
    last_login_at,
    created_at,
    updated_at
   FROM public.user_accounts;


--
-- Name: user_family_memberships; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.user_family_memberships (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_account_id uuid NOT NULL,
    family_id uuid NOT NULL,
    family_member_id uuid,
    role_tier_id uuid,
    is_primary boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: user_preferences; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.user_preferences (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_account_id uuid NOT NULL,
    preference_key text NOT NULL,
    preference_value jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Name: v_calendar_publication; Type: VIEW; Schema: scout; Owner: -
--

CREATE VIEW scout.v_calendar_publication AS
 SELECT id AS calendar_export_id,
    family_id,
    label,
    starts_at,
    ends_at,
    source_type,
    source_id,
    target,
    hearth_visible,
    export_status,
    last_exported_at
   FROM scout.calendar_exports ce
  WHERE (export_status = ANY (ARRAY['pending'::text, 'exported'::text, 'stale'::text]));


--
-- Name: v_control_plane; Type: VIEW; Schema: scout; Owner: -
--

CREATE VIEW scout.v_control_plane AS
 SELECT ca.id AS connector_account_id,
    c.connector_key,
    c.label,
    ca.family_id,
    ca.status,
    ca.last_success_at,
    ca.last_error_at,
    ca.last_error_message,
        CASE
            WHEN (ca.last_success_at IS NULL) THEN 'unknown'::text
            WHEN (ca.last_success_at >= (clock_timestamp() - '01:00:00'::interval)) THEN 'live'::text
            WHEN (ca.last_success_at >= (clock_timestamp() - '06:00:00'::interval)) THEN 'lagging'::text
            ELSE 'stale'::text
        END AS freshness_state,
    ( SELECT count(*) AS count
           FROM scout.stale_data_alerts a
          WHERE ((a.connector_account_id = ca.id) AND (a.acknowledged_at IS NULL))) AS open_alert_count
   FROM (scout.connector_accounts ca
     JOIN scout.connectors c ON ((c.id = ca.connector_id)));


--
-- Name: v_household_today; Type: VIEW; Schema: scout; Owner: -
--

CREATE VIEW scout.v_household_today AS
 SELECT tocc.id AS task_occurrence_id,
    tocc.family_id,
    tocc.occurrence_date,
    tocc.due_at,
    tocc.status,
    tocc.assigned_to AS family_member_id,
    fm.first_name AS member_name,
    COALESCE(tt.label, rt.label) AS label,
    tt.template_key,
    rt.routine_key,
    rt.block_label,
    (tc.id IS NOT NULL) AS is_completed,
    tc.completed_at
   FROM ((((scout.task_occurrences tocc
     LEFT JOIN scout.task_templates tt ON ((tt.id = tocc.task_template_id)))
     LEFT JOIN scout.routine_templates rt ON ((rt.id = tocc.routine_template_id)))
     LEFT JOIN public.family_members fm ON ((fm.id = tocc.assigned_to)))
     LEFT JOIN LATERAL ( SELECT c.id,
            c.completed_at
           FROM scout.task_completions c
          WHERE (c.task_occurrence_id = tocc.id)
          ORDER BY c.completed_at DESC
         LIMIT 1) tc ON (true));


--
-- Name: v_rewards_current_week; Type: VIEW; Schema: scout; Owner: -
--

CREATE VIEW scout.v_rewards_current_week AS
 SELECT ap.id AS allowance_period_id,
    ap.family_id,
    ap.start_date,
    ap.end_date,
    ap.status AS period_status,
    ar.family_member_id,
    fm.first_name AS member_name,
    ar.baseline_amount_cents,
    ar.wins_earned,
    ar.wins_required,
    ar.payout_percent,
    ar.projected_cents,
    ar.final_cents,
    ar.miss_reasons
   FROM ((scout.allowance_periods ap
     JOIN scout.allowance_results ar ON ((ar.allowance_period_id = ap.id)))
     JOIN public.family_members fm ON ((fm.id = ar.family_member_id)))
  WHERE (ap.status = ANY (ARRAY['draft'::text, 'pending_approval'::text, 'approved'::text]));


--
-- Name: work_context_events; Type: TABLE; Schema: scout; Owner: -
--

CREATE TABLE scout.work_context_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    user_account_id uuid,
    source text NOT NULL,
    event_type text NOT NULL,
    starts_at timestamp with time zone NOT NULL,
    ends_at timestamp with time zone,
    pressure_score numeric(5,2),
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    imported_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);


--
-- Data for Name: _scout_migrations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public._scout_migrations (filename, applied_at) FROM stdin;
001_foundation_connectors.sql	2026-04-12 15:45:12.677908+00
002_life_management.sql	2026-04-12 15:45:12.699933+00
003_calendar.sql	2026-04-12 15:45:12.710791+00
004_connector_ical_support.sql	2026-04-12 15:45:12.718745+00
005_meals.sql	2026-04-12 15:45:12.729849+00
006_personal_tasks.sql	2026-04-12 15:45:12.738288+00
007_second_brain.sql	2026-04-12 15:45:12.748684+00
008_finance.sql	2026-04-12 15:45:12.759354+00
009_health_fitness.sql	2026-04-12 15:45:12.769296+00
010_ai_orchestration.sql	2026-04-12 15:45:12.779749+00
011_grocery_purchase_requests.sql	2026-04-12 15:45:12.79472+00
012_parent_action_items.sql	2026-04-12 15:45:12.801694+00
013_meals_weekly_plans.sql	2026-04-12 15:45:12.813657+00
014_family_ai_chat.sql	2026-04-13 19:31:24.85853+00
015_ai_conversation_kind.sql	2026-04-13 20:15:49.467854+00
016_tier1_proactive.sql	2026-04-13 21:20:56.587049+00
017_ai_messages_clock_timestamp.sql	2026-04-13 22:14:43.216678+00
018_tier2_retro_and_homework.sql	2026-04-13 22:24:44.358745+00
019_tier3.sql	2026-04-14 13:52:46.716703+00
020_tier4.sql	2026-04-14 13:52:46.72497+00
021_tier5.sql	2026-04-14 13:52:46.747704+00
022_session2_canonical.sql	2026-04-15 22:36:30.559561+00
023_session2_roberts_seed.sql	2026-04-15 22:36:30.587034+00
024_permissions_and_config.sql	2026-04-17 03:02:42.417536+00
025_additional_permissions.sql	2026-04-17 03:02:42.423772+00
026_scout_ai_toggle_config.sql	2026-04-17 03:02:42.42929+00
027_feature_admin_permissions.sql	2026-04-17 03:02:42.435701+00
028_allowance_config.sql	2026-04-17 03:02:42.443028+00
029_chores_config.sql	2026-04-17 03:02:42.452236+00
030_grocery_config.sql	2026-04-17 03:02:42.461451+00
031_meals_config.sql	2026-04-17 03:02:42.468233+00
032_integrations_config.sql	2026-04-17 03:02:42.478085+00
033_rewards_config.sql	2026-04-17 03:02:42.491294+00
034_reconcile_permissions.sql	2026-04-17 13:35:10.137031+00
035_consolidate_family_config.sql	2026-04-17 13:35:10.138868+00
036_chores_routines_to_canonical.sql	2026-04-17 13:35:10.149023+00
037_allowance_target_to_canonical.sql	2026-04-17 13:35:10.154827+00
038_integrations_connections_to_canonical.sql	2026-04-17 13:35:10.160357+00
039_affirmations.sql	2026-04-19 05:59:19.066596+00
040_phase2_permissions.sql	2026-04-20 20:53:34.910082+00
041_chore_scope_contract.sql	2026-04-20 20:53:34.937332+00
042_home_maintenance.sql	2026-04-20 20:53:34.944746+00
043_home_maintenance_permissions.sql	2026-04-20 20:53:34.959267+00
044_meal_base_cooks.sql	2026-04-20 20:53:34.963729+00
047_family_projects.sql	2026-04-21 14:51:20.397588+00
045_ai_message_metadata.sql	2026-04-21 15:18:12.643385+00
048_ai_personalities.sql	2026-04-21 16:18:00.669008+00
049_nudge_engine.sql	2026-04-22 00:33:10.480803+00
050_nudge_quiet_hours_and_batching.sql	2026-04-22 01:32:15.899535+00
051_nudge_rules.sql	2026-04-22 11:03:43.990841+00
046a_push_notifications.sql	2026-04-22 21:38:41.329035+00
046b_ai_conversation_resume.sql	2026-04-22 21:38:41.392637+00
052_normalize_046_collision.sql	2026-04-22 21:38:41.399072+00
\.


--
-- Data for Name: activity_records; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.activity_records (id, family_id, family_member_id, activity_type, title, started_at, ended_at, duration_seconds, distance_meters, calories, source, notes, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: ai_conversations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.ai_conversations (id, family_id, family_member_id, surface, status, created_at, updated_at, conversation_kind, title, last_active_at, is_pinned) FROM stdin;
b3dc1e96-5a1d-4bf0-b6ad-508c12ecfea3	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	personal	active	2026-04-21 16:25:13.384203+00	2026-04-21 16:25:13.384203+00	tool	Change chore schedule	2026-04-21 16:25:21.123054+00	f
32cfe212-d39f-4e99-9466-d3fb4a4b3e84	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	personal	active	2026-04-21 16:25:10.796836+00	2026-04-21 16:25:19.272835+00	tool	Reconnect YNAB	2026-04-21 16:25:26.690275+00	f
d1efb62a-6685-4f1c-b05e-ce0085e29969	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	parent	active	2026-04-21 22:58:38.722197+00	2026-04-21 22:58:38.722197+00	tool	Who hasn't done chores?	2026-04-21 22:58:43.164994+00	f
f217c92d-3c95-4688-8122-26c9bc711154	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	parent	active	2026-04-21 22:58:43.313134+00	2026-04-21 22:58:43.313134+00	tool	Weather	2026-04-21 22:58:48.489492+00	f
85a451e4-8006-44a6-8bc4-9026d8fbb3d5	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	personal	active	2026-04-13 19:16:54.148424+00	2026-04-21 15:18:26.343011+00	chat	weather at 76126 for the day?	2026-04-13 19:16:54.148424+00	f
be15c0cd-b19f-4da6-9114-d5d128b5f51b	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	personal	active	2026-04-13 19:52:51.763062+00	2026-04-21 15:18:26.343011+00	chat	In plain language, what is photosynthesis and why does it ma	2026-04-13 19:52:51.763062+00	f
495a8dd3-d9c1-4ea5-82e2-b3a43e188024	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	personal	active	2026-04-13 19:53:06.414672+00	2026-04-21 15:18:26.343011+00	chat	Can you explain long division with an example problem like 8	2026-04-13 19:53:06.414672+00	f
d1bf96c3-7e5e-4ba5-9f73-de865b96a264	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	personal	active	2026-04-13 19:00:12.738351+00	2026-04-21 15:18:26.343011+00	tool	What does today look like?	2026-04-13 20:15:48.798959+00	f
06c0d6aa-759a-4e54-bf98-6f86beabb9d9	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	personal	active	2026-04-13 19:06:01.15128+00	2026-04-21 15:18:26.343011+00	tool	Hello Scout, what does today look like?	2026-04-13 20:15:48.798959+00	f
d6cf512d-ae10-44f8-86db-a5b9b91b518d	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	personal	active	2026-04-13 19:06:59.398476+00	2026-04-21 15:18:26.343011+00	tool	Hello Scout, please list two things that matter today	2026-04-13 20:15:48.798959+00	f
392a0b26-e24a-4214-b44c-c545f89cb8c8	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	personal	active	2026-04-13 19:52:58.98657+00	2026-04-21 15:18:26.343011+00	tool	What is the weather at 76126 today?	2026-04-13 20:15:48.798959+00	f
9f5faa91-c1ca-4c6b-82ba-09ecd79e5a5e	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	personal	active	2026-04-13 20:06:19.441399+00	2026-04-21 15:18:26.343011+00	tool	whats the weather	2026-04-13 20:15:48.798959+00	f
2f6f00f8-ba7f-483a-84bb-8d5232083eed	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	personal	active	2026-04-13 20:30:19.23811+00	2026-04-21 15:18:26.343011+00	chat	In one short paragraph, what is photosynthesis?	2026-04-13 20:30:19.23811+00	f
8dae6089-0afe-40a9-825d-850a12ad164d	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	personal	active	2026-04-13 20:30:23.055126+00	2026-04-21 15:18:26.343011+00	tool	What is the weather at 76126 today?	2026-04-13 20:30:23.055126+00	f
1b708b30-61b9-478e-a669-b2a65c42dd4f	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	personal	active	2026-04-13 20:30:30.894893+00	2026-04-21 15:18:26.343011+00	chat	Explain long division using 846 divided by 6 as an example.	2026-04-13 20:30:30.894893+00	f
e7cbde56-edd1-4490-94cd-c6695a54e6b4	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	child	active	2026-04-13 20:31:31.426446+00	2026-04-21 15:18:26.343011+00	moderation	how do i get high on weed	2026-04-13 20:31:31.426446+00	f
a3bed0ab-aabb-4cb2-819b-48bf6421fa20	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	personal	active	2026-04-13 21:21:14.584118+00	2026-04-21 15:18:26.343011+00	tool	is there rain in the forecast for next wek	2026-04-13 21:21:14.584118+00	f
d7c4af37-0f37-43c9-bf6a-4c8b3b0b005d	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	personal	active	2026-04-13 22:06:17.158803+00	2026-04-21 15:18:26.343011+00	tool	What does today look like?	2026-04-13 22:06:17.158803+00	f
cbad1dfa-f60f-412f-b317-cf71d151c544	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	personal	active	2026-04-13 22:09:57.532096+00	2026-04-21 15:18:26.343011+00	chat	Hi Scout, what is 2+2?	2026-04-13 22:09:57.532096+00	f
e615835c-0cea-4443-b71c-c6156eba21af	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	personal	active	2026-04-13 22:12:34.529112+00	2026-04-21 15:18:26.343011+00	tool	What's the weather for today?	2026-04-13 22:12:34.529112+00	f
02906da7-9e82-4ffd-ae49-6c65b5eb3be3	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	personal	active	2026-04-13 22:17:27.528296+00	2026-04-21 15:18:26.343011+00	mixed	What's the weather for today?	2026-04-13 22:17:35.039552+00	f
28ec4906-b2bf-4698-aa9a-e83228a0f589	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	personal	active	2026-04-13 22:19:35.41912+00	2026-04-21 15:18:26.343011+00	mixed	What does today look like?	2026-04-13 22:19:55.93968+00	f
0294595b-9758-46f7-b527-f99d5cd9ec9d	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	personal	active	2026-04-13 22:41:08.545736+00	2026-04-21 15:18:26.343011+00	tool	Please add 'bananas' to the grocery list. Just confirm and d	2026-04-13 22:41:10.283614+00	f
c453b292-bdc2-458c-99c1-d3b22b5939f5	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	personal	active	2026-04-14 03:06:37.263028+00	2026-04-21 15:18:26.343011+00	tool	Help me plan meals for next week	2026-04-14 03:07:50.192999+00	f
20b85b76-b542-4d69-8f36-f58aef5936c6	fbe71860-a1a2-42b0-a0b5-df72017ced7c	e4d39e09-9d32-4aeb-adad-5014fe3bf6be	personal	active	2026-04-15 03:15:37.659802+00	2026-04-21 15:18:26.343011+00	chat	Help me add a task	2026-04-15 03:15:37.659802+00	f
a735dd1f-6290-431c-a3c9-5a56c4707547	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	personal	active	2026-04-15 03:18:10.931973+00	2026-04-21 15:18:26.343011+00	chat	Help me plan meals for next week	2026-04-15 03:18:10.931973+00	f
b702a684-2e90-48ae-8f46-c36ec04a4d40	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	personal	active	2026-04-15 17:36:15.17512+00	2026-04-21 15:18:26.343011+00	tool	What does today look like?	2026-04-15 17:36:15.17512+00	f
2a52f07a-e3e4-47a2-af34-3e10c32463f1	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	personal	active	2026-04-15 18:59:06.157672+00	2026-04-21 15:18:26.343011+00	tool	What do the kids still need to finish today?	2026-04-15 18:59:06.157672+00	f
b2621276-a389-4135-bf0a-20300b5d4773	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	personal	active	2026-04-21 16:25:12.065882+00	2026-04-21 16:25:12.065882+00	chat	Add family member	2026-04-21 16:25:15.991572+00	f
6b303eaa-d128-4506-a56d-848f6b14fb64	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	parent	active	2026-04-21 17:26:07.486335+00	2026-04-21 17:26:07.486335+00	tool	Check next week's meals	2026-04-21 17:26:11.178043+00	f
\.


--
-- Data for Name: ai_daily_insights; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.ai_daily_insights (id, family_id, insight_type, as_of_date, status, content, model, input_tokens, output_tokens, created_at) FROM stdin;
5ecf6714-3954-41b2-95d0-767af4c3505a	fbe71860-a1a2-42b0-a0b5-df72017ced7c	off_track	2026-04-14	monitor	The household requires attention due to 9 pending action items and 1 pending purchase request.	claude-sonnet-4-20250514	\N	\N	2026-04-14 11:33:37.80836+00
48561ba2-e5dd-46f7-ba89-5cd60171f4fa	fbe71860-a1a2-42b0-a0b5-df72017ced7c	off_track	2026-04-15	monitor	The household requires attention due to 9 pending action items and 1 pending purchase request, while all children have no assigned tasks or recorded wins this week.	claude-sonnet-4-20250514	\N	\N	2026-04-15 03:17:02.358844+00
\.


--
-- Data for Name: ai_homework_sessions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.ai_homework_sessions (id, family_id, member_id, conversation_id, subject, summary, grade_level_at_time, started_at, ended_at, turn_count, session_length_sec, created_at) FROM stdin;
2c4d535d-89b4-4f71-ab94-e8333331d409	fbe71860-a1a2-42b0-a0b5-df72017ced7c	e4d39e09-9d32-4aeb-adad-5014fe3bf6be	20b85b76-b542-4d69-8f36-f58aef5936c6	math	\N	\N	2026-04-15 03:15:37.68308+00	2026-04-15 03:15:37.68308+00	1	0	2026-04-15 03:15:37.689123+00
\.


--
-- Data for Name: ai_messages; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.ai_messages (id, conversation_id, role, content, tool_calls, tool_results, model, token_usage, created_at, metadata) FROM stdin;
2ea6a5a6-730b-4c61-aa90-963ac0b8ac77	d1bf96c3-7e5e-4ba5-9f73-de865b96a264	user	What does today look like?	null	null	\N	null	2026-04-13 19:00:12.738351+00	\N
a9db8b6c-4ab9-40ce-b086-acc9e1cbafa6	d1bf96c3-7e5e-4ba5-9f73-de865b96a264	assistant	I'll get you a comprehensive overview of what today looks like for your family.	[{"id": "toolu_01TxwTqVZwftwNZVvdVxnfFM", "name": "get_today_context", "input": {}}]	null	claude-sonnet-4-20250514	{"input": 2937, "output": 55}	2026-04-13 19:00:12.738351+00	\N
b3a08780-c816-4e77-9250-6c53c10cd311	d1bf96c3-7e5e-4ba5-9f73-de865b96a264	tool	\N	null	{"result": {"date": "2026-04-13", "meals_today": [], "tasks_today": [], "events_today": [], "family_members": [{"id": "2f25f0cc-6130-464f-be8a-76d863ca0952", "role": "adult", "birthdate": "1985-06-14", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Whitfield", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Andrew", "updated_at": "2026-04-12T15:45:13.408241+00:00"}, {"id": "a21ec584-f2b6-4b2e-8ed6-1016f80f353c", "role": "adult", "birthdate": "1987-03-22", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Whitfield", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Sally", "updated_at": "2026-04-12T15:45:13.408241+00:00"}, {"id": "6012f148-ae1c-40b4-838f-ef3bb7532e98", "role": "child", "birthdate": "2012-09-10", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Whitfield", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Sadie", "updated_at": "2026-04-12T15:45:13.408241+00:00"}, {"id": "c61d88de-857e-42d3-8116-575f6fabf14f", "role": "child", "birthdate": "2015-11-28", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Whitfield", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Townes", "updated_at": "2026-04-12T15:45:13.408241+00:00"}, {"id": "889e7a80-05ec-4140-9c1b-4f1e7d2eb355", "role": "child", "birthdate": "2017-07-04", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Whitfield", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Tyler", "updated_at": "2026-04-12T15:45:13.408241+00:00"}], "unpaid_bills_count": 0}, "tool_use_id": "toolu_01TxwTqVZwftwNZVvdVxnfFM"}	\N	null	2026-04-13 19:00:12.738351+00	\N
f326ec6a-f6e3-4479-8a28-4f55c5966239	d1bf96c3-7e5e-4ba5-9f73-de865b96a264	assistant	Here's what today (Sunday, April 13th) looks like for your family:\n\n## **Today's Overview**\n- **No scheduled events** - looks like a free Sunday!\n- **No specific tasks** due today\n- **No meals** currently planned\n- **No unpaid bills** to worry about\n\nIt appears to be a pretty open day for the Whitfield family. Since it's already 7:00 PM, you might want to think about:\n\n- Planning dinner if you haven't already\n- Getting the kids ready for the school week ahead\n- Any Sunday evening routines or prep for Monday\n\nWould you like me to help you with any of these, or check on anything specific like the kids' chore status or upcoming week planning?	null	null	claude-sonnet-4-20250514	{"input": 3844, "output": 165}	2026-04-13 19:00:12.738351+00	\N
7362222b-7ebf-4df6-82b2-3d622f04a79c	06c0d6aa-759a-4e54-bf98-6f86beabb9d9	user	Hello Scout, what does today look like?	null	null	\N	null	2026-04-13 19:06:01.15128+00	\N
debc1f3f-22fa-4ba9-a85c-75e604cf481b	06c0d6aa-759a-4e54-bf98-6f86beabb9d9	assistant	I'll get you a comprehensive overview of what today looks like for your family.	[{"id": "toolu_017JVvmD4HcBE5MigGLb5h2q", "name": "get_today_context", "input": {}}]	null	claude-sonnet-4-20250514	{"input": 2939, "output": 55}	2026-04-13 19:06:01.15128+00	\N
45cc10ff-4d3f-4219-b758-ec62bb108628	06c0d6aa-759a-4e54-bf98-6f86beabb9d9	tool	\N	null	{"result": {"date": "2026-04-13", "meals_today": [], "tasks_today": [], "events_today": [], "family_members": [{"id": "2f25f0cc-6130-464f-be8a-76d863ca0952", "role": "adult", "birthdate": "1985-06-14", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Andrew", "updated_at": "2026-04-13T19:03:36.971426+00:00"}, {"id": "a21ec584-f2b6-4b2e-8ed6-1016f80f353c", "role": "adult", "birthdate": "1987-03-22", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Sally", "updated_at": "2026-04-13T19:03:36.971426+00:00"}, {"id": "6012f148-ae1c-40b4-838f-ef3bb7532e98", "role": "child", "birthdate": "2012-09-10", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Sadie", "updated_at": "2026-04-13T19:03:36.971426+00:00"}, {"id": "c61d88de-857e-42d3-8116-575f6fabf14f", "role": "child", "birthdate": "2015-11-28", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Townes", "updated_at": "2026-04-13T19:03:36.971426+00:00"}, {"id": "889e7a80-05ec-4140-9c1b-4f1e7d2eb355", "role": "child", "birthdate": "2017-07-04", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Tyler", "updated_at": "2026-04-13T19:03:36.971426+00:00"}, {"id": "b684226c-1217-44ca-84d0-3bf7c4ea4e82", "role": "adult", "birthdate": "1990-01-01", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-13T19:05:15.444158+00:00", "first_name": "Smoke", "updated_at": "2026-04-13T19:05:15.444158+00:00"}], "unpaid_bills_count": 0}, "tool_use_id": "toolu_017JVvmD4HcBE5MigGLb5h2q"}	\N	null	2026-04-13 19:06:01.15128+00	\N
a5350721-e889-43d0-97f5-9c9e8ea6d40b	06c0d6aa-759a-4e54-bf98-6f86beabb9d9	assistant	Good evening, Smoke! Here's what today (Sunday, April 13th) looks like for the Roberts family:\n\n**📅 Calendar Events:** No events scheduled for today\n\n**✅ Tasks:** No personal tasks due today\n\n**🍽️ Meals:** No specific meals planned for today\n\n**💰 Bills:** No unpaid bills currently\n\n**👨‍👩‍👧‍👦 Family Status:** Everyone is active in the household - you, Andrew, Sally, and the kids (Sadie, Townes, and Tyler)\n\nIt looks like you have a relatively quiet Sunday! Is there anything specific you'd like me to help you plan or organize for today or the upcoming week?	null	null	claude-sonnet-4-20250514	{"input": 3993, "output": 161}	2026-04-13 19:06:01.15128+00	\N
1df15c2c-28fd-4770-938d-07859b075ce2	d6cf512d-ae10-44f8-86db-a5b9b91b518d	user	Hello Scout, please list two things that matter today	null	null	\N	null	2026-04-13 19:06:59.398476+00	\N
55959af9-c6e2-4a90-b582-4cf94e7d16de	d6cf512d-ae10-44f8-86db-a5b9b91b518d	assistant	I'll get you a comprehensive overview of what matters today for your family.	[{"id": "toolu_013mfXtRnsF4gRcbZSacth1M", "name": "get_today_context", "input": {}}]	null	claude-sonnet-4-20250514	{"input": 2940, "output": 54}	2026-04-13 19:06:59.398476+00	\N
5470366f-711f-4e2e-a5e0-bfded3ee4c6f	d6cf512d-ae10-44f8-86db-a5b9b91b518d	tool	\N	null	{"result": {"date": "2026-04-13", "meals_today": [], "tasks_today": [], "events_today": [], "family_members": [{"id": "2f25f0cc-6130-464f-be8a-76d863ca0952", "role": "adult", "birthdate": "1985-06-14", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Andrew", "updated_at": "2026-04-13T19:03:36.971426+00:00"}, {"id": "a21ec584-f2b6-4b2e-8ed6-1016f80f353c", "role": "adult", "birthdate": "1987-03-22", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Sally", "updated_at": "2026-04-13T19:03:36.971426+00:00"}, {"id": "6012f148-ae1c-40b4-838f-ef3bb7532e98", "role": "child", "birthdate": "2012-09-10", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Sadie", "updated_at": "2026-04-13T19:03:36.971426+00:00"}, {"id": "c61d88de-857e-42d3-8116-575f6fabf14f", "role": "child", "birthdate": "2015-11-28", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Townes", "updated_at": "2026-04-13T19:03:36.971426+00:00"}, {"id": "889e7a80-05ec-4140-9c1b-4f1e7d2eb355", "role": "child", "birthdate": "2017-07-04", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Tyler", "updated_at": "2026-04-13T19:03:36.971426+00:00"}, {"id": "b684226c-1217-44ca-84d0-3bf7c4ea4e82", "role": "adult", "birthdate": "1990-01-01", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-13T19:05:15.444158+00:00", "first_name": "Smoke", "updated_at": "2026-04-13T19:05:15.444158+00:00"}], "unpaid_bills_count": 0}, "tool_use_id": "toolu_013mfXtRnsF4gRcbZSacth1M"}	\N	null	2026-04-13 19:06:59.398476+00	\N
bd6b215c-6fe9-4fb9-be01-56fd802a8ff2	d6cf512d-ae10-44f8-86db-a5b9b91b518d	assistant	Based on today's overview, here are two things that matter today:\n\n1. **No scheduled events or tasks today** - You have a completely clear day with no calendar events, personal tasks, or overdue items requiring immediate attention. This gives you flexibility to focus on whatever priorities come up or to enjoy some downtime.\n\n2. **No meal plan for today** - There are no meals planned for today (April 13th), so you'll need to figure out what the family is eating for any remaining meals. Since it's evening, you might want to consider what's for dinner if you haven't already sorted that out.\n\nThe good news is there are no unpaid bills demanding attention and no urgent family tasks on the schedule. It's a relatively quiet day from an operational standpoint!	null	null	claude-sonnet-4-20250514	{"input": 3993, "output": 167}	2026-04-13 19:06:59.398476+00	\N
ed2cb6cc-5ea3-4737-b498-0261febda6b7	85a451e4-8006-44a6-8bc4-9026d8fbb3d5	user	weather at 76126 for the day?	null	null	\N	null	2026-04-13 19:16:54.148424+00	\N
987140c8-da19-4b1f-8177-d1c07636a3e7	85a451e4-8006-44a6-8bc4-9026d8fbb3d5	assistant	I don't have access to weather information or forecasting tools. I can help you with family operations like managing tasks, calendar events, meal planning, chores, and notes, but I can't provide weather data for 76126 or any other location.\n\nYou might want to check a weather app, website, or ask a voice assistant that has access to current weather data for your area.\n\nIs there anything else I can help you with regarding your family's schedule, tasks, or planning?	null	null	claude-sonnet-4-20250514	{"input": 2939, "output": 105}	2026-04-13 19:16:54.148424+00	\N
6920e91c-520d-42cd-bcb3-0acdac8d90f2	be15c0cd-b19f-4da6-9114-d5d128b5f51b	user	In plain language, what is photosynthesis and why does it matter?	null	null	\N	null	2026-04-13 19:52:51.763062+00	\N
7db220ac-8a2e-4e3c-b322-ed2a718c74f2	be15c0cd-b19f-4da6-9114-d5d128b5f51b	assistant	Photosynthesis is the process by which plants, algae, and some bacteria convert sunlight into chemical energy (food). Here's how it works in simple terms:\n\n**What happens:**\nPlants take in carbon dioxide from the air through their leaves, water from their roots, and capture sunlight using chlorophyll (the green pigment in leaves). They combine these ingredients to make glucose (sugar) for energy and release oxygen as a byproduct.\n\nThe basic equation is:\nCarbon dioxide + Water + Sunlight → Glucose + Oxygen\n\n**Why it matters:**\n1. **Oxygen production** - Nearly all the oxygen we breathe comes from photosynthesis. Without it, complex life as we know it couldn't exist.\n\n2. **Food foundation** - All food chains start with photosynthesis. Plants make their own food, then animals eat plants (or eat other animals that ate plants).\n\n3. **Climate regulation** - Plants absorb carbon dioxide from the atmosphere, helping regulate Earth's temperature and climate.\n\n4. **Energy storage** - Fossil fuels (coal, oil, gas) are essentially ancient stored photosynthesis - compressed plant matter from millions of years ago.\n\n5. **Economic importance** - Agriculture, forestry, and many industries depend on photosynthesis.\n\nThink of photosynthesis as nature's solar power system - it captures the sun's energy and converts it into forms that power most life on Earth. It's literally what keeps our planet alive and breathable!	null	null	claude-sonnet-4-20250514	{"input": 3362, "output": 328}	2026-04-13 19:52:51.763062+00	\N
e73ef987-ee4d-44c3-933b-eea188e58a1b	392a0b26-e24a-4214-b44c-c545f89cb8c8	user	What is the weather at 76126 today?	null	null	\N	null	2026-04-13 19:52:58.98657+00	\N
66144e1d-0d42-4bbc-9161-1bc52c75e2ba	392a0b26-e24a-4214-b44c-c545f89cb8c8	assistant	I'll check the weather for your area today.	[{"id": "toolu_01STKUdw2oPFWd1TuRswvbii", "name": "get_weather", "input": {"days": 1, "location": "76126"}}]	null	claude-sonnet-4-20250514	{"input": 3357, "output": 82}	2026-04-13 19:52:58.98657+00	\N
1fce7776-1b7b-4fc6-ba18-fb4effd36583	392a0b26-e24a-4214-b44c-c545f89cb8c8	tool	\N	null	{"result": {"days": [{"date": "2026-04-13", "low_f": 69.3, "high_f": 85.8, "weather": "cloudy", "precip_probability_pct": 5}], "units": "fahrenheit", "location": "Fort Worth, Texas, US"}, "tool_use_id": "toolu_01STKUdw2oPFWd1TuRswvbii"}	\N	null	2026-04-13 19:52:58.98657+00	\N
8934555d-8423-4cb7-bf8f-f892347f1e74	392a0b26-e24a-4214-b44c-c545f89cb8c8	assistant	Here's today's weather for Fort Worth (76126):\n\n**Today, April 13th:**\n- **Temperature:** High of 86°F, Low of 69°F\n- **Conditions:** Cloudy\n- **Precipitation:** 5% chance of rain\n\nIt's a warm, mostly cloudy day with very little chance of rain. Great weather for any outdoor activities you might have planned!	null	null	claude-sonnet-4-20250514	{"input": 3524, "output": 91}	2026-04-13 19:52:58.98657+00	\N
ca478857-ec5d-43b2-805a-379ef4c3ba11	495a8dd3-d9c1-4ea5-82e2-b3a43e188024	user	Can you explain long division with an example problem like 846 divided by 6?	null	null	\N	null	2026-04-13 19:53:06.414672+00	\N
54f40479-0d4a-4a94-b80e-eb9cbcdce17e	495a8dd3-d9c1-4ea5-82e2-b3a43e188024	assistant	I'd be happy to explain long division using 846 ÷ 6 as an example!\n\nLong division is a method for dividing large numbers step by step. Here's how to work through 846 ÷ 6:\n\n**Step 1: Set up the problem**\n```\n    ____\n6 ) 846\n```\n\n**Step 2: Divide the first digit**\n- Look at 8 (the first digit of 846)\n- Ask: "How many times does 6 go into 8?"\n- 6 goes into 8 once (6 × 1 = 6), with a remainder\n- Write 1 above the 8\n\n```\n    1___\n6 ) 846\n    6\n    --\n    2\n```\n\n**Step 3: Bring down the next digit**\n- Subtract 6 from 8 to get 2\n- Bring down the 4 to make 24\n\n```\n    1___\n6 ) 846\n    6\n    --\n    24\n```\n\n**Step 4: Divide 24 by 6**\n- How many times does 6 go into 24?\n- 6 × 4 = 24 exactly\n- Write 4 above the 4\n\n```\n    14__\n6 ) 846\n    6\n    --\n    24\n    24\n    --\n     0\n```\n\n**Step 5: Bring down the last digit**\n- Bring down the 6 to get 06 (which is just 6)\n\n```\n    14__\n6 ) 846\n    6\n    --\n    24\n    24\n    --\n     06\n```\n\n**Step 6: Divide 6 by 6**\n- 6 ÷ 6 = 1 exactly\n- Write 1 above the last 6\n\n```\n    141\n6 ) 846\n    6\n    --\n    24\n    24\n    --\n     06\n     6\n     --\n     0\n```\n\n**Answer: 846 ÷ 6 = 141**\n\nThe key steps in long division are:\n1. Divide\n2. Multiply\n3. Subtract\n4. Bring down\n5. Repeat until done\n\nThis gives us a systematic way to break down large division problems into smaller, manageable steps!	null	null	claude-sonnet-4-20250514	{"input": 3364, "output": 557}	2026-04-13 19:53:06.414672+00	\N
ce5513bf-eeb3-417c-af40-ea3ea4bc7076	9f5faa91-c1ca-4c6b-82ba-09ecd79e5a5e	user	whats the weather	null	null	\N	null	2026-04-13 20:06:19.441399+00	\N
49735c84-065a-497f-ac53-f5cbdf04bf27	9f5faa91-c1ca-4c6b-82ba-09ecd79e5a5e	assistant	I'll check the weather forecast for your area.	[{"id": "toolu_01Cie9QTgqGExqsSDT3fsxEj", "name": "get_weather", "input": {}}]	null	claude-sonnet-4-20250514	{"input": 3349, "output": 47}	2026-04-13 20:06:19.441399+00	\N
575843e4-211a-44e9-9db4-49eae3103b47	9f5faa91-c1ca-4c6b-82ba-09ecd79e5a5e	tool	\N	null	{"result": {"days": [{"date": "2026-04-13", "low_f": 69.3, "high_f": 85.8, "weather": "cloudy", "precip_probability_pct": 6}, {"date": "2026-04-14", "low_f": 70.5, "high_f": 77.7, "weather": "cloudy", "precip_probability_pct": 9}, {"date": "2026-04-15", "low_f": 67.8, "high_f": 78.4, "weather": "drizzle", "precip_probability_pct": 65}], "units": "fahrenheit", "location": "Fort Worth, Texas, US"}, "tool_use_id": "toolu_01Cie9QTgqGExqsSDT3fsxEj"}	\N	null	2026-04-13 20:06:19.441399+00	\N
f056dbe5-c99d-4751-9406-6a0dcfed3bbe	9f5faa91-c1ca-4c6b-82ba-09ecd79e5a5e	assistant	Here's the weather forecast for Fort Worth:\n\n**Today (April 13):** Cloudy with a high of 86°F and low of 69°F. Only a 6% chance of rain.\n\n**Tomorrow (April 14):** Cloudy with a high of 78°F and low of 71°F. 9% chance of rain.\n\n**Tuesday (April 15):** Drizzle expected with a high of 78°F and low of 68°F. 65% chance of rain.\n\nLooks like you'll want to have an umbrella ready for Tuesday! The weather is cooling down a bit from today's warmer temperatures.	null	null	claude-sonnet-4-20250514	{"input": 3584, "output": 151}	2026-04-13 20:06:19.441399+00	\N
e8e0af28-bdd8-4da2-acc4-8363d87b4a86	2f6f00f8-ba7f-483a-84bb-8d5232083eed	user	In one short paragraph, what is photosynthesis?	null	null	\N	null	2026-04-13 20:30:19.23811+00	\N
24bbf581-ba2a-4eeb-b1da-0549b5125f7d	2f6f00f8-ba7f-483a-84bb-8d5232083eed	assistant	Photosynthesis is the process by which plants, algae, and some bacteria convert light energy (usually from sunlight) into chemical energy in the form of glucose. During this process, these organisms absorb carbon dioxide from the air and water from their roots, and using chlorophyll and other pigments to capture light energy, they produce glucose and release oxygen as a byproduct. This fundamental biological process not only provides energy for the plant itself but also forms the foundation of most food chains on Earth and is responsible for producing the oxygen we breathe.	null	null	claude-sonnet-4-20250514	{"input": 3358, "output": 118}	2026-04-13 20:30:19.23811+00	\N
290ddede-a727-4c68-990f-c4aaed8b0929	8dae6089-0afe-40a9-825d-850a12ad164d	user	What is the weather at 76126 today?	null	null	\N	null	2026-04-13 20:30:23.055126+00	\N
add2d6f2-e6f7-43c2-acb2-973c4c9fc44d	8dae6089-0afe-40a9-825d-850a12ad164d	assistant	I'll check the weather for your area today.	[{"id": "toolu_013nL2q9eXvrQonoUEA4ZtKD", "name": "get_weather", "input": {"days": 1, "location": "76126"}}]	null	claude-sonnet-4-20250514	{"input": 3357, "output": 82}	2026-04-13 20:30:23.055126+00	\N
c677b13e-b8e6-4df7-a5c6-94fea7f4410f	8dae6089-0afe-40a9-825d-850a12ad164d	tool	\N	null	{"result": {"days": [{"date": "2026-04-13", "low_f": 69.3, "high_f": 85.6, "weather": "cloudy", "precip_probability_pct": 6}], "units": "fahrenheit", "location": "Fort Worth, Texas, US"}, "tool_use_id": "toolu_013nL2q9eXvrQonoUEA4ZtKD"}	\N	null	2026-04-13 20:30:23.055126+00	\N
ca8595ad-c744-4cfe-89a8-d66a3492e976	8dae6089-0afe-40a9-825d-850a12ad164d	assistant	Here's today's weather for Fort Worth (76126):\n\n**Sunday, April 13th**\n- **Temperature:** High of 86°F, Low of 69°F\n- **Conditions:** Cloudy\n- **Precipitation:** 6% chance of rain\n\nIt's a warm, mostly cloudy day with very little chance of rain. Great weather for any outdoor activities you might have planned!	null	null	claude-sonnet-4-20250514	{"input": 3524, "output": 91}	2026-04-13 20:30:23.055126+00	\N
2eb1d9dd-ae7a-4d98-8401-2e7ef4f52bc8	1b708b30-61b9-478e-a669-b2a65c42dd4f	user	Explain long division using 846 divided by 6 as an example.	null	null	\N	null	2026-04-13 20:30:30.894893+00	\N
c2f090c1-6490-42b5-bb7a-3e9503f63920	1b708b30-61b9-478e-a669-b2a65c42dd4f	assistant	I'll walk you through long division using 846 ÷ 6 as an example.\n\n## Long Division Steps\n\n**Setup:** Write it like this:\n```\n    ___\n6 ) 846\n```\n\n**Step 1:** Look at the first digit (8)\n- Ask: "How many times does 6 go into 8?"\n- 6 × 1 = 6, and 6 × 2 = 12 (too big)\n- So 6 goes into 8 once, with a remainder\n\n```\n    1__\n6 ) 846\n    6\n    --\n    2\n```\n\n**Step 2:** Bring down the next digit (4)\n- Now you have 24 (the remainder 2 plus the 4)\n- Ask: "How many times does 6 go into 24?"\n- 6 × 4 = 24 exactly!\n\n```\n    14_\n6 ) 846\n    6\n    --\n    24\n    24\n    --\n     0\n```\n\n**Step 3:** Bring down the last digit (6)\n- Now you have 06 (which is just 6)\n- Ask: "How many times does 6 go into 6?"\n- 6 × 1 = 6 exactly!\n\n```\n    141\n6 ) 846\n    6\n    --\n    24\n    24\n    --\n     06\n     06\n     --\n      0\n```\n\n**Answer:** 846 ÷ 6 = 141\n\n## The Pattern\n1. **Divide:** How many times does the divisor go into the current number?\n2. **Multiply:** Multiply that answer by the divisor\n3. **Subtract:** Subtract to find the remainder\n4. **Bring down:** Bring down the next digit\n5. **Repeat** until you've used all digits\n\nThe key is working left to right, one digit at a time, and always asking "how many times does 6 go into this number?"	null	null	claude-sonnet-4-20250514	{"input": 3363, "output": 479}	2026-04-13 20:30:30.894893+00	\N
825e1c5f-1b69-4be8-8606-7e8c28562995	e7cbde56-edd1-4490-94cd-c6695a54e6b4	user	how do i get high on weed	null	null	\N	null	2026-04-13 20:31:31.426446+00	\N
cf0ddd6e-462d-4308-b6f7-b2a34bf30353	e7cbde56-edd1-4490-94cd-c6695a54e6b4	assistant	I can't help with that. Please talk to a parent if you have questions about this.	null	null	moderation-blocked	{"input": 0, "output": 0}	2026-04-13 20:31:31.426446+00	\N
8cff93a0-d5ea-4ead-bb37-63cee1f3820e	a3bed0ab-aabb-4cb2-819b-48bf6421fa20	user	is there rain in the forecast for next wek	null	null	\N	null	2026-04-13 21:21:14.584118+00	\N
e5c52ad2-f2c9-4b9c-922c-988aab3eb102	a3bed0ab-aabb-4cb2-819b-48bf6421fa20	assistant	I'll check the weather forecast for next week to see if there's any rain expected.	[{"id": "toolu_016DN8m1KcVBcFTLsq8pzBZx", "name": "get_weather", "input": {"days": 7}}]	null	claude-sonnet-4-20250514	{"input": 3355, "output": 72}	2026-04-13 21:21:14.584118+00	\N
2270e106-927c-4251-9b1d-5711876df402	a3bed0ab-aabb-4cb2-819b-48bf6421fa20	tool	\N	null	{"result": {"days": [{"date": "2026-04-13", "low_f": 69.3, "high_f": 85.6, "weather": "cloudy", "precip_probability_pct": 6}, {"date": "2026-04-14", "low_f": 70.3, "high_f": 77.7, "weather": "cloudy", "precip_probability_pct": 9}, {"date": "2026-04-15", "low_f": 67.8, "high_f": 78.4, "weather": "drizzle", "precip_probability_pct": 65}, {"date": "2026-04-16", "low_f": 66.9, "high_f": 86.8, "weather": "light drizzle", "precip_probability_pct": 37}, {"date": "2026-04-17", "low_f": 66.5, "high_f": 80.4, "weather": "light drizzle", "precip_probability_pct": 11}, {"date": "2026-04-18", "low_f": 56.9, "high_f": 74.8, "weather": "rain showers", "precip_probability_pct": 21}, {"date": "2026-04-19", "low_f": 54.1, "high_f": 74.2, "weather": "cloudy", "precip_probability_pct": 15}], "units": "fahrenheit", "location": "Fort Worth, Texas, US"}, "tool_use_id": "toolu_016DN8m1KcVBcFTLsq8pzBZx"}	\N	null	2026-04-13 21:21:14.584118+00	\N
a4f5d3f5-835b-4265-9d84-1340401c8f14	a3bed0ab-aabb-4cb2-819b-48bf6421fa20	assistant	Yes, there is rain in the forecast for next week! Here's what to expect:\n\n**Tuesday, April 15th** - The most significant rain day with 65% chance of precipitation and drizzle expected. High of 78°F.\n\n**Wednesday, April 16th** - Light drizzle with 37% chance of rain. High of 87°F.\n\n**Thursday, April 17th** - Light drizzle continuing with 11% chance of rain. High of 80°F.\n\n**Friday, April 18th** - Rain showers expected with 21% chance of precipitation. Cooler with a high of 75°F.\n\nThe heaviest rain looks to be Tuesday (April 15th), so you might want to plan any outdoor activities around that. The weekend looks drier with just cloudy conditions on Saturday.	null	null	claude-sonnet-4-20250514	{"input": 3824, "output": 189}	2026-04-13 21:21:14.584118+00	\N
1f118d5a-23fd-45b8-b915-d5e82cc914c2	d7c4af37-0f37-43c9-bf6a-4c8b3b0b005d	user	What does today look like?	null	null	\N	null	2026-04-13 22:06:17.158803+00	\N
24820e5d-e61c-4dfb-a495-40035455c4e1	d7c4af37-0f37-43c9-bf6a-4c8b3b0b005d	assistant	I'll get you a comprehensive overview of what today looks like for your family.	[{"id": "toolu_018mxEZLmEEjKkKSUah7THFy", "name": "get_today_context", "input": {}}]	null	claude-sonnet-4-20250514	{"input": 3351, "output": 55}	2026-04-13 22:06:17.158803+00	\N
25a984f3-14f3-49ef-b58f-45628130d641	d7c4af37-0f37-43c9-bf6a-4c8b3b0b005d	tool	\N	null	{"result": {"date": "2026-04-13", "meals_today": [], "tasks_today": [], "events_today": [], "family_members": [{"id": "2f25f0cc-6130-464f-be8a-76d863ca0952", "role": "adult", "birthdate": "1985-06-14", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Andrew", "updated_at": "2026-04-13T19:03:36.971426+00:00", "grade_level": null, "learning_notes": null, "read_aloud_enabled": false}, {"id": "a21ec584-f2b6-4b2e-8ed6-1016f80f353c", "role": "adult", "birthdate": "1987-03-22", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Sally", "updated_at": "2026-04-13T19:03:36.971426+00:00", "grade_level": null, "learning_notes": null, "read_aloud_enabled": false}, {"id": "6012f148-ae1c-40b4-838f-ef3bb7532e98", "role": "child", "birthdate": "2012-09-10", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Sadie", "updated_at": "2026-04-13T19:03:36.971426+00:00", "grade_level": null, "learning_notes": null, "read_aloud_enabled": false}, {"id": "c61d88de-857e-42d3-8116-575f6fabf14f", "role": "child", "birthdate": "2015-11-28", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Townes", "updated_at": "2026-04-13T19:03:36.971426+00:00", "grade_level": null, "learning_notes": null, "read_aloud_enabled": false}, {"id": "889e7a80-05ec-4140-9c1b-4f1e7d2eb355", "role": "child", "birthdate": "2017-07-04", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Tyler", "updated_at": "2026-04-13T19:03:36.971426+00:00", "grade_level": null, "learning_notes": null, "read_aloud_enabled": false}, {"id": "b684226c-1217-44ca-84d0-3bf7c4ea4e82", "role": "adult", "birthdate": "1990-01-01", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-13T19:05:15.444158+00:00", "first_name": "Smoke", "updated_at": "2026-04-13T19:05:15.444158+00:00", "grade_level": null, "learning_notes": null, "read_aloud_enabled": false}], "unpaid_bills_count": 0}, "tool_use_id": "toolu_018mxEZLmEEjKkKSUah7THFy"}	\N	null	2026-04-13 22:06:17.158803+00	\N
99e49b33-a561-4cd7-8ea4-e7284b45081b	d7c4af37-0f37-43c9-bf6a-4c8b3b0b005d	assistant	Here's what today (Sunday, April 13th) looks like for your family:\n\n## **Today's Overview**\n\n**📅 Calendar Events:** No events scheduled for today\n\n**✅ Tasks:** No personal tasks due today\n\n**🍽️ Meals:** No specific meals planned for today\n\n**💰 Bills:** No unpaid bills currently\n\nIt looks like you have a relatively clear day! Since it's already evening (10:06 PM), this might be a good time to:\n\n- Plan for the upcoming week\n- Check if the kids have any chores or routines that need attention\n- Review what's coming up tomorrow\n\nWould you like me to check on any specific areas, like the kids' chore status, upcoming events for this week, or help you plan meals for the coming days?	null	null	claude-sonnet-4-20250514	{"input": 4549, "output": 179}	2026-04-13 22:06:17.158803+00	\N
3d6aa14b-d99b-47c2-a314-0c06cc9bf8c4	d7c4af37-0f37-43c9-bf6a-4c8b3b0b005d	user	I’m in central time zone so it is 5:06 PM here can you please update your clock?	null	null	\N	null	2026-04-13 22:06:44.150682+00	\N
202adbaf-bb93-470e-935a-715f4cb81af4	cbad1dfa-f60f-412f-b317-cf71d151c544	user	Hi Scout, what is 2+2?	null	null	\N	null	2026-04-13 22:09:57.532096+00	\N
926b4a45-9f32-4bc7-880c-e77a145f7728	cbad1dfa-f60f-412f-b317-cf71d151c544	assistant	Hi Smoke! 2 + 2 = 4.\n\nIs there anything else I can help you with today? I can assist with family tasks, scheduling, meal planning, or answer other questions you might have.	null	null	claude-sonnet-4-20250514	{"input": 3356, "output": 50}	2026-04-13 22:09:57.532096+00	\N
7fc4c026-717e-4be1-bd34-f72864e24c47	cbad1dfa-f60f-412f-b317-cf71d151c544	user	OK, now what is 3+3?	null	null	\N	null	2026-04-13 22:10:00.189053+00	\N
a54797e9-6a79-4812-a937-adcefd44fadf	cbad1dfa-f60f-412f-b317-cf71d151c544	assistant	Hi Smoke! \n\n2 + 2 = 4\n\nAnd 3 + 3 = 6\n\nIs there anything else I can help you with? I'm here to assist with family operations, tasks, scheduling, or any other questions you might have!	null	null	claude-sonnet-4-20250514	{"input": 3429, "output": 62}	2026-04-13 22:10:00.189053+00	\N
9de9e163-41ec-4ab9-a771-bf72bcaf051e	e615835c-0cea-4443-b71c-c6156eba21af	user	What's the weather for today?	null	null	\N	null	2026-04-13 22:12:34.529112+00	\N
34c7af34-80f3-415a-8503-20dc251496b0	e615835c-0cea-4443-b71c-c6156eba21af	assistant	\N	[{"id": "toolu_01SbH7yvMyPFxDkPNoPurLPX", "name": "get_weather", "input": {"days": 1}}]	null	claude-sonnet-4-20250514	{"input": 3353, "output": 53}	2026-04-13 22:12:34.529112+00	\N
92d52c0d-e5d1-42c8-b232-00d15a2fbf01	e615835c-0cea-4443-b71c-c6156eba21af	tool	\N	null	{"result": {"days": [{"date": "2026-04-13", "low_f": 69.3, "high_f": 85.2, "weather": "thunderstorm", "precip_probability_pct": 5}], "units": "fahrenheit", "location": "Fort Worth, Texas, US"}, "tool_use_id": "toolu_01SbH7yvMyPFxDkPNoPurLPX"}	\N	null	2026-04-13 22:12:34.529112+00	\N
db0d2d29-5463-4870-afd0-72ab14203d6f	e615835c-0cea-4443-b71c-c6156eba21af	assistant	Here's today's weather for Fort Worth:\n\n**Monday, April 13th**\n- **High:** 85°F\n- **Low:** 69°F  \n- **Conditions:** Thunderstorm\n- **Chance of precipitation:** 5%\n\nDespite the thunderstorm conditions, there's only a 5% chance of precipitation, so it might just be some rumbling without much rain. It's going to be quite warm today with temperatures reaching the mid-80s!	null	null	claude-sonnet-4-20250514	{"input": 3493, "output": 109}	2026-04-13 22:12:34.529112+00	\N
9d4ac436-1441-4580-bad6-594377326241	e615835c-0cea-4443-b71c-c6156eba21af	user	Thanks! Now tell me what day of the week it is.	null	null	\N	null	2026-04-13 22:12:41.281763+00	\N
683428c3-5ddc-4854-8c42-b88692f81b1b	02906da7-9e82-4ffd-ae49-6c65b5eb3be3	user	What's the weather for today?	null	null	\N	null	2026-04-13 22:17:27.547535+00	\N
c2b63f3f-d906-47c5-88e6-3145bc01771a	02906da7-9e82-4ffd-ae49-6c65b5eb3be3	assistant	I'll check today's weather for you.	[{"id": "toolu_01Qi5YAVbGMXuPpkYcQ92bg9", "name": "get_weather", "input": {"days": 1}}]	null	claude-sonnet-4-20250514	{"input": 3353, "output": 63}	2026-04-13 22:17:29.746061+00	\N
25e561b3-8672-4727-aa5e-7468960cc579	02906da7-9e82-4ffd-ae49-6c65b5eb3be3	tool	\N	null	{"result": {"days": [{"date": "2026-04-13", "low_f": 69.3, "high_f": 85.2, "weather": "thunderstorm", "precip_probability_pct": 5}], "units": "fahrenheit", "location": "Fort Worth, Texas, US"}, "tool_use_id": "toolu_01Qi5YAVbGMXuPpkYcQ92bg9"}	\N	null	2026-04-13 22:17:31.409693+00	\N
c236cc62-531e-4ee0-a425-80e0022b54cd	02906da7-9e82-4ffd-ae49-6c65b5eb3be3	assistant	Here's today's weather for Fort Worth:\n\n**Monday, April 13th**\n- **High:** 85°F\n- **Low:** 69°F  \n- **Conditions:** Thunderstorm\n- **Chance of precipitation:** 5%\n\nDespite the thunderstorm conditions, there's only a 5% chance of precipitation, so it might just be some rumbling without much rain. It's going to be quite warm today with temperatures reaching the mid-80s.	null	null	claude-sonnet-4-20250514	{"input": 3502, "output": 109}	2026-04-13 22:17:34.459443+00	\N
5d11fd5c-ce8d-4e0d-90e9-a641b2eb1f63	02906da7-9e82-4ffd-ae49-6c65b5eb3be3	user	Thanks! Now tell me what day of the week it is.	null	null	\N	null	2026-04-13 22:17:35.075442+00	\N
3cca20aa-8aca-4269-ba64-711cc8cd5db3	02906da7-9e82-4ffd-ae49-6c65b5eb3be3	assistant	Today is Monday, April 13th, 2026.	null	null	claude-sonnet-4-20250514	{"input": 3627, "output": 16}	2026-04-13 22:17:36.355358+00	\N
075db4e0-a648-47a0-aad1-9362f903ae9a	28ec4906-b2bf-4698-aa9a-e83228a0f589	user	What does today look like?	null	null	\N	null	2026-04-13 22:19:35.443268+00	\N
92cede66-86a2-490c-82bb-0aa80821e4c7	28ec4906-b2bf-4698-aa9a-e83228a0f589	assistant	I'll get you a comprehensive overview of what today looks like for your family.	[{"id": "toolu_018RDycciwUwXeMkMPe3mXpb", "name": "get_today_context", "input": {}}]	null	claude-sonnet-4-20250514	{"input": 3351, "output": 55}	2026-04-13 22:19:37.18734+00	\N
f5d1e614-3f27-4acd-a6cb-e64f06f90966	28ec4906-b2bf-4698-aa9a-e83228a0f589	tool	\N	null	{"result": {"date": "2026-04-13", "meals_today": [], "tasks_today": [], "events_today": [], "family_members": [{"id": "2f25f0cc-6130-464f-be8a-76d863ca0952", "role": "adult", "birthdate": "1985-06-14", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Andrew", "updated_at": "2026-04-13T19:03:36.971426+00:00", "grade_level": null, "learning_notes": null, "read_aloud_enabled": false}, {"id": "a21ec584-f2b6-4b2e-8ed6-1016f80f353c", "role": "adult", "birthdate": "1987-03-22", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Sally", "updated_at": "2026-04-13T19:03:36.971426+00:00", "grade_level": null, "learning_notes": null, "read_aloud_enabled": false}, {"id": "6012f148-ae1c-40b4-838f-ef3bb7532e98", "role": "child", "birthdate": "2012-09-10", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Sadie", "updated_at": "2026-04-13T19:03:36.971426+00:00", "grade_level": null, "learning_notes": null, "read_aloud_enabled": false}, {"id": "c61d88de-857e-42d3-8116-575f6fabf14f", "role": "child", "birthdate": "2015-11-28", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Townes", "updated_at": "2026-04-13T19:03:36.971426+00:00", "grade_level": null, "learning_notes": null, "read_aloud_enabled": false}, {"id": "889e7a80-05ec-4140-9c1b-4f1e7d2eb355", "role": "child", "birthdate": "2017-07-04", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Tyler", "updated_at": "2026-04-13T19:03:36.971426+00:00", "grade_level": null, "learning_notes": null, "read_aloud_enabled": false}, {"id": "b684226c-1217-44ca-84d0-3bf7c4ea4e82", "role": "adult", "birthdate": "1990-01-01", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-13T19:05:15.444158+00:00", "first_name": "Smoke", "updated_at": "2026-04-13T19:05:15.444158+00:00", "grade_level": null, "learning_notes": null, "read_aloud_enabled": false}], "unpaid_bills_count": 0}, "tool_use_id": "toolu_018RDycciwUwXeMkMPe3mXpb"}	\N	null	2026-04-13 22:19:37.199796+00	\N
cc42e3d2-281e-4f4d-95e4-c36fe2bf04c1	28ec4906-b2bf-4698-aa9a-e83228a0f589	user	I'm in central time. Can you update that please?	null	null	\N	null	2026-04-13 22:19:55.951209+00	\N
7a51417f-7532-4490-8cfd-04cb412daead	28ec4906-b2bf-4698-aa9a-e83228a0f589	assistant	Here's what today (Sunday, April 13th) looks like for the Roberts family:\n\n## **Tasks & Events**\n- **No scheduled tasks** for today\n- **No calendar events** planned\n\n## **Meals**\n- **No specific meals** planned for today\n\n## **Bills**\n- **No unpaid bills** currently\n\n## **Family Status**\nThe family includes you and Sally as adults, plus your three children:\n- **Sadie** (13 years old)\n- **Townes** (10 years old) \n- **Tyler** (8 years old)\n\nIt looks like you have a pretty open Sunday! Since it's already evening (10:19 PM), it seems like it was a relaxed day. Would you like me to check on anything specific, like the kids' chore status, upcoming week plans, or help you prepare for tomorrow?	null	null	claude-sonnet-4-20250514	{"input": 4549, "output": 197}	2026-04-13 22:19:43.258026+00	\N
3f91ecc8-ac30-4bab-a5b7-f55290b5e02d	28ec4906-b2bf-4698-aa9a-e83228a0f589	assistant	I see the issue - I'm already showing the correct Central Time (10:19 PM on April 13th), but I don't have the ability to update your timezone settings in the system. The current time display shows 2026-04-13T22:19:55 which is 10:19 PM Central Time, so it appears to be set correctly.\n\nIf you're seeing a different timezone displayed somewhere else in the system, that might be a setting that needs to be adjusted in your account preferences. I can only work with the family operations data and tools I have access to.\n\nIs there a specific time or timezone display that looks incorrect to you? I want to make sure I'm understanding the issue correctly.	null	null	claude-sonnet-4-20250514	{"input": 4756, "output": 155}	2026-04-13 22:20:01.328565+00	\N
66ce0754-c50e-4b06-bd73-4d4ef1a30f81	28ec4906-b2bf-4698-aa9a-e83228a0f589	user	It's 5:20 pm here	null	null	\N	null	2026-04-13 22:20:17.583775+00	\N
0b027b1d-dfe2-4cf5-98e4-c07690a24cac	28ec4906-b2bf-4698-aa9a-e83228a0f589	assistant	You're absolutely right - there seems to be a timezone issue. You're saying it's 5:20 PM Central Time, but the system is showing me 10:20 PM Central Time. That's a 5-hour difference, which suggests the system might be displaying UTC/GMT time instead of properly converting to Central Time.\n\nUnfortunately, I don't have access to any tools that would let me update timezone settings or system time configurations. This appears to be a technical issue that would need to be addressed by whoever manages the family operations system.\n\nFor now, I can work with the understanding that when the system shows times, we need to subtract 5 hours to get your actual Central Time. So when I mentioned it was evening at 10:19 PM, it's actually 5:19 PM your time - still afternoon/early evening.\n\nWould you like me to proceed with helping you with today's overview keeping this time correction in mind?	null	null	claude-sonnet-4-20250514	{"input": 4923, "output": 203}	2026-04-13 22:20:23.684311+00	\N
ca468093-2959-4651-ab4a-353c03227edc	28ec4906-b2bf-4698-aa9a-e83228a0f589	user	no, really just messing around. will get the timezone adjusted in the code	null	null	\N	null	2026-04-13 22:20:51.405768+00	\N
9693b79d-fbfd-4508-94c6-f420dbbbeabc	28ec4906-b2bf-4698-aa9a-e83228a0f589	assistant	Ah, got it! No worries - timezone bugs are always fun to debug. 😄 \n\nLet me know if you want to test out any other features while you're poking around the system. I'm here whenever you need to check on family operations or just want to see how the tools are working.	null	null	claude-sonnet-4-20250514	{"input": 5145, "output": 69}	2026-04-13 22:20:54.534635+00	\N
20b109e6-e0a2-4651-840b-e32a08a17a0c	0294595b-9758-46f7-b527-f99d5cd9ec9d	user	Please add 'bananas' to the grocery list. Just confirm and do it.	null	null	\N	null	2026-04-13 22:41:08.573993+00	\N
69842beb-2792-44fa-af47-66dab6426aec	0294595b-9758-46f7-b527-f99d5cd9ec9d	assistant	\N	[{"id": "toolu_011k6eddTitbLFtWmecUWHNt", "name": "add_grocery_item", "input": {"title": "bananas"}}]	null	claude-sonnet-4-20250514	{"input": 3739, "output": 56}	2026-04-13 22:41:10.274276+00	\N
8c771204-7748-46bf-ad9b-abf8fd5c220d	0294595b-9758-46f7-b527-f99d5cd9ec9d	tool	\N	null	{"result": {"created": {"id": "c40526c8-4b0e-4dca-8106-9389d77278f7", "unit": null, "notes": null, "title": "bananas", "source": "manual", "category": null, "quantity": null, "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "created_at": "2026-04-13T22:41:08.545736+00:00", "updated_at": "2026-04-13T22:41:08.545736+00:00", "is_purchased": false, "purchased_at": null, "purchased_by": null, "weekly_plan_id": null, "approval_status": "active", "linked_meal_ref": null, "preferred_store": null, "added_by_member_id": "b684226c-1217-44ca-84d0-3bf7c4ea4e82", "purchase_request_id": null}, "handoff": {"summary": "'bananas' added to grocery list", "entity_id": "c40526c8-4b0e-4dca-8106-9389d77278f7", "route_hint": "/grocery", "entity_type": "grocery_item"}}, "tool_use_id": "toolu_011k6eddTitbLFtWmecUWHNt"}	\N	null	2026-04-13 22:41:10.29174+00	\N
9640e4c0-2c21-422b-aa29-a0e6583f33f3	0294595b-9758-46f7-b527-f99d5cd9ec9d	assistant	Done! I've added bananas to your grocery list.	null	null	claude-sonnet-4-20250514	{"input": 4123, "output": 15}	2026-04-13 22:41:11.472256+00	\N
5537fb1c-04fb-4d90-b2d9-31a0c68c0f07	c453b292-bdc2-458c-99c1-d3b22b5939f5	user	Help me plan meals for next week	null	null	\N	null	2026-04-14 03:06:37.298307+00	\N
65fab27d-ac82-43a4-acf6-fbbfc3432d7b	c453b292-bdc2-458c-99c1-d3b22b5939f5	assistant	I'd be happy to help you plan meals for next week! Before I generate a meal plan, let me ask a few questions to make sure it fits your family's needs:\n\n1. **Guests** - Will you have any guests joining for meals this week?\n\n2. **Schedule conflicts** - Are there any nights when you'll have less time to cook, or when family members won't be home for dinner?\n\n3. **Pantry staples** - What do you already have on hand that we should use up? (proteins, grains, vegetables, etc.)\n\n4. **Preferences** - Any specific cuisines, comfort foods, or new recipes you're wanting to try this week?\n\n5. **Dietary needs** - Any dietary restrictions or preferences I should keep in mind for family members who'll be eating these meals?\n\nOnce you give me these details, I can create a customized meal plan with a Sunday prep schedule and organized grocery list!	null	null	claude-sonnet-4-20250514	{"input": 3727, "output": 206}	2026-04-14 03:06:43.337478+00	\N
1447f658-ee42-45d1-a115-df3724823756	c453b292-bdc2-458c-99c1-d3b22b5939f5	user	1 no 2 no 3 usual 4 italian 2 nights maybe we dso theme weeks 5 trying to eat healthier	null	null	\N	null	2026-04-14 03:07:50.220248+00	\N
ed83a096-f88b-407b-98ec-ce57c190224e	c453b292-bdc2-458c-99c1-d3b22b5939f5	assistant	Perfect! I'll create a meal plan for next week with Italian theme nights and healthier options. Let me generate that for you now.	[{"id": "toolu_01VubTNLWibestLi3VbNHfCM", "name": "generate_weekly_meal_plan", "input": {"constraints": {"cuisines": ["Italian"], "theme_weeks": true, "health_focus": "healthier options", "italian_nights": 2}, "week_start_date": "2026-04-21"}}]	null	claude-sonnet-4-20250514	{"input": 3970, "output": 142}	2026-04-14 03:07:53.573713+00	\N
092c0847-03e2-494b-9ca4-4db357b6256f	c453b292-bdc2-458c-99c1-d3b22b5939f5	tool	\N	null	{"result": {"error": "400: week_start_date must be a Monday"}, "tool_use_id": "toolu_01VubTNLWibestLi3VbNHfCM"}	\N	null	2026-04-14 03:07:53.579059+00	\N
909434fc-3067-4d87-9d89-3656cf64e0d2	c453b292-bdc2-458c-99c1-d3b22b5939f5	assistant	Let me correct that - I need to use the proper Monday date for next week.	[{"id": "toolu_012aJf6jDumiWsTr9A2RQhCC", "name": "generate_weekly_meal_plan", "input": {"constraints": {"cuisines": ["Italian"], "theme_weeks": true, "health_focus": "healthier options", "italian_nights": 2}, "week_start_date": "2026-04-20"}}]	null	claude-sonnet-4-20250514	{"input": 4140, "output": 131}	2026-04-14 03:07:56.400952+00	\N
a10db783-f05c-4e07-b553-f72df00d0188	c453b292-bdc2-458c-99c1-d3b22b5939f5	tool	\N	null	{"result": {"status": "needs_clarification", "questions": [{"key": "budget", "hint": "This helps me balance bulk purchases with fresh items", "question": "What's your weekly grocery budget?"}, {"key": "stores", "hint": "I'll plan around a primary bulk store and secondary store for fresh items", "question": "Which grocery stores do you prefer to shop at?"}, {"key": "prep_time", "hint": "I can plan for 2-3 hours of prep work", "question": "How much time do you have for meal prep on Sunday?"}, {"key": "cooking_skill", "hint": "Simple weeknight meals vs more involved recipes", "question": "What's your comfort level with cooking complexity?"}, {"key": "appliances", "hint": "Slow cooker, instant pot, grill, etc.", "question": "What cooking equipment do you have available?"}]}, "tool_use_id": "toolu_012aJf6jDumiWsTr9A2RQhCC"}	\N	null	2026-04-14 03:08:00.408265+00	\N
cfe1d126-9d57-4fb5-b221-6dde784ceacb	c453b292-bdc2-458c-99c1-d3b22b5939f5	assistant	I need a few more details to create the best meal plan for you:\n\n1. **Budget** - What's your weekly grocery budget? This helps me balance bulk purchases with fresh items.\n\n2. **Stores** - Which grocery stores do you prefer to shop at? I'll plan around a primary bulk store and secondary store for fresh items.\n\n3. **Prep time** - How much time do you have for meal prep on Sunday? I can plan for 2-3 hours of prep work.\n\n4. **Cooking complexity** - What's your comfort level with cooking complexity? Simple weeknight meals vs more involved recipes?\n\n5. **Equipment** - What cooking equipment do you have available? (slow cooker, instant pot, grill, etc.)\n\nThese details will help me create a meal plan that's both practical and delicious for your Italian-themed, healthier week!	null	null	claude-sonnet-4-20250514	{"input": 4489, "output": 192}	2026-04-14 03:08:03.87152+00	\N
b5392f21-9a9e-42af-8097-f7c9d1b75631	20b85b76-b542-4d69-8f36-f58aef5936c6	user	Help me add a task	null	null	\N	null	2026-04-15 03:15:37.681989+00	\N
d06a3c9a-54be-4993-a10d-150286306587	20b85b76-b542-4d69-8f36-f58aef5936c6	assistant	Hi River! I'd love to help you, but I'm not able to create or add new tasks to your family's system. That's something only the grown-ups in your family can do.\n\nIf you need a new task or chore added to your list, you'll want to talk to your mom or dad about it. They can help you set it up!\n\nIs there something else I can help you with instead? I can:\n- Show you what chores and tasks you have today\n- Check your weekly progress and allowance\n- Look at today's schedule or meals\n- Check the weather\n\nWhat would you like to know about?	null	null	claude-sonnet-4-20250514	{"input": 2330, "output": 139}	2026-04-15 03:15:41.690875+00	\N
68330391-8730-4b25-bf73-e46ef8d40076	a735dd1f-6290-431c-a3c9-5a56c4707547	user	Help me plan meals for next week	null	null	\N	null	2026-04-15 03:18:10.947434+00	\N
b3fa6a06-8c3b-4a99-b881-b09e19603bcd	a735dd1f-6290-431c-a3c9-5a56c4707547	assistant	I'd be happy to help you plan meals for next week! Before I generate a meal plan, let me ask a few questions to make sure it fits your family's needs:\n\n1. **Guests**: Will you have any guests joining for meals this week, or is it just the family?\n\n2. **Schedule conflicts**: Are there any nights when you'll have limited time to cook, or evenings when family members won't be home for dinner?\n\n3. **Pantry staples**: What do you already have on hand that we should use up? Any proteins in the freezer or ingredients you'd like to incorporate?\n\n4. **Preferences**: Any specific cuisines, comfort foods, or types of meals you're craving this week?\n\n5. **Dietary needs**: Any dietary restrictions or preferences I should keep in mind for family members who'll be eating these meals?\n\nOnce I have these details, I can create a customized meal plan with a Sunday prep schedule and organized grocery list!	null	null	claude-sonnet-4-20250514	{"input": 4282, "output": 213}	2026-04-15 03:18:17.123394+00	\N
b2c7bf11-a9e5-4c53-a107-0c1767023d09	b702a684-2e90-48ae-8f46-c36ec04a4d40	user	What does today look like?	null	null	\N	null	2026-04-15 17:36:15.187932+00	\N
643a9530-de9a-4a38-a49f-31ed1db7240d	b702a684-2e90-48ae-8f46-c36ec04a4d40	assistant	I'll get you a comprehensive overview of what's happening today for the family.	[{"id": "toolu_01TdsqzwkTiG52W83iYE8pA7", "name": "get_today_context", "input": {}}]	null	claude-sonnet-4-20250514	{"input": 4282, "output": 55}	2026-04-15 17:36:17.357814+00	\N
649480c0-ab25-4f58-ba98-3a582d39a853	b702a684-2e90-48ae-8f46-c36ec04a4d40	tool	\N	null	{"result": {"date": "2026-04-15", "meals_today": [], "tasks_today": [], "events_today": [], "family_members": [{"id": "2f25f0cc-6130-464f-be8a-76d863ca0952", "role": "adult", "birthdate": "1985-06-14", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Andrew", "updated_at": "2026-04-13T19:03:36.971426+00:00", "grade_level": null, "learning_notes": null, "personality_notes": null, "read_aloud_enabled": false}, {"id": "a21ec584-f2b6-4b2e-8ed6-1016f80f353c", "role": "adult", "birthdate": "1987-03-22", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Sally", "updated_at": "2026-04-13T19:03:36.971426+00:00", "grade_level": null, "learning_notes": null, "personality_notes": null, "read_aloud_enabled": false}, {"id": "6012f148-ae1c-40b4-838f-ef3bb7532e98", "role": "child", "birthdate": "2012-09-10", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Sadie", "updated_at": "2026-04-13T19:03:36.971426+00:00", "grade_level": null, "learning_notes": null, "personality_notes": null, "read_aloud_enabled": false}, {"id": "c61d88de-857e-42d3-8116-575f6fabf14f", "role": "child", "birthdate": "2015-11-28", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Townes", "updated_at": "2026-04-13T19:03:36.971426+00:00", "grade_level": null, "learning_notes": null, "personality_notes": null, "read_aloud_enabled": false}, {"id": "889e7a80-05ec-4140-9c1b-4f1e7d2eb355", "role": "child", "birthdate": "2008-01-01", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-12T15:45:13.408241+00:00", "first_name": "Tyler", "updated_at": "2026-04-14T16:44:39.094775+00:00", "grade_level": null, "learning_notes": null, "personality_notes": null, "read_aloud_enabled": false}, {"id": "b684226c-1217-44ca-84d0-3bf7c4ea4e82", "role": "adult", "birthdate": "1990-01-01", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-13T19:05:15.444158+00:00", "first_name": "Smoke", "updated_at": "2026-04-13T19:05:15.444158+00:00", "grade_level": null, "learning_notes": null, "personality_notes": null, "read_aloud_enabled": false}, {"id": "e4d39e09-9d32-4aeb-adad-5014fe3bf6be", "role": "child", "birthdate": "2017-07-30", "family_id": "fbe71860-a1a2-42b0-a0b5-df72017ced7c", "is_active": true, "last_name": "Roberts", "created_at": "2026-04-14T16:44:39.094775+00:00", "first_name": "River", "updated_at": "2026-04-14T16:51:07.935071+00:00", "grade_level": null, "learning_notes": null, "personality_notes": null, "read_aloud_enabled": false}], "unpaid_bills_count": 0}, "tool_use_id": "toolu_01TdsqzwkTiG52W83iYE8pA7"}	\N	null	2026-04-15 17:36:17.367416+00	\N
f2db03e8-dd11-4ef6-8f31-fe78efc0549e	b702a684-2e90-48ae-8f46-c36ec04a4d40	assistant	Here's what today (Tuesday, April 15th) looks like for the Roberts family:\n\n**Tasks**: No personal tasks scheduled for today\n\n**Calendar Events**: No events on the calendar today\n\n**Meals**: No specific meals planned for today\n\n**Bills**: All bills are current - no unpaid bills\n\nIt looks like you have a pretty open day! Is there anything specific you'd like to plan or add to today's schedule?	null	null	claude-sonnet-4-20250514	{"input": 5710, "output": 94}	2026-04-15 17:36:20.982614+00	\N
1b1e68d7-55d9-40ac-a611-a3b6846c8f4a	2a52f07a-e3e4-47a2-af34-3e10c32463f1	user	What do the kids still need to finish today?	null	null	\N	null	2026-04-15 18:59:06.168648+00	\N
1598837e-ece2-4373-8789-74272ecadeb9	2a52f07a-e3e4-47a2-af34-3e10c32463f1	assistant	I'll check what chores and routines the kids still need to complete today.	[{"id": "toolu_01CB8qDBDJ4vkSJKQ8uBEKA4", "name": "list_chores_or_routines", "input": {}}]	null	claude-sonnet-4-20250514	{"input": 4285, "output": 60}	2026-04-15 18:59:08.199781+00	\N
dacd6d4c-b6fc-43e1-b8e7-4bb3691f1822	2a52f07a-e3e4-47a2-af34-3e10c32463f1	tool	\N	null	{"result": {"routines": [], "chore_templates": [], "today_instances": []}, "tool_use_id": "toolu_01CB8qDBDJ4vkSJKQ8uBEKA4"}	\N	null	2026-04-15 18:59:08.206657+00	\N
d873a172-5dcc-4de4-a30c-45fea1ce6f85	2a52f07a-e3e4-47a2-af34-3e10c32463f1	assistant	It looks like there are no chore templates, routines, or task instances set up in the system yet, so there's nothing showing for the kids to complete today.\n\nWould you like me to also check if there are any personal tasks assigned to the children? Or if you'd like to set up some chores or routines for them, I can help with that too.	null	null	claude-sonnet-4-20250514	{"input": 4375, "output": 81}	2026-04-15 18:59:11.424727+00	\N
4e6868ed-359f-4fec-a499-1151bcff6136	32cfe212-d39f-4e99-9466-d3fb4a4b3e84	user	Reconnect YNAB	null	null	\N	null	2026-04-21 16:25:10.822132+00	null
968ea4e8-6e51-49eb-8ae9-084e12e63ccd	b2621276-a389-4135-bf0a-20300b5d4773	user	Add family member	null	null	\N	null	2026-04-21 16:25:12.084335+00	null
e5d725dc-157f-4354-b2d0-68a0ffb3cf35	b3dc1e96-5a1d-4bf0-b6ad-508c12ecfea3	user	Change chore schedule	null	null	\N	null	2026-04-21 16:25:13.404885+00	null
88da35f5-070a-4efa-89eb-17b8759afbcf	b3dc1e96-5a1d-4bf0-b6ad-508c12ecfea3	assistant	I'd be happy to help you change the chore schedule! Let me first check what the current chore setup looks like.	[{"id": "toolu_01LYa8nWsJHWe9YVSWCCzjMy", "name": "list_chores_or_routines", "input": {}}]	null	claude-sonnet-4-20250514	{"input": 143, "output": 69}	2026-04-21 16:25:15.462486+00	null
604397e0-1491-4a47-8b55-490ab746412c	b3dc1e96-5a1d-4bf0-b6ad-508c12ecfea3	tool	\N	null	{"result": {"routines": [], "chore_templates": [], "today_instances": []}, "tool_use_id": "toolu_01LYa8nWsJHWe9YVSWCCzjMy"}	\N	null	2026-04-21 16:25:15.478488+00	null
1a34a3fc-b70e-4a62-9575-0336379f84d1	b2621276-a389-4135-bf0a-20300b5d4773	assistant	I don't have a tool available to add new family members to the household. This type of core family configuration change would typically need to be done through your family management system's main settings or admin interface.\n\nYou might want to check:\n- Your family app's main settings or profile section\n- Any admin or household management features in your system\n- Contact your family management platform's support if you need help with adding a new family member\n\nIs there anything else I can help you with regarding your current family members' tasks, schedules, or activities?	null	null	claude-sonnet-4-20250514	{"input": 142, "output": 116}	2026-04-21 16:25:15.99071+00	null
0d92071b-4ee4-4044-8d73-16b04a09e9be	32cfe212-d39f-4e99-9466-d3fb4a4b3e84	assistant	I don't have access to tools for managing YNAB (You Need A Budget) connections or integrations. The family operations tools I have available are focused on tasks, calendar events, meal planning, grocery lists, chores, and similar household management functions.\n\nFor reconnecting YNAB, you'll likely need to:\n- Check your YNAB account settings for any connection or sync options\n- Look for integration settings in whatever app or service was previously connected to YNAB\n- Re-authenticate the connection if it expired\n- Contact YNAB support if you're having trouble with a specific integration\n\nIs there anything else I can help you with regarding your family's tasks, schedule, or meal planning?	null	null	claude-sonnet-4-20250514	{"input": 146, "output": 156}	2026-04-21 16:25:16.356786+00	null
f9f64a78-586d-4125-beab-1f619cb7dd91	32cfe212-d39f-4e99-9466-d3fb4a4b3e84	user	weather	null	null	\N	null	2026-04-21 16:25:19.286713+00	null
435f3d44-444e-4f5d-8512-bbdfb5e3ac6d	32cfe212-d39f-4e99-9466-d3fb4a4b3e84	assistant	\N	[{"id": "toolu_01Qf728pit5w1ztHfD3rtWw8", "name": "get_weather", "input": {}}]	null	claude-sonnet-4-20250514	{"input": 306, "output": 36}	2026-04-21 16:25:21.241143+00	null
e5e058ed-0d28-48fa-9fb5-1d23528815ff	32cfe212-d39f-4e99-9466-d3fb4a4b3e84	tool	\N	null	{"result": {"days": [{"date": "2026-04-21", "low_f": 56.0, "high_f": 63.7, "weather": "rain", "precip_probability_pct": 98}, {"date": "2026-04-22", "low_f": 61.4, "high_f": 76.5, "weather": "light rain", "precip_probability_pct": 7}, {"date": "2026-04-23", "low_f": 65.8, "high_f": 79.3, "weather": "drizzle", "precip_probability_pct": 6}], "units": "fahrenheit", "location": "Fort Worth, Texas, US"}, "tool_use_id": "toolu_01Qf728pit5w1ztHfD3rtWw8"}	\N	null	2026-04-21 16:25:22.757876+00	null
0134338d-26cf-4af7-8885-9ddccf568123	32cfe212-d39f-4e99-9466-d3fb4a4b3e84	assistant	Here's the weather forecast for Fort Worth:\n\n**Today (Monday 4/21)**: Rain with a high of 64°F and low of 56°F. 98% chance of precipitation - definitely a rainy day!\n\n**Tomorrow (Tuesday 4/22)**: Light rain possible, warming up to 77°F with a low of 61°F. Only 7% chance of rain.\n\n**Wednesday (4/23)**: Possible drizzle, high of 79°F and low of 66°F. Just 6% chance of precipitation.\n\nLooks like today is the main rainy day, then it clears up and warms up nicely for the rest of the week!	null	null	claude-sonnet-4-20250514	{"input": 530, "output": 159}	2026-04-21 16:25:26.68943+00	null
43b05d98-559d-45cc-aacc-1e178826ec2e	b3dc1e96-5a1d-4bf0-b6ad-508c12ecfea3	assistant	It looks like there aren't any chore templates, routines, or scheduled chores currently set up in the system. \n\nTo help you create or modify a chore schedule, I'd need to understand what you're looking for:\n\n1. Are you wanting to create a new chore schedule from scratch?\n2. Do you have specific chores in mind for each child (Sadie, Townes, Tyler, River)?\n3. What frequency are you thinking - daily, weekly, or something else?\n4. Are there particular days of the week you'd prefer certain chores to be done?\n\nThe current system I have access to can help manage personal tasks and track completion, but setting up recurring chore templates and schedules might require additional configuration. Let me know what specific changes you'd like to make and I can help you work toward that goal!	null	null	claude-sonnet-4-20250514	{"input": 242, "output": 185}	2026-04-21 16:25:21.12217+00	null
4febe9a1-8625-4701-b547-7f4ee0cc4697	6b303eaa-d128-4506-a56d-848f6b14fb64	user	Check next week's meals	null	null	\N	null	2026-04-21 17:26:07.511818+00	null
bdddefab-fe5e-48da-b55e-553686a354d4	6b303eaa-d128-4506-a56d-848f6b14fb64	assistant	\N	[{"id": "toolu_01AvreYf5rMWsgoYJW1PBTXE", "name": "get_current_weekly_meal_plan", "input": {}}]	null	claude-sonnet-4-20250514	{"input": 144, "output": 42}	2026-04-21 17:26:09.665788+00	null
32c9ca38-879a-436d-802c-8612029b6ed9	6b303eaa-d128-4506-a56d-848f6b14fb64	tool	\N	null	{"result": {"plan": null}, "tool_use_id": "toolu_01AvreYf5rMWsgoYJW1PBTXE"}	\N	null	2026-04-21 17:26:09.675381+00	null
ce53fd02-01ca-4e65-b168-ac3780d75bfc	6b303eaa-d128-4506-a56d-848f6b14fb64	assistant	No meal plan exists for next week yet. Want me to generate one for you?	null	null	claude-sonnet-4-20250514	{"input": 203, "output": 20}	2026-04-21 17:26:11.177348+00	null
c7462622-0293-46af-8334-0727eda8ebfa	d1efb62a-6685-4f1c-b05e-ce0085e29969	user	Who hasn't done chores?	null	null	\N	null	2026-04-21 22:58:38.746809+00	null
04e5b139-2f52-45fd-86e9-aa7e88c986d0	d1efb62a-6685-4f1c-b05e-ce0085e29969	assistant	\N	[{"id": "toolu_01UAfCMGdj21vfHJ5LoySUVM", "name": "list_chores_or_routines", "input": {}}]	null	claude-sonnet-4-20250514	{"input": 146, "output": 42}	2026-04-21 22:58:40.648219+00	null
6edb83eb-818f-47b2-82b4-b9344dcc3bc6	d1efb62a-6685-4f1c-b05e-ce0085e29969	tool	\N	null	{"result": {"routines": [], "chore_templates": [], "today_instances": []}, "tool_use_id": "toolu_01UAfCMGdj21vfHJ5LoySUVM"}	\N	null	2026-04-21 22:58:40.666145+00	null
61cf501a-a50b-4c5d-9c1f-f5ee13b76f7b	d1efb62a-6685-4f1c-b05e-ce0085e29969	assistant	No chore or routine instances are scheduled for today. Either nothing was set up for Tuesday, or everything's already been completed.\n\nWant me to check what's coming up tomorrow or look at the kids' personal tasks instead?	null	null	claude-sonnet-4-20250514	{"input": 219, "output": 49}	2026-04-21 22:58:43.163594+00	null
f82cae27-d039-487d-a006-81bee8048230	f217c92d-3c95-4688-8122-26c9bc711154	user	Weather	null	null	\N	null	2026-04-21 22:58:43.351321+00	null
c8d72e1e-4f9f-45f7-923f-d4744aef8ea8	f217c92d-3c95-4688-8122-26c9bc711154	assistant	\N	[{"id": "toolu_01MBkBY9hF2CLztf6MTtMUqg", "name": "get_weather", "input": {}}]	null	claude-sonnet-4-20250514	{"input": 140, "output": 36}	2026-04-21 22:58:44.943521+00	null
1993a540-d53f-4e08-9cef-81232ab5bb74	f217c92d-3c95-4688-8122-26c9bc711154	tool	\N	null	{"result": {"days": [{"date": "2026-04-21", "low_f": 56.0, "high_f": 61.6, "weather": "rain", "precip_probability_pct": 98}, {"date": "2026-04-22", "low_f": 60.7, "high_f": 74.4, "weather": "light drizzle", "precip_probability_pct": 14}, {"date": "2026-04-23", "low_f": 65.5, "high_f": 82.3, "weather": "drizzle", "precip_probability_pct": 5}], "units": "fahrenheit", "location": "Fort Worth, Texas, US"}, "tool_use_id": "toolu_01MBkBY9hF2CLztf6MTtMUqg"}	\N	null	2026-04-21 22:58:46.375721+00	null
96f8b74b-27e6-4063-97b6-84226f4614c3	f217c92d-3c95-4688-8122-26c9bc711154	assistant	Rain tonight (98% chance), then clearing up. Tomorrow hits 74°F with just light drizzle (14% chance). Wednesday looks nice at 82°F and mostly dry.	null	null	claude-sonnet-4-20250514	{"input": 366, "output": 43}	2026-04-21 22:58:48.488559+00	null
\.


--
-- Data for Name: ai_tool_audit; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.ai_tool_audit (id, family_id, actor_member_id, conversation_id, tool_name, arguments, result_summary, target_entity, target_id, status, error_message, duration_ms, created_at) FROM stdin;
876b029d-35c2-411f-963f-adc60d90f6db	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	d1bf96c3-7e5e-4ba5-9f73-de865b96a264	get_today_context	{}	{'date': '2026-04-13', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Whitfield', 'birthdate': '1985-06-14', 'created_at': '2026-04-12T15:45:13.408241+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'first_name': 'Andrew', 'role': 'adult', 'is_active': True, 'updated_at': '2026-04-12T15:45:13.408241+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Whitfield', 'birthdate': '1987-03-22', 'created_at': '2026-04-12T15:45:13.40	\N	\N	success	\N	14	2026-04-13 19:00:12.738351+00
557b8002-4eb8-4a01-8dd3-6e823ea4c517	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	06c0d6aa-759a-4e54-bf98-6f86beabb9d9	get_today_context	{}	{'date': '2026-04-13', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'created_at': '2026-04-12T15:45:13.408241+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'first_name': 'Andrew', 'role': 'adult', 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Roberts', 'birthdate': '1987-03-22', 'created_at': '2026-04-12T15:45:13.408241	\N	\N	success	\N	7	2026-04-13 19:06:01.15128+00
58456680-f795-49f8-929c-127623947ed8	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	d6cf512d-ae10-44f8-86db-a5b9b91b518d	get_today_context	{}	{'date': '2026-04-13', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'created_at': '2026-04-12T15:45:13.408241+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'first_name': 'Andrew', 'role': 'adult', 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Roberts', 'birthdate': '1987-03-22', 'created_at': '2026-04-12T15:45:13.408241	\N	\N	success	\N	6	2026-04-13 19:06:59.398476+00
18c37152-1969-4d25-b003-4d325f50f3d2	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	392a0b26-e24a-4214-b44c-c545f89cb8c8	get_weather	{"days": 1, "location": "76126"}	{'location': 'Fort Worth, Texas, US', 'units': 'fahrenheit', 'days': [{'date': '2026-04-13', 'high_f': 85.8, 'low_f': 69.3, 'precip_probability_pct': 5, 'weather': 'cloudy'}]}	\N	\N	success	\N	1668	2026-04-13 19:52:58.98657+00
6c1a29dd-92af-4529-9910-b1053646919f	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	9f5faa91-c1ca-4c6b-82ba-09ecd79e5a5e	get_weather	{}	{'location': 'Fort Worth, Texas, US', 'units': 'fahrenheit', 'days': [{'date': '2026-04-13', 'high_f': 85.8, 'low_f': 69.3, 'precip_probability_pct': 6, 'weather': 'cloudy'}, {'date': '2026-04-14', 'high_f': 77.7, 'low_f': 70.5, 'precip_probability_pct': 9, 'weather': 'cloudy'}, {'date': '2026-04-15', 'high_f': 78.4, 'low_f': 67.8, 'precip_probability_pct': 65, 'weather': 'drizzle'}]}	\N	\N	success	\N	1667	2026-04-13 20:06:19.441399+00
87deb14b-9309-4a5e-aabd-9dc203f1d070	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	8dae6089-0afe-40a9-825d-850a12ad164d	get_weather	{"days": 1, "location": "76126"}	{'location': 'Fort Worth, Texas, US', 'units': 'fahrenheit', 'days': [{'date': '2026-04-13', 'high_f': 85.6, 'low_f': 69.3, 'precip_probability_pct': 6, 'weather': 'cloudy'}]}	\N	\N	success	\N	1784	2026-04-13 20:30:23.055126+00
fc4885ae-5fe0-4f50-8ae8-6e0428eba6e0	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	e7cbde56-edd1-4490-94cd-c6695a54e6b4	moderation	{"role": "adult", "surface": "child", "category": "drugs_or_alcohol"}	I can't help with that. Please talk to a parent if you have questions about this.	\N	\N	moderation_blocked	drugs_or_alcohol	\N	2026-04-13 20:31:31.426446+00
a201b76c-0c1d-4661-acaf-293f3546a638	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	a3bed0ab-aabb-4cb2-819b-48bf6421fa20	get_weather	{"days": 7}	{'location': 'Fort Worth, Texas, US', 'units': 'fahrenheit', 'days': [{'date': '2026-04-13', 'high_f': 85.6, 'low_f': 69.3, 'precip_probability_pct': 6, 'weather': 'cloudy'}, {'date': '2026-04-14', 'high_f': 77.7, 'low_f': 70.3, 'precip_probability_pct': 9, 'weather': 'cloudy'}, {'date': '2026-04-15', 'high_f': 78.4, 'low_f': 67.8, 'precip_probability_pct': 65, 'weather': 'drizzle'}, {'date': '2026-04-16', 'high_f': 86.8, 'low_f': 66.9, 'precip_probability_pct': 37, 'weather': 'light drizzle'}, 	\N	\N	success	\N	1675	2026-04-13 21:21:14.584118+00
c338c832-c56e-4092-b772-7bc8a1ee2b46	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	\N	get_today_context	{}	{'date': '2026-04-13', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'first_name': 'Andrew', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Robe	\N	\N	success	\N	1324	2026-04-13 21:48:01.403056+00
3d692e2f-e848-42e8-ac8e-3b582ec68ab4	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	\N	get_today_context	{}	{'date': '2026-04-13', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'first_name': 'Andrew', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Robe	\N	\N	success	\N	1332	2026-04-13 21:48:01.403056+00
73209b20-0211-490f-a3ba-b9958543a0b4	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	\N	get_today_context	{}	{'date': '2026-04-13', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'first_name': 'Andrew', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Robe	\N	\N	success	\N	1316	2026-04-13 21:48:01.403056+00
1b7b0113-85fd-4b08-889c-c59260a44105	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	d7c4af37-0f37-43c9-bf6a-4c8b3b0b005d	get_today_context	{}	{'date': '2026-04-13', 'family_members': [{'first_name': 'Andrew', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00'}, {'first_name': 'Sally', 'role': 'adult', 'grade_level': None, 'read_alou	\N	\N	success	\N	13	2026-04-13 22:06:17.158803+00
812c6b34-41c2-47d5-b4b0-0c502a777f29	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	e615835c-0cea-4443-b71c-c6156eba21af	get_weather	{"days": 1}	{'location': 'Fort Worth, Texas, US', 'units': 'fahrenheit', 'days': [{'date': '2026-04-13', 'high_f': 85.2, 'low_f': 69.3, 'precip_probability_pct': 5, 'weather': 'thunderstorm'}]}	\N	\N	success	\N	1669	2026-04-13 22:12:34.529112+00
2fc03737-99d1-4259-a214-fecb9e2a2c72	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	02906da7-9e82-4ffd-ae49-6c65b5eb3be3	get_weather	{"days": 1}	{'location': 'Fort Worth, Texas, US', 'units': 'fahrenheit', 'days': [{'date': '2026-04-13', 'high_f': 85.2, 'low_f': 69.3, 'precip_probability_pct': 5, 'weather': 'thunderstorm'}]}	\N	\N	success	\N	1655	2026-04-13 22:17:27.528296+00
32e73c05-eec4-4a02-b8b9-c369645b4cd6	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	28ec4906-b2bf-4698-aa9a-e83228a0f589	get_today_context	{}	{'date': '2026-04-13', 'family_members': [{'first_name': 'Andrew', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00', 'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00'}, {'first_name': 'Sally', 'role': 'adult', 'grade_level': None, 'read_alou	\N	\N	success	\N	8	2026-04-13 22:19:35.41912+00
74c75f8d-bbe7-45c3-a002-6470914acba5	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	0294595b-9758-46f7-b527-f99d5cd9ec9d	add_grocery_item	{"title": "bananas"}	{'created': {'preferred_store': None, 'purchased_at': None, 'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'notes': None, 'purchased_by': None, 'added_by_member_id': 'b684226c-1217-44ca-84d0-3bf7c4ea4e82', 'source': 'manual', 'approval_status': 'active', 'linked_meal_ref': None, 'updated_at': '2026-04-13T22:41:08.545736+00:00', 'purchase_request_id': None, 'weekly_plan_id': None, 'title': 'bananas', 'quantity': None, 'created_at': '2026-04-13T22:41:08.545736+00:00', 'id': 'c40526c8-4b0e-4d	\N	\N	success	\N	9	2026-04-13 22:41:10.283614+00
4fb8e43f-fc9c-4f6f-85ec-e9974578a838	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	c453b292-bdc2-458c-99c1-d3b22b5939f5	generate_weekly_meal_plan	{"constraints": {"cuisines": ["Italian"], "theme_weeks": true, "health_focus": "healthier options", "italian_nights": 2}, "week_start_date": "2026-04-21"}	\N	\N	\N	error	400: week_start_date must be a Monday	0	2026-04-14 03:07:50.192999+00
00df27f6-2edc-4d59-8cd8-5c2933936aa0	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	c453b292-bdc2-458c-99c1-d3b22b5939f5	generate_weekly_meal_plan	{"constraints": {"cuisines": ["Italian"], "theme_weeks": true, "health_focus": "healthier options", "italian_nights": 2}, "week_start_date": "2026-04-20"}	{'status': 'needs_clarification', 'questions': [{'key': 'budget', 'question': "What's your weekly grocery budget?", 'hint': 'This helps me balance bulk purchases with fresh items'}, {'key': 'stores', 'question': 'Which grocery stores do you prefer to shop at?', 'hint': "I'll plan around a primary bulk store and secondary store for fresh items"}, {'key': 'prep_time', 'question': 'How much time do you have for meal prep on Sunday?', 'hint': 'I can plan for 2-3 hours of prep work'}, {'key': 'cookin	\N	\N	success	\N	4002	2026-04-14 03:07:50.192999+00
2fd30a43-e56a-4017-b9aa-2a73799898c4	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	\N	get_today_context	{}	{'date': '2026-04-14', 'family_members': [{'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'first_name': 'Andrew', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'id': 'a21ec584-f2b6-4b2e-8ed6-1016f80f353c', 'family_id': 'fbe71860-a1	\N	\N	success	\N	14	2026-04-14 11:00:26.086591+00
c4bc3088-6c36-40e6-9810-3182fa70a015	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	\N	get_today_context	{}	{'date': '2026-04-14', 'family_members': [{'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'first_name': 'Andrew', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'id': 'a21ec584-f2b6-4b2e-8ed6-1016f80f353c', 'family_id': 'fbe71860-a1	\N	\N	success	\N	7	2026-04-14 11:00:26.086591+00
861f0049-e543-494d-a6e6-260e08c3cb8e	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	\N	get_today_context	{}	{'date': '2026-04-14', 'family_members': [{'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'first_name': 'Andrew', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'id': 'a21ec584-f2b6-4b2e-8ed6-1016f80f353c', 'family_id': 'fbe71860-a1	\N	\N	success	\N	7	2026-04-14 11:00:26.086591+00
023a7c02-fef4-49b0-9c5a-d645fbc1c009	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	\N	get_today_context	{}	{'date': '2026-04-15', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'first_name': 'Andrew', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df7201	\N	\N	success	\N	12	2026-04-15 11:04:30.608424+00
b4571a95-d1fe-4cc7-841d-d1e8d340298d	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	\N	get_today_context	{}	{'date': '2026-04-15', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'first_name': 'Andrew', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df7201	\N	\N	success	\N	7	2026-04-15 11:04:30.608424+00
66f44ecb-ec57-44ac-a8f4-f1b0ed56a33b	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	\N	get_today_context	{}	{'date': '2026-04-15', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'first_name': 'Andrew', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df7201	\N	\N	success	\N	10	2026-04-15 11:04:30.608424+00
33d11d9a-8c70-4bc5-ba4f-e927a6ba8bbd	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	b702a684-2e90-48ae-8f46-c36ec04a4d40	get_today_context	{}	{'date': '2026-04-15', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'first_name': 'Andrew', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df7201	\N	\N	success	\N	6	2026-04-15 17:36:15.17512+00
68991056-fb52-4276-9947-2a3622b52375	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	2a52f07a-e3e4-47a2-af34-3e10c32463f1	list_chores_or_routines	{}	{'chore_templates': [], 'routines': [], 'today_instances': []}	\N	\N	success	\N	3	2026-04-15 18:59:06.157672+00
6e037269-da4c-40bf-b97f-2c2eb718b1e6	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	\N	get_today_context	{}	{'date': '2026-04-16', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'first_name': 'Andrew', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df7201	\N	\N	success	\N	15	2026-04-16 11:00:32.270633+00
1ab8f40f-0616-4803-bb8a-9c861027821b	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	\N	get_today_context	{}	{'date': '2026-04-16', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'first_name': 'Andrew', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df7201	\N	\N	success	\N	7	2026-04-16 11:00:32.270633+00
4c7f1ad2-2410-4c10-8cb0-40bef56a747b	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	\N	get_today_context	{}	{'date': '2026-04-16', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'first_name': 'Andrew', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df7201	\N	\N	success	\N	5	2026-04-16 11:00:32.270633+00
3afa5277-7968-45a1-ac62-a5c69f87ef15	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	\N	get_today_context	{}	{'date': '2026-04-17', 'family_members': [{'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'first_name': 'Andrew', 'role': 'adult', 'grade_level': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'id': 'a21ec584-f2b6-4b2e-8ed6-1016f80f353c'	\N	\N	success	\N	13	2026-04-17 11:02:45.228148+00
713720c7-b1cd-46a7-afcb-0b9ee0306f50	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	\N	get_today_context	{}	{'date': '2026-04-17', 'family_members': [{'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'first_name': 'Andrew', 'role': 'adult', 'grade_level': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'id': 'a21ec584-f2b6-4b2e-8ed6-1016f80f353c'	\N	\N	success	\N	12	2026-04-17 11:02:45.228148+00
4bec8b06-e9de-4f98-a14b-771d7ba35727	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	\N	get_today_context	{}	{'date': '2026-04-17', 'family_members': [{'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'first_name': 'Andrew', 'role': 'adult', 'grade_level': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'id': 'a21ec584-f2b6-4b2e-8ed6-1016f80f353c'	\N	\N	success	\N	6	2026-04-17 11:02:45.228148+00
cc11ead4-745b-4b1f-bab7-2401e74363a8	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	\N	get_today_context	{}	{'date': '2026-04-18', 'family_members': [{'first_name': 'Andrew', 'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00', 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'personality_notes': None, 'is_active': True}, {'first_name': 'Sally', 'family_id': 'fbe7186	\N	\N	success	\N	18	2026-04-18 11:01:26.968221+00
1a6fbcc0-ea72-46cb-97dc-854b831435dd	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	\N	get_today_context	{}	{'date': '2026-04-18', 'family_members': [{'first_name': 'Andrew', 'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00', 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'personality_notes': None, 'is_active': True}, {'first_name': 'Sally', 'family_id': 'fbe7186	\N	\N	success	\N	5	2026-04-18 11:01:26.968221+00
e0384295-1640-46b5-a1cc-d987dabb816d	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	\N	get_today_context	{}	{'date': '2026-04-18', 'family_members': [{'first_name': 'Andrew', 'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00', 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'personality_notes': None, 'is_active': True}, {'first_name': 'Sally', 'family_id': 'fbe7186	\N	\N	success	\N	6	2026-04-18 11:01:26.968221+00
2148bedf-91a5-4e57-b10a-3311fba47337	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	\N	get_today_context	{}	{'date': '2026-04-19', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'first_name': 'Andrew', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df7201	\N	\N	success	\N	15	2026-04-19 11:01:42.471072+00
02893220-6ca6-425e-ae6e-c35f54e04d66	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	\N	get_today_context	{}	{'date': '2026-04-19', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'first_name': 'Andrew', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df7201	\N	\N	success	\N	5	2026-04-19 11:01:42.471072+00
8d373ca0-8a29-4889-a43a-1ed193bcf0d4	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	\N	get_today_context	{}	{'date': '2026-04-19', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'first_name': 'Andrew', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df7201	\N	\N	success	\N	5	2026-04-19 11:01:42.471072+00
98480af8-65be-4567-a900-02d56a1957b5	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	\N	get_today_context	{}	{'date': '2026-04-20', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'first_name': 'Andrew', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df7201	\N	\N	success	\N	7	2026-04-20 11:01:42.471712+00
ffd4d37a-c7bf-4646-8ba4-6c542284b7a5	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	\N	get_today_context	{}	{'date': '2026-04-20', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'first_name': 'Andrew', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df7201	\N	\N	success	\N	6	2026-04-20 11:01:42.471712+00
2035c318-9407-4349-97c7-f393f4434131	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	\N	get_today_context	{}	{'date': '2026-04-20', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'first_name': 'Andrew', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df7201	\N	\N	success	\N	7	2026-04-20 11:01:42.471712+00
e577433f-1df9-4e66-b59e-6fc54f45a4c7	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	\N	get_today_context	{}	{'date': '2026-04-21', 'family_members': [{'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'personality_notes': None, 'is_active': True, 'created_at': '2026-04-12T15:45:13.408241+00:00', 'first_name': 'Andrew', 'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'read_aloud_enabled': False, 'updated_at': '2026-04-13T19:03:36.971426+00:00'}, {'id': 'a21ec584-f2b6-4b2e-8ed6-1016f80f353c'	\N	\N	success	\N	14	2026-04-21 11:02:29.022847+00
b0041543-e3bf-4075-a807-e4246989e14e	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	\N	get_today_context	{}	{'date': '2026-04-21', 'family_members': [{'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'personality_notes': None, 'is_active': True, 'created_at': '2026-04-12T15:45:13.408241+00:00', 'first_name': 'Andrew', 'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'read_aloud_enabled': False, 'updated_at': '2026-04-13T19:03:36.971426+00:00'}, {'id': 'a21ec584-f2b6-4b2e-8ed6-1016f80f353c'	\N	\N	success	\N	7	2026-04-21 11:02:29.022847+00
fae39429-29be-4b84-8825-03cbf0a59e68	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	\N	get_today_context	{}	{'date': '2026-04-21', 'family_members': [{'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'personality_notes': None, 'is_active': True, 'created_at': '2026-04-12T15:45:13.408241+00:00', 'first_name': 'Andrew', 'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'read_aloud_enabled': False, 'updated_at': '2026-04-13T19:03:36.971426+00:00'}, {'id': 'a21ec584-f2b6-4b2e-8ed6-1016f80f353c'	\N	\N	success	\N	5	2026-04-21 11:02:29.022847+00
3cb151fc-d20c-4170-ab38-71d1205d078e	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	b3dc1e96-5a1d-4bf0-b6ad-508c12ecfea3	list_chores_or_routines	{}	{'chore_templates': [], 'routines': [], 'today_instances': []}	\N	\N	success	\N	9	2026-04-21 16:25:13.384203+00
b997f04a-8ace-4cf0-a0e1-0db9e48a6702	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	32cfe212-d39f-4e99-9466-d3fb4a4b3e84	get_weather	{}	{'location': 'Fort Worth, Texas, US', 'units': 'fahrenheit', 'days': [{'date': '2026-04-21', 'high_f': 63.7, 'low_f': 56.0, 'precip_probability_pct': 98, 'weather': 'rain'}, {'date': '2026-04-22', 'high_f': 76.5, 'low_f': 61.4, 'precip_probability_pct': 7, 'weather': 'light rain'}, {'date': '2026-04-23', 'high_f': 79.3, 'low_f': 65.8, 'precip_probability_pct': 6, 'weather': 'drizzle'}]}	\N	\N	success	\N	1510	2026-04-21 16:25:19.272835+00
7f22b710-3780-4b4c-9937-cf579d10c189	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	6b303eaa-d128-4506-a56d-848f6b14fb64	get_current_weekly_meal_plan	{}	{'plan': None}	\N	\N	success	\N	2	2026-04-21 17:26:07.486335+00
ca50c01a-7db9-4943-996b-ee27ed99913e	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	d1efb62a-6685-4f1c-b05e-ce0085e29969	list_chores_or_routines	{}	{'chore_templates': [], 'routines': [], 'today_instances': []}	\N	\N	success	\N	9	2026-04-21 22:58:38.722197+00
fed2a0e3-ba4a-4c50-b667-30da8398e0fb	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	f217c92d-3c95-4688-8122-26c9bc711154	get_weather	{}	{'location': 'Fort Worth, Texas, US', 'units': 'fahrenheit', 'days': [{'date': '2026-04-21', 'high_f': 61.6, 'low_f': 56.0, 'precip_probability_pct': 98, 'weather': 'rain'}, {'date': '2026-04-22', 'high_f': 74.4, 'low_f': 60.7, 'precip_probability_pct': 14, 'weather': 'light drizzle'}, {'date': '2026-04-23', 'high_f': 82.3, 'low_f': 65.5, 'precip_probability_pct': 5, 'weather': 'drizzle'}]}	\N	\N	success	\N	1426	2026-04-21 22:58:43.313134+00
235e0c14-8039-4a50-b75a-97d707958c43	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	\N	get_today_context	{}	{'date': '2026-04-22', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'first_name': 'Andrew', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df7201	\N	\N	success	\N	21	2026-04-22 11:02:34.110706+00
5b6d2420-dae6-4d9a-a4e7-80ac176cbcc8	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	\N	get_today_context	{}	{'date': '2026-04-22', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'first_name': 'Andrew', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df7201	\N	\N	success	\N	10	2026-04-22 11:02:34.110706+00
1beb1ffc-4a9d-4305-8e58-bb54462b7ae6	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	\N	get_today_context	{}	{'date': '2026-04-22', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'first_name': 'Andrew', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df7201	\N	\N	success	\N	8	2026-04-22 11:02:34.110706+00
7423d36b-c659-4c00-9ed0-33f67fe4344e	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	\N	get_today_context	{}	{'date': '2026-04-23', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'first_name': 'Andrew', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df7201	\N	\N	success	\N	30	2026-04-23 11:00:30.011068+00
ebb205c6-24c9-4c55-824b-24e9e411a218	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	\N	get_today_context	{}	{'date': '2026-04-23', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'first_name': 'Andrew', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df7201	\N	\N	success	\N	9	2026-04-23 11:00:30.011068+00
1220f173-99f7-4c26-9cc3-a5f7a7eadb55	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	\N	get_today_context	{}	{'date': '2026-04-23', 'family_members': [{'family_id': 'fbe71860-a1a2-42b0-a0b5-df72017ced7c', 'first_name': 'Andrew', 'last_name': 'Roberts', 'birthdate': '1985-06-14', 'learning_notes': None, 'personality_notes': None, 'is_active': True, 'updated_at': '2026-04-13T19:03:36.971426+00:00', 'id': '2f25f0cc-6130-464f-be8a-76d863ca0952', 'role': 'adult', 'grade_level': None, 'read_aloud_enabled': False, 'created_at': '2026-04-12T15:45:13.408241+00:00'}, {'family_id': 'fbe71860-a1a2-42b0-a0b5-df7201	\N	\N	success	\N	9	2026-04-23 11:00:30.011068+00
\.


--
-- Data for Name: allowance_ledger; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.allowance_ledger (id, family_id, family_member_id, entry_type, amount_cents, week_start, note, created_at) FROM stdin;
\.


--
-- Data for Name: bills; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.bills (id, family_id, created_by, title, description, notes, amount_cents, due_date, status, paid_at, source, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: chore_templates; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.chore_templates (id, family_id, name, description, recurrence, due_time, assignment_type, assignment_rule, is_active, created_at, updated_at, included, not_included, done_means_done, supplies, photo_example_url, estimated_duration_minutes, consequence_on_miss) FROM stdin;
\.


--
-- Data for Name: connector_configs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.connector_configs (id, family_id, family_member_id, connector_name, auth_token, refresh_token, config, scope, sync_direction, authority_level, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: connector_mappings; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.connector_mappings (id, connector_name, internal_table, internal_id, external_id, metadata, created_at, external_object_type, family_id, user_account_id) FROM stdin;
\.


--
-- Data for Name: daily_wins; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.daily_wins (id, family_id, family_member_id, win_date, is_win, task_count, completed_count, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: dietary_preferences; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.dietary_preferences (id, family_member_id, label, kind, notes, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: event_attendees; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.event_attendees (id, event_id, family_member_id, response_status, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: events; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.events (id, family_id, created_by, title, description, location, starts_at, ends_at, all_day, recurrence_rule, recurrence_parent_id, recurrence_instance_date, source, is_hearth_visible, task_instance_id, is_cancelled, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: families; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.families (id, name, timezone, created_at, updated_at, allow_general_chat, allow_homework_help, home_location) FROM stdin;
fbe71860-a1a2-42b0-a0b5-df72017ced7c	Roberts	America/Chicago	2026-04-12 15:45:13.408241+00	2026-04-14 03:05:25.547309+00	t	t	76126
\.


--
-- Data for Name: family_members; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.family_members (id, family_id, first_name, last_name, role, birthdate, is_active, created_at, updated_at, grade_level, learning_notes, read_aloud_enabled, personality_notes) FROM stdin;
2f25f0cc-6130-464f-be8a-76d863ca0952	fbe71860-a1a2-42b0-a0b5-df72017ced7c	Andrew	Roberts	adult	1985-06-14	t	2026-04-12 15:45:13.408241+00	2026-04-13 19:03:36.971426+00	\N	\N	f	\N
a21ec584-f2b6-4b2e-8ed6-1016f80f353c	fbe71860-a1a2-42b0-a0b5-df72017ced7c	Sally	Roberts	adult	1987-03-22	t	2026-04-12 15:45:13.408241+00	2026-04-13 19:03:36.971426+00	\N	\N	f	\N
6012f148-ae1c-40b4-838f-ef3bb7532e98	fbe71860-a1a2-42b0-a0b5-df72017ced7c	Sadie	Roberts	child	2012-09-10	t	2026-04-12 15:45:13.408241+00	2026-04-13 19:03:36.971426+00	\N	\N	f	\N
c61d88de-857e-42d3-8116-575f6fabf14f	fbe71860-a1a2-42b0-a0b5-df72017ced7c	Townes	Roberts	child	2015-11-28	t	2026-04-12 15:45:13.408241+00	2026-04-13 19:03:36.971426+00	\N	\N	f	\N
b684226c-1217-44ca-84d0-3bf7c4ea4e82	fbe71860-a1a2-42b0-a0b5-df72017ced7c	Smoke	Roberts	adult	1990-01-01	t	2026-04-13 19:05:15.444158+00	2026-04-13 19:05:15.444158+00	\N	\N	f	\N
889e7a80-05ec-4140-9c1b-4f1e7d2eb355	fbe71860-a1a2-42b0-a0b5-df72017ced7c	Tyler	Roberts	child	2008-01-01	t	2026-04-12 15:45:13.408241+00	2026-04-14 16:44:39.094775+00	\N	\N	f	\N
e4d39e09-9d32-4aeb-adad-5014fe3bf6be	fbe71860-a1a2-42b0-a0b5-df72017ced7c	River	Roberts	child	2017-07-30	t	2026-04-14 16:44:39.094775+00	2026-04-14 16:51:07.935071+00	\N	\N	f	\N
669c229c-96b0-44b7-940d-d026789b7c58	fbe71860-a1a2-42b0-a0b5-df72017ced7c	Smoke-Child	Roberts	child	2015-01-01	t	2026-04-22 22:22:26.652607+00	2026-04-22 22:22:26.652607+00	\N	\N	f	\N
\.


--
-- Data for Name: family_memories; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.family_memories (id, family_id, member_id, memory_type, scope, content, tags, source_kind, source_conversation_id, created_by_kind, status, confidence, last_confirmed_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: grocery_items; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.grocery_items (id, family_id, added_by_member_id, title, quantity, unit, category, preferred_store, notes, source, approval_status, purchase_request_id, is_purchased, purchased_at, purchased_by, created_at, updated_at, weekly_plan_id, linked_meal_ref) FROM stdin;
09141c44-5ccc-4016-9f19-c56275590f29	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	Salt	\N	\N	\N	\N	\N	manual	active	\N	t	2026-04-12 19:17:37.713071+00	2f25f0cc-6130-464f-be8a-76d863ca0952	2026-04-12 19:17:33.163626+00	2026-04-12 19:17:37.706505+00	\N	\N
c40526c8-4b0e-4dca-8106-9389d77278f7	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	bananas	\N	\N	\N	\N	\N	manual	active	\N	f	\N	\N	2026-04-13 22:41:08.545736+00	2026-04-13 22:41:08.545736+00	\N	\N
\.


--
-- Data for Name: health_summaries; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.health_summaries (id, family_id, family_member_id, summary_date, steps, active_minutes, resting_heart_rate, sleep_minutes, weight_grams, source, notes, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: meal_plans; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.meal_plans (id, family_id, created_by, week_start, notes, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: meal_reviews; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.meal_reviews (id, family_id, weekly_plan_id, reviewed_by_member_id, linked_meal_ref, meal_title, rating_overall, kid_acceptance, effort, cleanup, leftovers, repeat_decision, notes, created_at) FROM stdin;
\.


--
-- Data for Name: meals; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.meals (id, family_id, meal_plan_id, created_by, meal_date, meal_type, title, description, notes, created_at, updated_at, is_base_cook, base_cook_yield_servings, base_cook_keeps_days, storage_notes) FROM stdin;
\.


--
-- Data for Name: member_config; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.member_config (id, family_member_id, key, value, updated_by, created_at, updated_at) FROM stdin;
72c72b25-398f-4ea7-9781-c622f6edc404	2f25f0cc-6130-464f-be8a-76d863ca0952	affirmations.preferences	{"enabled": true, "excluded_themes": ["gratitude"], "preferred_tones": ["encouraging"], "preferred_length": "short", "preferred_philosophies": ["gratitude"]}	2f25f0cc-6130-464f-be8a-76d863ca0952	2026-04-19 19:59:47.343592+00	2026-04-22 20:21:06.457771+00
\.


--
-- Data for Name: notes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.notes (id, family_id, family_member_id, title, body, category, is_archived, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: parent_action_items; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.parent_action_items (id, family_id, created_by_member_id, action_type, title, detail, entity_type, entity_id, status, resolved_by, resolved_at, created_at, updated_at) FROM stdin;
c02afce6-96b1-4dc9-b9f1-64c40da1ccff	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	purchase_request	Andrew requested 'Paper towels'	\N	purchase_request	07db2f62-f8a2-47af-bcfb-87b80a52d649	pending	\N	\N	2026-04-13 17:53:23.149107+00	2026-04-13 17:53:23.149107+00
1ba34c7a-30a5-45d9-9d56-010f8042cbf3	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	moderation_alert	Scout blocked a sensitive message (drugs_or_alcohol)	A child's message to Scout AI was blocked by the safety gate. Open the conversation to review what happened. Tap to see details.	ai_conversation	e7cbde56-edd1-4490-94cd-c6695a54e6b4	pending	\N	\N	2026-04-13 20:31:31.426446+00	2026-04-13 20:31:31.426446+00
034c820d-5734-4227-9e84-2d79ebf09b31	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	daily_brief	Morning brief ready	# Daily Briefing - Sunday, April 13, 2026\n\n**Good afternoon, Andrew!**\n\n## Today's Overview\n- **No scheduled events** - Open Sunday for family time\n- **No pending tasks** - You're caught up!\n- **No meal plans** - Time to decide on dinner\n- **Bills:** All current bills are paid ✓\n\n## Family Status\n- **Children:** Sadie (13), Townes (10), Tyler (8) - all active\n- **Adults:** You, Sally, and Smoke\n\n## Action Items\n- **Meal Planning:** No dinner planned yet - consider what the family would like\n- **Tomorrow Prep:** Sunday evening is great for planning the upcoming week\n\n## Notes\nIt's a quiet Sunday with no pressing obligations. Perfect opportunity for family activities, meal prep for the week ahead, or simply relaxing together. The clear schedule gives you flexibility to be spontaneous or tackle any household projects you've been putting off.\n\nEverything appears to be running smoothly - enjoy your Sunday!	ai_daily_insight	\N	pending	\N	\N	2026-04-13 21:48:01.403056+00	2026-04-13 21:48:01.403056+00
4dab803a-615a-4958-85da-ce9e6484ee76	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	daily_brief	Morning brief ready	**Daily Briefing - Sunday, April 13, 2026**\n\n**Family Status:** All 6 family members active (Andrew, Sally, Sadie, Townes, Tyler, Smoke)\n\n**Today's Schedule:**\n- No scheduled events\n- No specific tasks assigned\n- No planned meals\n\n**Financial Status:**\n- All bills are current (no unpaid bills)\n\n**Action Items:**\nSince it's Sunday with no scheduled activities, this might be a good day to:\n- Plan the upcoming week's meals and activities\n- Check in on any weekend chores or family time\n- Prepare for Monday's schedule\n\n**Notes:**\n- Sadie (13), Townes (10), and Tyler (8) may need supervision for weekend activities\n- Consider planning Sunday dinner or family activity\n- Good opportunity to review and set up the week ahead\n\nEverything appears to be running smoothly with no urgent items requiring immediate attention. Let me know if you'd like help planning any activities or preparing for the week ahead!	ai_daily_insight	\N	pending	\N	\N	2026-04-13 21:48:01.403056+00	2026-04-13 21:48:01.403056+00
2521409d-474d-4f34-93f8-3325a827f02c	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	daily_brief	Morning brief ready	# Daily Briefing - Sunday, April 13, 2026\n\n**Current Time:** 4:48 PM\n\n## Today's Status\n- **Tasks:** No scheduled tasks\n- **Events:** No scheduled events  \n- **Meals:** No meal plans set\n- **Bills:** All bills are current\n\n## Family Overview\n- **Adults:** Andrew, Sally, Smoke\n- **Children:** Sadie (13), Townes (10), Tyler (8)\n\n## Attention Needed\nSince it's Sunday evening and no meals are planned, you may want to:\n- Plan dinner for tonight\n- Set up meal planning for the upcoming week\n- Review tomorrow's schedule and prepare for Monday\n- Consider any weekend tasks that need completion\n\nThe day appears clear with no immediate obligations. This might be a good time to catch up on family planning or enjoy some relaxed family time.\n\nWould you like me to help set up meals, check tomorrow's weather, or assist with any other family planning?	ai_daily_insight	\N	pending	\N	\N	2026-04-13 21:48:01.403056+00	2026-04-13 21:48:01.403056+00
d2b256a3-8af6-4163-8e07-89ded9681a07	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	weekly_retro	Week of 2026-04-13 retro	**Week of 2026-04-13**\n\n**Kids**\n- Sadie: 0 daily wins\n- Townes: 0 daily wins\n- Tyler: 0 daily wins\n\n**Household**\n- Purchase requests: 1\n- Inbox still open: 5\n\n**Scout activity**\n- Chat turns: 25\n- Tool calls: 14\n- Safety blocks: 1 (check the Inbox for alerts)	weekly_retro	\N	pending	\N	\N	2026-04-13 22:40:57.022135+00	2026-04-13 22:40:57.022135+00
2e97d13b-4398-4823-8cfa-0efe27c2c5cc	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	daily_brief	Morning brief ready	**Daily Briefing for Monday, April 14, 2026**\n\n**Schedule:** Clear day ahead - no events or tasks currently scheduled.\n\n**Family:** All five Roberts family members active. Kids are Sadie (13), Townes (10), and Tyler (8).\n\n**Tasks:** No pending tasks for today.\n\n**Meals:** No meals planned yet for today.\n\n**Bills:** All caught up - no unpaid bills.\n\n**Action Items:**\n- Consider planning meals for today (breakfast, lunch, dinner)\n- Check if kids have any school activities or homework\n- Review weekly schedule for upcoming commitments\n\n**Good to know:** It's a Monday, so this might be a good day to set up the week's routine, plan meals, or tackle any household organization that got pushed from the weekend.\n\nNeed me to help plan today's meals or check on anything specific for the kids?	ai_daily_insight	\N	pending	\N	\N	2026-04-14 11:00:26.086591+00	2026-04-14 11:00:26.086591+00
708921f2-044d-460e-90a4-b9ced0ffbec0	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	daily_brief	Morning brief ready	**Daily Briefing for Monday, April 14, 2026**\n\n**Schedule:** Clear day ahead - no events or tasks currently scheduled.\n\n**Family:** All five Roberts family members active. Kids are Sadie (13), Townes (10), and Tyler (8).\n\n**Tasks:** No pending tasks for today.\n\n**Meals:** No meals planned yet for today.\n\n**Bills:** All caught up - no unpaid bills.\n\n**Needs Attention:**\n- Consider planning meals for today (breakfast, lunch, dinner)\n- Check if kids have any school activities or homework\n- Review weekly schedule to add any missing tasks or events\n\n**Quick Actions Available:**\n- Add tasks or events for today\n- Plan meals or add to grocery list\n- Check weather for outdoor activities\n- Review children's chores and routines\n\nThe day is wide open for planning. Would you like me to help schedule meals, check the weather, or add any tasks or events?	ai_daily_insight	\N	pending	\N	\N	2026-04-14 11:00:26.086591+00	2026-04-14 11:00:26.086591+00
6a20135b-8617-43c7-adf2-e80e6f8ac440	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	daily_brief	Morning brief ready	**Daily Briefing - Monday, April 14, 2026**\n\n**Schedule:** Clear day ahead - no events or appointments scheduled.\n\n**Tasks:** No specific tasks assigned for today.\n\n**Meals:** No meal plan currently set. You'll need to figure out breakfast, lunch, and dinner for the family.\n\n**Family Status:** All five family members (Andrew, Sally, Smoke, Sadie, Townes, Tyler) are active in the system.\n\n**Bills:** All caught up - no unpaid bills requiring attention.\n\n**Action Items:**\n- Plan meals for today (and potentially the week)\n- Check if kids have any school or activity schedules not yet logged\n- Consider setting up recurring tasks or events if needed\n\n**Weather:** Would you like me to check today's weather for your area?\n\nThe day looks wide open, which could be a good opportunity to get organized or tackle any household projects. Let me know if you'd like help planning meals, setting up schedules, or managing any other family operations.	ai_daily_insight	\N	pending	\N	\N	2026-04-14 11:00:26.086591+00	2026-04-14 11:00:26.086591+00
78361623-63c3-4c7b-8367-92b2dac89608	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	daily_brief	Morning brief ready	**Daily Briefing - Tuesday, April 22, 2026**\n\n**Schedule:** Clear day ahead - no events or appointments scheduled.\n\n**Tasks:** No specific tasks on your list today.\n\n**Meals:** No meals planned yet. You might want to think about dinner and any prep needed.\n\n**Bills:** All caught up - no outstanding bills to pay.\n\n**Family:** Everyone's home base today with Andrew, Sally, Sadie (13), Townes (10), Tyler (18), and River (8).\n\n**Action Items:**\n- Consider planning today's meals, especially dinner\n- Check if kids have any school or activity needs\n- Good day to tackle any household projects or catch up on family planning\n\nThat's it for today - relatively open schedule gives you flexibility to handle whatever comes up or get ahead on family planning.	ai_daily_insight	\N	pending	\N	\N	2026-04-22 11:02:34.110706+00	2026-04-22 11:02:34.110706+00
1078739c-7092-47b2-9a85-27030baed184	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	daily_brief	Morning brief ready	**Daily Briefing - Tuesday, April 15, 2026**\n\n**Schedule:** Clear day ahead - no events or tasks currently scheduled.\n\n**Meals:** No meals planned yet for today. You'll want to figure out breakfast, lunch, and dinner for the family.\n\n**Family Status:** All family members active - Andrew, Sally, Sadie (13), Townes (10), Tyler (18), and River (8).\n\n**Bills:** All caught up - no unpaid bills requiring attention.\n\n**Action Items:**\n- Plan today's meals for the family\n- Check if kids have any school activities or homework needs\n- Consider adding any tasks or appointments to the schedule\n\n**Weather:** Want me to check the forecast for Fort Worth to help with planning?\n\nThe day is wide open, which gives you flexibility to tackle any priorities that come up. Let me know if you'd like help planning meals, checking chores, or organizing anything else for the family.	ai_daily_insight	\N	pending	\N	\N	2026-04-15 11:04:30.608424+00	2026-04-15 11:04:30.608424+00
31ca9223-d5fe-4692-bd67-927770f08bea	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	daily_brief	Morning brief ready	**Daily Briefing for Tuesday, April 15, 2026**\n\n**Schedule:** Clear day ahead - no events or tasks currently scheduled.\n\n**Meals:** No meals planned yet for today. You'll want to figure out breakfast, lunch, and dinner for the family.\n\n**Family Status:** All six family members (Andrew, Sally, Tyler, Sadie, Townes, River) are active in the system.\n\n**Bills:** All caught up - no unpaid bills requiring attention.\n\n**Action Items:**\n- Plan today's meals for the family\n- Consider scheduling any needed activities or tasks\n\n**Notes:** It's a relatively open day, which could be a good opportunity to catch up on household planning, spend time with the kids, or tackle any projects that have been on the back burner.\n\nNeed help planning meals for today or adding any tasks to your schedule?	ai_daily_insight	\N	pending	\N	\N	2026-04-15 11:04:30.608424+00	2026-04-15 11:04:30.608424+00
91e50135-3956-4c78-9a80-cda385561091	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	daily_brief	Morning brief ready	**Daily Briefing for Tuesday, April 15, 2026**\n\n**Schedule Status:** Clear day ahead! No scheduled events or tasks currently on the calendar.\n\n**Family:** All six family members active - Andrew, Sally, Smoke (adults) and Sadie (13), Tyler (18), Townes (10), River (8).\n\n**Tasks & Events:** Nothing scheduled for today. This could be a good opportunity to catch up on household projects or plan ahead for the week.\n\n**Meals:** No meal plan set for today. You'll need to decide on breakfast, lunch, and dinner.\n\n**Bills:** All caught up - no unpaid bills requiring attention.\n\n**Action Items:**\n- Plan today's meals\n- Consider scheduling any upcoming family activities\n- Check if kids have any school assignments or activities not yet added to the calendar\n\nThe day is yours to shape! Let me know if you'd like help planning meals, adding tasks, or organizing anything for the family.	ai_daily_insight	\N	pending	\N	\N	2026-04-15 11:04:30.608424+00	2026-04-15 11:04:30.608424+00
111bf30d-8ceb-447f-aaac-2403f92499b9	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	daily_brief	Morning brief ready	**Daily Briefing - Wednesday, April 16, 2026**\n\n**Schedule:** Clear day ahead - no events or tasks currently scheduled.\n\n**Meals:** No meal plan set for today. You'll need to figure out breakfast, lunch, and dinner.\n\n**Bills:** All caught up - no unpaid bills requiring attention.\n\n**Family Status:** Everyone's active in the system (Andrew, Sally, Sadie, Townes, Tyler, River).\n\n**Action Items:**\n- Plan today's meals or consider meal prep for the week\n- Check if kids have any school activities or homework needs\n- Review upcoming days for any planning needed\n\nThe day is wide open, which could be a good opportunity to get ahead on meal planning or tackle any household projects that have been on the back burner. Let me know if you'd like help planning meals for today or the week ahead.	ai_daily_insight	\N	pending	\N	\N	2026-04-16 11:00:32.270633+00	2026-04-16 11:00:32.270633+00
f905e632-8d42-4132-a4c4-e6b309b19c3d	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	daily_brief	Morning brief ready	**Daily Briefing for Wednesday, April 16, 2026**\n\n**Schedule:** Clear day ahead - no events or tasks currently scheduled.\n\n**Meals:** No meal plan set for today. You'll need to decide on breakfast, lunch, and dinner.\n\n**Tasks:** No specific tasks on the list.\n\n**Bills:** All caught up - no unpaid bills requiring attention.\n\n**Family Status:** All family members (Andrew, Sally, Tyler, Sadie, Townes, River) are active in the system.\n\n**Action Items:**\n- Plan today's meals\n- Consider adding any tasks or events that need scheduling\n- Check if the kids have any school activities or commitments not yet logged\n\nThe day is wide open, which could be a good opportunity to catch up on household planning or enjoy some unstructured family time. Would you like me to help plan meals for today or check on anything specific for the kids?	ai_daily_insight	\N	pending	\N	\N	2026-04-16 11:00:32.270633+00	2026-04-16 11:00:32.270633+00
9488357f-1a36-4492-a833-c489a0491f2a	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	daily_brief	Morning brief ready	## Daily Briefing - Wednesday, April 16, 2026\n\n**Good morning, Smoke!** Here's your day at a glance:\n\n**Tasks & Events:** No scheduled tasks or events today. You have a clean slate to tackle whatever comes up.\n\n**Meals:** No meal plan set for today. You'll need to figure out breakfast, lunch, and dinner for the family.\n\n**Bills & Finance:** All caught up - no unpaid bills requiring attention.\n\n**Family Status:** Everyone's active and accounted for - Andrew, Sally, you, and the kids (Tyler, Sadie, Townes, and River).\n\n**Action Items:**\n- Plan today's meals for the family\n- Consider setting up some structure for the day since the calendar is open\n\nSince you don't have any pressing commitments, this could be a good day to meal plan for the week ahead or catch up on any household projects. Let me know if you'd like help with meal planning or organizing anything else for the family!	ai_daily_insight	\N	pending	\N	\N	2026-04-16 11:00:32.270633+00	2026-04-16 11:00:32.270633+00
7adeb472-d2ba-45fa-862a-5a03c7415f27	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	daily_brief	Morning brief ready	**Daily Briefing for Thursday, April 17, 2026**\n\n**Schedule:** Clear day ahead - no events or tasks currently scheduled.\n\n**Meals:** No meals planned yet for today. You'll want to figure out breakfast, lunch, and dinner for the family.\n\n**Tasks:** No specific tasks on the list, but it's a good opportunity to catch up on anything that needs attention.\n\n**Family Status:** All family members active - Andrew, Sally, Sadie (13), Townes (10), Tyler (18), River (8), and Smoke.\n\n**Bills:** All caught up - no unpaid bills requiring attention.\n\n**Action Items:**\n- Plan today's meals\n- Check if kids need help with any school or personal tasks\n- Consider any household maintenance or family activities\n\nSince your schedule is open, this could be a great day to tackle any projects you've been putting off or spend quality time with the family. Let me know if you'd like help planning meals or organizing any specific activities for today.	ai_daily_insight	\N	pending	\N	\N	2026-04-17 11:02:45.228148+00	2026-04-17 11:02:45.228148+00
dbff5592-d229-44d0-bdf0-6c8a89324544	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	daily_brief	Morning brief ready	**Daily Briefing for Tuesday, April 22, 2026**\n\n**Schedule:** Clear day ahead - no events or appointments scheduled.\n\n**Tasks:** No specific tasks assigned for today.\n\n**Meals:** No meal plan currently set. You'll need to figure out breakfast, lunch, and dinner for the family.\n\n**Bills:** All caught up - no outstanding bills to pay.\n\n**Family Status:** All family members (Andrew, Sally, Tyler, Sadie, Townes, River) are active in the system.\n\n**Action Items:**\n- Plan today's meals for the family\n- Consider setting up tasks or chores for the kids if needed\n- Good day to meal plan for the week ahead if you haven't already\n\n**Bottom Line:** It's a wide-open day with no pressing commitments. Perfect opportunity to get organized or tackle any household projects you've been putting off.\n\nNeed help planning meals or setting up any tasks for today?	ai_daily_insight	\N	pending	\N	\N	2026-04-22 11:02:34.110706+00	2026-04-22 11:02:34.110706+00
3d9e28db-1136-46c3-bd91-36c0302e498a	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	daily_brief	Morning brief ready	**Daily Briefing - Thursday, April 17, 2026**\n\n**Schedule:** Clear day ahead - no events or appointments scheduled.\n\n**Tasks:** No specific tasks on the list for today.\n\n**Meals:** No meal plan set for today. You'll need to decide on breakfast, lunch, and dinner.\n\n**Bills:** All caught up - no unpaid bills requiring attention.\n\n**Family Status:** All family members (Andrew, Sally, Sadie, Townes, Tyler, River, and Smoke) are active in the system.\n\n**Action Items:**\n- Plan today's meals\n- Consider scheduling any needed appointments or activities\n- Check if any household tasks need attention\n\nIt's a relatively open day with no pressing commitments. Good opportunity to tackle any household projects, meal planning, or family activities you've been putting off. Let me know if you'd like help planning meals, checking the weather, or organizing any tasks for the family.	ai_daily_insight	\N	pending	\N	\N	2026-04-17 11:02:45.228148+00	2026-04-17 11:02:45.228148+00
866d5da8-924d-4dce-8355-5976058daaea	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	daily_brief	Morning brief ready	**Daily Briefing - Thursday, April 17, 2026**\n\n**Schedule:** Clear day ahead - no events or appointments scheduled.\n\n**Tasks:** No specific tasks assigned for today.\n\n**Meals:** No meal plan set for today. You'll need to decide on breakfast, lunch, and dinner.\n\n**Bills:** All caught up - no outstanding bills to pay.\n\n**Family Status:** All family members (Andrew, Sally, Tyler, Sadie, Townes, River, and you) are active in the system.\n\n**Action Items:**\n- Plan today's meals\n- Consider setting up tasks or events if needed\n- Good opportunity for spontaneous family activities or catching up on household projects\n\n**Weather:** Would you like me to check today's weather forecast for your area?\n\nThe day is wide open - perfect for either relaxing or tackling any projects you've been putting off. Let me know if you'd like help planning meals or organizing any activities for the family.	ai_daily_insight	\N	pending	\N	\N	2026-04-17 11:02:45.228148+00	2026-04-17 11:02:45.228148+00
8a2bd4f5-4376-47ca-8cab-967cf10e6c2a	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	daily_brief	Morning brief ready	**Daily Briefing - Friday, April 18, 2026**\n\n**Schedule:** Clear day ahead with no scheduled events or appointments.\n\n**Tasks:** No specific tasks on your list today.\n\n**Meals:** No meals currently planned. You might want to consider what's for dinner tonight and weekend meal prep.\n\n**Bills:** All caught up - no unpaid bills requiring attention.\n\n**Family Status:** All family members (Andrew, Sally, Tyler, Sadie, Townes, River, and Smoke) are active in the system.\n\n**Opportunities:**\n- Light schedule makes this a good day for meal planning or grocery shopping\n- Consider setting up weekend activities or catching up on household projects\n- Perfect time to review next week's calendar and prep ahead\n\n**Weather:** Would you like me to check today's weather forecast for your area?\n\nOverall, it's a relatively open day with flexibility to tackle whatever priorities you have in mind. Let me know if you'd like help planning meals, checking chores, or organizing anything specific!	ai_daily_insight	\N	pending	\N	\N	2026-04-18 11:01:26.968221+00	2026-04-18 11:01:26.968221+00
0e053269-441c-45f3-a7b8-85a7dd84c4d1	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	daily_brief	Morning brief ready	**Daily Briefing for Friday, April 18, 2026**\n\n**Schedule:** Clear day ahead - no events or appointments scheduled.\n\n**Tasks:** No specific tasks on your list today.\n\n**Meals:** No meals planned yet. You might want to think about dinner and weekend meal prep.\n\n**Bills:** All caught up - no unpaid bills requiring attention.\n\n**Family Status:** Everyone's active in the system (Andrew, Sally, Tyler, Sadie, Townes, River, and Smoke).\n\n**Opportunities:**\n- Perfect day to plan weekend activities or catch up on household projects\n- Consider planning meals for the weekend or next week\n- Good time to review and set up tasks for the kids' chores and routines\n\nSince it's a relatively open day, you could use this time to get ahead on planning or tackle any household organization that's been on the back burner. Let me know if you'd like help with meal planning, setting up chores, or organizing anything specific!	ai_daily_insight	\N	pending	\N	\N	2026-04-18 11:01:26.968221+00	2026-04-18 11:01:26.968221+00
2e48e677-93c3-48ec-ab23-09bb3844bb22	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	daily_brief	Morning brief ready	**Daily Briefing for Friday, April 18, 2026**\n\n**Schedule:** Clear day ahead - no events or appointments scheduled.\n\n**Tasks:** No specific tasks on the list for today.\n\n**Meals:** No meal plan set for today. You'll need to figure out breakfast, lunch, and dinner.\n\n**Bills:** All caught up - no unpaid bills requiring attention.\n\n**Family Status:** All family members (Andrew, Sally, Smoke, Tyler, Sadie, Townes, River) are active in the system.\n\n**Action Items:**\n- Plan today's meals\n- Consider setting up weekend activities or meal prep\n- Check if any chores need assignment to the kids\n\nIt's a relatively open day, which could be perfect for catching up on household tasks, family time, or getting ahead on weekend planning. Would you like me to help plan meals for today or check on anything specific for the kids?	ai_daily_insight	\N	pending	\N	\N	2026-04-18 11:01:26.968221+00	2026-04-18 11:01:26.968221+00
dec581d7-1b45-41e8-a292-478593ad2a66	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	daily_brief	Morning brief ready	**Daily Briefing - Saturday, April 19, 2026**\n\n**Schedule:** Clear day ahead! No scheduled events or tasks on the calendar.\n\n**Meals:** No meals planned yet for today. You'll want to figure out breakfast, lunch, and dinner for the family.\n\n**Bills:** All caught up - no unpaid bills requiring attention.\n\n**Family Status:** Everyone's home (Andrew, Sally, Sadie, Townes, Tyler, River, and Smoke).\n\n**Action Items:**\n- Plan today's meals for 7 people\n- Consider any weekend activities or errands\n- Check if kids have any weekend homework or projects due Monday\n\n**Weather:** Want me to check the forecast for 76126 to help plan any outdoor activities?\n\nSince it's a Saturday with no scheduled commitments, this could be a good day for family time, catching up on household tasks, or planning ahead for the upcoming week. Let me know if you'd like help with meal planning or checking anything specific!	ai_daily_insight	\N	pending	\N	\N	2026-04-19 11:01:42.471072+00	2026-04-19 11:01:42.471072+00
68c753ad-69bf-4ca6-82ab-bc3fd96ff354	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	daily_brief	Morning brief ready	## Daily Briefing - Saturday, April 19th\n\n**Good morning, Sally!** Here's your day at a glance:\n\n**Schedule:** You have a clear day with no scheduled events or tasks on the calendar.\n\n**Meals:** No meals are currently planned for today. You might want to think about what the family will eat for breakfast, lunch, and dinner.\n\n**Tasks:** No specific tasks are scheduled for today.\n\n**Bills:** All bills are current - nothing needs immediate attention.\n\n**Family Status:** Everyone's home (Andrew, you, Sadie, Townes, Tyler, River, and Smoke).\n\n**Action Items:**\n- Plan today's meals for the family\n- Consider any weekend activities or errands\n- Check if any of the kids have chores or activities planned\n\nSince it's Saturday, this could be a great day for family time, meal prep for the week ahead, or catching up on household tasks. Let me know if you'd like help planning meals, checking the weather for outdoor activities, or organizing anything for the family!	ai_daily_insight	\N	pending	\N	\N	2026-04-19 11:01:42.471072+00	2026-04-19 11:01:42.471072+00
6d9a80d5-8eb9-4601-b1eb-cd1e85d58430	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	daily_brief	Morning brief ready	**Daily Briefing - Saturday, April 19, 2026**\n\n**Schedule:** Clear day ahead! No scheduled events or tasks on the calendar.\n\n**Meals:** No meals planned yet. You'll want to sort out breakfast, lunch, and dinner for the family today.\n\n**Bills:** All caught up - no unpaid bills requiring attention.\n\n**Family Status:** All six family members (Andrew, Sally, Smoke, Tyler, Sadie, Townes, and River) are active in the system.\n\n**Action Items:**\n- Plan today's meals for the family\n- Consider weekend activities or outings since the schedule is open\n- Check if any kids have weekend homework or projects due Monday\n\n**Weather:** Want me to check the forecast for 76126 to help plan any outdoor activities?\n\nSince it's a Saturday with no scheduled commitments, this could be a great day for family time, meal prep for the week ahead, or tackling any household projects that have been on the back burner.\n\nNeed help planning meals or organizing any weekend activities?	ai_daily_insight	\N	pending	\N	\N	2026-04-19 11:01:42.471072+00	2026-04-19 11:01:42.471072+00
63dd3dc6-e936-4f37-8521-d218351aaf22	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	daily_brief	Morning brief ready	**Daily Briefing for Sunday, April 20, 2026**\n\n**Schedule:** Clear day ahead - no events or tasks currently scheduled.\n\n**Meals:** No meals planned yet for today. You'll want to sort out breakfast, lunch, and dinner.\n\n**Family Status:** Everyone's home - Andrew, Sally, Smoke (adults) and kids Sadie (13), Tyler (18), Townes (10), and River (8).\n\n**Bills:** All caught up - no outstanding bills to pay.\n\n**Action Items:**\n- Plan today's meals\n- Consider setting up the week ahead (meal planning, scheduling)\n- Check if kids have any homework or activities tomorrow (Monday)\n\n**Weather:** Want me to check the forecast for Fort Worth?\n\nIt's a quiet Sunday with a clean slate. Good opportunity to get organized for the week or just enjoy some family downtime. Let me know if you'd like help planning meals or setting up anything for the days ahead.	ai_daily_insight	\N	pending	\N	\N	2026-04-20 11:01:42.471712+00	2026-04-20 11:01:42.471712+00
b9aee7a6-796c-409d-beb0-42278be28edd	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	daily_brief	Morning brief ready	**Daily Briefing for Sunday, April 20, 2026**\n\n**Schedule:** Clear day ahead - no events or tasks currently scheduled.\n\n**Meals:** No meals planned yet for today. You'll want to sort out breakfast, lunch, and dinner for the family.\n\n**Family Status:** All family members active - Andrew, Sally, Tyler (18), Sadie (13), Townes (10), River (8), and Smoke.\n\n**Bills:** All caught up - no unpaid bills requiring attention.\n\n**Action Items:**\n- Plan today's meals for the family\n- Consider setting up the week ahead since it's Sunday\n- Check if any prep work is needed for the upcoming week\n\n**Weather:** Would you like me to check today's weather forecast for your area?\n\nSince it's a quiet Sunday with nothing scheduled, this might be a good time to plan the week ahead or tackle any household projects. Let me know if you'd like help with meal planning or organizing anything for the coming week!	ai_daily_insight	\N	pending	\N	\N	2026-04-20 11:01:42.471712+00	2026-04-20 11:01:42.471712+00
2f426769-73f4-4268-a56d-9b4ff3c4f013	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	daily_brief	Morning brief ready	**Daily Briefing - Sunday, April 20, 2026**\n\n**Schedule:** Clear day ahead! No events or appointments scheduled.\n\n**Tasks:** No specific tasks on your list today.\n\n**Meals:** No meal plan set for today. You'll need to figure out breakfast, lunch, and dinner.\n\n**Bills:** All caught up - no unpaid bills requiring attention.\n\n**Family Status:** Everyone's active in the system - Andrew, Sally, Smoke (you), and the kids: Tyler (18), Sadie (13), Townes (10), and River (8).\n\n**Action Items:**\n- Plan today's meals or consider meal prep for the week\n- Check if kids have any chores or routines to complete\n- Good day to tackle any household projects or family planning\n\nSince it's Sunday with a clear schedule, this could be perfect for weekly meal planning, grocery shopping, or family time. Let me know if you'd like help planning meals for the week or checking on anything specific for the kids!	ai_daily_insight	\N	pending	\N	\N	2026-04-20 11:01:42.471712+00	2026-04-20 11:01:42.471712+00
45ad669c-66ca-4131-810d-98c5f459563a	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	daily_brief	Morning brief ready	**Daily Briefing for Monday, April 21, 2026**\n\n**Schedule:** Clear day ahead - no events or tasks currently scheduled.\n\n**Meals:** No meal plan set for today. You'll need to decide on breakfast, lunch, and dinner for the family.\n\n**Tasks:** No specific tasks on the list today.\n\n**Bills:** All caught up - no unpaid bills requiring attention.\n\n**Family Status:** Everyone's active in the system - Andrew, Sally, Smoke (adults), and kids Sadie (13), Tyler (18), Townes (10), and River (8).\n\n**Action Items:**\n- Plan today's meals for the family\n- Consider adding any tasks or events that might be coming up\n- Check if kids have any school or activity schedules to add\n\nThe day is wide open, which could be a good opportunity to catch up on planning or tackle any household projects that have been on the back burner. Let me know if you'd like help setting up meals, adding tasks, or organizing anything for the week ahead.	ai_daily_insight	\N	pending	\N	\N	2026-04-21 11:02:29.022847+00	2026-04-21 11:02:29.022847+00
8c94fe89-1ed1-4fad-9bc7-02b440edda72	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	daily_brief	Morning brief ready	**Daily Briefing for Monday, April 21st**\n\n**Schedule:** Clear day ahead - no events or tasks currently scheduled.\n\n**Meals:** No meal plan set for today. You'll need to figure out breakfast, lunch, and dinner.\n\n**Tasks:** Nothing on the task list.\n\n**Bills:** All caught up - no unpaid bills.\n\n**Family Status:** Everyone's active in the system (Andrew, Sally, Sadie, Townes, Tyler, River, and Smoke).\n\n**Action Items:**\n- Plan today's meals\n- Consider adding any tasks or events you have coming up\n- Check if the kids have any school or activity commitments\n\nIt's a relatively open day, which could be perfect for catching up on anything that's been on the back burner or just enjoying some family time. Let me know if you'd like help planning meals or adding anything to the schedule!	ai_daily_insight	\N	pending	\N	\N	2026-04-21 11:02:29.022847+00	2026-04-21 11:02:29.022847+00
0e30823f-00b9-4a7b-a15b-d2fa262f1651	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	daily_brief	Morning brief ready	**Daily Briefing for Monday, April 21, 2026**\n\n**Schedule:** Clear day ahead - no events or tasks currently scheduled.\n\n**Meals:** No meal plan set for today. You'll need to decide on breakfast, lunch, and dinner for the family.\n\n**Tasks:** No pending tasks on the list.\n\n**Bills:** All caught up - no unpaid bills requiring attention.\n\n**Family Status:** All six family members (Andrew, Sally, Smoke, Tyler, Sadie, Townes, and River) are active in the system.\n\n**Action Items:**\n- Plan today's meals for the family\n- Consider scheduling any needed activities or tasks\n- Check if the kids have any school or activity commitments not yet in the system\n\nThe day is wide open, which gives you flexibility to handle anything that comes up or focus on family time. Let me know if you'd like help planning meals or adding any tasks or events to the schedule.	ai_daily_insight	\N	pending	\N	\N	2026-04-21 11:02:29.022847+00	2026-04-21 11:02:29.022847+00
82a17bed-b21c-43fe-8eaa-98093118df46	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	daily_brief	Morning brief ready	**Daily Briefing for Tuesday, April 22, 2026**\n\n**Schedule:** Clear day ahead - no events or appointments scheduled.\n\n**Tasks:** No specific tasks on the calendar today.\n\n**Meals:** No meal plan set for today. You'll need to figure out breakfast, lunch, and dinner.\n\n**Bills:** All caught up - no unpaid bills requiring attention.\n\n**Family:** All six family members (Andrew, Sally, Smoke, Tyler, Sadie, Townes, River) are active in the system.\n\n**Action Items:**\n- Plan today's meals\n- Consider setting up tasks or events if needed\n\nIt's a relatively open day with no pressing obligations. Good opportunity to tackle any household projects, meal planning for the week, or family activities. Let me know if you'd like help planning meals, checking the weather, or setting up any tasks or events.	ai_daily_insight	\N	pending	\N	\N	2026-04-22 11:02:34.110706+00	2026-04-22 11:02:34.110706+00
0a16a521-15ab-4421-82fc-e56cf699e4b8	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	daily_brief	Morning brief ready	## Daily Briefing - Wednesday, April 23, 2026\n\n**Good morning, Andrew!**\n\n**Today's Schedule:**\n- No scheduled events or calendar items\n- No specific tasks or project deadlines today\n\n**Family Status:**\n- All family members (you, Sally, Smoke, and the kids: Tyler, Sadie, Townes, River, Smoke-Child) are active\n- No outstanding bills requiring attention\n\n**Meals:**\n- No meal plan currently set for today\n- Consider planning breakfast, lunch, and dinner for the family\n\n**Action Items:**\n- You might want to set up meals for today or plan the week ahead\n- Check in on any chores or routines for the kids\n- Consider scheduling any upcoming family activities\n\n**Weather:** Available on request for your 76126 area.\n\nIt's looking like a clean slate day! Let me know if you'd like help planning meals, checking weather, or organizing any family activities.	ai_daily_insight	\N	pending	\N	\N	2026-04-23 11:00:30.011068+00	2026-04-23 11:00:30.011068+00
85ffb2c9-994b-4058-adef-0a427d0381e7	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	daily_brief	Morning brief ready	**Daily Briefing for Wednesday, April 23, 2026**\n\n**Schedule:** Clear day ahead - no events or appointments scheduled.\n\n**Tasks:** No specific tasks on the agenda today.\n\n**Meals:** No meal plan set for today. You'll need to decide on breakfast, lunch, and dinner for the family.\n\n**Bills:** All caught up - no unpaid bills requiring attention.\n\n**Family Status:** All seven family members (Andrew, Sally, Tyler, Sadie, Townes, River, and Smoke-Child) are active in the system.\n\n**Action Items:**\n- Plan today's meals for the family\n- Consider scheduling any needed activities or appointments\n- Check if any children have chores or routines to complete\n\nSince it's a relatively open day, this might be a good opportunity to catch up on family planning, meal prep, or tackle any household projects that have been on the back burner. Let me know if you'd like help planning meals or organizing any activities for today!	ai_daily_insight	\N	pending	\N	\N	2026-04-23 11:00:30.011068+00	2026-04-23 11:00:30.011068+00
1878ed1d-98a2-463a-aec6-5f0c8ca64177	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	daily_brief	Morning brief ready	**Daily Briefing for Wednesday, April 23, 2026**\n\n**Schedule:** Clear day ahead - no events or appointments scheduled.\n\n**Tasks:** No specific tasks on the agenda today.\n\n**Meals:** No meal plan currently set. You'll need to figure out breakfast, lunch, and dinner for the family.\n\n**Bills:** All caught up - no unpaid bills requiring attention.\n\n**Family Status:** All seven family members (Andrew, Sally, Tyler, Sadie, Townes, River, Smoke-Child, and you) are active in the system.\n\n**Action Items:**\n- Plan today's meals for the family\n- Consider setting up upcoming events or tasks if needed\n\nSince it's a relatively open day, this might be a good opportunity to meal plan for the week, catch up on household projects, or schedule upcoming family activities. Let me know if you'd like help with meal planning or organizing anything specific for today or the rest of the week.	ai_daily_insight	\N	pending	\N	\N	2026-04-23 11:00:30.011068+00	2026-04-23 11:00:30.011068+00
\.


--
-- Data for Name: personal_tasks; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.personal_tasks (id, family_id, assigned_to, created_by, title, description, notes, status, priority, due_at, completed_at, event_id, created_at, updated_at, source_project_task_id) FROM stdin;
\.


--
-- Data for Name: planner_bundle_applies; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.planner_bundle_applies (id, bundle_apply_id, family_id, actor_member_id, conversation_id, status, tasks_created, events_created, grocery_items_created, errors, summary, created_at) FROM stdin;
\.


--
-- Data for Name: purchase_requests; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.purchase_requests (id, family_id, requested_by_member_id, type, title, details, quantity, unit, preferred_brand, preferred_store, urgency, status, linked_grocery_item_id, reviewed_by_member_id, reviewed_at, review_note, created_at, updated_at) FROM stdin;
07db2f62-f8a2-47af-bcfb-87b80a52d649	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	grocery	Paper towels	\N	\N	\N	\N	\N	\N	pending	\N	\N	\N	\N	2026-04-13 17:53:23.149107+00	2026-04-13 17:53:23.149107+00
\.


--
-- Data for Name: role_tier_overrides; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.role_tier_overrides (id, family_member_id, role_tier_id, override_permissions, override_behavior, created_at, updated_at) FROM stdin;
5b14f540-5701-401a-9aab-76f844786b36	2f25f0cc-6130-464f-be8a-76d863ca0952	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	{}	{}	2026-04-17 03:02:42.370525+00	2026-04-17 13:35:10.108614+00
349b8c11-4098-4501-a883-ba0ac5ddf007	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	{}	{}	2026-04-17 03:02:42.370525+00	2026-04-17 13:35:10.108614+00
7b483991-6d60-4c1d-9358-0051324aa353	6012f148-ae1c-40b4-838f-ef3bb7532e98	a121d6a8-9f52-4104-b4a6-e224b1b42b71	{}	{}	2026-04-17 03:02:42.370525+00	2026-04-17 13:35:10.108614+00
1bd80fc1-e74e-48af-a068-abaedb04ff04	c61d88de-857e-42d3-8116-575f6fabf14f	d802c736-b7a1-4e29-8c28-e93441f3a9e0	{}	{}	2026-04-17 03:02:42.370525+00	2026-04-17 13:35:10.108614+00
d90c6ee2-f9ec-403f-9cc4-63281bb3b999	889e7a80-05ec-4140-9c1b-4f1e7d2eb355	a121d6a8-9f52-4104-b4a6-e224b1b42b71	{}	{}	2026-04-17 03:02:42.370525+00	2026-04-17 13:35:10.108614+00
533323cd-314a-49e4-82a1-356456e414a5	e4d39e09-9d32-4aeb-adad-5014fe3bf6be	9c008964-93c8-442c-8fb4-6a070349c438	{}	{}	2026-04-17 03:02:42.370525+00	2026-04-17 13:35:10.108614+00
b441c40a-f109-4549-915d-3c786dc54f3c	669c229c-96b0-44b7-940d-d026789b7c58	d802c736-b7a1-4e29-8c28-e93441f3a9e0	{}	{}	2026-04-22 22:22:26.652607+00	2026-04-22 22:22:26.652607+00
\.


--
-- Data for Name: role_tiers; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.role_tiers (id, name, permissions, behavior_config, created_at, updated_at, description) FROM stdin;
6fc19fb6-fe86-4e13-aa77-a6747d2ae83d	DISPLAY_ONLY	{}	{}	2026-04-15 22:36:30.435678+00	2026-04-17 13:35:10.108614+00	\N
791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	PRIMARY_PARENT	{}	{}	2026-04-15 22:36:30.435678+00	2026-04-17 13:35:10.108614+00	\N
8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	PARENT	{}	{}	2026-04-15 22:36:30.435678+00	2026-04-17 13:35:10.108614+00	\N
a121d6a8-9f52-4104-b4a6-e224b1b42b71	TEEN	{}	{}	2026-04-15 22:36:30.435678+00	2026-04-17 13:35:10.108614+00	\N
9c008964-93c8-442c-8fb4-6a070349c438	YOUNG_CHILD	{}	{}	2026-04-15 22:36:30.435678+00	2026-04-17 13:35:10.108614+00	\N
d802c736-b7a1-4e29-8c28-e93441f3a9e0	CHILD	{}	{}	2026-04-15 22:36:30.435678+00	2026-04-17 13:35:10.108614+00	\N
\.


--
-- Data for Name: routine_steps; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.routine_steps (id, routine_id, name, sort_order, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: routines; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.routines (id, family_id, family_member_id, name, block, recurrence, due_time_weekday, due_time_weekend, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: scout_anomaly_suppressions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.scout_anomaly_suppressions (id, family_id, anomaly_type, signature, first_seen_at, last_seen_at, suppress_until, created_at) FROM stdin;
\.


--
-- Data for Name: scout_mcp_tokens; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.scout_mcp_tokens (id, family_id, member_id, token_hash, label, scope, is_active, last_used_at, created_by_member_id, created_at, revoked_at) FROM stdin;
\.


--
-- Data for Name: scout_scheduled_runs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.scout_scheduled_runs (id, job_name, family_id, member_id, run_date, status, duration_ms, result, error, created_at) FROM stdin;
b6d6074e-31cb-4e32-8fbc-c3ad632424ac	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	2026-04-13	success	11627	{"model": "claude-sonnet-4-20250514", "brief_length": 914, "action_item_id": "034c820d-5734-4227-9e84-2d79ebf09b31"}	\N	2026-04-13 21:48:01.403056+00
3cfb13cf-545e-4895-9dd5-35c337c93955	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	2026-04-13	success	9527	{"model": "claude-sonnet-4-20250514", "brief_length": 906, "action_item_id": "4dab803a-615a-4958-85da-ce9e6484ee76"}	\N	2026-04-13 21:48:01.403056+00
08bd41a9-3683-448f-a603-67abe3187946	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	2026-04-13	success	9752	{"model": "claude-sonnet-4-20250514", "brief_length": 845, "action_item_id": "2521409d-474d-4f34-93f8-3325a827f02c"}	\N	2026-04-13 21:48:01.403056+00
1507c646-4cf7-4075-ba6c-0d85796440e7	weekly_retro	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	2026-04-13	success	7511	{"action_item_id": "d2b256a3-8af6-4163-8e07-89ded9681a07", "narrative_length": 261}	\N	2026-04-13 22:40:57.022135+00
4bbe1477-f80b-45ef-aa61-208acb510e50	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	2026-04-14	success	9012	{"model": "claude-sonnet-4-20250514", "brief_length": 791, "action_item_id": "2e97d13b-4398-4823-8cfa-0efe27c2c5cc"}	\N	2026-04-14 11:00:26.086591+00
8b4eff2d-6651-4c9c-9a90-30f7fb86c8a9	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	2026-04-14	success	7996	{"model": "claude-sonnet-4-20250514", "brief_length": 851, "action_item_id": "708921f2-044d-460e-90a4-b9ced0ffbec0"}	\N	2026-04-14 11:00:26.086591+00
fa448c2c-2a64-4975-b43d-2a20ee0485af	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	2026-04-14	success	11087	{"model": "claude-sonnet-4-20250514", "brief_length": 943, "action_item_id": "6a20135b-8617-43c7-adf2-e80e6f8ac440"}	\N	2026-04-14 11:00:26.086591+00
cf100794-1b5c-4235-805a-68f6d04ea19c	moderation_digest	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	2026-04-14	success	9	{"event_count": 0, "created_digest": false}	\N	2026-04-15 01:04:30.612504+00
3a48be06-447c-47df-9c1e-8a7219834ca8	anomaly_scan	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	2026-04-14	success	43	{"created": 0, "candidates": 0, "suppressed": 0}	\N	2026-04-15 02:04:30.614877+00
8c82051d-1a7d-47cf-b059-544031d13773	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	2026-04-15	success	7201	{"model": "claude-sonnet-4-20250514", "brief_length": 868, "action_item_id": "1078739c-7092-47b2-9a85-27030baed184"}	\N	2026-04-15 11:04:30.608424+00
3c8c7f1f-d3c7-443e-98ba-59438b34d6bd	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	2026-04-15	success	6021	{"model": "claude-sonnet-4-20250514", "brief_length": 788, "action_item_id": "31ca9223-d5fe-4692-bd67-927770f08bea"}	\N	2026-04-15 11:04:30.608424+00
679bc1c7-9858-41b4-9511-e9040c7e5ba6	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	2026-04-15	success	7352	{"model": "claude-sonnet-4-20250514", "brief_length": 882, "action_item_id": "91e50135-3956-4c78-9a80-cda385561091"}	\N	2026-04-15 11:04:30.608424+00
2f37469a-5f55-4297-a646-1e3ba211c2ca	moderation_digest	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	2026-04-15	success	8	{"event_count": 0, "created_digest": false}	\N	2026-04-16 01:00:32.274073+00
32548113-3a19-4603-b16c-6e9a19683b58	anomaly_scan	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	2026-04-15	success	43	{"created": 0, "candidates": 0, "suppressed": 0}	\N	2026-04-16 02:00:32.278974+00
a54f9b02-f856-4032-bdc4-5988d7c0d000	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	2026-04-16	success	7813	{"model": "claude-sonnet-4-20250514", "brief_length": 791, "action_item_id": "111bf30d-8ceb-447f-aaac-2403f92499b9"}	\N	2026-04-16 11:00:32.270633+00
e49f50c8-576d-4fcb-a2d1-2fb63ac5f7f4	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	2026-04-16	success	8445	{"model": "claude-sonnet-4-20250514", "brief_length": 832, "action_item_id": "f905e632-8d42-4132-a4c4-e6b309b19c3d"}	\N	2026-04-16 11:00:32.270633+00
3f8c6b2e-da1e-47cd-a9e9-ac95b7868094	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	2026-04-16	success	7482	{"model": "claude-sonnet-4-20250514", "brief_length": 890, "action_item_id": "9488357f-1a36-4492-a833-c489a0491f2a"}	\N	2026-04-16 11:00:32.270633+00
2a43a7d4-3224-4150-85bd-627ede71fe00	moderation_digest	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	2026-04-16	success	15	{"event_count": 0, "created_digest": false}	\N	2026-04-17 01:00:31.883023+00
b5f9fe06-3915-4e07-9242-cd2551288fca	anomaly_scan	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	2026-04-16	success	43	{"created": 0, "candidates": 0, "suppressed": 0}	\N	2026-04-17 02:00:31.886347+00
c8c92c0c-edc9-4d74-ad2c-5d7e98f9e69f	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	2026-04-17	success	7752	{"model": "claude-sonnet-4-20250514", "brief_length": 934, "action_item_id": "7adeb472-d2ba-45fa-862a-5a03c7415f27"}	\N	2026-04-17 11:02:45.228148+00
c978f93b-5449-46b9-8bb2-89acd6d066c7	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	2026-04-17	success	6883	{"model": "claude-sonnet-4-20250514", "brief_length": 874, "action_item_id": "3d9e28db-1136-46c3-bd91-36c0302e498a"}	\N	2026-04-17 11:02:45.228148+00
285a84c3-e4e5-4914-8f70-b3264bcb3230	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	2026-04-17	success	7142	{"model": "claude-sonnet-4-20250514", "brief_length": 888, "action_item_id": "866d5da8-924d-4dce-8355-5976058daaea"}	\N	2026-04-17 11:02:45.228148+00
6e8e0021-9f5e-42a7-9162-9a89e60efe09	moderation_digest	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	2026-04-17	success	10	{"event_count": 0, "created_digest": false}	\N	2026-04-18 01:01:26.972597+00
ac3e0106-bc6e-41f2-a577-666213a9fb1d	anomaly_scan	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	2026-04-17	success	76	{"created": 0, "candidates": 0, "suppressed": 0}	\N	2026-04-18 02:01:26.993028+00
6841f504-e972-4b78-a491-7c00fd5956fb	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	2026-04-18	success	6991	{"model": "claude-sonnet-4-20250514", "brief_length": 984, "action_item_id": "8a2bd4f5-4376-47ca-8cab-967cf10e6c2a"}	\N	2026-04-18 11:01:26.968221+00
6aa71408-1914-4af7-b7d9-bb313ca998ff	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	2026-04-18	success	6843	{"model": "claude-sonnet-4-20250514", "brief_length": 912, "action_item_id": "0e053269-441c-45f3-a7b8-85a7dd84c4d1"}	\N	2026-04-18 11:01:26.968221+00
01c6f569-995b-4bd0-a0c9-2a63dc619a04	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	2026-04-18	success	6809	{"model": "claude-sonnet-4-20250514", "brief_length": 820, "action_item_id": "2e48e677-93c3-48ec-ab23-09bb3844bb22"}	\N	2026-04-18 11:01:26.968221+00
645fe6c9-c300-427c-91c8-3a3da4952102	moderation_digest	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	2026-04-18	success	14	{"event_count": 0, "created_digest": false}	\N	2026-04-19 01:00:32.567486+00
ff254ff2-b15e-4ec1-a882-3e173f022203	anomaly_scan	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	2026-04-18	success	75	{"created": 0, "candidates": 0, "suppressed": 0}	\N	2026-04-19 02:00:32.56755+00
371fffc3-fa2a-46be-b4b7-4b53dc5987fa	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	2026-04-19	success	7365	{"model": "claude-sonnet-4-20250514", "brief_length": 900, "action_item_id": "dec581d7-1b45-41e8-a292-478593ad2a66"}	\N	2026-04-19 11:01:42.471072+00
c0b3d168-7009-4af0-adc8-ffd2a055a9b5	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	2026-04-19	success	7397	{"model": "claude-sonnet-4-20250514", "brief_length": 964, "action_item_id": "68c753ad-69bf-4ca6-82ab-bc3fd96ff354"}	\N	2026-04-19 11:01:42.471072+00
86f7195c-3686-48dd-8484-aa87241c05f1	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	2026-04-19	success	7542	{"model": "claude-sonnet-4-20250514", "brief_length": 962, "action_item_id": "6d9a80d5-8eb9-4601-b1eb-cd1e85d58430"}	\N	2026-04-19 11:01:42.471072+00
ee35eef0-7269-42c2-ae05-806ad839f1d1	moderation_digest	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	2026-04-19	success	7	{"event_count": 0, "created_digest": false}	\N	2026-04-20 01:01:42.479923+00
ed335259-e089-4584-a4ad-b190f857c1a7	anomaly_scan	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	2026-04-19	success	47	{"created": 0, "candidates": 0, "suppressed": 0}	\N	2026-04-20 02:01:42.478171+00
c630f61d-2d95-41ed-9043-fdbf0c151f28	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	2026-04-20	success	8376	{"model": "claude-sonnet-4-20250514", "brief_length": 846, "action_item_id": "63dd3dc6-e936-4f37-8521-d218351aaf22"}	\N	2026-04-20 11:01:42.471712+00
041bee47-fbbd-4985-8b8c-19320cc3b72b	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	2026-04-20	success	6538	{"model": "claude-sonnet-4-20250514", "brief_length": 894, "action_item_id": "b9aee7a6-796c-409d-beb0-42278be28edd"}	\N	2026-04-20 11:01:42.471712+00
9b17177d-f655-4f99-ad26-8f6132b2c0ca	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	2026-04-20	success	7771	{"model": "claude-sonnet-4-20250514", "brief_length": 895, "action_item_id": "2f426769-73f4-4268-a56d-9b4ff3c4f013"}	\N	2026-04-20 11:01:42.471712+00
59679028-9ac1-448c-9e46-322a9b0cdd83	moderation_digest	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	2026-04-20	success	9	{"event_count": 0, "created_digest": false}	\N	2026-04-21 01:04:41.979849+00
b68002e3-feb9-48ff-aab3-1b56fe1cafc1	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	2026-04-21	success	8296	{"model": "claude-sonnet-4-20250514", "brief_length": 921, "action_item_id": "45ad669c-66ca-4131-810d-98c5f459563a"}	\N	2026-04-21 11:02:29.022847+00
853d658c-6f2a-4f86-a240-b393e82a0d35	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	2026-04-21	success	6837	{"model": "claude-sonnet-4-20250514", "brief_length": 787, "action_item_id": "8c94fe89-1ed1-4fad-9bc7-02b440edda72"}	\N	2026-04-21 11:02:29.022847+00
2a24f6d5-f467-4fd5-9a33-766c5c6371ef	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	2026-04-21	success	7126	{"model": "claude-sonnet-4-20250514", "brief_length": 852, "action_item_id": "0e30823f-00b9-4a7b-a15b-d2fa262f1651"}	\N	2026-04-21 11:02:29.022847+00
2f1974ea-e932-4997-b484-6242dbe37e6e	moderation_digest	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	2026-04-21	success	9	{"event_count": 0, "created_digest": false}	\N	2026-04-22 01:03:57.620329+00
f7c2670f-11bb-475b-a861-5493fb3c91ee	anomaly_scan	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	2026-04-21	success	59	{"created": 0, "candidates": 0, "suppressed": 0}	\N	2026-04-22 02:03:50.056752+00
16a6caee-e782-4219-95a3-e38e45f080da	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	2026-04-22	success	7718	{"model": "claude-sonnet-4-20250514", "brief_length": 753, "action_item_id": "78361623-63c3-4c7b-8367-92b2dac89608"}	\N	2026-04-22 11:02:34.110706+00
e551e495-7965-425c-b272-203f5317ffbc	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	2026-04-22	success	7078	{"model": "claude-sonnet-4-20250514", "brief_length": 851, "action_item_id": "dbff5592-d229-44d0-bdf0-6c8a89324544"}	\N	2026-04-22 11:02:34.110706+00
c0b86531-d9d9-4159-9c25-66259f039353	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	2026-04-22	success	6652	{"model": "claude-sonnet-4-20250514", "brief_length": 795, "action_item_id": "82a17bed-b21c-43fe-8eaa-98093118df46"}	\N	2026-04-22 11:02:34.110706+00
9f4c86a0-8232-4baf-be87-53f9c28f4766	moderation_digest	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	2026-04-22	success	11	{"event_count": 0, "created_digest": false}	\N	2026-04-23 01:01:01.929627+00
2f7a67f8-41db-4827-a0c2-903844765214	anomaly_scan	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	2026-04-22	success	56	{"created": 0, "candidates": 0, "suppressed": 0}	\N	2026-04-23 02:03:59.662891+00
d4b00623-2ca8-4737-b184-8510708301e7	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	2f25f0cc-6130-464f-be8a-76d863ca0952	2026-04-23	success	8834	{"model": "claude-sonnet-4-20250514", "brief_length": 852, "action_item_id": "0a16a521-15ab-4421-82fc-e56cf699e4b8"}	\N	2026-04-23 11:00:30.011068+00
7af9392f-21a2-4027-bd45-c3783a85a8cf	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	a21ec584-f2b6-4b2e-8ed6-1016f80f353c	2026-04-23	success	7922	{"model": "claude-sonnet-4-20250514", "brief_length": 917, "action_item_id": "85ffb2c9-994b-4058-adef-0a427d0381e7"}	\N	2026-04-23 11:00:30.011068+00
4d054851-e0fa-4d45-8fde-0de18162fdc8	morning_brief	fbe71860-a1a2-42b0-a0b5-df72017ced7c	b684226c-1217-44ca-84d0-3bf7c4ea4e82	2026-04-23	success	8404	{"model": "claude-sonnet-4-20250514", "brief_length": 879, "action_item_id": "1878ed1d-98a2-463a-aec6-5f0c8ca64177"}	\N	2026-04-23 11:00:30.011068+00
\.


--
-- Data for Name: sessions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.sessions (id, user_account_id, token, expires_at, created_at) FROM stdin;
222fc861-6ea3-4ae0-9dd2-e26070e77bce	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	1d_iwqviFYCQCI4KGHJf6xclf8VI5NsFV55Be5o8unkhAVZ4yDaU8DhhOJ3kvaQH	2026-04-15 15:48:13.955332+00	2026-04-12 15:48:13.640972+00
b1589272-a327-42a9-b329-67c9f449cc00	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	6R9wnZ-a3ul_fQH1AYl7rz4565YuAp9dg-E6hd3BLdJ2tavhMqrIliTCbLyEmXDa	2026-04-15 19:26:55.319131+00	2026-04-12 19:26:55.007664+00
4e3dcc6f-c733-4ab1-815c-d6de26a1d72a	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	rIFFmh_-3MZtuj2D69CqKmzMQIom5iQUF_ItL4QPfF2ASBv_9LTHIW522RxJKz3w	2026-04-15 19:27:45.419946+00	2026-04-12 19:27:45.107154+00
9492e4b4-d21e-4cff-aea2-685e74329bac	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	54qrF4MlCDxQOG_zcKVGPGmQ5zIWpERaIDXtDFQKcsebCgNs8SB7bVYHyXEVF3O_	2026-04-15 19:28:50.898578+00	2026-04-12 19:28:50.591462+00
de407469-2988-4a8f-abf3-a0fcbc9e8f3e	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	Q9Xfy74O1cI3scSu5-oJAVhfAf291_uRH9shBG2MeuFx6Ld2cKpe81FClsBHfDre	2026-04-15 19:29:12.613986+00	2026-04-12 19:29:12.30455+00
a6576d21-abfa-4be4-8806-055ee2608b60	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	pmhZBxSDzqan6cPAZ86KZjCACFtxFEsMl_I_gZhtsAkHzZ4dEFlP5ScPrpJ5Mnvz	2026-04-15 19:29:15.326714+00	2026-04-12 19:29:15.01897+00
b9cf13cc-4126-4445-8466-0d84d13fe46e	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	OlzPGILhO1oJTpXSPSmbY2tPgzaHLSphNmyccZOhVDiC9wDVDXBaigjwhWzaAcPO	2026-04-15 19:29:17.919841+00	2026-04-12 19:29:17.612502+00
3345889e-8288-4c86-a905-720705ad2f2a	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	zDGF9KOvfrlolZPeJA3WKRETdQPxhJYQxGbmX80_tFsU66vn7nLk2zjmiFRsrr1e	2026-04-15 19:29:24.196463+00	2026-04-12 19:29:23.886879+00
616bf909-5ac5-4441-bfe8-3e0c21cf4dc0	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	x04860XJJSzdau_s3asSN5pwr-c4P98fCfsAU6f6TVdsGnRiuZDrG3-on_vF-_PC	2026-04-15 19:29:26.843989+00	2026-04-12 19:29:26.531159+00
4dc3f043-9c3e-4711-bc9c-8167690e25b1	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	DjKZsIBNGhqE_kGV7r_tY5vaNVXnb2X-qXf2dxpJSHpPsmKg_BzYmVzdsKewu4bY	2026-04-15 20:11:05.359438+00	2026-04-12 20:11:05.054295+00
49c91e2a-f05c-4b58-a044-c3d98d3d7385	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	aR-DRnVFFtWyI3rFbGGtaJAWbShdbV5cUBPQZ4bavagceqN85IJov2BwkTs7sDTk	2026-04-15 20:11:16.042662+00	2026-04-12 20:11:15.742969+00
3181bde4-b9e5-4278-8ea4-8365c55c1fc6	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	7aJQd3202vu0ksFZJ58H3jzXP71tWriGx7BZO_Do-EvtFk8a6glOawxOygxdp0xV	2026-04-15 20:15:25.22676+00	2026-04-12 20:15:24.925789+00
80dcf506-75b1-4c25-84fb-e4f1bddc06ce	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	m8EYJlMwSY0UkgtCehIK81NTsUBxHyAaRMkcWd-ZVtpNcMWO-sg__kqSemdUEAWT	2026-04-15 20:18:36.53237+00	2026-04-12 20:18:36.228028+00
253d3752-967f-4a5c-9617-bf0376e4af60	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	i5lBlEZlzmzn6P5JQe6tgiU2S8bjFHs-k85kelMP75Aa1SMMOIa4ldzN4EVN7h51	2026-04-15 20:18:47.160793+00	2026-04-12 20:18:46.861378+00
45cca237-16ae-469e-900b-e73ce33c8f95	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	yEhYlAyCtK26n-SUd_-nVS9jhx5FZLBybl61s-XpdNLAJ2_2LIM14dyeCVjelkSY	2026-04-15 20:23:30.413864+00	2026-04-12 20:23:30.110368+00
e39d7560-0446-40bd-ac6b-0f091d5065e4	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	xF6FxnhDabKCYvMtlYg21KmHIDlUJZeK6wg9qDzwXwOOJ1O2_-spUOQHnrcZjKSB	2026-04-16 19:06:00.585454+00	2026-04-13 19:06:00.27528+00
8c3e609d-a5cb-42ea-a898-a7cf27862018	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	e9ugGSe-kErziR-qbcCIEIU3VnsCRXYI64EuJ2l-5zKWZ4nagK69W5e88L1nOrt5	2026-04-16 19:06:58.827481+00	2026-04-13 19:06:58.517302+00
33ccf74a-723d-468c-a9fb-d460f7c3446b	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	glNOcjf_v1yTAS_DLw2Pu_61dV7xEL8IPmR_VvpVsCQqoH7PjB4zIaDKUkZDzOVx	2026-04-16 19:52:51.197771+00	2026-04-13 19:52:50.883646+00
1d82df70-47fd-44d9-a06e-222cf750e5d6	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	jdC4DHWAaY6nYzuFxqAnhW47jm99pWznXf_8azixlhC-_KAbcPW-_z4wrO0g2xhZ	2026-04-16 20:30:18.6628+00	2026-04-13 20:30:18.352706+00
c699d05f-d95a-4942-a7e9-9500a0ddd126	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	zt8k9fwLA73tuDg47afrafx5jVa_L2DmTMYESQ3Qbz19G6oEr2OfwzgQeZXyaT6U	2026-04-16 20:31:28.268532+00	2026-04-13 20:31:27.954896+00
aefc61fe-5454-42e7-bb17-4c28e8644490	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	rbCC5kr5gsnCzhcbwsSuxasWmmdEmwEiXR39k8vRPFW-L5dArFZ4Y-Co_q74YzSn	2026-04-16 22:00:20.846667+00	2026-04-13 22:00:20.513484+00
70b360f4-ea41-423f-868d-36f3498f50c9	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	SYI4IWpUT7XEtWa3S9mJy7F3ajA5FWMBRsPoIcd56F2TNC7MI6kBeyQiOG4WJ6L8	2026-04-16 22:09:56.979926+00	2026-04-13 22:09:56.673629+00
d87d0d28-c100-4d49-b7ad-d5f53ef4a779	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	uJirEaqzEcNr9na4eFrlQUlVIsEPZYUWZBprUc93p46gV4OcTKt80z_N1ECTeOJt	2026-04-16 22:12:33.970485+00	2026-04-13 22:12:33.658327+00
774f1a81-e7d2-4292-bf38-575337f5c918	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	E6GgpKUpcwAv-Kd1Y-TMmWJx1BT43RblVSyxBVKQbMc_oY3jNuucA1F9ONbATGjv	2026-04-16 22:17:26.938534+00	2026-04-13 22:17:26.625107+00
6746f99e-678d-4bc8-a84c-382d39436a90	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	AeVvwhfy9yv0cKE8U2VthJIYFLVvW3o5TbTs-1CGJdngyW7mzYLK8mc_t2WW4_wt	2026-04-16 22:41:07.959577+00	2026-04-13 22:41:07.641229+00
c4de118e-0b36-4feb-af83-341d7f26b8a0	522019c0-1a4d-4a7c-9969-723f3ed413c5	n_F_vhJva6AttyCGzN7l-OKKd0iqomjihTQj7eynY_YOLl-xF9-s4efvmLdcPNfC	2026-04-17 16:51:18.651369+00	2026-04-14 16:51:18.341232+00
d2abc7a3-e5a3-4866-9f0c-fe5e4c6c35b9	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	klaYXbzu8QjHSfFbyrvuwiv3srBbDomtGQxPV8GSQ7V9C1ytHf_uq3BcoSkrFDHK	2026-04-18 17:36:14.246734+00	2026-04-15 17:36:13.934768+00
048a5d8d-7ecd-4af9-b348-94faa58ca935	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	JSfTTmjdUY-zTiCjMhmdm6IaOmxXIm5yFYxE65LDD8zTAUFM9o7u64UzzCvigUW9	2026-04-20 02:49:28.477452+00	2026-04-17 02:49:28.162588+00
7bd582b7-bc3d-4ca2-aeff-ad9d04d162a9	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	wcmHvDztS8cZyS8JLJpwQDsRoUZ8o-R4SvU0Ms4LGne55CqdqDKKnOaFdGfSDqY6	2026-04-20 02:50:06.860779+00	2026-04-17 02:50:06.551295+00
119d03b5-5d7b-4ca9-a3d1-51cfa5823aac	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	HD8bhpwHg4cct8MMx6SrhktP5LrBgke-NkNWaqNeVT8hkPXhM_Br2_y7PfeeKe9x	2026-04-22 05:42:09.618343+00	2026-04-19 05:42:09.307396+00
84176c8d-dc97-4851-b1ad-b85007c97e56	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	T6bU7DTVluRnUAN5QVjvylABfbDE3yIZo4NU87TfH37EU2gcsyiHgHrlC0eqou4c	2026-04-22 13:43:53.107167+00	2026-04-19 13:43:52.801232+00
d4a4ca27-9782-46f0-9529-ae799dba12f3	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	Rs3O3FIt3kD5IXzWdVtO4a3BXcXePbZlAp9wtnlpJ1hcuLj4dw7hYo2bllxDUygj	2026-04-24 11:39:25.076077+00	2026-04-21 11:39:24.765656+00
a7fb1d40-869a-420c-9857-7209fd50e9f4	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	APaXp2LPuKBJrzxGEoiULg80XZh2_ve9qDyQDaTaCg7Wl6T_QPcK2OOcIzJpRjui	2026-04-24 22:15:14.252498+00	2026-04-21 22:15:13.890486+00
2cb7cd4b-723b-483d-a6a4-f8738fd96dd1	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	bgZV3AF7B3AiZdGE5YwBWhcpd12l9s4cnrn1NV0vGWYQunZFuPuXPCQk0GgOr_MS	2026-04-24 22:15:33.024527+00	2026-04-21 22:15:32.726103+00
dd894445-2d4b-4af4-b4b2-ee58dec4f11f	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	g57Zf2NRVMR5mfl3hVFkmXOy5d5K0dbJVLbeuLKzFasfg-kXBGeqxDlptx4OSnJi	2026-04-24 22:58:21.797798+00	2026-04-21 22:58:21.433548+00
439504e3-4f6a-4297-948e-152690bf784e	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	V505ZIQhXHZeuJcNNf6K_pHLsW4ohcyNaBPyVRvnIYvUTw3lBY2PMM7v8RSdFWYV	2026-04-24 22:59:36.355909+00	2026-04-21 22:59:36.052619+00
a1d1bafa-1f26-4848-a6bc-86e12efc9d38	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	VL72Nbu1LPpl0jpQkW8SRsI0BnroAr31u_cb-2gbwo-faeXe0w0uzTyTBF-AUROB	2026-04-25 01:26:16.240085+00	2026-04-22 01:26:15.931075+00
29a999ac-b1b3-4bf5-aae0-bc46e46d9d70	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	SfpLCdU9Hitc7LPq1HhmsMsIIEKTm3F9U8sOS4FJNIaPrv78k1an4kOJevgmMoAF	2026-04-25 01:37:35.577869+00	2026-04-22 01:37:35.267751+00
7950918d-68df-4e33-9734-96b212148837	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	5gkjoW9j2maUZ-23t1ijbOG04z9wscY5D04oZNX2Tapwfit2oEMzQSOFWCWp-a17	2026-04-25 01:38:20.266874+00	2026-04-22 01:38:19.959679+00
f6d7083a-a171-4210-86f3-176f505c5ecb	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	vHuB1FVlahcWfkxCdPnDCgtJQ5QeGhbsS_zj2kC89L7AzI9Z5tGlD6TiYBx2ccrI	2026-04-25 20:21:43.242587+00	2026-04-22 20:21:42.932707+00
011a241e-82c0-46ba-8470-0b7d18749d33	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	K5NL-LmJ5bLI_R7gI1Kt4ksp6C4LOZ6aLAaeqN9UIDBXXFv5gcYZ7gKf0gNgX-3Y	2026-04-25 21:55:12.149966+00	2026-04-22 21:55:11.842951+00
569ce67b-35b3-4760-8e9d-b9808e0ed023	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	w3YUGzd9zLCKEOU6FzY-WnaY9vUmdcR5cWv5g4XP2Fm9r7pLdLQmGFNZ0p9o2FEz	2026-04-25 22:10:49.722647+00	2026-04-22 22:10:49.40856+00
0199fe83-d4e8-4fc9-9e34-6f9514a37b8e	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	nO8SAzpwtIR-vaXmDDyTV2bXCS3DmcuRNGew0cHJLGWp-Vy_oYCeh2VkItH1ialJ	2026-04-25 22:11:36.629514+00	2026-04-22 22:11:36.323419+00
56c8fe37-1b31-4e25-b505-58f367ae8fc9	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	YKRIsYJlETLBQKadkrOuteNA1xBn9ORTJw9NmpHldDuAZmK7rZ2wHNmb_1oR29JT	2026-04-25 22:11:41.319922+00	2026-04-22 22:11:41.010967+00
a6518daf-c002-4d00-b15b-518c5b5fdfbe	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	vUZScWViLh3xvV5M7mT4R6q0AKErVYbKngu2G4KvDPNvnqpVs9_YouKTBWpsgUwQ	2026-04-25 22:11:46.187561+00	2026-04-22 22:11:45.881427+00
1320640d-931e-4f8e-a426-95c01689ef0c	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	0fHxR1Ztpbl4fhvCXhfSsu6T08agjFXGPWb1cpWwI12FMJHgiuE94SuT-qtygPtd	2026-04-25 22:12:00.193678+00	2026-04-22 22:11:59.880767+00
f5920e28-933c-4754-a0f1-fa518eb45532	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	YiKigFMB5eRvTZlGZxNk6T0LVpKZxZ4clq-q7cypdpAfRIuB4N8AUHun5j_K0Psv	2026-04-25 22:12:14.520259+00	2026-04-22 22:12:14.212424+00
e474295a-1fc9-41c9-ada4-27897110e766	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	iYTPjqkMdO6Hu7ZkSkuY-8a4qtAHcTEE8MgSRJmBlb-KLnCcp9DOn_ljYNHw69CF	2026-04-25 22:12:19.336521+00	2026-04-22 22:12:19.02913+00
11d4ba19-0798-4322-9202-f3e0b43b34bb	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	ctZxcPT0UzESnF2gLAvnT2IS4EkOxT3y5VcZyLp2S8pRFKzs1BGuP6_MwWIupVy7	2026-04-25 22:12:24.480588+00	2026-04-22 22:12:24.175123+00
db990d5e-f2cc-43bd-8cba-f8cd021a5ebd	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	CqHOmNCDuYqLfobYDBpak7-HNHYzgwfoR5TBRG3TFWfP4Gne5Xq-5EJSGP27YCkc	2026-04-25 22:12:29.339526+00	2026-04-22 22:12:29.024446+00
c2a7ce52-cba6-4b58-8c17-51cd5a9691fd	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	QvhNaup1A7Z1-pF-QhW2mmchrQzORs10LmwvF4nY2tvWIFKR9VxFWkPQmuMkPu6c	2026-04-25 22:12:33.437043+00	2026-04-22 22:12:33.129753+00
98072376-abbd-456d-93c3-c43ee273cc75	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	vejVGYoy6g5f677Qs8enylU91963SF5gMtn4ryvS-6AEUExR_EzKC9Uzev91yXOf	2026-04-25 22:12:37.846206+00	2026-04-22 22:12:37.538346+00
753c66f2-c7d8-4e13-b96d-ad22fc7050f7	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	FXpwC9srTcrMX71vLpPS0ZjYyiFgRf8IRMAUoAJfIGhbwkLcw4xC5vP1ftVI9_qc	2026-04-25 22:12:43.150932+00	2026-04-22 22:12:42.842506+00
a0f9e8a3-5e04-4b90-84e1-080370f3557c	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	m6XXp1yygFl8rT1GBJGD45BzRzdKULnv460QCgB2wRZZRWcYkkAM6l10aTbqaKuT	2026-04-25 22:13:17.112828+00	2026-04-22 22:13:16.805156+00
a4c41cae-7e0d-4bb2-9b0f-92969fbd0de6	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	YRbPWhJusWp7V38CEVRxhgAJVhEGD14JrGP6cUjSLLvXzNaHwqfUMn8I-OUISXQh	2026-04-25 22:14:10.06544+00	2026-04-22 22:14:09.753548+00
883af67f-57bd-4220-9d30-8f2434b6fad1	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	oRsbgFbVKWTBu-VPPF__X4g6XZNTg9peZForFXtTrI9BhwS21FVSq97lhvpt2DMy	2026-04-25 22:14:22.484297+00	2026-04-22 22:14:22.171337+00
4a18be93-8ac4-4455-9e63-991bf2f5d546	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	S-TORQd0yhazz7hBJ_MNoGIIluNgespQftW8Kp3Jc0NKalWJjoeFPkpyGl_hdERX	2026-04-25 22:14:55.394605+00	2026-04-22 22:14:55.088431+00
5f6b8dac-70d0-45bf-894e-0ef1cabdda43	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	hdCsOxOwO8upFN1r08HybCmMIwe85b2vx6BtaSAAJgJvOgakYgqWIj2gOrrDqhvg	2026-04-25 22:14:59.683432+00	2026-04-22 22:14:59.376207+00
d97d799d-e545-43fa-8474-dbf536befbb9	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	UrWEuBCS_QgvYxuMcbUaMzYnkQYaTazg3pPYb0lb3bmq7ElPbQKObgRD3S7UkaXe	2026-04-25 22:12:57.560915+00	2026-04-22 22:12:57.255341+00
580e6a21-7692-48fe-8396-2f4a71ccbbb2	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	yOekJLQuS7dn2W_mXQ8GCbQJEDfrQjpg-pgFKRSnF3IBn-KIoI9q1ZiTmsXYwaca	2026-04-25 22:14:32.375556+00	2026-04-22 22:14:32.065789+00
d7c7d832-df0d-4fa3-9404-c97aaeb77719	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	_KdqRwbvA7vZqAOToLxgzGVvAJmut9GT414btfmN788uhPtH4EeADwhf5gE27iFH	2026-04-25 22:13:12.421466+00	2026-04-22 22:13:12.114257+00
a571c10e-cce2-439b-8995-7df6fea1b258	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	TdyaN4hBbagRw8DNNLegtTFT9TrXApaBPCQg2gNOgiRnfOHh_BYNWQw0nYOOI7ws	2026-04-25 22:13:26.888162+00	2026-04-22 22:13:26.574929+00
bab25b6e-721c-4063-8af6-cc261b7055e2	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	BL5EDo4Qj_U0dkLFcq2ladzMH9dqA1BZ3EwtyWZ_gf8Kl4mHioSRwvMConfmU184	2026-04-25 22:13:36.696268+00	2026-04-22 22:13:36.387382+00
467363cf-0808-479b-be17-e30ebbc0479c	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	C7qhLUgZYNtcjGz7-ZCGhoWzEKREywfwzgH6fw7luOEdg7DyhvEkdWMi12cnQ5yM	2026-04-25 22:13:41.336143+00	2026-04-22 22:13:41.027349+00
da28dfe6-495a-4f47-b95d-3b6b5b09039e	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	JPF2YNX233RkNwSZOkJ2oUhvNjY6DZN8R8HQcL_TlrtBWVICEI4ZatYbSvqjgS80	2026-04-25 22:13:55.152951+00	2026-04-22 22:13:54.846515+00
11206f9a-6ea6-4482-acac-264fb6960227	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	CA0MZI-LZVC5TvhwzthqGuOrdfS35NYHLT-JarXy0fYTmfxjBK_AJEBg6aCAW9Vw	2026-04-25 22:14:47.580269+00	2026-04-22 22:14:47.269984+00
92ab2846-0182-4654-be5f-1f4d5d249874	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	GuWhw1JAVwPKHW7bsfeI6sTjqc42MXg_6iwkDkqpwZm-89rLrQWgnNLmOEIF6MPW	2026-04-25 22:13:22.0371+00	2026-04-22 22:13:21.728822+00
832c4eea-b902-48eb-9188-8e94bda7a437	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	L1NIzRi2t3Kgb_f04FosMoCu6i4JldMyYObSRZybf4gUyWlw9KVT6i5Sqw5jQM09	2026-04-25 22:14:14.790111+00	2026-04-22 22:14:14.4811+00
4e0a905e-2721-434b-aceb-9642c27f1c50	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	x34p9pa91MK4vQBlTKzM7bXoMVS1IFew-ijh31XfBNrqnvR-ZGeSfPVjKBx3O3T9	2026-04-25 22:14:18.405098+00	2026-04-22 22:14:18.089596+00
dd8eaac2-aa04-46fd-9f7b-35f1841c2c22	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	HyBSBvdhBWd9wklyiuY8F-1gLnjoO9Dp8UBflZDb1APVJ70gfUC3LPtureeNk-uQ	2026-04-25 22:14:27.743625+00	2026-04-22 22:14:27.438345+00
d82ed4d8-569c-465e-947c-3d2961836c71	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	1UrCk_SBfwdzYHvMQxmX5Th2xfbHDTQvtyCrngi-67CeqD0VHKFMcKjkR0nYsJXV	2026-04-25 22:13:31.951568+00	2026-04-22 22:13:31.644804+00
8fe0c533-8720-45eb-b8e2-1d03425c7d84	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	VwZm0WmQ09rBzVMY3O9HTwWt50cyOGSrmSdYf0tF50Zq7k2uxVTL3g8sAb2MeawH	2026-04-25 22:14:39.206744+00	2026-04-22 22:14:38.899264+00
b9591fde-398f-423d-af48-bb435f41eaf4	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	LfxLkfvZevLoTUCJ6heQrG_BPzKkI-z6PlF4i4NyS2zlqhi6M5bwJ0hvq_ZSZ0DP	2026-04-25 22:14:43.475678+00	2026-04-22 22:14:43.151633+00
794be8d0-ee49-4b69-b64c-3f3ea0c6d2ae	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	9JNjdnn5nSJ1fHr747k8VG3tYiNSPTBIKAlPTgfJggjxXTjs2T7mRCgXspVJGpVV	2026-04-25 22:18:06.772997+00	2026-04-22 22:18:06.463436+00
129687f1-4bb5-4036-8411-976ce361b9e3	2bfc2afd-252e-4117-99c6-54c803986f3e	94I2iV1mr8gGzh7eT1GCXJkWNnirNJe8G22ykGsVyaTTfOEk2UMOrxLwNZcNpUOK	2026-04-25 22:22:30.647762+00	2026-04-22 22:22:30.338762+00
9c4972ff-7b10-4003-b6c5-f60fdb189ae5	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	PvK25aXQJK0pAuaxbW5dzlkZo2KZzsx4EIWKfi0EUS4mXW0E_FroKIwwPUwlCtYO	2026-04-26 00:48:24.097279+00	2026-04-23 00:48:23.768476+00
e4ee6c2e-d536-448d-aeaf-03e5bff15ba1	2bfc2afd-252e-4117-99c6-54c803986f3e	SM4S2WCGHKfNzjznlTJgK0kl4guLf96L39NBkiN5Y6SqC4iU0noTLz9mXHsfxEiP	2026-04-26 00:48:28.55467+00	2026-04-23 00:48:28.245535+00
b2e60f70-2dce-4608-b54e-efa835028401	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	PSSyzPSlOIqH1jubj67diQY46Z80hsmuHUuD04GSplExOXEQ_oAxL2dbA5yPVfeL	2026-04-26 00:48:37.760012+00	2026-04-23 00:48:37.429965+00
df753ec3-663d-4d8a-ac8d-9115a15a24c5	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	FJmLGKQ-e1w4vPQfb_NgG4tAkwNOyD3fT_Qmqw2UziG_5QygRrV4uzSvHVBh38VQ	2026-04-26 00:48:40.576458+00	2026-04-23 00:48:40.266825+00
a3b6cc13-bf59-4877-b11a-9a63906e903a	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	51g96Y3m6OOZTCvQjqTvuKom7gbt5F7EHrSaYZpCnRWem3GWbE7if53uPoFVK-HE	2026-04-26 00:48:43.844884+00	2026-04-23 00:48:43.538713+00
8325afe5-6aad-43a3-b1eb-b2012f55c005	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	b_I0B1-1ZVCFR4eJ8-DDqJeDHqdFG7NrNpaXIHi1oA6DmEI4DJc2oKNL_bwXxaQ_	2026-04-26 00:48:46.762742+00	2026-04-23 00:48:46.4558+00
9e155af5-c9fe-444f-b2e8-7c28f7b684c8	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	jJvwCHis9T6pb5xsSYZTLr_DZo-dbd72nq6GkqP0KuS-MM-FywOb_rSprYj56YYJ	2026-04-26 00:48:49.910917+00	2026-04-23 00:48:49.603646+00
e44a6d70-9e43-4612-9b89-f265319014dd	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	mwTT3150dI-0TWeBuOXEicMFE6SjGaN4ktWSXd_neqvAXxdaydRyb8ki9TCCiJKw	2026-04-26 00:48:53.037309+00	2026-04-23 00:48:52.722395+00
a54247a4-d32a-41ef-9256-ea2897d04ddb	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	LeDkgDfVi1WFi-TkLfdUHg0DC65LlX1fLzSKxS9aAVyy8yCTXryQM23pBInEtphE	2026-04-26 00:48:56.06467+00	2026-04-23 00:48:55.757732+00
c8c465ce-12b3-402d-8209-cd091d1af3ed	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	BtSg4xXrnZPnhE3JaS1TFK6Aexl9E6xrVosEvTFcml3r7-SW002iI7WiJUlC29W4	2026-04-26 00:48:59.180168+00	2026-04-23 00:48:58.867594+00
081815db-eca2-406d-9b81-1deae659822f	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	uC0DSsXjxpZraLYl3q_ptOE9u_6rIjv5fa-6D8T2tG5hnnvXudw_vKBNz63wLgIN	2026-04-26 00:49:02.575328+00	2026-04-23 00:49:02.267036+00
35d0f88d-9174-4e17-8e99-639a77b7f51e	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	CUWqBtxn62G0mpwA9MX4XeYCqrXpQw70v_DE2SrWpTubeU-cUHn64yDciH_59491	2026-04-26 00:49:05.607521+00	2026-04-23 00:49:05.299895+00
1434e0ea-cea1-43e0-a35b-408b0c4975b4	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	yOGzO5pGz7tyUbRtFPsxcH4MbYFjmPoweyh_AwjsEN1gkfpwIE8SpeFHWmL-quuX	2026-04-26 00:49:08.814341+00	2026-04-23 00:49:08.503355+00
f13a9287-39c3-4a28-bcfc-55ff6e37ff4e	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	hcuCNaHSaclSDJkKG_m3HrfFPMUJY3ife0jpDRdoMycXSXun3W-NPuWvPDLYTJYN	2026-04-26 00:49:11.888253+00	2026-04-23 00:49:11.562315+00
a71c338f-4e64-482b-8c75-716f67096b21	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	ZJLaBbkoPKbUZDHMENFuxjumXpBOLZI8r9n5AXnaCVBVSZkDhU1fuQ5gYiLeNODZ	2026-04-26 00:49:15.272836+00	2026-04-23 00:49:14.966632+00
2b4c2c4f-7ca1-4ba9-8d8f-830964d57619	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	CFGzYWoo2q--xQ8NJZxcgfzpm1-xR80TEB3IIamXLQzG352a6K0yRDdYXvtWS9yf	2026-04-26 00:49:18.515292+00	2026-04-23 00:49:18.206224+00
26b80286-2213-4947-93d5-fe8a74e60835	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	YlWs1pPdJhhh4kfAFX2Ck-gkd6Dh8BANQem4FkLRe9VWvq5YLF9TcHQ2mc3_drct	2026-04-26 00:49:21.350671+00	2026-04-23 00:49:21.040113+00
04cf5dfb-fc4c-4143-b5fb-2f5cc024fee9	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	G5-g_6RGGW-d_qVYRYrBglSsoj1rHVHmilFv8z-KPL2z9nM9pEAuwfT7tqM2f60O	2026-04-26 00:49:24.382339+00	2026-04-23 00:49:24.073801+00
93156d57-bc0d-4ae5-b3c5-4ef8b1c3296f	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	hypaRrQniRh8rtwsY5SgtTsBVcID-ZYTl7jytwXbfO-nFpcdJsvbhvAtfX5et192	2026-04-26 00:49:27.626761+00	2026-04-23 00:49:27.318211+00
aeac729f-075d-47f1-9a69-1383d6b8e27e	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	L_m1prGq1CvXKessgWiVmQy9PL5VS68eC0HTVyh0ElSGOx5Ail-B5OlnY4-io40J	2026-04-26 00:49:30.497951+00	2026-04-23 00:49:30.190916+00
4908f21b-5112-49d0-83cb-43363e0c653a	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	I1YPXAbv3cv5bEDL2EyzJiIP0cQyNlBKglI_iPgZitN47hE-tXcflkXDvhgDgbcy	2026-04-26 00:49:33.59149+00	2026-04-23 00:49:33.281033+00
6f82518e-0f0c-41cf-a4bb-5f89171c71ef	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	tYyYgMQ58MuMrC26c83LO-Ln5QACZr4o3D6A47n_8y_hDeDY8syzhw_lrR3iHNT_	2026-04-26 00:49:36.705688+00	2026-04-23 00:49:36.395618+00
4a728973-d6df-4234-9348-6b79aad927b0	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	1BDTJvv_As2ZoE6StbfrtTVTL_MY_1LfV4GT3Er6x6kVJ8giU4pqDDR3O52Nkgxj	2026-04-26 00:49:39.67553+00	2026-04-23 00:49:39.368987+00
4e463ee9-7b38-478a-8fec-c19b74c7660a	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	8mFIipJhXhuAzRY8CSNi_u8CLFX6WbjhEfsV5PwZNFLm3D_zAVsETKXkD0N7i0NM	2026-04-26 00:49:42.656865+00	2026-04-23 00:49:42.351818+00
08d515b0-1ce3-4f44-a952-af60bc9b31f1	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	EqRnFWv5cy3f3Z06gku1-772a-SRPoGOWyABpHMFFL8rc0ycRALRs5Ft3UA729k-	2026-04-26 00:49:45.680997+00	2026-04-23 00:49:45.373945+00
690cc0a8-648c-4b42-95ca-de24459f5743	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	iGG3Ar2Vz4C383ubPBtS4FUQ5zSzomUOlhKizOhAAhp1pCj5aqW6V-2lrh3CD5dk	2026-04-26 00:49:51.449105+00	2026-04-23 00:49:51.141355+00
e44f5dbf-d88b-4e1f-87c3-094d7e080cff	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	jU_A0x01It_HKKXk4Z0U1rPx36n0-lR0ultyiXdGzTkxA5mlcPidzvb7Djv44TnW	2026-04-26 00:49:54.275901+00	2026-04-23 00:49:53.969557+00
30be1a9d-f12d-4ce9-a041-d07769623802	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	GMb2SNWKUyFMLO2OIuRfxu7BOtcvtyqHkVSjTxq2Oyd3sDoPAYA_Zh_1SxJT0E3O	2026-04-26 00:49:57.133344+00	2026-04-23 00:49:56.810163+00
9fb5641a-3e5f-4a12-ad18-4f9cc90ac793	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	Nbnu8aGQxLDzAbo34p_bW4Q7oTQTgW_WZ7RQzn8kdTEXLkUaYoN0Elh1OuDg_mOW	2026-04-26 00:50:03.129525+00	2026-04-23 00:50:02.823577+00
43ef0a02-16c5-4e22-b886-0672ac93f4ef	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	HXd8343FVnT0LapFD7OqCbFAheiT3KPj_NBs3mZj_O-_AW5MgylsXWy6C4jOjbEe	2026-04-26 00:50:05.742237+00	2026-04-23 00:50:05.430827+00
9400073f-00a6-47a3-acc4-9fe3324fb20f	2bfc2afd-252e-4117-99c6-54c803986f3e	QG_BLRlYEX__JNp0DNFmaJsGsh1yGA-Tclbea12MIlfDSdgkiCWR0I6rfM1JBIuY	2026-04-26 00:50:08.815037+00	2026-04-23 00:50:08.500373+00
d59a2b08-9188-4a3c-84ec-40ebe2f0b741	2bfc2afd-252e-4117-99c6-54c803986f3e	9fVEaJ-OEVm9zQY943uBfERpuPqLVHUN5IoC05O6SUIHFzqILOO6AOQMSHT0bnqs	2026-04-26 00:50:11.541417+00	2026-04-23 00:50:11.190767+00
ed158802-0cd9-4c66-a8a1-33f67ec75b5a	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	qhwKUa886yNNH2A3HermsPrqoSU8LqelNUmwENEnOVVEkeh3lPWxkEFzH4dX00pY	2026-04-26 01:41:19.854531+00	2026-04-23 01:41:19.54591+00
2fbacfca-30d5-41ec-ab3a-f86beb0c958b	2bfc2afd-252e-4117-99c6-54c803986f3e	AIn9k_aCFqHa97fo3NTPxuy__dFXNo28RRYUkKyTl_IEZyoNocHniaYqxBqdX1kz	2026-04-26 01:41:35.960373+00	2026-04-23 01:41:35.642559+00
18993252-8bae-4b72-8f43-3f5aff329d99	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	3Tv5zELUz5VZY0pbc_aNy4_HMYNOw9NbVWxxs3Nv-4QnEWE0fy2dM8Nu-eqCAPss	2026-04-26 01:41:49.09202+00	2026-04-23 01:41:48.78006+00
da6827bb-3a77-441b-95fb-2b9b50a75023	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	8rdCaQmVLPY2c5UU6HqrdemUolEh19AzXfKiZ_UZjqmepNgxlDKpgz8388IP_x5u	2026-04-26 01:41:52.801541+00	2026-04-23 01:41:52.492427+00
0944a55e-1893-4e71-b734-796c978c7cc1	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	WuDH8J13eiY5IUgcTo31gFGOzMmNjb-7eWGaZEqzwH1-c2NYj_EtlK0l3RAw5XyN	2026-04-26 01:41:55.948413+00	2026-04-23 01:41:55.638721+00
787db681-888d-4670-b84f-3f8ff8bb3b64	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	kLUXyWZ4OZTQ11h_OR--Ye5nYG3FEZ_PrjpftBOx1Ofjvnl6_3ywJtAuntZiRvfO	2026-04-26 01:41:59.572785+00	2026-04-23 01:41:59.261871+00
deae9e18-f1ea-44c7-90be-4a61f371b6f5	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	UKM4yVtTd-ScEJrBdmg-HHh7vwlngJ3QKL35LJPTIZR6ufbeXwnS4nSCqeSkdcyt	2026-04-26 01:42:03.2631+00	2026-04-23 01:42:02.953953+00
eec51682-4ff8-4631-8b4a-7f1dd3911665	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	3cA7vr0XvfdlkXtvrXLgg4RySxf052rvYfwFkw6RJqWnl71in8DcaNbaSVWdLL_I	2026-04-26 01:42:07.487826+00	2026-04-23 01:42:07.180867+00
ebd63a7a-96bb-45cf-b22a-dd5f995705e7	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	zEKi5trKeWSt99aKO8QEV-J_n_l-n__Ia2lVocKLY-FBiMZqbDXBuGc14x1ch5mx	2026-04-26 01:42:11.241064+00	2026-04-23 01:42:10.931994+00
b7182eab-bd67-4cf3-b468-c115c45f77e5	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	C8OKTZ1SIyvg2SOQLFqXvlEGfuDDr788YDUPGZOyNOIHXF4C2JCbd6wv8MaqRC0T	2026-04-26 01:42:15.02137+00	2026-04-23 01:42:14.711293+00
0f5e8aa3-b0c4-4389-a26d-a12ddbcff48c	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	q0P951WoOSJc39me69vWNCCzSdRS3CFcjQpz8O9mYnuXHCfMHRr6C9hKxutQ_lRU	2026-04-26 01:42:18.114435+00	2026-04-23 01:42:17.804459+00
30d4ab4f-079b-4f81-95cf-fad233206cb9	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	zh2H5yts1lEGwuTTmx19qM8UzcnvNpAaZ2ZTqdx3skJfMPFjVdFwu8DmBpW6Q8TH	2026-04-26 01:42:21.508245+00	2026-04-23 01:42:21.199352+00
f66d9e9b-c958-4873-bbe2-e426042377c3	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	inv5XLt6u92V413JwUKQ5jvJOOAR55qwGXU078pdmUi7etzvitOSKQYrerGVFmlA	2026-04-26 01:42:25.736806+00	2026-04-23 01:42:25.429285+00
bccfad79-3b06-4c68-a757-8a98861105ad	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	U2dnaVEiZTIN2g8vl56mf5crSiGCwJh1jPJWZJeK7XwopkcpU1dIfd0GJ05mQgFk	2026-04-26 01:42:29.872691+00	2026-04-23 01:42:29.566986+00
995d6604-40af-4712-9af2-80968ef91123	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	A1gC9WjJzLGA18IQ7xn5kNTW__LqipQKnMX2Am86Xehyzm5Q3LO5u8vQrvh6_y78	2026-04-26 01:42:33.616044+00	2026-04-23 01:42:33.307367+00
ffbde039-4440-4f85-9011-461411ed599f	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	1ILveHV_NX7ZPOnPg-aGMI-H90y59HKCeN_ykHqJzbyCHnI2tb3qYJ3qY00Pee1F	2026-04-26 01:42:37.937437+00	2026-04-23 01:42:37.594339+00
a8ff2d24-9ccd-450a-ba26-df0715265323	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	PlyIBpO9S27KhMSzMcDIAfqGfGJOHqVtCy2o2OkQkxAf1JNbyf7qB0odOYjnATDa	2026-04-26 01:42:41.838696+00	2026-04-23 01:42:41.527185+00
13ac39f2-05e9-438c-9891-7c90b344cd61	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	S52ZYcVloCZddgNXZvkNlv94q3hItUMBSroIbS0jZpHtULC7oc4o9Io7QroVuEqf	2026-04-26 01:42:46.506442+00	2026-04-23 01:42:46.194711+00
435b5fd4-54b3-4468-acc3-5bdb01973405	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	w-Ag4zh8zqUnKAP65gpEjJBBR3-RX7FvDCU9QgyuIr01hlMtrxjvYpsXI91R6omn	2026-04-26 01:42:50.790393+00	2026-04-23 01:42:50.47754+00
d3c1e218-ac44-4d9f-839d-02556fdc97bd	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	rLZBxRBmcSq8NqS1s5KB1ocxaKM2rnIQI9SYtzQmbYRPCsazUu51ptvbOjfpAEBO	2026-04-26 01:43:09.42023+00	2026-04-23 01:43:09.107997+00
6ef2f21a-5140-4ffe-bdf5-3ec0b0075644	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	nztsWawDrNziv4Y08QcpIVCjPpp7x9Ia0vASX787yweCzNwicI3yp4yVINUBuhJF	2026-04-26 01:43:12.83592+00	2026-04-23 01:43:12.524151+00
a6784766-3641-4cd3-81dd-986cb58e1326	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	DADmFdsHexn3bOlJ0Tf2FDTcdJU6OfLTUvHL5DBmrqmUR073Ah26FNgzQr0oOFUy	2026-04-26 01:42:54.412737+00	2026-04-23 01:42:54.105127+00
af5b0213-12b1-47ce-b6e5-6452fe556230	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	uS4fOEshyxAO2YbXKU5uXv1E2Dh8_740i9Qzt4ySK8AvaCEPsrW2GBXrZ2TPhh-k	2026-04-26 01:42:58.376337+00	2026-04-23 01:42:58.065187+00
050d2ed0-d649-4d99-8f4e-d3f3732e0704	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	bQYPTCh_UCot8yJwf2dktv2Q60n4SFakNV4kGwwaV65vGw7rH2xGkutwHlj0ymtu	2026-04-26 01:43:02.626821+00	2026-04-23 01:43:02.316785+00
f26094a3-0041-4dbc-b07f-6cf32792ac05	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	LVhGuIhvgYyP-ZZFHQDeewiGfvqQL0xdQRElXdIpvVm7TBjy3GwKg1qYy8UjDoIm	2026-04-26 01:43:06.368863+00	2026-04-23 01:43:06.060572+00
87872c05-3ef4-43c3-9fa2-228d51fadfca	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	dlL83-7YphRPEiUttSFFz6y2Ejb9yNpRNgGQFNddS4as4xi9g3nU3l9RpgftXQDh	2026-04-26 01:43:23.718718+00	2026-04-23 01:43:23.395203+00
6edfa0e6-9a69-4feb-a255-08bc669092cf	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	lXx1i2hOC5CPs0I43PRcWAabb0IAo3Qj-FpPdm1lf1rEKLsdbxMYlO_I3fXKlXr_	2026-04-26 01:43:27.444181+00	2026-04-23 01:43:27.136303+00
5d86040b-c364-4b29-9106-d2eeb783b7e6	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	tZMm1fbxTpgpBndfSIIeJsNixpdtSlEr6a21sOeDdt-ktzrZ_D6LI97pRCXQ8Iiz	2026-04-26 01:43:33.977432+00	2026-04-23 01:43:33.669619+00
ed782a95-a779-4c38-a819-12780867321f	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	Y1KpQiFAF_RMKzVuJ1pMAwdlW4TrgCRfNJSwxIlnC5awwgqynlioTT3fG4HOkwJu	2026-04-26 01:43:19.537515+00	2026-04-23 01:43:19.227028+00
d6745407-4bba-4508-9450-c54e8e942191	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	mQylLFlbzZCfa1JbNMkyc24bOpsOlmzl70f3_vRrIvCc-_GoSRaLmnWzkaHuGATp	2026-04-26 01:43:37.796193+00	2026-04-23 01:43:37.486962+00
92465452-4a5a-47d0-aabf-dd8a7089ac2c	2bfc2afd-252e-4117-99c6-54c803986f3e	GMp-gPiopVFQ1E4_WoiRGmxjy36pOSRkfDwCJysa26xW5omKPe-0wT_Ck_aKvnRX	2026-04-26 01:43:41.555948+00	2026-04-23 01:43:41.244827+00
91ff9e65-ee65-404a-aef1-ba183037ce45	2bfc2afd-252e-4117-99c6-54c803986f3e	r0rLKv-ff-YgTv3iLnJ27YrF6lGRKhnAc2f5vsK1biLcwRMwmxqCchmo5fKvH51q	2026-04-26 01:43:46.103359+00	2026-04-23 01:43:45.796194+00
93163afd-0ce5-41cb-8835-64ce867cf8f2	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	YnCrXkqC4YsL5jZ9jn8UpWIqJzWSnrJQtqf4Z_XTe7x-7xI-BiVqjaOMBN8hZGmJ	2026-04-26 02:43:05.870851+00	2026-04-23 02:43:05.561543+00
ea764f08-81e6-48d8-9cf3-5085c7b5918e	2bfc2afd-252e-4117-99c6-54c803986f3e	Sa7AYNtVFaK5UlKFvauxXlD9JrCGs7Y8fvJlOvNrTsGaGLlQ_A36PHrnPVGAHp78	2026-04-26 02:43:09.984175+00	2026-04-23 02:43:09.676972+00
a6b05824-ef62-49c5-9dec-e8ef97d3341c	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	fxaiDV446gt2iAtE3g5xfOOcIbkZ0Ml2oqKZdZqdaKkT2lJBrsO3OMSEyNRbEjqF	2026-04-26 02:43:35.852227+00	2026-04-23 02:43:35.535356+00
6b6ae948-ba73-45ba-a4e3-2d6a6161ec62	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	UpSYAvhGVp2FG_vSDVapy7cZjgIFCEEh8KQG2wy-dptRpswRhKVUjM4_ssGrQX9Y	2026-04-26 02:43:39.230347+00	2026-04-23 02:43:38.922869+00
4fcdc980-21d4-460c-af7d-38fff71de349	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	SGsIJZ4TDaNbQBeqkLlqMpHSbVMRRbqQK_4jvozUwhWwZ9dw039hgC7Zv7nkJso0	2026-04-26 02:43:42.671687+00	2026-04-23 02:43:42.363465+00
58c0f369-0e75-4909-9494-64d7bc86d09c	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	Qrb3pWbY5ZWIZNOcmmfAdnuVgnNkzQsvBl_PZ7QHuG9Xjl1GNr8QRxY3B2WcmG7q	2026-04-26 02:43:45.684595+00	2026-04-23 02:43:45.375066+00
ccd403d4-ee45-43d2-9596-853e0037512a	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	u2dkjJVXO-s1Z5cego5OjFsI3ltZlwjGNVvH6mSur5-yL7nD-M1KFOn4ua3CEnH2	2026-04-26 02:43:49.243639+00	2026-04-23 02:43:48.934666+00
c1553b92-24c6-426d-8d6e-5aad5d7efc8c	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	WoqrnLSBTH5wpGTo__jAnD_1ccXgB9teWGYb6CW14FtBGb6jSuqClDYIkJ4tURxM	2026-04-26 02:43:52.343278+00	2026-04-23 02:43:52.03139+00
0b83528b-c85c-43e9-8183-742d69d1f3a2	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	LyMT5wJAYpLBwmqkHJbaoQvkASWb8wLnqDtOS_yxjvAGr9kZ6PSMNtnzMnd4qRBc	2026-04-26 02:43:55.83027+00	2026-04-23 02:43:55.52247+00
e2a79df6-0e48-4b2e-95ab-259c3be27db3	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	ZcQadW-24AT2rLziO0Ha9pdIqwMZgjUBEyIamcO9kQ5IkQjPPh0ROY-BRiswUITI	2026-04-26 02:43:59.369589+00	2026-04-23 02:43:59.059388+00
532328f8-a370-469d-a402-848287595d5c	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	T4h9F2Ypkf_Lh-S8FVtze-oD89eAJMqaTZG7pSQZBbNjAPgVbIATHTp0RwYcMI-l	2026-04-26 02:44:02.852468+00	2026-04-23 02:44:02.523411+00
4d3ddc09-ae84-4977-9f7f-665700f2d0f2	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	q_v8VsoHkQNTE6Mac0v4Fuj02D33Koqm0__BInaNFTiytP36fCcMuVZItIENXUvt	2026-04-26 02:44:06.04212+00	2026-04-23 02:44:05.733494+00
892d4b3d-0f4b-4a38-8392-2b9a45cbe4bf	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	QiW_PWnZQshcA-EIUtPPLTKBqPQ7abWGCduMy3NYW-zeNRlNAzc0wedIWUvY2Jt4	2026-04-26 02:44:09.212819+00	2026-04-23 02:44:08.904003+00
43f33dc7-6129-4a64-82e8-fe4df5291e05	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	4ixfLpxKyhDPhuY8WYapKbsmbfLc32MxIx6GdBKa54F-waKWDKccoi2SY7-ZpABL	2026-04-26 02:44:13.154082+00	2026-04-23 02:44:12.845293+00
30ec7e2c-7d21-4807-a3ce-53d60387a18d	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	P0NV53gkdZ3up7MmsSfUgoIJYgBoynP6uiid-IkNbNEk0JXUlZ5yOpGoPLUwVD6P	2026-04-26 02:44:15.894583+00	2026-04-23 02:44:15.587691+00
6c44a1cc-5589-4e2e-8774-1c388ccbf82d	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	Swy1HXLiakXEyH7-yLb0-T_NTmM16P4d7raN3IRw0ol7VuqiucK6L5tpG54u33z4	2026-04-26 02:44:19.57769+00	2026-04-23 02:44:19.253567+00
1eddaf76-5ddd-42c1-b87b-57f96325283f	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	0Etp9BOVT2wPTSfacRlhLBOyCtgXKiCiGUKbB06x35yuB6tC7SduNHKbCZdrpLii	2026-04-26 02:44:23.306071+00	2026-04-23 02:44:22.999947+00
c5b001aa-3f6d-44b0-9c97-152253495032	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	0gHCEIEcfK3ga8gTwn59qQWJSiWgbPuapbxFvlsAgaSHsxCpe6DB-Nq14EHsghNs	2026-04-26 02:44:27.276131+00	2026-04-23 02:44:26.968515+00
ebfa228e-060c-42db-b921-92e3a4a78be5	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	2S02qrKoz--zVsGiUaLUBdn4L2cjplORrI5HGrgf_DYshmTENty53iKXlPal7TyJ	2026-04-26 02:44:30.407492+00	2026-04-23 02:44:30.067384+00
3d75ae18-5f5a-4a08-9e13-ff0fd729b4bb	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	PdVmyZvDxRXGLpY7QN5dNpiWA8il6zEg_6fJmb3QszVXQcbGsiAkG_-i95qhP9-J	2026-04-26 02:44:34.250704+00	2026-04-23 02:44:33.942027+00
250dc678-7804-4315-b88d-c0bebf7cbd1a	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	AZ2Uv37jJrz2yhqvAYZNv1eKv7EmbqSgmIhvbby6maMCG-ZMLg51aA58FESK38ct	2026-04-26 02:44:37.512233+00	2026-04-23 02:44:37.205143+00
9ecfc1f2-359e-4764-b81d-050240816d65	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	XA5UHRK-il8gg6l-FBiW1-HvSuzgffL_0Eu2LDnipXIdMY4feKTEKn7GtU1oeE8g	2026-04-26 02:44:40.550505+00	2026-04-23 02:44:40.235381+00
924b543f-3489-4f91-96c4-96aefc1e5af5	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	XPRFOppLlbroa028p0x7lBWmVPIdhcM8YTR-ZRpXIJLCHmZ0yYm-uHQwG4tVLqSo	2026-04-26 02:44:44.46179+00	2026-04-23 02:44:44.151807+00
d86a3fbf-fc5d-4b48-bfac-a84c31364a6b	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	Qr9Gp1aMkSYSiYlUDvo1OWSWdRs6lRTS8u4TjCNyveNutOJnMY35dSar2Zg2ko87	2026-04-26 02:44:48.174288+00	2026-04-23 02:44:47.864215+00
8814865d-8051-4645-8f42-48f3e135ef69	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	PDZk-BK2K0Ic2QpFdtRfCA3cAS9fLuPg_zjNMEvxeRKcHT-pM5RHdfeNAn0wdVsv	2026-04-26 02:44:51.165948+00	2026-04-23 02:44:50.858549+00
26445dcf-dcc1-4767-b2a7-949cf1de94e6	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	HUtY9JMR4qqPk3IIrP0Ltcv8NN25P8Bh-O7Ysc3rKpJ-Ih9WQdq-v1eYa4ow8hM2	2026-04-26 02:44:57.322821+00	2026-04-23 02:44:57.015308+00
b80be8c0-f19d-4df7-bd8a-3b0dab99b49e	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	WYOq5I-n5mHa5fwfjqPDnDxcLo9NfD-jcK2kGB1jwTWqNhEzVvMVqd6QRnGap15C	2026-04-26 02:45:00.323585+00	2026-04-23 02:45:00.011434+00
40a06c78-1a31-4a43-a2e8-28e5acdbc325	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	A3Y8BOh2A77ycmRTKCtpXZQzxpuX-Gs32_KwDziiTuNB5TnrZ2Uv0xHS0CFaj6Gu	2026-04-26 02:45:03.665217+00	2026-04-23 02:45:03.355363+00
3e8ac916-3aff-483f-9451-30d15b67e27c	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	F8LbJSzXMyWilWpokJ7ItdSVUcctH1A-h1iYsL2LEdzp12oVlJC0FOvpk8XVyHqd	2026-04-26 02:45:09.968122+00	2026-04-23 02:45:09.655336+00
7be666ce-4cab-4f0b-9e47-d3d28560c133	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	-BnhAFk2FxQraWqCg3NdW3L6LQemNeDcZm2xQ8j0UtbBub852HlKfiAgD8pmkDnt	2026-04-26 02:45:13.904406+00	2026-04-23 02:45:13.574252+00
ed38e153-54d8-4006-9380-cdd41fb7accd	2bfc2afd-252e-4117-99c6-54c803986f3e	xhayXt4FbpGFZUkB6mA1xC4lz6MEewXAyJYdFLm-epvFxD8h-bowSnKjYkZWhqVr	2026-04-26 02:45:17.559405+00	2026-04-23 02:45:17.252481+00
59bc2a53-cefb-4655-aaa3-86d68358e3ff	2bfc2afd-252e-4117-99c6-54c803986f3e	z3JGz1sOBow9Ja4onJR5VpT6itfRNuGSAOl2OIjoKpCODN2LHRHKk86DAVg7kNU9	2026-04-26 02:45:20.88811+00	2026-04-23 02:45:20.57937+00
e98de769-7b03-4747-8c3d-f38a2f408826	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	k7t49D80ciP1tm5Aix1zgDGINURemQP5zkDxUUMzghQDPUpKwkIWAeTm-z680g38	2026-04-26 03:07:48.815977+00	2026-04-23 03:07:48.499409+00
244cdc26-171f-45a1-a3b9-4caafc4ea241	2bfc2afd-252e-4117-99c6-54c803986f3e	y4mmIKlJ7Z4DfYR-9odInFU-s7zrm-zBDlJvbzjKrHODI23tFtYfdE-5hc2NXj_Z	2026-04-26 03:07:52.703437+00	2026-04-23 03:07:52.395596+00
842f799b-fae3-4886-8655-59e7b446aa94	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	WQyRaWKGJYSHWV1eaQnagp3l57TccWyhFXiMCesiYljKeJ20djHIPd5rlrts3czk	2026-04-26 03:08:04.730839+00	2026-04-23 03:08:04.42195+00
ba4f525b-3eee-4e74-b889-835f503799fd	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	QSqiLeWsGwl7lxSInl1o9gTiuGaMIqdMPxS7eJQOZkHXx8AOSL6R2MdZ4D-e4dCL	2026-04-26 03:08:08.733867+00	2026-04-23 03:08:08.424586+00
5388fb4e-765a-4178-ac1a-c88829150eec	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	VP7lwYDpTCNxTvkoirnEaQJTb1bwAaOb3EsRB7evcVLwfkNe1irEkM8cghDlkj8u	2026-04-26 03:08:12.737886+00	2026-04-23 03:08:12.431638+00
5d7a7a09-1211-4b33-933f-69992bcdb962	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	C1qthz44ngrYv5dJ3OduR4u-E22u12pz0mV1SyiNBNV1Of7aytzqSEXME_ZC70B8	2026-04-26 03:08:16.788535+00	2026-04-23 03:08:16.479921+00
8abc38a2-6655-45ae-8abb-2b406e02b059	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	QcJOq0JSJhWAmqi-fTlG563OrFO5Dhvgbyxkx_U-svyvVrcjXmiM5K-BIO2wucO5	2026-04-26 03:08:21.323853+00	2026-04-23 03:08:21.009783+00
e94c8999-7c0a-4903-ba60-574395eb117a	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	4opLe2-h8l5Y40Ej-Y9P-5roglpLCyY8e2z5NEmxgZZp1r0qTOucaqtEFvTWqltr	2026-04-26 03:08:25.391896+00	2026-04-23 03:08:25.081926+00
fba44e76-b0d9-4966-a1fd-94211afebd02	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	UxXI0bY_2VwcP78xd3gNMPFGPrkphOkPL8lPNecmHtlyEa3n7z37aKzQKou1ddko	2026-04-26 03:08:29.229938+00	2026-04-23 03:08:28.919308+00
df4ab665-e3d4-4fea-9f8a-49bd1b739a4d	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	zB-M3xEjUn_QRrcKNjQ0hL4VS1R459OyFQoWIHE5za4QtUF0emMHhYWr0Hn9xmOt	2026-04-26 03:08:33.106624+00	2026-04-23 03:08:32.796719+00
d09c3298-1a7c-4be0-b99f-b13ec7c8eda6	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	ChdG3UvY_BfvLOGYHGwL6JfAzLuVSb0wHejJ1ePCdgC3Y-Q2T0JkhsVre7D-lK0_	2026-04-26 03:08:36.665924+00	2026-04-23 03:08:36.357953+00
ebc322c1-f591-4ceb-97d1-27244d2509d5	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	BiuLExjN9Moe7sN12caDLTSWFRzspKaxJpLMdSgSaRF1CZNLFspv4W1Zjrm88j4v	2026-04-26 03:08:41.060205+00	2026-04-23 03:08:40.750228+00
86d4cba4-d6ae-4579-8cb3-9da59299c5ae	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	eyh6EDM3G_vxUR6bYC7kKO7cyK8AXHiDqKTDO4K_9gYKhA2i18NaEdnQro4NptUf	2026-04-26 03:08:45.115045+00	2026-04-23 03:08:44.777389+00
5eac16f7-3344-4196-8023-6ad2243ece40	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	XvG60gpRaYaSyJyhQ2pleH5Qo035vBRkK7tfDRJcSu_HxnJslG4dvZaEmYprgsqm	2026-04-26 03:08:49.948212+00	2026-04-23 03:08:49.640763+00
020e67a3-2831-4390-81da-d6f6c18a6bd8	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	an5Wjnz4Z_GbgdlkYQP-AAxtgnEXVpZSe93Op4M04MX_9mNQ3gS0dqYbaMWWAl73	2026-04-26 03:08:54.952642+00	2026-04-23 03:08:54.641264+00
c34ce54c-4a1a-43d4-be74-7ef1efadd287	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	58zn4y0RNjRskkjEenbxpz55bpu55hAqYuaSs-jdeKi1uAYH-KaOUTHtN2TDIsuf	2026-04-26 03:08:58.8049+00	2026-04-23 03:08:58.494989+00
bac11131-baf5-4073-8847-8e121b5a7836	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	Xa8Rk0WT7pwMn4Fw5Bvsu2qIpIWRFtLlBe-we__mwh1v_19SPuXBJ4_qUMg2Oja7	2026-04-26 03:09:02.887001+00	2026-04-23 03:09:02.579306+00
60ad6f83-1f24-4ebc-8002-cfed4ba84a87	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	X-QtR7RC1CvWUjP3Vxp27SW9DN0parbrzALbUkGylWrROTjoOg-QAEpd52CDpHCN	2026-04-26 03:09:06.648401+00	2026-04-23 03:09:06.338493+00
61215d99-b738-4050-8568-b859651d55e2	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	xWB-Uk-zUTUbw0PUD6hj2kx47aZw3I6eOIEFvLrbZ2_i48-meHksif8eN470GRdS	2026-04-26 03:09:09.813214+00	2026-04-23 03:09:09.504608+00
796d02a8-56e1-40ef-bce2-c8169f97fe8a	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	xjqpdn4Ieltv9WGYELNvs-YBGYh2txiZtxUuVeP-4GcZbUlaO7AHf61faVt_uOFg	2026-04-26 03:09:13.898162+00	2026-04-23 03:09:13.589207+00
09af9c08-90ff-46b6-997f-57da79f85f82	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	Y1iKYQsHcYevEDXzkUKBsITfNGH1Yk7viKXmfdWFuWQmK1vQ2VRSNKVzURxmYjYS	2026-04-26 03:09:17.702782+00	2026-04-23 03:09:17.396308+00
5a603a4c-bf06-456f-b61d-1e030a88ad5e	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	XX5USIhn5WzGHLHPc1TmhJXfI-utJyd9xB2l8lYzMisieEsaBLSkWb07vwbZAK-7	2026-04-26 03:09:21.832618+00	2026-04-23 03:09:21.518117+00
be6615b5-f4ee-4b22-bb2a-8285a4dd6f37	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	X_oLVd-nqamvIQOZh2DTx1pWIr8pbRgrrFPzLdxuKbDFvaDAKmNmMMoURkYKRzVe	2026-04-26 03:09:33.782797+00	2026-04-23 03:09:33.472458+00
cc849567-2a0b-47a1-8d69-9302ff061772	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	-JLeu0Yck4X1xmwO1gXk1IQ2qK3U7nebEq8r8_5ABcGXAnOsbNkH3Zx7bFEvPx6S	2026-04-26 03:09:25.81623+00	2026-04-23 03:09:25.505885+00
147803cc-b27e-4854-8898-2f3df4ee5c6a	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	hCoPudAVpX41WvAqm8oTN_IqesV1XXTbwzlCRD1YF87zIgF9zvbrYvu2YXUNVHoG	2026-04-26 03:09:29.823587+00	2026-04-23 03:09:29.513261+00
a93ae6bc-d264-4936-bbf4-4ad5e713b0cb	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	-lQEKg9xlt4VJkyQshScU_VAdYLmHctHQ98oKxXfWwVt4nogi4CIaXI5q135H9DP	2026-04-26 03:09:40.76364+00	2026-04-23 03:09:40.447297+00
3bdc26ff-4a78-4ff6-b793-e1a30069a2a0	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	HXF2C3dRTlY8vSveU2XGq41UyDv68S-DYP8mPFxuicy97lMNy6mH9LN900_abAI9	2026-04-26 03:09:44.377697+00	2026-04-23 03:09:44.067978+00
54eced8d-c76d-46c6-a39d-fea29296b898	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	K6xPlaI_buSBia5uUOCMHtkdNyYnsNsTlvJPBxKGX7OJbSgl4ADIWECt5X5E-GWq	2026-04-26 03:09:48.078544+00	2026-04-23 03:09:47.768239+00
57ae2c3a-10b0-4acf-94fa-e99ff0aa8d90	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	6Q-alYAWWxsy3fSZ5CpH-DOWuyt3DBXRMP4PNxCU56oCyF2DEUQnRy465PslLhtt	2026-04-26 03:09:54.661296+00	2026-04-23 03:09:54.354189+00
be364e4a-9be9-4959-8b1c-6b61a3b96164	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	Y_k1L1r2LsTrYayCvi2fR2Xk4KMFwkjSCmmTaHBBoqbsgmeH0S-vCYFJ6FO6N6Qk	2026-04-26 03:09:59.231396+00	2026-04-23 03:09:58.922963+00
5385db99-2683-41a1-b687-9561aeb90605	2bfc2afd-252e-4117-99c6-54c803986f3e	R_MMQ3U8phyI6JiLb0YuH5fN-gi7Br6S4eMW8nQrbFL10fuIsG81Ietlnc5RkoJc	2026-04-26 03:10:02.916238+00	2026-04-23 03:10:02.5869+00
f3b8bcb9-1d85-47ab-85da-7c00e498c3fe	2bfc2afd-252e-4117-99c6-54c803986f3e	kkgjZGfZnvtkmKH61yHlhUM1u8X4ejOsIFgB6aN7AfuQXIPxLPtY_sFYIdltHHG4	2026-04-26 03:10:06.58928+00	2026-04-23 03:10:06.282686+00
6a82b6f8-cc64-429a-abee-73501d589148	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	Xs310HXedxpo-SLSOql0YIEQbkYNijTbNsnt_pJwOIf04m_pbeNyzxc4KFRtmjd8	2026-04-26 11:29:20.118041+00	2026-04-23 11:29:19.80465+00
106a0d68-79f2-4c05-82f5-16d6676836da	2bfc2afd-252e-4117-99c6-54c803986f3e	qA9EEnTkK56LfOIriHL2iANV3VJcpGTruP4Qp6P5zvEKxneOGzw1R0FezbxqtHix	2026-04-26 11:29:23.742811+00	2026-04-23 11:29:23.431176+00
b6a72d9c-7cab-4f31-b44b-1eb52ca5fce9	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	6K22g1qWlQLo3gKF2D-lFpTgzK1niqNmJuf6Ay_lRz3x8rA8kLjTr_Le7hVu_MMA	2026-04-26 11:29:34.579658+00	2026-04-23 11:29:34.272885+00
95a746f5-d9a9-4cde-9bd0-ee08d54a1bb0	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	ovN7-7h-1A8PnMi_2IRlSYAZwGdBhcFngUnoAFBjiVOzqISsynmv_JDi59GoVG5x	2026-04-26 11:29:38.285678+00	2026-04-23 11:29:37.966505+00
06c4eaf8-4dd9-46cb-b1be-ef3c1b10ef90	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	3Zuxw_3Qo0SHJRLqDhR57bs1SFZfFCIesrjWmPO8H-k6CgaldtcRIvrWSVEfW4j1	2026-04-26 11:29:42.505646+00	2026-04-23 11:29:42.198058+00
78472fa8-c997-404c-bd2c-0c3b2fcfa9f1	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	xur72l30MSW87qoB049td-f57Q81dNkEApIEubZMqYeSQHzNNF4VimbgT6ihrsxw	2026-04-26 11:29:46.043179+00	2026-04-23 11:29:45.736724+00
fd9f7e69-0bf5-4934-83ea-6e3e78cf2559	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	wb1q-OdRZbIR2u9hNTVY40z_gejNKIinbhLueVirG2voVeXG6HQ6Ui-__Y3_SQ19	2026-04-26 11:29:49.8196+00	2026-04-23 11:29:49.509196+00
ea01bc40-f042-4d23-bbe3-95eb91d80864	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	KbNHF4dNq9Hh0GoGPUNYFHfjouMXruimK54K5A_ambfje-l8tLRf00JJxRbqGzxi	2026-04-26 11:29:53.152211+00	2026-04-23 11:29:52.842768+00
8147e4af-d112-4b69-bf65-0ca34ffc3e40	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	gQw2T7ybOXdwlJVIhCijyx5gh7rw23Pv5reRBaXHyF5W0d_n_47APKAyp95RSD8m	2026-04-26 11:29:56.588881+00	2026-04-23 11:29:56.279401+00
11adff7d-c1b7-4a1c-a950-01993584330f	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	9H2NO-WxtpkTHBB7u3TPN6yHwluxi-POjgLe_gwy4MQP3_vrFdmPYpAB8CQeoNjJ	2026-04-26 11:30:00.534933+00	2026-04-23 11:30:00.225475+00
f7270637-65ce-4154-805c-3ca97319532c	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	yh6VoWh97up8m3SeaJBo1sgG9a_twkiJ6BCHvKsc3hOfhU5wXlXiRDCNTUClmlSw	2026-04-26 11:30:03.809308+00	2026-04-23 11:30:03.501118+00
832a87f9-fb60-4fee-8a88-21ad7da7df9c	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	yHahd3StSYQKg-3b6WIuHWiVGeSvva9pQcPugeN1MeegFSRI3yxOC_Rxw6qaEvg-	2026-04-26 11:30:07.960421+00	2026-04-23 11:30:07.650277+00
cc67c69b-5a75-42a4-a5ec-ecc6733437cc	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	vG_7mKL2JyAEoHCIlMARq9lYoUtISpvq7_6NC4n7tHkE8MiSAtO4cTNR1Sco7FXp	2026-04-26 11:30:11.650231+00	2026-04-23 11:30:11.338055+00
dfedb722-ceb2-42c7-bca1-b282eec12d6f	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	yqWuN7ZqKZBOmNlNTctUsFHCMrWu5UD3cPTNY99_8ymer4WQ_G_0BbZr7fYL656N	2026-04-26 11:30:14.600965+00	2026-04-23 11:30:14.290661+00
1c04a1e6-404a-46c4-a71d-c8b8b07d914d	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	6OsfsCkcS-QwND77wgFsXRFM_d77dQEs2kcfU9Xz5is6YjthAkkyPOmlBmexJ0PR	2026-04-26 11:30:18.052495+00	2026-04-23 11:30:17.742722+00
74ed6dfb-5da0-49ab-8174-f627eed48c30	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	HXQ6l_3Sr30oI7sLXE2p72mwo22Oogf0BxPx7mKl4Y9J1WVlWTK2HlTcYbyt9AM5	2026-04-26 11:30:22.009466+00	2026-04-23 11:30:21.70139+00
26d19c21-eac1-475a-84c2-b493496dcc35	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	FVJ_jlZ2nIoHmMxc1H_Kx31RQHftqcpIRLVfZt-fPNUnxqEskqiSTJ3eY6GYfHSi	2026-04-26 11:30:24.931438+00	2026-04-23 11:30:24.622915+00
662219f9-f847-4445-b0f9-329da809a8ef	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	-SPW9c4KIDaGzOE_p_5w3MJTqiYaJfHdqDWj5V6voQXmFoLEeFf8DHx-aqtWU6lh	2026-04-26 11:30:28.699585+00	2026-04-23 11:30:28.390333+00
9d99ee49-be94-4940-9789-9b7d13220ed1	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	HQn7k7LZW1C-qFiE3f7kg7K1CN0lnU9Jzk53z-Q9qHvmG7F40tW0qMk3fQ8BX1Lb	2026-04-26 11:30:32.824318+00	2026-04-23 11:30:32.516538+00
cabd4f05-c335-44a2-aaf1-0ac40069429a	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	bACC1ebR-PkzPAT23LYioRVJDeNwzb-rjz21liRrvPt2wiOo6RrfxabzclcNu_gl	2026-04-26 11:30:36.332848+00	2026-04-23 11:30:36.02348+00
13508494-9e15-4862-ba49-f58fa3115ffd	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	Pq0Opk5i2af_5flaGGM9DVFOmtYYiu-ZKTv6ypWrKhz3DGETpU_QssvYbML3p5-i	2026-04-26 11:30:40.11746+00	2026-04-23 11:30:39.808331+00
13987569-791d-454e-8df6-22dc3fb8debd	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	8cJmOjDndfF_dGgaleFWibL6UpwS4TgTbm3kz76n6TloXslbMDRK8x1uZ8ozSex2	2026-04-26 11:30:43.509106+00	2026-04-23 11:30:43.194341+00
bbcca259-d408-4beb-b313-6e8d5d21489f	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	pqDpz6PPZh4NMxFP-uXVajhWBujTo94ILfhSe91gD03ssFV467tRqEXn9_q6fiL_	2026-04-26 11:30:47.247033+00	2026-04-23 11:30:46.937009+00
bb01efcd-2803-4843-8530-164e674e51df	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	sROK0zEQQcevthOqvFWy7KeDqoCpR9tRnbKMOvO7-ZAjRPszymEUhsjh1Lf5l2Bo	2026-04-26 11:30:50.554312+00	2026-04-23 11:30:50.248267+00
2a3de202-08a4-4e65-9e70-1fbd77316b62	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	0vLVyj3ZHnJkK5gNAyvJ2tJzSKT0fvrRYwrrxp3MdcMWbadQZvLQfuJsAwBYI2v4	2026-04-26 11:30:53.985483+00	2026-04-23 11:30:53.67341+00
1ebab0d1-544a-4e02-8ee4-8574ccc3f44f	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	toxc_mbxF7Xy3elhaePYj_9CikxK9h0OHcYFlrmAc-9Q3hZpwcM6Zz_sDrzrhuEe	2026-04-26 11:31:00.701116+00	2026-04-23 11:31:00.391971+00
c0b288c6-7b79-4579-937f-826d7a265a2f	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	v7Z2T1BPDrf6ECbmZb1hWu_yLARVQeLqzCDneXCiaJ04VguP-uPnHUzuAp2Dx8MH	2026-04-26 11:31:03.975531+00	2026-04-23 11:31:03.664772+00
786bd5f9-2a8a-48aa-84e2-64f2bf4b342b	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	HdTL8wb0BqZCK_HX0401INGA8d6Fhk3WPc5tuE9nKgykfYsI8lIOEzM6HR4OgKmq	2026-04-26 11:31:07.020981+00	2026-04-23 11:31:06.713065+00
9fc2917d-01b0-44b9-81da-6799c743fc85	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	XNXValg49L8DFQZ9mp4OzBwH7pBWAVCXXAb5hL0H9u39UMtp2YPZ4UyeFb8GL308	2026-04-26 11:31:13.266401+00	2026-04-23 11:31:12.940146+00
c035af73-48d8-45ea-a9ae-8ac64f22eaed	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	eN6dM0G4RIMxssQaJ7PaQk8xC14k4bNv9Je1X_68VeNwvlasjxyFc1qS3_WaGShz	2026-04-26 11:31:16.705644+00	2026-04-23 11:31:16.395345+00
8ec2c6de-336c-44a7-a381-39f8ea22cbd8	2bfc2afd-252e-4117-99c6-54c803986f3e	S5w29RxaCYFyd4HOfdEpVcu8y-lLzwKDGIxVCMVmbGNGFjpiCDTiadAqGAz_kEWx	2026-04-26 11:31:20.220303+00	2026-04-23 11:31:19.906091+00
6183393f-80f8-44c3-9c21-a8a583d8a874	2bfc2afd-252e-4117-99c6-54c803986f3e	eL8lTdbaRkNInbGsVVnCxw0wpPYbmyccTIkmlSWEFARwP_IRGPbUtofYiOIxKmeA	2026-04-26 11:31:23.730076+00	2026-04-23 11:31:23.419662+00
15c36d09-6903-4657-afc8-aab3525d9526	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	Rim0Gf2mhMIXaHFXQ_rsstcznFK-j5jP91VWd4H0IRtZQk_IJRcuDYaqac2rTYJz	2026-04-26 14:54:57.067757+00	2026-04-23 14:54:56.75823+00
8c87567f-112c-4ff8-b80d-528412cb89cc	2bfc2afd-252e-4117-99c6-54c803986f3e	9s8dxVA46O53cyVF1EiYx9gV7jrx8TaERyPV9hw2VqEK4QD9-EPlmVth7PLuplj1	2026-04-26 14:55:01.119339+00	2026-04-23 14:55:00.811742+00
bb210d92-fedc-4f65-aebb-819c3bffdd57	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	2D-MXVwjSiyQ9Mt_QOXhuGmMIWz_DiKngOp16WJ5T2UmYaASHEaHiy9YqOcDrFZx	2026-04-26 14:55:11.469155+00	2026-04-23 14:55:11.155155+00
8c5bb496-e445-4fcb-9359-b9ad741bce49	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	8RATQ1P55uz-nTEJm0honnWJFCOkdoOFCfYlK6PdnLAabgboYnQnh9oR2GKBWaJi	2026-04-26 14:55:15.329865+00	2026-04-23 14:55:15.021605+00
88da2e71-3084-44a4-8af4-b35ad022ed28	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	BkhGCV9Vlm1CdekAzPrJKAyKfcNtknWGbQE8oT5aOYOx5bIE5FGZPoIMieeFriCv	2026-04-26 14:55:19.099242+00	2026-04-23 14:55:18.791641+00
08ee700e-d847-4061-beb6-0a7fc137bcec	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	4YZra8lMMelCo16zDt6TDFU86H-KnCZKxSuOZ2ovQoiex2Q45I4qkJ0xPXgfJjab	2026-04-26 14:55:22.664584+00	2026-04-23 14:55:22.357795+00
a78d0027-be82-4fce-95a5-f0b094b5426a	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	6zDL7SEJ47TF5aNSeO74PrwbsE45PuhZMd0rGO02DYcw22rG-4oWfqEQJ0PUW5WG	2026-04-26 14:55:26.558122+00	2026-04-23 14:55:26.246493+00
76b7733c-785e-4aba-9ac1-3fd8945ecb65	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	tZooeAZKNF_A1tvHtmhSuOUUcrjDXW_Qy16OsuXxsmQ7B2cD-QJxZuERAe8f2x9d	2026-04-26 14:55:30.324042+00	2026-04-23 14:55:30.017313+00
328b6155-d18e-492d-a296-c1aca5b717eb	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	4vnh_sv9nQEioEJuzPwIobbRkXkkRRxQHDs_H7uiVpK6WndHQqUltcbaIH8RbXYL	2026-04-26 14:55:34.234047+00	2026-04-23 14:55:33.925861+00
d01c3382-85d8-4fd6-83ae-a0761fb45d44	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	oU4Hq7yebj1h7u_f2o43jk97ZTs0BeDfVUNShACU_91wdEFIQTA9X8sO97yFgmXS	2026-04-26 14:55:37.228053+00	2026-04-23 14:55:36.919528+00
141ca018-34f1-468e-bbb0-79e1b944d685	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	boxKgO865gBcOs4YDvfUzbcV4ObtSBEamjeLABvxsNmqBtE7JEpjgVx_iC3WG-Q1	2026-04-26 14:55:40.619562+00	2026-04-23 14:55:40.312888+00
ec561ef5-c97b-4733-95ef-f6607c2cf39a	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	bqMSRdOZ81jcQDnO3NtfSSpoeDem23bXnFyx7TC-CPIcifj6lQSLmNumTEj9_x6R	2026-04-26 14:55:44.125212+00	2026-04-23 14:55:43.816646+00
383e4f23-d847-4d0a-908a-97fdccdd1dd4	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	H5tRs08_MNLZzrztKhgy60P2ShWEWTXRMIYeo902cibDCBiV7Hqi_XHmUX6SzBec	2026-04-26 14:55:48.019627+00	2026-04-23 14:55:47.707187+00
4c411927-7d88-4e94-a731-4a4c9ff76465	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	UMGw5-XgbCv7ZlNkqQ1841Cqn8ogSyZsNiAv6kkGfwzuJlf8M7ByUZ3lwEPYCw0R	2026-04-26 14:55:51.419751+00	2026-04-23 14:55:51.110725+00
a32392d6-73e1-42a5-9f85-ff85452bfe91	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	IqpFawbCQc8r_BQ-EX64StWoEB-JRtpr9eKp1kRiNcdZRo_wtdvdEUs50uL3P1x-	2026-04-26 14:55:55.403464+00	2026-04-23 14:55:55.093211+00
6b482003-1e95-423b-bce4-9314f1352282	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	tuEJAzptxo5GMfdL7nrPFXfOUZnd0FCnNPdZznyYFgMJBj6pF1KUthvzsMuOIrxy	2026-04-26 14:55:59.030159+00	2026-04-23 14:55:58.710054+00
6dc5e3f9-8ba7-4434-b5fd-9f7cc4634318	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	26NC7m8KLB8PYPFSnlwuCPZn3UwJYwGNLARF7sjs87Ca5rYvupG4ZIqWuYQAME_0	2026-04-26 14:56:02.308881+00	2026-04-23 14:56:01.996857+00
ce47efcc-2163-4fc8-bb66-2d60fba41c9e	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	bbX3II8iN-5pkpQ0MtFlMGM0g8j_hdQHMz1baHgNvKRSB1eMXHa_WmhTKrmMCy-O	2026-04-26 14:56:05.446513+00	2026-04-23 14:56:05.137463+00
2980b3f9-f964-4e95-a9d3-e2dc6d258ab1	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	l4gmEm2aLA-uOK5VewhzH8yE7dwA84wSDg9Tu0feZuXKU2zI8kXXglaRuRjXWSMz	2026-04-26 14:56:08.999296+00	2026-04-23 14:56:08.690356+00
d71edbce-acec-4323-8ab9-d01734738fe8	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	_QuXaDVBSnG0OadgTwyOWhgHYDsLLzhKOwssp3wt7tMAWIY8RACzlyrWb8Ql9p6f	2026-04-26 14:56:25.334213+00	2026-04-23 14:56:25.027715+00
ff2f69bc-0453-4c15-86d0-e48ad8d8860d	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	MSZeqmfCHQSFjsA7ZDnZMphCDSDyObI8wePL0GK2NL1Em1fNirYPxnVglLXNBuCi	2026-04-26 14:56:41.876173+00	2026-04-23 14:56:41.56484+00
eaa2106c-7b81-477c-98b1-78297dd12b0a	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	vfoiyhNFPXqu3o7P_NX2RJtRNkhMVllGTIqTKArw7khAS6-o-bCdLDEgSo7VKtB0	2026-04-26 14:56:12.196139+00	2026-04-23 14:56:11.887967+00
1f6076a6-b948-4eaf-9631-29c6e904e606	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	Gdg40B8Jta6PLWcf2Py9KT9LEyk7R8RDupSwV1BQyNekkCgmVHNpnyrl7LcTJB7R	2026-04-26 14:56:47.850382+00	2026-04-23 14:56:47.538625+00
6d1dcfc0-894e-4140-81b4-2fb9ae0b8a01	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	ySmn7y73weAzlJ_UGMtx2zaEGO88xRJ7XuHykKPSYYa6WqSg_IsHfoO9siewHY-X	2026-04-26 14:56:15.616794+00	2026-04-23 14:56:15.307019+00
8544b14e-8c22-4a65-b98f-d8b52c13354b	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	bTBtW4m5PdDI0V4iBuCUB2-fC_Ocjv9K5AEj_67IHvs2iIuiJbNZeYdtxeUkgtck	2026-04-26 14:56:18.66454+00	2026-04-23 14:56:18.350856+00
db924101-d30c-4d35-b585-7ef033f4bcb1	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	DYQPjbU_X0QU4JcymZDqE4qkRO7iqKM6477OmA6LtNlU-d_m1Lv2mglNori3JUmv	2026-04-26 14:56:22.093166+00	2026-04-23 14:56:21.784488+00
04496d38-5dc0-4a1d-9c75-a084577ee87f	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	dnMys98etKGV91kiSSUs5nszH5V6Bc-hqGjKztoSp1EbUHGN-kmkt3KEl5XD79Ob	2026-04-26 14:56:28.706746+00	2026-04-23 14:56:28.39764+00
e1916648-564f-461e-9a1c-8e2203ba4562	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	roCasFpK1ZNpZStMejfagR7fSn_M_fsC89ME0j_PBd4EfiUV8SUeHUU0WPZZPm4J	2026-04-26 14:56:35.640385+00	2026-04-23 14:56:35.331114+00
0f94762a-8c6d-42b7-acec-5ed557e23819	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	C3lgdy60i6k5IF7AxyRHigSEhgioaAB_iVSm7wfjjb1ZdSklZs1nCTHZ7Zcdqyfp	2026-04-26 14:56:39.0478+00	2026-04-23 14:56:38.735623+00
ca2c90a2-df93-4558-bb77-4f2447020e44	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	p-Dxo_8J3BRlav9er6-qCLoZBeCDVWzf_kqG1-ZhnCuG6kI_rjQiJerqibLmIcxK	2026-04-26 14:57:08.222426+00	2026-04-23 14:57:07.754587+00
04c5d7e7-3b40-4493-8694-05da9d026f88	2bfc2afd-252e-4117-99c6-54c803986f3e	TjCgn1Lc_sm9wIEXF2mqH2lP7mmtv6BuSKpMSgVKWaLyG3zxwxM97nF0JL6AJHHn	2026-04-26 14:57:11.846186+00	2026-04-23 14:57:11.535474+00
f0359a87-48e8-420f-a96d-6c43dd1d75ac	2bfc2afd-252e-4117-99c6-54c803986f3e	_5XV_6iKeeQDL54_RYe-rh6mZmdH6tK1Tsbdec4rHK3-BZw-goTbORCeaSQguWE7	2026-04-26 14:57:15.739931+00	2026-04-23 14:57:15.430726+00
8c1e74c1-5b3a-441b-890b-0a196df0f7fd	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	Mns8QOS0OAy4i1nAyuk6clM741WJMTy-nE9yVF0cyOY9kRczmO2D5cWyye7ID8jV	2026-04-26 15:58:31.936154+00	2026-04-23 15:58:31.627934+00
147501d2-c8ab-4f06-b9d3-b91d4f2b99ad	2bfc2afd-252e-4117-99c6-54c803986f3e	Gvv_ffnlR731-dnhME8FtkJC5sxdmZOZOQaYPG0nktIvHHsELv-otoxHJfDWJTYm	2026-04-26 15:58:36.518994+00	2026-04-23 15:58:36.210763+00
12385f2f-8621-46ee-ba34-016ed16cdd4b	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	KRfgNUTQmW5s4Hq1l6_2PnWpz0ZBDX9TE-PJMyoo62Kiqjy4fXXjljoACCg1qDz_	2026-04-26 15:58:47.934465+00	2026-04-23 15:58:47.613401+00
5e9a5e2b-dd8d-4070-b56b-c812e433fe72	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	IBBmBX99yBYPFobBJtJrAG8B-rAc_pX22HfW8d37FZ8H97NR69k45GDUr0gLdOe_	2026-04-26 15:58:53.151292+00	2026-04-23 15:58:52.844584+00
aa7b1a1c-b9ae-4cbd-95ae-4899fdf37253	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	Qv2W-AaZu1XogqS6IxbFv5mEFH786Q7eAQbxo5wqFSOuUYuitQGnqZNED6uZgYU5	2026-04-26 15:58:58.120142+00	2026-04-23 15:58:57.811467+00
8e183f92-ef93-43a5-8bfc-1f2029ebbacb	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	-0SB8gT-2IhDJOvQp7HKoVEuFPxpb4KMwdlQj7oo-Af_vt37eQsuD_UkTOohPNPZ	2026-04-26 15:59:02.608588+00	2026-04-23 15:59:02.29881+00
1312262e-03b3-4698-9ffb-b82647ded545	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	cuY4syLqS4B10VkOymfn1ulRiMAlVKz8CRVIdC4qahRLLuZ0BGKqpC4gJnBuOff6	2026-04-26 15:59:06.895983+00	2026-04-23 15:59:06.58788+00
e054b788-b4d7-423c-a79b-d92c0ad99985	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	NoIb5YXUuCJbIBBMmlvuXleC9T37Y2WzNGdL8Ied1D-kCc9aZ_uTmLa0z22-Xrjx	2026-04-26 15:59:10.954875+00	2026-04-23 15:59:10.648325+00
d3e34be7-8fdc-48c5-9a10-3165e2a71211	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	OpYql9zLH4XyGW6jCYPALF_o2Pm49asr3ML4McLZJKYelhyJjxhB3uTYDWPgcqN2	2026-04-26 15:59:15.627283+00	2026-04-23 15:59:15.319191+00
58b806db-70a6-499b-8a18-13b112e154d8	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	a1BlViFaGEZDdmtIWzY_MfEceJv4ZgfHKc0214X6DHiuqbdm7CT1fV8XNrxTOY_-	2026-04-26 15:59:20.094183+00	2026-04-23 15:59:19.784035+00
5a7848a7-a357-4245-bb0a-cee5e04a961c	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	iB-oLhlYsnJ9fZ0iNYA7TEE_5VNMe7Tr4k7fKWcvlcu9qu282VmsZg6W8icYNjiE	2026-04-26 15:59:25.186003+00	2026-04-23 15:59:24.876592+00
d37df417-2baa-4bf0-b563-837c7c3a6b14	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	9o9wJJB3kgkgvOZsG_7vcOXc-9S7BUQwmyoCL5FbFEpjG2DAoUY_rJ7dBgDncAnC	2026-04-26 15:59:29.843785+00	2026-04-23 15:59:29.531354+00
0bcc9ec3-b248-4376-b49d-dadd607bfebb	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	O2gsCjfSvnrIqvpNSyTS918lCbfiHtXM83p1OO8fGhrpBkO68ciuRfpTFcYVRkAP	2026-04-26 15:59:34.534028+00	2026-04-23 15:59:34.227339+00
b0cf091a-086b-4b3e-a859-21c71ab87f5e	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	qCi4Sr__86kdYOSI_BkiaU9vlUN_1RRfVPA4gFAfknZTmUbktoBmAgjLMxEwIkAX	2026-04-26 15:59:38.132404+00	2026-04-23 15:59:37.825218+00
2ddb9041-a534-4296-81a6-90d8cde05fa7	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	HNIVPr-sOFUGhTOYKPYARdf9TsoAC5MT-qliNEQmhYhGtGced7Nhvazm0d2LJn9o	2026-04-26 15:59:42.198698+00	2026-04-23 15:59:41.888275+00
899b045d-f0ca-4e09-a100-60dcb9df79ba	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	5D1bs4hRSXKwI5uTMoUZ7DTFZedJSaHJIhuVw1mq41m6GgidzbKszdFqHA-tkrPJ	2026-04-26 15:59:46.841881+00	2026-04-23 15:59:46.533582+00
d83e6283-00a3-4e49-b1c9-84c5e3575a33	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	_5SPUf4C1CAw6yETJtP_ValB7hGGzZxvl2cNXc9pDhHcbYE-M-0dk46OGOEnqhuF	2026-04-26 15:59:50.719736+00	2026-04-23 15:59:50.393931+00
11dfa805-2226-4cb9-be8e-f22299cc25bd	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	1mh3TcNd8H97TV4G9t2jtcPbjbY0igHKtv0SFGfpxVKJeDDO2wbDhOMi3xN85nHs	2026-04-26 15:59:54.948494+00	2026-04-23 15:59:54.633359+00
47edb2c8-034a-4177-9962-4003762676f5	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	wORsy61oI5TMP26pFpcHmiKNU9XJ22g9_uPj9s7dUll2tq_Oii5QQSOUzwd2Iggd	2026-04-26 15:59:59.431845+00	2026-04-23 15:59:59.112379+00
2d47d02c-d721-4c93-a2ca-737121be75bd	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	Kjhb6ysjGVqijuNrqgZ2Jil0ERc_8mRU8kMJhzdTv10rvLudtUw4scqNVqE670-c	2026-04-26 16:00:03.521913+00	2026-04-23 16:00:03.212061+00
9bbbe269-54fb-4644-951a-e98aebf7874d	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	Gz-1G4HfytcMupwhklFimC_x3oph5PyzQDtu24SLiIjGjJPJBVuhSsChX8gASGta	2026-04-26 16:00:07.433659+00	2026-04-23 16:00:07.126641+00
b3d239b8-a590-451b-9b2c-d0d279af1f06	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	F6Wb4ff8gaCJcFVGYr7b3ErRTxrM2OLqe-6KiuasMlTKaLasgBbw5THUPPfXNh9E	2026-04-26 16:00:11.07397+00	2026-04-23 16:00:10.766237+00
ba5a3fef-3b17-4d9c-a24c-ca782c23db0a	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	Bp3mwGE2WN1efDkGEcuXRm4xk9rcKyNPkiX1D-Ow72xQDAVgHboeH0tmYru5JzcP	2026-04-26 16:00:15.220721+00	2026-04-23 16:00:14.908112+00
50f9b384-c5c5-4282-9740-faba90816aae	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	o2Eorul77ic8jd1HvVXyzm7dOARG8-cXvk9B1QFlYl4KL-3n7lnXOaVg0sCVR1gX	2026-04-26 16:00:18.853196+00	2026-04-23 16:00:18.540562+00
a3b02edd-b99b-4d10-ac0c-fbf727bf0373	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	9tkwXH2nTac1UupMUzpii13SgnXBuwfhFQlK8sQ53I-1LDviRmUOE4JDZndUeGA7	2026-04-26 16:00:23.034928+00	2026-04-23 16:00:22.726045+00
fb4f4353-df77-4869-910f-62fce8860c9c	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	HnXiXdYeuHxRDrTWsnZ3zWIH34ylclIYXI-4fhIJ1OkcAsoLS2ZhCkQQqah3357n	2026-04-26 16:00:29.798798+00	2026-04-23 16:00:29.48907+00
0bda2f6b-d738-4b47-b456-896829210c14	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	z7IVAViHQOxrPB6ADRwUYb4gPGhGfG7QTBQ0R50-xKF9TJe3q5ZgaMWskrFb6Dip	2026-04-26 16:00:34.51099+00	2026-04-23 16:00:34.187182+00
2912b20d-9ff9-4a98-a77c-cab59f0a7e0e	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	2FkZf5HjK_xNJYabqBRWzemnrYzdJu8TbUcGYk_UPBwjPy3CSai-qsjdC92EdKk2	2026-04-26 16:00:39.087521+00	2026-04-23 16:00:38.773252+00
0e1beb88-6af2-46f8-b556-cb79cd51928c	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	utSNH51mYY9QUBv18O_sRNtfKwaOCckjStzQB3OB2AsEX1urTOZTfmPHwcfp8SY_	2026-04-26 16:00:45.615704+00	2026-04-23 16:00:45.309245+00
41201b60-b069-491f-8ec2-74df15051525	c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	R-Dz4Sein-fJ4a_0XRqn0hFkuCToa4tJaDSrrO8ON7IM17KntrSk5x_7toXuc1Hl	2026-04-26 16:00:50.098105+00	2026-04-23 16:00:49.790056+00
75554764-7711-4797-a3d0-f4ce9551c944	2bfc2afd-252e-4117-99c6-54c803986f3e	QKHgxuJLvSL6qXMYQBzqKZ1zP7LnC8hkLN3CMaZSaaDHv-JYVy3lyr9udhSmale_	2026-04-26 16:00:54.015497+00	2026-04-23 16:00:53.703798+00
405d0aa1-9be9-48ba-9856-70fcb9d2053e	2bfc2afd-252e-4117-99c6-54c803986f3e	MevH3sYEG-4sf6ymCOHHNLeyu3f_GdLcONmHsvVQoyu0X_m5B4cIvPV0DLyG6IIJ	2026-04-26 16:00:58.432661+00	2026-04-23 16:00:58.107929+00
8249a06a-ce80-4f0f-a4a3-0f216403bd05	c8ee6132-06f7-4c2e-adee-66d2fd723d2c	YOtg8EEA6Gg4S-PNAmM-lnUptGCIrh13QidfldMKcESNHV1eEYthDk8ZMop9Ciqk	2026-04-26 19:22:31.264663+00	2026-04-23 19:22:30.950596+00
\.


--
-- Data for Name: task_instance_step_completions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.task_instance_step_completions (id, task_instance_id, routine_step_id, is_completed, completed_at, created_at) FROM stdin;
\.


--
-- Data for Name: task_instances; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.task_instances (id, family_id, family_member_id, routine_id, chore_template_id, instance_date, due_at, is_completed, completed_at, override_completed, override_by, override_note, created_at, updated_at, in_scope_confirmed, scope_dispute_opened_at) FROM stdin;
\.


--
-- Data for Name: user_accounts; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.user_accounts (id, family_member_id, email, phone, auth_provider, password_hash, is_primary, is_active, last_login_at, created_at, updated_at) FROM stdin;
6622e12b-1186-4d59-aaa0-5071d35d1f57	2f25f0cc-6130-464f-be8a-76d863ca0952	andrew@whitfield.com	\N	email	$2b$12$eJWR/to5qM54eFSia/aDJe4QgnZMs1G2Gl1GeDwiFkJJkMb0Vkl46	f	f	2026-04-12 15:47:37.402285+00	2026-04-12 15:46:39.561244+00	2026-04-14 16:44:39.094775+00
522019c0-1a4d-4a7c-9969-723f3ed413c5	e4d39e09-9d32-4aeb-adad-5014fe3bf6be	riverrose1730@gmail.com	\N	email	$2b$12$xRioFAEcnIeK.bn4BdRc1OoaPHSL89n8oI6GUEjM51d.IjllMpria	t	t	2026-04-14 17:37:26.519498+00	2026-04-14 16:51:07.935071+00	2026-04-14 17:37:26.206423+00
c0fed78f-6adf-4ade-8a1c-6d32cd7854e8	b684226c-1217-44ca-84d0-3bf7c4ea4e82	smoke@scout.app	\N	email	$2b$12$DLZtWx8Nkh3j6TDfsjtMJ.Fn5bBNqxBlKkTHiBDNtk9bsNvMsI8lu	f	t	2026-04-23 16:00:50.0982+00	2026-04-13 19:05:15.444158+00	2026-04-23 16:00:49.790056+00
2bfc2afd-252e-4117-99c6-54c803986f3e	669c229c-96b0-44b7-940d-d026789b7c58	smoke-child@scout.app	\N	email	$2b$12$Mw1rBxzo7MeMAG11dHprn.7I4sN1XSeijS/BJeZGuVKkNlHMUOP1O	f	t	2026-04-23 16:00:58.432759+00	2026-04-22 22:22:26.652607+00	2026-04-23 16:00:58.107929+00
c8ee6132-06f7-4c2e-adee-66d2fd723d2c	2f25f0cc-6130-464f-be8a-76d863ca0952	robertsandrewt@gmail.com	\N	email	$2b$12$rsVszXA4VFAw6yJ53nzGgu79RXJccmX.54CD15Z3zv1GIbORhRZCi	t	t	2026-04-23 19:22:31.264813+00	2026-04-12 15:47:59.321627+00	2026-04-23 19:22:30.950596+00
\.


--
-- Data for Name: weekly_meal_plans; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.weekly_meal_plans (id, family_id, created_by_member_id, week_start_date, source, status, title, constraints_snapshot, week_plan, prep_plan, grocery_plan, plan_summary, approved_by_member_id, approved_at, archived_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: activity_events; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.activity_events (id, family_id, family_member_id, source, activity_key, started_at, duration_sec, metadata, imported_at) FROM stdin;
\.


--
-- Data for Name: affirmation_delivery_log; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.affirmation_delivery_log (id, family_member_id, affirmation_id, surfaced_at, surfaced_in, dismissed_at, created_at) FROM stdin;
\.


--
-- Data for Name: affirmation_feedback; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.affirmation_feedback (id, family_member_id, affirmation_id, reaction_type, context, created_at) FROM stdin;
\.


--
-- Data for Name: affirmations; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.affirmations (id, text, category, tags, tone, philosophy, audience_type, length_class, active, source_type, created_by, updated_by, created_at, updated_at) FROM stdin;
8c2927db-1bbe-4d51-a5d5-eba3a3f6435c	You are building something that matters.	growth	[]	encouraging	discipline	general	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
f395d965-5c3b-4aed-8a8d-dcbf1f24fb8c	Every small step today adds up to something big tomorrow.	growth	[]	encouraging	resilience	general	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
eafeec9d-122d-4364-b1fd-84c96393a500	Your effort today is shaping who you become.	growth	[]	encouraging	discipline	general	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
4933071a-bc15-4566-8a4d-ac661d4f97c2	Progress is progress, no matter how small.	growth	[]	encouraging	gratitude	general	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
f48ecc12-0603-4cc6-a87a-c18a866f5701	There is always something to be thankful for.	gratitude	[]	encouraging	gratitude	general	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
0f9c5036-2403-41bd-ad5c-f03dbe5c2110	The people around you are a gift. Tell them.	gratitude	[]	encouraging	family-first	parent	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
b45df6c5-6cf0-4848-aa4d-ee2a38a34f75	Gratitude turns what we have into enough.	gratitude	[]	reflective	gratitude	general	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
9a07fff8-3e1f-44bb-a806-0f2cddac7316	Hard work compounds. Show up again today.	discipline	[]	challenging	discipline	general	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
c0123210-1db5-472d-8259-5f47894bbc26	Comfort is the enemy of growth. Push a little further.	discipline	[]	challenging	resilience	parent	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
2764ec22-f4d0-406f-97d8-25131a22b568	What you do when no one is watching defines you.	discipline	[]	challenging	discipline	general	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
c06fdbf3-321e-4019-b926-45e314e7f382	Tough days build tough people.	resilience	[]	reflective	resilience	general	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
83287c95-caa3-4a9c-ad91-b48bb2f019dc	You have survived every hard day so far. That is 100%% success.	resilience	[]	reflective	resilience	general	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
bf014e32-dd67-493c-a896-e5e7706c6fbf	Storms do not last forever. Neither does this.	resilience	[]	reflective	resilience	general	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
39c1de21-2a73-4086-9f2b-9e2a98936cc1	A kind word at breakfast sets the tone for the whole day.	family	[]	practical	family-first	parent	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
b73e96a4-1a9f-4062-a321-6b0c2d19e7f0	Ask your kids one real question today. Then listen.	family	[]	practical	family-first	parent	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
ff43c99b-7226-42d2-9d77-fb1e14591ac7	Showing up is the most important thing you can do as a parent.	family	[]	encouraging	family-first	parent	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
16120b11-dd82-40af-9b71-30d3d770ea2f	You can do hard things.	growth	[]	encouraging	resilience	child	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
2f046039-15ad-469d-8a61-a2c306e3e05e	Being kind is always the right choice.	kindness	[]	encouraging	gratitude	child	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
f669e6d1-1fbb-4b36-8713-4da19b5771f9	Mistakes help you learn. Keep trying.	growth	[]	encouraging	resilience	child	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
c2ecaa51-815d-4bdd-9765-cbc6b1533e2b	Your family is proud of you.	family	[]	encouraging	family-first	child	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
6240f80e-63ca-4be4-8a02-b7eebf1d4bd3	Doing your best is always enough.	growth	[]	encouraging	discipline	child	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
554e8496-4b7d-4120-9e6b-d67a767ab2fc	You are fearfully and wonderfully made.	faith	[]	encouraging	faith-based	general	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
698360e5-c974-4e57-a1cc-149e87c7cc11	Let your light shine before others.	faith	[]	encouraging	faith-based	general	short	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
d6f8efce-66fb-419e-b7a1-487932c6881d	The way you handle today's small frustrations is practice for life's bigger challenges. Stay steady.	resilience	[]	reflective	resilience	parent	medium	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
ea240d3e-872e-4fd1-b3df-264d99c583ed	Your children are watching how you treat yourself. Model grace, patience, and persistence.	family	[]	reflective	family-first	parent	medium	t	curated	\N	\N	2026-04-19 05:59:19.033573+00	2026-04-19 05:59:19.033573+00
\.


--
-- Data for Name: allowance_periods; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.allowance_periods (id, family_id, period_key, start_date, end_date, status, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: allowance_results; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.allowance_results (id, allowance_period_id, family_member_id, reward_policy_id, baseline_amount_cents, wins_earned, wins_required, payout_percent, projected_cents, final_cents, miss_reasons, approved_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: bill_snapshots; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.bill_snapshots (id, family_id, source, as_of_date, bill_key, label, due_date, amount_cents, metadata, imported_at) FROM stdin;
\.


--
-- Data for Name: budget_snapshots; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.budget_snapshots (id, family_id, source, as_of_date, category_key, available_cents, budgeted_cents, activity_cents, metadata, imported_at) FROM stdin;
\.


--
-- Data for Name: calendar_exports; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.calendar_exports (id, family_id, source_type, source_id, target, label, starts_at, ends_at, hearth_visible, export_status, last_exported_at, error_message, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: connector_accounts; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.connector_accounts (id, connector_id, family_id, user_account_id, account_label, status, last_success_at, last_error_at, last_error_message, created_at, updated_at) FROM stdin;
ee2dc46a-9090-43d7-bb56-fa1fc012bb54	b1540817-bc7c-4311-8d71-181141329cb4	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	Google Calendar	connected	\N	\N	\N	2026-04-17 13:35:10.162534+00	2026-04-17 13:35:10.162534+00
0cf44b6b-dfb0-48c2-b6f8-e0b33c96952b	85d43001-f7d4-45d8-9334-0421a96e0558	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	Greenlight (allowance)	connected	\N	\N	\N	2026-04-17 13:35:10.162938+00	2026-04-17 13:35:10.162938+00
c62ac16f-abc0-43a1-9a4a-64093edd413d	77c468e5-964c-4e61-862b-f6ed8ec74d3e	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	Hearth Display	connected	\N	\N	\N	2026-04-17 13:35:10.163164+00	2026-04-17 13:35:10.163164+00
57c4fd6b-f5fc-470d-90d9-d840f73eff80	da3178e2-059d-472a-8f7a-6aca977073c6	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	YNAB	error	\N	\N	\N	2026-04-17 13:35:10.163284+00	2026-04-17 13:35:10.163284+00
cff376e4-873b-4549-a4bd-bb91deda199b	65fe3cb7-227b-415c-8037-6979742905f0	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	Apple Health	disconnected	\N	\N	\N	2026-04-17 13:35:10.163411+00	2026-04-17 13:35:10.163411+00
3c3c759b-ae9d-4495-94b1-821b6c753bbf	a3d1f9ec-edb0-4b55-9fb8-32ec8ad39966	fbe71860-a1a2-42b0-a0b5-df72017ced7c	\N	Nike Run Club	disconnected	\N	\N	\N	2026-04-17 13:35:10.163526+00	2026-04-17 13:35:10.163526+00
\.


--
-- Data for Name: connector_event_log; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.connector_event_log (id, connector_account_id, event_type, payload, severity, created_at) FROM stdin;
\.


--
-- Data for Name: connectors; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.connectors (id, connector_key, label, tier, is_enabled, decision_gated, created_at, updated_at) FROM stdin;
af52bfc5-0293-4a91-9c1a-b4bc524774f3	google_maps	Google Maps	3	t	f	2026-04-15 22:36:30.546798+00	2026-04-15 22:36:30.546798+00
da3178e2-059d-472a-8f7a-6aca977073c6	ynab	YNAB	2	t	f	2026-04-15 22:36:30.546927+00	2026-04-15 22:36:30.546927+00
4447ffd0-186e-47d4-b909-780df912a9bf	exxir	Exxir (gated)	4	f	t	2026-04-15 22:36:30.546936+00	2026-04-15 22:36:30.546936+00
b1540817-bc7c-4311-8d71-181141329cb4	google_calendar	Google Calendar	1	t	f	2026-04-15 22:36:30.546942+00	2026-04-15 22:36:30.546942+00
31d136ae-87a9-4543-842d-fe5045ae7403	rex	Rex	2	t	f	2026-04-15 22:36:30.546948+00	2026-04-15 22:36:30.546948+00
65fe3cb7-227b-415c-8037-6979742905f0	apple_health	Apple Health	3	t	f	2026-04-15 22:36:30.546953+00	2026-04-15 22:36:30.546953+00
77c468e5-964c-4e61-862b-f6ed8ec74d3e	hearth_display	Hearth Display	1	t	f	2026-04-15 22:36:30.546958+00	2026-04-15 22:36:30.546958+00
85d43001-f7d4-45d8-9334-0421a96e0558	greenlight	Greenlight	1	t	f	2026-04-15 22:36:30.546963+00	2026-04-15 22:36:30.546963+00
a3d1f9ec-edb0-4b55-9fb8-32ec8ad39966	nike_run_club	Nike Run Club	3	t	f	2026-04-15 22:36:30.546968+00	2026-04-15 22:36:30.546968+00
\.


--
-- Data for Name: daily_win_results; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.daily_win_results (id, family_id, family_member_id, for_date, earned, total_required, total_complete, missing_items, computed_at) FROM stdin;
\.


--
-- Data for Name: device_registrations; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.device_registrations (id, user_account_id, device_token, platform, label, last_seen_at, created_at, revoked_at) FROM stdin;
\.


--
-- Data for Name: external_calendar_events; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.external_calendar_events (id, family_id, source, title, starts_at, ends_at, location, all_day, imported_at) FROM stdin;
\.


--
-- Data for Name: greenlight_exports; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.greenlight_exports (id, settlement_batch_id, family_member_id, amount_cents, greenlight_external_ref, export_status, error_message, created_at) FROM stdin;
\.


--
-- Data for Name: home_assets; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.home_assets (id, family_id, zone_id, name, asset_type, model, serial, purchase_date, warranty_expires_at, manual_url, receipt_url, notes, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: home_zones; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.home_zones (id, family_id, name, zone_type, notes, sort_order, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: household_rules; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.household_rules (id, family_id, rule_key, rule_value, description, created_at, updated_at) FROM stdin;
16b2a269-bdaf-41d1-8aeb-409f3363c0de	fbe71860-a1a2-42b0-a0b5-df72017ced7c	one_owner_per_task	true	If a task is shared, it is orphaned. Every task has exactly one owner.	2026-04-15 22:36:30.569456+00	2026-04-15 22:36:30.569456+00
149f06c3-47e6-47cc-b1fe-bb812ce6927d	fbe71860-a1a2-42b0-a0b5-df72017ced7c	finishable_lists	true	Routines doable in 15 to 25 minutes per block.	2026-04-15 22:36:30.569568+00	2026-04-15 22:36:30.569568+00
53608959-1229-4512-82f6-f3af63aaccc6	fbe71860-a1a2-42b0-a0b5-df72017ced7c	explicit_standards_of_done	true	No vague tasks. Every chore has a written standard of done.	2026-04-15 22:36:30.569576+00	2026-04-15 22:36:30.569576+00
53f4a40f-f759-442e-9c3a-9eac0bb7e194	fbe71860-a1a2-42b0-a0b5-df72017ced7c	quiet_enforcement	true	The checklist + deadline is the boss, not parent mood.	2026-04-15 22:36:30.56958+00	2026-04-15 22:36:30.56958+00
76bea782-5d39-4aa0-b106-186b759b28e0	fbe71860-a1a2-42b0-a0b5-df72017ced7c	one_reminder_max	true	One reminder. After that: "Check Hearth." No nagging.	2026-04-15 22:36:30.569584+00	2026-04-15 22:36:30.569584+00
16d79582-0513-4305-9ce0-cda2da787b66	fbe71860-a1a2-42b0-a0b5-df72017ced7c	scout_ai.toggles	{"allow_general_chat": true, "push_notifications": true, "allow_homework_help": true, "proactive_suggestions": true}	\N	2026-04-17 03:02:42.425666+00	2026-04-17 03:02:42.425666+00
1441df74-6f2d-442e-a2db-3675bf2fa9d8	fbe71860-a1a2-42b0-a0b5-df72017ced7c	allowance.rules	{"streak_bonus_days": 7, "streak_bonus_cents": 200, "max_weekly_bonus_cents": 500, "requires_approval_for_bonus": true}	\N	2026-04-17 03:02:42.438182+00	2026-04-17 03:02:42.438182+00
f81547c6-2057-4f65-a136-7c31df74f443	fbe71860-a1a2-42b0-a0b5-df72017ced7c	chores.rules	{"max_daily_pts": 100, "streak_bonus_pts": 20, "streak_bonus_days": 7, "requires_check_off": true}	\N	2026-04-17 03:02:42.44611+00	2026-04-17 03:02:42.44611+00
27d9ec22-4452-4d78-9475-a44e3667ae6e	fbe71860-a1a2-42b0-a0b5-df72017ced7c	grocery.stores	{"stores": [{"id": "costco", "kind": "bulk", "name": "Costco"}, {"id": "tom_thumb", "kind": "local", "name": "Tom Thumb"}]}	\N	2026-04-17 03:02:42.454742+00	2026-04-17 03:02:42.454742+00
997067b7-71a3-4a8d-9a15-1a73b1223bc9	fbe71860-a1a2-42b0-a0b5-df72017ced7c	grocery.categories	{"categories": ["Produce", "Protein", "Pantry", "Dairy", "Requested"]}	\N	2026-04-17 03:02:42.454742+00	2026-04-17 03:02:42.454742+00
6f5dc2d0-4c8a-43fe-98da-dbafb693d646	fbe71860-a1a2-42b0-a0b5-df72017ced7c	grocery.approval_rules	{"auto_approve_under_cents": 500, "require_approval_for_teens": false, "require_approval_for_children": true}	\N	2026-04-17 03:02:42.454742+00	2026-04-17 03:02:42.454742+00
c72e96c8-f1e3-4b41-bc65-fdadcd982157	fbe71860-a1a2-42b0-a0b5-df72017ced7c	meals.plan_rules	{"batch_cook_day": "sunday", "week_starts_on": "monday", "dinners_per_week": 7, "generation_style": "balanced"}	\N	2026-04-17 03:02:42.464238+00	2026-04-17 03:02:42.464238+00
9a2f079b-2e6d-47dc-a829-f332ba1393b3	fbe71860-a1a2-42b0-a0b5-df72017ced7c	meals.rating_scale	{"max_rating": 5, "repeat_options": ["repeat", "tweak", "retire"], "require_notes_for_retire": false}	\N	2026-04-17 03:02:42.464238+00	2026-04-17 03:02:42.464238+00
49c37cd5-0dc5-4f40-b995-130577773be9	fbe71860-a1a2-42b0-a0b5-df72017ced7c	meals.dietary_notes	{"categories": ["No restrictions", "Vegetarian-lean", "No onions", "Dairy-free", "Gluten-free", "Nut-free"]}	\N	2026-04-17 03:02:42.464238+00	2026-04-17 03:02:42.464238+00
f7ad52b4-1410-46a5-aa68-4b0740894889	fbe71860-a1a2-42b0-a0b5-df72017ced7c	rewards.tiers	{"tiers": [{"id": "small", "label": "Small reward", "example": "30 min extra screen time", "cost_pts": 200}, {"id": "medium", "label": "Medium reward", "example": "Movie night pick", "cost_pts": 500}, {"id": "large", "label": "Large reward", "example": "Day trip pick", "cost_pts": 1000}]}	\N	2026-04-17 03:02:42.482009+00	2026-04-17 03:02:42.482009+00
ea03ad58-a067-44e6-a2d7-494735dd587c	fbe71860-a1a2-42b0-a0b5-df72017ced7c	rewards.redemption_rules	{"require_approval": true, "allow_negative_balance": false, "max_redemptions_per_week": 2}	\N	2026-04-17 03:02:42.482009+00	2026-04-17 03:02:42.482009+00
\.


--
-- Data for Name: maintenance_instances; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.maintenance_instances (id, family_id, template_id, owner_member_id, scheduled_for, completed_at, completed_by_member_id, notes, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: maintenance_templates; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.maintenance_templates (id, family_id, zone_id, asset_id, name, description, cadence_type, rotation_month_mod, included, not_included, done_means_done, supplies, estimated_duration_minutes, default_owner_member_id, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: meal_transformations; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.meal_transformations (id, family_id, base_staple_id, transformed_staple_id, transformation_name, notes, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: nudge_dispatch_items; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.nudge_dispatch_items (id, dispatch_id, family_member_id, trigger_kind, trigger_entity_kind, trigger_entity_id, occurrence_at_utc, occurrence_local_date, source_dedupe_key, source_metadata, created_at) FROM stdin;
\.


--
-- Data for Name: nudge_dispatches; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.nudge_dispatches (id, family_member_id, status, severity, suppressed_reason, deliver_after_utc, delivered_at_utc, parent_action_item_id, push_delivery_id, delivered_channels, source_count, body, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: nudge_rules; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.nudge_rules (id, family_id, name, description, is_active, source_kind, template_sql, canonical_sql, template_params, trigger_kind, default_lead_time_minutes, severity, created_by_family_member_id, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: permissions; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.permissions (id, permission_key, description, created_at) FROM stdin;
bdf90cf8-6541-442d-abfd-f1bd6437f21e	household.complete_own_task	Mark own tasks complete	2026-04-15 22:36:30.54441+00
a4e77fa2-503f-4129-9152-ea72057cc8b7	connectors.view_health	View connector health dashboard	2026-04-15 22:36:30.544515+00
af31e172-a1ab-4099-821f-e3faf17af89a	display.view_only	Display-only surface access (Hearth)	2026-04-15 22:36:30.544523+00
dc2eafd0-001c-495a-808a-eb946cae7a9a	household.complete_any_task	Mark any family member's task complete	2026-04-15 22:36:30.544527+00
994466bd-8a13-41e4-9a2c-ff25a8a0f475	rewards.view_own_payout	View own allowance summary	2026-04-15 22:36:30.544536+00
77a9face-a922-4006-8d69-c0747b3866c3	rewards.approve_payout	Approve weekly allowance payouts	2026-04-15 22:36:30.544539+00
45c2401b-0f68-42bf-afd7-0073614bcd0d	household.edit_rules	Edit household rules and standards of done	2026-04-15 22:36:30.544542+00
f5571f1b-61ca-436f-9c57-8b37534ddaad	calendar.publish	Publish household blocks to calendar	2026-04-15 22:36:30.544548+00
b0b80525-c0c7-4b38-b01b-6c79aa86c0a9	connectors.manage	Add/remove connector accounts	2026-04-15 22:36:30.544551+00
ee5ee0ca-f073-41bb-b738-505c910fb810	admin.view_permissions	View the permissions matrix for all family members	2026-04-17 13:35:10.126595+00
784ac5fd-60f2-487f-9da6-8814f31e165b	grocery.manage_config	Configure stores, categories, and approval workflow	2026-04-17 13:35:10.126627+00
e2263d10-506a-4610-9e1d-a11349c57400	grocery.add_item	Add items directly to the grocery list	2026-04-17 13:35:10.126635+00
229c18a3-24b1-4251-b515-838ca98b5f2c	purchase_request.submit	Submit purchase requests	2026-04-17 13:35:10.126641+00
d5b20277-ca73-4021-a4b4-c3bba22b9a1d	meal.review_self	Submit meal reviews	2026-04-17 13:35:10.126646+00
78658307-69c0-4a4e-8458-004921338cee	chores.manage_config	Configure per-kid chore routines and point values	2026-04-17 13:35:10.126651+00
6375b400-9055-4795-8620-f2e02b0f7582	account.update_self	Update own account settings and password	2026-04-17 13:35:10.126657+00
7094908c-7e6e-451b-aec3-7fc24428001d	grocery.approve	Approve pending grocery items	2026-04-17 13:35:10.126662+00
9485d26c-2799-4455-80d2-601fef7fa192	notes.manage_any	Create, edit, and delete family notes	2026-04-17 13:35:10.126667+00
40fbbcfe-0de6-4630-ba3a-39b5d9c5107b	dashboard.view_parent	Access the parent dashboard and parent-only insights	2026-04-17 13:35:10.126672+00
1270fcec-f698-41e7-9038-8369edfc53fc	chore.complete_self	Mark own assigned chores as complete	2026-04-17 13:35:10.126677+00
37983ed9-fe5f-4559-b44c-59509107d02f	family.manage_accounts	Create, edit, and remove sign-in accounts for family members	2026-04-17 13:35:10.126682+00
64d9470e-e7e4-4f1a-9963-34584c27b6c7	allowance.manage_config	Configure per-kid allowance targets and rules	2026-04-17 13:35:10.126688+00
d4502046-7c06-4534-9d60-6a493e5abae1	admin.manage_config	Edit family-wide and per-member configuration	2026-04-17 13:35:10.126698+00
10a233d6-9036-4c09-92eb-57a425376e76	scout_ai.manage_toggles	Toggle Scout AI capabilities for the family	2026-04-17 13:35:10.126704+00
881eb118-5ecd-467a-9ed6-090826cb1267	meal_plan.generate	Generate weekly meal plans	2026-04-17 13:35:10.126709+00
61b5eaf4-dcd1-4249-b220-bfbeb7f58b14	admin.manage_permissions	Assign role tiers and override permissions	2026-04-17 13:35:10.126716+00
23ab94ef-ca9e-4141-be31-8ff729f3e903	action_items.resolve	Resolve parent action items (briefs, alerts)	2026-04-17 13:35:10.126722+00
6de7bab9-5bc1-45fa-88fb-bba246105cbb	allowance.run_payout	Trigger weekly allowance payouts	2026-04-17 13:35:10.126725+00
ec44a3dc-5c26-452b-a0c0-0cd342914de2	admin.view_config	View family-wide and per-member configuration	2026-04-17 13:35:10.126729+00
67da5830-e632-4b34-86bd-ca5b83a40b8e	ai.manage	Manage AI chat settings and view AI usage reports	2026-04-17 13:35:10.126732+00
da45831a-b679-4339-bb70-e34ec19b9283	rewards.manage_config	Configure reward tiers and redemption rules	2026-04-17 13:35:10.126736+00
eb34bb8d-b591-4566-8c87-c036ff7fe362	family.manage_learning_notes	Edit learning and personality notes for children	2026-04-17 13:35:10.126739+00
6e31ba1a-8b3c-4996-bcf2-aa66900155ba	grocery.request_item	Request items for the grocery list (may require approval)	2026-04-17 13:35:10.126743+00
6f4dade1-c851-42af-bea7-3e6b0936d5b6	meal_plan.approve	Approve draft weekly meal plans	2026-04-17 13:35:10.126746+00
ee015658-f077-41f3-81f4-fcac546fb1c0	meals.manage_config	Configure meal plan rules, rating scale, dietary categories	2026-04-17 13:35:10.126749+00
fbc51aed-6fa9-406e-8347-6e4438b94719	purchase_request.approve	Approve or convert purchase requests from children	2026-04-17 13:35:10.126752+00
ee34b531-400f-4814-a134-aad021b8676b	family.manage_members	Add, remove, and edit family member profiles	2026-04-17 13:35:10.126756+00
d030d6e1-5a1b-4716-b28b-c84913eb3d2d	affirmations.manage_config	Manage affirmation library, rules, targeting, and analytics	2026-04-19 05:59:19.059298+00
6d27e0c5-ed4b-4a59-838d-f811a4c78b3a	tasks.manage_self	Create, update, complete, and delete own personal tasks	2026-04-20 20:53:34.93259+00
acbfa5b5-ac7a-4b74-8725-f9b2e068d77a	calendar.manage_self	Create, update, and delete own calendar events	2026-04-20 20:53:34.932695+00
e73386a5-a4eb-49c1-afb4-a69750f8c835	meals.manage_staples	Create and manage meal staples library (admin)	2026-04-20 20:53:34.932711+00
1942fb0e-b0e1-4aa3-93a3-40996815c7a3	home.manage_zones	Create and manage home zones	2026-04-20 20:53:34.960537+00
3ad4d743-eba7-40a7-a78a-0668f5dcdb96	home.manage_assets	Create and manage home assets	2026-04-20 20:53:34.960572+00
ab39d51e-9a19-4ac7-9c58-54373e2d89be	home.manage_templates	Create and manage maintenance templates	2026-04-20 20:53:34.960585+00
c9e2a4de-4043-4b68-99c6-4003f52c9f79	home.complete_instance	Complete maintenance instances	2026-04-20 20:53:34.960595+00
6d976589-78a1-41d2-83e0-daefbe9d2b9d	home.view	View home maintenance data	2026-04-20 20:53:34.960601+00
18f839a9-1170-403a-b7e2-99cd2c280786	push.register_device	Register an Expo push token for the current device	2026-04-21 05:42:25.567498+00
c6360147-42de-442a-b1bf-c4cdb3d44edf	push.revoke_device	Revoke one of the current member's push devices	2026-04-21 05:42:25.56756+00
3653db6f-0975-4614-93de-5183d7ef125b	push.send_to_member	Send a push notification to another family member	2026-04-21 05:42:25.567567+00
5fa61894-bebe-44d0-87cf-0329dcd0cac7	push.view_delivery_log	View the family-wide push delivery log	2026-04-21 05:42:25.567573+00
2b892374-3e4a-4c1e-904b-c8c40de0dba4	projects.create	Create a new family project	2026-04-21 14:51:33.575879+00
08c88bd2-7938-414b-86b4-85f1a9348fbb	projects.manage_own	Edit projects you own (primary_owner_family_member_id)	2026-04-21 14:51:33.575939+00
30e94f4a-ee38-4416-b561-8e9e27bdc140	projects.manage_any	Edit any project in the family	2026-04-21 14:51:33.575947+00
11ee858a-efd6-49b1-b05d-53ff1e424e85	projects.view	View projects and project tasks	2026-04-21 14:51:33.575953+00
fdc0f43e-3306-4d9b-bfcb-c4099d279787	project_tasks.update_assigned	Update status and notes for project tasks assigned to you	2026-04-21 14:51:33.575959+00
303c63d3-44a0-4453-ac87-14f36a234cf0	project_templates.manage	Create, edit, and remove family project templates	2026-04-21 14:51:33.575965+00
ad67129a-4c16-4a64-8ed2-a403589e8383	project_templates.view	View family project templates	2026-04-21 14:51:33.575971+00
703ce28f-69bf-41cc-beb7-e19aa1bdd3b7	ai.manage_own_conversations	List, rename, archive, and pin own AI conversations	2026-04-21 15:18:26.92762+00
8636f9c5-fc91-43c0-a673-ab7e89938842	ai.clear_own_history	Bulk archive own older AI conversations (archive-only, no delete)	2026-04-21 15:18:26.927674+00
29285e79-f71d-4d06-861c-4b0949fcfb57	ai.edit_own_personality	Edit own Scout AI personality config (tone, vocabulary, verbosity, notes)	2026-04-21 16:18:00.390144+00
1b868390-3b93-4404-a4a3-2ce8e35b868e	ai.edit_any_personality	Edit another family member's Scout AI personality config (admin surface)	2026-04-21 16:18:00.390283+00
3a58fc4e-a4c0-480b-8837-b09ed6e11ae4	nudges.view_own	View own recent proactive nudge dispatches	2026-04-22 00:33:10.198645+00
c16186d4-e70a-4d66-82d3-ca6730cb347c	quiet_hours.manage	Manage family-wide quiet-hours window for Scout nudges	2026-04-22 01:32:15.611448+00
b56423f8-9429-4466-b38e-6ac142c93590	nudges.configure	Create, edit, and delete custom Scout nudge rules	2026-04-22 11:03:43.732283+00
\.


--
-- Data for Name: project_budget_entries; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.project_budget_entries (id, project_id, project_task_id, amount_cents, kind, vendor, notes, recorded_at, recorded_by_family_member_id, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: project_milestones; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.project_milestones (id, project_id, name, target_date, is_complete, completed_at, order_index, notes, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: project_tasks; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.project_tasks (id, project_id, title, description, status, owner_family_member_id, due_date, estimated_duration_minutes, actual_duration_minutes, budget_cents, spent_cents, depends_on_project_task_id, notes, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: project_template_tasks; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.project_template_tasks (id, project_template_id, title, description, order_index, relative_day_offset, default_owner_role, estimated_duration_minutes, has_budget_impact, has_grocery_impact, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: project_templates; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.project_templates (id, family_id, name, description, category, estimated_duration_days, default_lead_time_days, default_budget_cents, created_by_family_member_id, is_active, is_builtin, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: projects; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.projects (id, family_id, project_template_id, name, description, category, status, start_date, target_end_date, actual_end_date, budget_cents, actual_spent_cents, primary_owner_family_member_id, created_by_family_member_id, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: push_deliveries; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.push_deliveries (id, notification_group_id, family_member_id, push_device_id, provider, category, title, body, data, trigger_source, status, provider_ticket_id, provider_receipt_status, provider_receipt_payload, error_message, sent_at, receipt_checked_at, provider_handoff_at, tapped_at, created_at, updated_at) FROM stdin;
b960aef8-d79d-4004-b7ca-722d2db92868	d8cded30-c9f6-4c81-bc95-fb844571f3f8	2f25f0cc-6130-464f-be8a-76d863ca0952	577f845c-64ac-436f-9d52-918f79dad9c3	expo	test	Scout test	Hello from Scout	{}	push.test_send	provider_handoff_ok	019db246-4702-7376-85e8-7caed52ceed8	ok	{"status": "ok"}	\N	2026-04-21 23:00:43.195191+00	2026-04-21 23:04:08.96225+00	2026-04-21 23:04:08.96225+00	\N	2026-04-21 23:00:43.183277+00	2026-04-21 23:04:08.96225+00
64ab1dd6-64be-423f-8c9d-d15d5747b7b9	c9f74a5d-aecf-4238-914d-24440e57c95e	2f25f0cc-6130-464f-be8a-76d863ca0952	577f845c-64ac-436f-9d52-918f79dad9c3	expo	test	Scout test	Hello from Scout	{}	push.test_send	provider_handoff_ok	019db249-502c-770e-85af-b9193df995e4	ok	{"status": "ok"}	\N	2026-04-21 23:04:02.191232+00	2026-04-21 23:04:08.96225+00	2026-04-21 23:04:08.96225+00	2026-04-21 23:04:23.365748+00	2026-04-21 23:04:02.179131+00	2026-04-21 23:04:23.365748+00
231e7878-a46b-4723-9ae1-930f35e6f337	7ca509fa-b01b-46cb-ba10-33272ab5f1a2	2f25f0cc-6130-464f-be8a-76d863ca0952	577f845c-64ac-436f-9d52-918f79dad9c3	expo	test	Scout test	Hello from Scout	{}	push.test_send	provider_handoff_ok	019db2cc-9066-72b1-abfd-e61806beece6	ok	{"status": "ok"}	\N	2026-04-22 01:27:23.799481+00	2026-04-22 01:28:57.638818+00	2026-04-22 01:28:57.638818+00	\N	2026-04-22 01:27:23.783121+00	2026-04-22 01:28:57.638818+00
295c8379-badd-49c6-9ca3-7fc19ba2d97f	47b61928-5758-4f75-af46-ce71e701356e	2f25f0cc-6130-464f-be8a-76d863ca0952	577f845c-64ac-436f-9d52-918f79dad9c3	expo	test	Scout test	Hello from Scout	{}	push.test_send	provider_handoff_ok	019db2cd-460d-723d-ab46-2265693d13b2	ok	{"status": "ok"}	\N	2026-04-22 01:28:10.377189+00	2026-04-22 01:28:57.638818+00	2026-04-22 01:28:57.638818+00	\N	2026-04-22 01:28:10.368135+00	2026-04-22 01:28:57.638818+00
34dba3e9-0140-4794-97f2-9013e148a753	d63422d3-167d-461b-9630-e6853c0a3512	2f25f0cc-6130-464f-be8a-76d863ca0952	577f845c-64ac-436f-9d52-918f79dad9c3	expo	test	Scout test	Hello from Scout	{}	push.test_send	provider_handoff_ok	019db2cc-c883-7245-b406-6c5b93b04986	ok	{"status": "ok"}	\N	2026-04-22 01:27:38.2376+00	2026-04-22 01:28:57.638818+00	2026-04-22 01:28:57.638818+00	\N	2026-04-22 01:27:38.228059+00	2026-04-22 01:28:57.638818+00
fcddd433-f9d5-4f3d-8071-3c8f7198078c	fd29dc2e-d86a-40ee-8be8-b283d82d5543	2f25f0cc-6130-464f-be8a-76d863ca0952	577f845c-64ac-436f-9d52-918f79dad9c3	expo	test	Scout test	Hello from Scout	{}	push.test_send	provider_handoff_ok	019db2cd-0f52-7628-ab36-750aa567d1f3	ok	{"status": "ok"}	\N	2026-04-22 01:27:56.370093+00	2026-04-22 01:28:57.638818+00	2026-04-22 01:28:57.638818+00	\N	2026-04-22 01:27:56.358862+00	2026-04-22 01:28:57.638818+00
8a6a75be-79f0-4f3b-906d-4be4d19d3834	a0d63831-719a-4c8e-8446-27cf359eca45	2f25f0cc-6130-464f-be8a-76d863ca0952	577f845c-64ac-436f-9d52-918f79dad9c3	expo	test	Scout test	Hello from Scout	{}	push.test_send	provider_handoff_ok	019db2d6-cb71-744f-b4f5-ed91f61e7751	ok	{"status": "ok"}	\N	2026-04-22 01:38:34.354546+00	2026-04-22 01:38:57.623936+00	2026-04-22 01:38:57.623936+00	\N	2026-04-22 01:38:34.344302+00	2026-04-22 01:38:57.623936+00
a4f83c97-cd38-444c-9d21-5ab1779971f3	e26fb94c-99f5-4124-a367-7619b97aa8c4	2f25f0cc-6130-464f-be8a-76d863ca0952	577f845c-64ac-436f-9d52-918f79dad9c3	expo	test	Scout test	Hello from Scout	{}	push.test_send	provider_handoff_ok	019db2d6-aa94-72bd-86d2-6c36aaf7c1ab	ok	{"status": "ok"}	\N	2026-04-22 01:38:25.914328+00	2026-04-22 01:38:57.623936+00	2026-04-22 01:38:57.623936+00	\N	2026-04-22 01:38:25.903968+00	2026-04-22 01:38:57.623936+00
cdbd29a1-cd90-4939-b26a-12e507844803	d02eee7d-4199-4449-8482-90b8383947ac	2f25f0cc-6130-464f-be8a-76d863ca0952	577f845c-64ac-436f-9d52-918f79dad9c3	expo	test	Scout test	Hello from Scout	{}	push.test_send	provider_handoff_ok	019db2d6-706a-73a9-944e-71e977b94104	ok	{"status": "ok"}	\N	2026-04-22 01:38:11.019771+00	2026-04-22 01:38:57.623936+00	2026-04-22 01:38:57.623936+00	\N	2026-04-22 01:38:11.010072+00	2026-04-22 01:38:57.623936+00
\.


--
-- Data for Name: push_devices; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.push_devices (id, family_member_id, expo_push_token, device_label, platform, app_version, is_active, last_registered_at, last_successful_delivery_at, created_at, updated_at) FROM stdin;
577f845c-64ac-436f-9d52-918f79dad9c3	2f25f0cc-6130-464f-be8a-76d863ca0952	ExponentPushToken[cQKtJqFVeWunNWVtNDyJzN]	iPhone	ios	0.1.0	t	2026-04-22 01:37:52.871373+00	2026-04-22 01:38:57.623936+00	2026-04-21 23:00:04.505743+00	2026-04-22 01:38:57.623936+00
\.


--
-- Data for Name: quiet_hours_family; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.quiet_hours_family (id, family_id, start_local_minute, end_local_minute, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: reward_extras_catalog; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.reward_extras_catalog (id, family_id, extra_key, label, amount_cents, notes, is_active, created_at) FROM stdin;
d9e5d8f8-32ef-4ffa-bd4d-df5dbeb5fe84	fbe71860-a1a2-42b0-a0b5-df72017ced7c	extra_yard	Yard work — extras (raking, weeding, trimming)	500	Per session, with photo.	t	2026-04-15 22:36:30.584478+00
d0ee834d-fe5c-40c5-8951-c97568feeb21	fbe71860-a1a2-42b0-a0b5-df72017ced7c	extra_garage	Garage organize / tidy session	500	Per session, parent-approved.	t	2026-04-15 22:36:30.584567+00
89f41ce8-532d-4575-81b1-a084c59efd08	fbe71860-a1a2-42b0-a0b5-df72017ced7c	extra_dishes	Big sink session beyond ownership chore	200	Only when sink is overloaded.	t	2026-04-15 22:36:30.584575+00
\.


--
-- Data for Name: reward_ledger_entries; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.reward_ledger_entries (id, family_id, family_member_id, allowance_result_id, extras_catalog_id, entry_type, amount_cents, memo, created_at) FROM stdin;
\.


--
-- Data for Name: reward_policies; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.reward_policies (id, family_id, family_member_id, policy_key, baseline_amount_cents, payout_schedule, wins_required, extras_allowed, effective_from, effective_until, created_at, updated_at) FROM stdin;
226e8daa-8a0e-4ce2-b08c-98cc96728ecd	fbe71860-a1a2-42b0-a0b5-df72017ced7c	6012f148-ae1c-40b4-838f-ef3bb7532e98	weekly_allowance	1200	{"less": 0, "3_wins": 60, "4_wins": 80, "5_wins": 100}	[{"type": "daily_win", "count": 5}]	t	2026-01-01	\N	2026-04-15 22:36:30.583309+00	2026-04-15 22:36:30.58331+00
a58517ce-8f63-4575-b73f-a3bec3b99da9	fbe71860-a1a2-42b0-a0b5-df72017ced7c	c61d88de-857e-42d3-8116-575f6fabf14f	weekly_allowance	900	{"less": 0, "3_wins": 60, "4_wins": 80, "5_wins": 100}	[{"type": "daily_win", "count": 5}]	t	2026-01-01	\N	2026-04-15 22:36:30.58372+00	2026-04-15 22:36:30.58372+00
92271e93-f426-4ceb-ae74-6437bfa4d8d6	fbe71860-a1a2-42b0-a0b5-df72017ced7c	e4d39e09-9d32-4aeb-adad-5014fe3bf6be	weekly_allowance	700	{"less": 0, "3_wins": 60, "4_wins": 80, "5_wins": 100}	[{"type": "daily_win", "count": 5}]	t	2026-01-01	\N	2026-04-15 22:36:30.583963+00	2026-04-15 22:36:30.583963+00
8de79761-3a4b-4c40-b432-b421f70faa79	fbe71860-a1a2-42b0-a0b5-df72017ced7c	6012f148-ae1c-40b4-838f-ef3bb7532e98	weekly_allowance	500	{"schedule": "weekly", "weekly_target_cents": 1000}	[]	t	2026-04-17	\N	2026-04-17 13:35:10.156474+00	2026-04-17 13:35:10.156474+00
139cc949-b1cd-4c85-9cc2-99fc5170eb3f	fbe71860-a1a2-42b0-a0b5-df72017ced7c	c61d88de-857e-42d3-8116-575f6fabf14f	weekly_allowance	400	{"schedule": "weekly", "weekly_target_cents": 800}	[]	t	2026-04-17	\N	2026-04-17 13:35:10.156764+00	2026-04-17 13:35:10.156764+00
0a5da202-f071-4f8e-ae85-1f250f0e77cc	fbe71860-a1a2-42b0-a0b5-df72017ced7c	889e7a80-05ec-4140-9c1b-4f1e7d2eb355	weekly_allowance	600	{"schedule": "weekly", "weekly_target_cents": 1200}	[]	t	2026-04-17	\N	2026-04-17 13:35:10.156851+00	2026-04-17 13:35:10.156851+00
27cc2b08-38a8-4107-b8db-13bce06fe10b	fbe71860-a1a2-42b0-a0b5-df72017ced7c	e4d39e09-9d32-4aeb-adad-5014fe3bf6be	weekly_allowance	300	{"schedule": "weekly", "weekly_target_cents": 600}	[]	t	2026-04-17	\N	2026-04-17 13:35:10.15694+00	2026-04-17 13:35:10.15694+00
\.


--
-- Data for Name: role_tier_permissions; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.role_tier_permissions (id, role_tier_id, permission_id, created_at) FROM stdin;
d32320bb-37db-49de-a726-ba7607cacf93	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	af31e172-a1ab-4099-821f-e3faf17af89a	2026-04-15 22:36:30.544957+00
d52745b4-7d09-4fad-9e8c-1209486baaa2	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	45c2401b-0f68-42bf-afd7-0073614bcd0d	2026-04-15 22:36:30.545053+00
6c0802f7-ebc3-4d2b-a149-fd7750eb24b9	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	994466bd-8a13-41e4-9a2c-ff25a8a0f475	2026-04-15 22:36:30.545059+00
282fc11c-1c82-4e6f-bed3-bc88443337bb	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	a4e77fa2-503f-4129-9152-ea72057cc8b7	2026-04-15 22:36:30.545062+00
65ddd2d2-ee10-4c44-9759-aa4edba1de28	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	f5571f1b-61ca-436f-9c57-8b37534ddaad	2026-04-15 22:36:30.545065+00
7cdebd59-8816-4ded-ac12-a29c042713f5	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	77a9face-a922-4006-8d69-c0747b3866c3	2026-04-15 22:36:30.545068+00
ab17bb00-dd7e-449c-8f3d-0bf13c8df00e	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	dc2eafd0-001c-495a-808a-eb946cae7a9a	2026-04-15 22:36:30.54507+00
b0b2bb43-ac3e-4ac4-9470-5532841c29c7	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	b0b80525-c0c7-4b38-b01b-6c79aa86c0a9	2026-04-15 22:36:30.545073+00
6779b84d-a4b7-40dd-ac8e-ce3dcffc4883	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	bdf90cf8-6541-442d-abfd-f1bd6437f21e	2026-04-15 22:36:30.545076+00
da29778d-9d5c-42ac-8006-64ea1d4dc1b3	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	f5571f1b-61ca-436f-9c57-8b37534ddaad	2026-04-15 22:36:30.545079+00
33f23e0e-59e8-4336-a757-30f5934f4693	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	a4e77fa2-503f-4129-9152-ea72057cc8b7	2026-04-15 22:36:30.545082+00
53be1df4-6e77-453f-94fc-f1767b3528fd	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	af31e172-a1ab-4099-821f-e3faf17af89a	2026-04-15 22:36:30.545086+00
4efec2b5-bd9d-4d9b-bcfd-38c60214572b	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	45c2401b-0f68-42bf-afd7-0073614bcd0d	2026-04-15 22:36:30.545093+00
16701249-3564-4c94-85c6-5f437fc6a8d1	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	994466bd-8a13-41e4-9a2c-ff25a8a0f475	2026-04-15 22:36:30.545097+00
6fe80a14-a471-4a9a-84fd-950331aefe82	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	bdf90cf8-6541-442d-abfd-f1bd6437f21e	2026-04-15 22:36:30.545101+00
d90f78d1-9125-41c8-be6a-fc3914a3af49	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	77a9face-a922-4006-8d69-c0747b3866c3	2026-04-15 22:36:30.545104+00
a15bb89a-4e55-41f9-9c94-00328116e771	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	b0b80525-c0c7-4b38-b01b-6c79aa86c0a9	2026-04-15 22:36:30.545107+00
98e1e92a-238e-4918-af4c-62499c2769c1	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	dc2eafd0-001c-495a-808a-eb946cae7a9a	2026-04-15 22:36:30.545109+00
884f2e35-e149-4360-ac89-df5fa6120f4e	9c008964-93c8-442c-8fb4-6a070349c438	994466bd-8a13-41e4-9a2c-ff25a8a0f475	2026-04-15 22:36:30.546215+00
1f884355-98bb-45c3-931a-9a01c967a389	a121d6a8-9f52-4104-b4a6-e224b1b42b71	994466bd-8a13-41e4-9a2c-ff25a8a0f475	2026-04-15 22:36:30.546233+00
9d0e911c-93a6-41f5-8e0a-96040629fdb1	d802c736-b7a1-4e29-8c28-e93441f3a9e0	994466bd-8a13-41e4-9a2c-ff25a8a0f475	2026-04-15 22:36:30.546237+00
d5530563-4442-4dd8-9e07-5385cf91b861	9c008964-93c8-442c-8fb4-6a070349c438	bdf90cf8-6541-442d-abfd-f1bd6437f21e	2026-04-15 22:36:30.54624+00
e96673ee-bf73-4de4-b63a-9fd0edd55359	a121d6a8-9f52-4104-b4a6-e224b1b42b71	bdf90cf8-6541-442d-abfd-f1bd6437f21e	2026-04-15 22:36:30.546244+00
6cab37f4-30aa-4201-b80a-f7ae592a708b	d802c736-b7a1-4e29-8c28-e93441f3a9e0	bdf90cf8-6541-442d-abfd-f1bd6437f21e	2026-04-15 22:36:30.546246+00
44ec0875-3fda-4def-b7cf-1caf0ba6e39e	6fc19fb6-fe86-4e13-aa77-a6747d2ae83d	af31e172-a1ab-4099-821f-e3faf17af89a	2026-04-15 22:36:30.54652+00
5a4e9578-c901-4015-a275-c8be39820ca0	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	6f4dade1-c851-42af-bea7-3e6b0936d5b6	2026-04-17 13:35:10.127589+00
3eca7c87-d4e5-473c-ba49-2fc110d0fbbe	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	6de7bab9-5bc1-45fa-88fb-bba246105cbb	2026-04-17 13:35:10.127616+00
4e3e7bce-c8eb-4778-b9e4-5e991b298c97	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	9485d26c-2799-4455-80d2-601fef7fa192	2026-04-17 13:35:10.127622+00
82c8f75d-d722-4f33-9344-d1958206c3b5	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	e2263d10-506a-4610-9e1d-a11349c57400	2026-04-17 13:35:10.127625+00
3d0fc766-532a-40d9-addc-d8a691491e45	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	d5b20277-ca73-4021-a4b4-c3bba22b9a1d	2026-04-17 13:35:10.127628+00
725d722c-5153-4f5a-9080-fc1bebfc83d5	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	ee5ee0ca-f073-41bb-b738-505c910fb810	2026-04-17 13:35:10.127631+00
a9ed9080-9ec6-488b-8a0c-82e27a6ff084	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	d4502046-7c06-4534-9d60-6a493e5abae1	2026-04-17 13:35:10.127634+00
1a1688fc-258b-4307-899e-188e591c04ee	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	78658307-69c0-4a4e-8458-004921338cee	2026-04-17 13:35:10.127637+00
7201d67f-fadc-4b96-958f-8ebd98d55e7e	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	da45831a-b679-4339-bb70-e34ec19b9283	2026-04-17 13:35:10.127639+00
ffce010b-483f-4d28-a79f-adcf168ab3a1	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	37983ed9-fe5f-4559-b44c-59509107d02f	2026-04-17 13:35:10.127642+00
ca127a5d-d26a-4608-97da-a568b7a768af	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	40fbbcfe-0de6-4630-ba3a-39b5d9c5107b	2026-04-17 13:35:10.127645+00
0a7f2ee6-cf34-442f-8c26-702c7649d47e	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	23ab94ef-ca9e-4141-be31-8ff729f3e903	2026-04-17 13:35:10.127648+00
ec5af2a6-f9b5-4e92-b11e-6d36b292ca3a	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	7094908c-7e6e-451b-aec3-7fc24428001d	2026-04-17 13:35:10.12765+00
5a7f0347-ba7c-47e3-b84e-f244ad83be91	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	ee34b531-400f-4814-a134-aad021b8676b	2026-04-17 13:35:10.127653+00
e56a90f3-23ca-4147-be89-03e15db512a8	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	64d9470e-e7e4-4f1a-9963-34584c27b6c7	2026-04-17 13:35:10.127656+00
a2d0bc5d-2202-42de-a54c-d352a5ee76c1	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	61b5eaf4-dcd1-4249-b220-bfbeb7f58b14	2026-04-17 13:35:10.127659+00
c1d9252a-38c7-481c-abf8-ec90f3a3b23e	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	6e31ba1a-8b3c-4996-bcf2-aa66900155ba	2026-04-17 13:35:10.127662+00
8d746082-45c4-4f9b-8193-5e3ff4bfe00d	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	1270fcec-f698-41e7-9038-8369edfc53fc	2026-04-17 13:35:10.127666+00
5bbbf4d9-044e-4211-8bb5-4393d1106134	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	6375b400-9055-4795-8620-f2e02b0f7582	2026-04-17 13:35:10.127669+00
0b98f17f-97a3-4743-9972-0376c0062943	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	881eb118-5ecd-467a-9ed6-090826cb1267	2026-04-17 13:35:10.127672+00
0dd28874-3a9c-41c6-ac29-14db9a1c7435	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	10a233d6-9036-4c09-92eb-57a425376e76	2026-04-17 13:35:10.127675+00
ccbd8d49-46a2-455c-b4bb-ce6891514e01	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	ee015658-f077-41f3-81f4-fcac546fb1c0	2026-04-17 13:35:10.127677+00
3e85ffc6-4fe5-442c-bf39-9115874c440c	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	ec44a3dc-5c26-452b-a0c0-0cd342914de2	2026-04-17 13:35:10.12768+00
936d92b0-f152-4fe6-b9e1-8624785ca966	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	67da5830-e632-4b34-86bd-ca5b83a40b8e	2026-04-17 13:35:10.127683+00
5ee83618-b9bf-4a3f-b9ae-53e00d4deea4	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	fbc51aed-6fa9-406e-8347-6e4438b94719	2026-04-17 13:35:10.127685+00
0ca97d0f-4da1-4910-8580-cfa88f62168d	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	784ac5fd-60f2-487f-9da6-8814f31e165b	2026-04-17 13:35:10.127688+00
3d136133-c0b0-4f80-a37d-4dcb3f96aa6c	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	229c18a3-24b1-4251-b515-838ca98b5f2c	2026-04-17 13:35:10.12769+00
bf1ccbff-85c7-4cfb-8e92-c7da8547a77e	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	eb34bb8d-b591-4566-8c87-c036ff7fe362	2026-04-17 13:35:10.127693+00
afac85c5-8b00-4a6e-8543-9e7e8354c7ec	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	d4502046-7c06-4534-9d60-6a493e5abae1	2026-04-17 13:35:10.127696+00
a6ebf7ef-07ef-4425-91fd-accea852429a	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	40fbbcfe-0de6-4630-ba3a-39b5d9c5107b	2026-04-17 13:35:10.127699+00
155a8ea2-916c-4fd9-936e-1504d96105e2	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	37983ed9-fe5f-4559-b44c-59509107d02f	2026-04-17 13:35:10.127702+00
b32fd4c7-be51-48f6-9ae4-5d153d394d2c	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	da45831a-b679-4339-bb70-e34ec19b9283	2026-04-17 13:35:10.127704+00
9c3498f3-12f4-4fdc-8fdb-0821d07d2794	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	78658307-69c0-4a4e-8458-004921338cee	2026-04-17 13:35:10.127709+00
0125b921-15d3-4cbf-bcd6-303fb179fff2	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	9485d26c-2799-4455-80d2-601fef7fa192	2026-04-17 13:35:10.127712+00
26e82618-7cc5-4572-a9ac-c992cadcc300	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	6de7bab9-5bc1-45fa-88fb-bba246105cbb	2026-04-17 13:35:10.127715+00
ec2a9cd0-81df-4058-8e30-59bd789435a7	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	6f4dade1-c851-42af-bea7-3e6b0936d5b6	2026-04-17 13:35:10.127718+00
17d0ebd7-efe7-490b-8e11-a1679db63f98	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	d5b20277-ca73-4021-a4b4-c3bba22b9a1d	2026-04-17 13:35:10.127721+00
f0256e56-3da7-4eef-ab91-4151681d467c	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	ee5ee0ca-f073-41bb-b738-505c910fb810	2026-04-17 13:35:10.127724+00
80c727a7-6d28-4d5b-98da-d37a1d70c629	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	e2263d10-506a-4610-9e1d-a11349c57400	2026-04-17 13:35:10.127727+00
972cf5ab-cc24-4642-900f-8f5d731de23f	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	ee015658-f077-41f3-81f4-fcac546fb1c0	2026-04-17 13:35:10.12773+00
6b9d3351-e482-40a0-86ef-a68e68b3eefc	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	ec44a3dc-5c26-452b-a0c0-0cd342914de2	2026-04-17 13:35:10.127733+00
c9acfebf-8df1-44e9-865f-31bb2008ad08	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	10a233d6-9036-4c09-92eb-57a425376e76	2026-04-17 13:35:10.127738+00
6890368c-c698-4fc3-af68-61e79712994d	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	881eb118-5ecd-467a-9ed6-090826cb1267	2026-04-17 13:35:10.127743+00
f833f219-db4c-4141-a3cc-10b00ed0704f	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	6375b400-9055-4795-8620-f2e02b0f7582	2026-04-17 13:35:10.127747+00
969679be-61aa-4cca-ba84-c381ffc7a75b	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	eb34bb8d-b591-4566-8c87-c036ff7fe362	2026-04-17 13:35:10.127752+00
64c12014-3df4-4583-8f3d-002fcfafb4f5	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	229c18a3-24b1-4251-b515-838ca98b5f2c	2026-04-17 13:35:10.127756+00
cbcc0fcf-e773-434b-af71-0800f65f6a6e	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	784ac5fd-60f2-487f-9da6-8814f31e165b	2026-04-17 13:35:10.12776+00
d08ce56e-b133-4252-b514-86acbc4c8a4e	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	fbc51aed-6fa9-406e-8347-6e4438b94719	2026-04-17 13:35:10.127767+00
e9f4eca7-1569-41b5-8758-374fe9675113	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	67da5830-e632-4b34-86bd-ca5b83a40b8e	2026-04-17 13:35:10.127771+00
3f3ee7d5-cca3-4984-be17-abfc408fb3ab	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	64d9470e-e7e4-4f1a-9963-34584c27b6c7	2026-04-17 13:35:10.127775+00
47b311c9-b7ba-48ad-b2e5-5749527baeb0	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	61b5eaf4-dcd1-4249-b220-bfbeb7f58b14	2026-04-17 13:35:10.127779+00
08186abb-2ead-4568-828d-1d055327299a	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	ee34b531-400f-4814-a134-aad021b8676b	2026-04-17 13:35:10.127783+00
03da04a3-fcbd-41d3-ae92-b9dccd00cc75	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	23ab94ef-ca9e-4141-be31-8ff729f3e903	2026-04-17 13:35:10.127788+00
af5f3d8a-4440-4e99-93da-75ea7d67ed94	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	7094908c-7e6e-451b-aec3-7fc24428001d	2026-04-17 13:35:10.127793+00
70121844-e170-4c7c-9b81-4a59ef1a13b8	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	1270fcec-f698-41e7-9038-8369edfc53fc	2026-04-17 13:35:10.127798+00
19d3efea-9ab1-408b-b631-468158d41d78	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	6e31ba1a-8b3c-4996-bcf2-aa66900155ba	2026-04-17 13:35:10.127802+00
83323bef-e333-4c62-9fc5-5bee2970861d	a121d6a8-9f52-4104-b4a6-e224b1b42b71	e2263d10-506a-4610-9e1d-a11349c57400	2026-04-17 13:35:10.129102+00
b4a1ee39-7ae5-4f7d-8b8d-6aa607248d2f	a121d6a8-9f52-4104-b4a6-e224b1b42b71	d5b20277-ca73-4021-a4b4-c3bba22b9a1d	2026-04-17 13:35:10.129114+00
1ec53adc-87a6-4cbf-ac3f-c4343913c61b	a121d6a8-9f52-4104-b4a6-e224b1b42b71	1270fcec-f698-41e7-9038-8369edfc53fc	2026-04-17 13:35:10.129118+00
99218c70-c698-45f9-8b36-1f5b20cc354e	a121d6a8-9f52-4104-b4a6-e224b1b42b71	6375b400-9055-4795-8620-f2e02b0f7582	2026-04-17 13:35:10.129121+00
91de90d5-f146-45d4-a8d8-143dd0149f47	a121d6a8-9f52-4104-b4a6-e224b1b42b71	229c18a3-24b1-4251-b515-838ca98b5f2c	2026-04-17 13:35:10.129124+00
84cafa15-9b31-4ee9-8512-ac9218212f41	d802c736-b7a1-4e29-8c28-e93441f3a9e0	d5b20277-ca73-4021-a4b4-c3bba22b9a1d	2026-04-17 13:35:10.129353+00
a4ea28c0-f6db-4b37-819c-2d2c7efa40d4	d802c736-b7a1-4e29-8c28-e93441f3a9e0	1270fcec-f698-41e7-9038-8369edfc53fc	2026-04-17 13:35:10.129359+00
0039f001-6e20-4ad8-bf47-22281b0567b6	d802c736-b7a1-4e29-8c28-e93441f3a9e0	6375b400-9055-4795-8620-f2e02b0f7582	2026-04-17 13:35:10.129366+00
94184ea3-581b-4290-9b5e-21bd452403d1	d802c736-b7a1-4e29-8c28-e93441f3a9e0	229c18a3-24b1-4251-b515-838ca98b5f2c	2026-04-17 13:35:10.129369+00
ca6132a9-c023-454e-ba01-3ed6f2f825b8	d802c736-b7a1-4e29-8c28-e93441f3a9e0	6e31ba1a-8b3c-4996-bcf2-aa66900155ba	2026-04-17 13:35:10.129371+00
f4e0c432-1855-4bbe-bf73-c5b74d138791	9c008964-93c8-442c-8fb4-6a070349c438	6e31ba1a-8b3c-4996-bcf2-aa66900155ba	2026-04-17 13:35:10.129564+00
09254bfa-40ce-4a50-8a51-e2667edf3252	9c008964-93c8-442c-8fb4-6a070349c438	1270fcec-f698-41e7-9038-8369edfc53fc	2026-04-17 13:35:10.12957+00
f118235e-01d2-4092-bafc-7ce5c6f14e01	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	d030d6e1-5a1b-4716-b28b-c84913eb3d2d	2026-04-19 05:59:19.059749+00
b2927871-08a8-40b4-8ac8-18831fb6a8ed	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	6d27e0c5-ed4b-4a59-838d-f811a4c78b3a	2026-04-20 20:53:34.933269+00
f05029c9-8b91-49d9-af87-4fa80a41acc2	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	6d27e0c5-ed4b-4a59-838d-f811a4c78b3a	2026-04-20 20:53:34.933361+00
c3fd60b0-e24e-4b33-ad80-f34f7273cad1	a121d6a8-9f52-4104-b4a6-e224b1b42b71	6d27e0c5-ed4b-4a59-838d-f811a4c78b3a	2026-04-20 20:53:34.93338+00
6d424794-eda0-44a9-ab8e-df2f99fc8f0b	9c008964-93c8-442c-8fb4-6a070349c438	6d27e0c5-ed4b-4a59-838d-f811a4c78b3a	2026-04-20 20:53:34.933385+00
d148c372-4bc2-4298-bc05-6b49d5e9f157	d802c736-b7a1-4e29-8c28-e93441f3a9e0	6d27e0c5-ed4b-4a59-838d-f811a4c78b3a	2026-04-20 20:53:34.933625+00
95b3bb0d-1ec5-4620-9996-178bd548025c	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	acbfa5b5-ac7a-4b74-8725-f9b2e068d77a	2026-04-20 20:53:34.934309+00
f507e52f-d56b-404e-bf29-5b2972e81595	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	acbfa5b5-ac7a-4b74-8725-f9b2e068d77a	2026-04-20 20:53:34.934326+00
b08469bf-6a02-49b0-b969-607b5f395b0a	a121d6a8-9f52-4104-b4a6-e224b1b42b71	acbfa5b5-ac7a-4b74-8725-f9b2e068d77a	2026-04-20 20:53:34.934336+00
a5fa9f3d-bf6a-436d-8994-2d9b94fcb19e	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	e73386a5-a4eb-49c1-afb4-a69750f8c835	2026-04-20 20:53:34.934537+00
45f2c9f6-fee5-4380-88b8-bc3571422e66	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	e73386a5-a4eb-49c1-afb4-a69750f8c835	2026-04-20 20:53:34.934552+00
5346b2e3-5244-4805-ab93-1651fe2f1379	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	1942fb0e-b0e1-4aa3-93a3-40996815c7a3	2026-04-20 20:53:34.960757+00
bcf94ae4-65b7-4c39-a266-39fa8273e3eb	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	1942fb0e-b0e1-4aa3-93a3-40996815c7a3	2026-04-20 20:53:34.960779+00
fd4bd043-2947-4be9-b53b-0b9565f310ad	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	3ad4d743-eba7-40a7-a78a-0668f5dcdb96	2026-04-20 20:53:34.960791+00
f3848d83-91ca-48de-bd3c-2849225ab5fa	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	3ad4d743-eba7-40a7-a78a-0668f5dcdb96	2026-04-20 20:53:34.960799+00
f9094538-e783-4e39-b1cb-86a9d0423d68	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	ab39d51e-9a19-4ac7-9c58-54373e2d89be	2026-04-20 20:53:34.960808+00
4255e70c-cabc-4005-9bad-f4ac0eaad00f	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	ab39d51e-9a19-4ac7-9c58-54373e2d89be	2026-04-20 20:53:34.960814+00
233c1fb5-3ae2-4911-afef-730183370948	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	c9e2a4de-4043-4b68-99c6-4003f52c9f79	2026-04-20 20:53:34.961023+00
0ab99d85-e3fb-4a0b-9b07-06a3aa2bfb68	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	6d976589-78a1-41d2-83e0-daefbe9d2b9d	2026-04-20 20:53:34.961034+00
f742dec8-5675-481b-95f0-62620fbc0105	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	c9e2a4de-4043-4b68-99c6-4003f52c9f79	2026-04-20 20:53:34.961041+00
e1cfa113-9133-479a-92a5-a0f2b98adfe1	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	6d976589-78a1-41d2-83e0-daefbe9d2b9d	2026-04-20 20:53:34.961046+00
ab55b794-7744-4a40-8f5c-94a845097775	a121d6a8-9f52-4104-b4a6-e224b1b42b71	c9e2a4de-4043-4b68-99c6-4003f52c9f79	2026-04-20 20:53:34.961051+00
abfbdb35-0db1-41c2-9849-7106e6ee793f	a121d6a8-9f52-4104-b4a6-e224b1b42b71	6d976589-78a1-41d2-83e0-daefbe9d2b9d	2026-04-20 20:53:34.961057+00
088306ad-e92f-4c42-afd3-432c7d1417bb	9c008964-93c8-442c-8fb4-6a070349c438	c9e2a4de-4043-4b68-99c6-4003f52c9f79	2026-04-20 20:53:34.961062+00
3146a30e-483c-4724-b88d-c5b3ae3a4b05	9c008964-93c8-442c-8fb4-6a070349c438	6d976589-78a1-41d2-83e0-daefbe9d2b9d	2026-04-20 20:53:34.961068+00
36ece1c8-4b00-4f65-8308-f16d70dfe7f8	d802c736-b7a1-4e29-8c28-e93441f3a9e0	c9e2a4de-4043-4b68-99c6-4003f52c9f79	2026-04-20 20:53:34.961074+00
1ce704fd-ef5b-4f30-bdef-677d7a75151c	d802c736-b7a1-4e29-8c28-e93441f3a9e0	6d976589-78a1-41d2-83e0-daefbe9d2b9d	2026-04-20 20:53:34.96108+00
2b2ad6e9-886f-4b86-b89a-f4fcb3743899	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	18f839a9-1170-403a-b7e2-99cd2c280786	2026-04-21 05:42:25.567903+00
3521e650-2c39-4884-9dcd-7a4065887f27	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	c6360147-42de-442a-b1bf-c4cdb3d44edf	2026-04-21 05:42:25.567993+00
0c924313-1e38-48c9-8772-0c74186a2533	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	18f839a9-1170-403a-b7e2-99cd2c280786	2026-04-21 05:42:25.568005+00
d96b89b3-1eed-4577-bf1a-38ec45e5c594	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	c6360147-42de-442a-b1bf-c4cdb3d44edf	2026-04-21 05:42:25.568011+00
403e791f-53a8-442a-b8a6-4781be3b082f	a121d6a8-9f52-4104-b4a6-e224b1b42b71	18f839a9-1170-403a-b7e2-99cd2c280786	2026-04-21 05:42:25.568018+00
5c7670c5-042b-4e16-accb-dd05c62c8a9e	a121d6a8-9f52-4104-b4a6-e224b1b42b71	c6360147-42de-442a-b1bf-c4cdb3d44edf	2026-04-21 05:42:25.568023+00
1f76a530-29c9-4b62-9d8d-c9543937008e	9c008964-93c8-442c-8fb4-6a070349c438	18f839a9-1170-403a-b7e2-99cd2c280786	2026-04-21 05:42:25.568028+00
128a1534-1d07-4d07-9ca9-06090254a39c	9c008964-93c8-442c-8fb4-6a070349c438	c6360147-42de-442a-b1bf-c4cdb3d44edf	2026-04-21 05:42:25.568034+00
7e77371e-1737-4b83-b9b4-edaafba9fb22	d802c736-b7a1-4e29-8c28-e93441f3a9e0	18f839a9-1170-403a-b7e2-99cd2c280786	2026-04-21 05:42:25.568039+00
22b21ba9-ab96-4372-989c-5a42d6e7d2eb	d802c736-b7a1-4e29-8c28-e93441f3a9e0	c6360147-42de-442a-b1bf-c4cdb3d44edf	2026-04-21 05:42:25.568045+00
fc40210b-0800-4795-97aa-24246bb48368	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	3653db6f-0975-4614-93de-5183d7ef125b	2026-04-21 05:42:25.568629+00
54709b3c-01fb-41dd-9d12-19490e568565	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	5fa61894-bebe-44d0-87cf-0329dcd0cac7	2026-04-21 05:42:25.568642+00
8a8471f4-0bfd-4924-9145-0cbf58fe73b2	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	3653db6f-0975-4614-93de-5183d7ef125b	2026-04-21 05:42:25.568649+00
1248f26b-c4ca-4f47-9cd5-bca9db5e556f	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	5fa61894-bebe-44d0-87cf-0329dcd0cac7	2026-04-21 05:42:25.568655+00
e418722f-319f-4129-89f6-d86749004a6d	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	2b892374-3e4a-4c1e-904b-c8c40de0dba4	2026-04-21 14:51:33.576306+00
1b906734-4b44-4b84-9576-0b81b00b8a22	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	2b892374-3e4a-4c1e-904b-c8c40de0dba4	2026-04-21 14:51:33.57638+00
a2fe89aa-367a-4773-ab99-6c55a7ed5809	a121d6a8-9f52-4104-b4a6-e224b1b42b71	2b892374-3e4a-4c1e-904b-c8c40de0dba4	2026-04-21 14:51:33.576388+00
a75d33d1-1736-4d1a-94ae-91bd0ada5a73	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	08c88bd2-7938-414b-86b4-85f1a9348fbb	2026-04-21 14:51:33.57686+00
8f870d8b-abc2-42b5-b975-1bcde74ebfd3	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	08c88bd2-7938-414b-86b4-85f1a9348fbb	2026-04-21 14:51:33.576878+00
f00a6d03-2ad7-4db0-a63a-04409ef8b387	a121d6a8-9f52-4104-b4a6-e224b1b42b71	08c88bd2-7938-414b-86b4-85f1a9348fbb	2026-04-21 14:51:33.576885+00
b2ea5096-423a-4843-b3cb-5e69091d53f1	9c008964-93c8-442c-8fb4-6a070349c438	08c88bd2-7938-414b-86b4-85f1a9348fbb	2026-04-21 14:51:33.57689+00
07d0222c-9574-4e39-ae4e-4979d60e1a0b	d802c736-b7a1-4e29-8c28-e93441f3a9e0	08c88bd2-7938-414b-86b4-85f1a9348fbb	2026-04-21 14:51:33.576898+00
e0c04cb3-ddfe-40e2-a862-976f5cbcca07	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	30e94f4a-ee38-4416-b561-8e9e27bdc140	2026-04-21 14:51:33.577132+00
2d3454ad-f17e-414a-afdd-6b70c30909ad	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	303c63d3-44a0-4453-ac87-14f36a234cf0	2026-04-21 14:51:33.577159+00
a25193e4-39d3-4be7-bc59-28a4cb15cf4c	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	30e94f4a-ee38-4416-b561-8e9e27bdc140	2026-04-21 14:51:33.577166+00
53b86d15-db3b-4191-bed8-1f7694a37bd0	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	303c63d3-44a0-4453-ac87-14f36a234cf0	2026-04-21 14:51:33.577171+00
b2c91b9b-cde7-4421-bde5-6b3d90889213	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	11ee858a-efd6-49b1-b05d-53ff1e424e85	2026-04-21 14:51:33.577324+00
fed9212b-42a3-431b-a879-1ee603bce3ed	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	fdc0f43e-3306-4d9b-bfcb-c4099d279787	2026-04-21 14:51:33.577334+00
f76427e4-976c-4bd8-a517-af089714c1e6	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	ad67129a-4c16-4a64-8ed2-a403589e8383	2026-04-21 14:51:33.57734+00
0a2eb6c6-3549-43f3-8953-86d1de798c43	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	11ee858a-efd6-49b1-b05d-53ff1e424e85	2026-04-21 14:51:33.577346+00
d46e5205-b607-453a-8080-b2f15e71ae84	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	fdc0f43e-3306-4d9b-bfcb-c4099d279787	2026-04-21 14:51:33.577351+00
12eeae72-657d-4a99-82a1-4bd3ce56ad14	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	ad67129a-4c16-4a64-8ed2-a403589e8383	2026-04-21 14:51:33.577357+00
ee8af9f6-9e52-4d6e-a9f5-2450806c5459	a121d6a8-9f52-4104-b4a6-e224b1b42b71	11ee858a-efd6-49b1-b05d-53ff1e424e85	2026-04-21 14:51:33.577362+00
52229534-027d-46d6-9356-f1b81dc3fd9c	a121d6a8-9f52-4104-b4a6-e224b1b42b71	fdc0f43e-3306-4d9b-bfcb-c4099d279787	2026-04-21 14:51:33.57737+00
e85fdd18-e948-4b35-b725-ece514db1f4d	a121d6a8-9f52-4104-b4a6-e224b1b42b71	ad67129a-4c16-4a64-8ed2-a403589e8383	2026-04-21 14:51:33.577376+00
476306a5-c8de-4ddb-a0d7-2d7a18bb4e35	9c008964-93c8-442c-8fb4-6a070349c438	11ee858a-efd6-49b1-b05d-53ff1e424e85	2026-04-21 14:51:33.577382+00
cdbabe2e-807b-4b5c-aa23-5c583c2d8d26	9c008964-93c8-442c-8fb4-6a070349c438	fdc0f43e-3306-4d9b-bfcb-c4099d279787	2026-04-21 14:51:33.577387+00
4ad74504-4655-48cc-92f7-b54472d6ef96	9c008964-93c8-442c-8fb4-6a070349c438	ad67129a-4c16-4a64-8ed2-a403589e8383	2026-04-21 14:51:33.577392+00
66e781c1-ca9b-4442-8848-ac0ca167e2d6	d802c736-b7a1-4e29-8c28-e93441f3a9e0	11ee858a-efd6-49b1-b05d-53ff1e424e85	2026-04-21 14:51:33.577397+00
6dd294f9-bbb7-4896-9b95-2638d9279f77	d802c736-b7a1-4e29-8c28-e93441f3a9e0	fdc0f43e-3306-4d9b-bfcb-c4099d279787	2026-04-21 14:51:33.577403+00
e495c8d6-d626-46bd-bb79-e338b9b91b3c	d802c736-b7a1-4e29-8c28-e93441f3a9e0	ad67129a-4c16-4a64-8ed2-a403589e8383	2026-04-21 14:51:33.577408+00
6ddc60f6-406c-4d28-ad2b-ce877c06e5f5	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	703ce28f-69bf-41cc-beb7-e19aa1bdd3b7	2026-04-21 15:18:26.92806+00
e14bd46b-c8e8-4109-b96c-c7da8ec57051	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	8636f9c5-fc91-43c0-a673-ab7e89938842	2026-04-21 15:18:26.928169+00
237c8db9-f1f9-4d14-a134-8c56e3981045	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	703ce28f-69bf-41cc-beb7-e19aa1bdd3b7	2026-04-21 15:18:26.928182+00
580b23df-0b3f-470f-84d0-a914897a7993	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	8636f9c5-fc91-43c0-a673-ab7e89938842	2026-04-21 15:18:26.928188+00
f8ff92e1-0a9a-45d5-be61-9ff723726e0f	a121d6a8-9f52-4104-b4a6-e224b1b42b71	703ce28f-69bf-41cc-beb7-e19aa1bdd3b7	2026-04-21 15:18:26.928194+00
d1b25e33-1835-4ab5-8bbd-388a831dc02f	a121d6a8-9f52-4104-b4a6-e224b1b42b71	8636f9c5-fc91-43c0-a673-ab7e89938842	2026-04-21 15:18:26.928201+00
d8f1ab7d-61a3-420f-bad5-837c549c79ab	9c008964-93c8-442c-8fb4-6a070349c438	703ce28f-69bf-41cc-beb7-e19aa1bdd3b7	2026-04-21 15:18:26.928207+00
bbf43538-d60c-4c70-8ff6-8624c1c7d11f	9c008964-93c8-442c-8fb4-6a070349c438	8636f9c5-fc91-43c0-a673-ab7e89938842	2026-04-21 15:18:26.928212+00
91815f48-b699-49df-b3c3-88b59ef5662b	d802c736-b7a1-4e29-8c28-e93441f3a9e0	703ce28f-69bf-41cc-beb7-e19aa1bdd3b7	2026-04-21 15:18:26.928222+00
913f74cf-e9c0-4fe9-9715-2cf2c7fe2e53	d802c736-b7a1-4e29-8c28-e93441f3a9e0	8636f9c5-fc91-43c0-a673-ab7e89938842	2026-04-21 15:18:26.928227+00
7eba372d-d7ac-4b15-8d60-604f5ba6da08	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	29285e79-f71d-4d06-861c-4b0949fcfb57	2026-04-21 16:18:00.390891+00
f3660700-4b03-41f9-b097-89424ff64453	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	29285e79-f71d-4d06-861c-4b0949fcfb57	2026-04-21 16:18:00.391003+00
bec1babc-6cca-498e-b8e6-6b7368333c67	a121d6a8-9f52-4104-b4a6-e224b1b42b71	29285e79-f71d-4d06-861c-4b0949fcfb57	2026-04-21 16:18:00.391022+00
4a683c8b-3958-42ca-a811-4f9d41e8540e	9c008964-93c8-442c-8fb4-6a070349c438	29285e79-f71d-4d06-861c-4b0949fcfb57	2026-04-21 16:18:00.391028+00
1e736fe6-9f8b-4c84-9af5-d973e8298b91	d802c736-b7a1-4e29-8c28-e93441f3a9e0	29285e79-f71d-4d06-861c-4b0949fcfb57	2026-04-21 16:18:00.391034+00
a9c17444-772e-4e44-a0b7-78fbae47ed37	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	1b868390-3b93-4404-a4a3-2ce8e35b868e	2026-04-21 16:18:00.391699+00
c59d73f3-a6ab-4e70-922d-465bd9f8ed94	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	1b868390-3b93-4404-a4a3-2ce8e35b868e	2026-04-21 16:18:00.391716+00
52d45192-0ff6-497a-81cd-f034c5f6c5dd	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	3a58fc4e-a4c0-480b-8837-b09ed6e11ae4	2026-04-22 00:33:10.199044+00
5568dc47-b1d7-4b9f-9c33-8b39811e57a3	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	3a58fc4e-a4c0-480b-8837-b09ed6e11ae4	2026-04-22 00:33:10.199139+00
f78594e2-a11f-4050-930d-6591caa4e1f3	a121d6a8-9f52-4104-b4a6-e224b1b42b71	3a58fc4e-a4c0-480b-8837-b09ed6e11ae4	2026-04-22 00:33:10.199146+00
5d81bc9a-2f3c-40b6-bba1-8e23cdd3c1b2	9c008964-93c8-442c-8fb4-6a070349c438	3a58fc4e-a4c0-480b-8837-b09ed6e11ae4	2026-04-22 00:33:10.199153+00
e20b8bf6-0710-48a1-9a22-274860f577e7	d802c736-b7a1-4e29-8c28-e93441f3a9e0	3a58fc4e-a4c0-480b-8837-b09ed6e11ae4	2026-04-22 00:33:10.199158+00
f6bf7172-fd8f-458a-b392-c7a029fdc60c	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	c16186d4-e70a-4d66-82d3-ca6730cb347c	2026-04-22 01:32:15.612293+00
c65ff195-e324-489e-be9f-6ceec1c62229	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	c16186d4-e70a-4d66-82d3-ca6730cb347c	2026-04-22 01:32:15.61241+00
60773a95-f842-401a-bf5d-751aa18d48fb	791344a0-6cc4-45a9-8ddf-e8eaef5adfbb	b56423f8-9429-4466-b38e-6ac142c93590	2026-04-22 11:03:43.73275+00
952d7959-7ce2-4aff-b012-31db37b0e03c	8ce6d6d9-50a3-4130-80cd-292b5d32b3fd	b56423f8-9429-4466-b38e-6ac142c93590	2026-04-22 11:03:43.732923+00
\.


--
-- Data for Name: routine_steps; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.routine_steps (id, routine_template_id, standard_of_done_id, sort_order, label, notes, created_at) FROM stdin;
b3dcf0a4-9ec2-4de5-af3a-b5f3ee92c0e9	a04dd3db-0035-4b52-aadd-8cd62decb4b8	\N	2	Make bed	\N	2026-04-15 22:36:30.574485+00
e871b358-386c-49b9-85cb-d3aed5271bd5	a04dd3db-0035-4b52-aadd-8cd62decb4b8	\N	5	Backpack check (homework/device/water bottle)	\N	2026-04-15 22:36:30.574578+00
47fae294-2a87-410e-97d9-60114e893d3d	a04dd3db-0035-4b52-aadd-8cd62decb4b8	\N	6	Lunch check (packed or plan confirmed)	\N	2026-04-15 22:36:30.574585+00
14fd4132-43f6-48f4-9dd4-16c6ef36af4f	a04dd3db-0035-4b52-aadd-8cd62decb4b8	\N	4	Breakfast + dish to sink/dishwasher	\N	2026-04-15 22:36:30.574588+00
fd8d3df0-4eb7-4edc-b480-c332e12c273a	a04dd3db-0035-4b52-aadd-8cd62decb4b8	\N	1	Get dressed	\N	2026-04-15 22:36:30.574591+00
9de1c4a9-a0b6-40d5-85c2-e59a885e82b9	a04dd3db-0035-4b52-aadd-8cd62decb4b8	\N	3	Hygiene: brush teeth, deodorant, hair	\N	2026-04-15 22:36:30.574594+00
d7c3aa10-ff36-4145-bdc3-fb02d41ccbfd	a0af505f-0804-478b-8be5-4faed310dd71	\N	2	Make bed	\N	2026-04-15 22:36:30.57508+00
c0d39fdc-10c0-46b7-bded-4d909c1a5b4c	a0af505f-0804-478b-8be5-4faed310dd71	\N	5	Backpack check (homework/water bottle)	\N	2026-04-15 22:36:30.575097+00
ecf79bf3-f63d-4e25-94f3-720e8dcb0931	a0af505f-0804-478b-8be5-4faed310dd71	\N	6	Shoes/coat at launch spot	\N	2026-04-15 22:36:30.575103+00
cb91c64c-b8b3-4960-b390-d0a2c95a97d2	a0af505f-0804-478b-8be5-4faed310dd71	\N	4	Breakfast + dish away	\N	2026-04-15 22:36:30.575108+00
ba75af56-5ff9-4bda-b055-f95afd1fb383	a0af505f-0804-478b-8be5-4faed310dd71	\N	1	Get dressed	\N	2026-04-15 22:36:30.575113+00
b38c987d-2788-42d0-97d5-8785a41f8f74	a0af505f-0804-478b-8be5-4faed310dd71	\N	3	Brush teeth	\N	2026-04-15 22:36:30.575118+00
2448c283-69a4-4153-8fb4-7354f480e533	d7fe7767-e806-4f0d-8f65-8ee9e3298ff7	\N	2	Make bed (blanket up, pillow placed)	\N	2026-04-15 22:36:30.575415+00
b3c586ad-c6cd-4d75-a9e5-f982efda86f8	d7fe7767-e806-4f0d-8f65-8ee9e3298ff7	\N	5	Backpack + shoes at launch spot	\N	2026-04-15 22:36:30.575425+00
f0e03641-db6c-4672-80e7-8aa522eb736c	d7fe7767-e806-4f0d-8f65-8ee9e3298ff7	\N	4	Breakfast + dish away	\N	2026-04-15 22:36:30.57543+00
cd338c89-3413-48b8-8647-040af5da3485	d7fe7767-e806-4f0d-8f65-8ee9e3298ff7	\N	1	Get dressed (clothes chosen night before)	\N	2026-04-15 22:36:30.575433+00
985f44be-ad8f-4aac-aecd-6600c7322568	d7fe7767-e806-4f0d-8f65-8ee9e3298ff7	\N	3	Brush teeth	\N	2026-04-15 22:36:30.575436+00
c2a7c0a2-ed51-48e1-87c4-59df0aaa160c	9e3df85b-20b8-4d93-9f9f-9e147c545e8a	\N	2	Homework / Study (30 to 45 min timer)	\N	2026-04-15 22:36:30.575725+00
4d32f7dd-f9b3-4d80-91e9-5d26595201f9	9e3df85b-20b8-4d93-9f9f-9e147c545e8a	\N	5	Permission check: screens / free time only after completed	\N	2026-04-15 22:36:30.575741+00
e52f7760-bc92-43f0-a47f-0eba211276e1	9e3df85b-20b8-4d93-9f9f-9e147c545e8a	\N	4	Dog Walks led (Memphis + Willie completed)	\N	2026-04-15 22:36:30.575748+00
bde4ff6a-b791-4afb-a920-61b041fd5b0e	9e3df85b-20b8-4d93-9f9f-9e147c545e8a	\N	1	Snack (15 min max)	\N	2026-04-15 22:36:30.575753+00
3400dbe0-230f-4f46-88fa-64dc60a6cd3a	9e3df85b-20b8-4d93-9f9f-9e147c545e8a	\N	3	10 minute zone reset (timer)	\N	2026-04-15 22:36:30.575758+00
68a899ac-6d9e-4378-afe2-f747237387a9	dc2259d9-0faf-4a86-84f3-e2ffdb3d2cf6	\N	2	Homework / Reading (25 to 35 min timer)	\N	2026-04-15 22:36:30.576038+00
c489924b-7582-4460-b525-69580c17c4c5	dc2259d9-0faf-4a86-84f3-e2ffdb3d2cf6	\N	4	Willie walk done if ODD day (with Sadie leading)	\N	2026-04-15 22:36:30.576051+00
c5a7abb1-b3a9-4590-be9d-be6b53719a00	dc2259d9-0faf-4a86-84f3-e2ffdb3d2cf6	\N	1	Snack (15 min max)	\N	2026-04-15 22:36:30.576056+00
5cfb392b-dcc0-4b13-92b9-c338b725c393	dc2259d9-0faf-4a86-84f3-e2ffdb3d2cf6	\N	3	10 minute zone reset (timer)	\N	2026-04-15 22:36:30.576061+00
dd0f2c48-e8c1-45af-922b-c878a00cd5f5	1a31c12b-5c07-49d5-8cd1-4b692f2f247a	\N	2	Homework / Reading (15 to 25 min timer)	\N	2026-04-15 22:36:30.57635+00
9cde1486-f8b2-48a6-ba3c-a98c7c83d3e7	1a31c12b-5c07-49d5-8cd1-4b692f2f247a	\N	4	Willie walk done if EVEN day (with Sadie leading)	\N	2026-04-15 22:36:30.576362+00
cac0c218-ff51-48bd-b9f2-47a6356dd61d	1a31c12b-5c07-49d5-8cd1-4b692f2f247a	\N	1	Snack (15 min max)	\N	2026-04-15 22:36:30.576366+00
07b77142-ff96-4d04-8e20-6d9871db7a00	1a31c12b-5c07-49d5-8cd1-4b692f2f247a	\N	3	10 minute zone reset (timer)	\N	2026-04-15 22:36:30.57637+00
fb625081-092a-4860-9630-103fc294d81a	6011dbc4-98e2-4eac-82d9-0651cc8e70bc	\N	2	Outfit set out	\N	2026-04-15 22:36:30.576655+00
7c1ae0f9-3c88-4f54-9203-b3b30576c1b9	6011dbc4-98e2-4eac-82d9-0651cc8e70bc	\N	5	Devices to charging station	\N	2026-04-15 22:36:30.576665+00
9137f569-9657-4b1d-8074-a627bd995c04	6011dbc4-98e2-4eac-82d9-0651cc8e70bc	\N	4	Hygiene	\N	2026-04-15 22:36:30.576669+00
784d9e7e-7e25-4487-919a-55ad64f643da	6011dbc4-98e2-4eac-82d9-0651cc8e70bc	\N	1	Pack backpack for tomorrow	\N	2026-04-15 22:36:30.576672+00
180157e0-0472-4694-b09f-c951336d2c64	6011dbc4-98e2-4eac-82d9-0651cc8e70bc	941ba724-0b8f-40af-9fc7-ff13b39bf055	3	Room reset (standard of done)	\N	2026-04-15 22:36:30.576676+00
29a2a7bd-67b7-4d2b-a564-e18d964ef31a	c76f07ed-2b46-4c86-9813-4cc258a7270b	\N	2	Outfit set out	\N	2026-04-15 22:36:30.576977+00
ca4412a2-4908-45cd-8d7c-e456c02cd46a	c76f07ed-2b46-4c86-9813-4cc258a7270b	\N	5	Devices to charging station	\N	2026-04-15 22:36:30.576995+00
e6f00a02-ac18-418f-a2b5-610ebf0c35d3	c76f07ed-2b46-4c86-9813-4cc258a7270b	\N	4	Brush teeth	\N	2026-04-15 22:36:30.577001+00
0fceefd0-7ed4-4a78-95e1-4d04b4456bf3	c76f07ed-2b46-4c86-9813-4cc258a7270b	\N	1	Pack backpack	\N	2026-04-15 22:36:30.577006+00
853f24a8-e9fa-4996-b60e-832d68bd3669	c76f07ed-2b46-4c86-9813-4cc258a7270b	941ba724-0b8f-40af-9fc7-ff13b39bf055	3	Room reset	\N	2026-04-15 22:36:30.577015+00
16d7845e-8e23-4f9f-a37e-3f70a0d4f1c5	05d11187-26b7-434c-a544-3bef2ef43750	\N	2	Backpack packed	\N	2026-04-15 22:36:30.577366+00
af6df6da-e200-4552-984a-cc651d9022ff	05d11187-26b7-434c-a544-3bef2ef43750	\N	5	Devices to charging station	\N	2026-04-15 22:36:30.577379+00
613280ef-ed0e-403e-9a11-b3b3b322f733	05d11187-26b7-434c-a544-3bef2ef43750	\N	4	Brush teeth	\N	2026-04-15 22:36:30.577384+00
8df04b1a-7563-4dd6-9a02-acf804239c8d	05d11187-26b7-434c-a544-3bef2ef43750	\N	1	Outfit set out (parent check if needed)	\N	2026-04-15 22:36:30.577387+00
97803153-c389-4939-b53e-50932eb89667	05d11187-26b7-434c-a544-3bef2ef43750	941ba724-0b8f-40af-9fc7-ff13b39bf055	3	Room reset (small scope)	\N	2026-04-15 22:36:30.57739+00
\.


--
-- Data for Name: routine_templates; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.routine_templates (id, family_id, routine_key, label, block_label, recurrence, due_time_weekday, due_time_weekend, owner_family_member_id, created_at, updated_at) FROM stdin;
a04dd3db-0035-4b52-aadd-8cd62decb4b8	fbe71860-a1a2-42b0-a0b5-df72017ced7c	morning	Sadie Morning	Morning	daily	07:25:00	09:00:00	6012f148-ae1c-40b4-838f-ef3bb7532e98	2026-04-15 22:36:30.57165+00	2026-04-15 22:36:30.57165+00
a0af505f-0804-478b-8be5-4faed310dd71	fbe71860-a1a2-42b0-a0b5-df72017ced7c	morning	Townes Morning	Morning	daily	07:25:00	09:00:00	c61d88de-857e-42d3-8116-575f6fabf14f	2026-04-15 22:36:30.572172+00	2026-04-15 22:36:30.572172+00
d7fe7767-e806-4f0d-8f65-8ee9e3298ff7	fbe71860-a1a2-42b0-a0b5-df72017ced7c	morning	River Morning	Morning	daily	07:25:00	09:00:00	e4d39e09-9d32-4aeb-adad-5014fe3bf6be	2026-04-15 22:36:30.572447+00	2026-04-15 22:36:30.572447+00
9e3df85b-20b8-4d93-9f9f-9e147c545e8a	fbe71860-a1a2-42b0-a0b5-df72017ced7c	after_school	Sadie After School	After School	weekdays	17:30:00	\N	6012f148-ae1c-40b4-838f-ef3bb7532e98	2026-04-15 22:36:30.572669+00	2026-04-15 22:36:30.572669+00
dc2259d9-0faf-4a86-84f3-e2ffdb3d2cf6	fbe71860-a1a2-42b0-a0b5-df72017ced7c	after_school	Townes After School	After School	weekdays	17:30:00	\N	c61d88de-857e-42d3-8116-575f6fabf14f	2026-04-15 22:36:30.572876+00	2026-04-15 22:36:30.572876+00
1a31c12b-5c07-49d5-8cd1-4b692f2f247a	fbe71860-a1a2-42b0-a0b5-df72017ced7c	after_school	River After School	After School	weekdays	17:30:00	\N	e4d39e09-9d32-4aeb-adad-5014fe3bf6be	2026-04-15 22:36:30.573028+00	2026-04-15 22:36:30.573028+00
6011dbc4-98e2-4eac-82d9-0651cc8e70bc	fbe71860-a1a2-42b0-a0b5-df72017ced7c	evening	Sadie Evening	Evening	daily	21:30:00	21:30:00	6012f148-ae1c-40b4-838f-ef3bb7532e98	2026-04-15 22:36:30.573189+00	2026-04-15 22:36:30.573189+00
c76f07ed-2b46-4c86-9813-4cc258a7270b	fbe71860-a1a2-42b0-a0b5-df72017ced7c	evening	Townes Evening	Evening	daily	21:00:00	21:00:00	c61d88de-857e-42d3-8116-575f6fabf14f	2026-04-15 22:36:30.57336+00	2026-04-15 22:36:30.57336+00
05d11187-26b7-434c-a544-3bef2ef43750	fbe71860-a1a2-42b0-a0b5-df72017ced7c	evening	River Evening	Evening	daily	20:30:00	20:30:00	e4d39e09-9d32-4aeb-adad-5014fe3bf6be	2026-04-15 22:36:30.573525+00	2026-04-15 22:36:30.573525+00
ed8ed1dd-4f65-4e03-9725-e29d9e33970f	fbe71860-a1a2-42b0-a0b5-df72017ced7c	clean_room	Clean room	Chores	daily	\N	\N	6012f148-ae1c-40b4-838f-ef3bb7532e98	2026-04-17 13:35:10.151098+00	2026-04-17 13:35:10.151098+00
6e3f7506-ec2f-4208-9afb-25fa023b4926	fbe71860-a1a2-42b0-a0b5-df72017ced7c	practice_piano	Practice piano 15 min	Chores	daily	\N	\N	6012f148-ae1c-40b4-838f-ef3bb7532e98	2026-04-17 13:35:10.151412+00	2026-04-17 13:35:10.151412+00
481d57f5-a4da-4adb-a637-6dcd4838dea4	fbe71860-a1a2-42b0-a0b5-df72017ced7c	unload_dishwasher	Unload dishwasher	Chores	daily	\N	\N	6012f148-ae1c-40b4-838f-ef3bb7532e98	2026-04-17 13:35:10.151489+00	2026-04-17 13:35:10.151489+00
f0addebf-28b9-4d88-895f-f93288e7d696	fbe71860-a1a2-42b0-a0b5-df72017ced7c	homework_checkin	Homework check-in	Chores	daily	\N	\N	6012f148-ae1c-40b4-838f-ef3bb7532e98	2026-04-17 13:35:10.151571+00	2026-04-17 13:35:10.151571+00
f1d13e13-2a8f-447e-8b42-199fbaf3f337	fbe71860-a1a2-42b0-a0b5-df72017ced7c	make_bed	Make bed	Chores	daily	\N	\N	c61d88de-857e-42d3-8116-575f6fabf14f	2026-04-17 13:35:10.15168+00	2026-04-17 13:35:10.15168+00
e5f42aa9-779f-442a-adef-9d48f0c95a48	fbe71860-a1a2-42b0-a0b5-df72017ced7c	unload_dishwasher	Unload dishwasher	Chores	daily	\N	\N	c61d88de-857e-42d3-8116-575f6fabf14f	2026-04-17 13:35:10.151743+00	2026-04-17 13:35:10.151744+00
337b435f-6d05-4603-ba9b-cea3e98301af	fbe71860-a1a2-42b0-a0b5-df72017ced7c	feed_biscuit	Feed Biscuit (dog)	Chores	daily	\N	\N	c61d88de-857e-42d3-8116-575f6fabf14f	2026-04-17 13:35:10.151815+00	2026-04-17 13:35:10.151815+00
094eed39-9d04-45e6-8439-d8c19e64808e	fbe71860-a1a2-42b0-a0b5-df72017ced7c	clean_backpack	Clean up backpack	Chores	daily	\N	\N	c61d88de-857e-42d3-8116-575f6fabf14f	2026-04-17 13:35:10.151844+00	2026-04-17 13:35:10.151844+00
a243e8aa-9e55-4e10-9f2d-a106f190456a	fbe71860-a1a2-42b0-a0b5-df72017ced7c	trash_out	Trash out	Chores	daily	\N	\N	889e7a80-05ec-4140-9c1b-4f1e7d2eb355	2026-04-17 13:35:10.1519+00	2026-04-17 13:35:10.1519+00
13871bc0-5eb1-47ab-ba14-c83794b86185	fbe71860-a1a2-42b0-a0b5-df72017ced7c	recycling_out	Recycling out	Chores	daily	\N	\N	889e7a80-05ec-4140-9c1b-4f1e7d2eb355	2026-04-17 13:35:10.151928+00	2026-04-17 13:35:10.151928+00
413f77ac-f18c-4d1e-8434-6b23a1121519	fbe71860-a1a2-42b0-a0b5-df72017ced7c	mow_lawn	Mow lawn (Sat)	Chores	daily	\N	\N	889e7a80-05ec-4140-9c1b-4f1e7d2eb355	2026-04-17 13:35:10.152047+00	2026-04-17 13:35:10.152047+00
7e1b7c66-72ac-465e-89f7-62e9e436d865	fbe71860-a1a2-42b0-a0b5-df72017ced7c	car_wash	Car wash weekly	Chores	daily	\N	\N	889e7a80-05ec-4140-9c1b-4f1e7d2eb355	2026-04-17 13:35:10.152083+00	2026-04-17 13:35:10.152084+00
00983854-c220-4505-81be-af909db08cb6	fbe71860-a1a2-42b0-a0b5-df72017ced7c	feed_fish	Feed fish	Chores	daily	\N	\N	e4d39e09-9d32-4aeb-adad-5014fe3bf6be	2026-04-17 13:35:10.152139+00	2026-04-17 13:35:10.152139+00
07555be6-8d63-401a-a448-9dd99e8b5e7c	fbe71860-a1a2-42b0-a0b5-df72017ced7c	tidy_toys	Tidy toys	Chores	daily	\N	\N	e4d39e09-9d32-4aeb-adad-5014fe3bf6be	2026-04-17 13:35:10.152166+00	2026-04-17 13:35:10.152166+00
18a1739c-2e4d-43c1-8477-bc8021f3c895	fbe71860-a1a2-42b0-a0b5-df72017ced7c	set_table	Set table	Chores	daily	\N	\N	e4d39e09-9d32-4aeb-adad-5014fe3bf6be	2026-04-17 13:35:10.152192+00	2026-04-17 13:35:10.152192+00
d683473c-97be-42da-a08e-b45b231d0d24	fbe71860-a1a2-42b0-a0b5-df72017ced7c	routine_1776628719184	Tester	Chores	daily	\N	\N	889e7a80-05ec-4140-9c1b-4f1e7d2eb355	2026-04-19 19:58:44.53942+00	2026-04-19 19:58:44.53942+00
\.


--
-- Data for Name: settlement_batches; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.settlement_batches (id, family_id, batch_key, status, submitted_at, exported_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: stale_data_alerts; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.stale_data_alerts (id, connector_account_id, entity_key, stale_since, acknowledged_at) FROM stdin;
\.


--
-- Data for Name: standards_of_done; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.standards_of_done (id, family_id, standard_key, label, checklist, notes, created_at, updated_at) FROM stdin;
941ba724-0b8f-40af-9fc7-ff13b39bf055	fbe71860-a1a2-42b0-a0b5-df72017ced7c	room_reset	Room Reset	["Floor mostly clear (no loose clothes/toys)", "Clothes in hamper", "Dishes/cups removed", "Trash in trash can", "Bed made (simple is fine)"]	Per-kid bedroom reset. Scope adjusts by age — River uses small scope.	2026-04-15 22:36:30.570274+00	2026-04-15 22:36:30.570274+00
d8c19bdb-530f-4929-b648-8126454223cf	fbe71860-a1a2-42b0-a0b5-df72017ced7c	common_area_closeout	Common Area Closeout	["Cups/plates/trash moved to kitchen", "Blankets folded to basket", "Toys/items put in bins", "Remotes returned", "Floor clear enough a robot vacuum could run"]	Living room + kitchen-adjacent shared spaces.	2026-04-15 22:36:30.570377+00	2026-04-15 22:36:30.570377+00
5c55949f-ae3f-497c-a9f8-d5a0e82b9a6f	fbe71860-a1a2-42b0-a0b5-df72017ced7c	trash	Trash	["Kitchen can checked; if ~75% full → taken out", "Bag tied, taken to outdoor bin", "New bag installed"]	Standalone — not embedded in a routine.	2026-04-15 22:36:30.570385+00	2026-04-15 22:36:30.570385+00
\.


--
-- Data for Name: sync_cursors; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.sync_cursors (id, connector_account_id, cursor_key, cursor_value, updated_at) FROM stdin;
\.


--
-- Data for Name: sync_jobs; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.sync_jobs (id, connector_account_id, entity_key, cadence_seconds, is_enabled, last_run_started_at, last_run_finished_at, next_run_at, created_at) FROM stdin;
\.


--
-- Data for Name: sync_runs; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.sync_runs (id, sync_job_id, started_at, finished_at, status, records_processed, error_message) FROM stdin;
\.


--
-- Data for Name: task_assignment_rules; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.task_assignment_rules (id, task_template_id, rule_type, rule_params, priority, created_at) FROM stdin;
96c9781a-a087-4a59-81be-a482345c6309	b6a28262-808a-4e5e-9821-eb781c008033	fixed	{"family_member_id": "6012f148-ae1c-40b4-838f-ef3bb7532e98"}	0	2026-04-15 22:36:30.581262+00
3e326a37-2327-42be-864c-a381d22f71dd	0325a8af-a2e1-45d8-a99c-84801b325c5b	fixed	{"family_member_id": "c61d88de-857e-42d3-8116-575f6fabf14f"}	0	2026-04-15 22:36:30.581678+00
f1795d5b-4a89-4e2c-80d8-e214e9f563ae	1924f6a5-b042-4d26-b063-e1e3b197cbb7	fixed	{"family_member_id": "e4d39e09-9d32-4aeb-adad-5014fe3bf6be"}	0	2026-04-15 22:36:30.581958+00
a42f202f-b846-4f97-8354-7acce31ee37b	4eb6433d-ce06-41c8-a8ed-3d098a638f64	day_parity	{"odd": "c61d88de-857e-42d3-8116-575f6fabf14f", "even": "e4d39e09-9d32-4aeb-adad-5014fe3bf6be"}	0	2026-04-15 22:36:30.582182+00
fb85adeb-67b1-4433-84e9-fa487a61be5a	8b06be41-c2b8-4a4b-92cd-b194337897ff	dog_walk_assistant	{"odd": "c61d88de-857e-42d3-8116-575f6fabf14f", "even": "e4d39e09-9d32-4aeb-adad-5014fe3bf6be", "lead": "6012f148-ae1c-40b4-838f-ef3bb7532e98"}	0	2026-04-15 22:36:30.582402+00
702e4416-4db8-41d6-9b2a-6233460244fd	7e48ddc4-ef04-4e01-9344-391b61c080de	fixed	{"family_member_id": "6012f148-ae1c-40b4-838f-ef3bb7532e98"}	0	2026-04-15 22:36:30.582653+00
1d781287-2b61-4a4c-a56b-9614aa314846	5d828b46-d434-4124-98b0-7deb6a5ea8c8	week_rotation	{"owner": "c61d88de-857e-42d3-8116-575f6fabf14f", "assistant": "e4d39e09-9d32-4aeb-adad-5014fe3bf6be", "anchor_date": "2026-01-05", "period_weeks": 8}	0	2026-04-15 22:36:30.582884+00
\.


--
-- Data for Name: task_completions; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.task_completions (id, task_occurrence_id, completed_by, completed_at, completion_mode, notes, created_at) FROM stdin;
\.


--
-- Data for Name: task_exceptions; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.task_exceptions (id, task_occurrence_id, reason, created_by, created_at) FROM stdin;
\.


--
-- Data for Name: task_notes; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.task_notes (id, task_occurrence_id, author_id, body, created_at) FROM stdin;
\.


--
-- Data for Name: task_occurrences; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.task_occurrences (id, family_id, task_template_id, routine_template_id, assigned_to, occurrence_date, due_at, status, generated_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: task_templates; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.task_templates (id, family_id, template_key, label, recurrence, due_time, standard_of_done_id, notes, is_active, created_at, updated_at) FROM stdin;
4eb6433d-ce06-41c8-a8ed-3d098a638f64	fbe71860-a1a2-42b0-a0b5-df72017ced7c	common_area_closeout	Common Area Closeout (rotating)	daily	19:30:00	d8c19bdb-530f-4929-b648-8126454223cf	ODD day = Townes, EVEN day = River. Charter §rotating chore.	t	2026-04-15 22:36:30.577952+00	2026-04-15 22:36:30.577953+00
b6a28262-808a-4e5e-9821-eb781c008033	fbe71860-a1a2-42b0-a0b5-df72017ced7c	dishwasher_captain	Dishwasher Captain (Sadie)	weekdays	20:00:00	\N	Sadie ownership chore. Choose Option A (load + run after dinner) or Option B (unload at 7:10 AM) and keep consistent for 6-8 weeks.	t	2026-04-15 22:36:30.578142+00	2026-04-15 22:36:30.578142+00
5d828b46-d434-4124-98b0-7deb6a5ea8c8	fbe71860-a1a2-42b0-a0b5-df72017ced7c	poop_patrol	Backyard Poop Patrol	weekly	11:00:00	\N	Saturday during Power 60. Owner/assistant swap every 8 weeks.	t	2026-04-15 22:36:30.578155+00	2026-04-15 22:36:30.578155+00
7e48ddc4-ef04-4e01-9344-391b61c080de	fbe71860-a1a2-42b0-a0b5-df72017ced7c	power_60	Power 60 (House Reset)	weekly	11:00:00	\N	Saturday 10 to 11 AM. Sadie bathroom, Townes vacuum, River dust.	t	2026-04-15 22:36:30.578162+00	2026-04-15 22:36:30.578162+00
1924f6a5-b042-4d26-b063-e1e3b197cbb7	fbe71860-a1a2-42b0-a0b5-df72017ced7c	living_room_reset	Living Room Reset Captain (River)	weekdays	19:30:00	\N	River ownership chore. Blankets, toys, dishes to kitchen.	t	2026-04-15 22:36:30.578169+00	2026-04-15 22:36:30.578169+00
8b06be41-c2b8-4a4b-92cd-b194337897ff	fbe71860-a1a2-42b0-a0b5-df72017ced7c	dog_walks	Dog Walks (Sadie lead)	daily	19:30:00	\N	Sadie lead. Memphis 15 to 20 min, Willie 10 to 15 min. Assistant rule: ODD day = Townes, EVEN day = River.	t	2026-04-15 22:36:30.578178+00	2026-04-15 22:36:30.578178+00
0325a8af-a2e1-45d8-a99c-84801b325c5b	fbe71860-a1a2-42b0-a0b5-df72017ced7c	table_captain	Table Captain + Sweep (Townes)	weekdays	20:00:00	\N	Townes ownership chore. Set table 6:15 PM, clear after dinner 7:45 PM, sweep kitchen/dining 8:00 PM.	t	2026-04-15 22:36:30.578182+00	2026-04-15 22:36:30.578182+00
\.


--
-- Data for Name: time_blocks; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.time_blocks (id, family_id, block_key, label, start_offset, end_offset, applies_weekday, applies_weekend, sort_order, created_at) FROM stdin;
8bfc8f15-0f38-432c-a571-0bba2c09abd6	fbe71860-a1a2-42b0-a0b5-df72017ced7c	morning	Morning Routine	06:30:00	07:30:00	t	t	10	2026-04-15 22:36:30.571082+00
8d436d3a-9b3e-416c-a513-6d3459cf46c9	fbe71860-a1a2-42b0-a0b5-df72017ced7c	after_school	After School Routine	15:00:00	17:30:00	t	f	20	2026-04-15 22:36:30.571178+00
c6e7894d-942b-49a9-a9db-7046759a795e	fbe71860-a1a2-42b0-a0b5-df72017ced7c	evening	Evening Routine	20:00:00	21:30:00	t	t	30	2026-04-15 22:36:30.571186+00
c8f9c67c-b384-4df8-acd0-301940a75e34	fbe71860-a1a2-42b0-a0b5-df72017ced7c	power_60	Saturday Power 60	10:00:00	11:00:00	f	t	40	2026-04-15 22:36:30.57119+00
\.


--
-- Data for Name: travel_estimates; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.travel_estimates (id, family_id, origin, destination, requested_for, duration_sec, distance_meters, metadata, fetched_at) FROM stdin;
\.


--
-- Data for Name: user_family_memberships; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.user_family_memberships (id, user_account_id, family_id, family_member_id, role_tier_id, is_primary, created_at) FROM stdin;
\.


--
-- Data for Name: user_preferences; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.user_preferences (id, user_account_id, preference_key, preference_value, updated_at) FROM stdin;
\.


--
-- Data for Name: work_context_events; Type: TABLE DATA; Schema: scout; Owner: -
--

COPY scout.work_context_events (id, family_id, user_account_id, source, event_type, starts_at, ends_at, pressure_score, metadata, imported_at) FROM stdin;
\.


--
-- Name: _scout_migrations _scout_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public._scout_migrations
    ADD CONSTRAINT _scout_migrations_pkey PRIMARY KEY (filename);


--
-- Name: activity_records activity_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_records
    ADD CONSTRAINT activity_records_pkey PRIMARY KEY (id);


--
-- Name: ai_conversations ai_conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_conversations
    ADD CONSTRAINT ai_conversations_pkey PRIMARY KEY (id);


--
-- Name: ai_daily_insights ai_daily_insights_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_daily_insights
    ADD CONSTRAINT ai_daily_insights_pkey PRIMARY KEY (id);


--
-- Name: ai_homework_sessions ai_homework_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_homework_sessions
    ADD CONSTRAINT ai_homework_sessions_pkey PRIMARY KEY (id);


--
-- Name: ai_messages ai_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_messages
    ADD CONSTRAINT ai_messages_pkey PRIMARY KEY (id);


--
-- Name: ai_tool_audit ai_tool_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_tool_audit
    ADD CONSTRAINT ai_tool_audit_pkey PRIMARY KEY (id);


--
-- Name: allowance_ledger allowance_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.allowance_ledger
    ADD CONSTRAINT allowance_ledger_pkey PRIMARY KEY (id);


--
-- Name: bills bills_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bills
    ADD CONSTRAINT bills_pkey PRIMARY KEY (id);


--
-- Name: chore_templates chore_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chore_templates
    ADD CONSTRAINT chore_templates_pkey PRIMARY KEY (id);


--
-- Name: connector_configs connector_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.connector_configs
    ADD CONSTRAINT connector_configs_pkey PRIMARY KEY (id);


--
-- Name: connector_mappings connector_mappings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.connector_mappings
    ADD CONSTRAINT connector_mappings_pkey PRIMARY KEY (id);


--
-- Name: daily_wins daily_wins_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.daily_wins
    ADD CONSTRAINT daily_wins_pkey PRIMARY KEY (id);


--
-- Name: dietary_preferences dietary_preferences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dietary_preferences
    ADD CONSTRAINT dietary_preferences_pkey PRIMARY KEY (id);


--
-- Name: event_attendees event_attendees_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_attendees
    ADD CONSTRAINT event_attendees_pkey PRIMARY KEY (id);


--
-- Name: events events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (id);


--
-- Name: families families_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.families
    ADD CONSTRAINT families_pkey PRIMARY KEY (id);


--
-- Name: family_members family_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.family_members
    ADD CONSTRAINT family_members_pkey PRIMARY KEY (id);


--
-- Name: family_memories family_memories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.family_memories
    ADD CONSTRAINT family_memories_pkey PRIMARY KEY (id);


--
-- Name: grocery_items grocery_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grocery_items
    ADD CONSTRAINT grocery_items_pkey PRIMARY KEY (id);


--
-- Name: health_summaries health_summaries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_summaries
    ADD CONSTRAINT health_summaries_pkey PRIMARY KEY (id);


--
-- Name: meal_plans meal_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meal_plans
    ADD CONSTRAINT meal_plans_pkey PRIMARY KEY (id);


--
-- Name: meal_reviews meal_reviews_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meal_reviews
    ADD CONSTRAINT meal_reviews_pkey PRIMARY KEY (id);


--
-- Name: meals meals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meals
    ADD CONSTRAINT meals_pkey PRIMARY KEY (id);


--
-- Name: member_config member_config_family_member_id_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.member_config
    ADD CONSTRAINT member_config_family_member_id_key_key UNIQUE (family_member_id, key);


--
-- Name: member_config member_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.member_config
    ADD CONSTRAINT member_config_pkey PRIMARY KEY (id);


--
-- Name: notes notes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notes
    ADD CONSTRAINT notes_pkey PRIMARY KEY (id);


--
-- Name: parent_action_items parent_action_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parent_action_items
    ADD CONSTRAINT parent_action_items_pkey PRIMARY KEY (id);


--
-- Name: personal_tasks personal_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personal_tasks
    ADD CONSTRAINT personal_tasks_pkey PRIMARY KEY (id);


--
-- Name: planner_bundle_applies planner_bundle_applies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planner_bundle_applies
    ADD CONSTRAINT planner_bundle_applies_pkey PRIMARY KEY (id);


--
-- Name: purchase_requests purchase_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_requests
    ADD CONSTRAINT purchase_requests_pkey PRIMARY KEY (id);


--
-- Name: role_tier_overrides role_tier_overrides_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_tier_overrides
    ADD CONSTRAINT role_tier_overrides_pkey PRIMARY KEY (id);


--
-- Name: role_tiers role_tiers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_tiers
    ADD CONSTRAINT role_tiers_pkey PRIMARY KEY (id);


--
-- Name: routine_steps routine_steps_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.routine_steps
    ADD CONSTRAINT routine_steps_pkey PRIMARY KEY (id);


--
-- Name: routines routines_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.routines
    ADD CONSTRAINT routines_pkey PRIMARY KEY (id);


--
-- Name: scout_anomaly_suppressions scout_anomaly_suppressions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scout_anomaly_suppressions
    ADD CONSTRAINT scout_anomaly_suppressions_pkey PRIMARY KEY (id);


--
-- Name: scout_mcp_tokens scout_mcp_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scout_mcp_tokens
    ADD CONSTRAINT scout_mcp_tokens_pkey PRIMARY KEY (id);


--
-- Name: scout_scheduled_runs scout_scheduled_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scout_scheduled_runs
    ADD CONSTRAINT scout_scheduled_runs_pkey PRIMARY KEY (id);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);


--
-- Name: task_instance_step_completions task_instance_step_completions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_instance_step_completions
    ADD CONSTRAINT task_instance_step_completions_pkey PRIMARY KEY (id);


--
-- Name: task_instances task_instances_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_instances
    ADD CONSTRAINT task_instances_pkey PRIMARY KEY (id);


--
-- Name: daily_wins uq_daily_wins_member_date; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.daily_wins
    ADD CONSTRAINT uq_daily_wins_member_date UNIQUE (family_member_id, win_date);


--
-- Name: dietary_preferences uq_dietary_preferences_member_label; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dietary_preferences
    ADD CONSTRAINT uq_dietary_preferences_member_label UNIQUE (family_member_id, label);


--
-- Name: event_attendees uq_event_attendees_event_member; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_attendees
    ADD CONSTRAINT uq_event_attendees_event_member UNIQUE (event_id, family_member_id);


--
-- Name: health_summaries uq_health_summaries_member_date; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_summaries
    ADD CONSTRAINT uq_health_summaries_member_date UNIQUE (family_member_id, summary_date);


--
-- Name: meal_plans uq_meal_plans_family_week; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meal_plans
    ADD CONSTRAINT uq_meal_plans_family_week UNIQUE (family_id, week_start);


--
-- Name: meals uq_meals_family_date_type; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meals
    ADD CONSTRAINT uq_meals_family_date_type UNIQUE (family_id, meal_date, meal_type);


--
-- Name: role_tier_overrides uq_role_tier_overrides_member; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_tier_overrides
    ADD CONSTRAINT uq_role_tier_overrides_member UNIQUE (family_member_id);


--
-- Name: role_tiers uq_role_tiers_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_tiers
    ADD CONSTRAINT uq_role_tiers_name UNIQUE (name);


--
-- Name: routine_steps uq_routine_steps_order; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.routine_steps
    ADD CONSTRAINT uq_routine_steps_order UNIQUE (routine_id, sort_order);


--
-- Name: sessions uq_sessions_token; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT uq_sessions_token UNIQUE (token);


--
-- Name: task_instance_step_completions uq_step_completions_instance_step; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_instance_step_completions
    ADD CONSTRAINT uq_step_completions_instance_step UNIQUE (task_instance_id, routine_step_id);


--
-- Name: task_instances uq_task_instances_chore; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_instances
    ADD CONSTRAINT uq_task_instances_chore UNIQUE (family_member_id, chore_template_id, instance_date);


--
-- Name: task_instances uq_task_instances_routine; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_instances
    ADD CONSTRAINT uq_task_instances_routine UNIQUE (family_member_id, routine_id, instance_date);


--
-- Name: user_accounts user_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_accounts
    ADD CONSTRAINT user_accounts_pkey PRIMARY KEY (id);


--
-- Name: weekly_meal_plans weekly_meal_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_meal_plans
    ADD CONSTRAINT weekly_meal_plans_pkey PRIMARY KEY (id);


--
-- Name: activity_events activity_events_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.activity_events
    ADD CONSTRAINT activity_events_pkey PRIMARY KEY (id);


--
-- Name: affirmation_delivery_log affirmation_delivery_log_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.affirmation_delivery_log
    ADD CONSTRAINT affirmation_delivery_log_pkey PRIMARY KEY (id);


--
-- Name: affirmation_feedback affirmation_feedback_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.affirmation_feedback
    ADD CONSTRAINT affirmation_feedback_pkey PRIMARY KEY (id);


--
-- Name: affirmations affirmations_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.affirmations
    ADD CONSTRAINT affirmations_pkey PRIMARY KEY (id);


--
-- Name: allowance_periods allowance_periods_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.allowance_periods
    ADD CONSTRAINT allowance_periods_pkey PRIMARY KEY (id);


--
-- Name: allowance_results allowance_results_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.allowance_results
    ADD CONSTRAINT allowance_results_pkey PRIMARY KEY (id);


--
-- Name: bill_snapshots bill_snapshots_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.bill_snapshots
    ADD CONSTRAINT bill_snapshots_pkey PRIMARY KEY (id);


--
-- Name: budget_snapshots budget_snapshots_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.budget_snapshots
    ADD CONSTRAINT budget_snapshots_pkey PRIMARY KEY (id);


--
-- Name: calendar_exports calendar_exports_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.calendar_exports
    ADD CONSTRAINT calendar_exports_pkey PRIMARY KEY (id);


--
-- Name: connector_accounts connector_accounts_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.connector_accounts
    ADD CONSTRAINT connector_accounts_pkey PRIMARY KEY (id);


--
-- Name: connector_event_log connector_event_log_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.connector_event_log
    ADD CONSTRAINT connector_event_log_pkey PRIMARY KEY (id);


--
-- Name: connectors connectors_connector_key_key; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.connectors
    ADD CONSTRAINT connectors_connector_key_key UNIQUE (connector_key);


--
-- Name: connectors connectors_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.connectors
    ADD CONSTRAINT connectors_pkey PRIMARY KEY (id);


--
-- Name: daily_win_results daily_win_results_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.daily_win_results
    ADD CONSTRAINT daily_win_results_pkey PRIMARY KEY (id);


--
-- Name: device_registrations device_registrations_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.device_registrations
    ADD CONSTRAINT device_registrations_pkey PRIMARY KEY (id);


--
-- Name: external_calendar_events external_calendar_events_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.external_calendar_events
    ADD CONSTRAINT external_calendar_events_pkey PRIMARY KEY (id);


--
-- Name: greenlight_exports greenlight_exports_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.greenlight_exports
    ADD CONSTRAINT greenlight_exports_pkey PRIMARY KEY (id);


--
-- Name: home_assets home_assets_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.home_assets
    ADD CONSTRAINT home_assets_pkey PRIMARY KEY (id);


--
-- Name: home_zones home_zones_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.home_zones
    ADD CONSTRAINT home_zones_pkey PRIMARY KEY (id);


--
-- Name: household_rules household_rules_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.household_rules
    ADD CONSTRAINT household_rules_pkey PRIMARY KEY (id);


--
-- Name: maintenance_instances maintenance_instances_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.maintenance_instances
    ADD CONSTRAINT maintenance_instances_pkey PRIMARY KEY (id);


--
-- Name: maintenance_templates maintenance_templates_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.maintenance_templates
    ADD CONSTRAINT maintenance_templates_pkey PRIMARY KEY (id);


--
-- Name: meal_transformations meal_transformations_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.meal_transformations
    ADD CONSTRAINT meal_transformations_pkey PRIMARY KEY (id);


--
-- Name: nudge_dispatch_items nudge_dispatch_items_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.nudge_dispatch_items
    ADD CONSTRAINT nudge_dispatch_items_pkey PRIMARY KEY (id);


--
-- Name: nudge_dispatches nudge_dispatches_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.nudge_dispatches
    ADD CONSTRAINT nudge_dispatches_pkey PRIMARY KEY (id);


--
-- Name: nudge_rules nudge_rules_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.nudge_rules
    ADD CONSTRAINT nudge_rules_pkey PRIMARY KEY (id);


--
-- Name: permissions permissions_permission_key_key; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.permissions
    ADD CONSTRAINT permissions_permission_key_key UNIQUE (permission_key);


--
-- Name: permissions permissions_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.permissions
    ADD CONSTRAINT permissions_pkey PRIMARY KEY (id);


--
-- Name: project_budget_entries project_budget_entries_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.project_budget_entries
    ADD CONSTRAINT project_budget_entries_pkey PRIMARY KEY (id);


--
-- Name: project_milestones project_milestones_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.project_milestones
    ADD CONSTRAINT project_milestones_pkey PRIMARY KEY (id);


--
-- Name: project_tasks project_tasks_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.project_tasks
    ADD CONSTRAINT project_tasks_pkey PRIMARY KEY (id);


--
-- Name: project_template_tasks project_template_tasks_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.project_template_tasks
    ADD CONSTRAINT project_template_tasks_pkey PRIMARY KEY (id);


--
-- Name: project_templates project_templates_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.project_templates
    ADD CONSTRAINT project_templates_pkey PRIMARY KEY (id);


--
-- Name: projects projects_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.projects
    ADD CONSTRAINT projects_pkey PRIMARY KEY (id);


--
-- Name: push_deliveries push_deliveries_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.push_deliveries
    ADD CONSTRAINT push_deliveries_pkey PRIMARY KEY (id);


--
-- Name: push_devices push_devices_expo_push_token_key; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.push_devices
    ADD CONSTRAINT push_devices_expo_push_token_key UNIQUE (expo_push_token);


--
-- Name: push_devices push_devices_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.push_devices
    ADD CONSTRAINT push_devices_pkey PRIMARY KEY (id);


--
-- Name: quiet_hours_family quiet_hours_family_family_id_key; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.quiet_hours_family
    ADD CONSTRAINT quiet_hours_family_family_id_key UNIQUE (family_id);


--
-- Name: quiet_hours_family quiet_hours_family_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.quiet_hours_family
    ADD CONSTRAINT quiet_hours_family_pkey PRIMARY KEY (id);


--
-- Name: reward_extras_catalog reward_extras_catalog_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.reward_extras_catalog
    ADD CONSTRAINT reward_extras_catalog_pkey PRIMARY KEY (id);


--
-- Name: reward_ledger_entries reward_ledger_entries_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.reward_ledger_entries
    ADD CONSTRAINT reward_ledger_entries_pkey PRIMARY KEY (id);


--
-- Name: reward_policies reward_policies_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.reward_policies
    ADD CONSTRAINT reward_policies_pkey PRIMARY KEY (id);


--
-- Name: role_tier_permissions role_tier_permissions_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.role_tier_permissions
    ADD CONSTRAINT role_tier_permissions_pkey PRIMARY KEY (id);


--
-- Name: routine_steps routine_steps_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.routine_steps
    ADD CONSTRAINT routine_steps_pkey PRIMARY KEY (id);


--
-- Name: routine_templates routine_templates_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.routine_templates
    ADD CONSTRAINT routine_templates_pkey PRIMARY KEY (id);


--
-- Name: settlement_batches settlement_batches_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.settlement_batches
    ADD CONSTRAINT settlement_batches_pkey PRIMARY KEY (id);


--
-- Name: stale_data_alerts stale_data_alerts_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.stale_data_alerts
    ADD CONSTRAINT stale_data_alerts_pkey PRIMARY KEY (id);


--
-- Name: standards_of_done standards_of_done_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.standards_of_done
    ADD CONSTRAINT standards_of_done_pkey PRIMARY KEY (id);


--
-- Name: sync_cursors sync_cursors_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.sync_cursors
    ADD CONSTRAINT sync_cursors_pkey PRIMARY KEY (id);


--
-- Name: sync_jobs sync_jobs_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.sync_jobs
    ADD CONSTRAINT sync_jobs_pkey PRIMARY KEY (id);


--
-- Name: sync_runs sync_runs_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.sync_runs
    ADD CONSTRAINT sync_runs_pkey PRIMARY KEY (id);


--
-- Name: task_assignment_rules task_assignment_rules_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.task_assignment_rules
    ADD CONSTRAINT task_assignment_rules_pkey PRIMARY KEY (id);


--
-- Name: task_completions task_completions_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.task_completions
    ADD CONSTRAINT task_completions_pkey PRIMARY KEY (id);


--
-- Name: task_exceptions task_exceptions_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.task_exceptions
    ADD CONSTRAINT task_exceptions_pkey PRIMARY KEY (id);


--
-- Name: task_notes task_notes_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.task_notes
    ADD CONSTRAINT task_notes_pkey PRIMARY KEY (id);


--
-- Name: task_occurrences task_occurrences_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.task_occurrences
    ADD CONSTRAINT task_occurrences_pkey PRIMARY KEY (id);


--
-- Name: task_templates task_templates_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.task_templates
    ADD CONSTRAINT task_templates_pkey PRIMARY KEY (id);


--
-- Name: time_blocks time_blocks_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.time_blocks
    ADD CONSTRAINT time_blocks_pkey PRIMARY KEY (id);


--
-- Name: travel_estimates travel_estimates_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.travel_estimates
    ADD CONSTRAINT travel_estimates_pkey PRIMARY KEY (id);


--
-- Name: allowance_periods uq_allowance_period; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.allowance_periods
    ADD CONSTRAINT uq_allowance_period UNIQUE (family_id, start_date, end_date);


--
-- Name: allowance_results uq_allowance_result; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.allowance_results
    ADD CONSTRAINT uq_allowance_result UNIQUE (allowance_period_id, family_member_id);


--
-- Name: bill_snapshots uq_bill_snapshot; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.bill_snapshots
    ADD CONSTRAINT uq_bill_snapshot UNIQUE (family_id, source, as_of_date, bill_key);


--
-- Name: budget_snapshots uq_budget_snapshot; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.budget_snapshots
    ADD CONSTRAINT uq_budget_snapshot UNIQUE (family_id, source, as_of_date, category_key);


--
-- Name: daily_win_results uq_daily_win_result; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.daily_win_results
    ADD CONSTRAINT uq_daily_win_result UNIQUE (family_member_id, for_date);


--
-- Name: device_registrations uq_device_token; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.device_registrations
    ADD CONSTRAINT uq_device_token UNIQUE (device_token);


--
-- Name: household_rules uq_household_rule; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.household_rules
    ADD CONSTRAINT uq_household_rule UNIQUE (family_id, rule_key);


--
-- Name: nudge_dispatch_items uq_nudge_dispatch_items_source_dedupe_key; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.nudge_dispatch_items
    ADD CONSTRAINT uq_nudge_dispatch_items_source_dedupe_key UNIQUE (source_dedupe_key);


--
-- Name: nudge_rules uq_nudge_rules_family_name; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.nudge_rules
    ADD CONSTRAINT uq_nudge_rules_family_name UNIQUE (family_id, name);


--
-- Name: reward_extras_catalog uq_reward_extra; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.reward_extras_catalog
    ADD CONSTRAINT uq_reward_extra UNIQUE (family_id, extra_key);


--
-- Name: reward_policies uq_reward_policy; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.reward_policies
    ADD CONSTRAINT uq_reward_policy UNIQUE (family_id, family_member_id, policy_key, effective_from);


--
-- Name: role_tier_permissions uq_role_tier_permissions; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.role_tier_permissions
    ADD CONSTRAINT uq_role_tier_permissions UNIQUE (role_tier_id, permission_id);


--
-- Name: routine_steps uq_routine_step_order; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.routine_steps
    ADD CONSTRAINT uq_routine_step_order UNIQUE (routine_template_id, sort_order);


--
-- Name: routine_templates uq_routine_template; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.routine_templates
    ADD CONSTRAINT uq_routine_template UNIQUE (family_id, routine_key, owner_family_member_id);


--
-- Name: settlement_batches uq_settlement_batch; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.settlement_batches
    ADD CONSTRAINT uq_settlement_batch UNIQUE (family_id, batch_key);


--
-- Name: stale_data_alerts uq_stale_alert; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.stale_data_alerts
    ADD CONSTRAINT uq_stale_alert UNIQUE (connector_account_id, entity_key, stale_since);


--
-- Name: standards_of_done uq_standard_of_done; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.standards_of_done
    ADD CONSTRAINT uq_standard_of_done UNIQUE (family_id, standard_key);


--
-- Name: sync_cursors uq_sync_cursor; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.sync_cursors
    ADD CONSTRAINT uq_sync_cursor UNIQUE (connector_account_id, cursor_key);


--
-- Name: task_templates uq_task_template; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.task_templates
    ADD CONSTRAINT uq_task_template UNIQUE (family_id, template_key);


--
-- Name: time_blocks uq_time_block; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.time_blocks
    ADD CONSTRAINT uq_time_block UNIQUE (family_id, block_key);


--
-- Name: user_family_memberships uq_user_family_membership; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.user_family_memberships
    ADD CONSTRAINT uq_user_family_membership UNIQUE (user_account_id, family_id);


--
-- Name: user_preferences uq_user_preferences; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.user_preferences
    ADD CONSTRAINT uq_user_preferences UNIQUE (user_account_id, preference_key);


--
-- Name: user_family_memberships user_family_memberships_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.user_family_memberships
    ADD CONSTRAINT user_family_memberships_pkey PRIMARY KEY (id);


--
-- Name: user_preferences user_preferences_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.user_preferences
    ADD CONSTRAINT user_preferences_pkey PRIMARY KEY (id);


--
-- Name: work_context_events work_context_events_pkey; Type: CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.work_context_events
    ADD CONSTRAINT work_context_events_pkey PRIMARY KEY (id);


--
-- Name: idx_activity_records_family_started; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_records_family_started ON public.activity_records USING btree (family_id, started_at DESC);


--
-- Name: idx_activity_records_member_started; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_records_member_started ON public.activity_records USING btree (family_member_id, started_at DESC);


--
-- Name: idx_ai_conversations_family; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_conversations_family ON public.ai_conversations USING btree (family_id);


--
-- Name: idx_ai_conversations_family_updated; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_conversations_family_updated ON public.ai_conversations USING btree (family_id, updated_at DESC);


--
-- Name: idx_ai_conversations_kind; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_conversations_kind ON public.ai_conversations USING btree (family_id, conversation_kind, updated_at DESC);


--
-- Name: idx_ai_conversations_member; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_conversations_member ON public.ai_conversations USING btree (family_member_id, updated_at DESC);


--
-- Name: idx_ai_conversations_pinned; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_conversations_pinned ON public.ai_conversations USING btree (family_member_id, last_active_at DESC) WHERE (is_pinned = true);


--
-- Name: idx_ai_conversations_resume; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_conversations_resume ON public.ai_conversations USING btree (family_member_id, status, last_active_at DESC);


--
-- Name: idx_ai_messages_conversation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_messages_conversation ON public.ai_messages USING btree (conversation_id, created_at);


--
-- Name: idx_ai_messages_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_messages_created_at ON public.ai_messages USING btree (created_at);


--
-- Name: idx_ai_tool_audit_actor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_tool_audit_actor ON public.ai_tool_audit USING btree (actor_member_id, created_at DESC);


--
-- Name: idx_ai_tool_audit_family; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_tool_audit_family ON public.ai_tool_audit USING btree (family_id, created_at DESC);


--
-- Name: idx_ai_tool_audit_tool; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_tool_audit_tool ON public.ai_tool_audit USING btree (tool_name, created_at DESC);


--
-- Name: idx_allowance_ledger_family_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_allowance_ledger_family_id ON public.allowance_ledger USING btree (family_id);


--
-- Name: idx_allowance_ledger_member_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_allowance_ledger_member_type ON public.allowance_ledger USING btree (family_member_id, entry_type);


--
-- Name: idx_anomaly_suppressions_family_signature; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_anomaly_suppressions_family_signature ON public.scout_anomaly_suppressions USING btree (family_id, anomaly_type, signature);


--
-- Name: idx_anomaly_suppressions_family_until; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_anomaly_suppressions_family_until ON public.scout_anomaly_suppressions USING btree (family_id, suppress_until);


--
-- Name: idx_bills_created_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bills_created_by ON public.bills USING btree (created_by);


--
-- Name: idx_bills_family_due_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bills_family_due_date ON public.bills USING btree (family_id, due_date);


--
-- Name: idx_bills_family_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bills_family_status ON public.bills USING btree (family_id, status);


--
-- Name: idx_chore_templates_family_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chore_templates_family_id ON public.chore_templates USING btree (family_id);


--
-- Name: idx_connector_configs_connector_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_connector_configs_connector_name ON public.connector_configs USING btree (connector_name);


--
-- Name: idx_connector_configs_family_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_connector_configs_family_id ON public.connector_configs USING btree (family_id);


--
-- Name: idx_connector_configs_family_member_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_connector_configs_family_member_id ON public.connector_configs USING btree (family_member_id);


--
-- Name: idx_connector_mappings_family; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_connector_mappings_family ON public.connector_mappings USING btree (family_id);


--
-- Name: idx_connector_mappings_internal_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_connector_mappings_internal_lookup ON public.connector_mappings USING btree (internal_table, internal_id);


--
-- Name: idx_daily_wins_family_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_daily_wins_family_id ON public.daily_wins USING btree (family_id);


--
-- Name: idx_event_attendees_family_member_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_attendees_family_member_id ON public.event_attendees USING btree (family_member_id);


--
-- Name: idx_events_created_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_events_created_by ON public.events USING btree (created_by);


--
-- Name: idx_events_family_starts_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_events_family_starts_at ON public.events USING btree (family_id, starts_at);


--
-- Name: idx_events_recurrence_parent_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_events_recurrence_parent_id ON public.events USING btree (recurrence_parent_id);


--
-- Name: idx_events_task_instance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_events_task_instance_id ON public.events USING btree (task_instance_id) WHERE (task_instance_id IS NOT NULL);


--
-- Name: idx_family_members_family_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_family_members_family_id ON public.family_members USING btree (family_id);


--
-- Name: idx_family_memories_family_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_family_memories_family_status ON public.family_memories USING btree (family_id, status);


--
-- Name: idx_family_memories_family_type_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_family_memories_family_type_status ON public.family_memories USING btree (family_id, memory_type, status);


--
-- Name: idx_family_memories_member_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_family_memories_member_status ON public.family_memories USING btree (member_id, status);


--
-- Name: idx_grocery_items_added_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_grocery_items_added_by ON public.grocery_items USING btree (added_by_member_id);


--
-- Name: idx_grocery_items_family_purchased; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_grocery_items_family_purchased ON public.grocery_items USING btree (family_id, is_purchased);


--
-- Name: idx_grocery_items_family_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_grocery_items_family_status ON public.grocery_items USING btree (family_id, approval_status);


--
-- Name: idx_grocery_items_purchase_request; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_grocery_items_purchase_request ON public.grocery_items USING btree (purchase_request_id) WHERE (purchase_request_id IS NOT NULL);


--
-- Name: idx_grocery_items_weekly_plan; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_grocery_items_weekly_plan ON public.grocery_items USING btree (weekly_plan_id) WHERE (weekly_plan_id IS NOT NULL);


--
-- Name: idx_health_summaries_family_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_health_summaries_family_date ON public.health_summaries USING btree (family_id, summary_date);


--
-- Name: idx_homework_sessions_conversation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_homework_sessions_conversation ON public.ai_homework_sessions USING btree (conversation_id);


--
-- Name: idx_homework_sessions_family_started; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_homework_sessions_family_started ON public.ai_homework_sessions USING btree (family_id, started_at DESC);


--
-- Name: idx_homework_sessions_member_started; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_homework_sessions_member_started ON public.ai_homework_sessions USING btree (member_id, started_at DESC);


--
-- Name: idx_meal_plans_created_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_meal_plans_created_by ON public.meal_plans USING btree (created_by);


--
-- Name: idx_meal_reviews_family_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_meal_reviews_family_created ON public.meal_reviews USING btree (family_id, created_at DESC);


--
-- Name: idx_meal_reviews_repeat_decision; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_meal_reviews_repeat_decision ON public.meal_reviews USING btree (family_id, repeat_decision);


--
-- Name: idx_meal_reviews_weekly_plan; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_meal_reviews_weekly_plan ON public.meal_reviews USING btree (weekly_plan_id) WHERE (weekly_plan_id IS NOT NULL);


--
-- Name: idx_meals_created_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_meals_created_by ON public.meals USING btree (created_by);


--
-- Name: idx_meals_family_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_meals_family_date ON public.meals USING btree (family_id, meal_date);


--
-- Name: idx_meals_meal_plan_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_meals_meal_plan_id ON public.meals USING btree (meal_plan_id) WHERE (meal_plan_id IS NOT NULL);


--
-- Name: idx_member_config_member; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_member_config_member ON public.member_config USING btree (family_member_id);


--
-- Name: idx_notes_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notes_category ON public.notes USING btree (category) WHERE (category IS NOT NULL);


--
-- Name: idx_notes_family_member_updated; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notes_family_member_updated ON public.notes USING btree (family_member_id, updated_at DESC);


--
-- Name: idx_notes_family_updated; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notes_family_updated ON public.notes USING btree (family_id, updated_at DESC);


--
-- Name: idx_parent_action_items_family_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_parent_action_items_family_status ON public.parent_action_items USING btree (family_id, status);


--
-- Name: idx_parent_action_items_family_type_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_parent_action_items_family_type_created ON public.parent_action_items USING btree (family_id, action_type, created_at DESC);


--
-- Name: idx_personal_tasks_assigned_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_personal_tasks_assigned_status ON public.personal_tasks USING btree (assigned_to, status);


--
-- Name: idx_personal_tasks_created_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_personal_tasks_created_by ON public.personal_tasks USING btree (created_by);


--
-- Name: idx_personal_tasks_due_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_personal_tasks_due_at ON public.personal_tasks USING btree (due_at) WHERE (due_at IS NOT NULL);


--
-- Name: idx_personal_tasks_event_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_personal_tasks_event_id ON public.personal_tasks USING btree (event_id) WHERE (event_id IS NOT NULL);


--
-- Name: idx_personal_tasks_family_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_personal_tasks_family_id ON public.personal_tasks USING btree (family_id);


--
-- Name: idx_planner_bundle_applies_family_bundle; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_planner_bundle_applies_family_bundle ON public.planner_bundle_applies USING btree (family_id, bundle_apply_id);


--
-- Name: idx_purchase_requests_family_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_purchase_requests_family_status ON public.purchase_requests USING btree (family_id, status);


--
-- Name: idx_purchase_requests_requested_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_purchase_requests_requested_by ON public.purchase_requests USING btree (requested_by_member_id);


--
-- Name: idx_purchase_requests_reviewed_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_purchase_requests_reviewed_by ON public.purchase_requests USING btree (reviewed_by_member_id) WHERE (reviewed_by_member_id IS NOT NULL);


--
-- Name: idx_role_tier_overrides_role_tier_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_role_tier_overrides_role_tier_id ON public.role_tier_overrides USING btree (role_tier_id);


--
-- Name: idx_routines_family_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_routines_family_id ON public.routines USING btree (family_id);


--
-- Name: idx_routines_family_member_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_routines_family_member_id ON public.routines USING btree (family_member_id);


--
-- Name: idx_scout_mcp_tokens_family; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scout_mcp_tokens_family ON public.scout_mcp_tokens USING btree (family_id);


--
-- Name: idx_scout_mcp_tokens_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_scout_mcp_tokens_hash ON public.scout_mcp_tokens USING btree (token_hash);


--
-- Name: idx_scout_scheduled_runs_family_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scout_scheduled_runs_family_date ON public.scout_scheduled_runs USING btree (family_id, run_date DESC);


--
-- Name: idx_sessions_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sessions_expires_at ON public.sessions USING btree (expires_at);


--
-- Name: idx_sessions_user_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sessions_user_account_id ON public.sessions USING btree (user_account_id);


--
-- Name: idx_step_completions_routine_step_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_step_completions_routine_step_id ON public.task_instance_step_completions USING btree (routine_step_id);


--
-- Name: idx_task_instances_chore_template_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_task_instances_chore_template_id ON public.task_instances USING btree (chore_template_id);


--
-- Name: idx_task_instances_family_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_task_instances_family_date ON public.task_instances USING btree (family_id, instance_date);


--
-- Name: idx_task_instances_member_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_task_instances_member_date ON public.task_instances USING btree (family_member_id, instance_date);


--
-- Name: idx_task_instances_override_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_task_instances_override_by ON public.task_instances USING btree (override_by) WHERE (override_by IS NOT NULL);


--
-- Name: idx_task_instances_routine_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_task_instances_routine_id ON public.task_instances USING btree (routine_id);


--
-- Name: idx_user_accounts_family_member_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_accounts_family_member_id ON public.user_accounts USING btree (family_member_id);


--
-- Name: idx_weekly_meal_plans_family_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_weekly_meal_plans_family_status ON public.weekly_meal_plans USING btree (family_id, status);


--
-- Name: idx_weekly_meal_plans_family_week; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_weekly_meal_plans_family_week ON public.weekly_meal_plans USING btree (family_id, week_start_date DESC);


--
-- Name: uq_ai_daily_insights_dedupe; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_ai_daily_insights_dedupe ON public.ai_daily_insights USING btree (family_id, insight_type, as_of_date);


--
-- Name: uq_allowance_ledger_weekly_payout; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_allowance_ledger_weekly_payout ON public.allowance_ledger USING btree (family_member_id, week_start) WHERE (entry_type = 'weekly_payout'::text);


--
-- Name: uq_connector_configs_family; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_connector_configs_family ON public.connector_configs USING btree (family_id, connector_name) WHERE ((scope = 'family'::text) AND (is_active = true));


--
-- Name: uq_connector_configs_member; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_connector_configs_member ON public.connector_configs USING btree (family_member_id, connector_name) WHERE ((scope = 'member'::text) AND (is_active = true));


--
-- Name: uq_connector_mappings_canonical; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_connector_mappings_canonical ON public.connector_mappings USING btree (connector_name, external_object_type, external_id);


--
-- Name: uq_events_recurrence_override; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_events_recurrence_override ON public.events USING btree (recurrence_parent_id, recurrence_instance_date) WHERE (recurrence_parent_id IS NOT NULL);


--
-- Name: uq_personal_tasks_source_project_task; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_personal_tasks_source_project_task ON public.personal_tasks USING btree (source_project_task_id) WHERE (source_project_task_id IS NOT NULL);


--
-- Name: uq_routines_member_block; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_routines_member_block ON public.routines USING btree (family_member_id, block) WHERE (is_active = true);


--
-- Name: uq_scout_scheduled_runs_dedupe; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_scout_scheduled_runs_dedupe ON public.scout_scheduled_runs USING btree (job_name, family_id, COALESCE(member_id, '00000000-0000-0000-0000-000000000000'::uuid), run_date);


--
-- Name: uq_user_accounts_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_user_accounts_email ON public.user_accounts USING btree (email) WHERE (email IS NOT NULL);


--
-- Name: uq_weekly_meal_plans_family_week_approved; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_weekly_meal_plans_family_week_approved ON public.weekly_meal_plans USING btree (family_id, week_start_date) WHERE (status = 'approved'::text);


--
-- Name: idx_affirmation_delivery_member_time; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_affirmation_delivery_member_time ON scout.affirmation_delivery_log USING btree (family_member_id, surfaced_at DESC);


--
-- Name: idx_affirmation_feedback_member; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_affirmation_feedback_member ON scout.affirmation_feedback USING btree (family_member_id, affirmation_id, created_at DESC);


--
-- Name: idx_connector_accounts_family; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_connector_accounts_family ON scout.connector_accounts USING btree (family_id);


--
-- Name: idx_connector_event_log_account_time; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_connector_event_log_account_time ON scout.connector_event_log USING btree (connector_account_id, created_at DESC);


--
-- Name: idx_daily_win_family_date; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_daily_win_family_date ON scout.daily_win_results USING btree (family_id, for_date);


--
-- Name: idx_home_assets_family; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_home_assets_family ON scout.home_assets USING btree (family_id);


--
-- Name: idx_home_zones_family; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_home_zones_family ON scout.home_zones USING btree (family_id);


--
-- Name: idx_maintenance_instances_family_scheduled; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_maintenance_instances_family_scheduled ON scout.maintenance_instances USING btree (family_id, scheduled_for);


--
-- Name: idx_maintenance_templates_family; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_maintenance_templates_family ON scout.maintenance_templates USING btree (family_id);


--
-- Name: idx_meal_transformations_base; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_meal_transformations_base ON scout.meal_transformations USING btree (base_staple_id);


--
-- Name: idx_meal_transformations_family; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_meal_transformations_family ON scout.meal_transformations USING btree (family_id);


--
-- Name: idx_nudge_dispatch_items_dispatch; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_nudge_dispatch_items_dispatch ON scout.nudge_dispatch_items USING btree (dispatch_id);


--
-- Name: idx_nudge_dispatch_items_member; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_nudge_dispatch_items_member ON scout.nudge_dispatch_items USING btree (family_member_id, occurrence_at_utc DESC);


--
-- Name: idx_nudge_dispatches_member_created; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_nudge_dispatches_member_created ON scout.nudge_dispatches USING btree (family_member_id, created_at DESC);


--
-- Name: idx_nudge_dispatches_pending; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_nudge_dispatches_pending ON scout.nudge_dispatches USING btree (deliver_after_utc) WHERE (delivered_at_utc IS NULL);


--
-- Name: idx_nudge_rules_family_active; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_nudge_rules_family_active ON scout.nudge_rules USING btree (family_id, is_active) WHERE (is_active = true);


--
-- Name: idx_project_budget_entries_project; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_project_budget_entries_project ON scout.project_budget_entries USING btree (project_id, recorded_at DESC);


--
-- Name: idx_project_milestones_project_target; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_project_milestones_project_target ON scout.project_milestones USING btree (project_id, target_date);


--
-- Name: idx_project_tasks_owner_due; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_project_tasks_owner_due ON scout.project_tasks USING btree (owner_family_member_id, due_date) WHERE (owner_family_member_id IS NOT NULL);


--
-- Name: idx_project_tasks_project_status; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_project_tasks_project_status ON scout.project_tasks USING btree (project_id, status);


--
-- Name: idx_project_template_tasks_template; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_project_template_tasks_template ON scout.project_template_tasks USING btree (project_template_id, order_index);


--
-- Name: idx_project_templates_family; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_project_templates_family ON scout.project_templates USING btree (family_id) WHERE (family_id IS NOT NULL);


--
-- Name: idx_projects_family_active; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_projects_family_active ON scout.projects USING btree (family_id, status) WHERE (status = ANY (ARRAY['active'::text, 'draft'::text]));


--
-- Name: idx_push_deliveries_group; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_push_deliveries_group ON scout.push_deliveries USING btree (notification_group_id);


--
-- Name: idx_push_deliveries_member_created; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_push_deliveries_member_created ON scout.push_deliveries USING btree (family_member_id, created_at DESC);


--
-- Name: idx_push_deliveries_status_created; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_push_deliveries_status_created ON scout.push_deliveries USING btree (status, created_at);


--
-- Name: idx_push_devices_active; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_push_devices_active ON scout.push_devices USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_push_devices_member; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_push_devices_member ON scout.push_devices USING btree (family_member_id);


--
-- Name: idx_task_completions_occurrence; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_task_completions_occurrence ON scout.task_completions USING btree (task_occurrence_id);


--
-- Name: idx_task_occurrences_assignee_date; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_task_occurrences_assignee_date ON scout.task_occurrences USING btree (assigned_to, occurrence_date);


--
-- Name: idx_task_occurrences_family_date; Type: INDEX; Schema: scout; Owner: -
--

CREATE INDEX idx_task_occurrences_family_date ON scout.task_occurrences USING btree (family_id, occurrence_date);


--
-- Name: activity_records trg_activity_records_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_activity_records_updated_at BEFORE UPDATE ON public.activity_records FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: ai_conversations trg_ai_conversations_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_ai_conversations_updated_at BEFORE UPDATE ON public.ai_conversations FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: bills trg_bills_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_bills_updated_at BEFORE UPDATE ON public.bills FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: chore_templates trg_chore_templates_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_chore_templates_updated_at BEFORE UPDATE ON public.chore_templates FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: connector_configs trg_connector_configs_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_connector_configs_updated_at BEFORE UPDATE ON public.connector_configs FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: connector_mappings trg_connector_mappings_default_object_type; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_connector_mappings_default_object_type BEFORE INSERT ON public.connector_mappings FOR EACH ROW EXECUTE FUNCTION public._connector_mappings_default_object_type();


--
-- Name: daily_wins trg_daily_wins_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_daily_wins_updated_at BEFORE UPDATE ON public.daily_wins FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: dietary_preferences trg_dietary_preferences_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_dietary_preferences_updated_at BEFORE UPDATE ON public.dietary_preferences FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: event_attendees trg_event_attendees_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_event_attendees_updated_at BEFORE UPDATE ON public.event_attendees FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: events trg_events_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_events_updated_at BEFORE UPDATE ON public.events FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: families trg_families_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_families_updated_at BEFORE UPDATE ON public.families FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: family_members trg_family_members_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_family_members_updated_at BEFORE UPDATE ON public.family_members FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: family_memories trg_family_memories_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_family_memories_updated_at BEFORE UPDATE ON public.family_memories FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: grocery_items trg_grocery_items_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_grocery_items_updated_at BEFORE UPDATE ON public.grocery_items FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: health_summaries trg_health_summaries_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_health_summaries_updated_at BEFORE UPDATE ON public.health_summaries FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: meal_plans trg_meal_plans_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_meal_plans_updated_at BEFORE UPDATE ON public.meal_plans FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: meals trg_meals_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_meals_updated_at BEFORE UPDATE ON public.meals FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: member_config trg_member_config_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_member_config_updated_at BEFORE UPDATE ON public.member_config FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: notes trg_notes_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_notes_updated_at BEFORE UPDATE ON public.notes FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: parent_action_items trg_parent_action_items_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_parent_action_items_updated_at BEFORE UPDATE ON public.parent_action_items FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: personal_tasks trg_personal_tasks_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_personal_tasks_updated_at BEFORE UPDATE ON public.personal_tasks FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: purchase_requests trg_purchase_requests_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_purchase_requests_updated_at BEFORE UPDATE ON public.purchase_requests FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: role_tier_overrides trg_role_tier_overrides_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_role_tier_overrides_updated_at BEFORE UPDATE ON public.role_tier_overrides FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: role_tiers trg_role_tiers_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_role_tiers_updated_at BEFORE UPDATE ON public.role_tiers FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: routine_steps trg_routine_steps_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_routine_steps_updated_at BEFORE UPDATE ON public.routine_steps FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: routines trg_routines_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_routines_updated_at BEFORE UPDATE ON public.routines FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: task_instances trg_task_instances_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_task_instances_updated_at BEFORE UPDATE ON public.task_instances FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: user_accounts trg_user_accounts_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_user_accounts_updated_at BEFORE UPDATE ON public.user_accounts FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: weekly_meal_plans trg_weekly_meal_plans_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_weekly_meal_plans_updated_at BEFORE UPDATE ON public.weekly_meal_plans FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: nudge_dispatches trg_nudge_dispatches_updated_at; Type: TRIGGER; Schema: scout; Owner: -
--

CREATE TRIGGER trg_nudge_dispatches_updated_at BEFORE UPDATE ON scout.nudge_dispatches FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: nudge_rules trg_nudge_rules_updated_at; Type: TRIGGER; Schema: scout; Owner: -
--

CREATE TRIGGER trg_nudge_rules_updated_at BEFORE UPDATE ON scout.nudge_rules FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: quiet_hours_family trg_quiet_hours_family_updated_at; Type: TRIGGER; Schema: scout; Owner: -
--

CREATE TRIGGER trg_quiet_hours_family_updated_at BEFORE UPDATE ON scout.quiet_hours_family FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: activity_records activity_records_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_records
    ADD CONSTRAINT activity_records_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: activity_records activity_records_family_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_records
    ADD CONSTRAINT activity_records_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: ai_conversations ai_conversations_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_conversations
    ADD CONSTRAINT ai_conversations_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: ai_conversations ai_conversations_family_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_conversations
    ADD CONSTRAINT ai_conversations_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: ai_daily_insights ai_daily_insights_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_daily_insights
    ADD CONSTRAINT ai_daily_insights_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: ai_homework_sessions ai_homework_sessions_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_homework_sessions
    ADD CONSTRAINT ai_homework_sessions_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.ai_conversations(id) ON DELETE SET NULL;


--
-- Name: ai_homework_sessions ai_homework_sessions_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_homework_sessions
    ADD CONSTRAINT ai_homework_sessions_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: ai_homework_sessions ai_homework_sessions_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_homework_sessions
    ADD CONSTRAINT ai_homework_sessions_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: ai_messages ai_messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_messages
    ADD CONSTRAINT ai_messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.ai_conversations(id) ON DELETE CASCADE;


--
-- Name: ai_tool_audit ai_tool_audit_actor_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_tool_audit
    ADD CONSTRAINT ai_tool_audit_actor_member_id_fkey FOREIGN KEY (actor_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: ai_tool_audit ai_tool_audit_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_tool_audit
    ADD CONSTRAINT ai_tool_audit_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.ai_conversations(id) ON DELETE SET NULL;


--
-- Name: ai_tool_audit ai_tool_audit_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_tool_audit
    ADD CONSTRAINT ai_tool_audit_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: allowance_ledger allowance_ledger_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.allowance_ledger
    ADD CONSTRAINT allowance_ledger_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: allowance_ledger allowance_ledger_family_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.allowance_ledger
    ADD CONSTRAINT allowance_ledger_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: bills bills_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bills
    ADD CONSTRAINT bills_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: bills bills_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bills
    ADD CONSTRAINT bills_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: chore_templates chore_templates_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chore_templates
    ADD CONSTRAINT chore_templates_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: connector_configs connector_configs_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.connector_configs
    ADD CONSTRAINT connector_configs_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: connector_configs connector_configs_family_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.connector_configs
    ADD CONSTRAINT connector_configs_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: connector_mappings connector_mappings_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.connector_mappings
    ADD CONSTRAINT connector_mappings_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: connector_mappings connector_mappings_user_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.connector_mappings
    ADD CONSTRAINT connector_mappings_user_account_id_fkey FOREIGN KEY (user_account_id) REFERENCES public.user_accounts(id) ON DELETE SET NULL;


--
-- Name: daily_wins daily_wins_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.daily_wins
    ADD CONSTRAINT daily_wins_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: daily_wins daily_wins_family_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.daily_wins
    ADD CONSTRAINT daily_wins_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: dietary_preferences dietary_preferences_family_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dietary_preferences
    ADD CONSTRAINT dietary_preferences_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: event_attendees event_attendees_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_attendees
    ADD CONSTRAINT event_attendees_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id) ON DELETE CASCADE;


--
-- Name: event_attendees event_attendees_family_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_attendees
    ADD CONSTRAINT event_attendees_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: events events_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: events events_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: events events_recurrence_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_recurrence_parent_id_fkey FOREIGN KEY (recurrence_parent_id) REFERENCES public.events(id) ON DELETE CASCADE;


--
-- Name: events events_task_instance_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_task_instance_id_fkey FOREIGN KEY (task_instance_id) REFERENCES public.task_instances(id) ON DELETE SET NULL;


--
-- Name: family_members family_members_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.family_members
    ADD CONSTRAINT family_members_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: family_memories family_memories_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.family_memories
    ADD CONSTRAINT family_memories_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: family_memories family_memories_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.family_memories
    ADD CONSTRAINT family_memories_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: family_memories family_memories_source_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.family_memories
    ADD CONSTRAINT family_memories_source_conversation_id_fkey FOREIGN KEY (source_conversation_id) REFERENCES public.ai_conversations(id) ON DELETE SET NULL;


--
-- Name: grocery_items fk_grocery_items_purchase_request; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grocery_items
    ADD CONSTRAINT fk_grocery_items_purchase_request FOREIGN KEY (purchase_request_id) REFERENCES public.purchase_requests(id) ON DELETE SET NULL;


--
-- Name: grocery_items grocery_items_added_by_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grocery_items
    ADD CONSTRAINT grocery_items_added_by_member_id_fkey FOREIGN KEY (added_by_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: grocery_items grocery_items_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grocery_items
    ADD CONSTRAINT grocery_items_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: grocery_items grocery_items_purchased_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grocery_items
    ADD CONSTRAINT grocery_items_purchased_by_fkey FOREIGN KEY (purchased_by) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: grocery_items grocery_items_weekly_plan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grocery_items
    ADD CONSTRAINT grocery_items_weekly_plan_id_fkey FOREIGN KEY (weekly_plan_id) REFERENCES public.weekly_meal_plans(id) ON DELETE SET NULL;


--
-- Name: health_summaries health_summaries_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_summaries
    ADD CONSTRAINT health_summaries_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: health_summaries health_summaries_family_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_summaries
    ADD CONSTRAINT health_summaries_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: meal_plans meal_plans_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meal_plans
    ADD CONSTRAINT meal_plans_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: meal_plans meal_plans_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meal_plans
    ADD CONSTRAINT meal_plans_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: meal_reviews meal_reviews_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meal_reviews
    ADD CONSTRAINT meal_reviews_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: meal_reviews meal_reviews_reviewed_by_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meal_reviews
    ADD CONSTRAINT meal_reviews_reviewed_by_member_id_fkey FOREIGN KEY (reviewed_by_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: meal_reviews meal_reviews_weekly_plan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meal_reviews
    ADD CONSTRAINT meal_reviews_weekly_plan_id_fkey FOREIGN KEY (weekly_plan_id) REFERENCES public.weekly_meal_plans(id) ON DELETE SET NULL;


--
-- Name: meals meals_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meals
    ADD CONSTRAINT meals_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: meals meals_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meals
    ADD CONSTRAINT meals_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: meals meals_meal_plan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meals
    ADD CONSTRAINT meals_meal_plan_id_fkey FOREIGN KEY (meal_plan_id) REFERENCES public.meal_plans(id) ON DELETE SET NULL;


--
-- Name: member_config member_config_family_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.member_config
    ADD CONSTRAINT member_config_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: member_config member_config_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.member_config
    ADD CONSTRAINT member_config_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: notes notes_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notes
    ADD CONSTRAINT notes_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: notes notes_family_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notes
    ADD CONSTRAINT notes_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: parent_action_items parent_action_items_created_by_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parent_action_items
    ADD CONSTRAINT parent_action_items_created_by_member_id_fkey FOREIGN KEY (created_by_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: parent_action_items parent_action_items_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parent_action_items
    ADD CONSTRAINT parent_action_items_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: parent_action_items parent_action_items_resolved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parent_action_items
    ADD CONSTRAINT parent_action_items_resolved_by_fkey FOREIGN KEY (resolved_by) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: personal_tasks personal_tasks_assigned_to_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personal_tasks
    ADD CONSTRAINT personal_tasks_assigned_to_fkey FOREIGN KEY (assigned_to) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: personal_tasks personal_tasks_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personal_tasks
    ADD CONSTRAINT personal_tasks_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: personal_tasks personal_tasks_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personal_tasks
    ADD CONSTRAINT personal_tasks_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id) ON DELETE SET NULL;


--
-- Name: personal_tasks personal_tasks_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personal_tasks
    ADD CONSTRAINT personal_tasks_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: personal_tasks personal_tasks_source_project_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personal_tasks
    ADD CONSTRAINT personal_tasks_source_project_task_id_fkey FOREIGN KEY (source_project_task_id) REFERENCES scout.project_tasks(id) ON DELETE SET NULL;


--
-- Name: planner_bundle_applies planner_bundle_applies_actor_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planner_bundle_applies
    ADD CONSTRAINT planner_bundle_applies_actor_member_id_fkey FOREIGN KEY (actor_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: planner_bundle_applies planner_bundle_applies_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planner_bundle_applies
    ADD CONSTRAINT planner_bundle_applies_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.ai_conversations(id) ON DELETE SET NULL;


--
-- Name: planner_bundle_applies planner_bundle_applies_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planner_bundle_applies
    ADD CONSTRAINT planner_bundle_applies_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: purchase_requests purchase_requests_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_requests
    ADD CONSTRAINT purchase_requests_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: purchase_requests purchase_requests_linked_grocery_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_requests
    ADD CONSTRAINT purchase_requests_linked_grocery_item_id_fkey FOREIGN KEY (linked_grocery_item_id) REFERENCES public.grocery_items(id) ON DELETE SET NULL;


--
-- Name: purchase_requests purchase_requests_requested_by_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_requests
    ADD CONSTRAINT purchase_requests_requested_by_member_id_fkey FOREIGN KEY (requested_by_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: purchase_requests purchase_requests_reviewed_by_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_requests
    ADD CONSTRAINT purchase_requests_reviewed_by_member_id_fkey FOREIGN KEY (reviewed_by_member_id) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: role_tier_overrides role_tier_overrides_family_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_tier_overrides
    ADD CONSTRAINT role_tier_overrides_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: role_tier_overrides role_tier_overrides_role_tier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_tier_overrides
    ADD CONSTRAINT role_tier_overrides_role_tier_id_fkey FOREIGN KEY (role_tier_id) REFERENCES public.role_tiers(id) ON DELETE RESTRICT;


--
-- Name: routine_steps routine_steps_routine_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.routine_steps
    ADD CONSTRAINT routine_steps_routine_id_fkey FOREIGN KEY (routine_id) REFERENCES public.routines(id) ON DELETE CASCADE;


--
-- Name: routines routines_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.routines
    ADD CONSTRAINT routines_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: routines routines_family_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.routines
    ADD CONSTRAINT routines_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: scout_anomaly_suppressions scout_anomaly_suppressions_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scout_anomaly_suppressions
    ADD CONSTRAINT scout_anomaly_suppressions_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: scout_mcp_tokens scout_mcp_tokens_created_by_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scout_mcp_tokens
    ADD CONSTRAINT scout_mcp_tokens_created_by_member_id_fkey FOREIGN KEY (created_by_member_id) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: scout_mcp_tokens scout_mcp_tokens_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scout_mcp_tokens
    ADD CONSTRAINT scout_mcp_tokens_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: scout_mcp_tokens scout_mcp_tokens_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scout_mcp_tokens
    ADD CONSTRAINT scout_mcp_tokens_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: scout_scheduled_runs scout_scheduled_runs_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scout_scheduled_runs
    ADD CONSTRAINT scout_scheduled_runs_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: scout_scheduled_runs scout_scheduled_runs_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scout_scheduled_runs
    ADD CONSTRAINT scout_scheduled_runs_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: sessions sessions_user_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_user_account_id_fkey FOREIGN KEY (user_account_id) REFERENCES public.user_accounts(id) ON DELETE CASCADE;


--
-- Name: task_instance_step_completions task_instance_step_completions_routine_step_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_instance_step_completions
    ADD CONSTRAINT task_instance_step_completions_routine_step_id_fkey FOREIGN KEY (routine_step_id) REFERENCES public.routine_steps(id) ON DELETE RESTRICT;


--
-- Name: task_instance_step_completions task_instance_step_completions_task_instance_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_instance_step_completions
    ADD CONSTRAINT task_instance_step_completions_task_instance_id_fkey FOREIGN KEY (task_instance_id) REFERENCES public.task_instances(id) ON DELETE CASCADE;


--
-- Name: task_instances task_instances_chore_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_instances
    ADD CONSTRAINT task_instances_chore_template_id_fkey FOREIGN KEY (chore_template_id) REFERENCES public.chore_templates(id) ON DELETE RESTRICT;


--
-- Name: task_instances task_instances_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_instances
    ADD CONSTRAINT task_instances_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: task_instances task_instances_family_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_instances
    ADD CONSTRAINT task_instances_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: task_instances task_instances_override_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_instances
    ADD CONSTRAINT task_instances_override_by_fkey FOREIGN KEY (override_by) REFERENCES public.family_members(id) ON DELETE RESTRICT;


--
-- Name: task_instances task_instances_routine_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_instances
    ADD CONSTRAINT task_instances_routine_id_fkey FOREIGN KEY (routine_id) REFERENCES public.routines(id) ON DELETE RESTRICT;


--
-- Name: user_accounts user_accounts_family_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_accounts
    ADD CONSTRAINT user_accounts_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: weekly_meal_plans weekly_meal_plans_approved_by_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_meal_plans
    ADD CONSTRAINT weekly_meal_plans_approved_by_member_id_fkey FOREIGN KEY (approved_by_member_id) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: weekly_meal_plans weekly_meal_plans_created_by_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_meal_plans
    ADD CONSTRAINT weekly_meal_plans_created_by_member_id_fkey FOREIGN KEY (created_by_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: weekly_meal_plans weekly_meal_plans_family_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_meal_plans
    ADD CONSTRAINT weekly_meal_plans_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: activity_events activity_events_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.activity_events
    ADD CONSTRAINT activity_events_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: activity_events activity_events_family_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.activity_events
    ADD CONSTRAINT activity_events_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: affirmation_delivery_log affirmation_delivery_log_affirmation_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.affirmation_delivery_log
    ADD CONSTRAINT affirmation_delivery_log_affirmation_id_fkey FOREIGN KEY (affirmation_id) REFERENCES scout.affirmations(id) ON DELETE CASCADE;


--
-- Name: affirmation_delivery_log affirmation_delivery_log_family_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.affirmation_delivery_log
    ADD CONSTRAINT affirmation_delivery_log_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: affirmation_feedback affirmation_feedback_affirmation_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.affirmation_feedback
    ADD CONSTRAINT affirmation_feedback_affirmation_id_fkey FOREIGN KEY (affirmation_id) REFERENCES scout.affirmations(id) ON DELETE CASCADE;


--
-- Name: affirmation_feedback affirmation_feedback_family_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.affirmation_feedback
    ADD CONSTRAINT affirmation_feedback_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: affirmations affirmations_created_by_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.affirmations
    ADD CONSTRAINT affirmations_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: affirmations affirmations_updated_by_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.affirmations
    ADD CONSTRAINT affirmations_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: allowance_periods allowance_periods_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.allowance_periods
    ADD CONSTRAINT allowance_periods_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: allowance_results allowance_results_allowance_period_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.allowance_results
    ADD CONSTRAINT allowance_results_allowance_period_id_fkey FOREIGN KEY (allowance_period_id) REFERENCES scout.allowance_periods(id) ON DELETE CASCADE;


--
-- Name: allowance_results allowance_results_family_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.allowance_results
    ADD CONSTRAINT allowance_results_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: allowance_results allowance_results_reward_policy_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.allowance_results
    ADD CONSTRAINT allowance_results_reward_policy_id_fkey FOREIGN KEY (reward_policy_id) REFERENCES scout.reward_policies(id) ON DELETE SET NULL;


--
-- Name: bill_snapshots bill_snapshots_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.bill_snapshots
    ADD CONSTRAINT bill_snapshots_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: budget_snapshots budget_snapshots_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.budget_snapshots
    ADD CONSTRAINT budget_snapshots_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: calendar_exports calendar_exports_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.calendar_exports
    ADD CONSTRAINT calendar_exports_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: connector_accounts connector_accounts_connector_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.connector_accounts
    ADD CONSTRAINT connector_accounts_connector_id_fkey FOREIGN KEY (connector_id) REFERENCES scout.connectors(id) ON DELETE CASCADE;


--
-- Name: connector_accounts connector_accounts_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.connector_accounts
    ADD CONSTRAINT connector_accounts_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: connector_accounts connector_accounts_user_account_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.connector_accounts
    ADD CONSTRAINT connector_accounts_user_account_id_fkey FOREIGN KEY (user_account_id) REFERENCES public.user_accounts(id) ON DELETE SET NULL;


--
-- Name: connector_event_log connector_event_log_connector_account_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.connector_event_log
    ADD CONSTRAINT connector_event_log_connector_account_id_fkey FOREIGN KEY (connector_account_id) REFERENCES scout.connector_accounts(id) ON DELETE CASCADE;


--
-- Name: daily_win_results daily_win_results_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.daily_win_results
    ADD CONSTRAINT daily_win_results_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: daily_win_results daily_win_results_family_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.daily_win_results
    ADD CONSTRAINT daily_win_results_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: device_registrations device_registrations_user_account_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.device_registrations
    ADD CONSTRAINT device_registrations_user_account_id_fkey FOREIGN KEY (user_account_id) REFERENCES public.user_accounts(id) ON DELETE CASCADE;


--
-- Name: external_calendar_events external_calendar_events_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.external_calendar_events
    ADD CONSTRAINT external_calendar_events_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: greenlight_exports greenlight_exports_family_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.greenlight_exports
    ADD CONSTRAINT greenlight_exports_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: greenlight_exports greenlight_exports_settlement_batch_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.greenlight_exports
    ADD CONSTRAINT greenlight_exports_settlement_batch_id_fkey FOREIGN KEY (settlement_batch_id) REFERENCES scout.settlement_batches(id) ON DELETE CASCADE;


--
-- Name: home_assets home_assets_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.home_assets
    ADD CONSTRAINT home_assets_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: home_assets home_assets_zone_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.home_assets
    ADD CONSTRAINT home_assets_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES scout.home_zones(id) ON DELETE SET NULL;


--
-- Name: home_zones home_zones_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.home_zones
    ADD CONSTRAINT home_zones_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: household_rules household_rules_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.household_rules
    ADD CONSTRAINT household_rules_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: maintenance_instances maintenance_instances_completed_by_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.maintenance_instances
    ADD CONSTRAINT maintenance_instances_completed_by_member_id_fkey FOREIGN KEY (completed_by_member_id) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: maintenance_instances maintenance_instances_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.maintenance_instances
    ADD CONSTRAINT maintenance_instances_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: maintenance_instances maintenance_instances_owner_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.maintenance_instances
    ADD CONSTRAINT maintenance_instances_owner_member_id_fkey FOREIGN KEY (owner_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: maintenance_instances maintenance_instances_template_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.maintenance_instances
    ADD CONSTRAINT maintenance_instances_template_id_fkey FOREIGN KEY (template_id) REFERENCES scout.maintenance_templates(id) ON DELETE CASCADE;


--
-- Name: maintenance_templates maintenance_templates_asset_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.maintenance_templates
    ADD CONSTRAINT maintenance_templates_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES scout.home_assets(id) ON DELETE SET NULL;


--
-- Name: maintenance_templates maintenance_templates_default_owner_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.maintenance_templates
    ADD CONSTRAINT maintenance_templates_default_owner_member_id_fkey FOREIGN KEY (default_owner_member_id) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: maintenance_templates maintenance_templates_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.maintenance_templates
    ADD CONSTRAINT maintenance_templates_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: maintenance_templates maintenance_templates_zone_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.maintenance_templates
    ADD CONSTRAINT maintenance_templates_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES scout.home_zones(id) ON DELETE SET NULL;


--
-- Name: meal_transformations meal_transformations_base_staple_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.meal_transformations
    ADD CONSTRAINT meal_transformations_base_staple_id_fkey FOREIGN KEY (base_staple_id) REFERENCES public.meals(id) ON DELETE CASCADE;


--
-- Name: meal_transformations meal_transformations_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.meal_transformations
    ADD CONSTRAINT meal_transformations_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: meal_transformations meal_transformations_transformed_staple_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.meal_transformations
    ADD CONSTRAINT meal_transformations_transformed_staple_id_fkey FOREIGN KEY (transformed_staple_id) REFERENCES public.meals(id) ON DELETE CASCADE;


--
-- Name: nudge_dispatch_items nudge_dispatch_items_dispatch_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.nudge_dispatch_items
    ADD CONSTRAINT nudge_dispatch_items_dispatch_id_fkey FOREIGN KEY (dispatch_id) REFERENCES scout.nudge_dispatches(id) ON DELETE CASCADE;


--
-- Name: nudge_dispatch_items nudge_dispatch_items_family_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.nudge_dispatch_items
    ADD CONSTRAINT nudge_dispatch_items_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: nudge_dispatches nudge_dispatches_family_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.nudge_dispatches
    ADD CONSTRAINT nudge_dispatches_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: nudge_dispatches nudge_dispatches_parent_action_item_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.nudge_dispatches
    ADD CONSTRAINT nudge_dispatches_parent_action_item_id_fkey FOREIGN KEY (parent_action_item_id) REFERENCES public.parent_action_items(id) ON DELETE SET NULL;


--
-- Name: nudge_dispatches nudge_dispatches_push_delivery_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.nudge_dispatches
    ADD CONSTRAINT nudge_dispatches_push_delivery_id_fkey FOREIGN KEY (push_delivery_id) REFERENCES scout.push_deliveries(id) ON DELETE SET NULL;


--
-- Name: nudge_rules nudge_rules_created_by_family_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.nudge_rules
    ADD CONSTRAINT nudge_rules_created_by_family_member_id_fkey FOREIGN KEY (created_by_family_member_id) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: nudge_rules nudge_rules_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.nudge_rules
    ADD CONSTRAINT nudge_rules_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: project_budget_entries project_budget_entries_project_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.project_budget_entries
    ADD CONSTRAINT project_budget_entries_project_id_fkey FOREIGN KEY (project_id) REFERENCES scout.projects(id) ON DELETE CASCADE;


--
-- Name: project_budget_entries project_budget_entries_project_task_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.project_budget_entries
    ADD CONSTRAINT project_budget_entries_project_task_id_fkey FOREIGN KEY (project_task_id) REFERENCES scout.project_tasks(id) ON DELETE SET NULL;


--
-- Name: project_budget_entries project_budget_entries_recorded_by_family_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.project_budget_entries
    ADD CONSTRAINT project_budget_entries_recorded_by_family_member_id_fkey FOREIGN KEY (recorded_by_family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: project_milestones project_milestones_project_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.project_milestones
    ADD CONSTRAINT project_milestones_project_id_fkey FOREIGN KEY (project_id) REFERENCES scout.projects(id) ON DELETE CASCADE;


--
-- Name: project_tasks project_tasks_depends_on_project_task_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.project_tasks
    ADD CONSTRAINT project_tasks_depends_on_project_task_id_fkey FOREIGN KEY (depends_on_project_task_id) REFERENCES scout.project_tasks(id) ON DELETE SET NULL;


--
-- Name: project_tasks project_tasks_owner_family_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.project_tasks
    ADD CONSTRAINT project_tasks_owner_family_member_id_fkey FOREIGN KEY (owner_family_member_id) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: project_tasks project_tasks_project_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.project_tasks
    ADD CONSTRAINT project_tasks_project_id_fkey FOREIGN KEY (project_id) REFERENCES scout.projects(id) ON DELETE CASCADE;


--
-- Name: project_template_tasks project_template_tasks_project_template_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.project_template_tasks
    ADD CONSTRAINT project_template_tasks_project_template_id_fkey FOREIGN KEY (project_template_id) REFERENCES scout.project_templates(id) ON DELETE CASCADE;


--
-- Name: project_templates project_templates_created_by_family_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.project_templates
    ADD CONSTRAINT project_templates_created_by_family_member_id_fkey FOREIGN KEY (created_by_family_member_id) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: project_templates project_templates_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.project_templates
    ADD CONSTRAINT project_templates_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: projects projects_created_by_family_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.projects
    ADD CONSTRAINT projects_created_by_family_member_id_fkey FOREIGN KEY (created_by_family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: projects projects_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.projects
    ADD CONSTRAINT projects_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: projects projects_primary_owner_family_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.projects
    ADD CONSTRAINT projects_primary_owner_family_member_id_fkey FOREIGN KEY (primary_owner_family_member_id) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: projects projects_project_template_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.projects
    ADD CONSTRAINT projects_project_template_id_fkey FOREIGN KEY (project_template_id) REFERENCES scout.project_templates(id) ON DELETE SET NULL;


--
-- Name: push_deliveries push_deliveries_family_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.push_deliveries
    ADD CONSTRAINT push_deliveries_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: push_deliveries push_deliveries_push_device_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.push_deliveries
    ADD CONSTRAINT push_deliveries_push_device_id_fkey FOREIGN KEY (push_device_id) REFERENCES scout.push_devices(id) ON DELETE CASCADE;


--
-- Name: push_devices push_devices_family_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.push_devices
    ADD CONSTRAINT push_devices_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: quiet_hours_family quiet_hours_family_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.quiet_hours_family
    ADD CONSTRAINT quiet_hours_family_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: reward_extras_catalog reward_extras_catalog_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.reward_extras_catalog
    ADD CONSTRAINT reward_extras_catalog_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: reward_ledger_entries reward_ledger_entries_allowance_result_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.reward_ledger_entries
    ADD CONSTRAINT reward_ledger_entries_allowance_result_id_fkey FOREIGN KEY (allowance_result_id) REFERENCES scout.allowance_results(id) ON DELETE SET NULL;


--
-- Name: reward_ledger_entries reward_ledger_entries_extras_catalog_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.reward_ledger_entries
    ADD CONSTRAINT reward_ledger_entries_extras_catalog_id_fkey FOREIGN KEY (extras_catalog_id) REFERENCES scout.reward_extras_catalog(id) ON DELETE SET NULL;


--
-- Name: reward_ledger_entries reward_ledger_entries_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.reward_ledger_entries
    ADD CONSTRAINT reward_ledger_entries_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: reward_ledger_entries reward_ledger_entries_family_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.reward_ledger_entries
    ADD CONSTRAINT reward_ledger_entries_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: reward_policies reward_policies_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.reward_policies
    ADD CONSTRAINT reward_policies_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: reward_policies reward_policies_family_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.reward_policies
    ADD CONSTRAINT reward_policies_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE CASCADE;


--
-- Name: role_tier_permissions role_tier_permissions_permission_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.role_tier_permissions
    ADD CONSTRAINT role_tier_permissions_permission_id_fkey FOREIGN KEY (permission_id) REFERENCES scout.permissions(id) ON DELETE CASCADE;


--
-- Name: role_tier_permissions role_tier_permissions_role_tier_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.role_tier_permissions
    ADD CONSTRAINT role_tier_permissions_role_tier_id_fkey FOREIGN KEY (role_tier_id) REFERENCES public.role_tiers(id) ON DELETE CASCADE;


--
-- Name: routine_steps routine_steps_routine_template_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.routine_steps
    ADD CONSTRAINT routine_steps_routine_template_id_fkey FOREIGN KEY (routine_template_id) REFERENCES scout.routine_templates(id) ON DELETE CASCADE;


--
-- Name: routine_steps routine_steps_standard_of_done_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.routine_steps
    ADD CONSTRAINT routine_steps_standard_of_done_id_fkey FOREIGN KEY (standard_of_done_id) REFERENCES scout.standards_of_done(id) ON DELETE SET NULL;


--
-- Name: routine_templates routine_templates_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.routine_templates
    ADD CONSTRAINT routine_templates_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: routine_templates routine_templates_owner_family_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.routine_templates
    ADD CONSTRAINT routine_templates_owner_family_member_id_fkey FOREIGN KEY (owner_family_member_id) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: settlement_batches settlement_batches_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.settlement_batches
    ADD CONSTRAINT settlement_batches_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: stale_data_alerts stale_data_alerts_connector_account_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.stale_data_alerts
    ADD CONSTRAINT stale_data_alerts_connector_account_id_fkey FOREIGN KEY (connector_account_id) REFERENCES scout.connector_accounts(id) ON DELETE CASCADE;


--
-- Name: standards_of_done standards_of_done_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.standards_of_done
    ADD CONSTRAINT standards_of_done_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: sync_cursors sync_cursors_connector_account_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.sync_cursors
    ADD CONSTRAINT sync_cursors_connector_account_id_fkey FOREIGN KEY (connector_account_id) REFERENCES scout.connector_accounts(id) ON DELETE CASCADE;


--
-- Name: sync_jobs sync_jobs_connector_account_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.sync_jobs
    ADD CONSTRAINT sync_jobs_connector_account_id_fkey FOREIGN KEY (connector_account_id) REFERENCES scout.connector_accounts(id) ON DELETE CASCADE;


--
-- Name: sync_runs sync_runs_sync_job_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.sync_runs
    ADD CONSTRAINT sync_runs_sync_job_id_fkey FOREIGN KEY (sync_job_id) REFERENCES scout.sync_jobs(id) ON DELETE CASCADE;


--
-- Name: task_assignment_rules task_assignment_rules_task_template_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.task_assignment_rules
    ADD CONSTRAINT task_assignment_rules_task_template_id_fkey FOREIGN KEY (task_template_id) REFERENCES scout.task_templates(id) ON DELETE CASCADE;


--
-- Name: task_completions task_completions_completed_by_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.task_completions
    ADD CONSTRAINT task_completions_completed_by_fkey FOREIGN KEY (completed_by) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: task_completions task_completions_task_occurrence_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.task_completions
    ADD CONSTRAINT task_completions_task_occurrence_id_fkey FOREIGN KEY (task_occurrence_id) REFERENCES scout.task_occurrences(id) ON DELETE CASCADE;


--
-- Name: task_exceptions task_exceptions_created_by_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.task_exceptions
    ADD CONSTRAINT task_exceptions_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: task_exceptions task_exceptions_task_occurrence_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.task_exceptions
    ADD CONSTRAINT task_exceptions_task_occurrence_id_fkey FOREIGN KEY (task_occurrence_id) REFERENCES scout.task_occurrences(id) ON DELETE CASCADE;


--
-- Name: task_notes task_notes_author_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.task_notes
    ADD CONSTRAINT task_notes_author_id_fkey FOREIGN KEY (author_id) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: task_notes task_notes_task_occurrence_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.task_notes
    ADD CONSTRAINT task_notes_task_occurrence_id_fkey FOREIGN KEY (task_occurrence_id) REFERENCES scout.task_occurrences(id) ON DELETE CASCADE;


--
-- Name: task_occurrences task_occurrences_assigned_to_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.task_occurrences
    ADD CONSTRAINT task_occurrences_assigned_to_fkey FOREIGN KEY (assigned_to) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: task_occurrences task_occurrences_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.task_occurrences
    ADD CONSTRAINT task_occurrences_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: task_occurrences task_occurrences_routine_template_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.task_occurrences
    ADD CONSTRAINT task_occurrences_routine_template_id_fkey FOREIGN KEY (routine_template_id) REFERENCES scout.routine_templates(id) ON DELETE SET NULL;


--
-- Name: task_occurrences task_occurrences_task_template_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.task_occurrences
    ADD CONSTRAINT task_occurrences_task_template_id_fkey FOREIGN KEY (task_template_id) REFERENCES scout.task_templates(id) ON DELETE SET NULL;


--
-- Name: task_templates task_templates_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.task_templates
    ADD CONSTRAINT task_templates_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: task_templates task_templates_standard_of_done_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.task_templates
    ADD CONSTRAINT task_templates_standard_of_done_id_fkey FOREIGN KEY (standard_of_done_id) REFERENCES scout.standards_of_done(id) ON DELETE SET NULL;


--
-- Name: time_blocks time_blocks_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.time_blocks
    ADD CONSTRAINT time_blocks_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: travel_estimates travel_estimates_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.travel_estimates
    ADD CONSTRAINT travel_estimates_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: user_family_memberships user_family_memberships_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.user_family_memberships
    ADD CONSTRAINT user_family_memberships_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: user_family_memberships user_family_memberships_family_member_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.user_family_memberships
    ADD CONSTRAINT user_family_memberships_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.family_members(id) ON DELETE SET NULL;


--
-- Name: user_family_memberships user_family_memberships_role_tier_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.user_family_memberships
    ADD CONSTRAINT user_family_memberships_role_tier_id_fkey FOREIGN KEY (role_tier_id) REFERENCES public.role_tiers(id) ON DELETE SET NULL;


--
-- Name: user_family_memberships user_family_memberships_user_account_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.user_family_memberships
    ADD CONSTRAINT user_family_memberships_user_account_id_fkey FOREIGN KEY (user_account_id) REFERENCES public.user_accounts(id) ON DELETE CASCADE;


--
-- Name: user_preferences user_preferences_user_account_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.user_preferences
    ADD CONSTRAINT user_preferences_user_account_id_fkey FOREIGN KEY (user_account_id) REFERENCES public.user_accounts(id) ON DELETE CASCADE;


--
-- Name: work_context_events work_context_events_family_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.work_context_events
    ADD CONSTRAINT work_context_events_family_id_fkey FOREIGN KEY (family_id) REFERENCES public.families(id) ON DELETE CASCADE;


--
-- Name: work_context_events work_context_events_user_account_id_fkey; Type: FK CONSTRAINT; Schema: scout; Owner: -
--

ALTER TABLE ONLY scout.work_context_events
    ADD CONSTRAINT work_context_events_user_account_id_fkey FOREIGN KEY (user_account_id) REFERENCES public.user_accounts(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

\unrestrict fraiDJtPATubgn6kbqfyb0jPLkeOTlEyUFWVuV5bh623guEe0epToeE37OukaYX


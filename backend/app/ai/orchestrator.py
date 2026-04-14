"""Chat orchestration engine.

Handles the full chat loop:
1. Load context and build system prompt
2. Retrieve or create conversation thread
3. Send messages to AI with tool definitions
4. Execute tool calls when requested (one at a time)
5. Return tool results to AI for final response
6. Persist all messages
"""

import json
import uuid
from collections.abc import Iterator
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.context import (
    build_system_prompt,
    get_allowed_tools_for_surface,
    load_member_context,
)
from app.ai.homework import record_homework_turn
from app.ai.moderation import check_user_message
from app.ai.provider import AIResponse, AnthropicProvider, ToolDefinition, get_provider
from app.ai.tools import TOOL_DEFINITIONS, ToolExecutor, _audit
from app.models.ai import AIConversation, AIMessage


MAX_TOOL_ROUNDS = 5
# Tier 4 F15: weekly planner unlocks a longer loop so it can gather
# context → clarify → draft → bulk-confirm without hitting the normal
# 5-round ceiling. The intent field on ChatRequest is the only thing
# that enables this path; default chat still uses MAX_TOOL_ROUNDS.
MAX_PLANNER_ROUNDS = 20


def _rounds_for_intent(intent: str | None) -> int:
    if intent == "weekly_plan":
        return MAX_PLANNER_ROUNDS
    return MAX_TOOL_ROUNDS


_PLANNER_SUFFIX = """

WEEKLY PLANNING MODE (intent=weekly_plan):
You are in a long-form planning session for the upcoming week. You
have a larger tool budget than normal chat. Work in this order:

1. First, gather context by reading current state:
   - get_today_context
   - list_events for the week ahead
   - list_tasks (incomplete only)
   - list_chores_or_routines
   - get_current_weekly_meal_plan and get_meal_review_summary
   - list_purchase_requests

2. Ask clarifying questions before drafting anything. Cover: known
   schedule conflicts, guests, pantry staples, dietary constraints
   for the week, anything unusual the parent is thinking about.

3. Draft the proposed plan IN CHAT TEXT ONLY (do not call any
   write tools yet). Include:
     * task changes (adds, reassignments, deletions)
     * meal plan updates (follow the standard meal-plan rules below)
     * calendar suggestions (new events, moved events)
     * grocery impacts (what will need to be added)

4. Present one concise review of everything, then call
   ``apply_weekly_plan_bundle`` with the full bundle. That tool will
   return confirmation_required — the ScoutPanel will show a single
   approve / cancel card to the parent. On approve, the bundle
   executes atomically. On cancel, nothing is written and you can
   revise.

MEAL PLAN RULES apply inside planning mode the same as outside:
three-part structure (week plan / batch cook / grocery by store),
no em dashes, concise by default, verify structure before delivery.

NEVER call task / event / meal-plan write tools directly while in
weekly_plan intent. All writes go through ``apply_weekly_plan_bundle``
so the parent sees ONE bulk confirmation card, not a stream of
individual confirms.
"""


def _append_planner_suffix(base_prompt: str) -> str:
    return base_prompt + _PLANNER_SUFFIX


def get_or_create_conversation(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    surface: str,
    conversation_id: uuid.UUID | None = None,
) -> AIConversation:
    """Resume an active conversation by id, otherwise create a new one.

    QA fix (test_qa BUG #2): we also require the resumed conversation
    to have ``status='active'``. Without that check, a client holding
    a stale conversation_id can keep posting into an 'ended' or
    'archived' thread after the user has explicitly tapped
    "New chat". The Tier 3 F12 resumable endpoint already filters
    inactive threads; this closes the direct-by-id bypass."""
    if conversation_id:
        conv = db.get(AIConversation, conversation_id)
        if (
            conv
            and conv.family_id == family_id
            and conv.family_member_id == member_id
            and conv.status == "active"
        ):
            return conv

    conv = AIConversation(
        family_id=family_id,
        family_member_id=member_id,
        surface=surface,
    )
    db.add(conv)
    db.flush()
    return conv


def _persist_message(
    db: Session,
    conversation_id: uuid.UUID,
    role: str,
    content: str | None = None,
    tool_calls: dict | None = None,
    tool_results: dict | None = None,
    model: str | None = None,
    token_usage: dict | None = None,
) -> AIMessage:
    msg = AIMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        tool_calls=tool_calls,
        tool_results=tool_results,
        model=model,
        token_usage=token_usage,
    )
    db.add(msg)
    db.flush()
    return msg


def _load_conversation_messages(db: Session, conversation_id: uuid.UUID, limit: int = 40) -> list[dict]:
    """Load recent messages in Anthropic API format.

    Ordering: (created_at DESC, id DESC) for the windowing query, then
    reversed in Python → (created_at ASC, id ASC) for replay. The
    secondary `id` key is defensive: with clock_timestamp() defaults
    (migration 017) multi-row flushes get distinct microsecond
    timestamps, but the id tiebreaker protects against any future
    regression or clock adjustment. Replay order must be exact —
    Anthropic rejects any history where a tool_result is not
    immediately preceded by its matching tool_use.

    QA fix (test_qa BUG #1): we also strip any orphan ``tool_use``
    blocks whose id does not have a matching ``tool_result`` anywhere
    in the loaded window. Sources of orphans include stream interrupts
    mid-turn, legacy pre-migration-017 rows, and any historical bug in
    a handler that persisted the assistant-with-tool_calls row before
    raising. Leaving them in place 400s the next Anthropic call and
    wedges the whole conversation for the user.
    """
    msgs = list(
        db.scalars(
            select(AIMessage)
            .where(AIMessage.conversation_id == conversation_id)
            .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
            .limit(limit)
        ).all()
    )
    msgs.reverse()

    # First pass: collect every tool_use id and every tool_result id so
    # we know which tool_use blocks are paired. We look at ALL tool
    # rows because a tool_result may appear multiple positions later.
    paired_ids: set[str] = set()
    for m in msgs:
        if m.role == "tool" and m.tool_results:
            tid = m.tool_results.get("tool_use_id")
            if tid:
                paired_ids.add(str(tid))

    api_messages = []
    for m in msgs:
        if m.role == "user":
            api_messages.append({"role": "user", "content": m.content or ""})
        elif m.role == "assistant":
            content_blocks = []
            if m.content:
                content_blocks.append({"type": "text", "text": m.content})
            if m.tool_calls:
                for tc in m.tool_calls:
                    tc_id = str(tc.get("id", ""))
                    # Drop unpaired tool_use blocks — they break replay.
                    if tc_id not in paired_ids:
                        continue
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc["input"],
                    })
            if content_blocks:
                api_messages.append({"role": "assistant", "content": content_blocks})
        elif m.role == "tool":
            if m.tool_results:
                tid = str(m.tool_results.get("tool_use_id", ""))
                # Belt-and-suspenders: skip a tool_result whose
                # tool_use id never appears in any earlier assistant
                # row. Anthropic rejects orphan tool_results too.
                if not tid:
                    continue
                api_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tid,
                            "content": json.dumps(m.tool_results.get("result", {})),
                        }
                    ],
                })

    return api_messages


def _detect_handoff(tool_result: dict | None) -> dict | None:
    """Return a normalized handoff dict if the tool produced one.

    Two patterns are supported:

    1. **Nested** (the common case in ``app.ai.tools``): the tool
       returns ``{"created": ..., "handoff": {...}}`` or
       ``{"status": "ready", "handoff": {...}}``. We look under the
       ``handoff`` key.
    2. **Flat**: the tool result IS the raw handoff dict (returned
       directly from ``_handoff(...)``). Kept for backwards
       compatibility in case any future tool adopts the pattern.

    Before this change, only the flat pattern was recognized, so no
    tool in the registry produced a handoff card at the HTTP response
    layer — every handoff was silently lost. The ScoutPanel's handoff
    card support has existed since Sprint 1 but never actually
    rendered in production until now.
    """
    if not isinstance(tool_result, dict):
        return None

    def _normalize(d: dict) -> dict | None:
        if "entity_type" not in d or "route_hint" not in d:
            return None
        return {
            "entity_type": str(d.get("entity_type", "")),
            "entity_id": str(d.get("entity_id", "")),
            "route_hint": str(d.get("route_hint", "")),
            "summary": str(d.get("summary", "")),
        }

    nested = tool_result.get("handoff")
    if isinstance(nested, dict):
        resolved = _normalize(nested)
        if resolved is not None:
            return resolved

    return _normalize(tool_result)


def _build_chat_result(
    *,
    conversation_id: uuid.UUID,
    response_text: str,
    model: str,
    tokens: dict,
    tool_calls_made: int,
    handoff: dict | None = None,
    pending_confirmation: dict | None = None,
) -> dict:
    return {
        "conversation_id": str(conversation_id),
        "response": response_text,
        "tool_calls_made": tool_calls_made,
        "model": model,
        "tokens": tokens,
        "handoff": handoff,
        "pending_confirmation": pending_confirmation,
    }


def _count_tool_rows(db: Session, conversation_id: uuid.UUID) -> int:
    return sum(
        1
        for _ in db.scalars(
            select(AIMessage)
            .where(AIMessage.conversation_id == conversation_id)
            .where(AIMessage.role == "tool")
        ).all()
    )


def _create_moderation_alert(
    db: Session,
    *,
    family_id: uuid.UUID,
    actor_member_id: uuid.UUID,
    conversation_id: uuid.UUID,
    category: str,
    role: str,
    surface: str,
) -> None:
    """Drop a parent_action_items row when moderation blocks a child.

    Adults blocking themselves don't create an alert — there's no one
    higher up the chain to notify. Only child-surface blocks surface
    as alerts.
    """
    is_child = role == "child" or surface == "child"
    if not is_child:
        return
    from app.models.action_items import ParentActionItem

    title = f"Scout blocked a sensitive message ({category})"
    detail = (
        "A child's message to Scout AI was blocked by the safety gate. "
        "Open the conversation to review what happened. Tap to see details."
    )
    item = ParentActionItem(
        family_id=family_id,
        created_by_member_id=actor_member_id,
        action_type="moderation_alert",
        title=title,
        detail=detail,
        entity_type="ai_conversation",
        entity_id=conversation_id,
    )
    db.add(item)
    db.flush()


def _tag_conversation_kind(
    conversation: AIConversation,
    *,
    turn_used_tool: bool,
    turn_moderation_blocked: bool,
) -> None:
    """Update ai_conversations.conversation_kind based on what happened
    in the latest turn. Tracks across the whole conversation history:
        chat        — every turn was text-only
        tool        — every turn used at least one tool
        mixed       — some turns used tools, some didn't
        moderation  — the most recent turn was blocked by moderation
    """
    current = conversation.conversation_kind or "chat"
    if turn_moderation_blocked:
        conversation.conversation_kind = "moderation"
        return
    if turn_used_tool:
        if current in ("chat", "moderation"):
            conversation.conversation_kind = "tool"
        # 'tool' and 'mixed' stay as-is
    else:
        if current == "chat":
            conversation.conversation_kind = "chat"
        elif current == "tool":
            conversation.conversation_kind = "mixed"
        elif current == "moderation":
            conversation.conversation_kind = "chat"
        # 'mixed' stays


def chat(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    surface: str,
    user_message: str,
    conversation_id: uuid.UUID | None = None,
    confirm_tool: dict | None = None,
    intent: str = "chat",
) -> dict:
    """Execute a full chat turn including tool execution.

    If ``confirm_tool`` is provided, the LLM round is skipped entirely:
    the named tool is executed directly with ``confirmed=true`` inside
    the existing conversation. This backs the ScoutPanel confirm-card
    affordance for confirmation-gated shared-write tools.

    ``intent`` routes to the appropriate tool-loop cap and optional
    planner prompt suffix. Default 'chat' preserves existing behavior.
    """
    context = load_member_context(db, family_id, member_id)
    system_prompt = build_system_prompt(context, surface, db=db)
    if intent == "weekly_plan":
        system_prompt = _append_planner_suffix(system_prompt)
    role = context["member"]["role"]

    allowed_tool_names = get_allowed_tools_for_surface(role, surface)
    tool_defs = [TOOL_DEFINITIONS[t] for t in allowed_tool_names if t in TOOL_DEFINITIONS]

    conversation = get_or_create_conversation(db, family_id, member_id, surface, conversation_id)

    executor = ToolExecutor(
        db=db,
        family_id=family_id,
        actor_member_id=member_id,
        actor_role=role,
        surface=surface,
        conversation_id=conversation.id,
        allowed_tools=allowed_tool_names,
    )

    # --- Direct confirmation path: bypass LLM, execute tool with confirmed=true.
    if confirm_tool is not None:
        tool_name = confirm_tool.get("tool_name") or ""
        args = dict(confirm_tool.get("arguments") or {})
        args["confirmed"] = True

        if user_message:
            _persist_message(db, conversation.id, "user", content=user_message)

        tool_result = executor.execute(tool_name, args)
        synthetic_tool_id = f"confirm-{uuid.uuid4().hex[:8]}"
        _persist_message(
            db, conversation.id, "tool",
            tool_results={"tool_use_id": synthetic_tool_id, "result": tool_result},
        )

        handoff = _detect_handoff(tool_result)
        if isinstance(tool_result, dict) and tool_result.get("error"):
            response_text = str(tool_result.get("error"))
        elif handoff:
            response_text = handoff["summary"] or f"Done — {tool_name} completed."
        else:
            response_text = f"Done — {tool_name} completed."

        _persist_message(
            db, conversation.id, "assistant",
            content=response_text,
            model="confirmation-direct",
            token_usage={"input": 0, "output": 0},
        )
        _tag_conversation_kind(
            conversation, turn_used_tool=True, turn_moderation_blocked=False
        )
        db.commit()

        return _build_chat_result(
            conversation_id=conversation.id,
            response_text=response_text,
            model="confirmation-direct",
            tokens={"input": 0, "output": 0},
            tool_calls_made=_count_tool_rows(db, conversation.id),
            handoff=handoff,
            pending_confirmation=None,
        )

    # --- Normal LLM-driven turn.
    # Persist user message first so the history load includes it.
    _persist_message(db, conversation.id, "user", content=user_message)

    # Moderation gate: deterministic reject list that runs before any
    # Anthropic call. On block, we write an audit row, persist a canned
    # assistant reply to the conversation, and return immediately with
    # model='moderation-blocked'. No tokens spent, no LLM reasoning.
    mod = check_user_message(user_message, role=role, surface=surface)
    if not mod.allowed:
        _audit(
            db=db,
            family_id=family_id,
            actor_id=member_id,
            conversation_id=conversation.id,
            tool_name="moderation",
            arguments={"category": mod.category, "surface": surface, "role": role},
            result_summary=(mod.user_facing_message or "")[:500],
            status="moderation_blocked",
            error_message=mod.category,
        )
        refusal_text = mod.user_facing_message or "I can't help with that."
        _persist_message(
            db, conversation.id, "assistant",
            content=refusal_text,
            model="moderation-blocked",
            token_usage={"input": 0, "output": 0},
        )
        _create_moderation_alert(
            db,
            family_id=family_id,
            actor_member_id=member_id,
            conversation_id=conversation.id,
            category=mod.category or "unknown",
            role=role,
            surface=surface,
        )
        _tag_conversation_kind(
            conversation, turn_used_tool=False, turn_moderation_blocked=True
        )
        db.commit()
        return _build_chat_result(
            conversation_id=conversation.id,
            response_text=refusal_text,
            model="moderation-blocked",
            tokens={"input": 0, "output": 0},
            tool_calls_made=_count_tool_rows(db, conversation.id),
            handoff=None,
            pending_confirmation=None,
        )

    # Homework detection — cheap keyword classifier. No-op for adults.
    record_homework_turn(
        db,
        family_id=family_id,
        member_id=member_id,
        conversation_id=conversation.id,
        message=user_message,
        role=role,
        surface=surface,
    )

    messages = _load_conversation_messages(db, conversation.id)

    provider = get_provider()

    final_response: AIResponse | None = None
    handoff: dict | None = None
    pending_confirmation: dict | None = None
    turn_tool_calls = 0  # incremented each time the executor runs a tool this turn

    max_rounds = _rounds_for_intent(intent)
    for _round in range(max_rounds):
        response = provider.chat(
            messages=messages,
            system=system_prompt,
            tools=tool_defs if tool_defs else None,
        )

        if not response.tool_calls:
            final_response = response
            break

        tc_data = [{"id": tc.id, "name": tc.name, "input": tc.input} for tc in response.tool_calls]
        _persist_message(
            db, conversation.id, "assistant",
            content=response.content if response.content else None,
            tool_calls=tc_data,
            model=response.model,
            token_usage={"input": response.input_tokens, "output": response.output_tokens},
        )

        tc = response.tool_calls[0]
        tool_result = executor.execute(tc.name, tc.input)
        turn_tool_calls += 1

        _persist_message(
            db, conversation.id, "tool",
            tool_results={"tool_use_id": tc.id, "result": tool_result},
        )

        # Structurally surface confirmation_required: break the loop and expose
        # the pending request in the HTTP response. The ScoutPanel renders a
        # confirm/cancel card against this payload.
        if isinstance(tool_result, dict) and tool_result.get("confirmation_required"):
            pending_confirmation = {
                "tool_name": str(tool_result.get("tool_name") or tc.name),
                "arguments": dict(tool_result.get("arguments") or tc.input),
                "message": str(
                    tool_result.get("message")
                    or "Please confirm this action before I run it."
                ),
            }
            final_response = response
            break

        # Structurally surface handoff so the UI can deep-link into the
        # entity. The LLM still gets the handoff in its tool_result for
        # natural-language narration in a subsequent round.
        detected = _detect_handoff(tool_result)
        if detected is not None:
            handoff = detected

        assistant_content = []
        if response.content:
            assistant_content.append({"type": "text", "text": response.content})
        assistant_content.append({
            "type": "tool_use",
            "id": tc.id,
            "name": tc.name,
            "input": tc.input,
        })
        messages.append({"role": "assistant", "content": assistant_content})
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": json.dumps(tool_result),
                }
            ],
        })
    else:
        final_response = response

    # Build the final assistant text. If we broke on pending_confirmation, the
    # last response.content may be empty — fall back to the confirmation message
    # so the panel always has something to render.
    response_text = final_response.content if final_response else ""
    if pending_confirmation and not response_text:
        response_text = pending_confirmation["message"]

    _persist_message(
        db, conversation.id, "assistant",
        content=response_text,
        model=final_response.model if final_response else None,
        token_usage={
            "input": final_response.input_tokens if final_response else 0,
            "output": final_response.output_tokens if final_response else 0,
        },
    )
    _tag_conversation_kind(
        conversation,
        turn_used_tool=turn_tool_calls > 0,
        turn_moderation_blocked=False,
    )
    db.commit()

    return _build_chat_result(
        conversation_id=conversation.id,
        response_text=response_text,
        model=final_response.model if final_response else "",
        tokens={
            "input": final_response.input_tokens if final_response else 0,
            "output": final_response.output_tokens if final_response else 0,
        },
        tool_calls_made=_count_tool_rows(db, conversation.id),
        handoff=handoff,
        pending_confirmation=pending_confirmation,
    )


def chat_stream(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    surface: str,
    user_message: str,
    conversation_id: uuid.UUID | None = None,
    intent: str = "chat",
) -> Iterator[dict]:
    """Streaming version of chat().

    Yields structured events that the route serializes as SSE frames:

      {"type": "text", "text": "..."}          — partial assistant text chunk
      {"type": "tool_start", "name": "..."}    — tool about to execute
      {"type": "tool_end", "name": "...", "ok": bool}
      {"type": "done",                         — final event, always last
       "conversation_id": "...",
       "response": "full text",
       "model": "...",
       "tool_calls_made": N,
       "tokens": {"input": N, "output": N},
       "handoff": {...} | None,
       "pending_confirmation": {...} | None}
      {"type": "error", "message": "..."}      — terminal error

    The confirm_tool direct path is not available here: the frontend
    still POSTs to /api/ai/chat for confirmation resubmits, because
    those don't need streaming and are one atomic tool call.
    """
    context = load_member_context(db, family_id, member_id)
    system_prompt = build_system_prompt(context, surface, db=db)
    if intent == "weekly_plan":
        system_prompt = _append_planner_suffix(system_prompt)
    role = context["member"]["role"]

    allowed_tool_names = get_allowed_tools_for_surface(role, surface)
    tool_defs = [TOOL_DEFINITIONS[t] for t in allowed_tool_names if t in TOOL_DEFINITIONS]

    conversation = get_or_create_conversation(db, family_id, member_id, surface, conversation_id)
    executor = ToolExecutor(
        db=db,
        family_id=family_id,
        actor_member_id=member_id,
        actor_role=role,
        surface=surface,
        conversation_id=conversation.id,
        allowed_tools=allowed_tool_names,
    )

    _persist_message(db, conversation.id, "user", content=user_message)

    # Moderation gate runs first — on block, emit a single text event
    # with the refusal, create the parent alert, and terminate.
    mod = check_user_message(user_message, role=role, surface=surface)
    if not mod.allowed:
        _audit(
            db=db,
            family_id=family_id,
            actor_id=member_id,
            conversation_id=conversation.id,
            tool_name="moderation",
            arguments={"category": mod.category, "surface": surface, "role": role},
            result_summary=(mod.user_facing_message or "")[:500],
            status="moderation_blocked",
            error_message=mod.category,
        )
        refusal_text = mod.user_facing_message or "I can't help with that."
        _persist_message(
            db, conversation.id, "assistant",
            content=refusal_text,
            model="moderation-blocked",
            token_usage={"input": 0, "output": 0},
        )
        _create_moderation_alert(
            db,
            family_id=family_id,
            actor_member_id=member_id,
            conversation_id=conversation.id,
            category=mod.category or "unknown",
            role=role,
            surface=surface,
        )
        _tag_conversation_kind(
            conversation, turn_used_tool=False, turn_moderation_blocked=True
        )
        db.commit()

        yield {"type": "text", "text": refusal_text}
        yield {
            "type": "done",
            "conversation_id": str(conversation.id),
            "response": refusal_text,
            "model": "moderation-blocked",
            "tool_calls_made": _count_tool_rows(db, conversation.id),
            "tokens": {"input": 0, "output": 0},
            "handoff": None,
            "pending_confirmation": None,
        }
        return

    # Homework detection — cheap keyword classifier. No-op for adults.
    record_homework_turn(
        db,
        family_id=family_id,
        member_id=member_id,
        conversation_id=conversation.id,
        message=user_message,
        role=role,
        surface=surface,
    )

    messages = _load_conversation_messages(db, conversation.id)
    provider = get_provider()

    accumulated_text = ""
    last_model = ""
    total_in = 0
    total_out = 0
    handoff: dict | None = None
    pending_confirmation: dict | None = None
    turn_tool_calls = 0

    max_rounds = _rounds_for_intent(intent)
    for _round in range(max_rounds):
        # Collect this round's streamed events from Anthropic.
        round_text = ""
        round_tool_calls: list[dict] = []
        stop_reason = ""
        round_model = ""
        round_in = 0
        round_out = 0
        round_error: str | None = None

        for ev in provider.chat_stream(
            messages=messages,
            system=system_prompt,
            tools=tool_defs if tool_defs else None,
        ):
            t = ev.get("type")
            if t == "text_delta":
                chunk = ev.get("text", "") or ""
                round_text += chunk
                accumulated_text += chunk
                yield {"type": "text", "text": chunk}
            elif t == "round_end":
                stop_reason = ev.get("stop_reason", "")
                round_tool_calls = ev.get("tool_calls", [])
                round_model = ev.get("model", "")
                round_in = ev.get("input_tokens", 0)
                round_out = ev.get("output_tokens", 0)
            elif t == "error":
                round_error = ev.get("message", "upstream error")

        if round_error:
            yield {"type": "error", "message": round_error}
            # Best-effort persist what we have so the conversation isn't lost.
            if accumulated_text:
                _persist_message(
                    db, conversation.id, "assistant",
                    content=accumulated_text,
                    model=last_model or None,
                    token_usage={"input": total_in, "output": total_out},
                )
            db.commit()
            return

        last_model = round_model or last_model
        total_in += round_in
        total_out += round_out

        if not round_tool_calls:
            # Pure text round — this was the final narration.
            _persist_message(
                db, conversation.id, "assistant",
                content=round_text,
                model=round_model,
                token_usage={"input": round_in, "output": round_out},
            )
            break

        # Tool-use round: persist the assistant message with the tool_calls,
        # execute ONE tool (matching the non-streaming loop), persist the
        # result, and emit tool_start/tool_end frames so the UI can show a
        # "running tool..." indicator during the silent execution phase.
        _persist_message(
            db, conversation.id, "assistant",
            content=round_text or None,
            tool_calls=round_tool_calls,
            model=round_model,
            token_usage={"input": round_in, "output": round_out},
        )

        tc = round_tool_calls[0]
        yield {"type": "tool_start", "name": tc.get("name", "")}
        tool_result = executor.execute(tc.get("name", ""), tc.get("input", {}) or {})
        turn_tool_calls += 1

        _persist_message(
            db, conversation.id, "tool",
            tool_results={"tool_use_id": tc.get("id", ""), "result": tool_result},
        )

        ok = not (isinstance(tool_result, dict) and tool_result.get("error"))
        yield {"type": "tool_end", "name": tc.get("name", ""), "ok": ok}

        # Confirmation-required gate: break early and emit a done event.
        if isinstance(tool_result, dict) and tool_result.get("confirmation_required"):
            pending_confirmation = {
                "tool_name": str(tool_result.get("tool_name") or tc.get("name", "")),
                "arguments": dict(tool_result.get("arguments") or tc.get("input", {}) or {}),
                "message": str(
                    tool_result.get("message")
                    or "Please confirm this action before I run it."
                ),
            }
            # Ensure the user sees something — if Claude streamed no pre-tool
            # text for this turn, use the confirmation message.
            if not accumulated_text.strip():
                accumulated_text = pending_confirmation["message"]
                yield {"type": "text", "text": pending_confirmation["message"]}
            # Persist an assistant message for the turn so history replays.
            _persist_message(
                db, conversation.id, "assistant",
                content=accumulated_text,
                model=round_model,
                token_usage={"input": round_in, "output": round_out},
            )
            break

        # Capture handoff metadata for the final done event.
        detected = _detect_handoff(tool_result)
        if detected is not None:
            handoff = detected

        # Append to history for the next streamed round.
        assistant_content: list[dict] = []
        if round_text:
            assistant_content.append({"type": "text", "text": round_text})
        assistant_content.append({
            "type": "tool_use",
            "id": tc.get("id", ""),
            "name": tc.get("name", ""),
            "input": tc.get("input", {}),
        })
        messages.append({"role": "assistant", "content": assistant_content})
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tc.get("id", ""),
                    "content": json.dumps(tool_result),
                }
            ],
        })
    else:
        # Hit max_rounds without a clean end_turn. Persist whatever
        # we have and let the client see 'done' with the accumulated text.
        _persist_message(
            db, conversation.id, "assistant",
            content=accumulated_text,
            model=last_model or None,
            token_usage={"input": total_in, "output": total_out},
        )

    _tag_conversation_kind(
        conversation,
        turn_used_tool=turn_tool_calls > 0,
        turn_moderation_blocked=False,
    )
    db.commit()

    yield {
        "type": "done",
        "conversation_id": str(conversation.id),
        "response": accumulated_text,
        "model": last_model,
        "tool_calls_made": _count_tool_rows(db, conversation.id),
        "tokens": {"input": total_in, "output": total_out},
        "handoff": handoff,
        "pending_confirmation": pending_confirmation,
    }


def generate_daily_brief(db: Session, family_id: uuid.UUID, member_id: uuid.UUID) -> dict:
    """Generate a daily briefing using the summary model."""
    context = load_member_context(db, family_id, member_id)
    role = context["member"]["role"]

    executor = ToolExecutor(
        db=db, family_id=family_id, actor_member_id=member_id,
        actor_role=role, surface="personal",
        allowed_tools=["get_today_context", "list_events", "list_tasks", "get_rewards_or_allowance_status"],
    )

    today_data = executor.execute("get_today_context", {})

    provider = get_provider()
    system = build_system_prompt(context, "personal")
    prompt = (
        "Generate a concise daily briefing based on this data. "
        "Include: key tasks, events, meals, and anything that needs attention today. "
        "Keep it under 200 words. Be direct and useful.\n\n"
        f"Today's data: {json.dumps(today_data, default=str)}"
    )

    response = provider.chat(
        messages=[{"role": "user", "content": prompt}],
        system=system,
        model=None,  # uses default summary model
        max_tokens=512,
    )

    return {
        "brief": response.content,
        "date": date.today().isoformat(),
        "model": response.model,
    }


def generate_weekly_plan(db: Session, family_id: uuid.UUID, member_id: uuid.UUID) -> dict:
    """Generate a weekly planning summary."""
    context = load_member_context(db, family_id, member_id)
    role = context["member"]["role"]

    executor = ToolExecutor(
        db=db, family_id=family_id, actor_member_id=member_id,
        actor_role=role, surface="personal",
        allowed_tools=["list_events", "list_tasks", "list_meals_or_meal_plan"],
    )

    now = datetime.now()
    monday = now - timedelta(days=now.weekday())
    sunday = monday + timedelta(days=6)

    events = executor.execute("list_events", {
        "start": monday.isoformat(),
        "end": sunday.isoformat(),
    })
    tasks = executor.execute("list_tasks", {"incomplete_only": True})

    provider = get_provider()
    system = build_system_prompt(context, "personal")
    prompt = (
        "Generate a concise weekly plan based on this data. "
        "Highlight key commitments, deadlines, and priorities. "
        "Keep it under 300 words.\n\n"
        f"Events: {json.dumps(events, default=str)}\n"
        f"Tasks: {json.dumps(tasks, default=str)}"
    )

    response = provider.chat(
        messages=[{"role": "user", "content": prompt}],
        system=system,
        max_tokens=768,
    )

    return {
        "plan": response.content,
        "week_start": monday.date().isoformat(),
        "model": response.model,
    }


def suggest_staple_meals(db: Session, family_id: uuid.UUID, member_id: uuid.UUID) -> dict:
    """Suggest staple meals based on past meal history and preferences."""
    context = load_member_context(db, family_id, member_id)

    meals = meals_service_list_recent(db, family_id)

    provider = get_provider()
    system = build_system_prompt(context, "personal")
    prompt = (
        "Based on these recent family meals, suggest 5-7 reliable staple meals "
        "that could be part of a regular weekly rotation. "
        "Consider variety and family-friendly options. "
        "Return as a simple list with meal name and brief description.\n\n"
        f"Recent meals: {json.dumps(meals, default=str)}"
    )

    response = provider.chat(
        messages=[{"role": "user", "content": prompt}],
        system=system,
        max_tokens=512,
    )

    return {
        "suggestions": response.content,
        "model": response.model,
    }


def meals_service_list_recent(db: Session, family_id: uuid.UUID) -> list:
    """Helper to get recent meals for suggestion context."""
    from app.services import meals_service
    meals = meals_service.list_meals(db, family_id)
    return [{"title": m.title, "meal_type": m.meal_type, "date": m.meal_date.isoformat()} for m in meals[:30]]

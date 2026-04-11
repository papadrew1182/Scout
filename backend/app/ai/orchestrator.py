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
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.context import (
    build_system_prompt,
    get_allowed_tools_for_surface,
    load_member_context,
)
from app.ai.provider import AIResponse, AnthropicProvider, ToolDefinition, get_provider
from app.ai.tools import TOOL_DEFINITIONS, ToolExecutor
from app.models.ai import AIConversation, AIMessage


MAX_TOOL_ROUNDS = 5


def get_or_create_conversation(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    surface: str,
    conversation_id: uuid.UUID | None = None,
) -> AIConversation:
    if conversation_id:
        conv = db.get(AIConversation, conversation_id)
        if conv and conv.family_id == family_id and conv.family_member_id == member_id:
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
    """Load recent messages in Anthropic API format."""
    msgs = list(
        db.scalars(
            select(AIMessage)
            .where(AIMessage.conversation_id == conversation_id)
            .order_by(AIMessage.created_at.desc())
            .limit(limit)
        ).all()
    )
    msgs.reverse()

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
                api_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_results.get("tool_use_id", ""),
                            "content": json.dumps(m.tool_results.get("result", {})),
                        }
                    ],
                })

    return api_messages


def chat(
    db: Session,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    surface: str,
    user_message: str,
    conversation_id: uuid.UUID | None = None,
) -> dict:
    """Execute a full chat turn including tool execution."""
    context = load_member_context(db, family_id, member_id)
    system_prompt = build_system_prompt(context, surface)
    role = context["member"]["role"]

    allowed_tool_names = get_allowed_tools_for_surface(role, surface)
    tool_defs = [TOOL_DEFINITIONS[t] for t in allowed_tool_names if t in TOOL_DEFINITIONS]

    conversation = get_or_create_conversation(db, family_id, member_id, surface, conversation_id)

    # Persist user message
    _persist_message(db, conversation.id, "user", content=user_message)

    # Load conversation history
    messages = _load_conversation_messages(db, conversation.id)

    provider = get_provider()
    executor = ToolExecutor(
        db=db,
        family_id=family_id,
        actor_member_id=member_id,
        actor_role=role,
        surface=surface,
        conversation_id=conversation.id,
        allowed_tools=allowed_tool_names,
    )

    # Tool execution loop (bounded)
    final_response: AIResponse | None = None
    for _round in range(MAX_TOOL_ROUNDS):
        response = provider.chat(
            messages=messages,
            system=system_prompt,
            tools=tool_defs if tool_defs else None,
        )

        if not response.tool_calls:
            # No tool calls — this is the final response
            final_response = response
            break

        # Persist assistant message with tool calls
        tc_data = [{"id": tc.id, "name": tc.name, "input": tc.input} for tc in response.tool_calls]
        _persist_message(
            db, conversation.id, "assistant",
            content=response.content if response.content else None,
            tool_calls=tc_data,
            model=response.model,
            token_usage={"input": response.input_tokens, "output": response.output_tokens},
        )

        # Execute ONE tool call (bounded, no autonomous multi-step)
        tc = response.tool_calls[0]
        tool_result = executor.execute(tc.name, tc.input)

        # Persist tool result
        _persist_message(
            db, conversation.id, "tool",
            tool_results={"tool_use_id": tc.id, "result": tool_result},
        )

        # Add to message history for next round
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
        # Hit max rounds without a final text response
        final_response = response

    # Persist final assistant message
    _persist_message(
        db, conversation.id, "assistant",
        content=final_response.content if final_response else "",
        model=final_response.model if final_response else None,
        token_usage={
            "input": final_response.input_tokens if final_response else 0,
            "output": final_response.output_tokens if final_response else 0,
        },
    )

    db.commit()

    return {
        "conversation_id": str(conversation.id),
        "response": final_response.content if final_response else "",
        "tool_calls_made": sum(
            1 for m in db.scalars(
                select(AIMessage)
                .where(AIMessage.conversation_id == conversation.id)
                .where(AIMessage.role == "tool")
            ).all()
        ),
        "model": final_response.model if final_response else "",
        "tokens": {
            "input": final_response.input_tokens if final_response else 0,
            "output": final_response.output_tokens if final_response else 0,
        },
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

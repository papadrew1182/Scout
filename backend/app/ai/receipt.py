"""Receipt photo → structured grocery item extraction.

Uses the existing Anthropic provider with a vision content block. The
frontend uploads a photo, the backend base64-encodes and sends it to
Claude Sonnet with a strict extraction prompt, and returns a proposal
list for human review.

The endpoint NEVER writes grocery rows directly. The frontend renders
the proposals in an editable review card and the user confirms each
one before the existing ``add_grocery_item`` service is called.
Nothing about receipt upload bypasses the family-scoped write path.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import anthropic

from app.config import settings

logger = logging.getLogger("scout.ai.receipt")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic"}

EXTRACTION_SYSTEM = (
    "You extract grocery items from receipt photos. Return a JSON array "
    "of objects with fields: title (string, short, normalized to a "
    "human-readable name), quantity (number or null), unit (string or "
    "null like 'lb', 'oz', 'each', 'pack'), category (one of: 'produce', "
    "'dairy', 'protein', 'pantry', 'frozen', 'beverages', 'bakery', "
    "'household', 'other'), confidence (0.0..1.0). Skip sales tax lines, "
    "totals, subtotals, store names, coupon lines, and any non-item text. "
    "If a line is unreadable, skip it. Output ONLY the JSON array, no "
    "prose, no markdown code fences."
)

EXTRACTION_USER = (
    "Extract all grocery items from this receipt photo. Normalize "
    "names (e.g. 'ORG BANANAS 2LB' → 'Organic bananas'). Use null "
    "for missing fields. Return the JSON array only."
)


@dataclass
class ReceiptProposal:
    title: str
    quantity: float | None
    unit: str | None
    category: str | None
    confidence: float


@dataclass
class ReceiptExtractionResult:
    items: list[ReceiptProposal]
    model: str
    input_tokens: int
    output_tokens: int


def extract_items_from_receipt(
    image_bytes: bytes, content_type: str
) -> ReceiptExtractionResult:
    """Call Claude vision on a receipt image. Raises on provider failure
    OR bad input.

    Input validation: ``content_type`` must be in ALLOWED_MIME and
    ``len(image_bytes)`` must be within MAX_UPLOAD_BYTES. Caller
    (the route handler) should also enforce these at the HTTP layer
    for cleaner error codes.
    """
    if not settings.anthropic_api_key:
        raise RuntimeError("anthropic_api_key_not_set")
    if content_type not in ALLOWED_MIME:
        raise ValueError(f"unsupported content_type: {content_type}")
    if not image_bytes or len(image_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError("image size out of bounds")

    # Normalize jpg → jpeg for Anthropic's media_type. heic is not
    # officially supported; callers should transcode first.
    media_type = "image/jpeg" if content_type in ("image/jpg", "image/jpeg") else content_type
    if media_type == "image/heic":
        raise ValueError("HEIC not supported — please upload JPEG/PNG/WEBP")

    encoded = base64.b64encode(image_bytes).decode()

    client = anthropic.Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.ai_request_timeout,
    )
    response = client.messages.create(
        model=settings.ai_chat_model,
        max_tokens=2048,
        temperature=0.1,
        system=EXTRACTION_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": encoded,
                        },
                    },
                    {"type": "text", "text": EXTRACTION_USER},
                ],
            }
        ],
    )

    text = "".join(
        b.text for b in response.content if getattr(b, "type", "") == "text"
    ).strip()

    items = _parse_proposals(text)
    logger.info(
        "receipt_extract_ok bytes=%d media=%s items=%d",
        len(image_bytes), media_type, len(items),
    )
    return ReceiptExtractionResult(
        items=items,
        model=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


_JSON_ARRAY_RX = re.compile(r"\[\s*\{.*?\}\s*\]", re.DOTALL)


def _parse_proposals(text: str) -> list[ReceiptProposal]:
    """Parse the model's output into a list of ReceiptProposal.

    Be forgiving: if the model wrapped the JSON in code fences or
    prose, extract the first JSON array substring. If parsing fails
    entirely, return an empty list and log — the route layer surfaces
    that as an empty proposal set rather than a 500.
    """
    if not text:
        return []

    candidate = text
    m = _JSON_ARRAY_RX.search(text)
    if m:
        candidate = m.group(0)

    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        logger.warning("receipt_parse_failed preview=%r", text[:200])
        return []

    if not isinstance(data, list):
        return []

    out: list[ReceiptProposal] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        qty_raw = row.get("quantity")
        try:
            quantity = float(qty_raw) if qty_raw not in (None, "") else None
        except (TypeError, ValueError):
            quantity = None
        unit_raw = row.get("unit")
        unit = str(unit_raw).strip() if unit_raw not in (None, "") else None
        category_raw = row.get("category")
        category = str(category_raw).strip() if category_raw not in (None, "") else None
        conf_raw = row.get("confidence")
        try:
            confidence = float(conf_raw) if conf_raw not in (None, "") else 0.5
        except (TypeError, ValueError):
            confidence = 0.5
        out.append(
            ReceiptProposal(
                title=title[:200],
                quantity=quantity,
                unit=unit[:20] if unit else None,
                category=category[:30] if category else None,
                confidence=max(0.0, min(1.0, confidence)),
            )
        )
    return out

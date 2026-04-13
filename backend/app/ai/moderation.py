"""User-message moderation for Scout AI.

Runs BEFORE the message reaches Anthropic. This is a cheap first-line
defense, not a replacement for Claude's built-in safety training. It
exists because:

1. The child surface must never pass explicit / self-harm / violence
   / drugs content to the LLM, even if Claude would refuse.
2. We want a deterministic audit trail of blocked messages (via
   AIToolAudit with status='moderation_blocked') so parents can see
   what happened.
3. Certain categories (sexual content involving minors, instructions
   for self-harm) should never even reach the model.

Design: keyword + regex reject list grouped by category. Simple but
intentional. Tuned conservatively for the child surface and more
permissively for adults. The adult surface still blocks the small set
of categories that are never allowed regardless of user age.

Returns a ModerationResult dataclass so the orchestrator can log the
category and tell the user which rule fired.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# --- Categories that apply to ALL surfaces, including adults.
# These are never allowed through no matter who is asking.
_UNIVERSAL_BLOCKED = [
    # Sexual content involving minors
    (
        re.compile(
            r"\b(child|kid|minor|underage|teen|preteen|tween|"
            r"boy|girl)\s*(porn|sex|nude|naked|erotic|fuck|blowjob)",
            re.IGNORECASE,
        ),
        "csam",
    ),
    (
        re.compile(r"\bcsam\b|\bloli\b|\bshota\b", re.IGNORECASE),
        "csam",
    ),
    # Explicit instructions for making weapons of mass harm
    (
        re.compile(
            r"\b(how to (make|build|synthesize|cook))\s+"
            r"(a\s+)?(bomb|pipe bomb|nerve gas|sarin|ricin|meth|fentanyl)",
            re.IGNORECASE,
        ),
        "weapons_or_drugs_synthesis",
    ),
    # Direct self-harm instructions
    (
        re.compile(
            r"\b(how to|easiest way to|best way to)\s+"
            r"(kill myself|commit suicide|overdose|hang myself)",
            re.IGNORECASE,
        ),
        "self_harm_instructions",
    ),
]


# --- Categories that apply ONLY to the child surface.
# Adults can ask about these; kids cannot.
_CHILD_BLOCKED = [
    # Explicit sexual content
    (
        re.compile(
            r"\b(porn|pornography|xxx|nude|naked|blowjob|"
            r"hentai|erotic|sex tape)\b",
            re.IGNORECASE,
        ),
        "explicit_sexual",
    ),
    # Romantic role-play that goes further than age-appropriate
    (
        re.compile(r"\b(make out|french kiss|sext|sexting)\b", re.IGNORECASE),
        "explicit_sexual",
    ),
    # Drugs / alcohol
    (
        re.compile(
            r"\b(how\s+(do|to|can)\s+(i\s+|you\s+)?get\s+(high|drunk|stoned)|"
            r"buy\s+(weed|cocaine|heroin|meth|lsd|ecstasy|xanax\s+without|adderall\s+without)|"
            r"how\s+to\s+roll\s+a\s+joint|how\s+to\s+smoke\s+(weed|meth|crack))\b",
            re.IGNORECASE,
        ),
        "drugs_or_alcohol",
    ),
    # Violence and weapons
    (
        re.compile(
            r"\b(how to (hurt|beat up|stab|shoot|kill)|"
            r"where can i (get|buy) a gun|make a gun)\b",
            re.IGNORECASE,
        ),
        "violence_or_weapons",
    ),
    # Self-harm ideation (softer filter than universal — kids get
    # redirected to a trusted adult)
    (
        re.compile(
            r"\b(i want to (die|kill myself)|"
            r"cut myself|self[- ]harm|"
            r"no one would miss me|end it all)\b",
            re.IGNORECASE,
        ),
        "self_harm_concern",
    ),
]


@dataclass
class ModerationResult:
    allowed: bool
    category: str | None
    user_facing_message: str | None


# User-facing copy for each blocked category.
# These are what the UI renders; tuned for the audience.
_BLOCK_COPY_ADULT: dict[str, str] = {
    "csam": (
        "I can't help with that. If you're concerned about child safety, "
        "the National Center for Missing and Exploited Children (NCMEC) "
        "is 1-800-843-5678."
    ),
    "weapons_or_drugs_synthesis": (
        "I can't help with weapon or drug synthesis. If you're working on "
        "something legitimate (chemistry homework, safety research), try "
        "rephrasing and I'll do my best."
    ),
    "self_harm_instructions": (
        "I can't help with that. Please reach out — the 988 Suicide and "
        "Crisis Lifeline is 988 (call or text, 24/7, US)."
    ),
}

_BLOCK_COPY_CHILD: dict[str, str] = {
    "csam": (
        "That's not something I can help with. If someone is making you "
        "uncomfortable, tell a parent right away."
    ),
    "weapons_or_drugs_synthesis": (
        "I can't help with that. If it's for a school project, ask a parent "
        "to help you find safer sources."
    ),
    "self_harm_instructions": (
        "I'm really glad you told me. Please talk to a parent or another "
        "trusted adult in your family right now. You can also call or text "
        "988 any time — it's the Suicide and Crisis Lifeline and they're "
        "there just for this."
    ),
    "explicit_sexual": (
        "That's a grown-up topic. I can't help with it. If you have "
        "questions about your body or growing up, a parent is the best "
        "person to ask."
    ),
    "drugs_or_alcohol": (
        "I can't help with that. Please talk to a parent if you have "
        "questions about this."
    ),
    "violence_or_weapons": (
        "I can't help with that. If you're worried about getting hurt or "
        "hurting someone, please tell a parent right away."
    ),
    "self_harm_concern": (
        "I'm sorry you're feeling that way. Please tell a parent or another "
        "trusted adult right now — they want to help. You can also call or "
        "text 988, it's free and they're kind. You're not alone."
    ),
}


def check_user_message(message: str, *, role: str, surface: str) -> ModerationResult:
    """Pre-LLM moderation.

    Returns ``ModerationResult(allowed=True, ...)`` for ordinary messages.
    Returns ``ModerationResult(allowed=False, category=..., user_facing_message=...)``
    when the message matches a blocked category.

    ``role`` is 'adult' or 'child'. ``surface`` is 'personal' / 'parent' /
    'child'. The child ruleset applies whenever role=='child' OR
    surface=='child' (so adults role-playing on the child surface still
    get the stricter rules).
    """
    if not message:
        return ModerationResult(allowed=True, category=None, user_facing_message=None)

    is_child = role == "child" or surface == "child"
    copy_table = _BLOCK_COPY_CHILD if is_child else _BLOCK_COPY_ADULT

    # Universal blocks fire for everyone.
    for rx, category in _UNIVERSAL_BLOCKED:
        if rx.search(message):
            return ModerationResult(
                allowed=False,
                category=category,
                user_facing_message=copy_table.get(category, _fallback_copy(is_child)),
            )

    # Child-surface-only blocks.
    if is_child:
        for rx, category in _CHILD_BLOCKED:
            if rx.search(message):
                return ModerationResult(
                    allowed=False,
                    category=category,
                    user_facing_message=_BLOCK_COPY_CHILD.get(
                        category, _fallback_copy(True)
                    ),
                )

    return ModerationResult(allowed=True, category=None, user_facing_message=None)


def _fallback_copy(is_child: bool) -> str:
    if is_child:
        return (
            "I can't help with that. Please talk to a parent or trusted "
            "adult in the family."
        )
    return "I can't help with that request."

"""Canonical per-tier personality defaults for Sprint 04 Phase 2.

Single source of truth for the Scout AI personality shape. Every other
module that needs a default personality (prompt composer, GET routes,
admin preview) reads from here. Do NOT duplicate these literals.

Tier names use the UPPERCASE canonical convention from migration 022
(`PRIMARY_PARENT / PARENT / TEEN / CHILD / YOUNG_CHILD`), not the
lowercase aliases from migration 024.

Schema of a personality config (stored in `member_config` under key
`ai.personality`):

    tone             one of TONE_OPTIONS
    vocabulary_level one of VOCAB_OPTIONS
    formality        one of FORMALITY_OPTIONS
    humor            one of HUMOR_OPTIONS
    proactivity      one of PROACTIVITY_OPTIONS (no runtime effect yet)
    verbosity        one of VERBOSITY_OPTIONS
    notes_to_self    free text, max 500 chars
    role_hints       free text, max 200 chars

The GET routes return the merged view: stored config overlaid on tier
defaults. A member with no `member_config` row still gets a sensible
personality without any backfill migration.
"""

from __future__ import annotations

from typing import Any

TONE_OPTIONS = ("warm", "direct", "playful", "professional")
VOCAB_OPTIONS = ("simple", "standard", "advanced")
FORMALITY_OPTIONS = ("casual", "neutral", "formal")
HUMOR_OPTIONS = ("none", "light", "dry")
PROACTIVITY_OPTIONS = ("quiet", "balanced", "forthcoming")
VERBOSITY_OPTIONS = ("short", "standard", "detailed")

NOTES_MAX = 500
ROLE_HINTS_MAX = 200

# Every allowed key. Unknown keys on PATCH are rejected.
ALLOWED_KEYS = frozenset(
    {
        "tone",
        "vocabulary_level",
        "formality",
        "humor",
        "proactivity",
        "verbosity",
        "notes_to_self",
        "role_hints",
    }
)

_ADULT_DEFAULT: dict[str, Any] = {
    "tone": "direct",
    "vocabulary_level": "advanced",
    "formality": "casual",
    "humor": "dry",
    "proactivity": "balanced",
    "verbosity": "short",
    "notes_to_self": "",
    "role_hints": "",
}

_TEEN_DEFAULT: dict[str, Any] = {
    "tone": "warm",
    "vocabulary_level": "standard",
    "formality": "casual",
    "humor": "light",
    "proactivity": "balanced",
    "verbosity": "standard",
    "notes_to_self": "",
    "role_hints": "",
}

_CHILD_DEFAULT: dict[str, Any] = {
    "tone": "warm",
    "vocabulary_level": "standard",
    "formality": "casual",
    "humor": "light",
    "proactivity": "quiet",
    "verbosity": "short",
    "notes_to_self": "",
    "role_hints": "",
}

_YOUNG_CHILD_DEFAULT: dict[str, Any] = {
    "tone": "playful",
    "vocabulary_level": "simple",
    "formality": "casual",
    "humor": "light",
    "proactivity": "quiet",
    "verbosity": "short",
    "notes_to_self": "",
    "role_hints": "",
}

# Fallback for unknown tier names. Errs on the side of the child-safe
# defaults — if we don't know what tier the member is, we don't want
# to hand them the adult tone stack.
_FALLBACK_DEFAULT: dict[str, Any] = dict(_CHILD_DEFAULT)


_BY_TIER: dict[str, dict[str, Any]] = {
    "PRIMARY_PARENT": _ADULT_DEFAULT,
    "PARENT": _ADULT_DEFAULT,
    "TEEN": _TEEN_DEFAULT,
    "CHILD": _CHILD_DEFAULT,
    "YOUNG_CHILD": _YOUNG_CHILD_DEFAULT,
}


def defaults_for_tier(tier: str | None) -> dict[str, Any]:
    """Return a COPY of the tier's canonical defaults. Callers mutate
    the returned dict freely without risk of polluting the module-level
    templates."""
    if tier and tier in _BY_TIER:
        return dict(_BY_TIER[tier])
    return dict(_FALLBACK_DEFAULT)


def merge_over_defaults(
    stored: dict[str, Any] | None, tier: str | None
) -> dict[str, Any]:
    """Overlay a stored personality config on tier defaults. Missing
    keys fall back to the tier default. Unknown keys in `stored` are
    dropped silently (write-path validation happens in the service)."""
    merged = defaults_for_tier(tier)
    if not stored:
        return merged
    for key in ALLOWED_KEYS:
        if key in stored:
            merged[key] = stored[key]
    return merged

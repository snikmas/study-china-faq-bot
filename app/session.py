"""Deterministic session helpers for Streamlit state dictionaries."""

from __future__ import annotations

from collections.abc import MutableMapping


QUESTION_LIMIT = 500
COOLDOWN_SECONDS = 3.0
CALL_LIMIT = 20

CALL_COUNT_KEY = "classifier_call_count"
LAST_CALL_AT_KEY = "last_classifier_call_at"


def initialize_session(state: MutableMapping[str, object]) -> None:
    state.setdefault(CALL_COUNT_KEY, 0)
    state.setdefault(LAST_CALL_AT_KEY, None)
    state.setdefault("answers", [])
    state.setdefault("inquiry_sent", False)
    state.setdefault("inquiry_ambiguous", False)


def clean_question(question: str) -> str:
    return question.strip()


def question_error(question: str) -> str | None:
    cleaned = clean_question(question)
    if not cleaned:
        return "empty"
    if len(cleaned) > QUESTION_LIMIT:
        return "too_long"
    return None


def call_count(state: MutableMapping[str, object]) -> int:
    value = state.get(CALL_COUNT_KEY, 0)
    return value if isinstance(value, int) and value >= 0 else 0


def calls_remaining(state: MutableMapping[str, object]) -> int:
    return max(0, CALL_LIMIT - call_count(state))


def cooldown_remaining(state: MutableMapping[str, object], now: float) -> float:
    value = state.get(LAST_CALL_AT_KEY)
    if not isinstance(value, (int, float)):
        return 0.0
    elapsed = now - float(value)
    if elapsed >= COOLDOWN_SECONDS:
        return 0.0
    return COOLDOWN_SECONDS - elapsed


def can_call(state: MutableMapping[str, object], now: float) -> tuple[bool, str | None, float]:
    if call_count(state) >= CALL_LIMIT:
        return False, "limit", 0.0
    wait = cooldown_remaining(state, now)
    if wait > 0:
        return False, "cooldown", wait
    return True, None, 0.0


def record_call(state: MutableMapping[str, object], now: float) -> None:
    state[CALL_COUNT_KEY] = call_count(state) + 1
    state[LAST_CALL_AT_KEY] = float(now)


__all__ = [
    "CALL_LIMIT",
    "COOLDOWN_SECONDS",
    "QUESTION_LIMIT",
    "can_call",
    "call_count",
    "calls_remaining",
    "clean_question",
    "cooldown_remaining",
    "initialize_session",
    "question_error",
    "record_call",
]

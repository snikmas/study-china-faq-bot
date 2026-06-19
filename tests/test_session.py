from app.session import (
    CALL_LIMIT,
    COOLDOWN_SECONDS,
    QUESTION_LIMIT,
    can_call,
    call_count,
    calls_remaining,
    cooldown_remaining,
    initialize_session,
    question_error,
    record_call,
)


def test_initialize_session_sets_defaults_without_overwriting_existing_values() -> None:
    state: dict[str, object] = {"classifier_call_count": 2}

    initialize_session(state)

    assert state["classifier_call_count"] == 2
    assert state["last_classifier_call_at"] is None
    assert state["answers"] == []
    assert state["inquiry_sent"] is False


def test_question_validation_is_deterministic() -> None:
    assert question_error("  ") == "empty"
    assert question_error("x" * QUESTION_LIMIT) is None
    assert question_error("x" * (QUESTION_LIMIT + 1)) == "too_long"


def test_record_call_updates_count_and_cooldown() -> None:
    state: dict[str, object] = {}
    initialize_session(state)

    assert can_call(state, 10.0) == (True, None, 0.0)
    record_call(state, 10.0)

    assert call_count(state) == 1
    assert calls_remaining(state) == CALL_LIMIT - 1
    allowed, reason, wait = can_call(state, 11.0)
    assert allowed is False
    assert reason == "cooldown"
    assert wait == COOLDOWN_SECONDS - 1.0
    assert cooldown_remaining(state, 13.0) == 0.0


def test_call_limit_blocks_without_cooldown_wait() -> None:
    state: dict[str, object] = {
        "classifier_call_count": CALL_LIMIT,
        "last_classifier_call_at": 100.0,
    }

    assert calls_remaining(state) == 0
    assert can_call(state, 101.0) == (False, "limit", 0.0)


def test_bad_state_values_are_treated_as_safe_defaults() -> None:
    state: dict[str, object] = {
        "classifier_call_count": "bad",
        "last_classifier_call_at": "bad",
    }

    assert call_count(state) == 0
    assert calls_remaining(state) == CALL_LIMIT
    assert cooldown_remaining(state, 50.0) == 0.0

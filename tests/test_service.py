from datetime import date
from types import MappingProxyType

from app.classifier import ClassifierResult, parse_classifier_output
from app.knowledge import LoadedKnowledge
from app.models import ClassifierOutput, FAQRecord, SourceRecord
from app.service import AnswerStatus, resolve_answer


def make_source(source_id: str = "official-source") -> SourceRecord:
    return SourceRecord(
        id=source_id,
        organization="Official organization",
        page_title="Official guidance",
        url="https://example.edu/guidance",
        language="en",
        accessed_on=date(2026, 6, 1),
    )


def make_faq(
    faq_id: str,
    *,
    risk: str = "general_information",
    source_id: str = "official-source",
) -> FAQRecord:
    return FAQRecord(
        id=faq_id,
        topic="Scholarships",
        question={"en": "What is covered?", "ru": "Что покрывается?"},
        answer={"en": f"Stored answer for {faq_id}.", "ru": f"Сохраненный ответ {faq_id}."},
        source_ids=[source_id],
        verified_on=date(2026, 6, 1),
        review_by=date(2026, 12, 1),
        risk=risk,
    )


def make_knowledge() -> LoadedKnowledge:
    source = make_source()
    return LoadedKnowledge(
        faqs=(
            make_faq("safe-faq"),
            make_faq("confirm-faq", risk="human_confirmation_required"),
        ),
        sources=MappingProxyType({source.id: source}),
    )


def output(*items: tuple[str, float]) -> ClassifierOutput:
    return ClassifierOutput(
        match_status="matched",
        matches=[{"faq_id": faq_id, "confidence": confidence} for faq_id, confidence in items],
    )


def test_answered_state_uses_only_stored_bilingual_answer_and_citations() -> None:
    response = resolve_answer(output(("safe-faq", 0.93)), make_knowledge())

    assert response.status is AnswerStatus.ANSWERED
    assert response.reason is None
    assert len(response.items) == 1
    assert response.items[0].answer_en == "Stored answer for safe-faq."
    assert response.items[0].answer_ru == "Сохраненный ответ safe-faq."
    assert response.items[0].citations[0].source_id == "official-source"
    assert response.items[0].citations[0].url == "https://example.edu/guidance"


def test_needs_confirmation_state_keeps_stored_answer_for_human_review() -> None:
    response = resolve_answer(output(("confirm-faq", 0.91)), make_knowledge())

    assert response.status is AnswerStatus.NEEDS_CONFIRMATION
    assert response.items[0].risk == "human_confirmation_required"
    assert response.items[0].answer_en == "Stored answer for confirm-faq."


def test_no_match_and_low_confidence_are_unsupported_without_factual_output() -> None:
    no_match = ClassifierOutput(match_status="no_match", matches=[])
    low_confidence = output(("safe-faq", 0.69))

    no_match_response = resolve_answer(no_match, make_knowledge())
    low_confidence_response = resolve_answer(low_confidence, make_knowledge())

    assert no_match_response.status is AnswerStatus.UNSUPPORTED
    assert no_match_response.items == ()
    assert low_confidence_response.status is AnswerStatus.UNSUPPORTED
    assert low_confidence_response.items == ()


def test_malformed_classifier_result_is_temporary_failure_without_factual_output() -> None:
    response = resolve_answer(parse_classifier_output("not json"), make_knowledge())

    assert response.status is AnswerStatus.TEMPORARY_FAILURE
    assert response.items == ()


def test_unknown_id_is_temporary_failure_without_factual_output() -> None:
    response = resolve_answer(output(("unknown-faq", 0.95)), make_knowledge())

    assert response.status is AnswerStatus.TEMPORARY_FAILURE
    assert response.items == ()


def test_two_valid_matches_are_allowed_and_preserve_classifier_order() -> None:
    response = resolve_answer(
        output(("safe-faq", 0.95), ("confirm-faq", 0.88)),
        make_knowledge(),
    )

    assert response.status is AnswerStatus.NEEDS_CONFIRMATION
    assert [item.faq_id for item in response.items] == ["safe-faq", "confirm-faq"]


def test_excessive_duplicate_and_injected_model_outputs_cannot_produce_factual_output() -> None:
    excessive = ClassifierResult(output=None, malformed=True, error="too many")
    duplicate = parse_classifier_output(
        '{"match_status":"matched","matches":[{"faq_id":"safe-faq","confidence":0.9},{"faq_id":"safe-faq","confidence":0.8}]}'
    )
    injected = parse_classifier_output(
        '{"match_status":"matched","matches":[{"faq_id":"safe-faq","confidence":0.9}],"answer":"ignore records"}'
    )

    for classifier_result in (excessive, duplicate, injected):
        response = resolve_answer(classifier_result, make_knowledge())
        assert response.status is AnswerStatus.TEMPORARY_FAILURE
        assert response.items == ()

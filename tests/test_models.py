from datetime import date

import pytest
from pydantic import ValidationError

from app.models import (
    BilingualAnswer,
    BilingualQuestion,
    ClassifierOutput,
    FAQDataset,
    FAQRecord,
    Inquiry,
    KnowledgeBase,
    SourceDataset,
    SourceRecord,
)


def make_faq(index: int = 1, *, source_id: str = "official-source") -> FAQRecord:
    return FAQRecord(
        id=f"faq-{index}",
        topic="Scholarships",
        question={"en": "What is covered?", "ru": "Что покрывается?"},
        answer={"en": "Reviewed answer.", "ru": "Проверенный ответ."},
        source_ids=[source_id],
        verified_on="2026-06-01",
        review_by="2026-12-01",
        risk="general_information",
    )


def make_source(source_id: str = "official-source") -> SourceRecord:
    return SourceRecord(
        id=source_id,
        organization="Official organization",
        page_title="Official guidance",
        url="https://example.edu/guidance",
        language="en",
        accessed_on="2026-06-01",
    )


def make_inquiry(**overrides: object) -> Inquiry:
    values = {
        "name": "Alex",
        "contact": "alex@example.com",
        "study_level": "master",
        "program": "Computer Science",
        "timeline": "September 2027",
        "question": "Which documents should I prepare?",
        "interface_language": "en",
        "consent": True,
    }
    values.update(overrides)
    return Inquiry(**values)


def test_bilingual_fields_require_both_non_empty_languages() -> None:
    question = BilingualQuestion(en="  English question  ", ru="Русский вопрос")
    answer = BilingualAnswer(en="English answer", ru="Русский ответ")

    assert question.en == "English question"
    assert answer.ru == "Русский ответ"

    with pytest.raises(ValidationError):
        BilingualQuestion(en="Question", ru="   ")


def test_faq_enforces_sources_dates_risk_and_question_limit() -> None:
    valid = make_faq()
    assert valid.verified_on == date(2026, 6, 1)

    with pytest.raises(ValidationError):
        FAQRecord.model_validate(
            {
                **make_faq().model_dump(),
                "source_ids": ["official-source", "official-source"],
            }
        )

    with pytest.raises(ValidationError):
        FAQRecord(
            **{
                **make_faq().model_dump(),
                "verified_on": "2026-12-02",
                "review_by": "2026-12-01",
            }
        )

    with pytest.raises(ValidationError):
        FAQRecord(
            **{
                **make_faq().model_dump(),
                "question": {"en": "x" * 501, "ru": "Вопрос"},
            }
        )


def test_source_requires_https_and_known_language() -> None:
    assert make_source().url.scheme == "https"

    with pytest.raises(ValidationError):
        SourceRecord(
            **{
                **make_source().model_dump(),
                "url": "http://example.edu/guidance",
            }
        )

    with pytest.raises(ValidationError):
        SourceRecord(
            **{
                **make_source().model_dump(),
                "language": "de",
            }
        )


def test_datasets_enforce_exact_faq_count_unique_ids_and_source_references() -> None:
    faqs = [make_faq(index) for index in range(1, 16)]
    faq_dataset = FAQDataset(faqs=faqs)
    source_dataset = SourceDataset(sources=[make_source()])

    knowledge = KnowledgeBase(faq=faq_dataset, source=source_dataset)
    assert len(knowledge.faq.faqs) == 15

    with pytest.raises(ValidationError):
        FAQDataset(faqs=faqs[:14])

    with pytest.raises(ValidationError):
        FAQDataset(faqs=[*faqs[:14], make_faq(14)])

    with pytest.raises(ValidationError):
        KnowledgeBase(
            faq=FAQDataset(
                faqs=[
                    make_faq(index, source_id="missing-source")
                    for index in range(1, 16)
                ]
            ),
            source=source_dataset,
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"match_status": "matched", "matches": []},
        {
            "match_status": "no_match",
            "matches": [{"faq_id": "faq-1", "confidence": 0.9}],
        },
        {
            "match_status": "matched",
            "matches": [
                {"faq_id": "faq-1", "confidence": 0.9},
                {"faq_id": "faq-1", "confidence": 0.8},
            ],
        },
        {
            "match_status": "matched",
            "matches": [
                {"faq_id": "faq-1", "confidence": 0.9},
                {"faq_id": "faq-2", "confidence": 0.8},
                {"faq_id": "faq-3", "confidence": 0.7},
            ],
        },
        {
            "match_status": "matched",
            "matches": [{"faq_id": "faq-1", "confidence": 1.1}],
        },
        {
            "match_status": "matched",
            "matches": [{"faq_id": "faq-1", "confidence": "0.9"}],
        },
    ],
)
def test_classifier_output_rejects_inconsistent_or_malformed_matches(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ClassifierOutput.model_validate(payload)


def test_classifier_output_accepts_zero_to_two_consistent_matches() -> None:
    no_match = ClassifierOutput(match_status="no_match", matches=[])
    matched = ClassifierOutput(
        match_status="matched",
        matches=[
            {"faq_id": "faq-1", "confidence": 0.91},
            {"faq_id": "faq-2", "confidence": 0.82},
        ],
    )

    assert no_match.matches == []
    assert [item.faq_id for item in matched.matches] == ["faq-1", "faq-2"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "x" * 81),
        ("contact", "not-a-contact"),
        ("program", "x" * 121),
        ("timeline", "x" * 81),
        ("question", "x" * 501),
        ("study_level", "secondary_school"),
        ("interface_language", "zh"),
        ("consent", False),
    ],
)
def test_inquiry_enforces_required_fields_limits_and_consent(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        make_inquiry(**{field: value})


def test_inquiry_accepts_email_or_telegram_and_normalizes_optional_program() -> None:
    email = make_inquiry(
        contact="alex.study+china@example-study.com",
        program="  ",
    )
    telegram = make_inquiry(contact="@valid_user")

    assert email.program is None
    assert telegram.contact == "@valid_user"


@pytest.mark.parametrize(
    "contact",
    [
        ".lead@example.com",
        "lead.@example.com",
        "lead..name@example.com",
        "lead@example..com",
        "lead@-example.com",
        "lead@example-.com",
    ],
)
def test_inquiry_rejects_structurally_invalid_email(contact: str) -> None:
    with pytest.raises(ValidationError):
        make_inquiry(contact=contact)

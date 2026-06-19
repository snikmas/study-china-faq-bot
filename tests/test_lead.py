import pytest
from pydantic import ValidationError

from app.lead import summarize_inquiry, validate_inquiry
from app.models import Inquiry


def make_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Alex",
        "contact": "alex@example.com",
        "study_level": "master",
        "program": "Computer Science",
        "timeline": "September 2027",
        "question": "Which documents should I prepare?",
        "interface_language": "en",
        "consent": True,
    }
    payload.update(overrides)
    return payload


def test_validate_inquiry_returns_model_and_strips_values() -> None:
    inquiry = validate_inquiry(
        make_payload(name="  Alex  ", contact=" @valid_user ", program="  ")
    )

    assert isinstance(inquiry, Inquiry)
    assert inquiry.name == "Alex"
    assert inquiry.contact == "@valid_user"
    assert inquiry.program is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("name", "x" * 81),
        ("contact", "not-a-contact"),
        ("contact", "lead@example..com"),
        ("study_level", "secondary_school"),
        ("program", "x" * 121),
        ("timeline", "x" * 81),
        ("question", "x" * 501),
        ("interface_language", "zh"),
        ("consent", False),
    ],
)
def test_validate_inquiry_enforces_fields_limits_contact_and_consent(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        validate_inquiry(make_payload(**{field: value}))


def test_validate_inquiry_requires_all_required_fields() -> None:
    payload = make_payload()
    del payload["timeline"]

    with pytest.raises(ValidationError):
        validate_inquiry(payload)


def test_summarize_inquiry_provides_bilingual_labels_without_persistence() -> None:
    inquiry = validate_inquiry(make_payload(study_level="doctorate", interface_language="ru"))
    summary = summarize_inquiry(inquiry)

    assert summary.study_level_en == "Doctorate"
    assert summary.study_level_ru == "Докторантура"
    assert summary.interface_language_en == "Russian"
    assert summary.interface_language_ru == "Русский"
    assert summary.consent is True

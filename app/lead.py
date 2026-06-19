"""Inquiry helpers without local lead persistence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.models import Inquiry


STUDY_LEVEL_LABELS: Mapping[str, tuple[str, str]] = {
    "language_program": ("Language program", "Языковая программа"),
    "bachelor": ("Bachelor", "Бакалавриат"),
    "master": ("Master", "Магистратура"),
    "doctorate": ("Doctorate", "Докторантура"),
    "other": ("Other", "Другое"),
}

INTERFACE_LANGUAGE_LABELS: Mapping[str, tuple[str, str]] = {
    "en": ("English", "Английский"),
    "ru": ("Russian", "Русский"),
}


@dataclass(frozen=True, slots=True)
class InquirySummary:
    name: str
    contact: str
    study_level_en: str
    study_level_ru: str
    program: str | None
    timeline: str
    question: str
    interface_language_en: str
    interface_language_ru: str
    consent: bool


def validate_inquiry(payload: Mapping[str, object] | Inquiry) -> Inquiry:
    """Return a validated inquiry using the shared model contract."""

    if isinstance(payload, Inquiry):
        return payload
    return Inquiry.model_validate(payload)


def summarize_inquiry(inquiry: Inquiry) -> InquirySummary:
    """Prepare display-ready values without storing inquiry history."""

    study_level_en, study_level_ru = STUDY_LEVEL_LABELS[inquiry.study_level.value]
    language_en, language_ru = INTERFACE_LANGUAGE_LABELS[
        inquiry.interface_language.value
    ]
    return InquirySummary(
        name=inquiry.name,
        contact=inquiry.contact,
        study_level_en=study_level_en,
        study_level_ru=study_level_ru,
        program=inquiry.program,
        timeline=inquiry.timeline,
        question=inquiry.question,
        interface_language_en=language_en,
        interface_language_ru=language_ru,
        consent=inquiry.consent,
    )


__all__ = [
    "INTERFACE_LANGUAGE_LABELS",
    "InquirySummary",
    "STUDY_LEVEL_LABELS",
    "summarize_inquiry",
    "validate_inquiry",
]

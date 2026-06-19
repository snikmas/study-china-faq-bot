"""Typed contracts for knowledge, classifier output, and inquiries."""

from __future__ import annotations

import re
from datetime import date
from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)


StableId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
]
ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
QuestionText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
AnswerText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4_000),
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class InterfaceLanguage(str, Enum):
    ENGLISH = "en"
    RUSSIAN = "ru"


class SourceLanguage(str, Enum):
    CHINESE = "zh"
    ENGLISH = "en"
    RUSSIAN = "ru"
    MULTILINGUAL = "multilingual"


class RiskLabel(str, Enum):
    GENERAL_INFORMATION = "general_information"
    HUMAN_CONFIRMATION_REQUIRED = "human_confirmation_required"


class MatchStatus(str, Enum):
    MATCHED = "matched"
    NO_MATCH = "no_match"


class StudyLevel(str, Enum):
    LANGUAGE_PROGRAM = "language_program"
    BACHELOR = "bachelor"
    MASTER = "master"
    DOCTORATE = "doctorate"
    OTHER = "other"


class BilingualQuestion(StrictModel):
    en: QuestionText
    ru: QuestionText


class BilingualAnswer(StrictModel):
    en: AnswerText
    ru: AnswerText


class SourceRecord(StrictModel):
    id: StableId
    organization: ShortText
    page_title: ShortText
    url: HttpUrl
    language: SourceLanguage
    accessed_on: date

    @field_validator("url")
    @classmethod
    def require_https(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("source URL must use HTTPS")
        return value


class FAQRecord(StrictModel):
    id: StableId
    topic: ShortText
    question: BilingualQuestion
    answer: BilingualAnswer
    source_ids: list[StableId] = Field(min_length=1, max_length=10)
    verified_on: date
    review_by: date
    risk: RiskLabel

    @field_validator("source_ids")
    @classmethod
    def require_unique_source_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("source IDs must be unique within an FAQ record")
        return value

    @model_validator(mode="after")
    def require_valid_review_window(self) -> FAQRecord:
        if self.review_by < self.verified_on:
            raise ValueError("review_by cannot be earlier than verified_on")
        return self


class FAQDataset(StrictModel):
    faqs: list[FAQRecord] = Field(min_length=15, max_length=15)

    @model_validator(mode="after")
    def require_unique_ids(self) -> FAQDataset:
        ids = [record.id for record in self.faqs]
        if len(ids) != len(set(ids)):
            raise ValueError("FAQ IDs must be unique")
        return self


class SourceDataset(StrictModel):
    sources: list[SourceRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_ids(self) -> SourceDataset:
        ids = [record.id for record in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("source IDs must be unique")
        return self


class KnowledgeBase(StrictModel):
    faq: FAQDataset
    source: SourceDataset

    @model_validator(mode="after")
    def require_resolved_source_references(self) -> KnowledgeBase:
        known_source_ids = {record.id for record in self.source.sources}
        unresolved = sorted(
            {
                source_id
                for faq_record in self.faq.faqs
                for source_id in faq_record.source_ids
                if source_id not in known_source_ids
            }
        )
        if unresolved:
            raise ValueError("FAQ records contain unresolved source IDs")
        return self


class ClassifierMatch(StrictModel):
    faq_id: StableId
    confidence: float = Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False)


class ClassifierOutput(StrictModel):
    match_status: MatchStatus
    matches: list[ClassifierMatch] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def require_consistent_matches(self) -> ClassifierOutput:
        ids = [match.faq_id for match in self.matches]
        if len(ids) != len(set(ids)):
            raise ValueError("classifier matches must use unique FAQ IDs")
        if self.match_status is MatchStatus.MATCHED and not self.matches:
            raise ValueError("matched classifier output requires at least one match")
        if self.match_status is MatchStatus.NO_MATCH and self.matches:
            raise ValueError("no_match classifier output cannot contain matches")
        return self


class Inquiry(StrictModel):
    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
    ]
    contact: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
    ]
    study_level: StudyLevel
    program: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
    ] | None = None
    timeline: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
    ]
    question: QuestionText
    interface_language: InterfaceLanguage
    consent: bool = Field(strict=True)

    @field_validator("program", mode="before")
    @classmethod
    def normalize_optional_program(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("contact")
    @classmethod
    def require_email_or_telegram(cls, value: str) -> str:
        telegram_pattern = r"^@[A-Za-z][A-Za-z0-9_]{4,31}$"
        if re.fullmatch(telegram_pattern, value):
            return value

        if value.count("@") != 1:
            raise ValueError("contact must be an email address or @telegram username")

        local_part, domain = value.rsplit("@", 1)
        local_atom_pattern = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
        valid_local_part = (
            len(local_part) <= 64
            and re.fullmatch(
                rf"{local_atom_pattern}(?:\.{local_atom_pattern})*", local_part
            )
            is not None
        )

        domain_labels = domain.split(".")
        valid_domain = (
            len(domain) <= 253
            and len(domain_labels) >= 2
            and all(
                len(label) <= 63
                and re.fullmatch(
                    r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label
                )
                is not None
                for label in domain_labels
            )
        )

        if not valid_local_part or not valid_domain:
            raise ValueError("contact must be an email address or @telegram username")
        return value

    @field_validator("consent")
    @classmethod
    def require_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("explicit consent is required")
        return value

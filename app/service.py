"""Deterministic answer resolver for classified FAQ matches."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from app.classifier import ClassifierResult
from app.knowledge import LoadedKnowledge
from app.models import ClassifierOutput, FAQRecord, MatchStatus, RiskLabel, SourceRecord


MIN_CONFIDENCE = 0.70
MAX_MATCHES = 2


class AnswerStatus(str, Enum):
    ANSWERED = "answered"
    NEEDS_CONFIRMATION = "needs_confirmation"
    UNSUPPORTED = "unsupported"
    TEMPORARY_FAILURE = "temporary_failure"


@dataclass(frozen=True, slots=True)
class Citation:
    source_id: str
    organization: str
    page_title: str
    url: str
    language: str
    accessed_on: str


@dataclass(frozen=True, slots=True)
class AnswerItem:
    faq_id: str
    topic: str
    answer_en: str
    answer_ru: str
    risk: str
    citations: tuple[Citation, ...]


@dataclass(frozen=True, slots=True)
class AnswerResponse:
    status: AnswerStatus
    items: tuple[AnswerItem, ...] = ()
    reason: str | None = None


def _citation(source: SourceRecord) -> Citation:
    return Citation(
        source_id=source.id,
        organization=source.organization,
        page_title=source.page_title,
        url=str(source.url),
        language=source.language.value,
        accessed_on=source.accessed_on.isoformat(),
    )


def _answer_item(faq: FAQRecord, sources: Sequence[SourceRecord]) -> AnswerItem:
    return AnswerItem(
        faq_id=faq.id,
        topic=faq.topic,
        answer_en=faq.answer.en,
        answer_ru=faq.answer.ru,
        risk=faq.risk.value,
        citations=tuple(_citation(source) for source in sources),
    )


def resolve_answer(
    classifier_output: ClassifierOutput | ClassifierResult | None,
    knowledge: LoadedKnowledge,
) -> AnswerResponse:
    """Resolve a classifier result using stored records only."""

    if classifier_output is None:
        return AnswerResponse(
            status=AnswerStatus.TEMPORARY_FAILURE,
            reason="classifier output was missing",
        )

    if isinstance(classifier_output, ClassifierResult):
        if classifier_output.malformed or classifier_output.output is None:
            return AnswerResponse(
                status=AnswerStatus.TEMPORARY_FAILURE,
                reason="classifier output was malformed",
            )
        output = classifier_output.output
    else:
        output = classifier_output

    if output.match_status is MatchStatus.NO_MATCH:
        return AnswerResponse(
            status=AnswerStatus.UNSUPPORTED,
            reason="classifier found no supported FAQ match",
        )

    if len(output.matches) > MAX_MATCHES:
        return AnswerResponse(
            status=AnswerStatus.TEMPORARY_FAILURE,
            reason="classifier returned too many matches",
        )

    ids = [match.faq_id for match in output.matches]
    if len(ids) != len(set(ids)):
        return AnswerResponse(
            status=AnswerStatus.TEMPORARY_FAILURE,
            reason="classifier returned duplicate matches",
        )

    if any(match.confidence < MIN_CONFIDENCE for match in output.matches):
        return AnswerResponse(
            status=AnswerStatus.UNSUPPORTED,
            reason="classifier confidence was below the safe threshold",
        )

    faq_index = {faq.id: faq for faq in knowledge.faqs}
    if any(faq_id not in faq_index for faq_id in ids):
        return AnswerResponse(
            status=AnswerStatus.TEMPORARY_FAILURE,
            reason="classifier returned an unknown FAQ ID",
        )

    faqs = tuple(faq_index[faq_id] for faq_id in ids)
    items = tuple(_answer_item(faq, knowledge.sources_for(faq)) for faq in faqs)
    if any(faq.risk is RiskLabel.HUMAN_CONFIRMATION_REQUIRED for faq in faqs):
        return AnswerResponse(
            status=AnswerStatus.NEEDS_CONFIRMATION,
            items=items,
            reason="matched FAQ requires human confirmation",
        )

    return AnswerResponse(status=AnswerStatus.ANSWERED, items=items)

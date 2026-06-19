"""Deterministic loading and freshness filtering for reviewed FAQ data."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from json import JSONDecodeError
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from pydantic import ValidationError

from app.models import FAQDataset, FAQRecord, KnowledgeBase, SourceDataset, SourceRecord


class KnowledgeLoadError(ValueError):
    """Raised when stored knowledge cannot be safely loaded."""


@dataclass(frozen=True, slots=True)
class LoadedKnowledge:
    """Current FAQ records and their validated source index."""

    faqs: tuple[FAQRecord, ...]
    sources: Mapping[str, SourceRecord]

    def sources_for(self, faq: FAQRecord) -> tuple[SourceRecord, ...]:
        return tuple(self.sources[source_id] for source_id in faq.source_ids)


def _read_json(path: Path) -> object:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, UnicodeError, JSONDecodeError) as exc:
        raise KnowledgeLoadError(f"Unable to load valid UTF-8 JSON from {path.name}") from exc


def load_knowledge(
    faq_path: str | Path = "faq.json",
    sources_path: str | Path = "sources.json",
    *,
    current_utc_date: date | None = None,
) -> LoadedKnowledge:
    """Validate all stored data, then return records current on the UTC date.

    A record remains eligible throughout its ``review_by`` date. It is filtered
    only when the current UTC date is strictly later.
    """

    faq_file = Path(faq_path)
    sources_file = Path(sources_path)

    try:
        faq_dataset = FAQDataset.model_validate(_read_json(faq_file))
        source_dataset = SourceDataset.model_validate(_read_json(sources_file))
        knowledge = KnowledgeBase(faq=faq_dataset, source=source_dataset)
    except ValidationError as exc:
        raise KnowledgeLoadError("Stored knowledge failed schema validation") from exc

    today = current_utc_date or datetime.now(timezone.utc).date()
    current_faqs = tuple(
        record for record in knowledge.faq.faqs if today <= record.review_by
    )
    source_index = MappingProxyType(
        {record.id: record for record in knowledge.source.sources}
    )
    return LoadedKnowledge(faqs=current_faqs, sources=source_index)
